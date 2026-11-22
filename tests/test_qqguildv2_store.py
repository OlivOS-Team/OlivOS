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


def test_list_seed_groups_skips_suspect_groups(store):
    now = int(time.time())
    store.upsert_group(_BOT, 'active_g', state='active', last_seen_at=now - 10)
    store.upsert_group(_BOT, 'suspect_g', state='suspect', last_seen_at=now)
    store.upsert_group(_BOT, 'dormant_g', state='dormant', last_seen_at=now + 10)
    assert store.list_seed_groups(_BOT, limit=10) == ['active_g']


def test_touch_group_restores_suspect_to_active(store):
    store.touch_group(_BOT, 'g1')
    store.upsert_group(_BOT, 'g1', state='suspect')
    assert store.get_group(_BOT, 'g1')['state'] == 'suspect'
    store.touch_group(_BOT, 'g1')
    assert store.get_group(_BOT, 'g1')['state'] == 'active'


def test_evict_suspect_groups_after_30_days(store):
    now = int(time.time())
    day = 86400
    store.upsert_group(_BOT, 'old_suspect', state='suspect', last_seen_at=now - 31 * day)
    store.upsert_member(_BOT, 'old_suspect', 'u1', username='old')
    store.upsert_group(_BOT, 'recent_suspect', state='suspect', last_seen_at=now - 10 * day)
    store.upsert_member(_BOT, 'recent_suspect', 'u2', username='recent')
    store.upsert_group(_BOT, 'old_active', state='active', last_seen_at=now - 40 * day)
    store.upsert_member(_BOT, 'old_active', 'u3', username='active')

    assert store.evict_suspect_groups(now=now) == 1
    evicted = store.get_group(_BOT, 'old_suspect')
    assert evicted['state'] == 'dormant'
    assert evicted['members_state'] == 'evicted'
    assert store.get_members(_BOT, 'old_suspect') == {}
    assert store.get_group(_BOT, 'recent_suspect')['state'] == 'suspect'
    assert set(store.get_members(_BOT, 'recent_suspect')) == {'u2'}
    assert store.get_group(_BOT, 'old_active')['state'] == 'active'
    assert set(store.get_members(_BOT, 'old_active')) == {'u3'}


def test_list_groups_for_calibration_filters_and_orders(store):
    now = int(time.time())
    day = 86400
    other_bot = 'b' * 32
    # 1. 未 complete 且从未校准（最高优先，按 last_seen_at 降序）
    store.upsert_group(_BOT, 'g_incomp_new', state='active', members_state='active',
                       verified_at=None, last_seen_at=now - 1 * day)
    store.upsert_group(_BOT, 'g_incomp_old', state='active', members_state='warming',
                       verified_at=None, last_seen_at=now - 5 * day)
    # 2. 未 complete 但有旧 verified_at（仍排在 complete 之前）
    store.upsert_group(_BOT, 'g_incomp_verified', state='active', members_state='active',
                       verified_at=now - 2 * day, last_seen_at=now - 2 * day)
    # 3. complete 但已超过 7 天未校准（按 verified_at 升序）
    store.upsert_group(_BOT, 'g_stale_older', state='active', members_state='complete',
                       verified_at=now - 10 * day, last_seen_at=now - 3 * day)
    store.upsert_group(_BOT, 'g_stale_newer', state='active', members_state='complete',
                       verified_at=now - 8 * day, last_seen_at=now - 1 * day)
    # 应被排除的群：已 complete 且 7 天内校准 / 超过 14 天不活跃 / suspect / dormant / 其它 bot
    store.upsert_group(_BOT, 'g_fresh_complete', state='active', members_state='complete',
                       verified_at=now - 2 * day, last_seen_at=now - 1 * day)
    store.upsert_group(_BOT, 'g_inactive_15d', state='active', members_state='active',
                       verified_at=None, last_seen_at=now - 15 * day)
    store.upsert_group(_BOT, 'g_suspect', state='suspect', members_state='active',
                       verified_at=None, last_seen_at=now - 1 * day)
    store.upsert_group(_BOT, 'g_dormant', state='dormant', members_state='evicted',
                       verified_at=None, last_seen_at=now - 1 * day)
    store.upsert_group(other_bot, 'g_other_bot', state='active', members_state='active',
                       verified_at=None, last_seen_at=now - 1 * day)

    result = store.list_groups_for_calibration(_BOT, now - 14 * day, now - 7 * day, 50)
    assert result == [
        'g_incomp_new',
        'g_incomp_old',
        'g_incomp_verified',
        'g_stale_older',
        'g_stale_newer',
    ]
    assert store.list_groups_for_calibration(_BOT, now - 14 * day, now - 7 * day, 2) == [
        'g_incomp_new',
        'g_incomp_old',
    ]
    assert store.list_groups_for_calibration(other_bot, now - 14 * day, now - 7 * day, 50) == [
        'g_other_bot'
    ]


