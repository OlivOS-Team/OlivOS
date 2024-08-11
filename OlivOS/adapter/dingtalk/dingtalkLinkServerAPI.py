# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/dingtalkLinkServerSDK.py
@Author    :   RainyZhou雨舟, OlivOS-Team
@Contact   :   thunderain_zhou@163.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''


import multiprocessing
import threading
import time
import json
import traceback
from weakref import proxy
import websocket
import ssl
import asyncio
import uuid
import requests as req

import OlivOS


gCheckList = [
    'default',
]

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval=0.001, dead_interval=1, rx_queue=None, tx_queue=None, logger_proc=None,
                 debug_mode=False, bot_info_dict=None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='dingtalk_link',
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
            'websocket_ticket': None,
            'pulse_interval': None,
            'last_s': None,
            'ws_obj': None,
            'ws_item': None
        }
        self.Proc_data['platform_bot_info_dict'] = None

    def run(self):
        self.log(2, 'OlivOS dingtalk link server [' + self.Proc_name + '] is running')
        while True:
            try:
                api_obj = OlivOS.dingtalkSDK.API.getGateway(
                    OlivOS.dingtalkSDK.get_SDK_bot_info_from_Plugin_bot_info(
                        self.Proc_data['bot_info_dict']
                    )
                )
                api_obj.do_api('POST')
                api_obj_json = api_obj.res
                if api_obj_json is not None:
                    if "endpoint" in api_obj_json:
                        self.Proc_data['extend_data']['websocket_url'] = api_obj_json['endpoint']
                    else:
                        self.Proc_data['extend_data']['websocket_url'] = None
                    if "ticket" in api_obj_json:
                        self.Proc_data['extend_data']['websocket_ticket'] = api_obj_json['ticket']
                    else:
                        self.Proc_data['extend_data']['websocket_ticket'] = None
            except:
                self.Proc_data['extend_data']['websocket_url'] = None
                self.Proc_data['extend_data']['websocket_ticket'] = None

            if self.Proc_data['extend_data']['websocket_url'] is not None and \
                self.Proc_data['extend_data']['websocket_ticket'] is not None:
                self.run_websocket_rx_connect_start()
            time.sleep(self.Proc_info.scan_interval)

    def on_message(self, ws: websocket.WebSocketApp, message):
        try:
            # ws.send()
            tmp_data_rx_obj = OlivOS.dingtalkSDK.PAYLOAD.rxPacket(
                data=json.loads(message)
            )
            if tmp_data_rx_obj.active:
                if tmp_data_rx_obj.data.type in [
                    "CALLBACK",
                    "EVENT",
                    # "SYSTEM"          # 系统消息仅在SDK做处理，不生成事件
                ]:
                    sdk_event = OlivOS.dingtalkSDK.event(tmp_data_rx_obj, self.Proc_data['bot_info_dict'])
                    tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                    self.Proc_info.tx_queue.put(tx_packet_data, block=False)

            # 对 ws 进行回复
            if tmp_data_rx_obj.data.type == "SYSTEM":
                if tmp_data_rx_obj.data.topic == "ping":
                    resp_data = OlivOS.dingtalkSDK.PAYLOAD.sendPong(tmp_data_rx_obj)
                    self.send(ws, resp_data)
                if tmp_data_rx_obj.data.topic == "disconnect":
                    self.log(0, 'OlivOS dingtalk link server [' + self.Proc_name + '] websocket link will be closed by remote!')
            elif tmp_data_rx_obj.data.type == "CALLBACK":
                resp_data = OlivOS.dingtalkSDK.PAYLOAD.replyCallback(tmp_data_rx_obj)
                self.send(ws, resp_data)
            elif tmp_data_rx_obj.data.type == "EVENT":
                resp_data = OlivOS.dingtalkSDK.PAYLOAD.replyEvent(tmp_data_rx_obj)
                self.send(ws, resp_data)

        except Exception as err:
            pass
            traceback.print_exc()

    def send(self, ws, payload_data):
        s = payload_data.dump()
        ws.send(s)

    def on_error(self, ws, error):
        self.log(0, 'OlivOS dingtalk link server [' + self.Proc_name + '] websocket link error')

    def on_close(self, ws, close_status_code, close_msg):
        self.log(0, 'OlivOS dingtalk link server [' + self.Proc_name + '] websocket link close')

    def on_open(self, ws):
        self.log(2, 'OlivOS dingtalk link server [' + self.Proc_name + '] websocket link start')

    def run_websocket_rx_connect_start(self):
        websocket.enableTrace(False)
        url_this = f"{self.Proc_data['extend_data']['websocket_url']}?ticket={self.Proc_data['extend_data']['websocket_ticket']}"
        ws = websocket.WebSocketApp(
            url_this,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.Proc_data['extend_data']['ws_obj'] = ws
        self.Proc_data['extend_data']['ws_item'] = uuid.uuid4()
        ws.run_forever(
            ping_interval=30,
            ping_timeout=5,
        )
        self.Proc_data['extend_data']['pulse_interval'] = None
        self.Proc_data['extend_data']['ws_obj'] = None
        self.Proc_data['extend_data']['ws_item'] = None
        self.Proc_data['extend_data']['websocket_url'] = None
        self.Proc_data['extend_data']['websocket_ticket'] = None
        self.log(2, 'OlivOS dingtalk link server [' + self.Proc_name + '] websocket link lost')
