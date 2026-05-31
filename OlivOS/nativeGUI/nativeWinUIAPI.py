# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/nativeWinUIAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

import OlivOS

import base64
import os
import pystray
import tkinter
import tkinter.messagebox
import re
import datetime
import webbrowser
import platform

from PIL import Image
from PIL import ImageTk

from tkinter import ttk

dictColorContext = {
    'color_001': '#00A0EA',
    'color_002': '#BBE9FF',
    'color_003': '#40C3FF',
    'color_004': '#FFFFFF',
    'color_005': '#000000',
    'color_006': '#80D7FF'
}

gTerminalDataMax = 128
gTerminalDataStep = 8


class dock(OlivOS.API.Proc_templet):
    def __init__(
            self,
            Proc_name='native_nativeWinUI',
            scan_interval=0.001,
            dead_interval=1,
            rx_queue=None,
            tx_queue=None,
            logger_proc=None,
            control_queue=None,
            bot_info_dict=None
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='nativeWinUI',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            control_queue=control_queue,
            logger_proc=logger_proc
        )
        self.Proc_config['ready_for_restart'] = False
        self.bot_info = bot_info_dict
        self.busy = False
        self.UIObject = {}
        self.UIData = {}
        self.UIObject['root_window_on'] = False
        self.UIObject['root_shallow'] = None
        self.UIObject['root_OlivOS_terminal'] = None
        self.UIObject['root_OlivOS_terminal_data'] = []
        self.UIObject['root_OlivOS_terminal_data_max'] = gTerminalDataMax
        self.UIObject['root_gocqhttp_terminal'] = {}
        self.UIObject['root_gocqhttp_terminal_data'] = {}
        self.UIObject['root_gocqhttp_terminal_data_max'] = gTerminalDataMax
        self.UIObject['root_walleq_terminal'] = {}
        self.UIObject['root_walleq_terminal_data'] = {}
        self.UIObject['root_walleq_terminal_data_max'] = gTerminalDataMax
        self.UIObject['root_cwcb_terminal'] = {}
        self.UIObject['root_cwcb_terminal_data'] = {}
        self.UIObject['root_cwcb_terminal_data_max'] = gTerminalDataMax
        self.UIObject['root_opqbot_terminal'] = {}
        self.UIObject['root_opqbot_terminal_data'] = {}
        self.UIObject['root_opqbot_terminal_data_max'] = gTerminalDataMax
        self.UIObject['root_napcat_terminal'] = {}
        self.UIObject['root_napcat_terminal_data'] = {}
        self.UIObject['root_napcat_terminal_data_max'] = gTerminalDataMax
        self.UIObject['root_virtual_terminal_terminal'] = {}
        self.UIObject['root_virtual_terminal_terminal_data'] = {}
        self.UIObject['root_virtual_terminal_terminal_data_max'] = gTerminalDataMax
        self.UIObject['root_qrcode_window'] = {}
        self.UIObject['root_qrcode_window_thread'] = {}
        self.UIObject['root_qrcode_window_enable'] = False
        self.UIObject['root_plugin_edit'] = {}
        self.UIObject['root_plugin_edit_enable'] = False
        self.UIObject['root_plugin_edit_count'] = 0
        self.UIObject['flag_have_update'] = False
        self.UIObject['flag_first_account_list_update'] = True
        self.UIData['shallow_plugin_menu_list'] = None
        self.UIData['shallow_gocqhttp_menu_list'] = None
        self.UIData['shallow_walleq_menu_list'] = None
        self.UIData['shallow_cwcb_menu_list'] = None
        self.UIData['shallow_opqbot_menu_list'] = None
        self.UIData['shallow_napcat_menu_list'] = None
        self.UIData['shallow_virtual_terminal_menu_list'] = None
        self.UIData['shallow_account_menu_list'] = None
        self.UIData['shallow_plugin_data_dict'] = None
        self.UIData['shallow_account_list'] = []
        self.UIData['shallow_account_list_new'] = []
        self.updateShallowMenuList()

    def run(self):
        self.UIObject['main_tk'] = tkinter.Tk()
        self.UIObject['main_tk'].withdraw()
        self.UIObject['main_tk'].iconbitmap('./resource/tmp_favoricon.ico')
        self.startShallowSend()
        self.process_msg()
        self.UIObject['main_tk'].mainloop()

    def on_control_rx(self, packet):
        if type(packet) is OlivOS.API.Control.packet:
            if 'send' == packet.action:
                if (
                    type(packet.key) is dict
                    and 'data' in packet.key
                    and type(packet.key['data'])
                    and 'action' in packet.key['data']
                ):
                    if 'account_update' == packet.key['data']['action']:
                        if (
                            'data' in packet.key['data']
                            and type(packet.key['data']['data']) is dict
                        ):
                            self.bot_info = packet.key['data']['data']
                        self.UIData['shallow_napcat_menu_list'] = None
                        self.UIData['shallow_opqbot_menu_list'] = None
                        self.UIData['shallow_gocqhttp_menu_list'] = None
                        self.UIData['shallow_walleq_menu_list'] = None
                        self.UIData['shallow_cwcb_menu_list'] = None
                        self.UIData['shallow_virtual_terminal_menu_list'] = None
                        self.UIData['shallow_account_menu_list'] = None
                        self.updateShallowMenuList()

    def process_msg(self):
        delay = 1 if self.busy else 20
        self.UIObject['main_tk'].after(delay, self.process_msg)
        self.mainrun()

    def update_account_msg(self):
        if self.UIObject['flag_first_account_list_update']:
            self.UIObject['main_tk'].after(60000, self.update_account_msg)
            self.UIObject['flag_first_account_list_update'] = False
        else:
            self.UIObject['main_tk'].after(300000, self.update_account_msg)
            self.updateShallowMenuAccountList()

    def mainrun(self):
        if True:
            if self.Proc_info.rx_queue.empty() or self.Proc_config['ready_for_restart']:
                self.busy = False
            else:
                self.busy = True
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block=False)
                except Exception:
                    rx_packet_data = None
                if rx_packet_data is None:
                    pass
                elif not type(rx_packet_data) is OlivOS.API.Control.packet:
                    pass
                elif (
                    rx_packet_data.action == 'send'
                    and type(rx_packet_data.key) is dict
                    and 'data' in rx_packet_data.key
                    and 'action' in rx_packet_data.key['data']
                ):
                    if 'update_data' == rx_packet_data.key['data']['action']:
                        self.UIData.update(rx_packet_data.key['data']['data'])
                        self.updateShallowMenuList()
                    elif 'update_account_list' == rx_packet_data.key['data']['action']:
                        self.updateShallowMenuAccountList()
                        if self.UIObject['root_shallow'] is not None:
                            self.updateShallow()
                    elif 'start_shallow' == rx_packet_data.key['data']['action']:
                        if self.UIObject['root_shallow'] is None:
                            self.startShallow()
                            self.startOlivOSTerminalUISend()
                        else:
                            self.updateShallow()
                            self.updatePluginEdit()
                    elif 'show_update' == rx_packet_data.key['data']['action']:
                        self.UIObject['flag_have_update'] = True
                        self.updateShallowMenuList()
                        if self.UIObject['root_shallow'] is not None:
                            self.updateShallow()
                    elif 'account_edit' == rx_packet_data.key['data']['action']:
                        if (
                            'event' in rx_packet_data.key['data']
                            and 'account_edit_on' == rx_packet_data.key['data']['event']
                            and 'bot_info' in rx_packet_data.key['data']
                            and type(rx_packet_data.key['data']['bot_info']) is dict
                        ):
                            OlivOS.multiLoginUIAPI.run_HostUI_asayc(
                                plugin_bot_info_dict=rx_packet_data.key['data']['bot_info'],
                                control_queue=self.Proc_info.control_queue
                            )
                    elif 'plugin_edit_menu_on' == rx_packet_data.key['data']['action']:
                        self.startPluginEdit()
                    elif 'logger' == rx_packet_data.key['data']['action']:
                        self.UIObject['root_OlivOS_terminal_data'].append(
                            rx_packet_data.key['data']['data']
                        )
                        if len(
                            self.UIObject['root_OlivOS_terminal_data']
                        ) > self.UIObject['root_OlivOS_terminal_data_max']:
                            self.UIObject['root_OlivOS_terminal_data'].pop(0)
                        if self.UIObject['root_OlivOS_terminal'] is not None:
                            self.UIObject['root_OlivOS_terminal'].tree_add_line(
                                rx_packet_data.key['data']['data']
                            )
                    elif 'napcat' == rx_packet_data.key['data']['action']:
                        if 'event' in rx_packet_data.key['data']:
                            if 'init' == rx_packet_data.key['data']['event']:
                                if self.UIData['shallow_napcat_menu_list'] is None:
                                    self.UIData['shallow_napcat_menu_list'] = []
                                if 'hash' in rx_packet_data.key['data']:
                                    if rx_packet_data.key['data']['hash'] in self.bot_info:
                                        tmp_title = '%s' % (
                                            str(
                                                self.bot_info[rx_packet_data.key['data']['hash']].id
                                            )
                                        )
                                        self.UIData['shallow_napcat_menu_list'].append(
                                            [
                                                tmp_title,
                                                rx_packet_data.key['data']['hash'],
                                                '',
                                                'napcat'
                                            ]
                                        )
                                        self.updateShallowMenuList()
                                if self.UIObject['root_shallow'] is not None:
                                    self.updateShallow()
                                self.startNapCatTerminalUISend(rx_packet_data.key['data']['hash'])
                            elif 'log' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'data' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    if hash not in self.UIObject['root_napcat_terminal_data']:
                                        self.UIObject['root_napcat_terminal_data'][hash] = []
                                    self.UIObject['root_napcat_terminal_data'][hash].append(
                                        rx_packet_data.key['data']['data']
                                    )
                                    if len(
                                        self.UIObject['root_napcat_terminal_data'][hash]
                                    ) > self.UIObject['root_napcat_terminal_data_max']:
                                        self.UIObject['root_napcat_terminal_data'][hash].pop(0)
                                    if hash in self.UIObject['root_napcat_terminal']:
                                        self.UIObject['root_napcat_terminal'][hash].tree_add_line(
                                            rx_packet_data.key['data']['data']
                                        )
                            elif 'qrcode' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'path' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    if hash in self.bot_info:
                                        if hash in self.UIObject['root_qrcode_window']:
                                            try:
                                                self.UIObject['root_qrcode_window'][hash].stop()
                                            except Exception:
                                                pass
                                        self.UIObject['root_qrcode_window'][hash] = QRcodeUI(
                                            Model_name='qrcode_window',
                                            logger_proc=self.Proc_info.logger_proc.log,
                                            root=self,
                                            root_tk=None,
                                            bot=self.bot_info[hash],
                                            path=rx_packet_data.key['data']['path']
                                        )
                                        self.UIObject['root_qrcode_window'][hash].start()
                            elif 'napcat_terminal_on' == rx_packet_data.key['data']['event']:
                                if 'hash' in rx_packet_data.key['data']:
                                    self.startNapCatTerminalUI(rx_packet_data.key['data']['hash'])
                    elif 'gocqhttp' == rx_packet_data.key['data']['action']:
                        if 'event' in rx_packet_data.key['data']:
                            if 'init' == rx_packet_data.key['data']['event']:
                                if self.UIData['shallow_gocqhttp_menu_list'] is None:
                                    self.UIData['shallow_gocqhttp_menu_list'] = []
                                if 'hash' in rx_packet_data.key['data']:
                                    if rx_packet_data.key['data']['hash'] in self.bot_info:
                                        tmp_title = '%s' % (
                                            str(
                                                self.bot_info[rx_packet_data.key['data']['hash']].id
                                            )
                                        )
                                        self.UIData['shallow_gocqhttp_menu_list'].append(
                                            [
                                                tmp_title,
                                                rx_packet_data.key['data']['hash'],
                                                '',
                                                'gocqhttp'
                                            ]
                                        )
                                        self.updateShallowMenuList()
                                if self.UIObject['root_shallow'] is not None:
                                    self.updateShallow()
                                self.startGoCqhttpTerminalUISend(rx_packet_data.key['data']['hash'])
                            elif 'log' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'data' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    if hash not in self.UIObject['root_gocqhttp_terminal_data']:
                                        self.UIObject['root_gocqhttp_terminal_data'][hash] = []
                                    self.UIObject['root_gocqhttp_terminal_data'][hash].append(
                                        rx_packet_data.key['data']['data']
                                    )
                                    if len(
                                        self.UIObject['root_gocqhttp_terminal_data'][hash]
                                    ) > self.UIObject['root_gocqhttp_terminal_data_max']:
                                        self.UIObject['root_gocqhttp_terminal_data'][hash].pop(0)
                                    if hash in self.UIObject['root_gocqhttp_terminal']:
                                        self.UIObject['root_gocqhttp_terminal'][hash].tree_add_line(
                                            rx_packet_data.key['data']['data']
                                        )
                            elif 'qrcode' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'path' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    if hash in self.bot_info:
                                        if hash in self.UIObject['root_qrcode_window']:
                                            try:
                                                self.UIObject['root_qrcode_window'][hash].stop()
                                            except Exception:
                                                pass
                                        self.UIObject['root_qrcode_window'][hash] = QRcodeUI(
                                            Model_name='qrcode_window',
                                            logger_proc=self.Proc_info.logger_proc.log,
                                            root=self,
                                            root_tk=None,
                                            bot=self.bot_info[hash],
                                            path=rx_packet_data.key['data']['path']
                                        )
                                        self.UIObject['root_qrcode_window'][hash].start()
                            elif 'token_get' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'token' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    self.setGoCqhttpModelSend(
                                        hash=rx_packet_data.key['data']['hash'],
                                        data=rx_packet_data.key['data']['token']
                                    )
                            elif 'gocqhttp_terminal_on' == rx_packet_data.key['data']['event']:
                                if 'hash' in rx_packet_data.key['data']:
                                    self.startGoCqhttpTerminalUI(rx_packet_data.key['data']['hash'])
                    elif 'walleq' == rx_packet_data.key['data']['action']:
                        if 'event' in rx_packet_data.key['data']:
                            if 'init' == rx_packet_data.key['data']['event']:
                                if self.UIData['shallow_walleq_menu_list'] is None:
                                    self.UIData['shallow_walleq_menu_list'] = []
                                if 'hash' in rx_packet_data.key['data']:
                                    if rx_packet_data.key['data']['hash'] in self.bot_info:
                                        tmp_title = '%s' % (
                                            str(
                                                self.bot_info[rx_packet_data.key['data']['hash']].id
                                            )
                                        )
                                        self.UIData['shallow_walleq_menu_list'].append(
                                            [
                                                tmp_title,
                                                rx_packet_data.key['data']['hash'],
                                                '',
                                                'walleq'
                                            ]
                                        )
                                        self.updateShallowMenuList()
                                if self.UIObject['root_shallow'] is not None:
                                    self.updateShallow()
                                self.startWalleQTerminalUISend(rx_packet_data.key['data']['hash'])
                            elif 'log' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'data' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    if hash not in self.UIObject['root_walleq_terminal_data']:
                                        self.UIObject['root_walleq_terminal_data'][hash] = []
                                    self.UIObject['root_walleq_terminal_data'][hash].append(
                                        rx_packet_data.key['data']['data']
                                    )
                                    if len(
                                        self.UIObject['root_walleq_terminal_data'][hash]
                                    ) > self.UIObject['root_walleq_terminal_data_max']:
                                        self.UIObject['root_walleq_terminal_data'][hash].pop(0)
                                    if hash in self.UIObject['root_walleq_terminal']:
                                        self.UIObject['root_walleq_terminal'][hash].tree_add_line(
                                            rx_packet_data.key['data']['data']
                                        )
                            elif 'qrcode' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'path' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    if hash in self.bot_info:
                                        if hash in self.UIObject['root_qrcode_window']:
                                            try:
                                                self.UIObject['root_qrcode_window'][hash].stop()
                                            except Exception:
                                                pass
                                        self.UIObject['root_qrcode_window'][hash] = QRcodeUI(
                                            Model_name='qrcode_window',
                                            logger_proc=self.Proc_info.logger_proc.log,
                                            root=self,
                                            root_tk=None,
                                            bot=self.bot_info[hash],
                                            path=rx_packet_data.key['data']['path']
                                        )
                                        self.UIObject['root_qrcode_window'][hash].start()
                            elif 'walleq_terminal_on' == rx_packet_data.key['data']['event']:
                                if 'hash' in rx_packet_data.key['data']:
                                    self.startWalleQTerminalUI(rx_packet_data.key['data']['hash'])
                    elif 'ComWeChatBotClient' == rx_packet_data.key['data']['action']:
                        if 'event' in rx_packet_data.key['data']:
                            if 'init' == rx_packet_data.key['data']['event']:
                                if self.UIData['shallow_cwcb_menu_list'] is None:
                                    self.UIData['shallow_cwcb_menu_list'] = []
                                if 'hash' in rx_packet_data.key['data']:
                                    if rx_packet_data.key['data']['hash'] in self.bot_info:
                                        tmp_title = '%s' % (
                                            str(
                                                self.bot_info[rx_packet_data.key['data']['hash']].id
                                            )
                                        )
                                        self.UIData['shallow_cwcb_menu_list'].append(
                                            [
                                                tmp_title,
                                                rx_packet_data.key['data']['hash'],
                                                '',
                                                'ComWeChatBotClient'
                                            ]
                                        )
                                        self.updateShallowMenuList()
                                if self.UIObject['root_shallow'] is not None:
                                    self.updateShallow()
                                self.startCWCBTerminalUISend(rx_packet_data.key['data']['hash'])
                            elif 'log' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'data' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    if hash not in self.UIObject['root_cwcb_terminal_data']:
                                        self.UIObject['root_cwcb_terminal_data'][hash] = []
                                    self.UIObject['root_cwcb_terminal_data'][hash].append(
                                        rx_packet_data.key['data']['data']
                                    )
                                    if len(
                                        self.UIObject['root_cwcb_terminal_data'][hash]
                                    ) > self.UIObject['root_cwcb_terminal_data_max']:
                                        self.UIObject['root_cwcb_terminal_data'][hash].pop(0)
                                    if hash in self.UIObject['root_cwcb_terminal']:
                                        self.UIObject['root_cwcb_terminal'][hash].tree_add_line(
                                            rx_packet_data.key['data']['data']
                                        )
                            elif 'cwcb_terminal_on' == rx_packet_data.key['data']['event']:
                                if 'hash' in rx_packet_data.key['data']:
                                    self.startCWCBTerminalUI(rx_packet_data.key['data']['hash'])
                    elif 'opqbot' == rx_packet_data.key['data']['action']:
                        if 'event' in rx_packet_data.key['data']:
                            if 'init' == rx_packet_data.key['data']['event']:
                                if self.UIData['shallow_opqbot_menu_list'] is None:
                                    self.UIData['shallow_opqbot_menu_list'] = []
                                if 'hash' in rx_packet_data.key['data']:
                                    if rx_packet_data.key['data']['hash'] in self.bot_info:
                                        tmp_title = '%s' % (
                                            str(
                                                self.bot_info[rx_packet_data.key['data']['hash']].id
                                            )
                                        )
                                        self.UIData['shallow_opqbot_menu_list'].append(
                                            [
                                                tmp_title,
                                                rx_packet_data.key['data']['hash'],
                                                '',
                                                'opqbot'
                                            ]
                                        )
                                        self.updateShallowMenuList()
                                if self.UIObject['root_shallow'] is not None:
                                    self.updateShallow()
                                self.startOPQBotTerminalUISend(rx_packet_data.key['data']['hash'])
                            elif 'log' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'data' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    if hash not in self.UIObject['root_opqbot_terminal_data']:
                                        self.UIObject['root_opqbot_terminal_data'][hash] = []
                                    self.UIObject['root_opqbot_terminal_data'][hash].append(
                                        rx_packet_data.key['data']['data']
                                    )
                                    if len(
                                        self.UIObject['root_opqbot_terminal_data'][hash]
                                    ) > self.UIObject['root_opqbot_terminal_data_max']:
                                        self.UIObject['root_opqbot_terminal_data'][hash].pop(0)
                                    if hash in self.UIObject['root_opqbot_terminal']:
                                        self.UIObject['root_opqbot_terminal'][hash].tree_add_line(
                                            rx_packet_data.key['data']['data']
                                        )
                            elif 'qrcode' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'path' in rx_packet_data.key['data']
                                ):
                                    hash = rx_packet_data.key['data']['hash']
                                    path = rx_packet_data.key['data']['path']
                                    self.sendOpenQRcodeUrl(hash, path)
                            elif 'opqbot_terminal_on' == rx_packet_data.key['data']['event']:
                                if 'hash' in rx_packet_data.key['data']:
                                    self.startOPQBotTerminalUI(rx_packet_data.key['data']['hash'])
                    elif 'virtual_terminal' == rx_packet_data.key['data']['action']:
                        if 'event' in rx_packet_data.key['data']:
                            if 'init' == rx_packet_data.key['data']['event']:
                                if self.UIData['shallow_virtual_terminal_menu_list'] is None:
                                    self.UIData['shallow_virtual_terminal_menu_list'] = []
                                if 'hash' in rx_packet_data.key['data']:
                                    if rx_packet_data.key['data']['hash'] in self.bot_info:
                                        tmp_title = '%s' % (
                                            str(
                                                self.bot_info[rx_packet_data.key['data']['hash']].id
                                            )
                                        )
                                        self.UIData['shallow_virtual_terminal_menu_list'].append(
                                            [
                                                tmp_title,
                                                rx_packet_data.key['data']['hash'],
                                                '',
                                                'virtual_terminal'
                                            ]
                                        )
                                        self.updateShallowMenuList()
                                if self.UIObject['root_shallow'] is not None:
                                    self.updateShallow()
                                self.startVirtualTerminalUISend(rx_packet_data.key['data']['hash'])
                            elif 'virtual_terminal_on' == rx_packet_data.key['data']['event']:
                                if 'hash' in rx_packet_data.key['data']:
                                    self.startVirtualTerminalUI(rx_packet_data.key['data']['hash'])
                            elif 'log' == rx_packet_data.key['data']['event']:
                                if (
                                    'hash' in rx_packet_data.key['data']
                                    and 'data' in rx_packet_data.key['data']
                                    and 'name' in rx_packet_data.key['data']
                                ):
                                    user_conf = {
                                        "user_name": "未知",
                                        "user_id": "-1",
                                        "flag_group": True,
                                        "target_id": "-1",
                                        "group_role": "member",
                                    }
                                    if (
                                        "user_conf" in rx_packet_data.key['data']
                                        and rx_packet_data.key['data']["user_conf"] is not None
                                    ):
                                        user_conf.update(rx_packet_data.key['data']["user_conf"])
                                    hash = rx_packet_data.key['data']['hash']
                                    if hash not in (
                                        self.UIObject['root_virtual_terminal_terminal_data']
                                    ):
                                        (
                                            self.UIObject
                                            ['root_virtual_terminal_terminal_data']
                                            [hash]
                                        ) = []
                                    (
                                        self.UIObject['root_virtual_terminal_terminal_data'][hash]
                                        .append(rx_packet_data.key['data'])
                                    )
                                    if len(
                                        self.UIObject['root_virtual_terminal_terminal_data'][hash]
                                    ) > self.UIObject['root_virtual_terminal_terminal_data_max']:
                                        (
                                            self.UIObject
                                            ['root_virtual_terminal_terminal_data']
                                            [hash]
                                            .pop(0)
                                        )
                                    if hash in self.UIObject['root_virtual_terminal_terminal']:
                                        (
                                            self.UIObject['root_virtual_terminal_terminal'][hash]
                                            .tree_add_line(rx_packet_data.key['data'], user_conf)
                                        )
                    elif 'OlivOS_terminal_on' == rx_packet_data.key['data']['action']:
                        self.startOlivOSTerminalUI()

    def getPlatformDisplayName(self, bot_info):
        """
        获取协议端显示名称
        """
        try:
            if bot_info and hasattr(bot_info, 'platform') and bot_info.platform:
                platform_platform = str(bot_info.platform.get('platform', ''))
                platform_sdk = str(bot_info.platform.get('sdk', ''))
                platform_model = str(bot_info.platform.get('model', ''))
                server_auto = (
                    str(bot_info.post_info.auto)
                    if (
                        hasattr(bot_info, 'post_info')
                        and hasattr(bot_info.post_info, 'auto')
                    )
                    else 'False'
                )
                server_type = (
                    str(bot_info.post_info.type)
                    if (
                        hasattr(bot_info, 'post_info')
                        and hasattr(bot_info.post_info, 'type')
                    )
                    else 'post'
                )

                list_data_check = [
                    platform_platform,
                    platform_sdk,
                    platform_model,
                    server_auto,
                    server_type
                ]
                # 使用 accountTypeMappingList 进行匹配
                for type_this in OlivOS.accountMetadataAPI.accountTypeList:
                    flag_hit = True
                    if type_this in OlivOS.accountMetadataAPI.accountTypeMappingList:
                        for list_data_check_i in range(len(list_data_check)):
                            if list_data_check[list_data_check_i] != str(
                                OlivOS.accountMetadataAPI.accountTypeMappingList[type_this][list_data_check_i]
                            ):
                                flag_hit = False
                                break
                        if flag_hit:
                            return type_this
                # 如果找不到完全匹配，尝试只匹配前三个参数（platform, sdk, model）
                for type_this in OlivOS.accountMetadataAPI.accountTypeList:
                    if type_this in OlivOS.accountMetadataAPI.accountTypeMappingList:
                        mapping = OlivOS.accountMetadataAPI.accountTypeMappingList[type_this]
                        if (
                            len(mapping) >= 3
                            and str(mapping[0]) == platform_platform
                            and str(mapping[1]) == platform_sdk
                            and str(mapping[2]) == platform_model
                        ):
                            return type_this
        except Exception:
            pass
        return '自定义'

    def getAccountDisplayInfo(self, botHash, bot_info, flagInit=False):
        """
        获取账号显示信息（名称和协议端）
        """
        account_name = "未知账号"
        try:
            account_name = str(bot_info.id)
        except Exception:
            pass
        if not flagInit:
            try:
                fake_event = OlivOS.API.Event(
                    OlivOS.contentAPI.fake_sdk_event(
                        bot_info=bot_info,
                        fakename='nativeWinUI'
                    ),
                    None
                )
                res_data = fake_event.get_login_info(bot_info)
                if res_data and res_data.get('active') and 'data' in res_data:
                    account_name = res_data['data'].get('name', str(bot_info.id))
                    account_name = f'{account_name}({str(bot_info.id)})'
                else:
                    account_name = str(bot_info.id) if hasattr(bot_info, 'id') else "未知账号"
            except Exception:
                try:
                    account_name = str(bot_info.id) if hasattr(bot_info, 'id') else "未知账号"
                except Exception:
                    pass
        platform_name = self.getPlatformDisplayName(bot_info)
        return account_name, platform_name

    def updateAccountList(self, flagInit=False):
        self.UIData['shallow_account_list_new'] = []
        if self.bot_info and type(self.bot_info) is dict:
            for botHash, bot_info in self.bot_info.items():
                account_name, platform_name = self.getAccountDisplayInfo(botHash, bot_info, flagInit=flagInit)
                self.UIData['shallow_account_list_new'].append((botHash, account_name, platform_name))
            self.UIData['shallow_account_list_new'].sort(key=lambda x: x[1])

    def mergeAccountList(self):
        self.UIData['shallow_account_list'] = self.UIData['shallow_account_list_new']
        return True

    def updateShallowMenuAccountList(self):
        self.updateAccountList()
        if self.mergeAccountList():
            self.updateShallowMenuList()

    def updateShallowMenuAccountListSendFunc(self):
        def resFunc():
            self.updateShallowMenuAccountListSend()
        return resFunc

    def updateShallowMenuAccountListSend(self):
        self.sendRxEvent('send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'update_account_list'
                }
            }
        )

    def updateShallowMenuList(self):
        tmp_new = []
        account_items = []
        account_list = self.UIData['shallow_account_list']
        account_count = len(account_list)
        if 0 == account_count:
            self.updateAccountList(flagInit=True)
            self.mergeAccountList()
        for botHash, account_name, platform_name in account_list:
            account_items.append(['account_info', f"{account_name} - {platform_name}", botHash])

        self.UIData['shallow_menu_list'] = []
        self.UIData['shallow_menu_list'].extend([
            ['打开终端', self.startOlivOSTerminalUISend]
        ])
        # 账号菜单项
        account_menu_title = f"[{account_count}]个账号"
        account_list_final = []
        if account_items:
            account_list_final = account_items
        account_refresh = [
            ['SEPARATOR'],
            ['刷新', self.updateShallowMenuAccountListSendFunc()]
        ]
        self.UIData['shallow_menu_list'].extend([
            ['account_menu', account_menu_title, account_list_final + account_refresh, account_count]
        ])
        self.UIData['shallow_menu_list'].extend([
            ['SEPARATOR']
        ])
        self.UIData['shallow_menu_list'].extend([
            # ['账号管理', self.startAccountEditSendFunc()],
            # ['账号管理', None],
            ['NapCat管理', self.UIData['shallow_napcat_menu_list']],
            ['OPQBot管理', self.UIData['shallow_opqbot_menu_list']],
            ['gocqhttp管理', self.UIData['shallow_gocqhttp_menu_list']],
            ['walleq管理', self.UIData['shallow_walleq_menu_list']],
            ['ComWeChat管理', self.UIData['shallow_cwcb_menu_list']],
            ['虚拟终端', self.UIData['shallow_virtual_terminal_menu_list']],
            ['插件管理', self.startPluginEditSend],
            ['插件菜单', self.UIData['shallow_plugin_menu_list']],
            ['重载插件', self.sendPluginRestart],
            ['社区论坛', self.sendOpenForum],
            ['更新OlivOS', self.sendOlivOSUpdateGet],
            ['退出OlivOS', self.setOlivOSExit]
        ])

        for data_this in self.UIData['shallow_menu_list']:
            if data_this[0] in ['NapCat管理', 'OPQBot管理', 'gocqhttp管理', 'walleq管理', 'ComWeChat管理', '虚拟终端']:
                if data_this[1] is not None:
                    tmp_new.append(data_this)
            elif data_this[0] in ['更新OlivOS']:
                if self.UIObject['flag_have_update']:
                    data_this[0] += '[有更新!]'
                tmp_new.append(data_this)
            else:
                tmp_new.append(data_this)
        self.UIData['shallow_menu_list'] = tmp_new

    def startAccountEditSendFunc(self):
        def resFunc():
            self.startAccountEditSend()
        return resFunc

    def startAccountEditSend(self):
        self.sendControlEventSend(
            'call_system_event', {
                'action': [
                    'account_edit_asayc_start',
                    'account_edit_asayc_do'
                ]
            }
        )

    def startGoCqhttpTerminalUISendFunc(self, hash):
        def resFunc():
            self.startGoCqhttpTerminalUISend(hash)
        return resFunc

    def startWalleQTerminalUISendFunc(self, hash):
        def resFunc():
            self.startWalleQTerminalUISend(hash)
        return resFunc

    def startCWCBTerminalUISendFunc(self, hash):
        def resFunc():
            self.startCWCBTerminalUISend(hash)
        return resFunc

    def startOPQBotTerminalUISendFunc(self, hash):
        def resFunc():
            self.startOPQBotTerminalUISend(hash)
        return resFunc

    def startNapCatTerminalUISendFunc(self, hash):
        def resFunc():
            self.startNapCatTerminalUISend(hash)
        return resFunc

    def startGoCqhttpTerminalUISend(self, hash):
        self.sendRxEvent(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'gocqhttp',
                    'event': 'gocqhttp_terminal_on',
                    'hash': hash,
                }
            }
        )

    def startWalleQTerminalUISend(self, hash):
        self.sendRxEvent(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'walleq',
                    'event': 'walleq_terminal_on',
                    'hash': hash,
                }
            }
        )

    def startCWCBTerminalUISend(self, hash):
        self.sendRxEvent(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'ComWeChatBotClient',
                    'event': 'cwcb_terminal_on',
                    'hash': hash,
                }
            }
        )

    def startOPQBotTerminalUISend(self, hash):
        self.sendRxEvent(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'opqbot',
                    'event': 'opqbot_terminal_on',
                    'hash': hash,
                }
            }
        )

    def startNapCatTerminalUISend(self, hash):
        self.sendRxEvent(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'napcat',
                    'event': 'napcat_terminal_on',
                    'hash': hash,
                }
            }
        )

    def startGoCqhttpTerminalUI(self, hash):
        if hash in self.bot_info:
            if hash in self.UIObject['root_gocqhttp_terminal']:
                try:
                    self.UIObject['root_gocqhttp_terminal'][hash].lift()
                except Exception:
                    pass
            else:
                self.UIObject['root_gocqhttp_terminal'][hash] = gocqhttpTerminalUI(
                    Model_name='gocqhttp_terminal',
                    logger_proc=self.Proc_info.logger_proc.log,
                    root=self,
                    root_tk=None,
                    bot=self.bot_info[hash]
                )
                self.UIObject['root_gocqhttp_terminal'][hash].start()

    def startWalleQTerminalUI(self, hash):
        if hash in self.bot_info:
            if hash in self.UIObject['root_walleq_terminal']:
                try:
                    self.UIObject['root_walleq_terminal'][hash].lift()
                except Exception:
                    pass
            else:
                self.UIObject['root_walleq_terminal'][hash] = walleqTerminalUI(
                    Model_name='walleq_terminal',
                    logger_proc=self.Proc_info.logger_proc.log,
                    root=self,
                    root_tk=None,
                    bot=self.bot_info[hash]
                )
                self.UIObject['root_walleq_terminal'][hash].start()

    def startCWCBTerminalUI(self, hash):
        if hash in self.bot_info:
            if hash in self.UIObject['root_cwcb_terminal']:
                try:
                    self.UIObject['root_cwcb_terminal'][hash].lift()
                except Exception:
                    pass
            else:
                self.UIObject['root_cwcb_terminal'][hash] = CWCBTerminalUI(
                    Model_name='cwcb_terminal',
                    logger_proc=self.Proc_info.logger_proc.log,
                    root=self,
                    root_tk=None,
                    bot=self.bot_info[hash]
                )
                self.UIObject['root_cwcb_terminal'][hash].start()

    def startOPQBotTerminalUI(self, hash):
        if hash in self.bot_info:
            if hash in self.UIObject['root_opqbot_terminal']:
                try:
                    self.UIObject['root_opqbot_terminal'][hash].lift()
                except Exception:
                    pass
            else:
                self.UIObject['root_opqbot_terminal'][hash] = opqbotTerminalUI(
                    Model_name='opqbot_terminal',
                    logger_proc=self.Proc_info.logger_proc.log,
                    root=self,
                    root_tk=None,
                    bot=self.bot_info[hash]
                )
                self.UIObject['root_opqbot_terminal'][hash].start()

    def startNapCatTerminalUI(self, hash):
        if hash in self.bot_info:
            if hash in self.UIObject['root_napcat_terminal']:
                try:
                    self.UIObject['root_napcat_terminal'][hash].lift()
                except Exception:
                    pass
            else:
                self.UIObject['root_napcat_terminal'][hash] = napcatTerminalUI(
                    Model_name='napcat_terminal',
                    logger_proc=self.Proc_info.logger_proc.log,
                    root=self,
                    root_tk=None,
                    bot=self.bot_info[hash]
                )
                self.UIObject['root_napcat_terminal'][hash].start()

    def startVirtualTerminalUISendFunc(self, hash):
        def resFunc():
            self.startVirtualTerminalUISend(hash)

        return resFunc

    def startVirtualTerminalUISend(self, hash):
        self.sendRxEvent(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'virtual_terminal',
                    'event': 'virtual_terminal_on',
                    'hash': hash,
                }
            }
        )

    def startVirtualTerminalUI(self, hash):
        if hash in self.bot_info:
            if hash in self.UIObject['root_virtual_terminal_terminal']:
                try:
                    self.UIObject['root_virtual_terminal_terminal'][hash].lift()
                except Exception:
                    pass
            else:
                self.UIObject['root_virtual_terminal_terminal'][hash] = VirtualTerminalUI(
                    Model_name='virtual_terminal',
                    logger_proc=self.Proc_info.logger_proc.log,
                    root=self,
                    root_tk=None,
                    bot=self.bot_info[hash]
                )
                self.UIObject['root_virtual_terminal_terminal'][hash].start()

    def startOlivOSTerminalUISend(self):
        self.sendRxEvent(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'OlivOS_terminal_on'
                }
            }
        )

    def startOlivOSTerminalUI(self):
        existing: 'OlivOSTerminalUI' = self.UIObject.get('root_OlivOS_terminal')
        if existing is not None:
            try:
                existing.lift()
            except Exception:
                pass
        else:
            self.UIObject['root_OlivOS_terminal'] = OlivOSTerminalUI(
                Model_name='OlivOS_terminal',
                logger_proc=self.Proc_info.logger_proc.log,
                root=self,
                root_tk=None
            )
            self.UIObject['root_OlivOS_terminal'].start()

    def setGoCqhttpModelSend(self, hash, data):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'gocqhttp_lib_exe_model',
                    'hash': hash
                },
                'data': {
                    'action': 'input',
                    'data': data
                }
            }
        )

    def setWalleQModelSend(self, hash, data):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'walleq_lib_exe_model',
                    'hash': hash
                },
                'data': {
                    'action': 'input',
                    'data': data
                }
            }
        )

    def setCWCBModelSend(self, hash, data):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'cwcb_lib_exe_model',
                    'hash': hash
                },
                'data': {
                    'action': 'input',
                    'data': data
                }
            }
        )

    def setOPQBotModelSend(self, hash, data):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'opqbot_lib_exe_model',
                    'hash': hash
                },
                'data': {
                    'action': 'input',
                    'data': data
                }
            }
        )

    def setNapCatModelSend(self, hash, data):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'napcat_lib_exe_model',
                    'hash': hash
                },
                'data': {
                    'action': 'input',
                    'data': data
                }
            }
        )

    def setVirtualModelSend(self, hash, data, user_conf=None):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'terminal_link',
                    'hash': hash
                },
                'data': {
                    'action': 'input',
                    'data': data,
                    'user_conf': user_conf
                }
            }
        )

    def startPluginEditSend(self):
        self.sendRxEvent(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'plugin_edit_menu_on'
                }
            }
        )

    def sendRxEvent(self, action, data):
        if self.Proc_info.rx_queue is not None:
            self.Proc_info.rx_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block=False
            )

    def startPluginEdit(self):
        count_str = str(self.UIObject['root_plugin_edit_count'])
        # self.UIObject['root_plugin_edit_count'] += 1
        if count_str not in self.UIObject['root_plugin_edit']:
            self.UIObject['root_plugin_edit'][count_str] = {}
            self.UIObject['root_plugin_edit'][count_str]['obj'] = pluginManageUI(
                Model_name='shallow_menu_plugin_manage',
                logger_proc=self.Proc_info.logger_proc.log,
                root=self,
                key=count_str
            )
            self.UIObject['root_plugin_edit'][count_str]['obj'].start()

    def updatePluginEdit(self):
        try:
            for obj_this in self.UIObject['root_plugin_edit']:
                try:
                    self.UIObject['root_plugin_edit'][obj_this]['obj'].tree_load()
                except Exception:
                    pass
        except Exception:
            pass

    def setOlivOSExit(self):
        self.sendControlEvent('exit_total')

    def sendPluginControlEventFunc(self, pluginNameSpace, eventName):
        def resFunc():
            self.sendPluginControlEvent(pluginNameSpace, eventName)

        return resFunc

    def sendPluginControlEvent(self, pluginNameSpace, eventName):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'plugin'
                },
                'data': {
                    'action': 'plugin_menu',
                    'namespace': pluginNameSpace,
                    'event': eventName
                }
            }
        )

    def sendControlEventSend(self, action, data):
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block=False
            )

    def sendControlEvent(self, eventName: str):
        if self.UIObject['root_shallow'] is not None:
            self.UIObject['root_shallow'].UIObject['shallow_root'].notify(
                '正在退出……'
            )
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(eventName, self.Proc_name),
                block=False
            )

    def sendPluginRestart(self):
        if self.UIObject['root_shallow'] is not None:
            self.UIObject['root_shallow'].UIObject['shallow_root'].notify(
                '正在重载……'
            )
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet('restart_send', 'plugin'),
                block=False
            )

    def sendOlivOSUpdateGet(self):
        if self.UIObject['root_shallow'] is not None:
            self.UIObject['root_shallow'].UIObject['shallow_root'].notify(
                '正在检查更新……'
            )
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet('init_type', 'update_get'),
                block=False
            )

    def sendOpenForum(self):
        if self.UIObject['root_shallow'] is not None:
            self.UIObject['root_shallow'].UIObject['shallow_root'].notify(
                '正在前往社区论坛……'
            )
        self.sendOpenWebviewEvent('forum_page', 'OlivOS论坛', 'https://forum.olivos.run/')

    def sendOpenQRcodeUrl(self, hash, url):
        if (
            type(self.bot_info) is dict
            and hash in self.bot_info
        ):
            try:
                res = tkinter.messagebox.askquestion(f'请使用账号 {self.bot_info[hash].id} 扫码', "是否使用内置浏览器?")
                if res == 'yes':
                    self.sendOpenWebviewEvent(f'qrcode_page={hash}', f'请使用账号 {self.bot_info[hash].id} 扫码', url)
                else:
                    webbrowser.open(url)
            except webbrowser.Error as error_info:
                tkinter.messagebox.showerror("webbrowser.Error", error_info)

    def sendOpenWebviewEvent(
        self,
        name: str,
        title: str,
        url: str
    ):
        OlivOS.webviewUIAPI.sendOpenWebviewPage(
            self.Proc_info.control_queue,
            name,
            title,
            url
        )

    def startShallowSend(self):
        self.sendRxEvent('send', {
            'target': {
                'type': 'nativeWinUI'
            },
            'data': {
                'action': 'start_shallow'
            }
        })

    def startShallow(self):
        releaseBase64Data('./resource', 'tmp_favoricon.ico', OlivOS.data.favoricon)
        if self.UIObject['root_shallow'] is None:
            self.UIObject['root_shallow'] = shallow(
                name='OlivOS',
                image='./resource/tmp_favoricon.ico',
                root=self
            )
            self.UIObject['root_shallow'].start()

    def updateShallow(self):
        if self.UIObject['root_shallow'] is not None:
            self.UIObject['root_shallow'].refresh()


