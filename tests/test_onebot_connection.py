"""Connection authorization and session cleanup without live platform services."""

import asyncio
import queue
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import OlivOS


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
