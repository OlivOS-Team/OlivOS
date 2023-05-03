# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/onebotV12SDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import logging
import json
import multiprocessing
import threading
import time
import websocket
import uuid
import copy

import OlivOS

gResReg = {}

gTmpReg = {}

gUsrReg = {}

class bot_info_T(object):
    def __init__(self, id=-1, host='', port=-1, access_token=None):
        self.id = id
        self.host = host
        self.port = port
        self.access_token = access_token
        self.platform = 'qq'
        self.debug_mode = False
        self.debug_logger = None


def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info:OlivOS.API.bot_info_T):
    res = bot_info_T(
        id=plugin_bot_info.id,
        host=plugin_bot_info.post_info.host,
        port=plugin_bot_info.post_info.port,
        access_token=plugin_bot_info.post_info.access_token
    )
    res.platform = plugin_bot_info.platform['platform']
    res.debug_mode = plugin_bot_info.debug_mode
    return res


def get_SDK_bot_info_from_Event(target_event:OlivOS.API.Event):
    res = get_SDK_bot_info_from_Plugin_bot_info(target_event.bot_info)
    return res


class event(object):
    def __init__(self, raw:dict, bot_info:bot_info_T):
        self.json = self.event_load(raw)
        self.platform = {
            'sdk': 'onebot',
            'platform': bot_info.platform,
            'model': 'onebotV12'
        }
        self.base_info = {}
        self.active = False
        if self.json is not None:
            self.active = True
        if self.active:
            self.base_info['time'] = time.time()
            self.base_info['self_id'] = bot_info.id
            self.base_info['post_type'] = 'websocket'

    def event_load(self, raw):
        res = raw
        if type(res) is not dict:
            res = None
        return res


