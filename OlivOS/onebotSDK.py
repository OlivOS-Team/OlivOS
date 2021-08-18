# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/onebotSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import requests as req
import OlivOS

class bot_info_T(object):
    def __init__(self, id = -1, host = '', port = -1, access_token = None):
        self.id = id
        self.host = host
        self.port = port
        self.access_token = access_token
        self.debug_mode = False
        self.debug_logger = None

def get_SDK_bot_info_from_Event(target_event):
    res = bot_info_T(
        target_event.bot_info.id,
        target_event.bot_info.post_info.host,
        target_event.bot_info.post_info.port,
        target_event.bot_info.post_info.access_token
    )
    res.debug_mode = target_event.bot_info.debug_mode
    return res

class send_onebot_post_json_T(object):
    def __init__(self):
        self.bot_info = None
        self.obj = None
        self.node_ext = ''

    def send_onebot_post_json(self):
        if type(self.bot_info) is not bot_info_T or self.bot_info.host == '' or self.bot_info.port == -1 or self.obj == None or self.node_ext == '':
            return None
        else:
            json_str_tmp = json.dumps(obj = self.obj.__dict__)
            send_url = self.bot_info.host + ':' + str(self.bot_info.port) + '/' + self.node_ext + '?access_token=' + self.bot_info.access_token

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ': ' + json_str_tmp)

            headers = {
                'Content-Type': 'application/json'
            }
            msg_res = req.request("POST", send_url, headers = headers, data = json_str_tmp)

            if self.bot_info.debug_mode:
                if self.bot_info.debug_logger != None:
                    self.bot_info.debug_logger.log(0, self.node_ext + ' - sendding succeed: ' + msg_res.text)

            return msg_res

class api_templet(object):
    def __init__(self):
        self.bot_info = None
        self.data = None
        self.node_ext = None
        self.res = None

    def do_api(self):
        this_post_json = send_onebot_post_json_T()
        this_post_json.bot_info = self.bot_info
        this_post_json.obj = self.data
        this_post_json.node_ext = self.node_ext
        self.res = this_post_json.send_onebot_post_json()
        return self.res

    def do_api_async(self):
        this_post_json = send_onebot_post_json_T()
        this_post_json.bot_info = self.bot_info
        this_post_json.obj = self.data
        this_post_json.node_ext = self.node_ext + '_async'
        self.res = this_post_json.send_onebot_post_json()
        return self.res

    def do_api_rate_limited(self):
        this_post_json = send_onebot_post_json_T()
        this_post_json.bot_info = self.bot_info
        this_post_json.obj = self.data
        this_post_json.node_ext = self.node_ext + '_rate_limited'
        self.res = this_post_json.send_onebot_post_json()
        return self.res

class event(object):
    def __init__(self, raw):
        self.raw = raw
        self.json = self.event_load(raw)
        self.platform = {}
        self.platform['sdk'] = 'onebot'
        self.platform['platform'] = 'qq'
        self.platform['model'] = 'default'
        self.active = False
        if self.json != None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = self.json['time']
            self.base_info['self_id'] = self.json['self_id']
            self.base_info['post_type'] = self.json['post_type']

    def event_load(self, raw):
        try:
            res = json.loads(raw)
        except:
            res = None
        return res


