# -*- coding: utf-8 -*-
"""自动重载调度：定时点、滚动周期、冲突仲裁与总闸语义。"""

import queue
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS


class _LeaveLoop(Exception):
    """伪时钟退出 run() 主循环用。"""


class FakeClock:
    """同时冒充墙钟与单调时钟；sleep 第 2 次调用时跳出主循环。"""

    def __init__(self, wall='2026-10-26 04:30:00', mono=1000.0):
        self.wall = wall
        self.mono = mono
        self.sleep_calls = 0

    def strftime(self, fmt, *_args):
        return datetime.strptime(self.wall, '%Y-%m-%d %H:%M:%S').strftime(fmt)

    def monotonic(self):
        return self.mono

    def time(self):
        return 0.0

    def sleep(self, _seconds):
        self.sleep_calls += 1
        if self.sleep_calls >= 2:
            raise _LeaveLoop()


@pytest.fixture(autouse=True)
def _restore_global_proc():
    """run() 会把 gProc 指向本用例的加载器，跑完必须还原。

    否则后续用例（qqGuildv2 等）会走 gProc.log，落在这个 Mock 上。
    """
    original = getattr(OlivOS.pluginAPI, 'gProc', None)
    yield
    OlivOS.pluginAPI.gProc = original


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(OlivOS.pluginAPI, 'time', fake)
    return fake


