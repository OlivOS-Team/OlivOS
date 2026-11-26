"""Tray account management and the existing hot-reload control bus."""

import base64
import gc
import os
import queue
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

import OlivOS

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows account GUI')


@pytest.fixture
def account_editor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    bot = OlivOS.API.bot_info_T(
        id=10001, platform_sdk='terminal_link', platform_platform='terminal', platform_model='default')
    accounts = {bot.hash: bot}
    control = queue.Queue()
    editor = OlivOS.multiLoginUIAPI.HostUI('test', accounts, asaycMode=True, control_queue=control)
    editor.tree_load = Mock()
    editor.UIObject['root'] = Mock()
    return editor, accounts, control


def test_tray_account_management_starts_existing_edit_workflow():
    control = queue.Queue()
    dock = OlivOS.nativeWinUIAPI.dock(control_queue=control, bot_info_dict={})
    entry = next(item for item in dock.UIData['shallow_menu_list'] if item[0] == '账号管理')
    entry[1]()
    packet = control.get_nowait()
    assert packet.action == 'call_system_event'
    assert packet.key['action'] == ['account_edit_asayc_start', 'account_edit_asayc_do']


def test_cancelling_account_edit_keeps_running_account_objects(account_editor):
    editor, accounts, control = account_editor
    key = next(iter(accounts))
    editor.UIData['Account_data'][key].enable = False
    editor.UIData['Account_data'][key].extends['draft'] = True
    editor.tree_edit_commit(['delete', key, None])
    assert accounts[key].enable is True
    assert 'draft' not in accounts[key].extends
    assert control.empty()


@pytest.mark.parametrize('action', ['create', 'update', 'delete'])
def test_account_editor_updates_draft_list(account_editor, action):
    editor, accounts, _ = account_editor
    old = next(iter(accounts))
    new = OlivOS.API.bot_info_T(id=10002)
    editor.tree_edit_commit([action, old, new])
    draft = editor.UIData['Account_data']
    assert (new.hash in draft) is (action != 'delete')
    assert (old in draft) is (action == 'create')
    editor.tree_load.assert_called_once()


def test_account_save_requests_persistence_then_hot_reload(account_editor):
    editor, accounts, control = account_editor
    key = next(iter(accounts))
    editor.UIData['Account_data'][key].enable = False
    editor.account_data_commit()
    packets = [control.get_nowait() for _ in range(4)]
    assert [packet.action for packet in packets] == [
        'call_system_event', 'call_account_update', 'call_system_stop_type_event', 'call_system_event']
    assert packets[0].key['action'] == ['account_edit_asayc_end']
    assert packets[1].key['data'][key].enable is False
    assert packets[2].key['action'] == packets[3].key['action'] == ['account_update']
    steps = OlivOS.bootDataAPI.default_Conf['system']['event']['account_edit_asayc_end']
    assert 'OlivOS_account_config_save' in steps and 'OlivOS_account_config_update' in steps
    assert editor.UIData['flag_commit'] is True
    editor.UIObject['root'].destroy.assert_called_once()


