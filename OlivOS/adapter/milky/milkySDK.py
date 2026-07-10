r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/milkySDK.py
@Author    :   RemiliaCat
@Contact   :   RemiliaNero@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

import OlivOS

import os
import time
import uuid
import threading
from . import milkyType
from dataclasses import dataclass
import inspect
from functools import wraps
from urllib import parse
from pathlib import Path
from typing import TypeAlias

"""

# `message_seq` 与 `message_id` （来自Milky官方）

> 省流：message_scene + peer_id + message_seq = 完整版 message_id。
>
> message_seq 不是“大号的 message_id”，而是一个自增的数字，表示消息在当前会话中的顺序，对于每个会话（好友或群聊）都是独立的。
> Milky 用 message_scene、peer_id 和 message_seq 组合来唯一标识一条消息。其中：
>
> - message_scene 是一个字符串，表示消息的场景（例如：好友、群聊等）
> - peer_id 是一个数字，表示会话的 ID。对于好友消息，peer_id 是好友的 QQ 号；对于群消息，peer_id 是群号。
>
> OneBot 11 则使用 message_id 来唯一标识一条消息。

"""

"""

# 各种请求标识 `flag`

> 本SDK将flag定义为各个参数的简单拼装，并尽量确保其全局唯一性
> 在不同场景下，flag也有所区别
>
> - 对于好友添加请求：flag = is_filtered + initiator_uid
> - 对于群添加请求：
>   * 他人加群：flag = notification_type + group_id + is_filtered + notification_seq
>   * 自身受邀：flag = group_id + invitation_seq
>
> 对于`OlivOS`插件接口`get_group_ignore_add_request`的返回值字段`request_id`即对应他人加群

"""


# 使用OlivOS定义的类型

RES: TypeAlias = OlivOS.contentAPI.api_result_data_template.universal_result
MSG: TypeAlias = OlivOS.messageAPI.Message_templet | list[dict]
ID: TypeAlias = str | int
USER: TypeAlias = dict
GROUP: TypeAlias = dict
GROUP_USER: TypeAlias = dict


# 全局变量区
gResReg = {}    # 响应寄存器
gEveReg = {}    # 线程唤醒事件寄存器


class bot_info_T(object):
    def __init__(self, id=-1, host='', port=-1, access_token=None):
        self.id = id
        self.host = host
        self.port = port
        self.access_token = access_token
        self.debug_mode = False
        self.debug_logger = None


def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info: OlivOS.API.bot_info_T):
    res = bot_info_T(
        id=plugin_bot_info.id,
        host=plugin_bot_info.post_info.host,
        port=plugin_bot_info.post_info.port,
        access_token=plugin_bot_info.post_info.access_token
    )
    res.hash = plugin_bot_info.hash
    res.server_type = plugin_bot_info.post_info.type
    res.platform = plugin_bot_info.platform['platform']
    res.debug_mode = plugin_bot_info.debug_mode
    return res


def get_SDK_bot_info_from_Event(target_event: OlivOS.API.Event):
    return get_SDK_bot_info_from_Plugin_bot_info(target_event.bot_info)


