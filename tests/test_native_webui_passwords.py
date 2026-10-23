"""Tray password dialogs use the Tk dispatch queue and the real local credential store."""

import os
import queue
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.webUI import authAPI

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows tray')


@pytest.fixture
def dock(tmp_path):
    instance = OlivOS.nativeWinUIAPI.dock(rx_queue=queue.Queue(), root_path=tmp_path)
    instance.UIObject['main_tk'] = Mock()
    return instance


@pytest.mark.parametrize('answers', [[None], ['fixture', None], ['fixture', 'different'], ['', '']])
def test_cancelled_or_invalid_tray_password_preserves_credentials(dock, tmp_path, monkeypatch, answers):
    config = {'auth_path': './conf/webui_auth.json'}
    initial = authAPI.password_record('original-fixture-password')
    authAPI.reset_offline(tmp_path, config, initial)
    values = iter(answers)
    dialog = Mock(side_effect=lambda *args, **kwargs: next(values))
    monkeypatch.setattr(OlivOS.nativeWinUIAPI.tkinter.simpledialog, 'askstring', dialog)
    monkeypatch.setattr(OlivOS.nativeWinUIAPI.tkinter.messagebox, 'showerror', Mock())
    dock.showWebUIPasswordReset()
    assert authAPI.read_record(tmp_path / 'conf/webui_auth.json') == initial
    assert dock.UIData['webui_password_reset_active'] is False
    assert all(call.kwargs['show'] == '*' for call in dialog.call_args_list)


def test_tray_password_reset_saves_without_original_password(dock, tmp_path, monkeypatch):
    monkeypatch.setattr(OlivOS.nativeWinUIAPI.tkinter.simpledialog, 'askstring',
                        lambda *args, **kwargs: 'tray-fixture-password')
    success = Mock()
    monkeypatch.setattr(OlivOS.nativeWinUIAPI.tkinter.messagebox, 'showinfo', success)
    dock.changeWebUIPassword()
    dock.mainrun()
    result = dock.Proc_info.rx_queue.get(timeout=5)
    assert result.key['data']['action'] == 'webui_local_result' and not result.key['data'].get('error')
    dock.Proc_info.rx_queue.put(result)
    dock.mainrun()
    assert success.called and dock.UIData['webui_password_reset_active'] is False
    assert authAPI.verify('tray-fixture-password', authAPI.read_record(tmp_path / 'conf/webui_auth.json'))


@pytest.fixture(scope='module')
def password_dialog_owner():
    import tkinter

    root = tkinter.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.mark.native_gui
@pytest.mark.parametrize('copy_fails', [False, True])
def test_password_dialog_has_click_to_copy_and_selectable_password(
        monkeypatch, capsys, copy_fails, password_dialog_owner):
    import tkinter
    from tkinter import ttk

    # 使用真实隐藏窗口和按钮；剪贴板接口用替身，避免测试覆盖用户剪贴板。
    window = tkinter.Toplevel(password_dialog_owner)
    window.withdraw()
    monkeypatch.setattr(tkinter, 'Tk', lambda: window)
    clear = Mock()
    append = Mock(side_effect=tkinter.TclError('fixture') if copy_fails else None)
    monkeypatch.setattr(window, 'clipboard_clear', clear)
    monkeypatch.setattr(window, 'clipboard_append', append)

    def check_window():
        panel = window.winfo_children()[0]
        widgets = panel.winfo_children()
        entry = next(widget for widget in widgets if isinstance(widget, ttk.Entry))
        assert entry.get() == 'copy-fixture-password' and str(entry['state']) == 'readonly'
        button = next(widget for widget in widgets if isinstance(widget, ttk.Button) and widget['text'] == '复制密码')
        button.invoke()
        clear.assert_called_once_with()
        append.assert_called_once_with('copy-fixture-password')
        labels = [window.getvar(widget['textvariable']) for widget in widgets
                  if isinstance(widget, ttk.Label) and widget['textvariable']]
        assert any(('复制失败' if copy_fails else '密码已复制') in text for text in labels)
        window.destroy()

    monkeypatch.setattr(window, 'mainloop', check_window)
    assert authAPI.show_password_dialog('copy-fixture-password', migrated=True) is True
    output = capsys.readouterr()
    assert output.out == output.err == ''
