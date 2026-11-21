'''真实 adapter API 的离线契约测试：只替换网络、队列和外部进程边界。'''

import json
import queue
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
import requests

import OlivOS
from adapter_api_support import (
    FakeHTTPResponse,
    RequestRecorder,
    json_body,
    kook_failed,
    kook_ok,
    make_bot,
    make_event,
    onebot_failed,
    onebot_ok,
    query_params,
    xhh_failed,
    xhh_ok,
)


@pytest.fixture
def onebot_http(monkeypatch):
    '''把 OneBot HTTP 层替换成可检查请求的离线记录器。'''

    recorder = RequestRecorder(FakeHTTPResponse(onebot_ok({})))
    monkeypatch.setattr(OlivOS.onebotSDK.req, 'request', recorder)
    return recorder


def test_onebot_post_sender_rejects_incomplete_connection(onebot_http):
    '''缺少账号、端点或请求体时不得发出半成品请求。'''

    sender = OlivOS.onebotSDK.send_onebot_post_json_T()
    sender.bot_info = OlivOS.onebotSDK.bot_info_T(id=1, host='', port=-1)
    sender.obj = NS(__dict__={'message_type': 'group'})
    sender.node_ext = 'send_group_msg'
    assert sender.send_onebot_post_json() is None
    assert onebot_http.calls == []


def test_onebot_private_post_drops_group_id_and_keeps_auth(onebot_http):
    '''私聊 POST 必须移除 group_id，同时携带 Bearer 头和访问令牌查询参数。'''

    sender = OlivOS.onebotSDK.send_onebot_post_json_T()
    sender.bot_info = OlivOS.onebotSDK.bot_info_T(
        id=1, host='https://127.0.0.1', port=5700, access_token='fixture-token')
    sender.obj = NS(message_type='private', user_id=42, group_id=7)
    sender.node_ext = 'send_private_msg'
    sender.send_onebot_post_json()
    call = onebot_http.calls[0]
    assert call.method == 'POST'
    assert call.url.startswith('https://127.0.0.1:5700/send_private_msg')
    assert query_params(call)['access_token'] == ['fixture-token']
    assert call.headers['Authorization'] == 'Bearer fixture-token'
    assert json_body(call) == {'message_type': 'private', 'user_id': 42}


def test_onebot_debug_logger_records_request_and_response(onebot_http):
    '''调试模式只调用注入的 logger，不向标准输出泄漏令牌或请求体。'''

    logger = Mock()
    sender = OlivOS.onebotSDK.send_onebot_post_json_T()
    sender.bot_info = OlivOS.onebotSDK.bot_info_T(id=1, host='127.0.0.1', port=5700)
    sender.bot_info.debug_mode = True
    sender.bot_info.debug_logger = logger
    sender.obj = NS(__dict__={'message_type': 'group', 'group_id': 7, 'message': 'hello'})
    sender.node_ext = 'send_group_msg'
    sender.send_onebot_post_json()
    assert logger.log.call_count == 2


def test_onebot_post_request_failure_is_nonfatal(monkeypatch):
    '''网络异常由发送层吞掉并返回 None，调用方仍能得到失败结果。'''

    monkeypatch.setattr(
        OlivOS.onebotSDK.req,
        'request',
        RequestRecorder(error=requests.Timeout('fixture timeout')),
    )
    event = make_event(make_bot())
    result = OlivOS.onebotSDK.event_action.send_group_msg(event, '7', 'hello')
    assert result['active'] is False
    assert result['data']['error'] == '协议端无有效响应'


@pytest.mark.parametrize(
    'server_type,expected_type',
    [
        # 正向 WebSocket 必须把动作投递到 link 组件。
        ('websocket', 'onebotV11_link'),
        # 反向 WebSocket 必须把动作投递到 host 组件。
        ('websocket_host', 'onebotV11_host'),
    ],
)
def test_onebot_websocket_api_serializes_params_and_reads_response(monkeypatch, server_type, expected_type):
    '''WebSocket 发送保留 echo/action/params，并从等待队列解析回包。'''

    sent = []
    monkeypatch.setattr(OlivOS.onebotSDK, 'waitForResReady', Mock())
    monkeypatch.setattr(OlivOS.onebotSDK, 'send_ws_event', lambda **kwargs: sent.append(kwargs))
    monkeypatch.setattr(
        OlivOS.onebotSDK,
        'waitForRes',
        lambda echo: onebot_ok({'message_id': 8}),
    )
    bot = make_bot(server_type=server_type)
    action = OlivOS.onebotSDK.api.send_group_msg(OlivOS.onebotSDK.get_SDK_bot_info_from_Event(make_event(bot)))
    action.data.group_id = 7
    action.data.message = 'hello'
    result = action.do_api(control_queue=queue.Queue())
    assert result.body == onebot_ok({'message_id': 8})
    dumped = json.loads(sent[0]['data'])
    assert sent[0]['type'] == expected_type
    assert dumped['action'] == 'send_group_msg'
    assert dumped['params'] == {'group_id': 7, 'message': 'hello', 'auto_escape': False}
    assert dumped['echo'] == action.echo


def test_onebot_websocket_exception_becomes_empty_result(monkeypatch):
    '''等待回包异常时 do_api 返回 None，而不是把异常抛给插件。'''

    monkeypatch.setattr(OlivOS.onebotSDK, 'waitForResReady', Mock(side_effect=RuntimeError('closed')))
    action = OlivOS.onebotSDK.api.get_login_info(
        OlivOS.onebotSDK.get_SDK_bot_info_from_Event(make_event(make_bot(server_type='websocket'))))
    assert action.do_api(control_queue=queue.Queue()) is None


