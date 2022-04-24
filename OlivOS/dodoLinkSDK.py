# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/dodoLinkSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import requests as req
from requests_toolbelt import MultipartEncoder
import time
import traceback
import rsa
import base64
import uuid

import OlivOS

sdkAPIHost = {
    'default': 'https://botopen.imdodo.com/api/v1',
    'v1': 'https://botopen.imdodo.com/api/v1',
    'native': 'https://botopen.imdodo.com/api'
}

sdkAPIRoute = {
    'me': '/bot/info',
    'gateway': '/websocket/connection',
    'channel': '/channel',
    'personal': '/personal',
    'member': '/member',
    'resource': '/resource'
}

sdkAPIRouteTemp = {}

sdkSubSelfInfo = {}
sdkUserInfo = {}

class bot_info_T(object):
    def __init__(self, id = -1, password = '', host = '', access_token = None):
        self.id = id
        self.clientSecret = password
        self.publicKey = host
        self.access_token = access_token
        self.debug_mode = False
        self.debug_logger = None

def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(
        plugin_bot_info.id,
        plugin_bot_info.password,
        plugin_bot_info.post_info.host,
        plugin_bot_info.post_info.access_token
    )
    res.debug_mode = plugin_bot_info.debug_mode
    return res

def get_SDK_bot_info_from_Event(target_event):
    res = bot_info_T(
        target_event.bot_info.id,
        target_event.bot_info.password,
        target_event.bot_info.post_info.host,
        target_event.bot_info.post_info.access_token
    )
    res.debug_mode = target_event.bot_info.debug_mode
    return res

