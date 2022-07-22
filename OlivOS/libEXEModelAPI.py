# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/libEXEModelAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import multiprocessing
import subprocess
import threading
import time
import os
import traceback

import OlivOS

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval = 0.001, dead_interval = 1, rx_queue = None, tx_queue = None, control_queue = None, logger_proc = None, target_proc = None, debug_mode = False, bot_info_dict = None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name = Proc_name,
            Proc_type = 'lib_exe_model',
            scan_interval = scan_interval,
            dead_interval = dead_interval,
            rx_queue = rx_queue,
            tx_queue = tx_queue,
            control_queue = control_queue,
            logger_proc = logger_proc
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_config['target_proc'] = target_proc
        self.Proc_data['check_qrcode_flag'] = False
        self.Proc_data['check_stdin'] = False

    def run(self):
        flag_run = True
        if self.Proc_data['bot_info_dict'].platform['model'] in [
            'gocqhttp_show'
        ]:
            self.send_init_event()
        while flag_run:
            releaseDir('./lib')
            if not os.path.exists('./lib/go-cqhttp.exe'):
                self.log(3, 'OlivOS libEXEModel server [' + self.Proc_name + '] can`t found target lib')
                break
            releaseDir('./conf')
            releaseDir('./conf/gocqhttp')
            with open('./conf/gocqhttp/filter.json', 'w+') as tmp:
                tmp.write('{}')
            releaseDir('./conf/gocqhttp/' + self.Proc_data['bot_info_dict'].hash)
            goTypeConfig(self.Proc_data['bot_info_dict'], self.Proc_config['target_proc']).setConfig()
            if False and (self.Proc_data['bot_info_dict'].platform['model'] in [
                'gocqhttp',
                'gocqhttp_hide'
            ]):
                model_Proc = subprocess.Popen(
                    '..\\..\\..\\lib\\go-cqhttp.exe faststart',
                    cwd = '.\\conf\\gocqhttp\\' + self.Proc_data['bot_info_dict'].hash,
                    shell = True,
                    stdin = subprocess.PIPE,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.PIPE
                )
                self.log(2, 'OlivOS libEXEModel server [' + self.Proc_name + '] is running')
                model_Proc.communicate(timeout = None)
                self.log(2, 'OlivOS libEXEModel server [' + self.Proc_name + '] exited')
            elif self.Proc_data['bot_info_dict'].platform['model'] in [
                'gocqhttp',
                'gocqhttp_show'
            ]:
                self.log(2, 'OlivOS libEXEModel server [' + self.Proc_name + '] will run under visiable mode')
                self.clear_gocqhttp()
                self.Proc_data['check_qrcode_flag'] = False
                self.Proc_data['check_stdin'] = False
                time.sleep(2)
                self.Proc_data['check_qrcode_flag'] = True
                self.Proc_data['check_stdin'] = True
                threading.Thread(
                    target = self.check_qrcode,
                    args = ()
                ).start()
                model_Proc = subprocess.Popen(
                    '..\\..\\..\\lib\\go-cqhttp.exe',
                    cwd = '.\\conf\\gocqhttp\\' + self.Proc_data['bot_info_dict'].hash,
                    shell = True,
                    stdin = subprocess.PIPE,
                    stdout = subprocess.PIPE,
                    stderr = subprocess.PIPE,
                    creationflags = subprocess.CREATE_NEW_CONSOLE
                )
                threading.Thread(
                    target = self.check_stdin,
                    args = (model_Proc, )
                ).start()
                self.get_model_stdout(model_Proc)
                #model_Proc.communicate(timeout = None)
                self.log(3, 'OlivOS libEXEModel server [' + self.Proc_name + '] will retry in 10s...')
                time.sleep(8)
            elif self.Proc_data['bot_info_dict'].platform['model'] in [
                'gocqhttp_show_old'
            ]:
                self.log(2, 'OlivOS libEXEModel server [' + self.Proc_name + '] will run under visiable mode')
                subprocess.call(
                    'start cmd /K "title GoCqHttp For OlivOS|..\\..\\..\\lib\\go-cqhttp.exe"',
                    shell = True,
                    cwd = '.\\conf\\gocqhttp\\' + self.Proc_data['bot_info_dict'].hash
                )
                flag_run = False

    def getBotIDStr(self):
        tmp_self_data = self.Proc_data['bot_info_dict'].platform['platform']
        if self.Proc_data['bot_info_dict'].id != None:
            tmp_self_data = '%s|%s' % (
                self.Proc_data['bot_info_dict'].platform['platform'],
                str(self.Proc_data['bot_info_dict'].id)
            )
        return tmp_self_data

    def check_stdin(self, model_Proc:subprocess.Popen):
        while self.Proc_data['check_stdin']:
            if self.Proc_info.rx_queue.empty():
                time.sleep(0.02)
            else:
                try:
                    rx_packet_data = self.Proc_info.rx_queue.get(block = False)
                except:
                    rx_packet_data = None
                if 'data' in rx_packet_data.key and 'action' in rx_packet_data.key['data']:
                        if 'input' == rx_packet_data.key['data']['action']:
                            if 'data' in rx_packet_data.key['data']:
                                input_raw = str(rx_packet_data.key['data']['data'])
                                input_data = ('%s\n' % input_raw).encode('utf-8')
                                model_Proc.stdin.write(input_data)
                                log_data = ('%s' % input_raw)
                                self.send_log_event(log_data)
                                self.log(2, log_data, [
                                    (self.getBotIDStr(), 'default'),
                                    ('gocqhttp', 'default'),
                                    ('onebot_send', 'default')
                                ])

    def get_model_stdout(self, model_Proc:subprocess.Popen):
        for line in iter(model_Proc.stdout.readline, b''):
            try:
                log_data = ('%s' % line.decode('utf-8', errors = 'replace')).rstrip('\n')
                self.send_log_event(log_data)
                self.log(1, log_data, [
                    (self.getBotIDStr(), 'default'),
                    ('gocqhttp', 'default'),
                    ('onebot', 'default')
                ])
            except Exception as e:
                self.log(4, 'OlivOS libEXEModelAPI failed: %s\n%s' % (
                        str(e),
                        traceback.format_exc()
                    )
                )

    def send_init_event(self):
        self.sendControlEventSend('send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'gocqhttp',
                    'event': 'init',
                    'hash': self.Proc_data['bot_info_dict'].hash
                }
            }
        )

    def clear_gocqhttp(self):
        file_path = './conf/gocqhttp/' + self.Proc_data['bot_info_dict'].hash + '/qrcode.png'
        if os.path.exists(file_path):
            os.remove(file_path)

    def check_qrcode(self):
        count = 2 * 60
        file_path = './conf/gocqhttp/' + self.Proc_data['bot_info_dict'].hash + '/qrcode.png'
        while count > 0 and self.Proc_data['check_qrcode_flag']:
            if os.path.exists(file_path):
                self.send_QRCode_event(file_path)
                count = 0
            count -= 1
            time.sleep(1)
        self.Proc_data['check_qrcode_flag'] = False

    def send_QRCode_event(self, path:str):
        self.sendControlEventSend('send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'gocqhttp',
                    'event': 'qrcode',
                    'hash': self.Proc_data['bot_info_dict'].hash,
                    'path': path
                }
            }
        )

    def send_log_event(self, data):
        self.sendControlEventSend('send', {
                'target': {
                    'type': 'nativeWinUI'
                },
                'data': {
                    'action': 'gocqhttp',
                    'event': 'log',
                    'hash': self.Proc_data['bot_info_dict'].hash,
                    'data': data
                }
            }
        )

    def sendControlEventSend(self, action, data):
        if self.Proc_info.control_queue != None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block = False
            )

