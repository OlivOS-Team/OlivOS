# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqRedSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
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
        self.platform = {'sdk': 'onebot', 'platform': 'qq', 'model': 'red'}
        self.active = False
        if self.payload is not None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = bot_info.id
            self.base_info['post_type'] = None


def get_message_obj(elements:list):
    flag_hit = False
    message_list = []
    for element_this in elements:
        if 'textElement' in element_this and type(element_this['textElement']) is dict \
        and 'atType' in element_this['textElement'] and type(element_this['textElement']['atType']) is int \
        and 'atNtUin' in element_this['textElement'] and type(element_this['textElement']['atNtUin']) is str \
        and 2 == element_this['textElement']['atType']:
            message_list.append(OlivOS.messageAPI.PARA.at(id=element_this['textElement']['atNtUin']))
            flag_hit = True
        elif 'textElement' in element_this and type(element_this['textElement']) is dict \
        and 'content' in element_this['textElement'] and type(element_this['textElement']['content']) is str:
            message_list.append(OlivOS.messageAPI.PARA.text(text=element_this['textElement']['content']))
            flag_hit = True
    if not flag_hit:
        message_obj = OlivOS.messageAPI.Message_templet(
            'olivos_para',
            []
        )
        message_obj.active = False
    else:
        try:
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                message_list
            )
            message_obj.init_data()
        except:
            message_obj.active = False
            message_obj.data = []
    return message_obj

def get_Event_from_SDK(target_event):
    global sdkSubSelfInfo
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info['self_id'])
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'olivos_para'
    plugin_event_bot_hash = OlivOS.API.getBotHash(
        bot_id=target_event.base_info['self_id'],
        platform_sdk=target_event.platform['sdk'],
        platform_platform=target_event.platform['platform'],
        platform_model=target_event.platform['model']
    )
    if target_event.sdk_event.payload.active:
        if target_event.sdk_event.payload.type == 'message::recv' \
        and type(target_event.sdk_event.payload.payload) is list \
        and len(target_event.sdk_event.payload.payload) > 0:
            payload_data = target_event.sdk_event.payload.payload[0]
            if 'chatType' in payload_data and payload_data['chatType'] == 2 \
            and 'peerUid' in payload_data and type(payload_data['peerUid']) is str \
            and 'senderUin' in payload_data and type(payload_data['senderUin']) is str \
            and (('sendNickName' in payload_data and type(payload_data['sendNickName']) is str) \
            or ('sendMemberName' in payload_data and type(payload_data['sendMemberName']) is str)) \
            and 'elements' in payload_data and type(payload_data['elements']) is list \
            and len(payload_data['elements']) > 0:
                message_obj = get_message_obj(payload_data['elements'])
                if message_obj.active:
                    target_event.active = True
                    target_event.plugin_info['func_type'] = 'group_message'
                    target_event.data = target_event.group_message(
                        str(payload_data['peerUid']),
                        str(payload_data['senderUin']),
                        message_obj,
                        'group'
                    )
                    target_event.data.message_sdk = message_obj
                    target_event.data.message_id = str(-1)
                    target_event.data.raw_message = message_obj
                    target_event.data.raw_message_sdk = message_obj
                    target_event.data.font = None
                    target_event.data.sender['user_id'] = str(payload_data['senderUin'])
                    target_event.data.sender['nickname'] = payload_data['sendNickName']
                    if len(payload_data['sendMemberName']) > 0:
                        target_event.data.sender['nickname'] = payload_data['sendMemberName']
                    target_event.data.sender['id'] = target_event.data.sender['user_id']
                    target_event.data.sender['name'] = target_event.data.sender['nickname']
                    target_event.data.sender['sex'] = 'unknown'
                    target_event.data.sender['age'] = 0
                    target_event.data.host_id = None
            elif 'chatType' in payload_data and payload_data['chatType'] == 1 \
            and 'peerUin' in payload_data and type(payload_data['peerUin']) is str \
            and 'elements' in payload_data and type(payload_data['elements']) is list \
            and len(payload_data['elements']) > 0:
                message_obj = get_message_obj(payload_data['elements'])
                if message_obj.active:
                    target_event.active = True
                    target_event.plugin_info['func_type'] = 'private_message'
                    target_event.data = target_event.private_message(
                        str(payload_data['peerUin']),
                        message_obj,
                        'friend'
                    )
                    target_event.data.message_sdk = message_obj
                    target_event.data.message_id = str(-1)
                    target_event.data.raw_message = message_obj
                    target_event.data.raw_message_sdk = message_obj
                    target_event.data.font = None
                    target_event.data.sender['user_id'] = str(payload_data['peerUin'])
                    target_event.data.sender['nickname'] = 'User'
                    target_event.data.sender['id'] = target_event.data.sender['user_id']
                    target_event.data.sender['name'] = target_event.data.sender['nickname']
                    target_event.data.sender['sex'] = 'unknown'
                    target_event.data.sender['age'] = 0
                    target_event.data.host_id = None


'''
对于WEBSOCKET接口的PAYLOAD实现
'''


class payload_template(object):
    def __init__(self, data=None, is_rx=False):
        self.active = True
        self.type = None
        self.payload = None
        self.load(data, is_rx)

    def dump(self):
        res = json.dumps(obj={
                'type': self.type,
                'payload': self.payload
            }
        )
        return res

    def load(self, data, is_rx: bool):
        if data is not None:
            if type(data) is dict:
                if 'type' in data and type(data['type']) is str:
                    self.type = data['type']
                else:
                    self.active = False
                if 'payload' in data and type(data['payload']) in [dict, list]:
                    self.payload = data['payload']
                else:
                    self.active = False
            else:
                self.active = False
        return self


class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, data):
            payload_template.__init__(self, data, True)

    class metaConnect(payload_template):
        def __init__(self, token: str):
            payload_template.__init__(self)
            self.type = 'meta::connect'
            self.payload = {
                "token": token
            }

    class messageSend(payload_template):
        def __init__(self, target_type, target_id, message: OlivOS.messageAPI.Message_templet):
            payload_template.__init__(self)
            self.type = 'message::send'
            elements_list = []
            for message_this in message.data:
                if type(message_this) is OlivOS.messageAPI.PARA.text:
                    elements_list.append({
                        "elementType": 1,
                        "textElement": {
                            "content": message_this.data['text']
                        }
                    })
                if type(message_this) is OlivOS.messageAPI.PARA.at:
                    elements_list.append({
                        "elementType": 1,
                        "textElement": {
                            "content": message_this.data['id'],
                            "atType": 2,
                            "atNtUin": message_this.data['id']
                        }
                    })
            self.payload = {
                "peer": {
                    "chatType": target_type, # private 1, group 2
                    "peerUin": target_id,
                    "guildId": None
                },
                "elements": elements_list
            }


# 支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, target_type, target_id, message, control_queue):
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id=target_event.base_info['self_id'],
            platform_sdk=target_event.platform['sdk'],
            platform_platform=target_event.platform['platform'],
            platform_model=target_event.platform['model']
        )
        if message.active:
            send_ws_event(
                plugin_event_bot_hash,
                PAYLOAD.messageSend(
                    target_type=target_type,
                    target_id=target_id,
                    message=message
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
                'type': 'qqRed_link',
                'hash': hash
            },
            'data': {
                'action': 'send',
                'data': data
            }
        },
        control_queue
    )