def test_onebot_get_api_success_and_failure_are_non_blocking(onebot_http):
    '''GET 查询成功返回响应；连接异常返回 None 并清理 res。'''

    bot = OlivOS.onebotSDK.get_SDK_bot_info_from_Event(make_event(make_bot()))
    action = OlivOS.onebotSDK.api.get_group_info(bot)
    assert action.do_api_get() is onebot_http.response
    assert onebot_http.calls[-1].method == 'GET'
    assert action.res is onebot_http.response


def test_onebot_get_api_invalid_configuration_skips_request(onebot_http):
    '''GET 查询缺少 host/port/node_ext 时不发请求。'''

    action = OlivOS.onebotSDK.api.get_group_info(OlivOS.onebotSDK.bot_info_T(id=1))
    assert action.do_api_get() is None
    assert onebot_http.calls == []


def _endpoint(call):
    '''提取请求路径最后一段，便于逐项断言 OneBot 动作名。'''

    return call.url.split('?', 1)[0].rstrip('/').rsplit('/', 1)[-1]


def test_onebot_management_actions_build_expected_endpoints(onebot_http):
    '''常用管理接口必须命中对应 OneBot 动作，并把参数放进 JSON 请求体。'''

    event = make_event(make_bot())
    actions = OlivOS.onebotSDK.event_action
    actions.delete_msg(event, 8)
    actions.send_group_forward_msg(event, 7, [{'type': 'node', 'data': {}}])
    actions.send_private_forward_msg(event, 42, [{'type': 'node', 'data': {}}])
    actions.set_essence_msg(event, 8)
    actions.delete_essence_msg(event, 8)
    actions.send_like(event, 42, 3)
    actions.send_group_sign(event, 7)
    actions.set_group_kick(event, 7, 42, True)
    actions.set_group_ban(event, 7, 42, 60)
    actions.set_group_anonymous_ban(event, 7, {'id': 1}, 'flag', 60)
    actions.set_group_whole_ban(event, 7, True)
    actions.set_group_admin(event, 7, 42, True)
    actions.set_group_anonymous(event, 7, True)
    actions.set_group_card(event, 7, 42, 'card')
    actions.set_group_name(event, 7, 'name')
    actions.set_group_leave(event, 7, True)
    actions.set_group_special_title(event, 7, 42, 'title', 60)
    actions.set_friend_add_request(event, 'flag', True, 'remark')
    actions.set_group_add_request(event, 'flag', 'add', True, 'reason')
    actions.send_guild_channel_msg(event, 9, 7, 'hello')
    actions.send_group_notice(event, 7, 'notice', image='https://example.invalid/a.png')
    actions.upload_group_file(event, 7, 'file.txt', 'name', 'folder')
    actions.delete_group_file(event, 7, 'file-id')
    actions.create_group_file_folder(event, 7, 'folder', '/')
    actions.delete_group_folder(event, 7, 'folder-id')
    actions.upload_private_file(event, 42, 'file.txt', 'name')
    assert [_endpoint(call) for call in onebot_http.calls] == [
        'delete_msg',
        'send_group_forward_msg',
        'send_private_forward_msg',
        'set_essence_msg',
        'delete_essence_msg',
        'send_like',
        'send_group_sign',
        'set_group_kick',
        'set_group_ban',
        'set_group_anonymous_ban',
        'set_group_whole_ban',
        'set_group_admin',
        'set_group_anonymous',
        'set_group_card',
        'set_group_name',
        'set_group_leave',
        'set_group_special_title',
        'set_friend_add_request',
        'set_group_add_request',
        'send_guild_channel_msg',
        '_send_group_notice',
        'upload_group_file',
        'delete_group_file',
        'create_group_file_folder',
        'delete_group_folder',
        'upload_private_file',
    ]
    assert json_body(onebot_http.calls[0]) == {'message_id': '8'}
    assert json_body(onebot_http.calls[12]) == {'group_id': 7, 'enable': True}
    assert json_body(onebot_http.calls[16])['duration'] == 60
    assert json_body(onebot_http.calls[20])['image'] == 'https://example.invalid/a.png'
    assert json_body(onebot_http.calls[21])['folder_id'] == 'folder'
    assert json_body(onebot_http.calls[22])['parent_id'] == '/'


@pytest.mark.parametrize(
    'model,expected',
    [
        # NapCat 通过 trans_group_file 转永久。
        ('napcat_default', 'trans_group_file'),
        # LLOneBot 使用独立 set_group_file_forever 动作。
        ('llonebot_default', 'set_group_file_forever'),
    ],
)
def test_onebot_file_forever_uses_model_specific_endpoint(monkeypatch, model, expected):
    '''群文件转永久在各协议实现中动作名不同，不能共用单一路径。'''

    recorder = RequestRecorder(FakeHTTPResponse(onebot_ok({})))
    monkeypatch.setattr(OlivOS.onebotSDK.req, 'request', recorder)
    event = make_event(make_bot(model=model))
    OlivOS.onebotSDK.event_action.set_group_file_forever(event, 7, 'file-id')
    assert _endpoint(recorder.calls[0]) == expected


def test_onebot_lagrange_file_forever_is_unsupported(onebot_http):
    '''Lagrange 未实现文件转永久时必须静默跳过。'''

    event = make_event(make_bot(model='lagrange_default'))
    OlivOS.onebotSDK.event_action.set_group_file_forever(event, 7, 'file-id')
    assert onebot_http.calls == []