def get_Event_from_SDK(target_event:OlivOS.API.Event):
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info['self_id'])
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'obv12_para'

    control_queue = target_event.plugin_info['control_queue']
    bot_hash = OlivOS.API.getBotHash(
        bot_id=target_event.base_info['self_id'],
        platform_sdk=target_event.sdk_event.platform['sdk'],
        platform_platform=target_event.sdk_event.platform['platform'],
        platform_model=target_event.sdk_event.platform['model']
    )

    if 'retcode' in target_event.sdk_event.json \
    and 'echo' in target_event.sdk_event.json \
    and type(target_event.sdk_event.json['echo']) is str:
        target_event.active = False
        waitForResSet(
            target_event.sdk_event.json['echo'],
            target_event.sdk_event.json
        )
    elif 'type' in target_event.sdk_event.json \
    and 'message' == target_event.sdk_event.json['type']:
        if 'detail_type' in target_event.sdk_event.json \
        and 'private' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message'
            target_event.data = target_event.private_message(
                str(target_event.sdk_event.json['user_id']),
                '',
                'private'
            )
            target_event.data.message_sdk = OlivOS.messageAPI.Message_templet(
                'obv12_para',
                target_event.sdk_event.json['message']
            )
            target_event.data.message = target_event.sdk_event.json['message']
            target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
            target_event.data.raw_message = target_event.data.message
            target_event.data.raw_message_sdk = target_event.data.message_sdk
            target_event.data.font = None
            target_event.data.sender.update(
                {
                    'id': target_event.data.user_id,
                    'user_id': target_event.data.user_id,
                    'name': 'NoBody',
                    'nickname': 'NoBody'
                }
            )
            if 'user_name' in target_event.sdk_event.json:
                target_event.data.sender['name'] = target_event.sdk_event.json['user_name']
                target_event.data.sender['nickname'] = target_event.sdk_event.json['user_name']
            pass
        elif 'detail_type' in target_event.sdk_event.json \
        and 'group' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message'
            target_event.data = target_event.group_message(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['user_id']),
                '',
                'group'
            )
            target_event.data.message_sdk = OlivOS.messageAPI.Message_templet(
                'obv12_para',
                target_event.sdk_event.json['message']
            )
            target_event.data.message = target_event.sdk_event.json['message']
            target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
            target_event.data.raw_message = target_event.data.message
            target_event.data.raw_message_sdk = target_event.data.message_sdk
            target_event.data.font = None
            target_event.data.sender.update(
                {
                    'id': target_event.data.user_id,
                    'user_id': target_event.data.user_id,
                    'name': 'NoBody',
                    'nickname': 'NoBody'
                }
            )
            if 'user_name' in target_event.sdk_event.json:
                target_event.data.sender['name'] = target_event.sdk_event.json['user_name']
                target_event.data.sender['nickname'] = target_event.sdk_event.json['user_name']
        elif 'detail_type' in target_event.sdk_event.json \
        and 'channel' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message'
            target_event.data = target_event.group_message(
                str(target_event.sdk_event.json['guild_id']),
                str(target_event.sdk_event.json['user_id']),
                '',
                'channel'
            )
            target_event.data.host_id = str(target_event.sdk_event.json['channel_id'])
            target_event.data.message_sdk = OlivOS.messageAPI.Message_templet(
                'obv12_para',
                target_event.sdk_event.json['message']
            )
            target_event.data.message = target_event.sdk_event.json['message']
            target_event.data.message_id = str(target_event.sdk_event.json['message_id'])
            target_event.data.raw_message = target_event.data.message
            target_event.data.raw_message_sdk = target_event.data.message_sdk
            target_event.data.font = None
            target_event.data.sender.update(
                {
                    'id': target_event.data.user_id,
                    'user_id': target_event.data.user_id,
                    'name': 'NoBody',
                    'nickname': 'NoBody'
                }
            )
            if 'user_name' in target_event.sdk_event.json:
                target_event.data.sender['name'] = target_event.sdk_event.json['user_name']
                target_event.data.sender['nickname'] = target_event.sdk_event.json['user_name']
    elif 'type' in target_event.sdk_event.json \
    and 'notice' == target_event.sdk_event.json['type']:
        if 'detail_type' in target_event.sdk_event.json \
        and 'friend_increase' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'friend_add'
            target_event.data = target_event.friend_add(
                str(target_event.sdk_event.json['user_id'])
            )
        elif 'detail_type' in target_event.sdk_event.json \
        and 'friend_decrease' == target_event.sdk_event.json['detail_type']:
            # 暂无该事件
            pass
        elif 'detail_type' in target_event.sdk_event.json \
        and 'private_message_delete' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message_recall'
            target_event.data = target_event.private_message_recall(
                str(target_event.sdk_event.json['user_id']),
                str(target_event.sdk_event.json['message_id'])
            )
        elif 'detail_type' in target_event.sdk_event.json \
        and 'group_member_increase' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_member_increase'
            target_event.data = target_event.group_member_increase(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['operator_id']),
                str(target_event.sdk_event.json['user_id'])
            )
            if target_event.sdk_event.json['sub_type'] == 'approve':
                target_event.data.action = 'approve'
            elif target_event.sdk_event.json['sub_type'] == 'join':
                target_event.data.action = 'approve'
            elif target_event.sdk_event.json['sub_type'] == 'invite':
                target_event.data.action = 'invite'
        elif 'detail_type' in target_event.sdk_event.json \
        and 'group_member_decrease' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_member_decrease'
            target_event.data = target_event.group_member_decrease(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['operator_id']),
                str(target_event.sdk_event.json['user_id'])
            )
            if target_event.sdk_event.json['sub_type'] == 'leave':
                target_event.data.action = 'leave'
            elif target_event.sdk_event.json['sub_type'] == 'kick':
                target_event.data.action = 'kick'
                if target_event.data.user_id == str(target_event.base_info['self_id']):
                    target_event.data.action = 'kick_me'
            elif target_event.sdk_event.json['sub_type'] == 'kick_me':
                target_event.data.action = 'kick_me'
        elif 'detail_type' in target_event.sdk_event.json \
        and 'group_message_delete' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message_recall'
            target_event.data = target_event.group_message_recall(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['operator_id']),
                str(target_event.sdk_event.json['user_id']),
                str(target_event.sdk_event.json['message_id'])
            )
        elif 'detail_type' in target_event.sdk_event.json \
        and 'group_admin_set' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_admin'
            target_event.data = target_event.group_admin(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['user_id'])
            )
            target_event.data.action = 'set'
        elif 'detail_type' in target_event.sdk_event.json \
        and 'group_admin_unset' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_admin'
            target_event.data = target_event.group_admin(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['user_id'])
            )
            target_event.data.action = 'unset'
        elif 'detail_type' in target_event.sdk_event.json \
        and 'group_member_ban' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_ban'
            target_event.data = target_event.group_ban(
                str(target_event.sdk_event.json['group_id']),
                str(target_event.sdk_event.json['operator_id']),
                str(target_event.sdk_event.json['user_id']),
                target_event.sdk_event.json['duration']
            )
            if 0 != target_event.sdk_event.json['duration']:
                target_event.data.action = 'ban'
            else:
                target_event.data.action = 'unban'
    elif 'type' in target_event.sdk_event.json \
    and 'request' == target_event.sdk_event.json['type']:
        if 'detail_type' in target_event.sdk_event.json \
        and 'new_friend' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'friend_add_request'
            target_event.data = target_event.friend_add_request(
                str(target_event.sdk_event.json['user_id']),
                target_event.sdk_event.json['message']
            )
            target_event.data.flag = str(target_event.sdk_event.json['request_id'])
            setReg(target_event.data.flag, target_event.data.user_id)
        elif 'detail_type' in target_event.sdk_event.json \
        and 'join_group' == target_event.sdk_event.json['detail_type']:
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_add_request'
                target_event.data = target_event.group_add_request(
                    str(target_event.sdk_event.json['group_id']),
                    str(target_event.sdk_event.json['user_id']),
                    target_event.sdk_event.json['message']
                )
                target_event.data.flag = str(target_event.sdk_event.json['request_id'])
                setReg(target_event.data.flag, target_event.data.group_id)
                setReg(target_event.data.flag + '-user', target_event.data.user_id)
        elif 'detail_type' in target_event.sdk_event.json \
        and ('group_invited' == target_event.sdk_event.json['detail_type'] \
        or 'group_invite' == target_event.sdk_event.json['detail_type']): # 这里是为了兼容 https://github.com/onebot-walle/walle-q/issues/37
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_invite_request'
                target_event.data = target_event.group_invite_request(
                    str(target_event.sdk_event.json['group_id']),
                    str(target_event.sdk_event.json['invitor_id']),
                    ''
                )
                target_event.data.flag = str(target_event.sdk_event.json['request_id'])
                setReg(target_event.data.flag, target_event.data.group_id)
                setReg(target_event.data.flag + '-user', target_event.data.user_id)
    elif 'type' in target_event.sdk_event.json \
    and 'meta' == target_event.sdk_event.json['type']:
        if 'detail_type' in target_event.sdk_event.json \
        and 'heartbeat' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'heartbeat'
            target_event.data = target_event.heartbeat(
                int(target_event.sdk_event.json['interval']) * 1000
            )
        elif 'detail_type' in target_event.sdk_event.json \
        and 'connect' == target_event.sdk_event.json['detail_type']:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'lifecycle'
            target_event.data = target_event.lifecycle()
            target_event.data.action = 'connect'


