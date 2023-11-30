# -*- encoding: utf-8 -*-
'''
@ _______________________    ________________ 
@ __  __ \__  /____  _/_ |  / /_  __ \_  ___/ 
@ _  / / /_  /  __  / __ | / /_  / / /____ \  
@ / /_/ /_  /____/ /  __ |/ / / /_/ /____/ /  
@ \____/ /_____/___/  _____/  \____/ /____/   
@                                             
@File      :   OlivOS/mhyVilaLinkServerAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL3
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import multiprocessing
import threading
import time
import json
import websocket
import uuid
import requests as req
import traceback

import OlivOS


class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval=0.001, dead_interval=1, rx_queue=None, tx_queue=None, logger_proc=None,
                 debug_mode=False, bot_info_dict=None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='mhyVila_link',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            logger_proc=logger_proc
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['extend_data'] = {
            'websocket_url': None,
            'pulse_interval': None,
            'last_s': None,
            'ws_obj': None,
            'ws_item': None
        }
        self.Proc_data['platform_bot_info_dict'] = None

    def run(self):
        self.log(2, 'OlivOS kaiheila link server [' + self.Proc_name + '] is running')
        while True:
            api_obj = OlivOS.mhyVilaSDK.API.getWebsocketInfo(
                OlivOS.mhyVilaSDK.get_SDK_bot_info_from_Plugin_bot_info(
                    self.Proc_data['bot_info_dict']
                )
            )
            try:
                api_obj.do_api('GET')
                api_obj_json = json.loads(api_obj.res)
                if api_obj_json['retcode'] == 0:
                    self.Proc_data['extend_data']['websocket_url'] = api_obj_json['data']['websocket_url']
                else:
                    self.Proc_data['extend_data']['websocket_url'] = None
            except:
                self.Proc_data['extend_data']['websocket_url'] = None
            print(self.Proc_data['extend_data']['websocket_url'])
            #if self.Proc_data['extend_data']['websocket_url'] is not None:
            #    self.run_websocket_rx_connect_start()
            time.sleep(10)

    def on_message(self, ws, message):
        try:
            print(message)
        except:
            pass

    def on_error(self, ws, error):
        self.log(0, 'OlivOS kaiheila link server [' + self.Proc_name + '] websocket link error')

    def on_close(self, ws, close_status_code, close_msg):
        self.log(0, 'OlivOS kaiheila link server [' + self.Proc_name + '] websocket link close')

    def on_open(self, ws):
        self.log(2, 'OlivOS kaiheila link server [' + self.Proc_name + '] websocket link start')

    def run_websocket_rx_connect_start(self):
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            self.Proc_data['extend_data']['websocket_url'],
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.Proc_data['extend_data']['ws_obj'] = ws
        self.Proc_data['extend_data']['ws_item'] = uuid.uuid4()
        ws.run_forever()
        self.Proc_data['extend_data']['pulse_interval'] = None
        self.Proc_data['extend_data']['ws_obj'] = None
        self.Proc_data['extend_data']['ws_item'] = None
        self.log(2, 'OlivOS kaiheila link server [' + self.Proc_name + '] websocket link lost')
