# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_webui.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

# WebUI 使用临时账号、插件和日志，不启动真实机器人。

import asyncio
import base64
import copy
import json
import os
import queue
import secrets
import socket
import threading
import time
from pathlib import Path

import aiohttp
import pytest

import OlivOS
from OlivOS.webUI import pageAPI, serverAPI, staticData


def account(account_id=10001):
    bot = OlivOS.API.bot_info_T(
        id=account_id, password=secrets.token_urlsafe(16),
        server_auto=True, server_type='websocket', host='NONEED', port=0,
        access_token=secrets.token_urlsafe(16), platform_sdk='terminal_link',
        platform_platform='terminal', platform_model='default')
    bot.extends = {'app_secret': secrets.token_urlsafe(16), 'setting': 'preserve',
                   'qsign-server': [{'addr': 'http://localhost:1', 'key': secrets.token_urlsafe(16)},
                                    {'addr': 'http://localhost:2', 'key': secrets.token_urlsafe(16)}]}
    return bot


@pytest.fixture
def host(tmp_path):
    bot = account()
    service = serverAPI.server(root_path=tmp_path, rx_queue=queue.Queue(), control_queue=queue.Queue(),
                               bot_info_dict={bot.hash: bot})
    service.account_path.parent.mkdir(parents=True, exist_ok=True)
    OlivOS.accountAPI.Account.save(str(service.account_path), service, service.accounts)
    yield service
    service.on_terminate()


@pytest.fixture
def client(host):
    client = host.app.test_client()
    client.environ_base['HTTP_X_AUTH_TOKEN'] = host.token
    return client


def send(host, data):
    host.consume(OlivOS.API.Control.packet('send', {'data': data}))


def test_auth_and_rate_limit(host):
    client = host.app.test_client()
    assert client.get('/api/health').json == {'status': 'OK'}
    assert client.get('/').status_code == 200
    for _ in range(10):
        assert client.get('/api/status').status_code == 401
    assert client.get('/api/status').status_code == 429
    host.failures.clear()
    good = {'X-Auth-Token': host.token}
    assert client.get('/api/status', headers=good).status_code == 200
    assert client.get('/api/status', headers={**good, 'Origin': 'https://foreign.invalid'}).status_code == 403
    response = client.get('/api/status', headers=good)
    assert 'Access-Control-Allow-Origin' not in response.headers
    assert response.headers['Cache-Control'] == 'no-store'
    assert host.token not in response.get_data(as_text=True)


def test_token_persisted_not_regenerated(host):
    other = serverAPI.server(root_path=host.root)
    assert other.token == host.token
    assert (host.root / 'conf/webui_token.txt').is_file()


@pytest.mark.parametrize('legacy_path', ['data/webui_token', 'data/webui_token.txt'])
def test_legacy_token_is_not_used(tmp_path, legacy_path):
    legacy = tmp_path / legacy_path
    legacy.parent.mkdir(parents=True)
    old_token = secrets.token_urlsafe(32)
    legacy.write_text(old_token, encoding='utf-8')
    service = serverAPI.server(root_path=tmp_path)
    assert service.token != old_token
    assert legacy.read_text(encoding='utf-8') == old_token
    assert (tmp_path / 'conf/webui_token.txt').read_text(encoding='utf-8') == service.token
    service.on_terminate()


def test_logo_is_available_before_login(host):
    client = host.app.test_client()
    response = client.get('/static/logo.png')
    assert response.status_code == 200
    assert response.mimetype == 'image/png'
    assert response.data == base64.b64decode(staticData.FILES['logo.png'])
    html = client.get('/').get_data(as_text=True)
    assert 'conf/webui_token.txt' in html
    assert html.count('class="brand-logo"') == 2


def test_all_rest_routes(client, host):
    for endpoint in ['/api/status', '/api/accounts', '/api/accounts/schema', '/api/logs', '/api/plugins',
                     '/api/terminals', '/api/accounts/webhook?id=10001']:
        response = client.get(endpoint)
        assert response.status_code == 200, endpoint
    status = client.get('/api/status').json
    assert status['accounts'] == 1
    assert status['online'] == 0  # 启用不能冒充在线。
    for endpoint, action in [('/api/plugins/reload', 'restart_send'), ('/api/update/check', 'init_type'),
                             ('/api/exit', 'exit_total')]:
        assert client.post(endpoint).status_code == 202
        assert host.Proc_info.control_queue.get_nowait().action == action


def test_log_display_setting_changes_webui_history_not_original_logs(client, host):
    message = 'User: [OP:at,id=42,name=Alice][OP:face,id=311]'
    send(host, {'action': 'logger', 'event': 'log', 'data': {
        'data': {'log_level': 2, 'log_time': 1750000000}, 'str': message
    }})
    assert client.get('/api/logs/display').json == {'format': 'op'}
    assert client.put('/api/logs/display', json={'format': 'wrong'}).status_code == 400
    assert client.put('/api/logs/display', json={'format': 'cq'}).json == {
        'format': 'cq'
    }
    assert OlivOS.diagnoseAPI.load_log_display_mode(host.root) == 'cq'
    log = client.get('/api/logs').json['items'][-1]
    assert log['text'] == message
    assert log['op_text'] == message
    assert log['cq_text'] == 'User: [CQ:at,qq=42,name=Alice][CQ:face,id=311]'
    assert host.snapshot('logs')[-1]['text'] == message
    assert client.put('/api/logs/display', json={'format': 'op'}).status_code == 200

    send(host, {'action': 'logger', 'event': 'log', 'data': {
        'data': {'log_level': 2, 'log_time': 1750000001},
        'str': 'User: [CQ:at,qq=7,name=Bob][CQ:face,id=311]'
    }})
    last = client.get('/api/logs').json['items'][-1]
    assert last['op_text'] == 'User: [OP:at,id=7,name=Bob][OP:face,id=311]'
    assert last['cq_text'] == last['text']


