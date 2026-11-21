'''OlivOS.API.Event 公共动作方法的离线路由矩阵测试。'''

from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest

import OlivOS


ACTION_MODULES = (
    'virtualTerminalSDK',
    'onebotV12SDK',
    'onebotSDK',
    'qqGuildSDK',
    'qqGuildv2SDK',
    'discordSDK',
    'telegramSDK',
    'fanbookSDK',
    'dodoLinkSDK',
    'dodoSDK',
    'dodobotEASDK',
    'kaiheilaSDK',
    'xiaoheiheSDK',
    'mhyVilaSDK',
    'qqRedSDK',
    'hackChatSDK',
    'OPQBotSDK',
    'dingtalkSDK',
    'biliLiveSDK',
    'milkySDK',
)

COMMON_DATA = {
    'message_id': 8,
    'group_id': 7,
    'user_id': 42,
    'host_id': 9,
    'operator_id': 5,
    'duration': 60,
    'flag': 'fixture-flag',
    'sub_type': 'add',
    'comment': 'hello',
    'extend': {
        'flag_from_qq': True,
        'flag_from_direct': False,
        'qq_event_type': 'MESSAGE_CREATE',
    },
}

METHOD_CALLS = [
    # remote=True 时必须在调用插件可见动作前短路，不能把远端事件误发给本机账号。
    ('set_block', (True,), {}, {}),
    # 群聊 send 应走群发送边界，同时保持字符串消息原样传递。
    ('send', ('group', 7, 'hello'), {}, {}),
    # 私聊 send 应与群聊分支分离，避免目标类型串用。
    ('send', ('private', 42, 'hello'), {}, {}),
    # 删除消息应进入消息生命周期动作路由。
    ('delete_msg', (8,), {}, {}),
    # 单条消息查询应进入查询动作路由。
    ('get_msg', (8,), {}, {}),
    # 合并转发详情查询应进入消息查询路由。
    ('get_forward_msg', (8,), {}, {}),
    # 发送群合并转发应保留节点数组参数。
    ('send_group_forward_msg', (7, []), {}, {}),
    # 发送私聊合并转发应保留目标用户参数。
    ('send_private_forward_msg', (42, []), {}, {}),
    # 设置群精华消息属于群管理动作。
    ('set_essence_msg', (8,), {}, {}),
    # 移除群精华消息属于群管理动作。
    ('delete_essence_msg', (8,), {}, {}),
    # 点赞动作应传递用户与次数。
    ('send_like', (42, 1), {}, {}),
    # 群签到动作应传递群号。
    ('send_group_sign', (7,), {}, {}),
    # 群精华列表查询应走只读查询分支。
    ('get_essence_msg_list', (7,), {}, {}),
    # 忽略加群请求查询应走群请求管理分支。
    ('get_group_ignore_add_request', (7,), {}, {}),
    # 陌生好友请求查询应保留起始序号。
    ('get_doubt_friends_add_request', (50,), {}, {}),
    # 陌生好友请求处理应保留请求标识与同意标志。
    ('set_doubt_friends_add_request', ('fixture-flag', True), {}, {}),
    # 群系统消息查询应保留起始序号。
    ('get_group_system_msg', (50,), {}, {}),
    # 群戳一戳应传递群号与目标用户。
    ('group_poke', (7, 42), {}, {}),
    # 群公告查询应传递群号。
    ('get_group_notice', (7,), {}, {}),
    # 群公告发送应保留置顶参数。
    ('send_group_notice', (7, 'notice'), {'pinned': 1}, {}),
    # 群公告删除应传递公告标识。
    ('del_group_notice', (7, 'notice'), {}, {}),
    # 好友戳一戳应传递目标用户。
    ('friend_poke', (42,), {}, {}),
    # 踢出群成员应同时传递群号和用户号。
    ('set_group_kick', (7, 42), {}, {}),
    # 禁言群成员应保留时长关键字参数。
    ('set_group_ban', (7, 42), {'duration': 60}, {}),
    # 匿名用户禁言应保留匿名标识与时长。
    ('set_group_anonymous_ban', (7, {}, 'fixture-flag'), {'duration': 60}, {}),
    # 全员禁言应传递开关值。
    ('set_group_whole_ban', (7, True), {}, {}),
    # 设置管理员应传递用户与启用状态。
    ('set_group_admin', (7, 42, True), {}, {}),
    # 开启匿名聊天应传递群号与开关值。
    ('set_group_anonymous', (7, True), {}, {}),
    # 修改群名片应传递用户与目标名片。
    ('set_group_card', (7, 42, 'card'), {}, {}),
    # 修改群名称应传递群号与新名称。
    ('set_group_name', (7, 'name'), {}, {}),
    # 退群动作应传递群号。
    ('set_group_leave', (7,), {}, {}),
    # 设置群头衔应保留目标用户、头衔和时长。
    ('set_group_special_title', (7, 42, 'title'), {'duration': 60}, {}),
    # 好友申请处理应保留请求标识、同意标志和备注。
    ('set_friend_add_request', ('fixture-flag', True, 'remark'), {}, {}),
    # 加群申请处理应保留子类型、同意标志和理由。
    ('set_group_add_request', ('fixture-flag', 'add', True, 'reason'), {}, {}),
    # 登录信息查询不应要求额外业务参数。
    ('get_login_info', (), {}, {}),
    # 陌生人信息查询应传递目标用户。
    ('get_stranger_info', (42,), {}, {}),
    # 好友列表查询不应要求额外业务参数。
    ('get_friend_list', (), {}, {}),
    # 群信息查询应传递群号。
    ('get_group_info', (7,), {}, {}),
    # 群列表查询不应要求额外业务参数。
    ('get_group_list', (), {}, {}),
    # 群成员信息查询应同时传递群号与用户号。
    ('get_group_member_info', (7, 42), {}, {}),
    # 群成员列表查询应传递群号。
    ('get_group_member_list', (7,), {}, {}),
    # 频道服务器列表查询不应要求额外业务参数。
    ('get_host_list', (), {}, {}),
    # 频道服务器信息查询应传递服务器标识。
    ('get_host_info', (9,), {}, {}),
    # 图片发送能力探测不应要求额外业务参数。
    ('can_send_image', (), {}, {}),
    # 语音发送能力探测不应要求额外业务参数。
    ('can_send_record', (), {}, {}),
    # 状态查询不应要求额外业务参数。
    ('get_status', (), {}, {}),
    # 版本查询不应要求额外业务参数。
    ('get_version_info', (), {}, {}),
    # 上传群文件应保留群号与文件路径。
    ('upload_group_file', (7, 'file.txt'), {}, {}),
    # 删除群文件应保留群号与文件标识。
    ('delete_group_file', (7, 'file-id'), {}, {}),
    # 创建群文件夹应保留群号与文件夹名。
    ('create_group_file_folder', (7, 'folder'), {}, {}),
    # 删除群文件夹应保留群号与文件夹标识。
    ('delete_group_folder', (7, 'folder-id'), {}, {}),
    # 群文件系统信息查询应传递群号。
    ('get_group_file_system_info', (7,), {}, {}),
    # 群根目录文件查询应传递群号。
    ('get_group_root_files', (7,), {}, {}),
    # 文件夹文件查询应保留群号与文件夹标识。
    ('get_group_files_by_folder', (7, 'folder-id'), {}, {}),
    # 群文件下载地址查询应保留分页参数。
    ('get_group_file_url', (7, 'file-id', 1), {}, {}),
    # 上传私聊文件应保留用户号、路径和显示名。
    ('upload_private_file', (42, 'file.txt', 'name'), {}, {}),
    # 重命名群文件夹应保留原标识与目标名称。
    ('rename_group_file_folder', (7, 'folder-id', 'new-folder'), {}, {}),
    # 重命名群文件应保留父目录与目标名称。
    ('rename_group_file', (7, 'file-id', '/', 'new-name'), {}, {}),
    # 设置群文件永久保存应保留群号与文件标识。
    ('set_group_file_forever', (7, 'file-id'), {}, {}),
    # 表情回应应保留群号回退字段，兼容只提供 message_id 的模型。
    ('set_msg_emoji_like', (8, 1), {'group_id': 7}, {}),
]


