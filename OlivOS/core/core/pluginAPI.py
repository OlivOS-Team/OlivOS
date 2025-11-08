# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/pluginAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

import multiprocessing
import platform
import threading
import time
import datetime
import sys
import importlib
import os
import json
import traceback
import zipfile
import shutil

if platform.system() == 'Windows':
    import tkinter

import OlivOS

modelName = 'pluginAPI'

gProc = None

def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def removeDir(dir_path):
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
    except:
        pass


def doOpkRemove(plugin_path, plugin_dir):
    if len(plugin_dir) > 4:
        if plugin_dir[-4:] == '.opk':
            removeDir(plugin_path + plugin_dir[:-4])


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


class shallow(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name='native_plugin', scan_interval=0.001, dead_interval=1, rx_queue=None, tx_queue=None,
                 control_queue=None, logger_proc=None, debug_mode=False, plugin_func_dict=None, bot_info_dict=None,
                 treading_mode='full', restart_gate=10000, enable_auto_restart=False):
        OlivOS.API.Proc_templet.__init__(self, Proc_name=Proc_name, Proc_type='plugin', scan_interval=scan_interval,
                                         dead_interval=dead_interval, rx_queue=rx_queue, tx_queue=tx_queue,
                                         control_queue=control_queue, logger_proc=logger_proc)
        if bot_info_dict is None:
            bot_info_dict = {}
        if plugin_func_dict is None:
            plugin_func_dict = {}
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_config['treading_mode'] = treading_mode
        self.Proc_config['shallow_dict'] = {}
        self.Proc_config['ready_for_restart'] = False
        self.Proc_config['enable_auto_restart'] = enable_auto_restart
        self.Proc_config['step_to_restart'] = restart_gate
        self.Proc_data['plugin_func_dict'] = plugin_func_dict
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['main_tk'] = None
        self.plugin_models_dict = {}
        self.plugin_models_call_list = []
        self.tx_queue = []
        self.menu_queue = []
        self.database = None

    class rx_packet(object):
        def __init__(self, sdk_event):
            self.sdk_event = sdk_event

    def __init_GUI(self):
        if platform.system() == 'Windows':
            self.Proc_data['main_tk'] = tkinter.Tk()
            self.Proc_data['main_tk'].withdraw()
            self.Proc_data['main_tk'].iconbitmap('./resource/tmp_favoricon.ico')
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
        threading.Thread(target=self.__init_GUI).start()
        # self.set_check_update()
        time.sleep(1)  # 此处延迟用于在终端第一次启动时等待终端初始化，避免日志丢失，后续需要用异步(控制包流程)方案替代
        self.database = OlivOS.userModule.UserConfDB.DataBaseAPI(self.log, max_thread=None, timeout=self.Proc_info.dead_interval)
        self.load_plugin_list()
        self.check_plugin_list()
        self.run_plugin_func(None, 'init_after')
        self.log(2, OlivOS.L10NAPI.getTrans('OlivOS plugin shallow [{0}] is running', [self.Proc_name], modelName))
        self.sendPluginList()
        rx_count = 0
        while True:
            if self.Proc_info.rx_queue.empty() or self.Proc_config['ready_for_restart']:
                time.sleep(self.Proc_info.scan_interval)
            else:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block=False)
                except:
                    continue
                if type(rx_packet_data) == OlivOS.API.Control.packet:
                    if rx_packet_data.action == 'restart_do' and self.Proc_config['enable_auto_restart']:
                        self.Proc_config['ready_for_restart'] = True
                        self.run_plugin_func(None, 'save')
                        self.Proc_info.control_queue.put(
                            OlivOS.API.Control.packet('restart_do', self.Proc_name), block=False)
                        self.log(2, OlivOS.L10NAPI.getTrans(
                            'OlivOS plugin shallow [{0}] will restart', [self.Proc_name], modelName))
                        # 在运行过 save 指令后，将配置数据库关闭
                        self.database.stop()
                    elif rx_packet_data.action == 'update_hit' and self.Proc_config['enable_auto_restart']:
                        self.Proc_config['ready_for_restart'] = True
                        self.run_plugin_func(None, 'save')
                        self.Proc_info.control_queue.put(OlivOS.API.Control.packet('init_type', 'update_replace'),
                                                         block=False)
                        # 在运行过 save 指令后，将配置数据库关闭
                        self.database.stop()
                    elif rx_packet_data.action == 'send':
                        self.menu_queue.append(rx_packet_data)
                else:
                    if self.Proc_config['treading_mode'] == 'none':
                        self.run_plugin(rx_packet_data.sdk_event)
                    elif self.Proc_config['treading_mode'] == 'full':
                        t_run_plugin = None
                        t_run_plugin = threading.Thread(target=self.run_plugin, args=(rx_packet_data.sdk_event,))
                        t_run_plugin.start()
                if self.Proc_config['enable_auto_restart']:
                    rx_count += 1
                    if rx_count == self.Proc_config['step_to_restart']:
                        self.set_restart()

    def on_control_rx(self, packet):
        if type(packet) is OlivOS.API.Control.packet:
            if 'send' == packet.action:
                if type(packet.key) is dict \
                and 'data' in packet.key \
                and type(packet.key['data']) \
                and 'action' in packet.key['data']:
                    if 'account_update' == packet.key['data']['action']:
                        self.set_restart()

    def set_restart(self):
        self.log(2, OlivOS.L10NAPI.getTrans(
            'OlivOS plugin shallow [{0}] call restart', [
                self.Proc_name
            ],
            modelName
        ))
        self.Proc_info.rx_queue.put(OlivOS.API.Control.packet('restart_do', self.Proc_name), block=False)

    def set_check_update(self):
        self.log(2, OlivOS.L10NAPI.getTrans(
            'OlivOS plugin shallow [{0}] call check update', [
                self.Proc_name
            ],
            modelName
        ))
        self.Proc_info.control_queue.put(OlivOS.API.Control.packet('init_type', 'update_get'), block=False)

    def get_plugin_list(self):
        return self.plugin_models_call_list

    def get_main_root(self):
        return self.Proc_data['main_tk']

    def run_plugin(self, sdk_event):
        #plugin_event = OlivOS.API.Event(sdk_event=sdk_event, log_func=self.log, Proc=self)
        plugin_event = OlivOS.API.Event(sdk_event=sdk_event)
        plugin_event_bot_hash = OlivOS.API.getBotHash(
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
                        plugin_event.plugin_info['compatible_svn'] = self.plugin_models_dict[plugin_models_index_this]['compatible_svn']
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
                elif plugin_event.plugin_info['func_type'] == 'group_lucky_king':
                    plugin_model.main.Event.group_lucky_king(plugin_event=plugin_event, Proc=self)
                elif plugin_event.plugin_info['func_type'] == 'group_honor':
                    plugin_model.main.Event.group_honor(plugin_event=plugin_event, Proc=self)
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

    def run_plugin_data_release(self):
        for plugin_models_index_this in self.plugin_models_call_list:
            if plugin_models_index_this in self.plugin_models_dict:
                self.run_plugin_data_release_by_name(plugin_models_index_this)

    def run_plugin_data_release_by_name(self, plugin_models_index_this):
        func_name = 'release_data'
        dataPath = './plugin/data/%s/data' % plugin_models_index_this
        dataPathFromList = [
            './plugin/app/%s/data' % plugin_models_index_this,
            './plugin/tmp/%s/data' % plugin_models_index_this
        ]
        for dataPathFrom in dataPathFromList:
            if os.path.exists(dataPathFrom) \
            and os.path.isdir(dataPathFrom):
                try:
                    removeDir(dataPath)
                    shutil.copytree(dataPathFrom, dataPath)
                    self.log(2, OlivOS.L10NAPI.getTrans(
                        'OlivOS plugin [{0}] call [{1}] done', [
                            self.plugin_models_dict[plugin_models_index_this]['name'],
                            func_name
                        ],
                        modelName
                    ))
                except Exception as e:
                    self.log(4, OlivOS.L10NAPI.getTrans(
                        'OlivOS plugin [{0}] call [{1}] failed: {2}\n{3}', [
                            self.plugin_models_dict[plugin_models_index_this]['name'],
                            func_name,
                            str(e),
                            traceback.format_exc()
                        ],
                        modelName
                    ))
                break

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

    def sendPluginList(self):
        tmp_plugin_list_send = []
        tmp_plugin_dict_send = {}
        for plugin_models_index_this in self.plugin_models_call_list:
            if plugin_models_index_this in self.plugin_models_dict:
                plugin_models_this = self.plugin_models_dict[plugin_models_index_this]
                tmp_plugin_list_this = None
                if plugin_models_this['menu_config'] is not None:
                    plugin_models_this_menu = plugin_models_this['menu_config']
                    if type(plugin_models_this_menu) == list:
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
                    plugin_models_this['priority']
                ]
        self.sendControlEvent('send', {
            'target': {
                'type': 'nativeWinUI'
            },
            'data': {
                'action': 'update_data',
                'data': {
                    'shallow_plugin_menu_list': tmp_plugin_list_send,
                    'shallow_plugin_data_dict': tmp_plugin_dict_send
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
                OlivOS.API.Control.packet(
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
                if item.endswith('.opk') and os.path.isfile(item_full_path):
                    plugin_list.append((item_relative_path, True, item_full_path))
                elif os.path.isdir(item_full_path):
                    sub_plugins = self.find_plugins_recursive(base_path, item_relative_path, depth + 1, max_depth)
                    plugin_list.extend(sub_plugins)
        return plugin_list

    def load_plugin_list(self):
        total_models_count = 0
        self.plugin_models_dict = {}
        skip_result = ''
        func_init_name = 'init'
        # 递归查找插件
        plugin_dir_list_with_info = self.find_plugins_recursive(plugin_path)
        opk_plugin_list = []
        # 解包opk格式插件
        for plugin_dir_this_tmp, is_opk, full_path_info in plugin_dir_list_with_info:
            flag_is_opk = is_opk
            try:
                plugin_dir_this = plugin_dir_this_tmp
                if flag_is_opk and len(plugin_dir_this_tmp) > 4:
                    if plugin_dir_this_tmp[-4:] == '.opk':
                        plugin_dir_this = plugin_dir_this_tmp[:-4]
                        opkFile = zipfile.ZipFile(os.path.join(plugin_path, plugin_dir_this_tmp))
                        opkFile_list = opkFile.namelist()
                        releaseDir(plugin_path_tmp)
                        doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                        opk_plugin_list.append(plugin_dir_this_tmp)
                        releaseDir(os.path.join(plugin_path_tmp, plugin_dir_this))
                        for opkFile_list_this in opkFile_list:
                            opkFile.extract(opkFile_list_this, os.path.join(plugin_path_tmp, plugin_dir_this))
            except Exception as e:
                doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                # traceback.print_exc()
                self.log(3, OlivOS.L10NAPI.getTrans(
                    'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}\n{3}', [
                        plugin_dir_this,
                        self.Proc_name,
                        str(e),
                        traceback.format_exc()
                    ],
                    modelName
                ))
                continue

        plugin_models_dict = {}

        # 统一载入插件
        for plugin_dir_this_tmp, is_opk, full_path_info in plugin_dir_list_with_info:
            flag_is_opk = is_opk
            plugin_models_app_conf = None
            skip_result = None
            skip_result_level = None
            try:
                plugin_dir_this = plugin_dir_this_tmp
                if flag_is_opk and len(plugin_dir_this_tmp) > 4:
                    if plugin_dir_this_tmp[-4:] == '.opk':
                        plugin_dir_this = plugin_dir_this_tmp[:-4]
                if len(plugin_dir_this) > 0:
                    if plugin_dir_this[0] not in ['.']:
                        try:
                            if flag_is_opk:
                                app_json_path = os.path.join(plugin_path_tmp, plugin_dir_this, 'app.json')
                                with open(app_json_path, 'r', encoding='utf-8') as plugin_models_app_conf_f:
                                    plugin_models_app_conf = json.loads(plugin_models_app_conf_f.read())
                            else:
                                app_json_path = os.path.join(plugin_path, plugin_dir_this, 'app.json')
                                with open(app_json_path, 'r', encoding='utf-8') as plugin_models_app_conf_f:
                                    plugin_models_app_conf = json.loads(plugin_models_app_conf_f.read())
                        except:
                            traceback.print_exc()
                            plugin_models_app_conf = None
                        plugin_models_dict_this = {}
                        if plugin_models_app_conf is None:
                            skip_result = plugin_dir_this + '/app.json' + ' not found'
                            skip_result_level = 4
                        else:
                            # 获取插件的模块名
                            plugin_module_name = os.path.basename(plugin_dir_this.rstrip(os.sep).rstrip('/'))
                            # 获取插件所在的文件夹路径
                            plugin_folder_path = os.path.dirname(plugin_dir_this) if os.sep in plugin_dir_this or '/' in plugin_dir_this else ''
                            
                            # 优先使用 app.json 中定义的 namespace,如果没有则使用插件模块名
                            if 'namespace' in plugin_models_app_conf:
                                plugin_namespace = plugin_models_app_conf['namespace']
                            else:
                                plugin_namespace = plugin_module_name
                            
                            plugin_models_dict_this = {
                                'appconf': plugin_models_app_conf,
                                'priority': plugin_models_app_conf['priority'],
                                'namespace': plugin_namespace,
                                'module_name': plugin_module_name,
                                'folder_path': plugin_folder_path,
                                'name': plugin_models_app_conf['name'],
                                'support': plugin_models_app_conf['support'],
                                'menu_config': None
                            }
                            if 'menu_config' in plugin_models_app_conf:
                                plugin_models_dict_this['menu_config'] = plugin_models_app_conf['menu_config']
                            if 'message_mode' in plugin_models_app_conf:
                                plugin_models_dict_this['message_mode'] = plugin_models_app_conf['message_mode']
                            else:
                                plugin_models_dict_this['message_mode'] = OlivOS.infoAPI.OlivOS_message_mode_tx_default
                            if 'author' in plugin_models_app_conf:
                                plugin_models_dict_this['author'] = plugin_models_app_conf['author']
                            else:
                                plugin_models_dict_this['author'] = 'N/A'
                            if 'svn' in plugin_models_app_conf:
                                plugin_models_dict_this['svn'] = plugin_models_app_conf['svn']
                            else:
                                plugin_models_dict_this['svn'] = 0
                            if 'version' in plugin_models_app_conf:
                                plugin_models_dict_this['version'] = plugin_models_app_conf['version']
                            else:
                                plugin_models_dict_this['version'] = '0'
                            if 'info' in plugin_models_app_conf:
                                plugin_models_dict_this['info'] = plugin_models_app_conf['info']
                            else:
                                plugin_models_dict_this['info'] = 'N/A'
                            if 'compatible_svn' in plugin_models_app_conf:
                                plugin_models_dict_this['compatible_svn'] = plugin_models_app_conf['compatible_svn']
                            else:
                                plugin_models_dict_this['compatible_svn'] = OlivOS.infoAPI.OlivOS_compatible_svn_default
                            if plugin_models_dict_this['compatible_svn'] >= OlivOS.infoAPI.OlivOS_SVN_Compatible:
                                pass
                            elif plugin_models_dict_this[
                                'compatible_svn'] >= OlivOS.infoAPI.OlivOS_SVN_OldCompatible and \
                                    plugin_models_dict_this['compatible_svn'] <= OlivOS.infoAPI.OlivOS_SVN_Compatible:
                                self.log(3, OlivOS.L10NAPI.getTrans(
                                    'OlivOS plugin [{0}] is support for old OlivOS version {1}', [
                                        plugin_models_dict_this['name'],
                                        str(plugin_models_dict_this['compatible_svn'])
                                    ],
                                    modelName
                                ))
                            elif plugin_models_dict_this['compatible_svn'] <= OlivOS.infoAPI.OlivOS_SVN_OldCompatible:
                                skip_result = OlivOS.L10NAPI.getTrans(
                                    'is support for old OlivOS version {0}', [
                                        str(plugin_models_dict_this['compatible_svn'])
                                    ],
                                    modelName
                                )
                                self.log(4, OlivOS.L10NAPI.getTrans(
                                    'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}', [
                                        plugin_models_dict_this['name'],
                                        self.Proc_name,
                                        skip_result
                                    ],
                                    modelName
                                ))
                                continue

                            # 自动修改解包名称
                            if flag_is_opk:
                                plugin_namespace = plugin_models_dict_this['namespace']
                                if plugin_namespace != plugin_dir_this:
                                    removeDir(os.path.join(plugin_path_tmp, plugin_namespace))
                                    shutil.move(
                                        os.path.join(plugin_path_tmp, plugin_dir_this),
                                        os.path.join(plugin_path_tmp, plugin_namespace)
                                    )
                                    removeDir(os.path.join(plugin_path_tmp, plugin_dir_this))
                                    plugin_dir_this = plugin_namespace

                            # 完成配置数据库中对应插件命名空间的表格页初始化
                            self.database._init_namespace(plugin_models_dict_this['namespace'])

                            # 使用 namespace 作为字典的 key
                            plugin_namespace_key = plugin_models_dict_this['namespace']
                            plugin_models_dict[plugin_namespace_key] = {
                                'isOPK': flag_is_opk,
                                'data': plugin_models_dict_this,
                                'plugin_dir': plugin_dir_this  # 保存原始目录路径用于后续加载
                            }
                        # doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                    else:
                        # doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                        skip_result = 'mask path'
                else:
                    # doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                    skip_result = 'name too short'
            except Exception as e:
                # doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                # traceback.print_exc()
                skip_result = '%s\n%s' % (
                    str(e),
                    traceback.format_exc()
                )
                skip_result_level = 4
            if skip_result is not None:
                if skip_result_level is None:
                    skip_result_level = 3
                self.log(skip_result_level, OlivOS.L10NAPI.getTrans(
                    'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}', [
                        plugin_dir_this, self.Proc_name, skip_result
                    ],
                    modelName
                ))

        for plugin_models_dict_this_key in plugin_models_dict:
            try:
                # 从这里开始导入实际模块
                plugin_models_dict_this = plugin_models_dict[plugin_models_dict_this_key]['data']
                plugin_namespace = plugin_models_dict_this_key  # 这是 namespace
                plugin_dir_this = plugin_models_dict[plugin_models_dict_this_key].get('plugin_dir', plugin_namespace)  # 这是实际目录路径
                flag_is_opk = plugin_models_dict[plugin_models_dict_this_key]['isOPK']
                # 处理子目录中的插件
                # 获取插件的模块名
                plugin_module_name = plugin_models_dict_this.get('module_name', os.path.basename(plugin_dir_this.rstrip(os.sep)))
                # 获取插件所在的父目录
                plugin_folder_path = plugin_models_dict_this.get('folder_path', '')
                if plugin_folder_path:
                    # 插件在子目录中,需要将父目录添加到 sys.path
                    if flag_is_opk:
                        plugin_parent_full_path = os.path.join(plugin_path_tmp, plugin_folder_path)
                    else:
                        plugin_parent_full_path = os.path.join(plugin_path, plugin_folder_path)
                    # 添加到 sys.path (如果还没有添加)
                    if plugin_parent_full_path not in sys.path:
                        sys.path.insert(0, plugin_parent_full_path)
                
                plugin_models_tmp = importlib.import_module(plugin_module_name)
                plugin_models_dict_this['model'] = plugin_models_tmp
                if hasattr(plugin_models_tmp, 'main'):
                    if hasattr(plugin_models_tmp.main, 'Event'):
                        self.plugin_models_dict[plugin_namespace] = plugin_models_dict_this
                        if hasattr(plugin_models_tmp.main.Event, func_init_name):
                            try:
                                plugin_models_tmp.main.Event.init(plugin_event=None, Proc=self)
                                self.log(2, OlivOS.L10NAPI.getTrans(
                                    'OlivOS plugin [{0}] call [{1}] done', [
                                        plugin_models_dict_this['name'],
                                        func_init_name
                                    ],
                                    modelName
                                ))
                            except Exception as e:
                                self.log(4, OlivOS.L10NAPI.getTrans(
                                    'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}\n{3}', [
                                        plugin_models_dict_this['name'],
                                        func_init_name,
                                        str(e),
                                        traceback.format_exc()
                                    ],
                                    modelName
                                ))
                        total_models_count += 1
                        self.log(2, OlivOS.L10NAPI.getTrans(
                            'OlivOS plugin [{0}] is loaded by OlivOS plugin shallow [{1}]', [
                                plugin_models_dict_this['name'],
                                self.Proc_name
                            ],
                            modelName
                        ))
                        # doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                        self.run_plugin_data_release_by_name(plugin_namespace)
                        continue
                    else:
                        skip_result = plugin_namespace + '.main.Event' + ' not found'
                        skip_result_level = 4
                else:
                    skip_result = plugin_namespace + '.main' + ' not found'
                    skip_result_level = 4
            except Exception as e:
                # doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                # traceback.print_exc()
                skip_result = '%s\n%s' % (
                    str(e),
                    traceback.format_exc()
                )
                skip_result_level = 4
            if skip_result is not None:
                if skip_result_level is None:
                    skip_result_level = 3
                self.log(skip_result_level, OlivOS.L10NAPI.getTrans(
                    'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}',
                    [plugin_namespace, self.Proc_name, skip_result]
                ))

        # 清理opk格式插件缓存
        for plugin_models_dict_this in plugin_models_dict:
            if plugin_models_dict[plugin_models_dict_this]['isOPK']:
                plugin_dir = plugin_models_dict[plugin_models_dict_this].get('plugin_dir', plugin_models_dict_this)
                removeDir(os.path.join(plugin_path_tmp, plugin_dir))
        # 插件调用列表按照优先级排序
        plugin_models_call_list_tmp = sorted(self.plugin_models_dict.values(),
                                             key=lambda i: (i['priority'], i['namespace']))
        self.plugin_models_call_list = []
        for namespace_this in plugin_models_call_list_tmp:
            self.plugin_models_call_list.append(namespace_this['namespace'])
        self.log(2, OlivOS.L10NAPI.getTrans(
            'Total count [{0}] OlivOS plugin is loaded by OlivOS plugin shallow [{1}]',
            [total_models_count, self.Proc_name],
            modelName
        ))
