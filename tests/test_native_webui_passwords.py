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
