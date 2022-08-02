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
@Copyright :   (C) 2020-2021, OlivOS-Team
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

from PIL import Image
from PIL import ImageTk

from tkinter import ttk
from tkinter import messagebox


dictColorContext = {
    'color_001': '#00A0EA',
    'color_002': '#BBE9FF',
    'color_003': '#40C3FF',
    'color_004': '#FFFFFF',
    'color_005': '#000000',
    'color_006': '#80D7FF'
}

class StoppableThread(threading.Thread):
    def __init__(self,  *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()

    def terminate(self):
        self._stop_event.set()

    def stop(self):
        self._stop_event.set()

    def join(self):
        pass

    def stopped(self):
        return self._stop_event.is_set()


class dock(OlivOS.API.Proc_templet):
    def __init__(
        self,
        Proc_name = 'native_nativeWinUI',
        scan_interval = 0.001,
        dead_interval = 1,
        rx_queue = None,
        tx_queue = None,
        logger_proc = None,
        control_queue = None,
        bot_info_dict = None
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name = Proc_name,
            Proc_type = 'nativeWinUI',
            scan_interval = scan_interval,
            dead_interval = dead_interval,
            rx_queue = rx_queue,
            tx_queue = tx_queue,
            control_queue = control_queue,
            logger_proc = logger_proc
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
        self.UIObject['root_gocqhttp_terminal_data_max'] = 150
        self.UIObject['root_qrcode_window'] = {}
        self.UIObject['root_qrcode_window_thread'] = {}
        self.UIObject['root_qrcode_window_enable'] = False
        self.UIObject['root_plugin_edit'] = {}
        self.UIObject['root_plugin_edit_enable'] = False
        self.UIObject['root_plugin_edit_count'] = 0
        self.UIData['shallow_plugin_menu_list'] = None
        self.UIData['shallow_gocqhttp_menu_list'] = None
        self.UIData['shallow_plugin_data_dict'] = None
        self.updateShallowMenuList()

    def run(self):
        self.UIObject['main_tk'] = tkinter.Tk()
        self.UIObject['main_tk'].withdraw()
        self.UIObject['main_tk'].iconbitmap('./resource/tmp_favoricon.ico')
        self.process_msg()
        self.UIObject['main_tk'].mainloop()

    def process_msg(self):
        self.UIObject['main_tk'].after(50,self.process_msg)
        self.mainrun()

    def mainrun(self):
        if True:
            if self.Proc_info.rx_queue.empty() or self.Proc_config['ready_for_restart']:
                time.sleep(self.Proc_info.scan_interval)
            else:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block = False)
                except:
                    rx_packet_data = None
                if rx_packet_data != None:
                    if type(rx_packet_data) == OlivOS.API.Control.packet:
                        if rx_packet_data.action == 'send':
                            if type(rx_packet_data.key) == dict:
                                if 'data' in rx_packet_data.key:
                                    if 'action' in rx_packet_data.key['data']:
                                        if 'update_data' == rx_packet_data.key['data']['action']:
                                            self.UIData.update(rx_packet_data.key['data']['data'])
                                            self.updateShallowMenuList()
                                        elif 'start_shallow' == rx_packet_data.key['data']['action']:
                                            if self.UIObject['root_shallow'] == None:
                                                self.startShallow()
                                                self.startOlivOSTerminalUISend()
                                            else:
                                                self.updateShallow()
                                                self.updatePluginEdit()
                                        elif 'plugin_edit_menu_on' == rx_packet_data.key['data']['action']:
                                            self.startPluginEdit()
                                        elif 'logger' == rx_packet_data.key['data']['action']:
                                            self.UIObject['root_OlivOS_terminal_data'].append(rx_packet_data.key['data']['data'])
                                            if len(self.UIObject['root_OlivOS_terminal_data']) > self.UIObject['root_OlivOS_terminal_data_max']:
                                                self.UIObject['root_OlivOS_terminal_data'].pop(0)
                                            if self.UIObject['root_OlivOS_terminal'] != None:
                                                self.UIObject['root_OlivOS_terminal'].tree_add_line(rx_packet_data.key['data']['data'])
                                        elif 'gocqhttp' == rx_packet_data.key['data']['action']:
                                            if 'event' in rx_packet_data.key['data']:
                                                if 'init' == rx_packet_data.key['data']['event']:
                                                    if self.UIData['shallow_gocqhttp_menu_list'] == None:
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
                                                    if self.UIObject['root_shallow'] != None:
                                                        self.updateShallow()
                                                    self.startGoCqhttpTerminalUISend(rx_packet_data.key['data']['hash'])
                                                elif 'log' == rx_packet_data.key['data']['event']:
                                                    if 'hash' in rx_packet_data.key['data'] and 'data' in rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash not in self.UIObject['root_gocqhttp_terminal_data']:
                                                            self.UIObject['root_gocqhttp_terminal_data'][hash] = []
                                                        self.UIObject['root_gocqhttp_terminal_data'][hash].append(rx_packet_data.key['data']['data'])
                                                        if len(self.UIObject['root_gocqhttp_terminal_data'][hash]) > self.UIObject['root_gocqhttp_terminal_data_max']:
                                                            self.UIObject['root_gocqhttp_terminal_data'][hash].pop(0)
                                                        if hash in self.UIObject['root_gocqhttp_terminal']:
                                                            self.UIObject['root_gocqhttp_terminal'][hash].tree_add_line(rx_packet_data.key['data']['data'])
                                                elif 'qrcode' == rx_packet_data.key['data']['event']:
                                                    if 'hash' in rx_packet_data.key['data'] and 'path' in rx_packet_data.key['data']:
                                                        hash = rx_packet_data.key['data']['hash']
                                                        if hash in self.bot_info:
                                                            if hash in self.UIObject['root_qrcode_window']:
                                                                try:
                                                                    self.UIObject['root_qrcode_window'][hash].stop()
                                                                except:
                                                                    pass
                                                            self.UIObject['root_qrcode_window'][hash] = QRcodeUI(
                                                                Model_name = 'qrcode_window',
                                                                logger_proc = self.Proc_info.logger_proc.log,
                                                                root = self,
                                                                root_tk = None,
                                                                bot = self.bot_info[hash],
                                                                path = rx_packet_data.key['data']['path']
                                                            )
                                                            self.UIObject['root_qrcode_window'][hash].start()
                                                elif 'gocqhttp_terminal_on' == rx_packet_data.key['data']['event']:
                                                    if 'hash' in rx_packet_data.key['data']:
                                                        self.startGoCqhttpTerminalUI(rx_packet_data.key['data']['hash'])
                                        elif 'OlivOS_terminal_on' == rx_packet_data.key['data']['action']:
                                            self.startOlivOSTerminalUI()

    def updateShallowMenuList(self):
        tmp_new = []
        self.UIData['shallow_menu_list'] = [
            ['账号管理', False],
            ['打开终端', self.startOlivOSTerminalUISend],
            ['gocqhttp管理', self.UIData['shallow_gocqhttp_menu_list']],
            ['插件管理', self.startPluginEditSend],
            ['插件菜单', self.UIData['shallow_plugin_menu_list']],
            ['重载插件', self.sendPluginRestart],
            ['退出OlivOS', self.setOlivOSExit]
        ]
        for data_this in self.UIData['shallow_menu_list']:
            if data_this[0] == 'gocqhttp管理':
                if data_this[1] != None:
                    tmp_new.append(data_this)
            else:
                tmp_new.append(data_this)
        self.UIData['shallow_menu_list'] = tmp_new

    def startGoCqhttpTerminalUISendFunc(self, hash):
        def resFunc():
            self.startGoCqhttpTerminalUISend(hash)
        return resFunc

    def startGoCqhttpTerminalUISend(self, hash):
        self.sendControlEventSend('send', {
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

    def startGoCqhttpTerminalUI(self, hash):
        if hash in self.bot_info:
            if hash in self.UIObject['root_gocqhttp_terminal']:
                try:
                    self.UIObject['root_gocqhttp_terminal'][hash].stop()
                except:
                    pass
            self.UIObject['root_gocqhttp_terminal'][hash] = gocqhttpTerminalUI(
                Model_name = 'gocqhttp_terminal',
                logger_proc = self.Proc_info.logger_proc.log,
                root = self,
                root_tk = None,
                bot = self.bot_info[hash]
            )
            self.UIObject['root_gocqhttp_terminal'][hash].start()

    def startOlivOSTerminalUISend(self):
        self.sendControlEventSend('send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'OlivOS_terminal_on'
                }
            }
        )

    def startOlivOSTerminalUI(self):
        if self.UIObject['root_OlivOS_terminal'] != None:
            try:
                self.UIObject['root_OlivOS_terminal'].stop()
            except:
                pass
        self.UIObject['root_OlivOS_terminal'] = OlivOSTerminalUI(
            Model_name = 'OlivOS_terminal',
            logger_proc = self.Proc_info.logger_proc.log,
            root = self,
            root_tk = None
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

    def startPluginEditSend(self):
        self.sendControlEventSend('send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'plugin_edit_menu_on'
                }
            }
        )

    def startPluginEdit(self):
        count_str = str(self.UIObject['root_plugin_edit_count'])
        #self.UIObject['root_plugin_edit_count'] += 1
        if count_str not in self.UIObject['root_plugin_edit']:
            self.UIObject['root_plugin_edit'][count_str] = {}
            self.UIObject['root_plugin_edit'][count_str]['obj'] = pluginManageUI(
                Model_name = 'shallow_menu_plugin_manage',
                logger_proc = self.Proc_info.logger_proc.log,
                root = self,
                key = count_str
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
        if self.Proc_info.control_queue != None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block = False
            )

    def sendControlEvent(self, eventName:str):
        if self.UIObject['root_shallow'] != None:
            self.UIObject['root_shallow'].UIObject['shallow_root'].notify(
                '正在退出……'
            )
        if self.Proc_info.control_queue != None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(eventName, self.Proc_name),
                block = False
            )

    def sendPluginRestart(self):
        if self.UIObject['root_shallow'] != None:
            self.UIObject['root_shallow'].UIObject['shallow_root'].notify(
                '正在重载……'
            )
        if self.Proc_info.control_queue != None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet('restart_send', 'plugin'),
                block = False
            )

    def startShallow(self):
        releaseBase64Data('./resource', 'tmp_favoricon.ico', OlivOS.data.favoricon)
        if self.UIObject['root_shallow'] == None:
            self.UIObject['root_shallow'] = shallow(
                name = 'OlivOS',
                image = './resource/tmp_favoricon.ico',
                root = self
            )
            self.UIObject['root_shallow'].start()

    def updateShallow(self):
        if self.UIObject['root_shallow'] != None:
            self.UIObject['root_shallow'].refresh()

