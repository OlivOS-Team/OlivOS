# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/dingtalkSDK.py
@Author    :   RainyZhou雨舟, OlivOS-Team
@Contact   :   thunderain_zhou@163.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import traceback
import time
import uuid
import base64
import os
import dataclasses
import typing
# import mimetypes
import filetype
from enum import IntEnum

import requests as req
from requests_toolbelt import MultipartEncoder
from urllib import parse
from urllib3 import encode_multipart_formdata

import OlivOS

sdkAPIHost = {
    'default': 'https://api.dingtalk.com',
    # websocket 连接
    # "ws": "wss://wss-open-connection.dingtalk.com:443/connect"
}

sdkAPIRoute = {
    "old": "",                                          # 对于旧版和其他api情况，使用这个
    "gateway": "/v1.0/gateway/connections/open",        # 用于获取 websocket 连接
    "oauth": "/v1.0/oauth2",                            # 身份验证，用于获取 access token
    "bot": "/v1.0/robot"                                # 机器人相关（发送信息）
}

# endpoint 中的元数据
sdkAPIRouteTemp = {}

sdkSubSelfInfo = {}


def _init_kw_dataclass_safe(**kwargs):
    """
        用于兼容 python 3.9 及以下版本的 dataclass
    """
    if sys.version_info.minor < 10:
        return dataclasses.dataclass(**kwargs)
    else:
        return dataclasses.dataclass(kw_only=True, **kwargs)

class RESPONSE_STATUS_CODE(IntEnum):
    UNKNOWN = 0
    SUCCESS = 200
    NOT_FOUND = 404
    FAIL = 500


class bot_info_T(object):
    def __init__(self, id=-1, AppKey=None, AppSecret=None, model='private'):
        self.id = id
        self.app_key = AppKey
        self.app_secret = AppSecret
        self._access_token = None               # 在 dingtalk 中，access_token 7200s 过期，故需要基于函数生成
        self._expire_time = None
        self.model = model
        self.debug_mode = False
        self.debug_logger = None

    @property
    def access_token(self):
        """
            access token获取的就地实现
            如不存在或过期则自动获取，如果获取失败则返回 None
        """
        time_this = time.time()
        if self._access_token is not None and self._expire_time is not None:
            if time_this < self._expire_time:
                return self._access_token
        api_obj = API.getAccessToken(self)
        res = api_obj.do_api()
        if res is not None:
            self._access_token = res["accessToken"]
            self._expire_time = time_this + max(int(res["expireIn"])-200, 200)              # 提早 200s 更新 access token
            return self._access_token
        return None

def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    """
        基于本地缓存查看
    """
    global sdkSubSelfInfo
    bot_hash_this = plugin_bot_info.getHash()
    if bot_hash_this in sdkSubSelfInfo:
        return sdkSubSelfInfo[bot_hash_this]

    res = bot_info_T(
        id = plugin_bot_info.id,
        AppKey = plugin_bot_info.extends["app_key"],
        AppSecret = plugin_bot_info.extends["app_secret"]
    )
    res.debug_mode = plugin_bot_info.debug_mode
    if plugin_bot_info.platform['model'] == 'public':
        res.model = 'public'
    sdkSubSelfInfo[bot_hash_this] = res
    return res


def get_SDK_bot_info_from_Event(target_event):
    if target_event.bot_info is None:
        res = target_event.sdk_event.base_info.get("sdk_bot_info", None)
        # if target_event.base_info["sdk_bot_info"] is not None:
        #     return target_event.base_info["sdk_bot_info"]
    else:
        res = get_SDK_bot_info_from_Plugin_bot_info(target_event.bot_info)
    return res


