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
@Copyright :   (C) 2020-2023, OlivOS-Team
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
import hashlib

import OlivOS

modelName = 'updateAPI'

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


def OlivOSUpdateGet(
    logger_proc,
    flagChackOnly=False,
    control_queue=None
):
    res = False
    architecture_num = platform.architecture()[0]
    if platform.system() == 'Windows':
        clear_bat()
        exe_name = 'OlivOS.exe'
        if flagChackOnly:
            time.sleep(10)
        else:
            exe_name = get_exe_name()
        if exe_name is not None:
            releaseDir('./tmp')
            down_file_name = './tmp/tmp.zip'
            down_dir_name = './tmp/tmp/'
            down_name = down_dir_name + exe_name
            target_name = './resource/' + exe_name
            logger_proc.log(2, OlivOS.L10NAPI.getTrans('check OlivOS update ......', [], modelName))
            down_url_obj = GETHttpJson2Dict('https://api.oliva.icu/olivosver/')
            down_url = None
            if down_url_obj is not None:
                try:
                    if type(down_url_obj['version']['OlivOS'][architecture_num]['svn']) == int \
                    and down_url_obj['version']['OlivOS'][architecture_num]['svn'] > OlivOS.infoAPI.OlivOS_SVN:
                        down_url = down_url_obj['version']['OlivOS'][architecture_num]['path']
                        if flagChackOnly:
                            logger_proc.log(3, OlivOS.L10NAPI.getTrans('OlivOS update found, please try update.', [], modelName))
                            if control_queue is not None:
                                control_queue.put(
                                    OlivOS.API.Control.packet(
                                        'send', {
                                            'target': {
                                                'type': 'nativeWinUI'
                                            },
                                            'data': {
                                                'action': 'show_update'
                                            }
                                        }
                                    ),
                                    block=False
                                )
                        else:
                            logger_proc.log(3, OlivOS.L10NAPI.getTrans('OlivOS update found.', [], modelName))
                    else:
                        down_url_obj = None
                        logger_proc.log(2, OlivOS.L10NAPI.getTrans('OlivOS already latest.', [], modelName))
                except:
                    down_url = None
                    logger_proc.log(3, OlivOS.L10NAPI.getTrans('check OlivOS update api error, skip update replace.', [], modelName))
            # flagChackOnly True时仅做检查，不进入后续流程
            if not flagChackOnly and down_url is not None:
                if GETHttpFile(
                        down_url,
                        down_file_name
                ):
                    unZipFile(down_file_name, down_dir_name)
                    shutil.move(down_name, target_name)
                    if os.path.isfile(target_name):
                        res = True
                        logger_proc.log(2, OlivOS.L10NAPI.getTrans('check OlivOS update file hit, will run update replace.', [], modelName))
                    else:
                        logger_proc.log(3, OlivOS.L10NAPI.getTrans('check OlivOS update file not hit, skip update replace.', [], modelName))
                clearFile(down_file_name)
                removeDir(down_dir_name)
        else:
            logger_proc.log(3, OlivOS.L10NAPI.getTrans('OlivOS running in src mode, skip update replace.', [], modelName))
    return res


def checkResouceFile(
    logger_proc:OlivOS.diagnoseAPI.logger,
    resouce_name:str,
    resouce_api:str,
    filePath:str,
    filePathUpdate:str,
    filePathFORCESKIP:str
):
    logger = loggerGen(logger_proc)
    sleepTime = 2
    architecture_num = platform.architecture()[0]

    logger(2, OlivOS.L10NAPI.getTrans('will check {0} lib after {1}s ...', [resouce_name, sleepTime], modelName))
    time.sleep(sleepTime)

    for i in range(1):
        fMD5 = None
        fMD5Update = None
        flagFORCESKIP = False
        flagAlreadyLatest = False
        fMD5 = checkFileMD5(filePath)
        logger(2, OlivOS.L10NAPI.getTrans(
            'check {0} lib patch [{1}] md5: [{2}]', [
                resouce_name,
                filePath,
                str(fMD5)
            ], modelName
        ))

        flagFORCESKIP = os.path.exists(filePathFORCESKIP)

        if not flagFORCESKIP:
            apiJsonData = OlivOS.updateAPI.GETHttpJson2Dict(resouce_api)
            fMD5UpdateTarget = None
            fMD5UpdateUrl = None
            try:
                fMD5UpdateTarget = apiJsonData['version'][resouce_name][architecture_num]['md5']
                fMD5UpdateUrl = apiJsonData['version'][resouce_name][architecture_num]['path']
            except:
                fMD5UpdateTarget = None
            if apiJsonData != None \
            and fMD5UpdateTarget != None \
            and fMD5UpdateUrl != None:
                logger(2, OlivOS.L10NAPI.getTrans(
                    'check {0} lib patch target md5: [{1}]', [
                        resouce_name,
                        str(fMD5UpdateTarget)
                    ], modelName
                ))
                if fMD5UpdateTarget != fMD5:
                    logger(2, OlivOS.L10NAPI.getTrans('download new {0} lib ...', [resouce_name], modelName))
                    if OlivOS.updateAPI.GETHttpFile(fMD5UpdateUrl, filePathUpdate):
                        logger(2, OlivOS.L10NAPI.getTrans('download new {0} lib done', [resouce_name], modelName))
                        fMD5Update = checkFileMD5(filePathUpdate)
                        logger(2, OlivOS.L10NAPI.getTrans(
                            'check {0} lib patch [{1}] md5: [{2}]', [
                                resouce_name,
                                filePathUpdate,
                                str(fMD5Update)
                            ], modelName
                        ))
                    else:
                        fMD5Update = None
                        logger(4, OlivOS.L10NAPI.getTrans('download new {0} lib FAILED! md5 check FAILED!', [resouce_name], modelName))
                else:
                    flagAlreadyLatest = True
            else:
                logger(4, OlivOS.L10NAPI.getTrans('download {0} lib patch FAILED! try later please!', [resouce_name], modelName))
                fMD5Update = None

            if flagAlreadyLatest:
                logger(2, OlivOS.L10NAPI.getTrans('{0} lib already latest!', [resouce_name], modelName))
            elif fMD5UpdateTarget != None and fMD5Update != fMD5UpdateTarget:
                logger(4, OlivOS.L10NAPI.getTrans('download {0} lib patch FAILED! try later please!', [resouce_name], modelName))
            elif fMD5Update != None and fMD5 != fMD5Update:
                logger(3, OlivOS.L10NAPI.getTrans('update {0} lib patch [{1}] -> [{2}]', [resouce_name, filePathUpdate, filePath], modelName))
                shutil.copyfile(src = filePathUpdate, dst = filePath)
                os.remove(filePathUpdate)
                logger(2, OlivOS.L10NAPI.getTrans('update {0} lib patch done!', [resouce_name], modelName))
            else:
                logger(2, OlivOS.L10NAPI.getTrans('{0} lib already latest!', [resouce_name], modelName))
        else:
            logger(3, OlivOS.L10NAPI.getTrans('{0} lib update FORCESKIP!', [resouce_name], modelName))
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


def GETHttpJson2Dict(url):
    msg_res = None
    res = None
    send_url = url
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': OlivOS.infoAPI.OlivOS_Header_UA
    }
    try:
        msg_res = req.request("GET", send_url, headers=headers, timeout=60, proxies=OlivOS.webTool.get_system_proxy())
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
        msg_res = req.request("GET", send_url, headers=headers, proxies=OlivOS.webTool.get_system_proxy())
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
