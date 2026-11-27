# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/pluginAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

import platform
import threading
import time
import sys
import importlib.util
import os
import json
import traceback
import shutil
import tempfile
from contextlib import ExitStack
from pathlib import Path
from queue import Empty
from types import ModuleType
from uuid import uuid4

if platform.system() == 'Windows':
    import tkinter

import OlivOS
from OlivOS.core.core import API, opkAPI, tkBridgeAPI
from OlivOS.core.core.pluginSchedule import PluginSchedule

modelName = 'pluginAPI'
_SCHEDULE_OPERATIONS = {'restart_do': 'restart', 'update_hit': 'update', 'plugin_stop': 'stop'}

gProc = None

plugin_priority_path = './conf/plugin_priority.json'
plugin_priority_default = 10000

gPluginPriorityLock = threading.RLock()


def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def removeDir(dir_path):
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
    except Exception:
        pass


def doOpkRemove(plugin_path, plugin_dir):
    if len(plugin_dir) > 4:
        if plugin_dir[-4:] == '.opk':
            removeDir(plugin_path + plugin_dir[:-4])


def _discard_list_item(sequence, item):
    try:
        sequence.remove(item)
    except ValueError:
        pass


def load_plugin_priority(path=None, root='.'):
    """
    读取用户优先级覆盖配置，缺省路径为 conf/plugin_priority.json。

    配置文件是纯增量：只需要写被用户调整过的插件，未写到的插件
    完全使用 app.json 中的默认优先级；文件缺失或损坏时视为没有覆盖。

    Returns:
        dict: {namespace: priority}
    """
    priority_path = plugin_priority_path if path is None else path
    if not os.path.isabs(priority_path):
        priority_path = os.path.join(root, priority_path)
    res = {}
    try:
        with open(priority_path, 'r', encoding='utf-8') as priority_file:
            plugins = json.loads(priority_file.read()).get('plugins', {})
        for namespace_this in plugins:
            entry_this = plugins[namespace_this]
            if type(entry_this) is dict:
                entry_this = entry_this.get('priority')
            if type(entry_this) is int and entry_this >= 0:
                res[namespace_this] = entry_this
    except Exception:
        # traceback.print_exc()
        return res
    return res


def build_plugin_call_order(plugin_models_dict, overrides=None):
    """
    计算生效优先级与插件调用顺序，并把结果写回插件元数据。

    排序键始终是 (生效优先级, namespace)：生效优先级 = 用户覆盖值（若有）
    否则 app.json 默认值。
    没有任何覆盖时，结果与历史排序 (priority, namespace) 完全一致。

    Returns:
        list: 按生效优先级升序排列的 namespace 列表
    """
    if overrides is None:
        overrides = {}
    order_list = []
    for plugin_models_index_this in plugin_models_dict:
        plugin_models_this = plugin_models_dict[plugin_models_index_this]
        namespace_this = plugin_models_this.get('namespace', plugin_models_index_this)
        priority_default_this = plugin_models_this.get('priority', plugin_priority_default)
        if isinstance(priority_default_this, bool) or not isinstance(priority_default_this, (int, float)):
            priority_default_this = plugin_priority_default
        priority_user_this = overrides.get(namespace_this)
        if type(priority_user_this) is not int or priority_user_this < 0:
            priority_user_this = None
        priority_effective_this = priority_default_this
        if priority_user_this is not None:
            priority_effective_this = priority_user_this
        plugin_models_this['priority_default'] = priority_default_this
        plugin_models_this['priority_user'] = priority_user_this
        plugin_models_this['priority_effective'] = priority_effective_this
        order_list.append((priority_effective_this, namespace_this))
    order_list.sort()
    return [item_this[1] for item_this in order_list]


plugin_path = './plugin/app/'
plugin_path_tmp = './plugin/tmp/'
releaseDir(plugin_path)
sys.path.append(plugin_path)
releaseDir(plugin_path_tmp)
sys.path.append(plugin_path_tmp)
releaseDir('./lib/Lib')
sys.path.append('./lib/Lib')
releaseDir('./lib/DLLs')
sys.path.append('./lib/DLLs')


def parse_restart_at(value):
    """把配置里的定时重载时间点规范成 {'HH:MM'} 集合。

    只接受 24 小时制 'HH:MM' 字符串，非法项一律丢弃；返回值可为空集，
    表示不启用定时重载。配置写错不应导致组件启动失败。
    """
    if type(value) is not list:
        return set()
    result = set()
    for item in value:
        if type(item) is not str:
            continue
        parts = item.strip().split(':')
        if len(parts) != 2:
            continue
        hour_text, minute_text = parts
        if not (1 <= len(hour_text) <= 2 and len(minute_text) == 2):
            continue
        if not (hour_text.isdigit() and minute_text.isdigit()):
            continue
        hour, minute = int(hour_text), int(minute_text)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            result.add('%02d:%02d' % (hour, minute))
    return result


def parse_restart_interval(value):
    """把滚动重载周期（分钟）换算成秒。

    关闭（0/负数）或非法值返回 0；低于 6 分钟视为非法，避免把加载器当节拍器。
    """
    if type(value) is bool or type(value) not in (int, float):
        return 0
    if value <= 0:
        return 0
    seconds = float(value) * 60
    if seconds < 360:
        return 0
    return seconds


class _PluginFinder:
    """让插件之间的导入使用本次入选副本，而非同名源码或其他 OPK。"""

    def __init__(self, plugins):
        self.roots = {}
        for plugin in plugins:
            self.roots.setdefault(plugin['module_name'], plugin['plugin_root'])

    def find_spec(self, fullname, path=None, target=None):
        root = self.roots.get(fullname)
        if root is None:
            return None
        entry = os.path.join(root, '__init__.py')
        if not os.path.isfile(entry):
            raise ImportError(f'{fullname}.__init__ not found')
        return importlib.util.spec_from_file_location(fullname, entry, submodule_search_locations=[root])


