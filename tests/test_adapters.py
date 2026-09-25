"""Offline adapter boundaries: account mapping, events, notices and signatures."""

import json
import re
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


def onebot_event(model='default', **fields):
    payload = {'time': 1750000000, 'self_id': 10001, **fields}
    sdk_event = OlivOS.onebotSDK.event(json.dumps(payload))
    sdk_event.platform['model'] = model
    return OlivOS.API.Event(sdk_event)


@pytest.mark.parametrize('kind', ['private', 'group'])
@pytest.mark.parametrize('face_id', ['14', '311', '333'])
def test_napcat_face_matches_old_string_plugin_keyword(kind, face_id):
    segment = {'type': 'face', 'data': {
        'id': face_id, 'raw': {'faceIndex': int(face_id), 'faceText': '[表情]'},
        'resultId': None, 'chainCount': None,
    }}
    event = onebot_event(model='napcat', post_type='message', message_type=kind, sub_type='normal',
                         group_id=7, user_id=42, message_id=8, message=[segment],
                         raw_message='', font=0, sender={'user_id': 42, 'nickname': 'tester'})
    assert event.data.message_sdk.get('olivos_string') == f'[OP:face,id={face_id}]'
    event.plugin_info.update(compatible_svn=190, message_mode_tx='old_string')
    event.get_Event_on_Plugin()
    keyword = f'[CQ:face,id={face_id}]'
    assert event.data.message == keyword
    assert re.match('^' + re.escape(keyword) + '$', event.data.message)
    assert event.sdk_event.json['message'] == [segment]
    assert event.data.extend['napcat_face_data'] == [segment['data']]
    event.data.extend['napcat_face_data'][0]['raw']['faceText'] = 'changed'
    assert event.sdk_event.json['message'][0]['data']['raw']['faceText'] == '[表情]'


@pytest.mark.parametrize('qq', ['42', 'all'])
@pytest.mark.parametrize('compatible', [189, 190, 210])
def test_napcat_at_keeps_metadata_out_of_match_string(qq, compatible):
    segment = {'type': 'at', 'data': {
        'qq': qq, 'name': '[昵称],带逗号', 'raw': {'display': '[昵称]'}, 'extra': 'value',
    }}
    event = onebot_event(model='napcat_default', post_type='message', message_type='group',
                         sub_type='normal', group_id=7, user_id=42, message_id=8,
                         message=[segment], raw_message='', font=0,
                         sender={'user_id': 42, 'nickname': 'tester'})
    event.plugin_info.update(compatible_svn=compatible, message_mode_tx='old_string')
    event.get_Event_on_Plugin()
    suffix = ',name=[昵称],带逗号' if compatible >= 190 else ''
    assert event.data.message == f'[CQ:at,qq={qq}{suffix}]'
    assert event.data.extend['napcat_at_data'] == [segment['data']]
    assert event.sdk_event.json['message'] == [segment]


@pytest.mark.parametrize('kind', ['private', 'group'])
@pytest.mark.parametrize('post_type', ['message', 'message_sent'])
@pytest.mark.parametrize('model', OlivOS.onebotSDK.napcatModelMap)
def test_napcat_string_face_matches_plugin_keyword(kind, post_type, model):
    message = '[CQ:face,id=311,raw={"faceText":"&#91;打call&#93;"},chainCount=0]'
    event = onebot_event(model=model, post_type=post_type, message_type=kind, sub_type='normal',
                         group_id=7, user_id=42, message_id=8, message=message,
                         raw_message=message, font=0, sender={'user_id': 42, 'nickname': 'tester'})
    event.plugin_info.update(compatible_svn=190, message_mode_tx='old_string')
    event.get_Event_on_Plugin()
    assert event.data.message == '[CQ:face,id=311]'
    assert event.data.raw_message == '[CQ:face,id=311]'
    assert event.data.extend['napcat_face_data'][0]['raw'] == '{"faceText":"[打call]"}'
    assert event.data.extend['napcat_raw_message'] == message
    assert event.sdk_event.json['message'] == message


