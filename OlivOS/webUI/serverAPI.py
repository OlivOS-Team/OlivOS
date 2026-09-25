# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/webUI/serverAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

# Control 总线订阅者；Flask REST 与 WebSocket 共用一个监听端口。

import asyncio
import copy
import errno
import hmac
import io
import json
import os
import queue
import secrets
import tempfile
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import WSMsgType, web
import psutil
from flask import Flask
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Response

import OlivOS

from . import pageAPI, resourceAPI, staticData

BUFFER_LIMIT = 500
# 插件页面 iframe 保活数量上限：实测每个约 11MB，首个会拉起独立渲染进程（约 90MB）
PLUGIN_PAGE_CACHE = 10
PLUGIN_PAGE_CACHE_MAX = 20
TERMINAL_TYPES = {
    'napcat': 'napcat_lib_exe_model',
    'gocqhttp': 'gocqhttp_lib_exe_model',
    'walleq': 'walleq_lib_exe_model',
    'cwcb': 'cwcb_lib_exe_model',
    'opqbot': 'opqbot_lib_exe_model',
    'virtual_terminal': 'terminal_link',
}
DEFAULT_SERVER = {
    'auto': False, 'type': 'http', 'host': '127.0.0.1', 'port': 20480,
    'token_path': './conf/webui_token.txt', 'static_path': './data/webui/static', 'buffer_limit': BUFFER_LIMIT,
    'plugin_page_cache': PLUGIN_PAGE_CACHE,
}
ACTIVE_LISTENERS = {}


def apply_environment_config(config):
    """环境变量覆盖监听配置，仅影响当前进程，不写回配置文件。"""
    host = os.environ.get('OLIVOS_WEBUI_HOST')
    if isinstance(host, str) and host.strip():
        config['host'] = host.strip()

    port = os.environ.get('OLIVOS_WEBUI_PORT')
    if port is not None:
        try:
            port_value = int(port)
        except (TypeError, ValueError):
            port_value = None
        if port_value is not None and 0 <= port_value <= 65535:
            config['port'] = port_value
    return config


