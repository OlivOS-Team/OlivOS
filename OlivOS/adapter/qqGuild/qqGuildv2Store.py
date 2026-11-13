"""SQLite-backed QQ group cache with batched commits and legacy migration."""

import atexit
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import threading
import time


__all__ = [
    'open_db', 'close_db', 'upsert_group', 'touch_group', 'remove_group', 'get_group',
    'upsert_member', 'remove_member', 'get_members', 'list_seed_groups',
    'evict_members_by_age', 'evict_groups_by_age', 'import_legacy', 'get_meta', 'set_meta',
]

_DEFAULT_PATH = os.path.join('data', 'qqGuildv2', 'qqguildv2.sqlite3')
_LEGACY_PATH = os.path.join('data', 'qqGuildv2', 'group_members')
_DAY = 86400
_LOCK = threading.RLock()
_IMPORT_LOCK = threading.Lock()
_connection = None
_path = None
_default_path = False
_stop = None
_worker = None
_pending_groups = {}
_pending_members = {}
_deleted_group_members = set()
_pending_meta = {}
_import_changes = None
_log = logging.getLogger(__name__)

_GROUP_FIELDS = ('joined_at', 'member_role', 'allow_proactive_msg', 'recv_msg_setting',
                 'last_seen_at', 'state', 'members_state', 'updated_at', 'verified_at')
_MEMBER_FIELDS = ('username', 'member_role', 'bot', 'joined_at', 'union_openid',
                  'updated_at', 'source')


def _connect(path, default_path):
    global _connection, _path, _default_path, _stop, _worker
    if path != ':memory:':
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
    db = sqlite3.connect(path, timeout=5, check_same_thread=False)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA auto_vacuum=INCREMENTAL')
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA busy_timeout=5000')
        db.executescript('''
            CREATE TABLE IF NOT EXISTS groups(
                bot_hash TEXT NOT NULL, group_openid TEXT NOT NULL,
                joined_at TEXT, member_role TEXT, allow_proactive_msg INTEGER,
                recv_msg_setting TEXT, last_seen_at INTEGER NOT NULL,
                state TEXT NOT NULL, members_state TEXT NOT NULL,
                updated_at INTEGER NOT NULL, verified_at INTEGER,
                PRIMARY KEY(bot_hash, group_openid));
            CREATE INDEX IF NOT EXISTS idx_groups_seen ON groups(last_seen_at);
            CREATE TABLE IF NOT EXISTS members(
                bot_hash TEXT NOT NULL, group_openid TEXT NOT NULL,
                member_openid TEXT NOT NULL, username TEXT, member_role TEXT,
                bot INTEGER, joined_at TEXT, union_openid TEXT,
                updated_at INTEGER NOT NULL, source TEXT,
                PRIMARY KEY(bot_hash, group_openid, member_openid));
            CREATE INDEX IF NOT EXISTS idx_members_scan ON members(bot_hash, updated_at);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        ''')
    except Exception:
        db.close()
        raise
    _connection, _path, _default_path = db, path, default_path
    _stop = threading.Event()
    _worker = threading.Thread(target=_maintenance, args=(_stop,), daemon=True,
                               name='qqguildv2-store')
    _worker.start()


def open_db(path=None):
    """Open the shared store lazily; an explicit different path replaces it."""
    target = os.fspath(path) if path is not None else _DEFAULT_PATH
    if target != ':memory:':
        target = os.path.abspath(target)
    with _LOCK:
        if _connection is not None and target == _path:
            return _connection
        if _connection is not None:
            close_db()
        if _connection is None:
            _connect(target, path is None)
            # Run the initial sweep before any new events can be recorded.
            _evict_locked(int(time.time()), 1000)
            _commit_locked()
            if path is None:
                import_legacy(os.path.abspath(_LEGACY_PATH))
        return _connection


