# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_common_contracts.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   QQ API V2 公共 SDK 的离线契约、查询、撤回和上传辅助测试
'''

import json
from collections import deque
from types import SimpleNamespace

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDK as SDK
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common


ACTION = SDK.event_action


class FakeAPI(object):
    def __init__(self, body='', status=200):
        self.res = body
        self.res_code = status
        self.metadata = SimpleNamespace()
        self.data = SimpleNamespace(content=None)
        self.calls = []

    def do_api(self, req_type='POST'):
        self.calls.append(req_type)
        return self.res


def make_event(extend=None, chat_type='guild_channel'):
    bot = SimpleNamespace(hash='bot-hash', id=10001, model='public')
    target_data = SimpleNamespace(
        extend={} if extend is None else extend,
        user_id='user-1',
        group_id='channel-1'
    )
    return SimpleNamespace(
        bot_info=bot,
        plugin_info={},
        data=target_data,
        active=True,
        log_func=lambda *args, **kwargs: None
    )


@pytest.mark.parametrize('data,is_rx,active,expected', [
    ({'id': 'id', 'op': 0, 's': 1, 't': 'READY', 'd': {}}, False, True, ('id', 0, 1, 'READY')),
    ({'id': 'id', 'op': 0, 'd': {}}, True, False, ('id', 0, None, None)),
    ({'id': 1, 'op': 0, 's': 1, 't': 'READY'}, False, False, (None, 0, 1, 'READY')),
    ({'id': 'id', 'op': '0', 's': 1, 't': 'READY'}, False, False, ('id', None, 1, 'READY')),
    ({'id': 'id', 'op': 0, 's': '1', 't': 'READY'}, False, False, ('id', 0, None, 'READY')),
    ({'id': 'id', 'op': 0, 's': 1, 't': 1}, False, False, ('id', 0, 1, None)),
    ({'id': 'id', 'op': 0, 's': 1, 't': 'READY'}, False, True, ('id', 0, 1, 'READY')),
    ('not-a-dict', False, False, (None, None, None, None)),
    (None, False, True, (None, None, None, None)),
])
def test_payload_template_validates_websocket_frames(data, is_rx, active, expected):
    '''WebSocket 帧应校验 id/op/s/t 类型，畸形输入应返回 inactive 模板。'''

    payload = common.payload_template(data, is_rx)
    assert payload.active is active
    assert (payload.data.id, payload.data.op, payload.data.s, payload.data.t) == expected


def test_payload_template_dump_skips_empty_fields():
    '''序列化负载时应跳过空字段，同时保留 op 和 d 等必要字段。'''

    payload = common.payload_template({'id': 'id', 'op': 0, 'd': {'ok': True}, 's': 1, 't': 'READY'})
    assert json.loads(payload.dump()) == {'id': 'id', 'op': 0, 'd': {'ok': True}, 's': 1, 't': 'READY'}
    assert json.loads(common.PAYLOAD.sendHeartbeat(None).dump()) == {'op': 1, 'd': None}


@pytest.mark.parametrize('model,intents_attr', [
    ('private', None),
    ('public', None),
    ('public_guild_only', None),
    ('private_intents', 3),
    ('public_intents', 4),
    ('sandbox_intents', 5),
])
def test_identify_payload_keeps_model_specific_intents(monkeypatch, model, intents_attr):
    '''Identify 负载应按模型选择正确 intents，并写入 QQBot token。'''

    monkeypatch.setattr(common, 'getTokenNow', lambda bot_info: 'token')
    bot = SimpleNamespace(model=model, id=10001, intents=intents_attr)
    payload = common.PAYLOAD.sendIdentify(bot)
    assert payload.active is True
    assert payload.data.op == 2
    assert payload.data.d['token'] == 'QQBot token'
    assert isinstance(payload.data.d['intents'], int)


def test_identify_and_resume_payloads_mark_token_failure(monkeypatch):
    '''获取 token 失败时 Identify 与 Resume 负载都应标记 inactive。'''

    def reject_token(bot_info):
        raise RuntimeError('token unavailable')

    monkeypatch.setattr(common, 'getTokenNow', reject_token)
    bot = SimpleNamespace(model='public', id=10001)
    assert common.PAYLOAD.sendIdentify(bot).active is False
    assert common.PAYLOAD.sendResume(bot, 'session', 1).active is False


def test_resume_and_webhook_payloads_keep_required_fields(monkeypatch):
    '''Resume 负载应保留 token/session/seq，Webhook ACK 的 op 应为 12。'''

    monkeypatch.setattr(common, 'getTokenNow', lambda bot_info: 'token')
    bot = SimpleNamespace(model='public', id=10001)
    resume = common.PAYLOAD.sendResume(bot, 'session', 7)
    assert resume.active is True
    assert resume.data.d == {'token': 'QQBot token', 'session_id': 'session', 'seq': 7}
    assert common.PAYLOAD.sendWebhookAck().data.op == 12


def test_api_template_missing_query_returns_empty_string():
    '''API 模板无有效查询参数时应返回空字符串，不输出悬空问号。'''

    api_obj = common.api_templet()
    assert api_obj._get_query_string() == ''
    api_obj.query = {'empty': None}
    assert api_obj._get_query_string() == ''
    api_obj.query = {'page': 2, 'empty': None}
    assert api_obj._get_query_string() == '?page=2'


def test_api_template_do_api_builds_request_and_query(monkeypatch):
    '''do_api 应完成路由占位替换、查询拼接、鉴权和 JSON 序列化。'''

    calls = []

    def request(method, url, headers=None, data=None, timeout=None):
        calls.append((method, url, headers, data))
        return SimpleNamespace(text='{"ok":true}', status_code=200)

    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda bot_info: 'token')
    api_obj = common.api_templet()
    api_obj.bot_info = SimpleNamespace(model='default', id=10001)
    api_obj.host = 'https://api.example.invalid'
    api_obj.route = '/v2/users/{openid}/info'
    api_obj.metadata = SimpleNamespace(openid='openid-1')
    api_obj.data = SimpleNamespace(name='value', empty=None)
    api_obj.query = {'page': 1, 'cursor': None}
    assert api_obj.do_api('POST') == '{"ok":true}'
    method, url, headers, body = calls[0]
    assert method == 'POST'
    assert url == 'https://api.example.invalid:443/v2/users/openid-1/info?page=1'
    assert headers['Authorization'] == 'QQBot token'
    assert headers['X-Union-Appid'] == '10001'
    assert json.loads(body) == {'name': 'value'}


@pytest.mark.parametrize('method,has_data,expected_body', [
    ('GET', True, False),
    ('DELETE', True, True),
    ('DELETE', False, False),
    ('PUT', True, True),
    ('PATCH', False, False),
])
def test_api_template_do_api_supports_http_methods(monkeypatch, method, has_data, expected_body):
    '''do_api 应按 HTTP 方法决定是否发送 JSON 请求体。'''

    calls = []

    def request(req_method, url, headers=None, data=None, timeout=None):
        calls.append((req_method, data))
        return SimpleNamespace(text='{}', status_code=204)

    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda bot_info: 'token')
    api_obj = common.api_templet()
    api_obj.bot_info = SimpleNamespace(model='default', id=10001)
    api_obj.host = 'https://api.example.invalid'
    api_obj.route = '/v2/test'
    api_obj.data = SimpleNamespace(value=1) if has_data else None
    assert api_obj.do_api(method) == '{}'
    assert calls[0][0] == method
    assert (calls[0][1] is not None) is expected_body


def test_api_template_switches_sandbox_host(monkeypatch):
    '''sandbox 模型应把默认 API 主机切换为沙箱地址。'''

    calls = []

    def request(method, url, headers=None, data=None, timeout=None):
        calls.append(url)
        return SimpleNamespace(text='{}', status_code=200)

    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda bot_info: 'token')
    api_obj = common.api_templet()
    api_obj.bot_info = SimpleNamespace(model='sandbox', id=10001)
    api_obj.host = common.sdkAPIHost['default']
    api_obj.route = '/v2/test'
    api_obj.do_api('GET')
    assert calls[0].startswith(common.sdkAPIHost['sandbox'])


def test_api_template_do_api_plant_and_failure_paths(monkeypatch):
    '''do_api_plant 应记录状态码并返回响应，网络异常应返回 None。'''

    monkeypatch.setattr(common, 'getTokenNow', lambda bot_info: 'token')
    monkeypatch.setattr(common.traceback, 'print_exc', lambda: None)
    monkeypatch.setattr(common.req, 'request', lambda *args, **kwargs: SimpleNamespace(text='{}', status_code=200))
    plant = common.api_templet()
    plant.bot_info = SimpleNamespace(model='default', id=10001)
    plant.host = 'https://api.example.invalid'
    plant.route = '/v2/test'
    plant.data = SimpleNamespace(value=1)
    assert plant.do_api_plant('GET') == '{}'
    assert plant.res_code == 200

    def reject(*args, **kwargs):
        raise RuntimeError('offline')

    monkeypatch.setattr(common.req, 'request', reject)
    assert plant.do_api('GET') is None
    assert plant.do_api_plant('POST') is None


API_CLASS_NAMES = [
    'getAppAccessToken', 'getGateway', 'getMe', 'getQQUserInfo', 'generateUrlLink',
    'putInteraction', 'getGlobalMenu', 'setGlobalMenu', 'getCommandPanels',
    'createCommandPanel', 'getCommandPanel', 'setCommandPanel', 'deleteCommandPanel',
    'setCommandPanelTarget', 'prepareMediaImage', 'completeMediaImage', 'getMediaImages',
    'deleteMediaImage', 'uploadMediaImage', 'setResourcePictureUpload', 'uploadPrepare',
    'uploadPartFinish',
]


@pytest.mark.parametrize('class_name', API_CLASS_NAMES)
def test_api_common_templates_configure_host_and_route(class_name):
    '''各公共 API 模板应初始化非空 host/route，并保持未请求状态。'''

    api_class = getattr(SDK.API, class_name)
    if class_name == 'uploadMediaImage':
        api_obj = api_class(upload_url='https://example.invalid/file', content_type='image/png', file_data=b'x')
        assert api_obj.upload_url == 'https://example.invalid/file'
        assert api_obj.res is None
        return
    api_obj = api_class(bot_info=SimpleNamespace(id=10001, model='public'))
    assert isinstance(api_obj.host, str) and api_obj.host != ''
    assert isinstance(api_obj.route, str) and api_obj.route != ''
    assert api_obj.res is None
    assert api_obj.res_code is None


@pytest.mark.parametrize('class_name,suffix', [
    ('setResourcePictureUpload', '/files'),
    ('uploadPrepare', '/upload_prepare'),
    ('uploadPartFinish', '/upload_part_finish'),
])
def test_resource_api_templates_rebuild_resource_route(monkeypatch, class_name, suffix):
    '''资源上传相关 API 应根据 openid 重建 /groups 路由。'''

    urls = []

    def request(method, url, headers=None, data=None, timeout=None):
        urls.append(url)
        return SimpleNamespace(text='{}', status_code=200)

    monkeypatch.setattr(common.req, 'request', request)
    monkeypatch.setattr(common, 'getTokenNow', lambda bot_info: 'token')
    api_obj = getattr(SDK.API, class_name)(bot_info=SimpleNamespace(id=10001, model='public'))
    api_obj.metadata.openid = 'openid-1'
    assert api_obj.do_api('POST') == '{}'
    assert urls[0].endswith('/groups/openid-1' + suffix)


def test_upload_media_image_puts_binary_and_returns_failure(monkeypatch):
    '''uploadMediaImage 应以 PUT 发送二进制并保留响应头，异常返回 None。'''

    seen = []

    def request(method, url, headers=None, data=None, timeout=None):
        seen.append((method, url, headers, data))
        return SimpleNamespace(text='', status_code=200, headers={'etag': 'x'})

    monkeypatch.setattr(common.req, 'request', request)
    api_obj = SDK.API.uploadMediaImage('https://upload.invalid/1', 'image/png', b'data')
    assert api_obj.do_api() == ''
    assert seen[0] == ('PUT', 'https://upload.invalid/1', {'Content-Type': 'image/png'}, b'data')
    assert api_obj.res_headers == {'etag': 'x'}

    def reject(*args, **kwargs):
        raise RuntimeError('offline')

    monkeypatch.setattr(common.req, 'request', reject)
    assert api_obj.do_api() is None


def test_standard_group_helpers_normalize_common_response_shapes():
    '''群信息、群列表和成员列表应兼容常见嵌套响应结构。'''

    info = ACTION._standard_group_info({
        'active': True,
        'data': {'response': {'id': 'g1', 'title': 'Group', 'description': 'memo', 'max_members_count': 9}}
    }, fallback_id='fallback')
    assert info['active'] is True
    assert info['data']['id'] == 'g1'
    assert info['data']['name'] == 'Group'
    assert info['data']['memo'] == 'memo'
    assert info['data']['max_member_count'] == 9

    groups = ACTION._standard_group_list({
        'active': True,
        'data': {'response': {'data': {'items': [{'id': 'g1'}, {'no_id': True}, 'bad']}}}
    })
    assert groups['active'] is True
    assert [item['id'] for item in groups['data']] == ['g1']

    members = ACTION._standard_group_member_list({
        'active': True,
        'data': {'response': {'members': [{'member_openid': 'u1', 'nick': 'Nick'}, {'id': None}, 'bad']}}
    }, fallback_group_id='g1')
    assert members['active'] is True
    assert members['data'][0]['user_id'] == 'u1'
    assert members['data'][0]['group_id'] == 'g1'
    assert members['data'][0]['card'] == 'Nick'


@pytest.mark.parametrize('raw_result', [
    None,
    {'active': False, 'data': {'response': {'id': 'g1'}}},
    {'active': True, 'data': {'response': 'not-a-dict'}},
])
def test_standard_group_info_keeps_inactive_contract(raw_result):
    '''群信息结果无效或 inactive 时不得产出可用数据。'''

    assert ACTION._standard_group_info(raw_result)['active'] is False


def test_standard_list_helpers_reject_unusable_containers():
    '''列表辅助方法遇到不可用容器时应返回 inactive。'''

    assert ACTION._standard_group_list({'active': True, 'data': {'response': {'items': {}}}})['active'] is False
    assert ACTION._standard_group_member_list({'active': True, 'data': {'response': {'members': 1}}})['active'] is False


def test_get_msg_prefers_cached_record(monkeypatch):
    '''get_msg 命中本地缓存时应直接返回，不发起网络请求。'''

    record = {
        'message_id': 'm1', 'sender_id': 42, 'sender_name': 'Alice', 'time': 10,
        'message': 'hello', 'raw_message': 'hello'
    }
    monkeypatch.setattr(common, '_get_qq_rx_message', lambda bot_hash, message_id: record)
    monkeypatch.setattr(common.req, 'request', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('network')))
    result = ACTION.get_msg(make_event(), 'm1')
    assert result['active'] is True
    assert result['data']['message_id'] == 'm1'
    assert result['data']['sender']['id'] == '42'
    assert result['data']['message'] == 'hello'


def test_get_msg_rejects_empty_id_and_qq_context_without_transport(monkeypatch):
    '''空消息 id 或缺少 QQ 传输上下文的请求应直接失败。'''

    monkeypatch.setattr(common, '_get_qq_rx_message', lambda bot_hash, message_id: None)
    assert ACTION.get_msg(make_event(), '')['active'] is False
    qq_event = make_event({'flag_from_qq': True, 'group_id': 'group-1'})
    assert ACTION.get_msg(qq_event, 'm1')['active'] is False


def test_get_msg_falls_back_to_channel_api_and_registers_cache(monkeypatch):
    '''缓存未命中时应回退频道消息接口，并把结果登记进缓存。'''

    body = {
        'message': {
            'id': 'm1', 'content': 'hello', 'channel_id': 'channel-1',
            'author': {'id': 'u1', 'username': 'Alice'}, 'attachments': []
        }
    }
    fake_api = FakeAPI(json.dumps(body), 200)
    record = {'message_id': 'm1', 'sender_id': 'u1', 'sender_name': 'Alice', 'message': None}
    calls = []

    def get_cached(bot_hash, message_id):
        calls.append((bot_hash, message_id))
        return None if len(calls) == 1 else record

    monkeypatch.setattr(common, 'API', type('FakeAPIHost', (), {'getMessage': staticmethod(lambda bot_info: fake_api)}))
    monkeypatch.setattr(common, 'get_SDK_bot_info_from_Event', lambda event: None)
    monkeypatch.setattr(common, '_get_qq_rx_message', get_cached)
    monkeypatch.setattr(common, '_register_qq_rx_message', lambda *args, **kwargs: None)
    result = ACTION.get_msg(make_event({'flag_from_qq': False, 'group_id': 'channel-1'}), 'm1')
    assert result['active'] is True
    assert fake_api.calls == ['GET']
    assert result['data']['sender']['name'] == 'Alice'


@pytest.mark.parametrize('fake_api', [
    FakeAPI('{"message":{"id":"m1"}}', 500),
    FakeAPI('not-json', 200),
    FakeAPI('{"message":"bad"}', 200),
])
def test_get_msg_ignores_failed_or_malformed_channel_response(monkeypatch, fake_api):
    '''频道接口失败或结果畸形时应保持 inactive，不影响调用方。'''

    monkeypatch.setattr(common, 'API', type('FakeAPIHost', (), {'getMessage': staticmethod(lambda bot_info: fake_api)}))
    monkeypatch.setattr(common, 'get_SDK_bot_info_from_Event', lambda event: None)
    monkeypatch.setattr(common, '_get_qq_rx_message', lambda bot_hash, message_id: None)
    result = ACTION.get_msg(make_event({'flag_from_qq': False, 'group_id': 'channel-1'}), 'm1')
    assert result['active'] is False


@pytest.mark.parametrize('chat_type,api_name,field', [
    ('qq_group', 'deleteQQMessage', 'group_openid'),
    ('qq_private', 'deleteQQDirectMessage', 'openid'),
    ('guild_private', 'deleteDirectMessage', 'guild_id'),
    ('guild_channel', 'deleteMessage', 'channel_id'),
])
def test_delete_message_routes_each_chat_type(monkeypatch, chat_type, api_name, field):
    '''delete_message 应按群、私聊、频道分别选择撤回接口。'''

    fake_api = FakeAPI('', 200 if chat_type.startswith('qq_') else 204)
    monkeypatch.setattr(common.API, api_name, lambda bot_info, fake_api=fake_api: fake_api)
    monkeypatch.setattr(common, 'get_SDK_bot_info_from_Event', lambda event: None)
    monkeypatch.setattr(common, '_check_sent_message_for_delete', lambda *args: None)
    monkeypatch.setattr(common, '_acquire_delete_rate', lambda bot_hash: True)
    result = ACTION.delete_message(make_event(), chat_type, 'chat-1', 'm1')
    assert result['active'] is True
    assert result['data']['operation'] == 'delete'
    assert getattr(fake_api.metadata, field) == 'chat-1'
    assert fake_api.metadata.message_id == 'm1'
    assert fake_api.calls == ['DELETE']


@pytest.mark.parametrize('chat_type,chat_id,message_id,error', [
    ('unknown', 'chat-1', 'm1', 'unsupported chat_type'),
    ('qq_group', '', 'm1', 'chat_id is required'),
    ('qq_group', 'chat-1', '', 'message_id is required'),
])
def test_delete_message_validates_target_before_network(monkeypatch, chat_type, chat_id, message_id, error):
    '''撤回前应校验 chat_type、chat_id 和 message_id，非法目标不得联网。'''

    monkeypatch.setattr(common.req, 'request', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('network')))
    result = ACTION.delete_message(make_event(), chat_type, chat_id, message_id)
    assert result['active'] is False
    assert result['data']['error'] == error


@pytest.mark.parametrize('delete_error,rate_allowed,error', [
    ('message not recallable', True, 'message not recallable'),
    (None, False, 'message recall rate limit exceeded'),
])
def test_delete_message_stops_on_cache_or_rate_limit(monkeypatch, delete_error, rate_allowed, error):
    '''撤回缓存校验或频率限制失败时应停止并返回明确错误。'''

    monkeypatch.setattr(common, '_check_sent_message_for_delete', lambda *args: delete_error)
    monkeypatch.setattr(common, '_acquire_delete_rate', lambda bot_hash: rate_allowed)
    result = ACTION.delete_message(make_event(), 'qq_group', 'group-1', 'm1')
    assert result['active'] is False
    assert result['data']['error'] == error


@pytest.mark.parametrize('extend,expected', [
    ({'flag_from_qq': True}, ('qq_group', 'channel-1')),
    ({'flag_from_qq': True, 'flag_from_direct': True}, ('qq_private', 'user-1')),
    ({'flag_from_direct': True, 'host_group_id': 'host-1'}, ('guild_private', 'host-1')),
    ({'flag_from_direct': True}, ('guild_private', 'channel-1')),
    ({}, ('guild_channel', 'channel-1')),
])
def test_delete_msg_infers_chat_context(monkeypatch, extend, expected):
    '''delete_msg 应根据事件扩展字段推断 QQ 群、私聊或频道上下文。'''

    calls = []

    def fake_delete(target_event, chat_type, chat_id, message_id):
        calls.append((chat_type, chat_id, message_id))
        return {'active': True}

    monkeypatch.setattr(common.event_action, 'delete_message', fake_delete)
    assert ACTION.delete_msg(make_event(extend), 'm1')['active'] is True
    assert calls == [(expected[0], expected[1], 'm1')]


def test_delete_msg_rejects_event_without_context():
    '''事件缺少会话上下文时 delete_msg 应返回 inactive 错误。'''

    event = make_event()
    event.data = SimpleNamespace()
    result = ACTION.delete_msg(event, 'm1')
    assert result['active'] is False
    assert result['data']['error'] == 'current event has no chat context'


def test_get_login_info_uses_cache_then_falls_back_to_api(monkeypatch):
    '''登录信息应优先读缓存，缓存缺失时回退 getMe 接口。'''

    event = make_event()
    monkeypatch.setattr(common, 'sdkSelfInfo', {'bot-hash': {'id': 'bot', 'username': 'Cached'}})
    cached = ACTION.get_login_info(event)
    assert cached['active'] is True
    assert cached['data']['name'] == 'Cached'

    monkeypatch.setattr(common, 'sdkSelfInfo', {})
    fake_api = FakeAPI('{"id":"bot-2","username":"Remote"}', 200)
    monkeypatch.setattr(common.API, 'getMe', lambda bot_info: fake_api)
    monkeypatch.setattr(common, 'get_SDK_bot_info_from_Event', lambda target_event: None)
    remote = ACTION.get_login_info(event)
    assert remote['active'] is True
    assert remote['data']['id'] == 'bot-2'
    assert remote['data']['name'] == 'Remote'


def test_get_login_info_tolerates_api_failure_and_bad_payload(monkeypatch):
    '''登录接口失败或回包畸形时应保持 inactive 且不抛错。'''

    event = make_event()
    monkeypatch.setattr(common, 'sdkSelfInfo', {})
    monkeypatch.setattr(common, 'get_SDK_bot_info_from_Event', lambda target_event: None)
    monkeypatch.setattr(common.API, 'getMe', lambda bot_info: FakeAPI('not-json', 500))
    assert ACTION.get_login_info(event)['active'] is False

    def reject(bot_info):
        raise RuntimeError('offline')

    monkeypatch.setattr(common.API, 'getMe', reject)
    assert ACTION.get_login_info(event)['active'] is False


def test_get_user_info_exposes_cached_record_without_mutating_cache(monkeypatch):
    '''get_user_info 应暴露缓存记录但不得修改内部缓存对象。'''

    event = make_event()
    record = {'id': 'u1', 'name': 'Alice', 'time_monotonic': 1}
    monkeypatch.setattr(common, '_ensure_qq_user_basic_info', lambda *args, **kwargs: (record, False))
    monkeypatch.setattr(common, '_get_qq_user_info', lambda bot_hash, user_id: dict(record))
    monkeypatch.setattr(common, '_qq_user_avatar_url', lambda bot_id, user_id: 'https://example.invalid/a.png')
    result = ACTION.get_user_info(event, 'u1')
    assert result['active'] is True
    assert result['data']['user_info']['name'] == 'Alice'
    assert result['data']['user_info']['avatar'] == 'https://example.invalid/a.png'
    assert 'time_monotonic' not in result['data']['user_info']


def test_get_user_info_can_return_avatar_only(monkeypatch):
    '''用户基础信息缺失时仍可仅返回 id 与头像地址。'''

    event = make_event()
    monkeypatch.setattr(common, '_ensure_qq_user_basic_info', lambda *args, **kwargs: (None, False))
    monkeypatch.setattr(common, '_get_qq_user_info', lambda bot_hash, user_id: None)
    monkeypatch.setattr(common, '_qq_user_avatar_url', lambda bot_id, user_id: 'https://example.invalid/a.png')
    result = ACTION.get_user_info(event, 'u1')
    assert result['data']['user_info'] == {'id': 'u1', 'avatar': 'https://example.invalid/a.png'}


def test_get_unhandled_events_keeps_latest_and_can_clear(monkeypatch):
    '''未处理事件应按 limit 返回最新记录，clear 后清空队列。'''

    events = deque([{'id': 1}, {'id': 2}, {'id': 3}])
    monkeypatch.setattr(common, 'sdkUnhandledEventInfo', {'bot-hash': events})
    result = ACTION.get_unhandled_events(make_event(), limit=2, flag_clear=True)
    assert [item['id'] for item in result['data']['events']] == [2, 3]
    assert list(events) == []


def test_get_unhandled_events_returns_empty_for_unknown_bot(monkeypatch):
    '''未知 bot 查询未处理事件应返回 active 空列表。'''

    monkeypatch.setattr(common, 'sdkUnhandledEventInfo', {})
    result = ACTION.get_unhandled_events(make_event())
    assert result['active'] is True
    assert result['data']['events'] == []


def test_normalize_outgoing_message_accepts_public_message_shapes():
    '''出站消息应接受 Message_templet、PARA 列表及可字符串化对象。'''

    existing = OlivOS.messageAPI.Message_templet('olivos_para', [OlivOS.messageAPI.PARA.text('existing')])
    assert ACTION._normalize_outgoing_message(make_event(), existing) is existing
    para_message = ACTION._normalize_outgoing_message(make_event(), [OlivOS.messageAPI.PARA.text('part')])
    assert [para.CQ() for para in para_message.data] == ['part']
    assert ACTION._normalize_outgoing_message(make_event(), [OlivOS.messageAPI.PARA.text('part'), object()]).data == []
    assert ACTION._normalize_outgoing_message(make_event(), 42).data[0].CQ() == '42'


def test_message_reference_and_reply_sequence_helpers():
    '''消息引用与被动回复序号辅助方法应生成稳定标识。'''

    message = OlivOS.messageAPI.Message_templet(
        'olivos_para',
        [OlivOS.messageAPI.PARA.reply('m1'), OlivOS.messageAPI.PARA.text('hello')]
    )
    assert ACTION._get_message_reference_id(message) == 'm1'
    assert ACTION._get_message_reference_id(
        OlivOS.messageAPI.Message_templet('olivos_para', [OlivOS.messageAPI.PARA.text('hello')])
    ) is None
    assert ACTION._get_reply_seq_key(make_event(), 'qq_group', 'group-1', 'm1') == 'bot-hash|qq_group|group-1|m1'


@pytest.mark.parametrize('extend,chat_type,expected', [
    ({'flag_from_qq': True, 'qq_event_type': None, 'reply_msg_id': 'm0'}, 'qq_group', ('m0', None)),
    ({'flag_from_qq': True, 'qq_event_type': 'INTERACTION_CREATE', 'event_id': 'e1'}, 'qq_group', (None, 'e1')),
    ({'flag_from_qq': True, 'qq_event_type': 'INTERACTION_CREATE'}, 'qq_group', (None, None)),
    ({'flag_from_qq': True, 'qq_passive_reply_disabled': True}, 'qq_group', (None, None)),
    (
        {'flag_from_qq': True, 'qq_passive_reply_disabled': {'chat_type': 'qq_group', 'chat_id': 'channel-1'}},
        'qq_group',
        (None, None),
    ),
    ({'flag_from_qq': False}, 'qq_group', (None, None)),
])
def test_resolve_passive_ids_only_reuses_same_conversation(extend, chat_type, expected):
    '''被动回复 id 只在同一会话内复用，显式参数优先。'''

    event = make_event(extend)
    assert ACTION._resolve_qq_passive_ids(event, chat_type, 'channel-1') == expected
    assert ACTION._resolve_qq_passive_ids(event, chat_type, 'channel-1', msg_id='m2', event_id='e2') == ('m2', 'e2')


def keyboard_with_permission(permission):
    return {'content': {'rows': [{'buttons': [{'action': {'permission': permission}}]}]}}


@pytest.mark.parametrize('keyboard,chat_type,error', [
    (None, 'qq_group', None),
    ('not-a-dict', 'qq_group', 'keyboard must be a dict'),
    ({'content': 'bad'}, 'qq_group', 'keyboard content must be a dict'),
    ({'content': {'rows': 'bad'}}, 'qq_group', 'keyboard rows must be a list'),
    ({'content': {'rows': ['bad']}}, 'qq_group', 'keyboard row buttons must be a list'),
    ({'content': {'rows': [{'buttons': ['bad']}]}}, 'qq_group', 'keyboard button must be a dict'),
    ({'content': {'rows': [{'buttons': [{'action': 'bad'}]}]}}, 'qq_group', 'keyboard action must be a dict'),
    (keyboard_with_permission('bad'), 'qq_group', 'keyboard permission must be a dict'),
    (keyboard_with_permission({'type': 3}), 'qq_group', 'keyboard permission type must be 0, 1 or 2'),
    (
        keyboard_with_permission({'specify_user_ids': 'bad'}),
        'qq_group',
        'keyboard permission specify_user_ids must be a list',
    ),
    (
        keyboard_with_permission({'specify_role_ids': ['r1']}),
        'qq_group',
        'specify_role_ids is only available for guild channels',
    ),
    (keyboard_with_permission({'type': 1, 'specify_role_ids': ['r1']}), 'guild_channel', None),
])
def test_keyboard_permission_validation_matrix(keyboard, chat_type, error):
    '''键盘权限校验应覆盖类型、用户列表和频道专属字段。'''

    assert ACTION._validate_keyboard_permissions(keyboard, chat_type) == error


def test_message_chunks_keep_text_and_media_order():
    '''消息分块应保持文本与媒体顺序，并正确处理首尾媒体。'''

    text = OlivOS.messageAPI.PARA.text('hello')
    image = OlivOS.messageAPI.PARA.image('a.png')
    message = OlivOS.messageAPI.Message_templet('olivos_para', [text, image, OlivOS.messageAPI.PARA.text('tail')])
    assert ACTION._get_message_send_chunks(message, (OlivOS.messageAPI.PARA.image,)) == [
        ('hello', image), ('tail', None)
    ]
    message = OlivOS.messageAPI.Message_templet(
        'olivos_para',
        [image, OlivOS.messageAPI.PARA.text('middle'), OlivOS.messageAPI.PARA.image('b.png')]
    )
    assert ACTION._get_message_send_chunks(message, (OlivOS.messageAPI.PARA.image,)) == [
        ('middle', image), ('', message.data[2])
    ]
    assert ACTION._get_message_send_chunks(OlivOS.messageAPI.Message_templet('olivos_para', []), ()) == []


def test_resource_upload_parts_sort_and_validate_ranges():
    '''资源分片应按索引排序，并校验范围、URL 和块大小。'''

    prepare = {
        'block_size': 4,
        'parts': [
            {'index': 1, 'presigned_url': 'https://upload/2', 'block_size': 2},
            {'index': 0, 'presigned_url': 'https://upload/1', 'block_size': 2},
        ]
    }
    assert ACTION._get_resource_upload_parts(prepare, 4) == [
        {'index': 0, 'presigned_url': 'https://upload/1', 'offset': 0, 'size': 2},
        {'index': 1, 'presigned_url': 'https://upload/2', 'offset': 2, 'size': 2},
    ]
    assert ACTION._get_resource_upload_parts({'parts': []}, 4) is None
    assert ACTION._get_resource_upload_parts({'parts': ['bad']}, 4) is None
    assert ACTION._get_resource_upload_parts({'parts': [{'index': -1, 'presigned_url': 'u'}]}, 4) is None
    assert ACTION._get_resource_upload_parts({'parts': [{'index': 0, 'presigned_url': ''}]}, 4) is None
    assert ACTION._get_resource_upload_parts(
        {'parts': [{'index': 0, 'presigned_url': 'u', 'block_size': 2}]}, 4
    ) is None
    assert ACTION._get_resource_upload_parts(
        {'parts': [{'index': 0, 'presigned_url': 'u', 'block_size': 0}]}, 0
    ) is None


@pytest.mark.parametrize('body,status,expected', [
    ('{"file_info":"file-1","ttl":60}', 200, ('file-1', 60)),
    ('{"data":{"file_info":"file-2","ttl":0}}', 201, ('file-2', 0)),
    ('not-json', 200, (None, None)),
    ('{"code":400,"message":"bad"}', 200, (None, None)),
    ('{"file_info":"file-1"}', 500, (None, None)),
    ('{"data":"bad"}', 200, (None, None)),
    ('{}', 200, (None, None)),
])
def test_parse_resource_upload_result_handles_success_and_errors(body, status, expected):
    '''资源上传结果应兼容根级与 data 嵌套成功包，拒绝错误响应。'''

    fake_api = FakeAPI(body, status)
    assert ACTION._parse_resource_upload_result(fake_api) == expected


def test_resource_file_name_prefers_explicit_name_then_url_path():
    '''资源文件名应优先显式名称，其次 URL 路径，必要时按类型生成。'''

    assert ACTION._get_resource_file_name('https://example.invalid/a.png', file_name=' named.png ') == 'named.png'
    assert ACTION._get_resource_file_name('https://example.invalid/path/photo.jpg') == 'photo.jpg'
    generated = ACTION._get_resource_file_name('https://example.invalid/path/without-ext', type_path='images')
    assert generated.endswith('.png')
    assert ACTION._get_resource_file_name('not a url', type_path='unknown').endswith('.dat')


def test_resource_numeric_helpers_fall_back_on_bad_values():
    '''上传数值转换失败或为负数时应回退默认值。'''

    assert ACTION._get_upload_int('4', 1) == 4
    assert ACTION._get_upload_int('bad', 1) == 1
    assert ACTION._get_upload_float('1.5', 1.0) == 1.5
    assert ACTION._get_upload_float('bad', 1.0) == 1.0
    assert ACTION._get_upload_float(-1, 1.0) == 1.0


def test_resource_upload_and_raw_api_result_contracts():
    '''资源上传和原始 API 结果应统一 active/data 与错误契约。'''

    uploaded = ACTION._make_resource_upload_result('qq_group', 'group-1', 'file-1', 'upload')
    assert uploaded['active'] is True
    assert uploaded['data']['file_info'] == 'file-1'
    assert ACTION._make_resource_upload_result('qq_group', None, None, 'upload')['active'] is False

    fake_api = FakeAPI('{"ok":true}', 200)
    raw_result = ACTION._make_raw_api_result(fake_api, 'probe')
    assert raw_result['active'] is True
    assert raw_result['data']['response'] == {'ok': True}
    assert ACTION._raw_response(raw_result) == {'ok': True}
    assert ACTION._raw_response(None) is None

    fake_api = FakeAPI('{"code":400,"message":"bad"}', 400)
    raw_result = ACTION._make_raw_api_result(fake_api, 'probe')
    assert raw_result['active'] is False
    assert raw_result['data']['error'] == 'bad'
    assert ACTION._run_raw_api(fake_api, 'probe')['active'] is False


@pytest.mark.parametrize('extend,flag_direct,error', [
    (None, False, None),
    ({'flag_from_qq': False}, False, 'QQ group/C2C file upload is unavailable in a guild context'),
    (
        {'flag_from_qq': True, 'flag_from_direct': False},
        True,
        'current QQ event chat type does not match the file upload target',
    ),
    ({'flag_from_qq': True, 'flag_from_direct': True}, True, None),
])
def test_upload_context_error_explains_mismatch(extend, flag_direct, error):
    '''QQ 群/C2C 文件上传应校验当前事件会话与目标类型一致。'''

    event = make_event(extend)
    if extend is None:
        event.data = SimpleNamespace()
    assert ACTION._get_qq_upload_context_error(event, flag_direct) == error
