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
        try:
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

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ': ' + json_str_tmp)

            msg_res = req.request("POST", send_url, headers = headers, data = payload)

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ' - sendding succeed: ' + msg_res.text)

            self.res = msg_res.text
            return msg_res.text
        except:
            return None

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
    target_event.base_info['self_id'] = target_event.sdk_event.base_info['self_id']
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'fanbook_string'
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
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message'
        target_event.data = target_event.group_message(
            target_event.sdk_event.json['channel_post']['chat']['id'],
            target_event.sdk_event.json['channel_post']['from']['id'],
            message_obj,
            'group'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = target_event.sdk_event.json['channel_post']['message_id']
        target_event.data.raw_message = message_obj
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = target_event.sdk_event.json['channel_post']['from']['id']
        target_event.data.sender['nickname'] = target_event.sdk_event.json['channel_post']['from']['first_name']
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
        target_event.data.host_id = target_event.sdk_event.json['channel_post']['chat']['guild_id']
        target_event.data.extend['host_group_id'] = target_event.sdk_event.json['channel_post']['chat']['guild_id']

#支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, chat_id, message):
        this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.chat_id = chat_id
        this_msg.data.text = message
        if this_msg.data.text != '':
            this_msg.do_api()

    def send_private_msg(target_event, chat_id, message):
        private_chat_id = None
        this_msg = API.getPrivateChat(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.user_id = chat_id
        try:
            tmp_res = this_msg.do_api()
            tmp_res_obj = json.loads(tmp_res)
            if tmp_res_obj['ok'] == True:
                private_chat_id = tmp_res_obj['result']['id']
        except:
            return
        if private_chat_id != None:
            event_action.send_msg(target_event, private_chat_id, message)

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
