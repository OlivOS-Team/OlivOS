import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from types import SimpleNamespace

import pytest

from OlivOS.core.core import tkBridgeAPI as tk
from OlivOS.webUI import tkBridgeAPI as web

ADDRESS = ('127.0.0.1', 9090)
TOKEN = 'webui.abc'
KEY = ('Example', 'Test_001')
META = {'namespace': KEY[0], 'event': KEY[1], 'title': 'Example menu'}


class Root:
    def __init__(self):
        self.owner_thread = threading.get_ident()
        self.children = []

    def winfo_children(self):
        assert threading.get_ident() == self.owner_thread
        return self.children

    def after(self, _delay, callback):
        assert threading.get_ident() == self.owner_thread
        self.tick = callback


class Window:
    def __init__(self, root):
        assert threading.get_ident() == root.owner_thread
        self.root = root
        root.children.append(self)
        self.widgets = {}
        self.hidden = False

    def __str__(self):
        return '.owned'

    def winfo_toplevel(self):
        return self

    def winfo_exists(self):
        return self in self.root.children

    def withdraw(self):
        assert threading.get_ident() == self.root.owner_thread
        self.hidden = True

    def destroy(self):
        assert threading.get_ident() == self.root.owner_thread
        self.root.children.remove(self)

    def nametowidget(self, path):
        assert threading.get_ident() == self.root.owner_thread
        return self.widgets[path]


def label(value, *, textvariable=''):
    return SimpleNamespace(winfo_class=lambda: 'Label',
                           cget=lambda key: {'textvariable': textvariable, 'text': value}[key])


def build_panel(root):
    window = Window(root)
    window.widgets['.owned.safe'] = label('allowed')
    window.widgets['.owned.private'] = label('NEVER SEND')
    return window


class Harness:
    def __init__(self, path, extra_profiles=()):
        self.now = 10
        self.controls = Queue()
        self.credentials = {'revision': 'auth-v1'}
        self.lock = threading.RLock()
        self.root = path
        self.tokens = {TOKEN, 'other-token'}
        self.browser_tokens = {self.credential_key(token): 10_000 for token in self.tokens}
        self.tk_root = Root()
        self.web = web.WebBridge(self, clock=lambda: self.now)
        self.trace = []
        self.events = []
        profile = path / tk.PROFILES_PATH
        profile.parent.mkdir(parents=True, exist_ok=True)
        profile.write_text(json.dumps({'version': 1, 'panels': [{
            'namespace': KEY[0], 'event': KEY[1], 'version': '1.2', 'svn': 34,
            'sections': [{'id': 's', 'title': 'Safe', 'widget': 'safe', 'kind': 'label', 'group': 'Read only'}],
        }, *extra_profiles]}), encoding='utf-8')

        def menu(plugin_event, Proc):
            assert (plugin_event.data.namespace, plugin_event.data.event) == KEY
            assert not hasattr(plugin_event.data, 'webui')
            build_panel(Proc.get_main_root())

        self.models = {KEY[0]: {'namespace': KEY[0], 'name': 'Example', 'version': '1.2', 'svn': 34,
                                'menu_config': [{'event': KEY[1], 'title': META['title']}],
                                'model': SimpleNamespace(main=SimpleNamespace(Event=SimpleNamespace(menu=menu)))}}
        proc = SimpleNamespace(Proc_info=SimpleNamespace(tx_queue=None, control_queue=None),
                               get_main_root=lambda: self.tk_root)
        self.loader = tk.TkBridge(lambda: self.models, self.reply, proc=proc, panels=tk.load_panels(path),
                                  clock=lambda: self.now)
        self.loader.start(self.tk_root)
        self.web.listen([ADDRESS])
        self.web.update(self.loader.metadata())

    def credential_key(self, token):
        return 'owner:' + token

    def browser_valid(self, token):
        return token in self.tokens

    def send_control(self, action, key):
        assert action == 'send' and key['target'] == {'type': 'plugin', 'fliter': 'control_only'}
        self.controls.put_nowait(key['data'])

    def publish(self, stream, event):
        assert stream == 'events'
        self.events.append(event)

    def reply(self, data):
        self.trace.append(data)
        self.web.receive(data)

    def pump(self, op, *, tick=True):
        data = self.controls.get(timeout=2)
        assert data['op'] == op
        self.loader.submit(data)
        if tick:
            self.tk_root.tick()
        return data

    def settings(self, body=None, *, peer=ADDRESS, local=ADDRESS):
        return self.web.settings(TOKEN, self.credentials['revision'], peer, local, body)

    def operation(self, op, *, token=TOKEN, **values):
        return self.web.operation(token, self.credentials['revision'], ADDRESS, ADDRESS,
                                  dict(namespace=KEY[0], event=KEY[1], op=op, **values))

    def enable(self):
        current, _ = self.settings()
        state, status = self.settings(dict(namespace=KEY[0], event=KEY[1], enabled=True, revision=current['revision']))
        assert status == 200 and state['panels'][0]['enabled'] and not state['panels'][0]['applied']
        self.pump('configure')
        assert self.events[-1] == {'type': 'tk_bridge_status'}
        assert self.settings()[0]['panels'][0]['applied']

    def open(self, pool):
        call = pool.submit(self.operation, 'open')
        self.pump('open')
        result, status = call.result(timeout=2)
        assert status == 200
        return result


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setattr(tk.platform, 'system', lambda: 'Windows')
    return Harness(tmp_path)


