"""实际导入 OPK 并请求页面，验证宿主管理静态资源的完整流程。"""

import json
import queue
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from OlivOS import pluginAPI
from OlivOS.webUI import resourceAPI, serverAPI

NAMESPACE = 'OpkWebuiLifecycle'
ASSETS = {'webui/index.html': b'<html>test</html>', 'webui/assets/app.js': b'window.loaded = true;'}


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
    host = serverAPI.server(root_path=tmp_path, rx_queue=queue.Queue(), control_queue=queue.Queue(),
                            server_conf={'port': 0, 'host': '127.0.0.1'})
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


def install(host, relative_path, assets=None, registered=True, broken=False, entry='webui/index.html', main=None):
    manifest = {'name': NAMESPACE, 'namespace': NAMESPACE, 'priority': 30000,
                'compatible_svn': 190, 'support': []}
    if registered:
        manifest['webui_config'] = [{'title': 'OPK', 'type': 'iframe', 'path': entry}]
    files = {
        'app.json': json.dumps(manifest).encode(),
        '__init__.py': b'raise RuntimeError("test import failure")' if broken else b'from . import main\n',
        # 插件无缓存或写回网页的兜底逻辑。
        'main.py': main or b'class Event:\n    pass\n',
        'private.txt': b'not a web asset',
        'extra/unused.txt': b'import cache',
    }
    files.update(ASSETS if assets is None else assets)
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
    loader.sendPluginList(ready=True)
    while not host.Proc_info.control_queue.empty():
        host.consume(host.Proc_info.control_queue.get_nowait())
    client = host.app.test_client()
    assert client.get(f'/plugin/{NAMESPACE}/webui/index.html').status_code == 401
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
    assert Path(plugin['model'].__file__).parent == expected
    if packed:
        assert (host.root / 'plugin/tmp').is_dir()
        assert not expected.exists()
        cached = Path(plugin['webui_root'])
        assert cached.parent == host.root / resourceAPI.CACHE_PATH / NAMESPACE
        assert {path.name for path in cached.iterdir()} == {'webui'}
    else:
        assert Path(plugin['webui_root']) == expected
        assert (expected / 'main.py').is_file()
    loader.run_plugin_func(None, 'init_after')
    client = mount(host, loader)
    for name, data in ASSETS.items():
        response = client.get(f'/plugin/{NAMESPACE}/{name}', follow_redirects=True)
        assert response.status_code == 200
        assert response.data == data
        response.close()
        assert "connect-src 'none'" in response.headers['Content-Security-Policy']
    for name in ['app.json', 'private.txt', '../private.txt', 'assets/../../private.txt']:
        assert client.get(f'/plugin/{NAMESPACE}/{name}').status_code == 404


def test_reloading_replaces_assets_and_removes_stale_files(installation):
    host, loader = installation
    relative_path = '其他插件/release-name.opk'
    install(host, relative_path)
    loader.load_plugin_list()
    client = mount(host, loader)
    previous = Path(loader.plugin_models_dict[NAMESPACE]['webui_root'])
    updated = {'webui/index.html': b'<html>updated</html>', 'webui/new/app.js': b'window.updated = true;'}
    install(host, relative_path, assets=updated)
    for name in list(sys.modules):
        if name == NAMESPACE or name.startswith(NAMESPACE + '.'):
            sys.modules.pop(name)
    loader.load_plugin_list()
    assert previous.is_dir()
    with client.get(f'/plugin/{NAMESPACE}/webui/index.html') as response:
        assert response.data == ASSETS['webui/index.html']
    client = mount(host, loader)
    assert not previous.exists()
    for name, data in updated.items():
        response = client.get(f'/plugin/{NAMESPACE}/{name}', follow_redirects=True)
        assert response.status_code == 200
        assert response.data == data
        response.close()
    assert client.get(f'/plugin/{NAMESPACE}/webui/assets/app.js').status_code == 404


@pytest.mark.parametrize('registered,broken', [(False, False), (True, True)])
def test_unused_opk_cache_is_still_removed(installation, registered, broken):
    host, loader = installation
    install(host, NAMESPACE + '.opk', registered=registered, broken=broken)
    loader.load_plugin_list()
    assert (NAMESPACE in loader.plugin_models_dict) is not broken
    assert (host.root / 'plugin/tmp').is_dir()
    assert not (host.root / 'plugin/tmp' / NAMESPACE).exists()


