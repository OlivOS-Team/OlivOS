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
import copy
import threading
from collections import deque

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
    PUBLIC_QQ_GROUP_MEMBERS = (1 << 24)  # QQ 群成员进退群事件


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
sdkSubSelfOpenInfo = {}
sdkSubSelfOpenInfoLock = threading.Lock()
sdkSubSelfOpenInfoRetryAt = {}
sdkSubSelfOpenInfoRequestHistory = {}
sdkSubSelfOpenInfoDisabled = set()
sdkSubSelfOpenInfoRetryCooldown = 60.0
sdkSubSelfOpenInfoRateWindow = 60.0
sdkSubSelfOpenInfoRateLimit = 60
sdkTokenInfo = {}
sdkMsgidinfo = {}
sdkMsgidinfoLock = threading.Lock()
sdkMsgidinfoTTL = 300.0
sdkMsgidinfoMaxSize = 10000
sdkEventidinfo = {}
sdkEventidinfoLock = threading.Lock()
sdkEventidinfoMaxSize = 10000
sdkSentMessageInfo = {}
sdkSentMessageInfoLock = threading.Lock()
sdkSentMessageInfoLastCleanup = 0.0
sdkSentMessageInfoMaxSize = 20000
sdkDeleteRateInfo = {}
sdkDeleteRateInfoLock = threading.Lock()
sdkSelfInfo = {}

qqMessageEventTypes = {
    'MESSAGE_CREATE',
    'AT_MESSAGE_CREATE',
    'DIRECT_MESSAGE_CREATE',
    'GROUP_AT_MESSAGE_CREATE',
    'GROUP_MESSAGE_CREATE',
    'C2C_MESSAGE_CREATE'
}
qqAtBotEventTypes = {
    'AT_MESSAGE_CREATE',
    'GROUP_AT_MESSAGE_CREATE'
}
qqEventReplyTypes = {
    'qq_group': {
        'INTERACTION_CREATE',
        'GROUP_ADD_ROBOT',
        'GROUP_MEMBER_ADD',
        'GROUP_MSG_RECEIVE'
    },
    'qq_private': {
        'INTERACTION_CREATE',
        'C2C_MSG_RECEIVE',
        'FRIEND_ADD'
    }
}
qqAsyncAcceptedCodes = {304023, 304024}
qqPassiveFallbackErrorCodes = {
    'msg_id': {304103, 40034005, 40034024, 40034128},
    'event_id': {40034025, 40034026, 40034027, 40034128}
}
qqLocalPassiveFallbackErrors = {
    'passive reply count exceeded',
    'passive event reply count exceeded'
}
qqEventDedupeCache = {}
qqEventDedupeLock = threading.Lock()
qqEventDedupeTTL = 120.0
qqEventDedupeMaxSize = 10000


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
            self.id = None
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
                if 'id' in data:
                    if type(data['id']) is str:
                        self.data.id = data['id']
                    else:
                        self.active = False
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
                tmp_intents |= int(intents_T.PUBLIC_QQ_GROUP_MEMBERS)
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
        self.res_code = None

    def __switch_host(self):
        if self.bot_info.model in ['sandbox', 'sandbox_intents']:
            if self.host == sdkAPIHost['default']:
                self.host = sdkAPIHost['sandbox']

    def do_api_plant(self, req_type='POST'):
        self.res = None
        self.res_code = None
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
            self.res_code = msg_res.status_code
            return msg_res.text
        except Exception:
            return None

    def do_api(self, req_type='POST'):
        self.res = None
        self.res_code = None
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
            self.res_code = msg_res.status_code
            # print(self.res)
            return msg_res.text
        except Exception:
            traceback.print_exc()
            return None


def _send_channel_multipart(bot_info, metadata, data, host, port, route, req_type='POST'):
    try:
        if bot_info.model in ['sandbox', 'sandbox_intents']:
            if host == sdkAPIHost['default']:
                host = sdkAPIHost['sandbox']
        tmp_payload_dict = {}
        tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
        if metadata is not None:
            tmp_sdkAPIRouteTemp.update(metadata.__dict__)
        if data is not None:
            for data_this in data.__dict__:
                if data_this != 'file_image' and data.__dict__[data_this] is not None:
                    data_value = data.__dict__[data_this]
                    if type(data_value) in [dict, list]:
                        data_value = json.dumps(obj=data_value)
                    elif type(data_value) is bool:
                        data_value = str(data_value).lower()
                    else:
                        data_value = str(data_value)
                    tmp_payload_dict[data_this] = data_value
        tmp_payload_dict['file_image'] = data.file_image
        payload = MultipartEncoder(fields=tmp_payload_dict)
        send_url_temp = host + ':' + str(port) + route
        send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
        headers = {
            'Content-Type': payload.content_type,
            'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
            'Authorization': 'QQBot %s' % (getTokenNow(bot_info)),
            'X-Union-Appid': str(bot_info.id)
        }
        msg_res = None
        if req_type == 'POST':
            msg_res = req.request("POST", send_url, headers=headers, data=payload)
        return msg_res
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

    class getQQGroupBotState(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/bot_state'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

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
            msg_res = _send_channel_multipart(
                self.bot_info, self.metadata, self.data,
                self.host, self.port, self.route, req_type
            )
            if msg_res is None:
                self.res = None
                self.res_code = None
                return None
            self.res = msg_res.text
            self.res_code = msg_res.status_code
            return self.res

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
            msg_res = _send_channel_multipart(
                self.bot_info, self.metadata, self.data,
                self.host, self.port, self.route, req_type
            )
            if msg_res is None:
                self.res = None
                self.res_code = None
                return None
            self.res = msg_res.text
            self.res_code = msg_res.status_code
            return self.res

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


def _get_qq_author_name(author):
    if not isinstance(author, dict):
        return '用户'
    username = author.get('username', None)
    if isinstance(username, str) and username.strip() != '':
        return username
    return '用户'


def _get_qq_sender_role(author):
    if not isinstance(author, dict):
        return 'member'
    member_role = author.get('member_role', None)
    if member_role in {'member', 'admin', 'owner'}:
        return member_role
    return 'member'


def _get_qq_guild_sender_role(member):
    if not isinstance(member, dict):
        return 'member'
    roles = member.get('roles', None)
    if not isinstance(roles, list):
        return 'member'
    roles = {str(role) for role in roles}
    if '4' in roles:
        return 'owner'
    if '2' in roles or '5' in roles:
        return 'admin'
    return 'member'


def _parse_qq_message_scene_ext(message_scene):
    result = {}
    if not isinstance(message_scene, dict):
        return result
    scene_ext = message_scene.get('ext', None)
    if not isinstance(scene_ext, list):
        return result
    for ext_item in scene_ext:
        if not isinstance(ext_item, str) or '=' not in ext_item:
            continue
        key, value = ext_item.split('=', 1)
        key = key.strip()
        if key == '' or key.lower() == 'auth_token':
            continue
        result[key] = value
    return result


def _sanitize_qq_message_scene(message_scene):
    scene_copy = copy.deepcopy(message_scene)
    auth_token_present = False
    if not isinstance(scene_copy, dict):
        return scene_copy, auth_token_present
    scene_ext = scene_copy.get('ext', None)
    if not isinstance(scene_ext, list):
        return scene_copy, auth_token_present
    safe_scene_ext = []
    for ext_item in scene_ext:
        if isinstance(ext_item, str) and '=' in ext_item:
            key = ext_item.split('=', 1)[0].strip()
            if key.lower() == 'auth_token':
                auth_token_present = True
                continue
        safe_scene_ext.append(ext_item)
    scene_copy['ext'] = safe_scene_ext
    return scene_copy, auth_token_present


def _get_qq_message_event_extend(event_type, event_data):
    if not isinstance(event_data, dict):
        event_data = {}
    result = {
        'qq_event_type': str(event_type),
        # 全量群消息事件本身不能证明消息是否 @ 机器人；保留未知态，
        # 避免其先于 GROUP_AT_MESSAGE_CREATE 到达时被错误标记为 False。
        'qq_at_bot': (
            None
            if event_type == 'GROUP_MESSAGE_CREATE'
            else event_type in qqAtBotEventTypes
        ),
        'qq_at_bot_known': event_type != 'GROUP_MESSAGE_CREATE',
        'qq_raw_content': copy.deepcopy(event_data.get('content', None))
    }
    raw_event = copy.deepcopy(event_data)
    message_scene = event_data.get('message_scene', None)
    safe_message_scene, auth_token_present = _sanitize_qq_message_scene(message_scene)
    if 'message_scene' in raw_event:
        raw_event['message_scene'] = copy.deepcopy(safe_message_scene)
    result['qq_event_data'] = raw_event
    field_map = {
        'id': 'qq_message_id',
        'author': 'qq_author',
        'message_type': 'qq_message_type',
        'msg_elements': 'qq_msg_elements',
        'ark_data': 'qq_ark_data',
        'mentions': 'qq_mentions',
        'attachments': 'qq_attachments',
        'timestamp': 'qq_timestamp'
    }
    for source_key, target_key in field_map.items():
        if source_key in event_data:
            result[target_key] = copy.deepcopy(event_data[source_key])
    if 'message_scene' in event_data:
        result['qq_message_scene'] = copy.deepcopy(safe_message_scene)
        scene_ext = _parse_qq_message_scene_ext(message_scene)
        result['qq_message_scene_ext'] = scene_ext
        if 'msg_idx' in scene_ext:
            result['qq_msg_idx'] = scene_ext['msg_idx']
        if 'ref_msg_idx' in scene_ext:
            # ref_msg_idx 是 QQ 的消息索引，不是可发送的 message_id。
            result['qq_ref_msg_idx'] = scene_ext['ref_msg_idx']
    if auth_token_present:
        result['qq_message_scene_auth_token_present'] = True
    return result


def _get_qq_mention_map(mentions):
    result = {}
    if not isinstance(mentions, list):
        return result
    for mention in mentions:
        if not isinstance(mention, dict):
            continue
        username = mention.get('username', None)
        if not isinstance(username, str) or username.strip() == '':
            username = None
        for id_key in ['id', 'user_openid', 'member_openid']:
            user_id = mention.get(id_key, None)
            if user_id is not None and str(user_id) != '':
                result[str(user_id)] = username
    return result


def _get_qq_group_self_open_id(bot_hash, group_openid, bot_info, now=None):
    if group_openid is None or str(group_openid) == '':
        return None
    group_openid = str(group_openid)
    cache_key = (bot_hash, group_openid)
    if now is None:
        now = time.monotonic()
    with sdkSubSelfOpenInfoLock:
        bot_cache = sdkSubSelfOpenInfo.get(bot_hash, {})
        if group_openid in bot_cache:
            return bot_cache[group_openid]
        if bot_hash in sdkSubSelfOpenInfoDisabled:
            return None
        if sdkSubSelfOpenInfoRetryAt.get(cache_key, 0.0) > now:
            return None
        request_history = sdkSubSelfOpenInfoRequestHistory.setdefault(
            bot_hash,
            deque()
        )
        request_window_start = now - sdkSubSelfOpenInfoRateWindow
        while request_history and request_history[0] <= request_window_start:
            request_history.popleft()
        if len(request_history) >= sdkSubSelfOpenInfoRateLimit:
            sdkSubSelfOpenInfoRetryAt[cache_key] = (
                request_history[0] + sdkSubSelfOpenInfoRateWindow
            )
            return None
        # 先占用请求窗口，避免并发事件为同一群重复发起请求。
        sdkSubSelfOpenInfoRetryAt[cache_key] = now + sdkSubSelfOpenInfoRetryCooldown
        request_history.append(now)

    api_msg_obj = API.getQQGroupBotState(bot_info)
    api_msg_obj.metadata.group_openid = group_openid
    api_msg_obj.do_api('GET')
    try:
        api_res_json = json.loads(api_msg_obj.res)
    except (TypeError, ValueError):
        return None
    if not isinstance(api_res_json, dict):
        return None

    error_code = api_res_json.get('code', None)
    try:
        error_code = int(error_code)
    except (TypeError, ValueError):
        error_code = None
    if error_code == 11253:
        with sdkSubSelfOpenInfoLock:
            sdkSubSelfOpenInfoDisabled.add(bot_hash)
            sdkSubSelfOpenInfoRetryAt.pop(cache_key, None)
        return None

    member_openid = api_res_json.get('member_openid', None)
    if (
        api_msg_obj.res_code is None
        or not 200 <= api_msg_obj.res_code < 300
        or member_openid is None
        or str(member_openid) == ''
    ):
        return None
    member_openid = str(member_openid)
    with sdkSubSelfOpenInfoLock:
        sdkSubSelfOpenInfo.setdefault(bot_hash, {})[group_openid] = member_openid
        sdkSubSelfOpenInfoRetryAt.pop(cache_key, None)
    return member_openid


def _get_qq_group_self_open_id_from_mentions(bot_hash, group_openid, mentions):
    if group_openid is None or str(group_openid) == '':
        return None
    self_info = sdkSelfInfo.get(bot_hash, None)
    if not isinstance(self_info, dict):
        return None
    self_username = self_info.get('username', None)
    if not isinstance(self_username, str) or self_username == '':
        return None
    if not isinstance(mentions, list):
        return None

    candidates = []
    for mention in mentions:
        if not isinstance(mention, dict):
            continue
        if mention.get('bot', False) is not True:
            continue
        if mention.get('username', None) != self_username:
            continue
        open_id = mention.get(
            'member_openid',
            mention.get('id', mention.get('user_openid', None))
        )
        if open_id is not None and str(open_id) != '':
            candidates.append(str(open_id))
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) != 1:
        return None

    group_openid = str(group_openid)
    with sdkSubSelfOpenInfoLock:
        sdkSubSelfOpenInfo.setdefault(bot_hash, {})[group_openid] = candidates[0]
        sdkSubSelfOpenInfoRetryAt.pop((bot_hash, group_openid), None)
    return candidates[0]


