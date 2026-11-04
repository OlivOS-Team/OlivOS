"""真实浏览器验证插件分组、独立功能页面、保活及响应式侧栏。"""

import os
import json
import queue
import threading
from types import SimpleNamespace

import pytest

import OlivOS
from OlivOS.webUI import resourceAPI
from webui_test_support import make_host


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


@pytest.fixture
def navigation_host(tmp_path):
    host = make_host(root_path=tmp_path, rx_queue=queue.Queue(), control_queue=queue.Queue(),
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

    def open_sidebar():
        if not driver.execute_script(
                'return matchMedia("(max-width: 800px), (orientation: portrait)").matches'):
            return
        if driver.execute_script("return document.getElementById('shell').dataset.sidebarOpen === 'true'"):
            return
        toggle = driver.execute_script('''
            return document.getElementById('plugin-page').hidden
                ? '#sidebar-toggle' : '#plugin-sidebar-toggle';
        ''')
        click(toggle)
        wait.until(lambda _: driver.execute_script(
            "return document.getElementById('shell').dataset.sidebarOpen === 'true'"))
        wait.until(lambda _: driver.execute_script(
            "return document.getElementById('sidebar').getBoundingClientRect().left >= -1"))

    def select(path='webui/index.html', namespace='multi'):
        open_sidebar()
        entry = find(f'.plugin-link-entry[data-plugin-namespace="{namespace}"][data-plugin-path="{path}"]')
        driver.execute_script('arguments[0].scrollIntoView({block: "center"})', entry)
        click(f'.plugin-link-entry[data-plugin-namespace="{namespace}"][data-plugin-path="{path}"]')
        wait.until(lambda _: driver.execute_script('return !!state.frame && !state.frame.hidden'))
        driver.switch_to.frame(driver.execute_script('return state.frame'))
        wait.until(lambda _: driver.execute_script('return !!window.pageIdentity'))
        return driver.execute_script('return window.pageIdentity')

    def wait_plugin_events():
        wait.until(lambda _: driver.execute_script(
            'return state.seenEvents.has(arguments[0])', navigation_host.sequence))
        driver.execute_async_script(
            'const done = arguments[0];'
            'Promise.resolve(state.pluginEventChain).then(() => done(true), () => done(true));')

    try:
        driver.get(f"http://127.0.0.1:{navigation_host.config['port']}")
        find('#token').send_keys(navigation_host.test_password)
        click('#login-form button[type=submit]')
        wait.until(lambda _: find('#shell').is_displayed())
        yield SimpleNamespace(driver=driver, wait=wait, find=find, click=click, select=select,
                              open_sidebar=open_sidebar, wait_plugin_events=wait_plugin_events,
                              host=navigation_host)
    finally:
        driver.quit()


@pytest.mark.browser
@pytest.mark.parametrize('field', ['password', 'server.access_token', 'appsecret', 'token', 'cookie', 'key'])
def test_secret_visibility_toggle_preserves_value_and_does_not_submit(browser, field):
    browser.driver.execute_script("""
        const field = arguments[0];
        state.draft = {password: 'fixture-secret', server: {access_token: 'fixture-secret'},
          extends: {[field]: 'fixture-secret'}};
        const attribute = ['password', 'server.access_token'].includes(field) ? 'data-field' : 'data-extend';
        $('account-fields').replaceChildren();
        fieldInput({name: field, title: 'Secret'}, $('account-fields'), attribute);
    """, field)
    result = browser.driver.execute_async_script("""
        const done = arguments[0];
        const input = document.querySelector('#account-fields input');
        const toggle = input.parentElement.querySelector('button');
        const initial = input.type;
        const closed = toggle.innerHTML;
        toggle.click();
        setTimeout(() => {
          const shown = input.type;
          const opened = toggle.innerHTML;
          toggle.click();
          setTimeout(() => done([initial, shown, input.type, input.value, toggle.type,
            closed !== opened && toggle.innerHTML === closed]), 0);
        }, 0);
    """)
    assert result == ['password', 'text', 'password', 'fixture-secret', 'button', True]


@pytest.mark.browser
def test_plugin_navigation_groups_multiple_entries_and_directly_opens_single(browser):
    assert browser.find('.plugin-page-group[data-plugin-namespace="multi"] .plugin-group-count').text == '4'
    assert browser.find('.plugin-page-group[data-plugin-namespace="single"] .plugin-single-entry').is_displayed()
    browser.select(namespace='single')
    assert browser.find('h1').text == '功能首页'


@pytest.mark.browser
def test_plugin_navigation_always_shows_namespace_and_uses_page_title_for_single(browser):
    browser.driver.switch_to.default_content()
    multi = browser.find('.plugin-page-group[data-plugin-namespace="multi"]')
    single = browser.find('.plugin-page-group[data-plugin-namespace="single"]')
    assert multi.find_element('css selector', '.plugin-group-namespace').text == 'multi'
    assert single.find_element('css selector', '.plugin-group-name').text == '功能首页'
    assert single.find_element('css selector', '.plugin-group-namespace').text == 'single'
    assert single.find_element('css selector', '.plugin-single-entry').get_attribute('title') == '独立插件'
    child = multi.find_element('css selector', '[data-plugin-path="webui/settings/index.html"]')
    assert child.get_attribute('title') == '配置管理'
    assert child.get_attribute('aria-label') == '配置管理（multi）'


@pytest.mark.browser
def test_plugin_menu_dialog_shows_namespace_priority_and_info(browser):
    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return document.querySelectorAll("#plugin-rows tr").length') == 2)
    browser.driver.execute_script('''
        const row = [...document.querySelectorAll('#plugin-rows tr')]
          .find(item => item.cells[0].textContent === '独立插件');
        row.cells[row.cells.length - 1].querySelector('button').click();
    ''')
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return document.getElementById("menu-dialog").open'))
    assert browser.find('#menu-title').text == '独立插件'
    labels = browser.driver.execute_script(
        'return [...document.querySelectorAll("#menu-meta dt")].map(item => item.textContent)')
    assert labels == ['命名空间', '优先级', '介绍']
    assert browser.find('#menu-namespace').text == 'single'
    assert browser.find('#menu-priority').text == '1（默认）'
    assert browser.find('#menu-info').text == '分组导航测试'


@pytest.mark.browser
def test_plugin_menu_priority_refreshes_while_dialog_open(browser):
    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return document.querySelectorAll("#plugin-rows tr").length') == 2)
    browser.driver.execute_script('''
        const row = [...document.querySelectorAll('#plugin-rows tr')]
          .find(item => item.cells[0].textContent === '独立插件');
        row.cells[row.cells.length - 1].querySelector('button').click();
    ''')
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return document.getElementById("menu-dialog").open'))
    assert browser.find('#menu-priority').text == '1（默认）'
    # 模拟另一个会话调整优先级：宿主只广播 priority_only，弹窗需要跟着刷新。
    with browser.host.lock:
        browser.host.plugin_priority['single'] = {
            'default': 1, 'user': 50, 'effective': 50, 'source': 'user'}
        browser.host.publish('events', {'type': 'plugins', 'ready': True, 'priority_only': True})
    browser.wait.until(
        lambda _: browser.find('#menu-priority').text == '50（用户 50 / 默认 1）')


@pytest.mark.browser
def test_plugin_page_switch_preserves_input_and_frame_identity(browser):
    driver = browser.driver
    identity = browser.select()
    browser.find('#draft').send_keys('retained')
    driver.switch_to.default_content()
    page_title = driver.execute_script('return state.frame.title')
    assert driver.execute_script(
        "return document.getElementById('plugin-page-title').textContent") == page_title
    assert driver.execute_script(
        "return getComputedStyle(document.getElementById('plugin-mobile-toolbar')).display") == 'none'
    browser.select('webui/settings/index.html')
    driver.switch_to.default_content()
    assert browser.select() == identity
    assert browser.find('#draft').get_attribute('value') == 'retained'


@pytest.mark.browser
def test_plugin_restart_hides_pages_then_restores_the_open_page(browser):
    identity = browser.select()
    browser.find('#draft').send_keys('before restart')
    browser.driver.switch_to.default_content()
    with browser.host.lock:
        plugins = browser.host.plugins
        pages = browser.host.plugin_pages
        browser.host.plugins = {}
        browser.host.plugin_pages = []
        browser.host.publish('events', {'type': 'plugins', 'ready': False})
    browser.wait_plugin_events()
    assert not browser.driver.execute_script(
        'return !!state.frame || !!document.querySelector("#plugin-links .plugin-link-entry")')
    assert browser.driver.execute_script('return !!state.pluginReload')
    with browser.host.lock:
        browser.host.plugins = plugins
        browser.host.plugin_pages = pages
        browser.host.publish('events', {'type': 'plugins', 'ready': True})
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return state.frame?.isConnected && !state.frame.hidden && state.framePath === arguments[0]',
        'webui/index.html'))
    browser.driver.switch_to.frame(browser.driver.execute_script('return state.frame'))
    browser.wait.until(lambda _: browser.driver.execute_script('return !!window.pageIdentity'))
    assert browser.driver.execute_script('return window.pageIdentity') != identity
    assert browser.find('#draft').get_attribute('value') == ''