def close_db():
    """Persist pending writes and stop this instance's maintenance thread."""
    global _connection, _path, _default_path, _stop, _worker
    with _LOCK:
        if _connection is None:
            return
        _commit_locked()
        _stop.set()
        _connection.close()
        _connection = None
        _path = None
        _default_path = False
        _stop = None
        _worker = None


def _db():
    if _connection is None or (_default_path and _path != os.path.abspath(_DEFAULT_PATH)):
        return open_db()
    return _connection


def _commit_locked():
    if _connection is None or not (_pending_groups or _pending_members or
                                   _deleted_group_members or _pending_meta):
        return
    db = _connection
    try:
        for key in _deleted_group_members:
            db.execute('DELETE FROM members WHERE bot_hash=? AND group_openid=?', key)
        for key, row in _pending_groups.items():
            if row is None:
                db.execute('DELETE FROM groups WHERE bot_hash=? AND group_openid=?', key)
            else:
                columns = ('bot_hash', 'group_openid') + _GROUP_FIELDS
                db.execute('INSERT OR REPLACE INTO groups (%s) VALUES (%s)' % (
                    ','.join(columns), ','.join('?' for _ in columns)),
                    tuple(row.get(name) for name in columns))
        for key, row in _pending_members.items():
            if row is None:
                db.execute('DELETE FROM members WHERE bot_hash=? AND group_openid=? AND member_openid=?', key)
            else:
                columns = ('bot_hash', 'group_openid', 'member_openid') + _MEMBER_FIELDS
                db.execute('INSERT OR REPLACE INTO members (%s) VALUES (%s)' % (
                    ','.join(columns), ','.join('?' for _ in columns)),
                    tuple(row.get(name) for name in columns))
        for key, value in _pending_meta.items():
            db.execute('INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)', (key, value))
        db.commit()
    except Exception:
        db.rollback()
        raise
    _pending_groups.clear()
    _pending_members.clear()
    _deleted_group_members.clear()
    _pending_meta.clear()


def _maintenance(stop):
    next_sweep = time.monotonic() + 3600
    while not stop.wait(5):
        try:
            with _LOCK:
                if stop is not _stop or _connection is None:
                    return
                _commit_locked()
                if time.monotonic() >= next_sweep:
                    _evict_locked(int(time.time()), 1000)
                    _commit_locked()
                    next_sweep = time.monotonic() + 3600
        except sqlite3.Error:
            _log.exception('QQ group cache maintenance failed')


def _changed(kind, key):
    if _import_changes is not None:
        _import_changes.add((kind,) + key)


def _upsert(table, keys, fields, allowed, defaults):
    db = _db()
    key = tuple(keys.values())
    pending = _pending_groups if table == 'groups' else _pending_members
    if key in pending:
        old = pending[key]
    elif table == 'members' and key[:2] in _deleted_group_members:
        old = None
    else:
        where = ' AND '.join(name + '=?' for name in keys)
        old = db.execute('SELECT * FROM %s WHERE %s' % (table, where), key).fetchone()
    row = dict(old) if old is not None else dict(keys)
    row.update(defaults)
    row.update({name: value for name, value in fields.items()
                if name in allowed and value is not None and value != ''})
    pending[key] = row


def upsert_group(bot_hash, group_openid, **fields):
    now = int(time.time())
    key = (str(bot_hash), str(group_openid))
    with _LOCK:
        old = get_group(*key)
        defaults = {'last_seen_at': now, 'state': 'active', 'members_state': 'active', 'updated_at': now}
        if old:
            defaults = {'updated_at': now}
        _upsert('groups', dict(zip(('bot_hash', 'group_openid'), key)), fields, _GROUP_FIELDS, defaults)


def touch_group(bot_hash, group_openid, **fields):
    fields.setdefault('last_seen_at', int(time.time()))
    fields.setdefault('state', 'active')
    with _LOCK:
        old = get_group(bot_hash, group_openid)
        if old and old['members_state'] == 'evicted':
            fields.setdefault('members_state', 'active')
        upsert_group(bot_hash, group_openid, **fields)


