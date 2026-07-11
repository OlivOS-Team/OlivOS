r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/milkyAutoServerAPI.py
@Author    :   RemiliaCat
@Contact   :   RemiliaNero@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

import OlivOS

import queue
import asyncio
import aiohttp
import threading
import traceback
from dataclasses import dataclass


modelName = 'milkyAutoServerAPI'

gCheckList = [
    'milky_default',
    'llonebot_milky',
    'lagrange_milky',
    'yogurt_milky'
]


@dataclass
class ServerConf:
    """服务器配置类

    Attributes:
        ws_url (str): WS连接URL
        post_url (str): POST上报地址
        host (str): 主机
        port (int): 端口
        token (str): TOKEN
    """
    ws_url: str
    http_url: str
    host: str
    port: int
    token: str

    @classmethod
    def init_conf_from_post_info(cls, post_info: OlivOS.API.bot_info_T.post_info_T):
        """从bot_info.post_info中提取配置信息

        Args:
            post_info (OlivOS.API.bot_info_T.post_info_T): 通信相关的信息结构体
        """
        host = post_info.host
        port = post_info.port
        if port is None:
            ws_url = f"ws://{host}:55001/event"
            http_url = f"http://{host}:55001/api"
        else:
            ws_url = f"ws://{host}:{port}/event"
            http_url = f"http://{host}:{port}/api"
        token = post_info.access_token
        return cls(ws_url=ws_url, http_url=http_url, host=host, port=port, token=token)


@dataclass
class ExtraConf:
    """额外配置项

    Attributes:
        retry_interval (float): 重试间隔
        queue_timeout (float): 队列超时时长
        max_tx_worker (int): 最多tx并发协程数
    """
    retry_interval: float = 4
    queue_timeout: float = 0.5
    max_http_worker: int = 16

    @classmethod
    def init_extra_conf_from_extends(cls, extends: dict):
        """从bot_info.extends中提取配置信息

        Args:
            extends (dict): 额外配置项，来自OlivOS.API.bot_info_T.extends
        """
        return cls(
            retry_interval=extends.get('retry_interval', 4),
            queue_timeout=extends.get('queue_timeout', 0.5),
            max_http_worker=extends.get('max_http_worker', 16)
        )


