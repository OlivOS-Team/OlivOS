# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/dodobotEASDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import multiprocessing
import threading
import time
import json

import OlivOS

post_host = 'http://127.0.0.1'
post_port = '8022'
websocket_host = 'ws://127.0.0.1'
websocket_port = 8011

class bot_info_T(object):
    def __init__(self, id = -1, host = '', port = -1, access_token = None):
        self.id = id
        self.host = host
        self.port = port
        self.access_token = access_token
        self.debug_mode = False
        self.debug_logger = None

def get_SDK_bot_info_from_Event(target_event):
    res = bot_info_T(
        target_event.bot_info.id,
        target_event.bot_info.post_info.host,
        target_event.bot_info.post_info.port,
        target_event.bot_info.post_info.access_token
    )
    res.debug_mode = target_event.bot_info.debug_mode
    return res

class platform_bot_info_T(object):
    def __init__(self, id = -1):
        self.id = id
        self.host = None
        self.port = None
        self.access_token = None
        self.nickname = None
        self.avatar_url = None

def get_SDK_platform_bot_info_from_data(target_data):
    global websocket_host
    global websocket_port
    if 'Uid' in target_data:
        res = platform_bot_info_T(target_data['Uid'])
    else:
        return None
    if 'Token' in target_data:
        res.access_token = target_data['Token']
    else:
        return None
    if 'NickName' in target_data:
        res.nickname = target_data['NickName']
    else:
        return None
    if 'AvatarUrl' in target_data:
        res.avatar_url = target_data['AvatarUrl']
    else:
        return None
    res.host = websocket_host
    res.port = websocket_port
    return res

def get_SDK_bot_info_from_Plugin_bot_info(Plugin_bot_info, platform_bot_info):
    res = bot_info_T(
        id = Plugin_bot_info.id,
        host = platform_bot_info.host,
        port = platform_bot_info.port,
        access_token = platform_bot_info.access_token
    )
    res.debug_mode = Plugin_bot_info.debug_mode
    return res

class event(object):
    def __init__(self, json_obj = None, bot_info = None):
        self.raw = self.event_dump(json_obj)
        self.json = json_obj
        self.platform = {}
        self.platform['sdk'] = 'dodobot_ea'
        self.platform['platform'] = 'dodo'
        self.platform['model'] = 'default'
        self.active = False
        if self.json != None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = bot_info.id
            self.base_info['post_type'] = None

    def event_dump(self, raw):
        try:
            res = json.dumps(raw)
        except:
            res = None
        return res

#支持OlivOS API事件生成的映射实现
def get_Event_from_SDK(target_event):
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = target_event.sdk_event.base_info['self_id']
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'old_string'
    #现阶段只有频道消息
    if True:
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message'
        target_event.data = target_event.group_message(
            target_event.sdk_event.json['FromChannel'],
            target_event.sdk_event.json['Uid'],
            target_event.sdk_event.json['Content'],
            'group'
        )
        target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('old_string', target_event.sdk_event.json['Content'])
        target_event.data.message_id = target_event.sdk_event.json['Id']
        target_event.data.raw_message = target_event.sdk_event.json['OriginalContent']
        target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('old_string', target_event.sdk_event.json['OriginalContent'])
        target_event.data.font = None
        target_event.data.sender['user_id'] = target_event.sdk_event.json['Uid']
        target_event.data.sender['nickname'] = target_event.sdk_event.json['NickName']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0

#支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, chat_id, message):
        this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.chat_id = chat_id
        this_msg.data.text = message
        return this_msg.do_api()

class api_templet(object):
    def __init__(self):
        self.bot_info = None
        self.data = None
        self.node_ext = None
        self.res = None

    def do_api(self):
        res = {}
        if self.node_ext == 'sendMessage':
            res.update({
                'Type': 1,
                'Context': self.data.text,
                'Account': {
                    "Uid": self.bot_info.id,
                    "Token": self.bot_info.access_token
                },
                'Channel': self.data.chat_id,
                'ReferencedMessageId': None
            })
        self.res = res
        return res

class API(object):
    class sendMessage(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'sendMessage'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.chat_id = 0
                self.text = ''

