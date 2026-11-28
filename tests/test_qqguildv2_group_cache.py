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

from collections import deque
import json
import threading
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
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPages', {})
    monkeypatch.setattr(common, 'sdkQQGroupTier1Queue', deque())
    monkeypatch.setattr(common, 'sdkQQGroupTier1Delayed', [])
    monkeypatch.setattr(common, 'sdkQQGroupTier1Pending', set())
    monkeypatch.setattr(common, 'sdkQQGroupTier1Thread', None)
    monkeypatch.setattr(common, 'sdkQQGroupTier1Event', threading.Event())
    monkeypatch.setattr(common, 'sdkQQGroupTier1Spacing', 0.0)
    monkeypatch.setattr(common, 'sdkUserInfo', {})
    monkeypatch.setattr(common, 'sdkQQUserInfoMinorLogged', {})
    monkeypatch.setattr(common, 'sdkQQGroupRefreshCooldown', {})
    proc = SimpleNamespace(log=Mock())
    monkeypatch.setattr(OlivOS.pluginAPI, 'gProc', proc)
    bot = common.bot_info_T(id=123, model='public')
    bot_hash = OlivOS.API.getBotHash(
        bot_id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    yield bot, bot_hash, proc
    current_thread = threading.current_thread()
    suspect_thread = common.sdkQQGroupSuspectThread
    common.sdkQQGroupSuspectThread = None
    common.sdkQQGroupSuspectEvent.set()
    warm_thread = common.sdkQQGroupWarmThread
    common.sdkQQGroupWarmThread = None
    common.sdkQQGroupWarmEvent.set()
    tier1_thread = common.sdkQQGroupTier1Thread
    common.sdkQQGroupTier1Thread = None
    common.sdkQQGroupTier1Event.set()
    for thread in (suspect_thread, warm_thread, tier1_thread):
        if (
            thread is not None
            and thread is not current_thread
            and callable(getattr(thread, 'join', None))
            and callable(getattr(thread, 'is_alive', None))
            and thread.is_alive()
        ):
            thread.join(timeout=2.0)
    store.close_db()


def response_api(code, group='group'):
    return SimpleNamespace(
        metadata=SimpleNamespace(group_openid=group),
        res=json.dumps({'code': code}), res_code=400, do_api=Mock()
    )


def test_11253_disables_interface_permanently_and_logs_once(group_api, monkeypatch):
    bot, bot_hash, proc = group_api
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    api = response_api(11253)
    first = common._do_qq_group_api_request(bot, api, 'GET', 'group_member_info')
    clock[0] += 100000
    second = common._do_qq_group_api_request(bot, api, 'GET', 'group_member_info')
    common._mark_qq_group_api_denied(bot_hash, 'group_member_info')
    assert first['denied'] and second['denied']
    assert api.do_api.call_count == 1
    assert proc.log.call_count == 1


@pytest.mark.parametrize('payload,expected_primary', [
    ({'code': 11253, 'err_code': 40012010, 'message': '应用无接口访问权限'}, 40012010),
    ({'code': 11253, 'err_code': 40099999, 'message': '应用无接口访问权限'}, 40099999),
    ({'err_code': 40012010, 'message': '应用无接口访问权限'}, 40012010),
    ({'code': 11253, 'err_code': None, 'message': '应用无接口访问权限'}, 11253),
])
def test_dual_code_11253_and_40012010_disables_interface_permanently(
    group_api, payload, expected_primary
):
    bot, bot_hash, proc = group_api
    api = SimpleNamespace(
        metadata=SimpleNamespace(group_openid='group'),
        res=json.dumps(payload, ensure_ascii=False),
        res_code=400,
        do_api=Mock()
    )
    first = common._do_qq_group_api_request(bot, api, 'GET', 'group_member_list')
    second = common._do_qq_group_api_request(bot, api, 'GET', 'group_member_list')
    assert first['active'] is False
    assert first['denied'] is True
    assert first['http_status'] == 400
    assert first['error_code'] == expected_primary
    assert second['denied'] is True
    assert common._check_qq_group_api_denied(bot_hash, 'group_member_list') is True
    assert api.do_api.call_count == 1
    assert proc.log.call_count == 1


def test_dual_code_11255_still_marks_group_suspect(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    scheduled = []
    monkeypatch.setattr(
        common,
        '_schedule_qq_group_suspect_verify',
        lambda bh, bi, gid: scheduled.append((bh, gid)) or True
    )
    store.touch_group(bot_hash, 'group')
    api = SimpleNamespace(
        metadata=SimpleNamespace(group_openid='group'),
        res=json.dumps({'code': 11255, 'err_code': 40099998, 'message': 'group error'}),
        res_code=400,
        do_api=Mock()
    )
    res = common._do_qq_group_api_request(bot, api, 'GET', 'group_member_list')
    assert res['denied'] is False
    assert res['error_code'] == 40099998
    assert store.get_group(bot_hash, 'group')['state'] == 'suspect'
    assert scheduled == [(str(bot_hash), 'group')]


def test_11255_marks_group_suspect_and_preserves_members(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    scheduled = []
    monkeypatch.setattr(
        common,
        '_schedule_qq_group_suspect_verify',
        lambda bh, bi, gid: scheduled.append((bh, gid)) or True
    )
    store.touch_group(bot_hash, 'group')
    store.upsert_member(bot_hash, 'group', 'member', username='test')
    api = response_api(11255)
    common._do_qq_group_api_request(bot, api, 'GET', 'group_member_list')
    group_row = store.get_group(bot_hash, 'group')
    assert group_row is not None
    assert group_row['state'] == 'suspect'
    assert 'member' in store.get_members(bot_hash, 'group')
    assert scheduled == [(str(bot_hash), 'group')]


def test_11253_and_calibration_isolated_per_bot(group_api, monkeypatch):
    bot_a, hash_a, _ = group_api
    bot_b = common.bot_info_T(id=456, model='public')
    hash_b = OlivOS.API.getBotHash(
        bot_id=bot_b.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot_b.model
    )
    common.sdkQQGroupCalibrationGroups[str(hash_a)] = {'g_a': 0.0}
    common.sdkQQGroupCalibrationGroups[str(hash_b)] = {'g_b': 0.0}

    denied_api = response_api(11253, group='g_a')
    res_a = common._do_qq_group_api_request(bot_a, denied_api, 'GET', 'group_member_list')
    assert res_a['denied'] is True
    assert str(hash_a) not in common.sdkQQGroupCalibrationGroups
    assert str(hash_b) in common.sdkQQGroupCalibrationGroups

    ok_api = SimpleNamespace(
        metadata=SimpleNamespace(group_openid='g_b'),
        res=json.dumps({'members': []}), res_code=200, do_api=Mock()
    )
    res_b = common._do_qq_group_api_request(bot_b, ok_api, 'GET', 'group_member_list')
    assert res_b['active'] is True
    assert ok_api.do_api.call_count == 1


def test_rate_limit_window_isolated_per_bot(group_api, monkeypatch):
    _, hash_a, _ = group_api
    hash_b = 'bot_hash_b'
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    limit = common.qqGroupApiRateLimitMap['group_member_list']
    for _ in range(limit):
        assert common._acquire_qq_group_api_rate(hash_a, 'group_member_list') is True
    assert common._acquire_qq_group_api_rate(hash_a, 'group_member_list') is False
    # 另一个 bot 有独立的 60 QPM 配额，不受 bot A 影响。
    for _ in range(limit):
        assert common._acquire_qq_group_api_rate(hash_b, 'group_member_list') is True
    assert common._acquire_qq_group_api_rate(hash_b, 'group_member_list') is False


def test_suspect_verify_200_restores_active(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_schedule_qq_group_suspect_verify', lambda *args: True)

    store.touch_group(bot_hash, 'g1')
    store.upsert_member(bot_hash, 'g1', 'm1', username='alice')
    common._do_qq_group_api_request(bot, response_api(11255, 'g1'), 'GET', 'group_member_list')
    assert store.get_group(bot_hash, 'g1')['state'] == 'suspect'

    class OkBotState(object):
        def __init__(self, bot_info):
            self.metadata = SimpleNamespace(group_openid=None)
            self.res = json.dumps({'member_openid': 'bot', 'member_role': 'member'})
            self.res_code = 200

        def do_api(self, method):
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupBotState', OkBotState)
    clock[0] += 600.0
    common._verify_qq_group_suspect(bot_hash, bot, 'g1')
    assert store.get_group(bot_hash, 'g1')['state'] == 'active'
    assert (str(bot_hash), 'g1') not in common.sdkQQGroupSuspectState
    assert 'm1' in store.get_members(bot_hash, 'g1')


def test_suspect_verify_11253_keeps_suspect_and_logs(group_api, monkeypatch):
    bot, bot_hash, proc = group_api
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_schedule_qq_group_suspect_verify', lambda *args: True)

    store.touch_group(bot_hash, 'g2')
    store.upsert_member(bot_hash, 'g2', 'm1', username='alice')
    common._do_qq_group_api_request(bot, response_api(11255, 'g2'), 'GET', 'group_member_list')

    class DeniedBotState(object):
        def __init__(self, bot_info):
            self.metadata = SimpleNamespace(group_openid=None)
            self.res = json.dumps({'code': 11253})
            self.res_code = 403

        def do_api(self, method):
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupBotState', DeniedBotState)
    clock[0] += 600.0
    common._verify_qq_group_suspect(bot_hash, bot, 'g2')
    assert store.get_group(bot_hash, 'g2')['state'] == 'suspect'
    assert 'm1' in store.get_members(bot_hash, 'g2')
    assert any(call.args[0] == 2 for call in proc.log.call_args_list)


def test_suspect_verify_two_11255_with_600s_interval_removes_group(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    clock = [100.0]
    scheduled = []
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(
        common,
        '_schedule_qq_group_suspect_verify',
        lambda bh, bi, gid, delay=None, generation=None: (
            scheduled.append((bh, gid, delay, generation)) or True
        )
    )

    store.touch_group(bot_hash, 'g3')
    store.upsert_member(bot_hash, 'g3', 'm1', username='alice')
    common._do_qq_group_api_request(bot, response_api(11255, 'g3'), 'GET', 'group_member_list')
    assert len(scheduled) == 1

    class Err11255BotState(object):
        def __init__(self, bot_info):
            self.metadata = SimpleNamespace(group_openid=None)
            self.res = json.dumps({'code': 11255})
            self.res_code = 500

        def do_api(self, method):
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupBotState', Err11255BotState)
    # 间隔不足 600 秒时不能删群，按剩余 500 秒重排一次复核（同代次）。
    clock[0] += 100.0
    common._verify_qq_group_suspect(bot_hash, bot, 'g3')
    assert store.get_group(bot_hash, 'g3')['state'] == 'suspect'
    assert len(scheduled) == 2
    assert scheduled[1] == (str(bot_hash), 'g3', 500.0, 0)

    # 满剩余 500 秒（总计距首次 600 秒）再次命中 11255 才允许删群。
    clock[0] += 500.0
    common._verify_qq_group_suspect(bot_hash, bot, 'g3')
    assert store.get_group(bot_hash, 'g3') is None
    assert store.get_members(bot_hash, 'g3') == {}
    assert len(scheduled) == 2


def test_suspect_verify_clears_own_group_bot_state_backoff(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_schedule_qq_group_suspect_verify', lambda *args: True)

    store.touch_group(bot_hash, 'g_bs')
    store.upsert_member(bot_hash, 'g_bs', 'm1', username='alice')
    # 首次 11255 来自 group_bot_state，会写入 24h 退避；另一个群的退避应保持不受影响。
    common.sdkQQGroupApiBackoff[(str(bot_hash), 'group_bot_state', 'g_other')] = clock[0] + 86400.0
    common._do_qq_group_api_request(bot, response_api(11255, 'g_bs'), 'GET', 'group_bot_state')
    assert (str(bot_hash), 'group_bot_state', 'g_bs') in common.sdkQQGroupApiBackoff

    verify_calls = []

    class VerifyBotState(object):
        def __init__(self, bot_info):
            self.metadata = SimpleNamespace(group_openid=None)
            self.res = json.dumps({'code': 11255})
            self.res_code = 500

        def do_api(self, method):
            verify_calls.append((self.metadata.group_openid, method))
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupBotState', VerifyBotState)
    # 推进 600 秒（仍在 24h 退避期内），不手工清退避字典，复核应真的发出请求并删群。
    clock[0] += 600.0
    common._verify_qq_group_suspect(bot_hash, bot, 'g_bs')
    assert verify_calls == [('g_bs', 'GET')]
    assert store.get_group(bot_hash, 'g_bs') is None
    assert store.get_members(bot_hash, 'g_bs') == {}
    assert (str(bot_hash), 'group_bot_state', 'g_other') in common.sdkQQGroupApiBackoff


def test_send_qq_api_and_upload_11255_mark_suspect_without_sync_verify(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    scheduled = []
    verified = []
    monkeypatch.setattr(
        common,
        '_schedule_qq_group_suspect_verify',
        lambda bh, bi, gid: scheduled.append((bh, gid)) or True
    )
    monkeypatch.setattr(
        common,
        '_verify_qq_group_suspect',
        lambda *args, **kwargs: verified.append(args)
    )
    store.touch_group(bot_hash, 'g_send')
    store.upsert_member(bot_hash, 'g_send', 'm1', username='alice')

    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    event = SimpleNamespace(
        bot_info=account,
        data=SimpleNamespace(extend={'flag_from_qq': True}),
        log_func=None
    )
    api_obj = SimpleNamespace(
        data=SimpleNamespace(content='hi', message_reference=None),
        res=json.dumps({'code': 11255, 'message': 'invalid request'}),
        res_code=500,
        do_api=Mock()
    )
    send_res = OlivOS.qqGuildv2SDK.event_action._send_qq_api(
        event, api_obj, 'qq_group', 'g_send', None, None
    )
    assert send_res['active'] is False
    assert send_res['data']['error_code'] == 11255
    assert store.get_group(bot_hash, 'g_send')['state'] == 'suspect'
    assert 'm1' in store.get_members(bot_hash, 'g_send')
    assert scheduled == [(str(bot_hash), 'g_send')]
    assert verified == []

    # 文件直传返回 11255 同样标记 suspect，不发起同步复核。
    store.touch_group(bot_hash, 'g_upload')

    class UploadErr11255(object):
        def __init__(self, sdk_bot):
            self.resource_type = None
            self.metadata = SimpleNamespace(openid=None)
            self.data = SimpleNamespace()
            self.res = json.dumps({'code': 11255, 'message': 'invalid request'})
            self.res_code = 500

        def do_api(self, method='POST'):
            return self.res

    monkeypatch.setattr(common.API, 'setResourcePictureUpload', UploadErr11255)
    file_info = OlivOS.qqGuildv2SDK.event_action.setResourceUploadFast(
        event, 'https://example.invalid/a.png', 'g_upload', 'images', 'qq_groups'
    )
    assert file_info is None
    assert store.get_group(bot_hash, 'g_upload')['state'] == 'suspect'
    assert (str(bot_hash), 'g_upload') in scheduled
    assert verified == []


def test_group_mentions_exclude_bot_self_from_members(group_api, monkeypatch):
    bot, _, _ = group_api
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    monkeypatch.setattr(common, 'sdkSelfInfo', {account.hash: {'id': str(bot.id), 'username': 'bot'}})
    monkeypatch.setattr(common, 'qqEventDedupeCache', {})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args: 'SELF-OPENID')
    payload = OlivOS.qqGuildv2SDK.PAYLOAD.rxPacket({
        'op': 0,
        's': 1,
        't': 'GROUP_AT_MESSAGE_CREATE',
        'd': {
            'id': 'msg-1',
            'group_openid': 'g_mentions',
            'content': ' hello',
            'author': {'member_openid': 'u_sender', 'username': '发送者'},
            'mentions': [
                {'member_openid': 'SELF-OPENID', 'username': '机器人自己', 'bot': True},
                {'member_openid': 'u_other', 'username': '被艾特的人', 'bot': False}
            ]
        }
    })
    event = OlivOS.API.Event(OlivOS.qqGuildv2SDK.event(payload, account))
    assert event.active is True
    members = store.get_members(account.hash, 'g_mentions')
    assert 'u_sender' in members
    assert 'u_other' in members
    assert 'SELF-OPENID' not in members


def test_tier1_complete_writes_once_with_api_source(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    monkeypatch.setattr(common, '_ensure_qq_group_calibration_thread', Mock())

    class MemberInfoOk(object):
        def __init__(self, sdk_bot):
            self.metadata = SimpleNamespace(group_openid=None, member_openid=None)
            self.res = json.dumps({
                'member_openid': 'm_tier1',
                'username': '新成员昵称',
                'member_role': 'admin',
                'bot': False,
                'joined_at': '2026-11-01T00:00:00Z',
                'union_openid': 'u_union'
            })
            self.res_code = 200

        def do_api(self, method='GET'):
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupMemberInfo', MemberInfoOk)
    orig_upsert = store.upsert_member
    upsert_calls = []

    def spy_upsert(*args, **kwargs):
        upsert_calls.append((args, kwargs))
        return orig_upsert(*args, **kwargs)

    monkeypatch.setattr(store, 'upsert_member', spy_upsert)
    common._qq_group_member_tier1_complete(bot_hash, bot, 'g_t1', 'm_tier1')
    assert len(upsert_calls) == 1
    row = store.get_member(bot_hash, 'g_t1', 'm_tier1')
    assert row['username'] == '新成员昵称'
    assert row['member_role'] == 'admin'
    assert row['joined_at'] == '2026-11-01T00:00:00Z'
    assert row['source'] == 'api'
    # Tier 1 补全只登记 bot，不把群灌入优先校准队列。
    assert str(bot_hash) in common.sdkQQGroupCalibrationBotInfo
    assert str(bot_hash) not in common.sdkQQGroupCalibrationGroups


def test_get_group_member_list_card_prefers_member_nickname(group_api):
    _, bot_hash, _ = group_api
    store.touch_group(bot_hash, 'g_card')
    store.upsert_member(bot_hash, 'g_card', 'm1', username='全局昵称1', member_nickname='群名片1')
    store.upsert_member(bot_hash, 'g_card', 'm2', username='全局昵称2')
    event = SimpleNamespace(bot_info=SimpleNamespace(hash=bot_hash))
    result = OlivOS.qqGuildv2SDK.event_action.get_group_member_list(event, 'g_card')
    assert result['active'] is True
    by_id = {item['user_id']: item for item in result['data']}
    assert by_id['m1']['name'] == '全局昵称1'
    assert by_id['m1']['card'] == '群名片1'
    assert by_id['m2']['name'] == '全局昵称2'
    assert by_id['m2']['card'] == '全局昵称2'


def test_fetch_member_pages_single_multi_and_truncated(group_api, monkeypatch):
    bot, bot_hash, _ = group_api

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

    # 单页结束
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (200, {'members': [{'member_openid': 'm1', 'username': 'u1'}], 'next_cursor': ''})
    }))
    single = common._qq_group_fetch_member_pages(bot, 'g_single', bot_hash=bot_hash)
    assert single['ok'] is True
    assert single['pages'] == 1
    assert single['members'] == 1
    assert single['next_cursor'] == ''
    assert single['complete'] is True
    assert single['truncated'] is False
    assert store.get_group(bot_hash, 'g_single')['members_state'] == 'complete'

    # 多页翻完
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (200, {'members': [{'member_openid': 'm1', 'username': 'u1'}], 'next_cursor': 'c1'}),
        'c1': (200, {'members': [{'member_openid': 'm2', 'username': 'u2'}], 'next_cursor': ''}),
    }))
    multi = common._qq_group_fetch_member_pages(bot, 'g_multi', bot_hash=bot_hash)
    assert multi['ok'] is True
    assert multi['pages'] == 2
    assert multi['members'] == 2
    assert multi['next_cursor'] == ''
    assert multi['complete'] is True
    assert multi['truncated'] is False

    # 触顶截断 + 从 start_cursor 续翻
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (200, {'members': [{'member_openid': 'm1'}], 'next_cursor': 'c1'}),
        'c1': (200, {'members': [{'member_openid': 'm2'}], 'next_cursor': 'c2'}),
        'c2': (200, {'members': [{'member_openid': 'm3'}], 'next_cursor': ''}),
    }))
    part1 = common._qq_group_fetch_member_pages(bot, 'g_trunc', bot_hash=bot_hash, max_pages=2)
    assert part1['ok'] is True
    assert part1['pages'] == 2
    assert part1['members'] == 2
    assert part1['next_cursor'] == 'c2'
    assert part1['complete'] is False
    assert part1['truncated'] is True
    assert store.get_group(bot_hash, 'g_trunc')['members_state'] != 'complete'

    part2 = common._qq_group_fetch_member_pages(
        bot, 'g_trunc', bot_hash=bot_hash, max_pages=2, start_cursor=part1['next_cursor']
    )
    assert part2['ok'] is True
    assert part2['pages'] == 1
    assert part2['members'] == 1
    assert part2['next_cursor'] == ''
    assert part2['complete'] is True
    assert part2['truncated'] is False
    assert store.get_group(bot_hash, 'g_trunc')['members_state'] == 'complete'

    # 中途失败保留最后一次非空游标；首请求失败保留 start_cursor
    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        '': (200, {'members': [{'member_openid': 'm1'}], 'next_cursor': 'c1'}),
        'c1': (500, {'code': 99999, 'message': 'server error'}),
    }))
    mid_fail = common._qq_group_fetch_member_pages(bot, 'g_mid_fail', bot_hash=bot_hash)
    assert mid_fail['ok'] is False
    assert mid_fail['next_cursor'] == 'c1'
    assert mid_fail['complete'] is False
    assert mid_fail['truncated'] is False

    monkeypatch.setattr(common.API, 'getQQGroupMembers', make_members_api({
        'c_init': (500, {'code': 99999, 'message': 'server error'}),
    }))
    first_fail = common._qq_group_fetch_member_pages(
        bot, 'g_first_fail', bot_hash=bot_hash, start_cursor='c_init'
    )
    assert first_fail['ok'] is False
    assert first_fail['next_cursor'] == 'c_init'
    assert first_fail['complete'] is False
    assert first_fail['truncated'] is False


