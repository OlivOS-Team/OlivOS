"""Boot configuration, localization and resource helpers without starting bot workers."""

import copy
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