class QRcodeUI(object):
    def __init__(self, Model_name, logger_proc = None, root = None, root_tk = None, bot = None, path = None):
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
            width = False,
            height = False
        )
        self.UIObject['root'].configure(bg = self.UIConfig['color_001'])

        self.UIObject['root_qrcode_img_data'] = Image.open(self.path)
        self.UIObject['root_qrcode_img_data'] = self.UIObject['root_qrcode_img_data'].resize((500, 500), Image.ANTIALIAS)
        self.UIObject['root_qrcode_img'] = ImageTk.PhotoImage(self.UIObject['root_qrcode_img_data'])
        self.UIObject['root_qrcode_label'] = tkinter.Label(self.UIObject['root'])
        self.UIObject['root_qrcode_label'].config(image = self.UIObject['root_qrcode_img'])
        self.UIObject['root_qrcode_label'].image = self.UIObject['root_qrcode_img']
        self.UIObject['root_qrcode_label'].pack()

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')

        self.UIObject['root'].mainloop()

        self.exit()

    def exit(self):
        pass

    def stop(self):
        self.UIObject['root'].quit()

class gocqhttpTerminalUI(object):
    def __init__(self, Model_name, logger_proc = None, root = None, root_tk = None, bot = None):
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
        self.UIObject['root'].grid_rowconfigure(0, weight = 15)
        self.UIObject['root'].grid_rowconfigure(1, weight = 0)
        self.UIObject['root'].grid_columnconfigure(0, weight = 0)
        self.UIObject['root'].grid_columnconfigure(1, weight = 2)
        self.UIObject['root'].grid_columnconfigure(2, weight = 0)
        self.UIObject['root'].resizable(
            width = True,
            height = True
        )
        self.UIObject['root'].configure(bg = self.UIConfig['color_001'])

        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('DATA')
        self.UIObject['tree'].column('DATA', width = 800 - 15 * 2 - 18 - 5)
        self.UIObject['tree'].heading('DATA', text = '日志')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff = False)
        self.UIObject['tree'].bind('<Button-3>', lambda x : self.tree_rightKey(x))
        #self.tree_load()
        #self.UIObject['tree'].place(x = 15, y = 15, width = 800 - 15 * 2 - 18 , height = 600 - 15 * 2 - 24 - 8)
        self.UIObject['tree'].grid(
            row = 0,
            column = 0,
            sticky = "nsew",
            rowspan = 1,
            columnspan = 2,
            padx = (15, 0),
            pady = (15, 0),
            ipadx = 0,
            ipady = 0
        )
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient = "vertical",
            command = self.UIObject['tree'].yview
        )
        #self.UIObject['tree_yscroll'].place(
        #    x = 800 - 15 - 18,
        #    y = 15,
        #    width = 18,
        #    height = 600 - 15 * 2 - 24 - 8
        #)
        self.UIObject['tree_yscroll'].grid(
            row = 0,
            column = 2,
            sticky = "nsw",
            rowspan = 1,
            columnspan = 1,
            padx = (0, 15),
            pady = (15, 0),
            ipadx = 0,
            ipady = 0
        )
        self.UIObject['tree'].configure(
            yscrollcommand = self.UIObject['tree_yscroll'].set
        )

        self.root_Entry_init(
            obj_root = 'root',
            obj_name = 'root_input',
            str_name = 'root_input_StringVar',
            x = 15,
            y = 600 - 15 * 1 - 24,
            width_t = 0,
            width = 800 - 15 * 2,
            height = 24,
            action = None,
            title = '输入'
        )
        self.UIObject['root_input'].bind("<Return>", self.root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row = 1,
            column = 1,
            sticky = "s",
            rowspan = 1,
            columnspan = 3,
            padx = (15, 15),
            pady = (8, 15),
            ipadx = 0,
            ipady = 0
        )
        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        self.tree_init_line()

        self.UIObject['root'].mainloop()

        self.exit()

    def tree_rightKey(self, event):
        #右键设置的选择在后续流程中未生效，不知为何，等后续解决
        #iid = self.UIObject['tree'].identify_row(event.y)
        #self.UIObject['tree'].selection_set(iid)
        #self.UIObject['tree'].update()
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label = '查看', command = lambda : self.rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label = '复制', command = lambda : self.rightKey_action('copy'))
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def rightKey_action(self, action:str):
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
        def resFunc(event):
            self.root_Entry_enter(name, event)
        return resFunc

    def root_Entry_enter(self, name, event):
        if name == 'root_input':
            input = self.UIData['root_input_StringVar'].get()
            if len(input) > 0 and len(input) < 1000:
                self.root.setGoCqhttpModelSend(self.bot.hash, input)
            self.UIData['root_input_StringVar'].set('')

    def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title = '', mode = 'NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text = title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004']
        )
        #self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        #)
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root],
            textvariable = self.UIData[str_name]
        )
        self.UIObject[obj_name].configure(
            bg = self.UIConfig['color_004'],
            fg = self.UIConfig['color_005'],
            bd = 0
        )
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show = '●'
            )
        self.UIObject[obj_name].configure(
            width = width
        )
        #self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        #)

    def tree_init_line(self):
        if self.bot.hash in self.root.UIObject['root_gocqhttp_terminal_data']:
            for line in self.root.UIObject['root_gocqhttp_terminal_data'][self.bot.hash]:
                self.tree_add_line(line)

    def tree_add_line(self, data):
        res_data = re.sub('\033\[[\d;]*m?', '', data)
        res_data = res_data.encode(encoding = 'gb2312', errors = 'replace').decode(encoding = 'gb2312', errors = 'replace')
        res_data_1 = res_data
        res_data = res_data.replace(' ', '\ ')
        if len(res_data.replace('\ ', '')) > 0:
            try:
                iid = self.UIObject['tree'].insert(
                    '',
                    tkinter.END,
                    text = res_data_1,
                    values=(
                        res_data
                    )
                )
                self.UIObject['tree'].see(iid)
                self.UIObject['tree'].update()
            except:
                pass

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_gocqhttp_terminal'].pop(self.bot.hash)


