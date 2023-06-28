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

modelName = 'libEXEModelAPI'

gCheckList = [
    'gocqhttp',
    'gocqhttp_hide',
    'gocqhttp_show',
    'gocqhttp_show_Android_Phone',
    'gocqhttp_show_Android_Watch',
    'gocqhttp_show_iMac',
    'gocqhttp_show_iPad',
    'gocqhttp_show_Android_Pad',
    'gocqhttp_show_old'
]

def startGoCqhttpLibExeModel(
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
                resouce_api='https://api.oliva.icu/olivosver/resource/',
                resouce_name='go-cqhttp',
                filePath='./lib/go-cqhttp.exe',
                filePathUpdate='./lib/go-cqhttp.exe.tmp',
                filePathFORCESKIP='./lib/FORCESKIP'
            )
        for bot_info_key in plugin_bot_info_dict:
            if plugin_bot_info_dict[bot_info_key].platform['model'] in gCheckList:
                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                Proc_dict[tmp_Proc_name] = OlivOS.libEXEModelAPI.server(
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
            Proc_type='gocqhttp_lib_exe_model',
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
            'gocqhttp_show',
            'gocqhttp_show_Android_Phone',
            'gocqhttp_show_Android_Watch',
            'gocqhttp_show_iMac',
            'gocqhttp_show_iPad',
            'gocqhttp_show_Android_Pad'
        ]:
            self.send_init_event()
        while self.flag_run:
            releaseDir('./lib')
            if not os.path.exists('./lib/go-cqhttp.exe'):
                self.log(3, OlivOS.L10NAPI.getTrans(
                    'OlivOS libEXEModel server [{0}] can`t found target lib',
                    [self.Proc_name], modelName
                ))
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
                    cwd='.\\conf\\gocqhttp\\' + self.Proc_data['bot_info_dict'].hash,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS libEXEModel server [{0}] is running',
                    [self.Proc_name], modelName
                ))
                model_Proc.communicate(timeout=None)
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS libEXEModel server [{0}] exited',
                    [self.Proc_name], modelName
                ))
            elif self.Proc_data['bot_info_dict'].platform['model'] in [
                'gocqhttp',
                'gocqhttp_show',
                'gocqhttp_show_Android_Phone',
                'gocqhttp_show_Android_Watch',
                'gocqhttp_show_iMac',
                'gocqhttp_show_iPad',
                'gocqhttp_show_Android_Pad'
            ]:
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS libEXEModel server [{0}] will run under visiable mode',
                    [self.Proc_name], modelName
                ))
                self.clear_gocqhttp()
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
                # 依据 https://github.com/Mrs4s/go-cqhttp/pull/1772 的改动
                tmp_env['FORCE_TTY'] = ''
                model_Proc = subprocess.Popen(
                    '..\\..\\..\\lib\\go-cqhttp.exe',
                    cwd='.\\conf\\gocqhttp\\' + self.Proc_data['bot_info_dict'].hash,
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
                    'OlivOS libEXEModel server [{0}] will retry in 10s...',
                    [self.Proc_name], modelName
                ))
                self.Proc_data['model_Proc'] = None
                time.sleep(8)
            elif self.Proc_data['bot_info_dict'].platform['model'] in [
                'gocqhttp_show_old'
            ]:
                self.log(2, OlivOS.L10NAPI.getTrans(
                    'OlivOS libEXEModel server [{0}] will run under visiable mode',
                    [self.Proc_name], modelName
                ))
                tmp_env = dict(os.environ)
                tmp_env['FORCE_TTY'] = ''
                subprocess.call(
                    'start cmd /K "title GoCqHttp For OlivOS|..\\..\\..\\lib\\go-cqhttp.exe"',
                    shell=True,
                    cwd='.\\conf\\gocqhttp\\' + self.Proc_data['bot_info_dict'].hash,
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
                                ('gocqhttp', 'default'),
                                ('onebot_send', 'default')
                            ])

    def get_model_stdout(self, model_Proc: subprocess.Popen):
        for line in iter(model_Proc.stdout.readline, b''):
            try:
                log_data = ('%s' % line.decode('utf-8', errors='replace')).rstrip('\n')
                self.send_log_event(log_data)
                self.log(1, log_data, [
                    (self.getBotIDStr(), 'default'),
                    ('gocqhttp', 'default'),
                    ('onebot', 'default')
                ])
            except Exception as e:
                self.log(4, OlivOS.L10NAPI.getTrans('OlivOS libEXEModel failed: %s\n%s' % [
                        str(e),
                        traceback.format_exc()
                    ],
                    modelName
                ))

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

    def send_QRCode_event(self, path: str):
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
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(
                OlivOS.API.Control.packet(
                    action,
                    data
                ),
                block=False
            )


