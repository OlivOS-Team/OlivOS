"""Native terminal regressions using a real hidden Tk widget and injected failures."""

import logging.handlers
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS

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


def test_log_format_switch_rerenders_history_without_mutating_packets(terminal, tmp_path, tk_root):
    import tkinter

    terminal.root.webui_root = str(tmp_path)
    terminal.root.UIObject['root_OlivOS_terminal_data'] = [packet('User: [OP:at,id=42][OP:poke,id=123456]')]
    terminal.UIData['root_log_format_StringVar'] = tkinter.StringVar(tk_root, value='CQ')
    terminal._tree_init_line()
    terminal._on_log_format_change()

    assert rows(terminal) == ['User: [CQ:at,qq=42][CQ:poke,qq=123456]']
    assert terminal.root.UIObject['root_OlivOS_terminal_data'][0]['str'] == 'User: [OP:at,id=42][OP:poke,id=123456]'
    assert OlivOS.diagnoseAPI.load_log_display_mode(tmp_path) == 'cq'

    terminal.UIData['root_log_format_StringVar'].set('OP')
    terminal._on_log_format_change()
    assert rows(terminal) == ['User: [OP:at,id=42][OP:poke,id=123456]']


def test_terminal_refreshes_display_setting_changed_by_webui(terminal, tmp_path, tk_root):
    import tkinter

    terminal.root.webui_root = str(tmp_path)
    terminal.UIObject['root'] = tkinter.Toplevel(tk_root)
    terminal.UIObject['root'].withdraw()
    terminal.UIData['root_log_format_StringVar'] = tkinter.StringVar(tk_root, value='OP')
    terminal.root.UIObject['root_OlivOS_terminal_data'] = [packet('User: [OP:at,id=42]')]
    try:
        OlivOS.diagnoseAPI.save_log_display_mode('cq', tmp_path)
        terminal._sync_log_format()
        assert terminal.UIData['root_log_format_StringVar'].get() == 'CQ'
        assert rows(terminal) == ['User: [CQ:at,qq=42]']
    finally:
        terminal.UIObject['root'].destroy()


def test_log_format_control_is_visible_in_main_terminal(tk_root):
    from OlivOS.nativeGUI import nativeWinUIAPI

    owner = SimpleNamespace(UIObject={'root_OlivOS_terminal_data': []})
    terminal = nativeWinUIAPI.OlivOSTerminalUI('test', root=owner, logger_proc=Mock())
    terminal._build_main_window()
    terminal.UIObject['root'].withdraw()
    try:
        terminal._build_tree()
        terminal._build_scrollbar()
        terminal._build_input_area()
        terminal._build_extra_controls()
        assert terminal.UIObject['root_log_format_frame'].winfo_manager() == 'grid'
        assert str(terminal.UIObject['root_log_format'].cget('state')) == 'readonly'
        assert terminal.UIData['root_log_format_StringVar'].get() in ('OP', 'CQ')
        assert terminal.UIObject['root_log_format']['values'] == ('OP', 'CQ')
        assert terminal.UIObject['root_level'].cget('width') == 6
        assert max(map(len, terminal.UIData['level_list'])) == 5
        assert terminal.UIObject['root'].grid_columnconfigure(1, 'weight') == 0
        terminal.UIObject['root'].attributes('-alpha', 0)
        terminal.UIObject['root'].deiconify()
        terminal.UIObject['root'].update()
        entry = terminal.UIObject['root_input']
        assert entry.winfo_width() > terminal.UIObject['root'].winfo_width() / 2
        entry_width = entry.winfo_width()
        window_width = terminal.UIObject['root'].winfo_width()
        terminal.UIObject['root'].geometry(f'{window_width + 200}x600')
        terminal.UIObject['root'].update()
        window_growth = terminal.UIObject['root'].winfo_width() - window_width
        assert window_growth > 0
        assert abs((entry.winfo_width() - entry_width) - window_growth) <= 2
    finally:
        terminal.UIObject['root'].destroy()