def _apply_qq_message_mentions(message_obj, mentions):
    mention_map = _get_qq_mention_map(mentions)
    if not mention_map or not isinstance(message_obj.data, list):
        return
    flag_updated = False
    message_data = []
    for message_item in message_obj.data:
        if isinstance(message_item, OlivOS.messageAPI.PARA.at):
            user_id = str(message_item.data.get('id', ''))
            username = mention_map.get(user_id, None)
            if message_item.data.get('name', None) is None and username is not None:
                message_item.data['name'] = username
                flag_updated = True
            message_data.append(message_item)
            continue
        if not isinstance(message_item, OlivOS.messageAPI.PARA.text):
            message_data.append(message_item)
            continue
        text_content = message_item.data.get('text', '')
        if not isinstance(text_content, str):
            message_data.append(message_item)
            continue
        last_index = 0
        flag_text_updated = False
        for match in re.finditer(r'<@([^<>]+)>', text_content):
            user_id = str(match.group(1))
            if user_id not in mention_map:
                continue
            if match.start() > last_index:
                message_data.append(
                    OlivOS.messageAPI.PARA.text(text_content[last_index:match.start()])
                )
            message_data.append(
                OlivOS.messageAPI.PARA.at(
                    id=user_id,
                    name=mention_map[user_id]
                )
            )
            last_index = match.end()
            flag_text_updated = True
        if flag_text_updated:
            if last_index < len(text_content):
                message_data.append(
                    OlivOS.messageAPI.PARA.text(text_content[last_index:])
                )
            flag_updated = True
        else:
            message_data.append(message_item)
    if flag_updated:
        message_obj.data = message_data
        if isinstance(message_obj.data_raw, list):
            # 兼容层会处理 data_raw，避免其浅拷贝误删 message_sdk.data 中的 name。
            message_obj.data_raw = copy.deepcopy(message_obj.data)


def _get_qq_event_dedupe_key(bot_id, event_type, event_data):
    if event_type not in qqMessageEventTypes or not isinstance(event_data, dict):
        return None
    message_id = event_data.get('id', None)
    if message_id is None or str(message_id) == '':
        return None
    scene_ext = _parse_qq_message_scene_ext(event_data.get('message_scene', None))
    return (
        str(bot_id),
        str(event_type),
        str(message_id),
        str(scene_ext.get('msg_idx', ''))
    )


def _is_qq_event_duplicate(dedupe_key, now=None):
    if dedupe_key is None:
        return False
    if now is None:
        now = time.monotonic()
    with qqEventDedupeLock:
        expired_keys = [
            cache_key
            for cache_key, expires_at in qqEventDedupeCache.items()
            if expires_at <= now
        ]
        for cache_key in expired_keys:
            qqEventDedupeCache.pop(cache_key, None)
        expires_at = qqEventDedupeCache.get(dedupe_key, None)
        if expires_at is not None and expires_at > now:
            return True
        qqEventDedupeCache[dedupe_key] = now + qqEventDedupeTTL
        overflow_size = len(qqEventDedupeCache) - qqEventDedupeMaxSize
        if overflow_size > 0:
            oldest_items = sorted(
                qqEventDedupeCache.items(),
                key=lambda cache_item: cache_item[1]
            )[:overflow_size]
            for cache_key, _ in oldest_items:
                qqEventDedupeCache.pop(cache_key, None)
    return False


