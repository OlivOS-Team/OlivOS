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
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import requests as req
import time
from requests_toolbelt import MultipartEncoder
import uuid
import traceback
import base64
from urllib import parse

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
    'gateway': '/gateway',
    'asset': '/asset',
    'game': '/game'
}

sdkAPIRouteTemp = {}

sdkSubSelfInfo = {}


class bot_info_T(object):
    def __init__(self, id=-1, access_token=None):
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
    def __init__(self, payload_obj=None, bot_info=None):
        self.payload = payload_obj
        self.platform = {'sdk': 'kaiheila_link', 'platform': 'kaiheila', 'model': 'default'}
        if type(bot_info.platform) is dict:
            self.platform.update(bot_info.platform)
        self.active = False
        if self.payload is not None:
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
    def __init__(self, data=None, is_rx=False):
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
            if self.data.__dict__[data_this] is not None:
                res_obj[data_this] = self.data.__dict__[data_this]
        res = json.dumps(obj=res_obj)
        return res

    def load(self, data, is_rx):
        if data is not None:
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
        def __init__(self, last_s=None):
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

    def do_api(self, req_type='POST'):
        try:
            tmp_payload_dict = {}
            tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
            if self.metadata is not None:
                tmp_sdkAPIRouteTemp.update(self.metadata.__dict__)
            if self.data is not None:
                for data_this in self.data.__dict__:
                    if self.data.__dict__[data_this] is not None:
                        tmp_payload_dict[data_this] = self.data.__dict__[data_this]

            payload = json.dumps(obj=tmp_payload_dict)
            send_url_temp = self.host + self.route
            send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                'Authorization': 'Bot %s' % self.bot_info.access_token
            }

            msg_res = None
            if req_type == 'POST':
                msg_res = req.request("POST", send_url, headers=headers, data=payload)
            elif req_type == 'GET':
                msg_res = req.request("GET", send_url, headers=headers)

            self.res = msg_res.text
            return msg_res.text
        except:
            return None


