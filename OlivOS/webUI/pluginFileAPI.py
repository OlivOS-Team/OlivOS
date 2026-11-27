# -*- encoding: utf-8 -*-
'''
@File      :   pluginFileAPI.py
@License   :   AGPLv3
@Desc      :   WebUI OPK 文件清单、暂存和批量变更
'''

import hashlib
import json
import stat
import time
from pathlib import PureWindowsPath
from uuid import UUID, uuid4

from flask import abort, g, jsonify, request

from OlivOS.core.core import opkAPI
from . import resourceAPI

STAGE_URL = '/api/plugins/upload/stage'
STAGE_TTL = 15 * 60
MAX_STAGE_ITEMS = 64
MAX_STAGE_BYTES = 512 * 1024 * 1024
MAX_STAGE_FILE_BYTES = 100 * 1024 * 1024
MAX_DEPTH = 10
COPY_CHUNK = 64 * 1024


def _stat(path):
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def _stamp(info):
    if info is not None:
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    return None


def _safe_name(name):
    return (bool(name) and not name.startswith('.') and not name.endswith(('.', ' '))
            and not any(char in '\\/:*?"<>|' or ord(char) < 32 or ord(char) == 127 for char in name)
            and not PureWindowsPath(name).is_reserved())


def _directory(root, path):
    try:
        return not resourceAPI.is_link(root) and resourceAPI.mounted(path, root) and path.is_dir()
    except (FileNotFoundError, NotADirectoryError):
        return False


def _upload_id(value):
    try:
        parsed = UUID(hex=value)
        return parsed.version == 4 and value == parsed.hex
    except (ValueError, AttributeError, TypeError):
        return False


class StageStore:
    """仅回收服务器生成的 UUID 暂存目录；不递归删除外部放入的内容。"""

    def __init__(self, root):
        self.root = root
        self.path = root / 'plugin/tmp/webui-stage'
        self.items = {}

    def _prepare(self):
        path = self.root
        for part in self.path.relative_to(self.root).parts:
            path = path / part
            path.mkdir(exist_ok=True)
            if not _directory(self.root, path):
                raise ValueError('插件上传暂存目录不可用：目录或其上级不能是链接')

    def _staged_bytes(self):
        return sum(item.get('size', 0) for item in self.active().values())

    def save(self, stream):
        self.expire()
        if len(self.items) >= MAX_STAGE_ITEMS:
            raise ValueError(f'同时暂存的上传文件过多（上限 {MAX_STAGE_ITEMS} 个），请先提交或清空草稿')
        remaining = MAX_STAGE_BYTES - self._staged_bytes()
        if remaining <= 0:
            raise ValueError('上传暂存空间已达上限，请先提交或清空草稿')
        self._prepare()
        upload_id = uuid4().hex
        directory = self.path / upload_id
        directory.mkdir()
        path = directory / 'upload.opk'
        max_bytes = min(MAX_STAGE_FILE_BYTES, remaining)
        written = 0
        try:
            with path.open('xb') as output:
                while True:
                    chunk = stream.read(COPY_CHUNK)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_bytes:
                        raise ValueError('上传文件超过单文件或暂存总空间上限')
                    output.write(chunk)
        except BaseException:
            # 即使磁盘满或文件被锁定，也保留原始写入错误。
            try:
                self._cleanup(upload_id)
            except OSError:
                pass
            raise
        return upload_id, path, written

    def _cleanup(self, upload_id):
        directory = self.path / upload_id
        if not _directory(self.root, directory):
            return
        path = directory / 'upload.opk'
        info = _stat(path)
        if info is not None and stat.S_ISREG(info.st_mode) and not resourceAPI.is_link(path):
            path.unlink()
        directory.rmdir()

    def active(self):
        now = time.monotonic()
        return {key: item for key, item in self.items.items() if item['deadline'] > now}

    def source(self, item):
        path = self.path / item['upload_id'] / 'upload.opk'
        if (_directory(self.root, path.parent) and _stamp(_stat(path)) == item['stamp']
                and not resourceAPI.is_link(path)):
            return path
        raise ValueError('暂存文件已被修改或移除，请重新上传')

    def discard(self, upload_id):
        if upload_id not in self.items:
            return False
        self._cleanup(upload_id)
        self.items.pop(upload_id)
        return True

    def _discard_many(self, upload_ids, strict):
        failure = None
        for upload_id in upload_ids:
            try:
                self.discard(upload_id)
            except OSError as error:
                failure = error
        if strict and failure is not None:
            raise failure

    def clear(self, strict=False):
        self._discard_many(list(self.items), strict)

    def expire(self):
        now = time.monotonic()
        self._discard_many([key for key, item in self.items.items() if item['deadline'] <= now], False)

    def clean_residue(self):
        try:
            residues = list(self.path.iterdir()) if _directory(self.root, self.path) else []
        except OSError:
            return  # 暂存不可用不应阻止 WebUI 启动。
        for directory in residues:
            if _upload_id(directory.name):
                try:
                    self._cleanup(directory.name)
                except OSError:
                    # 上次中断遗留的文件可能正被扫描器占用，不影响 WebUI 启动。
                    continue


