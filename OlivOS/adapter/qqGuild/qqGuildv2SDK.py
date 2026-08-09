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

import base64
import copy
import hashlib
import json
import mimetypes
import os
import re
import threading
import time
import traceback
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from enum import IntEnum
from urllib import parse

import requests as req
from requests_toolbelt import MultipartEncoder

import OlivOS

modelName = 'qqGuildv2SDK'


class intents_T(IntEnum):
    GUILDS = (1 << 0)  # 频道变更
    GUILD_MEMBERS = (1 << 1)  # 频道成员变更
    GUILD_MESSAGES = (1 << 9)  # 消息事件，仅 *私域* 机器人能够设置此 intents。
    GUILD_MESSAGE_REACTIONS = (1 << 10)  # 表情表态事件
    DIRECT_MESSAGE = (1 << 12)  # 私聊消息
    OPEN_FORUMS_EVENT = (1 << 18)  # 开放论坛事件
    AUDIO_OR_LIVE_CHANNEL_MEMBER = (1 << 19)  # 音视频/直播子频道成员进出
    INTERACTION = (1 << 26)  # 互动事件变更(按钮回调等)
    MESSAGE_AUDIT = (1 << 27)  # 消息审核变更
    FORUMS_EVENT = (1 << 28)  # 论坛事件，仅 *私域* 机器人能够设置此 intents。
    AUDIO_ACTION = (1 << 29)  # 语音消息
    PUBLIC_GUILD_MESSAGES = (1 << 30)  # 消息事件，此为公域的频道消息事件
    PUBLIC_QQ_GROUP_MEMBERS = (1 << 24)  # QQ 群成员及机器人进退群事件(实测生效位,官方文档写 1<<15 有误)
    GROUP_AND_C2C_EVENT = (1 << 25)  # QQ 群消息与 C2C 单聊消息事件
    PUBLIC_QQ_MESSAGES = GROUP_AND_C2C_EVENT  # 兼容旧名称


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
    'users_me': '/users/@me',
    'gateway': '/gateway',
    'interactions': '/interactions',
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
sdkTokenRefreshAhead = 60.0  # token 提前刷新窗口(秒),文档:过期前 60s 内可换新,旧 token 仍有效
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
# 富媒体上传 file_info 缓存:同一资源在平台返回的 ttl 内重发时免重复上传。
sdkResourceUploadInfo = {}
sdkResourceUploadInfoLock = threading.Lock()
sdkResourceUploadInfoMaxSize = 2000
sdkResourceUploadTTLMargin = 30.0  # 缓存留出的安全余量,避免拿到临期 file_info
sdkResourceUploadTTLLongTerm = 6 * 86400.0  # 平台 ttl 为 0(长期有效)时的本地缓存时长
sdkResourceUploadDirectMaxSize = 4 * 1024 * 1024  # 本地文件 base64 直传上限,超过走文档的分片上传
sdkResourceUploadMd5_10mSize = 10002432  # 文档规定 md5_10m 校验的字节数(约 10MB)
sdkResourceUploadBlockSize = 5 * 1024 * 1024  # 预上传未返回分块大小时的默认值(文档默认 5MB)
sdkResourceUploadPartTimeout = 120.0  # 单个分片 PUT 的请求超时
sdkResourceUploadPartRetryMax = 3  # 单个分片的最大尝试次数
sdkResourceUploadPartMaxConcurrency = 8  # 分片并发上限,防御平台下发异常并发数

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
# 映射到 OlivOS 标准事件的平台事件
qqGuildMemberEventTypes = {
    'GUILD_MEMBER_ADD',
    'GUILD_MEMBER_REMOVE'
}
qqRecallEventTypes = {
    'MESSAGE_DELETE',
    'PUBLIC_MESSAGE_DELETE',
    'DIRECT_MESSAGE_DELETE'
}
# 对不上 OlivOS 标准事件的平台事件:在 SDK 层解析并记录
# (event_action.get_unhandled_events 可查),不投递到插件层。
qqInternalEventTypes = {
    'GUILD_CREATE', 'GUILD_UPDATE', 'GUILD_DELETE',
    'CHANNEL_CREATE', 'CHANNEL_UPDATE', 'CHANNEL_DELETE',
    'GUILD_MEMBER_UPDATE',
    'MESSAGE_REACTION_ADD', 'MESSAGE_REACTION_REMOVE',
    'MESSAGE_AUDIT_PASS', 'MESSAGE_AUDIT_REJECT',
    'INTERACTION_CREATE',
    'FRIEND_DEL', 'C2C_MSG_REJECT', 'C2C_MSG_RECEIVE',
    'GROUP_MSG_REJECT', 'GROUP_MSG_RECEIVE',
    'SUBSCRIBE_MESSAGE_STATUS',
    'FORUM_THREAD_CREATE', 'FORUM_THREAD_UPDATE', 'FORUM_THREAD_DELETE',
    'FORUM_POST_CREATE', 'FORUM_POST_DELETE',
    'FORUM_REPLY_CREATE', 'FORUM_REPLY_DELETE',
    'FORUM_PUBLISH_AUDIT_RESULT',
    'OPEN_FORUM_THREAD_CREATE', 'OPEN_FORUM_THREAD_UPDATE', 'OPEN_FORUM_THREAD_DELETE',
    'OPEN_FORUM_POST_CREATE', 'OPEN_FORUM_POST_DELETE',
    'OPEN_FORUM_REPLY_CREATE', 'OPEN_FORUM_REPLY_DELETE',
    'AUDIO_START', 'AUDIO_FINISH', 'AUDIO_ON_MIC', 'AUDIO_OFF_MIC',
    'AUDIO_OR_LIVE_CHANNEL_MEMBER_ENTER', 'AUDIO_OR_LIVE_CHANNEL_MEMBER_EXIT'
}
qqDispatchEventTypes = (
    qqMessageEventTypes
    | qqGuildMemberEventTypes
    | qqRecallEventTypes
    | qqInternalEventTypes
    | {
        'FRIEND_ADD',
        'GROUP_ADD_ROBOT',
        'GROUP_DEL_ROBOT',
        'GROUP_MEMBER_ADD',
        'GROUP_MEMBER_REMOVE',
        'READY'
    }
)
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
    'passive reply sequence cache is full',
    'passive reply count exceeded',
    'passive event reply cache is full',
    'passive event reply count exceeded'
}
qqEventDedupeCache = {}
qqEventDedupeLock = threading.Lock()
qqEventDedupeTTL = 120.0
qqEventDedupeMaxSize = 10000
# 消息内容缓存:收到/发出的消息按 message_id 暂存,供 get_msg 取引用文本。
# QQ 群/C2C 无"获取指定消息"官方接口,该缓存是取引用文本的唯一来源;频道可回源官方接口。
sdkRxMessageInfo = {}
sdkRxMessageInfoLock = threading.Lock()
sdkRxMessageInfoLastCleanup = 0.0
sdkRxMessageInfoTTL = 7200.0
sdkRxMessageInfoMaxSize = 20000
# 合并转发节点缓存:OneBot 风格通过外层消息 ID 再取回节点列表。
sdkForwardMessageInfo = {}
sdkForwardMessageInfoLock = threading.Lock()
sdkForwardMessageInfoLastCleanup = 0.0
sdkForwardMessageInfoTTL = 7200.0
sdkForwardMessageInfoMaxSize = 5000
# QQ 群/C2C 引用索引:message_scene.ext 的 msg_idx <-> message_id。
# 接收时把 ref_msg_idx 还原为业务层 message_id，发送时再反向转为 REFIDX。
sdkMsgIdxInfo = {}
sdkMsgIdxInfoLock = threading.Lock()
sdkMsgIdxInfoLastCleanup = 0.0
sdkMsgIdxInfoTTL = 7200.0
sdkMsgIdxInfoMaxSize = 20000
# 消息内容缓存单条文本上限:防御超长消息(长 markdown/合并转发)把缓存撑大。
sdkRxMessageContentMaxLen = 4096
# 未映射到 OlivOS 标准事件的平台事件环形缓存(按 bot 维度),供 SDK 层查询。
sdkUnhandledEventInfo = {}
sdkUnhandledEventLock = threading.Lock()
sdkUnhandledEventMaxSize = 200
# 用户信息缓存:消息/事件/mentions 中出现过的用户,按各类 openid 建索引,
# 记录昵称/角色/union_openid 等,供 get_stranger_info / at 昵称补全使用。
sdkUserInfo = {}
sdkUserInfoLock = threading.Lock()
sdkUserInfoLastCleanup = 0.0
sdkUserInfoTTL = 7 * 86400.0
sdkUserInfoMaxSize = 50000


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
                elif is_rx and self.data.op == 0:
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
            # 频道通用可订阅事件位(公私域均可):成员变更/表情表态/互动回调/消息审核。
            tmp_common_intents = (
                int(intents_T.GUILD_MEMBERS)
                | int(intents_T.GUILD_MESSAGE_REACTIONS)
                | int(intents_T.INTERACTION)
                | int(intents_T.MESSAGE_AUDIT)
            )
            if bot_info.model in ['private']:
                tmp_intents |= int(intents_T.GUILD_MESSAGES)
                tmp_intents |= int(intents_T.FORUMS_EVENT)
                tmp_intents |= tmp_common_intents
            elif bot_info.model in ['public', 'sandbox']:
                tmp_intents |= int(intents_T.PUBLIC_GUILD_MESSAGES)
                tmp_intents |= int(intents_T.GROUP_AND_C2C_EVENT)
                tmp_intents |= int(intents_T.PUBLIC_QQ_GROUP_MEMBERS)
                tmp_intents |= tmp_common_intents
            elif bot_info.model in ['public_guild_only']:
                tmp_intents |= int(intents_T.PUBLIC_GUILD_MESSAGES)
                tmp_intents |= tmp_common_intents
            elif bot_info.model in ['private_intents', 'public_intents', 'sandbox_intents']:
                tmp_intents = bot_info.intents
            # QQ 群成员进退群事件实测走 1<<24,群/C2C 消息走 1<<25,两位互为兼容:
            # 有其一即两个都订。官方文档标注的 1<<15 实测无效,不参与订阅。
            qq_group_compat_intents = (
                int(intents_T.PUBLIC_QQ_GROUP_MEMBERS)
                | int(intents_T.GROUP_AND_C2C_EVENT)
            )
            if tmp_intents & qq_group_compat_intents:
                tmp_intents |= qq_group_compat_intents
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

    class sendResume(payload_template):
        # 恢复登录态:重连后凭 session_id + 已收到的最新 seq 续传断线期间的事件。
        def __init__(self, bot_info: bot_info_T, session_id, last_s):
            payload_template.__init__(self)
            self.data.op = 6
            try:
                self.data.d = {
                    'token': 'QQBot %s' % (getTokenNow(bot_info)),
                    'session_id': session_id,
                    'seq': last_s
                }
            except Exception:
                self.active = False

    class sendHeartbeat(payload_template):
        def __init__(self, last_s=None):
            payload_template.__init__(self)
            self.data.op = 1
            self.data.d = last_s

        def dump(self):
            res_obj = {}
            for data_this in self.data.__dict__:
                if self.data.__dict__[data_this] is not None or data_this == 'd':
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
        self.query = None  # dict:GET 类接口的 query 参数,None 值自动剔除
        self.host = None
        self.port = 443
        self.route = None
        self.res = None
        self.res_code = None

    def _get_query_string(self):
        if type(self.query) is not dict:
            return ''
        tmp_query_dict = {
            key: value
            for key, value in self.query.items()
            if value is not None
        }
        if len(tmp_query_dict) == 0:
            return ''
        return '?' + parse.urlencode(tmp_query_dict)

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
            send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp) + self._get_query_string()
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
                # 部分 DELETE 接口(如删除频道成员)带请求体,无 data 时不发 body。
                if self.data is not None:
                    msg_res = req.request("DELETE", send_url, headers=headers, data=payload)
                else:
                    msg_res = req.request("DELETE", send_url, headers=headers)
            elif req_type in ['PUT', 'PATCH']:
                if self.data is not None:
                    msg_res = req.request(req_type, send_url, headers=headers, data=payload)
                else:
                    msg_res = req.request(req_type, send_url, headers=headers)

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
        and tmpInfo[1] > tmpTime + sdkTokenRefreshAhead
    ):
        # 距过期还早,直接用缓存 token
        access_token = tmpInfo[0]
    else:
        # 文档建议在过期前 60s 内换取新 token,旧 token 在此期间仍然有效
        tmp_new_token = None
        tmp_new_expire_at = -1
        try:
            msg_this = API.getAppAccessToken(bot_info)
            msg_this.data.clientSecret = bot_info.access_token
            msg_this.data.appId = str(bot_info.id)
            msg_this.do_api_plant()
            if msg_this.res is not None:
                raw_obj = init_api_json(msg_this.res)
                if (
                    type(raw_obj) is dict
                    and raw_obj.get('access_token', None) is not None
                ):
                    tmp_new_token = raw_obj['access_token']
                    tmp_new_expire_at = tmpTime + int(raw_obj.get('expires_in', 7200))
        except Exception:
            tmp_new_token = None
        if tmp_new_token is not None:
            sdkTokenInfo[plugin_event_bot_hash] = [tmp_new_token, tmp_new_expire_at]
            access_token = tmp_new_token
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
        elif (
            tmpInfo[0] is not None
            and tmpInfo[1] > tmpTime
        ):
            # 刷新失败但旧 token 尚未真正过期,先兜底沿用,避免覆盖成 None
            access_token = tmpInfo[0]
    return access_token


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


# QQ 消息会把表情编码成正文前缀,正文不应把该平台标记原样暴露给插件。
qqFaceTagPattern = re.compile(
    r'<faceType\s*=\s*(?P<face_type>[^,>]+)\s*,\s*faceId\s*=\s*'
    r'(?P<face_id>"[^"]*"|\'[^\']*\'|[^,\s>]+)'
    r'(?P<extra>(?:,[^>]*)?)\s*/?>'
)
qqFaceAttributePattern = re.compile(
    r'(?:^|,)\s*(?P<key>[A-Za-z_][\w-]*)\s*=\s*'
    r'(?P<value>"[^"]*"|\'[^\']*\'|[^,>]*)'
)


def _unquote_qq_face_value(value):
    value = str(value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ['"', "'"]:
        return value[1:-1]
    return value


def _strip_qq_face_tags(content):
    """移除 QQ 原始表情标签,同时返回可供 extend 使用的结构化信息。"""
    if content is None:
        return None, []
    if not isinstance(content, str):
        return '', []
    face_data = []

    def replace_face_tag(match):
        face_item = {
            'face_type': _unquote_qq_face_value(match.group('face_type')),
            'face_id': _unquote_qq_face_value(match.group('face_id')),
            'raw': match.group(0)
        }
        for attribute_match in qqFaceAttributePattern.finditer(match.group('extra')):
            face_item[attribute_match.group('key')] = _unquote_qq_face_value(
                attribute_match.group('value')
            )
        face_data.append(face_item)
        return ''

    return qqFaceTagPattern.sub(replace_face_tag, content), face_data


def _get_qq_message_content(event_data):
    """统一取得清理后的消息正文及 QQ 表情扩展数据。"""
    if not isinstance(event_data, dict):
        return None, []
    return _strip_qq_face_tags(event_data.get('content', None))


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


def _append_qq_message_attachments(message_obj, attachments, skip=False):
    if skip:
        return
    attachment_data = _get_message_attachments(attachments)
    if len(attachment_data) == 0:
        return
    message_obj.data.extend(attachment_data)
    if isinstance(message_obj.data_raw, list):
        message_obj.data_raw.extend(copy.deepcopy(attachment_data))


def _get_qq_message_type(event_data):
    if not isinstance(event_data, dict):
        return 0
    try:
        return int(event_data.get('message_type', 0))
    except (TypeError, ValueError):
        return 0


def _get_qq_attachment_message_segment(attachment):
    if not isinstance(attachment, dict):
        return None
    attachment_url = _get_attachment_url(attachment)
    if attachment_url is None:
        return None
    content_type = str(attachment.get('content_type', '')).lower()
    if content_type.startswith('image'):
        segment_type = 'image'
    elif content_type.startswith('video'):
        segment_type = 'video'
    elif content_type == 'voice' or content_type.startswith('audio'):
        segment_type = 'record'
    else:
        segment_type = 'file'
    segment_data = {
        'file': attachment_url,
        'url': attachment_url
    }
    for key in [
        'filename', 'size', 'width', 'height', 'content_type',
        'voice_wav_url', 'asr_refer_text'
    ]:
        if attachment.get(key, None) is not None:
            segment_data[key] = copy.deepcopy(attachment[key])
    if 'filename' in segment_data:
        segment_data['name'] = segment_data['filename']
    return {
        'type': segment_type,
        'data': segment_data
    }


def _get_qq_forward_element_content(element):
    if not isinstance(element, dict):
        return []
    content = []
    content_text = element.get('content', None)
    if isinstance(content_text, str) and content_text not in ['', ' ']:
        content_text, _ = _strip_qq_face_tags(content_text)
        if content_text not in ['', ' ']:
            content.append({
                'type': 'text',
                'data': {'text': content_text}
            })
    ark_data = element.get('ark_data', None)
    if isinstance(ark_data, dict):
        try:
            content.append({
                'type': 'json',
                'data': {
                    'data': json.dumps(
                        ark_data,
                        ensure_ascii=False,
                        separators=(',', ':')
                    )
                }
            })
        except (TypeError, ValueError):
            pass
    for attachment in element.get('attachments', []):
        segment = _get_qq_attachment_message_segment(attachment)
        if segment is not None:
            content.append(segment)
    nested_elements = element.get('msg_elements', None)
    if isinstance(nested_elements, list):
        for nested_element in nested_elements:
            content.extend(_get_qq_forward_element_content(nested_element))
    if not content and isinstance(content_text, str) and content_text != '':
        content.append({
            'type': 'text',
            'data': {'text': content_text}
        })
    return content


def _get_qq_forward_node(element, content=None):
    if not isinstance(element, dict):
        element = {}
    author = element.get('author', None)
    if not isinstance(author, dict):
        author = {}
    user_id = (
        author.get('member_openid', None)
        or author.get('user_openid', None)
        or author.get('union_openid', None)
        or author.get('id', None)
    )
    if user_id is not None:
        user_id = str(user_id)
    sender_name = author.get('username', author.get('nickname', None))
    if sender_name is not None:
        sender_name = str(sender_name)
    node_data = {
        'user_id': user_id,
        'uin': user_id,
        'name': sender_name,
        'nickname': sender_name,
        'content': (
            _get_qq_forward_element_content(element)
            if content is None else content
        )
    }
    msg_idx = element.get('msg_idx', None)
    if msg_idx is not None and str(msg_idx) != '':
        node_data['seq'] = str(msg_idx)
    message_id = element.get('id', None)
    if message_id is not None and str(message_id) != '':
        node_data['id'] = str(message_id)
    return {
        'type': 'node',
        'data': node_data
    }


def _get_qq_forward_nodes_from_elements(elements):
    nodes = []
    if not isinstance(elements, list):
        return nodes
    for element in elements:
        if not isinstance(element, dict):
            continue
        nested_elements = element.get('msg_elements', None)
        message_type = _get_qq_message_type(element)
        if message_type in [101, 102] and isinstance(nested_elements, list):
            nested_nodes = _get_qq_forward_nodes_from_elements(nested_elements)
            if nested_nodes:
                nodes.extend(nested_nodes)
                continue
        nodes.append(_get_qq_forward_node(element))
    return nodes


def _split_qq_forward_text_blocks(content, marker_pattern):
    matches = list(re.finditer(marker_pattern, content, flags=re.M))
    if not matches:
        return []
    min_indent = min(len(match.group('indent').expandtabs(4)) for match in matches)
    matches = [
        match
        for match in matches
        if len(match.group('indent').expandtabs(4)) == min_indent
    ]
    blocks = []
    for index, marker_match in enumerate(matches):
        block_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(content)
        )
        blocks.append(content[marker_match.end():block_end].strip())
    return blocks