def remove_group(bot_hash, group_openid):
    key = (str(bot_hash), str(group_openid))
    with _LOCK:
        _db()
        _pending_groups[key] = None
        _deleted_group_members.add(key)
        for member_key in list(_pending_members):
            if member_key[:2] == key:
                del _pending_members[member_key]
        _changed('removed_group', key)


def get_group(bot_hash, group_openid):
    with _LOCK:
        key = (str(bot_hash), str(group_openid))
        db = _db()
        if key in _pending_groups:
            row = _pending_groups[key]
        else:
            row = db.execute('SELECT * FROM groups WHERE bot_hash=? AND group_openid=?', key).fetchone()
        return dict(row) if row is not None else None


def upsert_member(bot_hash, group_openid, member_openid, **fields):
    key = (str(bot_hash), str(group_openid), str(member_openid))
    with _LOCK:
        _upsert('members', dict(zip(('bot_hash', 'group_openid', 'member_openid'), key)),
                fields, _MEMBER_FIELDS, {'updated_at': int(time.time())})


def remove_member(bot_hash, group_openid, member_openid):
    key = (str(bot_hash), str(group_openid), str(member_openid))
    with _LOCK:
        _db()
        _pending_members[key] = None
        _changed('removed_member', key)


def get_members(bot_hash, group_openid):
    with _LOCK:
        key = (str(bot_hash), str(group_openid))
        db = _db()
        rows = [] if key in _deleted_group_members else db.execute(
            'SELECT * FROM members WHERE bot_hash=? AND group_openid=?', key).fetchall()
        result = {row['member_openid']: dict(row) for row in rows}
        for member_key, row in _pending_members.items():
            if member_key[:2] == key:
                if row is None:
                    result.pop(member_key[2], None)
                else:
                    result[member_key[2]] = dict(row)
        cutoff = time.time() - 60 * _DAY
        for row in result.values():
            if row.get('bot') is not None:
                row['bot'] = bool(row['bot'])
            row['stale'] = row['updated_at'] < cutoff
        return result


def list_seed_groups(bot_hash, limit=3):
    with _LOCK:
        bot_hash = str(bot_hash)
        rows = _db().execute('SELECT * FROM groups WHERE bot_hash=?', (bot_hash,)).fetchall()
        groups = {row['group_openid']: dict(row) for row in rows}
        for key, row in _pending_groups.items():
            if key[0] == bot_hash:
                if row is None:
                    groups.pop(key[1], None)
                else:
                    groups[key[1]] = row
        active = [row for row in groups.values() if row['state'] != 'dormant']
        active.sort(key=lambda row: (-row['last_seen_at'], row['group_openid']))
        return [row['group_openid'] for row in active[:max(0, int(limit))]]


def _evict_locked(now, limit, members=True, groups=True):
    db = _db()
    _commit_locked()
    if groups and members:
        condition = "last_seen_at<? OR (last_seen_at<? AND (state!='dormant' OR members_state!='evicted'))"
        params = (now - 365 * _DAY, now - 120 * _DAY)
    elif groups:
        condition, params = 'last_seen_at<?', (now - 365 * _DAY,)
    else:
        condition = "last_seen_at<? AND (state!='dormant' OR members_state!='evicted')"
        params = (now - 120 * _DAY,)
    rows = db.execute('SELECT bot_hash,group_openid,last_seen_at FROM groups WHERE ' + condition +
                      ' ORDER BY last_seen_at LIMIT ?', params + (max(0, int(limit)),)).fetchall()
    for row in rows:
        key = (row['bot_hash'], row['group_openid'])
        db.execute('DELETE FROM members WHERE bot_hash=? AND group_openid=?', key)
        if groups and row['last_seen_at'] < now - 365 * _DAY:
            db.execute('DELETE FROM groups WHERE bot_hash=? AND group_openid=?', key)
        else:
            db.execute("UPDATE groups SET state='dormant',members_state='evicted' "
                       'WHERE bot_hash=? AND group_openid=?', key)
        _changed('removed_group', key)
    if rows:
        db.commit()
        db.execute('PRAGMA incremental_vacuum')
    return len(rows)


