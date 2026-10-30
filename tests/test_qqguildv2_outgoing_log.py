# -*- encoding: utf-8 -*-
r'''
@File      :   tests/test_qqguildv2_outgoing_log.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   发送日志（callbackLogger）要带上实际发出的正文
'''

import inspect
from types import SimpleNamespace

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common


class Res(dict):
    """模拟 universal_result：callbackLogger 只对 dict 子类输出字段。"""


def make_event():
    bot = SimpleNamespace(
        hash='probehash',
        id=102080146,
        platform={'sdk': 'qqGuildv2_link', 'model': 'public'},
        post_info=SimpleNamespace(access_token='probe-token', port=0, type='post'),
        debug_mode=False,
    )
    return SimpleNamespace(
        log_func=lambda level, message, segment=None: None,
        bot_info=bot,
        plugin_info={'name': 'probe-plugin', 'func_type': 'group_message'},
        getBotIDStr=lambda: 'qqGuild|102080146',
        data=SimpleNamespace(namespace='probe', event='probe'),
        active=True,
    )


def test_markdown_content_is_attached_for_log(monkeypatch):
    event = make_event()
    monkeypatch.setattr(common.event_action, '_send_qq_api', staticmethod(
        lambda *args, **kwargs: {'active': True, 'data': {
            'chat_type': 'qq_group', 'chat_id': 'CHATID', 'message_id': 'MSGID', 'http_status': 200}}))
    monkeypatch.setattr(common.API, 'sendQQMessage', staticmethod(
        lambda bot: SimpleNamespace(data=SimpleNamespace(), metadata=SimpleNamespace(),
                                    res='{"id":"MSGID"}', res_code=200)))

    res_data = common.event_action.create_markdown_message(
        event, 'qq_group', 'CHATID', {'content': '**标题**\n第一行\n第二行'}, msg_id='MSGID')

    # 正文写进返回值，callbackLogger 才能以 content 字段输出「到底发了什么」
    assert res_data['data']['content'] == '**标题**\\n第一行\\n第二行'


def test_text_content_survives_result_merge(monkeypatch):
    logs = []
    event = make_event()
    event.log_func = lambda level, message, segment=None: logs.append((level, message))
    monkeypatch.setattr(common.event_action, '_send_qq_api', staticmethod(
        lambda *args, **kwargs: Res({'active': True, 'data': {
            'chat_type': 'qq_group', 'chat_id': 'CHATID',
            'message_ids': ['MSGID'], 'http_status': 200}})))
    monkeypatch.setattr(common.API, 'sendQQMessage', staticmethod(
        lambda bot: SimpleNamespace(data=SimpleNamespace(), metadata=SimpleNamespace(),
                                    res='{"id":"MSGID"}', res_code=200)))
    iface = SimpleNamespace(event=event)
    message = OlivOS.messageAPI.Message_templet(
        'olivos_para', [OlivOS.messageAPI.PARA.text('第一行文本\n第二行文本')])

    res_data = common.inde_interface.send_qq_message(
        iface, 'qq_group', 'CHATID', message, reply_msg_id='MSGID')

    # 分片结果合并后正文不能丢，日志那一行要带 content(...)
    assert res_data['data']['content'] == '第一行文本\\n第二行文本'
    assert any('content(第一行文本\\n第二行文本)' in text for level, text in logs)


def test_log_val_list_carries_content():
    # 三个发送入口的 callbackLogger 都必须点名 content 字段
    source = inspect.getsource(common.inde_interface)
    for log_name in ['qqGuildv2:send_message', 'qqGuildv2:send_qq_message',
                     'qqGuildv2:create_markdown_message',
                     'qqGuildv2:create_card_message']:
        index = source.index(log_name)
        assert "'content'" in source[index:index + 220], \
            '%s 的 val_list 缺少 content' % log_name


def test_long_content_is_not_truncated():
    # 日志要能看到完整正文：不截断、不加省略标记
    preview = common.event_action._get_qq_log_text_preview('行\n' * 400)

    assert preview == '行\\n' * 400
    assert '（共' not in preview


def test_empty_content_has_no_preview():
    assert common.event_action._get_qq_log_text_preview(None) is None
    assert common.event_action._get_qq_log_text_preview('   ') is None
