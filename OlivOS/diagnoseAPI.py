# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/diagnoseAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import ctypes
import multiprocessing
import platform
import time
import datetime
import os

import OlivOS

logfile_dir = './logfile'
logfile_file = 'OlivOS_logfile_%s.log'
logfile_file_unity = 'OlivOS_logfile_unity.log'

level_dict = {
    -1 : 'TRACE',
    0  : 'DEBUG',
    1  : 'NOTE' ,
    2  : 'INFO' ,
    3  : 'WARN' ,
    4  : 'ERROR',
    5  : 'FATAL'
}

level_color_dict = {
    'TRACE' : '#666666',
    'DEBUG'  : 'green',
    'NOTE'  : 'black' ,
    'INFO'  : 'black' ,
    'WARN'  : '#E6992C', # 原版'yellow'亮瞎狗眼，换一个
    'ERROR'  : 'red',
    'FATAL'  : 'red'
}

dict_ctype = {
    'STD_HANDLE': {
        'STD_INPUT_HANDLE'  : -10,
        'STD_OUTPUT_HANDLE' : -11,
        'STD_ERROR_HANDLE'  : -12
    }
}

def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

class logger(OlivOS.API.Proc_templet):
    def __init__(
        self,
        Proc_name = 'native_logger',
        scan_interval = 0.001,
        dead_interval = 1,
        logger_queue = None,
        logger_mode = 'console',
        logger_vis_level = [2, 3, 4, 5],
        control_queue = None
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name = Proc_name,
            Proc_type = 'logger',
            scan_interval = scan_interval,
            dead_interval = dead_interval,
            rx_queue = logger_queue,
            tx_queue = None,
            control_queue = control_queue,
            logger_proc = self
        )
        self.Proc_config['logger_queue'] = logger_queue
        self.Proc_config['logger_mode'] = logger_mode
        self.Proc_config['level_dict'] = level_dict
        self.Proc_config['color_dict'] = {
            'color': {
                'BLACK'       : 0,
                'RED'         : 1,
                'GREEN'       : 2,
                'YELLOW'      : 3,
                'BLUE'        : 4,
                'MAGENTA'     : 5,
                'CYAN'        : 6,
                'WHITE'       : 7
            },
            'type': {
                'front'       : 3,
                'background'  : 4
            },
            'shader': {
                'default'     : 0 ,
                'highlight'   : 1 ,
                '-highlight'  : 22,
                'underline'   : 4 ,
                '-underline'  : 24,
                'blink'       : 5 ,
                '-blink'      : 25,
                'reverse'     : 7 ,
                '-reverse'    : 27,
                'invisiable'  : 8 ,
                '-invisiable' : 28
            },
            'color_win': {
                'BLACK'       : 0                       , # None
                'BLUE'        : 1 << 0                  , # B
                'GREEN'       : 1 << 1                  , # G
                'RED'         : 1 << 2                  , # R
                'YELLOW'      : 1 << 1 | 1 << 2         , # G + R
                'MAGENTA'     : 1 << 0 | 1 << 2         , # B + R
                'CYAN'        : 1 << 0 | 1 << 1         , # B + G
                'WHITE'       : 1 << 0 | 1 << 1 | 1 << 2  # G + B + R
            },
            'type_win': {
                'front'       : 0,
                'background'  : 4
            },
            'shader_win': {
                'default'     : 0     ,
                'highlight'   : 1 << 3,
                '-highlight'  : 0     ,
                'underline'   : 0     ,
                '-underline'  : 0     ,
                'blink'       : 0     ,
                '-blink'      : 0     ,
                'reverse'     : 1 << 3,
                '-reverse'    : 0     ,
                'invisiable'  : 0     ,
                '-invisiable' : 0
            },
            'mapping': {
                'need': [-1, 0, 3, 4, 5],
                'front': {
                    -1: 'BLUE',
                    0: 'GREEN',
                    3: 'YELLOW',
                    4: 'RED',
                    5: 'RED',
                },
                'background': {},
                'shader': {
                    5: 'reverse'
                }
            }
        }
        self.Proc_data['extend_data'] = {
            'std_out_handle': None
        }
        self.Proc_config['logger_vis_level'] = logger_vis_level
        self.Proc_config['segment_type'] = {
            'default' : ['[', ']'],
            'callback' : ['<', '>']
        }
        self.Proc_config['logfile_count'] = 10
        self.Proc_data['logfile_count'] = self.Proc_config['logfile_count']
        self.Proc_config['logfile_count_out'] = 5000
        self.Proc_data['logfile_count_out'] = self.Proc_config['logfile_count_out']
        self.Proc_data['data_tmp'] = {
            'logfile': ''
        }

    class log_packet(dict):
        def __init__(self, log_level, log_message, log_time, log_segment = []):
            self['log_level'] = log_level
            self['log_message'] = log_message
            self['log_time'] = log_time
            self['log_segment'] = log_segment

    def run(self):
        releaseDir(logfile_dir)
        self.log_output_shader_init()
        self.log(2, 'Welcome to OlivOS %s' % OlivOS.infoAPI.OlivOS_Version_Short)
        with open('%s/%s' % (logfile_dir, logfile_file_unity), 'w', encoding = 'utf-8') as logfile_f:
            pass
        self.log(2, 'OlivOS diagnose logger [' + self.Proc_name + '] is running')
        flag_need_refresh = False
        while True:
            if self.Proc_data['logfile_count_out'] >= 0:
                self.Proc_data['logfile_count_out'] -= 1
            if self.Proc_data['logfile_count_out'] == 0:
                flag_need_refresh = True
            if self.Proc_info.rx_queue.empty():
                time.sleep(self.Proc_info.scan_interval)
                continue
            else:
                try:
                    packet_this = self.Proc_info.rx_queue.get(block = False)
                except:
                    continue
                self.log_output(packet_this, flag_need_refresh)
            if flag_need_refresh:
                self.save_logfile()
                flag_need_refresh = False
                self.Proc_data['logfile_count_out'] = self.Proc_config['logfile_count_out']

    def log(self, log_level, log_message, log_segment = []):
        try:
            self.Proc_config['logger_queue'].put(self.log_packet(log_level, log_message, time.time(), log_segment), block = False)
        except:
            pass

    def save_logfile(self):
        if self.Proc_data['data_tmp']['logfile'] != '':
            file_name = logfile_file % str(time.strftime('%Y-%m-%d', time.localtime()))
            file_name_unity = logfile_file_unity
            with open('%s/%s' % (logfile_dir, file_name), 'a+', encoding = 'utf-8') as logfile_f:
                try:
                    logfile_f.write(self.Proc_data['data_tmp']['logfile'])
                except:
                    pass
            with open('%s/%s' % (logfile_dir, file_name_unity), 'a+', encoding = 'utf-8') as logfile_f:
                try:
                    logfile_f.write(self.Proc_data['data_tmp']['logfile'])
                except:
                    pass
            self.Proc_data['data_tmp']['logfile'] = ''

    def log_output_shader_key(self, key = None):
        keylist = key
        keylist_str = None
        keylist_new = []
        keylist_new_this = None
        if keylist == None:
            keylist = [self.Proc_config['color_dict']['shader']['default']]
        for keylist_this in keylist:
            keylist_new_this = None
            if type(keylist_this) == list:
                keylist_new_this = ''
                for keylist_this_this in keylist_this:
                    keylist_new_this += str(keylist_this_this)
            elif type(keylist_this) == int:
                keylist_new_this = str(keylist_this)
            elif type(keylist_this) == str:
                keylist_new_this = keylist_this
            if keylist_new_this == '':
                keylist_new_this = None
            if keylist_new_this != None:
                if type(keylist_new_this) == str:
                    keylist_new.append(keylist_new_this)
        keylist_str = '\033[%sm' % (';'.join(keylist_new),)
        return keylist_str

    def log_output_shader_init(self):
        tmp_logger_mode_list = []
        if type(self.Proc_config['logger_mode']) == str:
            tmp_logger_mode_list = [self.Proc_config['logger_mode']]
        elif type(self.Proc_config['logger_mode']) == list:
            tmp_logger_mode_list = self.Proc_config['logger_mode']
        if 'console_color' in tmp_logger_mode_list and platform.system() == 'Windows':
            self.Proc_data['extend_data']['std_out_handle'] = ctypes.windll.kernel32.GetStdHandle(dict_ctype['STD_HANDLE']['STD_OUTPUT_HANDLE'])
            if self.Proc_data['extend_data']['std_out_handle'] != None:
                ctypes.windll.kernel32.SetConsoleTextAttribute(
                    self.Proc_data['extend_data']['std_out_handle'],
                    self.Proc_config['color_dict']['shader_win'][
                        'default'
                    ] | self.Proc_config['color_dict']['color_win'][
                        'WHITE'
                    ] << self.Proc_config['color_dict']['type_win'][
                        'front'
                    ]
                )

    def log_output_shader(self, log_output_str, log_packet_this):
        tmp_color = 'WHITE'
        tmp_color_bak = 'BLACK'
        tmp_shader = 'default'
        flag_have_color = False
        if log_packet_this['log_level'] in self.Proc_config['color_dict']['mapping']['need']:
            flag_have_color = True
            if log_packet_this['log_level'] in self.Proc_config['color_dict']['mapping']['front']:
                tmp_color = self.Proc_config['color_dict']['mapping']['front'][log_packet_this['log_level']]
            if log_packet_this['log_level'] in self.Proc_config['color_dict']['mapping']['background']:
                tmp_color_bak = self.Proc_config['color_dict']['mapping']['background'][log_packet_this['log_level']]
            if log_packet_this['log_level'] in self.Proc_config['color_dict']['mapping']['shader']:
                tmp_shader = self.Proc_config['color_dict']['mapping']['shader'][log_packet_this['log_level']]
        if platform.system() == 'Windows':
            if flag_have_color and self.Proc_data['extend_data']['std_out_handle'] != None:
                ctypes.windll.kernel32.SetConsoleTextAttribute(
                    self.Proc_data['extend_data']['std_out_handle'],
                    self.Proc_config['color_dict']['shader_win'][
                        tmp_shader
                    ] | self.Proc_config['color_dict']['color_win'][
                        tmp_color
                    ] << self.Proc_config['color_dict']['type_win'][
                        'front'
                    ]
                )
            print(log_output_str)
            ctypes.windll.kernel32.SetConsoleTextAttribute(
                self.Proc_data['extend_data']['std_out_handle'],
                self.Proc_config['color_dict']['shader_win'][
                    tmp_shader
                ] | self.Proc_config['color_dict']['color_win'][
                    'WHITE'
                ] << self.Proc_config['color_dict']['type_win'][
                    'front'
                ]
            )
        elif flag_have_color:
            log_output_str = '%s%s%s' % (
                self.log_output_shader_key([
                    self.Proc_config['color_dict']['shader'][tmp_shader],
                    [
                        self.Proc_config['color_dict']['type']['front'],
                        self.Proc_config['color_dict']['color'][tmp_color]
                    ]
                ]),
                log_output_str,
                self.log_output_shader_key([
                    self.Proc_config['color_dict']['shader']['default']
                ])
            )
            print(log_output_str)
        else:
            print(log_output_str)

    def log_output(self, log_packet_this, flag_need_refresh_out = False):
        tmp_logger_mode_list = []
        flag_need_refresh = False
        if log_packet_this['log_level'] in self.Proc_config['logger_vis_level']:
            self.Proc_data['logfile_count'] -= 1
            if self.Proc_data['logfile_count'] <= 0 or flag_need_refresh_out:
                self.Proc_data['logfile_count'] = self.Proc_config['logfile_count']
                flag_need_refresh = True
            if type(self.Proc_config['logger_mode']) == str:
                tmp_logger_mode_list = [self.Proc_config['logger_mode']]
            elif type(self.Proc_config['logger_mode']) == list:
                tmp_logger_mode_list = self.Proc_config['logger_mode']
            for tmp_logger_mode_list_this in tmp_logger_mode_list:
                if tmp_logger_mode_list_this in [
                    'console',
                    'console_color',
                    'logfile',
                    'native'
                ]:
                    log_output_str = ''
                    log_output_str += '[' + str(datetime.datetime.fromtimestamp(int(log_packet_this['log_time']))) + '] - '
                    log_output_str += '[' + self.Proc_config['level_dict'][log_packet_this['log_level']] + ']' + ' - '
                    log_output_str_1 = self.__get_log_message(log_packet_this)
                    log_output_str += log_output_str_1
                    if tmp_logger_mode_list_this == 'console_color':
                        self.log_output_shader(log_output_str, log_packet_this)
                    elif tmp_logger_mode_list_this == 'console':
                        print(log_output_str)
                    elif tmp_logger_mode_list_this == 'logfile':
                        self.Proc_data['data_tmp']['logfile'] += '%s\n' % log_output_str
                        if flag_need_refresh:
                            self.save_logfile()
        if type(self.Proc_config['logger_mode']) == list and 'native' in self.Proc_config['logger_mode']:
            self.__sendControlEventSend('send', {
                    'target': {
                        'type': 'nativeWinUI'
                    },
                    'data': {
                        'action': 'logger',
                        'event': 'log',
                        'data': {
                            'data': log_packet_this,
                            'str': self.__get_log_message(log_packet_this)
                        }
                    }
                }
            )

    def __get_log_message(self, log_packet_this):
        log_output_str_1 = ''
        for segment_this in log_packet_this['log_segment']:
            (segment_this_mark, segment_this_type) = segment_this
            log_output_str_1 += self.Proc_config['segment_type'][segment_this_type][0]
            log_output_str_1 += str(segment_this_mark)
            log_output_str_1 += self.Proc_config['segment_type'][segment_this_type][1] + ' - '
        log_output_str_1 += log_packet_this['log_message']
        return log_output_str_1

    def __sendControlEventSend(self, action, data):
        if self.Proc_info.control_queue != None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block = False
            )
