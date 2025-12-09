# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/bootAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

# here put the import lib

import subprocess
import sys
import os
import threading
import time
import json
import multiprocessing
import platform
import signal
import psutil
import atexit
import importlib
import traceback
import copy

import OlivOS

modelName = 'bootAPI'

gMonitorReg = {}
gLoggerProc = None

def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


class Entity(object):
    def __init__(self, basic_conf=None, patch_conf=None):
        self.Config = {
            'basic_conf_path': './conf/basic.json',
            'patch_conf_path': './conf/config.json'
        }
        if basic_conf is not None:
            self.Config['basic_conf_path'] = basic_conf
        if patch_conf is not None:
            self.Config['patch_conf_path'] = patch_conf

    def start(self):
        global gLoggerProc
        # 兼容Win平台多进程，避免形成fork-bomb
        multiprocessing.freeze_support()
        atexit.register(killMain)
        sys.setrecursionlimit(100000)
        basic_conf_path = self.Config['basic_conf_path']
        patch_conf_path = self.Config['patch_conf_path']
        basic_conf = None
        patch_conf = None
        basic_conf_models = None
        Proc_dict = {}
        Proc_Proc_dict = {}
        Proc_logger_name = []
        plugin_bot_info_dict = {}
        logger_proc = None

        preLoadPrint('OlivOS - Witness Union')
        start_up_show_str = ('''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \ 
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ / 
\____/ /_____/___/  _____/  \____/ /____/  
''')
        print(start_up_show_str)
        print('･ﾟ( ﾉヮ´ )(`ヮ´ )σ`∀´) ﾟ∀ﾟ)σ' + ' [OlivOS - Witness Union]\n')

        preLoadPrint('init config from [%s] ... ' % basic_conf_path)
        try:
            with open(basic_conf_path, 'r', encoding='utf-8') as basic_conf_f:
                basic_conf = json.loads(basic_conf_f.read())
        except:
            preLoadPrint('init config from [%s] ... not hit' % basic_conf_path)
            releaseDir('./conf')
            basic_conf = OlivOS.bootDataAPI.default_Conf
            preLoadPrint('init config from default ... done')
        else:
            preLoadPrint('init config from [%s] ... done' % basic_conf_path)

        preLoadPrint('patch config from [%s] ... ' % patch_conf_path)
        try:
            with open(patch_conf_path, 'r', encoding='utf-8') as patch_conf_f:
                patch_conf = json.loads(patch_conf_f.read())
        except:
            preLoadPrint('patch config from [%s] ... not hit' % patch_conf_path)
            releaseDir('./conf')
            preLoadPrint('patch config from default ... done')
        else:
            basic_conf = get_patch_config(basic_conf, patch_conf)
            preLoadPrint('patch config from [%s] ... done' % patch_conf_path)

        preLoadPrint('init models from config ... ')
        if basic_conf is not None:
            basic_conf_models = basic_conf['models']
            preLoadPrint('init models from config ... done')
        else:
            preLoadPrint('init models from config ... failed')
            sys.exit()

        preLoadPrint('generate queue from config ... ')
        multiprocessing_dict = {}
        for queue_name_this in basic_conf['queue']:
            preLoadPrint('generate [%s] queue ...' % queue_name_this)
            multiprocessing_dict[queue_name_this] = multiprocessing.Queue()
            preLoadPrint('generate [%s] queue ... done' % queue_name_this)
        preLoadPrint('generate queue from config ... all done')

        main_control = OlivOS.API.Control(
            name=basic_conf['system']['name'],
            init_list=basic_conf['system']['init'],
            control_queue=multiprocessing_dict[basic_conf['system']['control_queue']],
            scan_interval=basic_conf['system']['interval']
        )

        for basic_conf_models_this_name in main_control.init_list:
            main_control.control_queue.put(main_control.packet('init', basic_conf_models_this_name), block=False)

        preLoadPrint('get init args ...')
        # 判断启动参数
        basic_argv = []
        if len(sys.argv) >= 1:
            basic_argv = sys.argv[1:]
        flag_noblock = False
        if '--noblock' in basic_argv:
            flag_noblock = True
        preLoadPrint('get init args ... done')

        preLoadPrint('basic init done!')
        setSplashClose()

        while True:
            if main_control.control_queue.empty():
                time.sleep(main_control.scan_interval)
                continue
            else:
                try:
                    rx_packet_data = main_control.control_queue.get(block=False)
                except:
                    continue
            if rx_packet_data.action == 'init':
                # 兼容Win平台多进程，避免形成fork-bomb
                multiprocessing.freeze_support()
                basic_conf_models_this = basic_conf_models[rx_packet_data.key]
                tmp_proc_mode_raw = 'auto'
                tmp_proc_mode = 'threading'
                if 'proc_mode' in basic_conf['system']:
                    tmp_proc_mode_raw = basic_conf['system']['proc_mode']
                if 'proc_mode' in basic_conf_models_this:
                    tmp_proc_mode_raw = basic_conf['system']['proc_mode']
                tmp_proc_mode = tmp_proc_mode_raw
                if 'auto' == tmp_proc_mode_raw:
                    tmp_proc_mode = 'threading'
                if basic_conf_models_this['enable']:
                    logG(1, OlivOS.L10NAPI.getTrans('OlivOS model [{0}] will init', [
                            basic_conf_models_this['name']
                        ],
                        modelName
                    ))
                    if basic_conf_models_this['type'] == 'sleep':
                        time.sleep(10)
                    elif basic_conf_models_this['type'] == 'update_check':
                        threading.Thread(
                            target = OlivOS.updateAPI.OlivOSUpdateGet,
                            kwargs = {
                                'logger_proc': Proc_dict[basic_conf_models_this['logger_proc']],
                                'flagChackOnly': True,
                                'control_queue': main_control.control_queue
                            }
                        ).start()
                    elif basic_conf_models_this['type'] == 'logger':
                        Proc_dict[basic_conf_models_this['name']] = OlivOS.diagnoseAPI.logger(
                            Proc_name=basic_conf_models_this['name'],
                            scan_interval=basic_conf_models_this['interval'],
                            dead_interval=basic_conf_models_this['dead_interval'],
                            logger_queue=multiprocessing_dict[basic_conf_models_this['rx_queue']],
                            logger_mode=basic_conf_models_this['mode'],
                            logger_vis_level=basic_conf_models_this['fliter'],
                            control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']]
                        )
                        Proc_Proc_dict[basic_conf_models_this['name']] = Proc_dict[
                            basic_conf_models_this['name']].start_unity(tmp_proc_mode)
                        for this_bot_info in plugin_bot_info_dict:
                            plugin_bot_info_dict[this_bot_info].debug_logger = Proc_dict[basic_conf_models_this['name']]
                        logger_proc = Proc_dict[basic_conf_models_this['name']]
                        gLoggerProc = Proc_dict[basic_conf_models_this['name']]
                    elif basic_conf_models_this['type'] == 'plugin':
                        proc_plugin_func_dict = {}
                        tmp_tx_queue_list = []
                        for tmp_tx_queue_list_this in basic_conf_models_this['tx_queue']:
                            tmp_tx_queue_list.append(multiprocessing_dict[tmp_tx_queue_list_this])
                        Proc_dict[basic_conf_models_this['name']] = OlivOS.pluginAPI.shallow(
                            Proc_name=basic_conf_models_this['name'],
                            scan_interval=basic_conf_models_this['interval'],
                            dead_interval=basic_conf_models_this['dead_interval'],
                            rx_queue=multiprocessing_dict[basic_conf_models_this['rx_queue']],
                            tx_queue=tmp_tx_queue_list,
                            control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']],
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                            debug_mode=basic_conf_models_this['debug'],
                            plugin_func_dict=proc_plugin_func_dict,
                            bot_info_dict=plugin_bot_info_dict,
                            treading_mode=basic_conf_models_this['treading_mode'],
                            restart_gate=basic_conf_models_this['restart_gate'],
                            enable_auto_restart=basic_conf_models_this['enable_auto_restart']
                        )
                        if True or 'auto' == tmp_proc_mode_raw:
                            tmp_proc_mode = 'processing'
                        Proc_Proc_dict[basic_conf_models_this['name']] = Proc_dict[
                            basic_conf_models_this['name']].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'terminal_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'terminal_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'terminal_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                                multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                Proc_dict[tmp_Proc_name] = OlivOS.virtualTerminalLinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=multiprocessing_dict[tmp_queue_name],
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                    tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'post':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'onebot':
                                if plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.flaskServerAPI.gCheckList:
                                    flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        Proc_dict[basic_conf_models_this['name']] = OlivOS.flaskServerAPI.server(
                            Proc_name=basic_conf_models_this['name'],
                            scan_interval=basic_conf_models_this['interval'],
                            dead_interval=basic_conf_models_this['dead_interval'],
                            Flask_namespace=__name__,
                            Flask_server_methods=['GET', 'POST'],
                            Flask_host=basic_conf_models_this['server']['host'],
                            Flask_port=basic_conf_models_this['server']['port'],
                            tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                            debug_mode=basic_conf_models_this['debug'],
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                        )
                        Proc_Proc_dict[basic_conf_models_this['name']] = Proc_dict[
                            basic_conf_models_this['name']].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'onebotV12_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'onebot':
                                if plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                                    flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'onebot':
                                if plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.onebotV12LinkServerAPI.gCheckList:
                                    tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                    tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                                    multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                                    Proc_dict[tmp_Proc_name] = OlivOS.onebotV12LinkServerAPI.server(
                                        Proc_name=tmp_Proc_name,
                                        scan_interval=basic_conf_models_this['interval'],
                                        dead_interval=basic_conf_models_this['dead_interval'],
                                        rx_queue=multiprocessing_dict[tmp_queue_name],
                                        tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                        logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                        bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                        debug_mode=False
                                    )
                                    Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                        tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'qqRed_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'onebot':
                                if plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.qqRedLinkServerAPI.gCheckList:
                                    flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'onebot':
                                if plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.qqRedLinkServerAPI.gCheckList:
                                    tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                    tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                                    multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                                    Proc_dict[tmp_Proc_name] = OlivOS.qqRedLinkServerAPI.server(
                                        Proc_name=tmp_Proc_name,
                                        scan_interval=basic_conf_models_this['interval'],
                                        dead_interval=basic_conf_models_this['dead_interval'],
                                        rx_queue=multiprocessing_dict[tmp_queue_name],
                                        tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                        logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                        bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                        debug_mode=False
                                    )
                                    Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'dingtalk_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'dingtalk_link':
                                if plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.dingtalkLinkServerAPI.gCheckList:
                                    flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'dingtalk_link':
                                if plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.dingtalkLinkServerAPI.gCheckList:
                                    tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                    tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                                    multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                                    Proc_dict[tmp_Proc_name] = OlivOS.dingtalkLinkServerAPI.server(
                                        Proc_name=tmp_Proc_name,
                                        scan_interval=basic_conf_models_this['interval'],
                                        dead_interval=basic_conf_models_this['dead_interval'],
                                        rx_queue=multiprocessing_dict[tmp_queue_name],
                                        tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                        logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                        bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                        debug_mode=False
                                    )
                                    Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'account_config':
                        plugin_bot_info_dict = OlivOS.accountAPI.Account.load(
                            path=basic_conf_models_this['data']['path'],
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']]
                        )
                    elif basic_conf_models_this['type'] == 'account_config_safe':
                        plugin_bot_info_dict = OlivOS.accountAPI.Account.load(
                            path=basic_conf_models_this['data']['path'],
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                            safe_mode=True
                        )
                    elif basic_conf_models_this['type'] == 'account_fix':
                        plugin_bot_info_dict = OlivOS.fanbookPollServerAPI.accountFix(
                            bot_info_dict=plugin_bot_info_dict,
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                        )
                        plugin_bot_info_dict = OlivOS.kaiheilaLinkServerAPI.accountFix(
                            bot_info_dict=plugin_bot_info_dict,
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                        )
                        plugin_bot_info_dict = OlivOS.discordLinkServerAPI.accountFix(
                            bot_info_dict=plugin_bot_info_dict,
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                        )
                        if platform.system() == 'Windows':
                            OlivOS.libEXEModelAPI.accountFix(
                                bot_info_dict=plugin_bot_info_dict,
                                logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                            )
                        plugin_bot_info_dict = OlivOS.accountAPI.accountFix(
                            basic_conf_models=basic_conf_models,
                            bot_info_dict=plugin_bot_info_dict,
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                        )
                    elif basic_conf_models_this['type'] == 'qqGuild_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'qqGuild_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'qqGuild_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                Proc_dict[tmp_Proc_name] = OlivOS.qqGuildLinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=None,
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                    tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'qqGuildv2_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'qqGuildv2_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'qqGuildv2_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                Proc_dict[tmp_Proc_name] = OlivOS.qqGuildv2LinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=None,
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                    tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'discord_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'discord_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'discord_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                Proc_dict[tmp_Proc_name] = OlivOS.discordLinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=None,
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                    tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'kaiheila_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'kaiheila_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'kaiheila_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                Proc_dict[tmp_Proc_name] = OlivOS.kaiheilaLinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=None,
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                    tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'xiaoheihe_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'xiaoheihe_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'xiaoheihe_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                Proc_dict[tmp_Proc_name] = OlivOS.xiaoheiheLinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=None,
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                    tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'mhyVila_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'mhyVila_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'mhyVila_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                Proc_dict[tmp_Proc_name] = OlivOS.mhyVilaLinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=None,
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                    tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'biliLive_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'biliLive_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'biliLive_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                                multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                                Proc_dict[tmp_Proc_name] = OlivOS.biliLiveLinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=multiprocessing_dict[tmp_queue_name],
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                    tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'hackChat_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'hackChat_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'hackChat_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                                multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                                Proc_dict[tmp_Proc_name] = OlivOS.hackChatLinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=multiprocessing_dict[tmp_queue_name],
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'OPQBot_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'onebot':
                                if plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.OPQBotLinkServerAPI.gCheckList:
                                    flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'onebot':
                                if plugin_bot_info_dict[bot_info_key].platform['model'] in OlivOS.OPQBotLinkServerAPI.gCheckList:
                                    tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                    tmp_queue_name = basic_conf_models_this['rx_queue'] + '=' + bot_info_key
                                    multiprocessing_dict[tmp_queue_name] = multiprocessing.Queue()
                                    Proc_dict[tmp_Proc_name] = OlivOS.OPQBotLinkServerAPI.server(
                                        Proc_name=tmp_Proc_name,
                                        scan_interval=basic_conf_models_this['interval'],
                                        dead_interval=basic_conf_models_this['dead_interval'],
                                        rx_queue=multiprocessing_dict[tmp_queue_name],
                                        tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                        logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                        bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                        debug_mode=False
                                    )
                                    Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'telegram_poll':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'telegram_poll':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        Proc_dict[basic_conf_models_this['name']] = OlivOS.telegramPollServerAPI.server(
                            Proc_name=basic_conf_models_this['name'],
                            scan_interval=basic_conf_models_this['interval'],
                            dead_interval=basic_conf_models_this['dead_interval'],
                            rx_queue=None,
                            tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                            bot_info_dict=plugin_bot_info_dict,
                            debug_mode=False
                        )
                        Proc_Proc_dict[basic_conf_models_this['name']] = Proc_dict[
                            basic_conf_models_this['name']].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'fanbook_poll':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'fanbook_poll':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        Proc_dict[basic_conf_models_this['name']] = OlivOS.fanbookPollServerAPI.server(
                            Proc_name=basic_conf_models_this['name'],
                            scan_interval=basic_conf_models_this['interval'],
                            dead_interval=basic_conf_models_this['dead_interval'],
                            rx_queue=None,
                            tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                            bot_info_dict=plugin_bot_info_dict,
                            debug_mode=False
                        )
                        Proc_Proc_dict[basic_conf_models_this['name']] = Proc_dict[
                            basic_conf_models_this['name']].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'dodo_link':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'dodo_link':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'dodo_link':
                                tmp_Proc_name = basic_conf_models_this['name'] + '=' + bot_info_key
                                Proc_dict[tmp_Proc_name] = OlivOS.dodoLinkServerAPI.server(
                                    Proc_name=tmp_Proc_name,
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=None,
                                    tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict[bot_info_key],
                                    debug_mode=False
                                )
                                Proc_Proc_dict[tmp_Proc_name] = Proc_dict[tmp_Proc_name].start_unity(
                                    tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'dodo_poll':
                        flag_need_enable = False
                        for bot_info_key in plugin_bot_info_dict:
                            if plugin_bot_info_dict[bot_info_key].platform['sdk'] == 'dodo_poll':
                                flag_need_enable = True
                        if not flag_need_enable:
                            continue
                        Proc_dict[basic_conf_models_this['name']] = OlivOS.dodoPollServerAPI.server(
                            Proc_name=basic_conf_models_this['name'],
                            scan_interval=basic_conf_models_this['interval'],
                            dead_interval=basic_conf_models_this['dead_interval'],
                            rx_queue=None,
                            tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                            bot_info_dict=plugin_bot_info_dict,
                            debug_mode=False
                        )
                        Proc_Proc_dict[basic_conf_models_this['name']] = Proc_dict[
                            basic_conf_models_this['name']].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'dodobot_ea':
                        Proc_dict[basic_conf_models_this['name']] = OlivOS.dodobotEAServerAPI.server(
                            Proc_name=basic_conf_models_this['name'],
                            scan_interval=basic_conf_models_this['interval'],
                            dead_interval=basic_conf_models_this['dead_interval'],
                            rx_queue=None,
                            tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                            bot_info_dict=plugin_bot_info_dict,
                            debug_mode=False
                        )
                        Proc_Proc_dict[basic_conf_models_this['name']] = Proc_dict[
                            basic_conf_models_this['name']].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'dodobot_ea_tx':
                        Proc_dict[basic_conf_models_this['name']] = OlivOS.dodobotEATXAPI.server(
                            Proc_name=basic_conf_models_this['name'],
                            scan_interval=basic_conf_models_this['interval'],
                            dead_interval=basic_conf_models_this['dead_interval'],
                            rx_queue=multiprocessing_dict[basic_conf_models_this['rx_queue']],
                            tx_queue=multiprocessing_dict[basic_conf_models_this['tx_queue']],
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                            bot_info_dict=plugin_bot_info_dict,
                            debug_mode=False
                        )
                        Proc_Proc_dict[basic_conf_models_this['name']] = Proc_dict[
                            basic_conf_models_this['name']].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'multiLoginUI' and not flag_noblock:
                        if platform.system() == 'Windows':
                            tmp_callbackData = {'res': False}
                            HostUI_obj = OlivOS.multiLoginUIAPI.HostUI(
                                Model_name=basic_conf_models_this['name'],
                                Account_data=plugin_bot_info_dict,
                                logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                callbackData=tmp_callbackData
                            )
                            tmp_res = HostUI_obj.start()
                            if tmp_res != True:
                                killMain()
                            if HostUI_obj.UIData['flag_commit']:
                                plugin_bot_info_dict = HostUI_obj.UIData['Account_data']
                    elif basic_conf_models_this['type'] == 'multiLoginUI_asayc':
                        if platform.system() == 'Windows':
                            main_control.control_queue.put(
                                main_control.packet(
                                    'send',
                                    {
                                        'target': {
                                            'type': 'nativeWinUI'
                                        },
                                        'data': {
                                            'action': 'account_edit',
                                            'event': 'account_edit_on',
                                            'bot_info': plugin_bot_info_dict
                                        }
                                    }
                                ),
                                block=False
                            )
                    elif basic_conf_models_this['type'] == 'nativeWinUI':
                        if platform.system() == 'Windows':
                            if basic_conf_models_this['name'] not in Proc_dict:
                                Proc_dict[basic_conf_models_this['name']] = OlivOS.nativeWinUIAPI.dock(
                                    Proc_name=basic_conf_models_this['name'],
                                    scan_interval=basic_conf_models_this['interval'],
                                    dead_interval=basic_conf_models_this['dead_interval'],
                                    rx_queue=multiprocessing_dict[basic_conf_models_this['rx_queue']],
                                    tx_queue=None,
                                    control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']],
                                    logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                    bot_info_dict=plugin_bot_info_dict
                                )
                            # if True or 'auto' == tmp_proc_mode_raw:
                            #    tmp_proc_mode = 'processing'
                            if basic_conf_models_this['name'] not in Proc_Proc_dict:
                                Proc_Proc_dict[basic_conf_models_this['name']] = Proc_dict[
                                    basic_conf_models_this['name']].start_unity(tmp_proc_mode)
                    elif basic_conf_models_this['type'] == 'account_config_save':
                        OlivOS.accountAPI.Account.save(
                            path=basic_conf_models_this['data']['path'],
                            Account_data=plugin_bot_info_dict,
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']]
                        )
                    elif basic_conf_models_this['type'] == 'gocqhttp_lib_exe_model':
                        if platform.system() == 'Windows':
                            threading.Thread(
                                target = OlivOS.libEXEModelAPI.startGoCqhttpLibExeModel,
                                kwargs = {
                                    'plugin_bot_info_dict': plugin_bot_info_dict,
                                    'basic_conf_models_this': basic_conf_models_this,
                                    'multiprocessing_dict': multiprocessing_dict,
                                    'Proc_dict': Proc_dict,
                                    'Proc_Proc_dict': Proc_Proc_dict,
                                    'basic_conf_models': basic_conf_models,
                                    'tmp_proc_mode': tmp_proc_mode
                                }
                            ).start()
                    elif basic_conf_models_this['type'] == 'walleq_lib_exe_model':
                        if platform.system() == 'Windows':
                            threading.Thread(
                                target = OlivOS.libWQEXEModelAPI.startWalleQLibExeModel,
                                kwargs = {
                                    'plugin_bot_info_dict': plugin_bot_info_dict,
                                    'basic_conf_models_this': basic_conf_models_this,
                                    'multiprocessing_dict': multiprocessing_dict,
                                    'Proc_dict': Proc_dict,
                                    'Proc_Proc_dict': Proc_Proc_dict,
                                    'basic_conf_models': basic_conf_models,
                                    'tmp_proc_mode': tmp_proc_mode
                                }
                            ).start()
                    elif basic_conf_models_this['type'] == 'cwcb_lib_exe_model':
                        if platform.system() == 'Windows':
                            threading.Thread(
                                target = OlivOS.libCWCBEXEModelAPI.startCWCBQLibExeModel,
                                kwargs = {
                                    'plugin_bot_info_dict': plugin_bot_info_dict,
                                    'basic_conf_models_this': basic_conf_models_this,
                                    'multiprocessing_dict': multiprocessing_dict,
                                    'Proc_dict': Proc_dict,
                                    'Proc_Proc_dict': Proc_Proc_dict,
                                    'basic_conf_models': basic_conf_models,
                                    'tmp_proc_mode': tmp_proc_mode
                                }
                            ).start()
                    elif basic_conf_models_this['type'] == 'opqbot_lib_exe_model':
                        if platform.system() == 'Windows':
                            threading.Thread(
                                target = OlivOS.libOPQBotEXEModelAPI.startOPQBotLibExeModel,
                                kwargs = {
                                    'plugin_bot_info_dict': plugin_bot_info_dict,
                                    'basic_conf_models_this': basic_conf_models_this,
                                    'multiprocessing_dict': multiprocessing_dict,
                                    'Proc_dict': Proc_dict,
                                    'Proc_Proc_dict': Proc_Proc_dict,
                                    'basic_conf_models': basic_conf_models,
                                    'tmp_proc_mode': tmp_proc_mode
                                }
                            ).start()
                    elif basic_conf_models_this['type'] == 'napcat_lib_exe_model':
                        if platform.system() == 'Windows':
                            threading.Thread(
                                target = OlivOS.libNapCatEXEModelAPI.startNapCatLibExeModel,
                                kwargs = {
                                    'plugin_bot_info_dict': plugin_bot_info_dict,
                                    'basic_conf_models_this': basic_conf_models_this,
                                    'multiprocessing_dict': multiprocessing_dict,
                                    'Proc_dict': Proc_dict,
                                    'Proc_Proc_dict': Proc_Proc_dict,
                                    'basic_conf_models': basic_conf_models,
                                    'tmp_proc_mode': tmp_proc_mode
                                }
                            ).start()
                    elif basic_conf_models_this['type'] == 'astralqsign_lib_exe_model':
                        if platform.system() == 'Windows':
                            if not OlivOS.libAstralQsignEXEModelAPI.isBotActive(plugin_bot_info_dict):
                                continue
                            threading.Thread(
                                target = OlivOS.libAstralQsignEXEModelAPI.startAstralQsignLibExeModel,
                                kwargs = {
                                    'plugin_bot_info_dict': plugin_bot_info_dict,
                                    'basic_conf_models_this': basic_conf_models_this,
                                    'multiprocessing_dict': multiprocessing_dict,
                                    'Proc_dict': Proc_dict,
                                    'Proc_Proc_dict': Proc_Proc_dict,
                                    'basic_conf_models': basic_conf_models,
                                    'tmp_proc_mode': tmp_proc_mode
                                }
                            ).start()
                    elif basic_conf_models_this['type'] == 'update_get':
                        threading.Thread(
                            target=update_get_func,
                            args=(Proc_dict, basic_conf_models, basic_conf_models_this)
                        ).start()
                    elif basic_conf_models_this['type'] == 'update_replace':
                        OlivOS.updateAPI.OlivOSUpdateReplace(
                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']]
                        )
            elif rx_packet_data.action == 'restart_do':
                Proc_type_this = Proc_dict[rx_packet_data.key].Proc_type
                time.sleep(Proc_dict[rx_packet_data.key].Proc_info.dead_interval)
                Proc_Proc_dict[rx_packet_data.key].terminate()
                Proc_Proc_dict[rx_packet_data.key].join()
                Proc_dict.pop(rx_packet_data.key)
                Proc_Proc_dict.pop(rx_packet_data.key)
                main_control.control_queue.put(
                    OlivOS.API.Control.packet('init_type', Proc_type_this),
                    block=False
                )
            elif rx_packet_data.action == 'restart_send':
                for tmp_Proc_name in basic_conf_models:
                    basic_conf_models_this = basic_conf_models[tmp_Proc_name]
                    if basic_conf_models_this['type'] == rx_packet_data.key:
                        if Proc_dict[basic_conf_models_this['name']].Proc_info.rx_queue is not None:
                            Proc_dict[basic_conf_models_this['name']].Proc_info.rx_queue.put(
                                OlivOS.API.Control.packet('restart_do', basic_conf_models_this['name']),
                                block=False
                            )
            elif rx_packet_data.action == 'send':
                if type(rx_packet_data.key) == dict:
                    if 'target' in rx_packet_data.key:
                        if 'type' in rx_packet_data.key['target']:
                            flag_target_all = (rx_packet_data.key['target']['type'] == 'all')
                            flag_fliter = 'all'
                            if 'fliter' in rx_packet_data.key['target']:
                                flag_fliter = rx_packet_data.key['target']['fliter']
                            for tmp_Proc_name in basic_conf_models:
                                basic_conf_models_this = basic_conf_models[tmp_Proc_name]
                                if flag_target_all or basic_conf_models_this['type'] == rx_packet_data.key['target']['type']:
                                    model_name = basic_conf_models_this['name']
                                    if 'hash' in rx_packet_data.key['target']:
                                        model_name = '%s=%s' % (
                                            basic_conf_models_this['name'],
                                            rx_packet_data.key['target']['hash']
                                        )
                                    if model_name in Proc_dict:
                                        if flag_fliter in ['all', 'control_only']:
                                            try:
                                                if Proc_dict[model_name].Proc_info.control_rx_queue is not None:
                                                    Proc_dict[model_name].Proc_info.control_rx_queue.put(
                                                        rx_packet_data,
                                                        block=False
                                                    )
                                            except Exception as e:
                                                traceback.print_exc()
                                        if flag_fliter in ['all', 'rx_only']:
                                            try:
                                                if Proc_dict[model_name].Proc_info.rx_queue is not None:
                                                    Proc_dict[model_name].Proc_info.rx_queue.put(
                                                        rx_packet_data,
                                                        block=False
                                                    )
                                            except Exception as e:
                                                traceback.print_exc()
            elif rx_packet_data.action == 'init_type_open_webview_page':
                if platform.system() == 'Windows':
                    if type(rx_packet_data.key) is dict \
                    and 'target' in rx_packet_data.key \
                    and type(rx_packet_data.key['target']) is dict \
                    and 'data' in rx_packet_data.key \
                    and type(rx_packet_data.key['data']) is dict \
                    and 'action' in rx_packet_data.key['target'] \
                    and 'name' in rx_packet_data.key['target'] \
                    and 'title' in rx_packet_data.key['data'] \
                    and 'url' in rx_packet_data.key['data']:
                        if 'init' == rx_packet_data.key['target']['action']:
                            for basic_conf_models_this_key in basic_conf_models:
                                basic_conf_models_this = basic_conf_models[basic_conf_models_this_key]
                                if 'webview_page' == basic_conf_models_this['type']:
                                    if basic_conf_models_this['name'] not in Proc_dict:
                                        model_name = '%s+%s' % (
                                            basic_conf_models_this['name'],
                                            rx_packet_data.key['target']['name']
                                        )
                                        Proc_dict[model_name] = OlivOS.webviewUIAPI.page(
                                            Proc_name=model_name,
                                            scan_interval=basic_conf_models_this['interval'],
                                            dead_interval=basic_conf_models_this['dead_interval'],
                                            rx_queue=None,
                                            tx_queue=None,
                                            control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']],
                                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                            title=rx_packet_data.key['data']['title'],
                                            url=rx_packet_data.key['data']['url']
                                        )
                                    if model_name not in Proc_Proc_dict:
                                        Proc_Proc_dict[model_name] = Proc_dict[model_name].start_unity('processing')
            elif rx_packet_data.action == 'init_type_open_tx_turingTest_webview_page':
                if platform.system() == 'Windows':
                    if type(rx_packet_data.key) is dict \
                    and 'target' in rx_packet_data.key \
                    and type(rx_packet_data.key['target']) is dict \
                    and 'data' in rx_packet_data.key \
                    and type(rx_packet_data.key['data']) is dict \
                    and 'action' in rx_packet_data.key['target'] \
                    and 'name' in rx_packet_data.key['target'] \
                    and 'title' in rx_packet_data.key['data'] \
                    and 'url' in rx_packet_data.key['data']:
                        if 'init' == rx_packet_data.key['target']['action']:
                            for basic_conf_models_this_key in basic_conf_models:
                                basic_conf_models_this = basic_conf_models[basic_conf_models_this_key]
                                if 'tx_turingTest_webview_page' == basic_conf_models_this['type']:
                                    if basic_conf_models_this['name'] not in Proc_dict:
                                        model_name = '%s+%s' % (
                                            basic_conf_models_this['name'],
                                            rx_packet_data.key['target']['name']
                                        )
                                        Proc_dict[model_name] = OlivOS.libEXEModelAPI.txTuringTestPage(
                                            Proc_name=model_name,
                                            scan_interval=basic_conf_models_this['interval'],
                                            dead_interval=basic_conf_models_this['dead_interval'],
                                            rx_queue=None,
                                            tx_queue=None,
                                            control_queue=multiprocessing_dict[basic_conf_models_this['control_queue']],
                                            logger_proc=Proc_dict[basic_conf_models_this['logger_proc']],
                                            title=rx_packet_data.key['data']['title'],
                                            url=rx_packet_data.key['data']['url']
                                        )
                                    if model_name not in Proc_Proc_dict:
                                        Proc_Proc_dict[model_name] = Proc_dict[model_name].start_unity('processing')
            elif rx_packet_data.action == 'call_system_event':
                if type(rx_packet_data.key) is dict \
                and 'action' in rx_packet_data.key \
                and type(rx_packet_data.key['action']) is list:
                    for event_this in rx_packet_data.key['action']:
                        if 'event' in basic_conf['system'] \
                        and event_this in basic_conf['system']['event']:
                            for model_this in basic_conf['system']['event'][event_this]:
                                main_control.control_queue.put(
                                    main_control.packet('init', model_this),
                                    block=False
                                )
            elif rx_packet_data.action == 'call_system_stop_type_event':
                if type(rx_packet_data.key) is dict \
                and 'action' in rx_packet_data.key \
                and type(rx_packet_data.key['action']) is list:
                    for event_this in rx_packet_data.key['action']:
                        if 'type_event' in basic_conf['system'] \
                        and event_this in basic_conf['system']['type_event']:
                            for model_this in basic_conf['system']['type_event'][event_this]:
                                main_control.control_queue.put(
                                    main_control.packet('stop_type', model_this),
                                    block=False
                                )
            elif rx_packet_data.action == 'call_account_update':
                if type(rx_packet_data.key) is dict \
                and 'data' in rx_packet_data.key \
                and type(rx_packet_data.key['data']) is dict:
                    plugin_bot_info_dict = rx_packet_data.key['data']
                    main_control.control_queue.put(
                        main_control.packet(
                            'send', {
                                'target': {
                                    'type': 'all',
                                    'fliter': 'control_only'
                                },
                                'data': {
                                    'action': 'account_update',
                                    'data': plugin_bot_info_dict
                                }
                            }
                        ),
                        block=False
                    )
            elif rx_packet_data.action == 'init_type':
                for tmp_Proc_name in basic_conf_models:
                    basic_conf_models_this = basic_conf_models[tmp_Proc_name]
                    if basic_conf_models_this['type'] == rx_packet_data.key:
                        main_control.control_queue.put(
                            main_control.packet('init', basic_conf_models_this['name']),
                            block=False
                        )
                        logG(1, OlivOS.L10NAPI.getTrans('OlivOS model [{0}] type init', [
                                tmp_Proc_name
                            ],
                            modelName
                        ))
            elif rx_packet_data.action == 'stop_type':
                list_stop = []
                for tmp_Proc_name in Proc_Proc_dict:
                    try:
                        if tmp_Proc_name in Proc_dict \
                        and rx_packet_data.key == Proc_dict[tmp_Proc_name].Proc_type:
                            Proc_Proc_dict[tmp_Proc_name].terminate()
                            Proc_Proc_dict[tmp_Proc_name].join()
                            list_stop.append(tmp_Proc_name)
                            logG(1, OlivOS.L10NAPI.getTrans('OlivOS model [{0}] will stop', [
                                    tmp_Proc_name
                                ],
                                modelName
                            ))
                    except Exception as e:
                        traceback.print_exc()
                for tmp_Proc_name in list_stop:
                    Proc_dict.pop(tmp_Proc_name)
                    Proc_Proc_dict.pop(tmp_Proc_name)
            elif rx_packet_data.action == 'stop':
                tmp_Proc_name = rx_packet_data.key
                try:
                    if tmp_Proc_name in Proc_Proc_dict:
                        Proc_Proc_dict[tmp_Proc_name].terminate()
                        Proc_Proc_dict[tmp_Proc_name].join()
                        logG(1, OlivOS.L10NAPI.getTrans('OlivOS model [{0}] will stop', [
                                tmp_Proc_name
                            ],
                            modelName
                        ))
                        Proc_Proc_dict.pop(tmp_Proc_name)
                    if tmp_Proc_name in Proc_dict:
                        Proc_dict.pop(tmp_Proc_name)
                except Exception as e:
                    traceback.print_exc()
            elif rx_packet_data.action == 'exit_total':
                killMain()
            bootMonitor(varDict=locals())


def get_patch_config(basic_conf: dict, patch_conf: dict):
    res = basic_conf
    list_patch = [
        ['system', 'name'],
        ['system', 'init'],
        ['system', 'event'],
        ['system', 'type_event'],
        ['system', 'control_queue'],
        ['system', 'interval'],
        ['system', 'proc_mode'],
        ['queue']
    ]
    for i in list_patch:
        patch_config_by_path(basic_conf, patch_conf, i)
    if 'models' in basic_conf:
        for i in basic_conf['models']:
            patch_config_by_path(basic_conf, patch_conf, ['models', i])
    return res

def patch_config_by_path(basic_conf: dict, patch_conf: dict, path: list):
    basic_conf_this = basic_conf
    patch_conf_this = patch_conf
    if len(path) > 0:
        for idx in range(len(path)):
            if idx == len(path) - 1:
                break
            basic_conf_this = basic_conf_this[path[idx]]
            patch_conf_this = patch_conf_this[path[idx]]
        conf_key = path[-1]
        if conf_key in basic_conf_this \
        and conf_key in patch_conf_this:
            flag_same_type = False
            if type(basic_conf_this[conf_key]) is type(patch_conf_this[conf_key]):
                flag_same_type = True
            elif type(basic_conf_this[conf_key]) in (int, float) \
            and type(patch_conf_this[conf_key]) in (int, float):
                flag_same_type = True
            if flag_same_type:
                if type(basic_conf_this[conf_key]) is dict:
                    basic_conf_this[conf_key].update(patch_conf_this[conf_key])
                else:
                    basic_conf_this[conf_key] = patch_conf_this[conf_key]

def update_get_func(
        Proc_dict,
        basic_conf_models,
        basic_conf_models_this
):
    tmp_model_this_res = OlivOS.updateAPI.OlivOSUpdateGet(
        logger_proc=Proc_dict[basic_conf_models_this['logger_proc']]
    )
    if tmp_model_this_res:
        for tmp_Proc_name in basic_conf_models:
            basic_conf_models_this = basic_conf_models[tmp_Proc_name]
            if basic_conf_models_this['type'] == 'plugin':
                if Proc_dict[basic_conf_models_this['name']].Proc_info.rx_queue is not None:
                    Proc_dict[basic_conf_models_this['name']].Proc_info.rx_queue.put(
                        OlivOS.API.Control.packet('update_hit', basic_conf_models_this['name']),
                        block=False
                    )

# 进程监控
def bootMonitor(varDict:dict):
    global gMonitorReg
    try:
        gMonitorReg.setdefault('Proc_dict', {'keys': []})
        if 'Proc_dict' in varDict \
        and type(varDict['Proc_dict']) is dict:
            flagNeedRefresh = False
            for Proc_name in gMonitorReg['Proc_dict']['keys']:
                if Proc_name not in varDict['Proc_dict']:
                    flagNeedRefresh = True
                    logG(2, OlivOS.L10NAPI.getTrans('OlivOS model [{0}] stopped', [
                            Proc_name
                        ],
                        modelName
                    ))
            for Proc_name in varDict['Proc_dict']:
                if Proc_name not in gMonitorReg['Proc_dict']['keys']:
                    flagNeedRefresh = True
                    logG(2, OlivOS.L10NAPI.getTrans('OlivOS model [{0}] init', [
                            Proc_name
                        ],
                        modelName
                    ))
            if flagNeedRefresh:
                gMonitorReg['Proc_dict']['keys'] = copy.deepcopy(list(varDict['Proc_dict'].keys()))
    except Exception as e:
        traceback.print_exc()

# 进程管理
def killByPid(pid):
    parent = psutil.Process(pid)
    kill_process_and_its_children(parent)

def killMain():
    parent = psutil.Process(os.getpid())
    kill_process_and_its_children(parent)

def kill_process(p):
    try:
        p.terminate()
        _, alive = psutil.wait_procs([p, ], timeout=0.1)
        if len(alive):
            _, alive = psutil.wait_procs(alive, timeout=3.0)
            if len(alive):
                for p in alive:
                    p.kill()
    except Exception as e:
        print(e)


def kill_process_and_its_children(p):
    p = psutil.Process(p.pid)
    kill_process_children(p)
    kill_process(p)


def kill_process_children(p):
    p = psutil.Process(p.pid)
    if len(p.children()) > 0:
        for child in p.children():
            if hasattr(child, 'children') and len(child.children()) > 0:
                kill_process_and_its_children(child)
            else:
                kill_process(child)

# 日志工具
def log(logger_proc, log_level, log_message, log_segment=None):
    if log_segment is None:
        log_segment = []
    try:
        if logger_proc is not None:
            logger_proc.log(log_level, log_message, log_segment)
    except Exception as e:
        traceback.print_exc()

def logG(log_level, log_message, log_segment=None):
    global gLoggerProc
    log(
        logger_proc=gLoggerProc,
        log_level=log_level,
        log_message=log_message,
        log_segment=log_segment
    )

# 启动画面的操作
def setSplashClose():
    if '_PYIBoot_SPLASH' in os.environ and importlib.util.find_spec("pyi_splash"):
        import pyi_splash
        pyi_splash.close()

def setSplashText(msg:str):
    if '_PYIBoot_SPLASH' in os.environ and importlib.util.find_spec("pyi_splash"):
        import pyi_splash
        pyi_splash.update_text(msg)

def preLoadPrint(msg:str):
    print(msg)
    #setSplashText(text)
