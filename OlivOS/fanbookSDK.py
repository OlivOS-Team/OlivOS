# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/fanbookSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import requests as req
import json
import time
import uuid

import OlivOS


fanbookAPIHost = {
    'a1': 'https://a1.fanbook.mobi'
}

fanbookAPIRoute = {
    'apiroot': '/api/bot'
}

fanbookAPIRouteTemp = {
    'token': 'TOKEN'
}


class bot_info_T(object):
    def __init__(self, id = -1, access_token = None):
        self.id = id
        self.access_token = access_token
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
    res = bot_info_T(
        target_event.bot_info.id,
        target_event.bot_info.post_info.access_token
    )
    res.debug_mode = target_event.bot_info.debug_mode
    return res

class api_templet(object):
    def __init__(self):
        self.bot_info = None
        self.data = None
        self.host = None
        self.port = 443
        self.route = None
        self.res = None

    def do_api(self):
        if True:
            tmp_payload_dict = {}
            tmp_fanbookAPIRouteTemp = fanbookAPIRouteTemp.copy()
            tmp_fanbookAPIRouteTemp.update({
                'token': self.bot_info.access_token
            })
            if self.data != None:
                for data_this in self.data.__dict__:
                    if self.data.__dict__[data_this] != None:
                        tmp_payload_dict[data_this] = self.data.__dict__[data_this]

            payload = json.dumps(obj = tmp_payload_dict)
            send_url_temp = self.host + ':' + str(self.port) + self.route
            send_url = send_url_temp.format(**tmp_fanbookAPIRouteTemp)
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA
            }

            msg_res = req.request("POST", send_url, headers = headers, data = payload)

            self.res = msg_res.text
            return msg_res.text

