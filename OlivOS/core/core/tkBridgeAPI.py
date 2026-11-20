# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/core/core/tkBridgeAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   Allowlisted, read-only projection of independent Tk windows
'''

import hashlib
import json
import platform
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Full, Queue

try:
    from tkinter import TclError
except ImportError:
    TCL_ERRORS = ()
else:
    TCL_ERRORS = (TclError,)

LEASE = 30
REQUEST_TIMEOUT = 3
MAX_SESSIONS = 16
MAX_ROWS = 100
MAX_TEXT = 8192
MAX_CELL = 512
MAX_SNAPSHOT = 128 * 1024
MAX_HANDLES = 512
PROFILES_PATH = Path('conf/plugin_tk_profiles.json')
MAX_PROFILES_BYTES = 64 * 1024
_SNAPSHOT_MARGIN = 4096  # 为外层回包和各分区的分页字段留空间
_WIDGET_CLASSES = {'label': ('Label', 'TLabel'), 'text': ('Text',), 'table': ('Treeview',)}


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    widget: str
    kind: str
    columns: tuple = ()  # （经审核的 Tk 列标识，网页显示标题）
    sibling_limit: int = 0  # 经审核的同层节点数量上限
    hierarchy: bool = False
    textvariable: str = ''  # 只读明确批准的 Tcl 变量，默认不读取
    group: str = ''


@dataclass(frozen=True)
class Panel:
    namespace: str
    event: str
    version: str
    svn: int
    sections: tuple

    @property
    def key(self):
        return self.namespace, self.event

    def match(self, models):
        model = models.get(self.namespace)
        if (model and model.get('namespace') == self.namespace and model.get('version') == self.version
                and type(model.get('svn')) is int and model['svn'] == self.svn):
            plugin = model.get('model')
            event = getattr(getattr(plugin, 'main', None), 'Event', None)
            menu_config = model.get('menu_config')
            if not callable(getattr(event, 'menu', None)) or not isinstance(menu_config, list):
                return None
            for item in menu_config:
                if isinstance(item, dict) and item.get('event') == self.event and isinstance(item.get('title'), str):
                    return model, item['title']
        return None


def _string(value):
    return isinstance(value, str) and 0 < len(value) <= 256


def _section(data):
    if not isinstance(data, dict) or not all(_string(data.get(key)) for key in ('id', 'title', 'widget', 'kind')):
        raise ValueError
    kind, widget = data['kind'], data['widget']
    if (kind not in _WIDGET_CLASSES or not all(widget.split('.'))
            or any(ord(character) < 32 or ord(character) == 127 for character in widget)):
        raise ValueError
    fields = {'id', 'title', 'widget', 'kind', 'group'}
    if 'group' in data and not _string(data['group']):
        raise ValueError
    if kind == 'table':
        fields.update(('columns', 'sibling_limit', 'hierarchy'))
        columns, limit = data.get('columns'), data.get('sibling_limit')
        if (not isinstance(columns, list) or not 0 < len(columns) <= 16
                or any(not isinstance(col, list) or len(col) != 2 or not all(map(_string, col)) for col in columns)
                or len({col[0] for col in columns}) != len(columns)
                or type(limit) is not int or not 0 < limit <= MAX_HANDLES
                or type(data.get('hierarchy', False)) is not bool):
            raise ValueError
    elif kind == 'label':
        fields.add('textvariable')
        if 'textvariable' in data and not _string(data['textvariable']):
            raise ValueError
    if data.keys() - fields:
        raise ValueError
    section = dict(data)
    if kind == 'table':
        section['columns'] = tuple(map(tuple, section['columns']))
    return Section(**section)


def load_panels(root):
    """读取宿主单独审核的只读描述。不读取插件声明，也不接受可执行字段。"""
    try:
        with (Path(root) / PROFILES_PATH).open('rb') as source:
            raw = source.read(MAX_PROFILES_BYTES + 1)
        if len(raw) > MAX_PROFILES_BYTES:
            raise ValueError
        doc = json.loads(raw)
        if (not isinstance(doc, dict) or set(doc) != {'version', 'panels'}
                or type(doc['version']) is not int or doc['version'] != 1 or not isinstance(doc['panels'], list)):
            raise ValueError
        panels = []
        keys = set()
        for data in doc['panels']:
            if (not isinstance(data, dict) or set(data) != {'namespace', 'event', 'version', 'svn', 'sections'}
                    or not all(_string(data[key]) for key in ('namespace', 'event', 'version'))
                    or type(data['svn']) is not int or data['svn'] < 0
                    or not isinstance(data['sections'], list) or not 0 < len(data['sections']) <= 16):
                raise ValueError
            sections = tuple(map(_section, data['sections']))
            if len(_encoded(list(map(_section_header, sections)))) > MAX_SNAPSHOT - _SNAPSHOT_MARGIN:
                raise ValueError
            panel = Panel(data['namespace'], data['event'], data['version'], data['svn'], sections)
            identity = panel.key + (panel.version, panel.svn)
            if identity in keys or len({section.id for section in sections}) != len(sections):
                raise ValueError
            keys.add(identity)
            panels.append(panel)
        return panels
    except FileNotFoundError:
        return ()
    except (OSError, ValueError, RecursionError):
        raise ValueError(f'Tk 兼容描述无效，请检查 {PROFILES_PATH.as_posix()}') from None


class BridgeError(Exception):
    pass


def opaque_id():
    return secrets.token_urlsafe(18)


def _fail(code):
    raise BridgeError(code)


def _encoded(value):
    return json.dumps(value, ensure_ascii=True, separators=(',', ':')).encode('ascii')


def _section_header(section):
    entry = {'id': section.id, 'title': section.title, 'type': section.kind}
    if section.group:
        entry['group'] = section.group
    if section.kind == 'table':
        entry.update(columns=[title for _, title in section.columns], rows=[])
    else:
        entry['text'] = ''
    return entry


def _bounded(value, limit):
    # 先截取再编码，避免超长字段增加临时内存占用。
    value = str(value)
    data = value[:limit].encode('utf-8', 'replace')
    truncated = len(value) > limit or len(data) > limit
    return data[:limit].decode('utf-8', 'ignore'), truncated


def _windows(root):
    # Toplevel 可自定义 Tk 类名，不能靠 winfo_class() 判断窗口归属。
    return {child for child in root.winfo_children() if child.winfo_toplevel() is child}


def _menu(model, panel, proc):
    from . import API

    packet = API.Control.packet('send', {'data': {
        'action': 'plugin_menu', 'namespace': panel.namespace, 'event': panel.event,
    }})
    event = API.Event(sdk_event=packet)
    event.plugin_info.update(name=model['name'], namespace=panel.namespace,
                             tx_queue=proc.Proc_info.tx_queue, control_queue=proc.Proc_info.control_queue)
    for source, target in (('compatible_svn', 'compatible_svn'), ('message_mode', 'message_mode_tx')):
        if source in model:
            event.plugin_info[target] = model[source]
    event.get_Event_on_Plugin()
    model['model'].main.Event.menu(plugin_event=event, Proc=proc)


@dataclass
class Projection:
    panel: Panel
    window: object
    handles: OrderedDict = field(default_factory=OrderedDict)
    tokens: dict = field(default_factory=dict)

    def handle(self, key):
        token = self.tokens.get(key)
        if token is None:
            token = opaque_id()
            if len(self.handles) >= MAX_HANDLES:
                _, old = self.handles.popitem(last=False)
                del self.tokens[old]
            self.handles[token] = key
            self.tokens[key] = token
        else:
            self.handles.move_to_end(token)
        return token

    def resolve(self, token, prefix):
        key = self.handles.get(token)
        if not key or key[:len(prefix)] != prefix:
            _fail('data_changed')
        self.handles.move_to_end(token)
        return key[len(prefix):]

    def widget(self, section):
        try:
            widget = self.window.nametowidget(f'{self.window}.{section.widget}')
        except KeyError:
            _fail('data_changed')
        if widget.winfo_class() not in _WIDGET_CLASSES[section.kind]:
            _fail('data_changed')
        return widget

    def table(self, section, widget, result, cursor, node_id, remaining_rows, remaining_bytes):
        parent, offset = '', 0
        previous = None
        if node_id:
            if not section.hierarchy:
                _fail('data_changed')
            (parent,) = self.resolve(node_id, ('row', section.id))
        if cursor:
            cursor_parent, offset, previous = self.resolve(cursor, ('cursor', section.id))
            if node_id and cursor_parent != parent:
                _fail('data_changed')
            parent = cursor_parent
        if parent and not widget.exists(parent):
            _fail('data_changed')
        children = self._siblings(section, widget, parent)
        if previous is not None and (offset > len(children) or children[offset - 1] != previous):
            _fail('data_changed')
        result['rows'] = rows = []
        for index in range(offset, min(len(children), offset + remaining_rows)):
            iid = children[index]
            values = [_bounded(widget.item(iid, 'text') if column == '#0' else widget.set(iid, column), MAX_CELL)
                      for column, _ in section.columns]
            row = {'id': self.handle(('row', section.id, iid)), 'cells': [value for value, _ in values],
                   'has_children': section.hierarchy and bool(self._siblings(section, widget, iid))}
            if any(truncated for _, truncated in values):
                row['truncated'] = True
            size = len(_encoded(row)) + 2
            if size > remaining_bytes:
                break
            rows.append(row)
            remaining_bytes -= size
        offset += len(rows)
        if rows and offset < len(children):
            result['next_cursor'] = self.handle(('cursor', section.id, parent, offset, children[offset - 1]))
        elif offset < len(children):
            result['truncated'] = True
        return len(rows)

    @staticmethod
    def _siblings(section, widget, parent):
        # Tk 一次返回整层节点，只允许读取经审核、已有上限的树。
        if not 0 < section.sibling_limit <= MAX_HANDLES:
            _fail('unsupported_panel')
        children = widget.get_children(parent)
        if len(children) > section.sibling_limit:
            _fail('unsupported_panel')
        return children

    def snapshot(self, section_id=None, cursor=None, node_id=None):
        if not self.window.winfo_exists():
            _fail('panel_closed')
        if (cursor or node_id) and not section_id:
            _fail('data_changed')
        sections = [section for section in self.panel.sections if section_id is None or section.id == section_id]
        if not sections or len(sections) > 16:
            _fail('data_changed')
        if (cursor or node_id) and sections[0].kind != 'table':
            _fail('data_changed')
        result = list(map(_section_header, sections))
        # 先保留所有分区的标题和翻页字段；大表不能挤掉其他分区的入口。
        remaining_rows = MAX_ROWS
        remaining_bytes = MAX_SNAPSHOT - _SNAPSHOT_MARGIN - len(_encoded(result))
        for section, entry in zip(sections, result):
            widget = self.widget(section)
            base_size = len(_encoded(entry))
            if section.kind == 'table':
                remaining_rows -= self.table(section, widget, entry, cursor, node_id, remaining_rows,
                                             max(0, remaining_bytes))
            else:
                if section.kind == 'label':
                    name = str(widget.cget('textvariable'))
                    if name and name != section.textvariable:
                        _fail('unsupported_panel')
                    text = widget.getvar(name) if name else widget.cget('text')
                else:
                    text = widget.get('1.0', f'1.0 + {MAX_TEXT + 1} chars')
                text, truncated = _bounded(text, min(MAX_TEXT, max(0, remaining_bytes // 6)))
                entry.update(text=text, truncated=truncated)
            remaining_bytes -= len(_encoded(entry)) - base_size
        revision = hashlib.blake2s(_encoded(result), digest_size=12).hexdigest()
        return {'revision': revision, 'sections': result}

    def destroy(self):
        if self.window.winfo_exists():
            self.window.destroy()


@dataclass
class Lease:
    key: tuple
    owner: str
    expiry: float
    projection: Projection = None
    revoked: bool = False


class TkBridge:
    def __init__(self, models_callable, reply_callable, proc=None, *, panels=(), profile_error=None,
                 clock=time.monotonic):
        self.models = models_callable
        self.reply = reply_callable
        self.proc = proc
        self.panels = {}
        for panel in panels:
            self.panels.setdefault(panel.key, []).append(panel)
        self.profile_error = profile_error
        self.clock = clock
        self.generation = opaque_id()
        self.ready = False
        self.stopped = False
        self.root = None
        self.lock = threading.RLock()
        self.queue = Queue(maxsize=16)
        self.enabled = set()
        self.queued_opens = {}
        self.leases = {}
        self.last_config = 0
        self.cleaned = threading.Event()

    def _match(self, models, key):
        for panel in self.panels.get(key, ()):
            match = panel.match(models)
            if match is not None:
                return panel, match
        return None, None

    def metadata(self):
        with self.lock:
            panels = []
            if self.panels:
                models = self.models()
                for key in self.panels:
                    _, matched = self._match(models, key)
                    if matched:
                        panels.append(dict(namespace=key[0], event=key[1], title=matched[1]))
            return dict(generation=self.generation, tk_ready=self.ready and not self.stopped, panels=panels,
                        profile_error=self.profile_error)

    def start(self, root):
        if not self.panels or platform.system() != 'Windows':
            return
        # 创建根窗口的线程负责所有控件操作。
        with self.lock:
            if self.stopped:
                return
            self.root = root
            self.ready = True
        self._tick()

    def stop(self):
        with self.lock:
            self.stopped = True
            if self.root is None:
                self.cleaned.set()
            for lease in self.leases.values():
                lease.revoked = True

    def _response(self, data, error=None, **fields):
        try:
            self.reply(dict(action='tk_bridge_reply', generation=self.generation, request_id=data['request_id'],
                            owner=data.get('owner'), bridge_id=data.get('bridge_id'), code=error, **fields))
        except Full:
            # 请求时限和租约到期会回收访问，不因回包丢失而延长。
            return

    def submit(self, data):
        if not isinstance(data, dict) or not isinstance(data.get('request_id'), str):
            return
        fields = {}
        with self.lock:
            op = data.get('op')
            if data.get('generation') != self.generation or self.stopped:
                error = 'stale_generation'
            elif not self.ready:
                error = 'tk_unavailable'
            elif data.get('deadline', 0) <= self.clock() and op not in ('revoke', 'configure'):
                error = 'timeout'
            elif op == 'configure':
                # 设置和撤销不进入控件队列，队列满时仍能撤销权限。
                serial = data['serial']
                if serial <= self.last_config:
                    error = 'stale_config'
                else:
                    self.last_config = serial
                    models = self.models()
                    self.enabled = {key for item in data['enabled'] if self._match(models, key := tuple(item))[1]}
                    for lease in self.leases.values():
                        if lease.key not in self.enabled:
                            lease.revoked = True
                    for bridge_id, queued in self.queued_opens.items():
                        if queued and queued[1] not in self.enabled:
                            self.queued_opens[bridge_id] = None
                    fields['enabled'] = sorted(self.enabled)
                    error = None
            elif op == 'revoke':
                lease = self.leases.get(data.get('bridge_id'))
                if lease and lease.owner == data.get('owner'):
                    lease.revoked = True
                    return  # 只有 Tk 所属线程能确认窗口已销毁。
                bridge_id = data.get('bridge_id')
                queued = self.queued_opens.get(bridge_id)
                if queued and queued[0] == data.get('owner'):
                    self.queued_opens[bridge_id] = None
                error = None
            elif op in ('open', 'read', 'renew'):
                try:
                    self.queue.put_nowait(data)
                    if op == 'open':
                        self.queued_opens[data['bridge_id']] = (data['owner'], (data['namespace'], data['event']))
                    return
                except Full:
                    error = 'busy'
            else:
                error = 'invalid'
        self._response(data, error, **fields)

    def _sweep(self):
        with self.lock:
            leases = list(self.leases.items())
        for bridge_id, lease in leases:
            try:
                alive = lease.projection is not None and lease.projection.window.winfo_exists()
            except TCL_ERRORS:
                alive = False
            if not lease.revoked and lease.expiry > self.clock() and (alive or lease.projection is None):
                continue
            try:
                if alive:
                    lease.projection.destroy()
                    if lease.projection.window.winfo_exists():
                        continue
            except TCL_ERRORS + (RuntimeError,):
                continue  # 未确认窗口销毁前，不允许其他会话打开同一面板。
            with self.lock:
                self.leases.pop(bridge_id, None)
            self._response(dict(request_id='', bridge_id=bridge_id, owner=lease.owner), 'panel_closed')

    def _tick(self):
        self._sweep()
        for _ in range(4):
            try:
                data = self.queue.get_nowait()
            except Empty:
                break
            try:
                self._response(data, **self._execute(data))
            except BridgeError as exc:
                self._response(data, str(exc))
            except Exception:
                # 插件异常可能含有控件值或路径，不能直接回传给浏览器。
                self._response(data, 'panel_failed')
        with self.lock:
            if not self.stopped or self.leases:
                self.root.after(50, self._tick)
            else:
                self.cleaned.set()

    def _validate(self, data, key):
        if self.stopped or data['generation'] != self.generation:
            _fail('stale_generation')
        if data['deadline'] <= self.clock():
            _fail('timeout')
        panel, matched = self._match(self.models(), key)
        if not matched or key not in self.enabled:
            _fail('disabled')
        return panel, matched[0]

    def _execute(self, data):
        key = data['namespace'], data['event']
        op, bridge_id, owner = data['op'], data['bridge_id'], data['owner']
        with self.lock:
            if op == 'open' and self.queued_opens.pop(bridge_id, None) != (owner, key):
                _fail('panel_closed')
            panel, model = self._validate(data, key)
            if op == 'open':
                if any(lease.key == key for lease in self.leases.values()):
                    _fail('occupied')
                if len(self.leases) >= MAX_SESSIONS:
                    _fail('busy')
                lease = self.leases[bridge_id] = Lease(key, owner, data['expires'])
            else:
                lease = self.leases.get(bridge_id)
                if (not lease or lease.revoked or lease.key != key or lease.owner != owner
                        or lease.expiry <= self.clock()):
                    _fail('panel_closed')
                if op == 'renew':
                    lease.expiry = data['expires']
                    return {}
        try:
            if op == 'open':
                before = _windows(self.root)
                with self.lock:
                    self._validate(data, key)
                    if lease.revoked or lease.expiry <= self.clock():
                        _fail('panel_closed')
                try:
                    _menu(model, panel, self.proc)
                finally:
                    added = _windows(self.root) - before
                    if len(added) == 1:
                        (created,) = added
                        lease.projection = Projection(panel, created)
                        created.withdraw()
                    elif added:
                        for created in added:
                            created.destroy()
                if len(added) == 0:
                    _fail('desktop_open')
                if len(added) != 1:
                    _fail('unsupported_panel')
            with self.lock:
                self._validate(data, key)
                if lease.revoked or lease.expiry <= self.clock():
                    _fail('panel_closed')
            snapshot = lease.projection.snapshot(data.get('section_id'), data.get('cursor'), data.get('node_id'))
            with self.lock:
                self._validate(data, key)
                if lease.revoked or lease.expiry <= self.clock():
                    _fail('panel_closed')
                if op == 'read':
                    lease.expiry = data['expires']
            if op == 'read' and snapshot['revision'] == data.get('revision'):
                return {'unchanged': True}
            return {'snapshot': snapshot}
        except Exception as exc:
            if op == 'open' or isinstance(exc, TCL_ERRORS) or (
                    isinstance(exc, BridgeError) and str(exc) == 'panel_closed'):
                with self.lock:
                    lease.revoked = True
                self._sweep()
            if isinstance(exc, TCL_ERRORS):
                _fail('panel_closed')
            raise
