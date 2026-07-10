# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqGuildv2SDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

from enum import IntEnum
import json
import mimetypes
import os
import requests as req
import time
from datetime import datetime, timezone
import traceback
import re
from requests_toolbelt import MultipartEncoder
import uuid
import base64
from urllib import parse

import OlivOS

modelName = 'qqGuildv2SDK'


class intents_T(IntEnum):
    GUILDS = (1 << 0)  # 频道变更
    GUILD_MEMBERS = (1 << 1)  # 频道成员变更
    GUILD_MESSAGES = (1 << 9)  # 消息事件，仅 *私域* 机器人能够设置此 intents。
    GUILD_MESSAGE_REACTIONS = (1 << 10)  # 戳表情
    DIRECT_MESSAGE = (1 << 12)  # 私聊消息
    INTERACTION = (1 << 26)  # 互动事件变更
    MESSAGE_AUDIT = (1 << 27)  # 消息审核变更
    FORUMS_EVENT = (1 << 28)  # 论坛事件，仅 *私域* 机器人能够设置此 intents。
    AUDIO_ACTION = (1 << 29)  # 语音消息
    PUBLIC_GUILD_MESSAGES = (1 << 30)  # 消息事件，此为公域的消息事件
    PUBLIC_QQ_MESSAGES = (1 << 25)  # 消息事件，此为公域的普通QQ消息事件


sdkAPIHost = {
    'default': 'https://api.sgroup.qq.com',
    'sandbox': 'https://sandbox.api.sgroup.qq.com',
    'bots': 'https://bots.qq.com'
}

sdkAPIRoute = {
    'guilds': '/guilds',
    'channels': '/channels',
    'dms': '/dms',
    'users': '/users',
    'gateway': '/gateway',
    'qq_users': '/v2/users',
    'qq_groups': '/v2/groups',
    'getAppAccessToken': '/app/getAppAccessToken'
}

sdkAPIRouteTemp = {
    'guild_id': '-1',
    'channel_id': '-1',
    'user_id': '-1',
    'openid': '-1',
    'group_openid': '-1',
    'message_id': '-1'
}

sdkSubSelfInfo = {}
sdkTokenInfo = {}
sdkMsgidinfo = {}
sdkSelfInfo = {}


class bot_info_T(object):
    def __init__(self, id=-1, access_token=None, model='private', intents=0):
        self.id = id
        self.access_token = access_token
        self.model = model
        self.intents = intents
        self.debug_mode = False
        self.debug_logger = None


def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(
        id=plugin_bot_info.id,
        access_token=plugin_bot_info.post_info.access_token,
        model=plugin_bot_info.platform.get('model', 'private'),
        intents=plugin_bot_info.post_info.port
    )
    res.debug_mode = plugin_bot_info.debug_mode
    return res


def get_SDK_bot_info_from_Event(target_event):
    res = get_SDK_bot_info_from_Plugin_bot_info(target_event.bot_info)
    return res


class event(object):
    def __init__(self, payload_obj=None, bot_info=None):
        self.payload = payload_obj
        self.platform = {'sdk': 'qqGuildv2_link', 'platform': 'qqGuild', 'model': 'default'}
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
            self.op = None
            self.d = None
            self.s = None
            self.t = None

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
                if 'op' in data:
                    if type(data['op']) is int:
                        self.data.op = data['op']
                    else:
                        self.active = False
                else:
                    self.active = False
                if 'd' in data:
                    self.data.d = data['d']
                if 's' in data:
                    if type(data['s']) is int:
                        self.data.s = data['s']
                    else:
                        self.active = False
                if 't' in data:
                    if type(data['t']) is str:
                        self.data.t = data['t']
                    else:
                        self.active = False
                elif is_rx:
                    self.active = False
            else:
                self.active = False
        return self


