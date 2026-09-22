"""Regression tests for WebUI browser authentication across server restarts."""

import os
import queue
import secrets
import threading
from types import SimpleNamespace

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
@pytest.mark.parametrize('reset_between', [False, True])
def test_obsolete_login_cannot_finish_a_new_attempt(host, reset_between):
    pytest.importorskip('selenium')
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    host.config.update(host='127.0.0.1', port=0)
    worker = threading.Thread(target=host.run, daemon=True)
    worker.start()
    driver = None
    try:
        assert host.ready.wait(5) and host.error is None
        options = webdriver.ChromeOptions()
        if os.environ.get('OLIVOS_CHROME_BINARY'):
            options.binary_location = os.environ['OLIVOS_CHROME_BINARY']
        for argument in ('--headless=new', '--no-first-run', '--disable-background-networking',
                         f'--user-data-dir={host.root / "login-race-profile"}'):
            options.add_argument(argument)
        driver_path = os.environ.get('OLIVOS_CHROMEDRIVER')
        service = Service(executable_path=driver_path) if driver_path else None
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(f"http://127.0.0.1:{host.config['port']}")
        driver.find_element(By.ID, 'token').send_keys(host.token)
        driver.find_element(By.CSS_SELECTOR, '#login-form button').click()
        WebDriverWait(driver, 10).until(lambda d: d.find_element(By.ID, 'shell').is_displayed())
        result = driver.execute_async_script('''
            const done = arguments[arguments.length - 1];
            const resetBetween = arguments[0];
            const originalFetch = window.fetch;
            const credential = state.token;
            const pending = [];
            resetLogin();
            window.fetch = (path, options) => path === '/api/login'
              ? new Promise((resolve, reject) => pending.push({path, options, resolve, reject}))
              : originalFetch(path, options);
            const oldAttempt = login(null, credential);
            if (resetBetween) resetLogin();
            const newAttempt = login(null, credential);
            pending[0].reject(new TypeError('delayed network error'));
            oldAttempt.then(async () => {
              const stayedDisabled = document.querySelector('#login-form button').disabled;
              const reply = await originalFetch(pending[1].path, pending[1].options);
              pending[1].resolve(reply);
              await newAttempt;
              window.fetch = originalFetch;
              done({stayedDisabled, loggedIn: !document.getElementById('shell').hidden});
            });
        ''', reset_between)
        assert result == {'stayedDisabled': True, 'loggedIn': True}
    finally:
        if driver is not None:
            driver.quit()
        host.on_terminate()
        worker.join(timeout=5)


@pytest.fixture
def browser_auth(host):
    if not os.environ.get('OLIVOS_WEBUI_BROWSER'):
        pytest.skip('Set OLIVOS_WEBUI_BROWSER=1 to run Chrome')
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    options = webdriver.ChromeOptions()
    for argument in ('--headless=new', '--no-first-run', '--disable-background-networking',
                     f'--user-data-dir={host.root / "auth-profile"}'):
        options.add_argument(argument)
    if os.environ.get('OLIVOS_CHROME_BINARY'):
        options.binary_location = os.environ['OLIVOS_CHROME_BINARY']
    services = []
    ui = SimpleNamespace(driver=None, host=host)

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
        service = serverAPI.server(root_path=host.root, rx_queue=queue.Queue(), control_queue=queue.Queue(),
                                   server_conf={'host': '127.0.0.1', 'port': previous.config['port']})
        assert start(service) == ui.url
        assert service.token == host.token

    def open_browser():
        path = os.environ.get('OLIVOS_CHROMEDRIVER')
        ui.driver = webdriver.Chrome(service=Service(executable_path=path) if path else None, options=options)
        ui.wait = WebDriverWait(ui.driver, 10)

    def find(selector):
        return ui.driver.find_element(By.CSS_SELECTOR, selector)

    def login():
        find('#token').send_keys(host.token)
        find('#login-form button').click()
        ui.wait.until(lambda _: find('#shell').is_displayed())

    def logged_out():
        ui.wait.until(lambda _: find('#login').is_displayed() and find('#login-form button').is_enabled())
        assert not find('#shell').is_displayed()
        assert find('#login-error').text == ''
        assert find('#token').get_attribute('value') == ''
        assert ui.driver.execute_script("return localStorage.getItem('olivos.webui.token') === null")
        assert not find('#notice').is_displayed()

    ui.find, ui.login, ui.logged_out, ui.restart, ui.open_browser = find, login, logged_out, restart, open_browser
    try:
        host.config.update(host='127.0.0.1', port=0)
        ui.url = start(host)
        open_browser()
        ui.driver.get(ui.url)
        login()
        yield ui
    finally:
        if ui.driver is not None:
            ui.driver.quit()
        for service, worker in services:
            service.on_terminate()
            worker.join(timeout=5)
            assert not worker.is_alive()


@pytest.mark.browser
@pytest.mark.parametrize('reopen', [False, True])
def test_browser_cache_survives_refresh_or_reopening(browser_auth, reopen):
    ui = browser_auth
    assert ui.driver.execute_script("return localStorage.getItem('olivos.webui.token') !== arguments[0]", ui.host.token)
    if reopen:
        ui.driver.quit()
        ui.open_browser()
        ui.driver.get(ui.url)
    else:
        ui.driver.refresh()
    ui.wait.until(lambda _: ui.find('#shell').is_displayed())


