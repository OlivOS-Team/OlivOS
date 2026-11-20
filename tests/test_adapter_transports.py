'''覆盖 WebSocket、HTTP、轮询和重连循环的离线传输契约。'''
import asyncio
import json
import queue
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import websockets

import OlivOS


@pytest.fixture(autouse=True)
def _restore_flask_activity_registry():
    '''在每个用例前后隔离模块级 HTTP 活动登记表。'''

    module = OlivOS.flaskServerAPI
    servers = list(module._http_post_servers)
    retired = dict(module._retired_activity)
    yield
    module._http_post_servers[:] = servers
    module._retired_activity.clear()
    module._retired_activity.update(retired)


def _bot(server_type='websocket', host='ws://127.0.0.1', port=5700):
    '''构造带具体 post_info 的离线插件账号。'''

    bot = OlivOS.API.bot_info_T(
        id=10001,
        server_type=server_type,
        host=host,
        port=port,
        access_token='fixture-token',
        platform_sdk='onebot',
        platform_platform='qq',
        platform_model='default',
    )
    bot.extends = {'retry_interval': 0}
    return bot


def _raw_message(text='hello'):
    '''返回合法的 OneBot V11 群消息上报帧。'''

    return json.dumps({
        'time': 1750000000,
        'self_id': 10001,
        'post_type': 'message',
        'message_type': 'group',
        'sub_type': 'normal',
        'group_id': 7,
        'user_id': 42,
        'message_id': 8,
        'message': text,
        'raw_message': text,
        'font': 0,
        'sender': {'user_id': 42, 'nickname': 'tester', 'role': 'member'},
    })


class FakeWS:
    '''由确定性入站序列驱动的最小 WebSocket 对端。'''

    def __init__(self, incoming=()):
        self.incoming = list(incoming)
        self.sent = []
        self.sent_event = asyncio.Event()
        self.closed = False

    async def recv(self):
        if not self.incoming:
            raise websockets.ConnectionClosedOK(None, None)
        item = self.incoming.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item

    async def send(self, payload):
        self.sent.append(payload)
        self.sent_event.set()

    async def close(self):
        self.closed = True


class FakeSyncWS:
    '''供 websocket-client 适配器使用的同步 WebSocket 对端。'''

    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)


def test_onebot_host_rx_drops_invalid_frame_and_routes_valid_event(monkeypatch):
    '''非法帧不得进入全局队列，后续合法帧仍应正常投递。'''

    tx_queue = queue.Queue()
    server = OlivOS.onebotV11HostServerAPI.server(
        'host-test', bot_info_dict=_bot('websocket_host'), tx_queue=tx_queue, rx_queue=queue.Queue())
    captured = []
    monkeypatch.setattr(
        OlivOS.pluginAPI.shallow,
        'rx_packet',
        lambda sdk_event: captured.append(sdk_event) or 'tx-packet',
    )
    ws = FakeWS(['not-json', _raw_message()])
    asyncio.run(server.rx(ws))
    assert len(captured) == 1
    assert captured[0].active and captured[0].json['group_id'] == 7
    assert tx_queue.get_nowait() == 'tx-packet'


def test_onebot_host_tx_serializes_dict_payload_to_websocket():
    '''控制发送包应只序列化一次并写入对端 WebSocket。'''

    rx_queue = queue.Queue()
    server = OlivOS.onebotV11HostServerAPI.server(
        'host-test', bot_info_dict=_bot('websocket_host'), tx_queue=queue.Queue(), rx_queue=rx_queue)
    ws = FakeWS()
    rx_queue.put(OlivOS.API.Control.packet(
        'send', {'data': {'action': 'send', 'data': {'action': 'get_status'}}}))

    async def exercise():
        task = asyncio.create_task(server.tx(ws))
        await asyncio.wait_for(ws.sent_event.wait(), timeout=1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise())
    assert json.loads(ws.sent[0]) == {'action': 'get_status'}


