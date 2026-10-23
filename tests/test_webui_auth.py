"""Regression tests for WebUI browser authentication across server restarts."""

import os
import json
import queue
import threading
import time
from http.cookies import SimpleCookie
from types import SimpleNamespace

import pytest

import OlivOS
from OlivOS.webUI import authAPI, serverAPI
from webui_test_support import make_host


@pytest.fixture
def host(tmp_path):
    service = make_host(root_path=tmp_path, rx_queue=queue.Queue(), control_queue=queue.Queue())
    yield service
    service.on_terminate()


@pytest.fixture
def client(host):
    client = host.app.test_client()
    client.environ_base['HTTP_X_AUTH_TOKEN'] = host.test_token
    return client


def send(host, data):
    host.consume(OlivOS.API.Control.packet('send', {'data': data}))


@pytest.mark.parametrize('token,origin,status,message', [
    ('', None, 401, '未提供登录凭据'),
    ('incorrect-fixture-token', None, 401, '登录凭据无效'),
    ('webui.expired-fixture', None, 401, '浏览器登录凭据已失效'),
])
def test_login_explains_authentication_failure(host, token, origin, status, message):
    headers = {'X-Auth-Token': host.test_token if token is None else token}
    if origin is not None:
        headers['Origin'] = origin
    response = host.app.test_client().post('/api/login', headers=headers)
    assert response.status_code == status
    assert message in response.json['error']
    assert host.test_token not in response.text


def test_login_rate_limit_explains_retry_delay(host):
    client = host.app.test_client()
    for _ in range(10):
        assert client.post('/api/login').status_code == 401
    response = client.post('/api/login', headers={'X-Auth-Token': host.test_token})
    assert response.status_code == 429
    assert '一分钟后重试' in response.json['error']
    assert response.headers['Retry-After'] == '60'


def test_expired_browser_credentials_do_not_count_as_password_failures(host):
    client = host.app.test_client()
    for path in ('/api/status', '/api/login') * 8:
        response = client.open(path, method='POST' if path == '/api/login' else 'GET',
                               headers={'X-Auth-Token': 'webui.expired-fixture'})
        assert response.status_code == 401
    assert not host.failures
    assert client.post('/api/login', json={'password': host.test_password}).status_code == 200


def test_expired_browser_credentials_cannot_clear_or_bypass_password_rate_limit(host):
    client = host.app.test_client()
    for _ in range(10):
        assert client.post('/api/login', json={'password': 'incorrect-fixture'}).status_code == 401
    attempts = list(host.failures['127.0.0.1'])
    assert client.get('/api/status', headers={'X-Auth-Token': 'webui.expired-fixture'}).status_code == 401
    assert list(host.failures['127.0.0.1']) == attempts
    assert client.post('/api/login', json={'password': host.test_password}).status_code == 429
    assert client.post('/api/login', json={'password': 'incorrect-fixture'},
                       headers={'X-Auth-Token': 'webui.expired-fixture'}).status_code == 429


@pytest.mark.parametrize('status', [101, 200, 202, 204, 302, 304])
def test_successful_http_requests_and_ws_handshakes_are_not_logged(host, monkeypatch, status):
    records = []
    monkeypatch.setattr(host, 'log', lambda *args: records.append(args))
    host.log_access('GET', '/fixture', status, '127.0.0.1', time.monotonic())
    assert not records


@pytest.mark.parametrize('origin', ['https://public.example:20480', 'null', 'https://[invalid'])
def test_public_client_can_login_without_origin_host_restrictions(host, origin):
    response = host.app.test_client().post(
        '/api/login', base_url='http://public.example:20480',
        headers={'Origin': origin}, json={'password': host.test_password},
        environ_overrides={'REMOTE_ADDR': '203.0.113.10'},
    )
    assert response.status_code == 200


def test_http_access_logs_explain_rejection_without_credentials(host):
    records = []
    host.Proc_info.logger_proc = SimpleNamespace(log=lambda *args: records.append(args))
    client = host.app.test_client()
    response = client.post(
        '/api/login?token=query-fixture-secret',
        headers={'X-Auth-Token': host.test_token, 'Cookie': 'private-fixture-cookie',
                 'Origin': 'https://user:password-fixture-secret@public.example/path?token=origin-fixture-secret'},
        json={'password': 'body-fixture-secret'},
    )
    assert response.status_code == 401
    assert records[-1][0] == 3
    entry = json.loads(records[-1][1].removeprefix('WebUI HTTP '))
    assert entry['method'] == 'POST' and entry['route'] == '/api/login' and entry['status'] == 401
    assert entry['remote'] == '127.0.0.1' and entry['duration_ms'] >= 0
    assert '密码不正确' in entry['error']
    rejected_count = len(records)
    login = client.post('/api/login', headers={'X-Auth-Token': host.test_token}).json
    assert len(records) == rejected_count
    client.get('/private-path-fixture-secret?token=another-fixture-secret')
    assert json.loads(records[-1][1].removeprefix('WebUI HTTP '))['route'] == '<unmatched>'
    logged = repr(records)
    for secret in (host.test_token, host.test_password, login['session'], 'query-fixture-secret',
                   'private-fixture-cookie', 'password-fixture-secret', 'origin-fixture-secret',
                   'body-fixture-secret', 'private-path-fixture-secret', 'another-fixture-secret'):
        assert secret not in logged