class QRcodeUI(object):
    def __init__(self, Model_name, logger_proc=None, root=None, root_tk=None, bot=None, path=None):
        self.Model_name = Model_name
        self.root = root
        self.root_tk = root_tk
        self.bot = bot
        self.path = path
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIConfig.update(dictColorContext)

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('请登录账号[%s]扫描二维码' % str(self.bot.id))
        self.UIObject['root'].geometry('500x500')
        self.UIObject['root'].resizable(
            width=False,
            height=False
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

        self.UIObject['root_qrcode_img_data'] = Image.open(self.path)
        try:
            self.UIObject['root_qrcode_img_data'] = self.UIObject['root_qrcode_img_data'].resize(
                (500, 500),
                (
                    Image.Resampling.LANCZOS
                    if hasattr(Image, 'Resampling')
                    else Image.LANCZOS
                )
            )
        except AttributeError:
            self.UIObject['root_qrcode_img_data'] = self.UIObject['root_qrcode_img_data'].resize(
                (500, 500),
                Image.ANTIALIAS
            )
        self.UIObject['root_qrcode_img'] = ImageTk.PhotoImage(self.UIObject['root_qrcode_img_data'])
        self.UIObject['root_qrcode_label'] = tkinter.Label(self.UIObject['root'])
        self.UIObject['root_qrcode_label'].config(image=self.UIObject['root_qrcode_img'])
        self.UIObject['root_qrcode_label'].image = self.UIObject['root_qrcode_img']
        self.UIObject['root_qrcode_label'].pack()

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')

        self.UIObject['root'].after(180 * 1000, self.sleepExit)
        self.UIObject['root'].mainloop()

        self.exit()

    def exit(self):
        pass

    def sleepExit(self):
        self.stop()

    def stop(self):
        self.UIObject['root'].quit()
        self.UIObject['root'].destroy()


# ---------------------------- 基类 ----------------------------
class BaseTerminalUI:
    """所有终端UI的基类，提供通用的布局、事件处理和生命周期管理"""

    # 子类可覆盖的配置
    WINDOW_TITLE = "终端"
    WINDOW_SIZE = "800x600"
    MIN_SIZE = (800, 600)
    # 网格列权重配置，默认4列 (col0权重0, col1权重2, col2权重2, col3权重0)
    COLUMN_WEIGHTS = [(0, 0), (1, 2), (2, 2), (3, 0)]
    # 是否包含发送按钮 (有些子类可能不需要)
    HAS_SEND_BUTTON = True
    # 是否包含输入框标签
    HAS_INPUT_LABEL = True

    def __init__(self, Model_name, logger_proc=None, root=None, root_tk=None, bot=None):
        self.Model_name = Model_name
        self.root = root
        self.root_tk = root_tk
        self.bot = bot
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIConfig.update(dictColorContext)  # 全局颜色配置

    # ========== 模板方法 ==========
    def start(self):
        """启动UI的主流程，子类可覆盖部分步骤"""
        self._build_main_window()
        self._build_tree()
        self._build_scrollbar()
        if self.HAS_INPUT_LABEL:
            self._build_input_area()
        if self.HAS_SEND_BUTTON:
            self._build_send_button()
        self._build_extra_controls()   # 子类可添加额外控件
        self._post_build()             # 收尾工作（图标、协议、历史日志等）
        self.UIObject['root'].mainloop()
        self.exit()

    def _build_main_window(self):
        """创建主窗口，配置几何和网格权重"""
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title(self.get_window_title())
        self.UIObject['root'].geometry(self.WINDOW_SIZE)
        self.UIObject['root'].minsize(*self.MIN_SIZE)
        self._config_grid_weights()
        self.UIObject['root'].resizable(width=True, height=True)
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

    def _config_grid_weights(self):
        """配置网格行/列权重"""
        self.UIObject['root'].grid_rowconfigure(0, weight=15)
        self.UIObject['root'].grid_rowconfigure(1, weight=0)
        for col, weight in self.COLUMN_WEIGHTS:
            self.UIObject['root'].grid_columnconfigure(col, weight=weight)

    def _build_tree(self):
        """创建日志树形视图"""
        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('DATA',)
        # 计算列宽（基于窗口宽度）
        width = int(self.WINDOW_SIZE.split('x')[0]) - 15*2 - 18 - 5
        self.UIObject['tree'].column('DATA', width=width)
        self.UIObject['tree'].heading('DATA', text='日志')
        self.UIObject['tree']['selectmode'] = 'browse'

        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['tree'].bind('<Button-3>', lambda x: self.tree_rightKey(x))

        # grid布局，默认跨越前3列（如果列数不同，子类可覆盖）
        self.UIObject['tree'].grid(
            row=0, column=0, sticky="nsew", rowspan=1, columnspan=3,
            padx=(15, 0), pady=(15, 0), ipadx=0, ipady=0
        )

    def _build_scrollbar(self):
        """创建垂直滚动条"""
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'], orient="vertical", command=self.UIObject['tree'].yview
        )
        self.UIObject['tree_yscroll'].grid(
            row=0, column=3, sticky="nsw", rowspan=1, columnspan=1,
            padx=(0, 15), pady=(15, 0), ipadx=0, ipady=0
        )
        self.UIData['flag_tree_is_bottom'] = True
        self.UIObject['tree'].configure(
            yscrollcommand=self._scroll_onChange(self.UIObject['tree_yscroll'].set)
        )

    def _build_input_area(self):
        """创建输入框"""
        self._root_Entry_init(
            obj_root='root', obj_name='root_input', str_name='root_input_StringVar',
            x=15, y=self._get_input_y(), width_t=0, width=self._get_input_width(),
            height=24, action=None, title=self._get_input_label_text()
        )
        self.UIObject['root_input'].bind("<Return>", self._root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row=1, column=0, sticky="s", rowspan=1, columnspan=2,
            padx=(15, 0), pady=(8, 15), ipadx=0, ipady=4
        )

    def _build_send_button(self):
        """创建发送按钮"""
        self._root_Button_init(
            name='root_button_save', text='>', command=self._root_Entry_enter_Func('root_input'),
            x=self._get_button_x(), y=self._get_input_y(), width=16, height=1
        )
        self.UIObject['root_button_save'].grid(
            row=1, column=2, sticky="swe", rowspan=1, columnspan=2,
            padx=(0, 15), pady=(8, 15), ipadx=8, ipady=0
        )

    def _build_extra_controls(self):
        """子类可覆盖以添加额外控件（如OlivOS的等级选择下拉框）"""
        pass

    def _post_build(self):
        """收尾工作：图标、关闭协议、加载历史日志"""
        try:
            self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        except Exception:
            pass
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)
        self._tree_init_line()

    # ========== 辅助计算方法 ==========
    def get_window_title(self):
        """子类可覆盖提供动态标题"""
        if self.bot:
            return f"{self.WINDOW_TITLE} - {str(self.bot.id)}"
        return self.WINDOW_TITLE

    def _get_input_y(self):
        """输入框的Y坐标（基于窗口高度）"""
        height = int(self.WINDOW_SIZE.split('x')[1])
        return height - 15*1 - 24

    def _get_input_width(self):
        """输入框宽度"""
        width = int(self.WINDOW_SIZE.split('x')[0])
        return width - 15*2

    def _get_button_x(self):
        width = int(self.WINDOW_SIZE.split('x')[0])
        return width - 15*2 - 5

    def _get_input_label_text(self):
        """输入框前的标签文字（一般不需要）"""
        return ''

    # ========== 通用事件和方法 ==========
    def _scroll_onChange(self, command):
        def res(*arg, **kwarg):
            if arg[1] == '1.0':
                self.UIData['flag_tree_is_bottom'] = True
            else:
                self.UIData['flag_tree_is_bottom'] = False
            return command(*arg, **kwarg)
        return res

    def tree_rightKey(self, event):
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label='查看', command=lambda: self._rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label='复制', command=lambda: self._rightKey_action('copy'))
        self._add_extra_menu_items()   # 子类可添加额外菜单项
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def _add_extra_menu_items(self):
        """子类可覆盖添加额外的右键菜单项"""
        pass

    def _rightKey_action(self, action: str):
        if action == 'show':
            msg = get_tree_force(self.UIObject['tree'])['text']
            if len(msg) > 0:
                tkinter.messagebox.showinfo('日志内容', msg)
        elif action == 'copy':
            msg = get_tree_force(self.UIObject['tree'])['text']
            if len(msg) > 0:
                self.UIObject['root'].clipboard_clear()
                self.UIObject['root'].clipboard_append(msg)
                self.UIObject['root'].update()

    def _root_Entry_enter_Func(self, name):
        def resFunc(*arg, **kwarg):
            self._root_Entry_enter(name, None)
        return resFunc

    def _root_Entry_enter(self, name, event):
        """子类必须实现具体的发送逻辑"""
        raise NotImplementedError("子类必须实现 _root_Entry_enter 方法")

    def _root_Entry_init(
        self, obj_root, obj_name, str_name, x, y, width_t, width, height, action,
        title='',
        mode='NONE'
    ):
        """通用输入框初始化（带标签，但标签通常不用）"""
        if title:
            self.UIObject[obj_name + '=Label'] = tkinter.Label(self.UIObject[obj_root], text=title)
            self.UIObject[obj_name + '=Label'].configure(bg=self.UIConfig['color_001'], fg=self.UIConfig['color_004'])
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root], textvariable=self.UIData[str_name], font=('TkDefaultFont 12')
        )
        self.UIObject[obj_name].configure(bg=self.UIConfig['color_004'], fg=self.UIConfig['color_005'], bd=0)
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(show='●')
        if width > 0:
            self.UIObject[obj_name].configure(width=width)

    def _root_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['root'], text=text, command=command, bd=0,
            activebackground=self.UIConfig['color_002'], activeforeground=self.UIConfig['color_001'],
            bg=self.UIConfig['color_003'], fg=self.UIConfig['color_004'], relief='groove', height=height
        )
        self.UIObject[name].bind('<Enter>', lambda e: self._button_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda e: self._button_action(name, '<Leave>'))

    def _button_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            elif action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def lift(self):
        self.UIObject['root'].lift()
        self.UIObject['root'].focus_force()

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        """子类可覆盖，用于从父窗口的数据结构中移除自己"""
        pass

    # ========== 日志相关方法（子类可覆盖） ==========
    def _tree_init_line(self):
        """加载历史日志，子类需实现具体从何处读取"""
        pass

    def tree_add_line(self, data, flagInit=False):
        """添加一行日志，子类可按需覆盖"""
        res_data = re.sub(r'\033\[[\d;]*m?', '', data)
        res_data = res_data.encode(encoding='gb2312', errors='replace').decode(encoding='gb2312', errors='replace')
        res_data_1 = res_data
        res_data = res_data.replace('\\', '\\\\').replace(' ', '\\ ')
        if len(res_data.replace('\\ ', '')) > 0:
            try:
                iid = self.UIObject['tree'].insert('', tkinter.END, text=res_data_1, values=(res_data,))
                keep_tree_thin(self.UIObject['tree'])
                if self.UIData.get('flag_tree_is_bottom', True):
                    self.UIObject['tree'].see(iid)
            except Exception:
                pass

    # ========== 浏览器辅助（子类可用） ==========
    def _show_url_webbrowser(self, url):
        res = tkinter.messagebox.askquestion("请完成验证", f"是否通过浏览器访问 \"{url}\" ?")
        try:
            if res == 'yes':
                webbrowser.open(url)
        except webbrowser.Error as error_info:
            tkinter.messagebox.showerror("webbrowser.Error", error_info)


