# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_card_messages.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   QQ API V2 群聊/单聊图文卡片（msg_type=8）发送测试
'''

import json
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlparse

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common


SDK = OlivOS.qqGuildv2SDK


def tuwen_card(**overrides):
    content = {
        'title': '今日天气预报',
        'description': '深圳 多云转晴 24°C~32°C',
        'url': 'https://example.invalid/weather',
        'pic_url': 'https://example.invalid/weather.png'
    }
    content.update(overrides)
    return {'type': 'tuwen', 'content': content}


@pytest.fixture
def bot(monkeypatch):
    bot = OlivOS.API.bot_info_T(
        id=10001,
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='public'
    )
    monkeypatch.setattr(common, 'sdkSelfInfo', {bot.hash: {'id': 'bot', 'username': 'bot'}})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args, **kwargs: 'bot')
    monkeypatch.setattr(
        common.req,
        'request',
        Mock(side_effect=AssertionError('Unexpected network call'))
    )
    return bot


def message_event(bot, event_type, data=None):
    body = {
        'id': 'test-message',
        'author': {
            'member_openid': 'member',
            'user_openid': 'user',
            'username': 'tester'
        },
        'group_openid': 'group',
        'content': '',
        'timestamp': '2026-09-16T12:00:00+08:00'
    }
    if data:
        body.update(data)
    payload = SDK.PAYLOAD.rxPacket({'op': 0, 's': 1, 't': event_type, 'd': body})
    event = OlivOS.API.Event(SDK.event(payload, bot))
    event.bot_info = bot
    return event


def mock_send_responses(monkeypatch, responses):
    request = Mock(side_effect=[
        SimpleNamespace(text=json.dumps(body), status_code=status)
        for status, body in responses
    ])
    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda _: None)
    monkeypatch.setattr(common, 'sdkMsgidinfo', {})
    monkeypatch.setattr(common, 'sdkSentMessageInfo', {})
    return request


def request_payload(request, index=-1):
    return json.loads(request.call_args_list[index].kwargs['data'])


@pytest.mark.parametrize('event_type, chat_type, chat_id, url_path', [
    ('GROUP_AT_MESSAGE_CREATE', 'qq_group', 'group', '/v2/groups/group/messages'),
    ('C2C_MESSAGE_CREATE', 'qq_private', 'user', '/v2/users/user/messages')
])
def test_create_card_message_sends_tuwen_payload(
    bot,
    monkeypatch,
    event_type,
    chat_type,
    chat_id,
    url_path
):
    request = mock_send_responses(monkeypatch, [(200, {'id': 'card-message'})])
    event = message_event(bot, event_type)
    card = tuwen_card()

    result = SDK.event_action.create_card_message(
        event,
        chat_type,
        chat_id,
        card,
        msg_id='test-message'
    )

    assert result['active'] is True
    assert result['data']['message_id'] == 'card-message'
    assert result['data']['content'] == '今日天气预报\\n深圳 多云转晴 24°C~32°C'
    payload = request_payload(request)
    assert payload['msg_type'] == 8
    assert payload['card'] == card
    assert payload['msg_id'] == 'test-message'
    assert payload['msg_seq'] == 1
    assert 'content' not in payload
    assert urlparse(request.call_args.args[1]).path == url_path


def test_create_card_message_defaults_type_to_tuwen(bot, monkeypatch):
    request = mock_send_responses(monkeypatch, [(200, {'id': 'card-message'})])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE')
    card = tuwen_card()
    card.pop('type')

    result = SDK.event_action.create_card_message(
        event,
        'qq_group',
        'group',
        card,
        msg_id='test-message'
    )

    assert result['active'] is True
    payload = request_payload(request)
    assert payload['card']['type'] == 'tuwen'
    assert payload['card']['content'] == card['content']


def test_create_card_message_quote_keeps_refidx(bot, monkeypatch):
    request = mock_send_responses(monkeypatch, [(200, {'id': 'card-message'})])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE')

    result = SDK.event_action.create_card_message(
        event,
        'qq_group',
        'group',
        tuwen_card(),
        msg_id='test-message',
        quote_msg_id='REFIDX_quoted=='
    )

    assert result['active'] is True
    payload = request_payload(request)
    assert payload['message_reference'] == {'message_id': 'REFIDX_quoted=='}


def test_create_card_message_keyboard_is_sent(bot, monkeypatch):
    request = mock_send_responses(monkeypatch, [(200, {'id': 'card-message'})])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE')
    keyboard = {
        'content': {
            'rows': [{
                'buttons': [{
                    'id': 'open',
                    'render_data': {'label': '打开', 'style': 1},
                    'action': {
                        'type': 0,
                        'permission': {'type': 2},
                        'data': 'https://example.invalid/weather'
                    }
                }]
            }]
        }
    }

    result = SDK.event_action.create_card_message(
        event,
        'qq_group',
        'group',
        tuwen_card(),
        msg_id='test-message',
        keyboard=keyboard
    )

    assert result['active'] is True
    assert request_payload(request)['keyboard'] == keyboard


def test_create_card_message_copies_card_before_send(bot, monkeypatch):
    request = mock_send_responses(monkeypatch, [(200, {'id': 'card-message'})])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE')
    card = tuwen_card()

    result = SDK.event_action.create_card_message(
        event,
        'qq_group',
        'group',
        card,
        msg_id='test-message'
    )

    card['content']['title'] = '已被调用方改掉'
    assert result['active'] is True
    assert request_payload(request)['card']['content']['title'] == '今日天气预报'


def test_plugin_indeapi_sends_group_card(bot, monkeypatch):
    request = mock_send_responses(monkeypatch, [(200, {'id': 'card-message'})])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE', {'content': 'hello'})
    card = tuwen_card()

    assert event.indeAPI.hasAPI('create_card_message')
    result = event.indeAPI.create_card_message(
        chat_type='qq_group',
        chat_id='group',
        card=card,
        msg_id='test-message',
        flag_log=False
    )

    assert result['active'] is True
    payload = request_payload(request)
    assert payload['msg_type'] == 8
    assert payload['card'] == card
    assert event.indeAPI.create_card_message(
        'qq_group',
        'group',
        card,
        remote=True
    ) is None
    assert request.call_count == 1


def test_expired_card_reply_retries_as_active(bot, monkeypatch):
    request = mock_send_responses(monkeypatch, [
        (400, {'code': 40034031, 'message': 'msgid已经过期,不能回复'}),
        (200, {'id': 'active-card'})
    ])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE')

    result = SDK.event_action.create_card_message(
        event,
        'qq_group',
        'group',
        tuwen_card(),
        msg_id='test-message'
    )

    assert result['active'] is True
    assert result['data']['message_id'] == 'active-card'
    passive, active = [request_payload(request, 0), request_payload(request, 1)]
    assert passive['msg_type'] == 8
    assert passive['msg_id'] == 'test-message'
    assert active['msg_type'] == 8
    assert 'msg_id' not in active
    assert active['card']['type'] == 'tuwen'


def test_force_active_card_does_not_send_passive_ids(bot, monkeypatch):
    request = mock_send_responses(monkeypatch, [(200, {'id': 'active-card'})])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE')

    result = SDK.event_action.create_card_message(
        event,
        'qq_group',
        'group',
        tuwen_card(),
        force_active=True
    )

    assert result['active'] is True
    payload = request_payload(request)
    assert payload['msg_type'] == 8
    assert 'msg_id' not in payload
    assert 'event_id' not in payload


@pytest.mark.parametrize('chat_type', ['guild_channel', 'guild_private', 'group'])
def test_create_card_message_rejects_unsupported_chat_type(bot, chat_type):
    result = SDK.event_action.create_card_message(
        SimpleNamespace(bot_info=bot, log_func=None),
        chat_type,
        'target',
        tuwen_card()
    )

    assert result['active'] is False
    assert result['data']['error'] == (
        'create_card_message only supports qq_group and qq_private'
    )
    common.req.request.assert_not_called()


def test_force_active_conflicts_with_msg_id(bot):
    result = SDK.event_action.create_card_message(
        SimpleNamespace(bot_info=bot, log_func=None),
        'qq_group',
        'group',
        tuwen_card(),
        msg_id='reply-id',
        force_active=True
    )

    assert result['data']['error'] == (
        'force_active cannot be combined with msg_id or event_id'
    )
    common.req.request.assert_not_called()


def test_msg_id_and_event_id_are_mutually_exclusive(bot):
    result = SDK.event_action.create_card_message(
        SimpleNamespace(bot_info=bot, log_func=None),
        'qq_group',
        'group',
        tuwen_card(),
        msg_id='reply-id',
        event_id='event-id'
    )

    assert result['data']['error'] == 'msg_id and event_id are mutually exclusive'
    common.req.request.assert_not_called()


def test_invalid_keyboard_is_rejected_before_network(bot):
    result = SDK.event_action.create_card_message(
        SimpleNamespace(bot_info=bot, log_func=None),
        'qq_group',
        'group',
        tuwen_card(),
        keyboard={'content': {'rows': 'bad'}}
    )

    assert result['data']['error'] == 'keyboard rows must be a list'
    common.req.request.assert_not_called()


@pytest.mark.parametrize('card, error', [
    (None, 'card must be a non-empty dict'),
    ({}, 'card must be a non-empty dict'),
    (
        {'type': 'feed', 'content': tuwen_card()['content']},
        'unsupported card type: feed'
    ),
    ({'type': 'tuwen', 'content': 'x'}, 'card content must be a dict'),
    (
        tuwen_card(title=''),
        'card content.title must be 1-50 characters'
    ),
    (
        tuwen_card(title='图' * 51),
        'card content.title must be 1-50 characters'
    ),
    (
        tuwen_card(description='描' * 201),
        'card content.description must be 1-200 characters'
    ),
    (
        tuwen_card(url='http://example.invalid/weather'),
        'card content.url must be an https URL'
    ),
    (
        tuwen_card(pic_url='https://'),
        'card content.pic_url must be an https URL'
    ),
    (
        tuwen_card(url='https://example.invalid/' + 'a' * 1024),
        'card content.url must be 1-1024 characters'
    )
])
def test_create_card_message_validates_fields_before_network(bot, card, error):
    result = SDK.event_action.create_card_message(
        SimpleNamespace(bot_info=bot, log_func=None),
        'qq_group',
        'group',
        card
    )

    assert result['active'] is False
    assert result['data']['error'] == error
    common.req.request.assert_not_called()


def test_title_50_characters_is_accepted(bot, monkeypatch):
    request = mock_send_responses(monkeypatch, [(200, {'id': 'card-message'})])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE')
    card = tuwen_card(title='图' * 50)

    result = SDK.event_action.create_card_message(
        event,
        'qq_group',
        'group',
        card,
        msg_id='test-message'
    )

    assert result['active'] is True
    assert request_payload(request)['card']['content']['title'] == '图' * 50
