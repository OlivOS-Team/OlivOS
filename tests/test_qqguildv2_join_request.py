# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_join_request.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   群入群申请：列表拉取 / 审批 / 私有函数跨模块可见性
'''

import ast
import inspect

from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common
from OlivOS.adapter.qqGuild import qqGuildv2SDKGroup as group_sdk

# 群聊模块通过 `from .qqGuildv2SDKCommon import *` 取函数，星号导入不包含下划线开头的名字。
# 这些名字必须在 group 模块里能直接取到，否则运行期抛 NameError。
COMMON_PRIVATE_NAMES = (
    '_do_qq_group_api_request',
    '_get_qq_group_member_cache_members',
    '_get_qq_join_request_comment',
    '_make_qq_join_request_flag',
    '_parse_qq_join_request_flag',
    '_parse_qq_message_timestamp',
    '_qq_group_fetch_member_pages',
    '_qq_group_member_cache_remove_member',
    '_register_qq_group_for_calibration',
)


def test_group_sdk_can_see_common_private_helpers():
    # 2026-11 实测：IShowGame 审批入群报 NameError: name '_parse_qq_join_request_flag' is not defined
    missing = [name for name in COMMON_PRIVATE_NAMES if not hasattr(group_sdk, name)]
    assert missing == []
    for name in COMMON_PRIVATE_NAMES:
        assert getattr(group_sdk, name) is getattr(common, name)


def test_parse_qq_join_request_flag_roundtrip():
    flag = group_sdk._make_qq_join_request_flag('G-OPENID', 'M-OPENID', 'AURi8Rr6')
    assert group_sdk._parse_qq_join_request_flag(flag) == {
        'group_openid': 'G-OPENID',
        'member_openid': 'M-OPENID',
        'join_request_id': 'AURi8Rr6',
    }
    # 缺字段、非法 JSON、非字典一律返回 None，由调用方转成本地失败结果。
    assert group_sdk._parse_qq_join_request_flag('not-json') is None
    assert group_sdk._parse_qq_join_request_flag('{"group_openid": "G"}') is None
    assert group_sdk._parse_qq_join_request_flag([]) is None


def test_set_group_add_request_applies_to_qq_group_join_approval(monkeypatch):
    # 审批走官方 POST /v2/groups/{group_openid}/approval_join_request/{member_openid}
    calls = []

    def fake_approve(target_event, group_openid, member_openid, op, join_request_id=None, reject_reason=None):
        calls.append({
            'group_openid': group_openid, 'member_openid': member_openid,
            'op': op, 'join_request_id': join_request_id, 'reject_reason': reject_reason,
        })
        return 'ok'

    monkeypatch.setattr(common.event_action, 'approve_qq_group_join_request', staticmethod(fake_approve))
    monkeypatch.setattr(group_sdk, 'event_action', common.event_action)

    flag = group_sdk._make_qq_join_request_flag('G-1', 'M-1', 'REQ-1')
    assert group_sdk.event_action_group.set_group_add_request(None, flag, 'add', True) == 'ok'
    assert calls[-1] == {
        'group_openid': 'G-1', 'member_openid': 'M-1',
        'op': 'approve', 'join_request_id': 'REQ-1', 'reject_reason': None,
    }

    assert group_sdk.event_action_group.set_group_add_request(None, flag, 'add', False, '不认识') == 'ok'
    assert calls[-1]['op'] == 'decline'
    assert calls[-1]['reject_reason'] == '不认识'


def test_set_group_add_request_rejects_bad_flag_and_sub_type(monkeypatch):
    monkeypatch.setattr(group_sdk, 'event_action', common.event_action)
    bad_flag = group_sdk.event_action_group.set_group_add_request(None, 'not-json', 'add', True)
    assert bad_flag['active'] is False
    assert 'invalid QQ group join request flag' in str(bad_flag)

    flag = group_sdk._make_qq_join_request_flag('G-1', 'M-1', 'REQ-1')
    bad_type = group_sdk.event_action_group.set_group_add_request(None, flag, 'kick', True)
    assert bad_type['active'] is False
    assert 'unsupported group request sub_type' in str(bad_type)


def test_qqguild_v2_modules_can_see_all_common_private_helpers():
    """星号导入漏私有名是整包性问题，这里按模块逐个核对，防止再漏。"""
    from OlivOS.adapter.qqGuild import qqGuildv2SDKGuild as guild_sdk
    from OlivOS.adapter.qqGuild import qqGuildv2SDKGuildPrivate as guild_private_sdk

    modules = (group_sdk, guild_sdk, guild_private_sdk)
    # 频道本地图片走 multipart 时用到的工具函数。
    assert guild_sdk._send_channel_multipart is common._send_channel_multipart
    assert guild_private_sdk._send_channel_multipart is common._send_channel_multipart

    private_names = [
        name for name in dir(common)
        if name.startswith('_') and not name.startswith('__')
        and callable(getattr(common, name))
        and getattr(getattr(common, name), '__module__', '') == common.__name__
    ]
    missing = {}
    for module in modules:
        used = {
            node.id
            for node in ast.walk(ast.parse(inspect.getsource(module)))
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        lack = sorted(name for name in private_names if name in used and not hasattr(module, name))
        if lack:
            missing[module.__name__] = lack
    assert missing == {}