@pytest.mark.browser
def test_stale_plugin_not_ready_event_keeps_open_page(browser):
    identity = browser.select()
    browser.find('#draft').send_keys('keep me')
    browser.driver.switch_to.default_content()
    with browser.host.lock:
        browser.host.publish('events', {'type': 'plugins', 'ready': False})
    browser.wait_plugin_events()
    assert browser.driver.execute_script('return state.frame?.isConnected && !state.frame.hidden')
    assert browser.find('.plugin-link-entry[data-plugin-namespace="multi"]').is_displayed()
    browser.driver.switch_to.frame(browser.driver.execute_script('return state.frame'))
    assert browser.driver.execute_script('return window.pageIdentity') == identity
    assert browser.find('#draft').get_attribute('value') == 'keep me'


@pytest.mark.browser
def test_reload_action_hides_open_page_before_ready(browser):
    identity = browser.select()
    browser.driver.switch_to.default_content()
    result = browser.driver.execute_async_script(
        'const done = arguments[0];'
        'runAction("reload", "/api/plugins/reload", "正在重载插件…")'
        '.then(() => done(true), (error) => done(String(error && error.message || error)));')
    assert result is True
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return !!state.pluginReload && !state.frame && '
        '!document.querySelector("#plugin-links .plugin-link-entry")'))
    with browser.host.lock:
        browser.host.publish('events', {'type': 'plugins', 'ready': True})
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return state.frame?.isConnected && !state.frame.hidden && state.framePath === arguments[0]',
        'webui/index.html'))
    browser.driver.switch_to.frame(browser.driver.execute_script('return state.frame'))
    browser.wait.until(lambda _: browser.driver.execute_script('return !!window.pageIdentity'))
    assert browser.driver.execute_script('return window.pageIdentity') != identity


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
            if page.get('path') == 'webui/tools/index.html' or page['type'] == 'link':
                page['title'] = '配置管理'
    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return document.querySelectorAll(".plugin-group-namespace").length') == 2)
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return document.querySelectorAll(".plugin-entry-path").length') == 3)
    group = '.plugin-page-group[data-plugin-namespace="multi"]'
    for path in ('webui/settings/index.html', 'webui/tools/index.html'):
        entry = browser.find(f'{group} [data-plugin-path="{path}"]')
        assert entry.accessible_name == f'配置管理（multi） / {path}'
    link = browser.find(f'{group} .plugin-link-external')
    assert link.accessible_name == f'配置管理（multi） / {link.get_attribute("href")}'
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
def test_theme_toggle_switches_both_buttons_and_persists(browser):
    from selenium.webdriver.common.by import By
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
        'features': [{'name': 'prefers-color-scheme', 'value': 'light'}]})
    driver.execute_script("localStorage.removeItem('olivos.webui.theme')")
    driver.refresh()
    browser.wait.until(lambda _: browser.find('#shell').is_displayed())
    browser.wait.until(lambda _: driver.execute_script(
        'return document.documentElement.dataset.theme') == 'light')

    def button_states():
        return driver.execute_script('''
            return [...document.querySelectorAll('[data-theme-toggle]')].map(button => ({
              pressed: button.getAttribute('aria-pressed'),
              label: button.querySelector('[data-theme-label]').textContent,
              action: button.getAttribute('aria-label'),
            }));
        ''')

    assert len(driver.find_elements(By.CSS_SELECTOR, '[data-theme-toggle]')) == 2
    assert button_states() == [
        {'pressed': 'false', 'label': '浅色模式', 'action': '切换到深色模式'},
        {'pressed': 'false', 'label': '浅色模式', 'action': '切换到深色模式'},
    ]
    browser.click('#sidebar [data-theme-toggle]')
    browser.wait.until(lambda _: driver.execute_script(
        'return document.documentElement.dataset.theme') == 'dark')
    assert driver.execute_script("return localStorage.getItem('olivos.webui.theme')") == 'dark'
    assert button_states() == [
        {'pressed': 'true', 'label': '深色模式', 'action': '切换到浅色模式'},
        {'pressed': 'true', 'label': '深色模式', 'action': '切换到浅色模式'},
    ]

    driver.refresh()
    browser.wait.until(lambda _: browser.find('#shell').is_displayed())
    browser.wait.until(lambda _: driver.execute_script(
        'return document.documentElement.dataset.theme') == 'dark')
    assert button_states()[0]['label'] == '深色模式'
    browser.click('#sidebar [data-theme-toggle]')
    browser.wait.until(lambda _: driver.execute_script(
        'return document.documentElement.dataset.theme') == 'light')
    assert driver.execute_script("return localStorage.getItem('olivos.webui.theme')") == 'light'


