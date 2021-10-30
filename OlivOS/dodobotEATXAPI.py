# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/dodobotEATXAPI.py
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
import websockets
import asyncio
import requests as req

import OlivOS

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval = 0.001, dead_interval = 1, rx_queue = None, tx_queue = None, logger_proc = None, debug_mode = False, bot_info_dict = None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name = Proc_name,
            Proc_type = 'dodobot_ea_tx',
            scan_interval = scan_interval,
            dead_interval = dead_interval,
            rx_queue = rx_queue,
            tx_queue = tx_queue,
            logger_proc = logger_proc
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['platform_bot_info_dict'] = None

    def run(self):
        self.log(2, 'OlivOS dodobot ea tx server [' + self.Proc_name + '] is running')
        while True:
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'OlivOS/0.0.1'
            }
            msg_res = req.request("GET", OlivOS.dodobotEASDK.post_host + ':' + str(OlivOS.dodobotEASDK.post_port) + '/GetAccounts', headers = headers, data = '')
            try:
                msg_res_obj = json.loads(msg_res.text)
                if 'Code' in msg_res_obj:
                    if msg_res_obj['Code'] == 200:
                        if 'Data' in msg_res_obj:
                            if type(msg_res_obj['Data']) == list:
                                self.Proc_data['platform_bot_info_dict'] = {}
                                for msg_res_obj_Data_this in msg_res_obj['Data']:
                                    tmp_platform_bot_info = OlivOS.dodobotEASDK.get_SDK_platform_bot_info_from_data(
                                        msg_res_obj_Data_this
                                    )
                                    if tmp_platform_bot_info != None:
                                        self.Proc_data['platform_bot_info_dict'][tmp_platform_bot_info.id] = tmp_platform_bot_info
            except:
                self.Proc_data['platform_bot_info_dict'] = None
            if self.Proc_data['platform_bot_info_dict'] != None:
                asyncio.get_event_loop().run_until_complete(self.run_websockets_tx_connect())
            time.sleep(self.Proc_info.scan_interval)

    class rx_packet(object):
        def __init__(self, pkg_type, data):
            self.pkg_type = pkg_type
            self.data = data

    def run_websockets_tx_connect_start(self):
        asyncio.get_event_loop().run_until_complete(self.run_websockets_tx_connect())

    async def run_websockets_tx_connect(self):
        while True:
            try:
                async with websockets.connect(OlivOS.dodobotEASDK.websocket_host + ':' + str(OlivOS.dodobotEASDK.websocket_port)) as websocket:
                    while True:
                        if self.Proc_info.rx_queue.empty():
                            time.sleep(self.Proc_info.scan_interval)
                        else:
                            try:
                                rx_packet_data = self.Proc_info.rx_queue.get(block = False)
                                if rx_packet_data.pkg_type == 'send':
                                    rx_packet_data_data = rx_packet_data.data
                                    if rx_packet_data_data['Account']['Uid'] in self.Proc_data['platform_bot_info_dict']:
                                        rx_packet_data_data['Account']['Token'] = self.Proc_data['platform_bot_info_dict'][rx_packet_data_data['Account']['Uid']].access_token
                                    await websocket.send(json.dumps(rx_packet_data_data))
                            except:
                                continue
            except:
                time.sleep(self.Proc_info.scan_interval)
                continue


