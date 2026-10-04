# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/accountAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

import json
import os
import socket
from contextlib import closing
import platform
import random
import hashlib

import OlivOS

default_account_conf = {
    'account': []
}

modelName = 'accountAPI'


class Account(object):
    def load(path, logger_proc, safe_mode=False, strict=False):
        def report(field, reason):
            message = OlivOS.L10NAPI.getTrans(
                'Account config [{0}], field [{1}]: {2}. The invalid entry is skipped; startup will continue.',
                [str(path), field, reason], modelName
            )
            logger_proc.log(4, message)
            return message

        try:
            with open(path, 'r', encoding='utf-8') as account_conf_f:
                account_conf = json.load(account_conf_f)
        except FileNotFoundError:
            logger_proc.log(3, OlivOS.L10NAPI.getTrans('init account from [{0}] ... failed', [path], modelName))
            if strict:
                raise ValueError(OlivOS.L10NAPI.getTrans(
                    'cannot read the account file or parse its JSON; check encoding and syntax', [], modelName
                )) from None
            account_conf = default_account_conf
            logger_proc.log(2, OlivOS.L10NAPI.getTrans('init account from default ... done', [], modelName))
        except (OSError, UnicodeError, ValueError):
            message = report('account', OlivOS.L10NAPI.getTrans(
                'cannot read the account file or parse its JSON; check encoding and syntax', [], modelName
            ))
            if strict:
                raise ValueError(message) from None
            return {}
        else:
            logger_proc.log(2, OlivOS.L10NAPI.getTrans('init account from [{0}] ... done', [path], modelName))
        if type(account_conf) is not dict or type(account_conf.get('account')) is not list:
            message = report('account', OlivOS.L10NAPI.getTrans('expected {0}', ['array'], modelName))
            if strict:
                raise ValueError(message)
            return {}
        plugin_bot_info_dict = {}
        for index, account_conf_account_this in enumerate(account_conf['account']):
            errors = _validate_account_config(account_conf_account_this)
            if errors:
                for field, reason in errors:
                    message = report('account[%d]%s' % (index, '.' + field if field else ''), reason)
                if strict:
                    raise ValueError(message)
                continue
            if safe_mode and account_conf_account_this['sdk_type'] not in [
                'dodo_link'
            ]:
                tmp_password = ''
            else:
                tmp_password = account_conf_account_this['password']
            bot_info_tmp = OlivOS.API.bot_info_T(
                id=account_conf_account_this['id'],
                password=tmp_password,
                server_auto=account_conf_account_this['server']['auto'],
                server_type=account_conf_account_this['server']['type'],
                host=account_conf_account_this['server']['host'],
                port=account_conf_account_this['server']['port'],
                access_token=account_conf_account_this['server']['access_token'],
                platform_sdk=account_conf_account_this['sdk_type'],
                platform_platform=account_conf_account_this['platform_type'],
                platform_model=account_conf_account_this['model_type']
            )
            if (
                'extends' in account_conf_account_this
                and dict is type(account_conf_account_this['extends'])
            ):
                bot_info_tmp.extends = account_conf_account_this['extends']
            if (
                'enable' in account_conf_account_this
                and bool is type(account_conf_account_this['enable'])
            ):
                bot_info_tmp.enable = account_conf_account_this['enable']
            bot_info_tmp.debug_mode = account_conf_account_this['debug']
            if bot_info_tmp.hash in plugin_bot_info_dict:
                message = report('account[%d].id' % index, OlivOS.L10NAPI.getTrans(
                    'duplicate account ID under the same SDK and platform; the first entry is retained', [], modelName
                ))
                if strict:
                    raise ValueError(message)
                continue
            plugin_bot_info_dict[bot_info_tmp.hash] = bot_info_tmp
            if OlivOS.qqGuildv2SDK.is_qqGuildv2_webhook_account(bot_info_tmp):
                try:
                    OlivOS.qqGuildv2WebhookServerAPI.ensure_qqGuildv2_webhook_ssl_dir(
                        bot_info_tmp.id
                    )
                except Exception:
                    pass
            logger_proc.log(2, OlivOS.L10NAPI.getTrans('generate [{0}] account [{1}] as [{2}] ... done', [
                str(account_conf_account_this['platform_type']),
                str(account_conf_account_this['id']),
                bot_info_tmp.hash
            ], modelName))
        logger_proc.log(2, OlivOS.L10NAPI.getTrans('generate account ... all done', [], modelName))
        return plugin_bot_info_dict

    def save(path, logger_proc, Account_data, safe_mode=False, protect_existing=False):
        # 启动流程会自动回写配置；加载时跳过的坏条目不能因此从用户原文件中消失。
        if protect_existing and os.path.exists(path):
            try:
                Account.load(path, logger_proc, strict=True)
            except ValueError:
                logger_proc.log(4, OlivOS.L10NAPI.getTrans(
                    'Account config [{0}] contains errors; save was skipped to preserve the original file. '
                    'Please fix it before saving. Startup will continue.', [str(path)], modelName
                ))
                return False
        tmp_total_account_data = {}
        tmp_total_account_data['account'] = []
        for Account_data_this_key in Account_data:
            Account_data_this: OlivOS.API.bot_info_T = Account_data[Account_data_this_key]
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
            tmp_this_account_data['extends'] = Account_data_this.extends
            tmp_this_account_data['enable'] = getattr(Account_data_this, 'enable', True)
            tmp_this_account_data['debug'] = Account_data_this.debug_mode
            tmp_total_account_data['account'].append(tmp_this_account_data)
            if OlivOS.qqGuildv2SDK.is_qqGuildv2_webhook_account(Account_data_this):
                try:
                    OlivOS.qqGuildv2WebhookServerAPI.ensure_qqGuildv2_webhook_ssl_dir(
                        Account_data_this.id
                    )
                except Exception:
                    pass
        with open(path, 'w', encoding='utf-8') as account_conf_f:
            account_conf_f.write(json.dumps(tmp_total_account_data, indent=4))

    def getEnabledAccountData(Account_data):
        if type(Account_data) is not dict:
            return {}
        return {
            Account_data_this_key: Account_data[Account_data_this_key]
            for Account_data_this_key in Account_data
            if getattr(Account_data[Account_data_this_key], 'enable', True) is True
        }


