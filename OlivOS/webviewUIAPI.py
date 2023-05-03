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
import os

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
        releaseDir('./data')
        releaseDir('./data/webview')
        releaseDir('./data/webview/%s' % self.Proc_name)
        if self.UIData['url'] != None:
            webview.create_window(
                title=self.UIData['title'],
                url=self.UIData['url'],
                background_color='#00A0EA'
            )
            webview.start(
                private_mode=False,
                storage_path='./data/webview/%s' % self.Proc_name
            )

        # 发送并等待结束
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet('stop', self.Proc_name),
                block=False
            )
        else:
            pass

def sendOpenWebviewPage(
    control_queue,
    name:str,
    title:str,
    url:str
):
    if control_queue is not None:
        control_queue.put(
            OlivOS.API.Control.packet(
                'init_type_open_webview_page',
                {
                    'target': {
                        'action': 'init',
                        'name': name
                    },
                    'data': {
                        'title': title,
                        'url': url
                    }
                }
            ),
            block=False
        )


def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
