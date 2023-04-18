# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/webviewUIAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import OlivOS

import webview
import time

class page(OlivOS.API.Proc_templet):
    def __init__(
            self,
            Proc_name='webview_page',
            scan_interval=0.001,
            dead_interval=1,
            rx_queue=None,
            tx_queue=None,
            logger_proc=None,
            control_queue=None,
            title='OlivOS Page',
            url=None
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='webview_page',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            control_queue=control_queue,
            logger_proc=logger_proc
        )
        self.UIObject = {}
        self.UIData = {
            'title': title,
            'url': url
        }

    def run(self):
        if self.UIData['url'] != None:
            webview.create_window(self.UIData['title'], self.UIData['url'])
            webview.start()

        # 发送并等待结束
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet('stop', self.Proc_name),
                block=False
            )
        else:
            pass
