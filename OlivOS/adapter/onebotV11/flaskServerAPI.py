# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/flaskServerAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

import multiprocessing
import time

from gevent import pywsgi
from flask import Flask
from flask import current_app
from flask import request

import OlivOS

modelName = 'flaskServerAPI'

gCheckList = [
    'default',
    'para_default',
    'gocqhttp',
    'gocqhttp_hide',
    'gocqhttp_show',
    'gocqhttp_show_Android_Phone',
    'gocqhttp_show_Android_Pad',
    'gocqhttp_show_Android_Watch',
    'gocqhttp_show_iPad',
    'gocqhttp_show_iMac',
    'gocqhttp_show_old',
    'napcat',
    'napcat_hide',
    'napcat_show',
    'napcat_show_new',
    'napcat_show_new_9_9_19',
    'napcat_show_old',
    'napcat_default',
    'llonebot_default',
    'lagrange_default',
    'shamrock_default',
]


class server(OlivOS.API.Proc_templet):
    def __init__(
        self, Proc_name, Flask_namespace, Flask_server_methods, Flask_host, Flask_port,
        tx_queue=None,
        debug_mode=False,
        logger_proc=None,
        scan_interval=0.001,
        dead_interval=16,
        Flask_server_xpath='/OlivOSMsgApi',
        bot_info_dict=None
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='Flask_rx',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=None,
            tx_queue=tx_queue,
            logger_proc=logger_proc
        )
        self.Proc_config['Flask_namespace'] = Flask_namespace
        self.Proc_config['Flask_app'] = None
        self.Proc_config['Flask_name'] = Proc_name
        self.Proc_config['Flask_server_xpath'] = Flask_server_xpath
        self.Proc_config['Flask_server_methods'] = Flask_server_methods
        self.Proc_config['Flask_server_host'] = Flask_host
        self.Proc_config['Flask_server_port'] = Flask_port
        self.Proc_config['config'] = self.config_T(debug_mode)
        # 记录各 HTTP 上报账号最近活动时间，供 WebUI 判断在线状态。
        self._post_slots = {}
        self._post_index = {}
        for bot_hash, bot in (bot_info_dict or {}).items():
            if not isinstance(bot, OlivOS.API.bot_info_T):
                continue
            if bot.platform['sdk'] != 'onebot' or bot.post_info.type != 'post':
                continue
            key = (bot.platform['sdk'], bot.platform['platform'], bot.platform['model'], str(bot.id))
            self._post_index[bot_hash] = len(self._post_slots)
            self._post_slots[key] = len(self._post_slots)
        self._post_last_seen = multiprocessing.Array('d', max(len(self._post_index), 1))

    def mark_post_seen(self, sdk_event):
        """记录一次 HTTP 上报，用于 WebUI 的在线判定。"""
        if not self._post_slots or not sdk_event.active:
            return
        self_id = str(sdk_event.base_info.get('self_id', ''))
        platform = sdk_event.platform
        slot = self._post_slots.get(
            (platform.get('sdk'), platform.get('platform'), platform.get('model'), self_id)
        )
        if slot is not None:
            self._post_last_seen[slot] = time.monotonic()

    def post_last_seen(self):
        """返回各 HTTP 上报账号最近一次收到上报的时间，0 表示本次运行未收到。"""
        return {bot_hash: self._post_last_seen[slot] for bot_hash, slot in self._post_index.items()}

    class config_T(object):
        def __init__(self, debug_mode):
            self.debug_mode = debug_mode

    def app(self):
        self.Proc_config['Flask_app'] = Flask(self.Proc_config['Flask_namespace'])
        return self.Proc_config['Flask_app']

    def set_config(self):
        with self.Proc_config['Flask_app'].app_context():
            @current_app.route(
                f"{self.Proc_config['Flask_server_xpath']}/<platform_path>/<sdk_path>/<model_path>",
                methods=self.Proc_config['Flask_server_methods']
            )
            def Flask_server_func(sdk_path, platform_path, model_path):
                sdk_event = OlivOS.onebotSDK.event(request.get_data(as_text=True))
                sdk_event.platform['sdk'] = sdk_path
                sdk_event.platform['platform'] = platform_path
                sdk_event.platform['model'] = model_path
                self.mark_post_seen(sdk_event)
                tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                try:
                    self.Proc_info.tx_queue.put(tx_packet_data, block=False)
                except Exception:
                    pass
                return '200'

    def run(self):
        self.app()
        self.set_config()
        self.Proc_config['Flask_app'].config.from_object(self.Proc_config['config'])
        self.log(
            2, OlivOS.L10NAPI.getTrans(
                'OlivOS flask server [{0}] is running on port [{1}]', [
                    self.Proc_config['Flask_name'],
                    str(self.Proc_config['Flask_server_port'])
                ],
                modelName
            )
        )
        self.log(
            2, OlivOS.L10NAPI.getTrans(
                'OlivOS flask server [{0}] is running on [{1}]', [
                    self.Proc_config['Flask_name'],
                    (
                        f"http://127.0.0.1:{self.Proc_config['Flask_server_port']}"
                        f"{self.Proc_config['Flask_server_xpath']}/qq/onebot/default"
                    )
                ],
                modelName
            )
        )
        if self.Proc_config['config'].debug_mode:
            self.Proc_config['Flask_app'].run(
                host=self.Proc_config['Flask_server_host'],
                port=self.Proc_config['Flask_server_port']
            )
        else:
            server = pywsgi.WSGIServer(
                (
                    self.Proc_config['Flask_server_host'],
                    self.Proc_config['Flask_server_port']
                ),
                self.Proc_config['Flask_app'],
                log=None
            )
            server.serve_forever()
