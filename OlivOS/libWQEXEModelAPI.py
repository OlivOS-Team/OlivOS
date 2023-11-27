# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/libWQEXEModelAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import multiprocessing
import subprocess
import threading
import time
import os
import traceback
import json
import copy
import random
import uuid
import hashlib
import platform
import shutil

import OlivOS

modelName = 'libWQEXEModelAPI'

resourceUrlPath = OlivOS.infoAPI.resourceUrlPath

gCheckList = [
    'walleq',
    'walleq_hide',
    'walleq_show',
    'walleq_show_Android_Phone',
    'walleq_show_Android_Pad',
    'walleq_show_Android_Watch',
    'walleq_show_iPad',
    'walleq_show_old',
]


def startWalleQLibExeModel(
    plugin_bot_info_dict,
    basic_conf_models_this,
    multiprocessing_dict,
    Proc_dict,
    Proc_Proc_dict,
    basic_conf_models,
    tmp_proc_mode
):
    if platform.system() == 'Windows':
        flagActive = False
        for bot_info_key in plugin_bot_info_dict:
            if plugin_bot_info_dict[bot_info_key].platform['model'] in gCheckList:
                flagActive = True
        if flagActive:
            releaseDir('./lib')
            OlivOS.updateAPI.checkResouceFile(
                logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                resouce_api=resourceUrlPath,
                resouce_name='walle-q',
                filePath='./lib/walle-q.exe',
                filePathUpdate='./lib/walle-q.exe.tmp',
                filePathFORCESKIP='./lib/FORCESKIP'
            )
        for bot_info_key in plugin_bot_info_dict:
            if plugin_bot_info_dict[bot_info_key].platform['model'] in gCheckList:
                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                Proc_dict[tmp_Proc_name] = OlivOS.libWQEXEModelAPI.server(
                    Proc_name=tmp_Proc_name,
                    scan_interval=basic_conf_models_this['interval'],
                    dead_interval=basic_conf_models_this['dead_interval'],
                    rx_queue=multiprocessing_dict[tmp_queue_name],
                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                    control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']],
                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                    target_proc=None,
                    debug_mode=False
                )
                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(tmp_proc_mode)

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval=0.001, dead_interval=1, rx_queue=None, tx_queue=None,
                 control_queue=None, logger_proc=None, target_proc=None, debug_mode=False, bot_info_dict=None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='walleq_lib_exe_model',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            control_queue=control_queue,
            logger_proc=logger_proc
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_config['target_proc'] = target_proc
        self.Proc_data['check_qrcode_flag'] = False
        self.Proc_data['check_stdin'] = False
        self.Proc_data['model_Proc'] = None
        self.flag_run = True

    def run(self):
        if self.Proc_data['bot_info_dict'].platform['model'] in [
            'walleq_show',
            'walleq_show_Android_Phone',
            'walleq_show_Android_Watch',
            'walleq_show_iMac',
            'walleq_show_iPad',
            'walleq_show_Android_Pad'
        ]:
            self.send_init_event()
        while self.flag_run:
            releaseDir('./lib')
            if not os.path.exists('./lib/walle-q.exe'):
                self.log(3, OlivOS.L10NAPI.getTrans(
                    'OlivOS libWQEXEModel server [{0}] can`t found target lib',
                    [self.Proc_name], modelName
                ))
                break
            releaseDir('./conf')
            releaseDir('./conf/walleq')
            releaseDir('./conf/walleq/' + self.Proc_data['bot_info_dict'].hash)
            wqTypeConfig(self.Proc_data['bot_info_dict']).setConfig()
            if self.Proc_data['bot_info_dict'].platform['model'] in [
                'walleq',
                'walleq_show',
                'walleq_show_Android_Phone',
                'walleq_show_Android_Watch',
                'walleq_show_iMac',
                'walleq_show_iPad',
                'walleq_show_Android_Pad'
            ]:
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS libWQEXEModel server [{0}] will run under visiable mode',
                    [self.Proc_name], modelName
                ))
                self.clear_walleq()
                self.Proc_data['check_qrcode_flag'] = False
                self.Proc_data['check_stdin'] = False
                time.sleep(2)
                self.Proc_data['check_qrcode_flag'] = True
                self.Proc_data['check_stdin'] = True
                threading.Thread(
                    target=self.check_qrcode,
                    args=(),
                    daemon=self.deamon
                ).start()
                tmp_env = dict(os.environ)
                model_Proc = subprocess.Popen(
                    '..\\..\\..\\lib\\walle-q.exe',
                    cwd='.\\conf\\walleq\\' + self.Proc_data['bot_info_dict'].hash,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    env=tmp_env
                )
                self.Proc_data['model_Proc'] = model_Proc
                threading.Thread(
                    target=self.check_stdin,
                    args=(model_Proc,),
                    daemon=self.deamon
                ).start()
                self.get_model_stdout(model_Proc)
                # model_Proc.communicate(timeout = None)
                self.log(3, OlivOS.L10NAPI.getTrans(
                    'OlivOS libWQEXEModel server [{0}] will retry in 10s...',
                    [self.Proc_name], modelName
                ))
                self.Proc_data['model_Proc'] = None
                time.sleep(8)
            elif self.Proc_data['bot_info_dict'].platform['model'] in [
                'walleq_show_old'
            ]:
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS libWQEXEModel server [{0}] will run under visiable mode',
                    [self.Proc_name], modelName
                ))
                tmp_env = dict(os.environ)
                subprocess.call(
                    'start cmd /K "title WalleQ For OlivOS|..\\..\\..\\lib\\walle-q.exe"',
                    shell=True,
                    cwd='.\\conf\\walleq\\' + self.Proc_data['bot_info_dict'].hash,
                    env=tmp_env
                )
                self.flag_run = False

    def on_terminate(self):
        self.flag_run = False
        if 'model_Proc' in self.Proc_data \
        and self.Proc_data['model_Proc'] is not None:
            OlivOS.bootAPI.killByPid(self.Proc_data['model_Proc'].pid)

    def getBotIDStr(self):
        tmp_self_data = self.Proc_data['bot_info_dict'].platform['platform']
        if self.Proc_data['bot_info_dict'].id is not None:
            tmp_self_data = '%s|%s' % (
                self.Proc_data['bot_info_dict'].platform['platform'],
                str(self.Proc_data['bot_info_dict'].id)
            )
        return tmp_self_data

    def check_stdin(self, model_Proc: subprocess.Popen):
        while self.Proc_data['check_stdin']:
            if self.Proc_info.rx_queue.empty():
                time.sleep(0.02)
            else:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block=False)
                except:
                    rx_packet_data = None
                if 'data' in rx_packet_data.key and 'action' in rx_packet_data.key['data']:
                    if 'input' == rx_packet_data.key['data']['action']:
                        if 'data' in rx_packet_data.key['data']:
                            input_raw = str(rx_packet_data.key['data']['data'])
                            input_data = ('%s\r\n' % input_raw).encode('utf-8')
                            model_Proc.stdin.write(input_data)
                            model_Proc.stdin.flush()
                            log_data = ('%s' % input_raw)
                            self.send_log_event(log_data)
                            self.log(2, log_data, [
                                (self.getBotIDStr(), 'default'),
                                ('walleq', 'default'),
                                ('onebot_send', 'default')
                            ])

    def get_model_stdout(self, model_Proc: subprocess.Popen):
        for line in iter(model_Proc.stdout.readline, b''):
            try:
                log_data = ('%s' % line.decode('utf-8', errors='replace')).rstrip('\n')
                self.send_log_event(log_data)
                self.log(1, log_data, [
                    (self.getBotIDStr(), 'default'),
                    ('walleq', 'default'),
                    ('onebot', 'default')
                ])
            except Exception as e:
                self.log(4, OlivOS.L10NAPI.getTrans('OlivOS libWQEXEModel failed: %s\n%s' % [
                        str(e),
                        traceback.format_exc()
                    ],
                    modelName
                ))

    def send_init_event(self):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'walleq',
                    'event': 'init',
                    'hash': self.Proc_data['bot_info_dict'].hash
                }
            }
        )

    def clear_walleq(self):
        file_path = './conf/walleq/' + self.Proc_data['bot_info_dict'].hash + '/qrcode.png'
        if os.path.exists(file_path):
            os.remove(file_path)

    def check_qrcode(self):
        count = 2 * 60
        file_path = './conf/walleq/' + self.Proc_data['bot_info_dict'].hash + '/qrcode.png'
        while count > 0 and self.Proc_data['check_qrcode_flag']:
            if os.path.exists(file_path):
                self.send_QRCode_event(file_path)
                count = 0
            count -= 1
            time.sleep(1)
        self.Proc_data['check_qrcode_flag'] = False

    def send_QRCode_event(self, path: str):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'walleq',
                    'event': 'qrcode',
                    'hash': self.Proc_data['bot_info_dict'].hash,
                    'path': path
                }
            }
        )

    def send_log_event(self, data):
        self.sendControlEventSend(
            'send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'walleq',
                    'event': 'log',
                    'hash': self.Proc_data['bot_info_dict'].hash,
                    'data': data
                }
            }
        )

    def sendControlEventSend(self, action, data):
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block=False
            )


