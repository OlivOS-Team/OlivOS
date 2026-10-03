"""Message conversion at public format boundaries, with one behavior per test."""

import json

import pytest

from OlivOS.core.core.messageAPI import PARA, Message_templet


@pytest.mark.parametrize('mode,prefix', [('old_string', 'CQ'), ('olivos_string', 'OP')])
def test_code_string_parses_text_mentions_and_media_in_order(mode, prefix):
    at_key = 'qq' if prefix == 'CQ' else 'id'
    message = Message_templet(mode, f'hello[{prefix}:at,{at_key}=42][{prefix}:image,file=picture.png]end')
    assert message.active
    assert [item.type for item in message.data] == ['text', 'at', 'image', 'text']
    assert message.data[1].data['id'] == '42'
    assert message.data[2].data['file'] == 'picture.png'


@pytest.mark.parametrize('mode,prefix', [('old_string', 'CQ'), ('olivos_string', 'OP')])
def test_segments_serialize_to_code_string(mode, prefix):
    message = Message_templet('olivos_para', [PARA.text('你好'), PARA.at('42'), PARA.reply('8')])
    at_key = 'qq' if prefix == 'CQ' else 'id'
    assert message.get(mode) == f'你好[{prefix}:at,{at_key}=42][{prefix}:reply,id=8]'


def test_onebot12_message_roundtrip_preserves_mentions():
    payload = [{'type': 'text', 'data': {'text': 'hi'}}, {'type': 'mention', 'data': {'user_id': '42'}},
               {'type': 'mention_all', 'data': {}}]
    message = Message_templet('obv12_para', payload)
    assert message.active and message.get('obv12_para') == payload


@pytest.mark.parametrize('mode', ['olivos_para', 'obv12_para', 'milky_para_rx'])
def test_invalid_segment_container_is_inactive(mode):
    message = Message_templet(mode, None)
    assert not message.active and message.data == []


def test_unknown_structured_segment_does_not_discard_valid_text():
    message = Message_templet('obv12_para', [
        None, {'type': 'future', 'data': {}}, {'type': 'text', 'data': {'text': 'kept'}}])
    assert message.active and message.get('olivos_string') == 'kept'


def test_segment_json_serialization_does_not_mutate_source():
    image = PARA.image('file.png', url='https://example.invalid/file.png')
    original = image.data.copy()
    serialized = json.loads(image.PARA())
    assert serialized['type'] == 'image' and serialized['data']['file'] == 'file.png'
    assert all(value is not None for value in serialized['data'].values())
    assert image.data == original


@pytest.mark.parametrize('mode', ['milky_para_rx', 'milky_para_tx'])
def test_milky_text_and_mentions(mode):
    message = Message_templet(mode, [
        {'type': 'text', 'data': {'text': 'hello'}}, {'type': 'mention_all', 'data': {}}])
    assert message.active and message.get('olivos_string') == 'hello[OP:at,id=all]'


def test_milky_outgoing_image_uses_uri():
    message = Message_templet('milky_para_tx', [
        {'type': 'image', 'data': {'uri': 'https://example.invalid/image.png', 'sub_type': 'normal'}}])
    assert message.active
    assert message.data[0].data['file'] == 'https://example.invalid/image.png'


@pytest.mark.parametrize('mode', ['milky_para_rx', 'milky_para_tx'])
def test_milky_light_app_is_preserved(mode):
    message = Message_templet(mode, [
        {'type': 'light_app', 'data': {'app_name': 'demo', 'json_payload': '{"title":"demo"}'}}])
    assert message.active and len(message.data) == 1
    assert message.data[0].type == 'json'
    assert json.loads(message.data[0].data['data']) == {'title': 'demo'}
