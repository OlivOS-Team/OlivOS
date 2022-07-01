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

from PIL import Image

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
        control_queue = None
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
        self.UIObject = {}
        self.UIData = {}
        self.UIObject['root_shallow'] = None
        self.UIObject['root_plugin_edit'] = {}
        self.UIObject['root_plugin_edit_enable'] = False
        self.UIObject['root_plugin_edit_count'] = 0
        self.UIData['shallow_plugin_menu_list'] = None
        self.UIData['shallow_plugin_data_dict'] = None
        self.updateShallowMenuList()

    def updateShallowMenuList(self):
        self.UIData['shallow_menu_list'] = [
            ['账号管理', False],
            ['插件管理', self.startPluginEdit],
            ['插件菜单', self.UIData['shallow_plugin_menu_list']],
            ['重载插件', self.sendPluginRestart],
            ['退出OlivOS', self.setOlivOSExit]
        ]

    def startPluginEdit(self):
        if not self.UIObject['root_plugin_edit_enable']:
            self.UIObject['root_plugin_edit_enable'] = True
            count_str = str(self.UIObject['root_plugin_edit_count'])
            self.UIObject['root_plugin_edit_count'] += 1
            self.UIObject['root_plugin_edit'][count_str] = {}
            self.UIObject['root_plugin_edit'][count_str]['obj'] = pluginManageUI(
                Model_name = 'shallow_menu_plugin_manage',
                logger_proc = self.Proc_info.logger_proc.log,
                root = self,
                key = count_str
            )
            self.UIObject['root_plugin_edit'][count_str]['treading'] = threading.Thread(
                target = self.UIObject['root_plugin_edit'][count_str]['obj'].start,
                args = ()
            )
            self.UIObject['root_plugin_edit'][count_str]['treading'].start()

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

    def run(self):
        while True:
            if self.Proc_info.rx_queue.empty() or self.Proc_config['ready_for_restart']:
                time.sleep(self.Proc_info.scan_interval)
            else:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block = False)
                except:
                    continue
                if rx_packet_data != None:
                    if type(rx_packet_data) == OlivOS.API.Control.packet:
                        if rx_packet_data.action == 'send':
                            if type(rx_packet_data.key) == dict:
                                if 'data' in rx_packet_data.key:
                                    if 'action' in rx_packet_data.key['data']:
                                        if rx_packet_data.key['data']['action'] == 'update_data':
                                            self.UIData.update(rx_packet_data.key['data']['data'])
                                            self.updateShallowMenuList()
                                        elif rx_packet_data.key['data']['action'] == 'start_shallow':
                                            if self.UIObject['root_shallow'] == None:
                                                self.startShallow()
                                            else:
                                                self.updateShallow()
                                                self.updatePluginEdit()

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
        self.UIObject['root'] = tkinter.Tk()
        self.UIObject['root'].title('OlivOS 插件管理器')
        self.UIObject['root'].geometry('518x400')
        self.UIObject['root'].resizable(
            width = False,
            height = False
        )
        self.UIObject['root'].configure(bg = self.UIConfig['color_001'])

        self.tree_init()

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

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')

        self.UIObject['root'].mainloop()

        self.root.UIObject['root_plugin_edit'].pop(self.key)
        self.root.UIObject['root_plugin_edit_enable'] = False

    def tree_init(self):
        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('NAME', 'VERSION', 'AUTHOR')
        self.UIObject['tree'].column('NAME', width = 150)
        self.UIObject['tree'].column('VERSION', width = 100)
        self.UIObject['tree'].column('AUTHOR', width = 95)
        self.UIObject['tree'].heading('NAME', text = '插件')
        self.UIObject['tree'].heading('VERSION', text = '版本')
        self.UIObject['tree'].heading('AUTHOR', text = '作者')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff = False)
        self.UIObject['tree'].bind('<<TreeviewSelect>>', lambda x : self.treeSelect('tree', x))
        self.tree_load()
        self.UIObject['tree'].place(x = 15, y = 15, width = 350 , height = 370)

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
                        0,
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
