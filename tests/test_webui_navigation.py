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
from webui_test_support import QQBindRemote, login_ui, make_host


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
            if packet.action == 'webui_accounts':
                host.commit_accounts(packet.key['request_id'], {})
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
    from selenium.common.exceptions import StaleElementReferenceException
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait

    url = f"http://127.0.0.1:{navigation_host.config['port']}"
    driver = chrome_session.prepare(url)
    wait = WebDriverWait(driver, 10)

    def locate(selector):
        return driver.find_element(By.CSS_SELECTOR, selector)

    def plain_text_keys(keys):
        # WebDriver 的特殊键位于私有区，普通文本才需要做幂等重放。
        return all(
            isinstance(key, str) and all(
                not ('\ue000' <= char <= '\ue05f') for char in key)
            for key in keys
        )

    def restore_field_value(field, value):
        driver.execute_script('''
            const node = arguments[0];
            const proto = node.tagName === 'TEXTAREA'
              ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
            setter.call(node, arguments[1]);
            node.dispatchEvent(new Event('input', {bubbles: true}));
            node.dispatchEvent(new Event('change', {bubbles: true}));
        ''', field, value)

    class Element:
        """按选择器重新定位的元素包装，避免轮询刷新后句柄失效。"""

        def __init__(self, selector):
            self.selector = selector

        def raw(self):
            return locate(self.selector)

        def _retry(self, action):
            def attempt(_):
                try:
                    return True, action(self.raw())
                except StaleElementReferenceException:
                    return False
            return wait.until(attempt, '元素在刷新中持续失效：' + self.selector)[1]

        @property
        def text(self):
            return self._retry(lambda element: element.text)

        @property
        def accessible_name(self):
            return self._retry(lambda element: element.accessible_name)

        def get_attribute(self, name):
            return self._retry(lambda element: element.get_attribute(name))

        def is_displayed(self):
            return self._retry(lambda element: element.is_displayed())

        def is_enabled(self):
            return self._retry(lambda element: element.is_enabled())

        def click(self):
            click(self.selector)

        def send_keys(self, *keys):
            text_only = plain_text_keys(keys)
            initial_value = None
            attempted = False

            def attempt(_):
                nonlocal initial_value, attempted
                try:
                    field = self.raw()
                    tag = field.tag_name.lower()
                    if text_only and tag in ('input', 'textarea'):
                        if initial_value is None:
                            initial_value = field.get_attribute('value') or ''
                        elif attempted:
                            restore_field_value(field, initial_value)
                    attempted = True
                    field.send_keys(*keys)
                    return True
                except StaleElementReferenceException:
                    return False
            wait.until(attempt)

        def find_element(self, by, value):
            return self.raw().find_element(by, value)

        def find_elements(self, by, value):
            return self.raw().find_elements(by, value)

        def __eq__(self, other):
            other = other.raw() if isinstance(other, Element) else other
            return self.raw() == other

        def __repr__(self):
            return f'Element({self.selector!r})'

    def find(selector):
        return Element(selector)

    def click(selector):
        def click_when_ready(_):
            # 统计轮询会重建局部节点；点击前重新定位，stale 时交给 wait 重试。
            try:
                element = locate(selector)
                if not (element.is_displayed() and element.is_enabled()):
                    return False
                element.click()
            except StaleElementReferenceException:
                return False
            return True
        wait.until(click_when_ready)

    def hover(selector):
        def hover_when_ready(_):
            # 统计轮询会重建进程树等局部节点；悬停前重新定位，stale 时交给 wait 重试。
            try:
                element = locate(selector)
                if not element.is_displayed():
                    return False
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                ActionChains(driver).move_to_element(element).perform()
            except StaleElementReferenceException:
                return False
            return True
        wait.until(hover_when_ready)

    def type_text(selector, text):
        # Chrome 158 对 sandbox iframe 内输入框的可交互性判定更严格，
        # 先点击聚焦，避免直接 send_keys 被 ChromeDriver 拒绝。
        field = find(selector)
        field.click()
        field.send_keys(text)

    def press(selector):
        def press_when_ready(_):
            try:
                element = locate(selector)
                if not element.is_displayed():
                    return False
                ActionChains(driver).click_and_hold(element).perform()
            except StaleElementReferenceException:
                return False
            return True
        wait.until(press_when_ready)

    def release():
        ActionChains(driver).release().perform()

    def text(selector):
        return find(selector).text

    def attribute(selector, name):
        return find(selector).get_attribute(name)

    def open_sidebar():
        if not driver.execute_script(
                'return matchMedia("(max-width: 800px), (orientation: portrait)").matches'):
            return
        if driver.execute_script("return document.getElementById('shell').dataset.sidebarOpen === 'true'"):
            return
        click('#sidebar-toggle')
        wait.until(lambda _: driver.execute_script('''
            const sidebar = document.getElementById('sidebar');
            return document.getElementById('shell').dataset.sidebarOpen === 'true' &&
              sidebar.getBoundingClientRect().left >= -1 &&
              sidebar.getAnimations().every(animation => animation.playState === 'finished');
        '''))

    def select(path='webui/index.html', namespace='multi'):
        open_sidebar()
        selector = f'.plugin-link-entry[data-plugin-namespace="{namespace}"][data-plugin-path="{path}"]'
        driver.execute_script('document.querySelector(arguments[0]).scrollIntoView({block: "center"})', selector)
        click(selector)
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
    login_ui(driver, navigation_host.test_password)
    yield SimpleNamespace(driver=driver, wait=wait, find=find, click=click, hover=hover, press=press, release=release,
                          text=text, attribute=attribute, type_text=type_text,
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
        return mobile === arguments[0] && synced &&
            sidebar.getAnimations().every(animation => animation.playState === 'finished');
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
    multi = '.plugin-page-group[data-plugin-namespace="multi"]'
    single = '.plugin-page-group[data-plugin-namespace="single"]'
    assert browser.text(f'{multi} .plugin-group-namespace') == 'multi'
    assert browser.text(f'{single} .plugin-group-name') == '功能首页'
    assert browser.text(f'{single} .plugin-group-namespace') == 'single'
    assert browser.attribute(f'{single} .plugin-single-entry', 'title') == '独立插件'
    child = f'{multi} [data-plugin-path="webui/settings/index.html"]'
    assert browser.attribute(child, 'title') == '配置管理'
    assert browser.attribute(child, 'aria-label') == '配置管理（multi）'


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
    browser.select()
    driver = browser.driver
    driver.switch_to.default_content()
    entry = '#plugin-links .plugin-link-entry.active'
    category = '[data-performance-category="overview"]'
    time.sleep(0.2)
    # 插件页面入口应对齐导航基准；性能分类复用导航样式，因此用作可见参照。
    active_styles = driver.execute_script("""
        return [arguments[0], arguments[1]].map((selector) => {
          const style = getComputedStyle(document.querySelector(selector));
          return [style.backgroundColor, style.borderColor, style.boxShadow];
        });
    """, entry, category)
    assert active_styles[0] == active_styles[1]

    # 插件入口按下态也应对齐导航基准；性能分类复用同一套按下效果。
    pressed_script = """
        const style = getComputedStyle(document.querySelector(arguments[0]));
        return {
          background: style.backgroundColor,
          border: style.borderColor,
          shadow: style.boxShadow,
          outline: style.outline,
        };
    """
    browser.press(entry)
    time.sleep(0.2)
    entry_pressed = driver.execute_script(pressed_script, entry)
    browser.release()
    time.sleep(0.05)

    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.click('[data-page="performance"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return !document.getElementById('performance-content').hidden"))
    browser.press(category)
    time.sleep(0.2)
    category_pressed = driver.execute_script(pressed_script, category)
    browser.release()
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
    close_title = browser.driver.execute_script("""
        const entry = document.querySelector('[data-plugin-path="webui/tools/index.html"]');
        return entry.parentElement.querySelector('.plugin-link-close').getAttribute('title');
    """)
    assert close_title == '关闭：多页面插件（multi） / 配置管理（webui/tools/index.html）'


@pytest.mark.browser
def test_closing_one_plugin_page_keeps_other_cached_pages(browser):
    browser.select()
    browser.driver.switch_to.default_content()
    browser.select('webui/settings/index.html')
    browser.driver.switch_to.default_content()
    browser.driver.execute_script("""
        const row = document.querySelector(
          '.plugin-link-entry[data-plugin-namespace="multi"][data-plugin-path="webui/index.html"]');
        row.parentElement.querySelector('.plugin-link-close').click();
    """)
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
def test_log_output_keeps_bottom_gap_aligned_with_inline_padding(browser):
    # 宽窄屏下日志面板的底边距离都应与页面左右内边距一致，且不随视口高度或工具栏换行漂移。
    driver = browser.driver
    set_viewport(browser, 1440, 900)
    browser.click('[data-page="logs"]')
    browser.wait.until(lambda _: browser.find('#logs').is_displayed())

    for width, height in ((1440, 900), (1440, 680), (1024, 768), (801, 720),
                          (800, 720), (390, 844), (390, 640), (320, 640)):
        set_viewport(browser, width, height, mobile_device=width <= 800)
        geometry = driver.execute_script("""
            const main = document.querySelector('main');
            const output = document.getElementById('log-output');
            const rect = output.getBoundingClientRect();
            return {
              rightGap: innerWidth - rect.right,
              bottomGap: innerHeight - rect.bottom,
              inlinePadding: parseFloat(getComputedStyle(main).paddingRight),
              height: rect.height,
            };
        """)
        label = f'{width}x{height}'
        assert abs(geometry['rightGap'] - geometry['inlinePadding']) <= 1, (label, geometry)
        assert abs(geometry['bottomGap'] - geometry['inlinePadding']) <= 1, (label, geometry)
        assert geometry['height'] > 250, (label, geometry)


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


@pytest.fixture
def account_qr(browser, monkeypatch):
    """记录实际 Flask 请求的路径和状态，不截取密钥、请求正文或账号响应。"""
    remote = QQBindRemote(monkeypatch)
    calls = []
    app = browser.host.app
    dispatch = app.wsgi_app

    def observe(environ, start_response):
        def started(status, headers, exc_info=None):
            calls.append((environ['REQUEST_METHOD'], environ['PATH_INFO'], status.split()[0]))
            return start_response(status, headers, exc_info)

        return dispatch(environ, started)

    monkeypatch.setattr(app, 'wsgi_app', observe)
    browser.click('[data-page="accounts"]')
    browser.wait.until(lambda _: browser.find('#accounts').is_displayed())
    return SimpleNamespace(remote=remote, calls=calls)


def choose_account_preset(browser, title):
    from selenium.webdriver.common.by import By
    browser.click('#account-preset')
    browser.driver.find_element(By.XPATH, f'//*[@role="option"][normalize-space(.)="{title}"]').click()
    assert browser.attribute('#account-preset', 'value') == title


def quick_account_qr(browser):
    browser.click('#add-account-menu-toggle')
    browser.click('#account-add-qr')


def account_confirm(browser, text, accept=True):
    from selenium.webdriver.support import expected_conditions as ec
    alert = browser.wait.until(ec.alert_is_present())
    assert text in alert.text
    if accept:
        alert.accept()
    else:
        alert.dismiss()


def qr_blob(browser):
    return browser.wait.until(lambda _: browser.driver.execute_script('''
        const image = document.querySelector('#qr-image');
        return image.complete && image.naturalWidth && image.src.startsWith('blob:') && image.src;
    '''))


def assert_revoked_blob(browser, url):
    assert browser.driver.execute_async_script('''
        const done = arguments[1];
        fetch(arguments[0]).then(() => done(false), () => done(true));
    ''', url)


@pytest.mark.browser
def test_account_split_menu_and_qr_preset_visibility(browser, account_qr):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    toggle = browser.find('#add-account-menu-toggle')
    assert browser.driver.execute_script('''
        const button = document.getElementById('add-account-menu-toggle');
        const svg = button.querySelector('svg');
        if (!svg) return false;
        const br = button.getBoundingClientRect();
        const sr = svg.getBoundingClientRect();
        const dx = Math.abs((br.left + br.width / 2) - (sr.left + sr.width / 2));
        const dy = Math.abs((br.top + br.height / 2) - (sr.top + sr.height / 2));
        return sr.width > 0 && sr.height > 0 && dx <= 1.5 && dy <= 1.5;
    ''')
    toggle.click()
    browser.wait.until(lambda _: browser.driver.execute_script('''
        const menu = document.getElementById('account-add-menu');
        return !menu.hidden && menu.getAnimations().every(animation => animation.playState === 'finished');
    '''))
    items = browser.find('#account-add-menu').find_elements(By.XPATH, './*')
    assert [item.text for item in items] == [
        '新增账号（通用）', 'QQ 官方扫码创建', '从剪贴板导入', '从 JSON 文件导入',
    ]
    assert toggle.get_attribute('aria-expanded') == 'true'
    browser.find('#account-add-general').send_keys(Keys.ESCAPE)
    assert not browser.find('#account-add-menu').is_displayed()
    assert browser.driver.switch_to.active_element == toggle.raw()
    toggle.click()
    browser.click('#page-title')
    assert toggle.get_attribute('aria-expanded') == 'false'
    toggle.click()
    browser.click('#account-add-general')
    assert not browser.find('#account-add-menu').is_displayed()
    bar = browser.find('#account-qr-bind-bar')
    assert not bar.is_displayed()  # 默认 NapCat
    for preset, visible in [('QQ官方/公域/V2', True), ('QQ官方/公域/V1', False),
                            ('QQ官方/沙盒/V2/Webhook', True), ('QQ官方/私域/V2/指定intents', True)]:
        choose_account_preset(browser, preset)
        assert bar.is_displayed() is visible
        if preset == 'QQ官方/公域/V2':
            assert 'IP白名单' not in browser.text('#account-note')
    assert not account_qr.remote.keys


@pytest.mark.browser
def test_mobile_account_split_keeps_two_touch_targets_and_menu_in_view(browser, account_qr):
    set_viewport(browser, 320, 568)
    browser.click('#add-account-menu-toggle')
    assert browser.driver.execute_script('''
        const bounds = (id) => document.getElementById(id).getBoundingClientRect();
        const add = bounds('add-account'), toggle = bounds('add-account-menu-toggle');
        const menu = bounds('account-add-menu');
        return add.height >= 44 && toggle.height >= 44 && toggle.width >= 44 &&
          Math.abs(add.right - toggle.left) < 1 && menu.left >= 0 && menu.right <= innerWidth;
    ''')


@pytest.mark.browser
def test_qr_quick_account_saves_then_updates_only_confirmed_secret(browser, account_qr):
    remote = account_qr.remote
    path = browser.host.account_path
    remote.status = 2
    quick_account_qr(browser)
    browser.wait.until(lambda _: path.is_file() and not browser.text('#accounts-dirty'))
    original, = json.loads(path.read_text(encoding='utf-8'))['account']
    assert str(original['id']) == remote.app_id
    assert (original['sdk_type'], original['platform_type'], original['model_type'], original['enable']) == (
        'qqGuildv2_link', 'qqGuild', 'public', True)
    assert (original['server']['type'], original['server']['auto'], original['server']['access_token']) == (
        'websocket', True, remote.app_secret)

    # 同一 AppID 可以已有非默认预设；快捷入口只应修改它的密钥。
    browser.click('#account-rows .actions button:nth-child(2)')
    choose_account_preset(browser, 'QQ官方/私域/V2')
    browser.click('#account-debug')
    browser.click('#account-form button[type="submit"]')
    browser.click('#account-rows [role="switch"]')
    remote.app_secret += '-rotated'
    quick_account_qr(browser)
    account_confirm(browser, '一并保存', accept=False)
    assert len(remote.keys) == 1 and not browser.find('#qr-dialog').is_displayed()
    quick_account_qr(browser)
    account_confirm(browser, '一并保存')
    account_confirm(browser, '仅更新 AppSecret', accept=False)
    assert json.loads(path.read_text(encoding='utf-8'))['account'] == [original]
    assert browser.text('#accounts-dirty')

    quick_account_qr(browser)
    account_confirm(browser, '一并保存')
    account_confirm(browser, '仅更新 AppSecret')
    browser.wait.until(lambda _: not browser.text('#accounts-dirty'))
    original.update(enable=False, debug=True, model_type='private')
    original['server']['access_token'] = remote.app_secret
    assert json.loads(path.read_text(encoding='utf-8'))['account'] == [original]
    assert account_qr.calls.count(('POST', '/api/accounts', '200')) == 2


@pytest.mark.browser
@pytest.mark.parametrize(('preset', 'review'), [
    ('QQ官方/私域/V2', ''), ('QQ官方/公域/V2/Webhook', 'Webhook'), ('QQ官方/沙盒/V2/指定intents', 'intents'),
])
def test_account_qr_editor_stages_until_manual_save(browser, account_qr, preset, review):
    remote = account_qr.remote
    path = browser.host.account_path
    browser.click('#add-account')
    choose_account_preset(browser, preset)
    browser.click('#account-qr-fill')
    qr_blob(browser)
    assert browser.attribute('#qr-link', 'href').startswith('https://q.qq.com/qqbot/openclaw/connect.html?')
    remote.status = 2
    browser.wait.until(lambda _: not browser.find('#qr-dialog').is_displayed())
    if review:
        assert browser.find('#account-dialog').is_displayed()
        assert review in browser.text('#account-error')
        assert browser.attribute('#account-form [data-field="id"]', 'value') == remote.app_id
        assert browser.attribute('#account-form [data-field="server.access_token"]', 'value') == remote.app_secret
        if review == 'Webhook':
            browser.wait.until(lambda _: browser.attribute('#webhook-url', 'value').endswith('/' + remote.app_id))
        else:
            browser.type_text('#account-form [data-field="server.port"]', '33554432')
        browser.click('#account-form button[type="submit"]')
    assert not browser.find('#account-dialog').is_displayed()
    assert remote.app_id in browser.text('#account-rows') and browser.text('#accounts-dirty')
    assert not path.exists() and not any(call[:2] == ('POST', '/api/accounts') for call in account_qr.calls)
    browser.click('#save-accounts')
    browser.wait.until(lambda _: not browser.text('#accounts-dirty'))
    row, = json.loads(path.read_text(encoding='utf-8'))['account']
    assert str(row['id']) == remote.app_id and row['server']['access_token'] == remote.app_secret
    if review == 'intents':
        assert row['server']['port'] == 33554432


@pytest.mark.browser
def test_account_qr_expiry_refresh_keeps_editor_callback_and_revokes_image(browser, account_qr):
    browser.click('#add-account')
    choose_account_preset(browser, 'QQ官方/公域/V2/指定intents')
    browser.type_text('#account-form [data-field="server.port"]', '4096')
    browser.click('#account-qr-fill')
    first = qr_blob(browser)
    account_qr.remote.status = 3
    browser.wait.until(lambda _: '过期' in browser.text('#qr-status'))
    assert not browser.find('#qr-link').is_displayed() and not browser.find('#qr-image').is_displayed()
    assert_revoked_blob(browser, first)
    account_qr.remote.status = 1
    browser.click('#qr-refresh')
    assert qr_blob(browser) != first
    account_qr.remote.status = 2
    browser.wait.until(lambda _: not browser.find('#account-dialog').is_displayed())
    assert account_qr.remote.app_id in browser.text('#account-rows')
    assert not browser.host.account_path.exists()
    assert len(account_qr.remote.keys) == 2
    browser.click('#refresh-accounts')
    account_confirm(browser, '放弃尚未应用')
    browser.wait.until(lambda _: not browser.text('#accounts-dirty'))


@pytest.mark.browser
@pytest.mark.parametrize('pending', ['create_bind_task', 'poll_bind_result'])
def test_account_qr_cancel_inflight_never_applies_late_result(browser, account_qr, monkeypatch, pending):
    import requests
    entered, release = threading.Event(), threading.Event()
    remote = account_qr.remote
    remote.status = 2

    def slow_post(url, **kwargs):
        if url.endswith('/' + pending):
            entered.set()
            assert release.wait(15)
        return remote.post(url, **kwargs)

    monkeypatch.setattr(requests, 'post', slow_post)
    quick_account_qr(browser)
    try:
        assert entered.wait(8)
        image = qr_blob(browser) if pending == 'poll_bind_result' else None
        browser.click('#qr-actions [data-close="qr-dialog"]')
        assert not browser.find('#qr-dialog').is_displayed()
    finally:
        release.set()
    browser.wait.until(lambda _: any(method == 'DELETE' and '/qr-bind/' in path and status == '200'
                                     for method, path, status in account_qr.calls))
    if image:
        assert_revoked_blob(browser, image)
    assert not browser.host.account_path.exists() and not browser.text('#accounts-dirty')
    assert remote.app_id not in browser.text('#account-rows')


@pytest.mark.browser
def test_terminal_qr_keeps_original_link_and_releases_image_on_escape(browser, tmp_path):
    import qrcode
    from selenium.webdriver.common.keys import Keys

    bot = OlivOS.API.bot_info_T(id=23456, platform_sdk='onebot', platform_platform='qq',
                                platform_model='napcat_show_new')
    host = browser.host
    with host.lock:
        host.accounts[bot.hash] = bot
    image = tmp_path / 'data/terminal-qr.png'
    image.parent.mkdir(exist_ok=True)
    qrcode.make('fixture-terminal').save(image)
    url = f'http://127.0.0.1:{host.config["port"]}/api/health'

    def emit(event, **fields):
        host.consume(OlivOS.API.Control.packet('send', {'data': {
            'action': 'napcat', 'event': event, 'hash': bot.hash, **fields,
        }}))

    emit('init')
    emit('qrcode_url', url=url)
    browser.wait.until(lambda _: browser.find('#qr-link').is_displayed())
    emit('qrcode', path=str(image))
    blob = qr_blob(browser)
    assert str(bot.id) in browser.text('#qr-title')
    assert browser.attribute('#qr-link', 'href') == url
    assert not browser.find('#qr-actions').is_displayed() and not browser.find('#qr-status').is_displayed()
    browser.find('#qr-dialog [data-close]').send_keys(Keys.ESCAPE)
    browser.wait.until(lambda _: not browser.find('#qr-dialog').is_displayed())
    assert_revoked_blob(browser, blob)


@pytest.mark.browser
@pytest.mark.parametrize('dirty', [False, True], ids=['clean', 'confirmed-dirty'])
def test_account_qr_page_reload_deletes_session(browser, account_qr, dirty):
    if dirty:
        browser.click('#add-account')
        choose_account_preset(browser, 'QQ官方/公域/V2')
        browser.type_text('#account-form [data-field="id"]', '444444')
        browser.click('#account-form button[type="submit"]')
    quick_account_qr(browser)
    if dirty:
        account_confirm(browser, '一并保存')
    qr_blob(browser)
    session_path, = [path.removesuffix('/qrcode') for method, path, status in account_qr.calls
                     if method == 'GET' and path.endswith('/qrcode') and status == '200']
    browser.driver.refresh()
    browser.wait.until(lambda _: ('DELETE', session_path, '200') in account_qr.calls)
    with pytest.raises(KeyError):
        browser.host.qr_bind_manager.get_qr_png(session_path.rsplit('/', 1)[-1])
    assert not browser.host.account_path.exists()


@pytest.mark.browser
def test_qr_quick_account_applies_multiple_credentials_and_editor_warns(browser, account_qr):
    remote = account_qr.remote
    path = browser.host.account_path
    remote.credentials = [('11111111', 'secret-alpha'), ('22222222', 'secret-beta')]
    remote.status = 2
    quick_account_qr(browser)
    browser.wait.until(lambda _: path.is_file() and not browser.text('#accounts-dirty'))
    saved = json.loads(path.read_text(encoding='utf-8'))['account']
    assert {(str(row['id']), row['server']['access_token']) for row in saved} == {
        ('11111111', 'secret-alpha'), ('22222222', 'secret-beta'),
    }

    remote.credentials = [('33333333', 'secret-gamma'), ('44444444', 'secret-delta')]
    browser.click('#add-account')
    choose_account_preset(browser, 'QQ官方/公域/V2')
    browser.click('#account-qr-fill')
    browser.wait.until(lambda _: not browser.find('#account-dialog').is_displayed())
    assert '44444444' in browser.text('#notice-message')
    assert '33333333' in browser.text('#account-rows')
    browser.click('#refresh-accounts')
    account_confirm(browser, '放弃尚未应用')
    browser.wait.until(lambda _: not browser.text('#accounts-dirty'))


@pytest.mark.browser
def test_account_save_preserves_concurrent_edits_during_inflight_request(browser, account_qr):
    driver = browser.driver
    browser.click('#add-account')
    choose_account_preset(browser, 'QQ官方/公域/V2')
    browser.type_text('#account-form [data-field="id"]', '555555')
    browser.type_text('#account-form [data-field="server.access_token"]', 'secret-555')
    browser.click('#account-form button[type="submit"]')
    browser.wait.until(lambda _: browser.text('#accounts-dirty'))

    result = driver.execute_async_script('''
        const done = arguments[arguments.length - 1];
        const originalFetch = window.fetch;
        let releasePost = null;
        let postStarted = false;
        window.fetch = (path, options) => {
          if (path === '/api/accounts' && options?.method === 'POST') {
            postStarted = true;
            return new Promise((resolve, reject) => {
              releasePost = () => originalFetch(path, options).then(resolve, reject);
            });
          }
          return originalFetch(path, options);
        };
        const saving = saveAccounts();
        const waitStart = () => {
          if (!postStarted) return setTimeout(waitStart, 10);
          state.accounts[0].debug = true;
          dirty();
          releasePost();
          saving.then(() => {
            window.fetch = originalFetch;
            done({
              dirty: state.dirty,
              dirtyText: document.getElementById('accounts-dirty').textContent,
              debugKept: state.accounts[0].debug === true,
              notice: document.getElementById('notice-message').textContent,
            });
          }, (error) => {
            window.fetch = originalFetch;
            done({ error: String(error) });
          });
        };
        waitStart();
    ''')
    assert result.get('error') is None
    assert result['dirty'] is True
    assert result['dirtyText'] != ''
    assert result['debugKept'] is True
    assert '新的本地编辑' in result['notice']
    browser.click('#save-accounts')
    browser.wait.until(lambda _: not browser.text('#accounts-dirty'))
    saved, = json.loads(browser.host.account_path.read_text(encoding='utf-8'))['account']
    assert saved['debug'] is True


ACCOUNT_IDS = (51001, 51002, 51003)
ACCOUNT_IMPORT = '#account-import-dialog'
ACCOUNT_IMPORT_CANCEL = f'{ACCOUNT_IMPORT} .dialog-actions [data-close="account-import-dialog"]'


def transfer_account(account_id, **fields):
    row = {
        'id': account_id, 'sdk_type': 'onebot', 'platform_type': 'qq', 'model_type': 'default',
        'server': {'auto': False, 'type': 'post', 'host': 'http://127.0.0.1', 'port': 5700,
                   'access_token': f'fixture-token-{account_id}'},
        'password': f'fixture-password-{account_id}', 'extends': {}, 'enable': True, 'debug': False,
    }
    return dict(row, **fields)


def account_file_rows(host):
    return json.loads(host.account_path.read_text(encoding='utf-8'))['account']


def account_table(browser):
    return browser.driver.execute_script('''
        return Array.from(document.querySelectorAll('#account-rows tr:has(.account-select)'), row => ({
          id: row.cells[2].textContent.trim().split(' ')[0],
          checked: row.querySelector('.account-select').checked,
          offline: row.cells[2].textContent.includes('离线'),
        }));
    ''')


def account_order(browser):
    return [int(row['id']) for row in account_table(browser)]


def selected_accounts(browser):
    return [int(row['id']) for row in account_table(browser) if row['checked']]


def account_row(position):
    return f'#account-rows tr:nth-child({position})'


def wait_account_menu_open(browser, selector):
    # .account-split-menu 展开时带有 select-menu-in（opacity 0 -> 1）入场动画，
    # 等动画结束后再断言 is_displayed() 或发送按键，避免在首帧透明态误判。
    browser.wait.until(lambda _: browser.driver.execute_script('''
        const menu = document.querySelector(arguments[0]);
        return !!menu && !menu.hidden &&
          menu.getAnimations().every(animation => animation.playState === 'finished');
    ''', selector) and browser.find(selector).is_displayed())


@pytest.fixture
def account_transfer(browser):
    from OlivOS.webUI import pageAPI

    rows = [transfer_account(account_id) for account_id in ACCOUNT_IDS]
    rows[0]['extends'] = {'retired': 'previous-fixture-value'}
    host = browser.host
    path = host.account_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'account': rows}), encoding='utf-8')
    with host.lock:
        host.accounts = pageAPI.load_accounts(host)

    browser.click('[data-page="accounts"]')
    browser.wait.until(lambda _: account_order(browser) == list(ACCOUNT_IDS))
    # 等进入账号页触发的 GET /api/accounts 和随后的 GET /api/status 完成，避免和首个用户操作竞争。
    browser.wait.until(lambda _: browser.driver.execute_script('''
        const requests = path => performance.getEntriesByName(new URL(path, location.href).href);
        const accounts = requests('/api/accounts');
        const status = requests('/api/status');
        return accounts.length >= 2 && status.length >= 2 &&
          status.at(-1).startTime >= accounts.at(-1).responseEnd;
    '''))
    return browser


