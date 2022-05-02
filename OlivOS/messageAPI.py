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
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import json
import re

import OlivOS
import traceback

#platform sdk model
dictMessageType = {
    'qq': {
        'onebot': {
            'default': 'old_string',
            'gocqhttp_show': 'old_string'
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
            'default': 'olivos_para'
        }
    },
    'dodo': {
        'dodo_link': {
            'default': 'olivos_para'
        },
        'dodo_poll': {
            'default': 'olivos_para'
        },
        'dodobot_ea': {
            'default': 'olivos_para'
        }
    },
    'fake': {
        'fake': {
            'default': 'olivos_para'
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

    def get_from_dict(self, src_dict, key_list, default_val = None):
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
        else:
            res = str(self)
        return res

    def init_data(self):
        if self.mode_rx == 'olivos_para':
            self.init_from_olivos_para()
        elif self.mode_rx == 'olivos_string':
            self.init_from_code_string('OP')
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

    def init_from_olivos_para(self):
        tmp_data = []
        if type(self.data_raw) == list:
            for data_raw_this in self.data_raw:
                if data_raw_this.__class__.__base__ == PARA_templet:
                    tmp_data.append(data_raw_this)
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
                            id = str(self.get_from_dict(tmp_code_data_dict, ['id']))
                        )
                    elif tmp_data_type_key == 'at':
                        if code_key == 'CQ':
                            tmp_code_data_dict['id'] = str(self.get_from_dict(tmp_code_data_dict, ['qq'], -1))
                        tmp_para_this = PARA.at(
                            id = str(self.get_from_dict(tmp_code_data_dict, ['id'], -1))
                        )
                    elif tmp_data_type_key == 'reply':
                        tmp_para_this = PARA.reply(
                            id = str(self.get_from_dict(tmp_code_data_dict, ['id'], 0))
                        )
                    elif tmp_data_type_key == 'image':
                        tmp_para_this = PARA.image(
                            file = str(self.get_from_dict(tmp_code_data_dict, ['file'])),
                            type = self.get_from_dict(tmp_code_data_dict, ['type'], None),
                            url = self.get_from_dict(tmp_code_data_dict, ['url'], None)
                        )
                    elif tmp_data_type_key == 'record':
                        tmp_para_this = PARA.record(
                            file = str(self.get_from_dict(tmp_code_data_dict, ['file'])),
                            url = str(self.get_from_dict(tmp_code_data_dict, ['url']))
                        )
                    elif tmp_data_type_key == 'video':
                        tmp_para_this = PARA.video(
                            file = str(self.get_from_dict(tmp_code_data_dict, ['file'])),
                            url = str(self.get_from_dict(tmp_code_data_dict, ['url']))
                        )
                    elif tmp_data_type_key == 'rps':
                        tmp_para_this = PARA.rps()
                    elif tmp_data_type_key == 'dice':
                        tmp_para_this = PARA.dice()
                    elif tmp_data_type_key == 'shake':
                        tmp_para_this = PARA.shake()
                    elif tmp_data_type_key == 'poke':
                        tmp_para_this = PARA.poke(
                            id = str(self.get_from_dict(tmp_code_data_dict, ['id'], -1))
                        )
                    elif tmp_data_type_key == 'anonymous':
                        tmp_para_this = PARA.anonymous()
                    elif tmp_data_type_key == 'share':
                        tmp_para_this = PARA.share(
                            url = str(self.get_from_dict(tmp_code_data_dict, ['url'], '')),
                            title = str(self.get_from_dict(tmp_code_data_dict, ['title'], '')),
                            content = str(self.get_from_dict(tmp_code_data_dict, ['content'], '')),
                            image = str(self.get_from_dict(tmp_code_data_dict, ['image'], ''))
                        )
                    elif tmp_data_type_key == 'location':
                        tmp_para_this = PARA.location(
                            lat = str(self.get_from_dict(tmp_code_data_dict, ['lat'], '')),
                            lon = str(self.get_from_dict(tmp_code_data_dict, ['lon'], '')),
                            title = str(self.get_from_dict(tmp_code_data_dict, ['title'], '')),
                            content = str(self.get_from_dict(tmp_code_data_dict, ['content'], ''))
                        )
                    elif tmp_data_type_key == 'music':
                        tmp_para_this = PARA.music(
                            type = str(self.get_from_dict(tmp_code_data_dict, ['type'], '')),
                            id = str(self.get_from_dict(tmp_code_data_dict, ['id'], '')),
                            url = str(self.get_from_dict(tmp_code_data_dict, ['url'], '')),
                            audio = str(self.get_from_dict(tmp_code_data_dict, ['audio'], '')),
                            title = str(self.get_from_dict(tmp_code_data_dict, ['title'], '')),
                            content = str(self.get_from_dict(tmp_code_data_dict, ['content'], '')),
                            image = str(self.get_from_dict(tmp_code_data_dict, ['image'], ''))
                        )
                    elif tmp_data_type_key == 'forward':
                        tmp_para_this = PARA.forward(
                            id = str(self.get_from_dict(tmp_code_data_dict, ['id'], 'NULLHASH'))
                        )
                    elif tmp_data_type_key == 'xml':
                        tmp_para_this = PARA.xml(
                            data = str(self.get_from_dict(tmp_code_data_dict, ['data'], ''))
                        )
                    elif tmp_data_type_key == 'json':
                        tmp_para_this = PARA.json(
                            data = str(self.get_from_dict(tmp_code_data_dict, ['data'], ''))
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
                            id = str(tmp_code_data_list[0])
                        )
                    elif tmp_data_type_key_2 == '@' and len(tmp_code_data_list_2) > 0:
                        tmp_para_this = PARA.at(
                            id = 'all'
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
                            id = str(tmp_code_data_list[0])
                        )
                    elif tmp_data_type_key_2 == '@' and len(tmp_code_data_list_2) > 0:
                        tmp_para_this = PARA.at(
                            id = 'all'
                        )
                    else:
                        tmp_para_this = PARA.at(
                            id = 'all'
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
        tmp_data_raw = re.sub("\\(met\\)(\\d+)\\(met\\)", "@User#\\1 ", tmp_data_raw)
        tmp_data_raw_1 = ''
        tmp_data_raw_2 = ''
        tmp_data_raw_3 = ''
        tmp_data_raw_4 = ''
        tmp_data_raw_list = []
        tmp_data = []
        it_data = range(0, len(tmp_data_raw))
        it_data_base = 0
        tmp_data_type = 'string'
        for it_data_this in it_data:
            if tmp_data_type == 'string' and tmp_data_raw[it_data_this] == '[':
                tmp_data_raw_list = []
                tmp_data_raw_list.append('[')
                tmp_data_type = 'emoji_begin'
            elif tmp_data_type == 'string' and tmp_data_raw[it_data_this] == '@':
                tmp_data_raw_1 = ''
                tmp_data_raw_2 = ''
                tmp_data_raw_3 += tmp_data_raw[it_data_this]
                tmp_data_type = 'code_begin'
            elif tmp_data_type == 'string':
                tmp_data_raw_1 += tmp_data_raw[it_data_this]
                tmp_data_raw_3 += tmp_data_raw[it_data_this]
                tmp_data_raw_4 += tmp_data_raw[it_data_this]
                tmp_data_type = 'string'
            elif tmp_data_type == 'emoji_begin' and tmp_data_raw[it_data_this] == '#':
                tmp_data_raw_list.append(tmp_data_raw[it_data_this])
                tmp_data_type = 'emoji_after'
            elif tmp_data_type == 'emoji_begin':
                tmp_data_raw_1 += ''.join(tmp_data_raw_list) + tmp_data_raw[it_data_this]
                tmp_data_raw_3 += ''.join(tmp_data_raw_list) + tmp_data_raw[it_data_this]
                tmp_data_raw_4 += ''.join(tmp_data_raw_list) + tmp_data_raw[it_data_this]
                tmp_data_type = 'string'
            elif tmp_data_type == 'emoji_after' and tmp_data_raw[it_data_this].isdigit():
                tmp_data_raw_list.append(tmp_data_raw[it_data_this])
                tmp_data_type = 'emoji_after'
            elif tmp_data_type == 'emoji_after' and tmp_data_raw[it_data_this] == ';':
                tmp_data_raw_list.append(tmp_data_raw[it_data_this])
                tmp_data_type = 'emoji_after_last'
            elif tmp_data_type == 'emoji_after':
                tmp_data_raw_1 += ''.join(tmp_data_raw_list) + tmp_data_raw[it_data_this]
                tmp_data_raw_3 += ''.join(tmp_data_raw_list) + tmp_data_raw[it_data_this]
                tmp_data_raw_4 += ''.join(tmp_data_raw_list) + tmp_data_raw[it_data_this]
                tmp_data_type = 'string'
            elif tmp_data_type == 'emoji_after_last' and tmp_data_raw[it_data_this] == ']':
                tmp_emoji = chr(
                    int(
                        ''.join(tmp_data_raw_list[2:-1]),
                        10
                    )
                )
                tmp_data_raw_1 += tmp_emoji
                tmp_data_raw_3 += tmp_emoji
                tmp_data_raw_4 += tmp_emoji
                tmp_data_raw_list = []
                tmp_data_type = 'string'
            elif tmp_data_type == 'emoji_after_last':
                tmp_data_raw_1 += ''.join(tmp_data_raw_list) + tmp_data_raw[it_data_this]
                tmp_data_raw_3 += ''.join(tmp_data_raw_list) + tmp_data_raw[it_data_this]
                tmp_data_raw_4 += ''.join(tmp_data_raw_list) + tmp_data_raw[it_data_this]
                tmp_data_type = 'string'
            elif tmp_data_type == 'code_begin' and tmp_data_raw[it_data_this] == '#':
                tmp_data_raw_1 = ''
                tmp_data_raw_3 += tmp_data_raw[it_data_this]
                tmp_data_type = 'code_after'
            elif tmp_data_type == 'code_begin':
                tmp_data_raw_2 += tmp_data_raw[it_data_this]
                tmp_data_raw_3 += tmp_data_raw[it_data_this]
                tmp_data_type = 'code_begin'
            elif tmp_data_type == 'code_after' and tmp_data_raw[it_data_this].isdigit():
                tmp_data_raw_1 += tmp_data_raw[it_data_this]
                tmp_data_raw_3 += tmp_data_raw[it_data_this]
                tmp_data_type = 'code_after'
            elif tmp_data_type == 'code_after':
                if tmp_data_raw_1 != '':
                    if tmp_data_raw_4 != '':
                        tmp_data.append(
                            PARA.text(tmp_data_raw_4)
                        )
                    tmp_data.append(
                        PARA.at(
                            id = tmp_data_raw_1
                        )
                    )
                else:
                    tmp_data.append(
                        PARA.text(tmp_data_raw_3)
                    )
                tmp_data_raw_1 = ''
                tmp_data_raw_2 = ''
                tmp_data_raw_3 = ''
                tmp_data_raw_4 = ''
                tmp_data_raw_3 += tmp_data_raw[it_data_this]
                tmp_data_raw_4 += tmp_data_raw[it_data_this]
                tmp_data_type = 'string'
        if tmp_data_type == 'code_after' and tmp_data_raw_1 != '':
            if tmp_data_raw_4 != '':
                tmp_data.append(
                    PARA.text(tmp_data_raw_4)
                )
            tmp_data.append(
                PARA.at(
                    id = tmp_data_raw_1
                )
            )
        else:
            tmp_data.append(
                PARA.text(tmp_data_raw_3)
            )
        self.data = tmp_data


class PARA_templet(object):
    def __init__(self, type = None, data = None):
        self.type = type
        self.data = data

    def CQ(self):
        return self.get_string_by_key('CQ')

    def OP(self):
        return self.get_string_by_key('OP')

    def kaiheila(self):
        code_tmp = '${'
        if type(self) == PARA.at:
            if self.data != None:
                for key_this in self.data:
                    if self.data[key_this] != None:
                        code_tmp += '@'
                        code_tmp += '#' + str(self.data[key_this])
        elif type(self) == PARA.text:
            if self.data != None:
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
            if self.data != None:
                for key_this in self.data:
                    if self.data[key_this] != None:
                        code_tmp += '@'
                        code_tmp += '!' + str(self.data[key_this])
        elif type(self) == PARA.text:
            if self.data != None:
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
            if self.data != None:
                for key_this in self.data:
                    if self.data[key_this] != None:
                        code_tmp += '@'
                        code_tmp += '!' + str(self.data[key_this])
        elif type(self) == PARA.text:
            if self.data != None:
                if type(self.data['text']) is str:
                    return self.data['text']
                else:
                    return str(self.data['text'])
            else:
                return ''
        code_tmp += '>'
        return code_tmp

    def get_string_by_key(self, code_key):
        code_tmp = '[' + code_key + ':' + self.type
        if self.data != None:
            for key_this in self.data:
                if self.data[key_this] != None:
                    code_tmp += ',' + key_this + '=' + str(self.data[key_this])
        code_tmp += ']'
        return code_tmp

    def PARA(self):
        PARA_tmp = self.cut()
        if self.data == None:
            PARA_tmp.data = dict()
        return json.dumps(obj = PARA_tmp.__dict__)

    def copy(self):
        copy_tmp = PARA_templet(self.type, self.data.copy())
        return copy_tmp

    def cut(self):
        copy_tmp = self.copy()
        if copy_tmp.data != None:
            for key_this in self.data:
                if copy_tmp.data[key_this] == None:
                    del copy_tmp.data[key_this]
                else:
                    copy_tmp.data[key_this] = str(copy_tmp.data[key_this])
        return copy_tmp

    def __str__(self):
        return str(self.__dict__)

class PARA(object):
    class text(PARA_templet):
        def __init__(self, text = ''):
            PARA_templet.__init__(self, 'text', self.data_T(text))

        class data_T(dict):
            def __init__(self, text = ''):
                self['text'] = text

        def get_string_by_key(self, code_key):
            if self.data != None:
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
        def __init__(self, file, type = None, url = None, cache = None, proxy = None, timeout = None):
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
            if self.data != None:
                for key_this in self.data:
                    if self.data[key_this] != None:
                        if code_key == 'CQ' and key_this == 'file':
                            code_tmp += ',' + key_this + '='
                            if self.data['url'] != None:
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
        def __init__(self, file, magic = None, url = None, cache = None, proxy = None, timeout = None):
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
        def __init__(self, file, url = None, cache = None, proxy = None, timeout = None):
            PARA_templet.__init__(self, 'record', self.data_T(file, url, cache, proxy, timeout))

        class data_T(dict):
            def __init__(self, file, url, cache, proxy, timeout):
                self['file'] = file
                self['url'] = url
                self['cache'] = cache
                self['proxy'] = proxy
                self['timeout'] = timeout

    class at(PARA_templet):
        def __init__(self, id):
            PARA_templet.__init__(self, 'at', self.data_T(id))

        class data_T(dict):
            def __init__(self, id):
                self['id'] = id

        def get_string_by_key(self, code_key):
            code_tmp = '[' + code_key + ':' + self.type
            if self.data != None:
                for key_this in self.data:
                    if self.data[key_this] != None:
                        if code_key == 'CQ' and key_this == 'id':
                            code_tmp += ',qq=' + str(self.data[key_this])
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
        def __init__(self, id, type = None, name = None):
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
        def __init__(self, url, title, content = None, image = None):
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
        def __init__(self, lat, lon, title = None, content = None):
            PARA_templet.__init__(self, 'location', self.data_T(lat, lon, title, content))

        class data_T(dict):
            def __init__(self, lat, lon, title, content):
                self['lat'] = lat
                self['lon'] = lon
                self['title'] = title
                self['content'] = content

    class music(PARA_templet):
        def __init__(self, type, id = None, url = None, audio = None, title = None, content = None, image = None):
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
        def __init__(self, id = None, user_id = None, nickname = None, content = None):
            PARA_templet.__init__(self, 'node', self.data_T(id, user_id, nickname, content))

        class data_T(dict):
            def __init__(self, id, user_id, nickname, content):
                self['id'] = id
                self['user_id'] = user_id
                self['nickname'] = nickname
                self['content'] = content

    class xml(PARA_templet):
        def __init__(self, data, resid = None):
            PARA_templet.__init__(self, 'xml', self.data_T(data, resid))

        class data_T(dict):
            def __init__(self, data, resid):
                self['data'] = data
                self['resid'] = resid

    class json(PARA_templet):
        def __init__(self, data, resid = None):
            PARA_templet.__init__(self, 'json', self.data_T(data, resid))

        class data_T(dict):
            def __init__(self, data, resid):
                self['data'] = data
                self['resid'] = resid
