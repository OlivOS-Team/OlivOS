# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/onebotV12LinkServerAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import logging
import json
import multiprocessing
import threading
import time
import websocket
import uuid

import OlivOS

modelName = 'onebotV12LinkServerAPI'

gCheckList = [
    'onebotV12',
    'walleq',
    'walleq_hide',
    'walleq_show',
    'walleq_show_Android_Phone',
    'walleq_show_Android_Pad',
    'walleq_show_Android_Watch',
    'walleq_show_iPad',
    'walleq_show_old',
    'ComWeChatBotClient'
]

class server(OlivOS.API.Proc_templet):
    def __init__(
        self,
        Proc_name,
        scan_interval=0.001,
        dead_interval=1,
        rx_queue=None,
        tx_queue=None,
        logger_proc=None,
        debug_mode=False,
        bot_info_dict=None
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='onebotV12_link',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            logger_proc=logger_proc
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['bot_info_dict_sdk'] = OlivOS.onebotV12SDK.get_SDK_bot_info_from_Plugin_bot_info(
            bot_info_dict
        )
        self.Proc_data['extend_data'] = {
            'websocket_url': None,
            'pulse_interval': None,
            'last_s': None,
            'ws_obj': None,
            'ws_item': None
        }
        self.Proc_data['platform_bot_info_dict'] = None

    def run(self):
        self.log(2, OlivOS.L10NAPI.getTrans('OlivOS onebotV12 link server [{0}] is running', [self.Proc_name], modelName))
        threading.Thread(
            target=self.message_router,
            args=()
        ).start()
        while True:
            try:
                self.Proc_data['extend_data']['websocket_url'] = '%s:%d/' % (
                    self.Proc_data['bot_info_dict'].post_info.host,
                    self.Proc_data['bot_info_dict'].post_info.port
                )
            except:
                self.Proc_data['extend_data']['websocket_url'] = None
            if self.Proc_data['extend_data']['websocket_url'] is not None:
                self.run_websocket_rx_connect_start()
            self.log(3, OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV12 link server [{0}] websocket link will retry in {1}s',
                [self.Proc_name, str(4)],
                modelName
            ))
            time.sleep(4)

    def on_message(self, ws, message):
        try:
            tmp_data_rx_obj = OlivOS.onebotV12SDK.PAYLOAD.rxPacket(
                data=json.loads(message)
            )
            if tmp_data_rx_obj.active:
                if tmp_data_rx_obj.data.type == 'rxPacket':
                    sdk_event = OlivOS.onebotV12SDK.event(
                        tmp_data_rx_obj.data.data,
                        self.Proc_data['bot_info_dict_sdk']
                    )
                    if sdk_event.active:
                        tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                        self.Proc_info.tx_queue.put(tx_packet_data, block=False)
        except:
            pass

    def on_error(self, ws, error):
        self.log(0, OlivOS.L10NAPI.getTrans(
            'OlivOS onebotV12 link server [{0}] websocket link error',
            [self.Proc_name],
            modelName
        ))

    def on_close(self, ws, close_status_code, close_msg):
        self.log(0, OlivOS.L10NAPI.getTrans(
            'OlivOS onebotV12 link server [{0}] websocket link close',
            [self.Proc_name],
            modelName
        ))

    def on_open(self, ws):
        self.log(2, OlivOS.L10NAPI.getTrans(
            'OlivOS onebotV12 link server [{0}] websocket link start',
            [self.Proc_name],
            modelName
        ))

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
        proxy_set = OlivOS.webTool.get_system_proxy_tuple('http')
        ws.run_forever(http_proxy_host=proxy_set[0], http_proxy_port=proxy_set[1], proxy_type=proxy_set[2])
        self.Proc_data['extend_data']['pulse_interval'] = None
        self.Proc_data['extend_data']['ws_obj'] = None
        self.Proc_data['extend_data']['ws_item'] = None
        self.log(2, OlivOS.L10NAPI.getTrans(
            'OlivOS onebotV12 link server [{0}] websocket link lost',
            [self.Proc_name],
            modelName
        ))

    def message_router(self):
        while True:
            if self.Proc_data['extend_data']['ws_obj'] is None or self.Proc_info.rx_queue.empty():
                time.sleep(self.Proc_info.scan_interval)
            else:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block=False)
                except:
                    rx_packet_data = None
                if rx_packet_data is not None:
                    if 'data' in rx_packet_data.key and 'action' in rx_packet_data.key['data']:
                        if 'send' == rx_packet_data.key['data']['action']:
                            if 'data' in rx_packet_data.key['data']:
                                self.Proc_data['extend_data']['ws_obj'].send(rx_packet_data.key['data']['data'])