class server(OlivOS.API.Proc_templet):
    """Milky 自动连接 服务器

    实现 Milky 协议中的 POST请求上报 + WS事件推送 混合通信

    Attributes:
        Proc_name (str): 服务器线程名称
        Proc_name_short (str): 将标识Hash进行简化的服务器线程名称
        scan_interval (float): 抓奸间隔
        dead_interval (float): 枪毙间隔
        rx_queue (multiprocessing.Queue): 接收队列，从插件托盘接收控制请求
        tx_queue (multiprocessing.Queue): 发送队列，向OlivOS发送SDK事件包
        logger_proc (OlivOS.API.Proc_templet): 日志记录器
        debug_mode (bool): 是否开启调试模式
        bot_info (OlivOS.API.bot_info_T): 机器人信息
        session (aiohttp.ClientSession): 单次会话对象
        running_event (threading.Event): 事件锁
        conf (ServerConf): 服务器配置
        extra_conf (ExtraConf): 额外配置
    """

    def __init__(
        self,
        Proc_name: str,
        scan_interval: float = 0.001,
        dead_interval: float = 1,
        rx_queue=None,
        tx_queue=None,
        logger_proc: OlivOS.API.Proc_templet = None,
        bot_info: OlivOS.API.bot_info_T = None,
        debug_mode: bool = False,
    ) -> None:
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='milky_auto',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            logger_proc=logger_proc
        )
        self.bot_info: OlivOS.API.bot_info_T = bot_info
        self.conf: ServerConf = ServerConf.init_conf_from_post_info(self.bot_info.post_info)
        self.extra_conf: ExtraConf = ExtraConf.init_extra_conf_from_extends(self.bot_info.extends)
        self.session: aiohttp.ClientSession = None
        self.running_event = threading.Event()
        self.running_event.set()
        self.debug_mode = debug_mode
        self.Proc_name_short = f"OlivOS_milky_auto={self.bot_info.hash[:6]}"

    def start(self) -> threading.Thread:
        proc_this = threading.Thread(
            target=lambda: asyncio.run(self.run()),
            name=self.Proc_name
        )
        proc_this.daemon = self.deamon
        proc_this.start()
        return proc_this

    def start_unity(self, mode='threading') -> threading.Thread:
        """由于协程设计机制，强制以线程方式运行事件循环"""
        return self.start()

    async def run(self) -> None:
        """主运行循环"""
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {'Content-Type': 'application/json'}
        if self.conf.token:
            headers['Authorization'] = f'Bearer {self.conf.token}'
        while self.running_event.is_set():
            try:
                async with aiohttp.ClientSession(headers=headers, timeout=timeout) as session:
                    self.session = session
                    await self.__session_lifecycle()
            except asyncio.CancelledError:
                raise
            except aiohttp.ClientError:
                self.on_retry()
                await asyncio.sleep(self.extra_conf.retry_interval)
            except Exception as e:
                self.on_error(e)

    async def rx(self) -> None:
        """WS接收逻辑"""
        while True:
            is_open = False
            try:
                async with self.session.ws_connect(
                    self.conf.ws_url,
                    heartbeat=self.extra_conf.retry_interval
                ) as ws_conn:
                    self.on_open()
                    is_open = True
                    async for msg in ws_conn:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        raw = msg.json()
                        self.__tx_send(raw)
            except asyncio.CancelledError:
                if is_open:
                    self.on_close()
                raise
            except aiohttp.ClientConnectionError:
                if is_open:
                    self.on_lost()
                    self.on_close()
            except Exception:
                if is_open:
                    self.on_lost()
                    self.on_close()
                self.on_error(Exception(traceback.format_exc()))
            finally:
                await asyncio.sleep(self.extra_conf.retry_interval)

    async def tx(self) -> None:
        """POST发送逻辑"""
        while True:
            # OlivOS包解析
            try:
                rx_packet_data: OlivOS.API.Control.packet = await asyncio.to_thread(
                    self.Proc_info.rx_queue.get,
                    timeout=self.extra_conf.queue_timeout
                )
                ctrl_data = rx_packet_data.key.get('data', {})
                if ctrl_data.get('action') != 'send':
                    continue
                api_data = ctrl_data.get('data')
                if api_data is None:
                    continue
            except queue.Empty:
                continue
            except Exception as e:
                self.on_error(e)
                continue

            # 动作请求+响应推送
            tmp_url = f"{self.conf.http_url}/{api_data['action']}"
            payload = api_data['params']
            post_id = api_data['post_id']
            try:
                async with self.session.post(tmp_url, json=payload) as response:
                    raw = await response.json()
                    raw['post_id'] = post_id
            except Exception as e:
                raw = fake_response('failed', -1, str(e))
                raw['post_id'] = post_id
                if not isinstance(e, aiohttp.ClientError):
                    self.on_error(e)
            self.__tx_send(raw)

    async def __session_lifecycle(self) -> None:
        """单次会话生命周期

        主要用于统筹rx建立连接与tx上报数据，其中rx独立实现自动重连，tx则在出错时触发本方法的session重建
        由于self.tx执行串行post逻辑，当post长时未响应时会卡住rx_queue数据提取，故需要并发tx协程，即tx_tasks而非tx_task
        """
        rx_task = asyncio.create_task(self.rx())
        tx_tasks = [asyncio.create_task(self.tx()) for _ in range(self.extra_conf.max_http_worker)]
        pending = [rx_task] + tx_tasks
        try:
            done, pending_tasks = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if not task.exception():
                    continue
                raise task.exception()
        finally:
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

    def __tx_send(self, raw):
        sdk_event = OlivOS.milkySDK.event(raw)
        if not sdk_event.active:
            return
        tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
        self.Proc_info.tx_queue.put_nowait(tx_packet_data)

    def on_open(self) -> None:
        """连接建立时的处理"""
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS milky auto server [{0}] websocket link start',
                [self.Proc_name_short],
                modelName
            )
        )

    def on_close(self) -> None:
        """连接关闭时的处理"""
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS milky auto server [{0}] websocket link close',
                [self.Proc_name_short],
                modelName
            )
        )

    def on_retry(self) -> None:
        """连接重试时的处理"""
        self.log(
            3,
            OlivOS.L10NAPI.getTrans(
                'OlivOS milky auto server [{0}] websocket link will retry in {1}s',
                [self.Proc_name_short, self.extra_conf.retry_interval],
                modelName
            )
        )

    def on_lost(self) -> None:
        """连接丢失时的处理"""
        self.log(
            3,
            OlivOS.L10NAPI.getTrans(
                'OlivOS milky auto server [{0}] websocket link lost',
                [self.Proc_name_short],
                modelName
            )
        )

    def on_error(self, error: Exception) -> None:
        """发生错误时的处理"""
        self.log(
            4,
            OlivOS.L10NAPI.getTrans(
                'OlivOS milky auto server [{0}] websocket link error: \n{1}',
                [self.Proc_name_short, traceback.format_exc()],
                modelName
            )
        )


def fake_response(status: str, retcode: int, message: str, data: dict = None) -> dict:
    res = {
        'status': status,
        'retcode': retcode,
        'message': message
    }
    if data is not None:
        res['data'] = data
    return res