def test_production_gate_and_exact_loaded_menu(harness):
    missing = tk.load_panels(harness.root / 'missing')
    assert tk.TkBridge(lambda: harness.models, lambda _reply: None, panels=missing).metadata()['panels'] == []
    assert harness.loader.metadata()['panels'] == [META]
    harness.models[KEY[0]]['svn'] = '34'
    assert harness.loader.metadata()['panels'] == []
    harness.models[KEY[0]].update(svn=34, menu_config=[{'event': 'another', 'title': 'Other'}])
    assert harness.loader.metadata()['panels'] == []
    assert harness.tk_root.children == []


def test_one_menu_selects_config_for_the_loaded_version(harness):
    other = Harness(harness.root / 'other', extra_profiles=({
        'namespace': KEY[0], 'event': KEY[1], 'version': '2.0', 'svn': 50,
        'sections': [{'id': 'v2', 'title': 'Second version', 'widget': 'safe', 'kind': 'label'}],
    },))
    other.models[KEY[0]].update(version='2.0', svn=50)
    other.enable()
    with ThreadPoolExecutor() as pool:
        result = other.open(pool)
    section, = result['snapshot']['sections']
    assert section['id'] == 'v2' and section['text'] == 'allowed'


@pytest.mark.parametrize('edit', ['executable', 'absolute_path', 'duplicate', 'unbounded_tree'])
def test_invalid_host_profiles_are_rejected(harness, edit):
    path = harness.root / tk.PROFILES_PATH
    doc = json.loads(path.read_text(encoding='utf-8'))
    entry = doc['panels'][0]
    section = entry['sections'][0]
    if edit == 'executable':
        entry['builder'] = 'plugin.module.function'
    elif edit == 'absolute_path':
        section['widget'] = '.outside'
    elif edit == 'duplicate':
        doc['panels'].append(entry)
    else:
        section.update(kind='table', columns=[['value', 'Value']])
    path.write_text(json.dumps(doc), encoding='utf-8')
    with pytest.raises(ValueError, match='plugin_tk_profiles.json'):
        tk.load_panels(harness.root)


@pytest.mark.parametrize(('bind', 'peer', 'local'), [
    ([('0.0.0.0', 9090)], ADDRESS, ADDRESS),
    ([ADDRESS, ('::', 9090, 0, 0)], ADDRESS, ADDRESS),
    ([ADDRESS], ('192.0.2.1', 40000), ADDRESS),
    ([ADDRESS], None, ADDRESS),
    ([ADDRESS], ADDRESS, ('127.0.0.1', 9091)),
])
def test_real_loopback_listener_and_peer_are_required(harness, bind, peer, local):
    harness.web.listen(bind)
    state, _ = harness.settings(peer=peer, local=local)
    assert not state['panels'][0]['available']
    body = dict(namespace=KEY[0], event=KEY[1], enabled=True, revision=state['revision'])
    assert harness.settings(body, peer=peer, local=local)[0]['code'] == 'unsupported_environment'
    assert not (harness.root / web.CONFIG).exists()


