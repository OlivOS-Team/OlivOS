"""Account identity, persistence and enable-state contracts."""

import copy
import json
import socket
from unittest.mock import Mock

import pytest

import OlivOS


@pytest.fixture
def bot():
    return OlivOS.API.bot_info_T(id=10001, platform_sdk='terminal_link',
                                 platform_platform='terminal', platform_model='default',
                                 server_type='websocket', port=0)


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


@pytest.fixture
def account_row():
    return {
        'id': 10001, 'password': '', 'sdk_type': 'onebot', 'platform_type': 'qq', 'model_type': 'default',
        'server': {'auto': False, 'type': 'post', 'host': 'http://127.0.0.1', 'port': 5700, 'access_token': ''},
        'enable': True, 'debug': False, 'extends': {},
    }


@pytest.mark.parametrize('language', ['zh-CN', 'en-US'])
@pytest.mark.parametrize('field,value', [
    ('id', []), ('id', ''), ('password', {}), ('enable', 'false'), ('debug', 1), ('extends', []),
    ('sdk_type', 'typo'), ('platform_type', 'typo'), ('model_type', 'typo'),
    ('server', []), ('server.auto', 'false'), ('server.type', 'port'), ('server.host', {}),
    ('server.port', 'oops'), ('server.port', True), ('server.port', -1), ('server.port', 65536),
    ('server.access_token', {}), ('extends.qsign-server', {}), ('enbale', True), ('server.prot', 5700),
])
def test_invalid_account_field_logs_and_loads_later_accounts(
        tmp_path, monkeypatch, account_row, language, field, value):
    monkeypatch.setattr(OlivOS.L10NDataAPI, 'flagL10NSelection', language)
    invalid = copy.deepcopy(account_row)
    parent = invalid
    parts = field.split('.')
    for part in parts[:-1]:
        parent = parent[part]
    parent[parts[-1]] = value
    account_row['id'] = 10002
    path = tmp_path / 'account.json'
    original = json.dumps({'account': [invalid, account_row]})
    path.write_text(original, encoding='utf-8')
    logger = Mock()

    loaded = OlivOS.accountAPI.Account.load(path, logger)

    assert [bot.id for bot in loaded.values()] == [10002]
    errors = [call.args[1] for call in logger.log.call_args_list if call.args[0] == 4]
    assert errors and all(str(path) in error for error in errors)
    assert any('account[0].' + field in error for error in errors)
    assert ('继续' if language == 'zh-CN' else 'continue') in errors[0]
    assert path.read_text(encoding='utf-8') == original


@pytest.mark.parametrize('field', [
    'id', 'password', 'sdk_type', 'platform_type', 'model_type', 'debug', 'server',
    'server.auto', 'server.type', 'server.host', 'server.port', 'server.access_token',
])
def test_missing_account_field_is_nonfatal(tmp_path, account_row, field):
    parent = account_row
    parts = field.split('.')
    for part in parts[:-1]:
        parent = parent[part]
    del parent[parts[-1]]
    path = tmp_path / 'account.json'
    path.write_text(json.dumps({'account': [account_row]}), encoding='utf-8')
    logger = Mock()
    assert OlivOS.accountAPI.Account.load(path, logger) == {}
    assert any('account[0].' + field in call.args[1] for call in logger.log.call_args_list if call.args[0] == 4)


@pytest.mark.parametrize('body', [None, [], {}, {'account': {}}, {'account': [None, [], 1]}])
def test_invalid_account_document_structure_is_nonfatal(tmp_path, body):
    path = tmp_path / 'account.json'
    path.write_text(json.dumps(body), encoding='utf-8')
    logger = Mock()
    assert OlivOS.accountAPI.Account.load(path, logger) == {}
    assert any(call.args[0] == 4 for call in logger.log.call_args_list)


@pytest.mark.parametrize('title,config', [
    (title, config) for title, config in OlivOS.accountMetadataAPI.accountTypeMappingList.items()
    if title != '自定义'
])
def test_all_account_presets_load_and_reject_invalid_connection_type(tmp_path, account_row, title, config):
    platform, sdk, model, auto, connection = config
    account_row.update(platform_type=platform, sdk_type=sdk, model_type=model)
    account_row['server'].update(auto=auto == 'True', type=connection)
    if sdk == 'dingtalk_link':
        account_row['extends'] = {'app_key': 'fixture-key', 'app_secret': 'fixture-secret'}
    path = tmp_path / 'account.json'
    path.write_text(json.dumps({'account': [account_row]}), encoding='utf-8')
    logger = Mock()
    assert len(OlivOS.accountAPI.Account.load(path, logger)) == 1
    assert not [call for call in logger.log.call_args_list if call.args[0] == 4]

    account_row['server']['type'] = 'port'
    path.write_text(json.dumps({'account': [account_row]}), encoding='utf-8')
    assert OlivOS.accountAPI.Account.load(path, logger) == {}
    assert any('server.type' in call.args[1] for call in logger.log.call_args_list if call.args[0] == 4)


