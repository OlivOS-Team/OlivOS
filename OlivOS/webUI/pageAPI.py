# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/webUI/pageAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

# 账号、日志、终端与插件页面；业务写入统一交给 Control 主循环。

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, jsonify, request, send_file, send_from_directory

import OlivOS

from . import resourceAPI

MASK = '********'
# 轮询与上报类协议没有长连接，超过该时间未收到活动即视为离线。
ACTIVITY_ONLINE_WINDOW = 180
SECRET_KEY = re.compile(r'password|token|secret|(?:^|_)key$|cookie|authorization', re.I)
ENTRY_FIELDS = {
    'edit_root_Entry_ID': 'id', 'edit_root_Entry_Password': 'password',
    'edit_root_Entry_Server_host': 'server.host', 'edit_root_Entry_Server_port': 'server.port',
    'edit_root_Entry_Server_access_token': 'server.access_token',
}


# 插件页 iframe 的沙箱能力，一次配齐「常规浏览器能做的事」，避免缺一个补一个。
# 刻意不含两个 token：
#   allow-same-origin —— 插件页与宿主 WebUI 同源，给了它就能读宿主的 token、
#     localStorage 与 DOM，沙箱会彻底失效；
#   allow-top-navigation —— 会把宿主 WebUI 整页导航走。
# 注意：iframe 的 sandbox 属性（webUI/static/app.js 的 pluginSandbox）必须使用同一份
# 列表 —— CSP 头的 sandbox 指令与 iframe 属性是两套独立机制，浏览器取更严格的那个。
# 只列两套机制都合法的 token。注意不要加 allow-downloads-without-user-activation：
# `allow-downloads` 本身已允许「无用户手势也能下载」，而那个 token 既不在 CSP sandbox
# 的合法值列表里、也不是 iframe 的合法 token，写进 iframe 属性浏览器会直接报
# 「is an invalid sandbox flag」。
PLUGIN_SANDBOX = (
    'sandbox allow-scripts allow-forms allow-modals allow-downloads '
    'allow-popups allow-popups-to-escape-sandbox allow-pointer-lock '
    'allow-orientation-lock allow-presentation '
    'allow-top-navigation-by-user-activation '
    'allow-storage-access-by-user-activation; '
)


