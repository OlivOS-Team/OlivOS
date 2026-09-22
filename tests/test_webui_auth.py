"""Regression tests for WebUI browser authentication across server restarts."""

import os
import queue
import secrets
import threading
from pathlib import Path

import pytest

import OlivOS
from OlivOS.webUI import serverAPI


@pytest.fixture
def host(tmp_path):
    service = serverAPI.server(root_path=tmp_path, rx_queue=queue.Queue(), control_queue=queue.Queue())
    yield service
    service.on_terminate()


@pytest.fixture
def client(host):
    client = host.app.test_client()
    client.environ_base['HTTP_X_AUTH_TOKEN'] = host.token
    return client


def send(host, data):
    host.consume(OlivOS.API.Control.packet('send', {'data': data}))


def test_browser_login_cache_expires_on_restart(client, host):
    cached = client.post('/api/login').json['browser_token']
    assert cached.startswith('webui.') and cached != host.token
    headers = {'X-Auth-Token': cached}
    assert client.get('/api/status', headers=headers).status_code == 200
    assert client.post('/api/login', headers=headers).json['browser_token'] == cached
    assert client.post('/api/plugins/reload', headers=headers).status_code == 202
    assert host.Proc_info.control_queue.get_nowait().action == 'restart_send'
    send(host, {'action': 'update_data', 'data': {'ready': True}})
    send(host, {'action': 'account_update', 'data': host.accounts})
    assert client.post('/api/login', headers=headers).json['browser_token'] == cached

    host.on_terminate()
    restarted = serverAPI.server(root_path=host.root, control_queue=queue.Queue())
    try:
        other = restarted.app.test_client()
        assert restarted.token == host.token
        assert other.post('/api/login', headers=headers).status_code == 401
        assert other.get('/api/status', headers=headers).status_code == 401
        assert other.post('/api/plugins/reload', headers=headers).status_code == 401
        assert restarted.Proc_info.control_queue.empty()
        login = other.post('/api/login', headers={'X-Auth-Token': host.token})
        assert login.status_code == 200
        assert login.json['browser_token'] != cached
        assert other.get('/api/status', headers={'X-Auth-Token': login.json['browser_token']}).status_code == 200
    finally:
        restarted.on_terminate()


def test_browser_login_cache_expires_when_token_changes(client, host):
    cached = client.post('/api/login').json['browser_token']
    host.token = secrets.token_urlsafe(32)
    assert client.get('/api/status', headers={'X-Auth-Token': cached}).status_code == 401
    assert client.post('/api/login', headers={'X-Auth-Token': host.token}).status_code == 200


