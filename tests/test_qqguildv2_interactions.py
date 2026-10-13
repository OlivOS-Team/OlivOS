# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_interactions.py
@Author    :   OlivOS-Team
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   QQ API V2 按钮事件投递与自动应答测试
'''

import copy
import json
import queue
import threading
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlparse

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common

SDK = OlivOS.qqGuildv2SDK
BUTTON_DATA = '{"value":"&amp;[OP:at,id=42]"}'
SCENES = [
    ('group', 1, {'group_openid': 'group', 'group_member_openid': 'member'},
     'qq_group', 'group', 'member', 'group', None),
    ('c2c', 2, {'user_openid': 'user'},
     'qq_private', 'user', 'user', None, None),
    ('guild', 0, {'guild_id': 'guild', 'channel_id': 'channel'},
     'guild_channel', 'channel', 'channel-user', 'channel', 'guild'),
]


@pytest.fixture(params=['public', 'private', 'sandbox', 'public_intents', 'private_intents', 'sandbox_intents'])
def bot(request, monkeypatch):
    bot = OlivOS.API.bot_info_T(
        id=10001, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=request.param
    )
    monkeypatch.setattr(common, 'sdkSelfInfo', {bot.hash: {'id': 'bot', 'username': 'bot'}})
    for name in ['qqEventDedupeCache', 'sdkSubSelfInfo', 'sdkUnhandledEventInfo', 'sdkEventidinfo']:
        monkeypatch.setattr(common, name, {})
    monkeypatch.setattr(common.req, 'request', Mock(side_effect=AssertionError('Unexpected network call')))
    monkeypatch.setattr(common, '_interaction_ack_pool', common._InteractionAckPool())
    return bot


@pytest.fixture
def ack(monkeypatch):
    completed = threading.Event()
    callback = Mock(side_effect=lambda *args: completed.set())
    monkeypatch.setattr(SDK.event_action, '_ack_interaction_plant', callback)
    return callback, completed


def interaction(bot, body):
    return SDK.event(SDK.PAYLOAD.rxPacket({
        'op': 0, 's': 7, 'id': 'INTERACTION_CREATE:interaction-1',
        't': 'INTERACTION_CREATE', 'd': body
    }), bot)


def button_body(scene='group', chat_type=1, fields=None):
    return {
        'id': 'interaction-1', 'type': 11, 'scene': scene, 'chat_type': chat_type,
        'data': {'type': 11, 'resolved': {
            'button_id': 'confirm', 'button_data': BUTTON_DATA,
            'user_id': 'channel-user', 'message_id': 'source-message'
        }},
        **(fields or {'group_openid': 'group', 'group_member_openid': 'member'})
    }


def loader_for(bot, callbacks):
    loader = OlivOS.pluginAPI.shallow(
        control_queue=queue.Queue(), rx_queue=queue.Queue(), bot_info_dict={bot.hash: bot}
    )
    loader.log = Mock()
    for name, handlers, support in callbacks:
        loader.plugin_models_call_list.append(name)
        loader.plugin_models_dict[name] = {
            'name': name, 'namespace': name,
            'support': support or [{'sdk': 'all', 'platform': 'all', 'model': 'all'}],
            'message_mode': 'old_string',
            'model': SimpleNamespace(main=SimpleNamespace(Event=SimpleNamespace(**handlers)))
        }
    return loader


@pytest.mark.parametrize('scene,chat_type,fields,target_type,chat_id,user_id,group_id,host_id', SCENES)
def test_button_click_reaches_plugin_with_original_data(
    bot, ack, scene, chat_type, fields, target_type, chat_id, user_id, group_id, host_id
):
    callback, message_callback = Mock(), Mock()
    loader = loader_for(bot, [('probe', {
        'button_click': callback, 'group_message': message_callback, 'private_message': message_callback
    }, None)])
    body = button_body(scene, chat_type, fields)
    original = copy.deepcopy(body)

    loader.run_plugin(interaction(bot, body))

    callback.assert_called_once()
    message_callback.assert_not_called()
    event = callback.call_args.kwargs['plugin_event']
    assert callback.call_args.kwargs['Proc'] is loader
    assert event.bot_info is bot
    assert event.data.button_id == 'confirm'
    assert event.data.button_data == BUTTON_DATA
    assert (event.data.user_id, event.data.group_id, event.data.host_id) == (user_id, group_id, host_id)
    assert event.data.message_id == 'source-message'
    assert event.data.extend['chat_type'] == target_type
    assert event.data.extend['chat_id'] == chat_id
    assert event.data.extend['interaction_id'] == 'interaction-1'
    assert event.data.extend['event_id'] == 'interaction-1'
    assert event.data.extend['qq_payload_id'] == 'INTERACTION_CREATE:interaction-1'
    assert event.data.extend['qq_event_data'] == original
    assert body == original
    assert common.sdkUnhandledEventInfo == {}
    assert ack[1].wait(1)
    ack[0].assert_called_once()
    assert ack[0].call_args.args[1:] == ('interaction-1', 0)


def test_button_flood_bounds_ack_workers_and_queue_without_blocking_plugins(bot, monkeypatch):
    monkeypatch.setattr(common, '_interaction_ack_pool', common._InteractionAckPool(max_workers=2, max_pending=2))
    release = threading.Event()
    started = threading.Condition()
    ack_ids = []
    delivered = []
    original_threads = set(threading.enumerate())

    def slow_ack(bot_info, interaction_id, code):
        with started:
            ack_ids.append(interaction_id)
            started.notify_all()
        assert release.wait(3)

    monkeypatch.setattr(SDK.event_action, '_ack_interaction_plant', slow_ack)
    loader = loader_for(bot, [('probe', {'button_click': lambda plugin_event, Proc: delivered.append(
        (plugin_event.data.extend['interaction_id'], plugin_event.data.extend['qq_auto_ack'])
    )}, None)])

    def dispatch(index):
        body = button_body()
        body['id'] = 'flood-%s' % index
        loader.run_plugin(interaction(bot, body))

    try:
        for index in range(2):
            dispatch(index)
        with started:
            assert started.wait_for(lambda: len(ack_ids) == 2, timeout=1)
        for index in range(2, 12):
            dispatch(index)
        assert len(delivered) == 12
        assert [scheduled for _, scheduled in delivered] == [True] * 4 + [False] * 8
        assert len(ack_ids) == 2
        assert len(set(threading.enumerate()) - original_threads) == 2
    finally:
        release.set()
        for thread in set(threading.enumerate()) - original_threads:
            thread.join(2)
    assert sorted(ack_ids) == ['flood-0', 'flood-1', 'flood-2', 'flood-3']
    dispatch(12)
    for thread in set(threading.enumerate()) - original_threads:
        thread.join(2)
    assert delivered[-1] == ('flood-12', True)
    assert ack_ids[-1] == 'flood-12'


def test_ack_worker_recovers_after_request_exception(bot, monkeypatch, capsys):
    monkeypatch.setattr(common, '_interaction_ack_pool', common._InteractionAckPool(max_workers=1, max_pending=1))
    request = Mock(side_effect=[RuntimeError('simulated ACK failure'), None])
    monkeypatch.setattr(SDK.event_action, '_ack_interaction_plant', request)
    original_threads = set(threading.enumerate())
    for index in range(2):
        body = button_body()
        body['id'] = 'recover-%s' % index
        event = OlivOS.API.Event(interaction(bot, body))
        assert event.active and event.data.extend['qq_auto_ack']
        for thread in set(threading.enumerate()) - original_threads:
            thread.join(2)
    assert request.call_count == 2
    assert 'simulated ACK failure' in capsys.readouterr().err


def test_ack_thread_start_failure_keeps_button_delivery_and_releases_capacity(bot, ack, monkeypatch, capsys):
    logger = Mock()
    with monkeypatch.context() as patch:
        thread = Mock()
        thread.start.side_effect = RuntimeError('simulated thread start failure')
        patch.setattr(common.threading, 'Thread', Mock(return_value=thread))
        event = OlivOS.API.Event(interaction(bot, button_body()), logger)
    assert event.active and event.data.extend['qq_auto_ack'] is False
    ack[0].assert_not_called()
    assert any(call.args[0] == 3 for call in logger.call_args_list)
    assert 'simulated thread start failure' in capsys.readouterr().err
    body = button_body()
    body['id'] = 'retry-new-interaction'
    event = OlivOS.API.Event(interaction(bot, body))
    assert event.data.extend['qq_auto_ack']
    assert ack[1].wait(1)


def test_ack_pool_discards_expired_queued_requests(bot, monkeypatch):
    pool = common._InteractionAckPool(max_workers=1, max_pending=1)
    release, started = threading.Event(), threading.Event()
    ack_ids = []
    now = [10.0]
    original_threads = set(threading.enumerate())

    def slow_ack(bot_info, interaction_id, code):
        ack_ids.append(interaction_id)
        if interaction_id == 'running':
            started.set()
            assert release.wait(3)

    monkeypatch.setattr(SDK.event_action, '_ack_interaction_plant', slow_ack)
    monkeypatch.setattr(common.time, 'monotonic', lambda: now[0])
    try:
        assert pool.submit(None, 'running')
        assert started.wait(1)
        assert pool.submit(None, 'expired')
        now[0] += common.sdkInteractionAckMaxQueueAge + 1
    finally:
        release.set()
        for thread in set(threading.enumerate()) - original_threads:
            thread.join(2)
    assert ack_ids == ['running']
    assert pool.submit(None, 'fresh')
    for thread in set(threading.enumerate()) - original_threads:
        thread.join(2)
    assert ack_ids == ['running', 'fresh']


@pytest.mark.parametrize('scene,chat_type,fields,target_type,chat_id,user_id,group_id,host_id', SCENES)
def test_button_click_supports_payload_without_scene_or_outer_type(
    bot, ack, scene, chat_type, fields, target_type, chat_id, user_id, group_id, host_id
):
    body = button_body(scene, chat_type, fields)
    del body['scene'], body['type']
    event = OlivOS.API.Event(interaction(bot, body))
    assert event.active
    assert event.plugin_info['func_type'] == 'button_click'
    assert event.data.extend['chat_type'] == target_type
    assert (event.data.user_id, event.data.group_id, event.data.host_id) == (user_id, group_id, host_id)
    assert ack[1].wait(1)


def test_button_click_missing_optional_resolved_fields_still_reaches_plugin(bot, ack):
    body = button_body()
    body['data']['resolved'] = {'button_data': ''}
    event = OlivOS.API.Event(interaction(bot, body))
    assert event.active
    assert event.data.button_data == ''
    assert event.data.button_id is None
    assert event.data.message_id is None
    assert ack[1].wait(1)


@pytest.mark.parametrize('body', [None, [], {}, {'id': 'interaction-1', 'data': None},
                                  {'id': 'interaction-1', 'type': 11, 'data': []},
                                  {'id': 'interaction-1', 'type': 11, 'data': {'resolved': []}}])
def test_malformed_interaction_is_ignored_without_breaking_next_button(bot, ack, body):
    assert not OlivOS.API.Event(interaction(bot, body)).active
    ack[0].assert_not_called()
    assert OlivOS.API.Event(interaction(bot, button_body())).active
    assert ack[1].wait(1)


@pytest.mark.parametrize('interaction_type', [12, 13, 14, 15, 16, 18, 19, 20, 99])
def test_other_interactions_stay_in_cache_and_only_menu_is_acknowledged(bot, ack, interaction_type):
    body = button_body()
    body['type'] = body['data']['type'] = interaction_type
    event = OlivOS.API.Event(interaction(bot, body))
    assert not event.active
    assert common.sdkUnhandledEventInfo[bot.hash][-1]['data'] == body
    if interaction_type == 12:
        assert ack[1].wait(1)
        ack[0].assert_called_once()
    else:
        ack[0].assert_not_called()


def test_repeated_interaction_is_dispatched_and_acknowledged_once(bot, ack):
    callback = Mock()
    loader = loader_for(bot, [('probe', {'button_click': callback}, None)])
    for _ in range(2):
        loader.run_plugin(interaction(bot, button_body()))
    callback.assert_called_once()
    assert ack[1].wait(1)
    ack[0].assert_called_once()


def test_button_click_respects_plugin_filter_and_blocking(bot, ack):
    unsupported, later = Mock(), Mock()
    blocker = Mock(side_effect=lambda plugin_event, Proc: plugin_event.set_block())
    loader = loader_for(bot, [
        ('unsupported', {'button_click': unsupported}, [{'sdk': 'onebot', 'platform': 'qq', 'model': 'all'}]),
        ('legacy', {'group_message': Mock()}, None),
        ('blocker', {'button_click': blocker}, None),
        ('later', {'button_click': later}, None)
    ])
    loader.run_plugin(interaction(bot, button_body()))
    unsupported.assert_not_called()
    blocker.assert_called_once()
    later.assert_not_called()
    assert ack[1].wait(1)


def test_button_click_log_identifies_event_without_logging_button_data(bot, ack):
    logger = Mock()
    event = OlivOS.API.Event(interaction(bot, button_body()), logger)
    assert event.active
    logger.assert_called_once()
    assert logger.call_args.args[0] == 2
    assert 'confirm' in logger.call_args.args[1]
    assert BUTTON_DATA not in logger.call_args.args[1]
    assert ack[1].wait(1)


@pytest.mark.parametrize('scene,chat_type,fields,target_type,chat_id,user_id,group_id,host_id', SCENES[:2])
def test_button_click_can_use_interaction_id_for_passive_qq_message(
    bot, ack, scene, chat_type, fields, target_type, chat_id, user_id, group_id, host_id
):
    event = OlivOS.API.Event(interaction(bot, button_body(scene, chat_type, fields)))
    assert event.active
    event.bot_info = bot
    assert SDK.event_action._resolve_qq_passive_ids(event, target_type, chat_id) == (None, 'interaction-1')
    assert SDK.event_action._resolve_qq_passive_ids(event, target_type, 'another-chat') == (None, None)
    assert ack[1].wait(1)


def test_button_click_auto_ack_sends_one_success_response(bot, monkeypatch):
    completed = threading.Event()

    def respond(*args, **kwargs):
        completed.set()
        return SimpleNamespace(text='{}', status_code=200)

    request = Mock(side_effect=respond)
    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda _: None)
    assert OlivOS.API.Event(interaction(bot, button_body())).active
    assert completed.wait(1)
    assert not OlivOS.API.Event(interaction(bot, button_body())).active
    request.assert_called_once()
    args, kwargs = request.call_args
    assert args[0] == 'PUT'
    url = urlparse(args[1])
    assert url.path == '/interactions/interaction-1'
    assert url.hostname == 'api.bot.qq.com'
    assert json.loads(kwargs['data']) == {'code': 0}


@pytest.mark.parametrize('scene,chat_type,fields,target_type,chat_id,user_id,group_id,host_id', SCENES[:2])
def test_button_click_indeapi_message_sends_passive_event_id(
    bot, ack, monkeypatch, scene, chat_type, fields, target_type, chat_id, user_id, group_id, host_id
):
    event = OlivOS.API.Event(interaction(bot, button_body(scene, chat_type, fields)))
    assert event.active
    event.bot_info = bot
    request = Mock(return_value=SimpleNamespace(text='{"id":"reply-message"}', status_code=200))
    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda _: None)
    monkeypatch.setattr(common, 'sdkMsgidinfo', {})
    monkeypatch.setattr(common, 'sdkSentMessageInfo', {})

    result = event.indeAPI.send_message(target_type, chat_id, '收到', flag_log=False)

    assert result['active']
    request.assert_called_once()
    args, kwargs = request.call_args
    assert args[0] == 'POST'
    assert urlparse(args[1]).path == (
        '/v2/groups/group/messages' if target_type == 'qq_group' else '/v2/users/user/messages'
    )
    body = json.loads(kwargs['data'])
    assert body['event_id'] == 'interaction-1'
    assert 'msg_id' not in body
    assert body['content'] == '收到'
    assert ack[1].wait(1)