class event(object):
    def __init__(self, json_obj = None, bot_info = None):
        self.raw = self.event_dump(json_obj)
        self.json = json_obj
        self.platform = {}
        self.platform['sdk'] = 'fanbook_poll'
        self.platform['platform'] = 'fanbook'
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
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info['self_id'])
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'olivos_para'
    if checkByListAnd([
        not target_event.active,
        checkInDictSafe('channel_post', target_event.sdk_event.json, []),
        checkInDictSafe('text', target_event.sdk_event.json, ['channel_post']),
        checkInDictSafe('chat', target_event.sdk_event.json, ['channel_post']),
        checkInDictSafe('type', target_event.sdk_event.json, ['channel_post', 'chat']),
        checkInDictSafe('message_id', target_event.sdk_event.json, ['channel_post']),
        checkInDictSafe('from', target_event.sdk_event.json, ['channel_post']),
        checkInDictSafe('first_name', target_event.sdk_event.json, ['channel_post', 'from']),
        checkEquelInDictSafe('channel', target_event.sdk_event.json, ['channel_post', 'chat', 'type'])
    ]):
        message_obj = None
        message_obj = OlivOS.messageAPI.Message_templet(
            'fanbook_string',
            target_event.sdk_event.json['channel_post']['text']
        )
        message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
        message_obj.data_raw = message_obj.data.copy()
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message'
        target_event.data = target_event.group_message(
            str(target_event.sdk_event.json['channel_post']['chat']['id']),
            str(target_event.sdk_event.json['channel_post']['from']['id']),
            message_obj,
            'group'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = str(target_event.sdk_event.json['channel_post']['message_id'])
        target_event.data.raw_message = message_obj
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = str(target_event.sdk_event.json['channel_post']['from']['id'])
        target_event.data.sender['nickname'] = target_event.sdk_event.json['channel_post']['from']['first_name']
        target_event.data.sender['id'] = str(target_event.sdk_event.json['channel_post']['from']['id'])
        target_event.data.sender['name'] = target_event.sdk_event.json['channel_post']['from']['first_name']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
        target_event.data.host_id = str(target_event.sdk_event.json['channel_post']['chat']['guild_id'])
        target_event.data.extend['host_group_id'] = str(target_event.sdk_event.json['channel_post']['chat']['guild_id'])
    elif checkByListAnd([
        not target_event.active,
        checkInDictSafe('channel_post', target_event.sdk_event.json, []),
        checkInDictSafe('photo', target_event.sdk_event.json, ['channel_post']),
        checkInDictSafe('chat', target_event.sdk_event.json, ['channel_post']),
        checkInDictSafe('type', target_event.sdk_event.json, ['channel_post', 'chat']),
        checkInDictSafe('message_id', target_event.sdk_event.json, ['channel_post']),
        checkInDictSafe('from', target_event.sdk_event.json, ['channel_post']),
        checkInDictSafe('first_name', target_event.sdk_event.json, ['channel_post', 'from']),
        checkEquelInDictSafe('channel', target_event.sdk_event.json, ['channel_post', 'chat', 'type'])
    ]):
        message_obj = None
        message_para_list = []
        if type(target_event.sdk_event.json['channel_post']['photo']) == list:
            for photo_this in target_event.sdk_event.json['channel_post']['photo']:
                if 'file_id' in photo_this:
                    message_para_list.append(OlivOS.messageAPI.PARA.image(photo_this['file_id']))
        message_obj = OlivOS.messageAPI.Message_templet(
            'olivos_para',
            message_para_list
        )
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message'
        target_event.data = target_event.group_message(
            str(target_event.sdk_event.json['channel_post']['chat']['id']),
            str(target_event.sdk_event.json['channel_post']['from']['id']),
            message_obj,
            'group'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = str(target_event.sdk_event.json['channel_post']['message_id'])
        target_event.data.raw_message = message_obj
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = str(target_event.sdk_event.json['channel_post']['from']['id'])
        target_event.data.sender['nickname'] = target_event.sdk_event.json['channel_post']['from']['first_name']
        target_event.data.sender['id'] = str(target_event.sdk_event.json['channel_post']['from']['id'])
        target_event.data.sender['name'] = target_event.sdk_event.json['channel_post']['from']['first_name']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
        target_event.data.host_id = str(target_event.sdk_event.json['channel_post']['chat']['guild_id'])
        target_event.data.extend['host_group_id'] = str(target_event.sdk_event.json['channel_post']['chat']['guild_id'])

#支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, chat_id, message):
        flag_now_type = 'string'
        this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg_image = API.sendPhoto(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.chat_id = int(chat_id)
        this_msg_image.data.chat_id = int(chat_id)
        this_msg.data.text = ''
        for message_this in message.data:
            if type(message_this) == OlivOS.messageAPI.PARA.image:
                if flag_now_type != 'image':
                    if this_msg.data.text != '':
                        this_msg.do_api()
                        this_msg.data.text = ''
                this_msg_image.data.photo['Url'] = message_this.data['file']
                this_msg_image.do_api()
                flag_now_type = 'image'
            elif type(message_this) == OlivOS.messageAPI.PARA.text:
                this_msg.data.text += message_this.fanbook()
                flag_now_type = 'string'
            elif type(message_this) == OlivOS.messageAPI.PARA.at:
                this_msg.data.text += message_this.fanbook()
                flag_now_type = 'string'
        if flag_now_type != 'image':
            if this_msg.data.text != '':
                this_msg.do_api()

    def send_private_msg(target_event, chat_id, message):
        private_chat_id = None
        this_msg = API.getPrivateChat(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.user_id = int(chat_id)
        try:
            tmp_res = this_msg.do_api()
            tmp_res_obj = json.loads(tmp_res)
            if tmp_res_obj['ok'] == True:
                private_chat_id = tmp_res_obj['result']['id']
        except:
            return
        if private_chat_id != None:
            event_action.send_msg(target_event, private_chat_id, message)

    def get_login_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        private_chat_id = None
        this_msg = API.getMe(get_SDK_bot_info_from_Event(target_event))
        try:
            tmp_res = this_msg.do_api()
            tmp_res_obj = json.loads(tmp_res)
            if tmp_res_obj['ok'] == True:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(tmp_res_obj, ['result', 'username'], str)
                res_data['data']['id'] = str(init_api_do_mapping_for_dict(tmp_res_obj, ['result', 'id'], int))
        except:
            res_data['active'] = False
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

class API(object):
    class getMe(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.host = fanbookAPIHost['a1']
            self.route = fanbookAPIRoute['apiroot'] + '/{token}/getMe'


    class getUpdates(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = fanbookAPIHost['a1']
            self.route = fanbookAPIRoute['apiroot'] + '/{token}/getUpdates'

        class data_T(object):
            def __init__(self):
                self.offset = 0
                self.limit = 100
                self.timeout = 2

    class sendMessage(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = fanbookAPIHost['a1']
            self.route = fanbookAPIRoute['apiroot'] + '/{token}/sendMessage'

        class data_T(object):
            def __init__(self):
                self.chat_id = 0
                self.text = ''
                self.disable_web_page_preview = True
                self.disable_notification = False

    class sendPhoto(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = fanbookAPIHost['a1']
            self.route = fanbookAPIRoute['apiroot'] + '/{token}/sendPhoto'

        class data_T(object):
            def __init__(self):
                self.chat_id = 0
                self.photo = {
                    'Url': ''
                }

    class getPrivateChat(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = fanbookAPIHost['a1']
            self.route = fanbookAPIRoute['apiroot'] + '/{token}/getPrivateChat'

        class data_T(object):
            def __init__(self):
                self.user_id = 0

    class setBotPrivacyMode(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.data.bot_id = self.bot_info.id
            self.host = fanbookAPIHost['a1']
            self.route = fanbookAPIRoute['apiroot'] + '/setBotPrivacyMode'

        class data_T(object):
            def __init__(self):
                self.owner_id = -1
                self.bot_id = -1
                self.enable = True