class event(object):
    def __init__(self, payload_obj=None, bot_info=None):
        self.payload = payload_obj
        self.platform = {'sdk': 'dingtalk_link', 'platform': 'dingtalk', 'model': 'default'}
        self.active = False
        if self.payload is not None:
            self.active = True
        self.base_info = {}
        self.at_list = []
        if self.active:
            self.base_info['time'] = int(time.time())
            bot_info_this = get_SDK_bot_info_from_Plugin_bot_info(bot_info)
            self.base_info['self_id'] = bot_info_this.id
            # self.base_info['token'] = bot_info_this.access_token
            # self.base_info['expire'] = bot_info_this._expire_time
            self.base_info["sdk_bot_info"] = bot_info_this
            self.base_info['post_type'] = None
            # self.bot_info = bot_info


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
            self.recv_data_raw = {}
            self.headers = {}
            self.data = None
            self.messageId = None
            self.type = None
            self.topic = None


    def load(self, data, is_rx):
        if data is not None:
            if isinstance(data, dict):
                # self.data = data
                try:
                    if is_rx:
                        self.data.recv_data_raw = data
                        self.data.headers = data["headers"]
                        self.data.data = json.loads(data["data"])
                        self.data.messageId = data["headers"]["messageId"]
                        self.data.type = data["type"]
                        self.data.topic = data['headers']["topic"]
                except Exception:
                    self.active = False
            else:
                self.active = False
        return self

    def dump(self, res_code=None, message=None, data=None):
        res_obj = {
            "code": None,
            "headers": {
                "messageId": None,
                "contentType": "application/json"
            },
            "message": None,
            "data": None
        }
        res_obj['headers']['messageId'] = self.data.messageId
        if data is None:
            res_obj['data'] = json.dumps(self.data.data)
        else:
            res_obj['data'] = json.dumps(data)

        if res_code is not None and message is not None:
            res_obj['code'] = res_code
            res_obj["message"] = message
        elif self.active:
            res_obj['code'] = RESPONSE_STATUS_CODE.SUCCESS.value
            res_obj["message"] = "OK"
        else:
            res_obj['code'] = RESPONSE_STATUS_CODE.FAIL.value
            res_obj["message"] = "internal error"
        res = json.dumps(obj=res_obj)
        return res


class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, data):
            payload_template.__init__(self, data, True)

    class sendPong(payload_template):
        def __init__(self, packet: "PAYLOAD.rxPacket"):
            payload_template.__init__(self)
            self.active = packet.active
            if packet.data.messageId is not None:
                self.data.messageId = packet.data.messageId
            else:
                self.active = False
            if packet.data.data is not None:
                self.data.data = packet.data.data
            else:
                self.active = False
        def dump(self):
            return super().dump()

    class replyCallback(payload_template):
        def __init__(self, packet: "PAYLOAD.rxPacket"):
            payload_template.__init__(self)
            self.active = packet.active
            if packet.data.messageId is not None:
                self.data.messageId = packet.data.messageId
            else:
                self.active = False
            if packet.data.data is not None:
                self.data.data = packet.data.data
            else:
                self.active = False
    
        def dump(self):
            data = {"response": None}
            return super().dump(data=data)
        
    class replyEvent(payload_template):
        def __init__(self, packet: "PAYLOAD.rxPacket"):
            payload_template.__init__(self)
            self.active = packet.active
            if packet.data.messageId is not None:
                self.data.messageId = packet.data.messageId
            else:
                self.active = False
            if packet.data.data is not None:
                self.data.data = packet.data.data
            else:
                self.active = False
    
        def dump(self, flag_status=True, err_msg=""):
            data = {}
            if flag_status:
                data["status"] = "SUCCESS" 
                data["message"] = "success"
            else:
                data['status'] = "LATER"
                data['message'] = str(err_msg)
            return super().dump(data=data)
        


'''
对于POST接口的实现
'''


