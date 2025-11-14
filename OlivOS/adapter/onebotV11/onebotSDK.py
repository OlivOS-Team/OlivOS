# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/onebotSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import requests as req
from urllib import parse
import os
import time
import traceback

import OlivOS

paraMsgMap = [
    'shamrock_default',
    'para_default'
]

napcatModelMap = [
    'napcat',
    'napcat_hide',
    'napcat_show',
    'napcat_show_new',
    'napcat_show_old',
    'napcat_default',
]

llonebotModelMap = [
    'llonebot_default'
]

lagrangeModelMap = [
    'lagrange_default'
]

gFlagCheckList = []

class bot_info_T(object):
    def __init__(self, id=-1, host='', port=-1, access_token=None):
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


class send_onebot_post_json_T(object):
    def __init__(self):
        self.bot_info = None
        self.obj = None
        self.node_ext = ''

    def send_onebot_post_json(self):
        if type(self.bot_info) is not bot_info_T or self.bot_info.host == '' or self.bot_info.port == -1 or self.obj is None or self.node_ext == '':
            return None
        else:
            try:
                # clear_dict = {k: v for k, v in self.obj.__dict__.items() if v != -1}
                clear_dict = self.obj.__dict__
                if clear_dict.get('message_type') == 'private':
                    clear_dict.pop('group_id','No "group_id"')
                json_str_tmp = json.dumps(obj=clear_dict, ensure_ascii=False)
                tmp_host = self.bot_info.host
                if tmp_host.startswith('http://') or tmp_host.startswith('https://'):
                    pass
                else:
                    tmp_host = 'http://' + tmp_host
                token_str = ''
                token_dict = {}
                if len(self.bot_info.access_token) > 0:
                    token_str = f'?access_token={self.bot_info.access_token}'
                    token_dict = {'Authorization': f'Bearer {self.bot_info.access_token}'}
                send_url = f'{self.bot_info.host}:{self.bot_info.port}/{self.node_ext}{token_str}'

                if self.bot_info.debug_mode:
                    if self.bot_info.debug_logger is not None:
                        self.bot_info.debug_logger.log(0, self.node_ext + ': ' + json_str_tmp)

                headers = {
                    'Content-Type': 'application/json'
                }
                headers.update(token_dict)
                msg_res = req.request("POST", send_url, headers=headers, data=json_str_tmp.encode('utf-8'))

                if self.bot_info.debug_mode:
                    if self.bot_info.debug_logger is not None:
                        self.bot_info.debug_logger.log(0, self.node_ext + ' - sendding succeed: ' + msg_res.text)

                return msg_res
            except:
                traceback.print_exc()


class api_templet(object):
    def __init__(self):
        self.bot_info = None
        self.data = None
        self.node_ext = None
        self.res = None

    def do_api(self):
        this_post_json = send_onebot_post_json_T()
        this_post_json.bot_info = self.bot_info
        this_post_json.obj = self.data
        this_post_json.node_ext = self.node_ext
        try:
            self.res = this_post_json.send_onebot_post_json()
        except:
            self.res = None
        return self.res

    def do_api_async(self):
        this_post_json = send_onebot_post_json_T()
        this_post_json.bot_info = self.bot_info
        this_post_json.obj = self.data
        this_post_json.node_ext = self.node_ext + '_async'
        try:
            self.res = this_post_json.send_onebot_post_json()
        except:
            self.res = None
        return self.res

    def do_api_rate_limited(self):
        this_post_json = send_onebot_post_json_T()
        this_post_json.bot_info = self.bot_info
        this_post_json.obj = self.data
        this_post_json.node_ext = self.node_ext + '_rate_limited'
        try:
            self.res = this_post_json.send_onebot_post_json()
        except:
            self.res = None
        return self.res

    def do_api_get(self):
        if type(self.bot_info) is not bot_info_T or self.bot_info.host == '' or self.bot_info.port == -1 or self.node_ext == '':
            return None
        try:
            tmp_host = self.bot_info.host
            if tmp_host.startswith('http://') or tmp_host.startswith('https://'):
                pass
            else:
                tmp_host = 'http://' + tmp_host
            token_str = ''
            token_dict = {}
            if len(self.bot_info.access_token) > 0:
                token_str = f'?access_token={self.bot_info.access_token}'
                token_dict = {'Authorization': f'Bearer {self.bot_info.access_token}'}
            send_url = f'{self.bot_info.host}:{self.bot_info.port}/{self.node_ext}{token_str}'
            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger is not None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ': GET request')
            headers = {}
            headers.update(token_dict)
            msg_res = req.request("GET", send_url, headers=headers)
            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger is not None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ' - GET succeed: ' + msg_res.text)
            self.res = msg_res
            return msg_res
        except:
            traceback.print_exc()
            self.res = None
            return None

class event(object):
    def __init__(self, raw):
        self.raw = raw
        self.json = self.event_load(raw)
        self.platform = {'sdk': 'onebot', 'platform': 'qq', 'model': 'default'}
        self.active = False
        if self.json is not None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = self.json['time']
            self.base_info['self_id'] = self.json['self_id']
            self.base_info['post_type'] = self.json['post_type']

    def event_load(self, raw):
        try:
            res = json.loads(raw)
        except:
            res = None
        return res


def format_cq_code_msg(msg):
    res = msg
    if type(msg) is str:
        res = msg
    elif type(msg) is list:
        res = ''
        for msg_this in msg:
            if type(msg_this) is dict \
            and 'type' in msg_this \
            and 'data' in msg_this \
            and type(msg_this['data']) is dict:
                if msg_this['type'] == 'text':
                    if 'text' in msg_this['data']:
                        res += msg_this['data']['text']
                elif msg_this['type'] == 'at':
                    if 'qq' in msg_this['data']:
                        cq_params = [f"qq={msg_this['data']['qq']}"]
                        if 'name' in msg_this['data'] and msg_this['data']['name']:
                            cq_params.append(f"name={msg_this['data']['name']}")
                        res += f"[CQ:at,{','.join(cq_params)}]"
                else:
                    res += '[' + ','.join([f"CQ:{msg_this['type']}"] + [f"{key_this}={msg_this['data'][key_this]}" for key_this in msg_this['data']]) + ']'
    return res


