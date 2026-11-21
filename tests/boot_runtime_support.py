'''用于覆盖 bootAPI 且不创建进程的伪运行时组件。'''

import queue
from collections import deque
from types import SimpleNamespace

import OlivOS


Packet = OlivOS.API.Control.packet


class MemoryQueue(queue.Queue):
    '''提供 boot 主循环所需 multiprocessing.Queue 子集的队列。'''


class ScriptedControlQueue:
    '''在若干次初始读取后注入预设控制包的控制队列。'''

    def __init__(self):
        self.items = deque()
        self.after_gets = {}
        self.gets = 0

    def put(self, item, block=None):
        self.items.append(item)

    def get(self, block=None):
        if not self.items:
            raise KeyboardInterrupt()
        item = self.items.popleft()
        self.gets += 1
        self.items.extend(self.after_gets.pop(self.gets, []))
        return item

    def empty(self):
        if not self.items and self.gets:
            raise KeyboardInterrupt()
        return not self.items


class FakeControl:
    '''绑定调用方脚本队列的控制对象替身。'''

    packet = Packet

    def __init__(self, name, init_list, control_queue, scan_interval, queue_obj=None):
        self.name = name
        self.init_list = init_list
        self.control_queue = queue_obj if queue_obj is not None else control_queue
        self.scan_interval = scan_interval


class FakeProcess:
    '''FakeProc.start_unity() 返回的可终止进程占位对象。'''

    def __init__(self, proc):
        self.proc = proc
        self.name = proc.Proc_name
        self.terminated = False
        self.joined = False

    def terminate(self):
        self.terminated = True
        self.proc.records['terminated'].append(self.proc.Proc_name)

    def join(self, timeout=None):
        self.joined = True


class FakeProc:
    '''记录公开状态的可配置 Proc_templet 替代实现。'''

    default_type = 'fake'

    def __init__(self, *args, **kwargs):
        self.Proc_name = kwargs.get('Proc_name', args[0] if args else 'fake')
        self.Proc_type = kwargs.get('Proc_type', self.default_type)
        self.Proc_config = dict(kwargs)
        self.Proc_data = {
            'bot_info_dict': kwargs.get('bot_info_dict'),
            'extend_data': {'ws_obj': None},
        }
        self.Proc_info = SimpleNamespace(
            rx_queue=kwargs.get('rx_queue'),
            tx_queue=kwargs.get('tx_queue'),
            control_queue=kwargs.get('control_queue'),
            control_rx_queue=queue.Queue(),
            logger_proc=kwargs.get('logger_proc'),
            dead_interval=kwargs.get('dead_interval', 0),
        )
        self.schedule_generation = 'generation-1'
        self.debug_logger = None
        self.commit_calls = []
        self.start_modes = []
        self.records = kwargs.get('_records') or FakeRuntimeRecords.current
        self.records['instances'].append(self)
        self.records['constructed'].append((self.Proc_type, self.Proc_name))

    def start_unity(self, mode='threading'):
        self.start_modes.append(mode)
        self.records['started'].append((self.Proc_name, mode))
        return FakeProcess(self)

    def on_parent_terminate(self):
        self.records['parent_terminated'].append(self.Proc_name)

    def commit_accounts(self, request_id, models):
        self.commit_calls.append((request_id, models))
        return True

    def log(self, level, message, segment=None):
        self.records['logs'].append((level, message))


class FakeRuntimeRecords:
    '''记录单次 boot 测试创建的对象，避免测试夹具间泄漏。'''

    current = {
        'instances': [],
        'constructed': [],
        'started': [],
        'terminated': [],
        'parent_terminated': [],
        'logs': [],
        'lifecycle': [],
    }


def make_proc_factory(proc_type, records):
    '''为某个 boot 分支创建符合预期类型的构造器类。'''

    class Factory(FakeProc):
        default_type = proc_type

    def constructor(*args, **kwargs):
        kwargs['_records'] = records
        return Factory(*args, **kwargs)

    return constructor


def make_boot_bot():
    '''返回一个启用的 OneBot 反向 WebSocket 账号。'''

    bot = OlivOS.API.bot_info_T(
        id=10001,
        server_type='websocket',
        host='ws://127.0.0.1',
        port=5700,
        access_token='fixture-token',
        platform_sdk='onebot',
        platform_platform='qq',
        platform_model='default',
    )
    bot.enable = True
    return bot


