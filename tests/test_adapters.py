"""Offline adapter boundaries: account mapping, events, notices and signatures."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS


@pytest.mark.parametrize('sdk', [
    'onebotSDK', 'onebotV12SDK', 'milkySDK', 'virtualTerminalSDK', 'qqGuildSDK', 'qqGuildv2SDK',
    'discordSDK', 'telegramSDK', 'fanbookSDK', 'dodoSDK', 'dodoLinkSDK', 'kaiheilaSDK',
    'xiaoheiheSDK', 'biliLiveSDK', 'OPQBotSDK', 'mhyVilaSDK', 'qqRedSDK', 'hackChatSDK', 'dingtalkSDK', 'dodobotEASDK',
])
def test_adapter_receives_correct_bot_identity(sdk, monkeypatch):
    bot = OlivOS.API.bot_info_T(id=10001, password='fixture-password', host='localhost',
                                port=1234, access_token='fixture-token')
    bot.extends = {'app_key': 'fixture-key', 'app_secret': 'fixture-secret'}
    module = getattr(OlivOS, sdk)
    if sdk == 'dingtalkSDK':
        monkeypatch.setattr(module, 'sdkSubSelfInfo', {})
    if sdk == 'dodobotEASDK':
        platform_info = SimpleNamespace(host='localhost', port=1234, access_token='fixture-token')
        mapped = module.get_SDK_bot_info_from_Plugin_bot_info(bot, platform_info)
    else:
        mapped = module.get_SDK_bot_info_from_Plugin_bot_info(bot)
    assert getattr(mapped, 'id', getattr(mapped, 'bot_id', None)) == bot.id


def onebot_event(**fields):
    payload = {'time': 1750000000, 'self_id': 10001, **fields}
    return OlivOS.API.Event(OlivOS.onebotSDK.event(json.dumps(payload)))


@pytest.mark.parametrize('kind', ['private', 'group'])
def test_onebot_message_maps_sender_and_text(kind):
    event = onebot_event(post_type='message', message_type=kind, sub_type='normal',
                         group_id=7, user_id=42, message_id=8, message='hello[CQ:at,qq=10001]',
                         raw_message='hello', font=0, sender={'user_id': 42, 'nickname': 'tester', 'role': 'member'})
    assert event.active and event.plugin_info['func_type'] == kind + '_message'
    assert event.data.user_id == '42' and event.data.message_id == '8'
    assert event.data.message_sdk.get('olivos_string') == 'hello[OP:at,id=10001]'


@pytest.mark.parametrize('notice,expected,extra', [
    ('group_increase', 'group_member_increase', {'sub_type': 'approve'}),
    ('group_decrease', 'group_member_decrease', {'sub_type': 'kick'}),
    ('group_ban', 'group_ban', {'sub_type': 'ban', 'duration': 60}),
    ('group_recall', 'group_message_recall', {'message_id': 8}),
    ('friend_recall', 'private_message_recall', {'message_id': 8}),
    ('friend_add', 'friend_add', {}),
])
def test_onebot_notice_maps_event_type(notice, expected, extra):
    event = onebot_event(post_type='notice', notice_type=notice, group_id=7, user_id=42, operator_id=5, **extra)
    assert event.active and event.plugin_info['func_type'] == expected
    assert event.data.user_id == '42'


def test_onebot_duplicate_request_is_not_dispatched_twice(monkeypatch):
    monkeypatch.setattr(OlivOS.onebotSDK, 'gFlagCheckList', [])
    fields = dict(post_type='request', request_type='friend', flag='fixture-request', user_id=42, comment='hello')
    assert onebot_event(**fields).active
    assert not onebot_event(**fields).active


def test_malformed_onebot_json_is_inactive():
    assert not OlivOS.onebotSDK.event('{not json').active


@pytest.mark.parametrize('group', [False, True])
def test_virtual_terminal_maps_user_configuration(group):
    bot = OlivOS.API.bot_info_T(id=10001)
    packet = OlivOS.API.Control.packet('send', {'data': {'data': 'test', 'user_conf': {
        'user_id': '42', 'target_id': '7', 'user_name': 'tester', 'flag_group': group, 'group_role': 'admin'}}})
    event = OlivOS.API.Event(OlivOS.virtualTerminalSDK.event(packet, bot))
    assert event.active and event.data.user_id == '42'
    assert event.plugin_info['func_type'] == ('group_message' if group else 'private_message')
    assert event.data.sender['nickname'] == 'tester'


def test_account_activity_rejects_unknown_accounts(monkeypatch):
    bot = OlivOS.API.bot_info_T(id=1)
    activity = OlivOS.API.accountActivity(bot)
    monkeypatch.setattr(OlivOS.API.time, 'monotonic', Mock(return_value=123))
    assert not activity.mark('unknown')
    assert activity.mark(bot.hash)
    assert activity.snapshot() == {bot.hash: 123}


def test_qq_webhook_signature_accepts_untampered_body():
    sdk = OlivOS.qqGuildv2SDK
    signature = sdk.sign_qqGuildv2_webhook_validation('fixture-secret', '1750000000', '{"op":0}')
    assert sdk.verify_qqGuildv2_webhook_signature('fixture-secret', '1750000000', b'{"op":0}', signature)


@pytest.mark.parametrize('body,timestamp', [(b'{"op":1}', '1750000000'), (b'{"op":0}', '1750000001')])
def test_qq_webhook_signature_rejects_tampering(body, timestamp):
    sdk = OlivOS.qqGuildv2SDK
    signature = sdk.sign_qqGuildv2_webhook_validation('fixture-secret', '1750000000', '{"op":0}')
    assert not sdk.verify_qqGuildv2_webhook_signature('fixture-secret', timestamp, body, signature)


@pytest.mark.parametrize('signature', [None, '', 'invalid-hex', '00' * 64])
def test_qq_webhook_rejects_malformed_signature(signature):
    assert not OlivOS.qqGuildv2SDK.verify_qqGuildv2_webhook_signature('fixture-secret', '1', b'{}', signature)


def test_qq_webhook_validation_extracts_challenge():
    assert OlivOS.qqGuildv2SDK.get_qqGuildv2_webhook_validation(
        {'op': 13, 'd': {'plain_token': 'challenge', 'event_ts': '1'}}) == ('challenge', '1')
    assert OlivOS.qqGuildv2SDK.get_qqGuildv2_webhook_validation({'op': 0}) == (None, None)
