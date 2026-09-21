import json
import threading

import pytest

from OlivOS.webUI import serverAPI


def test_environment_overrides_webui_bind_config(tmp_path, monkeypatch):
    monkeypatch.setenv('OLIVOS_WEBUI_HOST', ' 0.0.0.0 ')
    monkeypatch.setenv('OLIVOS_WEBUI_PORT', '23456')
    (tmp_path / 'conf').mkdir()
    config_path = tmp_path / 'conf/config.json'
    config_path.write_text(json.dumps({
        'models': {'OlivOS_webUI': {'server': {'host': 'localhost', 'port': 20480}}},
    }), encoding='utf-8')
    original = config_path.read_bytes()
    service = serverAPI.server(
        root_path=tmp_path,
        server_conf={'host': '127.0.0.1', 'port': 20480},
    )
    try:
        assert service.config['host'] == '0.0.0.0'
        assert service.config['port'] == 23456
        assert serverAPI.browser_url(tmp_path) == 'http://127.0.0.1:23456'
        assert config_path.read_bytes() == original
    finally:
        service.on_terminate()


@pytest.mark.parametrize('name,value', [
    ('OLIVOS_WEBUI_HOST', '   '),
    ('OLIVOS_WEBUI_PORT', 'not-a-port'),
    ('OLIVOS_WEBUI_PORT', '65536'),
    ('OLIVOS_WEBUI_PORT', '-1'),
    ('OLIVOS_WEBUI_PORT', '1.5'),
    ('OLIVOS_WEBUI_PORT', ''),
])
def test_invalid_webui_environment_values_are_ignored(tmp_path, monkeypatch, name, value):
    monkeypatch.delenv('OLIVOS_WEBUI_HOST', raising=False)
    monkeypatch.delenv('OLIVOS_WEBUI_PORT', raising=False)
    monkeypatch.setenv(name, value)
    service = serverAPI.server(
        root_path=tmp_path,
        server_conf={'host': '127.0.0.1', 'port': 23456},
    )
    try:
        assert service.config['host'] == '127.0.0.1'
        assert service.config['port'] == 23456
    finally:
        service.on_terminate()


def test_environment_port_zero_uses_actual_listener_in_browser_url(tmp_path, monkeypatch):
    import urllib.request

    monkeypatch.setenv('OLIVOS_WEBUI_HOST', '127.0.0.1')
    monkeypatch.setenv('OLIVOS_WEBUI_PORT', '0')
    service = serverAPI.server(root_path=tmp_path)
    worker = threading.Thread(target=service.run, daemon=True)
    worker.start()
    try:
        assert service.ready.wait(5) and service.error is None
        assert 1 <= service.config['port'] <= 65535
        url = serverAPI.browser_url(tmp_path)
        assert url == f"http://127.0.0.1:{service.config['port']}"
        with urllib.request.urlopen(url + '/api/health', timeout=3) as response:
            assert json.load(response) == {'status': 'OK'}
    finally:
        service.on_terminate()
        worker.join(timeout=5)
    assert not worker.is_alive()