@pytest.mark.parametrize(
    'model,is_set,expected',
    [
        # NapCat 统一使用 set_msg_emoji_like，由 set 字段表示添加/取消。
        ('napcat_default', True, 'set_msg_emoji_like'),
        ('napcat_default', False, 'set_msg_emoji_like'),
        # LLOneBot 添加和取消使用不同动作。
        ('llonebot_default', True, 'set_msg_emoji_like'),
        ('llonebot_default', False, 'unset_msg_emoji_like'),
        # Lagrange 使用群表情回应接口。
        ('lagrange_default', True, 'set_group_reaction'),
    ],
)
def test_onebot_emoji_like_model_routes(monkeypatch, model, is_set, expected):
    '''表情回应必须按模型选择动作，并传递 is_set/group_id 语义。'''

    recorder = RequestRecorder(FakeHTTPResponse(onebot_ok({})))
    monkeypatch.setattr(OlivOS.onebotSDK.req, 'request', recorder)
    event = make_event(make_bot(model=model))
    OlivOS.onebotSDK.event_action.set_msg_emoji_like(event, 8, 1, is_set=is_set, group_id=7)
    assert _endpoint(recorder.calls[0]) == expected


def test_onebot_lagrange_emoji_like_requires_group_id(onebot_http):
    '''Lagrange 缺少群号时无法构造表情回应，必须显式报错。'''

    event = make_event(make_bot(model='lagrange_default'))
    with pytest.raises(ValueError, match='group_id'):
        OlivOS.onebotSDK.event_action.set_msg_emoji_like(event, 8, 1, group_id=None)


def test_onebot_napcat_notice_and_file_options(monkeypatch):
    '''NapCat 独有公告参数和 file_count 应进入请求体。'''

    recorder = RequestRecorder(FakeHTTPResponse(onebot_ok({'files': [], 'folders': []})))
    monkeypatch.setattr(OlivOS.onebotSDK.req, 'request', recorder)
    event = make_event(make_bot(model='napcat_default'))
    actions = OlivOS.onebotSDK.event_action
    actions.send_group_notice(
        event, 7, 'notice', pinned=True, type='text', confirm_required=True,
        is_show_edit_card=True, tip_window_type='tip')
    actions.get_group_root_files(event, 7, 20)
    actions.rename_group_file(event, 7, 'file-id', '/', 'new-name')
    body = json_body(recorder.calls[0])
    assert body['pinned'] is True and body['type'] == 'text'
    assert body['confirm_required'] is True and body['is_show_edit_card'] is True
    assert json_body(recorder.calls[1])['file_count'] == 20
    assert json_body(recorder.calls[2])['current_parent_directory'] == '/'


def test_onebot_query_actions_map_rich_responses(monkeypatch):
    '''查询接口必须把平台字段映射成 OlivOS 公共结构，并保持 active 语义。'''

    responses = [
        onebot_ok({'message_id': 8, 'real_id': 9, 'sender': {'user_id': 42, 'nickname': 'tester'},
                   'time': 1, 'message': 'hello', 'raw_message': 'hello'}),
        onebot_ok({'messages': [{'sender': {'nickname': 'tester'}}]}),
        onebot_ok({'nickname': 'bot', 'user_id': 10001}),
        onebot_ok({'nickname': 'stranger', 'user_id': 42}),
        onebot_ok([{'nickname': 'friend', 'user_id': 42}]),
        onebot_ok({'group_name': 'group', 'group_id': 7, 'group_memo': 'memo',
                   'member_count': 3, 'max_member_count': 10}),
        onebot_ok([{'group_name': 'group', 'group_id': 7, 'group_memo': 'memo',
                    'member_count': 3, 'max_member_count': 10}]),
        onebot_ok({'nickname': 'member', 'user_id': 42, 'group_id': 7, 'join_time': 1,
                   'last_sent_time': 2, 'shut_up_timestamp': 0, 'role': 'admin',
                   'card': 'card', 'title': 'title'}),
        onebot_ok([{'nickname': 'member', 'user_id': 42, 'group_id': 7, 'join_time': 1,
                    'last_sent_time': 2, 'shut_up_timestamp': 0, 'role': 'admin',
                    'card': 'card', 'title': 'title'}]),
        onebot_ok({'yes': True}),
        onebot_ok({'yes': True}),
        onebot_ok({'online': True, 'stat': {
            'packet_received': 1, 'packet_sent': 2, 'packet_lost': 0,
            'message_received': 3, 'message_sent': 4, 'disconnect_times': 0,
            'lost_times': 0, 'last_message_time': 5}}),
        onebot_ok({'app_name': 'OneBot', 'app_full_name': 'OneBot 11', 'app_version': '11',
                   'coolq_directory': '/tmp', 'runtime_os': 'linux'}),
        onebot_ok({'nickname': 'guild-member', 'tiny_id': 'tiny', 'join_time': 1}),
        onebot_ok([{'sender_id': 42, 'publish_time': 1, 'message': {'text': 'notice'},
                    'notice_id': '8'}]),
        onebot_ok({'file_count': 1, 'limit_count': 10, 'used_space': 2, 'total_space': 3}),
        onebot_ok({'files': [{'file_id': 'f'}], 'folders': [{'folder_id': 'd'}]}),
        onebot_ok({'files': [], 'folders': []}),
        onebot_ok({'url': 'https://example.invalid/file'}),
        onebot_ok([{'sender_id': 42, 'sender_nick': 'tester', 'sender_time': 1,
                    'operator_id': 5, 'operator_nick': 'op', 'operator_time': 2,
                    'message_id': 8, 'message': 'hello', 'wording': 'w',
                    'msg_seq': 1, 'msg_random': 2, 'content': []}]),
        onebot_ok([{'request_id': 8, 'invitor_uin': 42, 'invitor_nick': 'tester',
                    'group_id': 7, 'group_name': 'group', 'checked': False,
                    'actor': 5, 'requester_nick': 'req', 'message': 'join'}]),
        onebot_ok([{'flag': 'flag', 'uin': '42', 'nick': 'tester', 'source': 'qq',
                    'reason': 'hi', 'msg': 'hello', 'group_code': '7', 'time': '1',
                    'type': 'friend'}]),
        onebot_ok({'invited_requests': [{'request_id': 1}], 'join_requests': [{'request_id': 2}]}),
    ]
    recorder = RequestRecorder(responses=[FakeHTTPResponse(body) for body in responses])
    monkeypatch.setattr(OlivOS.onebotSDK.req, 'request', recorder)
    event = make_event(make_bot(model='napcat_default'))
    actions = OlivOS.onebotSDK.event_action
    results = [
        actions.get_msg(event, 8),
        actions.get_forward_msg(event, 8),
        actions.get_login_info(event),
        actions.get_stranger_info(event, 42),
        actions.get_friend_list(event),
        actions.get_group_info(event, 7),
        actions.get_group_list(event),
        actions.get_group_member_info(event, 7, 42),
        actions.get_group_member_list(event, 7),
        actions.can_send_image(event),
        actions.can_send_record(event),
        actions.get_status(event),
        actions.get_version_info(event),
        actions.get_guild_member_profile(event, 9, 42),
        actions.get_group_notice(event, 7),
        actions.get_group_file_system_info(event, 7),
        actions.get_group_root_files(event, 7),
        actions.get_group_files_by_folder(event, 7, 'folder'),
        actions.get_group_file_url(event, 7, 'file', 1),
        actions.get_essence_msg_list(event, 7),
        actions.get_group_ignore_add_request(event, 7),
        actions.get_doubt_friends_add_request(event, 50),
        actions.get_group_system_msg(event, 50),
    ]
    assert all(result['active'] for result in results)
    assert results[0]['data']['message_id'] == '8'
    assert results[4]['data'][0]['id'] == '42'
    assert results[7]['data']['times']['join_time'] == 1
    assert results[11]['data']['status']['message_sent'] == 4
    assert results[14]['data'][0]['extra']['notice_id_type'] == 'string'
    assert results[19]['data'][0]['extra']['msg_seq'] == 1
    assert results[22]['data']['join_requests'] == [{'request_id': 2}]
    assert len(recorder.calls) == len(responses)