@pytest.mark.parametrize('sdk,platform,model', [
    ('discord_link', 'discord', 'intents'), ('qqGuildv2_link', 'qqGuild', 'public_intents'),
    ('mhyVila_link', 'mhyVila', 'sandbox'),
])
def test_intents_are_not_validated_as_tcp_ports(tmp_path, account_row, sdk, platform, model):
    account_row.update(sdk_type=sdk, platform_type=platform, model_type=model)
    account_row['server'].update(type='websocket', port=1 << 30)
    path = tmp_path / 'account.json'
    path.write_text(json.dumps({'account': [account_row]}), encoding='utf-8')
    logger = Mock()
    assert len(OlivOS.accountAPI.Account.load(path, logger)) == 1
    assert not [call for call in logger.log.call_args_list if call.args[0] == 4]


def test_optional_fields_and_custom_extensions_remain_supported(tmp_path, account_row):
    del account_row['enable']
    account_row['extends'] = {'plugin-setting': {'nested': [1, 2]}}
    path = tmp_path / 'account.json'
    path.write_text(json.dumps({'account': [account_row]}), encoding='utf-8')
    bot = next(iter(OlivOS.accountAPI.Account.load(path, Mock()).values()))
    assert bot.enable is True
    assert bot.extends == account_row['extends']


def test_account_errors_do_not_echo_values(tmp_path, account_row):
    secret = 'fixture-private-value'
    account_row['server']['access_token'] = {'bad': secret}
    account_row['password'] = [secret]
    account_row['server']['host'] = [secret]
    path = tmp_path / 'account.json'
    path.write_text(json.dumps({'account': [account_row]}), encoding='utf-8')
    logger = Mock()
    assert OlivOS.accountAPI.Account.load(path, logger) == {}
    assert secret not in str(logger.log.call_args_list)


def test_webui_does_not_offer_partial_accounts_for_overwriting_bad_file(tmp_path, account_row):
    from types import SimpleNamespace
    from OlivOS.webUI import pageAPI

    invalid = copy.deepcopy(account_row)
    del invalid['server']
    path = tmp_path / 'account.json'
    original = json.dumps({'account': [invalid, account_row]})
    path.write_text(original, encoding='utf-8')
    host = SimpleNamespace(account_path=path, log=Mock())
    with pytest.raises(ValueError):
        pageAPI.load_accounts(host)
    assert path.read_text(encoding='utf-8') == original


@pytest.mark.parametrize('malformed_json', [False, True])
def test_startup_save_preserves_invalid_source(tmp_path, account_row, malformed_json):
    invalid = copy.deepcopy(account_row)
    invalid['enable'] = 'false'
    path = tmp_path / 'account.json'
    original = '{broken' if malformed_json else json.dumps({'account': [invalid, account_row]})
    path.write_text(original, encoding='utf-8')
    logger = Mock()
    loaded = OlivOS.accountAPI.Account.load(path, logger)
    assert OlivOS.accountAPI.Account.save(path, logger, loaded, protect_existing=True) is False
    assert path.read_text(encoding='utf-8') == original


def test_startup_save_still_updates_valid_config(tmp_path, account_row):
    path = tmp_path / 'account.json'
    path.write_text(json.dumps({'account': [account_row]}), encoding='utf-8')
    loaded = OlivOS.accountAPI.Account.load(path, Mock())
    next(iter(loaded.values())).debug_mode = True
    OlivOS.accountAPI.Account.save(path, Mock(), loaded, protect_existing=True)
    assert json.loads(path.read_text(encoding='utf-8'))['account'][0]['debug'] is True


def test_duplicate_accounts_are_reported_without_overwriting_first(tmp_path, account_row):
    duplicate = copy.deepcopy(account_row)
    duplicate['server']['port'] = 5701
    path = tmp_path / 'account.json'
    path.write_text(json.dumps({'account': [account_row, duplicate]}), encoding='utf-8')
    logger = Mock()
    loaded = OlivOS.accountAPI.Account.load(path, logger)
    assert len(loaded) == 1 and next(iter(loaded.values())).post_info.port == 5700
    assert any('account[1].id' in call.args[1] for call in logger.log.call_args_list if call.args[0] == 4)


@pytest.mark.parametrize('sdk,platform,model,connection', [
    ('discord_link', 'discord', 'default', 'post'),
    ('telegram_poll', 'telegram', 'default', 'websocket'),
    ('qqGuildv2_link', 'qqGuild', 'public_intents', 'post'),
])
def test_connection_type_must_match_selected_protocol(tmp_path, account_row, sdk, platform, model, connection):
    account_row.update(sdk_type=sdk, platform_type=platform, model_type=model)
    account_row['server']['type'] = connection
    path = tmp_path / 'account.json'
    path.write_text(json.dumps({'account': [account_row]}), encoding='utf-8')
    logger = Mock()
    assert OlivOS.accountAPI.Account.load(path, logger) == {}
    assert any('server.type' in call.args[1] for call in logger.log.call_args_list if call.args[0] == 4)