class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name='OlivOS_webUI', scan_interval=0.02, dead_interval=1,
                 rx_queue=None, tx_queue=None, control_queue=None, logger_proc=None,
                 bot_info_dict=None, server_conf=None, account_path='./conf/account.json',
                 runtime=None, root_path=None):
        super().__init__(Proc_name, 'webUI', scan_interval, dead_interval, rx_queue, tx_queue,
                         control_queue, logger_proc)
        self.root = Path(root_path or os.getcwd()).resolve()
        self.config = apply_environment_config(dict(DEFAULT_SERVER, **(server_conf or {})))
        self.account_path = self.root / account_path
        self.runtime = runtime if runtime is not None else {}
        self.started_at = time.monotonic()
        self._browser_key = secrets.token_bytes(32)
        self.lock = threading.RLock()
        self.accounts = copy.deepcopy(bot_info_dict or {})
        self.limit = max(8, min(int(self.config['buffer_limit']), 4096))
        # 配置写坏时退回默认值，避免 WebUI 连带整个实例启动失败
        try:
            plugin_page_cache = int(self.config['plugin_page_cache'])
        except (TypeError, ValueError):
            plugin_page_cache = PLUGIN_PAGE_CACHE
        self.plugin_page_cache = max(1, min(plugin_page_cache, PLUGIN_PAGE_CACHE_MAX))
        self.streams = {'logs': deque(maxlen=self.limit), 'events': deque(maxlen=self.limit)}
        self.log_levels = {level: deque(maxlen=self.limit) for level in OlivOS.diagnoseAPI.level_dict}
        self.sequence = 0
        self.terminals = {}
        self.plugins = {}
        self.plugin_order = []
        self.plugin_priority = {}
        self.plugin_pages = []
        self.plugin_roots = {}
        self.plugin_webui_paths = {}
        self.retired_plugin_roots = set()
        self.update_available = False
        self.pending = {}
        self.sessions = {}
        self.failures = OrderedDict()
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.error = None
        self.listen_path = self.root / 'data/webui/listen.json'
        self.loop = None
        self.sockets = set()
        token_path = self.root / self.config['token_path']
        token_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(str(token_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            self.token = token_path.read_text(encoding='utf-8').strip()
        else:
            self.token = secrets.token_urlsafe(32)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as token_file:
                token_file.write(self.token)
        if len(self.token) < 32:
            raise ValueError('WebUI token 文件无效，请恢复或移走该文件后重新启动')
        static_override = os.environ.get('OLIVOS_WEBUI_STATIC')
        if static_override:
            self.static_path = Path(static_override).resolve()
            if not all((self.static_path / name).is_file() for name in staticData.FILES):
                raise ValueError('OLIVOS_WEBUI_STATIC 中缺少前端资源')
        else:
            self.static_path = staticData.releaseBase64Data(self.root / self.config['static_path'])
        self.app = Flask(__name__, static_folder=None)
        self.app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
        pageAPI.register_routes(self)

    @property
    def browser_token(self):
        # 浏览器缓存仅在本次运行有效；原 Token 改变时，缓存也随之失效。
        return 'webui.' + hmac.new(self._browser_key, self.token.encode(), 'sha256').hexdigest()

    def authenticate(self, token, address, origin=None, host=None):
        """REST 与 WS 共用认证与限流；不信任客户端提供的转发地址。"""
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in ('http', 'https') or parsed.netloc != host:
                return 403
        now = time.monotonic()
        with self.lock:
            attempts = self.failures.get(address, deque())
            while attempts and now - attempts[0] > 60:
                attempts.popleft()
            if len(attempts) >= 10:
                return 429
            valid = isinstance(token, str) and (
                hmac.compare_digest(token.encode(), self.token.encode())
                or hmac.compare_digest(token.encode(), self.browser_token.encode())
            )
            if valid:
                self.failures.pop(address, None)
                return 200
            attempts.append(now)
            self.failures[address] = attempts
            self.failures.move_to_end(address)
            while len(self.failures) > 1024:
                self.failures.popitem(last=False)
            return 401

    def new_session(self):
        with self.lock:
            now = time.monotonic()
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            if len(self.sessions) >= 128:
                self.sessions.pop(next(iter(self.sessions)))
            session = secrets.token_urlsafe(32)
            self.sessions[session] = now + 12 * 3600
            return session

    def session_valid(self, session):
        with self.lock:
            return self.sessions.get(session, 0) > time.monotonic()

    def publish(self, stream, item):
        with self.lock:
            self.sequence += 1
            item = dict(item, sequence=self.sequence)
            self.streams.setdefault(stream, deque(maxlen=self.limit)).append(item)
            if stream == 'logs' and item.get('level', 2) in self.log_levels:
                self.log_levels[item.get('level', 2)].append(item)

    def snapshot(self, stream, since=0, session=None, level=None):
        with self.lock:
            if stream == 'logs' and level is not None:
                selected = (level,) if isinstance(level, int) else level
                source = sorted(
                    (item for value in selected for item in self.log_levels.get(value, ())),
                    key=lambda item: item['sequence'],
                )[-self.limit:]
            else:
                source = self.streams.get(stream, ())
            return [copy.deepcopy(item) for item in source
                    if item['sequence'] > since and (not item.get('session') or item['session'] == session)]

    def send_control(self, action, key=None):
        if self.Proc_info.control_queue is None:
            raise RuntimeError('Control 总线尚未就绪')
        self.Proc_info.control_queue.put(OlivOS.API.Control.packet(action, key), block=False)

    def prune_plugin_cache(self):
        with self.lock:
            if not self.retired_plugin_roots:
                return
            try:
                resourceAPI.prune_cache(self.root, self.retired_plugin_roots)
                self.retired_plugin_roots.clear()
            except (OSError, ValueError) as error:
                # Windows 正在发送的文件可能暂时占用；响应关闭后再次回收。
                self.log(3, f'WebUI cache cleanup failed: {error}')

    def consume(self, packet):
        if not isinstance(packet, OlivOS.API.Control.packet) or packet.action != 'send':
            return
        data = (packet.key or {}).get('data', {})
        action = data.get('action')
        if action == 'logger' and data.get('event') == 'log':
            log = data.get('data', {})
            entry = log.get('data', {})
            text = log.get('str', entry.get('log_message', ''))
            self.publish('logs', {'level': entry.get('log_level', 2), 'time': entry.get('log_time'),
                                  'text': text,
                                  'op_text': OlivOS.diagnoseAPI.format_log_message(text, 'op'),
                                  'cq_text': OlivOS.diagnoseAPI.format_log_message(text, 'cq')})
        elif action == 'account_update':
            with self.lock:
                old_accounts = self.accounts
                self.accounts = copy.deepcopy(data.get('data', {}))
                for key in list(self.terminals):
                    bot = self.accounts.get(key[1])
                    previous = old_accounts.get(key[1])
                    if (bot is None or not bot.enable or previous is None
                            or previous.platform != bot.platform):
                        self.terminals.pop(key)
                        self.streams.pop('/'.join(key), None)
            self.publish('events', {'type': 'accounts'})
        elif action == 'update_data':
            update = data.get('data', {})
            with self.lock:
                self.plugins = copy.deepcopy(update.get('shallow_plugin_data_dict', {}))
                self.plugin_order = copy.deepcopy(update.get('shallow_plugin_order_list', []))
                self.plugin_priority = copy.deepcopy(update.get('shallow_plugin_priority_dict', {}))
                self.plugin_pages = copy.deepcopy(update.get('shallow_plugin_webui_list', []))
                roots = update.get('shallow_plugin_webui_roots', {})
                if roots or update.get('ready'):
                    self.retired_plugin_roots.update(set(self.plugin_roots.values()) - set(roots.values()))
                    self.retired_plugin_roots.difference_update(roots.values())
                    self.plugin_roots = copy.deepcopy(roots)
                    self.plugin_webui_paths = copy.deepcopy(update.get('shallow_plugin_webui_paths', {}))
                    self.prune_plugin_cache()
            self.publish('events', {'type': 'plugins', 'ready': update.get('ready', False),
                                    'priority_only': update.get('priority_only', False),
                                    'started_at': update.get('load_started', 0)})
        elif action in TERMINAL_TYPES and data.get('hash'):
            bot_hash = data['hash']
            with self.lock:
                bot = self.accounts.get(bot_hash)
                if (bot is None or not bot.enable
                        or data.get('account_platform', bot.platform) != bot.platform):
                    return
                if data.get('event') != 'init' and (action, bot_hash) not in self.terminals:
                    return
                terminal = self.terminals.setdefault((action, bot_hash), {'model': action, 'hash': bot_hash})
                event = data.get('event')
                if event == 'qrcode':
                    path = (self.root / data.get('path', '')).resolve()
                    if not pageAPI.within(path, self.root / 'conf') and not pageAPI.within(path, self.root / 'data'):
                        return
                    terminal['qrcode'] = str(path)
                    terminal['qrcode_time'] = time.time()
                elif event == 'qrcode_url':
                    if pageAPI.safe_url(data.get('url', '')):
                        terminal['qrcode_url'] = data['url']
            if event == 'log':
                self.publish(f'{action}/{bot_hash}', {
                    'type': 'log', 'text': str(data.get('data', '')),
                    'name': data.get('name'), 'time': time.time(),
                })
            elif event in ('qrcode', 'qrcode_url', 'init'):
                self.publish('events', {'type': event, 'model': action, 'hash': bot_hash,
                                        'url': terminal.get('qrcode_url')})
        elif action == 'show_update':
            self.update_available = True
            self.publish('events', {'type': 'update'})
        elif action == 'update_check_result':
            status = data.get('status')
            if status in ('available', 'latest'):
                self.update_available = status == 'available'
            self.publish('events', {'type': 'update_check_result', 'status': status,
                                    'started_at': data.get('started_at', 0)})
        elif action == 'webui_reply' and self.session_valid(data.get('session')):
            self.publish('events', {'type': 'plugin_reply', 'namespace': data.get('namespace'),
                                    'request_id': data.get('request_id'), 'payload': data.get('payload'),
                                    'session': data['session']})
        elif action == 'webui_open_page' and pageAPI.safe_url(data.get('url', '')):
            self.publish('events', {'type': 'open_page', 'title': data.get('title'), 'url': data['url']})

    def on_control_rx(self, packet):
        # 常规 send 会同时进入两个队列，只有 control_only 的账号更新在这里消费。
        if (isinstance(packet, OlivOS.API.Control.packet) and isinstance(packet.key, dict)
                and packet.key.get('target', {}).get('fliter') == 'control_only'):
            self.consume(packet)

    def submit_accounts(self, body):
        request_id = secrets.token_hex(16)
        pending = {'body': body, 'done': threading.Event(), 'result': None}
        with self.lock:
            self.pending[request_id] = pending
        try:
            self.send_control('webui_accounts', {'name': self.Proc_name, 'request_id': request_id})
            if not pending['done'].wait(15):
                return {'error': '账号提交等待超时，请刷新核对保存结果'}, 503
            return pending['result']
        finally:
            with self.lock:
                self.pending.pop(request_id, None)

    def commit_accounts(self, request_id, basic_models):
        """只由 boot 主循环调用，和 nativeGUI 的写操作串行。"""
        with self.lock:
            pending = self.pending.get(request_id)
            if pending is None:
                return
            try:
                current = pageAPI.load_accounts(self)
                if pending['body'].get('revision') != pageAPI.account_revision(current):
                    pending['result'] = ({'error': '账号已被其他窗口修改，请刷新后重试'}, 409)
                    return
                accounts = pageAPI.parse_accounts(pending['body'], current)
                accounts = OlivOS.accountAPI.accountFix(basic_models, accounts, self)
                self.account_path.parent.mkdir(parents=True, exist_ok=True)
                if self.account_path.exists():
                    backup = self.account_path.with_name(self.account_path.name + '.webui-backup')
                    backup.write_bytes(self.account_path.read_bytes())
                descriptor, temporary = tempfile.mkstemp(
                    prefix='.webui-', suffix='.json', dir=str(self.account_path.parent),
                )
                os.close(descriptor)
                try:
                    OlivOS.accountAPI.Account.save(temporary, self, accounts)
                    os.replace(temporary, self.account_path)
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
                self.accounts = accounts
                # 直接依次排列，避免把保存和后续协议重建拆到不同 HTTP 线程。
                self.send_control('call_account_update', {'data': accounts})
                self.send_control('call_system_stop_type_event', {'action': ['account_update']})
                self.send_control('call_system_event', {'action': ['account_update']})
                pending['result'] = (pageAPI.account_response(accounts), 200)
            except (ValueError, TypeError, KeyError) as error:
                pending['result'] = ({'error': str(error)}, 400)
            except OSError:
                pending['result'] = ({'error': '账号文件保存失败，请检查文件权限和磁盘空间'}, 500)
            finally:
                pending['done'].set()

    def terminal_input(self, model, bot_hash, data):
        if (model, bot_hash) not in self.terminals or bot_hash not in self.accounts:
            raise ValueError('终端不存在')
        if not self.accounts[bot_hash].enable:
            raise ValueError('账号已停用')
        text = data.get('data')
        if not isinstance(text, str) or not text or len(text) > 8192:
            raise ValueError('请输入 1–8192 字符的终端内容')
        packet = {'action': 'input', 'data': text}
        if model == 'virtual_terminal':
            packet['user_conf'] = data.get('user_conf') or {}
            if not isinstance(packet['user_conf'], dict):
                raise ValueError('虚拟终端用户配置必须为对象')
        self.send_control('send', {'target': {'type': TERMINAL_TYPES[model], 'hash': bot_hash,
                                              'fliter': 'rx_only'}, 'data': packet})

    async def websocket(self, request):
        protocols = [part.strip() for part in request.headers.get('Sec-WebSocket-Protocol', '').split(',')]
        token = next((part[6:] for part in protocols if part.startswith('token.')), '')
        status = self.authenticate(token, request.remote, request.headers.get('Origin'), request.host)
        if status != 200:
            return web.json_response({'error': '认证失败' if status != 429 else '尝试过多，请稍后重试'}, status=status)
        parts = request.path.strip('/').split('/')
        session = request.query.get('session')
        level = None
        try:
            cursor = int(request.query.get('since', '0'))
            if cursor < 0:
                raise ValueError
        except ValueError:
            return web.json_response({'error': '订阅游标无效'}, status=400)
        if parts == ['ws', 'logs']:
            stream = 'logs'
            try:
                level = pageAPI.parse_log_levels(request.query.get('level', ''))
            except ValueError:
                return web.json_response({'error': '日志级别或游标无效'}, status=400)
        elif parts == ['ws', 'events'] and self.session_valid(session):
            stream = 'events'
        elif len(parts) == 4 and parts[:2] == ['ws', 'terminal'] and tuple(parts[2:]) in self.terminals:
            stream = '/'.join(parts[2:])
        else:
            return web.json_response({'error': '订阅不存在'}, status=404)
        socket = web.WebSocketResponse(protocols=['olivos'], heartbeat=30, max_msg_size=16384)
        await socket.prepare(request)
        self.sockets.add(socket)

        async def push():
            nonlocal cursor
            # 第一帧为历史，随后每 50ms 批量发送；慢客户端不会积累无界队列。
            first = True
            while not socket.closed:
                items = self.snapshot(stream, cursor, session, level)
                if items or first:
                    if items:
                        cursor = items[-1]['sequence']
                    await asyncio.wait_for(socket.send_json({
                        'type': 'history' if first else 'batch', 'items': items, 'limit': self.limit,
                    }), 10)
                    first = False
                await asyncio.sleep(0.05)

        task = asyncio.create_task(push())
        try:
            async for message in socket:
                if message.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(message.data)
                        if stream in ('logs', 'events') or not isinstance(data, dict):
                            raise ValueError('该订阅不接受输入')
                        self.terminal_input(parts[2], parts[3], data)
                    except (ValueError, RuntimeError):
                        await socket.send_json({'type': 'error', 'error': '终端输入无效或账号已停用'})
                elif message.type == WSMsgType.ERROR:
                    break
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.sockets.discard(socket)
        return socket

    async def http(self, request):
        if request.path.startswith('/ws/'):
            return await self.websocket(request)
        body = await request.read()
        # aiohttp 负责同端口 WS 握手；所有 HTTP 路由、认证和响应仍由 Flask 执行。
        builder = EnvironBuilder(path=request.path, base_url=f'{request.scheme}://{request.host}',
                                 query_string=request.query_string, method=request.method,
                                 headers=list(request.headers.items()), input_stream=io.BytesIO(body),
                                 content_length=len(body), environ_base={'REMOTE_ADDR': request.remote or ''})
        try:
            environ = builder.get_environ()
            response = await asyncio.get_running_loop().run_in_executor(
                None, lambda: Response.from_app(self.app, environ, buffered=True))
            try:
                return web.Response(status=response.status_code, headers=list(response.headers.items()),
                                    body=response.get_data())
            finally:
                response.close()
        finally:
            builder.close()

    async def serve(self):
        self.loop = asyncio.get_running_loop()
        app = web.Application(client_max_size=1024 * 1024)
        app.router.add_route('*', '/{path:.*}', self.http)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        listener = None
        try:
            requested_port = int(self.config['port'])
            if not 0 <= requested_port <= 65535:
                raise ValueError('WebUI 端口必须在 0–65535 之间')
            for port in range(requested_port, 65536):
                site = web.TCPSite(runner, self.config['host'], port)
                try:
                    await site.start()
                    break
                except OSError as error:
                    if site in runner.sites:
                        await site.stop()
                    if error.errno not in (errno.EADDRINUSE, 10048) or port == 65535:
                        raise
            self.config['port'] = runner.addresses[0][1]
            self.listen_path.parent.mkdir(parents=True, exist_ok=True)
            listener = {
                'host': self.config['host'], 'port': self.config['port'], 'pid': os.getpid(),
                'created': psutil.Process().create_time(),
            }
            descriptor, temporary = tempfile.mkstemp(prefix='.listen-', suffix='.json', dir=self.listen_path.parent)
            try:
                with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
                    json.dump(listener, output)
                os.replace(temporary, self.listen_path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            ACTIVE_LISTENERS[self.root] = listener
            if requested_port != self.config['port']:
                self.log(2, f"WebUI 监听端口由 {requested_port} 调整为 {self.config['port']}")
            self.ready.set()
            self.log(2, f"WebUI 已启动：http://{self.config['host']}:{self.config['port']}；"
                        f"认证文件：{self.config['token_path']}")
            while not self.stop_event.is_set():
                for _ in range(256):
                    try:
                        packet = self.Proc_info.rx_queue.get_nowait()
                    except (queue.Empty, AttributeError):
                        break
                    self.consume(packet)
                await asyncio.sleep(self.Proc_info.scan_interval)
        finally:
            if listener is not None and ACTIVE_LISTENERS.get(self.root) == listener:
                ACTIVE_LISTENERS.pop(self.root, None)
            for socket in list(self.sockets):
                await socket.close()
            await runner.cleanup()
            try:
                current = json.loads(self.listen_path.read_text(encoding='utf-8'))
                if listener is not None and current == listener:
                    self.listen_path.unlink()
            except (OSError, ValueError):
                pass

    def run(self):
        try:
            if os.name == 'nt':
                # 仅 WebUI 使用 Selector，避开 Proactor 在浏览器刷新断连时的 shutdown 异常。
                # 不修改全局事件循环策略，其他协议端继续使用自己的事件循环。
                loop = asyncio.SelectorEventLoop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.serve())
                finally:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    loop.run_until_complete(loop.shutdown_asyncgens())
                    if hasattr(loop, 'shutdown_default_executor'):
                        loop.run_until_complete(loop.shutdown_default_executor())
                    asyncio.set_event_loop(None)
                    loop.close()
            else:
                asyncio.run(self.serve())
        except (OSError, ValueError) as error:
            self.error = str(error)
            self.log(4, f'WebUI 启动失败：{self.error}')
            self.ready.set()

    def on_terminate(self):
        self.stop_event.set()


def forward_packet(packet, proc_dict):
    """旁路分发原生 UI 数据，避免修改六种终端生产者。日志由独立 web 目标转发。"""
    if not isinstance(packet.key, dict) or packet.key.get('target', {}).get('type') != 'nativeWinUI':
        return
    if packet.key.get('data', {}).get('action') == 'logger':
        return
    for proc in list(proc_dict.values()):
        if getattr(proc, 'Proc_type', None) == 'webUI' and proc.Proc_info.rx_queue is not None:
            proc.Proc_info.rx_queue.put(packet, block=False)


def listener_valid(active, root):
    """只查询本机进程与监听信息，不在托盘线程发起网络请求。"""
    try:
        if not isinstance(active, dict) or not isinstance(active.get('host'), str):
            return False
        pid, port = active['pid'], active['port']
        if type(pid) is not int or type(port) is not int or not 1 <= port <= 65535:
            return False
        process = psutil.Process(pid)
        if process.create_time() != active['created']:
            return False
        if pid == os.getpid():
            return ACTIVE_LISTENERS.get(root) == active
        # 子进程中的原生界面通过操作系统确认端口仍由该进程监听。
        return any(connection.status == psutil.CONN_LISTEN and connection.laddr.port == port
                   for connection in process.connections(kind='tcp'))
    except (OSError, ValueError, KeyError, TypeError, psutil.Error):
        return False


def browser_url(root_path=None):
    root = Path(root_path or os.getcwd()).resolve()
    config = dict(DEFAULT_SERVER)
    enabled = True
    for path in ('./conf/basic.json', './conf/config.json'):
        try:
            model = json.loads((root / path).read_text(encoding='utf-8'))['models']['OlivOS_webUI']
            config.update(model.get('server', {}))
            enabled = model.get('enable', enabled)
        except (OSError, ValueError, KeyError):
            pass
    apply_environment_config(config)
    try:
        active = json.loads((root / 'data/webui/listen.json').read_text(encoding='utf-8'))
        if listener_valid(active, root):
            config.update(host=active['host'], port=active['port'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    host = config['host']
    if host in ('0.0.0.0', '::'):
        host = '127.0.0.1'
    if ':' in host:
        host = f'[{host}]'
    return f"http://{host}:{config['port']}" if enabled else None