def _set_qq_group_member_event(
    target_event,
    event_data,
    flag_increase,
    operator_id,
    user_id,
    action
):
    target_event.active = True
    if flag_increase:
        target_event.plugin_info['func_type'] = 'group_member_increase'
        target_event.data = target_event.group_member_increase(
            str(event_data.get('group_openid', '')),
            str(operator_id),
            str(user_id),
            action=action
        )
    else:
        target_event.plugin_info['func_type'] = 'group_member_decrease'
        target_event.data = target_event.group_member_decrease(
            str(event_data.get('group_openid', '')),
            str(operator_id),
            str(user_id),
            action=action
        )
    target_event.data.extend = {
        'flag_from_qq': True,
        'timestamp': event_data.get('timestamp', None)
    }


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
    event_type = target_event.sdk_event.payload.data.t
    event_data = target_event.sdk_event.payload.data.d
    dedupe_key = _get_qq_event_dedupe_key(
        plugin_event_bot_hash,
        event_type,
        event_data
    )
    if _is_qq_event_duplicate(dedupe_key):
        target_event.active = False
        return
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
        'GROUP_ADD_ROBOT',
        'GROUP_DEL_ROBOT'
    ]:
        event_data = target_event.sdk_event.payload.data.d
        operator_openid = str(event_data.get('op_member_openid', ''))
        flag_increase = target_event.sdk_event.payload.data.t == 'GROUP_ADD_ROBOT'
        _set_qq_group_member_event(
            target_event,
            event_data,
            flag_increase,
            operator_openid,
            target_event.base_info['self_id'],
            'invite' if flag_increase else 'kick_me'
        )
    elif target_event.sdk_event.payload.data.t in [
        'GROUP_MEMBER_ADD',
        'GROUP_MEMBER_REMOVE'
    ]:
        event_data = target_event.sdk_event.payload.data.d
        member_openid = str(event_data.get('member_openid', ''))
        flag_increase = target_event.sdk_event.payload.data.t == 'GROUP_MEMBER_ADD'
        _set_qq_group_member_event(
            target_event,
            event_data,
            flag_increase,
            member_openid,
            member_openid,
            'approve' if flag_increase else 'leave'
        )
    elif target_event.sdk_event.payload.data.t == 'FRIEND_ADD':
        user_openid = event_data.get('openid', None)
        if user_openid is not None and str(user_openid) != '':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'friend_add'
            target_event.data = target_event.friend_add(str(user_openid))
            target_event.data.extend = {
                'flag_from_qq': True,
                'flag_from_direct': True,
                'timestamp': event_data.get('timestamp', None),
                'qq_scene': event_data.get('scene', None),
                'qq_scene_param': event_data.get('scene_param', None),
                'qq_author': copy.deepcopy(event_data.get('author', None)),
                'qq_event_data': copy.deepcopy(event_data)
            }
    elif target_event.sdk_event.payload.data.t in [
        'GROUP_AT_MESSAGE_CREATE',
        'GROUP_MESSAGE_CREATE'
    ]:
        author = event_data.get('author', {})
        message_obj = None
        if 'content' in event_data:
            if event_data['content'] != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuildv2_string',
                    event_data['content']
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
                event_data.get('attachments', None)
            )
        )
        try:
            message_obj.init_data()
        except Exception:
            message_obj.active = False
            message_obj.data = []
        if message_obj.active:
            _apply_qq_message_mentions(message_obj, event_data.get('mentions', None))
            # QQ 新版事件使用 group_openid/member_openid，保留旧字段作为兼容回退。
            group_openid = event_data.get(
                'group_openid',
                event_data.get('group_id', None)
            )
            sub_self_open_id = _get_qq_group_self_open_id(
                plugin_event_bot_hash,
                group_openid,
                bot_info_T(
                    id=target_event.sdk_event.base_info['self_id'],
                    access_token=target_event.sdk_event.base_info['token'],
                    model=target_event.platform.get('model', 'default')
                )
            )
            if sub_self_open_id is None:
                sub_self_open_id = _get_qq_group_self_open_id_from_mentions(
                    plugin_event_bot_hash,
                    group_openid,
                    event_data.get('mentions', None)
                )
            member_openid = author.get(
                'member_openid',
                author.get('id', None)
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
            target_event.data.message_id = str(event_data.get('id', ''))
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = str(member_openid)
            target_event.data.sender['nickname'] = _get_qq_author_name(author)
            target_event.data.sender['id'] = target_event.data.sender['user_id']
            target_event.data.sender['name'] = target_event.data.sender['nickname']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.sender['role'] = _get_qq_sender_role(author)
            target_event.data.host_id = None
            target_event.data.extend['group_id'] = str(group_openid)
            target_event.data.extend['host_group_id'] = None
            target_event.data.extend['flag_from_direct'] = False
            target_event.data.extend['flag_from_qq'] = True
            target_event.data.extend['reply_msg_id'] = event_data.get('id', None)
            target_event.data.extend.update(
                _get_qq_message_event_extend(event_type, event_data)
            )
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
            if sub_self_open_id is not None:
                target_event.data.extend['sub_self_open_id'] = sub_self_open_id
    elif target_event.sdk_event.payload.data.t == 'C2C_MESSAGE_CREATE':
        author = event_data.get('author', {})
        message_obj = None
        if 'content' in event_data:
            if event_data['content'] != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuildv2_string',
                    event_data['content']
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
                event_data.get('attachments', None)
            )
        )
        try:
            message_obj.init_data()
        except Exception:
            message_obj.active = False
            message_obj.data = []
        if message_obj.active:
            _apply_qq_message_mentions(message_obj, event_data.get('mentions', None))
            # C2C 新版事件的用户标识为 author.user_openid。
            user_openid = author.get(
                'user_openid',
                author.get('id', None)
            )
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message'
            target_event.data = target_event.private_message(
                str(user_openid),
                message_obj,
                'friend'
            )
            target_event.data.message_sdk = message_obj
            target_event.data.message_id = str(event_data.get('id', ''))
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = str(user_openid)
            target_event.data.sender['nickname'] = _get_qq_author_name(author)
            target_event.data.sender['id'] = target_event.data.sender['user_id']
            target_event.data.sender['name'] = target_event.data.sender['nickname']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.sender['role'] = 'member'
            target_event.data.extend['flag_from_direct'] = True
            target_event.data.extend['flag_from_qq'] = True
            target_event.data.extend['reply_msg_id'] = event_data.get('id', None)
            target_event.data.extend.update(
                _get_qq_message_event_extend(event_type, event_data)
            )
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
    elif target_event.sdk_event.payload.data.t in [
        'MESSAGE_CREATE',
        'AT_MESSAGE_CREATE'
    ]:
        author = event_data.get('author', {})
        message_content = event_data.get('content', None)
        message_obj = None
        if message_content is not None:
            if message_content != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuild_string',
                    message_content.lstrip(' ')
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
                event_data.get('attachments', None)
            )
        )
        try:
            message_obj.init_data()
        except Exception:
            message_obj.active = False
            message_obj.data = []
        if message_obj.active:
            _apply_qq_message_mentions(message_obj, event_data.get('mentions', None))
            author_id = author.get('id', None)
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message'
            target_event.data = target_event.group_message(
                str(event_data.get('channel_id', '')),
                str(author_id),
                message_obj,
                'group'
            )
            target_event.data.message_sdk = message_obj
            target_event.data.message_id = str(event_data.get('id', ''))
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = str(author_id)
            target_event.data.sender['nickname'] = _get_qq_author_name(author)
            target_event.data.sender['id'] = str(author_id)
            target_event.data.sender['name'] = target_event.data.sender['nickname']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.sender['role'] = _get_qq_guild_sender_role(
                event_data.get('member', None)
            )
            target_event.data.host_id = event_data.get('guild_id', None)
            target_event.data.extend['group_id'] = str(event_data.get('channel_id', ''))
            target_event.data.extend['host_group_id'] = str(event_data.get('guild_id', ''))
            target_event.data.extend['flag_from_direct'] = False
            target_event.data.extend['flag_from_qq'] = False
            target_event.data.extend['reply_msg_id'] = event_data.get('id', None)
            target_event.data.extend.update(
                _get_qq_message_event_extend(event_type, event_data)
            )
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
    elif target_event.sdk_event.payload.data.t == 'DIRECT_MESSAGE_CREATE':
        author = event_data.get('author', {})
        message_obj = None
        if 'content' in event_data:
            if event_data['content'] != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuild_string',
                    event_data['content'].lstrip(' ')
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
                event_data.get('attachments', None)
            )
        )
        try:
            message_obj.init_data()
        except Exception:
            message_obj.active = False
            message_obj.data = []
        if message_obj.active:
            _apply_qq_message_mentions(message_obj, event_data.get('mentions', None))
            author_id = author.get('id', None)
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message'
            target_event.data = target_event.private_message(
                str(author_id),
                message_obj,
                'friend'
            )
            target_event.data.message_sdk = message_obj
            target_event.data.message_id = str(event_data.get('id', ''))
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = str(author_id)
            target_event.data.sender['nickname'] = _get_qq_author_name(author)
            target_event.data.sender['id'] = str(author_id)
            target_event.data.sender['name'] = target_event.data.sender['nickname']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.sender['role'] = 'member'
            target_event.data.extend['group_id'] = str(event_data.get('channel_id', ''))
            target_event.data.extend['host_group_id'] = str(event_data.get('guild_id', ''))
            target_event.data.extend['flag_from_direct'] = True
            target_event.data.extend['flag_from_qq'] = False
            target_event.data.extend['reply_msg_id'] = event_data.get('id', None)
            target_event.data.extend.update(
                _get_qq_message_event_extend(event_type, event_data)
            )
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])

    event_id = target_event.sdk_event.payload.data.id
    if (
        target_event.active
        and hasattr(target_event.data, 'extend')
        and type(target_event.data.extend) is dict
    ):
        target_event.data.extend.setdefault('qq_event_type', str(event_type))
        if event_id is not None:
            target_event.data.extend['event_id'] = str(event_id)


