# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_inde_member.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   qqGuildv2 indeAPI 群成员缓存读取与全量刷新入口测试
'''

import json
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common
from OlivOS.adapter.qqGuild import qqGuildv2Store as store

SDK = OlivOS.qqGuildv2SDK


@pytest.fixture
def inde_ctx(monkeypatch):
    monkeypatch.setattr(common, 'sdkQQGroupApiDenied', set())
    monkeypatch.setattr(common, 'sdkQQGroupApiBackoff', {})
    monkeypatch.setattr(common, 'sdkQQGroupApiRateInfo', {})
    monkeypatch.setattr(common, 'sdkQQGroupCalibrationGroups', {})
    monkeypatch.setattr(common, 'sdkQQGroupCalibrationBotInfo', {})
    monkeypatch.setattr(common, 'sdkQQGroupRefreshCooldown', {})
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPages', {})
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPageLimit', 3000)
    monkeypatch.setattr(
        common.req,
        'request',
        Mock(side_effect=AssertionError('不应发起真实网络请求'))
    )
    account = OlivOS.API.bot_info_T(
        id=20001,
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='public'
    )
    event = SimpleNamespace(bot_info=account, log_func=None)
    api = SDK.inde_interface(event, 'qqGuild')
    yield account, event, api
    store.close_db()


def test_get_qq_group_member_cache_empty_and_no_network(inde_ctx, monkeypatch):
    _, _, api = inde_ctx
    fetch_mock = Mock(side_effect=AssertionError('只读缓存入口不得触发拉取'))
    monkeypatch.setattr(common, '_qq_group_fetch_member_pages', fetch_mock)
    monkeypatch.setattr(common, '_enqueue_qq_group_warm', fetch_mock)

    assert api.hasAPI('get_qq_group_member_cache') is True
    assert api.get_qq_group_member_cache('g_empty', remote=True) is None

    res = api.get_qq_group_member_cache('g_empty', flag_log=False)
    assert res['active'] is False
    assert res['data'] == []
    assert res['extra']['source'] == 'cache'
    assert res['extra']['members_state'] == 'active'
    assert res['extra']['verified_at'] is None
    assert res['extra']['complete'] is False
    assert res['extra']['partial'] is True
    assert res['extra']['api_denied'] is False
    assert res['extra']['stale_count'] == 0
    assert res['extra']['placeholder_count'] == 0
    fetch_mock.assert_not_called()


def test_get_qq_group_member_cache_matches_unified_get_group_member_list(inde_ctx, monkeypatch):
    account, event, api = inde_ctx
    now = int(time.time())
    store.upsert_group(account.hash, 'g_same', members_state='complete', verified_at=now - 10)
    store.upsert_member(
        account.hash, 'g_same', 'm1',
        username='张三', member_nickname='群名片张三', member_role='admin',
        bot=False, joined_at='2026-11-01T00:00:00Z', union_openid='u1',
        source='api', updated_at=now
    )
    store.upsert_member(
        account.hash, 'g_same', 'm2',
        source='event', updated_at=now - 61 * 86400
    )

    cache_res = api.get_qq_group_member_cache('g_same', flag_log=False)
    unified_res = SDK.event_action.get_group_member_list(event, 'g_same')

    assert cache_res['active'] is True
    assert cache_res == unified_res
    assert cache_res['extra']['complete'] is True
    assert cache_res['extra']['partial'] is False
    assert cache_res['extra']['verified_at'] == now - 10
    assert cache_res['extra']['stale_count'] == 1
    assert cache_res['extra']['placeholder_count'] == 1
    common.req.request.assert_not_called()


def test_refresh_qq_group_member_list_cooldown_and_passthrough(inde_ctx, monkeypatch):
    account, event, api = inde_ctx
    clock = [1000.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])

    assert api.hasAPI('refresh_qq_group_member_list') is True
    assert '阻塞' in (api.refresh_qq_group_member_list.__doc__ or '')
    assert api.refresh_qq_group_member_list('g_ref', remote=True) is None

    refresh_calls = []

    def fake_refresh(target_event, group_openid, max_pages=500):
        refresh_calls.append((target_event.bot_info.hash, group_openid, max_pages))
        res = OlivOS.contentAPI.api_result_data_template.universal_result()
        res['active'] = True
        res['data'].update({
            'chat_type': 'qq_group',
            'chat_id': str(group_openid),
            'operation': 'refresh_qq_group_member_list',
            'pages': 3,
            'member_count': 65,
            'error': None,
            'error_code': None
        })
        return res

    monkeypatch.setattr(SDK.event_action, 'refresh_qq_group_member_list', fake_refresh)

    # 首次刷新正常放行并原样返回，传入 max_pages=min(500, 剩余预算)。
    first = api.refresh_qq_group_member_list('g_ref', flag_log=False)
    assert first['active'] is True
    assert first['data']['pages'] == 3
    assert first['data']['member_count'] == 65
    assert refresh_calls == [(account.hash, 'g_ref', 500)]

    # 60 秒冷却期内直接返回 refresh cooldown，不调底层刷新。
    clock[0] += 59.0
    cooling = api.refresh_qq_group_member_list('g_ref', flag_log=False)
    assert cooling['active'] is False
    assert cooling['data']['error'] == 'refresh cooldown'
    assert cooling['data']['operation'] == 'refresh_qq_group_member_list'
    assert len(refresh_calls) == 1

    # 其它群不受 g_ref 冷却影响。
    other = api.refresh_qq_group_member_list('g_other', flag_log=False)
    assert other['active'] is True
    assert len(refresh_calls) == 2

    # 满 60 秒后 g_ref 恢复允许刷新。
    clock[0] += 1.0
    after = api.refresh_qq_group_member_list('g_ref', flag_log=False)
    assert after['active'] is True
    assert refresh_calls == [
        (account.hash, 'g_ref', 500),
        (account.hash, 'g_other', 500),
        (account.hash, 'g_ref', 500)
    ]


def test_inde_member_methods_validate_missing_event_or_bot_info(inde_ctx):
    for bad_event in (
        None,
        SimpleNamespace(bot_info=None, log_func=None),
        SimpleNamespace(bot_info=SimpleNamespace(hash=None), log_func=None),
    ):
        api = SDK.inde_interface(bad_event, 'qqGuild')
        cache_res = api.get_qq_group_member_cache('g_bad', flag_log=False)
        assert cache_res['active'] is False
        assert cache_res['data'] == []
        assert cache_res['extra']['source'] == 'cache'
        assert cache_res['extra']['complete'] is False
        assert cache_res['extra']['partial'] is True

        ref_res = api.refresh_qq_group_member_list('g_bad', flag_log=False)
        assert ref_res['active'] is False
        assert ref_res['data']['operation'] == 'refresh_qq_group_member_list'
        assert ref_res['data']['error'] == 'bot_info is required'


def test_get_qq_group_member_cache_default_flag_log_is_false(inde_ctx):
    account, _, _ = inde_ctx
    log_calls = []
    event = SimpleNamespace(
        bot_info=account,
        plugin_info={'name': 'test_plugin'},
        log_func=lambda *args: log_calls.append(args),
        getBotIDStr=lambda: 'bot_str'
    )
    api = SDK.inde_interface(event, 'qqGuild')

    # 默认不打 2 级回调日志。
    res_silent = api.get_qq_group_member_cache('g_log')
    assert res_silent['active'] is False
    assert 'extra' in res_silent
    assert log_calls == []

    # 显式传 flag_log=True 才打 2 级日志。
    api.get_qq_group_member_cache('g_log', flag_log=True)
    assert len(log_calls) == 1
    assert log_calls[0][0] == 2


def test_refresh_qq_group_member_list_enforces_and_deducts_daily_budget(inde_ctx, monkeypatch):
    account, _, api = inde_ctx
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPageLimit', 5)
    monkeypatch.setattr(common.time, 'strftime', lambda fmt: '2026-11-22')

    calls = []

    def fake_refresh(target_event, group_openid, max_pages=500):
        calls.append((group_openid, max_pages))
        res = OlivOS.contentAPI.api_result_data_template.universal_result()
        res['active'] = True
        res['data'].update({
            'chat_type': 'qq_group',
            'chat_id': str(group_openid),
            'operation': 'refresh_qq_group_member_list',
            'pages': 5,
            'member_count': 120,
            'error': None,
            'error_code': None
        })
        return res

    monkeypatch.setattr(SDK.event_action, 'refresh_qq_group_member_list', fake_refresh)

    first = api.refresh_qq_group_member_list('g_b1', flag_log=False)
    assert first['active'] is True
    assert common.sdkQQGroupWarmDailyPages[(str(account.hash), '2026-11-22')] == 5

    # 预算耗尽后直接拒绝，不调用底层接口，也不写入 g_b2 的冷却表。
    second = api.refresh_qq_group_member_list('g_b2', flag_log=False)
    assert second['active'] is False
    assert second['data']['error'] == 'daily page budget exhausted'
    assert calls == [('g_b1', 5)]
    assert (str(account.hash), 'g_b2') not in common.sdkQQGroupRefreshCooldown


def test_refresh_qq_group_member_list_end_to_end_real_fetch_db_and_budget_cap(inde_ctx, monkeypatch):
    """端到端：走真实 _qq_group_fetch_member_pages + 真实 SQLite DB + 剩余预算作为 max_pages 上限。"""
    account, _, api = inde_ctx
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPageLimit', 3)
    monkeypatch.setattr(common.time, 'strftime', lambda fmt: '2026-11-22')
    monkeypatch.setattr(common, '_ensure_qq_group_calibration_thread', Mock())
    # 预先消耗 1 页，当日剩余预算仅 2 页。
    common._add_qq_group_warm_daily_pages(account.hash, 1, day_str='2026-11-22')

    pages_by_cursor = {
        '': (200, {'members': [{'member_openid': 'm1', 'username': '成员1'}], 'next_cursor': 'c2'}),
        'c2': (200, {'members': [{'member_openid': 'm2', 'username': '成员2'}], 'next_cursor': 'c3'}),
        'c3': (200, {'members': [{'member_openid': 'm3', 'username': '成员3'}], 'next_cursor': ''}),
    }
    requested_cursors = []

    class StubMembersAPI(object):
        def __init__(self, sdk_bot):
            self.bot_info = sdk_bot
            self.metadata = SimpleNamespace(group_openid=None)
            self.query = None
            self.res = None
            self.res_code = 200

        def do_api(self, method='GET'):
            cursor = '' if not self.query else self.query.get('cursor', '')
            requested_cursors.append(cursor)
            status, body = pages_by_cursor[cursor]
            self.res_code = status
            self.res = json.dumps(body)
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupMembers', StubMembersAPI)

    res = api.refresh_qq_group_member_list('g_e2e_ref', flag_log=False)
    assert res['active'] is True
    assert res['data']['pages'] == 2
    assert res['data']['member_count'] == 2
    assert requested_cursors == ['', 'c2']
    # 已落库 2 名成员，且未翻完故不误标 complete。
    members = store.get_members(account.hash, 'g_e2e_ref')
    assert set(members) == {'m1', 'm2'}
    assert members['m1']['username'] == '成员1'
    assert store.get_group(account.hash, 'g_e2e_ref')['members_state'] != 'complete'
    # 预算 1 + 2 = 3 恰好用满，下一次刷新被拒。
    assert common.sdkQQGroupWarmDailyPages[(str(account.hash), '2026-11-22')] == 3
    blocked = api.refresh_qq_group_member_list('g_e2e_ref_2', flag_log=False)
    assert blocked['active'] is False
    assert blocked['data']['error'] == 'daily page budget exhausted'
