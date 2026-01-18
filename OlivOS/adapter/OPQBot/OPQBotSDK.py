r"""
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/OPQBotSDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
"""

import copy
import hashlib
import json
import time
import traceback
import uuid
from urllib import parse

import OlivOS

gBotIdDict = {}

gResReg = {}

gUinfoReg = {}

gMsgSeqToGroupCodeReg = {}

gFriendReqTsReg = {}


class bot_info_T:
    def __init__(self, id=-1):
        self.id = id
        self.debug_mode = False
        self.debug_logger = None


def get_SDK_bot_info_from_Plugin_bot_info(plugin_bot_info):
    res = bot_info_T(id=plugin_bot_info.id)
    return res


def get_SDK_bot_info_from_Event(target_event):
    res = get_SDK_bot_info_from_Plugin_bot_info(target_event.bot_info)
    return res


class event:
    def __init__(self, payload_data=None, bot_info=None):
        self.payload = payload_data
        self.platform = {'sdk': 'onebot', 'platform': 'qq', 'model': 'opqbot_default'}
        if type(bot_info.platform) is dict:
            self.platform.update(bot_info.platform)
        self.active = False
        if self.payload is not None:
            self.active = True
        self.base_info = {}
        if self.active:
            self.base_info['time'] = int(time.time())
            self.base_info['self_id'] = self.payload.CurrentQQ
            self.base_info['post_type'] = None


def get_message(Content: str, AtUinLists: list):
    res_msg = Content
    if type(AtUinLists) is list:
        for AtUin in AtUinLists:
            res_msg = res_msg.replace(f'@{AtUin["Nick"]}', f'[OP:at,id={AtUin["Uin"]}]')
    return res_msg