class api_templet(object):
    NO_DATA = object()      # 当需要传入 `None` 时，使用这个（直接传 None 代表使用默认配置）
    def __init__(self, bot_info: 'bot_info_T|None'=None):
        self.bot_info = bot_info
        self.data = None
        self.metadata = None
        self.host = None
        self.port = 443
        self.route = None
        self.res = None

    # @dataclasses.dataclass
    class data_T:
        def  __init__(self, *args, **kwargs):
            raise NotImplementedError()

    # @dataclasses.dataclass
    class metadata_T:
        def  __init__(self, *args, **kwargs):
            raise NotImplementedError()

    def do_api(self, req_type='POST', proxy=None):
        raise NotImplementedError()

    def set_data(self, data_obj=None, **kwargs):
        if data_obj is not None:
            self.data = data_obj
        else:
            self.data = self.data_T(**kwargs)

    def set_metadata(self, metadata_obj=None, **kwargs):
        if metadata_obj is not None:
            self.metadata = metadata_obj
        else:
            self.metadata = self.metadata_T(**kwargs)

    def _do_api(self, req_type, body=None, headers=None, *, flag_body_json=True, request_args=None):
        try:
            if headers is None:
                headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'x-acs-dingtalk-access-token': str(self.bot_info.access_token)      # 此时会自动更新 access_token
                }
            elif headers is self.NO_DATA:
                headers = None
            if body is None:
                body = {}
            elif body is self.NO_DATA:
                body = None
            if request_args is None:
                request_args = {}
            # tmp_payload_dict = body
            tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
            if self.metadata is not None:
                tmp_sdkAPIRouteTemp.update(self.metadata.__dict__)
            if flag_body_json:
                payload = json.dumps(obj=body)
            else:
                payload = body
            send_url_temp = self.host + self.route
            send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)

            msg_res = None
            if req_type == 'POST':
                msg_res = req.request("POST", send_url, headers=headers, data=payload,
                                      proxies=OlivOS.webTool.get_system_proxy(), **request_args)
            elif req_type == 'GET':
                msg_res = req.request("GET", send_url, headers=headers, proxies=OlivOS.webTool.get_system_proxy(), **request_args)

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger is not None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ' - sendding succeed: ' + msg_res.text)

            t = msg_res.text
            try:
                self.res = json.loads(t)
            except json.JSONDecodeError:
                self.res = t
            return self.res
        except:
            traceback.print_exc()
            return None


