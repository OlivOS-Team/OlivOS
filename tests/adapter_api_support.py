'''真实适配器契约测试共用的离线 API 夹具。'''

import json
import queue
from types import SimpleNamespace as NS
from urllib.parse import parse_qs, urlsplit

import OlivOS


class FakeHTTPResponse:
    '''最小 requests.Response 替身，保留适配器实际读取的 text/status/body。'''

    def __init__(self, payload=None, text=None, status_code=200):
        if text is None:
            text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        self.text = text
        self.status_code = status_code
        self.body = text
        self.content = text.encode('utf-8') if isinstance(text, str) else text
        self.headers = {}


class RequestRecorder:
    '''记录 adapter 发出的请求，并按需返回成功、错误或异常响应。'''

    def __init__(self, response=None, error=None, responses=None):
        self.response = response if response is not None else FakeHTTPResponse({})
        self.error = error
        self.responses = list(responses or [])
        self.calls = []

    def __call__(self, method, url, **kwargs):
        call = NS(
            method=method,
            url=url,
            headers=kwargs.get('headers'),
            data=kwargs.get('data'),
            params=kwargs.get('params'),
            timeout=kwargs.get('timeout'),
            kwargs=kwargs,
        )
        self.calls.append(call)
        if self.error is not None:
            raise self.error
        if self.responses:
            response = self.responses.pop(0)
            if callable(response):
                return response(call)
            if isinstance(response, BaseException):
                raise response
            return response
        return self.response


def json_body(call):
    '''把记录的 POST 请求体解码成字典，便于断言字段和过滤规则。'''

    raw = call.data
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    if raw is None:
        return None
    return json.loads(raw)


def query_params(call):
    '''取出 URL 查询参数，保留同名多值场景。'''

    return parse_qs(urlsplit(call.url).query, keep_blank_values=True)


def make_bot(model='default', server_type='post', sdk='onebot', platform='qq', access_token='fixture-token'):
    '''构造带 post_info 的插件可见账号，覆盖 get_SDK_bot_info_from_Event 的入参形状。'''

    bot = OlivOS.API.bot_info_T(
        id=10001,
        server_type=server_type,
        host='127.0.0.1',
        port=5700,
        access_token=access_token,
        platform_sdk=sdk,
        platform_platform=platform,
        platform_model=model,
    )
    bot.extends = {'app_key': 'fixture-key', 'app_secret': 'fixture-secret'}
    return bot


def make_event(bot, data=None, control_queue=None, platform=None):
    '''构造 event_action 所需的最小 Event 形状，避免触发真实协议连接。'''

    default_data = {
        'message_id': '8',
        'group_id': '7',
        'user_id': '42',
        'host_id': '9',
        'operator_id': '5',
        'duration': 60,
        'flag': 'fixture-flag',
        'sub_type': 'add',
    }
    default_data.update(data or {})
    return NS(
        bot_info=bot,
        plugin_info={'control_queue': control_queue if control_queue is not None else queue.Queue()},
        data=NS(**default_data),
        platform=platform or dict(bot.platform),
    )


def onebot_ok(data=None, **extra):
    '''OneBot V11 标准成功回包。'''

    payload = {'status': 'ok', 'retcode': 0, 'data': data}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def onebot_failed(retcode=1404, wording=None):
    '''OneBot V11 标准失败回包，用于错误文案和 active=False 分支。'''

    payload = {'status': 'failed', 'retcode': retcode, 'data': None}
    if wording is not None:
        payload['wording'] = wording
    return json.dumps(payload, ensure_ascii=False)


def kook_ok(data=None, **extra):
    '''KOOK 成功回包，code=0 才会进入解析流程。'''

    payload = {'code': 0, 'message': 'ok', 'data': data if data is not None else {}}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def kook_failed(code=40100, message='denied'):
    '''KOOK 业务失败回包。'''

    return json.dumps({'code': code, 'message': message}, ensure_ascii=False)


def xhh_ok(result=None, **extra):
    '''小黑盒成功回包，支持 result 或 status=ok 两种历史格式。'''

    payload = {'code': 0, 'status': 'ok', 'result': result if result is not None else {}}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def xhh_failed(code=40001, msg='denied'):
    '''小黑盒业务失败回包。'''

    return json.dumps({'code': code, 'status': 'failed', 'msg': msg}, ensure_ascii=False)


def drain_queue(control_queue):
    '''非阻塞取出全部控制包，防止测试结束时仍有未消费数据。'''

    packets = []
    while True:
        try:
            packets.append(control_queue.get_nowait())
        except queue.Empty:
            return packets
