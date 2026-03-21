# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OneBotWSServer/onebotV11_ws/websocketServerAPI.py
@Author    :   RemiliaCat
@Contact   :   RemiliaNero@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   OneBot11 WebSocket Server Implementation
'''

import json
import asyncio
import threading
import websockets
from websockets import Response, Headers
import http

import OlivOS

modelName = 'onebotV11HostServerAPI'

gCheckList = [
    'default',
]

DEFAULT_SCAN_INTERVAL = 0.001
DEFAULT_DEAD_INTERVAL = 1
QUEUE_TIMEOUT = 0.1
RECONNECT_DELAY = 4


class server(OlivOS.API.Proc_templet):
    """OneBot11 WebSocket 服务器"""

    def __init__(
        self,
        Proc_name: str,
        scan_interval=0.001,
        dead_interval=1,
        rx_queue=None,
        tx_queue=None,
        control_queue=None,
        logger_proc=None,
        debug_mode=False,
        bot_info_dict=None,
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='onebotV11_link',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            control_queue=control_queue,
            logger_proc=logger_proc
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_config['host'] = bot_info_dict.post_info.host
        if (
            self.Proc_config['host'].startswith('ws://')
            or self.Proc_config['host'].startswith('wss://')
        ):
            self.Proc_config['host'] = self.Proc_config['host'].split('://', 1)[1]
        self.Proc_config['port'] = bot_info_dict.post_info.port
        self.Proc_config['access_token'] = bot_info_dict.post_info.access_token
        self.Proc_data['platform_bot_info_dict'] = None

    def start(self):
        """重写自基类的start方法，强制使用线程来运行事件循环"""
        proc_this = threading.Thread(
            target=lambda: asyncio.run(self.run()),
            name=self.Proc_name
        )
        proc_this.daemon = self.deamon
        proc_this.start()
        # self.Proc = proc_this
        return proc_this

    def start_unity(self, mode='threading'):
        """事实上参数mode已经没有意义了，目前强制新开一个线程来运行事件循环"""
        proc_this = self.start()
        return proc_this

    async def consumer(self, websocket):
        """消费者，即接收逻辑的执行者"""
        try:
            async for raw_message in websocket:
                try:
                    sdk_event = OlivOS.onebotSDK.event(raw_message)
                    if not sdk_event.active:
                        continue
                    tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                    self.Proc_info.tx_queue.put(tx_packet_data, block=False)
                except Exception:
                    continue
        except asyncio.CancelledError:
            raise
        finally:
            pass

    async def producer(self, websocket):
        """生产者，即发送逻辑的执行者"""
        try:
            while True:
                rx_packet_data = None
                try:
                    if not self.Proc_info.rx_queue.empty():
                        rx_packet_data = await asyncio.to_thread(
                            self.Proc_info.rx_queue.get
                        )
                except Exception:
                    await asyncio.sleep(QUEUE_TIMEOUT)
                    continue

                if rx_packet_data is not None:
                    try:
                        data_part = rx_packet_data.key.get('data', {})
                        if data_part.get('action') == 'send':
                            payload = data_part.get('data')
                            if payload:
                                if isinstance(payload, (dict, list)):
                                    payload = json.dumps(payload)
                                await websocket.send(payload)
                    except Exception:
                        pass
                else:
                    await asyncio.sleep(QUEUE_TIMEOUT)
        except asyncio.CancelledError:
            raise
        finally:
            pass

    async def handler(self, websocket):
        """处理WebSocket连接的协程"""
        self.on_open()

        consumer_task = asyncio.create_task(self.consumer(websocket))
        producer_task = asyncio.create_task(self.producer(websocket))
        try:
            done, pending = await asyncio.wait(
                [consumer_task, producer_task],
                return_when=asyncio.ALL_COMPLETED,
            )

            # 取消所有待处理的任务
            for task in pending:
                task.cancel()
                try:
                    await task
                except Exception:
                    self.on_error()

            # 取消所有任务
            for task in [consumer_task, producer_task]:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except Exception:
                        self.on_error()
        finally:
            self.on_close()

    async def run(self):
        """运行WebSocket服务器的主协程"""
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] is running on [{1}]',
                [
                    self.Proc_name,
                    f"ws://{self.Proc_config['host']}:{self.Proc_config['port']}/"
                ],
                modelName
            )
        )

        def process_request(connection, request):
            """验证客户端的访问令牌"""
            access_token = self.Proc_config.get('access_token', '')
            if not access_token:
                return None
            auth_header = request.headers.get('Authorization')
            if auth_header != f"Bearer {access_token}" and auth_header != access_token:
                client_token = auth_header.replace('Bearer ', '') if auth_header else 'None'
                self.log(
                    3,
                    OlivOS.L10NAPI.getTrans(
                        'OlivOS onebotV11 host server [{0}] websocket link unauthorized token: [{1}]',
                        [self.Proc_name, client_token],
                        modelName
                    )
                )
                res = Response(
                    http.HTTPStatus.UNAUTHORIZED,
                    reason_phrase='Unauthorized',
                    headers=Headers(),
                    body=b'Unauthorized'
                )
                return res
            return None

        while True:
            try:
                async with websockets.serve(
                    self.handler,
                    self.Proc_config['host'],
                    self.Proc_config['port'],
                    process_request=process_request
                ):
                    await asyncio.Future()  # run forever
            except Exception:
                self.log(
                    3,
                    OlivOS.L10NAPI.getTrans(
                        'OlivOS onebotV11 host server [{0}] websocket link lost',
                        [self.Proc_name],
                        modelName
                    )
                )
                self.log(
                    3,
                    OlivOS.L10NAPI.getTrans(
                        'OlivOS onebotV11 host server [{0}] websocket link will retry in {1}s',
                        [self.Proc_name, str(RECONNECT_DELAY)],
                        modelName
                    )
                )
                await asyncio.sleep(RECONNECT_DELAY)

    def on_open(self):
        """连接建立时的日志打印"""
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] websocket link start',
                [self.Proc_name],
                modelName
            )
        )

    def on_close(self):
        """连接关闭时的日志打印"""
        self.log(
            0,
            OlivOS.L10NAPI.getTrans(
                'OlivOS onebotV11 host server [{0}] websocket link close',
                [self.Proc_name],
                modelName
            )
        )

    def on_error(self):
        """发生错误时的日志打印"""
        self.log(
            2,
            OlivOS.L10NAPI.gketTrans(
                'OlivOS onebotV11 host server [{0}] websocket link error',
                [self.Proc_name],
                modelName
            )
        )
