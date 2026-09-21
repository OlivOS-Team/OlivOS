"""真实浏览器验证插件分组、独立功能页面、保活及响应式侧栏。"""

import os
import queue
import threading
from pathlib import Path

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


@pytest.mark.skipif(not os.environ.get('OLIVOS_WEBUI_BROWSER'), reason='Set OLIVOS_WEBUI_BROWSER=1 to run Chrome')
def test_grouped_navigation_preserves_all_pages(navigation_host, tmp_path):
    pytest.importorskip('selenium')
    from selenium import webdriver
    from selenium.common.exceptions import StaleElementReferenceException
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as conditions
    from selenium.webdriver.support.ui import WebDriverWait

    host = navigation_host
    options = webdriver.ChromeOptions()
    for arg in ('--headless=new', '--no-first-run', '--disable-background-networking', '--window-size=1440,1000',
                f'--user-data-dir={tmp_path / "browser-profile"}'):
        options.add_argument(arg)
    options.set_capability('goog:loggingPrefs', {'browser': 'ALL'})
    driver_path = os.environ.get('OLIVOS_CHROMEDRIVER')
    service = Service(executable_path=driver_path) if driver_path else None
    driver = webdriver.Chrome(service=service, options=options)
    wait = WebDriverWait(driver, 10, ignored_exceptions=(StaleElementReferenceException,))
    screenshots = Path(os.environ.get('OLIVOS_WEBUI_SCREENSHOTS', tmp_path / 'screenshots'))
    screenshots.mkdir(parents=True, exist_ok=True)
    multi = '.plugin-page-group[data-plugin-namespace="multi"]'
    single = '.plugin-page-group[data-plugin-namespace="single"]'

    def find(selector):
        return driver.find_element(By.CSS_SELECTOR, selector)

    def visible(selector):
        return wait.until(lambda _: find(selector).is_displayed())

    def click(selector):
        visible(selector)
        previous_group = find(multi) if selector == '[data-page="plugins"]' else None
        find(selector).click()
        if previous_group is not None:
            wait.until(conditions.staleness_of(previous_group))

    def select_page(path):
        click(f'{multi} .plugin-link-entry[data-plugin-path="{path}"]')
        frame = wait.until(lambda _: find('#plugin-frame-container iframe:not([hidden])'))
        driver.switch_to.frame(frame)
        visible('#draft')
        return driver.execute_script('return window.pageIdentity')

    def screenshot(name):
        driver.save_screenshot(str(screenshots / name))

    try:
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': 1440, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False,
        })
        driver.get(f"http://127.0.0.1:{host.config['port']}/")
        visible('#token')
        find('#token').send_keys(host.token)
        click('#login-form button')
        visible('#shell')
        wait.until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '.plugin-page-group')) == 2)
        assert [e.text for e in driver.find_elements(By.CSS_SELECTOR, f'{multi} .plugin-link-entry')] == [
            '首页', '配置管理', '工具面板']
        assert find(multi + ' .plugin-group-count').text == '4'
        assert not driver.find_elements(By.CSS_SELECTOR, single + ' .plugin-group-toggle')
        assert not driver.find_elements(By.CSS_SELECTOR, single + ' .plugin-group-children')
        click(single + ' .plugin-single-entry')
        driver.switch_to.frame(wait.until(lambda _: find('#plugin-frame-container iframe:not([hidden])')))
        visible('#draft')
        assert find('h1').text == '功能首页'
        driver.switch_to.default_content()
        screenshot('desktop-single.png')
        assert find(single + ' .plugin-link-close').get_attribute('title') == '关闭：独立插件 / 功能首页'
        previous_group = find(single)
        click(single + ' .plugin-link-close')
        wait.until(conditions.staleness_of(previous_group))
        wait.until(lambda _: not driver.find_elements(By.CSS_SELECTOR, '#plugin-frame-container iframe'))
        assert find('#notice-message').text == '已关闭插件页面：独立插件 / 功能首页'
        screenshot('close-single.png')
        click('#notice-close')
        assert len(driver.find_elements(By.CSS_SELECTOR, '#navigation [data-page]')) == 5

        identities = {}
        for path, title in [('webui/index.html', '首页'), ('webui/settings/index.html', '配置管理'),
                            ('webui/tools/index.html', '工具面板')]:
            identities[path] = select_page(path)
            assert find('h1').text == title
            find('#draft').send_keys(title + '已编辑')
            click('#request')
            wait.until(lambda _: find('#reply').text == '回包成功：' + title + '已编辑')
            driver.switch_to.default_content()
        assert len(driver.find_elements(By.CSS_SELECTOR, '#plugin-frame-container iframe')) == 3
        screenshot('desktop-tools.png')
        assert select_page('webui/settings/index.html') == identities['webui/settings/index.html']
        assert find('#draft').get_attribute('value') == '配置管理已编辑'
        driver.switch_to.default_content()
        screenshot('desktop-settings.png')

        click(multi + ' .plugin-group-toggle')
        assert find('#page-title').text == '配置管理'
        assert not find(multi + ' .plugin-group-children').is_displayed()
        assert find(multi + ' .plugin-group-toggle').get_attribute('aria-expanded') == 'false'
        assert len(driver.find_elements(By.CSS_SELECTOR, '#plugin-frame-container iframe')) == 3
        screenshot('desktop-collapsed.png')
        click('[data-page="plugins"]')
        wait.until(lambda _: find(multi + ' .plugin-group-toggle').get_attribute('aria-expanded') == 'false')
        # 分组按钮可通过键盘展开，普通插件列表刷新也保留折叠状态。
        find(multi + ' .plugin-group-toggle').send_keys(Keys.ENTER)
        assert select_page('webui/settings/index.html') == identities['webui/settings/index.html']
        driver.switch_to.default_content()

        original = driver.current_window_handle
        click(multi + ' .plugin-link-external')
        wait.until(lambda _: len(driver.window_handles) == 2)
        driver.switch_to.window(next(handle for handle in driver.window_handles if handle != original))
        wait.until(lambda _: 'OK' in find('body').text)
        driver.close()
        driver.switch_to.window(original)

        # 相同显示名也按 namespace 保持两个分组，不吞掉功能入口。
        with host.lock:
            host.plugins['single'][0] = host.plugins['multi'][0]
            for page in host.plugin_pages:
                if page.get('path') == 'webui/tools/index.html':
                    page['title'] = '配置管理'
        click('[data-page="plugins"]')
        wait.until(lambda _: find(single + ' .plugin-group-name').text == '多页面插件')
        assert len(driver.find_elements(By.CSS_SELECTOR, '.plugin-page-group')) == 2
        assert find(multi + ' .plugin-group-namespace').text == 'multi'
        assert find(single + ' .plugin-group-namespace').text == 'single'
        assert [entry.text for entry in driver.find_elements(By.CSS_SELECTOR, multi + ' .plugin-entry-path')] == [
            'webui/settings/index.html', 'webui/tools/index.html']
        assert select_page('webui/tools/index.html') == identities['webui/tools/index.html']
        driver.switch_to.default_content()
        screenshot('desktop-duplicate-names.png')
        tools = find(multi + ' .plugin-link-entry[data-plugin-path="webui/tools/index.html"]')
        close = tools.find_element(By.XPATH, '..').find_element(By.CSS_SELECTOR, '.plugin-link-close')
        label = '多页面插件（multi） / 配置管理（webui/tools/index.html）'
        assert close.get_attribute('title') == '关闭：' + label
        assert close.get_attribute('aria-label') == '关闭 ' + label
        previous_group = find(multi)
        close.click()
        wait.until(conditions.staleness_of(previous_group))
        wait.until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '#plugin-frame-container iframe')) == 2)
        assert find('#notice-message').text == '已关闭插件页面：' + label
        visible('#plugins')
        screenshot('close-duplicate.png')
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False,
        })
        find('#notice').location_once_scrolled_into_view
        assert driver.execute_script('return document.documentElement.scrollWidth <= innerWidth')
        screenshot('close-duplicate-mobile.png')
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': 1440, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False,
        })
        identities['webui/tools/index.html'] = select_page('webui/tools/index.html')
        driver.switch_to.default_content()
        click('#notice-close')
        with host.lock:
            host.plugins['single'][0] = '独立插件'
            for page in host.plugin_pages:
                if page.get('path') == 'webui/tools/index.html':
                    page['title'] = '工具面板'
        click('[data-page="plugins"]')
        wait.until(lambda _: find(single + ' .plugin-group-name').text == '独立插件')
        assert not driver.find_elements(By.CSS_SELECTOR, '.plugin-group-namespace, .plugin-entry-path')
        select_page('webui/settings/index.html')
        driver.switch_to.default_content()

        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False,
        })
        assert driver.execute_script('return document.documentElement.scrollWidth <= innerWidth')
        screenshot('mobile-settings.png')
        driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
            'width': 1440, 'height': 1000, 'deviceScaleFactor': 1, 'mobile': False,
        })
        driver.execute_cdp_cmd('Emulation.setEmulatedMedia', {
            'features': [{'name': 'prefers-color-scheme', 'value': 'dark'}],
        })
        wait.until(lambda _: driver.execute_script('return document.documentElement.dataset.theme') == 'dark')
        screenshot('desktop-dark.png')

        # 关闭一个非当前子页面只释放它；关闭全部后导航中的所有子入口仍保留。
        tools = find(multi + ' .plugin-link-entry[data-plugin-path="webui/tools/index.html"]')
        tools.find_element(By.XPATH, '..').find_element(By.CSS_SELECTOR, '.plugin-link-close').click()
        wait.until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '#plugin-frame-container iframe')) == 2)
        assert find('#notice-message').text == '已关闭插件页面：多页面插件 / 工具面板'
        screenshot('close-child.png')
        assert select_page('webui/settings/index.html') == identities['webui/settings/index.html']
        driver.switch_to.default_content()
        click(single + ' .plugin-single-entry')
        wait.until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '#plugin-frame-container iframe')) == 3)
        assert find('#plugin-pages-close').get_attribute('title') == '关闭全部插件页面（2 个插件，3 个页面）'
        previous_group = find(multi)
        click('#plugin-pages-close')
        wait.until(conditions.staleness_of(previous_group))
        wait.until(lambda _: not driver.find_elements(By.CSS_SELECTOR, '#plugin-frame-container iframe'))
        assert find('#notice-message').text == '已关闭全部插件页面（2 个插件，共 3 个页面）。'
        screenshot('close-all.png')
        assert len(driver.find_elements(By.CSS_SELECTOR, f'{multi} .plugin-link-entry')) == 3
        select_page('webui/index.html')
        driver.switch_to.default_content()
        driver.refresh()
        visible('#shell')
        wait.until(lambda _: len(driver.find_elements(By.CSS_SELECTOR, '#plugin-frame-container iframe')) == 1)
        assert find(multi + ' .plugin-group-toggle').get_attribute('aria-expanded') == 'true'

        for page in ('dashboard', 'accounts', 'logs', 'terminals', 'plugins'):
            click(f'[data-page="{page}"]')
            visible('#' + page)

        # 页面注册表缩为一个入口后直接打开，重新增加页面后恢复分组。
        with host.lock:
            original_pages = host.plugin_pages[:]
            host.plugin_pages = [page for page in host.plugin_pages
                                 if page['namespace'] != 'multi' or page.get('path') == 'webui/tools/index.html']
        click('[data-page="plugins"]')
        wait.until(lambda _: not driver.find_elements(By.CSS_SELECTOR, multi + ' .plugin-group-toggle'))
        select_page('webui/tools/index.html')
        assert find('h1').text == '工具面板'
        driver.switch_to.default_content()
        with host.lock:
            host.plugin_pages = original_pages
        click('[data-page="plugins"]')
        visible(multi + ' .plugin-group-toggle')
        assert len(driver.find_elements(By.CSS_SELECTOR, multi + ' .plugin-link-entry')) == 3
        errors = [entry['message'] for entry in driver.get_log('browser')
                  if entry['level'] == 'SEVERE' and entry.get('source') == 'javascript']
        assert not errors
    except Exception:
        screenshot('failure.png')
        raise
    finally:
        driver.quit()
