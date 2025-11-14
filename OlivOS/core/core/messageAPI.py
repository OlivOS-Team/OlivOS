# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/messageAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

import json
import re

import OlivOS
import traceback

# platform sdk model
dictMessageType = {
    'wechat': {
        'onebot': {
            'onebotV12': 'obv12_para',
            'ComWeChatBotClient': 'obv12_para'
        }
    },
    'qq': {
        'onebot': {
            'default': 'old_string',
            'onebotV12': 'obv12_para',
            'red': 'olivos_para',
            'gocqhttp': 'old_string',
            'gocqhttp_hide': 'old_string',
            'gocqhttp_show': 'old_string',
            'gocqhttp_show_Android_Phone': 'old_string',
            'gocqhttp_show_Android_Pad': 'old_string',
            'gocqhttp_show_Android_Watch': 'old_string',
            'gocqhttp_show_iPad': 'old_string',
            'gocqhttp_show_iMac': 'old_string',
            'gocqhttp_show_old': 'old_string',
            'walleq': 'obv12_para',
            'walleq_hide': 'obv12_para',
            'walleq_show': 'obv12_para',
            'walleq_show_Android_Phone': 'obv12_para',
            'walleq_show_Android_Pad': 'obv12_para',
            'walleq_show_Android_Watch': 'obv12_para',
            'walleq_show_iPad': 'obv12_para',
            'walleq_show_iMac': 'obv12_para',
            'walleq_show_old': 'obv12_para',
            'opqbot_default': 'olivos_string',
            'opqbot_auto': 'old_string',
            'opqbot_port': 'old_string',
            'opqbot_port_old': 'old_string',
            'napcat': 'old_string',
            'napcat_hide': 'old_string',
            'napcat_show': 'old_string',
            'napcat_show_new': 'old_string',
            'napcat_show_old': 'old_string',
            'napcat_default': 'old_string',
            'llonebot_default': 'old_string',
            'lagrange_default': 'old_string'
        }
    },
    'qqGuild': {
        'qqGuild_link': {
            'default': 'olivos_para',
            'private': 'olivos_para',
            'public': 'olivos_para'
        },
        'qqGuildv2_link': {
            'default': 'olivos_para',
            'sandbox': 'olivos_para',
            'sandbox_intents': 'olivos_para',
            'private': 'olivos_para',
            'private_intents': 'olivos_para',
            'public': 'olivos_para',
            'public_intents': 'olivos_para'
        }
    },
    'telegram': {
        'telegram_poll': {
            'default': 'olivos_para'
        }
    },
    'fanbook': {
        'fanbook_poll': {
            'default': 'olivos_para',
            'private': 'olivos_para'
        }
    },
    'kaiheila': {
        'kaiheila_link': {
            'default': 'olivos_para',
            'card': 'olivos_para',
            'text': 'olivos_para'
        }
    },
    'xiaoheihe': {
        'xiaoheihe_link': {
            'default': 'old_string'
        }
    },
    'mhyVila': {
        'mhyVila_link': {
            'default': 'olivos_string',
            'public': 'olivos_string',
            'private': 'olivos_string',
            'sandbox': 'olivos_string'
        }
    },
    'discord': {
        'discord_link': {
            'default': 'olivos_para'
        }
    },
    'dodo': {
        'dodo_link': {
            'default': 'olivos_para',
            'v1': 'olivos_para',
            'v2': 'olivos_para'
        },
        'dodo_poll': {
            'default': 'olivos_para'
        },
        'dodobot_ea': {
            'default': 'olivos_para'
        }
    },
    'dingtalk': {
        'dingtalk_link': {
            'default': 'olivos_para'
        }
    },
    'fake': {
        'fake': {
            'default': 'olivos_para'
        }
    },
    'terminal': {
        'terminal_link': {
            'default': 'olivos_string',
            'postapi': 'olivos_string',
            'ff14': 'olivos_string'
        }
    },
    'hackChat': {
        'hackChat_link': {
            'default': 'olivos_string',
            'private': 'olivos_string'
        }
    },
    'biliLive': {
        'biliLive_link': {
            'default': 'olivos_string',
            'login': 'olivos_string'
        }
    }
}