@pytest.mark.browser
def test_empty_account_table_spans_all_columns_and_disables_selection(browser):
    browser.click('[data-page="accounts"]')
    browser.wait.until(lambda _: browser.driver.execute_script(
        'return document.querySelectorAll("#account-rows td").length === 1'))
    assert browser.driver.execute_script(
        'return document.querySelectorAll("#accounts thead th").length') == 6
    assert browser.attribute('#account-rows td', 'colspan') == '6'
    assert not browser.find('#accounts-select-all').is_enabled()
    assert not browser.find('#export-accounts-copy').is_enabled()
    assert not browser.find('#export-accounts-menu-toggle').is_enabled()


@pytest.mark.browser
def test_account_selection_and_export_menu_follow_current_rows(account_transfer):
    from selenium.webdriver.common.keys import Keys

    browser = account_transfer
    driver = browser.driver
    header = '#accounts-select-all'
    copy = '#export-accounts-copy'
    toggle = '#export-accounts-menu-toggle'
    export_menu = '#account-export-menu'
    add_menu = '#account-add-menu'
    assert browser.text(copy) == '复制所选'
    assert not browser.find(copy).is_enabled() and not browser.find(toggle).is_enabled()

    browser.click(f'{account_row(2)} .account-select')
    assert selected_accounts(browser) == [51002]
    assert driver.execute_script('return document.querySelector(arguments[0]).indeterminate', header)
    assert browser.text(copy) == '复制所选 (1)'
    assert browser.find(copy).is_enabled() and browser.find(toggle).is_enabled()

    browser.click('#add-account-menu-toggle')
    wait_account_menu_open(browser, add_menu)
    browser.click(toggle)
    assert not browser.find(add_menu).is_displayed()
    wait_account_menu_open(browser, export_menu)
    browser.click('#add-account-menu-toggle')
    assert not browser.find(export_menu).is_displayed()
    wait_account_menu_open(browser, add_menu)
    browser.click(toggle)
    wait_account_menu_open(browser, export_menu)
    browser.find('#account-export-clipboard').send_keys(Keys.ESCAPE)
    assert not browser.find(export_menu).is_displayed()
    assert driver.switch_to.active_element == browser.find(toggle).raw()
    browser.click(toggle)
    wait_account_menu_open(browser, export_menu)
    browser.click('[data-page="plugins"]')
    browser.wait.until(lambda _: browser.attribute(toggle, 'aria-expanded') == 'false')
    browser.click('[data-page="accounts"]')
    browser.wait.until(lambda _: not browser.find(copy).is_enabled())

    browser.click(header)
    assert selected_accounts(browser) == list(ACCOUNT_IDS)
    assert browser.attribute(header, 'checked') == 'true'
    assert not driver.execute_script('return document.querySelector(arguments[0]).indeterminate', header)
    assert browser.text(copy) == '复制所选 (3)'
    browser.click(header)
    assert selected_accounts(browser) == []
    assert not browser.find(copy).is_enabled() and not browser.find(toggle).is_enabled()

    browser.click(f'{account_row(2)} .account-select')
    browser.click(f'{account_row(2)} .actions button:nth-child(2)')
    browser.click('#account-form button[type="submit"]')
    browser.wait.until(lambda _: not browser.find('#account-dialog').is_displayed())
    assert selected_accounts(browser) == [51002]
    browser.click(f'{account_row(2)} .actions button:last-child')
    account_confirm(browser, '删除账号 51002')
    assert selected_accounts(browser) == []
    assert account_order(browser) == [51001, 51003]
    browser.click(f'{account_row(2)} .account-select')
    browser.click('#refresh-accounts')
    account_confirm(browser, '放弃尚未应用')
    browser.wait.until(lambda _: account_order(browser) == list(ACCOUNT_IDS))
    assert selected_accounts(browser) == []


