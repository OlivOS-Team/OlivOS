"""QQ API V2 media image management request construction."""

import json
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common


def _bot():
    return common.bot_info_T(id=10001, model='public')


def _request(monkeypatch, response=None):
    request = Mock(return_value=SimpleNamespace(
        text='' if response is None else json.dumps(response),
        status_code=200
    ))
    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda _: 'token')
    return request


def test_prepare_and_complete_media_image_payloads(monkeypatch):
    request = _request(monkeypatch, {'upload_id': 'upload-1'})
    prepare = OlivOS.qqGuildv2SDK.API.prepareMediaImage(_bot())
    prepare.data.file_name = 'image.png'
    prepare.data.file_size = 123
    prepare.data.content_type = 'image/png'
    prepare.data.md5 = 'a' * 32
    prepare.data.sha1 = 'b' * 40
    prepare.do_api()
    args, kwargs = request.call_args
    assert args == ('POST', 'https://api.bot.qq.com:443/v2/media-images/prepare')
    assert json.loads(kwargs['data']) == {
        'file_name': 'image.png', 'file_size': 123,
        'content_type': 'image/png', 'md5': 'a' * 32, 'sha1': 'b' * 40
    }
    assert kwargs['headers']['Authorization'] == 'QQBot token'

    complete = OlivOS.qqGuildv2SDK.API.completeMediaImage(_bot())
    complete.data.upload_id = 'upload-1'
    complete.data.md5 = 'a' * 32
    complete.do_api()
    assert json.loads(request.call_args.kwargs['data']) == {
        'upload_id': 'upload-1', 'md5': 'a' * 32
    }


def test_upload_media_image_uses_unsigned_presigned_put(monkeypatch):
    request = _request(monkeypatch)
    api = OlivOS.qqGuildv2SDK.API.uploadMediaImage(
        'https://upload.example.invalid/signed', 'image/png', b'image-bytes'
    )
    api.do_api()
    args, kwargs = request.call_args
    assert args == ('PUT', 'https://upload.example.invalid/signed')
    assert kwargs['headers'] == {'Content-Type': 'image/png'}
    assert kwargs['data'] == b'image-bytes'


def test_list_and_delete_media_images(monkeypatch):
    request = _request(monkeypatch, {'images': [], 'next_cursor': '', 'total': 0})
    listing = OlivOS.qqGuildv2SDK.API.getMediaImages(_bot())
    listing.query = {'cursor': 'cursor /+'}
    listing.do_api('GET')
    args = request.call_args.args
    assert urlparse(args[1]).path == '/v2/media-images'
    assert parse_qs(urlparse(args[1]).query) == {'cursor': ['cursor /+']}

    delete = OlivOS.qqGuildv2SDK.API.deleteMediaImage(_bot())
    delete.metadata.image_id = 'image-id'
    delete.do_api('DELETE')
    args, kwargs = request.call_args
    assert args == ('DELETE', 'https://api.bot.qq.com:443/v2/media-images/image-id/delete')
    assert 'data' not in kwargs