class API:
    class getGateway(api_templet):
        def __init__(self, bot_info: bot_info_T):
            """
                获取 websocket 连接的 ticket 和 endpoint
            """
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['gateway']
        
        def do_api(self, req_type='POST', proxy=None):
            body = {
                    "clientId" : None, 
                    "clientSecret" : None,
                    "subscriptions" : [
                        {
                        "type" : "EVENT",
                        "topic" : "*"
                        },
                        {
                        "type" : "CALLBACK",
                        "topic" : "/v1.0/im/bot/messages/get"
                        },
                        {
                        "type" : "SYSTEM",
                        "topic" : "ping"
                        },
                        {
                        "type" : "SYSTEM",
                        "topic" : "disconnect"
                        },
                    ],
                    "ua" : OlivOS.infoAPI.OlivOS_Header_UA,
                    # localIp : "0.0.0.0"                   # ip 为非必填项
                }
            body['clientId'] = self.bot_info.app_key
            body['clientSecret'] = self.bot_info.app_secret

            headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
            }
            return self._do_api(req_type, body, headers)

    class getAccessToken(api_templet):
        def __init__(self, bot_info: bot_info_T):
            """
                基于 app_key, app_secret 获取 api 的 access_token
            """
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['oauth'] + '/accessToken'

        def do_api(self, req_type='POST', proxy=None):
            headers = {
                    'Content-Type': 'application/json',
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    # 'x-acs-dingtalk-access-token': str(self.bot_info.access_token)
                }
            tmp_payload_dict = {}
            if self.bot_info is not None:
                tmp_payload_dict["appKey"] = self.bot_info.app_key
                tmp_payload_dict["appSecret"] = self.bot_info.app_secret
            return self._do_api("POST", tmp_payload_dict, headers)

    class uploadMedia(api_templet):
        def __init__(self, bot_info: bot_info_T):
            """
                上传各类媒体文件的实现
                `media` 为文件的二进制数据
                `mediaType` 为文件类型，如 `image`
                `contentType` 为文件的 MIME 类型，如 `image/png`
                `mediaName` 为文件名，如 `image.png`
            """
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['old'] + '/media/upload'

        @_init_kw_dataclass_safe()
        class data_T(object):
            media: bytes
            mediaType: str
            mediaName: typing.Optional[str] = None
            contentType: typing.Optional[str] = None


        def do_api(self, req_type='POST', proxy=None):
            if self.data is None:
                return None
            if self.data.contentType is None:
                file_mime = filetype.guess_mime(self.data.media)
                if file_meta is not None:
                    self.data.contentType = file_mime
                else:
                    self.data.contentType = 'application/octet-stream'
            if self.data.mediaName is None:
                file_ext = filetype.guess_extension(self.data.media)
                if file_ext is not None:
                    self.data.mediaName = str(uuid.uuid4()) + '.' + file_ext
                else:
                    self.data.mediaName = str(uuid.uuid4())

            # tmp_payload = MultipartEncoder(
            #     fields={
            #         "media": (self.data.mediaName, self.data.media, self.data.contentType),
            #         "type": self.data.mediaType
            #     }
            # )
            requset_args = {
                "params": {
                    "access_token": str(self.bot_info.access_token)
                },
                "files": {
                    "media": (self.data.mediaName, self.data.media, self.data.contentType)
                }
            }

            body = {"type": self.data.mediaType}
            return self._do_api(
                req_type="POST",
                body=body,
                headers=self.NO_DATA,
                flag_body_json=False,
                request_args=requset_args
            )         

    class getFileDownloadUrl(api_templet):
        def __init__(self, bot_info: bot_info_T):
            api_templet.__init__(self)
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.imagedata = []
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['bot'] + '/messageFiles/download'

        @_init_kw_dataclass_safe()
        class data_T(object):
            downloadCode: str
            robotCode: typing.Optional[str] = None

        def do_api(self, req_type='POST', proxy=None):
            if self.data is None:
                return None
            tmp_payload_dict = {}
            if self.data is not None:
                tmp_payload_dict["downloadCode"] = self.data.downloadCode
                if self.data.robotCode is not None:
                    tmp_payload_dict["robotCode"] = self.data.robotCode
                else:
                    tmp_payload_dict["robotCode"] = self.bot_info.id
            return self._do_api(
                req_type="POST",
                body=tmp_payload_dict,
            )

    class getUserInfo(api_templet):
        def __init__(self, bot_info: bot_info_T):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['old'] + '/topapi/v2/user/get'

        @_init_kw_dataclass_safe()
        class data_T(object):
            userid: str
            language: str = "zh_CN"

        def do_api(self, req_type='POST', proxy=None):
            if self.data is None:
                return None
            tmp_payload_dict = {}
            if self.data is not None:
                tmp_payload_dict["userid"] = self.data.userid
                tmp_payload_dict["language"] = self.data.language
            return self._do_api(
                req_type="POST",
                body=tmp_payload_dict
            )

    class sendGroupMessage(api_templet):
        def __init__(self, bot_info: bot_info_T):            
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.imagedata = []
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['bot'] + '/groupMessages/send'

        @_init_kw_dataclass_safe()
        class data_T(object):
            msgKey: str
            msgParam: dict
            openConversationId: typing.Optional[str] = None
            robotCode: typing.Optional[str] = None
            coolAppCode: typing.Optional[str] = None

            @property
            def str_msgParam(self):
                return json.dumps(self.msgParam)

        def do_api(self, req_type='POST', proxy=None):
            if self.data is None:
                return None
            tmp_payload_dict = {
                "msgKey" : self.data.msgKey,
                "msgParam" : self.data.str_msgParam
            }

            tmp_payload_dict["openConversationId"] = self.data.openConversationId
            if self.data.robotCode is not None:
                tmp_payload_dict["robotCode"] = self.data.robotCode
            elif self.data.coolAppCode is not None:
                tmp_payload_dict["coolAppCode"] = self.data.coolAppCode
            else:
                tmp_payload_dict["robotCode"] = self.bot_info.id
            
            return self._do_api(
                req_type="POST",
                body=tmp_payload_dict
            )

    class sendPrivateMessage(api_templet):
        def __init__(self, bot_info: bot_info_T):            
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.imagedata = []
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['bot'] + '/oToMessages/batchSend'

        @_init_kw_dataclass_safe()
        class data_T(object):
            msgKey: str
            msgParam: dict
            userIds: typing.List[str]
            robotCode: typing.Optional[str] = None

            @property
            def str_msgParam(self):
                return json.dumps(self.msgParam)

        def do_api(self, req_type='POST', proxy=None):
            if self.data is None:
                return None
            tmp_payload_dict = {
                "msgKey" : self.data.msgKey,
                "msgParam" : self.data.str_msgParam,
                "userIds" : self.data.userIds,
            }

            if self.data.robotCode is not None:
                tmp_payload_dict["robotCode"] = self.data.robotCode
            else:
                tmp_payload_dict["robotCode"] = self.bot_info.id
            
            return self._do_api(
                req_type="POST",
                body=tmp_payload_dict
            )

def checkInDictSafe(var_key, var_dict, var_path=None):
    if var_path is None:
        var_path = []
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


