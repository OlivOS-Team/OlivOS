"""Password storage, migration and local management use temporary installations only."""

import json
import asyncio
import os
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs

import aiohttp
import pytest

from OlivOS.webUI import authAPI, localAPI, serverAPI
from webui_test_support import make_host


def test_legacy_password_migrates_once_without_plaintext_backup(tmp_path, monkeypatch):
    path = tmp_path / 'conf/webui_token.txt'
    path.parent.mkdir()
    password = 'migration-fixture-password'
    path.write_text('  ' + password + '\n', encoding='utf-8')
    displayed = []
    monkeypatch.setattr(authAPI, 'display_password', lambda value, migrated=False: displayed.append((value, migrated)))
    record = authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER)
    assert authAPI.verify(password, record)
    assert not authAPI.verify('incorrect', record)
    assert not path.exists()
    assert displayed == [(password, True)]
    saved = tmp_path / 'conf/webui_auth.json'
    assert password not in saved.read_text(encoding='utf-8')
    assert authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER) == record
    assert len(displayed) == 1


def test_corrupt_new_file_never_falls_back_to_legacy(tmp_path):
    path = tmp_path / 'conf/webui_auth.json'
    path.parent.mkdir()
    path.write_text('{broken', encoding='utf-8')
    legacy = path.with_name('webui_token.txt')
    legacy.write_text('legacy-fixture-password', encoding='utf-8')
    with pytest.raises(ValueError):
        authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER)
    assert legacy.exists() and path.read_text(encoding='utf-8') == '{broken'


def test_migration_write_failure_preserves_legacy(tmp_path, monkeypatch):
    path = tmp_path / 'conf/webui_token.txt'
    path.parent.mkdir()
    path.write_text('migration-fixture-password', encoding='utf-8')
    monkeypatch.setattr(authAPI, 'write_record', lambda *args: (_ for _ in ()).throw(OSError('fixture')))
    with pytest.raises(OSError):
        authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER)
    assert path.read_text(encoding='utf-8') == 'migration-fixture-password'


def test_interrupted_migration_resumes_without_replacing_new_credentials(tmp_path, monkeypatch):
    record = authAPI.password_record('migration-fixture-password')
    authAPI.write_record(tmp_path / 'conf/webui_auth.json', record)
    legacy = tmp_path / 'conf/webui_token.txt'
    legacy.write_text('migration-fixture-password', encoding='utf-8')
    displayed = []
    monkeypatch.setattr(authAPI, 'display_password', lambda value, migrated=False: displayed.append(migrated))
    assert authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER) == record
    assert displayed == [True] and not legacy.exists()


def test_new_credentials_never_reactivate_a_different_legacy_password(tmp_path):
    record = authAPI.password_record('new-fixture-password')
    authAPI.write_record(tmp_path / 'conf/webui_auth.json', record)
    (tmp_path / 'conf/webui_token.txt').write_text('old-fixture-password', encoding='utf-8')
    assert authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER) == record
    assert not authAPI.verify('old-fixture-password', record)


def test_password_hash_uses_new_salt_and_rejects_unbounded_parameters():
    first = authAPI.password_record('fixture-password')
    second = authAPI.password_record('fixture-password')
    assert first['salt'] != second['salt'] and first['hash'] != second['hash']
    assert authAPI.verify('fixture-password', first)
    second['n'] = 2 ** 30
    with pytest.raises(ValueError):
        authAPI.validate_record(second)
    assert 'fixture-password' not in json.dumps(first)


def test_initial_password_is_displayed_once_and_never_written_as_plaintext(tmp_path, monkeypatch):
    displayed = []
    monkeypatch.setattr(authAPI, 'interactive_output', lambda: True)
    monkeypatch.setattr(authAPI, 'display_password', lambda value, migrated=False: displayed.append(value))
    record = authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER)
    assert len(displayed) == 1 and authAPI.verify(displayed[0], record)
    assert displayed[0] not in (tmp_path / 'conf/webui_auth.json').read_text(encoding='utf-8')
    assert authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER) == record and len(displayed) == 1


