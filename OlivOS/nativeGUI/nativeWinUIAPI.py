# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/nativeWinUIAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

import OlivOS

import base64
import os
import time
import threading
import pystray
import tkinter
import re
import datetime
import webbrowser
import platform
import traceback

from PIL import Image
from PIL import ImageTk

from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog

dictColorContext = {
    'color_001': '#00A0EA',
    'color_002': '#BBE9FF',
    'color_003': '#40C3FF',
    'color_004': '#FFFFFF',
    'color_005': '#000000',
    'color_006': '#80D7FF'
}

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
        self.UIObject = {}
        self.UIData = {}
        self.UIObject['root_window_on'] = False
        self.UIObject['root_shallow'] = None
        self.UIObject['root_OlivOS_terminal'] = None
        self.UIObject['root_OlivOS_terminal_data'] = []
        self.UIObject['root_OlivOS_terminal_data_max'] = 500
        self.UIObject['root_gocqhttp_terminal'] = {}
        self.UIObject['root_gocqhttp_terminal_data'] = {}
        self.UIObject['root_gocqhttp_terminal_data_max'] = 500
        self.UIObject['root_walleq_terminal'] = {}
        self.UIObject['root_walleq_terminal_data'] = {}
        self.UIObject['root_walleq_terminal_data_max'] = 500
        self.UIObject['root_cwcb_terminal'] = {}
        self.UIObject['root_cwcb_terminal_data'] = {}
        self.UIObject['root_cwcb_terminal_data_max'] = 500
        self.UIObject['root_opqbot_terminal'] = {}
        self.UIObject['root_opqbot_terminal_data'] = {}
        self.UIObject['root_opqbot_terminal_data_max'] = 500
        self.UIObject['root_napcat_terminal'] = {}
        self.UIObject['root_napcat_terminal_data'] = {}
        self.UIObject['root_napcat_terminal_data_max'] = 500
        self.UIObject['root_virtual_terminal_terminal'] = {}
        self.UIObject['root_virtual_terminal_terminal_data'] = {}
        self.UIObject['root_virtual_terminal_terminal_data_max'] = 150
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
                if type(packet.key) is dict \
                and 'data' in packet.key \
                and type(packet.key['data']) \
                and 'action' in packet.key['data']:
                    if 'account_update' == packet.key['data']['action']:
                        if 'data' in packet.key['data'] \
                        and type(packet.key['data']['data']) is dict:
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
        self.UIObject['main_tk'].after(50, self.process_msg)
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
                time.sleep(self.Proc_info.scan_interval)
            else:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block=False)
                except:
                    rx_packet_data = None
                if rx_packet_data is not None:
                    if type(rx_packet_data) == OlivOS.API.Control.packet:
                        if rx_packet_data.action == 'send':
                            if type(rx_packet_data.key) == dict:
                                if 'data' in rx_packet_data.key:
                                    if 'action' in rx_packet_data.key['data']:
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
                                            if 'event' in rx_packet_data.key['data'] \
                                            and 'account_edit_on' == rx_packet_data.key['data']['event'] \
                                            and 'bot_info' in rx_packet_data.key['data'] \
                                            and type(rx_packet_data.key['data']['bot_info']) is dict:
                                                OlivOS.multiLoginUIAPI.run_HostUI_asayc(
                                                    plugin_bot_info_dict=rx_packet_data.key['data']['bot_info'],
                                                    control_queue=self.Proc_info.control_queue
                                                )
                                        elif 'plugin_edit_menu_on' == rx_packet_data.key['data']['action']:
                                            self.startPluginEdit()
                                        elif 'logger' == rx_packet_data.key['data']['action']:
                                            self.UIObject['root_OlivOS_terminal_data'].append(
                                                rx_packet_data.key['data']['data'])
                                            if len(self.UIObject['root_OlivOS_terminal_data']) > self.UIObject[
                                                'root_OlivOS_terminal_data_max']:
                                                self.UIObject['root_OlivOS_terminal_data'].pop(0)
                                            if self.UIObject['root_OlivOS_terminal'] is not None:
                                                self.UIObject['root_OlivOS_terminal'].tree_add_line(
                                                    rx_packet_data.key['data']['data'])
                                        elif 'napcat' == rx_packet_data.key['data']['action']:
                                            if 'event' in rx_packet_data.key['data']:
                                                if 'init' == rx_packet_data.key['data']['event']:
                                                    if self.UIData['shallow_napcat_menu_list'] is None:
                                                        self.UIData['shallow_napcat_menu_list'] = []
                                                    if 'hash' in rx_packet_data.key['data']:
                                                        if rx_packet_data.key['data']['hash'] in self.bot_info:
                                                            tmp_title = '%s' % (
                                                                str(self.bot_info[rx_packet_data.key['data']['hash']].id)
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
                                                    if 'hash' in rx_packet_data.key['data'] and 'data' in \
                                                            rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash not in self.UIObject['root_napcat_terminal_data']:
                                                            self.UIObject['root_napcat_terminal_data'][hash] = []
                                                        self.UIObject['root_napcat_terminal_data'][hash].append(
                                                            rx_packet_data.key['data']['data'])
                                                        if len(self.UIObject['root_napcat_terminal_data'][hash]) > \
                                                                self.UIObject['root_napcat_terminal_data_max']:
                                                            self.UIObject['root_napcat_terminal_data'][hash].pop(0)
                                                        if hash in self.UIObject['root_napcat_terminal']:
                                                            self.UIObject['root_napcat_terminal'][hash].tree_add_line(
                                                                rx_packet_data.key['data']['data'])
                                                elif 'qrcode' == rx_packet_data.key['data']['event']:
                                                    if 'hash' in rx_packet_data.key['data'] and 'path' in \
                                                            rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash in self.bot_info:
                                                            if hash in self.UIObject['root_qrcode_window']:
                                                                try:
                                                                    self.UIObject['root_qrcode_window'][hash].stop()
                                                                except:
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
                                                                str(self.bot_info[rx_packet_data.key['data']['hash']].id)
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
                                                    if 'hash' in rx_packet_data.key['data'] and 'data' in \
                                                            rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash not in self.UIObject['root_gocqhttp_terminal_data']:
                                                            self.UIObject['root_gocqhttp_terminal_data'][hash] = []
                                                        self.UIObject['root_gocqhttp_terminal_data'][hash].append(
                                                            rx_packet_data.key['data']['data'])
                                                        if len(self.UIObject['root_gocqhttp_terminal_data'][hash]) > \
                                                                self.UIObject['root_gocqhttp_terminal_data_max']:
                                                            self.UIObject['root_gocqhttp_terminal_data'][hash].pop(0)
                                                        if hash in self.UIObject['root_gocqhttp_terminal']:
                                                            self.UIObject['root_gocqhttp_terminal'][hash].tree_add_line(
                                                                rx_packet_data.key['data']['data'])
                                                elif 'qrcode' == rx_packet_data.key['data']['event']:
                                                    if 'hash' in rx_packet_data.key['data'] and 'path' in \
                                                            rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash in self.bot_info:
                                                            if hash in self.UIObject['root_qrcode_window']:
                                                                try:
                                                                    self.UIObject['root_qrcode_window'][hash].stop()
                                                                except:
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
                                                    if 'hash' in rx_packet_data.key['data'] \
                                                    and 'token' in rx_packet_data.key['data']:
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
                                                                str(self.bot_info[rx_packet_data.key['data']['hash']].id)
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
                                                    if 'hash' in rx_packet_data.key['data'] and 'data' in \
                                                            rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash not in self.UIObject['root_walleq_terminal_data']:
                                                            self.UIObject['root_walleq_terminal_data'][hash] = []
                                                        self.UIObject['root_walleq_terminal_data'][hash].append(
                                                            rx_packet_data.key['data']['data'])
                                                        if len(self.UIObject['root_walleq_terminal_data'][hash]) > \
                                                                self.UIObject['root_walleq_terminal_data_max']:
                                                            self.UIObject['root_walleq_terminal_data'][hash].pop(0)
                                                        if hash in self.UIObject['root_walleq_terminal']:
                                                            self.UIObject['root_walleq_terminal'][hash].tree_add_line(
                                                                rx_packet_data.key['data']['data'])
                                                elif 'qrcode' == rx_packet_data.key['data']['event']:
                                                    if 'hash' in rx_packet_data.key['data'] and 'path' in \
                                                            rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash in self.bot_info:
                                                            if hash in self.UIObject['root_qrcode_window']:
                                                                try:
                                                                    self.UIObject['root_qrcode_window'][hash].stop()
                                                                except:
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
                                                                str(self.bot_info[rx_packet_data.key['data']['hash']].id)
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
                                                    if 'hash' in rx_packet_data.key['data'] and 'data' in \
                                                            rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash not in self.UIObject['root_cwcb_terminal_data']:
                                                            self.UIObject['root_cwcb_terminal_data'][hash] = []
                                                        self.UIObject['root_cwcb_terminal_data'][hash].append(
                                                            rx_packet_data.key['data']['data'])
                                                        if len(self.UIObject['root_cwcb_terminal_data'][hash]) > \
                                                                self.UIObject['root_cwcb_terminal_data_max']:
                                                            self.UIObject['root_cwcb_terminal_data'][hash].pop(0)
                                                        if hash in self.UIObject['root_cwcb_terminal']:
                                                            self.UIObject['root_cwcb_terminal'][hash].tree_add_line(
                                                                rx_packet_data.key['data']['data'])
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
                                                                str(self.bot_info[rx_packet_data.key['data']['hash']].id)
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
                                                    if 'hash' in rx_packet_data.key['data'] and 'data' in \
                                                            rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash not in self.UIObject['root_opqbot_terminal_data']:
                                                            self.UIObject['root_opqbot_terminal_data'][hash] = []
                                                        self.UIObject['root_opqbot_terminal_data'][hash].append(
                                                            rx_packet_data.key['data']['data'])
                                                        if len(self.UIObject['root_opqbot_terminal_data'][hash]) > \
                                                                self.UIObject['root_opqbot_terminal_data_max']:
                                                            self.UIObject['root_opqbot_terminal_data'][hash].pop(0)
                                                        if hash in self.UIObject['root_opqbot_terminal']:
                                                            self.UIObject['root_opqbot_terminal'][hash].tree_add_line(
                                                                rx_packet_data.key['data']['data'])
                                                elif 'qrcode' == rx_packet_data.key['data']['event']:
                                                    if 'hash' in rx_packet_data.key['data'] \
                                                    and 'path' in rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        path = rx_packet_data.key['data']['path']
                                                        #print(rx_packet_data.key['data'])
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
                                                                str(self.bot_info[rx_packet_data.key['data']['hash']].id)
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
                                                    if 'hash' in rx_packet_data.key['data'] and 'data' in \
                                                            rx_packet_data.key['data'] and 'name' in rx_packet_data.key[
                                                        'data']:
                                                        user_conf = {
                                                            "user_name": "未知",
                                                            "user_id": "-1",
                                                            "flag_group": True,
                                                            "target_id": "-1",
                                                            "group_role": "member",
                                                        }
                                                        if "user_conf" in rx_packet_data.key['data'] and rx_packet_data.key['data']["user_conf"] is not None:
                                                            user_conf.update(rx_packet_data.key['data']["user_conf"])
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash not in self.UIObject[
                                                            'root_virtual_terminal_terminal_data']:
                                                            self.UIObject['root_virtual_terminal_terminal_data'][
                                                                hash] = []
                                                        self.UIObject['root_virtual_terminal_terminal_data'][
                                                            hash].append(rx_packet_data.key['data'])
                                                        if len(self.UIObject['root_virtual_terminal_terminal_data'][
                                                                   hash]) > self.UIObject[
                                                            'root_virtual_terminal_terminal_data_max']:
                                                            self.UIObject['root_virtual_terminal_terminal_data'][
                                                                hash].pop(0)
                                                        if hash in self.UIObject['root_virtual_terminal_terminal']:
                                                            self.UIObject['root_virtual_terminal_terminal'][
                                                                hash].tree_add_line(rx_packet_data.key['data'], user_conf)
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
                server_auto = str(bot_info.post_info.auto) if hasattr(bot_info, 'post_info') and hasattr(bot_info.post_info, 'auto') else 'False'
                server_type = str(bot_info.post_info.type) if hasattr(bot_info, 'post_info') and hasattr(bot_info.post_info, 'type') else 'post'
                
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
                            if list_data_check[list_data_check_i] != str(OlivOS.accountMetadataAPI.accountTypeMappingList[type_this][list_data_check_i]):
                                flag_hit = False
                                break
                        if flag_hit:
                            return type_this
                # 如果找不到完全匹配，尝试只匹配前三个参数（platform, sdk, model）
                for type_this in OlivOS.accountMetadataAPI.accountTypeList:
                    if type_this in OlivOS.accountMetadataAPI.accountTypeMappingList:
                        mapping = OlivOS.accountMetadataAPI.accountTypeMappingList[type_this]
                        if (len(mapping) >= 3 and 
                            str(mapping[0]) == platform_platform and 
                            str(mapping[1]) == platform_sdk and 
                            str(mapping[2]) == platform_model):
                            return type_this
        except:
            pass
        return '自定义'
    
    def getAccountDisplayInfo(self, botHash, bot_info, flagInit = False):
        """
        获取账号显示信息（名称和协议端）
        """
        account_name = "未知账号"
        try:
            account_name = str(bot_info.id)
        except:
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
            except:
                try:
                    account_name = str(bot_info.id) if hasattr(bot_info, 'id') else "未知账号"
                except:
                    pass
        platform_name = self.getPlatformDisplayName(bot_info)
        return account_name, platform_name

    def updateAccountList(self, flagInit = False):
        self.UIData['shallow_account_list_new'] = []
        if self.bot_info and type(self.bot_info) is dict:
            for botHash, bot_info in self.bot_info.items():
                account_name, platform_name = self.getAccountDisplayInfo(botHash, bot_info, flagInit = flagInit)
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
            self.updateAccountList(flagInit = True)
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
                    self.UIObject['root_gocqhttp_terminal'][hash].stop()
                except:
                    pass
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
                    self.UIObject['root_walleq_terminal'][hash].stop()
                except:
                    pass
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
                    self.UIObject['root_cwcb_terminal'][hash].stop()
                except:
                    pass
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
                    self.UIObject['root_opqbot_terminal'][hash].stop()
                except:
                    pass
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
                    self.UIObject['root_napcat_terminal'][hash].stop()
                except:
                    pass
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
        self.sendRxEvent('send', {
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
                    self.UIObject['root_virtual_terminal_terminal'][hash].stop()
                except:
                    pass
            self.UIObject['root_virtual_terminal_terminal'][hash] = VirtualTerminalUI(
                Model_name='virtual_terminal',
                logger_proc=self.Proc_info.logger_proc.log,
                root=self,
                root_tk=None,
                bot=self.bot_info[hash]
            )
            self.UIObject['root_virtual_terminal_terminal'][hash].start()

    def startOlivOSTerminalUISend(self):
        self.sendRxEvent('send', {
            'target': {
                'type': 'nativeWinUI'
            },
            'data': {
                'action': 'OlivOS_terminal_on'
            }
        }
                                  )

    def startOlivOSTerminalUI(self):
        if self.UIObject['root_OlivOS_terminal'] is not None:
            try:
                self.UIObject['root_OlivOS_terminal'].stop()
            except:
                pass
        self.UIObject['root_OlivOS_terminal'] = OlivOSTerminalUI(
            Model_name='OlivOS_terminal',
            logger_proc=self.Proc_info.logger_proc.log,
            root=self,
            root_tk=None
        )
        self.UIObject['root_OlivOS_terminal'].start()

    def setGoCqhttpModelSend(self, hash, data):
        self.sendControlEventSend('send', {
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
        self.sendControlEventSend('send', {
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
        self.sendControlEventSend('send', {
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
        self.sendControlEventSend('send', {
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
        self.sendControlEventSend('send', {
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
        self.sendControlEventSend('send', {
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
        self.sendRxEvent('send', {
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
                except:
                    pass
        except:
            pass

    def setOlivOSExit(self):
        self.sendControlEvent('exit_total')

    def sendPluginControlEventFunc(self, pluginNameSpace, eventName):
        def resFunc():
            self.sendPluginControlEvent(pluginNameSpace, eventName)

        return resFunc

    def sendPluginControlEvent(self, pluginNameSpace, eventName):
        self.sendControlEventSend('send', {
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
        if type(self.bot_info) is dict \
        and hash in self.bot_info:
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
        name:str,
        title:str,
        url:str
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
            self.UIObject['root_qrcode_img_data'] = self.UIObject['root_qrcode_img_data'].resize((500, 500), Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS)
        except AttributeError:
            self.UIObject['root_qrcode_img_data'] = self.UIObject['root_qrcode_img_data'].resize((500, 500), Image.ANTIALIAS)
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


class gocqhttpTerminalUI(object):
    def __init__(self, Model_name, logger_proc=None, root=None, root_tk=None, bot=None):
        self.Model_name = Model_name
        self.root = root
        self.root_tk = root_tk
        self.bot = bot
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIConfig.update(dictColorContext)

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('GoCqhttp 终端 - %s' % str(self.bot.id))
        self.UIObject['root'].geometry('800x600')
        self.UIObject['root'].minsize(800, 600)
        self.UIObject['root'].grid_rowconfigure(0, weight=15)
        self.UIObject['root'].grid_rowconfigure(1, weight=0)
        self.UIObject['root'].grid_columnconfigure(0, weight=0)
        self.UIObject['root'].grid_columnconfigure(1, weight=2)
        self.UIObject['root'].grid_columnconfigure(2, weight=2)
        self.UIObject['root'].grid_columnconfigure(3, weight=0)
        self.UIObject['root'].resizable(
            width=True,
            height=True
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('DATA')
        self.UIObject['tree'].column('DATA', width=800 - 15 * 2 - 18 - 5)
        self.UIObject['tree'].heading('DATA', text='日志')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['tree'].bind('<Button-3>', lambda x: self.tree_rightKey(x))
        # self.tree_load()
        # self.UIObject['tree'].place(x = 15, y = 15, width = 800 - 15 * 2 - 18 , height = 600 - 15 * 2 - 24 - 8)
        self.UIObject['tree'].grid(
            row=0,
            column=0,
            sticky="nsew",
            rowspan=1,
            columnspan=3,
            padx=(15, 0),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient="vertical",
            command=self.UIObject['tree'].yview
        )
        # self.UIObject['tree_yscroll'].place(
        #    x = 800 - 15 - 18,
        #    y = 15,
        #    width = 18,
        #    height = 600 - 15 * 2 - 24 - 8
        # )
        self.UIObject['tree_yscroll'].grid(
            row=0,
            column=3,
            sticky="nsw",
            rowspan=1,
            columnspan=1,
            padx=(0, 15),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIData['flag_tree_is_bottom'] = True
        self.UIObject['tree'].configure(
            yscrollcommand=self.scroll_onChange(self.UIObject['tree_yscroll'].set)
        )

        self.root_Entry_init(
            obj_root='root',
            obj_name='root_input',
            str_name='root_input_StringVar',
            x=15,
            y=600 - 15 * 1 - 24,
            width_t=0,
            width=800 - 15 * 2,
            height=24,
            action=None,
            title='输入'
        )
        self.UIObject['root_input'].bind("<Return>", self.root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row=1,
            column=0,
            sticky="s",
            rowspan=1,
            columnspan=2,
            padx=(15, 0),
            pady=(8, 15),
            ipadx=0,
            ipady=4
        )

        self.root_Button_init(
            name='root_button_save',
            text='>',
            command=self.root_Entry_enter_Func('root_input'),
            x=800 - 15 * 2 - 5,
            y=600 - 15 * 1 - 24,
            width=16,
            height=1
        )
        self.UIObject['root_button_save'].grid(
            row=1,
            column=2,
            sticky="swe",
            rowspan=1,
            columnspan=2,
            padx=(0, 15),
            pady=(8, 15),
            ipadx=8,
            ipady=0
        )

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        self.tree_init_line()

        self.UIObject['root'].mainloop()

        self.exit()

    def scroll_onChange(self, command):
        def res(*arg, **kwarg):
            if arg[1] == '1.0':
                self.UIData['flag_tree_is_bottom'] = True
            else:
                self.UIData['flag_tree_is_bottom'] = False
            return command(*arg, **kwarg)
        return res

    def tree_rightKey(self, event):
        # 右键设置的选择在后续流程中未生效，不知为何，等后续解决
        # iid = self.UIObject['tree'].identify_row(event.y)
        # self.UIObject['tree'].selection_set(iid)
        # self.UIObject['tree'].update()
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label='查看', command=lambda: self.rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label='复制', command=lambda: self.rightKey_action('copy'))
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def rightKey_action(self, action: str):
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

    def root_Entry_enter_Func(self, name):
        def resFunc(*arg, **kwarg):
            self.root_Entry_enter(name, None)

        return resFunc

    def root_Entry_enter(self, name, event):
        if name == 'root_input':
            input_data = self.UIData['root_input_StringVar'].get()
            if len(input_data) >= 0 and len(input_data) < 1000:
                self.root_setGoCqhttpModelSend(input_data)
            self.UIData['root_input_StringVar'].set('')

    def root_setGoCqhttpModelSend(self, input_data):
        self.root.setGoCqhttpModelSend(self.bot.hash, input_data)

    def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title='',
                        mode='NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        # self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        # )
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root],
            textvariable=self.UIData[str_name],
            font=('TkDefaultFont 12')
        )
        self.UIObject[obj_name].configure(
            bg=self.UIConfig['color_004'],
            fg=self.UIConfig['color_005'],
            bd=0
        )
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show='●'
            )
        self.UIObject[obj_name].configure(
            width=width
        )
        # self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        # )

    def show_tx_url_webbrowser(self, url):
        res = tkinter.messagebox.askquestion("请完成验证", "是否使用内置人机验证助手访问 \"" + url + "\" ?")
        try:
            if res == 'yes':
                OlivOS.libEXEModelAPI.sendOpentxTuringTestPage(
                    control_queue=self.root.Proc_info.control_queue,
                    name='slider_verification_code=%s' % self.bot.hash,
                    title='请完成验证',
                    url=url
                )
            else:
                webbrowser.open(url)
        except webbrowser.Error as error_info:
            tkinter.messagebox.showerror("webbrowser.Error", error_info)

    def show_url_webbrowser(self, url):
        res = tkinter.messagebox.askquestion("请完成验证", "是否通过浏览器访问 \"" + url + "\" ?")
        try:
            if res == 'yes':
                res = tkinter.messagebox.askquestion("请完成验证", "是否使用内置浏览器?")
                if res == 'yes':
                    OlivOS.webviewUIAPI.sendOpenWebviewPage(
                        control_queue=self.root.Proc_info.control_queue,
                        name='slider_verification_code=%s' % self.bot.hash,
                        title='请完成验证',
                        url=url
                    )
                else:
                    webbrowser.open(url)
        except webbrowser.Error as error_info:
            tkinter.messagebox.showerror("webbrowser.Error", error_info)

    def tree_init_line(self):
        if self.bot.hash in self.root.UIObject['root_gocqhttp_terminal_data']:
            for line in self.root.UIObject['root_gocqhttp_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit = True)

    def tree_add_line(self, data, flagInit = False):
        res_data = re.sub(r'\033\[[\d;]*m?', '', data)
        res_data_raw = res_data
        res_data = res_data.encode(encoding='gb2312', errors='replace').decode(encoding='gb2312', errors='replace')
        res_data_1 = res_data
        res_data = res_data.replace(' ', '\ ')
        if len(res_data.replace('\ ', '')) > 0:
            try:
                iid = self.UIObject['tree'].insert(
                    '',
                    tkinter.END,
                    text=res_data_1,
                    values=(
                        res_data
                    )
                )
                if self.UIData['flag_tree_is_bottom']:
                    self.UIObject['tree'].see(iid)
                    #self.UIObject['tree'].update()
            except:
                pass

        if not flagInit and platform.system() == 'Windows':
            try:
                matchRes = re.match(
                    r'^\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\]\s\[WARNING\]:\s请选择提交滑块ticket方式:.*$',
                    res_data_raw
                )
                if matchRes != None:
                    self.tree_add_line('=================================================================')
                    self.tree_add_line('        【推荐】　选择手动抓取ticket方式将会允许OlivOS接管验证流程　【推荐】')
                    self.tree_add_line('=================================================================')

                matchRes = re.match(
                    r'^\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\]\s\[WARNING\]:\s请前往该地址验证\s+->\s+(http[s]{0,1}://ti\.qq\.com/safe/tools/captcha/sms-verify-login\?[^\s]+).*$',
                    res_data_raw
                )
                if matchRes != None:
                    matchResList = list(matchRes.groups())
                    if len(matchResList) == 1:
                        matchResUrl = matchResList[0]
                        self.show_tx_url_webbrowser(matchResUrl)

                matchRes = re.match(
                    r'^\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\]\s\[WARNING\]:\s账号已开启设备锁，请前往\s+->\s+(http[s]{0,1}://accounts\.qq\.com/safe/verify[^\s]+).*$',
                    res_data_raw
                )
                if matchRes != None:
                    matchResList = list(matchRes.groups())
                    if len(matchResList) == 1:
                        matchResUrl = matchResList[0]
                        matchResUrl = matchResUrl.replace('accounts.qq.com/safe/verify', 'accounts.qq.com/safe/qrcode')
                        self.show_url_webbrowser(matchResUrl)
            except:
                pass

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def root_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['root'],
            text=text,
            command=command,
            bd=0,
            activebackground=self.UIConfig['color_002'],
            activeforeground=self.UIConfig['color_001'],
            bg=self.UIConfig['color_003'],
            fg=self.UIConfig['color_004'],
            relief='groove',
            height=height
        )
        self.UIObject[name].bind('<Enter>', lambda x: self.buttom_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda x: self.buttom_action(name, '<Leave>'))

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_gocqhttp_terminal'].pop(self.bot.hash)


class walleqTerminalUI(object):
    def __init__(self, Model_name, logger_proc=None, root=None, root_tk=None, bot=None):
        self.Model_name = Model_name
        self.root = root
        self.root_tk = root_tk
        self.bot = bot
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIConfig.update(dictColorContext)

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('WalleQ 终端 - %s' % str(self.bot.id))
        self.UIObject['root'].geometry('800x600')
        self.UIObject['root'].minsize(800, 600)
        self.UIObject['root'].grid_rowconfigure(0, weight=15)
        self.UIObject['root'].grid_rowconfigure(1, weight=0)
        self.UIObject['root'].grid_columnconfigure(0, weight=0)
        self.UIObject['root'].grid_columnconfigure(1, weight=2)
        self.UIObject['root'].grid_columnconfigure(2, weight=2)
        self.UIObject['root'].grid_columnconfigure(3, weight=0)
        self.UIObject['root'].resizable(
            width=True,
            height=True
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('DATA')
        self.UIObject['tree'].column('DATA', width=800 - 15 * 2 - 18 - 5)
        self.UIObject['tree'].heading('DATA', text='日志')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['tree'].bind('<Button-3>', lambda x: self.tree_rightKey(x))
        # self.tree_load()
        # self.UIObject['tree'].place(x = 15, y = 15, width = 800 - 15 * 2 - 18 , height = 600 - 15 * 2 - 24 - 8)
        self.UIObject['tree'].grid(
            row=0,
            column=0,
            sticky="nsew",
            rowspan=1,
            columnspan=3,
            padx=(15, 0),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient="vertical",
            command=self.UIObject['tree'].yview
        )
        # self.UIObject['tree_yscroll'].place(
        #    x = 800 - 15 - 18,
        #    y = 15,
        #    width = 18,
        #    height = 600 - 15 * 2 - 24 - 8
        # )
        self.UIObject['tree_yscroll'].grid(
            row=0,
            column=3,
            sticky="nsw",
            rowspan=1,
            columnspan=1,
            padx=(0, 15),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIData['flag_tree_is_bottom'] = True
        self.UIObject['tree'].configure(
            yscrollcommand=self.scroll_onChange(self.UIObject['tree_yscroll'].set)
        )

        self.root_Entry_init(
            obj_root='root',
            obj_name='root_input',
            str_name='root_input_StringVar',
            x=15,
            y=600 - 15 * 1 - 24,
            width_t=0,
            width=800 - 15 * 2,
            height=24,
            action=None,
            title='输入'
        )
        self.UIObject['root_input'].bind("<Return>", self.root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row=1,
            column=0,
            sticky="s",
            rowspan=1,
            columnspan=2,
            padx=(15, 0),
            pady=(8, 15),
            ipadx=0,
            ipady=4
        )

        self.root_Button_init(
            name='root_button_save',
            text='>',
            command=self.root_Entry_enter_Func('root_input'),
            x=800 - 15 * 2 - 5,
            y=600 - 15 * 1 - 24,
            width=16,
            height=1
        )
        self.UIObject['root_button_save'].grid(
            row=1,
            column=2,
            sticky="swe",
            rowspan=1,
            columnspan=2,
            padx=(0, 15),
            pady=(8, 15),
            ipadx=8,
            ipady=0
        )

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        self.tree_init_line()

        self.UIObject['root'].mainloop()

        self.exit()

    def scroll_onChange(self, command):
        def res(*arg, **kwarg):
            if arg[1] == '1.0':
                self.UIData['flag_tree_is_bottom'] = True
            else:
                self.UIData['flag_tree_is_bottom'] = False
            return command(*arg, **kwarg)
        return res

    def tree_rightKey(self, event):
        # 右键设置的选择在后续流程中未生效，不知为何，等后续解决
        # iid = self.UIObject['tree'].identify_row(event.y)
        # self.UIObject['tree'].selection_set(iid)
        # self.UIObject['tree'].update()
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label='查看', command=lambda: self.rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label='复制', command=lambda: self.rightKey_action('copy'))
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def rightKey_action(self, action: str):
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

    def root_Entry_enter_Func(self, name):
        def resFunc(*arg, **kwarg):
            self.root_Entry_enter(name, None)

        return resFunc

    def root_Entry_enter(self, name, event):
        if name == 'root_input':
            input = self.UIData['root_input_StringVar'].get()
            if len(input) >= 0 and len(input) < 1000:
                self.root.setWalleQModelSend(self.bot.hash, input)
            self.UIData['root_input_StringVar'].set('')

    def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title='',
                        mode='NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        # self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        # )
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root],
            textvariable=self.UIData[str_name],
            font=('TkDefaultFont 12')
        )
        self.UIObject[obj_name].configure(
            bg=self.UIConfig['color_004'],
            fg=self.UIConfig['color_005'],
            bd=0
        )
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show='●'
            )
        self.UIObject[obj_name].configure(
            width=width
        )
        # self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        # )

    def show_url_webbrowser(self, url):
        res = tkinter.messagebox.askquestion("请完成验证", "是否通过浏览器访问 \"" + url + "\" ?")
        try:
            if res == 'yes':
                webbrowser.open(url)
        except webbrowser.Error as error_info:
            tkinter.messagebox.showerror("webbrowser.Error", error_info)

    def tree_init_line(self):
        if self.bot.hash in self.root.UIObject['root_walleq_terminal_data']:
            for line in self.root.UIObject['root_walleq_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit = True)

    def tree_add_line(self, data, flagInit = False):
        res_data = re.sub(r'\033\[[\d;]*m?', '', data)
        res_data_raw = res_data
        res_data = res_data.encode(encoding='gb2312', errors='replace').decode(encoding='gb2312', errors='replace')
        res_data_1 = res_data
        res_data = res_data.replace(' ', '\ ')
        if len(res_data.replace('\ ', '')) > 0:
            try:
                iid = self.UIObject['tree'].insert(
                    '',
                    tkinter.END,
                    text=res_data_1,
                    values=(
                        res_data
                    )
                )
                if self.UIData['flag_tree_is_bottom']:
                    self.UIObject['tree'].see(iid)
                    #self.UIObject['tree'].update()
            except:
                pass

        if not flagInit and platform.system() == 'Windows':
            try:
                matchRes = re.match(
                    r'^\[\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}\]\s\[WARNING\]:\s请前往该地址验证\s+->\s+(http[s]{0,1}://captcha\.go-cqhttp\.org/captcha\?[^\s]+).*$',
                    res_data_raw
                )
                if matchRes != None:
                    matchResList = list(matchRes.groups())
                    if len(matchResList) == 1:
                        matchResUrl = matchResList[0]
                        self.show_url_webbrowser(matchResUrl)
            except:
                pass

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def root_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['root'],
            text=text,
            command=command,
            bd=0,
            activebackground=self.UIConfig['color_002'],
            activeforeground=self.UIConfig['color_001'],
            bg=self.UIConfig['color_003'],
            fg=self.UIConfig['color_004'],
            relief='groove',
            height=height
        )
        self.UIObject[name].bind('<Enter>', lambda x: self.buttom_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda x: self.buttom_action(name, '<Leave>'))

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_walleq_terminal'].pop(self.bot.hash)



class CWCBTerminalUI(object):
    def __init__(self, Model_name, logger_proc=None, root=None, root_tk=None, bot=None):
        self.Model_name = Model_name
        self.root = root
        self.root_tk = root_tk
        self.bot = bot
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIConfig.update(dictColorContext)

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('ComWeChatBotClient 终端 - %s' % str(self.bot.id))
        self.UIObject['root'].geometry('800x600')
        self.UIObject['root'].minsize(800, 600)
        self.UIObject['root'].grid_rowconfigure(0, weight=15)
        self.UIObject['root'].grid_rowconfigure(1, weight=0)
        self.UIObject['root'].grid_columnconfigure(0, weight=0)
        self.UIObject['root'].grid_columnconfigure(1, weight=2)
        self.UIObject['root'].grid_columnconfigure(2, weight=2)
        self.UIObject['root'].grid_columnconfigure(3, weight=0)
        self.UIObject['root'].resizable(
            width=True,
            height=True
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('DATA')
        self.UIObject['tree'].column('DATA', width=800 - 15 * 2 - 18 - 5)
        self.UIObject['tree'].heading('DATA', text='日志')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['tree'].bind('<Button-3>', lambda x: self.tree_rightKey(x))
        # self.tree_load()
        # self.UIObject['tree'].place(x = 15, y = 15, width = 800 - 15 * 2 - 18 , height = 600 - 15 * 2 - 24 - 8)
        self.UIObject['tree'].grid(
            row=0,
            column=0,
            sticky="nsew",
            rowspan=1,
            columnspan=3,
            padx=(15, 0),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient="vertical",
            command=self.UIObject['tree'].yview
        )
        # self.UIObject['tree_yscroll'].place(
        #    x = 800 - 15 - 18,
        #    y = 15,
        #    width = 18,
        #    height = 600 - 15 * 2 - 24 - 8
        # )
        self.UIObject['tree_yscroll'].grid(
            row=0,
            column=3,
            sticky="nsw",
            rowspan=1,
            columnspan=1,
            padx=(0, 15),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIData['flag_tree_is_bottom'] = True
        self.UIObject['tree'].configure(
            yscrollcommand=self.scroll_onChange(self.UIObject['tree_yscroll'].set)
        )

        self.root_Entry_init(
            obj_root='root',
            obj_name='root_input',
            str_name='root_input_StringVar',
            x=15,
            y=600 - 15 * 1 - 24,
            width_t=0,
            width=800 - 15 * 2,
            height=24,
            action=None,
            title='输入'
        )
        self.UIObject['root_input'].bind("<Return>", self.root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row=1,
            column=0,
            sticky="s",
            rowspan=1,
            columnspan=2,
            padx=(15, 0),
            pady=(8, 15),
            ipadx=0,
            ipady=4
        )

        self.root_Button_init(
            name='root_button_save',
            text='>',
            command=self.root_Entry_enter_Func('root_input'),
            x=800 - 15 * 2 - 5,
            y=600 - 15 * 1 - 24,
            width=16,
            height=1
        )
        self.UIObject['root_button_save'].grid(
            row=1,
            column=2,
            sticky="swe",
            rowspan=1,
            columnspan=2,
            padx=(0, 15),
            pady=(8, 15),
            ipadx=8,
            ipady=0
        )

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        self.tree_init_line()

        self.UIObject['root'].mainloop()

        self.exit()

    def scroll_onChange(self, command):
        def res(*arg, **kwarg):
            if arg[1] == '1.0':
                self.UIData['flag_tree_is_bottom'] = True
            else:
                self.UIData['flag_tree_is_bottom'] = False
            return command(*arg, **kwarg)
        return res

    def tree_rightKey(self, event):
        # 右键设置的选择在后续流程中未生效，不知为何，等后续解决
        # iid = self.UIObject['tree'].identify_row(event.y)
        # self.UIObject['tree'].selection_set(iid)
        # self.UIObject['tree'].update()
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label='查看', command=lambda: self.rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label='复制', command=lambda: self.rightKey_action('copy'))
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def rightKey_action(self, action: str):
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

    def root_Entry_enter_Func(self, name):
        def resFunc(*arg, **kwarg):
            self.root_Entry_enter(name, None)

        return resFunc

    def root_Entry_enter(self, name, event):
        if name == 'root_input':
            input = self.UIData['root_input_StringVar'].get()
            if len(input) >= 0 and len(input) < 1000:
                self.root.setCWCBModelSend(self.bot.hash, input)
            self.UIData['root_input_StringVar'].set('')

    def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title='',
                        mode='NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        # self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        # )
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root],
            textvariable=self.UIData[str_name],
            font=('TkDefaultFont 12')
        )
        self.UIObject[obj_name].configure(
            bg=self.UIConfig['color_004'],
            fg=self.UIConfig['color_005'],
            bd=0
        )
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show='●'
            )
        self.UIObject[obj_name].configure(
            width=width
        )
        # self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        # )

    def tree_init_line(self):
        if self.bot.hash in self.root.UIObject['root_cwcb_terminal_data']:
            for line in self.root.UIObject['root_cwcb_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit = True)

    def tree_add_line(self, data, flagInit = False):
        res_data = re.sub(r'\033\[[\d;]*m?', '', data)
        res_data_raw = res_data
        res_data = res_data.encode(encoding='gb2312', errors='replace').decode(encoding='gb2312', errors='replace')
        res_data_1 = res_data
        res_data = res_data.replace(' ', '\ ')
        if len(res_data.replace('\ ', '')) > 0:
            try:
                iid = self.UIObject['tree'].insert(
                    '',
                    tkinter.END,
                    text=res_data_1,
                    values=(
                        res_data
                    )
                )
                if self.UIData['flag_tree_is_bottom']:
                    self.UIObject['tree'].see(iid)
                    #self.UIObject['tree'].update()
            except:
                pass

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def root_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['root'],
            text=text,
            command=command,
            bd=0,
            activebackground=self.UIConfig['color_002'],
            activeforeground=self.UIConfig['color_001'],
            bg=self.UIConfig['color_003'],
            fg=self.UIConfig['color_004'],
            relief='groove',
            height=height
        )
        self.UIObject[name].bind('<Enter>', lambda x: self.buttom_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda x: self.buttom_action(name, '<Leave>'))

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_cwcb_terminal'].pop(self.bot.hash)



class opqbotTerminalUI(object):
    def __init__(self, Model_name, logger_proc=None, root=None, root_tk=None, bot=None):
        self.Model_name = Model_name
        self.root = root
        self.root_tk = root_tk
        self.bot = bot
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIConfig.update(dictColorContext)

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('OPQBot 终端 - %s' % str(self.bot.id))
        self.UIObject['root'].geometry('800x600')
        self.UIObject['root'].minsize(800, 600)
        self.UIObject['root'].grid_rowconfigure(0, weight=15)
        self.UIObject['root'].grid_rowconfigure(1, weight=0)
        self.UIObject['root'].grid_columnconfigure(0, weight=0)
        self.UIObject['root'].grid_columnconfigure(1, weight=2)
        self.UIObject['root'].grid_columnconfigure(2, weight=2)
        self.UIObject['root'].grid_columnconfigure(3, weight=0)
        self.UIObject['root'].resizable(
            width=True,
            height=True
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('DATA')
        self.UIObject['tree'].column('DATA', width=800 - 15 * 2 - 18 - 5)
        self.UIObject['tree'].heading('DATA', text='日志')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['tree'].bind('<Button-3>', lambda x: self.tree_rightKey(x))
        # self.tree_load()
        # self.UIObject['tree'].place(x = 15, y = 15, width = 800 - 15 * 2 - 18 , height = 600 - 15 * 2 - 24 - 8)
        self.UIObject['tree'].grid(
            row=0,
            column=0,
            sticky="nsew",
            rowspan=1,
            columnspan=3,
            padx=(15, 0),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient="vertical",
            command=self.UIObject['tree'].yview
        )
        # self.UIObject['tree_yscroll'].place(
        #    x = 800 - 15 - 18,
        #    y = 15,
        #    width = 18,
        #    height = 600 - 15 * 2 - 24 - 8
        # )
        self.UIObject['tree_yscroll'].grid(
            row=0,
            column=3,
            sticky="nsw",
            rowspan=1,
            columnspan=1,
            padx=(0, 15),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIData['flag_tree_is_bottom'] = True
        self.UIObject['tree'].configure(
            yscrollcommand=self.scroll_onChange(self.UIObject['tree_yscroll'].set)
        )

        self.root_Entry_init(
            obj_root='root',
            obj_name='root_input',
            str_name='root_input_StringVar',
            x=15,
            y=600 - 15 * 1 - 24,
            width_t=0,
            width=800 - 15 * 2,
            height=24,
            action=None,
            title='输入'
        )
        self.UIObject['root_input'].bind("<Return>", self.root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row=1,
            column=0,
            sticky="s",
            rowspan=1,
            columnspan=2,
            padx=(15, 0),
            pady=(8, 15),
            ipadx=0,
            ipady=4
        )

        self.root_Button_init(
            name='root_button_save',
            text='>',
            command=self.root_Entry_enter_Func('root_input'),
            x=800 - 15 * 2 - 5,
            y=600 - 15 * 1 - 24,
            width=16,
            height=1
        )
        self.UIObject['root_button_save'].grid(
            row=1,
            column=2,
            sticky="swe",
            rowspan=1,
            columnspan=2,
            padx=(0, 15),
            pady=(8, 15),
            ipadx=8,
            ipady=0
        )

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        self.tree_init_line()

        self.UIObject['root'].mainloop()

        self.exit()

    def scroll_onChange(self, command):
        def res(*arg, **kwarg):
            if arg[1] == '1.0':
                self.UIData['flag_tree_is_bottom'] = True
            else:
                self.UIData['flag_tree_is_bottom'] = False
            return command(*arg, **kwarg)
        return res

    def tree_rightKey(self, event):
        # 右键设置的选择在后续流程中未生效，不知为何，等后续解决
        # iid = self.UIObject['tree'].identify_row(event.y)
        # self.UIObject['tree'].selection_set(iid)
        # self.UIObject['tree'].update()
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label='查看', command=lambda: self.rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label='复制', command=lambda: self.rightKey_action('copy'))
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def rightKey_action(self, action: str):
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

    def root_Entry_enter_Func(self, name):
        def resFunc(*arg, **kwarg):
            self.root_Entry_enter(name, None)

        return resFunc

    def root_Entry_enter(self, name, event):
        if name == 'root_input':
            input = self.UIData['root_input_StringVar'].get()
            if len(input) >= 0 and len(input) < 1000:
                self.root.setOPQBotModelSend(self.bot.hash, input)
            self.UIData['root_input_StringVar'].set('')

    def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title='',
                        mode='NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        # self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        # )
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root],
            textvariable=self.UIData[str_name],
            font=('TkDefaultFont 12')
        )
        self.UIObject[obj_name].configure(
            bg=self.UIConfig['color_004'],
            fg=self.UIConfig['color_005'],
            bd=0
        )
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show='●'
            )
        self.UIObject[obj_name].configure(
            width=width
        )
        # self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        # )

    def tree_init_line(self):
        if self.bot.hash in self.root.UIObject['root_opqbot_terminal_data']:
            for line in self.root.UIObject['root_opqbot_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit = True)

    def tree_add_line(self, data, flagInit = False):
        res_data = re.sub(r'\033\[[\d;]*m?', '', data)
        res_data_raw = res_data
        res_data = res_data.encode(encoding='gb2312', errors='replace').decode(encoding='gb2312', errors='replace')
        res_data_1 = res_data
        res_data = res_data.replace(' ', '\ ')
        if len(res_data.replace('\ ', '')) > 0:
            try:
                iid = self.UIObject['tree'].insert(
                    '',
                    tkinter.END,
                    text=res_data_1,
                    values=(
                        res_data
                    )
                )
                if self.UIData['flag_tree_is_bottom']:
                    self.UIObject['tree'].see(iid)
                    #self.UIObject['tree'].update()
            except:
                pass

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def root_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['root'],
            text=text,
            command=command,
            bd=0,
            activebackground=self.UIConfig['color_002'],
            activeforeground=self.UIConfig['color_001'],
            bg=self.UIConfig['color_003'],
            fg=self.UIConfig['color_004'],
            relief='groove',
            height=height
        )
        self.UIObject[name].bind('<Enter>', lambda x: self.buttom_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda x: self.buttom_action(name, '<Leave>'))

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_opqbot_terminal'].pop(self.bot.hash)


class napcatTerminalUI(object):
    def __init__(self, Model_name, logger_proc=None, root=None, root_tk=None, bot=None):
        self.Model_name = Model_name
        self.root = root
        self.root_tk = root_tk
        self.bot = bot
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIConfig.update(dictColorContext)

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('NapCat 终端 - %s' % str(self.bot.id))
        self.UIObject['root'].geometry('800x600')
        self.UIObject['root'].minsize(800, 600)
        self.UIObject['root'].grid_rowconfigure(0, weight=15)
        self.UIObject['root'].grid_rowconfigure(1, weight=0)
        self.UIObject['root'].grid_columnconfigure(0, weight=0)
        self.UIObject['root'].grid_columnconfigure(1, weight=2)
        self.UIObject['root'].grid_columnconfigure(2, weight=2)
        self.UIObject['root'].grid_columnconfigure(3, weight=0)
        self.UIObject['root'].resizable(
            width=True,
            height=True
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('DATA')
        self.UIObject['tree'].column('DATA', width=800 - 15 * 2 - 18 - 5)
        self.UIObject['tree'].heading('DATA', text='日志')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['tree'].bind('<Button-3>', lambda x: self.tree_rightKey(x))
        # self.tree_load()
        # self.UIObject['tree'].place(x = 15, y = 15, width = 800 - 15 * 2 - 18 , height = 600 - 15 * 2 - 24 - 8)
        self.UIObject['tree'].grid(
            row=0,
            column=0,
            sticky="nsew",
            rowspan=1,
            columnspan=3,
            padx=(15, 0),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient="vertical",
            command=self.UIObject['tree'].yview
        )
        # self.UIObject['tree_yscroll'].place(
        #    x = 800 - 15 - 18,
        #    y = 15,
        #    width = 18,
        #    height = 600 - 15 * 2 - 24 - 8
        # )
        self.UIObject['tree_yscroll'].grid(
            row=0,
            column=3,
            sticky="nsw",
            rowspan=1,
            columnspan=1,
            padx=(0, 15),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIData['flag_tree_is_bottom'] = True
        self.UIObject['tree'].configure(
            yscrollcommand=self.scroll_onChange(self.UIObject['tree_yscroll'].set)
        )

        self.root_Entry_init(
            obj_root='root',
            obj_name='root_input',
            str_name='root_input_StringVar',
            x=15,
            y=600 - 15 * 1 - 24,
            width_t=0,
            width=800 - 15 * 2,
            height=24,
            action=None,
            title='输入'
        )
        self.UIObject['root_input'].bind("<Return>", self.root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row=1,
            column=0,
            sticky="s",
            rowspan=1,
            columnspan=2,
            padx=(15, 0),
            pady=(8, 15),
            ipadx=0,
            ipady=4
        )

        self.root_Button_init(
            name='root_button_save',
            text='>',
            command=self.root_Entry_enter_Func('root_input'),
            x=800 - 15 * 2 - 5,
            y=600 - 15 * 1 - 24,
            width=16,
            height=1
        )
        self.UIObject['root_button_save'].grid(
            row=1,
            column=2,
            sticky="swe",
            rowspan=1,
            columnspan=2,
            padx=(0, 15),
            pady=(8, 15),
            ipadx=8,
            ipady=0
        )

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        self.tree_init_line()

        self.UIObject['root'].mainloop()

        self.exit()

    def scroll_onChange(self, command):
        def res(*arg, **kwarg):
            if arg[1] == '1.0':
                self.UIData['flag_tree_is_bottom'] = True
            else:
                self.UIData['flag_tree_is_bottom'] = False
            return command(*arg, **kwarg)
        return res

    def tree_rightKey(self, event):
        # 右键设置的选择在后续流程中未生效，不知为何，等后续解决
        # iid = self.UIObject['tree'].identify_row(event.y)
        # self.UIObject['tree'].selection_set(iid)
        # self.UIObject['tree'].update()
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label='查看', command=lambda: self.rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label='复制', command=lambda: self.rightKey_action('copy'))
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def rightKey_action(self, action: str):
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

    def root_Entry_enter_Func(self, name):
        def resFunc(*arg, **kwarg):
            self.root_Entry_enter(name, None)

        return resFunc

    def root_Entry_enter(self, name, event):
        if name == 'root_input':
            input = self.UIData['root_input_StringVar'].get()
            if len(input) >= 0 and len(input) < 1000:
                self.root.setNapCatModelSend(self.bot.hash, input)
            self.UIData['root_input_StringVar'].set('')

    def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title='',
                        mode='NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        # self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        # )
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root],
            textvariable=self.UIData[str_name],
            font=('TkDefaultFont 12')
        )
        self.UIObject[obj_name].configure(
            bg=self.UIConfig['color_004'],
            fg=self.UIConfig['color_005'],
            bd=0
        )
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show='●'
            )
        self.UIObject[obj_name].configure(
            width=width
        )
        # self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        # )

    def tree_init_line(self):
        if self.bot.hash in self.root.UIObject['root_napcat_terminal_data']:
            for line in self.root.UIObject['root_napcat_terminal_data'][self.bot.hash]:
                self.tree_add_line(line, flagInit = True)

    def tree_add_line(self, data, flagInit = False):
        res_data = re.sub(r'\033\[[\d;]*m?', '', data)
        res_data_raw = res_data
        res_data = res_data.encode(encoding='gb2312', errors='replace').decode(encoding='gb2312', errors='replace')
        res_data_1 = res_data
        res_data = res_data.replace(' ', '\ ')
        if len(res_data.replace('\ ', '')) > 0:
            try:
                iid = self.UIObject['tree'].insert(
                    '',
                    tkinter.END,
                    text=res_data_1,
                    values=(
                        res_data
                    )
                )
                if self.UIData['flag_tree_is_bottom']:
                    self.UIObject['tree'].see(iid)
                    #self.UIObject['tree'].update()
            except:
                pass

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def root_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['root'],
            text=text,
            command=command,
            bd=0,
            activebackground=self.UIConfig['color_002'],
            activeforeground=self.UIConfig['color_001'],
            bg=self.UIConfig['color_003'],
            fg=self.UIConfig['color_004'],
            relief='groove',
            height=height
        )
        self.UIObject[name].bind('<Enter>', lambda x: self.buttom_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda x: self.buttom_action(name, '<Leave>'))


    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_napcat_terminal'].pop(self.bot.hash)



class OlivOSTerminalUI(object):
    def __init__(self, Model_name, logger_proc=None, root=None, root_tk=None):
        self.Model_name = Model_name
        self.root = root
        self.root_tk = root_tk
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIConfig.update(dictColorContext)

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('OlivOS 终端 - %s' % OlivOS.infoAPI.OlivOS_Version_Title)
        self.UIObject['root'].geometry('900x600')
        self.UIObject['root'].minsize(900, 600)
        self.UIObject['root'].grid_rowconfigure(0, weight=15)
        self.UIObject['root'].grid_rowconfigure(1, weight=0)
        self.UIObject['root'].grid_columnconfigure(0, weight=0)
        self.UIObject['root'].grid_columnconfigure(1, weight=2)
        self.UIObject['root'].grid_columnconfigure(2, weight=0)
        self.UIObject['root'].resizable(
            width=True,
            height=True
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])
        self.UIObject['root'].bind('<Configure>', self.root_resize)

        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])

        for level_this in OlivOS.diagnoseAPI.level_dict:
            self.UIObject['tree'].tag_configure(
                OlivOS.diagnoseAPI.level_dict[level_this],
                foreground=OlivOS.diagnoseAPI.level_color_dict[
                    OlivOS.diagnoseAPI.level_dict[level_this]
                ]
            )

        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('TIME', 'LEVEL', 'DATA')
        self.UIObject['tree'].column('TIME', width=140)
        self.UIObject['tree'].column('LEVEL', width=50)
        # self.UIObject['tree'].column('SIG_01', width = 80)
        # self.UIObject['tree'].column('SIG_02', width = 80)
        # self.UIObject['tree'].column('SIG_03', width = 80)
        self.UIObject['tree'].column('DATA', width=710 - 15 * 2 - 18 - 5)
        self.UIObject['tree'].heading('TIME', text='时间')
        self.UIObject['tree'].heading('LEVEL', text='等级')
        # self.UIObject['tree'].heading('SIG_01', text = '')
        # self.UIObject['tree'].heading('SIG_02', text = '')
        # self.UIObject['tree'].heading('SIG_03', text = '')
        self.UIObject['tree'].heading('DATA', text='日志')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['tree'].bind('<Button-3>', lambda x: self.tree_rightKey(x))
        # self.tree_load()
        # self.UIObject['tree'].place(x = 15, y = 15, width = 900 - 15 * 2 - 18 , height = 600 - 15 * 2 - 24 - 8)
        self.UIObject['tree'].grid(
            row=0,
            column=0,
            sticky="nsew",
            rowspan=1,
            columnspan=2,
            padx=(15, 0),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient="vertical",
            command=self.UIObject['tree'].yview
        )
        self.UIObject['tree_yscroll'].grid(
            row=0,
            column=2,
            sticky="nsw",
            rowspan=1,
            columnspan=1,
            padx=(0, 15),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIData['flag_tree_is_bottom'] = True
        self.UIObject['tree'].configure(
            yscrollcommand=self.scroll_onChange(self.UIObject['tree_yscroll'].set)
        )

        self.tree_edit_UI_Combobox_init(
            obj_root='root',
            obj_name='root_level',
            str_name='root_level_StringVar',
            x=15,
            y=600 - 15 * 1 - 24,
            width_t=0,
            width=50,
            height=24,
            action=None,
            title='等级'
        )
        self.UIObject['root_level'].grid(
            row=1,
            column=0,
            sticky="ns",
            rowspan=1,
            columnspan=1,
            padx=(15, 8),
            pady=(9, 15),
            ipadx=0,
            ipady=0
        )
        self.UIData['level_list'] = []
        self.UIData['level_find'] = {}
        self.UIData['level_default'] = 'INFO'
        for level_this in OlivOS.diagnoseAPI.level_dict:
            self.UIData['level_list'].append(OlivOS.diagnoseAPI.level_dict[level_this])
            self.UIData['level_find'][OlivOS.diagnoseAPI.level_dict[level_this]] = level_this
        self.UIObject['root_level']['value'] = tuple(self.UIData['level_list'])
        self.UIObject['root_level'].current(self.UIData['level_list'].index(self.UIData['level_default']))

        self.root_Entry_init(
            obj_root='root',
            obj_name='root_input',
            str_name='root_input_StringVar',
            x=15 + 70 + 8,
            y=600 - 15 * 1 - 24,
            width_t=0,
            width=900,
            height=24,
            action=None,
            title='输入'
        )
        self.UIObject['root_input'].bind("<Return>", self.root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row=1,
            column=1,
            sticky="s",
            rowspan=1,
            columnspan=2,
            padx=(0, 15),
            pady=(8, 15),
            ipadx=0,
            ipady=2
        )

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stopManual)

        self.tree_init_line()

        self.UIObject['root'].mainloop()

        self.exit()

    def scroll_onChange(self, command):
        def res(*arg, **kwarg):
            if arg[1] == '1.0':
                self.UIData['flag_tree_is_bottom'] = True
            else:
                self.UIData['flag_tree_is_bottom'] = False
            return command(*arg, **kwarg)
        return res

    def tree_rightKey(self, event):
        # 右键设置的选择在后续流程中未生效，不知为何，等后续解决
        # iid = self.UIObject['tree'].identify_row(event.y)
        # self.UIObject['tree'].selection_set(iid)
        # self.UIObject['tree'].update()
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label='查看', command=lambda: self.rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label='复制', command=lambda: self.rightKey_action('copy'))
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def rightKey_action(self, action: str):
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

    def root_resize(self, event=None):
        pass

    def root_Entry_enter_Func(self, name):
        def resFunc(event):
            self.root_Entry_enter(name, event)

        return resFunc

    def root_Entry_enter(self, name, event):
        if name == 'root_input':
            input = self.UIData['root_input_StringVar'].get()
            if len(input) > 0:
                #    self.root.setGoCqhttpModelSend(self.bot.hash, input)
                pass
            self.UIData['root_input_StringVar'].set('')

    def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title='',
                        mode='NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        # self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        # )
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root],
            textvariable=self.UIData[str_name]
        )
        self.UIObject[obj_name].configure(
            bg=self.UIConfig['color_004'],
            fg=self.UIConfig['color_005'],
            bd=0
        )
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show='●'
            )
        self.UIObject[obj_name].configure(
            width=width
        )
        # self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        # )

    def tree_edit_UI_Combobox_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title=''):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        # self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        # )
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = ttk.Combobox(
            self.UIObject[obj_root],
            textvariable=self.UIData[str_name]
        )
        # self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        # )
        self.UIObject[obj_name].configure(state='readonly')
        # self.UIObject[obj_name].bind('<<ComboboxSelected>>', lambda x : self.tree_edit_UI_Combobox_ComboboxSelected(x, action, obj_name))

    def tree_init_line(self):
        tmp_count_old = 0
        tmp_count_new = len(self.root.UIObject['root_OlivOS_terminal_data'])
        try:
            while tmp_count_old < tmp_count_new:
                for line in self.root.UIObject['root_OlivOS_terminal_data'].copy()[tmp_count_old:tmp_count_new]:
                    self.tree_add_line(line)
                tmp_count_old = tmp_count_new
                tmp_count_new = len(self.root.UIObject['root_OlivOS_terminal_data'])
        except:
            pass

    def tree_add_line(self, data):
        data_raw = data['data']
        select_level = self.UIData['level_find'][self.UIData['root_level_StringVar'].get()]
        this_level = data_raw['log_level']
        if select_level <= this_level:
            data_str = data['str']
            data_str = data_str.encode(encoding='gbk', errors='replace').decode(encoding='gbk', errors='replace')
            res_data = data_str
            data_str = data_str.replace('\r', '\\r')
            data_str = data_str.replace('\n', '\\n')
            sig_list = data_raw['log_segment']
            sig_01 = ''
            sig_02 = ''
            sig_03 = ''
            if len(sig_list) >= 1:
                sig_03 = sig_list[0][0]
            if len(sig_list) >= 2:
                sig_02, sig_03 = sig_03, sig_list[1][0]
            if len(sig_list) >= 3:
                sig_01, sig_02, sig_03 = sig_02, sig_03, sig_list[2][0]
            log_level = OlivOS.diagnoseAPI.level_dict[data_raw['log_level']]
            if len(res_data) > 0:
                try:
                    iid = self.UIObject['tree'].insert(
                        '',
                        tkinter.END,
                        text=res_data,
                        values=(
                            str(datetime.datetime.fromtimestamp(int(data_raw['log_time']))),
                            log_level,
                            data_str
                        ),
                        tag=log_level
                    )
                    if self.UIData['flag_tree_is_bottom']:
                        self.UIObject['tree'].see(iid)
                        #self.UIObject['tree'].update()
                except:
                    pass

    def stopManual(self):
        # 手动关闭时要给用户气泡，不然有些用户不知道自己还开着
        try:
            self.root.UIObject['root_shallow'].UIObject['shallow_root'].notify(
                '已最小化至托盘'
            )
        except:
            pass
        self.stop()

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_OlivOS_terminal'] = None


