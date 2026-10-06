"""Shared offline event contracts for every SDK dispatched by OlivOS.API.Event.

Payload fixtures follow each adapter's wire fields. Only remote metadata is seeded;
event constructors, message parsing and public Event dispatch remain real.
"""

import ast
import inspect
import json
import textwrap
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
import requests

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as qq_common


SDK_PLATFORMS = {
    'onebotSDK': ('onebot', 'qq', 'default'),
    'onebotV12SDK': ('onebot', 'qq', 'onebotV12'),
    'milkySDK': ('onebot', 'qq', 'milky_default'),
    'virtualTerminalSDK': ('terminal_link', 'terminal', 'default'),
    'qqGuildSDK': ('qqGuild_link', 'qqGuild', 'default'),
    'qqGuildv2SDK': ('qqGuildv2_link', 'qqGuild', 'public'),
    'discordSDK': ('discord_link', 'discord', 'default'),
    'telegramSDK': ('telegram_poll', 'telegram', 'default'),
    'fanbookSDK': ('fanbook_poll', 'fanbook', 'default'),
    'dodoSDK': ('dodo_poll', 'dodo', 'default'),
    'dodoLinkSDK': ('dodo_link', 'dodo', 'v2'),
    'dodobotEASDK': ('dodobot_ea', 'dodo', 'default'),
    'kaiheilaSDK': ('kaiheila_link', 'kaiheila', 'default'),
    'xiaoheiheSDK': ('xiaoheihe_link', 'xiaoheihe', 'default'),
    'biliLiveSDK': ('biliLive_link', 'biliLive', 'default'),
    'OPQBotSDK': ('onebot', 'qq', 'opqbot_default'),
    'mhyVilaSDK': ('mhyVila_link', 'mhyVila', 'default'),
    'qqRedSDK': ('onebot', 'qq', 'red'),
    'hackChatSDK': ('hackChat_link', 'hackChat', 'default'),
    'dingtalkSDK': ('dingtalk_link', 'dingtalk', 'default'),
}