class Message_templet(object):
    def __init__(self, mode_rx, data_raw):
        self.active = True
        self.mode_rx = mode_rx
        self.data = []
        self.data_raw = data_raw
        try:
            self.init_data()
        except:
            self.active = False
            self.data = []

    def __str__(self):
        tmp_res = self.__dict__.copy()
        tmp_res_data = []
        for data_this in tmp_res['data']:
            tmp_res_data.append(data_this.__dict__)
        tmp_res['data'] = tmp_res_data
        return str(tmp_res)

    def append(self, para_append):
        self.data.append(para_append)

    def match_str(self, src_str, match_str_src):
        if len(src_str) >= len(match_str_src):
            if src_str[:len(match_str_src)] == match_str_src:
                return True
        return False

    def get_from_dict(self, src_dict, key_list, default_val=None):
        tmp_src_dict = src_dict
        for key_list_this in key_list:
            if key_list_this in tmp_src_dict:
                tmp_src_dict = tmp_src_dict[key_list_this]
            else:
                return default_val
        return tmp_src_dict

    def get(self, get_type):
        res = None
        if not self.active:
            res = str(self)
        elif get_type == 'olivos_para':
            res = self
        elif get_type == 'olivos_string':
            res = ''
            for data_this in self.data:
                res += data_this.OP()
        elif get_type == 'obv12_para':
            res = []
            for data_this in self.data:
                res.append(data_this.OBV12())
        elif get_type == 'old_string':
            res = ''
            for data_this in self.data:
                res += data_this.CQ()
        elif get_type == 'fanbook_string':
            res = ''
            for data_this in self.data:
                res += data_this.fanbook()
        elif get_type == 'dodo_string':
            res = ''
            for data_this in self.data:
                res += data_this.dodo()
        elif get_type == 'qqGuild_string':
            res = ''
            for data_this in self.data:
                res += data_this.OP()
        elif get_type == 'kaiheila_string':
            res = ''
            for data_this in self.data:
                res += data_this.kaiheila()
        elif get_type == 'xiaoheihe_string':
            res = ''
            for data_this in self.data:
                res += data_this.xiaoheihe()
        else:
            res = str(self)
        return res

    def init_data(self):
        if self.mode_rx == 'olivos_para':
            self.init_from_olivos_para()
        elif self.mode_rx == 'olivos_string':
            self.init_from_code_string('OP')
        elif self.mode_rx == 'obv12_para':
            self.init_from_obv12_para()
        elif self.mode_rx == 'old_string':
            self.init_from_code_string('CQ')
        elif self.mode_rx == 'fanbook_string':
            self.init_from_fanbook_code_string()
        elif self.mode_rx == 'dodo_string':
            self.init_from_angle_code_string()
        elif self.mode_rx == 'qqGuild_string':
            self.init_from_angle_code_string()
        elif self.mode_rx == 'kaiheila_string':
            self.init_from_kaiheila_code_string()
        elif self.mode_rx == 'discord_string':
            self.init_from_discord_code_string()
        elif self.mode_rx == 'xiaoheihe_string':
            self.init_from_xiaoheihe_string()

    def init_from_olivos_para(self):
        tmp_data = []
        if type(self.data_raw) == list:
            for data_raw_this in self.data_raw:
                if data_raw_this.__class__.__base__ == PARA_templet:
                    tmp_data.append(data_raw_this)
            self.data = tmp_data
        else:
            self.active = False

    def init_from_obv12_para(self):
        tmp_data = []
        if type(self.data_raw) == list:
            for data_raw_this in self.data_raw:
                if type(data_raw_this) is dict \
                and 'type' in data_raw_this \
                and 'data' in data_raw_this \
                and type(data_raw_this['data']) is dict:
                    if 'text' == data_raw_this['type'] \
                    and 'text' in data_raw_this['data']:
                        tmp_data.append(
                            PARA.text(data_raw_this['data']['text'])
                        )
                    elif 'mention' == data_raw_this['type'] \
                    and 'user_id' in data_raw_this['data']:
                        tmp_data.append(
                            PARA.at(str(data_raw_this['data']['user_id']))
                        )
                    elif 'mention_all' == data_raw_this['type']:
                        tmp_data.append(
                            PARA.at('all')
                        )
                    elif 'image' == data_raw_this['type'] \
                    and 'file_id' in data_raw_this['data']:
                        tmp_this = PARA.image(data_raw_this['data']['file_id'])
                        if 'url' in data_raw_this['data']:
                            tmp_this.data['url'] = data_raw_this['data']['url']
                        if 'flush' in data_raw_this['data'] \
                        and True is data_raw_this['data']['flush']:
                            tmp_this.data['type'] = 'flush'
                        tmp_data.append(tmp_this)
                    elif 'voice' == data_raw_this['type'] \
                    and 'file_id' in data_raw_this['data']:
                        tmp_this = PARA.record(data_raw_this['data']['file_id'])
                        tmp_data.append(tmp_this)
                    elif 'audio' == data_raw_this['type'] \
                    and 'file_id' in data_raw_this['data']:
                        tmp_this = PARA.record(data_raw_this['data']['file_id'])
                        tmp_data.append(tmp_this)
                    elif 'video' == data_raw_this['type'] \
                    and 'file_id' in data_raw_this['data']:
                        tmp_this = PARA.video(data_raw_this['data']['file_id'])
                        tmp_data.append(tmp_this)
                    elif 'location' == data_raw_this['type'] \
                    and 'latitude' in data_raw_this['data'] \
                    and 'longitude' in data_raw_this['data'] \
                    and 'title' in data_raw_this['data'] \
                    and 'content' in data_raw_this['data']:
                        tmp_this = PARA.location(
                            lat=data_raw_this['data']['latitude'],
                            lon=data_raw_this['data']['longitude'],
                            title=data_raw_this['data']['title'],
                            content=data_raw_this['data']['content']
                        )
                        tmp_data.append(tmp_this)
                    elif 'face' == data_raw_this['type'] \
                    and 'id' in data_raw_this['data']:
                        tmp_data.append(PARA.face(data_raw_this['data']['id']))
                    elif 'dice' == data_raw_this['type']:
                        tmp_data.append(PARA.dice())
                    elif 'rps' == data_raw_this['type']:
                        tmp_data.append(PARA.rps())
                    elif 'reply' == data_raw_this['type'] \
                    and 'message_id' in data_raw_this['data']:
                        tmp_data.append(PARA.reply(str(data_raw_this['data']['message_id'])))
                    elif 'json' == data_raw_this['type'] \
                    and 'data' in data_raw_this['data']:
                        tmp_data.append(PARA.json(data_raw_this['data']['data']))
                    elif 'xml' == data_raw_this['type'] \
                    and 'data' in data_raw_this['data']:
                        tmp_data.append(PARA.xml(data_raw_this['data']['data']))
            self.data = tmp_data
        else:
            self.active = False

    def init_from_code_string(self, code_key):
        tmp_data_raw = str(self.data_raw)
        tmp_data = []
        it_data = range(0, len(tmp_data_raw) + 1)
        it_data_base = 0
        tmp_data_type = 'string'
        for it_data_this in it_data:
            if tmp_data_type == 'string' and self.match_str(tmp_data_raw[it_data_this:], '[' + code_key + ':'):
                tmp_para_this = None
                if it_data_this > it_data_base:
                    tmp_data_raw_this = tmp_data_raw[it_data_base:it_data_this]
                    tmp_para_this = PARA.text(tmp_data_raw_this)
                    tmp_data.append(tmp_para_this)
                it_data_base = it_data_this
                tmp_data_type = 'code'
            elif tmp_data_type == 'code' and self.match_str(tmp_data_raw[it_data_this:], ']'):
                tmp_para_this = None
                if it_data_this > it_data_base:
                    tmp_data_raw_this_bak = tmp_data_raw[it_data_base:it_data_this + 1]
                    tmp_data_raw_this = tmp_data_raw_this_bak
                    tmp_data_raw_this = tmp_data_raw_this[len('[' + code_key + ':'):]
                    tmp_data_raw_this = tmp_data_raw_this[:-len(']')]
                    tmp_data_raw_this_list = tmp_data_raw_this.split(',')
                    tmp_data_type_key = tmp_data_raw_this_list[0]
                    tmp_code_data_list = tmp_data_raw_this_list[1:]
                    tmp_code_data_dict = {}
                    for tmp_code_data_list_this in tmp_code_data_list:
                        tmp_code_data_list_this_list = tmp_code_data_list_this.split('=')
                        tmp_code_data_list_this_key = tmp_code_data_list_this_list[0]
                        tmp_code_data_list_this_val = ''
                        flag_tmp_code_data_list_this_val_begin = True
                        for tmp_code_data_list_this_val_this in tmp_code_data_list_this_list[1:]:
                            if not flag_tmp_code_data_list_this_val_begin:
                                tmp_code_data_list_this_val += '='
                            else:
                                flag_tmp_code_data_list_this_val_begin = False
                            tmp_code_data_list_this_val += tmp_code_data_list_this_val_this
                        tmp_code_data_dict[tmp_code_data_list_this_key] = tmp_code_data_list_this_val
                    if tmp_data_type_key == 'face':
                        tmp_para_this = PARA.face(
                            id=str(self.get_from_dict(tmp_code_data_dict, ['id']))
                        )
                    elif tmp_data_type_key == 'at':
                        if code_key == 'CQ':
                            tmp_code_data_dict['id'] = str(self.get_from_dict(tmp_code_data_dict, ['qq'], -1))
                        tmp_para_this = PARA.at(
                            id=str(self.get_from_dict(tmp_code_data_dict, ['id'], -1)),
                            name=self.get_from_dict(tmp_code_data_dict, ['name'], None)
                        )
                    elif tmp_data_type_key == 'reply':
                        tmp_para_this = PARA.reply(
                            id=str(self.get_from_dict(tmp_code_data_dict, ['id'], 0))
                        )
                    elif tmp_data_type_key == 'image':
                        tmp_para_this = PARA.image(
                            file=str(self.get_from_dict(tmp_code_data_dict, ['file'])),
                            type=self.get_from_dict(tmp_code_data_dict, ['type'], None),
                            url=self.get_from_dict(tmp_code_data_dict, ['url'], None)
                        )
                    elif tmp_data_type_key == 'record':
                        tmp_para_this = PARA.record(
                            file=str(self.get_from_dict(tmp_code_data_dict, ['file'])),
                            url=str(self.get_from_dict(tmp_code_data_dict, ['url']))
                        )
                    elif tmp_data_type_key == 'video':
                        tmp_para_this = PARA.video(
                            file=str(self.get_from_dict(tmp_code_data_dict, ['file'])),
                            url=str(self.get_from_dict(tmp_code_data_dict, ['url']))
                        )
                    elif tmp_data_type_key == 'rps':
                        tmp_para_this = PARA.rps()
                    elif tmp_data_type_key == 'dice':
                        tmp_para_this = PARA.dice()
                    elif tmp_data_type_key == 'shake':
                        tmp_para_this = PARA.shake()
                    elif tmp_data_type_key == 'poke':
                        tmp_para_this = PARA.poke(
                            id=str(self.get_from_dict(tmp_code_data_dict, ['id'], -1))
                        )
                    elif tmp_data_type_key == 'anonymous':
                        tmp_para_this = PARA.anonymous()
                    elif tmp_data_type_key == 'share':
                        tmp_para_this = PARA.share(
                            url=str(self.get_from_dict(tmp_code_data_dict, ['url'], '')),
                            title=str(self.get_from_dict(tmp_code_data_dict, ['title'], '')),
                            content=str(self.get_from_dict(tmp_code_data_dict, ['content'], '')),
                            image=str(self.get_from_dict(tmp_code_data_dict, ['image'], ''))
                        )
                    elif tmp_data_type_key == 'location':
                        tmp_para_this = PARA.location(
                            lat=str(self.get_from_dict(tmp_code_data_dict, ['lat'], '')),
                            lon=str(self.get_from_dict(tmp_code_data_dict, ['lon'], '')),
                            title=str(self.get_from_dict(tmp_code_data_dict, ['title'], '')),
                            content=str(self.get_from_dict(tmp_code_data_dict, ['content'], ''))
                        )
                    elif tmp_data_type_key == 'music':
                        tmp_para_this = PARA.music(
                            type=str(self.get_from_dict(tmp_code_data_dict, ['type'], '')),
                            id=str(self.get_from_dict(tmp_code_data_dict, ['id'], '')),
                            url=str(self.get_from_dict(tmp_code_data_dict, ['url'], '')),
                            audio=str(self.get_from_dict(tmp_code_data_dict, ['audio'], '')),
                            title=str(self.get_from_dict(tmp_code_data_dict, ['title'], '')),
                            content=str(self.get_from_dict(tmp_code_data_dict, ['content'], '')),
                            image=str(self.get_from_dict(tmp_code_data_dict, ['image'], ''))
                        )
                    elif tmp_data_type_key == 'forward':
                        tmp_para_this = PARA.forward(
                            id=str(self.get_from_dict(tmp_code_data_dict, ['id'], 'NULLHASH'))
                        )
                    elif tmp_data_type_key == 'xml':
                        tmp_para_this = PARA.xml(
                            data=str(self.get_from_dict(tmp_code_data_dict, ['data'], ''))
                        )
                    elif tmp_data_type_key == 'json':
                        tmp_para_this = PARA.json(
                            data=str(self.get_from_dict(tmp_code_data_dict, ['data'], ''))
                        )
                    else:
                        tmp_para_this = PARA.text(tmp_data_raw_this_bak)
                    tmp_data.append(tmp_para_this)
                it_data_base = it_data_this + 1
                tmp_data_type = 'string'
            elif it_data_this >= len(tmp_data_raw):
                tmp_para_this = None
                if it_data_this > it_data_base:
                    tmp_data_raw_this = tmp_data_raw[it_data_base:it_data_this + 1]
                    tmp_para_this = PARA.text(tmp_data_raw_this)
                    tmp_data.append(tmp_para_this)
                it_data_base = it_data_this
        self.data = tmp_data

    def init_from_fanbook_code_string(self):
        tmp_data_raw = str(self.data_raw)
        tmp_data = []
        it_data = range(0, len(tmp_data_raw) + 1)
        it_data_base = 0
        tmp_data_type = 'string'
        for it_data_this in it_data:
            if tmp_data_type == 'string' and self.match_str(tmp_data_raw[it_data_this:], '${'):
                tmp_para_this = None
                if it_data_this > it_data_base:
                    tmp_data_raw_this = tmp_data_raw[it_data_base:it_data_this]
                    tmp_para_this = PARA.text(tmp_data_raw_this)
                    tmp_data.append(tmp_para_this)
                it_data_base = it_data_this
                tmp_data_type = 'code'
            elif tmp_data_type == 'code' and self.match_str(tmp_data_raw[it_data_this:], '}'):
                tmp_para_this = None
                if it_data_this > it_data_base:
                    tmp_data_raw_this_bak = tmp_data_raw[it_data_base:it_data_this + 1]
                    tmp_data_raw_this = tmp_data_raw_this_bak
                    tmp_data_raw_this = tmp_data_raw_this[len('${'):]
                    tmp_data_raw_this = tmp_data_raw_this[:-len('}')]
                    tmp_data_raw_this_list = tmp_data_raw_this.split('!')
                    tmp_data_raw_this_list_2 = tmp_data_raw_this.split('&')
                    tmp_data_type_key = tmp_data_raw_this_list[0]
                    tmp_data_type_key_2 = tmp_data_raw_this_list_2[0]
                    tmp_code_data_list = tmp_data_raw_this_list[1:]
                    tmp_code_data_list_2 = tmp_data_raw_this_list_2[1:]
                    if tmp_data_type_key == '@' and len(tmp_code_data_list) > 0:
                        tmp_para_this = PARA.at(
                            id=str(tmp_code_data_list[0])
                        )
                    elif tmp_data_type_key_2 == '@' and len(tmp_code_data_list_2) > 0:
                        tmp_para_this = PARA.at(
                            id='all'
                        )
                    else:
                        tmp_para_this = PARA.text(tmp_data_raw_this_bak)
                    tmp_data.append(tmp_para_this)
                it_data_base = it_data_this + 1
                tmp_data_type = 'string'
            elif it_data_this >= len(tmp_data_raw):
                tmp_para_this = None
                if it_data_this > it_data_base:
                    tmp_data_raw_this = tmp_data_raw[it_data_base:it_data_this + 1]
                    tmp_para_this = PARA.text(tmp_data_raw_this)
                    tmp_data.append(tmp_para_this)
                it_data_base = it_data_this
        self.data = tmp_data

    def init_from_angle_code_string(self):
        tmp_data_raw = str(self.data_raw)
        tmp_data = []
        it_data = range(0, len(tmp_data_raw) + 1)
        it_data_base = 0
        tmp_data_type = 'string'
        for it_data_this in it_data:
            if tmp_data_type == 'string' and self.match_str(tmp_data_raw[it_data_this:], '<'):
                tmp_para_this = None
                if it_data_this > it_data_base:
                    tmp_data_raw_this = tmp_data_raw[it_data_base:it_data_this]
                    tmp_para_this = PARA.text(tmp_data_raw_this)
                    tmp_data.append(tmp_para_this)
                it_data_base = it_data_this
                tmp_data_type = 'code'
            elif tmp_data_type == 'code' and self.match_str(tmp_data_raw[it_data_this:], '>'):
                tmp_para_this = None
                if it_data_this > it_data_base:
                    tmp_data_raw_this_bak = tmp_data_raw[it_data_base:it_data_this + len('>')]
                    tmp_data_raw_this = tmp_data_raw_this_bak
                    tmp_data_raw_this = tmp_data_raw_this[len('<'):]
                    tmp_data_raw_this = tmp_data_raw_this[:-len('>')]
                    tmp_data_raw_this_list = tmp_data_raw_this.split('!')
                    tmp_data_raw_this_list_2 = tmp_data_raw_this.split('&')
                    tmp_data_type_key = tmp_data_raw_this_list[0]
                    tmp_data_type_key_2 = tmp_data_raw_this_list_2[0]
                    tmp_code_data_list = tmp_data_raw_this_list[1:]
                    tmp_code_data_list_2 = tmp_data_raw_this_list_2[1:]
                    if tmp_data_type_key == '@' and len(tmp_code_data_list) > 0:
                        tmp_para_this = PARA.at(
                            id=str(tmp_code_data_list[0])
                        )
                    elif tmp_data_type_key_2 == '@' and len(tmp_code_data_list_2) > 0:
                        tmp_para_this = PARA.at(
                            id='all'
                        )
                    else:
                        tmp_para_this = PARA.at(
                            id='all'
                        )
                    tmp_data.append(tmp_para_this)
                it_data_base = it_data_this + 1
                tmp_data_type = 'string'
            elif it_data_this >= len(tmp_data_raw):
                tmp_para_this = None
                if it_data_this > it_data_base:
                    tmp_data_raw_this = tmp_data_raw[it_data_base:it_data_this + 1]
                    tmp_para_this = PARA.text(tmp_data_raw_this)
                    tmp_data.append(tmp_para_this)
                it_data_base = it_data_this
        self.data = tmp_data

    def init_from_kaiheila_code_string(self):
        tmp_data_raw = str(self.data_raw)
        tmp_data_raw = re.sub(r'\(met\)(\d+)\(met\)', r'[OP:at,id=\1]', tmp_data_raw)
        tmp_data_raw = re.sub(r'\\(.)', r'\1', tmp_data_raw)
        self.data_raw = tmp_data_raw
        self.init_from_code_string('OP')

    def init_from_discord_code_string(self):
        tmp_data_raw = str(self.data_raw)
        tmp_data_raw = re.sub(r'<@(\d+)>', r'[OP:at,id=\1]', tmp_data_raw)
        # tmp_data_raw = re.sub(r'\\(.)', r'\1', tmp_data_raw)
        self.data_raw = tmp_data_raw
        self.init_from_code_string('OP')

    def init_from_xiaoheihe_string(self):
        tmp_data_raw = str(self.data_raw)
        # 将小黑盒的 @{id:xxxxx} 格式转换为 [OP:at,id=xxxxx]
        tmp_data_raw = re.sub(r'@\{id:(\d+)\}', r'[OP:at,id=\1]', tmp_data_raw)
        self.data_raw = tmp_data_raw
        self.init_from_code_string('OP')


