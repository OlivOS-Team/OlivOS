# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/dodobotEAServerAPI.py
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
            Proc_type = 'dodobot_ea',
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
        self.log(2, 'OlivOS dodobot ea server [' + self.Proc_name + '] is running')
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
                asyncio.get_event_loop().run_until_complete(self.run_websockets_rx_connect())
            time.sleep(self.Proc_info.scan_interval)

    def run_websockets_rx_connect_start(self):
        asyncio.get_event_loop().run_until_complete(self.run_websockets_rx_connect())

    async def run_websockets_rx_connect(self):
        while True:
            try:
                async with websockets.connect(OlivOS.dodobotEASDK.websocket_host + ':' + str(OlivOS.dodobotEASDK.websocket_port)) as websocket:
                    while True:
                        tmp_recv_pkg = None
                        tmp_recv_pkg_data = None
                        tmp_recv_pkg_str = await websocket.recv()
                        try:
                            tmp_recv_pkg = json.loads(tmp_recv_pkg_str)
                        except:
                            tmp_recv_pkg = None
                        if tmp_recv_pkg != None and type(tmp_recv_pkg) == dict:
                            if 'Data' in tmp_recv_pkg:
                                if type(tmp_recv_pkg['Data']) == str:
                                    try:
                                        tmp_recv_pkg_data = json.loads(tmp_recv_pkg['Data'])
                                    except:
                                        tmp_recv_pkg_data = None
                        if tmp_recv_pkg_data != None:
                            for bot_info_this in self.Proc_data['bot_info_dict']:
                                bot_info_this_obj = self.Proc_data['bot_info_dict'][bot_info_this]
                                if bot_info_this_obj.id in self.Proc_data['platform_bot_info_dict']:
                                    sdk_bot_info_this = OlivOS.dodobotEASDK.get_SDK_bot_info_from_Plugin_bot_info(
                                        bot_info_this_obj,
                                        self.Proc_data['platform_bot_info_dict'][bot_info_this_obj.id]
                                    )
                                    sdk_event = OlivOS.dodobotEASDK.event(tmp_recv_pkg_data, sdk_bot_info_this)
                                    tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                                    self.Proc_info.tx_queue.put(tx_packet_data, block = False)
            except:
                time.sleep(self.Proc_info.scan_interval)
                tmp_recv_pkg_data = None

