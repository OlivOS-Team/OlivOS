"""Real temporary SQLite databases, including persistence beyond the memory cache."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import pytest

from OlivOS.userModule import UserConfDB


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setattr(UserConfDB, 'DATABASE_PATH', str(tmp_path / 'config.db'))
    db = UserConfDB.DataBaseAPI(Mock(), max_thread=2, timeout=5)
    for namespace in ('one', 'two'):
        db._init_namespace(namespace)
    yield db
    db.stop()


def test_database_persists_values_after_reopening(database):
    database.set_basic_config('one', 'value', '中文')
    other = UserConfDB.DataBaseAPI(Mock(), max_thread=1, timeout=5)
    try:
        assert other.get_basic_config('one', 'value') == '中文'
    finally:
        other.stop()


def test_database_namespaces_are_isolated(database):
    database.set_basic_config('one', 'key', 'first')
    database.set_basic_config('two', 'key', 'second')
    database.clean_cache()
    assert database.get_basic_config('one', 'key') == 'first'
    assert database.get_basic_config('two', 'key') == 'second'


def test_user_configuration_separates_platform_and_user(database):
    database.set_user_config('one', 'key', 'value', 'qq', 42)
    assert database.get_user_config('one', 'key', 'qq', '42') == 'value'
    assert database.get_user_config('one', 'key', 'qq', 43) is None
    assert database.get_user_config('one', 'key', 'discord', 42) is None


def test_group_configuration_separates_host_and_group(database):
    database.set_group_config('one', 'key', 'value', 'qqGuild', 'group', host_id='host')
    assert database.get_group_config('one', 'key', 'qqGuild', 'group', host_id='host') == 'value'
    assert database.get_group_config('one', 'key', 'qqGuild', 'group', host_id='other') is None


def test_database_pickle_roundtrip(database):
    value = {'members': [1, 2], 'options': (True, '中文')}
    database.set_basic_config('one', 'complex', value, pkl=True)
    database.clean_cache()
    assert database.get_basic_config('one', 'complex', pkl=True) == value


def test_missing_configuration_returns_default(database):
    assert database.get_basic_config('one', 'missing', default_value='fallback') == 'fallback'


def test_database_keys_are_bound_parameters(database):
    key = "'); DROP TABLE table_master; --"
    database.set_basic_config('one', key, 'safe')
    database.clean_cache()
    assert database.get_basic_config('one', key) == 'safe'
    database._init_namespace('third')
    assert 'third' in database.namespace_list


def test_database_concurrent_writes_do_not_lose_independent_keys(database):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: database.set_basic_config('one', str(i), i), range(20)))
    database.clean_cache()
    assert [database.get_basic_config('one', str(i)) for i in range(20)] == list(range(20))