def test_napcat_string_decodes_only_after_splitting():
    message = ('&#91;CQ:face,id=311&#93;&amp;#91;'
               '[CQ:image,summary=&#91;动画&#93;,file=test.png,url=https://example.invalid/a?x=1&amp;y=2]'
               '[CQ:at,qq=42,name=A&#44;B&#91;C&#93;][CQ:dice]')
    event = onebot_event(model='napcat_default', post_type='message', message_type='group', sub_type='normal',
                         group_id=7, user_id=42, message_id=8, message=message,
                         raw_message=message, font=0, sender={'user_id': 42, 'nickname': 'tester'})
    parsed = event.data.message_sdk
    assert [item.type for item in parsed.data] == ['text', 'image', 'at', 'dice']
    assert parsed.data[0].data['text'] == '[CQ:face,id=311]&#91;'
    assert parsed.data[1].data['url'] == 'https://example.invalid/a?x=1&y=2'
    assert parsed.data[2].data['name'] == 'A,B[C]'


def test_non_napcat_keeps_original_face_and_image_fields():
    segments = [
        {'type': 'face', 'data': {'id': '311', 'raw': {'faceText': '[表情]'}}},
        {'type': 'image', 'data': {'summary': '[动画表情]', 'file': 'x.png', 'sub_type': 1}},
    ]
    payload = {'time': 1750000000, 'self_id': 10001, 'post_type': 'message',
               'message_type': 'private', 'sub_type': 'friend', 'user_id': 42,
               'message_id': 8, 'message': segments, 'raw_message': '', 'font': 0,
               'sender': {'user_id': 42, 'nickname': 'tester'}}
    sdk_event = OlivOS.onebotSDK.event(json.dumps(payload))
    sdk_event.platform['model'] = 'gocqhttp'
    assert OlivOS.onebotSDK.format_cq_code_msg(segments) == (
        '[CQ:face,id=311,raw={\'faceText\': \'[表情]\'}]'
        '[CQ:image,summary=[动画表情],file=x.png,sub_type=1]'
    )


@pytest.mark.parametrize('kind,data,expected', [
    ('reply', {'id': '7'}, '[CQ:reply,id=7]'),
    ('record', {'file': 'a.amr', 'url': 'https://example.invalid/a.amr'},
     '[CQ:record,file=a.amr,url=https://example.invalid/a.amr]'),
    ('video', {'file': 'a.mp4'}, '[CQ:video,file=a.mp4]'),
    ('file', {'file': 'a.txt', 'name': 'a.txt', 'size': 123}, '[CQ:file,file=a.txt,name=a.txt,size=123]'),
    ('forward', {'id': '7'}, '[CQ:forward,id=7]'),
    ('dice', {'result': 6}, '[CQ:dice]'),
    ('rps', {'result': 2}, '[CQ:rps]'),
])
@pytest.mark.parametrize('post_type', ['message', 'message_sent'])
@pytest.mark.parametrize('wire_format', ['array', 'string'])
def test_napcat_message_metadata_is_separate(kind, data, expected, post_type, wire_format):
    segment = {'type': kind, 'data': {**data, 'raw': {'label': '[扩展],内容'}}}
    message = [segment]
    if wire_format == 'string':
        segment['data'] = {key: json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else str(value)
                           for key, value in segment['data'].items()}
        fields = [key + '=' + value.replace('&', '&amp;').replace('[', '&#91;')
                  .replace(']', '&#93;').replace(',', '&#44;') for key, value in segment['data'].items()]
        message = '[CQ:' + kind + ',' + ','.join(fields) + ']'
    event = onebot_event(model='napcat_default', post_type=post_type,
                         message_type='private', sub_type='friend', user_id=42,
                         message_id=8, message=message, raw_message='', font=0,
                         sender={'user_id': 42, 'nickname': 'tester'})
    event.plugin_info.update(compatible_svn=190, message_mode_tx='old_string')
    event.get_Event_on_Plugin()
    assert event.data.message == expected
    assert event.data.extend[f'napcat_{kind}_data'] == [segment['data']]
    assert event.data.extend['napcat_raw_message'] == message