def evict_members_by_age(now=None, limit=1000):
    with _LOCK:
        return _evict_locked(int(time.time() if now is None else now), limit, groups=False)


def evict_groups_by_age(now=None, limit=1000):
    with _LOCK:
        return _evict_locked(int(time.time() if now is None else now), limit, members=False)


def get_meta(key):
    with _LOCK:
        key = str(key)
        db = _db()
        if key in _pending_meta:
            return _pending_meta[key]
        row = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        return row[0] if row else None


def set_meta(key, value):
    with _LOCK:
        _db()
        _pending_meta[str(key)] = str(value)


def import_legacy(dir_rel):
    """Import a legacy directory; directories above 5000 groups run in a daemon."""
    global _import_changes
    with _LOCK:
        _db()
        if get_meta('legacy_import_at') is not None or not os.path.isdir(dir_rel):
            return False
        try:
            names = os.listdir(dir_rel)
        except OSError:
            _log.exception('Cannot list legacy QQ group cache')
            return False
        if not _IMPORT_LOCK.acquire(blocking=False):
            return False
        _import_changes = set()
        if len([name for name in names if name.endswith('.json')]) > 5000:
            try:
                threading.Thread(target=_import_legacy, args=(os.fspath(dir_rel), _connection),
                                 daemon=True, name='qqguildv2-import').start()
            except Exception:
                _import_changes = None
                _IMPORT_LOCK.release()
                raise
            return True
        return _import_legacy(os.fspath(dir_rel), _connection)


def _import_legacy(directory, connection):
    global _import_changes
    # The caller reserves the import and starts tracking mutations before launching us.
    try:
        with _LOCK:
            if connection is not _connection or get_meta('legacy_import_at') is not None:
                return False
        try:
            names = os.listdir(directory)
            records = []
            signatures = {}
            for name in names:
                path = os.path.join(directory, name)
                stat = os.stat(path, follow_symlinks=False)
                if not os.path.isfile(path) or os.path.islink(path):
                    _log.warning('Legacy QQ group cache entry is not a regular file: %r', name)
                    return False
                signatures[name] = (stat.st_size, stat.st_mtime_ns, stat.st_ino)
                match = re.fullmatch(r'([0-9a-fA-F]{32})_(.+)\.json', name)
                if not match:
                    _log.warning('Skipping legacy QQ group cache with invalid filename: %r', name)
                    continue
                try:
                    with open(path, 'r', encoding='utf-8') as stream:
                        data = json.load(stream)
                    if not isinstance(data, dict) or not isinstance(data.get('members'), dict):
                        raise ValueError('invalid members')
                    timestamp = data.get('updated_at', 0)
                    if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
                        raise ValueError('invalid group timestamp')
                    timestamp = int(timestamp)
                    if not -(2 ** 63) <= timestamp < 2 ** 63:
                        raise ValueError('group timestamp out of range')
                    key = (match.group(1), match.group(2))
                    key[1].encode('utf-8')
                    members = []
                    for member_id, fields in data['members'].items():
                        if not member_id or not isinstance(fields, dict):
                            raise ValueError('invalid member')
                        item = {k: v for k, v in fields.items() if k in _MEMBER_FIELDS and v is not None and v != ''}
                        if any(not isinstance(v, (str, int, float, bool)) for v in item.values()):
                            raise ValueError('invalid member field')
                        if not isinstance(item.get('updated_at', timestamp), (int, float)):
                            raise ValueError('invalid member timestamp')
                        item.setdefault('updated_at', timestamp)
                        for value in (member_id, *item.values()):
                            if isinstance(value, str):
                                value.encode('utf-8')
                            elif isinstance(value, int) and not -(2 ** 63) <= value < 2 ** 63:
                                raise ValueError('member field out of range')
                            elif isinstance(value, float) and not math.isfinite(value):
                                raise ValueError('non-finite member field')
                        members.append((member_id, item))
                except (UnicodeError, ValueError, TypeError, OverflowError) as exc:
                    _log.warning('Skipping invalid legacy QQ group cache file %r: %s', name, exc)
                    continue
                records.append((key, timestamp, members))
            if not records:
                return False
            # Each batch commits independently; existing and live rows always win.
            batch = []
            for key, timestamp, members in records:
                batch.append(('group', key, timestamp, {}))
                batch.extend(('member', key + (member_id,), timestamp, fields)
                             for member_id, fields in members)
                while len(batch) >= 5000:
                    if not _import_batch(connection, batch[:5000]):
                        return False
                    del batch[:5000]
            if batch and not _import_batch(connection, batch):
                return False
            with _LOCK:
                if connection is not _connection:
                    return False
                _commit_locked()
                for key, _, members in records:
                    if ('removed_group',) + key in _import_changes:
                        continue
                    if not connection.execute('SELECT 1 FROM groups WHERE bot_hash=? AND group_openid=?',
                                              key).fetchone():
                        return False
                    for member_id, _ in members:
                        member_key = key + (member_id,)
                        if ('removed_member',) + member_key in _import_changes:
                            continue
                        if not connection.execute('SELECT 1 FROM members WHERE bot_hash=? AND group_openid=? '
                                                  'AND member_openid=?', member_key).fetchone():
                            return False
                if set(os.listdir(directory)) != set(names):
                    return False
                for name, signature in signatures.items():
                    stat = os.stat(os.path.join(directory, name), follow_symlinks=False)
                    if (stat.st_size, stat.st_mtime_ns, stat.st_ino) != signature:
                        return False
                # The metadata is committed only after the directory was removed successfully.
                shutil.rmtree(directory)
                set_meta('legacy_import_at', int(time.time()))
                _commit_locked()
                return True
        except (OSError, ValueError, TypeError, OverflowError, sqlite3.Error):
            _log.exception('Legacy QQ group cache import failed; retaining source')
            return False
    finally:
        with _LOCK:
            _import_changes = None
        _IMPORT_LOCK.release()


