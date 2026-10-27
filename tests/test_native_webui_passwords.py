"""Tray password dialogs use the Tk dispatch queue and the real local credential store."""

import gc
import os
import queue
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.webUI import authAPI

# 本文件的用例都要真实 Tk 窗口和托盘，其他平台既无桌面也无 pystray。
pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows tray')


@pytest.fixture
def dock(tmp_path):
    instance = OlivOS.nativeWinUIAPI.dock(rx_queue=queue.Queue(), root_path=tmp_path)
    instance.UIObject['main_tk'] = Mock()
    return instance


@pytest.mark.skipif(os.name != 'nt', reason='Windows tray')
def test_cancelled_tray_password_preserves_credentials(dock, tmp_path, monkeypatch):
    config = {'auth_path': './conf/webui_auth.json'}
    initial = authAPI.password_record('original-fixture-password')
    authAPI.reset_offline(tmp_path, config, initial)
    monkeypatch.setattr(dock, 'askWebUIPassword', lambda: None)
    dock.showWebUIPasswordReset()
    assert authAPI.read_record(tmp_path / 'conf/webui_auth.json') == initial
    assert dock.UIData['webui_password_reset_active'] is False


@pytest.mark.skipif(os.name != 'nt', reason='Windows tray')
def test_tray_password_reset_saves_without_original_password(dock, tmp_path, monkeypatch):
    # localAPI.request() 在子线程里才 import 命名管道要用的 pywin32 模块；CI 的
    # windows-latest 上「子线程首次 import + GC」会直接把解释器打死
    # （Windows fatal exception: code 0x80000003），整个 pytest 进程退出。
    # 这里在主线程先把它们导进来，子线程里就只是一次 sys.modules 命中。
    import pywintypes  # noqa: F401
    import win32con  # noqa: F401
    import win32file  # noqa: F401
    import win32pipe  # noqa: F401

    monkeypatch.setattr(dock, 'askWebUIPassword',
                        lambda: ('tray-fixture-password', 'tray-fixture-password'))
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

    try:
        root = tkinter.Tk()
    except tkinter.TclError as error:
        # hostedtoolcache 的 Windows runner 偶发 Tcl 自身损坏（init.tcl 读不出），
        # 属于环境问题而非代码问题；跳过本模块需要真实 Tk 窗口的用例。
        pytest.skip(f'tkinter unavailable on this runner: {error}')
        raise AssertionError('pytest.skip should raise')  # pragma: no cover
    root.withdraw()
    yield root
    root.destroy()


@pytest.mark.native_gui
@pytest.mark.parametrize('copy_fails', [False, True])
def test_password_dialog_has_click_to_copy_and_selectable_password(
        monkeypatch, capsys, copy_fails, password_dialog_owner):
    import tkinter

    # 使用真实隐藏窗口和按钮；剪贴板接口用替身，避免测试覆盖用户剪贴板。
    window = tkinter.Toplevel(password_dialog_owner)
    window.withdraw()
    monkeypatch.setattr(tkinter, 'Tk', lambda: window)
    clear = Mock()
    append = Mock(side_effect=tkinter.TclError('fixture') if copy_fails else None)
    monkeypatch.setattr(window, 'clipboard_clear', clear)
    monkeypatch.setattr(window, 'clipboard_append', append)
    ready = Mock()

    def check_window():
        ready.assert_called_once_with()

        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)

        widgets = list(descendants(window))
        entry = next(widget for widget in widgets if isinstance(widget, tkinter.Entry))
        assert entry.get() == 'copy-fixture-password' and str(entry['state']) == 'readonly'
        button = next(widget for widget in widgets
                      if isinstance(widget, tkinter.Button) and widget['text'] == '复制密码')
        button.invoke()
        clear.assert_called_once_with()
        append.assert_called_once_with('copy-fixture-password')
        labels = [window.getvar(widget['textvariable']) for widget in widgets
                  if isinstance(widget, tkinter.Label) and widget['textvariable']]
        assert any(('复制失败' if copy_fails else '密码已复制') in text for text in labels)
        window.destroy()
        # Tk 控件环在主线程回收，避免别的线程 GC 时触碰这些对象。
        gc.collect()

    monkeypatch.setattr(window, 'mainloop', check_window)
    assert authAPI.show_password_dialog('copy-fixture-password', migrated=True, on_ready=ready) is True
    output = capsys.readouterr()
    assert output.out == output.err == ''


@pytest.mark.native_gui
def test_real_password_window_runs_in_its_own_thread_while_webui_serves(tmp_path):
    import subprocess
    import sys
    import textwrap

    # 独立进程只打开隐藏测试窗口，避免多个 Tk 解释器互相干扰。
    script = textwrap.dedent('''
        import threading
        import time
        import tkinter
        from pathlib import Path
        from OlivOS.webUI import authAPI, serverAPI

        legacy = Path('conf/webui_token.txt')
        legacy.parent.mkdir()
        legacy.write_text('threaded-window-fixture', encoding='utf-8')
        authAPI.windows_desktop_available = lambda: True
        original_tk = tkinter.Tk
        original_dialog = authAPI.show_password_dialog
        services = []
        observed = threading.Event()
        closed = threading.Event()
        failures = []
        window_threads = []

        def hidden_window():
            window_threads.append(threading.current_thread().name)
            window = original_tk()
            window.withdraw()
            deadline = time.monotonic() + 5

            def verify_progress():
                try:
                    if services and services[0].ready.is_set():
                        host = services[0]
                        assert host.error is None
                        assert host.app.test_client().get('/api/health').status_code == 200
                        assert not legacy.exists()
                        observed.set()
                        window.destroy()
                    elif time.monotonic() < deadline:
                        window.after(50, verify_progress)
                    else:
                        failures.append('startup blocked')
                        window.destroy()
                except Exception as error:
                    failures.append(type(error).__name__)
                    window.destroy()

            window.after(50, verify_progress)
            return window

        def tracked_dialog(*args, **kwargs):
            try:
                return original_dialog(*args, **kwargs)
            finally:
                closed.set()

        tkinter.Tk = hidden_window
        authAPI.show_password_dialog = tracked_dialog
        worker = None
        try:
            host = serverAPI.server(root_path=Path.cwd(), server_conf={'port': 0, 'host': '127.0.0.1'})
            services.append(host)
            worker = threading.Thread(target=host.run, daemon=True)
            worker.start()
            assert observed.wait(7), failures
            assert closed.wait(3)
            assert window_threads == ['WebUI-password-display']
            assert not failures
        finally:
            for service in services:
                service.on_terminate()
            if worker:
                worker.join(timeout=5)
                assert not worker.is_alive()
            for thread in threading.enumerate():
                if thread.name == 'WebUI-password-display':
                    thread.join(timeout=3)
                    assert not thread.is_alive()
    ''')
    result = subprocess.run([sys.executable, '-c', script], cwd=tmp_path, capture_output=True,
                            text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert 'threaded-window-fixture' not in result.stdout + result.stderr
