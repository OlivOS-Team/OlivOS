"""QQ 官方扫码绑定协议、内存会话和一次性交付；所有 HTTP 请求均由本地替身处理。"""

import base64
import io
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image

import OlivOS

qr = OlivOS.qqGuildv2QrBindAPI
TASK = 'offline-task/a&b=1'
SECRET = '仅用于测试的 AppSecret'


def reply(data):
    return SimpleNamespace(status_code=200, json=lambda: {'retcode': 0, 'msg': 'success', 'data': data})


@pytest.fixture
def post(monkeypatch):
    fake = Mock(return_value=reply({'task_id': TASK}))
    monkeypatch.setattr(qr.requests, 'post', fake)
    return fake


@pytest.fixture
def manager(post):
    mgr = qr.QrBindManager()
    yield mgr
    mgr.close()


def request_key(post):
    encoded = post.call_args_list[0][1]['json']['key']
    return base64.b64decode(encoded, validate=True)


def encrypted(key, plaintext=None):
    nonce = os.urandom(12)
    if plaintext is None:
        plaintext = SECRET.encode()
    return base64.b64encode(nonce + AESGCM(key).encrypt(nonce, plaintext, None)).decode('ascii')


def completion(post):
    return {'status': 2, 'bot_appid': 12345, 'bot_encrypt_secret': encrypted(request_key(post)),
            'user_openid': 'offline-openid'}


def gate(fn, started, release):
    def blocked(*args, **kwargs):
        started.set()
        assert release.wait(5), '扫码操作阻塞了取消或其他会话'
        return fn(*args, **kwargs)
    return blocked


