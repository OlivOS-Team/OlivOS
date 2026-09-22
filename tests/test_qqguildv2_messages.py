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
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common

SDK = OlivOS.qqGuildv2SDK
PICTURE_URL = 'https://example.invalid/photo.png'
EVENT_TYPES = ['GROUP_AT_MESSAGE_CREATE', 'GROUP_MESSAGE_CREATE', 'C2C_MESSAGE_CREATE']


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
    return OlivOS.API.Event(SDK.event(payload, bot))


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