class OlivOSTerminalUI(object):
    def __init__(self, Model_name, logger_proc = None, root = None, root_tk = None):
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
        self.UIObject['root'].title('OlivOS 终端')
        self.UIObject['root'].geometry('900x600')
        self.UIObject['root'].minsize(900, 600)
        self.UIObject['root'].grid_rowconfigure(0, weight = 15)
        self.UIObject['root'].grid_rowconfigure(1, weight = 0)
        self.UIObject['root'].grid_columnconfigure(0, weight = 0)
        self.UIObject['root'].grid_columnconfigure(1, weight = 2)
        self.UIObject['root'].grid_columnconfigure(2, weight = 0)
        self.UIObject['root'].resizable(
            width = True,
            height = True
        )
        self.UIObject['root'].configure(bg = self.UIConfig['color_001'])
        self.UIObject['root'].bind('<Configure>', self.root_resize)

        self.UIObject['style'] = ttk.Style()
        fix_Treeview_color(self.UIObject['style'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])

        for level_this in OlivOS.diagnoseAPI.level_dict:
            self.UIObject['tree'].tag_configure(
                OlivOS.diagnoseAPI.level_dict[level_this],
                foreground = OlivOS.diagnoseAPI.level_color_dict[
                    OlivOS.diagnoseAPI.level_dict[level_this]
                ]
            )

        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('TIME', 'LEVEL', 'DATA')
        self.UIObject['tree'].column('TIME', width = 140)
        self.UIObject['tree'].column('LEVEL', width = 50)
        #self.UIObject['tree'].column('SIG_01', width = 80)
        #self.UIObject['tree'].column('SIG_02', width = 80)
        #self.UIObject['tree'].column('SIG_03', width = 80)
        self.UIObject['tree'].column('DATA', width = 710 - 15 * 2 - 18 - 5)
        self.UIObject['tree'].heading('TIME', text = '时间')
        self.UIObject['tree'].heading('LEVEL', text = '等级')
        #self.UIObject['tree'].heading('SIG_01', text = '')
        #self.UIObject['tree'].heading('SIG_02', text = '')
        #self.UIObject['tree'].heading('SIG_03', text = '')
        self.UIObject['tree'].heading('DATA', text = '日志')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff = False)
        self.UIObject['tree'].bind('<Button-3>', lambda x : self.tree_rightKey(x))
        #self.tree_load()
        #self.UIObject['tree'].place(x = 15, y = 15, width = 900 - 15 * 2 - 18 , height = 600 - 15 * 2 - 24 - 8)
        self.UIObject['tree'].grid(
            row = 0,
            column = 0,
            sticky = "nsew",
            rowspan = 1,
            columnspan = 2,
            padx = (15, 0),
            pady = (15, 0),
            ipadx = 0,
            ipady = 0
        )
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient = "vertical",
            command = self.UIObject['tree'].yview
        )
        self.UIObject['tree_yscroll'].grid(
            row = 0,
            column = 2,
            sticky = "nsw",
            rowspan = 1,
            columnspan = 1,
            padx = (0, 15),
            pady = (15, 0),
            ipadx = 0,
            ipady = 0
        )
        self.UIObject['tree'].configure(
            yscrollcommand = self.UIObject['tree_yscroll'].set
        )

        self.tree_edit_UI_Combobox_init(
            obj_root = 'root',
            obj_name = 'root_level',
            str_name = 'root_level_StringVar',
            x = 15,
            y = 600 - 15 * 1 - 24,
            width_t = 0,
            width = 50,
            height = 24,
            action = None,
            title = '等级'
        )
        self.UIObject['root_level'].grid(
            row = 1,
            column = 0,
            sticky = "ns",
            rowspan = 1,
            columnspan = 1,
            padx = (15, 8),
            pady = (9, 15),
            ipadx = 0,
            ipady = 0
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
            obj_root = 'root',
            obj_name = 'root_input',
            str_name = 'root_input_StringVar',
            x = 15 + 70 + 8,
            y = 600 - 15 * 1 - 24,
            width_t = 0,
            width = 900,
            height = 24,
            action = None,
            title = '输入'
        )
        self.UIObject['root_input'].bind("<Return>", self.root_Entry_enter_Func('root_input'))
        self.UIObject['root_input'].grid(
            row = 1,
            column = 1,
            sticky = "s",
            rowspan = 1,
            columnspan = 2,
            padx = (0, 15),
            pady = (8, 15),
            ipadx = 0,
            ipady = 0
        )

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')
        self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.stop)

        self.tree_init_line()

        self.UIObject['root'].mainloop()

        self.exit()

    def tree_rightKey(self, event):
        #右键设置的选择在后续流程中未生效，不知为何，等后续解决
        #iid = self.UIObject['tree'].identify_row(event.y)
        #self.UIObject['tree'].selection_set(iid)
        #self.UIObject['tree'].update()
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label = '查看', command = lambda : self.rightKey_action('show'))
        self.UIObject['tree_rightkey_menu'].add_command(label = '复制', command = lambda : self.rightKey_action('copy'))
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def rightKey_action(self, action:str):
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

    def root_resize(self, event = None):
        pass

    def root_Entry_enter_Func(self, name):
        def resFunc(event):
            self.root_Entry_enter(name, event)
        return resFunc

    def root_Entry_enter(self, name, event):
        if name == 'root_input':
            #input = self.UIData['root_input_StringVar'].get()
            #if len(input) > 0:
            #    self.root.setGoCqhttpModelSend(self.bot.hash, input)
            #self.UIData['root_input_StringVar'].set('')
            pass

    def root_Entry_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title = '', mode = 'NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text = title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004']
        )
        #self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        #)
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = tkinter.Entry(
            self.UIObject[obj_root],
            textvariable = self.UIData[str_name]
        )
        self.UIObject[obj_name].configure(
            bg = self.UIConfig['color_004'],
            fg = self.UIConfig['color_005'],
            bd = 0
        )
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show = '●'
            )
        self.UIObject[obj_name].configure(
            width = width
        )
        #self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        #)

    def tree_edit_UI_Combobox_init(self, obj_root, obj_name, str_name, x, y, width_t, width, height, action, title = ''):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text = title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004']
        )
        #self.UIObject[obj_name + '=Label'].place(
        #    x = x - width_t,
        #    y = y,
        #    width = width_t,
        #    height = height
        #)
        self.UIData[str_name] = tkinter.StringVar()
        self.UIObject[obj_name] = ttk.Combobox(
            self.UIObject[obj_root],
            textvariable = self.UIData[str_name]
        )
        #self.UIObject[obj_name].place(
        #    x = x,
        #    y = y,
        #    width = width,
        #    height = height
        #)
        self.UIObject[obj_name].configure(state='readonly')
        #self.UIObject[obj_name].bind('<<ComboboxSelected>>', lambda x : self.tree_edit_UI_Combobox_ComboboxSelected(x, action, obj_name))


    def tree_init_line(self):
        for line in self.root.UIObject['root_OlivOS_terminal_data']:
            self.tree_add_line(line)

    def tree_add_line(self, data):
        data_raw = data['data']
        select_level = self.UIData['level_find'][self.UIData['root_level_StringVar'].get()]
        this_level = data_raw['log_level']
        if select_level <= this_level:
            data_str = data['str']
            data_str = data_str.encode(encoding = 'gbk', errors = 'replace').decode(encoding = 'gbk', errors = 'replace')
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
                        text = res_data,
                        values=(
                            str(datetime.datetime.fromtimestamp(int(data_raw['log_time']))),
                            log_level,
                            data_str
                        ),
                        tag = log_level
                    )
                    self.UIObject['tree'].see(iid)
                    self.UIObject['tree'].update()
                except:
                    pass

    def stop(self):
        self.exit()
        self.UIObject['root'].destroy()

    def exit(self):
        self.root.UIObject['root_OlivOS_terminal'] = None

