"""QQ 群聊/单聊 Markdown 卡片的空行占位行为。

QQ 的 Markdown 卡片不渲染空行：正文里连续两个换行只会显示成一次换行，
段落之间要留一行空白必须用零宽空格（U+200B）占位。这里覆盖占位规则本身，
以及图文混发、直连 markdown 接口、长度降级转纯文本三条链路。
"""

from types import SimpleNamespace
from unittest.mock import Mock

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


def test_code_block_blank_lines_are_preserved():
    text = '```' + NL + 'A' + NL * 2 + 'B' + NL + '```' + NL + 'C'

    assert common.markdown_tag.normalize_blank_lines(text) == text


def test_trailing_blank_lines_are_not_padded():
    text = 'A' + NL * 2

    assert common.markdown_tag.normalize_blank_lines(text) == text


def test_crlf_input_is_normalized():
    text = 'A' + CRLF * 2 + 'B'

    assert common.markdown_tag.normalize_blank_lines(text) == 'A' + NL + ZWSP + NL + 'B'


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
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('第一段' + NL * 2 + '第二段'),
        OlivOS.messageAPI.PARA.image('images/a.png')
    ])

    result, error = SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', message
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


def test_blank_line_after_quote_is_untouched():
    """引用块后面的空行不能换占位，否则手机端会把正文吞进引用框。"""
    text = '> kp_Desom hp12/12 san0/99 dex65' + NL * 2 + '收到！已激活！'

    assert common.markdown_tag.normalize_blank_lines(text) == text


def test_blank_line_before_quote_is_untouched():
    text = '普通段落' + NL * 2 + '> 引用一行'

    assert common.markdown_tag.normalize_blank_lines(text) == text


def test_blank_line_after_list_and_fence_is_untouched():
    listed = '- 第一项' + NL * 2 + '正文'
    fenced = '```' + NL + 'code' + NL + '```' + NL * 2 + '正文'

    assert common.markdown_tag.normalize_blank_lines(listed) == listed
    assert common.markdown_tag.normalize_blank_lines(fenced) == fenced


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


def test_blank_line_between_table_and_text_is_padded():
    """表格和正文之间的空行同样要占位，否则正文会变成表格新行。"""
    after = '| a | b |' + NL + '| - | - |' + NL * 2 + 'D1'
    before = 'D0' + NL * 2 + '| a | b |' + NL + '| - | - |'

    assert common.markdown_tag.normalize_blank_lines(after) == (
        '| a | b |' + NL + '| - | - |' + NL + ZWSP + NL + 'D1'
    )
    assert common.markdown_tag.normalize_blank_lines(before) == (
        'D0' + NL + ZWSP + NL + '| a | b |' + NL + '| - | - |'
    )


def test_blank_line_after_rule_is_untouched():
    rule = '正文' + NL + '---' + NL * 2 + '下一段'

    assert common.markdown_tag.normalize_blank_lines(rule) == rule


def test_blank_line_after_heading_is_untouched():
    text = '# 标题' + NL * 2 + '正文'

    assert common.markdown_tag.normalize_blank_lines(text) == text


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


def test_plain_text_fallback_drops_placeholder():
    content = 'A' + NL + ZWSP + NL + 'B'

    assert SDK.event_action._qq_markdown_to_plain_text(content) == 'A' + NL + NL + 'B'


def _joined_text(message):
    return ''.join(
        segment.data['text']
        for segment in message.data
        if isinstance(segment, OlivOS.messageAPI.PARA.text)
    )


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
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('第一段' + NL * 2 + '第二段'),
        OlivOS.messageAPI.PARA.image('images/a.png')
    ])

    SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', message
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


def test_log_preview_strips_placeholder():
    """日志里不显示零宽字符，换行仍以字面量 \n 呈现。"""
    preview = SDK.event_action._get_qq_log_text_preview('A' + NL + ZWSP + NL + 'B')

    assert ZWSP not in preview
    assert preview == 'A' + chr(92) + 'n' + chr(92) + 'n' + 'B'
