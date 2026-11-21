'''覆盖非纯 HTTP 适配器 API 的扩展离线契约。'''

import json
import queue
from types import SimpleNamespace

import pytest

import OlivOS
from adapter_api_support import FakeHTTPResponse, RequestRecorder, json_body


def _bot(model, platform='qq', sdk='onebot'):
    '''构造仅含插件可见字段的账号，不读取真实凭据。'''

    return OlivOS.API.bot_info_T(
        id=10001,
        host='https://fixture.invalid',
        port=443,
        access_token='fixture-token',
        platform_sdk=sdk,
        platform_platform=platform,
        platform_model=model,
    )


def _event(bot, control_queue=None, **data):
    '''只构造 adapter event_action 方法会消费的 Event 字段。'''

    return SimpleNamespace(
        bot_info=bot,
        plugin_info={'control_queue': control_queue if control_queue is not None else queue.Queue()},
        data=SimpleNamespace(**data),
    )


def _packet_json(packet):
    '''解码控制包中携带的 OneBot V12 JSON 请求体。'''

    return json.loads(packet.key['data']['data'])


@pytest.fixture
def v12_queue(monkeypatch):
    '''在每个用例前重置 V12 请求登记表，避免跨用例串状态。'''

    module = OlivOS.onebotV12SDK
    monkeypatch.setattr(module, 'gResReg', {})
    monkeypatch.setattr(module, 'gTmpReg', {})
    monkeypatch.setattr(module, 'gUsrReg', {})
    return queue.Queue()


def test_onebot12_control_packet_omits_none_params_and_keeps_echo(v12_queue):
    '''OneBot V12 控制包不得序列化值为 None 的参数，并应保留 echo。'''

    bot = _bot('onebotV12')
    bot.hash = 'fixture-hash'
    action = OlivOS.onebotV12SDK.api.send_message()
    action.params.detail_type = 'private'
    action.params.user_id = '42'
    action.params.group_id = None
    action.params.message = [{'type': 'text', 'data': {'text': 'hello'}}]
    action.do_api(bot.hash, v12_queue)
    packet = v12_queue.get_nowait()
    body = _packet_json(packet)
    assert packet.action == 'send'
    assert packet.key['target'] == {'type': 'onebotV12_link', 'hash': 'fixture-hash'}
    assert body['action'] == 'send_message'
    assert body['params'] == {
        'detail_type': 'private',
        'user_id': '42',
        'message': [{'type': 'text', 'data': {'text': 'hello'}}],
    }
    assert body['echo'] == action.echo


def test_onebot12_send_actions_route_private_group_and_channel(v12_queue):
    '''私聊、群聊和频道发送应分别使用 V12 对应的参数结构。'''

    bot = _bot('onebotV12')
    bot.hash = 'fixture-hash'
    event = _event(bot, v12_queue)
    actions = OlivOS.onebotV12SDK.event_action
    actions.send_private_msg(event, 42, 'private')
    actions.send_group_msg(event, 7, 'group')
    actions.send_host_msg(event, 9, 8, 'channel')
    bodies = [_packet_json(v12_queue.get_nowait()) for _ in range(3)]
    assert bodies[0]['params'] == {'detail_type': 'private', 'user_id': '42', 'message': 'private'}
    assert bodies[1]['params'] == {'detail_type': 'group', 'group_id': '7', 'message': 'group'}
    assert bodies[2]['params'] == {
        'detail_type': 'channel', 'channel_id': '9', 'guild_id': '8', 'message': 'channel'}


@pytest.mark.parametrize('duration, expected_action, expected_params', [
    # duration=0 表示解除禁言，必须走 unban 接口且不携带时长。
    (0, 'unban_group_member', {'group_id': '7', 'user_id': '42'}),
    # 正数时长表示禁言，必须走 ban 接口并保留字符串时长。
    (60, 'ban_group_member', {'group_id': '7', 'user_id': '42', 'duration': '60'}),
])
def test_onebot12_ban_duration_selects_ban_or_unban(
        v12_queue, duration, expected_action, expected_params):
    '''时长为 0 应调用解禁接口，正数时长才调用禁言接口。'''

    bot = _bot('onebotV12')
    bot.hash = 'fixture-hash'
    OlivOS.onebotV12SDK.event_action.set_group_ban(_event(bot, v12_queue), 7, 42, duration)
    body = _packet_json(v12_queue.get_nowait())
    assert body['action'] == expected_action
    assert body['params'] == expected_params


