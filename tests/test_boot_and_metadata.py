"""Boot configuration, localization and resource helpers without starting bot workers."""

import copy
import os
import urllib.request
from pathlib import Path
from unittest.mock import Mock

import pytest

import OlivOS


def test_boot_patch_merges_model_options_without_dropping_defaults():
    original = copy.deepcopy(OlivOS.bootDataAPI.default_Conf)
    patched = OlivOS.bootAPI.get_patch_config(original, {'system': {}, 'models': {
        'OlivOS_webUI': {'enable': False}}})
    assert patched['models']['OlivOS_webUI']['enable'] is False
    assert patched['models']['OlivOS_webUI']['rx_queue'] == 'OlivOS_webUI_rx_queue'


def test_boot_patch_rejects_mismatched_field_type():
    original = {'system': {'name': 'OlivOS'}, 'models': {}}
    result = OlivOS.bootAPI.get_patch_config(original, {'system': {'name': 7}})
    assert result['system']['name'] == 'OlivOS'


def test_boot_defaults_reference_declared_models_and_queues():
    config = OlivOS.bootDataAPI.default_Conf
    assert set(config['system']['init']) <= config['models'].keys()
    # 协议连接队列按账号动态创建，只检查固定核心队列。
    for name in ('OlivOS_logger', 'OlivOS_plugin', 'OlivOS_nativeWinUIAPI', 'OlivOS_webUI'):
        assert config['models'][name]['rx_queue'] in config['queue']


def test_webui_is_created_before_initial_plugin_broadcast():
    steps = OlivOS.bootDataAPI.default_Conf['system']['init']
    assert steps.index('OlivOS_webUI') < steps.index('OlivOS_plugin')


def test_boot_adds_statistics_model_to_legacy_config():
    # 旧版 basic.json 没有统计模型时，启动前应补全组件并放在 WebUI 之前。
    config = copy.deepcopy(OlivOS.bootDataAPI.default_Conf)
    config['models'].pop('OlivOS_statistics')
    config['system']['init'].remove('OlivOS_statistics')
    OlivOS.bootAPI.ensure_statistics_model(config)
    assert 'OlivOS_statistics' in config['models']
    assert config['system']['init'].index('OlivOS_statistics') < config['system']['init'].index('OlivOS_webUI')
    assert 'OlivOS_statistics' in OlivOS.bootDataAPI.default_Conf['models']


def test_boot_statistics_compat_uses_existing_logger():
    # 自定义 logger 与 WebUI 名称的旧配置不能被默认名称覆盖，统计组件仍要插到 WebUI 之前。
    config = {
        'system': {'init': ['my_logger', 'my_webui']},
        'models': {
            'my_logger': {'type': 'logger'},
            'my_webui': {'type': 'webUI'},
        },
    }
    OlivOS.bootAPI.ensure_statistics_model(config)
    assert config['models']['OlivOS_statistics']['logger_proc'] == 'my_logger'
    assert config['system']['init'] == ['my_logger', 'OlivOS_statistics', 'my_webui']


def test_boot_statistics_compat_restores_missing_init_entry():
    # 即使模型定义已存在，只要初始化顺序漏了统计组件，也要补回 WebUI 之前。
    config = {
        'system': {'init': ['logger', 'webui']},
        'models': {
            'logger': {'type': 'logger'},
            'webui': {'type': 'webUI'},
            'OlivOS_statistics': {'type': 'statistics', 'logger_proc': 'logger'},
        },
    }
    OlivOS.bootAPI.ensure_statistics_model(config)
    assert config['system']['init'] == ['logger', 'OlivOS_statistics', 'webui']


def test_metadata_format_uses_defaults_without_mutating_patch():
    patch = {'user_id': '42'}
    assert OlivOS.metadataAPI.getTextByMetaTableFormat(
        {'event': '{user_id}/{nickname}'}, 'event', patch) == '42/N/A'
    assert patch == {'user_id': '42'}


