# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_group_cache.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   QQ 群成员缓存及接口降级测试
'''

import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common
from OlivOS.adapter.qqGuild import qqGuildv2Store as store


@pytest.fixture
def group_api(monkeypatch):
    monkeypatch.setattr(common, 'sdkQQGroupApiDenied', set())
    monkeypatch.setattr(common, 'sdkQQGroupApiBackoff', {})
    monkeypatch.setattr(common, 'sdkQQGroupApiRateInfo', {})
    monkeypatch.setattr(common, 'sdkQQGroupCalibrationGroups', {})
    proc = SimpleNamespace(log=Mock())
    monkeypatch.setattr(OlivOS.pluginAPI, 'gProc', proc)
    bot = common.bot_info_T(id=123, model='public')
    bot_hash = OlivOS.API.getBotHash(
        bot_id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    yield bot, bot_hash, proc
    store.close_db()


def response_api(code, group='group'):
    return SimpleNamespace(
        metadata=SimpleNamespace(group_openid=group),
        res=json.dumps({'code': code}), res_code=400, do_api=Mock()
    )


def test_11253_disables_interface_permanently_and_logs_once(group_api, monkeypatch):
    bot, _, proc = group_api
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    api = response_api(11253)
    first = common._do_qq_group_api_request(bot, api, 'GET', 'group_member_info')
    clock[0] += 100000
    second = common._do_qq_group_api_request(bot, api, 'GET', 'group_member_info')
    common._mark_qq_group_api_denied('group_member_info')
    assert first['denied'] and second['denied']
    assert api.do_api.call_count == 1
    assert proc.log.call_count == 1


def test_11255_removes_cached_group_and_members(group_api):
    bot, bot_hash, _ = group_api
    store.touch_group(bot_hash, 'group')
    store.upsert_member(bot_hash, 'group', 'member', username='test')
    api = response_api(11255)
    common._do_qq_group_api_request(bot, api, 'GET', 'group_member_list')
    assert store.get_group(bot_hash, 'group') is None
    assert store.get_members(bot_hash, 'group') == {}


@pytest.mark.parametrize('error_code', [100017, 40023001])
def test_group_api_backoff_is_one_hour_per_group(group_api, monkeypatch, error_code):
    bot, _, _ = group_api
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    api = response_api(error_code)
    common._do_qq_group_api_request(bot, api, 'GET', 'group_member_info')
    clock[0] += 3599
    blocked = common._do_qq_group_api_request(bot, api, 'GET', 'group_member_info')
    assert blocked['rate_limited']
    assert api.do_api.call_count == 1
    clock[0] += 1
    common._do_qq_group_api_request(bot, api, 'GET', 'group_member_info')
    assert api.do_api.call_count == 2


def test_member_list_exposes_stale_and_preserves_boolean(group_api):
    _, bot_hash, _ = group_api
    store.touch_group(bot_hash, 'group')
    store.upsert_member(bot_hash, 'group', 'member', username='name', bot=True,
                        updated_at=int(time.time()) - 61 * 86400)
    store.close_db()
    event = SimpleNamespace(bot_info=SimpleNamespace(hash=bot_hash))
    result = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'group')
    assert result['active']
    assert result['data'][0]['extra']['stale'] is True
    assert result['data'][0]['extra']['bot'] is True


def test_default_store_follows_working_directory(tmp_path, monkeypatch):
    first = tmp_path / 'first'
    second = tmp_path / 'second'
    first.mkdir()
    second.mkdir()
    store.close_db()
    monkeypatch.chdir(first)
    store.touch_group('bot', 'first-group')
    monkeypatch.chdir(second)
    assert store.get_group('bot', 'first-group') is None
    store.touch_group('bot', 'second-group')
    monkeypatch.chdir(first)
    assert store.get_group('bot', 'first-group') is not None
    assert store.get_group('bot', 'second-group') is None
    store.close_db()
