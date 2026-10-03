"""Plugin event dispatch, blocking and exception isolation."""

import queue
import json
import sys
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


def register(loader, name, callback, support=None, priority=30000):
    loader.plugin_models_call_list.append(name)
    loader.plugin_models_dict[name] = {
        'name': name, 'namespace': name,
        'support': support or [{'sdk': 'all', 'platform': 'all', 'model': 'all'}],
        'message_mode': 'olivos_string',
        'priority': priority,
        'version': '1', 'svn': 1, 'author': 'N/A', 'info': 'N/A',
        'folder_path': '', 'menu_config': None,
        'model': SimpleNamespace(main=SimpleNamespace(Event=SimpleNamespace(group_message=callback))),
    }


def event_for(bot):
    packet = OlivOS.API.Control.packet('send', {'data': {'data': 'hello', 'user_conf': {
        'user_id': '42', 'target_id': '7', 'user_name': 'test', 'flag_group': True}}})
    return OlivOS.virtualTerminalSDK.event(packet, bot)


@pytest.mark.parametrize('model', OlivOS.onebotSDK.napcatModelMap + ['gocqhttp', 'lagrange_default'])
@pytest.mark.parametrize('reported_model', ['default', 'para_default'])
def test_account_model_resolves_only_configured_napcat(model, reported_model, monkeypatch):
    bot = OlivOS.API.bot_info_T(
        id=10001, platform_sdk='onebot', platform_platform='qq', platform_model=model)
    loader = OlivOS.pluginAPI.shallow(
        control_queue=queue.Queue(), rx_queue=queue.Queue(), bot_info_dict={bot.hash: bot})
    loader.log = Mock()
    monkeypatch.setattr(OlivOS.pluginAPI, 'gProc', loader)
    callback = Mock()
    register(loader, 'probe', callback)
    loader.plugin_models_dict['probe']['message_mode'] = 'old_string'
    payload = {'time': 1, 'self_id': 10001, 'post_type': 'message',
               'message_type': 'group', 'sub_type': 'normal', 'group_id': 7,
               'user_id': 42, 'message_id': 8, 'font': 0,
               'sender': {'user_id': 42, 'nickname': 'tester'},
               'message': [{'type': 'face', 'data': {'id': '311', 'raw': {
                   'faceText': '[表情]', 'faceType': 3, 'chainCount': 0}}}]}
    sdk_event = OlivOS.onebotSDK.event(json.dumps(payload))
    sdk_event.platform['model'] = reported_model
    loader.run_plugin(sdk_event)
    callback.assert_called_once()
    event = callback.call_args.kwargs['plugin_event']
    if model in OlivOS.onebotSDK.napcatModelMap:
        assert event.platform['model'] == reported_model
        assert event.data.message == '[CQ:face,id=311]'
        assert event.data.extend['napcat_face_data'] == [payload['message'][0]['data']]
    else:
        assert event.platform['model'] == reported_model
        assert 'raw=' in event.data.message
        assert 'napcat_face_data' not in event.data.extend


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


def test_call_order_without_override_matches_legacy_sort(dispatcher):
    loader, _ = dispatcher
    register(loader, 'beta', Mock(), priority=30000)
    register(loader, 'alpha', Mock(), priority=30000)
    register(loader, 'early', Mock(), priority=100)
    order_list = OlivOS.pluginAPI.build_plugin_call_order(loader.plugin_models_dict)
    assert order_list == ['early', 'alpha', 'beta']
    assert loader.plugin_models_dict['alpha']['priority_default'] == 30000
    assert loader.plugin_models_dict['alpha']['priority_user'] is None
    assert loader.plugin_models_dict['alpha']['priority_effective'] == 30000


def test_priority_override_only_changes_effective_order(dispatcher):
    loader, _ = dispatcher
    register(loader, 'alpha', Mock(), priority=30000)
    register(loader, 'beta', Mock(), priority=20000)
    model_before = loader.plugin_models_dict['alpha']['model']
    loader.apply_plugin_priority(overrides={'alpha': 100})
    assert loader.plugin_models_call_list == ['alpha', 'beta']
    assert loader.plugin_models_dict['alpha']['priority'] == 30000
    assert loader.plugin_models_dict['alpha']['priority_user'] == 100
    assert loader.plugin_models_dict['alpha']['priority_effective'] == 100
    assert loader.plugin_models_dict['alpha']['model'] is model_before
    assert loader.plugin_models_dict['beta']['priority_user'] is None


def test_hot_priority_change_affects_next_dispatch(dispatcher):
    loader, bot = dispatcher
    called = []
    register(loader, 'alpha', lambda plugin_event, Proc: called.append('alpha'), priority=30000)
    register(loader, 'beta', lambda plugin_event, Proc: called.append('beta'), priority=20000)
    loader.apply_plugin_priority(overrides={})
    loader.run_plugin(event_for(bot))
    assert called == ['beta', 'alpha']
    called.clear()
    loader.apply_plugin_priority(overrides={'alpha': 100})
    loader.run_plugin(event_for(bot))
    assert called == ['alpha', 'beta']