def test_metadata_unknown_key_returns_fallback():
    assert OlivOS.metadataAPI.getTextByMetaTableFormat({}, 'missing', {}, 'fallback') == 'fallback'


def test_localization_keeps_missing_placeholders():
    args = ['value']
    assert OlivOS.L10NAPI.formatSTR('{0}/{1}', args) == 'value/{1}'
    assert args == ['value']


def test_unknown_language_falls_back_to_original_text():
    assert OlivOS.L10NAPI.getTransByL10N('test {0}', ['ok'], 'not-a-language') == 'test ok'


def test_relative_resource_is_resolved_in_data_directory(tmp_path):
    assert Path(OlivOS.contentAPI.resourcePathTransform('images', 'demo.png')) == tmp_path / 'data/images/demo.png'


def test_absolute_resource_path_is_preserved(tmp_path):
    path = str(tmp_path / 'absolute.png')
    assert OlivOS.contentAPI.resourcePathTransform('images', path) == path


def test_update_digest_matches_file_contents(tmp_path):
    path = tmp_path / 'resource'
    path.write_bytes(b'abc')
    assert OlivOS.updateAPI.checkFileMD5(path) == '900150983cd24fb0d6963f7d28e17f72'
    assert OlivOS.updateAPI.checkFileMD5(tmp_path / 'absent') is None


def test_update_json_request_uses_timeout_and_parses_response(monkeypatch):
    request = Mock(return_value=Mock(text='{"version": 42}'))
    monkeypatch.setattr(OlivOS.updateAPI.req, 'request', request)
    monkeypatch.setattr(OlivOS.webTool, 'get_system_proxy', lambda: {})
    assert OlivOS.updateAPI.GETHttpJson2Dict('https://example.invalid/update') == {'version': 42}
    assert request.call_args.kwargs['timeout'] > 0


@pytest.mark.parametrize('response', ['not json', ''])
def test_update_invalid_response_is_nonfatal(monkeypatch, response):
    monkeypatch.setattr(OlivOS.updateAPI.req, 'request', Mock(return_value=Mock(text=response)))
    assert OlivOS.updateAPI.GETHttpJson2Dict('https://example.invalid/update') is None


def test_process_termination_escalates_only_for_unresponsive_process(monkeypatch):
    process = Mock()
    monkeypatch.setattr(OlivOS.bootAPI.psutil, 'wait_procs', Mock(side_effect=[([], [process]), ([], [process])]))
    OlivOS.bootAPI.kill_process(process)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()


def test_restart_lookup_treats_component_in_rebuild_window_as_missing():
    """重载真空期（组件已被弹出、尚未重建）内重复的重载请求必须变成空操作。

    直接取 Proc_dict[name] 会抛 KeyError 打穿主控制循环，之后所有重载、优先级更新、
    插件事件都会投进没人消费的死队列。
    """
    proc_this = Mock()
    proc_this.Proc_info.rx_queue = Mock()
    assert OlivOS.bootAPI.get_proc_for_restart({}, 'OlivOS_plugin') is None
    assert OlivOS.bootAPI.get_proc_for_restart({'OlivOS_plugin': proc_this}, 'OlivOS_plugin') is proc_this

    proc_this.Proc_info.rx_queue = None
    assert OlivOS.bootAPI.get_proc_for_restart({'OlivOS_plugin': proc_this}, 'OlivOS_plugin') is None


