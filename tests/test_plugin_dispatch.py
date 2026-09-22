"""Plugin event dispatch, blocking and exception isolation."""

import queue
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS


@pytest.fixture
def dispatcher():
    bot = OlivOS.API.bot_info_T(id=10001, platform_sdk='terminal_link',
                                platform_platform='terminal', platform_model='default')
    loader = OlivOS.pluginAPI.shallow(
        control_queue=queue.Queue(), rx_queue=queue.Queue(), bot_info_dict={bot.hash: bot})
    loader.log = Mock()
    return loader, bot


def register(loader, name, callback, support=None):
    loader.plugin_models_call_list.append(name)
    loader.plugin_models_dict[name] = {
        'name': name, 'namespace': name,
        'support': support or [{'sdk': 'all', 'platform': 'all', 'model': 'all'}],
        'message_mode': 'olivos_string',
        'model': SimpleNamespace(main=SimpleNamespace(Event=SimpleNamespace(group_message=callback))),
    }


def event_for(bot):
    packet = OlivOS.API.Control.packet('send', {'data': {'data': 'hello', 'user_conf': {
        'user_id': '42', 'target_id': '7', 'user_name': 'test', 'flag_group': True}}})
    return OlivOS.virtualTerminalSDK.event(packet, bot)


def test_plugin_dispatch_preserves_order(dispatcher):
    loader, bot = dispatcher
    called = []
    for name in ('first', 'second'):
        register(loader, name, lambda plugin_event, Proc: called.append(plugin_event.plugin_info['namespace']))
    loader.run_plugin(event_for(bot))
    assert called == ['first', 'second']


def test_plugin_block_stops_later_handlers(dispatcher):
    loader, bot = dispatcher
    register(loader, 'first', lambda plugin_event, Proc: plugin_event.set_block())
    second = Mock()
    register(loader, 'second', second)
    loader.run_plugin(event_for(bot))
    second.assert_not_called()


def test_plugin_platform_filter_skips_unsupported_event(dispatcher):
    loader, bot = dispatcher
    callback = Mock()
    register(loader, 'wrong-platform', callback, [{'sdk': 'onebot', 'platform': 'qq', 'model': 'all'}])
    loader.run_plugin(event_for(bot))
    callback.assert_not_called()


def test_plugin_exception_is_logged_and_does_not_escape_dispatch(dispatcher):
    loader, bot = dispatcher
    register(loader, 'broken', Mock(side_effect=RuntimeError('fixture failure')))
    loader.run_plugin(event_for(bot))
    assert any(call.args[0] == 4 for call in loader.log.call_args_list)


def test_unknown_account_is_not_delivered_to_plugins(dispatcher):
    loader, bot = dispatcher
    callback = Mock()
    register(loader, 'demo', callback)
    loader.Proc_data['bot_info_dict'].clear()
    loader.run_plugin(event_for(bot))
    callback.assert_not_called()


def test_missing_plugin_is_removed_from_dispatch_order(dispatcher):
    loader, _ = dispatcher
    register(loader, 'exists', Mock())
    loader.plugin_models_call_list.append('missing')
    loader.check_plugin_list()
    assert loader.get_plugin_list() == ['exists']


def test_restart_request_uses_loader_queue(dispatcher):
    loader, _ = dispatcher
    loader.set_restart()
    packet = loader.Proc_info.rx_queue.get_nowait()
    assert packet.action == 'restart_do' and packet.key == loader.Proc_name