@pytest.mark.browser
def test_keyboard_account_sort_keeps_handle_focus_and_persists_file_order(account_transfer):
    from selenium.webdriver.common.keys import Keys

    browser = account_transfer
    driver = browser.driver
    first = f'{account_row(1)} .account-drag-handle'
    second = f'{account_row(2)} .account-drag-handle'
    revision = driver.execute_script('return state.revision')
    old_rows = account_file_rows(browser.host)
    browser.click(f'{account_row(1)} .account-select')
    browser.find(first).send_keys(Keys.ARROW_UP)
    assert account_order(browser) == list(ACCOUNT_IDS)
    assert not browser.text('#accounts-dirty')

    browser.find(first).send_keys(Keys.ARROW_DOWN)
    assert account_order(browser) == [51002, 51001, 51003]
    assert driver.switch_to.active_element == browser.find(second).raw()
    assert selected_accounts(browser) == [51001]
    browser.find(second).send_keys(Keys.ARROW_UP)
    assert account_order(browser) == list(ACCOUNT_IDS)
    assert driver.switch_to.active_element == browser.find(first).raw()
    browser.find(first).send_keys(Keys.ARROW_DOWN)
    assert browser.text('#accounts-dirty') == '有未应用的修改'
    assert account_file_rows(browser.host) == old_rows

    browser.click('#save-accounts')
    browser.wait.until(lambda _: not browser.text('#accounts-dirty'))
    assert account_file_rows(browser.host) == [old_rows[1], old_rows[0], old_rows[2]]
    assert [bot.id for bot in browser.host.accounts.values()] == [51002, 51001, 51003]
    assert driver.execute_script('return state.revision') != revision
    assert selected_accounts(browser) == []
    driver.refresh()
    browser.wait.until(lambda _: browser.find('#accounts').is_displayed())
    assert account_order(browser) == [51002, 51001, 51003]


def observe_account_pointer(browser):
    browser.driver.execute_script('''
        document.addEventListener('pointerdown', event => {
          const handle = event.target.closest('.account-drag-handle');
          if (handle) window.accountTestPointer = {
            handle, id: event.pointerId, type: event.pointerType, trusted: event.isTrusted,
          };
        }, true);
    ''')


def account_pointer_capture(browser, pointer_type):
    return browser.driver.execute_script('''
        const pointer = window.accountTestPointer;
        return !!pointer && pointer.trusted && pointer.type === arguments[0] &&
          pointer.handle.hasPointerCapture(pointer.id) &&
          pointer.handle.closest('tr').classList.contains('account-row-dragging');
    ''', pointer_type)


def account_drag_coordinates(browser):
    return browser.driver.execute_script('''
        const row = document.querySelector('#account-rows tr:first-child');
        const handle = row.querySelector('.account-drag-handle').getBoundingClientRect();
        const last = document.querySelector('#account-rows tr:last-child').getBoundingClientRect();
        return [Math.round(handle.left + handle.width / 2), Math.round(handle.top + handle.height / 2),
          Math.floor(last.top + last.height * 0.8)];
    ''')


def mouse_account_pointer(browser, event_type, x, y):
    phase = {
        'mousePressed': {'button': 'left', 'buttons': 1, 'clickCount': 1},
        # Chromium CDP 的鼠标移动需同时传 button 和 buttons，才能把事件投递给已捕获指针的元素。
        'mouseMoved': {'button': 'left', 'buttons': 1},
        'mouseReleased': {'button': 'left', 'buttons': 0, 'clickCount': 1},
    }
    browser.driver.execute_cdp_cmd('Input.dispatchMouseEvent', dict(type=event_type, x=x, y=y, **phase[event_type]))