def _onebot_lists(active, model):
    lists = {
        'onebotV12LinkServerAPI': [],
        'flaskServerAPI': [],
        'onebotV11HostServerAPI': [],
        'onebotV11LinkServerAPI': [],
        'OPQBotLinkServerAPI': [],
        'qqRedLinkServerAPI': [],
    }
    lists[active] = [model]
    return lists


def _onebot_case(name, active):
    model = 'route_' + name
    return NS(name='onebot-' + name, sdk='onebot', platform='qq', model=model,
              lists=_onebot_lists(active, model))


PLATFORM_CASES = [
    _onebot_case('v12', 'onebotV12LinkServerAPI'),
    _onebot_case('flask', 'flaskServerAPI'),
    _onebot_case('host', 'onebotV11HostServerAPI'),
    _onebot_case('link', 'onebotV11LinkServerAPI'),
    _onebot_case('opq', 'OPQBotLinkServerAPI'),
    _onebot_case('red', 'qqRedLinkServerAPI'),
    NS(name='milky', sdk='milky', platform='qq', model='route_milky',
       lists={'milkyAutoServerAPI': ['route_milky']}),
    NS(name='qqGuildv2', sdk='qqGuildv2_link', platform='qqGuild', model='public', lists={}),
    NS(name='kaiheila', sdk='kaiheila_link', platform='kaiheila', model='default', lists={}),
    NS(name='xiaoheihe', sdk='xiaoheihe_link', platform='xiaoheihe', model='default', lists={}),
    NS(name='qqGuild', sdk='qqGuild_link', platform='qqGuild', model='default', lists={}),
    NS(name='discord', sdk='discord_link', platform='discord', model='default', lists={}),
    NS(name='telegram', sdk='telegram_poll', platform='telegram', model='default', lists={}),
    NS(name='fanbook', sdk='fanbook_poll', platform='fanbook', model='default', lists={}),
    NS(name='dodo-link', sdk='dodo_link', platform='dodo', model='v2', lists={}),
    NS(name='dodo-poll', sdk='dodo_poll', platform='dodo', model='default', lists={}),
    NS(name='dodobot-ea', sdk='dodobot_ea', platform='dodo', model='default', lists={}),
    NS(name='dingtalk', sdk='dingtalk_link', platform='dingtalk', model='default', lists={}),
    NS(name='biliLive', sdk='biliLive_link', platform='biliLive', model='default', lists={}),
    NS(name='hackChat', sdk='hackChat_link', platform='hackChat', model='default', lists={}),
    NS(name='mhyVila', sdk='mhyVila_link', platform='mhyVila', model='default', lists={}),
    NS(name='terminal', sdk='terminal_link', platform='terminal', model='default', lists={}),
    NS(name='unknown', sdk='unknown_link', platform='unknown', model='default', lists={}),
]

