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
    'wss': 'wss://chat.xiaoheihe.cn',
    'default': 'https://chat.xiaoheihe.cn',
    'native': 'https://chat.xiaoheihe.cn',
    'chat-upload': 'https://chat-upload.xiaoheihe.cn'
}

sdkAPIRoute = {
    'wss': '/chatroom/ws/connect',
    'channel_msg': '/chatroom/v2/channel_msg',
    'msg': '/chatroom/v3/msg',
    'chat-upload': '/upload',
    'room': '/chatroom/v2/room',
    'room_role': '/chatroom/v2/room_role'
}

sdkAPIParams = {
    'client_type': 'heybox_chat',
    'x_client_type': 'web',
    'os_type': 'web',
    'x_os_type': 'bot',
    'x_app': 'heybox_chat',
    'chat_os_type': 'bot',
    'chat_version': '1.30.0'
}

sdkAPIRouteTemp = {}

sdkSubSelfInfo = {}

# 缓存房间管理员角色ID
sdkRoomAdminRoleId = {}


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
    tmp_sdkAPIParams = sdkAPIParams.copy()
    tmp_sdkAPIParams['token'] = token
    send_url = f"{sdkAPIHost['wss']}{sdkAPIRoute['wss']}?{parse.urlencode(tmp_sdkAPIParams)}"
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
            send_url = self.host + self.route
            send_url = send_url.format(**tmp_sdkAPIRouteTemp)
            send_url = f'{send_url}?{parse.urlencode(sdkAPIParams)}'
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

    class setResourceUpload(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['chat-upload']
            self.route = sdkAPIRoute['chat-upload']

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
                send_url = self.host + self.route
                send_url = send_url.format(**tmp_sdkAPIRouteTemp)
                send_url = f'{send_url}?{parse.urlencode(sdkAPIParams)}'
                headers = {
                    'Content-Type': payload.content_type,
                    'Content-Length': str(len(self.data.file)),
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'Token': self.bot_info.access_token
                }

                msg_res = None
                if req_type == 'POST':
                    msg_res = req.request("POST", send_url, headers=headers, data=payload)

                self.res = msg_res.text
                return msg_res.text
            except Exception as e:
                traceback.print_exc()
                return None

    class setRoomNickname(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['room'] + '/nickname'

        class data_T(object):
            def __init__(self):
                self.nickname = None
                self.room_id = None
                self.to_user_id = None

    class leaveRoom(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['room'] + '/leave'

        class data_T(object):
            def __init__(self):
                self.room_id = None

    class kickOutUser(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['room'] + '/kick_out'

        class data_T(object):
            def __init__(self):
                self.room_id = None
                self.to_user_id = None

    class banUser(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['room'] + '/ban'

        class data_T(object):
            def __init__(self):
                self.room_id = None
                self.to_user_id = None
                self.duration = None
                self.reason = None

    class getRoomUserList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['room'] + '/users'

        class metadata_T(object):
            def __init__(self):
                self.room_id = None
                self.limit = 300
                self.offset = 0

        def do_api(self, req_type='GET'):
            try:
                tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
                send_url = self.host + self.route
                send_url = send_url.format(**tmp_sdkAPIRouteTemp)
                
                # 构建查询参数
                params = sdkAPIParams.copy()
                if self.metadata is not None:
                    if self.metadata.room_id is not None:
                        params['room_id'] = str(self.metadata.room_id)
                    if self.metadata.limit is not None:
                        params['limit'] = str(self.metadata.limit)
                    if self.metadata.offset is not None:
                        params['offset'] = str(self.metadata.offset)
                
                send_url = f'{send_url}?{parse.urlencode(params)}'
                headers = {
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'Token': self.bot_info.access_token
                }

                msg_res = None
                if req_type == 'GET':
                    msg_res = req.request("GET", send_url, headers=headers)

                self.res = msg_res.text
                return msg_res.text
            except:
                return None

    class getJoinedRoomList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['room'] + '/joined'

        class metadata_T(object):
            def __init__(self):
                self.limit = 50
                self.offset = 0

        def do_api(self, req_type='GET'):
            try:
                tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
                send_url = self.host + self.route
                send_url = send_url.format(**tmp_sdkAPIRouteTemp)
                
                # 构建查询参数
                params = sdkAPIParams.copy()
                if self.metadata is not None:
                    if self.metadata.limit is not None:
                        params['limit'] = str(self.metadata.limit)
                    if self.metadata.offset is not None:
                        params['offset'] = str(self.metadata.offset)
                
                send_url = f'{send_url}?{parse.urlencode(params)}'
                headers = {
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'Token': self.bot_info.access_token
                }

                msg_res = None
                if req_type == 'GET':
                    msg_res = req.request("GET", send_url, headers=headers)

                self.res = msg_res.text
                return msg_res.text
            except:
                return None

    class getRoomRoleList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['room_role'] + '/roles'

        class metadata_T(object):
            def __init__(self):
                self.room_id = None

        def do_api(self, req_type='GET'):
            try:
                tmp_sdkAPIRouteTemp = sdkAPIRouteTemp.copy()
                send_url = self.host + self.route
                send_url = send_url.format(**tmp_sdkAPIRouteTemp)

                # 构建查询参数
                params = sdkAPIParams.copy()
                if self.metadata is not None:
                    if self.metadata.room_id is not None:
                        params['room_id'] = str(self.metadata.room_id)
                
                send_url = f'{send_url}?{parse.urlencode(params)}'
                headers = {
                    'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA,
                    'Token': self.bot_info.access_token
                }

                msg_res = None
                if req_type == 'GET':
                    msg_res = req.request("GET", send_url, headers=headers)

                self.res = msg_res.text
                return msg_res.text
            except:
                return None


def get_room_admin_role_id(bot_info, room_id):
    """
    获取并缓存房间的管理员role_id列表
    通过调用getRoomRoleList，在roles数组中查找"高级管理员"角色
    """
    global sdkRoomAdminRoleId
    room_id_str = str(room_id)
    
    # 如果缓存中已有，直接返回
    if room_id_str in sdkRoomAdminRoleId:
        return sdkRoomAdminRoleId[room_id_str]
    
    admin_role_ids = []
    try:
        this_msg = API.getRoomRoleList(bot_info)
        this_msg.metadata.room_id = room_id_str
        this_msg.do_api('GET')
        
        if this_msg.res is not None:
            raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None and type(raw_obj) == dict:
                if 'result' in raw_obj and 'roles' in raw_obj['result']:
                    roles = raw_obj['result']['roles']
                    # 查找管理员角色 (type=3,4,5,6,7 都是管理员)
                    admin_types = [3, 4, 5, 6, 7]
                    for role in roles:
                        if type(role) == dict:
                            role_id = role.get('id')
                            role_name = role.get('name')
                            role_type = role.get('type')
                            # 通过type判断: 3=成员管理员, 4=文字频道管理员, 5=语音频道管理员, 6=社区共建者, 7=高级管理员
                            if role_type in admin_types:
                                admin_role_id = role.get('id')
                                if admin_role_id is not None:
                                    admin_role_ids.append(str(admin_role_id))
    except Exception as e:
        traceback.print_exc()
    
    # 缓存结果
    sdkRoomAdminRoleId[room_id_str] = admin_role_ids if len(admin_role_ids) > 0 else None
    return sdkRoomAdminRoleId[room_id_str]


def determine_user_role(user_data, admin_role_ids):
    """
    根据用户数据判断用户的role
    """
    user_id = user_data.get('user_id', 'unknown')
    is_master = user_data.get('is_master', False)
    user_roles = user_data.get('roles', [])
    
    # 如果 is_master 为 true，返回 owner
    if is_master == True:
        return 'owner'
    
    # 如果 roles 数组中包含任何一个管理员 role_id
    if admin_role_ids is not None:
        if type(user_roles) == list and type(admin_role_ids) == list:
            for admin_role_id in admin_role_ids:
                if str(admin_role_id) in [str(r) for r in user_roles]:
                    return 'admin'
    
    # 默认返回普通成员
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

    # 我是搞不明白了，为什么文档里面说的是50，实际上收到的消息type是5？？？？？？？？？？？？？？？？
    if '5' == target_event.sdk_event.payload.data.type or '50' == target_event.sdk_event.payload.data.type:
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
                message_obj = OlivOS.messageAPI.Message_templet(
                    'xiaoheihe_string',
                    msg_raw
                )
                target_event.data = target_event.group_message(
                    str(target_event.sdk_event.payload.data.data['channel_id']),
                    str(target_event.sdk_event.payload.data.data['user_id']),
                    msg_raw,
                    'group'
                )
                target_event.data.host_id = str(target_event.sdk_event.payload.data.data['room_id'])
                target_event.data.message_sdk = message_obj
                target_event.data.message_id = str(target_event.sdk_event.payload.data.data['msg_id'])
                target_event.data.raw_message = msg_raw
                target_event.data.raw_message_sdk = message_obj
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(target_event.sdk_event.payload.data.data['user_id'])
                target_event.data.sender['nickname'] = str(target_event.sdk_event.payload.data.data['nickname'])
                target_event.data.sender['id'] = target_event.data.sender['user_id']
                target_event.data.sender['name'] = target_event.data.sender['nickname']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0
                # 判断发送者角色
                room_id = str(target_event.sdk_event.payload.data.data['room_id'])
                user_id = str(target_event.sdk_event.payload.data.data['user_id'])
                user_data = {
                    'user_id': user_id
                }
                if 'is_master' in target_event.sdk_event.payload.data.data:
                    user_data['is_master'] = target_event.sdk_event.payload.data.data['is_master']
                if 'roles' in target_event.sdk_event.payload.data.data:
                    user_data['roles'] = target_event.sdk_event.payload.data.data['roles']
                bot_info = bot_info_T(
                    target_event.sdk_event.base_info['self_id'],
                    target_event.sdk_event.base_info['token']
                )
                admin_role_ids = get_room_admin_role_id(bot_info, room_id)
                target_event.data.sender['role'] = determine_user_role(user_data, admin_role_ids)
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
    
    elif '3001' == target_event.sdk_event.payload.data.type:
        try:
            if 'room_base_info' in target_event.sdk_event.payload.data.data \
            and 'user_info' in target_event.sdk_event.payload.data.data \
            and 'state' in target_event.sdk_event.payload.data.data:
                room_base_info = target_event.sdk_event.payload.data.data['room_base_info']
                user_info = target_event.sdk_event.payload.data.data['user_info']
                state = target_event.sdk_event.payload.data.data['state']
                host_id = str(room_base_info.get('room_id', ''))
                user_id = str(user_info.get('user_id', ''))
                if state == 1:
                    # 用户加入房间
                    target_event.active = True
                    target_event.plugin_info['func_type'] = 'group_member_increase'
                    target_event.data = target_event.group_member_increase(
                        None,
                        '-1',
                        user_id,
                        host_id
                    )
                    target_event.data.action = 'join'
                elif state == 0:
                    # 用户退出房间
                    target_event.active = True
                    target_event.plugin_info['func_type'] = 'group_member_decrease'
                    target_event.data = target_event.group_member_decrease(
                        None,
                        '-1',
                        user_id,
                        host_id
                    )
                    target_event.data.action = 'leave'  # 退出房间
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
        
        # 用于累积文本内容
        text_buffer = ''
        
        for message_this in message.data:
            if type(message_this) == OlivOS.messageAPI.PARA.text:
                # 累积文本内容
                text_buffer += message_this.data['text']
            elif type(message_this) == OlivOS.messageAPI.PARA.at:
                # 将 AT 转换为小黑盒格式
                if 'id' in message_this.data and message_this.data['id'] is not None:
                    text_buffer += f"@{{id:{message_this.data['id']}}}"
            elif type(message_this) == OlivOS.messageAPI.PARA.image:
                # 如果有累积的文本,先发送
                if text_buffer:
                    res_data['modules'].append(
                        {
                            "type": "section",
                            "paragraph": [
                                {
                                    "type": "plain-text",
                                    "text": text_buffer.replace('\r\n', '\n').replace('\n', '<br>')
                                }
                            ]
                        }
                    )
                    text_buffer = ''
                # 发送图片
                image_path = event_action.setResourceUploadFast(target_event, message_this.data['file'], 'images')
                if image_path:
                    res_data['modules'].append(
                        {
                            "type": "images",
                            "urls": [
                                {
                                  "url": image_path
                                }
                            ]
                        }
                    )
        # 发送剩余的文本
        if text_buffer:
            res_data['modules'].append(
                {
                    "type": "section",
                    "paragraph": [
                        {
                            "type": "plain-text",
                            "text": text_buffer.replace('\r\n', '\n').replace('\n', '<br>')
                        }
                    ]
                }
            )
        
        if len(res_data['modules']) > 0:
            this_msg.data.msg = json.dumps({"data": [res_data]}, ensure_ascii=False)
            this_msg.do_api()

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

            msg_upload_api = API.setResourceUpload(get_SDK_bot_info_from_Event(target_event))
            msg_upload_api.data.file = pic_file
            msg_upload_api.do_api('POST', check_list[type_path])
            if msg_upload_api.res is not None:
                msg_upload_api_obj = json.loads(msg_upload_api.res)
                if 'status' in msg_upload_api_obj \
                and 'ok' == msg_upload_api_obj['status'] \
                and 'result' in msg_upload_api_obj \
                and 'url' in msg_upload_api_obj['result']:
                    res = msg_upload_api_obj['result']['url']
        except Exception as e:
            traceback.print_exc()
            res = None
        return res

    # /room 相关接口
    # 这里没问题，没改是因为——最多限制20个字！！！！！！！
    def set_group_card(target_event, group_id, user_id, card):
        """
        修改房间内昵称
        """
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.setRoomNickname(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.room_id = str(group_id)
        this_msg.data.to_user_id = int(user_id)
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
        """
        退出房间
        """
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.leaveRoom(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.room_id = str(group_id)
        try:
            this_msg.do_api('POST')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None:
                if type(raw_obj) is dict:
                    res_data['active'] = True
        except Exception as e:
            res_data['active'] = False
        return res_data

    def set_group_kick(target_event, group_id, user_id):
        """
        房间踢人
        """
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.kickOutUser(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.room_id = str(group_id)
        this_msg.data.to_user_id = str(user_id)
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

    def set_group_ban(target_event, group_id, user_id, duration):
        """
        禁言/解禁用户
        """
        raw_obj = None
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        this_msg = API.banUser(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.room_id = str(group_id)
        this_msg.data.to_user_id = int(user_id)
        this_msg.data.duration = int(duration)
        this_msg.data.reason = "Bot operation"
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

    # 猜猜为什么我要做重试呢，好难猜啊，fxxk黑盒！！！
    def get_group_member_list(target_event, group_id):
        """
        获取房间用户列表
        包含错误重试逻辑:
        - 如果请求失败,会尝试修改offset为10再重试
        - 然后再将offset改回0接受数据
        - 最多重试3次,每次间隔1秒
        """
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_list()
        raw_obj = None
        max_retry = 3
        retry_count = 0
        
        # 获取管理员role_id列表
        bot_info = get_SDK_bot_info_from_Event(target_event)
        admin_role_ids = get_room_admin_role_id(bot_info, group_id)
        
        while retry_count < max_retry:
            try:
                #尝试 offset=0
                this_msg = API.getRoomUserList(get_SDK_bot_info_from_Event(target_event))
                this_msg.metadata.room_id = str(group_id)
                this_msg.metadata.limit = 300
                this_msg.metadata.offset = 0
                this_msg.do_api('GET')
                if this_msg.res is not None:
                    raw_obj = init_api_json(this_msg.res)
                    
                if raw_obj is not None and type(raw_obj) == dict:
                    # 请求成功
                    if 'result' in raw_obj and 'room_info' in raw_obj['result']:
                        room_info = raw_obj['result']['room_info']
                        if 'user_info' in room_info:
                            res_data['active'] = True
                            for user_this in room_info['user_info']:
                                tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_member_info_strip()
                                tmp_res_data_this['id'] = str(user_this.get('user_id', ''))
                                tmp_res_data_this['user_id'] = str(user_this.get('user_id', ''))
                                tmp_res_data_this['name'] = user_this.get('username', '')
                                tmp_res_data_this['card'] = user_this.get('room_nickname', user_this.get('nickname', ''))
                                tmp_res_data_this['group_id'] = str(group_id)
                                # 判断角色
                                user_data = {
                                    'user_id': user_this.get('user_id', '')
                                }
                                if 'is_master' in user_this:
                                    user_data['is_master'] = user_this['is_master']
                                if 'roles' in user_this:
                                    user_data['roles'] = user_this['roles']
                                tmp_res_data_this['role'] = determine_user_role(user_data, admin_role_ids)
                                
                                res_data['data'].append(tmp_res_data_this)
                    break
                else:
                    # 请求失败,尝试 offset=10
                    this_msg_retry = API.getRoomUserList(get_SDK_bot_info_from_Event(target_event))
                    this_msg_retry.metadata.room_id = str(group_id)
                    this_msg_retry.metadata.limit = 300
                    this_msg_retry.metadata.offset = 10
                    this_msg_retry.do_api('GET')
                    time.sleep(1)
                    # 再次尝试 offset=0
                    this_msg_final = API.getRoomUserList(get_SDK_bot_info_from_Event(target_event))
                    this_msg_final.metadata.room_id = str(group_id)
                    this_msg_final.metadata.limit = 300
                    this_msg_final.metadata.offset = 0
                    this_msg_final.do_api('GET')
                    if this_msg_final.res is not None:
                        raw_obj = init_api_json(this_msg_final.res)
                    if raw_obj is not None and type(raw_obj) == dict:
                        # 重试成功
                        if 'result' in raw_obj and 'room_info' in raw_obj['result']:
                            room_info = raw_obj['result']['room_info']
                            if 'user_info' in room_info:
                                res_data['active'] = True
                                for user_this in room_info['user_info']:
                                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_member_info_strip()
                                    tmp_res_data_this['id'] = str(user_this.get('user_id', ''))
                                    tmp_res_data_this['user_id'] = str(user_this.get('user_id', ''))
                                    tmp_res_data_this['name'] = user_this.get('username', '')
                                    tmp_res_data_this['card'] = user_this.get('room_nickname', user_this.get('nickname', ''))
                                    tmp_res_data_this['group_id'] = str(group_id)
                                    
                                    # 判断角色: owner(房主) / admin(管理员) / member(普通成员)
                                    user_data = {
                                        'user_id': user_this.get('user_id', '')
                                    }
                                    if 'is_master' in user_this:
                                        user_data['is_master'] = user_this['is_master']
                                    if 'roles' in user_this:
                                        user_data['roles'] = user_this['roles']
                                    tmp_res_data_this['role'] = determine_user_role(user_data, admin_role_ids)
                                    
                                    res_data['data'].append(tmp_res_data_this)
                        break
                    # 重试也失败,增加计数
                    retry_count += 1
                    if retry_count < max_retry:
                        time.sleep(1)
            except Exception as e:
                traceback.print_exc()
                retry_count += 1
                if retry_count < max_retry:
                    time.sleep(1)
        if not res_data['active']:
            res_data['active'] = False
        return res_data

    # 至少这个api没问题，乐
    def get_group_list(target_event):
        """
        获取加入的房间列表
        """
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_list()
        raw_obj = None
        try:
            this_msg = API.getJoinedRoomList(get_SDK_bot_info_from_Event(target_event))
            # limit=50, offset=0 已在 metadata_T 中设置
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
            if raw_obj is not None and type(raw_obj) == dict:
                if 'result' in raw_obj and 'rooms' in raw_obj['result']:
                    rooms_data = raw_obj['result']['rooms']
                    if 'rooms' in rooms_data:
                        res_data['active'] = True
                        for room_this in rooms_data['rooms']:
                            tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_group_info_strip()
                            tmp_res_data_this['id'] = str(room_this.get('room_id', ''))
                            tmp_res_data_this['name'] = room_this.get('room_name', '')
                            tmp_res_data_this['avatar'] = room_this.get('room_avatar', '')
                            # 添加额外信息到 extra 字段
                            tmp_res_data_this['extra'] = {
                                'room_pic': room_this.get('room_pic', ''),
                                'create_by': room_this.get('create_by', ''),
                                'is_public': room_this.get('is_public', 0),
                                'public_id': room_this.get('public_id', ''),
                                'is_hot': room_this.get('is_hot', 0),
                                'join_time': room_this.get('join_time', 0)
                            }
                            res_data['data'].append(tmp_res_data_this)
            else:
                res_data['active'] = False
        except Exception as e:
            traceback.print_exc()
            res_data['active'] = False
        return res_data

    # /room_role相关接口
    def get_group_role_list(target_event, room_id):
        """
        获取房间角色列表
        """
        res_data = {
            'active': False,
            'data': []
        }
        raw_obj = None
        try:
            this_msg = API.getRoomRoleList(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.room_id = str(room_id)
            this_msg.do_api('GET')
            if this_msg.res is not None:
                raw_obj = init_api_json(this_msg.res)
                
            if raw_obj is not None and type(raw_obj) == dict:
                if 'result' in raw_obj and 'roles' in raw_obj['result']:
                    roles_list = raw_obj['result']['roles']
                    if isinstance(roles_list, list):
                        res_data['active'] = True
                        for role_this in roles_list:
                            tmp_role_data = {
                                'id': str(role_this.get('id', '')),
                                'name': role_this.get('name', ''),
                                'color': role_this.get('color', 0),
                                'position': role_this.get('position', 0),
                                'permissions': role_this.get('permissions', '0'),
                                'type': role_this.get('type', 0),
                                'hoist': role_this.get('hoist', 0),
                                'mentionable': role_this.get('mentionable', 0),
                                'extra': {
                                    'icon': role_this.get('icon', ''),
                                    'color_list': role_this.get('color_list'),
                                    'department_id': role_this.get('department_id', ''),
                                    'room_id': role_this.get('room_id', ''),
                                    'del_tag': role_this.get('del_tag', 1),
                                    'creator': role_this.get('creator', '0'),
                                    'create_time': role_this.get('create_time', 0)
                                }
                            }
                            res_data['data'].append(tmp_role_data)
            else:
                res_data['active'] = False
        except Exception as e:
            traceback.print_exc()
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
        # 支持两种返回格式: code == 0 或 status == 'ok'。猜猜为什么要这样呢？乐
        if ('code' in tmp_obj and tmp_obj['code'] == 0) or \
           ('status' in tmp_obj and tmp_obj['status'] == 'ok'):
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