class PARA_templet(object):
    def __init__(self, type=None, data=None):
        self.type = type
        self.data = data

    def CQ(self):
        return self.get_string_by_key('CQ')

    def OP(self):
        return self.get_string_by_key('OP')

    def OBV12(self):
        paraType = None
        paraData = {}
        try:
            if type(self) is PARA.text:
                paraType = 'text'
                paraData['text'] = str(self.data['text'])
            elif type(self) is PARA.at \
            and self.data['id'] == 'all':
                paraType = 'mention_all'
            elif type(self) is PARA.at:
                paraType = 'mention'
                paraData['user_id'] = str(self.data['id'])
            elif type(self) is PARA.image:
                paraType = 'image'
                paraData['file_id'] = self.data['file']
                paraData['url'] = self.data['url']
                paraData['flush'] = True if self.data['type'] == 'flush' else False
            elif type(self) is PARA.record:
                paraType = 'record'
                paraData['file_id'] = self.data['file']
            elif type(self) is PARA.video:
                paraType = 'video'
                paraData['file_id'] = self.data['file']
            elif type(self) is PARA.location:
                paraType = 'location'
                paraData['latitude'] = self.data['lat']
                paraData['longitude'] = self.data['lon']
                paraData['title'] = self.data['title']
                paraData['content'] = self.data['content']
            elif type(self) is PARA.face:
                paraType = 'face'
                paraData['id'] = self.data['id']
            elif type(self) is PARA.dice:
                paraType = 'dice'
            elif type(self) is PARA.rps:
                paraType = 'rps'
            elif type(self) is PARA.reply:
                paraType = 'reply'
                paraData['message_id'] = self.data['id']
            elif type(self) is PARA.json:
                paraType = 'json'
                paraData['data'] = self.data['data']
            elif type(self) is PARA.xml:
                paraType = 'xml'
                paraData['data'] = self.data['data']
        except Exception as e:
            traceback.print_exc()
            paraType = None
        if paraType is None:
            paraType = 'text'
            paraData = {'text': ''}
        res = {
            'type': paraType,
            'data': paraData
        }
        return res

    def kaiheila(self):
        code_tmp = '${'
        if type(self) == PARA.at:
            if self.data is not None:
                for key_this in self.data:
                    if self.data[key_this] is not None:
                        code_tmp += '@'
                        code_tmp += '#' + str(self.data[key_this])
        elif type(self) == PARA.text:
            if self.data is not None:
                if type(self.data['text']) is str:
                    return self.data['text']
                else:
                    return str(self.data['text'])
            else:
                return ''
        code_tmp += '}'
        return code_tmp

    def fanbook(self):
        code_tmp = '${'
        if type(self) == PARA.at:
            if self.data is not None:
                for key_this in self.data:
                    if self.data[key_this] is not None:
                        code_tmp += '@'
                        code_tmp += '!' + str(self.data[key_this])
        elif type(self) == PARA.text:
            if self.data is not None:
                if type(self.data['text']) is str:
                    return self.data['text']
                else:
                    return str(self.data['text'])
            else:
                return ''
        code_tmp += '}'
        return code_tmp

    def dodo(self):
        code_tmp = '<'
        if type(self) == PARA.at:
            if self.data is not None:
                for key_this in self.data:
                    if self.data[key_this] is not None:
                        code_tmp += '@'
                        code_tmp += '!' + str(self.data[key_this])
        elif type(self) == PARA.text:
            if self.data is not None:
                if type(self.data['text']) is str:
                    return self.data['text']
                else:
                    return str(self.data['text'])
            else:
                return ''
        code_tmp += '>'
        return code_tmp

    def xiaoheihe(self):
        if type(self) == PARA.at:
            if self.data is not None and 'id' in self.data and self.data['id'] is not None:
                return f"@{{id:{self.data['id']}}}"
            return ''
        elif type(self) == PARA.text:
            if self.data is not None:
                if type(self.data['text']) is str:
                    return self.data['text']
                else:
                    return str(self.data['text'])
            else:
                return ''
        return ''

    def get_string_by_key(self, code_key):
        code_tmp = '[' + code_key + ':' + self.type
        if self.data is not None:
            for key_this in self.data:
                if self.data[key_this] is not None:
                    code_tmp += ',' + key_this + '=' + str(self.data[key_this])
        code_tmp += ']'
        return code_tmp

    def PARA(self):
        PARA_tmp = self.cut()
        if self.data is None:
            PARA_tmp.data = dict()
        return json.dumps(obj=PARA_tmp.__dict__)

    def copy(self):
        copy_tmp = PARA_templet(self.type, self.data.copy())
        return copy_tmp

    def cut(self):
        copy_tmp = self.copy()
        if copy_tmp.data is not None:
            for key_this in self.data:
                if copy_tmp.data[key_this] is None:
                    del copy_tmp.data[key_this]
                else:
                    copy_tmp.data[key_this] = str(copy_tmp.data[key_this])
        return copy_tmp

    def __str__(self):
        return str(self.__dict__)