class API(object):
    class getGateway(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['gateway'] + '/index?compress=0'

    class getMe(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['user'] + '/me'

    class creatMessage(api_templet):
        def __init__(self, bot_info=None):
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
        def __init__(self, bot_info=None):
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
        def __init__(self, bot_info=None):
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
        def __init__(self, bot_info=None):
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

    class setResourcePictureUpload(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['asset'] + '/create'

        class data_T(object):
            def __init__(self):
                self.file = None

        def do_api(self, req_type='POST', file_type: str = ['.png', 'image/png']):
            try:
                tmp_payload_dict = {'file': (str(uuid.uuid4()) + file_type[0], self.data.file, file_type[1])}
                payload = MultipartEncoder(
                    fields=tmp_payload_dict
                )

                tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
                send_url_temp = self.host + self.route
                send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
                headers = {
                    'Content-Type': payload.content_type,
                    'Content-Length': str(len(self.data.file)),
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'Authorization': 'Bot %s' % self.bot_info.access_token
                }

                msg_res = None
                if req_type == 'POST':
                    msg_res = req.request("POST", send_url, headers=headers, data=payload)

                self.res = msg_res.text
                return msg_res.text
            except Exception as e:
                traceback.print_exc()
                return None

    #在玩游戏相关接口
    class getPlayGameList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['game']

    class setPlayGameCreate(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['game'] + '/create'

        class data_T(object):
            def __init__(self):
                self.name = "N/A"
                self.icon = None

    class setPlayGameUpdate(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['game'] + '/update'

        class data_T(object):
            def __init__(self):
                self.id = -1
                self.name = None
                self.icon = None

    class setPlayGameDelete(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['game'] + '/delete'

        class data_T(object):
            def __init__(self):
                self.id = -1

    class setPlayGameActivity(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['game'] + '/activity'

        class data_T(object):
            def __init__(self):
                self.id = -1
                self.data_type = 1
                self.software = None
                self.singer = None
                self.music_name = None

    class setPlayGameDeleteActivity(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['game'] + '/delete-activity'

        class data_T(object):
            def __init__(self):
                self.data_type = 1


def get_kmarkdown_message_raw(data: dict):
    res = data['raw_content']
    return res

def get_message_obj(target_event):
    flag_hit = False
    if 'type' in target_event.sdk_event.payload.data.d:
        if 1 == target_event.sdk_event.payload.data.d['type'] \
        and 'content' in target_event.sdk_event.payload.data.d:
            flag_hit = True
            message_obj = OlivOS.messageAPI.Message_templet(
                'kaiheila_string',
                target_event.sdk_event.payload.data.d['content']
            )
            message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
            message_obj.data_raw = message_obj.data.copy()
        elif 9 == target_event.sdk_event.payload.data.d['type'] \
        and 'content' in target_event.sdk_event.payload.data.d:
            flag_hit = True
            message_obj = OlivOS.messageAPI.Message_templet(
                'kaiheila_string',
                target_event.sdk_event.payload.data.d['content']
            )
            message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
            message_obj.data_raw = message_obj.data.copy()
        elif 2 == target_event.sdk_event.payload.data.d['type'] \
        and 'content' in target_event.sdk_event.payload.data.d:
            flag_hit = True
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                [
                    OlivOS.messageAPI.PARA.image(file=target_event.sdk_event.payload.data.d['content'])
                ]
            )
        elif 3 == target_event.sdk_event.payload.data.d['type'] \
        and 'content' in target_event.sdk_event.payload.data.d:
            flag_hit = True
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                [
                    OlivOS.messageAPI.PARA.video(file=target_event.sdk_event.payload.data.d['content'])
                ]
            )
        elif 8 == target_event.sdk_event.payload.data.d['type'] \
        and 'content' in target_event.sdk_event.payload.data.d:
            flag_hit = True
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                [
                    OlivOS.messageAPI.PARA.record(file=target_event.sdk_event.payload.data.d['content'])
                ]
            )
    if not flag_hit:
        message_obj = OlivOS.messageAPI.Message_templet(
            'olivos_para',
            []
        )
        message_obj.active = False
    else:
        try:
            message_obj.init_data()
        except:
            message_obj.active = False
            message_obj.data = []
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
        bot_id=target_event.base_info['self_id'],
        platform_sdk=target_event.platform['sdk'],
        platform_platform=target_event.platform['platform'],
        platform_model=target_event.platform['model']
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
            message_obj = get_message_obj(target_event)
            if message_obj.active:
                try:
                    if 'extra' in target_event.sdk_event.payload.data.d \
                    and 'type' in target_event.sdk_event.payload.data.d:
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
                        target_event.data.sender['user_id'] = str(
                            target_event.sdk_event.payload.data.d['extra']['author']['id'])
                        target_event.data.sender['nickname'] = target_event.sdk_event.payload.data.d['extra']['author'][
                            'username']
                        target_event.data.sender['id'] = str(
                            target_event.sdk_event.payload.data.d['extra']['author']['id'])
                        target_event.data.sender['name'] = target_event.sdk_event.payload.data.d['extra']['author'][
                            'username']
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
                except Exception as e:
                    traceback.print_exc()
                    target_event.active = False
        elif target_event.sdk_event.payload.data.d['channel_type'] == 'PERSON':
            message_obj = get_message_obj(target_event)
            if message_obj.active:
                try:
                    if 'extra' in target_event.sdk_event.payload.data.d \
                    and 'type' in target_event.sdk_event.payload.data.d:
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
                        target_event.data.sender['user_id'] = str(
                            target_event.sdk_event.payload.data.d['extra']['author']['id'])
                        target_event.data.sender['nickname'] = target_event.sdk_event.payload.data.d['extra']['author'][
                            'username']
                        target_event.data.sender['id'] = str(
                            target_event.sdk_event.payload.data.d['extra']['author']['id'])
                        target_event.data.sender['name'] = target_event.sdk_event.payload.data.d['extra']['author'][
                            'username']
                        target_event.data.sender['sex'] = 'unknown'
                        target_event.data.sender['age'] = 0
                        target_event.data.extend['flag_from_direct'] = True
                        if plugin_event_bot_hash in sdkSubSelfInfo:
                            target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
                        if str(target_event.data.user_id) == str(target_event.base_info['self_id']):
                            target_event.active = False
                    else:
                        target_event.active = False
                except Exception as e:
                    traceback.print_exc()
                    target_event.active = False


# 支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, chat_id, message, flag_direct=False, message_type_in='card'):
        message_type = message_type_in
        if target_event is not None:
            if target_event.bot_info.platform['model'] != 'default':
                if target_event.bot_info.platform['model'] == 'text':
                    message_type = 'text'
                elif target_event.bot_info.platform['model'] == 'card':
                    message_type = 'card'
        if message_type not in ['text', 'card']:
            message_type = 'card'
        this_msg = None
        if message_type == 'text':
            res_data = ''
        elif message_type == 'card':
            res_data = {
                "type": "card",
                "theme": "secondary",
                "size": "lg",
                "modules": []
            }
        if flag_direct:
            this_msg = API.creatDirectMessage(get_SDK_bot_info_from_Event(target_event))
        else:
            this_msg = API.creatMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.target_id = str(chat_id)
        if this_msg is None:
            return
        msg_type_last = 'text'
        for message_this in message.data:
            if message_type == 'text':
                if type(message_this) == OlivOS.messageAPI.PARA.text:
                    if msg_type_last != 'text':
                        res_data = ''
                    res_data += message_this.data['text']
                    msg_type_last = 'text'
                elif type(message_this) == OlivOS.messageAPI.PARA.image:
                    if msg_type_last == 'text':
                        if len(res_data) > 0:
                            this_msg.data.type = 9
                            this_msg.data.content = res_data
                            this_msg.do_api()
                        image_path = event_action.setResourceUploadFast(target_event, message_this.data['file'], 'images')
                        this_msg.data.type = 2
                        this_msg.data.content = image_path
                        this_msg.do_api()
                    msg_type_last = 'media'
            elif message_type == 'card':
                if type(message_this) == OlivOS.messageAPI.PARA.text:
                    res_data['modules'].append(
                        {
                            "type": "section",
                            "text": {
                                "type": "plain-text",
                                "content": message_this.data['text']
                            }
                        }
                    )
                elif type(message_this) == OlivOS.messageAPI.PARA.image:
                    image_path = event_action.setResourceUploadFast(target_event, message_this.data['file'], 'images')
                    res_data['modules'].append(
                        {
                            "type": "image-group",
                            "elements": [
                                {
                                    "type": "image",
                                    "src": image_path
                                }
                            ]
                        }
                    )
                elif type(message_this) == OlivOS.messageAPI.PARA.video:
                    video_path = event_action.setResourceUploadFast(target_event, message_this.data['file'], 'videos')
                    res_data['modules'].append(
                        {
                            "type": "video",
                            "title": "video.mp4",
                            "src": video_path
                        }
                    )
                elif type(message_this) == OlivOS.messageAPI.PARA.record:
                    audio_path = event_action.setResourceUploadFast(target_event, message_this.data['file'], 'audios')
                    res_data['modules'].append(
                        {
                            "type": "audio",
                            "title": "audio.mp4",
                            "src": audio_path
                        }
                    )
        if message_type == 'text':
            if len(res_data) > 0:
                this_msg.data.type = 9
                this_msg.data.content = res_data
                this_msg.do_api()
        elif message_type == 'card':
            if len(res_data['modules']) > 0:
                this_msg.data.type = 10
                this_msg.data.content = json.dumps([res_data], ensure_ascii=False)
                this_msg.do_api()

    def get_login_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        raw_obj = None
        this_msg = API.getMe(get_SDK_bot_info_from_Event(target_event))
        try:
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
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
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
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
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) == dict:
                    res_data['active'] = True
                    res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'username'], str)
                    res_data['data']['id'] = str(user_id)
                    res_data['data']['user_id'] = str(user_id)
                    res_data['data']['group_id'] = str(host_id)
                    res_data['data']['times']['join_time'] = init_api_do_mapping_for_dict(raw_obj,
                                                                                          ['data', 'joined_at'], int)
                    res_data['data']['times']['last_sent_time'] = 0
                    res_data['data']['times']['shut_up_timestamp'] = 0
                    res_data['data']['role'] = 'member'
                    res_data['data']['card'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'nickname'], str)
                    res_data['data']['title'] = ''
        except:
            res_data['active'] = False
        return res_data

    # 现场上传的就地实现
    def setResourceUploadFast(target_event, url: str, type_path: str = 'images'):
        res = None
        check_list = {
            'images': ['.png', 'image/png'],
            'videos': ['.mp4', 'video/mp4'],
            'audios': ['.mp3', 'audio/mp3']
        }
        check_list.setdefault(type_path, ['', 'file/*'])
        try:
            pic_file = None
            if url.startswith("base64://"):
                data = url[9:]
                pic_file = base64.decodebytes(data.encode("utf-8"))
            else:
                url_parsed = parse.urlparse(url)
                if url_parsed.scheme in ["http", "https"]:
                    send_url = url
                    headers = {
                        'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA
                    }
                    msg_res = None
                    msg_res = req.request("GET", send_url, headers=headers)
                    pic_file = msg_res.content
                else:
                    file_path = url_parsed.path
                    file_path = OlivOS.contentAPI.resourcePathTransform(type_path, file_path)
                    with open(file_path, "rb") as f:
                        pic_file = f.read()

            msg_upload_api = API.setResourcePictureUpload(get_SDK_bot_info_from_Event(target_event))
            msg_upload_api.data.file = pic_file
            msg_upload_api.do_api('POST', check_list[type_path])
            if msg_upload_api.res is not None:
                msg_upload_api_obj = json.loads(msg_upload_api.res)
                if 'code' in msg_upload_api_obj \
                and 0 == msg_upload_api_obj['code'] \
                and 'data' in msg_upload_api_obj \
                and 'url' in msg_upload_api_obj['data']:
                    res = msg_upload_api_obj['data']['url']
        except Exception as e:
            traceback.print_exc()
            res = None
        return res

    def set_playgame_delete_activity(target_event, data_type:int):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.setPlayGameDeleteActivity(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.data_type = data_type
        try:
            this_msg.do_api('POST')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) is dict:
                    res_data['active'] = True
        except:
            res_data['active'] = False
            return res_data
        return res_data

    def set_playgame_delete_activity_all(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['active'] = False
        for i in [1, 2]:
            res_data = event_action.set_playgame_delete_activity(target_event, i)
            if not res_data['active']:
                return res_data
        return res_data

    def set_playgame_activity_game(target_event, game_id):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['active'] = False
        res_data = event_action.set_playgame_delete_activity_all(target_event)
        if not res_data['active']:
            return res_data
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.setPlayGameActivity(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.data_type = 1
        this_msg.data.id = game_id
        try:
            this_msg.do_api('POST')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) is dict:
                    res_data['active'] = True
                    res_data['data'] = {}
                    res_data['data']['id'] = game_id
        except:
            res_data['active'] = False
            return res_data
        return res_data

    def set_playgame_activity_music(target_event, music_name, singer, software):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['active'] = False
        res_data = event_action.set_playgame_delete_activity_all(target_event)
        if not res_data['active']:
            return res_data
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.setPlayGameActivity(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.data_type = 2
        this_msg.data.id = None
        this_msg.data.software = software
        this_msg.data.music_name = music_name
        this_msg.data.singer = singer
        try:
            this_msg.do_api('POST')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) is dict:
                    res_data['active'] = True
                    res_data['data'] = {}
                    res_data['data']['music_name'] = music_name
                    res_data['data']['singer'] = singer
                    res_data['data']['software'] = software
        except:
            res_data['active'] = False
        return res_data

class inde_interface(OlivOS.API.inde_interface_T):
    @OlivOS.API.Event.callbackLogger('kaiheila:set_playgame_delete_activity_all')
    def __set_playgame_delete_activity_all(target_event, flag_log=True):
        res_data = None
        res_data = OlivOS.kaiheilaSDK.event_action.set_playgame_delete_activity_all(target_event)
        return res_data

    def set_playgame_delete_activity_all(self, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = inde_interface.__set_playgame_delete_activity_all(self.event, flag_log=True)
        return res_data

    @OlivOS.API.Event.callbackLogger('kaiheila:set_playgame_activity_game', ['id'])
    def __set_playgame_activity_game(target_event, game_id, flag_log=True):
        res_data = None
        res_data = OlivOS.kaiheilaSDK.event_action.set_playgame_activity_game(target_event, game_id)
        return res_data

    def set_playgame_activity_game(self, game_id:int, flag_log: bool = True, remote: bool = False):
        res_data = None
        if remote:
            pass
        else:
            res_data = inde_interface.__set_playgame_activity_game(self.event, game_id, flag_log=True)
        return res_data

    @OlivOS.API.Event.callbackLogger('kaiheila:set_playgame_activity_music', ['music_name', 'singer', 'software'])
    def __set_playgame_activity_music(target_event, music_name, singer, software, flag_log=True):
        res_data = None
        res_data = OlivOS.kaiheilaSDK.event_action.set_playgame_activity_music(target_event, music_name, singer, software)
        return res_data

    def set_playgame_activity_music(
        self,
        music_name:str,
        singer:str,
        software:str = 'cloudmusic',
        flag_log: bool = True,
        remote: bool = False
    ):
        res_data = None
        if remote:
            pass
        else:
            res_data = inde_interface.__set_playgame_activity_music(self.event, music_name, singer, software, flag_log=True)
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