@pytest.mark.parametrize('enable, expected_action', [
    # 授予管理员必须走 set_group_admin。
    (True, 'set_group_admin'),
    # 撤销管理员必须走 unset_group_admin。
    (False, 'unset_group_admin'),
])
def test_onebot12_admin_toggle_uses_matching_action(v12_queue, enable, expected_action):
    '''管理员开关应分别调用 set/unset 动作，而不是发送布尔参数。'''

    bot = _bot('onebotV12')
    bot.hash = 'fixture-hash'
    OlivOS.onebotV12SDK.event_action.set_group_admin(_event(bot, v12_queue), 7, 42, enable)
    body = _packet_json(v12_queue.get_nowait())
    assert body['action'] == expected_action
    assert body['params'] == {'group_id': '7', 'user_id': '42'}


def test_onebot12_request_state_registers_success_and_ignores_unknown_echo(v12_queue):
    '''响应登记只应完成当前正在等待的 echo，未知 echo 必须忽略。'''

    module = OlivOS.onebotV12SDK
    module.waitForResReady('known')
    module.waitForResSet('unknown', {'retcode': 0, 'data': {}})
    module.waitForResSet('known', {'retcode': 0, 'data': {'id': '42'}})
    assert module.gResReg['known'] == {'retcode': 0, 'data': {'id': '42'}}
    assert 'unknown' not in module.gResReg


def test_onebot12_request_registry_reads_and_writes_flags(v12_queue):
    '''临时请求表和按 bot 请求表应相互隔离，读写标记互不污染。'''

    module = OlivOS.onebotV12SDK
    module.setReg('flag', 'value')
    module.setUserReg('bot-hash', 'group', 'flag', 'group-id')
    assert module.getReg('flag') == 'value'
    assert module.getUserReg('bot-hash', 'group', 'flag') == 'group-id'
    assert module.getUserReg('other-hash', 'group', 'flag') is None
    assert module.getReg('missing') is None


@pytest.mark.parametrize('raw, expected', [
    # 标准成功回包只复制 data，调用方不能修改原始响应。
    ({'retcode': 0, 'data': {'id': '42'}}, {'id': '42'}),
    # 列表 data 同样允许作为查询结果返回。
    ({'retcode': 0, 'data': [{'id': '42'}]}, [{'id': '42'}]),
    # 非零 retcode 视为失败。
    ({'retcode': 1, 'data': {'id': '42'}}, None),
    # 缺少整数 retcode 视为畸形回包。
    ({'retcode': '0', 'data': {'id': '42'}}, None),
    # 缺少 data 时没有可映射的业务结果。
    ({'retcode': 0}, None),
    # 非字典输入必须安全返回 None。
    ('not-a-dict', None),
])
def test_onebot12_init_api_json_accepts_only_success_shape(raw, expected):
    '''共享响应解码器应拒绝畸形或字段不完整的成功回包。'''

    assert OlivOS.onebotV12SDK.init_api_json(raw) == expected


def test_onebot12_query_actions_map_success_payloads(monkeypatch, v12_queue):
    '''只读 V12 动作应把用户、群和成员结果映射为统一结构。'''

    module = OlivOS.onebotV12SDK
    bot = _bot('onebotV12')
    bot.hash = 'fixture-hash'
    event = _event(bot, v12_queue)
    responses = [
        {'retcode': 0, 'data': {'user_id': '10001', 'user_name': 'bot'}},
        {'retcode': 0, 'data': {'user_id': '42', 'user_name': 'stranger'}},
        {'retcode': 0, 'data': [{'user_id': '42', 'user_name': 'friend'}]},
        {'retcode': 0, 'data': {'group_id': '7', 'group_name': 'group'}},
        {'retcode': 0, 'data': [{'group_id': '7', 'group_name': 'group'}]},
        {'retcode': 0, 'data': {'group_id': '7', 'user_id': '42', 'user_name': 'member'}},
        {'retcode': 0, 'data': [{'group_id': '7', 'user_id': '42', 'user_name': 'member'}]},
    ]
    monkeypatch.setattr(module, 'waitForResReady', lambda echo: True)
    monkeypatch.setattr(module, 'waitForRes', lambda echo: responses.pop(0))
    login = module.event_action.get_login_info(event)
    stranger = module.event_action.get_stranger_info(event, 42)
    friends = module.event_action.get_friend_list(event)
    group = module.event_action.get_group_info(event, 7)
    groups = module.event_action.get_group_list(event)
    member = module.event_action.get_group_member_info(event, 7, 42)
    members = module.event_action.get_group_member_list(event, 7)
    assert login['active'] and login['data'] == {'name': 'bot', 'id': '10001'}
    assert stranger['active'] and stranger['data'] == {'name': 'stranger', 'id': '42'}
    assert friends['active'] and friends['data'] == [{'name': 'friend', 'id': '42'}]
    assert group['active'] and group['data']['name'] == 'group' and group['data']['id'] == '7'
    assert groups['active'] and groups['data'][0]['name'] == 'group'
    assert member['active'] and member['data']['name'] == 'member' and member['data']['group_id'] == '7'
    assert members['active'] and members['data'][0]['name'] == 'member'


