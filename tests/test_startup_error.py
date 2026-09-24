"""Exercise the entry point without starting any real bot processes."""

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('log_writable', [True, False])
def test_windowed_startup_failure_is_visible(tmp_path, monkeypatch, log_writable):
    entry = Path(__file__).resolve().parents[1] / 'main.py'
    dialogs = []

    def fail_start():
        raise ValueError('test startup configuration error')

    monkeypatch.setitem(sys.modules, 'OlivOS', SimpleNamespace(
        bootAPI=SimpleNamespace(Entity=lambda **kwargs: SimpleNamespace(start=fail_start))))
    monkeypatch.setitem(sys.modules, 'ctypes', SimpleNamespace(windll=SimpleNamespace(
        user32=SimpleNamespace(MessageBoxW=lambda *args: dialogs.append(args)))))
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'stderr', None)
    if not log_writable:
        (tmp_path / 'logfile').write_text('occupied', encoding='utf-8')
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(entry), run_name='__main__')
    assert result.value.code == 1
    assert len(dialogs) == 1
    assert 'ValueError: test startup configuration error' in dialogs[0][1]
    if log_writable:
        logs = list((tmp_path / 'logfile').glob('startup-error-*.log'))
        assert len(logs) == 1
        assert 'Traceback' in logs[0].read_text(encoding='utf-8')
        assert str(logs[0]) in dialogs[0][1]
    else:
        assert '错误日志保存失败' in dialogs[0][1]
