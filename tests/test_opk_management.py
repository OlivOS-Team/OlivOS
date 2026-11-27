"""OPK 规范化、加载来源和 WebUI 插件文件批处理回归。"""

import asyncio
import io
import json
import queue
import stat
import sys
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from multidict import CIMultiDict
from werkzeug.datastructures import FileStorage
from werkzeug.test import encode_multipart

from OlivOS import infoAPI, pluginAPI
from OlivOS.core.core import opkAPI
from OlivOS.webUI import serverAPI
from webui_test_support import make_host


NAMESPACE = 'OpkManagementFixture'
STAGE_URL = '/api/plugins/upload/stage'
FILES_URL = '/api/plugins/files'
BATCH_URL = '/api/plugins/batch/'
BOM = b'\xef\xbb\xbf'
APPLEDOUBLE = b'\x00\x05\x16\x07'
MACOS_NOISE = {
    '__MACOSX/finder.txt': b'finder',
    'assets/__MACOSX': b'also excluded',
    '.DS_Store': b'finder',
    'assets/.DS_Store': b'finder',
    'assets/._data.json': APPLEDOUBLE + b'metadata',
}


def plugin_members(namespace=NAMESPACE, version='1.0', svn=1):
    manifest = {'name': 'OPK fixture', 'namespace': namespace, 'version': version, 'svn': svn,
                'priority': 30000, 'support': [], 'compatible_svn': infoAPI.OlivOS_SVN_Compatible}
    return {
        'app.json': json.dumps(manifest, ensure_ascii=False).encode('utf-8'),
        '__init__.py': b'from . import main\n',
        'main.py': b'class Event:\n'
                   b'    @staticmethod\n'
                   b'    def init(plugin_event, Proc):\n'
                   b'        Proc.opk_test_inits += 1\n',
    }


def zip_bytes(members):
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


def shape_members(members, nested):
    if nested == 'directory':
        return {f'发布目录/{name}': content for name, content in members.items()}
    if nested == 'opk':
        return {'release.opk': zip_bytes(members)}
    return members


def write_opk(path, members=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zip_bytes(plugin_members() if members is None else members))
    return path


def write_source(path, members=None):
    path.mkdir(parents=True)
    for name, data in (plugin_members() if members is None else members).items():
        file = path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    return path


def archive_members(path):
    with zipfile.ZipFile(path) as archive:
        return {info.filename: archive.read(info) for info in archive.infolist() if not info.is_dir()}


@pytest.mark.parametrize('nested', [None, 'directory', 'opk'])
def test_inspect_extract_and_rebuild_all_supported_shapes(tmp_path, nested):
    members = dict(plugin_members(), **{'assets/data.json': b'{}'})
    path = write_opk(tmp_path / 'historical-release.opk', shape_members(members, nested))
    report = opkAPI.inspect_opk(path)
    assert report['namespace'] == NAMESPACE
    assert report['manifest']['version'] == '1.0'
    assert report['nested'] == nested
    destination = tmp_path / 'unpacked'
    opkAPI.extract_opk(path, destination)
    assert {p.relative_to(destination).as_posix(): p.read_bytes()
            for p in destination.rglob('*') if p.is_file()} == members
    rebuilt = tmp_path / 'rebuilt.opk'
    opkAPI.rebuild_opk_file(path, rebuilt)
    assert opkAPI.inspect_opk(rebuilt)['nested'] is None
    assert archive_members(rebuilt) == members
    assert opkAPI.inspect_opk(path)['nested'] == nested


@pytest.mark.parametrize('outer,inner,extra', [
    ('directory', 'directory', {}),
    ('directory', 'opk', {}),
    ('opk', 'directory', {}),
    ('opk', 'opk', {}),
    ('directory', None, {'another/ignored.txt': b'not ignored'}),
    ('directory', None, {'readme.txt': b'not ignored'}),
    ('opk', None, {'another.opk': b'not ignored'}),
    ('opk', None, {'readme.txt': b'not ignored'}),
], ids=['AA', 'AB', 'BA', 'BB', 'two-folders', 'folder-plus-file', 'two-opks', 'opk-plus-file'])
def test_rejects_double_or_mixed_nesting(tmp_path, outer, inner, extra):
    members = shape_members(shape_members(plugin_members(), inner), outer)
    members.update(extra)
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', members)
    with pytest.raises(opkAPI.OPKError):
        opkAPI.inspect_opk(path)


@pytest.mark.parametrize('nested', [None, 'directory', 'opk'])
def test_only_exact_macos_artifacts_disappear_during_extract_and_rebuild(tmp_path, nested):
    kept = dict(plugin_members(), **{
        '._evil.py': b'not AppleDouble',
        'assets/._near-match': b'\x00\x05\x16\x08',
        'assets/__macosx/real.txt': b'not the exact macOS name',
    })
    members = shape_members(dict(kept, **MACOS_NOISE), nested)
    if nested:
        members.update(MACOS_NOISE)
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', members)
    assert opkAPI.inspect_opk(path)['nested'] == nested
    destination = tmp_path / 'unpacked'
    opkAPI.extract_opk(path, destination)
    assert {p.relative_to(destination).as_posix(): p.read_bytes()
            for p in destination.rglob('*') if p.is_file()} == kept
    opkAPI.rebuild_opk_file(path, path)
    assert archive_members(path) == kept


@pytest.mark.parametrize('bad_path', [
    '../outside.txt', r'..\outside.txt', '/rooted.txt', 'C:/drive.txt',
    'assets/config.txt:alternate', 'assets/control\x01.txt',
])
@pytest.mark.parametrize('nested', [None, 'opk'])
def test_rejects_unsafe_paths_before_writing(tmp_path, bad_path, nested):
    members = dict(plugin_members(), **{bad_path: b'not extracted'})
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', shape_members(members, nested))
    destination = tmp_path / 'unpacked'
    with pytest.raises(opkAPI.OPKError):
        opkAPI.extract_opk(path, destination)
    assert not (tmp_path / 'outside.txt').exists()
    assert not destination.exists() or not list(destination.iterdir())


