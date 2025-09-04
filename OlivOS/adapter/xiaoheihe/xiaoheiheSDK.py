# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/xiaoheiheSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
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
    'wss': 'wss://chat.xiaoheihe.cn/chatroom/ws/connect',
    'default': 'https://chat.xiaoheihe.cn',
    'native': 'https://chat.xiaoheihe.cn'
}

sdkAPIRoute = {
    'wss': '?chat_os_type=bot&client_type=heybox_chat&chat_version=1.30.0&token=',
    'channel_msg': '/chatroom/v2/channel_msg',
    'msg': '/chatroom/v3/msg'
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
        self.platform = {'sdk': 'xiaoheihe_link', 'platform': 'xiaoheihe', 'model': 'default'}
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
对于WEBSOCKET接口的URI生成
'''


def get_websocket_url(bot_info: OlivOS.API.bot_info_T):
    token = str(bot_info.post_info.access_token)
    send_url = sdkAPIHost['wss'] + sdkAPIRoute['wss'] + token
    return send_url


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
            self.sequence = None
            self.type = None
            self.notify_type = None
            self.data = None
            self.timestamp = None

    def dump(self):
        res_obj = {}
        for data_this in self.data.__dict__:
            if self.data.__dict__[data_this] is not None:
                res_obj[data_this] = self.data.__dict__[data_this]
        res = json.dumps(obj=res_obj)
        return res

    def load(self, data, is_rx):
        if data is not None:
            if type(data) is dict:
                if 'sequence' in data:
                    self.data.sequence = data['sequence']
                if 'type' in data:
                    self.data.type = data['type']
                if 'notify_type' in data:
                    self.data.notify_type = data['notify_type']
                if 'data' in data:
                    self.data.data = data['data']
                if 'timestamp' in data:
                    self.data.timestamp = data['timestamp']
            else:
                self.active = False
        return self


class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, data):
            payload_template.__init__(self, data, True)

    class sendPing(object):
        def __init__(self):
            pass

        def dump(self):
            return 'PING'


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
            params = {
                'client_type': 'heybox_chat',
                'x_client_type': 'web',
                'os_type': 'web',
                'x_os_type': 'bot',
                'x_app': 'heybox_chat',
                'chat_os_type': 'bot',
                'chat_version': '1.30.0'
            }
            send_url = f'{send_url}?{parse.urlencode(params)}'
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                'Token': self.bot_info.access_token
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
    class sendChannelMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channel_msg'] + '/send'

        class data_T(object):
            def __init__(self):
                self.addition = None
                self.room_id = None
                self.channel_id = None
                self.heychat_ack_id = None
                self.msg_type = None
                self.msg = None
                self.reply_id = ''


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

    # print(target_event.sdk_event.payload.data.__dict__)
        
    if '5' == target_event.sdk_event.payload.data.type:
        try:
            if 'room_id' in target_event.sdk_event.payload.data.data \
            and 'channel_id' in target_event.sdk_event.payload.data.data \
            and 'msg_id' in target_event.sdk_event.payload.data.data \
            and 'user_id' in target_event.sdk_event.payload.data.data \
            and 'nickname' in target_event.sdk_event.payload.data.data \
            and 'msg' in target_event.sdk_event.payload.data.data:
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_message'
                msg_raw = target_event.sdk_event.payload.data.data['msg']
                target_event.data = target_event.group_message(
                    str(target_event.sdk_event.payload.data.data['channel_id']),
                    str(target_event.sdk_event.payload.data.data['user_id']),
                    msg_raw,
                    'group'
                )
                target_event.data.host_id = str(target_event.sdk_event.payload.data.data['room_id'])
                target_event.data.message_sdk = OlivOS.messageAPI.Message_templet(
                    target_event.plugin_info['message_mode_tx'],
                    msg_raw
                )
                target_event.data.message_id = str(target_event.sdk_event.payload.data.data['msg_id'])
                target_event.data.raw_message = msg_raw
                target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet(
                    target_event.plugin_info['message_mode_tx'],
                    msg_raw
                )
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.data.data['user_id'])
                target_event.data.sender['nickname'] = str(target_event.sdk_event.payload.data.data['nickname'])
                target_event.data.sender['id'] = target_event.data.sender['user_id']
                target_event.data.sender['name'] = target_event.data.sender['nickname']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0
                target_event.data.sender['role'] = 'member'
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

# 支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, group_id, host_id, message, reply_id=None, flag_direct=False):
        this_msg = None
        res_data = {
            "type": "card",
            "border_color": "#009FE9",
            "size": "medium",
            "modules": []
        }
        if flag_direct:
            pass
        else:
            this_msg = API.sendChannelMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.data.msg_type = 20
            this_msg.data.channel_id = str(group_id)
            this_msg.data.room_id = str(host_id)
            this_msg.data.heychat_ack_id = '0'
            this_msg.data.addition = '{}'
            if reply_id is not None:
                this_msg.data.reply_id = reply_id
        for message_this in message.data:
            if type(message_this) == OlivOS.messageAPI.PARA.text:
                res_data['modules'].append(
                    {
                      "type": "section",
                      "paragraph": [
                        {
                          "type": "plain-text",
                          "text": message_this.data['text'].replace('\r\n', '\n').replace('\n', '<br>')
                        }
                      ]
                    }
                )
            elif type(message_this) == OlivOS.messageAPI.PARA.image:
                pass
                # 后续再实现图片的上传和插入
                #image_path = event_action.setResourceUploadFast(target_event, message_this.data['file'], 'images')
                #res_data['modules'].append(
                #    {
                #        "type": "images",
                #        "urls": [
                #          {
                #            "url": image_path
                #          }
                #        ]
                #    }
                #)
        if len(res_data['modules']) > 0:
            this_msg.data.msg = json.dumps({"data": [res_data]}, ensure_ascii=False)
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