def test_terminal_model_switch_uses_launcher_init_and_closes_old():
    import copy

    bot = OlivOS.API.bot_info_T(
        id=10001, platform_sdk='onebot', platform_platform='qq', platform_model='napcat_show')
    inbox = queue.Queue()
    dock = OlivOS.nativeWinUIAPI.dock(
        rx_queue=inbox, control_queue=queue.Queue(), bot_info_dict={bot.hash: bot})
    dock.updateShallowMenuList = Mock()
    dock.startNapCatTerminalUI = Mock()
    window = Mock(bot=copy.deepcopy(bot))
    dock.UIObject['root_napcat_terminal'][bot.hash] = window
    window.stop.side_effect = lambda: dock.UIObject['root_napcat_terminal'].pop(bot.hash)
    changed = copy.deepcopy(bot)
    changed.platform['model'] = 'napcat_default'
    packet = OlivOS.API.Control.packet('send', {'data': {
        'action': 'account_update', 'data': {bot.hash: changed}}})
    dock.on_control_rx(packet)
    window.stop.assert_not_called()
    dock.mainrun()
    window.stop.assert_called_once()
    dock.startNapCatTerminalUI.assert_not_called()
    inbox.put(OlivOS.API.Control.packet('send', {'data': {
        'action': 'napcat', 'event': 'init', 'hash': bot.hash, 'account_platform': bot.platform}}))
    dock.mainrun()
    assert inbox.empty()
    dock.on_control_rx(OlivOS.API.Control.packet('send', {'data': {
        'action': 'account_update', 'data': {bot.hash: bot}}}))
    dock.mainrun()
    inbox.put(OlivOS.API.Control.packet('send', {'data': {
        'action': 'napcat', 'event': 'init', 'hash': bot.hash, 'account_platform': bot.platform}}))
    dock.mainrun()
    dock.mainrun()
    dock.startNapCatTerminalUI.assert_called_once_with(bot.hash)


@pytest.mark.parametrize('module,model', [
    ('libNapCatEXEModelAPI', 'napcat_show'), ('libEXEModelAPI', 'gocqhttp_show'),
    ('libWQEXEModelAPI', 'walleq_show'), ('libCWCBEXEModelAPI', 'ComWeChatBotClient'),
    ('libOPQBotEXEModelAPI', 'opqbot_auto'), ('virtualTerminalLinkServerAPI', 'default'),
])
def test_launcher_init_carries_account_snapshot(module, model):
    bot = OlivOS.API.bot_info_T(
        id=10001, platform_sdk='onebot', platform_platform='qq', platform_model=model)
    control = queue.Queue()
    launcher = getattr(OlivOS, module).server('test', control_queue=control, bot_info_dict=bot)
    launcher.send_init_event()
    packet = control.get_nowait()
    assert packet.key['data']['event'] == 'init'
    assert packet.key['data']['account_platform'] == bot.platform
    bot.platform['model'] = 'changed'
    assert packet.key['data']['account_platform']['model'] == model


@pytest.fixture(scope='module')
def account_tk_owner():
    import tkinter

    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        pytest.skip(f'tkinter unavailable on this runner: {error}')
    root.withdraw()
    yield root
    root.destroy()
    gc.collect()


@pytest.fixture
def hidden_root(account_tk_owner, tmp_path, monkeypatch):
    import tkinter

    # 在 Tk 创建线程回收上一个用例留下的引用环，再启动本用例的网络线程。
    gc.collect()
    root = account_tk_owner
    monkeypatch.chdir(tmp_path)
    dialogs = []
    init = tkinter.Toplevel.__init__

    def hidden_init(window, *args, **kwargs):
        init(window, *args, **kwargs)
        window.withdraw()
        if isinstance(window, OlivOS.multiLoginUIAPI.QrBindDialog):
            dialogs.append(window)

    monkeypatch.setattr(tkinter.Toplevel, '__init__', hidden_init)
    monkeypatch.setattr(tkinter.Toplevel, 'mainloop', lambda *_: pytest.fail('子窗口不能启动 mainloop'))
    errors = []
    monkeypatch.setattr(tkinter.Tk, 'report_callback_exception', lambda _self, _type, error, _tb: errors.append(error))
    yield root
    for child in root.winfo_children():
        child.destroy()
    while dialogs:
        worker = dialogs.pop().worker
        worker.join(8)
        assert not worker.is_alive(), '扫码窗口关闭后工作线程未退出'
    gc.collect()
    assert not errors, errors


def _until(root, condition):
    deadline = time.monotonic() + 8
    while not condition():
        assert time.monotonic() < deadline, '未收到预期的 Tk 或 QQ 事件'
        root.update()
        time.sleep(0.01)


