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

import multiprocessing
import time
import datetime
import os

import OlivOS

logfile_dir = './logfile'
logfile_file = 'OlivOS_logfile_%s.log'
logfile_file_unity = 'OlivOS_logfile_unity.log'


def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

class logger(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name = 'native_logger', scan_interval = 0.001, dead_interval = 1, logger_queue = None, logger_mode = 'console', logger_vis_level = [2, 3, 4, 5]):
        OlivOS.API.Proc_templet.__init__(self, Proc_name = Proc_name, Proc_type = 'logger', scan_interval = scan_interval, dead_interval = dead_interval, rx_queue = logger_queue, tx_queue = None, logger_proc = self)
        self.Proc_config['logger_queue'] = logger_queue
        self.Proc_config['logger_mode'] = logger_mode
        self.Proc_config['level_dict'] = {
            -1 : 'TRACE',
            0 : 'DEBUG',
            1 : 'NOTE',
            2 : 'INFO',
            3 : 'WARN',
            4 : 'ERROR',
            5 : 'FATAL'
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
        self.log(2, 'Welcome to OlivOS %s' % OlivOS.infoAPI.OlivOS_Version_Short)
        releaseDir(logfile_dir)
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
                    'logfile'
                ]:
                    log_output_str = ''
                    log_output_str += '[' + str(datetime.datetime.fromtimestamp(int(log_packet_this['log_time']))) + '] - '
                    log_output_str += '[' + self.Proc_config['level_dict'][log_packet_this['log_level']] + ']' + ' - '
                    for segment_this in log_packet_this['log_segment']:
                        (segment_this_mark, segment_this_type) = segment_this
                        log_output_str += self.Proc_config['segment_type'][segment_this_type][0]
                        log_output_str += str(segment_this_mark)
                        log_output_str += self.Proc_config['segment_type'][segment_this_type][1] + ' - '
                    log_output_str += log_packet_this['log_message']
                    if tmp_logger_mode_list_this == 'console':
                        print(log_output_str)
                    elif tmp_logger_mode_list_this == 'logfile':
                        self.Proc_data['data_tmp']['logfile'] += '%s\n' % log_output_str
                        if flag_need_refresh:
                            self.save_logfile()
