'''Shared fixtures and capability tables for adapter business tests.'''

import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import requests

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as qq_common


SDK_PLATFORMS = {
    'onebotSDK': ('onebot', 'qq', 'default'),
    'onebotV12SDK': ('onebot', 'qq', 'onebotV12'),
    'milkySDK': ('onebot', 'qq', 'milky_default'),
    'virtualTerminalSDK': ('terminal_link', 'terminal', 'default'),
    'qqGuildSDK': ('qqGuild_link', 'qqGuild', 'default'),
    'qqGuildv2SDK': ('qqGuildv2_link', 'qqGuild', 'public'),
    'discordSDK': ('discord_link', 'discord', 'default'),
    'telegramSDK': ('telegram_poll', 'telegram', 'default'),
    'fanbookSDK': ('fanbook_poll', 'fanbook', 'default'),
    'dodoSDK': ('dodo_poll', 'dodo', 'default'),
    'dodoLinkSDK': ('dodo_link', 'dodo', 'v2'),
    'dodobotEASDK': ('dodobot_ea', 'dodo', 'default'),
    'kaiheilaSDK': ('kaiheila_link', 'kaiheila', 'default'),
    'xiaoheiheSDK': ('xiaoheihe_link', 'xiaoheihe', 'default'),
    'biliLiveSDK': ('biliLive_link', 'biliLive', 'default'),
    'OPQBotSDK': ('onebot', 'qq', 'opqbot_default'),
    'mhyVilaSDK': ('mhyVila_link', 'mhyVila', 'default'),
    'qqRedSDK': ('onebot', 'qq', 'red'),
    'hackChatSDK': ('hackChat_link', 'hackChat', 'default'),
    'dingtalkSDK': ('dingtalk_link', 'dingtalk', 'default'),
}


def make_bot(name):
    sdk, platform, model = SDK_PLATFORMS[name]
    bot = OlivOS.API.bot_info_T(
        id=10001,
        platform_sdk=sdk,
        platform_platform=platform,
        platform_model=model,
        host='fixture-room',
        access_token='fixture-token',
    )
    bot.extends = {'app_key': 'fixture-key', 'app_secret': 'fixture-secret'}
    return bot


def prepare_sdk(name, bot, monkeypatch):
    module = getattr(OlivOS, name)
    network = Mock(side_effect=AssertionError('Event conversion must remain offline'))
    monkeypatch.setattr(requests.sessions.Session, 'request', network)
    if hasattr(module, 'sdkSubSelfInfo'):
        monkeypatch.setattr(module, 'sdkSubSelfInfo', {bot.hash: '10001'})
    if name == 'dingtalkSDK':
        monkeypatch.setattr(module, 'sdkSubSelfInfo', {})
    if name == 'onebotSDK':
        monkeypatch.setattr(module, 'gFlagCheckList', [])
    if name == 'OPQBotSDK':
        monkeypatch.setattr(module, 'gFriendReqTsReg', {})
    if name == 'dodoLinkSDK':
        monkeypatch.setattr(module, 'sdkUserInfo', {'9': {'42': {'nickName': 'tester', 'sex': 1}}})
    if name == 'kaiheilaSDK':
        monkeypatch.setattr(module, 'get_guild_admin_role_id', lambda *args: [])
    if name == 'xiaoheiheSDK':
        monkeypatch.setattr(module, 'get_room_admin_role_id', lambda *args: [])
    if name == 'hackChatSDK':
        monkeypatch.setattr(module, 'gBotIdDict', {})
    if name == 'mhyVilaSDK':
        monkeypatch.setattr(module, 'sdkNameDict', {})
    if name == 'qqGuildv2SDK':
        monkeypatch.setattr(qq_common, 'sdkSelfInfo', {bot.hash: {'id': '10001', 'username': 'bot'}})
        for field in ('qqEventDedupeCache', 'sdkUserInfo', 'sdkSubSelfInfo', 'sdkRxMessageInfo', 'sdkMsgIdxInfo'):
            monkeypatch.setattr(qq_common, field, {})
        monkeypatch.setattr(qq_common, '_get_qq_group_self_open_id', lambda *args: '10001')
    return module, network


