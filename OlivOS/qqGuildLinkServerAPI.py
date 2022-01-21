# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqGuildLinkServerAPI.py
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
import websocket
import ssl
import asyncio
import uuid
import requests as req

import OlivOS

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval = 0.001, dead_interval = 1, rx_queue = None, tx_queue = None, logger_proc = None, debug_mode = False, bot_info_dict = None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name = Proc_name,
            Proc_type = 'qqGuild_link',
            scan_interval = scan_interval,
            dead_interval = dead_interval,
            rx_queue = rx_queue,
            tx_queue = tx_queue,
            logger_proc = logger_proc
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
        self.log(2, 'OlivOS qqGuild link server [' + self.Proc_name + '] is running')
        while True:
            api_obj = OlivOS.qqGuildSDK.API.getGateway(
                OlivOS.qqGuildSDK.get_SDK_bot_info_from_Plugin_bot_info(
                    self.Proc_data['bot_info_dict']
                )
            )
            try:
                api_obj.do_api('GET')
                api_obj_json = json.loads(api_obj.res)
                self.Proc_data['extend_data']['websocket_url'] = api_obj_json['url']
            except:
                self.Proc_data['extend_data']['websocket_url'] = None
            if self.Proc_data['extend_data']['websocket_url'] != None:
                self.run_websocket_rx_connect_start()
            time.sleep(self.Proc_info.scan_interval)

    def on_message(self, ws, message):
        try:
            tmp_data_rx_obj = OlivOS.qqGuildSDK.PAYLOAD.rxPacket(
                data = json.loads(message)
            )
            self.Proc_data['extend_data']['last_s'] = tmp_data_rx_obj.data.s
            if tmp_data_rx_obj.data.op == 0:
                if tmp_data_rx_obj.data.t in [
                    'MESSAGE_CREATE',
                    'DIRECT_MESSAGE_CREATE',
                    'AT_MESSAGE_CREATE'
                ]:
                    sdk_event = OlivOS.qqGuildSDK.event(tmp_data_rx_obj, self.Proc_data['bot_info_dict'])
                    tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                    self.Proc_info.tx_queue.put(tx_packet_data, block = False)
                elif tmp_data_rx_obj.data.t == 'READY':
                    self.log(0, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket identify ACK')
            elif tmp_data_rx_obj.data.op == 10:
                self.Proc_data['extend_data']['pulse_interval'] = tmp_data_rx_obj.data.d['heartbeat_interval'] / 1000
                tmp_data = OlivOS.qqGuildSDK.PAYLOAD.sendIdentify(
                    OlivOS.qqGuildSDK.get_SDK_bot_info_from_Plugin_bot_info(
                        self.Proc_data['bot_info_dict']
                    )
                ).dump()
                threading.Thread(
                    target = self.run_pulse,
                    args = ()
                ).start()
                ws.send(tmp_data)
                self.log(0, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket identify send')
            elif tmp_data_rx_obj.data.op == 11:
                self.log(0, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket pulse ACK')
        except:
            pass

    def on_error(self, ws, error):
        self.log(0, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket link error')

    def on_close(self, ws, close_status_code, close_msg):
        self.log(0, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket link close')

    def on_open(self, ws):
        self.log(2, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket link start')


    def run_pulse(self):
        tmp_ws_item = self.Proc_data['extend_data']['ws_item']
        while self.Proc_data['extend_data']['pulse_interval'] != None:
            tmp_pulse_interval = self.Proc_data['extend_data']['pulse_interval']
            if tmp_pulse_interval > 1:
                tmp_pulse_interval -= 1
            time.sleep(tmp_pulse_interval)
            tmp_data = OlivOS.qqGuildSDK.PAYLOAD.sendHeartbeat(
                self.Proc_data['extend_data']['last_s']
            ).dump()
            if tmp_ws_item != self.Proc_data['extend_data']['ws_item'] or self.Proc_data['extend_data']['ws_item'] == None:
                self.log(0, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket pulse giveup')
                return
            if self.Proc_data['extend_data']['ws_obj'] != None:
                try:
                    self.Proc_data['extend_data']['ws_obj'].send(tmp_data)
                    self.log(0, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket pulse send')
                except:
                    break
            else:
                break
        self.log(0, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket pulse lost')
        return

    def run_websocket_rx_connect_start(self):
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            self.Proc_data['extend_data']['websocket_url'],
            on_open = self.on_open,
            on_message = self.on_message,
            on_error = self.on_error,
            on_close = self.on_close
        )
        self.Proc_data['extend_data']['ws_obj'] = ws
        self.Proc_data['extend_data']['ws_item'] = uuid.uuid4()
        ws.run_forever()
        self.Proc_data['extend_data']['pulse_interval'] = None
        self.Proc_data['extend_data']['ws_obj'] = None
        self.Proc_data['extend_data']['ws_item'] = None
        self.log(2, 'OlivOS qqGuild link server [' + self.Proc_name + '] websocket link lost')