PLATFORM_CASE_MAP = {case.name: case for case in PLATFORM_CASES}


@pytest.fixture
def action_stubs(monkeypatch):
    stubs = {}
    for module_name in ACTION_MODULES:
        action = getattr(getattr(OlivOS, module_name), 'event_action', None)
        if action is None:
            continue
        for method_name in dir(action):
            if method_name.startswith('_'):
                continue
            if callable(getattr(action, method_name)):
                recorder = Mock(return_value=None)
                monkeypatch.setattr(action, method_name, recorder)
                stubs[(module_name, method_name)] = recorder
    return stubs


def apply_platform_lists(monkeypatch, case):
    for module_name, values in case.lists.items():
        monkeypatch.setattr(getattr(OlivOS, module_name), 'gCheckList', values)


def make_event(case, monkeypatch=None, data=None):
    if monkeypatch is not None:
        apply_platform_lists(monkeypatch, case)
    bot = OlivOS.API.bot_info_T(
        id=10001,
        platform_sdk=case.sdk,
        platform_platform=case.platform,
        platform_model=case.model,
    )
    sdk_event = OlivOS.contentAPI.fake_sdk_event(bot)
    event = OlivOS.API.Event(sdk_event, log_func=Mock())
    for name, value in COMMON_DATA.items():
        setattr(event.data, name, value)
    for name, value in (data or {}).items():
        setattr(event.data, name, value)
    return event


def called_stubs(stubs):
    return sorted(key for key, recorder in stubs.items() if recorder.called)


@pytest.mark.parametrize('method,args,kwargs,data', METHOD_CALLS, ids=[item[0] for item in METHOD_CALLS])
def test_remote_mode_short_circuits_before_adapter_dispatch(method, args, kwargs, data, action_stubs):
    """远程模式应在调用 adapter 前直接返回，避免把远端事件误发给本机账号。"""

    event = make_event(PLATFORM_CASE_MAP['onebot-flask'])
    result = getattr(event, method)(*args, remote=True, **kwargs)
    assert result is None
    assert called_stubs(action_stubs) == []


@pytest.mark.parametrize(
    'method,args,kwargs,data',
    METHOD_CALLS,
    ids=[item[0] for item in METHOD_CALLS],
)
@pytest.mark.parametrize('case', PLATFORM_CASES, ids=[case.name for case in PLATFORM_CASES])
def test_platform_route_dispatches_at_most_one_adapter_boundary(
    method, args, kwargs, data, case, action_stubs, monkeypatch
):
    """任一动作最多跨越一个 adapter 边界，防止一次调用重复投递到多个平台实现。"""

    event = make_event(case, monkeypatch=monkeypatch, data=data)
    getattr(event, method)(*args, **kwargs)
    calls = called_stubs(action_stubs)
    assert len(calls) <= 1, (method, case.name, calls)