def make_sdk_group_event(name, module, bot, text='hello', unsupported=False):
    user = {'id': '42', 'username': 'tester', 'first_name': 'tester', 'is_master': False, 'roles': []}
    if name == 'onebotSDK':
        return module.event(
            json.dumps(
                {
                    'time': 1750000000,
                    'self_id': 10001,
                    'post_type': 'unknown' if unsupported else 'message',
                    'message_type': 'group',
                    'sub_type': 'normal',
                    'group_id': 7,
                    'user_id': 42,
                    'message_id': 8,
                    'message': text,
                    'raw_message': text,
                    'font': 0,
                    'sender': {'user_id': 42, 'nickname': 'tester', 'role': 'member'},
                }
            )
        )
    if name == 'onebotV12SDK':
        return module.event(
            {
                'type': 'unknown' if unsupported else 'message',
                'detail_type': 'group',
                'group_id': '7',
                'user_id': '42',
                'user_name': 'tester',
                'message_id': '8',
                'message': [{'type': 'text', 'data': {'text': text}}],
            },
            module.get_SDK_bot_info_from_Plugin_bot_info(bot),
        )
    if name == 'milkySDK':
        return module.event(
            {
                'time': 1750000000,
                'self_id': 10001,
                'event_type': 'unknown' if unsupported else 'message_receive',
                'data': {
                    'message_scene': 'group',
                    'peer_id': 7,
                    'sender_id': 42,
                    'message_seq': 8,
                    'segments': [{'type': 'text', 'data': {'text': text}}],
                    'group_member': {'user_id': 42, 'nickname': 'tester'},
                },
            }
        )
    if name == 'virtualTerminalSDK':
        if unsupported:
            return module.event({'type': 'unsupported'}, bot, model='postapi')
        packet = OlivOS.API.Control.packet(
            'send',
            {
                'data': {
                    'data': text,
                    'user_conf': {'user_id': '42', 'target_id': '7', 'user_name': 'tester', 'flag_group': True},
                }
            },
        )
        return module.event(packet, bot)
    if name in ('qqGuildSDK', 'discordSDK'):
        payload = module.PAYLOAD.rxPacket(
            {
                'op': 0,
                's': 1,
                't': 'UNKNOWN' if unsupported else 'MESSAGE_CREATE',
                'd': {'id': '8', 'channel_id': '7', 'guild_id': '9', 'content': text, 'author': user},
            }
        )
        return module.event(payload, bot)
    if name == 'qqGuildv2SDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'op': 0,
                's': 1,
                't': 'UNKNOWN' if unsupported else 'GROUP_AT_MESSAGE_CREATE',
                'd': {
                    'id': '8',
                    'group_openid': '7',
                    'author': {'member_openid': '42', 'username': 'tester'},
                    'content': text,
                    'timestamp': '2026-09-22T12:00:00+08:00',
                },
            }
        )
        return module.event(payload, bot)
    if name == 'telegramSDK':
        body = (
            {}
            if unsupported
            else {
                'message': {
                    'date': 1750000000,
                    'message_id': 8,
                    'text': text,
                    'chat': {'id': 7, 'type': 'group'},
                    'from': user,
                }
            }
        )
        return module.event(body, bot_info=bot)
    if name == 'fanbookSDK':
        body = (
            {}
            if unsupported
            else {
                'channel_post': {
                    'message_id': 8,
                    'text': text,
                    'from': user,
                    'chat': {'id': 7, 'type': 'channel', 'guild_id': 9},
                }
            }
        )
        return module.event(body, bot)
    if name == 'dodoSDK':
        body = (
            {}
            if unsupported
            else {'channelId': '7', 'uid': '42', 'id': '8', 'content': text, 'resourceJson': '', 'nickName': 'tester'}
        )
        return module.event(body, bot, islandId='9')
    if name == 'dodoLinkSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'type': 0,
                'data': {
                    'eventType': 'unknown' if unsupported else '2001',
                    'eventBody': {
                        'messageType': 1,
                        'messageBody': {'content': text},
                        'islandSourceId': '9',
                        'dodoSourceId': '42',
                        'channelId': '7',
                        'messageId': '8',
                    },
                },
            }
        )
        return module.event(payload, bot)
    if name == 'dodobotEASDK':
        return module.event(
            {
                'FromChannel': '7',
                'Uid': '42',
                'Id': '8',
                'NickName': 'tester',
                'Content': None if unsupported else text,
                'OriginalContent': text,
            },
            bot,
        )
    if name == 'kaiheilaSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                's': 0,
                'd': {
                    'channel_type': 'UNKNOWN' if unsupported else 'GROUP',
                    'type': 1,
                    'content': text,
                    'target_id': '7',
                    'author_id': '42',
                    'msg_id': '8',
                    'extra': {'author': user, 'guild_id': '9'},
                },
            }
        )
        return module.event(payload, bot)
    if name == 'xiaoheiheSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'type': 'unknown' if unsupported else '5',
                'data': {
                    'room_id': '9',
                    'channel_id': '7',
                    'msg_id': '8',
                    'user_id': '42',
                    'nickname': 'tester',
                    'msg': text,
                    'is_master': False,
                    'roles': [],
                },
            }
        )
        return module.event(payload, bot)
    if name == 'biliLiveSDK':
        from OlivOS.thirdPartyModule.blivedm.models import DanmakuMessage, HeartbeatMessage

        payload = HeartbeatMessage(1) if unsupported else DanmakuMessage(msg=text, uid=42, uname='tester')
        return module.event(payload, bot)
    if name == 'OPQBotSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'CurrentQQ': 10001,
                'CurrentPacket': {
                    'EventName': 'UNKNOWN' if unsupported else 'ON_EVENT_GROUP_NEW_MSG',
                    'EventData': {
                        'MsgHead': {'FromUin': 7, 'ToUin': 10001, 'SenderUin': 42, 'SenderNick': 'tester'},
                        'MsgBody': {'Content': text},
                    },
                },
            }
        )
        return module.event(payload, bot)
    if name == 'mhyVilaSDK':
        body = {
            'type': 'Unknown' if unsupported else 'SendMessage',
            'extendData': {
                'sendMessage': {
                    'objectName': 'Text',
                    'villaId': '9',
                    'roomId': '7',
                    'msgUid': '8',
                    'nickname': 'tester',
                    'fromUserId': '42',
                    'content': json.dumps({'content': {'text': text, 'entities': []}}),
                }
            },
        }
        return module.event(module.protoEnum.Model_ROBOTEVENT.value, body, bot)
    if name == 'qqRedSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'type': 'unknown' if unsupported else 'message::recv',
                'payload': [
                    {
                        'chatType': 2,
                        'peerUid': '7',
                        'senderUin': '42',
                        'sendNickName': 'tester',
                        'sendMemberName': '',
                        'elements': [{'textElement': {'content': text}}],
                    }
                ],
            }
        )
        return module.event(payload, bot)
    if name == 'hackChatSDK':
        payload = module.PAYLOAD.rxPacket(
            {'cmd': 'unknown' if unsupported else 'chat', 'nick': 'tester', 'userid': '42', 'text': text}
        )
        return module.event(payload, bot)
    if name == 'dingtalkSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'type': 'UNKNOWN' if unsupported else 'CALLBACK',
                'headers': {'messageId': '8', 'topic': '/v1.0/im/bot/messages/get'},
                'data': json.dumps(
                    {
                        'chatbotUserId': 'bot',
                        'msgtype': 'text',
                        'text': {'content': text},
                        'conversationType': '2',
                        'conversationId': '7',
                        'senderStaffId': '42',
                        'senderNick': 'tester',
                    }
                ),
            }
        )
        return module.event(payload, bot)
    raise AssertionError('Missing SDK fixture: ' + name)


