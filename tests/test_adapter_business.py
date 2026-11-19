'''Cross-adapter business contracts for offline event and outbound paths.'''

import inspect
import queue
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import OlivOS
from adapter_test_support import (
    ADAPTER_BUSINESS_CASES,
    CORE_INBOUND_CAPABILITIES,
    INBOUND_BUILDERS,
    INBOUND_CASES,
    OUTBOUND_ACTION_CASES,
    OUTBOUND_PRIVATE_REPLY_CASES,
    OUTBOUND_PRIVATE_SEND_CASES,
    OUTBOUND_REPLY_CASES,
    OUTBOUND_SEND_CASES,
    SDK_PLATFORMS,
    assert_outbound_call,
    expected_group_id,
    install_outbound_recorder,
    make_bot,
    make_sdk_event,
    prepare_sdk,
)


def _event_data_value(event, path):
    value = event.data
    for part in path.split('.'):
        value = getattr(value, part)
    return value


@pytest.fixture(params=ADAPTER_BUSINESS_CASES)
def business_case(request, monkeypatch):
    name = request.param
    bot = make_bot(name)
    module, network = prepare_sdk(name, bot, monkeypatch)
    yield NS(name=name, case=ADAPTER_BUSINESS_CASES[name], bot=bot, module=module, network=network)
    network.assert_not_called()


def test_group_message_matches_business_matrix(business_case):
    spec = business_case.case.inbound['group_message']
    event = OlivOS.API.Event(
        make_sdk_event(business_case.name, business_case.module, business_case.bot, 'group_message')
    )
    assert event.active
    assert event.plugin_info['func_type'] == spec.func_type
    assert str(event.data.group_id) == expected_group_id(business_case.name)


@pytest.mark.parametrize(
    'name,capability,spec',
    INBOUND_CASES,
    ids=[name + '-' + capability for name, capability, _ in INBOUND_CASES],
)
def test_declared_inbound_event_matches_matrix(name, capability, spec, monkeypatch):
    bot = make_bot(name)
    module, network = prepare_sdk(name, bot, monkeypatch)
    event = OlivOS.API.Event(make_sdk_event(name, module, bot, capability))
    assert event.active, (name, capability)
    assert event.plugin_info['func_type'] == spec.func_type, (name, capability)
    for path, expected in spec.checks.items():
        assert _event_data_value(event, path) == expected, (name, capability, path)
    network.assert_not_called()


@pytest.mark.parametrize('name,spec', OUTBOUND_REPLY_CASES, ids=[name for name, _ in OUTBOUND_REPLY_CASES])
def test_group_reply_uses_declared_adapter_boundary(name, spec, monkeypatch):
    bot = make_bot(name)
    module, network = prepare_sdk(name, bot, monkeypatch)
    recorder = install_outbound_recorder(name, spec.method, monkeypatch)
    event = OlivOS.API.Event(make_sdk_event(name, module, bot, spec.event))
    event.reply('reply-text')
    assert_outbound_call(recorder, event, 'reply-text', event.data.group_id, spec.target_aware)
    network.assert_not_called()


@pytest.mark.parametrize(
    'name,spec',
    OUTBOUND_PRIVATE_REPLY_CASES,
    ids=[name for name, _ in OUTBOUND_PRIVATE_REPLY_CASES],
)
def test_private_reply_uses_declared_adapter_boundary(name, spec, monkeypatch):
    bot = make_bot(name)
    module, network = prepare_sdk(name, bot, monkeypatch)
    recorder = install_outbound_recorder(name, spec.method, monkeypatch)
    event = OlivOS.API.Event(make_sdk_event(name, module, bot, spec.event))
    event.reply('reply-text')
    assert_outbound_call(recorder, event, 'reply-text', event.data.user_id, spec.target_aware)
    network.assert_not_called()


@pytest.mark.parametrize('name,spec', OUTBOUND_SEND_CASES, ids=[name for name, _ in OUTBOUND_SEND_CASES])
def test_group_active_send_uses_declared_adapter_boundary(name, spec, monkeypatch):
    bot = make_bot(name)
    module, network = prepare_sdk(name, bot, monkeypatch)
    recorder = install_outbound_recorder(name, spec.method, monkeypatch)
    event = OlivOS.API.Event(make_sdk_event(name, module, bot, spec.event))
    event.send('group', 7, 'active-text')
    assert_outbound_call(recorder, event, 'active-text', 7, spec.target_aware)
    network.assert_not_called()


@pytest.mark.parametrize(
    'name,spec',
    OUTBOUND_PRIVATE_SEND_CASES,
    ids=[name for name, _ in OUTBOUND_PRIVATE_SEND_CASES],
)
def test_private_active_send_uses_declared_adapter_boundary(name, spec, monkeypatch):
    bot = make_bot(name)
    module, network = prepare_sdk(name, bot, monkeypatch)
    recorder = install_outbound_recorder(name, spec.method, monkeypatch)
    event = OlivOS.API.Event(make_sdk_event(name, module, bot, spec.event))
    event.send('private', 42, 'active-text')
    assert_outbound_call(recorder, event, 'active-text', 42, spec.target_aware)
    network.assert_not_called()


