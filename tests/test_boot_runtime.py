'''不启动真实工作进程的启动装配与主控制路由测试。'''

import json
import queue
from types import SimpleNamespace

import pytest

import OlivOS
from boot_runtime_support import FakeProc, FakeRuntimeRecords, install_boot_harness


def _records():
    records = {
        'instances': [],
        'constructed': [],
        'started': [],
        'terminated': [],
        'parent_terminated': [],
        'logs': [],
    }
    FakeRuntimeRecords.current = records
    return records


def test_request_plugin_lifecycle_queues_generation_and_start_time():
    '''生命周期请求应携带当前 generation 和启动时间，供拒绝过期控制包。'''

    proc = SimpleNamespace(
        Proc_info=SimpleNamespace(rx_queue=queue.Queue()),
        schedule_generation='generation-1',
    )
    OlivOS.bootAPI.request_plugin_lifecycle(proc, 'restart_do', started_at=123)
    packet = proc.Proc_info.rx_queue.get_nowait()
    assert packet.action == 'restart_do'
    assert packet.key == {'generation': 'generation-1', 'started_at': 123}
    proc.Proc_info.rx_queue = None
    OlivOS.bootAPI.request_plugin_lifecycle(proc, 'plugin_stop')


@pytest.mark.parametrize('action,operation,generation,registered,expected', [
    ('restart_do', 'restart', 'generation-1', True, 'restart'),
    ('stop_do', 'stop', 'generation-1', True, 'stop'),
    ('restart_do', 'stop', 'generation-1', True, None),
    ('stop_do', 'update', 'old-generation', True, None),
    ('stop_do', 'stop', 'generation-1', False, None),
])
def test_complete_plugin_lifecycle_accepts_only_matching_requests(
    action, operation, generation, registered, expected
):
    '''重启或停止请求必须同时匹配操作、generation 与注册表成员，否则不得结束进程。'''

    _records()
    proc = FakeProc(Proc_name='plugin', Proc_type='plugin', Proc_info=SimpleNamespace(rx_queue=queue.Queue()))
    process = SimpleNamespace(terminate=lambda: None, join=lambda: None)
    proc_dict = {'plugin': proc}
    process_dict = {'plugin': process} if registered else {}
    packet = SimpleNamespace(action=action, key={
        'name': 'plugin', 'operation': operation, 'generation': generation,
    })
    assert OlivOS.bootAPI.complete_plugin_lifecycle(packet, proc_dict, process_dict) == expected
    if expected is None:
        assert ('plugin' in process_dict) is registered
    else:
        assert process_dict == {}


def test_stop_component_calls_parent_hook_and_removes_both_registries():
    '''停止组件时应先调用父类钩子、终止进程并移除两个注册表项。'''

    _records()
    proc = FakeProc(Proc_name='link', Proc_type='onebotV11_link')
    process = proc.start_unity('threading')
    proc_dict = {'link': proc}
    process_dict = {'link': process}
    OlivOS.bootAPI.stop_component('link', proc_dict, process_dict)
    assert proc.records['parent_terminated'] == ['link']
    assert process.terminated and process.joined
    assert proc_dict == {} and process_dict == {}
    OlivOS.bootAPI.stop_component('missing', proc_dict, process_dict)


def test_schedule_status_routes_only_to_live_webui_queues():
    '''插件调度快照只能路由到存活的 WebUI 队列，不能广播给协议或日志进程。'''

    _records()
    web = FakeProc(Proc_name='web', Proc_type='webUI', rx_queue=queue.Queue())
    link = FakeProc(Proc_name='link', Proc_type='onebotV11_link', rx_queue=queue.Queue())
    OlivOS.bootAPI._send_schedule_status({'web': web, 'link': link})
    status = web.Proc_info.rx_queue.get_nowait()
    assert status.action == 'send'
    assert status.key['data']['action'] == 'plugin_schedule_status'
    assert link.Proc_info.rx_queue.empty()


@pytest.mark.parametrize('source,proc_type,generation,expected', [
    ({'name': 'plugin', 'generation': 'generation-1'}, 'plugin', 'generation-1', True),
    ({'name': 'plugin', 'generation': 'old'}, 'plugin', 'generation-1', False),
    ({'name': 'link', 'generation': 'generation-1'}, 'onebotV11_link', 'generation-1', False),
    ({'name': 'missing', 'generation': 'generation-1'}, None, None, False),
    ('bad-source', None, None, False),
])
def test_current_schedule_source_requires_live_plugin_generation(source, proc_type, generation, expected):
    '''只有当前存活插件代次才能发布调度快照，未知或过期来源一律拒绝。'''

    proc = SimpleNamespace(Proc_type=proc_type, schedule_generation=generation)
    packet = SimpleNamespace(key={'schedule_source': source})
    assert OlivOS.bootAPI._current_schedule_source(packet, {'plugin': proc, 'link': proc}) is expected


