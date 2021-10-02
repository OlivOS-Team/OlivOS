# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/API.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import multiprocessing
import hashlib

import OlivOS

OlivOS_Version = OlivOS.infoAPI.OlivOS_Version
mod_global_name = sys.modules[__name__]


class Control(object):
    def __init__(self, name, init_list, control_queue, scan_interval):
        self.name = name
        self.init_list = init_list
        self.control_queue = control_queue
        self.scan_interval = scan_interval

    class packet(object):
        def __init__(self, action, key = None):
            self.action = action
            self.key = key

class bot_info_T(object):
    def __init__(self, id = -1, password = '', server_type = 'post', server_auto = False, host = '', port = -1, access_token = None, platform_sdk = None, platform_platform = None, platform_model = None):
        self.id = id
        self.password = password
        self.platform = {}
        self.platform['sdk'] = platform_sdk
        self.platform['platform'] = platform_platform
        self.platform['model'] = platform_model
        self.hash = None
        self.post_info = self.post_info_T(
            server_auto = server_auto,
            server_type = server_type,
            host = host,
            port = port,
            access_token = access_token
        )
        self.debug_mode = False
        self.getHash()

    class post_info_T(object):
        def __init__(self, host = '', port = -1, access_token = None, server_type = 'post', server_auto = False):
            self.auto = server_auto
            self.type = server_type
            self.host = host
            self.port = port
            self.access_token = access_token

    def getHash(self):
        self.hash = getBotHash(
            bot_id = self.id,
            platform_sdk = self.platform['sdk'],
            platform_platform = self.platform['platform'],
            platform_model = self.platform['model']
        )

def getBotHash(bot_id = None, platform_sdk = None, platform_platform = None, platform_model = None):
    hash_tmp = hashlib.new('md5')
    hash_tmp.update(str(bot_id).encode(encoding='UTF-8'))
    hash_tmp.update(str(platform_sdk).encode(encoding='UTF-8'))
    hash_tmp.update(str(platform_platform).encode(encoding='UTF-8'))
    #hash_tmp.update(str(platform_model).encode(encoding='UTF-8'))
    return hash_tmp.hexdigest()

