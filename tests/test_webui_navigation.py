"""真实浏览器验证插件分组、独立功能页面、保活及响应式侧栏。"""

import os
import queue
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

import OlivOS
from OlivOS.webUI import resourceAPI, serverAPI, staticData


PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<style>
:root { color-scheme: light dark; }
body { margin: 0; padding: 32px; font: 15px/1.7 system-ui; }
h1 { margin: 0 0 12px; font-size: 24px; }
p { color: #73808e; }
label { display: grid; gap: 8px; max-width: 480px; }
input, button { font: inherit; padding: 10px 14px; border: 1px solid #90b3c5; border-radius: 6px; }
button { margin: 20px 0; cursor: pointer; }
output { display: block; color: #1593bb; }
</style><h1>TITLE</h1><p>多页面插件 · 功能页面验证</p>
<label>页面内容<input id="draft" placeholder="输入后切换页面，内容会保留"></label>
<button id="request">验证消息回包</button><output id="reply">等待操作</output>
<script>
window.pageIdentity = Math.random();
document.getElementById('request').onclick = () => {
  const id = location.pathname + '-' + Date.now();
  window.pendingRequest = id;
  parent.postMessage({type: 'olivos:plugin_event', event: 'verify', request_id: id,
    payload: {page: location.pathname, value: document.getElementById('draft').value}}, '*');
};
window.addEventListener('message', event => {
  if (event.source !== parent || event.data?.type !== 'olivos:plugin_reply') return;
  if (event.data.request_id !== window.pendingRequest) return;
  document.getElementById('reply').textContent = event.data.payload.text;
});
</script></html>'''


def test_embedded_navigation_assets_match_sources():
    import base64

    root = Path(__file__).resolve().parents[1] / 'OlivOS/webUI/static'
    for name in ('app.js', 'style.css'):
        assert base64.b64decode(staticData.FILES[name]) == root.joinpath(name).read_text(encoding='utf-8').encode()


@pytest.fixture
def navigation_host(tmp_path):
    host = serverAPI.server(root_path=tmp_path, rx_queue=queue.Queue(), control_queue=queue.Queue(),
                            server_conf={'host': '127.0.0.1', 'port': 0})
    for namespace, name, entries in [
        ('multi', '多页面插件', [('首页', 'webui/index.html'), ('配置管理', 'webui/settings/index.html'),
                            ('工具面板', 'webui/tools/index.html')]),
        ('single', '独立插件', [('功能首页', 'webui/index.html')]),
    ]:
        source = tmp_path / 'plugin/app' / namespace
        pages = []
        for title, path in entries:
            file = source / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(PAGE.replace('TITLE', title), encoding='utf-8')
            pages.append({'title': title, 'type': 'iframe', 'path': path})
        resources, pages = resourceAPI.declaration(source, {'webui_config': pages})
        host.plugin_roots[namespace] = str(source)
        host.plugin_webui_paths[namespace] = resources
        host.plugin_pages.extend(dict(page, namespace=namespace) for page in pages)
        host.plugins[namespace] = [name, '1.0', 'OlivOS', [], '分组导航测试', '', 1]
    stopped = threading.Event()

    def bus():
        while not stopped.is_set():
            try:
                packet = host.Proc_info.control_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if packet.action != 'send':
                continue
            data = packet.key.get('data', {})
            if data.get('action') == 'plugin_menu' and data.get('webui'):
                event = OlivOS.API.Event(packet, Proc=OlivOS.pluginAPI.shallow(
                    control_queue=host.Proc_info.control_queue))
                event.plugin_info.update(namespace=data['namespace'], control_queue=host.Proc_info.control_queue)
                event.send('webui', event.data.webui['request_id'], {'text': '回包成功：' + event.data.payload['value']})
            elif data.get('action') == 'webui_reply':
                host.consume(packet)

    workers = [threading.Thread(target=target, daemon=True) for target in (host.run, bus)]
    for worker in workers:
        worker.start()
    try:
        assert host.ready.wait(5) and host.error is None
        host.plugin_pages.insert(1, {'namespace': 'multi', 'type': 'link', 'title': '使用说明',
                                     'url': f"http://127.0.0.1:{host.config['port']}/api/health"})
        yield host
    finally:
        stopped.set()
        host.on_terminate()
        for worker in workers:
            worker.join(timeout=5)


@pytest.fixture
def browser(navigation_host, tmp_path):
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
                     '--window-size=1440,1000', f'--user-data-dir={tmp_path / "browser-profile"}'):
        options.add_argument(argument)
    if os.environ.get('OLIVOS_CHROME_BINARY'):
        options.binary_location = os.environ['OLIVOS_CHROME_BINARY']
    path = os.environ.get('OLIVOS_CHROMEDRIVER')
    driver = webdriver.Chrome(service=Service(executable_path=path) if path else None, options=options)
    wait = WebDriverWait(driver, 10)

    def find(selector):
        return driver.find_element(By.CSS_SELECTOR, selector)

    def click(selector):
        wait.until(lambda _: find(selector).is_displayed() and find(selector).is_enabled())
        find(selector).click()

    def select(path='webui/index.html', namespace='multi'):
        click(f'.plugin-link-entry[data-plugin-namespace="{namespace}"][data-plugin-path="{path}"]')
        wait.until(lambda _: driver.execute_script('return !!state.frame && !state.frame.hidden'))
        driver.switch_to.frame(driver.execute_script('return state.frame'))
        wait.until(lambda _: driver.execute_script('return !!window.pageIdentity'))
        return driver.execute_script('return window.pageIdentity')

    try:
        driver.get(f"http://127.0.0.1:{navigation_host.config['port']}")
        find('#token').send_keys(navigation_host.token)
        click('#login-form button')
        wait.until(lambda _: find('#shell').is_displayed())
        yield SimpleNamespace(driver=driver, wait=wait, find=find, click=click, select=select, host=navigation_host)
    finally:
        driver.quit()


@pytest.mark.browser
def test_plugin_navigation_groups_multiple_entries_and_directly_opens_single(browser):
    assert browser.find('.plugin-page-group[data-plugin-namespace="multi"] .plugin-group-count').text == '4'
    assert browser.find('.plugin-page-group[data-plugin-namespace="single"] .plugin-single-entry').is_displayed()
    browser.select(namespace='single')
    assert browser.find('h1').text == '功能首页'


@pytest.mark.browser
def test_plugin_page_switch_preserves_input_and_frame_identity(browser):
    identity = browser.select()
    browser.find('#draft').send_keys('retained')
    browser.driver.switch_to.default_content()
    browser.select('webui/settings/index.html')
    browser.driver.switch_to.default_content()
    assert browser.select() == identity
    assert browser.find('#draft').get_attribute('value') == 'retained'


@pytest.mark.browser
def test_plugin_browser_message_bridge_roundtrip(browser):
    browser.select()
    browser.find('#draft').send_keys('roundtrip')
    browser.click('#request')
    browser.wait.until(lambda _: browser.find('#reply').text == '回包成功：roundtrip')


@pytest.mark.browser
@pytest.mark.parametrize('failure', ['cookie', 'expired', 'evicted'])
def test_plugin_page_recovers_lost_session_before_open(browser, failure):
    if failure == 'cookie':
        browser.driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
    else:
        session = browser.driver.execute_script('return state.session')
        with browser.host.lock:
            if failure == 'expired':
                browser.host.sessions[session] = 0
            else:
                browser.host.sessions.pop(session)
    browser.select()
    browser.find('#draft').send_keys('recovered')
    browser.click('#request')
    browser.wait.until(lambda _: browser.find('#reply').text == '回包成功：recovered')


@pytest.mark.browser
def test_plugin_frame_reload_recovers_missing_cookie(browser):
    browser.select()
    browser.driver.execute_cdp_cmd('Network.clearBrowserCookies', {})
    browser.driver.execute_script('location.reload()')
    browser.driver.switch_to.default_content()
    browser.wait.until(lambda _: browser.driver.execute_script('return !!state.frame'))
    browser.driver.switch_to.frame(browser.driver.execute_script('return state.frame'))
    browser.wait.until(lambda _: browser.driver.execute_script('return !!window.pageIdentity'))
    browser.find('#draft').send_keys('reloaded')
    browser.click('#request')
    browser.wait.until(lambda _: browser.find('#reply').text == '回包成功：reloaded')


@pytest.mark.browser
@pytest.mark.parametrize('evicted', [False, True])
def test_open_plugin_survives_session_expiry_without_losing_form(browser, evicted):
    identity = browser.select()
    browser.find('#draft').send_keys('retained after expiry')
    browser.driver.switch_to.default_content()
    session = browser.driver.execute_script('state.sessionCheckedAt = 0; return state.session')
    with browser.host.lock:
        if evicted:
            browser.host.sessions.pop(session)
        else:
            browser.host.sessions[session] = 0
    browser.driver.execute_async_script('checkAuthentication().then(arguments[arguments.length - 1])')
    browser.driver.switch_to.frame(browser.driver.execute_script('return state.frame'))
    assert browser.driver.execute_script('return window.pageIdentity') == identity
    assert browser.find('#draft').get_attribute('value') == 'retained after expiry'
    browser.click('#request')
    browser.wait.until(lambda _: browser.find('#reply').text == '回包成功：retained after expiry')


@pytest.mark.browser
def test_slow_session_renewal_does_not_override_later_navigation(browser):
    browser.driver.execute_script('''
        window.originalFetch = window.fetch;
        window.pendingRenewal = null;
        window.fetch = (path, options) => path === '/api/session'
          ? new Promise(resolve => { pendingRenewal = () => resolve(originalFetch(path, options)); })
          : originalFetch(path, options);
    ''')
    browser.click('.plugin-link-entry[data-plugin-namespace="single"]')
    browser.wait.until(lambda _: browser.driver.execute_script('return !!pendingRenewal'))
    browser.click('[data-page="logs"]')
    browser.driver.execute_async_script('''
        const done = arguments[arguments.length - 1];
        window.fetch = originalFetch;
        pendingRenewal();
        state.sessionRefresh.then(() => setTimeout(done, 0));
    ''')
    assert browser.find('#page-title').text == '日志'
    assert browser.driver.execute_script('return state.frame === null && state.frames.size === 0')


@pytest.mark.browser
def test_collapsing_plugin_group_does_not_unload_frames(browser):
    identity = browser.select()
    browser.driver.switch_to.default_content()
    toggle = '.plugin-page-group[data-plugin-namespace="multi"] .plugin-group-toggle'
    browser.click(toggle)
    assert browser.find(toggle).get_attribute('aria-expanded') == 'false'
    assert browser.driver.execute_script('return state.frames.size') == 1
    browser.click(toggle)
    assert browser.select() == identity


@pytest.mark.browser
def test_duplicate_plugin_and_page_names_are_disambiguated(browser):
    with browser.host.lock:
        browser.host.plugins['single'][0] = browser.host.plugins['multi'][0]
        for page in browser.host.plugin_pages:
            if page.get('path') == 'webui/tools/index.html':
                page['title'] = '配置管理'
    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return document.querySelectorAll(".plugin-group-namespace").length') == 2)
    assert browser.driver.execute_script('return document.querySelectorAll(".plugin-entry-path").length') == 2
    browser.select('webui/tools/index.html')
    browser.driver.switch_to.default_content()
    title = browser.find('[data-plugin-path="webui/tools/index.html"]').find_element('xpath', '..')
    assert title.find_element('css selector', '.plugin-link-close').get_attribute('title') == (
        '关闭：多页面插件（multi） / 配置管理（webui/tools/index.html）')


@pytest.mark.browser
def test_closing_one_plugin_page_keeps_other_cached_pages(browser):
    browser.select()
    browser.driver.switch_to.default_content()
    browser.select('webui/settings/index.html')
    browser.driver.switch_to.default_content()
    row = browser.find('.plugin-link-entry[data-plugin-namespace="multi"][data-plugin-path="webui/index.html"]')
    row.find_element('xpath', '..').find_element('css selector', '.plugin-link-close').click()
    assert browser.driver.execute_script('return state.frames.size') == 1
    assert browser.find('#page-title').text == '配置管理'


@pytest.mark.browser
def test_close_all_reports_plugin_and_page_counts(browser):
    browser.select()
    browser.driver.switch_to.default_content()
    browser.select(namespace='single')
    browser.driver.switch_to.default_content()
    browser.click('#plugin-pages-close')
    browser.wait.until(lambda _: browser.driver.execute_script('return state.frames.size') == 0)
    assert browser.find('#notice-message').text == '已关闭全部插件页面（2 个插件，共 2 个页面）。'


@pytest.mark.browser
def test_refresh_restores_selected_plugin_page(browser):
    browser.select('webui/settings/index.html')
    browser.driver.switch_to.default_content()
    browser.driver.refresh()
    browser.wait.until(lambda _: browser.find('#shell').is_displayed())
    assert browser.driver.execute_script('return state.framePath') == 'webui/settings/index.html'


@pytest.mark.browser
def test_plugin_registration_change_updates_group_navigation(browser):
    with browser.host.lock:
        browser.host.plugin_pages = [page for page in browser.host.plugin_pages
                                     if page['namespace'] != 'multi' or page.get('path') == 'webui/index.html']
    browser.click('[data-page="plugins"]')
    selector = '.plugin-page-group[data-plugin-namespace="multi"] .plugin-single-entry'
    browser.wait.until(lambda _: browser.find(selector).is_displayed())
    browser.select()
    assert browser.find('h1').text == '首页'


@pytest.mark.browser
@pytest.mark.parametrize('width,theme', [(390, 'light'), (1440, 'dark')])
def test_plugin_navigation_layout_fits_viewport(browser, width, theme):
    browser.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
    browser.driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
        'features': [{'name': 'prefers-color-scheme', 'value': theme}]})
    browser.wait.until(
        lambda _: browser.driver.execute_script('return document.documentElement.dataset.theme') == theme)
    assert browser.driver.execute_script('return document.documentElement.scrollWidth <= innerWidth')


@pytest.mark.browser
def test_external_plugin_link_opens_separate_tab(browser):
    browser.click('.plugin-link-external')
    browser.wait.until(lambda _: len(browser.driver.window_handles) == 2)
    browser.driver.switch_to.window(browser.driver.window_handles[-1])
    browser.wait.until(lambda _: 'OK' in browser.find('body').text)