# 支持OlivOS API事件生成的映射实现
def get_Event_from_SDK(target_event):
    global gFlagCheckList
    target_event.base_info['time'] = target_event.sdk_event.base_info.get('time', int(time.time()))
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info['self_id'])
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'old_string'
    if target_event.base_info['type'] == 'message_sent':
        """_自身消息事件_
        添加`message_sent`事件,详见:https://docs.go-cqhttp.org/event/#%E6%89%80%E6%9C%89%E4%B8%8A%E6%8A%A5
        """
        if target_event.sdk_event.json['message_type'] == 'private':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message_sent'
            new_msg = format_cq_code_msg(target_event.sdk_event.json['message'])
            target_event.data = target_event.private_message_sent(
                str(target_event.sdk_event.json['user_id']),
                new_msg,
                target_event.sdk_event.json['sub_type']
            )
            target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
            target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
            target_event.data.raw_message = new_msg
            target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
            target_event.data.font = target_event.sdk_event.json['font']
            target_event.data.sender.update(target_event.sdk_event.json['sender'])
            if 'user_id' in target_event.sdk_event.json['sender']:
                target_event.data.sender['id'] = str(target_event.sdk_event.json['sender']['user_id'])
            if 'nickname' in target_event.sdk_event.json['sender']:
                target_event.data.sender['name'] = target_event.sdk_event.json['sender']['nickname']
        elif target_event.sdk_event.json['message_type'] == 'group':
            if target_event.sdk_event.json['sub_type'] == 'normal':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_message_sent'
                new_msg = format_cq_code_msg(target_event.sdk_event.json['message'])
                target_event.data = target_event.group_message_sent(
                    str(target_event.sdk_event.json['group_id']),
                    str(target_event.sdk_event.json['user_id']),
                    new_msg,
                    target_event.sdk_event.json['sub_type']
                )
                target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
                target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
                target_event.data.raw_message = new_msg
                target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
                target_event.data.font = target_event.sdk_event.json['font']
                target_event.data.sender.update(target_event.sdk_event.json['sender'])
                if 'user_id' in target_event.sdk_event.json['sender']:
                    target_event.data.sender['id'] = str(target_event.sdk_event.json['sender']['user_id'])
                if 'nickname' in target_event.sdk_event.json['sender']:
                    target_event.data.sender['name'] = target_event.sdk_event.json['sender']['nickname']
    elif target_event.base_info['type'] == 'message':
        if target_event.sdk_event.json['message_type'] == 'private':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message'
            new_msg = format_cq_code_msg(target_event.sdk_event.json['message'])
            target_event.data = target_event.private_message(
                str(target_event.sdk_event.json['user_id']),
                new_msg,
                target_event.sdk_event.json['sub_type']
            )
            target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
            target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
            target_event.data.raw_message = new_msg
            target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
            target_event.data.font = target_event.sdk_event.json['font']
            target_event.data.sender.update(target_event.sdk_event.json['sender'])
            if 'user_id' in target_event.sdk_event.json['sender']:
                target_event.data.sender['id'] = str(target_event.sdk_event.json['sender']['user_id'])
            if 'nickname' in target_event.sdk_event.json['sender']:
                target_event.data.sender['name'] = target_event.sdk_event.json['sender']['nickname']
        elif target_event.sdk_event.json['message_type'] == 'group':
            if target_event.sdk_event.json['sub_type'] == 'normal':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_message'
                new_msg = format_cq_code_msg(target_event.sdk_event.json['message'])
                target_event.data = target_event.group_message(
                    str(target_event.sdk_event.json['group_id']),
                    str(target_event.sdk_event.json['user_id']),
                    new_msg,
                    target_event.sdk_event.json['sub_type']
                )
                target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
                target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
                target_event.data.raw_message = new_msg
                target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
                target_event.data.font = target_event.sdk_event.json['font']
                target_event.data.sender.update(target_event.sdk_event.json['sender'])
                if 'user_id' in target_event.sdk_event.json['sender']:
                    target_event.data.sender['id'] = str(target_event.sdk_event.json['sender']['user_id'])
                if 'nickname' in target_event.sdk_event.json['sender']:
                    target_event.data.sender['name'] = target_event.sdk_event.json['sender']['nickname']
        elif target_event.sdk_event.json['message_type'] == 'guild':
            if target_event.sdk_event.json['sub_type'] == 'channel':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_message'
                new_msg = format_cq_code_msg(target_event.sdk_event.json['message'])
                target_event.data = target_event.group_message(
                    str(target_event.sdk_event.json['channel_id']),
                    str(target_event.sdk_event.json['user_id']),
                    new_msg,
                    target_event.sdk_event.json['sub_type']
                )
                target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
                target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
                target_event.data.raw_message = new_msg
                target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('old_string', new_msg)
                target_event.data.font = None
                target_event.data.sender.update(target_event.sdk_event.json['sender'])
                if 'user_id' in target_event.sdk_event.json['sender']:
                    target_event.data.sender['id'] = str(target_event.sdk_event.json['sender']['user_id'])
                if 'nickname' in target_event.sdk_event.json['sender']:
                    target_event.data.sender['name'] = target_event.sdk_event.json['sender']['nickname']
                if 'guild_id' in target_event.sdk_event.json:
                    target_event.data.host_id = str(target_event.sdk_event.json['guild_id'])
                    target_event.data.extend['host_group_id'] = str(target_event.sdk_event.json['guild_id'])
                if 'self_tiny_id' in target_event.sdk_event.json:
                    target_event.data.extend['sub_self_id'] = str(target_event.sdk_event.json['self_tiny_id'])
                    if str(target_event.sdk_event.json['user_id']) == str(target_event.sdk_event.json['self_tiny_id']):
                        target_event.active = False
        if target_event.data is not None:
            if target_event.data.raw_message == '':
                target_event.active = False
        else:
            target_event.active = False
    elif target_event.base_info['type'] == 'notice':
        if target_event.sdk_event.json['notice_type'] == 'group_upload':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_file_upload'
            target_event.data = target_event.group_file_upload(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['user_id'])
            )
            target_event.data.file.update(target_event.sdk_event.json['file'])
        elif target_event.sdk_event.json['notice_type'] == 'group_admin':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_admin'
            target_event.data = target_event.group_admin(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['user_id'])
            )
            if target_event.sdk_event.json['sub_type'] == 'set':
                target_event.data.action = 'set'
        elif target_event.sdk_event.json['notice_type'] == 'group_decrease':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_member_decrease'
            target_event.data = target_event.group_member_decrease(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['operator_id']),
                str(target_event.sdk_event.json['user_id'])
            )
            if target_event.sdk_event.json['sub_type'] == 'leave':
                target_event.data.action = 'leave'
            elif target_event.sdk_event.json['sub_type'] == 'kick':
                target_event.data.action = 'kick'
            elif target_event.sdk_event.json['sub_type'] == 'kick_me':
                target_event.data.action = 'kick_me'
        elif target_event.sdk_event.json['notice_type'] == 'group_increase':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_member_increase'
            target_event.data = target_event.group_member_increase(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json.get('operator_id', '-1')),
                str(target_event.sdk_event.json['user_id'])
            )
            if target_event.sdk_event.json['sub_type'] == 'approve':
                target_event.data.action = 'approve'
            elif target_event.sdk_event.json['sub_type'] == 'invite':
                target_event.data.action = 'invite'
        elif target_event.sdk_event.json['notice_type'] == 'group_ban':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_ban'
            target_event.data = target_event.group_ban(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['operator_id']),
                str(target_event.sdk_event.json['user_id']),
                target_event.sdk_event.json['duration']
            )
            if target_event.sdk_event.json['sub_type'] == 'ban':
                target_event.data.action = 'ban'
        elif target_event.sdk_event.json['notice_type'] == 'friend_add':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'friend_add'
            target_event.data = target_event.friend_add(
                str(target_event.sdk_event.json['user_id'])
            )
        elif target_event.sdk_event.json['notice_type'] == 'group_recall':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message_recall'
            target_event.data = target_event.group_message_recall(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['operator_id']),
                str(target_event.sdk_event.json['user_id']),
                str(target_event.sdk_event.json['message_id'])
            )
        elif target_event.sdk_event.json['notice_type'] == 'friend_recall':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message_recall'
            target_event.data = target_event.private_message_recall(
                str(target_event.sdk_event.json['user_id']),
                str(target_event.sdk_event.json['message_id'])
            )
        elif target_event.sdk_event.json['notice_type'] == 'notify':
            if target_event.sdk_event.json['sub_type'] == 'poke':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'poke'
                target_event.data = target_event.poke(
                    str(target_event.sdk_event.json['user_id']),
                    str(target_event.sdk_event.json['target_id'])
                )
                if 'group_id' in target_event.sdk_event.json:
                    target_event.data.group_id = str(target_event.sdk_event.json['group_id'])
                if target_event.data.group_id == '-1':
                    target_event.data.group_id = None
            elif target_event.sdk_event.json['sub_type'] == 'lucky_king':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_lucky_king'
                target_event.data = target_event.group_lucky_king(
                    str(target_event.sdk_event.json['group_id']),
                    str(target_event.sdk_event.json['user_id']),
                    str(target_event.sdk_event.json['target_id'])
                )
            elif target_event.sdk_event.json['sub_type'] == 'honor':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_honor'
                target_event.data = target_event.group_honor(
                    str(target_event.sdk_event.json['group_id']),
                    str(target_event.sdk_event.json['user_id'])
                )
                if target_event.sdk_event.json['honor_type'] == 'talkative':
                    target_event.data.type = 'talkative'
                elif target_event.sdk_event.json['honor_type'] == 'performer':
                    target_event.data.type = 'performer'
                elif target_event.sdk_event.json['honor_type'] == 'emotion':
                    target_event.data.type = 'emotion'
    elif target_event.base_info['type'] == 'request':
        if 'flag' in target_event.sdk_event.json:
            tmp_flag = target_event.sdk_event.json['flag']
            if tmp_flag not in gFlagCheckList:
                gFlagCheckList.append(tmp_flag)
                if target_event.sdk_event.json['request_type'] == 'friend':
                    target_event.active = True
                    target_event.plugin_info['func_type'] = 'friend_add_request'
                    target_event.data = target_event.friend_add_request(
                        str(target_event.sdk_event.json['user_id']),
                        target_event.sdk_event.json['comment']
                    )
                    target_event.data.flag = tmp_flag
                elif target_event.sdk_event.json['request_type'] == 'group':
                    if target_event.sdk_event.json['sub_type'] == 'add':
                        target_event.active = True
                        target_event.plugin_info['func_type'] = 'group_add_request'
                        target_event.data = target_event.group_add_request(
                            str(target_event.sdk_event.json['group_id']),
                            str(target_event.sdk_event.json['user_id']),
                            target_event.sdk_event.json['comment']
                        )
                        target_event.data.flag = tmp_flag
                    elif target_event.sdk_event.json['sub_type'] == 'invite':
                        target_event.active = True
                        target_event.plugin_info['func_type'] = 'group_invite_request'
                        target_event.data = target_event.group_invite_request(
                            str(target_event.sdk_event.json['group_id']),
                            str(target_event.sdk_event.json['user_id']),
                            target_event.sdk_event.json['comment']
                        )
                        target_event.data.flag = tmp_flag
    elif target_event.base_info['type'] == 'meta_event':
        if target_event.sdk_event.json['meta_event_type'] == 'lifecycle':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'lifecycle'
            target_event.data = target_event.lifecycle()
            if target_event.sdk_event.json['sub_type'] == 'enable':
                target_event.data.action = 'enable'
            elif target_event.sdk_event.json['sub_type'] == 'disable':
                target_event.data.action = 'disable'
            elif target_event.sdk_event.json['sub_type'] == 'connect':
                target_event.data.action = 'connect'
        elif target_event.sdk_event.json['meta_event_type'] == 'heartbeat':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'heartbeat'
            target_event.data = target_event.heartbeat(
                target_event.sdk_event.json['interval']
            )