@pytest.mark.parametrize('update_available', [True, False])
def test_update_get_func_only_queues_replace_when_update_exists(monkeypatch, update_available):
    '''后台更新检查仅在发现新版本时排队 update_replace，否则保持控制队列为空。'''

    monkeypatch.setattr(OlivOS.updateAPI, 'OlivOSUpdateGet', lambda **kwargs: update_available)
    control_queue = queue.Queue()
    OlivOS.bootAPI.update_get_func(
        {'logger': object()}, {'logger_proc': 'logger'}, control_queue)
    if update_available:
        assert control_queue.get_nowait().action == 'init_type'
    else:
        assert control_queue.empty()


def test_boot_monitor_tracks_registration_changes(monkeypatch):
    '''组件注册集合出现或消失时应刷新监控登记，并记录本次变化。'''

    messages = []
    monkeypatch.setattr(OlivOS.bootAPI, 'logG', lambda level, message, segment=None: messages.append(message))
    monkeypatch.setattr(OlivOS.bootAPI, 'gMonitorReg', {})
    OlivOS.bootAPI.bootMonitor({'Proc_dict': {'a': object()}})
    OlivOS.bootAPI.bootMonitor({'Proc_dict': {'b': object()}})
    assert OlivOS.bootAPI.gMonitorReg['Proc_dict']['keys'] == ['b']
    assert len(messages) == 3


def test_entity_start_assembles_models_and_routes_control_packets(monkeypatch, tmp_path):
    '''Entity.start 应按账号装配进程，并保持控制面与数据面路由互不混用。'''

    harness = install_boot_harness(monkeypatch)
    config_path = tmp_path / 'basic.json'
    config_path.write_text(json.dumps(harness.config), encoding='utf-8')
    link_name = 'link=' + harness.bot.hash

    send_link = harness.packet('send', {
        'target': {'type': 'onebotV11_link', 'hash': harness.bot.hash, 'fliter': 'all'},
        'data': {'action': 'probe'},
    })
    schedule = harness.packet('send', {
        'target': {'type': 'webUI'},
        'data': {'action': 'plugin_schedule_status'},
        'schedule_source': {'name': 'plugin', 'generation': 'generation-1'},
    })
    extras = [
        send_link,
        schedule,
        harness.packet('restart_send', {'type': 'webUI', 'started_at': 1}),
        harness.packet('restart_send', {'type': 'plugin', 'started_at': 2}),
        harness.packet('call_system_event', {'action': ['ready']}),
        harness.packet('webui_accounts', {'name': 'webui', 'request_id': 'request-1'}),
        harness.packet('call_account_update', {'data': harness.accounts}),
        harness.packet('init_type', 'plugin'),
        harness.packet('plugin_lifecycle_rejected', {
            'name': 'plugin', 'generation': 'generation-1', 'operation': 'stop', 'reason': 'fixture',
        }),
        harness.packet('restart_do', 'missing'),
        harness.packet('call_system_stop_type_event', {'action': ['shutdown']}),
        harness.packet('stop', 'plugin'),
        harness.packet('exit_total'),
    ]
    harness.control_queue.after_gets[len(harness.config['system']['init'])] = extras

    with pytest.raises(KeyboardInterrupt):
        OlivOS.bootAPI.Entity(
            basic_conf=str(config_path), patch_conf=str(tmp_path / 'patch.json')).start()

    instances = {proc.Proc_name: proc for proc in harness.records['instances']}
    logger = next(proc for proc in harness.records['instances'] if proc.Proc_type == 'logger')
    link = next(proc for proc in harness.records['instances'] if proc.Proc_name == link_name)
    plugin = instances['plugin']
    web = instances['webui']
    assert harness.account_calls == [('./conf/account.json', logger, True)]
    assert ('onebotV11_link', link_name) in harness.records['constructed']
    assert ('webUI', 'webui') in harness.records['constructed']
    assert ('plugin', 'plugin') in harness.records['constructed']
    assert harness.records['started'] == [
        ('logger', 'processing'),
        ('plugin', 'processing'),
        ('webui', 'threading'),
        (link_name, 'threading'),
    ]

    assert link_name in harness.records['parent_terminated']
    assert link_name in harness.records['terminated']
    assert 'killMain' in [message for level, message in harness.records['logs']]

    # 按账号命名的队列应同时收到定向包和广播包。
    assert link.Proc_info.control_rx_queue.get_nowait() is send_link
    assert link.Proc_info.rx_queue.get_nowait() is send_link
    assert web.Proc_info.rx_queue.get_nowait() is schedule
    assert web.Proc_info.rx_queue.get_nowait().action == 'restart_do'
    assert web.commit_calls[0][0] == 'request-1'
    assert [item[1] for item in harness.records['lifecycle']] == ['restart_do', 'plugin_stop']
    assert plugin.Proc_info.rx_queue.get_nowait().action == 'restart_do'
    assert plugin.Proc_info.rx_queue.get_nowait().action == 'plugin_stop'