# ---------------------------- 各子类实现 ----------------------------
class gocqhttpTerminalUI(BaseTerminalUI):
    WINDOW_TITLE = "GoCqhttp 终端"
    WINDOW_SIZE = "800x600"
    MIN_SIZE = (800, 600)

    def _root_Entry_enter(self, name, event):
        if name == 'root_input':
            input_data = self.UIData['root_input_StringVar'].get()
            if 0 <= len(input_data) < 1000:
                self.root.setGoCqhttpModelSend(self.bot.hash, input_data)
            self.UIData['root_input_StringVar'].set('')

    def _tree_init_line(self):
        if self.bot.hash in self.root.UIObject.get('root_gocqhttp_terminal_data', {}):
            for line in self.root.UIObject['root_gocqhttp_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit=True)

    def tree_add_line(self, data, flagInit=False):
        super().tree_add_line(data, flagInit)
        if not flagInit and platform.system() == 'Windows':
            try:
                # 处理腾讯滑块验证
                matchRes = re.match(
                    (
                        r'^\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\]\s\[WARNING\]:'
                        r'\s请前往该地址验证\s+->\s+(http[s]{0,1}://ti\.qq\.com/safe/tools/captcha/sms-verify-login\?[^\s]+).*$'
                    ),
                    data
                )
                if matchRes:
                    self._show_tx_url_webbrowser(matchRes.group(1))
                # 设备锁处理
                matchRes = re.match(
                    (
                        r'^\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\]\s\[WARNING\]:'
                        r'\s账号已开启设备锁，请前往\s+->\s+(http[s]{0,1}://accounts\.qq\.com/safe/verify[^\s]+).*$'
                    ),
                    data
                )
                if matchRes:
                    url = matchRes.group(1).replace('accounts.qq.com/safe/verify', 'accounts.qq.com/safe/qrcode')
                    self._show_url_webbrowser(url)
            except Exception:
                pass

    def _show_tx_url_webbrowser(self, url):
        res = tkinter.messagebox.askquestion("请完成验证", f"是否使用内置人机验证助手访问 \"{url}\" ?")
        try:
            if res == 'yes':
                # 调用外部模块，假设存在
                OlivOS.libEXEModelAPI.sendOpentxTuringTestPage(
                    control_queue=self.root.Proc_info.control_queue,
                    name=f'slider_verification_code={self.bot.hash}',
                    title='请完成验证',
                    url=url
                )
            else:
                webbrowser.open(url)
        except webbrowser.Error as error_info:
            tkinter.messagebox.showerror("webbrowser.Error", error_info)

    def exit(self):
        self.root.UIObject['root_gocqhttp_terminal'].pop(self.bot.hash, None)


class walleqTerminalUI(BaseTerminalUI):
    WINDOW_TITLE = "WalleQ 终端"
    WINDOW_SIZE = "800x600"

    def _root_Entry_enter(self, name, event):
        if name == 'root_input':
            input_data = self.UIData['root_input_StringVar'].get()
            if 0 <= len(input_data) < 1000:
                self.root.setWalleQModelSend(self.bot.hash, input_data)
            self.UIData['root_input_StringVar'].set('')

    def _tree_init_line(self):
        if self.bot.hash in self.root.UIObject.get('root_walleq_terminal_data', {}):
            for line in self.root.UIObject['root_walleq_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit=True)

    def tree_add_line(self, data, flagInit=False):
        super().tree_add_line(data, flagInit)
        if not flagInit and platform.system() == 'Windows':
            try:
                matchRes = re.match(
                    (
                        r'^\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\]\s\[WARNING\]:'
                        r'\s请前往该地址验证\s+->\s+(http[s]{0,1}://captcha\.go-cqhttp\.org/captcha\?[^\s]+).*$'
                    ),
                    data
                )
                if matchRes:
                    self._show_url_webbrowser(matchRes.group(1))
            except Exception:
                pass

    def exit(self):
        self.root.UIObject['root_walleq_terminal'].pop(self.bot.hash, None)


class CWCBTerminalUI(BaseTerminalUI):
    WINDOW_TITLE = "ComWeChatBotClient 终端"
    WINDOW_SIZE = "800x600"

    def _root_Entry_enter(self, name, event):
        if name == 'root_input':
            input_data = self.UIData['root_input_StringVar'].get()
            if 0 <= len(input_data) < 1000:
                self.root.setCWCBModelSend(self.bot.hash, input_data)
            self.UIData['root_input_StringVar'].set('')

    def _tree_init_line(self):
        if self.bot.hash in self.root.UIObject.get('root_cwcb_terminal_data', {}):
            for line in self.root.UIObject['root_cwcb_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit=True)

    def exit(self):
        self.root.UIObject['root_cwcb_terminal'].pop(self.bot.hash, None)


class opqbotTerminalUI(BaseTerminalUI):
    WINDOW_TITLE = "OPQBot 终端"
    WINDOW_SIZE = "800x600"

    def _root_Entry_enter(self, name, event):
        if name == 'root_input':
            input_data = self.UIData['root_input_StringVar'].get()
            if 0 <= len(input_data) < 1000:
                self.root.setOPQBotModelSend(self.bot.hash, input_data)
            self.UIData['root_input_StringVar'].set('')

    def _tree_init_line(self):
        if self.bot.hash in self.root.UIObject.get('root_opqbot_terminal_data', {}):
            for line in self.root.UIObject['root_opqbot_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit=True)

    def exit(self):
        self.root.UIObject['root_opqbot_terminal'].pop(self.bot.hash, None)


class napcatTerminalUI(BaseTerminalUI):
    WINDOW_TITLE = "NapCat 终端"
    WINDOW_SIZE = "800x600"

    def _root_Entry_enter(self, name, event):
        if name == 'root_input':
            input_data = self.UIData['root_input_StringVar'].get()
            if 0 <= len(input_data) < 1000:
                self.root.setNapCatModelSend(self.bot.hash, input_data)
            self.UIData['root_input_StringVar'].set('')

    def _tree_init_line(self):
        if self.bot.hash in self.root.UIObject.get('root_napcat_terminal_data', {}):
            for line in self.root.UIObject['root_napcat_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit=True)

    def exit(self):
        self.root.UIObject['root_napcat_terminal'].pop(self.bot.hash, None)


class OlivOSTerminalUI(BaseTerminalUI):
    WINDOW_TITLE = "OlivOS 终端"
    WINDOW_SIZE = "900x600"
    MIN_SIZE = (900, 600)
    COLUMN_WEIGHTS = [(0, 0), (1, 2), (2, 2), (3, 0)]
    HAS_SEND_BUTTON = False

    def __init__(self, Model_name, logger_proc=None, root=None, root_tk=None, bot=None):
        # OlivOS终端没有bot参数，但基类要求，我们忽略它
        super().__init__(Model_name, logger_proc, root, root_tk, bot)

    def get_window_title(self):
        # 假设 OlivOS.infoAPI.OlivOS_Version_Title 存在
        return f"{self.WINDOW_TITLE} - {OlivOS.infoAPI.OlivOS_Version_Title}"

    def _build_main_window(self):
        super()._build_main_window()
        self.UIObject['root'].bind('<Configure>', self._root_resize)

    def _build_tree(self):
        super()._build_tree()
        # 为树形视图添加日志等级标签颜色
        for level_this in OlivOS.diagnoseAPI.level_dict:
            self.UIObject['tree'].tag_configure(
                OlivOS.diagnoseAPI.level_dict[level_this],
                foreground=OlivOS.diagnoseAPI.level_color_dict[OlivOS.diagnoseAPI.level_dict[level_this]]
            )

    def _build_extra_controls(self):
        # 添加等级选择下拉框
        self._tree_edit_UI_Combobox_init(
            obj_root='root', obj_name='root_level', str_name='root_level_StringVar',
            x=15, y=self._get_input_y(), width_t=0, width=50, height=24,
            action=None, title='等级'
        )
        self.UIObject['root_level'].grid(
            row=1, column=0, sticky="ns", rowspan=1, columnspan=1,
            padx=(15, 8), pady=(9, 15), ipadx=0, ipady=0
        )
        self.UIData['level_list'] = []
        self.UIData['level_find'] = {}
        self.UIData['level_default'] = 'INFO'
        for level_this in OlivOS.diagnoseAPI.level_dict:
            level_name = OlivOS.diagnoseAPI.level_dict[level_this]
            self.UIData['level_list'].append(level_name)
            self.UIData['level_find'][level_name] = level_this
        self.UIObject['root_level']['value'] = tuple(self.UIData['level_list'])
        self.UIObject['root_level'].current(self.UIData['level_list'].index(self.UIData['level_default']))

    def _build_input_area(self):
        # 输入框占据第1列（共3列，tree占2列，这里需要调整）
        self._root_Entry_init(
            obj_root='root', obj_name='root_input', str_name='root_input_StringVar',
            x=15 + 70 + 8, y=self._get_input_y(), width_t=0, width=0,
            height=24, action=None, title='输入'
        )
        self.UIObject['root_input'].bind("<Return>", self._root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row=1, column=1, sticky="we", rowspan=1, columnspan=3,
            padx=(0, 15), pady=(8, 15), ipadx=0, ipady=2
        )

    def _root_Entry_enter(self, name, event):
        if name == 'root_input':
            input_data = self.UIData['root_input_StringVar'].get()
            if len(input_data) > 0:
                # 原代码中此处无实际操作，保留空实现
                pass
            self.UIData['root_input_StringVar'].set('')

    def _root_resize(self, event=None):
        pass

    def _tree_edit_UI_Combobox_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title=''):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(self.UIObject[obj_root], text=title)
        self.UIObject[obj_name + '=Label'].configure(bg=self.UIConfig['color_001'], fg=self.UIConfig['color_004'])
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = ttk.Combobox(self.UIObject[obj_root], textvariable=self.UIData[str_name])
        self.UIObject[obj_name].configure(state='readonly')

    def _tree_init_line(self):
        # 从 root 中读取历史日志
        tmp_count_old = 0
        tmp_count_new = len(self.root.UIObject.get('root_OlivOS_terminal_data', []))
        try:
            while tmp_count_old < tmp_count_new:
                for line in self.root.UIObject['root_OlivOS_terminal_data'][tmp_count_old:tmp_count_new]:
                    self.tree_add_line(line)
                tmp_count_old = tmp_count_new
                tmp_count_new = len(self.root.UIObject['root_OlivOS_terminal_data'])
        except Exception:
            pass

    def tree_add_line(self, data):
        """重写日志添加，支持等级过滤和带时间戳的格式"""
        data_raw = data['data']
        select_level = self.UIData['level_find'][self.UIData['root_level_StringVar'].get()]
        this_level = data_raw['log_level']
        if select_level <= this_level:
            data_str = data['str']
            data_str = data_str.encode(encoding='gbk', errors='replace').decode(encoding='gbk', errors='replace')
            # 处理转义
            data_str = data_str.replace('\r', '\\r').replace('\n', '\\n')
            log_level = OlivOS.diagnoseAPI.level_dict[data_raw['log_level']]
            time_str = datetime.datetime.fromtimestamp(int(data_raw['log_time'])).strftime("%Y-%m-%d %H:%M:%S")
            display_str = f"{time_str} - {log_level} - {data_str}"
            if len(display_str) > 0:
                try:
                    iid = self.UIObject['tree'].insert(
                        '', tkinter.END,
                        text=data_str,
                        values=(display_str,),
                        tag=log_level
                    )
                    keep_tree_thin(self.UIObject['tree'])
                    if self.UIData.get('flag_tree_is_bottom', True):
                        self.UIObject['tree'].see(iid)
                except Exception:
                    pass

    def stop(self):
        """手动关闭时给通知"""
        try:
            self.root.UIObject['root_shallow'].UIObject['shallow_root'].notify('已最小化至托盘')
        except Exception:
            pass
        super().stop()

    def exit(self):
        self.root.UIObject['root_OlivOS_terminal'] = None


class VirtualTerminalUI(BaseTerminalUI):
    WINDOW_TITLE = "Virtual Terminal 终端"
    WINDOW_SIZE = "800x600"

    def __init__(self, Model_name, logger_proc, root, root_tk=None, bot=None):
        super().__init__(Model_name, logger_proc, root, root_tk, bot)
        self.user_conf_data = {
            "user_name": "仑质", "user_id": "88888888", "flag_group": True,
            "group_id": "88888888", "group_role": "owner", "target_id": "88888888"
        }

    def _add_extra_menu_items(self):
        self.UIObject['tree_rightkey_menu'].add_command(label='编辑账号', command=lambda: self._rightKey_action('account'))

    def _rightKey_action(self, action: str):
        if action == 'account':
            self._root_AccountEdit_init()
        else:
            super()._rightKey_action(action)

    def _root_AccountEdit_init(self):
        existing = self.UIObject.get('root_terminal_account_edit')
        if existing is None:
            self.UIObject['root_terminal_account_edit'] = self._VirtualTerminalUI_AccountEdit(
                Model_name=self.Model_name, root=self, root_tk=self.root_tk, bot=self.bot
            )
            self.UIObject['root_terminal_account_edit'].start()
        else:
            existing.lift()

    def _root_Entry_enter(self, name, event):
        if name == 'root_input':
            input_data = self.UIData['root_input_StringVar'].get()
            if 0 < len(input_data) < 1000:
                self.root.setVirtualModelSend(self.bot.hash, input_data, self.user_conf_data)
            self.UIData['root_input_StringVar'].set('')

    def _tree_init_line(self):
        if self.bot.hash in self.root.UIObject.get('root_virtual_terminal_terminal_data', {}):
            for line in self.root.UIObject['root_virtual_terminal_terminal_data'][self.bot.hash]:
                self.tree_add_line(line)

    def tree_add_line(self, data, user_conf=None):
        """重写以显示用户信息头"""
        res_data = data['data']
        if user_conf is None:
            user_conf = data.get("user_conf", self.user_conf_data)
        res_data = res_data.encode(encoding='gb2312', errors='replace').decode(encoding='gb2312', errors='replace')
        res_data = res_data.replace('\r\n', '\n')
        if not user_conf['flag_group']:
            header = f"<{user_conf['user_name']}> ({user_conf['user_id']}) -> (用户: {user_conf['target_id']})"
        else:
            header = f"<{user_conf['user_name']}> ({user_conf['user_id']}) -> (群: {user_conf['target_id']})"
        header = header.replace('\r\n', '\n')
        full = f"{header}\n{res_data}\n{'-'*25}"
        for line in full.split('\n'):
            try:
                iid = self.UIObject['tree'].insert('', tkinter.END, text=line, values=(line,))
                keep_tree_thin(self.UIObject['tree'])
                if self.UIData.get('flag_tree_is_bottom', True):
                    self.UIObject['tree'].see(iid)
            except Exception:
                pass

    def exit(self):
        self.root.UIObject['root_virtual_terminal_terminal'].pop(self.bot.hash, None)

    # ---------- 内部类：账号编辑窗口 ----------
    class _VirtualTerminalUI_AccountEdit(BaseTerminalUI):
        """内部类，用于编辑虚拟账号信息，也继承基类以复用部分UI逻辑"""
        WINDOW_SIZE = "300x210"
        MIN_SIZE = (300, 210)
        HAS_SEND_BUTTON = False

        def __init__(self, Model_name, root: "VirtualTerminalUI", root_tk=None, bot=None):
            # 注意：这里的 root 是 VirtualTerminalUI 实例，不是外层的 dock
            super().__init__(Model_name, root.logger_proc, root, root_tk, bot)
            self.parent_virtual = root

        def start(self):
            self._build_main_window()
            self._init_style()
            self._build_edit_fields()
            self._build_save_button()
            self.UIObject['root'].mainloop()
            self.stop()

        def _build_main_window(self):
            self.UIObject['root'] = tkinter.Toplevel(
                master=self.parent_virtual.UIObject['root'],
                bg=self.UIConfig['color_001']
            )
            self.UIObject['root'].title(f'账号编辑 - {str(self.bot.id)}')
            self.UIObject['root'].geometry(self.WINDOW_SIZE)
            self.UIObject['root'].minsize(*self.MIN_SIZE)
            self.UIObject['root'].resizable(width=False, height=False)
            self.UIObject['root'].configure(bg=self.UIConfig['color_001'])
            self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        def _build_edit_fields(self):
            # 账号名称
            self._root_Entry_init(
                obj_root='root', obj_name='root_entry_user_name', str_name='StringVar_user_name',
                x=15+80, y=15+30*0, width_t=80, width=300-15*2-80, height=24,
                action=None, title='账号名称:\t'
            )
            # 账号ID
            self._root_Entry_init(
                obj_root='root', obj_name='root_entry_user_id', str_name='StringVar_user_id',
                x=15+80, y=15+30*1, width_t=80, width=300-15*2-80, height=24,
                action=None, title='账号ID:\t'
            )
            # 是否为群复选框
            self.UIData['BoolVar_flag_group'] = tkinter.BooleanVar()
            self._root_Checkbutton_init(
                obj_root='root', obj_name='root_checkbutton_flag_group', str_name='BoolVar_flag_group',
                x=15+80, y=15+30*2, width_t=80, width=300-15*2-80, height=24,
                action=lambda: self.UIData['BoolVar_flag_group'].set(not self.UIData['BoolVar_flag_group'].get()),
                title='是否为群:\t'
            )
            # 群组ID
            self._root_Entry_init(
                obj_root='root', obj_name='root_entry_group_id', str_name='StringVar_group_id',
                x=15+80, y=15+30*3, width_t=80, width=300-15*2-80, height=24,
                action=None, title='群组ID:\t'
            )
            # 群组角色下拉框
            self._root_ComboBox_init(
                obj_root='root', obj_name='root_combobox_group_role', str_name='StringVar_group_role',
                x=15+80, y=15+30*4, width_t=80, width=300-15*2-80, height=24,
                action=["owner", "admin", "member", "unknown"], title='群组角色:\t'
            )
            # 加载现有数据
            self._userConfDataInit(self.parent_virtual.user_conf_data)

        def _build_save_button(self):
            self._root_Button_init(
                name='root_button_save', text='保存并返回', command=self._save_and_close,
                x=15+80, y=15+30*5, width=300-15*2-80, height=24
            )
            self.UIObject['root_button_save'].place(x=15+80, y=15+30*5, width=300-15*2-80, height=24)

        def _init_style(self):
            self.UIData['style'] = ttk.Style(self.UIObject['root'])
            self.UIData['style'].configure(
                "TCheckbutton",
                indicatorbackground=self.UIConfig['color_001'],
                indicatorforeground=self.UIConfig['color_004'],
                background=self.UIConfig['color_001'],
                foreground=self.UIConfig['color_004']
            )

        def _root_Checkbutton_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title=''):
            # 简化版复选框初始化
            self.UIObject[obj_name + '=Label'] = tkinter.Label(self.UIObject[obj_root], text=title)
            self.UIObject[obj_name + '=Label'].configure(bg=self.UIConfig['color_001'], fg=self.UIConfig['color_004'])
            self.UIObject[obj_name + '=Label'].place(x=x-width_t, y=y, width=width_t, height=height)
            self.UIObject[obj_name] = ttk.Checkbutton(
                self.UIObject[obj_root],
                variable=self.UIData[str_name],
                onvalue=True,
                offvalue=False,
                style='TCheckbutton'
            )
            self.UIObject[obj_name].place(x=x, y=y)

        def _root_ComboBox_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title=''):
            self.UIObject[obj_name + '=Label'] = tkinter.Label(self.UIObject[obj_root], text=title)
            self.UIObject[obj_name + '=Label'].configure(bg=self.UIConfig['color_001'], fg=self.UIConfig['color_004'])
            self.UIObject[obj_name + '=Label'].place(x=x-width_t, y=y, width=width_t, height=height)
            self.UIData[str_name] = tkinter.StringVar()
            self.UIObject[obj_name] = ttk.Combobox(
                self.UIObject[obj_root], textvariable=self.UIData[str_name], values=action, state='readonly'
            )
            self.UIObject[obj_name].place(x=x, y=y, width=width, height=height)

        def _root_Entry_init(
            self, obj_root, obj_name, str_name, x, y, width_t, width, height, action,
            title='',
            mode='NONE'
        ):
            # 带标签的Entry
            self.UIObject[obj_name + '=Label'] = tkinter.Label(self.UIObject[obj_root], text=title)
            self.UIObject[obj_name + '=Label'].configure(bg=self.UIConfig['color_001'], fg=self.UIConfig['color_004'])
            self.UIObject[obj_name + '=Label'].place(x=x-width_t, y=y, width=width_t, height=height)
            self.UIData[str_name] = tkinter.StringVar()
            self.UIObject[obj_name] = tkinter.Entry(self.UIObject[obj_root], textvariable=self.UIData[str_name])
            self.UIObject[obj_name].configure(bg=self.UIConfig['color_004'], fg=self.UIConfig['color_005'], bd=0)
            if mode == 'SAFE':
                self.UIObject[obj_name].configure(show='●')
            self.UIObject[obj_name].place(x=x, y=y, width=width, height=height)

        def _userConfDataInit(self, datadict):
            """加载用户数据到界面"""
            self.UIData['StringVar_user_name'].set(datadict['user_name'])
            self.UIData['StringVar_user_id'].set(datadict['user_id'])
            self.UIData['BoolVar_flag_group'].set(datadict['flag_group'])
            self.UIData['StringVar_group_id'].set(datadict['group_id'])
            self.UIData['StringVar_group_role'].set(datadict['group_role'])

        def _save_and_close(self):
            """保存修改并关闭"""
            tmp = {
                'user_name': self.UIData['StringVar_user_name'].get(),
                'user_id': self.UIData['StringVar_user_id'].get(),
                'flag_group': self.UIData['BoolVar_flag_group'].get(),
                'group_id': self.UIData['StringVar_group_id'].get(),
                'group_role': self.UIData['StringVar_group_role'].get(),
            }
            tmp['target_id'] = tmp['group_id'] if tmp['flag_group'] else self.bot.id
            self.parent_virtual.user_conf_data = tmp
            self.stop()

        def _root_Button_init(self, name, text, command, x, y, width, height):
            # 使用place布局的按钮
            self.UIObject[name] = tkinter.Button(
                self.UIObject['root'], text=text, command=command, bd=0,
                activebackground=self.UIConfig['color_002'], activeforeground=self.UIConfig['color_001'],
                bg=self.UIConfig['color_003'], fg=self.UIConfig['color_004'], relief='groove'
            )
            self.UIObject[name].bind('<Enter>', lambda e: self._button_action(name, '<Enter>'))
            self.UIObject[name].bind('<Leave>', lambda e: self._button_action(name, '<Leave>'))
            self.UIObject[name].place(x=x, y=y, width=width, height=height)

        def _button_action(self, name, action):
            if name in self.UIObject:
                if action == '<Enter>':
                    self.UIObject[name].configure(bg=self.UIConfig['color_006'])
                elif action == '<Leave>':
                    self.UIObject[name].configure(bg=self.UIConfig['color_003'])

        def stop(self):
            self.exit()
            if self.UIObject.get('root'):
                self.UIObject['root'].destroy()

        def exit(self):
            self.parent_virtual.UIObject["root_terminal_account_edit"] = None


class shallow(object):
    def __init__(self, name: str, image: str, root: 'dock'):
        self.name = name
        self.image = image
        self.root = root
        self.UIObject = {}
        self.UIData = {'shallow_menu_list': None}
        self.UIObject['shallow_menu'] = None

    def refresh(self):
        self.refreshData()
        if 'shallow_root' in self.UIObject:
            self.UIObject['shallow_root'].menu = self.UIObject['shallow_menu']

    def refreshData(self):
        if 'shallow_menu_list' in self.root.UIData:
            self.UIData['shallow_menu_list'] = self.root.UIData['shallow_menu_list']
        self.UIObject['shallow_menu'] = self.getMenu(self.UIData['shallow_menu_list'])

    def getMenu(self, data):
        if data is None:
            return None
        elif not type(data) is list:
            return data
        else:
            list_new = []
            for item_this in data:
                if not type(item_this) is list:
                    pass
                # 处理账号信息项（禁用）
                elif len(item_this) == 3 and item_this[0] == 'account_info':
                    list_new.append(
                        pystray.MenuItem(
                            item_this[1],
                            None,
                            enabled=True
                        )
                    )
                # 处理账号菜单项（根据账号数量决定是否禁用）
                elif len(item_this) == 4 and item_this[0] == 'account_menu':
                    account_count = item_this[3]
                    tmp_sub_menu = self.getMenu(item_this[2])
                    menu_enabled = (tmp_sub_menu not in [None, False]) and account_count > 0
                    list_new.append(
                        pystray.MenuItem(
                            item_this[1],
                            tmp_sub_menu,
                            enabled=menu_enabled
                        )
                    )
                elif len(item_this) == 1 and item_this[0] == 'SEPARATOR':
                    list_new.append(pystray.Menu.SEPARATOR)
                elif len(item_this) == 2:
                    tmp_sub_menu = self.getMenu(item_this[1])
                    list_new.append(
                        pystray.MenuItem(
                            item_this[0],
                            tmp_sub_menu,
                            enabled=(tmp_sub_menu not in [None, False]),
                            default=(item_this[0] in ['打开终端'])
                        )
                    )
                elif (
                    len(item_this) == 3
                    and type(item_this[1]) is str
                    and type(item_this[2]) is str
                ):
                    list_new.append(
                        pystray.MenuItem(
                            item_this[0],
                            self.root.sendPluginControlEventFunc(
                                item_this[1],
                                item_this[2]
                            )
                        )
                    )
                elif (
                    len(item_this) == 4
                    and type(item_this[1]) is str
                    and type(item_this[2]) is str
                    and type(item_this[3]) is str
                ):
                    if item_this[3] == 'gocqhttp':
                        list_new.append(
                            pystray.MenuItem(
                                item_this[0],
                                self.root.startGoCqhttpTerminalUISendFunc(
                                    item_this[1]
                                )
                            )
                        )
                    elif item_this[3] == 'walleq':
                        list_new.append(
                            pystray.MenuItem(
                                item_this[0],
                                self.root.startWalleQTerminalUISendFunc(
                                    item_this[1]
                                )
                            )
                        )
                    elif item_this[3] == 'ComWeChatBotClient':
                        list_new.append(
                            pystray.MenuItem(
                                item_this[0],
                                self.root.startCWCBTerminalUISendFunc(
                                    item_this[1]
                                )
                            )
                        )
                    elif item_this[3] == 'opqbot':
                        list_new.append(
                            pystray.MenuItem(
                                item_this[0],
                                self.root.startOPQBotTerminalUISendFunc(
                                    item_this[1]
                                )
                            )
                        )
                    elif item_this[3] == 'virtual_terminal':
                        list_new.append(
                            pystray.MenuItem(
                                item_this[0],
                                self.root.startVirtualTerminalUISendFunc(
                                    item_this[1]
                                )
                            )
                        )
                    elif item_this[3] == 'napcat':
                        list_new.append(
                            pystray.MenuItem(
                                item_this[0],
                                self.root.startNapCatTerminalUISendFunc(
                                    item_this[1]
                                )
                            )
                        )
            if len(list_new) > 0:
                return pystray.Menu(*list_new)
            else:
                return None

    def start(self):
        image = Image.open(self.image)
        self.refreshData()
        self.UIObject['shallow_root'] = pystray.Icon(
            name=self.name,
            icon=image,
            title=self.name,
            menu=self.UIObject['shallow_menu']
        )
        self.UIObject['shallow_root'].run_detached()


class pluginManageUI(object):
    def __init__(self, Model_name, logger_proc=None, root=None, key=None):
        self.Model_name = Model_name
        self.root = root
        self.key = key
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIData['flag_commit'] = False
        self.UIData['click_record'] = {}
        self.UIData['show_path'] = False  # 默认不显示路径
        self.UIData['item_namespace_map'] = {}
        self.UIConfig.update(dictColorContext)

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('OlivOS 插件管理器')
        self.UIObject['root'].geometry('680x500')
        self.UIObject['root'].resizable(
            width=False,
            height=False
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

        self.tree_init()

        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient="vertical",
            command=self.UIObject['tree'].yview
        )
        self.UIObject['tree_yscroll'].place(
            x=15 + 500 - 18,
            y=15,
            width=18,
            height=470 - 1
        )
        self.UIObject['tree'].configure(
            yscrollcommand=self.UIObject['tree_yscroll'].set
        )

        self.tree_UI_Label_init(
            name='root_Label_PRIORITY_title',
            title='root_Label_PRIORITY_title_StringVar',
            x=525,
            y=15,
            width=140,
            height=20
        )
        self.UIData['root_Label_PRIORITY_title_StringVar'].set('优先级')

        self.tree_UI_Label_init(
            name='root_Label_PRIORITY',
            title='root_Label_PRIORITY_StringVar',
            x=530,
            y=35,
            width=140,
            height=20
        )
        self.UIData['root_Label_PRIORITY_StringVar'].set('N/A')

        self.tree_UI_Label_init(
            name='root_Label_INFO_title',
            title='root_Label_INFO_title_StringVar',
            x=525,
            y=65,
            width=140,
            height=20
        )
        self.UIData['root_Label_INFO_title_StringVar'].set('介绍')

        self.tree_UI_Label_init(
            name='root_Label_INFO',
            title='root_Label_INFO_StringVar',
            x=530,
            y=85,
            width=140,
            height=300
        )
        self.UIData['root_Label_INFO_StringVar'].set('未选定插件')

        self.tree_UI_Button_init(
            name='root_Button_RESTART',
            text='重载插件',
            command=lambda: self.sendPluginRestart(),
            x=530,
            y=(500 - 34 - 15 - 40 * 2),
            width=140,
            height=34
        )

        self.tree_UI_Button_init(
            name='root_Button_TOGGLE_MODE',
            text='切换显示',
            command=lambda: self.toggleDisplayMode(),
            x=530,
            y=(500 - 34 - 15 - 40 * 1),
            width=140,
            height=34
        )

        self.tree_UI_Button_init(
            name='root_Button_MENU',
            text='插件菜单',
            command=lambda: self.pluginMenu('root_Button_MENU'),
            x=530,
            y=(500 - 34 - 15 - 40 * 0),
            width=140,
            height=34
        )

        # self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.exit)

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        self.UIObject['root'].mainloop()

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_plugin_edit'].pop(self.key)

    def lift(self):
        self.UIObject['root'].lift()

    def tree_init(self):
        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        # 默认不显示路径列
        self.UIObject['tree']['columns'] = ('NAME', 'VERSION', 'AUTHOR')
        self.UIObject['tree'].column('NAME', width=220)
        self.UIObject['tree'].column('VERSION', width=130)
        self.UIObject['tree'].column('AUTHOR', width=130)
        self.UIObject['tree'].heading('NAME', text='插件')
        self.UIObject['tree'].heading('VERSION', text='版本')
        self.UIObject['tree'].heading('AUTHOR', text='作者')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['tree'].bind('<<TreeviewSelect>>', lambda x: self.treeSelect('tree', x))
        self.tree_load()
        self.UIObject['tree'].place(x=15, y=15, width=500 - 18, height=470)

    def tree_load(self):
        tmp_tree_item_children = self.UIObject['tree'].get_children()
        for tmp_tree_item_this in tmp_tree_item_children:
            self.UIObject['tree'].delete(tmp_tree_item_this)

        # 清空映射表
        self.UIData['item_namespace_map'] = {}

        if self.root is not None:
            if self.root.UIData['shallow_plugin_data_dict'] is not None:
                tmp_plugin_menu_dict = self.root.UIData['shallow_plugin_data_dict']

                # 收集所有插件并按优先级排序
                plugin_list = []
                for plugin_namespace in tmp_plugin_menu_dict:
                    plugin_this = tmp_plugin_menu_dict[plugin_namespace]
                    priority = plugin_this[6] if len(plugin_this) > 6 else 10000
                    folder_path = plugin_this[5] if len(plugin_this) > 5 else ''
                    # 规范化路径
                    folder_path = folder_path.replace('\\', '/')

                    # 构建完整路径
                    if folder_path:
                        full_path = '/' + folder_path + '/' + os.path.basename(plugin_namespace)
                    else:
                        full_path = '/' + os.path.basename(plugin_namespace)

                    plugin_list.append({
                        'namespace': plugin_namespace,
                        'name': plugin_this[0],
                        'version': plugin_this[1],
                        'author': plugin_this[2],
                        'priority': priority,
                        'full_path': full_path
                    })

                # 按优先级排序
                sorted_plugins = sorted(plugin_list, key=lambda x: x['priority'])

                # 插入到树中
                for plugin_data in sorted_plugins:
                    if self.UIData['show_path']:
                        # 显示路径模式:PATH, NAME, VERSION, AUTHOR
                        item_id = self.UIObject['tree'].insert(
                            '',
                            tkinter.END,
                            text=plugin_data['namespace'],
                            values=(
                                plugin_data['full_path'],
                                plugin_data['name'],
                                plugin_data['version'],
                                plugin_data['author']
                            )
                        )
                    else:
                        # 不显示路径模式:NAME, VERSION, AUTHOR
                        item_id = self.UIObject['tree'].insert(
                            '',
                            tkinter.END,
                            text=plugin_data['namespace'],
                            values=(
                                plugin_data['name'],
                                plugin_data['version'],
                                plugin_data['author']
                            )
                        )
                    self.UIData['item_namespace_map'][item_id] = plugin_data['namespace']

    def toggleDisplayMode(self):
        """切换显示/隐藏路径列"""
        if self.UIData['show_path']:
            # 当前显示路径,切换为隐藏 - 移除PATH列
            self.UIData['show_path'] = False
            self.UIObject['tree']['columns'] = ('NAME', 'VERSION', 'AUTHOR')
            self.UIObject['tree'].heading('NAME', text='插件')
            self.UIObject['tree'].heading('VERSION', text='版本')
            self.UIObject['tree'].heading('AUTHOR', text='作者')
            self.UIObject['tree'].column('NAME', width=220)
            self.UIObject['tree'].column('VERSION', width=130)
            self.UIObject['tree'].column('AUTHOR', width=130)
        else:
            # 当前隐藏路径,切换为显示 - 添加PATH列
            self.UIData['show_path'] = True
            self.UIObject['tree']['columns'] = ('PATH', 'NAME', 'VERSION', 'AUTHOR')
            self.UIObject['tree'].heading('PATH', text='路径')
            self.UIObject['tree'].heading('NAME', text='插件')
            self.UIObject['tree'].heading('VERSION', text='版本')
            self.UIObject['tree'].heading('AUTHOR', text='作者')
            self.UIObject['tree'].column('PATH', width=150)
            self.UIObject['tree'].column('NAME', width=120)
            self.UIObject['tree'].column('VERSION', width=120)
            self.UIObject['tree'].column('AUTHOR', width=90)

        # 重新加载插件列表以应用新的列配置
        self.tree_load()

    def tree_UI_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['root'],
            text=text,
            command=command,
            bd=0,
            activebackground=self.UIConfig['color_002'],
            activeforeground=self.UIConfig['color_001'],
            bg=self.UIConfig['color_003'],
            fg=self.UIConfig['color_004'],
            relief='groove'
        )
        self.UIObject[name].bind('<Enter>', lambda x: self.buttom_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda x: self.buttom_action(name, '<Leave>'))
        self.UIObject[name].bind('<Button-1>', lambda x: self.clickRecord(name, x))
        self.UIObject[name].place(
            x=x,
            y=y,
            width=width,
            height=height
        )

    def tree_UI_Label_init(self, name, title, x, y, width, height):
        self.UIData[title] = tkinter.StringVar()
        self.UIObject[name] = tkinter.Label(
            self.UIObject['root'],
            text='N/A',
            textvariable=self.UIData[title],
            wraplength=width - 4
        )
        self.UIObject[name].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004'],
            justify='left',
            anchor='nw'
        )
        self.UIObject[name].place(
            x=x,
            y=y,
            width=width,
            height=height
        )

    def sendPluginRestart(self):
        self.root.sendPluginRestart()

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def treeSelect(self, name, event):
        if name == 'tree':
            selected_item = self.UIObject['tree'].focus()
            if not selected_item:
                return

            # 从映射表获取插件的 namespace
            plugin_namespace_now = self.UIData['item_namespace_map'].get(selected_item, None)
            if not plugin_namespace_now:
                self.UIData['root_Label_PRIORITY_StringVar'].set('N/A')
                self.UIData['root_Label_INFO_StringVar'].set('未找到插件信息')
                return

            tmp_info_str = '这个插件的作者很懒，没有写介绍。'
            tmp_priority_str = 'N/A'
            if plugin_namespace_now in self.root.UIData['shallow_plugin_data_dict']:
                plugin_menu_now = self.root.UIData['shallow_plugin_data_dict'][plugin_namespace_now]
                # 获取优先级
                if len(plugin_menu_now) > 6:
                    tmp_priority_str = str(plugin_menu_now[6])
                # 获取介绍
                if type(plugin_menu_now[4]) is str:
                    if plugin_menu_now[4] != 'N/A':
                        tmp_info_str = plugin_menu_now[4]

            self.UIData['root_Label_PRIORITY_StringVar'].set(tmp_priority_str)
            self.UIData['root_Label_INFO_StringVar'].set(tmp_info_str)

    def clickRecord(self, name, event):
        self.UIData['click_record'][name] = event

    def pluginMenu(self, name):
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)

        selected_item = self.UIObject['tree'].focus()
        if not selected_item:
            self.UIObject['tree_rightkey_menu'].add_command(label='未选定插件', command=None)
            self.UIObject['tree_rightkey_menu'].post(
                self.UIData['click_record'][name].x_root,
                self.UIData['click_record'][name].y_root
            )
            return

        # 从映射表获取插件的 namespace
        plugin_namespace_now = self.UIData['item_namespace_map'].get(selected_item, None)

        if plugin_namespace_now and plugin_namespace_now in self.root.UIData['shallow_plugin_data_dict']:
            plugin_menu_now = self.root.UIData['shallow_plugin_data_dict'][plugin_namespace_now]
            if type(plugin_menu_now[3]) is list:
                for plugin_menu_this in plugin_menu_now[3]:
                    self.UIObject['tree_rightkey_menu'].add_command(
                        label=plugin_menu_this[0],
                        command=self.root.sendPluginControlEventFunc(
                            plugin_menu_this[1],
                            plugin_menu_this[2]
                        )
                    )
            else:
                self.UIObject['tree_rightkey_menu'].add_command(label='无选项', command=None)
        else:
            self.UIObject['tree_rightkey_menu'].add_command(label='未找到插件', command=None)

        self.UIObject['tree_rightkey_menu'].post(
            self.UIData['click_record'][name].x_root,
            self.UIData['click_record'][name].y_root
        )