@pytest.mark.parametrize('response', [
    # 非零 retcode 不得把查询标记为成功。
    {'retcode': 1200, 'data': {'user_id': '42'}},
    # 畸形 JSON 文本由外层解析器拒绝。
    'not-json',
    # data 类型与动作预期不符时保持 inactive。
    {'retcode': 0, 'data': 'unexpected'},
])
def test_onebot12_query_failure_stays_inactive(monkeypatch, v12_queue, response):
    '''查询接口收到异常回包时应保持 inactive，不得抛错。'''

    module = OlivOS.onebotV12SDK
    bot = _bot('onebotV12')
    bot.hash = 'fixture-hash'
    event = _event(bot, v12_queue)
    monkeypatch.setattr(module, 'waitForResReady', lambda echo: True)
    monkeypatch.setattr(module, 'waitForRes', lambda echo: response)
    assert module.event_action.get_stranger_info(event, 42)['active'] is False
    assert module.event_action.get_friend_list(event)['active'] is False
    assert module.event_action.get_group_info(event, 7)['active'] is False
    assert module.event_action.get_group_member_info(event, 7, 42)['active'] is False


def test_onebot12_add_request_actions_use_registered_identifiers(v12_queue):
    '''好友和群请求动作应读取事件转换阶段登记的标识。'''

    module = OlivOS.onebotV12SDK
    bot = _bot('onebotV12')
    bot.hash = 'fixture-hash'
    event = _event(bot, v12_queue)
    module.setReg('1', '42')
    module.setReg('1-user', '43')
    module.event_action.set_friend_add_request(event, '1', True, 'remark')
    module.event_action.set_group_add_request(event, '1', 'add', True, 'reason')
    module.event_action.set_group_add_request(event, '1', 'invite', False, '')
    bodies = [_packet_json(v12_queue.get_nowait()) for _ in range(3)]
    assert bodies[0]['action'] == 'set_new_friend'
    assert bodies[0]['params'] == {'user_id': '42', 'request_id': 1, 'accept': True}
    assert bodies[1]['action'] == 'set_join_group'
    assert bodies[1]['params'] == {
        'request_id': 1, 'group_id': '42', 'user_id': '43', 'accept': True, 'message': 'reason'}
    assert bodies[2]['action'] == 'set_group_invited'
    assert bodies[2]['params'] == {'request_id': 1, 'group_id': '42', 'accept': False}


def test_onebot12_actions_without_bot_info_are_noops(v12_queue):
    '''缺少 bot_info 的 webhook 风格动作应直接 no-op，不生成畸形控制包。'''

    event = _event(None, v12_queue)
    OlivOS.onebotV12SDK.event_action.send_group_msg(event, 7, 'hello')
    OlivOS.onebotV12SDK.event_action.delete_msg(event, 8)
    assert v12_queue.empty()


@pytest.fixture
def telegram_http(monkeypatch):
    '''替换 Telegram HTTP 调用，同时保留 URL 与请求体构造逻辑。'''

    recorder = RequestRecorder(FakeHTTPResponse({'ok': True, 'result': {}}))
    monkeypatch.setattr(OlivOS.telegramSDK.req, 'request', recorder)
    return recorder


def test_telegram_sender_rejects_incomplete_configuration(telegram_http):
    '''Telegram 发送器缺少 host、port、载荷或方法时不得发起 HTTP。'''

    sender = OlivOS.telegramSDK.send_telegram_post_json_T()
    sender.bot_info = OlivOS.telegramSDK.bot_info_T(id=1)
    sender.obj = SimpleNamespace(value='hello')
    sender.node_ext = 'sendMessage'
    assert sender.send_telegram_post_json() is None
    assert telegram_http.calls == []