def _get_qq_forward_text_field(block, field_name):
    field_match = re.search(
        r'(?m)^[ \t]*\[%s\][ \t]*(.*)$' % re.escape(field_name),
        block
    )
    if field_match is None:
        return None
    value_lines = [field_match.group(1)]
    remainder = block[field_match.end():]
    for line in remainder.splitlines():
        if re.match(
            r'^[ \t]*\[(?:消息内容|发送者|消息类型|关联消息|附件\d+)\]',
            line
        ):
            break
        if re.match(r'^[ \t]*(?:===|---)\s*', line):
            break
        value_lines.append(line.strip())
    value = '\n'.join(value_lines).strip()
    return value if value != '' else None


def _get_qq_forward_text_attachment(attachment_text):
    url_match = re.search(r'URL:\s*(\S+)', attachment_text)
    if url_match is None:
        return None
    type_match = re.search(r'类型:\s*([^\s]+)', attachment_text)
    type_name = type_match.group(1).lower() if type_match else ''
    if '图片' in type_name or 'image' in type_name:
        content_type = 'image'
    elif '视频' in type_name or 'video' in type_name:
        content_type = 'video'
    elif '语音' in type_name or '音频' in type_name or 'audio' in type_name:
        content_type = 'audio'
    else:
        content_type = 'file'
    attachment = {
        'url': url_match.group(1),
        'content_type': content_type
    }
    filename_match = re.search(
        r'文件名:\s*(.*?)(?=\s+(?:尺寸|大小|URL):|$)',
        attachment_text
    )
    if filename_match is not None:
        attachment['filename'] = filename_match.group(1).strip()
    size_match = re.search(r'大小:\s*([^\s]+)', attachment_text)
    if size_match is not None:
        attachment['size'] = size_match.group(1)
    dimension_match = re.search(r'尺寸:\s*(\d+)\s*[xX×]\s*(\d+)', attachment_text)
    if dimension_match is not None:
        attachment['width'] = int(dimension_match.group(1))
        attachment['height'] = int(dimension_match.group(2))
    return _get_qq_attachment_message_segment(attachment)


def _get_qq_forward_text_node(block, attachment_state):
    sender_name = _get_qq_forward_text_field(block, '发送者')
    message_text = _get_qq_forward_text_field(block, '消息内容')
    content_segments = []
    if message_text is not None:
        message_text, _ = _strip_qq_face_tags(message_text)
        if message_text != '':
            content_segments.append({
                'type': 'text',
                'data': {'text': message_text}
            })
    attachment_matches = list(re.finditer(
        r'(?m)^[ \t]*\[附件\d+\][ \t]*(.*)$',
        block
    ))
    for attachment_match in attachment_matches:
        segment = _get_qq_forward_text_attachment(attachment_match.group(1))
        if segment is None and attachment_state['index'] < len(attachment_state['items']):
            segment = _get_qq_attachment_message_segment(
                attachment_state['items'][attachment_state['index']]
            )
            attachment_state['index'] += 1
        if segment is not None:
            content_segments.append(segment)
    if not content_segments and block != '':
        content_segments.append({
            'type': 'text',
            'data': {'text': block}
        })
    return _get_qq_forward_node({
        'author': {'username': sender_name} if sender_name else {}
    }, content=content_segments)


def _get_qq_forward_text_block_nodes(block, attachment_state):
    related_blocks = _split_qq_forward_text_blocks(
        block,
        r'^(?P<indent>[ \t]*)---\s*第\s*\d+\s*条\s*---\s*$'
    )
    if related_blocks:
        nodes = []
        for related_block in related_blocks:
            nodes.extend(_get_qq_forward_text_block_nodes(
                related_block,
                attachment_state
            ))
        if nodes:
            return nodes
    return [_get_qq_forward_text_node(block, attachment_state)]


def _get_qq_forward_text_nodes(content, attachments=None):
    if not isinstance(content, str):
        return []
    normalized_content = content.replace('\\r\\n', '\n')
    normalized_content = normalized_content.replace('\\n', '\n').replace('\r', '\n')
    message_blocks = _split_qq_forward_text_blocks(
        normalized_content,
        r'^(?P<indent>[ \t]*)===\s*消息\s+\d+\s*===\s*$'
    )
    if not message_blocks:
        message_blocks = [normalized_content]
        if not re.search(
            r'(?m)^\s*\[(?:消息内容|发送者|附件\d+)\]',
            normalized_content
        ) and not re.search(
            r'(?m)^\s*---\s*第\s*\d+\s*条\s*---\s*$',
            normalized_content
        ):
            return []
    attachment_state = {
        'items': attachments if isinstance(attachments, list) else [],
        'index': 0
    }
    nodes = []
    for message_block in message_blocks:
        nodes.extend(_get_qq_forward_text_block_nodes(
            message_block,
            attachment_state
        ))
    if len(nodes) == 1 and attachment_state['index'] == 0:
        for attachment in attachment_state['items']:
            segment = _get_qq_attachment_message_segment(attachment)
            if segment is not None:
                nodes[0]['data']['content'].append(segment)
    return nodes


def _get_qq_forward_messages(event_data):
    if not isinstance(event_data, dict):
        return []
    elements = event_data.get('msg_elements', None)
    element_contents = []
    if isinstance(elements, list):
        for element in elements:
            if isinstance(element, dict) and isinstance(element.get('content', None), str):
                element_contents.append(element['content'])
        text_nodes = _get_qq_forward_text_nodes(
            '\n'.join(element_contents),
            event_data.get('attachments', None)
        )
        if text_nodes:
            return text_nodes
        element_nodes = _get_qq_forward_nodes_from_elements(elements)
        if element_nodes:
            return element_nodes
    text_nodes = _get_qq_forward_text_nodes(
        event_data.get('content', None),
        event_data.get('attachments', None)
    )
    if text_nodes:
        return text_nodes
    fallback_element = {
        'author': event_data.get('author', {}),
        'content': event_data.get('content', ''),
        'attachments': event_data.get('attachments', [])
    }
    return [_get_qq_forward_node(fallback_element)]


def _get_qq_message_para(event_data, bot_hash=None):
    if _get_qq_message_type(event_data) == 102:
        forward_id = event_data.get('id', None) if isinstance(event_data, dict) else None
        if forward_id is not None and str(forward_id) != '':
            forward_id = str(forward_id)
            if bot_hash is not None:
                _register_qq_forward_message(
                    bot_hash,
                    forward_id,
                    _get_qq_forward_messages(event_data)
                )
            return OlivOS.messageAPI.PARA.forward(id=forward_id)
    return _get_qq_structured_message_para(event_data)


def _get_qq_structured_message_para(event_data):
    if not isinstance(event_data, dict):
        return None
    structured_data = event_data.get('ark_data', None)
    if not isinstance(structured_data, dict):
        structured_data = event_data.get('ark', None)
    if not isinstance(structured_data, dict):
        # 频道 Message 模型还定义了 embeds 卡片；目前官方不投递这类
        # 入站消息，但若网关实际携带，仍按结构化消息完整交给插件。
        embeds = event_data.get('embeds', None)
        if isinstance(embeds, list) and len(embeds) > 0:
            structured_data = {'embeds': copy.deepcopy(embeds)}
    if not isinstance(structured_data, dict):
        return None
    try:
        structured_json = json.dumps(
            structured_data,
            ensure_ascii=False,
            separators=(',', ':')
        )
    except (TypeError, ValueError):
        return None
    return OlivOS.messageAPI.PARA.json(data=structured_json)


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


def _register_qq_user_info(bot_hash, user_obj, role=None, chat_type=None, chat_id=None):
    # 登记/合并用户信息:author、mentions 条目、频道 user 对象均可直接传入。
    # 同一用户的各类 OpenID/统一账号各建一条索引,指向同一记录。
    global sdkUserInfoLastCleanup
    if not isinstance(user_obj, dict):
        return None
    id_keys = [
        'member_openid', 'user_openid', 'union_openid',
        'union_user_account', 'id'
    ]
    user_ids = []
    for id_key in id_keys:
        user_id = user_obj.get(id_key, None)
        if user_id is not None and str(user_id) != '' and str(user_id) not in user_ids:
            user_ids.append(str(user_id))
    if len(user_ids) == 0:
        return None
    username = user_obj.get('username', None)
    if (
        not isinstance(username, str)
        or username.strip() == ''
        or username in ['用户', 'Nobody']
    ):
        # 平台缺省昵称/框架占位名不入缓存,避免覆盖真实昵称。
        username = None
    now_monotonic = time.monotonic()
    with sdkUserInfoLock:
        if now_monotonic - sdkUserInfoLastCleanup >= 300:
            expired_keys = [
                key for key, data in sdkUserInfo.items()
                if now_monotonic - data['time_monotonic'] >= sdkUserInfoTTL
            ]
            for key in expired_keys:
                sdkUserInfo.pop(key, None)
            sdkUserInfoLastCleanup = now_monotonic
        record = None
        for user_id in user_ids:
            record = sdkUserInfo.get((str(bot_hash), user_id), None)
            if record is not None:
                break
        if record is None:
            record = {
                'id': user_ids[0],
                'name': None,
                'member_openid': None,
                'user_openid': None,
                'union_openid': None,
                'union_user_account': None,
                'bot': None,
                'role': None,
                'chat_type': None,
                'chat_id': None,
                'time': 0,
                'time_monotonic': 0.0
            }
        for id_key in ['member_openid', 'user_openid', 'union_openid']:
            id_value = user_obj.get(id_key, None)
            if id_value is not None and str(id_value) != '':
                record[id_key] = str(id_value)
        union_user_account = user_obj.get('union_user_account', None)
        if union_user_account is not None and str(union_user_account) != '':
            record['union_user_account'] = str(union_user_account)
        if isinstance(user_obj.get('bot', None), bool):
            record['bot'] = user_obj['bot']
        if username is not None:
            record['name'] = username
        if role is not None:
            record['role'] = str(role)
        if chat_type is not None:
            record['chat_type'] = str(chat_type)
        if chat_id is not None and str(chat_id) != '':
            record['chat_id'] = str(chat_id)
        record['time'] = int(time.time())
        record['time_monotonic'] = now_monotonic
        # 容量上限:一次性淘汰最旧的一批,避免每条消息都全量扫描。
        if len(sdkUserInfo) >= sdkUserInfoMaxSize:
            oldest_keys = sorted(
                sdkUserInfo,
                key=lambda key: sdkUserInfo[key]['time_monotonic']
            )[:max(100, len(sdkUserInfo) - sdkUserInfoMaxSize + len(user_ids))]
            for key in oldest_keys:
                sdkUserInfo.pop(key, None)
        for user_id in user_ids:
            sdkUserInfo[(str(bot_hash), user_id)] = record
    return record


def _register_qq_user_info_from_mentions(bot_hash, mentions, chat_type=None, chat_id=None):
    if not isinstance(mentions, list):
        return
    for mention in mentions:
        _register_qq_user_info(
            bot_hash,
            mention,
            chat_type=chat_type,
            chat_id=chat_id
        )


def _get_qq_user_info(bot_hash, user_id):
    if user_id is None or str(user_id) == '':
        return None
    with sdkUserInfoLock:
        record = sdkUserInfo.get((str(bot_hash), str(user_id)), None)
        if record is None:
            return None
        if time.monotonic() - record['time_monotonic'] >= sdkUserInfoTTL:
            sdkUserInfo.pop((str(bot_hash), str(user_id)), None)
            return None
        return copy.deepcopy(record)


def _get_qq_user_name_from_cache(bot_hash, user_id):
    record = _get_qq_user_info(bot_hash, user_id)
    if record is None:
        return None
    return record.get('name', None)


def _get_qq_author_name_cached(bot_hash, author, fallback_user_id=None):
    # 本条消息带昵称就用本条的;缺省时回退到该用户历史消息留下的缓存昵称。
    author_name = _get_qq_author_name(author)
    if author_name != '用户':
        return author_name
    lookup_ids = []
    if isinstance(author, dict):
        for id_key in [
            'member_openid', 'user_openid', 'union_openid',
            'union_user_account', 'id'
        ]:
            id_value = author.get(id_key, None)
            if id_value is not None and str(id_value) != '':
                lookup_ids.append(str(id_value))
    if fallback_user_id is not None and str(fallback_user_id) != '':
        lookup_ids.append(str(fallback_user_id))
    for lookup_id in lookup_ids:
        cached_name = _get_qq_user_name_from_cache(bot_hash, lookup_id)
        if cached_name is not None:
            return cached_name
    return '用户'


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
        if key == '':
            continue
        result[key] = value
    return result


def _get_qq_event_extend(event_type, event_data):
    if not isinstance(event_data, dict):
        event_data = {}
    raw_event = copy.deepcopy(event_data)
    result = {
        'qq_event_type': str(event_type),
        'qq_event_data': raw_event
    }
    # 官方事件 data 的每个顶层字段均提供稳定的 qq_ 前缀入口。
    # 复用 raw_event 中的对象，避免大型转发/附件数据在单个事件内重复占用内存。
    for field_name, field_value in raw_event.items():
        if isinstance(field_name, str) and field_name != '':
            result.setdefault('qq_%s' % field_name, field_value)
    return result


def _get_qq_message_event_extend(event_type, event_data, face_data=None):
    if not isinstance(event_data, dict):
        event_data = {}
    result = _get_qq_event_extend(event_type, event_data)
    result.update({
        # 全量群消息事件本身不能证明消息是否 @ 机器人；保留未知态，
        # 避免其先于 GROUP_AT_MESSAGE_CREATE 到达时被错误标记为 False。
        'qq_at_bot': (
            None
            if event_type == 'GROUP_MESSAGE_CREATE'
            else event_type in qqAtBotEventTypes
        ),
        'qq_at_bot_known': event_type != 'GROUP_MESSAGE_CREATE',
        'qq_raw_content': result.get('qq_content', None)
    })
    if face_data is None:
        _, face_data = _get_qq_message_content(event_data)
    if len(face_data) > 0:
        result['qq_face_data'] = copy.deepcopy(face_data)
    if 'id' in event_data:
        # 保留既有消息专用名称；qq_id 则由通用入口提供。
        result['qq_message_id'] = result.get('qq_id', event_data['id'])
    message_scene = event_data.get('message_scene', None)
    attachment_segments = []
    attachments = event_data.get('attachments', None)
    if isinstance(attachments, list):
        for attachment in attachments:
            attachment_segment = _get_qq_attachment_message_segment(attachment)
            if attachment_segment is not None:
                attachment_segments.append(attachment_segment)
    if len(attachment_segments) > 0:
        result['qq_attachment_segments'] = attachment_segments
    if 'ark_data' not in event_data and 'ark' in event_data:
        result['qq_ark_data'] = result.get('qq_ark', event_data['ark'])
    if 'message_scene' in event_data:
        scene_ext = _parse_qq_message_scene_ext(message_scene)
        result['qq_message_scene_ext'] = scene_ext
        if 'msg_idx' in scene_ext:
            result['qq_msg_idx'] = scene_ext['msg_idx']
        if 'ref_msg_idx' in scene_ext:
            # ref_msg_idx 是 QQ 的消息索引，不是可发送的 message_id。
            result['qq_ref_msg_idx'] = scene_ext['ref_msg_idx']
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