def get_Event_from_SDK(target_event):
    target_event.base_info['time'] = target_event.sdk_event.base_info['time']
    target_event.base_info['self_id'] = str(target_event.sdk_event.base_info['self_id'])
    target_event.base_info['type'] = target_event.sdk_event.base_info['post_type']
    target_event.platform['sdk'] = target_event.sdk_event.platform['sdk']
    target_event.platform['platform'] = target_event.sdk_event.platform['platform']
    target_event.platform['model'] = target_event.sdk_event.platform['model']
    target_event.plugin_info['message_mode_rx'] = 'olivos_string'
    if target_event.sdk_event.payload.active:
        if target_event.sdk_event.payload.EventName == 'CgiBaseResponse':
            if (
                type(target_event.sdk_event.payload.ReqId) is int
                and type(target_event.sdk_event.payload.ResponseData) is dict
                and type(target_event.sdk_event.payload.Ret) is int
            ):
                target_event.active = False
                waitForResSet(str(target_event.sdk_event.payload.ReqId), target_event.sdk_event.payload.data)
        elif target_event.sdk_event.payload.EventName == 'ON_EVENT_GROUP_NEW_MSG':
            if (
                type(target_event.sdk_event.payload.EventData) is dict
                and 'MsgHead' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgHead']) is dict
                and 'FromUin' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']) is int
                and 'ToUin' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['ToUin']) is int
                and 'SenderUin' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['SenderUin']) is int
                and 'SenderNick' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['SenderNick']) is str
                and 'MsgBody' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgBody']) is dict
                and 'Content' in target_event.sdk_event.payload.EventData['MsgBody']
                and type(target_event.sdk_event.payload.EventData['MsgBody']['Content']) is str
            ):
                target_event.active = True
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_string',
                    get_message(
                        Content=target_event.sdk_event.payload.EventData['MsgBody']['Content'],
                        AtUinLists=target_event.sdk_event.payload.EventData['MsgBody'].get('AtUinLists', []),
                    ),
                )
                if str(target_event.sdk_event.payload.EventData['MsgHead']['SenderUin']) == str(
                    target_event.base_info['self_id']
                ):
                    target_event.plugin_info['func_type'] = 'group_message_sent'
                    target_event.data = target_event.group_message_sent(
                        str(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']),
                        str(target_event.sdk_event.payload.EventData['MsgHead']['SenderUin']),
                        message_obj,
                        'group',
                    )
                else:
                    target_event.plugin_info['func_type'] = 'group_message'
                    target_event.data = target_event.group_message(
                        str(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']),
                        str(target_event.sdk_event.payload.EventData['MsgHead']['SenderUin']),
                        message_obj,
                        'group',
                    )
                target_event.data.message_sdk = message_obj
                target_event.data.message_id = str(-1)
                target_event.data.raw_message = message_obj
                target_event.data.raw_message_sdk = message_obj
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(
                    target_event.sdk_event.payload.EventData['MsgHead']['SenderUin']
                )
                target_event.data.sender['nickname'] = target_event.sdk_event.payload.EventData['MsgHead']['SenderNick']
                target_event.data.sender['id'] = target_event.data.sender['user_id']
                target_event.data.sender['name'] = target_event.data.sender['nickname']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0
                if 'role' in target_event.data.sender:
                    target_event.data.sender.pop('role')
                target_event.data.host_id = None
        elif target_event.sdk_event.payload.EventName == 'ON_EVENT_FRIEND_NEW_MSG':
            if (
                type(target_event.sdk_event.payload.EventData) is dict
                and 'MsgHead' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgHead']) is dict
                and 'MsgType' in target_event.sdk_event.payload.EventData['MsgHead']
                and target_event.sdk_event.payload.EventData['MsgHead']['MsgType'] == 528
                and 'C2cCmd' in target_event.sdk_event.payload.EventData['MsgHead']
                and target_event.sdk_event.payload.EventData['MsgHead']['C2cCmd'] == 35
                and 'ToUin' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['ToUin']) is int
                and 'FromUin' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']) is int
                and 'FromUid' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['FromUid']) is str
            ):
                tmp_ToUin = str(target_event.sdk_event.payload.EventData['MsgHead']['ToUin'])
                tmp_FromUin = str(target_event.sdk_event.payload.EventData['MsgHead']['FromUin'])
                if tmp_ToUin != tmp_FromUin:
                    if int(time.time()) - gFriendReqTsReg.get(tmp_FromUin, -1) >= 5:
                        gFriendReqTsReg[tmp_FromUin] = int(time.time())
                        target_event.active = True
                        target_event.plugin_info['func_type'] = 'friend_add_request'
                        target_event.data = target_event.friend_add_request(tmp_FromUin, '')
                        target_event.data.flag = str(target_event.sdk_event.payload.EventData['MsgHead']['FromUid'])
            elif (
                type(target_event.sdk_event.payload.EventData) is dict
                and 'MsgHead' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgHead']) is dict
                and 'FromUin' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']) is int
                and 'ToUin' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['ToUin']) is int
                and 'MsgBody' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgBody']) is dict
                and 'Content' in target_event.sdk_event.payload.EventData['MsgBody']
                and type(target_event.sdk_event.payload.EventData['MsgBody']['Content']) is str
            ):
                target_event.active = True
                message_obj = OlivOS.messageAPI.Message_templet(
                    'olivos_string',
                    get_message(
                        Content=target_event.sdk_event.payload.EventData['MsgBody']['Content'],
                        AtUinLists=target_event.sdk_event.payload.EventData['MsgBody'].get('AtUinLists', []),
                    ),
                )
                target_event.plugin_info['func_type'] = 'private_message'
                target_event.data = target_event.private_message(
                    str(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']), message_obj, 'private'
                )
                target_event.data.message_sdk = message_obj
                target_event.data.message_id = str(-1)
                target_event.data.raw_message = message_obj
                target_event.data.raw_message_sdk = message_obj
                target_event.data.font = None
                target_event.data.sender['user_id'] = str(
                    target_event.sdk_event.payload.EventData['MsgHead']['FromUin']
                )
                target_event.data.sender['nickname'] = '用户'
                target_event.data.sender['id'] = target_event.data.sender['user_id']
                target_event.data.sender['name'] = target_event.data.sender['nickname']
                target_event.data.sender['sex'] = 'unknown'
                target_event.data.sender['age'] = 0
                target_event.data.host_id = None
        elif target_event.sdk_event.payload.EventName == 'ON_EVENT_GROUP_INVITE':
            if (
                type(target_event.sdk_event.payload.EventData) is dict
                and 'MsgHead' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgHead']) is dict
                and 'FromUin' in target_event.sdk_event.payload.EventData['MsgHead']
                and type(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']) is int
                and 'Event' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['Event']) is dict
                and 'Invitee' in target_event.sdk_event.payload.EventData['Event']
                and type(target_event.sdk_event.payload.EventData['Event']['Invitee']) in [str, int]
                and 'Invitor' in target_event.sdk_event.payload.EventData['Event']
                and type(target_event.sdk_event.payload.EventData['Event']['Invitor']) in [str, int]
            ):
                target_event.active = True
                target_event.plugin_info['func_type'] = 'group_member_increase'
                target_event.data = target_event.group_member_increase(
                    str(target_event.sdk_event.payload.EventData['MsgHead']['FromUin']),
                    str(target_event.sdk_event.payload.EventData['Event']['Invitor']),
                    str(target_event.sdk_event.payload.EventData['Event']['Invitee']),
                )
                target_event.data.action = 'approve'
        elif False and target_event.sdk_event.payload.EventName == 'ON_EVENT_FRIEND_SYSTEM_MSG_NOTIFY':
            if (
                type(target_event.sdk_event.payload.EventData) is dict
                and 'ReqUid' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['ReqUid']) is str
                and 'Status' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['Status']) is int
                and 'MsgAdditional' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgAdditional']) is str
            ):
                target_event.active = True
                target_event.plugin_info['func_type'] = 'friend_add_request'
                uin = None
                if False and OlivOS.pluginAPI.gProc is not None:
                    uin = event_action.getUinfo(
                        target_event=target_event,
                        Uid=target_event.sdk_event.payload.EventData['ReqUid'],
                        control_queue=OlivOS.pluginAPI.gProc.Proc_info.control_queue,
                    )
                if uin is None:
                    uin = -1
                target_event.data = target_event.friend_add_request(
                    str(uin), target_event.sdk_event.payload.EventData['MsgAdditional']
                )
                target_event.data.flag = str(target_event.sdk_event.payload.EventData['ReqUid'])
        elif target_event.sdk_event.payload.EventName == 'ON_EVENT_GROUP_SYSTEM_MSG_NOTIFY':
            if (
                type(target_event.sdk_event.payload.EventData) is dict
                and 'MsgType' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgType']) is int
                and 'GroupCode' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['GroupCode']) is int
                and 'MsgSeq' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgSeq']) is int
                and 'Status' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['Status']) is int
                and 'MsgAdditional' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['MsgAdditional']) is str
                and 'ActorUid' in target_event.sdk_event.payload.EventData
                and type(target_event.sdk_event.payload.EventData['ActorUid']) in [str, int]
            ):
                if (
                    target_event.sdk_event.payload.EventData['MsgType'] == 2
                    and target_event.sdk_event.payload.EventData['Status'] == 1
                ):
                    target_event.active = True
                    target_event.plugin_info['func_type'] = 'group_invite_request'
                    uin = None
                    if False and OlivOS.pluginAPI.gProc is not None:
                        uin = event_action.getUinfo(
                            target_event=target_event,
                            Uid=target_event.sdk_event.payload.EventData['ActorUid'],
                            control_queue=OlivOS.pluginAPI.gProc.Proc_info.control_queue,
                        )
                    if uin is None:
                        uin = -1
                    target_event.data = target_event.group_invite_request(
                        str(target_event.sdk_event.payload.EventData['GroupCode']),
                        str(uin),
                        target_event.sdk_event.payload.EventData['MsgAdditional'],
                    )
                    target_event.data.flag = str(target_event.sdk_event.payload.EventData['MsgSeq'])
                    gMsgSeqToGroupCodeReg[target_event.data.flag] = target_event.sdk_event.payload.EventData[
                        'GroupCode'
                    ]