@pytest.fixture
def qq_http(monkeypatch):
    # 仅替换 QQ HTTP 边界；渲染、加解密、会话清理和本机控制总线均使用真实实现。
    state = SimpleNamespace(status=2, calls=[], entered=threading.Event(), proceed=threading.Event())
    state.proceed.set()
    key = None

    def post(url, *, json, **_kwargs):
        nonlocal key
        state.calls.append((url, threading.get_ident()))
        if url == 'https://q.qq.com/lite/create_bind_task':
            key = base64.b64decode(json['key'])
            state.entered.set()
            assert state.proceed.wait(5), '建单 HTTP 阻塞了 Tk 线程'
            data = {'task_id': 'offline-native-qr'}
        else:
            assert url == 'https://q.qq.com/lite/poll_bind_result' and json['task_id'] == 'offline-native-qr'
            data = {'status': state.status}
            if state.status == 2:
                nonce = os.urandom(12)
                encrypted = AESGCM(key).encrypt(nonce, b'offline-native-secret', None)
                data.update(bot_appid='10001', bot_encrypt_secret=base64.b64encode(nonce + encrypted).decode('ascii'),
                            user_openid='offline-user')
        return SimpleNamespace(status_code=200, json=lambda: {'retcode': 0, 'data': data})

    monkeypatch.setattr(OlivOS.qqGuildv2QrBindAPI.requests, 'post', post)
    yield state
    state.proceed.set()


def _host(accounts, first_run=False):
    control = queue.Queue()
    host = OlivOS.multiLoginUIAPI.HostUI(
        'test', accounts, rootMode=False, asaycMode=not first_run, callbackData={'res': False}, control_queue=control)
    host.start()
    return host, control


def _form(host, preset):
    form = OlivOS.multiLoginUIAPI.TreeEditUI(
        'create', host.UIData['Account_data'], edit_commit_callback=host.tree_edit_commit, parent=host.UIObject['root'])
    form.start()
    _select(form, 'Account_type', preset)
    return form


def _select(form, field, value):
    name = 'edit_root_Combobox_' + field
    form.UIObject[name].set(value)
    form.tree_edit_UI_Combobox_ComboboxSelected(None, form.action, name)


def _place(widget):
    info = widget.place_info()
    return tuple(int(info[k]) for k in ('x', 'y', 'width', 'height'))


def test_native_split_menu_keeps_generic_create_and_first_run_controls(hidden_root, monkeypatch):
    host, _ = _host({})
    ui = host.UIObject
    assert _place(ui['root_Button_NEW']) == (10, 358, 87, 34)
    assert _place(ui['root_Button_NEW_MENU']) == (98, 358, 29, 34)
    assert ui['root_Button_NEW']['text'] == '新增账号' and ui['root_Button_NEW_MENU']['text'] == '▾'
    menu = ui['root_new_menu']
    assert [menu.entrycget(i, 'label') for i in range(menu.index('end') + 1)] == ['新增账号（通用）', 'QQ 官方扫码创建']
    popup = Mock()
    monkeypatch.setattr(type(menu), 'tk_popup', popup)
    ui['root_Button_NEW_MENU'].invoke()
    popup.assert_called_once()
    host.tree_edit = Mock()
    ui['root_Button_NEW'].invoke()
    menu.invoke(0)
    ui['root_frame_first_root_Button_FIRST_NEW'].invoke()
    assert [call.args for call in host.tree_edit.call_args_list] == [('create',)] * 3
    assert ui['root_frame_first_root'].place_info() and ui['root_frame_first_root_Button_QR_NEW'].place_info()
    ui['root_frame_first_root_Button_FIRST_COMMIT'].invoke()
    assert ui['root_frame_skip_root'].place_info()


