r"""
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/__init__.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
"""

# here put the import lib

import platform

from . import hook, thirdPartyModule
from .adapter.biliLive import biliLiveLinkServerAPI, biliLiveSDK
from .adapter.dingtalk import dingtalkLinkServerAPI, dingtalkSDK
from .adapter.discord import discordLinkServerAPI, discordSDK
from .adapter.dodo import (
    dodobotEASDK,
    dodobotEAServerAPI,
    dodobotEATXAPI,
    dodoLinkSDK,
    dodoLinkServerAPI,
    dodoPollServerAPI,
    dodoSDK,
)
from .adapter.fanbook import fanbookPollServerAPI, fanbookSDK
from .adapter.hackChat import hackChatLinkServerAPI, hackChatSDK
from .adapter.kaiheila import kaiheilaLinkServerAPI, kaiheilaSDK
from .adapter.mhyVila import mhyVilaLinkServerAPI, mhyVilaSDK
from .adapter.onebotV11 import flaskServerAPI, onebotSDK
from .adapter.onebotV12 import onebotV12LinkServerAPI, onebotV12SDK
from .adapter.OPQBot import OPQBotLinkServerAPI, OPQBotSDK
from .adapter.qqGuild import qqGuildLinkServerAPI, qqGuildSDK, qqGuildv2LinkServerAPI, qqGuildv2SDK
from .adapter.red import qqRedLinkServerAPI, qqRedSDK
from .adapter.telegram import telegramPollServerAPI, telegramSDK
from .adapter.virtualTerminal import virtualTerminalLinkServerAPI, virtualTerminalSDK
from .adapter.xiaoheihe import xiaoheiheLinkServerAPI, xiaoheiheSDK
from .core.boot import bootAPI, bootDataAPI
from .core.core import API, accountAPI, accountMetadataAPI, contentAPI, diagnoseAPI, messageAPI, metadataAPI, pluginAPI
from .core.info import infoAPI
from .core.inlineData import data
from .core.L10N import L10NAPI, L10NDataAPI
from .core.web import updateAPI, webTool

if platform.system() == 'Windows':
    from .libBooter import (
        libAstralQsignEXEModelAPI,
        libCWCBEXEModelAPI,
        libEXEModelAPI,
        libNapCatEXEModelAPI,
        libOPQBotEXEModelAPI,
        libWQEXEModelAPI,
    )
    from .nativeGUI import multiLoginUIAPI, nativeWinUIAPI, webviewUIAPI
from . import userModule