def test_browser_login_cache_expires_on_restart(client, host):
    cached = client.post('/api/login').json['browser_token']
    assert cached.startswith('webui.') and cached != host.test_password
    headers = {'X-Auth-Token': cached}
    assert client.get('/api/status', headers=headers).status_code == 200
    assert client.post('/api/login', headers=headers).json['browser_token'] == cached
    assert client.post('/api/plugins/reload', headers=headers).status_code == 202
    assert host.Proc_info.control_queue.get_nowait().action == 'restart_send'
    send(host, {'action': 'update_data', 'data': {'ready': True}})
    send(host, {'action': 'account_update', 'data': host.accounts})
    assert client.post('/api/login', headers=headers).json['browser_token'] == cached

    host.on_terminate()
    restarted = make_host(root_path=host.root, control_queue=queue.Queue())
    try:
        other = restarted.app.test_client()
        assert restarted.credentials == host.credentials
        assert other.post('/api/login', headers=headers).status_code == 401
        assert other.get('/api/status', headers=headers).status_code == 401
        assert other.post('/api/plugins/reload', headers=headers).status_code == 401
        assert restarted.Proc_info.control_queue.empty()
        login = other.post('/api/login', json={'password': host.test_password})
        assert login.status_code == 200
        assert login.json['browser_token'] != cached
        assert other.get('/api/status', headers={'X-Auth-Token': login.json['browser_token']}).status_code == 200
    finally:
        restarted.on_terminate()


def test_browser_login_cache_expires_when_token_changes(client, host):
    cached = client.post('/api/login').json['browser_token']
    host.reset_password(authAPI.password_record('changed-fixture-password'))
    assert client.get('/api/status', headers={'X-Auth-Token': cached}).status_code == 401
    assert client.post('/api/login', json={'password': 'changed-fixture-password'}).status_code == 200


def test_session_renewal_requires_token_and_preserves_reply_session(client, host):
    session = client.post('/api/login').json['session']
    host.sessions[session] = 0
    unauthenticated = host.app.test_client()
    assert unauthenticated.post('/api/session', json={'session': session}).status_code == 401
    assert not host.session_valid(session)
    assert client.post('/api/session', json={'session': session},
                       headers={'Origin': 'https://foreign.invalid'}).status_code == 200
    response = client.post('/api/session', json={'session': session})
    assert response.status_code == 200
    assert response.json['session'] == session
    assert host.sessions[session] > time.monotonic() + 11 * 3600
    cookie = next(iter(SimpleCookie(response.headers['Set-Cookie']).values()))
    assert cookie['httponly'] and cookie['samesite'] == 'Strict' and cookie['path'] == '/plugin/'
    assert cookie['max-age'] == str(12 * 3600)
    assert client.post('/api/session', json={'session': []}).status_code == 200


def test_session_recreated_after_eviction(client, host):
    session = client.post('/api/login').json['session']
    host.sessions.pop(session)
    response = client.post('/api/session', json={'session': session})
    assert response.json['session'] != session
    assert host.session_valid(response.json['session'])


def test_renewed_browser_token_survives_capacity_eviction(client, host):
    renewed = host.test_token
    host.browser_tokens.clear()
    # 续期前它是最早的一条，续期必须同时更新淘汰顺序。
    host.browser_tokens[host.credential_key(renewed)] = time.monotonic() + 3600
    for index in range(127):
        host.browser_tokens['fixture-%d' % index] = time.monotonic() + 3600
    assert host.renew_browser_token(renewed)
    host.new_browser_token()
    assert host.browser_valid(renewed)


def test_plugin_cookie_names_are_isolated_by_port(client, host):
    from test_webui import install_plugin

    install_plugin(host)
    first = client.post('/api/login', base_url='http://localhost:20480')
    first_name = next(iter(SimpleCookie(first.headers['Set-Cookie'])))
    second = client.post('/api/login', base_url='http://localhost:20481')
    second_name = next(iter(SimpleCookie(second.headers['Set-Cookie'])))
    assert first_name != second_name
    client.post('/api/logout', base_url='http://localhost:20481', json={'session': second.json['session']})
    assert client.get('/plugin/demo/webui/index.html', base_url='http://localhost:20480').status_code == 200
    assert client.get('/plugin/demo/webui/index.html', base_url='http://localhost:20481').status_code == 401