class goTypeConfig(object):
    def __init__(self, bot_info_dict, target_proc):
        self.bot_info_dict = bot_info_dict
        self.target_proc = target_proc
        self.config_file_str = ''
        self.config_file_format = {}

    def setConfig(self):
        self.config_file_str = '''
account:
  uin: {uin}
  password: '{password}'
  encrypt: false
  status: 0
  relogin:
    disabled: false
    delay: 3
    interval: 0
    max-times: 0
  use-sso-address: true
  sign-server: '{sign-server}'

heartbeat:
  disabled: false
  interval: 5

message:
  post-format: string
  ignore-invalid-cqcode: false
  force-fragment: false
  fix-url: false
  proxy-rewrite: ''
  report-self-message: true
  remove-reply-at: false
  extra-reply-data: false

output:
  log-level: info
  debug: false

default-middlewares: &default
  access-token: '{access-token}'
  filter: '../filter.json'
  rate-limit:
    enabled: false
    frequency: 1
    bucket: 1

servers:
  - http:
      disabled: false
      host: {servers-host}
      port: {servers-port}
      timeout: 60
      middlewares:
        <<: *default
      post:
       - url: '{servers-post-url}'

database:
  leveldb:
    enable: true
'''

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
        self.config_file_format['servers-post-url'] = 'http://127.0.0.1:' + str(
            self.target_proc['server']['port']) + '/OlivOSMsgApi/qq/onebot/gocqhttp'
        self.config_file_format['sign-server'] = '-'
        if 'sign-server' in self.bot_info_dict.extends \
        and '' != self.bot_info_dict.extends['sign-server']:
            self.config_file_format['sign-server'] = str(self.bot_info_dict.extends['sign-server'])

        self.config_file_str = self.config_file_str.format(**self.config_file_format)

        with open('./conf/gocqhttp/' + self.bot_info_dict.hash + '/config.yml', 'w+', encoding='utf-8') as tmp:
            tmp.write(self.config_file_str)

def accountFix(bot_info_dict, logger_proc):
    releaseDir('./conf')
    releaseDir('./conf/gocqhttp')
    for bot_info_dict_this in bot_info_dict:
        bot_hash = bot_info_dict_this
        if bot_info_dict[bot_hash].platform['sdk'] == 'onebot' \
        and bot_info_dict[bot_hash].platform['platform'] == 'qq' \
        and bot_info_dict[bot_hash].platform['model'] in [
            'gocqhttp_show_Android_Phone',
            'gocqhttp_show_Android_Watch',
            'gocqhttp_show_iMac',
            'gocqhttp_show_iPad',
            'gocqhttp_show_Android_Pad'
        ]:
            releaseDir('./conf/gocqhttp/' + bot_hash)
            file_path = './conf/gocqhttp/' + bot_hash + '/device.json'
            device_info = {}

            # 读取文件
            try:
                with open(file_path, 'r', encoding = 'utf-8') as f:
                    device_info = json.loads(f.read())
            except:
                device_info = {}

            # 协议修改
            if bot_info_dict[bot_hash].platform['model'] == 'gocqhttp_show_Android_Phone':
                device_info['protocol'] = 1
            elif bot_info_dict[bot_hash].platform['model'] == 'gocqhttp_show_Android_Watch':
                device_info['protocol'] = 2
            elif bot_info_dict[bot_hash].platform['model'] == 'gocqhttp_show_iMac':
                device_info['protocol'] = 3
            elif bot_info_dict[bot_hash].platform['model'] == 'gocqhttp_show_QiDian':
                device_info['protocol'] = 4
            elif bot_info_dict[bot_hash].platform['model'] == 'gocqhttp_show_iPad':
                device_info['protocol'] = 5
            elif bot_info_dict[bot_hash].platform['model'] == 'gocqhttp_show_Android_Pad':
                device_info['protocol'] = 6

            # 补全虚拟设备信息
            device_info = deviceInfoFix(device_info)

            # 刷写回文件
            try:
                with open(file_path, 'w', encoding = 'utf-8') as f:
                    f.write(json.dumps(device_info, ensure_ascii = False))
            except:
                pass