def make_sdk_private_event(name, module, bot, text='hello'):
    user = {'id': '42', 'username': 'tester', 'first_name': 'tester'}
    if name == 'onebotSDK':
        return module.event(
            json.dumps(
                {
                    'time': 1750000000,
                    'self_id': 10001,
                    'post_type': 'message',
                    'message_type': 'private',
                    'sub_type': 'friend',
                    'user_id': 42,
                    'message_id': 8,
                    'message': text,
                    'raw_message': text,
                    'font': 0,
                    'sender': {'user_id': 42, 'nickname': 'tester'},
                }
            )
        )
    if name == 'onebotV12SDK':
        return module.event(
            {
                'type': 'message',
                'detail_type': 'private',
                'user_id': '42',
                'user_name': 'tester',
                'message_id': '8',
                'message': [{'type': 'text', 'data': {'text': text}}],
            },
            module.get_SDK_bot_info_from_Plugin_bot_info(bot),
        )
    if name == 'milkySDK':
        return module.event(
            {
                'time': 1750000000,
                'self_id': 10001,
                'event_type': 'message_receive',
                'data': {
                    'message_scene': 'friend',
                    'peer_id': 42,
                    'sender_id': 42,
                    'message_seq': 8,
                    'segments': [{'type': 'text', 'data': {'text': text}}],
                    'friend': {'user_id': 42, 'nickname': 'tester'},
                },
            }
        )
    if name == 'virtualTerminalSDK':
        packet = OlivOS.API.Control.packet(
            'send',
            {
                'data': {
                    'data': text,
                    'user_conf': {'user_id': '42', 'target_id': '42', 'user_name': 'tester', 'flag_group': False},
                }
            },
        )
        return module.event(packet, bot)
    if name in ('qqGuildSDK', 'discordSDK'):
        payload = module.PAYLOAD.rxPacket(
            {
                'op': 0,
                's': 1,
                't': 'DIRECT_MESSAGE_CREATE',
                'd': {'id': '8', 'channel_id': '7', 'guild_id': '9', 'content': text, 'author': user},
            }
        )
        return module.event(payload, bot)
    if name == 'telegramSDK':
        return module.event(
            {
                'message': {
                    'date': 1750000000,
                    'message_id': 8,
                    'text': text,
                    'chat': {'id': 42, 'type': 'private'},
                    'from': user,
                }
            },
            bot_info=bot,
        )
    if name == 'dodoLinkSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'type': 0,
                'data': {
                    'eventType': '1001',
                    'eventBody': {
                        'messageType': 1,
                        'messageBody': {'content': text},
                        'dodoSourceId': '42',
                        'personal': {'nickName': 'tester', 'sex': 1},
                        'messageId': '8',
                    },
                },
            }
        )
        return module.event(payload, bot)
    if name == 'OPQBotSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'CurrentQQ': 10001,
                'CurrentPacket': {
                    'EventName': 'ON_EVENT_FRIEND_NEW_MSG',
                    'EventData': {
                        'MsgHead': {
                            'ToUin': 10001,
                            'FromUin': 42,
                            'FromUid': 'uid-42',
                        },
                        'MsgBody': {'Content': text},
                    },
                },
            }
        )
        return module.event(payload, bot)
    if name == 'qqRedSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'type': 'message::recv',
                'payload': [{'chatType': 1, 'peerUin': '42', 'elements': [{'textElement': {'content': text}}]}],
            }
        )
        return module.event(payload, bot)
    if name == 'dingtalkSDK':
        payload = module.PAYLOAD.rxPacket(
            {
                'type': 'CALLBACK',
                'headers': {'messageId': '8', 'topic': '/v1.0/im/bot/messages/get'},
                'data': json.dumps(
                    {
                        'chatbotUserId': 'bot',
                        'msgtype': 'text',
                        'text': {'content': text},
                        'conversationType': '1',
                        'conversationId': '42',
                        'senderStaffId': '42',
                        'senderNick': 'tester',
                    }
                ),
            }
        )
        return module.event(payload, bot)
    raise AssertionError('Missing private-message fixture: ' + name)


