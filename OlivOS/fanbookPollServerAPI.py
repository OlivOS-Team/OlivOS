# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/fanbookPollServerAPI.py
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
import traceback

import OlivOS

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval = 0.001, dead_interval = 1, rx_queue = None, tx_queue = None, logger_proc = None, debug_mode = False, bot_info_dict = None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name = Proc_name,
            Proc_type = 'fanbook_poll',
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
        self.log(2, 'OlivOS fanbook poll server [' + self.Proc_name + '] is running')
        flag_first = True
        while True:
            time.sleep(self.Proc_info.scan_interval)
            self.run_poll_list(flag_first)
            flag_first = False

    def run_poll_list(self, flag_first):
        for bot_info_this in self.Proc_data['bot_info_dict']:
            flag_not_attach = False
            bot_info_this_obj = self.Proc_data['bot_info_dict'][bot_info_this]
            if bot_info_this_obj.platform['sdk'] == 'fanbook_poll':
                sdk_bot_info_this = OlivOS.fanbookSDK.get_SDK_bot_info_from_Plugin_bot_info(bot_info_this_obj)
                flag_not_attach = False
                sdk_api_tmp = OlivOS.fanbookSDK.API.getUpdates(sdk_bot_info_this)
                sdk_api_res = None
                try:
                    sdk_api_res = sdk_api_tmp.do_api()
                except Exception as e:
                    flag_not_attach = True
                    skip_result = '%s\n%s' % (
                        str(e),
                        traceback.format_exc()
                    )
                    self.log(3, skip_result, [
                        ('fanbookPollServer', 'default')
                    ])
                if not flag_not_attach and not flag_first:
                    if bot_info_this in self.Proc_data['bot_info_first']:
                        try:
                            res_obj = json.loads(sdk_api_res)
                            if res_obj['ok'] == True:
                                if type(res_obj['result']) == list:
                                    for tmp_messages_this in res_obj['result']:
                                        sdk_event = OlivOS.fanbookSDK.event(tmp_messages_this, bot_info_this_obj)
                                        tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                                        self.Proc_info.tx_queue.put(tx_packet_data, block = False)
                                else:
                                    continue
                            else:
                                continue
                        except Exception as e:
                            skip_result = '%s\n%s\n[data]\n%s' % (
                                str(e),
                                traceback.format_exc(),
                                str(sdk_api_res)
                            )
                            self.log(3, skip_result, [
                                ('fanbookPollServer', 'default')
                            ])
                    else:
                        self.Proc_data['bot_info_first'][bot_info_this] = True

    def run_sdk_api(self, sdk_api):
        sdk_api.do_api()

def accountFix(bot_info_dict, logger_proc):
    res = {}
    for bot_info_dict_this in bot_info_dict:
        bot_hash = bot_info_dict_this
        if bot_info_dict[bot_hash].platform['sdk'] == 'fanbook_poll':
            this_msg = OlivOS.fanbookSDK.API.getMe(OlivOS.fanbookSDK.get_SDK_bot_info_from_Plugin_bot_info(bot_info_dict[bot_hash]))
            this_msg_2 = OlivOS.fanbookSDK.API.setBotPrivacyMode(OlivOS.fanbookSDK.get_SDK_bot_info_from_Plugin_bot_info(bot_info_dict[bot_hash]))
            try:
                #刷新至真实bot_id
                this_msg_res = this_msg.do_api()
                this_msg_res_obj = json.loads(this_msg_res)
                if this_msg_res_obj['ok'] == True:
                    if type(this_msg_res_obj['result']['id']) == int:
                        logger_proc.log(2, '[fanbook] account [' + str(bot_info_dict[bot_hash].id) + '] will be updated as [' + str(this_msg_res_obj['result']['id']) + ']')
                        bot_info_dict[bot_hash].id = this_msg_res_obj['result']['id']
                        bot_info_dict[bot_hash].getHash()
                    else:
                        logger_proc.log(2, '[fanbook] account [' + str(bot_info_dict[bot_hash].id) + '] not hit')
                else:
                    logger_proc.log(2, '[fanbook] account [' + str(bot_info_dict[bot_hash].id) + '] not hit')
                res[bot_info_dict[bot_hash].hash] = bot_info_dict[bot_hash]
                #刷新至私有模式
                if bot_info_dict[bot_hash].platform['model'] == 'private':
                    this_msg_2.data.owner_id = this_msg_res_obj['result']['owner_id']
                    this_msg_2.data.bot_id = this_msg_res_obj['result']['id']
                    this_msg_2.data.enable = True
                    this_msg_res_2 = this_msg_2.do_api()
                    logger_proc.log(2, '[fanbook] account [' + str(this_msg_res_obj['result']['id']) + '] set to private mode')
                continue
            except:
                logger_proc.log(2, '[fanbook] account [' + str(bot_info_dict[bot_hash].id) + '] not hit')
                continue
        else:
            res[bot_info_dict_this] = bot_info_dict[bot_info_dict_this]
    return res
