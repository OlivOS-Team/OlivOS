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
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import multiprocessing
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

import OlivOS


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
    def __init__(self, Proc_name = 'native_plugin', scan_interval = 0.001, dead_interval = 1, rx_queue = None, tx_queue = None, control_queue = None, logger_proc = None, debug_mode = False, plugin_func_dict = {}, bot_info_dict = {}, treading_mode = 'full', restart_gate = 10000, enable_auto_restart = False):
        OlivOS.API.Proc_templet.__init__(self, Proc_name = Proc_name, Proc_type = 'shallow', scan_interval = scan_interval, dead_interval = dead_interval, rx_queue = rx_queue, tx_queue = tx_queue, control_queue = control_queue, logger_proc = logger_proc)
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_config['treading_mode'] = treading_mode
        self.Proc_config['shallow_dict'] = {}
        self.Proc_config['ready_for_restart'] = False
        self.Proc_config['enable_auto_restart'] = enable_auto_restart
        self.Proc_config['step_to_restart'] = restart_gate
        self.Proc_data['plugin_func_dict'] = plugin_func_dict
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.plugin_models_dict = {}
        self.plugin_models_call_list = []
        self.tx_queue = []

    class rx_packet(object):
        def __init__(self, sdk_event):
            self.sdk_event = sdk_event

    def run(self):
        releaseDir('./plugin')
        releaseDir('./plugin/app')
        releaseDir('./plugin/conf')
        releaseDir('./plugin/data')
        releaseDir('./plugin/tmp')
        releaseDir('./lib')
        releaseDir('./lib/Lib')
        releaseDir('./lib/DLLs')
        self.sendPluginList()
        self.load_plugin_list()
        self.run_plugin_func(None, 'init_after')
        self.log(2, 'OlivOS plugin shallow [' + self.Proc_name + '] is running')
        self.sendPluginList()
        rx_count = 0
        while True:
            if self.Proc_info.rx_queue.empty() or self.Proc_config['ready_for_restart']:
                time.sleep(self.Proc_info.scan_interval)
            else:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block = False)
                except:
                    continue
                if type(rx_packet_data) == OlivOS.API.Control.packet:
                    if rx_packet_data.action == 'restart_do' and self.Proc_config['enable_auto_restart']:
                        self.Proc_config['ready_for_restart'] = True
                        self.run_plugin_func(None, 'save')
                        self.Proc_info.control_queue.put(OlivOS.API.Control.packet('restart_do', self.Proc_name), block=False)
                        self.Proc_info.control_queue.put(OlivOS.API.Control.packet('init', self.Proc_name), block=False)
                        self.log(2, 'OlivOS plugin shallow [' + self.Proc_name + '] will restart')
                    elif rx_packet_data.action == 'send':
                        t_run_plugin = None
                        t_run_plugin = threading.Thread(target=self.run_plugin, args=(rx_packet_data,))
                        t_run_plugin.start()
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

    def set_restart(self):
        self.log(2, 'OlivOS plugin shallow [' + self.Proc_name + '] call restart')
        self.Proc_info.rx_queue.put(OlivOS.API.Control.packet('restart_do', self.Proc_name), block=False)

    def get_plugin_list(self):
        return self.plugin_models_call_list

    def run_plugin(self, sdk_event):
        plugin_event = OlivOS.API.Event(sdk_event, self.log)
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id = plugin_event.base_info['self_id'],
            platform_sdk = plugin_event.platform['sdk'],
            platform_platform = plugin_event.platform['platform'],
            platform_model = plugin_event.platform['model']
        )
        if plugin_event.active:
            if plugin_event_bot_hash in self.Proc_data['bot_info_dict']:
                plugin_event.bot_info = self.Proc_data['bot_info_dict'][plugin_event_bot_hash]
            elif plugin_event.plugin_info['func_type'] in ['menu']:
                pass
            else:
                self.log(3, 'Account [' + str(plugin_event.base_info['self_id']) + '] not found, please check your account config')
                plugin_event.active = False
        if plugin_event.active:
            plugin_event.plugin_info['tx_queue'] = self.Proc_info.tx_queue
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
                    if flag_support_found_dict['sdk'] and flag_support_found_dict['platform'] and flag_support_found_dict['model']:
                        flag_support_found_dict['flag'] = True
                if flag_support_found_dict['flag']:
                    plugin_event.plugin_info['name'] = self.plugin_models_dict[plugin_models_index_this]['name']
                    plugin_event.plugin_info['namespace'] = self.plugin_models_dict[plugin_models_index_this]['namespace']
                    if 'message_mode' in self.plugin_models_dict[plugin_models_index_this]:
                        plugin_event.plugin_info['message_mode_tx'] = self.plugin_models_dict[plugin_models_index_this]['message_mode']
                    else:
                        plugin_event.plugin_info['message_mode_tx'] = OlivOS.infoAPI.OlivOS_message_mode_tx_default
                    plugin_event.get_Event_on_Plugin()
                    self.plugin_event_router(plugin_event, self.plugin_models_dict[plugin_models_index_this]['model'], plugin_models_index_this)
                    self.log(0, 'event [' + str(plugin_event.plugin_info['func_type']) + '] call plugin [' + self.plugin_models_dict[plugin_models_index_this]['name'] + '] done')
                if plugin_event.blocked:
                    self.log(2, 'event [' + str(plugin_event.plugin_info['func_type']) + '] call blocked by plugin [' + self.plugin_models_dict[plugin_models_index_this]['name'] + ']')
                    break
        return

    def plugin_event_router(self, plugin_event, plugin_model, plugin_name):
        if hasattr(plugin_model.main.Event, plugin_event.plugin_info['func_type']):
            try:
                if plugin_event.plugin_info['func_type'] == 'private_message':
                    plugin_model.main.Event.private_message(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_message':
                    plugin_model.main.Event.group_message(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_file_upload':
                    plugin_model.main.Event.group_file_upload(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_admin':
                    plugin_model.main.Event.group_admin(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_member_decrease':
                    plugin_model.main.Event.group_member_decrease(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_member_increase':
                    plugin_model.main.Event.group_member_increase(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_ban':
                    plugin_model.main.Event.group_ban(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_message_recall':
                    plugin_model.main.Event.group_message_recall(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'private_message_recall':
                    plugin_model.main.Event.private_message_recall(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'poke':
                    plugin_model.main.Event.poke(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_lucky_king':
                    plugin_model.main.Event.group_lucky_king(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_honor':
                    plugin_model.main.Event.group_honor(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'friend_add_request':
                    plugin_model.main.Event.friend_add_request(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_add_request':
                    plugin_model.main.Event.group_add_request(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'group_invite_request':
                    plugin_model.main.Event.group_invite_request(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'lifecycle':
                    plugin_model.main.Event.lifecycle(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'heartbeat':
                    plugin_model.main.Event.heartbeat(plugin_event = plugin_event, Proc = self)
                elif plugin_event.plugin_info['func_type'] == 'menu':
                    plugin_model.main.Event.menu(plugin_event = plugin_event, Proc = self)
            except Exception as e:
                #traceback.print_exc()
                self.log(4, 'OlivOS plugin [' + plugin_name + '] call [' + plugin_event.plugin_info['func_type'] + '] failed: %s\n%s' % (
                        str(e),
                        traceback.format_exc()
                    )
                )
                plugin_event.set_block()
        return

    def run_plugin_func(self, plugin_event, func_name):
        for plugin_models_index_this in self.plugin_models_call_list:
            if hasattr(self.plugin_models_dict[plugin_models_index_this]['model'].main.Event, func_name):
                try:
                    getattr(self.plugin_models_dict[plugin_models_index_this]['model'].main.Event, func_name)(plugin_event = plugin_event, Proc = self)
                    self.log(2, 'OlivOS plugin [' + self.plugin_models_dict[plugin_models_index_this]['name'] + '] call [' + func_name + '] done')
                except Exception as e:
                    #traceback.print_exc()
                    self.log(4, 'OlivOS plugin [' + self.plugin_models_dict[plugin_models_index_this]['name'] + '] call [' + func_name + '] failed: %s\n%s' % (
                            str(e),
                            traceback.format_exc()
                        )
                    )
        return

    def sendPluginList(self):
        tmp_plugin_list_send = []
        tmp_plugin_dict_send = {}
        for plugin_models_index_this in self.plugin_models_call_list:
            if plugin_models_index_this in self.plugin_models_dict:
                plugin_models_this = self.plugin_models_dict[plugin_models_index_this]
                tmp_plugin_list_this = None
                if plugin_models_this['menu_config'] != None:
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
                    plugin_models_this['info']
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
        if self.Proc_info.control_queue != None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block = False
            )

    def load_plugin_list(self):
        total_models_count = 0
        self.plugin_models_dict = {}
        skip_result = ''
        func_init_name = 'init'
        plugin_dir_list = os.listdir(plugin_path)
        opk_plugin_list = []
        #解包opk格式插件
        for plugin_dir_this_tmp in plugin_dir_list:
            flag_is_opk = False
            try:
                plugin_dir_this = plugin_dir_this_tmp
                if len(plugin_dir_this_tmp) > 4:
                    if plugin_dir_this_tmp[-4:] == '.opk':
                        flag_is_opk = True
                        plugin_dir_this = plugin_dir_this_tmp[:-4]
                        opkFile = zipfile.ZipFile(plugin_path + plugin_dir_this_tmp)
                        opkFile_list = opkFile.namelist()
                        releaseDir(plugin_path_tmp)
                        doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                        opk_plugin_list.append(plugin_dir_this_tmp)
                        releaseDir(plugin_path_tmp + plugin_dir_this)
                        for opkFile_list_this in opkFile_list:
                            opkFile.extract(opkFile_list_this, plugin_path_tmp + plugin_dir_this)
            except Exception as e:
                doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                #traceback.print_exc()
                self.log(3, 'OlivOS plugin [' + plugin_dir_this + '] is skiped by OlivOS plugin shallow [' + self.Proc_name + ']: %s\n%s' % (
                        str(e),
                        traceback.format_exc()
                    )
                )
                continue
        #统一载入插件
        for plugin_dir_this_tmp in plugin_dir_list:
            flag_is_opk = False
            plugin_models_app_conf = None
            skip_result_level = None
            try:
                plugin_dir_this = plugin_dir_this_tmp
                if len(plugin_dir_this_tmp) > 4:
                    if plugin_dir_this_tmp[-4:] == '.opk':
                        flag_is_opk = True
                        plugin_dir_this = plugin_dir_this_tmp[:-4]
                if len(plugin_dir_this) > 0:
                    if plugin_dir_this[0] not in ['.']:
                        try:
                            if flag_is_opk:
                                with open(plugin_path_tmp + plugin_dir_this + '/app.json', 'r', encoding = 'utf-8') as plugin_models_app_conf_f:
                                    plugin_models_app_conf = json.loads(plugin_models_app_conf_f.read())
                            else:
                                with open(plugin_path + plugin_dir_this + '/app.json', 'r', encoding = 'utf-8') as plugin_models_app_conf_f:
                                    plugin_models_app_conf = json.loads(plugin_models_app_conf_f.read())
                        except:
                            #traceback.print_exc()
                            plugin_models_app_conf = None
                        plugin_models_dict_this = {}
                        if plugin_models_app_conf == None:
                            skip_result = plugin_dir_this + '/app.json' + ' not found'
                            skip_result_level = 4
                        else:
                            plugin_models_dict_this = {}
                            plugin_models_dict_this['appconf'] = plugin_models_app_conf
                            plugin_models_dict_this['priority'] = plugin_models_app_conf['priority']
                            plugin_models_dict_this['namespace'] = plugin_dir_this
                            plugin_models_dict_this['name'] = plugin_models_app_conf['name']
                            plugin_models_dict_this['support'] = plugin_models_app_conf['support']
                            plugin_models_dict_this['menu_config'] = None
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
                            elif plugin_models_dict_this['compatible_svn'] >= OlivOS.infoAPI.OlivOS_SVN_OldCompatible and plugin_models_dict_this['compatible_svn'] <= OlivOS.infoAPI.OlivOS_SVN_Compatible:
                                self.log(3, 'OlivOS plugin [' + plugin_models_dict_this['name'] + '] is support for old OlivOS version ' + str(plugin_models_dict_this['compatible_svn']))
                            elif plugin_models_dict_this['compatible_svn'] <= OlivOS.infoAPI.OlivOS_SVN_OldCompatible:
                                skip_result = 'is support for old OlivOS version ' + str(plugin_models_dict_this['compatible_svn'])
                                self.log(4, 'OlivOS plugin [' + plugin_models_dict_this['name'] + '] is skiped by OlivOS plugin shallow [' + self.Proc_name + ']: ' + skip_result)
                                continue
                            plugin_models_tmp = importlib.import_module(plugin_dir_this)
                            plugin_models_dict_this['model'] = plugin_models_tmp
                            if hasattr(plugin_models_tmp, 'main'):
                                if hasattr(plugin_models_tmp.main, 'Event'):
                                    self.plugin_models_dict[plugin_dir_this] = plugin_models_dict_this
                                    if hasattr(plugin_models_tmp.main.Event, func_init_name):
                                        try:
                                            plugin_models_tmp.main.Event.init(plugin_event = None, Proc = self)
                                            self.log(2, 'OlivOS plugin [' + plugin_models_dict_this['name'] + '] call [' + func_init_name + '] done')
                                        except Exception as e:
                                            self.log(4, 'OlivOS plugin [' + plugin_models_dict_this['name'] + '] call [' + func_init_name + '] failed: %s\n%s' % (
                                                    str(e),
                                                    traceback.format_exc()
                                                )
                                            )
                                    total_models_count += 1
                                    self.log(2, 'OlivOS plugin [' + plugin_models_dict_this['name'] + '] is loaded by OlivOS plugin shallow [' + self.Proc_name + ']')
                                    #doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                                    continue
                                else:
                                    skip_result = plugin_dir_this + '.main.Event' + ' not found'
                                    skip_result_level = 4
                            else:
                                skip_result = plugin_dir_this + '.main' + ' not found'
                                skip_result_level = 4
                        #doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                    else:
                        #doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                        skip_result = 'mask path'
                else:
                    #doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                    skip_result = 'name too short'
            except Exception as e:
                #doOpkRemove(plugin_path_tmp, plugin_dir_this_tmp)
                #traceback.print_exc()
                skip_result = '%s\n%s' % (
                    str(e),
                    traceback.format_exc()
                )
                skip_result_level = 4
            if skip_result_level == None:
                skip_result_level = 3
            self.log(skip_result_level, 'OlivOS plugin [' + plugin_dir_this + '] is skiped by OlivOS plugin shallow [' + self.Proc_name + ']: ' + skip_result)
        #清理opk格式插件缓存
        for opk_plugin_list_this in opk_plugin_list:
            doOpkRemove(plugin_path_tmp, opk_plugin_list_this)
        #插件调用列表按照优先级排序
        plugin_models_call_list_tmp = sorted(self.plugin_models_dict.values(), key = lambda i : (i['priority'], i['namespace']))
        self.plugin_models_call_list = []
        for namespace_this in plugin_models_call_list_tmp:
            self.plugin_models_call_list.append(namespace_this['namespace'])
        self.log(2, 'Total count [' + str(total_models_count) + '] OlivOS plugin is loaded by OlivOS plugin shallow [' + self.Proc_name + ']')
