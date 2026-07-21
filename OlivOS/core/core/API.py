# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/API.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

import sys
import multiprocessing
import threading
import hashlib
import time
import traceback
import inspect
import ctypes
import html
import os

from functools import wraps
from urllib import parse

import OlivOS
from OlivOS.core.info.infoAPI import OlivOS_Version  # noqa

mod_global_name = sys.modules[__name__]


class Control(object):
    def __init__(self, name, init_list, control_queue, scan_interval):
        self.name = name
        self.init_list = init_list
        self.control_queue = control_queue
        self.scan_interval = scan_interval

    class packet(object):
        def __init__(self, action, key=None):
            self.action = action
            self.key = key


class bot_info_T(object):
    def __init__(self, id=-1, password='', server_type='post', server_auto=False, host='', port=-1, access_token=None,
                 platform_sdk=None, platform_platform=None, platform_model=None):
        self.id = id
        self.password = password
        self.platform = {'sdk': platform_sdk, 'platform': platform_platform, 'model': platform_model}
        self.hash = None
        self.post_info = self.post_info_T(
            server_auto=server_auto,
            server_type=server_type,
            host=host,
            port=port,
            access_token=access_token
        )
        self.extends = {}
        self.debug_mode = False
        self.getHash()

    class post_info_T(object):
        def __init__(self, host='', port=-1, access_token=None, server_type='post', server_auto=False):
            self.auto = server_auto
            self.type = server_type
            self.host = host
            self.port = port
            self.access_token = access_token

    def getHash(self):
        self.hash = getBotHash(
            bot_id=self.id,
            platform_sdk=self.platform['sdk'],
            platform_platform=self.platform['platform'],
            platform_model=self.platform['model']
        )


def getBotHash(bot_id=None, platform_sdk=None, platform_platform=None, platform_model=None):
    hash_tmp = hashlib.new('md5')
    hash_tmp.update(str(bot_id).encode(encoding='UTF-8'))
    hash_tmp.update(str(platform_sdk).encode(encoding='UTF-8'))
    hash_tmp.update(str(platform_platform).encode(encoding='UTF-8'))
    # hash_tmp.update(str(platform_model).encode(encoding='UTF-8'))
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
        if type(target_event.sdk_event.key) is dict:
            if 'data' in target_event.sdk_event.key:
                if 'action' in target_event.sdk_event.key['data']:
                    if 'plugin_menu' == target_event.sdk_event.key['data']['action']:
                        target_event.active = True
                        target_event.plugin_info['func_type'] = 'menu'
                        target_event.data = target_event.menu(
                            namespace=target_event.sdk_event.key['data']['namespace'],
                            event=target_event.sdk_event.key['data']['event']
                        )
    pass


class inde_interface_T(object):
    def __init__(self, event, platform: str):
        self.platform = platform
        self.event = event

    def hasAPI(self, api_name):
        res = False
        if hasattr(self, api_name):
            res = True
        return res


