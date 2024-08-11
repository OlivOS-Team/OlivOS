# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/biliLiveSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import OlivOS

import time
import aiohttp
from aiohttp.client import ClientSession
from enum import IntEnum
from aiohttp import cookiejar
from genericpath import exists
import json

QRCODE_REQUEST_URL = 'http://passport.bilibili.com/qrcode/getLoginUrl'
CHECK_LOGIN_RESULT = 'http://passport.bilibili.com/qrcode/getLoginInfo'
SEND_URL = 'https://api.live.bilibili.com/msg/send'
MUTE_USER_URL = 'https://api.live.bilibili.com/xlive/web-ucenter/v1/banned/AddSilentUser'
ROOM_SLIENT_URL = 'https://api.live.bilibili.com/xlive/web-room/v1/banned/RoomSilent'
ADD_BADWORD_URL = 'https://api.live.bilibili.com/xlive/web-ucenter/v1/banned/AddShieldKeyword'
DEL_BADWORD_URL = 'https://api.live.bilibili.com/xlive/web-ucenter/v1/banned/DelShieldKeyword'


class bot_info_T(object):
    def __init__(self, id=-1, room_id=None):
        self.id = id
        self.room_id = room_id
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
    def __init__(self, payload_data=None, bot_info=None):
        self.payload = payload_data
        self.platform = {'sdk': 'biliLive_link', 'platform': 'biliLive', 'model': 'default'}
        self.active = False
        if self.payload is not None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = bot_info.id
            self.base_info['room_id'] = bot_info.post_info.access_token
            self.base_info['post_type'] = None


class BiliLiveBot(OlivOS.thirdPartyModule.blivedm.BLiveClient):
    def __init__(
            self,
            room_id,
            uid=0,
            session=None,
            heartbeat_interval=30,
            ssl=True,
            loop=None,
            Proc=None
    ):
        super().__init__(
            room_id,
            uid=uid,
            session=session,
            heartbeat_interval=heartbeat_interval,
            ssl=ssl,
            loop=loop
        )
        self.Proc = Proc
        handler = SDKHandler()
        self.add_handler(handler)


class SDKHandler(OlivOS.thirdPartyModule.blivedm.BaseHandler):
    async def _on_danmaku(self, client: BiliLiveBot, message: OlivOS.thirdPartyModule.blivedm.models.DanmakuMessage):
        try:
            sdk_event = event(message, client.Proc.Proc_data['bot_info_dict'])
            tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
            client.Proc.Proc_info.tx_queue.put(tx_packet_data, block=False)
        except Exception as e:
            pass


def get_Event_from_SDK(target_event: event):
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info['self_id'])
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'olivos_string'
    plugin_event_bot_hash = OlivOS.API.getBotHash(
        bot_id=target_event.base_info['self_id'],
        platform_sdk=target_event.platform['sdk'],
        platform_platform=target_event.platform['platform'],
        platform_model=target_event.platform['model']
    )
    type_sdk_event = type(target_event.sdk_event.payload)
    if type_sdk_event == OlivOS.thirdPartyModule.blivedm.models.DanmakuMessage:
        sdk_payload: OlivOS.thirdPartyModule.blivedm.models.DanmakuMessage = target_event.sdk_event.payload
        target_event.active = True
        target_event.plugin_info['func_type'] = 'group_message'
        message_obj = OlivOS.messageAPI.Message_templet('olivos_string', sdk_payload.msg)
        target_event.data = target_event.group_message(
            str(target_event.sdk_event.base_info['self_id']),
            str(sdk_payload.uid),
            sdk_payload.msg,
            'group'
        )
        target_event.data.message_sdk = message_obj
        target_event.data.message_id = '-1'
        target_event.data.raw_message = sdk_payload.msg
        target_event.data.raw_message_sdk = message_obj
        target_event.data.font = None
        target_event.data.sender['user_id'] = str(sdk_payload.uid)
        target_event.data.sender['nickname'] = str(sdk_payload.uname)
        target_event.data.sender['id'] = str(sdk_payload.uid)
        target_event.data.sender['name'] = str(sdk_payload.uname)
        target_event.data.sender['sex'] = 'unknown'
        target_event.data.sender['age'] = 0
        target_event.data.sender['role'] = 'member'
        target_event.data.host_id = None