def get_Event_from_SDK(target_event: OlivOS.API.Event):
    target_event.base_info['time'] = target_event.sdk_event.base_info.get('time', int(time.time()))
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info.get('self_id', '-1'))
    target_event.base_info['type'] = str(target_event.sdk_event.base_info.get('type', 'None'))
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'milky_para_tx'

    if target_event.base_info['type'] == 'response':
        target_event.active = False
        post_id = target_event.sdk_event.json.get('post_id')
        if (
            target_event.sdk_event.json['retcode'] == 0
            or target_event.sdk_event.json['status'] == 'ok'
        ):
            set_for_res(
                post_id,
                target_event.sdk_event.json
            )
        else:
            # 当post不成功时，响应retcode不为0，此时释放响应锁gResReg[post_id]
            set_for_res(post_id, None)
    elif target_event.base_info['type'] == 'bot_offline':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'lifecycle'
        target_event.data = target_event.lifecycle(action='disable')

    elif target_event.base_info['type'] == 'message_receive':
        target_event.active = True
        if target_event.sdk_event.json['data']['message_scene'] == 'friend':
            if target_event.base_info['self_id'] == str(target_event.sdk_event.json['data']['sender_id']):
                target_event.plugin_info['func_type'] = 'private_message_sent'
            else:
                target_event.plugin_info['func_type'] = 'private_message'
            new_msg = target_event.sdk_event.json['data']['segments']
            target_event.data = target_event.private_message(
                str(target_event.sdk_event.json['data']['sender_id']),
                new_msg,
                'friend'
            )
            target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('milky_para_rx', new_msg)
            target_event.data.message_id = msgID(
                target_event.sdk_event.json['data']['message_scene'],
                target_event.sdk_event.json['data']['peer_id'],
                target_event.sdk_event.json['data']['message_seq']
            )
            target_event.data.raw_message = new_msg
            target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('milky_para_rx', new_msg)
            target_event.data.sender.update(target_event.sdk_event.json['data']['friend'])
            if 'sender_id' in target_event.sdk_event.json['data']:
                target_event.data.sender['id'] = str(target_event.sdk_event.json['data']['sender_id'])
            if 'nickname' in target_event.sdk_event.json['data']['friend']:
                target_event.data.sender['name'] = target_event.sdk_event.json['data']['friend']['nickname']
        elif target_event.sdk_event.json['data']['message_scene'] == 'group':
            if target_event.base_info['self_id'] == str(target_event.sdk_event.json['data']['sender_id']):
                target_event.plugin_info['func_type'] = 'group_message_sent'
            else:
                target_event.plugin_info['func_type'] = 'group_message'
            new_msg = target_event.sdk_event.json['data']['segments']
            target_event.data = target_event.group_message(
                str(target_event.sdk_event.json['data']['peer_id']),
                str(target_event.sdk_event.json['data']['sender_id']),
                new_msg,
                'group'
            )
            target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('milky_para_rx', new_msg)
            target_event.data.message_id = msgID(
                target_event.sdk_event.json['data']['message_scene'],
                target_event.sdk_event.json['data']['peer_id'],
                target_event.sdk_event.json['data']['message_seq']
            )
            target_event.data.raw_message = new_msg
            target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('milky_para_rx', new_msg)
            target_event.data.sender.update(target_event.sdk_event.json['data']['group_member'])
            if 'sender_id' in target_event.sdk_event.json['data']:
                target_event.data.sender['id'] = str(target_event.sdk_event.json['data']['sender_id'])
            if 'nickname' in target_event.sdk_event.json['data']['group_member']:
                target_event.data.sender['name'] = target_event.sdk_event.json['data']['group_member']['nickname']
        elif target_event.sdk_event.json['data']['message_scene'] == 'temp':
            if target_event.base_info['self_id'] == str(target_event.sdk_event.json['data']['sender_id']):
                target_event.plugin_info['func_type'] = 'private_message_sent'
            else:
                target_event.plugin_info['func_type'] = 'private_message'
            new_msg = target_event.sdk_event.json['data']['segments']
            target_event.data = target_event.private_message(
                str(target_event.sdk_event.json['data']['sender_id']),
                new_msg,
                'temp'
            )
            target_event.data.message_sdk = OlivOS.messageAPI.Message_templet('milky_para_rx', new_msg)
            target_event.data.message_id = msgID(
                target_event.sdk_event.json['data']['message_scene'],
                target_event.sdk_event.json['data']['peer_id'],
                target_event.sdk_event.json['data']['message_seq']
            )
            target_event.data.raw_message = new_msg
            target_event.data.raw_message_sdk = OlivOS.messageAPI.Message_templet('milky_para_rx', new_msg)
            target_event.data.sender.update(target_event.sdk_event.json['data']['group_member'])
            if 'sender_id' in target_event.sdk_event.json['data']:
                target_event.data.sender['id'] = str(target_event.sdk_event.json['data']['sender_id'])
            target_event.data.sender['name'] = 'temp'
    elif target_event.base_info['type'] == 'message_recall':
        target_event.active = True
        if target_event.sdk_event.json['data']['message_scene'] == 'friend':
            target_event.plugin_info['func_type'] = 'private_message_recall'
            target_event.data = target_event.private_message_recall(
                str(target_event.sdk_event.json['data']['operator_id']),
                msgID(
                    target_event.sdk_event.json['data']['message_scene'],
                    target_event.sdk_event.json['data']['peer_id'],
                    target_event.sdk_event.json['data']['message_seq']
                )
            )
        elif target_event.sdk_event.json['data']['message_scene'] == 'group':
            target_event.plugin_info['func_type'] = 'group_message_recall'
            target_event.data = target_event.group_message_recall(
                str(target_event.sdk_event.json['data']['peer_id']),
                str(target_event.sdk_event.json['data']['operator_id']),
                str(target_event.sdk_event.json['data']['sender_id']),
                msgID(
                    target_event.sdk_event.json['data']['message_scene'],
                    target_event.sdk_event.json['data']['peer_id'],
                    target_event.sdk_event.json['data']['message_seq']
                )
            )
        elif target_event.sdk_event.json['data']['message_scene'] == 'temp':
            target_event.plugin_info['func_type'] = 'private_message_recall'
            target_event.data = target_event.private_message_recall(
                str(target_event.sdk_event.json['data']['operator_id']),
                msgID(
                    target_event.sdk_event.json['data']['message_scene'],
                    target_event.sdk_event.json['data']['peer_id'],
                    target_event.sdk_event.json['data']['message_seq']
                )
            )
    elif target_event.base_info['type'] == 'peer_pin_change':
        target_event.active = False
        pass
    elif target_event.base_info['type'] == 'friend_request':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'friend_add_request'
        initiator_id = str(target_event.sdk_event.json['data']['initiator_id'])
        comment = target_event.sdk_event.json['data'].get('comment', '')
        target_event.data = target_event.friend_add_request(
            user_id=initiator_id,
            comment=comment
        )
        target_event.data.flag = f"False|{target_event.sdk_event.json['data']['initiator_uid']}"
    elif target_event.base_info['type'] == 'group_join_request':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_add_request'
        group_id = str(target_event.sdk_event.json['data']['group_id'])
        initiator_id = str(target_event.sdk_event.json['data']['initiator_id'])
        notification_seq = int(target_event.sdk_event.json['data']['notification_seq'])
        comment = target_event.sdk_event.json['data'].get('comment', '')
        target_event.data = target_event.group_add_request(
            group_id=group_id,
            user_id=initiator_id,
            comment=comment
        )
        target_event.data.flag = f'join_request|{group_id}|False|{notification_seq}'
    elif target_event.base_info['type'] == 'group_invited_join_request':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_add_request'
        group_id = str(target_event.sdk_event.json['data']['group_id'])
        initiator_id = str(target_event.sdk_event.json['data']['initiator_id'])
        notification_seq = int(target_event.sdk_event.json['data']['notification_seq'])
        comment = target_event.sdk_event.json['data'].get('comment', '')
        target_event.data = target_event.group_add_request(
            group_id=group_id,
            user_id=initiator_id,
            comment=comment
        )
        target_event.data.flag = f'invited_join_request|{group_id}|False|{notification_seq}'
    elif target_event.base_info['type'] == 'group_invitation':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_invite_request'
        group_id = str(target_event.sdk_event.json['data']['group_id'])
        initiator_id = str(target_event.sdk_event.json['data']['initiator_id'])
        invitation_seq = int(target_event.sdk_event.json['data']['invitation_seq'])
        comment = target_event.sdk_event.json['data'].get('comment', '')
        target_event.data = target_event.group_invite_request(
            group_id=group_id,
            user_id=initiator_id,
            comment=comment
        )
        target_event.data.flag = f'{group_id}|{invitation_seq}'
    elif target_event.base_info['type'] == 'friend_nudge':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'poke'
        is_self_send = target_event.sdk_event.json['data']['is_self_send']
        is_self_receive = target_event.sdk_event.json['data']['is_self_receive']
        if is_self_send:
            sender_id = str(target_event.base_info['self_id'])
        else:
            sender_id = str(target_event.sdk_event.json['data']['user_id'])
        if is_self_receive:
            receiver_id = str(target_event.base_info['self_id'])
        else:
            receiver_id = str(target_event.sdk_event.json['data']['user_id'])
        target_event.data = target_event.poke(
            user_id=sender_id,
            target_id=receiver_id,
        )
    elif target_event.base_info['type'] == 'friend_file_upload':
        target_event.active = False
        pass
    elif target_event.base_info['type'] == 'group_admin_change':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_admin'
        target_event.data = target_event.group_admin(
            str(target_event.sdk_event.json['data']['group_id']),
            str(target_event.sdk_event.json['data']['user_id'])
        )
        if target_event.sdk_event.json['data']['is_set']:
            target_event.data.action = 'set'
    elif target_event.base_info['type'] == 'group_essence_message_change':
        target_event.active = False
        pass
    elif target_event.base_info['type'] == 'group_member_increase':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_member_increase'
        operator_id = -1
        action = 'approve'
        if 'operator_id' in target_event.sdk_event.json['data']:
            operator_id = str(target_event.sdk_event.json['data']['operator_id'])
            action = 'approve'
        elif 'invitor_id' in target_event.sdk_event.json['data']:
            operator_id = str(target_event.sdk_event.json['data']['invitor_id'])
            action = 'invite'
        target_event.data = target_event.group_member_increase(
            group_id=str(target_event.sdk_event.json['data']['group_id']),
            operator_id=operator_id,
            user_id=str(target_event.sdk_event.json['data']['user_id']),
            action=action
        )
    elif target_event.base_info['type'] == 'group_member_decrease':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_member_decrease'
        operator_id = -1
        action = 'leave'
        if 'operator_id' in target_event.sdk_event.json['data']:
            operator_id = str(target_event.sdk_event.json['data']['operator_id'])
            if target_event.base_info['self_id'] == str(target_event.sdk_event.json['data']['user_id']):
                action = 'kick_me'
            else:
                action = 'kick'
        target_event.data = target_event.group_member_decrease(
            group_id=str(target_event.sdk_event.json['data']['group_id']),
            operator_id=operator_id,
            user_id=str(target_event.sdk_event.json['data']['user_id']),
            action=action
        )
    elif target_event.base_info['type'] == 'group_name_change':
        target_event.active = False
        pass
    elif target_event.base_info['type'] == 'group_message_reaction':
        target_event.active = False
        pass
    elif target_event.base_info['type'] == 'group_mute':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_ban'
        duration = target_event.sdk_event.json['data']['duration']
        action = 'unban'
        if duration != 0:
            action = 'ban'
        target_event.data = target_event.group_ban(
            str(target_event.sdk_event.json['data']['group_id']),
            str(target_event.sdk_event.json['data']['operator_id']),
            str(target_event.sdk_event.json['data']['user_id']),
            duration=duration,
            action=action
        )
    elif target_event.base_info['type'] == 'group_whole_mute':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_ban'
        duration = target_event.sdk_event.json['data']['duration']
        action = 'unban'
        if duration != 0:
            action = 'ban'
        target_event.data = target_event.group_ban(
            str(target_event.sdk_event.json['data']['group_id']),
            str(target_event.sdk_event.json['data']['operator_id']),
            user_id=0,
            duration=duration,
            action=action
        )
    elif target_event.base_info['type'] == 'group_nudge':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'poke'
        target_event.data = target_event.poke(
            str(target_event.sdk_event.json['data']['sender_id']),
            str(target_event.sdk_event.json['data']['receiver_id']),
            str(target_event.sdk_event.json['data']['group_id'])
        )
    elif target_event.base_info['type'] == 'group_file_upload':
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_file_upload'
        target_event.data = target_event.group_file_upload(
            str(target_event.sdk_event.json['data']['group_id']),
            str(target_event.sdk_event.json['data']['user_id']),
        )
        file_obj = {
            'id': target_event.sdk_event.json['data']['file_id'],
            'name': target_event.sdk_event.json['data']['file_name'],
            'size': target_event.sdk_event.json['data']['file_size'],
        }
        target_event.data.file.update(file_obj)