def accountFix(basic_conf_models, bot_info_dict, logger_proc):
    res = {}
    with free_port_selector() as g:  # 在端口选择过程中使用上下文
        for basic_conf_models_this in basic_conf_models:
            if (
                basic_conf_models[basic_conf_models_this]['type'] == 'post'
                and basic_conf_models[basic_conf_models_this]['server']['auto'] is True
            ):
                basic_conf_models[basic_conf_models_this]['server']['host'] = '0.0.0.0'
                if isInuse(
                        '127.0.0.1',
                        basic_conf_models[basic_conf_models_this]['server']['port']
                ):
                    basic_conf_models[basic_conf_models_this]['server']['port'] = g.get_free_port()
            if (
                platform.system() == 'Windows'
                and basic_conf_models[basic_conf_models_this]['type'] == 'astralqsign_lib_exe_model'
                and basic_conf_models[basic_conf_models_this]['server']['auto'] is True
            ):
                basic_conf_models[basic_conf_models_this]['server']['host'] = '0.0.0.0'
                basic_conf_models[basic_conf_models_this]['server']['port'] = random.randint(10000, 65535)
                basic_conf_models[basic_conf_models_this]['server']['token'] = (
                    getToken(str(random.randint(10000, 65535)))
                )
                if isInuse(
                        '127.0.0.1',
                        basic_conf_models[basic_conf_models_this]['server']['port']
                ):
                    basic_conf_models[basic_conf_models_this]['server']['port'] = g.get_free_port()
        for bot_info_dict_this in bot_info_dict:
            Account_data_this = bot_info_dict[bot_info_dict_this]
            if getattr(Account_data_this, 'enable', True) is not True:
                res[bot_info_dict_this] = Account_data_this
                continue
            if platform.system() == 'Windows':
                if (
                    Account_data_this.platform['model'] in OlivOS.libEXEModelAPI.gCheckList
                    or Account_data_this.platform['model'] in OlivOS.libNapCatEXEModelAPI.gCheckList
                ):
                    if Account_data_this.post_info.auto is True:
                        Account_data_this.post_info.type = 'post'
                        Account_data_this.post_info.host = 'http://127.0.0.1'
                        Account_data_this.post_info.port = g.get_free_port()
                        Account_data_this.post_info.access_token = bot_info_dict_this
                if Account_data_this.platform['model'] in OlivOS.libWQEXEModelAPI.gCheckList:
                    if Account_data_this.post_info.auto is True:
                        Account_data_this.post_info.type = 'websocket'
                        Account_data_this.post_info.host = 'ws://127.0.0.1'
                        Account_data_this.post_info.port = g.get_free_port()
                        Account_data_this.post_info.access_token = bot_info_dict_this
                if Account_data_this.platform['model'] in OlivOS.libCWCBEXEModelAPI.gCheckList:
                    if Account_data_this.post_info.auto is True:
                        Account_data_this.post_info.type = 'websocket'
                        Account_data_this.post_info.host = 'ws://127.0.0.1'
                        Account_data_this.post_info.port = g.get_free_port()
                        Account_data_this.post_info.access_token = bot_info_dict_this
                if Account_data_this.platform['model'] in OlivOS.libOPQBotEXEModelAPI.gAutoCheckList:
                    if Account_data_this.post_info.auto is True:
                        Account_data_this.post_info.type = 'websocket'
                        Account_data_this.post_info.host = '127.0.0.1'
                        Account_data_this.post_info.port = g.get_free_port()
            res[bot_info_dict_this] = Account_data_this
    return res


