"""真实浏览器验证插件分组、独立功能页面、保活及响应式侧栏。"""

import json
import re
import queue
import threading
import time
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
def browser(navigation_host, chrome_session):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    url = f"http://127.0.0.1:{navigation_host.config['port']}"
    driver = chrome_session.prepare(url)
    wait = WebDriverWait(driver, 10)
    # Windows CI 连续启动 Chrome 时，首屏脚本偶尔会超过 10 秒才就绪；只放宽登录初始化。
    login_wait = WebDriverWait(driver, 30)

    def find(selector):
        return driver.find_element(By.CSS_SELECTOR, selector)

    def click(selector):
        wait.until(lambda _: find(selector).is_displayed() and find(selector).is_enabled())
        find(selector).click()

    def type_text(selector, text):
        # Chrome 158 对 sandbox iframe 内输入框的可交互性判定更严格，
        # 先点击聚焦，避免直接 send_keys 被 ChromeDriver 拒绝。
        field = find(selector)
        wait.until(lambda _: field.is_displayed() and field.is_enabled())
        field.click()
        field.send_keys(text)

    def open_sidebar():
        if not driver.execute_script(
                'return matchMedia("(max-width: 800px), (orientation: portrait)").matches'):
            return
        if driver.execute_script("return document.getElementById('shell').dataset.sidebarOpen === 'true'"):
            return
        click('#sidebar-toggle')
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

    driver.get(url)
    login_wait.until(lambda _: find('#token').is_displayed() and find('#token').is_enabled(),
                     '登录页输入框未出现')
    find('#token').send_keys(navigation_host.test_password)
    click('#login-form button[type=submit]')
    login_wait.until(lambda _: find('#shell').is_displayed(), '登录后主界面未出现')
    yield SimpleNamespace(driver=driver, wait=wait, find=find, click=click, type_text=type_text,
                          select=select, open_sidebar=open_sidebar,
                          wait_plugin_events=wait_plugin_events, host=navigation_host)


def set_viewport(browser, width, height, *, mobile_device=False):
    """切换视口，并等侧边栏完成移动端/桌面端模式同步。

    matchMedia 命中是同步的，但它派发的 change 事件是异步的，aria-expanded /
    aria-hidden 要等监听器跑完才更新；只等 matchMedia 就断言会读到上一档视口的旧值。
    """
    driver = browser.driver
    # 侧边栏媒体查询还包含纵向视口，宽大于 800px 的竖屏同样属于移动侧栏模式。
    mobile = width <= 800 or height > width
    driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
        'width': width, 'height': height, 'deviceScaleFactor': 1, 'mobile': mobile_device})
    browser.wait.until(lambda _: driver.execute_script(
        '''
        const mobile = matchMedia('(max-width: 800px), (orientation: portrait)').matches;
        const sidebar = document.getElementById('sidebar');
        const synced = mobile
            ? sidebar.getAttribute('aria-hidden') === 'true'
            : !sidebar.hasAttribute('aria-hidden');
        return mobile === arguments[0] && synced;
        ''', mobile))


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
@pytest.mark.parametrize('page', ['login', 'accounts'])
def test_password_eye_icon_matches_next_action(browser, page):
    if page == 'login':
        browser.click('#logout')
        field = '#token'
        form = '#login-form'
    else:
        browser.click('[data-page="accounts"]')
        browser.click('#add-account')
        field = '#account-form [data-field="password"]'
        form = '#account-dialog'
        if browser.driver.find_elements('css selector', '#account-extra-fields [data-field="password"]'):
            browser.click('#account-form details summary')

    browser.type_text(field, 'fixture-password')
    toggle = f'{field} + .secret-toggle'

    def check(input_type, action, svg_element):
        assert browser.find(form).is_displayed()
        secret = browser.find(field)
        assert secret.get_attribute('type') == input_type and secret.get_attribute('value') == 'fixture-password'
        assert browser.find(toggle).get_attribute('aria-label') == action
        assert browser.find(toggle).get_attribute('title') == action
        assert browser.find(f'{toggle} svg > {svg_element}:last-child').is_displayed()

    check('password', '显示内容', 'circle')
    browser.click(toggle)
    check('text', '隐藏内容', 'path')
    browser.click(toggle)
    check('password', '显示内容', 'circle')


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
    browser.type_text('#draft', 'retained')
    driver.switch_to.default_content()
    page_title = driver.execute_script('return state.frame.title')
    assert driver.execute_script(
        "return document.getElementById('page-title').textContent") == page_title
    browser.select('webui/settings/index.html')
    driver.switch_to.default_content()
    assert browser.select() == identity
    assert browser.find('#draft').get_attribute('value') == 'retained'


@pytest.mark.browser
def test_plugin_restart_hides_pages_then_restores_the_open_page(browser):
    identity = browser.select()
    browser.type_text('#draft', 'before restart')
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
    browser.type_text('#draft', 'keep me')
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
@pytest.mark.parametrize('phone_width', [None, 320, 390])
def test_schedule_timezone_browser_keeps_saved_and_active_separate(browser, phone_width):
    from selenium.webdriver.common.keys import Keys

    def report(zone):
        saved = OlivOS.scheduleAPI.read_settings(browser.host.root)
        packet = OlivOS.API.Control.packet('send', {
            'data': {'action': 'plugin_schedule_status', 'data': dict(saved, effective_timezone=zone)},
        })
        browser.host.Proc_info.rx_queue.put(packet)

    report('Asia/Shanghai')
    if phone_width:
        set_viewport(browser, phone_width, 640, mobile_device=True)
        browser.open_sidebar()
    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: '当前生效：上海（Asia/Shanghai）' in browser.find('#plugin-schedule-status').text)
    dropdown = '#plugin-schedule-timezone'
    assert browser.find(dropdown).get_attribute('value') == 'system'
    if phone_width:
        assert browser.driver.execute_script('''
            const zone = document.getElementById('plugin-schedule-timezone').getBoundingClientRect();
            const save = document.getElementById('plugin-schedule-save').getBoundingClientRect();
            return innerWidth === arguments[0] && document.documentElement.scrollWidth <= innerWidth &&
                zone.height >= 44 && save.height >= 44 && save.right <= innerWidth &&
                zone.right <= save.left && Math.abs(zone.top - save.top) < 4;
        ''', phone_width)
    else:
        assert browser.driver.execute_script('''
            const reload = document.getElementById('reload-plugins').getBoundingClientRect();
            const zone = document.getElementById('plugin-schedule-timezone').getBoundingClientRect();
            return zone.left > reload.right && Math.abs(zone.top - reload.top) < 4;
        ''')
    browser.click(dropdown)
    search = browser.find('.select-menu input[type="search"]')
    assert search == browser.driver.switch_to.active_element
    search.send_keys('上海')
    active = '.select-menu-option[data-active="true"]'
    assert browser.find(f'{active} .select-menu-option-detail').text == 'Asia/Shanghai'
    search.send_keys(Keys.CONTROL, 'a')
    search.send_keys('柏林')
    assert browser.find(f'{active} .select-menu-option-label').text == '柏林'
    assert browser.find(f'{active} .select-menu-option-detail').text == 'Europe/Berlin'
    if phone_width:
        assert browser.driver.execute_script('''
            const menu = document.querySelector('.select-menu').getBoundingClientRect();
            return menu.left >= 0 && menu.right <= innerWidth && menu.top >= 0 && menu.bottom <= innerHeight;
        ''')
    search.send_keys(Keys.CONTROL, 'a')
    search.send_keys('NoSuchCity')
    assert browser.find('.select-menu-empty').is_displayed()
    search.send_keys(Keys.CONTROL, 'a')
    search.send_keys('europe/berlin')
    if phone_width:
        browser.click(active)
    else:
        search.send_keys(Keys.ENTER)
    assert browser.find(dropdown).get_attribute('value') == 'Europe/Berlin'
    browser.click('#plugin-schedule-save')
    browser.wait.until(lambda _: '重载插件后生效' in browser.find('#plugin-schedule-status').text)
    assert '当前生效：上海（Asia/Shanghai）' in browser.find('#plugin-schedule-status').text
    assert OlivOS.scheduleAPI.read_settings(browser.host.root)['timezone'] == 'Europe/Berlin'
    report('Europe/Berlin')
    browser.wait.until(lambda _: browser.find('#plugin-schedule-status').text == '当前生效：柏林（Europe/Berlin）')


@pytest.mark.browser
@pytest.mark.parametrize('has_unavailable_panel', [False, True])
def test_plugins_show_only_empty_state_when_no_tk_panel_is_available(browser, has_unavailable_panel):
    if has_unavailable_panel:
        browser.host.tk_bridge.update({'generation': 'test-generation', 'tk_ready': False, 'panels': [
            {'namespace': 'multi', 'event': 'settings', 'title': '原有设置'},
        ]})
        set_viewport(browser, 320, 640, mobile_device=True)
        browser.open_sidebar()
    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: browser.find('#tk-bridge-empty').is_displayed())
    assert browser.find('#tk-bridge-empty').text == '当前没有可转换成 WebUI 的 GUI 面板'
    assert not browser.find('#tk-bridge-panel').is_displayed()
    assert not browser.driver.find_elements('css selector', '#tk-bridge-panels input')


@pytest.mark.browser
@pytest.mark.parametrize('phone_width', [None, 320])
def test_tk_bridge_paginates_only_target_table_and_waits_for_release(browser, monkeypatch, phone_width):
    from OlivOS.webUI import tkBridgeAPI

    host = browser.host
    monkeypatch.setattr(tkBridgeAPI.platform, 'system', lambda: 'Windows')
    send = host.send_control
    revokes = queue.Queue()

    def reply(data, **fields):
        host.Proc_info.rx_queue.put(OlivOS.API.Control.packet('send', {
            'data': dict(data, action='tk_bridge_reply', code=None, **fields),
        }))

    def section(text, **fields):
        return dict(id='table', group='列表', type='table', columns=['条目'],
                    rows=[{'id': 'row', 'cells': [text]}], **fields)

    def control(action, key):
        data = key.get('data', {})
        if data.get('action') != 'tk_bridge_request':
            return send(action, key)
        match data['op']:
            case 'open':
                reply(data, snapshot={'revision': 'first', 'sections': [
                    {'id': 'summary', 'group': '<概况>', 'type': 'label', 'text': '原始概况'},
                    section('第一页', next_cursor='next'),
                ]})
            case 'read' if data.get('cursor') == 'next':
                assert data['section_id'] == 'table'
                reply(data, snapshot={'revision': 'second', 'sections': [section('第二页')]})
            case 'read':
                reply(data, unchanged=True)
            case 'revoke':
                revokes.put(data)
            case _:
                reply(data)

    monkeypatch.setattr(host, 'send_control', control)
    host.tk_bridge.update({'generation': 'test-generation', 'tk_ready': True, 'panels': [
        {'namespace': 'multi', 'event': 'read_only', 'title': '只读菜单'},
    ]})
    if phone_width:
        set_viewport(browser, phone_width, 640, mobile_device=True)
        browser.open_sidebar()
    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: browser.find('#tk-bridge-panels input').is_enabled())
    assert browser.find('#tk-bridge-heading').text == '可转换为 WebUI 的 GUI 面板'
    assert not browser.find('#tk-bridge-empty').is_displayed()
    browser.click('#tk-bridge-panels input')
    browser.click('#tk-bridge-panels button')
    if phone_width:
        assert browser.driver.execute_script('''
            const dialog = document.getElementById('tk-bridge-dialog').getBoundingClientRect();
            return innerWidth === arguments[0] && dialog.left >= 0 && dialog.right <= innerWidth;
        ''', phone_width)
    browser.click('#tk-bridge-content section button')
    browser.wait.until(lambda _: '第二页' in browser.find('#tk-bridge-content').text)
    preview = browser.find('#tk-bridge-content').text
    assert '<概况>' in preview and '原始概况' in preview and '第一页' not in preview
    browser.click('[data-close="tk-bridge-dialog"]')
    revoke = revokes.get(timeout=2)
    browser.wait.until(lambda _: '正在撤销' in browser.find('#tk-bridge-panels').text)
    reply(revoke)
    browser.wait.until(lambda _: '只读菜单 · Tk 兼容' in browser.find('#tk-bridge-panels').text)


@pytest.mark.browser
def test_plugin_browser_message_bridge_roundtrip(browser):
    browser.select()
    browser.type_text('#draft', 'roundtrip')
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
    browser.type_text('#draft', 'recovered')
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
    browser.type_text('#draft', 'reloaded')
    browser.click('#request')
    browser.wait.until(lambda _: browser.find('#reply').text == '回包成功：reloaded')