@pytest.mark.parametrize('first_run', [True, False])
def test_native_quick_scan_saves_without_extra_clicks(hidden_root, qq_http, monkeypatch, first_run):
    other = OlivOS.API.bot_info_T(id=10001, platform_sdk='terminal_link', platform_platform='terminal',
                                  platform_model='default')
    host, control = _host({} if first_run else {other.hash: other}, first_run=first_run)
    root = host.UIObject['root']
    confirm = Mock(return_value=False)
    monkeypatch.setattr(OlivOS.multiLoginUIAPI.messagebox, 'askyesno', confirm)
    if first_run:
        host.UIObject['root_frame_first_root_Button_QR_NEW'].invoke()
    else:
        host.UIObject['root_new_menu'].invoke(1)
    dialog = root.grab_current()
    assert isinstance(dialog, OlivOS.multiLoginUIAPI.QrBindDialog)
    assert dialog.master is root and str(dialog.transient()) == str(root)
    _until(hidden_root, lambda: dialog.photo is not None)
    assert dialog.image_label['image'] and dialog.photo.width() > 0
    clear, copy = Mock(), Mock()
    monkeypatch.setattr(type(dialog), 'clipboard_clear', clear)
    monkeypatch.setattr(type(dialog), 'clipboard_append', copy)
    dialog.copy_button.invoke()
    clear.assert_called_once_with()
    copy.assert_called_once_with(dialog.qr_url)
    open_url = Mock(return_value=True)
    monkeypatch.setattr(OlivOS.multiLoginUIAPI.webbrowser, 'open', open_url)
    dialog.open_button.invoke()
    open_url.assert_called_once_with(dialog.qr_url)
    _until(hidden_root, lambda: not root.winfo_exists())
    assert not dialog.winfo_exists() and hidden_root.grab_current() is None
    assert host.UIData['flag_commit'] and all(tid != threading.get_ident() for _, tid in qq_http.calls)
    confirm.assert_not_called()
    assert host.callbackData['res'] is True and dialog.manager.poll_session(dialog.bind_id)['status'] == 3
    packets = [control.get_nowait() for _ in range(4)]
    assert [packet.action for packet in packets] == [
        'call_system_event', 'call_account_update', 'call_system_stop_type_event', 'call_system_event']
    accounts = packets[1].key['data']
    assert len(accounts) == (1 if first_run else 2)
    bot = next(bot for bot in accounts.values() if bot.platform['sdk'] == 'qqGuildv2_link')
    assert str(bot.id) == '10001' and bot.enable
    assert bot.platform == {'sdk': 'qqGuildv2_link', 'platform': 'qqGuild', 'model': 'public'}
    assert (bot.post_info.type, bot.post_info.auto) == ('websocket', True)
    assert (bot.post_info.host, bot.post_info.port) == ('', 0)
    assert bot.post_info.access_token == 'offline-native-secret'


@pytest.mark.parametrize('accept', [False, True])
def test_native_quick_scan_requires_approval_for_dirty_drafts(hidden_root, qq_http, monkeypatch, accept):
    bot = OlivOS.API.bot_info_T(id=2, platform_sdk='terminal_link', platform_platform='terminal',
                                platform_model='default')
    host, control = _host({bot.hash: bot})
    switch = host.UIObject['tree_switch_dict'][bot.hash]
    switch['variable'].set(False)
    host.tree_switch_toggle(bot.hash)
    confirm = Mock(return_value=accept)
    monkeypatch.setattr(OlivOS.multiLoginUIAPI.messagebox, 'askyesno', confirm)
    host.UIObject['root_new_menu'].invoke(1)
    assert '一并保存' in confirm.call_args.args[1]
    if accept:
        _until(hidden_root, lambda: host.UIData['flag_commit'])
        control.get_nowait()
        assert not control.get_nowait().key['data'][bot.hash].enable
    else:
        assert not qq_http.calls and control.empty() and hidden_root.grab_current() is None
        assert bot.enable and not host.UIData['Account_data'][bot.hash].enable


