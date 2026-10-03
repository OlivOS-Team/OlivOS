# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/accountAPI.py
@Author    :   MetaLeo元理
@Contact   :
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

accountTypeList = [
    'QQ/NapCat/默认',
    'QQ/NapCat/9.9.19',
    'QQ/NapCat/9.9.11',
    'KOOK',
    'KOOK/消息兼容',
    '黑盒语音',
    'QQ官方/公域/V2',
    'QQ官方/公域/V2/Webhook',
    'QQ官方/公域/V2/纯频道',
    'QQ官方/公域/V2/纯频道/Webhook',
    'QQ官方/公域/V2/指定intents',
    'QQ官方/私域/V2',
    'QQ官方/私域/V2/Webhook',
    'QQ官方/私域/V2/指定intents',
    'QQ官方/沙盒/V2',
    'QQ官方/沙盒/V2/Webhook',
    'QQ官方/沙盒/V2/指定intents',
    'QQ官方/公域/V1',
    'QQ官方/私域/V1',
    'Discord',
    'Discord/指定intents',
    'Telegram',
    'Fanbook',
    'Hack.Chat',
    'Hack.Chat/私有',
    'onebotV12/正向WS',
    'onebotV11/正向WS',
    'onebotV11/正向WS/NapCat',
    'onebotV11/正向WS/LLOneBot',
    'onebotV11/正向WS/Lagrange',
    'onebotV11/正向WS/Shamrock',
    'onebotV11/反向WS',
    'onebotV11/反向WS/NapCat',
    'onebotV11/反向WS/LLOneBot',
    'onebotV11/反向WS/Lagrange',
    'onebotV11/反向WS/Shamrock',
    'onebotV11/Http',
    'onebotV11/Http/NapCat',
    'onebotV11/Http/LLOneBot',
    'onebotV11/Http/Lagrange',
    'onebotV11/Http/Shamrock',
    'Milky/自动',
    'Milky/自动/Yogurt',
    'Milky/自动/LLOneBot',
    'Milky/自动/Lagrange',
    'RED协议',
    '微信/ComWeChat',
    '米游社/大别野/公域',
    '米游社/大别野/私域',
    '米游社/大别野/沙盒',
    '渡渡语音/Dodo/V2',
    '渡渡语音/Dodo/V1',
    '钉钉',
    'B站直播间/游客',
    'B站直播间/登录',
    'FF14终端',
    '虚拟终端',
    '接口终端',
    'QQ/GoCq/安卓平板',
    'QQ/GoCq/安卓手机',
    'QQ/GoCq/安卓手表',
    'QQ/GoCq/默认',
    'QQ/GoCq/iPad',
    'QQ/GoCq/iMac',
    'QQ/Wq/安卓手表',
    'QQ/Wq/安卓手机',
    'QQ/Wq/安卓平板',
    'QQ/OPQ/默认',
    'QQ/OPQ/指定端口',
    'QQ/GoCq/旧',
    'QQ/Wq/旧',
    'QQ/NapCat/旧',
    'QQ/OPQ/指定端口/旧',
    'OPQBot/正向WS',
    '自定义'
]