def test_password_display_does_not_write_redirected_output(monkeypatch, capsys):
    monkeypatch.setattr(authAPI, 'interactive_output', lambda: False)
    monkeypatch.setattr(authAPI, 'windows_desktop_available', lambda: False)
    monkeypatch.setattr(authAPI.sys, 'frozen', False, raising=False)
    assert authAPI.display_password('display-fixture-password', migrated=True) is False
    output = capsys.readouterr()
    assert output.out == output.err == ''


@pytest.mark.skipif(os.name != 'nt', reason='Windows local password dialog')
@pytest.mark.parametrize('interactive', [False, True])
def test_source_windows_migration_displays_local_dialog_once_without_logging(
        tmp_path, monkeypatch, capsys, interactive):
    monkeypatch.setattr(authAPI, 'interactive_output', lambda: interactive)
    monkeypatch.setattr(authAPI, 'windows_desktop_available', lambda: True)
    monkeypatch.setattr(authAPI.sys, 'frozen', False, raising=False)
    legacy = tmp_path / 'conf/webui_token.txt'
    legacy.parent.mkdir()
    legacy.write_text('dialog-fixture-password', encoding='utf-8')
    dialogs = []
    monkeypatch.setattr(authAPI, 'show_password_dialog',
                        lambda value, migrated=False: dialogs.append((value, migrated)) or True)
    record = authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER)
    assert authAPI.verify('dialog-fixture-password', record)
    assert dialogs == [('dialog-fixture-password', True)]
    assert not legacy.exists()
    assert authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER) == record
    assert len(dialogs) == 1
    output = capsys.readouterr()
    assert output.out == output.err == ''


@pytest.mark.skipif(os.name != 'nt', reason='Windows local password dialog')
def test_dialog_failure_preserves_legacy_password_for_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(authAPI, 'windows_desktop_available', lambda: True)

    def fail_dialog(*args, **kwargs):
        raise OSError('fixture display failure')

    monkeypatch.setattr(authAPI, 'show_password_dialog', fail_dialog)
    legacy = tmp_path / 'conf/webui_token.txt'
    legacy.parent.mkdir()
    legacy.write_text('dialog-fixture-password', encoding='utf-8')
    with pytest.raises(OSError):
        authAPI.initialize(tmp_path, serverAPI.DEFAULT_SERVER)
    assert legacy.exists()
    assert authAPI.verify('dialog-fixture-password', authAPI.read_record(tmp_path / 'conf/webui_auth.json'))


def test_credential_file_has_current_user_only_permissions(tmp_path):
    path = tmp_path / 'conf/webui_auth.json'
    authAPI.write_record(path, authAPI.password_record('permission-fixture-password'))
    if os.name == 'nt':
        import win32security
        sd = win32security.GetNamedSecurityInfo(str(path), win32security.SE_FILE_OBJECT,
                                                win32security.DACL_SECURITY_INFORMATION)
        acl = sd.GetSecurityDescriptorDacl()
        assert acl.GetAceCount() == 1 and acl.GetAce(0)[2] == localAPI.current_sid()
        assert sd.GetSecurityDescriptorControl()[0] & win32security.SE_DACL_PROTECTED
    else:
        import stat
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_local_manager_can_restart_without_inheriting_handles(tmp_path):
    import subprocess
    import sys

    first = localAPI.LocalServer(tmp_path, lambda message: {})
    first.start()
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(10)'], close_fds=False)
    second = None
    try:
        first.close()
        first.worker.join(timeout=4)
        assert not first.worker.is_alive()
        second = localAPI.LocalServer(tmp_path, lambda message: {})
        second.start()
        assert localAPI.request(tmp_path, {})['ok'] is True
    finally:
        first.close()
        if second:
            second.close()
            second.worker.join(timeout=4)
        child.terminate()
        child.wait(timeout=5)