@pytest.mark.browser
def test_theme_toggle_follows_system_until_first_click(browser):
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
        'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}]})
    driver.execute_script("localStorage.removeItem('olivos.webui.theme')")
    driver.refresh()
    browser.wait.until(lambda _: browser.find('#shell').is_displayed())
    browser.wait.until(lambda _: driver.execute_script(
        'return document.documentElement.dataset.theme') == 'dark')
    assert browser.find('#sidebar [data-theme-toggle]').get_attribute('aria-label') == '切换到浅色模式'
    assert browser.find('#sidebar [data-theme-label]').text == '深色模式'

    driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
        'features': [{'name': 'prefers-color-scheme', 'value': 'light'}]})
    browser.wait.until(lambda _: driver.execute_script(
        'return document.documentElement.dataset.theme') == 'light')
    assert browser.find('#sidebar [data-theme-toggle]').get_attribute('aria-label') == '切换到深色模式'
    assert driver.execute_script("return localStorage.getItem('olivos.webui.theme')") is None


@pytest.mark.browser
def test_theme_and_logout_actions_share_layout_and_icons(browser):
    result = browser.driver.execute_script('''
        const theme = document.querySelector('#sidebar [data-theme-toggle]');
        const logout = document.getElementById('logout');
        const login = document.querySelector('#login [data-theme-toggle]');
        const loginLabel = login.querySelector('[data-theme-label]');
        const themeRect = theme.getBoundingClientRect();
        const logoutRect = logout.getBoundingClientRect();
        return {
          aligned: Math.abs(themeRect.left - logoutRect.left) < 0.5 &&
            Math.abs(themeRect.right - logoutRect.right) < 0.5 &&
            Math.abs(themeRect.width - logoutRect.width) < 0.5,
          stacked: logoutRect.top >= themeRect.bottom,
          sameHeight: Math.abs(themeRect.height - logoutRect.height) < 0.5,
          themeIcon: !!theme.querySelector('svg.theme-toggle-icon'),
          logoutIcon: !!logout.querySelector('svg.sidebar-action-icon'),
          loginIconOnly: login.classList.contains('theme-toggle-icon-only') &&
            getComputedStyle(loginLabel).position === 'absolute' &&
            parseFloat(getComputedStyle(loginLabel).width) <= 1,
          loginHasVisibleLabel: !!document.querySelector(
            '#login .theme-control > span:not([data-theme-label]):not(.login-version)'),
        };
    ''')
    assert result == {
        'aligned': True, 'stacked': True, 'sameHeight': True, 'themeIcon': True,
        'logoutIcon': True, 'loginIconOnly': True, 'loginHasVisibleLabel': False,
    }