def test_create_posts_fresh_base64_aes256_key_and_json_headers(manager, post):
    first = manager.create_session()
    second = manager.create_session()
    assert first['bind_id'] != second['bind_id']
    assert first['expires_in'] == 300 and first['poll_interval'] == 2
    assert set(first) == {'bind_id', 'qr_url', 'expires_in', 'poll_interval'}
    keys = []
    for args, kwargs in post.call_args_list:
        assert args == ('https://q.qq.com/lite/create_bind_task',)
        assert kwargs['timeout'] == 10 and kwargs['allow_redirects'] is False
        assert kwargs['headers'] == {'Accept': 'application/json', 'Content-Type': 'application/json',
                                     'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA}
        assert set(kwargs['json']) == {'key'}
        key = kwargs['json']['key']
        assert len(key) == 44 and len(base64.b64decode(key, validate=True)) == 32
        assert key not in repr(first) and key not in repr(second)
        keys.append(key)
    assert len(set(keys)) == 2


@pytest.mark.parametrize('source', ['', '本地来源/a+b&c=#d'])
def test_qr_url_quotes_each_query_value(manager, source):
    url = urlsplit(manager.create_session(source=source)['qr_url'])
    assert (url.scheme, url.netloc, url.path, url.fragment) == ('https', 'q.qq.com', '/qqbot/openclaw/connect.html', '')
    expected = {'task_id': [TASK], '_wv': ['2']}
    if source:
        expected['source'] = [source]
    assert parse_qs(url.query) == expected


@pytest.mark.parametrize('kind, expected_status', [
    ('timeout', 504), ('connection', 502), ('html', 502), ('redirect', 502), ('retcode', 502), ('missing-task', 502),
])
def test_creation_failure_is_sanitized_and_releases_slot(post, kind, expected_status):
    mgr = qr.QrBindManager(max_sessions=1)
    upstream = 'fake-sensitive-upstream'
    bad_response = {
        'timeout': qr.requests.Timeout(upstream),
        'connection': qr.requests.ConnectionError(upstream),
        'html': SimpleNamespace(status_code=200, json=Mock(side_effect=ValueError(upstream))),
        'redirect': SimpleNamespace(status_code=307),
        'retcode': SimpleNamespace(status_code=200, json=lambda: {'retcode': 30001, 'msg': upstream}),
        'missing-task': reply({'msg': upstream}),
    }
    post.side_effect = [bad_response[kind], reply({'task_id': TASK})]
    try:
        with pytest.raises(qr.QrBindError) as error:
            mgr.create_session()
        assert error.value.http_status == expected_status
        assert upstream not in str(error.value) and upstream not in repr(error.value)
        assert post.call_args[1]['json']['key'] not in str(error.value)
        assert error.value.__context__ is None
        assert mgr.create_session()['bind_id']
    finally:
        mgr.close()


@pytest.mark.parametrize('status, name', [(0, 'NONE'), (1, 'PENDING'), (3, 'EXPIRED')])
def test_poll_status_ignores_placeholder_credentials(manager, post, status, name):
    bind_id = manager.create_session()['bind_id']
    session = manager._sessions[bind_id]
    post.return_value = reply({'status': status, 'bot_appid': '0', 'bot_encrypt_secret': '', 'user_openid': ''})
    result = manager.poll_session(bind_id)
    assert qr.QrBindStatus(result['status']).name == name
    assert result['status'] == status and result['status_text'] and 'credentials' not in result
    args, kwargs = post.call_args
    assert args == ('https://q.qq.com/lite/poll_bind_result',)
    assert kwargs['json'] == {'task_id': TASK} and kwargs['timeout'] == 10
    if status == qr.QrBindStatus.EXPIRED:
        assert not any(session.aes_key_bytes)
        post.reset_mock()
        assert manager.poll_session(bind_id)['status'] == 3
        post.assert_not_called()
    else:
        assert any(session.aes_key_bytes)


@pytest.mark.parametrize('status', [-1, 4, None, True, '2', 2.0, []])
def test_unknown_status_is_not_mistaken_for_completion(manager, post, status):
    bind_id = manager.create_session()['bind_id']
    post.return_value = reply({'status': status})
    with pytest.raises(qr.QrBindError, match='状态'):
        manager.poll_session(bind_id)


def test_completed_secret_is_authenticated_decoded_and_consumed_once(manager, post):
    bind_id = manager.create_session()['bind_id']
    session = manager._sessions[bind_id]
    key = session.aes_key_bytes
    assert repr(bytes(key)) not in repr(session) and TASK not in repr(session)
    data = completion(post)
    post.return_value = reply(data)
    result = manager.poll_session(bind_id)
    assert qr.QrBindStatus(result['status']).name == 'COMPLETED'
    assert result['credentials'] == [{'app_id': '12345', 'app_secret': SECRET, 'user_openid': 'offline-openid'}]
    assert result['status_text'] and data['bot_encrypt_secret'] not in repr(result) and SECRET not in repr(result)
    assert bytes(key) == bytes(32) and session.consumed
    assert manager.poll_session(bind_id)['status'] == 3 and post.call_count == 2
    with pytest.raises(KeyError):
        manager.get_qr_png(bind_id)


def test_multiple_encrypted_credentials_are_normalized_in_order(manager, post):
    bind_id = manager.create_session()['bind_id']
    key = request_key(post)
    post.return_value = reply({'status': 2, 'user_openid': 'owner', 'credentials': [
        {'bot_appid': '17', 'bot_encrypt_secret': encrypted(key, b'first')},
        {'bot_appid': 18, 'bot_encrypt_secret': encrypted(key, b'second'), 'user_openid': 'other'},
    ]})
    assert manager.poll_session(bind_id)['credentials'] == [
        {'app_id': '17', 'app_secret': 'first', 'user_openid': 'owner'},
        {'app_id': '18', 'app_secret': 'second', 'user_openid': 'other'},
    ]


@pytest.mark.parametrize('failure', ['base64', 'short', 'empty', 'bad-tag', 'wrong-key', 'utf8'])
def test_invalid_ciphertext_never_delivers_a_secret_and_wipes_key(manager, post, failure):
    bind_id = manager.create_session()['bind_id']
    session = manager._sessions[bind_id]
    data = completion(post)
    raw = base64.b64decode(data['bot_encrypt_secret'])
    variants = {
        'base64': 'not base64 ' + SECRET,
        'short': base64.b64encode(bytes(27)).decode(),
        'empty': encrypted(request_key(post), b''),
        'bad-tag': base64.b64encode(raw[:-1] + bytes([raw[-1] ^ 1])).decode(),
        'wrong-key': encrypted(os.urandom(32)),
        'utf8': encrypted(request_key(post), b'fake-credential\xff'),
    }
    data['bot_encrypt_secret'] = variants[failure]
    post.return_value = reply(data)
    with pytest.raises(qr.QrBindError, match='解密') as error:
        manager.poll_session(bind_id)
    assert variants[failure] not in repr(error.value) and SECRET not in repr(error.value)
    assert error.value.__context__ is None
    assert not any(session.aes_key_bytes) and not session.consumed
    assert manager.poll_session(bind_id)['status'] == 3


@pytest.mark.parametrize('fields', [
    {'credentials': []}, {'credentials': None}, {'credentials': [None]}, {'bot_appid': '0', 'bot_encrypt_secret': 'x'},
    {'bot_appid': '12345', 'app_secret': SECRET}, {'bot_appid': None},
])
def test_incomplete_completed_payload_is_rejected(manager, post, fields):
    bind_id = manager.create_session()['bind_id']
    post.return_value = reply(dict(status=2, **fields))
    with pytest.raises(qr.QrBindError) as error:
        manager.poll_session(bind_id)
    assert SECRET not in repr(error.value)
    assert manager.poll_session(bind_id)['status'] == 3


def test_cancel_is_idempotent_and_unknown_handles_do_not_call_qq(manager, post):
    bind_id = manager.create_session()['bind_id']
    key = manager._sessions[bind_id].aes_key_bytes
    post.reset_mock()
    for handle in [bind_id, bind_id, 'offline-unknown']:
        manager.cancel_session(handle)
        assert manager.poll_session(handle)['status'] == 3
        with pytest.raises(KeyError):
            manager.get_qr_png(handle)
    post.assert_not_called()
    assert bytes(key) == bytes(32)


def test_cancel_all_wipes_active_sessions_and_keeps_manager_usable(manager, post):
    handles = [manager.create_session()['bind_id'] for _ in range(2)]
    keys = [manager._sessions[handle].aes_key_bytes for handle in handles]
    post.reset_mock()
    manager.cancel_all()
    for handle, key in zip(handles, keys):
        assert bytes(key) == bytes(32)
        assert manager.poll_session(handle)['status'] == 3
        with pytest.raises(KeyError):
            manager.get_qr_png(handle)
    post.assert_not_called()
    fresh = manager.create_session()['bind_id']
    assert fresh not in handles and manager.get_qr_png(fresh).startswith(b'\x89PNG\r\n\x1a\n')


def test_ttl_wipes_an_abandoned_session_without_any_api_calls(post):
    mgr = qr.QrBindManager(ttl=0.5)
    try:
        bind_id = mgr.create_session()['bind_id']
        key = mgr._sessions[bind_id].aes_key_bytes
        cleaner = mgr._cleaner
        cleaner.join(5)
        assert not cleaner.is_alive() and bytes(key) == bytes(32) and bind_id not in mgr._sessions
        assert post.call_count == 1
    finally:
        mgr.close()


def test_new_session_is_rejected_at_active_limit_and_cancel_frees_slot(post):
    mgr = qr.QrBindManager()
    try:
        handles = [mgr.create_session()['bind_id'] for _ in range(16)]
        with pytest.raises(qr.QrBindError) as error:
            mgr.create_session()
        assert error.value.http_status == 429 and post.call_count == 16
        mgr.cancel_session(handles[0])
        assert mgr.create_session()['bind_id'] not in handles
    finally:
        mgr.close()


@pytest.mark.parametrize('cancel_pending', [False, True])
def test_in_flight_creations_count_toward_limit_even_when_cancelled(post, cancel_pending):
    mgr = qr.QrBindManager(max_sessions=1)
    started, release = threading.Event(), threading.Event()
    post.side_effect = gate(lambda *a, **kw: reply({'task_id': TASK}), started, release)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            first = pool.submit(mgr.create_session)
            try:
                assert started.wait(5)
                if cancel_pending:
                    mgr.cancel_session(next(iter(mgr._sessions)))
                with pytest.raises(qr.QrBindError) as error:
                    mgr.create_session()
                assert error.value.http_status == 429 and post.call_count == 1
            finally:
                release.set()
            if cancel_pending:
                with pytest.raises(qr.QrBindError) as error:
                    first.result(5)
                assert error.value.http_status == 410
            else:
                assert first.result(5)['bind_id']
    finally:
        mgr.close()


def test_close_wipes_inflight_key_and_late_creation_cannot_reopen_service(manager, post):
    started, release = threading.Event(), threading.Event()
    post.side_effect = gate(lambda *a, **kw: reply({'task_id': TASK}), started, release)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(manager.create_session)
        try:
            assert started.wait(5)
            key = next(iter(manager._sessions.values())).aes_key_bytes
            manager.close()
            assert bytes(key) == bytes(32)
        finally:
            release.set()
        with pytest.raises(qr.QrBindError):
            future.result(5)
    with pytest.raises(qr.QrBindError) as error:
        manager.create_session()
    assert error.value.http_status == 503 and post.call_count == 1


@pytest.mark.parametrize('phase', ['http', 'decrypt'])
@pytest.mark.parametrize('end', ['cancel', 'close', 'expire'])
def test_cancel_close_or_expiry_wins_against_late_completion(manager, post, monkeypatch, phase, end):
    clock = [100]
    monkeypatch.setattr(qr, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    bind_id = manager.create_session()['bind_id']
    key = manager._sessions[bind_id].aes_key_bytes
    response = reply(completion(post))
    started, release = threading.Event(), threading.Event()
    if phase == 'http':
        post.side_effect = gate(lambda *a, **kw: response, started, release)
    else:
        post.return_value = response
        monkeypatch.setattr(qr, '_credentials', gate(qr._credentials, started, release))
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(manager.poll_session, bind_id)
        try:
            assert started.wait(5)
            if end == 'cancel':
                manager.cancel_session(bind_id)
            elif end == 'close':
                manager.close()
            else:
                clock[0] += 300
        finally:
            release.set()
        result = future.result(5)
    assert result['status'] == 3 and 'credentials' not in result and bytes(key) == bytes(32)


def test_concurrent_polls_can_only_consume_completed_secret_once(manager, post):
    bind_id = manager.create_session()['bind_id']
    post.return_value = reply(completion(post))
    together = threading.Barrier(2)

    def poll():
        together.wait(5)
        return manager.poll_session(bind_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(poll) for _ in range(2)]
        results = sorted((future.result(5) for future in futures), key=lambda row: row['status'])
    assert [row['status'] for row in results] == [2, 3]
    assert results[0]['credentials'][0]['app_secret'] == SECRET and 'credentials' not in results[1]
    assert post.call_count == 2


def test_blocked_poll_does_not_block_another_session(manager, post):
    first = manager.create_session()['bind_id']
    started, release = threading.Event(), threading.Event()
    poll = gate(lambda: reply({'status': 1}), started, release)
    post.side_effect = lambda url, **kw: poll() if url.endswith('poll_bind_result') else reply({'task_id': TASK})
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(manager.poll_session, first)
        try:
            assert started.wait(5)
            assert manager.create_session()['bind_id'] != first
        finally:
            release.set()
        assert future.result(5)['status'] == 1


def test_qr_is_rendered_as_real_png_in_memory_from_exact_url(manager, monkeypatch, tmp_path):
    import qrcode

    session = manager.create_session()
    renderer = Mock(wraps=qrcode.make)
    monkeypatch.setattr(qrcode, 'make', renderer)
    png = manager.get_qr_png(session['bind_id'])
    renderer.assert_called_once_with(session['qr_url'])
    assert png.startswith(b'\x89PNG\r\n\x1a\n')
    with Image.open(io.BytesIO(png)) as image:
        assert image.format == 'PNG' and image.width == image.height
        assert len(image.getcolors()) == 2
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('sdk, platform, expected', [
    ('qqGuildv2_link', 'qqGuild', True), ('qqGuild_link', 'qqGuild', False),
    ('qqGuildv2_link', 'qq', False), ('onebot', 'qq', False),
])
def test_supported_preset_depends_on_both_sdk_and_platform(sdk, platform, expected):
    assert qr.is_qr_bind_supported(sdk, platform) is expected


def test_standard_public_ws_account_keeps_secret_only_in_access_token():
    account = qr.build_qqguild_v2_ws_account('12345', SECRET)
    assert json.loads(json.dumps(account)) == {
        'id': '12345', 'enable': True, 'password': '',
        'sdk_type': 'qqGuildv2_link', 'platform_type': 'qqGuild', 'model_type': 'public',
        'server': {'auto': True, 'type': 'websocket', 'host': '', 'port': 0, 'access_token': SECRET},
        'extends': {}, 'debug': False,
    }
    assert SECRET not in repr(account)
