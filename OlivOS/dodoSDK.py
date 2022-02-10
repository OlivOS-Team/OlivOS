# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/dodoSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import requests as req
import json
import time
import uuid
#import urllib

import OlivOS


dodoAPIHost = {
    'beta': 'https://apis.mahuatalk.com'
}

dodoAPIRoute = {
    'tokenmgr': '/island/api/beta/@me',
    'apiroot': '/island/api/beta'
}


class bot_info_T(object):
    def __init__(self, id = -1, access_token = None):
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

class api_templet(object):
    def __init__(self):
        self.bot_info = None
        self.data = None
        self.host = None
        self.port = 443
        self.route = None
        self.res = None

    def do_api(self):
        try:
            tmp_payload_dict = {
                'uid': self.bot_info.id,
                'token': self.bot_info.access_token,
                'clientType': 3
            }
            if self.data != None:
                for data_this in self.data.__dict__:
                    if self.data.__dict__[data_this] != None:
                        tmp_payload_dict[data_this] = self.data.__dict__[data_this]

            #payload = urllib.parse.urlencode(tmp_payload_dict)
            payload = tmp_payload_dict
            send_url = self.host + ':' + str(self.port) + self.route
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA
            }

            msg_res = req.request("POST", send_url, headers = headers, data = payload)

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ' - sendding succeed: ' + msg_res.text)

            self.res = msg_res.text
            return msg_res.text
        except:
            return None

class event(object):
    def __init__(self, json_obj = None, bot_info = None, islandId = None):
        self.raw = self.event_dump(json_obj)
        self.json = json_obj
        self.platform = {}
        self.platform['sdk'] = 'dodo_poll'
        self.platform['platform'] = 'dodo'
        self.platform['model'] = 'default'
        self.islandId = islandId
        self.active = False
        if self.json != None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = bot_info.id
            self.base_info['post_type'] = None

    def event_dump(self, raw):
        try:
            res = json.dumps(raw)
        except:
            res = None
        return res

def get_Event_from_SDK(target_event):
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = target_event.sdk_event.base_info['self_id']
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'olivos_para'
    if True:
        message_obj = None
        if 'content' in target_event.sdk_event.json:
            if target_event.sdk_event.json['content'] != '':
                message_obj = OlivOS.messageAPI.Message_templet(
                    'dodo_string',
                    ' '.join(str(target_event.sdk_event.json['content']).split())
                )
                message_obj.mode_rx = target_event.plugin_info['message_mode_rx']
                message_obj.data_raw = message_obj.data.copy()
        if 'resourceJson' in target_event.sdk_event.json:
            if target_event.sdk_event.json['resourceJson'] != '':
                resourceJson_obj = None
                try:
                    resourceJson_obj = json.loads(target_event.sdk_event.json['resourceJson'])
                    message_obj = OlivOS.messageAPI.Message_templet(
                        'olivos_para',
                        [
                            OlivOS.messageAPI.PARA.image(resourceJson_obj['resourceUrl'])
                        ]
                    )
                except:
                    return
        if message_obj != None:
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message'
            target_event.data = target_event.group_message(
                target_event.sdk_event.json['channelId'],
                target_event.sdk_event.json['uid'],
                message_obj,
                'group'
            )
            target_event.data.message_sdk = message_obj
            target_event.data.message_id = target_event.sdk_event.json['id']
            target_event.data.raw_message = message_obj
            target_event.data.raw_message_sdk = message_obj
            target_event.data.font = None
            target_event.data.sender['user_id'] = target_event.sdk_event.json['uid']
            target_event.data.sender['nickname'] = target_event.sdk_event.json['nickName']
            target_event.data.sender['id'] = target_event.sdk_event.json['uid']
            target_event.data.sender['name'] = target_event.sdk_event.json['nickName']
            target_event.data.sender['sex'] = 'unknown'
            target_event.data.sender['age'] = 0
            if target_event.sdk_event.islandId != None:
                target_event.data.host_id = target_event.sdk_event.islandId
                target_event.data.extend['host_group_id'] = target_event.sdk_event.islandId