def test_log_display_formats_logfile_fallback_without_rewriting_file(client, host):
    logfile = host.root / 'logfile/OlivOS_logfile_unity.log'
    logfile.parent.mkdir(parents=True)
    source = '[2026-09-23 17:00:00] - [INFO] - [unity] - [OP:at,id=42]'
    logfile.write_text(source + '\n', encoding='utf-8')

    item = client.get('/api/logs').json['items'][0]
    assert item['op_text'] == '[unity] - [OP:at,id=42]'
    assert item['cq_text'] == '[unity] - [CQ:at,qq=42]'
    assert logfile.read_text(encoding='utf-8') == source + '\n'


def test_unknown_account_details_exclude_disabled_and_known_states(client, host):
    from types import SimpleNamespace

    other_platform = OlivOS.API.bot_info_T(
        id=10001, platform_sdk='onebot', platform_platform='qq', platform_model='napcat',
    )
    disabled, online, offline = account(10003), account(10004), account(10005)
    disabled.enable = False
    for bot in [other_platform, disabled, online, offline]:
        host.accounts[bot.hash] = bot
    host.runtime.update({
        'online': SimpleNamespace(bot_info=online, ws_conn=SimpleNamespace(open=True)),
        'offline': SimpleNamespace(bot_info=offline, ws_conn=None),
    })
    status = client.get('/api/status').json
    assert status['accounts'] == 5
    assert status['enabled'] == 4 and status['online'] == 1 and status['unknown'] == 2
    assert [(item['id'], item['platform_type']) for item in status['unknown_accounts']] == [
        ('10001', 'terminal'), ('10001', 'qq'),
    ]
    assert all(set(item) == {'id', 'platform_type', 'sdk_type', 'model_type'}
               for item in status['unknown_accounts'])
    assert status['account_connections'] == {
        next(iter(host.accounts)): 'unknown', other_platform.hash: 'unknown',
        disabled.hash: 'disabled', online.hash: 'online', offline.hash: 'offline',
    }
    for index, bot in enumerate(host.accounts.values()):
        host.runtime[f'known-{index}'] = SimpleNamespace(bot_info=bot, ws_conn=None)
    status = client.get('/api/status').json
    assert status['unknown'] == 0 and status['unknown_accounts'] == []
    assert 'unknown' not in status['account_connections'].values()


def test_onebot_reverse_websocket_reports_connection_state(client, host):
    from unittest.mock import Mock

    bot = OlivOS.API.bot_info_T(
        id=10020, platform_sdk='onebot', platform_platform='qq', platform_model='default',
        server_type='websocket_host', host='127.0.0.1', port=5700,
    )
    host.accounts = {bot.hash: bot}
    service = OlivOS.onebotV11HostServerAPI.server(
        'test-onebot-host', rx_queue=queue.Queue(), tx_queue=queue.Queue(), bot_info_dict=bot,
    )
    host.runtime['test-onebot-host'] = service
    assert client.get('/api/status').json['account_connections'][bot.hash] == 'offline'

    async def connected_session():
        connection = Mock()

        async def recv():
            await asyncio.Event().wait()

        connection.recv = recv
        task = asyncio.create_task(service.session(connection))
        try:
            await asyncio.sleep(0)
            assert service.active_links == 1
            status = client.get('/api/status').json
            assert status['online'] == 1 and status['unknown'] == 0
            assert status['account_connections'][bot.hash] == 'online'
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(connected_session())
    assert service.active_links == 0
    status = client.get('/api/status').json
    assert status['account_connections'][bot.hash] == 'offline'
    assert status['unknown'] == 0 and 'unknown' not in status['account_connections'].values()


def test_aiohttp_websocket_adapters_report_connection_state(client, host):
    from types import SimpleNamespace

    bots = [
        OlivOS.API.bot_info_T(
            id=10030 + index, platform_sdk='discord_link', platform_platform='discord', platform_model='default')
        for index in range(4)
    ]
    host.accounts = {bot.hash: bot for bot in bots}

    def process(bot, ws_obj):
        return SimpleNamespace(
            bot_info=bot, Proc_type='discord_link',
            Proc_data={'extend_data': {'ws_obj': ws_obj}},
        )

    host.runtime.update({
        # aiohttp 连接：没有 sock 属性，只能看 closed。
        'aiohttp-open': process(bots[0], SimpleNamespace(closed=False)),
        'aiohttp-closed': process(bots[1], SimpleNamespace(closed=True)),
        # 兼容保留旧适配器的 sock.connected 判定。
        'legacy-open': process(bots[2], SimpleNamespace(closed=True, sock=SimpleNamespace(connected=True))),
        'missing': process(bots[3], None),
    })
    status = client.get('/api/status').json
    assert status['unknown'] == 0
    assert status['account_connections'][bots[0].hash] == 'online'
    assert status['account_connections'][bots[1].hash] == 'offline'
    assert status['account_connections'][bots[2].hash] == 'online'
    assert status['account_connections'][bots[3].hash] == 'offline'


def test_account_activity_tracker_marks_and_snapshots():
    bot = account()
    tracker = OlivOS.API.accountActivity(bot)
    assert tracker.snapshot() == {bot.hash: 0.0}
    assert tracker.mark('missing-hash') is False
    assert tracker.mark(bot.hash) is True
    assert tracker.snapshot()[bot.hash] > 0
    assert OlivOS.API.accountActivity({bot.hash: bot}).snapshot() == {bot.hash: 0.0}
    assert OlivOS.API.accountActivity().snapshot() == {}