@pytest.mark.parametrize('packed', [False, True])
def test_cleanup_preserves_tmp_root_and_unrelated_files(installation, packed):
    host, loader = installation
    tmp_root = host.root / 'plugin/tmp'
    original_root = tmp_root.stat()
    unrelated = tmp_root / 'OtherPlugin' / 'pending.bin'
    unrelated.parent.mkdir()
    unrelated.write_bytes(b'ongoing plugin work')
    root_file = tmp_root / 'pending.txt'
    root_file.write_bytes(b'pending work')
    install(host, NAMESPACE + ('.opk' if packed else ''))
    # 初次加载和重载都保留根目录及与本次解包无关的临时文件。
    for _ in range(2):
        loader.load_plugin_list()
        assert tmp_root.is_dir()
        assert tmp_root.stat().st_ino == original_root.st_ino
        assert unrelated.read_bytes() == b'ongoing plugin work'
        assert root_file.read_bytes() == b'pending work'
        assert not (tmp_root / NAMESPACE).exists()


@pytest.mark.parametrize('packed', [False, True])
@pytest.mark.parametrize('entry,files', [
    ('webui/custom/index.html', {'webui/custom/index.html': b'custom', 'webui/custom/assets/style.css': b'body {}'}),
    ('panel.html', {'panel.html': b'single file'}),
    ('界面/pages/', {'界面/pages/index.html': b'directory', '界面/pages/app.js': b'void 0;'}),
    ('webui/custom', {'webui/custom/index.html': b'directory without slash'}),
])
def test_paths_follow_manifest_without_extra_fields(installation, packed, entry, files):
    host, loader = installation
    source = install(host, NAMESPACE + ('.opk' if packed else ''), assets=files, entry=entry)
    loader.load_plugin_list()
    client = mount(host, loader)
    assert host.plugin_pages[0]['path'] == next(iter(files))
    for name, data in files.items():
        with client.get(f'/plugin/{NAMESPACE}/{name}') as response:
            assert response.status_code == 200
            assert response.data == data
    assert client.get(f'/plugin/{NAMESPACE}/private.txt').status_code == 404
    if packed:
        assert (host.root / 'plugin/tmp').is_dir()
        assert not (host.root / 'plugin/tmp' / NAMESPACE).exists()
        cached = Path(host.plugin_roots[NAMESPACE])
        assert {p.relative_to(cached).as_posix() for p in cached.rglob('*') if p.is_file()} == set(files)
    else:
        assert Path(host.plugin_roots[NAMESPACE]) == source


@pytest.mark.parametrize('packed', [False, True])
def test_private_files_and_links_are_never_published(installation, packed):
    host, loader = installation
    private = ['webui/main.py', 'webui/cache.pyc', 'webui/app.json', 'webui/.hidden',
               'webui/.private/password.txt', 'webui/sub/App.JSON', 'other/file.txt']
    files = dict(ASSETS, **{name: b'private' for name in private})
    install(host, NAMESPACE + ('.opk' if packed else ''), assets=files)
    loader.load_plugin_list()
    client = mount(host, loader)
    for name in private + ['webui/../private.txt', 'webui/%2e%2e/private.txt', 'webui/index.html:stream']:
        assert client.get(f'/plugin/{NAMESPACE}/{name}').status_code == 404
    if packed:
        cached = Path(host.plugin_roots[NAMESPACE])
        for name in private:
            assert not (cached / name).exists()


def test_init_generated_assets_are_cached_before_tmp_is_removed(installation):
    host, loader = installation
    main = (b'from pathlib import Path\nclass Event:\n'
            b'    def init(plugin_event, Proc):\n'
            b'        (Path(__file__).parent / "webui/index.html").write_bytes(b"generated")\n')
    install(host, NAMESPACE + '.opk', main=main)
    loader.load_plugin_list()
    client = mount(host, loader)
    with client.get(f'/plugin/{NAMESPACE}/webui/index.html') as response:
        assert response.data == b'generated'
    assert (host.root / 'plugin/tmp').is_dir()
    assert not (host.root / 'plugin/tmp' / NAMESPACE).exists()