@pytest.mark.parametrize('summary', ['[动画表情]', '[躺赢]', '', '[CQ:face,id=311]'])
def test_napcat_image_survives_plugin_delivery_and_reply(summary):
    url = 'https://example.invalid/test.png?appid=1406&fileid=fixture&rkey=fixture'
    segment = {'type': 'image', 'data': {
        'summary': summary, 'file': 'test.png', 'sub_type': 1, 'url': url, 'file_size': '6030',
    }}
    event = onebot_event(model='napcat', post_type='message', message_type='private', sub_type='friend',
                         user_id=42, message_id=8, message=[segment], raw_message='', font=0,
                         sender={'user_id': 42, 'nickname': 'tester'})
    assert len(event.data.message_sdk.data) == 1
    assert event.data.message_sdk.data[0].data['file'] == 'test.png'
    assert event.data.message_sdk.data[0].data['url'] == url
    event.plugin_info.update(compatible_svn=190, message_mode_tx='old_string')
    event.get_Event_on_Plugin()
    assert event.data.message == f'[CQ:image,file={url}]'
    reply = OlivOS.messageAPI.Message_templet('old_string', event.data.message)
    assert len(reply.data) == 1
    assert reply.get('old_string') == f'[CQ:image,file={url}]'
    assert event.sdk_event.json['message'] == [segment]
    assert event.data.extend['napcat_image_data'] == [segment['data']]


@pytest.mark.parametrize('kind', ['private', 'group'])
def test_onebot_message_maps_sender_and_text(kind):
    event = onebot_event(post_type='message', message_type=kind, sub_type='normal',
                         group_id=7, user_id=42, message_id=8, message='hello[CQ:at,qq=10001]',
                         raw_message='hello', font=0, sender={'user_id': 42, 'nickname': 'tester', 'role': 'member'})
    assert event.active and event.plugin_info['func_type'] == kind + '_message'
    assert event.data.user_id == '42' and event.data.message_id == '8'
    assert event.data.message_sdk.get('olivos_string') == 'hello[OP:at,id=10001]'


def test_receive_log_preserves_at_name_while_plugin_compatibility_controls_delivery():
    log = Mock()
    payload = {
        'time': 1750000000, 'self_id': 10001, 'post_type': 'message',
        'message_type': 'private', 'sub_type': 'normal', 'user_id': 42,
        'message_id': 8, 'message': [
            {'type': 'at', 'data': {'qq': '10001', 'name': 'tester-name'}}
        ],
        'raw_message': '', 'font': 0,
        'sender': {'user_id': 42, 'nickname': 'tester', 'role': 'member'}
    }
    event = OlivOS.API.Event(OlivOS.onebotSDK.event(json.dumps(payload)), log_func=log)

    assert any('[OP:at,id=10001,name=tester-name]' in call.args[1] for call in log.call_args_list)
    assert event.data.message == '[OP:at,id=10001]'

    event.plugin_info.update(compatible_svn=189, message_mode_tx='old_string')
    event.get_Event_on_Plugin()
    assert event.data.message == '[CQ:at,qq=10001]'
    event.plugin_info['compatible_svn'] = 190
    event.get_Event_on_Plugin()
    assert event.data.message == '[CQ:at,qq=10001,name=tester-name]'
    event.plugin_info.update(compatible_svn=189, message_mode_tx='olivos_string')
    event.get_Event_on_Plugin()
    assert event.data.message == '[OP:at,id=10001]'
    event.plugin_info['compatible_svn'] = 190
    event.get_Event_on_Plugin()
    assert event.data.message == '[OP:at,id=10001,name=tester-name]'


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