#支持OlivOS API事件生成的映射实现
def get_Event_from_SDK(target_event):
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = target_event.sdk_event.base_info['self_id']
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    if target_event.base_info['type'] == 'message':
        if target_event.sdk_event.json['message_type'] == 'private':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message'
            target_event.data = target_event.private_message(target_event.sdk_event.json['user_id'], target_event.sdk_event.json['message'], target_event.sdk_event.json['sub_type'])
            target_event.data.message_id = target_event.sdk_event.json['message_id']
            target_event.data.raw_message = target_event.sdk_event.json['raw_message']
            target_event.data.font = target_event.sdk_event.json['font']
            target_event.data.sender.update(target_event.sdk_event.json['sender'])
        elif target_event.sdk_event.json['message_type'] == 'group':
            if target_event.sdk_event.json['sub_type'] == 'normal':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_message'
                target_event.data = target_event.group_message(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['user_id'], target_event.sdk_event.json['message'], target_event.sdk_event.json['sub_type'])
                target_event.data.message_id = target_event.sdk_event.json['message_id']
                target_event.data.raw_message = target_event.sdk_event.json['raw_message']
                target_event.data.font = target_event.sdk_event.json['font']
                target_event.data.sender.update(target_event.sdk_event.json['sender'])
    elif target_event.base_info['type'] == 'notice':
        if target_event.sdk_event.json['notice_type'] == 'group_upload':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_file_upload'
            target_event.data = target_event.group_file_upload(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['user_id'])
            target_event.data.file.update(target_event.sdk_event.json['file'])
        elif target_event.sdk_event.json['notice_type'] == 'group_admin':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_admin'
            target_event.data = target_event.group_admin(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['user_id'])
            if target_event.sdk_event.json['sub_type'] == 'set':
                target_event.data.action = 'set'
        elif target_event.sdk_event.json['notice_type'] == 'group_decrease':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_member_decrease'
            target_event.data = target_event.group_member_decrease(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['operator_id'], target_event.sdk_event.json['user_id'])
            if target_event.sdk_event.json['sub_type'] == 'leave':
                target_event.data.action = 'leave'
            elif target_event.sdk_event.json['sub_type'] == 'kick':
                target_event.data.action = 'kick'
            elif target_event.sdk_event.json['sub_type'] == 'kick_me':
                target_event.data.action = 'kick_me'
        elif target_event.sdk_event.json['notice_type'] == 'group_increase':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_member_increase'
            target_event.data = target_event.group_member_increase(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['operator_id'], target_event.sdk_event.json['user_id'])
            if target_event.sdk_event.json['sub_type'] == 'approve':
                target_event.data.action = 'approve'
            elif target_event.sdk_event.json['sub_type'] == 'invite':
                target_event.data.action = 'invite'
        elif target_event.sdk_event.json['notice_type'] == 'group_ban':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_ban'
            target_event.data = target_event.group_ban(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['operator_id'], target_event.sdk_event.json['user_id'], target_event.sdk_event.json['duration'])
            if target_event.sdk_event.json['sub_type'] == 'ban':
                target_event.data.action = 'ban'
        elif target_event.sdk_event.json['notice_type'] == 'friend_add':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'friend_add'
            target_event.data = target_event.friend_add(target_event.sdk_event.json['user_id'])
            target_event.log_func(2, '[' + target_event.plugin_info['func_type'] + '] - QQ(' + str(target_event.data.user_id) + ')')
        elif target_event.sdk_event.json['notice_type'] == 'group_recall':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'group_message_recall'
            target_event.data = target_event.group_message_recall(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['operator_id'], target_event.sdk_event.json['user_id'], target_event.sdk_event.json['message_id'])
        elif target_event.sdk_event.json['notice_type'] == 'friend_recall':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'private_message_recall'
            target_event.data = target_event.private_message_recall(target_event.sdk_event.json['user_id'], target_event.sdk_event.json['message_id'])
        elif target_event.sdk_event.json['notice_type'] == 'notify':
            if target_event.sdk_event.json['sub_type'] == 'poke':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'poke'
                target_event.data = target_event.poke(target_event.sdk_event.json['user_id'], target_event.sdk_event.json['target_id'])
                if 'group_id' in target_event.sdk_event.json:
                    target_event.data.group_id = target_event.sdk_event.json['group_id']
            elif target_event.sdk_event.json['sub_type'] == 'lucky_king':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_lucky_king'
                target_event.data = target_event.group_lucky_king(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['user_id'], target_event.sdk_event.json['target_id'])
            elif target_event.sdk_event.json['sub_type'] == 'honor':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_honor'
                target_event.data = target_event.group_honor(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['user_id'])
                if target_event.sdk_event.json['honor_type'] == 'talkative':
                    target_event.data.type = 'talkative'
                elif target_event.sdk_event.json['honor_type'] == 'performer':
                    target_event.data.type = 'performer'
                elif target_event.sdk_event.json['honor_type'] == 'emotion':
                    target_event.data.type = 'emotion'
    elif target_event.base_info['type'] == 'request':
        if target_event.sdk_event.json['request_type'] == 'friend':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'friend_add_request'
            target_event.data = target_event.friend_add_request(target_event.sdk_event.json['user_id'], target_event.sdk_event.json['comment'])
            target_event.data.flag = target_event.sdk_event.json['flag']
        elif target_event.sdk_event.json['request_type'] == 'group':
            if target_event.sdk_event.json['sub_type'] == 'add':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_add_request'
                target_event.data = target_event.group_add_request(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['user_id'], target_event.sdk_event.json['comment'])
                target_event.data.flag = target_event.sdk_event.json['flag']
            elif target_event.sdk_event.json['sub_type'] == 'invite':
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_invite_request'
                target_event.data = target_event.group_invite_request(target_event.sdk_event.json['group_id'], target_event.sdk_event.json['user_id'], target_event.sdk_event.json['comment'])
                target_event.data.flag = target_event.sdk_event.json['flag']
    elif target_event.base_info['type'] == 'meta_event':
        if target_event.sdk_event.json['meta_event_type'] == 'lifecycle':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'lifecycle'
            target_event.data = target_event.lifecycle()
            if target_event.sdk_event.json['sub_type'] == 'enable':
                target_event.data.action = 'enable'
            elif target_event.sdk_event.json['sub_type'] == 'disable':
                target_event.data.action = 'disable'
            elif target_event.sdk_event.json['sub_type'] == 'connect':
                target_event.data.action = 'connect'
        elif target_event.sdk_event.json['meta_event_type'] == 'heartbeat':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'heartbeat'
            target_event.data = target_event.heartbeat(target_event.sdk_event.json['interval'])


