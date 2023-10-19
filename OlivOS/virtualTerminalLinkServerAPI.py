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
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

from gevent import pywsgi
from flask import Flask
from flask import current_app
from flask import request

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
    def __init__(self, Proc_name, scan_interval=0.001, dead_interval=1, rx_queue=None, tx_queue=None,
                 control_queue=None, logger_proc=None, debug_mode=False, bot_info_dict=None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='terminal_link',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            logger_proc=logger_proc,
            control_queue=control_queue
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_config['Flask_app'] = None
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['platform_bot_info_dict'] = None
        self.Proc_data['reply_event_pool'] = {}

    def run(self):
        time.sleep(2)
        self.log(2, 'OlivOS virtual terminal link server [' + self.Proc_name + '] is running')
        if self.Proc_data['bot_info_dict'].platform['model'] in ['postapi', 'ff14']:
            threading.Thread(
                target=self.set_flask,
                args=()
            ).start()
            while True:
                if self.Proc_info.rx_queue.empty():
                    time.sleep(self.Proc_info.scan_interval)
                else:
                    try:
                        rx_packet_data = self.Proc_info.rx_queue.get(block=False)
                    except:
                        rx_packet_data = None
                    if 'data' in rx_packet_data.key and 'action' in rx_packet_data.key['data']:
                        if 'reply' == rx_packet_data.key['data']['action']:
                            if 'data' in rx_packet_data.key['data'] and 'event_id' in rx_packet_data.key['data']:
                                self.Proc_data['reply_event_pool'][str(rx_packet_data.key['data']['event_id'])] = rx_packet_data.key['data']['data']
        elif self.Proc_data['bot_info_dict'].platform['model'] == 'default':
            self.send_init_event()
            while True:
                if self.Proc_info.rx_queue.empty():
                    time.sleep(self.Proc_info.scan_interval)
                else:
                    try:
                        rx_packet_data = self.Proc_info.rx_queue.get(block=False)
                    except:
                        rx_packet_data = None
                    if 'data' in rx_packet_data.key and 'action' in rx_packet_data.key['data']:
                        if 'input' == rx_packet_data.key['data']['action']:
                            if 'data' in rx_packet_data.key['data']:
                                # 增加 user_conf 配置字段
                                user_conf = None
                                user_name = "仑质"
                                if "user_conf" in rx_packet_data.key['data']:
                                    user_conf = rx_packet_data.key['data']['user_conf']
                                    if "user_name" in user_conf:
                                        user_name = user_conf['user_name']
                                sdk_event = OlivOS.virtualTerminalSDK.event(rx_packet_data,
                                                                            self.Proc_data['bot_info_dict'])
                                tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                                self.Proc_info.tx_queue.put(tx_packet_data, block=False)
                                self.send_log_event(
                                    rx_packet_data.key['data']['data'],
                                    name=user_name, 
                                    user_conf=user_conf
                                )

    def set_flask(self):
        self.Proc_config['Flask_app'] = Flask('__main__')
        with self.Proc_config['Flask_app'].app_context():
            @current_app.route('/', methods=['POST'])
            def Flask_server_func():
                res = '{}'
                status = 200
                header = {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'POST'
                }
                flag_active = False
                rx_packet_data_raw = request.get_data(as_text=True)
                try:
                    event_id = str(uuid.uuid4())
                    rx_packet_data = json.loads(rx_packet_data_raw)
                    sdk_event = OlivOS.virtualTerminalSDK.event(
                        rx_packet_data,
                        self.Proc_data['bot_info_dict'],
                        model=self.Proc_data['bot_info_dict'].platform['model'],
                        event_id=event_id
                    )
                    tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                    self.Proc_info.tx_queue.put(tx_packet_data, block=False)
                    flag_active = True
                except:
                    flag_active = False
                if self.Proc_data['bot_info_dict'].platform['model'] == 'ff14':
                    flag_active = False
                if flag_active:
                    for count_i in range(30 * 4):
                        if event_id in self.Proc_data['reply_event_pool']:
                            res = json.dumps(self.Proc_data['reply_event_pool'][event_id])
                            self.Proc_data['reply_event_pool'].pop(event_id)
                            break
                        time.sleep(0.25)
                return res, status, header
        server = pywsgi.WSGIServer(('0.0.0.0', self.Proc_data['bot_info_dict'].post_info.port),
                                   self.Proc_config['Flask_app'], log=None)
        server.serve_forever()

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
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block=False
            )

    def send_log_event(self, data, name, user_conf=None):
        self.sendControlEventSend('send', {
            'target': {
                'type': 'nativeWinUI'
            },
            'data': {
                'action': 'virtual_terminal',
                'event': 'log',
                'hash': self.Proc_data['bot_info_dict'].hash,
                'data': data,
                'name': name,
                'user_conf': user_conf
            }
        }
                                  )
