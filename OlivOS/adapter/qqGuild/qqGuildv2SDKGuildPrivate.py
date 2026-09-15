# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqGuildv2SDKGuildPrivate.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   qqGuildv2 频道私信实现
'''

from .qqGuildv2SDKCommon import *

event_action = None
API = None

class event_action_guild_private(object):
    def send_guild_private_msg(
        target_event,
        user_id,
        source_guild_id,
        message,
        quote_msg_id=None
    ):
        """从频道上下文向指定用户主动发起私信。"""
        if user_id is None or str(user_id) == '':
            return event_action._make_local_result(
                'guild_private',
                user_id,
                'send',
                'user_id is required'
            )
        if source_guild_id is None or str(source_guild_id) == '':
            return event_action._make_local_result(
                'guild_private',
                user_id,
                'send',
                'source_guild_id is required'
            )
        dms_result = event_action.create_dms_session(
            target_event,
            user_id,
            source_guild_id
        )
        if not dms_result.get('active', False):
            dms_result['data']['chat_type'] = 'guild_private'
            dms_result['data']['chat_id'] = str(user_id)
            dms_result['data']['operation'] = 'send'
            return dms_result
        response_data = dms_result.get('data', {}).get('response', None)
        direct_guild_id = None
        if isinstance(response_data, dict):
            direct_guild_id = response_data.get('guild_id', None)
        if direct_guild_id is None or str(direct_guild_id) == '':
            return event_action._make_local_result(
                'guild_private',
                user_id,
                'send',
                'create dms session response has no guild_id'
            )
        return event_action.send_msg(
            target_event,
            direct_guild_id,
            message,
            flag_direct=True,
            quote_msg_id=quote_msg_id
        )

    def create_dms_session(target_event, recipient_id, source_guild_id):
        # 返回 data.response 中含 guild_id(私信会话凭据),可直接用于 send_msg 的 flag_direct 通道
        this_msg = API.createDirectMessageSession(get_SDK_bot_info_from_Event(target_event))
        this_msg.data.recipient_id = str(recipient_id)
        this_msg.data.source_guild_id = str(source_guild_id)
        return event_action._run_raw_api(this_msg, 'create_dms_session', 'POST')

class API_guild_private(object):
    # POST /users/@me/dms 创建私信会话
    class createDirectMessageSession(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['users_me'] + '/dms'

        class data_T(object):
            def __init__(self):
                self.recipient_id = None      # str 接收者 id
                self.source_guild_id = None   # str 源频道 id

    class sendDirectMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['dms'] + '/{guild_id}/messages'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.content = None     # str
                self.embed = None       # object
                self.ark = None         # object
                self.message_reference = None  # object
                self.image = None       # str
                self.file_image = None  # multipart file
                self.msg_id = None      # str
                self.event_id = None    # str
                self.markdown = None    # object
                self.keyboard = None    # object

        # 频道私信本地图片使用 multipart/form-data，其他消息沿用通用 JSON 请求
        def do_api(self, req_type='POST'):
            if self.data.file_image is None:
                return api_templet.do_api(self, req_type)
            msg_res = _send_channel_multipart(
                self.bot_info, self.metadata, self.data,
                self.host, self.port, self.route, req_type
            )
            if msg_res is None:
                self.res = None
                self.res_code = None
                return None
            self.res = msg_res.text
            self.res_code = msg_res.status_code
            return self.res

    class deleteDirectMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['dms'] + '/{guild_id}/messages/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.message_id = '-1'
