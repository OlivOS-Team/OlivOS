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


def startGoCqhttpLibExeModel(
    plugin_bot_info_dict,
    basic_conf_models_this,
    multiprocessing_dict,
    Proc_dict,
    Proc_Proc_dict,
    basic_conf_models,
    tmp_proc_mode
):
    checkGoCqHttpExeLib(Proc_dict[basic_conf_models_this['logger_proc']])
    if platform.system() == 'Windows':
        for bot_info_key in plugin_bot_info_dict:
            if plugin_bot_info_dict[bot_info_key].platform['model'] in [
                'gocqhttp',
                'gocqhttp_hide',
                'gocqhttp_show',
                'gocqhttp_show_Android_Phone',
                'gocqhttp_show_Android_Watch',
                'gocqhttp_show_iMac',
                'gocqhttp_show_iPad',
                'gocqhttp_show_Android_Pad',
                'gocqhttp_show_old'
            ]:
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

def checkGoCqHttpExeLib(logger_proc:OlivOS.diagnoseAPI.logger):
    logger = loggerGen(logger_proc)
    filePath = './lib/go-cqhttp.exe'
    filePathUpdate = './lib/go-cqhttp.exe.tmp'
    filePathFORCESKIP = './lib/FORCESKIP'
    sleepTime = 2
    architecture_num = platform.architecture()[0]

    logger(2, 'will check go-cqhttp lib after %ds ...' % (sleepTime))
    time.sleep(sleepTime)

    for i in range(1):
        fMD5 = None
        fMD5Update = None
        flagFORCESKIP = False
        flagAlreadyLatest = False
        releaseDir('./lib')
        fMD5 = checkFileMD5(filePath)
        logger(2, 'check go-cqhttp lib [%s] md5: [%s]' % (
                filePath,
                str(fMD5)
            )
        )

        flagFORCESKIP = os.path.exists(filePathFORCESKIP)

        if not flagFORCESKIP:
            apiJsonData = OlivOS.updateAPI.GETHttpJson2Dict('https://api.oliva.icu/olivosver/gocqhttp/')
            fMD5UpdateTarget = None
            fMD5UpdateUrl = None
            try:
                fMD5UpdateTarget = apiJsonData['version']['go-cqhttp'][architecture_num]['md5']
                fMD5UpdateUrl = apiJsonData['version']['go-cqhttp'][architecture_num]['path']
            except:
                fMD5UpdateTarget = None
            if apiJsonData != None \
            and fMD5UpdateTarget != None \
            and fMD5UpdateUrl != None:
                logger(2, 'check go-cqhttp lib patch target md5: [%s]' % (str(fMD5UpdateTarget)))
                if fMD5UpdateTarget != fMD5:
                    logger(2, 'download new go-cqhttp lib ...')
                    if OlivOS.updateAPI.GETHttpFile(fMD5UpdateUrl, filePathUpdate):
                        logger(2, 'download new go-cqhttp lib done')
                        fMD5Update = checkFileMD5(filePathUpdate)
                        logger(2, 'check go-cqhttp lib patch [%s] md5: [%s]' % (filePathUpdate, str(fMD5Update)))
                    else:
                        fMD5Update = None
                        logger(4, 'download new go-cqhttp lib FAILED! md5 check FAILED!')
                else:
                    flagAlreadyLatest = True
            else:
                logger(4, 'check go-cqhttp lib patch api FAILED! try later please!')
                fMD5Update = None

            if flagAlreadyLatest:
                logger(2, 'go-cqhttp lib already latest!')
            elif fMD5UpdateTarget != None and fMD5Update != fMD5UpdateTarget:
                logger(4, 'download go-cqhttp lib patch FAILED! try later please!')
            elif fMD5Update != None and fMD5 != fMD5Update:
                logger(3, 'update go-cqhttp lib patch [%s] -> [%s]' % (filePathUpdate, filePath))
                shutil.copyfile(src = filePathUpdate, dst = filePath)
                os.remove(filePathUpdate)
                logger(2, 'update go-cqhttp lib patch done!')
            else:
                logger(2, 'go-cqhttp lib already latest!')
        else:
            logger(3, 'go-cqhttp lib update FORCESKIP!')

        break

