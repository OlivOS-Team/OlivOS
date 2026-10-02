"""Connection authorization and session cleanup without live platform services."""

import asyncio
import queue
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import quote

import pytest

import OlivOS


SYMBOL_TOKEN = 'a&b=+/#?'


@pytest.fixture
def connection_host():
    bot = OlivOS.API.bot_info_T(id=10001, host='ws://127.0.0.1', port=0, access_token='fixture-token')
    host = OlivOS.onebotV11HostServerAPI.server(
        'test', bot_info_dict=bot, rx_queue=queue.Queue(), tx_queue=queue.Queue())
    host.on_unauth = Mock()
    host.on_open = Mock()
    host.on_close = Mock()
    return host


@pytest.mark.parametrize('header', ['fixture-token', 'Bearer fixture-token'])
def test_reverse_websocket_accepts_configured_authorization(connection_host, header):
    request = SimpleNamespace(headers={'Authorization': header})
    assert connection_host.auther(None, request) is None


@pytest.mark.parametrize('header', [None, '', 'wrong'])
def test_reverse_websocket_rejects_missing_or_wrong_authorization(connection_host, header):
    request = SimpleNamespace(headers={'Authorization': header} if header is not None else {})
    assert connection_host.auther(None, request).status_code == 401


@pytest.mark.parametrize('token', [SYMBOL_TOKEN, 'abc+def', '100%off', 'foo bar'])
def test_reverse_websocket_accepts_query_access_token_with_symbols(token):
    bot = OlivOS.API.bot_info_T(id=10001, host='ws://127.0.0.1', port=0, access_token=token)
    host = OlivOS.onebotV11HostServerAPI.server(
        'test', bot_info_dict=bot, rx_queue=queue.Queue(), tx_queue=queue.Queue())
    host.on_unauth = Mock()
    request = SimpleNamespace(headers={}, path='/?access_token=%s' % quote(token, safe=''))
    assert host.auther(None, request) is None
    host.on_unauth.assert_not_called()


def test_reverse_websocket_accepts_urlencoded_bearer_token():
    bot = OlivOS.API.bot_info_T(id=10001, host='ws://127.0.0.1', port=0, access_token=SYMBOL_TOKEN)
    host = OlivOS.onebotV11HostServerAPI.server(
        'test', bot_info_dict=bot, rx_queue=queue.Queue(), tx_queue=queue.Queue())
    host.on_unauth = Mock()
    request = SimpleNamespace(
        headers={'Authorization': 'Bearer %s' % quote(SYMBOL_TOKEN, safe='')}, path='/')
    assert host.auther(None, request) is None


def test_access_token_query_keeps_plus_and_ampersand():
    encoded = OlivOS.webTool.append_access_token_query('ws://127.0.0.1:8080/event', SYMBOL_TOKEN)
    query = encoded.split('access_token=', 1)[1]
    assert query == quote(SYMBOL_TOKEN, safe='')
    assert OlivOS.webTool.access_token_from_url(encoded) == SYMBOL_TOKEN


def test_onebot_http_api_encodes_access_token_query(monkeypatch):
    captured = {}

    def fake_request(method, url, headers=None, data=None, timeout=None):
        captured['url'] = url
        captured['headers'] = headers
        return SimpleNamespace(text='{}')

    monkeypatch.setattr(OlivOS.onebotSDK.req, 'request', fake_request)
    sender = OlivOS.onebotSDK.send_onebot_post_json_T()
    sender.bot_info = OlivOS.onebotSDK.bot_info_T(
        id=1, host='127.0.0.1', port=5700, access_token=SYMBOL_TOKEN)
    sender.obj = SimpleNamespace(__dict__={'message_type': 'private'})
    sender.node_ext = 'send_private_msg'
    sender.send_onebot_post_json()
    assert 'access_token=%s' % quote(SYMBOL_TOKEN, safe='') in captured['url']
    assert captured['headers']['Authorization'] == 'Bearer %s' % SYMBOL_TOKEN


def test_milky_and_onebot_forward_urls_encode_access_token():
    bot = OlivOS.API.bot_info_T(id=1, host='127.0.0.1', port=3000, access_token=SYMBOL_TOKEN)
    milky = OlivOS.milkyAutoServerAPI.ServerConf.init_conf_from_post_info(bot.post_info)
    encoded = quote(SYMBOL_TOKEN, safe='')
    assert 'access_token=%s' % encoded in milky.ws_url
    assert 'access_token=%s' % encoded in milky.http_url
    bot.post_info.host = 'ws://127.0.0.1:8080'
    link = OlivOS.onebotV11LinkServerAPI.ServerConf.init_conf_from_post_info(bot.post_info)
    assert 'access_token=%s' % encoded in link.url
    assert OlivOS.webTool.access_token_headers(SYMBOL_TOKEN)['Authorization'] == (
        'Bearer %s' % SYMBOL_TOKEN
    )


def test_disconnected_websocket_cancels_other_worker(connection_host):
    async def exercise():
        cancelled = asyncio.Event()

        async def transmit(_):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        connection_host.rx = AsyncMock(return_value=None)
        connection_host.tx = transmit
        await asyncio.wait_for(connection_host.session(Mock()), timeout=2)
        assert cancelled.is_set()
        assert connection_host._active_links.value == 0

    asyncio.run(exercise())
    connection_host.on_open.assert_called_once()
    connection_host.on_close.assert_called_once()