def test_shared_connection_proc_only_reports_its_own_accounts(client, host):
    from types import SimpleNamespace

    owned = OlivOS.API.bot_info_T(id=10050, platform_sdk='dodobot_ea', platform_platform='dodo',
                                  platform_model='default')
    foreign = OlivOS.API.bot_info_T(id=10051, platform_sdk='dodo_link', platform_platform='dodo',
                                    platform_model='default')
    host.accounts = {owned.hash: owned, foreign.hash: foreign}
    counter = SimpleNamespace(value=0)
    host.runtime['shared'] = SimpleNamespace(
        Proc_type='dodobot_ea', Proc_data={}, active_links=0,
        status_bot_info={owned.hash: owned},
    )
    status = client.get('/api/status').json
    assert status['account_connections'][owned.hash] == 'offline'
    assert status['account_connections'][foreign.hash] == 'unknown'
    host.runtime['shared'].active_links = 1
    status = client.get('/api/status').json
    assert status['account_connections'][owned.hash] == 'online'
    assert status['account_connections'][foreign.hash] == 'unknown'
    counter.value = 1


def test_onebot_http_post_reports_heartbeat_status(client, host):
    bot = OlivOS.API.bot_info_T(
        id=10040, platform_sdk='onebot', platform_platform='qq', platform_model='default',
        server_type='post', host='127.0.0.1', port=5700,
    )
    other = OlivOS.API.bot_info_T(
        id=10041, platform_sdk='onebot', platform_platform='qq', platform_model='default',
        server_type='post', host='127.0.0.1', port=5700,
    )
    host.accounts = {bot.hash: bot, other.hash: other}
    service = OlivOS.flaskServerAPI.server(
        'test-onebot-post', 'test-onebot-post', ['GET', 'POST'], '127.0.0.1', 0,
        tx_queue=queue.Queue(), bot_info_dict=host.accounts,
    )
    service.app()
    service.set_config()
    host.runtime['test-onebot-post'] = service
    status = client.get('/api/status').json
    assert status['unknown'] == 0 and status['online'] == 0
    assert status['account_connections'][bot.hash] == 'offline'
    assert status['account_connections'][other.hash] == 'offline'
    flask_client = service.Proc_config['Flask_app'].test_client()
    heartbeat = {
        'time': int(time.time()), 'self_id': bot.id, 'post_type': 'meta_event',
        'meta_event_type': 'heartbeat', 'status': {'online': True, 'good': True}, 'interval': 5000,
    }
    assert flask_client.post('/OlivOSMsgApi/qq/onebot/default', json=heartbeat).status_code == 200
    status = client.get('/api/status').json
    assert status['online'] == 1 and status['unknown'] == 0
    assert status['account_connections'][bot.hash] == 'online'
    # 同一监听端口上的其他账号不会跟着变成在线。
    assert status['account_connections'][other.hash] == 'offline'
    # 未知 self_id 与非法请求不会影响已有状态。
    assert flask_client.post(
        '/OlivOSMsgApi/qq/onebot/default', json=dict(heartbeat, self_id=10099),
    ).status_code == 200
    assert flask_client.post(
        '/OlivOSMsgApi/qq/onebot/default', data='not json',
    ).status_code == 200
    assert client.get('/api/status').json['account_connections'][bot.hash] == 'online'
    # 超过心跳窗口后回落为离线，但仍是已知状态。
    service.activity._seen[service.activity._index[bot.hash]] = (
        time.monotonic() - pageAPI.ACTIVITY_ONLINE_WINDOW - 1
    )
    status = client.get('/api/status').json
    assert status['account_connections'][bot.hash] == 'offline'
    assert status['unknown'] == 0 and status['unknown_accounts'] == []


def test_webhook_accounts_use_shared_listener_status(client, host, tmp_path, monkeypatch):
    from unittest.mock import Mock

    monkeypatch.chdir(tmp_path)
    bots = [OlivOS.API.bot_info_T(
        id=10010 + index, platform_sdk='qqGuildv2_link', platform_platform='qqGuild',
        platform_model='public', server_type='post',
    ) for index in range(3)]
    bots[2].enable = False
    mapping = {bot.hash: bot for bot in bots}
    host.accounts = mapping
    webhook = OlivOS.qqGuildv2WebhookServerAPI.server(
        'test-webhook', 'test-webhook', ['POST'], '127.0.0.1', 0,
        bot_info_dict=mapping, Flask_ssl_dir=str(tmp_path / 'ssl'),
    )
    host.runtime['webhook'] = webhook
    status = client.get('/api/status').json
    assert status['unknown'] == 0 and status['online'] == 0
    assert status['account_connections'][bots[0].hash] == 'offline'

    listener = Mock()

    def serving():
        status = client.get('/api/status').json
        assert status['online'] == 2 and status['unknown'] == 0
        assert status['account_connections'][bots[0].hash] == 'online'
        assert status['account_connections'][bots[1].hash] == 'online'
        assert status['account_connections'][bots[2].hash] == 'disabled'
    listener.serve_forever.side_effect = serving
    monkeypatch.setattr(OlivOS.qqGuildv2WebhookServerAPI.pywsgi, 'WSGIServer', Mock(return_value=listener))
    monkeypatch.setattr(webhook, '_run_watchdog', lambda: None)
    webhook.run()
    assert not webhook.webhook_online
    assert client.get('/api/status').json['online'] == 0
    webhook._webhook_stopped.clear()
    webhook._webhook_last_ready.value = time.monotonic() - 3600
    assert not webhook.webhook_online
    webhook.on_terminate()
    listener.start.side_effect = OSError('test bind failure')
    with pytest.raises(OSError, match='test bind failure'):
        webhook.run()
    assert not webhook.webhook_online