def _import_batch(connection, batch):
    with _LOCK:
        if connection is not _connection:
            return False
        _commit_locked()
        try:
            for kind, key, timestamp, fields in batch:
                if (('removed_group',) + key[:2] in _import_changes or
                        (kind == 'member' and ('removed_member',) + key in _import_changes)):
                    continue
                if kind == 'group':
                    columns = ('bot_hash', 'group_openid') + _GROUP_FIELDS
                    old = connection.execute(
                        'SELECT * FROM groups WHERE bot_hash=? AND group_openid=?', key
                    ).fetchone()
                    row = dict(old) if old else {
                        'bot_hash': key[0], 'group_openid': key[1],
                        'last_seen_at': timestamp, 'state': 'active',
                        'members_state': 'active', 'updated_at': timestamp
                    }
                    table = 'groups'
                else:
                    columns = ('bot_hash', 'group_openid', 'member_openid') + _MEMBER_FIELDS
                    old = connection.execute(
                        'SELECT * FROM members WHERE bot_hash=? AND group_openid=? AND member_openid=?', key
                    ).fetchone()
                    row = dict(old) if old else dict(zip(columns[:3], key))
                    for name, value in fields.items():
                        if name == 'updated_at':
                            row[name] = max(row.get(name, 0), value)
                        elif row.get(name) is None or row[name] == '':
                            row[name] = value
                    table = 'members'
                connection.execute(
                    'INSERT OR REPLACE INTO %s (%s) VALUES (%s)' % (
                        table, ','.join(columns), ','.join('?' for _ in columns)
                    ), tuple(row.get(name) for name in columns)
                )
            connection.commit()
            return True
        except Exception:
            connection.rollback()
            raise


atexit.register(close_db)