def checkEquelInDictSafe(var_it, var_dict, var_path=None):
    if var_path is None:
        var_path = []
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
    # OlivOS.bootAPI.logG(0, "get_Event_from_SDK")
    global sdkSubSelfInfo
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info['self_id'])
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'olivos_para'
    # plugin_event_bot_hash = OlivOS.API.getBotHash(
    #     bot_id=target_event.base_info['self_id'],
    #     platform_sdk=target_event.platform['sdk'],
    #     platform_platform=target_event.platform['platform'],
    #     platform_model=target_event.platform['model']
    # )
    # if plugin_event_bot_hash not in sdkSubSelfInfo:
        # tmp_bot_info = bot_info_T(
        #     target_event.sdk_event.base_info['self_id'],
        #     target_event.sdk_event.base_info['token']
        # )
        # api_msg_obj = API.getMe(tmp_bot_info)
        # try:
        #     api_msg_obj.do_api('GET')
        #     api_res_json = json.loads(api_msg_obj.res)
        #     sdkSubSelfInfo[plugin_event_bot_hash] = api_res_json['id']
        # except:
        #     pass
    if target_event.sdk_event.payload.data.type in [
        'CALLBACK',
    ]:
        data_raw = target_event.sdk_event.payload.data.data
        message_obj = None
        message_para_list = []

        if type(data_raw) == dict:
            self_id_encrypted = data_raw['chatbotUserId']
            tmp_at_list = []
            if 'atUsers' in data_raw:
                para_self_at = None
                for at_user_this in data_raw['atUsers']:
                    if "staffId" in at_user_this:
                        tmp_at_list.append(OlivOS.messageAPI.PARA.at(at_user_this["staffId"]))
                    elif at_user_this["dingtalkId"] == self_id_encrypted:
                        para_self_at = OlivOS.messageAPI.PARA.at(target_event.base_info['self_id'])
                        tmp_at_list.append(para_self_at)
                        message_para_list.append(para_self_at)
            target_event.sdk_event.at_list = tmp_at_list

            if data_raw["msgtype"] == "text":
                message_para_list.append(OlivOS.messageAPI.PARA.text(data_raw["text"]["content"]))
            elif data_raw["msgtype"] == "richText":
                tmp_str = []
                for para_this in data_raw["content"]["richText"]:
                    if "text" in para_this:
                        tmp_str.append(para_this["text"])
                    else:
                        message_para_list.append(OlivOS.messageAPI.PARA.text("\n".join(tmp_str)))
                        tmp_str = []
                        if "type" in para_this:
                            if para_this["type"] == "picture":
                                download_code = para_this["downloadCode"]
                                path = _download_file(target_event, download_code, ".png", "images")
                                message_para_list.append(OlivOS.messageAPI.PARA.image(path))
                if len(tmp_str) > 0:
                    message_para_list.append(OlivOS.messageAPI.PARA.text("\n".join(tmp_str)))
            elif data_raw["msgtype"] == "audio":
                download_code = data_raw["content"]["downloadCode"]
                path = _download_file(target_event, download_code, ".mp3", "audios")
                message_para_list.append(OlivOS.messageAPI.PARA.record(path))
            elif data_raw["msgtype"] == "picture":
                download_code = data_raw["content"]["downloadCode"]
                path = _download_file(target_event, download_code, ".png", "images")
                message_para_list.append(OlivOS.messageAPI.PARA.image(path))
            elif data_raw["msgtype"] == "video":
                download_code = data_raw["content"]["downloadCode"]
                videoType = data_raw["content"]["videoType"]
                path = _download_file(target_event, download_code, f".{videoType}", "videos")
                message_para_list.append(OlivOS.messageAPI.PARA.video(path))
            elif data_raw["msgtype"] == "file":
                # TODO: 文件接收事件，尚未实现
                pass
    
        message_obj = OlivOS.messageAPI.Message_templet(
            'olivos_para',
            message_para_list
        )        
        try:
            message_obj.init_data()
        except:
            traceback.print_exc()
            message_obj.active = False
            message_obj.data = []

        if message_obj.active:
            target_event.active = True
            if data_raw["conversationType"] == "1":
                if "senderStaffId" in data_raw:
                    sender_id = data_raw["senderStaffId"]
                else:
                    sender_id = data_raw["senderId"]
                target_event.data = target_event.private_message(
                    str(sender_id),
                    message_obj,
                    'private'
                )
                target_event.plugin_info['func_type'] = 'private_message'
                target_event.data.message_sdk = message_obj
                target_event.data.message_id = target_event.sdk_event.payload.data.messageId
                target_event.data.raw_message = message_obj
                target_event.data.raw_message_sdk = message_obj
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(sender_id)
                target_event.data.sender['nickname'] = data_raw['senderNick']
                target_event.data.sender['id'] = str(sender_id)
                target_event.data.sender['name'] = data_raw['senderNick']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0

            elif data_raw["conversationType"] == "2":
                target_event.plugin_info['func_type'] = 'group_message'
                if "senderStaffId" in data_raw:
                    sender_id = data_raw["senderStaffId"]
                else:
                    sender_id = data_raw["senderId"]
                target_event.data = target_event.group_message(
                    str(data_raw['conversationId']),
                    str(sender_id),
                    message_obj,
                    'group'
                )

                target_event.data.message_sdk = message_obj
                target_event.data.message_id = target_event.sdk_event.payload.data.messageId
                target_event.data.raw_message = message_obj
                target_event.data.raw_message_sdk = message_obj
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(sender_id)
                target_event.data.sender['nickname'] = data_raw['senderNick']
                target_event.data.sender['id'] = str(sender_id)
                target_event.data.sender['name'] = data_raw['senderNick']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0
                
                if "isAdmin" in data_raw:
                    if data_raw["isAdmin"]:
                        target_event.data.sender['role'] = 'admin'
                target_event.data.sender['role'] = 'member'

                target_event.data.host_id = None

    elif target_event.sdk_event.payload.data.type in [
            "EVENT"
        ]:
        # TODO: 事件订阅处理
        target_event.active = False
    else:
        # 其他未知事件
        target_event.active = False

