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

resourceUrlPath = OlivOS.infoAPI.resourceUrlPath

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

gProtocalInfo = {
    'android_pad': {
        '8.9.58': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537161402,
    "sub_app_id": 537161402,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.58.11170",
    "build_time": 1684467300,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2545",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1686334718,
    "qua": "V1_AND_SQ_8.9.58_4106_YYB_D",
    "protocol_type": 6
}''',
        '8.9.63': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537164888,
    "sub_app_id": 537164888,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.63.11390",
    "build_time": 1685069178,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2546",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1687796862,
    "qua": "V1_AND_SQ_8.9.63_4194_YYB_D",
    "protocol_type": 6
}''',
        '8.9.68': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537168361,
    "sub_app_id": 537168361,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.68.11565",
    "build_time": 1688523354,
    "apk_sign": "7772804f3cb4961f57cb764fbe4973e6",
    "sdk_version": "6.0.0.2549",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1689780543,
    "qua": "V1_AND_SQ_8.9.68_4264_YYB_D",
    "protocol_type": 6
}''',
        '8.9.70': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537169976,
    "sub_app_id": 537169976,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.70.11730",
    "build_time": 1689956914,
    "apk_sign": "e686fa90d9a33950c46de9cfb4ec7e71",
    "sdk_version": "6.0.0.2551",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1690350020,
    "qua": "V1_AND_SQ_8.9.70_4330_YYB_D",
    "protocol_type": 6
}''',
        '8.9.71': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537170072,
    "sub_app_id": 537170072,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.71.11735",
    "build_time": 1688560152,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2551",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 16724722,
    "sub_sig_map": 66560,
    "dump_time": 1688560152,
    "qua": "V1_AND_SQ_8.9.71_4332_YYB_D",
    "protocol_type": 1
}''',
        '8.9.73': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537171018,
    "sub_app_id": 537171018,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.73.11790",
    "build_time": 1690515318,
    "apk_sign": "d4dd51c0a4a7a37f7fa9d791cd1c0377",
    "sdk_version": "6.0.0.2553",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1690715354,
    "qua": "V1_AND_SQ_8.9.73_4354_HDBM_T",
    "protocol_type": 6
}''',
        '8.9.80': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537176902,
    "sub_app_id": 537176902,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.80.12440",
    "build_time": 1691565978,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2554",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 16724722,
    "sub_sig_map": 66560,
    "dump_time": 1692110632,
    "qua": "V1_AND_SQ_8.9.80_4614_YYB_D",
    "protocol_type": 6
}''',
        '8.9.83': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537178685,
    "sub_app_id": 537178685,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.83.12605",
    "build_time": 1691565978,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2554",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 16724722,
    "sub_sig_map": 66560,
    "dump_time": 1692110632,
    "qua": "V1_AND_SQ_8.9.83_4680_YYB_D",
    "protocol_type": 6
}''',
        '8.9.85': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537180607,
    "sub_app_id": 537180607,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.85.12820",
    "build_time": 1697015435,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2556",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 16724722,
    "sub_sig_map": 66560,
    "dump_time": 1692110632,
    "qua": "V1_AND_SQ_8.9.85_4766_YYB_D",
    "protocol_type": 6
}'''
    },
    'android_phone': {
        '8.9.58': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537163098,
    "sub_app_id": 537163098,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.58.11170",
    "build_time": 1684467300,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2545",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1686334718,
    "qua": "V1_AND_SQ_8.9.58_4106_YYB_D",
    "protocol_type": 1
}''',
        '8.9.63': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537164840,
    "sub_app_id": 537164840,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.63.11390",
    "build_time": 1685069178,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2546",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1687796862,
    "qua": "V1_AND_SQ_8.9.63_4194_YYB_D",
    "protocol_type": 1
}''',
        '8.9.68': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537168313,
    "sub_app_id": 537168313,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.68.11565",
    "build_time": 1688523354,
    "apk_sign": "7772804f3cb4961f57cb764fbe4973e6",
    "sdk_version": "6.0.0.2549",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1689780543,
    "qua": "V1_AND_SQ_8.9.68_4264_YYB_D",
    "protocol_type": 1
}''',
        '8.9.70': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537169928,
    "sub_app_id": 537169928,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.70.11730",
    "build_time": 1689956914,
    "apk_sign": "e686fa90d9a33950c46de9cfb4ec7e71",
    "sdk_version": "6.0.0.2551",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1690350020,
    "qua": "V1_AND_SQ_8.9.70_4330_YYB_D",
    "protocol_type": 1
}''',
        '8.9.71': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537170024,
    "sub_app_id": 537170024,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.71.11735",
    "build_time": 1688560152,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2551",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 16724722,
    "sub_sig_map": 66560,
    "dump_time": 1688560152,
    "qua": "V1_AND_SQ_8.9.71_4332_YYB_D",
    "protocol_type": 1
}''',
        '8.9.73': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537171007,
    "sub_app_id": 537171007,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.73.11790",
    "build_time": 1690515318,
    "apk_sign": "d4dd51c0a4a7a37f7fa9d791cd1c0377",
    "sdk_version": "6.0.0.2553",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 34869472,
    "sub_sig_map": 66560,
    "dump_time": 1690715354,
    "qua": "V1_AND_SQ_8.9.73_4354_HDBM_T",
    "protocol_type": 1
}''',
        '8.9.80': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537176863,
    "sub_app_id": 537176863,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.80.12440",
    "build_time": 1691565978,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2554",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 16724722,
    "sub_sig_map": 66560,
    "dump_time": 1692110632,
    "qua": "V1_AND_SQ_8.9.80_4614_YYB_D",
    "protocol_type": 1
}''',
        '8.9.83': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537178646,
    "sub_app_id": 537178646,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.83.12605",
    "build_time": 1691565978,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2554",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 16724722,
    "sub_sig_map": 66560,
    "dump_time": 1692110632,
    "qua": "V1_AND_SQ_8.9.83_4680_YYB_D",
    "protocol_type": 1
}''',
        '8.9.85': '''{
    "apk_id": "com.tencent.mobileqq",
    "app_id": 537180568,
    "sub_app_id": 537180568,
    "app_key": "0S200MNJT807V3GE",
    "sort_version_name": "8.9.85.12820",
    "build_time": 1697015435,
    "apk_sign": "a6b745bf24a2c277527716f6f36eb68d",
    "sdk_version": "6.0.0.2556",
    "sso_version": 20,
    "misc_bitmap": 150470524,
    "main_sig_map": 16724722,
    "sub_sig_map": 66560,
    "dump_time": 1692110632,
    "qua": "V1_AND_SQ_8.9.85_4766_YYB_D",
    "protocol_type": 1
}'''
    }
}

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
                resouce_api=resourceUrlPath,
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
account: # 账号相关
  uin: {uin} # QQ账号
  password: '{password}' # 密码为空时使用扫码登录
  encrypt: false  # 是否开启密码加密
  status: 0      # 在线状态 请参考 https://docs.go-cqhttp.org/guide/config.html#在线状态
  relogin: # 重连设置
    delay: 3   # 首次重连延迟, 单位秒
    interval: 3   # 重连间隔
    max-times: 0  # 最大重连次数, 0为无限制

  # 是否使用服务器下发的新地址进行重连
  # 注意, 此设置可能导致在海外服务器上连接情况更差
  use-sso-address: true
  # 是否允许发送临时会话消息
  allow-temp-session: false

  # 数据包的签名服务器列表，第一个作为主签名服务器，后续作为备用
  # 兼容 https://github.com/fuqiuluo/unidbg-fetch-qsign
  # 如果遇到 登录 45 错误, 或者发送信息风控的话需要填入一个或多个服务器
  # 不建议设置过多，设置主备各一个即可，超过 5 个只会取前五个
  # 示例:
  # sign-servers: 
  #   - url: 'http://127.0.0.1:8080' # 本地签名服务器
  #     key: "114514"  # 相应 key
  #     authorization: "-"   # authorization 内容, 依服务端设置
  #   - url: 'https://signserver.example.com' # 线上签名服务器
  #     key: "114514"  
  #     authorization: "-"   
  #   ...
  # 
  # 服务器可使用docker在本地搭建或者使用他人开放的服务
  sign-servers: 
{sign-servers-data}

  # 判断签名服务不可用（需要切换）的额外规则
  # 0: 不设置 （此时仅在请求无法返回结果时判定为不可用）
  # 1: 在获取到的 sign 为空 （若选此建议关闭 auto-register，一般为实例未注册但是请求签名的情况）
  # 2: 在获取到的 sign 或 token 为空（若选此建议关闭 auto-refresh-token ）
  rule-change-sign-server: 1

  # 连续寻找可用签名服务器最大尝试次数
  # 为 0 时会在连续 3 次没有找到可用签名服务器后保持使用主签名服务器，不再尝试进行切换备用
  # 否则会在达到指定次数后 **退出** 主程序
  max-check-count: 0
  # 签名服务请求超时时间(s)
  sign-server-timeout: 60
  # 如果签名服务器的版本在1.1.0及以下, 请将下面的参数改成true
  # 建议使用 1.1.6 以上版本，低版本普遍半个月冻结一次
  is-below-110: false
  # 在实例可能丢失（获取到的签名为空）时是否尝试重新注册
  # 为 true 时，在签名服务不可用时可能每次发消息都会尝试重新注册并签名。
  # 为 false 时，将不会自动注册实例，在签名服务器重启或实例被销毁后需要重启 go-cqhttp 以获取实例
  # 否则后续消息将不会正常签名。关闭此项后可以考虑开启签名服务器端 auto_register 避免需要重启
  # 由于实现问题，当前建议关闭此项，推荐开启签名服务器的自动注册实例
  auto-register: false
  # 是否在 token 过期后立即自动刷新签名 token（在需要签名时才会检测到，主要防止 token 意外丢失）
  # 独立于定时刷新
  auto-refresh-token: false
  # 定时刷新 token 间隔时间，单位为分钟, 建议 30~40 分钟, 不可超过 60 分钟
  # 目前丢失token也不会有太大影响，可设置为 0 以关闭，推荐开启
  refresh-interval: 40

heartbeat:
  # 心跳频率, 单位秒
  # -1 为关闭心跳
  interval: 5

message:
  # 上报数据类型
  # 可选: string,array
  post-format: string
  # 是否忽略无效的CQ码, 如果为假将原样发送
  ignore-invalid-cqcode: false
  # 是否强制分片发送消息
  # 分片发送将会带来更快的速度
  # 但是兼容性会有些问题
  force-fragment: false
  # 是否将url分片发送
  fix-url: false
  # 下载图片等请求网络代理
  proxy-rewrite: ''
  # 是否上报自身消息
  report-self-message: true
  # 移除服务端的Reply附带的At
  remove-reply-at: false
  # 为Reply附加更多信息
  extra-reply-data: false
  # 跳过 Mime 扫描, 忽略错误数据
  skip-mime-scan: false
  # 是否自动转换 WebP 图片
  convert-webp-image: false
  # download 超时时间(s)
  http-timeout: 15

output:
  # 日志等级 trace,debug,info,warn,error
  log-level: info
  # 日志时效 单位天. 超过这个时间之前的日志将会被自动删除. 设置为 0 表示永久保留.
  log-aging: 15
  # 是否在每次启动时强制创建全新的文件储存日志. 为 false 的情况下将会在上次启动时创建的日志文件续写
  log-force-new: true
  # 是否启用日志颜色
  log-colorful: false
  # 是否启用 DEBUG
  debug: false # 开启调试模式

# 默认中间件锚点
default-middlewares: &default
  # 访问密钥, 强烈推荐在公网的服务器设置
  access-token: '{access-token}'
  # 事件过滤器文件目录
  # API限速设置
  # 该设置为全局生效
  # 原 cqhttp 虽然启用了 rate_limit 后缀, 但是基本没插件适配
  # 目前该限速设置为令牌桶算法, 请参考:
  # https://baike.baidu.com/item/%E4%BB%A4%E7%89%8C%E6%A1%B6%E7%AE%97%E6%B3%95/6597000?fr=aladdin
  filter: '../filter.json'
  rate-limit:
    enabled: false # 是否启用限速
    frequency: 1  # 令牌回复频率, 单位秒
    bucket: 1     # 令牌桶大小

servers:
  # 添加方式，同一连接方式可添加多个，具体配置说明请查看文档
  #- http: # http 通信
  #- ws:   # 正向 Websocket
  #- ws-reverse: # 反向 Websocket
  #- pprof: #性能分析服务器
  - http:
      address: {servers-host}:{servers-port} # HTTP监听地址
      version: 11      # OneBot协议版本, 支持 11/12
      timeout: 60      # 反向 HTTP 超时时间, 单位秒，<5 时将被忽略
      long-polling:   # 长轮询拓展
        enabled: false       # 是否开启
        max-queue-size: 2000 # 消息队列大小，0 表示不限制队列大小，谨慎使用
      middlewares:
        <<: *default # 引用默认中间件
      post:           # 反向HTTP POST地址列表
       - url: '{servers-post-url}'
      #- url: ''                # 地址
      #  secret: ''             # 密钥
      #  max-retries: 3         # 最大重试，0 时禁用
      #  retries-interval: 1500 # 重试时间，单位毫秒，0 时立即
      #- url: http://127.0.0.1:5701/ # 地址
      #  secret: ''                  # 密钥
      #  max-retries: 10             # 最大重试，0 时禁用
      #  retries-interval: 1000      # 重试时间，单位毫秒，0 时立即

database: # 数据库相关设置
  leveldb:
    # 是否启用内置leveldb数据库
    # 启用将会增加10-20MB的内存占用和一定的磁盘空间
    # 关闭将无法使用 撤回 回复 get_msg 等上下文相关功能
    enable: true
  sqlite3:
    # 是否启用内置sqlite3数据库
    # 启用将会增加一定的内存占用和一定的磁盘空间
    # 关闭将无法使用 撤回 回复 get_msg 等上下文相关功能
    enable: false
    cachettl: 3600000000000 # 1h
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
        self.config_file_format['sign-servers-data'] = '''
    - url: '-'
      key: '-'
      authorization: '-'