def test_reconcile_group_members_removes_departed_and_guards_new_and_empty(store):
    sync_started_at = 10000
    store.touch_group(_BOT, 'g_rec')
    store.upsert_member(_BOT, 'g_rec', 'm_keep', username='留存', updated_at=sync_started_at - 100)
    store.upsert_member(_BOT, 'g_rec', 'm_gone', username='离群', updated_at=sync_started_at - 50)
    store.upsert_member(_BOT, 'g_rec', 'm_new_eq', username='并发新成员1', updated_at=sync_started_at)
    store.upsert_member(_BOT, 'g_rec', 'm_new_gt', username='并发新成员2', updated_at=sync_started_at + 5)

    # 空 keep 集合绝不删除任何成员（防上游异常清空整群）。
    assert store.reconcile_group_members(_BOT, 'g_rec', set(), sync_started_at) == 0
    assert set(store.get_members(_BOT, 'g_rec')) == {'m_keep', 'm_gone', 'm_new_eq', 'm_new_gt'}

    # 正常差集：仅删除未出现且早于 sync_started_at 的 m_gone。
    deleted = store.reconcile_group_members(_BOT, 'g_rec', {'m_keep'}, sync_started_at)
    assert deleted == 1
    assert set(store.get_members(_BOT, 'g_rec')) == {'m_keep', 'm_new_eq', 'm_new_gt'}

    # 超过 500 个成员分批处理：不误删保留成员，正确清除离群者。
    store.touch_group(_BOT, 'g_big')
    keep_big = set()
    for idx in range(600):
        mid = 'keep_%d' % idx
        keep_big.add(mid)
        store.upsert_member(_BOT, 'g_big', mid, username=mid, updated_at=sync_started_at - 10)
    for idx in range(520):
        store.upsert_member(_BOT, 'g_big', 'gone_%d' % idx, username='gone', updated_at=sync_started_at - 10)
    assert store.reconcile_group_members(_BOT, 'g_big', keep_big, sync_started_at) == 520
    assert set(store.get_members(_BOT, 'g_big')) == keep_big


def test_evict_member_placeholders_only_deletes_old_nameless_rows(store, tmp_path):
    now = int(time.time())
    day = 86400
    store.touch_group(_BOT, 'g_ph')
    store.upsert_member(_BOT, 'g_ph', 'm_old_ph', updated_at=now - 61 * day)
    store.upsert_member(_BOT, 'g_ph', 'm_fresh_ph', updated_at=now - 10 * day)
    store.upsert_member(_BOT, 'g_ph', 'm_old_user', username='有昵称', updated_at=now - 90 * day)
    store.upsert_member(_BOT, 'g_ph', 'm_old_card', member_nickname='有名片', updated_at=now - 90 * day)

    assert store.evict_member_placeholders(now=now) == 1
    remaining = set(store.get_members(_BOT, 'g_ph'))
    assert remaining == {'m_fresh_ph', 'm_old_user', 'm_old_card'}

    # open_db 初始清扫同样只删 60 天纯占位，保留有昵称的旧成员。
    store.upsert_member(_BOT, 'g_ph', 'm_boot_ph', updated_at=now - 70 * day)
    store.close_db()
    store.open_db(tmp_path / 'cache.sqlite3')
    assert set(store.get_members(_BOT, 'g_ph')) == {'m_fresh_ph', 'm_old_user', 'm_old_card'}


def test_eviction_and_touch_revival_clear_verified_at(store):
    now = int(time.time())
    day = 86400
    # 1. 常规淘汰转 dormant 时清空 verified_at。
    store.upsert_group(
        _BOT, 'g_dormant', state='active', members_state='complete',
        verified_at=now - 2 * day, last_seen_at=now - 130 * day
    )
    assert store.evict_members_by_age(now=now) == 1
    dormant = store.get_group(_BOT, 'g_dormant')
    assert dormant['state'] == 'dormant'
    assert dormant['members_state'] == 'evicted'
    assert dormant['verified_at'] is None

    # 2. suspect 满 30 天淘汰时清空 verified_at。
    store.upsert_group(
        _BOT, 'g_sus', state='suspect', members_state='complete',
        verified_at=now - 5 * day, last_seen_at=now - 35 * day
    )
    assert store.evict_suspect_groups(now=now) == 1
    sus = store.get_group(_BOT, 'g_sus')
    assert sus['state'] == 'dormant'
    assert sus['members_state'] == 'evicted'
    assert sus['verified_at'] is None

    # 3. 即使历史库里 evicted 群还留着旧 verified_at，touch_group 复活时也会置空。
    store.upsert_group(
        _BOT, 'g_legacy_evicted', state='dormant', members_state='evicted',
        verified_at=now - 3 * day, last_seen_at=now - 200 * day
    )
    store.touch_group(_BOT, 'g_legacy_evicted')
    revived = store.get_group(_BOT, 'g_legacy_evicted')
    assert revived['state'] == 'active'
    assert revived['members_state'] == 'active'
    assert revived['verified_at'] is None
    store._commit_locked()
    assert store.get_group(_BOT, 'g_legacy_evicted')['verified_at'] is None