@pytest.mark.parametrize('response', [onebot_failed(1404, 'denied'), 'not json', '{}'])
def test_onebot_query_failure_stays_inactive(monkeypatch, response):
    '''业务失败、非 JSON 和空对象不能让查询结果错误地标记为 active。'''

    recorder = RequestRecorder(FakeHTTPResponse(response))
    monkeypatch.setattr(OlivOS.onebotSDK.req, 'request', recorder)
    event = make_event(make_bot())
    result = OlivOS.onebotSDK.event_action.get_group_info(event, 7)
    assert result['active'] is False


def test_onebot_reply_helpers_route_to_public_or_group_send(onebot_http):
    '''reply_private_msg/reply_group_msg 使用事件中的目标，而不是调用方伪造。'''

    event = make_event(make_bot())
    OlivOS.onebotSDK.event_action.reply_private_msg(event, 'private-reply')
    OlivOS.onebotSDK.event_action.reply_group_msg(event, 'group-reply')
    first, second = onebot_http.calls
    assert _endpoint(first) == 'send_msg'
    assert json_body(first)['message_type'] == 'private'
    assert json_body(first)['user_id'] == '42'
    assert json_body(second)['message_type'] == 'group'
    assert json_body(second)['group_id'] == '7'


def test_onebot_para_model_serializes_message_segments(onebot_http):
    '''para 系列模型必须把 CQ 文本转换成结构化消息段数组。'''

    event = make_event(make_bot(model='shamrock_default'))
    OlivOS.onebotSDK.event_action.send_group_msg(event, 7, 'hello[CQ:at,qq=42]')
    body = json_body(onebot_http.calls[0])
    assert isinstance(body['message'], list)
    assert any(item.get('type') == 'at' for item in body['message'])


@pytest.mark.parametrize(
    'raw,expected',
    [
        # status=ok 即使 retcode 非零也按已受理处理。
        ({'status': 'ok', 'retcode': 9, 'data': {'message_id': 8}}, 8),
        # 仅 retcode=0 且无 status 的协议端也按成功处理。
        ({'retcode': 0, 'data': {'message_id': 8}}, 8),
        # retcode=1 表示异步已接收。
        ({'retcode': 1, 'data': {}}, None),
    ],
)
def test_onebot_send_result_accepts_legacy_success_shapes(raw, expected):
    '''兼容没有 status 字段的 OneBot 实现，并正确提取 message_id。'''

    action = NS(res=NS(body=raw))
    result = OlivOS.onebotSDK.get_send_result(action)
    assert result['active'] is True
    assert result['data']['message_id'] == (str(expected) if expected is not None else None)


@pytest.mark.parametrize(
    'raw,error',
    [
        # message 字段优先于默认 retcode 文案。
        ({'status': 'failed', 'retcode': 1, 'message': 'message-error'}, 'message-error'),
        # 没有 wording/message 时使用 msg 字段。
        ({'status': 'failed', 'retcode': 1, 'msg': 'msg-error'}, 'msg-error'),
        # 所有文案缺失时生成稳定的 retcode 提示。
        ({'status': 'failed', 'retcode': 1404}, '协议端返回失败（retcode=1404）'),
    ],
)
def test_onebot_send_result_extracts_failure_text(raw, error):
    '''失败回包的 wording/message/msg 与兜底文案必须一致。'''

    result = OlivOS.onebotSDK.get_send_result(NS(res=NS(body=raw)))
    assert result['active'] is False
    assert result['data']['error'] == error