class PARA(object):
    class text(PARA_templet):
        def __init__(self, text=''):
            PARA_templet.__init__(self, 'text', self.data_T(text))

        class data_T(dict):
            def __init__(self, text=''):
                self['text'] = text

        def get_string_by_key(self, code_key):
            if self.data is not None:
                if type(self.data['text']) is str:
                    return self.data['text']
                else:
                    return str(self.data['text'])
            else:
                return ''

    class face(PARA_templet):
        def __init__(self, id):
            PARA_templet.__init__(self, 'face', self.data_T(id))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id

    class image(PARA_templet):
        def __init__(self, file, type=None, url=None, cache=None, proxy=None, timeout=None):
            PARA_templet.__init__(self, 'image', self.data_T(file, type, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, type, url, cache, proxy, timeout):
                self['file'] = file
                self['type'] = type
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

        def get_string_by_key(self, code_key):
            code_tmp = '[' + code_key + ':' + self.type
            if self.data is not None:
                for key_this in self.data:
                    if self.data[key_this] is not None:
                        if code_key == 'CQ' and key_this == 'file':
                            code_tmp += ',' + key_this + '='
                            if self.data['url'] is not None:
                                code_tmp += str(self.data['url'])
                            else:
                                code_tmp += str(self.data[key_this])
                        elif code_key == 'CQ' and key_this == 'url':
                            pass
                        else:
                            code_tmp += ',' + key_this + '=' + str(self.data[key_this])
            code_tmp += ']'
            return code_tmp

    class record(PARA_templet):
        def __init__(self, file, magic=None, url=None, cache=None, proxy=None, timeout=None):
            PARA_templet.__init__(self, 'record', self.data_T(file, magic, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, magic, url, cache, proxy, timeout):
                self['file'] = file
                self['magic'] = magic
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

    class video(PARA_templet):
        def __init__(self, file, url=None, cache=None, proxy=None, timeout=None):
            PARA_templet.__init__(self, 'video', self.data_T(file, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, url, cache, proxy, timeout):
                self['file'] = file
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

    class at(PARA_templet):
        def __init__(self, id, name=None):
            PARA_templet.__init__(self, 'at', self.data_T(id, name))

        class data_T(dict):
            def __init__(self, id, name=None):
                self['id'] = id
                self['name'] = name if (name is not None and name != '') else None

        def get_string_by_key(self, code_key):
            code_tmp = '[' + code_key + ':' + self.type
            if self.data is not None:
                for key_this in self.data:
                    if self.data[key_this] is not None:
                        if code_key == 'CQ' and key_this == 'id':
                            code_tmp += ',qq=' + str(self.data[key_this])
                        elif code_key == 'CQ' and key_this == 'name':
                            code_tmp += ',name=' + str(self.data[key_this])
                        else:
                            code_tmp += ',' + key_this + '=' + str(self.data[key_this])
            code_tmp += ']'
            return code_tmp

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
        def __init__(self, id, type=None, name=None):
            PARA_templet.__init__(self, 'poke', self.data_T(type, id, name))

        class data_T(dict):
            def __init__(self, type, id, name):
                self['type'] = type
                self['id'] = id
                self['name'] = name

    class anonymous(PARA_templet):
        def __init__(self):
            PARA_templet.__init__(self, 'anonymous', None)

    class share(PARA_templet):
        def __init__(self, url, title, content=None, image=None):
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
        def __init__(self, lat, lon, title=None, content=None):
            PARA_templet.__init__(self, 'location', self.data_T(lat, lon, title, content))

        class data_T(dict):
            def __init__(self, lat, lon, title, content):
                self['lat'] = lat
                self['lon'] = lon
                self['title'] = title
                self['content'] = content

    class music(PARA_templet):
        def __init__(self, type, id=None, url=None, audio=None, title=None, content=None, image=None):
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
        def __init__(self, id=None, user_id=None, nickname=None, content=None):
            PARA_templet.__init__(self, 'node', self.data_T(id, user_id, nickname, content))

        class data_T(dict):
            def __init__(self, id, user_id, nickname, content):
                self['id'] = id
                self['user_id'] = user_id
                self['nickname'] = nickname
                self['content'] = content

    class xml(PARA_templet):
        def __init__(self, data, resid=None):
            PARA_templet.__init__(self, 'xml', self.data_T(data, resid))

        class data_T(dict):
            def __init__(self, data, resid):
                self['data'] = data
                self['resid'] = resid

    class json(PARA_templet):
        def __init__(self, data, resid=None):
            PARA_templet.__init__(self, 'json', self.data_T(data, resid))

        class data_T(dict):
            def __init__(self, data, resid):
                self['data'] = data
                self['resid'] = resid