def test_reconcile_zero_deletes_releases_sqlite_write_lock(store, tmp_path):
    sync_started_at = 10000
    store.touch_group(_BOT, 'g_zero')
    store.upsert_member(_BOT, 'g_zero', 'm1', username='留存', updated_at=sync_started_at - 10)
    # 删除 0 行（所有成员都在 keep_openids 中），仍必须提交释放写锁。
    assert store.reconcile_group_members(_BOT, 'g_zero', {'m1'}, sync_started_at) == 0

    other = sqlite3.connect(tmp_path / 'cache.sqlite3', timeout=0.2)
    try:
        other.execute("INSERT INTO meta(key,value) VALUES('lock_check','ok')")
        other.commit()
    finally:
        other.close()
    assert store.get_meta('lock_check') == 'ok'


def test_query_plans_and_legacy_schema_partial_index(store, tmp_path):
    db = store.open_db()
    # 验证 reconcile 走主键索引而不误选 idx_members_scan。
    plan_rec = [
        row['detail'] for row in db.execute(
            'EXPLAIN QUERY PLAN DELETE FROM members '
            'WHERE bot_hash=? AND group_openid=? '
            'AND member_openid NOT IN (?) AND +updated_at<?',
            (_BOT, 'g1', 'm1', 100)
        ).fetchall()
    ]
    assert any('sqlite_autoindex_members_1' in line for line in plan_rec)
    assert not any('idx_members_scan' in line for line in plan_rec)

    # 验证占位清理走部分索引 idx_members_placeholders。
    plan_ph = [
        row['detail'] for row in db.execute(
            'EXPLAIN QUERY PLAN SELECT bot_hash, group_openid, member_openid FROM members '
            "WHERE (username IS NULL OR username='') "
            "AND (member_nickname IS NULL OR member_nickname='') "
            'AND updated_at<? ORDER BY updated_at ASC LIMIT ?',
            (100, 1000)
        ).fetchall()
    ]
    assert any('idx_members_placeholders' in line for line in plan_ph)

    # 验证旧库无 member_nickname 列时能先补列再建部分索引。
    legacy_db_path = tmp_path / 'legacy_schema.sqlite3'
    raw = sqlite3.connect(legacy_db_path)
    try:
        raw.executescript('''
            CREATE TABLE groups(
                bot_hash TEXT NOT NULL, group_openid TEXT NOT NULL,
                joined_at TEXT, member_role TEXT, allow_proactive_msg INTEGER,
                recv_msg_setting TEXT, last_seen_at INTEGER NOT NULL,
                state TEXT NOT NULL, members_state TEXT NOT NULL,
                updated_at INTEGER NOT NULL, verified_at INTEGER,
                PRIMARY KEY(bot_hash, group_openid));
            CREATE TABLE members(
                bot_hash TEXT NOT NULL, group_openid TEXT NOT NULL,
                member_openid TEXT NOT NULL, username TEXT, member_role TEXT,
                bot INTEGER, joined_at TEXT, union_openid TEXT,
                updated_at INTEGER NOT NULL, source TEXT,
                PRIMARY KEY(bot_hash, group_openid, member_openid));
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        ''')
        raw.commit()
    finally:
        raw.close()
    upgraded = store.open_db(legacy_db_path)
    indexes = {
        row[1] for row in upgraded.execute("PRAGMA index_list('members')").fetchall()
    }
    assert 'idx_members_placeholders' in indexes