@pytest.mark.browser
def test_custom_log_select_supports_pointer_and_keyboard(browser):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    driver = browser.driver
    browser.click('[data-page="logs"]')
    browser.wait.until(lambda _: browser.find('#logs').is_displayed())
    select = browser.find('#log-message-mode')
    assert select.get_attribute('aria-haspopup') == 'listbox'

    select.click()
    browser.wait.until(lambda _: browser.find('.select-menu').is_displayed())
    assert driver.execute_script(
        'return [...document.querySelectorAll(".select-menu-option")].map(item => item.textContent)'
    ) == ['OP', 'CQ']
    geometry = driver.execute_script("""
        const menu = document.querySelector('.select-menu');
        const style = getComputedStyle(menu);
        return {
          scrollableClass: menu.classList.contains('is-scrollable'),
          overflowY: style.overflowY,
        };
    """)
    assert geometry == {'scrollableClass': False, 'overflowY': 'hidden'}
    driver.find_elements(By.CSS_SELECTOR, '.select-menu-option')[1].click()
    browser.wait.until(lambda _: select.get_attribute('value') == 'cq')
    browser.wait.until(lambda _: driver.execute_script('return state.logMessageMode') == 'cq')
    assert driver.execute_script('return document.activeElement.id') == 'log-message-mode'
    assert not driver.find_elements(By.CSS_SELECTOR, '.select-menu')

    select.send_keys(Keys.ENTER)
    browser.wait.until(lambda _: browser.find('.select-menu').is_displayed())
    assert select.get_attribute('aria-expanded') == 'true'
    select.send_keys(Keys.ESCAPE)
    browser.wait.until(lambda _: not driver.find_elements(By.CSS_SELECTOR, '.select-menu'))
    assert select.get_attribute('aria-expanded') == 'false'
    assert driver.execute_script('return document.activeElement.id') == 'log-message-mode'

    select.send_keys(Keys.ARROW_UP)
    browser.wait.until(lambda _: browser.find('.select-menu').is_displayed())
    select.send_keys(Keys.ENTER)
    browser.wait.until(lambda _: select.get_attribute('value') == 'op')
    browser.wait.until(lambda _: driver.execute_script('return state.logMessageMode') == 'op')

    browser.find('label[for="log-message-mode"]').click()
    browser.wait.until(lambda _: browser.find('.select-menu').is_displayed())
    select.send_keys(Keys.TAB)
    browser.wait.until(lambda _: not driver.find_elements(By.CSS_SELECTOR, '.select-menu'))


@pytest.mark.browser
def test_custom_select_scrolls_only_when_options_overflow(browser):
    from selenium.webdriver.common.by import By
    driver = browser.driver
    browser.click('[data-page="logs"]')
    browser.wait.until(lambda _: browser.find('#logs').is_displayed())
    driver.execute_script("""
        const select = document.getElementById('log-message-mode');
        for (let index = 0; index < 20; index += 1) {
          select.append(new Option(`选项 ${index}`, `option-${index}`));
        }
    """)
    browser.find('#log-message-mode').click()
    browser.wait.until(lambda _: browser.find('.select-menu').is_displayed())
    browser.wait.until(lambda _: driver.execute_script(
        "return document.querySelector('.select-menu').classList.contains('is-scrollable')"))
    assert driver.execute_script("""
        const menu = document.querySelector('.select-menu');
        return {
          overflowY: getComputedStyle(menu).overflowY,
          hasOverflow: menu.scrollHeight > menu.clientHeight + 2,
        };
    """) == {'overflowY': 'auto', 'hasOverflow': True}
    driver.find_elements(By.CSS_SELECTOR, '.select-menu-option')[0].click()


