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
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from flask import abort, jsonify, request, send_file, send_from_directory

import OlivOS

MASK = '********'
SECRET_KEY = re.compile(r'password|token|secret|(?:^|_)key$|cookie|authorization', re.I)
ENTRY_FIELDS = {
    'edit_root_Entry_ID': 'id', 'edit_root_Entry_Password': 'password',
    'edit_root_Entry_Server_host': 'server.host', 'edit_root_Entry_Server_port': 'server.port',
    'edit_root_Entry_Server_access_token': 'server.access_token',
}


def within(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


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


def load_accounts(host):
    # Account.load 对坏文件回落空列表，WebUI 必须阻止随后覆盖损坏的用户文件。
    if host.account_path.exists():
        try:
            raw = json.loads(host.account_path.read_text(encoding='utf-8'))
            if not isinstance(raw.get('account'), list):
                raise ValueError
        except (ValueError, AttributeError) as error:
            raise ValueError('账号文件格式错误，请先修复原文件') from error
        return OlivOS.accountAPI.Account.load(str(host.account_path), host)
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


def log_tail(path, limit, level):
    if not path.exists():
        return []
    # 从尾部按块读取，避免日志文件变大后每次请求扫描整个文件。
    with path.open('rb') as source:
        source.seek(0, 2)
        position, chunks, lines = source.tell(), [], 0
        while position > 0 and lines <= limit * 8 and sum(map(len, chunks)) < 2 * 1024 * 1024:
            size = min(position, 16384)
            position -= size
            source.seek(position)
            chunk = source.read(size)
            chunks.append(chunk)
            lines += chunk.count(b'\n')
    output = deque(maxlen=limit)
    current_level = 2
    levels = {name: number for number, name in OlivOS.diagnoseAPI.level_dict.items()}
    for line in b''.join(reversed(chunks)).decode('utf-8', errors='replace').splitlines():
        match = re.match(r'^\[([^\]]+)\] - \[(TRACE|DEBUG|NOTE|INFO|WARN|ERROR|FATAL)\] - (.*)', line)
        if match:
            current_level = levels[match[2]]
        if level is None or current_level >= level:
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
        bot = getattr(proc, 'bot_info', None)
        if bot is None:
            bot = getattr(proc, 'Proc_data', {}).get('bot_info_dict')
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
            if getattr(getattr(connection, 'sock', None), 'connected', False):
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
            'uptime': int(time.monotonic() - host.started_at), 'update_available': host.update_available}


def register_routes(host):
    app = host.app

    @app.before_request
    def authorize():
        if request.path == '/api/health':
            return None
        if request.path.startswith('/plugin/'):
            if not host.session_valid(request.cookies.get('olivos_webui')):
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
            response.headers['Content-Security-Policy'] = (
                "sandbox allow-scripts; default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; connect-src 'none'; frame-ancestors 'self'; base-uri 'none'; "
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
        session = host.new_session()
        response = jsonify(session=session)
        response.set_cookie('olivos_webui', session, httponly=True, samesite='Strict',
                            secure=request.is_secure, path='/plugin/', max_age=12 * 3600)
        return response

    @app.post('/api/logout')
    def logout():
        body = request.get_json(silent=True) or {}
        with host.lock:
            host.sessions.pop(body.get('session'), None)
        response = jsonify(ok=True)
        response.delete_cookie('olivos_webui', path='/plugin/')
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
            level = request.args.get('level', '')
            level = int(level) if level else None
        except ValueError as error:
            raise ValueError('日志级别与条数必须为整数') from error
        if level is not None and level not in OlivOS.diagnoseAPI.level_dict:
            raise ValueError('日志级别无效')
        return jsonify(items=log_tail(host.root / 'logfile/OlivOS_logfile_unity.log', limit, level), limit=host.limit)

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

    @app.post('/api/plugins/reload')
    def reload_plugins():
        host.send_control('restart_send', 'plugin')
        return jsonify(ok=True), 202

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
        if not directory or not re.fullmatch(r'[\w.-]+', namespace):
            abort(404)
        root = Path(directory).resolve() / 'webui'
        if not within(root, host.root / 'plugin/app') and not within(root, host.root / 'plugin/tmp'):
            abort(404)
        path = (root / filename).resolve()
        if not within(path, root) or not path.is_file() or any(part.startswith('.') for part in Path(filename).parts):
            abort(404)
        return send_from_directory(str(root), filename)

    @app.post('/api/update/check')
    def update_check():
        host.send_control('init_type', 'update_check')
        return jsonify(ok=True), 202

    @app.post('/api/exit')
    def exit_total():
        host.send_control('exit_total', host.Proc_name)
        return jsonify(ok=True), 202