"""
对于WEBSOCKET接口的PAYLOAD实现
"""


class payload_template:
    def __init__(self, data=None, is_rx=False):
        self.active = True
        self.data = None
        self.EventName = None
        self.EventData = None
        self.CurrentQQ = None
        self.ReqId = int(getHash(str(uuid.uuid4())), 16) % 1000000000000
        self.CgiCmd = None
        self.ResponseData = None
        self.CgiBaseResponse = None
        self.Ret = None
        self.load(data, is_rx)

    def dump(self):
        res = json.dumps(obj=self.data)
        return res

    def dump_CurrentPacket(self):
        res = json.dumps(
            obj={
                'CurrentPacket': {'EventData': self.EventData, 'EventName': self.EventName},
                'CurrentQQ': int(self.CurrentQQ),
            }
        )
        return res

    def load(self, data, is_rx: bool):
        self.active = False
        if (
            is_rx
            and type(data) is dict
            and 'CurrentQQ' in data
            and type(data['CurrentQQ']) in [int, str]
            and 'CurrentPacket' in data
            and type(data['CurrentPacket']) is dict
            and 'EventName' in data['CurrentPacket']
            and type(data['CurrentPacket']['EventName']) is str
            and 'EventData' in data['CurrentPacket']
            and type(data['CurrentPacket']['EventData']) is dict
        ):
            self.active = True
            self.data = data
            self.EventName = data['CurrentPacket']['EventName']
            self.EventData = data['CurrentPacket']['EventData']
            self.CurrentQQ = data['CurrentQQ']
        elif (
            is_rx
            and type(data) is dict
            and 'CgiBaseResponse' in data
            and type(data['CgiBaseResponse']) is dict
            and 'Ret' in data['CgiBaseResponse']
            and type(data['CgiBaseResponse']['Ret']) is int
            and 'ReqId' in data
            and type(data['ReqId']) is int
            and 'ResponseData' in data
            and type(data['ResponseData']) is dict
        ):
            self.active = True
            self.data = data
            self.ReqId = data['ReqId']
            self.ResponseData = data['ResponseData']
            self.CgiBaseResponse = data['CgiBaseResponse']
            self.Ret = data['CgiBaseResponse']['Ret']
            self.EventName = 'CgiBaseResponse'
        return self