'''
        if 'qsign-server' in self.bot_info_dict.extends \
        and type(self.bot_info_dict.extends['qsign-server']) is list \
        and len(self.bot_info_dict.extends['qsign-server']) > 0:
            self.config_file_format['sign-servers-data'] = ''
            for tmp_data_this in self.bot_info_dict.extends['qsign-server']:
                if type(tmp_data_this) is dict \
                and 'addr' in tmp_data_this \
                and 'key' in tmp_data_this:
                    self.config_file_format['sign-servers-data'] += '''
    - url: '%s'
      key: '%s'
      authorization: '-' ''' % (tmp_data_this['addr'], tmp_data_this['key'])

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

            protocal_info = None
            protocal_num = 6
            releaseDir('./conf/gocqhttp/' + bot_hash)
            releaseDir('./conf/gocqhttp/' + bot_hash + '/data')
            releaseDir('./conf/gocqhttp/' + bot_hash + '/data/versions')
            if 'qsign-server-protocal' in bot_info_dict[bot_hash].extends \
            and type(bot_info_dict[bot_hash].extends['qsign-server-protocal']) is str:
                if bot_info_dict[bot_hash].platform['model'] in [
                    'gocqhttp_show_Android_Pad'
                ]:
                    if bot_info_dict[bot_hash].extends['qsign-server-protocal'] in gProtocalInfo['android_pad']:
                        protocal_info = gProtocalInfo['android_pad'][bot_info_dict[bot_hash].extends['qsign-server-protocal']]
                    protocal_num = 6
                if bot_info_dict[bot_hash].platform['model'] in [
                    'gocqhttp_show_Android_Phone'
                ]:
                    if bot_info_dict[bot_hash].extends['qsign-server-protocal'] in gProtocalInfo['android_phone']:
                        protocal_info = gProtocalInfo['android_phone'][bot_info_dict[bot_hash].extends['qsign-server-protocal']]
                    protocal_num = 1
            if protocal_info is not None:
                file_path = './conf/gocqhttp/' + bot_hash + '/data/versions/%d.json' % protocal_num
                try:
                    with open(file_path, 'w', encoding = 'utf-8') as f:
                        f.write(protocal_info)
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
