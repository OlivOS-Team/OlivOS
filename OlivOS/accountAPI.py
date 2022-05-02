# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/accountAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import json
import socket
from contextlib import closing

import OlivOS

default_account_conf = {
    'account': []
}

class Account(object):
    def load(path, logger_proc, safe_mode = False):
        account_conf = None
        try:
            with open(path, 'r', encoding = 'utf-8') as account_conf_f:
                account_conf = json.loads(account_conf_f.read())
        except:
            pass
        if account_conf == None:
            logger_proc.log(3, 'init account from [' + path + '] ... failed')
            account_conf = default_account_conf
            logger_proc.log(2, 'init account from default ... done')
        else:
            logger_proc.log(2, 'init account from [' + path + '] ... done')
        plugin_bot_info_dict = {}
        for account_conf_account_this in account_conf['account']:
            if safe_mode and account_conf_account_this['sdk_type'] not in [
                'dodo_link'
            ]:
                tmp_password = ''
            else:
                tmp_password = account_conf_account_this['password']
            bot_info_tmp = OlivOS.API.bot_info_T(
                id = account_conf_account_this['id'],
                password = tmp_password,
                server_auto = account_conf_account_this['server']['auto'],
                server_type = account_conf_account_this['server']['type'],
                host = account_conf_account_this['server']['host'],
                port = account_conf_account_this['server']['port'],
                access_token = account_conf_account_this['server']['access_token'],
                platform_sdk = account_conf_account_this['sdk_type'],
                platform_platform = account_conf_account_this['platform_type'],
                platform_model = account_conf_account_this['model_type']
            )
            bot_info_tmp.debug_mode = account_conf_account_this['debug']
            plugin_bot_info_dict[bot_info_tmp.hash] = bot_info_tmp
            logger_proc.log(2, 'generate [' + str(account_conf_account_this['platform_type']) + '] account [' + str(account_conf_account_this['id']) + '] as [' + bot_info_tmp.hash + '] ... done')
        logger_proc.log(2, 'generate account ... all done')
        return plugin_bot_info_dict

    def save(path, logger_proc, Account_data, safe_mode = False):
        tmp_total_account_data = {}
        tmp_total_account_data['account'] = []
        for Account_data_this_key in Account_data:
            Account_data_this = Account_data[Account_data_this_key]
            tmp_this_account_data = {}
            tmp_this_account_data['id'] = Account_data_this.id
            tmp_this_account_data['password'] = Account_data_this.password
            tmp_this_account_data['sdk_type'] = Account_data_this.platform['sdk']
            tmp_this_account_data['platform_type'] = Account_data_this.platform['platform']
            tmp_this_account_data['model_type'] = Account_data_this.platform['model']
            tmp_this_account_data['server'] = {}
            tmp_this_account_data['server']['auto'] = Account_data_this.post_info.auto
            tmp_this_account_data['server']['type'] = Account_data_this.post_info.type
            tmp_this_account_data['server']['host'] = Account_data_this.post_info.host
            tmp_this_account_data['server']['port'] = Account_data_this.post_info.port
            tmp_this_account_data['server']['access_token'] = Account_data_this.post_info.access_token
            tmp_this_account_data['debug'] = Account_data_this.debug_mode
            tmp_total_account_data['account'].append(tmp_this_account_data)
        with open(path, 'w', encoding = 'utf-8') as account_conf_f:
            account_conf_f.write(json.dumps(tmp_total_account_data, indent = 4))

def accountFix(basic_conf_models, bot_info_dict, logger_proc):
    res = {}
    for basic_conf_models_this in basic_conf_models:
        if basic_conf_models[basic_conf_models_this]['type'] == 'post':
            if basic_conf_models[basic_conf_models_this]['server']['auto'] == True:
                basic_conf_models[basic_conf_models_this]['server']['host'] = '0.0.0.0'
                if isInuse(
                    '127.0.0.1',
                    basic_conf_models[basic_conf_models_this]['server']['port']
                ):
                    basic_conf_models[basic_conf_models_this]['server']['port'] = get_free_port()
    for bot_info_dict_this in bot_info_dict:
        Account_data_this = bot_info_dict[bot_info_dict_this]
        if Account_data_this.platform['model'] == 'gocqhttp_show':
            if Account_data_this.post_info.auto == True:
                Account_data_this.post_info.type = 'post'
                Account_data_this.post_info.host = 'http://127.0.0.1'
                Account_data_this.post_info.port = get_free_port()
                Account_data_this.post_info.access_token = bot_info_dict_this
        res[bot_info_dict_this] = Account_data_this
    return res

def isInuse(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    flag = True
    try:
        s.connect((ip, port))
        s.shutdown(2)
        flag = True
    except:
        flag = False
    return flag


def get_free_port():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s: 
        s.bind(('', 0)) 
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 
        return s.getsockname()[1] 