def _metadata(manifest, namespace):
    return {'namespace': namespace, 'name': manifest.get('name', namespace),
            'version': manifest.get('version', '0'), 'svn': manifest.get('svn', 0)}


def _error_metadata(error, manifest, stem):
    manifest = getattr(error, 'manifest', None) or manifest
    namespace = getattr(error, 'namespace', None) or manifest.get('namespace')
    return _metadata(manifest, namespace if isinstance(namespace, str) and namespace else stem)


def _file_metadata(path, *, packed, fallback):
    manifest = {}
    nested = None
    parse_error = None
    bom_error = False
    try:
        if packed:
            package = opkAPI.inspect_opk(path)
            manifest, namespace, nested = package['manifest'], package['namespace'], package['nested']
        else:
            if _stat(path) is not None and (resourceAPI.is_link(path) or not path.is_file()):
                raise ValueError('app.json 必须为普通文件，不能是链接')
            manifest = opkAPI.load_app_json_file(path)
            namespace, _ = opkAPI.validate_manifest(manifest, fallback)
        metadata = _metadata(manifest, namespace)
    except (OSError, ValueError) as error:
        metadata = _error_metadata(error, manifest, fallback)
        nested = getattr(error, 'nested', None)
        parse_error = str(error)
        bom_error = getattr(error, 'code', None) == 'utf8_bom'
    return dict(metadata, nested=nested, parse_error=parse_error, bom_error=bom_error)


def _duplicates(opks, sources):
    groups = {}
    for packed, items in ((True, opks), (False, sources)):
        for item in items:
            namespace = item['namespace']
            entry = {key: item[key] for key in ('path', 'namespace', 'name', 'version', 'svn', 'loaded')}
            groups.setdefault(namespace.casefold(), []).append(dict(entry, is_opk=packed))
    result = []
    for key, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        namespaces = list(dict.fromkeys(item['namespace'] for item in items))
        result.append({'key': key, 'namespaces': namespaces, 'has_case_conflict': len(namespaces) > 1,
                       'has_source': any(not item['is_opk'] for item in items),
                       'active_path': next((item['path'] for item in items if item['loaded']), None), 'items': items})
    return result


