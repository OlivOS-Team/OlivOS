# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/core/core/opkAPI.py
@Author    :   OlivOS-Team
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   OPK 校验、解包与规范化
'''

import json
import keyword
import lzma
import math
import os
import stat
import tempfile
import unicodedata
import zipfile
import zlib
from contextlib import contextmanager
from pathlib import Path

from OlivOS.core.info import infoAPI

MAX_ENTRIES = 5000
MAX_TOTAL_SIZE = 512 * 1024 * 1024
MAX_INNER_OPK_SIZE = 100 * 1024 * 1024
_RATIO_MIN_SIZE = 1024 * 1024
_MAX_RATIO = 200
_APPLE_DOUBLE_MAGIC = b'\x00\x05\x16\x07'
_BINARY_SUFFIXES = {'.exe', '.dll', '.so', '.dylib', '.pyd', '.bat', '.cmd', '.ps1',
                    '.vbs', '.jse', '.wsf', '.scr', '.com'}
_ZIP_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED, zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA}
_WINDOWS_DEVICES = {'CON', 'PRN', 'AUX', 'NUL', 'CONIN$', 'CONOUT$'} | {
    prefix + digit for prefix in ('COM', 'LPT') for digit in '123456789¹²³'
}


class OPKError(ValueError):
    def __init__(self, code, message, *, manifest=None, namespace=None, warnings=()):
        super().__init__(message)
        self.code = code
        self.manifest = manifest
        self.namespace = namespace
        self.nested = None
        self.warnings = list(warnings)
        self.binary_warnings = []


def _reject_json_constant(value):
    raise ValueError(f'invalid JSON number {value}')


def load_app_json_bytes(raw_bytes):
    if raw_bytes.startswith(b'\xef\xbb\xbf'):
        raise OPKError('utf8_bom', 'app.json contains UTF-8 BOM，请保存为无 BOM 的 UTF-8 编码')
    try:
        text = raw_bytes.decode('utf-8')
    except UnicodeDecodeError as error:
        raise OPKError('invalid_encoding', f'app.json is not valid UTF-8: {error}') from error
    try:
        manifest = json.loads(text, parse_constant=_reject_json_constant)
    except (ValueError, RecursionError) as error:
        raise OPKError('invalid_json', f'app.json JSON parse error: {error}') from error
    if not isinstance(manifest, dict):
        raise OPKError('invalid_manifest', 'app.json must contain a JSON object')
    return manifest


def load_app_json_file(path):
    try:
        raw_bytes = Path(path).read_bytes()
    except FileNotFoundError as error:
        raise OPKError('not_found', f'{path} not found') from error
    return load_app_json_bytes(raw_bytes)


def _windows_device(name):
    return name.split('.', 1)[0].rstrip(' ').upper() in _WINDOWS_DEVICES


def _is_number(value):
    return type(value) is int or (type(value) is float and math.isfinite(value))


def validate_manifest(manifest, fallback_stem):
    """校验启动所需字段，返回有效 namespace 及兼容性告警。"""
    if not isinstance(manifest, dict):
        raise OPKError('invalid_manifest', 'app.json must contain a JSON object')
    namespace = manifest.get('namespace', fallback_stem)
    if (not isinstance(namespace, str) or not namespace.isidentifier()
            or keyword.iskeyword(namespace) or _windows_device(namespace)):
        raise OPKError('invalid_manifest', f'app.json namespace must be a valid Python identifier: {namespace!r}',
                       manifest=manifest)
    name = manifest.get('name')
    if not isinstance(name, str) or not name.strip():
        message = 'app.json name must be a non-empty string'
    elif not _is_number(manifest.get('priority')):
        message = 'app.json priority must be a number'
    elif not isinstance(manifest.get('support'), list):
        message = 'app.json support must be a list'
    else:
        message = None
    if message:
        raise OPKError('invalid_manifest', message, manifest=manifest, namespace=namespace)

    compatible = manifest.get('compatible_svn', infoAPI.OlivOS_compatible_svn_default)
    if not _is_number(compatible):
        raise OPKError('invalid_manifest', 'app.json compatible_svn must be a number',
                       manifest=manifest, namespace=namespace)
    if compatible < infoAPI.OlivOS_SVN_OldCompatible:
        raise OPKError('incompatible', f'app.json compatible_svn {compatible} is no longer supported',
                       manifest=manifest, namespace=namespace)
    warnings = []
    if compatible < infoAPI.OlivOS_SVN_Compatible:
        warnings.append(f'app.json compatible_svn {compatible} targets an old OlivOS version')
    return namespace, warnings


def _member_path(info):
    # ZipInfo.filename 会截断 NUL；必须检查中央目录中的原始名称。
    name = info.orig_filename.replace('\\', '/')
    if (name.startswith('/') or any(char in ':*?"<>|' or unicodedata.category(char) == 'Cc' for char in name)):
        raise OPKError('unsafe_path', f'Unsafe OPK path: {info.orig_filename!r}')
    raw_parts = [part for part in name.split('/') if part]
    if any(part in ('.', '..') or part.endswith((' ', '.')) or _windows_device(part) for part in raw_parts):
        raise OPKError('unsafe_path', f'Unsafe OPK path: {info.orig_filename!r}')
    parts = tuple(raw_parts)
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise OPKError('unsafe_path', f'OPK must not contain a symbolic link: {info.orig_filename!r}')
    directory = name.endswith('/') or stat.S_ISDIR(mode) or bool(info.external_attr & 0x10)
    if directory and info.file_size:
        raise OPKError('invalid_archive', f'OPK directory entry contains data: {info.orig_filename!r}')
    if not parts and not directory:
        raise OPKError('unsafe_path', f'Unsafe empty OPK path: {info.orig_filename!r}')
    return parts, directory


def _excessive_ratio(info):
    return info.file_size >= _RATIO_MIN_SIZE and info.file_size > _MAX_RATIO * max(info.compress_size, 1)


def _is_mac_artifact(archive, parts, directory, info):
    if '__MACOSX' in parts or '.DS_Store' in parts:
        return True
    if directory:
        return False
    if parts[-1].startswith('._'):
        with archive.open(info) as file:
            return file.read(len(_APPLE_DOUBLE_MAGIC)) == _APPLE_DOUBLE_MAGIC
    return False


def _check_path_conflicts(members):
    # 隐式父目录也参与大小写冲突检查；同一路径不能同时为文件和目录。
    root = {}
    explicit = set()
    for parts, directory, _ in members:
        if parts in explicit:
            raise OPKError('path_conflict', f'Duplicate OPK path: {"/".join(parts)}')
        explicit.add(parts)
        current = root
        for index, part in enumerate(parts):
            folded = part.casefold()
            needs_directory = directory or index < len(parts) - 1
            if folded not in current:
                current[folded] = (part, {} if needs_directory else None)
            spelling, children = current[folded]
            if spelling != part or (children is not None) != needs_directory:
                raise OPKError('path_conflict', f'Conflicting OPK path: {"/".join(parts)}')
            current = children


def _scan_members(archive):
    all_entries = archive.infolist()
    if len(all_entries) > MAX_ENTRIES:
        raise OPKError('archive_limit', f'OPK has more than {MAX_ENTRIES} ZIP entries')
    if sum(info.file_size for info in all_entries) > MAX_TOTAL_SIZE:
        raise OPKError('archive_limit', f'OPK expands beyond {MAX_TOTAL_SIZE} bytes')
    members = []
    for info in all_entries:
        parts, directory = _member_path(info)
        if _excessive_ratio(info):
            raise OPKError('archive_limit', f'OPK compression ratio exceeds {_MAX_RATIO}: {info.orig_filename!r}')
        # 加密、patched data、strong encryption 和掩码本地头不是 OPK 支持的 ZIP 特性。
        if info.compress_type not in _ZIP_COMPRESSION or info.flag_bits & 0x2061:
            raise OPKError('invalid_archive', f'Unsupported OPK ZIP member: {info.orig_filename!r}')
        if info.compress_type == zipfile.ZIP_STORED and info.file_size != info.compress_size:
            raise OPKError('invalid_archive', f'Wrong stored OPK member size: {info.orig_filename!r}')
        if parts:
            members.append((parts, directory, info))
    # 即使最终被忽略的 macOS 条目也必须先经过完整的静态安全扫描。
    members = [entry for entry in members if not _is_mac_artifact(archive, *entry)]
    _check_path_conflicts(members)
    return members


def _root_file(members, name):
    return next((info for parts, directory, info in members if not directory and parts == (name,)), None)


def _has_member_file(members, target_parts):
    return any(not directory and parts == target_parts for parts, directory, _ in members)


def _copy_bounded(source, target, expected_size, max_size, label):
    # 防止恶意 ZIP 伪造中央目录 file_size，解压流超出上限时立刻中止。
    limit = min(expected_size, max_size)
    written = 0
    while True:
        chunk = source.read(64 * 1024)
        if not chunk:
            break
        written += len(chunk)
        if written > limit:
            code = 'archive_limit' if written > max_size else 'invalid_archive'
            raise OPKError(code, f'Expanded OPK member exceeds declared size: {label}')
        if target is not None:
            target.write(chunk)
    if written != expected_size:
        raise OPKError('invalid_archive', f'Wrong expanded OPK size: {label}')
    return written


def _open_layout(members):
    if _root_file(members, 'app.json') is not None:
        return None, members
    if members and all(parts[0] == members[0][0][0] and (directory or len(parts) > 1)
                       for parts, directory, _ in members):
        return 'directory', [(parts[1:], directory, info) for parts, directory, info in members if len(parts) > 1]
    if len(members) == 1:
        parts, directory, info = members[0]
        if not directory and len(parts) == 1 and Path(parts[0]).suffix.lower() == '.opk':
            if info.file_size > MAX_INNER_OPK_SIZE:
                raise OPKError('archive_limit', f'Inner OPK exceeds {MAX_INNER_OPK_SIZE} bytes')
            return 'opk', info
    raise OPKError('not_found', 'app.json not found at the OPK root or inside a single wrapper directory or .opk')


def _inspect_members(archive, members, stem, nested, require_exact_filename):
    binary_warnings = ['/'.join(parts) for parts, directory, _ in members
                       if not directory and Path(parts[-1]).suffix.lower() in _BINARY_SUFFIXES]
    try:
        app_info = _root_file(members, 'app.json')
        if app_info is None:
            raise OPKError('not_found', 'app.json not found at the root after unwrapping one OPK layer')
        manifest = load_app_json_bytes(archive.read(app_info))
        namespace, warnings = validate_manifest(manifest, stem)
        if _root_file(members, 'main.py') is None and not _has_member_file(members, ('main', '__init__.py')):
            raise OPKError('missing_entry', 'main.py not found at the OPK root',
                           manifest=manifest, namespace=namespace, warnings=warnings)
        if _root_file(members, '__init__.py') is None:
            warnings.append('__init__.py not found at the OPK root')
        if require_exact_filename and stem != namespace:
            raise OPKError('filename_mismatch', f'OPK filename must match namespace exactly; rename to {namespace}.opk',
                           manifest=manifest, namespace=namespace, warnings=warnings)
    except OPKError as error:
        error.nested = nested
        error.binary_warnings = binary_warnings
        raise
    return {'manifest': manifest, 'namespace': namespace, 'nested': nested,
            'binary_warnings': binary_warnings, 'warnings': warnings}


def _verify_members(archive, members):
    # 预上传在允许提交前读取所有保留条目，检查本地头、解压流、真实体积和 CRC。
    total = 0
    for parts, directory, info in members:
        if directory:
            continue
        label = '/'.join(parts)
        with archive.open(info) as stream:
            total += _copy_bounded(stream, None, info.file_size, MAX_TOTAL_SIZE - total, label)


@contextmanager
def _open_opk(path, require_exact_filename=False, filename=None):
    opk_path = Path(path)
    opk_name = opk_path if filename is None else Path(filename)
    if opk_path.suffix.lower() != '.opk' or opk_name.suffix.lower() != '.opk':
        raise OPKError('invalid_format', 'Only .opk files are supported')
    try:
        with zipfile.ZipFile(path) as outer:
            outer_members = _scan_members(outer)
            nested, members = _open_layout(outer_members)
            if nested == 'opk':
                with tempfile.TemporaryFile() as inner_file:
                    with outer.open(members) as source:
                        _copy_bounded(source, inner_file, members.file_size, MAX_INNER_OPK_SIZE, members.orig_filename)
                    inner_file.seek(0)
                    with zipfile.ZipFile(inner_file) as inner:
                        members = _scan_members(inner)
                        result = _inspect_members(inner, members, opk_name.stem, nested, require_exact_filename)
                        if require_exact_filename:
                            _verify_members(inner, members)
                        yield inner, members, result
            else:
                result = _inspect_members(outer, members, opk_name.stem, nested, require_exact_filename)
                if require_exact_filename:
                    _verify_members(outer, outer_members)
                yield outer, members, result
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, UnicodeError, zlib.error,
            lzma.LZMAError) as error:
        raise OPKError('invalid_archive', f'Invalid OPK ZIP: {error}') from error


def inspect_opk(path, require_exact_filename=False, *, filename=None):
    """检查 OPK 目录和清单；严格上传模式还验证文件名及成员内容的完整性。"""
    with _open_opk(path, require_exact_filename, filename) as (_, _, result):
        return result


def extract_opk(path, dest):
    """解包至不存在或空的独立目录；绝不覆盖已有文件。"""
    root = Path(dest)
    with _open_opk(path) as (archive, members, result):
        root.mkdir(parents=True, exist_ok=True)
        info = root.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_reparse_tag', 0) & 0x20000000 or any(root.iterdir()):
            raise OPKError('unsafe_destination', f'OPK destination must be an empty real directory: {root}')
        total = 0
        for parts, directory, info in members:
            target = root.joinpath(*parts)
            if directory:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open('xb') as output:
                    total += _copy_bounded(source, output, info.file_size, MAX_TOTAL_SIZE - total, '/'.join(parts))
        return result


def _write_flat(output, archive, members, store=()):
    too_compressed = set()
    total = 0
    with zipfile.ZipFile(output, 'w') as rebuilt:
        for parts, directory, info in members:
            name = '/'.join(parts) + ('/' if directory else '')
            member = zipfile.ZipInfo(name, date_time=info.date_time)
            member.external_attr = info.external_attr
            if directory:
                rebuilt.writestr(member, b'')
                continue
            member.file_size = info.file_size
            if info.compress_type != zipfile.ZIP_STORED and name not in store:
                member.compress_type = zipfile.ZIP_DEFLATED
            with archive.open(info) as source, rebuilt.open(member, 'w') as target:
                total += _copy_bounded(source, target, info.file_size, MAX_TOTAL_SIZE - total, name)
            if _excessive_ratio(member):
                too_compressed.add(name)
    return too_compressed


def rebuild_opk_file(src, dst):
    """写出剥离套娃及 macOS 产物的 OPK，关闭 ZIP 后在目标目录原子替换。"""
    destination = Path(dst)
    if destination.suffix.lower() != '.opk':
        raise OPKError('invalid_format', 'Only .opk files are supported')
    temporary = None
    try:
        with _open_opk(src) as (archive, members, result):
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.opk-', delete=False) as output:
                temporary = output.name
                store = _write_flat(output, archive, members)
                if store:
                    # ZIP 重新压缩可能越过扫描阈值；这些成员改为不压缩。
                    output.seek(0)
                    output.truncate()
                    _write_flat(output, archive, members, store)
        os.replace(temporary, destination)
        temporary = None
        return result
    finally:
        if temporary is not None:
            os.unlink(temporary)
