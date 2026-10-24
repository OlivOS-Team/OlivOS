"""Create test WebUI instances with known fixture passwords; never display generated credentials."""

from pathlib import Path

from OlivOS.webUI import authAPI, serverAPI


FIXTURE_PASSWORD = 'webui-fixture-password'


def make_host(*args, password=FIXTURE_PASSWORD, **kwargs):
    root = Path(kwargs.get('root_path', Path.cwd()))
    config = dict(serverAPI.DEFAULT_SERVER, **kwargs.get('server_conf', {}))
    path = authAPI.auth_path(root, config)
    if not path.exists():
        authAPI.write_record(path, authAPI.password_record(password))
    host = serverAPI.server(*args, **kwargs)
    assert host.error is None
    host.test_password = password
    response = host.app.test_client().post('/api/login', json={'password': password})
    assert response.status_code == 200
    host.test_token = response.json['browser_token']
    return host