def test_webhook_watchdog_updates_and_clears_status(tmp_path, monkeypatch):
    from unittest.mock import Mock

    webhook = OlivOS.qqGuildv2WebhookServerAPI.server(
        'test-webhook', 'test-webhook', ['POST'], '127.0.0.1', 0,
        Flask_ssl_dir=str(tmp_path / 'ssl'),
    )
    monkeypatch.setattr(OlivOS.qqGuildv2WebhookServerAPI, 'qqGuildv2WebhookHeartbeatInterval', .01)
    webhook._self_probe = Mock(return_value=True)
    watcher = threading.Thread(target=webhook._run_watchdog)
    watcher.start()
    try:
        deadline = time.monotonic() + 2
        while not webhook.webhook_online and time.monotonic() < deadline:
            time.sleep(.01)
        assert webhook.webhook_online
        webhook._self_probe.return_value = False
        deadline = time.monotonic() + 2
        while webhook.webhook_online and time.monotonic() < deadline:
            time.sleep(.01)
        assert not webhook.webhook_online
    finally:
        webhook.on_terminate()
        watcher.join(timeout=2)
        assert not watcher.is_alive()


def test_webhook_listener_does_not_resolve_hostname_on_start(tmp_path, monkeypatch):
    from unittest.mock import Mock

    webhook = OlivOS.qqGuildv2WebhookServerAPI.server(
        'test-webhook', 'test-webhook', ['POST'], '127.0.0.1', 0,
        Flask_ssl_dir=str(tmp_path / 'ssl'),
    )
    listener = Mock()
    listener.serve_forever.side_effect = KeyboardInterrupt
    factory = Mock(return_value=listener)
    monkeypatch.setattr(OlivOS.qqGuildv2WebhookServerAPI.pywsgi, 'WSGIServer', factory)
    monkeypatch.setattr(webhook, '_run_watchdog', lambda: None)
    monkeypatch.setattr(OlivOS.qqGuildv2WebhookServerAPI.socket, 'getfqdn',
                        lambda name: pytest.fail(f'unexpected reverse DNS for {name}'))
    with pytest.raises(KeyboardInterrupt):
        webhook.run()
    assert factory.call_args.kwargs['environ']['SERVER_NAME'] == '127.0.0.1'