@pytest.mark.parametrize('replace', [False, True])
def test_native_duplicate_scan_only_rotates_the_secret(hidden_root, qq_http, monkeypatch, replace):
    existing = OlivOS.API.bot_info_T(id=10001, platform_sdk='qqGuildv2_link', platform_platform='qqGuild',
                                     platform_model='private', server_type='post', port=2083, access_token='old')
    existing.enable = False
    existing.extends = {'keep': True}
    host, control = _host({existing.hash: existing})
    draft = host.UIData['Account_data']
    old = draft[existing.hash]
    prompt_state = []

    def confirm(_title, prompt, parent):
        prompt_state.append((prompt, parent.grab_current(), dialog.winfo_exists()))
        return replace

    monkeypatch.setattr(OlivOS.multiLoginUIAPI.messagebox, 'askyesno', confirm)
    host.UIObject['root_new_menu'].invoke(1)
    dialog = host.UIObject['root'].grab_current()
    _until(hidden_root, lambda: bool(prompt_state))
    prompt, grab, child_exists = prompt_state[0]
    assert '仅更新 AppSecret' in prompt and grab is None and not child_exists
    assert len(draft) == 1 and draft[old.hash] is old
    assert old.post_info.access_token == ('offline-native-secret' if replace else 'old')
    assert (old.platform['model'], old.post_info.type, old.post_info.port) == ('private', 'post', 2083)
    assert old.extends == {'keep': True} and not old.enable and existing.post_info.access_token == 'old'
    assert control.empty() is (not replace)
    assert host.UIObject['root'].winfo_exists() == (not replace)


def test_native_fill_button_follows_selected_preset_and_custom_sdk(hidden_root):
    host, _ = _host({})
    form = _form(host, 'QQ官方/公域/V2')
    ui = form.UIObject
    qr = ui['edit_root_Button_qqguild_qr_bind']
    assert qr['text'] == '扫码填入' and _place(qr) == (310, 100, 70, 24)
    assert _place(ui['edit_root_Entry_Server_access_token'])[1] == _place(qr)[1]
    _select(form, 'Account_type', 'QQ官方/公域/V2/Webhook')
    assert _place(ui['edit_root_Button_Webhook_copy'])[1] >= _place(qr)[1] + 24
    for preset in ('QQ官方/公域/V1', 'QQ/NapCat/默认'):
        _select(form, 'Account_type', preset)
        assert not qr.place_info()
    _select(form, 'Account_type', '自定义')
    _select(form, 'platform', 'qqGuild')
    _select(form, 'sdk', 'qqGuildv2_link')
    assert _place(qr)[1] == _place(ui['edit_root_Entry_Server_access_token'])[1]
    _select(form, 'sdk', 'qqGuild_link')
    assert not qr.place_info()


@pytest.mark.parametrize(('preset', 'port', 'hint'), [
    ('QQ官方/公域/V2', '', None), ('QQ官方/私域/V2/指定intents', '123', None),
    ('QQ官方/公域/V2/Webhook', '', '回调地址'), ('QQ官方/沙盒/V2/指定intents', '', 'Intents'),
])
def test_native_editor_scan_commits_only_complete_ws_drafts(hidden_root, qq_http, preset, port, hint):
    host, control = _host({})
    form = _form(host, preset)
    form.UIData['edit_root_Entry_Server_port_StringVar'].set(port)
    root = form.UIObject['edit_root']
    form.UIObject['edit_root_Button_qqguild_qr_bind'].invoke()
    dialog = root.grab_current()
    assert dialog.master is root
    _until(hidden_root, lambda: not dialog.winfo_exists())
    assert hidden_root.grab_current() is None and control.empty() and not host.UIData['flag_commit']
    assert form.UIData['edit_root_Entry_ID_StringVar'].get() == '10001'
    assert form.UIData['edit_root_Entry_Server_access_token_StringVar'].get() == 'offline-native-secret'
    if hint:
        assert root.winfo_exists() and not host.UIData['Account_data']
        assert hint in form.UIObject['edit_root_qr_hint']['text'] and form.UIObject['edit_root_qr_hint'].place_info()
        if preset.endswith('/Webhook'):
            assert '10001' in form.UIData['edit_root_Entry_Webhook_callback_StringVar'].get()
            app_id = form.UIData['edit_root_Entry_ID_StringVar']
            assert app_id.trace_info()
            root.destroy()
            assert not app_id.trace_info()
    else:
        assert not root.winfo_exists() and host.UIData['account_dirty']
        bot, = host.UIData['Account_data'].values()
        assert str(bot.id) == '10001' and bot.post_info.port == int(port or 0)
        assert bot.post_info.access_token == 'offline-native-secret'
        assert len(host.UIObject['tree'].get_children()) == 1


