import copy
import json
import queue
from concurrent.futures import ThreadPoolExecutor

import pytest

import OlivOS
from OlivOS.webUI import pageAPI
from webui_test_support import make_host


ACCOUNTS = '/api/accounts'
PREVIEW = ACCOUNTS + '/import/preview'
PASSWORD = 'sample-submitted-password'


def import_row(account_id=42, **changes):
    return {
        'id': account_id, 'password': PASSWORD,
        'sdk_type': 'terminal_link', 'platform_type': 'terminal', 'model_type': 'default',
        'server': {'auto': True, 'type': 'websocket'},
        **changes,
    }


@pytest.fixture
def host(tmp_path):
    bots = {}
    for account_id in (10001, 10002, 10003):
        bot = OlivOS.API.bot_info_T(
            id=account_id, password='sample-local-password', server_auto=True, server_type='websocket',
            host='NONEED', port=0, access_token='sample-local-token',
            platform_sdk='terminal_link', platform_platform='terminal', platform_model='default',
        )
        bot.extends = {'app_secret': 'sample-local-secret', 'settings': {'keep': 'local'}}
        bots[bot.hash] = bot
    service = make_host(root_path=tmp_path, control_queue=queue.Queue(), bot_info_dict=bots)
    service.account_path.parent.mkdir(parents=True, exist_ok=True)
    OlivOS.accountAPI.Account.save(str(service.account_path), service, bots)
    yield service
    service.on_terminate()


@pytest.fixture
def client(host):
    client = host.app.test_client()
    client.environ_base['HTTP_X_AUTH_TOKEN'] = host.test_token
    return client


def post_and_commit(client, host, body):
    with ThreadPoolExecutor(max_workers=1) as worker:
        response = worker.submit(client.post, ACCOUNTS, json=body)
        packet = host.Proc_info.control_queue.get(timeout=5)
        assert packet.action == 'webui_accounts'
        host.commit_accounts(packet.key['request_id'], {})
        return response.result(timeout=5)


def test_preview_requires_authentication(host):
    response = host.app.test_client().post(PREVIEW, json=import_row())
    assert response.status_code == 401
    assert response.headers['Cache-Control'] == 'no-store'
    assert PASSWORD not in response.get_data(as_text=True)


def test_preview_does_not_read_or_mutate_local_accounts(client, host, monkeypatch):
    def forbid(*args, **kwargs):
        pytest.fail('导入预览不应读取或提交本地账号配置')

    monkeypatch.setattr(pageAPI, 'load_accounts', forbid)
    monkeypatch.setattr(host, 'submit_accounts', forbid)
    original = pageAPI.account_response(host.accounts)
    original_hash = original['account'][0]['hash']
    host.account_path.write_bytes(b'broken config')
    response = client.post(PREVIEW, json=[
        import_row(10001, hash=original_hash),
        import_row(10001, hash=original_hash, password=pageAPI.MASK),
    ])
    assert response.status_code == 200
    valid, invalid = response.json['items']
    assert valid['valid'] and valid['key'] == original_hash
    assert valid['account']['password'] == PASSWORD
    assert not invalid['valid'] and invalid['account'] is None
    assert 'sample-local-' not in response.get_data(as_text=True)
    assert host.account_path.read_bytes() == b'broken config'
    assert not host.account_path.with_name('account.json.webui-backup').exists()
    assert pageAPI.account_response(host.accounts) == original
    assert host.Proc_info.control_queue.empty() and not host.pending


@pytest.mark.parametrize('wrapped', [False, True], ids=['direct', 'payload'])
@pytest.mark.parametrize('shape', ['standard', 'array', 'single'])
def test_preview_accepts_shapes_and_normalizes_accounts(client, shape, wrapped):
    row = import_row('00042')
    payload = {'standard': {'account': [row]}, 'array': [row], 'single': row}[shape]
    response = client.post(PREVIEW, json={'payload': payload} if wrapped else payload)
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.json == {
        'items': [{
            'source_index': 0, 'valid': True, 'error': None,
            'key': OlivOS.API.getBotHash(42, 'terminal_link', 'terminal'),
            'account': {
                'id': '42', 'password': PASSWORD,
                'sdk_type': 'terminal_link', 'platform_type': 'terminal', 'model_type': 'default',
                'server': {'auto': True, 'type': 'websocket', 'host': 'NONEED', 'port': 0,
                           'access_token': 'NONEED'},
                'extends': {}, 'enable': True, 'debug': False,
            },
        }],
        'batch_duplicates': 0,
    }