def test_event_contract_matrix_covers_every_dispatched_sdk():
    """New SDK dispatch branches must explicitly add a functional fixture."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(OlivOS.API.Event.get_Event_from_SDK)))
    routed = {node.value.attr for node in ast.walk(tree)
              if isinstance(node, ast.Attribute) and node.attr == 'get_Event_from_SDK'
              and isinstance(node.value, ast.Attribute)}
    assert set(SDK_PLATFORMS) == routed


@pytest.fixture(params=SDK_PLATFORMS)
def sdk_case(request, monkeypatch):
    name = request.param
    sdk, platform, model = SDK_PLATFORMS[name]
    bot = OlivOS.API.bot_info_T(id=10001, platform_sdk=sdk, platform_platform=platform, platform_model=model,
                                host='fixture-room', access_token='fixture-token')
    bot.extends = {'app_key': 'fixture-key', 'app_secret': 'fixture-secret'}
    module = getattr(OlivOS, name)
    # Fail on any unexpected outbound request, even when an adapter catches the exception.
    network = Mock(side_effect=AssertionError('Event conversion must remain offline'))
    monkeypatch.setattr(requests.sessions.Session, 'request', network)
    if hasattr(module, 'sdkSubSelfInfo'):
        monkeypatch.setattr(module, 'sdkSubSelfInfo', {bot.hash: '10001'})
    if name == 'dingtalkSDK':
        monkeypatch.setattr(module, 'sdkSubSelfInfo', {})
    if name == 'dodoLinkSDK':
        monkeypatch.setattr(module, 'sdkUserInfo', {'9': {'42': {'nickName': 'tester', 'sex': 1}}})
    if name == 'kaiheilaSDK':
        monkeypatch.setattr(module, 'get_guild_admin_role_id', lambda *args: [])
    if name == 'xiaoheiheSDK':
        monkeypatch.setattr(module, 'get_room_admin_role_id', lambda *args: [])
    if name == 'hackChatSDK':
        monkeypatch.setattr(module, 'gBotIdDict', {})
    if name == 'mhyVilaSDK':
        monkeypatch.setattr(module, 'sdkNameDict', {})
    if name == 'qqGuildv2SDK':
        monkeypatch.setattr(qq_common, 'sdkSelfInfo', {bot.hash: {'id': '10001', 'username': 'bot'}})
        for field in ('qqEventDedupeCache', 'sdkUserInfo', 'sdkSubSelfInfo', 'sdkRxMessageInfo',
                      'sdkMsgIdxInfo', 'sdkGroupMemberCacheInfo'):
            monkeypatch.setattr(qq_common, field, {})
        monkeypatch.setattr(qq_common, '_get_qq_group_self_open_id', lambda *args: '10001')

    def make(text='hello', unsupported=False):
        user = {'id': '42', 'username': 'tester', 'first_name': 'tester', 'is_master': False, 'roles': []}
        if name == 'onebotSDK':
            return module.event(json.dumps({
                'time': 1750000000, 'self_id': 10001, 'post_type': 'unknown' if unsupported else 'message',
                'message_type': 'group', 'sub_type': 'normal', 'group_id': 7, 'user_id': 42,
                'message_id': 8, 'message': text, 'raw_message': text, 'font': 0,
                'sender': {'user_id': 42, 'nickname': 'tester', 'role': 'member'}}))
        if name == 'onebotV12SDK':
            return module.event({
                'type': 'unknown' if unsupported else 'message', 'detail_type': 'group',
                'group_id': '7', 'user_id': '42', 'user_name': 'tester', 'message_id': '8',
                'message': [{'type': 'text', 'data': {'text': text}}]},
                module.get_SDK_bot_info_from_Plugin_bot_info(bot))
        if name == 'milkySDK':
            return module.event({
                'time': 1750000000, 'self_id': 10001, 'event_type': 'unknown' if unsupported else 'message_receive',
                'data': {'message_scene': 'group', 'peer_id': 7, 'sender_id': 42, 'message_seq': 8,
                         'segments': [{'type': 'text', 'data': {'text': text}}],
                         'group_member': {'user_id': 42, 'nickname': 'tester'}}})
        if name == 'virtualTerminalSDK':
            if unsupported:
                return module.event({'type': 'unsupported'}, bot, model='postapi')
            packet = OlivOS.API.Control.packet('send', {'data': {'data': text, 'user_conf': {
                'user_id': '42', 'target_id': '7', 'user_name': 'tester', 'flag_group': True}}})
            return module.event(packet, bot)
        if name in ('qqGuildSDK', 'discordSDK'):
            payload = module.PAYLOAD.rxPacket({'op': 0, 's': 1, 't': 'UNKNOWN' if unsupported else 'MESSAGE_CREATE',
                                               'd': {'id': '8', 'channel_id': '7', 'guild_id': '9',
                                                     'content': text, 'author': user}})
            return module.event(payload, bot)
        if name == 'qqGuildv2SDK':
            payload = module.PAYLOAD.rxPacket({
                'op': 0, 's': 1, 't': 'UNKNOWN' if unsupported else 'GROUP_AT_MESSAGE_CREATE',
                'd': {'id': '8', 'group_openid': '7', 'author': {'member_openid': '42', 'username': 'tester'},
                      'content': text, 'timestamp': '2026-09-22T12:00:00+08:00'}})
            return module.event(payload, bot)
        if name == 'telegramSDK':
            body = {} if unsupported else {'message': {'date': 1750000000, 'message_id': 8, 'text': text,
                                                       'chat': {'id': 7, 'type': 'group'}, 'from': user}}
            return module.event(body, bot_info=bot)
        if name == 'fanbookSDK':
            body = {} if unsupported else {'channel_post': {'message_id': 8, 'text': text, 'from': user,
                                                            'chat': {'id': 7, 'type': 'channel', 'guild_id': 9}}}
            return module.event(body, bot)
        if name == 'dodoSDK':
            body = {} if unsupported else {'channelId': '7', 'uid': '42', 'id': '8', 'content': text,
                                           'resourceJson': '', 'nickName': 'tester'}
            return module.event(body, bot, islandId='9')
        if name == 'dodoLinkSDK':
            payload = module.PAYLOAD.rxPacket({'type': 0, 'data': {
                'eventType': 'unknown' if unsupported else '2001', 'eventBody': {
                    'messageType': 1, 'messageBody': {'content': text}, 'islandSourceId': '9',
                    'dodoSourceId': '42', 'channelId': '7', 'messageId': '8'}}})
            return module.event(payload, bot)
        if name == 'dodobotEASDK':
            # EA only accepts message records; malformed content must not reach plugins.
            return module.event({'FromChannel': '7', 'Uid': '42', 'Id': '8', 'NickName': 'tester',
                                 'Content': None if unsupported else text, 'OriginalContent': text}, bot)
        if name == 'kaiheilaSDK':
            payload = module.PAYLOAD.rxPacket({'s': 0, 'd': {
                'channel_type': 'UNKNOWN' if unsupported else 'GROUP', 'type': 1, 'content': text,
                'target_id': '7', 'author_id': '42', 'msg_id': '8', 'extra': {'author': user, 'guild_id': '9'}}})
            return module.event(payload, bot)
        if name == 'xiaoheiheSDK':
            payload = module.PAYLOAD.rxPacket({'type': 'unknown' if unsupported else '5', 'data': {
                'room_id': '9', 'channel_id': '7', 'msg_id': '8', 'user_id': '42',
                'nickname': 'tester', 'msg': text, 'is_master': False, 'roles': []}})
            return module.event(payload, bot)
        if name == 'biliLiveSDK':
            from OlivOS.thirdPartyModule.blivedm.models import DanmakuMessage, HeartbeatMessage
            payload = HeartbeatMessage(1) if unsupported else DanmakuMessage(msg=text, uid=42, uname='tester')
            return module.event(payload, bot)
        if name == 'OPQBotSDK':
            payload = module.PAYLOAD.rxPacket({'CurrentQQ': 10001, 'CurrentPacket': {
                'EventName': 'UNKNOWN' if unsupported else 'ON_EVENT_GROUP_NEW_MSG',
                'EventData': {'MsgHead': {'FromUin': 7, 'ToUin': 10001, 'SenderUin': 42, 'SenderNick': 'tester'},
                              'MsgBody': {'Content': text}}}})
            return module.event(payload, bot)
        if name == 'mhyVilaSDK':
            body = {'type': 'Unknown' if unsupported else 'SendMessage', 'extendData': {'sendMessage': {
                'objectName': 'Text', 'villaId': '9', 'roomId': '7', 'msgUid': '8', 'nickname': 'tester',
                'fromUserId': '42', 'content': json.dumps({'content': {'text': text, 'entities': []}})}}}
            return module.event(module.protoEnum.Model_ROBOTEVENT.value, body, bot)
        if name == 'qqRedSDK':
            payload = module.PAYLOAD.rxPacket({'type': 'unknown' if unsupported else 'message::recv', 'payload': [{
                'chatType': 2, 'peerUid': '7', 'senderUin': '42', 'sendNickName': 'tester', 'sendMemberName': '',
                'elements': [{'textElement': {'content': text}}]}]})
            return module.event(payload, bot)
        if name == 'hackChatSDK':
            payload = module.PAYLOAD.rxPacket({'cmd': 'unknown' if unsupported else 'chat',
                                               'nick': 'tester', 'userid': '42', 'text': text})
            return module.event(payload, bot)
        if name == 'dingtalkSDK':
            payload = module.PAYLOAD.rxPacket({'type': 'UNKNOWN' if unsupported else 'CALLBACK',
                                               'headers': {'messageId': '8', 'topic': '/v1.0/im/bot/messages/get'},
                                               'data': json.dumps({
                                                   'chatbotUserId': 'bot', 'msgtype': 'text',
                                                   'text': {'content': text}, 'conversationType': '2',
                                                   'conversationId': '7', 'senderStaffId': '42',
                                                   'senderNick': 'tester'})})
            return module.event(payload, bot)
        raise AssertionError('Missing SDK fixture: ' + name)

    yield NS(name=name, make=make, bot=bot)
    network.assert_not_called()


def test_sdk_group_event_maps_sender_and_conversation(sdk_case):
    event = OlivOS.API.Event(sdk_case.make())
    assert event.active and event.plugin_info['func_type'] == 'group_message'
    assert str(event.data.user_id) == '42'
    assert str(event.base_info['self_id']) == '10001'
    expected_group = {'biliLiveSDK': '10001', 'hackChatSDK': '0'}.get(sdk_case.name, '7')
    assert str(event.data.group_id) == expected_group


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


@pytest.mark.parametrize('payload', [None, [], {}, {'Content': 'incomplete'}, {
    'FromChannel': '7', 'Uid': '42', 'Content': 'hello', 'OriginalContent': None, 'Id': '8', 'NickName': 'tester',
}])
def test_dodo_ea_incomplete_record_is_rejected_without_exception(payload):
    bot = OlivOS.API.bot_info_T(id=10001)
    assert not OlivOS.API.Event(OlivOS.dodobotEASDK.event(payload, bot)).active