@pytest.mark.browser
def test_log_level_summary_uses_custom_chevron(browser):
    driver = browser.driver
    browser.click('[data-page="logs"]')
    browser.wait.until(lambda _: browser.find('#logs').is_displayed())

    def chevron():
        return driver.execute_script("""
            const logStyle = getComputedStyle(
              document.querySelector('#log-filter > summary'), '::before');
            const selectStyle = getComputedStyle(
              document.querySelector('#log-message-mode + .select-chevron'), '::before');
            return {
              content: logStyle.content,
              width: logStyle.width,
              height: logStyle.height,
              borderRightWidth: logStyle.borderRightWidth,
              borderBottomWidth: logStyle.borderBottomWidth,
              transform: logStyle.transform,
              selectWidth: selectStyle.width,
              selectHeight: selectStyle.height,
              selectBorderRightWidth: selectStyle.borderRightWidth,
              selectBorderBottomWidth: selectStyle.borderBottomWidth,
              selectTransform: selectStyle.transform,
            };
        """)

    closed = chevron()
    assert closed['content'] == '""'
    assert closed['width'] == closed['selectWidth']
    assert closed['height'] == closed['selectHeight']
    assert closed['borderRightWidth'] == closed['selectBorderRightWidth']
    assert closed['borderBottomWidth'] == closed['selectBorderBottomWidth']
    assert closed['transform'] == closed['selectTransform']
    assert closed['transform'] != 'none'

    browser.click('#log-level')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('log-filter').open"))
    browser.wait.until(lambda _: chevron()['transform'] != closed['transform'])


@pytest.mark.browser
@pytest.mark.parametrize('width', [320, 1440])
def test_login_page_shows_version_beside_theme_toggle(browser, width):
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
    driver.execute_script('resetLogin()')
    browser.wait.until(lambda _: browser.find('#login').is_displayed())
    browser.wait.until(lambda _: browser.find('#login-version').is_displayed())
    browser.wait.until(lambda _: driver.execute_script(
        "return document.querySelector('[data-version-number]').textContent"
    ) == OlivOS.infoAPI.OlivOS_Version_Short)
    layout = driver.execute_script("""
        const row = document.querySelector('.login-theme-control');
        const version = document.getElementById('login-version');
        const slogan = version.querySelector('[data-version-slogan]');
        const theme = row.querySelector('[data-theme-toggle]');
        const rowRect = row.getBoundingClientRect();
        const versionRect = version.getBoundingClientRect();
        const themeRect = theme.getBoundingClientRect();
        return {
          slogan: slogan.textContent,
          versionLeft: Math.abs(versionRect.left - rowRect.left) < 1,
          themeRight: Math.abs(themeRect.right - rowRect.right) < 1,
          insideRow: versionRect.top >= rowRect.top - 1 && versionRect.bottom <= rowRect.bottom + 1,
          noOverflow: document.documentElement.scrollWidth <= innerWidth,
        };
    """)
    assert layout == {
        'slogan': OlivOS.infoAPI.OlivOS_Version_Slogan,
        'versionLeft': True,
        'themeRight': True,
        'insideRow': True,
        'noOverflow': True,
    }


@pytest.mark.browser
def test_account_dialog_custom_select_is_not_covered_by_modal(browser):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    driver = browser.driver
    browser.click('[data-page="accounts"]')
    browser.wait.until(lambda _: browser.find('#accounts').is_displayed())
    browser.click('#add-account')
    browser.wait.until(lambda _: driver.execute_script(
        'return document.getElementById("account-dialog").open'))
    select = browser.find('#account-sdk')
    select.click()
    browser.wait.until(lambda _: browser.find('.select-menu').is_displayed())
    geometry = driver.execute_script('''
        const menu = document.querySelector('.select-menu');
        const dialog = document.getElementById('account-dialog');
        const rect = menu.getBoundingClientRect();
        const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + 12);
        return {
          inDialog: menu.closest('dialog') === dialog,
          inViewport: rect.left >= 0 && rect.top >= 0 &&
            rect.right <= innerWidth && rect.bottom <= innerHeight,
          hitMenu: !!hit?.closest('.select-menu'),
        };
    ''')
    assert geometry == {'inDialog': True, 'inViewport': True, 'hitMenu': True}

    driver.execute_script('''
        document.getElementById('account-sdk').append(new Option('动态 SDK', 'dynamic-sdk'));
    ''')
    select.send_keys(Keys.ESCAPE)
    browser.wait.until(lambda _: not driver.find_elements(By.CSS_SELECTOR, '.select-menu'))
    select.click()
    browser.wait.until(lambda _: browser.find('.select-menu').is_displayed())
    labels = driver.execute_script(
        'return [...document.querySelectorAll(".select-menu-option")].map(item => item.textContent)')
    assert '动态 SDK' in labels
    driver.execute_script('''
        const select = document.getElementById('account-sdk');
        select.querySelector('option[value="dynamic-sdk"]')?.remove();
        closeSelectMenu();
    ''')