def send_event(action, data, control_queue) -> None:
    if control_queue is not None:
        control_queue.put(
            OlivOS.API.Control.packet(
                action,
                data
            ),
            block=False
        )


def send_ws_event(hash, data, control_queue) -> None:
    send_event(
        'send',
        {
            'target' : {
                'type': 'milky_auto',
                'hash': hash
            },
            'data': {
                'action': 'send',
                'data': data
            }
        },
        control_queue
    )


def send_post_event(hash, data, control_queue) -> None:
    send_event(
        'send',
        {
            'target' : {
                'type': 'milky_auto',
                'hash': hash
            },
            'data': {
                'action': 'send',
                'data': data
            }
        },
        control_queue
    )


@dataclass
class API_template:
    def call(self, bot_hash, control_queue) -> dict:
        try:
            post_id = self.post_id
            data = self.gen_data(post_id)
            ready_for_res(post_id)
            send_post_event(
                hash=bot_hash,
                data=data,
                control_queue=control_queue
            )
            return wait_for_res(post_id)
        except Exception:
            return None

    def gen_data(self, post_id: str) -> dict:
        res = {
            'action': self.action,
            'params': {},
            'post_id': post_id
        }
        for k_cur, v_cur in self.__dict__.items():
            if v_cur is not None:
                res['params'][k_cur] = v_cur
        return res

    @property
    def action(self):
        return self.__class__.__name__

    @property
    def post_id(self):
        return str(uuid.uuid4())