# 支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, message, control_queue):
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id=target_event.base_info['self_id'],
            platform_sdk=target_event.platform['sdk'],
            platform_platform=target_event.platform['platform'],
            platform_model=target_event.platform['model']
        )
        message_new = ''
        message_obj = OlivOS.messageAPI.Message_templet(
            'olivos_string',
            message
        )
        if message_obj.active:
            for data_this in message_obj.data:
                if data_this.type == 'text':
                    message_new += data_this.data['text']
                elif data_this.type == 'image':
                    imagePath = data_this.data['file']
                    if data_this.data['url'] is not None:
                        imagePath = data_this.data['url']
                    message_new += '![%s](%s)' % (
                        imagePath,
                        imagePath
                    )
        if len(message_new) > 0:
            send_ws_event(
                plugin_event_bot_hash,
                PAYLOAD.chat(
                    message=message_new
                ).data,
                control_queue
            )


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
    sendControlEventSend('send', {
        'target': {
            'type': 'biliLive_link',
            'hash': hash
        },
        'data': {
            'action': 'send',
            'data': data
        }
    }, control_queue)


def send_QRCode_event(hash, path: str, control_queue):
    sendControlEventSend('send', {
        'target': {
            'type': 'nativeWinUI'
        },
        'data': {
            'action': 'gocqhttp',
            'event': 'qrcode',
            'hash': hash,
            'path': path
        }
    }, control_queue)


class DanmakuPosition(IntEnum):
    TOP = 5,
    BOTTOM = 4,
    NORMAL = 1


'''
对于WEBSOCKET接口的PAYLOAD实现
'''


class payload_template(object):
    def __init__(self, data=None, is_rx=False):
        self.active = True
        self.cmd = None
        self.data = None
        self.load(data, is_rx)

    def load(self, data, is_rx: bool):
        if data is not None:
            if type(data) == dict:
                if 'cmd' in data and type(data['cmd']) == str:
                    self.cmd = data['cmd']
                else:
                    self.active = False
                self.data = data
            else:
                self.active = False
        return self


class PAYLOAD(object):
    class chat(payload_template):
        def __init__(self, message: str):
            payload_template.__init__(self)
            self.cmd = 'chat'
            self.data = {
                'msg': message,
                'fontsize': 25,
                'color': 0xffffff,
                'pos': DanmakuPosition.NORMAL,
                'roomid': -1,
                'bubble': 0
            }


"""
Http Request

"""


async def aiohttpGet(session: ClientSession, url: str):
    async with session.get(url) as resp:
        resp.raise_for_status()
        data = await resp.json()
        if 'code' in data and data['code'] != 0:
            raise Exception(data['message'] if 'message' in data else data['code'])
        return data


async def aiohttpPost(session: ClientSession, url: str, **data):
    form = aiohttp.FormData()
    for (k, v) in data.items():
        form.add_field(k, v)
    async with session.post(url, data=form) as resp:
        resp.raise_for_status()
        data = await resp.json()
        if 'code' in data and data['code'] != 0:
            raise Exception(data['message'] if 'message' in data else data['code'])
        return data


def get_cookies(cookies: cookiejar.CookieJar, name: str):
    for cookie in cookies:
        if cookie.key == name:
            return cookie.value
    return None


def load_cookies(path: str):
    cookies = {}
    session_exist = exists(path)
    if session_exist:
        with open(path, encoding='utf-8') as f:
            cookies = json.load(f)
    return cookies


def save_cookies(cookies: cookiejar.CookieJar, path: str):
    cookies_dict = {}
    for cookie in cookies:
        cookies_dict[cookie.key] = cookie.value
    with open(path, mode='w', encoding='utf-8') as f:
        json.dump(cookies_dict, f)
    return None