@pytest.mark.browser
def test_mobile_custom_select_menu_opens_above_and_fits_viewport(browser):
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': 320, 'height': 568, 'deviceScaleFactor': 1, 'mobile': False})
    browser.wait.until(lambda _: driver.execute_script(
        'return matchMedia("(max-width: 800px)").matches'))
    driver.execute_script('''
        const select = document.createElement('select');
        select.id = 'edge-select';
        for (let index = 0; index < 12; index += 1) {
          select.append(new Option(`选项 ${index}`, `v${index}`));
        }
        Object.assign(select.style, {
          position: 'fixed', left: '8px', bottom: '8px', width: '190px', zIndex: '100',
        });
        document.body.append(select);
        enhanceSelects(document);
        select.dispatchEvent(new PointerEvent('pointerdown', {
          bubbles: true, cancelable: true, pointerType: 'mouse',
        }));
    ''')
    browser.wait.until(lambda _: driver.execute_script(
        'return !!document.querySelector(".select-menu.opens-above")'))
    browser.wait.until(lambda _: driver.execute_script(
        'return document.querySelector(".select-menu").getAnimations()'
        '.every(item => item.playState === "finished")'))
    geometry = driver.execute_script('''
        const menu = document.querySelector('.select-menu');
        const select = document.getElementById('edge-select');
        const menuRect = menu.getBoundingClientRect();
        const selectRect = select.getBoundingClientRect();
        return {
          inViewport: menuRect.left >= 8 && menuRect.top >= 8 &&
            menuRect.right <= innerWidth - 8 && menuRect.bottom <= innerHeight - 8,
          aboveSelect: menuRect.bottom <= selectRect.top - 4,
          touchHeight: selectRect.height >= 44 &&
            document.getElementById('sidebar-toggle').getBoundingClientRect().height >= 44,
          fitsPage: document.documentElement.scrollWidth <= innerWidth,
        };
    ''')
    assert geometry == {
        'inViewport': True, 'aboveSelect': True, 'touchHeight': True, 'fitsPage': True,
    }
    driver.execute_script('''
        closeSelectMenu();
        document.getElementById('edge-select').remove();
    ''')