def test_atomic_group_state_helpers(store):
    # mark_group_suspect：不存在不插新行，存在才置 suspect。
    assert store.mark_group_suspect(_BOT, 'g_missing') is False
    assert store.get_group(_BOT, 'g_missing') is None

    store.touch_group(_BOT, 'g_atomic')
    store.upsert_member(_BOT, 'g_atomic', 'm1', username='成员1')
    assert store.mark_group_suspect(_BOT, 'g_atomic') is True
    assert store.get_group(_BOT, 'g_atomic')['state'] == 'suspect'

    # mark_group_warming：suspect 群拒绝；不存在拒绝。
    assert store.mark_group_warming(_BOT, 'g_missing') is False
    assert store.get_group(_BOT, 'g_missing') is None
    assert store.mark_group_warming(_BOT, 'g_atomic') is False

    # restore_group_active_if_suspect：仅 suspect -> active。
    assert store.restore_group_active_if_suspect(_BOT, 'g_atomic') is True
    assert store.get_group(_BOT, 'g_atomic')['state'] == 'active'
    assert store.restore_group_active_if_suspect(_BOT, 'g_atomic') is False
    assert store.restore_group_active_if_suspect(_BOT, 'g_missing') is False

    # remove_group_if_suspect：active 群不删；suspect 群才删（连同成员）。
    assert store.remove_group_if_suspect(_BOT, 'g_atomic') is False
    assert store.get_group(_BOT, 'g_atomic') is not None
    assert 'm1' in store.get_members(_BOT, 'g_atomic')
    assert store.mark_group_suspect(_BOT, 'g_atomic') is True
    assert store.remove_group_if_suspect(_BOT, 'g_atomic') is True
    assert store.get_group(_BOT, 'g_atomic') is None
    assert store.get_members(_BOT, 'g_atomic') == {}

    # mark_group_warming / reset_group_warming 原子迁移，不降级 complete、不复活已删群。
    store.touch_group(_BOT, 'g_warm')
    assert store.mark_group_warming(_BOT, 'g_warm') is True
    assert store.get_group(_BOT, 'g_warm')['members_state'] == 'warming'
    assert store.mark_group_warming(_BOT, 'g_warm') is False
    assert store.reset_group_warming(_BOT, 'g_warm') is True
    assert store.get_group(_BOT, 'g_warm')['members_state'] == 'active'
    assert store.reset_group_warming(_BOT, 'g_warm') is False

    store.upsert_group(_BOT, 'g_done', state='active', members_state='complete', verified_at=100)
    assert store.mark_group_warming(_BOT, 'g_done') is False
    assert store.reset_group_warming(_BOT, 'g_done') is False
    assert store.get_group(_BOT, 'g_done')['members_state'] == 'complete'
    assert store.reset_group_warming(_BOT, 'g_missing') is False
    assert store.get_group(_BOT, 'g_missing') is None


def test_evict_and_reconcile_rollback_preserves_db_and_import_changes(store):
    now = int(time.time())
    day = 86400
    store.upsert_group(_BOT, 'g_ev_fail', state='suspect', last_seen_at=now - 40 * day)
    store.upsert_member(_BOT, 'g_ev_fail', 'm1', username='u1', updated_at=now - 10)
    store.upsert_group(_BOT, 'g_age_fail', state='active', last_seen_at=now - 130 * day)
    store.upsert_member(_BOT, 'g_age_fail', 'm2', username='u2', updated_at=now - 10)
    store._commit_locked()

    db = store._db()
    db.execute(
        "CREATE TRIGGER fail_group_update BEFORE UPDATE ON groups BEGIN "
        "SELECT RAISE(ABORT, 'update_fail'); END"
    )
    db.commit()
    store._import_changes = set()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            store.evict_suspect_groups(now=now)
        # 事务回滚后成员未被删，且 _import_changes 不被污染。
        assert 'm1' in store.get_members(_BOT, 'g_ev_fail')
        assert store.get_group(_BOT, 'g_ev_fail')['state'] == 'suspect'
        assert store._import_changes == set()

        with pytest.raises(sqlite3.IntegrityError):
            store.evict_members_by_age(now=now)
        assert 'm2' in store.get_members(_BOT, 'g_age_fail')
        assert store.get_group(_BOT, 'g_age_fail')['state'] == 'active'
        assert store._import_changes == set()
    finally:
        store._import_changes = None
        db.execute('DROP TRIGGER fail_group_update')
        db.commit()

    # reconcile 慢路径与占位清理在 DELETE 失败回滚后不污染 _import_changes。
    store.touch_group(_BOT, 'g_rec_rb')
    store.upsert_member(_BOT, 'g_rec_rb', 'm_keep', username='留存', updated_at=100)
    store.upsert_member(_BOT, 'g_rec_rb', 'm_gone', username='离群', updated_at=100)
    store.upsert_member(_BOT, 'g_rec_rb', 'm_ph_old', updated_at=now - 70 * day)
    store._commit_locked()
    db.execute(
        "CREATE TRIGGER fail_member_del BEFORE DELETE ON members BEGIN "
        "SELECT RAISE(ABORT, 'del_fail'); END"
    )
    db.commit()
    store._import_changes = set()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            store.reconcile_group_members(_BOT, 'g_rec_rb', {'m_keep'}, 200)
        assert store._import_changes == set()
        assert set(store.get_members(_BOT, 'g_rec_rb')) == {'m_keep', 'm_gone', 'm_ph_old'}

        with pytest.raises(sqlite3.IntegrityError):
            store.evict_member_placeholders(now=now)
        assert store._import_changes == set()
        assert 'm_ph_old' in store.get_members(_BOT, 'g_rec_rb')
    finally:
        store._import_changes = None
        db.execute('DROP TRIGGER fail_member_del')
        db.commit()
