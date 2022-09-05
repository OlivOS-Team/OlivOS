# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/virtualTerminalLinkServerAPI.py
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
import websocket
import ssl
import asyncio
import uuid
import requests as req

import OlivOS

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval = 0.001, dead_interval = 1, rx_queue = None, tx_queue = None, control_queue = None, logger_proc = None, debug_mode = False, bot_info_dict = None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name = Proc_name,
            Proc_type = 'terminal_link',
            scan_interval = scan_interval,
            dead_interval = dead_interval,
            rx_queue = rx_queue,
            tx_queue = tx_queue,
            logger_proc = logger_proc,
            control_queue = control_queue
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['platform_bot_info_dict'] = None

    def run(self):
        time.sleep(2)
        self.log(2, 'OlivOS virtual terminal link server [' + self.Proc_name + '] is running')
        self.send_init_event()
        while True:
            if self.Proc_info.rx_queue.empty():
                time.sleep(self.Proc_info.scan_interval)
            else:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block = False)
                except:
                    rx_packet_data = None
                if 'data' in rx_packet_data.key and 'action' in rx_packet_data.key['data']:
                        if 'input' == rx_packet_data.key['data']['action']:
                            if 'data' in rx_packet_data.key['data']:
                                sdk_event = OlivOS.virtualTerminalSDK.event(rx_packet_data, self.Proc_data['bot_info_dict'])
                                tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                                self.Proc_info.tx_queue.put(tx_packet_data, block = False)
                                self.send_log_event(rx_packet_data.key['data']['data'], '仑质')

    def send_init_event(self):
        self.sendControlEventSend('send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'virtual_terminal',
                    'event': 'init',
                    'hash': self.Proc_data['bot_info_dict'].hash
                }
            }
        )

    def sendControlEventSend(self, action, data):
        if self.Proc_info.control_queue != None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block = False
            )

    def send_log_event(self, data, name):
        self.sendControlEventSend('send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'virtual_terminal',
                    'event': 'log',
                    'hash': self.Proc_data['bot_info_dict'].hash,
                    'data': data,
                    'name': name
                }
            }
        )
