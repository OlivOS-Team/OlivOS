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
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import threading
import time
import json
import websocket
import uuid

import OlivOS


class bot_info_T(object):
    def __init__(self, id=-1, nickname=None, chatroom=None):
        self.id = id
        self.nickname = nickname
        self.chatroom = chatroom
        self.debug_mode = False
        self.debug_logger = None


def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(
        id=plugin_bot_info.id,
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
    if target_event.sdk_event.payload.active:
        if target_event.sdk_event.payload.cmd == 'chat':
            if (
                    'nick' in target_event.sdk_event.payload.data
            ) and (
                    'userid' in target_event.sdk_event.payload.data
            ) and (
                    'text' in target_event.sdk_event.payload.data
            ):
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_message'
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_string',
                    target_event.sdk_event.payload.data['text']
                )
                target_event.data = target_event.group_message(
                    str(0),
                    str(target_event.sdk_event.payload.data['userid']),
                    message_obj,
                    'group'
                )
                target_event.data.message_sdk = message_obj
                target_event.data.message_id = str(-1)
                target_event.data.raw_message = message_obj
                target_event.data.raw_message_sdk = message_obj
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.data['userid'])
                target_event.data.sender['nickname'] = target_event.sdk_event.payload.data['nick']
                target_event.data.sender['id'] = str(target_event.sdk_event.payload.data['userid'])
                target_event.data.sender['name'] = target_event.sdk_event.payload.data['nick']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0
                target_event.data.sender['role'] = 'member'
                target_event.data.host_id = None
                # if plugin_event_bot_hash in sdkSubSelfInfo:
                #    target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
                # if str(target_event.data.user_id) == str(target_event.base_info['self_id']):
                #    target_event.active = False


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
        def __init__(self, nickname: str, chatroom: str):
            payload_template.__init__(self)
            self.cmd = 'join'
            self.data = {
                "cmd": "join",
                "channel": chatroom,
                "nick": nickname
            }

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
