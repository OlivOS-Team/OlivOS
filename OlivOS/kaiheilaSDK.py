# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/kaiheilaSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import requests as req
import time

import OlivOS

sdkAPIHost = {
    'default': 'https://www.kaiheila.cn/api/v3',
    'v3': 'https://www.kaiheila.cn/api/v3',
    'native': 'https://www.kaiheila.cn/api'
}

sdkAPIRoute = {
    'channel': '/channel',
    'message': '/message',
    'user-chat': '/user-chat',
    'direct-message': '/direct-message',
    'user': '/user',
    'gateway': '/gateway'
}

sdkAPIRouteTemp = {}

sdkSubSelfInfo = {}

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

class event(object):
    def __init__(self, payload_obj = None, bot_info = None):
        self.payload = payload_obj
        self.platform = {}
        self.platform['sdk'] = 'kaiheila_link'
        self.platform['platform'] = 'kaiheila'
        self.platform['model'] = 'default'
        self.active = False
        if self.payload != None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = bot_info.id
            self.base_info['token'] = bot_info.post_info.access_token
            self.base_info['post_type'] = None

'''
对于WEBSOCKET接口的PAYLOAD实现
'''
class payload_template(object):
    def __init__(self, data = None, is_rx = False):
        self.active = True
        self.data = self.data_T()
        self.load(data, is_rx)

    class data_T(object):
        def __init__(self):
            self.s = None
            self.d = None
            self.sn = None

    def dump(self):
        res_obj = {}
        for data_this in self.data.__dict__:
            if self.data.__dict__[data_this] != None:
                res_obj[data_this] = self.data.__dict__[data_this]
        res = json.dumps(obj = res_obj)
        return res

    def load(self, data, is_rx):
        if data != None:
            if type(data) == dict:
                if 's' in data:
                    self.data.s = data['s']
                if 'd' in data:
                    self.data.d = data['d']
                if 'sn' in data:
                    self.data.sn = data['sn']
            else:
                self.active = False
        return self

class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, data):
            payload_template.__init__(self, data, True)

    class sendPing(payload_template):
        def __init__(self, last_s = None):
            payload_template.__init__(self)
            self.data.s = 2
            self.data.sn = last_s

'''
对于POST接口的实现
'''
class api_templet(object):
    def __init__(self):
        self.bot_info = None
        self.data = None
        self.metadata = None
        self.host = None
        self.port = 443
        self.route = None
        self.res = None

    def do_api(self, req_type = 'POST'):
        try:
            tmp_payload_dict = {}
            tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
            if self.metadata != None:
                tmp_sdkAPIRouteTemp.update(self.metadata.__dict__)
            if self.data != None:
                for data_this in self.data.__dict__:
                    if self.data.__dict__[data_this] != None:
                        tmp_payload_dict[data_this] = self.data.__dict__[data_this]

            payload = json.dumps(obj = tmp_payload_dict)
            send_url_temp = self.host + self.route
            send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                'Authorization': 'Bot %s' % self.bot_info.access_token
            }

            msg_res = None
            if req_type == 'POST':
                msg_res = req.request("POST", send_url, headers = headers, data = payload)
            elif req_type == 'GET':
                msg_res = req.request("GET", send_url, headers = headers)

            self.res = msg_res.text
            return msg_res.text
        except:
            return None