@pytest.mark.parametrize('nested', [None, 'opk'])
def test_rejects_unix_symlink_members(tmp_path, nested):
    member = zipfile.ZipInfo('assets/link')
    member.create_system = 3
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    members = plugin_members()
    members[member] = b'data.txt'
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', shape_members(members, nested))
    with pytest.raises(opkAPI.OPKError, match='symbolic link'):
        opkAPI.inspect_opk(path)


@pytest.mark.parametrize('paths', [('assets/Entry.txt', 'assets/entry.txt'), ('Straße', 'STRASSE')])
def test_rejects_casefold_collisions(tmp_path, paths):
    members = dict(plugin_members(), **dict.fromkeys(paths, b'collision'))
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', members)
    with pytest.raises(opkAPI.OPKError, match='Conflicting OPK path'):
        opkAPI.inspect_opk(path)


@pytest.mark.parametrize('limit', ['member-count', 'compression-ratio'])
def test_rejects_zip_bomb_limits(tmp_path, limit):
    members = plugin_members()
    if limit == 'member-count':
        members.update({f'data/{i}': b'' for i in range(5001 - len(members))})
    else:
        members['data/compressible.bin'] = b'\0' * (1024 * 1024)
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', members)
    with pytest.raises(opkAPI.OPKError) as caught:
        opkAPI.inspect_opk(path)
    assert caught.value.code == 'archive_limit'


@pytest.mark.parametrize('nested', [None, 'opk'])
def test_expanded_total_and_inner_archive_size_boundaries(tmp_path, monkeypatch, nested):
    members = shape_members(plugin_members(), nested)
    size = sum(map(len, members.values()))
    constant = 'MAX_INNER_OPK_SIZE' if nested else 'MAX_TOTAL_SIZE'
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', members)
    monkeypatch.setattr(opkAPI, constant, size)
    assert opkAPI.inspect_opk(path)['nested'] == nested
    monkeypatch.setattr(opkAPI, constant, size - 1)
    with pytest.raises(opkAPI.OPKError) as caught:
        opkAPI.inspect_opk(path)
    assert caught.value.code == 'archive_limit'


def test_binary_warnings_do_not_include_webui_assets_or_block_rebuild(tmp_path):
    binary_paths = [f'bin/program.{suffix}' for suffix in (
        'EXE', 'dll', 'so', 'dylib', 'pyd', 'bat', 'cmd', 'ps1', 'vbs', 'jse', 'wsf', 'scr', 'com',
    )]
    static_paths = ['webui/index.html', 'webui/main.css', 'webui/app.js']
    members = dict(plugin_members(), **dict.fromkeys(binary_paths + static_paths, b'fixture'))
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', shape_members(members, 'directory'))
    assert set(opkAPI.inspect_opk(path)['binary_warnings']) == set(binary_paths)
    opkAPI.rebuild_opk_file(path, path)
    assert archive_members(path) == members


@pytest.mark.parametrize('packed', [False, True])
@pytest.mark.parametrize('raw,marker,code', [
    (BOM + b'{}', 'BOM', 'utf8_bom'),
    (b'{"name": }', 'JSON', 'invalid_json'),
    (b'[]', 'JSON', 'invalid_manifest'),
    (b'\xff', 'UTF-8', 'invalid_encoding'),
], ids=['bom', 'syntax', 'non-object', 'invalid-encoding'])
def test_manifest_errors_report_the_actual_parse_problem(tmp_path, packed, raw, marker, code):
    with pytest.raises(opkAPI.OPKError) as caught:
        if packed:
            members = dict(plugin_members(), **{'app.json': raw})
            opkAPI.inspect_opk(write_opk(tmp_path / f'{NAMESPACE}.opk', members))
        else:
            manifest = tmp_path / 'app.json'
            manifest.write_bytes(raw)
            opkAPI.load_app_json_file(manifest)
    assert marker in str(caught.value)
    assert 'not found' not in str(caught.value).lower()
    assert caught.value.code == code


def test_missing_manifest_is_distinct_from_invalid_manifest(tmp_path):
    with pytest.raises(opkAPI.OPKError) as caught:
        opkAPI.load_app_json_file(tmp_path / 'app.json')
    assert caught.value.code == 'not_found'


@pytest.mark.parametrize('field,value', [
    ('name', ''), ('priority', True), ('support', {}), ('namespace', ''),
    ('namespace', '../outside'), ('namespace', 'class'), ('namespace', '.hidden'),
    ('compatible_svn', infoAPI.OlivOS_SVN_OldCompatible - 1),
])
def test_invalid_manifest_fields_are_rejected(tmp_path, field, value):
    members = plugin_members()
    manifest = json.loads(members['app.json'])
    manifest[field] = value
    members['app.json'] = json.dumps(manifest).encode('utf-8')
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', members)
    with pytest.raises(opkAPI.OPKError):
        opkAPI.inspect_opk(path)


def test_old_compatible_version_warns_without_rejecting(tmp_path):
    members = plugin_members()
    manifest = json.loads(members['app.json'])
    manifest['compatible_svn'] = infoAPI.OlivOS_SVN_OldCompatible
    members['app.json'] = json.dumps(manifest).encode('utf-8')
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', members)
    assert opkAPI.inspect_opk(path)['warnings']


def test_missing_python_entry_is_rejected(tmp_path):
    members = plugin_members()
    del members['main.py']
    with pytest.raises(opkAPI.OPKError, match=r'main\.py'):
        opkAPI.inspect_opk(write_opk(tmp_path / f'{NAMESPACE}.opk', members))


@pytest.mark.parametrize('explicit', [False, True])
def test_accepts_chinese_identifiers_as_manifest_or_fallback_namespace(tmp_path, explicit):
    namespace = '中文插件'
    members = plugin_members(namespace)
    if not explicit:
        manifest = json.loads(members['app.json'])
        del manifest['namespace']
        members['app.json'] = json.dumps(manifest).encode('utf-8')
    path = write_opk(tmp_path / f'{namespace}.opk', members)
    assert opkAPI.inspect_opk(path, require_exact_filename=True)['namespace'] == namespace


