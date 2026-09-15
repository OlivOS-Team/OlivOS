# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqGuildv2SDKGuild.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   qqGuildv2 频道（文字子频道）实现
'''

from .qqGuildv2SDKCommon import *

event_action = None
API = None

class event_action_guild(object):
    def _normalize_guild_markdown(markdown, allow_at_all=True):
        markdown_obj = copy.deepcopy(markdown)
        if isinstance(markdown_obj.get('content', None), str):
            markdown_obj['content'] = markdown_tag.normalize_guild_text(
                markdown_obj['content'],
                allow_at_all=allow_at_all
            )
        params = markdown_obj.get('params', None)
        if isinstance(params, list):
            for param in params:
                if not isinstance(param, dict) or not isinstance(param.get('values', None), list):
                    continue
                param['values'] = [
                    markdown_tag.normalize_guild_text(value, allow_at_all=allow_at_all)
                    if isinstance(value, str)
                    else value
                    for value in param['values']
                ]
        return markdown_obj

    def send_msg(
        target_event,
        chat_id,
        message,
        reply_msg_id=None,
        flag_direct=False,
        quote_msg_id=None
    ):
        # 频道图片沿用 QQ 图文的双向分组规则。
        chat_type = 'guild_private' if flag_direct else 'guild_channel'
        if chat_id is None or str(chat_id) == '':
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'chat_id is required'
            )
        send_results = []
        if quote_msg_id is None:
            quote_msg_id = event_action._get_message_reference_id(message)

        def send_payload(text_content, image_data=None):
            nonlocal quote_msg_id
            result = event_action._send_channel_payload(
                target_event,
                chat_id,
                text_content,
                reply_msg_id,
                flag_direct=flag_direct,
                image_data=image_data,
                quote_msg_id=quote_msg_id
            )
            send_results.append(result)
            if result.get('active', False):
                quote_msg_id = None
            return result

        for text_content, message_this in event_action._get_message_send_chunks(
            message,
            [OlivOS.messageAPI.PARA.image],
            allow_at_all=not flag_direct,
            flag_qq=False
        ):
            if message_this is None:
                result = send_payload(text_content)
                if not result.get('active', False):
                    return event_action._merge_send_results(
                        chat_type,
                        chat_id,
                        send_results
                    )
                continue
            resource_url = event_action._get_message_resource(message_this)
            if resource_url is None:
                send_results.append(event_action._make_local_result(
                    chat_type,
                    chat_id,
                    'send',
                    'message resource is empty'
                ))
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
            image_data = event_action._get_channel_image_data(resource_url)
            if image_data is None:
                send_results.append(event_action._make_local_result(
                    chat_type,
                    chat_id,
                    'send',
                    'message resource load failed'
                ))
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
            result = send_payload(text_content, image_data=image_data)
            if not result.get('active', False):
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
        return event_action._merge_send_results(chat_type, chat_id, send_results)

    def _send_channel_payload(
        target_event,
        chat_id,
        content,
        msg_id,
        flag_direct=False,
        image_data=None,
        quote_msg_id=None
    ):
        chat_type = 'guild_private' if flag_direct else 'guild_channel'
        if flag_direct:
            this_msg = API.sendDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.guild_id = str(chat_id)
        else:
            this_msg = API.sendMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.channel_id = str(chat_id)
        this_msg.data.content = content
        this_msg.data.msg_id = None if msg_id is None else str(msg_id)
        if quote_msg_id is not None and str(quote_msg_id) != '':
            this_msg.data.message_reference = {'message_id': str(quote_msg_id)}
        if type(image_data) is dict:
            if image_data.get('image', None) is not None:
                this_msg.data.image = image_data['image']
            elif image_data.get('file_image', None) is not None:
                this_msg.data.file_image = image_data['file_image']
        this_msg.do_api()
        return event_action._make_api_result(
            target_event,
            this_msg,
            chat_type,
            chat_id,
            'send'
        )

    # ============ 频道:频道/子频道 ============
    def get_guild_info(target_event, guild_id):
        this_msg = API.getGuild(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        return event_action._run_raw_api(this_msg, 'get_guild_info', 'GET')

    def get_me_guild_list(target_event, before=None, after=None, limit=None):
        this_msg = API.getMeGuilds(get_SDK_bot_info_from_Event(target_event))
        this_msg.query = {'before': before, 'after': after, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_me_guild_list', 'GET')

    def get_guild_channel_list(target_event, guild_id):
        this_msg = API.getGuildChannels(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        return event_action._run_raw_api(this_msg, 'get_guild_channel_list', 'GET')

    def get_channel_info(target_event, channel_id):
        this_msg = API.getChannel(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'get_channel_info', 'GET')

    def get_guild_info_standard(target_event, guild_id):
        return event_action._standard_group_info(
            event_action.get_guild_info(target_event, guild_id),
            fallback_id=guild_id
        )

    def get_guild_list_standard(target_event, before=None, after=None, limit=None):
        return event_action._standard_group_list(
            event_action.get_me_guild_list(target_event, before, after, limit)
        )

    def get_guild_channel_list_standard(target_event, guild_id):
        return event_action._standard_group_list(
            event_action.get_guild_channel_list(target_event, guild_id)
        )

    def get_channel_info_standard(target_event, channel_id):
        return event_action._standard_group_info(
            event_action.get_channel_info(target_event, channel_id),
            fallback_id=channel_id
        )

    def get_guild_member_list_standard(target_event, guild_id, after=None, limit=None):
        return event_action._standard_group_member_list(
            event_action.get_guild_member_list(target_event, guild_id, after, limit),
            fallback_group_id=guild_id
        )

    def create_channel(target_event, guild_id, name, type=None, sub_type=None,
                       position=None, parent_id=None, private_type=None,
                       private_user_ids=None, speak_permission=None, application_id=None):
        this_msg = API.createChannel(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.name = str(name)
        this_msg.data.type = type
        this_msg.data.sub_type = sub_type
        this_msg.data.position = position
        this_msg.data.parent_id = parent_id
        this_msg.data.private_type = private_type
        this_msg.data.private_user_ids = private_user_ids
        this_msg.data.speak_permission = speak_permission
        this_msg.data.application_id = application_id
        return event_action._run_raw_api(this_msg, 'create_channel', 'POST')

    def patch_channel(target_event, channel_id, name=None, position=None,
                      parent_id=None, private_type=None, speak_permission=None):
        this_msg = API.patchChannel(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.data.name = name
        this_msg.data.position = position
        this_msg.data.parent_id = parent_id
        this_msg.data.private_type = private_type
        this_msg.data.speak_permission = speak_permission
        return event_action._run_raw_api(this_msg, 'patch_channel', 'PATCH')

    def delete_channel(target_event, channel_id):
        this_msg = API.deleteChannel(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'delete_channel', 'DELETE')

    def get_channel_online_nums(target_event, channel_id):
        this_msg = API.getChannelOnlineNums(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'get_channel_online_nums', 'GET')

    # ============ 频道:成员 ============
    def get_guild_member_list(target_event, guild_id, after=None, limit=None):
        this_msg = API.getGuildMembers(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.query = {'after': after, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_guild_member_list', 'GET')

    def get_guild_role_member_list(target_event, guild_id, role_id, start_index=None, limit=None):
        this_msg = API.getGuildRoleMembers(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.role_id = str(role_id)
        this_msg.query = {'start_index': start_index, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_guild_role_member_list', 'GET')

    def get_guild_member_info(target_event, guild_id, user_id):
        this_msg = API.getGuildMember(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        return event_action._run_raw_api(this_msg, 'get_guild_member_info', 'GET')

    def delete_guild_member(target_event, guild_id, user_id,
                            add_blacklist=None, delete_history_msg_days=None):
        this_msg = API.deleteGuildMember(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.data.add_blacklist = add_blacklist
        this_msg.data.delete_history_msg_days = delete_history_msg_days
        return event_action._run_raw_api(this_msg, 'delete_guild_member', 'DELETE')

    # ============ 频道:身份组 ============
    def get_guild_role_list(target_event, guild_id):
        this_msg = API.getGuildRoles(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        return event_action._run_raw_api(this_msg, 'get_guild_role_list', 'GET')

    def create_guild_role(target_event, guild_id, name=None, color=None, hoist=None):
        this_msg = API.createGuildRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.name = name
        this_msg.data.color = color
        this_msg.data.hoist = hoist
        return event_action._run_raw_api(this_msg, 'create_guild_role', 'POST')

    def patch_guild_role(target_event, guild_id, role_id, name=None, color=None, hoist=None):
        this_msg = API.patchGuildRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.role_id = str(role_id)
        this_msg.data.name = name
        this_msg.data.color = color
        this_msg.data.hoist = hoist
        return event_action._run_raw_api(this_msg, 'patch_guild_role', 'PATCH')

    def delete_guild_role(target_event, guild_id, role_id):
        this_msg = API.deleteGuildRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.role_id = str(role_id)
        return event_action._run_raw_api(this_msg, 'delete_guild_role', 'DELETE')

    def set_guild_member_role(target_event, guild_id, user_id, role_id, channel_id=None):
        # 操作 5 号(子频道管理员)身份组时必须传 channel_id
        this_msg = API.putGuildMemberRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.metadata.role_id = str(role_id)
        if channel_id is not None:
            this_msg.data.channel = {'id': str(channel_id)}
        return event_action._run_raw_api(this_msg, 'set_guild_member_role', 'PUT')

    def unset_guild_member_role(target_event, guild_id, user_id, role_id, channel_id=None):
        this_msg = API.deleteGuildMemberRole(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.metadata.role_id = str(role_id)
        if channel_id is not None:
            this_msg.data.channel = {'id': str(channel_id)}
        return event_action._run_raw_api(this_msg, 'unset_guild_member_role', 'DELETE')

    # ============ 频道:子频道权限 ============
    def get_channel_member_permissions(target_event, channel_id, user_id):
        this_msg = API.getChannelMemberPermissions(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.user_id = str(user_id)
        return event_action._run_raw_api(this_msg, 'get_channel_member_permissions', 'GET')

    def set_channel_member_permissions(target_event, channel_id, user_id, add=None, remove=None):
        this_msg = API.putChannelMemberPermissions(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.data.add = None if add is None else str(add)
        this_msg.data.remove = None if remove is None else str(remove)
        return event_action._run_raw_api(this_msg, 'set_channel_member_permissions', 'PUT')

    def get_channel_role_permissions(target_event, channel_id, role_id):
        this_msg = API.getChannelRolePermissions(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.role_id = str(role_id)
        return event_action._run_raw_api(this_msg, 'get_channel_role_permissions', 'GET')

    def set_channel_role_permissions(target_event, channel_id, role_id, add=None, remove=None):
        this_msg = API.putChannelRolePermissions(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.role_id = str(role_id)
        this_msg.data.add = None if add is None else str(add)
        this_msg.data.remove = None if remove is None else str(remove)
        return event_action._run_raw_api(this_msg, 'set_channel_role_permissions', 'PUT')

    # ============ 频道:消息列表/私信会话 ============
    def get_channel_message_list(target_event, channel_id, around=None, before=None, after=None, limit=None):
        this_msg = API.getChannelMessages(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.query = {'around': around, 'before': before, 'after': after, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_channel_message_list', 'GET')

    # ============ 频道:禁言 ============
    def set_guild_mute_all(target_event, guild_id, mute_seconds=None, mute_end_timestamp=None):
        # mute_seconds='0' 或 mute_end_timestamp='0' 表示解除全员禁言
        this_msg = API.patchGuildMute(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.mute_seconds = None if mute_seconds is None else str(mute_seconds)
        this_msg.data.mute_end_timestamp = None if mute_end_timestamp is None else str(mute_end_timestamp)
        return event_action._run_raw_api(this_msg, 'set_guild_mute_all', 'PATCH')

    def set_guild_members_mute(target_event, guild_id, user_ids, mute_seconds=None, mute_end_timestamp=None):
        # 批量成员禁言;成功时 data.response.user_ids 为生效的成员列表
        this_msg = API.patchGuildMute(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.user_ids = [str(user_id) for user_id in user_ids]
        this_msg.data.mute_seconds = None if mute_seconds is None else str(mute_seconds)
        this_msg.data.mute_end_timestamp = None if mute_end_timestamp is None else str(mute_end_timestamp)
        return event_action._run_raw_api(this_msg, 'set_guild_members_mute', 'PATCH')

    def set_guild_member_mute(target_event, guild_id, user_id, mute_seconds=None, mute_end_timestamp=None):
        this_msg = API.patchGuildMemberMute(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.user_id = str(user_id)
        this_msg.data.mute_seconds = None if mute_seconds is None else str(mute_seconds)
        this_msg.data.mute_end_timestamp = None if mute_end_timestamp is None else str(mute_end_timestamp)
        return event_action._run_raw_api(this_msg, 'set_guild_member_mute', 'PATCH')

    # ============ 频道:公告/精华 ============
    def create_guild_announce(target_event, guild_id, message_id=None, channel_id=None,
                              announces_type=None, recommend_channels=None):
        this_msg = API.createAnnounce(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.message_id = message_id
        this_msg.data.channel_id = channel_id
        this_msg.data.announces_type = announces_type
        this_msg.data.recommend_channels = recommend_channels
        return event_action._run_raw_api(this_msg, 'create_guild_announce', 'POST')

    def delete_guild_announce(target_event, guild_id, message_id='all'):
        this_msg = API.deleteAnnounce(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.metadata.message_id = str(message_id)
        return event_action._run_raw_api(this_msg, 'delete_guild_announce', 'DELETE')

    def set_pins_message(target_event, channel_id, message_id):
        this_msg = API.putPinsMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        return event_action._run_raw_api(this_msg, 'set_pins_message', 'PUT')

    def delete_pins_message(target_event, channel_id, message_id='all'):
        this_msg = API.deletePinsMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        return event_action._run_raw_api(this_msg, 'delete_pins_message', 'DELETE')

    def get_pins_message(target_event, channel_id):
        this_msg = API.getPinsMessage(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'get_pins_message', 'GET')

    def get_essence_msg_list(target_event, channel_id):
        res_data = OlivOS.contentAPI.api_result_data_template.get_essence_msg_list()
        raw_result = event_action.get_pins_message(target_event, channel_id)
        if not raw_result.get('active', False):
            return res_data
        raw_response = raw_result.get('data', {}).get('response', None)
        if not isinstance(raw_response, dict):
            return res_data
        message_ids = raw_response.get('message_ids', None)
        if not isinstance(message_ids, list):
            return res_data
        response_channel_id = raw_response.get('channel_id', channel_id)
        res_data['active'] = True
        for message_id in message_ids:
            res_data['data'].append({
                'sender_id': None,
                'sender_nick': None,
                'sender_time': None,
                'operator_id': None,
                'operator_nick': None,
                'operator_time': None,
                'message_id': str(message_id),
                'message': None,
                'wording': None,
                'extra': {
                    'channel_id': None if response_channel_id is None else str(response_channel_id),
                    'qq_response': copy.deepcopy(raw_response)
                }
            })
        return res_data

    # ============ 频道:日程 ============
    def get_schedule_list(target_event, channel_id, since=None):
        this_msg = API.getSchedules(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.query = {'since': since}
        return event_action._run_raw_api(this_msg, 'get_schedule_list', 'GET')

    def get_schedule_info(target_event, channel_id, schedule_id):
        this_msg = API.getSchedule(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.schedule_id = str(schedule_id)
        return event_action._run_raw_api(this_msg, 'get_schedule_info', 'GET')

    def create_schedule(target_event, channel_id, schedule):
        # schedule: dict,Schedule 对象(不含 id),字段见官方文档
        this_msg = API.createSchedule(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.data.schedule = schedule
        return event_action._run_raw_api(this_msg, 'create_schedule', 'POST')

    def patch_schedule(target_event, channel_id, schedule_id, schedule):
        this_msg = API.patchSchedule(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.schedule_id = str(schedule_id)
        this_msg.data.schedule = schedule
        return event_action._run_raw_api(this_msg, 'patch_schedule', 'PATCH')

    def delete_schedule(target_event, channel_id, schedule_id):
        this_msg = API.deleteSchedule(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.schedule_id = str(schedule_id)
        return event_action._run_raw_api(this_msg, 'delete_schedule', 'DELETE')

    # ============ 频道:表情表态 ============
    def set_message_reaction(target_event, channel_id, message_id, emoji_id, emoji_type=1):
        # emoji_type: 1系统表情 2emoji;emoji_id 见官方表情对照表
        this_msg = API.putMessageReaction(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        this_msg.metadata.emoji_type = str(emoji_type)
        this_msg.metadata.emoji_id = str(emoji_id)
        return event_action._run_raw_api(this_msg, 'set_message_reaction', 'PUT')

    def delete_message_reaction(target_event, channel_id, message_id, emoji_id, emoji_type=1):
        this_msg = API.deleteMessageReaction(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        this_msg.metadata.emoji_type = str(emoji_type)
        this_msg.metadata.emoji_id = str(emoji_id)
        return event_action._run_raw_api(this_msg, 'delete_message_reaction', 'DELETE')

    def get_message_reaction_user_list(target_event, channel_id, message_id, emoji_id,
                                       emoji_type=1, cookie=None, limit=None):
        this_msg = API.getMessageReactionUsers(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.message_id = str(message_id)
        this_msg.metadata.emoji_type = str(emoji_type)
        this_msg.metadata.emoji_id = str(emoji_id)
        this_msg.query = {'cookie': cookie, 'limit': limit}
        return event_action._run_raw_api(this_msg, 'get_message_reaction_user_list', 'GET')

    # ============ 频道:音频/麦克风 ============
    def set_audio_control(target_event, channel_id, status, audio_url=None, text=None):
        # status: 0开始 1暂停 2继续 3停止
        this_msg = API.postAudioControl(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.data.status = int(status)
        this_msg.data.audio_url = audio_url
        this_msg.data.text = text
        return event_action._run_raw_api(this_msg, 'set_audio_control', 'POST')

    def set_mic_on(target_event, channel_id):
        this_msg = API.putMic(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'set_mic_on', 'PUT')

    def set_mic_off(target_event, channel_id):
        this_msg = API.deleteMic(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'set_mic_off', 'DELETE')

    # ============ 频道:帖子(论坛,私域) ============
    def get_thread_list(target_event, channel_id):
        this_msg = API.getThreads(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        return event_action._run_raw_api(this_msg, 'get_thread_list', 'GET')

    def get_thread_info(target_event, channel_id, thread_id):
        this_msg = API.getThread(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.thread_id = str(thread_id)
        return event_action._run_raw_api(this_msg, 'get_thread_info', 'GET')

    def create_thread(target_event, channel_id, title, content, format=1):
        # format: 1文本 2HTML 3Markdown 4JSON
        this_msg = API.putThread(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.data.title = str(title)
        this_msg.data.content = str(content)
        this_msg.data.format = int(format)
        return event_action._run_raw_api(this_msg, 'create_thread', 'PUT')

    def delete_thread(target_event, channel_id, thread_id):
        this_msg = API.deleteThread(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.channel_id = str(channel_id)
        this_msg.metadata.thread_id = str(thread_id)
        return event_action._run_raw_api(this_msg, 'delete_thread', 'DELETE')

    # ============ 频道:API 权限 ============
    def get_guild_api_permission(target_event, guild_id):
        this_msg = API.getGuildApiPermission(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        return event_action._run_raw_api(this_msg, 'get_guild_api_permission', 'GET')

    def demand_guild_api_permission(target_event, guild_id, channel_id, api_path, api_method, desc=''):
        this_msg = API.demandGuildApiPermission(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.guild_id = str(guild_id)
        this_msg.data.channel_id = str(channel_id)
        this_msg.data.api_identify = {'path': str(api_path), 'method': str(api_method)}
        this_msg.data.desc = str(desc)
        return event_action._run_raw_api(this_msg, 'demand_guild_api_permission', 'POST')

class API_guild(object):
    # 获取指定消息(仅频道):GET /channels/{channel_id}/messages/{message_id}
    class getMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/messages/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'

    # ============ 频道模块:频道/子频道 ============
    # GET /guilds/{guild_id} 获取频道详情
    class getGuild(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # GET /users/@me/guilds 获取机器人加入的频道列表(query: before/after/limit)
    class getMeGuilds(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['users_me'] + '/guilds'

    # GET /guilds/{guild_id}/channels 获取子频道列表
    class getGuildChannels(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/channels'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # GET /channels/{channel_id} 获取子频道详情
    class getChannel(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # POST /guilds/{guild_id}/channels 创建子频道(私域)
    class createChannel(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/channels'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.name = None            # str
                self.type = None            # int 子频道类型
                self.sub_type = None        # int 子频道子类型
                self.position = None        # int
                self.parent_id = None       # str 分组 id
                self.private_type = None    # int 私密类型
                self.private_user_ids = None  # list
                self.speak_permission = None  # int
                self.application_id = None  # str 应用子频道应用类型

    # PATCH /channels/{channel_id} 修改子频道(私域)
    class patchChannel(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.name = None
                self.position = None
                self.parent_id = None
                self.private_type = None
                self.speak_permission = None

    # DELETE /channels/{channel_id} 删除子频道(私域)
    class deleteChannel(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # GET /channels/{channel_id}/online_nums 获取音视频/直播子频道在线成员数
    class getChannelOnlineNums(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/online_nums'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # ============ 频道模块:成员 ============
    # GET /guilds/{guild_id}/members 获取频道成员列表(私域, query: after/limit)
    class getGuildMembers(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # GET /guilds/{guild_id}/roles/{role_id}/members 获取身份组成员列表(query: start_index/limit)
    class getGuildRoleMembers(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles/{role_id}/members'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.role_id = '-1'

    # GET /guilds/{guild_id}/members/{user_id} 获取成员详情
    class getGuildMember(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'

    # DELETE /guilds/{guild_id}/members/{user_id} 删除频道成员(踢人,私域)
    class deleteGuildMember(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'

        class data_T(object):
            def __init__(self):
                self.add_blacklist = None             # bool 是否同时加入黑名单
                self.delete_history_msg_days = None   # int 撤回历史消息天数(3/7/15/30,0不撤回,-1全部)

    # ============ 频道模块:身份组 ============
    # GET /guilds/{guild_id}/roles 获取频道身份组列表
    class getGuildRoles(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # POST /guilds/{guild_id}/roles 创建频道身份组
    class createGuildRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.name = None   # str
                self.color = None  # int ARGB 十进制
                self.hoist = None  # int 是否在成员列表中单独展示(0/1)

    # PATCH /guilds/{guild_id}/roles/{role_id} 修改频道身份组
    class patchGuildRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles/{role_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.role_id = '-1'

        class data_T(object):
            def __init__(self):
                self.name = None
                self.color = None
                self.hoist = None

    # DELETE /guilds/{guild_id}/roles/{role_id} 删除频道身份组
    class deleteGuildRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/roles/{role_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.role_id = '-1'

    # PUT /guilds/{guild_id}/members/{user_id}/roles/{role_id} 增加频道身份组成员
    # 操作 5 号(子频道管理员)身份组时需在 body 传 channel.id。
    class putGuildMemberRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}/roles/{role_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'
                self.role_id = '-1'

        class data_T(object):
            def __init__(self):
                self.channel = None  # dict {'id': channel_id}

    # DELETE /guilds/{guild_id}/members/{user_id}/roles/{role_id} 删除频道身份组成员
    class deleteGuildMemberRole(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}/roles/{role_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'
                self.role_id = '-1'

        class data_T(object):
            def __init__(self):
                self.channel = None  # dict {'id': channel_id}

    # ============ 频道模块:子频道权限 ============
    # GET /channels/{channel_id}/members/{user_id}/permissions 获取子频道用户权限
    class getChannelMemberPermissions(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/members/{user_id}/permissions'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.user_id = '-1'

    # PUT /channels/{channel_id}/members/{user_id}/permissions 修改子频道用户权限
    class putChannelMemberPermissions(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/members/{user_id}/permissions'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.user_id = '-1'

        class data_T(object):
            def __init__(self):
                self.add = None     # str 权限位或值,如 '1'/'2'/'4'/'8' 的组合
                self.remove = None  # str

    # GET /channels/{channel_id}/roles/{role_id}/permissions 获取子频道身份组权限
    class getChannelRolePermissions(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/roles/{role_id}/permissions'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.role_id = '-1'

    # PUT /channels/{channel_id}/roles/{role_id}/permissions 修改子频道身份组权限
    class putChannelRolePermissions(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/roles/{role_id}/permissions'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.role_id = '-1'

        class data_T(object):
            def __init__(self):
                self.add = None
                self.remove = None

    # ============ 频道模块:消息列表/私信会话 ============
    # GET /channels/{channel_id}/messages 拉取消息列表(v1 存量接口, query: around/before/after/limit)
    class getChannelMessages(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/messages'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # ============ 频道模块:禁言 ============
    # PATCH /guilds/{guild_id}/mute 全员禁言(传 user_ids 时为批量成员禁言)
    class patchGuildMute(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/mute'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.mute_end_timestamp = None  # str 秒级时间戳
                self.mute_seconds = None        # str 禁言时长(秒),'0' 为解除
                self.user_ids = None            # list 批量成员禁言

    # PATCH /guilds/{guild_id}/members/{user_id}/mute 指定成员禁言
    class patchGuildMemberMute(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/members/{user_id}/mute'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.user_id = '-1'

        class data_T(object):
            def __init__(self):
                self.mute_end_timestamp = None
                self.mute_seconds = None

    # ============ 频道模块:公告/精华 ============
    # POST /guilds/{guild_id}/announces 创建频道公告
    class createAnnounce(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/announces'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.message_id = None          # str
                self.channel_id = None          # str
                self.announces_type = None      # int 0成员公告 1欢迎公告
                self.recommend_channels = None  # list RecommendChannel

    # DELETE /guilds/{guild_id}/announces/{message_id} 删除频道公告(message_id 可为 'all')
    class deleteAnnounce(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/announces/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'
                self.message_id = '-1'

    # PUT /channels/{channel_id}/pins/{message_id} 添加精华消息
    class putPinsMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/pins/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'

    # DELETE /channels/{channel_id}/pins/{message_id} 删除精华消息(message_id 可为 'all')
    class deletePinsMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/pins/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'

    # GET /channels/{channel_id}/pins 获取精华消息列表
    class getPinsMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/pins'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # ============ 频道模块:日程 ============
    # GET /channels/{channel_id}/schedules 获取日程列表(query: since)
    class getSchedules(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # GET /channels/{channel_id}/schedules/{schedule_id} 获取日程详情
    class getSchedule(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules/{schedule_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.schedule_id = '-1'

    # POST /channels/{channel_id}/schedules 创建日程
    class createSchedule(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.schedule = None  # dict Schedule 对象(不含 id)

    # PATCH /channels/{channel_id}/schedules/{schedule_id} 修改日程
    class patchSchedule(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules/{schedule_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.schedule_id = '-1'

        class data_T(object):
            def __init__(self):
                self.schedule = None  # dict Schedule 对象(不含 id)

    # DELETE /channels/{channel_id}/schedules/{schedule_id} 删除日程
    class deleteSchedule(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/schedules/{schedule_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.schedule_id = '-1'

    # ============ 频道模块:表情表态 ============
    # PUT /channels/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id} 发表表情表态
    class putMessageReaction(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['channels']
                + '/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id}'
            )

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'
                self.emoji_type = '1'  # 1系统表情 2emoji
                self.emoji_id = '-1'

    # DELETE /channels/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id} 删除自己的表情表态
    class deleteMessageReaction(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['channels']
                + '/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id}'
            )

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'
                self.emoji_type = '1'
                self.emoji_id = '-1'

    # GET .../reactions/{emoji_type}/{emoji_id} 拉取表态用户列表(query: cookie/limit)
    class getMessageReactionUsers(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['channels']
                + '/{channel_id}/messages/{message_id}/reactions/{emoji_type}/{emoji_id}'
            )

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'
                self.emoji_type = '1'
                self.emoji_id = '-1'

    # ============ 频道模块:音频/麦克风 ============
    # POST /channels/{channel_id}/audio 音频控制
    class postAudioControl(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/audio'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.audio_url = None  # str
                self.text = None       # str 状态文本
                self.status = None     # int 0开始 1暂停 2继续 3停止

    # PUT /channels/{channel_id}/mic 机器人上麦
    class putMic(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/mic'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # DELETE /channels/{channel_id}/mic 机器人下麦
    class deleteMic(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/mic'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # ============ 频道模块:帖子(论坛) ============
    # GET /channels/{channel_id}/threads 获取帖子列表(私域)
    class getThreads(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/threads'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

    # GET /channels/{channel_id}/threads/{thread_id} 获取帖子详情(私域)
    class getThread(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/threads/{thread_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.thread_id = '-1'

    # PUT /channels/{channel_id}/threads 发表帖子(私域)
    class putThread(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/threads'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.title = None    # str
                self.content = None  # str
                self.format = None   # int 1文本 2HTML 3Markdown 4JSON

    # DELETE /channels/{channel_id}/threads/{thread_id} 删除帖子(私域)
    class deleteThread(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/threads/{thread_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.thread_id = '-1'

    # ============ 频道模块:API 权限 ============
    # GET /guilds/{guild_id}/api_permission 获取频道可用权限列表
    class getGuildApiPermission(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/api_permission'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

    # POST /guilds/{guild_id}/api_permission/demand 创建频道 API 接口权限授权链接
    class demandGuildApiPermission(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['guilds'] + '/{guild_id}/api_permission/demand'

        class metadata_T(object):
            def __init__(self):
                self.guild_id = '-1'

        class data_T(object):
            def __init__(self):
                self.channel_id = None    # str
                self.api_identify = None  # dict {'path':..., 'method':...}
                self.desc = None          # str

    # ============ 消息发送 ============
    class sendMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/messages'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'

        class data_T(object):
            def __init__(self):
                self.content = None  # str
                self.embed = None  # object
                self.ark = None  # object
                self.message_reference = None  # object
                self.image = None  # str
                self.file_image = None  # multipart file
                self.msg_id = None  # str
                self.event_id = None  # str
                self.markdown = None  # object
                self.keyboard = None  # object

        # 频道本地图片使用 multipart/form-data，其他消息沿用通用 JSON 请求
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

    # ============ 消息删除 ============
    class deleteMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['channels'] + '/{channel_id}/messages/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.channel_id = '-1'
                self.message_id = '-1'
