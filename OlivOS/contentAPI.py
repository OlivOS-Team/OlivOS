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
