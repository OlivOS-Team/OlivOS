# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/hackChatSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

import threading
import time
import json
import websocket
import uuid

import OlivOS

gBotIdDict = {}

class bot_info_T(object):
    def __init__(self, id=-1, nickname=None, password='', chatroom=None):
        self.id = id
        self.nickname = nickname
        self.password = password
        self.chatroom = chatroom
        self.debug_mode = False
        self.debug_logger = None


def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(
        id=plugin_bot_info.id,
        password=plugin_bot_info.password,
        nickname=plugin_bot_info.post_info.access_token,
        chatroom=plugin_bot_info.post_info.host
    )
    return res


def get_SDK_bot_info_from_Event(target_event):
    res = get_SDK_bot_info_from_Plugin_bot_info(target_event.bot_info)
    return res


class event(object):
    def __init__(self, payload_data=None, bot_info=None):
        self.payload = payload_data
        self.platform = {'sdk': 'hackChat_link', 'platform': 'hackChat', 'model': 'default'}
        if type(bot_info.platform) is dict:
            self.platform.update(bot_info.platform)
        self.active = False
        if self.payload is not None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = bot_info.id
            self.base_info['nickname'] = bot_info.post_info.access_token
            self.base_info['chatroom'] = bot_info.post_info.host
            self.base_info['post_type'] = None


def get_Event_from_SDK(target_event):
    global sdkSubSelfInfo
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info['self_id'])
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'olivos_string'
    plugin_event_bot_hash = OlivOS.API.getBotHash(
        bot_id=target_event.base_info['self_id'],
        platform_sdk=target_event.platform['sdk'],
        platform_platform=target_event.platform['platform'],
        platform_model=target_event.platform['model']
    )
    user_hash = None
    if target_event.sdk_event.payload.active:
        if 'nick' in target_event.sdk_event.payload.data:
            user_hash = OlivOS.API.getBotHash(
                bot_id=target_event.sdk_event.payload.data['nick'],
                platform_sdk=target_event.platform['sdk'],
                platform_platform=target_event.platform['platform'],
                platform_model=target_event.platform['model']
            )
        if 'userid' in target_event.sdk_event.payload.data:
            user_hash = target_event.sdk_event.payload.data['userid']
        if target_event.sdk_event.payload.cmd == 'onlineSet':
            target_event.active = False
            if 'users' in target_event.sdk_event.payload.data \
            and type(target_event.sdk_event.payload.data['users']) is list:
                for user_this in target_event.sdk_event.payload.data['users']:
                    if type(user_this) is dict \
                    and 'isme' in user_this \
                    and 'userid' in user_this \
                    and user_this['isme'] == True:
                        gBotIdDict[plugin_event_bot_hash] = str(user_this['userid'])
        elif target_event.sdk_event.payload.cmd == 'chat':
            if 'nick' in target_event.sdk_event.payload.data \
            and 'text' in target_event.sdk_event.payload.data:
                target_event.active = True
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_string',
                    target_event.sdk_event.payload.data['text']
                )
                tmp_user_id = str(user_hash)
                if plugin_event_bot_hash in gBotIdDict \
                and tmp_user_id == gBotIdDict[plugin_event_bot_hash]:
                    target_event.plugin_info['func_type'] = 'group_message_sent'
                    target_event.data = target_event.group_message_sent(
                        str(0),
                        str(user_hash),
                        message_obj,
                        'group'
                    )
                else:
                    target_event.plugin_info['func_type'] = 'group_message'
                    target_event.data = target_event.group_message(
                        str(0),
                        str(user_hash),
                        message_obj,
                        'group'
                    )
                target_event.data.message_sdk = message_obj
                target_event.data.message_id = str(-1)
                target_event.data.raw_message = message_obj
                target_event.data.raw_message_sdk = message_obj
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(user_hash)
                target_event.data.sender['nickname'] = target_event.sdk_event.payload.data['nick']
                target_event.data.sender['id'] = str(user_hash)
                target_event.data.sender['name'] = target_event.sdk_event.payload.data['nick']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0
                target_event.data.sender['role'] = 'member'
                target_event.data.host_id = None
        elif target_event.sdk_event.payload.cmd == 'onlineAdd':
            if True:
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_member_increase'
                target_event.data = target_event.group_member_increase(
                    str(0),
                    str(0),
                    str(user_hash),
                    None,
                    'approve'
                )
        elif target_event.sdk_event.payload.cmd == 'onlineRemove':
            if True:
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_member_decrease'
                target_event.data = target_event.group_member_decrease(
                    str(0),
                    str(0),
                    str(user_hash),
                    None,
                    'leave'
                )


'''
对于WEBSOCKET接口的PAYLOAD实现
'''


class payload_template(object):
    def __init__(self, data=None, is_rx=False):
        self.active = True
        self.cmd = None
        self.data = None
        self.load(data, is_rx)

    def dump(self):
        res = json.dumps(obj=self.data)
        return res

    def load(self, data, is_rx: bool):
        if data is not None:
            if type(data) == dict:
                if 'cmd' in data and type(data['cmd']) == str:
                    self.cmd = data['cmd']
                else:
                    self.active = False
                self.data = data
            else:
                self.active = False
        return self


class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, data):
            payload_template.__init__(self, data, True)

    class join(payload_template):
        def __init__(self, nickname: str, chatroom: str, password:str=None):
            payload_template.__init__(self)
            self.cmd = 'join'
            self.data = {
                "cmd": "join",
                "channel": chatroom,
                "nick": nickname
            }
            if type(password) is str \
            and len(password) > 0:
                self.data['password'] = password

    class chat(payload_template):
        def __init__(self, message: str):
            payload_template.__init__(self)
            self.cmd = 'chat'
            self.data = {
                "cmd": "chat",
                "text": message
            }


# 支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, message, control_queue):
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id=target_event.base_info['self_id'],
            platform_sdk=target_event.platform['sdk'],
            platform_platform=target_event.platform['platform'],
            platform_model=target_event.platform['model']
        )
        message_new = ''
        message_obj = OlivOS.messageAPI.Message_templet(
            'olivos_string',
            message
        )
        if message_obj.active:
            for data_this in message_obj.data:
                if data_this.type == 'text':
                    message_new += data_this.data['text']
                elif data_this.type == 'image':
                    imagePath = data_this.data['file']
                    if data_this.data['url'] is not None:
                        imagePath = data_this.data['url']
                    message_new += '![%s](%s)' % (
                        imagePath,
                        imagePath
                    )
        if len(message_new) > 0:
            send_ws_event(
                plugin_event_bot_hash,
                PAYLOAD.chat(
                    message=message_new
                ).dump(),
                control_queue
            )


def sendControlEventSend(action, data, control_queue):
    if control_queue is not None:
        control_queue.put(
            OlivOS.API.Control.packet(
                action,
                data
            ),
            block=False
        )


def send_ws_event(hash, data, control_queue):
    sendControlEventSend('send', {
        'target': {
            'type': 'hackChat_link',
            'hash': hash
        },
        'data': {
            'action': 'send',
            'data': data
        }
    },
                         control_queue
                         )