ROUTE_EXPECTATIONS = [
    # OneBot V12 的删除消息应由 v12 link 适配器处理。
    ('delete_msg', (8,), {}, 'onebot-v12', ('onebotV12SDK', 'delete_msg')),
    # OneBot V11 HTTP 上报账号应走 flaskServerAPI 路由。
    ('delete_msg', (8,), {}, 'onebot-flask', ('onebotSDK', 'delete_msg')),
    # OneBot V11 反向 WebSocket 账号应走 host 路由。
    ('delete_msg', (8,), {}, 'onebot-host', ('onebotSDK', 'delete_msg')),
    # OneBot V11 正向 WebSocket 账号应走 link 路由。
    ('delete_msg', (8,), {}, 'onebot-link', ('onebotSDK', 'delete_msg')),
    # Milky 的删除消息不能被 OneBot 分支抢占。
    ('delete_msg', (8,), {}, 'milky', ('milkySDK', 'delete_msg')),
    # QQ 频道 v2 的删除消息映射到频道消息接口。
    ('delete_msg', (8,), {}, 'qqGuildv2', ('qqGuildv2SDK', 'delete_msg')),
    # OneBot 消息详情查询应命中当前 sdk 的 get_msg。
    ('get_msg', (8,), {}, 'onebot-flask', ('onebotSDK', 'get_msg')),
    # Milky 合并转发详情查询应命中独立查询接口。
    ('get_forward_msg', (8,), {}, 'milky', ('milkySDK', 'get_forward_msg')),
    # OneBot 群合并转发应命中群发送接口。
    ('send_group_forward_msg', (7, []), {}, 'onebot-link', ('onebotSDK', 'send_group_forward_msg')),
    # Milky 私聊合并转发应命中私聊发送接口。
    ('send_private_forward_msg', (42, []), {}, 'milky', ('milkySDK', 'send_private_forward_msg')),
    # QQ 频道“精华消息”对应频道置顶消息接口。
    ('set_essence_msg', (8,), {}, 'qqGuildv2', ('qqGuildv2SDK', 'set_pins_message')),
    # QQ 频道取消精华对应取消置顶消息接口。
    ('delete_essence_msg', (8,), {}, 'qqGuildv2', ('qqGuildv2SDK', 'delete_pins_message')),
    # Milky 点赞应命中自身动作而不是 OneBot 点赞。
    ('send_like', (42, 1), {}, 'milky', ('milkySDK', 'send_like')),
    # OneBot 群签到应命中对应动作。
    ('send_group_sign', (7,), {}, 'onebot-flask', ('onebotSDK', 'send_group_sign')),
    # QQ 频道群系统消息映射到加群请求列表标准接口。
    ('get_group_system_msg', (50,), {}, 'qqGuildv2',
     ('qqGuildv2SDK', 'get_qq_group_join_request_list_standard')),
    # OneBot 群戳一戳应命中群戳动作。
    ('group_poke', (7, 42), {}, 'onebot-flask', ('onebotSDK', 'group_poke')),
    # Milky 好友戳一戳应命中好友戳动作。
    ('friend_poke', (42,), {}, 'milky', ('milkySDK', 'friend_poke')),
    # 开黑啦踢人应命中自身群管理动作。
    ('set_group_kick', (7, 42), {}, 'kaiheila', ('kaiheilaSDK', 'set_group_kick')),
    # 小黑盒踢人应命中自身群管理动作。
    ('set_group_kick', (7, 42), {}, 'xiaoheihe', ('xiaoheiheSDK', 'set_group_kick')),
    # Milky 禁言应保留时长并命中自身动作。
    ('set_group_ban', (7, 42), {'duration': 60}, 'milky', ('milkySDK', 'set_group_ban')),
    # OneBot 设置管理员应命中群管理动作。
    ('set_group_admin', (7, 42, True), {}, 'onebot-flask', ('onebotSDK', 'set_group_admin')),
    # Milky 修改群名片应命中自身动作。
    ('set_group_card', (7, 42, 'card'), {}, 'milky', ('milkySDK', 'set_group_card')),
    # QQ 频道群名称修改映射到频道更新接口。
    ('set_group_name', (7, 'name'), {}, 'qqGuildv2', ('qqGuildv2SDK', 'patch_channel')),
    # Milky 退群应命中自身动作。
    ('set_group_leave', (7,), {}, 'milky', ('milkySDK', 'set_group_leave')),
    # Milky 好友申请处理应命中自身请求接口。
    ('set_friend_add_request', ('fixture-flag', True, 'remark'), {}, 'milky',
     ('milkySDK', 'set_friend_add_request')),
    # QQ 频道加群申请处理应命中标准请求接口。
    ('set_group_add_request', ('fixture-flag', 'add', True, 'reason'), {}, 'qqGuildv2',
     ('qqGuildv2SDK', 'set_group_add_request')),
    # Discord 登录信息查询应命中自身账号接口。
    ('get_login_info', (), {}, 'discord', ('discordSDK', 'get_login_info')),
    # OneBot 陌生人信息查询应命中用户查询接口。
    ('get_stranger_info', (42,), {}, 'onebot-flask', ('onebotSDK', 'get_stranger_info')),
    # Milky 好友列表应命中自身查询接口。
    ('get_friend_list', (), {}, 'milky', ('milkySDK', 'get_friend_list')),
    # QQ 频道群信息对应频道详情标准接口。
    ('get_group_info', (7,), {}, 'qqGuildv2', ('qqGuildv2SDK', 'get_channel_info_standard')),
    # 开黑啦群列表应命中自身查询接口。
    ('get_group_list', (), {}, 'kaiheila', ('kaiheilaSDK', 'get_group_list')),
    # 开黑啦群成员详情应命中自身查询接口。
    ('get_group_member_info', (7, 42), {}, 'kaiheila', ('kaiheilaSDK', 'get_group_member_info')),
    # QQ 频道成员列表对应频道成员标准接口。
    ('get_group_member_list', (7,), {}, 'qqGuildv2', ('qqGuildv2SDK', 'get_guild_member_list_standard')),
    # QQ 频道服务器列表对应频道服务器标准接口。
    ('get_host_list', (), {}, 'qqGuildv2', ('qqGuildv2SDK', 'get_guild_list_standard')),
    # QQ 频道服务器详情对应频道服务器标准接口。
    ('get_host_info', (9,), {}, 'qqGuildv2', ('qqGuildv2SDK', 'get_guild_info_standard')),
    # Milky 状态查询应命中自身动作。
    ('get_status', (), {}, 'milky', ('milkySDK', 'get_status')),
    # OneBot 版本查询应命中对应动作。
    ('get_version_info', (), {}, 'onebot-flask', ('onebotSDK', 'get_version_info')),
    # QQ 频道上传群文件应命中频道文件接口。
    ('upload_group_file', (7, 'file.txt'), {}, 'qqGuildv2', ('qqGuildv2SDK', 'upload_group_file')),
    # Milky 群文件地址查询应保留分页参数并命中自身接口。
    ('get_group_file_url', (7, 'file-id', 1), {}, 'milky', ('milkySDK', 'get_group_file_url')),
    # QQ 频道上传私聊文件应命中频道私聊文件接口。
    ('upload_private_file', (42, 'file.txt', 'name'), {}, 'qqGuildv2',
     ('qqGuildv2SDK', 'upload_private_file')),
    # QQ 频道表情回应应命中消息 reaction 接口。
    ('set_msg_emoji_like', (8, 1), {'group_id': 7}, 'qqGuildv2',
     ('qqGuildv2SDK', 'set_message_reaction')),
]


@pytest.mark.parametrize(
    'method,args,kwargs,case_name,expected',
    ROUTE_EXPECTATIONS,
    ids=[item[0] + '-' + item[3] for item in ROUTE_EXPECTATIONS],
)
def test_expected_platform_route_reaches_named_adapter_method(
    method, args, kwargs, case_name, expected, action_stubs, monkeypatch
):
    """每个平台动作必须命中预期的 adapter 方法，确保模型差异不会串路由。"""

    event = make_event(PLATFORM_CASE_MAP[case_name], monkeypatch=monkeypatch)
    getattr(event, method)(*args, **kwargs)
    assert called_stubs(action_stubs) == [expected]


@pytest.mark.parametrize(
    'case_name',
    ['telegram', 'unknown', 'terminal'],
)
def test_unsupported_platform_does_not_cross_dispatch_management_actions(case_name, action_stubs, monkeypatch):
    """不支持群管理的平台不得跨平台分派禁言、踢人或改名动作。"""

    event = make_event(PLATFORM_CASE_MAP[case_name], monkeypatch=monkeypatch)
    event.set_group_ban(7, 42, duration=60)
    event.set_group_kick(7, 42)
    event.set_group_card(7, 42, 'card')
    assert called_stubs(action_stubs) == []