@pytest.mark.parametrize('filename', [f'{NAMESPACE.lower()}.opk', f'{NAMESPACE}-v2.0.opk'])
def test_strict_filename_mismatch_requests_exact_rename_without_breaking_legacy_read(tmp_path, filename):
    path = write_opk(tmp_path / filename)
    assert opkAPI.inspect_opk(path)['namespace'] == NAMESPACE
    with pytest.raises(opkAPI.OPKError, match=rf'{NAMESPACE}\.opk'):
        opkAPI.inspect_opk(path, require_exact_filename=True)


@pytest.fixture
def app_dir(tmp_path):
    path = tmp_path / 'plugin/app'
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def loader_runtime(app_dir, tmp_path, monkeypatch):
    temp_dir = tmp_path / 'plugin/tmp'
    temp_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pluginAPI, 'plugin_path', str(app_dir) + '/')
    monkeypatch.setattr(pluginAPI, 'plugin_path_tmp', str(temp_dir) + '/')
    monkeypatch.syspath_prepend(str(app_dir))
    monkeypatch.syspath_prepend(str(temp_dir))
    loader = pluginAPI.shallow(control_queue=queue.Queue())
    loader.database = SimpleNamespace(_init_namespace=lambda namespace: None)
    loader.opk_test_inits = 0
    logs = []
    monkeypatch.setattr(loader, 'log', lambda level, message, *args, **kwargs: logs.append((level, message)))
    yield loader, logs
    for module in list(sys.modules):
        if module == NAMESPACE or module.startswith(NAMESPACE + '.'):
            sys.modules.pop(module)


def publish_ready(loader, host):
    loader.sendPluginList(ready=True)
    packets = loader.Proc_info.control_queue
    while not packets.empty():
        host.consume(packets.get_nowait())


@pytest.mark.parametrize('nested', ['directory', 'opk'])
def test_loader_normalizes_successful_nested_opks_in_place(app_dir, loader_runtime, nested, monkeypatch):
    loader, logs = loader_runtime
    members = plugin_members()
    installed = write_opk(app_dir / '中文分类/historical-name.opk', shape_members(members, nested))
    installed = installed.resolve()
    real_replace = opkAPI.os.replace
    replacements = []

    def replace(source, target):
        if Path(target).resolve() == installed:
            assert loader.opk_test_inits == 1
            assert Path(source).parent.resolve() == installed.parent
            assert opkAPI.inspect_opk(installed)['nested'] == nested
            replacements.append(Path(target).resolve())
        return real_replace(source, target)

    monkeypatch.setattr(opkAPI.os, 'replace', replace)
    loader.load_plugin_list()
    assert NAMESPACE in loader.plugin_models_dict
    assert loader.opk_test_inits == 1
    assert replacements == [installed]
    assert archive_members(installed) == members
    assert list(installed.parent.iterdir()) == [installed]
    assert any(level == 2 and installed.name in message for level, message in logs)


@pytest.mark.parametrize('nested', ['directory', 'opk'])
@pytest.mark.parametrize('failure', ['import', 'init'])
def test_loader_keeps_nested_archive_unchanged_on_plugin_failure(app_dir, loader_runtime, nested, failure):
    loader, logs = loader_runtime
    members = plugin_members()
    if failure == 'import':
        members['__init__.py'] = b'raise RuntimeError("fixture import failure")\n'
    else:
        members['main.py'] = members['main.py'].replace(
            b'Proc.opk_test_inits += 1', b'raise RuntimeError("fixture init failure")')
    installed = write_opk(app_dir / f'{NAMESPACE}.opk', shape_members(members, nested))
    original = installed.read_bytes()
    loader.load_plugin_list()
    assert any(level == 4 and f'fixture {failure} failure' in message for level, message in logs)
    assert installed.read_bytes() == original
    assert loader.opk_test_inits == 0


@pytest.mark.parametrize('nested', ['directory', 'opk'])
def test_locked_nested_archive_warns_and_plugin_still_runs(app_dir, loader_runtime, nested, monkeypatch):
    loader, logs = loader_runtime
    installed = write_opk(app_dir / f'{NAMESPACE}.opk', shape_members(plugin_members(), nested))
    original = installed.read_bytes()
    real_replace = opkAPI.os.replace

    def replace(source, target):
        if Path(target).resolve() == installed:
            raise PermissionError('fixture locked archive')
        return real_replace(source, target)

    monkeypatch.setattr(opkAPI.os, 'replace', replace)
    loader.load_plugin_list()
    assert loader.opk_test_inits == 1
    assert NAMESPACE in loader.plugin_models_call_list
    assert any(level == 3 and 'fixture locked archive' in message for level, message in logs)
    assert installed.read_bytes() == original
    assert list(app_dir.iterdir()) == [installed]


@pytest.mark.parametrize('packed', [False, True])
def test_loader_skips_bom_with_specific_error(app_dir, loader_runtime, packed):
    loader, logs = loader_runtime
    members = plugin_members()
    members['app.json'] = BOM + members['app.json']
    if packed:
        write_opk(app_dir / f'{NAMESPACE}.opk', members)
    else:
        write_source(app_dir / NAMESPACE, members)
    loader.load_plugin_list()
    assert NAMESPACE not in loader.plugin_models_dict
    errors = [message for level, message in logs if level == 4]
    assert any('app.json' in message and 'BOM' in message for message in errors)
    assert not any('app.json not found' in message for message in errors)


@pytest.fixture
def host(tmp_path, app_dir):
    service = make_host(root_path=tmp_path, rx_queue=queue.Queue(), control_queue=queue.Queue())
    yield service
    service.on_terminate()


@pytest.fixture
def client(host):
    client = host.app.test_client()
    client.environ_base['HTTP_X_AUTH_TOKEN'] = host.test_token
    return client