def test_native_edit_existing_account_replaces_only_its_draft(hidden_root, qq_http):
    import tkinter

    previous = OlivOS.API.bot_info_T(
        id=20002, platform_sdk='qqGuildv2_link', platform_platform='qqGuild', platform_model='private',
        server_type='websocket', server_auto=True, port=0, access_token='previous')
    previous.enable = False
    host, control = _host({previous.hash: previous})
    root, tree = host.UIObject['root'], host.UIObject['tree']
    tree.focus(tree.get_children()[0])
    host.UIObject['root_Button_EDIT'].invoke()
    editor, = (child for child in root.winfo_children() if isinstance(child, tkinter.Toplevel))
    button, = (child for child in editor.winfo_children() if isinstance(child, tkinter.Button)
               and child['text'] == '扫码填入')
    button.invoke()
    _until(hidden_root, lambda: not editor.winfo_exists())
    updated, = host.UIData['Account_data'].values()
    assert updated.id == 10001 and updated.platform['model'] == 'private' and not updated.enable
    assert previous.id == 20002 and previous.post_info.access_token == 'previous'
    assert updated.post_info.access_token == 'offline-native-secret' and control.empty()


@pytest.mark.parametrize('close', ['window', 'parent'])
def test_native_dialog_close_cancels_after_and_local_session(hidden_root, qq_http, close):
    import tkinter

    parent = tkinter.Toplevel(hidden_root)
    callback = Mock()
    dialog = OlivOS.multiLoginUIAPI.QrBindDialog(parent, callback)
    _until(hidden_root, lambda: dialog.bind_id is not None)
    timer = dialog.after_id
    if close == 'window':
        dialog.tk.call(dialog.protocol('WM_DELETE_WINDOW'))
    else:
        parent.destroy()
    assert hidden_root.grab_current() is None and not dialog.winfo_exists() and dialog.stopped.is_set()
    assert timer not in hidden_root.tk.call('after', 'info')
    assert dialog.manager.poll_session(dialog.bind_id)['status'] == 3
    callback.assert_not_called()


def test_native_cancel_before_qq_returns_does_not_block_or_open_a_late_dialog(hidden_root, qq_http):
    qq_http.proceed.clear()
    callback = Mock()
    dialog = OlivOS.multiLoginUIAPI.QrBindDialog(hidden_root, callback)
    _until(hidden_root, qq_http.entered.is_set)
    dialog.destroy()
    qq_http.proceed.set()
    assert not dialog.winfo_exists() and dialog.after_id is None and hidden_root.grab_current() is None
    dialog.worker.join(2)
    assert not dialog.worker.is_alive() and len(qq_http.calls) == 1
    callback.assert_not_called()


def test_native_expired_qr_stops_polling_and_disables_stale_links(hidden_root, qq_http):
    qq_http.status = 3
    callback = Mock()
    dialog = OlivOS.multiLoginUIAPI.QrBindDialog(hidden_root, callback)
    _until(hidden_root, lambda: '过期' in dialog.status_label['text'])
    assert dialog.after_id is None and dialog.photo is None
    assert dialog.copy_button.instate(['disabled']) and dialog.open_button.instate(['disabled'])
    callback.assert_not_called()