def make_boot_config():
    '''构造覆盖被测非 GUI 核心模型分支的最小配置。'''

    return {
        'system': {
            'name': 'OlivOS-fixture',
            'interval': 0.001,
            'proc_mode': 'auto',
            'control_queue': 'control',
            'init': ['logger', 'accounts', 'plugin', 'webui', 'link'],
            'event': {'ready': ['plugin']},
            'type_event': {'shutdown': ['onebotV11_link']},
        },
        'queue': ['control', 'logger_rx', 'plugin_rx', 'webui_rx', 'link_tx'],
        'models': {
            'logger': {
                'enable': True,
                'name': 'logger',
                'type': 'logger',
                'interval': 0.001,
                'dead_interval': 1,
                'proc_mode': 'processing',
                'rx_queue': 'logger_rx',
                'control_queue': 'control',
                'mode': 1,
                'fliter': 0,
            },
            'accounts': {
                'enable': True,
                'name': 'accounts',
                'type': 'account_config_safe',
                'proc_mode': 'auto',
                'logger_proc': 'logger',
                'data': {'path': './conf/account.json'},
            },
            'plugin': {
                'enable': True,
                'name': 'plugin',
                'type': 'plugin',
                'interval': 0.001,
                'dead_interval': 1,
                'proc_mode': 'auto',
                'rx_queue': 'plugin_rx',
                'tx_queue': ['link_tx'],
                'control_queue': 'control',
                'logger_proc': 'logger',
                'debug': False,
                'treading_mode': True,
                'restart_gate': None,
                'enable_auto_restart': True,
            },
            'webui': {
                'enable': True,
                'name': 'webui',
                'type': 'webUI',
                'interval': 0.001,
                'dead_interval': 1,
                'proc_mode': 'threading',
                'rx_queue': 'webui_rx',
                'control_queue': 'control',
                'logger_proc': 'logger',
                'server': {'host': '127.0.0.1', 'port': 0},
            },
            'link': {
                'enable': True,
                'name': 'link',
                'type': 'onebotV11_link',
                'interval': 0.001,
                'dead_interval': 0.01,
                'proc_mode': 'webUI',
                'rx_queue': 'link_rx',
                'tx_queue': 'link_tx',
                'logger_proc': 'logger',
                'debug': False,
            },
            'OlivOS_account_config': {'data': {'path': './conf/account.json'}},
        },
    }


def install_boot_harness(monkeypatch):
    '''替换 boot 依赖并返回测试可检查的对象集合。'''

    boot = OlivOS.bootAPI
    records = {
        'instances': [],
        'constructed': [],
        'started': [],
        'terminated': [],
        'parent_terminated': [],
        'logs': [],
        'lifecycle': [],
    }
    FakeRuntimeRecords.current = records
    bot = make_boot_bot()
    config = make_boot_config()
    control_queue = ScriptedControlQueue()
    accounts = {bot.hash: bot}
    account_calls = []

    def load_accounts(path, logger_proc=None, safe_mode=False):
        account_calls.append((path, logger_proc, safe_mode))
        return accounts

    monkeypatch.setattr(boot.multiprocessing, 'Queue', MemoryQueue)
    monkeypatch.setattr('builtins.print', lambda *args, **kwargs: None)
    monkeypatch.setattr(boot.atexit, 'register', lambda *args, **kwargs: None)
    monkeypatch.setattr(boot, 'preLoadPrint', lambda *args, **kwargs: None)
    monkeypatch.setattr(boot, 'setSplashClose', lambda: None)
    monkeypatch.setattr(boot, 'killMain', lambda: records['logs'].append((5, 'killMain')))
    monkeypatch.setattr(OlivOS.webUI.resourceAPI, 'reset_cache', lambda *args, **kwargs: None)
    monkeypatch.setattr(OlivOS.webUI.serverAPI, 'forward_packet', lambda *args, **kwargs: None)

    def control_factory(**kwargs):
        return FakeControl(queue_obj=control_queue, **kwargs)

    control_factory.packet = Packet
    monkeypatch.setattr(OlivOS.API, 'Control', control_factory)
    monkeypatch.setattr(OlivOS.diagnoseAPI, 'logger', make_proc_factory('logger', records))
    monkeypatch.setattr(OlivOS.pluginAPI, 'shallow', make_proc_factory('plugin', records))
    monkeypatch.setattr(OlivOS.onebotV11LinkServerAPI, 'server', make_proc_factory('onebotV11_link', records))
    monkeypatch.setattr(OlivOS.webUI.serverAPI, 'server', make_proc_factory('webUI', records))
    monkeypatch.setattr(OlivOS.accountAPI.Account, 'load', load_accounts)
    monkeypatch.setattr(OlivOS.accountAPI.Account, 'getEnabledAccountData', lambda data: data)
    original_lifecycle = boot.request_plugin_lifecycle

    def trace_lifecycle(proc, action, started_at=None):
        records['lifecycle'].append((proc.Proc_name, action, proc.Proc_info.rx_queue))
        return original_lifecycle(proc, action, started_at)

    monkeypatch.setattr(boot, 'request_plugin_lifecycle', trace_lifecycle)

    return SimpleNamespace(
        boot=boot,
        bot=bot,
        config=config,
        accounts=accounts,
        account_calls=account_calls,
        control_queue=control_queue,
        records=records,
        packet=Packet,
    )