def make_sdk_notice_event(name, module, bot, capability, text='notice'):
    if name == 'onebotSDK':
        payload = {'time': 1750000000, 'self_id': 10001}
        if capability == 'group_member_increase':
            payload.update(post_type='notice', notice_type='group_increase', sub_type='approve', group_id=7,
                           user_id=42, operator_id=5)
        elif capability == 'group_member_decrease':
            payload.update(post_type='notice', notice_type='group_decrease', sub_type='kick', group_id=7,
                           user_id=42, operator_id=5)
        elif capability == 'group_ban':
            payload.update(post_type='notice', notice_type='group_ban', sub_type='ban', group_id=7,
                           user_id=42, operator_id=5, duration=60)
        elif capability == 'group_message_recall':
            payload.update(post_type='notice', notice_type='group_recall', group_id=7, user_id=42,
                           operator_id=5, message_id=8)
        elif capability == 'private_message_recall':
            payload.update(post_type='notice', notice_type='friend_recall', user_id=42, message_id=8)
        elif capability == 'friend_add':
            payload.update(post_type='notice', notice_type='friend_add', user_id=42)
        elif capability == 'poke':
            payload.update(post_type='notice', notice_type='notify', sub_type='poke', group_id=7,
                           user_id=42, target_id=10001)
        elif capability == 'friend_add_request':
            payload.update(post_type='request', request_type='friend', flag='fixture-friend-request',
                           user_id=42, comment='hello')
        elif capability == 'group_add_request':
            payload.update(post_type='request', request_type='group', sub_type='add', flag='fixture-group-add',
                           group_id=7, user_id=42, comment='hello')
        elif capability == 'group_invite_request':
            payload.update(post_type='request', request_type='group', sub_type='invite', flag='fixture-group-invite',
                           group_id=7, user_id=42, comment='hello')
        elif capability == 'lifecycle':
            payload.update(post_type='meta_event', meta_event_type='lifecycle', sub_type='enable')
        elif capability == 'heartbeat':
            payload.update(post_type='meta_event', meta_event_type='heartbeat', interval=5000)
        else:
            raise AssertionError('Missing OneBot notice fixture: ' + capability)
        return module.event(json.dumps(payload))
    if name == 'onebotV12SDK':
        if capability == 'group_member_increase':
            payload = {'type': 'notice', 'detail_type': capability, 'group_id': '7', 'user_id': '42',
                       'operator_id': '5', 'sub_type': 'approve'}
        elif capability == 'group_member_decrease':
            payload = {'type': 'notice', 'detail_type': capability, 'group_id': '7', 'user_id': '42',
                       'operator_id': '5', 'sub_type': 'kick'}
        elif capability == 'group_ban':
            payload = {'type': 'notice', 'detail_type': 'group_member_ban', 'group_id': '7', 'user_id': '42',
                       'operator_id': '5', 'duration': 60}
        elif capability == 'group_message_recall':
            payload = {'type': 'notice', 'detail_type': 'group_message_delete', 'group_id': '7', 'user_id': '42',
                       'operator_id': '5', 'message_id': '8'}
        elif capability == 'private_message_recall':
            payload = {'type': 'notice', 'detail_type': 'private_message_delete', 'user_id': '42', 'message_id': '8'}
        elif capability == 'friend_add':
            payload = {'type': 'notice', 'detail_type': 'friend_increase', 'user_id': '42'}
        elif capability == 'friend_add_request':
            payload = {'type': 'request', 'detail_type': 'new_friend', 'request_id': 'fixture-friend-request',
                       'user_id': '42', 'message': 'hello'}
        elif capability == 'group_add_request':
            payload = {'type': 'request', 'detail_type': 'join_group', 'request_id': 'fixture-group-add',
                       'group_id': '7', 'user_id': '42', 'message': 'hello'}
        elif capability == 'group_invite_request':
            payload = {'type': 'request', 'detail_type': 'group_invited', 'request_id': 'fixture-group-invite',
                       'group_id': '7', 'user_id': '42', 'invitor_id': '42', 'message': 'hello'}
        elif capability == 'lifecycle':
            payload = {'type': 'meta', 'detail_type': 'connect'}
        elif capability == 'heartbeat':
            payload = {'type': 'meta', 'detail_type': 'heartbeat', 'interval': 5}
        else:
            raise AssertionError('Missing OneBot V12 notice fixture: ' + capability)
        return module.event(payload, module.get_SDK_bot_info_from_Plugin_bot_info(bot))
    if name == 'milkySDK':
        event_type = {
            'group_member_increase': 'group_member_increase',
            'group_member_decrease': 'group_member_decrease',
            'group_ban': 'group_mute',
            'group_message_recall': 'message_recall',
            'private_message_recall': 'message_recall',
            'friend_add_request': 'friend_request',
            'group_add_request': 'group_join_request',
            'group_invite_request': 'group_invitation',
            'poke': 'group_nudge',
            'lifecycle': 'bot_offline',
        }[capability]
        data = {}
        if capability in ('group_member_increase', 'group_member_decrease'):
            data = {'group_id': 7, 'user_id': 42, 'operator_id': 5}
        elif capability == 'group_ban':
            data = {'group_id': 7, 'user_id': 42, 'operator_id': 5, 'duration': 60}
        elif capability == 'group_message_recall':
            data = {'message_scene': 'group', 'peer_id': 7, 'sender_id': 42, 'operator_id': 5, 'message_seq': 8}
        elif capability == 'private_message_recall':
            data = {'message_scene': 'friend', 'peer_id': 42, 'operator_id': 5, 'message_seq': 8}
        elif capability == 'friend_add_request':
            data = {'initiator_id': 42, 'initiator_uid': 'uid-42', 'comment': 'hello'}
        elif capability == 'group_add_request':
            data = {'group_id': 7, 'initiator_id': 42, 'notification_seq': 8, 'comment': 'hello'}
        elif capability == 'group_invite_request':
            data = {'group_id': 7, 'initiator_id': 42, 'invitation_seq': 8, 'comment': 'hello'}
        elif capability == 'poke':
            data = {'group_id': 7, 'sender_id': 42, 'receiver_id': 10001}
        payload = {'time': 1750000000, 'self_id': 10001, 'event_type': event_type}
        if data:
            payload['data'] = data
        return module.event(payload)
    if name == 'xiaoheiheSDK' and capability in ('group_member_increase', 'group_member_decrease'):
        payload = module.PAYLOAD.rxPacket(
            {
                'type': '3001',
                'data': {
                    'room_base_info': {'room_id': '9'},
                    'user_info': {'user_id': '42'},
                    'state': 1 if capability == 'group_member_increase' else 0,
                },
            }
        )
        return module.event(payload, bot)
    if name == 'OPQBotSDK' and capability == 'group_member_increase':
        payload = module.PAYLOAD.rxPacket(
            {
                'CurrentQQ': 10001,
                'CurrentPacket': {
                    'EventName': 'ON_EVENT_GROUP_INVITE',
                    'EventData': {
                        'MsgHead': {'FromUin': 7},
                        'Event': {'Invitor': 5, 'Invitee': 42},
                    },
                },
            }
        )
        return module.event(payload, bot)
    raise AssertionError('Missing notice fixture: ' + name + '/' + capability)