@pytest.mark.parametrize('is_opk', [False, True])
def test_runtime_reports_precise_source_without_changing_seven_legacy_fields(
    app_dir, client, host, loader_runtime, is_opk,
):
    loader, _ = loader_runtime
    relative = '中文分类/' + ('historical-release.opk' if is_opk else NAMESPACE)
    (write_opk if is_opk else write_source)(app_dir / relative)
    loader.load_plugin_list()
    publish_ready(loader, host)
    payload = client.get('/api/plugins').json
    assert len(payload['shallow_plugin_data_dict'][NAMESPACE]) == 7
    assert payload['shallow_plugin_source_dict'][NAMESPACE] == {'path': relative, 'is_opk': is_opk}
    assert payload['shallow_plugin_shadowed_list'] == []


def test_duplicate_inventory_marks_only_the_loader_winner_active(app_dir, client, host, loader_runtime):
    loader, logs = loader_runtime
    source = '源码分类/' + NAMESPACE
    packed = '发布分类/' + NAMESPACE + '.opk'
    write_source(app_dir / source)
    write_opk(app_dir / packed, plugin_members(version='2.0', svn=2))
    loader.load_plugin_list()
    publish_ready(loader, host)
    runtime = client.get('/api/plugins').json
    winner = runtime['shallow_plugin_source_dict'][NAMESPACE]
    candidates = {source: False, packed: True}
    assert winner['is_opk'] == candidates[winner['path']]
    shadow, = runtime['shallow_plugin_shadowed_list']
    loser = next(path for path in candidates if path != winner['path'])
    assert shadow == {'namespace': NAMESPACE, 'path': loser, 'is_opk': candidates[loser]}
    assert any(level == 3 and NAMESPACE in message for level, message in logs)
    duplicate, = client.get(FILES_URL).json['duplicates']
    assert duplicate['key'] == NAMESPACE.casefold()
    assert duplicate['has_source'] is True
    assert duplicate['has_case_conflict'] is False
    assert duplicate['active_path'] == winner['path']
    assert {item['path']: item['loaded'] for item in duplicate['items']} == {
        path: path == winner['path'] for path in candidates
    }


@pytest.mark.parametrize('method,path,limit', [
    ('POST', STAGE_URL, 100 * 1024 * 1024),
    ('GET', STAGE_URL, 10 * 1024 * 1024),
    ('POST', STAGE_URL + '/', 10 * 1024 * 1024),
    ('POST', BATCH_URL + 'validate', 10 * 1024 * 1024),
])
@pytest.mark.parametrize('over_limit', [False, True], ids=['exact-limit', 'limit-plus-one'])
def test_content_length_boundary_before_reading_any_body(host, monkeypatch, method, path, limit, over_limit):
    async def chunks(chunk_size):
        yield b'body'

    def never_read(*args, **kwargs):
        pytest.fail('oversize Content-Length must be rejected without reading the body')

    async def dispatch(request, body, length):
        assert not over_limit
        assert length == 4
        assert body.read() == b'body'
        return SimpleNamespace(status=200)

    monkeypatch.setattr(host, '_dispatch_http', dispatch)
    declared = limit + over_limit
    request = SimpleNamespace(
        method=method, path=path, content_length=declared,
        headers=CIMultiDict({'Content-Length': str(declared), 'X-Auth-Token': host.test_token}),
        content=SimpleNamespace(iter_chunked=never_read if over_limit else chunks), read=never_read,
    )
    response = asyncio.run(host.http(request))
    assert response.status == (413 if over_limit else 200)
    if over_limit:
        assert json.loads(response.body)['error']


@pytest.mark.parametrize('method,path,limit', [
    ('POST', STAGE_URL, 8),
    ('GET', STAGE_URL, 4),
    ('POST', BATCH_URL + 'validate', 4),
])
@pytest.mark.parametrize('over_limit', [False, True], ids=['exact-limit', 'limit-plus-one'])
def test_chunked_body_without_content_length_uses_route_specific_limit(
    host, monkeypatch, method, path, limit, over_limit,
):
    monkeypatch.setattr(serverAPI, 'HTTP_BODY_LIMIT', 4)
    monkeypatch.setattr(serverAPI, 'UPLOAD_BODY_LIMIT', 8)

    async def chunks(chunk_size):
        yield b'a' * (limit - 1)
        yield b'b' * (1 + over_limit)
        if over_limit:
            pytest.fail('body continued streaming after its limit was exceeded')

    async def never_read():
        pytest.fail('must use the bounded streaming API, not request.read()')

    async def dispatch(request, body, length):
        assert not over_limit
        assert length == limit
        assert body.read() == b'a' * (limit - 1) + b'b'
        return SimpleNamespace(status=200)

    monkeypatch.setattr(host, '_dispatch_http', dispatch)
    request = SimpleNamespace(
        method=method, path=path, content_length=None,
        headers=CIMultiDict({'Transfer-Encoding': 'chunked', 'X-Auth-Token': host.test_token}),
        content=SimpleNamespace(iter_chunked=chunks), read=never_read,
    )
    response = asyncio.run(host.http(request))
    assert response.status == (413 if over_limit else 200)
    if over_limit:
        assert json.loads(response.body)['error']


def test_authenticated_chunked_multipart_upload_crosses_http_wsgi_bridge(host, app_dir):
    upload_file = FileStorage(io.BytesIO(zip_bytes(plugin_members())), filename=f'{NAMESPACE}.opk')
    boundary, encoded = encode_multipart({'file': upload_file, 'target_dir': ''})

    async def chunks(chunk_size):
        yield encoded[:97]
        yield encoded[97:]

    request = SimpleNamespace(
        method='POST', path=STAGE_URL, content_length=None, content=SimpleNamespace(iter_chunked=chunks),
        scheme='http', host='127.0.0.1', remote='127.0.0.1', transport=None, query_string='',
        headers=CIMultiDict({
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Transfer-Encoding': 'chunked',
            'X-Auth-Token': host.test_token,
        }),
    )
    response = asyncio.run(host.http(request))
    assert response.status == 200
    item = json.loads(response.body)
    assert item['can_commit'] is True
    assert item['namespace'] == NAMESPACE
    assert not list(app_dir.iterdir())