class wqTypeConfig(object):
    def __init__(self, bot_info_dict:OlivOS.API.bot_info_T):
        self.bot_info_dict = bot_info_dict
        self.config_file_str = ''
        self.config_file_format = {}

    def setConfig(self):
        self.config_file_str = '''[qq.{uin}]
protocol = {protocol}
{password}

[meta]
log_level = "info"
event_cache_size = 10
sled = true
leveldb = false

[onebot]
http = []
http_webhook = []
websocket_rev = []

[[onebot.websocket]]
host = "{host}"
port = {port}

[onebot.heartbeat]
enabled = true
interval = 5
'''

        protocol = 2
        if 'walleq_show_Android_Phone' == self.bot_info_dict.platform['model']:
            protocol = 1
        elif 'walleq_show_Android_Watch' == self.bot_info_dict.platform['model']:
            protocol = 2
        elif 'walleq_show_iMac' == self.bot_info_dict.platform['model']:
            protocol = 3
        elif 'walleq_show_iPad' == self.bot_info_dict.platform['model']:
            protocol = 5

        self.config_file_format['uin'] = str(self.bot_info_dict.id)
        self.config_file_format['protocol'] = str(protocol)
        self.config_file_format['password'] = ''
        if self.bot_info_dict.password != '':
            self.config_file_format['password'] = 'password = "%s"' % self.bot_info_dict.password
        self.config_file_format['token'] = self.bot_info_dict.post_info.access_token
        self.config_file_format['port'] = str(self.bot_info_dict.post_info.port)
        self.config_file_format['host'] = '127.0.0.1'

        self.config_file_str = self.config_file_str.format(**self.config_file_format)

        with open('./conf/walleq/' + self.bot_info_dict.hash + '/walle-q.toml', 'w+', encoding='utf-8') as tmp:
            tmp.write(self.config_file_str)

def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