def getHash(key):
    hash_tmp = hashlib.new('md5')
    hash_tmp.update(str(key).encode(encoding='UTF-8'))
    return hash_tmp.hexdigest()


def getIdBackport(id):
    res = id
    try:
        res = int(id)
    except Exception:
        res = id
    return res


class PAYLOAD:
    class rxPacket(payload_template):
        def __init__(self, data):
            payload_template.__init__(self, data, True)

    class MessageSvc_PbSendMsg(payload_template):
        def __init__(self, ToUin: 'int|str', ToType: int, Content: str, CurrentQQ: 'int|str'):
            payload_template.__init__(self)
            self.CgiCmd = 'MessageSvc.PbSendMsg'
            self.CurrentQQ = str(CurrentQQ)
            self.data = {
                'ReqId': self.ReqId,
                'BotUin': str(self.CurrentQQ),
                'CgiCmd': self.CgiCmd,
                'CgiRequest': {'ToUin': getIdBackport(ToUin), 'ToType': ToType, 'Content': Content},
            }

    class MessageSvc_PbSendMsg_all(payload_template):
        def __init__(self, ToUin: 'int|str', ToType: int, dataPatch: dict, CurrentQQ: 'int|str'):
            payload_template.__init__(self)
            self.CgiCmd = 'MessageSvc.PbSendMsg'
            self.CurrentQQ = str(CurrentQQ)
            self.data = {
                'ReqId': self.ReqId,
                'BotUin': str(self.CurrentQQ),
                'CgiCmd': self.CgiCmd,
                'CgiRequest': {'ToUin': getIdBackport(ToUin), 'ToType': ToType},
            }
            self.data['CgiRequest'].update(dataPatch)

    class exitGroup(payload_template):
        def __init__(self, Uin: 'int|str', CurrentQQ: 'int|str'):
            payload_template.__init__(self)
            self.CgiCmd = 'SsoGroup.Op'
            self.CurrentQQ = str(CurrentQQ)
            self.data = {
                'ReqId': self.ReqId,
                'BotUin': str(self.CurrentQQ),
                'CgiCmd': self.CgiCmd,
                'CgiRequest': {'OpCode': 4247, 'Uin': getIdBackport(Uin)},
            }

    class GetGroupLists(payload_template):
        def __init__(self, CurrentQQ: 'int|str'):
            payload_template.__init__(self)
            self.CgiCmd = 'GetGroupLists'
            self.CurrentQQ = str(CurrentQQ)
            self.data = {'ReqId': self.ReqId, 'BotUin': str(self.CurrentQQ), 'CgiCmd': self.CgiCmd, 'CgiRequest': {}}

    class PicUp_DataUp(payload_template):
        def __init__(
            self,
            CommandId: int,
            CurrentQQ: 'int|str',
            FilePath: 'str|None' = None,
            FileUrl: 'str|None' = None,
            Base64Buf: 'str|None' = None,
        ):
            payload_template.__init__(self)
            self.CgiCmd = 'PicUp.DataUp'
            self.CurrentQQ = str(CurrentQQ)
            self.data = {'ReqId': self.ReqId, 'BotUin': str(self.CurrentQQ), 'CgiCmd': self.CgiCmd, 'CgiRequest': {}}
            self.data['CgiRequest']['CommandId'] = CommandId
            if FilePath is not None:
                self.data['CgiRequest']['FilePath'] = FilePath
            if FileUrl is not None:
                self.data['CgiRequest']['FileUrl'] = FileUrl
            if Base64Buf is not None:
                self.data['CgiRequest']['Base64Buf'] = Base64Buf

    class QueryUinByUid(payload_template):
        def __init__(self, UidQuery: 'list[str]', CurrentQQ: 'int|str'):
            payload_template.__init__(self)
            self.CgiCmd = 'QueryUinByUid'
            self.CurrentQQ = str(CurrentQQ)
            self.data = {
                'ReqId': self.ReqId,
                'BotUin': str(self.CurrentQQ),
                'CgiCmd': self.CgiCmd,
                'CgiRequest': {'Uids': UidQuery},
            }

    class SystemMsgAction_Friend(payload_template):
        def __init__(self, ReqUid: int, OpCode: int, CurrentQQ: 'int|str'):
            payload_template.__init__(self)
            self.CgiCmd = 'SystemMsgAction.Friend'
            self.CurrentQQ = str(CurrentQQ)
            self.data = {
                'ReqId': self.ReqId,
                'BotUin': str(self.CurrentQQ),
                'CgiCmd': self.CgiCmd,
                'CgiRequest': {'ReqUid': ReqUid, 'OpCode': OpCode},
            }

    class SystemMsgAction_Group(payload_template):
        def __init__(self, MsgSeq: int, MsgType: int, GroupCode: int, OpCode: int, CurrentQQ: 'int|str'):
            payload_template.__init__(self)
            self.CgiCmd = 'SystemMsgAction.Group'
            self.CurrentQQ = str(CurrentQQ)
            self.data = {
                'ReqId': self.ReqId,
                'BotUin': str(self.CurrentQQ),
                'CgiCmd': self.CgiCmd,
                'CgiRequest': {'MsgSeq': MsgSeq, 'MsgType': MsgType, 'GroupCode': GroupCode, 'OpCode': OpCode},
            }