@pytest.mark.browser
def test_temporary_network_loss_does_not_clear_login(browser_auth):
    ui = browser_auth
    ui.driver.execute_cdp_cmd('Network.enable', {})
    network = {'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1}
    try:
        ui.driver.execute_cdp_cmd('Network.emulateNetworkConditions', dict(network, offline=True))
        ui.driver.execute_async_script('checkAuthentication().then(arguments[arguments.length - 1])')
        assert ui.find('#shell').is_displayed()
    finally:
        ui.driver.execute_cdp_cmd('Network.emulateNetworkConditions', dict(network, offline=False))
    ui.driver.execute_async_script('checkAuthentication().then(arguments[arguments.length - 1])')
    assert ui.find('#shell').is_displayed()


@pytest.mark.browser
@pytest.mark.parametrize('page_open', [False, True])
def test_server_restart_returns_browser_to_silent_login(browser_auth, page_open):
    ui = browser_auth
    if not page_open:
        ui.driver.get(ui.url + '/api/health')
    ui.restart()
    if page_open:
        ui.driver.execute_script('window.dispatchEvent(new Event("focus"))')
    else:
        ui.driver.get(ui.url)
    ui.logged_out()
    ui.login()


@pytest.mark.browser
def test_manual_wrong_token_shows_error_and_can_retry(browser_auth):
    ui = browser_auth
    ui.find('#logout').click()
    ui.logged_out()
    ui.find('#token').send_keys('incorrect-fixture-token')
    ui.find('#login-form button').click()
    ui.wait.until(lambda _: ui.find('#login-error').text == '认证失败')
    assert not ui.find('#shell').is_displayed()
    ui.login()


@pytest.mark.browser
def test_legacy_long_lived_cache_requires_manual_login(browser_auth):
    ui = browser_auth
    ui.driver.get(ui.url + '/api/health')
    ui.driver.execute_script("localStorage.setItem('olivos.webui.token', arguments[0])", ui.host.token)
    ui.driver.get(ui.url)
    ui.logged_out()


@pytest.mark.browser
def test_restart_during_login_initialization_ignores_delayed_response(browser_auth):
    ui = browser_auth
    ui.driver.execute_script('''
        window.originalFetch = window.fetch;
        window.waitingSchema = null;
        window.fetch = (path, options) => path === '/api/accounts/schema'
          ? new Promise(resolve => { window.waitingSchema = resolve; }) : originalFetch(path, options);
        window.oldLoginDone = false;
        login(null, state.token).then(() => { window.oldLoginDone = true; });
    ''')
    ui.wait.until(lambda _: ui.driver.execute_script('return !!window.waitingSchema'))
    ui.restart()
    ui.driver.execute_script('checkAuthentication()')
    ui.logged_out()
    ui.driver.execute_script('''
        window.fetch = window.originalFetch;
        window.waitingSchema(new Response(JSON.stringify({error: 'unauthorized'}), {status: 401}));
    ''')
    ui.wait.until(lambda _: ui.driver.execute_script('return window.oldLoginDone'))
    ui.logged_out()


@pytest.mark.browser
@pytest.mark.parametrize('status', [401, 403])
def test_late_authentication_and_network_failures_do_not_break_new_login(browser_auth, status):
    ui = browser_auth
    ui.driver.execute_script('''
        window.originalFetch = window.fetch;
        window.pendingAuth = [];
        window.authFailures = [];
        window.fetch = (path, options) => path === '/api/fixture'
          ? new Promise((resolve, reject) => pendingAuth.push({resolve, reject})) : originalFetch(path, options);
        for (let i = 0; i < 3; i++) api('/api/fixture').catch(error => {
          authFailures.push({message: error.message, obsolete: error.authObsolete === true});
          notifyError(error);
        });
        pendingAuth[0].resolve(new Response(JSON.stringify({error: 'unauthorized'}), {status: arguments[0]}));
    ''', status)
    ui.logged_out()
    ui.login()
    ui.driver.execute_script('''
        pendingAuth[1].resolve(new Response(JSON.stringify({error: 'unauthorized'}), {status: 401}));
        pendingAuth[2].reject(new TypeError('Failed to fetch'));
        window.fetch = originalFetch;
    ''')
    ui.wait.until(lambda _: ui.driver.execute_script('return authFailures.length === 3'))
    assert ui.driver.execute_script('return authFailures.slice(1).every(item => item.obsolete)')
    assert ui.find('#shell').is_displayed() and not ui.find('#notice').is_displayed()


@pytest.mark.browser
def test_rate_limit_message_does_not_log_browser_out(browser_auth):
    ui = browser_auth
    result = ui.driver.execute_async_script('''
        const done = arguments[arguments.length - 1], original = window.fetch;
        window.fetch = () => Promise.resolve(new Response(JSON.stringify({error: 'rate limited'}), {status: 429}));
        api('/api/fixture').catch(error => { window.fetch = original; done(error.message); });
    ''')
    assert result == 'rate limited' and ui.find('#shell').is_displayed()


@pytest.mark.browser
def test_clearing_login_cache_in_other_tab_logs_browser_out(browser_auth):
    ui = browser_auth
    ui.driver.execute_script('''
        localStorage.removeItem('olivos.webui.token');
        window.dispatchEvent(new StorageEvent('storage', {key: 'olivos.webui.token'}));
    ''')
    ui.logged_out()
