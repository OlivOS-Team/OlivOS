# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_frontend_coverage.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   WebUI 前端覆盖率采集辅助函数的单元测试。
'''

import gzip
import json

from frontend_coverage_support import (
    filter_coverage_scripts,
    prepare_frontend_coverage,
    reset_raw_coverage,
    write_coverage_payload,
)
from webui_test_support import ChromeSession


class FakeSwitchTo:
    def __init__(self):
        self.selected = None

    def window(self, handle):
        self.selected = handle


class FakeDriver:
    def __init__(self, coverage_result=None):
        self.coverage_result = coverage_result or {'result': []}
        self.commands = []
        self._window_handles = ['main']
        self.switch_to = FakeSwitchTo()

    @property
    def window_handles(self):
        return self._window_handles

    def execute_cdp_cmd(self, command, params):
        self.commands.append((command, params))
        if command == 'Profiler.takePreciseCoverage':
            return self.coverage_result
        return {}


class FailingDriver(FakeDriver):
    """模拟 Profiler 启动失败的浏览器驱动。"""

    def execute_cdp_cmd(self, command, params):
        if command == 'Profiler.enable':
            raise RuntimeError('profiler unavailable')
        return super().execute_cdp_cmd(command, params)


def test_filter_coverage_scripts_keeps_only_webui_scripts():
    # 只保留 app.js 与 theme.js，排除插件、Service Worker 和第三方脚本。
    result = [
        {'url': 'http://127.0.0.1:2048/static/app.js', 'functions': [{'functionName': 'a'}]},
        {'url': 'http://127.0.0.1:2048/static/theme.js?version=1', 'functions': []},
        {'url': 'http://127.0.0.1:2048/static/timezone-cities-zh.js', 'functions': []},
        {'url': 'http://127.0.0.1:2048/service-worker.js', 'functions': []},
        {'url': 'chrome-extension://demo/inject.js', 'functions': []},
    ]
    scripts, ignored = filter_coverage_scripts(result)
    assert [item['name'] for item in scripts] == ['app.js', 'theme.js']
    assert ignored == 3


def test_write_coverage_payload_uses_gzip_and_preserves_metadata(tmp_path):
    # raw 报告必须是可解压 JSON，并保留测试节点、结果和脚本数据。
    path = write_coverage_payload(
        tmp_path,
        nodeid='tests/test_webui_navigation.py::test_example',
        outcome='passed',
        scripts=[{'name': 'app.js', 'url': 'http://127.0.0.1/static/app.js', 'functions': []}],
        ignored_script_count=2,
        collected_at='2026-11-25T00:00:00+00:00',
    )
    payload = json.loads(gzip.decompress(path.read_bytes()))
    assert payload['nodeid'] == 'tests/test_webui_navigation.py::test_example'
    assert payload['outcome'] == 'passed'
    assert payload['ignored_script_count'] == 2
    assert payload['scripts'][0]['name'] == 'app.js'
    assert path.parent.name == 'raw' and path.suffix == '.gz'


def test_chrome_session_starts_precise_coverage_before_navigation(tmp_path):
    # Profiler 必须先于任何页面导航启动，否则顶层脚本和未执行函数会缺失。
    session = ChromeSession(tmp_path)
    session.driver = FakeDriver()
    session.coverage_enabled = True
    session.coverage_directory = tmp_path / 'coverage'
    assert session.start_coverage() is True
    assert session.driver.commands == [
        ('Profiler.enable', {}),
        ('Profiler.startPreciseCoverage', {'callCount': True, 'detailed': True}),
    ]


def test_chrome_session_filters_and_writes_taken_coverage(tmp_path):
    # 用例结束时只写入 WebUI 脚本，并记录测试节点与结果。
    session = ChromeSession(tmp_path)
    session.driver = FakeDriver({'result': [
        {'url': 'http://127.0.0.1/static/app.js', 'scriptId': '1', 'functions': []},
        {'url': 'chrome-extension://demo/inject.js', 'scriptId': '2', 'functions': []},
    ]})
    session.coverage_enabled = True
    session.coverage_directory = tmp_path / 'coverage'
    session.coverage_open = True
    session.set_coverage_context('tests/test_example.py::test_case', 'passed')
    path = session.take_coverage()
    payload = json.loads(gzip.decompress(path.read_bytes()))
    assert payload['nodeid'] == 'tests/test_example.py::test_case'
    assert payload['outcome'] == 'passed'
    assert payload['ignored_script_count'] == 1
    assert [item['name'] for item in payload['scripts']] == ['app.js']


def test_chrome_session_skips_coverage_when_browser_is_closed(tmp_path):
    # 用例主动关闭浏览器后，清理阶段不应再生成重复的错误 raw 节点。
    class ClosedDriver(FakeDriver):
        @property
        def window_handles(self):
            raise RuntimeError('browser is closed')

    session = ChromeSession(tmp_path)
    session.driver = ClosedDriver()
    session.coverage_enabled = True
    session.coverage_directory = tmp_path / 'coverage'
    session.coverage_open = True
    session.set_coverage_context('tests/test_example.py::test_case', 'passed')
    assert session.take_coverage() is None
    assert not (tmp_path / 'coverage' / 'raw').exists()
    assert session.coverage_errors == ['take: no active browser window']


def test_chrome_session_writes_incomplete_payload_when_profiler_start_fails(tmp_path):
    # Profiler 启动失败时仍要留下不完整记录，避免报告把缺失当成完整覆盖。
    session = ChromeSession(tmp_path)
    session.driver = FailingDriver()
    session.coverage_enabled = True
    session.coverage_directory = tmp_path / 'coverage'
    assert session.start_coverage() is False
    session.set_coverage_context('tests/test_example.py::test_case', 'passed')
    path = session.take_coverage()
    payload = json.loads(gzip.decompress(path.read_bytes()))
    assert payload['nodeid'] == 'tests/test_example.py::test_case'
    assert payload['scripts'] == []
    assert 'profiler unavailable' in payload['error']


def test_chrome_session_writes_incomplete_payload_when_no_scripts_match(tmp_path):
    # 只采集到非 WebUI 脚本时也要写入不完整记录，并保留被忽略的脚本数量。
    session = ChromeSession(tmp_path)
    session.driver = FakeDriver({'result': [
        {'url': 'chrome-extension://demo/inject.js', 'scriptId': '2', 'functions': []},
    ]})
    session.coverage_enabled = True
    session.coverage_directory = tmp_path / 'coverage'
    session.coverage_open = True
    session.set_coverage_context('tests/test_example.py::test_case', 'passed')
    path = session.take_coverage()
    payload = json.loads(gzip.decompress(path.read_bytes()))
    assert payload['scripts'] == []
    assert payload['ignored_script_count'] == 1
    assert '未采集到 WebUI 脚本' in payload['error']


def test_chrome_session_open_starts_coverage_before_returning(tmp_path, monkeypatch):
    # 浏览器打开流程必须在返回驱动前启动 Profiler，确保首页脚本也被采集。
    from selenium import webdriver

    driver = FakeDriver()
    monkeypatch.delenv('OLIVOS_CHROMEDRIVER', raising=False)
    monkeypatch.delenv('OLIVOS_CHROME_BINARY', raising=False)
    monkeypatch.setattr(webdriver, 'Chrome', lambda service=None, options=None: driver)
    session = ChromeSession(tmp_path)
    session.coverage_enabled = True
    session.coverage_directory = tmp_path / 'coverage'
    assert session.open() is driver
    assert driver.commands == [
        ('Profiler.enable', {}),
        ('Profiler.startPreciseCoverage', {'callCount': True, 'detailed': True}),
    ]


def test_reset_raw_coverage_removes_previous_run(tmp_path):
    # 新会话开始前清空 raw 目录，但不应删除输出目录中的其它文件。
    previous = write_coverage_payload(
        tmp_path,
        nodeid='tests/test_example.py::test_old',
        outcome='passed',
        scripts=[],
    )
    kept = tmp_path / 'keep.txt'
    kept.write_text('keep', encoding='utf-8')
    reset_raw_coverage(tmp_path)
    assert not previous.exists()
    assert not previous.parent.exists()
    assert kept.is_file()


def test_prepare_frontend_coverage_clears_raw_when_enabled(tmp_path, monkeypatch):
    # 开启覆盖率时，会话入口必须清掉上一次运行留下的 raw 数据。
    previous = write_coverage_payload(
        tmp_path,
        nodeid='tests/test_example.py::test_old',
        outcome='passed',
        scripts=[],
    )
    monkeypatch.setenv('OLIVOS_WEBUI_COVERAGE', '1')
    monkeypatch.setenv('OLIVOS_WEBUI_COVERAGE_DIR', str(tmp_path))
    prepare_frontend_coverage()
    assert not previous.exists()


def test_prepare_frontend_coverage_keeps_raw_when_disabled(tmp_path, monkeypatch):
    # 未开启覆盖率时不应清理目录，避免影响用户已有的报告数据。
    previous = write_coverage_payload(
        tmp_path,
        nodeid='tests/test_example.py::test_old',
        outcome='passed',
        scripts=[],
    )
    monkeypatch.delenv('OLIVOS_WEBUI_COVERAGE', raising=False)
    monkeypatch.setenv('OLIVOS_WEBUI_COVERAGE_DIR', str(tmp_path))
    prepare_frontend_coverage()
    assert previous.is_file()