# 支持OlivOS API调用的方法实现
class event_action:
    def getUinfo(target_event, Uid, control_queue):
        res = Uid
        if Uid in gUinfoReg:
            res = gUinfoReg[Uid]
        else:
            res_list = event_action.getUinfoCache(
                target_event=target_event, UidQuery=[Uid], control_queue=control_queue
            )
            if len(res_list) == 1:
                res = res_list[0]
        return res

    def getUinfoCache(target_event, UidQuery, control_queue):
        res_tmp = {}
        res = []
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id=target_event.base_info['self_id'],
            platform_sdk=target_event.platform['sdk'],
            platform_platform=target_event.platform['platform'],
            platform_model=target_event.platform['model'],
        )
        this_msg = PAYLOAD.QueryUinByUid(UidQuery=UidQuery, CurrentQQ=target_event.base_info['self_id'])
        waitForResReady(str(this_msg.ReqId))
        send_ws_event(plugin_event_bot_hash, this_msg.dump(), control_queue)
        res_raw = waitForRes(str(this_msg.ReqId))
        raw_obj = init_api_json(res_raw)
        if raw_obj is not None:
            if type(raw_obj) is list:
                for raw_obj_this in raw_obj:
                    res_tmp[str(raw_obj_this['Uid'])] = raw_obj_this['Uin']
        gUinfoReg.update(res_tmp)
        for UidQuery_this in UidQuery:
            res.append(res_tmp.get(UidQuery_this, None))
        return res

    def send_solo_msg(target_event, target_type, target_id, message, control_queue):
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id=target_event.base_info['self_id'],
            platform_sdk=target_event.platform['sdk'],
            platform_platform=target_event.platform['platform'],
            platform_model=target_event.platform['model'],
        )
        if len(message) > 0:
            send_ws_event(
                plugin_event_bot_hash,
                PAYLOAD.MessageSvc_PbSendMsg(
                    ToUin=target_id,
                    ToType=2 if 'group' == target_type else 1,
                    Content=message,
                    CurrentQQ=target_event.base_info['self_id'],
                ).dump(),
                control_queue,
            )

    def send_solo_all_msg(target_event, target_type, target_id, dataPatch, control_queue):
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id=target_event.base_info['self_id'],
            platform_sdk=target_event.platform['sdk'],
            platform_platform=target_event.platform['platform'],
            platform_model=target_event.platform['model'],
        )
        if type(dataPatch) is dict:
            send_ws_event(
                plugin_event_bot_hash,
                PAYLOAD.MessageSvc_PbSendMsg_all(
                    ToUin=target_id,
                    ToType=2 if 'group' == target_type else 1,
                    dataPatch=dataPatch,
                    CurrentQQ=target_event.base_info['self_id'],
                ).dump(),
                control_queue,
            )

    def send_msg(target_event, target_type, target_id, message, control_queue):
        message_new = ''
        message_obj = OlivOS.messageAPI.Message_templet('olivos_string', message)
        count_data = 0
        size_data = len(message_obj.data)
        flag_now_type = 'string'
        flag_now_type_last = flag_now_type
        if message_obj.active:
            for data_this in message_obj.data:
                res = None
                count_data += 1
                flag_now_type_last = flag_now_type
                if type(data_this) is OlivOS.messageAPI.PARA.text:
                    message_new += data_this.data['text']
                    flag_now_type = 'string'
                elif type(data_this) is OlivOS.messageAPI.PARA.image:
                    res = event_action.setResourceUploadFast(
                        target_event=target_event,
                        control_queue=control_queue,
                        url=data_this.data['file'],
                        type_path='images',
                        type_chat=2 if 'group' == target_type else 1,
                    )
                    flag_now_type = 'image'
                if size_data == count_data or (
                    flag_now_type_last != flag_now_type and flag_now_type_last == 'string' and len(message_new) > 0
                ):
                    event_action.send_solo_msg(
                        target_event=target_event,
                        target_type=target_type,
                        target_id=target_id,
                        message=message_new,
                        control_queue=control_queue,
                    )
                    message_new = ''
                    time.sleep(1)
                    if flag_now_type == 'image':
                        if res is not None:
                            event_action.send_solo_all_msg(
                                target_event=target_event,
                                target_type=target_type,
                                target_id=target_id,
                                dataPatch={
                                    'Images': [
                                        {
                                            'FileId': res[2],
                                            'FileMd5': res[0],
                                            'FileSize': res[1],
                                            'Height': 1920,
                                            'Width': 1080,
                                        }
                                    ]
                                },
                                control_queue=control_queue,
                            )
                            time.sleep(1)

    # 现场上传的就地实现
    def setResourceUploadFast(target_event, control_queue, url: str, type_path: str = 'images', type_chat: int = 2):
        plugin_event_bot_hash = OlivOS.API.getBotHash(
            bot_id=target_event.base_info['self_id'],
            platform_sdk=target_event.platform['sdk'],
            platform_platform=target_event.platform['platform'],
            platform_model=target_event.platform['model'],
        )
        res = [None, None, None]
        data_obj = None
        try:
            if url.startswith('base64://'):
                data_obj = PAYLOAD.PicUp_DataUp(
                    CommandId=type_chat, Base64Buf=url, CurrentQQ=target_event.base_info['self_id']
                )
            else:
                url_parsed = parse.urlparse(url)
                if url_parsed.scheme in ['http', 'https']:
                    data_obj = PAYLOAD.PicUp_DataUp(
                        CommandId=type_chat, FileUrl=url, CurrentQQ=target_event.base_info['self_id']
                    )
                else:
                    file_path = url_parsed.path
                    file_path = OlivOS.contentAPI.resourcePathTransform(type_path, file_path)
                    data_obj = PAYLOAD.PicUp_DataUp(
                        CommandId=type_chat, FilePath=file_path, CurrentQQ=target_event.base_info['self_id']
                    )

            if data_obj is not None:
                waitForResReady(str(data_obj.ReqId))
                send_ws_event(plugin_event_bot_hash, data_obj.dump(), control_queue)
                res_raw = waitForRes(str(data_obj.ReqId))
                raw_obj = init_api_json(res_raw)
                if raw_obj is not None:
                    if (
                        type(raw_obj) is dict
                        and 'FileMd5' in raw_obj
                        and type(raw_obj['FileMd5']) is str
                        and 'FileSize' in raw_obj
                        and type(raw_obj['FileSize']) is int
                        and 'FileId' in raw_obj
                        and type(raw_obj['FileId']) is int
                    ):
                        res = [raw_obj['FileMd5'], raw_obj['FileSize'], raw_obj['FileId']]
        except Exception:
            traceback.print_exc()
            res = [None, None, None]
        return res

    def set_group_leave(target_event, group_id, control_queue):
        if target_event.bot_info is not None:
            plugin_event_bot_hash = OlivOS.API.getBotHash(
                bot_id=target_event.base_info['self_id'],
                platform_sdk=target_event.platform['sdk'],
                platform_platform=target_event.platform['platform'],
                platform_model=target_event.platform['model'],
            )
            send_ws_event(
                plugin_event_bot_hash,
                PAYLOAD.exitGroup(Uin=group_id, CurrentQQ=target_event.base_info['self_id']).dump(),
                control_queue,
            )

    def set_friend_add_request(target_event, flag: str, approve: bool, control_queue):
        if target_event.bot_info is not None:
            plugin_event_bot_hash = OlivOS.API.getBotHash(
                bot_id=target_event.base_info['self_id'],
                platform_sdk=target_event.platform['sdk'],
                platform_platform=target_event.platform['platform'],
                platform_model=target_event.platform['model'],
            )
            OpCode_int = 3 if approve is True else 5
            send_ws_event(
                plugin_event_bot_hash,
                PAYLOAD.SystemMsgAction_Friend(
                    ReqUid=flag, OpCode=OpCode_int, CurrentQQ=target_event.base_info['self_id']
                ).dump(),
                control_queue,
            )

    def set_group_add_request(target_event, flag: str, sub_type: str, approve: bool, control_queue):
        if target_event.bot_info is not None:
            plugin_event_bot_hash = OlivOS.API.getBotHash(
                bot_id=target_event.base_info['self_id'],
                platform_sdk=target_event.platform['sdk'],
                platform_platform=target_event.platform['platform'],
                platform_model=target_event.platform['model'],
            )
            sub_type_int = None
            OpCode_int = None
            GroupCode_this = None
            if sub_type == 'invite':
                sub_type_int = 2
                GroupCode_this = gMsgSeqToGroupCodeReg.get(str(flag), None)
                if approve is True:
                    OpCode_int = 1
                else:
                    OpCode_int = 2
            elif sub_type == 'add':
                pass
            if sub_type_int is not None:
                send_ws_event(
                    plugin_event_bot_hash,
                    PAYLOAD.SystemMsgAction_Group(
                        MsgSeq=int(flag),
                        MsgType=sub_type_int,
                        GroupCode=GroupCode_this,
                        OpCode=OpCode_int,
                        CurrentQQ=target_event.base_info['self_id'],
                    ).dump(),
                    control_queue,
                )

    def get_group_list(target_event: OlivOS.API.Event, control_queue):
        res_data = OlivOS.contentAPI.api_result_data_template.get_group_list()
        if target_event.bot_info is not None:
            plugin_event_bot_hash = OlivOS.API.getBotHash(
                bot_id=target_event.base_info['self_id'],
                platform_sdk=target_event.platform['sdk'],
                platform_platform=target_event.platform['platform'],
                platform_model=target_event.platform['model'],
            )
            this_msg = PAYLOAD.GetGroupLists(CurrentQQ=target_event.base_info['self_id'])
            waitForResReady(str(this_msg.ReqId))
            send_ws_event(plugin_event_bot_hash, this_msg.dump(), control_queue)
            res_raw = waitForRes(str(this_msg.ReqId))
            raw_obj = init_api_json(res_raw)
            if raw_obj is not None:
                if type(raw_obj) is dict and 'GroupLists' in raw_obj and type(raw_obj['GroupLists']) is list:
                    res_data['active'] = True
                    for raw_obj_this in raw_obj['GroupLists']:
                        tmp_res_data_this = OlivOS.contentAPI.api_result_data_template.get_user_info_strip()
                        tmp_res_data_this['name'] = init_api_do_mapping_for_dict(raw_obj_this, ['GroupName'], str)
                        tmp_res_data_this['id'] = init_api_do_mapping_for_dict(raw_obj_this, ['GroupCode'], int)
                        tmp_res_data_this['memo'] = ''
                        tmp_res_data_this['member_count'] = init_api_do_mapping_for_dict(
                            raw_obj_this, ['MemberCnt'], int
                        )
                        tmp_res_data_this['max_member_count'] = init_api_do_mapping_for_dict(
                            raw_obj_this, ['GroupCnt'], int
                        )
                        res_data['data'].append(tmp_res_data_this)
        return res_data