def upload(client, members=None, *, filename=f'{NAMESPACE}.opk', target_dir=''):
    body = zip_bytes(plugin_members() if members is None else members)
    return client.post(STAGE_URL, data={'file': (io.BytesIO(body), filename), 'target_dir': target_dir})


def stage(client, members=None, **kwargs):
    response = upload(client, members, **kwargs)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.json['upload_id']
    return response.json


def inventory(client):
    response = client.get(FILES_URL)
    assert response.status_code == 200
    return response.json


def change(client, uploads=(), deletes=()):
    return {'revision': inventory(client)['revision'], 'uploads': list(uploads), 'deletes': list(deletes)}


def edit_upload(staged, **settings):
    return dict({'upload_id': staged['upload_id'], 'target_dir': staged['target_dir']}, **settings)


def installed_tree(app_dir):
    return {item.relative_to(app_dir).as_posix(): item.read_bytes() if item.is_file() else None
            for item in app_dir.rglob('*')}


@pytest.mark.parametrize('method,path', [
    ('GET', FILES_URL), ('POST', STAGE_URL), ('DELETE', STAGE_URL),
    ('DELETE', STAGE_URL + '/unknown'), ('POST', BATCH_URL + 'validate'), ('POST', BATCH_URL + 'commit'),
])
def test_plugin_file_routes_require_existing_webui_login(host, method, path):
    assert host.app.test_client().open(path, method=method).status_code == 401


def test_stage_rejects_zip_extension_even_with_valid_plugin_bytes(app_dir, client):
    response = upload(client, filename=f'{NAMESPACE}.zip')
    assert response.status_code == 400
    assert '.opk' in response.json['error']
    assert inventory(client)['staged'] == []
    assert not list(app_dir.iterdir())


@pytest.mark.parametrize('defect', ['bom', 'filename', 'not-zip'])
def test_stage_reports_invalid_items_without_installing(client, app_dir, defect):
    if defect == 'not-zip':
        response = client.post(STAGE_URL, data={'file': (io.BytesIO(b'not a ZIP'), f'{NAMESPACE}.opk')})
        assert response.status_code == 200
        item = response.json
    else:
        members = plugin_members()
        if defect == 'bom':
            members['app.json'] = BOM + members['app.json']
        filename = f'{NAMESPACE.lower() if defect == "filename" else NAMESPACE}.opk'
        item = stage(client, members, filename=filename)
    assert item['can_commit'] is False
    assert item['errors']
    assert item['bom_error'] is (defect == 'bom')
    if defect == 'bom':
        assert any('BOM' in error and 'not found' not in error for error in item['errors'])
    elif defect == 'filename':
        assert any(f'{NAMESPACE}.opk' in error for error in item['errors'])
    assert installed_tree(app_dir) == {}


def test_inventory_recurses_categories_but_stops_at_source_plugins(app_dir, client):
    (app_dir / '空分类/空子目录').mkdir(parents=True)
    (app_dir / '.hidden').mkdir()
    source = write_source(app_dir / '源码分类' / NAMESPACE)
    source_opk = write_opk(source / 'private/Private.opk', plugin_members('Private'))
    members = plugin_members('BrokenSource')
    members['app.json'] = BOM + members['app.json']
    write_source(app_dir / 'BrokenSource', members)
    write_opk(app_dir / 'BrokenArchive.opk', members)
    payload = inventory(client)
    assert set(payload) == {'revision', 'folders', 'source_plugins', 'opks', 'duplicates', 'staged', 'reload_required'}
    assert len(payload['revision']) == 64 and int(payload['revision'], 16) >= 0
    assert {folder['path'] for folder in payload['folders']} == {'', '空分类', '空分类/空子目录', '源码分类'}
    folders = {folder['path']: folder for folder in payload['folders']}
    assert folders['空分类/空子目录'] == {'path': '空分类/空子目录', 'source_count': 0, 'opk_count': 0}
    sources = {item['path']: item for item in payload['source_plugins']}
    assert sources[source.relative_to(app_dir).as_posix()]['namespace'] == NAMESPACE
    assert sources['BrokenSource']['bom_error'] is True
    assert sources['BrokenSource']['parse_error']
    assert {item['path'] for item in payload['opks']} == {'BrokenArchive.opk'}
    archive, = payload['opks']
    assert archive['bom_error'] is True
    assert archive['parse_error']
    assert source_opk.is_file()


@pytest.mark.parametrize('target', ['source', 'source/subdirectory'])
def test_batch_protects_source_directory_and_files(app_dir, client, target):
    source = write_source(app_dir / 'source', plugin_members('ExistingSource'))
    private_archive = write_opk(source / 'subdirectory/Private.opk', plugin_members('Private'))
    staged = stage(client)
    before = installed_tree(app_dir)
    paths = ['source', private_archive.relative_to(app_dir).as_posix()]
    data = change(client, [edit_upload(staged, target_dir=target)], paths)
    response = client.post(BATCH_URL + 'validate', json=data)
    assert response.status_code == 200
    assert response.json['ok'] is False
    assert set(response.json['item_errors']) == {staged['upload_id'], *paths}
    response = client.post(BATCH_URL + 'commit', json=data)
    assert response.status_code == 400
    assert response.json['ok'] is False
    assert installed_tree(app_dir) == before


def test_stage_blocks_same_namespace_as_source_in_another_category(app_dir, client):
    source_path = 'legacy/source-name'
    write_source(app_dir / source_path)
    staged = stage(client)
    assert staged['can_commit'] is False
    assert any(source_path in error for error in staged['errors'])


@pytest.mark.parametrize('collision', ['manifest-opk', 'manifest-source', 'file-stem'])
def test_stage_blocks_disk_wide_case_conflicts(app_dir, client, collision):
    lower = NAMESPACE.lower()
    if collision == 'manifest-opk':
        write_opk(app_dir / 'other/historic.opk', plugin_members(lower))
    elif collision == 'manifest-source':
        write_source(app_dir / 'other/source', plugin_members(lower))
    else:
        write_opk(app_dir / f'other/{lower}.opk', plugin_members('UnrelatedNamespace'))
    staged = stage(client)
    assert staged['can_commit'] is False
    assert any(NAMESPACE in error or lower in error for error in staged['errors'])