@pytest.mark.browser
def test_account_mouse_drag_uses_threshold_and_captures_outside_handle(account_transfer):
    browser = account_transfer
    browser.click(f'{account_row(1)} .account-select')
    observe_account_pointer(browser)
    x, y, target = account_drag_coordinates(browser)
    mouse_account_pointer(browser, 'mousePressed', x, y)
    try:
        mouse_account_pointer(browser, 'mouseMoved', x, y + 2)
        assert not account_pointer_capture(browser, 'mouse')
    finally:
        mouse_account_pointer(browser, 'mouseReleased', x, y + 2)
    assert account_order(browser) == list(ACCOUNT_IDS)
    assert not browser.text('#accounts-dirty')

    mouse_account_pointer(browser, 'mousePressed', x, y)
    try:
        mouse_account_pointer(browser, 'mouseMoved', x, target)
        assert account_pointer_capture(browser, 'mouse')
        assert account_order(browser) == list(ACCOUNT_IDS)
        assert not browser.text('#accounts-dirty')
        motion = browser.driver.execute_script('''
            const rows = [...document.querySelectorAll('#account-rows tr')];
            const shiftY = (node) => new DOMMatrixReadOnly(getComputedStyle(node).transform).m42;
            const targetY = (node) => {
              const match = node.style.transform.match(/translate3d\\([^,]+,\\s*([-\\d.]+)px/);
              return match ? Number(match[1]) : 0;
            };
            return {
              sorting: document.getElementById('account-rows').classList.contains('account-rows-sorting'),
              bodyDragging: document.body.classList.contains('account-dragging-active'),
              draggedY: shiftY(rows[0]),
              sibling1TargetY: targetY(rows[1]),
              sibling2TargetY: targetY(rows[2]),
              siblingTransition: getComputedStyle(rows[1]).transitionProperty,
            };
        ''')
        assert motion['sorting'] and motion['bodyDragging']
        assert motion['draggedY'] > 20
        assert motion['sibling1TargetY'] < -20 and motion['sibling2TargetY'] < -20
        assert 'transform' in motion['siblingTransition']
    finally:
        mouse_account_pointer(browser, 'mouseReleased', x, target)
    assert account_order(browser) == [51002, 51003, 51001]
    assert selected_accounts(browser) == [51001]
    assert browser.text('#accounts-dirty') == '有未应用的修改'
    assert browser.driver.execute_script('''
        const rows = [...document.querySelectorAll('#account-rows tr')];
        return !document.getElementById('account-rows').classList.contains('account-rows-sorting') &&
          !document.body.classList.contains('account-dragging-active') &&
          rows.every(row => row.style.transform === '');
    ''')


@pytest.mark.browser
def test_account_sort_animates_reorder_and_respects_reduced_motion(account_transfer):
    from selenium.webdriver.common.keys import Keys

    browser = account_transfer
    driver = browser.driver
    driver.execute_script('''
        const originalAnimate = Element.prototype.animate;
        window.accountSortAnimations = [];
        Element.prototype.animate = function(keyframes, options) {
          if (this.matches('#account-rows tr')) {
            window.accountSortAnimations.push({
              rowId: this.dataset.accountRowId,
              from: keyframes[0]?.transform || '',
              to: keyframes.at(-1)?.transform || '',
              duration: options?.duration || 0,
            });
          }
          return originalAnimate.call(this, keyframes, options);
        };
    ''')
    driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
        'features': [{'name': 'prefers-reduced-motion', 'value': 'no-preference'}],
    })
    try:
        browser.find(f'{account_row(1)} .account-drag-handle').send_keys(Keys.ARROW_DOWN)
        assert account_order(browser) == [51002, 51001, 51003]
        recorded = driver.execute_script('return window.accountSortAnimations')
        assert len(recorded) == 2
        assert all(item['from'].startswith('translate3d(0, ') and item['to'] == 'translate3d(0, 0, 0)'
                   and item['duration'] > 0 for item in recorded)
        browser.wait.until(lambda _: driver.execute_script('''
            const rows = [...document.querySelectorAll('#account-rows tr')];
            return rows.every(row => !row.classList.contains('account-row-settling') &&
              row.getAnimations().every(animation => animation.playState === 'finished'));
        '''))

        driver.execute_script('window.accountSortAnimations = [];')
        driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
            'features': [{'name': 'prefers-reduced-motion', 'value': 'reduce'}],
        })
        browser.find(f'{account_row(2)} .account-drag-handle').send_keys(Keys.ARROW_UP)
        assert account_order(browser) == list(ACCOUNT_IDS)
        assert driver.execute_script('return window.accountSortAnimations') == []
    finally:
        driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {'features': []})


@pytest.mark.browser
def test_account_drag_defers_status_redraw_and_escape_keeps_selection(account_transfer):
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait

    browser = account_transfer
    observe_account_pointer(browser)
    browser.click(f'{account_row(1)} .account-select')
    x, y, target = account_drag_coordinates(browser)
    mouse_account_pointer(browser, 'mousePressed', x, y)
    try:
        mouse_account_pointer(browser, 'mouseMoved', x, target)
        assert account_pointer_capture(browser, 'mouse')
        # 真正的状态轮询应读到连接变化，但拖动中的行要保持不动，直到 Escape 取消。
        with browser.host.lock:
            browser.host.runtime['fixture-link'] = SimpleNamespace(
                Proc_type='fixture', bot_info=next(iter(browser.host.accounts.values())), active_links=0)
            browser.host.update_available = True
        WebDriverWait(browser.driver, 15).until(lambda driver: driver.execute_script('''
            return document.querySelector('#update-status').textContent.includes('发现可用更新');
        '''))
        assert account_pointer_capture(browser, 'mouse')
        assert not account_table(browser)[0]['offline']
        assert selected_accounts(browser) == [51001]

        ActionChains(browser.driver).send_keys(Keys.ESCAPE).perform()
        browser.wait.until(lambda _: account_table(browser)[0]['offline'])
        assert not account_pointer_capture(browser, 'mouse')
    finally:
        mouse_account_pointer(browser, 'mouseReleased', x, target)
    assert account_order(browser) == list(ACCOUNT_IDS)
    assert selected_accounts(browser) == [51001]
    assert not browser.text('#accounts-dirty')


@pytest.mark.browser
def test_account_drag_scrolls_to_rows_below_the_viewport(account_transfer):
    browser = account_transfer
    driver = browser.driver
    set_viewport(browser, 1000, 315)
    x, y, target = account_drag_coordinates(browser)
    bottom = driver.execute_script('return innerHeight')
    assert y < bottom < target
    observe_account_pointer(browser)
    assert driver.execute_script('''
        return document.elementFromPoint(arguments[0], arguments[1])?.matches('.account-drag-handle');
    ''', x, y)
    mouse_account_pointer(browser, 'mousePressed', x, y)
    try:
        mouse_account_pointer(browser, 'mouseMoved', x, bottom - 8)
        assert account_pointer_capture(browser, 'mouse')
        browser.wait.until(lambda _: driver.execute_script('''
            const main = document.querySelector('main');
            const last = document.querySelector('#account-rows tr:last-child');
            return main.scrollTop > 0 && last.classList.contains('account-drop-after');
        '''))
    finally:
        mouse_account_pointer(browser, 'mouseReleased', x, bottom - 8)
    assert account_order(browser) == [51002, 51003, 51001]


@pytest.mark.browser
def test_account_touch_drag_can_cancel_and_reorder_at_320px(account_transfer):
    browser = account_transfer
    driver = browser.driver
    set_viewport(browser, 320, 640, mobile_device=True)
    assert driver.execute_script('''
        const handle = document.querySelector('#account-rows .account-drag-handle');
        const check = document.querySelector('#account-rows .account-select');
        const h = handle.getBoundingClientRect();
        const c = check.getBoundingClientRect();
        return innerWidth === 320 && document.documentElement.scrollWidth === innerWidth &&
          h.left >= 0 && h.right <= c.left && c.right <= innerWidth &&
          h.width >= 44 && h.height >= 44 && h.top < c.bottom && c.top < h.bottom &&
          getComputedStyle(handle).touchAction === 'none';
    ''')
    observe_account_pointer(browser)
    x, y, target = account_drag_coordinates(browser)

    def touch(event_type, point_y=None):
        points = [] if point_y is None else [{'x': x, 'y': point_y, 'id': 0}]
        driver.execute_cdp_cmd('Input.dispatchTouchEvent', {'type': event_type, 'touchPoints': points})

    driver.execute_cdp_cmd('Emulation.setTouchEmulationEnabled', {'enabled': True, 'maxTouchPoints': 1})
    try:
        touch('touchStart', y)
        touch('touchMove', target)
        assert account_pointer_capture(browser, 'touch')
        touch('touchCancel')
        assert account_order(browser) == list(ACCOUNT_IDS)
        assert not browser.text('#accounts-dirty')
        assert not account_pointer_capture(browser, 'touch')

        touch('touchStart', y)
        touch('touchMove', target)
        assert account_pointer_capture(browser, 'touch')
        touch('touchEnd')
        assert account_order(browser) == [51002, 51003, 51001]
        assert browser.text('#accounts-dirty') == '有未应用的修改'
    finally:
        driver.execute_cdp_cmd('Emulation.setTouchEmulationEnabled', {'enabled': False})


def assert_account_export(text, ids):
    payload = json.loads(text)
    assert list(payload) == ['account']
    assert [int(row['id']) for row in payload['account']] == ids
    # Windows 剪贴板会转换换行；保留对 JSON 缩进和内容的严格检查。
    assert text.replace('\r\n', '\n') == json.dumps(payload, indent=2, ensure_ascii=False)
    for row in payload['account']:
        assert set(row) == set(transfer_account(row['id']))
        assert row['password'] == f'fixture-password-{row["id"]}'
        assert row['server']['access_token'] == f'fixture-token-{row["id"]}'


@pytest.mark.browser
def test_account_row_copy_and_batch_copy_use_browser_clipboard(account_transfer):
    from selenium.webdriver.common.keys import Keys

    browser = account_transfer
    driver = browser.driver
    origin = driver.execute_script('return location.origin')
    driver.execute_cdp_cmd('Browser.grantPermissions', {
        'origin': origin, 'permissions': ['clipboardReadWrite', 'clipboardSanitizedWrite'],
    })
    driver.execute_script('''
        const execCommand = document.execCommand.bind(document);
        document.execCommand = (command, ...args) => command === 'copy' ? false : execCommand(command, ...args);
    ''')

    def expect_copy(ids):
        browser.wait.until(lambda _: browser.text('#notice-message') == f'已复制 {len(ids)} 个账号。')
        text = driver.execute_async_script('''
            const done = arguments[0];
            navigator.clipboard.readText().then(done, error => done({error: error.message}));
        ''')
        assert isinstance(text, str), text
        assert_account_export(text, ids)

    try:
        browser.click(f'{account_row(2)} .account-select')
        row_copy = f'{account_row(1)} .actions button:nth-child(3)'
        assert browser.text(row_copy) == '复制'
        browser.click(row_copy)
        expect_copy([51001])
        assert selected_accounts(browser) == [51002]
        assert not browser.find('#account-copy-fallback-dialog').is_displayed()

        browser.click(f'{account_row(1)} .account-select')
        browser.find(f'{account_row(1)} .account-drag-handle').send_keys(Keys.ARROW_DOWN)
        browser.click('#export-accounts-copy')
        expect_copy([51002, 51001])
        browser.click(f'{account_row(3)} .account-select')
        browser.click('#export-accounts-menu-toggle')
        browser.click('#account-export-clipboard')
        expect_copy([51002, 51001, 51003])
        open_clipboard_import(browser)
        preview = browser.wait.until(lambda _: import_list(browser))
        assert len(preview) == 3
        for row, account_id in zip(preview, [51002, 51001, 51003]):
            assert str(account_id) in row['text'] and '重复 · 覆盖' in row['text']
        assert not browser.find('#account-import-text').is_displayed()
        browser.click(ACCOUNT_IMPORT_CANCEL)
    finally:
        driver.execute_cdp_cmd('Browser.resetPermissions', {})


@pytest.mark.browser
def test_account_export_strips_qsign_editor_metadata(account_transfer):
    from selenium.webdriver.common.keys import Keys

    browser = account_transfer
    driver = browser.driver
    browser.click(f'{account_row(1)} .actions button:nth-child(2)')
    browser.click('#account-form details > summary')
    server = {'addr': 'http://127.0.0.1:8080', 'key': 'fixture-signing-key'}
    browser.find('#account-extends').send_keys(Keys.CONTROL, 'a', Keys.NULL, Keys.BACKSPACE)
    browser.type_text('#account-extends', json.dumps({'qsign-server': [dict(server, _source_index=-1)]}))
    browser.click('#account-form button[type="submit"]')
    browser.wait.until(lambda _: not browser.find('#account-dialog').is_displayed())
    driver.execute_script('''
        Object.defineProperty(navigator, 'clipboard', {configurable: true, value: undefined});
        document.execCommand = () => false;
    ''')
    browser.click(f'{account_row(1)} .actions button:nth-child(3)')
    browser.wait.until(lambda _: browser.find('#account-copy-fallback-dialog').is_displayed())
    text = browser.attribute('#account-copy-fallback-text', 'value')
    assert_account_export(text, [51001])
    assert json.loads(text)['account'][0]['extends']['qsign-server'] == [server]


