# -*- encoding: utf-8 -*-
r'''
@File      :   tests/test_flask_post_reload.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   OneBot V11 HTTP POST (flask_post_rx) 账号热重载停服、端口释放与端口保持回归测试
'''

import copy
import json
import multiprocessing
import queue
import socket
import threading
import time
import urllib.request
from unittest.mock import Mock

import pytest

import OlivOS
from boot_runtime_support import FakeProc, install_boot_harness


@pytest.fixture(autouse=True)
def _restore_flask_registries():
    servers = list(OlivOS.flaskServerAPI._http_post_servers)
    retired = dict(OlivOS.flaskServerAPI._retired_activity)
    OlivOS.flaskServerAPI._http_post_servers.clear()
    OlivOS.flaskServerAPI._retired_activity.clear()
    try:
        yield
    finally:
        OlivOS.flaskServerAPI._http_post_servers[:] = servers
        OlivOS.flaskServerAPI._retired_activity.clear()
        OlivOS.flaskServerAPI._retired_activity.update(retired)


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _make_post_bot(bot_id=3520767439):
    bot = OlivOS.API.bot_info_T(
        id=bot_id,
        server_type='post',
        host='http://127.0.0.1',
        port=9873,
        access_token='NONEED',
        platform_sdk='onebot',
        platform_platform='qq',
        platform_model='default',
    )
    bot.enable = True
    return bot