class API(object):
    """Milky API类，包含所有API的定义

    默认值设为None的参数对应API文档中的可选参数，其他含默认值的参数对应API文档中含默认值的必填参数
    """

    # ----------系统API----------

    @dataclass
    class get_login_info(API_template):
        pass

    @dataclass
    class get_impl_info(API_template):
        pass

    @dataclass
    class get_user_profile(API_template):
        user_id: int

    @dataclass
    class get_friend_list(API_template):
        no_cache: bool = False

    @dataclass
    class get_friend_info(API_template):
        user_id: int
        no_cache: bool = False

    @dataclass
    class get_group_list(API_template):
        no_cache: bool = False

    @dataclass
    class get_group_info(API_template):
        group_id: int
        no_cache: bool = False

    @dataclass
    class get_group_member_list(API_template):
        group_id: int
        no_cache: bool = False

    @dataclass
    class get_group_member_info(API_template):
        group_id: int
        user_id: int
        no_cache: bool = False

    @dataclass
    class get_peer_pins(API_template):
        pass

    @dataclass
    class set_peer_pin(API_template):
        message_scene: str
        peer_id: int
        is_pinned: bool = True

    @dataclass
    class set_avatar(API_template):
        uri: str

    @dataclass
    class set_nickname(API_template):
        new_nickname: str

    @dataclass
    class set_bio(API_template):
        new_bio: str

    @dataclass
    class get_custom_face_url_list(API_template):
        urls: list[str]

    @dataclass
    class get_cookies(API_template):
        domain: str

    @dataclass
    class get_csrf_token(API_template):
        pass

    # ----------消息API----------

    @dataclass
    class send_private_message(API_template):
        user_id: int
        message: str

    @dataclass
    class send_group_message(API_template):
        group_id: int
        message: dict

    @dataclass
    class recall_private_message(API_template):
        user_id: int
        message_seq: int

    @dataclass
    class recall_group_message(API_template):
        group_id: int
        message_seq: int

    @dataclass
    class get_message(API_template):
        message_scene: str
        peer_id: int
        message_seq: int

    @dataclass
    class get_history_messages(API_template):
        message_scene: str
        peer_id: int
        start_message_seq: int = None
        limit: int = 20

    @dataclass
    class get_resource_temp_url(API_template):
        resource_id: str

    @dataclass
    class get_forwarded_messages(API_template):
        forward_id: str

    @dataclass
    class mark_message_as_read(API_template):
        message_scene: str
        peer_id: int
        message_seq: int

    # ----------好友API----------

    @dataclass
    class send_friend_nudge(API_template):
        user_id: int
        is_self: bool = False

    @dataclass
    class send_profile_like(API_template):
        user_id: int
        count: int = 1

    @dataclass
    class delete_friend(API_template):
        user_id: int

    @dataclass
    class get_friend_requests(API_template):
        limit: int = 20
        is_filtered: bool = False

    @dataclass
    class accept_friend_request(API_template):
        initiator_uid: str
        is_filtered: bool = False

    @dataclass
    class reject_friend_request(API_template):
        initiator_uid: str
        is_filtered: bool = False
        reason: str = None

    # ----------群聊API----------

    @dataclass
    class set_group_name(API_template):
        group_id: int
        new_group_name: str

    @dataclass
    class set_group_avatar(API_template):
        group_id: int
        image_uri: str

    @dataclass
    class set_group_member_card(API_template):
        group_id: int
        user_id: int
        card: str

    @dataclass
    class set_group_member_special_title(API_template):
        group_id: int
        user_id: int
        special_title: str

    @dataclass
    class set_group_member_admin(API_template):
        group_id: int
        user_id: int
        is_set: bool = True

    @dataclass
    class set_group_member_mute(API_template):
        group_id: int
        user_id: int
        duration: int

    @dataclass
    class set_group_whole_mute(API_template):
        group_id: int
        is_muted: bool = True

    @dataclass
    class kick_group_member(API_template):
        group_id: int
        user_id: int
        reject_add_request: bool = False

    @dataclass
    class get_group_announcements(API_template):
        group_id: int

    @dataclass
    class send_group_announcement(API_template):
        group_id: int
        content: str
        image_uri: str = None

    @dataclass
    class delete_group_announcement(API_template):
        group_id: int
        announcement_id: str

    @dataclass
    class get_group_essence_messages(API_template):
        group_id: int
        page_index: int
        page_size: int

    @dataclass
    class set_group_essence_message(API_template):
        group_id: int
        message_seq: int
        is_set: bool = True

    @dataclass
    class quit_group(API_template):
        group_id: int

    @dataclass
    class send_group_message_reaction(API_template):
        group_id: int
        message_seq: int
        reaction: str
        reaction_type: str
        is_add: bool = True

    @dataclass
    class send_group_nudge(API_template):
        group_id: int
        user_id: int

    @dataclass
    class get_group_notifications(API_template):
        start_notification_seq: int = None
        is_filtered: bool = False
        limit: int = 20

    @dataclass
    class accept_group_request(API_template):
        notification_seq: int
        notification_type: str
        group_id: int
        is_filtered: bool = False

    @dataclass
    class reject_group_request(API_template):
        notification_seq: int
        notification_type: str
        group_id: int
        is_filtered: bool = False
        reason: str = None

    @dataclass
    class accept_group_invitation(API_template):
        group_id: int
        invitation_seq: int

    @dataclass
    class reject_group_invitation(API_template):
        group_id: int
        invitation_seq: int

    # ----------文件API----------

    @dataclass
    class upload_private_file(API_template):
        user_id: int
        file_uri: str
        file_name: str

    @dataclass
    class upload_group_file(API_template):
        group_id: int
        file_uri: str
        file_name: str
        parent_folder_id: str = '/'

    @dataclass
    class get_private_file_download_url(API_template):
        user_id: int
        file_id: str
        file_hash: str

    @dataclass
    class get_group_file_download_url(API_template):
        group_id: int
        file_id: str

    @dataclass
    class get_group_files(API_template):
        group_id: int
        parent_folder_id: str = '/'

    @dataclass
    class move_group_file(API_template):
        group_id: int
        file_id: str
        parent_folder_id: str = '/'
        target_folder_id: str = '/'

    @dataclass
    class rename_group_file(API_template):
        group_id: int
        file_id: str
        new_file_name: str
        parent_folder_id: str = '/'

    @dataclass
    class delete_group_file(API_template):
        group_id: int
        file_id: str

    @dataclass
    class create_group_folder(API_template):
        group_id: int
        folder_name: str

    @dataclass
    class rename_group_folder(API_template):
        group_id: int
        folder_id: str
        new_folder_name: str

    @dataclass
    class delete_group_folder(API_template):
        group_id: int
        folder_id: str