@pytest.mark.browser
@pytest.mark.parametrize('legacy_available', [True, False], ids=['legacy-copy', 'manual-copy'])
def test_account_copy_falls_back_when_clipboard_write_is_denied(account_transfer, legacy_available):
    browser = account_transfer
    driver = browser.driver
    driver.execute_script('''
        const legacyAvailable = arguments[0];
        const execCommand = document.execCommand.bind(document);
        window.accountTestCopy = [];
        Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
          writeText: () => {
            window.accountTestCopy.push('writeText');
            return Promise.reject(new DOMException('Denied', 'NotAllowedError'));
          },
        }});
        document.execCommand = (command, ...args) => {
          if (command !== 'copy') return execCommand(command, ...args);
          const field = document.activeElement;
          window.accountTestCopy.push('execCommand', field.value.slice(field.selectionStart, field.selectionEnd));
          return legacyAvailable;
        };
    ''', legacy_available)
    browser.click(f'{account_row(1)} .actions button:nth-child(3)')
    calls = browser.wait.until(lambda _: driver.execute_script(
        'return window.accountTestCopy.length === 3 && window.accountTestCopy'))
    assert calls[:2] == ['writeText', 'execCommand']
    assert_account_export(calls[2], [51001])
    dialog = '#account-copy-fallback-dialog'
    if legacy_available:
        assert not browser.find(dialog).is_displayed()
    else:
        browser.wait.until(lambda _: browser.find(dialog).is_displayed())
        assert driver.execute_script('''
            const text = document.querySelector('#account-copy-fallback-text');
            return document.activeElement === text && text.readOnly &&
              text.selectionStart === 0 && text.selectionEnd === text.value.length && text.value;
        ''') == calls[2]
        browser.click(f'{dialog} .dialog-actions button')
        assert not browser.find(dialog).is_displayed()


def clipboard_import_value(browser, value=None, *, denied=False):
    browser.driver.execute_script('''
        const [text, denied] = arguments;
        Object.defineProperty(navigator, 'clipboard', {configurable: true, value: text === null && !denied
          ? undefined : {readText: () => denied
            ? Promise.reject(new DOMException('Denied', 'NotAllowedError')) : Promise.resolve(text)}});
    ''', value, denied)


def open_clipboard_import(browser):
    browser.click('#add-account-menu-toggle')
    browser.click('#account-import-clipboard')
    browser.wait.until(lambda _: browser.find(ACCOUNT_IMPORT).is_displayed())


def import_list(browser):
    return browser.driver.execute_script('''
        return Array.from(document.querySelectorAll('#account-import-list li'), row => {
          const box = row.querySelector('input[type="checkbox"]');
          return {text: row.innerText, checked: box.checked, disabled: box.disabled};
        });
    ''')


def import_checkbox(preview, account_id):
    position = next(i for i, row in enumerate(preview, 1) if str(account_id) in row['text'])
    return f'#account-import-list li:nth-child({position}) input[type="checkbox"]'


def upload_account_json(browser, path):
    from selenium.webdriver.common.by import By

    driver = browser.driver
    driver.execute_cdp_cmd('Page.setInterceptFileChooserDialog', {'enabled': True})
    try:
        browser.click('#add-account-menu-toggle')
        browser.click('#account-import-file-trigger')
        # WebDriver 为真实文件输入选择本地文件，应用仍负责读取、校验和清空输入。
        driver.find_element(By.ID, 'account-import-file').send_keys(str(path.resolve()))
        browser.wait.until(lambda _: browser.find(ACCOUNT_IMPORT).is_displayed())
        browser.wait.until(lambda _: not browser.attribute('#account-import-file', 'value'))
    finally:
        driver.execute_cdp_cmd('Page.setInterceptFileChooserDialog', {'enabled': False})


@pytest.mark.browser
def test_account_json_download_and_repeated_upload_round_trip(account_transfer, tmp_path):
    from selenium.webdriver.common.keys import Keys

    browser = account_transfer
    driver = browser.driver
    downloads = tmp_path / 'downloads'
    downloads.mkdir()
    path = downloads / 'account.json'
    driver.execute_cdp_cmd('Browser.setDownloadBehavior', {'behavior': 'allow', 'downloadPath': str(downloads)})
    try:
        browser.find(f'{account_row(1)} .account-drag-handle').send_keys(Keys.ARROW_DOWN)
        browser.click('#accounts-select-all')
        browser.click('#export-accounts-menu-toggle')
        browser.click('#account-export-file')
        browser.wait.until(lambda _: path.is_file())
        assert_account_export(path.read_text(encoding='utf-8'), [51002, 51001, 51003])
    finally:
        driver.execute_cdp_cmd('Browser.setDownloadBehavior', {'behavior': 'default'})

    for _ in range(2):
        upload_account_json(browser, path)
        preview = browser.wait.until(lambda _: import_list(browser))
        assert len(preview) == 3
        for row, account_id in zip(preview, [51002, 51001, 51003]):
            assert str(account_id) in row['text'] and '重复 · 覆盖' in row['text']
            assert row['checked'] and not row['disabled']
        browser.click(ACCOUNT_IMPORT_CANCEL)
        assert not browser.find(ACCOUNT_IMPORT).is_displayed()
    assert account_order(browser) == [51002, 51001, 51003]
    assert [row['id'] for row in account_file_rows(browser.host)] == list(ACCOUNT_IDS)


@pytest.mark.browser
@pytest.mark.parametrize(('content', 'error'), [
    (b'not JSON', r'JSON|解析'),
    (b' ' * (1024 * 1024 + 1), r'1\s*Mi?B|大小|过大|超过'),
    (b'{"account": {}}', r'account|数组|格式'),
], ids=['invalid-json', 'oversize', 'invalid-wrapper'])
def test_account_file_import_reports_invalid_input(account_transfer, tmp_path, content, error):
    browser = account_transfer
    path = tmp_path / 'invalid.json'
    path.write_bytes(content)
    upload_account_json(browser, path)
    browser.wait.until(lambda _: re.search(error, browser.text('#account-import-error')))
    assert import_list(browser) == [] and not browser.find('#account-import-confirm').is_enabled()
    assert account_order(browser) == list(ACCOUNT_IDS)
    assert not browser.text('#accounts-dirty')


@pytest.mark.browser
@pytest.mark.parametrize('shape', ['wrapped', 'array', 'single'])
def test_clipboard_account_import_always_previews_before_staging(account_transfer, shape):
    browser = account_transfer
    account_id = 123456789012345678 if shape == 'single' else 51004
    row = transfer_account(account_id)
    clipboard_import_value(browser, json.dumps({'wrapped': {'account': [row]}, 'array': [row], 'single': row}[shape]))
    open_clipboard_import(browser)
    preview, = browser.wait.until(lambda _: import_list(browser))
    assert all(text in preview['text'] for text in ('新增', str(account_id), 'qq', 'onebot', 'default'))
    assert preview['checked'] and not preview['disabled']
    assert not browser.find('#account-import-text').is_displayed()
    assert browser.text('#account-import-confirm') == '确认导入（新增 1，覆盖 0）'
    assert account_order(browser) == list(ACCOUNT_IDS)
    assert not browser.text('#accounts-dirty')

    browser.click('#account-import-confirm')
    assert not browser.find(ACCOUNT_IMPORT).is_displayed()
    assert account_order(browser) == [*ACCOUNT_IDS, account_id]
    assert browser.text('#accounts-dirty') == '有未应用的修改'
    assert [row['id'] for row in account_file_rows(browser.host)] == list(ACCOUNT_IDS)


@pytest.mark.browser
@pytest.mark.parametrize(('value', 'denied'), [(None, False), (None, True), ('', False), ('{', False)],
                         ids=['unavailable', 'permission-denied', 'empty', 'invalid-json'])
def test_clipboard_account_import_opens_manual_paste_and_can_cancel(account_transfer, value, denied):
    from selenium.webdriver.common.keys import Keys

    browser = account_transfer
    if denied:
        set_viewport(browser, 320, 640, mobile_device=True)
    clipboard_import_value(browser, value, denied=denied)
    open_clipboard_import(browser)
    browser.wait.until(lambda _: '解析 JSON' in browser.text('#account-import-error'))
    assert not browser.find('#account-import-confirm').is_enabled()
    field = '#account-import-text'
    assert browser.driver.switch_to.active_element == browser.find(field).raw()
    if denied:
        assert browser.driver.execute_script('''
            const rect = document.querySelector('#account-import-dialog').getBoundingClientRect();
            return innerWidth === 320 && rect.left >= 0 && rect.right <= innerWidth &&
              rect.top >= 0 && rect.bottom <= innerHeight;
        ''')
    browser.find(field).send_keys(Keys.CONTROL, 'a', Keys.NULL, Keys.BACKSPACE)
    browser.type_text(field, json.dumps(transfer_account(51004)))
    browser.click('#account-import-parse')
    preview, = browser.wait.until(lambda _: import_list(browser))
    assert '新增' in preview['text'] and '51004' in preview['text']
    assert not browser.text('#account-import-error')
    browser.click(ACCOUNT_IMPORT_CANCEL)
    assert not browser.find(ACCOUNT_IMPORT).is_displayed()
    assert account_order(browser) == list(ACCOUNT_IDS)
    assert not browser.text('#accounts-dirty')


@pytest.mark.browser
def test_account_import_merges_duplicates_sanitizes_and_selectively_replaces_drafts(account_transfer):
    browser = account_transfer
    driver = browser.driver
    original = account_file_rows(browser.host)
    local_hash = driver.execute_script('return state.accounts[0].hash')

    # 先建立尚未保存的账号；下一次预览必须和当前草稿而不是磁盘比对。
    clipboard_import_value(browser, json.dumps(transfer_account(51004)))
    open_clipboard_import(browser)
    browser.click('#account-import-confirm')
    browser.click(f'{account_row(1)} .account-select')

    earlier = transfer_account(51001, password='fixture-discarded-password')
    latest = transfer_account(51001, hash='fixture-foreign-hash', password='fixture-new-password')
    latest['server']['access_token'] = 'fixture-new-access-token'
    added = transfer_account(51005, hash='fixture-new-foreign-hash', extends={
        'qsign-server': [{'addr': 'http://127.0.0.1:8080', 'key': 'fixture-qsign-key', '_source_index': -99}],
    })
    masked = transfer_account(51006, password='********')
    malformed = transfer_account({'password': 'fixture-invalid-id-password'})
    payload = [earlier, transfer_account(51002, enable=False), latest, masked, added,
               transfer_account(51004, debug=True), malformed]
    clipboard_import_value(browser, json.dumps({'account': payload}))
    set_viewport(browser, 320, 568, mobile_device=True)
    open_clipboard_import(browser)
    preview = browser.wait.until(lambda _: import_list(browser))
    assert len(preview) == 6
    assert sum(row['disabled'] for row in preview) == 2
    assert all(row['checked'] != row['disabled'] for row in preview)
    assert sum('重复 · 覆盖' in row['text'] for row in preview) == 3
    assert sum('无效' in row['text'] for row in preview) == 2
    assert any('新增' in row['text'] and '51005' in row['text'] for row in preview)
    assert any('51006' in row['text'] and re.search(r'脱敏|占位', row['text']) for row in preview)
    counts = browser.text('#account-import-counts')
    assert re.search(r'总数\s*7\s*·\s*新增\s*1\s*·\s*重复\s*3\s*·\s*无效\s*2', counts)
    assert re.search(r'已合并批内重复\s*1\s*条', counts)
    assert browser.text('#account-import-confirm') == '确认导入（新增 1，覆盖 3）'
    assert driver.execute_script('''
        const confirm = document.querySelector('#account-import-confirm');
        const rect = confirm.getBoundingClientRect();
        const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
        return innerWidth === 320 && innerHeight === 568 && rect.left >= 0 && rect.right <= innerWidth &&
          rect.top >= 0 && rect.bottom <= innerHeight && confirm.contains(hit);
    ''')
    dialog = browser.text(ACCOUNT_IMPORT)
    for private in (earlier['password'], latest['password'], latest['server']['access_token'],
                    original[0]['password'], original[0]['server']['access_token'], 'fixture-qsign-key',
                    'fixture-invalid-id-password', 'fixture-foreign-hash', '********', 'previous-fixture-value'):
        assert private not in dialog

    added_checkbox = import_checkbox(preview, 51005)
    skipped_checkbox = import_checkbox(preview, 51002)
    browser.click('#account-import-uncheck-conflicts')
    assert browser.text('#account-import-confirm') == '确认导入（新增 1，覆盖 0）'
    browser.click(added_checkbox)
    assert not browser.find('#account-import-confirm').is_enabled()
    browser.click('#account-import-check-conflicts')
    assert browser.text('#account-import-confirm') == '确认导入（新增 0，覆盖 3）'
    browser.click(added_checkbox)
    browser.click(skipped_checkbox)
    assert browser.text('#account-import-confirm') == '确认导入（新增 1，覆盖 2）'

    browser.click('#account-import-confirm')
    assert not browser.find(ACCOUNT_IMPORT).is_displayed()
    assert account_order(browser) == [*ACCOUNT_IDS, 51004, 51005]
    assert selected_accounts(browser) == [51001]
    assert driver.execute_script('return [state.accounts[0].hash, state.accounts.at(-1).hash ?? null]') == [
        local_hash, None,
    ]
    assert browser.text('#accounts-dirty') == '有未应用的修改'
    assert account_file_rows(browser.host) == original

    browser.click('#save-accounts')
    browser.wait.until(lambda _: not browser.text('#accounts-dirty'))
    saved = account_file_rows(browser.host)
    assert [row['id'] for row in saved] == [*ACCOUNT_IDS, 51004, 51005]
    assert saved[0]['password'] == latest['password']
    assert saved[0]['server']['access_token'] == latest['server']['access_token']
    assert saved[0].get('extends', {}) == {}
    assert driver.execute_script('return state.accounts[0].hash') == local_hash
    assert saved[1:3] == original[1:3]
    assert saved[3]['debug'] is True
    assert saved[4]['extends']['qsign-server'] == [{'addr': 'http://127.0.0.1:8080', 'key': 'fixture-qsign-key'}]
    assert selected_accounts(browser) == []


