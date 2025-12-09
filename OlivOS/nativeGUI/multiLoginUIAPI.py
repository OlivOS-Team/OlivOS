# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/multiLoginUIAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

import tkinter
import base64
import os
import hashlib
import random
import shutil
import platform
import traceback
import json
import copy

from tkinter import ttk
from tkinter import messagebox

import OlivOS

dictColorContext = {
    'color_001': '#00A0EA',
    'color_002': '#BBE9FF',
    'color_003': '#40C3FF',
    'color_004': '#FFFFFF',
    'color_005': '#000000',
    'color_006': '#80D7FF'
}

def run_HostUI_asayc(plugin_bot_info_dict, control_queue):
    if platform.system() == 'Windows':
        try:
            tmp_callbackData = {'res': False}
            tmp_t = OlivOS.multiLoginUIAPI.HostUI(
                Model_name='OlivOS_multiLoginUI_asayc',
                Account_data=plugin_bot_info_dict,
                logger_proc=None,
                callbackData=tmp_callbackData,
                asaycMode=True,
                rootMode=True,
                control_queue=control_queue
            )
            tmp_res = tmp_t.start()
            if tmp_res != True:
                pass
            if tmp_t.UIData['flag_commit']:
                pass
        except Exception as e:
            traceback.print_exc()

def sendAccountUpdate(obj, control_queue, account_data):
    if control_queue is not None:
        control_queue.put(
            OlivOS.API.Control.packet(
                'call_system_event',
                {
                    'action': [
                        'account_edit_asayc_end'
                    ]
                }
            ),
            block=False
        )
        control_queue.put(
            OlivOS.API.Control.packet(
                'call_account_update',
                {
                    'data': account_data
                }
            ),
            block=False
        )
        control_queue.put(
            OlivOS.API.Control.packet(
                'call_system_stop_type_event',
                {
                    'action': [
                        'account_update'
                    ]
                }
            ),
            block=False
        )
        control_queue.put(
            OlivOS.API.Control.packet(
                'call_system_event',
                {
                    'action': [
                        'account_update'
                    ]
                }
            ),
            block=False
        )

class HostUI(object):
    def __init__(
        self,
        Model_name,
        Account_data,
        logger_proc=None,
        callbackData=None,
        asaycMode=False,
        rootMode=True,
        control_queue=None
    ):
        self.Model_name = Model_name
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.callbackData = callbackData
        self.asaycMode = asaycMode
        self.rootMode = rootMode
        self.control_queue = control_queue
        self.res = False
        self.UIData['Account_data'] = Account_data
        self.UIData['flag_commit'] = False
        self.UIConfig.update(dictColorContext)
        releaseBase64Data('./resource', 'tmp_favoricon.ico', OlivOS.data.favoricon)

    def log(self, log_level, log_message):
        if self.logger_proc is not None:
            self.logger_proc.log(log_level, log_message)

    def start(self):
        if self.rootMode:
            self.UIObject['root'] = tkinter.Tk()
        else:
            self.UIObject['root'] = tkinter.Toplevel()
        self.UIObject['root'].title('OlivOS 登录管理器 - %s' % OlivOS.infoAPI.OlivOS_Version_Title)
        self.UIObject['root'].geometry('518x400')
        self.UIObject['root'].resizable(
            width=False,
            height=False
        )
        self.UIObject['root'].configure(bg=self.UIConfig['color_001'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        #self.UIObject['tree']['columns'] = ('ID', 'PLATFORM', 'SDK', 'MODEL')
        self.UIObject['tree']['columns'] = ('ID', 'TYPE')
        self.UIObject['tree'].column('ID', width=200)
        self.UIObject['tree'].column('TYPE', width=200)
        #self.UIObject['tree'].column('PLATFORM', width=100)
        #self.UIObject['tree'].column('SDK', width=100)
        #self.UIObject['tree'].column('MODEL', width=100)
        self.UIObject['tree'].heading('ID', text='ID')
        self.UIObject['tree'].heading('TYPE', text='账号类型')
        #self.UIObject['tree'].heading('PLATFORM', text='PLATFORM')
        #self.UIObject['tree'].heading('SDK', text='SDK')
        #self.UIObject['tree'].heading('MODEL', text='MODEL')
        self.UIObject['tree']['selectmode'] = 'browse'
        # 这个加载流程现在需要后置
        # 因为它现在需要同时控制 self.UIObject['root_frame_first_root'] 这个遮罩层是否显示
        #self.tree_load()
        self.UIObject['tree'].place(x=0, y=0, width=500, height=350)
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff=False)
        self.UIObject['root'].bind('<Button-3>', lambda x: self.tree_rightKey(x))

        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient="vertical",
            command=self.UIObject['tree'].yview
        )
        self.UIObject['tree_yscroll'].place(
            x=500,
            y=0,
            width=18,
            height=350
        )
        self.UIObject['tree'].configure(
            yscrollcommand=self.UIObject['tree_yscroll'].set
        )

        self.tree_UI_Button_init(
            name='root_Button_NEW',
            text='新建',
            command=lambda: self.tree_edit('create'),
            x=10,
            y=358,
            width=117,
            height=34
        )

        self.tree_UI_Button_init(
            name='root_Button_EDIT',
            text='编辑',
            command=lambda: self.tree_edit('update'),
            x=137,
            y=358,
            width=117,
            height=34
        )

        self.tree_UI_Button_init(
            name='root_Button_DEL',
            text='删除',
            command=lambda: self.tree_edit('delete'),
            x=264,
            y=358,
            width=117,
            height=34
        )

        self.tree_UI_Button_init(
            name='root_Button_COMMIT',
            text='启动 OlivOS',
            command=lambda: self.account_data_commit(),
            x=391,
            y=358,
            width=117,
            height=34
        )

        # 无账号时的引导遮罩层
        self.UIObject['root_frame_first_root'] = tkinter.Frame(self.UIObject['root'])
        self.UIObject['root_frame_first_root'].configure(relief = tkinter.FLAT)
        self.UIObject['root_frame_first_root'].configure(bg = self.UIConfig['color_001'], borderwidth = 0)
        # 这个组件使用这两个方法进行显示和隐藏
        # 位置信息依赖此处的数据
        # 是否显示通常受到数据控制其是否显示
        # self.frame_show('root_frame_first_root')
        # self.frame_hide('root_frame_first_root')
        self.UIConfig['root_frame_first_root_place'] = {
            'x': 0,
            'y': 0,
            'width': 518,
            'height': 400
        }

        self.UIObject['root_frame_first_root_label_note_new'] = tkinter.Label(
            self.UIObject['root_frame_first_root'],
            text = '\n'.join(
                [
                    '欢迎使用 OlivOS',
                    '',
                    '你可以在这里创建你的第一个账号'
                ]
            )
        )
        self.UIObject['root_frame_first_root_label_note_new'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004'],
            font = ('等线', 16, 'bold')
        )
        self.UIObject['root_frame_first_root_label_note_new'].place(
            x=int(518/2 - 518/2),
            y=int(400/2/2 + 20 - 200/2),
            width=518,
            height=200
        )

        self.tree_UI_Button_init(
            name='root_frame_first_root_Button_FIRST_NEW',
            text='创建一个账号',
            command=lambda: self.tree_edit('create'),
            x=int(518/2 - 250/2),
            y=int(400/2 + 20 - 48/2),
            width=250,
            height=48,
            root='root_frame_first_root'
        )
        self.UIObject['root_frame_first_root_Button_FIRST_NEW'].configure(font='等线 16 bold')

        self.UIObject['root_frame_first_root_label_note_commit'] = tkinter.Label(
            self.UIObject['root_frame_first_root'],
            text = '\n'.join(
                [
                    '或者你也可以'
                ]
            )
        )
        self.UIObject['root_frame_first_root_label_note_commit'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004'],
            font = ('等线', 12, 'bold')
        )
        self.UIObject['root_frame_first_root_label_note_commit'].place(
            x=391 - 16 * 6 - 8,
            y=358,
            width=16 * 6,
            height=34
        )

        self.tree_UI_Button_init(
            name='root_frame_first_root_Button_FIRST_COMMIT',
            text='直接启动',
            command=lambda: self.frame_show('root_frame_skip_root'),
            x=391,
            y=358,
            width=117,
            height=34,
            root='root_frame_first_root'
        )

        # 确认真的要无账号启动时的引导遮罩层
        self.UIObject['root_frame_skip_root'] = tkinter.Frame(self.UIObject['root'])
        self.UIObject['root_frame_skip_root'].configure(relief = tkinter.FLAT)
        self.UIObject['root_frame_skip_root'].configure(bg = self.UIConfig['color_001'], borderwidth = 0)
        # 这个组件使用这两个方法进行显示和隐藏
        # 位置信息依赖此处的数据
        # 需要按钮流程控制其是否显示
        # self.frame_show('root_frame_skip_root')
        # self.frame_hide('root_frame_skip_root')
        self.UIConfig['root_frame_skip_root_place'] = {
            'x': 0,
            'y': 0,
            'width': 518,
            'height': 400
        }

        self.UIObject['root_frame_skip_root_label_note_commit'] = tkinter.Label(
            self.UIObject['root_frame_skip_root'],
            text = '\n'.join(
                [
                    'OlivOS 的大部分功能都是基于账号进行的',
                    '',
                    '无账号的确可以正常运行',
                    '但请确保你真的明白你要做什么',
                    '',
                    '你真的要这么做吗？'
                ]
            )
        )
        self.UIObject['root_frame_skip_root_label_note_commit'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004'],
            font = ('等线', 16, 'bold')
        )
        self.UIObject['root_frame_skip_root_label_note_commit'].place(
            x=int(518/2 - 518/2),
            y=int(400/2/2 - 200/2),
            width=518,
            height=200
        )

        self.tree_UI_Button_init(
            name='root_frame_skip_root_Button_FIRST_COMMIT',
            text='是的，我要直接启动',
            command=lambda: self.account_data_commit(),
            x=int(518/2 - 250/2),
            y=int(400/2 + 20 - 48/2),
            width=250,
            height=48,
            root='root_frame_skip_root'
        )
        self.UIObject['root_frame_skip_root_Button_FIRST_COMMIT'].configure(font='等线 16 bold')

        self.tree_UI_Button_init(
            name='root_frame_skip_root_Button_FIRST_COMMIT_BACK',
            text='我点错了，让我回去',
            command=lambda: self.frame_hide('root_frame_skip_root'),
            x=int(518/2 - 250/2),
            y=int(400/2 + 20 + 48 * 1 + 15 - 48/2),
            width=250,
            height=48,
            root='root_frame_skip_root'
        )
        self.UIObject['root_frame_skip_root_Button_FIRST_COMMIT_BACK'].configure(font='等线 16 bold')

        # 这个数据加载过程会在后续多次反复执行
        self.tree_load()

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')

        self.UIObject['root'].mainloop()

        return self.res

    def frame_show(self, name):
        if name in ['root_frame_first_root', 'root_frame_skip_root']:
            self.UIObject[name].place(**self.UIConfig[f'{name}_place'])

    def frame_hide(self, name):
        if name in ['root_frame_first_root', 'root_frame_skip_root']:
            self.UIObject[name].place_forget()

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def tree_UI_Button_init(self, name, text, command, x, y, width, height, root='root'):
        self.UIObject[name] = tkinter.Button(
            self.UIObject[root],
            text=text,
            command=command,
            bd=0,
            activebackground=self.UIConfig['color_002'],
            activeforeground=self.UIConfig['color_001'],
            bg=self.UIConfig['color_003'],
            fg=self.UIConfig['color_004'],
            relief='groove',
            font='等线 12 bold'
        )
        self.UIObject[name].bind('<Enter>', lambda x: self.buttom_action(name, '<Enter>'))
        self.UIObject[name].bind('<Leave>', lambda x: self.buttom_action(name, '<Leave>'))
        self.UIObject[name].place(
            x=x,
            y=y,
            width=width,
            height=height
        )

    def tree_rightKey(self, event):
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label='新建', command=lambda: self.tree_edit('create'))
        self.UIObject['tree_rightkey_menu'].add_command(label='编辑', command=lambda: self.tree_edit('update'))
        self.UIObject['tree_rightkey_menu'].add_command(label='删除', command=lambda: self.tree_edit('delete'))
        self.UIObject['tree_rightkey_menu'].add_command(label='确认', command=lambda: self.account_data_commit())
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def tree_load(self):
        tmp_tree_item_children = self.UIObject['tree'].get_children()
        for tmp_tree_item_this in tmp_tree_item_children:
            self.UIObject['tree'].delete(tmp_tree_item_this)
        for Account_hash_this in self.UIData['Account_data']:
            self.UIObject['tree'].insert(
                '',
                0,
                text=Account_hash_this,
                values=(
                    self.UIData['Account_data'][Account_hash_this].id,
                    self.get_account_data_type_name(Account_hash_this)
                    #self.UIData['Account_data'][Account_hash_this].platform['platform'],
                    #self.UIData['Account_data'][Account_hash_this].platform['sdk'],
                    #self.UIData['Account_data'][Account_hash_this].platform['model']
                )
            )
        if len(self.UIData['Account_data']) <= 0:
            self.frame_show('root_frame_first_root')
        else:
            self.frame_hide('root_frame_first_root')

    def tree_edit(self, action):
        hash_key_how = None
        if action == 'update' or action == 'delete':
            hash_key_how = get_tree_force(self.UIObject['tree'])['text']
            if hash_key_how == '':
                action = 'create'
        edit_action = TreeEditUI(
            action=action,
            Account_data=self.UIData['Account_data'],
            hash_key=hash_key_how,
            edit_commit_callback=self.tree_edit_commit
        )
        edit_action.start()

    def tree_edit_commit(self, Edit_res):
        [
            Edit_action,
            Edit_old_hash,
            Edit_new_info
        ] = Edit_res
        if Edit_action == 'update' or Edit_action == 'delete':
            if Edit_old_hash in self.UIData['Account_data']:
                self.UIData['Account_data'].pop(Edit_old_hash)
        if Edit_action == 'create' or Edit_action == 'update':
            self.UIData['Account_data'][Edit_new_info.hash] = Edit_new_info
        self.tree_load()

    def account_data_commit(self):
        self.UIData['flag_commit'] = True
        self.res = True
        if type(self.callbackData) == dict:
            self.callbackData['res'] = self.res
        sendAccountUpdate(self, self.control_queue, self.UIData['Account_data'])
        self.UIObject['root'].destroy()

    def get_account_data_type_name(self, hash_key):
        res = '自定义'
        list_data_check = [
            str(self.UIData['Account_data'][hash_key].platform['platform']),
            str(self.UIData['Account_data'][hash_key].platform['sdk']),
            str(self.UIData['Account_data'][hash_key].platform['model']),
            str(self.UIData['Account_data'][hash_key].post_info.auto),
            str(self.UIData['Account_data'][hash_key].post_info.type)
        ]
        for type_this in OlivOS.accountMetadataAPI.accountTypeList:
            flag_hit = True
            for list_data_check_i in range(len(list_data_check)):
                if list_data_check[list_data_check_i] \
                != OlivOS.accountMetadataAPI.accountTypeMappingList[type_this][list_data_check_i]:
                    flag_hit = False
                    break
            if flag_hit:
                break
        if flag_hit:
            res = type_this
        return res