accountTypeMappingList = {
    'onebotV11/正向WS': ['qq', 'onebot', 'default', 'True', 'websocket'],
    'onebotV11/正向WS/NapCat': ['qq', 'onebot', 'napcat_default', 'False', 'websocket'],
    'onebotV11/正向WS/LLOneBot': ['qq', 'onebot', 'llonebot_default', 'False', 'websocket'],
    'onebotV11/正向WS/Lagrange': ['qq', 'onebot', 'lagrange_default', 'False', 'websocket'],
    'onebotV11/正向WS/Shamrock': ['qq', 'onebot', 'shamrock_default', 'False', 'websocket'],
    'onebotV11/反向WS': ['qq', 'onebot', 'default', 'False', 'websocket_host'],
    'onebotV11/反向WS/NapCat': ['qq', 'onebot', 'napcat_default', 'False', 'websocket_host'],
    'onebotV11/反向WS/LLOneBot': ['qq', 'onebot', 'llonebot_default', 'False', 'websocket_host'],
    'onebotV11/反向WS/Lagrange': ['qq', 'onebot', 'lagrange_default', 'False', 'websocket_host'],
    'onebotV11/反向WS/Shamrock': ['qq', 'onebot', 'shamrock_default', 'False', 'websocket_host'],
    'onebotV11/Http': ['qq', 'onebot', 'default', 'False', 'post'],
    'onebotV11/Http/NapCat': ['qq', 'onebot', 'napcat_default', 'False', 'post'],
    'onebotV11/Http/LLOneBot': ['qq', 'onebot', 'llonebot_default', 'False', 'post'],
    'onebotV11/Http/Lagrange': ['qq', 'onebot', 'lagrange_default', 'False', 'post'],
    'onebotV11/Http/Shamrock': ['qq', 'onebot', 'shamrock_default', 'False', 'post'],
    'onebotV12/正向WS': ['qq', 'onebot', 'onebotV12', 'False', 'websocket'],
    'Milky/自动': ['qq', 'onebot', 'milky_default', 'True', 'auto'],
    'Milky/自动/Yogurt': ['qq', 'onebot', 'yogurt_milky', 'True', 'auto'],
    'Milky/自动/LLOneBot': ['qq', 'onebot', 'llonebot_milky', 'True', 'auto'],
    'Milky/自动/Lagrange': ['qq', 'onebot', 'lagrange_milky', 'True', 'auto'],
    'RED协议': ['qq', 'onebot', 'red', 'False', 'websocket'],
    'OPQBot/正向WS': ['qq', 'onebot', 'opqbot_default', 'False', 'websocket'],
    'QQ/OPQ/默认': ['qq', 'onebot', 'opqbot_auto', 'True', 'websocket'],
    'QQ/OPQ/指定端口': ['qq', 'onebot', 'opqbot_port', 'True', 'websocket'],
    'QQ/OPQ/指定端口/旧': ['qq', 'onebot', 'opqbot_port_old', 'True', 'websocket'],
    'QQ/NapCat/默认': ['qq', 'onebot', 'napcat_show_new', 'True', 'post'],
    'QQ/NapCat/9.9.19': ['qq', 'onebot', 'napcat_show_new_9_9_19', 'True', 'post'],
    'QQ/NapCat/9.9.11': ['qq', 'onebot', 'napcat_show', 'True', 'post'],
    'QQ/NapCat/旧': ['qq', 'onebot', 'napcat_show_old', 'True', 'post'],
    'QQ/GoCq/默认': ['qq', 'onebot', 'gocqhttp_show', 'True', 'post'],
    'QQ/GoCq/安卓手机': ['qq', 'onebot', 'gocqhttp_show_Android_Phone', 'True', 'post'],
    'QQ/GoCq/安卓平板': ['qq', 'onebot', 'gocqhttp_show_Android_Pad', 'True', 'post'],
    'QQ/GoCq/安卓手表': ['qq', 'onebot', 'gocqhttp_show_Android_Watch', 'True', 'post'],
    'QQ/GoCq/iPad': ['qq', 'onebot', 'gocqhttp_show_iPad', 'True', 'post'],
    'QQ/GoCq/iMac': ['qq', 'onebot', 'gocqhttp_show_iMac', 'True', 'post'],
    'QQ/GoCq/旧': ['qq', 'onebot', 'gocqhttp_show_old', 'True', 'post'],
    'QQ/Wq/默认': ['qq', 'onebot', 'walleq_show', 'True', 'websocket'],
    'QQ/Wq/安卓手机': ['qq', 'onebot', 'walleq_show_Android_Phone', 'True', 'websocket'],
    'QQ/Wq/安卓平板': ['qq', 'onebot', 'walleq_show_Android_Pad', 'True', 'websocket'],
    'QQ/Wq/安卓手表': ['qq', 'onebot', 'walleq_show_Android_Watch', 'True', 'websocket'],
    'QQ/Wq/iPad': ['qq', 'onebot', 'walleq_show_iPad', 'True', 'websocket'],
    'QQ/Wq/iMac': ['qq', 'onebot', 'walleq_show_iMac', 'True', 'websocket'],
    'QQ/Wq/旧': ['qq', 'onebot', 'walleq_show_old', 'True', 'websocket'],
    '微信/ComWeChat': ['wechat', 'onebot', 'ComWeChatBotClient', 'True', 'websocket'],
    'KOOK': ['kaiheila', 'kaiheila_link', 'default', 'True', 'websocket'],
    'KOOK/消息兼容': ['kaiheila', 'kaiheila_link', 'text', 'True', 'websocket'],
    '黑盒语音': ['xiaoheihe', 'xiaoheihe_link', 'default', 'True', 'websocket'],
    '米游社/大别野/公域': ['mhyVila', 'mhyVila_link', 'public', 'True', 'websocket'],
    '米游社/大别野/私域': ['mhyVila', 'mhyVila_link', 'private', 'True', 'websocket'],
    '米游社/大别野/沙盒': ['mhyVila', 'mhyVila_link', 'sandbox', 'True', 'websocket'],
    'B站直播间/游客': ['biliLive', 'biliLive_link', 'default', 'True', 'websocket'],
    'B站直播间/登录': ['biliLive', 'biliLive_link', 'login', 'True', 'websocket'],
    'QQ官方/公域/V1': ['qqGuild', 'qqGuild_link', 'public', 'True', 'websocket'],
    'QQ官方/私域/V1': ['qqGuild', 'qqGuild_link', 'private', 'True', 'websocket'],
    'QQ官方/公域/V2': ['qqGuild', 'qqGuildv2_link', 'public', 'True', 'websocket'],
    'QQ官方/公域/V2/Webhook': ['qqGuild', 'qqGuildv2_link', 'public', 'True', 'post'],
    'QQ官方/公域/V2/纯频道': ['qqGuild', 'qqGuildv2_link', 'public_guild_only', 'True', 'websocket'],
    'QQ官方/公域/V2/纯频道/Webhook': ['qqGuild', 'qqGuildv2_link', 'public_guild_only', 'True', 'post'],
    'QQ官方/公域/V2/指定intents': ['qqGuild', 'qqGuildv2_link', 'public_intents', 'True', 'websocket'],
    'QQ官方/私域/V2': ['qqGuild', 'qqGuildv2_link', 'private', 'True', 'websocket'],
    'QQ官方/私域/V2/Webhook': ['qqGuild', 'qqGuildv2_link', 'private', 'True', 'post'],
    'QQ官方/私域/V2/指定intents': ['qqGuild', 'qqGuildv2_link', 'private_intents', 'True', 'websocket'],
    'QQ官方/沙盒/V2': ['qqGuild', 'qqGuildv2_link', 'sandbox', 'True', 'websocket'],
    'QQ官方/沙盒/V2/Webhook': ['qqGuild', 'qqGuildv2_link', 'sandbox', 'True', 'post'],
    'QQ官方/沙盒/V2/指定intents': ['qqGuild', 'qqGuildv2_link', 'sandbox_intents', 'True', 'websocket'],
    'Telegram': ['telegram', 'telegram_poll', 'default', 'True', 'post'],
    'Discord': ['discord', 'discord_link', 'default', 'True', 'websocket'],
    'Discord/指定intents': ['discord', 'discord_link', 'intents', 'True', 'websocket'],
    '渡渡语音/Dodo/V2': ['dodo', 'dodo_link', 'default', 'True', 'websocket'],
    '渡渡语音/Dodo/V1': ['dodo', 'dodo_link', 'v1', 'True', 'websocket'],
    'Fanbook': ['fanbook', 'fanbook_poll', 'default', 'True', 'post'],
    'Hack.Chat': ['hackChat', 'hackChat_link', 'default', 'True', 'websocket'],
    'Hack.Chat/私有': ['hackChat', 'hackChat_link', 'private', 'True', 'websocket'],
    '虚拟终端': ['terminal', 'terminal_link', 'default', 'True', 'websocket'],
    '接口终端': ['terminal', 'terminal_link', 'postapi', 'True', 'post'],
    'FF14终端': ['terminal', 'terminal_link', 'ff14', 'True', 'post'],
    "钉钉": ["dingtalk", "dingtalk_link", "default", "True", "websocket"],
    # 这个自定义屁用没有，只是占位用的
    # 对应代码里这个作为缺省项使用，不走这个逻辑
    '自定义': ['qq', 'default', 'default', 'True', 'post']
}