def MilkyMessage(param_name: str):
    def decorator(func):
        sig = inspect.signature(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            if param_name in bound_args.arguments:
                target_value = bound_args.arguments[param_name]
                if isinstance(target_value, list):
                    target_value = combine_forward_nodes(target_value)
                    target_value = URI_format(target_value)
                    bound_args.arguments[param_name] = target_value
            return func(*bound_args.args, **bound_args.kwargs)
        return wrapper
    return decorator


class event(object):
    def __init__(self, raw):
        self.raw = raw
        self.json = self.event_load(raw)
        self.platform = {'sdk': 'milky', 'platform': 'qq', 'model': 'default'}
        self.base_info = {}
        self.active = False
        if self.json is not None:
            self.active = True
        if self.active:
            if 'retcode' not in self.json:
                self.base_info['time'] = self.json['time']
                self.base_info['self_id'] = str(self.json['self_id'])
                self.base_info['type'] = self.json['event_type']
            else:
                self.base_info['type'] = 'response'

    def event_load(self, raw):
        if raw is None:
            return None
        if not isinstance(raw, (dict, list)):
            return None
        return raw


class event_action(object):
    """支持OlivOS API调用的方法实现"""

    @staticmethod
    @MilkyMessage('message')
    def send_private_msg(target_event: OlivOS.API.Event, user_id: ID, message: MSG) -> None:
        if not isinstance(message, (list, dict)):
            return
        user_id = int(user_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.send_private_message(
            user_id=user_id,
            message=message,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    @MilkyMessage('message')
    def send_group_msg(target_event: OlivOS.API.Event, group_id: ID, message: MSG) -> None:
        if not isinstance(message, (list, dict)):
            return
        group_id = int(group_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.send_group_message(
            group_id=group_id,
            message=message,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def delete_msg(target_event: OlivOS.API.Event, message_id: ID) -> None:
        scene, peer_id, seq = message_id.split('|')
        peer_id = int(peer_id)
        seq = int(seq)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = None
        if scene == 'friend':
            Action = API.recall_private_message(
                user_id=peer_id,
                message_seq=seq,
            )
        elif scene == 'group':
            Action = API.recall_group_message(
                group_id=peer_id,
                message_seq=seq,
            )
        if Action is not None:
            Action.call(bot_hash, control_queue)

    @staticmethod
    def get_msg(target_event: OlivOS.API.Event, message_id: ID) -> RES[MSG]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_msg()
        raw_obj = None
        scene, peer_id, seq = message_id.split('|')
        peer_id = int(peer_id)
        seq = int(seq)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_message(
            message_scene=scene,
            peer_id=peer_id,
            message_seq=seq,
        )
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            if raw_obj['message']['message_scene'] == 'friend':
                mlk_obj = milkyType.IncomingMessage.friend.from_json(raw_obj['message'])
                res_data['data']['message_id'] = msgID(mlk_obj.message_scene, mlk_obj.peer_id, mlk_obj.message_seq)
                res_data['data']['id'] = mlk_obj.message_seq
                res_data['data']['sender']['id'] = mlk_obj.sender_id
                res_data['data']['sender']['name'] = mlk_obj.friend.nickname
                res_data['data']['sender']['nickname'] = mlk_obj.friend.nickname
                res_data['data']['time'] = mlk_obj.time
                res_data['data']['message'] = mlk_obj.segments
                res_data['data']['raw_message'] = mlk_obj.segments
            elif raw_obj['message']['message_scene'] == 'group':
                mlk_obj = milkyType.IncomingMessage.group.from_json(raw_obj['message'])
                res_data['data']['message_id'] = msgID(mlk_obj.message_scene, mlk_obj.peer_id, mlk_obj.message_seq)
                res_data['data']['id'] = mlk_obj.message_seq
                res_data['data']['sender']['id'] = mlk_obj.sender_id
                res_data['data']['sender']['name'] = mlk_obj.group_member.nickname
                res_data['data']['sender']['user_id'] = mlk_obj.group_member.user_id
                res_data['data']['sender']['nickname'] = mlk_obj.group_member.nickname
            else:
                mlk_obj = milkyType.IncomingMessage.temp.from_json(raw_obj['message'])
                res_data['data']['message_id'] = msgID(mlk_obj.message_scene, mlk_obj.peer_id, mlk_obj.message_seq)
                res_data['data']['id'] = mlk_obj.message_seq
                res_data['data']['sender']['id'] = mlk_obj.sender_id
                res_data['data']['sender']['name'] = ''
                res_data['data']['sender']['user_id'] = mlk_obj.sender_id
                res_data['data']['sender']['nickname'] = ''
            res_data['data']['time'] = mlk_obj.time
            res_data['data']['message'] = mlk_obj.segments
            res_data['data']['raw_message'] = mlk_obj.segments
        return res_data

    @staticmethod
    def send_like(target_event: OlivOS.API.Event, user_id: ID, times: int = 1) -> None:
        user_id = int(user_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.send_profile_like(
            user_id=user_id,
            count=times,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_kick(target_event: OlivOS.API.Event, group_id: ID, user_id: ID,
                       reject_add_request: bool = False) -> None:
        group_id = int(group_id)
        user_id = int(user_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.kick_group_member(
            group_id=group_id,
            user_id=user_id,
            reject_add_request=reject_add_request,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_ban(target_event: OlivOS.API.Event, group_id: ID, user_id: ID, duration: int = 1800) -> None:
        group_id = int(group_id)
        user_id = int(user_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.set_group_member_mute(
            group_id=group_id,
            user_id=user_id,
            duration=duration,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_whole_ban(target_event: OlivOS.API.Event, group_id: ID, enable: bool) -> None:
        group_id = int(group_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.set_group_whole_mute(
            group_id=group_id,
            is_muted=enable,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_admin(target_event: OlivOS.API.Event, group_id: ID, user_id: ID, enable: bool) -> None:
        group_id = int(group_id)
        user_id = int(user_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.set_group_member_admin(
            group_id=group_id,
            user_id=user_id,
            is_set=enable,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_card(target_event: OlivOS.API.Event, group_id: ID, user_id: ID, card: str) -> None:
        group_id = int(group_id)
        user_id = int(user_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.set_group_member_card(
            group_id=group_id,
            user_id=user_id,
            card=card,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_name(target_event: OlivOS.API.Event, group_id: ID, group_name: str) -> None:
        group_id = int(group_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.set_group_name(
            group_id=group_id,
            new_group_name=group_name,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_leave(target_event: OlivOS.API.Event, group_id: ID, is_dismiss: bool = False) -> None:
        group_id = int(group_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.quit_group(group_id=group_id)
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_special_title(target_event: OlivOS.API.Event, group_id: ID,
                                user_id: ID, special_title: str, duration) -> None:
        group_id = int(group_id)
        user_id = int(user_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.set_group_member_special_title(
            group_id=group_id,
            user_id=user_id,
            special_title=special_title,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_friend_add_request(target_event: OlivOS.API.Event, flag: ID, approve: bool, remark: str = None) -> None:
        # 这里将flag定义为"<is_filtered>|<initiator_uid>"，在好友添加请求事件中同理
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        is_filtered_s, initiator_uid = flag.split('|')
        is_filtered = False
        if is_filtered_s == 'True':
            is_filtered = True
        if approve:
            Action = API.accept_friend_request(
                initiator_uid=initiator_uid,
                is_filtered=is_filtered,
            )
        else:
            Action = API.reject_friend_request(
                initiator_uid=initiator_uid,
                is_filtered=is_filtered,
            )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_add_request(target_event: OlivOS.API.Event, flag: ID, sub_type: str,
                              approve: bool, reason: str = None) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        if sub_type == 'add':
            # 这里将flag定义为"<notification_type>|<group_id>|<is_filtered>|<notification_seq>"，在加群请求事件中同理
            notification_type, group_id, is_filtered_s, notification_seq = flag.split('|')
            group_id = int(group_id)
            is_filtered = False
            if is_filtered_s == 'True':
                is_filtered = True
            if approve:
                Action = API.accept_group_request(
                    notification_seq=notification_seq,
                    notification_type=notification_type,
                    group_id=group_id,
                    is_filtered=is_filtered,
                )
            else:
                Action = API.reject_group_request(
                    notification_seq=notification_seq,
                    notification_type=notification_type,
                    group_id=group_id,
                    is_filtered=is_filtered,
                )
            Action.call(bot_hash, control_queue)
        elif sub_type == 'invite':
            # 这里将flag定义为"<group_id>|<invitation_seq>"，在邀请入群事件中同理
            group_id, invitation_seq = flag.split('|')
            group_id = int(group_id)
            invitation_seq = int(invitation_seq)
            if approve:
                Action = API.accept_group_invitation(
                    group_id=group_id,
                    invitation_seq=invitation_seq,
                )
            else:
                Action = API.reject_group_invitation(
                    group_id=group_id,
                    invitation_seq=invitation_seq,
                )
            Action.call(bot_hash, control_queue)

    @staticmethod
    def get_login_info(target_event: OlivOS.API.Event) -> RES[USER]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_login_info()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_login_info()
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            res_data['data']['id'] = str(raw_obj['uin'])
            res_data['data']['name'] = raw_obj['nickname']
        return res_data

    @staticmethod
    def get_stranger_info(target_event: OlivOS.API.Event, user_id: ID) -> RES[USER]:
        user_id = int(user_id)
        res_data = OlivOS.contentAPI.api_result_data_template.get_stranger_info()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_user_profile(user_id=user_id)
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            mlk_obj = milkyType.FriendEntity.from_json(raw_obj)
            res_data['active'] = True
            res_data['data']['id'] = str(mlk_obj.user_id)
            res_data['data']['qid'] = mlk_obj.qid
            res_data['data']['name'] = mlk_obj.nickname
            res_data['data']['remark'] = mlk_obj.remark
            res_data['data']['sex'] = mlk_obj.sex
        return res_data

    @staticmethod
    def get_friend_list(target_event: OlivOS.API.Event) -> RES[list[USER]]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_friend_list()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_friend_list()
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            raw_friends = raw_obj['friends']
            for raw_friend in raw_friends:
                res_data_data_this = {}
                res_data_data_this['id'] = raw_friend['user_id']
                res_data_data_this['qid'] = raw_friend['qid']
                res_data_data_this['name'] = raw_friend['nickname']
                res_data_data_this['remark'] = raw_friend['remark']
                res_data_data_this['sex'] = raw_friend['sex']
                res_data['data'].append(res_data_data_this)
        return res_data

    @staticmethod
    def get_group_info(target_event: OlivOS.API.Event, group_id: ID) -> RES[GROUP]:
        group_id = int(group_id)
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_info()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_group_info(group_id=group_id)
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            mlk_obj = milkyType.GroupEntity.from_json(raw_obj['group'])
            res_data['active'] = True
            res_data['data']['name'] = mlk_obj.group_name
            res_data['data']['id'] = str(mlk_obj.group_id)
            res_data['data']['memo'] = mlk_obj.description
            res_data['data']['member_count'] = mlk_obj.member_count
            res_data['data']['max_member_count'] = mlk_obj.max_member_count
            res_data['data']['created_time'] = mlk_obj.created_time
            res_data['data']['question'] = mlk_obj.question
            res_data['data']['announcement'] = mlk_obj.announcement
        return res_data

    @staticmethod
    def get_group_list(target_event: OlivOS.API.Event) -> RES[list[GROUP]]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_list()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_group_list()
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            raw_groups = raw_obj['groups']
            for raw_group in raw_groups:
                res_data_data_this = {}
                res_data_data_this['id'] = str(raw_group['group_id'])
                res_data_data_this['name'] = raw_group['group_name']
                res_data_data_this['memo'] = raw_group['description']
                res_data_data_this['max_member_count'] = raw_group['max_member_count']
                res_data_data_this['member_count'] = raw_group['member_count']
                res_data_data_this['created_time'] = raw_group['created_time']
                res_data_data_this['question'] = raw_group['question']
                res_data_data_this['announcement'] = raw_group['announcement']
                res_data['data'].append(res_data_data_this)
        return res_data

    @staticmethod
    def get_group_member_list(target_event: OlivOS.API.Event, group_id: ID) -> RES[list[GROUP_USER]]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_list()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.get_group_member_list(group_id)
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            raw_members = raw_obj['members']
            for raw_member in raw_members:
                res_data_data_this = {}
                res_data_data_this['id'] = str(raw_member['user_id'])
                res_data_data_this['name'] = raw_member['nickname']
                res_data_data_this['group_id'] = str(raw_member['group_id'])
                res_data_data_this['title'] = raw_member['title']
                res_data_data_this['sex'] = raw_member['sex']
                res_data_data_this['role'] = raw_member['role']
                res_data_data_this['level'] = raw_member['level']
                res_data_data_this['join_time'] = raw_member['join_time']
                res_data['data'].append(res_data_data_this)
        return res_data

    @staticmethod
    def get_group_member_info(target_event: OlivOS.API.Event, group_id: ID, user_id: ID) -> RES[GROUP_USER]:
        group_id = int(group_id)
        user_id = int(user_id)
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_info()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_group_member_info(
            group_id=group_id,
            user_id=user_id,
        )
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            mlk_obj = milkyType.GroupMemberEntity.from_json(raw_obj['member'])
            res_data['active'] = True
            res_data['data']['name'] = mlk_obj.nickname
            res_data['data']['id'] = str(mlk_obj.user_id)
            res_data['data']['group_id'] = str(mlk_obj.group_id)
            res_data['data']['card'] = mlk_obj.card
            res_data['data']['title'] = mlk_obj.title
            res_data['data']['sex'] = mlk_obj.sex
            res_data['data']['role'] = mlk_obj.role
            res_data['data']['level'] = mlk_obj.level
            res_data['data']['join_time'] = mlk_obj.join_time
        return res_data

    @staticmethod
    def can_send_image(target_event: OlivOS.API.Event) -> RES[bool]:
        # 作为非频道QQ特化协议的Milky当然可以发图片
        res_data = OlivOS.contentAPI.api_result_data_template.can_send_image()
        res_data['active'] = True
        res_data['data']['yes'] = True
        return res_data

    @staticmethod
    def can_send_record(target_event: OlivOS.API.Event) -> RES[bool]:
        # 作为非频道QQ特化协议的Milky当然可以发语音
        res_data = OlivOS.contentAPI.api_result_data_template.can_send_record()
        res_data['active'] = True
        res_data['data']['yes'] = True
        return res_data

    @staticmethod
    def get_status(target_event: OlivOS.API.Event) -> RES:
        res_data = OlivOS.contentAPI.api_result_data_template.get_status()
        res_data['active'] = False
        return res_data

    @staticmethod
    def get_version_info(target_event: OlivOS.API.Event) -> RES:
        res_data = OlivOS.contentAPI.api_result_data_template.get_version_info()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_impl_info()
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            res_data['data']['name'] = raw_obj['impl_name']
            res_data['data']['version_full'] = raw_obj['impl_version']
            res_data['data']['version'] = raw_obj['impl_version']
            res_data['data']['protocol_version'] = raw_obj['milky_version']
        return res_data

    @staticmethod
    def get_forward_msg(target_event: OlivOS.API.Event, message_id: ID) -> RES[list[MSG]]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_forward_msg()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_forwarded_messages(forward_id=message_id)
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            res_data['data']['messages'] = raw_obj['messages']
        return res_data

    @staticmethod
    @MilkyMessage('messages')
    def send_group_forward_msg(target_event: OlivOS.API.Event, group_id: ID, messages: list[MSG]) -> None:
        """暂时由插件作者自行组装消息段数组"""
        group_id = int(group_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        new_message = {
            'type': 'forward',
            'data': {
                'messages': messages
            }
        }
        Action = API.send_group_message(
            group_id=group_id,
            message=new_message,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    @MilkyMessage('messages')
    def send_private_forward_msg(target_event: OlivOS.API.Event, user_id: ID, messages: list[MSG]) -> None:
        """暂时由插件作者自行组装消息段数组"""
        user_id = int(user_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        new_message = {
            'type': 'forward',
            'data': {
                'messages': messages
            }
        }
        Action = API.send_private_message(
            user_id=user_id,
            message=new_message,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def get_essence_msg_list(target_event: OlivOS.API.Event, group_id: ID) -> RES[list]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_essence_msg_list()
        raw_obj = None
        group_id = int(group_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_group_essence_messages(
            group_id=group_id,
            page_index=0,
            page_size=30,
        )
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            raw_essence_msgs = raw_obj['messages']
            for raw_essence_msg in raw_essence_msgs:
                mlk_obj = milkyType.GroupEssenceMessage.from_json(raw_essence_msg)
                res_data_data_this = {}
                res_data_data_this['sender_id'] = str(mlk_obj.sender_id)
                res_data_data_this['sender_nick'] = mlk_obj.sender_name
                res_data_data_this['sender_time'] = mlk_obj.message_time
                res_data_data_this['operator_id'] = str(mlk_obj.operator_id)
                res_data_data_this['operator_nick'] = mlk_obj.operator_name
                res_data_data_this['operator_time'] = mlk_obj.operation_time
                res_data_data_this['message_id'] = f'group|{group_id}|{mlk_obj.message_seq}'
                res_data_data_this['message'] = mlk_obj.segments
                res_data['data'].append(res_data_data_this)
        return res_data

    @staticmethod
    def set_essence_msg(target_event: OlivOS.API.Event, message_id: ID) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id, message_seq = message_id.split('|')[1:]
        group_id = int(group_id)
        message_seq = int(message_seq)
        Action = API.set_group_essence_message(
            group_id=group_id,
            message_seq=message_seq,
            is_set=True,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def delete_essence_msg(target_event: OlivOS.API.Event, message_id: ID) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id, message_seq = message_id.split('|')[1:]
        group_id = int(group_id)
        message_seq = int(message_seq)
        Action = API.set_group_essence_message(
            group_id=group_id,
            message_seq=message_seq,
            is_set=False,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_msg_emoji_like(target_event: OlivOS.API.Event, message_id: ID, emoji_id: ID,
                           is_set: bool = True, group_id: ID = None) -> None:
        if group_id is None:
            return
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        message_seq = int(message_id.split('|')[2])
        reaction = emoji_id
        reaction_type = 'face'
        is_add = is_set
        group_id = int(group_id)
        Action = API.send_group_message_reaction(
            group_id=group_id,
            message_seq=message_seq,
            reaction=reaction,
            reaction_type=reaction_type,
            is_add=is_add,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def group_poke(target_event: OlivOS.API.Event, group_id: ID, user_id: ID) -> None:
        group_id = int(group_id)
        user_id = int(user_id)
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.send_group_nudge(
            group_id=group_id,
            user_id=user_id,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def friend_poke(target_event: OlivOS.API.Event, user_id: ID) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        user_id = int(user_id)
        is_self = False
        if user_id == int(target_event.bot_info.id):
            is_self = True
        Action = API.send_friend_nudge(
            user_id=user_id,
            is_self=is_self,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def send_group_sign(target_event: OlivOS.API.Event, group_id: ID) -> None:
        # 目前的Milky暂未提供该API
        pass

    @staticmethod
    def get_group_notice(target_event: OlivOS.API.Event, group_id: ID) -> RES[list]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_notice()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.get_group_announcements(group_id=group_id)
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            raw_annos = raw_obj['announcements']  # 原始人-千早爱音们
            for raw_anno in raw_annos:
                res_data_data_this = {}
                res_data_data_this['sender_id'] = raw_anno['user_id']
                res_data_data_this['publish_time'] = raw_anno['time']
                res_data_data_this['message'] = {
                    'text': raw_anno['content'],
                }
                if raw_anno.get('image_uri') is not None:
                    res_data_data_this['message']['image'] = [raw_anno['image_uri']]
                res_data_data_this['notice_id'] = raw_anno['announcement_id']
                res_data['data'].append(res_data_data_this)
        return res_data

    @staticmethod
    def send_group_notice(target_event: OlivOS.API.Event, group_id: ID,
                          content: str, image: str = None, **kwargs) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.send_group_announcement(
            group_id=group_id,
            content=content,
            image_uri=image,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def upload_group_file(target_event: OlivOS.API.Event, group_id: ID, file: str,
                          name: str = '', folder_id: str = None) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        folder_id = folder_id if folder_id else '/'
        Action = API.upload_group_file(
            group_id=group_id,
            file_uri=file,
            file_name=name,
            parent_folder_id=folder_id,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def delete_group_file(target_event: OlivOS.API.Event, group_id: ID, file_id: str, name: str = None) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.delete_group_file(
            group_id=group_id,
            file_id=file_id,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def create_group_file_folder(target_event: OlivOS.API.Event, group_id: ID, name: str, parent_id: str = '/') -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.create_group_folder(
            group_id=group_id,
            folder_name=name,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def delete_group_folder(target_event: OlivOS.API.Event, group_id: ID, folder_id: str = None) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        folder_id = folder_id if folder_id else '/'
        Action = API.delete_group_folder(
            group_id=group_id,
            folder_id=folder_id,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def get_group_file_system_info(target_event: OlivOS.API.Event, group_id: ID) -> RES:
        # 目前Milky暂未提供该API
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_file_system_info()
        res_data['active'] = False
        return res_data

    @staticmethod
    def get_group_root_files(target_event: OlivOS.API.Event, group_id: ID, file_count: int = None) -> RES:
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_root_files()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.get_group_files(
            group_id=group_id,
            parent_folder_id='/',
        )
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            raw_files = raw_obj['files']
            raw_folders = raw_obj['folders']
            for raw_file in raw_files:
                res_data_file_this = {}
                res_data_file_this['file_id'] = raw_file['file_id']
                res_data_file_this['file_size'] = raw_file['file_size']
                res_data_file_this['file_name'] = raw_file['file_name']
                res_data_file_this['folder_id'] = raw_file['parent_folder_id']
                res_data['data']['files'].append(res_data_file_this)
            for raw_folder in raw_folders:
                res_data_folder_this = {}
                res_data_folder_this['folder_id'] = raw_folder['folder_id']
                res_data_folder_this['folder_name'] = raw_folder['folder_name']
                res_data_folder_this['parent_folder_id'] = raw_folder['parent_folder_id']
                res_data['data']['folders'].append(res_data_folder_this)
        return res_data

    @staticmethod
    def get_group_files_by_folder(target_event: OlivOS.API.Event, group_id: ID,
                                  folder_id: str, file_count: int = None) -> RES:
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_files_by_folder()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.get_group_files(
            group_id=group_id,
            parent_folder_id=folder_id,
        )
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            raw_files = raw_obj['files']
            raw_folders = raw_obj['folders']
            for raw_file in raw_files:
                res_data_file_this = {}
                res_data_file_this['file_id'] = raw_file['file_id']
                res_data_file_this['file_size'] = raw_file['file_size']
                res_data_file_this['file_name'] = raw_file['file_name']
                res_data_file_this['folder_id'] = raw_file['parent_folder_id']
                res_data['data']['files'].append(res_data_file_this)
            for raw_folder in raw_folders:
                res_data_folder_this = {}
                res_data_folder_this['folder_id'] = raw_folder['folder_id']
                res_data_folder_this['folder_name'] = raw_folder['folder_name']
                res_data_folder_this['parent_folder_id'] = raw_folder['parent_folder_id']
                res_data['data']['folders'].append(res_data_folder_this)
        return res_data

    @staticmethod
    def get_group_file_url(target_event: OlivOS.API.Event, group_id: ID, file_id: str) -> RES:
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_file_url()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.get_group_file_download_url(
            group_id=group_id,
            file_id=file_id,
        )
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            res_data['data']['url'] = raw_obj['download_url']
        return res_data

    @staticmethod
    def upload_private_file(target_event: OlivOS.API.Event, user_id: ID, file: str, name: str) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        user_id = int(user_id)
        Action = API.upload_private_file(
            user_id=user_id,
            file_uri=file,
            file_name=name,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def rename_group_file_folder(target_event: OlivOS.API.Event, group_id: ID,
                                 folder_id: str, new_folder_name: str) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.rename_group_folder(
            group_id=group_id,
            folder_id=folder_id,
            new_folder_name=new_folder_name,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def rename_group_file(target_event: OlivOS.API.Event, group_id: ID, file_id: str,
                          current_parent_directory: str, new_name: str) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        group_id = int(group_id)
        Action = API.rename_group_file(
            group_id=group_id,
            file_id=file_id,
            new_file_name=new_name,
            parent_folder_id=current_parent_directory,
        )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def set_group_file_forever(target_event: OlivOS.API.Event, group_id: ID, file_id: str) -> None:
        # 目前Milky暂未提供该API
        pass

    @staticmethod
    def get_group_ignore_add_request(target_event: OlivOS.API.Event, group_id: ID = None) -> RES[list]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_ignore_add_request()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_group_notifications(is_filtered=True)
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            raw_notifications = raw_obj['notifications']
            for raw_notification in raw_notifications:
                if raw_notification['type'] not in ['join_request', 'invited_join_request']:
                    continue
                if group_id is not None and raw_notification['group_id'] != group_id:
                    continue
                res_data_data_this = {}
                res_data_data_this['request_id'] = \
                    f"{raw_notification['type']}|{group_id}|True|{raw_notification['notification_seq']}"
                res_data_data_this['initiator_uin'] = raw_notification['initiator_id']
                res_data_data_this['group_id'] = raw_notification['group_id']
                res_data_data_this['actor'] = raw_notification['operator_id']
                checked = False
                if raw_notification['state'] != 'pending':
                    checked = True
                res_data_data_this['checked'] = checked
                if 'comment' in raw_notification:
                    res_data_data_this['message'] = raw_notification['comment']
                res_data['data'].append(res_data_data_this)
        return res_data

    @staticmethod
    def get_doubt_friends_add_request(target_event: OlivOS.API.Event, count: int = 50) -> RES[list]:
        res_data = OlivOS.contentAPI.api_result_data_template.get_doubt_friends_add_request()
        raw_obj = None
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        Action = API.get_friend_requests(limit=count, is_filtered=True)
        raw = Action.call(bot_hash, control_queue)
        if raw is not None:
            raw_obj = init_api(raw)
        if raw_obj is not None:
            if not isinstance(raw_obj, dict):
                return res_data
            res_data['active'] = True
            raw_requests = raw_obj['requests']
            for raw_request in raw_requests:
                res_data_data_this = {}
                res_data_data_this['flag'] = \
                    f"True|{raw_request['initiator_uid']}"
                res_data_data_this['uin'] = str(raw_request['initiator_id'])
                res_data_data_this['nick'] = '-1'
                res_data_data_this['source'] = raw_request['via']
                res_data_data_this['msg'] = raw_request.get('comment', '')
                res_data_data_this['time'] = raw_request['time']
                res_data_data_this['state'] = raw_request['state']
                res_data['data'].append(res_data_data_this)
        return res_data

    @staticmethod
    def set_doubt_friends_add_request(target_event: OlivOS.API.Event, flag: str, approve: bool = True) -> None:
        control_queue = target_event.plugin_info['control_queue']
        bot_hash = target_event.bot_info.hash
        is_filtered_s, initiator_uid = flag.split('|')
        if approve:
            Action = API.accept_friend_request(
                initiator_uid=initiator_uid,
                is_filtered=True
            )
        else:
            Action = API.reject_friend_request(
                initiator_uid=initiator_uid,
                is_filtered=True
            )
        Action.call(bot_hash, control_queue)

    @staticmethod
    def get_group_system_msg(target_event: OlivOS.API.Event, count: int = 50) -> RES:
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_system_msg()
        res_data['active'] = False
        return res_data


def init_api(raw: dict) -> dict:
    res_data = None
    flag_is_active = False
    if 'status' in raw:
        if isinstance(raw['status'], str):
            if raw['status'] == 'ok':
                flag_is_active = True
    if 'retcode' in raw:
        if isinstance(raw['retcode'], int):
            if raw['retcode'] == 0:
                flag_is_active = True
    if flag_is_active:
        if 'data' in raw:
            if isinstance(raw['data'], dict):
                res_data = raw['data']
    return res_data


def combine_forward_nodes(msg_list):
    """将olivos_para的顺序forward结构合并为Milky的嵌套forward结构，以进行动作上报"""
    res = []
    for msg_this in msg_list:
        if not isinstance(msg_this, dict):
            res.append(msg_this)
            continue
        paraType = msg_this.get('type')
        if paraType == 'forward':
            msg_this = msg_this.copy()
            if 'data' not in msg_this:
                msg_this['data'] = {}
            msg_this['data']['message'] = []
            res.append(msg_this)
        elif paraType == 'node':
            if res and res[-1].get('type') == 'forward':
                res[-1]['data']['message'].append(msg_this)
            else:
                res.append(msg_this)
        else:
            res.append(msg_this)
    return res


def URI_format(msg_list: list):
    for msg_this in msg_list:
        if not isinstance(msg_this, dict):
            continue
        paraType = msg_this.get('type')
        paraData = msg_this.get('data')
        if paraType is None or paraData is None:
            continue
        if paraType not in ['image', 'video', 'record', 'file']:
            continue
        uri = paraData.get('uri')
        if uri is None:
            continue
        if (len(uri) > 1 and uri[1] == ':') or uri.startswith('/'):
            # Windows文件系统特判
            file_path = uri
        else:
            uri_parsed = parse.urlparse(uri)
            if uri_parsed.scheme.lower() not in ['http', 'https', 'file', 'base64']:
                file_path = uri_parsed.path
                if not os.path.isabs(file_path):
                    folder_name = 'files'
                    if paraType == 'image':
                        folder_name = 'images'
                    elif paraType == 'video':
                        folder_name = 'videos'
                    elif paraType == 'record':
                        folder_name = 'audios'
                    file_path = OlivOS.contentAPI.resourcePathTransform(folder_name, file_path)
            else:
                continue
        abs_path = Path(file_path).absolute()
        if abs_path.exists():
            msg_this['data']['uri'] = abs_path.as_uri()
    return msg_list


def msgID(scene: str, peer_id: str | int, seq: int):
    return f'{scene}|{peer_id}|{seq}'


def ready_for_res(post_id: str) -> None:
    gResReg[post_id] = None
    gEveReg[post_id] = threading.Event()


def set_for_res(post_id: str, data) -> None:
    if post_id in gResReg:
        gResReg[post_id] = data
        if post_id in gEveReg:
            gEveReg[post_id].set()


def wait_for_res(post_id: str, timeout=30):
    res = None
    if post_id in gEveReg:
        is_ready = gEveReg[post_id].wait(timeout=timeout)
        if is_ready and post_id in gResReg and gResReg[post_id] is not None:
            res = gResReg[post_id]
        gResReg.pop(post_id, None)
        gEveReg.pop(post_id, None)
    return res
