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
@Copyright :   (C) 2020-2023, OlivOS-Team
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
import hashlib
import hmac
import struct

import OlivOS
import OlivOS.thirdPartyModule.mhyVilaProto as mhyVilaProto

sdkAPIHost = {
    'default': 'https://bbs-api.miyoushe.com'
}

sdkAPIRoute = {
    'platform': '/vila/api/bot/platform'
}

sdkAPIRouteTemp = {}

sdkSubSelfInfo = {}


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


'''
对于WEBSOCKET接口的PAYLOAD实现
'''

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
        self.dataProto = None

    class magicHeader_T(object):
        def __init__(self):
            self.HeaderLen:int = 8
            self.Magic:bytearray = b'\xBA\xBE\xFA\xCE'
            self.DataLen:int = 0

    class dataHeader_T(object):
        def __init__(self):
            self.HeaderLen:int = 24   # uint32    变长头总长度，变长头部分所有字段（包括HeaderLen本身）的总长度。 注：也就是说这玩意每个版本是固定的
            self.ID:int = 0           # uint64    协议包序列ID，同一条连接上的发出的协议包应该单调递增，相同序列ID且Flag字段相同的包应该被认为是同一个包
            self.Flag:int = 1         # uint32    配合bizType使用，用于标识同一个bizType协议的方向。
                                      #             用 1 代表主动发到服务端的request包
                                      #             用 2 代表针对某个request包回应的response包
            self.BizType:int = 0      # uint32    消息体的业务类型，用于标识Body字段中的消息所属业务类型
            self.AppId:int = 104      # int32     应用标识。固定为 104

    def __dump_dataDataBody(self):
        if self.data is not None \
        and self.dataProto is not None:
            self.dataDataBody = self.dataProto(**self.data.__dict__).SerializeToString()
        return self.dataDataBody

    def __update_DataLen(self):
        self.magicHeader.DataLen = self.magicHeader.HeaderLen + self.dataHeader.HeaderLen + len(self.dataDataBody)
        return self.magicHeader.DataLen

    def __dump_magicHeader(self):
        return struct.pack(
            '<4sI',
            self.magicHeader.Magic,
            self.magicHeader.DataLen
        )

    def __dump_dataHeader(self):
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
        self.raw += self.__dump_dataDataBody()
        self.__update_DataLen()
        self.raw = self.__dump_magicHeader() + self.__dump_dataHeader() + self.raw
        return self.raw

    def load(self, data, is_rx):
        return self


class PAYLOAD(object):
    class rxPacket(payload_template):
        def __init__(self, raw):
            payload_template.__init__(self, data, True)

    # 登录命令
    class PLogin(payload_template):
        def __init__(self):
            payload_template.__init__(self)
            self.data = self.data_T()
            self.dataProto = mhyVilaProto.command.PLogin

        class data_T(object):
            def __init__(self):
                self.uid:int = 1
                self.token:str = '2'
                self.platform:int = 3
                self.app_id:int = 4
                self.device_id:str = '5'
                self.region:str = '6'


'''
对于POST接口的实现
'''

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
                'x-rpc-bot_secret': '%s' % str(hmac.new(
                    str(self.bot_info.pub_key).encode('utf-8'),
                    str(self.bot_info.secret).encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()),
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

# test
print(PAYLOAD.PLogin().dump())