# 支持OlivOS API调用的方法实现
class event_action(object):
    def _normalize_outgoing_message(target_event, message):
        if isinstance(message, OlivOS.messageAPI.Message_templet):
            return message
        message_mode = target_event.plugin_info.get(
            'message_mode_tx',
            OlivOS.infoAPI.OlivOS_message_mode_tx_unity
        )
        if type(message) is list:
            if all(
                isinstance(message_item, OlivOS.messageAPI.PARA_templet)
                for message_item in message
            ):
                return OlivOS.messageAPI.Message_templet('olivos_para', message)
            return OlivOS.messageAPI.Message_templet('olivos_para', [])
        if type(message) not in [str, list]:
            message = str(message)
        return OlivOS.messageAPI.Message_templet(message_mode, message)

    def _get_message_reference_id(message):
        for message_this in message.data:
            if not isinstance(message_this, OlivOS.messageAPI.PARA.reply):
                continue
            message_id = message_this.data.get('id', None)
            if message_id is not None and str(message_id) != '':
                return str(message_id)
        return None

    def _get_reply_seq_key(target_event, chat_type, chat_id, msg_id):
        return '|'.join([
            str(target_event.bot_info.hash),
            str(chat_type),
            str(chat_id),
            str(msg_id)
        ])

    def _resolve_qq_passive_ids(
        target_event,
        chat_type,
        chat_id,
        msg_id=None,
        event_id=None
    ):
        """仅为同一 QQ 会话自动复用官方允许的被动回复标识。"""
        if msg_id is not None or event_id is not None:
            return msg_id, event_id
        target_data = getattr(target_event, 'data', None)
        extend_data = getattr(target_data, 'extend', None)
        if not isinstance(extend_data, dict) or not extend_data.get('flag_from_qq', False):
            return None, None

        passive_disabled = extend_data.get('qq_passive_reply_disabled', None)
        if passive_disabled is True:
            return None, None
        if (
            isinstance(passive_disabled, dict)
            and passive_disabled.get('chat_type', None) == str(chat_type)
            and passive_disabled.get('chat_id', None) == str(chat_id)
        ):
            return None, None

        flag_direct = extend_data.get('flag_from_direct', False)
        if chat_type == 'qq_private' and flag_direct:
            source_chat_id = getattr(target_data, 'user_id', None)
        elif chat_type == 'qq_group' and not flag_direct:
            source_chat_id = getattr(target_data, 'group_id', None)
        else:
            return None, None
        if source_chat_id is None or str(source_chat_id) != str(chat_id):
            return None, None

        event_type = extend_data.get('qq_event_type', None)
        if event_type in qqEventReplyTypes.get(chat_type, set()):
            source_event_id = extend_data.get('event_id', None)
            if source_event_id is not None and str(source_event_id) != '':
                return None, str(source_event_id)
            return None, None

        # 兼容旧事件对象：未知事件类型时只沿用原有的 msg_id 被动回复。
        if event_type is None or event_type in qqMessageEventTypes:
            source_msg_id = extend_data.get('reply_msg_id', None)
            if source_msg_id is not None and str(source_msg_id) != '':
                return str(source_msg_id), None
        return None, None

    def _prepare_qq_passive_message(
        target_event,
        api_obj,
        chat_type,
        chat_id,
        msg_id,
        event_id
    ):
        api_obj.data.msg_id = None if msg_id is None else str(msg_id)
        api_obj.data.event_id = None if event_id is None else str(event_id)
        if msg_id is not None and chat_type in ['qq_group', 'qq_private']:
            max_seq = 4 if chat_type == 'qq_private' else 5
            msg_seq = get_msgid(
                event_action._get_reply_seq_key(target_event, chat_type, chat_id, msg_id),
                max_seq=max_seq
            )
            if msg_seq == 0:
                error = 'passive reply sequence cache is full'
            elif msg_seq is None:
                error = 'passive reply count exceeded'
            else:
                api_obj.data.msg_seq = msg_seq
                return None
            res_data = event_action._make_local_result(chat_type, chat_id, 'send', error)
            res_data['data']['reply_msg_id'] = str(msg_id)
            return res_data
        if event_id is not None and chat_type in ['qq_group', 'qq_private']:
            max_count = 4 if chat_type == 'qq_private' else 5
            ttl = 3600.0 if chat_type == 'qq_private' else 300.0
            reply_count = use_eventid(
                event_action._get_reply_seq_key(target_event, chat_type, chat_id, event_id),
                max_count=max_count,
                ttl=ttl
            )
            if reply_count == 0:
                error = 'passive event reply cache is full'
            elif reply_count is None:
                error = 'passive event reply count exceeded'
            else:
                return None
            res_data = event_action._make_local_result(chat_type, chat_id, 'send', error)
            res_data['data']['reply_event_id'] = str(event_id)
            return res_data
        return None

    def _make_local_result(chat_type, chat_id, operation, error, message_id=None):
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['data'].update({
            'chat_type': str(chat_type),
            'chat_id': None if chat_id is None else str(chat_id),
            'operation': str(operation),
            'message_id': None if message_id is None else str(message_id),
            'http_status': None,
            'error_code': None,
            'error': str(error),
            'response': None
        })
        return res_data

    def _get_api_error_code(raw_obj):
        if type(raw_obj) is not dict:
            return None
        api_code = raw_obj.get('err_code', None)
        if api_code is None:
            api_code = raw_obj.get('code', None)
        if isinstance(api_code, str):
            try:
                api_code = int(api_code.strip())
            except (TypeError, ValueError):
                pass
        return api_code

    def _is_api_async_accepted(operation, http_status, api_code):
        return (
            operation == 'send'
            and http_status in [201, 202]
            and api_code in qqAsyncAcceptedCodes
        )

    def _make_api_result(
        target_event,
        api_obj,
        chat_type,
        chat_id,
        operation,
        fallback_message_id=None
    ):
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        raw_obj = init_api_json(api_obj.res)
        api_code = event_action._get_api_error_code(raw_obj)
        if operation == 'delete' and chat_type in ['qq_group', 'qq_private']:
            # QQ 群/C2C 撤回文档明确以 HTTP 200 表示成功，响应体可为空。
            flag_http_success = api_obj.res_code == 200
        else:
            flag_http_success = (
                api_obj.res_code is not None
                and 200 <= api_obj.res_code < 300
            )
        flag_async_accepted = event_action._is_api_async_accepted(
            operation,
            api_obj.res_code,
            api_code
        )
        flag_success = flag_http_success and (
            api_code in [None, 0]
            or flag_async_accepted
        )
        message_id = fallback_message_id
        timestamp = None
        error_message = None
        if type(raw_obj) is dict:
            message_id = raw_obj.get('id', message_id)
            timestamp = raw_obj.get('timestamp', None)
            error_message = raw_obj.get('message', raw_obj.get('msg', None))
            if type(raw_obj.get('data', None)) is dict:
                message_id = raw_obj['data'].get('id', message_id)
                timestamp = raw_obj['data'].get('timestamp', timestamp)
        # 错误或异步审核响应中的 id 可能是请求/追踪标识，不得冒充消息 ID。
        if flag_async_accepted:
            message_id = None
        elif not flag_success:
            if operation == 'send':
                message_id = None
            elif fallback_message_id is not None:
                message_id = fallback_message_id
        res_data['active'] = flag_success
        res_data['data'].update({
            'chat_type': str(chat_type),
            'chat_id': None if chat_id is None else str(chat_id),
            'operation': str(operation),
            'message_id': None if message_id is None else str(message_id),
            'timestamp': timestamp,
            'http_status': api_obj.res_code,
            'error_code': api_code,
            'error': None if flag_success else error_message,
            'pending_review': flag_async_accepted,
            'response': raw_obj if raw_obj is not None else api_obj.res
        })
        if flag_success and operation == 'send' and message_id is not None:
            _register_sent_message(
                target_event.bot_info.hash,
                chat_type,
                chat_id,
                message_id,
                timestamp=timestamp
            )
        return res_data

    def _get_qq_passive_reply_info(msg_id, event_id):
        if event_id is not None:
            return 'event_id', str(event_id)
        if msg_id is not None:
            return 'msg_id', str(msg_id)
        return None, None

    def _clear_qq_passive_message(api_obj):
        for data_key in ['msg_id', 'event_id', 'msg_seq']:
            if hasattr(api_obj.data, data_key):
                setattr(api_obj.data, data_key, None)

    def _disable_qq_passive_reply(target_event, chat_type, chat_id):
        target_data = getattr(target_event, 'data', None)
        extend_data = getattr(target_data, 'extend', None)
        if isinstance(extend_data, dict):
            extend_data['qq_passive_reply_disabled'] = {
                'chat_type': str(chat_type),
                'chat_id': str(chat_id)
            }

    def _should_fallback_qq_passive(passive_result, msg_id, event_id):
        if passive_result.get('active', False):
            return False
        http_status = passive_result.get('data', {}).get('http_status', None)
        if (
            type(http_status) is not int
            or http_status < 400
            or http_status >= 500
            or http_status == 429
        ):
            return False
        reply_type, _ = event_action._get_qq_passive_reply_info(msg_id, event_id)
        if reply_type is None:
            return False
        error_code = passive_result.get('data', {}).get('error_code', None)
        return error_code in qqPassiveFallbackErrorCodes[reply_type]

    def _retry_qq_message_as_active(
        target_event,
        api_obj,
        chat_type,
        chat_id,
        msg_id,
        event_id,
        passive_result,
        reason
    ):
        reply_type, reply_id = event_action._get_qq_passive_reply_info(
            msg_id,
            event_id
        )
        event_action._clear_qq_passive_message(api_obj)
        event_action._disable_qq_passive_reply(target_event, chat_type, chat_id)
        api_obj.do_api()
        active_result = event_action._make_api_result(
            target_event,
            api_obj,
            chat_type,
            chat_id,
            'send'
        )
        active_result['data']['passive_fallback'] = {
            'attempted': True,
            'reply_type': reply_type,
            'reply_id': reply_id,
            'reason': str(reason),
            'passive_result': copy.deepcopy(passive_result)
        }
        return active_result

    def _send_qq_api(
        target_event,
        api_obj,
        chat_type,
        chat_id,
        msg_id,
        event_id,
        allow_active_fallback=False
    ):
        passive_error = event_action._prepare_qq_passive_message(
            target_event,
            api_obj,
            chat_type,
            chat_id,
            msg_id,
            event_id
        )
        if passive_error is not None:
            local_error = passive_error.get('data', {}).get('error', None)
            if (
                allow_active_fallback
                and local_error in qqLocalPassiveFallbackErrors
            ):
                return event_action._retry_qq_message_as_active(
                    target_event,
                    api_obj,
                    chat_type,
                    chat_id,
                    msg_id,
                    event_id,
                    passive_error,
                    'local_passive_reply_count_exceeded'
                )
            return passive_error

        api_obj.do_api()
        passive_result = event_action._make_api_result(
            target_event,
            api_obj,
            chat_type,
            chat_id,
            'send'
        )
        if (
            allow_active_fallback
            and event_action._should_fallback_qq_passive(
                passive_result,
                msg_id,
                event_id
            )
        ):
            return event_action._retry_qq_message_as_active(
                target_event,
                api_obj,
                chat_type,
                chat_id,
                msg_id,
                event_id,
                passive_result,
                'platform_rejected_passive_reply'
            )
        return passive_result

    def _merge_send_results(chat_type, chat_id, results):
        if len(results) == 0:
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'message contains no supported content'
            )
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['active'] = all(result.get('active', False) for result in results)
        message_ids = [
            result['data']['message_id']
            for result in results
            if (
                result.get('active', False)
                and result.get('data', {}).get('operation', None) == 'send'
                and result.get('data', {}).get('message_id', None) is not None
            )
        ]
        errors = [
            result.get('data', {}).get('error')
            for result in results
            if (
                not result.get('active', False)
                and result.get('data', {}).get('error') is not None
            )
        ]
        passive_fallbacks = [
            result.get('data', {}).get('passive_fallback')
            for result in results
            if result.get('data', {}).get('passive_fallback') is not None
        ]
        res_data['data'].update({
            'chat_type': str(chat_type),
            'chat_id': None if chat_id is None else str(chat_id),
            'operation': 'send',
            'message_id': message_ids[0] if len(message_ids) == 1 else None,
            'message_ids': message_ids,
            'partial': any(result.get('active', False) for result in results) and not res_data['active'],
            'error': errors[0] if len(errors) > 0 else None,
            'errors': errors,
            'passive_fallbacks': passive_fallbacks,
            'results': results
        })
        return res_data

    def _validate_keyboard_permissions(keyboard, chat_type):
        if keyboard is None:
            return None
        if type(keyboard) is not dict:
            return 'keyboard must be a dict'
        keyboard_content = keyboard.get('content', None)
        if keyboard_content is None:
            return None
        if type(keyboard_content) is not dict:
            return 'keyboard content must be a dict'
        rows = keyboard_content.get('rows', [])
        if type(rows) is not list:
            return 'keyboard rows must be a list'
        for row in rows:
            if type(row) is not dict or type(row.get('buttons', [])) is not list:
                return 'keyboard row buttons must be a list'
            for button in row.get('buttons', []):
                if type(button) is not dict:
                    return 'keyboard button must be a dict'
                action = button.get('action', None)
                if action is None:
                    continue
                if type(action) is not dict:
                    return 'keyboard action must be a dict'
                permission = action.get('permission', None)
                if permission is None:
                    continue
                if type(permission) is not dict:
                    return 'keyboard permission must be a dict'
                permission_type = permission.get('type', None)
                if (
                    permission_type is not None
                    and (
                        type(permission_type) is not int
                        or permission_type not in [0, 1, 2]
                    )
                ):
                    return 'keyboard permission type must be 0, 1 or 2'
                for data_key in ['specify_user_ids', 'specify_role_ids']:
                    data_value = permission.get(data_key, None)
                    if data_value is not None and type(data_value) is not list:
                        return 'keyboard permission %s must be a list' % data_key
                if (
                    chat_type in ['qq_group', 'qq_private']
                    and permission.get('specify_role_ids', None)
                ):
                    return 'specify_role_ids is only available for guild channels'
        return None

    # 按首个有效消息段确定图文方向，并将每个富媒体与相邻文字分组
    def _get_message_send_chunks(
        message,
        media_types,
        allow_at_all=True
    ):
        media_types = tuple(media_types)
        message_items = []
        for message_this in message.data:
            if isinstance(message_this, OlivOS.messageAPI.PARA.text):
                text_content = message_this.OP()
                # 空文字段不应改变整条消息按图片开头还是按文字开头分组。
                if text_content != '':
                    message_items.append(('text', text_content))
            elif isinstance(message_this, OlivOS.messageAPI.PARA.at):
                at_content = markdown_tag.at_para(
                    message_this,
                    allow_at_all=allow_at_all
                )
                if at_content != '':
                    message_items.append(('text', at_content))
            elif isinstance(message_this, media_types):
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

    def _get_qq_message_send_chunks(message, flag_direct=False):
        media_types = (
            OlivOS.messageAPI.PARA.image,
            OlivOS.messageAPI.PARA.video,
            OlivOS.messageAPI.PARA.record,
            OlivOS.messageAPI.PARA.music,
            OlivOS.messageAPI.PARA.file
        )
        bindable_types = (
            OlivOS.messageAPI.PARA.text,
            OlivOS.messageAPI.PARA.at,
            OlivOS.messageAPI.PARA.image
        )
        message_chunks = []
        image_message_buffer = []

        def flush_image_message_buffer():
            if len(image_message_buffer) == 0:
                return
            image_message = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                image_message_buffer.copy()
            )
            message_chunks.extend(event_action._get_message_send_chunks(
                image_message,
                [OlivOS.messageAPI.PARA.image],
                allow_at_all=False
            ))
            image_message_buffer.clear()

        for message_this in message.data:
            if isinstance(message_this, bindable_types):
                image_message_buffer.append(message_this)
            elif isinstance(message_this, media_types):
                flush_image_message_buffer()
                message_chunks.append(('', message_this))
        flush_image_message_buffer()
        return message_chunks

    def send_qq_msg(
        target_event,
        chat_id,
        message,
        reply_msg_id=None,
        flag_direct=False,
        quote_msg_id=None,
        event_id=None
    ):
        chat_type = 'qq_private' if flag_direct else 'qq_group'
        if chat_id is None or str(chat_id) == '':
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'chat_id is required'
            )
        if reply_msg_id is not None and event_id is not None:
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'msg_id and event_id are mutually exclusive'
            )
        allow_active_fallback = reply_msg_id is None and event_id is None
        msg_id, event_id = event_action._resolve_qq_passive_ids(
            target_event,
            chat_type,
            chat_id,
            msg_id=reply_msg_id,
            event_id=event_id
        )
        allow_active_fallback = (
            allow_active_fallback
            and (msg_id is not None or event_id is not None)
        )
        send_results = []
        if quote_msg_id is None:
            quote_msg_id = event_action._get_message_reference_id(message)

        def send_payload(text_content, file_info=None, bind_content=True):
            nonlocal allow_active_fallback, event_id, msg_id, quote_msg_id
            result = event_action._send_qq_payload(
                target_event,
                chat_id,
                text_content,
                msg_id,
                flag_direct=flag_direct,
                file_info=file_info,
                bind_content=bind_content,
                quote_msg_id=quote_msg_id,
                event_id=event_id,
                allow_active_fallback=allow_active_fallback
            )
            send_results.append(result)
            if result.get('data', {}).get('passive_fallback') is not None:
                msg_id = None
                event_id = None
                allow_active_fallback = False
            if result.get('active', False):
                quote_msg_id = None
            return result

        for text_content, message_this in event_action._get_qq_message_send_chunks(
            message,
            flag_direct=flag_direct
        ):
            if message_this is None:
                result = send_payload(text_content)
                if not result.get('active', False):
                    return event_action._merge_send_results(
                        chat_type,
                        chat_id,
                        send_results
                    )
                continue
            if isinstance(message_this, OlivOS.messageAPI.PARA.image):
                type_path = 'images'
            elif isinstance(message_this, OlivOS.messageAPI.PARA.video):
                type_path = 'videos'
            elif isinstance(message_this, OlivOS.messageAPI.PARA.record):
                type_path = 'audios'
            elif isinstance(message_this, OlivOS.messageAPI.PARA.music):
                type_path = 'audios'
            elif isinstance(message_this, OlivOS.messageAPI.PARA.file):
                type_path = 'files'
            else:
                continue
            bind_content = isinstance(message_this, OlivOS.messageAPI.PARA.image)
            if not bind_content and text_content != '':
                result = send_payload(text_content)
                if not result.get('active', False):
                    return event_action._merge_send_results(
                        chat_type,
                        chat_id,
                        send_results
                    )
                text_content = ''
            resource_url = event_action._get_message_resource(message_this)
            if resource_url is None:
                send_results.append(event_action._make_local_result(
                    chat_type,
                    chat_id,
                    'send',
                    'message resource is empty'
                ))
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
            file_info = event_action.setResourceUploadFast(
                target_event,
                resource_url,
                chat_id,
                type_path=type_path,
                type_chat='qq_users' if flag_direct else 'qq_groups'
            )
            if file_info is None:
                send_results.append(event_action._make_local_result(
                    chat_type,
                    chat_id,
                    'send',
                    'message resource upload failed'
                ))
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
            result = send_payload(
                text_content,
                file_info=file_info,
                bind_content=bind_content
            )
            if not result.get('active', False):
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
        return event_action._merge_send_results(chat_type, chat_id, send_results)

    def create_markdown_message(
        target_event,
        chat_type,
        chat_id,
        markdown,
        msg_id=None,
        event_id=None,
        keyboard=None,
        quote_msg_id=None
    ):
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['data']['chat_type'] = str(chat_type)
        res_data['data']['chat_id'] = None if chat_id is None else str(chat_id)

        if chat_type not in ['qq_group', 'qq_private', 'guild_channel', 'guild_private']:
            res_data['data']['error'] = 'unsupported chat_type'
            return res_data
        if chat_id is None or str(chat_id) == '':
            res_data['data']['error'] = 'chat_id is required'
            return res_data
        if type(markdown) is not dict or len(markdown) == 0:
            res_data['data']['error'] = 'markdown must be a non-empty dict'
            return res_data

        flag_content = (
            type(markdown.get('content', None)) is str
            and markdown.get('content', '') != ''
        )
        flag_template = (
            type(markdown.get('custom_template_id', None)) is str
            and markdown.get('custom_template_id', '') != ''
        )
        if flag_content == flag_template:
            res_data['data']['error'] = 'markdown requires either content or custom_template_id'
            return res_data
        if 'params' in markdown and type(markdown['params']) is not list:
            res_data['data']['error'] = 'markdown params must be a list'
            return res_data
        keyboard_error = event_action._validate_keyboard_permissions(keyboard, chat_type)
        if keyboard_error is not None:
            res_data['data']['error'] = keyboard_error
            return res_data
        if msg_id is not None and event_id is not None:
            res_data['data']['error'] = 'msg_id and event_id are mutually exclusive'
            return res_data

        allow_active_fallback = msg_id is None and event_id is None
        if chat_type in ['qq_group', 'qq_private']:
            msg_id, event_id = event_action._resolve_qq_passive_ids(
                target_event,
                chat_type,
                chat_id,
                msg_id=msg_id,
                event_id=event_id
            )
            allow_active_fallback = (
                allow_active_fallback
                and (msg_id is not None or event_id is not None)
            )
        else:
            allow_active_fallback = False

        this_msg = None
        if chat_type == 'qq_group':
            this_msg = API.sendQQMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.group_openid = str(chat_id)
            this_msg.data.msg_type = 2
        elif chat_type == 'qq_private':
            this_msg = API.sendQQDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.openid = str(chat_id)
            this_msg.data.msg_type = 2
        elif chat_type == 'guild_channel':
            this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.channel_id = str(chat_id)
        elif chat_type == 'guild_private':
            this_msg = API.sendDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.guild_id = str(chat_id)

        this_msg.data.markdown = markdown
        this_msg.data.keyboard = keyboard
        if quote_msg_id is not None and str(quote_msg_id) != '':
            this_msg.data.message_reference = {'message_id': str(quote_msg_id)}
        res_data = event_action._send_qq_api(
            target_event,
            this_msg,
            chat_type,
            chat_id,
            msg_id,
            event_id,
            allow_active_fallback=allow_active_fallback
        )

        if not res_data['active'] and target_event.log_func is not None:
            response_text = str(this_msg.res) if this_msg.res is not None else 'no response'
            if len(response_text) > 1000:
                response_text = response_text[:1000] + '...'
            response_code = 'n/a' if this_msg.res_code is None else str(this_msg.res_code)
            try:
                target_event.log_func(
                    3,
                    (
                        'OlivOS qqGuildv2SDK Markdown message response: '
                        f'HTTP {response_code} {response_text}'
                    ),
                    [
                        (target_event.getBotIDStr(), 'default'),
                        (modelName, 'default'),
                        ('create_markdown_message', 'callback')
                    ]
                )
            except Exception:
                traceback.print_exc()
        return res_data

    def _send_qq_payload(
        target_event,
        chat_id,
        content,
        msg_id,
        flag_direct=False,
        file_info=None,
        bind_content=True,
        quote_msg_id=None,
        event_id=None,
        allow_active_fallback=False
    ):
        chat_type = 'qq_private' if flag_direct else 'qq_group'
        if flag_direct:
            this_msg = API.sendQQDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.openid = str(chat_id)
        else:
            this_msg = API.sendQQMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.group_openid = str(chat_id)
        this_msg.data.content = content if file_info is None or bind_content else None
        if file_info is None:
            this_msg.data.msg_type = 0
        else:
            # 上传接口返回的 file_info 必须包装到 media 对象中，再调用消息发送接口。
            this_msg.data.msg_type = 7
            this_msg.data.media = {'file_info': file_info}
        if quote_msg_id is not None and str(quote_msg_id) != '':
            this_msg.data.message_reference = {'message_id': str(quote_msg_id)}
        res_data = event_action._send_qq_api(
            target_event,
            this_msg,
            chat_type,
            chat_id,
            msg_id,
            event_id,
            allow_active_fallback=allow_active_fallback
        )
        fallback_used = res_data.get('data', {}).get('passive_fallback') is not None
        event_action._log_qq_send_result(
            target_event,
            this_msg,
            None if fallback_used else msg_id,
            flag_direct=flag_direct,
            event_id=None if fallback_used else event_id
        )
        return res_data

    def _log_qq_send_result(target_event, api_obj, msg_id, flag_direct=False, event_id=None):
        if target_event.log_func is None:
            return
        res_obj = init_api_json(api_obj.res)
        api_code = event_action._get_api_error_code(res_obj)
        flag_success = (
            api_obj.res_code is not None
            and 200 <= api_obj.res_code < 300
            and (
                api_code in [None, 0]
                or event_action._is_api_async_accepted(
                    'send',
                    api_obj.res_code,
                    api_code
                )
            )
        )
        # 被动回复沿用现有简洁日志；主动消息额外记录平台结果，便于排查权限和审核问题。
        if flag_success and (msg_id is not None or event_id is not None):
            return
        send_mode = 'active' if msg_id is None and event_id is None else 'reply'
        chat_type = 'direct' if flag_direct else 'group'
        res_text = str(api_obj.res) if api_obj.res is not None else 'no response'
        if len(res_text) > 1000:
            res_text = res_text[:1000] + '...'
        res_code_text = 'n/a' if api_obj.res_code is None else str(api_obj.res_code)
        try:
            target_event.log_func(
                2 if flag_success else 3,
                'OlivOS qqGuildv2SDK QQ %s %s message response: HTTP %s %s' % (
                    chat_type,
                    send_mode,
                    res_code_text,
                    res_text
                ),
                [
                    (target_event.getBotIDStr(), 'default'),
                    (modelName, 'default'),
                    ('send_qq_msg', 'callback')
                ]
            )
        except Exception:
            traceback.print_exc()

    def send_msg(
        target_event,
        chat_id,
        message,
        reply_msg_id=None,
        flag_direct=False,
        quote_msg_id=None
    ):
        # 频道图片沿用 QQ 图文的双向分组规则。
        chat_type = 'guild_private' if flag_direct else 'guild_channel'
        if chat_id is None or str(chat_id) == '':
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'chat_id is required'
            )
        send_results = []
        if quote_msg_id is None:
            quote_msg_id = event_action._get_message_reference_id(message)

        def send_payload(text_content, image_data=None):
            nonlocal quote_msg_id
            result = event_action._send_channel_payload(
                target_event,
                chat_id,
                text_content,
                reply_msg_id,
                flag_direct=flag_direct,
                image_data=image_data,
                quote_msg_id=quote_msg_id
            )
            send_results.append(result)
            if result.get('active', False):
                quote_msg_id = None
            return result

        for text_content, message_this in event_action._get_message_send_chunks(
            message,
            [OlivOS.messageAPI.PARA.image],
            allow_at_all=not flag_direct
        ):
            if message_this is None:
                result = send_payload(text_content)
                if not result.get('active', False):
                    return event_action._merge_send_results(
                        chat_type,
                        chat_id,
                        send_results
                    )
                continue
            resource_url = event_action._get_message_resource(message_this)
            if resource_url is None:
                send_results.append(event_action._make_local_result(
                    chat_type,
                    chat_id,
                    'send',
                    'message resource is empty'
                ))
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
            image_data = event_action._get_channel_image_data(resource_url)
            if image_data is None:
                send_results.append(event_action._make_local_result(
                    chat_type,
                    chat_id,
                    'send',
                    'message resource load failed'
                ))
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
            result = send_payload(text_content, image_data=image_data)
            if not result.get('active', False):
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
        return event_action._merge_send_results(chat_type, chat_id, send_results)

    def _send_channel_payload(
        target_event,
        chat_id,
        content,
        msg_id,
        flag_direct=False,
        image_data=None,
        quote_msg_id=None
    ):
        chat_type = 'guild_private' if flag_direct else 'guild_channel'
        if flag_direct:
            this_msg = API.sendDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.guild_id = str(chat_id)
        else:
            this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.channel_id = str(chat_id)
        this_msg.data.content = content
        this_msg.data.msg_id = None if msg_id is None else str(msg_id)
        if quote_msg_id is not None and str(quote_msg_id) != '':
            this_msg.data.message_reference = {'message_id': str(quote_msg_id)}
        if type(image_data) is dict:
            if image_data.get('image', None) is not None:
                this_msg.data.image = image_data['image']
            elif image_data.get('file_image', None) is not None:
                this_msg.data.file_image = image_data['file_image']
        this_msg.do_api()
        return event_action._make_api_result(
            target_event,
            this_msg,
            chat_type,
            chat_id,
            'send'
        )

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

    def delete_message(target_event, chat_type, chat_id, message_id):
        if chat_type not in ['qq_group', 'qq_private', 'guild_channel', 'guild_private']:
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'delete',
                'unsupported chat_type',
                message_id=message_id
            )
        if chat_id is None or str(chat_id) == '':
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'delete',
                'chat_id is required',
                message_id=message_id
            )
        if message_id is None or str(message_id) == '':
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'delete',
                'message_id is required'
            )

        if chat_type in ['qq_group', 'qq_private']:
            delete_error = _check_sent_message_for_delete(
                target_event.bot_info.hash,
                chat_type,
                chat_id,
                message_id
            )
            if delete_error is not None:
                return event_action._make_local_result(
                    chat_type,
                    chat_id,
                    'delete',
                    delete_error,
                    message_id=message_id
                )
            if not _acquire_delete_rate(target_event.bot_info.hash):
                return event_action._make_local_result(
                    chat_type,
                    chat_id,
                    'delete',
                    'message recall rate limit exceeded',
                    message_id=message_id
                )

        this_msg = None
        if chat_type == 'qq_private':
            this_msg = API.deleteQQDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.openid = str(chat_id)
        elif chat_type == 'qq_group':
            this_msg = API.deleteQQMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.group_openid = str(chat_id)
        elif chat_type == 'guild_private':
            this_msg = API.deleteDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.guild_id = str(chat_id)
        else:
            this_msg = API.deleteMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.channel_id = str(chat_id)
        this_msg.metadata.message_id = str(message_id)
        this_msg.do_api('DELETE')
        res_data = event_action._make_api_result(
            target_event,
            this_msg,
            chat_type,
            chat_id,
            'delete',
            fallback_message_id=message_id
        )
        if res_data['active']:
            _forget_sent_message(
                target_event.bot_info.hash,
                chat_type,
                chat_id,
                message_id
            )
        if not res_data['active'] and target_event.log_func is not None:
            try:
                target_event.log_func(
                    3,
                    'OlivOS qqGuildv2SDK delete message response: HTTP %s %s' % (
                        str(this_msg.res_code),
                        str(this_msg.res)
                    ),
                    [
                        (target_event.getBotIDStr(), 'default'),
                        (modelName, 'default'),
                        ('delete_msg', 'callback')
                    ]
                )
            except Exception:
                traceback.print_exc()
        return res_data

    # 通过 OlivOS 既有 delete_msg 接口自动选择 QQ/频道撤回路由
    def delete_msg(target_event, message_id):
        target_data = target_event.data
        if target_data is None or not hasattr(target_data, 'extend'):
            return event_action._make_local_result(
                'unknown',
                None,
                'delete',
                'current event has no chat context',
                message_id=message_id
            )
        extend_data = target_data.extend
        flag_from_qq = extend_data.get('flag_from_qq', False)
        flag_from_direct = extend_data.get('flag_from_direct', False)
        if flag_from_qq and flag_from_direct:
            chat_type = 'qq_private'
            chat_id = target_data.user_id
        elif flag_from_qq:
            chat_type = 'qq_group'
            chat_id = target_data.group_id
        elif flag_from_direct:
            chat_type = 'guild_private'
            chat_id = extend_data.get('host_group_id', None)
            if chat_id is None:
                chat_id = getattr(target_data, 'group_id', None)
        else:
            chat_type = 'guild_channel'
            chat_id = getattr(target_data, 'group_id', None)
        return event_action.delete_message(
            target_event,
            chat_type,
            chat_id,
            message_id
        )

    # 富媒体优先使用 URL；自定义音乐使用 audio 字段中的实际音频资源。
    def _get_message_resource(message_para):
        if message_para.data is None:
            return None
        if isinstance(message_para, OlivOS.messageAPI.PARA.music):
            resource_keys = ['audio']
        else:
            resource_keys = ['path', 'url', 'file']
        for data_key in resource_keys:
            data_value = message_para.data.get(data_key, None)
            if data_value is None:
                continue
            data_value = str(data_value)
            if data_value not in ['', 'None']:
                return data_value
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
        type_path: str,
        type_chat: str
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