accountTypeDataList_platform = [
    'wechat',
    'qq',
    'qqGuild',
    'kaiheila',
    'xiaoheihe',
    'mhyVila',
    'telegram',
    'dodo',
    'fanbook',
    'discord',
    'terminal',
    'hackChat',
    'biliLive',
    "dingtalk"
]

accountTypeDataList_platform_sdk = {
    'wechat': [
        'onebot'
    ],
    'qq': [
        'onebot',
        'milky'
    ],
    'qqGuild': [
        'qqGuild_link',
        'qqGuildv2_link'
    ],
    'kaiheila': [
        'kaiheila_link'
    ],
    'xiaoheihe': [
        'xiaoheihe_link'
    ],
    'telegram': [
        'telegram_poll'
    ],
    'dodo': [
        'dodo_link'
        # 'dodo_poll',
        # 'dodobot_ea'
    ],
    'mhyVila': [
        'mhyVila_link'
    ],
    'fanbook': [
        'fanbook_poll'
    ],
    'discord': [
        'discord_link'
    ],
    'terminal': [
        'terminal_link'
    ],
    'hackChat': [
        'hackChat_link'
    ],
    'biliLive': [
        'biliLive_link'
    ],
    "dingtalk": [
        "dingtalk_link"
    ]
}

accountTypeDataList_platform_sdk_model = {
    'wechat': {
        'onebot': [
            'onebotV12',
            'ComWeChatBotClient'
        ]
    },
    'qq': {
        'onebot': [
            # 'gocqhttp',
            # 'gocqhttp_hide',
            'default',
            'shamrock_default',
            'para_default',
            'onebotV12',
            'red',
            'gocqhttp_show',
            'gocqhttp_show_Android_Phone',
            'gocqhttp_show_Android_Pad',
            'gocqhttp_show_Android_Watch',
            'gocqhttp_show_iPad',
            'gocqhttp_show_iMac',
            'gocqhttp_show_old',
            'walleq',
            'walleq_hide',
            'walleq_show',
            'walleq_show_Android_Phone',
            # 'walleq_show_Android_Pad',
            'walleq_show_Android_Watch',
            'walleq_show_iPad',
            'walleq_show_iMac',
            'walleq_show_old',
            'opqbot_default',
            'opqbot_auto',
            'opqbot_port',
            'opqbot_port_old',
            'napcat',
            # 'napcat_hide',
            'napcat_show',
            'napcat_show_new',
            'napcat_show_new_9_9_19',
            'napcat_show_old',
            'napcat_default',
            'llonebot_default',
            'lagrange_default'
            'milky_default',
            'yogurt_milky',
            'llonebot_milky',
            'lagrange_milky'
        ],
        'milky': [
            'default',
            'yogurt_default',
            'llonebot_default',
            'lagrange_default'
        ]
    },
    'qqGuild': {
        'qqGuild_link': [
            'private',
            'public',
            'default'
        ],
        'qqGuildv2_link': [
            'public',
            'public_guild_only',
            'public_intents',
            'private',
            'private_intents',
            'sandbox',
            'sandbox_intents',
            'default'
        ]
    },
    'kaiheila': {
        'kaiheila_link': [
            'default',
            'card',
            'text'
        ]
    },
    'xiaoheihe': {
        'xiaoheihe_link': [
            'default'
        ]
    },
    'mhyVila': {
        'mhyVila_link': [
            'private',
            'public',
            'sandbox',
            'default'
        ]
    },
    'telegram': {
        'telegram_poll': [
            'default'
        ]
    },
    'discord': {
        'discord_link': [
            'default',
            'intents'
        ]
    },
    'dodo': {
        'dodo_link': [
            'default',
            'v1',
            'v2'
        ],
        'dodo_poll': [
            'default'
        ],
        'dodobot_ea': [
            'default'
        ]
    },
    'fanbook': {
        'fanbook_poll': [
            'default',
            'private'
        ]
    },
    'terminal': {
        'terminal_link': [
            'default',
            'postapi',
            'ff14'
        ]
    },
    'hackChat': {
        'hackChat_link': [
            'default',
            'private'
        ]
    },
    'biliLive': {
        'biliLive_link': [
            'default',
            'login'
        ]
    },
    "dingtalk": {
        "dingtalk_link": [
            "default"
        ]
    }
}