@pytest.mark.parametrize(
    ('raw_proxies', 'expected'),
    [
        (
            {'http': 'http://proxy.example.com:8080'},
            {'http': 'proxy.example.com:8080'},
        ),
        (
            {'https': 'https://tunnel.example.com:8443'},
            {'https': 'tunnel.example.com:8443'},
        ),
        (
            {
                'http': 'http://http.example.com:8080',
                'https': 'https://https.server.example.com:8443',
            },
            {
                'http': 'http.example.com:8080',
                'https': 'https.server.example.com:8443',
            },
        ),
        (
            {
                'http': 'HTTP://Proxy.Example.com:8080',
                'https': 'HTTPS://Server.Example.com:8443',
            },
            {
                'http': 'Proxy.Example.com:8080',
                'https': 'Server.Example.com:8443',
            },
        ),
        (
            {
                'http': 'http://127.0.0.1:7890',
                'https': 'http://proxy.example.com:8080',
            },
            {
                'http': '127.0.0.1:7890',
                'https': 'http://proxy.example.com:8080',
            },
        ),
        (
            {
                'http': 'socks5://socks.example.com:1080',
                'https': 'socks5h://socks.example.com:1080',
            },
            {
                'http': 'socks5://socks.example.com:1080',
                'https': 'socks5h://socks.example.com:1080',
            },
        ),
        (
            {'no': 'notion.so,only.internal,localhost'},
            {'no': 'notion.so,only.internal,localhost'},
        ),
        (
            {'http': 'proxy.example.com:8080'},
            {'http': 'proxy.example.com:8080'},
        ),
        ({}, {}),
    ],
)
def test_get_system_proxy_strips_only_matching_scheme_prefix(monkeypatch, raw_proxies, expected):
    original = dict(raw_proxies)
    monkeypatch.setattr(urllib.request, 'getproxies', lambda: raw_proxies)
    assert OlivOS.webTool.get_system_proxy() == expected
    assert raw_proxies == original


@pytest.mark.parametrize(
    ('raw_proxies', 'proxy_type', 'expected'),
    [
        ({'http': 'http://proxy.example.com:8080'}, 'http', ('proxy.example.com', '8080', 'http')),
        ({'https': 'https://tunnel.example.com:8443'}, 'https', ('tunnel.example.com', '8443', 'https')),
        ({'http': 'http://http.example.com:8080/'}, 'http', ('http.example.com', '8080', 'http')),
        ({'http': 'http://127.0.0.1:7890'}, 'http', ('127.0.0.1', '7890', 'http')),
        ({'http': 'socks5://socks.example.com:1080'}, 'http', (None, None, None)),
        ({'http': 'http://proxy.example.com'}, 'http', (None, None, None)),
        ({'http': 'http://:8080'}, 'http', (None, None, None)),
        ({'http': 'http://proxy.example.com:'}, 'http', (None, None, None)),
        ({}, 'http', (None, None, None)),
    ],
)
def test_get_system_proxy_tuple_extracts_host_and_port_without_mangling(
    monkeypatch, raw_proxies, proxy_type, expected
):
    monkeypatch.setattr(urllib.request, 'getproxies', lambda: dict(raw_proxies))
    assert OlivOS.webTool.get_system_proxy_tuple(proxy_type) == expected


@pytest.mark.parametrize(
    ('proxy_map', 'expected'),
    [
        ({'http': 'http://proxy.example.com:8080'}, ('proxy.example.com', '8080', 'http')),
        ({'http': 'proxy.example.com:8080'}, ('proxy.example.com', '8080', 'http')),
        ({'http': 'http.example.com:8080'}, ('http.example.com', '8080', 'http')),
        (None, (None, None, None)),
    ],
)
def test_get_system_proxy_tuple_is_idempotent_on_proxy_values(monkeypatch, proxy_map, expected):
    monkeypatch.setattr(OlivOS.webTool, 'get_system_proxy', lambda: proxy_map)
    assert OlivOS.webTool.get_system_proxy_tuple('http') == expected


def test_get_system_proxy_reads_environment_variables_without_corrupting_hostnames(monkeypatch):
    for key in list(os.environ):
        if key.lower().endswith('_proxy'):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('http_proxy', 'http://proxy.example.com:8080')
    monkeypatch.setenv('https_proxy', 'https://tunnel.example.com:8443')
    assert OlivOS.webTool.get_system_proxy() == {
        'http': 'proxy.example.com:8080',
        'https': 'tunnel.example.com:8443',
    }
    assert OlivOS.webTool.get_system_proxy_tuple('http') == ('proxy.example.com', '8080', 'http')
