# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/webUI/tkBridgeAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   宿主只读 Tk 兼容桥的回环认证与传输。
'''

import hashlib
import ipaddress
import json
import platform
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from queue import Full

from flask import g, jsonify, request

from OlivOS.core.core.tkBridgeAPI import LEASE, MAX_SESSIONS, REQUEST_TIMEOUT, opaque_id

CONFIG = 'conf/plugin_tk_bridge.json'
MAX_CONFIG = 64 * 1024
MAX_REQUEST = 4096
MESSAGES = {
    'auth': (401, 'WebUI 登录已失效，请重新登录'),
    'invalid': (400, 'Tk 兼容请求格式错误'),
    'unsupported_environment': (409, 'Tk 兼容仅支持本机 Windows 桌面和直接回环访问'),
    'tk_unavailable': (409, '宿主 Tk 尚未就绪'),
    'unsupported_panel': (409, '当前插件版本或菜单未通过 Tk 兼容审核'),
    'disabled': (409, '此面板的 Tk 兼容已关闭'),
    'applying': (409, 'Tk 兼容设置正在应用，请稍后重试'),
    'occupied': (409, '此面板已在另一处打开或正在关闭'),
    'desktop_open': (409, '请先关闭桌面面板，再打开兼容页'),
    'panel_closed': (410, '面板已关闭或租约已过期，请重新打开'),
    'data_changed': (409, '面板数据已变化，请重新读取首页'),
    'stale_config': (409, '设置已被其他窗口修改，请刷新后重试'),
    'stale_generation': (409, '插件已重载，请重新打开面板'),
    'busy': (503, 'Tk 兼容繁忙，请稍后重试'),
    'timeout': (503, '等待 Tk 面板超时，请稍后重试'),
    'panel_failed': (409, '无法读取已审核的 Tk 面板'),
}
CONFIG_ERROR = 'Tk 兼容配置无法读取，请先修复 conf/plugin_tk_bridge.json'


def _name(value):
    return isinstance(value, str) and 0 < len(value) <= 256


def _loopback(address):
    if not isinstance(address, tuple) or len(address) < 2:
        return False
    try:
        ip = ipaddress.ip_address(address[0])
    except ValueError:
        return False
    return (getattr(ip, 'ipv4_mapped', None) or ip).is_loopback


def _load(root):
    try:
        with (root / CONFIG).open('rb') as source:
            raw = source.read(MAX_CONFIG + 1)
        if len(raw) > MAX_CONFIG:
            raise ValueError
        document = json.loads(raw)
        if (not isinstance(document, dict) or type(document.get('version')) is not int
                or document['version'] != 1 or set(document) != {'version', 'plugins'}
                or not isinstance(document['plugins'], dict)):
            raise ValueError
        for namespace, panels in document['plugins'].items():
            if (not _name(namespace) or not isinstance(panels, dict)
                    or any(not _name(event) or type(enabled) is not bool for event, enabled in panels.items())):
                raise ValueError
        return document
    except FileNotFoundError:
        return {'version': 1, 'plugins': {}}
    except (ValueError, OSError, RecursionError):
        return None


def _revision(document):
    if document is not None:
        return hashlib.blake2s(json.dumps(document, sort_keys=True).encode(), digest_size=16).hexdigest()
    return None


def _save(root, document):
    path = root / CONFIG
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(document, ensure_ascii=False, indent=4) + '\n').encode('utf-8')
    if len(raw) > MAX_CONFIG:
        raise ValueError('Tk 兼容配置已达到容量上限')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('wb', dir=path.parent, prefix='.tk-bridge-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _error(code):
    status, message = MESSAGES[code]
    return {'code': code, 'error': message}, status


@dataclass
class Session:
    key: tuple
    owner: str
    expiry: float
    phase: str = 'opening'
    inflight: str = ''
    revoke_request: dict | None = None
    next_poll: float = 0
    possible_expiry: float = 0


@dataclass
class Pending:
    data: dict
    done: threading.Event = field(default_factory=threading.Event)
    result: object = None


class WebBridge:
    def __init__(self, host, *, clock=time.monotonic):
        self.host = host
        self.clock = clock
        self.bound = ()
        self.generation = None
        self.ready = False
        self.profile_error = None
        self.panels = {}
        self.sessions = {}
        self.pending = {}
        self.target = set()
        self.applied = set()
        self.config_request = None
        self.config_dirty = False
        self.serial = 0
        self.stopped = False

    def listen(self, addresses):
        with self.host.lock:
            if self.stopped:
                return
            self.bound = tuple(addresses)
            self._sync(_load(self.host.root))

    def local(self, peer, local):
        return self.environment() and _loopback(peer) and _loopback(local) and local in self.bound

    def environment(self):
        return platform.system() == 'Windows' and bool(self.bound) and all(map(_loopback, self.bound))

    def _send(self, data):
        try:
            self.host.send_control('send', {'target': {'type': 'plugin', 'fliter': 'control_only'}, 'data': data})
            return True
        except (Full, RuntimeError):
            return False

    def _intent(self, op, **fields):
        return dict(action='tk_bridge_request', op=op, request_id=opaque_id(), generation=self.generation,
                    deadline=self.clock() + REQUEST_TIMEOUT, **fields)

    def _sync(self, document):
        target = set()
        if self.ready and self.environment() and document is not None and not self.profile_error:
            target = {key for key in self.panels if document['plugins'].get(key[0], {}).get(key[1]) is True}
        if target != self.target:
            self.target = target
            self.config_request = None
            self.config_dirty = True
            for bridge_id, session in self.sessions.items():
                if session.key not in target:
                    self._revoke(bridge_id, session)
        self._configure()

    def _configure(self):
        if not self.ready or not self.config_dirty:
            return
        if self.config_request is not None and self.config_request['deadline'] > self.clock():
            return
        self.serial = max(self.serial + 1, time.monotonic_ns())
        message = self._intent('configure', serial=self.serial, enabled=sorted(self.target))
        if self._send(message):
            self.config_request = message

    def _sweep(self):
        now = self.clock()
        changed = False
        for bridge_id, session in list(self.sessions.items()):
            if session.expiry <= now or self.host.browser_tokens.get(session.owner, 0) <= now:
                changed |= session.phase != 'closing'
                self._revoke(bridge_id, session)
            elif session.phase == 'closing':
                self._revoke(bridge_id, session)
            # 在途请求可能已延长了加载器租约，即使 HTTP 尚未收到回包。
            if session.phase == 'closing' and max(session.expiry, session.possible_expiry) <= now:
                del self.sessions[bridge_id]
                changed = True
        if changed:
            self.host.publish('events', {'type': 'tk_bridge_status'})

    def maintain(self):
        with self.host.lock:
            self._sweep()
            self._configure()

    def _finish(self, pending, result):
        if not pending.done.is_set():
            pending.result = result
            pending.done.set()

    def _revoke(self, bridge_id, session, code='panel_closed'):
        if session.inflight and (pending := self.pending.get(session.inflight)):
            self._finish(pending, _error(code))
        session.phase = 'closing'
        if session.revoke_request is None or session.revoke_request['deadline'] <= self.clock():
            message = self._intent('revoke', bridge_id=bridge_id, owner=session.owner)
            if self._send(message):
                session.revoke_request = message

    def revoke(self, owner_key=None):
        with self.host.lock:
            changed = False
            for bridge_id, session in self.sessions.items():
                if owner_key is None or session.owner == owner_key:
                    changed |= session.phase != 'closing'
                    self._revoke(bridge_id, session)
            if changed:
                self.host.publish('events', {'type': 'tk_bridge_status'})

    def invalidate(self):
        with self.host.lock:
            for bridge_id, session in self.sessions.items():
                self._revoke(bridge_id, session, 'stale_generation')
            self.generation = None
            self.ready = False
            self.profile_error = None
            self.panels.clear()
            self.sessions.clear()
            self.target.clear()
            self.applied.clear()
            self.config_request = None
            self.config_dirty = False

    def stop(self):
        with self.host.lock:
            self.stopped = True
            self.bound = ()
            self.invalidate()

    def update(self, metadata):
        with self.host.lock:
            if self.stopped:
                return
            if not isinstance(metadata, dict) or not _name(metadata.get('generation')):
                self.invalidate()
                return
            if metadata['generation'] != self.generation:
                self.invalidate()
                self.generation = metadata['generation']
            ready = metadata.get('tk_ready') is True
            if self.ready and not ready:
                self.config_dirty = True
                self.config_request = None
                self.applied.clear()
            self.ready = ready
            self.profile_error = metadata.get('profile_error')
            self.panels = {(panel['namespace'], panel['event']): panel['title'] for panel in metadata.get('panels', ())}
            self._sync(_load(self.host.root))

    def _status(self, document, local):
        entries = []
        error = CONFIG_ERROR if document is None else self.profile_error
        overrides = document['plugins'] if document else {}
        keys = self.panels.keys() | {(namespace, event) for namespace, items in overrides.items() for event in items}
        for namespace, event in sorted(keys):
            key = namespace, event
            enabled = overrides.get(namespace, {}).get(event) is True
            sessions = [s for s in self.sessions.values() if s.key == key]
            acknowledged = not self.config_dirty and (key in self.applied) == enabled
            reason = (error if error else
                      MESSAGES['unsupported_panel'][1] if key not in self.panels else
                      MESSAGES['unsupported_environment'][1] if not local else
                      MESSAGES['tk_unavailable'][1] if not self.ready else None)
            entries.append(dict(namespace=namespace, event=event, title=self.panels.get(key, event),
                                available=reason is None, enabled=enabled,
                                applied=acknowledged and (enabled or not sessions),
                                active=any(s.phase == 'open' for s in sessions),
                                closing=any(s.phase == 'closing' for s in sessions),
                                reason=reason))
        return dict(panels=entries, revision=_revision(document), error=error, generation=self.generation)

    def _authorized(self, token, auth_revision):
        return (self.host.credentials and auth_revision == self.host.credentials['revision']
                and self.host.browser_valid(token))

    def settings(self, token, auth_revision, peer, local, body=None):
        with self.host.lock:
            if not self._authorized(token, auth_revision):
                return _error('auth')
            self._sweep()
            document = _load(self.host.root)
            is_local = self.local(peer, local)
            self._sync(document)
            if body is None:
                return self._status(document, is_local), 200
            if not isinstance(body, dict) or not all(_name(body.get(k)) for k in ('namespace', 'event', 'revision')):
                return _error('invalid')
            key = body['namespace'], body['event']
            enabled = body.get('enabled')
            if type(enabled) is not bool:
                return _error('invalid')
            if not is_local:
                return _error('unsupported_environment')
            if document is None:
                return {'code': 'invalid_config', 'error': CONFIG_ERROR}, 409
            if enabled and self.profile_error:
                return {'code': 'invalid_profiles', 'error': self.profile_error}, 409
            if body['revision'] != _revision(document):
                return _error('stale_config')
            if enabled and key not in self.panels:
                return _error('unsupported_panel')
            if enabled and not self.ready:
                return _error('tk_unavailable')
            entries = document['plugins']
            if enabled:
                entries.setdefault(key[0], {})[key[1]] = True
            elif key[0] in entries:
                entries[key[0]].pop(key[1], None)
                if not entries[key[0]]:
                    del entries[key[0]]
            try:
                _save(self.host.root, document)
            except ValueError as exc:
                return {'code': 'invalid_config', 'error': str(exc)}, 409
            except OSError:
                return {'code': 'config_write_failed', 'error': '无法保存 Tk 兼容配置，请检查 conf 目录权限'}, 500
            self._sync(document)
            self.host.publish('events', {'type': 'tk_bridge_status'})
            return self._status(document, is_local), 200

    def operation(self, token, auth_revision, peer, local, body):
        if not isinstance(body, dict) or not all(_name(body.get(k)) for k in ('namespace', 'event')):
            return _error('invalid')
        key, op, bridge_id = (body['namespace'], body['event']), body.get('op'), body.get('bridge_id')
        if op not in ('open', 'read', 'renew', 'close') or (op != 'open' and not _name(bridge_id)):
            return _error('invalid')
        selectors = {k: body[k] for k in ('section_id', 'cursor', 'node_id', 'revision') if k in body}
        if selectors and (op != 'read' or not all(_name(value) for value in selectors.values())):
            return _error('invalid')
        with self.host.lock:
            if not self._authorized(token, auth_revision):
                return _error('auth')
            if not self.local(peer, local):
                return _error('unsupported_environment')
            owner = self.host.credential_key(token)
            self._sweep()
            if op == 'close':
                session = self.sessions.get(bridge_id)
                if session and session.owner == owner and session.key == key and session.phase != 'closing':
                    self._revoke(bridge_id, session)
                    self.host.publish('events', {'type': 'tk_bridge_status'})
                return {'ok': True}, 200
            document = _load(self.host.root)
            self._sync(document)
            if document is None:
                return {'code': 'invalid_config', 'error': CONFIG_ERROR}, 409
            if self.profile_error:
                return {'code': 'invalid_profiles', 'error': self.profile_error}, 409
            if not self.ready:
                return _error('tk_unavailable')
            if key not in self.panels:
                return _error('unsupported_panel')
            if key not in self.target:
                return _error('disabled')
            if self.config_dirty or key not in self.applied:
                return _error('applying')
            if len(self.pending) >= MAX_SESSIONS:
                return _error('busy')
            if op == 'open':
                if any(session.key == key for session in self.sessions.values()):
                    return _error('occupied')
                if len(self.sessions) >= MAX_SESSIONS:
                    return _error('busy')
                bridge_id = opaque_id()
                self.sessions[bridge_id] = session = Session(key, owner, self.clock() + LEASE)
            else:
                session = self.sessions.get(bridge_id)
                if not session or session.key != key or session.owner != owner or session.phase != 'open':
                    return _error('panel_closed')
                if session.inflight or session.next_poll > self.clock():
                    return _error('busy')
                session.next_poll = self.clock() + 0.1
            expires = session.expiry if op == 'open' else self.clock() + LEASE
            data = self._intent(op, namespace=key[0], event=key[1], bridge_id=bridge_id,
                                owner=owner, expires=expires, **selectors)
            pending = self.pending[data['request_id']] = Pending(data)
            session.inflight = data['request_id']
            if not self._send(data):
                session.inflight = ''
                del self.pending[data['request_id']]
                if op == 'open':
                    del self.sessions[bridge_id]
                return _error('busy')
            session.possible_expiry = expires
        pending.done.wait(REQUEST_TIMEOUT)
        with self.host.lock:
            self.pending.pop(data['request_id'], None)
            session.inflight = ''
            if not self._authorized(token, auth_revision):
                if self.sessions.get(bridge_id) is session:
                    self._revoke(bridge_id, session, 'auth')
                return _error('auth')
            if data['generation'] != self.generation:
                return _error('stale_generation')
            if (key not in self.target
                    or session.phase == 'closing' and pending.result and pending.result[1] == 200):
                return _error('panel_closed')
            if pending.result is None:
                self._revoke(bridge_id, session)
                self.host.publish('events', {'type': 'tk_bridge_status'})
                return _error('timeout')
            return pending.result

    def receive(self, reply):
        with self.host.lock:
            if reply.get('generation') != self.generation:
                return
            request_id = reply.get('request_id')
            code = reply.get('code')
            if self.config_request and request_id == self.config_request['request_id']:
                if code is None:
                    self.config_dirty = False
                    self.applied = set(map(tuple, reply['enabled']))
                self.config_request = None
                self.host.publish('events', {'type': 'tk_bridge_status'})
                return
            bridge_id = reply.get('bridge_id')
            session = self.sessions.get(bridge_id)
            if not session or session.owner != reply.get('owner'):
                return
            if session.phase == 'closing':
                if ((not request_id and code == 'panel_closed')
                        or (session.revoke_request and request_id == session.revoke_request['request_id']
                            and code is None)):
                    self.sessions.pop(bridge_id, None)
                    self.host.publish('events', {'type': 'tk_bridge_status'})
                return
            if not request_id and code == 'panel_closed':
                # 首次快照失败时，后续请求回包会携带具体错误。
                if session.phase != 'opening':
                    session.phase = 'closing'
                    self.sessions.pop(bridge_id, None)
                    if pending := self.pending.get(session.inflight):
                        self._finish(pending, _error('panel_closed'))
                return
            pending = self.pending.get(request_id)
            if not pending or session.inflight != request_id:
                return
            if pending.data['deadline'] <= self.clock():
                return
            session.possible_expiry = 0
            if code:
                if pending.data['op'] == 'open' or code == 'panel_closed':
                    self.sessions.pop(bridge_id, None)
                self._finish(pending, _error(code if code in MESSAGES else 'panel_failed'))
            else:
                session.phase = 'open'
                session.expiry = pending.data['expires']
                response = {'ok': True, 'bridge_id': bridge_id}
                response.update({key: reply[key] for key in ('snapshot', 'unchanged') if key in reply})
                self._finish(pending, (response, 200))


def register_routes(host):
    def context():
        return (request.headers.get('X-Auth-Token', ''), g.webui_auth_revision,
                request.environ.get('olivos.tk_bridge.peer'), request.environ.get('olivos.tk_bridge.local'))

    def respond(result):
        payload, status = result
        return jsonify(payload), status

    def body():
        if not request.is_json or request.content_length is None or request.content_length > MAX_REQUEST:
            return None
        return request.get_json(silent=True)

    @host.app.get('/api/tk_bridge')
    def tk_bridge_status():
        return respond(host.tk_bridge.settings(*context()))

    @host.app.put('/api/tk_bridge/config')
    def tk_bridge_config():
        data = body()
        if not isinstance(data, dict):
            return respond(_error('invalid'))
        return respond(host.tk_bridge.settings(*context(), data))

    @host.app.post('/api/tk_bridge')
    def tk_bridge_operation():
        return respond(host.tk_bridge.operation(*context(), body()))
