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
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import requests as req
import OlivOS

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

class send_onebot_post_json_T(object):
    def __init__(self):
        self.bot_info = None
        self.obj = None
        self.node_ext = ''

    def send_onebot_post_json(self):
        if type(self.bot_info) is not bot_info_T or self.bot_info.host == '' or self.bot_info.port == -1 or self.obj == None or self.node_ext == '':
            return None
        else:
            json_str_tmp = json.dumps(obj = self.obj.__dict__)
            send_url = self.bot_info.host + ':' + str(self.bot_info.port) + '/' + self.node_ext + '?access_token=' + self.bot_info.access_token

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ': ' + json_str_tmp)

            headers = {
                'Content-Type': 'application/json'
            }
            msg_res = req.request("POST", send_url, headers = headers, data = json_str_tmp)

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ' - sendding succeed: ' + msg_res.text)

            return msg_res

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

class event(object):
    def __init__(self, raw):
        self.raw = raw
        self.json = self.event_load(raw)
        self.platform = {}
        self.platform['sdk'] = 'onebot'
        self.platform['platform'] = 'qq'
        self.platform['model'] = 'default'
        self.active = False
        if self.json != None:
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


#支持OlivOS API事件生成的映射实现
def get_Event_from_SDK(target_event):
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info['self_id'])
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'old_string'
    if target_event.base_info['type'] == 'message':
        if target_event.sdk_event.json['message_type'] == 'private':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message'
            target_event.data = target_event.private_message(
                str(target_event.sdk_event.json['user_id']),
                target_event.sdk_event.json['message'],
                target_event.sdk_event.json['sub_type']
            )
            target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('old_string', target_event.sdk_event.json['message'])
            target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
            target_event.data.raw_message = target_event.sdk_event.json['raw_message']
            target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('old_string', target_event.sdk_event.json['raw_message'])
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
                target_event.data = target_event.group_message(
                    str(target_event.sdk_event.json['group_id']),
                    str(target_event.sdk_event.json['user_id']),
                    target_event.sdk_event.json['message'],
                    target_event.sdk_event.json['sub_type']
                )
                target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('old_string', target_event.sdk_event.json['message'])
                target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
                target_event.data.raw_message = target_event.sdk_event.json['raw_message']
                target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('old_string', target_event.sdk_event.json['raw_message'])
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
                target_event.data = target_event.group_message(
                    str(target_event.sdk_event.json['channel_id']),
                    str(target_event.sdk_event.json['user_id']),
                    target_event.sdk_event.json['message'],
                    target_event.sdk_event.json['sub_type']
                )
                target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('old_string', target_event.sdk_event.json['message'])
                target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
                target_event.data.raw_message = target_event.sdk_event.json['message']
                target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('old_string', target_event.sdk_event.json['message'])
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
        if target_event.data != None:
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
                str(target_event.sdk_event.json['operator_id']),
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
        if target_event.sdk_event.json['request_type'] == 'friend':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'friend_add_request'
            target_event.data = target_event.friend_add_request(
                str(target_event.sdk_event.json['user_id']),
                target_event.sdk_event.json['comment']
            )
            target_event.data.flag = target_event.sdk_event.json['flag']
        elif target_event.sdk_event.json['request_type'] == 'group':
            if target_event.sdk_event.json['sub_type'] == 'add':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_add_request'
                target_event.data = target_event.group_add_request(
                    str(target_event.sdk_event.json['group_id']),
                    str(target_event.sdk_event.json['user_id']),
                    target_event.sdk_event.json['comment']
                )
                target_event.data.flag = target_event.sdk_event.json['flag']
            elif target_event.sdk_event.json['sub_type'] == 'invite':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_invite_request'
                target_event.data = target_event.group_invite_request(
                    str(target_event.sdk_event.json['group_id']),
                    str(target_event.sdk_event.json['user_id']),
                    target_event.sdk_event.json['comment']
                )
                target_event.data.flag = target_event.sdk_event.json['flag']
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