class inde_interface(OlivOS.API.inde_interface_T):
    @OlivOS.API.Event.callbackLogger(
        'qqGuildv2:send_message',
        ['chat_type', 'chat_id', 'message_ids']
    )
    def __send_message(
        target_event,
        chat_type,
        chat_id,
        message,
        reply_msg_id=None,
        quote_msg_id=None,
        flag_log=True,
        event_id=None
    ):
        if chat_type not in [
            'qq_group',
            'qq_private',
            'guild_channel',
            'guild_private'
        ]:
            return OlivOS.qqGuildv2SDK.event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'unsupported chat_type'
            )
        message_obj = OlivOS.qqGuildv2SDK.event_action._normalize_outgoing_message(
            target_event,
            message
        )
        if not message_obj.active:
            return OlivOS.qqGuildv2SDK.event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'message parse failed'
            )
        if chat_type in ['qq_group', 'qq_private']:
            return OlivOS.qqGuildv2SDK.event_action.send_qq_msg(
                target_event,
                chat_id,
                message_obj,
                reply_msg_id=reply_msg_id,
                flag_direct=chat_type == 'qq_private',
                quote_msg_id=quote_msg_id,
                event_id=event_id
            )
        return OlivOS.qqGuildv2SDK.event_action.send_msg(
            target_event,
            chat_id,
            message_obj,
            reply_msg_id=reply_msg_id,
            flag_direct=chat_type == 'guild_private',
            quote_msg_id=quote_msg_id
        )

    def send_message(
        self,
        chat_type,
        chat_id,
        message,
        reply_msg_id=None,
        quote_msg_id=None,
        flag_log=True,
        remote=False,
        event_id=None
    ):
        if remote:
            return None
        return inde_interface.__send_message(
            self.event,
            chat_type,
            chat_id,
            message,
            reply_msg_id=reply_msg_id,
            quote_msg_id=quote_msg_id,
            flag_log=flag_log,
            event_id=event_id
        )

    @OlivOS.API.Event.callbackLogger(
        'qqGuildv2:send_qq_message',
        ['chat_type', 'chat_id', 'message_ids']
    )
    def __send_qq_message(
        target_event,
        chat_type,
        chat_id,
        message,
        reply_msg_id=None,
        quote_msg_id=None,
        flag_log=True,
        event_id=None
    ):
        if chat_type not in ['qq_group', 'qq_private']:
            return OlivOS.qqGuildv2SDK.event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'send_qq_message only supports qq_group and qq_private'
            )
        message_obj = OlivOS.qqGuildv2SDK.event_action._normalize_outgoing_message(
            target_event,
            message
        )
        if not message_obj.active:
            return OlivOS.qqGuildv2SDK.event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'message parse failed'
            )
        return OlivOS.qqGuildv2SDK.event_action.send_qq_msg(
            target_event,
            chat_id,
            message_obj,
            reply_msg_id=reply_msg_id,
            flag_direct=chat_type == 'qq_private',
            quote_msg_id=quote_msg_id,
            event_id=event_id
        )

    def send_qq_message(
        self,
        chat_type,
        chat_id,
        message,
        reply_msg_id=None,
        quote_msg_id=None,
        flag_log=True,
        remote=False,
        event_id=None
    ):
        if remote:
            return None
        return inde_interface.__send_qq_message(
            self.event,
            chat_type,
            chat_id,
            message,
            reply_msg_id=reply_msg_id,
            quote_msg_id=quote_msg_id,
            flag_log=flag_log,
            event_id=event_id
        )

    @OlivOS.API.Event.callbackLogger(
        'qqGuildv2:delete_message',
        ['chat_type', 'chat_id', 'message_id', 'http_status']
    )
    def __delete_message(
        target_event,
        chat_type,
        chat_id,
        message_id,
        flag_log=True
    ):
        return OlivOS.qqGuildv2SDK.event_action.delete_message(
            target_event,
            chat_type,
            chat_id,
            message_id
        )

    def delete_message(
        self,
        chat_type,
        chat_id,
        message_id,
        flag_log=True,
        remote=False
    ):
        if remote:
            return None
        return inde_interface.__delete_message(
            self.event,
            chat_type,
            chat_id,
            message_id,
            flag_log=flag_log
        )

    @OlivOS.API.Event.callbackLogger(
        'qqGuildv2:create_markdown_message',
        ['chat_type', 'chat_id', 'message_id']
    )
    def __create_markdown_message(
        target_event,
        chat_type,
        chat_id,
        markdown,
        msg_id=None,
        event_id=None,
        keyboard=None,
        quote_msg_id=None,
        flag_log=True
    ):
        return OlivOS.qqGuildv2SDK.event_action.create_markdown_message(
            target_event=target_event,
            chat_type=chat_type,
            chat_id=chat_id,
            markdown=markdown,
            msg_id=msg_id,
            event_id=event_id,
            keyboard=keyboard,
            quote_msg_id=quote_msg_id
        )

    def create_markdown_message(
        self,
        chat_type,
        chat_id,
        markdown,
        msg_id=None,
        event_id=None,
        keyboard=None,
        quote_msg_id=None,
        flag_log=True,
        remote=False
    ):
        res_data = None
        if remote:
            pass
        else:
            res_data = inde_interface.__create_markdown_message(
                self.event,
                chat_type,
                chat_id,
                markdown,
                msg_id=msg_id,
                event_id=event_id,
                keyboard=keyboard,
                quote_msg_id=quote_msg_id,
                flag_log=flag_log
            )
        return res_data


