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

import OlivOS

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

    class log_packet(dict):
        def __init__(self, log_level, log_message, log_time, log_segment = []):
            self['log_level'] = log_level
            self['log_message'] = log_message
            self['log_time'] = log_time
            self['log_segment'] = log_segment

    def run(self):
        self.log(2, 'OlivOS diagnose logger [' + self.Proc_name + '] is running')
        while True:
            if self.Proc_info.rx_queue.empty():
                time.sleep(self.Proc_info.scan_interval)
                continue
            else:
                try:
                    packet_this = self.Proc_info.rx_queue.get(block = False)
                except:
                    continue
                self.log_output(packet_this)

    def log(self, log_level, log_message, log_segment = []):
        try:
            self.Proc_config['logger_queue'].put(self.log_packet(log_level, log_message, time.time(), log_segment), block = False)
        except:
            pass

    def log_output(self, log_packet_this):
        if log_packet_this['log_level'] in self.Proc_config['logger_vis_level']:
            if self.Proc_config['logger_mode'] == 'console':
                log_output_str = ''
                log_output_str += '[' + str(datetime.datetime.fromtimestamp(int(log_packet_this['log_time']))) + '] - '
                log_output_str += '[' + self.Proc_config['level_dict'][log_packet_this['log_level']] + ']' + ' - '
                for segment_this in log_packet_this['log_segment']:
                    (segment_this_mark, segment_this_type) = segment_this
                    log_output_str += self.Proc_config['segment_type'][segment_this_type][0]
                    log_output_str += str(segment_this_mark)
                    log_output_str += self.Proc_config['segment_type'][segment_this_type][1] + ' - '
                log_output_str += log_packet_this['log_message']
                print(log_output_str)

