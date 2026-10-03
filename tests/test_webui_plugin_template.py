"""Plugin menu dispatch and browser reply isolation, without external repositories."""

import queue

import pytest

import OlivOS
from OlivOS.webUI import serverAPI


@pytest.fixture
def bridge(tmp_path):
    host = serverAPI.server(root_path=tmp_path, rx_queue=queue.Queue(), control_queue=queue.Queue())
    yield host
    host.on_terminate()


def menu_event(host, webui=None):
    data = {'action': 'plugin_menu', 'namespace': 'demo', 'event': 'read'}
    if webui is not None:
        data['webui'] = webui
    event = OlivOS.API.Event(OlivOS.API.Control.packet('send', {'data': data}))
    event.plugin_info.update(namespace='demo', control_queue=host.Proc_info.control_queue)
    return event


def test_browser_menu_payload_is_exposed_without_bot_context(bridge):
    event = menu_event(bridge, {'session': bridge.new_session(), 'request_id': 'request', 'payload': {'value': 4}})
    assert event.active and event.plugin_info['func_type'] == 'menu'
    assert event.data.namespace == 'demo' and event.data.payload == {'value': 4}
    assert event.bot_info is None


def test_browser_reply_is_delivered_only_to_requesting_session(bridge):
    session = bridge.new_session()
    event = menu_event(bridge, {'session': session, 'request_id': 'request', 'payload': {}})
    assert event.send('webui', 'request', {'value': 5}) is True
    bridge.consume(bridge.Proc_info.control_queue.get_nowait())
    reply = bridge.snapshot('events', session=session)
    assert len(reply) == 1 and reply[0]['payload'] == {'value': 5}
    assert reply[0]['namespace'] == 'demo' and reply[0]['request_id'] == 'request'
    assert bridge.snapshot('events', session=bridge.new_session()) == []


def test_native_menu_does_not_gain_browser_payload(bridge):
    event = menu_event(bridge)
    assert event.active and event.data.event == 'read'
    assert getattr(event.data, 'webui', None) is None