@pytest.fixture
def live_host(tmp_path):
    host = make_host(root_path=tmp_path, server_conf={'host': '127.0.0.1', 'port': 0})
    worker = threading.Thread(target=host.run, daemon=True)
    worker.start()
    try:
        assert host.ready.wait(5) and host.error is None
        yield host
    finally:
        host.on_terminate()
        worker.join(timeout=5)
        assert not worker.is_alive()
        if host.local_manager:
            host.local_manager.worker.join(timeout=5)
            assert not host.local_manager.worker.is_alive()


def test_local_reset_revokes_password_sessions_tickets_and_open_websockets(live_host):
    host = live_host
    client = host.app.test_client()
    login = client.post('/api/login', json={'password': host.test_password}).json
    pending_url = serverAPI.local_login_url(host.root)
    ticket = parse_qs(urlsplit(pending_url).fragment)['login_ticket'][0]

    async def scenario():
        url = serverAPI.listener_url(host.config)
        async with aiohttp.ClientSession() as network:
            async with network.ws_connect(url + '/ws/logs', protocols=['olivos', 'token.' + host.test_token]) as ws:
                await ws.receive_json(timeout=2)
                result = await asyncio.to_thread(authAPI.set_local_password, host.root,
                                                 authAPI.password_record('new-fixture-password'))
                assert result is True
                assert (await ws.receive(timeout=2)).type == aiohttp.WSMsgType.CLOSE
            async with network.get(url + '/api/health') as response:
                assert response.status == 200

    asyncio.run(scenario())
    assert host.ready.is_set() and host.error is None
    assert client.post('/api/login', json={'password': host.test_password}).status_code == 401
    assert client.get('/api/status', headers={'X-Auth-Token': login['browser_token']}).status_code == 401
    assert not host.session_valid(login['session'])
    assert client.post('/api/login', json={'ticket': ticket}).status_code == 401
    assert client.post('/api/login', json={'password': 'new-fixture-password'}).status_code == 200
    saved = authAPI.read_record(authAPI.auth_path(host.root, host.config))
    assert authAPI.verify('new-fixture-password', saved)
    assert not authAPI.verify(host.test_password, saved)


def test_local_ticket_is_single_use_and_expires(live_host):
    host = live_host
    client = host.app.test_client()
    url = serverAPI.local_login_url(host.root)
    ticket = parse_qs(urlsplit(url).fragment)['login_ticket'][0]
    assert urlsplit(url).query == ''
    assert client.post('/api/login', json={'ticket': ticket}).status_code == 200
    assert client.post('/api/login', json={'ticket': ticket}).status_code == 401
    url = serverAPI.local_login_url(host.root)
    ticket = parse_qs(urlsplit(url).fragment)['login_ticket'][0]
    host.login_tickets[host.credential_key(ticket)] = time.monotonic() - 1
    assert client.post('/api/login', json={'ticket': ticket}).status_code == 401


def test_missing_local_manager_does_not_silently_reset_a_running_instance(live_host, monkeypatch):
    host = live_host
    original = authAPI.read_record(authAPI.auth_path(host.root, host.config))
    host.local_manager.close()
    host.local_manager.worker.join(timeout=4)
    assert not host.local_manager.worker.is_alive()
    monkeypatch.setattr(serverAPI, 'active_listener', lambda root: None)
    with pytest.raises(OSError):
        authAPI.set_local_password(host.root, authAPI.password_record('unapplied-fixture-password'))
    assert authAPI.read_record(authAPI.auth_path(host.root, host.config)) == original