class shallow(object):
    def __init__(self, name:str, image:str, root):
        self.name = name
        self.image = image
        self.root = root
        self.UIObject = {}
        self.UIData = {}
        self.UIData['shallow_menu_list'] = None
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
        if data != None:
            if type(data) == list:
                list_new = []
                for item_this in data:
                    if type(item_this) == list:
                        if len(item_this) == 2:
                            tmp_sub_menu = self.getMenu(item_this[1])
                            list_new.append(
                                pystray.MenuItem(
                                    item_this[0],
                                    tmp_sub_menu,
                                    enabled = (tmp_sub_menu not in [None, False])
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
            name = self.name,
            icon = image,
            title = self.name,
            menu = self.UIObject['shallow_menu']
        )
        self.UIObject['shallow_root'].run_detached()

class pluginManageUI(object):
    def __init__(self, Model_name, logger_proc = None, root = None, key = None):
        self.Model_name = Model_name
        self.root = root
        self.key = key
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIData['flag_commit'] = False
        self.UIData['click_record'] = {}
        self.UIConfig.update(dictColorContext)

    def start(self):
        self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('OlivOS 插件管理器')
        self.UIObject['root'].geometry('518x400')
        self.UIObject['root'].resizable(
            width = False,
            height = False
        )
        self.UIObject['root'].configure(bg = self.UIConfig['color_001'])

        self.tree_init()
        
        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient = "vertical",
            command = self.UIObject['tree'].yview
        )
        self.UIObject['tree_yscroll'].place(
            x = 15 + 350 - 18,
            y = 15,
            width = 18,
            height = 370 - 1
        )
        self.UIObject['tree'].configure(
            yscrollcommand = self.UIObject['tree_yscroll'].set
        )

        self.tree_UI_Label_init(
            name = 'root_Label_INFO_title',
            title = 'root_Label_INFO_title_StringVar',
            x = 375,
            y = 15,
            width = 120,
            height = 300
        )
        self.UIData['root_Label_INFO_title_StringVar'].set('介绍')

        self.tree_UI_Label_init(
            name = 'root_Label_INFO',
            title = 'root_Label_INFO_StringVar',
            x = 380,
            y = 35,
            width = 120,
            height = 300
        )
        self.UIData['root_Label_INFO_StringVar'].set('未选定插件')

        self.tree_UI_Button_init(
            name = 'root_Button_RESTART',
            text = '重载插件',
            command = lambda : self.sendPluginRestart(),
            x = 380,
            y = (400 - 34 - 15 - 40 * 1),
            width = 120,
            height = 34
        )
        
        self.tree_UI_Button_init(
            name = 'root_Button_MENU',
            text = '插件菜单',
            command = lambda : self.pluginMenu('root_Button_MENU'),
            x = 380,
            y = (400 - 34 - 15 - 40 * 0),
            width = 120,
            height = 34
        )

        #self.UIObject['root'].protocol("WM_DELETE_WINDOW", self.exit)

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
        self.UIObject['tree']['columns'] = ('NAME', 'VERSION', 'AUTHOR')
        self.UIObject['tree'].column('NAME', width = 150 - 18)
        self.UIObject['tree'].column('VERSION', width = 100)
        self.UIObject['tree'].column('AUTHOR', width = 95)
        self.UIObject['tree'].heading('NAME', text = '插件')
        self.UIObject['tree'].heading('VERSION', text = '版本')
        self.UIObject['tree'].heading('AUTHOR', text = '作者')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff = False)
        self.UIObject['tree'].bind('<<TreeviewSelect>>', lambda x : self.treeSelect('tree', x))
        self.tree_load()
        self.UIObject['tree'].place(x = 15, y = 15, width = 350 - 18 , height = 370)

    def tree_load(self):
        tmp_tree_item_children = self.UIObject['tree'].get_children()
        for tmp_tree_item_this in tmp_tree_item_children:
            self.UIObject['tree'].delete(tmp_tree_item_this)
        if self.root != None:
            if self.root.UIData['shallow_plugin_data_dict'] != None:
                tmp_plugin_menu_dict = self.root.UIData['shallow_plugin_data_dict']
                for plugin_namespace in tmp_plugin_menu_dict:
                    plugin_this = tmp_plugin_menu_dict[plugin_namespace]
                    self.UIObject['tree'].insert(
                        '',
                        tkinter.END,
                        text = plugin_namespace,
                        values=(
                            plugin_this[0],
                            plugin_this[1],
                            plugin_this[2]
                        )
                    )

    def tree_UI_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['root'],
            text = text,
            command = command,
            bd = 0,
            activebackground = self.UIConfig['color_002'],
            activeforeground = self.UIConfig['color_001'],
            bg = self.UIConfig['color_003'],
            fg = self.UIConfig['color_004'],
            relief = 'groove'
        )
        self.UIObject[name].bind('<Enter>', lambda x : self.buttom_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda x : self.buttom_action(name, '<Leave>'))
        self.UIObject[name].bind('<Button-1>', lambda x : self.clickRecord(name, x))
        self.UIObject[name].place(
            x = x,
            y = y,
            width = width,
            height = height
        )

    def tree_UI_Label_init(self, name, title, x, y, width, height):
        self.UIData[title] = tkinter.StringVar()
        self.UIObject[name] = tkinter.Label(
            self.UIObject['root'],
            text = 'N/A',
            textvariable = self.UIData[title],
            wraplength = width - 4
        )
        self.UIObject[name].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004'],
            justify = 'left',
            anchor = 'nw'
        )
        self.UIObject[name].place(
            x = x,
            y = y,
            width = width,
            height = height
        )

    def sendPluginRestart(self):
        self.root.sendPluginRestart()

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg = self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg = self.UIConfig['color_003'])

    def treeSelect(self, name, event):
        if name == 'tree':
            tmp_info_str = '这个插件的作者很懒，没有写介绍。'
            plugin_namespace_now = get_tree_force(self.UIObject['tree'])['text']
            if plugin_namespace_now in self.root.UIData['shallow_plugin_data_dict']:
                plugin_menu_now = self.root.UIData['shallow_plugin_data_dict'][plugin_namespace_now]
                if type(plugin_menu_now[4]) == str:
                    if plugin_menu_now[4] != 'N/A':
                        tmp_info_str = plugin_menu_now[4]
            self.UIData['root_Label_INFO_StringVar'].set(tmp_info_str)

    def clickRecord(self, name, event):
        self.UIData['click_record'][name] = event

    def pluginMenu(self, name):
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        plugin_namespace_now = get_tree_force(self.UIObject['tree'])['text']
        if plugin_namespace_now in self.root.UIData['shallow_plugin_data_dict']:
            plugin_menu_now = self.root.UIData['shallow_plugin_data_dict'][plugin_namespace_now]
            if type(plugin_menu_now[3]) == list:
                for plugin_menu_this in plugin_menu_now[3]:
                    self.UIObject['tree_rightkey_menu'].add_command(label = plugin_menu_this[0],
                        command = self.root.sendPluginControlEventFunc(
                            plugin_menu_this[1],
                            plugin_menu_this[2]
                        )
                    )
            else:
                self.UIObject['tree_rightkey_menu'].add_command(label = '无选项', command = None)
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
        foreground = fixed_map('foreground', style),
        background = fixed_map('background', style)
    )
