"""QQ API V2 share-link request validation and response handling."""

import json
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import urlparse

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common

SDK = OlivOS.qqGuildv2SDK


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setattr(common.req, 'request', Mock(side_effect=AssertionError('Unexpected network call')))
    return OlivOS.API.bot_info_T(
        id=10001, platform_sdk='qqGuildv2_link', platform_platform='qqGuild', platform_model='public')


@pytest.mark.parametrize('callback_data', [None, '', 'custom_data_123', 'x' * 32, '图' * 32])
def test_generate_url_link_request_and_nested_response(bot, monkeypatch, callback_data):
    response = {'data': {'url': 'https://example.invalid/share'}}
    request = Mock(return_value=SimpleNamespace(text=json.dumps(response), status_code=200))
    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda _: None)
    target = SimpleNamespace(bot_info=bot)
    api = SDK.inde_interface(target, 'qqGuild')
    result = api.generate_url_link(callback_data, flag_log=False)
    assert result['active'] is True
    assert result['data']['operation'] == 'generate_url_link'
    assert result['data']['response'] == response
    assert result['data']['response']['data']['url'] == response['data']['url']
    args, kwargs = request.call_args
    assert args[0] == 'POST'
    assert urlparse(args[1]).hostname == 'api.bot.qq.com'
    assert urlparse(args[1]).path == '/v2/generate_url_link'
    assert json.loads(kwargs['data']) == ({} if callback_data is None else {'callback_data': callback_data})
    assert api.generate_url_link(remote=True) is None
    assert request.call_count == 1


@pytest.mark.parametrize('callback_data', ['x' * 33, '图' * 33, 123, False, {}, []])
def test_generate_url_link_rejects_invalid_data_before_network(bot, callback_data):
    result = SDK.event_action.generate_url_link(SimpleNamespace(bot_info=bot), callback_data)
    assert result['active'] is False
    assert 'callback_data' in result['data']['error']
    common.req.request.assert_not_called()


@pytest.mark.parametrize('status, response', [
    (400, {'code': 10001, 'message': 'invalid request'}),
    (200, {'code': 11004, 'message': 'generation failed'}),
    (503, {'message': 'unavailable'})
])
def test_generate_url_link_preserves_api_errors(bot, monkeypatch, status, response):
    monkeypatch.setattr(common.req, 'request', Mock(return_value=SimpleNamespace(
        text=json.dumps(response), status_code=status
    )))
    monkeypatch.setattr(common, 'getTokenNow', lambda _: None)
    result = SDK.event_action.generate_url_link(SimpleNamespace(bot_info=bot))
    assert result['active'] is False
    assert result['data']['http_status'] == status
    assert result['data']['response'] == response