class Event(object):
    def __init__(self, sdk_event = None, log_func = None):
        self.bot_info = None
        self.platform = {}
        self.platform['sdk'] = None
        self.platform['platform'] = None
        self.platform['model'] = None
        self.data = None
        self.active = False
        self.log_func = log_func
        self.base_info = {}
        self.base_info['time'] = None
        self.base_info['self_id'] = None
        self.base_info['type'] = None
        self.plugin_info = {}
        self.plugin_info['func_type'] = None
        self.sdk_event = sdk_event
        self.sdk_event_type = type(self.sdk_event)
        self.get_Event_from_SDK()
        self.do_init_log()

    def get_Event_from_SDK(self):
        if self.sdk_event_type is OlivOS.onebotSDK.event:
            OlivOS.onebotSDK.get_Event_from_SDK(self)
        if self.sdk_event_type is OlivOS.telegramSDK.event:
            OlivOS.telegramSDK.get_Event_from_SDK(self)

    def do_init_log(self):
        if self.active:
            tmp_log_level = 0
            tmp_log_message = ''
            if self.plugin_info['func_type'] == 'private_message':
                tmp_log_level = 2
                tmp_log_message = 'User[' + self.data.sender['nickname'] + '](' + str(self.data.user_id) + ') : ' + self.data.message
            elif self.plugin_info['func_type'] == 'group_message':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User[' + self.data.sender['nickname'] + '](' + str(self.data.user_id) + ') : ' + self.data.message
            elif self.plugin_info['func_type'] == 'group_file_upload':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') : ' + self.data.file['name']
            elif self.plugin_info['func_type'] == 'group_admin':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') Action(' +  self.data.action + ')'
            elif self.plugin_info['func_type'] == 'group_member_decrease':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') <- Operator(' +  str(self.data.operator_id) + ') Action(' + self.data.action + ')'
            elif self.plugin_info['func_type'] == 'group_member_increase':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') <- Operator(' +  str(self.data.operator_id) + ') Action(' + self.data.action + ')'
            elif self.plugin_info['func_type'] == 'group_ban':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') <- Operator(' +  str(self.data.operator_id) + ') Duration(' + str(self.data.duration) + ') Action(' + self.data.action + ')'
            elif self.plugin_info['func_type'] == 'group_message_recall':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') <- Operator(' +  str(self.data.operator_id) + ') Message_id(' + str(self.data.message_id) + ')'
            elif self.plugin_info['func_type'] == 'private_message_recall':
                tmp_log_level = 2
                tmp_log_message = 'User(' + str(self.data.user_id) + ') Message_id(' + str(self.data.message_id) + ')'
            elif self.plugin_info['func_type'] == 'poke':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') -> Target(' +  str(self.data.target_id) + ')'
            elif self.plugin_info['func_type'] == 'group_lucky_king':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') -> Target(' +  str(self.data.target_id) + ')'
            elif self.plugin_info['func_type'] == 'group_honor':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') Type(' + str(self.data.type) + ')'
            elif self.plugin_info['func_type'] == 'friend_add_request':
                tmp_log_level = 2
                tmp_log_message = 'User(' + str(self.data.user_id) + ') Flag(' + str(self.data.flag) + ') : ' + self.sdk_event.json['comment']
            elif self.plugin_info['func_type'] == 'group_add_request':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') Flag(' + str(self.data.flag) + ') : ' + self.sdk_event.json['comment']
            elif self.plugin_info['func_type'] == 'group_invite_request':
                tmp_log_level = 2
                tmp_log_message = 'Group(' + str(self.data.group_id) + ') User(' + str(self.data.user_id) + ') Flag(' + str(self.data.flag) + ') : ' + self.sdk_event.json['comment']
            elif self.plugin_info['func_type'] == 'lifecycle':
                tmp_log_level = 2
                tmp_log_message = 'Action(' + str(self.data.action) + ')'
            elif self.plugin_info['func_type'] == 'heartbeat':
                tmp_log_level = 1
                tmp_log_message = 'Interval(' + str(self.data.interval) + ')'
            self.log_func(tmp_log_level, tmp_log_message, [
                (self.platform['platform'], 'default'),
                (self.plugin_info['func_type'], 'default')
            ])

    class private_message(object):
        def __init__(self, user_id, message, sub_type, flag_lazy = True):
            self.sub_type = sub_type
            self.message = message
            self.message_id = None
            self.raw_message = None
            self.user_id = user_id
            self.font = None
            self.sender = {}
            if flag_lazy:
                self.sender['nickname'] = 'Nobody'

    class group_message(object):
        def __init__(self, group_id, user_id, message, sub_type, flag_lazy = True):
            self.sub_type = sub_type
            self.group_id = group_id
            self.message = message
            self.message_id = None
            self.raw_message = None
            self.user_id = user_id
            self.font = None
            self.sender = {}
            if flag_lazy:
                self.sender['nickname'] = 'Nobody'

    class group_file_upload(object):
        def __init__(self, group_id, user_id, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.file = {}
            if flag_lazy:
                self.file['id'] = 'Nofileid'
                self.file['name'] = 'Nofile'
                self.file['size'] = 0
                self.file['busid'] = -1

    class group_admin(object):
        def __init__(self, group_id, user_id, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.action = 'unset'

    class group_member_decrease(object):
        def __init__(self, group_id, operator_id, user_id, action = 'leave', flag_lazy = True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.action = action

    class group_member_increase(object):
        def __init__(self, group_id, operator_id, user_id, action = 'approve', flag_lazy = True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.action = action

    class group_ban(object):
        def __init__(self, group_id, operator_id, user_id, duration, action = 'unban', flag_lazy = True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.duration = duration
            self.action = action

    class friend_add(object):
        def __init__(self, user_id, flag_lazy = True):
            self.user_id = user_id

    class group_message_recall(object):
        def __init__(self, group_id, operator_id, user_id, message_id, flag_lazy = True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.message_id = message_id

    class private_message_recall(object):
        def __init__(self, user_id, message_id, flag_lazy = True):
            self.user_id = user_id
            self.message_id = message_id

    class poke(object):
        def __init__(self, user_id, target_id, group_id = -1, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.target_id = target_id

    class group_lucky_king(object):
        def __init__(self, group_id, user_id, target_id, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.target_id = target_id

    class group_honor(object):
        def __init__(self, group_id, user_id, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.type = None

    class friend_add_request(object):
        def __init__(self, user_id, comment = '', flag_lazy = True):
            self.user_id = user_id
            self.comment = comment
            self.flag = None

    class group_add_request(object):
        def __init__(self, group_id, user_id, comment = '', flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.comment = comment
            self.flag = None

    class group_invite_request(object):
        def __init__(self, group_id, user_id, comment = '', flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.comment = comment
            self.flag = None

    class lifecycle(object):
        def __init__(self, action = None, flag_lazy = True):
            self.action = action

    class heartbeat(object):
        def __init__(self, interval, flag_lazy = True):
            self.interval = interval

    #以下为统一事件动作调用方法实现，各接入sdk需完全支持

    def __reply(self, message, flag_log = True):
        flag_type = None
        if checkByListOrEqual(
            self.plugin_info['func_type'],
            [
                'private_message',
                'friend_add',
                'private_message_recall',
                'friend_add_request'
            ]
        ):
            self.__send('private', self.data.user_id, message, flag_log = False)
            flag_type = 'private'
        elif checkByListOrEqual(
            self.plugin_info['func_type'],
            [
                'group_message',
                'group_file_upload',
                'group_admin',
                'group_member_decrease',
                'group_member_increase',
                'group_ban',
                'group_message_recall',
                'group_lucky_king',
                'group_honor',
                'group_add_request',
                'group_invite_request'
                
            ]
        ):
            self.__send('group', self.data.group_id, message, flag_log = False)
            flag_type = 'group'
        elif checkByListOrEqual(
            self.plugin_info['func_type'],
            [
                'poke'
            ]
        ):
            if self.data.group_id == -1:
                self.__send('private', self.data.user_id, message, flag_log = False)
                flag_type = 'private'
            else:
                self.__send('group', self.data.group_id, message, flag_log = False)
                flag_type = 'group'

        if flag_log:
            if flag_type == 'private':
                self.log_func(2, 'User(' + str(self.data.user_id) + '): ' + message, [
                    (self.platform['platform'], 'default'),
                    ('reply', 'callback')
                ])
            elif flag_type == 'group':
                self.log_func(2, 'Group(' + str(self.data.group_id) + '): ' + message, [
                    (self.platform['platform'], 'default'),
                    ('reply', 'callback')
                ])

    def reply(self, message, flag_log = True, remote = False):
        if remote:
            pass
        else:
            self.__reply(message, flag_log = True)


    def __send(self, send_type, target_id, message, flag_log = True):
        flag_type = send_type
        if self.platform['sdk'] == 'onebot':
            if flag_type == 'private':
                OlivOS.onebotSDK.event_action.send_private_msg(self, target_id, message)
            elif flag_type == 'group':
                OlivOS.onebotSDK.event_action.send_group_msg(self, target_id, message)
        elif self.platform['sdk'] == 'telegram_poll':
            OlivOS.telegramSDK.event_action.send_msg(self, target_id, message)

        if flag_log:
            if flag_type == 'private':
                self.log_func(2, 'User(' + str(target_id) + '): ' + message, [
                    (self.platform['platform'], 'default'),
                    ('send', 'callback')
                ])
            elif flag_type == 'group':
                self.log_func(2, 'Group(' + str(target_id) + '): ' + message, [
                    (self.platform['platform'], 'default'),
                    ('send', 'callback')
                ])

    def send(self, send_type, target_id, message, flag_log = True, remote = False):
        if remote:
            pass
        else:
            self.__send(send_type, target_id, message, flag_log = True)


    def __delete_msg(self, message_id, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            OlivOS.onebotSDK.event_action.delete_msg(self, message_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

        if flag_log:
            self.log_func(2, ': done' , [
                (self.platform['platform'], 'default'),
                ('delete_msg', 'callback')
            ])

    def delete_msg(self, message_id, flag_log = True, remote = False):
        if remote:
            pass
        else:
            self.__delete_msg(message_id, flag_log = True)


    def __get_msg(self, message_id, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_msg(self, message_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

        if res_data == None:
            return None

        if flag_log:
            if checkDictByListAnd(
                res_data, [
                    ['active']
                ]
            ):
                if res_data['active'] == True:
                    self.log_func(2, ': succeed' , [
                        (self.platform['platform'], 'default'),
                        ('get_msg', 'callback')
                    ])
                else:
                    self.log_func(2, ': failed' , [
                        (self.platform['platform'], 'default'),
                        ('get_msg', 'callback')
                    ])
        return res_data

    def get_msg(self, message_id, flag_log = True, remote = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_msg(message_id, flag_log = True)
        return res_data


    def __get_login_info(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

        if res_data == None:
            return None

        if flag_log:
            if checkDictByListAnd(
                res_data, [
                    ['active'],
                    ['data', 'nickname'],
                    ['data', 'id']
                ]
            ):
                if res_data['active'] == True:
                    self.log_func(2, ': nickname(' + res_data['data']['nickname'] + ') id(' + str(res_data['data']['id']) + ')' , [
                        (self.platform['platform'], 'default'),
                        ('get_login_info', 'callback')
                    ])
                else:
                    self.log_func(2, ': failed' , [
                        (self.platform['platform'], 'default'),
                        ('get_login_info', 'callback')
                    ])
        return res_data

    def get_login_info(self, flag_log = True, remote = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_login_info(flag_log = True)
        return res_data


    def __get_stranger_info(self, user_id, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_stranger_info(self, user_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

        if res_data == None:
            return None

        if flag_log:
            if checkDictByListAnd(
                res_data, [
                    ['active']
                ]
            ):
                if res_data['active'] == True:
                    self.log_func(2, ': succeed' , [
                        (self.platform['platform'], 'default'),
                        ('get_stranger_info', 'callback')
                    ])
                else:
                    self.log_func(2, ': failed' , [
                        (self.platform['platform'], 'default'),
                        ('get_stranger_info', 'callback')
                    ])
        return res_data

    def get_stranger_info(self, user_id, flag_log = True, remote = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_stranger_info(user_id, flag_log = True)
        return res_data


    def __get_friend_list(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_friend_list(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

        if res_data == None:
            return None

        if flag_log:
            if checkDictByListAnd(
                res_data, [
                    ['active']
                ]
            ):
                if res_data['active'] == True:
                    self.log_func(2, ': succeed' , [
                        (self.platform['platform'], 'default'),
                        ('get_friend_list', 'callback')
                    ])
                else:
                    self.log_func(2, ': failed' , [
                        (self.platform['platform'], 'default'),
                        ('get_friend_list', 'callback')
                    ])
        return res_data

    def get_friend_list(self, flag_log = True, remote = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_friend_list(flag_log = True)
        return res_data


    def __get_group_info(self, group_id, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_group_info(self, group_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

        if res_data == None:
            return None

        if flag_log:
            if checkDictByListAnd(
                res_data, [
                    ['active']
                ]
            ):
                if res_data['active'] == True:
                    self.log_func(2, ': succeed' , [
                        (self.platform['platform'], 'default'),
                        ('get_group_info', 'callback')
                    ])
                else:
                    self.log_func(2, ': failed' , [
                        (self.platform['platform'], 'default'),
                        ('get_group_info', 'callback')
                    ])
        return res_data

    def get_group_info(self, group_id, flag_log = True, remote = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_info(group_id, flag_log = True)
        return res_data


    def __get_group_list(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_group_list(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

        if res_data == None:
            return None

        if flag_log:
            if checkDictByListAnd(
                res_data, [
                    ['active']
                ]
            ):
                if res_data['active'] == True:
                    self.log_func(2, ': succeed' , [
                        (self.platform['platform'], 'default'),
                        ('get_group_list', 'callback')
                    ])
                else:
                    self.log_func(2, ': failed' , [
                        (self.platform['platform'], 'default'),
                        ('get_group_list', 'callback')
                    ])
        return res_data

    def get_group_list(self, flag_log = True, remote = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_list(flag_log = True)
        return res_data


class api_result_data_template(object):
    class get_msg(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(
                {
                    'message_id': None,
                    'id': -1,
                    'sender': {
                        'id': -1,
                        'name': None
                    },
                    'time': -1,
                    'message': None,
                    'raw_message': None
                }
            )

    class get_login_info(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(
                {
                    'name': None,
                    'id': -1
                }
            )

    class get_user_info_strip(dict):
        def __init__(self):
            self.update(
                {
                    'name': None,
                    'id': -1
                }
            )

    class get_stranger_info(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(api_result_data_template.get_user_info_strip())

    class get_friend_list(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = []

    class get_group_info_strip(dict):
        def __init__(self):
            self.update(
                {
                    'name': None,
                    'id': -1,
                    'memo': None,
                    'max_member_count': 0
                }
            )

    class get_group_info(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(api_result_data_template.get_group_info_strip())

    class get_group_list(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = []

class Proc_templet(object):
    def __init__(self, Proc_name = 'native_plugin', Proc_type = 'default', scan_interval = 0.001, dead_interval = 1, rx_queue = None, tx_queue = None, control_queue = None, logger_proc = None):
        self.deamon = True
        self.Proc = None
        self.Proc_name = Proc_name
        self.Proc_type = Proc_type
        self.Proc_info = self.Proc_info_T(
            rx_queue = rx_queue,
            tx_queue = tx_queue,
            control_queue = control_queue,
            logger_proc = logger_proc,
            scan_interval = scan_interval,
            dead_interval = dead_interval
        )
        self.Proc_config = {}
        self.Proc_data = {}

    class Proc_info_T(object):
        def __init__(self, rx_queue, tx_queue, control_queue, logger_proc, scan_interval = 0.001, dead_interval = 1):
            self.rx_queue = rx_queue
            self.tx_queue = tx_queue
            self.control_queue = control_queue
            self.logger_proc = logger_proc
            self.scan_interval = scan_interval
            self.dead_interval = dead_interval

    def run(self):
        pass

    def start(self):
        proc_this = multiprocessing.Process(name = self.Proc_name, target = self.run, args = ())
        proc_this.daemon = self.deamon
        proc_this.start()
        self.Proc = proc_this
        return self.Proc

    def log(self, log_level, log_message, log_segment = []):
        if self.Proc_info.logger_proc != None:
            self.Proc_info.logger_proc.log(log_level, log_message, log_segment)

#兼容Win平台的进程生成方法
def Proc_start(proc_this):
    proc_proc_this = multiprocessing.Process(name = proc_this.Proc_name, target = proc_this.run, args = ())
    proc_proc_this.daemon = proc_this.deamon
    #multiprocessing.Process无法进行弱引用序列化烘培，故无法在Win平台下实现自动更新进程引用
    #proc_this.Proc = proc_proc_this
    proc_proc_this.start()
    return proc_proc_this

class Proc_info_T(object):
    def __init__(self, rx_queue, tx_queue, logger_proc, scan_interval = 0.001):
        self.rx_queue = rx_queue
        self.tx_queue = tx_queue
        self.logger_proc = logger_proc
        self.scan_interval = scan_interval


class PARA_templet(object):
    def __init__(self, type = None, data = None):
        self.type = type
        self.data = data

    def CQ(self):
        CQ_tmp = '[CQ:' + self.type
        if self.data != None:
            for key_this in self.data:
                if self.data[key_this] != None:
                    CQ_tmp += ',' + key_this + '=' + str(self.data[key_this])
        CQ_tmp += ']'
        return CQ_tmp

    def PARA(self):
        PARA_tmp = self.cut()
        if self.data == None:
            PARA_tmp.data = dict()
        return json.dumps(obj = PARA_tmp.__dict__)

    def copy(self):
        copy_tmp = PARA_templet(self.type, self.data.copy())
        return copy_tmp

    def cut(self):
        copy_tmp = self.copy()
        if copy_tmp.data != None:
            for key_this in self.data:
                if copy_tmp.data[key_this] == None:
                    del copy_tmp.data[key_this]
                else:
                    copy_tmp.data[key_this] = str(copy_tmp.data[key_this])
        return copy_tmp

class PARA(object):
    class text(PARA_templet):
        def __init__(self, text = ''):
            PARA_templet.__init__(self, 'text', self.data_T(text))

        class data_T(dict):
            def __init__(self, text = ''):
                self['text'] = text

        def CQ(self):
            if self.data != None:
                if type(self.data.text) is str:
                    return self.data.text
                else:
                    return str(self.data.text)
            else:
                return ''

    class face(PARA_templet):
        def __init__(self, id):
            PARA_templet.__init__(self, 'face', self.data_T(id))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id

    class image(PARA_templet):
        def __init__(self, file, type = None, url = None, cache = None, proxy = None, timeout = None):
            PARA_templet.__init__(self, 'image', self.data_T(file, type, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, type, url, cache, proxy, timeout):
                self['file'] = file
                self['type'] = type
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

    class record(PARA_templet):
        def __init__(self, file, magic = None, url = None, cache = None, proxy = None, timeout = None):
            PARA_templet.__init__(self, 'record', self.data_T(file, type, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, magic, url, cache, proxy, timeout):
                self['file'] = file
                self['magic'] = magic
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

    class video(PARA_templet):
        def __init__(self, file, url = None, cache = None, proxy = None, timeout = None):
            PARA_templet.__init__(self, 'record', self.data_T(file, type, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, url, cache, proxy, timeout):
                self['file'] = file
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

    class at(PARA_templet):
        def __init__(self, qq):
            PARA_templet.__init__(self, 'at', self.data_T(qq))

        class data_T(dict):
            def __init__(self, qq):
                self['qq'] = qq

    class rps(PARA_templet):
        def __init__(self):
            PARA_templet.__init__(self, 'rps', None)

    class dice(PARA_templet):
        def __init__(self):
            PARA_templet.__init__(self, 'dice', None)

    class shake(PARA_templet):
        def __init__(self):
            PARA_templet.__init__(self, 'shake', None)

    class poke(PARA_templet):
        def __init__(self, type, id, name = None):
            PARA_templet.__init__(self, 'poke', self.data_T(type, id, name))

        class data_T(dict):
            def __init__(self, type, id, name):
                self['type'] = type
                self['id'] = id
                self['name'] = name

    class anonymous(PARA_templet):
        def __init__(self):
            PARA_templet.__init__(self, 'shake', None)

    class share(PARA_templet):
        def __init__(self, url, title, content = None, image = None):
            PARA_templet.__init__(self, 'share', self.data_T(url, title, content, image))

        class data_T(dict):
            def __init__(self, url, title, content, image):
                self['url'] = url
                self['title'] = title
                self['content'] = content
                self['image'] = image

    class contact(PARA_templet):
        def __init__(self, type, id):
            PARA_templet.__init__(self, 'contact', self.data_T(type, id))

        class data_T(dict):
            def __init__(self, type, id):
                self['type'] = type
                self['id'] = id

    class location(PARA_templet):
        def __init__(self, lat, lon, title = None, content = None):
            PARA_templet.__init__(self, 'location', self.data_T(lat, lon, title, content))

        class data_T(dict):
            def __init__(self, lat, lon, title, content):
                self['lat'] = lat
                self['lon'] = lon
                self['title'] = title
                self['content'] = content

    class music(PARA_templet):
        def __init__(self, type, id = None, url = None, audio = None, title = None, content = None, image = None):
            PARA_templet.__init__(self, 'music', self.data_T(type, id, url, audio, title, content, image))

        class data_T(dict):
            def __init__(self, type, id, url, audio, title, content, image):
                self['type'] = type
                self['id'] = id
                self['url'] = url
                self['audio'] = audio
                self['title'] = title
                self['content'] = content
                self['image'] = image

    class reply(PARA_templet):
        def __init__(self, id):
            PARA_templet.__init__(self, 'reply', self.data_T(id))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id

    class forward(PARA_templet):
        def __init__(self, id):
            PARA_templet.__init__(self, 'forward', self.data_T(id))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id

    class node(PARA_templet):
        def __init__(self, id = None, user_id = None, nickname = None, content = None):
            PARA_templet.__init__(self, 'node', self.data_T(id, user_id, nickname, content))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id
                self['user_id'] = user_id
                self['nickname'] = nickname
                self['content'] = content

def checkByListAnd(check_list):
    flag_res = True
    for check_list_this in check_list:
        if not check_list_this:
            flag_res = False
            return flag_res
    return flag_res

def checkByListOr(check_list):
    flag_res = False
    for check_list_this in check_list:
        if check_list_this:
            flag_res = True
            return flag_res
    return flag_res

def checkByListAndEqual(checked_obj, check_list):
    flag_res = True
    for check_list_this in check_list:
        if checked_obj != check_list_this:
            flag_res = False
            return flag_res
    return flag_res

def checkByListOrEqual(checked_obj, check_list):
    flag_res = False
    for check_list_this in check_list:
        if checked_obj == check_list_this:
            flag_res = True
            return flag_res
    return flag_res

def checkDictByListAnd(checked_obj, check_list):
    flag_res = True
    for check_list_this in check_list:
        tmp_checked_obj = checked_obj
        for check_list_this_this in check_list_this:
            if check_list_this_this in tmp_checked_obj:
                tmp_checked_obj = tmp_checked_obj[check_list_this_this]
            else:
                flag_res = False
                return flag_res
    return flag_res