def _scan(host):
    root = host.root / 'plugin/app'
    with host.lock:
        loaded = {(source['is_opk'], source['path']) for source in host.plugin_sources.values()}
        reload_required = bool(host.plugin_files_changed_at)
    folders, sources, opks, tree = [], [], [], []
    stamps = {}

    def walk(directory, depth):
        relative = '' if directory == root else directory.relative_to(root).as_posix()
        parent = relative.rpartition('/')[0]
        manifest = directory / 'app.json'
        manifest_stat = _stat(manifest)
        if manifest_stat is not None:
            metadata = _file_metadata(manifest, packed=False, fallback=directory.name)
            metadata.pop('nested')
            sources.append(dict(metadata, path=relative, parent_dir=parent, loaded=(False, relative) in loaded))
            tree.append((relative, 'source', _stamp(manifest_stat), metadata))
            return
        folders.append({'path': relative, 'opk_count': 0, 'source_count': 0})
        tree.append((relative, 'folder'))
        for path in sorted(directory.iterdir(), key=lambda child: (child.name.casefold(), child.name)):
            if path.name.startswith('.'):
                continue
            name = path.relative_to(root).as_posix()
            info = _stat(path)
            if info is None:
                continue
            if not _safe_name(path.name) or resourceAPI.is_link(path):
                tree.append((name, 'excluded'))
            elif stat.S_ISDIR(info.st_mode) and depth < MAX_DEPTH:
                walk(path, depth + 1)
            elif stat.S_ISREG(info.st_mode) and path.suffix.lower() == '.opk':
                metadata = _file_metadata(path, packed=True, fallback=path.stem)
                stamps[name] = _stamp(info)
                tree.append((name, 'opk', stamps[name], metadata))
                opks.append(dict(metadata, path=name, parent_dir=relative, filename=path.name, size=info.st_size,
                                 loaded=(True, name) in loaded))
            else:
                tree.append((name, stat.S_IFMT(info.st_mode)))

    if _directory(host.root, root):
        walk(root, 0)
    by_folder = {item['path']: item for item in folders}
    for items, key in ((opks, 'opk_count'), (sources, 'source_count')):
        for item in items:
            if item['parent_dir'] in by_folder:
                by_folder[item['parent_dir']][key] += 1
    revision = hashlib.sha256(json.dumps(tree, ensure_ascii=True, sort_keys=True).encode('ascii')).hexdigest()
    result = {'revision': revision, 'folders': folders, 'source_plugins': sources, 'opks': opks,
              'duplicates': _duplicates(opks, sources), 'reload_required': reload_required}
    return result, stamps


def _placement(files, namespace, target):
    errors, existing = [], []
    folders = {item['path'] for item in files['folders']}
    if not isinstance(target, str) or target not in folders:
        errors.append('上传目标必须是现有分类目录，不能选择源码插件目录或链接')
    if namespace is None:
        return errors, existing, []
    folded = namespace.casefold()
    for packed, items in ((False, files['source_plugins']), (True, files['opks'])):
        for item in items:
            identities = [item['namespace']]
            if packed:
                identities.append(item['filename'][:-4])
            path = item['path'] or 'plugin/app'
            clashes = dict.fromkeys(name for name in identities if name.casefold() == folded and name != namespace)
            if clashes:
                errors.append(f'{namespace} 与现有插件 {" / ".join(clashes)}（{path}）大小写冲突；'
                              'namespace 和文件名必须与现有插件大小写完全一致')
            if not packed and item['namespace'] == namespace:
                errors.append(f'已存在同 namespace 的源码插件：{path}')
            if packed and item['namespace'] == namespace:
                existing.append(item)
            elif (packed and isinstance(target, str) and item['parent_dir'] == target
                  and item['filename'].casefold() == f'{namespace}.opk'.casefold()):
                errors.append(f'目标位置已被不同 namespace 的 OPK 占用：{path}（{item["namespace"]}）')
    options = []
    if isinstance(target, str) and any(item['parent_dir'] != target for item in existing):
        options = list(dict.fromkeys([target, *(item['parent_dir'] for item in existing)]))
    return errors, existing, options


def _stage_summary(item, files):
    data = item['summary']
    errors, existing, options = _placement(files, data['namespace'], data['target_dir'])
    errors = data['validation_errors'] + errors
    return dict(data, errors=errors, can_commit=not errors, existing_opks=existing,
                same_dir_overwrite=bool(existing) and not options, placement_options=options)