def test_telegram_text_and_image_preserve_message_order(telegram_http):
    '''图片前后文本应按原顺序拆成独立的 Telegram 请求。'''

    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('before'),
        OlivOS.messageAPI.PARA.image('fixture.png'),
        OlivOS.messageAPI.PARA.text('after'),
    ])
    event = _event(_bot('default', platform='telegram', sdk='telegram_poll'))
    OlivOS.telegramSDK.event_action.send_group_msg(event, 7, message)
    assert [call.method for call in telegram_http.calls] == ['POST', 'POST', 'POST']
    assert [call.url.rsplit('/', 1)[-1] for call in telegram_http.calls] == [
        'sendMessage', 'sendPhoto', 'sendMessage']
    assert json_body(telegram_http.calls[0])['text'] == 'before'
    assert json_body(telegram_http.calls[1])['photo'] == 'fixture.png'
    assert json_body(telegram_http.calls[2])['text'] == 'after'


def test_telegram_private_and_group_sends_share_chat_payload(telegram_http):
    '''Telegram 私聊与群聊发送只有目标 chat_id 不同。'''

    event = _event(_bot('default', platform='telegram', sdk='telegram_poll'))
    message = OlivOS.messageAPI.Message_templet(
        'olivos_para', [OlivOS.messageAPI.PARA.text('hello')])
    OlivOS.telegramSDK.event_action.send_private_msg(event, 42, message)
    OlivOS.telegramSDK.event_action.send_group_msg(event, 7, message)
    assert json_body(telegram_http.calls[0])['chat_id'] == '42'
    assert json_body(telegram_http.calls[1])['chat_id'] == '7'


def test_telegram_leave_chat_posts_only_chat_id(telegram_http):
    '''离开 Telegram 会话应调用 leaveChat 并只携带目标 id。'''

    event = _event(_bot('default', platform='telegram', sdk='telegram_poll'))
    OlivOS.telegramSDK.event_action.set_chat_leave(event, 7)
    assert telegram_http.calls[0].url.endswith('/leaveChat')
    assert json_body(telegram_http.calls[0]) == {'chat_id': '7'}


def test_telegram_query_mapping_covers_login_group_and_member(monkeypatch):
    '''机器人、群和成员查询应正确映射 Telegram result 对象。'''

    monkeypatch.setattr(
        OlivOS.telegramSDK.req,
        'request',
        RequestRecorder(responses=[
            FakeHTTPResponse({'ok': True, 'result': {'id': 10001, 'first_name': 'bot'}}),
            FakeHTTPResponse({'ok': True, 'result': {
                'title': 'group', 'description': 'memo', 'type': 'supergroup'}}),
            FakeHTTPResponse({'ok': True, 'result': 321}),
            FakeHTTPResponse({'ok': True, 'result': {
                'user': {'id': 42, 'first_name': 'member'}, 'status': {'role': 'administrator'}}}),
        ]),
    )
    event = _event(_bot('default', platform='telegram', sdk='telegram_poll'))
    login = OlivOS.telegramSDK.event_action.get_login_info(event)
    group = OlivOS.telegramSDK.event_action.get_group_info(event, 7)
    member = OlivOS.telegramSDK.event_action.get_group_member_info(event, 7, 42)
    assert login['active'] and login['data'] == {'name': 'bot', 'id': '10001'}
    assert group['active'] and group['data']['name'] == 'group'
    assert group['data']['memo'] == 'memo' and group['data']['member_count'] == 321
    assert group['data']['max_member_count'] == 200000
    assert member['active'] and member['data']['name'] == 'member'
    assert member['data']['role'] == 'admin' and member['data']['group_id'] == '7'


@pytest.mark.parametrize('payload, expected', [
    # Telegram 只有 ok=true 才暴露 result 字典。
    ({'ok': True, 'result': {'id': 1}}, {'id': 1}),
    # result 列表用于批量查询。
    ({'ok': True, 'result': [{'id': 1}]}, [{'id': 1}]),
    # 标量 result 也按原样返回，交给调用方按类型校验。
    ({'ok': True, 'result': 1}, 1),
    # ok=false 表示平台拒绝。
    ({'ok': False, 'result': {'id': 1}}, None),
    # 非布尔 ok 不构成可信成功回包。
    ({'ok': 'true', 'result': {'id': 1}}, None),
    # 非 JSON 文本必须安全返回 None。
    ('not-json', None),
])
def test_telegram_init_api_json_accepts_only_ok_envelope(payload, expected):
    '''Telegram 响应解码必须拒绝失败或畸形 envelope。'''

    raw = payload if isinstance(payload, str) else json.dumps(payload)
    assert OlivOS.telegramSDK.init_api_json(raw) == expected


