# -*- encoding: utf-8 -*-
'''
@ _______________________    ________________ 
@ __  __ \__  /____  _/_ |  / /_  __ \_  ___/ 
@ _  / / /_  /  __  / __ | / /_  / / /____ \  
@ / /_/ /_  /____/ /  __ |/ / / /_/ /____/ /  
@ \____/ /_____/___/  _____/  \____/ /____/   
@                                             
@File      :   OlivOS/mhyVilaSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL3
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import requests as req
import time
from datetime import datetime, timezone, timedelta
from requests_toolbelt import MultipartEncoder
import uuid
import traceback
import base64
from urllib import parse
import hashlib
import hmac
import struct
import enum

import OlivOS
import OlivOS.thirdPartyModule.mhyVilaProto as mhyVilaProto
from OlivOS.thirdPartyModule.mhyVilaProto.tools import MessageToDict

sdkAPIHost = {
    'default': 'https://bbs-api.miyoushe.com'
}

sdkAPIRoute = {
    'platform': '/vila/api/bot/platform'
}

sdkIDCount = {}

sdkAPIRouteTemp = {}

sdkSubSelfInfo = {}

sdkNameDict = {}

class bot_info_T(object):
    def __init__(
        self,
        id = -1,
        password = '',
        access_token = '',
        port = 0
    ):
        self.bot_id = id
        self.secret = password
        self.pub_key = access_token
        self.vila_id = port
        self.debug_mode = False
        self.debug_logger = None

def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(
        id = plugin_bot_info.id,
        password = plugin_bot_info.password,
        access_token = plugin_bot_info.post_info.access_token,
        port = plugin_bot_info.post_info.port
    )
    res.debug_mode = plugin_bot_info.debug_mode
    return res

def get_SDK_bot_info_from_Event(target_event):
    return get_SDK_bot_info_from_Plugin_bot_info(target_event.bot_info)

class event(object):
    def __init__(self, BizType:int, dataTable:dict, botInfo):
        self.payload = dataTable
        self.BizType = BizType
        self.platform = botInfo.platform
        self.active = False
        if self.payload is not None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = botInfo.id
            self.base_info['post_type'] = None

def set_name(id:str, name:str):
    global sdkNameDict
    sdkNameDict[str(id)] = str(name)

def get_name(id:str):
    global sdkNameDict
    return sdkNameDict.get(str(id), str(id))

def get_message(contentData:dict):
    msg = contentData.get('content', {}).get('text', '')
    res_msg = ''
    count = 0
    atTable = contentData.get('content', {}).get('entities', [])
    if type(atTable) is list:
        for atTable_this in atTable:
            if type(atTable_this) is dict:
                i_offset = atTable_this.get('offset', None)
                i_length = atTable_this.get('length', None)
                s_type = atTable_this.get('entity', {}).get('type', None)
                if type(i_offset) is int \
                and type(i_length) is int \
                and type(s_type) is str \
                and i_offset + i_length <= len(msg):
                    if s_type == 'mentioned_robot':
                        s_bot_id = atTable_this.get('entity', {}).get('bot_id', None)
                        if type(s_bot_id) is str:
                            res_msg += msg[count:i_offset]
                            res_msg += f'[OP:at,id={s_bot_id}] '
                            set_name(s_bot_id, msg[i_offset + 1:i_offset + i_length - 1])
                            count = i_offset + i_length
                    if s_type == 'mentioned_user':
                        s_user_id = atTable_this.get('entity', {}).get('user_id', None)
                        if type(s_user_id) is str:
                            res_msg += msg[count:i_offset]
                            res_msg += f'[OP:at,id={s_user_id}] '
                            set_name(s_user_id, msg[i_offset + 1:i_offset + i_length - 1])
                            count = i_offset + i_length
        if count <= len(msg):
            res_msg += msg[count:]
    return res_msg


def release_message(msg:str):
    res = {
        'content': {
            'text': '',
            'entities': []
        }
    }
    message_obj = OlivOS.messageAPI.Message_templet(
        'olivos_string',
        msg
    )
    for message_obj_this in message_obj.data:
        if type(message_obj_this) is OlivOS.messageAPI.PARA.at:
            i_offset = len(res['content']['text'])
            res['content']['text'] += f"@{get_name(message_obj_this.data['id'])}"
            i_length = len(res['content']['text']) - i_offset
            obj_this = {
                'offset': i_offset,
                'length': i_length
            }
            if str(message_obj_this.data['id']).isdecimal():
                obj_this['entity'] = {
                    'type': 'mentioned_user',
                    'user_id': message_obj_this.data['id']
                }
            else:
                obj_this['entity'] = {
                    'type': 'mentioned_robot',
                    'bot_id': message_obj_this.data['id']
                }
            res['content']['entities'].append(obj_this)
        elif type(message_obj_this) is OlivOS.messageAPI.PARA.text:
            res['content']['text'] += message_obj_this.data['text']
    return res

def get_Event_from_SDK(target_event):
    global sdkSubSelfInfo
    #print(json.dumps(target_event.sdk_event.__dict__, ensure_ascii=False, indent=4))
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
    #print(type(target_event.sdk_event.payload))
    if target_event.sdk_event.BizType == protoEnum.Model_ROBOTEVENT.value \
    and type(target_event.sdk_event.payload) is dict \
    and target_event.sdk_event.payload.get('type', None) == 'SendMessage' \
    and type(target_event.sdk_event.payload.get('extendData', None)) is dict:
        messageData = target_event.sdk_event.payload.get('extendData', {}).get('sendMessage', None)
        if type(messageData) is dict:
            contentData_str = messageData.get('content', None)
            if type(contentData_str) is str \
            and messageData.get('objectName', None) == 'Text':
                villaId = messageData.get('villaId', None)
                roomId = messageData.get('roomId', None)
                msgUid = messageData.get('msgUid', None)
                nickname = messageData.get('nickname', None)
                fromUserId = messageData.get('fromUserId', None)
                contentData = json.loads(contentData_str)
                #print(json.dumps(contentData, ensure_ascii=False, indent=4))
                if type(villaId) is str \
                and type(roomId) is str \
                and type(msgUid) is str \
                and type(nickname) is str \
                and type(fromUserId) is str:
                    msg = get_message(contentData)
                    target_event.active = True
                    target_event.plugin_info['func_type'] = 'group_message'
                    target_event.data = target_event.group_message(
                        roomId,
                        fromUserId,
                        msg,
                        'group'
                    )
                    target_event.data.message_sdk = OlivOS.messageAPI.Message_templet(
                        'olivos_string',
                        msg
                    )
                    target_event.data.message_id = msgUid
                    target_event.data.raw_message = target_event.data.message
                    target_event.data.raw_message_sdk = target_event.data.message_sdk
                    target_event.data.host_id = villaId
                    target_event.data.font = None
                    target_event.data.sender['name'] = nickname
                    target_event.data.sender['id'] = fromUserId
                    target_event.data.sender['nickname'] = target_event.data.sender['name']
                    target_event.data.sender['user_id'] = target_event.data.sender['id']

'''
对于WEBSOCKET接口的PAYLOAD实现
'''

def getIDCount(botId:str) -> int:
    global sdkIDCount
    if type(sdkIDCount.get(str(botId), None)) is not int:
        sdkIDCount[str(botId)] = 0
    res:int = sdkIDCount[str(botId)] + 1
    sdkIDCount[str(botId)] = res
    return res

class protoEnum(enum.Enum):
    Command_P_HEARTBEAT = mhyVilaProto.command.Command.P_HEARTBEAT
    Command_P_LOGIN = mhyVilaProto.command.Command.P_LOGIN
    Command_P_LOGOUT = mhyVilaProto.command.Command.P_LOGOUT
    Model_ROBOTEVENT = 30001

recvProtoDict = {
    protoEnum.Command_P_HEARTBEAT.value: mhyVilaProto.command.PHeartBeatReply,
    protoEnum.Command_P_LOGIN.value: mhyVilaProto.command.PLoginReply,
    protoEnum.Command_P_LOGOUT.value: mhyVilaProto.command.PLogoutReply,
    protoEnum.Model_ROBOTEVENT.value: mhyVilaProto.model.RobotEvent,
}

sendProtoDict = {
    protoEnum.Command_P_HEARTBEAT.value: mhyVilaProto.command.PHeartBeat,
    protoEnum.Command_P_LOGIN.value: mhyVilaProto.command.PLogin,
    protoEnum.Command_P_LOGOUT.value: mhyVilaProto.command.PLogout,
}

class payload_template(object):
    def __init__(self, raw:'bytearray|None'=None):
        self.active = True
        self.raw = raw
        self.is_rx = False
        if self.raw is not None:
            self.is_rx = True
        self.magicHeader = self.magicHeader_T()
        self.dataHeader = self.dataHeader_T()
        self.dataDataBody:bytearray = b''
        self.data = None
        self.dataTable = {}
        self.dataProto = None
        if self.is_rx:
            self.load()

    class magicHeader_T(object):
        def __init__(self):
            self.Magic:int = 0xBABEFACE
            self.DataLen:int = 0

    class dataHeader_T(object):
        def __init__(self):
            self.HeaderLen:int = 24   # uint32    变长头总长度，变长头部分所有字段（包括HeaderLen本身）的总长度。 注：也就是说这玩意每个版本是固定的
            self.ID:int = 1           # uint64    协议包序列ID，同一条连接上的发出的协议包应该单调递增，相同序列ID且Flag字段相同的包应该被认为是同一个包
            self.Flag:int = 1         # uint32    配合bizType使用，用于标识同一个bizType协议的方向。
                                      #             用 1 代表主动发到服务端的request包
                                      #             用 2 代表针对某个request包回应的response包
            self.BizType:int = 0      # uint32    消息体的业务类型，用于标识Body字段中的消息所属业务类型
            self.AppId:int = 104      # int32     应用标识。固定为 104

    def __dump_dataDataBody(self):
        if self.data is not None:
            self.dataTable = self.data.__dict__
        if self.dataProto is not None:
            self.dataDataBody = self.dataProto(**self.dataTable).SerializeToString()
        return self.dataDataBody

    def __update_DataLen(self):
        self.magicHeader.DataLen = self.dataHeader.HeaderLen + len(self.dataDataBody)
        return self.magicHeader.DataLen

    def __dump_magicHeader(self):
        return struct.pack(
            '<II',
            self.magicHeader.Magic,
            self.magicHeader.DataLen
        )

    def __dump_dataHeader(self):
        self.dataHeader.ID = getIDCount('unity')
        return struct.pack(
            '<IQIIi',
            self.dataHeader.HeaderLen,
            self.dataHeader.ID,
            self.dataHeader.Flag,
            self.dataHeader.BizType,
            self.dataHeader.AppId
        )

    def dump(self):
        if self.raw is None:
            self.raw = b''
        self.__dump_dataDataBody()
        self.__update_DataLen()
        self.raw = self.__dump_magicHeader() + self.__dump_dataHeader() + self.dataDataBody
        return self.raw

    def load(self):
        global recvProtoDict
        if self.raw is not None \
        and len(self.raw) >= 32:
            self.magicHeader.Magic, \
            self.magicHeader.DataLen = struct.unpack(
                '<II',
                self.raw[:8]
            )
            self.dataHeader.HeaderLen, \
            self.dataHeader.ID, \
            self.dataHeader.Flag, \
            self.dataHeader.BizType, \
            self.dataHeader.AppId = struct.unpack(
                '<IQIIi',
                self.raw[8:32]
            )
            self.dataDataBody = self.raw[32:]
            if recvProtoDict.get(self.dataHeader.BizType, None) is not None:
                self.dataProto = recvProtoDict[self.dataHeader.BizType]
                protoObj = self.dataProto()
                protoObj.ParseFromString(self.dataDataBody)
                self.dataTable = MessageToDict(protoObj)
        return self

    def get_hex_str(self):
        return self.raw.hex()

    def get_data_str(self):
        return str(self.dataTable)

    def __str__(self):
        return f'<mhyVilaSDK PAYLOAD [{str(self.dataProto.__name__ if self.dataProto is not None else None)}] BizType={self.dataHeader.BizType} ID={self.dataHeader.ID} dataTable={self.get_data_str()} HEX={self.get_hex_str()}>'

class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, raw):
            payload_template.__init__(self, raw)

    # 登录命令
    class PLogin(payload_template):
        def __init__(self):
            payload_template.__init__(self)
            self.dataHeader.Flag = 1
            self.dataHeader.BizType = protoEnum.Command_P_LOGIN.value
            self.data = self.data_T()
            self.dataProto = sendProtoDict[self.dataHeader.BizType]

        class data_T(object):
            def __init__(self):
                self.uid:int = 0
                self.token:str = ''
                self.platform:int = 0
                self.app_id:int = 0
                self.device_id:str = ''
                self.region:str = ''
                self.meta:dict = {}

    # 心跳命令
    class PHeartBeat(payload_template):
        def __init__(self):
            payload_template.__init__(self)
            self.dataHeader.Flag = 1
            self.dataHeader.BizType = protoEnum.Command_P_HEARTBEAT.value
            self.data = self.data_T()
            self.dataProto = sendProtoDict[self.dataHeader.BizType]

        class data_T(object):
            def __init__(self):
                self.client_timestamp:str = str(int(datetime.now(timezone.utc).timestamp() * 1000))


'''
对于POST接口的实现
'''

def get_bot_secret(bot_info:bot_info_T):
    return str(hmac.new(
        str(bot_info.pub_key).encode('utf-8'),
        str(bot_info.secret).encode('utf-8'),
        hashlib.sha256
    ).hexdigest())

class api_templet(object):
    def __init__(self):
        self.bot_info:'bot_info_T|None' = None
        self.data = None
        self.metadata = None
        self.headdata = self.headdata_T()
        self.host = sdkAPIHost['default']
        self.route = None
        self.res = None

    class headdata_T(object):
        def __init__(self):
            self.vila_id = None

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
                'x-rpc-bot_secret': '%s' % get_bot_secret(self.bot_info),
                'x-rpc-bot_id': '%s' % str(self.bot_info.bot_id)
            }
            if self.headdata.vila_id is not None:
                headers['x-rpc-bot_villa_id'] = '%s' % self.headdata.vila_id

            msg_res = None
            if req_type == 'POST':
                msg_res = req.request("POST", send_url, headers=headers, data=payload)
            elif req_type == 'GET':
                msg_res = req.request("GET", send_url, headers=headers)

            self.res = msg_res.text
            #print(self.res)
            return msg_res.text
        except:
            return None

class API(object):
    class getWebsocketInfo(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.route = sdkAPIRoute['platform'] + '/getWebsocketInfo'

    class sendMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.route = sdkAPIRoute['platform'] + '/sendMessage'

        class data_T(object):
            def __init__(self):
                self.room_id = -1
                self.object_name = 'MHY:Text'
                self.msg_content = ''


# 支持OlivOS API调用的方法实现
class event_action(object):
    def send_group_msg(target_event, chat_id, message, host_id = None):
        if host_id is None:
            try:
                host_id = target_event.data.host_id
            except:
                pass
        sdk_bot_info = get_SDK_bot_info_from_Event(target_event)
        api_obj = API.sendMessage(sdk_bot_info)
        api_obj.headdata.vila_id = host_id
        api_obj.data.room_id = chat_id
        api_obj.data.msg_content = json.dumps(release_message(message))
        api_obj.data.object_name = 'MHY:Text'
        api_obj.do_api('POST')
        return None

    def create_panel_message(target_event, chat_id, object_name, content:dict, host_id = None):
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['active'] = True
        if host_id is None:
            try:
                host_id = target_event.data.host_id
            except:
                pass
        sdk_bot_info = get_SDK_bot_info_from_Event(target_event)
        api_obj = API.sendMessage(sdk_bot_info)
        api_obj.headdata.vila_id = host_id
        api_obj.data.room_id = chat_id
        api_obj.data.msg_content = json.dumps(content)
        api_obj.data.object_name = object_name
        api_obj.do_api('POST')
        res_data['data'] = {}
        res_data['data']['chat_type'] = 'private' if False else 'group'
        res_data['data']['chat_id'] = str(chat_id)
        res_data['data']['object_name'] = str(object_name)
        res_data['data']['content'] = str(json.dumps(content, ensure_ascii = False))
        return res_data


class inde_interface(OlivOS.API.inde_interface_T):
    @OlivOS.API.Event.callbackLogger('mhyVila:create_message', ['chat_type', 'chat_id', 'object_name', 'content'])
    def __create_message(target_event, chat_type:str, chat_id:str, object_name:str, content:dict, host_id=None, flag_log:bool=True):
        res_data = None
        if chat_type == 'group':
            res_data = OlivOS.mhyVilaSDK.event_action.create_panel_message(
                target_event = target_event,
                chat_id = chat_id,
                object_name = object_name,
                content = content,
                host_id = host_id
            )
        return res_data

    def create_message(
        self,
        chat_type:str,
        chat_id:str,
        object_name:str,
        content:dict,
        host_id:'str|None' = None,
        flag_log: bool = True,
        remote: bool = False
    ):
        res_data = None
        if remote:
            pass
        else:
            res_data = inde_interface.__create_message(
                self.event,
                chat_type = chat_type,
                chat_id = chat_id,
                object_name = object_name,
                content = content,
                host_id = host_id,
                flag_log = True
            )
        return res_data

