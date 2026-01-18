# -*- encoding: utf-8 -*-
r"""
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/libAstralQsignEXEModelAPI.py
@Author    :   MetaLeo元理
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
"""

import subprocess
import time
import os
import traceback
import platform
import zipfile
import hashlib
import re

import OlivOS

modelName = 'libAstralQsignEXEModelAPI'

resourceUrlPath = OlivOS.infoAPI.resourceUrlPath

gCheckList = ['gocqhttp_show_Android_Phone', 'gocqhttp_show_Android_Pad']


def startAstralQsignLibExeModel(
    plugin_bot_info_dict,
    basic_conf_models_this,
    multiprocessing_dict,
    Proc_dict,
    Proc_Proc_dict,
    basic_conf_models,
    tmp_proc_mode,
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
                resouce_name='astral-qsign-20250316001',
                filePath='./lib/astral-qsign.zip',
                filePathUpdate='./lib/astral-qsign.zip.tmp',
                filePathFORCESKIP='./lib/FORCESKIP',
            )
            tmp_Proc_name = basic_conf_models_this['name']
            Proc_dict[tmp_Proc_name] = OlivOS.libAstralQsignEXEModelAPI.server(
                Proc_name=tmp_Proc_name,
                tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']],
                logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                server_data=basic_conf_models_this['server'],
                bot_info_dict=plugin_bot_info_dict,
                debug_mode=False,
            )
            Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(tmp_proc_mode)


class server(OlivOS.API.Proc_templet):
    def __init__(
        self,
        Proc_name,
        scan_interval=0.001,
        dead_interval=1,
        rx_queue=None,
        tx_queue=None,
        control_queue=None,
        logger_proc=None,
        server_data=None,
        bot_info_dict=None,
        debug_mode=False,
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='astralqsign_lib_exe_model',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            control_queue=control_queue,
            logger_proc=logger_proc,
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = {}
        if type(bot_info_dict) is dict:
            self.Proc_data['bot_info_dict'] = bot_info_dict
        self.server_data = server_data
        self.flag_run = True

    def run(self):
        while self.flag_run:
            self.sendLogSim(
                2, 'OlivOS libAstralQsignEXEModel server [{0}] will run under visiable mode', [self.Proc_name]
            )
            time.sleep(2)
            releaseDir('./conf')
            releaseDir('./conf/astral-qsign')
            unzip('./lib/astral-qsign.zip', './conf/astral-qsign')
            time.sleep(1)
            tmp_env = dict(os.environ)
            tmp_env['FORCE_TTY'] = ''
            model_Proc = subprocess.Popen(
                (
                    f'.\\uninstall.bat'
                    f' "localhost" "{self.server_data["port"]}"'
                    f' "{getOTPPASSWORD()}" "{self.server_data["token"]}"'
                ),
                cwd='.\\conf\\astral-qsign',
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                env=tmp_env,
            )
            self.sendLog(
                2,
                'OlivOS libAstralQsignEXEModel server [{0}] is running',
                [self.Proc_name, str(self.server_data['port'])],
            )
            self.Proc_data['model_Proc'] = model_Proc
            self.setGoCqhttpModelEnableSendAll()
            self.get_model_stdout(model_Proc)
            # model_Proc.communicate(timeout = None)
            self.sendLogSim(3, 'OlivOS libAstralQsignEXEModel server [{0}] will retry in 10s...', [self.Proc_name])
            self.Proc_data['model_Proc'] = None
            time.sleep(8)

    def get_model_stdout(self, model_Proc: subprocess.Popen):
        for line in iter(model_Proc.stdout.readline, b''):
            try:
                log_data = ('%s' % line.decode('utf-8', errors='replace')).rstrip('\n').rstrip('\r')
                log_data = re.sub(r'\033\[[\d;]*m?', '', log_data)
                self.log(2, log_data, [('AstralQsign', 'default')])
            except Exception as e:
                self.log(
                    4,
                    OlivOS.L10NAPI.getTrans(
                        'OlivOS libAstralQsignEXEModel failed: %s\n%s' % [str(e), traceback.format_exc()], modelName
                    ),
                )

    def send_log_event(self, data):
        self.sendControlEventSend(
            'send',
            {
                'target': {'type': 'nativeWinUI'},
                'data': {
                    'action': 'AstralQsign',
                    'event': 'log',
                    'hash': self.Proc_data['bot_info_dict'].hash,
                    'data': data,
                },
            },
        )

    def setGoCqhttpModelEnableSend(self, hash):
        self.sendControlEventSend(
            'send', {'target': {'type': 'gocqhttp_lib_exe_model', 'hash': hash}, 'data': {'action': 'skipDelay'}}
        )

    def sendControlEventSend(self, action, data):
        if self.Proc_info.control_queue is not None:
            self.Proc_info.control_queue.put(OlivOS.API.Control.packet(action, data), block=False)

    def setGoCqhttpModelEnableSendAll(self):
        for bot_info_key in self.Proc_data['bot_info_dict']:
            if self.Proc_data['bot_info_dict'][bot_info_key].platform['model'] in gCheckList:
                self.setGoCqhttpModelEnableSend(self.Proc_data['bot_info_dict'][bot_info_key].hash)

    def sendLog(self, log_level: int, log_message: str, log_message_list: list):
        self.log(
            log_level, OlivOS.L10NAPI.getTrans(log_message, log_message_list, modelName), [('AstralQsign', 'default')]
        )

    def sendLogSim(self, log_level: int, log_message: str, log_message_list: list):
        self.log(log_level, OlivOS.L10NAPI.getTrans(log_message, log_message_list, modelName), [])


def isBotActive(plugin_bot_info_dict: dict):
    flag_need_enable = False
    for bot_info_key in plugin_bot_info_dict:
        if (
            plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'onebot'
            and plugin_bot_info_dict[bot_info_key].platform['platform'] == 'qq'
            and plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.libAstralQsignEXEModelAPI.gCheckList
            and plugin_bot_info_dict[bot_info_key].extends.get('qsign-server-protocal', None) == 'AstralQsign'
        ):
            flag_need_enable = True
    return flag_need_enable


def getOTPPASSWORD():
    ts = str(int(time.time()))
    res = f'{ts}OTP_AstralQSign_Private_Package_OlivOS'
    hash_tmp = hashlib.new('md5')
    hash_tmp.update(str(res).encode(encoding='UTF-8'))
    res = f'{ts}{hash_tmp.hexdigest()}'
    return res


def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def support_gbk(zip_file: zipfile.ZipFile):
    name_to_info = zip_file.NameToInfo
    # copy map first
    for name, info in name_to_info.copy().items():
        try:
            real_name = name.encode('cp437').decode('gbk')
        except Exception:
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
