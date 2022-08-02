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
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import tkinter
import base64
import os
import hashlib

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

class HostUI(object):
    def __init__(self, Model_name, Account_data, logger_proc = None):
        self.Model_name = Model_name
        self.UIObject = {}
        self.UIData = {}
        self.UIConfig = {}
        self.logger_proc = logger_proc
        self.UIData['Account_data'] = Account_data
        self.UIData['flag_commit'] = False
        self.UIConfig.update(dictColorContext)
        releaseBase64Data('./resource', 'tmp_favoricon.ico', OlivOS.data.favoricon)

    def log(self, log_level, log_message):
        if self.logger_proc != None:
            self.logger_proc.log(log_level, log_message)

    def start(self):
        self.UIObject['root'] = tkinter.Tk()
        self.UIObject['root'].title('OlivOS 登录管理器')
        self.UIObject['root'].geometry('518x400')
        self.UIObject['root'].resizable(
            width = False,
            height = False
        )
        self.UIObject['root'].configure(bg = self.UIConfig['color_001'])

        self.UIObject['tree'] = ttk.Treeview(self.UIObject['root'])
        self.UIObject['tree']['show'] = 'headings'
        self.UIObject['tree']['columns'] = ('ID', 'PLATFORM', 'SDK', 'MODEL')
        self.UIObject['tree'].column('ID', width = 100)
        self.UIObject['tree'].column('PLATFORM', width = 100)
        self.UIObject['tree'].column('SDK', width = 100)
        self.UIObject['tree'].column('MODEL', width = 100)
        self.UIObject['tree'].heading('ID', text = 'ID')
        self.UIObject['tree'].heading('PLATFORM', text = 'PLATFORM')
        self.UIObject['tree'].heading('SDK', text = 'SDK')
        self.UIObject['tree'].heading('MODEL', text = 'MODEL')
        self.UIObject['tree']['selectmode'] = 'browse'
        self.tree_load()
        self.UIObject['tree'].place(x = 0, y = 0, width = 500, height = 350)
        self.UIObject['tree_rightkey_menu'] = tkinter.Menu(self.UIObject['root'], tearoff = False)
        self.UIObject['root'].bind('<Button-3>', lambda x : self.tree_rightKey(x))

        self.UIObject['tree_yscroll'] = ttk.Scrollbar(
            self.UIObject['root'],
            orient = "vertical",
            command = self.UIObject['tree'].yview
        )
        self.UIObject['tree_yscroll'].place(
            x = 500,
            y = 0,
            width = 18,
            height = 350
        )
        self.UIObject['tree'].configure(
            yscrollcommand = self.UIObject['tree_yscroll'].set
        )

        self.tree_UI_Button_init(
            name = 'root_Button_NEW',
            text = '新建',
            command = lambda : self.tree_edit('create'),
            x = 10,
            y = 358,
            width = 117,
            height = 34
        )

        self.tree_UI_Button_init(
            name = 'root_Button_EDIT',
            text = '编辑',
            command = lambda : self.tree_edit('update'),
            x = 137,
            y = 358,
            width = 117,
            height = 34
        )

        self.tree_UI_Button_init(
            name = 'root_Button_DEL',
            text = '删除',
            command = lambda : self.tree_edit('delete'),
            x = 264,
            y = 358,
            width = 117,
            height = 34
        )

        self.tree_UI_Button_init(
            name = 'root_Button_COMMIT',
            text = '确认',
            command = lambda : self.account_data_commit(),
            x = 391,
            y = 358,
            width = 117,
            height = 34
        )

        self.UIObject['root'].iconbitmap('./resource/tmp_favoricon.ico')

        self.UIObject['root'].mainloop()

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg = self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg = self.UIConfig['color_003'])

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
        self.UIObject[name].place(
            x = x,
            y = y,
            width = width,
            height = height
        )

    def tree_rightKey(self, event):
        self.UIObject['tree_rightkey_menu'].delete(0, tkinter.END)
        self.UIObject['tree_rightkey_menu'].add_command(label = '新建', command = lambda : self.tree_edit('create'))
        self.UIObject['tree_rightkey_menu'].add_command(label = '编辑', command = lambda : self.tree_edit('update'))
        self.UIObject['tree_rightkey_menu'].add_command(label = '删除', command = lambda : self.tree_edit('delete'))
        self.UIObject['tree_rightkey_menu'].add_command(label = '确认', command = lambda : self.account_data_commit())
        self.UIObject['tree_rightkey_menu'].post(event.x_root, event.y_root)

    def tree_load(self):
        tmp_tree_item_children = self.UIObject['tree'].get_children()
        for tmp_tree_item_this in tmp_tree_item_children:
            self.UIObject['tree'].delete(tmp_tree_item_this)
        for Account_hash_this in self.UIData['Account_data']:
            self.UIObject['tree'].insert(
                '',
                0,
                text = Account_hash_this,
                values=(
                    self.UIData['Account_data'][Account_hash_this].id,
                    self.UIData['Account_data'][Account_hash_this].platform['platform'],
                    self.UIData['Account_data'][Account_hash_this].platform['sdk'],
                    self.UIData['Account_data'][Account_hash_this].platform['model']
                )
            )

    def tree_edit(self, action):
        hash_key_how = None
        if action == 'update' or action == 'delete':
            hash_key_how = get_tree_force(self.UIObject['tree'])['text']
            if hash_key_how == '':
                action = 'create'
        edit_action = TreeEditUI(
            action = action,
            Account_data = self.UIData['Account_data'],
            hash_key = hash_key_how,
            edit_commit_callback = self.tree_edit_commit
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
        self.UIObject['root'].destroy()

class TreeEditUI(object):
    def __init__(self, action, Account_data, hash_key = None, edit_commit_callback = None):
        self.hash_key = hash_key
        self.action = action
        self.edit_commit_callback = edit_commit_callback
        self.UIObject = {}
        self.UIConfig = {}
        self.UIConfig.update(dictColorContext)
        self.UIData = {}
        self.UIData['Account_data'] = Account_data
        self.UIData['Edit_res'] = [
            'none',
            'OLDHASH',
            None
        ]
        self.UIData['edit_root_Combobox_platform_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_sdk_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_model_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Entry_ID_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Entry_Password_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_Server_auto_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_Server_type_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Entry_Server_host_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Entry_Server_port_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Entry_Server_access_token_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_Account_type_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_dict'] = {
            'type_list': [
                '传统QQ',
                '传统QQ - 旧',
                '开黑啦 - KOOK',
                'QQ频道 - 公域',
                'QQ频道 - 私域',
                '渡渡语音 - Dodo',
                'Fanbook',
                'Telegram',
                '自定义'
            ],
            # 各类账号组合的匹配与注册表
            # type: [platform, sdk, model, server_auto, server_type, {data_dict}]
            'type_mapping_list': {
                '传统QQ': ['qq', 'onebot', 'gocqhttp_show', 'True', 'post', {
                        '账号': 'edit_root_Entry_ID'
                        #'密码': 'edit_root_Entry_Password',
                        #推荐使用扫码登录，所以隐藏密码栏
                    }
                ],
                '传统QQ - 旧': ['qq', 'onebot', 'gocqhttp_show_old', 'True', 'post', {
                        '账号': 'edit_root_Entry_ID'
                        #'密码': 'edit_root_Entry_Password',
                        #推荐使用扫码登录，所以隐藏密码栏
                    }
                ],
                '开黑啦 - KOOK': ['kaiheila', 'kaiheila_link', 'default', 'True', 'websocket', {
                        'Token': 'edit_root_Entry_Server_access_token'
                    }
                ],
                'QQ频道 - 公域': ['qqGuild', 'qqGuild_link', 'public', 'True', 'websocket', {
                        'BotAppID': 'edit_root_Entry_ID',
                        '机器人令牌': 'edit_root_Entry_Server_access_token'
                    }
                ],
                'QQ频道 - 私域': ['qqGuild', 'qqGuild_link', 'private', 'True', 'websocket', {
                        'BotAppID': 'edit_root_Entry_ID',
                        '机器人令牌': 'edit_root_Entry_Server_access_token'
                    }
                ],
                '渡渡语音 - Dodo': ['dodo', 'dodo_link', 'default', 'True', 'websocket', {
                        'BotID': 'edit_root_Entry_ID',
                        'Bot私钥': 'edit_root_Entry_Server_access_token'
                    }
                ],
                'Fanbook': ['fanbook', 'fanbook_poll', 'default', 'True', 'post', {
                        'Token': 'edit_root_Entry_Server_access_token'
                    }
                ],
                'Telegram': ['telegram', 'telegram_poll', 'default', 'True', 'post', {
                        'ID': 'edit_root_Entry_ID',
                        'HOST': 'edit_root_Entry_Server_host',
                        'PORT': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token'
                    }
                ],
                '自定义': ['qq', 'default', 'default', 'True', 'post', {
                        'ID': 'edit_root_Entry_ID',
                        'PASSWORD': 'edit_root_Entry_Password',
                        'HOST': 'edit_root_Entry_Server_host',
                        'PORT': 'edit_root_Entry_Server_port',
                        'TOKEN': 'edit_root_Entry_Server_access_token'
                    }
                ],
            },
            'platform_list': [
                'qq',
                'qqGuild',
                'kaiheila',
                'telegram',
                'dodo',
                'fanbook'
            ],
            'platform_sdk_list': {
                'qq': [
                    'onebot'
                ],
                'qqGuild': [
                    'qqGuild_link'
                ],
                'kaiheila': [
                    'kaiheila_link'
                ],
                'telegram': [
                    'telegram_poll'
                ],
                'dodo': [
                    'dodo_link'
                    #'dodo_poll',
                    #'dodobot_ea'
                ],
                'fanbook': [
                    'fanbook_poll'
                ]
            },
            'platform_sdk_model_list': {
                'qq': {
                    'onebot': [
                        #'gocqhttp',
                        #'gocqhttp_hide',
                        'gocqhttp_show',
                        'gocqhttp_show_old',
                        'default'
                    ]
                },
                'qqGuild': {
                    'qqGuild_link': [
                        'private',
                        'public',
                        'default'
                    ]
                },
                'kaiheila': {
                    'kaiheila_link': [
                        'default'
                    ]
                },
                'telegram': {
                    'telegram_poll': [
                        'default'
                    ]
                },
                'dodo': {
                    'dodo_link': [
                        'default'
                    ],
                    'dodo_poll': [
                        'default'
                    ],
                    'dodobot_ea': [
                        'default'
                    ]
                },
                'fanbook': {
                    'fanbook_poll': [
                        'default',
                        'private'
                    ]
                }
            }
        }

        self.UIData['edit_root_Combobox_Server_auto_list'] = [
            'True',
            'False'
        ]

        self.UIData['edit_root_Combobox_Server_type_list'] = [
            'post',
            'websocket'
        ]

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
            width = False,
            height = False
        )
        self.UIObject['edit_root'].configure(bg = self.UIConfig['color_001'])

        self.tree_UI_Button_init(
            name = 'edit_root_Button_commit',
            text = '保存',
            command = self.tree_edit_commit,
            x = 310,
            y = 40,
            width = 70,
            height = 54
        )

        self.tree_edit_UI_Combobox_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Combobox_Account_type',
            str_name = 'edit_root_Combobox_Account_type_StringVar',
            x = 100,
            y = 40,
            width = 200,
            height = 24,
            action = self.action,
            title = '账号类型'
        )

        self.tree_edit_UI_Entry_update(self.action, 'init')
        self.tree_edit_UI_Combobox_update(self.action, 'init')

        self.UIObject['edit_root'].iconbitmap('./resource/tmp_favoricon.ico')

        self.UIObject['edit_root'].mainloop()

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg = self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg = self.UIConfig['color_003'])

    def tree_UI_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['edit_root'],
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
        self.UIObject[name].place(
            x = x,
            y = y,
            width = width,
            height = height
        )

    def tree_edit_UI_Entry_init(self, obj_root, obj_name, str_name, x, y, width, height, action, title = '', mode = 'NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text = title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004']
        )
        self.UIObject[obj_name + '=Label'].place(
            x = x - 100,
            y = y,
            width = 100,
            height = height
        )
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
        self.UIObject[obj_name].place(
            x = x,
            y = y,
            width = width,
            height = height
        )

    def tree_edit_UI_Combobox_init(self, obj_root, obj_name, str_name, x, y, width, height, action, title = ''):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text = title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004']
        )
        self.UIObject[obj_name + '=Label'].place(
            x = x - 100,
            y = y,
            width = 100,
            height = height
        )
        self.UIObject[obj_name] = ttk.Combobox(
            self.UIObject[obj_root],
            textvariable = self.UIData[str_name]
        )
        self.UIObject[obj_name].place(
            x = x,
            y = y,
            width = width,
            height = height
        )
        self.UIObject[obj_name].configure(state='readonly')
        self.UIObject[obj_name].bind('<<ComboboxSelected>>', lambda x : self.tree_edit_UI_Combobox_ComboboxSelected(x, action, obj_name))

    def tree_edit_UI_Combobox_ComboboxSelected(self, action, event, target):
        if target == 'edit_root_Combobox_Account_type':
            self.tree_edit_UI_Combobox_update(action, 'type')
        elif target == 'edit_root_Combobox_platform':
            self.tree_edit_UI_Combobox_update(action, 'platform')
        elif target == 'edit_root_Combobox_sdk':
            self.tree_edit_UI_Combobox_update(action, 'sdk')
        elif target == 'edit_root_Combobox_model':
            self.tree_edit_UI_Combobox_update(action, 'model')

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
            'edit_root_Combobox_Server_type'
        ]:
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
                    Account_data_this = self.UIData['Account_data'][self.hash_key]
                tmp_list_match_old = self.UIData['edit_root_Combobox_dict']['type_mapping_list']
                tmp_list_match = {}
                tmp_list_data = [
                    Account_data_this.platform['platform'],
                    Account_data_this.platform['sdk'],
                    Account_data_this.platform['model']
                ]
                for index in [0, 1, 2]:
                    tmp_list_match = {}
                    for tmp_list_match_old_this in tmp_list_match_old:
                        if tmp_list_match_old_this != '自定义' and tmp_list_data[index] == tmp_list_match_old[tmp_list_match_old_this][index]:
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
        if con_action in ['init', 'type', 'platform', 'sdk', 'model']:
            if tmp_type in self.UIData['edit_root_Combobox_dict']['type_mapping_list']:
                count = 1
                if tmp_type != '自定义':
                    self.UIData['edit_root_Combobox_platform_StringVar'].set(self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][0])
                    self.UIData['edit_root_Combobox_sdk_StringVar'].set(self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][1])
                    self.UIData['edit_root_Combobox_model_StringVar'].set(self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][2])
                    self.UIData['edit_root_Combobox_Server_auto_StringVar'].set(self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][3])
                    self.UIData['edit_root_Combobox_Server_type_StringVar'].set(self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][4])
                else:
                    for entry_this in [
                        ['PLATFORM', 'edit_root_Combobox_platform'],
                        ['SDK', 'edit_root_Combobox_sdk'],
                        ['MODEL', 'edit_root_Combobox_model'],
                        ['AUTO', 'edit_root_Combobox_Server_auto'],
                        ['TYPE', 'edit_root_Combobox_Server_type']
                    ]:
                        self.tree_edit_UI_Combobox_init(
                            obj_root = 'edit_root',
                            obj_name = entry_this[1],
                            str_name = entry_this[1] + '_StringVar',
                            x = 100,
                            y = 40 + count * (24 + 6),
                            width = 200,
                            height = 24,
                            action = self.action,
                            title = entry_this[0]
                        )
                        count += 1
                for entry_this in self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][5]:
                    tmp_mode = 'NONE'
                    if self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][5][entry_this] == 'edit_root_Entry_Password':
                        tmp_mode = 'SAFE'
                    self.tree_edit_UI_Entry_init(
                        obj_root = 'edit_root',
                        obj_name = self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][5][entry_this],
                        str_name = self.UIData['edit_root_Combobox_dict']['type_mapping_list'][tmp_type][5][entry_this] + '_StringVar',
                        x = 100,
                        y = 40 + count * (24 + 6),
                        width = 200,
                        height = 24,
                        action = self.action,
                        title = entry_this,
                        mode = tmp_mode
                    )
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
                    self.UIData['edit_root_Entry_Password_StringVar'].set(self.UIData['Account_data'][self.hash_key].password)
                    self.UIData['edit_root_Entry_Server_host_StringVar'].set(self.UIData['Account_data'][self.hash_key].post_info.host)
                    self.UIData['edit_root_Entry_Server_port_StringVar'].set(str(self.UIData['Account_data'][self.hash_key].post_info.port))
                    self.UIData['edit_root_Entry_Server_access_token_StringVar'].set(self.UIData['Account_data'][self.hash_key].post_info.access_token)

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
            if tmp_platform_platform == 'qq' and tmp_platform_sdk == 'onebot' and tmp_server_auto == 'True':
                if tmp_host == '':
                    tmp_host = 'http://127.0.0.1'
                if tmp_port == '':
                    tmp_port = '58000'
                if tmp_access_token == '':
                    tmp_access_token = 'NONEED'
            if tmp_platform_platform == 'qqGuild' and tmp_platform_sdk == 'qqGuild_link':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'kaiheila' and tmp_platform_sdk == 'kaiheila_link':
                if tmp_id == '':
                    tmp_id = int(getHash(tmp_access_token), 16)
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'fanbook' and tmp_platform_sdk == 'fanbook_poll':
                if tmp_id == '':
                    tmp_id = int(getHash(tmp_access_token), 16)
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'dodo' and tmp_platform_sdk == 'dodo_poll':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'dodo' and tmp_platform_sdk == 'dodo_link':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
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
                self.UIData['Edit_res'] = [
                    tmp_action,
                    self.hash_key,
                    OlivOS.API.bot_info_T(
                        id = int(tmp_id),
                        password = tmp_password,
                        server_auto = str2bool(tmp_server_auto),
                        server_type = tmp_server_type,
                        host = tmp_host,
                        port = int(tmp_port),
                        access_token = tmp_access_token,
                        platform_sdk = tmp_platform_sdk,
                        platform_platform = tmp_platform_platform,
                        platform_model = tmp_platform_model
                    )
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
            if miss_key_list != None:
                if type(miss_key_list) == list:
                    #tmp_messagebox_str = 'Value Not Fount!\nPlease Complete Follow Item:\n-----------------\n%s' % '\n'.join(miss_key_list)
                    tmp_messagebox_str = '发现未填写条目！请确认完成填写。'
                    messagebox.showwarning('警告', tmp_messagebox_str)
            else:
                self.UIObject['edit_root'].destroy()


class TreeEditUI_old(object):
    def __init__(self, action, Account_data, hash_key = None, edit_commit_callback = None):
        self.hash_key = hash_key
        self.action = action
        self.edit_commit_callback = edit_commit_callback
        self.UIObject = {}
        self.UIConfig = {}
        self.UIConfig['color_001'] = '#00A0EA'
        self.UIConfig['color_002'] = '#BBE9FF'
        self.UIConfig['color_003'] = '#40C3FF'
        self.UIConfig['color_004'] = '#FFFFFF'
        self.UIConfig['color_005'] = '#000000'
        self.UIConfig['color_006'] = '#80D7FF'
        self.UIData = {}
        self.UIData['Account_data'] = Account_data
        self.UIData['Edit_res'] = [
            'none',
            'OLDHASH',
            None
        ]
        self.UIData['edit_root_Combobox_platform_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_sdk_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_model_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Entry_ID_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Entry_Password_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_Server_auto_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_Server_type_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Entry_Server_host_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Entry_Server_port_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_Server_access_token_StringVar'] = tkinter.StringVar()
        self.UIData['edit_root_Combobox_dict'] = {
            'platform_list': [
                'qq',
                'qqGuild',
                'kaiheila',
                'telegram',
                'dodo',
                'fanbook'
            ],
            'platform_sdk_list': {
                'qq': [
                    'onebot'
                ],
                'qqGuild': [
                    'qqGuild_link'
                ],
                'kaiheila': [
                    'kaiheila_link'
                ],
                'telegram': [
                    'telegram_poll'
                ],
                'dodo': [
                    'dodo_link'
                    #'dodo_poll',
                    #'dodobot_ea'
                ],
                'fanbook': [
                    'fanbook_poll'
                ]
            },
            'platform_sdk_model_list': {
                'qq': {
                    'onebot': [
                        #'gocqhttp',
                        #'gocqhttp_hide',
                        'gocqhttp_show',
                        'default'
                    ]
                },
                'qqGuild': {
                    'qqGuild_link': [
                        'private',
                        'public',
                        'default'
                    ]
                },
                'kaiheila': {
                    'kaiheila_link': [
                        'default'
                    ]
                },
                'telegram': {
                    'telegram_poll': [
                        'default'
                    ]
                },
                'dodo': {
                    'dodo_link': [
                        'default'
                    ],
                    'dodo_poll': [
                        'default'
                    ],
                    'dodobot_ea': [
                        'default'
                    ]
                },
                'fanbook': {
                    'fanbook_poll': [
                        'default',
                        'private'
                    ]
                }
            }
        }

        self.UIData['edit_root_Combobox_Server_auto_list'] = [
            'True',
            'False'
        ]

        self.UIData['edit_root_Combobox_Server_type_list'] = [
            'post',
            'websocket'
        ]

    def start(self):
        if self.action == 'create' or self.action == 'update':
            self.tree_edit_UI()
        elif self.action == 'delete':
            self.tree_edit_commit()

    def tree_edit_UI(self):
        self.UIObject['edit_root'] = tkinter.Toplevel()
        self.UIObject['edit_root'].title('OlivOS Edit Account')
        self.UIObject['edit_root'].geometry('400x370')
        self.UIObject['edit_root'].resizable(
            width = False,
            height = False
        )
        self.UIObject['edit_root'].configure(bg = self.UIConfig['color_001'])

        self.tree_UI_Button_init(
            name = 'edit_root_Button_commit',
            text = 'SAVE',
            command = self.tree_edit_commit,
            x = 310,
            y = 40,
            width = 70,
            height = 54
        )

        self.tree_edit_UI_Entry_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Entry_ID',
            str_name = 'edit_root_Entry_ID_StringVar',
            x = 100,
            y = 40,
            width = 200,
            height = 24,
            action = self.action,
            title = 'ID'
        )

        self.tree_edit_UI_Entry_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Entry_Password',
            str_name = 'edit_root_Entry_Password_StringVar',
            x = 100,
            y = 70,
            width = 200,
            height = 24,
            action = self.action,
            title = 'PASSWORD',
            mode = 'SAFE'
        )

        self.tree_edit_UI_Combobox_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Combobox_platform',
            str_name = 'edit_root_Combobox_platform_StringVar',
            x = 100,
            y = 100,
            width = 280,
            height = 24,
            action = self.action,
            title = 'PLATFORM'
        )

        self.tree_edit_UI_Combobox_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Combobox_sdk',
            str_name = 'edit_root_Combobox_sdk_StringVar',
            x = 100,
            y = 130,
            width = 280,
            height = 24,
            action = self.action,
            title = 'SDK'
        )

        self.tree_edit_UI_Combobox_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Combobox_model',
            str_name = 'edit_root_Combobox_model_StringVar',
            x = 100,
            y = 160,
            width = 280,
            height = 24,
            action = self.action,
            title = 'MODEL'
        )

        self.tree_edit_UI_Combobox_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Combobox_Server_auto',
            str_name = 'edit_root_Combobox_Server_auto_StringVar',
            x = 100,
            y = 190,
            width = 280,
            height = 24,
            action = self.action,
            title = 'AUTO'
        )

        self.tree_edit_UI_Combobox_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Combobox_Server_type',
            str_name = 'edit_root_Combobox_Server_type_StringVar',
            x = 100,
            y = 220,
            width = 280,
            height = 24,
            action = self.action,
            title = 'TYPE'
        )

        self.tree_edit_UI_Entry_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Entry_Server_host',
            str_name = 'edit_root_Entry_Server_host_StringVar',
            x = 100,
            y = 250,
            width = 280,
            height = 24,
            action = self.action,
            title = 'HOST'
        )

        self.tree_edit_UI_Entry_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Entry_Server_port',
            str_name = 'edit_root_Entry_Server_port_StringVar',
            x = 100,
            y = 280,
            width = 280,
            height = 24,
            action = self.action,
            title = 'PORT'
        )

        self.tree_edit_UI_Entry_init(
            obj_root = 'edit_root',
            obj_name = 'edit_root_Entry_Server_access_token',
            str_name = 'edit_root_Entry_Server_access_token_StringVar',
            x = 100,
            y = 310,
            width = 280,
            height = 24,
            action = self.action,
            title = 'TOKEN'
        )

        self.tree_edit_UI_Entry_update(self.action, 'init')
        self.tree_edit_UI_Combobox_update(self.action, 'init')

        self.UIObject['edit_root'].iconbitmap('./resource/tmp_favoricon.ico')

        self.UIObject['edit_root'].mainloop()

    def buttom_action(self, name, action):
        if name in self.UIObject:
            if action == '<Enter>':
                self.UIObject[name].configure(bg = self.UIConfig['color_006'])
            if action == '<Leave>':
                self.UIObject[name].configure(bg = self.UIConfig['color_003'])

    def tree_UI_Button_init(self, name, text, command, x, y, width, height):
        self.UIObject[name] = tkinter.Button(
            self.UIObject['edit_root'],
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
        self.UIObject[name].place(
            x = x,
            y = y,
            width = width,
            height = height
        )

    def tree_edit_UI_Entry_init(self, obj_root, obj_name, str_name, x, y, width, height, action, title = '', mode = 'NONE'):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text = title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004']
        )
        self.UIObject[obj_name + '=Label'].place(
            x = x - 100,
            y = y,
            width = 100,
            height = height
        )
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
        self.UIObject[obj_name].place(
            x = x,
            y = y,
            width = width,
            height = height
        )

    def tree_edit_UI_Combobox_init(self, obj_root, obj_name, str_name, x, y, width, height, action, title = ''):
        self.UIObject[obj_name + '=Label'] = tkinter.Label(
            self.UIObject[obj_root],
            text = title
        )
        self.UIObject[obj_name + '=Label'].configure(
            bg = self.UIConfig['color_001'],
            fg = self.UIConfig['color_004']
        )
        self.UIObject[obj_name + '=Label'].place(
            x = x - 100,
            y = y,
            width = 100,
            height = height
        )
        self.UIObject[obj_name] = ttk.Combobox(
            self.UIObject[obj_root],
            textvariable = self.UIData[str_name]
        )
        self.UIObject[obj_name].place(
            x = x,
            y = y,
            width = width,
            height = height
        )
        self.UIObject[obj_name].configure(state='readonly')
        self.UIObject[obj_name].bind('<<ComboboxSelected>>', lambda x : self.tree_edit_UI_Combobox_ComboboxSelected(x, action, obj_name))

    def tree_edit_UI_Combobox_ComboboxSelected(self, action, event, target):
        if target == 'edit_root_Combobox_platform':
            self.tree_edit_UI_Combobox_update(action, 'platform')
        elif target == 'edit_root_Combobox_sdk':
            self.tree_edit_UI_Combobox_update(action, 'sdk')
        elif target == 'edit_root_Combobox_model':
            self.tree_edit_UI_Combobox_update(action, 'model')

    def tree_edit_UI_Combobox_update(self, action, con_action):
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
                    self.UIData['edit_root_Entry_Password_StringVar'].set(self.UIData['Account_data'][self.hash_key].password)
                    self.UIData['edit_root_Entry_Server_host_StringVar'].set(self.UIData['Account_data'][self.hash_key].post_info.host)
                    self.UIData['edit_root_Entry_Server_port_StringVar'].set(str(self.UIData['Account_data'][self.hash_key].post_info.port))
                    self.UIData['edit_root_Entry_Server_access_token_StringVar'].set(self.UIData['Account_data'][self.hash_key].post_info.access_token)

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
            if tmp_platform_platform == 'qq' and tmp_platform_sdk == 'onebot' and tmp_server_auto == 'True':
                if tmp_host == '':
                    tmp_host = 'http://127.0.0.1'
                if tmp_port == '':
                    tmp_port = '58000'
                if tmp_access_token == '':
                    tmp_access_token = 'NONEED'
            if tmp_platform_platform == 'qqGuild' and tmp_platform_sdk == 'qqGuild_link':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'kaiheila' and tmp_platform_sdk == 'kaiheila_link':
                if tmp_id == '':
                    tmp_id = int(getHash(tmp_access_token), 16)
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'fanbook' and tmp_platform_sdk == 'fanbook_poll':
                if tmp_id == '':
                    tmp_id = int(getHash(tmp_access_token), 16)
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'dodo' and tmp_platform_sdk == 'dodo_poll':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
            if tmp_platform_platform == 'dodo' and tmp_platform_sdk == 'dodo_link':
                if tmp_password == '':
                    tmp_password = 'NONEED'
                if tmp_host == '':
                    tmp_host = 'NONEED'
                if tmp_port == '':
                    tmp_port = '0'
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
                self.UIData['Edit_res'] = [
                    tmp_action,
                    self.hash_key,
                    OlivOS.API.bot_info_T(
                        id = int(tmp_id),
                        password = tmp_password,
                        server_auto = str2bool(tmp_server_auto),
                        server_type = tmp_server_type,
                        host = tmp_host,
                        port = int(tmp_port),
                        access_token = tmp_access_token,
                        platform_sdk = tmp_platform_sdk,
                        platform_platform = tmp_platform_platform,
                        platform_model = tmp_platform_model
                    )
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
            if miss_key_list != None:
                if type(miss_key_list) == list:
                    tmp_messagebox_str = 'Value Not Fount!\nPlease Complete Follow Item:\n-----------------\n%s' % '\n'.join(miss_key_list)
                    messagebox.showwarning('Warning', tmp_messagebox_str)
            else:
                self.UIObject['edit_root'].destroy()

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