class API(object):
    class getGateway(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['gateway'] + '/index?compress=0'

    class getMe(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['user'] + '/me'

    class creatMessage(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['message'] + '/create'

        class data_T(object):
            def __init__(self):
                self.type = 1
                self.target_id = None
                self.content = None
                self.quote = None
                self.nonce = None
                self.temp_target_id = None

    class creatDirectMessage(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['direct-message'] + '/create'

        class data_T(object):
            def __init__(self):
                self.type = 1
                self.target_id = None
                self.chat_code = None
                self.content = None
                self.quote = None
                self.nonce = None

    class getUserViewStranger(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['user'] + '/view?user_id={user_id}'

        class metadata_T(object):
            def __init__(self):
                self.user_id = '-1'

    class getUserView(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['user'] + '/view?user_id={user_id}&guild_id={guild_id}'

        class metadata_T(object):
            def __init__(self):
                self.user_id = '-1'
                self.guild_id = None


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
            target_event.sdk_event.base_info['token']
        )
        api_msg_obj = API.getMe(tmp_bot_info)
        try:
            api_msg_obj.do_api('GET')
            api_res_json = json.loads(api_msg_obj.res)
            sdkSubSelfInfo[plugin_event_bot_hash] = api_res_json['data']['id']
        except:
            pass
    if 'channel_type' in target_event.sdk_event.payload.data.d:
        if target_event.sdk_event.payload.data.d['channel_type'] == 'GROUP':
            message_obj = None
            flag_have_image = False
            if 'extra' in target_event.sdk_event.payload.data.d:
                if 'attachments' in target_event.sdk_event.payload.data.d['extra']:
                    if type(target_event.sdk_event.payload.data.d['extra']['attachments']) == dict:
                        attachments_this = target_event.sdk_event.payload.data.d['extra']['attachments']
                        if 'type' in attachments_this:
                            if attachments_this['type'].startswith('image'):
                                flag_have_image = True
                                message_obj = OlivOS.messageAPI.Message_templet(
                                    'olivos_para',
                                    []
                                )
                                message_obj.data_raw.append(
                                    OlivOS.messageAPI.PARA.image(
                                        '%s' % attachments_this['url']
                                    )
                                )
                elif 'kmarkdown' in target_event.sdk_event.payload.data.d['extra']:
                    if type(target_event.sdk_event.payload.data.d['extra']['kmarkdown']) == dict:
                        attachments_this = target_event.sdk_event.payload.data.d['extra']['kmarkdown']
                        if attachments_this['raw_content'] != '':
                            message_obj = OlivOS.messageAPI.Message_templet(
                                'kaiheila_string',
                                attachments_this['raw_content']
                            )
                            message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                            message_obj.data_raw = message_obj.data.copy()
                        else:
                            message_obj = OlivOS.messageAPI.Message_templet(
                                'olivos_para',
                                []
                            )
            if not flag_have_image and 'content' in target_event.sdk_event.payload.data.d:
                if target_event.sdk_event.payload.data.d['content'] != '':
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'kaiheila_string',
                        target_event.sdk_event.payload.data.d['content']
                    )
                    message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                    message_obj.data_raw = message_obj.data.copy()
                else:
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'olivos_para',
                        []
                    )
            try:
                message_obj.init_data()
            except:
                message_obj.active = False
                message_obj.data = []
            if message_obj.active:
                try:
                    if target_event.sdk_event.payload.data.d['extra']['type'] in [1, 9]:
                        target_event.active = True
                        target_event.plugin_info['func_type'] = 'group_message'
                        target_event.data = target_event.group_message(
                            str(target_event.sdk_event.payload.data.d['target_id']),
                            str(target_event.sdk_event.payload.data.d['author_id']),
                            message_obj,
                            'group'
                        )
                        target_event.data.message_sdk = message_obj
                        target_event.data.message_id = str(target_event.sdk_event.payload.data.d['msg_id'])
                        target_event.data.raw_message = message_obj
                        target_event.data.raw_message_sdk = message_obj
                        target_event.data.font = None
                        target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.data.d['extra']['author']['id'])
                        target_event.data.sender['nickname'] = target_event.sdk_event.payload.data.d['extra']['author']['username']
                        target_event.data.sender['id'] = str(target_event.sdk_event.payload.data.d['extra']['author']['id'])
                        target_event.data.sender['name'] = target_event.sdk_event.payload.data.d['extra']['author']['username']
                        target_event.data.sender['sex'] = 'unknown'
                        target_event.data.sender['age'] = 0
                        target_event.data.sender['role'] = 'member'
                        target_event.data.host_id = str(target_event.sdk_event.payload.data.d['extra']['guild_id'])
                        target_event.data.extend['flag_from_direct'] = False
                        if plugin_event_bot_hash in sdkSubSelfInfo:
                            target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
                        if str(target_event.data.user_id) == str(target_event.base_info['self_id']):
                            target_event.active = False
                    else:
                        target_event.active = False
                except:
                    target_event.active = False
        elif target_event.sdk_event.payload.data.d['channel_type'] == 'PERSON':
            message_obj = None
            flag_have_image = False
            if 'extra' in target_event.sdk_event.payload.data.d:
                if 'attachments' in target_event.sdk_event.payload.data.d['extra']:
                    if type(target_event.sdk_event.payload.data.d['extra']['attachments']) == dict:
                        attachments_this = target_event.sdk_event.payload.data.d['extra']['attachments']
                        if 'type' in attachments_this:
                            if attachments_this['type'].startswith('image'):
                                flag_have_image = True
                                message_obj = OlivOS.messageAPI.Message_templet(
                                    'olivos_para',
                                    []
                                )
                                message_obj.data_raw.append(
                                    OlivOS.messageAPI.PARA.image(
                                        '%s' % attachments_this['url']
                                    )
                                )
                elif 'kmarkdown' in target_event.sdk_event.payload.data.d['extra']:
                    if type(target_event.sdk_event.payload.data.d['extra']['kmarkdown']) == dict:
                        attachments_this = target_event.sdk_event.payload.data.d['extra']['kmarkdown']
                        if attachments_this['raw_content'] != '':
                            message_obj = OlivOS.messageAPI.Message_templet(
                                'kaiheila_string',
                                attachments_this['raw_content']
                            )
                            message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                            message_obj.data_raw = message_obj.data.copy()
                        else:
                            message_obj = OlivOS.messageAPI.Message_templet(
                                'olivos_para',
                                []
                            )
            if not flag_have_image and 'content' in target_event.sdk_event.payload.data.d:
                if target_event.sdk_event.payload.data.d['content'] != '':
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'olivos_string',
                        target_event.sdk_event.payload.data.d['content']
                    )
                    message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                    message_obj.data_raw = message_obj.data.copy()
                else:
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'olivos_para',
                        []
                    )
            try:
                message_obj.init_data()
            except:
                message_obj.active = False
                message_obj.data = []
            if message_obj.active:
                try:
                    if target_event.sdk_event.payload.data.d['extra']['type'] in [1, 9]:
                        target_event.active = True
                        target_event.plugin_info['func_type'] = 'private_message'
                        target_event.data = target_event.private_message(
                            str(target_event.sdk_event.payload.data.d['author_id']),
                            message_obj,
                            'friend'
                        )
                        target_event.data.message_sdk = message_obj
                        target_event.data.message_id = str(target_event.sdk_event.payload.data.d['msg_id'])
                        target_event.data.raw_message = message_obj
                        target_event.data.raw_message_sdk = message_obj
                        target_event.data.font = None
                        target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.data.d['extra']['author']['id'])
                        target_event.data.sender['nickname'] = target_event.sdk_event.payload.data.d['extra']['author']['username']
                        target_event.data.sender['id'] = str(target_event.sdk_event.payload.data.d['extra']['author']['id'])
                        target_event.data.sender['name'] = target_event.sdk_event.payload.data.d['extra']['author']['username']
                        target_event.data.sender['sex'] = 'unknown'
                        target_event.data.sender['age'] = 0
                        target_event.data.extend['flag_from_direct'] = True
                        if plugin_event_bot_hash in sdkSubSelfInfo:
                            target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
                        if str(target_event.data.user_id) == str(target_event.base_info['self_id']):
                            target_event.active = False
                    else:
                        target_event.active = False
                except:
                    target_event.active = False


