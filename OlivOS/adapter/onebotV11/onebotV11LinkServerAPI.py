# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/onebotV11LinkServerAPI.py
@Author    :   RemiliaCat
@Contact   :   RemiliaNero@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   OneBot11 WebSocket-Forward Server Implementation
'''

import asyncio
import threading
import traceback
import websockets
from dataclasses import dataclass
from queue import Empty as QueueEmpty
from urllib.parse import urlparse, parse_qs

import OlivOS

modelName = 'onebotV11LinkServerAPI'

gCheckList = [
    'default',
    'napcat_default',
    'llonebot_default',
    'lagrange_default',
    'shamrock_default',
]


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
    url: str
    host: str
    port: int
    token: str
    route: str

    @classmethod
    def init_conf_from_post_info(cls, post_info: OlivOS.API.bot_info_T.post_info_T):
        """从bot_info.post_info中提取配置信息

        考虑到OlivOS当前设计并没有区分URL与HOST+PORT的概念
        我们暂且废用了post_info的PORT字段，而通过HOST字段解析完整的URL

        Args:
            post_info (OlivOS.API.bot_info_T.post_info_T): 通信相关的信息结构体
        """
        tmp_host = post_info.host
        parsed = urlparse(tmp_host)
        scheme = parsed.scheme
        host = parsed.hostname
        port = parsed.port
        route = parsed.path
        url = f"{scheme}://{host}:{port}{route}"
        token = post_info.access_token
        if token is None:
            params = parse_qs(parsed.query)
            token = params.get('access_token', [None])[0]
        return cls(url=url, host=host, port=port, token=token, route=route)


@dataclass
class ExtraConf:
    """额外配置项

    Attributes:
        queue_max_size (int): 最大队列大小
        queue_timeout (float): 队列超时时间
        retry_interval (float): 重试间隔
        retry_interval_to_link (float): 重试间隔，但是尝试连接时
    """
    queue_max_size: int = 512
    queue_timeout: float = 30
    retry_interval: float = 4
    retry_interval_to_link: float = 1

    @classmethod
    def init_extra_conf_from_extends(cls, extends: dict):
        """从bot_info.extends中提取配置信息

        Args:
            extends (dict): 额外配置项，来自OlivOS.API.bot_info_T.extends
        """
        return cls(
            queue_max_size=extends.get('queue_max_size', 512),
            queue_timeout=extends.get('queue_timeout', 30),
            retry_interval=extends.get('retry_interval', 4),
            retry_interval_to_link=extends.get('retry_interval_to_link', 1)
        )


class server(OlivOS.API.Proc_templet):
    """OneBot11 正向WebSocket 服务器

    通常使用OlivOS.onebotV11HostServerAPI.start_unity启动本服务器

    Attributes:
        Proc_name (str): 服务器进程名称
        scan_interval (float): 扫描间隔
        dead_interval (float): 枪毙间隔
        rx_queue (multiprocessing.Queue): 接收队列
        tx_queue (multiprocessing.Queue): 发送队列
        logger_proc (OlivOS.API.Proc_templet): 日志记录器
        debug_mode (bool): 是否开启调试模式
        bot_info (OlivOS.API.bot_info_T): 机器人信息
        ws_conn (websockets.ClientConnection): WebSocket连接
        async_rx_queue (asyncio.Queue): 异步接收队列
        conf (ServerConf): 服务器配置
        extra_conf (ExtraConf): 额外配置
    """

    def __init__(
        self,
        Proc_name,
        scan_interval=0.001,
        dead_interval=1,
        rx_queue=None,
        tx_queue=None,
        logger_proc=None,
        debug_mode=False,
        bot_info=None
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
            bot_info (OlivOS.API.bot_info_T): 机器人信息
        """
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='onebotV11_link',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            logger_proc=logger_proc
        )
        self.bot_info: OlivOS.API.bot_info_T = bot_info
        self.ws_conn: websockets.ClientConnection = None
        self.async_rx_queue: asyncio.Queue = None
        self.conf: ServerConf = ServerConf.init_conf_from_post_info(self.bot_info.post_info)
        self.extra_conf: ExtraConf = ExtraConf.init_extra_conf_from_extends(self.bot_info.extends)
        self.debug_mode = debug_mode
        self._running_event = threading.Event()
        self._running_event.set()

    def start(self) -> threading.Thread:
        """启动入口

        Returns:
            threading.Thread: 运行本服务器的线程
        """
        proc_this = threading.Thread(
            target=lambda: asyncio.run(self.run()),
            name=self.Proc_name
        )
        proc_this.daemon = self.deamon
        proc_this.start()
        # self.Proc = proc_this
        return proc_this

    def start_unity(self, mode='threading') -> threading.Thread:
        """Unity启动入口

        Args:
            mode(str) 运行模式, 无实际意义, 详情见OlivOS.onebotV11HostServerAPI.start_unity

        Returns:
            threading.Thread: 运行本服务器的线程
        """
        proc_this = self.start()
        return proc_this

    async def run(self) -> None:
        """主运行循环

        负责初始化并执行协调执行流程
        """
        self.async_rx_queue = asyncio.Queue(maxsize=self.extra_conf.queue_max_size)
        loop = asyncio.get_event_loop()
        bridge_thread = threading.Thread(
            target=self.__bridge_queue,
            name=f'{self.Proc_name}_bridge',
            args=(loop,),
            daemon=True
        )
        bridge_thread.start()

        while self._running_event.is_set():
            pending = []
            try:
                await self.__link_to_server()
                if self.ws_conn is None:
                    await asyncio.sleep(self.extra_conf.retry_interval_to_link)
                    continue
                self.on_open()
                rx_task = asyncio.create_task(self.rx_link())
                tx_task = asyncio.create_task(self.tx_link())
                done, pending = await asyncio.wait(
                    [rx_task, tx_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )
            except Exception as e:
                self.on_error(e)
            finally:
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                if self.ws_conn is not None:
                    await self.ws_conn.close()
                    self.on_close()
                self.ws_conn = None

                await asyncio.sleep(self.extra_conf.retry_interval)

    async def rx_link(self) -> None:
        """WS接收逻辑"""
        while True:
            try:
                raw = await self.ws_conn.recv()
                extra_info = {
                    'id': self.bot_info.id,
                    'token': self.conf.token,
                    'type': 'websocket'
                }
                sdk_event = OlivOS.onebotSDK.event(raw, extra_info)
                if not sdk_event.active:
                    continue
                tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                self.Proc_info.tx_queue.put(tx_packet_data)
            except (websockets.ConnectionClosedOK, asyncio.CancelledError):
                # 被动关闭/主动关闭
                break
            except websockets.ConnectionClosedError:
                # 非预期关闭
                self.on_lost()
            except Exception as e:
                self.on_error(e)

    async def tx_link(self) -> None:
        """WS发送逻辑"""
        while True:
            rx_packet_data: OlivOS.API.Control.packet = await self.async_rx_queue.get()
            try:
                data_part = rx_packet_data.key.get('data', {})
                if data_part.get('action') == 'send':
                    payload = data_part.get('data')
                    if payload is not None:
                        await self.ws_conn.send(payload)
            except (websockets.ConnectionClosedOK, asyncio.CancelledError):
                # 被动关闭/主动关闭
                break
            except websockets.ConnectionClosedError:
                # 非预期关闭
                self.on_lost()
            except Exception as e:
                self.on_error(e)
            finally:
                self.async_rx_queue.task_done()

    async def __link_to_server(self) -> None:
        """WS连接逻辑"""
        url = self.conf.url
        headers = {
            'Authorization': f'Bearer {self.conf.token}',
            'Content-Type': 'application/json'
        }
        try:
            try:
                self.ws_conn = await websockets.connect(url, additional_headers=headers)
            except TypeError:
                self.ws_conn = await websockets.connect(url, extra_headers=headers)
        except ConnectionRefusedError:
            self.ws_conn = None
        except Exception as e:
            self.on_error(e)
            self.ws_conn = None

    def __bridge_queue(self, loop: asyncio.AbstractEventLoop) -> None:
        """队列桥接逻辑

        接收队列rx_queue是multiprocessing.Queue, 而本模块基于异步协程, 需要进行队列桥接以优化性能
        通常情况下, 在线程中运行本方法

        Args:
            loop (asyncio.AbstractEventLoop): 异步事件循环
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
        """异步队列入队逻辑

        在连接启动时正常入队，在连接未启动时返回
        在队列已满时不再入队

        Args:
            data (OlivOS.API.Control.packet): 数据包
        """
        if self.ws_conn is None:
            return
        try:
            self.async_rx_queue.put_nowait(data)    # 过期消息不再塞入
        except asyncio.QueueFull:
            pass

    def on_open(self) -> None:
        """连接建立时的处理"""
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 link server [{0}] websocket link start',
                [self.Proc_name],
                modelName
            )
        )

    def on_close(self) -> None:
        """连接关闭时的处理"""
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 link server [{0}] websocket link close',
                [self.Proc_name],
                modelName
            )
        )
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 link server [{0}] websocket link will retry in {1}s',
                [self.Proc_name, self.extra_conf.retry_interval],
                modelName
            )
        )

    def on_lost(self) -> None:
        """连接丢失时的处理"""
        self.log(
            3,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 link server [{0}] websocket link lost',
                [self.Proc_name],
                modelName
            )
        )

    def on_error(self, error: Exception) -> None:
        """发生错误时的处理"""
        self.log(
            4,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 link server [{0}] websocket link error: \n{1}',
                [self.Proc_name, traceback.format_exc()],
                modelName
            )
        )
