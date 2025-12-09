# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/libNapCatEXEModelAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
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
import zipfile

import OlivOS

modelName = 'libNapCatEXEModelAPI'

resourceUrlPath = OlivOS.infoAPI.resourceUrlPath

gCheckList = [
    'napcat',
    'napcat_hide',
    'napcat_show',
    'napcat_show_new',
    'napcat_show_old'
]

gCheck9912List = [
    'napcat_show_new_9_9_12'
]

gCheck9919List = [
    'napcat_show_new_9_9_19'
]

gCheck9922List = [
    'napcat_show_new_9_9_22',
    'napcat_show_new'
]

def startNapCatLibExeModel(
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
        flag9911Active = False
        flag9912Active = False
        flag9919Active = False
        flag9922Active = False
        for bot_info_key in plugin_bot_info_dict:
            if plugin_bot_info_dict[bot_info_key].platform['model'] in gCheckList:
                flagActive = True
            if plugin_bot_info_dict[bot_info_key].platform['model'] in gCheck9912List:
                flag9912Active = True
            elif plugin_bot_info_dict[bot_info_key].platform['model'] in gCheck9919List:
                flag9919Active = True
            elif plugin_bot_info_dict[bot_info_key].platform['model'] in gCheck9922List:
                flag9922Active = True
            else:
                flag9911Active = True
        if flagActive:
            releaseDir('./lib')
            if flag9911Active:
                OlivOS.updateAPI.checkResouceFile(
                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                    resouce_api=resourceUrlPath,
                    resouce_name='NapCat-QQ-Win-9.9.11-24568',
                    filePath='./lib/NapCat.zip',
                    filePathUpdate='./lib/NapCat.zip.tmp',
                    filePathFORCESKIP='./lib/FORCESKIP'
                )
            if flag9912Active:
                OlivOS.updateAPI.checkResouceFile(
                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                    resouce_api=resourceUrlPath,
                    resouce_name='NapCat-QQ-Win-9.9.12-26000',
                    filePath='./lib/NapCatNew.zip',
                    filePathUpdate='./lib/NapCatNew.zip.tmp',
                    filePathFORCESKIP='./lib/FORCESKIP'
                )
            if flag9919Active:
                OlivOS.updateAPI.checkResouceFile(
                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                    resouce_api=resourceUrlPath,
                    resouce_name='NapCat-QQ-Win-9.9.19-34740',
                    filePath='./lib/NapCat-QQ-Win-9.9.19-34740.zip',
                    filePathUpdate='./lib/NapCat-QQ-Win-9.9.19-34740.zip.tmp',
                    filePathFORCESKIP='./lib/FORCESKIP'
                )
            if flag9922Active:
                OlivOS.updateAPI.checkResouceFile(
                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                    resouce_api=resourceUrlPath,
                    resouce_name='NapCat-QQ-Win-9.9.22-40990',
                    filePath='./lib/NapCat-QQ-Win-9.9.22-40990.zip',
                    filePathUpdate='./lib/NapCat-QQ-Win-9.9.22-40990.zip.tmp',
                    filePathFORCESKIP='./lib/FORCESKIP'
                )
        for bot_info_key in plugin_bot_info_dict:
            if plugin_bot_info_dict[bot_info_key].platform['model'] in gCheckList:
                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                Proc_dict[tmp_Proc_name] = OlivOS.libNapCatEXEModelAPI.server(
                    Proc_name=tmp_Proc_name,
                    scan_interval=basic_conf_models_this['interval'],
                    dead_interval=basic_conf_models_this['dead_interval'],
                    rx_queue=multiprocessing_dict[tmp_queue_name],
                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                    control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']],
                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                    target_proc=basic_conf_models[basic_conf_models_this['target_proc']],
                    debug_mode=False
                )
                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(tmp_proc_mode)

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval=0.001, dead_interval=1, rx_queue=None, tx_queue=None,
                 control_queue=None, logger_proc=None, target_proc=None, debug_mode=False, bot_info_dict=None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='napcat_lib_exe_model',
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
            'napcat',
            'napcat_show',
            'napcat_show_new'
        ]:
            self.send_init_event()
        while self.flag_run:
            releaseDir('./lib')
            if not os.path.exists('./lib/NapCat.zip'):
                self.log(3, OlivOS.L10NAPI.getTrans(
                    'OlivOS libNapCatEXEModel server [{0}] can`t found target lib',
                    [self.Proc_name], modelName
                ))
                break
            releaseDir('./conf')
            releaseDir('./conf/napcat')
            releaseDir(f"./conf/napcat/{self.Proc_data['bot_info_dict'].hash}")
            releaseDir(f"./conf/napcat/{self.Proc_data['bot_info_dict'].hash}/config")
            if self.Proc_data['bot_info_dict'].platform['model'] in gCheck9922List:
                unzip('./lib/NapCat-QQ-Win-9.9.22-40990.zip', f"./conf/napcat/{self.Proc_data['bot_info_dict'].hash}")
                napcatTypeConfig(self.Proc_data['bot_info_dict'], self.Proc_config['target_proc'], version='9.9.19').setConfig()
            elif self.Proc_data['bot_info_dict'].platform['model'] in gCheck9919List:
                unzip('./lib/NapCat-QQ-Win-9.9.19-34740.zip', f"./conf/napcat/{self.Proc_data['bot_info_dict'].hash}")
                napcatTypeConfig(self.Proc_data['bot_info_dict'], self.Proc_config['target_proc'], version='9.9.19').setConfig()
            elif self.Proc_data['bot_info_dict'].platform['model'] in gCheck9912List:
                unzip('./lib/NapCatNew.zip', f"./conf/napcat/{self.Proc_data['bot_info_dict'].hash}")
                napcatTypeConfig(self.Proc_data['bot_info_dict'], self.Proc_config['target_proc']).setConfig()
            else:
                unzip('./lib/NapCat.zip', f"./conf/napcat/{self.Proc_data['bot_info_dict'].hash}")
                napcatTypeConfig(self.Proc_data['bot_info_dict'], self.Proc_config['target_proc']).setConfig()
            if self.Proc_data['bot_info_dict'].platform['model'] in [
                'napcat',
                'napcat_show_new_9_9_12',
                'napcat_show_new_9_9_19',
                'napcat_show_new_9_9_22',
                'napcat_show_new',
                'napcat_show'
            ]:
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS libNapCatEXEModel server [{0}] will run under visiable mode',
                    [self.Proc_name], modelName
                ))
                self.clear_napcat()
                self.Proc_data['check_qrcode_flag'] = False
                self.Proc_data['check_stdin'] = False
                time.sleep(2)
                self.Proc_data['check_qrcode_flag'] = True
                self.Proc_data['check_stdin'] = True
                if self.Proc_data['bot_info_dict'].platform['model'] in [
                    'napcat_show_new_9_9_22',
                    'napcat_show_new_9_9_19',
                    'napcat_show_new'
                ]:
                    threading.Thread(
                        target=self.check_qrcode,
                        args=(),
                        kwargs={'version': '9.9.19'},
                        daemon=self.deamon
                    ).start()
                    tmp_env = dict(os.environ)
                    model_Proc = subprocess.Popen(
                        f".\\launcher-win10-user.bat {self.Proc_data['bot_info_dict'].id}",
                        cwd=f".\\conf\\napcat\\{self.Proc_data['bot_info_dict'].hash}",
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
                        'OlivOS libNapCatEXEModel server [{0}] will retry in 10s...',
                        [self.Proc_name], modelName
                    ))
                    self.Proc_data['model_Proc'] = None
                    time.sleep(8)
                elif self.Proc_data['bot_info_dict'].platform['model'] in [
                    'napcat_show_new_9_9_12'
                ]:
                    tmp_env = dict(os.environ)
                    subprocess.call(
                        f"start powershell .\\BootWay05.ps1 -q {self.Proc_data['bot_info_dict'].id}",
                        shell=True,
                        cwd='.\\conf\\napcat\\' + self.Proc_data['bot_info_dict'].hash,
                        env=tmp_env
                    )
                    self.flag_run = False
                else:
                    threading.Thread(
                        target=self.check_qrcode,
                        args=(),
                        daemon=self.deamon
                    ).start()
                    tmp_env = dict(os.environ)
                    model_Proc = subprocess.Popen(
                        f".\\napcat-utf8.bat -q {self.Proc_data['bot_info_dict'].id}",
                        cwd=f".\\conf\\napcat\\{self.Proc_data['bot_info_dict'].hash}",
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
                        'OlivOS libNapCatEXEModel server [{0}] will retry in 10s...',
                        [self.Proc_name], modelName
                    ))
                    self.Proc_data['model_Proc'] = None
                    time.sleep(8)
            elif self.Proc_data['bot_info_dict'].platform['model'] in [
                'napcat_show_old'
            ]:
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS libNapCatEXEModel server [{0}] will run under visiable mode',
                    [self.Proc_name], modelName
                ))
                tmp_env = dict(os.environ)
                subprocess.call(
                    'start cmd /K "title NapCat For OlivOS| .\\napcat-utf8.bat -q ' + str(self.Proc_data['bot_info_dict'].id) + '"',
                    shell=True,
                    cwd='.\\conf\\napcat\\' + self.Proc_data['bot_info_dict'].hash,
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
                                ('napcat', 'default'),
                                ('onebot_send', 'default')
                            ])

    def get_model_stdout(self, model_Proc: subprocess.Popen):
        for line in iter(model_Proc.stdout.readline, b''):
            try:
                log_data = ('%s' % line.decode('utf-8', errors='replace')).rstrip('\n')
                self.send_log_event(log_data)
                self.log(1, log_data, [
                    (self.getBotIDStr(), 'default'),
                    ('napcat', 'default'),
                    ('onebot', 'default')
                ])
            except Exception as e:
                self.log(4, OlivOS.L10NAPI.getTrans('OlivOS libNapCatEXEModel failed: %s\n%s' % [
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
                    'action': 'napcat',
                    'event': 'init',
                    'hash': self.Proc_data['bot_info_dict'].hash
                }
            }
        )

    def clear_napcat(self):
        file_path = f"./conf/napcat/{self.Proc_data['bot_info_dict'].hash}/qrcode.png"
        if os.path.exists(file_path):
            os.remove(file_path)

    def check_qrcode(self, version='9.9.11'):
        count = 2 * 60
        file_path = f"./conf/napcat/{self.Proc_data['bot_info_dict'].hash}/qrcode.png"
        if version == '9.9.19':
            file_path = f"./conf/napcat/{self.Proc_data['bot_info_dict'].hash}/cache/qrcode.png"
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
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
                    'action': 'napcat',
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
                    'action': 'napcat',
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