#支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, chat_id, message, flag_direct = False):
        this_msg = None
        if flag_direct:
            this_msg = API.creatDirectMessage(get_SDK_bot_info_from_Event(target_event))
        else:
            this_msg = API.creatMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.target_id = str(chat_id)
        if this_msg == None:
            return
        flag_now_type = 'string'
        res = ''
        for message_this in message.data:
            if type(message_this) == OlivOS.messageAPI.PARA.image:
                res += message_this.data['file']
                flag_now_type = 'string'
            elif type(message_this) == OlivOS.messageAPI.PARA.text:
                res += message_this.kaiheila()
                flag_now_type = 'string'
        if res != '':
            this_msg.data.content = res
            this_msg.do_api()

    def get_login_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        raw_obj = None
        this_msg = API.getMe(get_SDK_bot_info_from_Event(target_event))
        try:
            this_msg.do_api('GET')
            if this_msg.res != None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj != None:
                if type(raw_obj) == dict:
                    res_data['active'] = True
                    res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'username'], str)
                    res_data['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'id'], str)
        except:
            res_data['active'] = False
        return res_data

    def get_stranger_info(target_event, user_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_stranger_info()
        raw_obj = None
        this_msg = API.getUserViewStranger(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.user_id = str(user_id)
        try:
            this_msg.do_api('GET')
            if this_msg.res != None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj != None:
                if type(raw_obj) == dict:
                    res_data['active'] = True
                    res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'username'], str)
                    res_data['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'id'], str)
        except:
            res_data['active'] = False
        return res_data

    def get_group_member_info(target_event, host_id, user_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_info()
        raw_obj = None
        this_msg = API.getUserView(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.user_id = str(user_id)
        this_msg.metadata.guild_id = str(host_id)
        this_msg.do_api()
        try:
            this_msg.do_api('GET')
            if this_msg.res != None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj != None:
                if type(raw_obj) == dict:
                    res_data['active'] = True
                    res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'username'], str)
                    res_data['data']['id'] = str(user_id)
                    res_data['data']['user_id'] = str(user_id)
                    res_data['data']['group_id'] = str(host_id)
                    res_data['data']['times']['join_time'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'joined_at'], int)
                    res_data['data']['times']['last_sent_time'] = 0
                    res_data['data']['times']['shut_up_timestamp'] = 0
                    res_data['data']['role'] = 'member'
                    res_data['data']['card'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'nickname'], str)
                    res_data['data']['title'] = ''
        except:
            res_data['active'] = False
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
        if tmp_obj['code'] == 0:
            flag_is_active = True
    if flag_is_active:
        if type(tmp_obj) == dict:
            res_data = tmp_obj.copy()
        elif type(tmp_obj) == list:
            res_data = tmp_obj.copy()
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