def _parse_qq_message_timestamp(timestamp, default=None):
    # 平台时间戳既可能是 RFC3339 字符串(频道/群/C2C 事件),也可能是秒级数字。
    if default is None:
        default = int(time.time())
    if timestamp is None:
        return default
    if isinstance(timestamp, bool):
        return default
    if isinstance(timestamp, (int, float)):
        return int(timestamp)
    if isinstance(timestamp, str):
        tmp_timestamp = timestamp.strip()
        if tmp_timestamp == '':
            return default
        try:
            return int(tmp_timestamp)
        except ValueError:
            pass
        try:
            if tmp_timestamp.endswith('Z'):
                tmp_timestamp = tmp_timestamp[:-1] + '+00:00'
            return int(datetime.fromisoformat(tmp_timestamp).timestamp())
        except Exception:
            return default
    return default


def _register_qq_msg_idx(bot_hash, chat_type, chat_id, msg_idx, message_id):
    if (
        msg_idx is None or str(msg_idx) == ''
        or message_id is None or str(message_id) == ''
        or chat_id is None or str(chat_id) == ''
    ):
        return
    global sdkMsgIdxInfoLastCleanup
    now = time.monotonic()
    cache_key = (str(bot_hash), str(chat_type), str(chat_id), str(msg_idx))
    with sdkMsgIdxInfoLock:
        # 过期清理按 60s 节流,避免每条消息全量扫描。
        if now - sdkMsgIdxInfoLastCleanup >= 60:
            expired_keys = [
                key for key, data in sdkMsgIdxInfo.items()
                if now - data['created_monotonic'] >= sdkMsgIdxInfoTTL
            ]
            for key in expired_keys:
                sdkMsgIdxInfo.pop(key, None)
            sdkMsgIdxInfoLastCleanup = now
        if cache_key not in sdkMsgIdxInfo and len(sdkMsgIdxInfo) >= sdkMsgIdxInfoMaxSize:
            # 一次性淘汰最旧的一批,摊薄满载时的每条消息开销。
            oldest_keys = sorted(
                sdkMsgIdxInfo,
                key=lambda key: sdkMsgIdxInfo[key]['created_monotonic']
            )[:100]
            for key in oldest_keys:
                sdkMsgIdxInfo.pop(key, None)
        sdkMsgIdxInfo[cache_key] = {
            'message_id': str(message_id),
            'created_monotonic': now
        }


def _get_qq_message_id_by_idx(bot_hash, chat_type, chat_id, msg_idx):
    if msg_idx is None or str(msg_idx) == '' or chat_id is None:
        return None
    now = time.monotonic()
    cache_key = (str(bot_hash), str(chat_type), str(chat_id), str(msg_idx))
    with sdkMsgIdxInfoLock:
        cache_data = sdkMsgIdxInfo.get(cache_key, None)
        if cache_data is None:
            return None
        if now - cache_data['created_monotonic'] >= sdkMsgIdxInfoTTL:
            sdkMsgIdxInfo.pop(cache_key, None)
            return None
        return cache_data['message_id']


def _register_qq_rx_message(
    bot_hash,
    chat_type,
    chat_id,
    message_id,
    message_obj=None,
    content=None,
    raw_content=None,
    sender_id=None,
    sender_name=None,
    timestamp=None,
    channel_id=None,
    msg_idx=None
):
    global sdkRxMessageInfoLastCleanup
    if message_id is None or str(message_id) == '':
        return
    message_str = content
    if message_str is None and message_obj is not None:
        try:
            message_str = message_obj.get('olivos_string')
        except Exception:
            message_str = None
    # 超长内容截断,防御异常长消息撑大缓存。
    if isinstance(message_str, str) and len(message_str) > sdkRxMessageContentMaxLen:
        message_str = message_str[:sdkRxMessageContentMaxLen]
    raw_message_str = raw_content if raw_content is not None else message_str
    if isinstance(raw_message_str, str) and len(raw_message_str) > sdkRxMessageContentMaxLen:
        raw_message_str = raw_message_str[:sdkRxMessageContentMaxLen]
    now = time.monotonic()
    cache_key = (str(bot_hash), str(message_id))
    with sdkRxMessageInfoLock:
        if now - sdkRxMessageInfoLastCleanup >= 60:
            expired_keys = [
                key for key, data in sdkRxMessageInfo.items()
                if now - data['created_monotonic'] >= sdkRxMessageInfoTTL
            ]
            for key in expired_keys:
                sdkRxMessageInfo.pop(key, None)
            sdkRxMessageInfoLastCleanup = now
        if cache_key not in sdkRxMessageInfo and len(sdkRxMessageInfo) >= sdkRxMessageInfoMaxSize:
            # 一次性淘汰最旧的一批,摊薄满载时的每条消息开销。
            oldest_keys = sorted(
                sdkRxMessageInfo,
                key=lambda key: sdkRxMessageInfo[key]['created_monotonic']
            )[:100]
            for key in oldest_keys:
                sdkRxMessageInfo.pop(key, None)
        sdkRxMessageInfo[cache_key] = {
            'message_id': str(message_id),
            'chat_type': str(chat_type),
            'chat_id': None if chat_id is None else str(chat_id),
            'channel_id': None if channel_id is None else str(channel_id),
            'msg_idx': None if msg_idx is None else str(msg_idx),
            'message': message_str,
            'raw_message': raw_message_str,
            'sender_id': None if sender_id is None else str(sender_id),
            'sender_name': sender_name,
            'time': _parse_qq_message_timestamp(timestamp),
            'created_monotonic': now
        }
    _register_qq_msg_idx(bot_hash, chat_type, chat_id, msg_idx, message_id)
    if sender_id is not None and str(sender_id) != '':
        _register_qq_user_info(
            bot_hash,
            {'id': str(sender_id), 'username': sender_name},
            chat_type=chat_type,
            chat_id=chat_id
        )


def _get_qq_rx_message(bot_hash, message_id):
    if message_id is None or str(message_id) == '':
        return None
    now = time.monotonic()
    cache_key = (str(bot_hash), str(message_id))
    with sdkRxMessageInfoLock:
        cache_data = sdkRxMessageInfo.get(cache_key, None)
        if cache_data is None:
            return None
        if now - cache_data['created_monotonic'] >= sdkRxMessageInfoTTL:
            sdkRxMessageInfo.pop(cache_key, None)
            return None
        return copy.deepcopy(cache_data)


def _get_qq_msg_idx_by_message_id(bot_hash, chat_type, chat_id, message_id):
    cache_data = _get_qq_rx_message(bot_hash, message_id)
    if cache_data is None:
        return None
    if (
        cache_data.get('chat_type', None) != str(chat_type)
        or cache_data.get('chat_id', None) != str(chat_id)
    ):
        return None
    msg_idx = cache_data.get('msg_idx', None)
    if msg_idx is None or not str(msg_idx).startswith('REFIDX_'):
        return None
    return str(msg_idx)


def _resolve_qq_reference_msg_idx(target_event, chat_type, chat_id, message_id):
    if message_id is None or str(message_id) == '':
        return None
    target_data = getattr(target_event, 'data', None)
    extend_data = getattr(target_data, 'extend', None)
    if isinstance(extend_data, dict):
        if chat_type == 'qq_private':
            source_chat_id = getattr(target_data, 'user_id', None)
        else:
            source_chat_id = getattr(target_data, 'group_id', None)
        source_message_id = extend_data.get(
            'qq_message_id',
            extend_data.get('reply_msg_id', None)
        )
        source_msg_idx = extend_data.get('qq_msg_idx', None)
        if (
            source_chat_id is not None
            and str(source_chat_id) == str(chat_id)
            and source_message_id is not None
            and str(source_message_id) == str(message_id)
            and source_msg_idx is not None
            and str(source_msg_idx).startswith('REFIDX_')
        ):
            return str(source_msg_idx)
    return _get_qq_msg_idx_by_message_id(
        target_event.bot_info.hash,
        chat_type,
        chat_id,
        message_id
    )


def _get_qq_reference_message_id(bot_hash, chat_type, chat_id, event_data):
    # 频道事件直接携带 message_reference.message_id;
    # QQ 群/C2C 事件只有 message_scene.ext 的 ref_msg_idx,需经 msg_idx 索引换回 message_id。
    if not isinstance(event_data, dict):
        return None
    message_reference = event_data.get('message_reference', None)
    if isinstance(message_reference, dict):
        reference_id = message_reference.get('message_id', None)
        if reference_id is not None and str(reference_id) != '':
            return str(reference_id)
    scene_ext = _parse_qq_message_scene_ext(event_data.get('message_scene', None))
    ref_msg_idx = scene_ext.get('ref_msg_idx', None)
    if ref_msg_idx is not None and str(ref_msg_idx) != '':
        reference_message_id = _get_qq_message_id_by_idx(
            bot_hash,
            chat_type,
            chat_id,
            ref_msg_idx
        )
        if reference_message_id is not None:
            return reference_message_id
        # 与 OneBot V11 一样保留 reply 段；缓存未命中时使用 QQ 原始索引。
        return str(ref_msg_idx)
    return None


def _record_unhandled_qq_event(bot_hash, event_type, event_id, event_data):
    # 对不上 OlivOS 标准事件的平台事件留在 SDK 层:进 bot 维度的环形缓存。
    try:
        with sdkUnhandledEventLock:
            event_deque = sdkUnhandledEventInfo.setdefault(
                str(bot_hash),
                deque(maxlen=sdkUnhandledEventMaxSize)
            )
            event_deque.append({
                'time': int(time.time()),
                'event_type': str(event_type),
                'event_id': None if event_id is None else str(event_id),
                'data': copy.deepcopy(event_data)
            })
    except Exception:
        traceback.print_exc()


def _apply_qq_message_reference(message_obj, reference_message_id):
    # 与 OneBot 行为对齐:引用作为 reply 消息段插在消息段列表最前。
    if reference_message_id is None or str(reference_message_id) == '':
        return
    reply_para = OlivOS.messageAPI.PARA.reply(id=str(reference_message_id))
    message_obj.data.insert(0, reply_para)
    if isinstance(message_obj.data_raw, list):
        message_obj.data_raw.insert(0, copy.deepcopy(reply_para))


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


def _get_qq_ordered_mention_ids(mentions):
    # 按 mentions 数组原始顺序提取真实用户标识(群优先 member_openid,C2C 为 user_openid)。
    result = []
    if not isinstance(mentions, list):
        return result
    for mention in mentions:
        if not isinstance(mention, dict):
            continue
        for id_key in ['member_openid', 'user_openid', 'id']:
            user_id = mention.get(id_key, None)
            if user_id is not None and str(user_id) != '':
                result.append(str(user_id))
                break
    return result