def test_plugin_navigation_auth_failure_can_notify_parent_without_credentials(host):
    client = host.app.test_client()
    response = client.get('/plugin/demo/index.html', headers={'Sec-Fetch-Dest': 'iframe'})
    assert response.status_code == 401 and response.mimetype == 'text/html'
    assert 'olivos:plugin_auth_required' in response.text
    assert host.test_token not in response.text and host.test_password not in response.text
    assert 'allow-same-origin' not in response.headers['Content-Security-Policy']
    assert client.get('/plugin/demo/index.html').json == {'error': '请先登录 WebUI'}


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
        if os.environ.get('OLIVOS_CHROME_NO_SANDBOX') == '1':
            options.add_argument('--no-sandbox')
        if os.environ.get('OLIVOS_CHROME_BINARY'):
            options.binary_location = os.environ['OLIVOS_CHROME_BINARY']
        for argument in ('--headless=new', '--no-first-run', '--disable-background-networking',
                         f'--user-data-dir={host.root / "login-race-profile"}'):
            options.add_argument(argument)
        driver_path = os.environ.get('OLIVOS_CHROMEDRIVER')
        service = Service(executable_path=driver_path) if driver_path else None
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(f"http://127.0.0.1:{host.config['port']}")
        driver.find_element(By.ID, 'token').send_keys(host.test_password)
        driver.find_element(By.CSS_SELECTOR, '#login-form button[type=submit]').click()
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
              const stayedDisabled = document.querySelector('#login-form button[type=submit]').disabled;
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
    if os.environ.get('OLIVOS_CHROME_NO_SANDBOX') == '1':
        options.add_argument('--no-sandbox')
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
        service = make_host(root_path=host.root, rx_queue=queue.Queue(), control_queue=queue.Queue(),
                            server_conf={'host': '127.0.0.1', 'port': previous.config['port']})
        assert start(service) == ui.url
        assert service.credentials == host.credentials

    def open_browser():
        path = os.environ.get('OLIVOS_CHROMEDRIVER')
        ui.driver = webdriver.Chrome(service=Service(executable_path=path) if path else None, options=options)
        ui.wait = WebDriverWait(ui.driver, 10)

    def find(selector):
        return ui.driver.find_element(By.CSS_SELECTOR, selector)

    def login():
        find('#token').send_keys(host.test_password)
        find('#login-form button[type=submit]').click()
        ui.wait.until(lambda _: find('#shell').is_displayed())

    def logged_out():
        ui.wait.until(lambda _: find('#login').is_displayed() and find('#login-form button[type=submit]').is_enabled())
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
    assert ui.driver.execute_script(
        "return localStorage.getItem('olivos.webui.token') !== arguments[0]", ui.host.test_password)
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
    ui.find('#login-form button[type=submit]').click()
    ui.wait.until(lambda _: '密码不正确' in ui.find('#login-error').text)
    assert not ui.find('#shell').is_displayed()
    ui.login()


@pytest.mark.browser
def test_tray_ticket_logs_in_once_and_is_removed_from_browser_address(browser_auth):
    ui = browser_auth
    url = serverAPI.local_login_url(ui.host.root)
    previous_token = ui.driver.execute_script('return state.token')
    ui.driver.get(url)
    ui.wait.until(lambda _: ui.find('#shell').is_displayed() and ui.driver.execute_script(
        'return state.token !== arguments[0]', previous_token))
    assert ui.driver.execute_script('return location.hash') == ''
    ui.driver.get(url)
    ui.wait.until(lambda _: '一次性登录凭证' in ui.find('#login-error').text)
    assert not ui.find('#shell').is_displayed()
    assert ui.driver.execute_script('return location.hash') == ''


@pytest.mark.browser
def test_local_password_reset_returns_open_browser_to_login_without_restart(browser_auth):
    ui = browser_auth
    assert authAPI.set_local_password(ui.host.root, authAPI.password_record('updated-browser-fixture')) is True
    ui.logged_out()
    ui.find('#token').send_keys('updated-browser-fixture')
    ui.find('#login-form button[type=submit]').click()
    ui.wait.until(lambda _: ui.find('#shell').is_displayed())
    assert ui.host.error is None and ui.host.ready.is_set()


@pytest.mark.browser
@pytest.mark.parametrize('status,message', [
    (403, '请求来源校验失败：请检查反向代理的 Host'),
    (429, '尝试过多，请一分钟后重试'),
    (403, None),
])
def test_manual_login_displays_server_or_proxy_error(browser_auth, status, message):
    ui = browser_auth
    ui.find('#logout').click()
    ui.logged_out()
    ui.driver.execute_script('''
        window.originalFetch = window.fetch;
        window.fetch = (path, options) => path === '/api/login'
          ? Promise.resolve(new Response(arguments[1] === null ? '<html>Forbidden</html>'
            : JSON.stringify({error: arguments[1]}), {status: arguments[0]}))
          : originalFetch(path, options);
    ''', status, message)
    ui.find('#token').send_keys('fixture-token')
    ui.find('#login-form button[type=submit]').click()
    ui.wait.until(lambda _: ui.find('#login-error').text != '')
    assert ui.find('#login-error').text == (message or f'请求失败 ({status})')
    assert not ui.find('#shell').is_displayed()
    ui.driver.execute_script('window.fetch = originalFetch;')
    ui.find('#token').clear()
    ui.login()


@pytest.mark.browser
def test_legacy_long_lived_cache_requires_manual_login(browser_auth):
    ui = browser_auth
    ui.driver.get(ui.url + '/api/health')
    ui.driver.execute_script("localStorage.setItem('olivos.webui.token', arguments[0])", ui.host.test_password)
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