def test_telegram_failed_query_stays_inactive(telegram_http):
    '''getMe 失败时登录查询应保持 inactive。'''

    telegram_http.response = FakeHTTPResponse({'ok': False, 'description': 'denied'})
    event = _event(_bot('default', platform='telegram', sdk='telegram_poll'))
    result = OlivOS.telegramSDK.event_action.get_login_info(event)
    assert result['active'] is False


@pytest.fixture
def discord_http(monkeypatch):
    '''替换 Discord HTTP 调用，并在每个用例前重置私聊频道缓存。'''

    recorder = RequestRecorder(FakeHTTPResponse({'id': '99', 'username': 'bot'}))
    monkeypatch.setattr(OlivOS.discordSDK.req, 'request', recorder)
    monkeypatch.setattr(OlivOS.discordSDK, 'sdkDMInfo', {})
    return recorder


def test_discord_api_post_filters_none_and_uses_bot_authorization(discord_http):
    '''Discord JSON 请求体应过滤 None 字段并使用 Bot 授权头。'''

    bot = OlivOS.discordSDK.bot_info_T(id=10001, access_token='fixture-token')
    api = OlivOS.discordSDK.API.sendMessage(bot)
    api.metadata.channel_id = '7'
    api.data.content = 'hello'
    assert api.do_api() == json.dumps({'id': '99', 'username': 'bot'})
    call = discord_http.calls[0]
    assert call.method == 'POST'
    assert call.url.endswith('/channels/7/messages')
    assert call.headers['Authorization'] == 'Bot fixture-token'
    assert json_body(call) == {'content': 'hello', 'embeds': [], 'attachments': []}


def test_discord_api_get_me_uses_get_without_body(discord_http):
    '''Discord 只读接口应使用 GET 且不构造无意义 JSON 请求体。'''

    bot = OlivOS.discordSDK.bot_info_T(id=10001, access_token='fixture-token')
    api = OlivOS.discordSDK.API.getMe(bot)
    api.do_api('GET')
    call = discord_http.calls[0]
    assert call.method == 'GET' and call.url.endswith('/users/@me')
    assert call.data is None


def test_discord_send_text_escapes_markdown_metacharacters(discord_http):
    '''Discord 文本发送应转义会改变 Markdown 结构的元字符。'''

    event = _event(_bot('default', platform='discord', sdk='discord_link'))
    message = OlivOS.messageAPI.Message_templet(
        'olivos_para', [OlivOS.messageAPI.PARA.text('a*b[c](d)')])
    OlivOS.discordSDK.event_action.send_msg(event, 7, message)
    body = json_body(discord_http.calls[0])
    assert body['embeds'] == [{'description': 'a\\*b\\[c\\]\\(d\\)'}]


def test_discord_send_image_uses_multipart_and_attachment_reference(discord_http):
    '''Base64 图片应以 multipart 上传，并生成缩略图附件引用。'''

    event = _event(_bot('default', platform='discord', sdk='discord_link'))
    message = OlivOS.messageAPI.Message_templet(
        'olivos_para', [OlivOS.messageAPI.PARA.image('base64://aGVsbG8=')])
    OlivOS.discordSDK.event_action.send_msg(event, 7, message)
    call = discord_http.calls[0]
    assert call.headers['Content-Type'].startswith('multipart/form-data')
    assert b'image_0.png' in call.data
    assert b'hello' in call.data


def test_discord_direct_message_creates_channel_then_reuses_cache(discord_http):
    '''首次私聊应创建 DM 频道，后续发送应复用缓存频道。'''

    discord_http.responses = [
        FakeHTTPResponse({'id': '99'}),
        FakeHTTPResponse({'id': 'message'}),
        FakeHTTPResponse({'id': 'message'}),
    ]
    event = _event(_bot('default', platform='discord', sdk='discord_link'))
    message = OlivOS.messageAPI.Message_templet(
        'olivos_para', [OlivOS.messageAPI.PARA.text('hello')])
    OlivOS.discordSDK.event_action.send_msg(event, 42, message, flag_direct=True)
    OlivOS.discordSDK.event_action.send_msg(event, 42, message, flag_direct=True)
    assert [call.url.rsplit('/', 1)[-1] for call in discord_http.calls] == [
        'channels', 'messages', 'messages']
    assert json_body(discord_http.calls[0]) == {'recipient_id': 42}
    assert '/channels/99/messages' in discord_http.calls[1].url
    assert '/channels/99/messages' in discord_http.calls[2].url