'''
对于WEBSOCKET接口的PAYLOAD实现
'''
class payload_template(object):
    def __init__(self, eventType:str, data:'str|None'=None, is_rx:bool=False):
        self.active = True
        self.data = self.data_T()
        self.load(eventType, data, is_rx)

    def __str__(self):
        res = {
            'active': self.active,
            'data': str(self.data)
        }
        return str(res)

    class data_T(object):
        def __init__(self):
            self.type = None
            self.data = None

        def __str__(self):
            return str(self.__dict__)

    def dump(self):
        res_obj = {}
        res_obj.update(self.data.data)
        res = json.dumps(obj=res_obj)
        return res

    def load(self, eventType, data, is_rx):
        if data is not None:
            if type(data) == dict:
                self.data.type = eventType
                self.data.data = data
            else:
                self.active = False
        else:
            self.active = False
        return self

class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, data:dict):
            payload_template.__init__(self, 'rxPacket', data, True)

    class txPacket(payload_template):
        def __init__(self, data:dict):
            payload_template.__init__(self, 'txPacket', data, False)


'''
对于WEBSOCKET接口的发送数据PAYLOAD实现
'''
class api_templet(object):
    def __init__(self, action:'str|None'=None, params=None, echo:'str|None'=None):
        self.action = action
        self.params = params
        self.echo = echo
        if self.echo is None:
            self.echo = str(uuid.uuid4())

    def do_api(self, bot_hash, control_queue):
        data = self.do_dump()
        send_ws_event(
            hash = bot_hash,
            data = data,
            control_queue = control_queue
        )

    def do_dump(self):
        res_obj = {
            'action': self.action,
            'params': {},
            'echo': self.echo
        }
        if self.params != None:
            for key_this in self.params.__dict__:
                if self.params.__dict__[key_this] is not None:
                    res_obj['params'][key_this] = self.params.__dict__[key_this]
        res = json.dumps(res_obj, ensure_ascii=False)
        return res