def sendControlEventSend(action, data, control_queue):
    if control_queue is not None:
        control_queue.put(OlivOS.API.Control.packet(action, data), block=False)


def send_ws_event(hash, data, control_queue):
    sendControlEventSend(
        'send',
        {'target': {'type': 'OPQBot_link', 'hash': hash}, 'data': {'action': 'send', 'data': data}},
        control_queue,
    )


def init_api_json(raw: dict):
    res_data = None
    if (
        type(raw) is dict
        and 'CgiBaseResponse' in raw
        and type(raw['CgiBaseResponse']) is dict
        and 'Ret' in raw['CgiBaseResponse']
        and type(raw['CgiBaseResponse']['Ret']) is int
        and raw['CgiBaseResponse']['Ret'] == 0
        and 'ReqId' in raw
        and type(raw['ReqId']) is int
        and 'ResponseData' in raw
        and type(raw['ResponseData']) in [dict, list]
    ):
        res_data = copy.deepcopy(raw['ResponseData'])
    return res_data


def init_api_do_mapping(src_type, src_data):
    if type(src_data) is src_type:
        return src_data


def init_api_do_mapping_for_dict(src_data, path_list, src_type):
    res_data = None
    tmp_src_data = src_data
    for path_list_this in path_list:
        if type(tmp_src_data) is dict:
            if path_list_this in tmp_src_data:
                tmp_src_data = tmp_src_data[path_list_this]
            else:
                return None
        else:
            return None
    res_data = init_api_do_mapping(src_type, tmp_src_data)
    return res_data


def waitForResSet(echo: str, data):
    if echo in gResReg:
        gResReg[echo] = data


def waitForResReady(echo: str):
    gResReg[echo] = None


def waitForRes(echo: str):
    res = None
    interval = 0.1
    limit = 30
    index_limit = int(limit / interval)
    for i in range(index_limit):
        time.sleep(interval)
        if echo in gResReg and gResReg[echo] is not None:
            res = gResReg[echo]
            gResReg.pop(echo)
            break
    return res
