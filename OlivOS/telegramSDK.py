# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/telegramSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import requests as req
import json

import OlivOS

telegram_host_default = 'https://api.telegram.org'
telegram_port_default = 443

sdkSubSelfInfo = {}
sdkSubInfo = {}

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

def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(
        plugin_bot_info.id,
        plugin_bot_info.post_info.host,
        plugin_bot_info.post_info.port,
        plugin_bot_info.post_info.access_token
    )
    res.debug_mode = plugin_bot_info.debug_mode
    return res

class send_telegram_post_json_T(object):
    def __init__(self):
        self.bot_info = None
        self.obj = None
        self.node_ext = ''

    def send_telegram_post_json(self):
        if type(self.bot_info) is not bot_info_T or self.bot_info.host == '' or self.bot_info.port == -1 or self.obj == None or self.node_ext == '':
            return None
        else:
            json_str_tmp = json.dumps(obj = self.obj.__dict__)
            send_url = self.bot_info.host + ':' + str(self.bot_info.port) + '/bot' + self.bot_info.access_token + '/' + self.node_ext

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ': ' + json_str_tmp)

            headers = {
                'Content-Type': 'application/json',
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA
            }
            msg_res = req.request("POST", send_url, headers = headers, data = json_str_tmp)

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ' - sendding succeed: ' + msg_res.text)

            return msg_res


class event(object):
    def __init__(self, json_obj = None, sdk_mode = 'poll', bot_info = None):
        self.raw = self.event_dump(json_obj)
        self.json = json_obj
        self.platform = {}
        if sdk_mode == 'poll':
            self.platform['sdk'] = 'telegram_poll'
        elif sdk_mode == 'hook':
            self.platform['sdk'] = 'telegram_hook'
        else:
            self.platform['sdk'] = 'telegram'
        self.platform['platform'] = 'telegram'
        self.platform['model'] = 'default'
        self.active = False
        if self.json != None:
            self.active = True
        self.base_info = {}
        if checkByListAnd([
            self.active,
            checkInDictSafe('message', self.json, []),
            checkInDictSafe('date', self.json, ['message'])
        ]):
            self.base_info['time'] = self.json['message']['date']
        else:
            self.base_info['time'] = 0
        if checkByListAnd([
            self.active
        ]):
            self.base_info['self_id'] = bot_info.id
            self.base_info['token'] = bot_info.post_info.access_token
            self.base_info['post_type'] = None

    def event_dump(self, raw):
        try:
            res = json.dumps(raw)
        except:
            res = None
        return res

def checkInDictSafe(var_key, var_dict, var_path = []):
    var_dict_this = var_dict
    for var_key_this in var_path:
        if var_key_this in var_dict_this:
            var_dict_this = var_dict_this[var_key_this]
        else:
            return False
    if var_key in var_dict_this:
        return True
    else:
        return False

def checkEquelInDictSafe(var_it, var_dict, var_path = []):
    var_dict_this = var_dict
    for var_key_this in var_path:
        if var_key_this in var_dict_this:
            var_dict_this = var_dict_this[var_key_this]
        else:
            return False
    if var_it == var_dict_this:
        return True
    else:
        return False

def checkByListAnd(check_list):
    flag_res = True
    for check_list_this in check_list:
        if not check_list_this:
            flag_res = False
            return flag_res
    return flag_res

