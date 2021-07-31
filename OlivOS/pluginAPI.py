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

import OlivOS

plugin_path = './plugin/app/'
sys.path.append(plugin_path)

class shallow(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name = 'native_plugin', scan_interval = 0.001, rx_queue = None, tx_queue = None, control_queue = None, logger_proc = None, debug_mode = False, plugin_func_dict = {}, bot_info_dict = {}, treading_mode = 'full', restart_gate = 10000, enable_auto_restart = False):
        OlivOS.API.Proc_templet.__init__(self, Proc_name = Proc_name, Proc_type = 'shallow', scan_interval = scan_interval, rx_queue = rx_queue, tx_queue = tx_queue, control_queue = control_queue, logger_proc = logger_proc)
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

    class rx_packet(object):
        def __init__(self, sdk_event):
            self.sdk_event = sdk_event

    def run(self):
        self.load_plugin_list()
        self.log(2, 'OlivOS plugin shallow [' + self.Proc_name + '] is running')
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
                        self.run_plugin_save()
                        self.Proc_info.control_queue.put(OlivOS.API.Control.packet('restart_do', self.Proc_name), block=False)
                        self.Proc_info.control_queue.put(OlivOS.API.Control.packet('init', self.Proc_name), block=False)
                        self.log(2, 'OlivOS plugin shallow [' + self.Proc_name + '] will restart')
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
                        self.log(2, 'OlivOS plugin shallow [' + self.Proc_name + '] call restart')
                        self.Proc_info.rx_queue.put(OlivOS.API.Control.packet('restart_do', self.Proc_name), block=False)


    def run_plugin(self, sdk_event):
        log_str_tmp = str(sdk_event.json)
        self.log(0, 'Received: ' + log_str_tmp)
        plugin_event = OlivOS.API.Event(sdk_event, self.log)
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id = plugin_event.base_info['self_id'],
            platform_sdk = plugin_event.platform['sdk'],
            platform_platform = plugin_event.platform['platform'],
            platform_model = plugin_event.platform['model']
        )
        if plugin_event_bot_hash in self.Proc_data['bot_info_dict']:
            plugin_event.bot_info = self.Proc_data['bot_info_dict'][plugin_event_bot_hash]
        else:
            self.log(3, 'Account [' + str(plugin_event.base_info['self_id']) + '] not found, please check your account config')
            plugin_event.active = False
        if plugin_event.active:
            for plugin_models_index_this in self.plugin_models_call_list:
                flag_support_found_dict = {}
                flag_support_found_dict['sdk'] = False
                flag_support_found_dict['platform'] = False
                flag_support_found_dict['model'] = False
                flag_support_found_dict['flag'] = False
                for plugin_model_support_this in self.plugin_models_dict[plugin_models_index_this]['support']:
                    if plugin_model_support_this['sdk'] == 'all':
                        flag_support_found_dict['sdk'] = True
                    elif plugin_model_support_this['sdk'] == plugin_event.platform['sdk']:
                        flag_support_found_dict['sdk'] = True
                    if plugin_model_support_this['platform'] == 'all':
                        flag_support_found_dict['platform'] = True
                    elif plugin_model_support_this['platform'] == plugin_event.platform['platform']:
                        flag_support_found_dict['platform'] = True
                    if plugin_model_support_this['model'] == 'all':
                        flag_support_found_dict['model'] = True
                    elif plugin_model_support_this['model'] == plugin_event.platform['model']:
                        flag_support_found_dict['model'] = True
                    if flag_support_found_dict['sdk'] and flag_support_found_dict['platform'] and flag_support_found_dict['model']:
                        flag_support_found_dict['flag'] = True
                if flag_support_found_dict['flag']:
                    self.plugin_event_router(plugin_event, self.plugin_models_dict[plugin_models_index_this]['model'])
                    self.log(0, 'event [' + str(plugin_event.plugin_info['func_type']) + '] call plugin [' + self.plugin_models_dict[plugin_models_index_this]['name'] + '] done')
        return

    def run_plugin_save(self):
        func_save_name = 'save'
        for plugin_models_index_this in self.plugin_models_call_list:
            if hasattr(self.plugin_models_dict[plugin_models_index_this]['model'].main.Event, func_save_name):
                self.plugin_models_dict[plugin_models_index_this]['model'].main.Event.save(plugin_event = None, Proc = self)
                self.log(2, 'OlivOS plugin [' + self.plugin_models_dict[plugin_models_index_this]['name'] + '] call [' + func_save_name + '] done')
        return

    def plugin_event_router(self, plugin_event, plugin_model):
        if hasattr(plugin_model.main.Event, plugin_event.plugin_info['func_type']):
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
        return

    def load_plugin_list(self):
        total_models_count = 0
        self.plugin_models_dict = {}
        skip_result = ''
        func_init_name = 'init'
        plugin_dir_list = os.listdir(plugin_path)
        for plugin_dir_this in plugin_dir_list:
            plugin_models_tmp = importlib.import_module(plugin_dir_this)
            if hasattr(plugin_models_tmp, 'main'):
                if hasattr(plugin_models_tmp.main, 'Event'):
                    try:
                        with open(plugin_path + plugin_dir_this + '/app.json', 'r', encoding = 'utf-8') as plugin_models_app_conf_f:
                            plugin_models_app_conf = json.loads(plugin_models_app_conf_f.read())
                    except:
                        plugin_models_app_conf = None
                    if plugin_models_app_conf == None:
                        skip_result = plugin_dir_this + '/app.json' + ' not found'
                    else:
                        plugin_models_dict_this = {}
                        plugin_models_dict_this['model'] = plugin_models_tmp
                        plugin_models_dict_this['appconf'] = plugin_models_app_conf
                        plugin_models_dict_this['priority'] = plugin_models_app_conf['priority']
                        plugin_models_dict_this['namespace'] = plugin_dir_this
                        plugin_models_dict_this['name'] = plugin_models_app_conf['name']
                        plugin_models_dict_this['support'] = plugin_models_app_conf['support']
                        self.plugin_models_dict[plugin_dir_this] = plugin_models_dict_this
                        if hasattr(plugin_models_tmp.main.Event, func_init_name):
                            plugin_models_tmp.main.Event.init(plugin_event = None, Proc = self)
                            self.log(2, 'OlivOS plugin [' + plugin_models_dict_this['name'] + '] call [' + func_init_name + '] done')
                        total_models_count += 1
                        self.log(2, 'OlivOS plugin [' + plugin_models_dict_this['name'] + '] is loaded by OlivOS plugin shallow [' + self.Proc_name + ']')
                        continue
                else:
                    skip_result = plugin_dir_this + '.main.Event' + ' not found'
            else:
                skip_result = plugin_dir_this + '.main' + ' not found'
            self.log(3, 'OlivOS plugin [' + plugin_dir_this + '] is skiped by OlivOS plugin shallow [' + self.Proc_name + ']: ' + skip_result)
        plugin_models_call_list_tmp = sorted(self.plugin_models_dict.values(), key = lambda i : (i['priority'], i['namespace']))
        self.plugin_models_call_list = []
        for namespace_this in plugin_models_call_list_tmp:
            self.plugin_models_call_list.append(namespace_this['namespace'])
        self.log(2, 'Total count [' + str(total_models_count) + '] OlivOS plugin is loaded by OlivOS plugin shallow [' + self.Proc_name + ']')