# 支持OlivOS API调用的方法实现
class event_action(object):
    @staticmethod
    def send_msg(target_event, send_type: str, target_id: 'str', message: 'OlivOS.messageAPI.Message_templet'):
        for message_this in message.data:
            if message_this.type == 'text':
                res_this = message_this.OP()
                if send_type == 'group':
                    api_obj = API.sendGroupMessage(
                        get_SDK_bot_info_from_Event(target_event),
                    )
                    api_obj.set_data(
                        API.sendGroupMessage.data_T(
                            msgKey = "sampleText",
                            msgParam = {
                                "content": res_this
                            },
                            openConversationId = target_id
                        )
                    )
                    api_obj.do_api()
                elif send_type == "private":
                    api_obj = API.sendPrivateMessage(
                        get_SDK_bot_info_from_Event(target_event),
                    )
                    api_obj.set_data(
                        API.sendPrivateMessage.data_T(
                            msgKey = "sampleText",
                            msgParam = {
                                "content": res_this
                            },
                            userIds = [target_id]
                        )
                    )
                    api_obj.do_api()
            elif message_this.type == "image":
                code = _set_image_upload_fast(target_event, message_this.data["file"])
                if code is not None:
                    if send_type == "group":
                        api_obj = API.sendGroupMessage(
                            get_SDK_bot_info_from_Event(target_event),
                        )
                        api_obj.set_data(
                            API.sendGroupMessage.data_T(
                                msgKey = "sampleImageMsg",
                                msgParam = {
                                    "photoURL": code,
                                },
                                openConversationId = target_id
                            )
                        )
                        api_obj.do_api()
                    elif send_type == "private":
                        api_obj = API.sendPrivateMessage(
                            get_SDK_bot_info_from_Event(target_event),
                        )
                        api_obj.set_data(
                            API.sendPrivateMessage.data_T(
                                msgKey = "sampleImageMsg",
                                msgParam = {
                                    "photoURL": code,
                                },
                                userIds = [target_id]
                            )
                        )
                        api_obj.do_api()

            # TODO: 发送语音、视频信息
            # 由于这些信息需要获取对应文件的时长信息，需要额外怎加依赖项，所以暂时不实现
            # if message_this.type == "video":
            #     code = _set_image_upload_fast(target_event, message_this.data["file"])
            #     if code is not None:
            #         api_obj = API.sendGroupMessage(
            #             get_SDK_bot_info_from_Event(target_event),
            #         )
            #         api_obj.set_data(
            #             API.sendGroupMessage.data_T(
            #                 msgKey = "sampleVideo",
            #                 msgParam = {
            #                     "mediaId": code
            #                 },
            #                 openConversationId = target_id
            #             )
            #         )
            #         api_obj.do_api()


