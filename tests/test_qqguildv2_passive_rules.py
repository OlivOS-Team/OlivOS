# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_passive_rules.py
@Author    :   Desom-fu
@Contact   :   desom233@outlook.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   2026-11-17 群消息被动回复规则：私聊回复、50 次上限、60 分钟有效期
'''

import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common

SDK = OlivOS.qqGuildv2SDK


@pytest.fixture
def bot(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    bot = OlivOS.API.bot_info_T(
        id=10001, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model='public'
    )
    monkeypatch.setattr(common, 'sdkSelfInfo', {bot.hash: {'id': 'bot', 'username': 'bot'}})
    for name in [
        'qqEventDedupeCache', 'sdkUserInfo', 'sdkSubSelfInfo',
        'sdkRxMessageInfo', 'sdkForwardMessageInfo', 'sdkMsgIdxInfo',
        'sdkMsgidinfo', 'sdkEventidinfo', 'sdkSentMessageInfo',
        'sdkGroupPassiveLimitInfo'
    ]:
        monkeypatch.setattr(common, name, {})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args: 'bot')
    monkeypatch.setattr(common.req, 'request', Mock(side_effect=AssertionError('Unexpected network call')))
    return bot


def message_event(bot, event_type, data=None):
    body = {
        'id': 'test-message',
        'author': {'member_openid': 'member', 'user_openid': 'user', 'username': 'tester'},
        'group_openid': 'group',
        'content': '',
        'timestamp': '2026-11-18T12:00:00+08:00',
        **(data or {})
    }
    payload = SDK.PAYLOAD.rxPacket({'op': 0, 's': 1, 't': event_type, 'd': body})
    event = OlivOS.API.Event(SDK.event(payload, bot))
    event.bot_info = bot
    return event


def send_recorder(monkeypatch, responses=None):
    responses = responses or [(200, {'id': 'reply-message'})]
    request = Mock(side_effect=[
        SimpleNamespace(text=json.dumps(body), status_code=status)
        for status, body in responses
    ])
    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda _: None)
    return request


def test_group_message_id_resolves_for_private_reply_to_sender(bot):
    event = message_event(bot, 'GROUP_MESSAGE_CREATE')
    event.data.extend['reply_msg_id'] = 'group-msg'

    msg_id, event_id = SDK.event_action._resolve_qq_passive_ids(
        event, 'qq_private', 'member'
    )
    assert (msg_id, event_id) == ('group-msg', None)

    # 群消息的凭据只能用来回复这条消息的发送者，目标换成别人就没有凭据。
    assert SDK.event_action._resolve_qq_passive_ids(
        event, 'qq_private', 'other-member'
    ) == (None, None)


def test_private_reply_passes_group_message_id_to_direct_api(bot, monkeypatch):
    request = send_recorder(monkeypatch)
    event = message_event(bot, 'GROUP_MESSAGE_CREATE')
    common._register_qq_rx_message(bot.hash, 'qq_group', 'group', 'test-message')
    message = OlivOS.messageAPI.Message_templet('olivos_string', 'hello')

    result = SDK.event_action.send_qq_msg(
        event, 'member', message, reply_msg_id='test-message', flag_direct=True
    )

    assert result['active'] is True
    payload = json.loads(request.call_args.kwargs['data'])
    assert payload == {'content': 'hello', 'msg_type': 0, 'msg_id': 'test-message', 'msg_seq': 1}
    assert request.call_args.args[1].endswith('/v2/users/member/messages')


def test_group_and_private_replies_share_one_message_quota(bot, monkeypatch):
    send_recorder(monkeypatch, [(200, {'id': 'a'}), (200, {'id': 'b'}), (200, {'id': 'c'})])
    event = message_event(bot, 'GROUP_MESSAGE_CREATE')
    common._register_qq_rx_message(bot.hash, 'qq_group', 'group', 'test-message')
    message = OlivOS.messageAPI.Message_templet('olivos_string', 'hello')

    SDK.event_action.send_qq_msg(event, 'group', message, reply_msg_id='test-message')
    SDK.event_action.send_qq_msg(event, 'group', message, reply_msg_id='test-message')
    SDK.event_action.send_qq_msg(
        event, 'member', message, reply_msg_id='test-message', flag_direct=True
    )

    # 同一个 msg_id 在群内和单聊共用次数，私聊回复接着群里的序号往下排。
    assert common.sdkMsgidinfo['|'.join([str(bot.hash), 'qq_group', 'group', 'test-message'])]['seq'] == 3


def test_group_reply_limit_defaults_to_five(bot, monkeypatch):
    monkeypatch.setattr(common, '_get_qq_group_passive_limit', lambda *args, **kwargs: 5)
    event = message_event(bot, 'GROUP_MESSAGE_CREATE')

    for index in range(5):
        assert SDK.event_action._prepare_qq_passive_message(
            event, SimpleNamespace(data=SimpleNamespace()), 'qq_group', 'group', 'group-msg', None
        ) is None
        assert common.sdkMsgidinfo['|'.join([str(bot.hash), 'qq_group', 'group', 'group-msg'])]['seq'] == index + 1

    rejected = SDK.event_action._prepare_qq_passive_message(
        event, SimpleNamespace(data=SimpleNamespace()), 'qq_group', 'group', 'group-msg', None
    )
    assert rejected['data']['error'] == 'passive reply count exceeded'


def test_group_reply_limit_reaches_fifty_for_administrator(bot, monkeypatch):
    monkeypatch.setattr(common, '_get_qq_group_passive_limit', lambda *args, **kwargs: 50)
    event = message_event(bot, 'GROUP_MESSAGE_CREATE')

    for _ in range(50):
        assert SDK.event_action._prepare_qq_passive_message(
            event, SimpleNamespace(data=SimpleNamespace()), 'qq_group', 'group', 'group-msg', None
        ) is None

    rejected = SDK.event_action._prepare_qq_passive_message(
        event, SimpleNamespace(data=SimpleNamespace()), 'qq_group', 'group', 'group-msg', None
    )
    assert rejected['data']['error'] == 'passive reply count exceeded'
    assert common.sdkMsgidinfo['|'.join([str(bot.hash), 'qq_group', 'group', 'group-msg'])]['seq'] == 50


def test_private_group_reply_uses_group_limit(bot, monkeypatch):
    monkeypatch.setattr(common, '_get_qq_group_passive_limit', lambda *args, **kwargs: 50)
    event = message_event(bot, 'GROUP_MESSAGE_CREATE')
    common._register_qq_rx_message(bot.hash, 'qq_group', 'group', 'test-message')

    for _ in range(6):
        assert SDK.event_action._prepare_qq_passive_message(
            event, SimpleNamespace(data=SimpleNamespace()), 'qq_private', 'member', 'test-message', None
        ) is None

    assert common.sdkMsgidinfo['|'.join([str(bot.hash), 'qq_group', 'group', 'test-message'])]['seq'] == 6


def test_passive_reply_limit_is_cached_and_defaults_on_denied(bot, monkeypatch):
    calls = []

    def fake_request(bot_info, api_obj, req_type, op_key, wait=False):
        calls.append(api_obj.metadata.group_openid)
        return {
            'active': True,
            'response': {'member_role': 'admin'},
            'denied': False
        }

    monkeypatch.setattr(common, '_do_qq_group_api_request', fake_request)
    assert common._get_qq_group_passive_limit(bot.hash, 'group', bot) == 50
    assert common._get_qq_group_passive_limit(bot.hash, 'group', bot) == 50
    assert calls == ['group']

    monkeypatch.setattr(
        common, '_do_qq_group_api_request',
        lambda *args, **kwargs: {'active': False, 'response': None, 'denied': True}
    )
    assert common._get_qq_group_passive_limit(bot.hash, 'other-group', bot) == 5
    # 11253 之后也要落缓存，别每条消息都去撞一次接口。
    assert (str(bot.hash), 'other-group') in common.sdkGroupPassiveLimitInfo


def test_event_reply_window_is_sixty_minutes(bot, monkeypatch):
    captured = {}

    def fake_use_eventid(key, max_count, ttl):
        captured['ttl'] = ttl
        captured['max_count'] = max_count
        return 1

    monkeypatch.setattr(common, 'use_eventid', fake_use_eventid)
    event = message_event(bot, 'GROUP_ADD_ROBOT')

    assert SDK.event_action._prepare_qq_passive_message(
        event, SimpleNamespace(data=SimpleNamespace()), 'qq_group', 'group', None, 'event-1'
    ) is None
    assert captured['ttl'] == 3600.0
    assert common.sdkMsgidinfoTTL == 3600.0


def test_msgid_cache_survives_more_than_five_minutes(bot):
    # 平台有效期延长到 60 分钟，本地序号窗口如果还停在 300 秒，
    # 会把同一个 msg_id 从 seq=1 重新计数，被平台按重复消息拒掉。
    key = 'bot|qq_group|group|long-lived'
    assert common.get_msgid(key, max_seq=5) == 1
    for item in common.sdkMsgidinfo.values():
        item['created_at'] = time.monotonic() - 601.0
        item['updated_at'] = item['created_at']
    assert common.get_msgid(key, max_seq=5) == 2