class napcatTypeConfig(object):
    def __init__(self, bot_info_dict:OlivOS.API.bot_info_T, target_proc, version='9.9.11'):
        self.bot_info_dict = bot_info_dict
        self.target_proc = target_proc
        self.config_file_str = ''
        self.config_file_data = ''
        self.config_file_format = {}
        self.config_file_version = version

    def setConfig(self):
        if self.config_file_version == '9.9.19':
            self.config_file_format['uin'] = str(self.bot_info_dict.id)
            self.config_file_format['token'] = self.bot_info_dict.post_info.access_token
            self.config_file_format['port'] = str(self.bot_info_dict.post_info.port)
            self.config_file_format['url'] = f"http://127.0.0.1:{self.target_proc['server']['port']}/OlivOSMsgApi/qq/onebot/default"

            self.config_file_data = {
                "network": {
                    "httpServers": [
                        {
                            "name": f"httpServer-{self.config_file_format['uin']}",
                            "enable": True,
                            "port": self.config_file_format['port'],
                            "host": "127.0.0.1",
                            "enableCors": True,
                            "enableWebsocket": True,
                            "messagePostFormat": "array",
                            "token": self.config_file_format['token'],
                            "debug": False,
                        }
                    ],
                    "httpClients": [
                        {
                            "name": f"httpClient-{self.config_file_format['uin']}",
                            "enable": True,
                            "url": self.config_file_format['url'],
                            "messagePostFormat": "array",
                            "reportSelfMessage": False,
                            "token": self.config_file_format['token'],
                            "debug": False,
                        }
                    ],
                    "websocketServers": [],
                    "websocketClients": []
                },
                "musicSignUrl": "",
                "enableLocalFile2Url": False,
                "parseMultMsg": False
            }

            self.config_file_str = json.dumps(self.config_file_data, ensure_ascii = False, indent = 4)

            with open(f'./conf/napcat/{self.bot_info_dict.hash}/config/onebot11_{self.bot_info_dict.id}.json', 'w+', encoding='utf-8') as tmp:
                tmp.write(self.config_file_str)
        else:
            self.config_file_format['uin'] = str(self.bot_info_dict.id)
            self.config_file_format['token'] = self.bot_info_dict.post_info.access_token
            self.config_file_format['port'] = str(self.bot_info_dict.post_info.port)
            self.config_file_format['postUrls'] = f"http://127.0.0.1:{self.target_proc['server']['port']}/OlivOSMsgApi/qq/onebot/default"

            self.config_file_data = {
                "http": {
                    "enable": True,
                    "host": "",
                    "port": self.config_file_format['port'],
                    "secret": self.config_file_format['token'],
                    "enableHeart": False,
                    "enablePost": True,
                    "postUrls": [
                        self.config_file_format['postUrls']
                    ]
                },
                "ws": {
                    "enable": False,
                    "host": "",
                    "port": 3001
                },
                "reverseWs": {
                    "enable": False,
                    "urls": []
                },
                "debug": False,
                "heartInterval": 30000,
                "messagePostFormat": "array",
                "enableLocalFile2Url": True,
                "musicSignUrl": "",
                "reportSelfMessage": False,
                "token": ""
            }

            self.config_file_str = json.dumps(self.config_file_data, ensure_ascii = False, indent = 4)

            with open(f'./conf/napcat/{self.bot_info_dict.hash}/config/onebot11_{self.bot_info_dict.id}.json', 'w+', encoding='utf-8') as tmp:
                tmp.write(self.config_file_str)

def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def support_gbk(zip_file: zipfile.ZipFile):
    name_to_info = zip_file.NameToInfo
    # copy map first
    for name, info in name_to_info.copy().items():
        try:
            real_name = name.encode('cp437').decode('gbk')
        except:
            real_name = name
        if real_name != name:
            info.filename = real_name
            del name_to_info[name]
            name_to_info[real_name] = info
    return zip_file

def unzip(zip_file_path, target_dir):
    with support_gbk(zipfile.ZipFile(zip_file_path, 'r', zipfile.ZIP_DEFLATED)) as zip_file:
        zip_file = support_gbk(zip_file)
        zip_file.extractall(target_dir)