def test_damaged_configuration_is_not_replaced(harness):
    path = harness.root / web.CONFIG
    path.write_text('{"version":99,"plugins":{}}', encoding='utf-8')
    state, _ = harness.settings()
    assert state['revision'] is None and state['error']
    response, status = harness.settings(dict(namespace=KEY[0], event=KEY[1], enabled=True, revision='old'))
    assert (response['code'], status) == ('invalid_config', 409)
    assert json.loads(path.read_text(encoding='utf-8'))['version'] == 99


def test_config_compare_and_swap_and_late_ack(harness):
    initial = harness.settings()[0]['revision']
    fields = dict(namespace=KEY[0], event=KEY[1], revision=initial)
    current, _ = harness.settings(dict(fields, enabled=True))
    assert harness.settings(dict(fields, enabled=False))[0]['code'] == 'stale_config'
    stopped, status = harness.settings(dict(fields, enabled=False, revision=current['revision']))
    assert status == 200 and not stopped['panels'][0]['applied']
    harness.pump('configure')
    assert not harness.settings()[0]['panels'][0]['applied']
    harness.pump('configure')
    assert harness.settings()[0]['panels'][0]['applied']
    assert harness.operation('open')[0]['code'] == 'disabled'


def test_open_read_and_close_are_private_and_hide_only_owned_window(harness):
    desktop = Window(harness.tk_root)
    assert harness.operation('open')[0]['code'] == 'disabled'
    harness.enable()
    with ThreadPoolExecutor() as pool:
        opened = harness.open(pool)
        bridge_id, snap = opened['bridge_id'], opened['snapshot']
        window = harness.tk_root.children[-1]
        assert window is not desktop and window.hidden and not desktop.hidden
        assert snap['sections'][0]['text'] == 'allowed'
        assert snap['sections'][0]['group'] == 'Read only'
        assert 'NEVER SEND' not in json.dumps(harness.trace)
        assert harness.operation('open')[0]['code'] == 'occupied'
        assert harness.operation('read', token='other-token', bridge_id=bridge_id)[0]['code'] == 'panel_closed'
        read = pool.submit(harness.operation, 'read', bridge_id=bridge_id, revision=snap['revision'])
        harness.pump('read')
        assert read.result(timeout=2)[0]['unchanged']
        assert harness.operation('close', bridge_id=bridge_id) == ({'ok': True}, 200)
        assert harness.operation('open')[0]['code'] == 'occupied'
        harness.pump('revoke')
        assert harness.tk_root.children == [desktop]
        assert harness.operation('close', bridge_id=bridge_id) == ({'ok': True}, 200)


def test_logout_cancels_open_already_in_loader_queue(harness):
    harness.enable()
    with ThreadPoolExecutor() as pool:
        opening = pool.submit(harness.operation, 'open')
        harness.pump('open', tick=False)
        with harness.lock:
            harness.tokens.remove(TOKEN)
            harness.web.revoke(harness.credential_key(TOKEN))
        harness.pump('revoke')
        assert opening.result(timeout=2)[0]['code'] == 'auth'
    assert harness.tk_root.children == []


def test_revoke_drops_waiting_snapshot_and_old_generation_reply(harness):
    harness.enable()
    with ThreadPoolExecutor() as pool:
        opened = harness.open(pool)
        read = pool.submit(harness.operation, 'read', bridge_id=opened['bridge_id'])
        data = harness.pump('read', tick=False)
        harness.web.invalidate()
        harness.reply(dict(data, code=None, snapshot={'sections': ['STALE']}))
        result, status = read.result(timeout=2)
        assert status == 409 and result['code'] == 'stale_generation' and 'snapshot' not in result
    harness.pump('revoke')
    assert not harness.tk_root.children


def test_renewal_extends_lease_without_projecting(harness):
    harness.enable()
    with ThreadPoolExecutor() as pool:
        opened = harness.open(pool)
        window = harness.tk_root.children[0]
        window.widgets.clear()  # 续租不读取已失效的控件。
        harness.now += tk.LEASE - 1
        renew = pool.submit(harness.operation, 'renew', bridge_id=opened['bridge_id'])
        harness.pump('renew')
        assert renew.result(timeout=2) == ({'ok': True, 'bridge_id': opened['bridge_id']}, 200)
        harness.now += 2
        harness.tk_root.tick()
        assert window.winfo_exists()
        harness.now += tk.LEASE
        harness.tk_root.tick()
        assert not window.winfo_exists()
    assert harness.operation('renew', bridge_id=opened['bridge_id'])[0]['code'] == 'panel_closed'