def _stage(host, upload, target, source, market_meta):
    upload_id, path, size = host.plugin_stage.save(upload.stream)
    data = {'upload_id': upload_id, 'filename': upload.filename, 'target_dir': target, 'source': source,
            'market_meta': market_meta, 'namespace': None, 'name': None, 'version': None, 'svn': None,
            'nested': None, 'binary_warnings': [], 'warnings': [], 'validation_errors': [], 'bom_error': False}
    try:
        package = opkAPI.inspect_opk(path, require_exact_filename=True, filename=upload.filename)
        data.update(_metadata(package['manifest'], package['namespace']), nested=package['nested'],
                    binary_warnings=package['binary_warnings'], warnings=package['warnings'])
    except (OSError, ValueError) as error:
        data.update(_error_metadata(error, {}, None), nested=getattr(error, 'nested', None),
                    binary_warnings=getattr(error, 'binary_warnings', []), warnings=getattr(error, 'warnings', []),
                    validation_errors=[str(error)], bom_error=getattr(error, 'code', None) == 'utf8_bom')
    item = {'upload_id': upload_id, 'summary': data, 'deadline': time.monotonic() + STAGE_TTL,
            'stamp': _stamp(path.lstat()), 'size': size}
    host.plugin_stage.items[upload_id] = item
    files, _ = _scan(host)
    return _stage_summary(item, files)


def _opk_path(host, relative, expected):
    """复查每一级目录，禁止将链接或新增的源码目录用于写入/删除。"""
    root = host.root / 'plugin/app'
    path = root / relative
    if not _directory(host.root, path.parent):
        raise ValueError('插件文件所在目录不存在，或目录路径包含链接')
    parent = path.parent
    while True:
        if _stat(parent / 'app.json') is not None:
            raise ValueError('不能写入或删除源码插件目录中的文件')
        if parent == root:
            break
        parent = parent.parent
    info = _stat(path)
    if info is not None and (not stat.S_ISREG(info.st_mode) or resourceAPI.is_link(path)):
        raise ValueError('目标必须是普通 .opk 文件，不能是目录或链接')
    if _stamp(info) != expected:
        raise ValueError('插件文件已在本次操作期间被修改，请刷新目录后重试')
    return path


