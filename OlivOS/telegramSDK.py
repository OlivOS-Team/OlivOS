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

def get_Event_from_SDK(target_event):
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = target_event.sdk_event.base_info['self_id']
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'olivos_para'
    if checkByListAnd([
        not target_event.active,
        checkInDictSafe('message', target_event.sdk_event.json, []),
        checkInDictSafe('chat', target_event.sdk_event.json, ['message']),
        checkInDictSafe('type', target_event.sdk_event.json, ['message', 'chat']),
        checkInDictSafe('message_id', target_event.sdk_event.json, ['message']),
        checkInDictSafe('from', target_event.sdk_event.json, ['message']),
        checkInDictSafe('first_name', target_event.sdk_event.json, ['message', 'from']),
        checkEquelInDictSafe('private', target_event.sdk_event.json, ['message', 'chat', 'type'])
    ]):
        message_obj = None
        if checkByListAnd([
            checkInDictSafe('text', target_event.sdk_event.json, ['message'])
        ]):
            message_obj = OlivOS.messageAPI.Message_templet(
                'old_string',
                target_event.sdk_event.json['message']['text']
            )
            message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
            message_obj.data_raw = message_obj.data.copy()
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
        if not target_event.active:
            return target_event.active
        target_event.plugin_info['func_type'] = 'private_message'
        target_event.data = target_event.private_message(
            target_event.sdk_event.json['message']['from']['id'],
            message_obj,
            'friend'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = target_event.sdk_event.json['message']['message_id']
        target_event.data.raw_message = message_obj
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = target_event.sdk_event.json['message']['from']['id']
        target_event.data.sender['nickname'] = target_event.sdk_event.json['message']['from']['first_name']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
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
        checkEquelInDictSafe('group', target_event.sdk_event.json, ['message', 'chat', 'type'])
    ]):
        message_obj = None
        if checkByListAnd([
            checkInDictSafe('text', target_event.sdk_event.json, ['message'])
        ]):
            message_obj = OlivOS.messageAPI.Message_templet(
                'old_string',
                target_event.sdk_event.json['message']['text']
            )
            message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
            message_obj.data_raw = message_obj.data.copy()
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
        else:
            return target_event.active
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message'
        target_event.data = target_event.group_message(
            target_event.sdk_event.json['message']['chat']['id'],
            target_event.sdk_event.json['message']['from']['id'],
            message_obj,
            'group'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = target_event.sdk_event.json['message']['message_id']
        target_event.data.raw_message = message_obj
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = target_event.sdk_event.json['message']['from']['id']
        target_event.data.sender['nickname'] = target_event.sdk_event.json['message']['from']['first_name']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
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
        checkEquelInDictSafe('supergroup', target_event.sdk_event.json, ['message', 'chat', 'type'])
    ]):
        message_obj = None
        if checkByListAnd([
            checkInDictSafe('text', target_event.sdk_event.json, ['message'])
        ]):
            message_obj = OlivOS.messageAPI.Message_templet(
                'old_string',
                target_event.sdk_event.json['message']['text']
            )
            message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
            message_obj.data_raw = message_obj.data.copy()
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
        else:
            return target_event.active
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message'
        target_event.data = target_event.group_message(
            target_event.sdk_event.json['message']['chat']['id'],
            target_event.sdk_event.json['message']['from']['id'],
            message_obj,
            'group'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = target_event.sdk_event.json['message']['message_id']
        target_event.data.raw_message = message_obj
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = target_event.sdk_event.json['message']['from']['id']
        target_event.data.sender['nickname'] = target_event.sdk_event.json['message']['from']['first_name']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
    return target_event.active

#支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, chat_id, message):
        this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg_image = API.sendPhoto(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.chat_id = chat_id
        this_msg_image.data.chat_id = chat_id
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