def isInuse(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    flag = True
    try:
        s.connect((ip, port))
        s.shutdown(2)
        flag = True
    except Exception:
        flag = False
    return flag


class free_port_selector:
    "对先前的端口获取函数进行二次包装，使得在上下文范围内不会重复生成套接字"
    def __init__(self) -> None:
        self._socket_list = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def get_free_port(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket_list.append(s)     # 通过在分配端口阶段维持所有套接字，理论上可以杜绝 Issue #83
        return s.getsockname()[1]

    def close(self):
        for s in self._socket_list:
            s.close()


def get_free_port():
    "注意：本函数两次分配的端口有可能相同 (详见issue #83) 。推荐改用上方 free_port_selector 在上下文中分配端口！"
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def getToken(src: str):
    hash_tmp = hashlib.new('md5')
    hash_tmp.update(str(src).encode(encoding='UTF-8'))
    hash_tmp.update(str(114514666).encode(encoding='UTF-8'))
    return hash_tmp.hexdigest()


def normalizeAccountFields(fields):
    """沿用 TreeEditUI 的平台默认值，不写文件、不创建窗口。"""
    tmp_id = fields['id']
    tmp_password = fields['password']
    tmp_server_auto = fields['server_auto']
    tmp_server_type = fields['server_type']
    tmp_host = fields['host']
    tmp_port = fields['port']
    tmp_access_token = fields['access_token']
    tmp_platform_sdk = fields['platform_sdk']
    tmp_platform_platform = fields['platform_platform']
    tmp_platform_model = fields['platform_model']
    if (
        tmp_platform_platform == 'qq'
        and tmp_platform_sdk == 'onebot'
        and tmp_platform_model in OlivOS.onebotV11HostServerAPI.gCheckList
        and tmp_server_auto == 'True'
    ):
        if tmp_host == '':
            tmp_host = 'ws://127.0.0.1'
        if tmp_port == '':
            tmp_port = '58001'
        if tmp_access_token == '':
            tmp_access_token = 'NONEED'
    if (
        tmp_platform_platform == 'qq'
        and tmp_platform_sdk == 'onebot'
        and tmp_platform_model in OlivOS.onebotV11LinkServerAPI.gCheckList
        and tmp_server_auto == 'True'
    ):
        if tmp_host == '':
            tmp_host = 'ws://127.0.0.1'
        if tmp_port == '':
            tmp_port = '0'
        if tmp_access_token == '':
            tmp_access_token = 'NONEED'
    if (
        tmp_platform_platform == 'qq'
        and tmp_platform_sdk == 'onebot'
        and tmp_platform_model in OlivOS.flaskServerAPI.gCheckList
        and tmp_server_auto == 'True'
    ):
        if tmp_host == '':
            tmp_host = 'http://127.0.0.1'
        if tmp_port == '':
            tmp_port = '58000'
        if tmp_access_token == '':
            tmp_access_token = 'NONEED'
    if (
        tmp_platform_platform in ['qq', 'wechat']
        and tmp_platform_sdk == 'onebot'
        and tmp_platform_model in OlivOS.onebotV12LinkServerAPI.gCheckList
        and tmp_server_auto == 'True'
    ):
        if tmp_host == '':
            tmp_host = 'ws://127.0.0.1'
        if tmp_port == '':
            tmp_port = '58001'
        if tmp_access_token == '':
            tmp_access_token = 'NONEED'
    if (
        tmp_platform_platform == 'qq'
        and tmp_platform_sdk == 'onebot'
        and tmp_platform_model in OlivOS.milkyAutoServerAPI.gCheckList
        and tmp_server_auto == 'True'
    ):
        if tmp_host == '':
            tmp_host = '127.0.0.1'
        if tmp_port == '':
            tmp_port = '58001'
        if tmp_access_token == '':
            tmp_access_token = 'NONEED'
    if (
        tmp_platform_platform == 'qq'
        and tmp_platform_sdk == 'onebot'
        and tmp_platform_model in OlivOS.OPQBotLinkServerAPI.gCheckList
        and tmp_server_auto == 'False'
    ):
        if tmp_host == '':
            tmp_host = '127.0.0.1'
        if tmp_access_token == '':
            tmp_access_token = 'NONEED'
    if (
        tmp_platform_platform == 'qq'
        and tmp_platform_sdk == 'onebot'
        and tmp_platform_model in OlivOS.OPQBotLinkServerAPI.gCheckList
        and tmp_server_auto == 'True'
    ):
        if tmp_host == '':
            tmp_host = '127.0.0.1'
        if tmp_platform_model in [
            'opqbot_auto'
        ]:
            if tmp_port == '':
                tmp_port = '8086'
    if (
        tmp_platform_platform == 'qqGuild'
        and tmp_platform_sdk == 'qqGuild_link'
    ):
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
    if (
        tmp_platform_platform == 'qqGuild'
        and tmp_platform_sdk == 'qqGuildv2_link'
    ):
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_platform_model not in [
            'public_intents',
            'private_intents',
            'sandbox_intents'
        ]:
            if tmp_port == '':
                tmp_port = '0'
    if (
        tmp_platform_platform == 'mhyVila'
        and tmp_platform_sdk == 'mhyVila_link'
    ):
        tmp_id = tmp_id.strip('\n')
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
        if tmp_platform_model in ['public', 'private']:
            tmp_port = '0'
        try:
            tmp_access_token_new = json.loads(tmp_access_token)
            if type(tmp_access_token_new) is str:
                tmp_access_token = tmp_access_token_new
        except Exception:
            pass
            # traceback.print_exc()
    if (
        tmp_platform_platform == 'telegram'
        and tmp_platform_sdk == 'telegram_poll'
    ):
        if tmp_id == '':
            if len(tmp_access_token.split('.')) > 0:
                tmp_id = tmp_access_token.split('.')[0]
            if len(tmp_id) <= 0 or not tmp_id.isdigit():
                tmp_id = int(hashlib.md5(str(tmp_access_token).encode('utf-8')).hexdigest(), 16)
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'https://api.telegram.org'
        if tmp_port == '':
            tmp_port = '443'
    if (
        tmp_platform_platform == 'discord'
        and tmp_platform_sdk == 'discord_link'
    ):
        if tmp_id == '':
            tmp_id = int(hashlib.md5(str(tmp_access_token).encode('utf-8')).hexdigest(), 16)
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_platform_model not in [
            'intents'
        ]:
            if tmp_port == '':
                tmp_port = '0'
    if (
        tmp_platform_platform == 'kaiheila'
        and tmp_platform_sdk == 'kaiheila_link'
    ):
        if tmp_id == '':
            tmp_id = int(hashlib.md5(str(tmp_access_token).encode('utf-8')).hexdigest(), 16)
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
    if (
        tmp_platform_platform == 'xiaoheihe'
        and tmp_platform_sdk == 'xiaoheihe_link'
    ):
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
    if (
        tmp_platform_platform == 'biliLive'
        and tmp_platform_sdk == 'biliLive_link'
    ):
        if tmp_id == '':
            tmp_id = int(hashlib.md5(str(tmp_access_token).encode('utf-8')).hexdigest(), 16) % 100000000000000
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
    if (
        tmp_platform_platform == 'fanbook'
        and tmp_platform_sdk == 'fanbook_poll'
    ):
        if tmp_id == '':
            tmp_id = int(hashlib.md5(str(tmp_access_token).encode('utf-8')).hexdigest(), 16)
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
    if (
        tmp_platform_platform == 'dodo'
        and tmp_platform_sdk == 'dodo_poll'
    ):
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
    if (
        tmp_platform_platform == 'dodo'
        and tmp_platform_sdk == 'dodo_link'
    ):
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
    if (
        tmp_platform_platform == 'terminal'
        and tmp_platform_sdk == 'terminal_link'
        and tmp_platform_model == 'default'
    ):
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
        if tmp_access_token == '':
            tmp_access_token = 'NONEED'
    if (
        tmp_platform_platform == 'terminal'
        and tmp_platform_sdk == 'terminal_link'
        and tmp_platform_model == 'postapi'
    ):
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_access_token == '':
            tmp_access_token = 'NONEED'
    if (
        tmp_platform_platform == 'terminal'
        and tmp_platform_sdk == 'terminal_link'
        and tmp_platform_model == 'ff14'
    ):
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
    if (
        tmp_platform_platform == 'hackChat'
        and tmp_platform_sdk == 'hackChat_link'
        and tmp_platform_model in ['default', 'private']
    ):
        if tmp_id == '':
            tmp_id = random.randint(1000000000, 9999999999)
        if tmp_port == '':
            tmp_port = '0'
    if (
        tmp_platform_platform == 'dingtalk'
        and tmp_platform_sdk == 'dingtalk_link'
        and tmp_platform_model == 'default'
    ):
        if tmp_password == '':
            tmp_password = 'NONEED'
        if tmp_host == '':
            tmp_host = 'NONEED'
        if tmp_port == '':
            tmp_port = '0'
        if tmp_access_token == '':
            tmp_access_token = 'NONEED'
    return {
        'id': tmp_id,
        'password': tmp_password,
        'server_auto': tmp_server_auto,
        'server_type': tmp_server_type,
        'host': tmp_host,
        'port': tmp_port,
        'access_token': tmp_access_token,
        'platform_sdk': tmp_platform_sdk,
        'platform_platform': tmp_platform_platform,
        'platform_model': tmp_platform_model,
    }


def _validate_account_config(account):
    """校验存档字段，返回字段路径与原因；不回显字段值或修改用户配置。"""
    errors = []

    def error(field, source, args=None):
        errors.append((field, OlivOS.L10NAPI.getTrans(source, args or [], modelName)))

    def check_fields(data, fields, prefix='', optional=()):
        for field, types in fields.items():
            name = prefix + field
            if field not in data:
                if field not in optional:
                    error(name, 'required field is missing')
            elif type(data[field]) not in types:
                error(name, 'expected {0}', [' / '.join(t.__name__ for t in types)])
        for field in data:
            if field not in fields:
                error(prefix + field, 'unknown field; check the spelling')

    if type(account) is not dict:
        error('', 'expected {0}', ['object'])
        return errors
    check_fields(account, {
        'id': (str, int), 'password': (str, int), 'sdk_type': (str,), 'platform_type': (str,),
        'model_type': (str,), 'server': (dict,), 'enable': (bool,), 'debug': (bool,), 'extends': (dict,),
    }, optional=('enable', 'extends'))
    server = account.get('server')
    if type(server) is dict:
        check_fields(server, {
            'auto': (bool,), 'type': (str,), 'host': (str,), 'port': (int,),
            'access_token': (str, int, type(None)),
        }, prefix='server.')
    # 结构错误先处理，避免下游对非字符串/非对象字段做查表或索引而中断整个加载。
    if errors:
        return errors
    if type(account['id']) is str and not account['id'].strip():
        error('id', 'must not be empty')

    sdk, platform_name, model = (account[key] for key in ('sdk_type', 'platform_type', 'model_type'))
    metadata = OlivOS.accountMetadataAPI
    combinations = {
        (platform_name, sdk, model)
        for platform_name, sdks in metadata.accountTypeDataList_platform_sdk_model.items()
        for sdk, models in sdks.items() for model in models
    }
    presets = [row for title, row in metadata.accountTypeMappingList.items() if title != '自定义']
    combinations.update(tuple(row[:3]) for row in presets)
    # 保留已从编辑器隐藏、但连接器仍支持的历史 OneBot 型号。
    if sdk == 'onebot':
        for adapter in (OlivOS.flaskServerAPI, OlivOS.onebotV11LinkServerAPI, OlivOS.onebotV11HostServerAPI,
                        OlivOS.onebotV12LinkServerAPI, OlivOS.OPQBotLinkServerAPI, OlivOS.qqRedLinkServerAPI,
                        OlivOS.milkyAutoServerAPI):
            combinations.update(('qq', 'onebot', item) for item in adapter.gCheckList)
    platforms = sorted({item[0] for item in combinations})
    sdks = sorted({item[1] for item in combinations if item[0] == platform_name})
    models = sorted({item[2] for item in combinations if item[:2] == (platform_name, sdk)})
    if platform_name not in platforms:
        error('platform_type', 'invalid value or combination; supported values: {0}', [', '.join(platforms)])
    elif sdk not in sdks:
        error('sdk_type', 'invalid value or combination; supported values: {0}', [', '.join(sdks)])
    elif model not in models:
        error('model_type', 'invalid value or combination; supported values: {0}', [', '.join(models)])

    connections = {row[4] for row in presets if row[:3] == [platform_name, sdk, model]}
    if sdk == 'onebot':
        for connection, adapter in (
            ('post', OlivOS.flaskServerAPI), ('websocket', OlivOS.onebotV11LinkServerAPI),
            ('websocket_host', OlivOS.onebotV11HostServerAPI), ('websocket', OlivOS.onebotV12LinkServerAPI),
            ('websocket', OlivOS.OPQBotLinkServerAPI), ('websocket', OlivOS.qqRedLinkServerAPI),
            ('auto', OlivOS.milkyAutoServerAPI),
        ):
            if model in adapter.gCheckList:
                connections.add(connection)
    # 未定义专属连接约束的历史型号只检查通用枚举，不凭空推断配置规则。
    connections = connections or set(metadata.accountTypeDataList_server_type)
    if server['type'] not in connections:
        error('server.type', 'invalid value or combination; supported values: {0}', [', '.join(sorted(connections))])
    is_intents = model.endswith('intents') or (sdk == 'mhyVila_link' and model == 'sandbox')
    if server['port'] < 0 or (not is_intents and server['port'] > 65535):
        error('server.port', 'expected {0}', ['integer >= 0' if is_intents else 'integer 0-65535'])

    extends = account.get('extends', {})
    if sdk == 'dingtalk_link':
        for field in ('app_key', 'app_secret'):
            if field not in extends:
                error('extends.' + field, 'required field is missing')
            elif type(extends[field]) is not str:
                error('extends.' + field, 'expected {0}', ['str'])
            elif not extends[field].strip():
                error('extends.' + field, 'must not be empty')
    for field in ('ws_path', 'http-path'):
        if field in extends and type(extends[field]) is not str:
            error('extends.' + field, 'expected {0}', ['str'])
    if 'qsign-server' in extends:
        qsign = extends['qsign-server']
        if type(qsign) is not list or len(qsign) > 10:
            error('extends.qsign-server', 'expected {0}', ['array (0-10 items)'])
        else:
            for index, item in enumerate(qsign):
                name = 'extends.qsign-server[%d]' % index
                if type(item) is not dict:
                    error(name, 'expected {0}', ['object'])
                else:
                    for field in ('addr', 'key'):
                        if type(item.get(field, '')) is not str:
                            error(name + '.' + field, 'expected {0}', ['str'])
    return errors