def _apply_qq_message_mentions(message_obj, mentions, self_ids=None, flag_backfill=False, bot_hash=None):
    if not isinstance(message_obj.data, list):
        return
    mention_map = _get_qq_mention_map(mentions)
    flag_updated = False
    message_data = []

    def get_mention_username(user_id):
        # mentions 优先,取不到时回退用户信息缓存里的历史昵称。
        username = mention_map.get(user_id, None)
        if username is None and bot_hash is not None:
            username = _get_qq_user_name_from_cache(bot_hash, user_id)
        return username

    if mention_map:
        for message_item in message_obj.data:
            if isinstance(message_item, OlivOS.messageAPI.PARA.at):
                user_id = str(message_item.data.get('id', ''))
                username = get_mention_username(user_id)
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
    else:
        message_data = list(message_obj.data)
        # 无 mentions 时也尝试用缓存补全 at 段昵称。
        if bot_hash is not None:
            for message_item in message_data:
                if (
                    isinstance(message_item, OlivOS.messageAPI.PARA.at)
                    and message_item.data.get('name', None) is None
                ):
                    user_id = str(message_item.data.get('id', ''))
                    if user_id in ['', 'all', 'everyone']:
                        continue
                    cached_name = _get_qq_user_name_from_cache(bot_hash, user_id)
                    if cached_name is not None:
                        message_item.data['name'] = cached_name
                        flag_updated = True

    if flag_backfill:
        # QQ 群/C2C 修正:平台把 @成员 降级为 <qqbot-at-user id=""/> 或
        # <qqbot-at-everyone/>(群聊本无 @全体语义)时,content 中拿不到 openid,
        # 但事件 mentions 数组按出现顺序携带真实 openid,这里按序回填。
        tmp_self_ids = set()
        if self_ids is not None:
            tmp_self_ids = {str(self_id) for self_id in self_ids if self_id is not None}
        used_ids = set()
        for message_item in message_data:
            if isinstance(message_item, OlivOS.messageAPI.PARA.at):
                user_id = str(message_item.data.get('id', ''))
                if user_id not in ['', 'all', 'everyone']:
                    used_ids.add(user_id)
        candidate_ids = [
            mention_id
            for mention_id in _get_qq_ordered_mention_ids(mentions)
            if mention_id not in used_ids and mention_id not in tmp_self_ids
        ]
        placeholder_paras = [
            message_item
            for message_item in message_data
            if isinstance(message_item, OlivOS.messageAPI.PARA.at)
            and str(message_item.data.get('id', '')) == ''
        ]
        degraded_all_paras = [
            message_item
            for message_item in message_data
            if isinstance(message_item, OlivOS.messageAPI.PARA.at)
            and str(message_item.data.get('id', '')) in ['all', 'everyone']
        ]
        # 空 id 占位:能填多少填多少,按出现顺序对应 mentions 顺序。
        for message_item in placeholder_paras:
            if len(candidate_ids) == 0:
                break
            message_item.data['id'] = candidate_ids.pop(0)
            username = get_mention_username(message_item.data['id'])
            if username is not None and message_item.data.get('name', None) is None:
                message_item.data['name'] = username
            flag_updated = True
        # 降级成 all 的 at:仅在数量与剩余 mentions 完全对应时按序回填,
        # 数量对不上时保持原样,避免误改(保守处理)。
        if (
            len(degraded_all_paras) > 0
            and len(candidate_ids) > 0
            and len(degraded_all_paras) == len(candidate_ids)
        ):
            for message_item in degraded_all_paras:
                message_item.data['id'] = candidate_ids.pop(0)
                username = get_mention_username(message_item.data['id'])
                if username is not None and message_item.data.get('name', None) is None:
                    message_item.data['name'] = username
            flag_updated = True
        # 未能回填的空 id 占位段没有任何可用语义,直接清理,避免误当 at 全体。
        tmp_message_data = []
        for message_item in message_data:
            if (
                isinstance(message_item, OlivOS.messageAPI.PARA.at)
                and str(message_item.data.get('id', '')) == ''
            ):
                flag_updated = True
                continue
            tmp_message_data.append(message_item)
        message_data = tmp_message_data

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
    if plugin_event_bot_hash not in sdkSelfInfo:
        tmp_bot_info = bot_info_T(
            target_event.sdk_event.base_info['self_id'],
            target_event.sdk_event.base_info['token']
        )
        api_msg_obj = API.getMe(tmp_bot_info)
        try:
            api_msg_obj.do_api('GET')
            api_res_json = json.loads(api_msg_obj.res)
            if (
                type(api_res_json) is dict
                and 'id' in api_res_json
                and 'username' in api_res_json
            ):
                sdkSelfInfo[plugin_event_bot_hash] = api_res_json
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
            tmp_friend_user = {'user_openid': str(user_openid)}
            if isinstance(event_data.get('author', None), dict):
                tmp_friend_user.update(event_data['author'])
            _register_qq_user_info(
                plugin_event_bot_hash,
                tmp_friend_user,
                chat_type='qq_private',
                chat_id=str(user_openid)
            )
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
        message_content, face_data = _get_qq_message_content(event_data)
        structured_message_para = _get_qq_message_para(event_data, plugin_event_bot_hash)
        # 群 AT 事件会移除机器人自身的 @，但保留其后的前导空格。
        if (
            event_type == 'GROUP_AT_MESSAGE_CREATE'
            and isinstance(message_content, str)
        ):
            message_content = message_content.lstrip(' ')
        if structured_message_para is not None:
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                [structured_message_para]
            )
        elif message_content is not None:
            if message_content != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuildv2_string',
                    message_content
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
        _append_qq_message_attachments(
            message_obj,
            event_data.get('attachments', None),
            skip=isinstance(structured_message_para, OlivOS.messageAPI.PARA.forward)
        )
        if message_obj.active:
            # QQ 新版事件使用 group_openid/member_openid，保留旧字段作为兼容回退。
            group_openid = event_data.get(
                'group_openid',
                event_data.get('group_id', None)
            )
            # 先解析机器人自身 openid,供 mentions 回填时排除自身条目。
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
            tmp_self_ids = {str(target_event.sdk_event.base_info['self_id'])}
            if plugin_event_bot_hash in sdkSubSelfInfo:
                tmp_self_ids.add(str(sdkSubSelfInfo[plugin_event_bot_hash]))
            if sub_self_open_id is not None:
                tmp_self_ids.add(str(sub_self_open_id))
            # 发送者与被 @ 用户进用户信息缓存(昵称/角色/union_openid 等)。
            # 角色仅在本条载荷明确携带时更新,缺省不得把缓存里的 admin/owner 冲成 member。
            tmp_author_role = author.get('member_role', None)
            if tmp_author_role not in ['member', 'admin', 'owner']:
                tmp_author_role = None
            _register_qq_user_info(
                plugin_event_bot_hash,
                author,
                role=tmp_author_role,
                chat_type='qq_group',
                chat_id=group_openid
            )
            _register_qq_user_info_from_mentions(
                plugin_event_bot_hash,
                event_data.get('mentions', None),
                chat_type='qq_group',
                chat_id=group_openid
            )
            _apply_qq_message_mentions(
                message_obj,
                event_data.get('mentions', None),
                self_ids=tmp_self_ids,
                flag_backfill=True,
                bot_hash=plugin_event_bot_hash
            )
            reference_message_id = _get_qq_reference_message_id(
                plugin_event_bot_hash,
                'qq_group',
                group_openid,
                event_data
            )
            _apply_qq_message_reference(message_obj, reference_message_id)
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
            target_event.data.sender['nickname'] = _get_qq_author_name_cached(
                plugin_event_bot_hash, author, member_openid
            )
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
                _get_qq_message_event_extend(event_type, event_data, face_data)
            )
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
            if sub_self_open_id is not None:
                target_event.data.extend['sub_self_open_id'] = sub_self_open_id
            if reference_message_id is not None:
                target_event.data.extend['qq_reference_message_id'] = str(reference_message_id)
            _register_qq_rx_message(
                plugin_event_bot_hash,
                'qq_group',
                group_openid,
                event_data.get('id', None),
                message_obj=message_obj,
                raw_content=event_data.get('content', None),
                sender_id=member_openid,
                sender_name=target_event.data.sender['nickname'],
                timestamp=event_data.get('timestamp', None),
                msg_idx=_parse_qq_message_scene_ext(
                    event_data.get('message_scene', None)
                ).get('msg_idx', None)
            )
    elif target_event.sdk_event.payload.data.t == 'C2C_MESSAGE_CREATE':
        author = event_data.get('author', {})
        message_obj = None
        message_content, face_data = _get_qq_message_content(event_data)
        structured_message_para = _get_qq_message_para(event_data, plugin_event_bot_hash)
        if structured_message_para is not None:
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                [structured_message_para]
            )
        elif message_content is not None:
            if message_content != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'qqGuildv2_string',
                    message_content
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
        _append_qq_message_attachments(
            message_obj,
            event_data.get('attachments', None),
            skip=isinstance(structured_message_para, OlivOS.messageAPI.PARA.forward)
        )
        if message_obj.active:
            tmp_self_ids = {str(target_event.sdk_event.base_info['self_id'])}
            if plugin_event_bot_hash in sdkSubSelfInfo:
                tmp_self_ids.add(str(sdkSubSelfInfo[plugin_event_bot_hash]))
            # C2C 新版事件的用户标识为 author.user_openid。
            user_openid = author.get(
                'user_openid',
                author.get('id', None)
            )
            _register_qq_user_info(
                plugin_event_bot_hash,
                author,
                chat_type='qq_private',
                chat_id=user_openid
            )
            _register_qq_user_info_from_mentions(
                plugin_event_bot_hash,
                event_data.get('mentions', None),
                chat_type='qq_private',
                chat_id=user_openid
            )
            _apply_qq_message_mentions(
                message_obj,
                event_data.get('mentions', None),
                self_ids=tmp_self_ids,
                flag_backfill=True,
                bot_hash=plugin_event_bot_hash
            )
            reference_message_id = _get_qq_reference_message_id(
                plugin_event_bot_hash,
                'qq_private',
                user_openid,
                event_data
            )
            _apply_qq_message_reference(message_obj, reference_message_id)
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
            target_event.data.sender['nickname'] = _get_qq_author_name_cached(
                plugin_event_bot_hash, author, user_openid
            )
            target_event.data.sender['id'] = target_event.data.sender['user_id']
            target_event.data.sender['name'] = target_event.data.sender['nickname']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.sender['role'] = 'member'
            target_event.data.extend['flag_from_direct'] = True
            target_event.data.extend['flag_from_qq'] = True
            target_event.data.extend['reply_msg_id'] = event_data.get('id', None)
            target_event.data.extend.update(
                _get_qq_message_event_extend(event_type, event_data, face_data)
            )
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
            if reference_message_id is not None:
                target_event.data.extend['qq_reference_message_id'] = str(reference_message_id)
            _register_qq_rx_message(
                plugin_event_bot_hash,
                'qq_private',
                user_openid,
                event_data.get('id', None),
                message_obj=message_obj,
                raw_content=event_data.get('content', None),
                sender_id=user_openid,
                sender_name=target_event.data.sender['nickname'],
                timestamp=event_data.get('timestamp', None),
                msg_idx=_parse_qq_message_scene_ext(
                    event_data.get('message_scene', None)
                ).get('msg_idx', None)
            )
    elif target_event.sdk_event.payload.data.t in [
        'MESSAGE_CREATE',
        'AT_MESSAGE_CREATE'
    ]:
        author = event_data.get('author', {})
        message_content, face_data = _get_qq_message_content(event_data)
        message_obj = None
        structured_message_para = _get_qq_message_para(event_data, plugin_event_bot_hash)
        if structured_message_para is not None:
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                [structured_message_para]
            )
        elif message_content is not None:
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
        _append_qq_message_attachments(
            message_obj,
            event_data.get('attachments', None),
            skip=isinstance(structured_message_para, OlivOS.messageAPI.PARA.forward)
        )
        if message_obj.active:
            author_id = author.get('id', None)
            tmp_member_obj = event_data.get('member', None)
            tmp_author_role = None
            if isinstance(tmp_member_obj, dict) and isinstance(tmp_member_obj.get('roles', None), list):
                tmp_author_role = _get_qq_guild_sender_role(tmp_member_obj)
            _register_qq_user_info(
                plugin_event_bot_hash,
                author,
                role=tmp_author_role,
                chat_type='guild_channel',
                chat_id=event_data.get('channel_id', None)
            )
            _register_qq_user_info_from_mentions(
                plugin_event_bot_hash,
                event_data.get('mentions', None),
                chat_type='guild_channel',
                chat_id=event_data.get('channel_id', None)
            )
            _apply_qq_message_mentions(
                message_obj,
                event_data.get('mentions', None),
                bot_hash=plugin_event_bot_hash
            )
            # 频道消息直接携带 message_reference.message_id,与 OneBot reply 段对齐。
            reference_message_id = _get_qq_reference_message_id(
                plugin_event_bot_hash,
                'guild_channel',
                event_data.get('channel_id', None),
                event_data
            )
            _apply_qq_message_reference(message_obj, reference_message_id)
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
                _get_qq_message_event_extend(event_type, event_data, face_data)
            )
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
            if reference_message_id is not None:
                target_event.data.extend['qq_reference_message_id'] = str(reference_message_id)
            _register_qq_rx_message(
                plugin_event_bot_hash,
                'guild_channel',
                event_data.get('channel_id', None),
                event_data.get('id', None),
                message_obj=message_obj,
                raw_content=event_data.get('content', None),
                sender_id=author_id,
                sender_name=target_event.data.sender['nickname'],
                timestamp=event_data.get('timestamp', None),
                channel_id=event_data.get('channel_id', None)
            )
    elif target_event.sdk_event.payload.data.t == 'DIRECT_MESSAGE_CREATE':
        author = event_data.get('author', {})
        message_obj = None
        message_content, face_data = _get_qq_message_content(event_data)
        structured_message_para = _get_qq_message_para(event_data, plugin_event_bot_hash)
        if structured_message_para is not None:
            message_obj = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                [structured_message_para]
            )
        elif message_content is not None:
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
        _append_qq_message_attachments(
            message_obj,
            event_data.get('attachments', None),
            skip=isinstance(structured_message_para, OlivOS.messageAPI.PARA.forward)
        )
        if message_obj.active:
            author_id = author.get('id', None)
            _register_qq_user_info(
                plugin_event_bot_hash,
                author,
                chat_type='guild_private',
                chat_id=event_data.get('channel_id', None)
            )
            _register_qq_user_info_from_mentions(
                plugin_event_bot_hash,
                event_data.get('mentions', None),
                chat_type='guild_private',
                chat_id=event_data.get('channel_id', None)
            )
            _apply_qq_message_mentions(
                message_obj,
                event_data.get('mentions', None),
                bot_hash=plugin_event_bot_hash
            )
            reference_message_id = _get_qq_reference_message_id(
                plugin_event_bot_hash,
                'guild_private',
                event_data.get('channel_id', None),
                event_data
            )
            _apply_qq_message_reference(message_obj, reference_message_id)
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
                _get_qq_message_event_extend(event_type, event_data, face_data)
            )
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
            if reference_message_id is not None:
                target_event.data.extend['qq_reference_message_id'] = str(reference_message_id)
            _register_qq_rx_message(
                plugin_event_bot_hash,
                'guild_private',
                event_data.get('channel_id', None),
                event_data.get('id', None),
                message_obj=message_obj,
                raw_content=event_data.get('content', None),
                sender_id=author_id,
                sender_name=target_event.data.sender['nickname'],
                timestamp=event_data.get('timestamp', None),
                channel_id=event_data.get('channel_id', None)
            )
    elif target_event.sdk_event.payload.data.t in [
        'GUILD_MEMBER_ADD',
        'GUILD_MEMBER_REMOVE'
    ]:
        # 频道成员进出 -> OlivOS group_member_increase/decrease(group/host 维度均取 guild_id)
        if not isinstance(event_data, dict):
            event_data = {}
        member_user = event_data.get('user', {})
        if not isinstance(member_user, dict):
            member_user = {}
        member_user_id = str(member_user.get('id', ''))
        member_guild_id = str(event_data.get('guild_id', ''))
        member_operator_id = str(event_data.get('op_user_id', '') or member_user_id)
        _register_qq_user_info(
            plugin_event_bot_hash,
            member_user,
            chat_type='guild',
            chat_id=member_guild_id
        )
        flag_increase = target_event.sdk_event.payload.data.t == 'GUILD_MEMBER_ADD'
        target_event.active = True
        if flag_increase:
            target_event.plugin_info['func_type'] = 'group_member_increase'
            target_event.data = target_event.group_member_increase(
                member_guild_id,
                member_operator_id,
                member_user_id,
                host_id=member_guild_id,
                action='approve'
            )
        else:
            target_event.plugin_info['func_type'] = 'group_member_decrease'
            target_event.data = target_event.group_member_decrease(
                member_guild_id,
                member_operator_id,
                member_user_id,
                host_id=member_guild_id,
                action='leave' if member_operator_id == member_user_id else 'kick'
            )
        target_event.data.extend = {
            'flag_from_qq': False,
            'host_group_id': member_guild_id,
            'qq_username': member_user.get('username', None),
            'qq_nick': event_data.get('nick', None),
            'qq_roles': copy.deepcopy(event_data.get('roles', None)),
            'qq_joined_at': event_data.get('joined_at', None)
        }
    elif target_event.sdk_event.payload.data.t in [
        'MESSAGE_DELETE',
        'PUBLIC_MESSAGE_DELETE'
    ]:
        # 频道消息撤回 -> OlivOS group_message_recall(group 维度取 channel_id)
        if not isinstance(event_data, dict):
            event_data = {}
        deleted_message = event_data.get('message', {})
        if not isinstance(deleted_message, dict):
            deleted_message = {}
        deleted_author = deleted_message.get('author', {})
        if not isinstance(deleted_author, dict):
            deleted_author = {}
        recall_op_user = event_data.get('op_user', {})
        if not isinstance(recall_op_user, dict):
            recall_op_user = {}
        recall_author_id = str(deleted_author.get('id', ''))
        recall_operator_id = str(recall_op_user.get('id', '') or recall_author_id)
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message_recall'
        target_event.data = target_event.group_message_recall(
            str(deleted_message.get('channel_id', '')),
            recall_operator_id,
            recall_author_id,
            str(deleted_message.get('id', ''))
        )
        target_event.data.extend = {
            'flag_from_qq': False,
            'flag_from_direct': False,
            'host_group_id': str(deleted_message.get('guild_id', ''))
        }
    elif target_event.sdk_event.payload.data.t == 'DIRECT_MESSAGE_DELETE':
        # 频道私信撤回 -> OlivOS private_message_recall
        if not isinstance(event_data, dict):
            event_data = {}
        deleted_message = event_data.get('message', {})
        if not isinstance(deleted_message, dict):
            deleted_message = {}
        deleted_author = deleted_message.get('author', {})
        if not isinstance(deleted_author, dict):
            deleted_author = {}
        target_event.active = True
        target_event.plugin_info['func_type'] = 'private_message_recall'
        target_event.data = target_event.private_message_recall(
            str(deleted_author.get('id', '')),
            str(deleted_message.get('id', ''))
        )
        target_event.data.extend = {
            'flag_from_qq': False,
            'flag_from_direct': True,
            'host_group_id': str(deleted_message.get('guild_id', ''))
        }
    elif target_event.sdk_event.payload.data.t == 'INTERACTION_CREATE':
        # 互动事件(按钮回调等):对不上 OlivOS 标准事件,留在 SDK 层记录;
        # 后台自动应答 code=0,避免用户端一直转圈提示"操作失败"。
        target_event.active = False
        _record_unhandled_qq_event(
            plugin_event_bot_hash,
            'INTERACTION_CREATE',
            target_event.sdk_event.payload.data.id,
            event_data
        )
        interaction_id = None
        if isinstance(event_data, dict):
            interaction_id = event_data.get('id', None)
        if interaction_id is not None and str(interaction_id) != '':
            tmp_ack_bot_info = bot_info_T(
                target_event.sdk_event.base_info['self_id'],
                target_event.sdk_event.base_info['token']
            )
            threading.Thread(
                target=event_action._ack_interaction_plant,
                args=(tmp_ack_bot_info, str(interaction_id), 0),
                daemon=True
            ).start()
    elif target_event.sdk_event.payload.data.t in qqInternalEventTypes:
        # 其余对不上 OlivOS 标准事件的平台事件:解析后留在 SDK 层环形缓存
        target_event.active = False
        _record_unhandled_qq_event(
            plugin_event_bot_hash,
            target_event.sdk_event.payload.data.t,
            target_event.sdk_event.payload.data.id,
            event_data
        )

    event_id = target_event.sdk_event.payload.data.id
    if (
        target_event.active
        and hasattr(target_event.data, 'extend')
        and type(target_event.data.extend) is dict
    ):
        if event_type not in qqMessageEventTypes:
            target_event.data.extend.update(
                _get_qq_event_extend(event_type, event_data)
            )
        payload_data = target_event.sdk_event.payload.data
        target_event.data.extend.setdefault('qq_event_type', str(event_type))
        if payload_data.op is not None:
            target_event.data.extend['qq_payload_op'] = payload_data.op
        if payload_data.s is not None:
            target_event.data.extend['qq_payload_seq'] = payload_data.s
        if event_id is not None:
            target_event.data.extend['event_id'] = str(event_id)
            target_event.data.extend['qq_payload_id'] = str(event_id)


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
        message_ref_idx = None
        if type(raw_obj) is dict:
            message_id = raw_obj.get('id', message_id)
            timestamp = raw_obj.get('timestamp', None)
            error_message = raw_obj.get('message', raw_obj.get('msg', None))
            if type(raw_obj.get('ext_info', None)) is dict:
                message_ref_idx = raw_obj['ext_info'].get('ref_idx', None)
            if type(raw_obj.get('data', None)) is dict:
                message_id = raw_obj['data'].get('id', message_id)
                timestamp = raw_obj['data'].get('timestamp', timestamp)
                if type(raw_obj['data'].get('ext_info', None)) is dict:
                    message_ref_idx = raw_obj['data']['ext_info'].get(
                        'ref_idx',
                        message_ref_idx
                    )
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
            # 机器人自己发出的消息也进内容缓存:
            # 频道内用户引用机器人消息时,get_msg 凭该缓存取回内容。
            sent_sender_name = None
            sent_self_info = sdkSelfInfo.get(target_event.bot_info.hash, None)
            if isinstance(sent_self_info, dict):
                sent_sender_name = sent_self_info.get('username', None)
            _register_qq_rx_message(
                target_event.bot_info.hash,
                chat_type,
                chat_id,
                message_id,
                content=getattr(api_obj.data, 'content', None),
                raw_content=getattr(api_obj.data, 'content', None),
                sender_id=str(target_event.bot_info.id),
                sender_name=sent_sender_name,
                timestamp=timestamp,
                channel_id=str(chat_id) if chat_type == 'guild_channel' else None,
                msg_idx=message_ref_idx
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
        message_reference = getattr(api_obj.data, 'message_reference', None)
        if chat_type in ['qq_group', 'qq_private'] and isinstance(message_reference, dict):
            reference_message_id = message_reference.get('message_id', None)
            if (
                reference_message_id is not None
                and not str(reference_message_id).startswith('REFIDX_')
            ):
                reference_msg_idx = _resolve_qq_reference_msg_idx(
                    target_event,
                    chat_type,
                    chat_id,
                    reference_message_id
                )
                if reference_msg_idx is not None:
                    message_reference['message_id'] = reference_msg_idx
                else:
                    # 普通 message_id 无法映射为 REFIDX 时只取消可见引用，
                    # 不影响独立的 msg_id 被动回复凭据。
                    api_obj.data.message_reference = None
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
        allow_at_all=True,
        flag_qq=True
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
                    allow_at_all=allow_at_all,
                    flag_qq=flag_qq
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

    def _normalize_guild_markdown(markdown, allow_at_all=True):
        markdown_obj = copy.deepcopy(markdown)
        if isinstance(markdown_obj.get('content', None), str):
            markdown_obj['content'] = markdown_tag.normalize_guild_text(
                markdown_obj['content'],
                allow_at_all=allow_at_all
            )
        params = markdown_obj.get('params', None)
        if isinstance(params, list):
            for param in params:
                if not isinstance(param, dict) or not isinstance(param.get('values', None), list):
                    continue
                param['values'] = [
                    markdown_tag.normalize_guild_text(value, allow_at_all=allow_at_all)
                    if isinstance(value, str)
                    else value
                    for value in param['values']
                ]
        return markdown_obj

    def send_qq_msg(
        target_event,
        chat_id,
        message,
        reply_msg_id=None,
        flag_direct=False,
        quote_msg_id=None,
        event_id=None,
        force_active=False
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
        if force_active:
            # Event.send 是主动发送语义，不能复用当前事件的被动回复凭据。
            msg_id = None
            event_id = None
            allow_active_fallback = False
        else:
            msg_id, event_id = event_action._resolve_qq_passive_ids(
                target_event,
                chat_type,
                chat_id,
                msg_id=reply_msg_id,
                event_id=event_id
            )
            allow_active_fallback = (
                msg_id is not None or event_id is not None
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
            file_name = None
            if (
                isinstance(message_this, OlivOS.messageAPI.PARA.file)
                and message_this.data is not None
            ):
                file_name = message_this.data.get('name', None)
            file_info = event_action.setResourceUploadFast(
                target_event,
                resource_url,
                chat_id,
                type_path=type_path,
                type_chat='qq_users' if flag_direct else 'qq_groups',
                file_name=file_name
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
        if chat_type in ['guild_channel', 'guild_private']:
            markdown = event_action._normalize_guild_markdown(
                markdown,
                allow_at_all=chat_type == 'guild_channel'
            )

        if chat_type in ['qq_group', 'qq_private']:
            msg_id, event_id = event_action._resolve_qq_passive_ids(
                target_event,
                chat_type,
                chat_id,
                msg_id=msg_id,
                event_id=event_id
            )
            allow_active_fallback = (
                msg_id is not None or event_id is not None
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
            None if fallback_used else getattr(this_msg.data, 'msg_id', None),
            flag_direct=flag_direct,
            event_id=None if fallback_used else getattr(this_msg.data, 'event_id', None)
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

    def send_guild_private_msg(
        target_event,
        user_id,
        source_guild_id,
        message,
        quote_msg_id=None
    ):
        """从频道上下文向指定用户主动发起私信。"""
        if user_id is None or str(user_id) == '':
            return event_action._make_local_result(
                'guild_private',
                user_id,
                'send',
                'user_id is required'
            )
        if source_guild_id is None or str(source_guild_id) == '':
            return event_action._make_local_result(
                'guild_private',
                user_id,
                'send',
                'source_guild_id is required'
            )
        dms_result = event_action.create_dms_session(
            target_event,
            user_id,
            source_guild_id
        )
        if not dms_result.get('active', False):
            dms_result['data']['chat_type'] = 'guild_private'
            dms_result['data']['chat_id'] = str(user_id)
            dms_result['data']['operation'] = 'send'
            return dms_result
        response_data = dms_result.get('data', {}).get('response', None)
        direct_guild_id = None
        if isinstance(response_data, dict):
            direct_guild_id = response_data.get('guild_id', None)
        if direct_guild_id is None or str(direct_guild_id) == '':
            return event_action._make_local_result(
                'guild_private',
                user_id,
                'send',
                'create dms session response has no guild_id'
            )
        return event_action.send_msg(
            target_event,
            direct_guild_id,
            message,
            flag_direct=True,
            quote_msg_id=quote_msg_id
        )

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
            allow_at_all=not flag_direct,
            flag_qq=False
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
                        and init_api_do_mapping_for_dict(raw_obj, ['id'], str) is not None
                        and init_api_do_mapping_for_dict(raw_obj, ['username'], str) is not None
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

    def get_msg(target_event, message_id):
        """获取指定消息,返回结构与 OneBot get_msg 对齐。

        优先读消息内容缓存(收到的消息与机器人自己发出的消息都会登记);
        缓存未命中且处于频道上下文时,回源官方"获取指定消息"接口。
        QQ 群/C2C 没有对应官方接口,只能依赖缓存命中。
        """
        res_data = OlivOS.contentAPI.api_result_data_template.get_msg()
        if message_id is None or str(message_id) == '':
            return res_data
        message_id = str(message_id)

        def fill_from_record(record):
            res_data['active'] = True
            res_data['data']['message_id'] = record.get('message_id', message_id)
            res_data['data']['id'] = record.get('message_id', message_id)
            sender_id = record.get('sender_id', None)
            sender_name = record.get('sender_name', None)
            if sender_id is not None:
                res_data['data']['sender']['id'] = str(sender_id)
                res_data['data']['sender']['user_id'] = str(sender_id)
            res_data['data']['sender']['name'] = sender_name
            res_data['data']['sender']['nickname'] = sender_name
            res_data['data']['time'] = record.get('time', -1)
            res_data['data']['message'] = record.get('message', None)
            res_data['data']['raw_message'] = record.get('raw_message', None)

        cached_record = _get_qq_rx_message(target_event.bot_info.hash, message_id)
        if cached_record is not None:
            fill_from_record(cached_record)
            return res_data

        # 缓存未命中:仅频道消息可通过官方接口回源,channel_id 取当前事件上下文。
        target_data = getattr(target_event, 'data', None)
        extend_data = getattr(target_data, 'extend', None)
        if not isinstance(extend_data, dict) or extend_data.get('flag_from_qq', False):
            return res_data
        channel_id = extend_data.get('group_id', None)
        if channel_id is None or str(channel_id) in ['', 'None']:
            channel_id = getattr(target_data, 'group_id', None)
        if channel_id is None or str(channel_id) in ['', 'None']:
            return res_data
        try:
            this_msg = API.getMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.channel_id = str(channel_id)
            this_msg.metadata.message_id = message_id
            this_msg.do_api('GET')
            if (
                this_msg.res_code is None
                or not (200 <= this_msg.res_code < 300)
            ):
                return res_data
            raw_obj = init_api_json(this_msg.res)
            if type(raw_obj) is not dict:
                return res_data
            # 响应为 {"message": {...}} 包装结构,兼容直接返回消息对象的情况。
            msg_data = raw_obj.get('message', raw_obj)
            if type(msg_data) is not dict or msg_data.get('id', None) is None:
                return res_data
            tmp_message_obj = OlivOS.messageAPI.Message_templet(
                'qqGuild_string',
                str(msg_data.get('content', ''))
            )
            tmp_message_obj.mode_rx = 'olivos_para'
            tmp_message_obj.data_raw = tmp_message_obj.data.copy()
            tmp_message_obj.data_raw.extend(
                _get_message_attachments(msg_data.get('attachments', None))
            )
            try:
                tmp_message_obj.init_data()
            except Exception:
                tmp_message_obj.active = False
            tmp_reference = msg_data.get('message_reference', None)
            if isinstance(tmp_reference, dict):
                _apply_qq_message_reference(
                    tmp_message_obj,
                    tmp_reference.get('message_id', None)
                )
            author = msg_data.get('author', {})
            if not isinstance(author, dict):
                author = {}
            # 回源结果登记进缓存,后续同一消息的 get_msg 免请求。
            _register_qq_rx_message(
                target_event.bot_info.hash,
                'guild_channel',
                msg_data.get('channel_id', channel_id),
                msg_data.get('id', None),
                message_obj=tmp_message_obj if tmp_message_obj.active else None,
                content=None if tmp_message_obj.active else str(msg_data.get('content', '')),
                raw_content=msg_data.get('content', None),
                sender_id=author.get('id', None),
                sender_name=_get_qq_author_name(author),
                timestamp=msg_data.get('timestamp', None),
                channel_id=msg_data.get('channel_id', channel_id)
            )
            fetched_record = _get_qq_rx_message(
                target_event.bot_info.hash,
                str(msg_data.get('id', message_id))
            )
            if fetched_record is not None:
                fill_from_record(fetched_record)
        except Exception:
            traceback.print_exc()
        return res_data

    def get_forward_msg(target_event, message_id):
        """获取收到的 QQ 合并转发节点,返回与 OneBot 对齐的结果。"""
        res_data = OlivOS.contentAPI.api_result_data_template.get_forward_msg()
        messages = _get_qq_forward_message(
            target_event.bot_info.hash,
            message_id
        )
        if messages is not None:
            res_data['active'] = True
            res_data['data']['messages'] = messages
        return res_data

    # ============ QQ 文件上传 ============
    def _make_resource_upload_result(chat_type, chat_id, file_info, operation):
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['active'] = file_info is not None
        res_data['data'].update({
            'operation': operation,
            'chat_type': chat_type,
            'chat_id': None if chat_id is None else str(chat_id),
            'file_info': file_info
        })
        return res_data

    def _get_qq_upload_context_error(target_event, flag_direct):
        target_data = getattr(target_event, 'data', None)
        extend_data = getattr(target_data, 'extend', None)
        if not isinstance(extend_data, dict) or 'flag_from_qq' not in extend_data:
            return None
        if not extend_data.get('flag_from_qq', False):
            return 'QQ group/C2C file upload is unavailable in a guild context'
        if extend_data.get('flag_from_direct', False) != flag_direct:
            return 'current QQ event chat type does not match the file upload target'
        return None

    def upload_group_file(target_event, group_id, file, name='', folder_id=None):
        # QQ 群文件接口不支持 OneBot 的 folder_id，保留参数仅为统一 API 签名。
        context_error = event_action._get_qq_upload_context_error(
            target_event,
            flag_direct=False
        )
        if context_error is not None:
            return event_action._make_local_result(
                'qq_group', group_id, 'upload_group_file', context_error
            )
        file_info = event_action.setResourceUploadFast(
            target_event,
            file,
            group_id,
            type_path='files',
            type_chat='qq_groups',
            file_name=name,
            flag_send_msg=True
        )
        return event_action._make_resource_upload_result(
            'qq_group', group_id, file_info, 'upload_group_file'
        )

    def upload_private_file(target_event, user_id, file, name):
        context_error = event_action._get_qq_upload_context_error(
            target_event,
            flag_direct=True
        )
        if context_error is not None:
            return event_action._make_local_result(
                'qq_private', user_id, 'upload_private_file', context_error
            )
        file_info = event_action.setResourceUploadFast(
            target_event,
            file,
            user_id,
            type_path='files',
            type_chat='qq_users',
            file_name=name,
            flag_send_msg=True
        )
        return event_action._make_resource_upload_result(
            'qq_private', user_id, file_info, 'upload_private_file'
        )

    # ============ 通用原始接口调用结果包装 ============
    # 平台接口返回体差异较大(对象/数组/空体),统一包装为 universal_result,
    # 原始响应放在 data.response,由调用方按文档自行取字段。
    def _make_raw_api_result(api_obj, operation):
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        raw_obj = None
        if api_obj.res is not None:
            try:
                raw_obj = json.loads(api_obj.res)
            except Exception:
                raw_obj = None
        api_code = None
        error_message = None
        if type(raw_obj) is dict:
            api_code = event_action._get_api_error_code(raw_obj)
            error_message = raw_obj.get('message', raw_obj.get('msg', None))
        flag_success = (
            api_obj.res_code is not None
            and 200 <= api_obj.res_code < 300
            and api_code in [None, 0]
        )
        res_data['active'] = flag_success
        res_data['data'].update({
            'operation': str(operation),
            'http_status': api_obj.res_code,
            'error_code': api_code,
            'error': None if flag_success else error_message,
            'response': raw_obj if raw_obj is not None else api_obj.res
        })
        return res_data

    def _run_raw_api(api_obj, operation, req_type='GET'):
        api_obj.do_api(req_type)
        return event_action._make_raw_api_result(api_obj, operation)

    # ============ 频道:频道/子频道 ============
    def get_guild_info(target_event, guild_id):
        this_msg = API.getGuild(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        return event_action._run_raw_api(this_msg, 'get_guild_info', 'GET')

    def get_me_guild_list(target_event, before=None, after=None, limit=None):
        this_msg = API.getMeGuilds(get_SDK_bot_info_from_Event(target_event))
        this_msg.query = {'before': before, 'after': after, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_me_guild_list', 'GET')

    def get_guild_channel_list(target_event, guild_id):
        this_msg = API.getGuildChannels(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        return event_action._run_raw_api(this_msg, 'get_guild_channel_list', 'GET')

    def get_channel_info(target_event, channel_id):
        this_msg = API.getChannel(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'get_channel_info', 'GET')

    def _raw_response(raw_result):
        if not isinstance(raw_result, dict):
            return None
        response = raw_result.get('data', {}).get('response', None)
        return response

    def _standard_group_info(raw_result, fallback_id=None):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_info()
        response = event_action._raw_response(raw_result)
        if not isinstance(raw_result, dict) or not raw_result.get('active', False) or not isinstance(response, dict):
            return res_data
        group_id = response.get('id', fallback_id)
        res_data['active'] = group_id is not None
        res_data['data']['id'] = None if group_id is None else str(group_id)
        res_data['data']['name'] = response.get('name', response.get('title', None))
        res_data['data']['memo'] = response.get('topic', response.get('description', None))
        res_data['data']['max_member_count'] = response.get(
            'max_member_count', response.get('max_members_count', 0)
        )
        res_data['data']['extra'] = copy.deepcopy(response)
        return res_data

    def _standard_group_list(raw_result):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_list()
        response = event_action._raw_response(raw_result)
        if not isinstance(raw_result, dict) or not raw_result.get('active', False):
            return res_data
        if isinstance(response, dict):
            response_items = response.get('data', response.get('items', response.get('channels', None)))
            if isinstance(response_items, dict):
                response_items = response_items.get('items', response_items.get('channels', None))
        else:
            response_items = response
        if not isinstance(response_items, list):
            return res_data
        res_data['active'] = True
        for item in response_items:
            if not isinstance(item, dict):
                continue
            item_id = item.get('id', None)
            if item_id is None:
                continue
            res_data['data'].append({
                'id': str(item_id),
                'name': item.get('name', item.get('title', None)),
                'memo': item.get('topic', item.get('description', None)),
                'max_member_count': item.get('max_member_count', item.get('max_members_count', 0)),
                'extra': copy.deepcopy(item)
            })
        return res_data

    def _standard_group_member_list(raw_result, fallback_group_id=None):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_list()
        response = event_action._raw_response(raw_result)
        if not isinstance(raw_result, dict) or not raw_result.get('active', False):
            return res_data
        if isinstance(response, dict):
            response_items = response.get('data', response.get('members', response.get('items', None)))
            if isinstance(response_items, dict):
                response_items = response_items.get(
                    'members',
                    response_items.get('items', response_items.get('data', None))
                )
        else:
            response_items = response
        if not isinstance(response_items, list):
            return res_data
        res_data['active'] = True
        for item in response_items:
            if not isinstance(item, dict):
                continue
            user_info = item.get('user', None)
            if not isinstance(user_info, dict):
                user_info = {}
            user_id = item.get(
                'user_id',
                item.get('member_openid', item.get('id', user_info.get('id', None)))
            )
            if user_id is None:
                continue
            member = OlivOS.contentAPI.api_result_data_template.get_group_member_info_strip()
            member['id'] = str(user_id)
            member['user_id'] = str(user_id)
            member['group_id'] = None if fallback_group_id is None else str(fallback_group_id)
            member['name'] = item.get(
                'username',
                item.get(
                    'nickname',
                    item.get('name', user_info.get('username', user_info.get('nickname', None)))
                )
            )
            member['card'] = item.get('nick', item.get('card', member['name']))
            member['role'] = item.get('role', None)
            member['extra'] = copy.deepcopy(item)
            res_data['data'].append(member)
        return res_data

    def get_guild_info_standard(target_event, guild_id):
        return event_action._standard_group_info(
            event_action.get_guild_info(target_event, guild_id),
            fallback_id=guild_id
        )

    def get_guild_list_standard(target_event, before=None, after=None, limit=None):
        return event_action._standard_group_list(
            event_action.get_me_guild_list(target_event, before, after, limit)
        )

    def get_guild_channel_list_standard(target_event, guild_id):
        return event_action._standard_group_list(
            event_action.get_guild_channel_list(target_event, guild_id)
        )

    def get_channel_info_standard(target_event, channel_id):
        return event_action._standard_group_info(
            event_action.get_channel_info(target_event, channel_id),
            fallback_id=channel_id
        )

    def get_guild_member_list_standard(target_event, guild_id, after=None, limit=None):
        return event_action._standard_group_member_list(
            event_action.get_guild_member_list(target_event, guild_id, after, limit),
            fallback_group_id=guild_id
        )

    def get_qq_group_member_list_standard(target_event, group_openid, limit=None, start_index=None):
        return event_action._standard_group_member_list(
            event_action.get_qq_group_member_list(target_event, group_openid, limit, start_index),
            fallback_group_id=group_openid
        )

    def create_channel(target_event, guild_id, name, type=None, sub_type=None,
                       position=None, parent_id=None, private_type=None,
                       private_user_ids=None, speak_permission=None, application_id=None):
        this_msg = API.createChannel(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.name = str(name)
        this_msg.data.type = type
        this_msg.data.sub_type = sub_type
        this_msg.data.position = position
        this_msg.data.parent_id = parent_id
        this_msg.data.private_type = private_type
        this_msg.data.private_user_ids = private_user_ids
        this_msg.data.speak_permission = speak_permission
        this_msg.data.application_id = application_id
        return event_action._run_raw_api(this_msg, 'create_channel', 'POST')

    def patch_channel(target_event, channel_id, name=None, position=None,
                      parent_id=None, private_type=None, speak_permission=None):
        this_msg = API.patchChannel(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.data.name = name
        this_msg.data.position = position
        this_msg.data.parent_id = parent_id
        this_msg.data.private_type = private_type
        this_msg.data.speak_permission = speak_permission
        return event_action._run_raw_api(this_msg, 'patch_channel', 'PATCH')

    def delete_channel(target_event, channel_id):
        this_msg = API.deleteChannel(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'delete_channel', 'DELETE')

    def get_channel_online_nums(target_event, channel_id):
        this_msg = API.getChannelOnlineNums(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'get_channel_online_nums', 'GET')

    # ============ 频道:成员 ============
    def get_guild_member_list(target_event, guild_id, after=None, limit=None):
        this_msg = API.getGuildMembers(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.query = {'after': after, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_guild_member_list', 'GET')

    def get_guild_role_member_list(target_event, guild_id, role_id, start_index=None, limit=None):
        this_msg = API.getGuildRoleMembers(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.role_id = str(role_id)
        this_msg.query = {'start_index': start_index, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_guild_role_member_list', 'GET')

    def get_guild_member_info(target_event, guild_id, user_id):
        this_msg = API.getGuildMember(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        return event_action._run_raw_api(this_msg, 'get_guild_member_info', 'GET')

    def delete_guild_member(target_event, guild_id, user_id,
                            add_blacklist=None, delete_history_msg_days=None):
        this_msg = API.deleteGuildMember(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.data.add_blacklist = add_blacklist
        this_msg.data.delete_history_msg_days = delete_history_msg_days
        return event_action._run_raw_api(this_msg, 'delete_guild_member', 'DELETE')

    # ============ 频道:身份组 ============
    def get_guild_role_list(target_event, guild_id):
        this_msg = API.getGuildRoles(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        return event_action._run_raw_api(this_msg, 'get_guild_role_list', 'GET')

    def create_guild_role(target_event, guild_id, name=None, color=None, hoist=None):
        this_msg = API.createGuildRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.name = name
        this_msg.data.color = color
        this_msg.data.hoist = hoist
        return event_action._run_raw_api(this_msg, 'create_guild_role', 'POST')

    def patch_guild_role(target_event, guild_id, role_id, name=None, color=None, hoist=None):
        this_msg = API.patchGuildRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.role_id = str(role_id)
        this_msg.data.name = name
        this_msg.data.color = color
        this_msg.data.hoist = hoist
        return event_action._run_raw_api(this_msg, 'patch_guild_role', 'PATCH')

    def delete_guild_role(target_event, guild_id, role_id):
        this_msg = API.deleteGuildRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.role_id = str(role_id)
        return event_action._run_raw_api(this_msg, 'delete_guild_role', 'DELETE')

    def set_guild_member_role(target_event, guild_id, user_id, role_id, channel_id=None):
        # 操作 5 号(子频道管理员)身份组时必须传 channel_id
        this_msg = API.putGuildMemberRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.metadata.role_id = str(role_id)
        if channel_id is not None:
            this_msg.data.channel = {'id': str(channel_id)}
        return event_action._run_raw_api(this_msg, 'set_guild_member_role', 'PUT')

    def unset_guild_member_role(target_event, guild_id, user_id, role_id, channel_id=None):
        this_msg = API.deleteGuildMemberRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.metadata.role_id = str(role_id)
        if channel_id is not None:
            this_msg.data.channel = {'id': str(channel_id)}
        return event_action._run_raw_api(this_msg, 'unset_guild_member_role', 'DELETE')

    # ============ 频道:子频道权限 ============
    def get_channel_member_permissions(target_event, channel_id, user_id):
        this_msg = API.getChannelMemberPermissions(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.user_id = str(user_id)
        return event_action._run_raw_api(this_msg, 'get_channel_member_permissions', 'GET')

    def set_channel_member_permissions(target_event, channel_id, user_id, add=None, remove=None):
        this_msg = API.putChannelMemberPermissions(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.data.add = None if add is None else str(add)
        this_msg.data.remove = None if remove is None else str(remove)
        return event_action._run_raw_api(this_msg, 'set_channel_member_permissions', 'PUT')

    def get_channel_role_permissions(target_event, channel_id, role_id):
        this_msg = API.getChannelRolePermissions(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.role_id = str(role_id)
        return event_action._run_raw_api(this_msg, 'get_channel_role_permissions', 'GET')

    def set_channel_role_permissions(target_event, channel_id, role_id, add=None, remove=None):
        this_msg = API.putChannelRolePermissions(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.role_id = str(role_id)
        this_msg.data.add = None if add is None else str(add)
        this_msg.data.remove = None if remove is None else str(remove)
        return event_action._run_raw_api(this_msg, 'set_channel_role_permissions', 'PUT')

    # ============ 频道:消息列表/私信会话 ============
    def get_channel_message_list(target_event, channel_id, around=None, before=None, after=None, limit=None):
        this_msg = API.getChannelMessages(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.query = {'around': around, 'before': before, 'after': after, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_channel_message_list', 'GET')

    def create_dms_session(target_event, recipient_id, source_guild_id):
        # 返回 data.response 中含 guild_id(私信会话凭据),可直接用于 send_msg 的 flag_direct 通道
        this_msg = API.createDirectMessageSession(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.recipient_id = str(recipient_id)
        this_msg.data.source_guild_id = str(source_guild_id)
        return event_action._run_raw_api(this_msg, 'create_dms_session', 'POST')

    # ============ 频道:禁言 ============
    def set_guild_mute_all(target_event, guild_id, mute_seconds=None, mute_end_timestamp=None):
        # mute_seconds='0' 或 mute_end_timestamp='0' 表示解除全员禁言
        this_msg = API.patchGuildMute(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.mute_seconds = None if mute_seconds is None else str(mute_seconds)
        this_msg.data.mute_end_timestamp = None if mute_end_timestamp is None else str(mute_end_timestamp)
        return event_action._run_raw_api(this_msg, 'set_guild_mute_all', 'PATCH')

    def set_guild_members_mute(target_event, guild_id, user_ids, mute_seconds=None, mute_end_timestamp=None):
        # 批量成员禁言;成功时 data.response.user_ids 为生效的成员列表
        this_msg = API.patchGuildMute(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.user_ids = [str(user_id) for user_id in user_ids]
        this_msg.data.mute_seconds = None if mute_seconds is None else str(mute_seconds)
        this_msg.data.mute_end_timestamp = None if mute_end_timestamp is None else str(mute_end_timestamp)
        return event_action._run_raw_api(this_msg, 'set_guild_members_mute', 'PATCH')

    def set_guild_member_mute(target_event, guild_id, user_id, mute_seconds=None, mute_end_timestamp=None):
        this_msg = API.patchGuildMemberMute(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.data.mute_seconds = None if mute_seconds is None else str(mute_seconds)
        this_msg.data.mute_end_timestamp = None if mute_end_timestamp is None else str(mute_end_timestamp)
        return event_action._run_raw_api(this_msg, 'set_guild_member_mute', 'PATCH')

    # ============ 频道:公告/精华 ============
    def create_guild_announce(target_event, guild_id, message_id=None, channel_id=None,
                              announces_type=None, recommend_channels=None):
        this_msg = API.createAnnounce(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.message_id = message_id
        this_msg.data.channel_id = channel_id
        this_msg.data.announces_type = announces_type
        this_msg.data.recommend_channels = recommend_channels
        return event_action._run_raw_api(this_msg, 'create_guild_announce', 'POST')

    def delete_guild_announce(target_event, guild_id, message_id='all'):
        this_msg = API.deleteAnnounce(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.message_id = str(message_id)
        return event_action._run_raw_api(this_msg, 'delete_guild_announce', 'DELETE')

    def set_pins_message(target_event, channel_id, message_id):
        this_msg = API.putPinsMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        return event_action._run_raw_api(this_msg, 'set_pins_message', 'PUT')

    def delete_pins_message(target_event, channel_id, message_id='all'):
        this_msg = API.deletePinsMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        return event_action._run_raw_api(this_msg, 'delete_pins_message', 'DELETE')

    def get_pins_message(target_event, channel_id):
        this_msg = API.getPinsMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'get_pins_message', 'GET')

    def get_essence_msg_list(target_event, channel_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_essence_msg_list()
        raw_result = event_action.get_pins_message(target_event, channel_id)
        if not raw_result.get('active', False):
            return res_data
        raw_response = raw_result.get('data', {}).get('response', None)
        if not isinstance(raw_response, dict):
            return res_data
        message_ids = raw_response.get('message_ids', None)
        if not isinstance(message_ids, list):
            return res_data
        response_channel_id = raw_response.get('channel_id', channel_id)
        res_data['active'] = True
        for message_id in message_ids:
            res_data['data'].append({
                'sender_id': None,
                'sender_nick': None,
                'sender_time': None,
                'operator_id': None,
                'operator_nick': None,
                'operator_time': None,
                'message_id': str(message_id),
                'message': None,
                'wording': None,
                'extra': {
                    'channel_id': None if response_channel_id is None else str(response_channel_id),
                    'qq_response': copy.deepcopy(raw_response)
                }
            })
        return res_data

    # ============ 频道:日程 ============
    def get_schedule_list(target_event, channel_id, since=None):
        this_msg = API.getSchedules(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.query = {'since': since}
        return event_action._run_raw_api(this_msg, 'get_schedule_list', 'GET')

    def get_schedule_info(target_event, channel_id, schedule_id):
        this_msg = API.getSchedule(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.schedule_id = str(schedule_id)
        return event_action._run_raw_api(this_msg, 'get_schedule_info', 'GET')

    def create_schedule(target_event, channel_id, schedule):
        # schedule: dict,Schedule 对象(不含 id),字段见官方文档
        this_msg = API.createSchedule(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.data.schedule = schedule
        return event_action._run_raw_api(this_msg, 'create_schedule', 'POST')

    def patch_schedule(target_event, channel_id, schedule_id, schedule):
        this_msg = API.patchSchedule(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.schedule_id = str(schedule_id)
        this_msg.data.schedule = schedule
        return event_action._run_raw_api(this_msg, 'patch_schedule', 'PATCH')

    def delete_schedule(target_event, channel_id, schedule_id):
        this_msg = API.deleteSchedule(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.schedule_id = str(schedule_id)
        return event_action._run_raw_api(this_msg, 'delete_schedule', 'DELETE')

    # ============ 频道:表情表态 ============
    def set_message_reaction(target_event, channel_id, message_id, emoji_id, emoji_type=1):
        # emoji_type: 1系统表情 2emoji;emoji_id 见官方表情对照表
        this_msg = API.putMessageReaction(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        this_msg.metadata.emoji_type = str(emoji_type)
        this_msg.metadata.emoji_id = str(emoji_id)
        return event_action._run_raw_api(this_msg, 'set_message_reaction', 'PUT')

    def delete_message_reaction(target_event, channel_id, message_id, emoji_id, emoji_type=1):
        this_msg = API.deleteMessageReaction(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        this_msg.metadata.emoji_type = str(emoji_type)
        this_msg.metadata.emoji_id = str(emoji_id)
        return event_action._run_raw_api(this_msg, 'delete_message_reaction', 'DELETE')

    def get_message_reaction_user_list(target_event, channel_id, message_id, emoji_id,
                                       emoji_type=1, cookie=None, limit=None):
        this_msg = API.getMessageReactionUsers(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        this_msg.metadata.emoji_type = str(emoji_type)
        this_msg.metadata.emoji_id = str(emoji_id)
        this_msg.query = {'cookie': cookie, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_message_reaction_user_list', 'GET')

    # ============ 频道:音频/麦克风 ============
    def set_audio_control(target_event, channel_id, status, audio_url=None, text=None):
        # status: 0开始 1暂停 2继续 3停止
        this_msg = API.postAudioControl(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.data.status = int(status)
        this_msg.data.audio_url = audio_url
        this_msg.data.text = text
        return event_action._run_raw_api(this_msg, 'set_audio_control', 'POST')

    def set_mic_on(target_event, channel_id):
        this_msg = API.putMic(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'set_mic_on', 'PUT')

    def set_mic_off(target_event, channel_id):
        this_msg = API.deleteMic(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'set_mic_off', 'DELETE')

    # ============ 频道:帖子(论坛,私域) ============
    def get_thread_list(target_event, channel_id):
        this_msg = API.getThreads(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'get_thread_list', 'GET')

    def get_thread_info(target_event, channel_id, thread_id):
        this_msg = API.getThread(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.thread_id = str(thread_id)
        return event_action._run_raw_api(this_msg, 'get_thread_info', 'GET')

    def create_thread(target_event, channel_id, title, content, format=1):
        # format: 1文本 2HTML 3Markdown 4JSON
        this_msg = API.putThread(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.data.title = str(title)
        this_msg.data.content = str(content)
        this_msg.data.format = int(format)
        return event_action._run_raw_api(this_msg, 'create_thread', 'PUT')

    def delete_thread(target_event, channel_id, thread_id):
        this_msg = API.deleteThread(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.thread_id = str(thread_id)
        return event_action._run_raw_api(this_msg, 'delete_thread', 'DELETE')

    # ============ 频道:API 权限 ============
    def get_guild_api_permission(target_event, guild_id):
        this_msg = API.getGuildApiPermission(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        return event_action._run_raw_api(this_msg, 'get_guild_api_permission', 'GET')

    def demand_guild_api_permission(target_event, guild_id, channel_id, api_path, api_method, desc=''):
        this_msg = API.demandGuildApiPermission(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.channel_id = str(channel_id)
        this_msg.data.api_identify = {'path': str(api_path), 'method': str(api_method)}
        this_msg.data.desc = str(desc)
        return event_action._run_raw_api(this_msg, 'demand_guild_api_permission', 'POST')

    # ============ 互动回调应答 ============
    def _ack_interaction_plant(bot_info, interaction_id, code=0):
        # 供事件层后台线程直接调用(此时 target_event.bot_info 尚未挂载)
        try:
            this_msg = API.putInteraction(bot_info)
            this_msg.metadata.interaction_id = str(interaction_id)
            this_msg.data.code = int(code)
            this_msg.do_api('PUT')
        except Exception:
            traceback.print_exc()

    def set_interaction_callback(target_event, interaction_id, code=0):
        # code: 0成功 1操作失败 2操作频繁 3重复操作 4没有权限 5仅管理员操作
        this_msg = API.putInteraction(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.interaction_id = str(interaction_id)
        this_msg.data.code = int(code)
        return event_action._run_raw_api(this_msg, 'set_interaction_callback', 'PUT')

    # ============ QQ 群 ============
    def get_qq_group_member_list(target_event, group_openid, limit=None, start_index=None):
        this_msg = API.getQQGroupMembers(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.group_openid = str(group_openid)
        this_msg.query = {'limit': limit, 'start_index': start_index}
        return event_action._run_raw_api(this_msg, 'get_qq_group_member_list', 'GET')

    def get_qq_group_bot_state(target_event, group_openid):
        this_msg = API.getQQGroupBotState(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.group_openid = str(group_openid)
        return event_action._run_raw_api(this_msg, 'get_qq_group_bot_state', 'GET')

    # ============ 用户信息(基于消息/事件积累的缓存) ============
    def get_stranger_info(target_event, user_id, no_cache=False):
        # 平台无"查用户资料"接口,数据来自消息/事件/mentions 积累的缓存;
        # 返回结构与 OneBot get_stranger_info 对齐,并附带各类 openid。
        res_data = OlivOS.contentAPI.api_result_data_template.get_stranger_info()
        record = _get_qq_user_info(target_event.bot_info.hash, user_id)
        if record is not None:
            res_data['active'] = True
            res_data['data']['name'] = record.get('name', None)
            res_data['data']['id'] = str(user_id)
            for extra_key in [
                'member_openid', 'user_openid', 'union_openid',
                'union_user_account', 'role', 'chat_type', 'chat_id', 'time'
            ]:
                res_data['data'][extra_key] = record.get(extra_key, None)
        return res_data

    def get_group_member_info(target_event, group_id, user_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_info()
        record = _get_qq_user_info(target_event.bot_info.hash, user_id)
        if record is not None:
            res_data['active'] = True
            res_data['data']['name'] = record.get('name', None)
            res_data['data']['card'] = record.get('name', None)
            res_data['data']['id'] = str(user_id)
            res_data['data']['user_id'] = str(user_id)
            res_data['data']['group_id'] = None if group_id is None else str(group_id)
            res_data['data']['role'] = record.get('role', None)
            res_data['data']['times']['last_sent_time'] = record.get('time', 0)
            for extra_key in ['member_openid', 'user_openid', 'union_openid']:
                res_data['data'][extra_key] = record.get(extra_key, None)
        return res_data

    def get_user_info(target_event, user_id):
        # SDK 级完整记录:昵称/角色/全部 openid/最后活跃时间等。
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        record = _get_qq_user_info(target_event.bot_info.hash, user_id)
        if record is not None:
            record.pop('time_monotonic', None)
            res_data['active'] = True
            res_data['data']['user_info'] = record
        return res_data

    # ============ 未映射平台事件查询 ============
    def get_unhandled_events(target_event, limit=50, flag_clear=False):
        # 取本 bot 未映射到 OlivOS 标准事件的平台事件(INTERACTION_CREATE、
        # MESSAGE_AUDIT_*、REACTION、FORUM、GUILD/CHANNEL 变更等),按时间正序。
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        bot_hash = str(target_event.bot_info.hash)
        with sdkUnhandledEventLock:
            event_deque = sdkUnhandledEventInfo.get(bot_hash, None)
            if event_deque is None:
                event_list = []
            else:
                event_list = list(event_deque)[-int(limit):]
                if flag_clear:
                    event_deque.clear()
        res_data['active'] = True
        res_data['data']['events'] = copy.deepcopy(event_list)
        return res_data

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
    # 远程资源交平台拉取；本地小文件 base64 直传，直传失败或超限时走文档的分片上传；
    # 成功结果按平台返回的 ttl 缓存，同一资源有效期内重发免重复上传。
    def setResourceUploadFast(
        target_event,
        url: str,
        chat_id,
        type_path: str,
        type_chat: str,
        file_name=None,
        flag_send_msg=False
    ):
        file_type_map = {
            'images': 1,
            'videos': 2,
            'audios': 3,
            'files': 4
        }
        file_type = file_type_map.get(type_path, 4)
        try:
            url_parsed = parse.urlparse(url)
            flag_remote = url_parsed.scheme in ['http', 'https']
            file_data = None
            if flag_remote:
                if type_path == 'files':
                    file_name = event_action._get_resource_file_name(
                        url,
                        type_path=type_path,
                        file_name=file_name
                    )
                resource_key = 'url:%s' % url
            else:
                file_data = event_action._get_local_resource_data(url, type_path)
                file_name = event_action._get_resource_file_name(
                    url,
                    type_path=type_path,
                    file_name=file_name
                )
                resource_key = 'md5:%s:%d' % (
                    hashlib.md5(file_data).hexdigest(),
                    len(file_data)
                )
            cache_key = (
                str(target_event.bot_info.hash),
                str(type_chat),
                str(chat_id),
                str(file_type),
                resource_key
            )
            if not flag_send_msg:
                file_info = _get_cached_resource_upload(cache_key)
                if file_info is not None:
                    return file_info

            ttl = None
            if flag_remote:
                # 远程资源直接交给 QQ 平台拉取，避免 OlivOS 额外下载和重复编码。
                file_info, ttl = event_action._upload_resource_direct(
                    target_event,
                    chat_id,
                    type_chat,
                    file_type,
                    url=url,
                    file_name=file_name,
                    flag_send_msg=flag_send_msg
                )
            else:
                if len(file_data) <= sdkResourceUploadDirectMaxSize:
                    file_info, ttl = event_action._upload_resource_direct(
                        target_event,
                        chat_id,
                        type_chat,
                        file_type,
                        file_data=file_data,
                        file_name=file_name,
                        flag_send_msg=flag_send_msg
                    )
                    if file_info is None:
                        # file_data 直传失败时回退到文档的分片上传流程。
                        file_info, ttl = event_action._upload_resource_chunked(
                            target_event,
                            chat_id,
                            type_chat,
                            file_type,
                            file_data,
                            file_name,
                            flag_send_msg=flag_send_msg
                        )
                else:
                    # 大文件按文档走分片上传，避免超长 base64 请求体。
                    file_info, ttl = event_action._upload_resource_chunked(
                        target_event,
                        chat_id,
                        type_chat,
                        file_type,
                        file_data,
                        file_name,
                        flag_send_msg=flag_send_msg
                    )
            if file_info is not None and not flag_send_msg:
                _cache_resource_upload(cache_key, file_info, ttl)
            return file_info
        except Exception:
            traceback.print_exc()
            return None

    # 富媒体直传：远程资源传 url，本地资源传 base64 file_data；
    # 普通消息传输不直接发消息，upload_*_file 调用则将 flag_send_msg 设为 True。
    def _upload_resource_direct(
        target_event,
        chat_id,
        type_chat,
        file_type,
        url=None,
        file_data=None,
        file_name=None,
        flag_send_msg=False
    ):
        msg_upload_api = API.setResourcePictureUpload(get_SDK_bot_info_from_Event(target_event))
        msg_upload_api.resource_type = type_chat
        msg_upload_api.metadata.openid = str(chat_id)
        msg_upload_api.data.file_type = file_type
        msg_upload_api.data.file_name = file_name
        msg_upload_api.data.srv_send_msg = flag_send_msg
        if url is not None:
            msg_upload_api.data.url = url
        elif file_data is not None:
            msg_upload_api.data.file_data = base64.b64encode(file_data).decode('ascii')
        msg_upload_api.do_api('POST')
        file_info, ttl = event_action._parse_resource_upload_result(msg_upload_api)
        event_action._log_qq_upload(
            target_event,
            'direct',
            api_obj=msg_upload_api,
            flag_success=file_info is not None
        )
        return file_info, ttl

    # 按文档的分片上传流程处理本地文件：预上传换取 upload_id 与分片预签名 URL，
    # 逐片 PUT 并确认，最后携带 upload_id 调用上传接口合并取 file_info。
    def _upload_resource_chunked(
        target_event,
        chat_id,
        type_chat,
        file_type,
        file_data,
        file_name,
        flag_send_msg=False
    ):
        sdk_bot_info = get_SDK_bot_info_from_Event(target_event)
        prepare_api = API.uploadPrepare(sdk_bot_info)
        prepare_api.resource_type = type_chat
        prepare_api.metadata.openid = str(chat_id)
        prepare_api.data.file_type = file_type
        prepare_api.data.file_size = str(len(file_data))
        prepare_api.data.file_name = file_name
        prepare_api.data.md5 = hashlib.md5(file_data).hexdigest()
        prepare_api.data.sha1 = hashlib.sha1(file_data).hexdigest()
        prepare_api.data.md5_10m = hashlib.md5(
            file_data[:sdkResourceUploadMd5_10mSize]
        ).hexdigest()
        prepare_api.do_api('POST')
        prepare_obj = init_api_json(prepare_api.res)
        flag_prepare_ok = (
            prepare_api.res_code is not None
            and 200 <= prepare_api.res_code < 300
            and type(prepare_obj) is dict
            and event_action._get_api_error_code(prepare_obj) in [None, 0]
        )
        upload_id = None
        if flag_prepare_ok:
            upload_id = prepare_obj.get('upload_id', None)
        event_action._log_qq_upload(
            target_event,
            'upload_prepare',
            api_obj=prepare_api,
            flag_success=(
                flag_prepare_ok
                and upload_id is not None
                and str(upload_id) != ''
            )
        )
        if upload_id is None or str(upload_id) == '':
            return None, None
        upload_id = str(upload_id)

        upload_parts = event_action._get_resource_upload_parts(prepare_obj, len(file_data))
        if upload_parts is None:
            event_action._log_qq_upload(
                target_event,
                'upload_prepare',
                detail='invalid parts in response'
            )
            return None, None

        upload_config = prepare_obj.get('upload_config', None)
        if type(upload_config) is not dict:
            upload_config = {}
        concurrency = event_action._get_upload_int(upload_config.get('concurrency', None), 1)
        concurrency = max(1, min(
            concurrency,
            sdkResourceUploadPartMaxConcurrency,
            len(upload_parts)
        ))
        retry_timeout = event_action._get_upload_float(upload_config.get('retry_timeout', None), 300.0)
        retry_delay = event_action._get_upload_float(upload_config.get('retry_delay', None), 1.0)

        def upload_part_this(upload_part):
            return event_action._upload_resource_part(
                sdk_bot_info,
                chat_id,
                type_chat,
                upload_id,
                upload_part,
                file_data,
                retry_timeout,
                retry_delay,
                target_event=target_event
            )

        if concurrency > 1:
            # 并发数由预上传响应的 upload_config 下发，官方默认为 1。
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                part_results = list(executor.map(upload_part_this, upload_parts))
        else:
            part_results = []
            for upload_part in upload_parts:
                part_result = upload_part_this(upload_part)
                part_results.append(part_result)
                if not part_result:
                    break
        if len(part_results) != len(upload_parts) or not all(part_results):
            event_action._log_qq_upload(
                target_event,
                'upload_part',
                detail='chunk upload failed (%d/%d parts done)' % (
                    sum(1 for part_result in part_results if part_result),
                    len(upload_parts)
                )
            )
            return None, None
        event_action._log_qq_upload(
            target_event,
            'upload_part',
            detail='chunk upload completed (%d/%d parts)' % (
                len(part_results),
                len(upload_parts)
            ),
            flag_success=True
        )

        merge_api = API.setResourcePictureUpload(sdk_bot_info)
        merge_api.resource_type = type_chat
        merge_api.metadata.openid = str(chat_id)
        merge_api.data.file_type = file_type
        merge_api.data.file_name = file_name
        merge_api.data.upload_id = upload_id
        merge_api.data.srv_send_msg = flag_send_msg
        merge_api.do_api('POST')
        file_info, ttl = event_action._parse_resource_upload_result(merge_api)
        event_action._log_qq_upload(
            target_event,
            'chunk_merge',
            api_obj=merge_api,
            flag_success=file_info is not None
        )
        return file_info, ttl

    # 上传单个分片：PUT 预签名 URL 成功后调用 upload_part_finish 确认，
    # 失败时按平台下发的 retry_delay/retry_timeout 重试。
    def _upload_resource_part(
        sdk_bot_info,
        chat_id,
        type_chat,
        upload_id,
        upload_part,
        file_data,
        retry_timeout,
        retry_delay,
        target_event=None
    ):
        part_data = file_data[upload_part['offset']:upload_part['offset'] + upload_part['size']]
        part_md5 = hashlib.md5(part_data).hexdigest()
        retry_deadline = time.monotonic() + retry_timeout
        attempt_count = 0
        while True:
            attempt_count += 1
            flag_put_ok = False
            try:
                # 预签名 URL 已含鉴权，不能附加额外头部，避免破坏签名校验。
                put_res = req.request(
                    'PUT',
                    upload_part['presigned_url'],
                    data=part_data,
                    timeout=sdkResourceUploadPartTimeout
                )
                flag_put_ok = 200 <= put_res.status_code < 300
                if target_event is not None:
                    put_text = getattr(put_res, 'text', None)
                    if put_text is None:
                        put_text = str(put_res)
                    event_action._log_qq_upload(
                        target_event,
                        'upload_part_put',
                        detail='part=%d attempt=%d HTTP %s response: %s' % (
                            upload_part['index'],
                            attempt_count,
                            str(put_res.status_code),
                            str(put_text)
                        ),
                        flag_success=flag_put_ok
                    )
            except Exception as exc:
                traceback.print_exc()
                if target_event is not None:
                    event_action._log_qq_upload(
                        target_event,
                        'upload_part_put',
                        detail='part=%d attempt=%d request exception: %s' % (
                            upload_part['index'],
                            attempt_count,
                            str(exc)
                        )
                    )
            if flag_put_ok:
                finish_api = API.uploadPartFinish(sdk_bot_info)
                finish_api.resource_type = type_chat
                finish_api.metadata.openid = str(chat_id)
                finish_api.data.upload_id = upload_id
                finish_api.data.part_index = upload_part['index']
                finish_api.data.block_size = str(upload_part['size'])
                finish_api.data.md5 = part_md5
                finish_api.do_api('POST')
                finish_obj = init_api_json(finish_api.res)
                flag_finish_ok = (
                    finish_api.res_code is not None
                    and 200 <= finish_api.res_code < 300
                    and (
                        type(finish_obj) is not dict
                        or event_action._get_api_error_code(finish_obj) in [None, 0]
                    )
                )
                event_action._log_qq_upload(
                    target_event,
                    'upload_part_finish',
                    api_obj=finish_api,
                    detail='part=%d attempt=%d' % (
                        upload_part['index'],
                        attempt_count
                    ),
                    flag_success=flag_finish_ok
                )
                if flag_finish_ok:
                    return True
            if (
                attempt_count >= sdkResourceUploadPartRetryMax
                or time.monotonic() + retry_delay >= retry_deadline
            ):
                return False
            time.sleep(retry_delay)

    # 解析预上传返回的分片列表并换算每片的数据范围；结构非法时返回 None。
    def _get_resource_upload_parts(prepare_obj, file_size):
        parts_raw = prepare_obj.get('parts', None)
        if type(parts_raw) is not list or len(parts_raw) == 0:
            return None
        block_size_default = event_action._get_upload_int(
            prepare_obj.get('block_size', None),
            sdkResourceUploadBlockSize
        )
        if block_size_default <= 0:
            block_size_default = sdkResourceUploadBlockSize
        parts_sorted = []
        for part_this in parts_raw:
            if type(part_this) is not dict:
                return None
            part_index = event_action._get_upload_int(part_this.get('index', None), -1)
            presigned_url = part_this.get('presigned_url', None)
            if (
                part_index < 0
                or type(presigned_url) is not str
                or presigned_url == ''
            ):
                return None
            part_block_size = event_action._get_upload_int(
                part_this.get('block_size', None),
                block_size_default
            )
            if part_block_size <= 0:
                part_block_size = block_size_default
            parts_sorted.append((part_index, presigned_url, part_block_size))
        parts_sorted.sort(key=lambda part_this: part_this[0])
        upload_parts = []
        data_offset = 0
        for part_index, presigned_url, part_block_size in parts_sorted:
            data_end = min(data_offset + part_block_size, file_size)
            if data_end <= data_offset:
                return None
            upload_parts.append({
                'index': part_index,
                'presigned_url': presigned_url,
                'offset': data_offset,
                'size': data_end - data_offset
            })
            data_offset = data_end
        if data_offset != file_size:
            # 分片总长与文件不一致说明预上传结果异常，避免上传残缺数据。
            return None
        return upload_parts

    # 解析富媒体上传/合并响应；成功返回 (file_info, ttl)，失败返回 (None, None)。
    def _parse_resource_upload_result(api_obj):
        raw_obj = init_api_json(api_obj.res)
        if type(raw_obj) is not dict:
            return None, None
        if event_action._get_api_error_code(raw_obj) not in [None, 0]:
            return None, None
        if api_obj.res_code is not None and not 200 <= api_obj.res_code < 300:
            return None, None
        # 当前接口成功时直接返回媒体对象；兼容部分环境的 data 包装格式。
        raw_data = raw_obj.get('data', raw_obj)
        if type(raw_data) is not dict:
            return None, None
        file_info = raw_data.get('file_info', None)
        if type(file_info) is not str or file_info == '':
            return None, None
        return file_info, raw_data.get('ttl', None)

    # 分片上传与文件消息需要文件名；优先用消息段提供的 name，再取 URL 路径，最后生成兜底名。
    def _get_resource_file_name(url, type_path='files', file_name=None):
        if type(file_name) is str and file_name.strip() != '':
            return file_name.strip()
        try:
            url_path = parse.urlparse(url).path
            base_name = os.path.basename(parse.unquote(url_path)).strip()
        except Exception:
            base_name = ''
        if base_name != '' and '.' in base_name:
            return base_name
        ext_map = {
            'images': 'png',
            'videos': 'mp4',
            'audios': 'silk',
            'files': 'dat'
        }
        return '%s.%s' % (str(uuid.uuid4()), ext_map.get(type_path, 'dat'))

    def _get_upload_int(value, default):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _get_upload_float(value, default):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return default
        if value <= 0:
            return default
        return value

    def _log_qq_upload(
        target_event,
        stage,
        api_obj=None,
        detail=None,
        flag_success=None
    ):
        if target_event is None or target_event.log_func is None:
            return
        if flag_success is True:
            return
        detail_parts = []
        if detail is not None:
            detail_parts.append(str(detail))
        if api_obj is not None:
            res_text = str(api_obj.res) if api_obj.res is not None else 'no response'
            res_code_text = 'n/a' if api_obj.res_code is None else str(api_obj.res_code)
            detail_parts.append('HTTP %s response: %s' % (res_code_text, res_text))
            if flag_success is None:
                flag_success = (
                    api_obj.res_code is not None
                    and 200 <= api_obj.res_code < 300
                )
        if flag_success is None:
            flag_success = False
        if flag_success:
            return
        if len(detail_parts) == 0:
            detail_parts.append('no response detail')
        try:
            target_event.log_func(
                3,
                'OlivOS qqGuildv2SDK QQ media upload [%s] failed: %s' % (
                    str(stage),
                    ' | '.join(detail_parts)
                ),
                [
                    (target_event.getBotIDStr(), 'default'),
                    (modelName, 'default'),
                    ('setResourceUploadFast', 'callback')
                ]
            )
        except Exception:
            traceback.print_exc()


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
    qqAtUserReg = re.compile(
        r'<qqbot-at-user\s+id=(["\'])([^"\']+)\1\s*/>'
    )
    qqAtEveryoneReg = re.compile(r'<qqbot-at-everyone\s*/>')

    def at_para(message_para, allow_at_all=True, flag_qq=True):
        if not isinstance(message_para, OlivOS.messageAPI.PARA.at):
            return ''
        user_id = str(message_para.data.get('id', ''))
        if user_id == 'all':
            if allow_at_all:
                return '<qqbot-at-everyone />' if flag_qq else '@everyone'
            return ''
        if user_id == '':
            return ''
        return markdown_tag.at_user(user_id, flag_qq=flag_qq)

    def at_user(user_id, flag_qq=True):
        if flag_qq:
            return '<qqbot-at-user id="%s" />' % str(user_id)
        return '<@!%s>' % str(user_id)

    def normalize_guild_text(text, allow_at_all=True):
        text = markdown_tag.qqAtUserReg.sub(
            lambda match: markdown_tag.at_user(match.group(2), flag_qq=False),
            str(text)
        )
        return markdown_tag.qqAtEveryoneReg.sub(
            '@everyone' if allow_at_all else '',
            text
        )

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


def _register_qq_forward_message(bot_hash, forward_id, messages):
    global sdkForwardMessageInfoLastCleanup
    if forward_id is None:
        return
    bot_hash = str(bot_hash)
    forward_id = str(forward_id)
    now = time.monotonic()
    with sdkForwardMessageInfoLock:
        if now - sdkForwardMessageInfoLastCleanup >= 60:
            expired_keys = [
                key_this
                for key_this, data_this in sdkForwardMessageInfo.items()
                if data_this['expires_at'] <= now
            ]
            for key_this in expired_keys:
                sdkForwardMessageInfo.pop(key_this, None)
            sdkForwardMessageInfoLastCleanup = now
        cache_key = (bot_hash, forward_id)
        if (
            cache_key not in sdkForwardMessageInfo
            and len(sdkForwardMessageInfo) >= sdkForwardMessageInfoMaxSize
        ):
            oldest_key = min(
                sdkForwardMessageInfo,
                key=lambda key_this: sdkForwardMessageInfo[key_this]['expires_at']
            )
            sdkForwardMessageInfo.pop(oldest_key, None)
        sdkForwardMessageInfo[cache_key] = {
            'messages': copy.deepcopy(messages),
            'expires_at': now + sdkForwardMessageInfoTTL
        }


def _get_qq_forward_message(bot_hash, forward_id):
    if forward_id is None:
        return None
    cache_key = (str(bot_hash), str(forward_id))
    now = time.monotonic()
    with sdkForwardMessageInfoLock:
        cache_data = sdkForwardMessageInfo.get(cache_key, None)
        if cache_data is None:
            return None
        if cache_data['expires_at'] <= now:
            sdkForwardMessageInfo.pop(cache_key, None)
            return None
        return copy.deepcopy(cache_data['messages'])


def _get_cached_resource_upload(cache_key):
    """命中未过期的 file_info 缓存时直接复用，避免重复上传同一富媒体资源。"""
    now = time.monotonic()
    with sdkResourceUploadInfoLock:
        cache_data = sdkResourceUploadInfo.get(cache_key, None)
        if cache_data is None:
            return None
        if cache_data['expires_at'] <= now:
            sdkResourceUploadInfo.pop(cache_key, None)
            return None
        return cache_data['file_info']


def _cache_resource_upload(cache_key, file_info, ttl):
    """按平台返回的 ttl 缓存 file_info；0 表示长期有效，其余留出安全余量。"""
    try:
        ttl_value = float(ttl)
    except (TypeError, ValueError):
        return
    if ttl_value < 0:
        return
    now = time.monotonic()
    if ttl_value == 0:
        expires_at = now + sdkResourceUploadTTLLongTerm
    else:
        ttl_value -= sdkResourceUploadTTLMargin
        if ttl_value <= 0:
            return
        expires_at = now + ttl_value
    with sdkResourceUploadInfoLock:
        if (
            cache_key not in sdkResourceUploadInfo
            and len(sdkResourceUploadInfo) >= sdkResourceUploadInfoMaxSize
        ):
            expired_keys = [
                key_this
                for key_this, data_this in sdkResourceUploadInfo.items()
                if data_this['expires_at'] <= now
            ]
            for key_this in expired_keys:
                sdkResourceUploadInfo.pop(key_this, None)
            if len(sdkResourceUploadInfo) >= sdkResourceUploadInfoMaxSize:
                oldest_key = min(
                    sdkResourceUploadInfo,
                    key=lambda key_this: sdkResourceUploadInfo[key_this]['expires_at']
                )
                sdkResourceUploadInfo.pop(oldest_key, None)
        sdkResourceUploadInfo[cache_key] = {
            'file_info': file_info,
            'expires_at': expires_at
        }


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


# QQ official API request models
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

    # 获取指定消息(仅频道):GET /channels/{channel_id}/messages/{message_id}
    class getMessage(api_templet):
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

    # ============ 频道模块:频道/子频道 ============
    # GET /guilds/{guild_id} 获取频道详情
    class getGuild(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # GET /users/@me/guilds 获取机器人加入的频道列表(query: before/after/limit)
    class getMeGuilds(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['users_me'] + '/guilds'

    # GET /guilds/{guild_id}/channels 获取子频道列表
    class getGuildChannels(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/channels'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # GET /channels/{channel_id} 获取子频道详情
    class getChannel(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # POST /guilds/{guild_id}/channels 创建子频道(私域)
    class createChannel(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/channels'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.name = None            # str
                self.type = None            # int 子频道类型
                self.sub_type = None        # int 子频道子类型
                self.position = None        # int
                self.parent_id = None       # str 分组 id
                self.private_type = None    # int 私密类型
                self.private_user_ids = None  # list
                self.speak_permission = None  # int
                self.application_id = None  # str 应用子频道应用类型

    # PATCH /channels/{channel_id} 修改子频道(私域)
    class patchChannel(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.name = None
                self.position = None
                self.parent_id = None
                self.private_type = None
                self.speak_permission = None

    # DELETE /channels/{channel_id} 删除子频道(私域)
    class deleteChannel(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # GET /channels/{channel_id}/online_nums 获取音视频/直播子频道在线成员数
    class getChannelOnlineNums(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/online_nums'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # ============ 频道模块:成员 ============
    # GET /guilds/{guild_id}/members 获取频道成员列表(私域, query: after/limit)
    class getGuildMembers(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # GET /guilds/{guild_id}/roles/{role_id}/members 获取身份组成员列表(query: start_index/limit)
    class getGuildRoleMembers(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles/{role_id}/members'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.role_id = '-1'

    # GET /guilds/{guild_id}/members/{user_id} 获取成员详情
    class getGuildMember(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'

    # DELETE /guilds/{guild_id}/members/{user_id} 删除频道成员(踢人,私域)
    class deleteGuildMember(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'

        class data_T(object):
            def __init__(self):
                self.add_blacklist = None             # bool 是否同时加入黑名单
                self.delete_history_msg_days = None   # int 撤回历史消息天数(3/7/15/30,0不撤回,-1全部)

    # ============ 频道模块:身份组 ============
    # GET /guilds/{guild_id}/roles 获取频道身份组列表
    class getGuildRoles(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # POST /guilds/{guild_id}/roles 创建频道身份组
    class createGuildRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.name = None   # str
                self.color = None  # int ARGB 十进制
                self.hoist = None  # int 是否在成员列表中单独展示(0/1)

    # PATCH /guilds/{guild_id}/roles/{role_id} 修改频道身份组
    class patchGuildRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles/{role_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.role_id = '-1'

        class data_T(object):
            def __init__(self):
                self.name = None
                self.color = None
                self.hoist = None

    # DELETE /guilds/{guild_id}/roles/{role_id} 删除频道身份组
    class deleteGuildRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles/{role_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.role_id = '-1'

    # PUT /guilds/{guild_id}/members/{user_id}/roles/{role_id} 增加频道身份组成员
    # 操作 5 号(子频道管理员)身份组时需在 body 传 channel.id。
    class putGuildMemberRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}/roles/{role_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'
                self.role_id = '-1'

        class data_T(object):
            def __init__(self):
                self.channel = None  # dict {'id': channel_id}

    # DELETE /guilds/{guild_id}/members/{user_id}/roles/{role_id} 删除频道身份组成员
    class deleteGuildMemberRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}/roles/{role_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'
                self.role_id = '-1'

        class data_T(object):
            def __init__(self):
                self.channel = None  # dict {'id': channel_id}

    # ============ 频道模块:子频道权限 ============
    # GET /channels/{channel_id}/members/{user_id}/permissions 获取子频道用户权限
    class getChannelMemberPermissions(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/members/{user_id}/permissions'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.user_id = '-1'

    # PUT /channels/{channel_id}/members/{user_id}/permissions 修改子频道用户权限
    class putChannelMemberPermissions(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/members/{user_id}/permissions'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.user_id = '-1'

        class data_T(object):
            def __init__(self):
                self.add = None     # str 权限位或值,如 '1'/'2'/'4'/'8' 的组合
                self.remove = None  # str

    # GET /channels/{channel_id}/roles/{role_id}/permissions 获取子频道身份组权限
    class getChannelRolePermissions(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/roles/{role_id}/permissions'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.role_id = '-1'

    # PUT /channels/{channel_id}/roles/{role_id}/permissions 修改子频道身份组权限
    class putChannelRolePermissions(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/roles/{role_id}/permissions'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.role_id = '-1'

        class data_T(object):
            def __init__(self):
                self.add = None
                self.remove = None

    # ============ 频道模块:消息列表/私信会话 ============
    # GET /channels/{channel_id}/messages 拉取消息列表(v1 存量接口, query: around/before/after/limit)
    class getChannelMessages(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/messages'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # POST /users/@me/dms 创建私信会话
    class createDirectMessageSession(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['users_me'] + '/dms'

        class data_T(object):
            def __init__(self):
                self.recipient_id = None      # str 接收者 id
                self.source_guild_id = None   # str 源频道 id

    # ============ 频道模块:禁言 ============
    # PATCH /guilds/{guild_id}/mute 全员禁言(传 user_ids 时为批量成员禁言)
    class patchGuildMute(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/mute'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.mute_end_timestamp = None  # str 秒级时间戳
                self.mute_seconds = None        # str 禁言时长(秒),'0' 为解除
                self.user_ids = None            # list 批量成员禁言

    # PATCH /guilds/{guild_id}/members/{user_id}/mute 指定成员禁言
    class patchGuildMemberMute(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}/mute'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'

        class data_T(object):
            def __init__(self):
                self.mute_end_timestamp = None
                self.mute_seconds = None

    # ============ 频道模块:公告/精华 ============
    # POST /guilds/{guild_id}/announces 创建频道公告
    class createAnnounce(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/announces'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.message_id = None          # str
                self.channel_id = None          # str
                self.announces_type = None      # int 0成员公告 1欢迎公告
                self.recommend_channels = None  # list RecommendChannel

    # DELETE /guilds/{guild_id}/announces/{message_id} 删除频道公告(message_id 可为 'all')
    class deleteAnnounce(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/announces/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.message_id = '-1'

    # PUT /channels/{channel_id}/pins/{message_id} 添加精华消息
    class putPinsMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/pins/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'

    # DELETE /channels/{channel_id}/pins/{message_id} 删除精华消息(message_id 可为 'all')
    class deletePinsMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/pins/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'

    # GET /channels/{channel_id}/pins 获取精华消息列表
    class getPinsMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/pins'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # ============ 频道模块:日程 ============
    # GET /channels/{channel_id}/schedules 获取日程列表(query: since)
    class getSchedules(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # GET /channels/{channel_id}/schedules/{schedule_id} 获取日程详情
    class getSchedule(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules/{schedule_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.schedule_id = '-1'

    # POST /channels/{channel_id}/schedules 创建日程
    class createSchedule(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.schedule = None  # dict Schedule 对象(不含 id)

    # PATCH /channels/{channel_id}/schedules/{schedule_id} 修改日程
    class patchSchedule(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules/{schedule_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.schedule_id = '-1'

        class data_T(object):
            def __init__(self):
                self.schedule = None  # dict Schedule 对象(不含 id)

    # DELETE /channels/{channel_id}/schedules/{schedule_id} 删除日程
    class deleteSchedule(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules/{schedule_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.schedule_id = '-1'

    # ============ 频道模块:表情表态 ============
    # PUT /channels/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id} 发表表情表态
    class putMessageReaction(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['channels']
                + '/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id}'
            )

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'
                self.emoji_type = '1'  # 1系统表情 2emoji
                self.emoji_id = '-1'

    # DELETE /channels/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id} 删除自己的表情表态
    class deleteMessageReaction(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['channels']
                + '/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id}'
            )

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'
                self.emoji_type = '1'
                self.emoji_id = '-1'

    # GET .../reactions/{emoji_type}/{emoji_id} 拉取表态用户列表(query: cookie/limit)
    class getMessageReactionUsers(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['channels']
                + '/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id}'
            )

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'
                self.emoji_type = '1'
                self.emoji_id = '-1'

    # ============ 频道模块:音频/麦克风 ============
    # POST /channels/{channel_id}/audio 音频控制
    class postAudioControl(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/audio'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.audio_url = None  # str
                self.text = None       # str 状态文本
                self.status = None     # int 0开始 1暂停 2继续 3停止

    # PUT /channels/{channel_id}/mic 机器人上麦
    class putMic(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/mic'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # DELETE /channels/{channel_id}/mic 机器人下麦
    class deleteMic(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/mic'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # ============ 频道模块:帖子(论坛) ============
    # GET /channels/{channel_id}/threads 获取帖子列表(私域)
    class getThreads(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/threads'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # GET /channels/{channel_id}/threads/{thread_id} 获取帖子详情(私域)
    class getThread(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/threads/{thread_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.thread_id = '-1'

    # PUT /channels/{channel_id}/threads 发表帖子(私域)
    class putThread(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/threads'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.title = None    # str
                self.content = None  # str
                self.format = None   # int 1文本 2HTML 3Markdown 4JSON

    # DELETE /channels/{channel_id}/threads/{thread_id} 删除帖子(私域)
    class deleteThread(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/threads/{thread_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.thread_id = '-1'

    # ============ 频道模块:API 权限 ============
    # GET /guilds/{guild_id}/api_permission 获取频道可用权限列表
    class getGuildApiPermission(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/api_permission'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # POST /guilds/{guild_id}/api_permission/demand 创建频道 API 接口权限授权链接
    class demandGuildApiPermission(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/api_permission/demand'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.channel_id = None    # str
                self.api_identify = None  # dict {'path':..., 'method':...}
                self.desc = None          # str

    # ============ 互动回调应答 ============
    # PUT /interactions/{interaction_id} 对 INTERACTION_CREATE 的应答(code: 0成功 1操作失败 2操作频繁 3重复操作 4没有权限 5仅管理员操作)
    class putInteraction(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['interactions'] + '/{interaction_id}'

        class metadata_T(object):
            def __init__(self):
                self.interaction_id = '-1'

        class data_T(object):
            def __init__(self):
                self.code = None  # int

    # ============ QQ 群 ============
    # GET /v2/groups/{group_openid}/members 获取群成员列表(query: limit/start_index,需相应权限)
    class getQQGroupMembers(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/members'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

    # ============ 消息发送 ============
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

    # ============ QQ 富媒体上传 ============
    # 名称保留以兼容已有内部引用，实际支持图片、视频、语音和文件。
    # 直传时携带 url 或 file_data；分片上传完成后携带 upload_id 请求合并，两者均返回 file_info。
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
                self.srv_send_msg = None  # bool，False 时仅返回 file_info，不由平台直接发消息
                self.file_name = None  # 文件名
                self.upload_id = None  # 分片上传任务 ID，合并分片时携带
                self.file_data = None  # 本地资源的 base64 数据

        class metadata_T(object):
            def __init__(self):
                self.openid = '-1'

        def do_api(self, req_type='POST'):
            # 官方富媒体接口使用 JSON：远程资源传 url，本地资源传 base64 file_data。
            self.route = sdkAPIRoute[self.resource_type] + '/{openid}/files'
            return api_templet.do_api(self, req_type)

    # QQ 单聊/群聊富媒体预上传：按文件校验值换取 upload_id 与各分片的预签名 URL。
    class uploadPrepare(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{openid}/upload_prepare'
            self.resource_type = 'qq_groups'

        class data_T(object):
            def __init__(self):
                self.file_type = None  # 1 图片、2 视频、3 语音、4 文件
                self.file_size = None  # str，文件总字节数
                self.file_name = None  # 文件名
                self.md5 = None        # 整个文件的 MD5
                self.sha1 = None       # 整个文件的 SHA1
                self.md5_10m = None    # 文件前 10002432 字节的 MD5

        class metadata_T(object):
            def __init__(self):
                self.openid = '-1'

        def do_api(self, req_type='POST'):
            self.route = sdkAPIRoute[self.resource_type] + '/{openid}/upload_prepare'
            return api_templet.do_api(self, req_type)

    # QQ 单聊/群聊分片上传完成确认：每个分片 PUT 成功后通知平台。
    class uploadPartFinish(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{openid}/upload_part_finish'
            self.resource_type = 'qq_groups'

        class data_T(object):
            def __init__(self):
                self.upload_id = None   # 分片上传任务 ID
                self.part_index = None  # int，分片序号，从 0 开始
                self.block_size = None  # str，该分片的字节数
                self.md5 = None         # 该分片数据的 MD5

        class metadata_T(object):
            def __init__(self):
                self.openid = '-1'

        def do_api(self, req_type='POST'):
            self.route = sdkAPIRoute[self.resource_type] + '/{openid}/upload_part_finish'
            return api_templet.do_api(self, req_type)

    # ============ 消息删除 ============
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
