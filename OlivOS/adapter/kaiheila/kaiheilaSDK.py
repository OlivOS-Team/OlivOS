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
    'game': '/game',
    'guild': '/guild',
    'guild-mute': '/guild-mute',
    'guild-boost': '/guild-boost'
}

sdkAPIRouteTemp = {}

sdkSubSelfInfo = {}

# 缓存每个guild的管理员role_id: {guild_id: admin_role_id}
sdkGuildAdminRoleId = {}


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

    # 服务器相关接口
    class getGuildList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild'] + '/list?page={page}&page_size={page_size}'

        class metadata_T(object):
            def __init__(self):
                self.page = 1
                self.page_size = 100

    class getGuildView(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild'] + '/view?guild_id={guild_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = None

    class getGuildUserList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild'] + '/user-list?guild_id={guild_id}&channel_id={channel_id}&page={page}&page_size={page_size}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = None
                self.channel_id = ''
                self.page = 1
                self.page_size = 100

    class setGuildNickname(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild'] + '/nickname'

        class data_T(object):
            def __init__(self):
                self.guild_id = None
                self.nickname = None
                self.user_id = None

    class setGuildLeave(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild'] + '/leave'

        class data_T(object):
            def __init__(self):
                self.guild_id = None

    class setGuildKickout(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild'] + '/kickout'

        class data_T(object):
            def __init__(self):
                self.guild_id = None
                self.target_id = None

    class getGuildMuteList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild-mute'] + '/list?guild_id={guild_id}&return_type={return_type}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = None
                self.return_type = 'detail'

    class setGuildMuteCreate(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild-mute'] + '/create'

        class data_T(object):
            def __init__(self):
                self.guild_id = None
                self.user_id = None
                self.type = 1

    class setGuildMuteDelete(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild-mute'] + '/delete'

        class data_T(object):
            def __init__(self):
                self.guild_id = None
                self.user_id = None
                self.type = 1

    class getGuildBoostHistory(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guild-boost'] + '/history?guild_id={guild_id}&start_time={start_time}&end_time={end_time}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = None
                self.start_time = ''
                self.end_time = ''

    # 频道相关接口
    class getChannelList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channel'] + '/list?guild_id={guild_id}&page={page}&page_size={page_size}&type={type}&parent_id={parent_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = None
                self.page = 1
                self.page_size = 100
                self.type = ''
                self.parent_id = ''

    class getChannelView(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channel'] + '/view?target_id={target_id}&need_children={need_children}'

        class metadata_T(object):
            def __init__(self):
                self.target_id = None
                self.need_children = 'false'

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

def get_guild_admin_role_id(bot_info, guild_id):
    """
    获取并缓存guild的管理员role_id
    通过调用/guild/view API，在roles数组中查找name为"管理员"的角色
    """
    global sdkGuildAdminRoleId
    guild_id_str = str(guild_id)
    # 如果缓存中已有，直接返回
    if guild_id_str in sdkGuildAdminRoleId:
        return sdkGuildAdminRoleId[guild_id_str]
    # 调用API获取guild信息
    try:
        this_msg = API.getGuildView(bot_info)
        this_msg.metadata.guild_id = guild_id_str
        this_msg.do_api('GET')
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None and type(raw_obj) == dict:
                if 'data' in raw_obj and 'roles' in raw_obj['data']:
                    roles = raw_obj['data']['roles']
                    # 查找name为"管理员"的角色
                    for role in roles:
                        if type(role) == dict and 'name' in role and role['name'] == '管理员':
                            admin_role_id = role.get('role_id')
                            if admin_role_id is not None:
                                sdkGuildAdminRoleId[guild_id_str] = admin_role_id
                                return admin_role_id
    except Exception as e:
        traceback.print_exc()
    
    # 如果没找到，缓存None避免重复请求
    sdkGuildAdminRoleId[guild_id_str] = None
    return None

def determine_user_role(user_data, admin_role_id):
    """
    根据用户数据判断用户的role
    """
    # 如果is_master为true，返回owner
    if user_data.get('is_master') == True:
        return 'owner'
    # 如果roles数组中包含管理员role_id，返回admin
    if admin_role_id is not None:
        user_roles = user_data.get('roles', [])
        if type(user_roles) == list and admin_role_id in user_roles:
            return 'admin'
    return 'member'

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
                        # 获取guild_id和user_id用于判断role
                        guild_id = str(target_event.sdk_event.payload.data.d['extra']['guild_id'])
                        user_id = str(target_event.sdk_event.payload.data.d['extra']['author']['id'])
                        target_event.data.host_id = guild_id
                        # 获取管理员role_id
                        tmp_bot_info = bot_info_T(
                            target_event.sdk_event.base_info['self_id'],
                            target_event.sdk_event.base_info['token']
                        )
                        admin_role_id = get_guild_admin_role_id(tmp_bot_info, guild_id)
                        # 尝试从事件数据中获取用户信息，如果没有则调用API
                        user_data = {}
                        if 'extra' in target_event.sdk_event.payload.data.d:
                            extra = target_event.sdk_event.payload.data.d['extra']
                            if 'author' in extra:
                                author = extra['author']
                                # 检查是否有is_master和roles字段
                                if 'is_master' in author:
                                    user_data['is_master'] = author['is_master']
                                if 'roles' in author:
                                    user_data['roles'] = author['roles']
                        # 如果事件数据中没有完整信息，调用API获取
                        if 'is_master' not in user_data or 'roles' not in user_data:
                            try:
                                this_msg = API.getUserView(tmp_bot_info)
                                this_msg.metadata.user_id = user_id
                                this_msg.metadata.guild_id = guild_id
                                this_msg.do_api('GET')
                                if this_msg.res is not None:
                                    raw_obj = init_api_json(this_msg.res)
                                    if raw_obj is not None and type(raw_obj) == dict:
                                        if 'data' in raw_obj:
                                            data = raw_obj['data']
                                            if 'is_master' in data:
                                                user_data['is_master'] = data['is_master']
                                            if 'roles' in data:
                                                user_data['roles'] = data['roles']
                            except:
                                pass
                        # 判断role
                        target_event.data.sender['role'] = determine_user_role(user_data, admin_role_id)
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
            else:
                if 'type' in target_event.sdk_event.payload.data.d \
                and target_event.sdk_event.payload.data.d['type'] == 255 \
                and 'extra' in target_event.sdk_event.payload.data.d \
                and type(target_event.sdk_event.payload.data.d['extra']) is dict:
                    if 'body' in target_event.sdk_event.payload.data.d['extra'] \
                    and type(target_event.sdk_event.payload.data.d['extra']['body']) is dict \
                    and 'type' in target_event.sdk_event.payload.data.d['extra'] \
                    and target_event.sdk_event.payload.data.d['extra']['type'] == 'message_btn_click':
                        if 'channel_type' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and target_event.sdk_event.payload.data.d['extra']['body']['channel_type'] == 'PERSON' \
                        and 'target_id' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['target_id']) is str \
                        and 'user_id' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['user_id']) is str \
                        and 'value' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['value']) is str \
                        and 'user_info' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['user_info']) is dict \
                        and 'id' in target_event.sdk_event.payload.data.d['extra']['body']['user_info'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['user_info']['id']) is str \
                        and 'username' in target_event.sdk_event.payload.data.d['extra']['body']['user_info'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['user_info']['username']) is str:
                            target_event.active = True
                            target_event.plugin_info['func_type'] = 'private_message'
                            msg = target_event.sdk_event.payload.data.d['extra']['body']['value']
                            user_id = target_event.sdk_event.payload.data.d['extra']['body']['user_info']['id']
                            user_name = target_event.sdk_event.payload.data.d['extra']['body']['user_info']['username']
                            message_obj = OlivOS.messageAPI.Message_templet(
                                'olivos_para',
                                [OlivOS.messageAPI.PARA.text(text=msg)]
                            )
                            target_event.data = target_event.private_message(
                                user_id,
                                message_obj,
                                'friend'
                            )
                            target_event.data.message_sdk = message_obj
                            target_event.data.message_id = str(-1)
                            target_event.data.raw_message = message_obj
                            target_event.data.raw_message_sdk = message_obj
                            target_event.data.font = None
                            target_event.data.sender['user_id'] = user_id
                            target_event.data.sender['nickname'] = user_name
                            target_event.data.sender['id'] = user_id
                            target_event.data.sender['name'] = user_name
                            target_event.data.sender['sex'] = 'unknown'
                            target_event.data.sender['age'] = 0
                            target_event.data.extend['flag_from_direct'] = True
                            if plugin_event_bot_hash in sdkSubSelfInfo:
                                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])
                        elif 'channel_type' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and target_event.sdk_event.payload.data.d['extra']['body']['channel_type'] == 'GROUP' \
                        and 'target_id' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['target_id']) is str \
                        and 'guild_id' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['guild_id']) is str \
                        and 'user_id' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['user_id']) is str \
                        and 'value' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['value']) is str \
                        and 'user_info' in target_event.sdk_event.payload.data.d['extra']['body'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['user_info']) is dict \
                        and 'id' in target_event.sdk_event.payload.data.d['extra']['body']['user_info'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['user_info']['id']) is str \
                        and 'username' in target_event.sdk_event.payload.data.d['extra']['body']['user_info'] \
                        and type(target_event.sdk_event.payload.data.d['extra']['body']['user_info']['username']) is str:
                            target_event.active = True
                            target_event.plugin_info['func_type'] = 'group_message'
                            msg = target_event.sdk_event.payload.data.d['extra']['body']['value']
                            host_id = target_event.sdk_event.payload.data.d['extra']['body']['guild_id']
                            group_id = target_event.sdk_event.payload.data.d['extra']['body']['target_id']
                            user_id = target_event.sdk_event.payload.data.d['extra']['body']['user_info']['id']
                            user_name = target_event.sdk_event.payload.data.d['extra']['body']['user_info']['username']
                            message_obj = OlivOS.messageAPI.Message_templet(
                                'olivos_para',
                                [OlivOS.messageAPI.PARA.text(text=msg)]
                            )
                            target_event.data = target_event.group_message(
                                group_id,
                                user_id,
                                message_obj,
                                'group'
                            )
                            target_event.data.message_sdk = message_obj
                            target_event.data.message_id = str(-1)
                            target_event.data.raw_message = message_obj
                            target_event.data.raw_message_sdk = message_obj
                            target_event.data.font = None
                            target_event.data.sender['user_id'] = user_id
                            target_event.data.sender['nickname'] = user_name
                            target_event.data.sender['id'] = user_id
                            target_event.data.sender['name'] = user_name
                            target_event.data.sender['sex'] = 'unknown'
                            target_event.data.sender['age'] = 0
                            # 获取管理员role_id并判断用户role
                            tmp_bot_info = bot_info_T(
                                target_event.sdk_event.base_info['self_id'],
                                target_event.sdk_event.base_info['token']
                            )
                            admin_role_id = get_guild_admin_role_id(tmp_bot_info, host_id)
                            # 尝试从事件数据中获取用户信息，如果没有则调用API
                            user_data = {}
                            body = target_event.sdk_event.payload.data.d['extra']['body']
                            if 'user_info' in body:
                                user_info = body['user_info']
                                if 'is_master' in user_info:
                                    user_data['is_master'] = user_info['is_master']
                                if 'roles' in user_info:
                                    user_data['roles'] = user_info['roles']
                            # 如果事件数据中没有完整信息，调用API获取
                            if 'is_master' not in user_data or 'roles' not in user_data:
                                try:
                                    this_msg = API.getUserView(tmp_bot_info)
                                    this_msg.metadata.user_id = user_id
                                    this_msg.metadata.guild_id = host_id
                                    this_msg.do_api('GET')
                                    if this_msg.res is not None:
                                        raw_obj = init_api_json(this_msg.res)
                                        if raw_obj is not None and type(raw_obj) == dict:
                                            if 'data' in raw_obj:
                                                data = raw_obj['data']
                                                if 'is_master' in data:
                                                    user_data['is_master'] = data['is_master']
                                                if 'roles' in data:
                                                    user_data['roles'] = data['roles']
                                except:
                                    pass
                            # 判断role
                            target_event.data.sender['role'] = determine_user_role(user_data, admin_role_id)
                            target_event.data.host_id = host_id
                            target_event.data.extend['flag_from_direct'] = False
                            if plugin_event_bot_hash in sdkSubSelfInfo:
                                target_event.data.extend['sub_self_id'] = str(sdkSubSelfInfo[plugin_event_bot_hash])

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
                "theme": "primary",
                "color": "#009FE9",
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

    def create_message(target_event, chat_id, content_type:int, content:str, flag_direct=False):
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['active'] = True
        this_msg = None
        if flag_direct:
            this_msg = API.creatDirectMessage(get_SDK_bot_info_from_Event(target_event))
        else:
            this_msg = API.creatMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.target_id = str(chat_id)
        this_msg.data.type = content_type
        this_msg.data.content = content
        this_msg.do_api()
        res_data['data'] = {}
        res_data['data']['chat_type'] = 'private' if flag_direct else 'group'
        res_data['data']['chat_id'] = str(chat_id)
        res_data['data']['content_type'] = str(content_type)
        res_data['data']['content'] = str(json.dumps(content, ensure_ascii = False))
        return res_data

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
                    # 获取管理员role_id并判断用户role
                    bot_info = get_SDK_bot_info_from_Event(target_event)
                    admin_role_id = get_guild_admin_role_id(bot_info, host_id)
                    # 从API返回数据中提取用户信息
                    user_data = {}
                    if 'data' in raw_obj:
                        data = raw_obj['data']
                        if 'is_master' in data:
                            user_data['is_master'] = data['is_master']
                        if 'roles' in data:
                            user_data['roles'] = data['roles']
                    # 判断role
                    res_data['data']['role'] = determine_user_role(user_data, admin_role_id)
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

    # 服务器相关接口实现
    def get_host_list(target_event, page=1, page_size=100):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_list()
        raw_obj = None
        this_msg = API.getGuildList(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.page = page
        this_msg.metadata.page_size = page_size
        try:
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) == dict:
                    if 'data' in raw_obj and 'items' in raw_obj['data']:
                        res_data['active'] = True
                        for raw_obj_this in raw_obj['data']['items']:
                            tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_info_strip()
                            tmp_res_data_this['id'] = init_api_do_mapping_for_dict(raw_obj_this, ['id'], str)
                            tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['name'], str)
                            tmp_res_data_this['memo'] = init_api_do_mapping_for_dict(raw_obj_this, ['topic'], str)
                            res_data['data'].append(tmp_res_data_this)
        except:
            res_data['active'] = False
        return res_data

    def get_host_info(target_event, group_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_info()
        raw_obj = None
        this_msg = API.getGuildView(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(group_id)
        try:
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) == dict:
                    res_data['active'] = True
                    res_data['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'id'], str)
                    res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'name'], str)
                    res_data['data']['memo'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'topic'], str)
        except:
            res_data['active'] = False
        return res_data

    def get_group_member_list(target_event, group_id, page=1, page_size=100):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_list()
        raw_obj = None
        this_msg = API.getGuildUserList(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(group_id)
        this_msg.metadata.page = page
        this_msg.metadata.page_size = page_size
        try:
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) == dict:
                    if 'data' in raw_obj and 'items' in raw_obj['data']:
                        res_data['active'] = True
                        # 获取管理员role_id
                        bot_info = get_SDK_bot_info_from_Event(target_event)
                        admin_role_id = get_guild_admin_role_id(bot_info, group_id)
                        for raw_obj_this in raw_obj['data']['items']:
                            tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_member_info_strip()
                            tmp_res_data_this['id'] = init_api_do_mapping_for_dict(raw_obj_this, ['id'], str)
                            tmp_res_data_this['user_id'] = init_api_do_mapping_for_dict(raw_obj_this, ['id'], str)
                            tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['username'], str)
                            tmp_res_data_this['card'] = init_api_do_mapping_for_dict(raw_obj_this, ['nickname'], str)
                            tmp_res_data_this['group_id'] = str(group_id)
                            # 判断role
                            user_data = {}
                            if 'is_master' in raw_obj_this:
                                user_data['is_master'] = raw_obj_this['is_master']
                            if 'roles' in raw_obj_this:
                                user_data['roles'] = raw_obj_this['roles']
                            tmp_res_data_this['role'] = determine_user_role(user_data, admin_role_id)
                            res_data['data'].append(tmp_res_data_this)
        except:
            res_data['active'] = False
        return res_data

    def set_group_card(target_event, group_id, user_id, card):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.setGuildNickname(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.guild_id = str(group_id)
        this_msg.data.user_id = str(user_id)
        this_msg.data.nickname = str(card) if card else ""
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

    def set_group_leave(target_event, group_id):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.setGuildLeave(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.guild_id = str(group_id)
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

    def set_group_kick(target_event, group_id, user_id):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.setGuildKickout(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.guild_id = str(group_id)
        this_msg.data.target_id = str(user_id)
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

    def get_guild_mute_list(target_event, group_id):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.getGuildMuteList(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(group_id)
        this_msg.metadata.return_type = 'detail'
        try:
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) is dict:
                    res_data['active'] = True
                    res_data['data'] = raw_obj.get('data', {})
        except:
            res_data['active'] = False
        return res_data

    def set_guild_mute_create(target_event, group_id, user_id, mute_type=1):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.setGuildMuteCreate(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.guild_id = str(group_id)
        this_msg.data.user_id = str(user_id)
        this_msg.data.type = mute_type
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

    def set_guild_mute_delete(target_event, group_id, user_id, mute_type=1):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.setGuildMuteDelete(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.guild_id = str(group_id)
        this_msg.data.user_id = str(user_id)
        this_msg.data.type = mute_type
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

    def get_guild_boost_history(target_event, group_id, start_time=None, end_time=None):
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.getGuildBoostHistory(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(group_id)
        this_msg.metadata.start_time = str(start_time) if start_time else ''
        this_msg.metadata.end_time = str(end_time) if end_time else ''
        try:
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) is dict:
                    res_data['active'] = True
                    res_data['data'] = raw_obj.get('data', {})
        except:
            res_data['active'] = False
        return res_data

    # 频道相关接口实现
    def get_group_list(target_event, host_id, page=1, page_size=100, channel_type=None, parent_id=None):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_list()
        raw_obj = None
        this_msg = API.getChannelList(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(host_id)
        this_msg.metadata.page = page
        this_msg.metadata.page_size = page_size
        if channel_type is not None:
            this_msg.metadata.type = str(channel_type)
        if parent_id is not None:
            this_msg.metadata.parent_id = str(parent_id)
        try:
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) == dict:
                    if 'data' in raw_obj and 'items' in raw_obj['data']:
                        res_data['active'] = True
                        for raw_obj_this in raw_obj['data']['items']:
                            tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_info_strip()
                            tmp_res_data_this['id'] = init_api_do_mapping_for_dict(raw_obj_this, ['id'], str)
                            tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['name'], str)
                            tmp_res_data_this['memo'] = ''
                            res_data['data'].append(tmp_res_data_this)
        except:
            res_data['active'] = False
        return res_data

    def get_group_info(target_event, group_id, need_children=False):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_info()
        raw_obj = None
        this_msg = API.getChannelView(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.target_id = str(group_id)
        this_msg.metadata.need_children = 'true' if need_children else 'false'
        try:
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) == dict:
                    res_data['active'] = True
                    res_data['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'id'], str)
                    res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'name'], str)
                    res_data['data']['memo'] = init_api_do_mapping_for_dict(raw_obj, ['data', 'topic'], str)
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

    @OlivOS.API.Event.callbackLogger('kaiheila:create_message', ['chat_type', 'chat_id', 'content_type', 'content'])
    def __create_message(target_event, chat_type:str, chat_id:str, content_type:int, content:str, flag_log:bool=True):
        res_data = None
        res_data = OlivOS.kaiheilaSDK.event_action.create_message(
            target_event,
            chat_id,
            content_type,
            content,
            flag_direct = (False if chat_type == 'group' else True)
        )
        return res_data

    def create_message(
        self,
        chat_type:str,
        chat_id:str,
        content_type:int,
        content:str,
        flag_log: bool = True,
        remote: bool = False
    ):
        res_data = None
        if remote:
            pass
        else:
            res_data = inde_interface.__create_message(self.event, chat_type, chat_id, content_type, content, flag_log=True)
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