def test_onebot_link_rx_and_tx_share_session_queues(monkeypatch):
    '''Link 会话应双向路由入站帧和出站控制包。'''

    tx_queue = queue.Queue()
    rx_queue = queue.Queue()
    server = OlivOS.onebotV11LinkServerAPI.server(
        'link-test', bot_info=_bot('websocket'), tx_queue=tx_queue, rx_queue=rx_queue)
    captured = []
    monkeypatch.setattr(
        OlivOS.pluginAPI.shallow,
        'rx_packet',
        lambda sdk_event: captured.append(sdk_event) or 'tx-packet',
    )
    ws = FakeWS(['not-json', _raw_message('link')])
    server.ws_conn = ws
    asyncio.run(server.rx_link())
    assert len(captured) == 1 and captured[0].json['message'] == 'link'
    assert tx_queue.get_nowait() == 'tx-packet'
    rx_queue.put(OlivOS.API.Control.packet(
        'send', {'data': {'action': 'send', 'data': {'echo': 'fixture'}}}))

    async def exercise_tx():
        task = asyncio.create_task(server.tx_link())
        await asyncio.wait_for(ws.sent_event.wait(), timeout=1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(exercise_tx())
    assert json.loads(ws.sent[0]) == {'echo': 'fixture'}


def test_onebot_link_connection_refusal_is_nonfatal(monkeypatch):
    '''首次连接被拒绝时应保持 ws_conn 为空，交由重连循环重试。'''

    server = OlivOS.onebotV11LinkServerAPI.server(
        'link-test', bot_info=_bot('websocket'), tx_queue=queue.Queue(), rx_queue=queue.Queue())

    async def refused(*args, **kwargs):
        raise ConnectionRefusedError('fixture refused')

    monkeypatch.setattr(OlivOS.onebotV11LinkServerAPI.websockets, 'connect', refused)
    asyncio.run(server._server__link_to_server())
    assert server.ws_conn is None


def test_onebot_link_run_retries_after_session_error(monkeypatch):
    '''外层 Link 循环在会话异常后应记录一次失败并继续运行直到停止。'''

    server = OlivOS.onebotV11LinkServerAPI.server(
        'link-test', bot_info=_bot('websocket'), tx_queue=queue.Queue(), rx_queue=queue.Queue())
    server.on_error = Mock()
    server.on_retry = Mock()
    calls = []

    async def lifecycle():
        calls.append('attempt')
        if len(calls) == 1:
            raise RuntimeError('fixture session failure')
        server.running_event.clear()

    monkeypatch.setattr(server, '_server__session_lifecycle', lifecycle)
    asyncio.run(asyncio.wait_for(server.run(), timeout=1))
    assert calls == ['attempt', 'attempt']
    server.on_error.assert_called_once()
    server.on_retry.assert_called_once()


def test_onebot_host_session_releases_link_after_rx_finishes(monkeypatch):
    '''反向 Host 会话任一侧结束时，应取消对端任务并扣减连接计数。'''

    server = OlivOS.onebotV11HostServerAPI.server(
        'host-test', bot_info_dict=_bot('websocket_host'), tx_queue=queue.Queue(), rx_queue=queue.Queue())
    monkeypatch.setattr(OlivOS.pluginAPI.shallow, 'rx_packet', lambda sdk_event: sdk_event.raw)
    ws = FakeWS(['not-json'])
    assert server.active_links == 0
    asyncio.run(server.session(ws))
    assert server.active_links == 0


def test_onebot_host_auth_accepts_header_and_rejects_unknown_token():
    '''Host 鉴权应接受配置令牌并拒绝错误令牌。'''

    server = OlivOS.onebotV11HostServerAPI.server(
        'host-test', bot_info_dict=_bot('websocket_host'), tx_queue=queue.Queue(), rx_queue=queue.Queue())
    server.on_unauth = Mock()
    request = SimpleNamespace(headers={'Authorization': 'Bearer ' + server.conf.token}, path='/' + server.conf.token)
    assert server.auther(None, request) is None
    rejected = server.auther(None, SimpleNamespace(headers={'Authorization': 'Bearer bad'}, path='/bad'))
    assert rejected.status_code == 401
    server.on_unauth.assert_called_once_with('bad')


def test_onebot_link_connect_falls_back_to_legacy_header_keyword(monkeypatch):
    '''旧版 websockets 仅支持 extra_headers 时，回退参数仍应连接成功。'''

    module = OlivOS.onebotV11LinkServerAPI
    server = module.server('link-test', bot_info=_bot('websocket'), tx_queue=queue.Queue(), rx_queue=queue.Queue())
    calls = []
    fake_conn = FakeWS()

    async def connect(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) == 1:
            raise TypeError('additional_headers unsupported')
        return fake_conn

    monkeypatch.setattr(module.websockets, 'connect', connect)
    asyncio.run(server._server__link_to_server())
    assert server.ws_conn is fake_conn
    assert 'additional_headers' in calls[0][1] and 'extra_headers' in calls[1][1]


def test_onebot_link_cancelled_connect_clears_socket_and_propagates(monkeypatch):
    '''取消待建立连接后不得遗留旧 ws_conn 引用，并应继续向上抛出取消。'''

    module = OlivOS.onebotV11LinkServerAPI
    server = module.server('link-test', bot_info=_bot('websocket'), tx_queue=queue.Queue(), rx_queue=queue.Queue())
    server.ws_conn = FakeWS()

    async def cancel_connect(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(module.websockets, 'connect', cancel_connect)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(server._server__link_to_server())
    assert server.ws_conn is None


def test_onebot_link_session_closes_socket_and_notifies(monkeypatch):
    '''会话完成应关闭 socket 且只触发一次关闭回调。'''

    server = OlivOS.onebotV11LinkServerAPI.server(
        'link-test', bot_info=_bot('websocket'), tx_queue=queue.Queue(), rx_queue=queue.Queue())
    ws = FakeWS()
    server.on_open = Mock()
    server.on_close = Mock()
    never = asyncio.Event()

    async def connect():
        server.ws_conn = ws

    async def rx_once():
        return None

    async def tx_forever():
        await never.wait()

    monkeypatch.setattr(server, '_server__link_to_server', connect)
    monkeypatch.setattr(server, 'rx_link', rx_once)
    monkeypatch.setattr(server, 'tx_link', tx_forever)
    asyncio.run(server._server__session_lifecycle())
    assert ws.closed and server.ws_conn is None
    server.on_open.assert_called_once()
    server.on_close.assert_called_once()


def _flask_server(monkeypatch, send_queue):
    '''构造带固定 bot hash 和已捕获数据包的 Flask 上报服务器。'''

    bot = _bot('post', host='127.0.0.1', port=5700)
    bot.hash = OlivOS.API.getBotHash(
        bot_id=bot.id,
        platform_sdk='onebot',
        platform_platform='qq',
        platform_model='default',
    )
    module = OlivOS.flaskServerAPI
    server = module.server(
        'flask-test', 'flask_test', ['POST'], '127.0.0.1', 0,
        tx_queue=send_queue, bot_info_dict={bot.hash: bot})
    monkeypatch.setattr(
        OlivOS.pluginAPI.shallow,
        'rx_packet',
        lambda sdk_event: {'self_id': str(sdk_event.base_info.get('self_id')), 'active': sdk_event.active},
    )
    app = server.app()
    server.set_config()
    app.testing = True
    return server, bot, app


def test_onebot_flask_route_routes_report_and_marks_activity(monkeypatch):
    '''HTTP 上报应进入全局队列并更新账号在线活动。'''

    send_queue = queue.Queue()
    server, bot, app = _flask_server(monkeypatch, send_queue)
    try:
        response = app.test_client().post(
            '/OlivOSMsgApi/qq/onebot/default',
            data=_raw_message(),
            content_type='application/json',
        )
        assert response.status_code == 200
        assert send_queue.get_nowait() == {'self_id': '10001', 'active': True}
        assert server.account_activity()[bot.hash] > 0
    finally:
        server.deregister()


def test_onebot_flask_heartbeat_offline_marks_account_offline(monkeypatch):
    '''显式离线心跳应把在线活动替换为负值标记。'''

    send_queue = queue.Queue()
    server, bot, app = _flask_server(monkeypatch, send_queue)
    try:
        payload = json.loads(_raw_message())
        payload['post_type'] = 'meta_event'
        payload['meta_event_type'] = 'heartbeat'
        payload['status'] = {'online': False}
        response = app.test_client().post(
            '/OlivOSMsgApi/qq/onebot/default',
            data=json.dumps(payload),
            content_type='application/json',
        )
        assert response.status_code == 200
        assert server.account_activity()[bot.hash] <= 0
    finally:
        server.deregister()


def test_onebot_flask_deregister_keeps_current_run_offline(monkeypatch):
    '''停止 HTTP 服务器后，本次运行账号应保持显式离线。'''

    send_queue = queue.Queue()
    server, bot, app = _flask_server(monkeypatch, send_queue)
    app.test_client().post(
        '/OlivOSMsgApi/qq/onebot/default',
        data=_raw_message(),
        content_type='application/json',
    )
    assert server.account_activity()[bot.hash] > 0
    server.deregister()
    retired = OlivOS.flaskServerAPI.http_post_activity()
    assert retired[bot.hash] <= 0


def _dingtalk_server(monkeypatch):
    '''构造可捕获入站 SDK 事件的钉钉 Link 服务器。'''

    module = OlivOS.dingtalkLinkServerAPI
    bot = OlivOS.API.bot_info_T(
        id=10001,
        host='https://fixture.invalid',
        port=443,
        access_token='fixture-token',
        platform_sdk='dingtalk_link',
        platform_platform='dingtalk',
        platform_model='default',
    )
    bot.extends = {'app_key': 'fixture-key', 'app_secret': 'fixture-secret'}
    tx_queue = queue.Queue()
    server = module.server('dingtalk-test', tx_queue=tx_queue, bot_info_dict=bot)
    captured = []
    monkeypatch.setattr(
        OlivOS.pluginAPI.shallow,
        'rx_packet',
        lambda sdk_event: captured.append(sdk_event) or 'tx-packet',
    )
    return server, bot, tx_queue, captured


def test_dingtalk_link_routes_callback_and_replies_to_ping(monkeypatch):
    '''钉钉回调应进入全局队列，ping/事件帧应在 socket 上确认。'''

    server, _, tx_queue, captured = _dingtalk_server(monkeypatch)
    ws = FakeSyncWS()
    callback = {
        'type': 'CALLBACK',
        'headers': {'messageId': 'callback-1', 'topic': '/v1.0/im/bot/messages/get'},
        'data': json.dumps({
            'chatbotUserId': 'bot',
            'msgtype': 'text',
            'text': {'content': 'hello'},
            'conversationType': '2',
            'conversationId': '7',
            'senderStaffId': '42',
            'senderNick': 'tester',
        }),
    }
    server.on_message(ws, json.dumps(callback))
    assert len(captured) == 1 and captured[0].active
    assert tx_queue.get_nowait() == 'tx-packet'
    assert json.loads(ws.sent[-1])['headers']['messageId'] == 'callback-1'

    ping = {
        'type': 'SYSTEM',
        'headers': {'messageId': 'ping-1', 'topic': 'ping'},
        'data': '{}',
    }
    server.on_message(ws, json.dumps(ping))
    assert len(captured) == 1
    assert json.loads(ws.sent[-1])['headers']['messageId'] == 'ping-1'


def test_dingtalk_link_ignores_invalid_and_disconnect_frames(monkeypatch):
    '''畸形 JSON 和远端断开都不得投递 SDK 事件。'''

    server, _, _, captured = _dingtalk_server(monkeypatch)
    ws = FakeSyncWS()
    disconnect = {
        'type': 'SYSTEM',
        'headers': {'messageId': 'disconnect-1', 'topic': 'disconnect'},
        'data': '{}',
    }
    server.on_message(ws, 'not-json')
    server.on_message(ws, json.dumps(disconnect))
    assert captured == [] and ws.sent == []


def test_dingtalk_link_websocket_runner_clears_ticket_after_exit(monkeypatch):
    '''WebSocket 地址应由 endpoint/ticket 拼接，并在 run_forever 结束后清空两者。'''

    server, _, _, _ = _dingtalk_server(monkeypatch)
    captured = {}

    class FakeWebSocketApp:
        def __init__(self, url, **kwargs):
            captured['url'] = url
            captured['callbacks'] = kwargs

        def run_forever(self, **kwargs):
            captured['run'] = kwargs

    monkeypatch.setattr(OlivOS.dingtalkLinkServerAPI.websocket, 'enableTrace', Mock())
    monkeypatch.setattr(OlivOS.dingtalkLinkServerAPI.websocket, 'WebSocketApp', FakeWebSocketApp)
    server.Proc_data['extend_data'].update({
        'websocket_url': 'wss://fixture.invalid/link',
        'websocket_ticket': 'fixture-ticket',
    })
    server.run_websocket_rx_connect_start()
    assert captured['url'].endswith('?ticket=fixture-ticket')
    assert captured['run'] == {'ping_interval': 30, 'ping_timeout': 5}
    assert server.Proc_data['extend_data']['websocket_url'] is None
    assert server.Proc_data['extend_data']['websocket_ticket'] is None


def _qq_webhook_server(monkeypatch):
    '''构造使用固定 bot 账号的 QQ 频道 v2 Webhook 应用。'''

    module = OlivOS.qqGuildv2WebhookServerAPI
    bot = OlivOS.API.bot_info_T(
        id=10001,
        host='127.0.0.1',
        port=443,
        access_token='fixture-secret',
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='public',
        server_type='webhook',
    )
    bot.extends = {'app_key': 'fixture-key', 'app_secret': 'fixture-secret'}
    server = module.server(
        'webhook-test',
        'webhook_test',
        ['POST'],
        '127.0.0.1',
        0,
        tx_queue=queue.Queue(),
        bot_info_dict={bot.hash: bot},
        Flask_server_xpath='/hook',
    )
    app = server.app()
    server.set_config()
    app.testing = True
    return server, bot, app


def test_qq_webhook_requires_known_appid(monkeypatch):
    '''缺失、未知或不匹配的 appid 都应在解析前拒绝。'''

    _, _, app = _qq_webhook_server(monkeypatch)
    client = app.test_client()
    assert client.post('/hook', data='{}').status_code == 401
    assert client.post('/hook', data='{}', headers={'X-Bot-Appid': 'other'}).status_code == 401
    assert client.post('/hook/10002', data='{}', headers={'X-Bot-Appid': '10001'}).status_code == 401


def test_qq_webhook_answers_malformed_json_with_ack(monkeypatch):
    '''畸形请求体也应返回 ACK，避免平台持续重试坏帧。'''

    _, _, app = _qq_webhook_server(monkeypatch)
    response = app.test_client().post(
        '/hook/10001', data='not-json', headers={'X-Bot-Appid': '10001'})
    assert response.status_code == 200
    assert response.get_json()['op'] == 12


def test_qq_webhook_validation_returns_signature(monkeypatch):
    '''op=13 回调握手应使用平台时间戳与密钥签名。'''

    module = OlivOS.qqGuildv2WebhookServerAPI
    _, _, app = _qq_webhook_server(monkeypatch)
    monkeypatch.setattr(module.OlivOS.qqGuildv2SDK, 'get_qqGuildv2_webhook_validation', lambda payload: ('token', 7))
    monkeypatch.setattr(
        module.OlivOS.qqGuildv2SDK,
        'sign_qqGuildv2_webhook_validation',
        lambda secret, ts, token: 'sig',
    )
    response = app.test_client().post(
        '/hook/10001',
        json={'op': 13, 'd': {'plain_token': 'token', 'event_ts': '7'}},
        headers={'X-Bot-Appid': '10001'},
    )
    assert response.status_code == 200
    assert response.get_json() == {'plain_token': 'token', 'signature': 'sig'}


def test_qq_webhook_rejects_invalid_signature(monkeypatch):
    '''没有有效 Ed25519 签名的事件推送不得进入分发器。'''

    module = OlivOS.qqGuildv2WebhookServerAPI
    _, _, app = _qq_webhook_server(monkeypatch)
    dispatched = []
    monkeypatch.setattr(module.OlivOS.qqGuildv2SDK, 'verify_qqGuildv2_webhook_signature', lambda *args: False)
    response = app.test_client().post(
        '/hook/10001',
        json={'op': 0, 't': 'READY', 's': 1, 'id': 'event-1', 'd': {}},
        headers={'X-Bot-Appid': '10001', 'X-Signature-Ed25519': 'bad', 'X-Signature-Timestamp': '7'},
    )
    assert response.status_code == 401
    assert dispatched == []


def test_qq_webhook_dispatches_signed_event_after_ack(monkeypatch):
    '''签名事件应先立即 ACK，再交给后台分发器处理。'''

    module = OlivOS.qqGuildv2WebhookServerAPI
    server, _, app = _qq_webhook_server(monkeypatch)
    finished = threading.Event()
    dispatched = []
    monkeypatch.setattr(module.OlivOS.qqGuildv2SDK, 'verify_qqGuildv2_webhook_signature', lambda *args: True)

    def dispatch(payload_obj, bot_info):
        dispatched.append((payload_obj, bot_info))
        finished.set()

    monkeypatch.setattr(server, '_handle_dispatch', dispatch)
    response = app.test_client().post(
        '/hook/10001',
        json={'op': 0, 't': 'READY', 's': 1, 'id': 'event-1', 'd': {}},
        headers={'X-Bot-Appid': '10001', 'X-Signature-Ed25519': 'good', 'X-Signature-Timestamp': '7'},
    )
    assert response.status_code == 200 and response.get_json()['op'] == 12
    assert finished.wait(timeout=1)
    assert dispatched and dispatched[0][0]['t'] == 'READY'


def test_qq_webhook_listen_url_contains_each_appid(monkeypatch):
    '''运行状态应列出每个已配置 appid 对应的回调地址。'''

    server, _, _ = _qq_webhook_server(monkeypatch)
    assert server._get_appid_list() == ['10001']
    assert server._get_listen_url() == 'http://127.0.0.1:0/hook/10001'


class _FakeGetUpdates:
    '''每次轮询弹出一个预设响应的 Telegram getUpdates 替代实现。'''

    def __init__(self, responses):
        self.responses = responses
        self.data = SimpleNamespace(offset=None)
        self.res = None

    def do_api(self):
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        self.res = SimpleNamespace(text=response)


def _telegram_server(monkeypatch, responses, tx_queue=None):
    '''构造带确定性 getUpdates 响应的 Telegram 轮询服务器。'''

    module = OlivOS.telegramPollServerAPI
    bot = OlivOS.API.bot_info_T(
        id=10001,
        host='https://fixture.invalid',
        port=443,
        access_token='fixture-token',
        platform_sdk='telegram_poll',
        platform_platform='telegram',
        platform_model='default',
    )
    bot.hash = 'telegram-hash'
    tx_queue = tx_queue or queue.Queue()
    server = module.server('poll-test', tx_queue=tx_queue, bot_info_dict={bot.hash: bot})
    monkeypatch.setattr(module.OlivOS.telegramSDK.API, 'getUpdates', lambda _bot: _FakeGetUpdates(responses))
    monkeypatch.setattr(OlivOS.pluginAPI.shallow, 'rx_packet', lambda sdk_event: sdk_event.raw)
    return server, bot, tx_queue


def _telegram_updates(*updates):
    '''把 Telegram 更新列表编码成轮询服务器消费的响应信封。'''

    return json.dumps({'ok': True, 'result': list(updates)})


def test_telegram_poll_skips_initial_backlog_then_advances_cursor(monkeypatch):
    '''首次轮询只记录积压游标而不投递，后续轮询才发送事件。'''

    send_queue = queue.Queue()
    responses = [
        _telegram_updates({'update_id': 1, 'message': {'date': 1, 'message_id': 1, 'text': 'old'}}),
        _telegram_updates(
            {'update_id': 2, 'message': {'date': 2, 'message_id': 2, 'text': 'new'}},
            {'update_id': 3, 'message': {'date': 3, 'message_id': 3, 'text': 'newer'}},
        ),
    ]
    server, bot, _ = _telegram_server(monkeypatch, responses, send_queue)
    server.run_poll_list()
    assert send_queue.empty()
    assert server.Proc_data['bot_info_update_id'][bot.hash] == 2
    server.run_poll_list()
    assert send_queue.qsize() == 2
    assert server.Proc_data['bot_info_update_id'][bot.hash] == 4


def test_telegram_poll_empty_and_exception_responses_are_nonfatal(monkeypatch):
    '''空结果、畸形响应和传输失败都应保持游标不变且不抛错。'''

    responses = [
        _telegram_updates(),
        RuntimeError('fixture transport failure'),
        'not-json',
    ]
    server, bot, _ = _telegram_server(monkeypatch, responses)
    for _ in range(3):
        server.run_poll_list()
    assert server.Proc_data['bot_info_update_id'][bot.hash] == -1


def test_telegram_poll_does_not_advance_malformed_update_id(monkeypatch):
    '''结果列表包含非法 update_id 时应吞掉错误且不破坏游标。'''

    server, bot, _ = _telegram_server(monkeypatch, [_telegram_updates({'update_id': 'bad'})])
    server.run_poll_list()
    assert server.Proc_data['bot_info_update_id'][bot.hash] == -1
