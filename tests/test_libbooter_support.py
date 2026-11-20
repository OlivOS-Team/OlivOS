"""可执行启动器辅助函数与模型分发的离线测试。"""

import importlib
import json
import os
import queue
import re
import zipfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS


START_CASES = [
    ('libEXEModelAPI', 'startGoCqhttpLibExeModel', 'gocqhttp_show'),
    ('libWQEXEModelAPI', 'startWalleQLibExeModel', 'walleq_show'),
    ('libOPQBotEXEModelAPI', 'startOPQBotLibExeModel', 'opqbot_port'),
    ('libCWCBEXEModelAPI', 'startCWCBQLibExeModel', 'ComWeChatBotClient'),
    ('libAstralQsignEXEModelAPI', 'startAstralQsignLibExeModel', 'gocqhttp_show_Android_Phone'),
]


def _bot(model='gocqhttp_show', bot_hash='hash1', enable=True, password='', extends=None, account_id='10001'):
    """构造启动器辅助函数需要的最小 bot_info 结构。"""

    return SimpleNamespace(
        id=account_id,
        hash=bot_hash,
        enable=enable,
        password=password,
        platform={'platform': 'qq', 'sdk': 'onebot', 'model': model},
        post_info=SimpleNamespace(auto='True', type='post', port=5700, access_token='token'),
        extends=extends or {},
    )


def _launcher_state():
    """返回一次启动器调用使用的独立队列、进程和配置映射。"""

    return {
        'multiprocessing_dict': {'tx': queue.Queue(), 'control': queue.Queue()},
        'Proc_dict': {'logger': Mock()},
        'Proc_Proc_dict': {},
        'basic_conf_models_this': {
            'name': 'model_proc',
            'rx_queue': 'model_rx',
            'tx_queue': 'tx',
            'control_queue': 'control',
            'logger_proc': 'logger',
            'interval': 0.1,
            'dead_interval': 1,
            'target_proc': 'target',
            'sub_target_proc': 'sub_target',
            'server': {'port': 9000, 'token': 'server-token'},
        },
        'basic_conf_models': {
            'target': {'server': {'port': 9000}},
            'sub_target': {'server': {'port': 9001}},
        },
    }


@pytest.mark.parametrize('module_name,function_name,model', START_CASES)
def test_windows_launcher_dispatches_supported_models(module_name, function_name, model, monkeypatch):
    """各 Windows 启动器应解析可执行文件、创建账号进程并启动。"""

    module = importlib.import_module('OlivOS.libBooter.' + module_name)
    resources = []
    monkeypatch.setattr(module.platform, 'system', lambda: 'Windows')
    if hasattr(module, 'multiprocessing'):
        monkeypatch.setattr(module.multiprocessing, 'Queue', queue.Queue)
    monkeypatch.setattr(OlivOS.updateAPI, 'checkResouceFile', lambda **kwargs: resources.append(kwargs))

    created = []

    class FakeServer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            created.append(self)

        def start_unity(self, mode):
            return {'mode': mode}

    monkeypatch.setattr(module, 'server', FakeServer)
    state = _launcher_state()
    getattr(module, function_name)({'bot': _bot(model)}, state['basic_conf_models_this'],
                                   state['multiprocessing_dict'], state['Proc_dict'],
                                   state['Proc_Proc_dict'], state['basic_conf_models'], 'threading')

    assert resources
    assert len(created) == 1
    bot_info_dict = created[0].kwargs['bot_info_dict']
    selected_bot = bot_info_dict['bot'] if isinstance(bot_info_dict, dict) else bot_info_dict
    assert selected_bot.platform['model'] == model
    expected_name = 'model_proc' if module_name == 'libAstralQsignEXEModelAPI' else 'model_proc=bot'
    assert expected_name in state['Proc_dict']
    assert state['Proc_Proc_dict'][expected_name] == {'mode': 'threading'}