class shallow(API.Proc_templet):
    def __init__(self, Proc_name='native_plugin', scan_interval=0.001, dead_interval=1, rx_queue=None, tx_queue=None,
                 control_queue=None, logger_proc=None, debug_mode=False, plugin_func_dict=None, bot_info_dict=None,
                 treading_mode='full', restart_gate=10000, enable_auto_restart=False, enable_gui=True,
                 restart_at=None, restart_interval_minutes=0):
        API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='plugin',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            control_queue=control_queue,
            logger_proc=logger_proc
        )
        if bot_info_dict is None:
            bot_info_dict = {}
        if plugin_func_dict is None:
            plugin_func_dict = {}
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_config['enable_gui'] = enable_gui
        self.Proc_config['treading_mode'] = treading_mode
        self.Proc_config['shallow_dict'] = {}
        self.Proc_config['ready_for_restart'] = False
        self.Proc_config['enable_auto_restart'] = enable_auto_restart
        self.Proc_config['step_to_restart'] = restart_gate
        self.Proc_config['restart_at'] = parse_restart_at(restart_at)
        self.Proc_config['restart_interval'] = parse_restart_interval(restart_interval_minutes)
        self.Proc_data['restart_at_last'] = None
        self.Proc_data['restart_interval_base'] = None
        self.Proc_data['plugin_func_dict'] = plugin_func_dict
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['main_tk'] = None
        self.plugin_models_dict = {}
        self.plugin_shadowed_list = []
        self.plugin_models_call_list = []
        self.tx_queue = []
        self.menu_queue = []
        self.database: OlivOS.userModule.UserConfDB.DataBaseAPI = None
        # 进程启动前只分配可序列化的标识；线程、调度器和锁在子进程创建。
        self.schedule_generation = uuid4().hex
        self._schedule = None
        self._schedule_lifecycle = None

    class rx_packet(object):
        def __init__(self, sdk_event):
            self.sdk_event = sdk_event

    def get_plugin_event_context(self, plugin_identity):
        if plugin_identity is None:
            return None
        plugin_identity = str(plugin_identity)
        plugin_models = list(self.plugin_models_dict.values())

        plugin_model = self.plugin_models_dict.get(plugin_identity)
        if plugin_model is None:
            namespace_matches = [
                model_this
                for model_this in plugin_models
                if str(model_this.get('namespace', '')) == plugin_identity
            ]
            if len(namespace_matches) == 1:
                plugin_model = namespace_matches[0]
        if plugin_model is None:
            name_matches = [
                model_this
                for model_this in plugin_models
                if str(model_this.get('name', '')) == plugin_identity
            ]
            if len(name_matches) == 1:
                plugin_model = name_matches[0]
        if plugin_model is None:
            module_matches = [
                model_this
                for model_this in plugin_models
                if str(model_this.get('module_name', '')) == plugin_identity
            ]
            if len(module_matches) == 1:
                plugin_model = module_matches[0]
        if plugin_model is None:
            return None
        return {
            'namespace': plugin_model.get('namespace'),
            'message_mode': plugin_model.get(
                'message_mode',
                OlivOS.infoAPI.OlivOS_message_mode_tx_default
            )
        }

    def __init_GUI(self):
        if platform.system() == 'Windows':
            self.Proc_data['main_tk'] = tkinter.Tk()
            self.Proc_data['main_tk'].withdraw()
            self.Proc_data['main_tk'].iconbitmap('./resource/tmp_favoricon.ico')
            self._tk_bridge.start(self.Proc_data['main_tk'])
            if self.Proc_data.get('tk_bridge_plugins_ready') and not self.Proc_config['ready_for_restart']:
                self._send_tk_bridge({'action': 'tk_bridge_status', 'data': self._tk_bridge.metadata()})
            self.__update_GUI()
            self.Proc_data['main_tk'].mainloop()

    def __update_GUI(self):
        if platform.system() == 'Windows':
            self.Proc_data['main_tk'].after(50, self.__update_GUI)
            if len(self.menu_queue) > 0:
                rx_packet_data = self.menu_queue.pop(0)
                self.run_plugin(rx_packet_data)

    def run(self):
        OlivOS.pluginAPI.gProc = self
        OlivOS.statisticsAPI.bind_control_queue(self.Proc_info.control_queue)
        profile_error = None
        try:
            tk_panels = tkBridgeAPI.load_panels('.')
        except ValueError as error:
            profile_error = str(error)
            self.log(3, profile_error)
            tk_panels = ()
        self._tk_bridge = tkBridgeAPI.TkBridge(lambda: self.plugin_models_dict, self._send_tk_bridge,
                                               proc=self, panels=tk_panels, profile_error=profile_error)
        if any(bot.platform.get('sdk') == 'qqGuildv2_link'
               for bot in self.Proc_data['bot_info_dict'].values()):
            try:
                from OlivOS.adapter.qqGuild import qqGuildv2Store
                qqGuildv2Store.open_db()
                threading.Thread(target=OlivOS.qqGuildv2SDK.init_qq_bot_self,
                                 args=(self.Proc_data['bot_info_dict'],), daemon=True).start()
            except Exception:
                self.log(4, 'QQ 群成员缓存初始化失败: %s' % traceback.format_exc())
        self.Proc_data['webui_load_started'] = time.time()
        self.sendPluginList()
        releaseDir('./plugin')
        releaseDir('./plugin/app')
        releaseDir('./plugin/conf')
        releaseDir('./plugin/data')
        releaseDir('./plugin/tmp')
        releaseDir('./lib')
        releaseDir('./lib/Lib')
        releaseDir('./lib/DLLs')
        releaseDir('./data')
        releaseDir('./data/images')
        releaseDir('./data/videos')
        releaseDir('./data/audios')
        releaseDir('./data/files')
        if self.Proc_config['enable_gui']:
            threading.Thread(target=self.__init_GUI).start()
        # self.set_check_update()
        time.sleep(1)  # 此处延迟用于在终端第一次启动时等待终端初始化，避免日志丢失，后续需要用异步(控制包流程)方案替代
        self.database = (
            OlivOS.userModule.UserConfDB.DataBaseAPI(self.log, max_thread=None, timeout=self.Proc_info.dead_interval)
        )
        self.load_plugin_list()
        self.check_plugin_list()
        self.run_plugin_func(None, 'init_after')
        self._schedule = PluginSchedule(self, self.schedule_generation)
        schedule_status = self._schedule.start(self.plugin_models_dict.values())
        self._send_schedule_event('plugin_schedule_status', schedule_status)
        self.log(2, OlivOS.L10NAPI.getTrans('OlivOS plugin shallow [{0}] is running', [self.Proc_name], modelName))
        self.Proc_data['tk_bridge_plugins_ready'] = True
        self.sendPluginList(ready=True)
        self.Proc_data['restart_interval_base'] = time.monotonic()
        self.Proc_data['restart_at_last'] = time.strftime('%Y-%m-%d %H:%M')
        rx_count = 0
        idle_check_at = 0.0
        while True:
            rx_packet_data = None
            if not self.Proc_config['ready_for_restart']:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get_nowait()
                except Empty:
                    pass
            # 先处理已取到的生命周期指令，再允许待处理的定时事件进池。
            if type(rx_packet_data) is API.Control.packet:
                operation = _SCHEDULE_OPERATIONS.get(rx_packet_data.action)
                if operation is not None:
                    generation = getattr(rx_packet_data, 'schedule_generation', self.schedule_generation)
                    if generation != self.schedule_generation:
                        continue
                    self._request_schedule_lifecycle(operation, rx_packet_data.key)
                    if self._advance_schedule_lifecycle() == 'timeout':
                        rx_count = 0
                    continue
            if self._advance_schedule_lifecycle() == 'timeout':
                rx_count = 0
            timer_work = self._schedule.dispatch()
            if rx_packet_data is None:
                OlivOS.statisticsAPI.flush_traffic()
                if not timer_work:
                    time.sleep(self.Proc_info.scan_interval)
                if (
                    self.Proc_config['enable_auto_restart']
                    and (self.Proc_config['restart_at'] or self.Proc_config['restart_interval'] > 0)
                ):
                    now = time.monotonic()
                    if now - idle_check_at >= 1.0:
                        idle_check_at = now
                        self._check_restart_schedule()
                continue
            if self.Proc_config['ready_for_restart']:
                continue
            if type(rx_packet_data) is API.Control.packet:
                if rx_packet_data.action == 'send':
                    webui_event = rx_packet_data.key.get('data', {}).get('webui')
                    if webui_event or platform.system() != 'Windows' or not self.Proc_config['enable_gui']:
                        self.run_plugin(rx_packet_data)
                    else:
                        self.menu_queue.append(rx_packet_data)
            elif self.Proc_config['treading_mode'] == 'none':
                self.run_plugin(rx_packet_data.sdk_event)
            elif self.Proc_config['treading_mode'] == 'full':
                threading.Thread(target=self.run_plugin, args=(rx_packet_data.sdk_event,)).start()
            if self.Proc_config['enable_auto_restart'] and self._schedule_lifecycle is None:
                rx_count += 1
                if rx_count == self.Proc_config['step_to_restart']:
                    self.set_restart()
                elif self.Proc_config['restart_at'] or self.Proc_config['restart_interval'] > 0:
                    self._check_restart_schedule()

    def _send_tk_bridge(self, data):
        self.sendControlEvent('send', {'target': {'type': 'webUI'}, 'data': data})

    def _send_schedule_event(self, action, data):
        packet = {'target': {'type': 'webUI'}, 'data': {'action': action, 'data': data}}
        if action == 'plugin_schedule_status':
            packet['schedule_source'] = {'name': self.Proc_name, 'generation': self.schedule_generation}
        self.sendControlEvent('send', packet)

    def _request_schedule_lifecycle(self, operation, key):
        request = key if isinstance(key, dict) else {}
        if request.get('generation', self.schedule_generation) != self.schedule_generation:
            return
        request = {'name': self.Proc_name, 'generation': self.schedule_generation,
                   'operation': operation, 'started_at': request.get('started_at')}
        if self._schedule_lifecycle is not None:
            self._reject_schedule_lifecycle(request, 'busy', self._schedule.running_tasks())
            return
        self._schedule.close_gate()
        self._schedule_lifecycle = request, time.monotonic() + self.Proc_info.dead_interval

    def _reject_schedule_lifecycle(self, request, reason, running):
        tasks = [{'namespace': namespace, 'task_id': task_id} for namespace, task_id in running]
        self.log(3, f'Plugin schedule {request["operation"]} rejected ({reason}): {running}')
        self.sendControlEvent('plugin_lifecycle_rejected', dict(request, reason=reason))
        self._send_schedule_event('plugin_schedule_lifecycle_rejected', {
            'operation': request['operation'], 'reason': reason, 'tasks': tasks, 'started_at': request['started_at'],
        })

    def _advance_schedule_lifecycle(self):
        if self._schedule_lifecycle is None:
            return
        request, deadline = self._schedule_lifecycle
        if request is None:
            if not self._schedule.running_tasks():
                self._schedule.recover()
                self._schedule_lifecycle = None
                self.Proc_data['restart_interval_base'] = time.monotonic()
            return
        now = time.monotonic()
        running, finished_late = self._schedule.drain_state(deadline)
        if finished_late or (running and now >= deadline):
            self._schedule_lifecycle = None, None
            self._reject_schedule_lifecycle(request, 'timeout', sorted(set(running) | set(finished_late)))
            return 'timeout'
        if running:
            return
        self._schedule.shutdown()
        self.Proc_config['ready_for_restart'] = True
        self._schedule_lifecycle = None
        bridge = getattr(self, '_tk_bridge', None)
        if bridge is not None:
            bridge.stop()
            self._send_tk_bridge({'action': 'tk_bridge_status', 'data': bridge.metadata()})
            if not bridge.cleaned.wait(self.Proc_info.dead_interval):
                self.log(3, 'Tk 桥接清理尚未确认，即将关闭插件加载器')
        self.run_plugin_func(None, 'save')
        self.database.stop()
        action = 'restart_do' if request['operation'] == 'restart' else 'plugin_lifecycle_complete'
        self.sendControlEvent(action, request)
        self.log(2, f'Plugin loader [{self.Proc_name}] ready for {request["operation"]}')

    def on_control_rx(self, packet):
        if type(packet) is API.Control.packet:
            if 'send' == packet.action:
                if (
                    type(packet.key) is dict
                    and 'data' in packet.key
                    and type(packet.key['data'])
                    and 'action' in packet.key['data']
                ):
                    if 'account_update' == packet.key['data']['action']:
                        self.set_restart()
                    elif 'plugin_priority_reload' == packet.key['data']['action']:
                        self.apply_plugin_priority()
                    elif packet.key['data']['action'] == 'tk_bridge_request':
                        bridge = getattr(self, '_tk_bridge', None)
                        if bridge is not None:
                            bridge.submit(packet.key['data'])

    def _check_restart_schedule(self):
        """按「定时点 → 滚动周期」的顺序检查自动重载，命中一次即返回。

        定时点用墙钟判定（错过窗口就不再补），滚动周期用 monotonic 差值判定
        （迟到必补）。两者都受 enable_auto_restart 总闸约束。
        """
        if not self.Proc_config['enable_auto_restart']:
            return False
        if self.Proc_config['ready_for_restart'] or self._schedule_lifecycle is not None:
            return False
        if self.Proc_config['restart_at']:
            slot = time.strftime('%H:%M')
            if slot in self.Proc_config['restart_at']:
                stamp = time.strftime('%Y-%m-%d ') + slot
                if stamp != self.Proc_data['restart_at_last']:
                    self.Proc_data['restart_at_last'] = stamp
                    self.log(2, OlivOS.L10NAPI.getTrans(
                        'OlivOS plugin shallow [{0}] reached scheduled time [{1}], restarting',
                        [self.Proc_name, slot], modelName))
                    self.set_restart()
                    return True
        interval = self.Proc_config['restart_interval']
        if interval > 0 and self.Proc_data['restart_interval_base'] is not None:
            elapsed = time.monotonic() - self.Proc_data['restart_interval_base']
            if elapsed >= interval:
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS plugin shallow [{0}] ran {1} min, reached restart interval {2} min, restarting',
                    [self.Proc_name, int(elapsed // 60), self.Proc_config['restart_interval'] / 60],
                    modelName))
                self.set_restart()
                return True
        return False

    def set_restart(self):
        """重载插件

        该接口可以重启整个插件加载器，并重新加载这个插件。
        """
        self.log(2, OlivOS.L10NAPI.getTrans(
            'OlivOS plugin shallow [{0}] call restart', [
                self.Proc_name
            ],
            modelName
        ))
        packet = API.Control.packet('restart_do', self.Proc_name)
        packet.schedule_generation = self.schedule_generation
        self.Proc_info.rx_queue.put(packet, block=False)

    def set_check_update(self):
        self.log(2, OlivOS.L10NAPI.getTrans(
            'OlivOS plugin shallow [{0}] call check update', [
                self.Proc_name
            ],
            modelName
        ))
        self.Proc_info.control_queue.put(API.Control.packet('init_type', 'update_get'), block=False)

    def get_plugin_list(self):
        """获取插件列表

        该接口可以获得一个由插件的`namespace`填充的`list`，这可以让你知道当前的`OlivOS`上存在哪些插件。

        Returns:
            list: 插件列表，Defaults to []
        """
        return self.plugin_models_call_list

    def get_main_root(self):
        return self.Proc_data['main_tk']

    def run_plugin(self, sdk_event):
        # plugin_event = API.Event(sdk_event=sdk_event, log_func=self.log, Proc=self)
        plugin_event = API.Event(sdk_event=sdk_event)
        func_type = plugin_event.plugin_info.get('func_type')
        if func_type is not None:
            OlivOS.statisticsAPI.record_event_type(func_type)
        plugin_event_bot_hash = API.getBotHash(
            bot_id=plugin_event.base_info['self_id'],
            platform_sdk=plugin_event.platform['sdk'],
            platform_platform=plugin_event.platform['platform'],
            platform_model=plugin_event.platform['model']
        )
        if plugin_event.active:
            if plugin_event_bot_hash in self.Proc_data['bot_info_dict']:
                plugin_event.bot_info = self.Proc_data['bot_info_dict'][plugin_event_bot_hash]
            elif plugin_event.plugin_info['func_type'] in ['menu']:
                pass
            else:
                self.log(3, OlivOS.L10NAPI.getTrans(
                    'Account [{0}] not found, please check your account config', [
                        str(plugin_event.base_info['self_id'])
                    ],
                    modelName
                ))
                plugin_event.active = False
        if plugin_event.active:
            plugin_event.plugin_info['tx_queue'] = self.Proc_info.tx_queue
            plugin_event.plugin_info['control_queue'] = self.Proc_info.control_queue
            for plugin_models_index_this in self.plugin_models_call_list:
                flag_support_found_dict = {}
                flag_support_found_dict['sdk'] = False
                flag_support_found_dict['platform'] = False
                flag_support_found_dict['model'] = False
                flag_support_found_dict['flag'] = False
                for plugin_model_support_this in self.plugin_models_dict[plugin_models_index_this]['support']:
                    if plugin_event.platform['sdk'] == 'all':
                        flag_support_found_dict['sdk'] = True
                    elif plugin_model_support_this['sdk'] == 'all':
                        flag_support_found_dict['sdk'] = True
                    elif plugin_model_support_this['sdk'] == plugin_event.platform['sdk']:
                        flag_support_found_dict['sdk'] = True
                    if plugin_event.platform['platform'] == 'all':
                        flag_support_found_dict['platform'] = True
                    elif plugin_model_support_this['platform'] == 'all':
                        flag_support_found_dict['platform'] = True
                    elif plugin_model_support_this['platform'] == plugin_event.platform['platform']:
                        flag_support_found_dict['platform'] = True
                    if plugin_event.platform['model'] == 'all':
                        flag_support_found_dict['model'] = True
                    elif plugin_model_support_this['model'] == 'all':
                        flag_support_found_dict['model'] = True
                    elif plugin_model_support_this['model'] == plugin_event.platform['model']:
                        flag_support_found_dict['model'] = True
                    if flag_support_found_dict['sdk'] and flag_support_found_dict['platform'] and \
                            flag_support_found_dict['model']:
                        flag_support_found_dict['flag'] = True
                if flag_support_found_dict['flag']:
                    plugin_event.plugin_info['name'] = self.plugin_models_dict[plugin_models_index_this]['name']
                    plugin_event.plugin_info['namespace'] = self.plugin_models_dict[plugin_models_index_this][
                        'namespace']
                    if 'compatible_svn' in self.plugin_models_dict[plugin_models_index_this]:
                        plugin_event.plugin_info['compatible_svn'] = (
                            self.plugin_models_dict[plugin_models_index_this]['compatible_svn']
                        )
                    else:
                        plugin_event.plugin_info['compatible_svn'] = OlivOS.infoAPI.OlivOS_compatible_svn_default
                    if 'message_mode' in self.plugin_models_dict[plugin_models_index_this]:
                        plugin_event.plugin_info['message_mode_tx'] = self.plugin_models_dict[plugin_models_index_this][
                            'message_mode']
                    else:
                        plugin_event.plugin_info['message_mode_tx'] = OlivOS.infoAPI.OlivOS_message_mode_tx_default
                    plugin_event.get_Event_on_Plugin()
                    self.plugin_event_router(plugin_event, self.plugin_models_dict[plugin_models_index_this]['model'],
                                             plugin_models_index_this)
                    self.log(0, OlivOS.L10NAPI.getTrans(
                        'event [{0}] call plugin [{1}] done', [
                            str(plugin_event.plugin_info['func_type']),
                            self.plugin_models_dict[plugin_models_index_this]['name']
                        ],
                        modelName
                    ))
                if plugin_event.blocked:
                    self.log(2, OlivOS.L10NAPI.getTrans(
                        'event [{0}] call blocked by plugin [{1}]', [
                            str(plugin_event.plugin_info['func_type']),
                            self.plugin_models_dict[plugin_models_index_this]['name']
                        ],
                        modelName
                    ))
                    break
        return

    def plugin_event_router(self, plugin_event, plugin_model, plugin_name):
        if hasattr(plugin_model.main.Event, plugin_event.plugin_info['func_type']):
            try:
                if plugin_event.plugin_info['func_type'] == 'private_message':
                    plugin_model.main.Event.private_message(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'private_message_sent':
                    plugin_model.main.Event.private_message_sent(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_message':
                    plugin_model.main.Event.group_message(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_message_sent':
                    plugin_model.main.Event.group_message_sent(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_file_upload':
                    plugin_model.main.Event.group_file_upload(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_admin':
                    plugin_model.main.Event.group_admin(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_member_decrease':
                    plugin_model.main.Event.group_member_decrease(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_member_increase':
                    plugin_model.main.Event.group_member_increase(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_ban':
                    plugin_model.main.Event.group_ban(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_message_recall':
                    plugin_model.main.Event.group_message_recall(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'private_message_recall':
                    plugin_model.main.Event.private_message_recall(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'poke':
                    plugin_model.main.Event.poke(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'button_click':
                    plugin_model.main.Event.button_click(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_lucky_king':
                    plugin_model.main.Event.group_lucky_king(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_honor':
                    plugin_model.main.Event.group_honor(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'friend_add':
                    plugin_model.main.Event.friend_add(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'friend_add_request':
                    plugin_model.main.Event.friend_add_request(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_add_request':
                    plugin_model.main.Event.group_add_request(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_invite_request':
                    plugin_model.main.Event.group_invite_request(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'lifecycle':
                    plugin_model.main.Event.lifecycle(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'heartbeat':
                    plugin_model.main.Event.heartbeat(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'menu':
                    plugin_model.main.Event.menu(plugin_event=plugin_event, Proc=self)
            except Exception as e:
                # traceback.print_exc()
                self.log(4, OlivOS.L10NAPI.getTrans(
                    'OlivOS plugin [{0}] call [{1}] failed: {2}\n{3}', [
                        plugin_name,
                        plugin_event.plugin_info['func_type'],
                        str(e),
                        traceback.format_exc()
                    ],
                    modelName
                ))
                OlivOS.statisticsAPI.record_failed()
                plugin_event.set_block()
        return

    def check_plugin_list(self):
        new_list = []
        for plugin_models_index_this in self.plugin_models_call_list:
            if plugin_models_index_this in self.plugin_models_dict:
                new_list.append(plugin_models_index_this)
            else:
                self.log(4, OlivOS.L10NAPI.getTrans(
                    'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}', [
                        plugin_models_index_this,
                        self.Proc_name,
                        'namespace failed'
                    ],
                    modelName
                ))
        self.plugin_models_call_list = new_list

    def apply_plugin_priority(self, overrides=None):
        """
        重算插件调用顺序。

        只替换 `plugin_models_call_list`，不会重新导入插件模块、不改变导入顺序；
        `overrides=None` 时从 conf/plugin_priority.json 重新读取。

        Args:
            overrides (dict|None): {namespace: priority}，None 表示重新读取文件

        Returns:
            list: 新的调用顺序（namespace 列表）
        """
        if overrides is None:
            overrides = load_plugin_priority()
        with gPluginPriorityLock:
            old_order_list = list(self.plugin_models_call_list)
            self.plugin_models_call_list = build_plugin_call_order(self.plugin_models_dict, overrides)
        if old_order_list != self.plugin_models_call_list:
            old_index_dict = {}
            for index_this, namespace_this in enumerate(old_order_list):
                old_index_dict[namespace_this] = index_this
            detail_list = []
            for index_this, namespace_this in enumerate(self.plugin_models_call_list):
                if old_index_dict.get(namespace_this) != index_this:
                    detail_list.append('%s %s->%s' % (
                        namespace_this,
                        old_index_dict.get(namespace_this, '?'),
                        index_this
                    ))
            self.log(2, OlivOS.L10NAPI.getTrans(
                'OlivOS plugin shallow [{0}] priority order applied: {1}', [
                    self.Proc_name,
                    ', '.join(detail_list[:20])
                ],
                modelName
            ))
        self.sendPluginList(priority_only=True)
        return self.plugin_models_call_list

    def run_plugin_data_release(self):
        for plugin_models_index_this in self.plugin_models_call_list:
            if plugin_models_index_this in self.plugin_models_dict:
                self.run_plugin_data_release_by_name(plugin_models_index_this)

    def run_plugin_data_release_by_name(self, plugin_models_index_this):
        from OlivOS.webUI import resourceAPI

        plugin = self.plugin_models_dict[plugin_models_index_this]
        data_from = Path(plugin['plugin_root']) / 'data'
        if not data_from.is_dir():
            return
        data_path = Path('plugin/data') / plugin_models_index_this / 'data'
        try:
            # 仅从入选副本释放资源，合并而不删除运行数据或跟随目标目录内的链接。
            for target in (data_path.parent, data_path):
                try:
                    linked = resourceAPI.is_link(target)
                except FileNotFoundError:
                    break
                if linked:
                    raise ValueError(f'Data destination must not be a link: {target}')
            for directory, subdirectories, files in os.walk(data_path):
                for name in subdirectories + files:
                    target = Path(directory) / name
                    if resourceAPI.is_link(target):
                        raise ValueError(f'Data destination must not be a link: {target}')
            shutil.copytree(data_from, data_path, dirs_exist_ok=True)
        except (OSError, ValueError) as error:
            self.log(4, OlivOS.L10NAPI.getTrans(
                'OlivOS plugin [{0}] call [{1}] failed: {2}\n{3}',
                [plugin['name'], 'release_data', str(error), traceback.format_exc()], modelName
            ))
        else:
            self.log(2, OlivOS.L10NAPI.getTrans(
                'OlivOS plugin [{0}] call [{1}] done', [plugin['name'], 'release_data'], modelName
            ))

    def run_plugin_func(self, plugin_event, func_name):
        for plugin_models_index_this in self.plugin_models_call_list:
            if plugin_models_index_this in self.plugin_models_dict:
                try:
                    if hasattr(self.plugin_models_dict[plugin_models_index_this]['model'].main.Event, func_name):
                        getattr(self.plugin_models_dict[plugin_models_index_this]['model'].main.Event, func_name)(
                            plugin_event=plugin_event, Proc=self)
                        self.log(2, OlivOS.L10NAPI.getTrans(
                            'OlivOS plugin [{0}] call [{1}] done', [
                                self.plugin_models_dict[plugin_models_index_this]['name'],
                                func_name
                            ],
                            modelName
                        ))
                except Exception as e:
                    if func_name == 'init_after':
                        self.plugin_models_dict[plugin_models_index_this]['schedule_init_failed'] = True
                    # traceback.print_exc()
                    self.log(4, OlivOS.L10NAPI.getTrans(
                        'OlivOS plugin [{0}] call [{1}] failed: {2}\n{3}', [
                            self.plugin_models_dict[plugin_models_index_this]['name'],
                            func_name,
                            str(e),
                            traceback.format_exc()
                        ],
                        modelName
                    ))
            else:
                self.log(4, OlivOS.L10NAPI.getTrans(
                    'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}', [
                        plugin_models_index_this,
                        self.Proc_name,
                        'namespace failed'
                    ],
                    modelName
                ))
        return

    def sendPluginList(self, ready=False, priority_only=False):
        tmp_plugin_list_send = []
        tmp_plugin_dict_send = {}
        tmp_plugin_webui_send = []
        tmp_plugin_webui_roots = {}
        tmp_plugin_webui_paths = {}
        tmp_plugin_order_list = []
        tmp_plugin_priority_dict = {}
        tmp_plugin_source_dict = {}
        for plugin_models_index_this in self.plugin_models_call_list:
            if plugin_models_index_this in self.plugin_models_dict:
                plugin_models_this = self.plugin_models_dict[plugin_models_index_this]
                if 'source' in plugin_models_this:
                    tmp_plugin_source_dict[plugin_models_this['namespace']] = plugin_models_this['source']
                priority_default_this = plugin_models_this.get(
                    'priority_default',
                    plugin_models_this.get('priority', plugin_priority_default)
                )
                priority_user_this = plugin_models_this.get('priority_user')
                if type(priority_user_this) is not int or priority_user_this < 0:
                    priority_user_this = None
                priority_effective_this = plugin_models_this.get('priority_effective', priority_default_this)
                tmp_plugin_order_list.append(plugin_models_this['namespace'])
                tmp_plugin_priority_dict[plugin_models_this['namespace']] = {
                    'default': priority_default_this,
                    'user': priority_user_this,
                    'effective': priority_effective_this,
                    'source': 'user' if priority_user_this is not None else 'default'
                }
                webui_config = plugin_models_this.get('webui_config')
                if isinstance(webui_config, list):
                    for entry in webui_config:
                        if not isinstance(entry, dict) or not isinstance(entry.get('title'), str):
                            continue
                        if entry.get('type') not in ('iframe', 'link'):
                            continue
                        tmp_plugin_webui_send.append(dict(entry, namespace=plugin_models_this['namespace']))
                    tmp_plugin_webui_roots[plugin_models_this['namespace']] = plugin_models_this.get('webui_root', '')
                    tmp_plugin_webui_paths[plugin_models_this['namespace']] = plugin_models_this.get(
                        'webui_resources', []
                    )
                tmp_plugin_list_this = None
                if plugin_models_this['menu_config'] is not None:
                    plugin_models_this_menu = plugin_models_this['menu_config']
                    if type(plugin_models_this_menu) is list:
                        if len(plugin_models_this_menu) > 0:
                            tmp_plugin_list_this = []
                            for plugin_models_this_menu_this in plugin_models_this_menu:
                                tmp_plugin_list_this.append(
                                    [
                                        plugin_models_this_menu_this['title'],
                                        plugin_models_this['namespace'],
                                        plugin_models_this_menu_this['event']
                                    ]
                                )
                            if len(tmp_plugin_list_this) > 0:
                                tmp_plugin_list_send.append(
                                    [
                                        plugin_models_this['name'],
                                        tmp_plugin_list_this
                                    ]
                                )
                            else:
                                tmp_plugin_list_this = None
                tmp_plugin_dict_send[plugin_models_this['namespace']] = [
                    plugin_models_this['name'],
                    '%s(%s)' % (
                        str(plugin_models_this['version']),
                        str(plugin_models_this['svn'])
                    ),
                    plugin_models_this['author'],
                    tmp_plugin_list_this,
                    plugin_models_this['info'],
                    plugin_models_this.get('folder_path', ''),
                    priority_effective_this
                ]
        self.sendControlEvent('send', {
            'target': {
                'type': 'nativeWinUI'
            },
            'data': {
                'action': 'update_data',
                'data': {
                    'ready': ready,
                    'load_started': self.Proc_data.get('webui_load_started', 0),
                    'shallow_plugin_menu_list': tmp_plugin_list_send,
                    'shallow_plugin_data_dict': tmp_plugin_dict_send,
                    'shallow_plugin_source_dict': tmp_plugin_source_dict,
                    'shallow_plugin_shadowed_list': getattr(self, 'plugin_shadowed_list', []),
                    'shallow_plugin_order_list': tmp_plugin_order_list,
                    'shallow_plugin_priority_dict': tmp_plugin_priority_dict,
                    'shallow_plugin_webui_list': tmp_plugin_webui_send,
                    'shallow_plugin_webui_roots': tmp_plugin_webui_roots,
                    'shallow_plugin_webui_paths': tmp_plugin_webui_paths,
                    'tk_bridge': self._tk_bridge.metadata() if hasattr(self, '_tk_bridge') else None,
                    'priority_only': priority_only
                }
            }
        }
        )
        self.sendControlEvent('send', {
            'target': {
                'type': 'nativeWinUI'
            },
            'data': {
                'action': 'start_shallow'
            }
        }
        )

    def sendControlEvent(self, action, data):
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                API.Control.packet(
                    action,
                    data
                ),
                block=False
            )

    def find_plugins_recursive(self, base_path, current_path='', depth=0, max_depth=10):
        """
        递归查找插件目录
        base_path: 基础路径
        current_path: 当前相对路径
        depth: 当前递归深度
        max_depth: 最大递归深度

        return 插件路径列表
        """
        if depth > max_depth:
            return []

        plugin_list = []
        full_path = os.path.join(base_path, current_path) if current_path else base_path

        try:
            items = os.listdir(full_path)
        except Exception as e:
            self.log(3, OlivOS.L10NAPI.getTrans(
                'Failed to list directory [{0}]: {1}', [
                    full_path,
                    str(e)
                ],
                modelName
            ))
            return []
        has_app_json = 'app.json' in items
        if has_app_json:
            # 当前目录就是插件,返回该插件的相对路径和完整路径
            # 使用系统默认的路径分隔符(os.sep)确保一致性
            relative_path = current_path.replace('/', os.sep) if current_path else '.'
            plugin_list.append((relative_path, False, full_path))
        else:
            # 继续递归查找子目录
            for item in items:
                # 跳过隐藏文件/目录
                if item.startswith('.'):
                    continue
                item_full_path = os.path.join(full_path, item)
                item_relative_path = os.path.join(current_path, item) if current_path else item
                if item.lower().endswith('.opk') and os.path.isfile(item_full_path):
                    plugin_list.append((item_relative_path, True, item_full_path))
                elif os.path.isdir(item_full_path):
                    sub_plugins = self.find_plugins_recursive(base_path, item_relative_path, depth + 1, max_depth)
                    plugin_list.extend(sub_plugins)
        return plugin_list

    def load_plugin_list(self):
        self.plugin_models_dict = {}
        self.plugin_shadowed_list = []
        candidates = {}
        for relative_path, is_opk, source_path in self.find_plugins_recursive(plugin_path):
            try:
                plugin = self._read_plugin_candidate(relative_path, is_opk, source_path)
                namespace = plugin['namespace']
                self.database._init_namespace(namespace)
            except opkAPI.OPKError as error:
                self._log_plugin_skip(relative_path, str(error))
                continue
            except Exception as error:
                self._log_plugin_skip(relative_path, f'{error}\n{traceback.format_exc()}')
                continue
            previous = candidates.get(namespace)
            if previous is not None:
                self.plugin_shadowed_list.append(dict(previous['source'], namespace=namespace))
                self.log(3, f'Duplicate plugin [{namespace}]: [{previous["source"]["path"]}] is shadowed by '
                         f'[{plugin["source"]["path"]}]')
            candidates[namespace] = plugin

        # 先准备所有入选插件，再执行 import/init，以保留插件间相互导入的能力。
        with ExitStack() as cleanup:
            prepared = []
            for plugin in candidates.values():
                try:
                    self._prepare_plugin(plugin, cleanup)
                    prepared.append(plugin)
                except (opkAPI.OPKError, OSError) as error:
                    self._log_plugin_skip(plugin['source']['path'], str(error))
            importlib.invalidate_caches()
            self._forget_loaded_plugins()
            finder = _PluginFinder(prepared)
            sys.meta_path.insert(0, finder)
            cleanup.callback(_discard_list_item, sys.meta_path, finder)
            for plugin in prepared:
                self._load_plugin(plugin)

            # init 可生成可发布资源；解包目录必须在缓存创建后才回收。
            self._cache_plugin_resources()
        self.plugin_models_call_list = build_plugin_call_order(self.plugin_models_dict, load_plugin_priority())
        self.log(2, OlivOS.L10NAPI.getTrans(
            'Total count [{0}] OlivOS plugin is loaded by OlivOS plugin shallow [{1}]',
            [len(self.plugin_models_dict), self.Proc_name],
            modelName
        ))

    def _log_plugin_skip(self, path, reason):
        self.log(4, OlivOS.L10NAPI.getTrans(
            'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}',
            [path, self.Proc_name, reason], modelName
        ))

    def _read_plugin_candidate(self, relative_path, is_opk, source_path):
        source_path = os.path.abspath(source_path)
        nested = None
        if is_opk:
            inspection = opkAPI.inspect_opk(source_path)
            appconf, namespace = inspection['manifest'], inspection['namespace']
            warnings, nested = inspection['warnings'], inspection['nested']
            module_name = namespace
        else:
            appconf = opkAPI.load_app_json_file(os.path.join(source_path, 'app.json'))
            module_name = os.path.basename(source_path)
            namespace, warnings = opkAPI.validate_manifest(appconf, module_name)
        for warning in warnings:
            self.log(3, f'OlivOS plugin [{relative_path}]: {warning}')
        normalized_relative = '' if relative_path == '.' else Path(relative_path).as_posix()
        return {
            'appconf': appconf,
            'namespace': namespace,
            'module_name': module_name,
            'folder_path': '' if relative_path == '.' else os.path.dirname(relative_path),
            'source': {'is_opk': is_opk, 'path': normalized_relative},
            'source_file': source_path,
            'nested': nested,
            'name': appconf['name'],
            'priority': appconf['priority'],
            'support': appconf['support'],
            'menu_config': appconf.get('menu_config'),
            'webui_config': appconf.get('webui_config'),
            'message_mode': appconf.get('message_mode', OlivOS.infoAPI.OlivOS_message_mode_tx_default),
            'author': appconf.get('author', 'N/A'),
            'svn': appconf.get('svn', 0),
            'version': appconf.get('version', '0'),
            'info': appconf.get('info', 'N/A'),
            'compatible_svn': appconf.get('compatible_svn', OlivOS.infoAPI.OlivOS_compatible_svn_default),
        }

    def _prepare_plugin(self, plugin, cleanup):
        root = plugin['source_file']
        if plugin['source']['is_opk']:
            from OlivOS.webUI import resourceAPI

            directory = os.path.abspath(plugin_path_tmp)
            os.makedirs(directory, exist_ok=True)
            if resourceAPI.is_link(Path(directory)):
                raise OSError('OPK temporary root must not be a symbolic link or junction')
            root = os.path.join(directory, plugin['namespace'])
            try:
                os.mkdir(root)
            except FileExistsError:
                # 不删除或重用其他插件、用户或并发加载器已存在的目录。
                work = tempfile.mkdtemp(prefix='.opk-', dir=directory)
                cleanup.callback(removeDir, work)
                root = os.path.join(work, plugin['namespace'])
            else:
                cleanup.callback(removeDir, root)
            archive_stat = self._archive_identity(plugin['source_file'])
            inspection = opkAPI.extract_opk(plugin['source_file'], root)
            manifest = opkAPI.load_app_json_file(os.path.join(root, 'app.json'))
            if (inspection['namespace'] != plugin['namespace'] or inspection['nested'] != plugin['nested']
                    or manifest != plugin['appconf'] or self._archive_identity(plugin['source_file']) != archive_stat):
                raise opkAPI.OPKError('changed', 'OPK changed while loading')
            plugin['archive_stat'] = archive_stat
        plugin.update(plugin_root=root, webui_root=root)
        parent = os.path.dirname(root)
        if parent not in map(os.path.abspath, sys.path):
            sys.path.insert(0, parent)
            if plugin['source']['is_opk'] and parent != os.path.abspath(plugin_path_tmp):
                cleanup.callback(_discard_list_item, sys.path, parent)

    @staticmethod
    def _archive_identity(path):
        info = os.stat(path)
        return info.st_dev, info.st_ino, info.st_mtime_ns, info.st_size

    @staticmethod
    def _forget_loaded_plugins():
        modules = sys.modules.copy()
        names = {name for name, module in modules.items()
                 if isinstance(module, ModuleType) and vars(module).get('_olivos_loaded_plugin')}
        for name in modules:
            if name.partition('.')[0] in names:
                sys.modules.pop(name, None)

    def _import_plugin(self, plugin):
        name, root = plugin['module_name'], plugin['plugin_root']
        entry = os.path.join(root, '__init__.py')
        try:
            module = importlib.import_module(name)
        except BaseException:
            # Python 回滚失败的包导入，但不回滚已经成功导入的子模块。
            for submodule in list(sys.modules):
                if submodule.startswith(name + '.'):
                    sys.modules.pop(submodule, None)
            raise
        existing = getattr(module, '__file__', None)
        if existing is None or os.path.normcase(os.path.abspath(existing)) != os.path.normcase(entry):
            raise ImportError(f'Plugin module [{name}] is already imported from [{existing}]')
        module._olivos_loaded_plugin = True
        return module

    def _load_plugin(self, plugin):
        namespace = plugin['namespace']
        try:
            module = self._import_plugin(plugin)
            if not hasattr(module, 'main'):
                raise ImportError(f'{namespace}.main not found')
            if not hasattr(module.main, 'Event'):
                raise ImportError(f'{namespace}.main.Event not found')
        except Exception as error:
            self._log_plugin_skip(plugin['source']['path'], f'{error}\n{traceback.format_exc()}')
            return

        plugin['model'] = module
        self.plugin_models_dict[namespace] = plugin
        if hasattr(module.main.Event, 'init'):
            try:
                module.main.Event.init(plugin_event=None, Proc=self)
            except Exception as error:
                # 与旧加载器一致，init 失败的实例仍保留在线，但不重写原包。
                plugin['schedule_init_failed'] = True
                self._log_plugin_skip(plugin['source']['path'], f'init: {error}\n{traceback.format_exc()}')
            else:
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS plugin [{0}] call [{1}] done', [plugin['name'], 'init'], modelName
                ))
        if plugin['nested'] and not plugin.get('schedule_init_failed'):
            self._rebuild_nested_plugin(plugin)
        self.log(2, OlivOS.L10NAPI.getTrans(
            'OlivOS plugin [{0}] is loaded by OlivOS plugin shallow [{1}]',
            [plugin['name'], self.Proc_name], modelName
        ))
        self.run_plugin_data_release_by_name(namespace)

    def _rebuild_nested_plugin(self, plugin):
        from OlivOS.webUI import resourceAPI

        relative = plugin['source']['path']
        path = plugin['source_file']
        try:
            if resourceAPI.is_link(Path(plugin_path)) or not resourceAPI.mounted(path, plugin_path):
                raise OSError('nested OPK path contains a symbolic link or junction')
            if self._archive_identity(path) != plugin['archive_stat']:
                raise OSError('original OPK changed after extraction')
            opkAPI.rebuild_opk_file(path, path)
        except (OSError, opkAPI.OPKError) as error:
            self.log(3, f'Failed to rebuild nested OPK [{relative}]: {error}')
        else:
            self.log(2, f'Rebuilt nested OPK [{relative}] as a flat archive')

    def _cache_plugin_resources(self):
        from OlivOS.webUI import resourceAPI

        for namespace, plugin in self.plugin_models_dict.items():
            if not isinstance(plugin.get('webui_config'), list):
                continue
            try:
                source = plugin['webui_root']
                resources, pages = resourceAPI.declaration(source, plugin['appconf'])
                if not resourceAPI.valid_namespace(namespace):
                    raise ValueError('Invalid WebUI namespace')
                if plugin['source']['is_opk']:
                    runtime_root = os.path.dirname(os.path.dirname(os.path.abspath(plugin_path_tmp)))
                    plugin['webui_root'] = (
                        resourceAPI.build_cache(runtime_root, source, namespace, resources) if resources else ''
                    )
                plugin.update(webui_resources=resources, webui_config=pages)
            except (OSError, ValueError, RuntimeError) as error:
                plugin.update(webui_resources=[], webui_config=[], webui_root='')
                self.log(4, f'WebUI resources [{namespace}]: {error}')
