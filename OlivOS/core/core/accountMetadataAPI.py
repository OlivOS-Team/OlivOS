# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/accountAPI.py
@Author    :   MetaLeo元理
@Contact   :   
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

import OlivOS

accountTypeList = [
    'QQ/NapCat/默认',
    'QQ/NapCat/9.9.11',
    'KOOK',
    'KOOK/消息兼容',
    '黑盒语音',
    'QQ官方/公域/V2',
    'QQ官方/公域/V2/纯频道',
    'QQ官方/公域/V2/指定intents',
    'QQ官方/私域/V2',
    'QQ官方/私域/V2/指定intents',
    'QQ官方/沙盒/V2',
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
    'onebotV11/Http',
    'onebotV11/Http/NapCat',
    'onebotV11/Http/LLOneBot',
    'onebotV11/Http/Lagrange',
    'onebotV11/Http/Shamrock',
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
    'onebotV11/Http': ['qq', 'onebot', 'default', 'False', 'post'],
    'onebotV11/Http/NapCat': ['qq', 'onebot', 'napcat_default', 'False', 'post'],
    'onebotV11/Http/LLOneBot': ['qq', 'onebot', 'llonebot_default', 'False', 'post'],
    'onebotV11/Http/Lagrange': ['qq', 'onebot', 'lagrange_default', 'False', 'post'],
    'onebotV11/Http/Shamrock': ['qq', 'onebot', 'shamrock_default', 'False', 'post'],
    'onebotV11/Http/消息段': ['qq', 'onebot', 'array_default', 'False', 'post'],
    'onebotV12/正向WS': ['qq', 'onebot', 'onebotV12', 'False', 'websocket'],
    'RED协议': ['qq', 'onebot', 'red', 'False', 'websocket'],
    'OPQBot/正向WS': ['qq', 'onebot', 'opqbot_default', 'False', 'websocket'],
    'QQ/OPQ/默认': ['qq', 'onebot', 'opqbot_auto', 'True', 'websocket'],
    'QQ/OPQ/指定端口': ['qq', 'onebot', 'opqbot_port', 'True', 'websocket'],
    'QQ/OPQ/指定端口/旧': ['qq', 'onebot', 'opqbot_port_old', 'True', 'websocket'],
    'QQ/NapCat/默认': ['qq', 'onebot', 'napcat_show_new', 'True', 'post'],
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
    'QQ官方/公域/V2/纯频道': ['qqGuild', 'qqGuildv2_link', 'public_guild_only', 'True', 'websocket'],
    'QQ官方/公域/V2/指定intents': ['qqGuild', 'qqGuildv2_link', 'public_intents', 'True', 'websocket'],
    'QQ官方/私域/V2': ['qqGuild', 'qqGuildv2_link', 'private', 'True', 'websocket'],
    'QQ官方/私域/V2/指定intents': ['qqGuild', 'qqGuildv2_link', 'private_intents', 'True', 'websocket'],
    'QQ官方/沙盒/V2': ['qqGuild', 'qqGuildv2_link', 'sandbox', 'True', 'websocket'],
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
    "钉钉": ["dingtalk", "dingtalk_link", "default",  "True", "websocket"],
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
        'onebot'
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
            #'walleq_show_Android_Pad',
            'walleq_show_Android_Watch',
            'walleq_show_iPad',
            'walleq_show_iMac',
            'walleq_show_old',
            'opqbot_default',
            'opqbot_auto',
            'opqbot_port',
            'opqbot_port_old',
            'napcat',
            #'napcat_hide',
            'napcat_show',
            'napcat_show_new',
            'napcat_show_old',
            'napcat_default',
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
    'websocket'
]
