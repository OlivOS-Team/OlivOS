# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/telegramPollServerAPI.py
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
            Proc_type = 'Telegram_poll',
            scan_interval = scan_interval,
            dead_interval = dead_interval,
            rx_queue = None,
            tx_queue = tx_queue,
            logger_proc = logger_proc
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['bot_info_update_id'] = {}

    def run(self):
        self.log(2, 'OlivOS telegram poll server [' + self.Proc_name + '] is running')
        while True:
            time.sleep(self.Proc_info.scan_interval)
            self.run_poll_list()

    def run_poll_list(self):
        for bot_info_this in self.Proc_data['bot_info_dict']:
            flag_not_attach = False
            bot_info_this_obj = self.Proc_data['bot_info_dict'][bot_info_this]
            if bot_info_this_obj.platform['sdk'] == 'telegram_poll':
                flag_first_update = False
                if bot_info_this in self.Proc_data['bot_info_update_id']:
                    flag_first_update = False
                else:
                    self.Proc_data['bot_info_update_id'][bot_info_this] = -1
                    flag_first_update = True
                sdk_bot_info_this = OlivOS.telegramSDK.get_SDK_bot_info_from_Plugin_bot_info(bot_info_this_obj)
                sdk_api_tmp = OlivOS.telegramSDK.API.getUpdates(sdk_bot_info_this)
                sdk_api_tmp.data.offset = self.Proc_data['bot_info_update_id'][bot_info_this]
                try:
                    sdk_api_tmp.do_api()
                except:
                    flag_not_attach = True
                if not flag_not_attach:
                    try:
                        res_obj = json.loads(sdk_api_tmp.res.text)
                        if type(res_obj['result']) == list and res_obj['result'] != []:
                            self.Proc_data['bot_info_update_id'][bot_info_this] = res_obj['result'][-1]['update_id'] + 1
                            if not flag_first_update:
                                for result_this in res_obj['result']:
                                    sdk_event = OlivOS.telegramSDK.event(result_this, 'poll', bot_info_this_obj)
                                    tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                                    self.Proc_info.tx_queue.put(tx_packet_data, block = False)
                    except:
                        pass