def test_unchanged_reads_extend_visible_lease(harness):
    harness.enable()
    with ThreadPoolExecutor() as pool:
        opened = harness.open(pool)
        harness.now += tk.LEASE - 1
        read = pool.submit(harness.operation, 'read', bridge_id=opened['bridge_id'],
                           revision=opened['snapshot']['revision'])
        harness.pump('read')
        assert read.result(timeout=2)[0]['unchanged']
        harness.now += 2
        harness.tk_root.tick()
        assert harness.tk_root.children


def test_disappeared_window_and_loader_stop_revoke_owner_sessions(harness):
    harness.enable()
    with ThreadPoolExecutor() as pool:
        opened = harness.open(pool)
        harness.tk_root.children[0].destroy()
        harness.tk_root.tick()
        assert harness.operation('renew', bridge_id=opened['bridge_id'])[0]['code'] == 'panel_closed'
        harness.open(pool)
        harness.loader.stop()
        assert not harness.loader.metadata()['tk_ready']
        assert not harness.loader.cleaned.is_set()
        harness.tk_root.tick()
        assert harness.loader.cleaned.is_set() and not harness.tk_root.children


def test_text_range_and_unapproved_variable(harness):
    window = Window(harness.tk_root)
    calls = []

    def text_get(first, last):
        calls.append((first, last))
        return '我' * (tk.MAX_TEXT + 1)

    window.widgets['.owned.text'] = SimpleNamespace(winfo_class=lambda: 'Text', get=text_get)
    text = tk.Section('s', 'Text', 'text', 'text')
    projection = tk.Projection(tk.Panel(*KEY, '1.2', 34, (text,)), window)
    data = projection.snapshot()['sections'][0]
    assert calls == [('1.0', f'1.0 + {tk.MAX_TEXT + 1} chars')]
    assert data['truncated'] and len(data['text'].encode()) <= tk.MAX_TEXT
    window.widgets['.owned.label'] = label('secret', textvariable='unapproved_tcl_var')
    projection.panel = tk.Panel(*KEY, '1.2', 34, (tk.Section('s', 'Label', 'label', 'label'),))
    with pytest.raises(tk.BridgeError, match='unsupported_panel'):
        projection.snapshot()


def test_paginated_tables_read_only_allowlisted_cells_and_opaque_handles(harness):
    window = Window(harness.tk_root)
    rows = [f'private-row-{i}' for i in range(103)]
    seen = []

    def cell(iid, column):
        seen.append(column)
        return iid.split('-')[-1]

    window.widgets['.owned.table'] = SimpleNamespace(winfo_class=lambda: 'Treeview', set=cell,
                                                     get_children=lambda _parent: tuple(rows))
    table = tk.Section('s', 'Table', 'table', 'table', (('visible', 'Public'),), 120)
    projection = tk.Projection(tk.Panel(*KEY, '1.2', 34, (table,)), window)
    snapshot = projection.snapshot()
    first = snapshot['sections'][0]
    assert len(first['rows']) == 100 and first['columns'] == ['Public']
    assert 'private-row-' not in json.dumps(first)
    assert snapshot == projection.snapshot()
    last = projection.snapshot('s', first['next_cursor'])['sections'][0]
    assert len(last['rows']) == 3 and 'next_cursor' not in last
    assert set(seen) == {'visible'}
    rows.pop(0)
    with pytest.raises(tk.BridgeError, match='data_changed'):
        projection.snapshot('s', first['next_cursor'])


