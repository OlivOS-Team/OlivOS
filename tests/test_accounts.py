"""Account identity, persistence and enable-state contracts."""

import socket
from unittest.mock import Mock

import pytest

import OlivOS


@pytest.fixture
def bot():
    return OlivOS.API.bot_info_T(id=10001, platform_sdk='terminal_link',
                                 platform_platform='terminal', platform_model='default')


def test_account_save_load_preserves_configuration(tmp_path, bot):
    bot.enable = False
    bot.debug_mode = True
    bot.extends = {'setting': '中文', 'nested': [1, 2]}
    path = tmp_path / 'account.json'
    logger = Mock()
    OlivOS.accountAPI.Account.save(path, logger, {bot.hash: bot})
    loaded = OlivOS.accountAPI.Account.load(path, logger)[bot.hash]
    assert loaded.id == bot.id
    assert loaded.platform == bot.platform
    assert loaded.extends == bot.extends
    assert loaded.enable is False and loaded.debug_mode is True


@pytest.mark.parametrize('content', [None, '{broken'])
def test_unreadable_account_file_falls_back_to_empty(tmp_path, content):
    path = tmp_path / 'account.json'
    if content is not None:
        path.write_text(content, encoding='utf-8')
    assert OlivOS.accountAPI.Account.load(path, Mock()) == {}


def test_disabled_accounts_are_excluded_without_mutating_source(bot):
    other = OlivOS.API.bot_info_T(id=10002)
    other.enable = False
    accounts = {bot.hash: bot, other.hash: other}
    assert OlivOS.accountAPI.Account.getEnabledAccountData(accounts) == {bot.hash: bot}
    assert len(accounts) == 2


def test_account_hash_separates_platforms():
    hash_for = OlivOS.API.getBotHash
    assert hash_for(1, 'onebot', 'qq', 'default') == hash_for('1', 'onebot', 'qq', 'default')
    assert hash_for(1, 'onebot', 'qq', 'default') != hash_for(1, 'terminal_link', 'terminal', 'default')


def test_safe_mode_does_not_load_account_password(tmp_path, bot):
    bot.password = 'fixture-password'
    path = tmp_path / 'account.json'
    OlivOS.accountAPI.Account.save(path, Mock(), {bot.hash: bot})
    loaded = OlivOS.accountAPI.Account.load(path, Mock(), safe_mode=True)
    assert loaded[bot.hash].password == ''


def test_port_selector_allocates_distinct_ports_and_releases_them():
    with OlivOS.accountAPI.free_port_selector() as selector:
        ports = [selector.get_free_port() for _ in range(8)]
        assert len(set(ports)) == 8
    for port in ports:
        with socket.socket() as probe:
            probe.bind(('', port))
