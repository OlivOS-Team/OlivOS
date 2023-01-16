# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/updateAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import os
import sys
import platform
import subprocess
import time
import requests as req
import json
import shutil
import zipfile

import OlivOS

update_bat_name = 'tmp.bat'


def OlivOSUpdateReplace(logger_proc):
    if platform.system() == 'Windows':
        clear_bat()
        exe_name = get_exe_name()
        exe_root_path = os.path.realpath(sys.argv[0])
        if exe_name is None:
            return
        with open(update_bat_name, 'w') as b:
            TempList = ""
            TempList += '@echo off\n'
            TempList += 'choice /t 2 /d y /n >nul\n'
            TempList += 'del ' + exe_root_path + '\n'
            TempList += 'move /y .\\resource\\' + exe_name + ' ' + exe_root_path + '\n'
            TempList += 'start ' + exe_name + ' --noblock\n'
            TempList += 'exit'
            b.write(TempList)
        subprocess.call(
            'start cmd /b /K ".\\' + update_bat_name + '"',
            shell=True,
            cwd='.\\'
        )
        OlivOS.bootAPI.killMain()


def OlivOSUpdateGet(logger_proc):
    res = False
    architecture_num = platform.architecture()[0]
    if platform.system() == 'Windows':
        clear_bat()
        exe_name = get_exe_name()
        if exe_name is not None:
            releaseDir('./tmp')
            down_file_name = './tmp/tmp.zip'
            down_dir_name = './tmp/tmp/'
            down_name = down_dir_name + exe_name
            target_name = './resource/' + exe_name
            logger_proc.log(2, 'check update ......')
            down_url_obj = GETHttpJson2Dict('https://api.oliva.icu/olivosver/')
            down_url = None
            if down_url_obj is not None:
                try:
                    if type(down_url_obj['version']['OlivOS'][architecture_num]['svn']) == int and \
                            down_url_obj['version']['OlivOS'][architecture_num]['svn'] > OlivOS.infoAPI.OlivOS_SVN:
                        down_url = down_url_obj['version']['OlivOS'][architecture_num]['path']
                    else:
                        down_url_obj = None
                        logger_proc.log(2, 'already latest.')
                except:
                    down_url = None
                    logger_proc.log(3, 'api error, skip update replace.')
            if down_url is not None:
                if GETHttpFile(
                        down_url,
                        down_file_name
                ):
                    unZipFile(down_file_name, down_dir_name)
                    shutil.move(down_name, target_name)
                    if os.path.isfile(target_name):
                        res = True
                        logger_proc.log(2, 'update file hit, will run update replace.')
                    else:
                        logger_proc.log(3, 'update file not hit, skip update replace.')
                clearFile(down_file_name)
                removeDir(down_dir_name)
        else:
            logger_proc.log(3, 'running in src mode, skip update replace.')
    return res


def GETHttpJson2Dict(url):
    msg_res = None
    res = None
    send_url = url
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA
    }
    try:
        msg_res = req.request("GET", send_url, headers=headers, timeout=60)
        res = json.loads(msg_res.text)
    except:
        pass
    return res


def GETHttpFile(url, path):
    res = False
    send_url = url
    headers = {
        'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA
    }
    try:
        msg_res = req.request("GET", send_url, headers=headers)
        releaseToDirForFile(path)
        with open(path, 'wb+') as tmp:
            tmp.write(msg_res.content)
        if msg_res.status_code in [200, 300]:
            res = True
        else:
            res = False
    except:
        res = False
    return res


def clear_bat():
    try:
        if os.path.isfile(update_bat_name):
            os.remove(update_bat_name)
    except:
        pass


def clearFile(path):
    try:
        if os.path.isfile(path):
            os.remove(path)
    except:
        pass


def get_exe_name():
    res = None
    for exe_this in ['OlivOS.exe', 'OlivOS_debug.exe']:
        if sys.executable.endswith(exe_this):
            res = exe_this
            break
    return res


def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def removeDir(dir_path):
    try:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
    except:
        try:
            if os.path.exists(dir_path):
                os.remove(dir_path)
        except:
            pass


def releaseToDir(dir_path):
    tmp_path_list = dir_path.rstrip('/').split('/')
    for tmp_path_list_index in range(len(tmp_path_list)):
        if tmp_path_list[tmp_path_list_index] != '':
            releaseDir('/'.join(tmp_path_list[:tmp_path_list_index + 1]))


def releaseToDirForFile(dir_path):
    tmp_path_list = dir_path.rstrip('/').split('/')
    if len(tmp_path_list) > 0:
        tmp_path_list = tmp_path_list[:-1]
    for tmp_path_list_index in range(len(tmp_path_list)):
        if tmp_path_list[tmp_path_list_index] != '':
            releaseDir('/'.join(tmp_path_list[:tmp_path_list_index + 1]))


def unZipFile(src, dst):
    with zipfile.ZipFile(src, 'r', zipfile.ZIP_DEFLATED) as z:
        z.extractall(dst)
