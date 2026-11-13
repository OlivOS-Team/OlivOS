import importlib.util
import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest


_STORE_PATH = (Path(__file__).resolve().parents[1] / 'OlivOS' / 'adapter' /
               'qqGuild' / 'qqGuildv2Store.py')
_BOT = 'a' * 32


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location('qqguildv2_store_test', _STORE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.open_db(tmp_path / 'cache.sqlite3')
    yield module
    module.close_db()


def _legacy(path, group, members, updated=None):
    path.mkdir(exist_ok=True)
    (path / ('%s_%s.json' % (_BOT, group))).write_text(
        json.dumps({'updated_at': int(time.time()) if updated is None else updated,
                    'members': members}), encoding='utf-8')


def test_migration_merges_existing_and_is_idempotent(store, tmp_path):
    directory = tmp_path / 'old'
    _legacy(directory, 'group_1', {'u': {'username': 'old', 'member_role': 'admin', 'updated_at': 10},
                                   'v': {'username': 'second', 'updated_at': 11}})
    store.upsert_group(_BOT, 'group_1', member_role='owner')
    store.upsert_member(_BOT, 'group_1', 'u', username='new', updated_at=20)
    assert store.import_legacy(directory) is True
    assert not directory.exists()
    assert store.get_meta('legacy_import_at') is not None
    members = store.get_members(_BOT, 'group_1')
    assert set(members) == {'u', 'v'}
    assert members['u']['username'] == 'new'
    assert members['u']['member_role'] == 'admin'
    assert members['u']['updated_at'] == 20
    assert store.get_group(_BOT, 'group_1')['member_role'] == 'owner'
    _legacy(directory, 'group_1', {'w': {'username': 'later'}})
    assert store.import_legacy(directory) is False
    assert directory.exists()
    assert set(store.get_members(_BOT, 'group_1')) == {'u', 'v'}


@pytest.mark.parametrize('name,content', [
    ('probe-group_xxx.json', b'{"members": {}}'),
    ('%s_bad.json' % _BOT, b'{'),
    ('%s_bad.json' % _BOT, b'\xff'),
    ('%s_bad.json' % _BOT, b'{"members": []}'),
    ('%s_bad.json' % _BOT, b'{"updated_at": "invalid", "members": {}}'),
    ('%s_bad.json' % _BOT, b'{"updated_at": NaN, "members": {}}'),
    ('%s_bad.json' % _BOT, b'{"members": {"good": {}, "bad": null}}'),
    ('%s_bad.json' % _BOT, b'{"members": {"good": {}, "bad": {"username": []}}}'),
    ('%s_bad.json' % _BOT, b'{"members": {"bad": {"updated_at": "invalid"}}}'),
    ('%s_bad.json' % _BOT, b'{"members": {"bad": {"updated_at": NaN}}}'),
    ('%s_bad.json' % _BOT, b'{"members": {"bad": {"username": 9223372036854775808}}}'),
    ('%s_bad.json' % _BOT, b'{"members": {"bad": {"username": "\\ud800"}}}'),
])
def test_migration_skips_invalid_files(store, tmp_path, caplog, name, content):
    directory = tmp_path / 'old'
    _legacy(directory, 'valid', {'u': {'username': 'known'}})
    (directory / name).write_bytes(content)

    assert store.import_legacy(directory) is True
    assert not directory.exists()
    assert store.get_meta('legacy_import_at') is not None
    assert store._db().execute('SELECT count(*) FROM groups').fetchone()[0] == 1
    assert set(store.get_members(_BOT, 'valid')) == {'u'}
    assert store._db().execute('SELECT count(*) FROM members').fetchone()[0] == 1
    assert any(record.levelname == 'WARNING' and name in record.message for record in caplog.records)


@pytest.mark.parametrize('invalid_files', [
    {},
    {'probe-group_xxx.json': b'{"members": {}}',
     '%s_broken.json' % _BOT: b'{',
     '%s_invalid.json' % _BOT: b'{"members": {"u": null}}'},
])
def test_migration_retains_directory_when_no_files_are_valid(store, tmp_path, caplog, invalid_files):
    directory = tmp_path / 'old'
    directory.mkdir()
    for name, content in invalid_files.items():
        (directory / name).write_bytes(content)

    assert store.import_legacy(directory) is False
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == invalid_files
    assert store.get_meta('legacy_import_at') is None
    assert store._db().execute('SELECT count(*) FROM groups').fetchone()[0] == 0
    assert store._db().execute('SELECT count(*) FROM members').fetchone()[0] == 0
    for name in invalid_files:
        assert any(record.levelname == 'WARNING' and name in record.message for record in caplog.records)


def test_two_tier_eviction_and_stale_reads(store):
    now = int(time.time())
    day = 86400
    for group, age in [('recent', 1), ('dormant', 121), ('deleted', 366)]:
        store.upsert_group(_BOT, group, last_seen_at=now - age * day)
        store.upsert_member(_BOT, group, 'u', updated_at=now - 61 * day)
    assert store.get_members(_BOT, 'recent')['u']['stale'] is True
    store.upsert_member(_BOT, 'recent', 'fresh', updated_at=now)
    assert store.get_members(_BOT, 'recent')['fresh']['stale'] is False
    assert store.evict_members_by_age(now=now) == 2
    assert store.get_group(_BOT, 'dormant')['state'] == 'dormant'
    assert store.get_group(_BOT, 'dormant')['members_state'] == 'evicted'
    assert store.get_members(_BOT, 'dormant') == {}
    assert store.evict_groups_by_age(now=now) == 1
    assert store.get_group(_BOT, 'deleted') is None
    assert store.get_group(_BOT, 'recent')['state'] == 'active'
    store.upsert_group(_BOT, 'dormant', member_role='admin')
    store.touch_group(_BOT, 'dormant')
    revived = store.get_group(_BOT, 'dormant')
    assert revived['state'] == 'active'
    assert revived['members_state'] == 'active'
    assert revived['member_role'] == 'admin'
    assert set(store.get_members(_BOT, 'recent')) == {'u', 'fresh'}


def test_import_preserves_removal_during_batch(store, tmp_path, monkeypatch):
    directory = tmp_path / 'old'
    _legacy(directory, 'group', {'u': {'username': 'old'}, 'v': {'username': 'keep'}})
    original = store._import_batch

    def remove_then_import(connection, batch):
        store.remove_member(_BOT, 'group', 'u')
        store.touch_group(_BOT, 'group')
        return original(connection, batch)

    monkeypatch.setattr(store, '_import_batch', remove_then_import)
    assert store.import_legacy(directory) is True
    assert set(store.get_members(_BOT, 'group')) == {'v'}


def test_migration_batches_rows_without_losing_members(store, tmp_path, monkeypatch):
    directory = tmp_path / 'old'
    _legacy(directory, 'large', {str(i): {'username': str(i)} for i in range(5001)})
    original = store._import_batch
    sizes = []

    def capture(connection, batch):
        sizes.append(len(batch))
        return original(connection, batch)

    monkeypatch.setattr(store, '_import_batch', capture)
    assert store.import_legacy(directory) is True
    assert sizes == [5000, 2]
    assert len(store.get_members(_BOT, 'large')) == 5001


def test_eviction_respects_round_limit(store):
    now = int(time.time())
    for group in ('a', 'b', 'c'):
        store.upsert_group(_BOT, group, last_seen_at=now - 400 * 86400)
        store.upsert_member(_BOT, group, 'member')
    assert store.evict_groups_by_age(now=now, limit=2) == 2
    assert sum(store.get_group(_BOT, group) is not None for group in ('a', 'b', 'c')) == 1
    assert store.evict_groups_by_age(now=now, limit=2) == 1


def test_background_import_tracks_mutations_before_worker_starts(store, tmp_path, monkeypatch):
    directory = tmp_path / 'old'
    _legacy(directory, 'group', {'u': {'username': 'old'}, 'v': {'username': 'keep'}})
    original_listdir = store.os.listdir
    original_import = store._import_legacy
    started = threading.Event()
    proceed = threading.Event()
    finished = threading.Event()
    calls = []

    def listdir(path):
        if not calls:
            calls.append(True)
            return ['%s_%d.json' % (_BOT, i) for i in range(5001)]
        return original_listdir(path)

    def delayed_import(path, connection):
        started.set()
        try:
            if proceed.wait(5):
                original_import(path, connection)
        finally:
            finished.set()

    monkeypatch.setattr(store.os, 'listdir', listdir)
    monkeypatch.setattr(store, '_import_legacy', delayed_import)
    assert store.import_legacy(directory) is True
    assert started.wait(5)
    try:
        store.remove_member(_BOT, 'group', 'u')
        store.touch_group(_BOT, 'group')
    finally:
        proceed.set()
        assert finished.wait(5)
    assert not directory.exists()
    assert set(store.get_members(_BOT, 'group')) == {'v'}


def test_writes_are_immediately_visible_and_close_persists(store, tmp_path):
    store.touch_group(_BOT, 'group', member_role='admin')
    store.upsert_member(_BOT, 'group', 'u', username='known', bot=False)
    store.upsert_member(_BOT, 'group', 'u', username='', member_role='owner')
    member = store.get_members(_BOT, 'group')['u']
    assert member['username'] == 'known'
    assert member['member_role'] == 'owner'
    assert member['bot'] == 0
    store.close_db()
    store.open_db(tmp_path / 'cache.sqlite3')
    assert store.get_group(_BOT, 'group')['member_role'] == 'admin'
    assert store.get_members(_BOT, 'group')['u']['username'] == 'known'


def test_pending_writes_do_not_hold_sqlite_writer_lock(store, tmp_path):
    store.touch_group(_BOT, 'group')
    store.upsert_member(_BOT, 'group', 'u', username='pending')
    store.set_meta('pending', 'value')
    assert store.get_meta('pending') == 'value'
    assert store.get_members(_BOT, 'group')['u']['username'] == 'pending'
    other = sqlite3.connect(tmp_path / 'cache.sqlite3', timeout=0.1)
    try:
        assert other.execute('SELECT COUNT(*) FROM members').fetchone()[0] == 0
        other.execute("INSERT INTO meta(key,value) VALUES('external','ok')")
        other.commit()
    finally:
        other.close()
    store.close_db()
    other = sqlite3.connect(tmp_path / 'cache.sqlite3')
    try:
        assert other.execute('SELECT username FROM members').fetchone()[0] == 'pending'
        assert dict(other.execute('SELECT key,value FROM meta')) == {
            'external': 'ok', 'pending': 'value'
        }
    finally:
        other.close()


def test_pending_delete_then_recreate_hides_old_members(store):
    store.touch_group(_BOT, 'group')
    store.upsert_member(_BOT, 'group', 'old')
    store._commit_locked()
    store.remove_group(_BOT, 'group')
    store.touch_group(_BOT, 'group')
    store.upsert_member(_BOT, 'group', 'new')
    assert set(store.get_members(_BOT, 'group')) == {'new'}
    assert store.list_seed_groups(_BOT) == ['group']
    store._commit_locked()
    assert set(store.get_members(_BOT, 'group')) == {'new'}


def test_flush_failure_keeps_dirty_records_for_retry(store):
    db = store.open_db()
    db.execute("CREATE TRIGGER fail_member BEFORE INSERT ON members BEGIN "
               "SELECT RAISE(ABORT, 'failure'); END")
    db.commit()
    store.touch_group(_BOT, 'group')
    store.upsert_member(_BOT, 'group', 'u', username='retained')
    with pytest.raises(sqlite3.IntegrityError):
        store._commit_locked()
    assert store.get_members(_BOT, 'group')['u']['username'] == 'retained'
    assert db.execute('SELECT COUNT(*) FROM groups').fetchone()[0] == 0
    db.execute('DROP TRIGGER fail_member')
    db.commit()
    store._commit_locked()
    assert db.execute('SELECT username FROM members').fetchone()[0] == 'retained'
