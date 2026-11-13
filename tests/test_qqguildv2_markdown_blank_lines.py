# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_markdown_blank_lines.py
@Author    :   Desom-fu
@Contact   :   desom233@outlook.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   QQ 群聊/单聊 Markdown 卡片的空行占位规则与三条回退链路
'''

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common


SDK = OlivOS.qqGuildv2SDK
NL = chr(10)          # 换行
CRLF = chr(13) + chr(10)
ZWSP = chr(0x200b)    # 空行占位


def _target_event():
    bot = OlivOS.API.bot_info_T(
        id=10001,
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='public'
    )
    return SimpleNamespace(bot_info=bot, log_func=None)


def _joined_text(message):
    return ''.join(
        segment.data['text']
        for segment in message.data
        if isinstance(segment, OlivOS.messageAPI.PARA.text)
    )


def _mixed_message():
    return OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('第一段' + NL * 2 + '第二段'),
        OlivOS.messageAPI.PARA.image('images/a.png')
    ])


# ---------------------------------------------------------------- 基本占位

def test_blank_line_gets_zero_width_placeholder():
    text = 'A' + NL * 2 + 'B'

    assert common.markdown_tag.normalize_blank_lines(text) == 'A' + NL + ZWSP + NL + 'B'


def test_single_line_breaks_are_untouched():
    text = 'A' + NL + 'B' + NL + 'C'

    assert common.markdown_tag.normalize_blank_lines(text) == text


def test_consecutive_blank_lines_all_get_placeholders():
    text = 'A' + NL * 3 + 'B'

    assert common.markdown_tag.normalize_blank_lines(text) == (
        'A' + NL + ZWSP + NL + ZWSP + NL + 'B'
    )


def test_placeholder_is_idempotent():
    once = common.markdown_tag.normalize_blank_lines('A' + NL * 2 + 'B')

    assert common.markdown_tag.normalize_blank_lines(once) == once


def test_trailing_blank_lines_are_not_padded():
    text = 'A' + NL * 2

    assert common.markdown_tag.normalize_blank_lines(text) == text


def test_crlf_input_is_normalized():
    text = 'A' + CRLF * 2 + 'B'

    assert common.markdown_tag.normalize_blank_lines(text) == 'A' + NL + ZWSP + NL + 'B'


# ---------------------------------------------------------------- 代码围栏

def test_code_block_blank_lines_are_preserved():
    text = '```' + NL + 'A' + NL * 2 + 'B' + NL + '```' + NL + 'C'

    assert common.markdown_tag.normalize_blank_lines(text) == text


def test_fence_with_info_string_does_not_close_code_block():
    """围栏收尾行不能带信息串：```python 只是代码内容，不是闭合。"""
    text = (
        '```' + NL + 'A' + NL + '```python' + NL * 2 + 'B'
        + NL + '```' + NL + 'C'
    )

    assert common.markdown_tag.normalize_blank_lines(text) == text


def test_shorter_fence_does_not_close_longer_fence():
    """四反引号开的围栏，三个反引号不足以闭合，里面的空行不算正文。"""
    text = '````' + NL + 'A' + NL + '```' + NL * 2 + 'B' + NL + '````'

    assert common.markdown_tag.normalize_blank_lines(text) == text


# ---------------------------------------------------------------- 块级元素

@pytest.mark.parametrize('text', [
    '> kp_Desom hp12/12 san0/99 dex65' + NL * 2 + '收到！已激活！',
    '普通段落' + NL * 2 + '> 引用一行',
    '- 第一项' + NL * 2 + '正文',
    '```' + NL + 'code' + NL + '```' + NL * 2 + '正文',
    '正文' + NL + '---' + NL * 2 + '下一段',
    '# 标题' + NL * 2 + '正文',
    '##' + NL * 2 + '正文',
])
def test_blank_line_next_to_block_element_is_untouched(text):
    """引用/列表/围栏/分割线/标题旁边的空行不补占位（补了会吞正文）。"""
    assert common.markdown_tag.normalize_blank_lines(text) == text


def test_mixed_thematic_markers_are_not_rule():
    """`-*-` 不是分割线（分割线要求整行同一字符），旁边的空行照常占位。"""
    text = '正文' + NL + '-*-' + NL * 2 + '下一段'

    assert common.markdown_tag.normalize_blank_lines(text) == (
        '正文' + NL + '-*-' + NL + ZWSP + NL + '下一段'
    )


def test_hash_topic_line_is_not_heading():
    """`#话题` 不是 ATX 标题，它旁边的空行照样要占位。"""
    text = '正文' + NL * 2 + '#今日话题'

    assert common.markdown_tag.normalize_blank_lines(text) == (
        '正文' + NL + ZWSP + NL + '#今日话题'
    )


def test_blank_line_between_plain_paragraphs_still_padded():
    text = '普通一段' + NL * 2 + '普通二段'

    assert common.markdown_tag.normalize_blank_lines(text) == (
        '普通一段' + NL + ZWSP + NL + '普通二段'
    )


# ---------------------------------------------------------------- 表格边界

def test_blank_line_between_two_tables_is_padded():
    """表格靠空行定边界：空行被 QQ 吞掉，两张表会连成一张。

    实测现象：后一张表的 `| --- |` 变成前一张表的数据行，
    表格后面的正文也会被吸进表格当行。
    """
    text = (
        '| a | b |' + NL + '| - | - |' + NL + '| 1 | 2 |' + NL * 2
        + '| c | d |' + NL + '| - | - |' + NL + '| 3 | 4 |'
    )
    expected = (
        '| a | b |' + NL + '| - | - |' + NL + '| 1 | 2 |' + NL + ZWSP + NL
        + '| c | d |' + NL + '| - | - |' + NL + '| 3 | 4 |'
    )

    assert common.markdown_tag.normalize_blank_lines(text) == expected


def test_blank_line_between_table_and_following_text_is_padded():
    text = '| a | b |' + NL + '| - | - |' + NL * 2 + 'D1'

    assert common.markdown_tag.normalize_blank_lines(text) == (
        '| a | b |' + NL + '| - | - |' + NL + ZWSP + NL + 'D1'
    )


def test_blank_line_between_heading_text_and_table_is_padded():
    text = 'D0' + NL * 2 + '| a | b |' + NL + '| - | - |'

    assert common.markdown_tag.normalize_blank_lines(text) == (
        'D0' + NL + ZWSP + NL + '| a | b |' + NL + '| - | - |'
    )


def test_table_without_outer_pipe_keeps_boundary():
    """没有外层竖线的表格（GFM 合法写法）同样要保住边界。"""
    text = 'a | b' + NL + '--- | ---' + NL + '1 | 2' + NL * 2 + '结论'

    assert common.markdown_tag.normalize_blank_lines(text) == (
        'a | b' + NL + '--- | ---' + NL + '1 | 2' + NL + ZWSP + NL + '结论'
    )


def test_pipe_text_is_not_table_without_separator_row():
    """普通文本里带竖线、又没有分隔行，不能当成表格。"""
    text = 'E | mc2' + NL * 2 + '普通段落'

    assert common.markdown_tag.normalize_blank_lines(text) == (
        'E | mc2' + NL + ZWSP + NL + '普通段落'
    )


# ---------------------------------------------------------------- 发送链路

def test_mixed_message_sends_padded_blank_line(monkeypatch):
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=(
            {'image_0': '![image #20px #10px](qqbot-media://image/v1/t)'},
            [],
            None
        ))
    )
    monkeypatch.setattr(SDK.event_action, '_delete_markdown_images', Mock())
    send = Mock(return_value={'active': True, 'data': {'http_status': 200}})
    monkeypatch.setattr(SDK.event_action, 'create_markdown_message', send)

    result, error = SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', _mixed_message()
    )

    assert result['active'] is True
    assert error is None
    content = send.call_args.args[3]['content']
    assert content.startswith('第一段' + NL + ZWSP + NL + '第二段')
    assert NL + NL not in content


def test_create_markdown_message_pads_blank_lines(monkeypatch):
    target = _target_event()
    api = Mock(return_value={'active': True, 'data': {'http_status': 200}})
    monkeypatch.setattr(SDK.event_action, '_send_qq_api', api)

    SDK.event_action.create_markdown_message(
        target,
        'qq_group',
        'group',
        {'content': '标题' + NL * 2 + '正文'},
        force_active=True
    )

    sent = api.call_args.args[1]
    assert sent.data.markdown['content'] == '标题' + NL + ZWSP + NL + '正文'


# ---------------------------------------------------------------- 回退与日志

def test_plain_text_fallback_drops_placeholder():
    content = 'A' + NL + ZWSP + NL + 'B'

    assert SDK.event_action._qq_markdown_to_plain_text(content) == 'A' + NL + NL + 'B'


def test_plain_text_fallback_keeps_authored_zero_width_space():
    """调用方自己写的零宽字符不是占位，降级时要原样保留。"""
    content = 'He' + ZWSP + 'llo' + NL + ZWSP + NL + 'B'

    assert SDK.event_action._qq_markdown_to_plain_text(content) == (
        'He' + ZWSP + 'llo' + NL + NL + 'B'
    )


def test_log_preview_strips_placeholder():
    """日志里不显示占位字符，换行仍以字面量 \\n 呈现。"""
    preview = SDK.event_action._get_qq_log_text_preview('A' + NL + ZWSP + NL + 'B')

    assert ZWSP not in preview
    assert preview == 'A' + chr(92) + 'n' + chr(92) + 'n' + 'B'


def test_log_preview_keeps_authored_zero_width_space():
    preview = SDK.event_action._get_qq_log_text_preview('He' + ZWSP + 'llo')

    assert ZWSP in preview


def test_rejected_mixed_markdown_fallback_has_no_placeholder(monkeypatch):
    """图文混发被平台拒掉时回退发原消息，原消息里不能带占位字符。"""
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=(
            {'image_0': '![image #20px #10px](qqbot-media://image/v1/t)'},
            [],
            None
        ))
    )
    monkeypatch.setattr(SDK.event_action, '_delete_markdown_images', Mock())
    monkeypatch.setattr(
        SDK.event_action,
        'create_markdown_message',
        Mock(return_value={'active': False, 'data': {'http_status': 400}})
    )
    fallback = Mock(return_value={'active': True, 'data': {}})
    monkeypatch.setattr(SDK.event_action, 'send_qq_msg', fallback)

    SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', _mixed_message()
    )

    assert fallback.called
    assert ZWSP not in _joined_text(fallback.call_args.args[2])


def test_upload_failure_fallback_has_no_placeholder(monkeypatch):
    """图片素材上传失败时回退发原始 markdown 正文，同样不能带占位。"""
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=(None, [], 'cover: 图片超过 10MB 素材上限'))
    )
    monkeypatch.setattr(SDK.event_action, '_delete_markdown_images', Mock())
    fallback = Mock(return_value={'active': True, 'data': {}})
    monkeypatch.setattr(SDK.event_action, 'send_qq_msg', fallback)

    SDK.event_action.create_markdown_message(
        _target_event(),
        'qq_group',
        'group',
        {'content': '标题' + NL * 2 + '正文{{cover}}'},
        local_images={'cover': 'cover.png'}
    )

    assert fallback.called
    assert ZWSP not in _joined_text(fallback.call_args.args[2])