@pytest.mark.browser
def test_account_transfer_review_edge_cases(account_transfer):
    browser = account_transfer
    driver = browser.driver

    # 1) 导出菜单展开时点击主按钮「复制所选」必须同时关闭下拉菜单，且异步双触发降级弹窗不抛 InvalidStateError。
    driver.execute_script('''
        window.accountCopyRejects = [];
        Object.defineProperty(navigator, 'clipboard', {configurable: true, value: {
          writeText: () => new Promise((_, reject) => {
            window.accountCopyRejects.push(() => reject(new DOMException('Denied', 'NotAllowedError')));
          }),
        }});
        document.execCommand = () => false;
    ''')
    browser.click(f'{account_row(1)} .account-select')
    browser.click('#export-accounts-menu-toggle')
    wait_account_menu_open(browser, '#account-export-menu')
    browser.click('#export-accounts-copy')
    assert not browser.find('#account-export-menu').is_displayed()
    assert browser.attribute('#export-accounts-menu-toggle', 'aria-expanded') == 'false'
    browser.click('#export-accounts-copy')
    browser.wait.until(lambda _: driver.execute_script('return window.accountCopyRejects.length === 2'))
    driver.execute_script('for (const reject of window.accountCopyRejects) reject();')
    browser.wait.until(lambda _: browser.find('#account-copy-fallback-dialog').is_displayed())
    assert not browser.find('#notice').is_displayed()
    browser.click('#account-copy-fallback-dialog .dialog-actions button')
    assert not browser.find('#account-copy-fallback-dialog').is_displayed()

    # 2) 未保存的编辑草稿带前导零 ID 和字符串端口时，导出端口应归一化为整数且导入预览能正确识别重复与无差异。
    browser.click('#add-account')
    browser.find('#account-form [data-field="id"]').send_keys('0051009')
    browser.click('#account-form details > summary')
    browser.type_text('#account-form [data-field="server.host"]', 'http://127.0.0.1')
    browser.type_text('#account-form [data-field="server.port"]', '5700')
    browser.type_text('#account-form [data-field="server.access_token"]', 'fixture-token-51009')
    browser.click('#account-form button[type="submit"]')
    browser.wait.until(lambda _: not browser.find('#account-dialog').is_displayed())
    exported = json.loads(driver.execute_script('return accountExportText([state.accounts.at(-1)])'))
    assert exported['account'][0]['server']['port'] == 5700
    assert isinstance(exported['account'][0]['server']['port'], int)

    clipboard_import_value(browser, json.dumps([exported['account'][0], {'id': ''}]))
    open_clipboard_import(browser)
    preview = browser.wait.until(lambda _: import_list(browser))
    assert len(preview) == 2
    assert '重复 · 覆盖' in preview[0]['text'] and '51009' in preview[0]['text'] and '配置相同' in preview[0]['text']
    assert '无效' in preview[1]['text'] and '账号 —' in preview[1]['text'] and '— · — / —' in preview[1]['text']
    browser.click(ACCOUNT_IMPORT_CANCEL)
    assert not browser.find(ACCOUNT_IMPORT).is_displayed()

    # 3) 剪贴板导入超过 1 MB 时在前端直接给出明确提示，不落到 413 通用错误。
    clipboard_import_value(browser, '{"x":"' + 'a' * (1024 * 1024) + '"}')
    open_clipboard_import(browser)
    browser.wait.until(lambda _: re.search(r'1\s*Mi?B|超过', browser.text('#account-import-error')))
    assert '413' not in browser.text('#account-import-error')
    browser.click(ACCOUNT_IMPORT_CANCEL)
    assert not browser.find(ACCOUNT_IMPORT).is_displayed()


