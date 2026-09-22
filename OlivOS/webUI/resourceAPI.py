"""Plugin page declarations and disposable, versioned OPK resource caches."""

import os
import re
import shutil
import stat
import tempfile
import uuid
from pathlib import Path

CACHE_PATH = Path('plugin/cache/webui')
CODE_SUFFIXES = {'.py', '.pyc', '.pyo', '.pyd', '.pyw'}


def valid_namespace(value):
    return isinstance(value, str) and not value.startswith('.') and re.fullmatch(r'[\w.-]+', value) is not None


def relative_path(value, directory=False):
    if not isinstance(value, str) or not value or any(ord(char) < 32 for char in value):
        raise ValueError('WebUI path must be a relative path')
    if any(char in value for char in '\\:*?"<>|'):
        raise ValueError('WebUI paths must use / and contain no special path characters')
    name = value[:-1] if directory and value.endswith('/') else value
    parts = name.split('/')
    if any(not part or part.startswith('.') or part.endswith((' ', '.')) for part in parts):
        raise ValueError('WebUI paths must not contain empty, hidden or parent components')
    if any(part.lower() == 'app.json' or Path(part).suffix.lower() in CODE_SUFFIXES for part in parts):
        raise ValueError('Plugin metadata and Python code cannot be published as WebUI resources')
    return name


def is_link(path):
    info = path.lstat()
    # Name-surrogate reparse points include junctions, but not OneDrive placeholders.
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_reparse_tag', 0) & 0x20000000)


def safe_path(root, name):
    """Reject symlinks and Windows junctions, including those inside declared directories."""
    path = Path(root)
    if is_link(path):
        raise ValueError('WebUI root must not be a link')
    for part in name.split('/'):
        path = path / part
        if is_link(path):
            raise ValueError('WebUI resources must not be links')
    return path


def allows(name, resources):
    return any(name.startswith(item) if item.endswith('/') else name == item for item in resources)


def declaration(source, manifest):
    entries = manifest.get('webui_config') or []
    resources = []
    pages = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('title'), str):
            continue
        if entry.get('type') == 'link':
            pages.append(dict(entry))
        elif entry.get('type') == 'iframe':
            name = relative_path(entry.get('path'), directory=True)
            path = safe_path(source, name)
            if path.is_dir():
                name += '/index.html'
                path = safe_path(source, name)
            elif entry['path'].endswith('/'):
                raise ValueError(f'WebUI directory does not exist: {name}')
            if not path.is_file():
                raise ValueError(f'WebUI entry is not a file: {name}')
            # 根目录入口只公开自身；其他入口公开其所在目录，保留资源相对位置。
            resource = name.rsplit('/', 1)[0] + '/' if '/' in name else name
            if resource not in resources:
                resources.append(resource)
            pages.append(dict(entry, path=name))
    return resources, pages


def cache_directory(root):
    path = Path(root).resolve()
    for part in CACHE_PATH.parts:
        path = path / part
        if path.exists() or path.is_symlink():
            if is_link(path) or not path.is_dir():
                raise ValueError('WebUI cache ancestors must be real directories')
        else:
            path.mkdir()
    return path


def remove_tree(path):
    # Never traverse reparse points while clearing a host-owned cache tree.
    if is_link(path):
        if path.is_symlink() or not path.is_dir():
            path.unlink()
        else:
            path.rmdir()
    elif path.is_dir():
        for child in path.iterdir():
            remove_tree(child)
        path.rmdir()
    else:
        path.unlink()


def reset_cache(root):
    """Called once by the main boot process, before starting plugin/WebUI workers."""
    cache = cache_directory(root)
    for child in cache.iterdir():
        remove_tree(child)


def build_cache(root, source, namespace, resources):
    if not valid_namespace(namespace):
        raise ValueError('Invalid WebUI namespace')
    parent = cache_directory(root) / namespace
    parent.mkdir(exist_ok=True)
    if is_link(parent):
        raise ValueError('WebUI namespace cache must not be a link')
    staging = Path(tempfile.mkdtemp(prefix='.build-', dir=parent))
    try:
        source = Path(source)
        for item in resources:
            name = item.rstrip('/')
            path = safe_path(source, name)
            candidates = [path]
            while candidates:
                candidate = candidates.pop()
                relative = candidate.relative_to(source).as_posix()
                try:
                    relative_path(relative)
                    candidate = safe_path(source, relative)
                except ValueError:
                    continue
                if candidate.is_dir():
                    candidates.extend(candidate.iterdir())
                elif candidate.is_file():
                    target = staging / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(candidate, target)
        destination = parent / uuid.uuid4().hex
        os.replace(staging, destination)
        return str(destination)
    except Exception:
        remove_tree(staging)
        raise


def prune_cache(root, obsolete_roots):
    """Only retire previously mounted generations, never a concurrent new build."""
    cache = cache_directory(root)
    for old_root in obsolete_roots:
        path = Path(old_root).absolute()
        if path.parent.parent != cache or not valid_namespace(path.parent.name):
            continue
        if not re.fullmatch(r'[0-9a-f]{32}', path.name):
            continue
        if path.parent.exists() and is_link(path.parent):
            raise ValueError('WebUI namespace cache must not be a link')
        if path.exists() or path.is_symlink():
            remove_tree(path)