class VirtualTerminalUI(object):
    class VirtualTerminalUI_AccountEdit(object):
        def __init__(self, Model_name, root: "VirtualTerminalUI", root_tk=None, bot=None):
            self.Model_name = Model_name
            self.root = root
            self.root_tk = root_tk
            self.bot = bot
            self.UIObject = {}
            self.UIData = {}
            # 由于 root 在 start 后才会初始化，故在之后调用
            # self.userConfDataInit(self.root.user_conf_data)
            self.UIConfig = {}
            self.UIConfig.update(dictColorContext)
        
        def start(self):
            self.UIObject['root'] = tkinter.Toplevel(
                master=self.root.UIObject['root'],
                bg=self.UIConfig['color_001']
            )
            self.UIObject['root'].title('账号编辑 - %s' % str(self.bot.id))
            self.UIObject['root'].geometry('300x210')
            self.UIObject['root'].minsize(300, 210)
            self.UIObject['root'].resizable(
                width=False,
                height=False
            )
            self.UIObject['root'].configure(bg=self.UIConfig['color_001'])
            self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

            self.userConfDataInit(self.root.user_conf_data)

            self.root_Entry_init(
                obj_root='root',
                obj_name='root_entry_user_name',
                str_name='StringVar_user_name',
                x=15 + 80,
                y=15 + 30 * 0,
                width_t=80,
                width=300 - 15 * 2 - 80,
                height=24,
                action=None,
                title='账号名称:\t',
            )

            self.root_Entry_init(
                obj_root='root',
                obj_name='root_entry_user_id',
                str_name='StringVar_user_id',
                x=15 + 80,
                y=15 + 30 * 1,
                width_t=80,
                width=300 - 15 * 2 - 80,
                height=24,
                action=None,
                title='账号ID:\t',
            )

            def root_checkbutton_flag_action_Func(str_name):
                def resFunc():
                    self.UIData[str_name].set(
                        not self.UIData[str_name].get()
                    )
                return resFunc

            self.init_style()
            self.root_Checkbutton_init(
                obj_root='root',
                obj_name='root_checkbutton_flag_group',
                str_name='BoolVar_flag_group',
                x=15 + 80,
                y=15 + 30 * 2,
                width_t=80,
                width=300 - 15 * 2 - 80,
                height=24,
                action=root_checkbutton_flag_action_Func('BoolVar_flag_group'),
                title='是否为群:\t',
            )

            self.root_Entry_init(
                obj_root='root',
                obj_name='root_entry_group_id',
                str_name='StringVar_group_id',
                x=15 + 80,
                y=15 + 30 * 3,
                width_t=80,
                width=300 - 15 * 2 - 80,
                height=24,
                action=None,
                title='群组ID:\t',
            )

            self.root_ComboBox_init(
                obj_root='root',
                obj_name='root_combobox_group_role',
                str_name='StringVar_group_role',
                x=15 + 80,
                y=15 + 30 * 4,
                width_t=80,
                width=300 - 15 * 2 - 80,
                height=24,
                action=["owner", "admin", "member", "unknown"],
                title='群组角色:\t',
            )

            self.root_Button_init(
                name='root_button_save',
                text='保存并返回',
                command=self.root_button_save_Func(),
                x=15 + 80,
                y=15 + 30 * 5,
                width=300 - 15 * 2 - 80,
                height=24
            )

            self.UIObject['root'].mainloop()

            self.stop()

        def root_button_save_Func(self):
            def resFunc():
                self.setUserConfDataFunc()
                # print(self.root.user_conf_data)
                self.stop()
            return resFunc

        def userConfDataInit(self, datadict):
            """
                根据 VirtualTerminalUI 的用户信息，初始化编辑界面中的用户信息数据
            """
            self.UIData['StringVar_user_name'] = tkinter.StringVar(
                master=self.UIObject['root'],
                name='StringVar_user_name',
                value=datadict['user_name']
            )
            self.UIData['StringVar_user_id'] = tkinter.StringVar(
                master=self.UIObject['root'],
                name='StringVar_user_id',
                value=datadict['user_id']
            )
            self.UIData['BoolVar_flag_group'] = tkinter.BooleanVar(
                master=self.UIObject['root'],
                name='BoolVar_flag_group',
                value=datadict['flag_group']
            )
            self.UIData['StringVar_group_id'] = tkinter.StringVar(
                master=self.UIObject['root'],
                name='StringVar_group_id',
                value=datadict['group_id']
            )
            self.UIData['StringVar_group_role'] = tkinter.StringVar(
                master=self.UIObject['root'],
                name='StringVar_group_role',
                value=datadict['group_role']
            )


        def setUserConfDataFunc(self):
            """
                根据编辑界面中的用户信息数据，更新 VirtualTerminalUI 的用户信息
            """
            tmp_data = {}
            tmp_data['user_name'] = self.UIData['StringVar_user_name'].get()
            tmp_data['user_id'] = self.UIData['StringVar_user_id'].get()
            tmp_data['flag_group'] = self.UIData['BoolVar_flag_group'].get()
            tmp_data['group_id'] = self.UIData['StringVar_group_id'].get()
            tmp_data['group_role'] = self.UIData['StringVar_group_role'].get()
            if tmp_data['flag_group']:
                tmp_data['target_id'] = self.UIData['StringVar_group_id'].get()

            else:
                tmp_data['target_id'] = self.root.bot.id        # 当为私聊消息时，target_id 为 bot 的 id
            self.root.user_conf_data = tmp_data


        def buttom_action(self, name, action):
            if name in self.UIObject:
                if action == '<Enter>':
                    self.UIObject[name].configure(bg=self.UIConfig['color_006'])
                if action == '<Leave>':
                    self.UIObject[name].configure(bg=self.UIConfig['color_003'])

        def root_Button_init(self, name, text, command, x, y, width, height):
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
            self.UIObject[name].place(
                x=x,
                y=y,
                width=width,
                height=height
            )

        def init_style(self):
            self.UIData['style'] = ttk.Style(self.UIObject['root'])
            self.UIData['style'].configure(
                "TCheckbutton",
                indicatorbackground=self.UIConfig['color_001'],
                indicatorforeground=self.UIConfig['color_004'],
                background=self.UIConfig['color_001'],
                foreground=self.UIConfig['color_004']
            )
            #self.UIData['style'].map("TCheckbutton", background=[("active", "darkgrey")])

        def root_Checkbutton_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title=''):
            self.UIObject[obj_name + '=Label'] = tkinter.Label(
                self.UIObject[obj_root],
                text=title
            )
            self.UIObject[obj_name + '=Label'].configure(
                bg=self.UIConfig['color_001'],
                fg=self.UIConfig['color_004']
            )
            self.UIObject[obj_name + '=Label'].place(
               x = x - width_t,
               y = y,
               width = width_t,
               height = height
            )
            # self.UIData[str_name] = tkinter.BooleanVar(
            #     master=self.UIObject[obj_name],
            #     name=str_name,
            # )
            self.UIObject[obj_name] = ttk.Checkbutton(
                self.UIObject[obj_root],
                variable=self.UIData[str_name],
                onvalue=True,
                offvalue=False,
                style='TCheckbutton'
            )
            # self.UIObject[obj_name].configure(
            #     bg=self.UIConfig['color_001'],
            #     fg=self.UIConfig['color_004'],
            #     bd=0
            # )
            self.UIObject[obj_name].place(
               x = x,
               y = y
            )

        def root_ComboBox_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title=''):
            self.UIObject[obj_name] = tkinter.Label(
                self.UIObject[obj_root],
                bg=self.UIConfig['color_001'],
                width=width,
                height=height
            )
            self.UIObject[obj_name + '=Label'] = tkinter.Label(
                self.UIObject[obj_root],
                text=title
            )
            self.UIObject[obj_name + '=Label'].configure(
                bg=self.UIConfig['color_001'],
                fg=self.UIConfig['color_004']
            )
            self.UIObject[obj_name + '=Label'].place(
               x = x - width_t,
               y = y,
               width = width_t,
               height = height
            )
            # self.UIData[str_name] = tkinter.StringVar(
            #     master=self.UIObject[obj_name],
            #     name=str_name,
            # )
            self.UIObject[obj_name] = ttk.Combobox(
                self.UIObject[obj_root],
                textvariable=self.UIData[str_name],
                values=action,
                state='readonly',
            )
            # self.UIObject[obj_name].configure(
            #     bg=self.UIConfig['color_004'],
            #     fg=self.UIConfig['color_005'],
            #     bd=0
            # )
            self.UIObject[obj_name].place(
               x = x,
               y = y,
               width = width,
               height = height
            )

        def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title='', mode='NONE'):
            self.UIObject[obj_name + '=Label'] = tkinter.Label(
                self.UIObject[obj_root],
                text=title
            )
            self.UIObject[obj_name + '=Label'].configure(
                bg=self.UIConfig['color_001'],
                fg=self.UIConfig['color_004']
            )
            self.UIObject[obj_name + '=Label'].place(
               x = x - width_t,
               y = y,
               width = width_t,
               height = height
            )
            self.UIObject[obj_name] = tkinter.Entry(
                self.UIObject[obj_root],
                textvariable=self.UIData[str_name]
            )
            self.UIObject[obj_name].configure(
                bg=self.UIConfig['color_004'],
                fg=self.UIConfig['color_005'],
                bd=0
            )
            self.UIObject[obj_name].place(
               x = x,
               y = y,
               width = width,
               height = height
            )
            if mode == 'SAFE':
                self.UIObject[obj_name].configure(
                    show='●'
                )


        def stop(self):
            self.exit()
            self.UIObject['root'].destroy()

        def exit(self):
            self.root.UIObject["root_terminal_account_edit"] = None

    def __init__(self, Model_name, logger_proc, root: dock, root_tk=None, bot=None):
        self.Model_name = Model_name
        self.root = root
        self.root_tk = root_tk
        self.bot = bot
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIConfig.update(dictColorContext)
        self.user_conf_data = {
            "user_name": "仑质",
            "user_id": "88888888",
            "flag_group": True,
            "group_id": "88888888",
            "group_role": "owner",
        }
        self.user_conf_data["target_id"] = self.user_conf_data["group_id"]

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('Virtual Terminal 终端 - %s' % str(self.bot.id))
        self.UIObject['root'].geometry('800x600')
        self.UIObject['root'].minsize(800, 600)
        self.UIObject['root'].grid_rowconfigure(0, weight=15)
        self.UIObject['root'].grid_rowconfigure(1, weight=0)
        self.UIObject['root'].grid_columnconfigure(0, weight=0)
        self.UIObject['root'].grid_columnconfigure(1, weight=2)
        self.UIObject['root'].grid_columnconfigure(2, weight=2)
        self.UIObject['root'].grid_columnconfigure(3, weight=0)
        self.UIObject['root'].resizable(
            width=True,
            height=True
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('DATA')
        self.UIObject['tree'].column('DATA', width=800 - 15 * 2 - 18 - 5)
        self.UIObject['tree'].heading('DATA', text='日志')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['tree'].bind('<Button-3>', lambda x: self.tree_rightKey(x))
        self.UIObject['tree'].grid(
            row=0,
            column=0,
            sticky="nsew",
            rowspan=1,
            columnspan=3,
            padx=(15, 0),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient="vertical",
            command=self.UIObject['tree'].yview
        )
        self.UIObject['tree_yscroll'].grid(
            row=0,
            column=3,
            sticky="nsw",
            rowspan=1,
            columnspan=1,
            padx=(0, 15),
            pady=(15, 0),
            ipadx=0,
            ipady=0
        )
        self.UIData['flag_tree_is_bottom'] = True
        self.UIObject['tree'].configure(
            yscrollcommand=self.scroll_onChange(self.UIObject['tree_yscroll'].set)
        )

        self.root_Entry_init(
            obj_root='root',
            obj_name='root_input',
            str_name='root_input_StringVar',
            x=15,
            y=600 - 15 * 1 - 24,
            width_t=0,
            width=800 - 15 * 2,
            height=24,
            action=None,
            title='输入'
        )
        self.UIObject['root_input'].bind("<Return>", self.root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row=1,
            column=0,
            sticky="s",
            rowspan=1,
            columnspan=2,
            padx=(15, 0),
            pady=(8, 15),
            ipadx=0,
            ipady=4
        )

        self.root_Button_init(
            name='root_button_save',
            text='>',
            command=self.root_Entry_enter_Func('root_input'),
            x=800 - 15 * 2 - 5,
            y=600 - 15 * 1 - 24,
            width=16,
            height=1
        )
        self.UIObject['root_button_save'].grid(
            row=1,
            column=2,
            sticky="swe",
            rowspan=1,
            columnspan=2,
            padx=(0, 15),
            pady=(8, 15),
            ipadx=8,
            ipady=0
        )

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        self.tree_init_line()

        self.UIObject['root'].mainloop()

        self.exit()

    def scroll_onChange(self, command):
        def res(*arg, **kwarg):
            if arg[1] == '1.0':
                self.UIData['flag_tree_is_bottom'] = True
            else:
                self.UIData['flag_tree_is_bottom'] = False
            return command(*arg, **kwarg)
        return res

    def tree_rightKey(self, event):
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label='查看', command=lambda: self.rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label='复制', command=lambda: self.rightKey_action('copy'))
        self.UIObject['tree_rightkey_menu'].add_command(label='编辑账号', command=lambda: self.rightKey_action('account'))
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def rightKey_action(self, action: str):
        if action == 'show':
            msg = get_tree_force(self.UIObject['tree'])['text']
            if len(msg) > 0:
                msg = msg.replace('\ ', ' ')
                messagebox.showinfo('日志内容', msg)
        elif action == 'copy':
            msg = get_tree_force(self.UIObject['tree'])['text']
            if len(msg) > 0:
                msg = msg.replace('\ ', ' ')
                self.UIObject['root'].clipboard_clear()
                self.UIObject['root'].clipboard_append(msg)
                self.UIObject['root'].update()
        elif action == 'account':
            self.root_AccountEdit_init()

    def root_AccountEdit_init(self):
        """
            用于初始化账号编辑界面(如果存在则关闭后重新打开)
        """
        if "root_terminal_account_edit" not in self.UIObject:
            self.UIObject["root_terminal_account_edit"] = None
        elif self.UIObject['root_terminal_account_edit'] is not None:
            self.UIObject['root_terminal_account_edit'].stop()
        
        self.UIObject['root_terminal_account_edit'] = self.VirtualTerminalUI_AccountEdit(
            Model_name=self.Model_name,
            root=self,
            root_tk=self.root_tk,
            bot=self.bot
        )
        self.UIObject['root_terminal_account_edit'].start()

    def root_Entry_enter_Func(self, name):
        def resFunc(*arg, **kwarg):
            self.root_Entry_enter(name, None)

        return resFunc

    def root_Entry_enter(self, name, event):
        if name == 'root_input':
            input = self.UIData['root_input_StringVar'].get()
            if len(input) > 0 and len(input) < 1000:
                self.root.setVirtualModelSend(self.bot.hash, input, self.user_conf_data)
            self.UIData['root_input_StringVar'].set('')

    def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title='',
                        mode='NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root],
            textvariable=self.UIData[str_name],
            font=('TkDefaultFont 12')
        )
        self.UIObject[obj_name].configure(
            bg=self.UIConfig['color_004'],
            fg=self.UIConfig['color_005'],
            bd=0
        )
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show='●'
            )
        self.UIObject[obj_name].configure(
            width=width
        )

    def tree_init_line(self):
        if self.bot.hash in self.root.UIObject['root_virtual_terminal_terminal_data']:
            for line in self.root.UIObject['root_virtual_terminal_terminal_data'][self.bot.hash]:
                self.tree_add_line(line)

    def tree_add_line(self, data, user_conf=None):
        res_data = data['data']
        if user_conf is None:
            user_conf = data["user_conf"]
        res_data = res_data.encode(encoding='gb2312', errors='replace').decode(encoding='gb2312', errors='replace')
        res_data_1 = res_data
        res_data = res_data.replace(' ', r'\ ')
        res_data = res_data.replace('\r\n', '\n')
        if not user_conf['flag_group']:
            data_header = f"<{user_conf['user_name']}> ({user_conf['user_id']}) -> (用户: {user_conf['target_id']})"
        else:
            data_header = f"<{user_conf['user_name']}> ({user_conf['user_id']}) -> (群: {user_conf['target_id']})"
        data_header = data_header.replace(' ', r'\ ')
        data_header = data_header.replace('\r\n', '\n')
        res_data = '%s\n%s\n%s' % (data_header, res_data, '-' * 25)
        res_data_list = res_data.split('\n')
        for res_data_list_this in res_data_list:
            try:
                iid = self.UIObject['tree'].insert(
                    '',
                    tkinter.END,
                    text=res_data_list_this,
                    values=(
                        res_data_list_this
                    )
                )
                if self.UIData['flag_tree_is_bottom']:
                    self.UIObject['tree'].see(iid)
                    #self.UIObject['tree'].update()
            except:
                pass

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def root_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['root'],
            text=text,
            command=command,
            bd=0,
            activebackground=self.UIConfig['color_002'],
            activeforeground=self.UIConfig['color_001'],
            bg=self.UIConfig['color_003'],
            fg=self.UIConfig['color_004'],
            relief='groove',
            height=height
        )
        self.UIObject[name].bind('<Enter>', lambda x: self.buttom_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda x: self.buttom_action(name, '<Leave>'))

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_virtual_terminal_terminal'].pop(self.bot.hash)


class shallow(object):
    def __init__(self, name: str, image: str, root):
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
        if data is not None:
            if type(data) == list:
                list_new = []
                for item_this in data:
                    if type(item_this) == list:
                        # 处理账号信息项（禁用）
                        if len(item_this) == 3 and item_this[0] == 'account_info':
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
                        elif len(item_this) == 3:
                            if type(item_this[1]) == str and type(item_this[2]) == str:
                                list_new.append(
                                    pystray.MenuItem(
                                        item_this[0],
                                        self.root.sendPluginControlEventFunc(
                                            item_this[1],
                                            item_this[2]
                                        )
                                    )
                                )
                        elif len(item_this) == 4:
                            if type(item_this[1]) == str and type(item_this[2]) == str and type(item_this[3]) == str:
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
            else:
                return data
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
        
        if self.root != None:
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
                if type(plugin_menu_now[4]) == str:
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
            if type(plugin_menu_now[3]) == list:
                for plugin_menu_this in plugin_menu_now[3]:
                    self.UIObject['tree_rightkey_menu'].add_command(label=plugin_menu_this[0],
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


def get_tree_force(tree_obj):
    return tree_obj.item(tree_obj.focus())


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