def make_sdk_event(name, module, bot, capability, text='hello'):
    builder = INBOUND_BUILDERS.get(capability)
    if builder is None:
        raise AssertionError('Missing inbound builder: ' + capability)
    if capability in ('group_message', 'private_message'):
        return builder(name, module, bot, text)
    return make_sdk_notice_event(name, module, bot, capability, text)


def expected_group_id(name):
    return {'biliLiveSDK': '10001', 'hackChatSDK': '0'}.get(name, '7')


def inbound(func_type, **checks):
    return NS(func_type=func_type, checks=checks)


def outbound(method, target_aware=True, event='group_message'):
    return NS(method=method, target_aware=target_aware, event=event)


def adapter_action(method, event_method, args=(), expected=(), event='group_message'):
    return NS(method=method, event_method=event_method, args=args, expected=expected, event=event)


ADAPTER_BUSINESS_CASES = {
    # OneBot V11：覆盖群/私聊消息、通知、请求、生命周期，以及常用查询和管理接口。
    'onebotSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
            'group_member_increase': inbound('group_member_increase', group_id='7', user_id='42'),
            'group_member_decrease': inbound('group_member_decrease', group_id='7', user_id='42'),
            'group_ban': inbound('group_ban', group_id='7', user_id='42', duration=60),
            'group_message_recall': inbound('group_message_recall', group_id='7', message_id='8'),
            'private_message_recall': inbound('private_message_recall', user_id='42', message_id='8'),
            'friend_add': inbound('friend_add', user_id='42'),
            'poke': inbound('poke', user_id='42', target_id='10001'),
            'friend_add_request': inbound('friend_add_request', user_id='42'),
            'group_add_request': inbound('group_add_request', group_id='7', user_id='42'),
            'group_invite_request': inbound('group_invite_request', group_id='7', user_id='42'),
            'lifecycle': inbound('lifecycle', action='enable'),
            'heartbeat': inbound('heartbeat'),
        },
        outbound={
            'reply_group': outbound('send_group_msg'),
            'send_group': outbound('send_group_msg'),
            'reply_private': outbound('send_private_msg', event='private_message'),
            'send_private': outbound('send_private_msg', event='private_message'),
        },
        actions={
            'delete_message': adapter_action('delete_msg', 'delete_msg', (8,), (8,)),
            'get_group_info': adapter_action('get_group_info', 'get_group_info', (7,), (7,)),
            'get_group_member_info': adapter_action(
                'get_group_member_info', 'get_group_member_info', (7, 42), (7, 42)
            ),
            'set_group_ban': adapter_action('set_group_ban', 'set_group_ban', (7, 42, None, 60), (7, 42, 60)),
            'set_group_kick': adapter_action('set_group_kick', 'set_group_kick', (7, 42), (7, 42)),
            'group_poke': adapter_action('group_poke', 'group_poke', (7, 42), (7, 42)),
            'set_friend_add_request': adapter_action(
                'set_friend_add_request', 'set_friend_add_request',
                ('fixture-flag', True, 'remark'), ('fixture-flag', True)
            ),
            'set_group_add_request': adapter_action(
                'set_group_add_request', 'set_group_add_request',
                ('fixture-flag', 'add', True, 'reason'), ('fixture-flag', 'add', True)
            ),
            'get_login_info': adapter_action('get_login_info', 'get_login_info'),
            'get_group_list': adapter_action('get_group_list', 'get_group_list'),
            'get_group_member_list': adapter_action('get_group_member_list', 'get_group_member_list', (7,), (7,)),
        },
    ),
    # OneBot V12：覆盖群/私聊消息、通知、请求、生命周期，以及查询和管理接口。
    'onebotV12SDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
            'group_member_increase': inbound('group_member_increase', group_id='7', user_id='42'),
            'group_member_decrease': inbound('group_member_decrease', group_id='7', user_id='42'),
            'group_ban': inbound('group_ban', group_id='7', user_id='42', duration=60),
            'group_message_recall': inbound('group_message_recall', group_id='7', message_id='8'),
            'private_message_recall': inbound('private_message_recall', user_id='42', message_id='8'),
            'friend_add': inbound('friend_add', user_id='42'),
            'friend_add_request': inbound('friend_add_request', user_id='42'),
            'group_add_request': inbound('group_add_request', group_id='7', user_id='42'),
            'group_invite_request': inbound('group_invite_request', group_id='7'),
            'lifecycle': inbound('lifecycle', action='connect'),
            'heartbeat': inbound('heartbeat'),
        },
        outbound={
            'reply_group': outbound('send_group_msg'),
            'send_group': outbound('send_group_msg'),
            'reply_private': outbound('send_private_msg', event='private_message'),
            'send_private': outbound('send_private_msg', event='private_message'),
        },
        actions={
            'delete_message': adapter_action('delete_msg', 'delete_msg', (8,), (8,)),
            'get_group_info': adapter_action('get_group_info', 'get_group_info', (7,), (7,)),
            'get_group_member_info': adapter_action(
                'get_group_member_info', 'get_group_member_info', (7, 42), (7, 42)
            ),
            'set_group_ban': adapter_action('set_group_ban', 'set_group_ban', (7, 42, None, 60), (7, 42, 60)),
            'set_group_kick': adapter_action('set_group_kick', 'set_group_kick', (7, 42), (7, 42)),
            'set_friend_add_request': adapter_action(
                'set_friend_add_request', 'set_friend_add_request',
                ('fixture-flag', True, 'remark'), ('fixture-flag', True)
            ),
            'set_group_add_request': adapter_action(
                'set_group_add_request', 'set_group_add_request',
                ('fixture-flag', 'add', True, 'reason'), ('fixture-flag', 'add', True)
            ),
            'get_login_info': adapter_action('get_login_info', 'get_login_info'),
            'get_group_list': adapter_action('get_group_list', 'get_group_list'),
            'get_group_member_list': adapter_action('get_group_member_list', 'get_group_member_list', (7,), (7,)),
        },
    ),
    # Milky：入站通知能力完整；出站仍受 SDK 标记与 Event 路由不一致影响，故显式豁免。
    'milkySDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
            'group_member_increase': inbound('group_member_increase', group_id='7', user_id='42'),
            'group_member_decrease': inbound('group_member_decrease', group_id='7', user_id='42'),
            'group_ban': inbound('group_ban', group_id='7', user_id='42', duration=60),
            'group_message_recall': inbound('group_message_recall'),
            'private_message_recall': inbound('private_message_recall'),
            'friend_add_request': inbound('friend_add_request', user_id='42'),
            'group_add_request': inbound('group_add_request', group_id='7'),
            'group_invite_request': inbound('group_invite_request', group_id='7'),
            'poke': inbound('poke', target_id='10001'),
            'lifecycle': inbound('lifecycle', action='disable'),
        },
        outbound={},
        exemptions={
            'reply_group': 'Event reports sdk=onebot while API.Event routes milky by sdk=milky',
            'send_group': 'Event reports sdk=onebot while API.Event routes milky by sdk=milky',
            'reply_private': 'Event reports sdk=onebot while API.Event routes milky by sdk=milky',
            'send_private': 'Event reports sdk=onebot while API.Event routes milky by sdk=milky',
        },
    ),
    # 虚拟终端：群/私聊消息进出站统一走 send_msg。
    'virtualTerminalSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
        },
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'reply_private': outbound('send_msg', event='private_message'),
            'send_private': outbound('send_msg', event='private_message'),
        },
    ),
    # QQ 频道旧版：群/私聊消息进出站统一走 send_msg。
    'qqGuildSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
        },
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'reply_private': outbound('send_msg', target_aware=False, event='private_message'),
            'send_private': outbound('send_msg', target_aware=False, event='private_message'),
        },
        actions={'get_login_info': adapter_action('get_login_info', 'get_login_info')},
    ),
    # QQ 频道新版：群消息、回复和群主动发送统一走 send_qq_msg。
    'qqGuildv2SDK': NS(
        inbound={'group_message': inbound('group_message', group_id='7', user_id='42')},
        outbound={
            'reply_group': outbound('send_qq_msg'),
            'send_group': outbound('send_qq_msg'),
        },
        actions={
            'delete_message': adapter_action('delete_msg', 'delete_msg', (8,), (8,)),
            'get_group_member_info': adapter_action(
                'get_group_member_info', 'get_group_member_info', (7, 42), (7, 42)
            ),
            'get_group_member_list': adapter_action('get_group_member_list', 'get_group_member_list', (7,), (7,)),
            'set_group_add_request': adapter_action(
                'set_group_add_request', 'set_group_add_request',
                ('fixture-flag', 'add', True, 'reason'), ('fixture-flag', 'add', True)
            ),
        },
    ),
    # Discord：群/私聊消息进出站统一走 send_msg。
    'discordSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
        },
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'reply_private': outbound('send_msg', event='private_message'),
            'send_private': outbound('send_msg', event='private_message'),
        },
        actions={'get_login_info': adapter_action('get_login_info', 'get_login_info')},
    ),
    # Telegram：群/私聊消息和查询接口可用；成员变更事件会被消息分支提前截断，因此不声明。
    'telegramSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
        },
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'reply_private': outbound('send_msg', target_aware=False, event='private_message'),
            'send_private': outbound('send_msg', target_aware=False, event='private_message'),
        },
        actions={
            'get_group_info': adapter_action('get_group_info', 'get_group_info', (7,), (7,)),
            'get_group_member_info': adapter_action(
                'get_group_member_info', 'get_group_member_info', (7, 42), (7, 42)
            ),
            'get_login_info': adapter_action('get_login_info', 'get_login_info'),
        },
    ),
    # Fanbook：群消息进出站走 send_msg，私聊主动发送走 send_private_msg。
    'fanbookSDK': NS(
        inbound={'group_message': inbound('group_message', group_id='7', user_id='42')},
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'send_private': outbound('send_private_msg'),
        },
        actions={'get_login_info': adapter_action('get_login_info', 'get_login_info')},
    ),
    # DoDo：群消息进出站走 send_msg，私聊主动发送走 send_private_msg。
    'dodoSDK': NS(
        inbound={'group_message': inbound('group_message', group_id='7', user_id='42')},
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'send_private': outbound('send_private_msg'),
        },
    ),
    # DoDo Link：群消息走 send_msg，私聊消息走 send_personal_msg。
    'dodoLinkSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
        },
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'reply_private': outbound('send_personal_msg', event='private_message'),
            'send_private': outbound('send_personal_msg', event='private_message'),
        },
        actions={'get_login_info': adapter_action('get_login_info', 'get_login_info')},
    ),
    # DoDoBot EA：群消息、回复和群主动发送统一走 send_msg。
    'dodobotEASDK': NS(
        inbound={'group_message': inbound('group_message', group_id='7', user_id='42')},
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
        },
    ),
    # 开黑啦：群消息与频道查询/管理走 send_msg 及对应接口。
    'kaiheilaSDK': NS(
        inbound={'group_message': inbound('group_message', group_id='7', user_id='42')},
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'send_private': outbound('send_msg'),
        },
        actions={
            'get_group_info': adapter_action('get_group_info', 'get_group_info', (7,), (7,)),
            'get_group_member_info': adapter_action(
                'get_group_member_info', 'get_group_member_info', (7, 42), (9, 42)
            ),
            'get_group_list': adapter_action('get_group_list', 'get_group_list', (), (9,)),
            'get_group_member_list': adapter_action('get_group_member_list', 'get_group_member_list', (7,), (9,)),
            'set_group_kick': adapter_action('set_group_kick', 'set_group_kick', (7, 42), (9, 42)),
            'get_login_info': adapter_action('get_login_info', 'get_login_info'),
        },
    ),
    # 小黑盒：覆盖群消息、成员变更、频道查询和管理接口。
    'xiaoheiheSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'group_member_increase': inbound('group_member_increase', user_id='42'),
            'group_member_decrease': inbound('group_member_decrease', user_id='42'),
        },
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
        },
        actions={
            'get_group_list': adapter_action('get_group_list', 'get_group_list'),
            'get_group_member_list': adapter_action('get_group_member_list', 'get_group_member_list', (7,), (9,)),
            'set_group_ban': adapter_action('set_group_ban', 'set_group_ban', (7, 42, None, 60), (9, 42, 60)),
            'set_group_kick': adapter_action('set_group_kick', 'set_group_kick', (7, 42), (9, 42)),
            'set_group_leave': adapter_action('set_group_leave', 'set_group_leave', (7,), (9,)),
        },
    ),
    # B 站直播：send_msg 不以目标 ID 为显式参数，因此出站只断言消息文本。
    'biliLiveSDK': NS(
        inbound={'group_message': inbound('group_message', group_id='10001', user_id='42')},
        outbound={
            'reply_group': outbound('send_msg', target_aware=False),
            'send_group': outbound('send_msg', target_aware=False),
        },
    ),
    # OPQBot：覆盖群/私聊消息、成员变更、请求处理、群查询和退群接口。
    'OPQBotSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
            'group_member_increase': inbound('group_member_increase', group_id='7', user_id='42'),
        },
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'reply_private': outbound('send_msg', event='private_message'),
            'send_private': outbound('send_msg', event='private_message'),
        },
        actions={
            'set_friend_add_request': adapter_action(
                'set_friend_add_request', 'set_friend_add_request',
                ('fixture-flag', True, 'remark'), ('fixture-flag', True)
            ),
            'set_group_add_request': adapter_action(
                'set_group_add_request', 'set_group_add_request',
                ('fixture-flag', 'add', True, 'reason'), ('fixture-flag', 'add', True)
            ),
            'get_group_list': adapter_action('get_group_list', 'get_group_list'),
            'set_group_leave': adapter_action('set_group_leave', 'set_group_leave', (7,), (7,)),
        },
    ),
    # 米游社大别野：群消息、回复和群主动发送统一走 send_group_msg。
    'mhyVilaSDK': NS(
        inbound={'group_message': inbound('group_message', group_id='7', user_id='42')},
        outbound={
            'reply_group': outbound('send_group_msg'),
            'send_group': outbound('send_group_msg'),
        },
    ),
    # QQ Red：群/私聊消息进出站统一走 send_msg。
    'qqRedSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
        },
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'reply_private': outbound('send_msg', event='private_message'),
            'send_private': outbound('send_msg', event='private_message'),
        },
    ),
    # HackChat：send_msg 不以目标 ID 为显式参数，因此出站只断言消息文本。
    'hackChatSDK': NS(
        inbound={'group_message': inbound('group_message', group_id='0', user_id='42')},
        outbound={
            'reply_group': outbound('send_msg', target_aware=False),
            'send_group': outbound('send_msg', target_aware=False),
        },
    ),
    # 钉钉：群/私聊消息进出站统一走 send_msg。
    'dingtalkSDK': NS(
        inbound={
            'group_message': inbound('group_message', group_id='7', user_id='42'),
            'private_message': inbound('private_message', user_id='42'),
        },
        outbound={
            'reply_group': outbound('send_msg'),
            'send_group': outbound('send_msg'),
            'reply_private': outbound('send_msg', event='private_message'),
            'send_private': outbound('send_msg', event='private_message'),
        },
    ),
}