def formatMessage(data:str, msgType:str = 'para'):
    res = data
    data_obj = OlivOS.messageAPI.Message_templet(
        mode_rx = 'old_string',
        data_raw = data
    )
    for data_obj_this in data_obj.data:
        if type(data_obj_this) is OlivOS.messageAPI.PARA.image:
            if data_obj_this.data['url'] != None:
                data_obj_this.data['file'] = data_obj_this.data['url']
                data_obj_this.data['url'] = None
            url_path = data_obj_this.data['file']
            if not url_path.startswith("base64://"):
                url_parsed = parse.urlparse(url_path)
                if url_parsed.scheme not in ["http", "https"]:
                    file_path = url_parsed.path
                    if not os.path.isabs(file_path):
                        file_path = OlivOS.contentAPI.resourcePathTransform('images', file_path)
                        if os.path.exists(file_path):
                            data_obj_this.data['file'] = 'file:///%s' % file_path
    if msgType == 'para':
        res = paraMapper(paraList = data_obj.data, msgType = 'para')
    else:
        res = data_obj.get('old_string')
    return res


def paraMapper(paraList, msgType='para'):
    res = []
    if 'para' == msgType:
        for para in paraList:
            tmp_para = para.__dict__
            if para.type == 'at':
                tmp_para = {}
                tmp_para['type'] = 'at'
                tmp_para['data'] = {}
                tmp_para['data']['qq'] = para.data['id']
            res.append(tmp_para)
    elif 'msg' == msgType:
        res = ''
        for para in paraList:
            res += para.CQ()
    return res

