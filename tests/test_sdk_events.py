'''Shared offline event contracts for every SDK dispatched by OlivOS.API.Event.

Payload builders and platform metadata live in adapter_test_support so business
tests and the event contract matrix use the same fixtures.
'''

import ast
import inspect
import textwrap
from types import SimpleNamespace as NS

import pytest

import OlivOS
from adapter_test_support import (
    SDK_PLATFORMS,
    expected_group_id,
    make_bot,
    make_sdk_group_event,
    prepare_sdk,
)


def test_event_contract_matrix_covers_every_dispatched_sdk():
    '''New SDK dispatch branches must explicitly add a functional fixture.'''
    tree = ast.parse(textwrap.dedent(inspect.getsource(OlivOS.API.Event.get_Event_from_SDK)))
    routed = {
        node.value.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == 'get_Event_from_SDK'
        and isinstance(node.value, ast.Attribute)
    }
    assert set(SDK_PLATFORMS) == routed


@pytest.fixture(params=SDK_PLATFORMS)
def sdk_case(request, monkeypatch):
    name = request.param
    bot = make_bot(name)
    module, network = prepare_sdk(name, bot, monkeypatch)

    def make(text='hello', unsupported=False):
        return make_sdk_group_event(name, module, bot, text=text, unsupported=unsupported)

    yield NS(name=name, make=make, bot=bot)
    network.assert_not_called()


def test_sdk_group_event_maps_sender_and_conversation(sdk_case):
    event = OlivOS.API.Event(sdk_case.make())
    assert event.active and event.plugin_info['func_type'] == 'group_message'
    assert str(event.data.user_id) == '42'
    assert str(event.base_info['self_id']) == '10001'
    assert str(event.data.group_id) == expected_group_id(sdk_case.name)


@pytest.mark.parametrize('text', ['hello', '中文消息 \U0001f98a'])
def test_sdk_text_message_reaches_plugin_unchanged(sdk_case, text):
    event = OlivOS.API.Event(sdk_case.make(text))
    assert event.active
    assert event.data.message_sdk.get('olivos_string') == text


def test_sdk_unhandled_input_is_not_delivered_as_a_message(sdk_case):
    event = OlivOS.API.Event(sdk_case.make(unsupported=True))
    assert not event.active


def test_sdk_valid_message_after_unhandled_input_is_still_delivered(sdk_case):
    assert not OlivOS.API.Event(sdk_case.make(unsupported=True)).active
    event = OlivOS.API.Event(sdk_case.make('next message'))
    assert event.active and event.data.message_sdk.get('olivos_string') == 'next message'


@pytest.mark.parametrize(
    'payload',
    [
        None,
        [],
        {},
        {'Content': 'incomplete'},
        {
            'FromChannel': '7',
            'Uid': '42',
            'Content': 'hello',
            'OriginalContent': None,
            'Id': '8',
            'NickName': 'tester',
        },
    ],
)
def test_dodo_ea_incomplete_record_is_rejected_without_exception(payload):
    bot = OlivOS.API.bot_info_T(id=10001)
    assert not OlivOS.API.Event(OlivOS.dodobotEASDK.event(payload, bot)).active
