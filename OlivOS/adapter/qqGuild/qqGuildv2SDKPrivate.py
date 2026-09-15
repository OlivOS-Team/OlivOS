# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqGuildv2SDKPrivate.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   qqGuildv2 QQ 单聊实现
'''

from .qqGuildv2SDKCommon import *

event_action = None
API = None

class event_action_private(object):
    def upload_private_file(target_event, user_id, file, name):
        context_error = event_action._get_qq_upload_context_error(
            target_event,
            flag_direct=True
        )
        if context_error is not None:
            return event_action._make_local_result(
                'qq_private', user_id, 'upload_private_file', context_error
            )
        file_info = event_action.setResourceUploadFast(
            target_event,
            file,
            user_id,
            type_path='files',
            type_chat='qq_users',
            file_name=name,
            flag_send_msg=True
        )
        return event_action._make_resource_upload_result(
            'qq_private', user_id, file_info, 'upload_private_file'
        )

class API_private(object):
    class sendQQDirectMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_users'] + '/{openid}/messages'

        class metadata_T(object):
            def __init__(self):
                self.openid = '-1'

        class data_T(object):
            def __init__(self):
                self.content = None     # str
                self.msg_type = 0       # int
                self.markdown = None    # object
                self.keyboard = None    # object
                self.ark = None         # object
                self.embed = None       # object
                self.media = None       # object
                self.message_reference = None  # object
                self.event_id = None    # str
                self.msg_id = None      # str
                self.msg_seq = None
                self.is_wakeup = None   # bool

    class deleteQQDirectMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_users'] + '/{openid}/messages/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.openid = '-1'
                self.message_id = '-1'