def test_priority_file_is_sparse_and_ignores_future_fields(tmp_path):
    path = tmp_path / 'plugin_priority.json'
    path.write_text(json.dumps({
        'version': 1,
        'plugins': {
            'valid': {'priority': 100},
            'legacy': 200,
            'future': {'before': ['valid']},
        },
    }), encoding='utf-8')
    overrides = OlivOS.pluginAPI.load_plugin_priority(str(path))
    assert overrides == {'valid': 100, 'legacy': 200}


@pytest.mark.parametrize('entry', [{'priority': True}, {'priority': 'high'}, []])
def test_priority_file_rejects_invalid_entry(tmp_path, entry):
    path = tmp_path / 'plugin_priority.json'
    path.write_text(json.dumps({'version': 1, 'plugins': {'broken': entry}}), encoding='utf-8')
    overrides = OlivOS.pluginAPI.load_plugin_priority(str(path))
    assert overrides == {}


def test_priority_file_missing_is_silent(tmp_path):
    assert OlivOS.pluginAPI.load_plugin_priority(str(tmp_path / 'missing.json')) == {}


def test_priority_file_ignores_negative_value(tmp_path):
    path = tmp_path / 'plugin_priority.json'
    path.write_text(json.dumps({'plugins': {'negative': {'priority': -1}}}), encoding='utf-8')
    assert OlivOS.pluginAPI.load_plugin_priority(str(path)) == {}


def test_negative_priority_override_is_ignored(dispatcher):
    loader, _ = dispatcher
    register(loader, 'alpha', Mock(), priority=30000)
    register(loader, 'beta', Mock(), priority=20000)
    order_list = OlivOS.pluginAPI.build_plugin_call_order(loader.plugin_models_dict, {'alpha': -1})
    assert order_list == ['beta', 'alpha']
    assert loader.plugin_models_dict['alpha']['priority_user'] is None


def test_priority_file_broken_falls_back_to_defaults(tmp_path):
    path = tmp_path / 'plugin_priority.json'
    path.write_text('{not json', encoding='utf-8')
    assert OlivOS.pluginAPI.load_plugin_priority(str(path)) == {}


def test_priority_reload_packet_applies_file_and_notifies_gui(dispatcher, tmp_path, monkeypatch):
    loader, _ = dispatcher
    register(loader, 'alpha', Mock(), priority=30000)
    register(loader, 'beta', Mock(), priority=20000)
    path = tmp_path / 'plugin_priority.json'
    path.write_text(json.dumps({'version': 1, 'plugins': {'alpha': {'priority': 100}}}),
                    encoding='utf-8')
    monkeypatch.setattr(OlivOS.pluginAPI, 'plugin_priority_path', str(path))
    loader.on_control_rx(OlivOS.API.Control.packet('send', {
        'data': {'action': 'plugin_priority_reload'}
    }))
    assert loader.plugin_models_call_list == ['alpha', 'beta']
    packet = loader.Proc_info.control_queue.get_nowait()
    assert packet.key['data']['action'] == 'update_data'
    payload = packet.key['data']['data']
    assert payload['priority_only'] is True
    assert payload['shallow_plugin_order_list'] == ['alpha', 'beta']
    assert payload['shallow_plugin_data_dict']['alpha'][6] == 100
    assert payload['shallow_plugin_priority_dict']['alpha'] == {
        'default': 30000, 'user': 100, 'effective': 100, 'source': 'user'}


def test_load_plugin_list_applies_priority_file(tmp_path, monkeypatch, dispatcher):
    loader, _ = dispatcher
    loader.database = SimpleNamespace(_init_namespace=lambda namespace: None)
    app_dir, tmp_dir = tmp_path / 'plugin/app', tmp_path / 'plugin/tmp'
    for name, priority in (('PriorityAlpha', 30000), ('PriorityBeta', 20000)):
        directory = app_dir / name
        directory.mkdir(parents=True)
        (directory / 'app.json').write_text(json.dumps({
            'name': name, 'namespace': name, 'priority': priority,
            'compatible_svn': OlivOS.infoAPI.OlivOS_SVN_Compatible, 'support': [],
        }), encoding='utf-8')
        (directory / '__init__.py').write_text('from . import main\n', encoding='utf-8')
        (directory / 'main.py').write_text('class Event:\n    pass\n', encoding='utf-8')
    (tmp_path / 'conf').mkdir()
    (tmp_path / 'conf/plugin_priority.json').write_text(
        json.dumps({'version': 1, 'plugins': {'PriorityAlpha': {'priority': 100}}}),
        encoding='utf-8')
    monkeypatch.setattr(OlivOS.pluginAPI, 'plugin_path', str(app_dir) + '/')
    monkeypatch.setattr(OlivOS.pluginAPI, 'plugin_path_tmp', str(tmp_dir) + '/')
    monkeypatch.syspath_prepend(str(app_dir))
    try:
        loader.load_plugin_list()
        assert loader.plugin_models_call_list == ['PriorityAlpha', 'PriorityBeta']
        assert loader.plugin_models_dict['PriorityAlpha']['priority'] == 30000
        assert loader.plugin_models_dict['PriorityAlpha']['priority_user'] == 100
        assert loader.plugin_models_dict['PriorityAlpha']['priority_effective'] == 100
        assert loader.plugin_models_dict['PriorityBeta']['priority_user'] is None
    finally:
        for name in ('PriorityAlpha', 'PriorityBeta'):
            sys.modules.pop(name, None)
