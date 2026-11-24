"""Unit tests for WebUI V8 coverage collection helpers."""

import gzip
import json

from frontend_coverage_support import filter_coverage_scripts, write_coverage_payload
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