class event(object):
    def __init__(self, payload_obj = None, bot_info = None):
        self.payload = payload_obj
        self.platform = {}
        self.platform['sdk'] = 'dodo_link'
        self.platform['platform'] = 'dodo'
        self.platform['model'] = 'default'
        self.active = False
        if self.payload != None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = bot_info.id
            self.base_info['clientSecret'] = bot_info.password
            self.base_info['publicKey'] = bot_info.post_info.host
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

    def __str__(self):
        res = {}
        res['active'] = self.active
        res['data'] = str(self.data)
        return str(res)

    class data_T(object):
        def __init__(self):
            self.type = None
            self.data = None

        def __str__(self):
            return str(self.__dict__)

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
                if 'type' in data:
                    self.data.type = data['type']
                if 'data' in data:
                    self.data.data = data['data']
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
                    tmp_payload_dict[data_this] = self.data.__dict__[data_this]

            payload = json.dumps(obj = tmp_payload_dict)
            send_url_temp = self.host + self.route
            send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                'Authorization': 'Bot %s.%s' % (
                    str(self.bot_info.id),
                    self.bot_info.access_token
                )
            }

            msg_res = None
            if req_type == 'POST':
                msg_res = req.request("POST", send_url, headers = headers, data = payload)
            elif req_type == 'GET':
                msg_res = req.request("GET", send_url, headers = headers)

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ' - sendding succeed: ' + msg_res.text)

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
            self.route = sdkAPIRoute['gateway']

    class getMe(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['me']

    class sendChannelMessage(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channel'] + '/message/send'

        class data_T(object):
            def __init__(self):
                self.channelId = '-1'
                self.messageType = 1
                self.messageBody = {}
                self.referencedMessageId = None

    class sendPersonalMessage(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['personal'] + '/message/send'

        class data_T(object):
            def __init__(self):
                self.dodoId = '-1'
                self.messageType = 1
                self.messageBody = {}

    class getMemberInfo(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['member'] + '/info'

        class data_T(object):
            def __init__(self):
                self.islandId = '-1'
                self.dodoId = '-1'

    class setResourcePictureUpload(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['resource'] + '/picture/upload'

        class data_T(object):
            def __init__(self):
                self.file = None

        def do_api(self, req_type = 'POST'):
            try:
                tmp_payload_dict = {}
                tmp_payload_dict['file'] = (str(uuid.uuid4()) + '.png', self.data.file, 'image/png')
                payload = MultipartEncoder(
                    fields = tmp_payload_dict
                )

                tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
                send_url_temp = self.host + self.route
                send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
                headers = {
                    'Content-Type': payload.content_type,
                    'Content-Length': str(len(self.data.file)),
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'Authorization': 'Bot %s.%s' % (
                        str(self.bot_info.id),
                        self.bot_info.access_token
                    )
                }

                msg_res = None
                if req_type == 'POST':
                    msg_res = req.request("POST", send_url, headers = headers, data = payload)

                self.res = msg_res.text
                return msg_res.text
            except:
                return None

def get_Event_from_SDK(target_event):
    global sdkSubSelfInfo
    global sdkUserInfo
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
    tmp_bot_info = bot_info_T(
        target_event.sdk_event.base_info['self_id'],
        target_event.sdk_event.base_info['clientSecret'],
        target_event.sdk_event.base_info['publicKey'],
        target_event.sdk_event.base_info['token']
    )
    if plugin_event_bot_hash not in sdkSubSelfInfo:
        api_msg_obj = API.getMe(tmp_bot_info)
        try:
            api_msg_obj.do_api('POST')
            api_res_json = json.loads(api_msg_obj.res)
            if api_res_json['status'] == 0:
                sdkSubSelfInfo[plugin_event_bot_hash] = int(api_res_json['data']['dodoId'])
        except:
            pass
    try:
        if target_event.sdk_event.payload.data.type == 0:
            if target_event.sdk_event.payload.data.data['eventType'] == str(2001):
                message_obj = None
                if target_event.sdk_event.payload.data.data['eventBody']['messageType'] == 1:
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'dodo_string',
                        target_event.sdk_event.payload.data.data['eventBody']['messageBody']['content']
                    )
                    message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                    message_obj.data_raw = message_obj.data.copy()
                elif target_event.sdk_event.payload.data.data['eventBody']['messageType'] == 2:
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'olivos_para',
                        [
                            OlivOS.messageAPI.PARA.image(
                                target_event.sdk_event.payload.data.data['eventBody']['messageBody']['url']
                            )
                        ]
                    )
                elif target_event.sdk_event.payload.data.data['eventBody']['messageType'] == 3:
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'olivos_para',
                        [
                            OlivOS.messageAPI.PARA.video(
                                target_event.sdk_event.payload.data.data['eventBody']['messageBody']['url']
                            )
                        ]
                    )
                if message_obj != None:
                    target_event.active = True
                    tmp_host_id = str(target_event.sdk_event.payload.data.data['eventBody']['islandId'])
                    tmp_user_id = str(target_event.sdk_event.payload.data.data['eventBody']['dodoId'])
                    if tmp_host_id not in sdkUserInfo:
                        sdkUserInfo[tmp_host_id] = {}
                    if tmp_user_id not in sdkUserInfo[tmp_host_id]:
                        api_msg_obj = API.getMemberInfo(tmp_bot_info)
                        api_msg_obj.data.islandId = tmp_host_id
                        api_msg_obj.data.dodoId = tmp_user_id
                        api_msg_obj.do_api('POST')
                        api_res_json = json.loads(api_msg_obj.res)
                        if api_res_json['status'] == 0:
                            sdkUserInfo[tmp_host_id][tmp_user_id] = {}
                            sdkUserInfo[tmp_host_id][tmp_user_id] = api_res_json['data'].copy()
                    target_event.plugin_info['func_type'] = 'group_message'
                    target_event.data = target_event.group_message(
                        str(target_event.sdk_event.payload.data.data['eventBody']['channelId']),
                        str(target_event.sdk_event.payload.data.data['eventBody']['dodoId']),
                        message_obj,
                        'group'
                    )
                    target_event.data.host_id = str(target_event.sdk_event.payload.data.data['eventBody']['islandId'])
                    target_event.data.message_sdk = message_obj
                    target_event.data.message_id = str(target_event.sdk_event.payload.data.data['eventBody']['messageId'])
                    target_event.data.raw_message = message_obj
                    target_event.data.raw_message_sdk = message_obj
                    target_event.data.font = None
                    target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.data.data['eventBody']['dodoId'])
                    target_event.data.sender['id'] = str(target_event.sdk_event.payload.data.data['eventBody']['dodoId'])
                    target_event.data.sender['nickname'] = 'User'
                    target_event.data.sender['name'] = 'User'
                    target_event.data.sender['sex'] = 'unknown'
                    target_event.data.sender['age'] = 0
                    if tmp_user_id in sdkUserInfo[tmp_host_id]:
                        if 'nickName' in sdkUserInfo[tmp_host_id][tmp_user_id]:
                            target_event.data.sender['nickname'] = sdkUserInfo[tmp_host_id][tmp_user_id]['nickName']
                            target_event.data.sender['name'] = sdkUserInfo[tmp_host_id][tmp_user_id]['nickName']
                        if 'sex' in sdkUserInfo[tmp_host_id][tmp_user_id]:
                            if sdkUserInfo[tmp_host_id][tmp_user_id]['sex'] == 0:
                                target_event.data.sender['sex'] = 'female'
                            elif sdkUserInfo[tmp_host_id][tmp_user_id]['sex'] == 1:
                                target_event.data.sender['sex'] = 'male'
                    target_event.data.extend['host_group_id'] = str(target_event.sdk_event.payload.data.data['eventBody']['islandId'])
                    if plugin_event_bot_hash in sdkSubSelfInfo:
                        target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
            elif target_event.sdk_event.payload.data.data['eventType'] == str(1001):
                message_obj = None
                if target_event.sdk_event.payload.data.data['eventBody']['messageType'] == 1:
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'dodo_string',
                        target_event.sdk_event.payload.data.data['eventBody']['messageBody']['content']
                    )
                    message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                    message_obj.data_raw = message_obj.data.copy()
                elif target_event.sdk_event.payload.data.data['eventBody']['messageType'] == 2:
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'olivos_para',
                        [
                            OlivOS.messageAPI.PARA.image(
                                target_event.sdk_event.payload.data.data['eventBody']['messageBody']['url']
                            )
                        ]
                    )
                elif target_event.sdk_event.payload.data.data['eventBody']['messageType'] == 3:
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'olivos_para',
                        [
                            OlivOS.messageAPI.PARA.video(
                                target_event.sdk_event.payload.data.data['eventBody']['messageBody']['url']
                            )
                        ]
                    )
                if message_obj != None:
                    target_event.active = True
                    tmp_user_info = target_event.sdk_event.payload.data.data['eventBody']['personal']       # use personal info from remote instead of local
                    tmp_user_id = str(target_event.sdk_event.payload.data.data['eventBody']['dodoId'])
                    target_event.plugin_info['func_type'] = 'private_message'
                    target_event.data = target_event.private_message(
                        str(target_event.sdk_event.payload.data.data['eventBody']['dodoId']),
                        message_obj,
                        'private'
                    )
                    target_event.data.message_sdk = message_obj
                    target_event.data.message_id = str(target_event.sdk_event.payload.data.data['eventBody']['messageId'])
                    target_event.data.raw_message = message_obj
                    target_event.data.raw_message_sdk = message_obj
                    target_event.data.font = None
                    target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.data.data['eventBody']['dodoId'])
                    target_event.data.sender['id'] = str(target_event.sdk_event.payload.data.data['eventBody']['dodoId'])
                    target_event.data.sender['nickname'] = 'User'
                    target_event.data.sender['name'] = 'User'
                    target_event.data.sender['sex'] = 'unknown'
                    target_event.data.sender['age'] = 0
                    if tmp_user_info:
                        if 'nickName' in tmp_user_info:
                            target_event.data.sender['nickname'] = tmp_user_info['nickName']
                            target_event.data.sender['name'] = tmp_user_info['nickName']
                        if 'sex' in tmp_user_info:
                            if tmp_user_info["sex"] == 0:
                                target_event.data.sender['sex'] = 'female'
                            elif tmp_user_info['sex'] == 1:
                                target_event.data.sender['sex'] = 'male'
                    # target_event.data.extend['host_group_id'] = str(target_event.sdk_event.payload.data.data['eventBody']['islandId'])
                    if plugin_event_bot_hash in sdkSubSelfInfo:
                        target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
    except:
        target_event.active = False