def sendControlEventSend(action, data, control_queue):
    if control_queue is not None:
        control_queue.put(
            OlivOS.API.Control.packet(
                action,
                data
            ),
            block=False
        )

def send_ws_event(hash, data, control_queue):
    sendControlEventSend(
        'send',
        {
            'target': {
                'type': 'onebotV12_link',
                'hash': hash
            },
            'data': {
                'action': 'send',
                'data': data
            }
        },
        control_queue
    )

class api(object):
    class send_message(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'send_message'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.detail_type = 'private'
                self.user_id = None
                self.group_id = None
                self.guild_id = None
                self.channel_id = None
                self.message = []

    class delete_message(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'delete_message'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.message_id = None

    class get_message(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_message'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.message_id = None

    class get_self_info(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_self_info'

    class get_user_info(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_user_info'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.user_id = None

    class get_friend_list(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_friend_list'

    class set_new_friend(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'set_new_friend'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.user_id = None
                self.request_id = None
                self.accept = None

    class delete_friend(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'delete_friend'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.user_id = None

    class get_new_friend_requests(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_new_friend_requests'

    class get_group_info(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_group_info'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None

    class get_group_list(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_group_list'

    class get_group_member_info(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_group_member_info'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None
                self.user_id = None

    class get_group_member_list(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_group_member_list'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None

    class set_group_name(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'set_group_name'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None
                self.group_name = None

    class leave_group(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'leave_group'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None

    class kick_group_member(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'kick_group_member'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None
                self.user_id = None

    class ban_group_member(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'ban_group_member'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None
                self.user_id = None
                self.duration = None

    class unban_group_member(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'unban_group_member'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None
                self.user_id = None

    class set_group_admin(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'set_group_admin'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None
                self.user_id = None

    class unset_group_admin(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'unset_group_admin'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.group_id = None
                self.user_id = None

    class set_join_group(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'set_join_group'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.request_id = None
                self.user_id = None
                self.group_id = None
                self.accept = None
                self.block = None
                self.message = None

    class get_join_group_requests(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_join_group_requests'

    class set_group_invited(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'set_group_invited'
            self.params = self.params_T()

        class params_T(object):
            def __init__(self):
                self.request_id = None
                self.group_id = None
                self.accept = None

    class get_group_inviteds(api_templet):
        def __init__(self):
            api_templet.__init__(self)
            self.action = 'get_group_inviteds'



# 支持OlivOS API调用的方法实现
class event_action(object):
    def send_private_msg(target_event:OlivOS.API.Event, user_id, message):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.send_message()
            this_msg.params.detail_type = 'private'
            this_msg.params.user_id = str(user_id)
            this_msg.params.message = message
            this_msg.do_api(bot_hash, control_queue)

    def send_group_msg(target_event:OlivOS.API.Event, group_id, message):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.send_message()
            this_msg.params.detail_type = 'group'
            this_msg.params.group_id = str(group_id)
            this_msg.params.message = message
            this_msg.do_api(bot_hash, control_queue)

    def send_host_msg(target_event:OlivOS.API.Event, host_id, group_id, message):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.send_message()
            this_msg.params.detail_type = 'channel'
            this_msg.params.channel_id = str(host_id)
            this_msg.params.guild_id = str(group_id)
            this_msg.params.message = message
            this_msg.do_api(bot_hash, control_queue)

    def delete_msg(target_event, message_id):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.delete_message()
            this_msg.params.message_id = str(message_id)
            this_msg.do_api(bot_hash, control_queue)

    def set_group_kick(target_event, group_id, user_id):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.kick_group_member()
            this_msg.params.group_id = str(group_id)
            this_msg.params.user_id = str(user_id)
            this_msg.do_api(bot_hash, control_queue)

    def set_group_leave(target_event, group_id):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.leave_group()
            this_msg.params.group_id = str(group_id)
            this_msg.do_api(bot_hash, control_queue)

    def set_group_name(target_event, group_id, group_name):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.set_group_name()
            this_msg.params.group_id = str(group_id)
            this_msg.params.group_name = str(group_name)
            this_msg.do_api(bot_hash, control_queue)

    def set_group_ban(target_event, group_id, user_id, duration=1800):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            if 0 == duration:
                this_msg = api.ban_group_member()
                this_msg.params.group_id = str(group_id)
                this_msg.params.user_id = str(user_id)
                this_msg.params.duration = str(duration)
                this_msg.do_api(bot_hash, control_queue)
            else:
                this_msg = api.unban_group_member()
                this_msg.params.group_id = str(group_id)
                this_msg.params.user_id = str(user_id)
                this_msg.do_api(bot_hash, control_queue)

    def set_group_admin(target_event, group_id, user_id, enable):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            if True is enable:
                this_msg = api.set_group_admin()
                this_msg.params.group_id = str(group_id)
                this_msg.params.user_id = str(user_id)
                this_msg.do_api(bot_hash, control_queue)
            else:
                this_msg = api.unset_group_admin()
                this_msg.params.group_id = str(group_id)
                this_msg.params.user_id = str(user_id)
                this_msg.do_api(bot_hash, control_queue)

    def get_login_info(target_event:OlivOS.API.Event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_info()
        raw_obj = None
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.get_self_info()
            waitForResReady(this_msg.echo)
            this_msg.do_api(bot_hash, control_queue)
            res_raw = waitForRes(this_msg.echo)
            raw_obj = init_api_json(res_raw)
        if raw_obj is not None:
            if type(raw_obj) is dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['user_name'], str)
                res_data['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['user_id'], str)
        return res_data

    def get_stranger_info(target_event:OlivOS.API.Event, user_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_stranger_info()
        raw_obj = None
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.get_user_info()
            this_msg.params.user_id = str(user_id)
            waitForResReady(this_msg.echo)
            this_msg.do_api(bot_hash, control_queue)
            res_raw = waitForRes(this_msg.echo)
            raw_obj = init_api_json(res_raw)
        if raw_obj is not None:
            if type(raw_obj) is dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['user_name'], str)
                res_data['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['user_id'], str)
        return res_data

    def get_friend_list(target_event:OlivOS.API.Event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_friend_list()
        raw_obj = None
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.get_friend_list()
            waitForResReady(this_msg.echo)
            this_msg.do_api(bot_hash, control_queue)
            res_raw = waitForRes(this_msg.echo)
            raw_obj = init_api_json(res_raw)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_user_info_strip()
                    tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['user_name'], str)
                    tmp_res_data_this['id'] = init_api_do_mapping_for_dict(raw_obj_this, ['user_id'], str)
                    res_data['data'].append(tmp_res_data_this)
        return res_data

    def get_group_info(target_event:OlivOS.API.Event, group_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_info()
        raw_obj = None
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.get_group_info()
            this_msg.params.group_id = str(group_id)
            waitForResReady(this_msg.echo)
            this_msg.do_api(bot_hash, control_queue)
            res_raw = waitForRes(this_msg.echo)
            raw_obj = init_api_json(res_raw)
        if raw_obj is not None:
            if type(raw_obj) is dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['group_name'], str)
                res_data['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['group_id'], str)
                res_data['data']['memo'] = ''
                res_data['data']['member_count'] = 0
                res_data['data']['max_member_count'] = 0
        return res_data

    def get_group_list(target_event:OlivOS.API.Event):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_list()
        raw_obj = None
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.get_group_list()
            waitForResReady(this_msg.echo)
            this_msg.do_api(bot_hash, control_queue)
            res_raw = waitForRes(this_msg.echo)
            raw_obj = init_api_json(res_raw)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_user_info_strip()
                    tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['group_name'], str)
                    tmp_res_data_this['id'] = init_api_do_mapping_for_dict(raw_obj_this, ['group_id'], str)
                    tmp_res_data_this['memo'] = ''
                    tmp_res_data_this['member_count'] = 0
                    tmp_res_data_this['max_member_count'] = 0
                    res_data['data'].append(tmp_res_data_this)
        return res_data

    def get_group_member_info(target_event:OlivOS.API.Event, group_id, user_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_info()
        raw_obj = None
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.get_group_member_info()
            this_msg.params.group_id = str(group_id)
            this_msg.params.user_id = str(user_id)
            waitForResReady(this_msg.echo)
            this_msg.do_api(bot_hash, control_queue)
            res_raw = waitForRes(this_msg.echo)
            raw_obj = init_api_json(res_raw)
        if raw_obj is not None:
            if type(raw_obj) is dict:
                res_data['active'] = True
                res_data['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['user_name'], str)
                res_data['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['user_id'], str)
                res_data['data']['user_id'] = init_api_do_mapping_for_dict(raw_obj, ['user_id'], str)
                res_data['data']['group_id'] = this_msg.params.group_id
                res_data['data']['times']['join_time'] = 0
                res_data['data']['times']['last_sent_time'] = 0
                res_data['data']['times']['shut_up_timestamp'] = 0
                res_data['data']['role'] = 'member'
                res_data['data']['card'] = init_api_do_mapping_for_dict(raw_obj, ['user_remark'], str)
                res_data['data']['title'] = init_api_do_mapping_for_dict(raw_obj, ['user_displayname'], str)
        return res_data

    def get_group_member_list(target_event:OlivOS.API.Event, group_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_list()
        raw_obj = None
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.get_group_member_list()
            this_msg.params.group_id = str(group_id)
            waitForResReady(this_msg.echo)
            this_msg.do_api(bot_hash, control_queue)
            res_raw = waitForRes(this_msg.echo)
            raw_obj = init_api_json(res_raw)
        if raw_obj is not None:
            if type(raw_obj) == list:
                res_data['active'] = True
                for raw_obj_this in raw_obj:
                    tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_user_info_strip()
                    tmp_res_data_this['data']['name'] = init_api_do_mapping_for_dict(raw_obj, ['user_name'], str)
                    tmp_res_data_this['data']['id'] = init_api_do_mapping_for_dict(raw_obj, ['user_id'], str)
                    tmp_res_data_this['data']['user_id'] = init_api_do_mapping_for_dict(raw_obj, ['user_id'], str)
                    tmp_res_data_this['data']['group_id'] = this_msg.params.group_id
                    tmp_res_data_this['data']['times']['join_time'] = 0
                    tmp_res_data_this['data']['times']['last_sent_time'] = 0
                    tmp_res_data_this['data']['times']['shut_up_timestamp'] = 0
                    tmp_res_data_this['data']['role'] = 'member'
                    tmp_res_data_this['data']['card'] = init_api_do_mapping_for_dict(raw_obj, ['user_remark'], str)
                    tmp_res_data_this['data']['title'] = init_api_do_mapping_for_dict(raw_obj, ['user_displayname'], str)
                    res_data['data'].append(tmp_res_data_this)
        return res_data

    def set_friend_add_request(target_event, flag, approve:bool, remark):
        global gTmpReg
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            this_msg = api.set_new_friend()
            this_msg.params.request_id = int(flag)
            this_msg.params.user_id = getReg(flag)
            this_msg.params.accept = approve
            this_msg.do_api(bot_hash, control_queue)

    def set_group_add_request(target_event, flag, sub_type, approve, reason):
        if target_event.bot_info != None:
            bot_hash = target_event.bot_info.hash
            control_queue = target_event.plugin_info['control_queue']
            if 'add' == sub_type:
                this_msg = api.set_join_group()
                this_msg.params.request_id = int(flag)
                this_msg.params.group_id = getReg(flag)
                this_msg.params.user_id = getReg(flag + '-user')
                this_msg.params.accept = approve
                this_msg.params.message = reason
                this_msg.do_api(bot_hash, control_queue)
            elif 'invite' == sub_type:
                this_msg = api.set_group_invited()
                this_msg.params.request_id = int(flag)
                this_msg.params.group_id = getReg(flag)
                this_msg.params.accept = approve
                this_msg.do_api(bot_hash, control_queue)


def init_api_json(raw:dict):
    res_data = None
    flag_is_active = False
    tmp_obj = raw
    if type(tmp_obj) is dict \
    and 'retcode' in tmp_obj \
    and type(tmp_obj['retcode']) is int \
    and tmp_obj['retcode'] == 0:
        flag_is_active = True
    if flag_is_active \
    and 'data' in tmp_obj:
        if type(tmp_obj['data']) is dict:
            res_data = copy.deepcopy(tmp_obj['data'])
        elif type(tmp_obj['data']) is list:
            res_data = copy.deepcopy(tmp_obj['data'])
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

def getReg(flag:str):
    global gTmpReg
    res = None
    if flag in gTmpReg:
        res = gTmpReg[flag]
    return res

def setReg(flag:str, value):
    global gTmpReg
    gTmpReg[flag] = value

def setUserReg(botHash:str, regType:str, flag:str, value:str):
    global gUsrReg
    gUsrReg.setdefault(botHash, {})
    gUsrReg[botHash].setdefault(regType, {})
    gUsrReg[botHash][regType][flag] = value

def getUserReg(botHash:str, regType:str, flag:str):
    global gUsrReg
    res = None
    if botHash in gUsrReg \
    and regType in gUsrReg[botHash] \
    and flag in gUsrReg[botHash][regType]:
        res = gUsrReg[botHash][regType][flag]
    return res

def waitForResSet(echo:str, data):
    global gResReg
    if echo in gResReg:
        gResReg[echo] = data

def waitForResReady(echo:str):
    global gResReg
    gResReg[echo] = None

def waitForRes(echo:str):
    global gResReg
    res = None
    interval = 0.1
    limit = 30
    index_limit = int(limit / interval)
    for i in range(index_limit):
        time.sleep(interval)
        if echo in gResReg \
        and gResReg[echo] is not None:
            res = gResReg[echo]
            gResReg.pop(echo)
            break
    return res