class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, data):
            payload_template.__init__(self, data, True)

    class sendIdentify(payload_template):
        def __init__(self, bot_info: bot_info_T, intents=(int(intents_T.GUILDS) | int(intents_T.DIRECT_MESSAGE))):
            tmp_intents = intents
            if bot_info.model in ['private']:
                tmp_intents |= int(intents_T.GUILD_MESSAGES)
                # tmp_intents |= int(intents_T.QQ_MESSAGES)
            elif bot_info.model in ['public', 'sandbox']:
                tmp_intents |= int(intents_T.PUBLIC_GUILD_MESSAGES)
                tmp_intents |= int(intents_T.PUBLIC_QQ_MESSAGES)
            elif bot_info.model in ['public_guild_only']:
                tmp_intents |= int(intents_T.PUBLIC_GUILD_MESSAGES)
            elif bot_info.model in ['private_intents', 'public_intents', 'sandbox_intents']:
                tmp_intents = bot_info.intents
            payload_template.__init__(self)
            self.data.op = 2
            try:
                self.data.d = {
                    'token': 'QQBot %s' % (getTokenNow(bot_info)),
                    'intents': tmp_intents,
                    'shard': [0, 1],
                    'properties': {
                        'os': OlivOS.infoAPI.OlivOS_Header_UA
                    }
                }
            except Exception:
                self.active = False

    class sendHeartbeat(payload_template):
        def __init__(self, last_s=None):
            payload_template.__init__(self)
            self.data.op = 1
            self.data.s = last_s

        def dump(self):
            res_obj = {}
            for data_this in self.data.__dict__:
                if self.data.__dict__[data_this] is not None or data_this == 's':
                    res_obj[data_this] = self.data.__dict__[data_this]
            res = json.dumps(obj=res_obj)
            return res


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

    def __switch_host(self):
        if self.bot_info.model in ['sandbox', 'sandbox_intents']:
            if self.host == sdkAPIHost['default']:
                self.host = sdkAPIHost['sandbox']

    def do_api_plant(self, req_type='POST'):
        try:
            self.__switch_host()
            tmp_payload_dict = {}
            tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
            if self.metadata is not None:
                tmp_sdkAPIRouteTemp.update(self.metadata.__dict__)
            if self.data is not None:
                for data_this in self.data.__dict__:
                    if self.data.__dict__[data_this] is not None:
                        tmp_payload_dict[data_this] = self.data.__dict__[data_this]

            payload = json.dumps(obj=tmp_payload_dict)
            send_url_temp = self.host + ':' + str(self.port) + self.route
            send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA
            }

            msg_res = None
            if req_type == 'POST':
                msg_res = req.request("POST", send_url, headers=headers, data=payload)
            elif req_type == 'GET':
                msg_res = req.request("GET", send_url, headers=headers)

            self.res = msg_res.text
            return msg_res.text
        except Exception:
            return None

    def do_api(self, req_type='POST'):
        try:
            self.__switch_host()
            tmp_payload_dict = {}
            tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
            if self.metadata is not None:
                tmp_sdkAPIRouteTemp.update(self.metadata.__dict__)
            if self.data is not None:
                for data_this in self.data.__dict__:
                    if self.data.__dict__[data_this] is not None:
                        tmp_payload_dict[data_this] = self.data.__dict__[data_this]

            payload = json.dumps(obj=tmp_payload_dict)
            # print(payload)
            send_url_temp = self.host + ':' + str(self.port) + self.route
            send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                'Authorization': 'QQBot %s' % (getTokenNow(self.bot_info)),
                'X-Union-Appid': str(self.bot_info.id)
            }

            msg_res = None
            if req_type == 'POST':
                msg_res = req.request("POST", send_url, headers=headers, data=payload)
            elif req_type == 'GET':
                msg_res = req.request("GET", send_url, headers=headers)
            elif req_type == 'DELETE':
                msg_res = req.request("DELETE", send_url, headers=headers)

            self.res = msg_res.text
            # print(self.res)
            return msg_res.text
        except Exception:
            traceback.print_exc()
            return None


def getTokenNow(bot_info: bot_info_T):
    access_token = None
    plugin_event_bot_hash = OlivOS.API.getBotHash(
        bot_id=bot_info.id,
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='default'
    )
    tmpInfo = sdkTokenInfo.get(plugin_event_bot_hash, [None, -1])
    tmpTime = int(datetime.now(timezone.utc).timestamp())
    if (
        tmpInfo[0] is not None
        and tmpInfo[1] > tmpTime
    ):
        access_token = sdkTokenInfo[plugin_event_bot_hash][0]
    else:
        msg_this = API.getAppAccessToken(bot_info)
        msg_this.data.clientSecret = bot_info.access_token
        msg_this.data.appId = str(bot_info.id)
        msg_this.do_api_plant()
        if msg_this.res is not None:
            raw_obj = init_api_json(msg_this.res)
            sdkTokenInfo[plugin_event_bot_hash] = [
                raw_obj.get('access_token', None),
                tmpTime + int(raw_obj.get('expires_in', -1))
            ]
            access_token = sdkTokenInfo[plugin_event_bot_hash][0]
            try:
                tmp_Proc = None
                if OlivOS.bootAPI.gLoggerProc is not None:
                    tmp_Proc = OlivOS.bootAPI.gLoggerProc
                if OlivOS.pluginAPI.gProc is not None:
                    tmp_Proc = OlivOS.pluginAPI.gProc
                if tmp_Proc is not None:
                    tmp_Proc.log(
                        2,
                        OlivOS.L10NAPI.getTrans(
                            'OlivOS qqGuildv2SDK bot [{0}] refresh TOKEN [{1}]',
                            [plugin_event_bot_hash, access_token],
                            modelName
                        )
                    )
            except Exception:
                traceback.print_exc()
    return access_token