@pytest.mark.parametrize(
    'method,suffix',
    [
        # 异步接口保留基础动作并追加 _async。
        ('do_api_async', 'send_group_msg_async'),
        # 限流接口保留基础动作并追加 _rate_limited。
        ('do_api_rate_limited', 'send_group_msg_rate_limited'),
    ],
)
def test_onebot_async_and_rate_limited_endpoints(onebot_http, method, suffix):
    '''两个扩展发送入口只能在动作名后追加后缀，不能改坏基础请求体。'''

    bot = OlivOS.onebotSDK.get_SDK_bot_info_from_Event(make_event(make_bot()))
    action = OlivOS.onebotSDK.api.send_group_msg(bot)
    action.data.group_id = 7
    action.data.message = 'hello'
    getattr(action, method)()
    assert _endpoint(onebot_http.calls[0]) == suffix
    assert json_body(onebot_http.calls[0])['group_id'] == 7


def test_onebot_post_do_api_swallows_invalid_sender(onebot_http, monkeypatch):
    '''POST 发送层返回 None 时 do_api 不得访问 text 属性而崩溃。'''

    monkeypatch.setattr(OlivOS.onebotSDK.send_onebot_post_json_T, 'send_onebot_post_json', lambda self: None)
    bot = OlivOS.onebotSDK.get_SDK_bot_info_from_Event(make_event(make_bot()))
    action = OlivOS.onebotSDK.api.get_login_info(bot)
    assert action.do_api() is None


@pytest.fixture
def kook_http(monkeypatch):
    '''KOOK 网络替身，并固定管理员角色查询避免额外请求。'''

    recorder = RequestRecorder(FakeHTTPResponse(kook_ok({})))
    monkeypatch.setattr(OlivOS.kaiheilaSDK.req, 'request', recorder)
    monkeypatch.setattr(OlivOS.kaiheilaSDK, 'get_guild_admin_role_id', lambda *args: [])
    return recorder


def test_kook_post_filters_none_fields_and_sets_bot_authorization(kook_http):
    '''KOOK POST 只发送非 None 字段，并使用 Bot token 鉴权。'''

    bot = OlivOS.kaiheilaSDK.get_SDK_bot_info_from_Event(
        make_event(make_bot(sdk='kaiheila_link', platform='kaiheila', access_token='kook-token')))
    action = OlivOS.kaiheilaSDK.API.createMessage(bot)
    action.data.target_id = '7'
    action.data.content = 'hello'
    action.do_api('POST')
    call = kook_http.calls[0]
    assert call.method == 'POST'
    assert call.url.endswith('/message/create')
    assert call.headers['Authorization'] == 'Bot kook-token'
    assert json_body(call) == {'type': 1, 'target_id': '7', 'content': 'hello'}


def test_kook_get_api_uses_query_metadata_and_returns_text(kook_http):
    '''KOOK GET 查询把 metadata 渲染进路由，并返回原始文本。'''

    bot = OlivOS.kaiheilaSDK.get_SDK_bot_info_from_Event(
        make_event(make_bot(sdk='kaiheila_link', platform='kaiheila')))
    action = OlivOS.kaiheilaSDK.API.getChannelView(bot)
    action.metadata.target_id = '7'
    result = action.do_api('GET')
    assert result == kook_http.response.text
    assert kook_http.calls[0].method == 'GET'
    assert '/channel/view' in kook_http.calls[0].url


def test_kook_request_exception_returns_none(monkeypatch):
    '''KOOK 网络异常不得抛给插件，do_api 返回 None。'''

    monkeypatch.setattr(
        OlivOS.kaiheilaSDK.req,
        'request',
        RequestRecorder(error=requests.ConnectionError('offline')),
    )
    bot = OlivOS.kaiheilaSDK.get_SDK_bot_info_from_Event(
        make_event(make_bot(sdk='kaiheila_link', platform='kaiheila')))
    assert OlivOS.kaiheilaSDK.API.getMe(bot).do_api('GET') is None


def test_kook_queries_and_management_map_success_payload(kook_http):
    '''KOOK 查询与管理接口在 code=0 时返回 active，并映射公共字段。'''

    payload = {'id': '9', 'username': 'tester', 'nickname': 'tester', 'joined_at': 1,
               'is_master': True, 'roles': [1], 'topic': 'topic', 'name': 'channel',
               'items': [{'id': '7', 'name': 'channel', 'username': 'tester',
                          'nickname': 'tester', 'is_master': False, 'roles': [1]}]}
    kook_http.response = FakeHTTPResponse(kook_ok(payload))
    event = make_event(make_bot(sdk='kaiheila_link', platform='kaiheila'))
    actions = OlivOS.kaiheilaSDK.event_action
    results = [
        actions.get_login_info(event),
        actions.get_stranger_info(event, 42),
        actions.get_group_member_info(event, 9, 42),
        actions.get_host_list(event),
        actions.get_host_info(event, 9),
        actions.get_group_member_list(event, 7),
        actions.set_group_card(event, 7, 42, 'card'),
        actions.set_group_leave(event, 7),
        actions.set_group_kick(event, 7, 42),
        actions.get_guild_mute_list(event, 7),
        actions.set_guild_mute_create(event, 7, 42),
        actions.set_guild_mute_delete(event, 7, 42),
        actions.get_guild_boost_history(event, 7, 1, 2),
        actions.get_group_list(event, 9, channel_type=1, parent_id=7),
        actions.get_group_info(event, 7, need_children=True),
    ]
    assert all(result['active'] for result in results)
    assert results[0]['data']['name'] == 'tester'
    assert results[2]['data']['role'] == 'owner'
    assert results[8]['data'] == {}