class markdown_tag:
    def at_para(message_para, allow_at_all=True):
        if not isinstance(message_para, OlivOS.messageAPI.PARA.at):
            return ''
        user_id = str(message_para.data.get('id', ''))
        if user_id == 'all':
            if allow_at_all:
                return '<qqbot-at-everyone />'
            return ''
        if user_id == '':
            return ''
        return markdown_tag.at_user(user_id)

    def at_user(user_id):
        return '<qqbot-at-user id="%s" />' % str(user_id)

    def cmd_enter(text):
        return '<qqbot-cmd-enter text="%s" />' % parse.quote(str(text), safe='')

    def cmd_input(text, show=None, reference=False):
        res = '<qqbot-cmd-input text="%s"' % parse.quote(str(text), safe='')
        if show is not None:
            res += ' show="%s"' % parse.quote(str(show), safe='')
        res += ' reference="%s" />' % ('true' if reference else 'false')
        return res


def get_msgid(key: str, max_seq=None):
    """线程安全地分配被动回复序号；0 表示缓存已满，None 表示次数超限。"""
    key = str(key)
    now = time.monotonic()
    with sdkMsgidinfoLock:
        # dict 保持插入顺序；created_at 不随回复更新，因此只需从最旧项开始清理。
        while len(sdkMsgidinfo) > 0:
            oldest_key = next(iter(sdkMsgidinfo))
            oldest_data = sdkMsgidinfo[oldest_key]
            if now - oldest_data['created_at'] < sdkMsgidinfoTTL:
                break
            sdkMsgidinfo.pop(oldest_key, None)

        cache_data = sdkMsgidinfo.get(key)
        # 不逐出仍有效的旧 key，避免同一 msg_id 从 seq=1 重新开始而绕过上限。
        if cache_data is None and len(sdkMsgidinfo) >= sdkMsgidinfoMaxSize:
            return 0
        next_seq = 1 if cache_data is None else cache_data['seq'] + 1
        if max_seq is not None and next_seq > max_seq:
            return None
        sdkMsgidinfo[key] = {
            'seq': next_seq,
            'created_at': now if cache_data is None else cache_data['created_at'],
            'updated_at': now
        }
        return next_seq


