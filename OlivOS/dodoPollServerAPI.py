# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/dodoPollServerAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import multiprocessing
import threading
import time
import json

import OlivOS

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval = 0.001, dead_interval = 1, rx_queue = None, tx_queue = None, logger_proc = None, debug_mode = False, bot_info_dict = None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name = Proc_name,
            Proc_type = 'dodo_poll',
            scan_interval = scan_interval,
            dead_interval = dead_interval,
            rx_queue = None,
            tx_queue = tx_queue,
            logger_proc = logger_proc
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['bot_info_update_id'] = {}
        self.Proc_data['bot_info_first'] = {}
        self.Proc_data['bot_info_token_life_counter'] = 1000
        self.Proc_data['bot_info_token_life'] = {}
        self.Proc_data['bot_info_island_list'] = {}

    def run(self):
        self.log(2, 'OlivOS dodo poll server [' + self.Proc_name + '] is running')
        while True:
            time.sleep(self.Proc_info.scan_interval)
            self.run_poll_list()

    def run_poll_list(self):
        for bot_info_this in self.Proc_data['bot_info_dict']:
            flag_not_attach = False
            bot_info_this_obj = self.Proc_data['bot_info_dict'][bot_info_this]
            if bot_info_this_obj.platform['sdk'] == 'dodo_poll':
                sdk_bot_info_this = OlivOS.dodoSDK.get_SDK_bot_info_from_Plugin_bot_info(bot_info_this_obj)
                flag_first_update = False
                if bot_info_this in self.Proc_data['bot_info_update_id']:
                    flag_first_update = False
                else:
                    self.Proc_data['bot_info_update_id'][bot_info_this] = 0
                    flag_first_update = True
                flag_need_extend = False
                if bot_info_this not in self.Proc_data['bot_info_token_life']:
                    flag_need_extend = True
                    self.Proc_data['bot_info_token_life'][bot_info_this] = self.Proc_data['bot_info_token_life_counter']
                else:
                    self.Proc_data['bot_info_token_life'][bot_info_this] -= 1
                    if self.Proc_data['bot_info_token_life'][bot_info_this] <= 0:
                        flag_need_extend = True
                        self.Proc_data['bot_info_token_life'][bot_info_this] = self.Proc_data['bot_info_token_life_counter']
                if flag_need_extend:
                    sdk_api_tmp_3 = OlivOS.dodoSDK.API.extendMyLife(sdk_bot_info_this)
                    sdk_api_res_3 = None
                    try:
                        sdk_api_res_3 = sdk_api_tmp_3.do_api()
                    except:
                        pass
                if bot_info_this not in self.Proc_data['bot_info_first']:
                    tmp_island_list = []
                    sdk_api_tmp = OlivOS.dodoSDK.API.getIslandList(sdk_bot_info_this)
                    sdk_api_res = None
                    try:
                        sdk_api_res = sdk_api_tmp.do_api()
                    except:
                        flag_not_attach = True
                    if not flag_not_attach:
                        try:
                            res_obj = json.loads(sdk_api_res)
                            if res_obj['status'] == 0:
                                if type(res_obj['data']) == dict:
                                    if type(res_obj['data']['islands']) == list:
                                        for tmp_islands_this in res_obj['data']['islands']:
                                            tmp_islands_this_dict = {
                                                'id': tmp_islands_this['id'],
                                                'title': tmp_islands_this['title']
                                            }
                                            tmp_island_list.append(tmp_islands_this_dict)
                                    else:
                                        continue
                                else:
                                    continue
                            else:
                                continue
                        except:
                            continue
                    self.Proc_data['bot_info_island_list'][bot_info_this] = tmp_island_list
                    self.Proc_data['bot_info_first'][bot_info_this] = True
                for tmp_island_list_this in self.Proc_data['bot_info_island_list'][bot_info_this]:
                    flag_not_attach_2 = False
                    sdk_api_tmp_2 = OlivOS.dodoSDK.API.getIslandUpdate(sdk_bot_info_this)
                    sdk_api_tmp_2.data.islandId = tmp_island_list_this['id']
                    sdk_api_res_2 = None
                    try:
                        sdk_api_res_2 = sdk_api_tmp_2.do_api()
                    except:
                        flag_not_attach_2 = True
                    if not flag_not_attach_2:
                        try:
                            res_obj_2 = json.loads(sdk_api_res_2)
                            tmp_message_id_max = self.Proc_data['bot_info_update_id'][bot_info_this]
                            if res_obj_2['status'] == 0:
                                if type(res_obj_2['data']) == dict:
                                    if type(res_obj_2['data']['messages']) == list:
                                        for tmp_messages_this in res_obj_2['data']['messages']:
                                            if self.Proc_data['bot_info_update_id'][bot_info_this] < tmp_messages_this['id']:
                                                if tmp_messages_this['uid'] != bot_info_this_obj.id:
                                                    sdk_event = OlivOS.dodoSDK.event(tmp_messages_this, bot_info_this_obj, sdk_api_tmp_2.data.islandId)
                                                    tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                                                    self.Proc_info.tx_queue.put(tx_packet_data, block = False)
                                            if tmp_message_id_max < tmp_messages_this['id']:
                                                tmp_message_id_max = tmp_messages_this['id']
                                        self.Proc_data['bot_info_update_id'][bot_info_this] = tmp_message_id_max
                                    else:
                                        continue
                                else:
                                    continue
                            else:
                                continue
                        except:
                            continue
                    time.sleep(1)

    def run_sdk_api(self, sdk_api):
        sdk_api.do_api()