@pytest.mark.skipif(not os.environ.get('OLIVOS_WEBUI_BROWSER'), reason='设置 OLIVOS_WEBUI_BROWSER=1 运行浏览器验证')
def test_browser_restart_requires_token(host):
    pytest.importorskip('selenium')
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    options = webdriver.ChromeOptions()
    for argument in ['--headless=new', '--no-first-run', '--disable-background-networking',
                     f'--user-data-dir={host.root / "browser-profile"}']:
        options.add_argument(argument)
    services = []
    driver = None
    screenshots = Path(os.environ.get('OLIVOS_WEBUI_SCREENSHOTS', host.root / 'screenshots'))
    screenshots.mkdir(parents=True, exist_ok=True)

    def browser():
        driver_path = os.environ.get('OLIVOS_CHROMEDRIVER')
        service = Service(executable_path=driver_path) if driver_path else None
        return webdriver.Chrome(options=options, service=service)

    def start(service):
        worker = threading.Thread(target=service.run, daemon=True)
        services.append((service, worker))
        worker.start()
        assert service.ready.wait(5) and service.error is None
        return f"http://127.0.0.1:{service.config['port']}"

    def restart():
        previous, worker = services[-1]
        previous.on_terminate()
        worker.join(timeout=5)
        assert not worker.is_alive()
        service = serverAPI.server(root_path=host.root, server_conf={'port': previous.config['port']},
                                   rx_queue=queue.Queue(), control_queue=queue.Queue(),
                                   bot_info_dict=host.accounts)
        assert start(service) == url
        assert service.token == host.token

    def visible(name):
        WebDriverWait(driver, 10).until(lambda d: d.find_element(By.ID, name).is_displayed())

    def login():
        driver.find_element(By.ID, 'token').send_keys(host.token)
        driver.find_element(By.CSS_SELECTOR, '#login-form button').click()
        visible('shell')

    def logged_out():
        visible('login')
        WebDriverWait(driver, 10).until(
            lambda d: d.find_element(By.CSS_SELECTOR, '#login-form button').is_enabled())
        assert driver.execute_script("return localStorage.getItem('olivos.webui.token') === null")
        assert not driver.find_element(By.ID, 'token').get_attribute('value')
        assert not driver.find_element(By.ID, 'shell').is_displayed()
        assert driver.find_element(By.ID, 'login-error').text == '登录已失效，请重新输入 Token。'
        assert not driver.find_element(By.ID, 'notice').is_displayed()

    try:
        host.config['port'] = 0
        url = start(host)
        driver = browser()
        driver.get(url)
        login()
        assert driver.execute_script(
            "return localStorage.getItem('olivos.webui.token') !== arguments[0]", host.token)
        driver.refresh()
        visible('shell')

        # 短暂断网保留缓存，恢复后继续使用当前登录。
        driver.execute_cdp_cmd('Network.enable', {})
        network = {'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1}
        driver.execute_cdp_cmd('Network.emulateNetworkConditions', dict(network, offline=True))
        driver.execute_async_script('checkAuthentication().then(arguments[arguments.length - 1])')
        visible('shell')
        driver.execute_cdp_cmd('Network.emulateNetworkConditions', dict(network, offline=False))
        driver.execute_async_script('checkAuthentication().then(arguments[arguments.length - 1])')
        visible('shell')

        # 真正关闭并重开浏览器，同一次 OlivOS 运行仍自动登录。
        driver.quit()
        driver = browser()
        driver.get(url)
        visible('shell')

        # 页面关闭期间重启服务，重新打开时必须手动输入原 Token。
        driver.get(url + '/api/health')
        restart()
        driver.get(url)
        logged_out()
        driver.save_screenshot(str(screenshots / 'restart-cached-login.png'))
        login()

        # 页面保持打开时重启，认证检查会退出并关闭弹窗。
        driver.find_element(By.CSS_SELECTOR, '[data-page="accounts"]').click()
        driver.find_element(By.ID, 'add-account').click()
        visible('account-dialog')
        restart()
        driver.execute_script('window.dispatchEvent(new Event("focus"))')
        logged_out()
        driver.save_screenshot(str(screenshots / 'restart-open-page.png'))
        assert not driver.find_element(By.ID, 'account-dialog').is_displayed()
        login()

        # 旧版缓存的长期 Token 不能在升级后直接恢复登录。
        driver.get(url + '/api/health')
        driver.execute_script("localStorage.setItem('olivos.webui.token', arguments[0])", host.token)
        driver.get(url)
        logged_out()
        login()

        # 登录初始化请求尚未返回时认证失效，迟到响应不能覆盖登录页提示。
        driver.execute_script('''
            window.authOriginalFetch = window.fetch;
            window.authWaitingSchema = null;
            window.fetch = (path, options) => path === '/api/accounts/schema'
              ? new Promise(resolve => { window.authWaitingSchema = resolve; })
              : window.authOriginalFetch(path, options);
            window.authOldLoginDone = false;
            login(null, state.token).then(() => { window.authOldLoginDone = true; });
        ''')
        WebDriverWait(driver, 10).until(lambda d: d.execute_script('return !!window.authWaitingSchema'))
        restart()
        driver.execute_script('checkAuthentication()')
        visible('login')
        driver.execute_script('''
            window.fetch = window.authOriginalFetch;
            window.authWaitingSchema(new Response(JSON.stringify({error: '认证失败'}), {status: 401}));
        ''')
        WebDriverWait(driver, 10).until(lambda d: d.execute_script('return window.authOldLoginDone'))
        logged_out()
        driver.save_screenshot(str(screenshots / 'restart-during-login.png'))
        login()

        # 多个请求同时失败：第一次退出后，迟到的认证/网络错误不干扰新的登录。
        for status in (401, 403):
            driver.execute_script('''
                window.authPending = [];
                window.authFailures = [];
                window.fetch = (path, options) => path === '/api/auth-notice-test'
                  ? new Promise((resolve, reject) => { window.authPending.push({resolve, reject}); })
                  : window.authOriginalFetch(path, options);
                for (let i = 0; i < 3; i++) api('/api/auth-notice-test').catch(error => {
                  window.authFailures.push({message: error.message, obsolete: error.authObsolete === true});
                  notifyError(error);
                });
                window.authPending[0].resolve(new Response(JSON.stringify({error: '认证失败'}),
                  {status: arguments[0]}));
            ''', status)
            logged_out()
            assert driver.execute_script('return window.authFailures[0].message') == '登录已失效，请重新输入 Token。'
            login()
            driver.execute_script('''
                window.authPending[1].resolve(new Response(JSON.stringify({error: '认证失败'}), {status: 401}));
                window.authPending[2].reject(new TypeError('Failed to fetch'));
                window.fetch = window.authOriginalFetch;
            ''')
            WebDriverWait(driver, 10).until(lambda d: d.execute_script('return window.authFailures.length === 3'))
            assert driver.execute_script('return window.authFailures.slice(1).every(item => item.obsolete)')
            visible('shell')
            assert not driver.find_element(By.ID, 'notice').is_displayed()

        # 限流仍显示原始原因，不能误报为登录失效。
        message = driver.execute_async_script('''
            const done = arguments[arguments.length - 1];
            window.fetch = () => Promise.resolve(new Response(
              JSON.stringify({error: '尝试过多，请一分钟后重试'}), {status: 429}));
            api('/api/auth-notice-test').catch(error => {
              window.fetch = window.authOriginalFetch;
              done(error.message);
            });
        ''')
        assert message == '尝试过多，请一分钟后重试'
        visible('shell')
    except Exception:
        if driver is not None:
            driver.execute_script("document.getElementById('token').value = ''")
            driver.save_screenshot(str(screenshots / 'failure.png'))
        raise
    finally:
        if driver is not None:
            driver.quit()
        for service, worker in services:
            service.on_terminate()
            worker.join(timeout=5)
            assert not worker.is_alive()
