# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS\API.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import sys
import json
import multiprocessing

import OlivOS

OlivOS_Version = '0.0.1'
mod_global_name = sys.modules[__name__]


class Control(object):
    def __init__(self, name, init_list, control_queue, scan_interval):
        self.name = name
        self.init_list = init_list
        self.control_queue = control_queue
        self.scan_interval = scan_interval

    class packet(object):
        def __init__(self, action, key = None):
            self.action = action
            self.key = key

class bot_info_T(object):
    def __init__(self, id = -1, host = '', port = -1, access_token = None):
        self.id = id
        self.platform = None
        self.post_info = self.post_info_T(host, port, access_token)
        self.debug_mode = False

    class post_info_T(object):
        def __init__(self, host = '', port = -1, access_token = None):
            self.host = host
            self.port = port
            self.access_token = access_token


class Event(object):
    def __init__(self, sdk_event = None, log_func = None):
        self.bot_info = None
        self.platform = {}
        self.platform['sdk'] = None
        self.platform['platform'] = None
        self.platform['model'] = None
        self.data = None
        self.active = False
        self.log_func = log_func
        self.base_info = {}
        self.base_info['time'] = None
        self.base_info['self_id'] = None
        self.base_info['type'] = None
        self.plugin_info = {}
        self.plugin_info['func_type'] = None
        self.sdk_event = sdk_event
        self.sdk_event_type = type(self.sdk_event)
        self.get_Event_from_SDK()
        self.do_init_log()

    def get_Event_from_SDK(self):
        if self.sdk_event_type is OlivOS.onebotSDK.event:
            OlivOS.onebotSDK.get_Event_from_SDK(self)

    def do_init_log(self):
        if self.active:
            if self.plugin_info['func_type'] == 'private_message':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - QQ[' + self.data.sender['nickname'] + '](' + str(self.data.user_id) + ') : ' + self.data.message)
            elif self.plugin_info['func_type'] == 'group_message':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ[' + self.data.sender['nickname'] + '](' + str(self.data.user_id) + ') : ' + self.data.message)
            elif self.plugin_info['func_type'] == 'group_file_upload':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') : ' + self.data.file['name'])
            elif self.plugin_info['func_type'] == 'group_admin':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') Action(' +  self.data.action + ')')
            elif self.plugin_info['func_type'] == 'group_member_decrease':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') <- Operator(' +  str(self.data.operator_id) + ') Action(' + self.data.action + ')')
            elif self.plugin_info['func_type'] == 'group_member_increase':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') <- Operator(' +  str(self.data.operator_id) + ') Action(' + self.data.action + ')')
            elif self.plugin_info['func_type'] == 'group_ban':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') <- Operator(' +  str(self.data.operator_id) + ') Duration(' + str(self.data.duration) + ') Action(' + self.data.action + ')')
            elif self.plugin_info['func_type'] == 'group_message_recall':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') <- Operator(' +  str(self.data.operator_id) + ') Message_id(' + str(self.data.message_id) + ')')
            elif self.plugin_info['func_type'] == 'private_message_recall':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - QQ(' + str(self.data.user_id) + ') Message_id(' + str(self.data.message_id) + ')')
            elif self.plugin_info['func_type'] == 'poke':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') -> Target(' +  str(self.data.target_id) + ')')
            elif self.plugin_info['func_type'] == 'group_lucky_king':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') -> Target(' +  str(self.data.target_id) + ')')
            elif self.plugin_info['func_type'] == 'group_honor':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') Type(' + str(self.data.type) + ')')
            elif self.plugin_info['func_type'] == 'friend_add_request':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - QQ(' + str(self.data.user_id) + ') Flag(' + str(self.data.flag) + ') : ' + self.sdk_event.json['comment'])
            elif self.plugin_info['func_type'] == 'group_add_request':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') Flag(' + str(self.data.flag) + ') : ' + self.sdk_event.json['comment'])
            elif self.plugin_info['func_type'] == 'group_invite_request':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Group(' + str(self.data.group_id) + ') QQ(' + str(self.data.user_id) + ') Flag(' + str(self.data.flag) + ') : ' + self.sdk_event.json['comment'])
            elif self.plugin_info['func_type'] == 'lifecycle':
                self.log_func(2, '[' + self.plugin_info['func_type'] + '] - Action(' + str(self.data.action) + ')')
            elif self.plugin_info['func_type'] == 'heartbeat':
                self.log_func(1, '[' + self.plugin_info['func_type'] + '] - Interval(' + str(self.data.interval) + ')')

    class private_message(object):
        def __init__(self, user_id, message, sub_type, flag_lazy = True):
            self.sub_type = sub_type
            self.message = message
            self.message_id = None
            self.raw_message = None
            self.user_id = user_id
            self.font = None
            self.sender = {}
            if flag_lazy:
                self.sender['nickname'] = 'Nobody'

    class group_message(object):
        def __init__(self, group_id, user_id, message, sub_type, flag_lazy = True):
            self.sub_type = sub_type
            self.group_id = group_id
            self.message = message
            self.message_id = None
            self.raw_message = None
            self.user_id = user_id
            self.font = None
            self.sender = {}
            if flag_lazy:
                self.sender['nickname'] = 'Nobody'

    class group_file_upload(object):
        def __init__(self, group_id, user_id, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.file = {}
            if flag_lazy:
                self.file['id'] = 'Nofileid'
                self.file['name'] = 'Nofile'
                self.file['size'] = 0
                self.file['busid'] = -1

    class group_admin(object):
        def __init__(self, group_id, user_id, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.action = 'unset'

    class group_member_decrease(object):
        def __init__(self, group_id, operator_id, user_id, action = 'leave', flag_lazy = True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.action = action

    class group_member_increase(object):
        def __init__(self, group_id, operator_id, user_id, action = 'approve', flag_lazy = True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.action = action

    class group_ban(object):
        def __init__(self, group_id, operator_id, user_id, duration, action = 'unban', flag_lazy = True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.duration = duration
            self.action = action

    class friend_add(object):
        def __init__(self, user_id, flag_lazy = True):
            self.user_id = user_id

    class group_message_recall(object):
        def __init__(self, group_id, operator_id, user_id, message_id, flag_lazy = True):
            self.group_id = group_id
            self.operator_id = operator_id
            self.user_id = user_id
            self.message_id = message_id

    class private_message_recall(object):
        def __init__(self, user_id, message_id, flag_lazy = True):
            self.user_id = user_id
            self.message_id = message_id

    class poke(object):
        def __init__(self, user_id, target_id, group_id = -1, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.target_id = target_id

    class group_lucky_king(object):
        def __init__(self, group_id, user_id, target_id, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.target_id = target_id

    class group_honor(object):
        def __init__(self, group_id, user_id, flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.type = None

    class friend_add_request(object):
        def __init__(self, user_id, comment = '', flag_lazy = True):
            self.user_id = user_id
            self.comment = comment
            self.flag = None

    class group_add_request(object):
        def __init__(self, group_id, user_id, comment = '', flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.comment = comment
            self.flag = None

    class group_invite_request(object):
        def __init__(self, group_id, user_id, comment = '', flag_lazy = True):
            self.group_id = group_id
            self.user_id = user_id
            self.comment = comment
            self.flag = None

    class lifecycle(object):
        def __init__(self, action = None, flag_lazy = True):
            self.action = action

    class heartbeat(object):
        def __init__(self, interval, flag_lazy = True):
            self.interval = interval

    #以下为统一事件动作调用方法实现，各接入sdk需完全支持

    def reply(self, message, flag_log = True):
        flag_type = None
        if self.plugin_info['func_type'] == 'private_message':
            self.send('private', self.data.user_id, message, flag_log = False)
            flag_type = 'private'
        elif self.plugin_info['func_type'] == 'group_message':
            self.send('group', self.data.group_id, message, flag_log = False)
            flag_type = 'group'
        elif self.plugin_info['func_type'] == 'poke':
            if self.data.group_id == -1:
                self.send('private', self.data.user_id, message, flag_log = False)
                flag_type = 'private'
            else:
                self.send('group', self.data.group_id, message, flag_log = False)
                flag_type = 'group'

        if flag_log:
            if flag_type == 'private':
                self.log_func(2, '<reply> - QQ(' + str(self.data.user_id) + '): ' + message)
            elif flag_type == 'group':
                self.log_func(2, '<reply> - Group(' + str(self.data.group_id) + '): ' + message)

    def send(self, send_type, target_id, message, flag_log = True):
        flag_type = send_type
        if self.platform['sdk'] == 'onebot':
            if flag_type == 'private':
                OlivOS.onebotSDK.event_action.send_private_msg(self, target_id, message)
            elif flag_type == 'group':
                OlivOS.onebotSDK.event_action.send_group_msg(self, target_id, message)

        if flag_log:
            if flag_type == 'private':
                self.log_func(2, '<send> - QQ(' + str(self.data.user_id) + '): ' + message)
            elif flag_type == 'group':
                self.log_func(2, '<send> - Group(' + str(self.data.group_id) + '): ' + message)


class Proc_templet(object):
    def __init__(self, Proc_name = 'native_plugin', Proc_type = 'default', scan_interval = 0.001, rx_queue = None, tx_queue = None, control_queue = None, logger_proc = None):
        self.deamon = True
        self.Proc = None
        self.Proc_name = Proc_name
        self.Proc_type = Proc_type
        self.Proc_info = self.Proc_info_T(
            rx_queue = rx_queue,
            tx_queue = tx_queue,
            control_queue = control_queue,
            logger_proc = logger_proc,
            scan_interval = scan_interval)
        self.Proc_config = {}
        self.Proc_data = {}

    class Proc_info_T(object):
        def __init__(self, rx_queue, tx_queue, control_queue, logger_proc, scan_interval = 0.001):
            self.rx_queue = rx_queue
            self.tx_queue = tx_queue
            self.control_queue = control_queue
            self.logger_proc = logger_proc
            self.scan_interval = scan_interval

    def run(self):
        pass

    def start(self):
        proc_this = multiprocessing.Process(name = self.Proc_name, target = self.run, args = ())
        proc_this.daemon = self.deamon
        proc_this.start()
        self.Proc = proc_this
        return self.Proc

    def log(self, log_level, log_message):
        if self.Proc_info.logger_proc != None:
            self.Proc_info.logger_proc.log(log_level, log_message)

#兼容Win平台的进程生成方法
def Proc_start(proc_this):
    proc_proc_this = multiprocessing.Process(name = proc_this.Proc_name, target = proc_this.run, args = ())
    proc_proc_this.daemon = proc_this.deamon
    #multiprocessing.Process无法进行弱引用序列化烘培，故无法在Win平台下实现自动更新进程引用
    #proc_this.Proc = proc_proc_this
    proc_proc_this.start()
    return proc_proc_this

class Proc_info_T(object):
    def __init__(self, rx_queue, tx_queue, logger_proc, scan_interval = 0.001):
        self.rx_queue = rx_queue
        self.tx_queue = tx_queue
        self.logger_proc = logger_proc
        self.scan_interval = scan_interval


class PARA_templet(object):
    def __init__(self, type = None, data = None):
        self.type = type
        self.data = data

    def CQ(self):
        CQ_tmp = '[CQ:' + self.type
        if self.data != None:
            for key_this in self.data:
                if self.data[key_this] != None:
                    CQ_tmp += ',' + key_this + '=' + str(self.data[key_this])
        CQ_tmp += ']'
        return CQ_tmp

    def PARA(self):
        PARA_tmp = self.cut()
        if self.data == None:
            PARA_tmp.data = dict()
        return json.dumps(obj = PARA_tmp.__dict__)

    def copy(self):
        copy_tmp = PARA_templet(self.type, self.data.copy())
        return copy_tmp

    def cut(self):
        copy_tmp = self.copy()
        if copy_tmp.data != None:
            for key_this in self.data:
                if copy_tmp.data[key_this] == None:
                    del copy_tmp.data[key_this]
                else:
                    copy_tmp.data[key_this] = str(copy_tmp.data[key_this])
        return copy_tmp

class PARA(object):
    class text(PARA_templet):
        def __init__(self, text = ''):
            PARA_templet.__init__(self, 'text', self.data_T(text))

        class data_T(dict):
            def __init__(self, text = ''):
                self['text'] = text

        def CQ(self):
            if self.data != None:
                if type(self.data.text) is str:
                    return self.data.text
                else:
                    return str(self.data.text)
            else:
                return ''

    class face(PARA_templet):
        def __init__(self, id):
            PARA_templet.__init__(self, 'face', self.data_T(id))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id

    class image(PARA_templet):
        def __init__(self, file, type = None, url = None, cache = None, proxy = None, timeout = None):
            PARA_templet.__init__(self, 'image', self.data_T(file, type, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, type, url, cache, proxy, timeout):
                self['file'] = file
                self['type'] = type
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

    class record(PARA_templet):
        def __init__(self, file, magic = None, url = None, cache = None, proxy = None, timeout = None):
            PARA_templet.__init__(self, 'record', self.data_T(file, type, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, magic, url, cache, proxy, timeout):
                self['file'] = file
                self['magic'] = magic
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

    class video(PARA_templet):
        def __init__(self, file, url = None, cache = None, proxy = None, timeout = None):
            PARA_templet.__init__(self, 'record', self.data_T(file, type, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, url, cache, proxy, timeout):
                self['file'] = file
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

    class at(PARA_templet):
        def __init__(self, qq):
            PARA_templet.__init__(self, 'at', self.data_T(qq))

        class data_T(dict):
            def __init__(self, qq):
                self['qq'] = qq

    class rps(PARA_templet):
        def __init__(self):
            PARA_templet.__init__(self, 'rps', None)

    class dice(PARA_templet):
        def __init__(self):
            PARA_templet.__init__(self, 'dice', None)

    class shake(PARA_templet):
        def __init__(self):
            PARA_templet.__init__(self, 'shake', None)

    class poke(PARA_templet):
        def __init__(self, type, id, name = None):
            PARA_templet.__init__(self, 'poke', self.data_T(type, id, name))

        class data_T(dict):
            def __init__(self, type, id, name):
                self['type'] = type
                self['id'] = id
                self['name'] = name

    class anonymous(PARA_templet):
        def __init__(self):
            PARA_templet.__init__(self, 'shake', None)

    class share(PARA_templet):
        def __init__(self, url, title, content = None, image = None):
            PARA_templet.__init__(self, 'share', self.data_T(url, title, content, image))

        class data_T(dict):
            def __init__(self, url, title, content, image):
                self['url'] = url
                self['title'] = title
                self['content'] = content
                self['image'] = image

    class contact(PARA_templet):
        def __init__(self, type, id):
            PARA_templet.__init__(self, 'contact', self.data_T(type, id))

        class data_T(dict):
            def __init__(self, type, id):
                self['type'] = type
                self['id'] = id

    class location(PARA_templet):
        def __init__(self, lat, lon, title = None, content = None):
            PARA_templet.__init__(self, 'location', self.data_T(lat, lon, title, content))

        class data_T(dict):
            def __init__(self, lat, lon, title, content):
                self['lat'] = lat
                self['lon'] = lon
                self['title'] = title
                self['content'] = content

    class music(PARA_templet):
        def __init__(self, type, id = None, url = None, audio = None, title = None, content = None, image = None):
            PARA_templet.__init__(self, 'music', self.data_T(type, id, url, audio, title, content, image))

        class data_T(dict):
            def __init__(self, type, id, url, audio, title, content, image):
                self['type'] = type
                self['id'] = id
                self['url'] = url
                self['audio'] = audio
                self['title'] = title
                self['content'] = content
                self['image'] = image

    class reply(PARA_templet):
        def __init__(self, id):
            PARA_templet.__init__(self, 'reply', self.data_T(id))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id

    class forward(PARA_templet):
        def __init__(self, id):
            PARA_templet.__init__(self, 'forward', self.data_T(id))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id

    class node(PARA_templet):
        def __init__(self, id = None, user_id = None, nickname = None, content = None):
            PARA_templet.__init__(self, 'node', self.data_T(id, user_id, nickname, content))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id
                self['user_id'] = user_id
                self['nickname'] = nickname
                self['content'] = content