def within(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def open_directory(path):
    # 交给运行 OlivOS 的机器上的文件管理器打开，浏览器无法直接访问本地目录。
    target = str(path)
    if os.name == 'nt':
        os.startfile(target)
        return
    if sys.platform == 'darwin':
        command = ['open', target]
    else:
        # 没有桌面会话时 xdg-open 必然失败，提前给出原因而不是假装打开成功
        if not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY'):
            raise OSError('运行 OlivOS 的环境没有可用的桌面会话，无法打开文件管理器')
        command = ['xdg-open', target]
    try:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as error:
        raise OSError(f'无法调用系统文件管理器：{error}') from error
    try:
        # 失败时 opener 会立刻返回非 0；成功时它可能驻留为文件管理器本身，故超时即视为已交付
        code = process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        return
    if code != 0:
        raise OSError(f'系统文件管理器返回 {code}，可能没有可用的桌面环境')


def safe_url(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return parsed.scheme in ('http', 'https') and bool(parsed.hostname) and not parsed.username
    except ValueError:
        return False


def redact(value, key=''):
    if SECRET_KEY.search(key) and value not in ('', None):
        return MASK
    if isinstance(value, dict):
        return {name: redact(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    # 连接 URL 可能内嵌凭据，避免通过非 token 字段返回。
    if (isinstance(value, str) and '://' in value
            and re.search(r'://[^/]*@|[?&](?:token|access_token|key)=', value, re.I)):
        return MASK
    return value


def restore(value, previous=None):
    if value == MASK:
        if previous is None:
            raise ValueError('新增账号不能使用脱敏占位符')
        return copy.deepcopy(previous)
    if isinstance(value, dict):
        previous = previous if isinstance(previous, dict) else {}
        result = copy.deepcopy(previous)
        for key, item in value.items():
            if key == '_source_index':
                continue
            result[key] = restore(item, previous.get(key))
        return result
    if isinstance(value, list):
        previous = previous if isinstance(previous, list) else []
        result = []
        for i, item in enumerate(value):
            source_index = item.get('_source_index', i) if isinstance(item, dict) else i
            if not isinstance(source_index, int) or source_index < -1:
                raise ValueError('签名服务器来源索引无效')
            old = previous[source_index] if 0 <= source_index < len(previous) else None
            result.append(restore(item, old))
        return result
    return value


def account_dict(bot):
    return {
        'id': bot.id, 'password': bot.password, 'sdk_type': bot.platform['sdk'],
        'platform_type': bot.platform['platform'], 'model_type': bot.platform['model'],
        'server': {'auto': bot.post_info.auto, 'type': bot.post_info.type, 'host': bot.post_info.host,
                   'port': bot.post_info.port, 'access_token': bot.post_info.access_token},
        'extends': copy.deepcopy(bot.extends), 'enable': getattr(bot, 'enable', True), 'debug': bot.debug_mode,
    }


def account_revision(accounts):
    content = json.dumps({key: account_dict(bot) for key, bot in accounts.items()}, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()


def account_response(accounts):
    return {'account': [dict(redact(account_dict(bot)), hash=key, id=str(bot.id)) for key, bot in accounts.items()],
            'revision': account_revision(accounts)}


class _AccountReadLogger:
    def __init__(self, host):
        self.host = host

    def log(self, level, message, *args):
        # 网页读取配置不属于账号初始化，仍保留警告和错误。
        if level != 2:
            self.host.log(level, message, *args)


def load_accounts(host):
    # Account.load 对坏文件回落空列表，WebUI 必须阻止随后覆盖损坏的用户文件。
    if host.account_path.exists():
        try:
            raw = json.loads(host.account_path.read_text(encoding='utf-8'))
            if not isinstance(raw.get('account'), list):
                raise ValueError
        except (ValueError, AttributeError) as error:
            raise ValueError('账号文件格式错误，请先修复原文件') from error
        return OlivOS.accountAPI.Account.load(str(host.account_path), _AccountReadLogger(host))
    return copy.deepcopy(host.accounts)


def account_schema():
    metadata = OlivOS.accountMetadataAPI.getAccountEditorMetadata()
    hierarchy = {}
    for platform, sdks in metadata['platform_sdk_model_list'].items():
        for sdk, models in sdks.items():
            hierarchy.setdefault(sdk, {})[platform] = list(models)
    presets = []
    for title in metadata['type_list']:
        if title == '自定义':
            continue
        platform, sdk, model, auto, connection = OlivOS.accountMetadataAPI.accountTypeMappingList[title]
        models = hierarchy.setdefault(sdk, {}).setdefault(platform, [])
        if model not in models:
            models.append(model)
        slots = metadata['type_mapping_list_Entry_slot'].get(title, {})
        presets.append({
            'title': title, 'platform_type': platform, 'sdk_type': sdk, 'model_type': model,
            'server': {'auto': auto == 'True', 'type': connection},
            'fields': [{'name': ENTRY_FIELDS[value], 'title': label} for label, value in slots.items()],
            'extends': [{'name': name, 'title': label} for label, name in
                        metadata['type_extends_note_list'].get(title, {}).items()],
            'note': metadata['type_note_list'].get(title, ''),
            'qsign': title in metadata['type_qsign_array_note_list'],
            'webhook': sdk == 'qqGuildv2_link' and connection == 'post',
        })
    return {'hierarchy': hierarchy, 'presets': presets,
            'server_types': OlivOS.accountMetadataAPI.accountTypeDataList_server_type,
            'qsign_protocols': OlivOS.accountMetadataAPI.accountQsignProtocols,
            'qsign_limit': 10,
            'fields': [{'name': 'id', 'title': 'ID'}, {'name': 'password', 'title': 'PASSWORD'},
                       {'name': 'server.host', 'title': 'HOST'}, {'name': 'server.port', 'title': 'PORT'},
                       {'name': 'server.access_token', 'title': 'TOKEN'}]}


def parse_accounts(body, previous):
    if not isinstance(body, dict) or not isinstance(body.get('account'), list):
        raise ValueError('请求必须包含 account 数组')
    result = {}
    hierarchy = account_schema()['hierarchy']
    for row in body['account']:
        if not isinstance(row, dict):
            raise ValueError('账号必须为对象')
        old_hash = row.get('hash')
        old = previous.get(old_hash)
        if old_hash and old is None:
            raise ValueError('原账号不存在，请刷新后重试')
        row = restore(row, account_dict(old) if old else {})
        connection = row.get('server', {})
        if not isinstance(connection, dict):
            raise ValueError('server 必须为对象')
        sdk, platform, model = (row.get(key) for key in ('sdk_type', 'platform_type', 'model_type'))
        if model not in hierarchy.get(sdk, {}).get(platform, []):
            if not old or (sdk, platform, model) != tuple(old.platform[key] for key in ('sdk', 'platform', 'model')):
                raise ValueError('SDK、平台与型号组合无效')
        for value in (row.get('enable', True), row.get('debug', False), connection.get('auto', False)):
            if not isinstance(value, bool):
                raise ValueError('启用、调试和自动配置必须为布尔值')
        if connection.get('type') not in OlivOS.accountMetadataAPI.accountTypeDataList_server_type:
            raise ValueError('连接类型无效')
        for value in (row.get('id', ''), row.get('password', ''), connection.get('host', ''),
                      connection.get('port', ''), connection.get('access_token', '')):
            if value is not None and not isinstance(value, (str, int)):
                raise ValueError('账号字段必须为字符串或整数')
        fields = OlivOS.accountAPI.normalizeAccountFields({
            'id': str(row.get('id', '')), 'password': row.get('password', ''),
            'server_auto': str(connection.get('auto', False)), 'server_type': connection['type'],
            'host': connection.get('host', ''), 'port': str(connection.get('port', '')),
            'access_token': connection.get('access_token', '') or '',
            'platform_sdk': sdk, 'platform_platform': platform, 'platform_model': model,
        })
        if not fields['id'] or not fields['host'] or fields['port'] == '' or not fields['access_token']:
            raise ValueError('请填写账号、主机和端口等必要字段')
        try:
            port = int(fields['port'])
        except (ValueError, TypeError) as error:
            raise ValueError('端口或 intents 必须为整数') from error
        is_intents = model.endswith('intents') or (sdk == 'mhyVila_link' and model == 'sandbox')
        if port < 0 or (not is_intents and port > 65535):
            raise ValueError('端口应在 0–65535 之间')
        account_id = fields['id']
        try:
            account_id = int(account_id)
        except ValueError:
            pass
        bot = OlivOS.API.bot_info_T(
            id=account_id, password=fields['password'],
            server_auto=connection.get('auto', False), server_type=connection['type'],
            host=fields['host'], port=port, access_token=fields['access_token'],
            platform_sdk=sdk, platform_platform=platform, platform_model=model,
        )
        bot.extends = row.get('extends', {})
        if not isinstance(bot.extends, dict):
            raise ValueError('extends 必须为 JSON 对象')
        qsign = bot.extends.get('qsign-server', [])
        if not isinstance(qsign, list) or len(qsign) > 10 or any(
            not isinstance(item, dict) or not all(isinstance(item.get(key, ''), str) for key in ('addr', 'key'))
            for item in qsign
        ):
            raise ValueError('签名服务器必须为不超过 10 项的地址与 KEY 列表')
        bot.enable, bot.debug_mode = row.get('enable', True), row.get('debug', False)
        if bot.hash in result:
            raise ValueError('同一 SDK 和平台不能添加重复账号 ID')
        result[bot.hash] = bot
    return result


def parse_log_levels(value):
    if not value:
        return None
    try:
        selected = tuple(sorted({int(item) for item in value.split(',')}))
    except (ValueError, AttributeError) as error:
        raise ValueError('日志级别无效') from error
    if any(level not in OlivOS.diagnoseAPI.level_dict for level in selected):
        raise ValueError('日志级别无效')
    return selected


def log_tail(path, limit, level):
    if not path.exists():
        return []
    # 从尾部按块读取，避免日志文件变大后每次请求扫描整个文件。
    selected = (level,) if isinstance(level, int) else level
    markers = [f' - [{OlivOS.diagnoseAPI.level_dict[item]}] - '.encode() for item in selected] if selected else [b'\n']
    with path.open('rb') as source:
        source.seek(0, 2)
        position, chunks, lines = source.tell(), [], 0
        while position > 0 and lines <= limit * 8 and sum(map(len, chunks)) < 2 * 1024 * 1024:
            size = min(position, 16384)
            position -= size
            source.seek(position)
            chunk = source.read(size)
            chunks.append(chunk)
            lines += sum(chunk.count(marker) for marker in markers)
    output = deque(maxlen=limit)
    current_level = None
    levels = {name: number for number, name in OlivOS.diagnoseAPI.level_dict.items()}
    for line in b''.join(reversed(chunks)).decode('utf-8', errors='replace').splitlines():
        match = re.match(r'^\[([^\]]+)\] - \[(TRACE|DEBUG|NOTE|INFO|WARN|ERROR|FATAL)\] - (.*)', line)
        if match:
            current_level = levels[match[2]]
        if current_level is not None and (selected is None or current_level in selected):
            output.append({'level': current_level, 'time': match[1] if match else None,
                           'text': match[3] if match else line})
    return list(output)


def runtime_status(host):
    online = set()
    known = set()
    for proc in list(host.runtime.values()):
        if getattr(proc, 'Proc_type', None) == 'qqGuildv2_webhook':
            for bot in proc.Proc_data.get('bot_info_dict', {}).values():
                if not isinstance(bot, OlivOS.API.bot_info_T) or not bot.enable:
                    continue
                if not OlivOS.qqGuildv2SDK.is_qqGuildv2_webhook_account(bot):
                    continue
                known.add(bot.hash)
                if proc.webhook_online:
                    online.add(bot.hash)
            continue
        if hasattr(proc, 'account_activity'):
            now = time.monotonic()
            for bot_hash, last_seen in proc.account_activity().items():
                bot = host.accounts.get(bot_hash)
                if bot is None or not bot.enable:
                    continue
                known.add(bot_hash)
                if last_seen > 0 and now - last_seen <= ACTIVITY_ONLINE_WINDOW:
                    online.add(bot_hash)
            continue
        bot_info = getattr(proc, 'bot_info', None)
        if bot_info is None:
            bot_info = getattr(proc, 'status_bot_info', None)
        if bot_info is None:
            bot_info = getattr(proc, 'Proc_data', {}).get('bot_info_dict')
        if isinstance(bot_info, OlivOS.API.bot_info_T):
            bots = [bot_info]
        elif isinstance(bot_info, dict):
            bots = list(bot_info.values())
        else:
            bots = []
        for bot in bots:
            if not isinstance(bot, OlivOS.API.bot_info_T) or not bot.enable:
                continue
            if hasattr(proc, 'ws_conn'):
                known.add(bot.hash)
                connection = proc.ws_conn
                if connection is not None and (getattr(connection, 'open', False)
                                               or getattr(getattr(connection, 'state', None), 'name', '') == 'OPEN'):
                    online.add(bot.hash)
            elif 'ws_obj' in getattr(proc, 'Proc_data', {}).get('extend_data', {}):
                known.add(bot.hash)
                connection = proc.Proc_data['extend_data']['ws_obj']
                # websocket-client 用 sock.connected 表示状态，aiohttp 用 closed。
                if connection is not None and (
                    getattr(getattr(connection, 'sock', None), 'connected', False)
                    or getattr(connection, 'closed', None) is False
                ):
                    online.add(bot.hash)
            elif hasattr(proc, 'active_links'):
                # 反向 WebSocket 或共享长连接，连接数大于零即为在线。
                known.add(bot.hash)
                if proc.active_links > 0:
                    online.add(bot.hash)
            elif proc.Proc_type == 'terminal_link' and bot.platform['model'] == 'default':
                known.add(bot.hash)
                if ('virtual_terminal', bot.hash) in host.terminals:
                    online.add(bot.hash)
    accounts = host.accounts
    enabled = {key for key, bot in accounts.items() if bot.enable}
    unknown = enabled - known
    unknown_accounts = [
        {'id': str(bot.id), 'platform_type': bot.platform['platform'],
         'sdk_type': bot.platform['sdk'], 'model_type': bot.platform['model']}
        for key, bot in accounts.items() if key in unknown
    ]
    account_connections = {
        key: ('disabled' if not bot.enable else 'online' if key in online
              else 'offline' if key in known else 'unknown')
        for key, bot in accounts.items()
    }
    return {'version': OlivOS.infoAPI.OlivOS_Version_Short, 'accounts': len(accounts),
            'enabled': len(enabled), 'online': len(online & enabled), 'unknown': len(unknown),
            'unknown_accounts': unknown_accounts, 'account_connections': account_connections,
            'uptime': int(time.monotonic() - host.started_at), 'update_available': host.update_available,
            'plugin_page_cache': getattr(host, 'plugin_page_cache', 10)}


def register_routes(host):
    app = host.app

    def cookie_name():
        # Cookie 不按端口隔离；同一主机上的多个 WebUI 必须使用不同名称。
        authority = request.host.lower().encode('utf-8')
        return 'olivos_webui_' + hashlib.sha256(authority).hexdigest()[:16]

    def session_response(session):
        response = jsonify(session=session, cursor=host.sequence, browser_token=host.browser_token)
        response.set_cookie(cookie_name(), session, httponly=True, samesite='Strict',
                            secure=request.is_secure, path='/plugin/', max_age=12 * 3600)
        return response

    @app.before_request
    def authorize():
        if request.path == '/api/health':
            return None
        if request.path.startswith('/plugin/'):
            if not host.session_valid(request.cookies.get(cookie_name())):
                if request.headers.get('Sec-Fetch-Dest') in ('iframe', 'document'):
                    # 沙箱页不能读 Cookie，由父页面验证身份并最多重试一次。
                    return ('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<p>插件页面登录已失效，正在尝试恢复；若未恢复，请关闭此插件页后重新打开。</p>
<script>window.parent.postMessage({type: 'olivos:plugin_auth_required'}, '*');</script>
</html>''', 401, {'Content-Type': 'text/html; charset=utf-8'})
                return jsonify(error='请先登录 WebUI'), 401
            return None
        if request.path.startswith('/api/'):
            status = host.authenticate(request.headers.get('X-Auth-Token', ''), request.remote_addr,
                                       request.headers.get('Origin'), request.host)
            if status != 200:
                response = jsonify(error='尝试过多，请一分钟后重试' if status == 429 else '认证失败')
                if status == 429:
                    response.headers['Retry-After'] = '60'
                return response, status
        return None

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        if request.path.startswith('/plugin/'):
            # 插件是独立沙箱，拿不到宿主 token、存储和 DOM。
            # 沙箱能力集中在 PLUGIN_SANDBOX 里定义，避免出现「缺一个补一个」。
            response.headers['Content-Security-Policy'] = (
                PLUGIN_SANDBOX +
                "default-src 'self' data: blob:; "
                "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                "connect-src 'none'; frame-ancestors 'self'; base-uri 'none'; "
                "form-action 'none'"
            )
        else:
            response.headers['Content-Security-Policy'] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' blob: data:; "
                "connect-src 'self'; frame-src 'self' https: http:; frame-ancestors 'none'; base-uri 'none'"
            )
        return response

    @app.errorhandler(ValueError)
    def invalid_request(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(OSError)
    def io_error(error):
        return jsonify(error='无法读取文件，请检查路径和权限'), 500

    @app.get('/')
    def index():
        return send_from_directory(str(host.static_path), 'index.html')

    @app.get('/static/<name>')
    def assets(name):
        if name not in ('app.js', 'theme.js', 'style.css', 'logo.png'):
            abort(404)
        return send_from_directory(str(host.static_path), name)

    @app.get('/api/health')
    def health():
        return jsonify(status='OK')

    @app.post('/api/login')
    def login():
        with host.lock:
            session = host.new_session()
            return session_response(session)

    @app.post('/api/session')
    def renew_session():
        # 此接口已经通过 Token 认证；只读 Cookie/插件访问本身不能续期。
        body = request.get_json(silent=True) or {}
        session = body.get('session') if isinstance(body, dict) else None
        with host.lock:
            if isinstance(session, str) and session in host.sessions:
                host.sessions[session] = time.monotonic() + 12 * 3600
            else:
                session = host.new_session()
            return session_response(session)

    @app.post('/api/logout')
    def logout():
        body = request.get_json(silent=True) or {}
        with host.lock:
            host.sessions.pop(body.get('session'), None)
        response = jsonify(ok=True)
        response.delete_cookie(cookie_name(), path='/plugin/')
        return response

    @app.get('/api/status')
    def status():
        return jsonify(runtime_status(host))

    @app.route('/api/accounts', methods=['GET', 'POST'])
    def accounts():
        if request.method == 'GET':
            with host.lock:
                return jsonify(account_response(load_accounts(host)))
        body = request.get_json()
        if not isinstance(body, dict) or not isinstance(body.get('revision'), str):
            raise ValueError('提交前请读取账号列表及 revision')
        with host.lock:
            parse_accounts(body, load_accounts(host))
        result, code = host.submit_accounts(body)
        return jsonify(result), code

    @app.get('/api/accounts/schema')
    def schema():
        return jsonify(account_schema())

    @app.get('/api/accounts/webhook')
    def webhook():
        return jsonify(url=OlivOS.qqGuildv2WebhookServerAPI.get_qqGuildv2_webhook_listen_url(
            request.args.get('id', '')),
            certdir=OlivOS.qqGuildv2WebhookServerAPI.get_qqGuildv2_webhook_server_conf().get('certdir', './conf/ssl'))

    @app.get('/api/logs')
    def logs():
        try:
            limit = max(1, min(int(request.args.get('tail', host.limit)), host.limit))
            level = parse_log_levels(request.args.get('level', ''))
        except ValueError as error:
            raise ValueError('日志级别与条数必须为整数') from error
        with host.lock:
            items = host.snapshot('logs', level=level)[-limit:]
            cursor = host.sequence
        if not items:
            items = log_tail(host.root / 'logfile/OlivOS_logfile_unity.log', limit, level)
            for item in items:
                item['op_text'] = OlivOS.diagnoseAPI.format_log_message(item['text'], 'op')
                item['cq_text'] = OlivOS.diagnoseAPI.format_log_message(item['text'], 'cq')
        return jsonify(items=items, cursor=cursor, limit=host.limit)

    @app.route('/api/logs/display', methods=['GET', 'PUT'])
    def log_display():
        if request.method == 'PUT':
            body = request.get_json(silent=True)
            mode = body.get('format') if isinstance(body, dict) else None
            OlivOS.diagnoseAPI.save_log_display_mode(mode, host.root)
        return jsonify(format=OlivOS.diagnoseAPI.load_log_display_mode(host.root))

    @app.get('/api/terminals')
    def terminals():
        with host.lock:
            return jsonify(items=[{'model': model, 'hash': bot_hash, 'id': str(host.accounts[bot_hash].id),
                                   'qrcode': bool(data.get('qrcode')), 'qrcode_time': data.get('qrcode_time'),
                                   'qrcode_url': data.get('qrcode_url')}
                                  for (model, bot_hash), data in host.terminals.items()
                                  if bot_hash in host.accounts and host.accounts[bot_hash].enable])

    @app.get('/api/terminal/<model>/<bot_hash>/qrcode')
    def qrcode(model, bot_hash):
        with host.lock:
            terminal = host.terminals.get((model, bot_hash), {})
            path = terminal.get('qrcode')
        if not path or not Path(path).is_file() or Path(path).stat().st_size > 4 * 1024 * 1024:
            abort(404)
        if Path(path).suffix.lower() not in ('.png', '.jpg', '.jpeg', '.gif', '.bmp'):
            abort(404)
        return send_file(path)

    @app.get('/api/plugins')
    def plugins():
        with host.lock:
            return jsonify(shallow_plugin_data_dict=host.plugins, shallow_plugin_webui_list=host.plugin_pages)

    @app.post('/api/plugins/open')
    def open_plugins():
        # 固定打开插件目录，不接受客户端路径，避免越界读取宿主文件系统。
        directory = (host.root / 'plugin/app').resolve()
        if not directory.is_dir():
            raise ValueError('插件目录不存在')
        try:
            open_directory(directory)
        except OSError as error:
            # 回传真实原因，避免落到「无法读取文件」这个与打开目录无关的通用处理器
            return jsonify(error=str(error)), 500
        return jsonify(ok=True, path=str(directory))

    @app.post('/api/plugins/reload')
    def reload_plugins():
        started_at = time.time()
        host.send_control('restart_send', 'plugin')
        return jsonify(ok=True, started_at=started_at), 202

    @app.post('/api/plugin_event')
    def plugin_event():
        body = request.get_json()
        if not isinstance(body, dict):
            raise ValueError('插件事件必须为对象')
        namespace, event = body.get('namespace'), body.get('event')
        if not isinstance(namespace, str) or namespace not in host.plugins:
            raise ValueError('插件不存在')
        if not isinstance(event, str) or not event or len(event) > 256:
            raise ValueError('事件名称无效')
        data = {'action': 'plugin_menu', 'namespace': namespace, 'event': event}
        if 'session' in body:
            if not host.session_valid(body['session']):
                abort(401)
            request_id = body.get('request_id', '')
            if not isinstance(request_id, str) or len(request_id) > 128:
                raise ValueError('request_id 无效')
            data['webui'] = {'session': body['session'], 'request_id': request_id, 'payload': body.get('payload')}
        host.send_control('send', {'target': {'type': 'plugin', 'fliter': 'rx_only'}, 'data': data})
        return jsonify(ok=True), 202

    @app.get('/plugin/<namespace>/', defaults={'filename': 'index.html'})
    @app.get('/plugin/<namespace>/<path:filename>')
    def plugin_file(namespace, filename):
        with host.lock:
            directory = host.plugin_roots.get(namespace)
            if not directory or not resourceAPI.valid_namespace(namespace):
                abort(404)
            root = Path(directory)
            allowed_roots = (host.root / 'plugin/app', host.root / resourceAPI.CACHE_PATH / namespace)
            if not any(within(root, allowed) for allowed in allowed_roots):
                abort(404)
            resources = host.plugin_webui_paths.get(namespace, [])
            try:
                name = resourceAPI.relative_path(filename)
                if not resourceAPI.allows(name, resources):
                    abort(404)
                resourceAPI.safe_path(host.root, root.relative_to(host.root).as_posix())
                path = resourceAPI.safe_path(root, name)
                if not within(path, root) or not path.is_file():
                    abort(404)
                # 在切换挂载与回收旧缓存之前打开响应文件。
                response = send_from_directory(str(root), name)
                response.direct_passthrough = False
                response.call_on_close(host.prune_plugin_cache)
                return response
            except (OSError, ValueError, RuntimeError):
                abort(404)

    @app.post('/api/update/check')
    def update_check():
        started_at = time.time()
        host.send_control('init_type', 'update_check')
        return jsonify(ok=True, started_at=started_at), 202

    @app.post('/api/exit')
    def exit_total():
        host.send_control('exit_total', host.Proc_name)
        return jsonify(ok=True), 202