def checkFileMD5(filePath):
    res = None
    if os.path.exists(filePath):
        with open(filePath, 'rb') as fp:
            fObj = fp.read()
            res = hashlib.md5(fObj).hexdigest()
    return res

def loggerGen(logger_proc:'OlivOS.diagnoseAPI.logger|None'):
    def logF(log_level, log_message, log_segment=None):
        if type(logger_proc) is OlivOS.diagnoseAPI.logger:
            logger_proc.log(
                log_level=log_level,
                log_message=log_message,
                log_segment=log_segment
            )
    return logF

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval=0.001, dead_interval=1, rx_queue=None, tx_queue=None,
                 control_queue=None, logger_proc=None, target_proc=None, debug_mode=False, bot_info_dict=None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='lib_exe_model',
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

    def run(self):
        flag_run = True
        if self.Proc_data['bot_info_dict'].platform['model'] in [
            'gocqhttp_show',
            'gocqhttp_show_Android_Phone',
            'gocqhttp_show_Android_Watch',
            'gocqhttp_show_iMac',
            'gocqhttp_show_iPad',
            'gocqhttp_show_Android_Pad'
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
                    cwd='.\\conf\\gocqhttp\\' + self.Proc_data['bot_info_dict'].hash,
                    shell=True,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                self.log(2, 'OlivOS libEXEModel server [' + self.Proc_name + '] is running')
                model_Proc.communicate(timeout=None)
                self.log(2, 'OlivOS libEXEModel server [' + self.Proc_name + '] exited')
            elif self.Proc_data['bot_info_dict'].platform['model'] in [
                'gocqhttp',
                'gocqhttp_show',
                'gocqhttp_show_Android_Phone',
                'gocqhttp_show_Android_Watch',
                'gocqhttp_show_iMac',
                'gocqhttp_show_iPad',
                'gocqhttp_show_Android_Pad'
            ]:
                self.log(2, 'OlivOS libEXEModel server [' + self.Proc_name + '] will run under visiable mode')
                self.clear_gocqhttp()
                self.Proc_data['check_qrcode_flag'] = False
                self.Proc_data['check_stdin'] = False
                time.sleep(2)
                self.Proc_data['check_qrcode_flag'] = True
                self.Proc_data['check_stdin'] = True
                threading.Thread(
                    target=self.check_qrcode,
                    args=()
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
                threading.Thread(
                    target=self.check_stdin,
                    args=(model_Proc,)
                ).start()
                self.get_model_stdout(model_Proc)
                # model_Proc.communicate(timeout = None)
                self.log(3, 'OlivOS libEXEModel server [' + self.Proc_name + '] will retry in 10s...')
                time.sleep(8)
            elif self.Proc_data['bot_info_dict'].platform['model'] in [
                'gocqhttp_show_old'
            ]:
                self.log(2, 'OlivOS libEXEModel server [' + self.Proc_name + '] will run under visiable mode')
                tmp_env = dict(os.environ)
                tmp_env['FORCE_TTY'] = ''
                subprocess.call(
                    'start cmd /K "title GoCqHttp For OlivOS|..\\..\\..\\lib\\go-cqhttp.exe"',
                    shell=True,
                    cwd='.\\conf\\gocqhttp\\' + self.Proc_data['bot_info_dict'].hash,
                    env=tmp_env
                )
                flag_run = False

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
            "  report-self-message: true\n"
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
        self.config_file_format['servers-post-url'] = 'http://127.0.0.1:' + str(
            self.target_proc['server']['port']) + '/OlivOSMsgApi/qq/onebot/gocqhttp'

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
        deviceResPatch['imei'] = GenIMEI()
        deviceResPatch['imsi_md5'] = getMD5([deviceResPatch['imei']])
        deviceResPatch['display'] = deviceResPatch['android_id']
        deviceResPatch['android_id'] = getHEX(getRandomString(8))

        deviceRes.update(deviceResPatch)

    return deviceRes

def GenIMEI():
    sum = 0 # the control sum of digits
    final = ''
    for i in range(14): # generating all the base digits
        toAdd = random.randint(0, 9)
        if (i + 1) % 2 == 0: # special proc for every 2nd one
            toAdd *= 2
            if toAdd >= 10:
                toAdd = (toAdd % 10) + 1
        sum += toAdd
        final += str(toAdd) # and even printing them here!
    ctrlDigit = (sum * 9) % 10 # calculating the control digit
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