class API(object):
    class getAppAccessToken(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['bots']
            self.route = sdkAPIRoute['getAppAccessToken']

        class data_T(object):
            def __init__(self):
                self.appId = None
                self.clientSecret = None

    class getGateway(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['gateway']

    class getMe(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['users'] + '/@me'

    class sendMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/messages'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.content = None  # str
                self.embed = None  # object
                self.ark = None  # object
                self.message_reference = None  # object
                self.image = None  # str
                self.file_image = None  # multipart file
                self.msg_id = None  # str
                self.event_id = None  # str
                self.markdown = None  # object
                self.keyboard = None  # object

        # 频道本地图片使用 multipart/form-data，其他消息沿用通用 JSON 请求
        def do_api(self, req_type='POST'):
            if self.data.file_image is None:
                return api_templet.do_api(self, req_type)
            try:
                if self.bot_info.model in ['sandbox', 'sandbox_intents']:
                    if self.host == sdkAPIHost['default']:
                        self.host = sdkAPIHost['sandbox']
                tmp_payload_dict = {}
                tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
                tmp_sdkAPIRouteTemp.update(self.metadata.__dict__)
                for data_this in self.data.__dict__:
                    if data_this != 'file_image' and self.data.__dict__[data_this] is not None:
                        data_value = self.data.__dict__[data_this]
                        if type(data_value) in [dict, list]:
                            data_value = json.dumps(obj=data_value)
                        elif type(data_value) is bool:
                            data_value = str(data_value).lower()
                        else:
                            data_value = str(data_value)
                        tmp_payload_dict[data_this] = data_value
                tmp_payload_dict['file_image'] = self.data.file_image
                payload = MultipartEncoder(fields=tmp_payload_dict)
                send_url_temp = self.host + ':' + str(self.port) + self.route
                send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
                headers = {
                    'Content-Type': payload.content_type,
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'Authorization': 'QQBot %s' % (getTokenNow(self.bot_info)),
                    'X-Union-Appid': str(self.bot_info.id)
                }
                msg_res = None
                if req_type == 'POST':
                    msg_res = req.request("POST", send_url, headers=headers, data=payload)
                self.res = msg_res.text
                return msg_res.text
            except Exception:
                traceback.print_exc()
                return None

    class sendDirectMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['dms'] + '/{guild_id}/messages'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.content = None     # str
                self.embed = None       # object
                self.ark = None         # object
                self.message_reference = None  # object
                self.image = None       # str
                self.file_image = None  # multipart file
                self.msg_id = None      # str
                self.event_id = None    # str
                self.markdown = None    # object
                self.keyboard = None    # object

        # 频道私信本地图片使用 multipart/form-data，其他消息沿用通用 JSON 请求
        def do_api(self, req_type='POST'):
            if self.data.file_image is None:
                return api_templet.do_api(self, req_type)
            try:
                if self.bot_info.model in ['sandbox', 'sandbox_intents']:
                    if self.host == sdkAPIHost['default']:
                        self.host = sdkAPIHost['sandbox']
                tmp_payload_dict = {}
                tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
                tmp_sdkAPIRouteTemp.update(self.metadata.__dict__)
                for data_this in self.data.__dict__:
                    if data_this != 'file_image' and self.data.__dict__[data_this] is not None:
                        data_value = self.data.__dict__[data_this]
                        if type(data_value) in [dict, list]:
                            data_value = json.dumps(obj=data_value)
                        elif type(data_value) is bool:
                            data_value = str(data_value).lower()
                        else:
                            data_value = str(data_value)
                        tmp_payload_dict[data_this] = data_value
                tmp_payload_dict['file_image'] = self.data.file_image
                payload = MultipartEncoder(fields=tmp_payload_dict)
                send_url_temp = self.host + ':' + str(self.port) + self.route
                send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
                headers = {
                    'Content-Type': payload.content_type,
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'Authorization': 'QQBot %s' % (getTokenNow(self.bot_info)),
                    'X-Union-Appid': str(self.bot_info.id)
                }
                msg_res = None
                if req_type == 'POST':
                    msg_res = req.request("POST", send_url, headers=headers, data=payload)
                self.res = msg_res.text
                return msg_res.text
            except Exception:
                traceback.print_exc()
                return None

    class sendQQMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/messages'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

        class data_T(object):
            def __init__(self):
                self.content = None     # str
                self.media = None       # object
                self.msg_type = 0       # int
                self.markdown = None    # object
                self.keyboard = None    # object
                self.ark = None         # object
                self.embed = None       # object
                self.message_reference = None  # object
                self.event_id = None    # str
                self.msg_id = None      # str
                self.msg_seq = None

    class sendQQDirectMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_users'] + '/{openid}/messages'

        class metadata_T(object):
            def __init__(self):
                self.openid = '-1'

        class data_T(object):
            def __init__(self):
                self.content = None     # str
                self.msg_type = 0       # int
                self.markdown = None    # object
                self.keyboard = None    # object
                self.ark = None         # object
                self.embed = None       # object
                self.media = None       # object
                self.message_reference = None  # object
                self.event_id = None    # str
                self.msg_id = None      # str
                self.msg_seq = None
                self.is_wakeup = None   # bool

    # QQ 单聊/群聊富媒体上传。名称保留以兼容已有内部引用，实际支持图片、视频、语音和文件。
    class setResourcePictureUpload(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{openid}/files'
            self.resource_type = 'qq_groups'

        class data_T(object):
            def __init__(self):
                self.file_type = None  # 1 图片、2 视频、3 语音、4 文件
                self.url = None        # 远程资源 URL
                self.file_data = None  # 本地资源的 base64 数据

        class metadata_T(object):
            def __init__(self):
                self.openid = '-1'

        def do_api(self, req_type='POST'):
            # 官方富媒体接口使用 JSON：远程资源传 url，本地资源传 base64 file_data。
            self.route = sdkAPIRoute[self.resource_type] + '/{openid}/files'
            return api_templet.do_api(self, req_type)

    class deleteMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/messages/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'

    class deleteDirectMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['dms'] + '/{guild_id}/messages/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.message_id = '-1'

    class deleteQQMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/messages/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'
                self.message_id = '-1'

    class deleteQQDirectMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_users'] + '/{openid}/messages/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.openid = '-1'
                self.message_id = '-1'


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


# 将 QQ 事件中的附件地址规范化为 OlivOS 可直接使用的 URL
def _get_attachment_url(attachment):
    attachment_url = attachment.get('url', None)
    if type(attachment_url) is not str or attachment_url == '':
        attachment_url = attachment.get('voice_wav_url', None)
    if type(attachment_url) is not str or attachment_url == '':
        return None
    if attachment_url.startswith('http://') or attachment_url.startswith('https://'):
        return attachment_url
    if attachment_url.startswith('//'):
        return 'https:' + attachment_url
    return 'https://' + attachment_url.lstrip('/')


# 按事件文档把图片、视频、语音和文件附件转换为统一消息段
def _get_message_attachments(attachments):
    message_list = []
    if type(attachments) is not list:
        return message_list
    for attachment_this in attachments:
        if type(attachment_this) is not dict:
            continue
        attachment_url = _get_attachment_url(attachment_this)
        if attachment_url is None:
            continue
        content_type = str(attachment_this.get('content_type', '')).lower()
        if content_type.startswith('image'):
            message_list.append(
                OlivOS.messageAPI.PARA.image(file=attachment_url, url=attachment_url)
            )
        elif content_type.startswith('video'):
            message_list.append(
                OlivOS.messageAPI.PARA.video(file=attachment_url, url=attachment_url)
            )
        elif content_type == 'voice' or content_type.startswith('audio'):
            message_list.append(
                OlivOS.messageAPI.PARA.record(file=attachment_url, url=attachment_url)
            )
        else:
            message_list.append(
                OlivOS.messageAPI.PARA.file(
                    file=attachment_url,
                    url=attachment_url,
                    name=attachment_this.get('filename', None),
                    size=attachment_this.get('size', None)
                )
            )
    return message_list


def get_Event_from_SDK(target_event):
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
            sdkSubSelfInfo[plugin_event_bot_hash] = api_res_json['id']
        except Exception:
            traceback.print_exc()
        if (
            plugin_event_bot_hash in sdkSelfInfo
            and type(sdkSelfInfo[plugin_event_bot_hash]) is dict
            and 'id' in sdkSelfInfo[plugin_event_bot_hash]
            and 'username' in sdkSelfInfo[plugin_event_bot_hash]
        ):
            sdkSubSelfInfo[plugin_event_bot_hash] = str(sdkSelfInfo[plugin_event_bot_hash]['id'])
    if target_event.sdk_event.payload.data.t == 'READY':
        target_event.active = False
        if (
            type(target_event.sdk_event.payload.data.d) is dict
            and 'user' in target_event.sdk_event.payload.data.d
            and type(target_event.sdk_event.payload.data.d['user']) is dict
        ):
            sdkSelfInfo[plugin_event_bot_hash] = target_event.sdk_event.payload.data.d['user']
    elif target_event.sdk_event.payload.data.t in [
        'GROUP_AT_MESSAGE_CREATE',
        'GROUP_MESSAGE_CREATE'
    ]:
        message_obj = None
        if 'content' in target_event.sdk_event.payload.data.d:
            if target_event.sdk_event.payload.data.d['content'] != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuild_string',
                    target_event.sdk_event.payload.data.d['content'].lstrip(' ')
                )
                message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                message_obj.data_raw = message_obj.data.copy()
            else:
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_para',
                    []
                )
        else:
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                []
            )
        message_obj.data_raw.extend(
            _get_message_attachments(
                target_event.sdk_event.payload.data.d.get('attachments', None)
            )
        )
        try:
            message_obj.init_data()
        except Exception:
            message_obj.active = False
            message_obj.data = []
        if message_obj.active:
            # QQ 新版事件使用 group_openid/member_openid，保留旧字段作为兼容回退。
            group_openid = target_event.sdk_event.payload.data.d.get(
                'group_openid',
                target_event.sdk_event.payload.data.d.get('group_id', None)
            )
            member_openid = target_event.sdk_event.payload.data.d['author'].get(
                'member_openid',
                target_event.sdk_event.payload.data.d['author'].get('id', None)
            )
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message'
            target_event.data = target_event.group_message(
                str(group_openid),
                str(member_openid),
                message_obj,
                'group'
            )
            target_event.data.message_sdk = message_obj
            target_event.data.message_id = target_event.sdk_event.payload.data.d['id']
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = str(member_openid)
            target_event.data.sender['nickname'] = '用户'
            target_event.data.sender['id'] = target_event.data.sender['user_id']
            target_event.data.sender['name'] = target_event.data.sender['nickname']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.sender['role'] = 'member'
            target_event.data.host_id = None
            target_event.data.extend['group_id'] = str(group_openid)
            target_event.data.extend['host_group_id'] = None
            target_event.data.extend['flag_from_direct'] = False
            target_event.data.extend['flag_from_qq'] = True
            target_event.data.extend['reply_msg_id'] = target_event.sdk_event.payload.data.d['id']
            if 'member' in target_event.sdk_event.payload.data.d:
                if 'roles' in target_event.sdk_event.payload.data.d['member']:
                    tmp_role_now = target_event.sdk_event.payload.data.d['member']['roles']
                    if '4' in tmp_role_now:
                        target_event.data.sender['role'] = 'owner'
                    elif '5' in tmp_role_now:
                        target_event.data.sender['role'] = 'sub_admin'
                    elif '2' in tmp_role_now:
                        target_event.data.sender['role'] = 'admin'
                    elif '1' in tmp_role_now:
                        target_event.data.sender['role'] = 'member'
            member_role = target_event.sdk_event.payload.data.d['author'].get('member_role', None)
            if member_role == 'owner':
                target_event.data.sender['role'] = 'owner'
            elif member_role == 'admin':
                target_event.data.sender['role'] = 'admin'
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
    elif target_event.sdk_event.payload.data.t == 'C2C_MESSAGE_CREATE':
        message_obj = None
        if 'content' in target_event.sdk_event.payload.data.d:
            if target_event.sdk_event.payload.data.d['content'] != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuild_string',
                    target_event.sdk_event.payload.data.d['content'].lstrip(' ')
                )
                message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                message_obj.data_raw = message_obj.data.copy()
            else:
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_para',
                    []
                )
        else:
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                []
            )
        message_obj.data_raw.extend(
            _get_message_attachments(
                target_event.sdk_event.payload.data.d.get('attachments', None)
            )
        )
        try:
            message_obj.init_data()
        except Exception:
            message_obj.active = False
            message_obj.data = []
        if message_obj.active:
            # C2C 新版事件的用户标识为 author.user_openid。
            user_openid = target_event.sdk_event.payload.data.d['author'].get(
                'user_openid',
                target_event.sdk_event.payload.data.d['author'].get('id', None)
            )
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message'
            target_event.data = target_event.private_message(
                str(user_openid),
                message_obj,
                'friend'
            )
            target_event.data.message_sdk = message_obj
            target_event.data.message_id = str(target_event.sdk_event.payload.data.d['id'])
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = str(user_openid)
            target_event.data.sender['nickname'] = '用户'
            target_event.data.sender['id'] = target_event.data.sender['user_id']
            target_event.data.sender['name'] = target_event.data.sender['nickname']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.extend['flag_from_direct'] = True
            target_event.data.extend['flag_from_qq'] = True
            target_event.data.extend['reply_msg_id'] = target_event.sdk_event.payload.data.d['id']
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
    elif target_event.sdk_event.payload.data.t in [
        'MESSAGE_CREATE',
        'AT_MESSAGE_CREATE'
    ]:
        message_obj = None
        if 'content' in target_event.sdk_event.payload.data.d:
            if target_event.sdk_event.payload.data.t == 'AT_MESSAGE_CREATE':
                # 针对某些无法调用 /users/@me 接口的机器人的临时解决方案
                target_event.sdk_event.payload.data.d['content'] = re.sub(
                    r'^<@!\d+>', r'',
                    target_event.sdk_event.payload.data.d['content']
                )
            if target_event.sdk_event.payload.data.d['content'] != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuild_string',
                    target_event.sdk_event.payload.data.d['content'].lstrip(' ')
                )
                message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                message_obj.data_raw = message_obj.data.copy()
            else:
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_para',
                    []
                )
        else:
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                []
            )
        message_obj.data_raw.extend(
            _get_message_attachments(
                target_event.sdk_event.payload.data.d.get('attachments', None)
            )
        )
        try:
            message_obj.init_data()
        except Exception:
            message_obj.active = False
            message_obj.data = []
        if message_obj.active:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message'
            target_event.data = target_event.group_message(
                str(target_event.sdk_event.payload.data.d['channel_id']),
                str(target_event.sdk_event.payload.data.d['author']['id']),
                message_obj,
                'group'
            )
            target_event.data.message_sdk = message_obj
            target_event.data.message_id = target_event.sdk_event.payload.data.d['id']
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.data.d['author']['id'])
            target_event.data.sender['nickname'] = target_event.sdk_event.payload.data.d['author']['username']
            target_event.data.sender['id'] = str(target_event.sdk_event.payload.data.d['author']['id'])
            target_event.data.sender['name'] = target_event.sdk_event.payload.data.d['author']['username']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.sender['role'] = 'member'
            target_event.data.host_id = target_event.sdk_event.payload.data.d['guild_id']
            target_event.data.extend['group_id'] = str(target_event.sdk_event.payload.data.d['channel_id'])
            target_event.data.extend['host_group_id'] = str(target_event.sdk_event.payload.data.d['guild_id'])
            target_event.data.extend['flag_from_direct'] = False
            target_event.data.extend['reply_msg_id'] = target_event.sdk_event.payload.data.d['id']
            if 'member' in target_event.sdk_event.payload.data.d:
                if 'roles' in target_event.sdk_event.payload.data.d['member']:
                    tmp_role_now = target_event.sdk_event.payload.data.d['member']['roles']
                    if '4' in tmp_role_now:
                        target_event.data.sender['role'] = 'owner'
                    elif '5' in tmp_role_now:
                        target_event.data.sender['role'] = 'sub_admin'
                    elif '2' in tmp_role_now:
                        target_event.data.sender['role'] = 'admin'
                    elif '1' in tmp_role_now:
                        target_event.data.sender['role'] = 'member'
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
    elif target_event.sdk_event.payload.data.t == 'DIRECT_MESSAGE_CREATE':
        message_obj = None
        if 'content' in target_event.sdk_event.payload.data.d:
            if target_event.sdk_event.payload.data.d['content'] != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuild_string',
                    target_event.sdk_event.payload.data.d['content'].lstrip(' ')
                )
                message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                message_obj.data_raw = message_obj.data.copy()
            else:
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_para',
                    []
                )
        else:
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                []
            )
        message_obj.data_raw.extend(
            _get_message_attachments(
                target_event.sdk_event.payload.data.d.get('attachments', None)
            )
        )
        try:
            message_obj.init_data()
        except Exception:
            message_obj.active = False
            message_obj.data = []
        if message_obj.active:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message'
            target_event.data = target_event.private_message(
                str(target_event.sdk_event.payload.data.d['author']['id']),
                message_obj,
                'friend'
            )
            target_event.data.message_sdk = message_obj
            target_event.data.message_id = str(target_event.sdk_event.payload.data.d['id'])
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.data.d['author']['id'])
            target_event.data.sender['nickname'] = target_event.sdk_event.payload.data.d['author']['username']
            target_event.data.sender['id'] = str(target_event.sdk_event.payload.data.d['author']['id'])
            target_event.data.sender['name'] = target_event.sdk_event.payload.data.d['author']['username']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.extend['group_id'] = str(target_event.sdk_event.payload.data.d['channel_id'])
            target_event.data.extend['host_group_id'] = str(target_event.sdk_event.payload.data.d['guild_id'])
            target_event.data.extend['flag_from_direct'] = True
            target_event.data.extend['reply_msg_id'] = target_event.sdk_event.payload.data.d['id']
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])