def get_message_obj_from_SDK(target_event):
    message_obj = None
    if True:
        if checkByListAnd([
            checkInDictSafe('text', target_event.sdk_event.json, ['message'])
        ]):
            message_list = []
            tmp_message_raw = target_event.sdk_event.json['message']['text']
            tmp_message_raw_1 = ''
            tmp_message_raw_2 = ''
            tmp_message_raw_3 = ''
            tmp_message_raw_3 = tmp_message_raw
            tmp_message_offset_count = 0
            if checkByListAnd([
                checkInDictSafe('entities', target_event.sdk_event.json, ['message'])
            ]):
                for entities_this in target_event.sdk_event.json['message']['entities']:
                    if entities_this['type'] == 'mention':
                        tmp_message_raw_1 = ''
                        tmp_message_raw_2 = ''
                        tmp_message_raw_3 = ''
                        tmp_message_raw_1 = tmp_message_raw[tmp_message_offset_count:entities_this['offset']]
                        tmp_message_raw_2 = tmp_message_raw[entities_this['offset']:entities_this['offset'] + entities_this['length']]
                        tmp_message_raw_2 = tmp_message_raw_2[1:]
                        tmp_message_raw_3 = tmp_message_raw[entities_this['offset'] + entities_this['length']:]
                        tmp_message_offset_count = entities_this['offset'] + entities_this['length']
                        if len(tmp_message_raw_1) > 0:
                            message_list.append(
                                OlivOS.messageAPI.PARA.text(
                                    text = tmp_message_raw_1
                                )
                            )
                        if len(tmp_message_raw_2) > 0:
                            message_list.append(
                                OlivOS.messageAPI.PARA.at(
                                    id = tmp_message_raw_2
                                )
                            )
            if len(tmp_message_raw_3) > 0:
                message_list.append(
                    OlivOS.messageAPI.PARA.text(
                        text = tmp_message_raw_3
                    )
                )
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                message_list
            )
            target_event.active = True
        elif checkByListAnd([
            checkInDictSafe('photo', target_event.sdk_event.json, ['message'])
        ]):
            message_list = []
            if type(target_event.sdk_event.json['message']['photo']) == list:
                message_list.append(
                    OlivOS.messageAPI.PARA.image(
                        target_event.sdk_event.json['message']['photo'][0]['file_id']
                    )
                )
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                message_list
            )
            target_event.active = True
        elif checkByListAnd([
            checkInDictSafe('sticker', target_event.sdk_event.json, ['message'])
        ]):
            message_list = []
            message_list.append(
                OlivOS.messageAPI.PARA.image(
                    target_event.sdk_event.json['message']['sticker']['file_id']
                )
            )
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                message_list
            )
            target_event.active = True
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
        bot_id = target_event.base_info['self_id'],
        platform_sdk = target_event.platform['sdk'],
        platform_platform = target_event.platform['platform'],
        platform_model = target_event.platform['model']
    )
    if plugin_event_bot_hash not in sdkSubSelfInfo:
        tmp_bot_info = bot_info_T(
            target_event.sdk_event.base_info['self_id'],
            telegram_host_default,
            telegram_port_default,
            target_event.sdk_event.base_info['token']
        )
        tmp_api = API.getMe(tmp_bot_info)
        try:
            tmp_api.do_api()
            tmp_api_json = json.loads(tmp_api.res.text)
            if tmp_api_json['ok'] == True:
                sdkSubSelfInfo[plugin_event_bot_hash] = tmp_api_json['result']['username']
        except:
            pass
    if checkByListAnd([
        not target_event.active,
        checkInDictSafe('message', target_event.sdk_event.json, []),
        checkInDictSafe('chat', target_event.sdk_event.json, ['message']),
        checkInDictSafe('type', target_event.sdk_event.json, ['message', 'chat']),
        checkInDictSafe('message_id', target_event.sdk_event.json, ['message']),
        checkInDictSafe('from', target_event.sdk_event.json, ['message']),
        checkInDictSafe('first_name', target_event.sdk_event.json, ['message', 'from']),
        checkInDictSafe('text', target_event.sdk_event.json, ['message']),
        checkEquelInDictSafe('private', target_event.sdk_event.json, ['message', 'chat', 'type'])
    ]):
        message_obj = None
        message_obj = get_message_obj_from_SDK(target_event)
        if not target_event.active:
            return target_event.active
        target_event.plugin_info['func_type'] = 'private_message'
        target_event.data = target_event.private_message(
            str(target_event.sdk_event.json['message']['from']['id']),
            message_obj,
            'friend'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = str(target_event.sdk_event.json['message']['message_id'])
        target_event.data.raw_message = message_obj
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = str(target_event.sdk_event.json['message']['from']['id'])
        target_event.data.sender['nickname'] = target_event.sdk_event.json['message']['from']['first_name']
        target_event.data.sender['id'] = str(target_event.sdk_event.json['message']['from']['id'])
        target_event.data.sender['name'] = target_event.sdk_event.json['message']['from']['first_name']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
        if plugin_event_bot_hash in sdkSubSelfInfo:
            target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
    if checkByListAnd([
        not target_event.active,
        'message' in target_event.sdk_event.json,
        checkInDictSafe('message', target_event.sdk_event.json, []),
        checkInDictSafe('chat', target_event.sdk_event.json, ['message']),
        checkInDictSafe('type', target_event.sdk_event.json, ['message', 'chat']),
        checkInDictSafe('message_id', target_event.sdk_event.json, ['message']),
        checkInDictSafe('from', target_event.sdk_event.json, ['message']),
        checkInDictSafe('id', target_event.sdk_event.json, ['message', 'from']),
        checkInDictSafe('first_name', target_event.sdk_event.json, ['message', 'from']),
        checkInDictSafe('text', target_event.sdk_event.json, ['message']),
        checkEquelInDictSafe('group', target_event.sdk_event.json, ['message', 'chat', 'type'])
    ]):
        message_obj = None
        message_obj = get_message_obj_from_SDK(target_event)
        if not target_event.active:
            return target_event.active
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message'
        target_event.data = target_event.group_message(
            str(target_event.sdk_event.json['message']['chat']['id']),
            str(target_event.sdk_event.json['message']['from']['id']),
            message_obj,
            'group'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = str(target_event.sdk_event.json['message']['message_id'])
        target_event.data.raw_message = message_obj
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = str(target_event.sdk_event.json['message']['from']['id'])
        target_event.data.sender['nickname'] = target_event.sdk_event.json['message']['from']['first_name']
        target_event.data.sender['id'] = str(target_event.sdk_event.json['message']['from']['id'])
        target_event.data.sender['name'] = target_event.sdk_event.json['message']['from']['first_name']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
        if plugin_event_bot_hash in sdkSubSelfInfo:
            target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
    if checkByListAnd([
        not target_event.active,
        'message' in target_event.sdk_event.json,
        checkInDictSafe('message', target_event.sdk_event.json, []),
        checkInDictSafe('chat', target_event.sdk_event.json, ['message']),
        checkInDictSafe('type', target_event.sdk_event.json, ['message', 'chat']),
        checkInDictSafe('message_id', target_event.sdk_event.json, ['message']),
        checkInDictSafe('from', target_event.sdk_event.json, ['message']),
        checkInDictSafe('id', target_event.sdk_event.json, ['message', 'from']),
        checkInDictSafe('first_name', target_event.sdk_event.json, ['message', 'from']),
        checkInDictSafe('text', target_event.sdk_event.json, ['message']),
        checkEquelInDictSafe('supergroup', target_event.sdk_event.json, ['message', 'chat', 'type'])
    ]):
        message_obj = None
        message_obj = get_message_obj_from_SDK(target_event)
        if not target_event.active:
            return target_event.active
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message'
        target_event.data = target_event.group_message(
            str(target_event.sdk_event.json['message']['chat']['id']),
            str(target_event.sdk_event.json['message']['from']['id']),
            message_obj,
            'group'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = target_event.sdk_event.json['message']['message_id']
        target_event.data.raw_message = message_obj
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = str(target_event.sdk_event.json['message']['from']['id'])
        target_event.data.sender['nickname'] = target_event.sdk_event.json['message']['from']['first_name']
        target_event.data.sender['id'] = str(target_event.sdk_event.json['message']['from']['id'])
        target_event.data.sender['name'] = target_event.sdk_event.json['message']['from']['first_name']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
        if plugin_event_bot_hash in sdkSubSelfInfo:
            target_event.data.extend['sub_self_id'] = sdkSubSelfInfo[plugin_event_bot_hash]
    if checkByListAnd([
        not target_event.active,
        'message' in target_event.sdk_event.json,
        checkInDictSafe('message', target_event.sdk_event.json, []),
        checkInDictSafe('from', target_event.sdk_event.json, ['message']),
        checkInDictSafe('id', target_event.sdk_event.json, ['message', 'from']),
        checkInDictSafe('chat', target_event.sdk_event.json, ['message']),
        checkInDictSafe('id', target_event.sdk_event.json, ['message', 'chat']),
        checkInDictSafe('new_chat_member', target_event.sdk_event.json, ['message']),
        checkInDictSafe('id', target_event.sdk_event.json, ['message', 'new_chat_member'])
    ]):
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_member_increase'
        target_event.data = target_event.group_member_increase(
            str(target_event.sdk_event.json['message']['chat']['id']),
            str(target_event.sdk_event.json['message']['from']['id']),
            target_event.sdk_event.json['message']['new_chat_member']['id']
        )
        target_event.data.action = 'invite'
    if checkByListAnd([
        not target_event.active,
        'message' in target_event.sdk_event.json,
        checkInDictSafe('message', target_event.sdk_event.json, []),
        checkInDictSafe('from', target_event.sdk_event.json, ['message']),
        checkInDictSafe('id', target_event.sdk_event.json, ['message', 'from']),
        checkInDictSafe('chat', target_event.sdk_event.json, ['message']),
        checkInDictSafe('id', target_event.sdk_event.json, ['message', 'chat']),
        checkInDictSafe('left_chat_member', target_event.sdk_event.json, ['message']),
        checkInDictSafe('id', target_event.sdk_event.json, ['message', 'left_chat_member'])
    ]):
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_member_decrease'
        target_event.data = target_event.group_member_decrease(
            str(target_event.sdk_event.json['message']['chat']['id']),
            str(target_event.sdk_event.json['message']['from']['id']),
            target_event.sdk_event.json['message']['left_chat_member']['id']
        )
        if target_event.data.operator_id == target_event.data.user_id:
            target_event.data.action = 'leave'
        else:
            if target_event.data.user_id == target_event.base_info['self_id']:
                target_event.data.action = 'kick_me'
            else:
                target_event.data.action = 'kick'
    return target_event.active

#支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, chat_id, message):
        this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg_image = API.sendPhoto(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.chat_id = str(chat_id)
        this_msg_image.data.chat_id = str(chat_id)
        this_msg.data.text = ''
        flag_now_type = 'string'
        if message != None:
            if type(message.data) == list:
                for message_this in message.data:
                    if type(message_this) == OlivOS.messageAPI.PARA.image:
                        if flag_now_type != 'image':
                            if this_msg.data.text != '':
                                this_msg.do_api()
                                this_msg.data.text = ''
                        this_msg_image.data.photo = message_this.data['file']
                        this_msg_image.do_api()
                        flag_now_type = 'image'
                    elif type(message_this) == OlivOS.messageAPI.PARA.text:
                        this_msg.data.text += message_this.OP()
                        flag_now_type = 'string'
        if flag_now_type != 'image':
            if this_msg.data.text != '':
                this_msg.do_api()

    def send_private_msg(target_event, user_id, message):
        event_action.send_msg(target_event, user_id, message)

    def send_group_msg(target_event, group_id, message):
        event_action.send_msg(target_event, group_id, message)

    def get_login_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        raw_obj = None
        this_msg = API.getMe(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['first_name'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['id'], int))
        return res_data

    def get_login_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        raw_obj = None
        this_msg = API.getMe(get_SDK_bot_info_from_Event(target_event))
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['first_name'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['id'], int))
        return res_data

    def set_chat_leave(target_event, chat_id, is_dismiss = False):
        this_msg = API.leaveChat(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.chat_id = str(chat_id)
        this_msg.do_api()

    def get_group_info(target_event, chat_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_info()
        raw_obj = None
        raw_obj_2 = None
        this_msg = API.getChat(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.chat_id = str(chat_id)
        this_msg.do_api()
        this_msg_2 = API.getChatMemberCount(get_SDK_bot_info_from_Event(target_event))
        this_msg_2.data.chat_id = str(chat_id)
        this_msg_2.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if this_msg_2.res != None:
            raw_obj_2 = init_api_json(this_msg_2.res.text)
        if raw_obj != None and raw_obj_2 != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['title'], str)
                res_data['data']['id'] = str(chat_id)
                if 'description' in raw_obj:
                    res_data['data']['memo'] = init_api_do_mapping_for_dict(raw_obj, ['description'], str)
                res_data['data']['member_count'] = init_api_do_mapping_for_dict(raw_obj_2, [], int)
                res_data['data']['max_member_count'] = 200
                tmp_group_type = init_api_do_mapping_for_dict(raw_obj, ['type'], str)
                if tmp_group_type == 'group':
                    res_data['data']['max_member_count'] = 200
                if tmp_group_type == 'supergroup':
                    res_data['data']['max_member_count'] = 200000
        return res_data

    def get_group_member_info(target_event, chat_id, user_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_info()
        raw_obj = None
        this_msg = API.getChatMember(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.chat_id = str(chat_id)
        this_msg.data.user_id = str(user_id)
        this_msg.do_api()
        if this_msg.res != None:
            raw_obj = init_api_json(this_msg.res.text)
        if raw_obj != None:
            if type(raw_obj) == dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['user', 'first_name'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['user', 'id'], int))
                res_data['data']['user_id'] = str(init_api_do_mapping_for_dict(raw_obj, ['user', 'id'], int))
                res_data['data']['group_id'] = str(chat_id)
                res_data['data']['times']['join_time'] = -1
                res_data['data']['times']['last_sent_time'] = -1
                res_data['data']['times']['shut_up_timestamp'] = -1
                res_data['data']['role'] = 'member'
                tmp_role = init_api_do_mapping_for_dict(raw_obj, ['status', 'role'], str)
                if tmp_role == 'creator':
                    res_data['data']['role'] = 'owner'
                elif tmp_role == 'administrator':
                    res_data['data']['role'] = 'admin'
                res_data['data']['card'] = init_api_do_mapping_for_dict(raw_obj, ['user', 'first_name'], str)
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
        if 'ok' in tmp_obj:
            if type(tmp_obj['ok']) == bool:
                if tmp_obj['ok'] == True:
                    flag_is_active = True
    if flag_is_active:
        if 'result' in tmp_obj:
            if type(tmp_obj['result']) == dict:
                res_data = tmp_obj['result'].copy()
            elif type(tmp_obj['result']) == list:
                res_data = tmp_obj['result'].copy()
            else:
                res_data = tmp_obj['result']
    return res_data

def init_api_do_mapping(src_type, src_data):
    if type(src_data) == src_type:
        return src_data

def init_api_do_mapping_for_dict(src_data, path_list, src_type):
    res_data = None
    flag_active = True
    tmp_src_data = src_data
    if type(src_data) == src_type:
        return src_data
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

class api_templet(object):
    def __init__(self):
        self.bot_info = None
        self.data = None
        self.node_ext = None
        self.res = None

    def do_api(self):
        this_post_json = send_telegram_post_json_T()
        this_post_json.bot_info = self.bot_info
        this_post_json.obj = self.data
        this_post_json.node_ext = self.node_ext
        self.res = this_post_json.send_telegram_post_json()
        return self.res

class API(object):
    class getMe(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'getMe'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None

    class getUpdates(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'getUpdates'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.offset = 0
                self.limit = 100
                self.timeout = 0

    class getUpdatesWithAllowed(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'getUpdates'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.offset = 0
                self.limit = 100
                self.timeout = 0
                self.allowed_updates = None

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
                self.disable_web_page_preview = True
                self.disable_notification = False

    class sendMessageWithReply(api_templet):
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
                self.disable_web_page_preview = True
                self.disable_notification = False
                self.reply_to_message_id = 0
                self.allow_sending_without_reply = True

    class sendPhoto(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'sendPhoto'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.chat_id = 0
                self.photo = ''

    class leaveChat(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'leaveChat'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.chat_id = 0

    class getChat(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'getChat'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.chat_id = 0

    class getChatMember(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'getChatMember'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.chat_id = 0
                self.user_id = 0

    class getChatMemberCount(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'getChatMemberCount'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.chat_id = 0
