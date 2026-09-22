"""Native terminal regressions using a real hidden Tk widget and injected failures."""

import logging.handlers
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytestmark = [pytest.mark.native_gui, pytest.mark.skipif(os.name != 'nt', reason='Windows native terminal')]


@pytest.fixture(scope='module')
def tk_root():
    import tkinter

    root = tkinter.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def terminal(monkeypatch, tk_root):
    import tkinter
    from tkinter import ttk

    from OlivOS.nativeGUI import nativeWinUIAPI

    root = tk_root
    owner = SimpleNamespace(UIObject={'root_OlivOS_terminal_data': []})
    value = nativeWinUIAPI.OlivOSTerminalUI('test', root=owner, logger_proc=Mock())
    value.UIObject['tree'] = ttk.Treeview(root, columns=('DATA',), show='headings')
    value.UIData.update(level_find={'INFO': 2}, root_level_StringVar=tkinter.StringVar(root, value='INFO'),
                        flag_tree_is_bottom=True)
    monkeypatch.setattr(nativeWinUIAPI.time, 'monotonic', lambda: 100)
    logger = logging.getLogger('OlivOS.nativeWinUI.terminal_display')
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    try:
        yield value
        value.logger_proc.assert_not_called()  # 诊断不回流到主日志队列。
    finally:
        value.UIObject['tree'].destroy()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()


def packet(text, level=2):
    return {'data': {'log_level': level, 'log_time': 1750000000}, 'str': text}


def rows(terminal):
    tree = terminal.UIObject['tree']
    return [tree.item(item)['text'] for item in tree.get_children()]


def test_invalid_history_row_does_not_discard_later_logs(terminal):
    terminal.root.UIObject['root_OlivOS_terminal_data'] = [packet('before'), {}, packet('after')]
    terminal._tree_init_line()
    assert rows(terminal) == ['before', 'after']


@pytest.mark.parametrize('text', ['emoji \U0001f98a', 'bad\ud800', 'nul\x00end', 'x' * 100000, 123, None],
                         ids=['emoji', 'surrogate', 'nul', 'long', 'number', 'none'])
def test_special_log_text_does_not_prevent_next_row(terminal, text):
    terminal.tree_add_line(packet(text))
    terminal.tree_add_line(packet('normal'))
    assert len(rows(terminal)) == 2 and rows(terminal)[-1] == 'normal'


@pytest.mark.parametrize('method,stage', [('insert', 'insert'), ('get_children', 'trim'), ('see', 'scroll')])
def test_widget_failure_is_recorded_and_following_rows_recover(terminal, tmp_path, monkeypatch, method, stage):
    import tkinter

    tree = terminal.UIObject['tree']
    with monkeypatch.context() as patch:
        patch.setattr(tree, method, Mock(side_effect=tkinter.TclError('PRIVATE_FIXTURE_MESSAGE')))
        terminal.tree_add_line(packet('PRIVATE_FIXTURE_MESSAGE'))
    terminal.tree_add_line(packet('recovered'))
    assert rows(terminal)[-1] == 'recovered'
    text = (tmp_path / 'logfile/OlivOS_native_terminal_error.log').read_text(encoding='utf-8')
    assert f'stage={stage}' in text and 'error=TclError' in text and 'tree_add_line' in text
    assert 'PRIVATE_FIXTURE_MESSAGE' not in text


def test_display_errors_are_rate_limited(terminal, tmp_path, monkeypatch):
    from OlivOS.nativeGUI import nativeWinUIAPI

    terminal.tree_add_line(None)
    for _ in range(100):
        terminal.tree_add_line(None)
    path = tmp_path / 'logfile/OlivOS_native_terminal_error.log'
    assert path.read_text(encoding='utf-8').count('stage=format') == 1
    monkeypatch.setattr(nativeWinUIAPI.time, 'monotonic', lambda: 130)
    terminal.tree_add_line(None)
    assert 'suppressed=100' in path.read_text(encoding='utf-8')


def test_unwritable_diagnostics_do_not_break_log_processing(terminal, monkeypatch):
    monkeypatch.setattr(logging.handlers, 'RotatingFileHandler', Mock(side_effect=PermissionError('fixture')))
    terminal.tree_add_line(None)
    terminal.tree_add_line(packet('normal'))
    assert rows(terminal) == ['normal']


def test_diagnostic_file_rotates_to_one_backup(terminal, tmp_path, monkeypatch):
    from OlivOS.nativeGUI import nativeWinUIAPI

    terminal.tree_add_line(None)
    handler = next(handler for handler in logging.getLogger('OlivOS.nativeWinUI.terminal_display').handlers
                   if isinstance(handler, logging.handlers.RotatingFileHandler))
    assert handler.maxBytes == 1024 * 1024 and handler.backupCount == 1
    handler.maxBytes = 700
    for index in range(5):
        monkeypatch.setattr(nativeWinUIAPI.time, 'monotonic', lambda i=index: 130 + 30 * i)
        terminal.tree_add_line(None)
    assert sorted(path.name for path in (tmp_path / 'logfile').iterdir()) == [
        'OlivOS_native_terminal_error.log', 'OlivOS_native_terminal_error.log.1']


def test_terminal_history_is_bounded_and_keeps_latest_row(terminal):
    for index in range(5000):
        terminal.tree_add_line(packet(str(index)))
    assert len(rows(terminal)) <= 128 and rows(terminal)[-1] == '4999'
