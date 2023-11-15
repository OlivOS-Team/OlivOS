# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/bootDataAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

# here put the import lib

import OlivOS

default_Conf = {
    "system": {
        "name": "OlivOS",
        "init": [
            "OlivOS_logger",
            "OlivOS_account_config",
            "OlivOS_multiLoginUI",
            "OlivOS_account_fix",
            "OlivOS_account_config_save",
            "OlivOS_account_config",
            "OlivOS_nativeWinUIAPI",
            "OlivOS_gocqhttp_lib_exe_model",
            "OlivOS_walleq_lib_exe_model",
            "OlivOS_cwcb_lib_exe_model",
            "OlivOS_hackChat_link",
            "OlivOS_qqRed_link",
            "OlivOS_dingtalk_link",
            "OlivOS_plugin",
            "OlivOS_virtual_terminal_link",
            "OlivOS_flask_post_rx",
            "OlivOS_onebotV12_link",
            "OlivOS_qqGuild_link",
            "OlivOS_qqGuildv2_link",
            "OlivOS_discord_link",
            "OlivOS_telegram_poll",
            "OlivOS_fanbook_poll",
            "OlivOS_kaiheila_link",
            "OlivOS_dodo_link",
            "OlivOS_biliLive_link",
            "OlivOS_update_check"
        ],
        "event": {
            "account_edit": [
                "OlivOS_account_config",
                "OlivOS_multiLoginUI",
                "OlivOS_account_fix",
                "OlivOS_account_config_save",
                "OlivOS_account_config",
                "OlivOS_account_config_update"
            ],
            "account_edit_asayc_start": [
                "OlivOS_account_config"
            ],
            "account_edit_asayc_do": [
                "OlivOS_multiLoginUI_asayc",
            ],
            "account_edit_asayc_end": [
                "OlivOS_account_fix",
                "OlivOS_account_config_save",
                "OlivOS_account_config",
                "OlivOS_account_config_update"
            ],
            "account_update": [
                "OlivOS_gocqhttp_lib_exe_model",
                "OlivOS_walleq_lib_exe_model",
                "OlivOS_cwcb_lib_exe_model",
                "OlivOS_hackChat_link",
                "OlivOS_qqRed_link",
                "OlivOS_dingtalk_link",
                "OlivOS_virtual_terminal_link",
                "OlivOS_flask_post_rx",
                "OlivOS_onebotV12_link",
                "OlivOS_qqGuild_link",
                "OlivOS_qqGuildv2_link",
                "OlivOS_discord_link",
                "OlivOS_telegram_poll",
                "OlivOS_fanbook_poll",
                "OlivOS_kaiheila_link",
                "OlivOS_dodo_link",
                "OlivOS_biliLive_link",
            ]
        },
        "type_event": {
            "account_update": [
                "gocqhttp_lib_exe_model",
                "walleq_lib_exe_model",
                "cwcb_lib_exe_model",
                "hackChat_link",
                "qqRed_link",
                "dingtalk_link",
                "terminal_link",
                "flask_post_rx",
                "onebotV12_link",
                "qqGuild_link",
                "qqGuildv2_link",
                "discord_link",
                "telegram_poll",
                "fanbook_poll",
                "kaiheila_link",
                "dodo_link",
                "biliLive_link",
            ]
        },
        "control_queue": "OlivOS_control_queue",
        "interval": 0.2,
        "proc_mode": "auto"
    },
    "queue": [
        "OlivOS_control_queue",
        "OlivOS_rx_queue",
        "OlivOS_logger_queue",
        "OlivOS_dodobot_rx_queue",
        "OlivOS_nativeUI_rx_queue",
        "OlivOS_gocqhttp_lib_rx_queue",
        "OlivOS_walleq_lib_rx_queue",
        "OlivOS_cwcb_lib_rx_queue",
        "OlivOS_virtual_terminal_queue",
        "OlivOS_hackChat_queue",
        "OlivOS_biliLive_queue",
        "OlivOS_onebotv12_queue",
        "OlivOS_qqRed_queue",
        "OlivOS_dingtalk_queue"
    ],
    "models": {
        "OlivOS_sleep": {
            "enable": True,
            "name": "OlivOS_sleep",
            "type": "sleep",
            "logger_proc": "OlivOS_logger"
        },
        "OlivOS_update_check": {
            "enable": True,
            "name": "OlivOS_update_check",
            "type": "update_check",
            "logger_proc": "OlivOS_logger"
        },
        "OlivOS_multiLoginUI": {
            "enable": True,
            "name": "OlivOS_multiLoginUI",
            "type": "multiLoginUI",
            "logger_proc": "OlivOS_logger"
        },
        "OlivOS_multiLoginUI_asayc": {
            "enable": True,
            "name": "OlivOS_multiLoginUI_asayc",
            "type": "multiLoginUI_asayc",
            "logger_proc": "OlivOS_logger"
        },
        "OlivOS_nativeWinUIAPI": {
            "enable": True,
            "name": "OlivOS_nativeWinUIAPI",
            "type": "nativeWinUI",
            "interval": 0.002,
            "dead_interval": 1,
            "rx_queue": "OlivOS_nativeUI_rx_queue",
            "tx_queue": [
                "OlivOS_rx_queue"
            ],
            "control_queue": "OlivOS_control_queue",
            "logger_proc": "OlivOS_logger"
        },
        "OlivOS_account_config_save": {
            "enable": True,
            "name": "OlivOS_account_config_save",
            "type": "account_config_save",
            "logger_proc": "OlivOS_logger",
            "data": {
                "path": "./conf/account.json"
            }
        },
        "OlivOS_account_fix": {
            "enable": True,
            "name": "OlivOS_account_fix",
            "type": "account_fix",
            "logger_proc": "OlivOS_logger"
        },
        "OlivOS_account_config": {
            "enable": True,
            "name": "OlivOS_account_config",
            "type": "account_config",
            "logger_proc": "OlivOS_logger",
            "data": {
                "path": "./conf/account.json"
            }
        },
        "OlivOS_account_config_safe": {
            "enable": True,
            "name": "OlivOS_account_config_safe",
            "type": "account_config_safe",
            "logger_proc": "OlivOS_logger",
            "data": {
                "path": "./conf/account.json"
            }
        },
        "OlivOS_account_config_update": {
            "enable": True,
            "name": "OlivOS_account_config_update",
            "type": "account_config_update",
            "logger_proc": "OlivOS_logger",
            "data": {
                "path": "./conf/account.json"
            }
        },
        "OlivOS_logger": {
            "enable": True,
            "name": "OlivOS_logger",
            "type": "logger",
            "interval": 0.002,
            "dead_interval": 1,
            "proc_mode": "auto",
            "rx_queue": "OlivOS_logger_queue",
            "control_queue": "OlivOS_control_queue",
            "mode": [
                "console_color",
                "logfile",
                "native"
            ],
            "fliter": [2, 3, 4, 5]
        },
        "OlivOS_plugin": {
            "enable": True,
            "name": "OlivOS_plugin",
            "type": "plugin",
            "interval": 0.002,
            "dead_interval": 1,
            "rx_queue": "OlivOS_rx_queue",
            "tx_queue": [
                "OlivOS_dodobot_rx_queue"
            ],
            "control_queue": "OlivOS_control_queue",
            "logger_proc": "OlivOS_logger",
            "treading_mode": "full",
            "restart_gate": 50000,
            "enable_auto_restart": True,
            "debug": False
        },
        "OlivOS_virtual_terminal_link": {
            "enable": True,
            "name": "OlivOS_virtual_terminal_link",
            "type": "terminal_link",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_virtual_terminal_queue",
            "tx_queue": "OlivOS_rx_queue",
            "control_queue": "OlivOS_control_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_flask_post_rx": {
            "enable": True,
            "name": "OlivOS_flask_post_rx",
            "type": "post",
            "interval": 0.002,
            "dead_interval": 1,
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False,
            "server": {
                "auto": True,
                "host": "0.0.0.0",
                "port": 55001
            }
        },
        "OlivOS_onebotV12_link": {
            "enable": True,
            "name": "OlivOS_onebotV12_link",
            "type": "onebotV12_link",
            "interval": 0.002,
            "dead_interval": 1,
            "rx_queue": "OlivOS_onebotv12_queue",
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_qqGuild_link": {
            "enable": True,
            "name": "OlivOS_qqGuild_link",
            "type": "qqGuild_link",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": None,
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_qqGuildv2_link": {
            "enable": True,
            "name": "OlivOS_qqGuildv2_link",
            "type": "qqGuildv2_link",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": None,
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_discord_link": {
            "enable": True,
            "name": "OlivOS_discord_link",
            "type": "discord_link",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": None,
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_hackChat_link": {
            "enable": True,
            "name": "OlivOS_hackChat_link",
            "type": "hackChat_link",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_hackChat_queue",
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_qqRed_link": {
            "enable": True,
            "name": "OlivOS_qqRed_link",
            "type": "qqRed_link",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_qqRed_queue",
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_biliLive_link": {
            "enable": True,
            "name": "OlivOS_biliLive_link",
            "type": "biliLive_link",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_biliLive_queue",
            "tx_queue": "OlivOS_rx_queue",
            "control_queue": "OlivOS_control_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_kaiheila_link": {
            "enable": True,
            "name": "OlivOS_kaiheila_link",
            "type": "kaiheila_link",
            "interval": 0.2,
            "dead_interval": 1,
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_telegram_poll": {
            "enable": True,
            "name": "OlivOS_telegram_poll",
            "type": "telegram_poll",
            "interval": 0.2,
            "dead_interval": 1,
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_fanbook_poll": {
            "enable": True,
            "name": "OlivOS_fanbook_poll",
            "type": "fanbook_poll",
            "interval": 0.2,
            "dead_interval": 1,
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_dodo_link": {
            "enable": True,
            "name": "OlivOS_dodo_link",
            "type": "dodo_link",
            "interval": 0.2,
            "dead_interval": 1,
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_dodo_poll": {
            "enable": True,
            "name": "OlivOS_dodo_poll",
            "type": "dodo_poll",
            "interval": 0.2,
            "dead_interval": 1,
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_dodobot_ea": {
            "enable": False,
            "name": "OlivOS_dodobot_ea",
            "type": "dodobot_ea",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_dodobot_rx_queue",
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_dodobot_ea_tx": {
            "enable": False,
            "name": "OlivOS_dodobot_ea_tx",
            "type": "dodobot_ea_tx",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_dodobot_rx_queue",
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_dingtalk_link": {
            "enable": True,
            "name": "OlivOS_dingtalk_link",
            "type": "dingtalk_link",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_dingtalk_queue",
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "debug": False
        },
        "OlivOS_gocqhttp_lib_exe_model": {
            "enable": True,
            "name": "OlivOS_gocqhttp_lib_exe_model",
            "type": "gocqhttp_lib_exe_model",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_gocqhttp_lib_rx_queue",
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "target_proc": "OlivOS_flask_post_rx",
            "control_queue": "OlivOS_control_queue",
            "debug": False
        },
        "OlivOS_walleq_lib_exe_model": {
            "enable": True,
            "name": "OlivOS_walleq_lib_exe_model",
            "type": "walleq_lib_exe_model",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_walleq_lib_rx_queue",
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "target_proc": None,
            "control_queue": "OlivOS_control_queue",
            "debug": False
        },
        "OlivOS_cwcb_lib_exe_model": {
            "enable": True,
            "name": "OlivOS_cwcb_lib_exe_model",
            "type": "cwcb_lib_exe_model",
            "interval": 0.2,
            "dead_interval": 1,
            "rx_queue": "OlivOS_cwcb_lib_rx_queue",
            "tx_queue": "OlivOS_rx_queue",
            "logger_proc": "OlivOS_logger",
            "target_proc": None,
            "control_queue": "OlivOS_control_queue",
            "debug": False
        },
        "OlivOS_webview_page": {
            "enable": True,
            "name": "OlivOS_webview_page",
            "type": "webview_page",
            "interval": 0.2,
            "dead_interval": 1,
            "logger_proc": "OlivOS_logger",
            "control_queue": "OlivOS_control_queue",
            "debug": False
        },
        "OlivOS_update_get": {
            "enable": True,
            "name": "OlivOS_update_get",
            "type": "update_get",
            "logger_proc": "OlivOS_logger"
        },
        "OlivOS_update_replace": {
            "enable": True,
            "name": "OlivOS_update_replace",
            "type": "update_replace",
            "logger_proc": "OlivOS_logger"
        }
    }
}