def get_tree_force(tree_obj: ttk.Treeview):
    return tree_obj.item(tree_obj.focus())


# 此函数用于确保传入的tree组件的条目数不超过指定数目
def keep_tree_thin(tree_obj: ttk.Treeview, max_num: int = gTerminalDataMax, step_num: int = gTerminalDataStep):
    items = tree_obj.get_children()
    if len(items) > max_num:
        for i in range(min(max_num, step_num)):
            tree_obj.delete(items[i])


def releaseBase64Data(dir_path, file_name, base64_data):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    with open(dir_path + '/' + file_name, 'wb+') as tmp:
        tmp.write(base64.b64decode(base64_data))


# 修复 tkinter 8.6.9 的Treeview颜色bug，后续升级Python版本与配套Tkinter版本后可以移除
# 目前已知Python 3.10.4 中 tkinter 8.6.12 已修复
# https://core.tcl-lang.org/tk/info/509cafafae
def fix_Treeview_color(style):
    def fixed_map(option, style_in):
        # Returns the style map for 'option' with any styles starting with
        # ("!disabled", "!selected", ...) filtered out
        # style.map() returns an empty list for missing options, so this should
        # be future-safe
        return [elm for elm in style_in.map("Treeview", query_opt=option)
                if elm[:2] != ("!disabled", "!selected")]

    style.map(
        'Treeview',
        foreground=fixed_map('foreground', style),
        background=fixed_map('background', style)
    )