def test_webhook_listener_status_visible_from_child_process(client, host, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    bot = OlivOS.API.bot_info_T(
        id=10010, platform_sdk='qqGuildv2_link', platform_platform='qqGuild',
        platform_model='public', server_type='post',
    )
    host.accounts = {bot.hash: bot}
    webhook = OlivOS.qqGuildv2WebhookServerAPI.server(
        'test-webhook', 'test-webhook', ['POST'], '127.0.0.1', port,
        bot_info_dict=host.accounts, Flask_ssl_dir=str(tmp_path / 'ssl'),
    )
    host.runtime['webhook'] = webhook
    process = webhook.start_unity('processing')
    try:
        deadline = time.monotonic() + 15
        while not webhook.webhook_online and process.is_alive() and time.monotonic() < deadline:
            time.sleep(.05)
        assert webhook.webhook_online, (
            f'webhook child: alive={process.is_alive()}, exitcode={process.exitcode}, '
            f'last_ready={webhook._webhook_last_ready.value}, stopped={webhook._webhook_stopped.is_set()}'
        )
        assert client.get('/api/status').json['account_connections'][bot.hash] == 'online'
        webhook.on_terminate()
        assert client.get('/api/status').json['account_connections'][bot.hash] == 'offline'
    finally:
        process.terminate()
        process.join(timeout=5)
        assert not process.is_alive()


def test_schema_presets_match_native_metadata(client):
    schema = client.get('/api/accounts/schema').json
    native = OlivOS.accountMetadataAPI.getAccountEditorMetadata()
    assert len(schema['presets']) == len(native['type_list']) - 1
    for preset in schema['presets']:
        mapping = OlivOS.accountMetadataAPI.accountTypeMappingList[preset['title']]
        assert [preset['platform_type'], preset['sdk_type'], preset['model_type'],
                str(preset['server']['auto']), preset['server']['type']] == mapping
        assert preset['model_type'] in schema['hierarchy'][preset['sdk_type']][preset['platform_type']]
        assert len(preset['fields']) == len(native['type_mapping_list_Entry_slot'][preset['title']])
    assert schema['qsign_limit'] == 10


def commit_request(host):
    packet = host.Proc_info.control_queue.get(timeout=2)
    assert packet.action == 'webui_accounts'
    host.commit_accounts(packet.key['request_id'], {})


def test_account_roundtrip_preserves_secrets_and_emits_hot_reload(client, host):
    old = next(iter(host.accounts.values()))
    body = client.get('/api/accounts').json
    text = json.dumps(body)
    assert old.password not in text and old.post_info.access_token not in text
    assert old.extends['app_secret'] not in text
    row = body['account'][0]
    assert row['password'] == pageAPI.MASK
    del row['password']
    del row['server']['access_token']
    row['enable'] = False
    row['debug'] = True
    row['id'] = '10002'
    worker = threading.Thread(target=commit_request, args=(host,))
    worker.start()
    response = client.post('/api/accounts', json=body)
    worker.join(timeout=2)
    assert response.status_code == 200, response.json
    loaded = OlivOS.accountAPI.Account.load(str(host.account_path), host)
    saved = next(iter(loaded.values()))
    assert saved.id == 10002 and not saved.enable and saved.debug_mode
    assert saved.password == old.password
    assert saved.post_info.access_token == old.post_info.access_token
    assert saved.extends == old.extends
    assert host.account_path.with_name('account.json.webui-backup').is_file()
    assert [host.Proc_info.control_queue.get_nowait().action for _ in range(3)] == [
        'call_account_update', 'call_system_stop_type_event', 'call_system_event']


def test_account_conflict_rejects_stale_gui_snapshot(client, host):
    body = client.get('/api/accounts').json
    next(iter(host.accounts.values())).debug_mode = True
    OlivOS.accountAPI.Account.save(str(host.account_path), host, host.accounts)
    worker = threading.Thread(target=commit_request, args=(host,))
    worker.start()
    response = client.post('/api/accounts', json=body)
    worker.join(timeout=2)
    assert response.status_code == 409
    assert next(iter(OlivOS.accountAPI.Account.load(str(host.account_path), host).values())).debug_mode


def test_account_reads_are_quiet_and_still_detect_external_changes(client, host, monkeypatch):
    messages = []
    monkeypatch.setattr(host, 'log', lambda *args: messages.append(args))
    before = host.account_path.read_bytes()
    initial = client.get('/api/accounts').json
    assert client.get('/api/accounts').json == initial
    changed = copy.deepcopy(host.accounts)
    next(iter(changed.values())).debug_mode = True
    OlivOS.accountAPI.Account.save(str(host.account_path), host, changed)
    latest = client.get('/api/accounts').json
    assert latest['revision'] != initial['revision'] and latest['account'][0]['debug']
    assert not next(iter(host.accounts.values())).debug_mode
    assert not messages and host.Proc_info.control_queue.empty()
    pageAPI._AccountReadLogger(host).log(3, 'warning')
    assert messages == [(3, 'warning')]
    host.account_path.write_text('broken', encoding='utf-8')
    assert client.get('/api/accounts').status_code == 400
    assert host.account_path.read_text(encoding='utf-8') == 'broken'
    host.account_path.write_bytes(before)


@pytest.mark.parametrize('system, version, expected', [
    ('Windows', OlivOS.infoAPI.OlivOS_SVN + 1, 'available'),
    ('Windows', OlivOS.infoAPI.OlivOS_SVN, 'latest'),
    ('Windows', None, 'error'),
    ('Windows', 'invalid', 'error'),
    ('Linux', None, 'unsupported'),
    ('Darwin', None, 'unsupported'),
])
def test_update_checks_report_the_actual_result(host, monkeypatch, system, version, expected):
    updater = OlivOS.updateAPI
    monkeypatch.setattr(updater.platform, 'system', lambda: system)
    monkeypatch.setattr(updater.platform, 'architecture', lambda: ('64bit', ''))
    monkeypatch.setattr(updater.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(updater, 'clear_bat', lambda: None)
    monkeypatch.setattr(updater, 'releaseDir', lambda path: None)
    monkeypatch.setattr(updater, 'GETHttpJson2Dict', lambda url: None if version is None else {
        'version': {'OlivOS': {'64bit': {'svn': version, 'path': 'https://example.invalid/update.zip'}}},
    })
    before = time.time()
    assert updater.OlivOSUpdateGet(host, flagChackOnly=True, control_queue=host.Proc_info.control_queue) is False
    packets = []
    while not host.Proc_info.control_queue.empty():
        packets.append(host.Proc_info.control_queue.get_nowait())
    result = packets[-1]
    assert result.key['target']['type'] == 'webUI'
    assert result.key['data']['action'] == 'update_check_result'
    assert result.key['data']['status'] == expected
    assert result.key['data']['started_at'] >= before
    host.consume(result)
    event = host.snapshot('events')[-1]
    assert event['type'] == 'update_check_result' and event['status'] == expected
    assert host.update_available == (expected == 'available')


def test_validation_rejects_malformed_accounts_without_writes(client, host):
    before = host.account_path.read_bytes()
    body = client.get('/api/accounts').json
    for invalid in [[], {}, {'account': []}, dict(body, account=[{'server': []}])]:
        assert client.post('/api/accounts', json=invalid).status_code == 400
    body['account'][0]['server']['port'] = 'invalid'
    assert client.post('/api/accounts', json=body).status_code == 400
    assert host.account_path.read_bytes() == before
    assert host.Proc_info.control_queue.empty()


def test_qsign_removal_keeps_the_right_masked_key(client, host):
    old = next(iter(host.accounts.values()))
    body = client.get('/api/accounts').json
    row = body['account'][0]
    row['extends']['qsign-server'] = [dict(row['extends']['qsign-server'][1], _source_index=1)]
    restored = next(iter(pageAPI.parse_accounts(body, host.accounts).values()))
    assert restored.extends['qsign-server'] == [old.extends['qsign-server'][1]]


def test_native_default_id_generation_is_preserved():
    token = secrets.token_urlsafe(16)
    fields = OlivOS.accountAPI.normalizeAccountFields({
        'id': '', 'password': '', 'server_auto': 'True', 'server_type': 'websocket', 'host': '',
        'port': '', 'access_token': token, 'platform_sdk': 'discord_link', 'platform_platform': 'discord',
        'platform_model': 'default',
    })
    import hashlib
    assert fields['id'] == int(hashlib.md5(token.encode()).hexdigest(), 16)


def test_logs_filter_tail_and_bounded_replay(client, host):
    path = host.root / 'logfile/OlivOS_logfile_unity.log'
    path.parent.mkdir()
    path.write_text('[2026-09-18 10:00:00] - [INFO] - hello\n'
                    '[2026-09-18 10:00:01] - [ERROR] - failure\ntraceback\n', encoding='utf-8')
    response = client.get('/api/logs?level=4&tail=2')
    assert [item['text'] for item in response.json['items']] == ['failure', 'traceback']
    assert client.get('/api/logs?level=99').status_code == 400
    for i in range(host.limit + 30):
        send(host, {'action': 'logger', 'event': 'log', 'data': {'data': {'log_level': 2}, 'str': str(i)}})
    assert len(host.snapshot('logs')) == host.limit
    for i in range(host.limit + 30):
        host.publish('logs', {'level': 0, 'text': f'debug-{i}'})
    assert len(host.snapshot('logs', level=2)) == host.limit
    assert all(item['level'] == 0 for item in host.snapshot('logs'))
    response = client.get('/api/logs?level=2&tail=5').json
    assert len(response['items']) == 5 and all(item['level'] == 2 for item in response['items'])
    host.publish('logs', {'level': 3, 'text': 'warning'})
    host.publish('logs', {'level': 5, 'text': 'fatal'})
    response = client.get('/api/logs?level=2,3').json
    assert len(response['items']) == host.limit
    assert {item['level'] for item in response['items']} == {2, 3}
    assert response['items'][-1]['text'] == 'warning'
    assert client.get('/api/logs?level=2,99').status_code == 400
    assert [item['text'] for item in pageAPI.log_tail(path, 5, (2,))] == ['hello']
    assert [item['text'] for item in pageAPI.log_tail(path, 5, (2, 4))] == ['hello', 'failure', 'traceback']


@pytest.mark.parametrize('model', list(serverAPI.TERMINAL_TYPES))
def test_all_six_terminal_inputs(client, host, model):
    bot_hash = next(iter(host.accounts))
    send(host, {'action': model, 'event': 'init', 'hash': bot_hash})
    host.terminal_input(model, bot_hash, {'data': 'test'})
    packet = host.Proc_info.control_queue.get_nowait()
    assert packet.key['target'] == {'type': serverAPI.TERMINAL_TYPES[model], 'hash': bot_hash, 'fliter': 'rx_only'}
    assert packet.key['data']['action'] == 'input'
    if model == 'virtual_terminal':
        assert packet.key['data']['user_conf'] == {}
    assert client.get('/api/terminals').json['items'][0]['hash'] == bot_hash
    host.accounts[bot_hash].enable = False
    with pytest.raises(ValueError):
        host.terminal_input(model, bot_hash, {'data': 'test'})


def test_qrcode_private_and_path_guard(client, host):
    bot_hash = next(iter(host.accounts))
    image = host.root / 'conf/qr.png'
    image.write_bytes(base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg=='))
    send(host, {'action': 'napcat', 'event': 'qrcode', 'hash': bot_hash, 'path': str(image)})
    endpoint = f'/api/terminal/napcat/{bot_hash}/qrcode'
    assert client.get(endpoint).status_code == 200
    assert host.app.test_client().get(endpoint).status_code == 401
    send(host, {'action': 'napcat', 'event': 'qrcode', 'hash': bot_hash, 'path': '../outside.png'})
    assert host.terminals[('napcat', bot_hash)]['qrcode'] == str(image)


def install_plugin(host):
    root = host.root / 'plugin/app/folder/demo'
    (root / 'webui').mkdir(parents=True)
    (root / 'webui/index.html').write_text('<h1>demo</h1>', encoding='utf-8')
    (root / 'app.json').write_text('{}', encoding='utf-8')
    host.plugin_roots = {'demo': str(root)}
    host.plugins = {'demo': ['Demo', '1', 'Author', [['Menu', 'demo', 'open']], 'info', 'folder', 1]}
    host.plugin_pages = [{'title': 'Demo', 'type': 'iframe', 'path': 'webui/index.html', 'namespace': 'demo'}]
    host.plugin_webui_paths['demo'] = ['webui/']
    return root


def test_plugin_mount_login_traversal_and_menu_roundtrip(client, host):
    install_plugin(host)
    assert client.get('/plugin/demo/webui/index.html').status_code == 401
    session = client.post('/api/login').json['session']
    page = client.get('/plugin/demo/webui/index.html')
    assert page.status_code == 200
    csp = page.headers['Content-Security-Policy']
    assert 'sandbox allow-scripts' in csp
    # 常规浏览器能力都要放行，避免「缺一个补一个」
    for token in ('allow-forms', 'allow-modals', 'allow-downloads', 'allow-popups',
                  'allow-popups-to-escape-sandbox'):
        assert token in csp, token
    # 沙箱底线：插件页与宿主 WebUI 同源，绝不能给 allow-same-origin
    assert 'allow-same-origin' not in csp
    assert client.get('/plugin/demo/../app.json').status_code == 404
    assert client.get('/plugin/demo/%2e%2e/app.json').status_code == 404
    response = client.post('/api/plugin_event', json={
        'namespace': 'demo', 'event': 'read', 'session': session, 'request_id': 'r1', 'payload': {'value': 4}})
    assert response.status_code == 202
    packet = host.Proc_info.control_queue.get_nowait()
    event = OlivOS.API.Event(packet, Proc=OlivOS.pluginAPI.shallow(control_queue=host.Proc_info.control_queue))
    event.plugin_info.update(namespace='demo', control_queue=host.Proc_info.control_queue)
    assert event.data.payload == {'value': 4}
    assert event.send('webui', 'r1', {'value': 5}) is True
    host.consume(host.Proc_info.control_queue.get_nowait())
    assert host.snapshot('events', session=session)[0]['payload'] == {'value': 5}
    assert host.snapshot('events', session='another-browser') == []
    assert client.post('/api/logout', json={'session': session}).status_code == 200
    assert client.get('/plugin/demo/webui/index.html').status_code == 401


def test_plugin_folder_open_uses_system_file_manager(client, host, monkeypatch):
    opened = []
    monkeypatch.setattr(pageAPI, 'open_directory', opened.append)
    assert host.app.test_client().post('/api/plugins/open').status_code == 401
    directory = host.root / 'plugin/app'
    assert client.post('/api/plugins/open').status_code == 400
    assert opened == []
    directory.mkdir(parents=True)
    response = client.post('/api/plugins/open')
    assert response.status_code == 200
    assert Path(response.json['path']) == directory
    assert opened == [directory]


def test_plugin_folder_open_reports_opener_failure(client, host, monkeypatch):
    """打开失败时必须回传真实原因，而不是落到「无法读取文件」这个通用处理器。"""
    def boom(_path):
        raise OSError('运行 OlivOS 的环境没有可用的桌面会话，无法打开文件管理器')

    monkeypatch.setattr(pageAPI, 'open_directory', boom)
    (host.root / 'plugin/app').mkdir(parents=True, exist_ok=True)
    response = client.post('/api/plugins/open')
    assert response.status_code == 500
    assert '桌面会话' in response.json['error']


def test_plugin_list_preserves_gui_and_adds_webui(host):
    shallow = OlivOS.pluginAPI.shallow(control_queue=host.Proc_info.control_queue)
    shallow.plugin_models_call_list = ['demo']
    shallow.plugin_models_dict = {'demo': {
        'name': 'Demo', 'namespace': 'demo', 'author': 'Author', 'version': '1',
        'svn': 1, 'priority': 1, 'info': '', 'menu_config': [],
        'webui_config': [{'title': 'Demo', 'type': 'iframe', 'path': 'webui/index.html'}],
        'webui_root': str(host.root / 'plugin/app/demo')}}
    shallow.sendPluginList()
    packet = host.Proc_info.control_queue.get_nowait()
    assert len(packet.key['data']['data']['shallow_plugin_data_dict']['demo']) == 7
    serverAPI.forward_packet(packet, {host.Proc_name: host})
    host.consume(host.Proc_info.rx_queue.get_nowait())
    assert host.plugin_pages[0]['namespace'] == 'demo'
    assert not host.snapshot('events')[-1]['ready']
    shallow.Proc_data['webui_load_started'] = time.time()
    shallow.sendPluginList(ready=True)
    while not host.Proc_info.control_queue.empty():
        host.consume(host.Proc_info.control_queue.get_nowait())
    event = host.snapshot('events')[-1]
    assert event['ready'] and event['started_at'] == shallow.Proc_data['webui_load_started']


def test_packaging_and_shallow_config():
    root = Path(__file__).resolve().parents[1]
    for name, encoded in staticData.FILES.items():
        source = root / 'OlivOS/webUI/static' / name
        expected = source.read_bytes() if source.suffix == '.png' else source.read_text(encoding='utf-8').encode()
        assert base64.b64decode(encoded) == expected
    user_config = {'system': {}, 'models': {}}
    assert 'OlivOS_webUI' not in user_config.get('models', {})
    patched = OlivOS.bootAPI.get_patch_config(copy.deepcopy(OlivOS.bootDataAPI.default_Conf), user_config)
    model = patched['models']['OlivOS_webUI']
    assert model['type'] == 'webUI'
    assert model['enable'] is True
    assert model['server'] == serverAPI.DEFAULT_SERVER
    assert model['name'] in patched['system']['init'] and model['rx_queue'] in patched['queue']


@pytest.mark.skipif(os.name != 'nt', reason='Windows tray menu')
def test_tray_default_opens_webui(monkeypatch):
    from types import SimpleNamespace

    calls = []
    root = SimpleNamespace(
        webui_root=str(Path.cwd()),
        UIData={'shallow_menu_list': [['打开终端', lambda: calls.append('terminal')]]},
        openWebUI=lambda: calls.append('webui'),
    )
    monkeypatch.setattr(serverAPI, 'browser_url', lambda root: 'http://127.0.0.1:20480')
    tray = OlivOS.nativeWinUIAPI.shallow('test', '', root)
    tray.refreshData()
    menu = tray.UIObject['shallow_menu']
    assert [item.text for item in menu if item.default] == ['打开 WebUI']
    menu(None)
    assert calls == ['webui']
    terminal = next(item for item in menu if item.text == '打开终端')
    assert not terminal.default
    terminal(None)
    assert calls == ['webui', 'terminal']
    monkeypatch.setattr(serverAPI, 'browser_url', lambda root: None)
    tray.refreshData()
    assert [item.text for item in tray.UIObject['shallow_menu']] == ['打开终端']


@pytest.fixture
def live_host(host):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        host.config['port'] = listener.getsockname()[1]
    thread = threading.Thread(target=host.run, daemon=True)
    thread.start()
    assert host.ready.wait(5) and host.error is None
    yield host
    host.on_terminate()
    thread.join(timeout=5)
    assert not thread.is_alive()


def test_busy_port_advances_and_tray_uses_actual_port(host, monkeypatch):
    import urllib.request
    import subprocess
    import sys

    working_dir = host.root / 'other-working-directory'
    working_dir.mkdir()
    monkeypatch.chdir(working_dir)

    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1', 0))
        occupied.listen()
        requested = occupied.getsockname()[1]
        host.config['port'] = requested
        worker = threading.Thread(target=host.run, daemon=True)
        worker.start()
        try:
            assert host.ready.wait(5) and host.error is None
            assert host.config['port'] > requested
            assert Path.cwd() != host.root
            assert serverAPI.browser_url(host.root) == f"http://127.0.0.1:{host.config['port']}"
            with urllib.request.urlopen(serverAPI.browser_url(host.root) + '/api/health', timeout=3) as response:
                assert json.load(response) == {'status': 'OK'}
            result = subprocess.run([
                sys.executable, '-c',
                'import sys; from OlivOS.webUI.serverAPI import browser_url; print(browser_url(sys.argv[1]))',
                str(host.root),
            ], capture_output=True, text=True, timeout=15, check=True)
            assert result.stdout.strip() == serverAPI.browser_url(host.root)
        finally:
            host.on_terminate()
            worker.join(timeout=5)
        assert not worker.is_alive()
        assert not host.listen_path.exists()


def test_listener_discovery_rejects_stale_records(host, monkeypatch):
    from types import SimpleNamespace

    host.listen_path.parent.mkdir(parents=True, exist_ok=True)
    (host.root / 'conf/config.json').write_text(json.dumps({
        'models': {'OlivOS_webUI': {'server': {'port': 23456}}},
    }), encoding='utf-8')
    record = {'host': '127.0.0.1', 'port': 23457, 'pid': 12345, 'created': 100.0}
    host.listen_path.write_text(json.dumps(record), encoding='utf-8')
    process = SimpleNamespace(create_time=lambda: 101.0, connections=lambda **kwargs: [])
    monkeypatch.setattr(serverAPI.psutil, 'Process', lambda pid: process)
    assert serverAPI.browser_url(host.root) == 'http://127.0.0.1:23456'
    process.create_time = lambda: 100.0
    assert serverAPI.browser_url(host.root) == 'http://127.0.0.1:23456'
    process.connections = lambda **kwargs: [SimpleNamespace(
        status=serverAPI.psutil.CONN_LISTEN, laddr=SimpleNamespace(port=23457))]
    assert serverAPI.browser_url(host.root) == 'http://127.0.0.1:23457'

    def dead(pid):
        raise serverAPI.psutil.NoSuchProcess(pid)
    monkeypatch.setattr(serverAPI.psutil, 'Process', dead)
    assert serverAPI.browser_url(host.root) == 'http://127.0.0.1:23456'
    host.listen_path.write_text('{', encoding='utf-8')
    assert serverAPI.browser_url(host.root) == 'http://127.0.0.1:23456'


def test_bind_errors_other_than_busy_do_not_advance(host, monkeypatch):
    from unittest.mock import AsyncMock
    import errno

    start = AsyncMock(side_effect=OSError(errno.EACCES, 'test permission failure'))
    monkeypatch.setattr(serverAPI.web.TCPSite, 'start', start)
    host.run()
    assert host.error and start.call_count == 1
    assert not host.listen_path.exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows socket reset regression')
def test_webui_disconnects_do_not_break_the_listener(live_host):
    import struct
    import urllib.request

    host = live_host
    assert isinstance(host.loop, asyncio.SelectorEventLoop)
    errors = []
    host.loop.call_soon_threadsafe(host.loop.set_exception_handler, lambda loop, context: errors.append(context))
    for index in range(20):
        with socket.create_connection(('127.0.0.1', host.config['port']), timeout=3) as connection:
            key = base64.b64encode(os.urandom(16)).decode()
            request = (f"GET /ws/logs HTTP/1.1\r\nHost: 127.0.0.1:{host.config['port']}\r\n"
                       'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
                       f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Protocol: olivos, token.{host.token}\r\n\r\n')
            connection.sendall(request.encode())
            assert connection.recv(4096).startswith(b'HTTP/1.1 101')
            host.publish('logs', {'text': f'reset-{index}', 'level': 2})
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('HH', 1, 0))
        with urllib.request.urlopen(f"http://127.0.0.1:{host.config['port']}/api/health", timeout=3) as response:
            assert response.status == 200
    assert not errors, f'{len(errors)} event loop errors after connection resets'


@pytest.mark.parametrize('browser_login', [False, True])
def test_live_http_ws_auth_history_and_stdin(live_host, browser_login):
    host = live_host
    bot_hash = next(iter(host.accounts))
    send(host, {'action': 'virtual_terminal', 'event': 'init', 'hash': bot_hash})
    host.publish('logs', {'text': 'history', 'level': 2})

    async def scenario():
        url = f"http://127.0.0.1:{host.config['port']}"
        async with aiohttp.ClientSession() as client:
            async with client.get(url + '/api/health') as response:
                assert response.status == 200 and (await response.json())['status'] == 'OK'
            async with client.post(url + '/api/login', headers={'X-Auth-Token': host.token}) as response:
                assert response.status == 200
            host.publish('events', {'type': 'open_page', 'url': 'https://example.invalid/old'})
            async with client.post(url + '/api/login', headers={'X-Auth-Token': host.token}) as response:
                login_state = await response.json()
            token = login_state['browser_token'] if browser_login else host.token
            events = url + f"/ws/events?session={login_state['session']}&since={login_state['cursor']}"
            async with client.ws_connect(events, protocols=['olivos', 'token.' + token]) as ws:
                assert (await ws.receive_json(timeout=2))['items'] == []
                host.publish('events', {'type': 'plugins'})
                assert [item['type'] for item in (await ws.receive_json(timeout=2))['items']] == ['plugins']
            with pytest.raises(aiohttp.WSServerHandshakeError):
                await client.ws_connect(url + '/ws/logs')
            with pytest.raises(aiohttp.WSServerHandshakeError):
                await client.ws_connect(url + '/ws/logs', protocols=['olivos', 'token.' + token],
                                        origin='https://foreign.invalid')
            async with client.ws_connect(url + '/ws/logs', protocols=['olivos', 'token.' + token]) as ws:
                first = await ws.receive_json(timeout=2)
                assert first['type'] == 'history' and first['items'][0]['text'] == 'history'
                host.publish('logs', {'text': 'live', 'level': 3})
                assert (await ws.receive_json(timeout=2))['items'][0]['text'] == 'live'
            endpoint = url + '/ws/terminal/virtual_terminal/' + bot_hash
            async with client.get(url + '/api/logs?level=2,3', headers={'X-Auth-Token': token}) as response:
                history = await response.json()
            host.publish('logs', {'text': 'ignored-debug', 'level': 0})
            host.publish('logs', {'text': 'new-info', 'level': 2})
            filtered = url + '/ws/logs?level=2,3&since=' + str(history['cursor'])
            async with client.ws_connect(filtered, protocols=['olivos', 'token.' + token]) as ws:
                assert [item['text'] for item in (await ws.receive_json(timeout=2))['items']] == ['new-info']
                for index in range(host.limit + 30):
                    host.publish('logs', {'text': f'ignored-{index}', 'level': 0})
                host.publish('logs', {'text': 'new-warning', 'level': 3})
                assert [item['text'] for item in (await ws.receive_json(timeout=2))['items']] == ['new-warning']
            async with client.ws_connect(endpoint, protocols=['olivos', 'token.' + token]) as ws:
                assert (await ws.receive_json(timeout=2))['type'] == 'history'
                await ws.send_json({'data': 'hello'})
                for _ in range(50):
                    if not host.Proc_info.control_queue.empty():
                        break
                    await asyncio.sleep(.02)
                packet = host.Proc_info.control_queue.get_nowait()
                assert packet.key['data']['data'] == 'hello'
                await ws.send_str('not json')
                assert (await ws.receive_json(timeout=2))['type'] == 'error'
    asyncio.run(scenario())