def test_discord_login_query_maps_username_and_failure(discord_http):
    '''Discord 登录查询应映射成功 JSON，并保持失败结果 inactive。'''

    event = _event(_bot('default', platform='discord', sdk='discord_link'))
    result = OlivOS.discordSDK.event_action.get_login_info(event)
    assert result['active'] and result['data'] == {'name': 'bot', 'id': '99'}
    discord_http.response = FakeHTTPResponse('not-json')
    result = OlivOS.discordSDK.event_action.get_login_info(event)
    assert result['active'] is False


@pytest.mark.parametrize('payload, expected', [
    # Discord 成功回包是任意 JSON 对象。
    ({'id': '99'}, {'id': '99'}),
    # 顶层数组不足以构成 Discord 对象回包，应拒绝。
    ([{'id': '99'}], None),
    # 非 JSON 文本必须安全返回 None。
    ('not-json', None),
])
def test_discord_init_api_json_accepts_only_objects(payload, expected):
    '''Discord 响应解码必须要求 JSON 对象。'''

    raw = payload if isinstance(payload, str) else json.dumps(payload)
    assert OlivOS.discordSDK.init_api_json(raw) == expected


def test_discord_request_exception_is_nonfatal(discord_http):
    '''网络异常应返回 None，不能抛给插件层。'''

    discord_http.error = RuntimeError('fixture transport failure')
    bot = OlivOS.discordSDK.bot_info_T(id=10001, access_token='fixture-token')
    assert OlivOS.discordSDK.API.getMe(bot).do_api('GET') is None


@pytest.fixture
def dingtalk_bot(monkeypatch):
    '''构造带缓存的钉钉 SDK 账号，确保测试不会请求真实令牌。'''

    import time

    module = OlivOS.dingtalkSDK
    plugin_bot = _bot('default', platform='dingtalk', sdk='dingtalk_link')
    plugin_bot.extends = {'app_key': 'fixture-key', 'app_secret': 'fixture-secret'}
    monkeypatch.setattr(module, 'sdkSubSelfInfo', {})
    sdk_bot = module.get_SDK_bot_info_from_Plugin_bot_info(plugin_bot)
    sdk_bot._access_token = 'fixture-token'
    sdk_bot._expire_time = time.time() + 3600
    return module, plugin_bot, sdk_bot


@pytest.fixture
def dingtalk_http(monkeypatch):
    '''替换钉钉 HTTP 调用，同时保留请求构造逻辑。'''

    recorder = RequestRecorder(FakeHTTPResponse({'errcode': 0}))
    monkeypatch.setattr(OlivOS.dingtalkSDK.req, 'request', recorder)
    return recorder


def test_dingtalk_access_token_is_cached_until_expiry(monkeypatch, dingtalk_http):
    '''有效钉钉令牌在过期前应复用，不能重复请求 OAuth。'''

    module = OlivOS.dingtalkSDK
    bot = module.bot_info_T(id=10001, AppKey='key', AppSecret='secret')
    dingtalk_http.responses = [FakeHTTPResponse({'accessToken': 'fresh', 'expireIn': 7200})]
    assert bot.access_token == 'fresh'
    assert bot.access_token == 'fresh'
    assert len(dingtalk_http.calls) == 1
    assert json_body(dingtalk_http.calls[0]) == {'appKey': 'key', 'appSecret': 'secret'}


def test_dingtalk_post_adds_token_header_and_parses_json(monkeypatch, dingtalk_bot, dingtalk_http):
    '''钉钉 POST 应附带访问令牌并解析 JSON 响应。'''

    _, _, bot = dingtalk_bot
    api = OlivOS.dingtalkSDK.API.getUserInfo(bot)
    api.set_data(api.data_T(userid='42'))
    assert api.do_api() == {'errcode': 0}
    call = dingtalk_http.calls[0]
    assert call.method == 'POST'
    assert call.headers['x-acs-dingtalk-access-token'] == 'fixture-token'
    assert json_body(call) == {'userid': '42', 'language': 'zh_CN'}