def test_napcat_launcher_selects_each_bundled_version(monkeypatch):
    """NapCat 应为每个匹配模型各启动一个进程，并下载各自依赖包。"""

    module = importlib.import_module('OlivOS.libBooter.libNapCatEXEModelAPI')
    resources = []
    monkeypatch.setattr(module.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(module.multiprocessing, 'Queue', queue.Queue)
    monkeypatch.setattr(OlivOS.updateAPI, 'checkResouceFile', lambda **kwargs: resources.append(kwargs))

    class FakeServer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def start_unity(self, mode):
            return mode

    monkeypatch.setattr(module, 'server', FakeServer)
    state = _launcher_state()
    models = ['napcat_show_new', 'napcat_show_new_9_9_19', 'napcat_show']
    bots = {model: _bot(model, bot_hash='hash-' + model) for model in models}
    module.startNapCatLibExeModel(bots, state['basic_conf_models_this'], state['multiprocessing_dict'],
                                  state['Proc_dict'], state['Proc_Proc_dict'], state['basic_conf_models'],
                                  'threading')

    assert len(resources) == 3
    assert {call['resouce_name'] for call in resources} == {
        'NapCat-QQ-Win-9.9.11-24568', 'NapCat-QQ-Win-9.9.19-34740', 'NapCat-QQ-Win-9.9.22-40990',
    }
    assert len(state['Proc_Proc_dict']) == 3


@pytest.mark.parametrize('module_name,function_name,model', START_CASES)
def test_launcher_is_a_noop_outside_windows(module_name, function_name, model, monkeypatch):
    """非 Windows 系统应跳过可执行文件下载与进程创建。"""

    module = importlib.import_module('OlivOS.libBooter.' + module_name)
    monkeypatch.setattr(module.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(OlivOS.updateAPI, 'checkResouceFile', Mock(side_effect=AssertionError('must not download')))
    state = _launcher_state()
    getattr(module, function_name)({'bot': _bot(model)}, state['basic_conf_models_this'],
                                   state['multiprocessing_dict'], state['Proc_dict'],
                                   state['Proc_Proc_dict'], state['basic_conf_models'], 'threading')
    assert state['Proc_Proc_dict'] == {}


def test_device_helpers_generate_stable_identifiers_without_mutating_input():
    """设备信息修补应隔离输入，标识生成器应符合约定格式。"""

    module = importlib.import_module('OlivOS.libBooter.libEXEModelAPI')
    original = {'protocol': 1}
    device = module.deviceInfoFix(original)
    assert original == {'protocol': 1}
    assert device['protocol'] == 1 and len(device['imei']) == 15
    assert re.fullmatch(r'[0-9a-f]{32}', device['imsi_md5'])
    assert re.fullmatch(r'[0-9a-f]+', device['android_id'])
    assert module.deviceInfoFix({'protocol': 1, 'imei': 'fixed'}) == {'protocol': 1, 'imei': 'fixed'}
    assert re.fullmatch(r'\d{15}', module.GenIMEI('123456789012345'))
    assert module.getMD5(['a', 'b']) == '187ef4436122d1cc2f40dc2b92f0eba0'
    assert module.getHEX('A') == '41'
    assert re.fullmatch(r'[A-Za-z0-9]{8}', module.getRandomString(8))
    assert re.fullmatch(r'\d{8}', module.getRandomStringOfInt(8))
    assert module.getRandomStringRange(4, 'x') == 'xxxx'


def test_release_dir_is_idempotent():
    """启动器目录创建应可重复执行而不报错。"""

    module = importlib.import_module('OlivOS.libBooter.libEXEModelAPI')
    module.releaseDir('./tmp/data')
    module.releaseDir('./tmp/data')
    assert os.path.isdir('tmp/data')


def test_control_event_helpers_emit_expected_packets():
    """令牌投递、webview 控制和 JS 桥接应发布预期控制包。"""

    module = importlib.import_module('OlivOS.libBooter.libEXEModelAPI')
    control_queue = queue.Queue()
    module.setGoCqhttpTokenSend(control_queue, 'hash1', 'token1')
    packet = control_queue.get_nowait()
    assert packet.action == 'send'
    assert packet.key['data']['event'] == 'token_get'
    assert packet.key['data']['token'] == 'token1'

    module.sendOpentxTuringTestPage(control_queue, 'page', 'Title', 'https://example.invalid')
    packet = control_queue.get_nowait()
    assert packet.action == 'init_type_open_tx_turingTest_webview_page'
    assert packet.key['target'] == {'action': 'init', 'name': 'page'}

    module.sendStopTxTuringTestPage(control_queue, 'page')
    packet = control_queue.get_nowait()
    assert packet.action == 'stop' and packet.key == 'page'

    window = Mock()
    module.txTuringTest_evaluate_js(window)
    assert 'pywebview.api.invoke' in window.evaluate_js.call_args.args[0]


def test_turing_api_forwards_only_ticket_payloads():
    """图灵测试桥接只转发合法 JSON ticket，忽略畸形或无关载荷。"""

    module = importlib.import_module('OlivOS.libBooter.libEXEModelAPI')
    control_queue = queue.Queue()
    api = module.txTuringTestApi('page', 'hash1', control_queue)
    api.invoke('ignored', json.dumps({'ticket': 'ticket1'}))
    send_packet = control_queue.get_nowait()
    stop_packet = control_queue.get_nowait()
    assert send_packet.key['data']['token'] == 'ticket1'
    assert stop_packet.action == 'stop'
    api.invoke('ignored', json.dumps({'ticket': 1}))
    api.invoke('ignored', json.dumps({'other': 'value'}))
    assert control_queue.empty()


def test_account_fix_writes_device_and_protocol_files(tmp_path):
    """协议账号修复应写入设备状态与所选 qsign 档案文件。"""

    module = importlib.import_module('OlivOS.libBooter.libEXEModelAPI')
    protocol_name = next(iter(module.gProtocalInfo['android_phone']))
    bot = _bot('gocqhttp_show_Android_Phone', extends={'qsign-server-protocal': protocol_name})
    module.accountFix({'hash1': bot}, Mock())
    device_path = tmp_path / 'conf/gocqhttp/hash1/device.json'
    protocol_path = tmp_path / 'conf/gocqhttp/hash1/data/versions/1.json'
    assert json.loads(device_path.read_text(encoding='utf-8'))['protocol'] == 1
    assert protocol_path.read_text(encoding='utf-8') == module.gProtocalInfo['android_phone'][protocol_name]


def test_account_fix_skips_disabled_accounts(tmp_path):
    """禁用账号不应生成协议目录。"""

    module = importlib.import_module('OlivOS.libBooter.libEXEModelAPI')
    module.accountFix({'hash1': _bot(enable=False)}, Mock())
    assert not (tmp_path / 'conf/gocqhttp/hash1').exists()


@pytest.mark.parametrize('module_name', ['libNapCatEXEModelAPI', 'libAstralQsignEXEModelAPI'])
def test_legacy_gbk_zip_names_are_restored_and_extracted(module_name, tmp_path):
    """两个启动器解压前都应修复历史 cp437 中文文件名。"""

    module = importlib.import_module('OlivOS.libBooter.' + module_name)
    archive = tmp_path / 'legacy.zip'
    legacy_name = '中文.txt'.encode('gbk').decode('cp437')
    with zipfile.ZipFile(archive, 'w') as zip_file:
        zip_file.writestr(legacy_name, 'payload')
    with zipfile.ZipFile(archive) as zip_file:
        module.support_gbk(zip_file)
        assert zip_file.namelist() == ['中文.txt']
    target = tmp_path / 'extract'
    module.unzip(archive, target)
    assert (target / '中文.txt').read_text(encoding='utf-8') == 'payload'


def test_copy_file_ignores_missing_source(tmp_path):
    """可选的启动器文件复制在源文件缺失时不得抛错。"""

    module = importlib.import_module('OlivOS.libBooter.libOPQBotEXEModelAPI')
    source = tmp_path / 'source.txt'
    source.write_text('content', encoding='utf-8')
    module.copyFile(source, tmp_path / 'target.txt')
    assert (tmp_path / 'target.txt').read_text(encoding='utf-8') == 'content'
    module.copyFile(tmp_path / 'missing.txt', tmp_path / 'never.txt')
    assert not (tmp_path / 'never.txt').exists()


def test_cwcb_install_command_writes_batch_file(tmp_path):
    """ComWeChat 安装脚本应写入 lib 目录并包含注册命令。"""

    module = importlib.import_module('OlivOS.libBooter.libCWCBEXEModelAPI')
    module.cwcbInstallCommand()
    text = (tmp_path / 'lib/install_cwcb.bat').read_text(encoding='utf-8')
    assert 'CWeChatRobot.exe /regserver' in text and 'chcp 65001' in text


def test_astral_activity_and_otp_helpers():
    """Astral QSign 激活只匹配配置的 QQ 模型，OTP 格式应保持稳定。"""

    module = importlib.import_module('OlivOS.libBooter.libAstralQsignEXEModelAPI')
    active = _bot('gocqhttp_show_Android_Phone', extends={'qsign-server-protocal': 'AstralQsign'})
    inactive = _bot('gocqhttp_show_Android_Phone', extends={'qsign-server-protocal': 'other'})
    assert module.isBotActive({'a': active}) is True
    assert module.isBotActive({'a': inactive}) is False
    otp = module.getOTPPASSWORD()
    assert re.fullmatch(r'\d{10}[0-9a-f]{32}', otp)


@pytest.mark.parametrize('module_name,action', [
    ('libEXEModelAPI', 'gocqhttp'),
    ('libWQEXEModelAPI', 'walleq'),
    ('libOPQBotEXEModelAPI', 'opqbot'),
    ('libCWCBEXEModelAPI', 'ComWeChatBotClient'),
    ('libNapCatEXEModelAPI', 'napcat'),
])
def test_launcher_event_helpers_publish_account_platform(module_name, action):
    """启动器事件辅助方法应把账号元数据附到原生 UI 控制包。"""

    module = importlib.import_module('OlivOS.libBooter.' + module_name)
    control_queue = queue.Queue()
    bot = _bot()
    server = module.server(Proc_name='proc', rx_queue=queue.Queue(), control_queue=control_queue,
                           bot_info_dict=bot)
    server.send_init_event()
    server.send_log_event('line')
    server.send_QRCode_event('qr.png')
    packets = [control_queue.get_nowait() for _ in range(3)]
    assert [packet.key['data']['event'] for packet in packets] == ['init', 'log', 'qrcode']
    assert all(packet.key['data']['action'] == action for packet in packets)
    assert all(packet.key['data']['hash'] == 'hash1' for packet in packets)
    assert all(packet.key['data']['account_platform'] == bot.platform for packet in packets)


def test_astral_model_enable_targets_only_supported_accounts():
    """Astral 只对使用受支持模型的账号发送 skip-delay 命令。"""

    module = importlib.import_module('OlivOS.libBooter.libAstralQsignEXEModelAPI')
    control_queue = queue.Queue()
    supported = _bot('gocqhttp_show_Android_Phone', bot_hash='supported')
    other = _bot('default', bot_hash='other')
    server = module.server(Proc_name='astral', control_queue=control_queue,
                           bot_info_dict={'supported': supported, 'other': other})
    server.setGoCqhttpModelEnableSendAll()
    packet = control_queue.get_nowait()
    assert packet.key['target'] == {'type': 'gocqhttp_lib_exe_model', 'hash': 'supported'}
    assert packet.key['data'] == {'action': 'skipDelay'}
    assert control_queue.empty()
