# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/metadataAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import OlivOS

def getTextByMetaTableFormat(src_table, fwd_key, format_patch, default_res = 'N/A'):
    global globalMetaTableTemp
    tmp_res = default_res
    tmp_src = tmp_res
    tmp_globalMetaTableTemp = globalMetaTableTemp.copy()
    if fwd_key in src_table:
        tmp_src = src_table[fwd_key]
        tmp_globalMetaTableTemp.update(format_patch)
        try:
            tmp_res = tmp_src.format(**tmp_globalMetaTableTemp)
        except:
            tmp_res = default_res
    return tmp_res

def getPairMapping(pair_list = []):
    tmp_res = {}
    for pair_list_this in pair_list:
        if type(pair_list_this) == list:
            if len(pair_list_this) == 2:
                tmp_res[pair_list_this[0]] = str(pair_list_this[1])
            else:
                continue
        else:
            continue
    return tmp_res

globalMetaTableTemp = {
    'nickname': 'N/A',
    'message': 'N/A',
    'message_id': 'N/A',
    'user_id': 'N/A',
    'group_id': 'N/A',
    'host_id': 'N/A',
    'operator_id': 'N/A',
    'target_id': 'N/A',
    'name': 'N/A',
    'action': 'N/A',
    'duration': 'N/A',
    'type': 'N/A',
    'flag': 'N/A',
    'comment': 'N/A',
    'interval': 'N/A',
    'namespace': 'N/A',
    'event': 'N/A'
}

globalMetaTable = {
    'event_fake_event_log': 'Self({self})',
    'event_private_message_log': 'User[{nickname}]({user_id}) : {message}',
    'event_group_message_log': 'Host({host_id}) Group({group_id}) User[{nickname}]({user_id}) : {message}',
    'event_group_file_upload_log': 'Group({group_id}) User({user_id}) : {name}',
    'event_group_admin_log': 'Group({group_id}) User({user_id}) Action({action})',
    'event_group_member_decrease_log': 'Group({group_id}) User({user_id}) <- Operator({operator_id}) Action({action})',
    'event_group_member_increase_log': 'Group({group_id}) User({user_id}) <- Operator({operator_id}) Action({action})',
    'event_group_ban_log': 'Group({group_id}) User({user_id}) <- Operator({operator_id}) Duration({duration}) Action({action})',
    'event_friend_add_log': 'User({user_id})',
    'event_group_message_recall_log': 'Group({group_id}) User({user_id}) <- Operator({operator_id}) Message_id({message_id})',
    'event_private_message_recall_log': 'User({user_id}) Message_id({message_id})',
    'event_poke_log': 'Group({group_id}) User({user_id}) -> Target({target_id})',
    'event_group_lucky_king_log': 'Group({group_id}) User({user_id}) -> Target({target_id})',
    'event_group_honor_log': 'Group({group_id}) User({user_id}) Type({type})',
    'event_friend_add_request_log': 'User({user_id}) Flag({flag}) : {comment}',
    'event_group_add_request_log': 'Group({group_id}) User({user_id}) Flag({flag}) : {comment}',
    'event_group_invite_request_log': 'Group({group_id}) User({user_id}) Flag({flag}) : {comment}',
    'event_lifecycle_log': 'Action({action})',
    'event_heartbeat_log': 'Interval({interval})',
    'event_menu_log': 'Namespace({namespace}) Event({event})'
}

eventLogMetaTable = {
    'fake_event' : {
        'level' : 0,
        'message_key' : 'event_fake_event_log'
    },
    'private_message' : {
        'level' : 2,
        'message_key' : 'event_private_message_log'
    },
    'group_message' : {
        'level' : 2,
        'message_key' : 'event_group_message_log'
    },
    'group_file_upload' : {
        'level' : 2,
        'message_key' : 'event_group_file_upload_log'
    },
    'group_admin' : {
        'level' : 2,
        'message_key' : 'event_group_admin_log'
    },
    'group_member_decrease' : {
        'level' : 2,
        'message_key' : 'event_group_member_decrease_log'
    },
    'group_member_increase' : {
        'level' : 2,
        'message_key' : 'event_group_member_increase_log'
    },
    'group_ban' : {
        'level' : 2,
        'message_key' : 'event_group_ban_log'
    },
    'friend_add' : {
        'level' : 2,
        'message_key' : 'event_friend_add_log'
    },
    'group_message_recall' : {
        'level' : 2,
        'message_key' : 'event_group_message_recall_log'
    },
    'private_message_recall' : {
        'level' : 2,
        'message_key' : 'event_private_message_recall_log'
    },
    'poke' : {
        'level' : 2,
        'message_key' : 'event_poke_log'
    },
    'group_lucky_king' : {
        'level' : 2,
        'message_key' : 'event_group_lucky_king_log'
    },
    'group_honor' : {
        'level' : 2,
        'message_key' : 'event_group_honor_log'
    },
    'friend_add_request' : {
        'level' : 2,
        'message_key' : 'event_friend_add_request_log'
    },
    'group_add_request' : {
        'level' : 2,
        'message_key' : 'event_group_add_request_log'
    },
    'group_invite_request' : {
        'level' : 2,
        'message_key' : 'event_group_invite_request_log'
    },
    'lifecycle' : {
        'level' : 2,
        'message_key' : 'event_lifecycle_log'
    },
    'heartbeat' : {
        'level' : 1,
        'message_key' : 'event_heartbeat_log'
    },
    'menu' : {
        'level' : 2,
        'message_key' : 'event_menu_log'
    }
}