def test_inventory_groups_casefold_conflicts_across_categories(app_dir, client):
    lower = NAMESPACE.lower()
    write_opk(app_dir / f'a/{NAMESPACE}.opk')
    write_opk(app_dir / f'b/{lower}.opk', plugin_members(lower))
    group, = inventory(client)['duplicates']
    assert group['key'] == NAMESPACE.casefold()
    assert set(group['namespaces']) == {NAMESPACE, lower}
    assert group['has_case_conflict'] is True
    assert group['has_source'] is False
    assert not group['active_path']


@pytest.mark.parametrize('other_namespace', [NAMESPACE, NAMESPACE.lower()], ids=['identical', 'case-only'])
def test_batch_rejects_conflicts_between_staged_uploads(app_dir, client, other_namespace):
    first = stage(client)
    other = stage(client, plugin_members(other_namespace), filename=f'{other_namespace}.opk')
    data = change(client, [edit_upload(first), edit_upload(other)])
    response = client.post(BATCH_URL + 'validate', json=data)
    assert response.status_code == 200
    assert response.json['ok'] is False
    assert response.json['item_errors']
    assert installed_tree(app_dir) == {}


def test_marking_an_existing_opk_for_deletion_does_not_bypass_case_conflict(app_dir, client):
    path = f'other/{NAMESPACE.lower()}.opk'
    write_opk(app_dir / path, plugin_members(NAMESPACE.lower()))
    staged = stage(client)
    before = installed_tree(app_dir)
    data = change(client, [edit_upload(staged)], [path])
    response = client.post(BATCH_URL + 'commit', json=data)
    assert response.status_code == 400
    assert staged['upload_id'] in response.json['item_errors']
    assert installed_tree(app_dir) == before


def test_same_directory_overwrite_reports_existing_version_and_plans_replace(app_dir, client):
    path = f'分类/{NAMESPACE}.opk'
    existing = write_opk(app_dir / path, plugin_members(version='1.2', svn=12))
    original = existing.read_bytes()
    staged = stage(client, plugin_members(version='2.0', svn=20), target_dir='分类')
    assert staged['can_commit'] is True
    assert staged['same_dir_overwrite'] is True
    old, = staged['existing_opks']
    assert (old['path'], old['parent_dir'], old['version'], old['svn']) == (path, '分类', '1.2', 12)
    data = change(client, [edit_upload(staged)])
    response = client.post(BATCH_URL + 'validate', json=data)
    assert response.status_code == 200
    assert response.json['ok'] is True
    assert response.json['plan']['will_overwrite'] == [path]
    assert existing.read_bytes() == original
    response = client.post(BATCH_URL + 'commit', json=data)
    assert response.status_code == 200
    assert response.json['ok'] is True
    assert opkAPI.inspect_opk(existing)['manifest']['version'] == '2.0'


@pytest.mark.parametrize('keep', ['new', 'old-b'])
def test_cross_directory_dedup_requires_explicit_choice_and_removes_other_opks(app_dir, client, keep):
    path = f'{NAMESPACE}.opk'
    for parent in ('old-a', 'old-b'):
        write_opk(app_dir / parent / path)
    (app_dir / 'new').mkdir()
    staged = stage(client, plugin_members(version='2.0'), target_dir='new')
    assert staged['same_dir_overwrite'] is False
    assert staged['placement_options'][0] == 'new'
    assert set(staged['placement_options']) == {'new', 'old-a', 'old-b'}
    before = installed_tree(app_dir)
    for rejected in (edit_upload(staged), edit_upload(staged, keep_dir='not-a-choice')):
        response = client.post(BATCH_URL + 'validate', json=change(client, [rejected]))
        assert response.status_code == 200
        assert response.json['ok'] is False
        assert staged['upload_id'] in response.json['item_errors']
    data = change(client, [edit_upload(staged, keep_dir=keep)])
    response = client.post(BATCH_URL + 'validate', json=data)
    assert response.json['ok'] is True
    dedup = {f'{parent}/{path}' for parent in ('old-a', 'old-b') if parent != keep}
    assert set(response.json['plan']['will_dedup_delete']) == dedup
    assert installed_tree(app_dir) == before
    response = client.post(BATCH_URL + 'commit', json=data)
    assert response.status_code == 200
    assert response.json['ok'] is True
    assert {item['path'] for item in inventory(client)['opks']} == {f'{keep}/{path}'}
    assert opkAPI.inspect_opk(app_dir / keep / path)['manifest']['version'] == '2.0'
    assert all((app_dir / parent).is_dir() for parent in ('old-a', 'old-b', 'new'))


def test_staging_and_individual_or_global_cancel_never_change_installed_tree(app_dir, client, tmp_path):
    installed = write_opk(app_dir / f'{NAMESPACE}.opk')
    before = installed_tree(app_dir)
    first = stage(client, plugin_members(version='2.0'))
    second = stage(client, plugin_members('Another'), filename='Another.opk')
    stage_root = tmp_path / 'plugin/tmp/webui-stage'
    for item in (first, second):
        assert (stage_root / item['upload_id'] / 'upload.opk').is_file()
    assert {item['upload_id'] for item in inventory(client)['staged']} == {first['upload_id'], second['upload_id']}
    assert client.delete(f"{STAGE_URL}/{first['upload_id']}").status_code in (200, 204)
    assert not (stage_root / first['upload_id']).exists()
    assert [item['upload_id'] for item in inventory(client)['staged']] == [second['upload_id']]
    assert client.delete(STAGE_URL).status_code in (200, 204)
    assert not (stage_root / second['upload_id']).exists()
    assert inventory(client)['staged'] == []
    assert installed_tree(app_dir) == before
    assert installed.is_file()