def make_loader(clock, **kwargs):
    kwargs.setdefault('enable_gui', False)      # 不开 tkinter 线程，否则 run() 后进程不退出
    loader = OlivOS.pluginAPI.shallow(
        control_queue=queue.Queue(), rx_queue=queue.Queue(), bot_info_dict={}, **kwargs)
    loader.log = Mock()
    loader.set_restart = Mock()
    now = datetime.strptime(clock.wall, '%Y-%m-%d %H:%M:%S')
    loader.Proc_data['restart_at_last'] = (now - timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M')
    loader.Proc_data['restart_interval_base'] = clock.monotonic()
    return loader


# ---------------------------------------------------------------- 解析函数

def test_parse_restart_at_accepts_valid_slots():
    assert OlivOS.pluginAPI.parse_restart_at(['04:30', '4:05', '23:59']) == {'04:30', '04:05', '23:59'}


def test_parse_restart_at_drops_invalid_entries():
    value = ['4:3', '25:00', 'abc', '', '04:5', 123, None, True, ['x'], '04:30']
    assert OlivOS.pluginAPI.parse_restart_at(value) == {'04:30'}


def test_parse_restart_at_non_list_is_disabled():
    assert OlivOS.pluginAPI.parse_restart_at(None) == set()
    assert OlivOS.pluginAPI.parse_restart_at('04:30') == set()


def test_parse_restart_interval_units_and_boundaries():
    assert OlivOS.pluginAPI.parse_restart_interval(6) == 360          # 6 分钟
    assert OlivOS.pluginAPI.parse_restart_interval(90) == 5400        # 1.5 小时
    assert OlivOS.pluginAPI.parse_restart_interval(0) == 0
    assert OlivOS.pluginAPI.parse_restart_interval(-3) == 0
    assert OlivOS.pluginAPI.parse_restart_interval('6') == 0
    assert OlivOS.pluginAPI.parse_restart_interval(True) == 0
    assert OlivOS.pluginAPI.parse_restart_interval(5.9) == 0          # 下限 6 分钟
    assert OlivOS.pluginAPI.parse_restart_interval(6.5) == 390


# ---------------------------------------------------------------- 定时点

def test_restart_at_hits_once(clock):
    loader = make_loader(clock, restart_at=['04:30'], enable_auto_restart=True)
    assert loader._check_restart_schedule() is True
    loader.set_restart.assert_called_once()


def test_restart_at_same_minute_not_repeated(clock):
    loader = make_loader(clock, restart_at=['04:30'], enable_auto_restart=True)
    for _ in range(3):
        loader._check_restart_schedule()
    loader.set_restart.assert_called_once()


def test_restart_at_other_minute_does_not_fire(clock):
    clock.wall = '2026-10-26 04:31:00'
    loader = make_loader(clock, restart_at=['04:30'], enable_auto_restart=True)
    assert loader._check_restart_schedule() is False
    loader.set_restart.assert_not_called()


def test_restart_at_empty_is_disabled(clock):
    for value in ([], None):
        loader = make_loader(clock, restart_at=value, enable_auto_restart=True)
        assert loader._check_restart_schedule() is False
        loader.set_restart.assert_not_called()


def test_restart_at_ignored_when_master_switch_off(clock):
    loader = make_loader(clock, restart_at=['04:30'], enable_auto_restart=False)
    assert loader._check_restart_schedule() is False
    loader.set_restart.assert_not_called()


def test_restart_at_skipped_while_restarting(clock):
    loader = make_loader(clock, restart_at=['04:30'], enable_auto_restart=True)
    loader.Proc_config['ready_for_restart'] = True
    assert loader._check_restart_schedule() is False
    loader.set_restart.assert_not_called()


def test_restart_at_multiple_slots_each_fire_once(clock):
    loader = make_loader(clock, restart_at=['04:30', '16:30'], enable_auto_restart=True)
    assert loader._check_restart_schedule() is True
    clock.wall = '2026-10-26 16:30:00'
    assert loader._check_restart_schedule() is True
    assert loader.set_restart.call_count == 2


def test_restart_at_started_within_same_minute_does_not_refire(clock):
    """新进程在 04:30 这一分钟内起来时不补触发（run() 用启动时刻初始化 last）。"""
    clock.wall = '2026-10-26 04:30:20'
    loader = make_loader(clock, restart_at=['04:30'], enable_auto_restart=True)
    loader.Proc_data['restart_at_last'] = clock.strftime('%Y-%m-%d %H:%M')
    assert loader._check_restart_schedule() is False
    loader.set_restart.assert_not_called()


# ---------------------------------------------------------------- 滚动周期

def test_interval_not_reached(clock):
    loader = make_loader(clock, restart_interval_minutes=360, enable_auto_restart=True)
    clock.mono += 360 * 60 - 60
    assert loader._check_restart_schedule() is False
    loader.set_restart.assert_not_called()


def test_interval_reached(clock):
    loader = make_loader(clock, restart_interval_minutes=360, enable_auto_restart=True)
    clock.mono += 360 * 60
    assert loader._check_restart_schedule() is True
    loader.set_restart.assert_called_once()


def test_interval_late_still_fires_once(clock):
    loader = make_loader(clock, restart_interval_minutes=360, enable_auto_restart=True)
    clock.mono += 420 * 60
    assert loader._check_restart_schedule() is True
    loader.set_restart.assert_called_once()


def test_interval_disabled_values(clock):
    for value in (0, -1, '6', True, 5.9):
        loader = make_loader(clock, restart_interval_minutes=value, enable_auto_restart=True)
        clock.mono += 30 * 60
        assert loader._check_restart_schedule() is False
        loader.set_restart.assert_not_called()


def test_interval_skipped_while_restarting(clock):
    loader = make_loader(clock, restart_interval_minutes=360, enable_auto_restart=True)
    loader.Proc_config['ready_for_restart'] = True
    clock.mono += 600 * 60
    assert loader._check_restart_schedule() is False
    loader.set_restart.assert_not_called()


# ---------------------------------------------------------------- 冲突仲裁

def test_scheduled_time_wins_over_interval(clock):
    loader = make_loader(
        clock, restart_at=['04:30'], restart_interval_minutes=360, enable_auto_restart=True)
    clock.mono += 600 * 60          # 周期也已到点
    assert loader._check_restart_schedule() is True
    loader.set_restart.assert_called_once()
    assert '计划时间' in loader.log.call_args[0][1] or 'scheduled time' in loader.log.call_args[0][1]


def test_gate_and_schedule_never_double_fire(clock, monkeypatch):
    """门与定时点同一 tick 命中时只触发一次（否则会往队列塞两个 restart_do）。"""
    loader = make_loader(clock, restart_at=['04:30'], restart_gate=1, enable_auto_restart=True)
    loader.set_restart = Mock()
    loader.run_plugin = Mock()
    loader.run_plugin_func = Mock()
    monkeypatch.setattr(OlivOS.pluginAPI, 'releaseDir', lambda *a, **k: None)
    monkeypatch.setattr(
        OlivOS.userModule.UserConfDB, 'DataBaseAPI', lambda *a, **k: SimpleNamespace(stop=lambda: None))
    loader.sendPluginList = Mock()
    loader.load_plugin_list = Mock()
    loader.check_plugin_list = Mock()

    loader.Proc_info.rx_queue.put(
        OlivOS.pluginAPI.API.Control.packet('send', {'data': {'webui': {'session': 's'}}}))

    with pytest.raises(_LeaveLoop):
        loader.run()

    loader.set_restart.assert_called_once()


# ---------------------------------------------------------------- 总闸与守卫修复

def test_restart_do_works_when_master_switch_off(clock, monkeypatch):
    """总闸关掉时，WebUI/托盘的手动重载仍要可用（上游 2021 年的守卫 bug）。"""
    loader = make_loader(clock, enable_auto_restart=False)
    calls = []
    loader.run_plugin_func = lambda target, name: calls.append(name)
    loader.run_plugin = Mock()
    monkeypatch.setattr(OlivOS.pluginAPI, 'releaseDir', lambda *a, **k: None)
    monkeypatch.setattr(
        OlivOS.userModule.UserConfDB, 'DataBaseAPI', lambda *a, **k: SimpleNamespace(stop=lambda: None))
    loader.sendPluginList = Mock()
    loader.load_plugin_list = Mock()
    loader.check_plugin_list = Mock()

    loader.Proc_info.rx_queue.put(
        OlivOS.pluginAPI.API.Control.packet('restart_do', loader.Proc_name))

    with pytest.raises(_LeaveLoop):
        loader.run()

    assert 'save' in calls
    forwarded = []
    while not loader.Proc_info.control_queue.empty():
        forwarded.append(loader.Proc_info.control_queue.get().action)
    assert 'restart_do' in forwarded


def test_gate_silent_when_master_switch_off(clock, monkeypatch):
    """总闸关掉时，事件门不再累计、不再触发。"""
    loader = make_loader(clock, restart_gate=1, enable_auto_restart=False)
    loader.run_plugin = Mock()
    loader.run_plugin_func = Mock()
    monkeypatch.setattr(OlivOS.pluginAPI, 'releaseDir', lambda *a, **k: None)
    monkeypatch.setattr(
        OlivOS.userModule.UserConfDB, 'DataBaseAPI', lambda *a, **k: SimpleNamespace(stop=lambda: None))
    loader.sendPluginList = Mock()
    loader.load_plugin_list = Mock()
    loader.check_plugin_list = Mock()

    loader.Proc_info.rx_queue.put(
        OlivOS.pluginAPI.API.Control.packet('send', {'data': {'webui': {'session': 's'}}}))

    with pytest.raises(_LeaveLoop):
        loader.run()

    loader.set_restart.assert_not_called()