def use_eventid(key: str, max_count: int, ttl: float):
    """登记 event_id 被动回复次数；event_id 不发送 msg_seq。"""
    key = str(key)
    now = time.monotonic()
    with sdkEventidinfoLock:
        expired_keys = [
            cache_key
            for cache_key, cache_data in sdkEventidinfo.items()
            if now - cache_data['created_at'] >= cache_data['ttl']
        ]
        for cache_key in expired_keys:
            sdkEventidinfo.pop(cache_key, None)

        cache_data = sdkEventidinfo.get(key)
        if cache_data is None and len(sdkEventidinfo) >= sdkEventidinfoMaxSize:
            return 0
        next_count = 1 if cache_data is None else cache_data['count'] + 1
        if next_count > max_count:
            return None
        sdkEventidinfo[key] = {
            'count': next_count,
            'created_at': now if cache_data is None else cache_data['created_at'],
            'updated_at': now,
            'ttl': float(ttl)
        }
        return next_count


def _register_sent_message(bot_hash, chat_type, chat_id, message_id, timestamp=None):
    """记录本进程发出的消息，用于撤回前的会话和时限校验。"""
    global sdkSentMessageInfoLastCleanup

    if message_id is None:
        return
    now = time.monotonic()
    cache_key = (str(bot_hash), str(chat_type), str(chat_id), str(message_id))
    with sdkSentMessageInfoLock:
        if now - sdkSentMessageInfoLastCleanup >= 60:
            expired_keys = [
                key
                for key, data in sdkSentMessageInfo.items()
                if now - data['created_monotonic'] >= 600
            ]
            for key in expired_keys:
                sdkSentMessageInfo.pop(key, None)
            sdkSentMessageInfoLastCleanup = now
        sdkSentMessageInfo[cache_key] = {
            'created_monotonic': now,
            'timestamp': timestamp
        }
        if len(sdkSentMessageInfo) > sdkSentMessageInfoMaxSize:
            oldest_key = min(
                sdkSentMessageInfo,
                key=lambda key: sdkSentMessageInfo[key]['created_monotonic']
            )
            sdkSentMessageInfo.pop(oldest_key, None)