def test_invalid_batch_does_not_apply_valid_upload_or_delete(app_dir, client):
    write_opk(app_dir / 'Removable.opk', plugin_members('Removable'))
    staged = stage(client)
    before = installed_tree(app_dir)
    data = change(client, [edit_upload(staged)], ['Removable.opk', 'missing.opk'])
    validation = client.post(BATCH_URL + 'validate', json=data)
    assert validation.status_code == 200
    assert validation.json['ok'] is False
    assert 'missing.opk' in validation.json['item_errors']
    assert installed_tree(app_dir) == before
    commit = client.post(BATCH_URL + 'commit', json=data)
    assert commit.status_code == 400
    assert commit.json['item_errors'] == validation.json['item_errors']
    assert installed_tree(app_dir) == before
    assert inventory(client)['staged'][0]['upload_id'] == staged['upload_id']


def test_batch_requires_confirmation_for_sensitive_binary(app_dir, client):
    members = dict(plugin_members(), **{'bin/native.dll': b'fixture'})
    staged = stage(client, members)
    assert staged['can_commit'] is True
    assert staged['binary_warnings'] == ['bin/native.dll']
    for not_confirmed in (edit_upload(staged), edit_upload(staged, confirm_binaries='true')):
        response = client.post(BATCH_URL + 'validate', json=change(client, [not_confirmed]))
        assert response.json['ok'] is False
        assert staged['upload_id'] in response.json['item_errors']
    confirmed = edit_upload(staged, confirm_binaries=True)
    response = client.post(BATCH_URL + 'validate', json=change(client, [confirmed]))
    assert response.json['ok'] is True
    assert installed_tree(app_dir) == {}


def test_batch_commit_normalizes_upload_and_deletes_opk_without_reloading(app_dir, client, host, loader_runtime):
    loader, _ = loader_runtime
    old = write_opk(app_dir / 'Retired.opk', plugin_members('Retired'))
    members = dict(plugin_members(), **MACOS_NOISE)
    staged = stage(client, shape_members(members, 'opk'))
    assert staged['nested'] == 'opk'
    before = installed_tree(app_dir)
    data = change(client, [edit_upload(staged)], [old.name])
    response = client.post(BATCH_URL + 'validate', json=data)
    assert response.status_code == 200
    assert response.json['ok'] is True
    assert response.json['plan']['will_write'] == [f'{NAMESPACE}.opk']
    assert response.json['plan']['will_delete'] == [old.name]
    assert installed_tree(app_dir) == before
    response = client.post(BATCH_URL + 'commit', json=data)
    assert response.status_code == 200
    assert response.json['ok'] is True
    assert response.json['reload_required'] is True
    assert {(item['action'], item['path'], item['ok']) for item in response.json['applied']} == {
        ('write', f'{NAMESPACE}.opk', True), ('delete', old.name, True),
    }
    assert not old.exists()
    assert archive_members(app_dir / f'{NAMESPACE}.opk') == plugin_members()
    disk = inventory(client)
    assert disk['revision'] == response.json['revision'] != data['revision']
    assert disk['reload_required'] is True
    assert disk['staged'] == []
    assert host.Proc_info.control_queue.empty()
    assert NAMESPACE not in client.get('/api/plugins').json['shallow_plugin_data_dict']
    loader.Proc_data['webui_load_started'] = time.time()
    loader.load_plugin_list()
    publish_ready(loader, host)
    assert inventory(client)['reload_required'] is False


@pytest.mark.parametrize('endpoint', ['validate', 'commit'])
@pytest.mark.parametrize('external_change', ['directory', 'archive'])
def test_stale_inventory_revision_reports_conflict_without_modifying_disk(app_dir, client, endpoint, external_change):
    staged = stage(client)
    old = write_opk(app_dir / 'External.opk', plugin_members('External'))
    data = change(client, [edit_upload(staged)])
    if external_change == 'directory':
        (app_dir / 'new-empty-category').mkdir()
    else:
        write_opk(old, plugin_members('External', version='2.0-local-update'))
    before = installed_tree(app_dir)
    response = client.post(BATCH_URL + endpoint, json=data)
    assert response.status_code == 409
    assert response.json['ok'] is False
    assert response.json['conflict'] is True
    assert installed_tree(app_dir) == before


@pytest.mark.parametrize('link_kind', ['symlink', 'junction'])
def test_linked_category_cannot_be_used_to_write_or_delete(app_dir, client, tmp_path, link_kind):
    outside = tmp_path / 'outside'
    external = write_opk(outside / 'External.opk', plugin_members('External'))
    original = external.read_bytes()
    link = app_dir / 'linked'
    if link_kind == 'junction':
        if sys.platform != 'win32':
            pytest.skip('Junctions are unavailable outside Windows')
        import _winapi
        _winapi.CreateJunction(str(outside), str(link))
    else:
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip('Creating directory symlinks is unavailable')
    staged = stage(client)
    snapshot = inventory(client)
    assert 'linked' not in {item['path'] for item in snapshot['folders']}
    assert not snapshot['opks']
    delete_path = 'linked/External.opk'
    data = change(client, [edit_upload(staged, target_dir='linked')], [delete_path])
    response = client.post(BATCH_URL + 'commit', json=data)
    assert response.status_code == 400
    assert set(response.json['item_errors']) == {staged['upload_id'], delete_path}
    assert external.read_bytes() == original
    assert not (outside / f'{NAMESPACE}.opk').exists()


def test_linked_opk_cannot_be_written_or_deleted(app_dir, client, tmp_path):
    outside = write_opk(tmp_path / 'external.opk')
    original = outside.read_bytes()
    path = f'{NAMESPACE}.opk'
    link = app_dir / path
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip('Creating file symlinks is unavailable')
    staged = stage(client)
    data = change(client, [edit_upload(staged)], [path])
    response = client.post(BATCH_URL + 'commit', json=data)
    assert response.status_code == 400
    assert set(response.json['item_errors']) == {staged['upload_id'], path}
    assert link.is_symlink()
    assert outside.read_bytes() == original