#支持OlivOS API调用的方法实现
class event_action(object):
    def reply_private_msg(target_event, message):
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'private'
        this_msg.data.user_id = target_event.data.user_id
        this_msg.data.message = message
        this_msg.do_api()

    def reply_group_msg(target_event, message):
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'group'
        this_msg.data.group_id = target_event.data.group_id
        this_msg.data.message = message
        this_msg.do_api()

    def send_private_msg(target_event, user_id, message):
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'private'
        this_msg.data.user_id = user_id
        this_msg.data.message = message
        this_msg.do_api()

    def send_group_msg(target_event, group_id, message):
        this_msg = api.send_msg(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.message_type = 'group'
        this_msg.data.group_id = group_id
        this_msg.data.message = message
        this_msg.do_api()

#onebot协议标准api调用实现
class api(object):
    class send_private_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_private_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.user_id = -1
                self.message = ''
                self.auto_escape  = False


    class send_group_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_group_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.message = ''
                self.auto_escape  = False


    class send_group_forward_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_group_forward_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.messages = ''


    class send_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.message_type = ''
                self.user_id = -1
                self.group_id = -1
                self.message = ''
                self.auto_escape = False


    class delete_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'delete_msg'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.message_id = -1


    class get_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_msg'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.message_id = -1


    class get_forward_msg(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_forward_msg'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.id = -1


    class send_like(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'send_like'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.user_id = -1
                self.times = 1


    class set_group_kick(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_kick'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.rehect_add_request = False


    class set_group_ban(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_ban'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.duration = 1800


    class set_group_anonymous_ban(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_anonymous_ban'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.anonymous = None
                self.anonymous_flag = ''
                self.duration = 1800


    class set_group_whole_ban(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_whole_ban'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.enable = True


    class set_group_admin(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_admin'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.enable = True


    class set_group_anonymous(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_anonymous'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.enable = True


    class set_group_card(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_card'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.card = ''


    class set_group_name(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_name'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.group_name = ''


    class set_group_leave(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_leave'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.is_dismiss = False


    class set_group_special_title(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_special_title'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.special_title = None
                self.duration = -1


    class set_friend_add_request(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_friend_add_request'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.flag = ''
                self.approve = True
                self.remark = None


    class set_group_add_request(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_group_add_request'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.flag = ''
                self.sub_type = ''
                self.approve = True
                self.reason = None


    class get_login_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_login_info'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.default = None


    class get_stranger_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_stranger_info'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.user_id = -1
                self.no_cache = False


    class get_friend_list(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_friend_list'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.default = None


    class get_group_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_info'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.no_cache = False


    class get_group_list(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_list'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.default = None


    class get_group_member_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_member_info'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1
                self.user_id = -1
                self.no_cache = False


    class get_group_member_list(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_group_member_list'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.group_id = -1


    class get_cookies(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_cookies'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.domain = ''


    class get_csrf_token(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_csrf_token'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.default = None


    class get_credentails(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_credentails'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.domain = ''


    class get_record(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_record'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.file = ''
                self.out_format = ''


    class get_image(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_image'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.file = ''


    class can_send_image(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'can_send_image'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.default = None

        def yes(self):
            if type(self.res) is req.models.Response and self.res.status_code == 200:
                json_obj = json.loads(self.res.text)
                yes_tmp = json_obj['data']['yes']
                return yes_tmp


    class can_send_record(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'can_send_record'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.default = None

        def yes(self):
            if type(self.res) is req.models.Response and self.res.status_code == 200:
                json_obj = json.loads(self.res.text)
                yes_tmp = json_obj['data']['yes']
                return yes_tmp


    class get_status(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_status'
            self.res = None
    
        class data_T(object):
            def __init__(self):
                self.default = None


    class get_version_info(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'get_version_info'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None


    class set_restart(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'set_restart'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.delay = 0


    class clean_cache(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.node_ext = 'clean_cache'
            self.res = None

        class data_T(object):
            def __init__(self):
                self.default = None
