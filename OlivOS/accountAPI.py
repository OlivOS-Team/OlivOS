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

import OlivOS


class Account(object):
    def load(path, logger_proc, safe_mode = False):
        account_conf = None
        with open(path, 'r', encoding = 'utf-8') as account_conf_f:
            account_conf = json.loads(account_conf_f.read())
        if account_conf == None:
            logger_proc.log(3, 'init account from [' + path + '] ... failed')
            sys.exit()
        else:
            logger_proc.log(2, 'init account from [' + path + '] ... done')
        plugin_bot_info_dict = {}
        for account_conf_account_this in account_conf['account']:
            if safe_mode:
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
            logger_proc.log(2, 'generate account [' + str(account_conf_account_this['id']) + '] ... done')
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
