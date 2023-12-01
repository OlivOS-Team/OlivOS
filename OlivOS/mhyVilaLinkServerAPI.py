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
            'ws_item': None,
            'ws_PLogin': {
                'uid': 0,
                'token': '',
                'platform': 3,
                'app_id': 104,
                'device_id': ''
            }
        }
        self.Proc_data['platform_bot_info_dict'] = None

    def run(self):
        self.log(2, 'OlivOS mhyVila link server [' + self.Proc_name + '] is running')
        while True:
            sdk_bot_info = OlivOS.mhyVilaSDK.get_SDK_bot_info_from_Plugin_bot_info(
                self.Proc_data['bot_info_dict']
            )
            api_obj = OlivOS.mhyVilaSDK.API.getWebsocketInfo(sdk_bot_info)
            try:
                api_obj.do_api('GET')
                api_obj_json = json.loads(api_obj.res)
                if api_obj_json['retcode'] == 0:
                    self.Proc_data['extend_data']['ws_PLogin']['uid'] = int(api_obj_json['data']['uid'])
                    self.Proc_data['extend_data']['ws_PLogin']['token'] = '%s.%s.%s' % (
                        str(sdk_bot_info.vila_id),
                        OlivOS.mhyVilaSDK.get_bot_secret(sdk_bot_info),
                        str(sdk_bot_info.bot_id)
                    )
                    self.Proc_data['extend_data']['ws_PLogin']['platform'] = int(api_obj_json['data']['platform'])
                    self.Proc_data['extend_data']['ws_PLogin']['app_id'] = int(api_obj_json['data']['app_id'])
                    self.Proc_data['extend_data']['ws_PLogin']['device_id'] = str(api_obj_json['data']['device_id'])
                    self.Proc_data['extend_data']['websocket_url'] = api_obj_json['data']['websocket_url']
                else:
                    self.Proc_data['extend_data']['websocket_url'] = None
            except:
                self.Proc_data['extend_data']['websocket_url'] = None
            if self.Proc_data['extend_data']['websocket_url'] is not None:
                self.run_websocket_rx_connect_start()
            time.sleep(10)

    def on_data(self, ws:websocket.WebSocketApp, data, opcode, FIN):
        #print([data, opcode, FIN])
        pass

    def on_message(self, ws:websocket.WebSocketApp, message):
        try:
            #print(message)
            messageObj = OlivOS.mhyVilaSDK.PAYLOAD.rxPacket(message)
            if messageObj.dataHeader.BizType in [
                OlivOS.mhyVilaSDK.protoEnum.Model_ROBOTEVENT.value
            ]:
                sdk_event = OlivOS.mhyVilaSDK.event(
                    messageObj.dataHeader.BizType,
                    messageObj.dataTable,
                    self.Proc_data['bot_info_dict']
                )
                tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                self.Proc_info.tx_queue.put(tx_packet_data, block=False)
        except Exception as e:
            traceback.print_exc()

    def on_error(self, ws:websocket.WebSocketApp, error):
        self.log(0, 'OlivOS mhyVila link server [' + self.Proc_name + '] websocket link error')

    def on_close(self, ws:websocket.WebSocketApp, close_status_code, close_msg):
        self.log(0, 'OlivOS mhyVila link server [' + self.Proc_name + '] websocket link close')

    def on_open(self, ws:websocket.WebSocketApp):
        self.send_PLogin(ws)
        threading.Thread(
            target=self.run_pulse,
            args=()
        ).start()
        self.log(2, 'OlivOS mhyVila link server [' + self.Proc_name + '] websocket link start')

    def run_pulse(self):
        tmp_ws_item = self.Proc_data['extend_data']['ws_item']
        while self.Proc_data['extend_data']['pulse_interval'] is not None:
            tmp_pulse_interval = self.Proc_data['extend_data']['pulse_interval']
            time.sleep(tmp_pulse_interval)
            tmp_data = OlivOS.mhyVilaSDK.PAYLOAD.PHeartBeat().dump()
            if tmp_ws_item != self.Proc_data['extend_data']['ws_item'] or self.Proc_data['extend_data']['ws_item'] is None:
                self.log(0, 'OlivOS mhyVila link server [' + self.Proc_name + '] websocket pulse giveup')
                return
            if self.Proc_data['extend_data']['ws_obj'] is not None:
                try:
                    self.Proc_data['extend_data']['ws_obj'].send(tmp_data, opcode=websocket.ABNF.OPCODE_BINARY)
                    self.log(0, 'OlivOS mhyVila link server [' + self.Proc_name + '] websocket pulse send')
                except:
                    break
            else:
                break
        self.log(0, 'OlivOS mhyVila link server [' + self.Proc_name + '] websocket pulse lost')
        return

    def send_PLogin(self, ws:websocket.WebSocketApp):
        tmp_data = OlivOS.mhyVilaSDK.PAYLOAD.PLogin()
        tmp_data.data.uid = self.Proc_data['extend_data']['ws_PLogin']['uid']
        tmp_data.data.token = self.Proc_data['extend_data']['ws_PLogin']['token']
        tmp_data.data.platform = self.Proc_data['extend_data']['ws_PLogin']['platform']
        tmp_data.data.app_id = self.Proc_data['extend_data']['ws_PLogin']['app_id']
        tmp_data.data.device_id = self.Proc_data['extend_data']['ws_PLogin']['device_id']
        tmp_data.dump()
        #print(tmp_data)
        ws.send(tmp_data.raw, opcode=websocket.ABNF.OPCODE_BINARY)

    def run_websocket_rx_connect_start(self):
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            self.Proc_data['extend_data']['websocket_url'],
            on_open=self.on_open,
            on_message=self.on_message,
            on_data=self.on_data,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.Proc_data['extend_data']['ws_obj'] = ws
        self.Proc_data['extend_data']['ws_item'] = uuid.uuid4()
        self.Proc_data['extend_data']['pulse_interval'] = 20
        ws.run_forever()
        self.Proc_data['extend_data']['pulse_interval'] = None
        self.Proc_data['extend_data']['ws_obj'] = None
        self.Proc_data['extend_data']['ws_item'] = None
        self.log(2, 'OlivOS mhyVila link server [' + self.Proc_name + '] websocket link lost')