def deviceInfoFix(deviceInfo:dict):
    deviceRes = copy.deepcopy(deviceInfo)
    deviceResPatch = {}
    flagRelease = False

    deviceRes.setdefault('protocol', 0)

    if len(list(deviceInfo.keys())) == 1:
        flagRelease = True

    if flagRelease:
        deviceResPatch.update({
            'display': 'MIRAI.123456.001',
            'product': 'mirai',
            'device': 'mirai',
            'board': 'mirai',
            'model': 'mirai',
            'boot_id': 'cb886ae2-00b6-4d68-a230-787f111d12c7',
            'proc_version': 'Linux version 3.0.31-cb886ae2 (android-build@xxx.xxx.xxx.xxx.com)',
            'imei': '468356291846738',
            'brand': 'mamoe',
            'bootloader': 'unknown',
            'base_band': '',
            'version': {
                'incremental': '5891938',
                'release': '10',
                'codename': 'REL',
                'sdk': 29
            },
            'sim_info': 'T-Mobile',
            'os_type': 'android',
            'mac_address': '00:50:56:C0:00:08',
            'ip_address': [10, 0, 1, 3],
            'wifi_bssid': '00:50:56:C0:00:08',
            'wifi_ssid': '<unknown ssid>',
            'android_id': 'MIRAI.123456.001',
            'apn': 'wifi',
            'vendor_name': 'MIUI',
            'vendor_os_name': 'mirai'
        })
        deviceResPatch['android_id'] = 'MIRAI.%s.001' % getRandomStringOfInt(6)
        deviceResPatch['finger_print'] = 'mamoe/mirai/mirai:10/MIRAI.200122.001/%s:user/release-keys' % getRandomStringOfInt(7)
        deviceResPatch['boot_id'] = str(uuid.uuid4())
        deviceResPatch['proc_version'] = 'Linux version 3.0.31-%s (android-build@xxx.xxx.xxx.xxx.com)' % getRandomString(8)
        deviceResPatch['imei'] = GenIMEI('XXXXXXXXXXXXXXX')
        deviceResPatch['imsi_md5'] = getMD5([deviceResPatch['imei']])
        deviceResPatch['display'] = deviceResPatch['android_id']
        deviceResPatch['android_id'] = getHEX(getRandomString(8))

        deviceRes.update(deviceResPatch)

    return deviceRes

def GenIMEI(src:str):
    sum = 0
    final = ''
    for i in range(14):
        toAdd = 0
        if i < len(src) and src[i] in '0123456789':
            toAdd = int(src[i])
        else:
            toAdd = random.randint(0, 9)
        final += str(toAdd) # 先行进行数值拼接
        if (i + 1) % 2 == 0: # 针对偶数位进行处理
            toAdd *= 2
            if toAdd >= 10:
                toAdd = (toAdd % 10) + 1 # luna algorithm 中间部分
        sum += toAdd
    ctrlDigit = (sum * 9) % 10 # luna algorithm 求和部分
    final += str(ctrlDigit)
    return final

def getMD5(src:list):
    hashObj = hashlib.new('md5')
    for srcThis in src:
        hashObj.update(str(srcThis).encode(encoding='UTF-8'))
    return hashObj.hexdigest()

def getHEX(src:str):
    return ''.join([hex(int(i)).lstrip('0x') for i in src.encode('utf-8')])

def getRandomString(length:int):
    return getRandomStringRange(length, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890')

def getRandomStringOfInt(length:int):
    return getRandomStringRange(length, '0123456789')

def getRandomStringRange(length:int, string:str):
    s = ''
    for i in range(length):
        s += random.choice(string)
    return s

def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
