# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_member_warm.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   QQ 群成员统一层非阻塞首屏、完整度元数据与后台续翻 worker 测试
'''

from collections import deque
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common
from OlivOS.adapter.qqGuild import qqGuildv2SDKGroup as group_mod
from OlivOS.adapter.qqGuild import qqGuildv2Store as store


@pytest.fixture
def warm_ctx(monkeypatch):
    monkeypatch.setattr(common, 'sdkQQGroupApiDenied', set())
    monkeypatch.setattr(common, 'sdkQQGroupApiBackoff', {})
    monkeypatch.setattr(common, 'sdkQQGroupApiRateInfo', {})
    monkeypatch.setattr(common, 'sdkQQGroupCalibrationGroups', {})
    monkeypatch.setattr(common, 'sdkQQGroupCalibrationBotInfo', {})
    monkeypatch.setattr(common, 'sdkQQGroupSuspectState', {})
    monkeypatch.setattr(common, 'sdkQQGroupSuspectDue', [])
    monkeypatch.setattr(common, 'sdkQQGroupSuspectGeneration', {})
    monkeypatch.setattr(common, 'sdkQQGroupSuspectPending', {})
    monkeypatch.setattr(common, 'sdkQQGroupSuspectVerifying', set())
    monkeypatch.setattr(common, 'sdkQQGroupSuspectThread', None)
    monkeypatch.setattr(common, 'sdkQQGroupSuspectEvent', threading.Event())
    monkeypatch.setattr(common, 'sdkQQGroupWarmQueue', deque())
    monkeypatch.setattr(common, 'sdkQQGroupWarmPending', set())
    monkeypatch.setattr(common, 'sdkQQGroupWarmSeen', {})
    monkeypatch.setattr(common, 'sdkQQGroupWarmStartedAt', {})
    monkeypatch.setattr(common, 'sdkQQGroupWarmFailCooldown', {})
    monkeypatch.setattr(common, 'sdkQQGroupWarmRateLimitUntilByBot', {})
    monkeypatch.setattr(common, 'sdkQQGroupWarmThread', None)
    monkeypatch.setattr(common, 'sdkQQGroupWarmEvent', threading.Event())
    monkeypatch.setattr(common, 'sdkQQGroupWarmSpacing', 0.0)
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPages', {})
    monkeypatch.setattr(common, '_register_qq_group_for_calibration', lambda *args: None)
    monkeypatch.setattr(group_mod, '_register_qq_group_for_calibration', lambda *args: None)
    proc = SimpleNamespace(log=Mock())
    monkeypatch.setattr(OlivOS.pluginAPI, 'gProc', proc)
    account = OlivOS.API.bot_info_T(
        id=123,
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='public'
    )
    event = SimpleNamespace(bot_info=account, log_func=None)
    sdk_bot = common.get_SDK_bot_info_from_Plugin_bot_info(account)
    yield account, event, sdk_bot, proc
    # 清理并唤醒可能启动过的测试后台线程，等待退出以防跨用例串扰。
    current_thread = threading.current_thread()
    warm_thread = common.sdkQQGroupWarmThread
    common.sdkQQGroupWarmThread = None
    common.sdkQQGroupWarmEvent.set()
    suspect_thread = common.sdkQQGroupSuspectThread
    common.sdkQQGroupSuspectThread = None
    common.sdkQQGroupSuspectEvent.set()
    for thread in (warm_thread, suspect_thread):
        if (
            thread is not None
            and thread is not current_thread
            and callable(getattr(thread, 'join', None))
            and callable(getattr(thread, 'is_alive', None))
            and thread.is_alive()
        ):
            thread.join(timeout=2.0)
    store.close_db()


def make_members_api(pages_by_cursor):
    class MembersAPI(object):
        def __init__(self, sdk_bot):
            self.metadata = SimpleNamespace(group_openid=None)
            self.query = None
            self.res = None
            self.res_code = 200

        def do_api(self, method='GET'):
            cursor = '' if not self.query else self.query.get('cursor', '')
            status, body = pages_by_cursor[cursor]
            self.res_code = status
            self.res = json.dumps(body)
            return self.res

    return MembersAPI


def test_small_group_single_page_complete_without_warm_queue(warm_ctx, monkeypatch):
    account, event, _, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (200, {
            'members': [
                {'member_openid': 'm1', 'username': '成员1', 'member_role': 'member'},
                {'member_openid': 'm2', 'username': '成员2', 'member_role': 'admin'},
            ],
            'next_cursor': ''
        })
    }))

    fetch_calls = []
    orig_fetch = common._qq_group_fetch_member_pages

    def spy_fetch(*args, **kwargs):
        fetch_calls.append((args, kwargs))
        return orig_fetch(*args, **kwargs)

    monkeypatch.setattr(group_mod, '_qq_group_fetch_member_pages', spy_fetch)

    result = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_small')
    assert result['active'] is True
    assert [m['user_id'] for m in result['data']] == ['m1', 'm2']
    assert len(fetch_calls) == 1
    assert fetch_calls[0][1]['wait'] is False
    assert fetch_calls[0][1]['max_pages'] == 1
    assert result['extra']['source'] == 'cache'
    assert result['extra']['members_state'] == 'complete'
    assert result['extra']['complete'] is True
    assert result['extra']['partial'] is False
    assert result['extra']['verified_at'] is not None
    assert result['extra']['api_denied'] is False
    assert result['extra']['stale_count'] == 0
    assert result['extra']['placeholder_count'] == 0
    assert len(common.sdkQQGroupWarmQueue) == 0
    assert len(common.sdkQQGroupWarmPending) == 0


def test_large_group_fetches_one_page_and_enqueues_warm(warm_ctx, monkeypatch):
    account, event, _, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (200, {
            'members': [{'member_openid': 'm1', 'username': '首屏成员'}],
            'next_cursor': 'cursor_p2'
        }),
        'cursor_p2': (200, {
            'members': [{'member_openid': 'm2', 'username': '次页成员'}],
            'next_cursor': ''
        }),
    }))

    fetch_calls = []
    orig_fetch = common._qq_group_fetch_member_pages

    def spy_fetch(*args, **kwargs):
        fetch_calls.append((args, kwargs))
        return orig_fetch(*args, **kwargs)

    monkeypatch.setattr(group_mod, '_qq_group_fetch_member_pages', spy_fetch)

    result = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_large')
    assert result['active'] is True
    assert [m['user_id'] for m in result['data']] == ['m1']
    assert len(fetch_calls) == 1
    assert fetch_calls[0][1]['wait'] is False
    assert fetch_calls[0][1]['max_pages'] == 1
    assert result['extra']['members_state'] == 'warming'
    assert result['extra']['complete'] is False
    assert result['extra']['partial'] is True
    assert store.get_group(account.hash, 'g_large')['members_state'] == 'warming'
    assert len(common.sdkQQGroupWarmQueue) == 1
    queued = common.sdkQQGroupWarmQueue[0]
    assert queued[0] == str(account.hash)
    assert queued[2] == 'g_large'
    assert queued[3] == 'cursor_p2'
    assert (str(account.hash), 'g_large') in common.sdkQQGroupWarmPending


def test_nonempty_incomplete_cache_returns_immediately_and_dedups_warm(warm_ctx, monkeypatch):
    account, event, _, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    fetch_mock = Mock(side_effect=AssertionError('缓存非空不应同步翻页'))
    monkeypatch.setattr(group_mod, '_qq_group_fetch_member_pages', fetch_mock)

    store.touch_group(account.hash, 'g_cached')
    store.upsert_member(account.hash, 'g_cached', 'm1', username='已缓存', source='event')
    store.upsert_member(account.hash, 'g_cached', 'm2', source='event')

    first = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_cached')
    second = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_cached')

    fetch_mock.assert_not_called()
    assert first['active'] is True
    assert second['active'] is True
    assert first['extra']['partial'] is True
    assert first['extra']['complete'] is False
    assert first['extra']['placeholder_count'] == 1
    assert len(common.sdkQQGroupWarmQueue) == 1
    assert common.sdkQQGroupWarmQueue[0][2] == 'g_cached'
    assert common.sdkQQGroupWarmQueue[0][3] == ''
    assert len(common.sdkQQGroupWarmPending) == 1


def test_warm_worker_completes_across_rounds_and_sleeps_outside_lock(warm_ctx, monkeypatch):
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, 'sdkQQGroupWarmPageBatch', 1)
    monkeypatch.setattr(common, 'sdkQQGroupWarmMaxRounds', 5)
    monkeypatch.setattr(common, 'sdkQQGroupWarmSpacing', 0.01)
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        'c1': (200, {'members': [{'member_openid': 'm2', 'username': 'u2'}], 'next_cursor': 'c2'}),
        'c2': (200, {'members': [{'member_openid': 'm3', 'username': 'u3'}], 'next_cursor': ''}),
    }))

    store.touch_group(account.hash, 'g_work')
    store.upsert_member(account.hash, 'g_work', 'm1', username='u1', source='api')

    wait_records = []
    real_event = common.sdkQQGroupWarmEvent
    orig_wait = real_event.wait
    orig_sleep = time.sleep

    class SpyEvent(object):
        def set(self):
            return real_event.set()

        def clear(self):
            return real_event.clear()

        def wait(self, timeout=None):
            # 确认等待时没有持有 sdkQQGroupWarmLock。
            acquired = common.sdkQQGroupWarmLock.acquire(blocking=False)
            if acquired:
                common.sdkQQGroupWarmLock.release()
            wait_records.append((timeout, acquired))
            return orig_wait(timeout=min(0.005, timeout) if timeout is not None else 0.005)

    monkeypatch.setattr(common, 'sdkQQGroupWarmEvent', SpyEvent())
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_work', start_cursor='c1') is True
    assert store.get_group(account.hash, 'g_work')['members_state'] == 'warming'

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        row = store.get_group(account.hash, 'g_work')
        if row and row['members_state'] == 'complete' and not common.sdkQQGroupWarmPending:
            break
        orig_sleep(0.01)

    row = store.get_group(account.hash, 'g_work')
    assert row['members_state'] == 'complete'
    assert row['verified_at'] is not None
    assert set(store.get_members(account.hash, 'g_work')) == {'m1', 'm2', 'm3'}
    assert len(common.sdkQQGroupWarmPending) == 0
    assert len(common.sdkQQGroupWarmQueue) == 0
    assert len(wait_records) >= 2
    assert all(lock_free for _, lock_free in wait_records)

    # 显式停止并等待真实 worker 线程退出。
    worker_thread = common.sdkQQGroupWarmThread
    common.sdkQQGroupWarmThread = None
    common.sdkQQGroupWarmEvent.set()
    if worker_thread is not None:
        worker_thread.join(timeout=2.0)
        assert not worker_thread.is_alive()


def test_warm_worker_denied_discards_and_resets_active(warm_ctx, monkeypatch):
    account, _, sdk_bot, proc = warm_ctx
    account_b = OlivOS.API.bot_info_T(
        id=999, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model='public'
    )
    sdk_bot_b = common.get_SDK_bot_info_from_Plugin_bot_info(account_b)
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (403, {'code': 11253, 'message': 'no permission'})
    }))

    store.touch_group(account.hash, 'g_deny1')
    store.touch_group(account.hash, 'g_deny2')
    store.touch_group(account_b.hash, 'g_other_bot')
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_deny1', start_cursor='') is True
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_deny2', start_cursor='') is True
    assert common._enqueue_qq_group_warm(account_b.hash, sdk_bot_b, 'g_other_bot', start_cursor='') is True
    assert store.get_group(account.hash, 'g_deny1')['members_state'] == 'warming'
    assert store.get_group(account.hash, 'g_deny2')['members_state'] == 'warming'

    # 第一个任务触发 11253：立即清掉该 bot 在 warm 队列的其它任务并复位 active，保留其它 bot 任务。
    assert common._qq_group_warm_step() is True
    assert store.get_group(account.hash, 'g_deny1')['members_state'] == 'active'
    assert store.get_group(account.hash, 'g_deny2')['members_state'] == 'active'
    assert (str(account.hash), 'g_deny1') not in common.sdkQQGroupWarmPending
    assert (str(account.hash), 'g_deny2') not in common.sdkQQGroupWarmPending
    assert common._check_qq_group_api_denied(account.hash, 'group_member_list') is True
    assert any(call.args[0] == 2 for call in proc.log.call_args_list)
    assert [(t[0], t[2]) for t in common.sdkQQGroupWarmQueue] == [(str(account_b.hash), 'g_other_bot')]
    assert store.get_group(account_b.hash, 'g_other_bot')['members_state'] == 'warming'


def test_warm_queue_overflow_drops_oldest_and_clears_pending(warm_ctx, monkeypatch):
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())

    for idx in range(501):
        store.touch_group(account.hash, 'g_%d' % idx)
    for idx in range(500):
        assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_%d' % idx) is True
    assert len(common.sdkQQGroupWarmQueue) == 500
    assert (str(account.hash), 'g_0') in common.sdkQQGroupWarmPending
    assert store.get_group(account.hash, 'g_0')['members_state'] == 'warming'

    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_500') is True
    assert len(common.sdkQQGroupWarmQueue) == 500
    assert (str(account.hash), 'g_0') not in common.sdkQQGroupWarmPending
    assert (str(account.hash), 'g_500') in common.sdkQQGroupWarmPending
    assert common.sdkQQGroupWarmQueue[0][2] == 'g_1'
    assert common.sdkQQGroupWarmQueue[-1][2] == 'g_500'
    assert store.get_group(account.hash, 'g_0')['members_state'] == 'active'


def test_open_db_resets_warming_to_active(tmp_path):
    db_path = tmp_path / 'warm_reset.sqlite3'
    store.open_db(db_path)
    store.upsert_group('bot_h', 'g_warming', members_state='warming')
    store.upsert_group('bot_h', 'g_complete', members_state='complete')
    store.close_db()

    store.open_db(db_path)
    try:
        assert store.get_group('bot_h', 'g_warming')['members_state'] == 'active'
        assert store.get_group('bot_h', 'g_complete')['members_state'] == 'complete'
    finally:
        store.close_db()


def test_fetch_failure_returns_partial_cache_or_inactive_when_empty(warm_ctx, monkeypatch):
    account, event, _, _ = warm_ctx

    # 场景 1：拉取返回 ok=False，但部分成员已落库 -> 仍返回成员，partial=True，members_state=active。
    def partial_fail_fetch(
        bot_info, group_openid, bot_hash=None, wait=False, max_pages=1,
        reconcile=False, sync_started_at=None
    ):
        store.touch_group(bot_hash, group_openid)
        store.upsert_member(bot_hash, group_openid, 'm_part', username='部分成员', source='api')
        return {
            'ok': False,
            'error': 'rate limit',
            'denied': False,
            'rate_limited': True,
            'pages': 1,
            'members': 1,
            'next_cursor': 'c1',
            'complete': False,
            'truncated': False
        }

    monkeypatch.setattr(group_mod, '_qq_group_fetch_member_pages', partial_fail_fetch)
    partial_res = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_part_fail')
    assert partial_res['active'] is True
    assert [m['user_id'] for m in partial_res['data']] == ['m_part']
    assert partial_res['extra']['partial'] is True
    assert partial_res['extra']['complete'] is False
    assert partial_res['extra']['members_state'] == 'active'
    assert partial_res['extra']['api_denied'] is False

    # 场景 2：无权限且缓存全空 -> active=False，extra.complete=False 且 extra.api_denied=True。
    common._mark_qq_group_api_denied(account.hash, 'group_member_list')
    empty_res = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_denied_empty')
    assert empty_res['active'] is False
    assert empty_res['data'] == []
    assert empty_res['extra']['source'] == 'cache'
    assert empty_res['extra']['members_state'] == 'active'
    assert empty_res['extra']['complete'] is False
    assert empty_res['extra']['partial'] is True
    assert empty_res['extra']['api_denied'] is True
    assert empty_res['extra']['stale_count'] == 0
    assert empty_res['extra']['placeholder_count'] == 0


def test_member_extra_exposes_source_and_counts(warm_ctx, monkeypatch):
    account, event, _, _ = warm_ctx
    store.upsert_group(account.hash, 'g_src', members_state='complete', verified_at=12345)
    store.upsert_member(
        account.hash, 'g_src', 'm_api',
        username='接口成员', bot=False, union_openid='u1', source='api',
        updated_at=int(time.time())
    )
    store.upsert_member(
        account.hash, 'g_src', 'm_evt',
        source='event', updated_at=int(time.time()) - 61 * 86400
    )

    result = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_src')
    assert result['active'] is True
    assert result['extra']['complete'] is True
    assert result['extra']['partial'] is False
    assert result['extra']['verified_at'] == 12345
    assert result['extra']['stale_count'] == 1
    assert result['extra']['placeholder_count'] == 1
    by_id = {m['user_id']: m for m in result['data']}
    assert by_id['m_api']['extra']['source'] == 'api'
    assert by_id['m_api']['extra']['cached'] is True
    assert by_id['m_api']['extra']['bot'] is False
    assert by_id['m_api']['extra']['union_openid'] == 'u1'
    assert by_id['m_api']['extra']['stale'] is False
    assert 'updated_at' in by_id['m_api']['extra']
    assert by_id['m_evt']['extra']['source'] == 'event'
    assert by_id['m_evt']['extra']['stale'] is True


def test_warm_multi_round_25_pages_reconciles_departed_members(warm_ctx, monkeypatch):
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmPageBatch', 10)
    monkeypatch.setattr(common, 'sdkQQGroupWarmMaxRounds', 10)

    base_ts = int(time.time())
    # 预置旧缓存：含 25 页里的在群成员与 2 个已离群成员。
    store.touch_group(account.hash, 'g_25p')
    store.upsert_member(account.hash, 'g_25p', 'm_gone_1', username='离群1', updated_at=base_ts - 100)
    store.upsert_member(account.hash, 'g_25p', 'm_gone_2', username='离群2', updated_at=base_ts - 100)
    store.upsert_member(account.hash, 'g_25p', 'm_new_evt', username='同步中入群', updated_at=base_ts + 50)

    pages = {}
    expected_present = set()
    for page_idx in range(25):
        cursor = '' if page_idx == 0 else 'c_%d' % page_idx
        next_cursor = '' if page_idx == 24 else 'c_%d' % (page_idx + 1)
        member_id = 'm_p%02d' % page_idx
        expected_present.add(member_id)
        pages[cursor] = (200, {
            'members': [{'member_openid': member_id, 'username': '成员%d' % page_idx}],
            'next_cursor': next_cursor
        })
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api(pages))

    key = (str(account.hash), 'g_25p')
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_25p', start_cursor='') is True
    assert key in common.sdkQQGroupWarmSeen

    # 第 1 轮（10 页）：未完成，不删离群成员，seen 累积 10 人。
    assert common._qq_group_warm_step() is True
    assert len(common.sdkQQGroupWarmSeen[key]) == 10
    assert 'm_gone_1' in store.get_members(account.hash, 'g_25p')

    # 第 2 轮（10 页）：未完成，不删离群成员，seen 累积 20 人。
    assert common._qq_group_warm_step() is True
    assert len(common.sdkQQGroupWarmSeen[key]) == 20
    assert 'm_gone_1' in store.get_members(account.hash, 'g_25p')

    # 第 3 轮（5 页）：翻到末页，差集删除 m_gone_1/m_gone_2，保留 25 人与同步中入群的 m_new_evt，清理 seen。
    assert common._qq_group_warm_step() is True
    final_members = set(store.get_members(account.hash, 'g_25p'))
    assert final_members == expected_present | {'m_new_evt'}
    assert store.get_group(account.hash, 'g_25p')['members_state'] == 'complete'
    assert key not in common.sdkQQGroupWarmSeen
    assert key not in common.sdkQQGroupWarmPending


def test_warm_multi_round_mid_failure_preserves_members_and_clears_seen(warm_ctx, monkeypatch):
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmPageBatch', 10)
    monkeypatch.setattr(common, 'sdkQQGroupWarmMaxRounds', 10)

    base_ts = int(time.time())
    store.touch_group(account.hash, 'g_25p_fail')
    store.upsert_member(account.hash, 'g_25p_fail', 'm_old', username='旧成员', updated_at=base_ts - 100)

    pages = {}
    for page_idx in range(15):
        cursor = '' if page_idx == 0 else 'c_%d' % page_idx
        next_cursor = 'c_%d' % (page_idx + 1)
        pages[cursor] = (200, {
            'members': [{'member_openid': 'm_p%02d' % page_idx, 'username': '成员%d' % page_idx}],
            'next_cursor': next_cursor
        })
    pages['c_15'] = (500, {'code': 99999, 'message': 'server error'})
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api(pages))

    key = (str(account.hash), 'g_25p_fail')
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_25p_fail', start_cursor='') is True
    # 第 1 轮成功（10 页），第 2 轮在第 16 页失败 -> 绝不触发差集，且清理 seen。
    assert common._qq_group_warm_step() is True
    assert common._qq_group_warm_step() is True
    members_after = store.get_members(account.hash, 'g_25p_fail')
    assert 'm_old' in members_after
    assert 'm_p00' in members_after
    assert 'm_p14' in members_after
    assert store.get_group(account.hash, 'g_25p_fail')['members_state'] == 'active'
    assert key not in common.sdkQQGroupWarmSeen
    assert key not in common.sdkQQGroupWarmPending


def test_warm_queue_overflow_also_drops_oldest_seen(warm_ctx, monkeypatch):
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmQueueMaxSize', 2)

    for gid in ('g_a', 'g_b', 'g_c'):
        store.touch_group(account.hash, gid)
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_a', start_cursor='') is True
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_b', start_cursor='') is True
    assert (str(account.hash), 'g_a') in common.sdkQQGroupWarmSeen
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_c', start_cursor='') is True
    assert (str(account.hash), 'g_a') not in common.sdkQQGroupWarmSeen
    assert (str(account.hash), 'g_b') in common.sdkQQGroupWarmSeen
    assert (str(account.hash), 'g_c') in common.sdkQQGroupWarmSeen
    assert (str(account.hash), 'g_a') not in common.sdkQQGroupWarmStartedAt
    assert (str(account.hash), 'g_b') in common.sdkQQGroupWarmStartedAt
    assert (str(account.hash), 'g_c') in common.sdkQQGroupWarmStartedAt


def test_warm_multi_round_uses_initial_scan_started_at_cutoff(warm_ctx, monkeypatch):
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmPageBatch', 1)
    monkeypatch.setattr(common, 'sdkQQGroupWarmMaxRounds', 5)

    wall = [10000]
    monkeypatch.setattr(common.time, 'time', lambda: wall[0])
    monkeypatch.setattr(store.time, 'time', lambda: wall[0])

    store.touch_group(account.hash, 'g_cutoff')
    store.upsert_member(account.hash, 'g_cutoff', 'm_old_gone', username='旧离群', updated_at=9900)
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (200, {'members': [{'member_openid': 'm_p1', 'username': 'u1'}], 'next_cursor': 'c2'}),
        'c2': (200, {'members': [{'member_openid': 'm_p2', 'username': 'u2'}], 'next_cursor': ''}),
    }))

    key = (str(account.hash), 'g_cutoff')
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_cutoff', start_cursor='') is True
    assert common.sdkQQGroupWarmStartedAt[key] == 10000

    # 第 1 轮后推进时间，并在同步期间有新成员入群发言（updated_at=10010 > 10000，但 < 末轮时间 10050）。
    assert common._qq_group_warm_step() is True
    wall[0] = 10010
    store.upsert_member(account.hash, 'g_cutoff', 'm_mid_join', username='同步中入群', updated_at=10010)
    wall[0] = 10050
    assert common._qq_group_warm_step() is True

    members = set(store.get_members(account.hash, 'g_cutoff'))
    assert members == {'m_p1', 'm_p2', 'm_mid_join'}
    assert key not in common.sdkQQGroupWarmStartedAt


def test_warm_rate_limited_preserves_progress_and_abandons_after_10(warm_ctx, monkeypatch):
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmPageBatch', 1)
    monkeypatch.setattr(common, 'sdkQQGroupWarmMaxRounds', 10)

    clock = [500.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])

    store.touch_group(account.hash, 'g_rl')
    call_count = [0]

    def fake_api_req(bot_info, api_obj, req_type, op_key, wait=False):
        call_count[0] += 1
        cursor = '' if not api_obj.query else api_obj.query.get('cursor', '')
        if call_count[0] == 1:
            return {
                'active': True, 'http_status': 200, 'error_code': None, 'error': None,
                'response': {'members': [{'member_openid': 'm1', 'username': 'u1'}], 'next_cursor': 'c2'},
                'raw_response': '{}', 'denied': False, 'rate_limited': False, 'backed_off': False
            }
        if call_count[0] == 2:
            # 模拟本地限流：http_status=None，不应计入 pages 预算。
            return {
                'active': False, 'http_status': None, 'error_code': None, 'error': 'rate limit',
                'response': None, 'raw_response': None, 'denied': False, 'rate_limited': True,
                'backed_off': False
            }
        assert cursor == 'c2'
        return {
            'active': True, 'http_status': 200, 'error_code': None, 'error': None,
            'response': {'members': [{'member_openid': 'm2', 'username': 'u2'}], 'next_cursor': ''},
            'raw_response': '{}', 'denied': False, 'rate_limited': False, 'backed_off': False
        }

    monkeypatch.setattr(common, '_do_qq_group_api_request', fake_api_req)
    key = (str(account.hash), 'g_rl')
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_rl', start_cursor='') is True

    # 第 1 轮成功拉 1 页（预算 +1）
    assert common._qq_group_warm_step() is True
    day_key = common._get_qq_group_warm_daily_key(account.hash)
    assert common.sdkQQGroupWarmDailyPages[day_key] == 1

    # 第 2 轮触发限流：保留 cursor='c2'、seen、rounds=1、pending、started_at，预算不增加，按 bot 设 30s 冷却。
    assert common._qq_group_warm_step() is True
    assert common.sdkQQGroupWarmDailyPages[day_key] == 1
    assert key in common.sdkQQGroupWarmPending
    assert common.sdkQQGroupWarmSeen[key] == {'m1'}
    assert key in common.sdkQQGroupWarmStartedAt
    assert common.sdkQQGroupWarmQueue[0][3] == 'c2'
    assert common.sdkQQGroupWarmQueue[0][4] == 1
    assert common.sdkQQGroupWarmQueue[0][5] == 1
    assert common.sdkQQGroupWarmRateLimitUntilByBot[str(account.hash)] == (
        500.0 + common.sdkQQGroupWarmRateLimitWait
    )

    # 冷却期内跳过该 bot 并给出最短剩余等待时间。
    processed, wait_sec = common._qq_group_warm_step_with_wait()
    assert processed is False
    assert wait_sec == common.sdkQQGroupWarmRateLimitWait

    # 冷却到期后第 3 轮恢复成功并 complete。
    clock[0] += common.sdkQQGroupWarmRateLimitWait
    assert common._qq_group_warm_step() is True
    assert store.get_group(account.hash, 'g_rl')['members_state'] == 'complete'
    assert set(store.get_members(account.hash, 'g_rl')) == {'m1', 'm2'}
    assert key not in common.sdkQQGroupWarmPending

    # 连续 10 次限流才放弃并进入失败冷却。
    def always_rate_limited(bot_info, api_obj, req_type, op_key, wait=False):
        return {
            'active': False, 'http_status': None, 'error_code': None, 'error': 'rate limit',
            'response': None, 'raw_response': None, 'denied': False, 'rate_limited': True,
            'backed_off': False
        }

    monkeypatch.setattr(common, '_do_qq_group_api_request', always_rate_limited)
    store.touch_group(account.hash, 'g_rl10')
    key10 = (str(account.hash), 'g_rl10')
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_rl10', start_cursor='') is True
    for idx in range(9):
        assert common._qq_group_warm_step() is True
        assert key10 in common.sdkQQGroupWarmPending
        assert common.sdkQQGroupWarmQueue[0][5] == idx + 1
        clock[0] += common.sdkQQGroupWarmRateLimitWait
    # 第 10 次限流放弃。
    assert common._qq_group_warm_step() is True
    assert key10 not in common.sdkQQGroupWarmPending
    assert key10 not in common.sdkQQGroupWarmSeen
    assert key10 not in common.sdkQQGroupWarmStartedAt
    assert store.get_group(account.hash, 'g_rl10')['members_state'] == 'active'
    assert key10 in common.sdkQQGroupWarmFailCooldown


def test_warm_failure_does_not_resurrect_removed_or_downgrade_complete_group(warm_ctx, monkeypatch):
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())

    # 场景 1：任务在途期间群被 remove_group，执行前校验直接丢弃且不得复活群行。
    store.touch_group(account.hash, 'g_removed')
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_removed', start_cursor='') is True
    store.remove_group(account.hash, 'g_removed')

    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (500, {'code': 99999, 'message': 'err'})
    }))
    assert common._qq_group_warm_step() is True
    assert store.get_group(account.hash, 'g_removed') is None

    # 场景 2：群不存在时入队直接返回 False 且不复活群行。
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_removed', start_cursor='') is False
    assert store.get_group(account.hash, 'g_removed') is None

    # 场景 3：已 complete 的群默认入队拒绝；定期校准 allow_complete=True 重排失败也不降级为 active。
    store.upsert_group(account.hash, 'g_done', members_state='complete', verified_at=100)
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_done', start_cursor='') is False
    assert common._enqueue_qq_group_warm(
        account.hash, sdk_bot, 'g_done', start_cursor='', allow_complete=True
    ) is True
    assert store.get_group(account.hash, 'g_done')['members_state'] == 'complete'
    assert common._qq_group_warm_step() is True
    assert store.get_group(account.hash, 'g_done')['members_state'] == 'complete'


def test_get_group_member_list_does_not_set_warming_when_enqueue_fails(warm_ctx, monkeypatch):
    account, event, _, _ = warm_ctx
    monkeypatch.setattr(group_mod, '_enqueue_qq_group_warm', lambda *args, **kwargs: False)

    # 场景 1：缓存为空、首屏有下一页，但入队返回 False -> members_state 保持 active。
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (200, {'members': [{'member_openid': 'm1', 'username': 'u1'}], 'next_cursor': 'c2'})
    }))
    res1 = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_enq_fail_1')
    assert res1['active'] is True
    assert store.get_group(account.hash, 'g_enq_fail_1')['members_state'] == 'active'

    # 场景 2：缓存非空、未 complete，入队返回 False -> members_state 保持 active。
    store.upsert_group(account.hash, 'g_enq_fail_2', state='active', members_state='active')
    store.upsert_member(account.hash, 'g_enq_fail_2', 'm1', username='u1', source='event')
    res2 = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_enq_fail_2')
    assert res2['active'] is True
    assert store.get_group(account.hash, 'g_enq_fail_2')['members_state'] == 'active'


def test_warm_fail_cooldown_and_non_active_group_skip(warm_ctx, monkeypatch):
    account, event, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    clock = [1000.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])

    # 失败后进入 300s 冷却，期间不重排；满 300s 恢复可入队。
    store.upsert_group(account.hash, 'g_cd', state='active', members_state='active')
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (500, {'code': 99999, 'message': 'err'})
    }))
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_cd', start_cursor='') is True
    assert store.get_group(account.hash, 'g_cd')['members_state'] == 'warming'
    assert common._qq_group_warm_step() is True
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_cd', start_cursor='') is False
    clock[0] += 299.0
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_cd', start_cursor='') is False
    clock[0] += 1.0
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_cd', start_cursor='') is True

    # 非空缓存分支跳过 suspect / dormant 群，不投递续翻。
    store.upsert_group(account.hash, 'g_sus_skip', state='suspect', members_state='active')
    store.upsert_member(account.hash, 'g_sus_skip', 'm1', username='u1')
    store.upsert_group(account.hash, 'g_dorm_skip', state='dormant', members_state='active')
    store.upsert_member(account.hash, 'g_dorm_skip', 'm2', username='u2')
    enq_spy = Mock(return_value=True)
    monkeypatch.setattr(group_mod, '_enqueue_qq_group_warm', enq_spy)
    OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_sus_skip')
    OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_dorm_skip')
    enq_spy.assert_not_called()


def test_warm_queue_rejects_and_evicts_exhausted_bot_first(warm_ctx, monkeypatch):
    account_a, _, sdk_bot_a, _ = warm_ctx
    account_b = OlivOS.API.bot_info_T(
        id=456, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model='public'
    )
    sdk_bot_b = common.get_SDK_bot_info_from_Plugin_bot_info(account_b)
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmQueueMaxSize', 2)
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPageLimit', 5)

    for bh, gid in (
        (account_b.hash, 'g_b1'),
        (account_a.hash, 'g_a1'),
        (account_a.hash, 'g_a2'),
        (account_b.hash, 'g_b2'),
    ):
        store.touch_group(bh, gid)

    # 先让 bot_b 入队（更早），再让 bot_a 入队（更晚）。
    assert common._enqueue_qq_group_warm(account_b.hash, sdk_bot_b, 'g_b1') is True
    assert common._enqueue_qq_group_warm(account_a.hash, sdk_bot_a, 'g_a1') is True

    # bot_a 预算耗尽后：新任务直接拒绝；bot_b 再入队满员时优先淘汰 bot_a 的 g_a1 而保留更旧的 g_b1。
    common._add_qq_group_warm_daily_pages(account_a.hash, 5)
    assert common._enqueue_qq_group_warm(account_a.hash, sdk_bot_a, 'g_a2') is False
    assert common._enqueue_qq_group_warm(account_b.hash, sdk_bot_b, 'g_b2') is True
    queued = [(t[0], t[2]) for t in common.sdkQQGroupWarmQueue]
    assert queued == [(str(account_b.hash), 'g_b1'), (str(account_b.hash), 'g_b2')]
    assert (str(account_a.hash), 'g_a1') not in common.sdkQQGroupWarmPending


def test_placeholder_count_requires_both_username_and_member_nickname_empty(warm_ctx):
    account, event, _, _ = warm_ctx
    store.upsert_group(account.hash, 'g_ph_cnt', members_state='complete', verified_at=100)
    store.upsert_member(account.hash, 'g_ph_cnt', 'm_both_empty', source='event')
    store.upsert_member(account.hash, 'g_ph_cnt', 'm_card_only', member_nickname='只有群名片', source='event')
    store.upsert_member(account.hash, 'g_ph_cnt', 'm_name_only', username='只有昵称', source='event')
    res = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_ph_cnt')
    assert res['extra']['placeholder_count'] == 1


def test_immediate_worker_failure_does_not_get_overwritten_back_to_warming(warm_ctx, monkeypatch):
    """复现 G3：worker 在入队返回前立刻失败并复位 active，主线程不会把状态打回 warming。"""
    account, event, _, _ = warm_ctx
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (200, {'members': [{'member_openid': 'm1', 'username': 'u1'}], 'next_cursor': 'c2'}),
        'c2': (500, {'code': 99999, 'message': 'immediate fail'}),
    }))
    # 模拟 worker 在 _ensure_qq_group_warm_thread 被调起的瞬间同步跑完一步并失败复位。
    monkeypatch.setattr(
        common, '_ensure_qq_group_warm_thread', lambda: common._qq_group_warm_step()
    )

    res = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_race_fail')
    assert res['active'] is True
    assert store.get_group(account.hash, 'g_race_fail')['members_state'] == 'active'
    assert res['extra']['members_state'] == 'active'


def test_reset_dropped_warm_groups_preserves_reenqueued_seen_and_started_at(warm_ctx, monkeypatch):
    """_reset_dropped_warm_groups 仅负责锁外复位 DB warming 状态，不修改内存 Pending/Seen/StartedAt。"""
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    store.touch_group(account.hash, 'g_reenq')
    assert common._enqueue_qq_group_warm(
        account.hash, sdk_bot, 'g_reenq', start_cursor='', initial_seen={'m_keep'}, scan_started_at=12345
    ) is True
    key = (str(account.hash), 'g_reenq')
    common._reset_dropped_warm_groups([key])
    assert key in common.sdkQQGroupWarmPending
    assert common.sdkQQGroupWarmSeen[key] == {'m_keep'}
    assert common.sdkQQGroupWarmStartedAt[key] == 12345
    assert store.get_group(account.hash, 'g_reenq')['members_state'] == 'active'


def test_warm_eviction_concurrent_reenqueue_does_not_stick_warming(warm_ctx, monkeypatch):
    """复现 M1：队列满淘汰复位期间并发重入被 Pending 阻挡，不会导致群永久卡在 warming。"""
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmQueueMaxSize', 1)

    store.touch_group(account.hash, 'g_evict')
    store.touch_group(account.hash, 'g_new')
    assert common._enqueue_qq_group_warm(
        account.hash, sdk_bot, 'g_evict', start_cursor='', initial_seen={'m0'}, scan_started_at=1000
    ) is True
    evict_key = (str(account.hash), 'g_evict')
    assert store.get_group(account.hash, 'g_evict')['members_state'] == 'warming'

    entered_reset = threading.Event()
    release_reset = threading.Event()
    orig_reset = common._reset_qq_group_warming_state

    def blocking_reset(bh, gid):
        if gid == 'g_evict':
            entered_reset.set()
            assert release_reset.wait(timeout=5.0)
        return orig_reset(bh, gid)

    monkeypatch.setattr(common, '_reset_qq_group_warming_state', blocking_reset)

    evict_result = []

    def run_enqueue_new():
        evict_result.append(common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_new', start_cursor=''))

    thread_a = threading.Thread(target=run_enqueue_new, daemon=True)
    thread_a.start()
    assert entered_reset.wait(timeout=5.0)

    # 复位尚未完成前：Queue/Seen/StartedAt 已清理，但 Pending 仍占位以挡住并发重入。
    assert evict_key in common.sdkQQGroupWarmPending
    assert evict_key not in common.sdkQQGroupWarmSeen
    assert evict_key not in common.sdkQQGroupWarmStartedAt
    assert [(t[0], t[2]) for t in common.sdkQQGroupWarmQueue] == [(str(account.hash), 'g_new')]
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_evict', start_cursor='') is False

    # 放行复位后：DB 正确回到 active 且 Pending 释放，不卡 warming。
    release_reset.set()
    thread_a.join(timeout=5.0)
    assert not thread_a.is_alive()
    assert evict_result == [True]
    assert evict_key not in common.sdkQQGroupWarmPending
    assert store.get_group(account.hash, 'g_evict')['members_state'] == 'active'

    # 复位完成后再次重入，新任务可正常接管并进入队列。
    monkeypatch.setattr(common, '_reset_qq_group_warming_state', orig_reset)
    monkeypatch.setattr(common, 'sdkQQGroupWarmQueueMaxSize', 2)
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_evict', start_cursor='') is True
    assert evict_key in common.sdkQQGroupWarmPending
    assert store.get_group(account.hash, 'g_evict')['members_state'] == 'warming'

    # 复位抛异常时，finally 仍必须释放 Pending，避免永久占坑。
    monkeypatch.setattr(common, 'sdkQQGroupWarmQueueMaxSize', 1)
    common.sdkQQGroupWarmQueue.clear()
    common.sdkQQGroupWarmPending.clear()
    store.upsert_group(account.hash, 'g_err_old', state='active', members_state='active')
    store.upsert_group(account.hash, 'g_err_new', state='active', members_state='active')
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_err_old', start_cursor='') is True
    monkeypatch.setattr(
        common, '_reset_qq_group_warming_state', Mock(side_effect=RuntimeError('db fail'))
    )
    with pytest.raises(RuntimeError, match='db fail'):
        common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_err_new', start_cursor='')
    assert (str(account.hash), 'g_err_old') not in common.sdkQQGroupWarmPending


def test_get_group_member_list_empty_fetch_failure_does_not_reset_concurrent_warming(warm_ctx, monkeypatch):
    """复现 S2：空缓存失败分支不再复位 warming，避免误重置并发任务的 warming 状态。"""
    account, event, _, _ = warm_ctx

    def concurrent_warming_fetch(
        bot_info, group_openid, bot_hash=None, wait=False, max_pages=1,
        reconcile=False, sync_started_at=None
    ):
        store.touch_group(bot_hash, group_openid)
        store.upsert_member(bot_hash, group_openid, 'm1', username='部分成员', source='api')
        # 模拟并发路径已将该群置为 warming。
        assert store.mark_group_warming(bot_hash, group_openid) is True
        return {
            'ok': False,
            'error': 'rate limit',
            'denied': False,
            'rate_limited': True,
            'pages': 1,
            'members': 1,
            'next_cursor': 'c1',
            'complete': False,
            'truncated': False
        }

    monkeypatch.setattr(group_mod, '_qq_group_fetch_member_pages', concurrent_warming_fetch)
    res = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_s2_keep')
    assert res['active'] is True
    assert store.get_group(account.hash, 'g_s2_keep')['members_state'] == 'warming'
    assert res['extra']['members_state'] == 'warming'


def test_warm_step_skips_suspect_group_and_empty_cache_skips_suspect(warm_ctx, monkeypatch):
    """复现 G7：续翻前校验群状态（suspect/已删不发请求）；空缓存分支跳过 suspect。"""
    account, event, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    api_called = Mock(side_effect=AssertionError('suspect 群不应发起成员列表请求'))
    monkeypatch.setattr(common.API, 'getQQGroupMembers', api_called)

    # 1. 入队时 active，执行前变为 suspect -> warm step 直接丢弃、复位 warming，不发请求。
    store.touch_group(account.hash, 'g_turn_sus')
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_turn_sus', start_cursor='') is True
    assert store.get_group(account.hash, 'g_turn_sus')['members_state'] == 'warming'
    assert store.mark_group_suspect(account.hash, 'g_turn_sus') is True
    assert common._qq_group_warm_step() is True
    api_called.assert_not_called()
    assert store.get_group(account.hash, 'g_turn_sus')['members_state'] == 'active'
    assert (str(account.hash), 'g_turn_sus') not in common.sdkQQGroupWarmPending
    assert (str(account.hash), 'g_turn_sus') not in common.sdkQQGroupWarmSeen

    # 2. 空缓存分支遇到 suspect 群：既不发同步拉取也不入队。
    store.upsert_group(account.hash, 'g_empty_sus', state='suspect', members_state='active')
    res = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_empty_sus')
    assert res['active'] is False
    assert res['data'] == []
    assert len(common.sdkQQGroupWarmQueue) == 0
    api_called.assert_not_called()


def test_warm_backoff_goes_to_failure_not_rate_limit(warm_ctx, monkeypatch):
    """复现 G2：群级退避（100017/11255）走失败冷却，不设 bot 限流等待、不冻结 worker。"""
    account, _, sdk_bot, _ = warm_ctx
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    store.touch_group(account.hash, 'g_bo')
    common._set_qq_group_api_backoff(account.hash, 'group_member_list', 'g_bo', 3600.0)
    assert common._enqueue_qq_group_warm(account.hash, sdk_bot, 'g_bo', start_cursor='') is True
    assert common._qq_group_warm_step() is True
    key = (str(account.hash), 'g_bo')
    assert key not in common.sdkQQGroupWarmPending
    assert len(common.sdkQQGroupWarmQueue) == 0
    assert str(account.hash) not in common.sdkQQGroupWarmRateLimitUntilByBot
    assert key in common.sdkQQGroupWarmFailCooldown
    assert store.get_group(account.hash, 'g_bo')['members_state'] == 'active'


def test_real_warm_worker_rate_limit_preserves_progress_without_starving_other_bot(warm_ctx, monkeypatch):
    """真实链路（建议 5.2）：真 worker + 真 _do_qq_group_api_request，bot A 打满窗口保留进度且不饿死 bot B。"""
    account_a, _, sdk_bot_a, _ = warm_ctx
    account_b = OlivOS.API.bot_info_T(
        id=456, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model='public'
    )
    sdk_bot_b = common.get_SDK_bot_info_from_Plugin_bot_info(account_b)

    # 缩小滑动窗口与冷却时间，让真实多线程 worker 在百毫秒级走完多轮。
    monkeypatch.setitem(common.qqGroupApiRateLimitMap, 'group_member_list', 1)
    monkeypatch.setattr(common, 'qqGroupApiRateWindow', 0.08)
    monkeypatch.setattr(common, 'sdkQQGroupWarmRateLimitWait', 0.09)
    monkeypatch.setattr(common, 'sdkQQGroupWarmPageBatch', 2)
    monkeypatch.setattr(common, 'sdkQQGroupWarmSpacing', 0.0)

    store.touch_group(account_a.hash, 'g_a')
    store.touch_group(account_b.hash, 'g_b')

    events_order = []
    pages = {
        ('g_a', ''): (200, {'members': [{'member_openid': 'a1', 'username': 'A1'}], 'next_cursor': 'ac2'}),
        ('g_a', 'ac2'): (200, {'members': [{'member_openid': 'a2', 'username': 'A2'}], 'next_cursor': ''}),
        ('g_b', ''): (200, {'members': [{'member_openid': 'b1', 'username': 'B1'}], 'next_cursor': ''}),
    }

    class StubMembersAPI(object):
        def __init__(self, sdk_bot):
            self.bot_info = sdk_bot
            self.metadata = SimpleNamespace(group_openid=None)
            self.query = None
            self.res = None
            self.res_code = 200

        def do_api(self, method='GET'):
            gid = self.metadata.group_openid
            cursor = '' if not self.query else self.query.get('cursor', '')
            events_order.append((gid, cursor))
            status, body = pages[(gid, cursor)]
            self.res_code = status
            self.res = json.dumps(body)
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupMembers', StubMembersAPI)

    assert common._enqueue_qq_group_warm(account_a.hash, sdk_bot_a, 'g_a', start_cursor='') is True
    assert common._enqueue_qq_group_warm(account_b.hash, sdk_bot_b, 'g_b', start_cursor='') is True

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        ra = store.get_group(account_a.hash, 'g_a')
        rb = store.get_group(account_b.hash, 'g_b')
        if (
            ra and ra['members_state'] == 'complete'
            and rb and rb['members_state'] == 'complete'
            and not common.sdkQQGroupWarmPending
        ):
            break
        time.sleep(0.01)

    assert store.get_group(account_a.hash, 'g_a')['members_state'] == 'complete'
    assert store.get_group(account_b.hash, 'g_b')['members_state'] == 'complete'
    assert set(store.get_members(account_a.hash, 'g_a')) == {'a1', 'a2'}
    assert set(store.get_members(account_b.hash, 'g_b')) == {'b1'}
    # bot A 第一页耗尽自身 1-req 窗口后在第二页限流，此时 bot B 应抢先完成，随后 bot A 从 ac2 续翻完成。
    assert events_order == [('g_a', ''), ('g_b', ''), ('g_a', 'ac2')]

    # 显式停止并等待真实 worker 线程退出。
    worker_thread = common.sdkQQGroupWarmThread
    common.sdkQQGroupWarmThread = None
    common.sdkQQGroupWarmEvent.set()
    if worker_thread is not None:
        worker_thread.join(timeout=2.0)
        assert not worker_thread.is_alive()