@pytest.mark.parametrize('response', [kook_failed(), 'not json', '{}'])
def test_kook_failed_response_keeps_queries_inactive(monkeypatch, response):
    '''业务错误、非 JSON 和空对象都不得被解释成成功。'''

    monkeypatch.setattr(OlivOS.kaiheilaSDK.req, 'request', RequestRecorder(FakeHTTPResponse(response)))
    event = make_event(make_bot(sdk='kaiheila_link', platform='kaiheila'))
    assert OlivOS.kaiheilaSDK.event_action.get_login_info(event)['active'] is False


def test_kook_send_msg_card_text_media_and_direct(kook_http, monkeypatch):
    '''发送入口按模型/消息段选择文本、卡片、图片、视频、音频和私聊路由。'''

    uploaded = []
    monkeypatch.setattr(
        OlivOS.kaiheilaSDK.event_action,
        'setResourceUploadFast',
        lambda target_event, url, type_path: uploaded.append((url, type_path)) or 'https://uploaded',
    )
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('hello'),
        OlivOS.messageAPI.PARA.image('image.png'),
        OlivOS.messageAPI.PARA.video('video.mp4'),
        OlivOS.messageAPI.PARA.record('audio.mp3'),
    ])
    event = make_event(make_bot(sdk='kaiheila_link', platform='kaiheila'))
    OlivOS.kaiheilaSDK.event_action.send_msg(event, 7, message)
    OlivOS.kaiheilaSDK.event_action.send_msg(event, 42, message, flag_direct=True)
    OlivOS.kaiheilaSDK.event_action.send_msg(event, 7, message, message_type_in='text')
    # 卡片两次各发一条；文本模式先发文本，再单独发图片。
    assert len(kook_http.calls) == 5
    assert kook_http.calls[0].url.endswith('/message/create')
    assert kook_http.calls[1].url.endswith('/direct-message/create')
    assert [json_body(call)['type'] for call in kook_http.calls[2:]] == [9, 2, 9]
    assert [kind for _, kind in uploaded] == ['images', 'videos', 'audios'] * 2 + ['images']


def test_kook_empty_message_does_not_send(kook_http):
    '''没有任何消息段时不产生空请求。'''

    event = make_event(make_bot(sdk='kaiheila_link', platform='kaiheila'))
    OlivOS.kaiheilaSDK.event_action.send_msg(
        event, 7, OlivOS.messageAPI.Message_templet('olivos_para', []))
    assert kook_http.calls == []


def test_kook_create_message_returns_chat_metadata(kook_http):
    '''create_message 在请求后返回统一的聊天类型、目标和内容字段。'''

    event = make_event(make_bot(sdk='kaiheila_link', platform='kaiheila'))
    result = OlivOS.kaiheilaSDK.event_action.create_message(event, 7, 2, 'https://image', True)
    assert result['active'] is True
    assert result['data'] == {
        'chat_type': 'private', 'chat_id': '7', 'content_type': 2,
        'content': 'https://image',
    }
    assert kook_http.calls[0].url.endswith('/direct-message/create')


@pytest.fixture
def xhh_http(monkeypatch):
    '''小黑盒网络替身，并固定房间管理员角色查询避免额外请求。'''

    recorder = RequestRecorder(FakeHTTPResponse(xhh_ok({})))
    monkeypatch.setattr(OlivOS.xiaoheiheSDK.req, 'request', recorder)
    monkeypatch.setattr(OlivOS.xiaoheiheSDK, 'get_room_admin_role_id', lambda *args: [])
    return recorder


def test_xiaoheihe_post_uses_token_header_and_common_query(xhh_http):
    '''小黑盒 POST 携带 Token 头和固定客户端查询参数，过滤 None 字段。'''

    bot = OlivOS.xiaoheiheSDK.get_SDK_bot_info_from_Event(
        make_event(make_bot(sdk='xiaoheihe_link', platform='xiaoheihe', access_token='xhh-token')))
    action = OlivOS.xiaoheiheSDK.API.sendChannelMessage(bot)
    action.data.room_id = '9'
    action.data.channel_id = '7'
    action.data.msg = 'hello'
    action.do_api('POST')
    call = xhh_http.calls[0]
    assert call.headers['Token'] == 'xhh-token'
    assert query_params(call)['client_type'] == ['heybox_chat']
    assert json_body(call) == {'room_id': '9', 'channel_id': '7', 'msg': 'hello', 'reply_id': ''}


def test_xiaoheihe_get_uses_query_and_handles_exception(monkeypatch):
    '''GET 查询保留查询参数；网络异常返回 None。'''

    recorder = RequestRecorder(FakeHTTPResponse(xhh_ok({'ok': True})))
    monkeypatch.setattr(OlivOS.xiaoheiheSDK.req, 'request', recorder)
    bot = OlivOS.xiaoheiheSDK.get_SDK_bot_info_from_Event(
        make_event(make_bot(sdk='xiaoheihe_link', platform='xiaoheihe')))
    action = OlivOS.xiaoheiheSDK.API.getJoinedRoomList(bot)
    assert action.do_api('GET') == recorder.response.text
    assert recorder.calls[0].method == 'GET'
    assert query_params(recorder.calls[0])['x_app'] == ['heybox_chat']
    monkeypatch.setattr(
        OlivOS.xiaoheiheSDK.req,
        'request',
        RequestRecorder(error=requests.Timeout('offline')),
    )
    assert OlivOS.xiaoheiheSDK.API.getJoinedRoomList(bot).do_api('GET') is None


