# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_send_retry.py
@Author    :   Desom-fu
@Contact   :   desom233@outlook.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   发送失败按错误类型分档重试，以及长度超限后的降级重发
'''

from types import SimpleNamespace

import pytest

from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common

SDK = common


LENGTH_BODY = '{"message":"消息发送失败, 长度超长","code":40054007,"err_code":40054007}'
LONG_BODY = '{"message":"消息发送失败, 消息过长或异常","code":40054018,"err_code":40054018}'
SERVER_BODY = '{"message":"消息发送异常，请稍后重试","code":50055001,"err_code":50055001}'
BANNED_BODY = '{"message":"机器人被禁言","code":40054002,"err_code":40054002}'
DUP_BODY = '{"message":"消息被去重","code":40054005,"err_code":40054005}'
OK_BODY = '{"id":"MSGID","timestamp":"2026-11-09T23:00:00+08:00"}'


def make_event():
    bot = SimpleNamespace(
        hash='retryprobe',
        id=102080146,
        platform={'sdk': 'qqGuildv2_link', 'model': 'public'},
        post_info=SimpleNamespace(access_token='probe-token', port=0, type='post'),
        debug_mode=False,
    )
    logs = []

    def log_func(level, message, segment=None):
        logs.append((level, message))

    event = SimpleNamespace(
        log_func=log_func,
        bot_info=bot,
        plugin_info={'name': 'probe-plugin', 'func_type': 'group_message'},
        getBotIDStr=lambda: 'qqGuild|102080146',
        data=SimpleNamespace(namespace='probe', event='probe'),
        active=True,
    )
    event.logs = logs
    return event


class FakeAPI(object):
    def __init__(self, responses, msg_type=0, content=None, markdown=None, keyboard=None):
        self.data = SimpleNamespace(
            msg_type=msg_type,
            content=content,
            markdown=markdown,
            keyboard=keyboard,
            media=None,
            msg_id=None,
            event_id=None,
            msg_seq=None,
            message_reference=None,
        )
        self.metadata = SimpleNamespace()
        self.responses = list(responses)
        self.calls = []
        self.res = None
        self.res_code = None

    def do_api(self):
        self.calls.append({
            'msg_type': self.data.msg_type,
            'content': self.data.content,
            'msg_seq': self.data.msg_seq,
        })
        code, body = self.responses.pop(0)
        self.res_code = code
        self.res = body


def run_send(
    event,
    api,
    chat_type='qq_group',
    chat_id='CHATRETRY',
    msg_id=None,
    event_id=None,
    allow_length_fallback=True
):
    return SDK.event_action._send_qq_api(
        event, api, chat_type, chat_id, msg_id, event_id, False, allow_length_fallback
    )


def test_length_error_retries_once_and_succeeds():
    event = make_event()
    api = FakeAPI([(400, LENGTH_BODY), (200, OK_BODY)], content='短消息')
    result = run_send(event, api)
    assert len(api.calls) == 2
    assert result['active'] is True
    assert result['data']['send_retry']['attempted'] is True
    assert result['data']['send_retry']['first_error_code'] == 40054007
    assert any('重试一次后成功' in message for _, message in event.logs)


def test_server_error_code_retries_once():
    event = make_event()
    api = FakeAPI([(400, SERVER_BODY), (200, OK_BODY)], content='短消息')
    result = run_send(event, api)
    assert len(api.calls) == 2
    assert result['active'] is True


def test_ambiguous_failure_is_never_retried():
    event = make_event()
    # 没有状态码（超时/连接中断）时，消息可能已经发出去了，不能重发
    api = FakeAPI([(None, '')], content='短消息')
    result = run_send(event, api)
    assert len(api.calls) == 1
    assert result['active'] is False


def test_server_5xx_is_never_retried():
    event = make_event()
    api = FakeAPI([(500, '{"message":"内部错误","code":50000001}')], content='短消息')
    result = run_send(event, api)
    assert len(api.calls) == 1
    assert result['active'] is False


def test_banned_error_is_not_retried():
    event = make_event()
    api = FakeAPI([(400, BANNED_BODY)], content='短消息')
    result = run_send(event, api)
    assert len(api.calls) == 1
    assert result['active'] is False


def test_duplicate_error_is_not_retried_and_stays_failed():
    # 40054005 只能说明相同 msg_seq 的上一条被平台处理过，无法确认内容一致
    # （事件重放时回复内容可能已经重新生成），所以既不重试也不谎报成功。
    event = make_event()
    api = FakeAPI([(400, DUP_BODY)], content='短消息')
    result = run_send(event, api)
    assert len(api.calls) == 1
    assert result['active'] is False


def test_retry_uses_new_msg_seq_for_passive_reply():
    event = make_event()
    api = FakeAPI([(400, LENGTH_BODY), (200, OK_BODY)], content='短消息')
    result = run_send(event, api, chat_id='CHATSEQ', msg_id='MSG-ID-SEQ')
    assert len(api.calls) == 2
    assert api.calls[0]['msg_seq'] is not None
    assert api.calls[1]['msg_seq'] is not None
    assert api.calls[1]['msg_seq'] != api.calls[0]['msg_seq']
    assert result['active'] is True


def test_length_failure_falls_back_to_split_text():
    event = make_event()
    text = '测' * 2000  # 6000 字节，远超单条 900 字节上限
    api = FakeAPI(
        [(400, LENGTH_BODY), (400, LENGTH_BODY)] + [(200, OK_BODY)] * 4,
        content=text,
    )
    result = run_send(event, api)
    # 1 次首发 + 1 次重试 + 最多 4 段降级
    assert len(api.calls) == 6
    sent_parts = [call['content'] for call in api.calls[2:]]
    # 每段都不超过上限，避免再被平台整段拒掉
    assert all(len(part.encode('utf-8')) <= 900 for part in sent_parts)
    assert text.startswith(''.join(sent_parts))
    fallback = result['data']['send_length_fallback']
    assert fallback['parts'] == 4
    assert fallback['dropped_bytes'] > 0
    assert result['active'] is True


def test_markdown_length_failure_falls_back_to_plain_text():
    event = make_event()
    markdown = (
        '# 状态卡\n'
        '**攻击** 60 / **闪避** 45\n'
        '![封面](https://example.invalid/cover.png)\n'
        '| 项目 | 值 |\n'
        '| --- | --- |\n'
        '| HP | 12 |\n'
    )
    api = FakeAPI(
        [(400, LENGTH_BODY), (400, LONG_BODY), (200, OK_BODY)],
        msg_type=2,
        markdown={'content': markdown},
    )
    result = run_send(event, api)
    assert result['active'] is True
    assert api.calls[2]['msg_type'] == 0
    plain = api.calls[2]['content']
    assert '# 状态卡' not in plain
    assert '**' not in plain
    assert '![' not in plain
    assert '---' not in plain
    assert '状态卡' in plain
    assert '攻击' in plain
    assert result['data']['send_length_fallback']['reason'] == 'markdown_to_text'


def test_markdown_with_local_images_skips_length_fallback():
    event = make_event()
    api = FakeAPI(
        [(400, LENGTH_BODY), (400, LENGTH_BODY)],
        msg_type=2,
        markdown={'content': '# 带图卡片\n![图](qqbot-media://image/v1/xxx)'},
    )
    # 带本地图片时由图文回退处理，这里不能把 markdown 转成纯文本（那会丢图）
    result = run_send(event, api, allow_length_fallback=False)
    assert len(api.calls) == 2
    assert result['active'] is False


def test_markdown_with_keyboard_degrades_and_drops_keyboard():
    event = make_event()
    api = FakeAPI(
        [(400, LENGTH_BODY), (400, LENGTH_BODY), (200, OK_BODY)],
        msg_type=2,
        markdown={'content': '# 带按钮卡片'},
        keyboard={'content': {'rows': []}},
    )
    result = run_send(event, api)
    # 按钮丢了也比整条回复发不出去好；降级后必须清掉 keyboard，否则会带残值发送
    assert len(api.calls) == 3
    assert api.calls[2]['msg_type'] == 0
    assert api.data.keyboard is None
    assert result['active'] is True
    assert result['data']['send_length_fallback']['keyboard_dropped'] is True


@pytest.mark.parametrize('chat_type, max_parts', [
    ('qq_group', 3),
    ('qq_private', 2),
])
def test_passive_fallback_caps_parts_by_reply_quota(chat_type, max_parts):
    # 群聊一个 msg_id 只允许 5 次回复、私聊 4 次：首发 + 重试之后只剩 3 / 2 段，
    # 拆多了会被平台直接拒掉，等于白丢内容。
    event = make_event()
    text = '测' * 2000
    responses = [(400, LENGTH_BODY), (400, LENGTH_BODY)]
    responses += [(200, OK_BODY)] * max_parts
    api = FakeAPI(responses, content=text)
    result = run_send(event, api, chat_type=chat_type, chat_id='CHATCAP', msg_id='MSG-ID-CAP')
    assert len(api.calls) == 2 + max_parts
    sent_parts = [call['content'] for call in api.calls[2:]]
    assert all(len(part.encode('utf-8')) <= 900 for part in sent_parts)
    assert result['data']['send_length_fallback']['parts'] == max_parts
    assert result['data']['send_length_fallback']['dropped_bytes'] > 0


def test_event_id_reply_reserves_quota_for_retry_and_parts():
    # event_id 通道（没有 msg_id）同样要按次占用额度，否则分段会被平台拒掉。
    event = make_event()
    api = FakeAPI(
        [(400, LENGTH_BODY), (400, LENGTH_BODY), (200, OK_BODY), (200, OK_BODY)],
        content='测' * 400,
    )
    result = run_send(
        event,
        api,
        chat_type='qq_private',
        chat_id='CHATEVENT',
        msg_id=None,
        event_id='EVENT-ID-1',
    )
    # 私聊 event_id 只允许 4 次：首发 + 重试 + 2 段，正好用满
    assert len(api.calls) == 4
    assert result['active'] is True


def test_split_text_keeps_utf8_boundaries():
    text = '小芙' * 700
    parts = SDK.event_action._split_qq_text_by_bytes(text)
    assert len(parts) <= 4
    assert text.startswith(''.join(parts))
    for part in parts:
        assert len(part.encode('utf-8')) <= SDK.qqSendLengthFallbackMaxBytes
        part.encode('utf-8').decode('utf-8')


def test_mention_tag_is_never_split():
    tag = '<qqbot-at-user id="ABCDEF0123456789" />'
    text = tag + '测' * 700
    parts = SDK.event_action._split_qq_text_by_bytes(text)
    joined = ''.join(parts)
    assert joined.startswith(tag)
    assert joined.count('<qqbot-at-user') == joined.count('/>')


def test_short_text_is_not_split():
    parts = SDK.event_action._split_qq_text_by_bytes('短消息')
    assert parts == ['短消息']


def test_length_fallback_switches_to_active_when_quota_exhausted():
    # 同一个 msg_id 之前已经回过消息、被动额度只剩 2 次时，首发 + 重试用满额度，
    # 后面的分段要自动改发主动消息，而不是把剩下的内容丢掉。
    event = make_event()
    msg_id = 'MSG-ID-TAIL'
    chat_id = 'CHATTAIL'
    dummy = FakeAPI([], content='预热')
    for _ in range(2):
        consumed = SDK.event_action._prepare_qq_passive_message(
            event, dummy, 'qq_private', chat_id, msg_id, None
        )
        assert consumed is None
    api = FakeAPI(
        [(400, LENGTH_BODY), (400, LENGTH_BODY), (200, OK_BODY), (200, OK_BODY)],
        content='测' * 400,
    )
    result = run_send(event, api, chat_type='qq_private', chat_id=chat_id, msg_id=msg_id)
    assert len(api.calls) == 4
    # 后两条已经改成主动发送：没有 msg_seq，且结果里记下了 passive_fallbacks
    assert api.calls[2]['msg_seq'] is None
    assert api.calls[3]['msg_seq'] is None
    assert result['active'] is True
    assert result['data']['send_length_fallback']['active_parts'] == 2
    assert len(result['data']['passive_fallbacks']) == 1
    assert result['data']['passive_fallbacks'][0]['reason'] == 'length_fallback_quota_exhausted'