CORE_INBOUND_CAPABILITIES = frozenset({'group_message'})


def _outbound_cases(capability):
    return [
        (name, case.outbound[capability])
        for name, case in ADAPTER_BUSINESS_CASES.items()
        if capability in case.outbound
    ]


OUTBOUND_REPLY_CASES = _outbound_cases('reply_group')
OUTBOUND_PRIVATE_REPLY_CASES = _outbound_cases('reply_private')
OUTBOUND_SEND_CASES = _outbound_cases('send_group')
OUTBOUND_PRIVATE_SEND_CASES = _outbound_cases('send_private')
OUTBOUND_ACTION_CASES = [
    (name, capability, spec)
    for name, case in ADAPTER_BUSINESS_CASES.items()
    for capability, spec in getattr(case, 'actions', {}).items()
]
INBOUND_CASES = [
    (name, capability, spec)
    for name, case in ADAPTER_BUSINESS_CASES.items()
    for capability, spec in case.inbound.items()
]
INBOUND_BUILDERS = {
    'group_message': make_sdk_group_event,
    'private_message': make_sdk_private_event,
    'group_member_increase': make_sdk_notice_event,
    'group_member_decrease': make_sdk_notice_event,
    'group_ban': make_sdk_notice_event,
    'group_message_recall': make_sdk_notice_event,
    'private_message_recall': make_sdk_notice_event,
    'friend_add': make_sdk_notice_event,
    'poke': make_sdk_notice_event,
    'friend_add_request': make_sdk_notice_event,
    'group_add_request': make_sdk_notice_event,
    'group_invite_request': make_sdk_notice_event,
    'lifecycle': make_sdk_notice_event,
    'heartbeat': make_sdk_notice_event,
}