"""
    以下为  DingTalk SDK 的内部实现函数，不建议直接调用
"""
def _get_file_url(target_event, downloadCode):
    """
        基于 downloadCode 获取文件下载地址
    """

    res = None
    try:
        msg_api = API.getFileDownloadUrl(get_SDK_bot_info_from_Event(target_event))
        msg_api.set_data(
            msg_api.data_T(
                downloadCode=downloadCode
            )
        )
        msg_api.do_api()
        if msg_api.res is not None:
            msg_api_obj = msg_api.res
            res = msg_api_obj['downloadUrl']
    except:
        traceback.print_exc()
        res = None
    return res

def _download_file(target_event, downloadCode, file_ext=".png", file_type="images"):
    """
        基于 downloadCode 下载到本地临时目录
        file_ext 为 文件扩展名
        file_type 为 文件类型  (images, audios, videos)
    """
    try:
        url = _get_file_url(target_event, downloadCode)
        if url is None:
            return
        req_obj = req.request("GET", url, proxies=OlivOS.webTool.get_system_proxy())
        if req_obj.status_code == 200:

            file_path = OlivOS.contentAPI.resourcePathTransform(
                file_type,
                f"cache-dingtalk-{uuid.uuid4().hex}{file_ext}"     # 临时文件名称以 cache-dingtalk- 开头，便于后续清理
            )
            # file_path = f"./data/{file_type}/
            with open(file_path, "wb") as f:
                f.write(req_obj.content)
            return file_path
    except:
        traceback.print_exc()
        pass
    return None

def _set_image_upload_fast(target_event, url: str):
    """
        基于uri上传图片并返回 media_id
    """
    res = None

    try:
        pic_file = None
        pic_mime = None
        pic_ext = None
        if url.startswith("base64://"):
            data = url[9:]
            pic_file = base64.decodebytes(data.encode("utf-8"))
        else:
            url_parsed = parse.urlparse(url)
            # pic_type = mimetypes.guess_type(url)[0]
            # if pic_type is not None:
            #     pic_ext = mimetypes.guess_extension(pic_type)
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
                file_path = OlivOS.contentAPI.resourcePathTransform('images', file_path)
                with open(file_path, "rb") as f:
                    pic_file = f.read()

        pic_meta = filetype.guess(pic_file)
        if pic_meta is not None:
            pic_mime = pic_meta.mime
            pic_ext = pic_meta.extension
        else:
            pic_mime = 'image/png'
            pic_ext = 'png'

        msg_upload_api = API.uploadMedia(get_SDK_bot_info_from_Event(target_event))
        msg_upload_api.set_data(
            msg_upload_api.data_T(
                media=pic_file,
                mediaType='image',
                contentType=pic_mime,
                mediaName=uuid.uuid4().hex + '.' + pic_ext
            )
        )
        msg_upload_api.do_api()
        if msg_upload_api.res is not None:
            msg_upload_api_obj = msg_upload_api.res
            if msg_upload_api_obj['errcode'] == 0:
                res = msg_upload_api_obj['media_id']
    except:
        traceback.print_exc()
        res = None
    return res

def _get_user_mobile(target_event, user_id: str):
    """
        基于 user_id 获取用户手机号
        用于 at 字段的实现
        目前只有基于 webhook 版本的消息发送才支持 at 字段
        而 webhook 的消息发送，当前 SDK 版本不支持
    """
    res = None
    try:
        msg_api = API.getUserInfo(get_SDK_bot_info_from_Event(target_event))
        msg_api.set_data(
            msg_api.data_T(
                userid=user_id
            )
        )
        msg_api.do_api()
        if msg_api.res is not None:
            msg_api_obj = json.loads(msg_api.res)
            if msg_api_obj['errcode'] == 0:
                if "result" in msg_api_obj and "mobile" in msg_api_obj["result"]:
                    res = msg_api_obj['result']['mobile']
    except:
        res = None
    return res