def test_schedule_suspect_verify_deduplicates(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    started = []

    class FakeThread(object):
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target
            self.daemon = daemon
            self.name = name
            self._alive = False

        def start(self):
            self._alive = True
            started.append(self)

        def is_alive(self):
            return self._alive

    monkeypatch.setattr(common.threading, 'Thread', FakeThread)
    assert common._schedule_qq_group_suspect_verify(bot_hash, bot, 'g_dedup') is True
    assert common._schedule_qq_group_suspect_verify(bot_hash, bot, 'g_dedup') is False
    # 第二个不同的群复用同一个单后台线程，不会引发线程风暴。
    assert common._schedule_qq_group_suspect_verify(bot_hash, bot, 'g_other') is True
    assert len(started) == 1
    assert started[0].daemon is True
    assert len(common.sdkQQGroupSuspectDue) == 2


def test_take_group_member_profile_writes_api_source(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    event = SimpleNamespace(bot_info=SimpleNamespace(hash=bot_hash, id=bot.id, model=bot.model))

    def fake_req(target_event, group_openid, member_openid):
        return {
            'active': True,
            'data': {
                'response': {
                    'member_openid': member_openid,
                    'username': '详情接口昵称',
                    'member_role': 'member',
                    'joined_at': '2026-11-02T00:00:00Z'
                }
            }
        }

    monkeypatch.setattr(OlivOS.qqGuildv2SDK.event_action, '_request_qq_group_member_info', fake_req)
    profile = common._take_qq_group_member_profile(event, 'g_prof', 'm_prof')
    assert profile is not None
    row = store.get_member(bot_hash, 'g_prof', 'm_prof')
    assert row['username'] == '详情接口昵称'
    assert row['source'] == 'api'
    assert row['joined_at'] == '2026-11-02T00:00:00Z'


@pytest.mark.parametrize('error_code', [100017, 40023001])
def test_group_api_backoff_is_one_hour_per_group(group_api, monkeypatch, error_code):
    bot, _, _ = group_api
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    api = response_api(error_code)
    common._do_qq_group_api_request(bot, api, 'GET', 'group_member_info')
    clock[0] += 3599
    blocked = common._do_qq_group_api_request(bot, api, 'GET', 'group_member_info')
    assert blocked['backed_off'] is True
    assert blocked['rate_limited'] is False
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


def _make_members_pages_api(pages_by_cursor):
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


def test_fetch_member_pages_reconcile_only_on_complete_full_scan(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    base_ts = int(time.time())

    # 1. 完整翻页 + reconcile=True：删除离群旧成员，保留同步开始后写入的新成员。
    store.touch_group(bot_hash, 'g_rec_ok')
    store.upsert_member(bot_hash, 'g_rec_ok', 'm_stay', username='留存', updated_at=base_ts - 100)
    store.upsert_member(bot_hash, 'g_rec_ok', 'm_gone', username='离群', updated_at=base_ts - 100)
    store.upsert_member(bot_hash, 'g_rec_ok', 'm_new', username='新入群', updated_at=base_ts + 50)
    monkeypatch.setattr(common.API, 'getQQGroupMembers', _make_members_pages_api({
        '': (200, {'members': [{'member_openid': 'm_stay', 'username': '留存'}], 'next_cursor': ''})
    }))
    res_ok = common._qq_group_fetch_member_pages(
        bot, 'g_rec_ok', bot_hash=bot_hash, reconcile=True
    )
    assert res_ok['complete'] is True
    assert set(store.get_members(bot_hash, 'g_rec_ok')) == {'m_stay', 'm_new'}

    # 2. 触顶截断（truncated=True）：绝不触发差集。
    store.touch_group(bot_hash, 'g_rec_trunc')
    store.upsert_member(bot_hash, 'g_rec_trunc', 'm_old', username='旧成员', updated_at=base_ts - 100)
    monkeypatch.setattr(common.API, 'getQQGroupMembers', _make_members_pages_api({
        '': (200, {'members': [{'member_openid': 'm1'}], 'next_cursor': 'c1'}),
        'c1': (200, {'members': [{'member_openid': 'm2'}], 'next_cursor': ''}),
    }))
    res_trunc = common._qq_group_fetch_member_pages(
        bot, 'g_rec_trunc', bot_hash=bot_hash, max_pages=1, reconcile=True
    )
    assert res_trunc['truncated'] is True
    assert res_trunc['complete'] is False
    assert set(store.get_members(bot_hash, 'g_rec_trunc')) == {'m_old', 'm1'}

    # 3. 中途失败：绝不触发差集。
    store.touch_group(bot_hash, 'g_rec_fail')
    store.upsert_member(bot_hash, 'g_rec_fail', 'm_old', username='旧成员', updated_at=base_ts - 100)
    monkeypatch.setattr(common.API, 'getQQGroupMembers', _make_members_pages_api({
        '': (200, {'members': [{'member_openid': 'm1'}], 'next_cursor': 'c1'}),
        'c1': (500, {'code': 99999, 'message': 'err'}),
    }))
    res_fail = common._qq_group_fetch_member_pages(
        bot, 'g_rec_fail', bot_hash=bot_hash, reconcile=True
    )
    assert res_fail['ok'] is False
    assert set(store.get_members(bot_hash, 'g_rec_fail')) == {'m_old', 'm1'}


def test_calibration_tick_priority_first_and_skips_denied_bot(group_api, monkeypatch):
    bot_a, hash_a, _ = group_api
    bot_b = common.bot_info_T(id=456, model='public')
    hash_b = OlivOS.API.getBotHash(
        bot_id=bot_b.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot_b.model
    )
    monkeypatch.setattr(common, '_ensure_qq_group_calibration_thread', Mock())
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())

    now = int(time.time())
    day = 86400
    # bot_a：优先队列登记 g_prio（需存在于库且 active/未完成），SQL 巡检有 g_sql_1 / g_sql_2（其中 g_sql_2 已在 pending 中）
    store.upsert_group(hash_a, 'g_prio', state='active', members_state='active',
                       verified_at=None, last_seen_at=now)
    common._register_qq_group_for_calibration(hash_a, bot_a, 'g_prio')
    store.upsert_group(hash_a, 'g_sql_1', state='active', members_state='active',
                       verified_at=None, last_seen_at=now - 1 * day)
    store.upsert_group(hash_a, 'g_sql_2', state='active', members_state='complete',
                       verified_at=now - 10 * day, last_seen_at=now - 2 * day)
    common.sdkQQGroupWarmPending.add((str(hash_a), 'g_sql_2'))

    # bot_b：已触发 11253 禁用，优先队列和 SQL 群都应被整段跳过。
    common.sdkQQGroupCalibrationBotInfo[str(hash_b)] = bot_b
    common.sdkQQGroupCalibrationGroups[str(hash_b)] = {'g_b_prio': 0.0}
    store.upsert_group(hash_b, 'g_b_sql', state='active', members_state='active',
                       verified_at=None, last_seen_at=now - 1 * day)
    common._mark_qq_group_api_denied(hash_b, 'group_member_list')

    enqueued_count = common._qq_group_calibration_tick(now=now, per_tick=50)
    assert enqueued_count == 2
    queued_pairs = [(item[0], item[2]) for item in common.sdkQQGroupWarmQueue]
    assert queued_pairs == [(str(hash_a), 'g_prio'), (str(hash_a), 'g_sql_1')]
    # 优先队列处理完后清空该 bot 的登记表。
    assert str(hash_a) not in common.sdkQQGroupCalibrationGroups


def test_group_message_registers_bot_info_once_for_calibration(group_api, monkeypatch):
    bot, _, _ = group_api
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    monkeypatch.setattr(common, '_ensure_qq_group_calibration_thread', Mock())
    monkeypatch.setattr(common, 'sdkSelfInfo', {account.hash: {'id': str(bot.id), 'username': 'bot'}})
    monkeypatch.setattr(common, 'qqEventDedupeCache', {})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args: 'SELF-OPENID')

    reg_calls = []
    orig_reg = common._register_qq_group_bot_for_calibration

    def spy_reg(bh, bi):
        reg_calls.append(str(bh))
        return orig_reg(bh, bi)

    monkeypatch.setattr(common, '_register_qq_group_bot_for_calibration', spy_reg)

    for idx in range(2):
        payload = OlivOS.qqGuildv2SDK.PAYLOAD.rxPacket({
            'op': 0,
            's': idx + 1,
            't': 'GROUP_AT_MESSAGE_CREATE',
            'd': {
                'id': 'msg-reg-%d' % idx,
                'group_openid': 'g_reg',
                'content': ' hi %d' % idx,
                'author': {'member_openid': 'u1', 'username': '成员'}
            }
        })
        event = OlivOS.API.Event(OlivOS.qqGuildv2SDK.event(payload, account))
        assert event.active is True

    assert reg_calls == [str(account.hash)]
    assert str(account.hash) in common.sdkQQGroupCalibrationBotInfo


def test_tier1_queue_retry_backoff_max_3_and_dedup(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    clock = [1000.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_ensure_qq_group_tier1_thread', Mock())
    monkeypatch.setattr(common, '_register_qq_group_calibration_bot', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupTier1RetryDelays', (30.0, 300.0, 1800.0))

    attempts = []

    def fake_api_req(bot_info, api_obj, req_type, op_key, wait=False):
        attempts.append((clock[0], api_obj.metadata.member_openid))
        return {
            'active': False, 'http_status': None, 'error_code': None,
            'error': 'rate limit', 'response': None, 'denied': False, 'rate_limited': True
        }

    monkeypatch.setattr(common, '_do_qq_group_api_request', fake_api_req)

    # 去重生效：相同 (bot, group, member) 重复入队返回 False。
    assert common._enqueue_qq_group_tier1(bot_hash, bot, 'g1', 'm1') is True
    assert common._enqueue_qq_group_tier1(bot_hash, bot, 'g1', 'm1') is False

    # 第 1 次执行（attempt=0）限流 -> 按 30s 延迟重排（attempt=1）
    processed, _ = common._qq_group_tier1_step()
    assert processed is True
    assert len(common.sdkQQGroupTier1Delayed) == 1
    assert common.sdkQQGroupTier1Delayed[0][0] == 1030.0
    assert common.sdkQQGroupTier1Delayed[0][1][4] == 1
    assert (str(bot_hash), 'g1', 'm1') in common.sdkQQGroupTier1Pending

    # 未到期时不出队，返回剩余等待时间。
    clock[0] = 1020.0
    processed, next_wait = common._qq_group_tier1_step()
    assert processed is False
    assert next_wait == 10.0

    # 到期后重试 #1（30s）-> 排 300s；重试 #2（300s）-> 排 1800s；重试 #3（1800s）-> 放弃清 pending。
    clock[0] = 1030.0
    assert common._qq_group_tier1_step()[0] is True
    assert common.sdkQQGroupTier1Delayed[0][0] == 1330.0
    clock[0] = 1330.0
    assert common._qq_group_tier1_step()[0] is True
    assert common.sdkQQGroupTier1Delayed[0][0] == 3130.0
    clock[0] = 3130.0
    assert common._qq_group_tier1_step()[0] is True

    assert len(attempts) == 4
    assert len(common.sdkQQGroupTier1Queue) == 0
    assert len(common.sdkQQGroupTier1Delayed) == 0
    assert len(common.sdkQQGroupTier1Pending) == 0


def test_tier1_11253_clears_bot_queue_and_11255_does_not_retry(group_api, monkeypatch):
    bot_a, hash_a, _ = group_api
    bot_b = common.bot_info_T(id=456, model='public')
    hash_b = OlivOS.API.getBotHash(
        bot_id=bot_b.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot_b.model
    )
    monkeypatch.setattr(common, '_ensure_qq_group_tier1_thread', Mock())
    monkeypatch.setattr(common, '_register_qq_group_calibration_bot', Mock())
    monkeypatch.setattr(common, '_schedule_qq_group_suspect_verify', lambda *args: True)

    # 场景 1：11255 不重试、直接清 pending。
    class Err11255MemberInfo(object):
        def __init__(self, sdk_bot):
            self.metadata = SimpleNamespace(group_openid=None, member_openid=None)
            self.res = json.dumps({'code': 11255})
            self.res_code = 500

        def do_api(self, method='GET'):
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupMemberInfo', Err11255MemberInfo)
    assert common._enqueue_qq_group_tier1(hash_a, bot_a, 'g_sus', 'm_sus') is True
    assert common._qq_group_tier1_step()[0] is True
    assert len(common.sdkQQGroupTier1Delayed) == 0
    assert (str(hash_a), 'g_sus', 'm_sus') not in common.sdkQQGroupTier1Pending

    # 场景 2：11253 清空 bot_a 的立即与延迟队列，不影响 bot_b。
    class Err11253MemberInfo(object):
        def __init__(self, sdk_bot):
            self.metadata = SimpleNamespace(group_openid=None, member_openid=None)
            self.res = json.dumps({'code': 11253})
            self.res_code = 403

        def do_api(self, method='GET'):
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupMemberInfo', Err11253MemberInfo)
    assert common._enqueue_qq_group_tier1(hash_a, bot_a, 'g1', 'm1') is True
    assert common._enqueue_qq_group_tier1(hash_a, bot_a, 'g1', 'm2') is True
    common.sdkQQGroupTier1Delayed.append((9999.0, (str(hash_a), bot_a, 'g1', 'm3', 1)))
    common.sdkQQGroupTier1Pending.add((str(hash_a), 'g1', 'm3'))
    assert common._enqueue_qq_group_tier1(hash_b, bot_b, 'g2', 'mb1') is True

    assert common._qq_group_tier1_step()[0] is True
    assert [(t[0], t[3]) for t in common.sdkQQGroupTier1Queue] == [(str(hash_b), 'mb1')]
    assert common.sdkQQGroupTier1Delayed == []
    assert common.sdkQQGroupTier1Pending == {(str(hash_b), 'g2', 'mb1')}


def test_warm_daily_page_budget_defers_without_consuming_and_resets_next_day(group_api, monkeypatch):
    bot_a, hash_a, _ = group_api
    bot_b = common.bot_info_T(id=456, model='public')
    hash_b = OlivOS.API.getBotHash(
        bot_id=bot_b.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot_b.model
    )
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPageLimit', 2)
    day = ['2026-11-22']
    monkeypatch.setattr(common.time, 'strftime', lambda fmt: day[0])

    fetch_calls = []

    def fake_fetch(bot_info, gid, bot_hash=None, wait=False, max_pages=10,
                   start_cursor='', reconcile=False, seen=None, sync_started_at=None):
        fetch_calls.append((str(bot_hash), gid, reconcile))
        return {
            'ok': True, 'error': None, 'denied': False, 'rate_limited': False,
            'pages': 2, 'members': 1, 'next_cursor': '', 'complete': True, 'truncated': False
        }

    monkeypatch.setattr(common, '_qq_group_fetch_member_pages', fake_fetch)

    store.touch_group(hash_a, 'g_a1')
    store.touch_group(hash_a, 'g_a2')
    store.touch_group(hash_b, 'g_b1')
    assert common._enqueue_qq_group_warm(hash_a, bot_a, 'g_a1') is True
    assert common._enqueue_qq_group_warm(hash_a, bot_a, 'g_a2') is True
    # 第一次消费 2 页，正好打满 bot_a 今日预算上限，且传入 reconcile=True。
    assert common._qq_group_warm_step() is True
    assert fetch_calls == [(str(hash_a), 'g_a1', True)]
    assert common.sdkQQGroupWarmDailyPages[(str(hash_a), '2026-11-22')] == 2

    # 达上限后 g_a2 不出队、不发请求、不消耗额度。
    assert common._qq_group_warm_step() is False
    assert len(fetch_calls) == 1
    assert [(t[0], t[2]) for t in common.sdkQQGroupWarmQueue] == [(str(hash_a), 'g_a2')]
    assert (str(hash_a), 'g_a2') in common.sdkQQGroupWarmPending
    assert common.sdkQQGroupWarmDailyPages[(str(hash_a), '2026-11-22')] == 2

    # 另一个未超限的 bot_b 仍可绕过 bot_a 正常执行。
    assert common._enqueue_qq_group_warm(hash_b, bot_b, 'g_b1') is True
    assert common._qq_group_warm_step() is True
    assert fetch_calls[-1] == (str(hash_b), 'g_b1', True)
    assert [(t[0], t[2]) for t in common.sdkQQGroupWarmQueue] == [(str(hash_a), 'g_a2')]

    # worker 在仅有预算受限任务时等待 60s（不忙等）。
    waits = []

    class FakeEvent(object):
        def clear(self):
            pass

        def set(self):
            pass

        def wait(self, timeout=None):
            waits.append(timeout)
            common.sdkQQGroupWarmThread = None

    common.sdkQQGroupWarmThread = threading.current_thread()
    monkeypatch.setattr(common, 'sdkQQGroupWarmEvent', FakeEvent())
    common._qq_group_warm_worker()
    assert waits == [60.0]

    # 跨天自动换 key，bot_a 恢复执行。
    day[0] = '2026-11-23'
    assert common._qq_group_warm_step() is True
    assert fetch_calls[-1] == (str(hash_a), 'g_a2', True)
    assert common.sdkQQGroupWarmDailyPages[(str(hash_a), '2026-11-23')] == 2
    assert len(common.sdkQQGroupWarmQueue) == 0


def test_group_member_add_enqueues_tier1_and_overflow_drops_oldest(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    monkeypatch.setattr(common, 'sdkSelfInfo', {account.hash: {'id': str(bot.id), 'username': 'bot'}})
    monkeypatch.setattr(common, 'qqEventDedupeCache', {})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args: 'SELF-OPENID')
    monkeypatch.setattr(common, '_ensure_qq_group_tier1_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupTier1MaxSize', 2)

    enqueued_events = []
    orig_enqueue = common._enqueue_qq_group_tier1

    def spy_enqueue(*args, **kwargs):
        enqueued_events.append((args[0], args[2], args[3]))
        return orig_enqueue(*args, **kwargs)

    monkeypatch.setattr(common, '_enqueue_qq_group_tier1', spy_enqueue)

    for idx, mid in enumerate(('m1', 'm2', 'm3')):
        payload = OlivOS.qqGuildv2SDK.PAYLOAD.rxPacket({
            'op': 0,
            's': idx + 1,
            't': 'GROUP_MEMBER_ADD',
            'd': {
                'id': 'evt-add-%d' % idx,
                'group_openid': 'g_add',
                'member_openid': mid,
                'timestamp': 1700000000 + idx
            }
        })
        event = OlivOS.API.Event(OlivOS.qqGuildv2SDK.event(payload, account))
        assert event.active is True

    assert enqueued_events == [
        (account.hash, 'g_add', 'm1'),
        (account.hash, 'g_add', 'm2'),
        (account.hash, 'g_add', 'm3'),
    ]
    # 超过上限 2 时丢弃最旧任务 m1 并同步清理 pending。
    assert [(t[2], t[3]) for t in common.sdkQQGroupTier1Queue] == [('g_add', 'm2'), ('g_add', 'm3')]
    assert (str(account.hash), 'g_add', 'm1') not in common.sdkQQGroupTier1Pending
    assert common.sdkQQGroupTier1Pending == {
        (str(account.hash), 'g_add', 'm2'),
        (str(account.hash), 'g_add', 'm3'),
    }


def test_raw_get_qq_group_member_list_respects_11253_and_60_qpm(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    event = SimpleNamespace(bot_info=account, log_func=None)
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])

    # 场景 1：60 QPM 限流约束（第 61 次直接返回 rate limit，不再调用 do_api）。
    do_api_calls = []

    class OkMembers(object):
        def __init__(self, sdk_bot):
            self.bot_info = sdk_bot
            self.metadata = SimpleNamespace(group_openid=None)
            self.query = None
            self.res = json.dumps({'members': [{'member_openid': 'm1'}], 'next_cursor': ''})
            self.res_code = 200

        def do_api(self, method='GET'):
            do_api_calls.append((method, self.metadata.group_openid))
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupMembers', OkMembers)
    limit = common.qqGroupApiRateLimitMap['group_member_list']
    for _ in range(limit):
        res = OlivOS.qqGuildv2SDK.event_action.get_qq_group_member_list(event, 'g_rate')
        assert res['active'] is True
        assert res['data']['operation'] == 'get_qq_group_member_list'
        assert res['data']['http_status'] == 200
        assert res['data']['response'] == {'members': [{'member_openid': 'm1'}], 'next_cursor': ''}
    limited = OlivOS.qqGuildv2SDK.event_action.get_qq_group_member_list(event, 'g_rate')
    assert limited['active'] is False
    assert limited['data']['operation'] == 'get_qq_group_member_list'
    assert 'rate limit' in limited['data']['error']
    assert len(do_api_calls) == limit

    # 场景 2：11253 禁用后不再调用 do_api。
    clock[0] += 120.0
    denied_calls = []

    class DeniedMembers(object):
        def __init__(self, sdk_bot):
            self.bot_info = sdk_bot
            self.metadata = SimpleNamespace(group_openid=None)
            self.query = None
            self.res = json.dumps({'code': 11253, 'message': 'no permission'})
            self.res_code = 403

        def do_api(self, method='GET'):
            denied_calls.append(self.metadata.group_openid)
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupMembers', DeniedMembers)
    first = OlivOS.qqGuildv2SDK.event_action.get_qq_group_member_list(event, 'g_deny')
    second = OlivOS.qqGuildv2SDK.event_action.get_qq_group_member_list(event, 'g_deny')
    assert first['active'] is False
    assert first['data']['error_code'] == 11253
    assert second['active'] is False
    assert second['data']['error_code'] == 11253
    assert common._check_qq_group_api_denied(bot_hash, 'group_member_list') is True
    assert denied_calls == ['g_deny']


def test_raw_get_qq_group_bot_state_uses_unified_request_and_keeps_shape(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    event = SimpleNamespace(bot_info=account, log_func=None)

    calls = []

    class BotStateApi(object):
        def __init__(self, sdk_bot):
            self.bot_info = sdk_bot
            self.metadata = SimpleNamespace(group_openid=None)
            self.res = json.dumps({'member_openid': 'bot_open', 'member_role': 'admin'})
            self.res_code = 200

        def do_api(self, method='GET'):
            calls.append((method, self.metadata.group_openid))
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupBotState', BotStateApi)
    res = OlivOS.qqGuildv2SDK.event_action.get_qq_group_bot_state(event, 'g_state')
    assert res['active'] is True
    assert res['data']['operation'] == 'get_qq_group_bot_state'
    assert res['data']['http_status'] == 200
    assert res['data']['error_code'] is None
    assert res['data']['error'] is None
    assert res['data']['response'] == {'member_openid': 'bot_open', 'member_role': 'admin'}
    assert calls == [('GET', 'g_state')]

    # 11253 禁用后直接走统一入口拦截，不发网络请求。
    common._mark_qq_group_api_denied(bot_hash, 'group_bot_state')
    denied = OlivOS.qqGuildv2SDK.event_action.get_qq_group_bot_state(event, 'g_state')
    assert denied['active'] is False
    assert denied['data']['operation'] == 'get_qq_group_bot_state'
    assert denied['data']['error_code'] == 11253
    assert denied['data']['response'] is None
    assert len(calls) == 1


def test_get_qq_group_member_list_standard_shape_on_success_and_failure(group_api, monkeypatch):
    bot, _, _ = group_api
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    event = SimpleNamespace(bot_info=account, log_func=None)

    monkeypatch.setattr(common.API, 'getQQGroupMembers', _make_members_pages_api({
        '': (200, {
            'members': [
                {'member_openid': 'm1', 'username': '成员1', 'role': 'admin'},
                {'member_openid': 'm2', 'username': '成员2', 'role': 'member'}
            ],
            'next_cursor': ''
        })
    }))
    ok_res = OlivOS.qqGuildv2SDK.event_action.get_qq_group_member_list_standard(event, 'g_std')
    assert ok_res['active'] is True
    assert [item['user_id'] for item in ok_res['data']] == ['m1', 'm2']
    assert ok_res['data'][0]['group_id'] == 'g_std'
    assert ok_res['data'][0]['name'] == '成员1'
    assert ok_res['data'][0]['extra']['member_openid'] == 'm1'

    # 失败时返回空列表与 active=False，结构不变。
    monkeypatch.setattr(common.API, 'getQQGroupMembers', _make_members_pages_api({
        '': (403, {'code': 11253, 'message': 'no permission'})
    }))
    fail_res = OlivOS.qqGuildv2SDK.event_action.get_qq_group_member_list_standard(event, 'g_std')
    assert fail_res['active'] is False
    assert fail_res['data'] == []


def test_suspect_recovered_by_group_message_or_removed_skips_verify(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_schedule_qq_group_suspect_verify', lambda *args: True)
    monkeypatch.setattr(common, '_ensure_qq_group_calibration_thread', Mock())

    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    monkeypatch.setattr(common, 'sdkSelfInfo', {account.hash: {'id': str(bot.id), 'username': 'bot'}})
    monkeypatch.setattr(common, 'qqEventDedupeCache', {})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args: 'SELF-OPENID')

    # 场景 1：11255 后 600s 内收到群消息恢复 active -> 内存 suspect 状态被清，复核不发请求、不删群。
    store.touch_group(account.hash, 'g_recover')
    store.upsert_member(account.hash, 'g_recover', 'm1', username='alice')
    common._do_qq_group_api_request(bot, response_api(11255, 'g_recover'), 'GET', 'group_member_list')
    assert store.get_group(account.hash, 'g_recover')['state'] == 'suspect'
    assert (str(account.hash), 'g_recover') in common.sdkQQGroupSuspectState

    payload = OlivOS.qqGuildv2SDK.PAYLOAD.rxPacket({
        'op': 0,
        's': 1,
        't': 'GROUP_AT_MESSAGE_CREATE',
        'd': {
            'id': 'msg-recover-1',
            'group_openid': 'g_recover',
            'content': ' hi',
            'author': {'member_openid': 'm1', 'username': 'alice'}
        }
    })
    event = OlivOS.API.Event(OlivOS.qqGuildv2SDK.event(payload, account))
    assert event.active is True
    assert store.get_group(account.hash, 'g_recover')['state'] == 'active'
    assert (str(account.hash), 'g_recover') not in common.sdkQQGroupSuspectState

    bot_state_mock = Mock(side_effect=AssertionError('已恢复或已删除的群不应再发 bot_state 复核请求'))
    monkeypatch.setattr(common.API, 'getQQGroupBotState', bot_state_mock)
    clock[0] += 600.0
    common._verify_qq_group_suspect(account.hash, bot, 'g_recover')
    bot_state_mock.assert_not_called()
    assert store.get_group(account.hash, 'g_recover')['state'] == 'active'
    assert 'm1' in store.get_members(account.hash, 'g_recover')

    # 场景 2：群已被 remove_group 后，复核同样不发请求。
    store.touch_group(account.hash, 'g_gone')
    common._do_qq_group_api_request(bot, response_api(11255, 'g_gone'), 'GET', 'group_member_list')
    store.remove_group(account.hash, 'g_gone')
    clock[0] += 600.0
    common._verify_qq_group_suspect(account.hash, bot, 'g_gone')
    bot_state_mock.assert_not_called()
    assert store.get_group(account.hash, 'g_gone') is None


def test_mark_suspect_missing_group_does_not_resurrect_and_bad_event_uses_none(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    scheduled = []
    monkeypatch.setattr(
        common,
        '_schedule_qq_group_suspect_verify',
        lambda bh, bi, gid: scheduled.append((bh, bi, gid)) or True
    )
    # 群已不存在时，11255 只写退避，不插入新群行、不排复核。
    common._mark_qq_group_suspect(bot_hash, bot, 'g_nonexistent', op_key='group_member_list')
    assert store.get_group(bot_hash, 'g_nonexistent') is None
    assert (str(bot_hash), 'group_member_list', 'g_nonexistent') in common.sdkQQGroupApiBackoff
    assert scheduled == []

    # _mark_qq_group_suspect_from_event 在 get_SDK_bot_info_from_Event 异常时传 None，不把插件 bot_info 传进去。
    store.touch_group(bot_hash, 'g_fallback')
    bad_event = SimpleNamespace(bot_info=SimpleNamespace(hash=bot_hash))
    OlivOS.qqGuildv2SDK.event_action._mark_qq_group_suspect_from_event(
        bad_event, 'g_fallback', 'send_message'
    )
    assert store.get_group(bot_hash, 'g_fallback')['state'] == 'suspect'
    assert scheduled == [(str(bot_hash), None, 'g_fallback')]


def test_calibration_tick_filters_priority_groups_and_skips_exhausted_bot(group_api, monkeypatch):
    bot_a, hash_a, _ = group_api
    monkeypatch.setattr(common, '_ensure_qq_group_calibration_thread', Mock())
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPageLimit', 10)

    now = int(time.time())
    day = 86400
    # 刚 complete（1 小时前）-> 跳过；suspect -> 跳过；已删（不在库）-> 跳过；
    # 未 complete -> 入队；超 7 天 complete -> 入队。
    store.upsert_group(hash_a, 'g_fresh', state='active', members_state='complete',
                       verified_at=now - 3600, last_seen_at=now)
    store.upsert_group(hash_a, 'g_sus', state='suspect', members_state='active',
                       verified_at=None, last_seen_at=now)
    store.upsert_group(hash_a, 'g_need', state='active', members_state='active',
                       verified_at=None, last_seen_at=now)
    store.upsert_group(hash_a, 'g_stale', state='active', members_state='complete',
                       verified_at=now - 8 * day, last_seen_at=now)
    for gid in ('g_fresh', 'g_sus', 'g_deleted', 'g_need', 'g_stale'):
        common._register_qq_group_for_calibration(hash_a, bot_a, gid)

    count = common._qq_group_calibration_tick(now=now, per_tick=50)
    assert count == 2
    assert [(t[0], t[2]) for t in common.sdkQQGroupWarmQueue] == [
        (str(hash_a), 'g_need'),
        (str(hash_a), 'g_stale')
    ]

    # 预算耗尽的 bot 在两段校准里都会被整段跳过。
    common.sdkQQGroupWarmQueue.clear()
    common.sdkQQGroupWarmPending.clear()
    common._add_qq_group_warm_daily_pages(hash_a, 10)
    common._register_qq_group_for_calibration(hash_a, bot_a, 'g_need')
    assert common._qq_group_calibration_tick(now=now, per_tick=50) == 0
    assert len(common.sdkQQGroupWarmQueue) == 0


def test_tier1_defaults_and_worker_spacing_and_removed_constants(group_api, monkeypatch):
    bot, bot_hash, _ = group_api
    # 校验 F2.4 默认常量与 F2.7 已移除的无用常量。
    assert common.sdkQQGroupTier1RetryDelays == (65.0, 300.0, 1800.0)
    assert not hasattr(common, 'sdkQQGroupCalibrateMaxAge')
    assert not hasattr(common, 'sdkQQGroupCalibrateGroupSpacing')

    # 验证 tier1 worker 在锁外按 sdkQQGroupTier1Spacing 休眠。
    monkeypatch.setattr(common, 'sdkQQGroupTier1Spacing', 2.0)
    monkeypatch.setattr(common, '_qq_group_tier1_step', Mock(return_value=(True, 0.0)))
    sleeps = []

    def fake_sleep(sec):
        lock_free = common.sdkQQGroupTier1Lock.acquire(blocking=False)
        if lock_free:
            common.sdkQQGroupTier1Lock.release()
        sleeps.append((sec, lock_free))
        common.sdkQQGroupTier1Thread = None

    monkeypatch.setattr(common.time, 'sleep', fake_sleep)
    common.sdkQQGroupTier1Thread = threading.current_thread()
    common._qq_group_tier1_worker()
    assert sleeps == [(2.0, True)]


def test_wrap_non_json_response_and_refresh_error_code_mapping(group_api, monkeypatch):
    bot, _, _ = group_api
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    event = SimpleNamespace(bot_info=account, log_func=None)

    # 非 JSON 响应体保留原始字符串到 data.response。
    class HtmlErrorMembers(object):
        def __init__(self, sdk_bot):
            self.bot_info = sdk_bot
            self.metadata = SimpleNamespace(group_openid=None)
            self.query = None
            self.res = '<html>502 Bad Gateway</html>'
            self.res_code = 502

        def do_api(self, method='GET'):
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupMembers', HtmlErrorMembers)
    raw_res = OlivOS.qqGuildv2SDK.event_action.get_qq_group_member_list(event, 'g_html')
    assert raw_res['active'] is False
    assert raw_res['data']['http_status'] == 502
    assert raw_res['data']['response'] == '<html>502 Bad Gateway</html>'

    # refresh_qq_group_member_list 透传非 11253 错误码（如 11255）及 denied/rate_limited。
    monkeypatch.setattr(common, '_register_qq_group_for_calibration', Mock())
    monkeypatch.setattr(
        OlivOS.adapter.qqGuild.qqGuildv2SDKGroup, '_register_qq_group_for_calibration', Mock()
    )
    monkeypatch.setattr(common, '_schedule_qq_group_suspect_verify', lambda *args: True)
    monkeypatch.setattr(common.API, 'getQQGroupMembers', _make_members_pages_api({
        '': (500, {'code': 11255, 'message': 'invalid group'})
    }))
    ref_res = OlivOS.qqGuildv2SDK.event_action.refresh_qq_group_member_list(event, 'g_err_code')
    assert ref_res['active'] is False
    assert ref_res['data']['error_code'] == 11255
    assert ref_res['data']['denied'] is False
    assert ref_res['data']['rate_limited'] is False


def test_suspect_inflight_verify_with_group_message_recovery_does_not_delete(group_api, monkeypatch):
    """真实链路（建议 5.1 / 复现 G1）：复核 HTTP 在途期间群消息恢复 active，复核返回 11255 不得删群。"""
    bot, _, _ = group_api
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    bot_hash = account.hash
    clock = [100.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_ensure_qq_group_suspect_thread', Mock())
    monkeypatch.setattr(common, '_ensure_qq_group_calibration_thread', Mock())
    monkeypatch.setattr(common, 'sdkSelfInfo', {bot_hash: {'id': str(bot.id), 'username': 'bot'}})
    monkeypatch.setattr(common, 'qqEventDedupeCache', {})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args: 'SELF-OPENID')

    store.touch_group(bot_hash, 'g_inflight')
    store.upsert_member(bot_hash, 'g_inflight', 'm1', username='活跃成员')
    common._do_qq_group_api_request(bot, response_api(11255, 'g_inflight'), 'GET', 'group_member_list')
    assert store.get_group(bot_hash, 'g_inflight')['state'] == 'suspect'
    assert (str(bot_hash), 'group_member_list', 'g_inflight') in common.sdkQQGroupApiBackoff

    in_flight = threading.Event()
    release_http = threading.Event()

    class Blocking11255BotState(object):
        def __init__(self, sdk_bot):
            self.metadata = SimpleNamespace(group_openid=None)
            self.res = json.dumps({'code': 11255, 'message': 'invalid group'})
            self.res_code = 500

        def do_api(self, method='GET'):
            in_flight.set()
            assert release_http.wait(timeout=5.0)
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupBotState', Blocking11255BotState)
    clock[0] += 600.0

    verify_thread = threading.Thread(
        target=common._qq_group_suspect_step,
        daemon=True
    )
    verify_thread.start()
    assert in_flight.wait(timeout=5.0)
    assert (str(bot_hash), 'g_inflight') in common.sdkQQGroupSuspectVerifying

    # 在途期间收到真实群消息 -> 恢复 active、清 suspect、代次 +1、清该群全部退避。
    payload = OlivOS.qqGuildv2SDK.PAYLOAD.rxPacket({
        'op': 0,
        's': 1,
        't': 'GROUP_AT_MESSAGE_CREATE',
        'd': {
            'id': 'msg-inflight-recover',
            'group_openid': 'g_inflight',
            'content': ' 群还活着',
            'author': {'member_openid': 'm1', 'username': '活跃成员'}
        }
    })
    event = OlivOS.API.Event(OlivOS.qqGuildv2SDK.event(payload, account))
    assert event.active is True
    assert store.get_group(bot_hash, 'g_inflight')['state'] == 'active'
    assert (str(bot_hash), 'group_member_list', 'g_inflight') not in common.sdkQQGroupApiBackoff

    # 放行在途的 11255 响应：不得把群写回 suspect，不得写 24h 退避，更不得删群。
    release_http.set()
    verify_thread.join(timeout=5.0)
    assert not verify_thread.is_alive()
    assert (str(bot_hash), 'group_bot_state', 'g_inflight') not in common.sdkQQGroupApiBackoff
    row = store.get_group(bot_hash, 'g_inflight')
    assert row is not None
    assert row['state'] == 'active'
    assert 'm1' in store.get_members(bot_hash, 'g_inflight')


def test_suspect_single_worker_generation_reschedule_cap_and_ttl(group_api, monkeypatch):
    """复现 G6 + G2.5 + 建议 1：代次失效、恢复后再次 11255 不卡死、最多重排 3 次、队列上限 2000、24h TTL。"""
    bot, bot_hash, _ = group_api
    clock = [1000.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_ensure_qq_group_suspect_thread', Mock())

    # 场景 1：T=1000 触发 -> T=1100 恢复（代次 +1、清退避）-> T=1590 再次 11255 ->
    # T=1600 旧代次任务直接丢弃 -> T=2190 新代次复核 11255 删群。
    store.touch_group(bot_hash, 'g_gen')
    store.upsert_member(bot_hash, 'g_gen', 'm1', username='u1')
    common._do_qq_group_api_request(bot, response_api(11255, 'g_gen'), 'GET', 'group_member_list')
    common._set_qq_group_api_backoff(bot_hash, 'group_member_info', 'g_gen', 3600.0, now=clock[0])
    assert len(common.sdkQQGroupSuspectDue) == 1
    assert common.sdkQQGroupSuspectDue[0][0] == 1600.0
    assert common.sdkQQGroupSuspectDue[0][4] == 0

    clock[0] = 1100.0
    store.touch_group(bot_hash, 'g_gen')
    common._clear_qq_group_suspect_state(bot_hash, 'g_gen')
    assert (str(bot_hash), 'group_member_list', 'g_gen') not in common.sdkQQGroupApiBackoff
    assert (str(bot_hash), 'group_member_info', 'g_gen') not in common.sdkQQGroupApiBackoff

    clock[0] = 1590.0
    common._do_qq_group_api_request(bot, response_api(11255, 'g_gen'), 'GET', 'group_member_list')
    assert len(common.sdkQQGroupSuspectDue) == 2
    assert common.sdkQQGroupSuspectDue[1][0] == 2190.0
    assert common.sdkQQGroupSuspectDue[1][4] == 1

    verify_calls = []

    class Err11255BotState(object):
        def __init__(self, sdk_bot):
            self.metadata = SimpleNamespace(group_openid=None)
            self.res = json.dumps({'code': 11255})
            self.res_code = 500

        def do_api(self, method='GET'):
            verify_calls.append((clock[0], self.metadata.group_openid))
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupBotState', Err11255BotState)
    # T=1600：旧代次（gen=0）到期被直接丢弃，不发请求；返回剩余等待 590s。
    clock[0] = 1600.0
    processed, next_wait = common._qq_group_suspect_step()
    assert processed is False
    assert next_wait == 590.0
    assert verify_calls == []
    assert store.get_group(bot_hash, 'g_gen')['state'] == 'suspect'

    # T=2190：新代次（gen=1）到期发请求并删群。
    clock[0] = 2190.0
    processed, _ = common._qq_group_suspect_step()
    assert processed is True
    assert verify_calls == [(2190.0, 'g_gen')]
    assert store.get_group(bot_hash, 'g_gen') is None

    # 场景 2：复核早于 600s 最多重排 3 次，第 4 次不再重排。
    clock[0] = 3000.0
    store.touch_group(bot_hash, 'g_resched')
    common._do_qq_group_api_request(bot, response_api(11255, 'g_resched'), 'GET', 'group_member_list')
    common.sdkQQGroupSuspectDue.clear()
    common.sdkQQGroupSuspectPending.clear()
    for step_idx in range(3):
        clock[0] += 10.0
        common._verify_qq_group_suspect(bot_hash, bot, 'g_resched')
        assert len(common.sdkQQGroupSuspectDue) == 1
        common.sdkQQGroupSuspectDue.clear()
        common.sdkQQGroupSuspectPending.clear()
    clock[0] += 10.0
    common._verify_qq_group_suspect(bot_hash, bot, 'g_resched')
    assert len(common.sdkQQGroupSuspectDue) == 0

    # 场景 3：24h TTL 清理过期 suspect 状态。
    clock[0] += 86401.0
    common._qq_group_suspect_step()
    assert (str(bot_hash), 'g_resched') not in common.sdkQQGroupSuspectState

    # 场景 4：队列上限丢最旧并同步清 pending。
    monkeypatch.setattr(common, 'sdkQQGroupSuspectQueueMaxSize', 2)
    assert common._schedule_qq_group_suspect_verify(bot_hash, bot, 'gq1', delay=10.0) is True
    assert common._schedule_qq_group_suspect_verify(bot_hash, bot, 'gq2', delay=20.0) is True
    assert common._schedule_qq_group_suspect_verify(bot_hash, bot, 'gq3', delay=30.0) is True
    assert [item[3] for item in common.sdkQQGroupSuspectDue] == ['gq2', 'gq3']
    assert (str(bot_hash), 'gq1') not in common.sdkQQGroupSuspectPending


def test_tier1_default_65s_retry_passes_after_60s_rate_window(group_api, monkeypatch):
    """真实链路（建议 5.3）：不改 sdkQQGroupTier1RetryDelays，可控时钟验证默认 65s 重试真实通过。"""
    bot, bot_hash, _ = group_api
    clock = [1000.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_ensure_qq_group_tier1_thread', Mock())
    monkeypatch.setattr(common, '_register_qq_group_calibration_bot', Mock())
    assert common.sdkQQGroupTier1RetryDelays == (65.0, 300.0, 1800.0)

    # 先打满 group_member_info 的 30 QPM 滑动窗口。
    limit = common.qqGroupApiRateLimitMap['group_member_info']
    for _ in range(limit):
        assert common._acquire_qq_group_api_rate(bot_hash, 'group_member_info') is True

    class MemberInfoOk(object):
        def __init__(self, sdk_bot):
            self.metadata = SimpleNamespace(group_openid=None, member_openid=None)
            self.res = json.dumps({
                'member_openid': 'm_65s',
                'username': '65秒后成功',
                'member_role': 'member',
                'bot': False
            })
            self.res_code = 200

        def do_api(self, method='GET'):
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupMemberInfo', MemberInfoOk)
    assert common._enqueue_qq_group_tier1(bot_hash, bot, 'g_t1_65', 'm_65s') is True

    # 首次执行命中 30 QPM 限流 -> 按默认 65s 排入延迟队列。
    processed, _ = common._qq_group_tier1_step()
    assert processed is True
    assert len(common.sdkQQGroupTier1Delayed) == 1
    assert common.sdkQQGroupTier1Delayed[0][0] == 1065.0

    # 64s 尚未到期。
    clock[0] = 1064.0
    processed, next_wait = common._qq_group_tier1_step()
    assert processed is False
    assert next_wait == 1.0

    # 65s 到期：60s 滑动窗口已自然清零，真实 _do_qq_group_api_request 放行并落库！
    clock[0] = 1065.0
    processed, _ = common._qq_group_tier1_step()
    assert processed is True
    row = store.get_member(bot_hash, 'g_t1_65', 'm_65s')
    assert row is not None
    assert row['username'] == '65秒后成功'
    assert row['source'] == 'api'
    assert (str(bot_hash), 'g_t1_65', 'm_65s') not in common.sdkQQGroupTier1Pending


def test_memory_bounds_clear_group_calibration_and_stub_proc_logging(group_api, monkeypatch):
    """覆盖 G7.3 + 建议 1 + 建议 4：退避读删/写清理、预算耗尽不登记校准、Stage1 per_tick、无 log 属性 stub 不崩。"""
    bot, bot_hash, _ = group_api
    clock = [500.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_ensure_qq_group_calibration_thread', Mock())
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkQQGroupWarmDailyPageLimit', 5)

    # 1. sdkQQGroupApiBackoff 读取时 pop 过期项；写入超 2000 时清过期项。
    common.sdkQQGroupApiBackoff[(str(bot_hash), 'group_member_info', 'g_exp')] = 400.0
    ok_api = SimpleNamespace(
        metadata=SimpleNamespace(group_openid='g_exp'),
        res=json.dumps({'username': 'ok'}), res_code=200, do_api=Mock()
    )
    res = common._do_qq_group_api_request(bot, ok_api, 'GET', 'group_member_info')
    assert res['active'] is True
    assert (str(bot_hash), 'group_member_info', 'g_exp') not in common.sdkQQGroupApiBackoff

    for idx in range(2005):
        common.sdkQQGroupApiBackoff[(str(bot_hash), 'op', 'old_%d' % idx)] = 100.0
    common._set_qq_group_api_backoff(bot_hash, 'op', 'fresh', 60.0, now=500.0)
    assert list(common.sdkQQGroupApiBackoff.keys()) == [(str(bot_hash), 'op', 'fresh')]

    # 2. _qq_group_member_cache_clear_group 同时清除 sdkQQGroupCalibrationGroups 和该群退避。
    store.touch_group(bot_hash, 'g_del')
    common._register_qq_group_for_calibration(bot_hash, bot, 'g_del')
    common._set_qq_group_api_backoff(bot_hash, 'group_member_list', 'g_del', 60.0, now=500.0)
    common._qq_group_member_cache_clear_group(bot_hash, 'g_del')
    assert 'g_del' not in common.sdkQQGroupCalibrationGroups.get(str(bot_hash), {})
    assert (str(bot_hash), 'group_member_list', 'g_del') not in common.sdkQQGroupApiBackoff

    # 3. Calibration Stage 1 受 per_tick 限制，超出部分保留在优先队列待下轮。
    now = int(time.time())
    for gid in ('gp1', 'gp2', 'gp3'):
        store.upsert_group(bot_hash, gid, state='active', members_state='active', last_seen_at=now)
        common._register_qq_group_for_calibration(bot_hash, bot, gid)
    assert common._qq_group_calibration_tick(now=now, per_tick=2) == 2
    assert len(common.sdkQQGroupWarmQueue) == 2
    assert set(common.sdkQQGroupCalibrationGroups[str(bot_hash)]) == {'gp3'}

    # 4. 预算耗尽的 bot 不再登记到 sdkQQGroupCalibrationGroups。
    common.sdkQQGroupCalibrationGroups.clear()
    common._add_qq_group_warm_daily_pages(bot_hash, 5)
    common._register_qq_group_for_calibration(bot_hash, bot, 'g_exhausted')
    assert str(bot_hash) not in common.sdkQQGroupCalibrationGroups

    # 5. 无 log 属性的 stub gProc 不崩。
    monkeypatch.setattr(OlivOS.pluginAPI, 'gProc', SimpleNamespace())
    common._log_qq_user_info_minor_mode('u_minor_stub')
    store.upsert_group(bot_hash, 'g_stub_sus', state='suspect')
    monkeypatch.setattr(common.API, 'getQQGroupBotState', lambda bi: SimpleNamespace(
        metadata=SimpleNamespace(group_openid='g_stub_sus'),
        res=json.dumps({'code': 99999}), res_code=500, do_api=Mock()
    ))
    common._verify_qq_group_suspect(bot_hash, bot, 'g_stub_sus')


def test_suspect_verify_confirmed_11255_writes_group_bot_state_backoff(group_api, monkeypatch):
    """复现 M2：复核确认 11255 且代次一致时，写入 group_bot_state 24h 退避。"""
    bot, bot_hash, _ = group_api
    clock = [1000.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_schedule_qq_group_suspect_verify', lambda *args, **kwargs: True)

    store.touch_group(bot_hash, 'g_confirm')
    store.upsert_member(bot_hash, 'g_confirm', 'm1', username='u1')
    common._do_qq_group_api_request(bot, response_api(11255, 'g_confirm'), 'GET', 'group_member_list')
    assert (str(bot_hash), 'group_bot_state', 'g_confirm') not in common.sdkQQGroupApiBackoff

    class Err11255BotState(object):
        def __init__(self, sdk_bot):
            self.metadata = SimpleNamespace(group_openid=None)
            self.res = json.dumps({'code': 11255, 'message': 'invalid group'})
            self.res_code = 500

        def do_api(self, method='GET'):
            return self.res

    monkeypatch.setattr(common.API, 'getQQGroupBotState', Err11255BotState)

    # 场景 1：复核命中 11255 但未满 600s（重排复核）-> 写入 24h group_bot_state 退避。
    clock[0] = 1100.0
    common._verify_qq_group_suspect(bot_hash, bot, 'g_confirm')
    assert store.get_group(bot_hash, 'g_confirm')['state'] == 'suspect'
    backoff_key = (str(bot_hash), 'group_bot_state', 'g_confirm')
    assert backoff_key in common.sdkQQGroupApiBackoff
    assert common.sdkQQGroupApiBackoff[backoff_key] == 1100.0 + 86400.0

    # 场景 2：满 600s 后复核再次命中 11255（确认删群）-> 同样写入最新 24h group_bot_state 退避。
    clock[0] = 1600.0
    common._verify_qq_group_suspect(bot_hash, bot, 'g_confirm')
    assert store.get_group(bot_hash, 'g_confirm') is None
    assert backoff_key in common.sdkQQGroupApiBackoff
    assert common.sdkQQGroupApiBackoff[backoff_key] == 1600.0 + 86400.0


def test_tier1_backed_off_fails_without_retry(group_api, monkeypatch):
    """复现 S1：群级退避（backed_off=True）直接返回 failed，不进延迟重试表。"""
    bot, bot_hash, _ = group_api
    clock = [1000.0]
    monkeypatch.setattr(common.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(common, '_ensure_qq_group_tier1_thread', Mock())
    monkeypatch.setattr(common, '_register_qq_group_calibration_bot', Mock())

    api_called = Mock(side_effect=AssertionError('退避期内不应发起网络请求'))

    class GuardMemberInfo(object):
        def __init__(self, sdk_bot):
            self.metadata = SimpleNamespace(group_openid=None, member_openid=None)
            self.res = None
            self.res_code = None

        def do_api(self, method='GET'):
            return api_called()

    monkeypatch.setattr(common.API, 'getQQGroupMemberInfo', GuardMemberInfo)
    common._set_qq_group_api_backoff(bot_hash, 'group_member_info', 'g_t1_bo', 3600.0, now=1000.0)

    assert common._qq_group_member_tier1_complete(bot_hash, bot, 'g_t1_bo', 'm_bo') == 'failed'
    assert common._enqueue_qq_group_tier1(bot_hash, bot, 'g_t1_bo', 'm_bo') is True
    processed, _ = common._qq_group_tier1_step()
    assert processed is True
    api_called.assert_not_called()
    assert common.sdkQQGroupTier1Delayed == []
    assert (str(bot_hash), 'g_t1_bo', 'm_bo') not in common.sdkQQGroupTier1Pending


def test_group_del_robot_clears_warm_queue_and_allows_clean_rejoin(group_api, monkeypatch):
    """复现 S3：GROUP_DEL_ROBOT 清理该群 warm 队列/状态/失败冷却，避免拉回后复用旧 cursor。"""
    bot, _, _ = group_api
    account = OlivOS.API.bot_info_T(
        id=bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=bot.model
    )
    bot_hash = account.hash
    other_bot = common.bot_info_T(id=456, model='public')
    other_hash = OlivOS.API.getBotHash(
        bot_id=other_bot.id, platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild', platform_model=other_bot.model
    )
    monkeypatch.setattr(common, '_ensure_qq_group_warm_thread', Mock())
    monkeypatch.setattr(common, 'sdkSelfInfo', {bot_hash: {'id': str(bot.id), 'username': 'bot'}})
    monkeypatch.setattr(common, 'qqEventDedupeCache', {})
    monkeypatch.setattr(common, '_get_qq_group_self_open_id', lambda *args: 'SELF-OPENID')

    store.touch_group(bot_hash, 'g_kick')
    store.touch_group(bot_hash, 'g_stay')
    store.touch_group(other_hash, 'g_kick')
    assert common._enqueue_qq_group_warm(
        bot_hash, bot, 'g_kick', start_cursor='old_cursor', initial_seen={'m_old'}, scan_started_at=1000
    ) is True
    assert common._enqueue_qq_group_warm(bot_hash, bot, 'g_stay', start_cursor='stay_c') is True
    assert common._enqueue_qq_group_warm(other_hash, other_bot, 'g_kick', start_cursor='other_c') is True
    common.sdkQQGroupWarmFailCooldown[(str(bot_hash), 'g_kick')] = time.monotonic() + 300.0

    # 收到 GROUP_DEL_ROBOT 事件：清掉本 bot 该群全部 warm 队列/pending/seen/started_at/冷却。
    del_payload = OlivOS.qqGuildv2SDK.PAYLOAD.rxPacket({
        'op': 0,
        's': 1,
        't': 'GROUP_DEL_ROBOT',
        'd': {'id': 'evt-del-1', 'group_openid': 'g_kick', 'op_member_openid': 'op1'}
    })
    del_event = OlivOS.API.Event(OlivOS.qqGuildv2SDK.event(del_payload, account))
    assert del_event.active is True

    key = (str(bot_hash), 'g_kick')
    assert store.get_group(bot_hash, 'g_kick') is None
    assert key not in common.sdkQQGroupWarmPending
    assert key not in common.sdkQQGroupWarmSeen
    assert key not in common.sdkQQGroupWarmStartedAt
    assert key not in common.sdkQQGroupWarmFailCooldown
    # 其它群和其它 bot 的 warm 任务不受影响。
    assert [(t[0], t[2], t[3]) for t in common.sdkQQGroupWarmQueue] == [
        (str(bot_hash), 'g_stay', 'stay_c'),
        (str(other_hash), 'g_kick', 'other_c'),
    ]

    # 很快被重新拉回群：可立即从首页（空 cursor）干净入队，不受旧任务或失败冷却阻挡。
    add_payload = OlivOS.qqGuildv2SDK.PAYLOAD.rxPacket({
        'op': 0,
        's': 2,
        't': 'GROUP_ADD_ROBOT',
        'd': {'id': 'evt-add-1', 'group_openid': 'g_kick', 'op_member_openid': 'op1'}
    })
    add_event = OlivOS.API.Event(OlivOS.qqGuildv2SDK.event(add_payload, account))
    assert add_event.active is True
    assert common._enqueue_qq_group_warm(bot_hash, bot, 'g_kick', start_cursor='') is True
    assert common.sdkQQGroupWarmQueue[-1][0] == str(bot_hash)
    assert common.sdkQQGroupWarmQueue[-1][2] == 'g_kick'
    assert common.sdkQQGroupWarmQueue[-1][3] == ''
