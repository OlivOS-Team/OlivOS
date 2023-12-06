# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqGuildv2SDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

from enum import IntEnum
import sys
import json
import requests as req
import time
from datetime import datetime, timezone, timedelta
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
    'user_id': '-1'
}

sdkSubSelfInfo = {}
sdkTokenInfo = {}
sdkMsgidinfo = {}
sdkSelfInfo = {}


class bot_info_T(object):
    def __init__(self, id=-1, access_token=None, model='private'):
        self.id = id
        self.access_token = access_token
        self.model = model
        self.debug_mode = False
        self.debug_logger = None


def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(
        plugin_bot_info.id,
        plugin_bot_info.post_info.access_token
    )
    res.debug_mode = plugin_bot_info.debug_mode
    if plugin_bot_info.platform['model'] == 'public':
        res.model = 'public'
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
            if type(data) == dict:
                if 'op' in data:
                    if type(data['op']) == int:
                        self.data.op = data['op']
                    else:
                        self.active = False
                else:
                    self.active = False
                if 'd' in data:
                    self.data.d = data['d']
                if 's' in data:
                    if type(data['s']) == int:
                        self.data.s = data['s']
                    else:
                        self.active = False
                if 't' in data:
                    if type(data['t']) == str:
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
        def __init__(self, bot_info, intents=(int(intents_T.GUILDS) | int(intents_T.DIRECT_MESSAGE))):
            tmp_intents = intents
            if bot_info.model == 'private':
                tmp_intents |= int(intents_T.GUILD_MESSAGES)
                #tmp_intents |= int(intents_T.QQ_MESSAGES)
            elif bot_info.model == 'public':
                tmp_intents |= int(intents_T.PUBLIC_GUILD_MESSAGES)
                tmp_intents |= int(intents_T.PUBLIC_QQ_MESSAGES)
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
            except:
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

    def do_api_plant(self, req_type='POST'):
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
        except:
            return None

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
            #print(payload)
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

            self.res = msg_res.text
            #print(self.res)
            return msg_res.text
        except Exception as e:
            traceback.print_exc()
            return None

