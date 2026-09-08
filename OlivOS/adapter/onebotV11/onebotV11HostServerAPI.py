# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/onebotV11HostServerAPI.py
@Author    :   RemiliaCat
@Contact   :   RemiliaNero@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   OneBot11 WebSocket-Reverse Server Implementation
'''

import json
import queue
import socket
import asyncio
import threading
import traceback
import websockets
from websockets import Response, Headers
from urllib.parse import urlparse
from dataclasses import dataclass
import http

import OlivOS

modelName = 'onebotV11HostServerAPI'

gCheckList = [
    'default',
    'napcat_default',
    'llonebot_default',
    'lagrange_default',
    'shamrock_default',
]

DEFAULT_SCAN_INTERVAL = 0.001
DEFAULT_DEAD_INTERVAL = 1
QUEUE_TIMEOUT = 0.01


@dataclass
class ServerConf:
    """服务器配置类

    Attributes:
        host (str): 连接HOST
        port (int): 连接PORT
        token (str): 连接TOKEN
        route (str): 连接路由
    """
    host: str
    port: int
    token: str
    route: str

    @classmethod
    def init_conf_from_post_info(cls, post_info: OlivOS.API.bot_info_T.post_info_T):
        """从bot_info.post_info中提取配置信息

        Args:
            post_info (OlivOS.API.bot_info_T.post_info_T): 通信相关的信息结构体
        """
        host = "127.0.0.1"
        parsed = urlparse(post_info.host)
        if parsed.hostname is not None:
            host = parsed.hostname
        port = post_info.port
        token = post_info.access_token
        route = None
        return cls(host=host, port=port, token=token, route=route)


class server(OlivOS.API.Proc_templet):
    """OneBot11 反向WebSocket 服务器

    Attributes:
        Proc_name (str): 服务器进程名称
        scan_interval (float): 扫描间隔
        dead_interval (float): 枪毙间隔
        rx_queue (multiprocessing.Queue): 接收队列
        tx_queue (multiprocessing.Queue): 发送队列
        logger_proc (OlivOS.API.Proc_templet): 日志记录器
        debug_mode (bool): 是否开启调试模式
        bot_info (OlivOS.API.bot_info_T): 机器人信息
        conf (ServerConf): 服务器配置
        running_event (threading.Event): 兼容性服务器开关
    """

    def __init__(
        self,
        Proc_name: str,
        scan_interval: float = 0.001,
        dead_interval: float = 1,
        rx_queue=None,
        tx_queue=None,
        control_queue=None,
        logger_proc=None,
        debug_mode=False,
        bot_info_dict=None,
    ) -> None:
        """构造函数

        Args:
            Proc_name (str): 服务器进程名称
            scan_interval (float): 扫描间隔
            dead_interval (float): 枪毙间隔
            rx_queue (multiprocessing.Queue): 接收队列
            tx_queue (multiprocessing.Queue): 发送队列
            logger_proc (OlivOS.API.Proc_templet): 日志记录器
            debug_mode (bool): 是否开启调试模式
            bot_info_dict (OlivOS.API.bot_info_T): 机器人信息
        """
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='onebotV11_host',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            control_queue=control_queue,
            logger_proc=logger_proc
        )
        self.debug_mode = debug_mode
        self.bot_info = bot_info_dict
        self.conf = ServerConf.init_conf_from_post_info(self.bot_info.post_info)
        self.extra_info = {'id': self.bot_info.id, 'token': self.conf.token, 'type': 'websocket_host'}
        self.running_event = threading.Event()
        self.running_event.set()

    def start(self) -> threading.Thread:
        """启动入口

        重写自基类的start方法,强制使用线程来运行事件循环

        Returns:
            threading.Thread: 运行事件循环的线程对象
        """
        proc_this = threading.Thread(
            target=lambda: asyncio.run(self.run()),
            name=self.Proc_name,
            daemon=self.deamon  # 依旧仑质神秘小巧思
        )
        proc_this.start()
        return proc_this

    def start_unity(self, mode: str = 'threading') -> threading.Thread:
        """Unity启动入口

        重写自基类的start_unity方法,强制使用线程来运行事件循环
        OlivOS是基于多线程/多进程设计的,事件循环必须在独立线程中运行,因此不支持其他模式

        Args:
            mode: 启动模式,默认为'threading',目前仅支持线程,且无法根据传入值切换

        Returns:
            threading.Thread: 运行事件循环的线程对象
        """
        return self.start()

    async def run(self) -> None:
        """运行WebSocket服务器的主运行循环"""
        if not is_free_port(self.conf.host, self.conf.port):
            self.on_occupy()
            self.conf.port = get_free_port(self.conf.host)

        while self.running_event.is_set():
            try:
                async with websockets.serve(
                    self.session,
                    self.conf.host,
                    self.conf.port,
                    process_request=self.auther
                ):
                    self.on_run()
                    while self.running_event.is_set():
                        await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.on_error(e)
            if self.running_event.is_set():
                await asyncio.sleep(1.0)
        self.on_lost()

    async def rx(self, ws_conn: websockets.ServerConnection) -> None:
        """接收器，即接收逻辑的实现

        Args:
            ws_conn: WebSocket连接对象, 用于接收消息
        """
        while True:
            try:
                raw = await ws_conn.recv()
                sdk_event = OlivOS.onebotSDK.event(raw, self.extra_info)
                if not sdk_event.active:
                    continue
                tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                try:
                    self.Proc_info.tx_queue.put_nowait(tx_packet_data)
                except queue.Full:
                    # 消费效率跟不上时直接丢弃
                    pass
            except asyncio.CancelledError:
                # 主动关闭
                raise
            except websockets.ConnectionClosedOK:
                # 被动关闭
                break
            except websockets.ConnectionClosedError:
                # 非预期关闭
                self.on_lost()  # 仅rx打印lost即可
                break
            except Exception as e:
                self.on_error(e)
                break

    async def tx(self, ws_conn: websockets.ServerConnection) -> None:
        """发送器，即发送逻辑的实现

        Args:
            ws_conn: WebSocket连接对象, 用于发送消息
        """
        while True:
            try:
                rx_packet_data: OlivOS.API.Control.packet = await asyncio.to_thread(
                    self.Proc_info.rx_queue.get,
                    timeout=QUEUE_TIMEOUT
                )
                data_part = rx_packet_data.key.get('data', {})
                if data_part.get('action') == 'send':
                    payload = data_part.get('data')
                    if payload is None:
                        continue
                    if isinstance(payload, (dict, list)):
                        payload = json.dumps(payload)
                    await ws_conn.send(payload)
            except queue.Empty:
                continue
            except asyncio.CancelledError:
                # 主动关闭
                raise
            except websockets.ConnectionClosedOK:
                # 被动关闭
                break
            except websockets.ConnectionClosedError:
                # 非预期关闭
                break
            except Exception as e:
                self.on_error(e)
                break

    def auther(
        self,
        connection: websockets.ServerConnection,
        request: websockets.Request
    ) -> Response | None:
        """验证器，即鉴权逻辑的实现

        WebSocket服务器的process_request回调函数

        Args:
            connection: WebSocket连接对象,未使用
            request: WebSocket请求对象

        Returns:
            Response | None: None表示成功,否则返回Response对象
        """
        token = self.conf.token
        if not token:
            return None
        auth_header = request.headers.get('Authorization')
        if auth_header != f"Bearer {token}" and auth_header != token:
            client_token = auth_header.replace('Bearer ', '') if auth_header else 'None'
            self.on_unauth(client_token)
            return Response(
                http.HTTPStatus.UNAUTHORIZED,
                reason_phrase='Unauthorized',
                headers=Headers(),
                body=b'Unauthorized'
            )
        return None

    async def session(self, ws_conn: websockets.ServerConnection) -> None:
        """会话管理器

        Args:
            ws_conn: WebSocket连接对象, 用于传给rx和tx接收和发送消息
        """
        self.on_open()
        rx_task = asyncio.create_task(self.rx(ws_conn))
        tx_task = asyncio.create_task(self.tx(ws_conn))
        pending = [rx_task, tx_task]
        try:
            await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            raise
        finally:
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            self.on_close()

    def on_run(self) -> None:
        """服务器启动时的处理"""
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] is running on [{1}]',
                [
                    self.Proc_name,
                    f"ws://{self.conf.host}:{self.conf.port}"
                ],
                modelName
            )
        )

    def on_open(self) -> None:
        """连接建立时的处理"""
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] websocket link start',
                [self.Proc_name],
                modelName
            )
        )

    def on_close(self) -> None:
        """连接关闭时的处理"""
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] websocket link close',
                [self.Proc_name],
                modelName
            )
        )

    def on_lost(self) -> None:
        """连接丢失时的处理"""
        self.log(
            3,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] websocket link lost',
                [self.Proc_name],
                modelName
            )
        )

    def on_error(self, error: Exception) -> None:
        """发生错误时的处理"""
        self.log(
            4,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] websocket link error: \n{1}',
                [self.Proc_name, traceback.format_exc()],
                modelName
            )
        )

    def on_occupy(self) -> None:
        self.log(
            3,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] websocket link port [{1}] is in use',
                [self.Proc_name, self.conf.port],
                modelName
            )
        )

    def on_unauth(self, token: str) -> None:
        """未验证通过的处理"""
        self.log(
            3,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] websocket link unauthorized token: [{1}]',
                [self.Proc_name, token],
                modelName
            )
        )


def is_free_port(host, port: int) -> bool:
    """检查端口是否可用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except (socket.error, OSError):
            return False


def get_free_port(host: str) -> int:
    """获取一个可用的端口号"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