def _validate(host, body, files, stamps):
    plan = {key: [] for key in ('will_write', 'will_overwrite', 'will_delete', 'will_dedup_delete', 'warnings')}
    result = {'ok': False, 'errors': [], 'item_errors': {}, 'plan': plan}
    writes, deletes, dedup = {}, {}, {}
    errors = result['errors']
    item_errors = result['item_errors']
    if not isinstance(body, dict) or not isinstance(body.get('revision'), str):
        errors.append('请先读取插件文件列表及 revision')
        return result, writes, deletes, dedup
    if body['revision'] != files['revision']:
        message = '磁盘插件文件已变更，请刷新目录并重新检查待执行变更'
        result.update(conflict=True, error=message)
        errors.append(message)
        return result, writes, deletes, dedup
    uploads, removals = body.get('uploads', []), body.get('deletes', [])
    if not isinstance(uploads, list) or not isinstance(removals, list):
        errors.append('上传和删除操作必须是列表')
        return result, writes, deletes, dedup
    if not uploads and not removals:
        errors.append('至少需要一个上传或删除操作')
    active = host.plugin_stage.active()
    by_path = {item['path']: item for item in files['opks']}
    by_filename = {(item['parent_dir'], item['filename'].casefold()): item['path'] for item in by_path.values()}
    names = {}
    for index, upload in enumerate(uploads, 1):
        if not isinstance(upload, dict) or not isinstance(upload.get('upload_id'), str):
            errors.append(f'第 {index} 个上传项目缺少 upload_id')
            continue
        upload_id = upload['upload_id']
        if upload_id not in active:
            item_errors[upload_id] = ['上传暂存不存在或已过期，请重新上传']
            continue
        item = active[upload_id]
        summary = item['summary']
        namespace = summary['namespace']
        if summary['validation_errors']:
            item_errors[upload_id] = summary['validation_errors']
            continue
        target = upload.get('target_dir', summary['target_dir'])
        failures, existing, options = _placement(files, namespace, target)
        key = namespace.casefold()
        if key in names:
            previous, old_name = names[key]
            message = (f'同批次不能重复上传 {namespace}' if old_name == namespace else
                       f'同批次上传存在大小写冲突：{old_name} / {namespace}')
            failures.append(message)
            if previous != upload_id:
                item_errors.setdefault(previous, []).append(message)
        else:
            names[key] = upload_id, namespace
        if summary['binary_warnings'] and upload.get('confirm_binaries') is not True:
            failures.append('请确认允许安装含二进制文件或脚本的插件')
        final_dir = target
        if options:
            final_dir = upload.get('keep_dir')
            if final_dir not in options:
                failures.append('请选择最终保留目录；其他位置的同名 OPK 将被删除')
        if failures:
            item_errors.setdefault(upload_id, []).extend(failures)
            continue
        filename = namespace + '.opk'
        destination = f'{final_dir}/{filename}' if final_dir else filename
        matching = {entry['path'] for entry in existing}
        other = destination if destination in by_path else by_filename.get((final_dir, filename.casefold()))
        try:
            # 在不区分后缀大小写的文件系统上，显式识别同一个文件，而不是写入后将其再删除。
            actual = _stamp(_stat(host.root / 'plugin/app' / destination))
            if actual is not None and other not in matching:
                raise ValueError(f'目标文件已被其他插件、目录或链接占用：{other or destination}')
            same_file = other if other and actual == stamps[other] else destination
            pending_dedup = matching - {same_file}
            host.plugin_stage.source(item)
            _opk_path(host, same_file, stamps.get(same_file))
            for path in pending_dedup:
                _opk_path(host, path, stamps[path])
        except (OSError, ValueError) as error:
            item_errors[upload_id] = [str(error)]
            continue
        writes[same_file] = item
        plan['will_overwrite' if same_file in stamps else 'will_write'].append(same_file)
        plan['warnings'].extend(f'{summary["filename"]}：{warning}' for warning in summary['warnings'])
        plan['warnings'].extend(f'{summary["filename"]} 含敏感文件：{name}' for name in summary['binary_warnings'])
        for path in pending_dedup:
            dedup[path] = upload_id
    for path in removals:
        if not isinstance(path, str):
            errors.append('待删除项必须是相对于 plugin/app 的 .opk 文件路径')
            continue
        if path not in by_path:
            item_errors[path] = ['只允许删除真实存在的 .opk 文件，不能删除源码插件、目录或链接']
            continue
        try:
            _opk_path(host, path, stamps[path])
        except (OSError, ValueError) as error:
            item_errors[path] = [str(error)]
            continue
        if path not in writes and path not in dedup:
            deletes[path] = None
    plan['will_delete'] = list(deletes)
    plan['will_dedup_delete'] = sorted(dedup)
    for path in writes.keys() & dedup.keys():
        item_errors.setdefault(writes[path]['upload_id'], []).append(f'其他上传操作也会删除此文件：{path}')
    result['ok'] = not errors and not item_errors
    if not result['ok']:
        result.setdefault('error', errors[0] if errors else '待执行变更存在错误')
    return result, writes, deletes, dedup


