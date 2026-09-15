# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqGuildv2SDKGroup.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   qqGuildv2 QQ 群聊实现
'''

from .qqGuildv2SDKCommon import *

event_action = None
API = None

class event_action_group(object):
    def _get_qq_message_send_chunks(message, flag_direct=False):
        media_types = (
            OlivOS.messageAPI.PARA.image,
            OlivOS.messageAPI.PARA.video,
            OlivOS.messageAPI.PARA.record,
            OlivOS.messageAPI.PARA.music,
            OlivOS.messageAPI.PARA.file
        )
        bindable_types = (
            OlivOS.messageAPI.PARA.text,
            OlivOS.messageAPI.PARA.at,
            OlivOS.messageAPI.PARA.image
        )
        message_chunks = []
        image_message_buffer = []

        def flush_image_message_buffer():
            if len(image_message_buffer) == 0:
                return
            image_message = OlivOS.messageAPI.Message_templet(
                'olivos_para',
                image_message_buffer.copy()
            )
            message_chunks.extend(event_action._get_message_send_chunks(
                image_message,
                [OlivOS.messageAPI.PARA.image],
                allow_at_all=False
            ))
            image_message_buffer.clear()

        for message_this in message.data:
            if isinstance(message_this, bindable_types):
                image_message_buffer.append(message_this)
            elif isinstance(message_this, media_types):
                flush_image_message_buffer()
                message_chunks.append(('', message_this))
        flush_image_message_buffer()
        return message_chunks

    def send_qq_msg(
        target_event,
        chat_id,
        message,
        reply_msg_id=None,
        flag_direct=False,
        quote_msg_id=None,
        event_id=None,
        force_active=False
    ):
        chat_type = 'qq_private' if flag_direct else 'qq_group'
        if chat_id is None or str(chat_id) == '':
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'chat_id is required'
            )
        if reply_msg_id is not None and event_id is not None:
            return event_action._make_local_result(
                chat_type,
                chat_id,
                'send',
                'msg_id and event_id are mutually exclusive'
            )
        if force_active:
            # Event.send 是主动发送语义，不能复用当前事件的被动回复凭据。
            msg_id = None
            event_id = None
            allow_active_fallback = False
        else:
            msg_id, event_id = event_action._resolve_qq_passive_ids(
                target_event,
                chat_type,
                chat_id,
                msg_id=reply_msg_id,
                event_id=event_id
            )
            allow_active_fallback = (
                msg_id is not None or event_id is not None
            )
        send_results = []
        if quote_msg_id is None:
            quote_msg_id = event_action._get_message_reference_id(message)

        def send_payload(text_content, file_info=None, bind_content=True):
            nonlocal allow_active_fallback, event_id, msg_id, quote_msg_id
            result = event_action._send_qq_payload(
                target_event,
                chat_id,
                text_content,
                msg_id,
                flag_direct=flag_direct,
                file_info=file_info,
                bind_content=bind_content,
                quote_msg_id=quote_msg_id,
                event_id=event_id,
                allow_active_fallback=allow_active_fallback
            )
            send_results.append(result)
            if result.get('data', {}).get('passive_fallback') is not None:
                msg_id = None
                event_id = None
                allow_active_fallback = False
            if result.get('active', False):
                quote_msg_id = None
            return result

        for text_content, message_this in event_action._get_qq_message_send_chunks(
            message,
            flag_direct=flag_direct
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
            if isinstance(message_this, OlivOS.messageAPI.PARA.image):
                type_path = 'images'
            elif isinstance(message_this, OlivOS.messageAPI.PARA.video):
                type_path = 'videos'
            elif isinstance(message_this, OlivOS.messageAPI.PARA.record):
                type_path = 'audios'
            elif isinstance(message_this, OlivOS.messageAPI.PARA.music):
                type_path = 'audios'
            elif isinstance(message_this, OlivOS.messageAPI.PARA.file):
                type_path = 'files'
            else:
                continue
            bind_content = isinstance(message_this, OlivOS.messageAPI.PARA.image)
            if not bind_content and text_content != '':
                result = send_payload(text_content)
                if not result.get('active', False):
                    return event_action._merge_send_results(
                        chat_type,
                        chat_id,
                        send_results
                    )
                text_content = ''
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
            file_name = None
            if (
                isinstance(message_this, OlivOS.messageAPI.PARA.file)
                and message_this.data is not None
            ):
                file_name = message_this.data.get('name', None)
            file_info = event_action.setResourceUploadFast(
                target_event,
                resource_url,
                chat_id,
                type_path=type_path,
                type_chat='qq_users' if flag_direct else 'qq_groups',
                file_name=file_name
            )
            if file_info is None:
                send_results.append(event_action._make_local_result(
                    chat_type,
                    chat_id,
                    'send',
                    'message resource upload failed'
                ))
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
            result = send_payload(
                text_content,
                file_info=file_info,
                bind_content=bind_content
            )
            if not result.get('active', False):
                return event_action._merge_send_results(
                    chat_type,
                    chat_id,
                    send_results
                )
        return event_action._merge_send_results(chat_type, chat_id, send_results)

    def _send_qq_payload(
        target_event,
        chat_id,
        content,
        msg_id,
        flag_direct=False,
        file_info=None,
        bind_content=True,
        quote_msg_id=None,
        event_id=None,
        allow_active_fallback=False
    ):
        chat_type = 'qq_private' if flag_direct else 'qq_group'
        if flag_direct:
            this_msg = API.sendQQDirectMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.openid = str(chat_id)
        else:
            this_msg = API.sendQQMessage(get_SDK_bot_info_from_Event(target_event))
            this_msg.metadata.group_openid = str(chat_id)
        this_msg.data.content = content if file_info is None or bind_content else None
        if file_info is None:
            this_msg.data.msg_type = 0
        else:
            # 上传接口返回的 file_info 必须包装到 media 对象中，再调用消息发送接口。
            this_msg.data.msg_type = 7
            this_msg.data.media = {'file_info': file_info}
        if quote_msg_id is not None and str(quote_msg_id) != '':
            this_msg.data.message_reference = {'message_id': str(quote_msg_id)}
        res_data = event_action._send_qq_api(
            target_event,
            this_msg,
            chat_type,
            chat_id,
            msg_id,
            event_id,
            allow_active_fallback=allow_active_fallback
        )
        fallback_used = res_data.get('data', {}).get('passive_fallback') is not None
        event_action._log_qq_send_result(
            target_event,
            this_msg,
            None if fallback_used else getattr(this_msg.data, 'msg_id', None),
            flag_direct=flag_direct,
            event_id=None if fallback_used else getattr(this_msg.data, 'event_id', None)
        )
        return res_data

    def _log_qq_send_result(target_event, api_obj, msg_id, flag_direct=False, event_id=None):
        if target_event.log_func is None:
            return
        res_obj = init_api_json(api_obj.res)
        api_code = event_action._get_api_error_code(res_obj)
        flag_success = (
            api_obj.res_code is not None
            and 200 <= api_obj.res_code < 300
            and (
                api_code in [None, 0]
                or event_action._is_api_async_accepted(
                    'send',
                    api_obj.res_code,
                    api_code
                )
            )
        )
        # 被动回复沿用现有简洁日志；主动消息额外记录平台结果，便于排查权限和审核问题。
        if flag_success and (msg_id is not None or event_id is not None):
            return
        send_mode = 'active' if msg_id is None and event_id is None else 'reply'
        chat_type = 'direct' if flag_direct else 'group'
        res_text = str(api_obj.res) if api_obj.res is not None else 'no response'
        if len(res_text) > 1000:
            res_text = res_text[:1000] + '...'
        res_code_text = 'n/a' if api_obj.res_code is None else str(api_obj.res_code)
        try:
            target_event.log_func(
                2 if flag_success else 3,
                'OlivOS qqGuildv2SDK QQ %s %s message response: HTTP %s %s' % (
                    chat_type,
                    send_mode,
                    res_code_text,
                    res_text
                ),
                [
                    (target_event.getBotIDStr(), 'default'),
                    (modelName, 'default'),
                    ('send_qq_msg', 'callback')
                ]
            )
        except Exception:
            traceback.print_exc()

    def upload_group_file(target_event, group_id, file, name='', folder_id=None):
        # QQ 群文件接口不支持 OneBot 的 folder_id，保留参数仅为统一 API 签名。
        context_error = event_action._get_qq_upload_context_error(
            target_event,
            flag_direct=False
        )
        if context_error is not None:
            return event_action._make_local_result(
                'qq_group', group_id, 'upload_group_file', context_error
            )
        file_info = event_action.setResourceUploadFast(
            target_event,
            file,
            group_id,
            type_path='files',
            type_chat='qq_groups',
            file_name=name,
            flag_send_msg=True
        )
        return event_action._make_resource_upload_result(
            'qq_group', group_id, file_info, 'upload_group_file'
        )

    def get_qq_group_member_list_standard(target_event, group_openid, cursor=None):
        return event_action._standard_group_member_list(
            event_action.get_qq_group_member_list(target_event, group_openid, cursor),
            fallback_group_id=group_openid
        )

    # ============ QQ 群 ============
    def get_qq_group_member_list(target_event, group_openid, cursor=None):
        # 官方文档:GET /v2/groups/{group_openid}/members,60 QPM,每页最多 30 条,
        # cursor 分页(首页不传或空串,后续传上一页响应的 next_cursor)。
        # 旧实现的 limit/start_index 参数平台不识别(始终返回第一页),已修正。
        this_msg = API.getQQGroupMembers(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.group_openid = str(group_openid)
        this_msg.query = {'cursor': cursor} if cursor else None
        return event_action._run_raw_api(this_msg, 'get_qq_group_member_list', 'GET')

    # ---- QQ 群管理接口(内邀白名单能力,统一走滑动窗口限流与 11253 降级) ----
    def _run_qq_group_member_api(api_obj, operation, op_key, req_type='GET',
                                 wait=False, group_openid=None):
        api_res = _do_qq_group_api_request(
            api_obj.bot_info,
            api_obj,
            req_type,
            op_key,
            wait=wait
        )
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['active'] = api_res.get('active', False)
        res_data['data'].update({
            'chat_type': 'qq_group',
            'chat_id': None if group_openid is None else str(group_openid),
            'operation': str(operation),
            'http_status': api_res.get('http_status', None),
            'error_code': api_res.get('error_code', None),
            'error': api_res.get('error', None),
            'response': api_res.get('response', None)
        })
        return res_data

    def _request_qq_group_member_info(target_event, group_openid, member_openid):
        this_msg = API.getQQGroupMemberInfo(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.group_openid = str(group_openid)
        this_msg.metadata.member_openid = str(member_openid)
        return event_action._run_qq_group_member_api(
            this_msg,
            'get_qq_group_member_info',
            'group_member_info',
            'GET',
            group_openid=group_openid
        )

    def _request_qq_group_member_blacklist_page(
        target_event,
        group_openid,
        limit=None,
        cursor=None
    ):
        this_msg = API.getQQGroupMemberBlacklist(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.group_openid = str(group_openid)
        this_msg.query = {'cursor': cursor, 'limit': limit}
        return event_action._run_qq_group_member_api(
            this_msg,
            'get_qq_group_member_blacklist_page',
            'group_member_blacklist_get',
            'GET',
            group_openid=group_openid
        )

    def _request_qq_group_member_blacklist_set_page(
        target_event,
        group_openid,
        op,
        member_openids
    ):
        this_msg = API.setQQGroupMemberBlacklist(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.group_openid = str(group_openid)
        this_msg.data.op = str(op)
        this_msg.data.member_openids = [str(item) for item in member_openids]
        return event_action._run_qq_group_member_api(
            this_msg,
            'set_qq_group_member_blacklist_page',
            'group_member_blacklist_set',
            'POST',
            group_openid=group_openid
        )

    def _request_qq_group_batch_remove_members_page(
        target_event,
        group_openid,
        member_openids,
        add_to_member_blacklist=None
    ):
        this_msg = API.setQQGroupBatchRemoveMembers(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.group_openid = str(group_openid)
        this_msg.data.member_openids = [str(item) for item in member_openids]
        this_msg.data.add_to_member_blacklist = add_to_member_blacklist
        return event_action._run_qq_group_member_api(
            this_msg,
            'set_qq_group_batch_remove_members_page',
            'group_batch_remove_members',
            'POST',
            group_openid=group_openid
        )

    def get_qq_group_member_blacklist(target_event, group_openid, limit=None):
        """群黑名单查询(SDK 级)

        支持 cursor 分页与 limit,自动翻页到末页。
        limit 单页数量(默认 20,最大 100);内邀白名单能力,无权限时优雅降级。
        """
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['data'].update({
            'chat_type': 'qq_group',
            'chat_id': None if group_openid is None else str(group_openid),
            'operation': 'get_qq_group_member_blacklist',
            'blacklist': [],
            'total': 0,
            'page_size': None,
            'pages': 0,
            'batches': []
        })
        try:
            page_limit = min(100, max(1, int(limit)))
        except (TypeError, ValueError):
            page_limit = 20
        res_data['data']['page_size'] = page_limit
        cursor = ''
        page_res = None
        while res_data['data']['pages'] < 500:
            page_res = event_action._request_qq_group_member_blacklist_page(
                target_event,
                group_openid,
                limit=page_limit,
                cursor=cursor if cursor != '' else None
            )
            res_data['data']['batches'].append(copy.deepcopy(page_res))
            res_data['data']['pages'] += 1
            if not page_res.get('active', False):
                if res_data['data']['total'] == 0:
                    res_data['data']['error'] = page_res['data'].get('error', None)
                    res_data['data']['error_code'] = page_res['data'].get('error_code', None)
                    return res_data
                # 后续页失败时保留已成功页的数据,并附错误说明。
                res_data['data']['error'] = page_res['data'].get('error', None)
                res_data['data']['error_code'] = page_res['data'].get('error_code', None)
                return res_data
            response = event_action._raw_response(page_res)
            users = response.get('users', None) if isinstance(response, dict) else None
            if isinstance(users, list):
                res_data['data']['blacklist'].extend(copy.deepcopy(users))
                res_data['data']['total'] = len(res_data['data']['blacklist'])
            next_cursor = response.get('next_cursor', '') if isinstance(response, dict) else ''
            if not isinstance(next_cursor, str) or next_cursor == '':
                break
            cursor = next_cursor
        res_data['active'] = True
        return res_data

    def set_qq_group_member_blacklist(target_event, group_openid, member_openids, op='add'):
        """群黑名单操作(SDK 级)

        op 支持 add(加入)/del(移出);单次接口上限 20 个,超出自动分批。
        内邀白名单能力,无权限时优雅降级(active=False + 明确错误信息)。
        """
        op = str(op)
        if op not in ['add', 'del']:
            return event_action._make_local_result(
                'qq_group',
                group_openid,
                'set_qq_group_member_blacklist',
                'op must be add or del'
            )
        valid_ids = []
        if isinstance(member_openids, (list, tuple, set)):
            for member_id in member_openids:
                member_id = str(member_id)
                if member_id != '' and member_id not in valid_ids:
                    valid_ids.append(member_id)
        if len(valid_ids) == 0:
            return event_action._make_local_result(
                'qq_group',
                group_openid,
                'set_qq_group_member_blacklist',
                'no valid member_openid provided'
            )
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['data'].update({
            'chat_type': 'qq_group',
            'chat_id': None if group_openid is None else str(group_openid),
            'operation': 'set_qq_group_member_blacklist',
            'op': op,
            'requested': len(valid_ids),
            'batches': 0,
            'batch_size': 20,
            'fail_openids': [],
            'results': []
        })
        batch_size = 20
        flag_all_ok = True
        last_error = None
        last_error_code = None
        for start in range(0, len(valid_ids), batch_size):
            page_res = event_action._request_qq_group_member_blacklist_set_page(
                target_event,
                group_openid,
                op,
                valid_ids[start:start + batch_size]
            )
            res_data['data']['batches'] += 1
            res_data['data']['results'].append(copy.deepcopy(page_res))
            if page_res.get('active', False):
                response = event_action._raw_response(page_res)
                fail_list = response.get('fail_openids', None) if isinstance(response, dict) else None
                if isinstance(fail_list, list):
                    res_data['data']['fail_openids'].extend(copy.deepcopy(fail_list))
            else:
                flag_all_ok = False
                last_error = page_res['data'].get('error', None)
                last_error_code = page_res['data'].get('error_code', None)
        res_data['active'] = flag_all_ok
        res_data['data']['error'] = last_error
        res_data['data']['error_code'] = last_error_code
        return res_data

    def set_qq_group_batch_remove_members(
        target_event,
        group_openid,
        member_openids,
        add_to_member_blacklist=False
    ):
        """群成员批量移除(SDK 级)

        底层走 batch_remove_members,单次接口上限 20 个,超出自动分批。
        成功移除的成员同步从本地群成员缓存中删除。
        内邀白名单能力,无权限时优雅降级(active=False + 明确错误信息)。
        """
        valid_ids = []
        if isinstance(member_openids, (list, tuple, set)):
            for member_id in member_openids:
                member_id = str(member_id)
                if member_id != '' and member_id not in valid_ids:
                    valid_ids.append(member_id)
        if len(valid_ids) == 0:
            return event_action._make_local_result(
                'qq_group',
                group_openid,
                'set_qq_group_batch_remove_members',
                'no valid member_openid provided'
            )
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        res_data['data'].update({
            'chat_type': 'qq_group',
            'chat_id': None if group_openid is None else str(group_openid),
            'operation': 'set_qq_group_batch_remove_members',
            'requested': len(valid_ids),
            'batches': 0,
            'batch_size': 20,
            'removed_openids': [],
            'add_to_member_blacklist_fail_openids': [],
            'results': []
        })
        batch_size = 20
        flag_all_ok = True
        last_error = None
        last_error_code = None
        bot_hash = target_event.bot_info.hash
        for start in range(0, len(valid_ids), batch_size):
            batch_ids = valid_ids[start:start + batch_size]
            page_res = event_action._request_qq_group_batch_remove_members_page(
                target_event,
                group_openid,
                batch_ids,
                add_to_member_blacklist=bool(add_to_member_blacklist)
            )
            res_data['data']['batches'] += 1
            res_data['data']['results'].append(copy.deepcopy(page_res))
            if page_res.get('active', False):
                # 移除成功即同步删本地缓存(GROUP_MEMBER_REMOVE 事件之外的一致性兜底)。
                for member_id in batch_ids:
                    _qq_group_member_cache_remove_member(bot_hash, group_openid, member_id)
                res_data['data']['removed_openids'].extend(batch_ids)
                response = event_action._raw_response(page_res)
                fail_list = (
                    response.get('add_to_member_blacklist_fail_openids', None)
                    if isinstance(response, dict) else None
                )
                if isinstance(fail_list, list):
                    res_data['data']['add_to_member_blacklist_fail_openids'].extend(
                        copy.deepcopy(fail_list)
                    )
            else:
                flag_all_ok = False
                last_error = page_res['data'].get('error', None)
                last_error_code = page_res['data'].get('error_code', None)
        res_data['active'] = flag_all_ok
        res_data['data']['error'] = last_error
        res_data['data']['error_code'] = last_error_code
        return res_data

    def refresh_qq_group_member_list(target_event, group_openid):
        """全量刷新群成员列表(SDK 级,Tier 2 手动入口)

        分页拉取全量成员(每页 30 条,60 QPM 限速),逐页写入本地缓存。
        """
        res_data = OlivOS.contentAPI.api_result_data_template.universal_result()
        bot_info = get_SDK_bot_info_from_Event(target_event)
        bot_hash = str(target_event.bot_info.hash)
        _register_qq_group_for_calibration(bot_hash, bot_info, group_openid)
        fetch_result = _qq_group_fetch_member_pages(
            bot_info,
            group_openid,
            bot_hash=bot_hash
        )
        res_data['active'] = fetch_result.get('ok', False)
        res_data['data'].update({
            'chat_type': 'qq_group',
            'chat_id': None if group_openid is None else str(group_openid),
            'operation': 'refresh_qq_group_member_list',
            'pages': fetch_result.get('pages', 0),
            'member_count': fetch_result.get('members', 0),
            'error': fetch_result.get('error', None),
            'error_code': qqGroupApiDeniedCode if fetch_result.get('denied', False) else None
        })
        return res_data

    def get_group_member_list(target_event, group_id):
        """群成员列表(统一层入口,本地缓存优先)

        大群全量需 60 次请求(30 条/页),正好吃满 60 QPM,因此优先读本地缓存:
        缓存为空时才全量拉取并落盘;缓存命中时 username=None 的成员即「待补全」。
        """
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_member_list()
        bot_hash = str(target_event.bot_info.hash)
        members = _get_qq_group_member_cache_members(bot_hash, group_id)
        if len(members) == 0:
            # 缓存为空才走网络全量(错峰限速,wait=True 分页匀速)。
            bot_info = get_SDK_bot_info_from_Event(target_event)
            _register_qq_group_for_calibration(bot_hash, bot_info, group_id)
            fetch_result = _qq_group_fetch_member_pages(
                bot_info,
                group_id,
                bot_hash=bot_hash
            )
            if fetch_result.get('ok', False):
                members = _get_qq_group_member_cache_members(bot_hash, group_id)
        if len(members) == 0:
            # 全量拉取失败(无权限/限流):缓存与网络均无数据,优雅返回 inactive。
            return res_data
        res_data['active'] = True
        for member_id in sorted(members.keys()):
            record = members[member_id]
            member = OlivOS.contentAPI.api_result_data_template.get_group_member_info_strip()
            member['id'] = str(member_id)
            member['user_id'] = str(member_id)
            member['group_id'] = str(group_id)
            # username=None 表示「待补全」,调用方可据此区分已知昵称与占位成员。
            member['name'] = record.get('username', None)
            member['card'] = record.get('username', None)
            member['role'] = record.get('member_role', None)
            member['times']['join_time'] = _parse_qq_message_timestamp(
                record.get('joined_at', None),
                default=0
            )
            member['extra'] = {
                'cached': True,
                'bot': record.get('bot', None),
                'union_openid': record.get('union_openid', None),
                'updated_at': record.get('updated_at', 0)
            }
            res_data['data'].append(member)
        return res_data

    def get_qq_group_bot_state(target_event, group_openid):
        this_msg = API.getQQGroupBotState(get_SDK_bot_info_from_Event(target_event))
        this_msg.metadata.group_openid = str(group_openid)
        return event_action._run_raw_api(this_msg, 'get_qq_group_bot_state', 'GET')

    def get_qq_group_restrict_chat_setting(target_event, group_openid):
        this_msg = API.getQQGroupRestrictChatSetting(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.metadata.group_openid = str(group_openid)
        return event_action._run_raw_api(
            this_msg,
            'get_qq_group_restrict_chat_setting',
            'GET'
        )

    def _get_qq_group_restrict_chat_setting_cached(
        target_event,
        group_openid,
        no_cache=False
    ):
        cache_key = (
            str(target_event.bot_info.hash),
            str(group_openid)
        )
        now = time.monotonic()
        if not no_cache:
            with sdkGroupRestrictChatInfoLock:
                cache_data = sdkGroupRestrictChatInfo.get(cache_key, None)
                if (
                    isinstance(cache_data, dict)
                    and now - cache_data.get('cached_at', 0)
                    < sdkGroupRestrictChatInfoTTL
                ):
                    return copy.deepcopy(cache_data.get('result', None))
                sdkGroupRestrictChatInfo.pop(cache_key, None)

        raw_result = event_action.get_qq_group_restrict_chat_setting(
            target_event,
            group_openid
        )
        if (
            isinstance(raw_result, dict)
            and raw_result.get('active', False)
            and isinstance(event_action._raw_response(raw_result), dict)
        ):
            with sdkGroupRestrictChatInfoLock:
                expired_keys = [
                    this_key
                    for this_key, this_data in sdkGroupRestrictChatInfo.items()
                    if now - this_data.get('cached_at', 0)
                    >= sdkGroupRestrictChatInfoTTL
                ]
                for expired_key in expired_keys:
                    sdkGroupRestrictChatInfo.pop(expired_key, None)
                if (
                    cache_key not in sdkGroupRestrictChatInfo
                    and len(sdkGroupRestrictChatInfo)
                    >= sdkGroupRestrictChatInfoMaxSize
                ):
                    oldest_key = min(
                        sdkGroupRestrictChatInfo,
                        key=lambda this_key: sdkGroupRestrictChatInfo[
                            this_key
                        ].get('cached_at', 0)
                    )
                    sdkGroupRestrictChatInfo.pop(oldest_key, None)
                sdkGroupRestrictChatInfo[cache_key] = {
                    'cached_at': now,
                    'result': copy.deepcopy(raw_result)
                }
        return raw_result

    def set_qq_group_restrict_chat_setting(target_event, group_openid, members):
        this_msg = API.setQQGroupRestrictChatSetting(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.metadata.group_openid = str(group_openid)
        this_msg.data.members = copy.deepcopy(members)
        res_data = event_action._run_raw_api(
            this_msg,
            'set_qq_group_restrict_chat_setting',
            'POST'
        )
        if res_data.get('active', False):
            cache_key = (
                str(target_event.bot_info.hash),
                str(group_openid)
            )
            with sdkGroupRestrictChatInfoLock:
                sdkGroupRestrictChatInfo.pop(cache_key, None)
        return res_data

    def get_qq_group_join_request_list(
        target_event,
        group_openid,
        cursor=None,
        limit=None
    ):
        this_msg = API.getQQGroupJoinRequestList(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.metadata.group_openid = str(group_openid)
        this_msg.query = {'cursor': cursor, 'limit': limit}
        return event_action._run_raw_api(
            this_msg,
            'get_qq_group_join_request_list',
            'GET'
        )

    def approve_qq_group_join_request(
        target_event,
        group_openid,
        member_openid,
        op,
        join_request_id=None,
        reject_reason=None,
        add_to_member_blacklist=None
    ):
        this_msg = API.approveQQGroupJoinRequest(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.metadata.group_openid = str(group_openid)
        this_msg.metadata.member_openid = str(member_openid)
        this_msg.data.op = str(op)
        this_msg.data.join_request_id = (
            None if join_request_id is None else str(join_request_id)
        )
        this_msg.data.reject_reason = reject_reason
        this_msg.data.add_to_member_blacklist = add_to_member_blacklist
        return event_action._run_raw_api(
            this_msg,
            'approve_qq_group_join_request',
            'POST'
        )

    def get_qq_join_approval_strategy_list(
        target_event,
        cursor=None,
        limit=None
    ):
        this_msg = API.getQQJoinApprovalStrategyList(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.query = {'cursor': cursor, 'limit': limit}
        return event_action._run_raw_api(
            this_msg,
            'get_qq_join_approval_strategy_list',
            'GET'
        )

    def create_qq_join_approval_strategy(
        target_event,
        group_openids=None,
        group_ids=None,
        is_enable=None,
        expire_at=None,
        remark=None
    ):
        this_msg = API.createQQJoinApprovalStrategy(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.data.group_openids = copy.deepcopy(group_openids)
        this_msg.data.group_ids = copy.deepcopy(group_ids)
        this_msg.data.is_enable = is_enable
        this_msg.data.expire_at = expire_at
        this_msg.data.remark = remark
        return event_action._run_raw_api(
            this_msg,
            'create_qq_join_approval_strategy',
            'POST'
        )

    def patch_qq_join_approval_strategy(
        target_event,
        strategy_id,
        is_enable=None,
        expire_at=None,
        group_action=None,
        remark=None
    ):
        this_msg = API.patchQQJoinApprovalStrategy(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.metadata.strategy_id = str(strategy_id)
        this_msg.data.is_enable = is_enable
        this_msg.data.expire_at = expire_at
        this_msg.data.group_action = copy.deepcopy(group_action)
        this_msg.data.remark = remark
        return event_action._run_raw_api(
            this_msg,
            'patch_qq_join_approval_strategy',
            'PATCH'
        )

    def delete_qq_join_approval_strategy(target_event, strategy_id):
        this_msg = API.deleteQQJoinApprovalStrategy(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.metadata.strategy_id = str(strategy_id)
        return event_action._run_raw_api(
            this_msg,
            'delete_qq_join_approval_strategy',
            'DELETE'
        )

    def execute_qq_join_approval_strategy(target_event, strategy_id):
        this_msg = API.executeQQJoinApprovalStrategy(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.metadata.strategy_id = str(strategy_id)
        return event_action._run_raw_api(
            this_msg,
            'execute_qq_join_approval_strategy',
            'POST'
        )

    def update_qq_join_approval_strategy_whitelist(
        target_event,
        strategy_id,
        op,
        whitelist_users
    ):
        this_msg = API.updateQQJoinApprovalStrategyWhitelist(
            get_SDK_bot_info_from_Event(target_event)
        )
        this_msg.metadata.strategy_id = str(strategy_id)
        this_msg.data.op = str(op)
        this_msg.data.whitelist_users = copy.deepcopy(whitelist_users)
        return event_action._run_raw_api(
            this_msg,
            'update_qq_join_approval_strategy_whitelist',
            'POST'
        )

    def _get_qq_group_member_mute_state(raw_result, member_openid):
        response = event_action._raw_response(raw_result)
        if not isinstance(response, dict):
            return None
        members = response.get('members', None)
        if not isinstance(members, list):
            return None
        for member in members:
            if (
                isinstance(member, dict)
                and str(member.get('member_openid', '')) == str(member_openid)
            ):
                return member
        return None

    def set_qq_group_member_mute(
        target_event,
        group_openid,
        member_openid,
        duration=1800
    ):
        try:
            duration = int(duration)
        except (TypeError, ValueError):
            return event_action._make_local_result(
                'qq_group',
                group_openid,
                'set_group_ban',
                'duration must be an integer'
            )
        if duration <= 0:
            operation = 'del'
            mute_expire_at = ''
        else:
            mute_result = event_action.get_qq_group_restrict_chat_setting(
                target_event,
                group_openid
            )
            mute_state = event_action._get_qq_group_member_mute_state(
                mute_result,
                member_openid
            )
            operation = 'update' if mute_state is not None else 'add'
            mute_expire_at = (
                datetime.now(timezone.utc) + timedelta(seconds=duration)
            ).isoformat(timespec='seconds')
        return event_action.set_qq_group_restrict_chat_setting(
            target_event,
            group_openid,
            [{
                'op': operation,
                'member_openid': str(member_openid),
                'mute_expire_at': mute_expire_at
            }]
        )

    def set_group_add_request(
        target_event,
        flag,
        sub_type,
        approve,
        reason=None
    ):
        flag_data = _parse_qq_join_request_flag(flag)
        if flag_data is None:
            return event_action._make_local_result(
                'qq_group',
                None,
                'set_group_add_request',
                'invalid QQ group join request flag'
            )
        if sub_type not in ['add', 'invite']:
            return event_action._make_local_result(
                'qq_group',
                flag_data['group_openid'],
                'set_group_add_request',
                'unsupported group request sub_type'
            )
        return event_action.approve_qq_group_join_request(
            target_event,
            flag_data['group_openid'],
            flag_data['member_openid'],
            'approve' if approve else 'decline',
            join_request_id=flag_data['join_request_id'],
            reject_reason=None if approve else reason
        )

    def get_qq_group_join_request_list_standard(
        target_event,
        group_openid,
        count=50
    ):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_system_msg()
        try:
            limit = min(100, max(1, int(count)))
        except (TypeError, ValueError):
            limit = 50
        raw_result = event_action.get_qq_group_join_request_list(
            target_event,
            group_openid,
            limit=limit
        )
        response = event_action._raw_response(raw_result)
        if (
            not isinstance(raw_result, dict)
            or not raw_result.get('active', False)
            or not isinstance(response, dict)
        ):
            return res_data
        request_list = response.get('list', None)
        if not isinstance(request_list, list):
            return res_data
        res_data['active'] = True
        res_data['data']['next_cursor'] = response.get('next_cursor', '')
        res_data['data']['qq_response'] = copy.deepcopy(response)
        for request_data in request_list:
            if not isinstance(request_data, dict):
                continue
            member_openid = request_data.get('member_openid', None)
            join_request_id = request_data.get('join_request_id', None)
            if member_openid is None or join_request_id is None:
                continue
            request_item = copy.deepcopy(request_data)
            request_item.update({
                'request_id': str(join_request_id),
                'group_id': str(group_openid),
                'user_id': str(member_openid),
                'comment': _get_qq_join_request_comment(request_data),
                'flag': _make_qq_join_request_flag(
                    group_openid,
                    member_openid,
                    join_request_id
                ),
                'sub_type': 'add',
                'time': _parse_qq_message_timestamp(
                    request_data.get('apply_at', None),
                    default=0
                ),
                'extra': copy.deepcopy(request_data)
            })
            res_data['data']['join_requests'].append(request_item)
        return res_data

class API_group(object):
    class getQQGroupBotState(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/bot_state'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

    # GET /v2/groups/{group_openid}/members/{member_openid} 获取群成员信息(内邀,30 QPM)
    class getQQGroupMemberInfo(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['qq_groups']
                + '/{group_openid}/members/{member_openid}'
            )

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'
                self.member_openid = '-1'

    # GET /v2/groups/{group_openid}/member_blacklist 群黑名单查询(内邀,30 QPM,query: cursor/limit)
    class getQQGroupMemberBlacklist(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/member_blacklist'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

    # POST /v2/groups/{group_openid}/member_blacklist 群黑名单操作(内邀,60 QPM,单次≤20)
    class setQQGroupMemberBlacklist(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/member_blacklist'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

        class data_T(object):
            def __init__(self):
                self.op = None            # str: 'add' 加入黑名单 / 'del' 移出黑名单
                self.member_openids = None  # list[str],单次最多 20 个

    # POST /v2/groups/{group_openid}/batch_remove_members 群成员批量移除(内邀,30 QPM,单次≤20)
    class setQQGroupBatchRemoveMembers(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/batch_remove_members'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

        class data_T(object):
            def __init__(self):
                self.member_openids = None          # list[str],单次最多 20 个
                self.add_to_member_blacklist = None  # bool,默认 False

    # ============ QQ 群 ============
    # GET /v2/groups/{group_openid}/members 获取群成员列表(query: cursor,内邀,60 QPM,每页≤30)
    class getQQGroupMembers(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/members'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

    # GET /v2/groups/{group_openid}/restrict_chat_setting 查询群禁言状态
    class getQQGroupRestrictChatSetting(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['qq_groups']
                + '/{group_openid}/restrict_chat_setting'
            )

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

    # POST /v2/groups/{group_openid}/restrict_chat_setting 设置成员禁言
    class setQQGroupRestrictChatSetting(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['qq_groups']
                + '/{group_openid}/restrict_chat_setting'
            )

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

        class data_T(object):
            def __init__(self):
                self.members = None  # list[SetMemberMuteState]

    # GET /v2/groups/{group_openid}/join_request_list 拉取入群申请
    class getQQGroupJoinRequestList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['qq_groups']
                + '/{group_openid}/join_request_list'
            )

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

    # POST /v2/groups/{group_openid}/approval_join_request/{member_openid}
    class approveQQGroupJoinRequest(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['qq_groups']
                + '/{group_openid}/approval_join_request/{member_openid}'
            )

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'
                self.member_openid = '-1'

        class data_T(object):
            def __init__(self):
                self.op = None
                self.join_request_id = None
                self.reject_reason = None
                self.add_to_member_blacklist = None

    # GET /v2/groups/join_approval_strategy 查询自动审批策略
    class getQQJoinApprovalStrategyList(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/join_approval_strategy'

    # POST /v2/groups/join_approval_strategy 创建自动审批策略
    class createQQJoinApprovalStrategy(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = None
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/join_approval_strategy'

        class data_T(object):
            def __init__(self):
                self.group_openids = None
                self.group_ids = None
                self.is_enable = None
                self.expire_at = None
                self.remark = None

    # PATCH /v2/groups/join_approval_strategy/{strategy_id}
    class patchQQJoinApprovalStrategy(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['qq_groups']
                + '/join_approval_strategy/{strategy_id}'
            )

        class metadata_T(object):
            def __init__(self):
                self.strategy_id = '-1'

        class data_T(object):
            def __init__(self):
                self.is_enable = None
                self.expire_at = None
                self.group_action = None
                self.remark = None

    # DELETE /v2/groups/join_approval_strategy/{strategy_id}
    class deleteQQJoinApprovalStrategy(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['qq_groups']
                + '/join_approval_strategy/{strategy_id}'
            )

        class metadata_T(object):
            def __init__(self):
                self.strategy_id = '-1'

    # POST /v2/groups/join_approval_strategy/{strategy_id}/execute
    class executeQQJoinApprovalStrategy(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['qq_groups']
                + '/join_approval_strategy/{strategy_id}/execute'
            )

        class metadata_T(object):
            def __init__(self):
                self.strategy_id = '-1'

    # POST /v2/groups/join_approval_strategy/{strategy_id}/whitelist_users
    class updateQQJoinApprovalStrategyWhitelist(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = (
                sdkAPIRoute['qq_groups']
                + '/join_approval_strategy/{strategy_id}/whitelist_users'
            )

        class metadata_T(object):
            def __init__(self):
                self.strategy_id = '-1'

        class data_T(object):
            def __init__(self):
                self.op = None
                self.whitelist_users = None

    class sendQQMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = self.data_T()
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/messages'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'

        class data_T(object):
            def __init__(self):
                self.content = None     # str
                self.media = None       # object
                self.msg_type = 0       # int
                self.markdown = None    # object
                self.keyboard = None    # object
                self.ark = None         # object
                self.embed = None       # object
                self.message_reference = None  # object
                self.event_id = None    # str
                self.msg_id = None      # str
                self.msg_seq = None

    class deleteQQMessage(api_templet):
        def __init__(self, bot_info=None):
            api_templet.__init__(self)
            self.bot_info = bot_info
            self.data = None
            self.metadata = self.metadata_T()
            self.host = sdkAPIHost['default']
            self.route = sdkAPIRoute['qq_groups'] + '/{group_openid}/messages/{message_id}'

        class metadata_T(object):
            def __init__(self):
                self.group_openid = '-1'
                self.message_id = '-1'
