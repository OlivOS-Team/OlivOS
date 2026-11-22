# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_user_info.py
@Author    :   Desom-fu
@Contact   :   desom233@outlook.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   QQ 官方机器人用户资料：缓存优先，群接口失败再打获取基本信息
'''

from types import SimpleNamespace
import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common
from OlivOS.adapter.qqGuild import qqGuildv2Store as store


SDK = OlivOS.qqGuildv2SDK


@pytest.fixture
def user_api(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store.close_db()
    store.open_db(tmp_path / 'cache.sqlite3')
    monkeypatch.setattr(common, 'sdkUserInfo', {})
    monkeypatch.setattr(common, 'sdkQQGroupApiDenied', set())
    monkeypatch.setattr(common, 'sdkQQUserInfoRateHistory', __import__('collections').deque())
    bot = OlivOS.API.bot_info_T(
        id='190001',
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='public'
    )
    event = SimpleNamespace(bot_info=bot)
    group_calls = []
    basic_calls = []

    def fake_group(target_event, group_openid, member_openid):
        group_calls.append((str(group_openid), str(member_openid)))
        return {'active': False, 'data': {'response': None, 'error_code': 11253}}

    def fake_basic(target_event, openid):
        basic_calls.append(str(openid))
        return {'username': '从基本信息来的', 'allow_proactive_msg': True, 'avatar': 'https://bad.example/a.png'}

    monkeypatch.setattr(SDK.event_action, '_request_qq_group_member_info', fake_group)
    monkeypatch.setattr(common, '_fetch_qq_user_basic_info', fake_basic)
    yield event, bot, group_calls, basic_calls
    store.close_db()


def test_rate_limit_is_ten_per_minute():
    assert common.qqUserInfoRateLimit == 10
    assert common.qqUserInfoRateWindow == 60.0


def test_cache_hit_does_not_call_api(user_api):
    event, bot, group_calls, basic_calls = user_api
    common._register_qq_user_info(bot.hash, {'id': 'u1', 'username': '缓存昵称'})
    result = SDK.event_action.get_stranger_info(event, 'u1', False)
    assert result['active'] is True
    assert result['data']['name'] == '缓存昵称'
    assert result['data']['avatar'] == 'https://q.qlogo.cn/qqapp/190001/u1/0'
    assert basic_calls == []
    assert group_calls == []
    assert 'avatar' not in common._get_qq_user_info(bot.hash, 'u1')


def test_private_miss_calls_basic_info_and_ignores_official_avatar(user_api):
    event, bot, group_calls, basic_calls = user_api
    result = SDK.event_action.get_stranger_info(event, 'u2', False)
    assert basic_calls == ['u2']
    assert group_calls == []
    assert result['data']['name'] == '从基本信息来的'
    assert result['data']['avatar'] == 'https://q.qlogo.cn/qqapp/190001/u2/0'
    assert result['data']['allow_proactive_msg'] is True
    cached = common._get_qq_user_info(bot.hash, 'u2')
    assert cached['name'] == '从基本信息来的'
    assert 'avatar' not in cached


def test_basic_info_failure_does_not_invent_name(user_api, monkeypatch):
    event, bot, _, _ = user_api
    monkeypatch.setattr(common, '_fetch_qq_user_basic_info', lambda *args: None)
    result = SDK.event_action.get_stranger_info(event, 'u3', False)
    assert result['data'].get('name') in (None, )
    assert result['data']['avatar'] == 'https://q.qlogo.cn/qqapp/190001/u3/0'
    assert common._get_qq_user_info(bot.hash, 'u3') is None


def test_group_tries_group_api_before_basic_info(user_api, monkeypatch):
    event, bot, group_calls, basic_calls = user_api

    def group_ok(target_event, group_openid, member_openid):
        group_calls.append((str(group_openid), str(member_openid)))
        return {
            'active': True,
            'data': {'response': {
                'member_openid': member_openid,
                'username': '群接口昵称',
                'member_role': 'admin'
            }}
        }

    monkeypatch.setattr(SDK.event_action, '_request_qq_group_member_info', group_ok)
    result = SDK.event_action.get_group_member_info(event, 'g1', 'm1', False)
    assert group_calls == [('g1', 'm1')]
    assert basic_calls == []
    assert result['data']['name'] == '群接口昵称'
    assert result['data']['avatar'] == 'https://q.qlogo.cn/qqapp/190001/m1/0'


def test_group_invalid_falls_back_to_basic_info(user_api):
    event, _, group_calls, basic_calls = user_api
    result = SDK.event_action.get_group_member_info(event, 'g1', 'm2', False)
    assert group_calls == [('g1', 'm2')]
    assert basic_calls == ['m2']
    assert result['data']['name'] == '从基本信息来的'


def test_11253_mark_skips_later_group_calls(user_api):
    event, bot, group_calls, basic_calls = user_api
    common._mark_qq_group_api_denied(bot.hash, 'group_member_info')
    SDK.event_action.get_group_member_info(event, 'g1', 'm3', False)
    assert group_calls == []
    assert basic_calls == ['m3']


def test_minor_mode_code_is_treated_as_miss_without_cache(monkeypatch):
    # 40011033:账号处于未成年人模式,平台不返回用户资料。按 miss 处理,
    # 不编数据、不进缓存。此用例直接用模块真实实现,不走 fixture 里的假实现。
    monkeypatch.setattr(common, 'sdkUserInfo', {})
    monkeypatch.setattr(common, 'sdkQQUserInfoMinorLogged', {})
    # 钉在开机不久：缺记录若被当成 0，这里会把第一次提示吞掉。
    monkeypatch.setattr(common.time, 'monotonic', lambda: 100.0)
    monkeypatch.setattr(common, 'sdkQQUserInfoRateHistory', __import__('collections').deque())
    bot = OlivOS.API.bot_info_T(
        id='190001',
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='public'
    )
    event = SimpleNamespace(bot_info=bot)
    calls = []

    class FakeAPI:
        @staticmethod
        def getQQUserInfo(bot_info):
            calls.append(1)

            class Obj:
                res = '{"err_code": 40011033, "message": "用户处于未成年人模式，暂不支持该操作"}'
                res_code = 400

                class metadata:
                    openid = '-1'

                def do_api(self, req_type='GET'):
                    return self.res

            return Obj()

    monkeypatch.setattr(common, 'API', FakeAPI)
    assert common._fetch_qq_user_basic_info(event, 'u_minor') is None
    assert calls == [1]
    assert common._get_qq_user_info(bot.hash, 'u_minor') is None
    # 未成年人模式只提示一次,不刷日志
    assert 'u_minor' in common.sdkQQUserInfoMinorLogged
    common.time.monotonic = lambda: 200.0
    common._log_qq_user_info_minor_mode('u_minor')
    assert common.sdkQQUserInfoMinorLogged['u_minor'] == 100.0


def test_missing_username_falls_back_to_stable_placeholder(user_api):
    # 平台没下发 username 时,插件侧的 sender['name'] 不能是空串或占位词「用户」。
    _, bot, _, _ = user_api
    openid = 'CF621F136B7B19AD1EDFC8A00D0728B2'
    event = SimpleNamespace(data=SimpleNamespace(sender={}), bot_info=bot)
    common._apply_incoming_sender(event, openid, '用户', 'member')
    assert event.data.sender['name'] == event.data.sender['nickname']
    assert event.data.sender['name'] not in ('', '用户', 'Nobody')
    assert event.data.sender['name'] == 'QQ用户0728B2'
    # 同一 openid 多次调用得到同一个名字
    again = SimpleNamespace(data=SimpleNamespace(sender={}), bot_info=bot)
    common._apply_incoming_sender(again, openid, None, 'member')
    assert again.data.sender['name'] == event.data.sender['name']
    # 真正的昵称到了就用真的
    real = SimpleNamespace(data=SimpleNamespace(sender={}), bot_info=bot)
    common._apply_incoming_sender(real, 'u9', '真昵称', 'member')
    assert real.data.sender['name'] == '真昵称'


def test_group_card_comes_from_member_nickname(user_api):
    event, bot, _, basic_calls = user_api
    common._register_qq_user_info(
        bot.hash,
        {
            'member_openid': 'm4',
            'username': 'QQ昵称',
            'member_nickname': '本群名片'
        },
        chat_type='qq_group',
        chat_id='g9'
    )
    result = SDK.event_action.get_group_member_info(event, 'g9', 'm4', False)
    assert basic_calls == []
    assert result['data']['name'] == 'QQ昵称'
    assert result['data']['card'] == '本群名片'
    assert result['data']['avatar'] == 'https://q.qlogo.cn/qqapp/190001/m4/0'


def test_group_message_sender_keeps_global_nickname_and_card_separately(
    user_api, monkeypatch
):
    event, bot, _, _ = user_api
    store.touch_group(bot.hash, 'g7')
    store.upsert_member(
        bot.hash, 'g7', 'm7', username='全局昵称', member_nickname='本群名片'
    )
    fake_event = SimpleNamespace(
        data=SimpleNamespace(sender={}), bot_info=bot
    )
    common._apply_incoming_sender(
        fake_event,
        'm7',
        common._get_qq_author_name_cached(
            bot.hash, {'member_openid': 'm7', 'username': '全局昵称'}, 'm7'
        ),
        'member',
        card=common._get_qq_group_member_card(
            bot.hash, {'member_openid': 'm7'}, 'g7', 'm7'
        )
    )
    assert fake_event.data.sender['name'] == '全局昵称'
    assert fake_event.data.sender['nickname'] == '全局昵称'
    assert fake_event.data.sender['card'] == '本群名片'


def test_group_card_helper_does_not_fall_back_to_username(user_api):
    _, bot, _, _ = user_api
    assert common._get_qq_group_member_card(
        bot.hash, {'member_openid': 'm8', 'username': '只有昵称'}, 'g8', 'm8'
    ) is None


def test_card_is_scoped_per_group(user_api):
    _, bot, _, _ = user_api
    common._register_qq_user_info(
        bot.hash,
        {'member_openid': 'm9', 'username': '同一个人', 'member_nickname': 'A群名片'},
        chat_type='qq_group',
        chat_id='group_a'
    )
    common._register_qq_user_info(
        bot.hash,
        {'member_openid': 'm9', 'username': '同一个人', 'member_nickname': 'B群名片'},
        chat_type='qq_group',
        chat_id='group_b'
    )
    assert common._get_qq_group_member_card(
        bot.hash, {'member_openid': 'm9'}, 'group_a', 'm9'
    ) == 'A群名片'
    assert common._get_qq_group_member_card(
        bot.hash, {'member_openid': 'm9'}, 'group_b', 'm9'
    ) == 'B群名片'
    # 没去过的群不能串用别的群名片
    assert common._get_qq_group_member_card(
        bot.hash, {'member_openid': 'm9'}, 'group_c', 'm9'
    ) is None
    # 全局昵称仍是同一个
    assert common._get_qq_user_name_from_cache(bot.hash, 'm9') == '同一个人'


def test_group_message_card_uses_that_group_only(user_api):
    event, bot, _, _ = user_api
    common._register_qq_user_info(
        bot.hash,
        {'member_openid': 'ma', 'username': '全局名', 'member_nickname': '甲群名片'},
        chat_type='qq_group',
        chat_id='gid_jia'
    )
    fake_event = SimpleNamespace(data=SimpleNamespace(sender={}), bot_info=bot)
    common._apply_incoming_sender(
        fake_event, 'ma', '全局名', 'member',
        card=common._get_qq_group_member_card(
            bot.hash, {'member_openid': 'ma'}, 'gid_yi', 'ma'
        )
    )
    assert fake_event.data.sender['name'] == '全局名'
    assert 'card' not in fake_event.data.sender