def getTokenNow(bot_info:bot_info_T):
    global sdkTokenInfo
    access_token = None
    plugin_event_bot_hash = OlivOS.API.getBotHash(
        bot_id=bot_info.id,
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='default'
    )
    tmpInfo = sdkTokenInfo.get(plugin_event_bot_hash, [None, -1])
    tmpTime = int(datetime.now(timezone.utc).timestamp())
    if tmpInfo[0] is not None \
    and tmpInfo[1] > tmpTime :
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
            except Exception as e:
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
                self.embed = None  # str
                self.ark = None  # str
                self.image = None  # str
                self.msg_id = None  # str
                #self.msg_type = 0
                #self.timestamp = int(datetime.now(timezone.utc).timestamp())

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
                self.content = None  # str
                self.embed = None  # str
                self.ark = None  # str
                self.image = None  # str
                self.msg_id = None  # str
                #self.msg_type = 0
                #self.timestamp = int(datetime.now(timezone.utc).timestamp())

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
                self.content = None  # str
                self.media = None  # str
                self.msg_type = 0
                self.embed = None  # str
                self.ark = None  # str
                self.image = None  # str
                self.msg_id = None  # str
                self.timestamp = int(datetime.now(timezone.utc).timestamp())
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
                self.content = None  # str
                self.msg_type = 0
                self.embed = None  # str
                self.ark = None  # str
                self.image = None  # str
                self.msg_id = None  # str
                self.timestamp = int(datetime.now(timezone.utc).timestamp())
                self.msg_seq = None

    #资源文件上传
    class setResourcePictureUpload(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{openid}/files'

        class data_T(object):
            def __init__(self):
                self.file = None
                self.type = 'qq_groups'

        class metadata_T(object):
            def __init__(self):
                self.openid = '-1'

        def do_api(self, req_type='POST', file_type: str = ['.png', 'image/png']):
            try:
                tmp_payload_dict = {'file': (str(uuid.uuid4()) + file_type[0], self.data.file, file_type[1])}
                payload = MultipartEncoder(
                    fields=tmp_payload_dict
                )

                tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
                if self.metadata is not None:
                    tmp_sdkAPIRouteTemp.update(self.metadata.__dict__)
                self.route = sdkAPIRoute[self.data.type] + '/{openid}/files'
                send_url_temp = self.host + ':' + str(self.port) + self.route
                send_url = send_url_temp.format(**tmp_sdkAPIRouteTemp)
                headers = {
                    'Content-Type': payload.content_type,
                    'Content-Length': str(len(self.data.file)),
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'Authorization': 'QQBot %s' % (getTokenNow(self.bot_info)),
                    'X-Union-Appid': str(self.bot_info.id)
                }

                msg_res = None
                if req_type == 'POST':
                    msg_res = req.request("POST", send_url, headers=headers, data=payload)

                self.res = msg_res.text
                return msg_res.text
            except Exception as e:
                traceback.print_exc()
                return None


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
    global sdkSubSelfInfo, sdkSelfInfo
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
        except Exception as e:
            traceback.print_exc()
        if plugin_event_bot_hash in sdkSelfInfo \
        and type(sdkSelfInfo[plugin_event_bot_hash]) is dict \
        and 'id' in sdkSelfInfo[plugin_event_bot_hash] \
        and 'username' in sdkSelfInfo[plugin_event_bot_hash]:
            sdkSubSelfInfo[plugin_event_bot_hash] = str(sdkSelfInfo[plugin_event_bot_hash]['id'])
    if target_event.sdk_event.payload.data.t == 'READY':
        target_event.active = False
        if type(target_event.sdk_event.payload.data.d) is dict \
        and 'user' in target_event.sdk_event.payload.data.d \
        and type(target_event.sdk_event.payload.data.d['user']) is dict:
            sdkSelfInfo[plugin_event_bot_hash] = target_event.sdk_event.payload.data.d['user']
    elif target_event.sdk_event.payload.data.t in [
        'GROUP_AT_MESSAGE_CREATE',
        'GROUP_MESSAGE_CREATE'
    ]:
        message_obj = None
        message_para_list = []
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
        if 'attachments' in target_event.sdk_event.payload.data.d:
            if type(target_event.sdk_event.payload.data.d['attachments']) == list:
                for attachments_this in target_event.sdk_event.payload.data.d['attachments']:
                    if 'content_type' in attachments_this:
                        if attachments_this['content_type'].startswith('image'):
                            message_obj.data_raw.append(
                                OlivOS.messageAPI.PARA.image(
                                    'https://%s' % attachments_this['url']
                                )
                            )
        try:
            message_obj.init_data()
        except:
            message_obj.active = False
            message_obj.data = []
        if message_obj.active:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message'
            target_event.data = target_event.group_message(
                str(target_event.sdk_event.payload.data.d['group_id']),
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
            target_event.data.sender['nickname'] = '用户'
            target_event.data.sender['id'] = target_event.data.sender['user_id']
            target_event.data.sender['name'] = target_event.data.sender['nickname']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            target_event.data.sender['role'] = 'member'
            target_event.data.host_id = None
            target_event.data.extend['group_id'] = str(target_event.sdk_event.payload.data.d['group_id'])
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
            if plugin_event_bot_hash in sdkSubSelfInfo:
                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
    elif target_event.sdk_event.payload.data.t == 'C2C_MESSAGE_CREATE':
        message_obj = None
        message_para_list = []
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
        if 'attachments' in target_event.sdk_event.payload.data.d:
            if type(target_event.sdk_event.payload.data.d['attachments']) == list:
                for attachments_this in target_event.sdk_event.payload.data.d['attachments']:
                    if 'content_type' in attachments_this:
                        if attachments_this['content_type'].startswith('image'):
                            message_obj.data_raw.append(
                                OlivOS.messageAPI.PARA.image(
                                    'https://%s' % attachments_this['url']
                                )
                            )
        try:
            message_obj.init_data()
        except:
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
        message_para_list = []
        if 'content' in target_event.sdk_event.payload.data.d:
            if(target_event.sdk_event.payload.data.t == 'AT_MESSAGE_CREATE'):
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
        if 'attachments' in target_event.sdk_event.payload.data.d:
            if type(target_event.sdk_event.payload.data.d['attachments']) == list:
                for attachments_this in target_event.sdk_event.payload.data.d['attachments']:
                    if 'content_type' in attachments_this:
                        if attachments_this['content_type'].startswith('image'):
                            message_obj.data_raw.append(
                                OlivOS.messageAPI.PARA.image(
                                    'https://%s' % attachments_this['url']
                                )
                            )
        try:
            message_obj.init_data()
        except:
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
        message_para_list = []
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
        if 'attachments' in target_event.sdk_event.payload.data.d:
            if type(target_event.sdk_event.payload.data.d['attachments']) == list:
                for attachments_this in target_event.sdk_event.payload.data.d['attachments']:
                    if 'content_type' in attachments_this:
                        if attachments_this['content_type'].startswith('image'):
                            message_obj.data_raw.append(
                                OlivOS.messageAPI.PARA.image(
                                    'https://%s' % attachments_this['url']
                                )
                            )
        try:
            message_obj.init_data()
        except:
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
    def send_qq_msg(target_event, chat_id, message, reply_msg_id=None, flag_direct=False):
        this_msg = None
        msg_id = None
        if flag_direct:
            this_msg = API.sendQQDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.openid = str(chat_id)
            if(type(target_event.sdk_event) is event):
                msg_id = target_event.sdk_event.payload.data.d.get('id', None)
        else:
            this_msg = API.sendQQMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.group_openid = str(chat_id)
            if(type(target_event.sdk_event) is event):
                msg_id = target_event.sdk_event.payload.data.d.get('id', None)
        if this_msg is None:
            return
        this_msg.data.msg_id = msg_id
        #this_msg.data.msg_id = reply_msg_id
        flag_now_type = 'string'
        flag_now_type_last = flag_now_type
        res = ''
        count_data = 0
        size_data = len(message.data)
        for message_this in message.data:
            count_data += 1
            flag_now_type_last = flag_now_type
            if type(message_this) == OlivOS.messageAPI.PARA.image:
                #this_msg.data.media = event_action.setResourceUploadFast(target_event, message_this.data['file'], 'images')
                #this_msg.data.msg_type = 7
                #this_msg.data.msg_seq = get_msgid(str(this_msg.data.msg_id))
                #this_msg.do_api()
                #flag_now_type = 'image'
                pass
            elif type(message_this) == OlivOS.messageAPI.PARA.text:
                res += message_this.OP()
                flag_now_type = 'string'
            if size_data == count_data\
            or (flag_now_type_last != flag_now_type \
            and flag_now_type_last == 'string' \
            and len(res) > 0):
                this_msg.data.content = res
                this_msg.data.msg_type = 0
                this_msg.data.msg_seq = get_msgid(str(this_msg.data.msg_id))
                this_msg.do_api()
                res = ''

    def send_msg(target_event, chat_id, message, reply_msg_id=None, flag_direct=False):
        this_msg = None
        if flag_direct:
            this_msg = API.sendDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.guild_id = int(chat_id)
        else:
            this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.channel_id = int(chat_id)
        if this_msg is None:
            return
        this_msg.data.msg_id = reply_msg_id
        flag_now_type = 'string'
        res = ''
        for message_this in message.data:
            if type(message_this) == OlivOS.messageAPI.PARA.image:
                pass
            elif type(message_this) == OlivOS.messageAPI.PARA.text:
                res += message_this.OP()
                flag_now_type = 'string'
        if res != '':
            this_msg.data.content = res
            #this_msg.data.msg_type = 0
            this_msg.do_api()

    def get_login_info(target_event):
        global sdkSelfInfo
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        raw_obj = None
        if target_event.bot_info.hash in sdkSelfInfo \
        and type(sdkSelfInfo[target_event.bot_info.hash]) is dict \
        and 'id' in sdkSelfInfo[target_event.bot_info.hash] \
        and 'username' in sdkSelfInfo[target_event.bot_info.hash]:
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
                    if type(raw_obj) is dict \
                    and 0 == init_api_do_mapping_for_dict(raw_obj, ['code'], int):
                        res_data['active'] = True
                        res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['username'], str)
                        res_data['data']['id'] = str(init_api_do_mapping_for_dict(raw_obj, ['id'], str))
            except:
                res_data['active'] = False
        return res_data

    # 现场上传的就地实现
    def setResourceUploadFast(target_event, url: str, type_path: str = 'images', type_chat: str = 'qq_groups'):
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
            msg_upload_api.data.type = type_chat
            msg_upload_api.do_api('POST', check_list[type_path])
            #print(msg_upload_api.res)
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


def get_msgid(key:str):
    global sdkMsgidinfo
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
    except:
        tmp_obj = None
    if type(tmp_obj) == dict:
        flag_is_active = True
    if flag_is_active:
        if type(tmp_obj) == dict:
            res_data = tmp_obj.copy()
        elif type(tmp_obj) == list:
            res_data = tmp_obj.copy()
    return res_data


def init_api_do_mapping(src_type, src_data):
    if type(src_data) is src_type:
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
