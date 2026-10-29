# -*- encoding: utf-8 -*-
r'''
@File      :   tests/test_qqguildv2_webhook_release.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   webhook 组件热停止时释放监听端口
'''

from unittest.mock import Mock

from OlivOS.adapter.qqGuild import qqGuildv2WebhookServerAPI as webhook_api


def make_server():
    return webhook_api.server(
        Proc_name='probe',
        Flask_namespace='probe',
        Flask_server_methods=['POST'],
        Flask_host='127.0.0.1',
        Flask_port=0,
    )


def test_on_terminate_stops_listen_server():
    # 热重载会 terminate 旧组件再重建；不 stop 监听对象的话端口一直占着，
    # 新组件 bind 失败，表现为「热重载不生效、重启进程才正常」。
    server = make_server()
    fake_listen = Mock()
    server._webhook_server = fake_listen

    server.on_terminate()

    fake_listen.stop.assert_called_once_with()
    assert server._webhook_server is None
    assert server._webhook_stopped.is_set()
    assert server._webhook_last_ready.value == 0.0


def test_on_terminate_without_listen_server_is_safe():
    server = make_server()

    server.on_terminate()

    assert server._webhook_stopped.is_set()
    assert server._webhook_server is None