# 支持OlivOS API调用的方法实现
class event_action(object):
    # 按首个有效消息段确定图文方向，并将每个富媒体与相邻文字分组
    def _get_message_send_chunks(message, media_types):
        message_items = []
        for message_this in message.data:
            if type(message_this) is OlivOS.messageAPI.PARA.text:
                text_content = message_this.OP()
                # 空文字段不应改变整条消息按图片开头还是按文字开头分组。
                if text_content != '':
                    message_items.append(('text', text_content))
            elif type(message_this) in media_types:
                message_items.append(('media', message_this))

        if len(message_items) == 0:
            return []

        message_chunks = []
        text_buffer = ''
        media_buffer = None
        if message_items[0][0] == 'media':
            # 图片开头时，后续文字归属前一张图片：图片1-文字1-图片2-文字2。
            for item_type, item_data in message_items:
                if item_type == 'text':
                    text_buffer += item_data
                else:
                    if media_buffer is not None:
                        message_chunks.append((text_buffer, media_buffer))
                        text_buffer = ''
                    media_buffer = item_data
            if media_buffer is not None:
                message_chunks.append((text_buffer, media_buffer))
        else:
            # 文字开头时，前置文字归属后一张图片：文字1-图片1-文字2-图片2。
            for item_type, item_data in message_items:
                if item_type == 'text':
                    text_buffer += item_data
                else:
                    message_chunks.append((text_buffer, item_data))
                    text_buffer = ''
            if text_buffer != '':
                message_chunks.append((text_buffer, None))
        return message_chunks

    def send_qq_msg(target_event, chat_id, message, reply_msg_id=None, flag_direct=False):
        msg_id = reply_msg_id
        if msg_id is None and type(target_event.sdk_event) is event:
            msg_id = target_event.sdk_event.payload.data.d.get('id', None)

        media_types = [
            OlivOS.messageAPI.PARA.image,
            OlivOS.messageAPI.PARA.video,
            OlivOS.messageAPI.PARA.record,
            OlivOS.messageAPI.PARA.file
        ]
        failed_text_buffer = ''
        for text_content, message_this in event_action._get_message_send_chunks(message, media_types):
            text_content = failed_text_buffer + text_content
            if message_this is None:
                event_action._send_qq_payload(
                    target_event,
                    chat_id,
                    text_content,
                    msg_id,
                    flag_direct=flag_direct
                )
                failed_text_buffer = ''
                continue
            if type(message_this) is OlivOS.messageAPI.PARA.image:
                type_path = 'images'
            elif type(message_this) is OlivOS.messageAPI.PARA.video:
                type_path = 'videos'
            elif type(message_this) is OlivOS.messageAPI.PARA.record:
                type_path = 'audios'
            elif type(message_this) is OlivOS.messageAPI.PARA.file:
                type_path = 'files'
            else:
                continue
            resource_url = event_action._get_message_resource(message_this)
            if resource_url is None:
                failed_text_buffer = text_content
                continue
            file_info = event_action.setResourceUploadFast(
                target_event,
                resource_url,
                chat_id,
                type_path=type_path,
                type_chat='qq_users' if flag_direct else 'qq_groups'
            )
            if file_info is None:
                # 上传失败时保留对应文字，合并到下一条成功发送的图文消息。
                failed_text_buffer = text_content
                continue
            event_action._send_qq_payload(
                target_event,
                chat_id,
                text_content,
                msg_id,
                flag_direct=flag_direct,
                file_info=file_info
            )
            failed_text_buffer = ''

        # 最后一项媒体上传失败时，仍发送已经积累的文字，避免内容静默丢失。
        if failed_text_buffer != '':
            event_action._send_qq_payload(
                target_event,
                chat_id,
                failed_text_buffer,
                msg_id,
                flag_direct=flag_direct
            )

    def _send_qq_payload(target_event, chat_id, content, msg_id, flag_direct=False, file_info=None):
        if flag_direct:
            this_msg = API.sendQQDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.openid = str(chat_id)
        else:
            this_msg = API.sendQQMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.group_openid = str(chat_id)
        this_msg.data.content = content
        this_msg.data.msg_id = msg_id
        if file_info is None:
            this_msg.data.msg_type = 0
        else:
            # 上传接口返回的 file_info 必须包装到 media 对象中，再调用消息发送接口。
            this_msg.data.msg_type = 7
            this_msg.data.media = {'file_info': file_info}
        if msg_id is not None:
            this_msg.data.msg_seq = get_msgid(str(msg_id))
        return this_msg.do_api()

    def send_msg(target_event, chat_id, message, reply_msg_id=None, flag_direct=False):
        # 频道图片沿用 QQ 图文的双向分组规则。
        failed_text_buffer = ''
        for text_content, message_this in event_action._get_message_send_chunks(
            message,
            [OlivOS.messageAPI.PARA.image]
        ):
            text_content = failed_text_buffer + text_content
            if message_this is None:
                event_action._send_channel_payload(
                    target_event,
                    chat_id,
                    text_content,
                    reply_msg_id,
                    flag_direct=flag_direct
                )
                failed_text_buffer = ''
                continue
            resource_url = event_action._get_message_resource(message_this)
            if resource_url is None:
                failed_text_buffer = text_content
                continue
            image_data = event_action._get_channel_image_data(resource_url)
            if image_data is None:
                failed_text_buffer = text_content
                continue
            event_action._send_channel_payload(
                target_event,
                chat_id,
                text_content,
                reply_msg_id,
                flag_direct=flag_direct,
                image_data=image_data
            )
            failed_text_buffer = ''

        if failed_text_buffer != '':
            event_action._send_channel_payload(
                target_event,
                chat_id,
                failed_text_buffer,
                reply_msg_id,
                flag_direct=flag_direct
            )

    def _send_channel_payload(target_event, chat_id, content, msg_id, flag_direct=False, image_data=None):
        if flag_direct:
            this_msg = API.sendDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.guild_id = str(chat_id)
        else:
            this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.channel_id = str(chat_id)
        this_msg.data.content = content
        this_msg.data.msg_id = msg_id
        if type(image_data) is dict:
            if image_data.get('image', None) is not None:
                this_msg.data.image = image_data['image']
            elif image_data.get('file_image', None) is not None:
                this_msg.data.file_image = image_data['file_image']
        return this_msg.do_api()

    def get_login_info(target_event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        raw_obj = None
        if (
            target_event.bot_info.hash in sdkSelfInfo
            and type(sdkSelfInfo[target_event.bot_info.hash]) is dict
            and 'id' in sdkSelfInfo[target_event.bot_info.hash]
            and 'username' in sdkSelfInfo[target_event.bot_info.hash]
        ):
            res_data['active'] = True
            res_data['data']['name'] = str(sdkSelfInfo[target_event.bot_info.hash]['username'])
            res_data['data']['id'] = str(sdkSelfInfo[target_event.bot_info.hash]['id'])
        else:
            this_msg = API.getMe(get_SDK_bot_info_from_Event(target_event))
            try:
                this_msg.do_api('GET')
                if this_msg.res is not None:
                    raw_obj = init_api_json(this_msg.res)
                if raw_obj is not None:
                    if (
                        type(raw_obj) is dict
                        and 0 == init_api_do_mapping_for_dict(raw_obj, ['code'], int)
                    ):
                        res_data['active'] = True
                        res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['username'], str)
                        res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['id'], str))
            except Exception:
                res_data['active'] = False
        return res_data

    # 通过 OlivOS 既有 delete_msg 接口自动选择 QQ/频道撤回路由
    def delete_msg(target_event, message_id):
        target_data = target_event.data
        extend_data = target_data.extend
        flag_from_qq = extend_data.get('flag_from_qq', False)
        flag_from_direct = extend_data.get('flag_from_direct', False)
        this_msg = None

        if flag_from_qq and flag_from_direct:
            this_msg = API.deleteQQDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.openid = str(target_data.user_id)
        elif flag_from_qq:
            this_msg = API.deleteQQMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.group_openid = str(target_data.group_id)
        elif flag_from_direct:
            this_msg = API.deleteDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.guild_id = str(extend_data['host_group_id'])
        else:
            this_msg = API.deleteMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.channel_id = str(target_data.group_id)
        this_msg.metadata.message_id = str(message_id)
        return this_msg.do_api('DELETE')

    # 优先使用消息段中的 URL，其次使用本地 path/file
    def _get_message_resource(message_para):
        if message_para.data is None:
            return None
        for data_key in ['url', 'path', 'file']:
            data_value = message_para.data.get(data_key, None)
            if data_value is not None and str(data_value) != '':
                return str(data_value)
        return None

    # 读取 OlivOS 支持的 base64、data URI、file URI 或本地资源
    def _get_local_resource_data(url: str, type_path: str = 'images'):
        if url.startswith('base64://'):
            return base64.b64decode(url[9:].encode('utf-8'))
        if url.startswith('data:') and ',' in url:
            data_meta, data_raw = url.split(',', 1)
            if data_meta.endswith(';base64'):
                return base64.b64decode(data_raw.encode('utf-8'))
            return parse.unquote_to_bytes(data_raw)

        url_parsed = parse.urlparse(url)
        if url_parsed.scheme == 'file':
            file_path = parse.unquote(url_parsed.path)
            if url_parsed.netloc != '':
                file_path = '//' + url_parsed.netloc + file_path
            if re.match(r'^/[a-zA-Z]:/', file_path):
                file_path = file_path[1:]
        else:
            file_path = url
        file_path = OlivOS.contentAPI.resourcePathTransform(type_path, file_path)
        with open(file_path, 'rb') as file_obj:
            return file_obj.read()

    # 频道远程图片走 image，本地/二进制图片走 file_image 表单字段
    def _get_channel_image_data(url: str):
        url_parsed = parse.urlparse(url)
        if url_parsed.scheme in ['http', 'https']:
            return {'image': url}
        try:
            file_data = event_action._get_local_resource_data(url, 'images')
            file_name = os.path.basename(parse.unquote(url_parsed.path))
            if file_name == '' or '.' not in file_name:
                file_name = str(uuid.uuid4()) + '.png'
            file_mime = mimetypes.guess_type(file_name)[0]
            if file_mime is None or not file_mime.startswith('image/'):
                file_mime = 'image/png'
            return {'file_image': (file_name, file_data, file_mime)}
        except Exception:
            traceback.print_exc()
            return None

    # QQ 富媒体必须先上传获取 file_info，再由 send_qq_msg 调用消息发送接口。
    def setResourceUploadFast(
        target_event,
        url: str,
        chat_id,
        type_path: str = 'images',
        type_chat: str = 'qq_groups'
    ):
        res = None
        file_type_map = {
            'images': 1,
            'videos': 2,
            'audios': 3,
            'files': 4
        }
        file_type = file_type_map.get(type_path, 4)
        try:
            msg_upload_api = API.setResourcePictureUpload(get_SDK_bot_info_from_Event(target_event))
            msg_upload_api.resource_type = type_chat
            msg_upload_api.metadata.openid = str(chat_id)
            msg_upload_api.data.file_type = file_type

            url_parsed = parse.urlparse(url)
            if url_parsed.scheme in ['http', 'https']:
                # 远程资源直接交给 QQ 平台拉取，避免 OlivOS 额外下载和重复编码。
                msg_upload_api.data.url = url
            else:
                file_data = event_action._get_local_resource_data(url, type_path)
                msg_upload_api.data.file_data = base64.b64encode(file_data).decode('ascii')

            msg_upload_api.do_api('POST')
            if msg_upload_api.res is not None:
                msg_upload_api_obj = init_api_json(msg_upload_api.res)
                if type(msg_upload_api_obj) is dict:
                    if msg_upload_api_obj.get('code', 0) != 0:
                        return None
                    # 当前接口成功时直接返回媒体对象；兼容部分环境的 data 包装格式。
                    msg_upload_api_data = msg_upload_api_obj.get('data', msg_upload_api_obj)
                    if type(msg_upload_api_data) is dict:
                        res = msg_upload_api_data.get('file_info', None)
        except Exception:
            traceback.print_exc()
            res = None
        return res


def get_msgid(key: str):
    res = sdkMsgidinfo.get(key, 0)
    if type(res) is int:
        res += 1
        sdkMsgidinfo[key] = res
    else:
        res = None
    return res


def init_api_json(raw_str):
    res_data = None
    tmp_obj = None
    flag_is_active = False
    try:
        tmp_obj = json.loads(raw_str)
    except Exception:
        tmp_obj = None
    if type(tmp_obj) is dict:
        flag_is_active = True
    if flag_is_active:
        if type(tmp_obj) is dict:
            res_data = tmp_obj.copy()
        elif type(tmp_obj) is list:
            res_data = tmp_obj.copy()
    return res_data


def init_api_do_mapping(src_type, src_data):
    if type(src_data) is src_type:
        return src_data


def init_api_do_mapping_for_dict(src_data, path_list, src_type):
    res_data = None
    tmp_src_data = src_data
    for path_list_this in path_list:
        if type(tmp_src_data) is dict:
            if path_list_this in tmp_src_data:
                tmp_src_data = tmp_src_data[path_list_this]
            else:
                return None
        else:
            return None
    res_data = init_api_do_mapping(src_type, tmp_src_data)
    return res_data