@pytest.mark.browser
@pytest.mark.parametrize('evicted', [False, True])
def test_open_plugin_survives_session_expiry_without_losing_form(browser, evicted):
    identity = browser.select()
    browser.type_text('#draft', 'retained after expiry')
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
def test_plugin_navigation_matches_sidebar_selection_style(browser):
    from selenium.webdriver.common.action_chains import ActionChains

    browser.select()
    driver = browser.driver
    driver.switch_to.default_content()
    entry = browser.find('#plugin-links .plugin-link-entry.active')
    category = browser.find('[data-performance-category="overview"]')
    time.sleep(0.2)
    # 插件页面入口应对齐导航基准；性能分类复用导航样式，因此用作可见参照。
    active_styles = driver.execute_script("""
        return [arguments[0], arguments[1]].map((node) => {
          const style = getComputedStyle(node);
          return [style.backgroundColor, style.borderColor, style.boxShadow];
        });
    """, entry, category)
    assert active_styles[0] == active_styles[1]

    # 插件入口按下态也应对齐导航基准；性能分类复用同一套按下效果。
    pressed_script = """
        const style = getComputedStyle(arguments[0]);
        return {
          background: style.backgroundColor,
          border: style.borderColor,
          shadow: style.boxShadow,
          outline: style.outline,
        };
    """
    ActionChains(driver).click_and_hold(entry).perform()
    time.sleep(0.2)
    entry_pressed = driver.execute_script(pressed_script, entry)
    ActionChains(driver).release(entry).perform()
    time.sleep(0.05)

    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.getElementById('performance-content').hidden"))
    category = browser.find('[data-performance-category="overview"]')
    ActionChains(driver).click_and_hold(category).perform()
    time.sleep(0.2)
    category_pressed = driver.execute_script(pressed_script, category)
    ActionChains(driver).release(category).perform()
    assert entry_pressed == category_pressed


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
def test_notice_centers_message_vertically_and_keeps_it_left_aligned(browser):
    driver = browser.driver
    driver.execute_script("notify('已关闭插件页面：QQ 官方机器人控制台')")
    browser.wait.until(lambda _: browser.find('#notice').is_displayed())
    # 关闭按钮比单行文字高：文字上下留白要相等，横向仍从左侧起排。
    assert driver.execute_script("""
        const notice = document.getElementById('notice');
        const box = notice.getBoundingClientRect();
        const message = document.getElementById('notice-message').getBoundingClientRect();
        const style = getComputedStyle(notice);
        const leftInset = parseFloat(style.paddingLeft) + parseFloat(style.borderLeftWidth);
        const top = message.top - box.top;
        const bottom = box.bottom - message.bottom;
        return Math.abs(top - bottom) <= 1 && Math.abs(message.left - box.left - leftInset) <= 1;
    """)
    driver.execute_script('hideNotice()')


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
def test_pwa_manifest_and_service_worker_cache_only_app_shell(browser):
    driver = browser.driver
    assert driver.execute_script('return window.isSecureContext') is True
    manifest = driver.execute_async_script('''
        const done = arguments[0];
        const link = document.querySelector('link[rel="manifest"]');
        if (!link) return done({error: 'missing manifest link'});
        fetch(link.href).then(response => response.json()).then(done)
          .catch(error => done({error: String(error)}));
    ''')
    assert manifest.get('error') is None
    assert manifest['start_url'] == '/'
    assert manifest['scope'] == '/'
    assert manifest['display'] == 'standalone'

    worker = driver.execute_async_script('''
        const done = arguments[0];
        navigator.serviceWorker.ready.then(async registration => {
          const cacheNames = await caches.keys();
          const cacheName = cacheNames.find(name => name.startsWith('olivos-webui-'));
          if (!cacheName) return done({error: 'missing cache', cacheNames});
          const cache = await caches.open(cacheName);
          const requests = await cache.keys();
          done({
            scope: registration.scope,
            cacheNames,
            paths: requests.map(request => new URL(request.url).pathname).sort(),
          });
        }).catch(error => done({error: String(error)}));
    ''')
    assert worker.get('error') is None
    assert worker['scope'] == driver.execute_script('return location.origin + `/`')
    for path in ('/', '/manifest.webmanifest', '/static/static-files.json',
                 '/static/app.js', '/static/theme.js',
                 '/static/style.css', '/static/icon-192.png', '/static/icon-512.png',
                 '/static/icon-maskable-512.png', '/static/apple-touch-icon.png'):
        assert path in worker['paths']
    assert not any(path.startswith(('/api/', '/ws/', '/plugin/')) for path in worker['paths'])
    browser.wait.until(lambda _: driver.execute_script('return !!navigator.serviceWorker.controller'))
    driver.execute_cdp_cmd('Network.enable', {})
    offline = {'offline': True, 'latency': 0, 'downloadThroughput': 0, 'uploadThroughput': 0}
    online = {'offline': False, 'latency': 0, 'downloadThroughput': -1, 'uploadThroughput': -1}
    driver.execute_cdp_cmd('Network.emulateNetworkConditions', offline)
    try:
        driver.get(driver.current_url)
        browser.wait.until(lambda _: driver.execute_script('return document.readyState') == 'complete')
        assert driver.title == 'OlivOS · WebUI'
    finally:
        driver.execute_cdp_cmd('Network.emulateNetworkConditions', online)


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
          return rect.width >= 44 && rect.height === 44 &&
            [...button.querySelectorAll('svg')].some(icon => icon.getBoundingClientRect().width > 0);
        });
    ''')
    # 标签不能退回 display: none，而是收敛成 0 宽并透明，才能跟着折叠动画一起淡出。
    labels = driver.execute_script('''
        return [...document.querySelectorAll('#sidebar .sidebar-action-label')].map(label => {
          const style = getComputedStyle(label);
          return {
            text: label.textContent.trim(),
            display: style.display,
            opacity: Number(style.opacity),
            width: label.getBoundingClientRect().width,
          };
        });
    ''')
    assert labels
    for label in labels:
        assert label['display'] != 'none', labels
        assert label['opacity'] < 0.05, labels
        assert label['width'] < 1, labels
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
def test_desktop_sidebar_collapse_transitions_instead_of_jumping(browser):
    driver = browser.driver
    # 该用例专门验证过渡效果，固定成「允许动画」，避免系统开了减少动态效果时必然失败。
    driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
        'features': [{'name': 'prefers-reduced-motion', 'value': 'no-preference'}]})
    expanded = driver.execute_script(
        "return document.getElementById('sidebar').getBoundingClientRect().width")
    assert expanded > 150
    samples = driver.execute_async_script("""
        const done = arguments[0];
        const aside = document.getElementById('sidebar');
        const widths = [];
        const start = performance.now();
        document.getElementById('sidebar-toggle').click();
        function step() {
          widths.push(aside.getBoundingClientRect().width);
          if (performance.now() - start < 400) requestAnimationFrame(step);
          else done(widths);
        }
        requestAnimationFrame(step);
    """)
    # 有过渡时能逐帧采到中间宽度；直接跳变则第一帧就是收起后的宽度。
    assert any(expanded - 5 > width > 70 for width in samples), samples
    assert samples[-1] < 100

    browser.click('#sidebar-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarCollapsed === 'false'"))


@pytest.mark.browser
def test_mobile_sidebar_drawer_opens_closes_and_returns_focus(browser):
    driver = browser.driver
    set_viewport(browser, 390, 844)
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
def test_sidebar_orders_performance_between_logs_and_terminals(browser):
    # 主导航保持“仪表盘、账号、日志、性能、终端、插件”的顺序。
    assert browser.driver.execute_script("""
        return [...document.querySelectorAll('#navigation [data-page]')]
          .map((node) => node.dataset.page);
    """) == ['dashboard', 'accounts', 'logs', 'performance', 'terminals', 'plugins']


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
    set_viewport(browser, 390, 844)
    browser.open_sidebar()

    set_viewport(browser, 1440, 900)
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'false'"))
    assert driver.execute_script('return document.body.classList.contains("sidebar-open")') is False
    assert driver.execute_script(
        "return document.getElementById('sidebar').hasAttribute('aria-hidden')") is False
    assert driver.execute_script(
        "return document.getElementById('sidebar').getBoundingClientRect().width") > 150

    set_viewport(browser, 390, 844)
    assert browser.find('#sidebar-toggle').get_attribute('aria-expanded') == 'false'
    assert driver.execute_script(
        "return document.getElementById('sidebar').getAttribute('aria-hidden')") == 'true'


@pytest.mark.browser
def test_mobile_plugin_page_keeps_regular_layout_and_sidebar_drawer(browser):
    driver = browser.driver
    set_viewport(browser, 390, 844)

    identity = browser.select()
    browser.type_text('#draft', 'mobile draft')
    driver.switch_to.default_content()

    # 插件页不再独占可视区域：没有移动端工具栏，也不做全屏覆盖。
    assert driver.execute_script("return !document.getElementById('plugin-mobile-toolbar')")
    assert driver.execute_script(
        "return getComputedStyle(document.getElementById('plugin-page')).position") == 'static'
    assert driver.execute_script('return state.frame.getBoundingClientRect().height > 200')

    # 顶栏的侧边栏按钮在插件页上同样能唤出抽屉。
    browser.click('#sidebar-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'true'"))
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('sidebar').getBoundingClientRect().left >= -1"))
    assert driver.execute_script('return document.activeElement.id') == 'sidebar-close'

    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: browser.find('#plugins').is_displayed())
    assert browser.select() == identity
    assert browser.find('#draft').get_attribute('value') == 'mobile draft'


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
def test_dashboard_uptime_advances_smoothly_between_status_refreshes(browser):
    driver = browser.driver
    browser.open_sidebar()
    browser.click('[data-page="dashboard"]')
    browser.wait.until(lambda _: driver.execute_script("""
        return state.page === 'dashboard' && !!state.uptimeSnapshot &&
          document.getElementById('runtime').textContent.startsWith('运行时长：');
    """))
    # 状态每 3 秒刷新；显示只到秒，时分秒固定两位，任何一次校准都不能让文本回退或跨越超过一秒。
    driver.set_script_timeout(30)
    result = driver.execute_async_script("""
        const done = arguments[arguments.length - 1];
        const runtime = document.getElementById('runtime');
        const values = [];
        function parse(text) {
          const match = text.match(/^运行时长：(\\d+) 天 (\\d{2}) 时 (\\d{2}) 分 (\\d{2}) 秒$/);
          if (!match) return null;
          return (((Number(match[1]) * 24 + Number(match[2])) * 60 + Number(match[3])) * 60 +
            Number(match[4]));
        }
        let count = 0;
        function step() {
          const value = parse(runtime.textContent);
          if (value === null) {
            done({error: runtime.textContent});
            return;
          }
          values.push(value);
          count += 1;
          if (count >= 25) {
            done({values});
            return;
          }
          setTimeout(step, 50);
        }
        step();
    """)
    assert 'error' not in result, result.get('error')
    deltas = [later - earlier for earlier, later in zip(result['values'], result['values'][1:])]
    assert all(delta >= 0 for delta in deltas), deltas
    assert all(delta <= 1 for delta in deltas), deltas
    assert any(delta > 0 for delta in deltas), deltas
    # 运行时长跨越分钟、小时和天后必须继续累计，不能因单位换算出错而重置。
    uptime_boundaries = driver.execute_script(r'''
        return [59, 60, 61, 3599, 3600, 86399, 86400].map(
          (seconds) => uptimeText(seconds * 1000));
    ''')
    assert uptime_boundaries == [
        '运行时长：0 天 00 时 00 分 59 秒',
        '运行时长：0 天 00 时 01 分 00 秒',
        '运行时长：0 天 00 时 01 分 01 秒',
        '运行时长：0 天 00 时 59 分 59 秒',
        '运行时长：0 天 01 时 00 分 00 秒',
        '运行时长：0 天 23 时 59 分 59 秒',
        '运行时长：1 天 00 时 00 分 00 秒',
    ]


def statistics_snapshot(inbound=120, outbound=45, inbound_per_minute=5.0,
                        cpu_percent=32.5, memory_percent=37.5, disk_percent=25.0,
                        process_threads=18, process_handles=400, process_num_fds=None):
    # 仪表盘浏览器用例使用的完整快照，字段与 statisticsAPI.server.snapshot() 保持一致。
    now = time.time()
    timestamps = [now - 30, now - 20, now - 10, now]

    def window_timestamps(capacity, interval):
        return [now - interval * (capacity - index - 1) for index in range(capacity)]

    def padded(values, capacity):
        return [0] * max(0, capacity - len(values)) + values[-capacity:]

    def performance_window(interval, cpu_value, capacity=60):
        series_timestamps = window_timestamps(capacity, interval)
        series = {key: [cpu_value, cpu_value + 1, cpu_value + 2] for key in (
            'cpu_percent', 'load_1', 'memory_percent', 'swap_percent', 'swap_in_bps',
            'swap_out_bps', 'disk_percent', 'disk_read_bps', 'disk_write_bps',
            'network_recv_bps', 'network_sent_bps', 'process_count', 'process_rss',
            'process_cpu_percent', 'process_threads', 'process_handles',
        )}
        series = {key: padded(item, capacity) for key, item in series.items()}
        return {
            'interval': interval,
            'capacity': capacity,
            'timestamps': series_timestamps,
            **series,
        }

    def traffic_window(capacity, interval, base):
        series_timestamps = window_timestamps(capacity, interval)
        return {
            'interval': interval,
            'capacity': capacity,
            'timestamps': series_timestamps,
            'inbound': padded([base, base + 1, base + 2], capacity),
            'outbound': padded([base + 3, base + 4, base + 5], capacity),
            'events': padded([base + 6, base + 7, base + 8], capacity),
            'failed': padded([0, 1, 0], capacity),
        }

    return {
        'available': True,
        'sampled_at': now,
        'performance': {
            'sampled_at': now,
            'system': {
                'os': 'Windows',
                'os_release': '11',
                'os_version': '10.0.22631',
                'architecture': 'AMD64',
                'hostname': 'OLIVOS-TEST',
                'cpu_model': 'Test CPU 9000',
                'python_version': '3.11.9',
                'python_implementation': 'CPython',
                'working_directory': 'D:/fixture',
            },
            'cpu': {'percent': cpu_percent, 'count': 8, 'load_1': 1.25, 'load_5': 1.0,
                    'load_15': 0.8, 'physical_count': 4, 'frequency_mhz': 2400,
                    'per_cpu_percent': [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]},
            'memory': {'total': 16 * 1024 ** 3, 'used': 6 * 1024 ** 3,
                       'available': 10 * 1024 ** 3, 'free': 2 * 1024 ** 3,
                       'percent': memory_percent, 'cached': 3 * 1024 ** 3,
                       'buffers': 256 * 1024 ** 2, 'shared': 128 * 1024 ** 2,
                       'swap_total': 4 * 1024 ** 3, 'swap_used': 1024 ** 3,
                       'swap_free': 3 * 1024 ** 3, 'swap_percent': 25.0,
                       'swap_in_bps': 512, 'swap_out_bps': 256, 'page_faults': None},
            'disk': {'path': 'D:/fixture', 'total': 512 * 1024 ** 3, 'used': 128 * 1024 ** 3,
                     'percent': disk_percent, 'volume_count': 2,
                     'volumes': [{'device': 'C:', 'mountpoint': 'C:\\', 'total': 256 * 1024 ** 3,
                                  'used': 64 * 1024 ** 3, 'percent': 25.0},
                                 {'device': 'D:', 'mountpoint': 'D:\\', 'total': 256 * 1024 ** 3,
                                  'used': 64 * 1024 ** 3, 'percent': 25.0}],
                     'read_bps': 1024, 'write_bps': 2048, 'read_iops': 12.0,
                     'write_iops': 8.0, 'read_latency_ms': 1.8,
                     'write_latency_ms': 2.4},
            'network': {'sent_bps': 4096, 'recv_bps': 8192,
                        'packets_sent_per_second': 10, 'packets_recv_per_second': 20,
                        'errin_per_second': 0.5, 'errout_per_second': 0.25,
                        'dropin_per_second': 1.0, 'dropout_per_second': 0.0,
                        'connection_count': 7,
                        'tcp_states': {'ESTABLISHED': 4, 'TIME_WAIT': 3},
                        'interfaces': [
                            {'name': 'eth0', 'sent_bps': 2048, 'recv_bps': 4096,
                             'errin_per_second': 0.5, 'errout_per_second': 0.0,
                             'dropin_per_second': 1.0, 'dropout_per_second': 0.0},
                            {'name': 'wlan0', 'sent_bps': 1024, 'recv_bps': 2048,
                             'errin_per_second': 0.0, 'errout_per_second': 0.0,
                             'dropin_per_second': 0.0, 'dropout_per_second': 0.0},
                        ]},
            'process': {'count': 3, 'rss': 256 * 1024 ** 2, 'cpu_percent': 12.5,
                        'threads': process_threads, 'handles': process_handles,
                        'num_fds': process_num_fds},
            'history': {
                'interval': 1.0,
                'capacity': 120,
                'timestamps': timestamps,
                'cpu_percent': [10.0, 20.0, 30.0, cpu_percent],
                'load_1': [0.8, 0.95, 1.1, 1.25],
                'memory_percent': [34.0, 35.0, 36.0, memory_percent],
                'swap_percent': [0.0, 0.0, 0.0, 0.0],
                'swap_in_bps': [0, 128, 256, 512],
                'swap_out_bps': [0, 64, 128, 256],
                'disk_percent': [20.0, 21.0, 23.0, disk_percent],
                'disk_read_bps': [100, 200, 500, 1024],
                'disk_write_bps': [200, 400, 1000, 2048],
                'network_recv_bps': [1000, 2000, 4000, 8192],
                'network_sent_bps': [500, 1000, 2000, 4096],
                'process_count': [2, 2, 3, 3],
                'process_rss': [200 * 1024 ** 2, 220 * 1024 ** 2,
                                240 * 1024 ** 2, 256 * 1024 ** 2],
                'process_cpu_percent': [8.0, 9.0, 10.0, 12.5],
                'process_threads': [16, 17, 18, process_threads],
                'process_handles': [380, 390, 395, process_handles],
            },
            'sampling': {'interval': 1.0, 'history_capacity': 120,
                         'long_history_capacity': 901, 'rollup_interval': 60.0,
                         'rollup_capacity': 1441, 'last_sampled_at': now},
            'windows': {
                '1m': performance_window(1.0, 41.0),
                '5m': performance_window(5.0, 51.0),
                '15m': performance_window(15.0, 61.0),
                '1h': performance_window(60.0, 71.0),
                '6h': performance_window(360.0, 81.0),
                '24h': performance_window(600.0, 91.0, 144),
            },
        },
        'traffic': {
            'inbound_total': inbound,
            'outbound_total': outbound,
            'event_total': inbound + 10,
            'failed_total': 2,
            'inbound_per_minute': inbound_per_minute,
            'outbound_per_minute': 3.0,
            'event_per_minute': 6.0,
            'failed_per_minute': 1.0,
            'bucket_seconds': 5.0,
            'history_capacity': 60,
            'history': [
                {'ts': now - 10, 'inbound': 10, 'outbound': 4, 'events': 11, 'failed': 0},
                {'ts': now - 5, 'inbound': 12, 'outbound': 5, 'events': 13, 'failed': 1},
                {'ts': now, 'inbound': 8, 'outbound': 3, 'events': 9, 'failed': 1},
            ],
            'windows': {
                '1m': traffic_window(12, 5.0, 10),
                '5m': traffic_window(60, 5.0, 20),
                '15m': traffic_window(60, 15.0, 30),
                '1h': traffic_window(60, 60.0, 40),
                '6h': traffic_window(60, 360.0, 50),
                '24h': traffic_window(144, 600.0, 60),
            },
        },
    }


PROCESS_ROOT_CREATED_AT = time.time() - 60
PROCESS_CHILD_CREATED_AT = time.time() - 30


def process_tree_snapshot():
    # 进程标签使用按需接口，这里提供一棵包含父子进程和线程的最小树。
    now = time.time()
    return {
        'available': True,
        'sampled_at': now,
        'root_pid': 1000,
        'process_count': 2,
        'thread_count': 3,
        'roots': [{
            'pid': 1000,
            'ppid': 900,
            'name': 'python.exe',
            'status': 'running',
            'username': 'tester',
            'create_time': PROCESS_ROOT_CREATED_AT,
            'cmdline': 'python.exe main.py --token ********',
            'exe': 'C:/OlivOS/python.exe',
            'memory_rss': 128 * 1024 ** 2,
            'memory_vms': 256 * 1024 ** 2,
            'memory_percent': 3.2,
            'memory_peak': 144 * 1024 ** 2,
            'memory_private': 120 * 1024 ** 2,
            'memory_shared': 8 * 1024 ** 2,
            'cpu_percent': 2.5,
            'cpu_user': 1.2,
            'cpu_system': 0.3,
            'cpu_children_user': 0.1,
            'cpu_children_system': 0.05,
            'cpu_iowait': 0.0,
            'nice': 0,
            'io_priority': {'class': 2, 'value': 0},
            'cpu_affinity': [0, 1, 2, 3],
            'ctx_switches': {'voluntary': 120, 'involuntary': 4},
            'io': {'read_count': 10, 'write_count': 20,
                   'read_bytes': 10240, 'write_bytes': 20480},
            'thread_count': 2,
            'handles': 100,
            'num_fds': 42,
            'threads': [
                {'id': 1001, 'user': 0.8, 'system': 0.2, 'cpu_percent': 50.0,
                 'name': 'main', 'python_name': 'MainThread', 'state': 'S',
                 'priority': 20, 'nice': 0, 'processor': 1,
                 'ctx_switches': {'voluntary': 30, 'involuntary': 1},
                 'wchan': 'futex_wait_queue_me',
                 'start_time': PROCESS_ROOT_CREATED_AT + 1,
                 'start_module': 'python311.dll+0x4A2C'},
                {'id': 1002, 'user': 0.4, 'system': 0.1, 'cpu_percent': 25.0,
                 'name': 'worker', 'python_name': 'Thread-1', 'state': 'R',
                 'priority': 20, 'nice': 0, 'processor': 2,
                 'ctx_switches': {'voluntary': 10, 'involuntary': 0}},
            ],
            'threads_truncated': False,
            'children': [{
                'pid': 1001,
                'ppid': 1000,
                'name': 'python.exe',
                'status': 'sleeping',
                'username': 'tester',
                'create_time': PROCESS_CHILD_CREATED_AT,
                'cmdline': 'python.exe plugin_worker.py',
                'exe': 'C:/OlivOS/python.exe',
                'memory_rss': 64 * 1024 ** 2,
                'memory_vms': 128 * 1024 ** 2,
                'memory_percent': 1.6,
                'cpu_percent': 0.5,
                'cpu_user': 0.2,
                'cpu_system': 0.1,
                'thread_count': 1,
                'handles': 20,
                'num_fds': 18,
                'threads': [
                    {'id': 1003, 'user': 0.2, 'system': 0.1, 'cpu_percent': 0.0,
                     'name': 'worker', 'state': 'S', 'priority': 20, 'nice': 0, 'processor': 3},
                ],
                'threads_truncated': False,
                'children': [],
            }],
        }],
    }


def process_detail_snapshot(pid, create_time=None):
    # 进程详情按需加载，覆盖文件、连接、完整内存和内存映射四类高成本数据。
    return {
        'available': True,
        'pid': pid,
        'create_time': create_time or 0.0,
        'sampled_at': time.time(),
        'open_files': {
            'count': 2,
            'items': [
                {'path': 'C:/OlivOS/logfile/a.log', 'fd': 3, 'mode': 'r', 'position': 0},
                {'path': 'C:/OlivOS/conf/account.json', 'fd': 4, 'mode': 'r', 'position': 0},
            ],
            'truncated': False,
        },
        'connections': {
            'count': 1,
            'items': [{
                'fd': 5, 'family': 'AF_INET', 'type': 'SOCK_STREAM',
                'laddr': {'ip': '127.0.0.1', 'port': 8080},
                'raddr': {'ip': '127.0.0.1', 'port': 9090},
                'status': 'ESTABLISHED',
            }],
            'truncated': False,
        },
        'memory_full': {
            'rss': 128 * 1024 ** 2, 'vms': 256 * 1024 ** 2,
            'uss': 96 * 1024 ** 2, 'pss': 100 * 1024 ** 2,
            'private': 120 * 1024 ** 2, 'peak_wset': 144 * 1024 ** 2,
        },
        'memory_maps': {
            'count': 1,
            'items': [{
                'path': 'C:/Windows/System32/ntdll.dll',
                'metrics': {'rss': 4096, 'size': 8192, 'pss': 5000},
            }],
            'truncated': False,
        },
        'errors': [],
    }


def chart_contract(driver, selector):
    # 读取图表容量与每条折线的实际点数，用于验证补零后横轴点位固定。
    return driver.execute_script(r"""
        const svg = document.querySelector(arguments[0]).querySelector('svg');
        return {
          capacity: Number(svg.dataset.capacity),
          seriesCount: Number(svg.dataset.seriesCount),
          pointCounts: [...svg.querySelectorAll('.chart-series')].map(
            (series) => series.getAttribute('points').trim().split(/\s+/).length),
        };
    """, selector)


def hover_chart(driver, selector, ratio):
    # 按图表真实宽度换算指针位置并悬停，返回值来自页面实际生成的时间提示框。
    return driver.execute_script("""
        const container = document.querySelector(arguments[0]);
        const svg = container.querySelector('svg');
        const rect = svg.getBoundingClientRect();
        container.dispatchEvent(new PointerEvent('pointermove', {
          bubbles: true,
          clientX: rect.left + rect.width * arguments[1],
          clientY: rect.top + rect.height / 2,
        }));
        const tooltip = container.querySelector('.chart-tooltip');
        const cursor = container.querySelector('.chart-cursor');
        return {
          hidden: tooltip.hidden,
          text: tooltip.textContent,
          cursorVisible: getComputedStyle(cursor).display !== 'none',
        };
    """, selector, ratio)


def metric_card_text(driver, label):
    # 按指标名称读取合并网格中的卡片文本，避免依赖卡片在 DOM 里的固定序号。
    return driver.execute_script("""
        const card = [...document.querySelectorAll('#performance-metrics .metric-card')]
          .find((node) => node.querySelector('.metric-label').textContent === arguments[0]);
        return card ? card.textContent : '';
    """, label)


@pytest.mark.browser
def test_dashboard_statistics_render_update_and_stay_mobile_safe(browser):
    driver = browser.driver
    counts = {
        'inbound': 120, 'inbound_per_minute': 5.0,
        'cpu': 32.5, 'memory': 37.5, 'disk': 25.0,
    }

    def snapshot():
        return statistics_snapshot(
            inbound=counts['inbound'], inbound_per_minute=counts['inbound_per_minute'],
            cpu_percent=counts['cpu'], memory_percent=counts['memory'],
            disk_percent=counts['disk'])

    browser.host.runtime['statistics'] = SimpleNamespace(Proc_type='statistics', snapshot=snapshot)
    browser.open_sidebar()
    browser.click('[data-page="dashboard"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.getElementById('statistics-content').hidden"))
    assert browser.find('#performance-title').text == '性能'
    assert driver.execute_script(
        "return document.querySelectorAll('#statistics-content .dashboard-panel').length") == 1
    assert driver.execute_script("return document.querySelectorAll('.metric-card').length") == 6
    assert 'CPU' in browser.find('#performance-metrics').text
    assert '内存' in browser.find('#performance-metrics').text
    assert '磁盘' in browser.find('#performance-metrics').text
    assert '收发消息' in browser.find('#performance-metrics').text
    assert '事件总量' not in browser.find('#performance-metrics').text
    assert 'OlivOS 进程' not in browser.find('#performance-metrics').text
    assert '2 个卷' in browser.find('#performance-metrics').text
    # 网络与消息卡片分别合并上下行、出入站数据，并和普通性能指标处于同一网格。
    network_text = metric_card_text(driver, '网络')
    assert '↓ 8.0 KiB/s' in network_text and '↑ 4.0 KiB/s' in network_text
    traffic_text = metric_card_text(driver, '收发消息')
    assert '↓ 5 条/分钟 · ↑ 3 条/分钟' in traffic_text
    assert '累计 收 120 · 发 45' in traffic_text
    # 磁盘卡的环图表示占用率，小字同时展示读写瞬时速率。
    disk_text = metric_card_text(driver, '磁盘')
    assert '读取 1.0 KiB/s' in disk_text and '写入 2.0 KiB/s' in disk_text
    # OlivOS 进程规模归入 CPU 卡，进程 CPU/内存占整机的比例分别画成环内副弧。
    cpu_text = metric_card_text(driver, 'CPU')
    assert 'OlivOS 3 进程' in cpu_text and '18 线程' in cpu_text and '0.13 核心' in cpu_text
    assert '| OlivOS 3 进程' in cpu_text
    cpu_ring = browser.find('.metric-ring-card[data-ring="cpu"] .metric-ring')
    cpu_secondary_arc = cpu_ring.find_element('css selector', '.metric-ring-secondary')
    assert abs(float(cpu_ring.get_attribute('data-secondary-percent')) - 1.5625) < 0.0001
    assert abs(float(cpu_secondary_arc.get_attribute('stroke-dashoffset')) - 98.4375) < 0.0001
    memory_text = metric_card_text(driver, '内存')
    assert 'OlivOS 256.0 MiB (1.6%)' in memory_text and '| OlivOS 256.0 MiB' in memory_text
    assert '换入' not in memory_text and '换出' not in memory_text
    memory_ring = browser.find('.metric-ring-card[data-ring="memory"] .metric-ring')
    memory_secondary_arc = memory_ring.find_element('css selector', '.metric-ring-secondary')
    assert abs(float(memory_ring.get_attribute('data-secondary-percent')) - 1.5625) < 0.0001
    assert abs(float(memory_secondary_arc.get_attribute('stroke-dashoffset')) - 98.4375) < 0.0001
    # CPU、内存、磁盘使用环形卡，网络和消息卡保留文字卡。
    rings = driver.execute_script("""
        return [...document.querySelectorAll('.metric-ring-card')].map((card) => ({
          label: card.querySelector('.metric-label').textContent,
          value: card.querySelector('.metric-value').textContent,
          offset: Number(card.querySelector('.metric-ring-progress').getAttribute('stroke-dashoffset')),
        }));
    """)
    assert [(item['label'], item['value'], item['offset']) for item in rings] == [
        ('CPU', '32.5%', 67.5),
        ('内存', '37.5%', 62.5),
        ('磁盘', '25.0%', 75.0),
    ]
    # 六张趋势图分别嵌入 CPU、内存、磁盘、网络、收发消息和失败事件卡片，独立趋势区不再保留。
    assert driver.execute_script("return document.querySelectorAll('.trend-card').length") == 0
    cards = driver.execute_script("""
        return [...document.querySelectorAll('#performance-metrics .metric-card')].map((card) => {
          const chart = card.querySelector('.metric-card-chart');
          return {
            label: card.querySelector('.metric-label').textContent,
            chart: chart ? chart.id : '',
            ring: Boolean(card.querySelector('.metric-ring')),
          };
        });
    """)
    assert cards == [
        {'label': 'CPU', 'chart': 'dashboard-cpu-chart', 'ring': True},
        {'label': '内存', 'chart': 'dashboard-memory-chart', 'ring': True},
        {'label': '磁盘', 'chart': 'dashboard-disk-chart', 'ring': True},
        {'label': '网络', 'chart': 'dashboard-network-chart', 'ring': False},
        {'label': '收发消息', 'chart': 'dashboard-traffic-chart', 'ring': False},
        {'label': '失败事件', 'chart': 'dashboard-failure-chart', 'ring': False},
    ]
    # 这一页的折线图不再显示图例，信息由图表悬停提示和卡片文字承担。
    assert driver.execute_script(
        "return document.querySelectorAll('#performance-metrics .chart-legend').length") == 0
    # CPU/内存/磁盘/网络图固定 120 点容量，收发消息与失败事件图沿用统计模块的 60 点容量；数据不足时左侧补零。
    assert chart_contract(driver, '#dashboard-cpu-chart') == {
        'capacity': 120, 'seriesCount': 1, 'pointCounts': [120]}
    assert chart_contract(driver, '#dashboard-memory-chart') == {
        'capacity': 120, 'seriesCount': 1, 'pointCounts': [120]}
    # 内存图只绘制占用率；换入/换出改由性能页图表展示。
    assert driver.execute_script("""
        return [...document.querySelectorAll('#dashboard-memory-chart .chart-series')]
          .map((series) => series.dataset.series);
    """) == ['chart-series-memory']
    # 比例类图表保持线性，磁盘 IO、网络使用对数标尺；收发消息和失败事件使用线性标尺。
    assert driver.execute_script("""
        return ['#dashboard-cpu-chart', '#dashboard-memory-chart', '#dashboard-disk-chart',
          '#dashboard-network-chart', '#dashboard-traffic-chart',
          '#dashboard-failure-chart'].map(
          (selector) => document.querySelector(selector).querySelector('svg').dataset.scale);
    """) == ['linear', 'linear', 'log', 'log', 'linear', 'linear']
    assert chart_contract(driver, '#dashboard-disk-chart') == {
        'capacity': 120, 'seriesCount': 2, 'pointCounts': [120, 120]}
    # 磁盘折线图必须绘制读取/写入速率，而不是磁盘占用率。
    assert driver.execute_script("""
        return [...document.querySelectorAll('#dashboard-disk-chart .chart-series')]
          .map((series) => series.dataset.series);
    """) == ['chart-series-disk-read', 'chart-series-disk-write']
    assert chart_contract(driver, '#dashboard-network-chart') == {
        'capacity': 120, 'seriesCount': 2, 'pointCounts': [120, 120]}
    assert chart_contract(driver, '#dashboard-traffic-chart') == {
        'capacity': 60, 'seriesCount': 2, 'pointCounts': [60, 60]}
    assert chart_contract(driver, '#dashboard-failure-chart') == {
        'capacity': 60, 'seriesCount': 1, 'pointCounts': [60]}
    # 环形图绝对定位在折线图左侧，与图表区域重叠但保留原有百分比显示。
    assert driver.execute_script("""
        const card = [...document.querySelectorAll('#performance-metrics .metric-card')]
          .find((node) => node.querySelector('.metric-label').textContent === 'CPU');
        const ring = card.querySelector('.metric-ring');
        const chart = card.querySelector('.metric-card-chart');
        const ringRect = ring.getBoundingClientRect();
        const chartRect = chart.getBoundingClientRect();
        return getComputedStyle(ring).position === 'absolute' &&
          Math.abs(ringRect.left - chartRect.left) <= 1 &&
          ringRect.right > chartRect.left &&
          ringRect.bottom > chartRect.top &&
          ringRect.top < chartRect.bottom;
    """)
    # 六张卡片图都使用渐变面积填充，性能页仍保持无面积的独立图表。
    assert driver.execute_script("""
        return ['#dashboard-cpu-chart', '#dashboard-memory-chart', '#dashboard-disk-chart',
          '#dashboard-network-chart', '#dashboard-traffic-chart',
          '#dashboard-failure-chart'].map((selector) => {
          const chart = document.querySelector(selector);
          const areas = [...chart.querySelectorAll('.chart-area')];
          return [areas.length, areas.every(
            (area) => area.getAttribute('fill').startsWith('url(#'))];
        });
    """) == [[1, True], [1, True], [2, True], [2, True], [2, True], [1, True]]
    assert driver.execute_script(
        "return document.querySelector('#dashboard-cpu-chart .chart-series-cpu')"
        ".getAttribute('points').split(' ')[0].endsWith(',38.00')")
    network_tip = hover_chart(driver, '#dashboard-network-chart', 0.999)
    assert network_tip['hidden'] is False and network_tip['cursorVisible'] is True
    assert '网络下行' in network_tip['text'] and '8.0 KiB/s' in network_tip['text']
    assert '网络上行' in network_tip['text'] and '4.0 KiB/s' in network_tip['text']
    disk_tip = hover_chart(driver, '#dashboard-disk-chart', 0.999)
    assert '读取' in disk_tip['text'] and '1.0 KiB/s' in disk_tip['text']
    assert '写入' in disk_tip['text'] and '2.0 KiB/s' in disk_tip['text']
    memory_tip = hover_chart(driver, '#dashboard-memory-chart', 0.999)
    assert '内存使用率' in memory_tip['text'] and '37.5%' in memory_tip['text']
    assert '换入' not in memory_tip['text'] and '换出' not in memory_tip['text']
    # 收发消息和失败事件的悬停值直接使用桶内实际条数，不再换算成条/分钟。
    traffic_tip = hover_chart(driver, '#dashboard-traffic-chart', 0.999)
    assert '收' in traffic_tip['text'] and '8 条' in traffic_tip['text']
    assert '发' in traffic_tip['text'] and '3 条' in traffic_tip['text']
    failure_tip = hover_chart(driver, '#dashboard-failure-chart', 0.999)
    assert '失败' in failure_tip['text'] and '1 条' in failure_tip['text']

    # 悬停提示高于图表时必须能溢出显示，不能被子卡片裁掉底部。
    # 内存图现在只绘制一条序列，临时补足提示行以稳定覆盖超高场景。
    tooltip_overflow = driver.execute_script("""
        const chart = document.querySelector('#dashboard-memory-chart');
        const tooltip = chart.querySelector('.chart-tooltip');
        const rows = [...tooltip.querySelectorAll('.chart-tooltip-row')];
        const extraRows = [];
        for (let index = 0; index < 4; index += 1) {
          const row = rows[index % rows.length].cloneNode(true);
          tooltip.append(row);
          extraRows.push(row);
        }
        const result = {
          overflow: getComputedStyle(chart).overflow,
          tooltipBottom: tooltip.getBoundingClientRect().bottom,
          chartBottom: chart.getBoundingClientRect().bottom,
        };
        extraRows.forEach((row) => row.remove());
        return result;
    """)
    assert tooltip_overflow['overflow'] == 'visible'
    assert tooltip_overflow['tooltipBottom'] > tooltip_overflow['chartBottom']
    padding_tip = hover_chart(driver, '#dashboard-network-chart', 0.0)
    assert padding_tip['hidden'] is False
    assert '暂无历史采样' in padding_tip['text']
    # 百分比越界与非法值只能在环图边界内收敛，不能生成负数或超出整圈的进度。
    clamped = driver.execute_script("""
        const high = ringMetricCard('High', 150, '', 'cpu');
        const low = ringMetricCard('Low', 'invalid', '', 'cpu');
        return [high, low].map((card) => [
          card.querySelector('.metric-value').textContent,
          card.querySelector('.metric-ring-progress').getAttribute('stroke-dashoffset'),
        ]);
    """)
    assert clamped == [['100.0%', '0'], ['0.0%', '100']]

    # 修改快照后主动刷新，确认轮询会把累计值更新到现有卡片，而不是重复堆叠。
    counts['inbound'] = 140
    counts['inbound_per_minute'] = 6.0
    counts['cpu'] = 46.0
    counts['memory'] = 51.0
    counts['disk'] = 72.0
    driver.execute_async_script("""
        const done = arguments[0];
        refreshStatus().then(() => done(true), (error) => done(String(error)));
    """)
    traffic_text = metric_card_text(driver, '收发消息')
    assert '↓ 6 条/分钟 · ↑ 3 条/分钟' in traffic_text
    assert '累计 收 140 · 发 45' in traffic_text
    assert driver.execute_script("return document.querySelectorAll('.metric-card').length") == 6
    assert driver.execute_script("return document.querySelectorAll('.metric-card-chart').length") == 6
    updated = driver.execute_script("""
        return [...document.querySelectorAll('.metric-ring-card .metric-value')]
          .map((node) => node.textContent);
    """)
    assert updated == ['46.0%', '51.0%', '72.0%']

    # 宽屏 3 列，中等宽度 2 列，窄屏 1 列。
    def metric_rows(selector):
        return driver.execute_script("""
            const tops = [...document.querySelectorAll(arguments[0])].map(
              (card) => Math.round(card.getBoundingClientRect().top));
            const rows = [];
            for (const top of tops) {
              if (!rows.length || rows[rows.length - 1].top !== top) rows.push({top, count: 0});
              rows[rows.length - 1].count += 1;
            }
            return rows.map((row) => row.count);
        """, selector)

    assert metric_rows('#performance-metrics .metric-card') == [3, 3]

    # 所有卡片应保持等高，避免不同行因小字换行而高低不齐。
    assert driver.execute_script("""
        const heights = [...document.querySelectorAll('#performance-metrics .metric-card')]
          .map((card) => Math.round(card.getBoundingClientRect().height));
        return new Set(heights).size;
    """) == 1

    # 折线图和环形图保持与调整前相近的高度，避免卡片被撑得过高。
    visual = driver.execute_script("""
        const card = [...document.querySelectorAll('#performance-metrics .metric-card')]
          .find((node) => node.querySelector('.metric-label').textContent === 'CPU');
        const chart = card.querySelector('.metric-card-chart').getBoundingClientRect();
        const ring = card.querySelector('.metric-ring').getBoundingClientRect();
        return {chart: chart.height, ringWidth: ring.width, ringHeight: ring.height};
    """)
    assert 74 <= visual['chart'] <= 84
    assert 64 <= visual['ringWidth'] <= 74
    assert abs(visual['ringWidth'] - visual['ringHeight']) <= 1

    set_viewport(browser, 900, 720, mobile_device=True)
    panel_tops = driver.execute_script("""
        return [...document.querySelectorAll('.dashboard-panel')].map(
          (panel) => Math.round(panel.getBoundingClientRect().top));
    """)
    assert len(panel_tops) == 1

    assert metric_rows('#performance-metrics .metric-card') == [2, 2, 2]

    # 两列布局下环形卡与普通卡同排，折线图底边必须对齐。
    chart_bottoms = driver.execute_script("""
        const cards = [...document.querySelectorAll('#performance-metrics .metric-card')];
        const find = (label) => cards.find(
          (node) => node.querySelector('.metric-label').textContent === label);
        return ['磁盘', '网络'].map((label) => Math.round(
          find(label).querySelector('.metric-card-chart').getBoundingClientRect().bottom));
    """)
    assert abs(chart_bottoms[0] - chart_bottoms[1]) <= 1

    # 窄屏降到单列，同时避免水平滚动、图表越界并保持卡片对比度。
    set_viewport(browser, 390, 640, mobile_device=True)
    assert metric_rows('#performance-metrics .metric-card') == [1, 1, 1, 1, 1, 1]

    set_viewport(browser, 320, 640, mobile_device=True)
    browser.wait.until(lambda _: driver.execute_script(
        "return document.documentElement.scrollWidth <= innerWidth"))
    assert metric_rows('#performance-metrics .metric-card') == [1, 1, 1, 1, 1, 1]
    chart_cards_fit = driver.execute_script("""
        return [...document.querySelectorAll('.metric-chart-card')].every((card) => {
          const chart = card.querySelector('.metric-card-chart').getBoundingClientRect();
          const box = card.getBoundingClientRect();
          return chart.left >= box.left && chart.right <= box.right;
        });
    """)
    assert chart_cards_fit
    contrasts = driver.execute_script("""
        function channels(color) {
          return (color.match(/[\\d.]+/g) || []).slice(0, 3).map(Number);
        }
        function luminance(color) {
          const values = channels(color).map((value) => {
            value /= 255;
            return value <= 0.03928 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
          });
          return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
        }
        function contrast(theme) {
          document.documentElement.dataset.theme = theme;
          const card = document.querySelector('.metric-card');
          const value = card.querySelector('.metric-value');
          const first = luminance(getComputedStyle(card).backgroundColor);
          const second = luminance(getComputedStyle(value).color);
          return (Math.max(first, second) + 0.05) / (Math.min(first, second) + 0.05);
        }
        return {light: contrast('light'), dark: contrast('dark')};
    """)
    assert contrasts['light'] >= 7
    assert contrasts['dark'] >= 7
    assert driver.execute_script("return document.documentElement.scrollWidth <= innerWidth")

    # 移动端必须按工具栏、更新通知、运行时长、性能标题、收发消息卡片依次纵向排列。
    tops = driver.execute_script("""
        const trafficCard = [...document.querySelectorAll('#performance-metrics .metric-card')]
          .find((card) => card.querySelector('.metric-label').textContent === '收发消息');
        const selectors = [
          '#dashboard .runtime-summary .toolbar',
          '#update-status',
          '#runtime',
          '#performance-title',
        ];
        const tops = selectors.map((selector) => Math.round(
          document.querySelector(selector).getBoundingClientRect().top));
        tops.push(Math.round(trafficCard.getBoundingClientRect().top));
        return tops;
    """)
    assert all(later > earlier for earlier, later in zip(tops, tops[1:])), tops
    # 检查更新工具栏与新版本通知都位于运行状态分割线之上。
    divider_layout = driver.execute_script("""
        const toolbar = document.querySelector('#dashboard .runtime-summary .toolbar');
        const update = document.getElementById('update-status');
        const divider = document.getElementById('runtime-details');
        const dividerTop = divider.getBoundingClientRect().top;
        return {
          toolbarAbove: toolbar.getBoundingClientRect().bottom <= dividerTop + 1,
          updateAbove: update.getBoundingClientRect().bottom <= dividerTop + 1,
          hasBorder: parseFloat(getComputedStyle(divider).borderTopWidth) > 0,
        };
    """)
    assert divider_layout == {'toolbarAbove': True, 'updateAbove': True, 'hasBorder': True}
    # 仪表盘只能通过 /api/status 获取统计，不能再请求旧路由。
    assert not driver.execute_script("""
        return performance.getEntriesByType('resource')
          .some((entry) => entry.name.includes('/api/statistics'));
    """)


@pytest.mark.browser
def test_performance_page_renders_category_navigation_and_mobile_layout(browser):
    from selenium.webdriver.common.action_chains import ActionChains

    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return state.page === 'performance' && !document.getElementById('performance-content').hidden"))
    assert browser.find('#page-title').text == '性能'
    assert browser.find('[data-page="performance"]').get_attribute('aria-current') == 'page'
    time.sleep(0.2)
    # 性能分类复用主页面导航的选中态：主题背景、主色边框与左侧强调条应与导航基准一致。
    assert driver.execute_script("""
        const navigation = getComputedStyle(
          document.querySelector('#navigation [data-page="performance"]'));
        const performanceCategory = getComputedStyle(
          document.querySelector('[data-performance-category="overview"]'));
        return {
          background: performanceCategory.backgroundColor === navigation.backgroundColor,
          border: performanceCategory.borderColor === navigation.borderColor,
          shadow: performanceCategory.boxShadow === navigation.boxShadow,
        };
    """) == {'background': True, 'border': True, 'shadow': True}
    navigation_button = browser.find('#navigation [data-page="performance"]')
    category_button = browser.find('[data-performance-category="overview"]')
    pressed_script = """
        const style = getComputedStyle(arguments[0]);
        return {
          background: style.backgroundColor,
          border: style.borderColor,
          shadow: style.boxShadow,
          outline: style.outline,
        };
    """
    ActionChains(driver).click_and_hold(navigation_button).perform()
    time.sleep(0.2)
    navigation_pressed = driver.execute_script(pressed_script, navigation_button)
    ActionChains(driver).release(navigation_button).perform()
    time.sleep(0.05)
    ActionChains(driver).click_and_hold(category_button).perform()
    time.sleep(0.2)
    category_pressed = driver.execute_script(pressed_script, category_button)
    ActionChains(driver).release(category_button).perform()
    assert category_pressed == navigation_pressed
    assert driver.execute_script("""
        return ['performance-cpu-chart-title', 'performance-memory-chart-title',
          'performance-disk-usage-chart-title', 'performance-network-chart-title',
          'performance-load-chart-title', 'performance-traffic-chart-title'].map(
          (id) => document.getElementById(id).textContent);
    """) == ['CPU', '内存', '磁盘', '网络', 'OlivOS 负载', '消息']
    # CPU 详情默认隐藏在概览之后，读取 textContent 以校验已渲染内容。
    assert '负载 1.25' in browser.find('#performance-cpu-readout').get_attribute('textContent')
    assert 'OlivOS 负载 0.13 核心' in browser.find('#performance-load-readout').get_attribute(
        'textContent')
    assert browser.find('[data-performance-stat="cpu-machine-load"]').get_attribute(
        'textContent') == '1.25 / 1.00 / 0.80'
    assert browser.find('[data-performance-stat="cpu-load"]').get_attribute(
        'textContent') == '0.13 核心'
    assert browser.find('[data-performance-stat="cpu-model"]').get_attribute(
        'textContent') == 'Test CPU 9000'
    assert '正在读取监测数据' not in browser.find('#performance-statistics-note').text
    assert browser.find('[data-performance-stat="system-cpu-model"]').text == 'Test CPU 9000'
    assert browser.find('[data-performance-stat="system-os"]').text == 'Windows'
    assert browser.find('[data-performance-stat="system-python-version"]').text == '3.11.9'
    assert browser.find('[data-performance-stat="system-memory-total"]').text == '16.0 GiB'
    assert 'Windows 11' in browser.find('#performance-overview-readout').text

    # 左侧分类导航按任务管理器风格排列，默认选中概览，性能类目显示小型趋势图。
    category_state = driver.execute_script("""
        return [...document.querySelectorAll('#performance-content .performance-category')]
          .map((node) => ({
            key: node.dataset.performanceCategory,
            selected: node.getAttribute('aria-selected'),
            mini: Boolean(node.querySelector('[data-performance-mini] .mini-line')),
          }));
    """)
    assert [item['key'] for item in category_state] == [
        'overview', 'cpu', 'memory', 'disk', 'network', 'traffic', 'processes',
    ]
    assert category_state[0]['selected'] == 'true'
    assert not category_state[0]['mini']
    assert all(item['mini'] for item in category_state[1:])
    # CPU、内存、磁盘迷你趋势图固定使用 0-100 标度，稳定值不应贴顶。
    percentage_minis = driver.execute_script(r'''
        return ['cpu', 'memory', 'disk'].map((key) => {
          const svg = document.querySelector('[data-performance-mini=' + key + '] svg');
          const points = svg.querySelector('.mini-line').getAttribute('points')
            .trim().split(/\s+/);
          return {
            maximum: Number(svg.dataset.maximum),
            y: Number(points[points.length - 1].split(',')[1]),
          };
        });
    ''')
    assert [item['maximum'] for item in percentage_minis] == [100, 100, 100]
    assert all(item['y'] > 10 for item in percentage_minis)
    network_summary = driver.execute_script(
        "return document.querySelector('[data-performance-summary=\"network\"]').textContent")
    assert '↓ 8.0 KiB/s' in network_summary
    assert '↑' not in network_summary
    network_value = driver.execute_script(
        "return document.getElementById('performance-network-value').textContent")
    assert '↓ 8.0 KiB/s' in network_value
    assert '↑ 4.0 KiB/s' in network_value
    traffic_summary = driver.execute_script(
        "return document.querySelector('[data-performance-summary=\"traffic\"]').textContent")
    assert '↓ 5' in traffic_summary
    assert '↑ 3' in traffic_summary
    assert '条/分钟' not in traffic_summary
    assert driver.execute_script("""
        const list = document.querySelector('.performance-categories');
        const detail = document.querySelector('.performance-detail');
        return getComputedStyle(document.getElementById('performance-content')).display === 'grid' &&
          list.getBoundingClientRect().right <= detail.getBoundingClientRect().left;
    """)
    assert driver.execute_script("""
        return [...document.querySelectorAll('[data-performance-view]')]
          .filter((view) => !view.hidden).map((view) => view.dataset.performanceView);
    """) == ['overview']

    # 进程标签按需读取进程树，显示父子进程与每个进程下的线程。
    browser.click('[data-performance-category="processes"]')
    browser.wait.until(lambda _: driver.execute_script("""
        return !document.getElementById('performance-view-processes').hidden &&
          document.querySelectorAll('#performance-process-tree .process-node').length === 2;
    """))
    assert '2 个进程' in browser.find('#performance-processes-readout').text
    assert '3 个线程' in browser.find('#performance-processes-readout').text
    process_summary = browser.find('#performance-view-processes .performance-view-value').text
    assert process_summary.startswith('3 ')
    assert len(process_summary.split()) == 8
    assert ' 18 ' in process_summary
    assert ' 400 ' in process_summary
    assert driver.execute_script("""
        return {
          rootBadge: document.querySelector('.process-root-badge').textContent,
          threads: document.querySelectorAll('#performance-process-tree .process-thread').length,
          children: document.querySelectorAll('#performance-process-tree .process-children .process-node').length,
        };
    """) == {'rootBadge': 'OlivOS 主进程', 'threads': 3, 'children': 1}
    process_row_text = driver.execute_script(
        "return document.querySelector('#performance-process-tree .process-row').textContent")
    assert '句柄 100' in process_row_text
    assert '文件描述符 42' in process_row_text
    process_facts = driver.execute_script(
        "return document.querySelector('.process-facts').textContent")
    assert '虚拟内存' in process_facts
    assert '256.0 MiB' in process_facts
    assert 'CPU 亲和性' in process_facts
    assert '0-3（4）' in process_facts
    assert '读 10.0 KiB（10 次）' in process_facts
    assert '写 20.0 KiB（20 次）' in process_facts
    process_commands = driver.execute_script("""
        return [...document.querySelectorAll('.process-command')]
          .map((node) => node.textContent).join('\\n');
    """)
    assert 'C:/OlivOS/python.exe' in process_commands
    assert 'main.py' in process_commands
    first_thread = driver.execute_script(
        "return document.querySelector('#performance-process-tree .process-thread').textContent")
    assert 'main' in first_thread
    assert 'MainThread' in first_thread
    assert '睡眠' in first_thread
    assert 'CPU 50.0%' in first_thread
    assert 'Nice 0' in first_thread
    assert '等待 futex_wait_queue_me' in first_thread
    assert '启动 ' in first_thread
    assert '起始 python311.dll+0x4A2C' in first_thread

    # 线程行悬停时整行高亮，便于在长线程列表中横向对齐各列字段。
    driver.execute_script(
        "document.querySelector('#performance-process-tree .process-thread')"
        ".scrollIntoView({block: 'center'});")
    ActionChains(driver).move_to_element(
        browser.find('#performance-process-tree .process-thread')).perform()
    browser.wait.until(lambda _: driver.execute_script("""
        const row = document.querySelector('#performance-process-tree .process-thread');
        const background = getComputedStyle(row).backgroundColor;
        return background !== 'rgba(0, 0, 0, 0)' && background !== 'transparent';
    """))

    # 文件、连接与内存详情只在用户点击后按需请求，并限制展示条目数。
    browser.click('#performance-process-tree .process-detail-button')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.querySelector('.process-detail-summary') !== null"))
    detail_text = driver.execute_script(
        "return document.querySelector('.process-detail').textContent")
    assert '打开文件 2' in detail_text
    assert '网络连接 1' in detail_text
    assert '内存映射 1' in detail_text
    assert 'C:/OlivOS/logfile/a.log' in detail_text
    assert '127.0.0.1:8080' in detail_text
    assert 'ntdll.dll' in detail_text
    assert '独占' in detail_text

    # 收起进程节点并展开详情分组后刷新，展开状态必须保留。
    driver.execute_async_script("""
        const done = arguments[0];
        const branch = document.querySelector('[data-process-branch]');
        branch.dataset.refreshMarker = 'old';
        branch.open = false;
        document.querySelector('[data-process-detail-group="files"]').open = true;
        setTimeout(done, 0);
    """)
    browser.click('#performance-processes-refresh')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.querySelector('[data-process-branch]').dataset.refreshMarker"))
    assert driver.execute_script("""
        return {
          branchOpen: document.querySelector('[data-process-branch]').open,
          filesOpen: document.querySelector('[data-process-detail-group="files"]').open,
          connectionsOpen: document.querySelector('[data-process-detail-group="connections"]').open,
        };
    """) == {'branchOpen': False, 'filesOpen': True, 'connectionsOpen': False}
    browser.click('[data-performance-category="cpu"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.getElementById('performance-view-cpu').hidden"))

    # 换出与 Swap 使用率使用不同颜色，且折线与图例颜色保持一致。
    swap_colors = driver.execute_script("""
        const chart = document.querySelector('#performance-memory-chart');
        return [
          getComputedStyle(chart.querySelector('.chart-series-swap')).stroke,
          getComputedStyle(chart.querySelector('.chart-series-swap-out')).stroke,
          getComputedStyle(document.querySelector('#performance-view-memory .legend-swap')).color,
          getComputedStyle(document.querySelector('#performance-view-memory .legend-swap-out')).color,
        ];
    """)
    assert swap_colors[0] != swap_colors[1]
    assert swap_colors[2] != swap_colors[3]
    assert swap_colors[0] == swap_colors[2] and swap_colors[1] == swap_colors[3]

    # 切换左侧分类后，右侧只展示对应详情，悬停提示使用该分类的图表。
    tooltip_cases = {
        'cpu': [
            ('#performance-cpu-chart', ['CPU 使用率', '43.0%', '负载', '43.00']),
            ('#performance-load-chart', ['OlivOS 负载', '0.43 核心']),
        ],
        'memory': [
            ('#performance-memory-chart',
             ['内存使用率', '43.0%', 'Swap 使用率', '43.0%', '换入', '43 B/s', '换出', '43 B/s']),
            ('#performance-process-memory-chart', ['OlivOS 进程内存', '43 B']),
        ],
        'disk': [
            ('#performance-disk-usage-chart', ['磁盘占用率', '43.0%']),
            ('#performance-disk-io-chart', ['读取', '43 B/s', '写入', '43 B/s']),
        ],
        'network': [
            ('#performance-network-chart', ['网络下行', '43 B/s', '网络上行', '43 B/s']),
        ],
        'traffic': [
            ('#performance-traffic-chart', ['12 条', '15 条']),
            ('#performance-failure-chart', ['失败事件', '0 条']),
        ],
    }
    for category, cases in tooltip_cases.items():
        browser.click(f'[data-performance-category="{category}"]')
        browser.wait.until(lambda _: driver.execute_script(
            "return !document.querySelector('[data-performance-view=\"' + arguments[0] + '\"]').hidden",
            category))
        assert driver.execute_script(
            "return [...document.querySelectorAll('[data-performance-view]')]"
            ".filter((view) => !view.hidden).map((view) => view.dataset.performanceView)",
        ) == [category]
        assert driver.execute_script(
            "return document.querySelector('[data-performance-category=\"' + arguments[0] + '\"]')"
            ".getAttribute('aria-selected')", category) == 'true'
        for selector, fragments in cases:
            tooltip = hover_chart(driver, selector, 0.999)
            assert tooltip['hidden'] is False, (category, selector)
            for fragment in fragments:
                assert fragment in tooltip['text'], (category, selector, fragment, tooltip['text'])
    browser.click('[data-performance-category="cpu"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.getElementById('performance-view-cpu').hidden"))
    # 采样不足时不能再留下左侧空白区；最左端也应命中真实采样点。
    left_tooltip = hover_chart(driver, '#performance-cpu-chart', 0.0)['text']
    assert '暂无历史采样' not in left_tooltip
    assert 'CPU 使用率' in left_tooltip

    # 刷新快照时只更新现有节点；线程缺失显示破折号，句柄缺失时不展示，文件描述符按可用性展示。
    updated = statistics_snapshot(cpu_percent=55.0, process_threads=None,
                                  process_handles=None, process_num_fds=42)
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=lambda: updated)
    driver.execute_async_script("""
        const done = arguments[0];
        refreshStatus().then(() => done(true), (error) => done(String(error)));
    """)
    assert '55.0%' in browser.find('#performance-cpu-readout').text
    browser.click('[data-performance-category="memory"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.getElementById('performance-view-memory').hidden"))
    assert '— 线程' in browser.find('#performance-process-memory-readout').text
    assert '句柄' not in browser.find('#performance-process-memory-readout').text
    assert '42 文件描述符' in browser.find('#performance-process-memory-readout').text
    assert driver.execute_script(
        "return document.getElementById('performance-fact-handles').hidden")
    assert driver.execute_script(
        "return document.querySelectorAll('#performance-content .performance-panel').length") == 15

    # 所有事实网格需按当前列数补齐占位项，末行空槽应与普通事实单元格同色。
    set_viewport(browser, 1280, 800)
    fact_layout = driver.execute_script("""
        return ['overview', 'cpu', 'memory', 'disk', 'network', 'traffic'].map((category) => {
          const grid = document.querySelector(
            `#performance-view-${category} .performance-fact-grid`);
          const template = getComputedStyle(grid).gridTemplateColumns;
          const repeated = template.match(/^repeat\\((\\d+),/);
          const facts = [...grid.children].filter(
            (node) => node.classList.contains('performance-fact'));
          const fillers = facts.filter(
            (node) => node.classList.contains('performance-fact-empty'));
          return {
            category,
            count: facts.length - fillers.length,
            rendered: facts.length,
            columns: repeated ? Number(repeated[1]) : template.split(' ').filter(Boolean).length,
            factBackground: getComputedStyle(facts[0]).backgroundColor,
            fillerBackground: fillers.length
              ? getComputedStyle(fillers[0]).backgroundColor
              : null,
          };
        });
    """)
    expected_counts = {
        'overview': 6, 'cpu': 9, 'memory': 13, 'disk': 10, 'network': 8, 'traffic': 8,
    }
    for item in fact_layout:
        assert item['count'] == expected_counts[item['category']]
        assert item['columns'] == 3
        assert item['rendered'] % item['columns'] == 0
        assert item['fillerBackground'] in (None, item['factBackground'])
    set_viewport(browser, 900, 800)
    browser.wait.until(lambda _: driver.execute_script("""
        return ['overview', 'cpu', 'memory', 'disk', 'network', 'traffic'].every((category) => {
          const grid = document.querySelector(
            `#performance-view-${category} .performance-fact-grid`);
          const template = getComputedStyle(grid).gridTemplateColumns;
          const repeated = template.match(/^repeat\\((\\d+),/);
          const columns = repeated ? Number(repeated[1]) : template.split(' ').filter(Boolean).length;
          return columns === 2 && grid.children.length % 2 === 0;
        });
    """))
    narrow_fact_layout = driver.execute_script("""
        return ['overview', 'cpu', 'memory', 'disk', 'network', 'traffic'].map((category) => {
          const grid = document.querySelector(
            `#performance-view-${category} .performance-fact-grid`);
          const template = getComputedStyle(grid).gridTemplateColumns;
          const repeated = template.match(/^repeat\\((\\d+),/);
          const facts = [...grid.children].filter(
            (node) => node.classList.contains('performance-fact'));
          const fillers = facts.filter(
            (node) => node.classList.contains('performance-fact-empty'));
          return {
            category,
            rendered: facts.length,
            columns: repeated ? Number(repeated[1]) : template.split(' ').filter(Boolean).length,
            factBackground: getComputedStyle(facts[0]).backgroundColor,
            fillerBackground: fillers.length
              ? getComputedStyle(fillers[0]).backgroundColor
              : null,
          };
        });
    """)
    for item in narrow_fact_layout:
        assert item['columns'] == 2
        assert item['rendered'] % item['columns'] == 0
        assert item['fillerBackground'] in (None, item['factBackground'])

    # 桌面端左右两栏各自滚动，内容不足时不应占出滚动条。
    set_viewport(browser, 1280, 420)
    scroll_layout = driver.execute_script("""
        const categories = document.querySelector('.performance-categories');
        const detail = document.querySelector('.performance-detail');
        const main = document.querySelector('main');
        categories.scrollTop = categories.scrollHeight;
        detail.scrollTop = 0;
        return {
          categoriesOverflow: getComputedStyle(categories).overflowY,
          detailOverflow: getComputedStyle(detail).overflowY,
          categoriesScrollTop: categories.scrollTop,
          detailScrollTop: detail.scrollTop,
          sameHeight: Math.abs(categories.offsetHeight - detail.offsetHeight) <= 1,
          mainFits: main.scrollHeight <= main.clientHeight + 1,
          bottomGap: Math.round(innerHeight -
            document.getElementById('performance-content').getBoundingClientRect().bottom),
          mainPaddingBottom: Math.round(parseFloat(getComputedStyle(main).paddingBottom)),
        };
    """)
    assert scroll_layout['categoriesOverflow'] == 'auto'
    assert scroll_layout['detailOverflow'] == 'auto'
    assert scroll_layout['categoriesScrollTop'] > 0
    assert scroll_layout['detailScrollTop'] == 0
    assert scroll_layout['sameHeight']
    assert scroll_layout['mainFits']
    assert scroll_layout['bottomGap'] == scroll_layout['mainPaddingBottom']
    detail_scroll = driver.execute_script("""
        const categories = document.querySelector('.performance-categories');
        const detail = document.querySelector('.performance-detail');
        categories.scrollTop = 0;
        detail.scrollTop = detail.scrollHeight;
        return {categories: categories.scrollTop, detail: detail.scrollTop};
    """)
    assert detail_scroll['categories'] == 0
    assert detail_scroll['detail'] > 0

    set_viewport(browser, 1400, 1280)
    assert driver.execute_script("""
        const categories = document.querySelector('.performance-categories');
        const detail = document.querySelector('.performance-detail');
        return categories.scrollHeight <= categories.clientHeight &&
          detail.scrollHeight <= detail.clientHeight;
    """)

    # 移动端分类导航改用抽屉，右侧详情单列显示且所有分类都不撑出视口。
    set_viewport(browser, 390, 844, mobile_device=True)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.getElementById('shell').dataset.sidebarOpen === 'false'"))

    set_viewport(browser, 320, 640, mobile_device=True)
    browser.wait.until(lambda _: driver.execute_script(
        "return document.documentElement.scrollWidth <= innerWidth"))
    assert driver.execute_script("""
        const drawer = document.querySelector('.performance-nav-drawer');
        const toggle = document.getElementById('performance-nav-toggle');
        return getComputedStyle(drawer).position === 'fixed' &&
          getComputedStyle(drawer).visibility === 'hidden' &&
          getComputedStyle(document.querySelector('.performance-categories')).flexDirection === 'column' &&
          toggle.getAttribute('aria-expanded') === 'false';
    """)
    for category in ('overview', 'cpu', 'memory', 'disk', 'network', 'traffic'):
        browser.click('#performance-nav-toggle')
        browser.wait.until(lambda _: driver.execute_script(
            "return document.body.classList.contains('performance-nav-open') && "
            "document.getElementById('performance-nav-toggle').getAttribute('aria-expanded') === 'true'"))
        browser.click(f'[data-performance-category="{category}"]')
        browser.wait.until(lambda _: driver.execute_script(
            "return !document.body.classList.contains('performance-nav-open') && "
            "!document.querySelector('[data-performance-view=\"' + arguments[0] + '\"]').hidden",
            category))
        assert driver.execute_script("""
            const view = [...document.querySelectorAll('[data-performance-view]')]
              .find((node) => !node.hidden);
            return [...view.querySelectorAll('.performance-panel')].every((panel) => (
              panel.getBoundingClientRect().right <= document.documentElement.clientWidth + 1
            )) && document.documentElement.scrollWidth <= innerWidth;
        """)

    # 数据刷新只更新抽屉内容，不能把用户正在浏览的滚动位置拉回当前分类。
    set_viewport(browser, 320, 360, mobile_device=True)
    browser.click('#performance-nav-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.body.classList.contains('performance-nav-open')"))
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=lambda: statistics_snapshot(cpu_percent=33.0),
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    scroll_before_refresh = driver.execute_script("""
        const bar = document.querySelector('.performance-categories');
        bar.scrollTop = bar.scrollHeight;
        return bar.scrollTop;
    """)
    driver.execute_async_script("""
        const done = arguments[arguments.length - 1];
        refreshStatus().then(() => done(true), (error) => done(String(error)));
    """)
    scroll_after_refresh = driver.execute_script("""
        const bar = document.querySelector('.performance-categories');
        return {
          after: bar.scrollTop,
          open: state.performanceNavOpen,
        };
    """)
    assert scroll_before_refresh > 0
    assert scroll_after_refresh['after'] == scroll_before_refresh
    assert scroll_after_refresh['open']
    browser.click('#performance-nav-close')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.body.classList.contains('performance-nav-open')"))
    set_viewport(browser, 320, 640, mobile_device=True)

    # 进程页在移动端使用卡片、字段网格与分行线程，选择后抽屉应关闭并更新当前分类。
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=lambda: updated,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.click('#performance-nav-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.body.classList.contains('performance-nav-open')"))
    driver.execute_script(
        "document.querySelector('[data-performance-category=\"processes\"]').click()")
    browser.wait.until(lambda _: driver.execute_script("""
        return !document.body.classList.contains('performance-nav-open') &&
          !document.getElementById('performance-view-processes').hidden &&
          document.querySelectorAll('#performance-process-tree .process-row').length === 2;
    """))
    browser.wait.until(lambda _: driver.execute_script("""
        return document.getElementById('performance-nav-current').textContent.trim() == '进程';
    """))
    process_layout = driver.execute_script("""
        const row = document.querySelector('#performance-process-tree .process-row');
        const name = row.querySelector('.process-name');
        const pid = row.querySelector('.process-pid');
        const meta = row.querySelector('.process-meta');
        const thread = document.querySelector('#performance-process-tree .process-thread');
        const threadId = thread.querySelector('.process-thread-id');
        const threadMeta = thread.querySelector('.process-thread-cpu');
        const facts = row.closest('.process-branch').querySelector('.process-facts');
        const refresh = document.getElementById('performance-processes-refresh');
        const heading = document.querySelector('.performance-view-heading-processes');
        const headingValue = document.querySelector('.performance-view-value-processes');
        const drawer = document.querySelector('.performance-nav-drawer');
        return {
          rowDisplay: getComputedStyle(row).display,
          rowColumns: getComputedStyle(row).gridTemplateColumns.split(' ').filter(Boolean).length,
          pidBelowName: pid.getBoundingClientRect().top >= name.getBoundingClientRect().bottom,
          metaBelowName: meta.getBoundingClientRect().top >= name.getBoundingClientRect().bottom,
          threadDisplay: getComputedStyle(thread).display,
          threadMetaBelow: threadMeta.getBoundingClientRect().top >=
            threadId.getBoundingClientRect().bottom,
          factsDisplay: getComputedStyle(facts).display,
          factsColumns: getComputedStyle(facts).gridTemplateColumns.split(' ').filter(Boolean).length,
          refreshHeight: refresh.getBoundingClientRect().height,
          headingDisplay: getComputedStyle(heading).display,
          headingAlign: getComputedStyle(headingValue).textAlign,
          drawerPosition: getComputedStyle(drawer).position,
          fits: document.documentElement.scrollWidth <= innerWidth,
        };
    """)
    assert process_layout['rowDisplay'] == 'grid'
    assert process_layout['rowColumns'] == 3
    assert process_layout['pidBelowName']
    assert process_layout['metaBelowName']
    assert process_layout['threadDisplay'] == 'grid'
    assert process_layout['threadMetaBelow']
    assert process_layout['factsDisplay'] == 'grid'
    assert process_layout['factsColumns'] >= 2
    assert process_layout['refreshHeight'] >= 40
    assert process_layout['headingDisplay'] == 'grid'
    assert process_layout['headingAlign'] == 'left'
    assert process_layout['drawerPosition'] == 'fixed'
    assert process_layout['fits']


@pytest.mark.browser
def test_performance_charts_use_percentage_and_independent_series_scales(browser):
    # 图表缩放是独立行为：百分比图固定 100%，非百分比序列各自缩放，并按线性/对数标尺绘制。
    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return state.page === 'performance' && !document.getElementById('performance-content').hidden"))

    # 默认 1 分钟窗口下，前端点数必须与后端窗口数组长度一致，并保持固定容量。
    expected = {
        '#performance-cpu-chart': (60, 2),
        '#performance-memory-chart': (60, 4),
        '#performance-disk-usage-chart': (60, 1),
        '#performance-disk-io-chart': (60, 2),
        '#performance-network-chart': (60, 2),
        '#performance-load-chart': (60, 1),
        '#performance-process-memory-chart': (60, 1),
        '#performance-traffic-chart': (12, 2),
        '#performance-failure-chart': (12, 1),
    }
    for selector, (capacity, series_count) in expected.items():
        actual = chart_contract(driver, selector)
        assert actual['capacity'] == capacity, selector
        assert actual['seriesCount'] == series_count, selector
        assert actual['pointCounts'] == [capacity] * series_count, selector

    # CPU、磁盘占用、流量与失败事件保持线性；内存、磁盘 IO、网络使用对数标尺。
    assert driver.execute_script("""
        return ['#performance-cpu-chart', '#performance-memory-chart',
          '#performance-disk-usage-chart', '#performance-disk-io-chart',
          '#performance-network-chart', '#performance-load-chart',
          '#performance-process-memory-chart', '#performance-traffic-chart',
          '#performance-failure-chart'].map(
          (selector) => document.querySelector(selector).querySelector('svg').dataset.scale);
    """) == ['linear', 'log', 'linear', 'log', 'log', 'linear', 'linear', 'linear', 'linear']

    # 百分比折线固定使用 100% 标度，实际坐标必须反映真实百分比而不是贴顶或压底。
    percentage_points = driver.execute_script(r'''
        return [
          ['#performance-cpu-chart', '.chart-series-cpu'],
          ['#performance-memory-chart', '.chart-series-memory'],
          ['#performance-memory-chart', '.chart-series-swap'],
          ['#performance-disk-usage-chart', '.chart-series-disk'],
        ].map(([chart, series]) => {
          const svg = document.querySelector(chart).querySelector('svg');
          const line = svg.querySelector(series);
          const points = line.getAttribute('points').trim().split(/\s+/);
          return {
            series: chart + ' ' + series,
            chartMaximum: Number(svg.dataset.maximum),
            seriesMaximum: Number(line.dataset.maximum),
            scale: line.dataset.scale,
            lastY: Number(points[points.length - 1].split(',')[1]),
          };
        });
    ''')
    assert all(item['chartMaximum'] == 100 for item in percentage_points)
    assert all(item['seriesMaximum'] == 100 for item in percentage_points)
    assert [item['scale'] for item in percentage_points] == ['linear', 'log', 'log', 'linear']
    by_series = {item['series']: item for item in percentage_points}
    cpu_percent = by_series['#performance-cpu-chart .chart-series-cpu']
    memory_percent = by_series['#performance-memory-chart .chart-series-memory']
    swap_percent = by_series['#performance-memory-chart .chart-series-swap']
    disk_percent = by_series['#performance-disk-usage-chart .chart-series-disk']
    assert abs(cpu_percent['lastY'] - 22.52) < 0.3
    assert abs(memory_percent['lastY'] - 8.48) < 0.4
    assert abs(swap_percent['lastY'] - 8.48) < 0.1
    assert abs(disk_percent['lastY'] - 22.52) < 0.1

    # 非百分比序列使用自身最大值：满值点应贴近图表顶部，而不是被整图 100% 标度压到底部。
    independent = driver.execute_script(r'''
        return [
          ['#performance-cpu-chart', '.chart-series-machine-load'],
          ['#performance-memory-chart', '.chart-series-swap-in'],
        ].map(([chart, series]) => {
          const line = document.querySelector(chart).querySelector(series);
          const points = line.getAttribute('points').trim().split(/\s+/);
          return {
            maximum: Number(line.dataset.maximum),
            lastY: Number(points[points.length - 1].split(',')[1]),
          };
        });
    ''')
    assert [item['maximum'] for item in independent] == [43, 43]
    assert all(abs(item['lastY'] - 2.0) < 0.1 for item in independent)

    # 刻线使用固定 0-100 参考量程：线性图等距，对数图非等距且不随数据最大值变化。
    grid_contracts = driver.execute_script("""
        return ['#performance-cpu-chart', '#performance-memory-chart',
          '#performance-disk-io-chart', '#performance-network-chart'].map((selector) => {
          const svg = document.querySelector(selector).querySelector('svg');
          const gridlines = [...svg.querySelectorAll('.chart-grid')];
          const ys = gridlines.map((line) => Number(line.getAttribute('y1')));
          const values = gridlines.map((line) => Number(line.dataset.gridValue));
          const gaps = ys.slice(1).map((value, index) => Math.abs(value - ys[index]));
          return {scale: svg.dataset.scale, maximum: Number(svg.dataset.maximum),
            count: ys.length, values, gaps};
        });
    """)
    assert grid_contracts[0]['scale'] == 'linear'
    assert grid_contracts[0]['count'] == 5
    assert grid_contracts[0]['values'] == [0, 25, 50, 75, 100]
    assert max(grid_contracts[0]['gaps']) - min(grid_contracts[0]['gaps']) < 0.01
    assert len({contract['maximum'] for contract in grid_contracts[1:]}) > 1
    reference_gaps = grid_contracts[1]['gaps']
    for contract in grid_contracts[1:]:
        assert contract['scale'] == 'log'
        assert contract['count'] == 5
        assert contract['values'] == [0, 25, 50, 75, 100]
        assert max(contract['gaps']) - min(contract['gaps']) > 1
        assert all(abs(left - right) < 0.01 for left, right in zip(reference_gaps, contract['gaps']))


@pytest.mark.browser
def test_performance_chart_series_fill_plot_width_in_every_window(browser):
    # 每个时间窗都应让现有采样铺满绘图区，并让首尾采样点贴住折线图左右边缘。
    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return state.page === 'performance' && !document.getElementById('performance-content').hidden"))

    selectors = [
        '#performance-cpu-chart', '#performance-memory-chart',
        '#performance-disk-usage-chart', '#performance-disk-io-chart',
        '#performance-network-chart', '#performance-load-chart',
        '#performance-process-memory-chart', '#performance-traffic-chart',
        '#performance-failure-chart',
    ]
    for window_key in ('1m', '5m', '15m', '1h', '6h', '24h'):
        browser.click(f'[data-performance-window="{window_key}"]')
        browser.wait.until(lambda _, key=window_key: driver.execute_script(
            'return state.performanceWindow === arguments[0]', key))
        contracts = driver.execute_script("""
            return arguments[0].map((selector) => {
              const svg = document.querySelector(selector).querySelector('svg');
              return {
                selector,
                capacity: Number(svg.dataset.capacity),
                samples: Number(svg.dataset.samples),
                series: [...svg.querySelectorAll('.chart-series')].map((line) => {
                  const xs = line.getAttribute('points').trim().split(/\\s+/)
                    .map((point) => Number(point.split(',')[0]));
                  return {count: xs.length, firstX: xs[0], lastX: xs[xs.length - 1]};
                }),
              };
            });
        """, selectors)
        for chart in contracts:
            assert chart['capacity'] >= 2, (window_key, chart['selector'])
            for item in chart['series']:
                assert chart['samples'] == chart['capacity'], (window_key, chart['selector'])
                assert item['count'] == chart['samples'], (window_key, chart['selector'])
                assert item['firstX'] == 0, (window_key, chart['selector'])
                assert item['lastX'] == 100, (window_key, chart['selector'])


@pytest.mark.browser
def test_performance_chart_points_follow_backend_window_shift(browser):
    # 前端点数必须等于后端窗口数组长度；窗口推进时，旧点应整体左移而不是被重新拉伸。
    driver = browser.driver
    snapshot = statistics_snapshot()
    window = snapshot['performance']['windows']['1m']
    capacity = window['capacity']
    window['cpu_percent'] = [0] * (capacity - 1) + [99.0]
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=lambda: snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page=performance]')
    browser.wait.until(lambda _: driver.execute_script(
        r'''return state.page === 'performance' && !document.getElementById('performance-content').hidden'''))

    def cpu_points():
        series = browser.find('#performance-cpu-chart .chart-series-cpu')
        text = driver.execute_script(r'''return arguments[0].getAttribute('points');''', series)
        return [tuple(map(float, point.split(','))) for point in text.split()]

    before = cpu_points()
    assert len(before) == len(window['cpu_percent']) == capacity
    top_before = min(range(len(before)), key=lambda index: before[index][1])
    assert top_before == capacity - 1

    window['cpu_percent'] = [0] * (capacity - 2) + [99.0, 0]
    driver.execute_script(
        'state.statistics = arguments[0]; renderPerformanceStatistics(arguments[0]);', snapshot)
    after = cpu_points()
    top_after = min(range(len(after)), key=lambda index: after[index][1])
    assert len(after) == len(window['cpu_percent']) == capacity
    assert top_after == top_before - 1
    assert after[top_before][0] > after[top_after][0]


@pytest.mark.browser
def test_performance_extended_metrics_and_local_time_window_switch(browser):
    # 性能页要展示细化的 CPU、内存、磁盘、网络与消息质量数据，并支持本地切换时间窗。
    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return state.page === 'performance' && !document.getElementById('performance-content').hidden"))

    details = driver.execute_script(r'''
        const stat = (name) => document.querySelector(`[data-performance-stat="${name}"]`).textContent;
        const volumes = [...document.querySelectorAll('#performance-disk-volumes .performance-volume-item')];
        return {
          windows: [...document.querySelectorAll('[data-performance-window]')].map((button) => ({
            key: button.dataset.performanceWindow,
            active: button.classList.contains('active'),
            disabled: button.disabled,
          })),
          sampled: document.getElementById('performance-sampled').textContent,
          cpuLoad: stat('cpu-machine-load'),
          cpuPhysical: stat('cpu-physical'),
          cpuFrequency: stat('cpu-frequency'),
          coreCount: document.querySelectorAll('#performance-cpu-cores .performance-core-item').length,
          coreFill: document.querySelector('#performance-cpu-cores .performance-meter-fill').style.width,
          memoryFree: stat('memory-free'),
          memoryCached: stat('memory-cached'),
          memoryBuffers: stat('memory-buffers'),
          memoryShared: stat('memory-shared'),
          swapTotal: stat('memory-swap-total'),
          swapUsed: stat('memory-swap-used'),
          swapFree: stat('memory-swap-free'),
          diskReadIops: stat('disk-read-iops'),
          diskWriteLatency: stat('disk-write-latency'),
          diskReadout: document.getElementById('performance-disk-io-readout').textContent,
          volumeCount: volumes.length,
          volumeText: volumes[0]?.querySelector('.performance-volume-meta')?.textContent || '',
          volumeFill: volumes[0]?.querySelector('.performance-meter-fill')?.style.width,
        };
    ''')
    assert details['windows'] == [
        {'key': '1m', 'active': True, 'disabled': False},
        {'key': '5m', 'active': False, 'disabled': False},
        {'key': '15m', 'active': False, 'disabled': False},
        {'key': '1h', 'active': False, 'disabled': False},
        {'key': '6h', 'active': False, 'disabled': False},
        {'key': '24h', 'active': False, 'disabled': False},
    ]
    assert re.fullmatch(r'更新于 \d{2}:\d{2}:\d{2}', details['sampled'])
    assert details['cpuLoad'] == '1.25 / 1.00 / 0.80'
    assert details['cpuPhysical'] == '4'
    assert details['cpuFrequency'] == '2400 MHz'
    assert details['coreCount'] == 8
    assert details['coreFill'] == '10%'
    assert details['memoryFree'] == '2.0 GiB'
    assert details['memoryCached'] == '3.0 GiB'
    assert details['memoryBuffers'] == '256.0 MiB'
    assert details['memoryShared'] == '128.0 MiB'
    assert details['swapTotal'] == '4.0 GiB'
    assert details['swapUsed'] == '1.0 GiB'
    assert details['swapFree'] == '3.0 GiB'
    assert details['diskReadIops'] == '12.0 次/秒'
    assert details['diskWriteLatency'] == '2.40 ms'
    assert '读取 1.0 KiB/s（12.0 次/秒，1.80 ms）' in details['diskReadout']
    assert details['volumeCount'] == 2
    assert '剩余 192.0 GiB' in details['volumeText']
    assert details['volumeFill'] == '25%'

    quality = driver.execute_script(r'''
        const stat = (name) => document.querySelector(`[data-performance-stat="${name}"]`).textContent;
        const interfaces = [...document.querySelectorAll(
          '#performance-network-interfaces .performance-interface-item')];
        return {
          networkErrors: stat('network-errors'),
          networkDrops: stat('network-drops'),
          networkConnections: stat('network-connections'),
          networkTcpStates: stat('network-tcp-states'),
          interfaceCount: interfaces.length,
          interfaceText: interfaces[0]?.textContent || '',
          trafficEvents: stat('traffic-events'),
          trafficFailed: stat('traffic-failed'),
          trafficFailedRate: stat('traffic-failed-rate'),
          trafficFailedTotal: stat('traffic-failed-total'),
          trafficReadout: document.getElementById('performance-traffic-readout').textContent,
          failureSeries: document.querySelector('#performance-failure-chart .chart-series-failed') !== null,
        };
    ''')
    assert quality['networkErrors'] == '收 0.5 个/秒 / 发 0.3 个/秒'
    assert quality['networkDrops'] == '收 1.0 个/秒 / 发 0.0 个/秒'
    assert quality['networkConnections'] == '7'
    assert quality['networkTcpStates'] == 'ESTABLISHED 4 · TIME_WAIT 3'
    assert quality['interfaceCount'] == 2
    assert 'eth0' in quality['interfaceText']
    assert quality['trafficEvents'] == '6 条/分钟'
    assert quality['trafficFailed'] == '1 条/分钟'
    assert quality['trafficFailedRate'] == '16.7%'
    assert quality['trafficFailedTotal'] == '2'
    assert '失败 1 条/分钟' in quality['trafficReadout']
    assert quality['failureSeries']

    switched = driver.execute_script(r'''
        const cpuY = () => {
          const line = document.querySelector('#performance-cpu-chart .chart-series-cpu');
          const points = line.getAttribute('points').trim().split(/\s+/);
          return Number(points[points.length - 1].split(',')[1]);
        };
        const beforeY = cpuY();
        const originalFetch = window.fetch;
        let requests = 0;
        window.fetch = function (...args) {
          if (String(args[0]).includes('/api/status?windows=1')) requests += 1;
          return originalFetch.apply(this, args);
        };
        document.querySelector('[data-performance-window="5m"]').click();
        const five = {
          active: document.querySelector('[data-performance-window="5m"]').classList.contains('active'),
          sampled: document.getElementById('performance-sampled').textContent,
          cpuY: cpuY(),
          trafficCapacity: Number(document.querySelector('#performance-traffic-chart svg').dataset.capacity),
          failureCapacity: Number(document.querySelector('#performance-failure-chart svg').dataset.capacity),
        };
        document.querySelector('[data-performance-window="15m"]').click();
        const fifteen = {
          active: document.querySelector('[data-performance-window="15m"]').classList.contains('active'),
          sampled: document.getElementById('performance-sampled').textContent,
          cpuY: cpuY(),
        };
        document.querySelector('[data-performance-window="24h"]').click();
        const daily = {
          active: document.querySelector('[data-performance-window="24h"]').classList.contains('active'),
          sampled: document.getElementById('performance-sampled').textContent,
          cpuCapacity: Number(document.querySelector('#performance-cpu-chart svg').dataset.capacity),
          trafficCapacity: Number(
            document.querySelector('#performance-traffic-chart svg').dataset.capacity),
          failureCapacity: Number(
            document.querySelector('#performance-failure-chart svg').dataset.capacity),
        };
        window.fetch = originalFetch;
        return {beforeY, requests, five, fifteen, daily};
    ''')
    assert switched['requests'] == 0
    assert switched['five']['active'] is True
    assert re.fullmatch(r'更新于 \d{2}:\d{2}:\d{2}', switched['five']['sampled'])
    assert switched['five']['cpuY'] < switched['beforeY']
    assert switched['five']['trafficCapacity'] == 60
    assert switched['five']['failureCapacity'] == 60
    assert switched['fifteen']['active'] is True
    assert re.fullmatch(r'更新于 \d{2}:\d{2}:\d{2}', switched['fifteen']['sampled'])
    assert switched['fifteen']['cpuY'] < switched['five']['cpuY']
    assert switched['daily']['active'] is True
    assert re.fullmatch(r'更新于 \d{2}:\d{2}:\d{2}', switched['daily']['sampled'])
    assert switched['daily']['cpuCapacity'] == 144
    assert switched['daily']['trafficCapacity'] == 144
    assert switched['daily']['failureCapacity'] == 144

    browser.click('[data-performance-category="traffic"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.getElementById('performance-view-traffic').hidden"))
    daily_tip = hover_chart(driver, '#performance-traffic-chart', 0.999)
    assert '条 / 10 分钟' in daily_tip['text']
    assert re.search(r'\d{1,2}[/-]\d{1,2}[ T,]*\d{2}:\d{2}:\d{2}', daily_tip['text'])


@pytest.mark.browser
def test_performance_window_falls_back_when_backend_has_no_windows(browser):
    # 旧统计组件只返回默认历史时，窗口按钮应禁用并回退到原容量，页面不能报错。
    snapshot = statistics_snapshot()
    snapshot['performance'].pop('windows', None)
    snapshot['traffic'].pop('windows', None)
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=lambda: snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    driver = browser.driver
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return state.page === 'performance' && !document.getElementById('performance-content').hidden"))

    fallback = driver.execute_script(r'''
        const buttons = [...document.querySelectorAll('[data-performance-window]')];
        const before = {
          disabled: buttons.map((button) => button.disabled),
          sampled: document.getElementById('performance-sampled').textContent,
          cpuCapacity: Number(document.querySelector('#performance-cpu-chart svg').dataset.capacity),
          trafficCapacity: Number(document.querySelector('#performance-traffic-chart svg').dataset.capacity),
        };
        buttons[1].click();
        return {
          before,
          windowKey: state.performanceWindow,
          cpuCapacity: Number(document.querySelector('#performance-cpu-chart svg').dataset.capacity),
          contentVisible: !document.getElementById('performance-content').hidden,
          note: document.getElementById('performance-statistics-note').textContent,
        };
    ''')
    assert fallback['before']['disabled'] == [True, True, True, True, True, True]
    assert re.fullmatch(r'更新于 \d{2}:\d{2}:\d{2}', fallback['before']['sampled'])
    assert fallback['before']['cpuCapacity'] == 120
    assert fallback['before']['trafficCapacity'] == 60
    assert fallback['windowKey'] == '1m'
    assert fallback['cpuCapacity'] == 120
    assert fallback['contentVisible'] is True
    assert fallback['note'] == ''


@pytest.mark.browser
def test_performance_navigation_uses_drawer_only_at_mobile_width(browser):
    # 宽竖屏不属于性能抽屉断点；900x1200 应继续使用 801-1100px 的横向导航。
    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return state.page === 'performance' && !document.getElementById('performance-content').hidden"))

    # 800px 及以下显示抽屉按钮，并打开固定抽屉。
    set_viewport(browser, 800, 1200, mobile_device=True)
    browser.wait.until(lambda _: driver.execute_script("""
        return innerWidth === 800 &&
          getComputedStyle(document.getElementById('performance-nav-toggle')).display !== 'none' &&
          getComputedStyle(document.getElementById('performance-nav-drawer')).position === 'fixed';
    """))
    browser.click('#performance-nav-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.body.classList.contains('performance-nav-open')"))

    # 加宽到 900px 后自动关闭抽屉，并恢复横向导航而不是纵向抽屉。
    set_viewport(browser, 900, 1200)
    browser.wait.until(lambda _: driver.execute_script("""
        return innerWidth === 900 && !state.performanceNavOpen &&
          !document.body.classList.contains('performance-nav-open');
    """))
    layout = driver.execute_script("""
        const toggle = document.getElementById('performance-nav-toggle');
        const drawer = document.getElementById('performance-nav-drawer');
        const categories = document.querySelector('.performance-categories');
        return {
          compact: matchMedia('(max-width: 800px)').matches,
          portrait: matchMedia('(orientation: portrait)').matches,
          toggleDisplay: getComputedStyle(toggle).display,
          drawerPosition: getComputedStyle(drawer).position,
          direction: getComputedStyle(categories).flexDirection,
        };
    """)
    assert layout == {
        'compact': False,
        'portrait': True,
        'toggleDisplay': 'none',
        'drawerPosition': 'sticky',
        'direction': 'row',
    }


@pytest.mark.browser
def test_performance_drawer_traps_focus_and_exposes_modal_state(browser):
    # 抽屉打开时是模态对话框：键盘焦点必须循环在关闭按钮和当前分类之间。
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys

    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return state.page === 'performance' && !document.getElementById('performance-content').hidden"))
    set_viewport(browser, 320, 844, mobile_device=True)

    browser.click('#performance-nav-toggle')
    browser.wait.until(lambda _: driver.execute_script("""
        const drawer = document.getElementById('performance-nav-drawer');
        return document.body.classList.contains('performance-nav-open') &&
          drawer.contains(document.activeElement) &&
          document.activeElement.dataset.performanceCategory === 'overview';
    """))
    assert driver.execute_script("""
        const drawer = document.getElementById('performance-nav-drawer');
        return {
          role: drawer.getAttribute('role'),
          modal: drawer.getAttribute('aria-modal'),
          labelledby: drawer.getAttribute('aria-labelledby'),
        };
    """) == {'role': 'dialog', 'modal': 'true', 'labelledby': 'performance-nav-title'}

    visited = set()
    for _ in range(4):
        ActionChains(driver).send_keys(Keys.TAB).perform()
        visited.add(driver.execute_script("""
            const active = document.activeElement;
            return active.id || active.dataset.performanceCategory;
        """))
    assert visited == {'performance-nav-close', 'performance-category-overview'}
    ActionChains(driver).key_down(Keys.SHIFT).send_keys(Keys.TAB).key_up(Keys.SHIFT).perform()
    assert driver.execute_script(
        "return document.getElementById('performance-nav-drawer')"
        ".contains(document.activeElement)")

    browser.click('#performance-nav-close')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.body.classList.contains('performance-nav-open')"))
    assert driver.execute_script("""
        const drawer = document.getElementById('performance-nav-drawer');
        return [drawer.getAttribute('role'), drawer.getAttribute('aria-modal')];
    """) == [None, None]


@pytest.mark.browser
def test_performance_drawer_closes_when_statistics_become_unavailable(browser):
    # 统计数据在抽屉打开期间失效时，必须先关闭抽屉并解除页面滚动锁定。
    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return state.page === 'performance' && !document.getElementById('performance-content').hidden"))
    set_viewport(browser, 320, 640, mobile_device=True)
    browser.click('#performance-nav-toggle')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.body.classList.contains('performance-nav-open')"))

    def fail():
        raise RuntimeError('fixture statistics failure while drawer open')

    browser.host.runtime['statistics'] = SimpleNamespace(Proc_type='statistics', snapshot=fail)
    driver.execute_async_script("""
        const done = arguments[arguments.length - 1];
        refreshStatus().then(() => done(true), (error) => done(String(error)));
    """)
    browser.wait.until(lambda _: '暂不可用' in browser.find('#performance-statistics-note').text)

    assert driver.execute_script("return document.getElementById('performance-content').hidden")
    assert driver.execute_script("""
        return {
          open: state.performanceNavOpen,
          bodyClass: document.body.classList.contains('performance-nav-open'),
          expanded: document.getElementById('performance-nav-toggle').getAttribute('aria-expanded'),
        };
    """) == {'open': False, 'bodyClass': False, 'expanded': 'false'}


@pytest.mark.browser
def test_performance_process_page_avoids_horizontal_overflow_across_widths(browser):
    # 进程树在手机、平板和窄桌面断点下都不能产生页面或详情栏级横向滚动条。
    driver = browser.driver
    # 用无空格长字符串模拟真实进程名、线程名和路径，覆盖最小内容宽度撑破布局的情况。
    long_name = 'OlivOSProcessNameWithoutBreak' * 8
    process_tree = process_tree_snapshot()
    process_tree['roots'][0]['name'] = long_name
    process_tree['roots'][0]['cmdline'] = 'C:/' + 'very-long-directory/' * 12 + 'runner.exe'
    process_tree['roots'][0]['threads'][0]['name'] = long_name
    process_tree['roots'][0]['threads'][0]['python_name'] = long_name
    process_tree['roots'][0]['children'][0]['name'] = long_name
    process_detail = process_detail_snapshot(1000, PROCESS_ROOT_CREATED_AT)
    process_detail['open_files']['items'][0]['path'] = 'C:/' + 'very-long-directory/' * 12 + 'a.log'

    def tree_snapshot():
        return process_tree

    def detail_snapshot(pid, create_time=None):
        return process_detail

    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=tree_snapshot,
        process_detail_snapshot=detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return state.page === 'performance' && !document.getElementById('performance-content').hidden"))
    browser.click('[data-performance-category="processes"]')
    browser.wait.until(lambda _: driver.execute_script("""
        return !document.getElementById('performance-view-processes').hidden &&
          document.querySelectorAll('#performance-process-tree .process-row').length === 2;
    """))
    browser.click('#performance-process-tree .process-detail-button')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.querySelector('.process-detail-summary') !== null"))

    for width in (320, 360, 390, 480, 640, 768, 800, 801, 900, 1024, 1030, 1031, 1100, 1101, 1280):
        set_viewport(browser, width, 700, mobile_device=width <= 800)
        browser.wait.until(lambda _, expected=width: driver.execute_script(
            "return innerWidth === arguments[0]", expected))
        layout = driver.execute_script("""
            const root = document.getElementById('performance-view-processes');
            const detail = document.querySelector('.performance-detail');
            const categories = document.querySelector('.performance-categories');
            const drawer = document.querySelector('.performance-nav-drawer');
            const workbench = document.querySelector('.performance-workbench');
            const viewport = document.documentElement.clientWidth;
            const overflow = [...root.querySelectorAll('*')].filter((node) => {
              const rect = node.getBoundingClientRect();
              if (!rect.width && !rect.height) return false;
              return rect.left < -1 || rect.right > viewport + 1;
            }).slice(0, 8).map((node) => ({
              tag: node.tagName.toLowerCase(),
              className: String(node.className || ''),
              left: Math.round(node.getBoundingClientRect().left),
              right: Math.round(node.getBoundingClientRect().right),
            }));
            return {
              viewport,
              documentWidth: document.documentElement.scrollWidth,
              workbenchColumns: getComputedStyle(workbench).gridTemplateColumns
                .split(' ').filter(Boolean).length,
              categoriesDirection: getComputedStyle(categories).flexDirection,
              drawerPosition: getComputedStyle(drawer).position,
              detailWidth: detail.clientWidth,
              detailScrollWidth: detail.scrollWidth,
              categoriesWidth: categories.clientWidth,
              categoriesScrollWidth: categories.scrollWidth,
              overflow,
            };
        """)
        assert layout['documentWidth'] <= layout['viewport'] + 1, (width, layout)
        assert layout['workbenchColumns'] == (1 if width <= 1100 else 2), (width, layout)
        assert layout['categoriesDirection'] == (
            'row' if 800 < width <= 1100 else 'column'
        ), (width, layout)
        assert layout['drawerPosition'] == (
            'fixed' if width <= 800 else 'sticky' if width <= 1100 else 'static'
        ), (width, layout)
        assert layout['detailScrollWidth'] <= layout['detailWidth'] + 1, (width, layout['overflow'])
        if width > 1100:
            assert layout['categoriesScrollWidth'] <= layout['categoriesWidth'] + 1, (width, layout)
        assert layout['overflow'] == [], (width, layout)


@pytest.mark.browser
def test_dashboard_statistics_failure_degrades_without_blocking_page(browser):
    driver = browser.driver

    def fail():
        raise RuntimeError('fixture statistics failure')

    browser.host.runtime['statistics'] = SimpleNamespace(Proc_type='statistics', snapshot=fail)
    browser.open_sidebar()
    browser.click('[data-page="dashboard"]')
    browser.wait.until(lambda _: '暂不可用' in browser.find('#statistics-note').text)
    assert driver.execute_script("return document.getElementById('statistics-content').hidden")
    assert browser.find('[data-page="dashboard"]').is_displayed()
    assert browser.find('#runtime').is_displayed()


@pytest.mark.browser
def test_performance_statistics_failure_degrades_without_blocking_page(browser):
    driver = browser.driver

    def fail():
        raise RuntimeError('fixture performance statistics failure')

    browser.host.runtime['statistics'] = SimpleNamespace(Proc_type='statistics', snapshot=fail)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: '暂不可用' in browser.find('#performance-statistics-note').text)
    assert browser.find('#page-title').text == '性能'
    assert driver.execute_script("return document.getElementById('performance-content').hidden")
    assert browser.find('#performance-statistics-note').is_displayed()
    assert browser.find('[data-page="performance"]').is_displayed()


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