#支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, chat_id, message):
        this_msg = None
        this_msg = API.sendChannelMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.channelId = str(chat_id)
        for message_this in message.data:
            if type(message_this) is OlivOS.messageAPI.PARA.text:
                this_msg.data.messageType = 1
                this_msg.data.messageBody = {}
                this_msg.data.messageBody['content'] = message_this.data['text']
                this_msg.do_api('POST')
            elif type(message_this) is OlivOS.messageAPI.PARA.image:
                this_msg.data.messageType = 2
                this_msg.data.messageBody = None
                this_msg.data.messageBody = event_action.setImageUploadFast(target_event, message_this.data['file'])
                if this_msg.data.messageBody != None:
                    this_msg.do_api('POST')

    def send_personal_msg(target_event, chat_id, message):
        this_msg = None
        this_msg = API.sendPersonalMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.dodoId = str(chat_id)
        for message_this in message.data:
            if type(message_this) is OlivOS.messageAPI.PARA.text:
                this_msg.data.messageType = 1
                this_msg.data.messageBody = {}
                this_msg.data.messageBody['content'] = message_this.data['text']
                this_msg.do_api('POST')
            elif type(message_this) is OlivOS.messageAPI.PARA.image:
                tmp_image_url = message_this.data['url']
                this_msg.data.messageType = 2
                this_msg.data.messageBody = None
                this_msg.data.messageBody = event_action.setImageUploadFast(target_event, message_this.data['file'])
                if this_msg.data.messageBody != None:
                    this_msg.do_api('POST')

    def get_login_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        raw_obj = None
        this_msg = API.getMe(get_SDK_bot_info_from_Event(target_event))
        try:
            this_msg.do_api('POST')
            if this_msg.res != None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj != None:
                if type(raw_obj) == dict:
                    res_data['active'] = True
                    res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'nickName'], str)
                    res_data['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'dodoId'], str)
        except:
            res_data['active'] = False
        return res_data

    #现场上传的就地实现
    def setImageUploadFast(target_event, url):
        res = None
        try:
            send_url = url
            headers = {
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA
            }
            msg_res = None
            msg_res = req.request("GET", send_url, headers = headers)
            msg_upload_api = API.setResourcePictureUpload(get_SDK_bot_info_from_Event(target_event))
            msg_upload_api.data.file = msg_res.content
            msg_upload_api.do_api()
            if msg_upload_api.res != None:
                msg_upload_api_obj = json.loads(msg_upload_api.res)
                if msg_upload_api_obj['status'] == 0:
                    res = msg_upload_api_obj['data']
        except:
            res = None
        return res


def init_api_json(raw_str):
    res_data = None
    tmp_obj = None
    flag_is_active = False
    try:
        tmp_obj = json.loads(raw_str)
    except:
        tmp_obj = None
    if type(tmp_obj) == dict:
        if tmp_obj['status'] == 0:
            flag_is_active = True
    if flag_is_active:
        if type(tmp_obj) == dict:
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
