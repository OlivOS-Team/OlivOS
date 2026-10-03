"""Windows protocol launcher configuration and UI bus packets; no executables launched."""

import json
import os
import queue

import pytest

import OlivOS

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows protocol launchers')


@pytest.mark.parametrize('module,action', [
    ('libNapCatEXEModelAPI', 'napcat'), ('libOPQBotEXEModelAPI', 'opqbot'),
    ('libWQEXEModelAPI', 'walleq'), ('libCWCBEXEModelAPI', 'ComWeChatBotClient'),
])
def test_launcher_log_packet_routes_to_its_own_terminal(module, action):
    control = queue.Queue()
    bot = OlivOS.API.bot_info_T(id=10001)
    service = getattr(OlivOS, module).server('test', control_queue=control, bot_info_dict=bot)
    service.send_log_event('fixture log')
    packet = control.get_nowait()
    assert packet.key['target']['type'] == 'nativeWinUI'
    assert packet.key['data']['action'] == action
    assert packet.key['data']['hash'] == bot.hash
    assert packet.key['data']['data'] == 'fixture log'


@pytest.mark.parametrize('version', ['9.9.11', '9.9.12'])
def test_napcat_generated_config_points_to_host_receiver(tmp_path, version):
    bot = OlivOS.API.bot_info_T(id=10001, port=58001, access_token='fixture-token')
    directory = tmp_path / 'conf/napcat' / bot.hash / 'config'
    directory.mkdir(parents=True)
    config = OlivOS.libNapCatEXEModelAPI.napcatTypeConfig(bot, {'server': {'port': 58000}}, version=version)
    config.setConfig()
    data = json.loads((directory / 'onebot11_10001.json').read_text(encoding='utf-8'))
    url = 'http://127.0.0.1:58000/OlivOSMsgApi/qq/onebot/default'
    if 'network' in data:
        assert data['network']['httpClients'][0]['url'] == url
    else:
        assert data['http']['postUrls'] == [url]