class goTypeConfig(object):
    def __init__(self, bot_info_dict, target_proc):
        self.bot_info_dict = bot_info_dict
        self.target_proc = target_proc
        self.config_file_str = ''
        self.config_file_format = {}

    def setConfig(self):
        self.config_file_str = (
            "account:\n"
            "  uin: {uin}\n"
            "  password: '{password}'\n"
            "  encrypt: false\n"
            "  status: 0\n"
            "  relogin:\n"
            "    disabled: false\n"
            "    delay: 3\n"
            "    interval: 0\n"
            "    max-times: 0\n"
            "  use-sso-address: true\n"
            "\n"
            "heartbeat:\n"
            "  disabled: false\n"
            "  interval: 5\n"
            "\n"
            "message:\n"
            "  post-format: string\n"
            "  ignore-invalid-cqcode: false\n"
            "  force-fragment: false\n"
            "  fix-url: false\n"
            "  proxy-rewrite: ''\n"
            "  report-self-message: false\n"
            "  remove-reply-at: false\n"
            "  extra-reply-data: false\n"
            "\n"
            "output:\n"
            "  log-level: info\n"
            "  debug: false\n"
            "\n"
            "default-middlewares: &default\n"
            "  access-token: '{access-token}'\n"
            "  filter: '../filter.json'\n"
            "  rate-limit:\n"
            "    enabled: false\n"
            "    frequency: 1\n"
            "    bucket: 1\n"
            "\n"
            "servers:\n"
            "  - http:\n"
            "      disabled: false\n"
            "      host: {servers-host}\n"
            "      port: {servers-port}\n"
            "      timeout: 60\n"
            "      middlewares:\n"
            "        <<: *default\n"
            "      post:\n"
            "       - url: '{servers-post-url}'\n"
            "\n"
            "database:\n"
            "  leveldb:\n"
            "    enable: true\n"
        )

        self.config_file_format['uin'] = str(self.bot_info_dict.id)
        self.config_file_format['password'] = self.bot_info_dict.password
        self.config_file_format['access-token'] = self.bot_info_dict.post_info.access_token
        tmp_host = self.bot_info_dict.post_info.host
        for prefix in [
            'http://',
            'https://',
            'ws://',
            'wss://'
        ]:
            if len(tmp_host) > len(prefix):
                if tmp_host[:len(prefix)] == prefix:
                    tmp_host = tmp_host[len(prefix):]
                    break
        self.config_file_format['servers-host'] = tmp_host
        self.config_file_format['servers-port'] = str(self.bot_info_dict.post_info.port)
        self.config_file_format['servers-post-url'] = 'http://127.0.0.1:' + str(self.target_proc['server']['port']) + '/OlivOSMsgApi/qq/onebot/gocqhttp'

        self.config_file_str = self.config_file_str.format(**self.config_file_format)

        with open('./conf/gocqhttp/' + self.bot_info_dict.hash + '/config.yml', 'w+', encoding = 'utf-8') as tmp:
            tmp.write(self.config_file_str)

def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