def _wait_for_server(server, port, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if server._wsgi_server is not None and OlivOS.accountAPI.isInuse('127.0.0.1', port):
            return True
        time.sleep(0.02)
    return False


def _post_heartbeat(port, bot_id):
    payload = json.dumps({
        'time': int(time.time()),
        'self_id': bot_id,
        'post_type': 'meta_event',
        'meta_event_type': 'heartbeat',
        'status': {'online': True, 'good': True},
        'interval': 30000,
    }).encode('utf-8')
    req = urllib.request.Request(
        f'http://127.0.0.1:{port}/OlivOSMsgApi/qq/onebot/default',
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=5.0) as resp:
        return resp.status, resp.read()


def test_flask_post_rx_proc_type_matches_account_update_stop_event():
    """热重载按 Proc_type 停止组件；flaskServerAPI 必须与 default_Conf 对齐。"""
    server = OlivOS.flaskServerAPI.server(
        Proc_name='OlivOS_flask_post_rx',
        Flask_namespace='probe',
        Flask_server_methods=['GET', 'POST'],
        Flask_host='127.0.0.1',
        Flask_port=0,
    )
    stop_types = OlivOS.bootDataAPI.default_Conf['system']['type_event']['account_update']
    assert server.Proc_type == 'flask_post_rx'
    assert server.Proc_type in stop_types


def test_on_terminate_stops_wsgi_server_and_is_idempotent():
    server = OlivOS.flaskServerAPI.server(
        Proc_name='OlivOS_flask_post_rx',
        Flask_namespace='probe',
        Flask_server_methods=['GET', 'POST'],
        Flask_host='127.0.0.1',
        Flask_port=0,
    )
    fake_wsgi = Mock()
    server._wsgi_server = fake_wsgi

    server.on_terminate()

    fake_wsgi.stop.assert_called_once_with()
    assert server._wsgi_server is None
    assert server._stop_requested is True
    assert server not in OlivOS.flaskServerAPI._http_post_servers

    # 重复调用或未绑定监听对象时必须安全。
    server.on_terminate()
    fake_wsgi.stop.assert_called_once_with()


def test_stoppable_thread_terminate_tolerates_thread_exiting_during_on_terminate():
    """on_terminate 主动唤醒并让线程退出后，stop_thread 不得因无效线程 ID 抛 ValueError。"""
    release = threading.Event()
    entered = threading.Event()

    class CleanExitProc:
        def on_terminate(self):
            release.set()
            # 等待工作线程自行退出，稳定复现 stop_thread 紧随其后执行的时序。
            time.sleep(0.05)

    def worker():
        entered.set()
        release.wait(timeout=3.0)

    thread = OlivOS.API.StoppableThread(target=worker)
    thread.root = CleanExitProc()
    thread.daemon = True
    thread.start()
    assert entered.wait(timeout=3.0)

    thread.terminate()
    threading.Thread.join(thread, timeout=3.0)
    assert not thread.is_alive()


def test_flask_post_hot_reload_keeps_port_releases_socket_and_reports_online():
    """真实热重载闭环：accountFix 不漂移端口，停服释放旧端口，重启同端口后立即恢复在线。"""
    port = _free_port()
    bot = _make_post_bot()
    accounts = {bot.hash: bot}
    tx_queue = queue.Queue()
    models = {
        'OlivOS_flask_post_rx': {
            'enable': True,
            'name': 'OlivOS_flask_post_rx',
            'type': 'post',
            'server': {'auto': True, 'host': '127.0.0.1', 'port': port},
        }
    }
    proc_dict = {}
    proc_proc_dict = {}

    server1 = OlivOS.flaskServerAPI.server(
        Proc_name='OlivOS_flask_post_rx',
        Flask_namespace='test_flask_reload_1',
        Flask_server_methods=['GET', 'POST'],
        Flask_host='127.0.0.1',
        Flask_port=port,
        tx_queue=tx_queue,
        bot_info_dict=accounts,
    )
    proc_dict['OlivOS_flask_post_rx'] = server1
    thread1 = server1.start_unity('threading')
    proc_proc_dict['OlivOS_flask_post_rx'] = thread1
    started_threads = [thread1]
    started_servers = [server1]
    try:
        assert _wait_for_server(server1, port), 'first flask server did not bind port'

        status_code, body = _post_heartbeat(port, bot.id)
        assert status_code == 200 and body == b'200'
        assert OlivOS.flaskServerAPI.http_post_activity()[bot.hash] > 0

        # 模拟 WebUI / NativeGUI 在停服前先执行 accountFix：不得将自身占用的端口漂移到随机端口。
        OlivOS.accountAPI.accountFix(models, accounts, Mock(), active_procs=proc_dict)
        assert models['OlivOS_flask_post_rx']['server']['port'] == port

        # 即使调用方走旧的三参数签名，也应识别本进程正在监听的同名服务。
        OlivOS.accountAPI.accountFix(models, accounts, Mock())
        assert models['OlivOS_flask_post_rx']['server']['port'] == port

        # 热重载停止旧组件：必须同步释放监听端口且不抛异常。
        OlivOS.bootAPI.stop_component('OlivOS_flask_post_rx', proc_dict, proc_proc_dict)
        assert proc_dict == {} and proc_proc_dict == {}
        assert OlivOS.flaskServerAPI.http_post_activity()[bot.hash] < 0
        threading.Thread.join(thread1, timeout=3.0)
        assert not thread1.is_alive()
        ctrl1 = OlivOS.API.get_control_rx_thread(server1)
        if ctrl1 is not None:
            threading.Thread.join(ctrl1, timeout=3.0)
            assert not ctrl1.is_alive()

        # 热重载重建新组件：立即重新绑定同一端口并接管在线状态。
        server2 = OlivOS.flaskServerAPI.server(
            Proc_name='OlivOS_flask_post_rx',
            Flask_namespace='test_flask_reload_2',
            Flask_server_methods=['GET', 'POST'],
            Flask_host='127.0.0.1',
            Flask_port=models['OlivOS_flask_post_rx']['server']['port'],
            tx_queue=tx_queue,
            bot_info_dict=accounts,
        )
        proc_dict['OlivOS_flask_post_rx'] = server2
        thread2 = server2.start_unity('threading')
        proc_proc_dict['OlivOS_flask_post_rx'] = thread2
        started_threads.append(thread2)
        started_servers.append(server2)
        assert _wait_for_server(server2, port), 'restarted flask server did not rebind same port'

        status_code, body = _post_heartbeat(port, bot.id)
        assert status_code == 200 and body == b'200'
        assert server2.account_activity()[bot.hash] > 0
        assert OlivOS.flaskServerAPI.http_post_activity()[bot.hash] > 0
    finally:
        if 'OlivOS_flask_post_rx' in proc_dict:
            OlivOS.bootAPI.stop_component('OlivOS_flask_post_rx', proc_dict, proc_proc_dict)
        for thread in started_threads:
            threading.Thread.join(thread, timeout=3.0)
        for server in started_servers:
            ctrl = OlivOS.API.get_control_rx_thread(server)
            if ctrl is not None:
                threading.Thread.join(ctrl, timeout=3.0)


def test_account_fix_reallocates_port_when_occupied_by_external_process():
    """端口确实被外部进程占用时，accountFix 仍须自动切换空闲端口以支持多开。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as external:
        external.bind(('127.0.0.1', 0))
        external.listen(1)
        occupied_port = external.getsockname()[1]
        models = {
            'OlivOS_flask_post_rx': {
                'enable': True,
                'name': 'OlivOS_flask_post_rx',
                'type': 'post',
                'server': {'auto': True, 'host': '127.0.0.1', 'port': occupied_port},
            }
        }
        OlivOS.accountAPI.accountFix(models, {}, Mock(), active_procs={})
        assert models['OlivOS_flask_post_rx']['server']['port'] != occupied_port


def test_account_fix_keeps_port_in_processing_mode_via_active_procs():
    """processing 模式下监听套接字在子进程，父进程通过 active_procs 识别自有端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as child_listener:
        child_listener.bind(('127.0.0.1', 0))
        child_listener.listen(1)
        port = child_listener.getsockname()[1]
        parent_proc = OlivOS.flaskServerAPI.server(
            Proc_name='OlivOS_flask_post_rx',
            Flask_namespace='parent_stub',
            Flask_server_methods=['GET', 'POST'],
            Flask_host='0.0.0.0',
            Flask_port=port,
        )
        assert parent_proc._wsgi_server is None
        models = {
            'OlivOS_flask_post_rx': {
                'enable': True,
                'name': 'OlivOS_flask_post_rx',
                'type': 'post',
                'server': {'auto': True, 'host': '0.0.0.0', 'port': port},
            }
        }
        OlivOS.accountAPI.accountFix(
            models, {}, Mock(), active_procs={'OlivOS_flask_post_rx': parent_proc}
        )
        assert models['OlivOS_flask_post_rx']['server']['port'] == port


def test_boot_account_update_reloads_flask_post_rx_on_same_port(monkeypatch, tmp_path):
    """主控制循环执行 account_fix -> stop_type -> init 后应先停旧服再以同端口重建。"""
    harness = install_boot_harness(monkeypatch)
    bot = _make_post_bot()
    harness.accounts.clear()
    harness.accounts[bot.hash] = bot

    port = _free_port()
    config = copy.deepcopy(harness.config)
    config['system']['init'] = ['logger', 'accounts', 'OlivOS_account_fix', 'OlivOS_flask_post_rx']
    config['system']['event']['account_update'] = ['OlivOS_flask_post_rx']
    config['system']['type_event']['account_update'] = ['flask_post_rx']
    config['models']['OlivOS_account_fix'] = {
        'enable': True,
        'name': 'OlivOS_account_fix',
        'type': 'account_fix',
        'logger_proc': 'logger',
    }
    config['models']['OlivOS_flask_post_rx'] = {
        'enable': True,
        'name': 'OlivOS_flask_post_rx',
        'type': 'post',
        'interval': 0.001,
        'dead_interval': 0.01,
        'tx_queue': 'link_tx',
        'logger_proc': 'logger',
        'debug': False,
        'server': {'auto': True, 'host': '127.0.0.1', 'port': port},
    }

    class FakeFlaskProc(FakeProc):
        default_type = 'flask_post_rx'

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.Proc_config['Flask_server_port'] = kwargs.get('Flask_port')

    def flask_factory(*args, **kwargs):
        kwargs['_records'] = harness.records
        return FakeFlaskProc(*args, **kwargs)

    monkeypatch.setattr(OlivOS.flaskServerAPI, 'server', flask_factory)
    monkeypatch.setattr(OlivOS.fanbookPollServerAPI, 'accountFix', lambda bot_info_dict, logger_proc: bot_info_dict)
    monkeypatch.setattr(OlivOS.kaiheilaLinkServerAPI, 'accountFix', lambda bot_info_dict, logger_proc: bot_info_dict)
    monkeypatch.setattr(OlivOS.discordLinkServerAPI, 'accountFix', lambda bot_info_dict, logger_proc: bot_info_dict)
    if hasattr(OlivOS, 'libEXEModelAPI'):
        monkeypatch.setattr(OlivOS.libEXEModelAPI, 'accountFix', lambda bot_info_dict, logger_proc: bot_info_dict)
    # 模拟端口正被该组件占用，验证 bootAPI 传入 active_procs=Proc_dict 后不会漂移端口。
    monkeypatch.setattr(OlivOS.accountAPI, 'isInuse', lambda ip, p: p == port)

    config_path = tmp_path / 'basic.json'
    config_path.write_text(json.dumps(config), encoding='utf-8')
    harness.control_queue.after_gets[len(config['system']['init'])] = [
        harness.packet('init', 'OlivOS_account_fix'),
        harness.packet('call_system_stop_type_event', {'action': ['account_update']}),
        harness.packet('call_system_event', {'action': ['account_update']}),
        harness.packet('exit_total'),
    ]

    with pytest.raises(KeyboardInterrupt):
        OlivOS.bootAPI.Entity(
            basic_conf=str(config_path), patch_conf=str(tmp_path / 'patch.json')
        ).start()

    flask_instances = [
        proc for proc in harness.records['instances'] if proc.Proc_name == 'OlivOS_flask_post_rx'
    ]
    assert len(flask_instances) == 2
    assert flask_instances[0].Proc_config['Flask_server_port'] == port
    assert flask_instances[1].Proc_config['Flask_server_port'] == port
    assert 'OlivOS_flask_post_rx' in harness.records['parent_terminated']
    assert 'OlivOS_flask_post_rx' in harness.records['terminated']


def test_boot_post_init_stops_existing_instance_even_without_stop_type(monkeypatch, tmp_path):
    """即使自定义 basic.json 未触发 stop_type，再次 init post 组件前也须先停旧实例。"""
    harness = install_boot_harness(monkeypatch)
    bot = _make_post_bot()
    harness.accounts.clear()
    harness.accounts[bot.hash] = bot

    port = _free_port()
    config = copy.deepcopy(harness.config)
    config['system']['init'] = ['logger', 'accounts', 'OlivOS_flask_post_rx']
    config['models']['OlivOS_flask_post_rx'] = {
        'enable': True,
        'name': 'OlivOS_flask_post_rx',
        'type': 'post',
        'interval': 0.001,
        'dead_interval': 0.01,
        'tx_queue': 'link_tx',
        'logger_proc': 'logger',
        'debug': False,
        'server': {'auto': True, 'host': '127.0.0.1', 'port': port},
    }

    class FakeFlaskProc(FakeProc):
        default_type = 'flask_post_rx'

    monkeypatch.setattr(
        OlivOS.flaskServerAPI,
        'server',
        lambda *args, **kwargs: FakeFlaskProc(*args, _records=harness.records, **kwargs),
    )

    config_path = tmp_path / 'basic.json'
    config_path.write_text(json.dumps(config), encoding='utf-8')
    harness.control_queue.after_gets[len(config['system']['init'])] = [
        harness.packet('init', 'OlivOS_flask_post_rx'),
        harness.packet('exit_total'),
    ]

    with pytest.raises(KeyboardInterrupt):
        OlivOS.bootAPI.Entity(
            basic_conf=str(config_path), patch_conf=str(tmp_path / 'patch.json')
        ).start()

    assert 'OlivOS_flask_post_rx' in harness.records['parent_terminated']
    assert 'OlivOS_flask_post_rx' in harness.records['terminated']


def test_webui_commit_accounts_keeps_running_flask_post_port(monkeypatch, tmp_path):
    """WebUI 保存账号时必须将 host.runtime 传给 accountFix，避免自身占用端口被判冲突。"""
    from OlivOS.webUI import pageAPI
    from webui_test_support import make_host

    bot = _make_post_bot()
    account_path = tmp_path / 'account.json'
    OlivOS.accountAPI.Account.save(account_path, Mock(), {bot.hash: bot})
    port = _free_port()
    parent_proc = OlivOS.flaskServerAPI.server(
        Proc_name='OlivOS_flask_post_rx',
        Flask_namespace='webui_commit_stub',
        Flask_server_methods=['GET', 'POST'],
        Flask_host='0.0.0.0',
        Flask_port=port,
        bot_info_dict={bot.hash: bot},
    )
    runtime = {'OlivOS_flask_post_rx': parent_proc}
    control_queue = queue.Queue()
    host = make_host(
        control_queue=control_queue,
        bot_info_dict={bot.hash: bot},
        account_path=str(account_path),
        runtime=runtime,
        root_path=str(tmp_path),
    )
    try:
        models = {
            'OlivOS_flask_post_rx': {
                'enable': True,
                'name': 'OlivOS_flask_post_rx',
                'type': 'post',
                'server': {'auto': True, 'host': '0.0.0.0', 'port': port},
            }
        }
        monkeypatch.setattr(OlivOS.accountAPI, 'isInuse', lambda ip, p: p == port)
        payload = pageAPI.account_response(host.accounts)
        done = threading.Event()
        host.pending['req-1'] = {'body': payload, 'done': done, 'result': None}

        host.commit_accounts('req-1', models)

        assert done.is_set()
        body, status = host.pending['req-1']['result']
        assert status == 200
        assert models['OlivOS_flask_post_rx']['server']['port'] == port
    finally:
        host.on_terminate()


def test_running_logger_and_plugin_remain_picklable_for_windows_spawn():
    """线程模式已运行的 logger 被 OlivOS_plugin 持有时，仍须可被 spawn 子进程序列化。"""
    ctx = multiprocessing.get_context('spawn')
    logger_queue = ctx.Queue()
    control_queue = ctx.Queue()
    rx_queue = ctx.Queue()
    tx_queue = ctx.Queue()
    logger_proc = OlivOS.diagnoseAPI.logger(
        Proc_name='OlivOS_logger',
        scan_interval=0.01,
        dead_interval=1,
        logger_queue=logger_queue,
        logger_mode=[],
        logger_vis_level=[2, 3, 4, 5],
        control_queue=control_queue,
    )
    logger_thread = logger_proc.start_unity('threading')
    try:
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            ctrl = OlivOS.API.get_control_rx_thread(logger_proc)
            if ctrl is not None and ctrl.is_alive():
                break
            time.sleep(0.01)
        ctrl = OlivOS.API.get_control_rx_thread(logger_proc)
        assert ctrl is not None and ctrl.is_alive()

        plugin_proc = OlivOS.pluginAPI.shallow(
            Proc_name='OlivOS_plugin',
            scan_interval=0.01,
            dead_interval=1,
            rx_queue=rx_queue,
            tx_queue=[tx_queue],
            control_queue=control_queue,
            logger_proc=logger_proc,
            debug_mode=False,
            plugin_func_dict={},
            bot_info_dict={},
        )
        # 真实通过 spawn 启动子进程，覆盖 Windows popen_spawn_win32 的 ForkingPickler 序列化路径。
        probe = ctx.Process(target=bool, args=(plugin_proc.run_total,))
        probe.start()
        probe.join(timeout=15.0)
        assert probe.exitcode == 0
    finally:
        ctrl = OlivOS.API.get_control_rx_thread(logger_proc)
        logger_thread.terminate()
        threading.Thread.join(logger_thread, timeout=3.0)
        if ctrl is not None:
            threading.Thread.join(ctrl, timeout=3.0)
            assert not ctrl.is_alive()


def test_flask_post_server_remains_picklable_for_processing_mode():
    """flaskServerAPI.server 在 processing 模式下须可被 spawn 子进程序列化并恢复锁。"""
    ctx = multiprocessing.get_context('spawn')
    bot = _make_post_bot()
    server = OlivOS.flaskServerAPI.server(
        Proc_name='OlivOS_flask_post_rx',
        Flask_namespace='test_flask_pickle',
        Flask_server_methods=['GET', 'POST'],
        Flask_host='0.0.0.0',
        Flask_port=55001,
        tx_queue=ctx.Queue(),
        bot_info_dict={bot.hash: bot},
    )
    state = server.__getstate__()
    assert state['_wsgi_lock'] is None and state['_wsgi_server'] is None

    restored = OlivOS.flaskServerAPI.server.__new__(OlivOS.flaskServerAPI.server)
    restored.__setstate__(state)
    assert restored._wsgi_lock is not None
    with restored._wsgi_lock:
        assert restored._wsgi_server is None

    probe = ctx.Process(target=bool, args=(server.run_total,))
    probe.start()
    probe.join(timeout=15.0)
    assert probe.exitcode == 0