# 支持OlivOS API调用的方法实现
class event_action(object):
    def reply_private_msg(target_event, message):
        event_action.send_private_msg(
            target_event = target_event,
            user_id = target_event.data.user_id,
            message = message
        )

    def reply_group_msg(target_event, message):
        event_action.send_group_msg(
            target_event = target_event,
            user_id = target_event.data.group_id,
            message = message
        )

    def send_private_msg(target_event, user_id, message):
        global paraMsgMap
        msgType = 'msg'
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'private'
        this_msg.data.user_id = str(user_id)
        if target_event.bot_info.platform['model'] in paraMsgMap:
            msgType = 'para'
        this_msg.data.message = formatMessage(data = message, msgType = msgType)
        this_msg.do_api()

    def send_group_msg(target_event, group_id, message):
        global paraMsgMap
        msgType = 'msg'
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'group'
        this_msg.data.group_id = str(group_id)
        if hasattr(this_msg.data, 'user_id'):
            del this_msg.data.user_id
        if target_event.bot_info.platform['model'] in paraMsgMap:
            msgType = 'para'
        this_msg.data.message = formatMessage(data = message, msgType = msgType)
        this_msg.do_api()

    def delete_msg(target_event, message_id):
        this_msg = api.delete_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_id = str(message_id)
        this_msg.do_api()

    def get_msg(target_event, message_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_msg()
        raw_obj = None
        this_msg = api.get_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_id = str(message_id)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['message_id'] = str(init_api_do_mapping_for_dict(raw_obj, ['message_id'], int))
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['real_id'], int))
                res_data['data']['sender']['id'] = str(
                    init_api_do_mapping_for_dict(raw_obj, ['sender', 'user_id'], int))
                res_data['data']['sender']['name'] = init_api_do_mapping_for_dict(raw_obj, ['sender', 'nickname'], str)
                res_data['data']['sender']['user_id'] = str(
                    init_api_do_mapping_for_dict(raw_obj, ['sender', 'user_id'], int))
                res_data['data']['sender']['nickname'] = init_api_do_mapping_for_dict(raw_obj, ['sender', 'nickname'],
                                                                                      str)
                res_data['data']['time'] = init_api_do_mapping_for_dict(raw_obj, ['time'], int)
                res_data['data']['message'] = init_api_do_mapping_for_dict(raw_obj, ['message'], str)
                res_data['data']['raw_message'] = init_api_do_mapping_for_dict(raw_obj, ['raw_message'], str)
        return res_data

    def get_forward_msg(target_event, message_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_forward_msg()
        raw_obj = None
        this_msg = api.get_forward_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.id = str(message_id)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['messages'] = init_api_do_mapping_for_dict(raw_obj, ['messages'], list)
        return res_data

    def send_group_forward_msg(target_event, group_id, messages):
        this_msg = api.send_group_forward_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.messages = messages
        this_msg.do_api()

    def send_private_forward_msg(target_event, user_id, messages):
        this_msg = api.send_private_forward_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.user_id = int(user_id)
        this_msg.data.messages = messages
        this_msg.do_api()

    def set_essence_msg(target_event, message_id):
        this_msg = api.set_essence_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_id = int(message_id)
        this_msg.do_api()

    def delete_essence_msg(target_event, message_id):
        this_msg = api.delete_essence_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_id = int(message_id)
        this_msg.do_api()

    def send_like(target_event, user_id, times=1):
        this_msg = api.send_like(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.user_id = int(user_id)
        this_msg.data.times = times
        this_msg.do_api()

    def send_group_sign(target_event, group_id):
        model = target_event.bot_info.platform['model']
        if model in lagrangeModelMap:
            return
        this_msg = api.send_group_sign(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.do_api()

    def set_group_kick(target_event, group_id, user_id, rehect_add_request=False):
        this_msg = api.set_group_kick(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.rehect_add_request = rehect_add_request
        this_msg.do_api()

    def set_group_ban(target_event, group_id, user_id, duration=1800):
        this_msg = api.set_group_ban(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.duration = duration
        this_msg.do_api()

    def set_group_anonymous_ban(target_event, group_id, anonymous, anonymous_flag, duration=1800):
        this_msg = api.set_group_anonymous_ban(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.anonymous = anonymous
        this_msg.data.anonymous_flag = anonymous_flag
        this_msg.data.duration = duration
        this_msg.do_api()

    def set_group_whole_ban(target_event, group_id, enable):
        this_msg = api.set_group_whole_ban(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.enable = enable
        this_msg.do_api()

    def set_group_admin(target_event, group_id, user_id, enable):
        this_msg = api.set_group_admin(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.enable = enable
        this_msg.do_api()

    def set_group_anonymous(target_event, group_id, enable):
        this_msg = api.set_group_anonymous(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.enable = enable
        this_msg.do_api()

    def set_group_card(target_event, group_id, user_id, card):
        this_msg = api.set_group_card(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.card = card
        this_msg.do_api()

    def set_group_name(target_event, group_id, group_name):
        this_msg = api.set_group_name(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.group_name = group_name
        this_msg.do_api()

    def set_group_leave(target_event, group_id, is_dismiss=False):
        this_msg = api.set_group_leave(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.is_dismiss = is_dismiss
        this_msg.do_api()

    def set_group_special_title(target_event, group_id, user_id, special_title, duration):
        model = target_event.bot_info.platform['model']
        this_msg = api.set_group_special_title(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.special_title = special_title
        # llonebot 和 napcat 不需要 duration 参数
        if model not in llonebotModelMap and model not in napcatModelMap:
            this_msg.data.duration = duration
        this_msg.do_api()

    def set_friend_add_request(target_event, flag, approve, remark):
        this_msg = api.set_friend_add_request(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.flag = flag
        this_msg.data.approve = approve
        this_msg.data.remark = remark
        this_msg.do_api()

    def set_group_add_request(target_event, flag, sub_type, approve, reason):
        this_msg = api.set_group_add_request(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.flag = flag
        this_msg.data.sub_type = sub_type
        this_msg.data.approve = approve
        this_msg.data.reason = reason
        this_msg.do_api()

    def get_login_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        raw_obj = None
        this_msg = api.get_login_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['nickname'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['user_id'], int))
        return res_data

    def get_stranger_info(target_event, user_id, no_cache=False):
        res_data = OlivOS.contentAPI.api_result_data_template.get_stranger_info()
        raw_obj = None
        this_msg = api.get_stranger_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.user_id = int(user_id)
        this_msg.data.no_cache = no_cache
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['nickname'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['user_id'], int))
        return res_data

    def get_friend_list(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_friend_list()
        raw_obj = None
        this_msg = api.get_friend_list(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_user_info_strip()
                    tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['nickname'], str)
                    tmp_res_data_this['id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['user_id'], int))
                    res_data['data'].append(tmp_res_data_this)
        return res_data

    def get_group_info(target_event, group_id, no_cache=False):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_info()
        raw_obj = None
        this_msg = api.get_group_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.no_cache = no_cache
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['group_name'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['group_id'], int))
                res_data['data']['memo'] = init_api_do_mapping_for_dict(raw_obj, ['group_memo'], str)
                res_data['data']['member_count'] = init_api_do_mapping_for_dict(raw_obj, ['member_count'], int)
                res_data['data']['max_member_count'] = init_api_do_mapping_for_dict(raw_obj, ['max_member_count'], int)
        return res_data

    def get_group_list(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_list()
        raw_obj = None
        this_msg = api.get_group_list(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_info_strip()
                    tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['group_name'], str)
                    tmp_res_data_this['id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['group_id'], int))
                    tmp_res_data_this['memo'] = init_api_do_mapping_for_dict(raw_obj_this, ['group_memo'], str)
                    tmp_res_data_this['member_count'] = init_api_do_mapping_for_dict(raw_obj_this, ['member_count'],
                                                                                     int)
                    tmp_res_data_this['max_member_count'] = init_api_do_mapping_for_dict(raw_obj_this,
                                                                                         ['max_member_count'], int)
                    res_data['data'].append(tmp_res_data_this)
        return res_data

    def get_group_member_info(target_event, group_id, user_id, no_cache=False):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_info()
        raw_obj = None
        this_msg = api.get_group_member_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.no_cache = no_cache
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['nickname'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['user_id'], int))
                res_data['data']['user_id'] = str(init_api_do_mapping_for_dict(raw_obj, ['user_id'], int))
                res_data['data']['group_id'] = str(init_api_do_mapping_for_dict(raw_obj, ['group_id'], int))
                res_data['data']['times']['join_time'] = init_api_do_mapping_for_dict(raw_obj, ['join_time'], int)
                res_data['data']['times']['last_sent_time'] = init_api_do_mapping_for_dict(raw_obj, ['last_sent_time'],
                                                                                           int)
                res_data['data']['times']['shut_up_timestamp'] = init_api_do_mapping_for_dict(raw_obj,
                                                                                              ['shut_up_timestamp'],
                                                                                              int)
                res_data['data']['role'] = init_api_do_mapping_for_dict(raw_obj, ['role'], str)
                res_data['data']['card'] = init_api_do_mapping_for_dict(raw_obj, ['card'], str)
                res_data['data']['title'] = init_api_do_mapping_for_dict(raw_obj, ['title'], str)
        return res_data

    def get_group_member_list(target_event, group_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_list()
        raw_obj = None
        this_msg = api.get_group_member_list(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_member_info_strip()
                    tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['nickname'], str)
                    tmp_res_data_this['id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['user_id'], int))
                    tmp_res_data_this['user_id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['user_id'], int))
                    tmp_res_data_this['group_id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['group_id'], int))
                    tmp_res_data_this['times']['join_time'] = init_api_do_mapping_for_dict(raw_obj_this, ['join_time'],
                                                                                           int)
                    tmp_res_data_this['times']['last_sent_time'] = init_api_do_mapping_for_dict(raw_obj_this,
                                                                                                ['last_sent_time'], int)
                    tmp_res_data_this['times']['shut_up_timestamp'] = init_api_do_mapping_for_dict(raw_obj_this, [
                        'shut_up_timestamp'], int)
                    tmp_res_data_this['role'] = init_api_do_mapping_for_dict(raw_obj_this, ['role'], str)
                    tmp_res_data_this['card'] = init_api_do_mapping_for_dict(raw_obj_this, ['card'], str)
                    tmp_res_data_this['title'] = init_api_do_mapping_for_dict(raw_obj_this, ['title'], str)
                    res_data['data'].append(tmp_res_data_this)
        return res_data

    def can_send_image(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.can_send_image()
        raw_obj = None
        this_msg = api.can_send_image(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['yes'] = init_api_do_mapping_for_dict(raw_obj, ['yes'], bool)
        return res_data

    def can_send_record(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.can_send_record()
        raw_obj = None
        this_msg = api.can_send_record(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['yes'] = init_api_do_mapping_for_dict(raw_obj, ['yes'], bool)
        return res_data

    def get_status(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_status()
        raw_obj = None
        this_msg = api.get_status(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['online'] = init_api_do_mapping_for_dict(raw_obj, ['online'], bool)
                res_data['data']['status']['packet_received'] = init_api_do_mapping_for_dict(raw_obj, ['stat',
                                                                                                       'packet_received'],
                                                                                             int)
                res_data['data']['status']['packet_sent'] = init_api_do_mapping_for_dict(raw_obj,
                                                                                         ['stat', 'packet_sent'], int)
                res_data['data']['status']['packet_lost'] = init_api_do_mapping_for_dict(raw_obj,
                                                                                         ['stat', 'packet_lost'], int)
                res_data['data']['status']['message_received'] = init_api_do_mapping_for_dict(raw_obj, ['stat',
                                                                                                        'message_received'],
                                                                                              int)
                res_data['data']['status']['message_sent'] = init_api_do_mapping_for_dict(raw_obj,
                                                                                          ['stat', 'message_sent'], int)
                res_data['data']['status']['disconnect_times'] = init_api_do_mapping_for_dict(raw_obj, ['stat',
                                                                                                        'disconnect_times'],
                                                                                              int)
                res_data['data']['status']['lost_times'] = init_api_do_mapping_for_dict(raw_obj, ['stat', 'lost_times'],
                                                                                        int)
                res_data['data']['status']['last_message_time'] = init_api_do_mapping_for_dict(raw_obj, ['stat',
                                                                                                         'last_message_time'],
                                                                                               int)
        return res_data

    def get_version_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_version_info()
        raw_obj = None
        this_msg = api.get_version_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['app_name'], str)
                res_data['data']['version_full'] = init_api_do_mapping_for_dict(raw_obj, ['app_full_name'], str)
                res_data['data']['version'] = init_api_do_mapping_for_dict(raw_obj, ['app_version'], str)
                res_data['data']['path'] = init_api_do_mapping_for_dict(raw_obj, ['coolq_directory'], str)
                res_data['data']['os'] = init_api_do_mapping_for_dict(raw_obj, ['runtime_os'], str)
        return res_data

    # 以下为 go-cqhttp v1.0.0-beta8-fix1 引入的试验性接口

    def send_guild_channel_msg(target_event, guild_id, channel_id, message):
        this_msg = api.send_guild_channel_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.guild_id = int(guild_id)
        this_msg.data.channel_id = int(channel_id)
        this_msg.data.message = message
        this_msg.do_api()

    def get_guild_member_profile(target_event, guild_id, user_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_info()
        raw_obj = None
        this_msg = api.get_guild_member_profile(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.guild_id = int(guild_id)
        this_msg.data.user_id = int(user_id)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['nickname'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['tiny_id'], str))
                res_data['data']['user_id'] = str(init_api_do_mapping_for_dict(raw_obj, ['tiny_id'], str))
                res_data['data']['group_id'] = str(guild_id)
                res_data['data']['times']['join_time'] = init_api_do_mapping_for_dict(raw_obj, ['join_time'], int)
                res_data['data']['times']['last_sent_time'] = 0
                res_data['data']['times']['shut_up_timestamp'] = 0
                res_data['data']['role'] = 'admin'
                res_data['data']['card'] = init_api_do_mapping_for_dict(raw_obj, ['nickname'], str)
                res_data['data']['title'] = ''
        return res_data

    def get_group_notice(target_event, group_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_notice()
        raw_obj = None
        this_msg = api.get_group_notice(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                model = target_event.bot_info.platform['model']
                for raw_obj_this in raw_obj:
                    item = {}
                    item['sender_id'] = init_api_do_mapping_for_dict(raw_obj_this, ['sender_id'], int)
                    item['publish_time'] = init_api_do_mapping_for_dict(raw_obj_this, ['publish_time'], int)
                    item['message'] = init_api_do_mapping_for_dict(raw_obj_this, ['message'], dict)
                    item['notice_id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['notice_id'], str))
                    item['extra'] = {}
                    if model in napcatModelMap or model in lagrangeModelMap:
                        item['extra']['notice_id_type'] = 'string'
                    else:
                        item['extra']['notice_id_type'] = 'int'
                    res_data['data'].append(item)
        return res_data

    def send_group_notice(target_event, group_id, content, image=None, **kwargs):
        model = target_event.bot_info.platform['model']
        this_msg = api.send_group_notice(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.content = str(content)
        if image is not None:
            this_msg.data.image = str(image)
        # NapCat 额外参数
        if model in napcatModelMap:
            if 'pinned' in kwargs and kwargs['pinned'] is not None:
                this_msg.data.pinned = kwargs['pinned']
            if 'type' in kwargs and kwargs['type'] is not None:
                this_msg.data.type = kwargs['type']
            if 'confirm_required' in kwargs and kwargs['confirm_required'] is not None:
                this_msg.data.confirm_required = kwargs['confirm_required']
            if 'is_show_edit_card' in kwargs and kwargs['is_show_edit_card'] is not None:
                this_msg.data.is_show_edit_card = kwargs['is_show_edit_card']
            if 'tip_window_type' in kwargs and kwargs['tip_window_type'] is not None:
                this_msg.data.tip_window_type = kwargs['tip_window_type']
        this_msg.do_api()

    def del_group_notice(target_event, group_id, notice_id):
        """删除群公告（仅 NapCat 和 Lagrange）"""
        model = target_event.bot_info.platform['model']
        if model not in napcatModelMap and model not in lagrangeModelMap:
            return
        this_msg = api.del_group_notice(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.notice_id = str(notice_id)
        this_msg.do_api()

    def upload_group_file(target_event, group_id, file, name='', folder_id=None):
        this_msg = api.upload_group_file(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.file = file
        if name:
            this_msg.data.name = name
        if folder_id is not None:
            this_msg.data.folder_id = folder_id
        this_msg.do_api()

    def delete_group_file(target_event, group_id, file_id, name=None):
        model = target_event.bot_info.platform['model']
        this_msg = api.delete_group_file(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        # llonebot 和 napcat 没有 parent_id
        if model in llonebotModelMap or model in napcatModelMap:
            this_msg.data.file_id = str(file_id)
        else:
            this_msg.data.file_id = str(file_id)
            this_msg.data.parent_id = '/'
        this_msg.do_api()

    def create_group_file_folder(target_event, group_id, name, parent_id='/'):
        this_msg = api.create_group_file_folder(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.name = name
        this_msg.data.parent_id = parent_id
        this_msg.do_api()

    def delete_group_folder(target_event, group_id, folder_id):
        this_msg = api.delete_group_folder(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.folder_id = str(folder_id)
        this_msg.do_api()

    def get_group_file_system_info(target_event, group_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_file_system_info()
        raw_obj = None
        this_msg = api.get_group_file_system_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['file_count'] = init_api_do_mapping_for_dict(raw_obj, ['file_count'], int)
                res_data['data']['limit_count'] = init_api_do_mapping_for_dict(raw_obj, ['limit_count'], int)
                res_data['data']['used_space'] = init_api_do_mapping_for_dict(raw_obj, ['used_space'], int)
                res_data['data']['total_space'] = init_api_do_mapping_for_dict(raw_obj, ['total_space'], int)
        return res_data

    def get_group_root_files(target_event, group_id, file_count=None):
        model = target_event.bot_info.platform['model']
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_root_files()
        raw_obj = None
        this_msg = api.get_group_root_files(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        # napcat 支持 file_count 参数
        if model in napcatModelMap and file_count is not None:
            this_msg.data.file_count = int(file_count)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['files'] = init_api_do_mapping_for_dict(raw_obj, ['files'], list)
                res_data['data']['folders'] = init_api_do_mapping_for_dict(raw_obj, ['folders'], list)
        return res_data

    def get_group_files_by_folder(target_event, group_id, folder_id, file_count=None):
        model = target_event.bot_info.platform['model']
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_files_by_folder()
        raw_obj = None
        this_msg = api.get_group_files_by_folder(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.folder_id = str(folder_id)
        # napcat 支持 file_count 参数
        if model in napcatModelMap and file_count is not None:
            this_msg.data.file_count = int(file_count)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['files'] = init_api_do_mapping_for_dict(raw_obj, ['files'], list)
                res_data['data']['folders'] = init_api_do_mapping_for_dict(raw_obj, ['folders'], list)
        return res_data

    def get_group_file_url(target_event, group_id, file_id, busid):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_file_url()
        raw_obj = None
        this_msg = api.get_group_file_url(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.file_id = str(file_id)
        this_msg.data.busid = int(busid)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['url'] = init_api_do_mapping_for_dict(raw_obj, ['url'], str)
        return res_data

    def upload_private_file(target_event, user_id, file, name):
        this_msg = api.upload_private_file(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.user_id = int(user_id)
        this_msg.data.file = file
        this_msg.data.name = name
        this_msg.do_api()

    # 这里是三协议新引入的接口，以 LLOneBot 为主，NapCat 和 Lagrange 兼容实现
    def rename_group_file_folder(target_event, group_id, folder_id, new_folder_name):
        """重命名群文件夹（仅 LLOneBot 和 Lagrange）"""
        model = target_event.bot_info.platform['model']
        if model not in llonebotModelMap and model not in lagrangeModelMap:
            return
        this_msg = api.rename_group_file_folder(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.folder_id = str(folder_id)
        this_msg.data.new_folder_name = str(new_folder_name)
        this_msg.do_api()

    def rename_group_file(target_event, group_id, file_id, current_parent_directory, new_name):
        """重命名群文件（仅 NapCat）"""
        model = target_event.bot_info.platform['model']
        if model not in napcatModelMap:
            return
        this_msg = api.rename_group_file(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.file_id = str(file_id)
        this_msg.data.current_parent_directory = str(current_parent_directory)
        this_msg.data.new_name = str(new_name)
        this_msg.do_api()

    def set_group_file_forever(target_event, group_id, file_id):
        """群文件转永久（仅 LLOneBot 和 NapCat）"""
        model = target_event.bot_info.platform['model']
        if model not in llonebotModelMap and model not in napcatModelMap:
            return
        if model in llonebotModelMap:
            this_msg = api.set_group_file_forever(get_SDK_bot_info_from_Event(target_event))
        elif model in napcatModelMap:
            this_msg = api.trans_group_file(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.file_id = str(file_id)
        this_msg.do_api()
    
    def get_essence_msg_list(target_event, group_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_essence_msg_list()
        raw_obj = None
        this_msg = api.get_essence_msg_list(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                model = target_event.bot_info.platform['model']
                for raw_obj_this in raw_obj:
                    item = {}
                    # LLOneBot 字段作为主要标准
                    item['sender_id'] = init_api_do_mapping_for_dict(raw_obj_this, ['sender_id'], int)
                    item['sender_nick'] = init_api_do_mapping_for_dict(raw_obj_this, ['sender_nick'], str)
                    item['sender_time'] = init_api_do_mapping_for_dict(raw_obj_this, ['sender_time'], int)
                    item['operator_id'] = init_api_do_mapping_for_dict(raw_obj_this, ['operator_id'], int)
                    item['operator_nick'] = init_api_do_mapping_for_dict(raw_obj_this, ['operator_nick'], str)
                    item['operator_time'] = init_api_do_mapping_for_dict(raw_obj_this, ['operator_time'], int)
                    item['message_id'] = init_api_do_mapping_for_dict(raw_obj_this, ['message_id'], int)
                    item['message'] = init_api_do_mapping_for_dict(raw_obj_this, ['message'], str)
                    item['wording'] = init_api_do_mapping_for_dict(raw_obj_this, ['wording'], str)
                    item['extra'] = {}
                    if model in napcatModelMap:
                        # NapCat 独有字段
                        item['extra']['msg_seq'] = init_api_do_mapping_for_dict(raw_obj_this, ['msg_seq'], int)
                        item['extra']['msg_random'] = init_api_do_mapping_for_dict(raw_obj_this, ['msg_random'], int)
                        item['extra']['content'] = init_api_do_mapping_for_dict(raw_obj_this, ['content'], list)
                    elif model in lagrangeModelMap:
                        # Lagrange 独有字段
                        item['extra']['content'] = init_api_do_mapping_for_dict(raw_obj_this, ['content'], list)
                    res_data['data'].append(item)
        return res_data

    def get_group_ignore_add_request(target_event, group_id=None):
        """获取已过滤的加群通知（仅 NapCat）"""
        model = target_event.bot_info.platform['model']
        if model not in napcatModelMap:
            return
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_ignore_add_request()
        raw_obj = None
        this_msg = api.get_group_ignore_add_request(get_SDK_bot_info_from_Event(target_event))
        if group_id is not None:
            this_msg.data.group_id = int(group_id)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    item = {}
                    item['request_id'] = init_api_do_mapping_for_dict(raw_obj_this, ['request_id'], int)
                    item['invitor_uin'] = init_api_do_mapping_for_dict(raw_obj_this, ['invitor_uin'], int)
                    item['invitor_nick'] = init_api_do_mapping_for_dict(raw_obj_this, ['invitor_nick'], str)
                    item['group_id'] = init_api_do_mapping_for_dict(raw_obj_this, ['group_id'], int)
                    item['group_name'] = init_api_do_mapping_for_dict(raw_obj_this, ['group_name'], str)
                    item['checked'] = init_api_do_mapping_for_dict(raw_obj_this, ['checked'], bool)
                    item['actor'] = init_api_do_mapping_for_dict(raw_obj_this, ['actor'], int)
                    item['requester_nick'] = init_api_do_mapping_for_dict(raw_obj_this, ['requester_nick'], str)
                    item['message'] = init_api_do_mapping_for_dict(raw_obj_this, ['message'], str)
        return res_data

    def get_doubt_friends_add_request(target_event, count=50):
        """获取被过滤的好友请求（仅 LLOneBot 和 NapCat）"""
        model = target_event.bot_info.platform['model']
        if model not in llonebotModelMap and model not in napcatModelMap:
            return
        res_data = OlivOS.contentAPI.api_result_data_template.get_doubt_friends_add_request()
        raw_obj = None
        this_msg = api.get_doubt_friends_add_request(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.count = int(count)
        this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    item = {}
                    # 以 LLOneBot 字段为主
                    item['flag'] = init_api_do_mapping_for_dict(raw_obj_this, ['flag'], str)
                    item['uin'] = init_api_do_mapping_for_dict(raw_obj_this, ['uin'], str)
                    item['nick'] = init_api_do_mapping_for_dict(raw_obj_this, ['nick'], str)
                    item['source'] = init_api_do_mapping_for_dict(raw_obj_this, ['source'], str)
                    item['reason'] = init_api_do_mapping_for_dict(raw_obj_this, ['reason'], str)
                    item['msg'] = init_api_do_mapping_for_dict(raw_obj_this, ['msg'], str)
                    item['group_code'] = init_api_do_mapping_for_dict(raw_obj_this, ['group_code'], str)
                    item['time'] = init_api_do_mapping_for_dict(raw_obj_this, ['time'], str)
                    item['type'] = init_api_do_mapping_for_dict(raw_obj_this, ['type'], str)
                    item['extra'] = {}
                    # 平台特有字段放在 extra 中（目前两个平台字段相同）
                    res_data['data'].append(item)
        return res_data

    def get_group_system_msg(target_event, count=50):
        """获取群系统消息（仅 LLOneBot 和 NapCat，LLOneBot 的已过滤在这里看）"""
        model = target_event.bot_info.platform['model']
        if model not in llonebotModelMap and model not in napcatModelMap:
            return
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_system_msg()
        raw_obj = None
        this_msg = api.get_group_system_msg(get_SDK_bot_info_from_Event(target_event))
        # LLOneBot 使用 GET，NapCat 使用 POST
        if model in llonebotModelMap:
            this_msg.do_api_get()
        elif model in napcatModelMap:
            this_msg.data.count = int(count)
            this_msg.do_api()
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj is not None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                # 处理邀请加群申请
                if 'invited_requests' in raw_obj or 'InvitedRequest' in raw_obj:
                    invited_key = 'invited_requests' if 'invited_requests' in raw_obj else 'InvitedRequest'
                    invited_list = init_api_do_mapping_for_dict(raw_obj, [invited_key], list)
                    if invited_list:
                        res_data['data']['invited_requests'] = invited_list
                # 处理加群申请
                if 'join_requests' in raw_obj:
                    join_list = init_api_do_mapping_for_dict(raw_obj, ['join_requests'], list)
                    if join_list:
                        res_data['data']['join_requests'] = join_list
        return res_data

    def set_doubt_friends_add_request(target_event, flag, approve=True):
        """处理被过滤的好友请求（仅 LLOneBot 和 NapCat）"""
        model = target_event.bot_info.platform['model']
        if model not in llonebotModelMap and model not in napcatModelMap:
            return
        this_msg = api.set_doubt_friends_add_request(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.flag = str(flag)
        if model in napcatModelMap:
            this_msg.data.approve = approve
        this_msg.do_api()

    def group_poke(target_event, group_id, user_id):
        model = target_event.bot_info.platform['model']
        if model in napcatModelMap or model in lagrangeModelMap or model in llonebotModelMap:
            this_msg = api.group_poke(get_SDK_bot_info_from_Event(target_event))
            this_msg.data.group_id = int(group_id)
            this_msg.data.user_id = int(user_id)
            this_msg.do_api()

    def friend_poke(target_event, user_id):
        model = target_event.bot_info.platform['model']
        if model in napcatModelMap or model in lagrangeModelMap or model in llonebotModelMap:
            this_msg = api.friend_poke(get_SDK_bot_info_from_Event(target_event))
            this_msg.data.user_id = int(user_id)
            this_msg.do_api()
            
    def set_msg_emoji_like(target_event, message_id, emoji_id, is_set=True, group_id=None):
        model = target_event.bot_info.platform['model']
        
        if model in lagrangeModelMap:
            # Lagrange 用 set_group_reaction
            this_msg = api.set_group_reaction(get_SDK_bot_info_from_Event(target_event))
            if group_id is None:
                raise ValueError("Lagrange model requires group_id parameter")
            this_msg.data.group_id = int(group_id)
            this_msg.data.message_id = int(message_id)
            this_msg.data.code = str(emoji_id)
            this_msg.data.is_add = is_set
            this_msg.do_api()
            
        elif model in napcatModelMap:
            # NapCat 用 set_msg_emoji_like
            this_msg = api.set_msg_emoji_like(get_SDK_bot_info_from_Event(target_event))
            this_msg.data.message_id = int(message_id)
            this_msg.data.emoji_id = int(emoji_id)
            this_msg.data.set = is_set
            this_msg.do_api()
            
        elif model in llonebotModelMap:
            # LLOneBot 用 set_msg_emoji_like，根据 is_set 使用不同的 API
            if is_set:
                this_msg = api.set_msg_emoji_like(get_SDK_bot_info_from_Event(target_event))
                this_msg.data.message_id = int(message_id)
                this_msg.data.emoji_id = int(emoji_id)
                this_msg.do_api()
            else:
                this_msg = api.unset_msg_emoji_like(get_SDK_bot_info_from_Event(target_event))
                this_msg.data.message_id = int(message_id)
                this_msg.data.emoji_id = int(emoji_id)
                this_msg.do_api()


def init_api_json(raw_str):
    res_data = None
    tmp_obj = None
    flag_is_active = False
    try:
        tmp_obj = json.loads(raw_str)
    except:
        tmp_obj = None
    if type(tmp_obj) == dict:
        if 'status' in tmp_obj:
            if type(tmp_obj['status']) == str:
                if tmp_obj['status'] == 'ok':
                    flag_is_active = True
        if 'retcode' in tmp_obj:
            if type(tmp_obj['retcode']) == int:
                if tmp_obj['retcode'] == 0:
                    flag_is_active = True
    if flag_is_active:
        if 'data' in tmp_obj:
            if type(tmp_obj['data']) == dict:
                res_data = tmp_obj['data'].copy()
            elif type(tmp_obj['data']) == list:
                res_data = tmp_obj['data'].copy()
    return res_data


def init_api_do_mapping(src_type, src_data):
    if type(src_data) == src_type:
        return src_data


def init_api_do_mapping_for_dict(src_data, path_list, src_type):
    res_data = None
    flag_active = True
    tmp_src_data = src_data
    for path_list_this in path_list:
        if type(tmp_src_data) == dict:
            if path_list_this in tmp_src_data:
                tmp_src_data = tmp_src_data[path_list_this]
            else:
                return None
        else:
            return None
    res_data = init_api_do_mapping(src_type, tmp_src_data)
    return res_data


# onebot协议标准api调用实现
class api(object):
    class send_private_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_private_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.user_id = -1
                self.message = ''
                self.auto_escape = False

    class send_group_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_group_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.message = ''
                self.auto_escape = False

    class send_group_forward_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_group_forward_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.messages = ''

    class send_private_forward_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_private_forward_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.user_id = -1
                self.messages = ''

    class send_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.message_type = ''
                self.user_id = -1
                self.group_id = -1
                self.message = ''
                self.auto_escape = False

    class delete_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'delete_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.message_id = -1

    class get_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.message_id = -1

    class get_forward_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_forward_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.id = -1

    class set_essence_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_essence_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.message_id = -1

    class delete_essence_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'delete_essence_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.message_id = -1

    class send_like(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_like'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.user_id = -1
                self.times = 1

    class send_group_sign(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_group_sign'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1

    class group_poke(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'group_poke'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1

    class friend_poke(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'friend_poke'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.user_id = -1

    class set_group_kick(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_kick'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.rehect_add_request = False

    class set_group_ban(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_ban'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.duration = 1800

    class set_group_anonymous_ban(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_anonymous_ban'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.anonymous = None
                self.anonymous_flag = ''
                self.duration = 1800

    class set_group_whole_ban(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_whole_ban'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.enable = True

    class set_group_admin(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_admin'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.enable = True

    class set_group_anonymous(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_anonymous'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.enable = True

    class set_group_card(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_card'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.card = ''

    class set_group_name(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_name'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.group_name = ''

    class set_group_leave(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_leave'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.is_dismiss = False

    class set_group_special_title(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_special_title'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.special_title = None
                self.duration = None

    class set_friend_add_request(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_friend_add_request'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.flag = ''
                self.approve = True
                self.remark = None

    class set_group_add_request(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_add_request'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.flag = ''
                self.sub_type = ''
                self.approve = True
                self.reason = None

    class get_login_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_login_info'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

    class get_stranger_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_stranger_info'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.user_id = -1
                self.no_cache = False

    class get_friend_list(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_friend_list'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

    class get_group_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_info'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.no_cache = False

    class get_group_list(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_list'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

    class get_group_member_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_member_info'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.no_cache = False

    class get_group_member_list(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_member_list'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1

    class get_cookies(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_cookies'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.domain = ''

    class get_csrf_token(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_csrf_token'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

    class get_credentails(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_credentails'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.domain = ''

    class get_record(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_record'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.file = ''
                self.out_format = ''

    class get_image(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_image'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.file = ''

    class can_send_image(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'can_send_image'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

        def yes(self):
            if type(self.res) is req.models.Response and self.res.status_code == 200:
                json_obj = json.loads(self.res.text)
                yes_tmp = json_obj['data']['yes']
                return yes_tmp

    class can_send_record(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'can_send_record'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

        def yes(self):
            if type(self.res) is req.models.Response and self.res.status_code == 200:
                json_obj = json.loads(self.res.text)
                yes_tmp = json_obj['data']['yes']
                return yes_tmp

    class get_status(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_status'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

    class get_version_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_version_info'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

    class set_restart(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_restart'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.delay = 0

    class clean_cache(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'clean_cache'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

    # 以下为 go-cqhttp v1.0.0-beta8-fix1 引入的试验性接口

    class send_guild_channel_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_guild_channel_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.guild_id = -1
                self.channel_id = -1
                self.message = ''

    class get_guild_member_profile(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_guild_member_profile'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.guild_id = -1
                self.user_id = -1

    # 文件相关接口

    class upload_group_file(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'upload_group_file'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.file = ''
                self.name = ''
                self.folder_id = None

    class delete_group_file(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'delete_group_file'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.file_id = ''
                self.name = None
                self.parent_id = None

    class create_group_file_folder(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'create_group_file_folder'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.name = ''
                self.parent_id = '/'

    class delete_group_folder(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'delete_group_folder'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.folder_id = ''

    class get_group_file_system_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_file_system_info'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1

    class get_group_root_files(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_root_files'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.file_count = None

    class get_group_files_by_folder(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_files_by_folder'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.folder_id = ''
                self.file_count = None

    class get_group_file_url(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_file_url'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.file_id = ''
                self.busid = -1

    class upload_private_file(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'upload_private_file'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.user_id = -1
                self.file = ''
                self.name = ''

    class rename_group_file_folder(api_templet):
        """LLOneBot 和 Lagrange 支持"""
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'rename_group_file_folder'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.folder_id = ''
                self.new_folder_name = ''

    class rename_group_file(api_templet):
        """NapCat 支持"""
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'rename_group_file'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.file_id = ''
                self.current_parent_directory = ''
                self.new_name = ''

    class set_group_file_forever(api_templet):
        """LLOneBot 支持 (群文件转永久)"""
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_file_forever'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.file_id = ''

    class trans_group_file(api_templet):
        """NapCat 支持 (转存为永久文件)"""
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'trans_group_file'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.file_id = ''

    class get_essence_msg_list(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_essence_msg_list'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1

    class get_group_ignore_add_request(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_ignore_add_request'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = None

    class get_doubt_friends_add_request(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_doubt_friends_add_request'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.count = 50

    class get_group_system_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_system_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.count = None

    class set_doubt_friends_add_request(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_doubt_friends_add_request'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.flag = ''
                self.approve = None

    class get_group_notice(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = '_get_group_notice'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1

    class send_group_notice(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = '_send_group_notice'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.content = ''
                self.image = ''
                # NapCat 额外参数
                self.pinned = None
                self.type = None
                self.confirm_required = None
                self.is_show_edit_card = None
                self.tip_window_type = None

    class del_group_notice(api_templet):
        """仅 Lagrange 和 NapCat 支持"""
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = '_del_group_notice'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.notice_id = ''
                
    class set_group_reaction(api_templet):
        """Lagrange 贴表情"""
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_reaction'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.message_id = -1
                self.code = ''
                self.is_add = True

    class set_msg_emoji_like(api_templet):
        """NapCat/LLOneBot 贴表情"""
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_msg_emoji_like'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.message_id = -1
                self.emoji_id = -1
                self.set = None

    class unset_msg_emoji_like(api_templet):
        """LLOneBot 取消贴表情"""
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'unset_msg_emoji_like'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.message_id = -1
                self.emoji_id = -1
