# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_qqguildv2_group_at_all.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   群聊 @全体成员（<qqbot-at-everyone />）分片测试
'''

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common
from OlivOS.adapter.qqGuild import qqGuildv2SDKGroup as group_sdk

AT_ALL_TAG = '<qqbot-at-everyone />'


def group_chunks(monkeypatch, parts, flag_direct=False):
    """把消息段丢进群聊分片函数，返回合并后的正文。"""
    monkeypatch.setattr(group_sdk, 'event_action', common.event_action)
    message = OlivOS.messageAPI.Message_templet('olivos_para', parts)
    chunks = group_sdk.event_action_group._get_qq_message_send_chunks(
        message,
        flag_direct=flag_direct
    )
    return ''.join(text for text, _media in chunks)


def build_parts():
    return [
        OlivOS.messageAPI.PARA.text('集合啦 '),
        OlivOS.messageAPI.PARA.at('all'),
        OlivOS.messageAPI.PARA.text(' 有事说')
    ]


class TestGroupAtAll:
    def test_group_text_keeps_at_everyone_tag(self, monkeypatch):
        # 2026-10-26 起群聊文本消息支持 <qqbot-at-everyone />，不再被吞掉。
        content = group_chunks(monkeypatch, build_parts())
        assert AT_ALL_TAG in content
        assert content == '集合啦 %s 有事说' % AT_ALL_TAG

    def test_private_text_drops_at_everyone(self, monkeypatch):
        # 私聊没有 @全体 语义，保持关闭，避免发出平台不认的标签。
        content = group_chunks(monkeypatch, build_parts(), flag_direct=True)
        assert AT_ALL_TAG not in content
        assert content == '集合啦  有事说'

    def test_member_at_unaffected(self, monkeypatch):
        parts = [
            OlivOS.messageAPI.PARA.text('看 '),
            OlivOS.messageAPI.PARA.at('ABCDEF'),
            OlivOS.messageAPI.PARA.text(' 这条')
        ]
        group_content = group_chunks(monkeypatch, parts)
        assert '<qqbot-at-user id="ABCDEF" />' in group_content
        private_content = group_chunks(monkeypatch, parts, flag_direct=True)
        assert '<qqbot-at-user id="ABCDEF" />' in private_content
