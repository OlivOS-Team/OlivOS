# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/OPQBotSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import time
import json
import uuid
import hashlib

import OlivOS

gBotIdDict = {}

class bot_info_T(object):
    def __init__(self, id=-1):
        self.id = id
        self.debug_mode = False
        self.debug_logger = None


def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(id=plugin_bot_info.id)
    return res


def get_SDK_bot_info_from_Event(target_event):
    res = get_SDK_bot_info_from_Plugin_bot_info(target_event.bot_info)
    return res


class event(object):
    def __init__(self, payload_data=None, bot_info=None):
        self.payload = payload_data
        self.platform = {'sdk': 'onebot', 'platform': 'qq', 'model': 'opqbot_default'}
        if type(bot_info.platform) is dict:
            self.platform.update(bot_info.platform)
        self.active = False
        if self.payload is not None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = self.payload.CurrentQQ
            self.base_info['post_type'] = None

def get_message(Content:str, AtUinLists:list):
    res_msg = Content
    if type(AtUinLists) is list:
        for AtUin in AtUinLists:
            res_msg = res_msg.replace(f'@{AtUin["Nick"]}', f'[OP:at,id={AtUin["Uin"]}]')
    return res_msg

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
        if target_event.sdk_event.payload.EventName == 'ON_EVENT_GROUP_NEW_MSG':
            if type(target_event.sdk_event.payload.EventData) is dict \
            and 'MsgHead' in target_event.sdk_event.payload.EventData \
            and type(target_event.sdk_event.payload.EventData['MsgHead']) is dict \
            and 'FromUin' in target_event.sdk_event.payload.EventData['MsgHead'] \
            and type(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']) is int \
            and 'ToUin' in target_event.sdk_event.payload.EventData['MsgHead'] \
            and type(target_event.sdk_event.payload.EventData['MsgHead']['ToUin']) is int \
            and 'SenderUin' in target_event.sdk_event.payload.EventData['MsgHead'] \
            and type(target_event.sdk_event.payload.EventData['MsgHead']['SenderUin']) is int \
            and 'SenderNick' in target_event.sdk_event.payload.EventData['MsgHead'] \
            and type(target_event.sdk_event.payload.EventData['MsgHead']['SenderNick']) is str \
            and 'MsgBody' in target_event.sdk_event.payload.EventData \
            and type(target_event.sdk_event.payload.EventData['MsgBody']) is dict \
            and 'Content' in target_event.sdk_event.payload.EventData['MsgBody'] \
            and type(target_event.sdk_event.payload.EventData['MsgBody']['Content']) is str:
                target_event.active = True
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_string',
                    get_message(
                        Content = target_event.sdk_event.payload.EventData['MsgBody']['Content'],
                        AtUinLists = target_event.sdk_event.payload.EventData['MsgBody'].get('AtUinLists', [])
                    )
                )
                if str(target_event.sdk_event.payload.EventData['MsgHead']['SenderUin']) == str(target_event.base_info['self_id']):
                    target_event.plugin_info['func_type'] = 'group_message_sent'
                    target_event.data = target_event.group_message_sent(
                        str(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']),
                        str(target_event.sdk_event.payload.EventData['MsgHead']['SenderUin']),
                        message_obj,
                        'group'
                    )
                else:
                    target_event.plugin_info['func_type'] = 'group_message'
                    target_event.data = target_event.group_message(
                        str(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']),
                        str(target_event.sdk_event.payload.EventData['MsgHead']['SenderUin']),
                        message_obj,
                        'group'
                    )
                target_event.data.message_sdk = message_obj
                target_event.data.message_id = str(-1)
                target_event.data.raw_message = message_obj
                target_event.data.raw_message_sdk = message_obj
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.EventData['MsgHead']['SenderUin'])
                target_event.data.sender['nickname'] = target_event.sdk_event.payload.EventData['MsgHead']['SenderNick']
                target_event.data.sender['id'] = target_event.data.sender['user_id']
                target_event.data.sender['name'] = target_event.data.sender['nickname']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0
                target_event.data.sender['role'] = 'member'
                target_event.data.host_id = None
        elif target_event.sdk_event.payload.EventName == 'ON_EVENT_FRIEND_NEW_MSG':
            if type(target_event.sdk_event.payload.EventData) is dict \
            and 'MsgHead' in target_event.sdk_event.payload.EventData \
            and type(target_event.sdk_event.payload.EventData['MsgHead']) is dict \
            and 'FromUin' in target_event.sdk_event.payload.EventData['MsgHead'] \
            and type(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']) is int \
            and 'ToUin' in target_event.sdk_event.payload.EventData['MsgHead'] \
            and type(target_event.sdk_event.payload.EventData['MsgHead']['ToUin']) is int \
            and 'MsgBody' in target_event.sdk_event.payload.EventData \
            and type(target_event.sdk_event.payload.EventData['MsgBody']) is dict \
            and 'Content' in target_event.sdk_event.payload.EventData['MsgBody'] \
            and type(target_event.sdk_event.payload.EventData['MsgBody']['Content']) is str:
                target_event.active = True
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_string',
                    get_message(
                        Content = target_event.sdk_event.payload.EventData['MsgBody']['Content'],
                        AtUinLists = target_event.sdk_event.payload.EventData['MsgBody'].get('AtUinLists', [])
                    )
                )
                target_event.plugin_info['func_type'] = 'private_message'
                target_event.data = target_event.private_message(
                    str(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']),
                    message_obj,
                    'private'
                )
                target_event.data.message_sdk = message_obj
                target_event.data.message_id = str(-1)
                target_event.data.raw_message = message_obj
                target_event.data.raw_message_sdk = message_obj
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.EventData['MsgHead']['FromUin'])
                target_event.data.sender['nickname'] = '用户'
                target_event.data.sender['id'] = target_event.data.sender['user_id']
                target_event.data.sender['name'] = target_event.data.sender['nickname']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0
                target_event.data.sender['role'] = 'member'
                target_event.data.host_id = None


'''
对于WEBSOCKET接口的PAYLOAD实现
'''


class payload_template(object):
    def __init__(self, data=None, is_rx=False):
        self.active = True
        self.data = None
        self.EventName = None
        self.EventData = None
        self.CurrentQQ = None
        self.ReqId = int(getHash(str(uuid.uuid4())), 16) % 1000000000000
        self.CgiCmd = None
        self.load(data, is_rx)

    def dump(self):
        res = json.dumps(obj=self.data)
        return res

    def dump_CurrentPacket(self):
        res = json.dumps(
            obj = {
                'CurrentPacket': {
                    'EventData': self.EventData,
                    'EventName': self.EventName
                },
                'CurrentQQ': int(self.CurrentQQ)
            }
        )
        return res

    def load(self, data, is_rx: bool):
        self.active = False
        if is_rx \
        and type(data) is dict \
        and 'CurrentQQ' in data \
        and type(data['CurrentQQ']) in [int, str] \
        and 'CurrentPacket' in data \
        and type(data['CurrentPacket']) is dict \
        and 'EventName' in data['CurrentPacket'] \
        and type(data['CurrentPacket']['EventName']) is str \
        and 'EventData' in data['CurrentPacket'] \
        and type(data['CurrentPacket']['EventData']) is dict:
            self.active = True
            self.data = data
            self.EventName = data['CurrentPacket']['EventName']
            self.EventData = data['CurrentPacket']['EventData']
            self.CurrentQQ = data['CurrentQQ']
        return self


def getHash(key):
    hash_tmp = hashlib.new('md5')
    hash_tmp.update(str(key).encode(encoding='UTF-8'))
    return hash_tmp.hexdigest()

def getIdBackport(id):
    res = id
    try:
        res = int(id)
    except:
        res = id
    return res

class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, data):
            payload_template.__init__(self, data, True)

    class MessageSvc_PbSendMsg(payload_template):
        def __init__(self, ToUin:'int|str', ToType:int, Content:str, CurrentQQ:'int|str'):
            payload_template.__init__(self)
            self.CgiCmd = "MessageSvc.PbSendMsg"
            self.CurrentQQ = str(CurrentQQ)
            self.data = {
                "ReqId": self.ReqId,
                "BotUin": str(self.CurrentQQ),
                "CgiCmd": self.CgiCmd,
                "CgiRequest": {
                    "ToUin": getIdBackport(ToUin),
                    "ToType": ToType,
                    "Content": Content
                }
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
        message_new = ''
        message_obj = OlivOS.messageAPI.Message_templet(
            'olivos_string',
            message
        )
        if message_obj.active:
            for data_this in message_obj.data:
                if data_this.type == 'text':
                    message_new += data_this.data['text']
        if len(message_new) > 0:
            send_ws_event(
                plugin_event_bot_hash,
                PAYLOAD.MessageSvc_PbSendMsg(
                    ToUin = target_id,
                    ToType = 2 if 'group' == target_type else 1,
                    Content = message_new,
                    CurrentQQ = target_event.base_info['self_id']
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
                'type': 'OPQBot_link',
                'hash': hash
            },
            'data': {
                'action': 'send',
                'data': data
            }
        },
        control_queue
    )