def test_startup_reset_clears_cache_only_and_resources_can_be_rebuilt(installation):
    host, loader = installation
    install(host, NAMESPACE + '.opk')
    user_file = host.root / 'plugin/data/settings.json'
    user_file.parent.mkdir(parents=True)
    user_file.write_bytes(b'user data')
    loader.load_plugin_list()
    previous = Path(loader.plugin_models_dict[NAMESPACE]['webui_root'])
    resourceAPI.reset_cache(host.root)
    assert not previous.exists()
    assert user_file.read_bytes() == b'user data'
    loader.load_plugin_list()
    client = mount(host, loader)
    assert Path(host.plugin_roots[NAMESPACE]) != previous
    with client.get(f'/plugin/{NAMESPACE}/webui/index.html') as response:
        assert response.data == ASSETS['webui/index.html']


def test_mount_update_does_not_prune_a_new_unpublished_generation(installation):
    host, loader = installation
    install(host, NAMESPACE + '.opk')
    loader.load_plugin_list()
    mount(host, loader)
    old_root = Path(host.plugin_roots[NAMESPACE])
    loader.sendPluginList(ready=True)
    old_packet = host.Proc_info.control_queue.get_nowait()
    loader.load_plugin_list()
    new_root = Path(loader.plugin_models_dict[NAMESPACE]['webui_root'])
    host.consume(old_packet)
    assert old_root.is_dir()
    assert new_root.is_dir()
    mount(host, loader)
    assert not old_root.exists()
    assert new_root.is_dir()


def test_loading_notification_keeps_last_mounted_resources(installation):
    host, loader = installation
    install(host, NAMESPACE + '.opk')
    loader.load_plugin_list()
    client = mount(host, loader)
    previous = Path(host.plugin_roots[NAMESPACE])
    loader.plugin_models_dict.clear()
    loader.sendPluginList(ready=False)
    while not host.Proc_info.control_queue.empty():
        host.consume(host.Proc_info.control_queue.get_nowait())
    assert previous.is_dir()
    with client.get(f'/plugin/{NAMESPACE}/webui/index.html') as response:
        assert response.status_code == 200
    mount(host, loader)
    assert not previous.exists()


def test_open_response_finishes_before_old_cache_is_reclaimed(installation):
    host, loader = installation
    install(host, NAMESPACE + '.opk')
    loader.load_plugin_list()
    client = mount(host, loader)
    previous = Path(host.plugin_roots[NAMESPACE])
    response = client.get(f'/plugin/{NAMESPACE}/webui/index.html', buffered=False)
    loader.load_plugin_list()
    mount(host, loader)
    assert response.data == ASSETS['webui/index.html']
    response.close()
    assert not previous.exists()


def test_unloaded_plugin_cache_is_reclaimed(installation):
    host, loader = installation
    package = install(host, NAMESPACE + '.opk')
    loader.load_plugin_list()
    client = mount(host, loader)
    previous = Path(host.plugin_roots[NAMESPACE])
    package.unlink()
    loader.load_plugin_list()
    mount(host, loader)
    assert not previous.exists()
    assert client.get(f'/plugin/{NAMESPACE}/webui/index.html').status_code == 404


@pytest.mark.parametrize('entry', [
    '../private.txt', '/webui/index.html', 'main.py', '.hidden',
    'webui\\index.html', 'webui/index.html:stream', 'missing/index.html',
])
def test_invalid_page_does_not_break_plugin_or_keep_tmp(installation, entry):
    host, loader = installation
    install(host, NAMESPACE + '.opk', entry=entry)
    loader.load_plugin_list()
    assert NAMESPACE in loader.plugin_models_dict
    assert not loader.plugin_models_dict[NAMESPACE]['webui_config']
    assert (host.root / 'plugin/tmp').is_dir()
    assert not (host.root / 'plugin/tmp' / NAMESPACE).exists()


def test_symbolic_links_are_not_copied_or_served(installation):
    host, loader = installation
    source = install(host, NAMESPACE)
    outside = host.root / 'outside'
    outside.mkdir()
    (outside / 'private.txt').write_bytes(b'private')
    link = source / 'webui/linked'
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        if sys.platform != 'win32':
            pytest.skip('Creating symlinks is unavailable')
        import _winapi
        _winapi.CreateJunction(str(outside), str(link))
    loader.load_plugin_list()
    client = mount(host, loader)
    assert client.get(f'/plugin/{NAMESPACE}/webui/linked/private.txt').status_code == 404
    cached = Path(resourceAPI.build_cache(host.root, source, NAMESPACE, ['webui/']))
    assert not (cached / 'webui/linked').exists()
    link.rename(cached / 'linked')
    resourceAPI.reset_cache(host.root)
    assert (outside / 'private.txt').read_bytes() == b'private'
