# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_messages.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   QQ API V2 图片卡片与合并转发功能测试
'''

import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common

SDK = OlivOS.qqGuildv2SDK
PICTURE_URL = 'https://example.invalid/photo.png'
EVENT_TYPES = ['GROUP_AT_MESSAGE_CREATE', 'GROUP_MESSAGE_CREATE', 'C2C_MESSAGE_CREATE']
FACE_TAG = '<faceType=1,faceId=311>'
MFACE_TAG = '<faceType=4,faceId=,ext=eyJ0ZXh0IjoiW10ifQ==>'


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
        'sdkGroupMemberCacheInfo'
    ]:
        monkeypatch.setattr(common, name, {})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args: 'bot')
    monkeypatch.setattr(common.req, 'request', Mock(side_effect=AssertionError('Unexpected network call')))
    return bot


def message_event(bot, event_type, data):
    body = {
        'id': 'test-message',
        'author': {'member_openid': 'member', 'user_openid': 'user', 'username': 'tester'},
        'group_openid': 'group',
        'content': '',
        'timestamp': '2026-09-16T12:00:00+08:00',
        **data
    }
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


@pytest.mark.parametrize('event_type', ['GROUP_AT_MESSAGE_CREATE', 'C2C_MESSAGE_CREATE'])
@pytest.mark.parametrize('error_fields', [
    {'code': 40034031, 'err_code': 40034031},
    {'code': 40034031},
    {'err_code': '40034031'}
])
def test_expired_qq_reply_retries_as_active(bot, monkeypatch, event_type, error_fields):
    expired = {'message': 'msgid已经过期,不能回复', **error_fields}
    request = mock_send_responses(monkeypatch, [
        (400, expired), (200, {'id': 'active-message'}), (200, {'id': 'next-message'})
    ])
    event = message_event(bot, event_type, {})

    result = event.reply('hello', flag_log=False)

    assert result['active'] is True
    assert result['data']['message_ids'] == ['active-message']
    fallback = result['data']['passive_fallbacks'][0]
    assert fallback['reply_type'] == 'msg_id'
    assert fallback['passive_result']['data']['response'] == expired
    passive, active = [json.loads(call.kwargs['data']) for call in request.call_args_list]
    assert passive == {'content': 'hello', 'msg_type': 0, 'msg_id': 'test-message', 'msg_seq': 1}
    assert active == {'content': 'hello', 'msg_type': 0}
    assert request.call_args_list[0].args == request.call_args_list[1].args

    assert event.reply('next', flag_log=False)['active'] is True
    assert json.loads(request.call_args.kwargs['data']) == {'content': 'next', 'msg_type': 0}
    assert request.call_count == 3


def test_expired_qq_reply_preserves_active_failure_without_loop(bot, monkeypatch):
    expired = {'code': 40034031, 'message': 'msgid已经过期,不能回复'}
    request = mock_send_responses(monkeypatch, [(400, expired), (400, expired)])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE', {})

    result = event.reply('hello', flag_log=False)

    assert result['active'] is False
    assert result['data']['message_ids'] == []
    assert result['data']['error'] == expired['message']
    assert result['data']['results'][0]['data']['error_code'] == 40034031
    assert len(result['data']['passive_fallbacks']) == 1
    assert json.loads(request.call_args.kwargs['data']) == {'content': 'hello', 'msg_type': 0}
    assert request.call_count == 2


@pytest.mark.parametrize('reply_type, error_code', [
    ('msg_id', 304103),
    ('msg_id', 40034005),
    ('msg_id', 40034024),
    ('msg_id', 40034128),
    ('event_id', 40034025),
    ('event_id', 40034026),
    ('event_id', 40034027),
    ('event_id', 40034128)
])
def test_documented_qq_passive_rejection_retries_as_active(bot, monkeypatch, reply_type, error_code):
    request = mock_send_responses(monkeypatch, [
        (400, {'code': error_code, 'message': 'passive reply rejected'}),
        (200, {'id': 'active-message'})
    ])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE', {})
    message = OlivOS.messageAPI.Message_templet('olivos_string', 'hello')
    reply_ids = {'reply_msg_id': 'test-message'} if reply_type == 'msg_id' else {'event_id': 'test-event'}

    result = SDK.event_action.send_qq_msg(event, 'group', message, **reply_ids)

    assert result['active'] is True
    assert result['data']['passive_fallbacks'][0]['reply_type'] == reply_type
    passive, active = [json.loads(call.kwargs['data']) for call in request.call_args_list]
    assert passive[reply_type] == ('test-message' if reply_type == 'msg_id' else 'test-event')
    assert ('msg_seq' in passive) is (reply_type == 'msg_id')
    assert active == {'content': 'hello', 'msg_type': 0}
    assert request.call_count == 2


@pytest.mark.parametrize('status, body', [
    (200, {'id': 'reply-message'}),
    (400, {'code': 12345, 'message': 'other error'}),
    (400, {'code': 40054005, 'message': 'duplicate message'}),
    (400, {'code': 40034100, 'message': 'active message rate limited'}),
    (400, {'code': 40034105, 'message': 'active message permission denied'}),
    (400, {'code': 40054002, 'message': 'bot muted'}),
    (400, {'code': 40034006, 'message': 'content rejected'}),
    (429, {'code': 40034031, 'message': 'rate limited'}),
    (503, {'code': 40034031, 'message': 'unavailable'})
])
def test_qq_reply_does_not_retry_success_or_unrelated_failure(bot, monkeypatch, status, body):
    request = mock_send_responses(monkeypatch, [(status, body)])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE', {})

    result = event.reply('hello', flag_log=False)

    assert result['active'] is (status == 200)
    assert result['data']['passive_fallbacks'] == []
    assert request.call_count == 1


def test_expired_qq_reply_remaining_media_uses_active_send(bot, monkeypatch):
    request = mock_send_responses(monkeypatch, [
        (400, {'code': 40034031, 'message': 'msgid已经过期,不能回复'}),
        (200, {'id': 'text-message'}),
        (200, {'file_info': 'uploaded-audio'}),
        (200, {'id': 'audio-message'})
    ])
    event = message_event(bot, 'GROUP_AT_MESSAGE_CREATE', {})
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('hello'),
        OlivOS.messageAPI.PARA.record('https://example.invalid/audio.amr')
    ])

    result = event.reply(message, flag_log=False)

    assert result['active'] is True
    assert result['data']['message_ids'] == ['text-message', 'audio-message']
    assert len(result['data']['passive_fallbacks']) == 1
    assert json.loads(request.call_args.kwargs['data']) == {
        'msg_type': 7, 'media': {'file_info': 'uploaded-audio'}
    }
    assert request.call_count == 4


def picture_data(**overrides):
    return {
        'message_type': 3,
        'ark_data': {
            'ark_type': 'picture', 'ark_name': '图片',
            'fields': {'preview': PICTURE_URL, 'title': 'Test picture'}
        },
        **overrides
    }


@pytest.mark.parametrize('event_type', EVENT_TYPES)
@pytest.mark.parametrize('tag', [FACE_TAG, '<faceType=1,faceId=311,type=sticker>'])
def test_qq_face_id_becomes_cq_face(bot, event_type, tag):
    event = message_event(bot, event_type, {'content': 'hello ' + tag})

    assert event.active
    assert event.data.message_sdk.get('old_string') == 'hello [CQ:face,id=311]'
    assert event.data.message_sdk.get('olivos_string') == 'hello [OP:face,id=311]'
    assert event.data.extend['qq_face_data'][0]['face_id'] == '311'


@pytest.mark.parametrize('tag', [MFACE_TAG, '<faceType=4,faceId="">', '<faceType=4,ext=abc>'])
def test_qq_face_without_id_remains_mface(bot, tag):
    event = message_event(bot, 'C2C_MESSAGE_CREATE', {'content': tag})

    assert event.active
    assert [segment.type for segment in event.data.message_sdk.data] == ['mface']
    assert event.data.message_sdk.get('old_string').startswith('[CQ:mface,')


@pytest.mark.parametrize('event_type', EVENT_TYPES)
@pytest.mark.parametrize('face_id', ['0', '311'])
def test_qq_face_tag_for_image_does_not_add_face(bot, event_type, face_id):
    event = message_event(bot, event_type, {
        'content': '<faceType=1,faceId=%s>' % face_id,
        'attachments': [{'content_type': 'image/png', 'url': PICTURE_URL}]
    })

    assert [segment.type for segment in event.data.message_sdk.data] == ['image']
    assert '[OP:face,' not in event.data.message_sdk.get('olivos_string')
    assert '[CQ:face,' not in event.data.message_sdk.get('old_string')
    assert event.data.extend['qq_face_data'][0]['face_id'] == face_id


def test_qq_face_after_image_tag_is_not_discarded(bot):
    event = message_event(bot, 'C2C_MESSAGE_CREATE', {
        'content': '<faceType=1,faceId=0>' + FACE_TAG,
        'attachments': [{'content_type': 'image/png', 'url': PICTURE_URL}]
    })

    assert [segment.type for segment in event.data.message_sdk.data] == ['image', 'face']
    assert event.data.message_sdk.get('old_string').endswith('[CQ:face,id=311]')


def test_qq_multiple_image_tags_only_consume_matching_face_tags(bot):
    event = message_event(bot, 'C2C_MESSAGE_CREATE', {
        'content': '<faceType=1,faceId=0>' * 2 + FACE_TAG,
        'attachments': [
            {'content_type': 'image/png', 'url': PICTURE_URL},
            {'content_type': 'image/png', 'url': 'https://example.invalid/second.png'}
        ]
    })

    assert [segment.type for segment in event.data.message_sdk.data] == ['image', 'image', 'face']
    assert event.data.message_sdk.get('old_string').endswith('[CQ:face,id=311]')


def test_qq_picture_card_face_tag_does_not_add_face(bot):
    event = message_event(bot, 'C2C_MESSAGE_CREATE', picture_data(content='<faceType=1,faceId=0>'))

    assert [segment.type for segment in event.data.message_sdk.data] == ['image']


def test_qq_face_in_forward_content_uses_same_mapping():
    content = common._get_qq_forward_element_content({
        'content': FACE_TAG + MFACE_TAG
    })

    assert [(segment['type'], segment['data'].get('id')) for segment in content] == [
        ('face', '311'), ('mface', None)
    ]
    node = common._get_qq_forward_text_node('[消息内容] ' + FACE_TAG + MFACE_TAG, {'index': 0, 'items': []})
    assert [segment['type'] for segment in node['data']['content']] == ['face', 'mface']


def test_qq_forward_image_face_tag_does_not_add_face():
    element = {
        'content': '<faceType=1,faceId=0>' + FACE_TAG,
        'attachments': [{'content_type': 'image/png', 'url': PICTURE_URL}]
    }
    content = common._get_qq_forward_element_content(element)
    assert [segment['type'] for segment in content] == ['image', 'face']
    assert content[-1]['data']['id'] == '311'

    node = common._get_qq_forward_text_node(
        '[消息内容] <faceType=1,faceId=0>' + FACE_TAG + '\n[附件1] URL: ' + PICTURE_URL + ' 类型: image',
        {'index': 0, 'items': []}
    )
    assert [segment['type'] for segment in node['data']['content']] == ['image', 'face']


@pytest.mark.parametrize('event_type', EVENT_TYPES)
@pytest.mark.parametrize('use_attachment', [False, True])
@pytest.mark.parametrize('caption', ['', 'caption'])
def test_picture_event_delivers_image_and_preserves_raw_card(bot, event_type, use_attachment, caption):
    data = picture_data(content=caption)
    expected_url = PICTURE_URL
    if use_attachment:
        expected_url = 'https://example.invalid/full.png'
        data['attachments'] = [{'content_type': 'image/png', 'url': expected_url}]
    original = copy.deepcopy(data)
    event = message_event(bot, event_type, data)
    assert event.active is True
    assert event.plugin_info['func_type'] == (
        'private_message' if event_type == 'C2C_MESSAGE_CREATE' else 'group_message'
    )
    segments = event.data.message_sdk.data
    images = [segment for segment in segments if segment.type == 'image']
    assert len(images) == 1
    assert images[0].data['url'] == expected_url
    assert not any(segment.type == 'json' for segment in segments)
    if caption:
        assert any(segment.type == 'text' and segment.data['text'] == caption for segment in segments)
    assert event.data.extend['qq_ark_data'] == original['ark_data']
    assert data == original
    assert '[OP:image,' in event.data.message_sdk.get('olivos_string')
    common.req.request.assert_not_called()


@pytest.mark.parametrize('preview', [None, '', {}, [], 'file:///C:/image.png', 'javascript:alert(1)', 'https://['])
def test_picture_without_valid_image_remains_json(bot, preview):
    data = picture_data()
    data['ark_data']['fields']['preview'] = preview
    event = message_event(bot, 'C2C_MESSAGE_CREATE', data)
    assert event.active is True
    para = event.data.message_sdk.data[0]
    assert para.type == 'json'
    assert json.loads(para.data['data']) == data['ark_data']


@pytest.mark.parametrize('ark_type', [
    'tuwen', 'feed', 'miniapp', 'map', 'contact_card', 'video_share', 'music_together', 'future_type'
])
def test_other_ark_types_remain_json(bot, ark_type):
    data = picture_data()
    data['ark_data']['ark_type'] = ark_type
    event = message_event(bot, 'C2C_MESSAGE_CREATE', data)
    assert event.active is True
    assert event.data.message_sdk.data[0].type == 'json'
    assert json.loads(event.data.message_sdk.data[0].data['data']) == data['ark_data']


@pytest.mark.parametrize('event_type', EVENT_TYPES)
def test_picture_in_nested_forward_nodes(bot, event_type):
    data = picture_data()
    nested = {'message_type': 102, 'msg_elements': [{'message_type': 101, 'msg_elements': [data]}]}
    event = message_event(bot, event_type, nested)
    assert event.active is True
    assert event.data.message_sdk.data[0].type == 'forward'
    nodes = common._get_qq_forward_message(bot.hash, event.data.message_id)
    assert len(nodes) == 1
    assert nodes[0]['data']['content'][0]['type'] == 'image'
    assert nodes[0]['data']['content'][0]['data']['url'] == PICTURE_URL
    assert event.data.extend['qq_msg_elements'] == nested['msg_elements']


def test_forward_picture_prefers_attachments_and_keeps_other_media():
    data = picture_data(attachments=[
        {'content_type': 'image/png', 'url': PICTURE_URL},
        {'content_type': 'video/mp4', 'url': 'https://example.invalid/movie.mp4'}
    ])
    content = common._get_qq_forward_element_content(data)
    assert [segment['type'] for segment in content] == ['image', 'video']


def test_picture_preview_accepts_protocol_relative_url():
    data = picture_data()
    data['ark_data']['fields']['preview'] = '//example.invalid/photo.png'
    para = common._get_qq_structured_message_para(data)
    assert para.type == 'image'
    assert para.data['url'] == PICTURE_URL