def test_local_manager_rejects_unknown_operations_and_has_private_permissions(live_host):
    with pytest.raises(OSError):
        localAPI.request(live_host.root, {'action': 'unknown'})
    if os.name == 'nt':
        import win32security
        import win32con
        import win32file
        import win32pipe

        win32pipe.WaitNamedPipe(localAPI.endpoint(live_host.root), 3000)
        handle = win32file.CreateFile(localAPI.endpoint(live_host.root), win32con.READ_CONTROL,
                                      0, None, win32con.OPEN_EXISTING, 0, None)
        try:
            sd = win32security.GetSecurityInfo(handle, win32security.SE_KERNEL_OBJECT,
                                               win32security.DACL_SECURITY_INFORMATION)
            acl = sd.GetSecurityDescriptorDacl()
            assert acl.GetAceCount() == 1 and acl.GetAce(0)[2] == localAPI.current_sid()
        finally:
            handle.Close()
    else:
        from pathlib import Path
        import stat
        path = Path(localAPI.endpoint(live_host.root))
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_offline_reset_needs_no_old_password_and_respects_custom_paths(tmp_path):
    config = {'models': {'OlivOS_webUI': {'server': {
        'auth_path': './private/auth.json', 'token_path': './private/old-token.txt'}}}}
    (tmp_path / 'conf').mkdir()
    (tmp_path / 'conf/config.json').write_text(json.dumps(config), encoding='utf-8')
    record = authAPI.password_record('offline-fixture-password')
    assert authAPI.set_local_password(tmp_path, record) is False
    assert authAPI.verify('offline-fixture-password', authAPI.read_record(tmp_path / 'private/auth.json'))


def test_offline_reset_does_not_guess_paths_when_instance_config_is_corrupt(tmp_path):
    (tmp_path / 'conf').mkdir()
    (tmp_path / 'conf/config.json').write_text('{broken', encoding='utf-8')
    with pytest.raises(ValueError):
        authAPI.set_local_password(tmp_path, authAPI.password_record('fixture-password'))
    assert not (tmp_path / 'conf/webui_auth.json').exists()


def test_headless_fresh_install_does_not_generate_an_unavailable_password(tmp_path, monkeypatch):
    monkeypatch.setattr(authAPI, 'interactive_output', lambda: False)
    monkeypatch.setattr(authAPI, 'windows_desktop_available', lambda: False)
    monkeypatch.setattr(authAPI.sys, 'stdout', SimpleNamespace(isatty=lambda: False))
    host = serverAPI.server(root_path=tmp_path)
    assert host.error is not None and host.credentials is None
    assert not (tmp_path / 'conf/webui_auth.json').exists()


def test_reset_command_hides_input_and_does_not_require_old_password(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(authAPI.sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    prompts = []
    monkeypatch.setattr(authAPI.getpass, 'getpass', lambda prompt: prompts.append(prompt) or 'cli-fixture-password')
    authAPI.reset_command(tmp_path)
    assert len(prompts) == 2
    output = capsys.readouterr()
    assert 'cli-fixture-password' not in output.out + output.err
    assert authAPI.verify('cli-fixture-password', authAPI.read_record(tmp_path / 'conf/webui_auth.json'))


def test_reset_entrypoint_rejects_redirected_input_without_starting_bots(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    main = Path(__file__).resolve().parents[1] / 'main.py'
    result = subprocess.run([sys.executable, str(main), '--reset-webui-password'], input='',
                            capture_output=True, text=True, cwd=tmp_path, timeout=15)
    assert result.returncode == 2
    assert not (tmp_path / 'conf/webui_auth.json').exists()
    assert not (tmp_path / 'logfile').exists()


@pytest.mark.parametrize('body', [None, {'password': ''}, {'password': []}, {'password': 'incorrect'}])
def test_password_login_reports_errors_and_rejects_hash_as_a_credential(tmp_path, body):
    host = make_host(root_path=tmp_path)
    client = host.app.test_client()
    assert client.post('/api/login', json=body).status_code == 401
    assert client.post('/api/login', json={'password': host.credentials['hash']}).status_code == 401
    assert client.get('/api/status', headers={'X-Auth-Token': host.test_password}).status_code == 401
    assert client.post('/api/login', data={'password': host.test_password}).status_code == 415
    assert client.post('/api/reset-password', json={'password': 'replacement'}).status_code == 401
