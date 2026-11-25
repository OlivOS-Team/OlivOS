"""Create test WebUI instances and reusable browser sessions."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from frontend_coverage_support import (
    coverage_directory,
    coverage_enabled,
    filter_coverage_scripts,
    write_coverage_payload,
)
from OlivOS.webUI import authAPI, serverAPI


FIXTURE_PASSWORD = 'webui-fixture-password'


class ChromeSession:
    """每个测试模块复用一个 Chrome，避免 CI 连续启动浏览器产生随机初始化失败。"""

    def __init__(self, profile):
        self.profile = Path(profile)
        self.driver = None
        self.coverage_enabled = coverage_enabled()
        self.coverage_directory = coverage_directory()
        self.coverage_open = False
        self.coverage_nodeid = None
        self.coverage_outcome = 'unknown'
        self.coverage_start_error = None
        self.coverage_errors = []

    def set_coverage_context(self, nodeid, outcome='unknown'):
        self.coverage_nodeid = nodeid
        self.coverage_outcome = outcome

    def start_coverage(self):
        if not self.coverage_enabled or self.driver is None or self.coverage_open:
            return False
        try:
            self.driver.execute_cdp_cmd('Profiler.enable', {})
            self.driver.execute_cdp_cmd('Profiler.startPreciseCoverage', {
                'callCount': True,
                'detailed': True,
            })
        except Exception as exc:
            self.coverage_start_error = f'Profiler 启动失败：{exc}'
            self.coverage_errors.append(f'start: {exc}')
            return False
        self.coverage_start_error = None
        self.coverage_open = True
        return True

    def _select_primary_window(self):
        if self.driver is None:
            return False
        try:
            handles = self.driver.window_handles
            if handles:
                self.driver.switch_to.window(handles[0])
                return True
        except Exception:
            return False
        return False

    def _write_incomplete_coverage(self, nodeid, error, ignored_script_count=0):
        """记录没有有效脚本的采集，避免报告把缺失数据当成完整覆盖。"""
        self.coverage_errors.append(f'incomplete: {error}')
        try:
            return write_coverage_payload(
                self.coverage_directory,
                nodeid=nodeid,
                outcome=self.coverage_outcome,
                scripts=[],
                ignored_script_count=ignored_script_count,
                error=error,
            )
        except OSError as write_exc:
            self.coverage_errors.append(f'write: {write_exc}')
            return None

    def take_coverage(self):
        if not self.coverage_enabled or self.driver is None:
            return None
        nodeid = self.coverage_nodeid
        if not nodeid:
            return None
        if not self.coverage_open:
            error = self.coverage_start_error or 'Chrome DevTools 覆盖率未启动'
            return self._write_incomplete_coverage(nodeid, error)
        if not self._select_primary_window():
            self.coverage_errors.append('take: no active browser window')
            return None
        try:
            data = self.driver.execute_cdp_cmd('Profiler.takePreciseCoverage', {})
        except Exception as exc:
            self.coverage_open = False
            self.coverage_errors.append(f'take: {exc}')
            return self._write_incomplete_coverage(nodeid, str(exc))
        scripts, ignored = filter_coverage_scripts(data.get('result', []))
        if not scripts:
            return self._write_incomplete_coverage(
                nodeid,
                '未采集到 WebUI 脚本；请确认 Profiler 已在首次导航前启动',
                ignored_script_count=ignored,
            )
        try:
            return write_coverage_payload(
                self.coverage_directory,
                nodeid=nodeid,
                outcome=self.coverage_outcome,
                scripts=scripts,
                ignored_script_count=ignored,
            )
        except OSError as exc:
            self.coverage_errors.append(f'write: {exc}')
            return None

    def open(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service

        if self.driver is not None:
            self.close()
        options = webdriver.ChromeOptions()
        if os.environ.get('OLIVOS_CHROME_NO_SANDBOX') == '1':
            options.add_argument('--no-sandbox')
        for argument in ('--headless=new', '--no-first-run', '--disable-background-networking',
                         '--window-size=1440,1000', f'--user-data-dir={self.profile}'):
            options.add_argument(argument)
        if os.environ.get('OLIVOS_CHROME_BINARY'):
            options.binary_location = os.environ['OLIVOS_CHROME_BINARY']
        path = os.environ.get('OLIVOS_CHROMEDRIVER')
        self.driver = webdriver.Chrome(service=Service(executable_path=path) if path else None, options=options)
        self.start_coverage()
        return self.driver

    def ensure_window(self):
        """只保留首个标签页，确保上一个用例打开的插件外链不会影响后续用例。"""
        from selenium.common.exceptions import WebDriverException

        if self.driver is None:
            return self.open()
        try:
            handles = self.driver.window_handles
        except WebDriverException:
            return self.open()
        if not handles:
            return self.open()
        primary = handles[0]
        for handle in handles[1:]:
            self.driver.switch_to.window(handle)
            self.driver.close()
        self.driver.switch_to.window(primary)
        self.start_coverage()
        return self.driver

    def prepare(self, url):
        """清除上一个用例留下的浏览器级状态，再把驱动交给新 origin 的页面。"""
        driver = self.ensure_window()
        driver.execute_cdp_cmd('Emulation.clearDeviceMetricsOverride', {})
        driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {'media': '', 'features': []})
        driver.execute_cdp_cmd('Network.emulateNetworkConditions', {
            'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1,
        })
        driver.execute_cdp_cmd('Network.clearBrowserCache', {})
        driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
        parts = urlsplit(url)
        driver.execute_cdp_cmd('Storage.clearDataForOrigin', {
            'origin': f'{parts.scheme}://{parts.netloc}', 'storageTypes': 'all',
        })
        return driver

    def close(self):
        driver = self.driver
        if driver is None:
            return
        self.take_coverage()
        self.coverage_open = False
        self.driver = None
        try:
            driver.quit()
        except Exception:
            # 浏览器可能已被用例主动关闭，模块清理只需尽力释放残留进程。
            pass


def make_host(*args, password=FIXTURE_PASSWORD, **kwargs):
    root = Path(kwargs.get('root_path', Path.cwd()))
    config = dict(serverAPI.DEFAULT_SERVER, **kwargs.get('server_conf', {}))
    path = authAPI.auth_path(root, config)
    if not path.exists():
        authAPI.write_record(path, authAPI.password_record(password))
    host = serverAPI.server(*args, **kwargs)
    assert host.error is None
    host.test_password = password
    response = host.app.test_client().post('/api/login', json={'password': password})
    assert response.status_code == 200
    host.test_token = response.json['browser_token']
    return host


def login_ui(driver, password, timeout=30, attempts=2):
    """在已打开的登录页完成登录，初始化卡住时刷新重试。

    Windows CI 的首个浏览器用例曾出现点击登录后 30 秒仍未进入主界面；
    重试前采集登录页状态，最终失败时能把错误提示和按钮状态带进断言。
    """
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    wait = WebDriverWait(driver, timeout)

    def snapshot():
        return driver.execute_script('''
            const shell = document.getElementById('shell');
            const login = document.getElementById('login');
            const error = document.getElementById('login-error');
            const submit = document.querySelector('#login-form button[type=submit]');
            return {
              href: location.href,
              readyState: document.readyState,
              loggedIn: Boolean(shell && !shell.hidden),
              loginVisible: Boolean(login && !login.hidden),
              error: error ? error.textContent : '',
              submitDisabled: submit ? submit.disabled : null,
            };
        ''')

    def ready(_):
        token = driver.find_element(By.ID, 'token')
        return token if token.is_displayed() and token.is_enabled() else False

    def settled(_):
        state = snapshot()
        return state if state['loggedIn'] or state['error'] else False

    last = None
    for attempt in range(attempts):
        if attempt:
            # 请求未返回时登录按钮会持续禁用，只有刷新页面才能重新发起。
            driver.refresh()
        token = wait.until(ready, '登录页输入框未出现')
        token.clear()
        token.send_keys(password)
        driver.find_element(By.CSS_SELECTOR, '#login-form button[type=submit]').click()
        try:
            last = wait.until(settled, '登录后主界面未出现')
        except TimeoutException:
            last = snapshot()
            continue
        if last['loggedIn']:
            return
        # 登录页给出了错误提示：刷新后仍按同一凭据重试，最终失败会保留该提示。
    raise AssertionError(f'登录后主界面未出现：{last}')