def test_dingtalk_get_omits_json_body(monkeypatch, dingtalk_bot, dingtalk_http):
    '''无需请求体时 GET 不应序列化空 JSON 对象。'''

    _, _, bot = dingtalk_bot
    api = OlivOS.dingtalkSDK.API.getUserInfo(bot)
    api._do_api('GET', body=api.NO_DATA)
    assert dingtalk_http.calls[0].method == 'GET'
    assert dingtalk_http.calls[0].data is None


def test_dingtalk_non_json_response_is_returned_as_text(monkeypatch, dingtalk_bot, dingtalk_http):
    '''非 JSON 的成功响应体应原样保留以便诊断。'''

    _, _, bot = dingtalk_bot
    dingtalk_http.response = FakeHTTPResponse('ok')
    api = OlivOS.dingtalkSDK.API.getUserInfo(bot)
    api.set_data(api.data_T(userid='42'))
    assert api.do_api() == 'ok'


def test_dingtalk_request_exception_is_nonfatal(monkeypatch, dingtalk_bot, dingtalk_http):
    '''传输异常应返回 None，不能逃逸给插件。'''

    _, _, bot = dingtalk_bot
    dingtalk_http.error = RuntimeError('fixture transport failure')
    api = OlivOS.dingtalkSDK.API.getUserInfo(bot)
    api.set_data(api.data_T(userid='42'))
    assert api.do_api() is None


@pytest.mark.parametrize('send_type, expected_url, expected_key', [
    # 群消息使用 openConversationId 定位会话。
    ('group', '/groupMessages/send', 'openConversationId'),
    # 私聊消息使用 userIds 数组定位接收者。
    ('private', '/oToMessages/batchSend', 'userIds'),
])
def test_dingtalk_text_send_routes_group_and_private(
        dingtalk_bot, dingtalk_http, send_type, expected_url, expected_key):
    '''钉钉文本消息应按目标类型使用正确的会话字段。'''

    _, plugin_bot, _ = dingtalk_bot
    event = _event(plugin_bot)
    message = OlivOS.messageAPI.Message_templet(
        'olivos_para', [OlivOS.messageAPI.PARA.text('hello')])
    OlivOS.dingtalkSDK.event_action.send_msg(event, send_type, '7', message)
    body = json_body(dingtalk_http.calls[0])
    assert dingtalk_http.calls[0].url.endswith(expected_url)
    assert body['msgKey'] == 'sampleText'
    assert json.loads(body['msgParam']) == {'content': 'hello'}
    assert body[expected_key] == (['7'] if expected_key == 'userIds' else '7')


def test_dingtalk_image_send_uses_uploaded_media(monkeypatch, dingtalk_bot, dingtalk_http):
    '''钉钉图片发送应在卡片载荷中使用已上传媒体标识。'''

    module, plugin_bot, _ = dingtalk_bot
    monkeypatch.setattr(module, '_set_image_upload_fast', lambda target_event, url: 'media-id')
    event = _event(plugin_bot)
    message = OlivOS.messageAPI.Message_templet(
        'olivos_para', [OlivOS.messageAPI.PARA.image('fixture.png')])
    module.event_action.send_msg(event, 'group', '7', message)
    body = json_body(dingtalk_http.calls[0])
    assert body['msgKey'] == 'sampleImageMsg'
    assert json.loads(body['msgParam']) == {'photoURL': 'media-id'}


def test_dingtalk_send_group_data_defaults_robot_code(monkeypatch, dingtalk_bot, dingtalk_http):
    '''群消息缺少 robotCode 和 coolAppCode 时应回退使用 bot id。'''

    module, _, bot = dingtalk_bot
    api = module.API.sendGroupMessage(bot)
    api.set_data(api.data_T(msgKey='sampleText', msgParam={'content': 'hello'}, openConversationId='7'))
    api.do_api()
    assert json_body(dingtalk_http.calls[0])['robotCode'] == 10001


def test_dingtalk_access_token_failure_returns_none(dingtalk_http):
    '''OAuth 失败时不得把失败响应当作可用令牌缓存。'''

    module = OlivOS.dingtalkSDK
    bot = module.bot_info_T(id=10001, AppKey='key', AppSecret='secret')
    dingtalk_http.response = FakeHTTPResponse({'message': 'denied'})
    assert bot.access_token is None
    assert bot._access_token is None