def test_expired_stage_is_removed_and_cannot_be_committed(app_dir, client, host, monkeypatch):
    staged = stage(client)
    body = change(client, [edit_upload(staged)])
    stage_root = host.root / 'plugin/tmp/webui-stage' / staged['upload_id']
    now = time.monotonic()
    monkeypatch.setattr('OlivOS.webUI.pluginFileAPI.time', SimpleNamespace(monotonic=lambda: now + 15 * 60))
    host.plugin_stage.expire()
    assert not stage_root.exists()
    assert inventory(client)['staged'] == []
    response = client.post(BATCH_URL + 'commit', json=body)
    assert response.status_code == 400
    assert staged['upload_id'] in response.json['item_errors']
    assert installed_tree(app_dir) == {}


def test_failed_write_preserves_dedup_copy_and_staged_upload(app_dir, client, monkeypatch):
    installed = write_opk(app_dir / f'old/{NAMESPACE}.opk')
    staged = stage(client)
    body = change(client, [edit_upload(staged, keep_dir='')])

    def locked_file(source, destination):
        raise PermissionError('fixture: destination is locked')

    monkeypatch.setattr(opkAPI, 'rebuild_opk_file', locked_file)
    response = client.post(BATCH_URL + 'commit', json=body)
    assert response.status_code == 200
    assert response.json['ok'] is False
    assert response.json['reload_required'] is False
    assert {(entry['action'], entry['ok']) for entry in response.json['applied']} == {
        ('write', False), ('delete', False),
    }
    assert installed.is_file()
    assert not (app_dir / installed.name).exists()
    assert [item['upload_id'] for item in inventory(client)['staged']] == [staged['upload_id']]


def test_accepts_main_package_directory_entry(tmp_path):
    members = plugin_members()
    main_code = members.pop('main.py')
    members['main/__init__.py'] = main_code
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', members)
    report = opkAPI.inspect_opk(path, require_exact_filename=True)
    assert report['namespace'] == NAMESPACE


def test_bounded_copy_rejects_forged_zip_member_size(tmp_path):
    members = dict(plugin_members(), **{'assets/payload.bin': b'A' * 4096})
    raw = bytearray(zip_bytes(members))
    # 篡改中央目录与本地头中 payload.bin 的 uncompressed size（4096 -> 16），模拟伪造 file_size 的 zip bomb。
    needle = (4096).to_bytes(4, 'little')
    patched = raw.replace(needle, (16).to_bytes(4, 'little'))
    assert patched != raw
    path = tmp_path / f'{NAMESPACE}.opk'
    path.write_bytes(bytes(patched))
    with pytest.raises(opkAPI.OPKError) as caught:
        opkAPI.extract_opk(path, tmp_path / 'out')
    assert caught.value.code == 'invalid_archive'


def test_dot_segment_in_zip_path_is_rejected(tmp_path):
    members = dict(plugin_members(), **{'assets/./sneaky.txt': b'x'})
    path = write_opk(tmp_path / f'{NAMESPACE}.opk', members)
    with pytest.raises(opkAPI.OPKError) as caught:
        opkAPI.inspect_opk(path)
    assert caught.value.code == 'unsafe_path'


def test_root_source_plugin_reports_empty_path_matching_inventory(app_dir, client, host, loader_runtime):
    loader, _ = loader_runtime
    for name, data in plugin_members().items():
        (app_dir / name).write_bytes(data)
    loader.load_plugin_list()
    publish_ready(loader, host)
    source = host.plugin_sources[NAMESPACE]
    assert source == {'is_opk': False, 'path': ''}
    disk = inventory(client)
    assert any(item['path'] == '' and item['loaded'] is True for item in disk['source_plugins'])


def test_stage_rejects_invalid_or_non_object_market_meta(app_dir, client):
    raw = zip_bytes(plugin_members())
    for bad in ('{bad json', '["not-object"]', '123'):
        response = client.post(
            STAGE_URL,
            data={'file': (io.BytesIO(raw), f'{NAMESPACE}.opk'), 'target_dir': '', 'market_meta': bad},
            content_type='multipart/form-data',
        )
        assert response.status_code == 400
        assert 'market_meta' in response.json['error']


def test_stage_enforces_stage_item_and_byte_quotas(app_dir, client, monkeypatch):
    from OlivOS.webUI import pluginFileAPI

    monkeypatch.setattr(pluginFileAPI, 'MAX_STAGE_ITEMS', 1)
    first = stage(client)
    assert first['can_commit'] is True
    raw = zip_bytes(plugin_members('SecondPlugin'))
    response = client.post(
        STAGE_URL,
        data={'file': (io.BytesIO(raw), 'SecondPlugin.opk'), 'target_dir': ''},
        content_type='multipart/form-data',
    )
    assert response.status_code == 400
    assert '上限' in response.json['error']


def test_stage_reports_target_filename_occupied_by_different_namespace(app_dir, client):
    write_opk(app_dir / f'{NAMESPACE}.opk', plugin_members('DifferentNamespace'))
    staged = stage(client)
    assert staged['can_commit'] is False
    assert any('DifferentNamespace' in error for error in staged['errors'])


def test_websocket_request_bypasses_http_body_reader(host, monkeypatch):
    called = []

    async def fake_websocket(request):
        called.append(request.path)
        return SimpleNamespace(status=101)

    def never_read(*args, **kwargs):
        pytest.fail('websocket upgrade must not read HTTP body chunks')

    monkeypatch.setattr(host, 'websocket', fake_websocket)
    request = SimpleNamespace(
        method='GET', path='/ws/logs', content_length=None,
        headers=CIMultiDict(), content=SimpleNamespace(iter_chunked=never_read),
    )
    response = asyncio.run(host.http(request))
    assert response.status == 101
    assert called == ['/ws/logs']


def test_send_plugin_list_tolerates_legacy_unpickled_shallow_without_shadowed_attr(loader_runtime):
    loader, _ = loader_runtime
    del loader.plugin_shadowed_list
    loader.sendPluginList(ready=False)
    packet = loader.Proc_info.control_queue.get_nowait()
    assert packet.key['data']['data']['shallow_plugin_shadowed_list'] == []
