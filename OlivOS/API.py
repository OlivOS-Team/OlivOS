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
import threading
import hashlib
import time
import traceback

from functools import wraps

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


def getMenuEvent(target_event):
    target_event.base_info['time'] = int(time.time())
    target_event.base_info['self_id'] = None
    target_event.base_info['type'] = None
    target_event.platform['sdk'] = 'all'
    target_event.platform['platform'] = 'all'
    target_event.platform['model'] = 'all'
    target_event.plugin_info['message_mode_rx'] = 'olivos_para'
    if target_event.sdk_event.action == 'send':
        if type(target_event.sdk_event.key) == dict:
            if 'data' in target_event.sdk_event.key:
                if 'action' in target_event.sdk_event.key['data']:
                    if 'plugin_menu' == target_event.sdk_event.key['data']['action']:
                        target_event.active = True
                        target_event.plugin_info['func_type'] = 'menu'
                        target_event.data = target_event.menu(
                            namespace = target_event.sdk_event.key['data']['namespace'],
                            event = target_event.sdk_event.key['data']['event']
                        )
    pass


class Event(object):
    def __init__(self, sdk_event = None, log_func = None):
        self.bot_info = None
        self.platform = {}
        self.platform['sdk'] = None
        self.platform['platform'] = None
        self.platform['model'] = None
        self.data = None
        self.active = False
        self.blocked = False
        self.log_func = log_func
        self.base_info = {}
        self.base_info['time'] = None
        self.base_info['self_id'] = None
        self.base_info['type'] = None
        self.plugin_info = {}
        self.plugin_info['func_type'] = None
        self.plugin_info['message_mode_rx'] = OlivOS.infoAPI.OlivOS_message_mode_rx_default
        self.plugin_info['message_mode_tx'] = OlivOS.infoAPI.OlivOS_message_mode_tx_unity
        self.plugin_info['name'] = 'unity'
        self.plugin_info['namespace'] = 'unity'
        self.plugin_info['tx_queue'] = []
        self.sdk_event = sdk_event
        self.sdk_event_type = type(self.sdk_event)
        self.get_Event_from_SDK()
        self.get_Event_on_Plugin()
        self.do_init_log()

    def get_Event_from_SDK(self):
        if self.sdk_event_type is OlivOS.onebotSDK.event:
            OlivOS.onebotSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.qqGuildSDK.event:
            OlivOS.qqGuildSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.telegramSDK.event:
            OlivOS.telegramSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.fanbookSDK.event:
            OlivOS.fanbookSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.dodoLinkSDK.event:
            OlivOS.dodoLinkSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.dodoSDK.event:
            OlivOS.dodoSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.dodobotEASDK.event:
            OlivOS.dodobotEASDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.contentAPI.fake_sdk_event:
            OlivOS.contentAPI.get_Event_from_fake_SDK(self)
        elif self.sdk_event_type is OlivOS.kaiheilaSDK.event:
            OlivOS.kaiheilaSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.API.Control.packet:
            getMenuEvent(self)

    def get_Event_on_Plugin(self):
        if self.plugin_info['func_type'] in [
            'private_message',
            'group_message'
        ]:
            if self.plugin_info['message_mode_tx'] == 'olivos_para' or self.data.message_sdk.mode_rx != self.plugin_info['message_mode_tx']:
                self.data.message = self.data.message_sdk.get(self.plugin_info['message_mode_tx'])
                self.data.raw_message = self.data.raw_message_sdk.get(self.plugin_info['message_mode_tx'])
            else:
                self.data.message = self.data.message_sdk.data_raw
                self.data.raw_message = self.data.raw_message_sdk.data_raw

    def do_init_log(self):
        if self.active:
            tmp_globalMetaTableTemp_patch = {}
            tmp_log_level = 0
            tmp_log_message = ''
            tmp_log_message_default = 'N/A'
            if self.plugin_info['func_type'] == 'fake_event':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['self', self.base_info['self_id']]
                ])
            elif self.plugin_info['func_type'] == 'private_message':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['nickname', self.data.sender['nickname']],
                    ['user_id', self.data.user_id],
                    ['message', self.data.message]
                ])
            elif self.plugin_info['func_type'] == 'group_message':
                tmp_host_id = '-'
                if self.data.host_id != None:
                    tmp_host_id = str(self.data.host_id)
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['host_id', tmp_host_id],
                    ['group_id', self.data.group_id],
                    ['nickname', self.data.sender['nickname']],
                    ['user_id', self.data.user_id],
                    ['message', self.data.message]
                ])
            elif self.plugin_info['func_type'] == 'group_file_upload':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['name', self.data.file['name']]
                ])
            elif self.plugin_info['func_type'] == 'group_admin':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['action', self.data.action]
                ])
            elif self.plugin_info['func_type'] == 'group_member_decrease':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['operator_id', self.data.operator_id],
                    ['action', self.data.action]
                ])
            elif self.plugin_info['func_type'] == 'group_member_increase':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['operator_id', self.data.operator_id],
                    ['action', self.data.action]
                ])
            elif self.plugin_info['func_type'] == 'group_ban':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['operator_id', self.data.operator_id],
                    ['duration', self.data.duration],
                    ['action', self.data.action]
                ])
            elif self.plugin_info['func_type'] == 'friend_add':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['user_id', self.data.user_id]
                ])
            elif self.plugin_info['func_type'] == 'group_message_recall':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['operator_id', self.data.operator_id],
                    ['message_id', self.data.message_id]
                ])
            elif self.plugin_info['func_type'] == 'private_message_recall':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['user_id', self.data.user_id],
                    ['message_id', self.data.message_id]
                ])
            elif self.plugin_info['func_type'] == 'poke':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['target_id', self.data.target_id]
                ])
            elif self.plugin_info['func_type'] == 'group_lucky_king':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['target_id', self.data.target_id]
                ])
            elif self.plugin_info['func_type'] == 'group_honor':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['type', self.data.type]
                ])
            elif self.plugin_info['func_type'] == 'friend_add_request':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['user_id', self.data.user_id],
                    ['flag', self.data.flag],
                    ['comment', self.data.comment]
                ])
            elif self.plugin_info['func_type'] == 'group_add_request':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['flag', self.data.flag],
                    ['comment', self.data.comment]
                ])
            elif self.plugin_info['func_type'] == 'group_invite_request':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['group_id', self.data.group_id],
                    ['user_id', self.data.user_id],
                    ['flag', self.data.flag],
                    ['comment', self.data.comment]
                ])
            elif self.plugin_info['func_type'] == 'lifecycle':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['action', self.data.action]
                ])
            elif self.plugin_info['func_type'] == 'heartbeat':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['interval', self.data.interval]
                ])
            elif self.plugin_info['func_type'] == 'menu':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['namespace', self.data.namespace],
                    ['event', self.data.event]
                ])
            if self.plugin_info['func_type'] in OlivOS.metadataAPI.eventLogMetaTable:
                tmp_log_level = OlivOS.metadataAPI.eventLogMetaTable[self.plugin_info['func_type']]['level']
                tmp_log_message = OlivOS.metadataAPI.getTextByMetaTableFormat(
                    src_table = OlivOS.metadataAPI.globalMetaTable,
                    fwd_key = OlivOS.metadataAPI.eventLogMetaTable[self.plugin_info['func_type']]['message_key'],
                    format_patch = tmp_globalMetaTableTemp_patch,
                    default_res = tmp_log_message_default
                )
            else:
                tmp_log_level = 3
                tmp_log_message = tmp_log_message_default
            if self.log_func != None:
                self.log_func(tmp_log_level, tmp_log_message, [
                    (self.getBotIDStr(), 'default'),
                    (self.plugin_info['name'], 'default'),
                    (self.plugin_info['func_type'], 'default')
                ])

    class fake_event(object):
        def __init__(self):
            self.default = None

    class menu(object):
        def __init__(self, namespace, event):
            self.namespace = namespace
            self.event = event

    class private_message(object):
        def __init__(self, user_id, message, sub_type, flag_lazy = True):
            self.sub_type = sub_type
            self.message = message
            self.message_sdk = message
            self.message_id = None
            self.raw_message = None
            self.raw_message_sdk = None
            self.user_id = user_id
            self.font = None
            self.sender = {}
            self.extend = {}
            if flag_lazy:
                self.sender['nickname'] = 'Nobody'
                self.extend['host_group_id'] = None

    class group_message(object):
        def __init__(self, group_id, user_id, message, sub_type, flag_lazy = True):
            self.sub_type = sub_type
            self.host_id = None
            self.group_id = group_id
            self.message = message
            self.message_sdk = message
            self.message_id = None
            self.raw_message = None
            self.raw_message_sdk = None
            self.user_id = user_id
            self.font = None
            self.sender = {}
            self.extend = {}
            if flag_lazy:
                self.sender['nickname'] = 'Nobody'
                self.extend['host_group_id'] = None

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


    def getBotIDStr(self):
        tmp_self_data = self.platform['platform']
        if self.base_info['self_id'] != None:
            tmp_self_data = '%s|%s' % (self.platform['platform'], str(self.base_info['self_id']))
        return tmp_self_data

    def callbackLogger(func_name = None, val_list = None):
        def callbackLoggerDecorator(func):
            @wraps(func)
            def funcWarpped(*args, **kwargs):
                warppedRes = func(*args, **kwargs)
                flag_log = True
                event_obj = None
                callback_msg = 'done'
                if 'flag_log' in kwargs:
                    flag_log = kwargs['flag_log']
                if len(args) >= 1:
                    event_obj = args[0]
                if flag_log and event_obj != None:
                    if warppedRes == None:
                        callback_msg = 'done'
                    elif warppedRes.__class__.__base__ == dict:
                        if 'active' in warppedRes:
                            if warppedRes['active'] == True:
                                if type(val_list) == list and 'data' in warppedRes:
                                    callback_msg_list = []
                                    for val_list_this in val_list:
                                        if val_list_this in warppedRes['data']:
                                            callback_msg_list.append(
                                                '%s(%s)' % (
                                                    val_list_this,
                                                    warppedRes['data'][val_list_this]
                                                )
                                            )
                                    callback_msg = ' '.join(callback_msg_list)
                                else:
                                    callback_msg = 'succeed'
                            else:
                                callback_msg = 'failed'
                        else:
                            callback_msg = 'done'
                    if event_obj.log_func != None:
                        event_obj.log_func(2, callback_msg , [
                            (event_obj.getBotIDStr(), 'default'),
                            (event_obj.plugin_info['name'], 'default'),
                            (func_name, 'callback')
                        ])
                return warppedRes
            return funcWarpped
        return callbackLoggerDecorator

    def __errorCatchLogger(self, e):
        self.log_func(3, str(e) , [
            (self.getBotIDStr(), 'default'),
            (self.plugin_info['name'], 'default'),
            ('error', 'callback')
        ])

    #以下为统一事件动作调用方法实现，各接入sdk需完全支持

    def __set_block(self, enable, flag_log = True):
        self.blocked = enable
        if flag_log and self.log_func != None:
            self.log_func(2, str(enable) , [
                (self.getBotIDStr(), 'default'),
                (self.plugin_info['name'], 'default'),
                ('set_block', 'callback')
            ])

    def set_block(self, enable: bool = True, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_block(enable, flag_log = True)

    def __message_router(self, message):
        tmp_message_obj = None
        tmp_message = None
        if type(message) == str and self.plugin_info['message_mode_tx'] == self.plugin_info['message_mode_rx']:
            tmp_message = message
            tmp_message_obj = OlivOS.messageAPI.Message_templet(
                self.plugin_info['message_mode_tx'],
                message
            )
        else:
            if type(message) == str or type(message) == list:
                tmp_message_obj = OlivOS.messageAPI.Message_templet(
                    self.plugin_info['message_mode_tx'],
                    message
                )
            elif type(message) == OlivOS.messageAPI.Message_templet:
                tmp_message_obj = message
            else:
                error_note = 'Wrong message type from plugin, please check your plugin first'
                error_obj = OlivOS.contentAPI.api_result_error_template.OlivOSTypeError(error_note)
                self.__errorCatchLogger(error_obj)
                raise error_obj
            if tmp_message_obj.active:
                tmp_message = tmp_message_obj.get(self.plugin_info['message_mode_rx'])
        return [tmp_message, tmp_message_obj]

    def __reply(self, message, flag_log = True):
        flag_type = None
        tmp_message = None
        tmp_message_obj = None
        tmp_message_log = None
        [tmp_message, tmp_message_obj] = self.__message_router(message)
        if tmp_message == None:
            return
        if checkByListOrEqual(
            self.plugin_info['func_type'],
            [
                'private_message',
                'friend_add',
                'private_message_recall',
                'friend_add_request'
            ]
        ):
            if 'host_group_id' in self.data.extend:
                self.__send('private', self.data.user_id, tmp_message, host_id = self.data.extend['host_group_id'], flag_log = False)
            else:
                self.__send('private', self.data.user_id, tmp_message, flag_log = False)
            flag_type = 'private'
        elif checkByListOrEqual(
            self.plugin_info['func_type'],
            [
                'group_message'
            ]
        ):
            self.__send('group', self.data.group_id, tmp_message, host_id = self.data.host_id, flag_log = False)
            flag_type = 'group'
        elif checkByListOrEqual(
            self.plugin_info['func_type'],
            [
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
            self.__send('group', self.data.group_id, tmp_message, flag_log = False)
            flag_type = 'group'
        elif checkByListOrEqual(
            self.plugin_info['func_type'],
            [
                'poke'
            ]
        ):
            if self.data.group_id == -1:
                self.__send('private', self.data.user_id, tmp_message, flag_log = False)
                flag_type = 'private'
            else:
                self.__send('group', self.data.group_id, tmp_message, flag_log = False)
                flag_type = 'group'

        if flag_log and self.log_func != None:
            if tmp_message_obj.active:
                tmp_message_log = tmp_message_obj.get(OlivOS.infoAPI.OlivOS_message_mode_tx_unity)
            else:
                tmp_message_log = tmp_message
            if flag_type == 'private':
                self.log_func(2, 'User(' + str(self.data.user_id) + '): ' + tmp_message_log, [
                    (self.getBotIDStr(), 'default'),
                    (self.plugin_info['name'], 'default'),
                    ('reply', 'callback')
                ])
            elif flag_type == 'group':
                if checkByListOrEqual(
                    self.plugin_info['func_type'],
                    [
                        'group_message'
                    ]
                ):
                    if self.data.host_id != None:
                        self.log_func(2, 'Host(' + str(self.data.host_id) + ') Group(' + str(self.data.group_id) + '): ' + tmp_message_log, [
                            (self.getBotIDStr(), 'default'),
                            (self.plugin_info['name'], 'default'),
                            ('reply', 'callback')
                        ])
                        return
                    else:
                        self.log_func(2, 'Group(' + str(self.data.group_id) + '): ' + tmp_message_log, [
                            (self.getBotIDStr(), 'default'),
                            (self.plugin_info['name'], 'default'),
                            ('reply', 'callback')
                        ])
                else:
                    self.log_func(2, 'Group(' + str(self.data.group_id) + '): ' + tmp_message_log, [
                        (self.getBotIDStr(), 'default'),
                        (self.plugin_info['name'], 'default'),
                        ('reply', 'callback')
                    ])

    def reply(self, message, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__reply(message, flag_log = True)


    def __send(self, send_type, target_id, message, host_id = None, flag_log = True):
        flag_type = send_type
        tmp_message = None
        tmp_message_obj = None
        tmp_message_log = None
        [tmp_message, tmp_message_obj] = self.__message_router(message)
        if tmp_message == None:
            return
        if self.platform['sdk'] == 'onebot':
            if flag_type == 'private':
                if 'host_id' in self.data.__dict__:
                    if self.data.host_id != None:
                        #此处缺少接口
                        pass
                    else:
                        OlivOS.onebotSDK.event_action.send_private_msg(self, target_id, tmp_message)
                else:
                    OlivOS.onebotSDK.event_action.send_private_msg(self, target_id, tmp_message)
            elif flag_type == 'group':
                if host_id != None:
                    OlivOS.onebotSDK.event_action.send_guild_channel_msg(self, host_id, target_id, tmp_message)
                else:
                    OlivOS.onebotSDK.event_action.send_group_msg(self, target_id, tmp_message)
        elif self.platform['sdk'] == 'qqGuild_link':
            if flag_type == 'group':
                if 'reply_msg_id' in self.data.extend:
                    OlivOS.qqGuildSDK.event_action.send_msg(self, target_id, tmp_message, self.data.extend['reply_msg_id'])
                else:
                    OlivOS.qqGuildSDK.event_action.send_msg(self, target_id, tmp_message)
            elif flag_type == 'private':
                if host_id != None and not flag_log:
                    OlivOS.qqGuildSDK.event_action.send_msg(self, host_id, tmp_message, self.data.extend['reply_msg_id'], flag_direct = True)
                elif 'flag_from_direct' in self.data.extend:
                    if self.data.extend['flag_from_direct']:
                        OlivOS.qqGuildSDK.event_action.send_msg(self, host_id, tmp_message, self.data.extend['reply_msg_id'], flag_direct = True)
                    else:
                        #主动私聊待实现
                        pass
                else:
                    #主动私聊待实现
                    pass
        elif self.platform['sdk'] == 'kaiheila_link':
            if flag_type == 'group':
                OlivOS.kaiheilaSDK.event_action.send_msg(self, target_id, tmp_message, flag_direct = False)
            elif flag_type == 'private':
                OlivOS.kaiheilaSDK.event_action.send_msg(self, target_id, tmp_message, flag_direct = True)
        elif self.platform['sdk'] == 'telegram_poll':
            OlivOS.telegramSDK.event_action.send_msg(self, target_id, tmp_message)
        elif self.platform['sdk'] == 'fanbook_poll':
            if flag_type == 'private':
                OlivOS.fanbookSDK.event_action.send_private_msg(self, target_id, tmp_message)
            elif flag_type == 'group':
                OlivOS.fanbookSDK.event_action.send_msg(self, target_id, tmp_message)
        elif self.platform['sdk'] == 'dodo_link':
            if flag_type == 'group':
                OlivOS.dodoLinkSDK.event_action.send_msg(self, target_id, tmp_message)
            elif flag_type == 'private':
                OlivOS.dodoLinkSDK.event_action.send_personal_msg(self, target_id, tmp_message)
        elif self.platform['sdk'] == 'dodo_poll':
            if flag_type == 'private':
                if host_id != None:
                    OlivOS.dodoSDK.event_action.send_private_msg(self, host_id, target_id, tmp_message)
                elif 'host_id' in self.data.__dict__:
                    OlivOS.dodoSDK.event_action.send_private_msg(self, self.data.host_id, target_id, tmp_message)
            elif flag_type == 'group':
                OlivOS.dodoSDK.event_action.send_msg(self, target_id, tmp_message)
        elif self.platform['sdk'] == 'dodobot_ea':
            if flag_type == 'group':
                tmp_send_msg = OlivOS.dodobotEASDK.event_action.send_msg(self, target_id, tmp_message)
                tx_packet_data = OlivOS.dodobotEATXAPI.server.rx_packet('send', tmp_send_msg)
                for tx_queue_this in self.plugin_info['tx_queue']:
                    tx_queue_this.put(tx_packet_data, block = False)

        if flag_log and self.log_func != None:
            if tmp_message_obj.active:
                tmp_message_log = tmp_message_obj.get(OlivOS.infoAPI.OlivOS_message_mode_tx_unity)
            else:
                tmp_message_log = tmp_message
            if flag_type == 'private':
                self.log_func(2, 'User(' + str(target_id) + '): ' + tmp_message_log, [
                    (self.getBotIDStr(), 'default'),
                    (self.plugin_info['name'], 'default'),
                    ('send', 'callback')
                ])
            elif flag_type == 'group':
                if host_id != None:
                    self.log_func(2, 'Host(' + str(host_id) + ') Group(' + str(target_id) + '): ' + tmp_message_log, [
                        (self.getBotIDStr(), 'default'),
                        (self.plugin_info['name'], 'default'),
                        ('send', 'callback')
                    ])
                else:
                    self.log_func(2, 'Group(' + str(target_id) + '): ' + tmp_message_log, [
                        (self.getBotIDStr(), 'default'),
                        (self.plugin_info['name'], 'default'),
                        ('send', 'callback')
                    ])

    def send(self, send_type: str, target_id: 'str|int', message, host_id: 'str|int|None' = None, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__send(send_type, target_id, message, host_id = host_id, flag_log = True)

    @callbackLogger('delete_msg')
    def __delete_msg(self, message_id, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            OlivOS.onebotSDK.event_action.delete_msg(self, message_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def delete_msg(self, message_id: 'str|int', flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__delete_msg(message_id, flag_log = True)

    @callbackLogger('get_msg')
    def __get_msg(self, message_id, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_msg(self, message_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        return res_data

    def get_msg(self, message_id: 'str|int', flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_msg(message_id, flag_log = True)
        return res_data


    @callbackLogger('send_like')
    def __send_like(self, user_id, times, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            OlivOS.onebotSDK.event_action.send_like(self, user_id, times)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def send_like(self, user_id: 'str|int', times: int = 1, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__send_like(user_id, times, flag_log = True)


    @callbackLogger('set_group_kick')
    def __set_group_kick(self, group_id, user_id, host_id, rehect_add_request, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_kick(self, group_id, user_id, rehect_add_request)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_kick(self, group_id: 'str|int', user_id: 'str|int', host_id: 'str|int|None' = None, rehect_add_request: bool = False, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_kick(group_id, user_id, host_id, rehect_add_request, flag_log = True)


    @callbackLogger('set_group_ban')
    def __set_group_ban(self, group_id, user_id, host_id, duration, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_ban(self, group_id, user_id, duration)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_ban(self, group_id: 'str|int', user_id: 'str|int', host_id: 'str|int|None' = None, duration: int = 1800, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_ban(group_id, user_id, host_id, duration, flag_log = True)


    @callbackLogger('set_group_anonymous_ban')
    def __set_group_anonymous_ban(self, group_id, anonymous, anonymous_flag, host_id, duration, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_anonymous_ban(self, group_id, anonymous, anonymous_flag, duration)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_anonymous_ban(self, group_id: 'str|int', anonymous, anonymous_flag: str, host_id: 'str|int|None' = None, duration: int = 1800, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_anonymous_ban(group_id, anonymous, anonymous_flag, host_id, duration, flag_log = True)


    @callbackLogger('set_group_whole_ban')
    def __set_group_whole_ban(self, group_id, enable, host_id, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_whole_ban(self, group_id, enable)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_whole_ban(self, group_id: 'str|int', enable: bool, host_id: 'str|int|None' = None, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_whole_ban(group_id, enable, host_id, flag_log = True)


    @callbackLogger('set_group_admin')
    def __set_group_admin(self, group_id, user_id, enable, host_id, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_admin(self, group_id, user_id, enable)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_admin(self, group_id: 'str|int', user_id: 'str|int', enable: bool, host_id: 'str|int|None' = None, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_admin(group_id, user_id, enable, host_id, flag_log = True)


    @callbackLogger('set_group_anonymous')
    def __set_group_anonymous(self, group_id, enable, host_id, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_anonymous(self, group_id, enable)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_anonymous(self, group_id: 'str|int', enable: bool, host_id: 'str|int' = None, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_anonymous(group_id, enable, host_id, flag_log = True)


    @callbackLogger('set_group_card')
    def __set_group_card(self, group_id, user_id, card, host_id, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_card(self, group_id, user_id, card)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_card(self, group_id: 'str|int', user_id: 'str|int', card, host_id: 'str|int|None' = None, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_card(group_id, user_id, card, host_id, flag_log = True)


    @callbackLogger('set_group_name')
    def __set_group_name(self, group_id, group_name, host_id, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_name(self, group_id, group_name)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_name(self, group_id: 'str|int', group_name: str, host_id: 'str|int|None' = None, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_name(group_id, group_name, host_id, flag_log = True)


    @callbackLogger('set_group_leave')
    def __set_group_leave(self, group_id, host_id, is_dismiss, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_leave(self, group_id, is_dismiss)
        elif self.platform['sdk'] == 'telegram_poll':
            OlivOS.telegramSDK.event_action.set_chat_leave(self, group_id, is_dismiss)

    def set_group_leave(self, group_id: 'str|int', host_id: 'str|int|None' = None, is_dismiss: bool = False, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_leave(group_id, host_id, is_dismiss, flag_log = True)


    @callbackLogger('set_group_special_title')
    def __set_group_special_title(self, group_id, user_id, special_title, duration, host_id, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                OlivOS.onebotSDK.event_action.set_group_special_title(self, group_id, user_id, special_title, duration)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_special_title(self, group_id: 'str|int', user_id: 'str|int', special_title: str, duration: int, host_id: 'str|int|None' = None, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_special_title(group_id, user_id, special_title, duration, host_id, flag_log = True)


    @callbackLogger('set_friend_add_request')
    def __set_friend_add_request(self, flag, approve, remark, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            OlivOS.onebotSDK.event_action.set_friend_add_request(self, flag, approve, remark)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_friend_add_request(self, flag: str, approve: bool, remark: str, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_friend_add_request(flag, approve, remark, flag_log = True)


    @callbackLogger('set_group_add_request')
    def __set_group_add_request(self, flag, sub_type, approve, reason, flag_log = True):
        if self.platform['sdk'] == 'onebot':
            OlivOS.onebotSDK.event_action.set_group_add_request(self, flag, sub_type, approve, reason)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_add_request(self, flag: str, sub_type: str, approve: bool, reason: str, flag_log: bool = True, remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_add_request(flag, sub_type, approve, reason, flag_log = True)


    def __get_login_info(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'telegram_poll':
            res_data = OlivOS.telegramSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'fanbook_poll':
            res_data = OlivOS.fanbookSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'qqGuild_link':
            res_data = OlivOS.qqGuildSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'kaiheila_link':
            res_data = OlivOS.kaiheilaSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'dodo_link':
            res_data = OlivOS.dodoLinkSDK.event_action.get_login_info(self)

        if res_data == None:
            return None

        if flag_log and self.log_func != None:
            if checkDictByListAnd(
                res_data, [
                    ['active'],
                    ['data', 'name'],
                    ['data', 'id']
                ]
            ):
                if res_data['active'] == True:
                    self.log_func(2, 'name(' + res_data['data']['name'] + ') id(' + str(res_data['data']['id']) + ')' , [
                        (self.getBotIDStr(), 'default'),
                        (self.plugin_info['name'], 'default'),
                        ('get_login_info', 'callback')
                    ])
                else:
                    self.log_func(2, 'failed' , [
                        (self.getBotIDStr(), 'default'),
                        (self.plugin_info['name'], 'default'),
                        ('get_login_info', 'callback')
                    ])
        return res_data

    def get_login_info(self, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_login_info(flag_log = True)
        return res_data


    @callbackLogger('get_stranger_info', ['name', 'id'])
    def __get_stranger_info(self, user_id, no_cache, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_stranger_info(self, user_id, no_cache)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'kaiheila_link':
            res_data = OlivOS.kaiheilaSDK.event_action.get_stranger_info(self, user_id)
        return res_data

    def get_stranger_info(self, user_id: 'str|int', no_cache: bool = False, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_stranger_info(user_id, no_cache, flag_log = True)
        return res_data


    @callbackLogger('get_friend_list')
    def __get_friend_list(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_friend_list(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        return res_data

    def get_friend_list(self, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_friend_list(flag_log = True)
        return res_data


    @callbackLogger('get_group_info', ['name', 'id'])
    def __get_group_info(self, group_id, host_id, no_cache, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                res_data = OlivOS.onebotSDK.event_action.get_group_info(self, group_id, no_cache)
        elif self.platform['sdk'] == 'telegram_poll':
            res_data = OlivOS.telegramSDK.event_action.get_group_info(self, group_id)
        return res_data

    def get_group_info(self, group_id: 'str|int', host_id: 'str|int|None' = None, no_cache: bool = False, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_info(group_id, host_id, no_cache, flag_log = True)
        return res_data


    @callbackLogger('get_group_list')
    def __get_group_list(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_group_list(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        return res_data

    def get_group_list(self, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_list(flag_log = True)
        return res_data


    @callbackLogger('get_group_member_info', ['name', 'id', 'group_id'])
    def __get_group_member_info(self, group_id, user_id, host_id, no_cache, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                res_data = OlivOS.onebotSDK.event_action.get_group_member_info(self, group_id, user_id, no_cache)
            else:
                res_data = OlivOS.onebotSDK.event_action.get_guild_member_profile(self, host_id, user_id)
        elif self.platform['sdk'] == 'telegram_poll':
            res_data = OlivOS.telegramSDK.event_action.get_group_member_info(self, group_id, user_id)
        elif self.platform['sdk'] == 'kaiheila_link':
            res_data = OlivOS.kaiheilaSDK.event_action.get_group_member_info(self, host_id, user_id)
        return res_data

    def get_group_member_info(self, group_id: 'str|int', user_id: 'str|int', host_id: 'str|int|None' = None, no_cache: bool = False, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_member_info(group_id, user_id, host_id, no_cache, flag_log = True)
        return res_data


    @callbackLogger('get_group_member_list')
    def __get_group_member_list(self, group_id, host_id, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if host_id == None:
                res_data = OlivOS.onebotSDK.event_action.get_group_member_list(self, group_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        return res_data

    def get_group_member_list(self, group_id: 'str|int', host_id: 'str|int|None' = None, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_member_list(group_id, host_id, flag_log = True)
        return res_data


    @callbackLogger('can_send_image')
    def __can_send_image(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.can_send_image(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        return res_data

    def can_send_image(self, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__can_send_image(flag_log = True)
        return res_data


    @callbackLogger('can_send_record')
    def __can_send_record(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.can_send_record(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        return res_data

    def can_send_record(self, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__can_send_record(flag_log = True)
        return res_data


    @callbackLogger('get_status')
    def __get_status(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_status(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        return res_data

    def get_status(self, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_status(flag_log = True)
        return res_data


    @callbackLogger('get_version_info')
    def __get_version_info(self, flag_log = True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            res_data = OlivOS.onebotSDK.event_action.get_version_info(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        return res_data

    def get_version_info(self, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_version_info(flag_log = True)
        return res_data

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
        #self.Proc = proc_this
        return proc_this

    def start_lite(self):
        proc_this = StoppableThread(name = self.Proc_name, target = self.run, args = ())
        proc_this.daemon = self.deamon
        proc_this.start()
        #self.Proc = proc_this
        return proc_this
    
    def start_unity(self, mode = 'threading'):
        proc_this = None
        if mode == 'processing':
            proc_this = self.start()
        elif mode == 'threading':
            proc_this = self.start_lite()
        return proc_this

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
