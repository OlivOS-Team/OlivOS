"""Create test WebUI instances and reusable browser sessions."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from OlivOS.webUI import authAPI, serverAPI


FIXTURE_PASSWORD = 'webui-fixture-password'


class ChromeSession:
    """每个测试模块复用一个 Chrome，避免 CI 连续启动浏览器产生随机初始化失败。"""

    def __init__(self, profile):
        self.profile = Path(profile)
        self.driver = None

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
        driver, self.driver = self.driver, None
        if driver is None:
            return
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