#支持OlivOS API调用的方法实现
class event_action(object):
    def send_msg(target_event, chat_id, message):
        flag_now_type = 'string'
        this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.channelId = chat_id
        this_msg.data.content = ''
        for message_this in message.data:
            if type(message_this) == OlivOS.messageAPI.PARA.image:
                if flag_now_type != 'image':
                    if this_msg.data.content != '':
                        this_msg.do_api()
                this_msg.data.content = ''
                this_msg.data.resourceJson = json.dumps({
                        'resourceType': 1,
                        'useType': 1,
                        'width': 283,
                        'height': 283,
                        'resourceUrl': message_this.data['file']
                })
                this_msg.data.type = 2
                this_msg.data.tk = uuid.uuid4()
                if this_msg.data.resourceJson != '{}':
                    this_msg.do_api()
                flag_now_type = 'image'
            else:
                if flag_now_type == 'image':
                    this_msg.data.content = ''
                    this_msg.data.resourceJson = '{}'
                    this_msg.data.type = 1
                    this_msg.data.tk = uuid.uuid4()
                this_msg.data.content += message_this.dodo()
                flag_now_type = 'string'
        if flag_now_type != 'image':
            if this_msg.data.content != '':
                this_msg.do_api()

    def send_private_msg(target_event, host_id, chat_id, message):
        this_msg = API.sendMessagePrivate(get_SDK_bot_info_from_Event(target_event))
        if host_id != None:
            this_msg.data.islandId = host_id
        this_msg.data.toUid = chat_id
        this_msg.data.content = ''
        for message_this in message.data:
            if type(message_this) == OlivOS.messageAPI.PARA.text:
                this_msg.data.content = message_this.OP()
                this_msg.data.resourceJson = '{}'
                this_msg.data.type = 1
                this_msg.data.tk = uuid.uuid4()
                if this_msg.data.content != '':
                    this_msg.do_api()
            elif type(message_this) == OlivOS.messageAPI.PARA.image:
                this_msg.data.content = ''
                this_msg.data.resourceJson = json.dumps({
                        'resourceType': 1,
                        'useType': 1,
                        'width': 283,
                        'height': 283,
                        'resourceUrl': message_this.data['file']
                })
                this_msg.data.type = 2
                this_msg.data.tk = uuid.uuid4()
                if this_msg.data.resourceJson != '{}':
                    this_msg.do_api()

class API(object):
    class extendMyLife(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.host = dodoAPIHost['beta']
            self.route = dodoAPIRoute['tokenmgr'] + '/extend-my-life'


    class requestNewToken(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.host = dodoAPIHost['beta']
            self.route = dodoAPIRoute['tokenmgr'] + '/request-new-token'


    class getIslandList(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.host = dodoAPIHost['beta']
            self.route = dodoAPIRoute['apiroot'] + '/islands'


    class getChannelList(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = dodoAPIHost['beta']
            self.route = dodoAPIRoute['apiroot'] + '/channels'

        class data_T(object):
            def __init__(self):
                self.islandId = 0


    class getChannelUpdate(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = dodoAPIHost['beta']
            self.route = dodoAPIRoute['apiroot'] + '/messages'

        class data_T(object):
            def __init__(self):
                self.channelId = 0
                self.size = 50


    class getIslandUpdate(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = dodoAPIHost['beta']
            self.route = dodoAPIRoute['apiroot'] + '/messages/batch'

        class data_T(object):
            def __init__(self):
                self.islandId = 0


    class sendMessage(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = dodoAPIHost['beta']
            self.route = dodoAPIRoute['apiroot'] + '/messages/send'

        class data_T(object):
            def __init__(self):
                self.channelId = 0
                self.type = 1
                self.content = ''
                self.resourceJson = '{}'
                self.referencedMessageId = None
                self.tk = uuid.uuid4()


    class sendMessagePrivate(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = dodoAPIHost['beta']
            self.route = dodoAPIRoute['apiroot'] + '/chat/send'

        class data_T(object):
            def __init__(self):
                self.islandId = 0
                self.toUid = 0
                self.type = 1
                self.content = ''
                self.resourceJson = '{}'
                self.referencedMessageId = None
                self.tk = uuid.uuid4()


    class setMemberNickname(api_templet):
        def __init__(self, bot_info = None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.host = dodoAPIHost['beta']
            self.route = dodoAPIRoute['apiroot'] + '/member/nickname/edit'

        class data_T(object):
            def __init__(self):
                self.islandId = 0
                self.toUid = 0
                self.nickName = ''
