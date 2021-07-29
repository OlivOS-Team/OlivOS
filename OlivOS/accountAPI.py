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
    def load(path, logger_proc):
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
            plugin_bot_info_dict[account_conf_account_this['id']] = OlivOS.API.bot_info_T(
                id = account_conf_account_this['id'], 
                host = account_conf_account_this['server']['host'], 
                port = account_conf_account_this['server']['port'], 
                access_token = account_conf_account_this['server']['access_token']
            )
            plugin_bot_info_dict[account_conf_account_this['id']].debug_mode = account_conf_account_this['debug']
            logger_proc.log(2, 'generate account [' + str(account_conf_account_this['id']) + '] ... done')
        logger_proc.log(2, 'generate account ... all done')
        return plugin_bot_info_dict