def _commit(host, writes, deletes, dedup, files, stamps):
    applied = []
    installed = set()
    for relative, item in writes.items():
        upload_id = item['upload_id']
        namespace = item['summary']['namespace']
        entry = {'action': 'write', 'path': relative, 'ok': False, 'upload_id': upload_id}
        try:
            source = host.plugin_stage.source(item)
            destination = _opk_path(host, relative, stamps.get(relative))
            opkAPI.rebuild_opk_file(source, destination)
            host.log(2, f'WebUI 已安装 OPK [{namespace}]：{relative}')
            entry['ok'] = True
            installed.add(upload_id)
        except (OSError, ValueError) as error:
            entry['error'] = str(error)
        applied.append(entry)
    namespaces = {item['path']: item['namespace'] for item in files['opks']}
    for relative in sorted(set(dedup) | deletes.keys()):
        entry = {'action': 'delete', 'path': relative, 'ok': False}
        if relative in dedup and dedup[relative] not in installed:
            entry['error'] = '新 OPK 写入失败，已保留原副本'
        else:
            try:
                _opk_path(host, relative, stamps[relative]).unlink()
                host.log(2, f'WebUI 已删除 OPK [{namespaces[relative]}]：{relative}')
                entry['ok'] = True
            except (OSError, ValueError) as error:
                entry['error'] = str(error)
        applied.append(entry)
    if any(entry['ok'] for entry in applied):
        with host.lock:
            host.plugin_files_changed_at = time.time()
    for upload_id in installed:
        try:
            host.plugin_stage.discard(upload_id)
        except OSError as error:
            host.log(3, f'无法清理已提交的 OPK 暂存 [{upload_id}]：{error.strerror}')
            host.plugin_stage.items[upload_id]['deadline'] = 0  # 后续维护再次清理，不能再次提交。
    try:
        snapshot, _ = _scan(host)
    except OSError:
        return {'ok': False, 'error': '操作已执行，但无法读取最新目录快照，请刷新目录', 'applied': applied,
                'revision': None, 'reload_required': bool(host.plugin_files_changed_at)}
    return {'ok': all(item['ok'] for item in applied), 'applied': applied, 'revision': snapshot['revision'],
            'reload_required': snapshot['reload_required']}


def register_routes(host):
    app = host.app

    def check_auth_revision():
        with host.lock:
            if host.credentials is None or g.webui_auth_revision != host.credentials['revision']:
                abort(401)

    @app.get('/api/plugins/files')
    def plugin_files():
        with host.plugin_fs_lock:
            files, _ = _scan(host)
            files['staged'] = [_stage_summary(item, files) for item in host.plugin_stage.active().values()]
            return jsonify(files)

    @app.post(STAGE_URL)
    def stage():
        upload = request.files.get('file')
        if upload is None or not upload.filename or not upload.filename.lower().endswith('.opk'):
            return jsonify(error='仅支持 .opk 文件，不接受 .zip'), 400
        if not _safe_name(upload.filename):
            return jsonify(error='上传的 .opk 文件名无效，请先重命名'), 400
        source = request.form.get('source', 'manual')
        if source not in ('manual', 'market'):
            return jsonify(error='上传来源无效'), 400
        market_meta = None
        raw_market_meta = request.form.get('market_meta')
        if raw_market_meta is not None and raw_market_meta.strip():
            try:
                market_meta = json.loads(raw_market_meta)
            except (ValueError, RecursionError):
                return jsonify(error='market_meta 必须是合法的 JSON 对象'), 400
            if not isinstance(market_meta, dict):
                return jsonify(error='market_meta 必须是合法的 JSON 对象'), 400
        with host.plugin_fs_lock:
            check_auth_revision()
            host.plugin_stage.expire()
            return jsonify(_stage(host, upload, request.form.get('target_dir', ''), source, market_meta))

    @app.delete(STAGE_URL + '/<upload_id>')
    def discard_stage(upload_id):
        with host.plugin_fs_lock:
            check_auth_revision()
            if not host.plugin_stage.discard(upload_id):
                return jsonify(error='上传暂存不存在或已过期'), 404
            return jsonify(ok=True)

    @app.delete(STAGE_URL)
    def clear_stage():
        with host.plugin_fs_lock:
            check_auth_revision()
            host.plugin_stage.clear(strict=True)
            return jsonify(ok=True)

    @app.post('/api/plugins/batch/validate')
    @app.post('/api/plugins/batch/commit')
    def batch():
        body = request.get_json()
        with host.plugin_fs_lock:
            check_auth_revision()
            files, stamps = _scan(host)
            result, writes, deletes, dedup = _validate(host, body, files, stamps)
            if result.get('conflict'):
                return jsonify(result), 409
            if request.path == '/api/plugins/batch/validate':
                return jsonify(result)
            if not result['ok']:
                return jsonify(result), 400
            return jsonify(_commit(host, writes, deletes, dedup, files, stamps))