@pytest.mark.parametrize('index', [-2, {'malformed': 'index'}, pageAPI.MASK], ids=['negative', 'object', 'masked'])
def test_preview_strips_external_hash_and_qsign_source_index(client, index):
    servers = [{'addr': 'http://localhost:5678', 'key': 'sample-qsign-key'}]
    row = import_row(hash=pageAPI.MASK, extends={'qsign-server': [dict(servers[0], _source_index=index)]})
    response = client.post(PREVIEW, json=row)
    assert response.status_code == 200
    item, = response.json['items']
    assert item['valid']
    assert item['key'] == OlivOS.API.getBotHash(42, 'terminal_link', 'terminal')
    assert 'hash' not in item['account']
    assert item['account']['extends']['qsign-server'] == servers


@pytest.mark.parametrize('payload', [False, 'string', [], {'account': []}, {'account': {}}, {'payload': None}],
                         ids=['boolean', 'string', 'empty-array', 'empty-account', 'bad-account', 'null-payload'])
def test_preview_rejects_invalid_top_level_structures(client, payload):
    response = client.post(PREVIEW, json=payload)
    assert response.status_code == 400
    assert response.json['error']
    assert response.headers['Cache-Control'] == 'no-store'


def test_preview_rejects_malformed_json(client):
    response = client.post(PREVIEW, data='{"account":[', content_type='application/json')
    assert response.status_code == 400
    assert response.json['error']


@pytest.mark.parametrize('row,error', [
    (False, '账号必须为对象'),
    (import_row(sdk_type=[]), 'SDK、平台与型号必须为字符串'),
    (import_row(sdk_type={}), 'SDK、平台与型号必须为字符串'),
    (import_row(platform_type=[]), 'SDK、平台与型号必须为字符串'),
    (import_row(platform_type={}), 'SDK、平台与型号必须为字符串'),
    (import_row(platform_type='unsupported'), 'SDK、平台与型号组合无效'),
    (import_row(model_type=[]), 'SDK、平台与型号必须为字符串'),
    (import_row(enable=1), '必须为布尔值'),
    (import_row(server=[]), 'server 必须为对象'),
    (import_row(server={'type': {}, 'auto': True}), '连接类型无效'),
    (import_row(server={'type': 'websocket', 'host': 'NONEED', 'port': 65536, 'access_token': 'NONEED'}),
     '端口应在 0–65535 之间'),
    (import_row(extends=[]), 'extends 必须为 JSON 对象'),
    (import_row(extends={'qsign-server': [{'key': ['bad']}]}), '签名服务器必须为'),
    (import_row('', sdk_type='telegram_poll', platform_type='telegram',
                server={'type': 'post', 'access_token': 1234}), '账号字段格式无效'),
    (import_row('\ud800'), '账号 ID 格式无效'),
], ids=['non-object', 'sdk-array', 'sdk-object', 'platform-array', 'platform-object', 'invalid-combination',
        'model-array', 'flag', 'server-array', 'connection-type', 'port-range', 'extends-array', 'qsign-key',
        'telegram-token', 'invalid-id-encoding'])
def test_preview_isolates_invalid_rows(client, row, error):
    response = client.post(PREVIEW, json=[import_row(1), row, import_row(2)])
    assert response.status_code == 200
    first, invalid, last = response.json['items']
    assert first['source_index'] == 0 and first['valid'] and first['account']['id'] == '1'
    assert last['source_index'] == 2 and last['valid'] and last['account']['id'] == '2'
    assert invalid['source_index'] == 1 and not invalid['valid']
    assert invalid['key'] is None and invalid['account'] is None
    assert error in invalid['error'] and PASSWORD not in invalid['error']
    assert response.json['batch_duplicates'] == 0