#支持OlivOS API调用的方法实现
class event_action(object):
    def reply_private_msg(target_event, message):
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'private'
        this_msg.data.user_id = int(target_event.data.user_id)
        this_msg.data.message = message
        this_msg.do_api()

    def reply_group_msg(target_event, message):
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'group'
        this_msg.data.group_id = int(target_event.data.group_id)
        this_msg.data.message = message
        this_msg.do_api()

    def send_private_msg(target_event, user_id, message):
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'private'
        this_msg.data.user_id = int(user_id)
        this_msg.data.message = message
        this_msg.do_api()

    def send_group_msg(target_event, group_id, message):
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'group'
        this_msg.data.group_id = int(group_id)
        this_msg.data.message = message
        this_msg.do_api()

    def delete_msg(target_event, message_id):
        this_msg = api.delete_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_id = int(message_id)
        this_msg.do_api()

    def get_msg(target_event, message_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_msg()
        raw_obj = None
        this_msg = api.get_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_id = str(message_id)
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['message_id'] = str(init_api_do_mapping_for_dict(raw_obj, ['message_id'], int))
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['real_id'], int))
                res_data['data']['sender']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['sender', 'user_id'], int))
                res_data['data']['sender']['name'] = init_api_do_mapping_for_dict(raw_obj, ['sender', 'nickname'], str)
                res_data['data']['sender']['user_id'] = str(init_api_do_mapping_for_dict(raw_obj, ['sender', 'user_id'], int))
                res_data['data']['sender']['nickname'] = init_api_do_mapping_for_dict(raw_obj, ['sender', 'nickname'], str)
                res_data['data']['time'] = init_api_do_mapping_for_dict(raw_obj, ['time'], int)
                res_data['data']['message'] = init_api_do_mapping_for_dict(raw_obj, ['message'], str)
                res_data['data']['raw_message'] = init_api_do_mapping_for_dict(raw_obj, ['raw_message'], str)
        return res_data

    def send_like(target_event, user_id, times = 1):
        this_msg = api.send_like(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.user_id = int(user_id)
        this_msg.data.times = times
        this_msg.do_api()

    def set_group_kick(target_event, group_id, user_id, rehect_add_request = False):
        this_msg = api.set_group_kick(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.rehect_add_request = rehect_add_request
        this_msg.do_api()

    def set_group_ban(target_event, group_id, user_id, duration = 1800):
        this_msg = api.set_group_ban(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.duration = duration
        this_msg.do_api()

    def set_group_anonymous_ban(target_event, group_id, anonymous, anonymous_flag, duration = 1800):
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

    def set_group_leave(target_event, group_id, is_dismiss = False):
        this_msg = api.set_group_leave(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.is_dismiss = is_dismiss
        this_msg.do_api()

    def set_group_special_title(target_event, group_id, user_id, special_title, duration):
        this_msg = api.set_group_special_title(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.special_title = special_title
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
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['nickname'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['user_id'], int))
        return res_data

    def get_stranger_info(target_event, user_id, no_cache = False):
        res_data = OlivOS.contentAPI.api_result_data_template.get_stranger_info()
        raw_obj = None
        this_msg = api.get_stranger_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.user_id = int(user_id)
        this_msg.data.no_cache = no_cache
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
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
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_user_info_strip()
                    tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['nickname'], str)
                    tmp_res_data_this['id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['user_id'], int))
                    res_data['data'].append(tmp_res_data_this)
        return res_data

    def get_group_info(target_event, group_id, no_cache = False):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_info()
        raw_obj = None
        this_msg = api.get_group_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.no_cache = no_cache
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
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
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_info_strip()
                    tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['group_name'], str)
                    tmp_res_data_this['id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['group_id'], int))
                    tmp_res_data_this['memo'] = init_api_do_mapping_for_dict(raw_obj_this, ['group_memo'], str)
                    tmp_res_data_this['member_count'] = init_api_do_mapping_for_dict(raw_obj_this, ['member_count'], int)
                    tmp_res_data_this['max_member_count'] = init_api_do_mapping_for_dict(raw_obj_this, ['max_member_count'], int)
                    res_data['data'].append(tmp_res_data_this)
        return res_data

    def get_group_member_info(target_event, group_id, user_id, no_cache = False):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_info()
        raw_obj = None
        this_msg = api.get_group_member_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.group_id = int(group_id)
        this_msg.data.user_id = int(user_id)
        this_msg.data.no_cache = no_cache
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['nickname'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['user_id'], int))
                res_data['data']['user_id'] = str(init_api_do_mapping_for_dict(raw_obj, ['user_id'], int))
                res_data['data']['group_id'] = str(init_api_do_mapping_for_dict(raw_obj, ['group_id'], int))
                res_data['data']['times']['join_time'] = init_api_do_mapping_for_dict(raw_obj, ['join_time'], int)
                res_data['data']['times']['last_sent_time'] = init_api_do_mapping_for_dict(raw_obj, ['last_sent_time'], int)
                res_data['data']['times']['shut_up_timestamp'] = init_api_do_mapping_for_dict(raw_obj, ['shut_up_timestamp'], int)
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
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_member_info_strip()
                    tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['nickname'], str)
                    tmp_res_data_this['id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['user_id'], int))
                    tmp_res_data_this['user_id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['user_id'], int))
                    tmp_res_data_this['group_id'] = str(init_api_do_mapping_for_dict(raw_obj_this, ['group_id'], int))
                    tmp_res_data_this['times']['join_time'] = init_api_do_mapping_for_dict(raw_obj_this, ['join_time'], int)
                    tmp_res_data_this['times']['last_sent_time'] = init_api_do_mapping_for_dict(raw_obj_this, ['last_sent_time'], int)
                    tmp_res_data_this['times']['shut_up_timestamp'] = init_api_do_mapping_for_dict(raw_obj_this, ['shut_up_timestamp'], int)
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
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['yes'] = init_api_do_mapping_for_dict(raw_obj, ['yes'], bool)
        return res_data

    def can_send_record(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.can_send_record()
        raw_obj = None
        this_msg = api.can_send_record(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['yes'] = init_api_do_mapping_for_dict(raw_obj, ['yes'], bool)
        return res_data

    def get_status(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_status()
        raw_obj = None
        this_msg = api.get_status(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['online'] = init_api_do_mapping_for_dict(raw_obj, ['online'], bool)
                res_data['data']['status']['packet_received'] = init_api_do_mapping_for_dict(raw_obj, ['stat', 'packet_received'], int)
                res_data['data']['status']['packet_sent'] = init_api_do_mapping_for_dict(raw_obj, ['stat', 'packet_sent'], int)
                res_data['data']['status']['packet_lost'] = init_api_do_mapping_for_dict(raw_obj, ['stat', 'packet_lost'], int)
                res_data['data']['status']['message_received'] = init_api_do_mapping_for_dict(raw_obj, ['stat', 'message_received'], int)
                res_data['data']['status']['message_sent'] = init_api_do_mapping_for_dict(raw_obj, ['stat', 'message_sent'], int)
                res_data['data']['status']['disconnect_times'] = init_api_do_mapping_for_dict(raw_obj, ['stat', 'disconnect_times'], int)
                res_data['data']['status']['lost_times'] = init_api_do_mapping_for_dict(raw_obj, ['stat', 'lost_times'], int)
                res_data['data']['status']['last_message_time'] = init_api_do_mapping_for_dict(raw_obj, ['stat', 'last_message_time'], int)
        return res_data

    def get_version_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_version_info()
        raw_obj = None
        this_msg = api.get_version_info(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['app_name'], str)
                res_data['data']['version_full'] = init_api_do_mapping_for_dict(raw_obj, ['app_full_name'], str)
                res_data['data']['version'] = init_api_do_mapping_for_dict(raw_obj, ['app_version'], str)
                res_data['data']['path'] = init_api_do_mapping_for_dict(raw_obj, ['coolq_directory'], str)
                res_data['data']['os'] = init_api_do_mapping_for_dict(raw_obj, ['runtime_os'], str)
        return res_data

    #以下为 go-cqhttp v1.0.0-beta8-fix1 引入的试验性接口

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
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
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

#onebot协议标准api调用实现
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
                self.auto_escape  = False


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
                self.auto_escape  = False


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
                self.duration = -1


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


    #以下为 go-cqhttp v1.0.0-beta8-fix1 引入的试验性接口

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