def _check_sent_message_for_delete(bot_hash, chat_type, chat_id, message_id):
    """仅校验本进程已知消息；重启前发送的未知消息仍交给平台判断。"""
    bot_hash = str(bot_hash)
    chat_type = str(chat_type)
    chat_id = str(chat_id)
    message_id = str(message_id)
    target_key = (bot_hash, chat_type, chat_id, message_id)
    now = time.monotonic()
    with sdkSentMessageInfoLock:
        target_data = sdkSentMessageInfo.get(target_key)
        if target_data is not None:
            if now - target_data['created_monotonic'] > 120:
                return 'message recall window exceeded'
            return None
        for cache_key in sdkSentMessageInfo:
            if cache_key[0] == bot_hash and cache_key[3] == message_id:
                return 'message does not belong to the target chat'
    return None


def _forget_sent_message(bot_hash, chat_type, chat_id, message_id):
    """撤回成功后移除本地归属记录。"""
    cache_key = (
        str(bot_hash),
        str(chat_type),
        str(chat_id),
        str(message_id)
    )
    with sdkSentMessageInfoLock:
        sdkSentMessageInfo.pop(cache_key, None)


def _acquire_delete_rate(bot_hash):
    """遵循 QQ 撤回接口每个机器人 10 QPS 的限制。"""
    bot_hash = str(bot_hash)
    now = time.monotonic()
    with sdkDeleteRateInfoLock:
        history = sdkDeleteRateInfo.setdefault(bot_hash, deque())
        while history and now - history[0] >= 1:
            history.popleft()
        if len(history) >= 10:
            return False
        history.append(now)
        return True


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