@pytest.mark.parametrize('row', [
    import_row(pageAPI.MASK),
    import_row(password=pageAPI.MASK),
    import_row(server={'type': 'websocket', 'host': pageAPI.MASK}),
    import_row(server={'type': 'websocket', 'access_token': pageAPI.MASK}),
    import_row(extends={'qsign-server': [{'addr': 'http://localhost:1234', 'key': pageAPI.MASK}]}),
    import_row(extends={'custom': {'array': [{'value': pageAPI.MASK}]}}),
    import_row(unknown_field={'nested': pageAPI.MASK}),
    import_row(sdk_type='mhyVila_link', platform_type='mhyVila', model_type='public',
               server={'type': 'websocket', 'access_token': json.dumps(pageAPI.MASK)}),
], ids=['id', 'password', 'host', 'token', 'qsign-key', 'nested-extension', 'unknown-field', 'normalized-token'])
def test_preview_rejects_masked_submitted_values(client, row):
    response = client.post(PREVIEW, json=row)
    assert response.status_code == 200
    item, = response.json['items']
    assert not item['valid'] and item['account'] is None and item['key'] is None
    assert '脱敏占位符' in item['error']
    assert PASSWORD not in response.get_data(as_text=True)


def test_preview_keeps_last_valid_duplicate_in_source_order(client):
    response = client.post(PREVIEW, json=[
        import_row('00042'), None, import_row(42), import_row(7),
        import_row(42, debug=True), import_row(42, server=False), import_row(8),
    ])
    assert response.status_code == 200
    data = response.json
    assert data['batch_duplicates'] == 2
    assert [item['source_index'] for item in data['items']] == [1, 3, 4, 5, 6]
    assert [item['account']['id'] for item in data['items'] if item['valid']] == ['7', '42', '8']
    assert data['items'][2]['account']['debug']
    assert not data['items'][3]['valid']


def test_account_revision_tracks_row_order_but_not_field_order(host):
    original = pageAPI.account_revision(host.accounts)
    updated = copy.deepcopy(host.accounts)
    first = next(iter(updated.values()))
    first.extends = dict(reversed(list(first.extends.items())))
    assert pageAPI.account_revision(updated) == original
    assert pageAPI.account_revision(dict(reversed(list(updated.items())))) != original


def test_order_only_save_persists_and_reloads_in_requested_order(client, host):
    body = client.get(ACCOUNTS).json
    body['account'] = body['account'][::-1]
    expected_ids = [row['id'] for row in body['account']]
    expected_keys = [row['hash'] for row in body['account']]
    response = post_and_commit(client, host, body)
    assert response.status_code == 200, response.json
    assert response.json['revision'] != body['revision']
    assert response.json['account'] == body['account']
    assert list(host.accounts) == expected_keys
    stored = json.loads(host.account_path.read_text(encoding='utf-8'))
    assert [str(row['id']) for row in stored['account']] == expected_ids
    reloaded = OlivOS.accountAPI.Account.load(str(host.account_path), host, strict=True)
    assert list(reloaded) == expected_keys
    assert client.get(ACCOUNTS).json == response.json
    packets = [host.Proc_info.control_queue.get_nowait() for _ in range(3)]
    assert [packet.action for packet in packets] == [
        'call_account_update', 'call_system_stop_type_event', 'call_system_event',
    ]
    assert list(packets[0].key['data']) == expected_keys


def test_order_only_save_rejects_stale_revision(client, host):
    stale = client.get(ACCOUNTS).json
    reordered = dict(stale, account=stale['account'][::-1])
    saved = post_and_commit(client, host, reordered)
    assert saved.status_code == 200, saved.json
    for _ in range(3):
        host.Proc_info.control_queue.get_nowait()
    original = host.account_path.read_bytes()
    response = post_and_commit(client, host, stale)
    assert response.status_code == 409
    assert response.json['error']
    assert host.account_path.read_bytes() == original
    assert client.get(ACCOUNTS).json == saved.json
    assert host.Proc_info.control_queue.empty()


