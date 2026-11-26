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

import socket
import threading
import time
import traceback

from gevent import pywsgi
from flask import Flask
from flask import current_app
from flask import request

import OlivOS

modelName = 'flaskServerAPI'

# WebUI 在 init 列表里早于 flask 启动；用模块级登记，避免只靠 host.runtime 才能读到上报。
_http_post_servers = []
# 服务停掉后保留一份「明确离线」记录：账号不在 host.runtime 里时，WebUI 才
# 不会把它显示成「未知」。
_retired_activity = {}


def http_post_activity():
    """合并各 HTTP 上报服务的活动表。

    时间戳存的是绝对时刻，负值表示明确离线。按事件先后（时间戳绝对值）取胜，
    这样后到的明确离线不会被另一份较旧的在线记录盖掉。
    """
    merged = dict(_retired_activity)
    for server in list(_http_post_servers):
        for bot_hash, last_seen in server.account_activity().items():
            prev = merged.get(bot_hash)
            if prev is None or abs(last_seen) > abs(prev):
                merged[bot_hash] = last_seen
    return merged


def owns_port(proc_name, port):
    """判断本进程中已运行的 HTTP 上报服务是否正在占用指定端口。"""
    for server in list(_http_post_servers):
        if (
            getattr(server, 'Proc_name', None) == proc_name
            and getattr(server, 'Proc_config', {}).get('Flask_server_port') == port
            and not getattr(server, '_stop_requested', False)
            and getattr(server, '_wsgi_server', None) is not None
        ):
            return True
    return False


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
            Proc_type='flask_post_rx',
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
        # 监听对象要在热停止时显式 stop：StoppableThread.terminate 只会异步抛 SystemExit，
        # gevent 循环阻塞在等待 I/O 时收不到，旧监听会继续霸占端口并被新实例顶出活动登记表。
        self._wsgi_lock = threading.Lock()
        self._wsgi_server = None
        self._wsgi_thread_ident = None
        self._stop_watcher = None
        self._stop_done = None
        self._stop_requested = False
        # 记录各 HTTP 上报账号最近活动时间，供 WebUI 判断在线状态。
        post_accounts = {
            bot_hash: bot for bot_hash, bot in (bot_info_dict or {}).items()
            if isinstance(bot, OlivOS.API.bot_info_T)
            and bot.platform['sdk'] == 'onebot' and bot.post_info.type == 'post'
        }
        self._post_accounts = post_accounts
        self.activity = OlivOS.API.accountActivity(post_accounts)
        for bot_hash in post_accounts:
            _retired_activity.pop(bot_hash, None)
        _http_post_servers[:] = [
            server for server in _http_post_servers
            if server is not self and getattr(server, 'Proc_name', None) != self.Proc_name
        ]
        _http_post_servers.append(self)

    def __getstate__(self):
        state = self.__dict__.copy()
        state['_wsgi_lock'] = None
        state['_wsgi_server'] = None
        state['_wsgi_thread_ident'] = None
        state['_stop_watcher'] = None
        state['_stop_done'] = None
        return state

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._wsgi_lock = threading.Lock()

    def mark_post_seen(self, sdk_event):
        """记录一次 HTTP 上报，用于 WebUI 的在线判定。"""
        if not sdk_event.active:
            return
        self_id = str(sdk_event.base_info.get('self_id', ''))
        if not self_id:
            return
        platform = sdk_event.platform or {}
        hashed = OlivOS.API.getBotHash(
            bot_id=self_id,
            platform_sdk=platform.get('sdk'),
            platform_platform=platform.get('platform'),
            platform_model=platform.get('model'),
        )
        payload = getattr(sdk_event, 'json', None) or {}
        status = payload.get('status') if isinstance(payload, dict) else None
        offline = (
            isinstance(payload, dict)
            and payload.get('post_type') == 'meta_event'
            and payload.get('meta_event_type') == 'heartbeat'
            and isinstance(status, dict)
            and status.get('online') is False
        )
        if self._mark_activity(hashed, offline):
            return
        for bot_hash, bot in self._post_accounts.items():
            if (str(bot.id) == self_id
                    and bot.platform.get('sdk') == platform.get('sdk')
                    and bot.platform.get('platform') == platform.get('platform')):
                self._mark_activity(bot_hash, offline)
                return

    def _mark_activity(self, bot_hash, offline):
        if offline:
            return self.activity.mark_offline(bot_hash)
        return self.activity.mark(bot_hash)

    def account_activity(self):
        """返回各 HTTP 上报账号最近一次收到上报的时间，0 表示本次运行未收到。"""
        return self.activity.snapshot()

    def _stop_wsgi_server(self):
        with self._wsgi_lock:
            self._stop_requested = True
            tmp_server = self._wsgi_server
            tmp_watcher = self._stop_watcher
            tmp_done = self._stop_done
            same_thread = self._wsgi_thread_ident == threading.get_ident()
            self._wsgi_server = None
            self._stop_watcher = None
            self._stop_done = None
            self._wsgi_thread_ident = None
            if tmp_server is not None and not same_thread and tmp_watcher is not None:
                try:
                    tmp_watcher.send()
                except Exception:
                    tmp_watcher = None
        if tmp_server is None:
            return
        if not same_thread and tmp_watcher is not None and tmp_done is not None:
            if tmp_done.wait(timeout=3.0):
                return
        try:
            tmp_server.stop()
        except Exception:
            traceback.print_exc()

    def on_terminate(self):
        self._stop_wsgi_server()
        self.deregister()

    def on_parent_terminate(self):
        """父进程侧在终止本组件前调用。

        processing 模式下的子进程被 terminate() 不会回调本对象，登记会一直留着，
        仪表盘就会在停服后继续把账号显示成在线，直到活动窗口过期。
        """
        self.deregister()

    def deregister(self):
        _http_post_servers[:] = [server for server in _http_post_servers if server is not self]
        # 停服后这些账号不会再有上报：留一条「明确离线」记录，WebUI 显示离线
        # 而不是「未知」（活动表清成 0 就回到「本次运行未收到上报」）。
        retired_at = -time.monotonic()
        for bot_hash, last_seen in self.activity.snapshot().items():
            if last_seen > 0:
                _retired_activity[bot_hash] = retired_at
        self.activity.clear()

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

    def _log_running(self):
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

    def run(self):
        self.app()
        self.set_config()
        self.Proc_config['Flask_app'].config.from_object(self.Proc_config['config'])
        if self.Proc_config['config'].debug_mode:
            self._log_running()
            try:
                self.Proc_config['Flask_app'].run(
                    host=self.Proc_config['Flask_server_host'],
                    port=self.Proc_config['Flask_server_port']
                )
            finally:
                self.on_terminate()
        else:
            tmp_listen = (
                self.Proc_config['Flask_server_host'],
                self.Proc_config['Flask_server_port']
            )
            server_name = (
                socket.gethostname()
                if tmp_listen[0] in ('0.0.0.0', '::', '')
                else str(tmp_listen[0])
            )
            server = pywsgi.WSGIServer(
                tmp_listen,
                self.Proc_config['Flask_app'],
                log=None,
                environ={'SERVER_NAME': server_name}
            )
            done = threading.Event()
            watcher = None
            try:
                with self._wsgi_lock:
                    if self._stop_requested:
                        return
                    server.start()
                    self._wsgi_server = server
                    self._wsgi_thread_ident = threading.get_ident()
                    loop = getattr(server, 'loop', None)
                    if loop is not None and hasattr(loop, 'async_'):
                        watcher = loop.async_(ref=False)

                        def _stop_in_loop():
                            try:
                                server.stop()
                            except Exception:
                                traceback.print_exc()
                            finally:
                                try:
                                    watcher.stop()
                                except Exception:
                                    pass

                        watcher.start(_stop_in_loop)
                    self._stop_watcher = watcher
                    self._stop_done = done
            except Exception as error:
                self.log(
                    3,
                    f"OlivOS flask server [{self.Proc_config['Flask_name']}] 无法监听 "
                    f"[{tmp_listen[0]}:{tmp_listen[1]}]: {type(error).__name__}: {error}"
                )
                self.on_terminate()
                raise
            self._log_running()
            try:
                server.serve_forever()
            finally:
                with self._wsgi_lock:
                    self._wsgi_server = None
                    self._stop_watcher = None
                    self._stop_done = None
                    self._wsgi_thread_ident = None
                if watcher is not None:
                    try:
                        watcher.stop()
                        watcher.close()
                    except Exception:
                        pass
                self.on_terminate()
                done.set()