def install_outbound_recorder(name, method, monkeypatch):
    module = getattr(OlivOS, name)
    recorder = Mock(return_value=None)
    monkeypatch.setattr(module.event_action, method, recorder)
    if name == 'dodobotEASDK':
        monkeypatch.setattr(OlivOS.dodobotEATXAPI.server, 'rx_packet', Mock(return_value=None))
    return recorder


def _contains_value(value, expected):
    if isinstance(value, OlivOS.messageAPI.Message_templet):
        value = value.get('olivos_string')
    if value == expected or str(value) == str(expected):
        return True
    if isinstance(value, dict):
        return any(_contains_value(item, expected) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_contains_value(item, expected) for item in value)
    return False


def assert_outbound_call(recorder, event, text=None, target_id=None, target_aware=True, expected_values=()):
    recorder.assert_called_once()
    args, kwargs = recorder.call_args
    assert args[0] is event
    values = list(args[1:]) + list(kwargs.values())
    if text is not None:
        assert any(_contains_value(value, text) for value in values), (text, args, kwargs)
    if target_aware and target_id is not None:
        assert any(_contains_value(value, target_id) for value in values), (target_id, args, kwargs)
    for expected in expected_values:
        assert any(_contains_value(value, expected) for value in values), (expected, args, kwargs)