@pytest.mark.parametrize(
    'name,capability,spec',
    OUTBOUND_ACTION_CASES,
    ids=[name + '-' + capability for name, capability, _ in OUTBOUND_ACTION_CASES],
)
def test_declared_action_uses_adapter_boundary(name, capability, spec, monkeypatch):
    bot = make_bot(name)
    module, network = prepare_sdk(name, bot, monkeypatch)
    recorder = install_outbound_recorder(name, spec.method, monkeypatch)
    event = OlivOS.API.Event(make_sdk_event(name, module, bot, spec.event))
    getattr(event, spec.event_method)(*spec.args)
    assert_outbound_call(recorder, event, expected_values=spec.expected)
    network.assert_not_called()


def test_every_sdk_has_business_case():
    assert set(ADAPTER_BUSINESS_CASES) == set(SDK_PLATFORMS)


def test_core_inbound_capabilities_are_present_or_explicitly_exempt():
    missing = {}
    for name, case in ADAPTER_BUSINESS_CASES.items():
        absent = CORE_INBOUND_CAPABILITIES - set(case.inbound)
        if absent:
            missing[name] = sorted(absent)
    assert missing == {}


def test_every_declared_inbound_capability_has_builder():
    missing = []
    for name, capability, _ in INBOUND_CASES:
        if capability not in INBOUND_BUILDERS:
            missing.append((name, capability))
    assert missing == []


def test_declared_inbound_capabilities_exist_in_sdk_source():
    missing = []
    for name, capability, _ in INBOUND_CASES:
        source = inspect.getsource(getattr(OlivOS, name).get_Event_from_SDK)
        if capability not in source:
            missing.append((name, capability))
    assert missing == []


def test_every_sdk_declares_core_outbound_capabilities():
    required = {'reply_group', 'send_group'}
    missing = {}
    for name, case in ADAPTER_BUSINESS_CASES.items():
        absent = required - set(case.outbound) - set(getattr(case, 'exemptions', {}))
        if absent:
            missing[name] = sorted(absent)
    assert missing == {}


def test_declared_inbound_and_outbound_specs_are_consistent():
    assert all(capability == spec.func_type for _, capability, spec in INBOUND_CASES)
    assert all(spec.event in INBOUND_BUILDERS for _, spec in OUTBOUND_REPLY_CASES + OUTBOUND_SEND_CASES)
    assert all(spec.event in INBOUND_BUILDERS for _, spec in OUTBOUND_PRIVATE_REPLY_CASES + OUTBOUND_PRIVATE_SEND_CASES)
    assert all(spec.event in INBOUND_BUILDERS for _, _, spec in OUTBOUND_ACTION_CASES)


def test_declared_outbound_exemptions_are_documented():
    missing = []
    for name, case in ADAPTER_BUSINESS_CASES.items():
        for capability, reason in getattr(case, 'exemptions', {}).items():
            if not reason or capability in case.outbound:
                missing.append((name, capability))
    assert missing == []


def test_declared_outbound_capabilities_exist_on_event_action():
    missing = []
    for name, case in ADAPTER_BUSINESS_CASES.items():
        action = getattr(getattr(OlivOS, name), 'event_action', None)
        specs = list(case.outbound.values()) + list(getattr(case, 'actions', {}).values())
        for spec in specs:
            if not callable(getattr(action, spec.method, None)):
                missing.append((name, spec.method))
    assert missing == []


def test_declared_action_event_methods_exist():
    missing = []
    for name, capability, spec in OUTBOUND_ACTION_CASES:
        if not callable(getattr(OlivOS.API.Event, spec.event_method, None)):
            missing.append((name, capability, spec.event_method))
    assert missing == []


@pytest.mark.parametrize(
    'capability,method,target',
    [
        ('group_message', 'send_group_msg', 7),
        ('private_message', 'send_private_msg', 42),
        ('group_member_increase', 'send_group_msg', 7),
    ],
    ids=['group', 'private', 'member-increase'],
)
def test_plugin_callback_reply_reaches_adapter_boundary(capability, method, target, monkeypatch):
    name = 'onebotSDK'
    bot = make_bot(name)
    module, network = prepare_sdk(name, bot, monkeypatch)
    recorder = install_outbound_recorder(name, method, monkeypatch)
    loader = OlivOS.pluginAPI.shallow(
        control_queue=queue.Queue(), rx_queue=queue.Queue(), bot_info_dict={bot.hash: bot}
    )
    loader.log = Mock()
    seen = {}

    def callback(plugin_event, Proc):
        seen['event'] = plugin_event
        plugin_event.reply('plugin-reply')

    spec = ADAPTER_BUSINESS_CASES[name].inbound[capability]
    loader.plugin_models_call_list.append('business_probe')
    loader.plugin_models_dict['business_probe'] = {
        'name': 'business_probe',
        'namespace': 'business_probe',
        'support': [{'sdk': 'all', 'platform': 'all', 'model': 'all'}],
        'message_mode': 'olivos_string',
        'priority': 30000,
        'version': '1',
        'svn': 1,
        'author': 'N/A',
        'info': 'N/A',
        'folder_path': '',
        'menu_config': None,
        'model': NS(main=NS(Event=NS(**{spec.func_type: callback}))),
    }
    loader.run_plugin(make_sdk_event(name, module, bot, capability))
    recorder.assert_called_once()
    assert_outbound_call(recorder, seen['event'], 'plugin-reply', target)
    network.assert_not_called()
