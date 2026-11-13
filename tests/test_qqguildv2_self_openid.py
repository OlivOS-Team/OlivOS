# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_self_openid.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   QQ 机器人自身 openid 持久化及发现测试
'''

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common
from OlivOS.adapter.qqGuild import qqGuildv2Store as store


@pytest.fixture
def self_context(monkeypatch):
    monkeypatch.setattr(common, 'sdkSubSelfOpenInfo', {})
    monkeypatch.setattr(common, 'sdkSubSelfOpenInfoRetryAt', {})
    monkeypatch.setattr(common, 'sdkSubSelfOpenInfoRequestHistory', {})
    monkeypatch.setattr(common, 'sdkSubSelfOpenInfoDisabled', set())
    proc = SimpleNamespace(Proc_data={})
    monkeypatch.setattr(OlivOS.pluginAPI, 'gProc', proc)
    yield common.bot_info_T(id=123, model='public'), proc
    store.close_db()


def bot_state_factory(monkeypatch, responses):
    calls = []

    class BotState:
        def __init__(self, bot_info):
            self.metadata = SimpleNamespace(group_openid=None)
            self.res = None
            self.res_code = None

        def do_api(self, method):
            group = self.metadata.group_openid
            calls.append(group)
            self.res_code, body = responses[group]
            self.res = json.dumps(body)

    monkeypatch.setattr(common.API, 'getQQGroupBotState', BotState)
    return calls


def test_file_hit_uses_no_bot_state_request_and_populates_proc_data(self_context, tmp_path, monkeypatch):
    bot, proc = self_context
    path = tmp_path / 'data' / 'qqGuildv2' / 'bot_self.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'hash': {
        'openid': 'self-openid', 'source': 'file', 'appid': '123',
        'seed_groups': ['group'], 'updated_at': 1
    }}), encoding='utf-8')
    request = Mock(side_effect=AssertionError('file hit must not call bot_state'))
    monkeypatch.setattr(common.API, 'getQQGroupBotState', request)
    assert common._get_qq_group_self_open_id('hash', 'group', bot) == 'self-openid'
    assert proc.Proc_data['qqGuildv2_self_openid']['hash'] == 'self-openid'
    assert common.sdkSubSelfOpenInfo['hash'] == 'self-openid'
    request.assert_not_called()


def test_invalid_seed_is_removed_then_next_seed_is_persisted(self_context, tmp_path, monkeypatch):
    bot, proc = self_context
    store.touch_group('hash', 'valid', last_seen_at=100)
    store.touch_group('hash', 'invalid', last_seen_at=200)
    calls = bot_state_factory(monkeypatch, {
        'invalid': (400, {'code': 11255}),
        'valid': (200, {'member_openid': 'self-openid'})
    })
    assert common._get_qq_group_self_open_id('hash', None, bot) == 'self-openid'
    assert calls == ['invalid', 'valid']
    assert store.get_group('hash', 'invalid') is None
    saved = json.loads((tmp_path / 'data' / 'qqGuildv2' / 'bot_self.json').read_text(encoding='utf-8'))['hash']
    assert saved['openid'] == 'self-openid'
    assert saved['source'] == 'group'
    assert saved['appid'] == '123'
    assert saved['seed_groups'] == ['valid']
    assert proc.Proc_data['qqGuildv2_self_openid']['hash'] == 'self-openid'


def test_without_seeds_waits_for_group_event(self_context, monkeypatch):
    bot, _ = self_context
    calls = bot_state_factory(monkeypatch, {'new-group': (200, {'member_openid': 'self'})})
    assert common._get_qq_group_self_open_id('hash', None, bot) is None
    assert calls == []
    assert common._get_qq_group_self_open_id('hash', 'new-group', bot) == 'self'
    assert calls == ['new-group']


def test_11253_disables_self_discovery_for_bot(self_context, monkeypatch):
    bot, _ = self_context
    calls = bot_state_factory(monkeypatch, {'group': (403, {'code': 11253})})
    assert common._get_qq_group_self_open_id('hash', 'group', bot) is None
    assert common._get_qq_group_self_open_id('hash', 'group', bot, now=1000000) is None
    assert calls == ['group']


def test_unknown_self_openid_is_not_guessed_from_mentions(self_context, monkeypatch):
    bot, _ = self_context
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link', platform_platform='qqGuild', platform_model='public'
    )
    monkeypatch.setattr(common, 'sdkSelfInfo', {account.hash: {'id': '123', 'username': 'bot'}})
    monkeypatch.setattr(common, 'qqEventDedupeCache', {})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args: None)
    data = {
        'id': 'message', 'group_openid': 'group', 'content': 'hello',
        'author': {'member_openid': 'sender', 'username': 'sender'},
        'mentions': [{'member_openid': 'unrelated-bot', 'bot': True, 'username': 'bot'}]
    }
    payload = OlivOS.qqGuildv2SDK.PAYLOAD.rxPacket({
        'op': 0, 's': 1, 't': 'GROUP_MESSAGE_CREATE', 'd': data
    })
    event = OlivOS.API.Event(OlivOS.qqGuildv2SDK.event(payload, account))
    assert event.active
    assert 'sub_self_open_id' not in event.data.extend
