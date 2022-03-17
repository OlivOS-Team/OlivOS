# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/contentAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import OlivOS

from enum import Enum
import time

class api_result_error_template(object):
    class OlivOSTypeError(TypeError):
        def __init__(self, arg):
            TypeError.__init__(self, arg)

class api_result_data_template(object):
    class get_msg(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(
                {
                    'message_id': None,
                    'id': -1,
                    'sender': {
                        'id': -1,
                        'name': None
                    },
                    'time': -1,
                    'message': None,
                    'raw_message': None
                }
            )

    class get_login_info(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(
                {
                    'name': None,
                    'id': -1
                }
            )

    class get_user_info_strip(dict):
        def __init__(self):
            self.update(
                {
                    'name': None,
                    'id': -1
                }
            )

    class get_stranger_info(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(api_result_data_template.get_user_info_strip())

    class get_friend_list(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = []

    class get_group_info_strip(dict):
        def __init__(self):
            self.update(
                {
                    'name': None,
                    'id': -1,
                    'memo': None,
                    'max_member_count': 0
                }
            )

    class get_group_info(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(api_result_data_template.get_group_info_strip())

    class get_group_list(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = []

    class get_group_member_info_strip(dict):
        def __init__(self):
            self.update(
                {
                    'name': None,
                    'id': -1,
                    'user_id': -1,
                    'group_id': -1,
                    'times': {
                        'join_time': 0,
                        'last_sent_time': 0,
                        'shut_up_timestamp': 0
                    },
                    'role': None,
                    'card': None,
                    'title': None
                }
            )

    class get_group_member_info(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(api_result_data_template.get_group_member_info_strip())

    class get_group_member_list(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = []

    class can_send_image(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(
                {
                    'yes': False
                }
            )

        def yes(self):
            if self['data']['yes'] == True:
                return True
            return False

    class can_send_record(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(
                {
                    'yes': False
                }
            )

        def yes(self):
            if self['data']['yes'] == True:
                return True
            return False

    class get_status(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(
                {
                    'online': False,
                    'status': {
                        'packet_received': 0,
                        'packet_sent': 0,
                        'packet_lost': 0,
                        'message_received': 0,
                        'message_sent': 0,
                        'disconnect_times': 0,
                        'lost_times': 0,
                        'last_message_time': 0
                    }
                }
            )

    class get_version_info(dict):
        def __init__(self):
            self['active'] = False
            self['data'] = {}
            self['data'].update(
                {
                    'name': None,
                    'version_full': None,
                    'version': None,
                    'path': None,
                    'os': None
                }
            )

def get_Event_from_fake_SDK(target_event):
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = target_event.sdk_event.base_info['self_id']
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.bot_info.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.bot_info.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.bot_info.platform['model']
    target_event.bot_info = target_event.sdk_event.bot_info
    target_event.plugin_info['message_mode_rx'] = 'olivos_para'
    if target_event.platform['platform'] in OlivOS.messageAPI.dictMessageType:
        if target_event.platform['sdk'] in OlivOS.messageAPI.dictMessageType[target_event.platform['platform']]:
            if target_event.platform['model'] in OlivOS.messageAPI.dictMessageType[target_event.platform['platform']][target_event.platform['sdk']]:
                target_event.plugin_info['message_mode_rx'] = OlivOS.messageAPI.dictMessageType[target_event.platform['platform']][target_event.platform['sdk']][target_event.platform['model']]
    target_event.plugin_info['name'] = target_event.sdk_event.fakename
    if True:
        if target_event.sdk_event.data['type'] == 'fake_event':
            target_event.active = True
            target_event.plugin_info['func_type'] = 'fake_event'
            target_event.data = target_event.fake_event()

class fake_sdk_event(object):
    def __init__(self, bot_info, data = None, platform = None, fakename = 'unity'):
        self.fakename = fakename
        tmp_platform = {
            'sdk': 'fake',
            'platform': 'fake',
            'model': 'default'
        }
        tmp_data = {
            'type': 'fake_event'
        }
        if type(data) == dict:
            tmp_data.update(data)
        self.raw = self.event_dump(data)
        self.data = tmp_data
        self.platform = {}
        self.platform.update(tmp_platform)
        if type(platform) == dict:
            self.platform.update(platform)
        self.active = False
        self.bot_info = bot_info
        if self.bot_info != None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = self.bot_info.id
            self.base_info['post_type'] = None

    def event_dump(self, raw):
        try:
            res = str(raw)
        except:
            res = None
        return res
