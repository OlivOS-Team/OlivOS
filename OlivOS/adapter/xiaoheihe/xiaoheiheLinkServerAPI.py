# -*- encoding: utf-8 -*-
r"""
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/xiaoheiheLinkServerAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
"""

import threading
import time
import json
import websocket
import uuid
import traceback

import OlivOS


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
        bot_info_dict=None,
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='xiaoheihe_link',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            logger_proc=logger_proc,
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['extend_data'] = {'websocket_url': None, 'pulse_interval': 30, 'ws_obj': None, 'ws_item': None}
        self.Proc_data['platform_bot_info_dict'] = None

    def run(self):
        self.log(2, 'OlivOS xiaoheihe link server [' + self.Proc_name + '] is running')
        while True:
            wss_url = OlivOS.xiaoheiheSDK.get_websocket_url(self.Proc_data['bot_info_dict'])
            self.Proc_data['extend_data']['websocket_url'] = wss_url
            if self.Proc_data['extend_data']['websocket_url'] is not None:
                self.run_websocket_rx_connect_start()
            time.sleep(10)

    def on_message(self, ws, message):
        try:
            tmp_data_rx_obj = OlivOS.xiaoheiheSDK.PAYLOAD.rxPacket(data=json.loads(message))
            # print(json.dumps(json.loads(message), indent=4, ensure_ascii=False))
            sdk_event = OlivOS.xiaoheiheSDK.event(tmp_data_rx_obj, self.Proc_data['bot_info_dict'])
            tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
            self.Proc_info.tx_queue.put(tx_packet_data, block=False)
        except Exception:
            pass

    def on_error(self, ws, error):
        self.log(0, 'OlivOS xiaoheihe link server [' + self.Proc_name + '] websocket link error')

    def on_close(self, ws, close_status_code, close_msg):
        self.log(0, 'OlivOS xiaoheihe link server [' + self.Proc_name + '] websocket link close')

    def on_open(self, ws):
        self.log(2, 'OlivOS xiaoheihe link server [' + self.Proc_name + '] websocket link start')

    def run_pulse(self):
        tmp_ws_item = self.Proc_data['extend_data']['ws_item']
        while self.Proc_data['extend_data']['pulse_interval'] is not None:
            tmp_pulse_interval = self.Proc_data['extend_data']['pulse_interval']
            if tmp_pulse_interval > 1:
                tmp_pulse_interval -= 1
            time.sleep(tmp_pulse_interval)
            tmp_data = OlivOS.xiaoheiheSDK.PAYLOAD.sendPing().dump()
            if (
                tmp_ws_item != self.Proc_data['extend_data']['ws_item']
                or self.Proc_data['extend_data']['ws_item'] is None
            ):
                self.log(0, 'OlivOS xiaoheihe link server [' + self.Proc_name + '] websocket pulse giveup')
                return
            if self.Proc_data['extend_data']['ws_obj'] is not None:
                try:
                    self.Proc_data['extend_data']['ws_obj'].send(tmp_data)
                    self.log(0, 'OlivOS xiaoheihe link server [' + self.Proc_name + '] websocket pulse send')
                except Exception:
                    break
            else:
                break
        self.log(0, 'OlivOS xiaoheihe link server [' + self.Proc_name + '] websocket pulse lost')
        return

    def run_websocket_rx_connect_start(self):
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            self.Proc_data['extend_data']['websocket_url'],
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close,
        )
        self.Proc_data['extend_data']['ws_obj'] = ws
        self.Proc_data['extend_data']['ws_item'] = uuid.uuid4()
        threading.Thread(target=self.run_pulse, args=()).start()
        ws.run_forever()
        self.Proc_data['extend_data']['pulse_interval'] = None
        self.Proc_data['extend_data']['ws_obj'] = None
        self.Proc_data['extend_data']['ws_item'] = None
        self.log(2, 'OlivOS xiaoheihe link server [' + self.Proc_name + '] websocket link lost')


def accountFix(bot_info_dict, logger_proc):
    res = {}
    for bot_info_dict_this in bot_info_dict:
        bot_hash = bot_info_dict_this
        if bot_info_dict[bot_hash].platform['sdk'] == 'xiaoheihe_link':
            this_msg = OlivOS.xiaoheiheSDK.API.getMe(
                OlivOS.xiaoheiheSDK.get_SDK_bot_info_from_Plugin_bot_info(bot_info_dict[bot_hash])
            )
            try:
                # 刷新至真实bot_id
                this_msg_res = this_msg.do_api()
                this_msg_res_obj = json.loads(this_msg_res)
                if this_msg_res_obj['code'] == 0:
                    if type(this_msg_res_obj['data']['id']) is str:
                        if this_msg_res_obj['data']['id'].isdigit():
                            logger_proc.log(
                                2,
                                '[xiaoheihe] account ['
                                + str(bot_info_dict[bot_hash].id)
                                + '] will be updated as ['
                                + str(this_msg_res_obj['data']['id'])
                                + ']',
                            )
                            bot_info_dict[bot_hash].id = int(this_msg_res_obj['data']['id'])
                            bot_info_dict[bot_hash].getHash()
                        else:
                            logger_proc.log(2, '[xiaoheihe] account [' + str(bot_info_dict[bot_hash].id) + '] not hit')
                    else:
                        logger_proc.log(2, '[xiaoheihe] account [' + str(bot_info_dict[bot_hash].id) + '] not hit')
                else:
                    logger_proc.log(2, '[xiaoheihe] account [' + str(bot_info_dict[bot_hash].id) + '] not hit')
                res[bot_info_dict[bot_hash].hash] = bot_info_dict[bot_hash]
            except Exception:
                logger_proc.log(
                    3,
                    '[xiaoheihe] account [' + str(bot_info_dict[bot_hash].id) + '] not hit:\n' + traceback.format_exc(),
                )
                continue
        else:
            res[bot_info_dict_this] = bot_info_dict[bot_info_dict_this]
    return res
