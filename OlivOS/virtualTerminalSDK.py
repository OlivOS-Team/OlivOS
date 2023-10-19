# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/virtualTerminalSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

from enum import IntEnum
import sys
import json
import traceback
import requests as req
import time
import hashlib

import OlivOS


class bot_info_T(object):
    def __init__(self, id=-1, access_token=None, model='default'):
        self.id = id
        self.access_token = access_token
        self.model = model
        self.debug_mode = False
        self.debug_logger = None


def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(
        plugin_bot_info.id,
        plugin_bot_info.post_info.access_token
    )
    res.debug_mode = plugin_bot_info.debug_mode
    return res


def get_SDK_bot_info_from_Event(target_event):
    res = get_SDK_bot_info_from_Plugin_bot_info(target_event.bot_info)
    return res


class event(object):
    def __init__(self, payload_obj=None, bot_info=None, model='default', event_id=None):
        self.payload = payload_obj
        self.event_id = event_id
        self.platform = {'sdk': 'terminal_link', 'platform': 'terminal', 'model': model}
        self.active = False
        if self.payload is not None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = bot_info.id
            self.base_info['token'] = bot_info.post_info.access_token
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
    message_obj = None
    user_conf = None
    if target_event.platform['model'] in ['default']:
        message_obj = OlivOS.messageAPI.Message_templet(
            'olivos_string',
            target_event.sdk_event.payload.key['data']['data']
        )
        user_conf = target_event.sdk_event.payload.key['data']['user_conf']
    if message_obj is not None and target_event.platform['model'] in ['default']:
        if message_obj.active:
            target_event.active = True
            tmp_user_conf = {
                "user_name": "未知",
                "user_id": "-1",
                "flag_group": True,
                "target_id": "-1",
                "group_role": "member",
            }
            if user_conf is not None:
                tmp_user_conf.update(user_conf)
            if tmp_user_conf["flag_group"] == True:
                target_event.plugin_info['func_type'] = 'group_message'
                target_event.data = target_event.group_message(
                    tmp_user_conf["target_id"],             # 此时的 target_id 为群号
                    tmp_user_conf["user_id"],
                    message_obj,
                    'group'
                )
            else:
                target_event.plugin_info['func_type'] = 'private_message'
                target_event.data = target_event.private_message(
                    tmp_user_conf["user_id"],               # 此时的 user_id 为发送者的 user_id，接收者固定为机器人
                    message_obj,
                    'private'
                )
            target_event.data.message_sdk = message_obj
            target_event.data.message_id = str(88888888)
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = tmp_user_conf["user_id"]
            target_event.data.sender['nickname'] = tmp_user_conf["user_name"]
            target_event.data.sender['id'] = tmp_user_conf["user_id"]
            target_event.data.sender['name'] = tmp_user_conf["user_name"]
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            if tmp_user_conf["flag_group"] \
            and 'unknown' != tmp_user_conf["group_role"]:
                target_event.data.sender['role'] = tmp_user_conf["group_role"]
            target_event.data.host_id = None
    elif target_event.platform['model'] in ['postapi', 'ff14']:
        # 此段内容不修改
        if 'type' in target_event.sdk_event.payload and target_event.sdk_event.payload['type'] == 'message':
            if 'message_type' in target_event.sdk_event.payload and target_event.sdk_event.payload['message_type'] == 'group_message':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_string',
                    target_event.sdk_event.payload['message']
                )
                if message_obj.active:
                    try:
                        target_event.active = True
                        target_event.plugin_info['func_type'] = 'group_message'
                        target_event.data = target_event.group_message(
                            str(target_event.sdk_event.payload['group_id']),
                            str(target_event.sdk_event.payload['user_id']),
                            message_obj,
                            'group'
                        )
                        target_event.data.message_sdk = message_obj
                        target_event.data.message_id = str(88888888)
                        target_event.data.raw_message = message_obj
                        target_event.data.raw_message_sdk = message_obj
                        target_event.data.font = None
                        target_event.data.sender['name'] = '仑质'
                        target_event.data.sender['id'] = str(target_event.sdk_event.payload['user_id'])
                        if 'sender' in target_event.sdk_event.payload and 'nickname' in target_event.sdk_event.payload['sender']:
                            target_event.data.sender['name'] = target_event.sdk_event.payload['sender']['nickname']
                        target_event.data.sender['nickname'] = target_event.data.sender['name']
                        target_event.data.sender['user_id'] = target_event.data.sender['id']
                        target_event.data.sender['sex'] = 'unknown'
                        target_event.data.sender['age'] = 0
                        target_event.data.sender['role'] = 'owner'
                        target_event.data.host_id = None
                        if target_event.platform['model'] in ['ff14']:
                            hash_tmp = hashlib.new('md5')
                            hash_tmp.update(str(target_event.data.sender['name']).encode(encoding='UTF-8'))
                            tmp_hash_user_id = str(int(int(hash_tmp.hexdigest(), 16) % 1000000000) + 1)
                            target_event.data.user_id = tmp_hash_user_id
                            target_event.data.sender['id'] = tmp_hash_user_id
                    except:
                        message_obj.active = False


# 支持OlivOS API调用的方法实现
class event_action:
    @staticmethod
    def send_msg(target_event, message,  control_queue, flag_type="group", target_id=None):
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id=target_event.base_info['self_id'],
            platform_sdk=target_event.platform['sdk'],
            platform_platform=target_event.platform['platform'],
            platform_model=target_event.platform['model']
        )
        if target_event.platform['model'] in ['default']:
            if target_event.active:
                user_conf = {}
                user_conf['user_name'] = "BOT"
                user_conf['user_id'] = target_event.base_info['self_id']
                user_conf['target_id'] = target_id
                if flag_type == 'group':
                    user_conf['flag_group'] = True
                    user_conf['group_role'] = "member"
                else:
                    user_conf['flag_group'] = False
                send_log_event(plugin_event_bot_hash, message, 'BOT', control_queue, user_conf)
        elif target_event.platform['model'] in ['postapi']:
            if target_event.sdk_event.event_id is not None:
                evnet_id = target_event.sdk_event.event_id
                event_data = {
                    'reply': message
                }
                send_postapi_event(plugin_event_bot_hash, event_data, evnet_id, control_queue)
        elif target_event.platform['model'] in ['ff14']:
            time.sleep(1)
            send_ff14_post(target_event, message)


def sendControlEventSend(action, data, control_queue):
    if control_queue is not None:
        control_queue.put(
            OlivOS.API.Control.packet(
                action,
                data
            ),
            block=False
        )


def send_log_event(hash, data, name, control_queue, user_conf=None):
    sendControlEventSend('send', {
        'target': {
            'type': 'nativeWinUI'
        },
        'data': {
            'action': 'virtual_terminal',
            'event': 'log',
            'hash': hash,
            'data': data,
            'name': name,
            'user_conf': user_conf
        }
    },
                         control_queue
                         )


def send_postapi_event(hash, data, event_id, control_queue):
    sendControlEventSend('send', {
        'target': {
            'type': 'terminal_link',
            'hash': hash
        },
        'data': {
            'action': 'reply',
            'event_id': str(event_id),
            'data': data
        }
    },
                         control_queue
                         )


def send_ff14_post(plugin_event, message: str):
    if True:
        send_url = 'http://127.0.0.1:%s/Command' % str(plugin_event.bot_info.post_info.access_token)
        headers = {
            'Content-Type': 'text/plain'
        }
        data = message.encode('UTF-8')
        msg_res = req.request("POST", send_url, headers=headers, data=data)
        return msg_res