@pytest.mark.browser
def test_desktop_sidebar_collapses_and_persists(browser):
    driver = browser.driver
    width = driver.execute_script(
        "return document.getElementById('sidebar').getBoundingClientRect().width")
    main_width = driver.execute_script(
        "return document.querySelector('main').getBoundingClientRect().width")
    browser.click('#sidebar-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarCollapsed === 'true'"))
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('sidebar').getBoundingClientRect().width < 100"))
    assert browser.find('#sidebar-toggle').get_attribute('aria-expanded') == 'false'
    assert browser.find('#sidebar-toggle').get_attribute('aria-label') == '展开侧边栏'
    assert driver.execute_script(
        "return getComputedStyle(document.getElementById('plugin-navigation')).display") == 'none'
    assert driver.execute_script(
        "return getComputedStyle(document.querySelector('.sidebar-footer')).display") == 'flex'
    theme_toggle = browser.find('#sidebar [data-theme-toggle]')
    logout = browser.find('#logout')
    assert theme_toggle.is_displayed() and theme_toggle.is_enabled()
    assert logout.is_displayed() and logout.is_enabled()
    initial_theme = driver.execute_script('return document.documentElement.dataset.theme')
    theme_toggle.click()
    browser.wait.until(lambda _: driver.execute_script(
        'return document.documentElement.dataset.theme') != initial_theme)
    assert driver.execute_script('''
        const buttons = [...document.querySelectorAll('#sidebar .sidebar-footer > .sidebar-action')];
        return buttons.length === 2 && buttons.every(button => {
          const rect = button.getBoundingClientRect();
          return rect.width === 44 && rect.height === 44 &&
            [...button.querySelectorAll('svg')].some(icon => icon.getBoundingClientRect().width > 0);
        });
    ''')
    assert driver.execute_script('''
        return [...document.querySelectorAll('#sidebar .sidebar-action-label')]
          .every(label => getComputedStyle(label).display === 'none');
    ''')
    assert driver.execute_script(
        "return document.querySelector('main').getBoundingClientRect().width") > main_width
    assert width > 150

    driver.refresh()
    browser.wait.until(lambda _: browser.find('#shell').is_displayed())
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarCollapsed === 'true'"))
    assert driver.execute_script(
        "return document.getElementById('sidebar').getBoundingClientRect().width < 100")
    assert browser.find('#sidebar-toggle').get_attribute('aria-expanded') == 'false'


@pytest.mark.browser
def test_mobile_sidebar_drawer_opens_closes_and_returns_focus(browser):
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
    browser.wait.until(lambda _: driver.execute_script(
        'return matchMedia("(max-width: 800px)").matches'))
    assert browser.find('#sidebar-toggle').get_attribute('aria-expanded') == 'false'
    assert driver.execute_script(
        "return document.getElementById('sidebar').getAttribute('aria-hidden')") == 'true'

    browser.click('#sidebar-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'true'"))
    assert browser.find('#sidebar-toggle').get_attribute('aria-expanded') == 'true'
    assert driver.execute_script(
        "return document.getElementById('sidebar').getAttribute('aria-hidden')") == 'false'
    assert driver.execute_script('return document.body.classList.contains("sidebar-open")')
    assert driver.execute_script('return document.activeElement.id') == 'sidebar-close'
    assert driver.execute_script(
        "return getComputedStyle(document.getElementById('sidebar-backdrop')).visibility") == 'visible'
    assert driver.execute_script(
        "return document.elementFromPoint(innerWidth - 10, innerHeight / 2).id") == 'sidebar-backdrop'

    driver.execute_script("document.elementFromPoint(innerWidth - 10, innerHeight / 2).click()")
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'false'"))
    assert driver.execute_script('return document.body.classList.contains("sidebar-open")') is False
    assert driver.execute_script('return document.activeElement.id') == 'sidebar-toggle'

    browser.click('#sidebar-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'true'"))
    driver.execute_script(
        "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'false'"))
    assert driver.execute_script('return document.activeElement.id') == 'sidebar-toggle'


@pytest.mark.browser
def test_mobile_sidebar_closes_after_navigation(browser):
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
    browser.open_sidebar()
    browser.click('[data-page="accounts"]')
    browser.wait.until(lambda _: browser.find('#accounts').is_displayed())
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'false'"))
    assert driver.execute_script('return document.activeElement.id') == 'sidebar-toggle'
    assert browser.find('[data-page="accounts"]').get_attribute('aria-current') == 'page'


@pytest.mark.browser
@pytest.mark.parametrize('width', [320, 390])
def test_mobile_sidebar_drawer_fits_viewport(browser, width):
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
    browser.open_sidebar()
    assert driver.execute_script('return document.documentElement.scrollWidth <= innerWidth')
    assert driver.execute_script('''
        const sidebar = document.getElementById('sidebar').getBoundingClientRect();
        return sidebar.right <= innerWidth && sidebar.width <= innerWidth;
    ''')


@pytest.mark.browser
def test_sidebar_viewport_switch_clears_mobile_state(browser):
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
    browser.open_sidebar()

    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': 1440, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
    browser.wait.until(lambda _: driver.execute_script(
        'return !matchMedia("(max-width: 800px)").matches'))
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'false'"))
    assert driver.execute_script('return document.body.classList.contains("sidebar-open")') is False
    assert driver.execute_script(
        "return document.getElementById('sidebar').hasAttribute('aria-hidden')") is False
    assert driver.execute_script(
        "return document.getElementById('sidebar').getBoundingClientRect().width") > 150

    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
    browser.wait.until(lambda _: driver.execute_script(
        'return matchMedia("(max-width: 800px)").matches'))
    assert browser.find('#sidebar-toggle').get_attribute('aria-expanded') == 'false'
    assert driver.execute_script(
        "return document.getElementById('sidebar').getAttribute('aria-hidden')") == 'true'


@pytest.mark.browser
def test_mobile_plugin_viewport_and_sidebar_header_preserve_page(browser):
    driver = browser.driver

    def resize(height):
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': 390, 'height': height, 'deviceScaleFactor': 1, 'mobile': False})
        browser.wait.until(lambda _: driver.execute_script(
            'return Math.abs(window.visualViewport.height - arguments[0]) < 2', height))

    def frame_fits():
        return driver.execute_script('''
            const frame = state.frame;
            if (!frame || frame.hidden) return false;
            const rect = frame.getBoundingClientRect();
            const viewport = window.visualViewport;
            return rect.height > 0 && rect.top >= viewport.offsetTop - 1 &&
                rect.bottom <= viewport.offsetTop + viewport.height + 1;
        ''')

    resize(844)
    identity = browser.select()
    browser.find('#draft').send_keys('mobile draft')
    driver.switch_to.default_content()
    page_title = driver.execute_script('return state.frame.title')
    driver.execute_script('window.__pluginFrame = state.frame')
    assert driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen") == 'false'
    assert driver.execute_script(
        "return getComputedStyle(document.getElementById('plugin-mobile-toolbar')).display") == 'flex'
    assert driver.execute_script(
        "return !document.getElementById('plugin-mobile-back')")
    assert browser.find('#plugin-page-title').text == page_title
    assert driver.execute_script(
        "return document.getElementById('plugin-sidebar-toggle').getBoundingClientRect().height >= 44")
    browser.wait.until(lambda _: frame_fits())
    initial_height = driver.execute_script('return state.frame.getBoundingClientRect().height')

    # 模拟键盘压缩浏览器可视区域，等待真实 resize 事件驱动布局更新。
    resize(500)
    browser.wait.until(lambda _: frame_fits() and driver.execute_script(
        'return state.frame.getBoundingClientRect().height') < initial_height - 200)
    browser.click('#plugin-sidebar-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'true'"))
    assert browser.find('#plugin-sidebar-toggle').get_attribute('aria-expanded') == 'true'
    assert driver.execute_script('return document.activeElement.id') == 'sidebar-close'
    assert driver.execute_script('''
        const sidebar = document.getElementById('sidebar');
        const plugin = document.getElementById('plugin-page');
        const backdrop = document.getElementById('sidebar-backdrop');
        return getComputedStyle(sidebar).visibility === 'visible' &&
            Number(getComputedStyle(sidebar).zIndex) > Number(getComputedStyle(plugin).zIndex) &&
            getComputedStyle(backdrop).visibility === 'visible';
    ''')
    driver.execute_script(
        "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'false'"))
    assert driver.execute_script('return document.activeElement.id') == 'plugin-sidebar-toggle'
    assert driver.execute_script('return window.__pluginFrame === state.frame')
    driver.switch_to.frame(driver.execute_script('return state.frame'))
    assert driver.execute_script('return window.pageIdentity') == identity
    assert browser.find('#draft').get_attribute('value') == 'mobile draft'
    driver.switch_to.default_content()

    browser.open_sidebar()
    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: browser.find('#plugins').is_displayed())
    assert browser.select() == identity
    assert browser.find('#draft').get_attribute('value') == 'mobile draft'
    driver.switch_to.default_content()
    assert driver.execute_script('return window.__pluginFrame === state.frame')

    browser.open_sidebar()
    browser.click('[data-page="dashboard"]')
    browser.wait.until(lambda _: browser.find('#dashboard').is_displayed())


@pytest.mark.browser
def test_portrait_tablet_plugin_header_opens_sidebar(browser):
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': 900, 'height': 1200, 'deviceScaleFactor': 1, 'mobile': False})
    browser.wait.until(lambda _: driver.execute_script(
        "return matchMedia('(orientation: portrait)').matches"))
    browser.select()
    driver.switch_to.default_content()
    assert driver.execute_script(
        "return getComputedStyle(document.getElementById('plugin-mobile-toolbar')).display") == 'flex'
    browser.click('#plugin-sidebar-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'true'"))
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('sidebar').getBoundingClientRect().left >= -1"))
    assert driver.execute_script(
        "return document.getElementById('plugin-sidebar-toggle').getAttribute('aria-expanded')") == 'true'


@pytest.mark.browser
@pytest.mark.parametrize('width', [320, 390, 1440])
def test_dashboard_version_card_keeps_slogan_within_viewport(browser, width):
    driver = browser.driver
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
    browser.open_sidebar()
    browser.click('[data-page="dashboard"]')
    browser.wait.until(lambda _: driver.execute_script(
        'return document.querySelector(".card-version .version-slogan")?.textContent',
    ) == OlivOS.infoAPI.OlivOS_Version_Slogan)
    assert driver.execute_script(
        'return document.querySelector(".card-version .version-value").textContent',
    ) == OlivOS.infoAPI.OlivOS_Version_Short
    # 版本号折行、简称省略号截断，版本卡自身不能把整页撑出横向滚动条。
    assert driver.execute_script("""
        const card = document.querySelector('.card-version');
        return [card.scrollWidth <= card.clientWidth + 1,
                document.documentElement.scrollWidth <= innerWidth];
    """) == [True, True]


@pytest.mark.browser
def test_dashboard_uptime_advances_between_status_refreshes(browser):
    driver = browser.driver
    browser.open_sidebar()
    browser.click('[data-page="dashboard"]')
    browser.wait.until(lambda _: driver.execute_script("""
        return state.page === 'dashboard' && !!state.uptimeSnapshot &&
          document.getElementById('runtime').textContent.startsWith('运行时长：');
    """))
    initial = driver.execute_script("""
        return {
          text: document.getElementById('runtime').textContent,
          seconds: state.uptimeSnapshot.seconds,
        };
    """)

    # 状态轮询间隔是 10 秒；这里要求锚点不变时文本也能在本地计时器驱动下推进。
    browser.wait.until(lambda _: driver.execute_script("""
        return document.getElementById('runtime').textContent !== arguments[0] &&
          state.uptimeSnapshot.seconds === arguments[1];
    """, initial['text'], initial['seconds']))


@pytest.mark.browser
def test_external_plugin_link_opens_separate_tab(browser):
    browser.click('.plugin-link-external')
    browser.wait.until(lambda _: len(browser.driver.window_handles) == 2)
    browser.driver.switch_to.window(browser.driver.window_handles[-1])
    browser.wait.until(lambda _: 'OK' in browser.find('body').text)


@pytest.mark.browser
def test_plugin_priority_editor_updates_order_and_file(browser):
    host = browser.host
    with host.lock:
        host.plugin_order = ['multi', 'single']
        host.plugin_priority = {
            namespace: {'default': 20000, 'user': None, 'effective': 20000, 'source': 'default'}
            for namespace in ('multi', 'single')
        }
    browser.click('[data-page="plugins"]')
    # 登录时已用空优先级渲染过一轮列表，行数条件对旧渲染同样成立；
    # 必须等点击触发的 loadPlugins 把 20000 拉回 state 后再断言，否则会读到旧渲染。
    browser.wait.until(lambda _: browser.driver.execute_script(
        "return state.pluginPriority['single']?.effective === 20000"))
    row = browser.driver.execute_script('''
        return [...document.querySelectorAll('#plugin-rows tr')]
          .find(item => item.cells[0].textContent === '独立插件');
    ''')
    assert row is not None and '20000' in row.text
    field = row.find_element('css selector', '.priority-input')
    field.clear()
    field.send_keys('100')
    row.find_element('css selector', '.priority-editor button').click()
    browser.wait.until(lambda _: browser.driver.execute_script(
        "return state.pluginPriority['single'] && state.pluginPriority['single'].effective === 100"))
    document = json.loads((host.root / 'conf/plugin_priority.json').read_text(encoding='utf-8'))
    assert document['plugins']['single'] == {'priority': 100}
    assert browser.driver.execute_script('return state.pluginOrder[0]') == 'single'
