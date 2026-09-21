"""实际导入 OPK 并请求页面，验证宿主管理静态资源的完整流程。"""

import json
import queue
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from OlivOS import pluginAPI
from OlivOS.webUI import serverAPI

NAMESPACE = 'OpkWebuiLifecycle'
ASSETS = {'index.html': b'<html>test</html>', 'assets/app.js': b'window.loaded = true;'}


@pytest.fixture
def installation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app_dir, tmp_dir = tmp_path / 'plugin/app', tmp_path / 'plugin/tmp'
    app_dir.mkdir(parents=True)
    tmp_dir.mkdir(parents=True)
    monkeypatch.setattr(pluginAPI, 'plugin_path', str(app_dir) + '/')
    monkeypatch.setattr(pluginAPI, 'plugin_path_tmp', str(tmp_dir) + '/')
    monkeypatch.syspath_prepend(str(app_dir))
    monkeypatch.syspath_prepend(str(tmp_dir))
    host = serverAPI.server(root_path=tmp_path, control_queue=queue.Queue())
    loader = pluginAPI.shallow(control_queue=host.Proc_info.control_queue)
    loader.database = SimpleNamespace(_init_namespace=lambda namespace: None)
    previous = {name: module for name, module in sys.modules.items()
                if name == NAMESPACE or name.startswith(NAMESPACE + '.')}
    for name in previous:
        sys.modules.pop(name)
    yield host, loader
    host.on_terminate()
    for name in list(sys.modules):
        if name == NAMESPACE or name.startswith(NAMESPACE + '.'):
            sys.modules.pop(name)
    sys.modules.update(previous)


def install(host, relative_path, assets=None, registered=True, broken=False):
    manifest = {'name': NAMESPACE, 'namespace': NAMESPACE, 'priority': 30000,
                'compatible_svn': 190, 'support': []}
    if registered:
        manifest['webui_config'] = [{'title': 'OPK', 'type': 'iframe', 'path': 'webui/index.html'}]
    files = {
        'app.json': json.dumps(manifest).encode(),
        '__init__.py': b'raise RuntimeError("test import failure")' if broken else b'from . import main\n',
        # 插件无缓存或写回网页的兜底逻辑。
        'main.py': b'class Event:\n    pass\n',
        'private.txt': b'not a web asset',
        'extra/unused.txt': b'import cache',
    }
    files.update({'webui/' + name: data for name, data in (ASSETS if assets is None else assets).items()})
    destination = host.root / 'plugin/app' / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.suffix == '.opk':
        with zipfile.ZipFile(destination, 'w') as archive:
            for name, data in files.items():
                archive.writestr(name, data)
    else:
        for name, data in files.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    return destination


def mount(host, loader):
    loader.sendPluginList()
    while not host.Proc_info.control_queue.empty():
        host.consume(host.Proc_info.control_queue.get_nowait())
    client = host.app.test_client()
    assert client.get(f'/plugin/{NAMESPACE}/index.html').status_code == 401
    assert client.post('/api/login', headers={'X-Auth-Token': host.token}).status_code == 200
    return client


@pytest.mark.parametrize('relative_path', [
    NAMESPACE, '其他插件/' + NAMESPACE, NAMESPACE + '.opk',
    '其他插件/' + NAMESPACE + '.opk', 'release-name.opk', '其他插件/release-name.opk',
])
def test_assets_survive_loading_and_use_final_root(installation, relative_path):
    host, loader = installation
    source = install(host, relative_path)
    loader.load_plugin_list()
    plugin = loader.plugin_models_dict[NAMESPACE]
    packed = source.suffix == '.opk'
    expected = host.root / 'plugin/tmp' / NAMESPACE if packed else source
    assert Path(plugin['webui_root']) == expected
    assert Path(plugin['model'].__file__).parent == expected
    if packed:
        assert {path.name for path in expected.iterdir()} == {'webui'}
    else:
        assert (expected / 'main.py').is_file()
    loader.run_plugin_func(None, 'init_after')
    client = mount(host, loader)
    for name, data in ASSETS.items():
        response = client.get(f'/plugin/{NAMESPACE}/{name}', follow_redirects=True)
        assert response.status_code == 200
        assert response.data == data
        assert "connect-src 'none'" in response.headers['Content-Security-Policy']
    for name in ['app.json', 'private.txt', '../private.txt', 'assets/../../private.txt']:
        assert client.get(f'/plugin/{NAMESPACE}/{name}').status_code == 404


def test_reloading_replaces_assets_and_removes_stale_files(installation):
    host, loader = installation
    relative_path = '其他插件/release-name.opk'
    install(host, relative_path)
    loader.load_plugin_list()
    updated = {'index.html': b'<html>updated</html>', 'new/app.js': b'window.updated = true;'}
    install(host, relative_path, assets=updated)
    for name in list(sys.modules):
        if name == NAMESPACE or name.startswith(NAMESPACE + '.'):
            sys.modules.pop(name)
    loader.load_plugin_list()
    client = mount(host, loader)
    for name, data in updated.items():
        response = client.get(f'/plugin/{NAMESPACE}/{name}', follow_redirects=True)
        assert response.status_code == 200
        assert response.data == data
    assert client.get(f'/plugin/{NAMESPACE}/assets/app.js').status_code == 404


@pytest.mark.parametrize('registered,broken', [(False, False), (True, True)])
def test_unused_opk_cache_is_still_removed(installation, registered, broken):
    host, loader = installation
    install(host, NAMESPACE + '.opk', registered=registered, broken=broken)
    loader.load_plugin_list()
    assert (NAMESPACE in loader.plugin_models_dict) is not broken
    assert not (host.root / 'plugin/tmp' / NAMESPACE).exists()
