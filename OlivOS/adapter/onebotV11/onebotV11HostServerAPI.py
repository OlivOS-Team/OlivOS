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
import socket
import asyncio
import threading
import traceback
import websockets
from websockets import Response, Headers
from queue import Empty as QueueEmpty
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
QUEUE_TIMEOUT = 0.1


@dataclass
class ServerConf:
    """服务器配置类

    Attributes:
        url (str): 连接URL
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
        host = post_info.host.strip('ws://').strip('wss://')
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
        async_rx_queue (asyncio.Queue): 异步接收队列
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
        self.async_rx_queue = None
        self._running_event = threading.Event()
        self._running_event.set()

    def start(self) -> threading.Thread:
        """启动入口

        重写自基类的start方法,强制使用线程来运行事件循环

        Returns:
            threading.Thread: 运行事件循环的线程对象
        """
        proc_this = threading.Thread(
            target=lambda: asyncio.run(self.run()),
            name=self.Proc_name
        )
        proc_this.daemon = self.deamon  # 依旧仑质神秘小巧思
        proc_this.start()
        # self.Proc = proc_this
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
        proc_this = self.start()
        return proc_this

    async def producer(self, websocket: websockets.ServerConnection) -> None:
        """生产者

        即发送逻辑的执行者

        Args:
            websocket: WebSocket连接对象, 用于发送消息
        """
        while True:
            rx_packet_data: OlivOS.API.Control.packet = await self.async_rx_queue.get()
            try:
                data_part: dict = rx_packet_data.key.get('data', {})
                if data_part.get('action') == 'send':
                    payload = data_part.get('data')
                    if payload is not None:
                        if isinstance(payload, (dict, list)):
                            payload = json.dumps(payload)
                        await websocket.send(payload)
            except websockets.ConnectionClosed:
                break
            except Exception as e:
                self.on_error(e)
            finally:
                self.async_rx_queue.task_done()

    async def consumer(self, websocket: websockets.ServerConnection) -> None:
        """消费者

        即接收逻辑的执行者

        Args:
            websocket: WebSocket连接对象, 用于接收消息
        """
        async for raw_message in websocket:
            try:
                extra_info = {
                    'id': self.bot_info.id,
                    'token': self.conf.token,
                    'type': 'websocket_host'
                }
                sdk_event = OlivOS.onebotSDK.event(raw_message, extra_info)
                if not sdk_event.active:
                    continue
                tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                self.Proc_info.tx_queue.put(tx_packet_data, block=False)
            except Exception as e:
                self.on_error(e)

    def bridger(self, loop: asyncio.AbstractEventLoop) -> None:
        """队列桥接者

        单独开一个线程将rx_queue的数据搬运到异步队列,以此规避producer频繁调用to_thread带来的性能问题
        这基于rx_queue是multiprocessing.Queue对象, 事实上也的确是

        Args:
            loop: 当前事件循环对象
            async_rx_queue: producer使用的异步队列,用于接收数据
        """
        while self._running_event.is_set():
            try:
                rx_packet_data = self.Proc_info.rx_queue.get(timeout=1.0)
                loop.call_soon_threadsafe(
                    self.__safe_async_put,
                    rx_packet_data
                )
            except QueueEmpty:
                continue
            except EOFError:
                break
            except Exception as e:
                self.on_error(e)

    def __safe_async_put(self, data: OlivOS.API.Control.packet) -> None:
        """安全的异步队列入队逻辑"""
        try:
            self.async_rx_queue.put_nowait(data)
        except asyncio.QueueFull:
            pass

    def auther(
            self,
            connection: websockets.ServerConnection,
            request: websockets.Request
    ) -> Response | None:
        """验证者

        即鉴权逻辑的执行者
        为WebSocket服务器的process_request回调函数

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

    async def handler(self, websocket: websockets.ServerConnection) -> None:
        """处理WebSocket连接的协程

        Args:
            websocket: WebSocket连接对象, 用于传给consumer和producer接收和发送消息
        """
        self.on_open()

        consumer_task = asyncio.create_task(self.consumer(websocket))
        producer_task = asyncio.create_task(self.producer(websocket))
        try:
            done, pending = await asyncio.wait(
                [consumer_task, producer_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            # 取消所有待处理的任务
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.on_error(e)
        finally:
            self.on_close()

    async def run(self) -> None:
        """运行WebSocket服务器的主协程"""
        if not is_free_port(self.conf.host, self.conf.port):
            self.log(
                3,
                OlivOS.L10NAPI.getTrans(
                    'OlivOS onebotV11 host server [{0}] websocket link port [{1}] is in use',
                    [self.Proc_name, self.conf.port],
                    modelName
                )
            )
            self.on_lost()
            return

        loop = asyncio.get_running_loop()
        self.async_rx_queue = asyncio.Queue(maxsize=512)
        bridger_thread = threading.Thread(
            target=self.bridger,
            args=(loop,),
            name=f'{self.Proc_name}-Bridger',
            daemon=True
        )
        bridger_thread.start()

        async with websockets.serve(
            self.handler,
            self.conf.host,
            self.conf.port,
            process_request=self.auther
        ):
            self.on_run()
            while self._running_event.is_set():
                await asyncio.sleep(1.0)  # run forever
        self.on_lost()

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
            0,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] websocket link close',
                [self.Proc_name],
                modelName
            )
        )

    def on_lost(self) -> None:
        """连接丢失时的处理"""
        self.log(
            0,
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