@pytest.mark.browser
def test_mobile_custom_select_menu_opens_above_and_fits_viewport(browser):
    driver = browser.driver
    set_viewport(browser, 320, 568)
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
    set_viewport(browser, width, 844)
    browser.open_sidebar()
    assert driver.execute_script('return document.documentElement.scrollWidth <= innerWidth')
    assert driver.execute_script('''
        const sidebar = document.getElementById('sidebar').getBoundingClientRect();
        return sidebar.right <= innerWidth && sidebar.width <= innerWidth &&
          document.querySelector('.sidebar-head').getBoundingClientRect().top === 0;
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

    def padded(values, capacity, lead=0):
        missing = max(0, capacity - len(values))
        if lead == 'first' and values:
            lead = values[0]
        return [lead] * missing + values[-capacity:]

    def performance_window(interval, cpu_value, capacity=60):
        series_timestamps = window_timestamps(capacity, interval)
        series = {key: [cpu_value, cpu_value + 1, cpu_value + 2] for key in (
            'cpu_percent', 'load_1', 'memory_percent', 'swap_percent', 'swap_in_bps',
            'swap_out_bps', 'disk_percent', 'disk_read_bps', 'disk_write_bps',
            'network_recv_bps', 'network_sent_bps', 'process_count', 'process_rss',
            'process_cpu_percent', 'process_threads', 'process_handles',
        )}
        # 进程与线程数量使用独立序列，便于验证缩略图确实使用线程数而非进程数。
        series['process_count'] = [3, 3, 4]
        series['process_threads'] = [18, 19, 20]
        series = {key: padded(item, capacity, 'first') for key, item in series.items()}
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
    # 读取图表容量与每条折线的实际点数，用于验证空桶回填后横轴点位固定。
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
          rows: [...tooltip.querySelectorAll('.chart-tooltip-row')].map((row) => {
            const label = row.querySelector('.chart-tooltip-label');
            const value = row.querySelector('.chart-tooltip-value');
            return {
              label: label ? label.textContent : '',
              value: value ? value.textContent : '',
            };
          }),
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
    cpu_ring = '.metric-ring-card[data-ring="cpu"] .metric-ring'
    assert abs(float(browser.attribute(cpu_ring, 'data-secondary-percent')) - 1.5625) < 0.0001
    assert abs(float(browser.attribute(f'{cpu_ring} .metric-ring-secondary', 'stroke-dashoffset')) - 98.4375) < 0.0001
    memory_text = metric_card_text(driver, '内存')
    assert 'OlivOS 256.0 MiB (1.6%)' in memory_text and '| OlivOS 256.0 MiB' in memory_text
    assert '换入' not in memory_text and '换出' not in memory_text
    memory_ring = '.metric-ring-card[data-ring="memory"] .metric-ring'
    assert abs(float(browser.attribute(memory_ring, 'data-secondary-percent')) - 1.5625) < 0.0001
    memory_arc = f'{memory_ring} .metric-ring-secondary'
    assert abs(float(browser.attribute(memory_arc, 'stroke-dashoffset')) - 98.4375) < 0.0001
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
    # CPU/内存/磁盘/网络图固定 120 点容量，收发消息与失败事件图沿用统计模块的 60 点容量；
    # 性能序列左侧空槽用最早有效值回填，流量计数序列才补零。
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
    # 左侧空槽用最早采样回填，不能把尚未采样的区域直接压到 0 基线。
    leading_cpu = driver.execute_script("""
        const line = document.querySelector('#dashboard-cpu-chart .chart-series-cpu');
        const points = line.getAttribute('points').trim().split(/\\s+/);
        const history = state.statistics.performance.history.cpu_percent;
        return {
          first: points[0].split(',')[1],
          firstActual: points[points.length - history.length].split(',')[1],
          baseline: '38.00',
        };
    """)
    assert leading_cpu['first'] == leading_cpu['firstActual']
    assert leading_cpu['first'] != leading_cpu['baseline']
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
    navigation_button = '#navigation [data-page="performance"]'
    category_button = '[data-performance-category="overview"]'
    pressed_script = """
        const style = getComputedStyle(document.querySelector(arguments[0]));
        return {
          background: style.backgroundColor,
          border: style.borderColor,
          shadow: style.boxShadow,
          outline: style.outline,
        };
    """
    browser.press(navigation_button)
    time.sleep(0.2)
    navigation_pressed = driver.execute_script(pressed_script, navigation_button)
    browser.release()
    time.sleep(0.05)
    browser.press(category_button)
    time.sleep(0.2)
    category_pressed = driver.execute_script(pressed_script, category_button)
    browser.release()
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
    process_summary = driver.execute_script(
        'return document.querySelector(`[data-performance-summary=processes]`).textContent')
    assert process_summary == '3 进程 · 18 线程'
    process_mini = driver.execute_script('''
        const svg = document.querySelector(`[data-performance-mini=processes] svg`);
        return {maximum: Number(svg.dataset.maximum),
                points: svg.querySelector('.mini-line').getAttribute('points')};
    ''')
    assert process_mini['maximum'] == 20
    assert process_mini['points']
    assert browser.find('#performance-process-count-readout').get_attribute(
        'textContent') == '3 进程 · 18 线程'
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
    browser.hover('#performance-process-tree .process-thread')
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
        'processes': [
            ('#performance-process-count-chart', ['进程数', '线程数']),
        ],
    }
    # 进程趋势图按“标签 → 数值”逐行精确比对，避免 '4'/'20' 命中 '14'/'120' 等错误计数。
    exact_tooltip_rows = {
        '#performance-process-count-chart': [('进程数', '4'), ('线程数', '20')],
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
            expected_rows = exact_tooltip_rows.get(selector)
            if expected_rows is not None:
                rows = [(row['label'], row['value']) for row in tooltip['rows']]
                assert rows == expected_rows, (category, selector, rows)
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
        "return document.querySelectorAll('#performance-content .performance-panel').length") == 16

    # 所有事实网格需按当前列数补齐占位项，占位项必须实际渲染且与普通事实单元格同色。
    categories = ('overview', 'cpu', 'memory', 'disk', 'network', 'traffic')
    expected_counts = {
        'overview': 6, 'cpu': 8, 'memory': 13, 'disk': 10, 'network': 8, 'traffic': 8,
    }

    def select_fact_category(category):
        browser.click(f'[data-performance-category="{category}"]')
        browser.wait.until(lambda _: driver.execute_script(
            "return !document.querySelector('[data-performance-view=\"' + arguments[0] + '\"]').hidden",
            category))
        # 等待视口变化触发的占位同步帧执行完成。
        driver.execute_async_script(
            'requestAnimationFrame(() => requestAnimationFrame(() => arguments[0]()));')

    def measure_fact_grid(category):
        return driver.execute_script("""
            const category = arguments[0];
            const grid = document.querySelector(
              `#performance-view-${category} .performance-fact-grid`);
            const template = getComputedStyle(grid).gridTemplateColumns;
            const repeated = template.match(/^repeat\\((\\d+),/);
            const visible = (node) => !node.hidden && getComputedStyle(node).display !== 'none';
            const facts = [...grid.children].filter(
              (node) => node.classList.contains('performance-fact') && visible(node));
            const fillers = facts.filter(
              (node) => node.classList.contains('performance-fact-empty'));
            return {
              count: facts.length - fillers.length,
              rendered: facts.length,
              columns: repeated ? Number(repeated[1]) : template.split(' ').filter(Boolean).length,
              factBackground: getComputedStyle(facts[0]).backgroundColor,
              fillerBackground: fillers.length
                ? getComputedStyle(fillers[0]).backgroundColor
                : null,
              fillersLaidOut: fillers.every((node) => {
                const rect = node.getBoundingClientRect();
                return rect.width > 0 && rect.height > 0;
              }),
            };
        """, category)

    def assert_fact_layout(expected_columns):
        for category in categories:
            select_fact_category(category)
            item = measure_fact_grid(category)
            assert item['count'] == expected_counts[category], category
            assert item['columns'] == expected_columns, category
            assert item['rendered'] % item['columns'] == 0, category
            assert item['fillerBackground'] in (None, item['factBackground']), category
            assert item['fillersLaidOut'], category

    set_viewport(browser, 1280, 800)
    assert_fact_layout(3)
    set_viewport(browser, 900, 800)
    assert_fact_layout(2)

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
def test_performance_process_tree_refresh_preserves_nodes(browser):
    # 轮询刷新只同步文本与属性，保留进程/线程节点，避免打断悬停、选中和展开。
    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page="performance"]')
    browser.click('[data-performance-category="processes"]')
    browser.wait.until(lambda _: driver.execute_script(
        "return document.querySelectorAll('#performance-process-tree .process-thread').length === 3"))
    original = driver.execute_script("""
        window.__processNode = document.querySelector('#performance-process-tree .process-node');
        window.__threadNode = document.querySelector('#performance-process-tree .process-thread');
        return window.__threadNode.textContent;
    """)
    assert 'CPU 50.0%' in original

    updated = process_tree_snapshot()
    updated['roots'][0]['threads'][0]['cpu_percent'] = 66.6
    browser.host.runtime['statistics'].process_tree_snapshot = lambda: updated
    driver.execute_async_script("""
        const done = arguments[0];
        refreshPerformanceProcesses().then(() => done(true), () => done(false));
    """)
    state = driver.execute_script("""
        const thread = document.querySelector('#performance-process-tree .process-thread');
        return {
          sameThread: thread === window.__threadNode,
          sameProcess: document.querySelector('#performance-process-tree .process-node') === window.__processNode,
          text: thread.textContent,
        };
    """)
    assert state['sameThread'] and state['sameProcess']
    assert 'CPU 66.6%' in state['text']


@pytest.mark.browser
def test_performance_process_tree_refresh_preserves_nodes_when_structure_changes(browser):
    # 新增线程、子进程或根进程时，只插入新增节点，不能把未变化节点从 DOM 中摘下来。
    driver = browser.driver
    snapshot = process_tree_snapshot()
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=lambda: snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page=performance]')
    browser.click('[data-performance-category=processes]')
    browser.wait.until(lambda _: driver.execute_script(
        r'''return document.querySelectorAll('#performance-process-tree .process-thread').length === 3'''))
    driver.execute_script('''
        const nodes = document.querySelectorAll('#performance-process-tree .process-node');
        window.__rootNode = nodes[0];
        window.__childNode = nodes[1];
        window.__threadNode = document.querySelector('#performance-process-tree .process-thread');
    ''')

    updated = process_tree_snapshot()
    root = updated['roots'][0]
    root['threads'].append({
        'id': 1004, 'user': 0.0, 'system': 0.0, 'cpu_percent': 5.0,
        'name': 'extra', 'state': 'S', 'start_time': PROCESS_ROOT_CREATED_AT + 5,
    })
    root['thread_count'] = 3
    updated['roots'].append({
        'pid': 2000, 'ppid': 1, 'name': 'helper.exe', 'status': 'running',
        'username': 'tester', 'create_time': PROCESS_ROOT_CREATED_AT - 5,
        'memory_rss': 32 * 1024 ** 2, 'memory_vms': 64 * 1024 ** 2,
        'thread_count': 0, 'threads': [], 'threads_truncated': False, 'children': [],
    })
    updated['process_count'] = 3
    updated['thread_count'] = 4
    browser.host.runtime['statistics'].process_tree_snapshot = lambda: updated
    driver.execute_async_script('''
        const done = arguments[0];
        refreshPerformanceProcesses().then(() => done(true), () => done(false));
    ''')
    state = driver.execute_script('''
        const roots = [...document.querySelectorAll(
          '#performance-process-tree .process-tree-list > .process-node')];
        return {
          sameRoot: roots[0] === window.__rootNode,
          sameChild: roots[0].querySelector('.process-node') === window.__childNode,
          sameThread: document.querySelector('#performance-process-tree .process-thread') ===
            window.__threadNode,
          rootCount: roots.length,
          childCount: roots[0].querySelectorAll('.process-children > .process-node').length,
          threadCount: document.querySelectorAll('#performance-process-tree .process-thread').length,
        };
    ''')
    assert state == {
        'sameRoot': True,
        'sameChild': True,
        'sameThread': True,
        'rootCount': 2,
        'childCount': 1,
        'threadCount': 4,
    }


@pytest.mark.browser
def test_performance_process_tree_refresh_preserves_live_toggle_state(browser):
    # 刷新先于排队的 toggle 处理器执行时，必须保留 details 的实时 open 状态，不能被旧快照覆盖。
    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page=performance]')
    browser.click('[data-performance-category=processes]')
    browser.wait.until(lambda _: driver.execute_script(
        r'''return document.querySelectorAll('#performance-process-tree .process-thread').length === 3'''))

    state = driver.execute_script('''
        const branch = document.querySelector('#performance-process-tree .process-branch');
        const key = branch.dataset.processBranch;
        branch.open = false;
        state.performanceProcessOpen[key] = true;
        renderProcessTree(state.performanceProcesses);
        const current = document.querySelector('#performance-process-tree .process-branch');
        return {same: current === branch, open: current.open};
    ''')
    assert state == {'same': True, 'open': False}


@pytest.mark.browser
def test_performance_process_detail_groups_reconcile_by_key(browser):
    # 内存信息出现或消失时，详情分组必须按 data 键复用，避免事件处理器写入其他分组的状态键。
    driver = browser.driver
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page=performance]')
    browser.click('[data-performance-category=processes]')
    browser.wait.until(lambda _: driver.execute_script(
        r'''return document.querySelectorAll('#performance-process-tree .process-thread').length === 3'''))
    browser.click('#performance-process-tree .process-detail-button')
    browser.wait.until(lambda _: driver.execute_script(
        """return document.querySelector('.process-detail [data-process-detail-group="files"]') !== null"""))
    driver.execute_script('''
        const detail = document.querySelector('.process-detail');
        const groups = {};
        for (const name of ['files', 'connections', 'maps']) {
          groups[name] = detail.querySelector(`[data-process-detail-group="${name}"]`);
        }
        groups.files.open = true;
        window.__detailGroups = {key: detail.dataset.processDetail, groups};
    ''')
    browser.wait.until(lambda _: driver.execute_script('''
        const key = window.__detailGroups.key;
        return state.performanceProcessDetailGroups[key]?.files === true;
    '''))
    result = driver.execute_script('''
        const {key, groups} = window.__detailGroups;
        const entry = state.performanceProcessDetails[key];
        const memory = entry.data.memory_full;
        const snapshot = () => {
          const detail = document.querySelector(
            `.process-detail[data-process-detail="${CSS.escape(key)}"]`);
          const group = (name) => detail.querySelector(
            `[data-process-detail-group="${name}"]`);
          return {
            files: group('files') === groups.files,
            connections: group('connections') === groups.connections,
            maps: group('maps') === groups.maps,
            filesOpen: group('files').open,
          };
        };
        entry.data.memory_full = {};
        renderProcessTree(state.performanceProcesses);
        const withoutMemory = snapshot();
        entry.data.memory_full = memory;
        renderProcessTree(state.performanceProcesses);
        return {
          withoutMemory,
          withMemory: snapshot(),
          groupState: state.performanceProcessDetailGroups[key],
        };
    ''')
    expected = {'files': True, 'connections': True, 'maps': True, 'filesOpen': True}
    assert result['withoutMemory'] == expected
    assert result['withMemory'] == expected
    assert result['groupState']['files'] is True


@pytest.mark.browser
def test_performance_process_tree_refresh_replaces_process_when_identity_changes(browser):
    # 同 PID、同结构但启动时间变化表示旧进程退出且新进程复用身份，必须换节点以重新绑定处理器。
    driver = browser.driver
    snapshot = process_tree_snapshot()
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=statistics_snapshot,
        process_tree_snapshot=lambda: snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page=performance]')
    browser.click('[data-performance-category=processes]')
    browser.wait.until(lambda _: driver.execute_script(
        r'''return document.querySelectorAll('#performance-process-tree .process-thread').length === 3'''))
    driver.execute_script('''
        const root = document.querySelector(
          '#performance-process-tree .process-tree-list > .process-node');
        window.__replacedRoot = root;
        window.__replacedKey = root.dataset.processKey;
    ''')

    updated = process_tree_snapshot()
    updated['roots'][0]['create_time'] = PROCESS_ROOT_CREATED_AT + 10
    browser.host.runtime['statistics'].process_tree_snapshot = lambda: updated
    driver.execute_async_script('''
        const done = arguments[0];
        refreshPerformanceProcesses().then(() => done(true), () => done(false));
    ''')
    state = driver.execute_script('''
        const root = document.querySelector(
          '#performance-process-tree .process-tree-list > .process-node');
        return {
          sameRoot: root === window.__replacedRoot,
          changedKey: root.dataset.processKey !== window.__replacedKey,
          branchKey: root.querySelector('.process-branch').dataset.processBranch,
          nodeKey: root.dataset.processKey,
        };
    ''')
    assert state['sameRoot'] is False
    assert state['changedKey'] is True
    assert state['branchKey'] == state['nodeKey']


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
        text = driver.execute_script(r'''
            return document.querySelector('#performance-cpu-chart .chart-series-cpu').getAttribute('points');
        ''')
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
def test_performance_one_minute_traffic_mini_uses_window_capacity(browser):
    # 1 分钟流量窗口按 5 秒分桶只有 12 个点，缩略图必须按窗口容量铺满，不能固定留 60 个槽位。
    driver = browser.driver
    snapshot = statistics_snapshot()
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=lambda: snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page=performance]')
    browser.wait.until(lambda _: driver.execute_script(
        r'''return state.page === 'performance' && !document.getElementById('performance-content').hidden'''))

    traffic_window = snapshot['traffic']['windows']['1m']
    assert traffic_window['capacity'] == 12
    browser.click('#performance-window-switch button:first-child')
    browser.wait.until(lambda _: driver.execute_script(
        r'''return state.performanceWindow === '1m' '''))
    points = driver.execute_script(r'''
        const line = document.querySelector('[data-performance-mini=traffic] .mini-line');
        return line.getAttribute('points').trim().split(/ +/).map(
          (point) => Number(point.split(',')[0]));
    ''')
    assert len(points) == traffic_window['capacity']
    assert points[0] == 2
    assert points[-1] == 98


@pytest.mark.browser
def test_performance_chart_backfills_empty_leading_buckets(browser):
    # 窗口左侧尚未采样的空桶由最早有效值回填，不能补成 0 把折线压到底部。
    driver = browser.driver
    snapshot = statistics_snapshot()
    window = snapshot['performance']['windows']['1m']
    capacity = window['capacity']
    window['cpu_percent'] = [None] * (capacity - 1) + [64.0]
    browser.host.runtime['statistics'] = SimpleNamespace(
        Proc_type='statistics', snapshot=lambda: snapshot,
        process_tree_snapshot=process_tree_snapshot,
        process_detail_snapshot=process_detail_snapshot)
    browser.open_sidebar()
    browser.click('[data-page=performance]')
    browser.wait.until(lambda _: driver.execute_script(
        r'''return state.page === 'performance' && !document.getElementById('performance-content').hidden'''))

    points = driver.execute_script(r'''
        const line = document.querySelector('#performance-cpu-chart .chart-series-cpu');
        return line.getAttribute('points').trim().split(/\s+/).map(
          (point) => Number(point.split(',')[1]));
    ''')
    assert len(points) == capacity
    assert abs(points[0] - points[-1]) < 0.01
    assert abs(points[0] - 38.0) > 1


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


@pytest.mark.browser
@pytest.mark.parametrize('height', [260, 420, 560, 561, 600, 641, 700, 701, 760, 761, 900])
def test_desktop_sidebar_plugin_list_stays_reachable_across_viewport_heights(browser, height):
    driver = browser.driver
    set_viewport(browser, 1280, height)
    metrics = driver.execute_script('''
        const aside = document.getElementById('sidebar');
        const scrollBox = aside.querySelector('.sidebar-scroll');
        const plinks = document.getElementById('plugin-links');
        const footer = document.querySelector('.sidebar-footer');
        const logout = document.getElementById('logout');
        const lastEntry = plinks.querySelector('.plugin-link-entry[data-plugin-namespace="single"]');
        const asideRect = aside.getBoundingClientRect();
        const scrollRect = scrollBox.getBoundingClientRect();
        const linksRect = plinks.getBoundingClientRect();
        const footerRect = footer.getBoundingClientRect();
        const logoutRect = logout.getBoundingClientRect();
        const logo = aside.querySelector('.brand-logo');
        const logoTop = logo.getBoundingClientRect().top;
        const plinksOverflow = getComputedStyle(plinks).overflowY;
        scrollBox.scrollTop = 0;
        const footerVisibleWithoutScroll = logoutRect.top >= asideRect.top - 0.5 &&
          footerRect.bottom <= asideRect.bottom + 0.5;
        scrollBox.scrollTop = scrollBox.scrollHeight;
        const boxMaxScroll = scrollBox.scrollTop;
        let lastEntryReachable = false;
        if (plinksOverflow === 'visible') {
          lastEntry.scrollIntoView({block: 'nearest'});
          const rect = lastEntry.getBoundingClientRect();
          const currentScrollRect = scrollBox.getBoundingClientRect();
          lastEntryReachable = rect.height > 20 && rect.top >= currentScrollRect.top - 1 &&
            rect.bottom <= currentScrollRect.bottom + 1 && rect.bottom <= footerRect.top + 1;
        } else {
          plinks.scrollTop = plinks.scrollHeight;
          const rect = lastEntry.getBoundingClientRect();
          const containerRect = plinks.getBoundingClientRect();
          lastEntryReachable = rect.height > 20 && rect.top >= containerRect.top - 1 &&
            rect.bottom <= containerRect.bottom + 1;
          plinks.scrollTop = 0;
        }
        const logoPinned = logoTop >= 0 && logoTop === logo.getBoundingClientRect().top;
        scrollBox.scrollTop = 0;
        return {
          logoPinned,
          boxScroll: boxMaxScroll > 0,
          plinksOverflow,
          plinksClientHeight: plinks.clientHeight,
          plinksScrollHeight: plinks.scrollHeight,
          noOverlap: scrollRect.bottom <= footerRect.top + 0.5 &&
            (plinksOverflow === 'visible' || linksRect.bottom <= scrollRect.bottom + 0.5),
          footerVisibleWithoutScroll,
          lastEntryReachable,
        };
    ''')
    assert metrics['noOverlap'], (height, metrics)
    assert metrics['logoPinned'], (height, metrics)
    assert metrics['footerVisibleWithoutScroll'], (height, metrics)
    assert metrics['lastEntryReachable'], (height, metrics)
    # 桌面端与移动端一致：保持 Logo 置顶、底栏固定，中段导航和插件列表走统一全局滚动，无内嵌双滚动条。
    assert metrics['plinksOverflow'] == 'visible', (height, metrics)
    assert metrics['plinksClientHeight'] >= metrics['plinksScrollHeight'] - 1, (height, metrics)
    if height <= 600:
        assert metrics['boxScroll'], (height, metrics)
    elif height >= 900:
        assert not metrics['boxScroll'], (height, metrics)

    if height in (420, 561):
        browser.click('#plugin-navigation-toggle')
        collapsed = driver.execute_script('''
            const scrollBox = document.querySelector('#sidebar .sidebar-scroll');
            const pnav = document.getElementById('plugin-navigation');
            const phead = document.getElementById('plugin-navigation-head');
            const footer = document.querySelector('.sidebar-footer');
            return {
              boxScroll: scrollBox.scrollHeight > scrollBox.clientHeight + 1,
              headPreserved: pnav.getBoundingClientRect().height >= phead.getBoundingClientRect().height - 1,
              noOverlap: phead.getBoundingClientRect().bottom <= footer.getBoundingClientRect().top + 0.5,
            };
        ''')
        browser.click('#plugin-navigation-toggle')
        assert collapsed == {
            'boxScroll': height == 420,
            'headPreserved': True,
            'noOverlap': True,
        }


@pytest.mark.browser
def test_desktop_sidebar_preserves_plugin_list_floor_when_font_scales(browser):
    driver = browser.driver
    set_viewport(browser, 1280, 780)
    try:
        driver.execute_script('document.body.style.fontSize = "20px"')
        metrics = driver.execute_script('''
            const aside = document.getElementById('sidebar');
            const logo = aside.querySelector('.brand-logo');
            const scrollBox = aside.querySelector('.sidebar-scroll');
            const plinks = document.getElementById('plugin-links');
            const footer = document.querySelector('.sidebar-footer');
            const logout = document.getElementById('logout');
            const logoTop = logo.getBoundingClientRect().top;
            scrollBox.scrollTop = scrollBox.scrollHeight;
            const logoPinned = logoTop >= 0 && logoTop === logo.getBoundingClientRect().top;
            scrollBox.scrollTop = 0;
            return {
              logoPinned,
              boxScroll: scrollBox.scrollHeight > scrollBox.clientHeight + 1,
              plinksOverflow: getComputedStyle(plinks).overflowY,
              plinksClientHeight: plinks.clientHeight,
              plinksScrollHeight: plinks.scrollHeight,
              footerVisible: logout.getBoundingClientRect().bottom <= aside.getBoundingClientRect().bottom + 0.5,
              noOverlap: scrollBox.getBoundingClientRect().bottom <= footer.getBoundingClientRect().top + 0.5,
            };
        ''')
    finally:
        driver.execute_script('document.body.style.fontSize = ""')
    assert metrics['logoPinned'], metrics
    assert metrics['boxScroll'], metrics
    assert metrics['plinksOverflow'] == 'visible', metrics
    assert metrics['plinksClientHeight'] >= metrics['plinksScrollHeight'] - 1, metrics
    assert metrics['plinksClientHeight'] >= 160, metrics
    assert metrics['footerVisible'], metrics
    assert metrics['noOverlap'], metrics


@pytest.mark.browser
@pytest.mark.parametrize('width,height', [(390, 600), (640, 360)])
def test_mobile_sidebar_drawer_uses_unified_scroll_on_short_viewport(browser, width, height):
    driver = browser.driver
    set_viewport(browser, width, height, mobile_device=True)
    browser.open_sidebar()
    try:
        metrics = driver.execute_script('''
            const aside = document.getElementById('sidebar');
            const scrollBox = aside.querySelector('.sidebar-scroll');
            const plinks = document.getElementById('plugin-links');
            const footer = document.querySelector('.sidebar-footer');
            const logout = document.getElementById('logout');
            const lastEntry = plinks.querySelector('.plugin-link-entry[data-plugin-namespace="single"]');
            const asideRect = aside.getBoundingClientRect();
            const scrollRect = scrollBox.getBoundingClientRect();
            const footerRect = footer.getBoundingClientRect();
            const noOverlap = scrollRect.bottom <= footerRect.top + 0.5;
            const logo = aside.querySelector('.brand-logo');
            const logoTop = logo.getBoundingClientRect().top;
            scrollBox.scrollTop = 0;
            const footerVisibleWithoutScroll = logout.getBoundingClientRect().top >= asideRect.top - 0.5 &&
              footerRect.bottom <= asideRect.bottom + 0.5;
            scrollBox.scrollTop = scrollBox.scrollHeight;
            const boxScroll = scrollBox.scrollTop > 0;
            lastEntry.scrollIntoView({block: 'nearest'});
            const entryRect = lastEntry.getBoundingClientRect();
            const entryVisible = entryRect.height > 20 && entryRect.top >= scrollRect.top - 1 &&
              entryRect.bottom <= scrollRect.bottom + 1 && entryRect.bottom <= footerRect.top + 1;
            return {
              logoPinned: logoTop >= 0 && logoTop === logo.getBoundingClientRect().top,
              boxScroll,
              plinksOverflow: getComputedStyle(plinks).overflowY,
              noOverlap,
              footerVisibleWithoutScroll,
              entryVisible,
              noHorizontalOverflow: scrollBox.scrollWidth <= scrollBox.clientWidth + 1,
            };
        ''')
    finally:
        driver.execute_script('setSidebarOpen(false)')
    assert metrics == {
        'logoPinned': True,
        'boxScroll': True,
        'plinksOverflow': 'visible',
        'noOverlap': True,
        'footerVisibleWithoutScroll': True,
        'entryVisible': True,
        'noHorizontalOverflow': True,
    }


@pytest.mark.browser
def test_short_viewport_collapsed_sidebar_keeps_controls_within_bounds(browser):
    driver = browser.driver
    set_viewport(browser, 1280, 420)
    try:
        driver.execute_script('setSidebarCollapsed(true, false)')
        browser.wait.until(lambda _: driver.execute_script(
            "return document.getElementById('sidebar').getBoundingClientRect().width < 70"))
        collapsed_metrics = driver.execute_script('''
            const aside = document.getElementById('sidebar');
            const scrollBox = aside.querySelector('.sidebar-scroll');
            const footer = aside.querySelector('.sidebar-footer');
            const asideRect = aside.getBoundingClientRect();
            const visibleLeft = asideRect.left + aside.clientLeft;
            const visibleRight = visibleLeft + aside.clientWidth;
            const scrollControls = [...scrollBox.querySelectorAll('#navigation button')];
            const footerControls = [...footer.querySelectorAll('button')];
            return {
              boxScroll: scrollBox.scrollHeight > scrollBox.clientHeight + 1,
              footerVisible: footer.getBoundingClientRect().bottom <= asideRect.bottom + 0.5,
              clipped: [...scrollControls, ...footerControls].filter((node) => {
                const container = footer.contains(node) ? aside : scrollBox;
                const cRect = container.getBoundingClientRect();
                const cLeft = Math.max(visibleLeft, cRect.left + container.clientLeft);
                const cRight = Math.min(visibleRight, cLeft + container.clientWidth);
                const rect = node.getBoundingClientRect();
                return rect.left < cLeft - 0.5 || rect.right > cRight + 0.5;
              }).length,
            };
        ''')
    finally:
        driver.execute_script('setSidebarCollapsed(false, false)')
    assert collapsed_metrics == {'boxScroll': True, 'footerVisible': True, 'clipped': 0}


@pytest.mark.browser
def test_short_viewport_plugin_frame_keeps_minimum_readable_height(browser):
    driver = browser.driver
    set_viewport(browser, 1280, 260)
    browser.select()
    driver.switch_to.default_content()
    frame_metrics = driver.execute_script('''
        const main = document.querySelector('main');
        return {
          frameHeight: Math.round(state.frame.getBoundingClientRect().height),
          mainScroll: main.scrollHeight > main.clientHeight + 1,
        };
    ''')
    assert frame_metrics['frameHeight'] >= 250, frame_metrics
    assert frame_metrics['mainScroll'], frame_metrics


@pytest.mark.browser
def test_short_viewport_dialog_fits_viewport_and_scrolls(browser):
    driver = browser.driver
    set_viewport(browser, 1280, 260)
    dialog_metrics = driver.execute_script('''
        const dialog = document.getElementById('account-dialog');
        dialog.showModal();
        const rect = dialog.getBoundingClientRect();
        const result = {
          fitsViewport: rect.top >= -0.5 && rect.bottom <= innerHeight + 0.5 && rect.height <= innerHeight,
          overflowY: getComputedStyle(dialog).overflowY,
          canScroll: dialog.scrollHeight > dialog.clientHeight + 1,
        };
        dialog.close();
        return result;
    ''')
    assert dialog_metrics == {'fitsViewport': True, 'overflowY': 'auto', 'canScroll': True}