class TreeEditUI(object):
    def __init__(self, action, Account_data, hash_key=None, edit_commit_callback=None):
        self.hash_key = hash_key
        self.action = action
        self.edit_commit_callback = edit_commit_callback
        self.UIObject = {}
        self.UIConfig = {}
        self.UIConfig.update(dictColorContext)
        self.UIData = {
            'Account_data': Account_data,
            'Edit_res': ['none', 'OLDHASH', None],
            'edit_root_Combobox_platform_StringVar': tkinter.StringVar(),
            'edit_root_Combobox_sdk_StringVar': tkinter.StringVar(),
            'edit_root_Combobox_model_StringVar': tkinter.StringVar(),
            'edit_root_Entry_ID_StringVar': tkinter.StringVar(),
            'edit_root_Entry_Password_StringVar': tkinter.StringVar(),
            'edit_root_Combobox_Server_auto_StringVar': tkinter.StringVar(),
            'edit_root_Combobox_Server_type_StringVar': tkinter.StringVar(),
            'edit_root_Entry_Server_host_StringVar': tkinter.StringVar(),
            'edit_root_Entry_Server_port_StringVar': tkinter.StringVar(),
            'edit_root_Entry_Server_access_token_StringVar': tkinter.StringVar(),
            'edit_root_Combobox_Account_type_StringVar': tkinter.StringVar(),
            'edit_root_Entry_Extend_StringVar': tkinter.StringVar(),
            'edit_root_Entry_Extend2_StringVar': tkinter.StringVar(),
            'edit_root_Combobox_qsign_protocal_StringVar': tkinter.StringVar(),
            'edit_root_Combobox_qsign_protocal_list': [
                'AstralQsign',
                '手动',
                '9.0.95',
                '9.0.56',
                '8.9.85',
                '8.9.83',
                '8.9.80',
                '8.9.73',
                '8.9.71',
                '8.9.70',
                '8.9.68',
                '8.9.63',
                '8.9.58',
            ],
            'edit_root_Combobox_qsign_protocal_list_exemod': [
                'AstralQsign'
            ],
            'edit_root_Entry_Extend_list': [
                'edit_root_Entry_Extend',
                'edit_root_Entry_Extend2'
            ],
            'edit_root_Entry_qsign_list': [],
            'edit_root_Entry_qsign_num': 1,
            'edit_root_Combobox_dict': {
                'type_list': OlivOS.accountMetadataAPI.accountTypeList,
                'type_note_list': {
                    'QQ/GoCq/安卓手表': '密码留空即尝试使用扫码登录',
                    'QQ/GoCq/旧': '密码留空即尝试使用扫码登录',
                    'QQ/Wq/安卓手表': '密码留空即尝试使用扫码登录',
                    'QQ/Wq/旧': '密码留空即尝试使用扫码登录',
                    '微信/ComWeChat': '启动后需要再运行特定版本微信',
                    'Hack.Chat': '密码可以留空',
                    'RED协议': 'HTTP可以不填，反正也没实现',
                    'QQ/OPQ/默认': '已弃用',
                    'QQ/OPQ/指定端口': '已弃用',
                    'QQ/OPQ/指定端口/旧': '已弃用',
                    'QQ/NapCat/默认': '需要已经安装不低于9.9.22版本QQ',
                    'QQ/NapCat/9.9.11': '需要已经安装不高于9.9.11版本QQ',
                    'QQ/NapCat/旧': '使用本方法需要已经安装较新版本QQ',
                    'QQ官方/公域/V2': '请确保已经添加IP白名单',
                    'QQ官方/公域/V2/纯频道': '请确保已经添加IP白名单',
                    'QQ官方/公域/V2/指定intents': '请确保已经添加IP白名单',
                    'QQ官方/私域/V2': '请确保已经添加IP白名单',
                    'QQ官方/私域/V2/指定intents': '请确保已经添加IP白名单'
                },
                'type_clear_note_list': {
                    'QQ/GoCq/默认': './conf/gocqhttp/{bothash}',
                    'QQ/GoCq/安卓手机': './conf/gocqhttp/{bothash}',
                    'QQ/GoCq/安卓平板': './conf/gocqhttp/{bothash}',
                    'QQ/GoCq/安卓手表': './conf/gocqhttp/{bothash}',
                    'QQ/GoCq/iPad': './conf/gocqhttp/{bothash}',
                    'QQ/GoCq/iMac': './conf/gocqhttp/{bothash}',
                    'QQ/GoCq/旧': './conf/gocqhttp/{bothash}',
                    'QQ/Wq/安卓手表': './conf/walleq/{bothash}',
                    'QQ/Wq/安卓手机': './conf/walleq/{bothash}',
                    'QQ/Wq/安卓平板': './conf/walleq/{bothash}',
                    'QQ/Wq/旧': './conf/walleq/{bothash}',
                    'QQ/OPQ/默认': './conf/OPQBot/{bothash}',
                    'QQ/OPQ/指定端口': './conf/OPQBot/{bothash}',
                    'QQ/OPQ/指定端口/旧': './conf/OPQBot/{bothash}',
                    'QQ/NapCat/默认': './conf/napcat/{bothash}',
                    'QQ/NapCat/9.9.11': './conf/napcat/{bothash}',
                    'QQ/NapCat/旧': './conf/napcat/{bothash}'
                },
                'type_extend_note_list': {
                    #'QQ/GoCq/默认': ['签名服务器', 'sign-server'],
                    #'QQ/GoCq/安卓手机': ['签名服务器', 'sign-server'],
                    #'QQ/GoCq/安卓平板': ['签名服务器', 'sign-server'],
                    #'QQ/GoCq/旧': ['签名服务器', 'sign-server']
                    'RED协议': ['HTTP地址'],
                    '钉钉': ["AppKey", "AppSecret"],
                    'Hack.Chat/私有': ["WS地址"]
                },
                'type_extends_name_note_list': {
                    #'QQ/GoCq/默认': ['签名服务器', 'KEY'],
                    #'QQ/GoCq/安卓手机': ['签名服务器', 'KEY'],
                    #'QQ/GoCq/安卓平板': ['签名服务器', 'KEY'],
                    #'QQ/GoCq/旧': ['签名服务器', 'KEY']
                    'RED协议': ['HTTP地址'],
                    '钉钉': ["AppKey", "AppSecret"],
                    'Hack.Chat/私有': ["WS地址"]
                },
                'type_extends_note_list': {
                    #'QQ/GoCq/默认': {'签名服务器': 'sign-server', 'KEY': 'key'},
                    #'QQ/GoCq/安卓手机': {'签名服务器': 'sign-server', 'KEY': 'key'},
                    #'QQ/GoCq/安卓平板': {'签名服务器': 'sign-server', 'KEY': 'key'},
                    #'QQ/GoCq/旧': {'签名服务器': 'sign-server', 'KEY': 'key'},
                    'RED协议': {'HTTP地址': 'http-path'},
                    '钉钉': {"AppKey": 'app_key', "AppSecret": "app_secret"},
                    'Hack.Chat/私有': {"WS地址": 'ws_path'}
                },
                'type_qsign_array_note_list': {
                    'QQ/GoCq/默认': {'地址': 'sign-server', 'KEY': 'key'},
                    'QQ/GoCq/安卓手机': {'地址': 'sign-server', 'KEY': 'key'},
                    'QQ/GoCq/安卓平板': {'地址': 'sign-server', 'KEY': 'key'},
                    'QQ/GoCq/旧': {'地址': 'sign-server', 'KEY': 'key'}
                },
                # 各类账号组合的匹配与注册表
                # 原本为合并格式，并在此处维护
                # type: [platform, sdk, model, server_auto, server_type, {data_dict}]
                # 现拆分为两个表，使用时合并，以便于维护
                # type: [platform, sdk, model, server_auto, server_type] + [{data_dict}]
                # 前半位于 OlivOS.accountMetadataAPI
                # 后半位于此处
                'type_mapping_list': {},
                'type_mapping_list_Entry_slot': {
                    'onebotV11/Http': {
                        '账号': 'edit_root_Entry_ID',
                        '地址': 'edit_root_Entry_Server_host',
                        '端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'onebotV11/Http/NapCat': {
                        '账号': 'edit_root_Entry_ID',
                        '地址': 'edit_root_Entry_Server_host',
                        '端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'onebotV11/Http/LLOneBot': {
                        '账号': 'edit_root_Entry_ID',
                        '地址': 'edit_root_Entry_Server_host',
                        '端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'onebotV11/Http/Lagrange': {
                        '账号': 'edit_root_Entry_ID',
                        '地址': 'edit_root_Entry_Server_host',
                        '端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'onebotV11/Http/Shamrock': {
                        '账号': 'edit_root_Entry_ID',
                        '地址': 'edit_root_Entry_Server_host',
                        '端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'onebotV11/Http/消息段': {
                        '账号': 'edit_root_Entry_ID',
                        '地址': 'edit_root_Entry_Server_host',
                        '端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'onebotV12/正向WS': {
                        '账号': 'edit_root_Entry_ID',
                        '地址': 'edit_root_Entry_Server_host',
                        '端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'RED协议': {
                        '账号': 'edit_root_Entry_ID',
                        'WS地址': 'edit_root_Entry_Server_host',
                        'WS端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'OPQBot/正向WS': {
                        'QQ号': 'edit_root_Entry_ID',
                        '服务地址': 'edit_root_Entry_Server_host',
                        '服务端口': 'edit_root_Entry_Server_port',
                    },
                    'QQ/OPQ/默认': {
                        'QQ号': 'edit_root_Entry_ID',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'QQ/OPQ/指定端口': {
                        'QQ号': 'edit_root_Entry_ID',
                        '服务端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'QQ/OPQ/指定端口/旧': {
                        'QQ号': 'edit_root_Entry_ID',
                        '服务端口': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                    },
                    'QQ/NapCat/默认': {
                        'QQ号': 'edit_root_Entry_ID',
                    },
                    'QQ/NapCat/9.9.11': {
                        'QQ号': 'edit_root_Entry_ID',
                    },
                    'QQ/NapCat/旧': {
                        'QQ号': 'edit_root_Entry_ID',
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                        '服务端口': 'edit_root_Entry_Server_port',
                    },
                    'QQ/GoCq/默认': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/GoCq/安卓手机': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/GoCq/安卓平板': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/GoCq/安卓手表': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/GoCq/iPad': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/GoCq/iMac': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/GoCq/旧': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/Wq/默认': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/Wq/安卓手机': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/Wq/安卓平板': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/Wq/安卓手表': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/Wq/iPad': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/Wq/iMac': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    'QQ/Wq/旧': {
                        '账号': 'edit_root_Entry_ID',
                        '密码': 'edit_root_Entry_Password',
                    },
                    '微信/ComWeChat': {
                        '微信号': 'edit_root_Entry_ID'
                    },
                    'KOOK': {
                        'Token': 'edit_root_Entry_Server_access_token'
                    },
                    'KOOK/消息兼容': {
                        'Token': 'edit_root_Entry_Server_access_token'
                    },
                    '黑盒语音': {
                        '机器人ID': 'edit_root_Entry_ID',
                        '机器人令牌': 'edit_root_Entry_Server_access_token'
                    },
                    '米游社/大别野/公域': {
                        'Bot_Id': 'edit_root_Entry_ID',
                        'Secret': 'edit_root_Entry_Password',
                        'Pub_Key': 'edit_root_Entry_Server_access_token'
                    },
                    '米游社/大别野/私域': {
                        'Bot_Id': 'edit_root_Entry_ID',
                        'Secret': 'edit_root_Entry_Password',
                        'Pub_Key': 'edit_root_Entry_Server_access_token'
                    },
                    '米游社/大别野/沙盒': {
                        'Bot_Id': 'edit_root_Entry_ID',
                        'Secret': 'edit_root_Entry_Password',
                        'Pub_Key': 'edit_root_Entry_Server_access_token',
                        '别野号': 'edit_root_Entry_Server_port'
                    },
                    'B站直播间/游客': {
                        '直播间ID': 'edit_root_Entry_Server_access_token'
                    },
                    'B站直播间/登录': {
                        '直播间ID': 'edit_root_Entry_Server_access_token'
                    },
                    'QQ官方/公域/V1': {
                        'AppID': 'edit_root_Entry_ID',
                        '机器人令牌': 'edit_root_Entry_Server_access_token'
                    },
                    'QQ官方/私域/V1': {
                        'AppID': 'edit_root_Entry_ID',
                        '机器人令牌': 'edit_root_Entry_Server_access_token'
                    },
                    'QQ官方/公域/V2': {
                        'AppID': 'edit_root_Entry_ID',
                        'AppSecret': 'edit_root_Entry_Server_access_token'
                    },
                    'QQ官方/公域/V2/纯频道': {
                        'AppID': 'edit_root_Entry_ID',
                        'AppSecret': 'edit_root_Entry_Server_access_token'
                    },
                    'QQ官方/公域/V2/指定intents': {
                        'AppID': 'edit_root_Entry_ID',
                        'AppSecret': 'edit_root_Entry_Server_access_token',
                        'intents': 'edit_root_Entry_Server_port'
                    },
                    'QQ官方/私域/V2': {
                        'AppID': 'edit_root_Entry_ID',
                        'AppSecret': 'edit_root_Entry_Server_access_token'
                    },
                    'QQ官方/私域/V2/指定intents': {
                        'AppID': 'edit_root_Entry_ID',
                        'AppSecret': 'edit_root_Entry_Server_access_token',
                        'intents': 'edit_root_Entry_Server_port'
                    },
                    'QQ官方/沙盒/V2': {
                        'AppID': 'edit_root_Entry_ID',
                        'AppSecret': 'edit_root_Entry_Server_access_token'
                    },
                    'QQ官方/沙盒/V2/指定intents': {
                        'AppID': 'edit_root_Entry_ID',
                        'AppSecret': 'edit_root_Entry_Server_access_token',
                        'intents': 'edit_root_Entry_Server_port'
                    },
                    'Telegram': {
                        'TOKEN': 'edit_root_Entry_Server_access_token'
                    },
                    'Discord': {
                        'TOKEN': 'edit_root_Entry_Server_access_token'
                    },
                    'Discord/指定intents': {
                        'TOKEN': 'edit_root_Entry_Server_access_token',
                        'intents': 'edit_root_Entry_Server_port'
                    },
                    '渡渡语音/Dodo/V2': {
                        'BotID': 'edit_root_Entry_ID',
                        'Bot私钥': 'edit_root_Entry_Server_access_token'
                    },
                    '渡渡语音/Dodo/V1': {
                        'BotID': 'edit_root_Entry_ID',
                        'Bot私钥': 'edit_root_Entry_Server_access_token'
                    },
                    'Fanbook': {
                        'Token': 'edit_root_Entry_Server_access_token'
                    },
                    'Hack.Chat': {
                        '房间名称': 'edit_root_Entry_Server_host',
                        'Bot名称': 'edit_root_Entry_Server_access_token',
                        '密码': 'edit_root_Entry_Password'
                    },
                    'Hack.Chat/私有': {
                        '房间名称': 'edit_root_Entry_Server_host',
                        'Bot名称': 'edit_root_Entry_Server_access_token',
                        '密码': 'edit_root_Entry_Password'
                    },
                    '虚拟终端': {
                        '账号': 'edit_root_Entry_ID'
                    },
                    '接口终端': {
                        '账号': 'edit_root_Entry_ID',
                        '端口': 'edit_root_Entry_Server_port'
                    },
                    'FF14终端': {
                        '账号': 'edit_root_Entry_ID',
                        '端口': 'edit_root_Entry_Server_port',
                        '回调端口': 'edit_root_Entry_Server_access_token'
                    },
                    "钉钉": {
                        "Robot Code": 'edit_root_Entry_ID'
                    },
                    '自定义': {
                        'ID': 'edit_root_Entry_ID',
                        'PASSWORD': 'edit_root_Entry_Password',
                        'HOST': 'edit_root_Entry_Server_host',
                        'PORT': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token'
                    },
                },
                'platform_list': OlivOS.accountMetadataAPI.accountTypeDataList_platform,
                'platform_sdk_list': OlivOS.accountMetadataAPI.accountTypeDataList_platform_sdk,
                'platform_sdk_model_list': OlivOS.accountMetadataAPI.accountTypeDataList_platform_sdk_model,
            },
            'edit_root_Combobox_Server_auto_list': OlivOS.accountMetadataAPI.accountTypeDataList_server_auto,
            'edit_root_Combobox_Server_type_list': OlivOS.accountMetadataAPI.accountTypeDataList_server_type
        }
        # 此处进行type_mapping_list的拼合
        tmp_type_mapping_list = {}
        for key_this in OlivOS.accountMetadataAPI.accountTypeMappingList:
            tmp_mapping_slot = copy.deepcopy(OlivOS.accountMetadataAPI.accountTypeMappingList[key_this])
            tmp_Entry_slot = None
            if key_this in self.UIData['edit_root_Combobox_dict']['type_mapping_list_Entry_slot']:
                tmp_Entry_slot = self.UIData['edit_root_Combobox_dict']['type_mapping_list_Entry_slot'][key_this]
            else:
                tmp_Entry_slot = {}
            tmp_mapping_slot.append(copy.deepcopy(tmp_Entry_slot))
            tmp_type_mapping_list[key_this] = tmp_mapping_slot
        self.UIData['edit_root_Combobox_dict']['type_mapping_list'] = tmp_type_mapping_list

    def tree_edit_commit(self):
        miss_key_list = None
        if self.action == 'create' or self.action == 'update':
            if self.action == 'create':
                tmp_action = 'create'
            elif self.action == 'update':
                tmp_action = 'update'
            tmp_id = self.UIData['edit_root_Entry_ID_StringVar'].get()
            tmp_password = self.UIData['edit_root_Entry_Password_StringVar'].get()
            tmp_server_auto = self.UIData['edit_root_Combobox_Server_auto_StringVar'].get()
            tmp_server_type = self.UIData['edit_root_Combobox_Server_type_StringVar'].get()
            tmp_host = self.UIData['edit_root_Entry_Server_host_StringVar'].get()
            tmp_port = self.UIData['edit_root_Entry_Server_port_StringVar'].get()
            tmp_access_token = self.UIData['edit_root_Entry_Server_access_token_StringVar'].get()
            tmp_platform_sdk = self.UIData['edit_root_Combobox_sdk_StringVar'].get()
            tmp_platform_platform = self.UIData['edit_root_Combobox_platform_StringVar'].get()
            tmp_platform_model = self.UIData['edit_root_Combobox_model_StringVar'].get()
            tmp_extend = self.UIData['edit_root_Entry_Extend_StringVar'].get()
            tmp_extends = [self.UIData[edit_root_Entry_Extend_this + '_StringVar'].get() for edit_root_Entry_Extend_this in self.UIData['edit_root_Entry_Extend_list']]
            if tmp_platform_platform == 'qq' \
            and tmp_platform_sdk == 'onebot' \
            and tmp_platform_model in OlivOS.flaskServerAPI.gCheckList \
            and tmp_server_auto == 'True':
                if tmp_host == '':
                    tmp_host = 'http://127.0.0.1'
                if tmp_port == '':
                    tmp_port = '58000'
                if tmp_access_token == '':
                    tmp_access_token = 'NONEED'
            if tmp_platform_platform in ['qq', 'wechat'] \
            and tmp_platform_sdk == 'onebot' \
            and tmp_platform_model in OlivOS.onebotV12LinkServerAPI.gCheckList \
            and tmp_server_auto == 'True':
                if tmp_host == '':
                    tmp_host = 'ws://127.0.0.1'
                if tmp_port == '':
                    tmp_port = '58001'
                if tmp_access_token == '':
                    tmp_access_token = 'NONEED'
            if tmp_platform_platform == 'qq' \
            and tmp_platform_sdk == 'onebot' \
            and tmp_platform_model in OlivOS.OPQBotLinkServerAPI.gCheckList \
            and tmp_server_auto == 'False':
                if tmp_host == '':
                    tmp_host = '127.0.0.1'
                if tmp_access_token == '':
                    tmp_access_token = 'NONEED'
            if tmp_platform_platform == 'qq' \
            and tmp_platform_sdk == 'onebot' \
            and tmp_platform_model in OlivOS.OPQBotLinkServerAPI.gCheckList \
            and tmp_server_auto == 'True':
                if tmp_host == '':
                    tmp_host = '127.0.0.1'
                if tmp_platform_model in [
                    'opqbot_auto'
                ]:
                    if tmp_port == '':
                        tmp_port = '8086'
            if tmp_platform_platform == 'qqGuild' \
            and tmp_platform_sdk == 'qqGuild_link':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'qqGuild' \
            and tmp_platform_sdk == 'qqGuildv2_link':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_platform_model not in [
                    'public_intents',
                    'private_intents',
                    'sandbox_intents'
                ]:
                    if tmp_port == '':
                        tmp_port = '0'
            if tmp_platform_platform == 'mhyVila' \
            and tmp_platform_sdk == 'mhyVila_link':
                tmp_id = tmp_id.strip('\n')
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
                if tmp_platform_model in ['public', 'private']:
                    tmp_port = '0'
                try:
                    tmp_access_token_new = json.loads(tmp_access_token)
                    if type(tmp_access_token_new) is str:
                        tmp_access_token = tmp_access_token_new
                except Exception as e:
                    pass
                    #traceback.print_exc()
            if tmp_platform_platform == 'telegram' \
            and tmp_platform_sdk == 'telegram_poll':
                if tmp_id == '':
                    if len(tmp_access_token.split('.')) > 0:
                        tmp_id = tmp_access_token.split('.')[0]
                    if len(tmp_id) <= 0 or not tmp_id.isdigit():
                        tmp_id = int(getHash(tmp_access_token), 16)
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'https://api.telegram.org'
                if tmp_port == '':
                    tmp_port = '443'
            if tmp_platform_platform == 'discord' \
            and tmp_platform_sdk == 'discord_link':
                if tmp_id == '':
                    tmp_id = int(getHash(tmp_access_token), 16)
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_platform_model not in [
                    'intents'
                ]:
                    if tmp_port == '':
                        tmp_port = '0'
            if tmp_platform_platform == 'kaiheila' \
            and tmp_platform_sdk == 'kaiheila_link':
                if tmp_id == '':
                    tmp_id = int(getHash(tmp_access_token), 16)
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'xiaoheihe' \
            and tmp_platform_sdk == 'xiaoheihe_link':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'biliLive' \
            and tmp_platform_sdk == 'biliLive_link':
                if tmp_id == '':
                    tmp_id = int(getHash(tmp_access_token), 16) % 100000000000000
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'fanbook' \
            and tmp_platform_sdk == 'fanbook_poll':
                if tmp_id == '':
                    tmp_id = int(getHash(tmp_access_token), 16)
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'dodo' \
            and tmp_platform_sdk == 'dodo_poll':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'dodo' \
            and tmp_platform_sdk == 'dodo_link':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'terminal' \
            and tmp_platform_sdk == 'terminal_link' \
            and tmp_platform_model == 'default':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
                if tmp_access_token == '':
                    tmp_access_token = 'NONEED'
            if tmp_platform_platform == 'terminal' \
            and tmp_platform_sdk == 'terminal_link' \
            and tmp_platform_model == 'postapi':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_access_token == '':
                    tmp_access_token = 'NONEED'
            if tmp_platform_platform == 'terminal' \
            and tmp_platform_sdk == 'terminal_link' \
            and tmp_platform_model == 'ff14':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
            if tmp_platform_platform == 'hackChat' \
            and tmp_platform_sdk == 'hackChat_link' \
            and tmp_platform_model in ['default', 'private']:
                if tmp_id == '':
                    tmp_id = random.randint(1000000000, 9999999999)
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'dingtalk' \
            and tmp_platform_sdk == 'dingtalk_link' \
            and tmp_platform_model == 'default':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
                if tmp_access_token == '':
                    tmp_access_token = 'NONEED'
            if not checkByListEmptyOr([
                tmp_id,
                tmp_server_auto,
                tmp_server_type,
                tmp_host,
                tmp_port,
                tmp_access_token,
                tmp_platform_sdk,
                tmp_platform_platform,
                tmp_platform_model
            ]):
                tmp_id_last = str(tmp_id)
                try:
                    tmp_id_last = int(tmp_id)
                except:
                    pass
                tmp_res_bot_info = OlivOS.API.bot_info_T(
                    id=tmp_id_last,
                    password=tmp_password,
                    server_auto=str2bool(tmp_server_auto),
                    server_type=tmp_server_type,
                    host=tmp_host,
                    port=int(tmp_port),
                    access_token=tmp_access_token,
                    platform_sdk=tmp_platform_sdk,
                    platform_platform=tmp_platform_platform,
                    platform_model=tmp_platform_model
                )
                type_this = self.get_type_name(
                    tmp_platform_platform,
                    tmp_platform_sdk,
                    tmp_platform_model,
                    tmp_server_auto,
                    tmp_server_type
                )
                if type_this is not None \
                and type_this in self.UIData['edit_root_Combobox_dict']['type_extends_note_list'] \
                and type_this in self.UIData['edit_root_Combobox_dict']['type_extends_name_note_list'] \
                and dict is type(self.UIData['edit_root_Combobox_dict']['type_extends_note_list'][type_this]) \
                and list is type(self.UIData['edit_root_Combobox_dict']['type_extends_name_note_list'][type_this]):
                    tmp_offset = 0
                    for tmp_Entry_this in self.UIData['edit_root_Combobox_dict']['type_extends_name_note_list'][type_this]:
                        if tmp_offset >= len(tmp_extends):
                            break
                        tmp_res_bot_info.extends[self.UIData['edit_root_Combobox_dict']['type_extends_note_list'][type_this][tmp_Entry_this]] = tmp_extends[tmp_offset]
                        tmp_offset += 1
                if type_this is not None \
                and type_this in self.UIData['edit_root_Combobox_dict']['type_qsign_array_note_list']:
                    tmp_res_bot_info.extends['qsign-server-protocal'] = self.UIData['edit_root_Combobox_qsign_protocal_StringVar'].get()
                    tmp_res_bot_info.extends['qsign-server'] = []
                    for tmp_i in range(self.UIData['edit_root_Entry_qsign_num']):
                        key_pare = [
                            'edit_root_Entry_qsign_addr_%d' % tmp_i,
                            'edit_root_Entry_qsign_key_%d' % tmp_i
                        ]
                        tmp_data = {}
                        tmp_data['addr'] = ''
                        tmp_data['key'] = ''
                        if key_pare[0] + '_StringVar' in self.UIData:
                            tmp_data['addr'] = self.UIData[key_pare[0] + '_StringVar'].get()
                        if key_pare[1] + '_StringVar' in self.UIData:
                            tmp_data['key'] = self.UIData[key_pare[1] + '_StringVar'].get()
                        if len(tmp_data['addr']) > 0 \
                        or len(tmp_data['key']) > 0:
                            tmp_res_bot_info.extends['qsign-server'].append(tmp_data)
                self.UIData['Edit_res'] = [
                    tmp_action,
                    self.hash_key,
                    tmp_res_bot_info
                ]
            else:
                miss_key_list = []
                tmp_check_list = [
                    ['ID', tmp_id],
                    ['SDK', tmp_platform_sdk],
                    ['PLATFORM', tmp_platform_platform],
                    ['MODEL', tmp_platform_model],
                    ['AUTO', tmp_server_auto],
                    ['TYPE', tmp_server_type],
                    ['HOST', tmp_host],
                    ['PORT', tmp_port],
                    ['TOKEN', tmp_access_token]
                ]
                for tmp_check_list_this in tmp_check_list:
                    if tmp_check_list_this[1] == '':
                        miss_key_list.append(tmp_check_list_this[0])
        elif self.action == 'delete':
            self.UIData['Edit_res'] = [
                'delete',
                self.hash_key,
                None
            ]
        self.edit_commit_callback(self.UIData['Edit_res'])
        if self.action == 'create' or self.action == 'update':
            if miss_key_list is not None:
                if type(miss_key_list) == list:
                    # tmp_messagebox_str = 'Value Not Fount!\nPlease Complete Follow Item:\n-----------------\n%s' % '\n'.join(miss_key_list)
                    tmp_messagebox_str = '发现未填写条目！请确认完成填写。'
                    messagebox.showwarning('警告', tmp_messagebox_str)
            else:
                self.UIObject['edit_root'].destroy()

    def start(self):
        if self.action == 'create' or self.action == 'update':
            self.tree_edit_UI()
        elif self.action == 'delete':
            self.tree_edit_commit()

    def tree_edit_UI(self):
        self.UIObject['edit_root'] = tkinter.Toplevel()
        self.UIObject['edit_root'].title('OlivOS 账号编辑器')
        self.UIObject['edit_root'].geometry('400x370')
        self.UIObject['edit_root'].resizable(
            width=False,
            height=False
        )
        self.UIObject['edit_root'].configure(bg=self.UIConfig['color_001'])

        self.tree_UI_Button_init(
            name='edit_root_Button_commit',
            text='保存',
            command=self.tree_edit_commit,
            x=310,
            y=40,
            width=70,
            height=54
        )

        self.tree_edit_UI_Combobox_init(
            obj_root='edit_root',
            obj_name='edit_root_Combobox_Account_type',
            str_name='edit_root_Combobox_Account_type_StringVar',
            x=100,
            y=40,
            width=200,
            height=24,
            action=self.action,
            title='账号类型'
        )

        self.tree_edit_UI_Entry_update(self.action, 'init')
        self.tree_edit_UI_Combobox_update(self.action, 'init')

        self.UIObject['edit_root'].iconbitmap('./resource/tmp_favoricon.ico')

        self.UIObject['edit_root'].mainloop()

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg=self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg=self.UIConfig['color_003'])

    def tree_UI_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['edit_root'],
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

    def tree_edit_UI_Label_init(self, obj_root, obj_name, x, y, width, height, title=''):
        self.UIObject[obj_name] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        self.UIObject[obj_name].place(
            x=x,
            y=y,
            width=width,
            height=height
        )

    def tree_edit_UI_Entry_init(self, obj_root, obj_name, str_name, x, y, width, height, action, title='', mode='NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        self.UIObject[obj_name + '=Label'].place(
            x=x - 100,
            y=y,
            width=100,
            height=height
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
        if mode == 'SAFE':
            self.UIObject[obj_name].configure(
                show='●'
            )
        self.UIObject[obj_name].place(
            x=x,
            y=y,
            width=width,
            height=height
        )

    def tree_edit_UI_Combobox_init(self, obj_root, obj_name, str_name, x, y, width, height, action, title=''):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text=title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg=self.UIConfig['color_001'],
            fg=self.UIConfig['color_004']
        )
        self.UIObject[obj_name + '=Label'].place(
            x=x - 100,
            y=y,
            width=100,
            height=height
        )
        self.UIObject[obj_name] = ttk.Combobox(
            self.UIObject[obj_root],
            textvariable=self.UIData[str_name]
        )
        self.UIObject[obj_name].place(
            x=x,
            y=y,
            width=width,
            height=height
        )
        self.UIObject[obj_name].configure(state='readonly')
        self.UIObject[obj_name].bind(
            '<<ComboboxSelected>>',
            lambda x: self.tree_edit_UI_Combobox_ComboboxSelected(x, action, obj_name)
        )

    def tree_edit_UI_Combobox_ComboboxSelected(self, event, action, target):
        if target == 'edit_root_Combobox_Account_type':
            self.tree_edit_UI_Combobox_update(action, 'type')
        elif target == 'edit_root_Combobox_platform':
            self.tree_edit_UI_Combobox_update(action, 'platform')
        elif target == 'edit_root_Combobox_sdk':
            self.tree_edit_UI_Combobox_update(action, 'sdk')
        elif target == 'edit_root_Combobox_model':
            self.tree_edit_UI_Combobox_update(action, 'model')
        elif target == 'edit_root_Combobox_qsign_protocal':
            self.tree_edit_UI_Combobox_update(action, 'qsign_protocal')

    def tree_edit_UI_type_clear_note_GEN(self, tmp_type:str):
        def tree_edit_UI_type_clear_note():
            if tmp_type in self.UIData['edit_root_Combobox_dict']['type_clear_note_list']:
                valDict = {
                    'bothash': self.hash_key
                }
                dirPath = self.UIData['edit_root_Combobox_dict']['type_clear_note_list'][tmp_type].format(**valDict)
                removeDir(dirPath)
        return tree_edit_UI_type_clear_note

    def tree_edit_UI_qsign_list_set_GEN(self, tmp_type:str):
        def tree_edit_UI_qsign_list_set():
            if '+' == tmp_type:
                self.UIData['edit_root_Entry_qsign_num'] += 1
            elif '-' == tmp_type:
                self.UIData['edit_root_Entry_qsign_num'] -= 1
            if self.UIData['edit_root_Entry_qsign_num'] <= 0:
                self.UIData['edit_root_Entry_qsign_num'] = 1
            if self.UIData['edit_root_Entry_qsign_num'] > 10:
                self.UIData['edit_root_Entry_qsign_num'] = 10
            self.tree_edit_UI_Combobox_update(self.action, 'qsign_protocal')
        return tree_edit_UI_qsign_list_set

    def tree_edit_UI_Combobox_update(self, action, con_action):
        for item_this in [
            'edit_root_Entry_ID',
            'edit_root_Entry_Password',
            'edit_root_Entry_Server_host',
            'edit_root_Entry_Server_port',
            'edit_root_Entry_Server_access_token',
            'edit_root_Combobox_platform',
            'edit_root_Combobox_sdk',
            'edit_root_Combobox_model',
            'edit_root_Combobox_Server_auto',
            'edit_root_Combobox_Server_type',
            'edit_root_Label_type_note',
            'edit_root_Button_type_clear_note',
            'edit_root_Entry_Extend',
            'edit_root_Entry_Extend2',
            'edit_root_Combobox_qsign_protocal',
            'edit_root_Label_qsign_note',
            'edit_root_Button_qsign_list_set_+',
            'edit_root_Button_qsign_list_set_-'
        ] + self.UIData['edit_root_Entry_qsign_list']:
            try:
                self.UIObject[item_this].place_forget()
            except:
                pass
            try:
                self.UIObject[item_this + '=Label'].place_forget()
            except:
                pass
        tmp_list_type = self.UIData['edit_root_Combobox_dict']['type_list']
        if con_action == 'init':
            self.UIObject['edit_root_Combobox_Account_type']['value'] = tuple(tmp_list_type)
            if action == 'create':
                self.UIObject['edit_root_Combobox_Account_type'].current(0)
            if action == 'update':
                if self.hash_key in self.UIData['Account_data']:
                    Account_data_this:OlivOS.API.bot_info_T = self.UIData['Account_data'][self.hash_key]
                tmp_list_match_old = self.UIData['edit_root_Combobox_dict']['type_mapping_list']
                tmp_list_match = {}
                tmp_list_data = [
                    Account_data_this.platform['platform'],
                    Account_data_this.platform['sdk'],
                    Account_data_this.platform['model'],
                    Account_data_this.post_info.auto,
                    Account_data_this.post_info.type
                ]
                for index in [0, 1, 2, 3, 4]:
                    tmp_list_match = {}
                    for tmp_list_match_old_this in tmp_list_match_old:
                        if tmp_list_match_old_this != '自定义' \
                        and str(tmp_list_data[index]) == str(tmp_list_match_old[tmp_list_match_old_this][index]):
                            tmp_list_match[tmp_list_match_old_this] = tmp_list_match_old[tmp_list_match_old_this]
                    tmp_list_match_old = tmp_list_match
                if len(tmp_list_match) > 0:
                    tmp_data_match = None
                    for tmp_list_match_this in tmp_list_match:
                        tmp_data_match = tmp_list_match_this
                        break
                    self.UIObject['edit_root_Combobox_Account_type'].current(
                        self.UIData['edit_root_Combobox_dict']['type_list'].index(tmp_data_match)
                    )
                else:
                    self.UIObject['edit_root_Combobox_Account_type'].current(
                        self.UIData['edit_root_Combobox_dict']['type_list'].index('自定义')
                    )
        tmp_type = self.UIObject['edit_root_Combobox_Account_type'].get()
        if con_action in ['init', 'type', 'platform', 'sdk', 'model', 'qsign_protocal']:
            if tmp_type in self.UIData['edit_root_Combobox_dict']['type_mapping_list']:
                count = 1
                if tmp_type != '自定义':
                    self.UIData['edit_root_Combobox_platform_StringVar'].set(
                        self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][0])
                    self.UIData['edit_root_Combobox_sdk_StringVar'].set(
                        self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][1])
                    self.UIData['edit_root_Combobox_model_StringVar'].set(
                        self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][2])
                    self.UIData['edit_root_Combobox_Server_auto_StringVar'].set(
                        self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][3])
                    self.UIData['edit_root_Combobox_Server_type_StringVar'].set(
                        self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][4])
                else:
                    for entry_this in [
                        ['PLATFORM', 'edit_root_Combobox_platform'],
                        ['SDK', 'edit_root_Combobox_sdk'],
                        ['MODEL', 'edit_root_Combobox_model'],
                        ['AUTO', 'edit_root_Combobox_Server_auto'],
                        ['TYPE', 'edit_root_Combobox_Server_type']
                    ]:
                        self.tree_edit_UI_Combobox_init(
                            obj_root='edit_root',
                            obj_name=entry_this[1],
                            str_name=entry_this[1] + '_StringVar',
                            x=100,
                            y=40 + count * (24 + 6),
                            width=200,
                            height=24,
                            action=self.action,
                            title=entry_this[0]
                        )
                        count += 1
                for entry_this in self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][5]:
                    tmp_mode = 'NONE'
                    if self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][5][
                        entry_this] == 'edit_root_Entry_Password':
                        tmp_mode = 'SAFE'
                    self.tree_edit_UI_Entry_init(
                        obj_root='edit_root',
                        obj_name=self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][5][entry_this],
                        str_name=self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][5][
                                     entry_this] + '_StringVar',
                        x=100,
                        y=40 + count * (24 + 6),
                        width=200,
                        height=24,
                        action=self.action,
                        title=entry_this,
                        mode=tmp_mode
                    )
                    self.UIObject['edit_root'].geometry('400x%s' % (count * (24 + 6) + 100 + 10))
                    count += 1
                if tmp_type in self.UIData['edit_root_Combobox_dict']['type_extends_note_list'] \
                and tmp_type in self.UIData['edit_root_Combobox_dict']['type_extends_name_note_list'] \
                and dict is type(self.UIData['edit_root_Combobox_dict']['type_extends_note_list'][tmp_type])\
                and list is type(self.UIData['edit_root_Combobox_dict']['type_extends_name_note_list'][tmp_type]):
                    tmp_offset = 0
                    self.UIData['edit_root_Combobox_dict']['type_extends_note_list'][tmp_type]
                    for Entry_Extend_this in self.UIData['edit_root_Combobox_dict']['type_extends_name_note_list'][tmp_type]:
                        if Entry_Extend_this in self.UIData['edit_root_Combobox_dict']['type_extends_note_list'][tmp_type]:
                            if tmp_offset >= len(self.UIData['edit_root_Entry_Extend_list']):
                                break
                            self.tree_edit_UI_Entry_init(
                                obj_root='edit_root',
                                obj_name=self.UIData['edit_root_Entry_Extend_list'][tmp_offset],
                                str_name=self.UIData['edit_root_Entry_Extend_list'][tmp_offset] + '_StringVar',
                                x=100,
                                y=40 + count * (24 + 6),
                                width=200,
                                height=24,
                                action=self.action,
                                title=Entry_Extend_this,
                                mode='NONE'
                            )
                            self.UIObject['edit_root'].geometry('400x%s' % (count * (24 + 6) + 100 + 10))
                            count += 1
                            tmp_offset += 1
                if tmp_type in self.UIData['edit_root_Combobox_dict']['type_note_list']:
                    self.tree_edit_UI_Label_init(
                        obj_root='edit_root',
                        obj_name='edit_root_Label_type_note',
                        x=15,
                        y=40 + count * (24 + 6),
                        width=400 - 15 * 2,
                        height=24,
                        title=self.UIData['edit_root_Combobox_dict']['type_note_list'][tmp_type]
                    )
                    self.UIObject['edit_root'].geometry('400x%s' % (count * (24 + 6) + 100 + 10))
                    count += 1
                if tmp_type in self.UIData['edit_root_Combobox_dict']['type_clear_note_list']:
                    self.tree_UI_Button_init(
                        name='edit_root_Button_type_clear_note',
                        text='重置数据',
                        command=self.tree_edit_UI_type_clear_note_GEN(tmp_type),
                        x=310,
                        y=40 + 2 * (24 + 6),
                        width=70,
                        height=24
                    )
                    if count < 1:
                        count = 1
                        self.UIObject['edit_root'].geometry('400x%s' % (count * (24 + 6) + 100 + 10))
                        count += 1
                if tmp_type in self.UIData['edit_root_Combobox_dict']['type_qsign_array_note_list']:
                    self.tree_edit_UI_Label_init(
                        obj_root='edit_root',
                        obj_name='edit_root_Label_qsign_note',
                        x=100,
                        y=40 + count * (24 + 6),
                        width=200,
                        height=24,
                        title='Qsign 服务器设置'
                    )
                    count += 1
                    self.tree_edit_UI_Combobox_init(
                        obj_root='edit_root',
                        obj_name='edit_root_Combobox_qsign_protocal',
                        str_name='edit_root_Combobox_qsign_protocal_StringVar',
                        x=100,
                        y=40 + count * (24 + 6),
                        width=200,
                        height=24,
                        action=self.action,
                        title='协议版本'
                    )
                    self.UIObject['edit_root_Combobox_qsign_protocal']['value'] = tuple(
                        self.UIData['edit_root_Combobox_qsign_protocal_list']
                    )
                    tmp_qsign_protocal = self.UIData['edit_root_Combobox_qsign_protocal_StringVar'].get()
                    self.UIObject['edit_root_Combobox_qsign_protocal'].current(0)
                    if con_action == 'init':
                        if action == 'update':
                            if self.hash_key in self.UIData['Account_data']:
                                Account_data_this = self.UIData['Account_data'][self.hash_key]
                                if 'qsign-server-protocal' in Account_data_this.extends \
                                and type(Account_data_this.extends['qsign-server-protocal']) is str \
                                and Account_data_this.extends['qsign-server-protocal'] in self.UIData['edit_root_Combobox_qsign_protocal_list']:
                                    self.UIObject['edit_root_Combobox_qsign_protocal'].current(
                                        self.UIData['edit_root_Combobox_qsign_protocal_list'].index(
                                            Account_data_this.extends['qsign-server-protocal']
                                        )
                                    )
                    if con_action == 'qsign_protocal':
                        if action == 'update':
                            if tmp_qsign_protocal in self.UIData['edit_root_Combobox_qsign_protocal_list']:
                                self.UIObject['edit_root_Combobox_qsign_protocal'].current(
                                    self.UIData['edit_root_Combobox_qsign_protocal_list'].index(
                                        tmp_qsign_protocal
                                    )
                                )
                    tmp_qsign_protocal = self.UIData['edit_root_Combobox_qsign_protocal_StringVar'].get()
                    count += 1
                    if tmp_qsign_protocal in self.UIData['edit_root_Combobox_qsign_protocal_list_exemod']:
                        tmp_note_name = 'edit_root_Label_qsign_note_astalqsign_will_set'
                        if tmp_note_name not in self.UIData['edit_root_Entry_qsign_list']:
                            self.UIData['edit_root_Entry_qsign_list'].append(tmp_note_name)
                        self.tree_edit_UI_Label_init(
                            obj_root='edit_root',
                            obj_name=tmp_note_name,
                            x=15,
                            y=40 + count * (24 + 6),
                            width=400 - 15 * 2,
                            height=24,
                            title='OlivOS 将会同步为你自动配置本地 AstralQsign 服务'
                        )
                        count += 1
                    else:
                        self.tree_UI_Button_init(
                            name='edit_root_Button_qsign_list_set_+',
                            text='增加一行',
                            command=self.tree_edit_UI_qsign_list_set_GEN('+'),
                            x=310,
                            y=40 + 5 * (24 + 6),
                            width=70,
                            height=24
                        )
                        self.tree_UI_Button_init(
                            name='edit_root_Button_qsign_list_set_-',
                            text='减少一行',
                            command=self.tree_edit_UI_qsign_list_set_GEN('-'),
                            x=310,
                            y=40 + 6 * (24 + 6),
                            width=70,
                            height=24
                        )
                        array_num = self.UIData['edit_root_Entry_qsign_num']
                        for tmp_i in range(array_num):
                            key_pare = [
                                'edit_root_Entry_qsign_addr_%d' % tmp_i,
                                'edit_root_Entry_qsign_key_%d' % tmp_i
                            ]
                            if key_pare[0] not in self.UIData['edit_root_Entry_qsign_list']:
                                self.UIData['edit_root_Entry_qsign_list'].append(key_pare[0])
                            if key_pare[1] not in self.UIData['edit_root_Entry_qsign_list']:
                                self.UIData['edit_root_Entry_qsign_list'].append(key_pare[1])
                            if key_pare[0] + '_StringVar' not in self.UIData:
                                self.UIData[key_pare[0] + '_StringVar'] = tkinter.StringVar()
                            self.tree_edit_UI_Entry_init(
                                obj_root='edit_root',
                                obj_name=key_pare[0],
                                str_name=key_pare[0] + '_StringVar',
                                x=100,
                                y=40 + count * (24 + 6),
                                width=200,
                                height=24,
                                action=self.action,
                                title='地址',
                                mode='NONE'
                            )
                            count += 1
                            if key_pare[1] + '_StringVar' not in self.UIData:
                                self.UIData[key_pare[1] + '_StringVar'] = tkinter.StringVar()
                            self.tree_edit_UI_Entry_init(
                                obj_root='edit_root',
                                obj_name=key_pare[1],
                                str_name=key_pare[1] + '_StringVar',
                                x=100,
                                y=40 + count * (24 + 6),
                                width=200,
                                height=24,
                                action=self.action,
                                title='KEY',
                                mode='NONE'
                            )
                            count += 1
                    count -= 1
                    self.UIObject['edit_root'].geometry('400x%s' % (count * (24 + 6) + 100 + 10))
                    count += 1
        if tmp_type == '自定义':
            if action == 'update':
                if self.hash_key in self.UIData['Account_data']:
                    Account_data_this = self.UIData['Account_data'][self.hash_key]
            tmp_list_platform = self.UIData['edit_root_Combobox_dict']['platform_list']
            self.UIObject['edit_root_Combobox_platform']['value'] = tuple(tmp_list_platform)
            if con_action == 'init':
                self.UIObject['edit_root_Combobox_platform'].current(0)
                if action == 'update':
                    account_this_platform = Account_data_this.platform['platform']
                    if account_this_platform in tmp_list_platform:
                        self.UIData['edit_root_Combobox_platform_StringVar'].set(account_this_platform)

            tmp_list_sdk = self.UIData['edit_root_Combobox_dict']['platform_sdk_list'][
                self.UIData['edit_root_Combobox_platform_StringVar'].get()
            ]
            self.UIObject['edit_root_Combobox_sdk']['value'] = tuple(tmp_list_sdk)
            if con_action == 'init':
                self.UIObject['edit_root_Combobox_sdk'].current(0)
                if action == 'update':
                    account_this_sdk = Account_data_this.platform['sdk']
                    if account_this_sdk in tmp_list_sdk:
                        self.UIData['edit_root_Combobox_sdk_StringVar'].set(account_this_sdk)
            elif con_action == 'platform':
                self.UIObject['edit_root_Combobox_sdk'].current(0)

            tmp_list_model = self.UIData['edit_root_Combobox_dict']['platform_sdk_model_list'][
                self.UIData['edit_root_Combobox_platform_StringVar'].get()
            ][
                self.UIData['edit_root_Combobox_sdk_StringVar'].get()
            ]
            self.UIObject['edit_root_Combobox_model']['value'] = tuple(tmp_list_model)
            if con_action == 'init':
                self.UIObject['edit_root_Combobox_model'].current(0)
                if action == 'update':
                    account_this_model = Account_data_this.platform['model']
                    if account_this_model in tmp_list_model:
                        self.UIData['edit_root_Combobox_model_StringVar'].set(account_this_model)
            elif con_action == 'platform':
                self.UIObject['edit_root_Combobox_model'].current(0)
            elif con_action == 'sdk':
                self.UIObject['edit_root_Combobox_model'].current(0)
            tmp_list_server_auto = self.UIData['edit_root_Combobox_Server_auto_list']
            self.UIObject['edit_root_Combobox_Server_auto']['value'] = tuple(tmp_list_server_auto)
            tmp_list_server_type = self.UIData['edit_root_Combobox_Server_type_list']
            self.UIObject['edit_root_Combobox_Server_type']['value'] = tuple(tmp_list_server_type)
            if con_action == 'init':
                self.UIObject['edit_root_Combobox_Server_auto'].current(0)
                self.UIObject['edit_root_Combobox_Server_type'].current(0)
                if action == 'update':
                    account_this_server_auto = str(Account_data_this.post_info.auto)
                    account_this_server_type = Account_data_this.post_info.type
                    if account_this_server_auto in tmp_list_server_auto:
                        self.UIData['edit_root_Combobox_Server_auto_StringVar'].set(account_this_server_auto)
                    if account_this_server_type in tmp_list_server_type:
                        self.UIData['edit_root_Combobox_Server_type_StringVar'].set(account_this_server_type)

    def tree_edit_UI_Entry_update(self, action, con_action):
        if con_action == 'init':
            if action == 'update':
                if self.hash_key in self.UIData['Account_data']:
                    self.UIData['edit_root_Entry_ID_StringVar'].set(str(self.UIData['Account_data'][self.hash_key].id))
                    self.UIData['edit_root_Entry_Password_StringVar'].set(
                        self.UIData['Account_data'][self.hash_key].password)
                    self.UIData['edit_root_Entry_Server_host_StringVar'].set(
                        self.UIData['Account_data'][self.hash_key].post_info.host)
                    self.UIData['edit_root_Entry_Server_port_StringVar'].set(
                        str(self.UIData['Account_data'][self.hash_key].post_info.port))
                    self.UIData['edit_root_Entry_Server_access_token_StringVar'].set(
                        self.UIData['Account_data'][self.hash_key].post_info.access_token)
                    type_this = self.get_type_name(
                        str(self.UIData['Account_data'][self.hash_key].platform['platform']),
                        str(self.UIData['Account_data'][self.hash_key].platform['sdk']),
                        str(self.UIData['Account_data'][self.hash_key].platform['model']),
                        str(self.UIData['Account_data'][self.hash_key].post_info.auto),
                        str(self.UIData['Account_data'][self.hash_key].post_info.type)
                    )
                    if type_this is not None \
                    and type_this in self.UIData['edit_root_Combobox_dict']['type_extends_note_list'] \
                    and type_this in self.UIData['edit_root_Combobox_dict']['type_extends_name_note_list'] \
                    and dict is type(self.UIData['edit_root_Combobox_dict']['type_extends_note_list'][type_this]) \
                    and list is type(self.UIData['edit_root_Combobox_dict']['type_extends_name_note_list'][type_this]):
                        tmp_offset = 0
                        for tmp_Entry_this in self.UIData['edit_root_Combobox_dict']['type_extends_name_note_list'][type_this]:
                            if tmp_offset >= len(self.UIData['edit_root_Entry_Extend_list']):
                                break
                            if self.UIData['edit_root_Combobox_dict']['type_extends_note_list'][type_this][tmp_Entry_this] \
                            in self.UIData['Account_data'][self.hash_key].extends:
                                self.UIData[self.UIData['edit_root_Entry_Extend_list'][tmp_offset] + '_StringVar'].set(
                                    self.UIData['Account_data'][self.hash_key].extends[
                                        self.UIData['edit_root_Combobox_dict']['type_extends_note_list'][type_this][tmp_Entry_this]
                                    ]
                                )
                            else:
                                self.UIData[self.UIData['edit_root_Entry_Extend_list'][tmp_offset] + '_StringVar'].set('')
                            tmp_offset += 1
                    if type_this is not None \
                    and type_this in self.UIData['edit_root_Combobox_dict']['type_qsign_array_note_list']:
                        if 'qsign-server' in self.UIData['Account_data'][self.hash_key].extends \
                        and type(self.UIData['Account_data'][self.hash_key].extends['qsign-server']) is list:
                            tmp_i = 0
                            for tmp_data_this in self.UIData['Account_data'][self.hash_key].extends['qsign-server']:
                                key_pare = [
                                    'edit_root_Entry_qsign_addr_%d' % tmp_i,
                                    'edit_root_Entry_qsign_key_%d' % tmp_i
                                ]
                                if type(tmp_data_this) is dict \
                                and 'addr' in tmp_data_this \
                                and type(tmp_data_this['addr']) is str \
                                and 'key' in tmp_data_this \
                                and type(tmp_data_this['key']) is str:
                                    self.UIData[key_pare[0] + '_StringVar'] = tkinter.StringVar()
                                    self.UIData[key_pare[0] + '_StringVar'].set(tmp_data_this['addr'])
                                    self.UIData[key_pare[1] + '_StringVar'] = tkinter.StringVar()
                                    self.UIData[key_pare[1] + '_StringVar'].set(tmp_data_this['key'])
                                    tmp_i += 1
                                else:
                                    break
                            if tmp_i <= 0:
                                tmp_i = 1
                            if tmp_i > 10:
                                tmp_i = 10
                            self.UIData['edit_root_Entry_qsign_num'] = tmp_i



    def get_type_name(
        self,
        platform_platform,
        platform_sdk,
        platform_model,
        server_auto,
        server_type
    ):
        res = None
        list_data_check = [
            platform_platform,
            platform_sdk,
            platform_model,
            server_auto,
            server_type
        ]
        for type_this in self.UIData['edit_root_Combobox_dict']['type_list']:
            flag_hit = True
            for list_data_check_i in range(len(list_data_check)):
                if list_data_check[list_data_check_i] \
                != self.UIData['edit_root_Combobox_dict']['type_mapping_list'][type_this][list_data_check_i]:
                    flag_hit = False
                    break
            if flag_hit:
                break
        if flag_hit:
            res = type_this
        return res


def get_tree_force(tree_obj):
    return tree_obj.item(tree_obj.focus())


def str2bool(str):
    return True if str.lower() == 'true' else False


def checkByListEmptyOr(check_list):
    flag_res = False
    for check_list_this in check_list:
        if check_list_this == '':
            flag_res = True
            return flag_res
    return flag_res


def releaseBase64Data(dir_path, file_name, base64_data):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
    with open(dir_path + '/' + file_name, 'wb+') as tmp:
        tmp.write(base64.b64decode(base64_data))


def getHash(key):
    hash_tmp = hashlib.new('md5')
    hash_tmp.update(str(key).encode(encoding='UTF-8'))
    return hash_tmp.hexdigest()


def removeDir(dir_path):
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
    except:
        pass