def test_child_cursor_keeps_parent_and_total_snapshot_bytes_are_bounded(harness):
    window = Window(harness.tk_root)
    children = ('internal-parent',) + tuple(f'internal-child-{i}' for i in range(101))

    def get_children(iid):
        return {'': children[:1], children[0]: children[1:]}.get(iid, ())

    window.widgets['.owned.table'] = SimpleNamespace(
        winfo_class=lambda: 'Treeview', exists=lambda iid: iid in children,
        set=lambda _iid, _column: '\\' * tk.MAX_CELL, get_children=get_children,
    )
    columns = tuple((str(i), f'Column {i}') for i in range(8))
    table = tk.Section('s', 'Table', 'table', 'table', columns, 101, hierarchy=True)
    projection = tk.Projection(tk.Panel(*KEY, '1.2', 34, (table,)), window)
    main = projection.snapshot()['sections'][0]
    parent = main['rows'][0]
    assert parent['has_children']
    detail = projection.snapshot('s', node_id=parent['id'])
    first = detail['sections'][0]
    assert 0 < len(first['rows']) < tk.MAX_ROWS
    assert len(json.dumps(detail).encode()) <= tk.MAX_SNAPSHOT
    assert 'internal-' not in json.dumps(detail)
    next_page = projection.snapshot('s', cursor=first['next_cursor'])['sections'][0]
    assert next_page['rows'][0]['id'] != first['rows'][0]['id']


def test_table_with_shared_row_budget_can_still_be_opened_on_its_own(harness):
    window = Window(harness.tk_root)
    for name in ('first', 'second'):
        window.widgets[f'.owned.{name}'] = SimpleNamespace(
            winfo_class=lambda: 'Treeview', get_children=lambda _: tuple(map(str, range(101))),
            set=lambda row, _column: row,
        )
    sections = tuple(tk.Section(name, name, name, 'table', (('value', '值'),), 101)
                     for name in ('first', 'second'))
    projection = tk.Projection(tk.Panel(*KEY, '1.2', 34, sections), window)
    first, second = projection.snapshot()['sections']
    assert len(first['rows']) == tk.MAX_ROWS and first['next_cursor']
    assert second['truncated'] and not second['rows'] and not second.get('next_cursor')
    targeted, = projection.snapshot('second')['sections']
    assert targeted['rows'][0]['cells'] == ['0'] and targeted['next_cursor']


@pytest.mark.skipif(sys.platform != 'win32', reason='需要 Windows 桌面 Tk')
def test_native_tk_hidden_widget_projection():
    import tkinter
    from tkinter import ttk

    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        pytest.skip(f'Windows 桌面不可用：{error}')
    root.withdraw()
    try:
        def menu(plugin_event, Proc):
            assert plugin_event.data.event == KEY[1]
            window = tkinter.Toplevel(Proc.get_main_root(), class_='CustomSettingsWindow')
            ttk.Label(window, name='label', text='hello').pack()
            text = tkinter.Text(window, name='content')
            text.insert('1.0', 'first line\nsecond line')
            text.pack()
            table = ttk.Treeview(window, name='table', columns=('safe', 'hidden'), show='headings')
            table.insert('', 'end', text='Tree label', values=('hello', 'never export'))
            table.pack()

        sections = (tk.Section('l', 'Label', 'label', 'label'), tk.Section('t', 'Text', 'content', 'text'),
                    tk.Section('r', 'Table', 'table', 'table', (('#0', 'Tree'), ('safe', 'Safe')), 1))
        panel = tk.Panel(*KEY, '1.2', 34, sections)
        model = dict(namespace=KEY[0], name=KEY[0], version='1.2', svn=34, menu_config=[META],
                     model=SimpleNamespace(main=SimpleNamespace(Event=SimpleNamespace(menu=menu))))
        proc = SimpleNamespace(Proc_info=SimpleNamespace(tx_queue=None, control_queue=None),
                               get_main_root=lambda: root)
        replies = []
        bridge = tk.TkBridge(lambda: {KEY[0]: model}, replies.append, proc=proc, panels=[panel])
        bridge.start(root)
        now = bridge.clock()
        request = dict(generation=bridge.generation, deadline=now + 3)
        bridge.submit(dict(request, op='configure', request_id='configure', serial=1, enabled=[KEY]))
        bridge.submit(dict(request, op='open', request_id='open', bridge_id='preview', owner='owner',
                           namespace=KEY[0], event=KEY[1], expires=now + tk.LEASE))
        bridge._tick()
        window, = root.winfo_children()
        snap = replies[-1]['snapshot']
        assert snap['sections'][0]['text'] == 'hello'
        assert 'second line' in snap['sections'][1]['text']
        assert snap['sections'][2]['rows'][0]['cells'] == ['Tree label', 'hello']
        root.update_idletasks()
        assert not window.winfo_ismapped() and 'never export' not in json.dumps(snap)
        bridge.stop()
        bridge._tick()
        assert not window.winfo_exists()
    finally:
        root.destroy()