accountTypeDataList_server_auto = [
    str(True),
    str(False)
]

accountTypeDataList_server_type = [
    'post',
    "auto",
    'websocket',
    'websocket_host'
]


accountQsignProtocols = [
    'AstralQsign', '手动', '9.0.95', '9.0.56', '8.9.85', '8.9.83', '8.9.80',
    '8.9.73', '8.9.71', '8.9.70', '8.9.68', '8.9.63', '8.9.58'
]


def getAccountEditorMetadata():
    """原生窗口与 WebUI 共享的字段、标签和联动元数据。"""
    return {
        'type_list': accountTypeList,
        'type_note_list': {
            'QQ/GoCq/安卓手表': '密码留空即尝试使用扫码登录',
            'QQ/GoCq/旧': '密码留空即尝试使用扫码登录',
            'QQ/Wq/安卓手表': '密码留空即尝试使用扫码登录',
            'QQ/Wq/旧': '密码留空即尝试使用扫码登录',
            '微信/ComWeChat': '启动后需要再运行特定版本微信',
            'Hack.Chat': '密码可以留空',
            'RED协议': 'HTTP可以不填，反正也没实现',
            'QQ/OPQ/默认': '已弃用',
            'QQ/OPQ/指定端口': '已弃用',
            'QQ/OPQ/指定端口/旧': '已弃用',
            'QQ/NapCat/默认': '需要已经安装不低于9.9.22版本QQ',
            'QQ/NapCat/9.9.19': '需要已经安装不低于9.9.19版本QQ',
            'QQ/NapCat/9.9.11': '需要已经安装不高于9.9.11版本QQ',
            'QQ/NapCat/旧': '使用本方法需要已经安装较新版本QQ',
            'QQ官方/公域/V2': '请确保已经添加IP白名单',
            'QQ官方/公域/V2/Webhook': '请确保此BOT接入方式为Webhook',
            'QQ官方/公域/V2/纯频道': '请确保已经添加IP白名单',
            'QQ官方/公域/V2/纯频道/Webhook': '请确保此BOT接入方式为Webhook',
            'QQ官方/公域/V2/指定intents': '请确保已经添加IP白名单',
            'QQ官方/私域/V2': '请确保已经添加IP白名单',
            'QQ官方/私域/V2/Webhook': '请确保此BOT接入方式为Webhook',
            'QQ官方/私域/V2/指定intents': '请确保已经添加IP白名单',
            'QQ官方/沙盒/V2/Webhook': '请确保此BOT接入方式为Webhook'
        },
        'type_clear_note_list': {
            'QQ/GoCq/默认': './conf/gocqhttp/{bothash}',
            'QQ/GoCq/安卓手机': './conf/gocqhttp/{bothash}',
            'QQ/GoCq/安卓平板': './conf/gocqhttp/{bothash}',
            'QQ/GoCq/安卓手表': './conf/gocqhttp/{bothash}',
            'QQ/GoCq/iPad': './conf/gocqhttp/{bothash}',
            'QQ/GoCq/iMac': './conf/gocqhttp/{bothash}',
            'QQ/GoCq/旧': './conf/gocqhttp/{bothash}',
            'QQ/Wq/安卓手表': './conf/walleq/{bothash}',
            'QQ/Wq/安卓手机': './conf/walleq/{bothash}',
            'QQ/Wq/安卓平板': './conf/walleq/{bothash}',
            'QQ/Wq/旧': './conf/walleq/{bothash}',
            'QQ/OPQ/默认': './conf/OPQBot/{bothash}',
            'QQ/OPQ/指定端口': './conf/OPQBot/{bothash}',
            'QQ/OPQ/指定端口/旧': './conf/OPQBot/{bothash}',
            'QQ/NapCat/默认': './conf/napcat/{bothash}',
            'QQ/NapCat/9.9.19': './conf/napcat/{bothash}',
            'QQ/NapCat/9.9.11': './conf/napcat/{bothash}',
            'QQ/NapCat/旧': './conf/napcat/{bothash}'
        },
        'type_extend_note_list': {
            # 'QQ/GoCq/默认': ['签名服务器', 'sign-server'],
            # 'QQ/GoCq/安卓手机': ['签名服务器', 'sign-server'],
            # 'QQ/GoCq/安卓平板': ['签名服务器', 'sign-server'],
            # 'QQ/GoCq/旧': ['签名服务器', 'sign-server']
            'RED协议': ['HTTP地址'],
            '钉钉': ["AppKey", "AppSecret"],
            'Hack.Chat/私有': ["WS地址"]
        },
        'type_extends_name_note_list': {
            # 'QQ/GoCq/默认': ['签名服务器', 'KEY'],
            # 'QQ/GoCq/安卓手机': ['签名服务器', 'KEY'],
            # 'QQ/GoCq/安卓平板': ['签名服务器', 'KEY'],
            # 'QQ/GoCq/旧': ['签名服务器', 'KEY']
            'RED协议': ['HTTP地址'],
            '钉钉': ["AppKey", "AppSecret"],
            'Hack.Chat/私有': ["WS地址"]
        },
        'type_extends_note_list': {
            # 'QQ/GoCq/默认': {'签名服务器': 'sign-server', 'KEY': 'key'},
            # 'QQ/GoCq/安卓手机': {'签名服务器': 'sign-server', 'KEY': 'key'},
            # 'QQ/GoCq/安卓平板': {'签名服务器': 'sign-server', 'KEY': 'key'},
            # 'QQ/GoCq/旧': {'签名服务器': 'sign-server', 'KEY': 'key'},
            'RED协议': {'HTTP地址': 'http-path'},
            '钉钉': {"AppKey": 'app_key', "AppSecret": "app_secret"},
            'Hack.Chat/私有': {"WS地址": 'ws_path'}
        },
        'type_qsign_array_note_list': {
            'QQ/GoCq/默认': {'地址': 'sign-server', 'KEY': 'key'},
            'QQ/GoCq/安卓手机': {'地址': 'sign-server', 'KEY': 'key'},
            'QQ/GoCq/安卓平板': {'地址': 'sign-server', 'KEY': 'key'},
            'QQ/GoCq/旧': {'地址': 'sign-server', 'KEY': 'key'}
        },
        # 各类账号组合的匹配与注册表
        # 原本为合并格式，并在此处维护
        # type: [platform, sdk, model, server_auto, server_type, {data_dict}]
        # 现拆分为两个表，使用时合并，以便于维护
        # type: [platform, sdk, model, server_auto, server_type] + [{data_dict}]
        # 前半位于 OlivOS.accountMetadataAPI
        # 后半位于此处
        'type_mapping_list': {},
        'type_mapping_list_Entry_slot': {
            'onebotV11/正向WS': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/正向WS/NapCat': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/正向WS/LLOneBot': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/正向WS/Lagrange': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/正向WS/Shamrock': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/反向WS': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/反向WS/NapCat': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/反向WS/LLOneBot': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/反向WS/Lagrange': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/反向WS/Shamrock': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/Http': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/Http/NapCat': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/Http/LLOneBot': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/Http/Lagrange': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV11/Http/Shamrock': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'onebotV12/正向WS': {
                '账号': 'edit_root_Entry_ID',
                '地址': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'Milky/自动': {
                '账号': 'edit_root_Entry_ID',
                '主机': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'Milky/自动/Yogurt': {
                '账号': 'edit_root_Entry_ID',
                '主机': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'Milky/自动/LLOneBot': {
                '账号': 'edit_root_Entry_ID',
                '主机': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'Milky/自动/Lagrange': {
                '账号': 'edit_root_Entry_ID',
                '主机': 'edit_root_Entry_Server_host',
                '端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'RED协议': {
                '账号': 'edit_root_Entry_ID',
                'WS地址': 'edit_root_Entry_Server_host',
                'WS端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'OPQBot/正向WS': {
                'QQ号': 'edit_root_Entry_ID',
                '服务地址': 'edit_root_Entry_Server_host',
                '服务端口': 'edit_root_Entry_Server_port',
            },
            'QQ/OPQ/默认': {
                'QQ号': 'edit_root_Entry_ID',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'QQ/OPQ/指定端口': {
                'QQ号': 'edit_root_Entry_ID',
                '服务端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'QQ/OPQ/指定端口/旧': {
                'QQ号': 'edit_root_Entry_ID',
                '服务端口': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token',
            },
            'QQ/NapCat/默认': {
                'QQ号': 'edit_root_Entry_ID',
            },
            'QQ/NapCat/9.9.19': {
                'QQ号': 'edit_root_Entry_ID',
            },
            'QQ/NapCat/9.9.11': {
                'QQ号': 'edit_root_Entry_ID',
            },
            'QQ/NapCat/旧': {
                'QQ号': 'edit_root_Entry_ID',
                'TOKEN': 'edit_root_Entry_Server_access_token',
                '服务端口': 'edit_root_Entry_Server_port',
            },
            'QQ/GoCq/默认': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/GoCq/安卓手机': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/GoCq/安卓平板': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/GoCq/安卓手表': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/GoCq/iPad': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/GoCq/iMac': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/GoCq/旧': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/Wq/默认': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/Wq/安卓手机': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/Wq/安卓平板': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/Wq/安卓手表': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/Wq/iPad': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/Wq/iMac': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            'QQ/Wq/旧': {
                '账号': 'edit_root_Entry_ID',
                '密码': 'edit_root_Entry_Password',
            },
            '微信/ComWeChat': {
                '微信号': 'edit_root_Entry_ID'
            },
            'KOOK': {
                'Token': 'edit_root_Entry_Server_access_token'
            },
            'KOOK/消息兼容': {
                'Token': 'edit_root_Entry_Server_access_token'
            },
            '黑盒语音': {
                '机器人ID': 'edit_root_Entry_ID',
                '机器人令牌': 'edit_root_Entry_Server_access_token'
            },
            '米游社/大别野/公域': {
                'Bot_Id': 'edit_root_Entry_ID',
                'Secret': 'edit_root_Entry_Password',
                'Pub_Key': 'edit_root_Entry_Server_access_token'
            },
            '米游社/大别野/私域': {
                'Bot_Id': 'edit_root_Entry_ID',
                'Secret': 'edit_root_Entry_Password',
                'Pub_Key': 'edit_root_Entry_Server_access_token'
            },
            '米游社/大别野/沙盒': {
                'Bot_Id': 'edit_root_Entry_ID',
                'Secret': 'edit_root_Entry_Password',
                'Pub_Key': 'edit_root_Entry_Server_access_token',
                '别野号': 'edit_root_Entry_Server_port'
            },
            'B站直播间/游客': {
                '直播间ID': 'edit_root_Entry_Server_access_token'
            },
            'B站直播间/登录': {
                '直播间ID': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/公域/V1': {
                'AppID': 'edit_root_Entry_ID',
                '机器人令牌': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/私域/V1': {
                'AppID': 'edit_root_Entry_ID',
                '机器人令牌': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/公域/V2': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/公域/V2/Webhook': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/公域/V2/纯频道': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/公域/V2/纯频道/Webhook': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/公域/V2/指定intents': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token',
                'intents': 'edit_root_Entry_Server_port'
            },
            'QQ官方/私域/V2': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/私域/V2/Webhook': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/私域/V2/指定intents': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token',
                'intents': 'edit_root_Entry_Server_port'
            },
            'QQ官方/沙盒/V2': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/沙盒/V2/Webhook': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token'
            },
            'QQ官方/沙盒/V2/指定intents': {
                'AppID': 'edit_root_Entry_ID',
                'AppSecret': 'edit_root_Entry_Server_access_token',
                'intents': 'edit_root_Entry_Server_port'
            },
            'Telegram': {
                'TOKEN': 'edit_root_Entry_Server_access_token'
            },
            'Discord': {
                'TOKEN': 'edit_root_Entry_Server_access_token'
            },
            'Discord/指定intents': {
                'TOKEN': 'edit_root_Entry_Server_access_token',
                'intents': 'edit_root_Entry_Server_port'
            },
            '渡渡语音/Dodo/V2': {
                'BotID': 'edit_root_Entry_ID',
                'Bot私钥': 'edit_root_Entry_Server_access_token'
            },
            '渡渡语音/Dodo/V1': {
                'BotID': 'edit_root_Entry_ID',
                'Bot私钥': 'edit_root_Entry_Server_access_token'
            },
            'Fanbook': {
                'Token': 'edit_root_Entry_Server_access_token'
            },
            'Hack.Chat': {
                '房间名称': 'edit_root_Entry_Server_host',
                'Bot名称': 'edit_root_Entry_Server_access_token',
                '密码': 'edit_root_Entry_Password'
            },
            'Hack.Chat/私有': {
                '房间名称': 'edit_root_Entry_Server_host',
                'Bot名称': 'edit_root_Entry_Server_access_token',
                '密码': 'edit_root_Entry_Password'
            },
            '虚拟终端': {
                '账号': 'edit_root_Entry_ID'
            },
            '接口终端': {
                '账号': 'edit_root_Entry_ID',
                '端口': 'edit_root_Entry_Server_port'
            },
            'FF14终端': {
                '账号': 'edit_root_Entry_ID',
                '端口': 'edit_root_Entry_Server_port',
                '回调端口': 'edit_root_Entry_Server_access_token'
            },
            "钉钉": {
                "Robot Code": 'edit_root_Entry_ID'
            },
            '自定义': {
                'ID': 'edit_root_Entry_ID',
                'PASSWORD': 'edit_root_Entry_Password',
                'HOST': 'edit_root_Entry_Server_host',
                'PORT': 'edit_root_Entry_Server_port',
                'TOKEN': 'edit_root_Entry_Server_access_token'
            },
        },
        'platform_list': accountTypeDataList_platform,
        'platform_sdk_list': accountTypeDataList_platform_sdk,
        'platform_sdk_model_list': accountTypeDataList_platform_sdk_model,
    }