def test_xiaoheihe_send_msg_builds_text_at_and_image_modules(xhh_http, monkeypatch):
    '''发送卡片必须把文本、提及和上传后的图片组装进模块数组。'''

    monkeypatch.setattr(
        OlivOS.xiaoheiheSDK.event_action,
        'setResourceUploadFast',
        lambda target_event, url, type_path: 'https://uploaded',
    )
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('hello'),
        OlivOS.messageAPI.PARA.at('42'),
        OlivOS.messageAPI.PARA.image('image.png'),
    ])
    event = make_event(make_bot(sdk='xiaoheihe_link', platform='xiaoheihe'))
    OlivOS.xiaoheiheSDK.event_action.send_msg(event, 7, 9, message, reply_id='8')
    body = json_body(xhh_http.calls[0])
    assert body['channel_id'] == '7' and body['room_id'] == '9' and body['reply_id'] == '8'
    card = json.loads(body['msg'])['data'][0]
    assert card['modules'][0]['paragraph'][0]['text'] == 'hello@{id:42}'
    assert card['modules'][1]['urls'][0]['url'] == 'https://uploaded'


def test_xiaoheihe_send_msg_empty_message_skips_request(xhh_http):
    '''空消息不发送空卡片。'''

    event = make_event(make_bot(sdk='xiaoheihe_link', platform='xiaoheihe'))
    OlivOS.xiaoheiheSDK.event_action.send_msg(
        event, 7, 9, OlivOS.messageAPI.Message_templet('olivos_para', []))
    assert xhh_http.calls == []


def test_xiaoheihe_management_actions_map_success_payload(xhh_http):
    '''房间管理动作在成功回包时统一返回 active=True。'''

    event = make_event(make_bot(sdk='xiaoheihe_link', platform='xiaoheihe'))
    actions = OlivOS.xiaoheiheSDK.event_action
    results = [
        actions.set_group_card(event, 7, 42, 'card'),
        actions.set_group_leave(event, 7),
        actions.set_group_kick(event, 7, 42),
        actions.set_group_ban(event, 7, 42, 60),
    ]
    assert all(result['active'] for result in results)
    assert json_body(xhh_http.calls[2])['to_user_id'] == '42'
    assert json_body(xhh_http.calls[3])['duration'] == 60


def test_xiaoheihe_queries_map_rooms_members_and_roles(xhh_http):
    '''房间、成员和角色查询必须映射各自的嵌套响应结构。'''

    xhh_http.response = FakeHTTPResponse(xhh_ok({
        'rooms': {'rooms': [{'room_id': '7', 'room_name': 'room', 'room_avatar': 'avatar'}]},
        'room_info': {'user_info': [{'user_id': '42', 'username': 'tester',
                                     'room_nickname': 'card', 'is_master': True}]},
        'roles': [{'id': '1', 'name': 'admin', 'color': 1, 'position': 2,
                   'permissions': '3', 'type': 1, 'hoist': 1, 'mentionable': 1}],
    }))
    event = make_event(make_bot(sdk='xiaoheihe_link', platform='xiaoheihe'))
    actions = OlivOS.xiaoheiheSDK.event_action
    rooms = actions.get_group_list(event)
    members = actions.get_group_member_list(event, 7)
    roles = actions.get_group_role_list(event, 7)
    assert rooms['active'] and rooms['data'][0]['name'] == 'room'
    assert members['active'] and members['data'][0]['role'] == 'owner'
    assert roles['active'] and roles['data'][0]['name'] == 'admin'


def test_xiaoheihe_member_retry_recovers_on_second_round(xhh_http, monkeypatch):
    '''首轮失败后按 offset 重试成功，且不把重试细节暴露给插件。'''

    monkeypatch.setattr(OlivOS.xiaoheiheSDK.time, 'sleep', lambda seconds: None)
    xhh_http.responses = [
        FakeHTTPResponse(xhh_failed()),
        FakeHTTPResponse(xhh_failed()),
        FakeHTTPResponse(xhh_ok({'room_info': {'user_info': [{'user_id': '42', 'username': 'tester'}]}})),
    ]
    event = make_event(make_bot(sdk='xiaoheihe_link', platform='xiaoheihe'))
    result = OlivOS.xiaoheiheSDK.event_action.get_group_member_list(event, 7)
    assert result['active'] is True
    assert len(xhh_http.calls) == 3


@pytest.mark.parametrize('response', [xhh_failed(), 'not json', '{}'])
def test_xiaoheihe_failed_response_keeps_queries_inactive(monkeypatch, response):
    '''业务错误、非 JSON 和空对象不得被解释成成功。'''

    monkeypatch.setattr(OlivOS.xiaoheiheSDK.req, 'request', RequestRecorder(FakeHTTPResponse(response)))
    event = make_event(make_bot(sdk='xiaoheihe_link', platform='xiaoheihe'))
    assert OlivOS.xiaoheiheSDK.event_action.get_group_list(event)['active'] is False