def test_save_replaces_import_overwrite_and_merges_regular_edit(client, host):
    body = client.get(ACCOUNTS).json
    to_replace, to_edit, _ = body['account']
    preview = client.post(PREVIEW, json=import_row(to_replace['id'], extends={'imported': True}))
    assert preview.status_code == 200
    item, = preview.json['items']
    assert item['valid']
    to_edit['extends'] = {'settings': {'edit': True}}
    to_edit['password'] = pageAPI.MASK
    body['account'][0] = dict(item['account'], hash=to_replace['hash'])
    body['replace_hashes'] = [to_replace['hash']]
    response = post_and_commit(client, host, body)
    assert response.status_code == 200, response.json
    assert response.json['account'][0]['extends'] == {'imported': True}
    loaded = OlivOS.accountAPI.Account.load(str(host.account_path), host, strict=True)
    assert loaded[to_replace['hash']].extends == {'imported': True}
    assert loaded[to_replace['hash']].post_info.access_token == 'NONEED'
    assert loaded[to_edit['hash']].extends == {
        'app_secret': 'sample-local-secret', 'settings': {'keep': 'local', 'edit': True},
    }
    assert loaded[to_edit['hash']].password == 'sample-local-password'


@pytest.mark.parametrize('replace_hashes', [None, 'hash', [None], [{}]], ids=['null', 'string', 'null-item', 'object'])
def test_save_rejects_invalid_replacement_sidecar(client, host, replace_hashes):
    body = client.get(ACCOUNTS).json
    response = client.post(ACCOUNTS, json=dict(body, replace_hashes=replace_hashes))
    assert response.status_code == 400
    assert 'replace_hashes' in response.json['error']
    assert host.Proc_info.control_queue.empty()


def test_save_import_overwrite_still_requires_existing_hash(client, host):
    body = client.get(ACCOUNTS).json
    body['account'][0]['hash'] = 'not-a-local-account'
    response = client.post(ACCOUNTS, json=dict(body, replace_hashes=['not-a-local-account']))
    assert response.status_code == 400
    assert '原账号不存在' in response.json['error']
    assert host.Proc_info.control_queue.empty()


@pytest.mark.parametrize('row', [
    import_row(True),
    import_row(None),
    import_row('   '),
    import_row(password=True),
    import_row(password=None),
    import_row(sdk_type='onebot', platform_type='qq', model_type='default',
               server={'auto': False, 'type': 'post', 'host': 12345, 'port': 5700, 'access_token': 'tok'}),
    import_row(sdk_type='onebot', platform_type='qq', model_type='default',
               server={'auto': False, 'type': 'post', 'host': 'http://127.0.0.1', 'port': True, 'access_token': 'tok'}),
    import_row(sdk_type='onebot', platform_type='qq', model_type='default',
               server={'auto': False, 'type': 'post', 'host': 'http://127.0.0.1', 'port': None, 'access_token': 'tok'}),
    import_row(sdk_type='onebot', platform_type='qq', model_type='default',
               server={'auto': False, 'type': 'post', 'host': 'http://127.0.0.1', 'port': 5700, 'access_token': True}),
    import_row(server={'auto': True, 'type': 'post', 'host': 'NONEED', 'port': 0, 'access_token': 'NONEED'}),
    import_row(sdk_type='dingtalk_link', platform_type='dingtalk', model_type='default',
               server={'auto': True, 'type': 'websocket'}),
    import_row(extends={'ws_path': 123}),
    import_row(extends={'http-path': False}),
], ids=[
    'bool-id', 'null-id', 'blank-id', 'bool-password', 'null-password',
    'int-host', 'bool-port', 'null-port', 'bool-token', 'bad-server-type-for-model',
    'dingtalk-missing-extends', 'non-str-ws-path', 'non-str-http-path',
])
def test_preview_and_save_reject_rows_incompatible_with_account_load(client, host, row):
    before = host.account_path.read_bytes()
    preview = client.post(PREVIEW, json=row)
    assert preview.status_code == 200
    item, = preview.json['items']
    assert not item['valid'] and item['account'] is None and item['error']
    assert PASSWORD not in item['error']

    body = client.get(ACCOUNTS).json
    body['account'].append(row)
    saved = client.post(ACCOUNTS, json=body)
    assert saved.status_code == 400
    assert saved.json['error']
    assert host.account_path.read_bytes() == before
    assert host.Proc_info.control_queue.empty()


def test_restore_rejects_boolean_qsign_source_index():
    with pytest.raises(ValueError, match='签名服务器来源索引无效'):
        pageAPI.restore([{'addr': 'http://localhost:1', 'key': 'k', '_source_index': True}], [])