class Event(object):
    def __init__(self, sdk_event=None, log_func=None, Proc=None):
        self.bot_info = None
        self.platform = {
            'sdk': None,
            'platform': None,
            'model': None
        }
        self.data = None
        self.active = False
        self.blocked = False
        self.log_func = log_func
        self.base_info = {
            'time': None,
            'self_id': None,
            'type': None
        }
        self.plugin_info = {
            'func_type': None,
            'message_mode_rx': OlivOS.infoAPI.OlivOS_message_mode_rx_default,
            'message_mode_tx': OlivOS.infoAPI.OlivOS_message_mode_tx_unity,
            'name': 'unity',
            'namespace': 'unity',
            'tx_queue': [],
            'control_queue': None
        }
        self.sdk_event = sdk_event
        self.sdk_event_type = type(self.sdk_event)
        if type(OlivOS.pluginAPI.gProc) is OlivOS.pluginAPI.shallow:
            self.plugin_info['control_queue'] = OlivOS.pluginAPI.gProc.Proc_info.control_queue
            self.log_func = OlivOS.pluginAPI.gProc.log
        if (
            self.plugin_info['control_queue'] is None
            and type(Proc) is OlivOS.pluginAPI.shallow
        ):
            self.plugin_info['control_queue'] = Proc.Proc_info.control_queue
        if type(self.log_func) is None:
            self.log_func = Proc.log
        self.indeAPI = None
        self.get_Event_from_SDK()
        self.get_Event_on_Plugin()
        self.__init_inde_interface()
        self.do_init_log()

    def __init_inde_interface(self):
        self.indeAPI = inde_interface_T(self, self.platform['platform'])
        if self.platform['sdk'] == 'kaiheila_link':
            self.indeAPI = OlivOS.kaiheilaSDK.inde_interface(self, self.platform['platform'])
        if self.platform['sdk'] == 'qqGuildv2_link':
            self.indeAPI = OlivOS.qqGuildv2SDK.inde_interface(self, self.platform['platform'])
        if self.platform['sdk'] == 'mhyVila_link':
            self.indeAPI = OlivOS.mhyVilaSDK.inde_interface(self, self.platform['platform'])

    def get_Event_from_SDK(self):
        if self.sdk_event_type is OlivOS.virtualTerminalSDK.event:
            OlivOS.virtualTerminalSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.onebotV12SDK.event:
            OlivOS.onebotV12SDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.onebotSDK.event:
            OlivOS.onebotSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.qqGuildSDK.event:
            OlivOS.qqGuildSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.qqGuildv2SDK.event:
            OlivOS.qqGuildv2SDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.discordSDK.event:
            OlivOS.discordSDK.get_Event_from_SDK(self)
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
        elif self.sdk_event_type is OlivOS.xiaoheiheSDK.event:
            OlivOS.xiaoheiheSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.mhyVilaSDK.event:
            OlivOS.mhyVilaSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.qqRedSDK.event:
            OlivOS.qqRedSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.hackChatSDK.event:
            OlivOS.hackChatSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.OPQBotSDK.event:
            OlivOS.OPQBotSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.dingtalkSDK.event:
            OlivOS.dingtalkSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.biliLiveSDK.event:
            OlivOS.biliLiveSDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.milkySDK.event:
            OlivOS.milkySDK.get_Event_from_SDK(self)
        elif self.sdk_event_type is OlivOS.API.Control.packet:
            getMenuEvent(self)

    def get_Event_on_Plugin(self):
        if self.plugin_info['func_type'] in [
            'private_message',
            'private_message_sent',
            'group_message',
            'group_message_sent'
        ]:
            compatible_svn = self.plugin_info.get('compatible_svn', OlivOS.infoAPI.OlivOS_compatible_svn_default)
            # 如果插件版本小于OlivOS_SVN_Compatible，需要从at部分移除name
            # 这里选择创建一个临时副本，避免共用
            if compatible_svn < OlivOS.infoAPI.OlivOS_SVN_Compatible:
                if self.data.message_sdk is not None and hasattr(self.data.message_sdk, 'data'):
                    temp_message_sdk = OlivOS.messageAPI.Message_templet(
                        self.data.message_sdk.mode_rx,
                        self.data.message_sdk.data_raw
                    )
                    # 从at部分移除name
                    for para_this in temp_message_sdk.data:
                        if type(para_this) is OlivOS.messageAPI.PARA.at:
                            if 'name' in para_this.data:
                                new_data = para_this.data.copy()
                                del new_data['name']
                                para_this.data = new_data
                    # 使用临时副本生成消息
                    if (
                        self.plugin_info['message_mode_tx'] == 'olivos_para'
                        or temp_message_sdk.mode_rx != self.plugin_info['message_mode_tx']
                    ):
                        self.data.message = temp_message_sdk.get(self.plugin_info['message_mode_tx'])
                        self.data.raw_message = temp_message_sdk.get(self.plugin_info['message_mode_tx'])
                    else:
                        self.data.message = temp_message_sdk.data_raw
                        self.data.raw_message = temp_message_sdk.data_raw
                else:
                    # 如果message_sdk不存在（通常不会发生），使用原始逻辑
                    if (
                        self.plugin_info['message_mode_tx'] == 'olivos_para'
                        or self.data.message_sdk.mode_rx != self.plugin_info['message_mode_tx']
                    ):
                        self.data.message = self.data.message_sdk.get(self.plugin_info['message_mode_tx'])
                        self.data.raw_message = self.data.raw_message_sdk.get(self.plugin_info['message_mode_tx'])
                    else:
                        self.data.message = self.data.message_sdk.data_raw
                        self.data.raw_message = self.data.raw_message_sdk.data_raw
            else:
                # 插件版本大于等于OlivOS_SVN_Compatible，保持原始逻辑
                if (
                    self.plugin_info['message_mode_tx'] == 'olivos_para'
                    or self.data.message_sdk.mode_rx != self.plugin_info['message_mode_tx']
                ):
                    self.data.message = self.data.message_sdk.get(self.plugin_info['message_mode_tx'])
                    self.data.raw_message = self.data.raw_message_sdk.get(self.plugin_info['message_mode_tx'])
                else:
                    self.data.message = self.data.message_sdk.data_raw
                    self.data.raw_message = self.data.raw_message_sdk.data_raw
        # 转换html实例
        self._normalize_message_entities()

    def _html_unescape_if_str(self, value):
        if isinstance(value, str):
            return html.unescape(value)
        return value

    def _normalize_message_entities(self):
        if self.data is None:
            return
        if hasattr(self.data, 'message'):
            self.data.message = self._html_unescape_if_str(self.data.message)
        if hasattr(self.data, 'raw_message'):
            self.data.raw_message = self._html_unescape_if_str(self.data.raw_message)

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
            elif self.plugin_info['func_type'] == 'private_message_sent':
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['nickname', self.data.sender['nickname']],
                    ['user_id', self.data.user_id],
                    ['message', self.data.message]
                ])
            elif self.plugin_info['func_type'] == 'group_message':
                tmp_host_id = '-'
                if self.data.host_id is not None:
                    tmp_host_id = str(self.data.host_id)
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['host_id', tmp_host_id],
                    ['group_id', self.data.group_id],
                    ['nickname', self.data.sender['nickname']],
                    ['user_id', self.data.user_id],
                    ['message', self.data.message]
                ])
            elif self.plugin_info['func_type'] == 'group_message_sent':
                tmp_host_id = '-'
                if self.data.host_id is not None:
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
                tmp_host_id = '-'
                if hasattr(self.data, 'host_id') and self.data.host_id is not None:
                    tmp_host_id = str(self.data.host_id)
                tmp_group_id = '-'
                if self.data.group_id is not None:
                    tmp_group_id = str(self.data.group_id)
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['host_id', tmp_host_id],
                    ['group_id', tmp_group_id],
                    ['user_id', self.data.user_id],
                    ['operator_id', self.data.operator_id],
                    ['action', self.data.action]
                ])
            elif self.plugin_info['func_type'] == 'group_member_increase':
                tmp_host_id = '-'
                if hasattr(self.data, 'host_id') and self.data.host_id is not None:
                    tmp_host_id = str(self.data.host_id)
                tmp_group_id = '-'
                if self.data.group_id is not None:
                    tmp_group_id = str(self.data.group_id)
                tmp_globalMetaTableTemp_patch = OlivOS.metadataAPI.getPairMapping([
                    ['host_id', tmp_host_id],
                    ['group_id', tmp_group_id],
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
                    src_table=OlivOS.metadataAPI.globalMetaTable,
                    fwd_key=OlivOS.metadataAPI.eventLogMetaTable[self.plugin_info['func_type']]['message_key'],
                    format_patch=tmp_globalMetaTableTemp_patch,
                    default_res=tmp_log_message_default
                )
            else:
                tmp_log_level = 3
                tmp_log_message = tmp_log_message_default
            if self.log_func is not None:
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
        def __init__(self, user_id, message, sub_type, flag_lazy=True):
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

    class private_message_sent(object):
        def __init__(self, user_id, message, sub_type, flag_lazy=True):
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
        def __init__(self, group_id, user_id, message, sub_type, flag_lazy=True):
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
                self.sender['name'] = 'Nobody'
                self.extend['host_group_id'] = None

    class group_message_sent(object):
        def __init__(self, group_id, user_id, message, sub_type, flag_lazy=True):
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
        def __init__(self, group_id, user_id, flag_lazy=True):
            self.group_id = group_id
            self.user_id = user_id
            self.file = {}
            if flag_lazy:
                self.file['id'] = 'Nofileid'
                self.file['name'] = 'Nofile'
                self.file['size'] = 0
                self.file['busid'] = -1

    class group_admin(object):
        def __init__(self, group_id, user_id, flag_lazy=True):
            self.group_id = group_id
            self.user_id = user_id
            self.action = 'unset'

    class group_member_decrease(object):
        def __init__(self, group_id, operator_id, user_id, host_id=None, action='leave', flag_lazy=True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.action = action
            self.host_id = host_id

    class group_member_increase(object):
        def __init__(self, group_id, operator_id, user_id, host_id=None, action='approve', flag_lazy=True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.action = action
            self.host_id = host_id

    class group_ban(object):
        def __init__(self, group_id, operator_id, user_id, duration, action='unban', flag_lazy=True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.duration = duration
            self.action = action

    class friend_add(object):
        def __init__(self, user_id, flag_lazy=True):
            self.user_id = user_id

    class group_message_recall(object):
        def __init__(self, group_id, operator_id, user_id, message_id, flag_lazy=True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.message_id = message_id

    class private_message_recall(object):
        def __init__(self, user_id, message_id, flag_lazy=True):
            self.user_id = user_id
            self.message_id = message_id

    class poke(object):
        def __init__(self, user_id, target_id, group_id='-1', flag_lazy=True):
            self.group_id = group_id
            self.user_id = user_id
            self.target_id = target_id

    class group_lucky_king(object):
        def __init__(self, group_id, user_id, target_id, flag_lazy=True):
            self.group_id = group_id
            self.user_id = user_id
            self.target_id = target_id

    class group_honor(object):
        def __init__(self, group_id, user_id, flag_lazy=True):
            self.group_id = group_id
            self.user_id = user_id
            self.type = None

    class friend_add_request(object):
        def __init__(self, user_id, comment='', flag_lazy=True):
            self.user_id = user_id
            self.comment = comment
            self.flag = None

    class group_add_request(object):
        def __init__(self, group_id, user_id, comment='', flag_lazy=True):
            self.group_id = group_id
            self.user_id = user_id
            self.comment = comment
            self.flag = None

    class group_invite_request(object):
        def __init__(self, group_id, user_id, comment='', flag_lazy=True):
            self.group_id = group_id
            self.user_id = user_id
            self.comment = comment
            self.flag = None

    class lifecycle(object):
        def __init__(self, action=None, flag_lazy=True):
            self.action = action

    class heartbeat(object):
        def __init__(self, interval, flag_lazy=True):
            self.interval = interval

    def getBotIDStr(self):
        tmp_self_data = self.platform['platform']
        if self.base_info['self_id'] is not None:
            tmp_self_data = '%s|%s' % (self.platform['platform'], str(self.base_info['self_id']))
        return tmp_self_data

    def callbackLogger(func_name=None, val_list=None):
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
                if flag_log and event_obj is not None:
                    if warppedRes is None:
                        callback_msg = 'done'
                    elif not (warppedRes.__class__.__base__ is dict):
                        pass
                    elif not ('active' in warppedRes):
                        callback_msg = 'done'
                    elif not (warppedRes['active'] is True):
                        callback_msg = 'failed'
                    elif not (type(val_list) is list and 'data' in warppedRes):
                        callback_msg = 'succeed'
                    else:
                        callback_msg_list = []
                        for val_list_this in val_list:
                            if val_list_this in warppedRes['data']:
                                callback_msg_list.append(
                                    '%s(%s)' % (
                                        val_list_this,
                                        str(warppedRes['data'][val_list_this])
                                    )
                                )
                        callback_msg = ' '.join(callback_msg_list)
                    if event_obj.log_func is not None:
                        event_obj.log_func(2, callback_msg, [
                            (event_obj.getBotIDStr(), 'default'),
                            (event_obj.plugin_info['name'], 'default'),
                            (func_name, 'callback')
                        ])
                return warppedRes

            return funcWarpped

        return callbackLoggerDecorator

    def __errorCatchLogger(self, e):
        self.log_func(3, str(e), [
            (self.getBotIDStr(), 'default'),
            (self.plugin_info['name'], 'default'),
            ('error', 'callback')
        ])

    # 以下为统一事件动作调用方法实现，各接入sdk需完全支持

    def __set_block(self, enable, flag_log=True):
        self.blocked = enable
        if flag_log and self.log_func is not None:
            self.log_func(2, str(enable), [
                (self.getBotIDStr(), 'default'),
                (self.plugin_info['name'], 'default'),
                ('set_block', 'callback')
            ])

    def set_block(self, enable: bool = True, flag_log: bool = True, remote: bool = False):
        """阻塞后续插件

        用于就此阻塞丢弃该消息事件而不传递给后续插件处理

        Args:
            enable: 阻塞状态 (default: True)
        """
        if remote:
            pass
        else:
            self.__set_block(enable, flag_log=True)

    def __message_router(self, message):
        tmp_message_obj = None
        tmp_message = None
        if (
            type(message) is str
            or type(message) is list
        ):
            tmp_message_obj = OlivOS.messageAPI.Message_templet(
                self.plugin_info['message_mode_tx'],
                message
            )
        elif type(message) is OlivOS.messageAPI.Message_templet:
            tmp_message_obj = message
        else:
            error_note = 'Wrong message type from plugin, please check your plugin first'
            error_obj = OlivOS.contentAPI.api_result_error_template.OlivOSTypeError(error_note)
            self.__errorCatchLogger(error_obj)
            raise error_obj
        if tmp_message_obj.active:
            tmp_message = tmp_message_obj.get(self.plugin_info['message_mode_rx'])
        return [tmp_message, tmp_message_obj]

    def __support_file_segment_upload(self, send_type, host_id=None):
        if send_type not in ['private', 'group']:
            return False
        if host_id is not None:
            return False
        if self.platform['sdk'] == 'milky':
            return self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList
        if self.platform['sdk'] != 'onebot':
            return False
        return (
            self.platform['model'] in OlivOS.flaskServerAPI.gCheckList
            or self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList
            or self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList
        )

    def __get_file_segment_data(self, message_para):
        file_data = message_para.data
        if not isinstance(file_data, dict):
            return None, None
        file_resource = None
        for data_key in ['path', 'url', 'file']:
            data_value = file_data.get(data_key)
            if data_value is None:
                continue
            data_value = str(data_value)
            if data_value not in ['', 'None']:
                file_resource = data_value
                break
        if file_resource is None:
            return None, None

        resource_parsed = parse.urlparse(file_resource)
        if resource_parsed.scheme == '' and not os.path.isabs(file_resource):
            file_resource = OlivOS.contentAPI.resourcePathTransform('files', file_resource)

        file_name = file_data.get('name')
        if file_name is not None and str(file_name) not in ['', 'None']:
            return file_resource, str(file_name)
        resource_parsed = parse.urlparse(file_resource)
        if resource_parsed.scheme in ['base64', 'data']:
            return file_resource, 'file'
        resource_path = parse.unquote(resource_parsed.path)
        file_name = resource_path.replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]
        if file_name == '':
            file_name = 'file'
        return file_resource, file_name

    def __send_file_segments(self, send_type, target_id, message_obj, host_id=None, flag_log=True):
        if not self.__support_file_segment_upload(send_type, host_id):
            return False
        if not any(isinstance(para, OlivOS.messageAPI.PARA.file) for para in message_obj.data):
            return False

        message_buffer = []

        def flush_message_buffer():
            if len(message_buffer) == 0:
                return
            message_chunk = OlivOS.messageAPI.Message_templet('olivos_para', message_buffer.copy())
            self.__send(
                send_type,
                target_id,
                message_chunk,
                host_id=host_id,
                flag_log=flag_log
            )
            message_buffer.clear()

        for message_para in message_obj.data:
            if not isinstance(message_para, OlivOS.messageAPI.PARA.file):
                message_buffer.append(message_para)
                continue
            flush_message_buffer()
            file_resource, file_name = self.__get_file_segment_data(message_para)
            if file_resource is None:
                continue
            if send_type == 'group':
                self.__upload_group_file(
                    target_id,
                    file_resource,
                    name=file_name,
                    flag_log=flag_log
                )
            else:
                self.__upload_private_file(
                    target_id,
                    file_resource,
                    file_name,
                    flag_log=flag_log
                )
        flush_message_buffer()
        return True

    def __reply(self, message, flag_log=True):
        flag_type = None
        tmp_message = None
        tmp_message_obj = None
        tmp_message_log = None
        [tmp_message, tmp_message_obj] = self.__message_router(message)
        tmp_message = message
        if tmp_message is None:
            return
        if checkByListOrEqual(
                self.plugin_info['func_type'],
                [
                    'private_message_sent',
                    'private_message',
                    'friend_add',
                    'private_message_recall',
                    'friend_add_request'
                ]
        ):
            if (
                hasattr(self.data, 'extend')
                and 'host_group_id' in self.data.extend
            ):
                self.__send('private', self.data.user_id, tmp_message, host_id=self.data.extend['host_group_id'],
                            flag_log=False)
            else:
                self.__send('private', self.data.user_id, tmp_message, flag_log=False)
            flag_type = 'private'
        elif checkByListOrEqual(
                self.plugin_info['func_type'],
                [
                    'group_message_sent',
                    'group_message'
                ]
        ):
            self.__send('group', self.data.group_id, tmp_message, host_id=self.data.host_id, flag_log=False)
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
            self.__send('group', self.data.group_id, tmp_message, flag_log=False)
            flag_type = 'group'
        elif checkByListOrEqual(
                self.plugin_info['func_type'],
                [
                    'poke'
                ]
        ):
            if self.data.group_id in [-1, '-1', None]:
                self.__send('private', self.data.user_id, tmp_message, flag_log=False)
                flag_type = 'private'
            else:
                self.__send('group', self.data.group_id, tmp_message, flag_log=False)
                flag_type = 'group'

        if flag_log and self.log_func is not None:
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
                            'group_message_sent',
                            'group_message'
                        ]
                ):
                    if self.data.host_id is not None:
                        self.log_func(2, 'Host(' + str(self.data.host_id) + ') Group(' + str(
                            self.data.group_id) + '): ' + tmp_message_log, [
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
        """回复消息

        用于快速原路回复消息

        Args:
            message: 所需要发送的消息
        """
        if remote:
            pass
        else:
            self.__reply(message, flag_log=True)

    def __send(self, send_type, target_id, message, host_id=None, flag_log=True):
        flag_type = send_type
        tmp_message = None
        tmp_message_obj = None
        tmp_message_log = None
        [tmp_message, tmp_message_obj] = self.__message_router(message)
        if tmp_message is None:
            return
        if self.__send_file_segments(
            flag_type,
            target_id,
            tmp_message_obj,
            host_id=host_id,
            flag_log=flag_log
        ):
            return
        if self.platform['sdk'] == 'terminal_link':
            OlivOS.virtualTerminalSDK.event_action.send_msg(
                self,
                tmp_message,
                self.plugin_info['control_queue'],
                flag_type=flag_type,
                target_id=target_id
            )
        elif self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                if flag_type == 'private':
                    if (
                        'host_id' in self.data.__dict__
                        and self.data.host_id is not None
                    ):
                        # 此处缺少接口
                        pass
                    else:
                        OlivOS.onebotV12SDK.event_action.send_private_msg(self, target_id, tmp_message)
                elif flag_type == 'group':
                    if host_id is not None:
                        OlivOS.onebotV12SDK.event_action.send_host_msg(self, host_id, target_id, tmp_message)
                    else:
                        OlivOS.onebotV12SDK.event_action.send_group_msg(self, target_id, tmp_message)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if flag_type == 'private':
                    if (
                        'host_id' in self.data.__dict__
                        and self.data.host_id is not None
                    ):
                        # 此处缺少接口
                        pass
                    else:
                        OlivOS.onebotSDK.event_action.send_private_msg(self, target_id, tmp_message)
                elif flag_type == 'group':
                    if host_id is not None:
                        OlivOS.onebotSDK.event_action.send_guild_channel_msg(self, host_id, target_id, tmp_message)
                    else:
                        OlivOS.onebotSDK.event_action.send_group_msg(self, target_id, tmp_message)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if flag_type == 'private':
                    if (
                        'host_id' in self.data.__dict__
                        and self.data.host_id is not None
                    ):
                        # 此处缺少接口
                        pass
                    else:
                        OlivOS.onebotSDK.event_action.send_private_msg(self, target_id, tmp_message)
                elif flag_type == 'group':
                    if host_id is not None:
                        OlivOS.onebotSDK.event_action.send_guild_channel_msg(self, host_id, target_id, tmp_message)
                    else:
                        OlivOS.onebotSDK.event_action.send_group_msg(self, target_id, tmp_message)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if flag_type == 'private':
                    if (
                        'host_id' in self.data.__dict__
                        and self.data.host_id is not None
                    ):
                        # 此处缺少接口
                        pass
                    else:
                        OlivOS.onebotSDK.event_action.send_private_msg(self, target_id, tmp_message)
                elif flag_type == 'group':
                    if host_id is not None:
                        OlivOS.onebotSDK.event_action.send_guild_channel_msg(self, host_id, target_id, tmp_message)
                    else:
                        OlivOS.onebotSDK.event_action.send_group_msg(self, target_id, tmp_message)
            elif self.platform['model'] in OlivOS.qqRedLinkServerAPI.gCheckList:
                if flag_type == 'private':
                    OlivOS.qqRedSDK.event_action.send_msg(
                        self, 1, target_id, tmp_message, self.plugin_info['control_queue']
                    )
                elif flag_type == 'group':
                    OlivOS.qqRedSDK.event_action.send_msg(
                        self, 2, target_id, tmp_message, self.plugin_info['control_queue']
                    )
            elif self.platform['model'] in OlivOS.OPQBotLinkServerAPI.gCheckList:
                if flag_type == 'private':
                    OlivOS.OPQBotSDK.event_action.send_msg(
                        self, 'private', target_id, tmp_message, self.plugin_info['control_queue']
                    )
                elif flag_type == 'group':
                    OlivOS.OPQBotSDK.event_action.send_msg(
                        self, 'group', target_id, tmp_message, self.plugin_info['control_queue']
                    )
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                if flag_type == 'private':
                    OlivOS.milkySDK.event_action.send_private_msg(self, target_id, tmp_message)
                elif flag_type == 'group':
                    OlivOS.milkySDK.event_action.send_group_msg(self, target_id, tmp_message)
        elif self.platform['sdk'] == 'qqGuild_link':
            if flag_type == 'group':
                if (
                    hasattr(self.data, 'extend')
                    and 'reply_msg_id' in self.data.extend
                ):
                    OlivOS.qqGuildSDK.event_action.send_msg(
                        self, target_id, tmp_message, self.data.extend['reply_msg_id']
                    )
                else:
                    OlivOS.qqGuildSDK.event_action.send_msg(self, target_id, tmp_message)
            elif flag_type == 'private':
                if (
                    hasattr(self.data, 'extend')
                    and host_id is not None and not flag_log
                ):
                    OlivOS.qqGuildSDK.event_action.send_msg(
                        self, host_id, tmp_message, self.data.extend['reply_msg_id'], flag_direct=True
                    )
                elif (
                    hasattr(self.data, 'extend')
                    and 'flag_from_direct' in self.data.extend
                ):
                    if (
                        hasattr(self.data, 'extend')
                        and self.data.extend['flag_from_direct']
                    ):
                        OlivOS.qqGuildSDK.event_action.send_msg(
                            self, host_id, tmp_message, self.data.extend['reply_msg_id'], flag_direct=True
                        )
                    else:
                        # 主动私聊待实现
                        pass
                else:
                    # 主动私聊待实现
                    pass
        elif self.platform['sdk'] == 'qqGuildv2_link':
            if (
                hasattr(self.data, 'extend')
                and self.data.extend.get('flag_from_qq', False)
            ):
                if flag_type == 'group':
                    if (
                        hasattr(self.data, 'extend')
                        and 'reply_msg_id' in self.data.extend
                    ):
                        OlivOS.qqGuildv2SDK.event_action.send_qq_msg(
                            self, target_id, tmp_message, self.data.extend['reply_msg_id']
                        )
                    else:
                        OlivOS.qqGuildv2SDK.event_action.send_qq_msg(self, target_id, tmp_message)
                elif flag_type == 'private':
                    if (
                        hasattr(self.data, 'extend')
                        and 'flag_from_direct' in self.data.extend
                    ):
                        if self.data.extend['flag_from_direct']:
                            OlivOS.qqGuildv2SDK.event_action.send_qq_msg(
                                self, target_id, tmp_message, self.data.extend['reply_msg_id'], flag_direct=True
                            )
                        else:
                            # 主动私聊待实现
                            pass
                    else:
                        # 主动私聊待实现
                        pass
            else:
                if flag_type == 'group':
                    if (
                        hasattr(self.data, 'extend')
                        and 'reply_msg_id' in self.data.extend
                    ):
                        OlivOS.qqGuildv2SDK.event_action.send_msg(
                            self, target_id, tmp_message, self.data.extend['reply_msg_id']
                        )
                    else:
                        OlivOS.qqGuildv2SDK.event_action.send_msg(self, target_id, tmp_message)
                elif flag_type == 'private':
                    if (
                        hasattr(self.data, 'extend')
                        and host_id is not None
                    ):
                        OlivOS.qqGuildv2SDK.event_action.send_msg(
                            self, host_id, tmp_message, self.data.extend['reply_msg_id'], flag_direct=True
                        )
                    elif (
                        hasattr(self.data, 'extend')
                        and 'flag_from_direct' in self.data.extend
                        and 'reply_msg_id' in self.data.extend
                    ):
                        if self.data.extend['flag_from_direct']:
                            OlivOS.qqGuildv2SDK.event_action.send_msg(
                                self, host_id, tmp_message, self.data.extend['reply_msg_id'], flag_direct=True
                            )
                        else:
                            # 主动私聊待实现
                            pass
                    else:
                        # 主动私聊待实现
                        pass
        elif self.platform['sdk'] == 'discord_link':
            if flag_type == 'group':
                OlivOS.discordSDK.event_action.send_msg(self, target_id, tmp_message)
            elif flag_type == 'private':
                OlivOS.discordSDK.event_action.send_msg(self, target_id, tmp_message, flag_direct=True)
        elif self.platform['sdk'] == 'kaiheila_link':
            if flag_type == 'group':
                OlivOS.kaiheilaSDK.event_action.send_msg(self, target_id, tmp_message, flag_direct=False)
            elif flag_type == 'private':
                OlivOS.kaiheilaSDK.event_action.send_msg(self, target_id, tmp_message, flag_direct=True)
        elif self.platform['sdk'] == 'xiaoheihe_link':
            if flag_type == 'group':
                OlivOS.xiaoheiheSDK.event_action.send_msg(self, target_id, host_id, tmp_message, flag_direct=False)
            elif flag_type == 'private':
                pass
        elif self.platform['sdk'] == 'mhyVila_link':
            if flag_type == 'group':
                if host_id is not None:
                    OlivOS.mhyVilaSDK.event_action.send_group_msg(self, target_id, tmp_message, host_id=host_id)
                elif 'host_id' in self.data.__dict__:
                    OlivOS.mhyVilaSDK.event_action.send_group_msg(
                        self, target_id, tmp_message, host_id=self.data.host_id
                    )
            elif flag_type == 'private':
                pass
        elif self.platform['sdk'] == 'hackChat_link':
            OlivOS.hackChatSDK.event_action.send_msg(self, tmp_message, self.plugin_info['control_queue'])
        elif self.platform['sdk'] == 'biliLive_link':
            OlivOS.biliLiveSDK.event_action.send_msg(self, tmp_message, self.plugin_info['control_queue'])
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
                if host_id is not None:
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
                    tx_queue_this.put(tx_packet_data, block=False)
        elif self.platform['sdk'] == 'dingtalk_link':
            OlivOS.dingtalkSDK.event_action.send_msg(self, flag_type, target_id, tmp_message)

        if flag_log and self.log_func is not None:
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
                if host_id is not None:
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

    def send(self, send_type: str, target_id: 'str|int', message, host_id: 'str|int|None' = None, flag_log: bool = True,
             remote: bool = False):
        """发送消息

        用于发送消息

        Args:
            send_type: 用于指定发送目标的类型
            target_id: 发送目标的ID
            message: 所需要发送的消息
            host_id: 发送目标的所属HOST ID (default: None)
        """
        if remote:
            pass
        else:
            self.__send(send_type, target_id, message, host_id=host_id, flag_log=True)

    @callbackLogger('delete_msg')
    def __delete_msg(self, message_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                OlivOS.onebotV12SDK.event_action.delete_msg(self, message_id)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_msg(self, message_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.delete_msg(self, message_id)
        elif self.platform['sdk'] == 'qqGuildv2_link':
            OlivOS.qqGuildv2SDK.event_action.delete_msg(self, message_id)

    def delete_msg(self, message_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """撤回消息

        用于撤回指定消息（以管理员权限）

        Args:
            message_id: 需要撤回的消息ID
        """
        if remote:
            pass
        else:
            self.__delete_msg(message_id, flag_log=True)

    @callbackLogger('get_msg')
    def __get_msg(self, message_id, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_msg(self, message_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_msg(self, message_id)
        return res_data

    def get_msg(self, message_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """获取消息

        用于获取指定消息详情

        Args:
            message_id: 需要查询的消息ID

        Returns:
            message_id (ID): 所查询的消息ID，Defaults to None
            id (ID): 所查询的消息的实际ID，Defaults to -1
            sender (USER): 发送者信息
            time (int): 消息时间戳，Defaults to -1
            message (MSG): 消息内容，Defaults to None
            raw_message (MSG): 消息原生内容，Defaults to None
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_msg(message_id, flag_log=True)
        return res_data

    @callbackLogger('get_forward_msg')
    def __get_forward_msg(self, message_id, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_forward_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_forward_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_forward_msg(self, message_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_forward_msg(self, message_id)
        return res_data

    def get_forward_msg(self, message_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """获取合并转发消息

        用于获取合并转发消息内容

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            message_id: 合并转发消息ID

        Returns:
            messages (list): 消息列表，Defaults to []
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_forward_msg(message_id, flag_log=True)
        return res_data

    @callbackLogger('send_group_forward_msg')
    def __send_group_forward_msg(self, group_id, messages, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_group_forward_msg(self, group_id, messages)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_group_forward_msg(self, group_id, messages)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_group_forward_msg(self, group_id, messages)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.send_group_forward_msg(self, group_id, messages)

    def send_group_forward_msg(self, group_id: 'str|int', messages, flag_log: bool = True, remote: bool = False):
        """发送群合并转发消息

        用于发送群合并转发消息

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID
            messages: 消息节点列表
        """
        if remote:
            pass
        else:
            self.__send_group_forward_msg(group_id, messages, flag_log=True)

    @callbackLogger('send_private_forward_msg')
    def __send_private_forward_msg(self, user_id, messages, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_private_forward_msg(self, user_id, messages)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_private_forward_msg(self, user_id, messages)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_private_forward_msg(self, user_id, messages)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.send_private_forward_msg(self, user_id, messages)

    def send_private_forward_msg(self, user_id: 'str|int', messages, flag_log: bool = True, remote: bool = False):
        """发送私聊合并转发消息

        用于发送私聊合并转发消息

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            user_id: 用户ID
            messages: 消息节点列表
        """
        if remote:
            pass
        else:
            self.__send_private_forward_msg(user_id, messages, flag_log=True)

    @callbackLogger('set_essence_msg')
    def __set_essence_msg(self, message_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_essence_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_essence_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_essence_msg(self, message_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_essence_msg(self, message_id)

    def set_essence_msg(self, message_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """设置精华消息

        用于设置精华消息

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            message_id: 消息ID
        """
        if remote:
            pass
        else:
            self.__set_essence_msg(message_id, flag_log=True)

    @callbackLogger('delete_essence_msg')
    def __delete_essence_msg(self, message_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_essence_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_essence_msg(self, message_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_essence_msg(self, message_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.delete_essence_msg(self, message_id)

    def delete_essence_msg(self, message_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """移出精华消息

        用于移出精华消息

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            message_id: 消息ID
        """
        if remote:
            pass
        else:
            self.__delete_essence_msg(message_id, flag_log=True)

    @callbackLogger('send_like')
    def __send_like(self, user_id, times, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_like(self, user_id, times)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_like(self, user_id, times)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_like(self, user_id, times)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.send_like(self, user_id, times)

    def send_like(self, user_id: 'str|int', times: int = 1, flag_log: bool = True, remote: bool = False):
        """发送赞

        用于发送赞

        Args:
            user_id: 点赞对象ID
            times: 点赞次数 (default: 1)
        """
        if remote:
            pass
        else:
            self.__send_like(user_id, times, flag_log=True)

    @callbackLogger('send_group_sign')
    def __send_group_sign(self, group_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_group_sign(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_group_sign(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_group_sign(self, group_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.send_group_sign(self, group_id)

    def send_group_sign(self, group_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """群打卡

        用于群打卡

        支持平台：OneBotV11
        支持协议：NapCat、LLOneBot

        Args:
            group_id: 群ID
        """
        if remote:
            pass
        else:
            self.__send_group_sign(group_id, flag_log=True)

    @callbackLogger('get_essence_msg_list')
    def __get_essence_msg_list(self, group_id, flag_log=True):
        res_data = OlivOS.contentAPI.api_result_data_template.get_essence_msg_list()
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_essence_msg_list(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_essence_msg_list(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_essence_msg_list(self, group_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_essence_msg_list(self, group_id)
        return res_data

    def get_essence_msg_list(self, group_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """获取精华消息列表

        用于获取群精华消息列表

        支持平台：`OneBotV11`
        支持协议：Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID

        Returns:
            list[dict]: 返回值为列表，列表中每项包含以下字段：
                - sender_id (int): 发送者QQ号
                - sender_nick (str): 发送者昵称
                - sender_time (int): 发送时间戳
                - operator_id (int): 操作者QQ号
                - operator_nick (str): 操作者昵称
                - operator_time (int): 操作时间戳
                - message_id (int): 消息ID
                - message (str): 消息内容
                - wording (str): 精华消息说明
                - extra (dict): 平台特有扩展数据
                    * extra.msg_seq (int): 消息序号 NapCat
                    * extra.msg_random (int): 消息随机数 NapCat
                    * extra.content (list): 消息内容列表 NapCat, Lagrange
        """
        if remote:
            pass
        else:
            return self.__get_essence_msg_list(group_id, flag_log=True)

    @callbackLogger('get_group_ignore_add_request')
    def __get_group_ignore_add_request(self, group_id=None, flag_log=True):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_ignore_add_request()
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_ignore_add_request(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_ignore_add_request(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_ignore_add_request(self, group_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_ignore_add_request(self, group_id)
        return res_data

    def get_group_ignore_add_request(self, group_id: 'str|int' = None, flag_log: bool = True, remote: bool = False):
        """获取已过滤的加群通知

        用于获取已过滤的加群通知

        支持平台：OneBotV11
        支持协议：NapCat（LLOneBot请使用`get_group_system_msg`）

        Args:
            group_id: 群ID（可选，用于筛选特定群） (default: None)

        Returns:
            list[dict]: 返回值为列表，列表中每项包含以下字段：
                - request_id (int): 请求ID
                - invitor_uin (int): 邀请者QQ号
                - invitor_nick (str): 邀请者昵称
                - group_id (int): 群号
                - group_name (str): 群名称
                - checked (bool): 是否已处理
                - actor (int): 操作者QQ号
                - requester_nick (str): 请求者昵称
                - message (str): 请求消息
        """
        if remote:
            pass
        else:
            return self.__get_group_ignore_add_request(group_id, flag_log=True)

    @callbackLogger('get_doubt_friends_add_request')
    def __get_doubt_friends_add_request(self, count=50, flag_log=True):
        res_data = OlivOS.contentAPI.api_result_data_template.get_doubt_friends_add_request()
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_doubt_friends_add_request(self, count)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_doubt_friends_add_request(self, count)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_doubt_friends_add_request(self, count)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_doubt_friends_add_request(self, count)
        return res_data

    def get_doubt_friends_add_request(self, count: int = 50, flag_log: bool = True, remote: bool = False):
        """获取被过滤的好友请求

        用于获取被过滤的好友请求

        支持平台：OneBotV11
        支持协议：NapCat、LLOneBot

        Args:
            count: 获取数量 (default: 50)

        Returns:
            list[dict]: 返回值为列表，列表中每项包含以下字段：
                - flag (str): 请求标识
                - uin (str): 请求者QQ号
                - nick (str): 请求者昵称
                - source (str): 请求来源
                - reason (str): 验证消息
                - msg (str): 附加消息
                - group_code (str): 来源群号
                - time (str): 请求时间
                - type (str): 请求类型
                - extra (dict): 平台特有扩展数据
        """
        if remote:
            pass
        else:
            return self.__get_doubt_friends_add_request(count, flag_log=True)

    @callbackLogger('set_doubt_friends_add_request')
    def __set_doubt_friends_add_request(self, flag, approve=True, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_doubt_friends_add_request(self, flag, approve)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_doubt_friends_add_request(self, flag, approve)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_doubt_friends_add_request(self, flag, approve)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_doubt_friends_add_request(self, flag, approve)

    def set_doubt_friends_add_request(
        self, flag: str,
        approve: bool = True,
        flag_log: bool = True,
        remote: bool = False
    ):
        """处理被过滤的好友请求

        用于处理被过滤的好友请求

        支持平台：OneBotV11
        支持协议：NapCat、LLOneBot
        - LLOneBot 不使用`approve`参数

        Args:
            flag: 加好友请求的`flag`（需下事件的数据中获得）
            approve: 是否同意请求 (default: True)
        """
        if remote:
            pass
        else:
            self.__set_doubt_friends_add_request(flag, approve, flag_log=True)

    @callbackLogger('get_group_system_msg')
    def __get_group_system_msg(self, count=50, flag_log=True):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_system_msg()
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_system_msg(self, count)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_system_msg(self, count)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_system_msg(self, count)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_system_msg(self, count)
        return res_data

    def get_group_system_msg(self, count: int = 50, flag_log: bool = True, remote: bool = False):
        """获取群系统消息

        用于获取群系统消息（包括加群申请和邀请）

        支持平台：OneBotV11
        支持协议：NapCat、LLOneBot
        - LLOneBot 使用 GET 方法，不支持 count 参数
        - NapCat 使用 POST 方法，支持 count 参数
        - LLOneBot 的已过滤请求也在此接口查看

        Args:
            count: 获取数量（仅NapCat支持） (default: 50)

        Returns:
            invited_requests (list): 邀请加群申请列表，Defaults to []
            join_requests (list): 加群申请列表，Defaults to []
        """
        if remote:
            pass
        else:
            return self.__get_group_system_msg(count, flag_log=True)

    @callbackLogger('group_poke')
    def __group_poke(self, group_id, user_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.group_poke(self, group_id, user_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.group_poke(self, group_id, user_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.group_poke(self, group_id, user_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.group_poke(self, group_id, user_id)

    def group_poke(self, group_id: 'str|int', user_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """群戳一戳

        用于在群内戳一戳某人

        支持平台：OneBotV11
        支持协议：Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID
            user_id: 用户ID
        """
        if remote:
            pass
        else:
            self.__group_poke(group_id, user_id, flag_log=True)

    @callbackLogger('get_group_notice')
    def __get_group_notice(self, group_id, flag_log=True):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_notice()
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_notice(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_notice(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_notice(self, group_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_notice(self, group_id)
        return res_data

    def get_group_notice(self, group_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """获取群公告

        用于获取群公告列表

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot
        - NapCat/Lagrange: notice_id 为字符串类型，extra.notice_id_type = 'string'
        - 其他平台: notice_id 为整数类型，extra.notice_id_type = 'int'

        Args:
            group_id: 群ID

        Returns:
            list[dict]: 返回值为列表，列表中每项包含以下字段：
                - sender_id (int): 发送者QQ号
                - publish_time (int): 发布时间戳
                - message (dict): 公告内容(字典格式)
                - notice_id (str/int): 公告ID
                - extra (dict): 扩展信息
                    * notice_id_type (str): 公告类型，可能值为 'string' 或 'int'
        """
        if remote:
            pass
        else:
            return self.__get_group_notice(group_id, flag_log=True)

    @callbackLogger('send_group_notice')
    def __send_group_notice(self, group_id, content, image=None, flag_log=True, **kwargs):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_group_notice(self, group_id, content, image, **kwargs)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_group_notice(self, group_id, content, image, **kwargs)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.send_group_notice(self, group_id, content, image, **kwargs)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.send_group_notice(
                    self, group_id, content, image, **kwargs
                )

    def send_group_notice(
        self, group_id: 'str|int', content: str,
        image: str = None,
        flag_log: bool = True,
        remote: bool = False,
        **kwargs
    ):
        """发送群公告

        用于发送群公告

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot
        - NapCat具有额外参数kwargs

        Args:
            group_id: 群ID
            content: 公告内容
            image: 公告图片URL (default: None)
            **kwargs (dict): NapCat 额外参数
                - pinned (int): 是否置顶(0-不置顶, 1-置顶)
                - type (int): 公告类型
                - confirm_required (int): 是否需要确认(0-不需要, 1-需要)
                - is_show_edit_card (int): 是否显示编辑卡片
                - tip_window_type (int): 提示窗口类型
        """
        if remote:
            pass
        else:
            self.__send_group_notice(group_id, content, image, flag_log=True, **kwargs)

    @callbackLogger('del_group_notice')
    def __del_group_notice(self, group_id, notice_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.del_group_notice(self, group_id, notice_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.del_group_notice(self, group_id, notice_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.del_group_notice(self, group_id, notice_id)

    def del_group_notice(self, group_id: 'str|int', notice_id: str, flag_log: bool = True, remote: bool = False):
        """删除群公告

        用于删除群公告

        支持平台：OneBotV11
        支持协议：Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID
            notice_id: 公告ID
        """
        if remote:
            pass
        else:
            self.__del_group_notice(group_id, notice_id, flag_log=True)

    @callbackLogger('friend_poke')
    def __friend_poke(self, user_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.friend_poke(self, user_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.friend_poke(self, user_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.friend_poke(self, user_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.friend_poke(self, user_id)

    def friend_poke(self, user_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """好友戳一戳

        用于戳一戳好友

        支持平台：OneBotV11
        支持协议：Lagrange、NapCat、LLOneBot

        Args:
            user_id: 用户ID
        """
        if remote:
            pass
        else:
            self.__friend_poke(user_id, flag_log=True)

    @callbackLogger('set_group_kick')
    def __set_group_kick(self, group_id, user_id, host_id, reject_add_request, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotV12SDK.event_action.set_group_kick(self, group_id, user_id)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_kick(self, group_id, user_id, reject_add_request)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_kick(self, group_id, user_id, reject_add_request)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_kick(self, group_id, user_id, reject_add_request)
        elif self.platform['sdk'] == 'kaiheila_link':
            # KOOK 中，host_id 是服务器ID（guild_id），group_id 是频道ID（channel_id）
            # 服务器相关操作需要使用 host_id
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            OlivOS.kaiheilaSDK.event_action.set_group_kick(self, tmp_host_id, user_id)
        elif self.platform['sdk'] == 'xiaoheihe_link':
            # 小黑盒中，host_id 是 room_id(房间ID)，group_id 是 channel_id(频道ID)
            # 踢人操作使用 host_id(room_id)
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            OlivOS.xiaoheiheSDK.event_action.set_group_kick(self, tmp_host_id, user_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_kick(
                    self, group_id, user_id, reject_add_request
                )

    def set_group_kick(self, group_id: 'str|int', user_id: 'str|int', host_id: 'str|int|None' = None,
                       rehect_add_request: bool = False, flag_log: bool = True, remote: bool = False):
        """踢出群成员

        用于踢出群成员

        Args:
            group_id: 群对象ID
            user_id: 群成员对象ID
            host_id: 发送目标的所属HOST ID (default: None)
            rehect_add_request: 是否拉黑对象 (default: False)
        """
        if remote:
            pass
        else:
            self.__set_group_kick(group_id, user_id, host_id, rehect_add_request, flag_log=True)

    @callbackLogger('set_group_ban')
    def __set_group_ban(self, group_id, user_id, host_id, duration, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotV12SDK.event_action.set_group_ban(self, group_id, user_id, duration)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_ban(self, group_id, user_id, duration)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_ban(self, group_id, user_id, duration)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_ban(self, group_id, user_id, duration)
        elif self.platform['sdk'] == 'xiaoheihe_link':
            # 小黑盒中，host_id 是 room_id(房间ID)，group_id 是 channel_id(频道ID)
            # 禁言操作使用 host_id(room_id)
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            OlivOS.xiaoheiheSDK.event_action.set_group_ban(self, tmp_host_id, user_id, duration)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_ban(self, group_id, user_id, duration)

    def set_group_ban(self, group_id: 'str|int', user_id: 'str|int', host_id: 'str|int|None' = None,
                      duration: int = 1800, flag_log: bool = True, remote: bool = False):
        """禁言群成员

        用于禁言群成员

        Args:
            group_id: 群对象ID
            user_id: 群成员对象ID
            host_id: 发送目标的所属HOST ID (default: None)
            duration: 禁言时长/秒 (default: 1800)，0表示解除禁言
        """
        if remote:
            pass
        else:
            self.__set_group_ban(group_id, user_id, host_id, duration, flag_log=True)

    @callbackLogger('set_group_anonymous_ban')
    def __set_group_anonymous_ban(self, group_id, anonymous, anonymous_flag, host_id, duration, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_anonymous_ban(
                        self, group_id, anonymous, anonymous_flag, duration)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_anonymous_ban(
                        self, group_id, anonymous, anonymous_flag, duration)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_anonymous_ban(
                        self, group_id, anonymous, anonymous_flag, duration)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_anonymous_ban(self, group_id: 'str|int', anonymous, anonymous_flag: str,
                                host_id: 'str|int|None' = None, duration: int = 1800, flag_log: bool = True,
                                remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_anonymous_ban(group_id, anonymous, anonymous_flag, host_id, duration, flag_log=True)

    @callbackLogger('set_group_whole_ban')
    def __set_group_whole_ban(self, group_id, enable, host_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_whole_ban(self, group_id, enable)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_whole_ban(self, group_id, enable)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_whole_ban(self, group_id, enable)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_whole_ban(self, group_id, enable)

    def set_group_whole_ban(self, group_id: 'str|int', enable: bool, host_id: 'str|int|None' = None,
                            flag_log: bool = True, remote: bool = False):
        """禁言本群

        用于禁言本群

        Args:
            group_id: 群对象ID
            enable: 禁言状态
            host_id: 发送目标的所属HOST ID (default: None)
        """
        if remote:
            pass
        else:
            self.__set_group_whole_ban(group_id, enable, host_id, flag_log=True)

    @callbackLogger('set_group_admin')
    def __set_group_admin(self, group_id, user_id, enable, host_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotV12SDK.event_action.set_group_admin(self, group_id, user_id, enable)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_admin(self, group_id, user_id, enable)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_admin(self, group_id, user_id, enable)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_admin(self, group_id, user_id, enable)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_admin(self, group_id, user_id, enable)

    def set_group_admin(self, group_id: 'str|int', user_id: 'str|int', enable: bool, host_id: 'str|int|None' = None,
                        flag_log: bool = True, remote: bool = False):
        """设置群管理员

        用于设置群管理员

        Args:
            group_id: 群对象ID
            user_id: 群成员对象ID
            enable: 管理员状态
            host_id: 发送目标的所属HOST ID (default: None)
        """
        if remote:
            pass
        else:
            self.__set_group_admin(group_id, user_id, enable, host_id, flag_log=True)

    @callbackLogger('set_group_anonymous')
    def __set_group_anonymous(self, group_id, enable, host_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_anonymous(self, group_id, enable)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_anonymous(self, group_id, enable)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_anonymous(self, group_id, enable)
        elif self.platform['sdk'] == 'telegram_poll':
            pass

    def set_group_anonymous(self, group_id: 'str|int', enable: bool, host_id: 'str|int' = None, flag_log: bool = True,
                            remote: bool = False):
        if remote:
            pass
        else:
            self.__set_group_anonymous(group_id, enable, host_id, flag_log=True)

    @callbackLogger('set_group_card')
    def __set_group_card(self, group_id, user_id, card, host_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_card(self, group_id, user_id, card)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_card(self, group_id, user_id, card)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_card(self, group_id, user_id, card)
        elif self.platform['sdk'] == 'kaiheila_link':
            # KOOK 中，host_id 是服务器ID（guild_id），group_id 是频道ID（channel_id）
            # 服务器相关操作需要使用 host_id
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            OlivOS.kaiheilaSDK.event_action.set_group_card(self, tmp_host_id, user_id, card)
        elif self.platform['sdk'] == 'xiaoheihe_link':
            # 小黑盒中，host_id 是 room_id(房间ID)，group_id 是 channel_id(频道ID)
            # 修改房间昵称使用 host_id(room_id)
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            OlivOS.xiaoheiheSDK.event_action.set_group_card(self, tmp_host_id, user_id, card)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_card(self, group_id, user_id, card)

    def set_group_card(self, group_id: 'str|int', user_id: 'str|int', card, host_id: 'str|int|None' = None,
                       flag_log: bool = True, remote: bool = False):
        """设置群成员名片

        用于设置群成员名片

        Args:
            group_id: 群对象ID
            user_id: 群成员对象ID
            card: 新的群名片
            host_id: 发送目标的所属HOST ID (default: None)
        """
        if remote:
            pass
        else:
            self.__set_group_card(group_id, user_id, card, host_id, flag_log=True)

    @callbackLogger('set_group_name')
    def __set_group_name(self, group_id, group_name, host_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotV12SDK.event_action.set_group_name(self, group_id, group_name)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_name(self, group_id, group_name)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_name(self, group_id, group_name)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_name(self, group_id, group_name)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_name(self, group_id, group_name)

    def set_group_name(self, group_id: 'str|int', group_name: str, host_id: 'str|int|None' = None,
                       flag_log: bool = True, remote: bool = False):
        """设置群名

        用于设置群名

        Args:
            group_id: 群对象ID
            group_name: 新的群名
            host_id: 发送目标的所属HOST ID (default: None)
        """
        if remote:
            pass
        else:
            self.__set_group_name(group_id, group_name, host_id, flag_log=True)

    @callbackLogger('set_group_leave')
    def __set_group_leave(self, group_id, host_id, is_dismiss, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotV12SDK.event_action.set_group_leave(self, group_id)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_leave(self, group_id, is_dismiss)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_leave(self, group_id, is_dismiss)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_leave(self, group_id, is_dismiss)
            elif self.platform['model'] in OlivOS.OPQBotLinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.OPQBotSDK.event_action.set_group_leave(self, group_id, self.plugin_info['control_queue'])
        elif self.platform['sdk'] == 'kaiheila_link':
            # KOOK 中，host_id 是服务器ID（guild_id），group_id 是频道ID（channel_id）
            # 服务器相关操作需要使用 host_id（guild_id）
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            OlivOS.kaiheilaSDK.event_action.set_group_leave(self, tmp_host_id)
        elif self.platform['sdk'] == 'xiaoheihe_link':
            # 小黑盒中，host_id 是 room_id(房间ID)，group_id 是 channel_id(频道ID)
            # 退出房间使用 host_id(room_id)
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            OlivOS.xiaoheiheSDK.event_action.set_group_leave(self, tmp_host_id)
        elif self.platform['sdk'] == 'telegram_poll':
            OlivOS.telegramSDK.event_action.set_chat_leave(self, group_id, is_dismiss)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_leave(self, group_id, is_dismiss)

    def set_group_leave(self, group_id: 'str|int', host_id: 'str|int|None' = None, is_dismiss: bool = False,
                        flag_log: bool = True, remote: bool = False):
        """退出群

        用于退出群

        Args:
            group_id: 群对象ID
            host_id: 发送目标的所属HOST ID (default: None)
            is_dismiss: 当为群主时是否解散该群 (default: False)
        """
        if remote:
            pass
        else:
            self.__set_group_leave(group_id, host_id, is_dismiss, flag_log=True)

    @callbackLogger('set_group_special_title')
    def __set_group_special_title(self, group_id, user_id, special_title, duration, host_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_special_title(
                        self, group_id, user_id, special_title, duration
                    )
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_special_title(
                        self, group_id, user_id, special_title, duration
                    )
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    OlivOS.onebotSDK.event_action.set_group_special_title(
                        self, group_id, user_id, special_title, duration
                    )
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_special_title(
                    self, group_id, user_id, special_title, duration
                )

    def set_group_special_title(self, group_id: 'str|int', user_id: 'str|int', special_title: str, duration: int,
                                host_id: 'str|int|None' = None, flag_log: bool = True, remote: bool = False):
        """设置群成员特殊头衩

        用于设置群成员特殊头衣

        Args:
            group_id: 群对象ID
            user_id: 群成员对象ID
            special_title: 专属头衣，不填或空字符串表示删除专属头衣
            duration: 专属头衣有效期/秒，`-1`表示永久
            host_id: 发送目标的所属HOST ID (default: None)
        """
        if remote:
            pass
        else:
            self.__set_group_special_title(group_id, user_id, special_title, duration, host_id, flag_log=True)

    @callbackLogger('set_friend_add_request')
    def __set_friend_add_request(self, flag, approve, remark, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                OlivOS.onebotV12SDK.event_action.set_friend_add_request(self, flag, approve, remark)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_friend_add_request(self, flag, approve, remark)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_friend_add_request(self, flag, approve, remark)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_friend_add_request(self, flag, approve, remark)
            elif self.platform['model'] in OlivOS.OPQBotLinkServerAPI.gCheckList:
                OlivOS.OPQBotSDK.event_action.set_friend_add_request(
                    self, flag, approve, self.plugin_info['control_queue']
                )
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_friend_add_request(
                    self, flag, approve, remark
                )

    def set_friend_add_request(self, flag: str, approve: bool, remark: str, flag_log: bool = True,
                               remote: bool = False):
        """处理好友请求

        用于处理好友请求

        Args:
            flag: 加好友请求的`flag`（需下事件的数据中获得）
            approve: 是否同意请求
            remark: 添加后的好友备注（仅在同意时有效）
        """
        if remote:
            pass
        else:
            self.__set_friend_add_request(flag, approve, remark, flag_log=True)

    @callbackLogger('set_group_add_request')
    def __set_group_add_request(self, flag, sub_type, approve, reason, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                OlivOS.onebotV12SDK.event_action.set_group_add_request(self, flag, sub_type, approve, reason)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_group_add_request(self, flag, sub_type, approve, reason)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_group_add_request(self, flag, sub_type, approve, reason)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_group_add_request(self, flag, sub_type, approve, reason)
            elif self.platform['model'] in OlivOS.OPQBotLinkServerAPI.gCheckList:
                OlivOS.OPQBotSDK.event_action.set_group_add_request(
                    self, flag, sub_type, approve, self.plugin_info['control_queue']
                )
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_add_request(
                    self, flag, sub_type, approve, reason
                )

    def set_group_add_request(self, flag: str, sub_type: str, approve: bool, reason: str, flag_log: bool = True,
                              remote: bool = False):
        """处理群请求

        用于处理群请求

        Args:
            flag: 加群请求的`flag`（需下事件的数据中获得）
            sub_type: 请求类型（需要和事件中的`sub_type`字段相符）
            approve: 是否同意请求/邀请
            reason: 拒绝理由（仅在拒绝时有效）
        """
        if remote:
            pass
        else:
            self.__set_group_add_request(flag, sub_type, approve, reason, flag_log=True)

    def __get_login_info(self, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotV12SDK.event_action.get_login_info(self)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_login_info(self)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_login_info(self)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'telegram_poll':
            res_data = OlivOS.telegramSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'discord_link':
            res_data = OlivOS.discordSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'fanbook_poll':
            res_data = OlivOS.fanbookSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'qqGuild_link':
            res_data = OlivOS.qqGuildSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'qqGuildv2_link':
            res_data = OlivOS.qqGuildv2SDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'kaiheila_link':
            res_data = OlivOS.kaiheilaSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'dodo_link':
            res_data = OlivOS.dodoLinkSDK.event_action.get_login_info(self)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_login_info(self)

        if res_data is None:
            return None

        if flag_log and self.log_func is not None:
            if checkDictByListAnd(
                    res_data, [
                        ['active'],
                        ['data', 'name'],
                        ['data', 'id']
                    ]
            ):
                if res_data['active']:
                    self.log_func(2, 'name(' + res_data['data']['name'] + ') id(' + str(res_data['data']['id']) + ')', [
                        (self.getBotIDStr(), 'default'),
                        (self.plugin_info['name'], 'default'),
                        ('get_login_info', 'callback')
                    ])
                else:
                    self.log_func(2, 'failed', [
                        (self.getBotIDStr(), 'default'),
                        (self.plugin_info['name'], 'default'),
                        ('get_login_info', 'callback')
                    ])
        return res_data

    def get_login_info(self, flag_log: bool = True, remote: bool = False):
        """获取登录账号信息

        用于获取登录账号信息

        Returns:
            dict: 整个返回值为USER类型
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_login_info(flag_log=True)
        return res_data

    @callbackLogger('get_stranger_info', ['name', 'id'])
    def __get_stranger_info(self, user_id, no_cache, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotV12SDK.event_action.get_stranger_info(self, user_id)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_stranger_info(self, user_id, no_cache)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_stranger_info(self, user_id, no_cache)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_stranger_info(self, user_id, no_cache)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'kaiheila_link':
            res_data = OlivOS.kaiheilaSDK.event_action.get_stranger_info(self, user_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_stranger_info(self, user_id)
        return res_data

    def get_stranger_info(self, user_id: 'str|int', no_cache: bool = False, flag_log: bool = True,
                          remote: bool = False):
        """获取陌生人信息

        用于获取陌生人信息

        Args:
            user_id: 陌生人对象ID

        Returns:
            dict: 整个返回值为USER类型
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_stranger_info(user_id, no_cache, flag_log=True)
        return res_data

    @callbackLogger('get_friend_list')
    def __get_friend_list(self, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotV12SDK.event_action.get_friend_list(self)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_friend_list(self)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_friend_list(self)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_friend_list(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_friend_list(self)
        return res_data

    def get_friend_list(self, flag_log: bool = True, remote: bool = False):
        """获取好友列表

        用于获取好友列表

        Returns:
            list[dict]: 整个返回值为USER类型的列表，Defaults to []
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_friend_list(flag_log=True)
        return res_data

    @callbackLogger('get_group_info', ['name', 'id'])
    def __get_group_info(self, group_id, host_id, no_cache, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotV12SDK.event_action.get_group_info(self, group_id)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotSDK.event_action.get_group_info(self, group_id, no_cache)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotSDK.event_action.get_group_info(self, group_id, no_cache)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotSDK.event_action.get_group_info(self, group_id, no_cache)
        elif self.platform['sdk'] == 'kaiheila_link':
            # KOOK 中，host_id 是服务器ID（guild_id），group_id 是频道ID（channel_id）
            # get_group_info 获取的是频道详情，使用 group_id（channel_id）
            res_data = OlivOS.kaiheilaSDK.event_action.get_group_info(self, group_id)
        elif self.platform['sdk'] == 'telegram_poll':
            res_data = OlivOS.telegramSDK.event_action.get_group_info(self, group_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_info(self, group_id)
        return res_data

    def get_group_info(self, group_id: 'str|int', host_id: 'str|int|None' = None, no_cache: bool = False,
                       flag_log: bool = True, remote: bool = False):
        """获取群信息

        用于获取群信息

        Args:
            group_id: 群对象ID
            host_id: 发送目标的所属HOST ID (default: None)

        Returns:
            dict: 整个返回值为GROUP类型
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_info(group_id, host_id, no_cache, flag_log=True)
        return res_data

    @callbackLogger('get_group_list')
    def __get_group_list(self, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotV12SDK.event_action.get_group_list(self)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_list(self)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_list(self)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_list(self)
            elif self.platform['model'] in OlivOS.OPQBotLinkServerAPI.gCheckList:
                res_data = OlivOS.OPQBotSDK.event_action.get_group_list(self, self.plugin_info['control_queue'])
        elif self.platform['sdk'] == 'kaiheila_link':
            # KOOK 中，host_id 是服务器ID（guild_id），group_id 是频道ID（channel_id）
            # get_group_list 获取的是频道列表，需要 host_id（guild_id）作为参数
            # 从事件数据中获取 host_id
            tmp_host_id = None
            if hasattr(self.data, 'host_id') and self.data.host_id is not None:
                tmp_host_id = self.data.host_id
            if tmp_host_id is not None:
                res_data = OlivOS.kaiheilaSDK.event_action.get_group_list(self, tmp_host_id)
        elif self.platform['sdk'] == 'xiaoheihe_link':
            res_data = OlivOS.xiaoheiheSDK.event_action.get_group_list(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_list(self)
        return res_data

    def get_group_list(self, flag_log: bool = True, remote: bool = False):
        """获取群列表

        用于获取群列表

        Returns:
            list[dict]: 整个返回值为GROUP类型的列表，Defaults to []
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_list(flag_log=True)
        return res_data

    @callbackLogger('get_group_member_info', ['name', 'id', 'group_id'])
    def __get_group_member_info(self, group_id, user_id, host_id, no_cache, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotV12SDK.event_action.get_group_member_info(self, group_id, user_id)
                else:
                    pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotSDK.event_action.get_group_member_info(self, group_id, user_id, no_cache)
                else:
                    res_data = OlivOS.onebotSDK.event_action.get_guild_member_profile(self, host_id, user_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotSDK.event_action.get_group_member_info(self, group_id, user_id, no_cache)
                else:
                    res_data = OlivOS.onebotSDK.event_action.get_guild_member_profile(self, host_id, user_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotSDK.event_action.get_group_member_info(self, group_id, user_id, no_cache)
                else:
                    res_data = OlivOS.onebotSDK.event_action.get_guild_member_profile(self, host_id, user_id)
        elif self.platform['sdk'] == 'telegram_poll':
            res_data = OlivOS.telegramSDK.event_action.get_group_member_info(self, group_id, user_id)
        elif self.platform['sdk'] == 'kaiheila_link':
            # KOOK 中，host_id 是服务器ID（guild_id），group_id 是频道ID（channel_id）
            # 获取服务器成员信息需要使用 host_id（guild_id）
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            res_data = OlivOS.kaiheilaSDK.event_action.get_group_member_info(self, tmp_host_id, user_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_member_info(self, group_id, user_id)
        return res_data

    def get_group_member_info(self, group_id: 'str|int', user_id: 'str|int', host_id: 'str|int|None' = None,
                              no_cache: bool = False, flag_log: bool = True, remote: bool = False):
        """获取群成员信息

        用于获取群成员信息

        Args:
            group_id: 群对象ID
            user_id: 群成员对象ID
            host_id: 发送目标的所属HOST ID (default: None)

        Returns:
            dict: 整个返回值为GROUPUSER类型
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_member_info(group_id, user_id, host_id, no_cache, flag_log=True)
        return res_data

    @callbackLogger('get_group_member_list')
    def __get_group_member_list(self, group_id, host_id, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotV12SDK.event_action.get_group_member_list(self, group_id)
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotSDK.event_action.get_group_member_list(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotSDK.event_action.get_group_member_list(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                if host_id is None:
                    res_data = OlivOS.onebotSDK.event_action.get_group_member_list(self, group_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_member_list(self, group_id)
        elif self.platform['sdk'] == 'kaiheila_link':
            # KOOK 中，host_id 是服务器ID（guild_id），group_id 是频道ID（channel_id）
            # 获取服务器成员列表需要使用 host_id（guild_id）
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            res_data = OlivOS.kaiheilaSDK.event_action.get_group_member_list(self, tmp_host_id)
        elif self.platform['sdk'] == 'xiaoheihe_link':
            # 小黑盒中，host_id 是 room_id(房间ID)，group_id 是 channel_id(频道ID)
            # 获取房间成员列表使用 host_id(room_id)
            # 如果未提供 host_id，尝试从事件数据中获取
            tmp_host_id = host_id
            if tmp_host_id is None and hasattr(self.data, 'host_id'):
                tmp_host_id = self.data.host_id
            res_data = OlivOS.xiaoheiheSDK.event_action.get_group_member_list(self, tmp_host_id)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        return res_data

    def get_group_member_list(self, group_id: 'str|int', host_id: 'str|int|None' = None, flag_log: bool = True,
                              remote: bool = False):
        """获取群成员列表

        用于获取群成员列表

        Args:
            group_id: 群对象ID
            host_id: 发送目标的所属HOST ID (default: None)

        Returns:
            list[dict]: 整个返回值为GROUPUSER类型的列表，Defaults to []
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_member_list(group_id, host_id, flag_log=True)
        return res_data

    @callbackLogger('get_host_list')
    def __get_host_list(self, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'kaiheila_link':
            res_data = OlivOS.kaiheilaSDK.event_action.get_host_list(self)
        return res_data

    def get_host_list(self, flag_log: bool = True, remote: bool = False):
        """获取频道列表

        用于获取频道列表

        Returns:
            list: 频道列表，Defaults to []
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_host_list(flag_log=True)
        return res_data

    @callbackLogger('get_host_info', ['name', 'id'])
    def __get_host_info(self, host_id, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'kaiheila_link':
            res_data = OlivOS.kaiheilaSDK.event_action.get_host_info(self, host_id)
        return res_data

    def get_host_info(self, host_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """获取频道信息

        用于获取频道信息

        Args:
            host_id: 频道ID
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_host_info(host_id, flag_log=True)
        return res_data

    @callbackLogger('can_send_image')
    def __can_send_image(self, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.can_send_image(self)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.can_send_image(self)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.can_send_image(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.can_send_image(self)
        return res_data

    def can_send_image(self, flag_log: bool = True, remote: bool = False):
        """检查是否可以发送图片

        用于检查是否可以发送图片

        Returns:
            yes (bool): 是否可以发送图片
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__can_send_image(flag_log=True)
        return res_data

    @callbackLogger('can_send_record')
    def __can_send_record(self, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.can_send_record(self)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.can_send_record(self)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.can_send_record(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.can_send_record(self)
        return res_data

    def can_send_record(self, flag_log: bool = True, remote: bool = False):
        """检查是否可以发送语音

        用于检查是否可以发送语音

        Returns:
            yes (bool): 是否可以发送语音
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__can_send_record(flag_log=True)
        return res_data

    @callbackLogger('get_status')
    def __get_status(self, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_status(self)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_status(self)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_status(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_status(self)
        return res_data

    def get_status(self, flag_log: bool = True, remote: bool = False):
        """获取运行状态

        用于获取OneBot运行状态

        Returns:
            online (bool): 当前QQ在线状态
            good (bool): 状态符合预期
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_status(flag_log=True)
        return res_data

    @callbackLogger('get_version_info')
    def __get_version_info(self, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_version_info(self)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_version_info(self)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_version_info(self)
        elif self.platform['sdk'] == 'telegram_poll':
            pass
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_version_info(self)
        return res_data

    def get_version_info(self, flag_log: bool = True, remote: bool = False):
        """获取版本信息

        用于获取OneBot版本信息

        Returns:
            name (str): 应用标识
            version (str): 应用版本
            protocol_version (str): OneBot协议版本
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_version_info(flag_log=True)
        return res_data

    # 文件相关接口

    @callbackLogger('upload_group_file')
    def __upload_group_file(self, group_id, file, name='', folder_id=None, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.upload_group_file(self, group_id, file, name, folder_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.upload_group_file(self, group_id, file, name, folder_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.upload_group_file(self, group_id, file, name, folder_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.upload_group_file(self, group_id, file, name, folder_id)

    def upload_group_file(self, group_id: 'str|int', file: str, name: str = '', folder_id: 'str|None' = None,
                          flag_log: bool = True, remote: bool = False):
        """上传群文件

        用于上传群文件

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID
            file: 本地文件路径
            name: 存储名称 (default: '')
            folder_id: 父目录ID (default: None)
        """
        if remote:
            pass
        else:
            self.__upload_group_file(group_id, file, name, folder_id, flag_log)

    @callbackLogger('delete_group_file')
    def __delete_group_file(self, group_id, file_id, name=None, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_group_file(self, group_id, file_id, name)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_group_file(self, group_id, file_id, name)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_group_file(self, group_id, file_id, name)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.delete_group_file(self, group_id, file_id, name)

    def delete_group_file(self, group_id: 'str|int', file_id: str, name: 'str|None' = None, flag_log: bool = True,
                          remote: bool = False):
        """删除群文件

        用于删除群文件

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID
            file_id: 文件ID
            name: 文件名（未使用） (default: None)
        """
        if remote:
            pass
        else:
            self.__delete_group_file(group_id, file_id, name, flag_log)

    @callbackLogger('create_group_file_folder')
    def __create_group_file_folder(self, group_id, name, parent_id='/', flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.create_group_file_folder(self, group_id, name, parent_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.create_group_file_folder(self, group_id, name, parent_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.create_group_file_folder(self, group_id, name, parent_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.create_group_file_folder(self, group_id, name, parent_id)

    def create_group_file_folder(self, group_id: 'str|int', name: str, parent_id: str = '/', flag_log: bool = True,
                                 remote: bool = False):
        """创建群文件夹

        用于创建群文件夹

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID
            name: 文件夹名称
            parent_id: 父目录ID (default: '/')
        """
        if remote:
            pass
        else:
            self.__create_group_file_folder(group_id, name, parent_id, flag_log)

    @callbackLogger('delete_group_folder')
    def __delete_group_folder(self, group_id, folder_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_group_folder(self, group_id, folder_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_group_folder(self, group_id, folder_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.delete_group_folder(self, group_id, folder_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.delete_group_folder(self, group_id, folder_id)

    def delete_group_folder(self, group_id: 'str|int', folder_id: str, flag_log: bool = True, remote: bool = False):
        """删除群文件夹

        用于删除群文件夹

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID
            folder_id: 文件夹ID
        """
        if remote:
            pass
        else:
            self.__delete_group_folder(group_id, folder_id, flag_log)

    @callbackLogger('get_group_file_system_info')
    def __get_group_file_system_info(self, group_id, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_file_system_info(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_file_system_info(self, group_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_file_system_info(self, group_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_file_system_info(self, group_id)
        return res_data

    def get_group_file_system_info(self, group_id: 'str|int', flag_log: bool = True, remote: bool = False):
        """获取群文件系统信息

        用于获取群文件系统信息

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID

        Returns:
            file_count (int): 文件数量，Defaults to 0
            limit_count (int): 文件数量限制，Defaults to 0
            used_space (int): 已使用空间，Defaults to 0
            total_space (int): 总空间，Defaults to 0
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_file_system_info(group_id, flag_log)
        return res_data

    @callbackLogger('get_group_root_files')
    def __get_group_root_files(self, group_id, file_count=None, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_root_files(self, group_id, file_count)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_root_files(self, group_id, file_count)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_root_files(self, group_id, file_count)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_root_files(
                    self, group_id, file_count
                )
        return res_data

    def get_group_root_files(
        self, group_id: 'str|int',
        file_count: 'int|None' = None,
        flag_log: bool = True,
        remote: bool = False
    ):
        """获取群根目录文件列表

        用于获取群根目录文件列表

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot（file_count参数仅NapCat支持）

        Args:
            group_id: 群ID
            file_count: 获取数量（NapCat支持） (default: None)

        Returns:
            list[dict]: 整个返回值为列表，列表中每项包含以下字段：
                - files (list): 文件列表，Defaults to []
                - folders (list): 文件夹列表，Defaults to []
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_root_files(group_id, file_count, flag_log)
        return res_data

    @callbackLogger('get_group_files_by_folder')
    def __get_group_files_by_folder(self, group_id, folder_id, file_count=None, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_files_by_folder(
                    self, group_id, folder_id, file_count
                )
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_files_by_folder(
                    self, group_id, folder_id, file_count
                )
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_files_by_folder(
                    self, group_id, folder_id, file_count
                )
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_files_by_folder(
                    self, group_id, folder_id, file_count
                )
        return res_data

    def get_group_files_by_folder(self, group_id: 'str|int', folder_id: str, file_count: 'int|None' = None,
                                  flag_log: bool = True, remote: bool = False):
        """获取群子目录文件列表

        用于获取群子目录文件列表

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot（file_count参数仅NapCat支持）

        Args:
            group_id: 群ID
            folder_id: 文件夹ID
            file_count: 获取数量（NapCat支持） (default: None)

        Returns:
            files (list): 文件列表，Defaults to []
            folders (list): 文件夹列表，Defaults to []
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_files_by_folder(group_id, folder_id, file_count, flag_log)
        return res_data

    @callbackLogger('get_group_file_url')
    def __get_group_file_url(self, group_id, file_id, busid, flag_log=True):
        res_data = None
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_file_url(self, group_id, file_id, busid)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_file_url(self, group_id, file_id, busid)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                res_data = OlivOS.onebotSDK.event_action.get_group_file_url(self, group_id, file_id, busid)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                res_data = OlivOS.milkySDK.event_action.get_group_file_url(self, group_id, file_id)
        return res_data

    def get_group_file_url(self, group_id: 'str|int', file_id: str, busid: int, flag_log: bool = True,
                           remote: bool = False):
        """获取群文件下载链接

        用于获取群文件下载链接

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            group_id: 群ID
            file_id: 文件ID
            busid: 文件类型

        Returns:
            url (str): 文件下载URL, Defaults to ''
        """
        res_data = None
        if remote:
            pass
        else:
            res_data = self.__get_group_file_url(group_id, file_id, busid, flag_log)
        return res_data

    @callbackLogger('upload_private_file')
    def __upload_private_file(self, user_id, file, name, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.upload_private_file(self, user_id, file, name)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.upload_private_file(self, user_id, file, name)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.upload_private_file(self, user_id, file, name)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.upload_private_file(self, user_id, file, name)

    def upload_private_file(self, user_id: 'str|int', file: str, name: str, flag_log: bool = True,
                            remote: bool = False):
        """上传私聊文件

        用于上传私聊文件

        支持平台：OneBotV11
        支持协议：go-cqhttp、Lagrange、NapCat、LLOneBot

        Args:
            user_id: 用户ID
            file: 本地文件路径
            name: 文件名称
        """
        if remote:
            pass
        else:
            self.__upload_private_file(user_id, file, name, flag_log)

    @callbackLogger('rename_group_file_folder')
    def __rename_group_file_folder(self, group_id, folder_id, new_folder_name, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.rename_group_file_folder(self, group_id, folder_id, new_folder_name)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.rename_group_file_folder(self, group_id, folder_id, new_folder_name)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.rename_group_file_folder(self, group_id, folder_id, new_folder_name)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.rename_group_file_folder(self, group_id, folder_id, new_folder_name)

    def rename_group_file_folder(
        self, group_id: 'str|int', folder_id: str, new_folder_name: str,
        flag_log: bool = True,
        remote: bool = False
    ):
        """重命名群文件夹

        用于重命名群文件夹

        支持平台：OneBotV11
        支持协议：LLOneBot、Lagrange

        Args:
            group_id: 群ID
            folder_id: 文件夹ID
            new_folder_name: 新文件夹名称
        """
        if remote:
            pass
        else:
            self.__rename_group_file_folder(group_id, folder_id, new_folder_name, flag_log=True)

    @callbackLogger('rename_group_file')
    def __rename_group_file(self, group_id, file_id, current_parent_directory, new_name, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.rename_group_file(
                    self, group_id, file_id, current_parent_directory, new_name
                )
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.rename_group_file(
                    self, group_id, file_id, current_parent_directory, new_name
                )
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.rename_group_file(
                    self, group_id, file_id, current_parent_directory, new_name
                )
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.rename_group_file(
                    self, group_id, file_id, current_parent_directory, new_name
                )

    def rename_group_file(
        self, group_id: 'str|int', file_id: str, current_parent_directory: str, new_name: str,
        flag_log: bool = True,
        remote: bool = False
    ):
        """重命名群文件

        用于重命名群文件

        支持平台：OneBotV11
        支持协议：NapCat

        Args:
            group_id: 群ID
            file_id: 文件ID
            current_parent_directory: 当前父目录路径
            new_name: 新文件名
        """
        if remote:
            pass
        else:
            self.__rename_group_file(group_id, file_id, current_parent_directory, new_name, flag_log=True)

    @callbackLogger('set_group_file_forever')
    def __set_group_file_forever(self, group_id, file_id, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_group_file_forever(self, group_id, file_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_group_file_forever(self, group_id, file_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_group_file_forever(self, group_id, file_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_group_file_forever(
                    self, group_id, file_id
                )

    def set_group_file_forever(self, group_id: 'str|int', file_id: str, flag_log: bool = True, remote: bool = False):
        """群文件转永久

        用于将群文件转为永久保存

        支持平台：OneBotV11
        支持协议：NapCat、LLOneBot

        Args:
            group_id: 群ID
            file_id: 文件ID
        """
        if remote:
            pass
        else:
            self.__set_group_file_forever(group_id, file_id, flag_log=True)

    @callbackLogger('set_msg_emoji_like')
    def __set_msg_emoji_like(self, message_id, emoji_id, is_set=True, group_id=None, flag_log=True):
        if self.platform['sdk'] == 'onebot':
            if self.platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                pass
            elif self.platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_msg_emoji_like(self, message_id, emoji_id, is_set, group_id)
            elif self.platform['model'] in OlivOS.onebotV11HostServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_msg_emoji_like(self, message_id, emoji_id, is_set, group_id)
            elif self.platform['model'] in OlivOS.onebotV11LinkServerAPI.gCheckList:
                OlivOS.onebotSDK.event_action.set_msg_emoji_like(self, message_id, emoji_id, is_set, group_id)
        elif self.platform['sdk'] == 'milky':
            if self.platform['model'] in OlivOS.milkyAutoServerAPI.gCheckList:
                OlivOS.milkySDK.event_action.set_msg_emoji_like(
                    self, message_id, emoji_id, is_set, group_id
                )

    def set_msg_emoji_like(
        self, message_id: 'str|int', emoji_id: 'str|int',
        is_set: bool = True,
        group_id: 'str|int|None' = None,
        flag_log: bool = True,
        remote: bool = False
    ):
        """消息表情回应

        用于给消息添加或取消表情回应，统合了所有主流协议的接口实现

        支持平台：OneBotV11
        支持协议：Lagrange、NapCat、LLOneBot
        - Lagrange 平台必须提供 group_id 参数，使用 set_group_reaction 接口
        - NapCat 使用 set_msg_emoji_like 接口，emoji_id为整数
        - LLOneBot 根据is_set使用 set_msg_emoji_like 或 unset_msg_emoji_like 接口

        Args:
            message_id: 消息ID
            emoji_id: 表情ID（Lagrange使用字符串code，NapCat和LLOneBot使用整数ID）
            is_set: True为添加，False为取消 (default: True)
            group_id: 群ID（Lagrange必需） (default: None)
        """
        if remote:
            pass
        else:
            self.__set_msg_emoji_like(message_id, emoji_id, is_set, group_id, flag_log)


class StoppableThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop_event = threading.Event()
        self.root = None

    def terminate(self):
        if self.root is not None:
            try:
                self.root.on_terminate()
            except Exception:
                traceback.print_exc()
        self._stop_event.set()
        self.stop_thread()

    def stop(self):
        self.terminate()

    def join(self):
        pass

    def stopped(self):
        return self._stop_event.is_set()

    def _async_raise(self, tid, exctype):
        """raises the exception, performs cleanup if needed"""
        tid = ctypes.c_long(tid)
        if not inspect.isclass(exctype):
            exctype = type(exctype)
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
        if res == 0:
            raise ValueError("invalid thread id")
        elif res != 1:
            # """if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"""
            ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")

    def stop_thread(self):
        self._async_raise(self.ident, SystemExit)


class Proc_templet(object):
    def __init__(self, Proc_name='native_plugin', Proc_type='default', scan_interval=0.001, dead_interval=1,
                 rx_queue=None, tx_queue=None, control_queue=None, logger_proc=None):
        self.deamon = True
        self.Proc = None
        self.Proc_name = Proc_name
        self.Proc_type = Proc_type
        self.Proc_info = self.Proc_info_T(
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            control_queue=control_queue,
            logger_proc=logger_proc,
            scan_interval=scan_interval,
            dead_interval=dead_interval
        )
        self.Proc_config = {}
        self.Proc_data = {}

    class Proc_info_T(object):
        def __init__(self, rx_queue, tx_queue, control_queue, logger_proc, scan_interval=0.001, dead_interval=1):
            self.rx_queue = rx_queue
            self.tx_queue = tx_queue
            self.control_queue = control_queue
            self.control_rx_queue = multiprocessing.Queue()
            self.logger_proc = logger_proc
            self.scan_interval = scan_interval
            self.dead_interval = dead_interval

    def run(self):
        pass

    def run_total(self):
        t_this = StoppableThread(
            name=self.Proc_name + '+on_control_rx',
            target=self.on_control_rx_init,
            args=()
        )
        t_this.daemon = self.deamon
        t_this.start()
        self.run()

    def on_control_rx_init(self):
        while True:
            if self.Proc_info.control_rx_queue.empty():
                time.sleep(0.02)
            else:
                try:
                    packet = self.Proc_info.control_rx_queue.get(block=False)
                except Exception:
                    continue
                self.on_control_rx(packet)

    def on_control_rx(self, packet):
        # print("!!!! " + self.Proc_name + str(packet.__dict__))
        pass

    def on_terminate(self):
        pass

    def start(self):
        proc_this = multiprocessing.Process(name=self.Proc_name, target=self.run_total, args=())
        proc_this.daemon = self.deamon
        proc_this.start()
        # self.Proc = proc_this
        return proc_this

    def start_lite(self):
        proc_this = StoppableThread(name=self.Proc_name, target=self.run_total, args=())
        proc_this.root = self
        proc_this.daemon = self.deamon
        proc_this.start()
        # self.Proc = proc_this
        return proc_this

    def start_unity(self, mode='threading'):
        proc_this = None
        if mode == 'processing':
            proc_this = self.start()
        elif mode == 'threading':
            proc_this = self.start_lite()
        return proc_this

    def log(self, log_level, log_message, log_segment=None):
        if log_segment is None:
            log_segment = []
        if self.Proc_info.logger_proc is not None:
            self.Proc_info.logger_proc.log(log_level, log_message, log_segment)


# 兼容Win平台的进程生成方法
def Proc_start(proc_this):
    proc_proc_this = multiprocessing.Process(name=proc_this.Proc_name, target=proc_this.run, args=())
    proc_proc_this.daemon = proc_this.deamon
    # multiprocessing.Process无法进行弱引用序列化烘培，故无法在Win平台下实现自动更新进程引用
    # proc_this.Proc = proc_proc_this
    proc_proc_this.start()
    return proc_proc_this


class Proc_info_T(object):
    def __init__(self, rx_queue, tx_queue, logger_proc, scan_interval=0.001):
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
