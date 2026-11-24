"""Helpers for collecting WebUI JavaScript coverage from Chrome DevTools Protocol."""

import gzip
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit


COVERAGE_FLAG = 'OLIVOS_WEBUI_COVERAGE'
COVERAGE_DIR_ENV = 'OLIVOS_WEBUI_COVERAGE_DIR'
COVERAGE_SCHEMA = 1
COVERED_SCRIPT_NAMES = frozenset(('app.js', 'theme.js'))


def repo_root():
    return Path(__file__).resolve().parents[1]


def coverage_enabled():
    return os.environ.get(COVERAGE_FLAG) == '1'


def coverage_directory():
    root = repo_root()
    configured = os.environ.get(COVERAGE_DIR_ENV)
    path = Path(configured) if configured else Path('test-results/frontend-coverage')
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _script_name(url):
    if not isinstance(url, str):
        return None
    try:
        path = urlsplit(url).path
    except ValueError:
        return None
    if not path.startswith('/static/'):
        return None
    name = path.rsplit('/', 1)[-1]
    return name if name in COVERED_SCRIPT_NAMES else None


def filter_coverage_scripts(result):
    """Keep only WebUI scripts while retaining a count of ignored CDP entries."""
    scripts = []
    ignored = 0
    for item in result or []:
        if not isinstance(item, dict):
            ignored += 1
            continue
        name = _script_name(item.get('url'))
        if name is None:
            ignored += 1
            continue
        scripts.append({
            'name': name,
            'url': item.get('url', ''),
            'scriptId': item.get('scriptId'),
            'functions': item.get('functions', []),
        })
    return scripts, ignored


@lru_cache(maxsize=1)
def git_head():
    try:
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'], cwd=repo_root(), capture_output=True,
            check=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def write_coverage_payload(directory, *, nodeid, outcome, scripts, ignored_script_count=0,
                           error=None, collected_at=None):
    """Write one compressed raw V8 payload for later Istanbul conversion."""
    directory = Path(directory)
    raw_directory = directory / 'raw'
    raw_directory.mkdir(parents=True, exist_ok=True)
    collected_at = collected_at or datetime.now(timezone.utc).isoformat()
    payload = {
        'schema': COVERAGE_SCHEMA,
        'nodeid': nodeid,
        'outcome': outcome,
        'collected_at': collected_at,
        'git_head': git_head(),
        'ignored_script_count': ignored_script_count,
        'error': error,
        'scripts': scripts,
    }
    encoded = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    unique = f'{nodeid}\0{outcome}\0{collected_at}\0{time.time_ns()}'.encode('utf-8')
    digest = hashlib.sha256(unique).hexdigest()[:20]
    path = raw_directory / f'{digest}.json.gz'
    path.write_bytes(gzip.compress(encoded, compresslevel=6))
    return path