def test_milky_post_event_builds_control_packet():
    '''Milky 出站控制包必须寻址 milky_auto，并保留动作和参数。'''

    control_queue = queue.Queue()
    OlivOS.milkySDK.send_post_event('bot-hash', {'action': 'send', 'params': {}}, control_queue)
    packet = control_queue.get_nowait()
    assert packet.key['target'] == {'type': 'milky_auto', 'hash': 'bot-hash'}
    assert packet.key['data']['data'] == {'action': 'send', 'params': {}}


def test_milky_api_template_call_posts_action_and_waits(monkeypatch):
    '''API_template.call 负责生成 post_id、投递控制包并等待对应回包。'''

    sent = []
    monkeypatch.setattr(
        OlivOS.milkySDK,
        'send_post_event',
        lambda hash, data, control_queue: sent.append((hash, data, control_queue)),
    )
    monkeypatch.setattr(OlivOS.milkySDK, 'wait_for_res', lambda post_id: {'status': 'ok', 'post_id': post_id})
    action = OlivOS.milkySDK.API.send_private_message(user_id=42, message=[])
    result = action.call('bot-hash', queue.Queue())
    assert result['status'] == 'ok'
    assert sent[0][0] == 'bot-hash'
    assert sent[0][1]['action'] == 'send_private_message'
    assert sent[0][1]['params'] == {'user_id': 42, 'message': []}
    assert sent[0][1]['post_id'] == result['post_id']


def test_milky_api_template_exception_returns_none(monkeypatch):
    '''控制包投递异常时 call 返回 None，不向插件抛错。'''

    monkeypatch.setattr(OlivOS.milkySDK, 'ready_for_res', Mock(side_effect=RuntimeError('closed')))
    assert OlivOS.milkySDK.API.get_login_info().call('bot-hash', queue.Queue()) is None


def test_milky_response_register_success_timeout_and_missing():
    '''响应锁在成功时返回值并清理；超时/未注册时返回 None。'''

    OlivOS.milkySDK.ready_for_res('ready')
    OlivOS.milkySDK.set_for_res('ready', {'ok': True})
    assert OlivOS.milkySDK.wait_for_res('ready', timeout=0.01) == {'ok': True}
    assert 'ready' not in OlivOS.milkySDK.gResReg and 'ready' not in OlivOS.milkySDK.gEveReg
    OlivOS.milkySDK.ready_for_res('timeout')
    assert OlivOS.milkySDK.wait_for_res('timeout', timeout=0.01) is None
    assert OlivOS.milkySDK.wait_for_res('missing', timeout=0.01) is None


def test_milky_event_actions_route_to_named_api_classes(monkeypatch):
    '''事件动作必须映射到 Milky 公开动作类，并传递解析后的参数。'''

    captured = []

    def fake_call(self, bot_hash, control_queue):
        captured.append(self)
        return None

    monkeypatch.setattr(OlivOS.milkySDK.API_template, 'call', fake_call)
    event = make_event(make_bot(model='milky_default'))
    actions = OlivOS.milkySDK.event_action
    actions.send_private_msg(event, 42, [{'type': 'text', 'data': {'text': 'hello'}}])
    actions.send_group_msg(event, 7, [{'type': 'text', 'data': {'text': 'hello'}}])
    actions.send_like(event, 42, 3)
    actions.set_group_kick(event, 7, 42, True)
    actions.set_group_ban(event, 7, 42, 60)
    actions.set_group_whole_ban(event, 7, True)
    actions.set_group_admin(event, 7, 42, True)
    actions.set_group_card(event, 7, 42, 'card')
    actions.set_group_name(event, 7, 'name')
    actions.set_group_leave(event, 7, True)
    actions.set_group_special_title(event, 7, 42, 'title', 60)
    actions.set_friend_add_request(event, 'False|42', True, 'remark')
    actions.set_group_add_request(event, 'add|7|False|8', 'add', True, 'reason')
    actions.send_group_forward_msg(event, 7, [])
    actions.send_private_forward_msg(event, 42, [])
    actions.set_essence_msg(event, 'group|7|8')
    actions.delete_essence_msg(event, 'group|7|8')
    actions.set_msg_emoji_like(event, 'group|7|8', 1, True, group_id=7)
    actions.group_poke(event, 7, 42)
    actions.friend_poke(event, 42)
    actions.send_group_sign(event, 7)
    actions.send_group_notice(event, 7, 'notice', 'image')
    actions.upload_group_file(event, 7, 'file.txt', 'name', '/folder')
    actions.delete_group_file(event, 7, 'file-id')
    actions.create_group_file_folder(event, 7, 'folder', '/')
    actions.delete_group_folder(event, 7, 'folder-id')
    actions.upload_private_file(event, 42, 'file.txt', 'name')
    actions.rename_group_file_folder(event, 7, 'folder-id', 'new-name')
    actions.rename_group_file(event, 7, 'file-id', '/', 'new-name')
    actions.set_group_file_forever(event, 7, 'file-id')
    actions.set_doubt_friends_add_request(event, 'False|42', True)
    assert [item.__class__.__name__ for item in captured] == [
        'send_private_message', 'send_group_message', 'send_profile_like',
        'kick_group_member', 'set_group_member_mute', 'set_group_whole_mute',
        'set_group_member_admin', 'set_group_member_card', 'set_group_name',
        'quit_group', 'set_group_member_special_title', 'accept_friend_request',
        'accept_group_request', 'send_group_message', 'send_private_message',
        'set_group_essence_message', 'set_group_essence_message',
        'send_group_message_reaction', 'send_group_nudge', 'send_friend_nudge',
        'send_group_announcement', 'upload_group_file',
        'delete_group_file', 'create_group_folder', 'delete_group_folder',
        'upload_private_file', 'rename_group_folder', 'rename_group_file',
        'accept_friend_request',
    ]
