# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/__init__.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

# here put the import lib

import platform

from .core.info import infoAPI
from .core.L10N import L10NAPI
from .core.L10N import L10NDataAPI
from .core.boot import bootAPI
from .core.boot import bootDataAPI
from .core.inlineData import data
from . import hook
from .core.core import contentAPI
from .core.core import messageAPI
from .core.core import metadataAPI
from .core.core import API
from . import thirdPartyModule
from .core.core import accountAPI
from .core.core import diagnoseAPI
from .adapter.onebotV11 import flaskServerAPI
from .adapter.onebotV12 import onebotV12SDK
from .adapter.onebotV12 import onebotV12LinkServerAPI
from .core.core import pluginAPI
from .adapter.onebotV11 import onebotSDK
from .adapter.virtualTerminal import virtualTerminalSDK
from .adapter.virtualTerminal import virtualTerminalLinkServerAPI
from .adapter.qqGuild import qqGuildSDK
from .adapter.qqGuild import qqGuildLinkServerAPI
from .adapter.qqGuild import qqGuildv2SDK
from .adapter.qqGuild import qqGuildv2LinkServerAPI
from .adapter.red import qqRedSDK
from .adapter.red import qqRedLinkServerAPI
from .adapter.OPQBot import OPQBotSDK
from .adapter.OPQBot import OPQBotLinkServerAPI
from .adapter.telegram import telegramSDK
from .adapter.telegram import telegramPollServerAPI
from .adapter.discord import discordSDK
from .adapter.discord import discordLinkServerAPI
from .adapter.hackChat import hackChatSDK
from .adapter.hackChat import hackChatLinkServerAPI
from .adapter.dodo import dodobotEAServerAPI
from .adapter.dodo import dodobotEATXAPI
from .adapter.dodo import dodobotEASDK
from .adapter.dodo import dodoSDK
from .adapter.dodo import dodoPollServerAPI
from .adapter.dodo import dodoLinkSDK
from .adapter.dodo import dodoLinkServerAPI
from .adapter.dingtalk import dingtalkSDK
from .adapter.dingtalk import dingtalkLinkServerAPI
from .adapter.fanbook import fanbookSDK
from .adapter.fanbook import fanbookPollServerAPI
from .adapter.kaiheila import kaiheilaSDK
from .adapter.kaiheila import kaiheilaLinkServerAPI
from .adapter.mhyVila import mhyVilaSDK
from .adapter.mhyVila import mhyVilaLinkServerAPI
from .adapter.biliLive import biliLiveSDK
from .adapter.biliLive import biliLiveLinkServerAPI
from .core.web import updateAPI
from .core.web import webTool
if platform.system() == 'Windows':
    from .nativeGUI import multiLoginUIAPI
    from .libBooter import libEXEModelAPI
    from .libBooter import libWQEXEModelAPI
    from .libBooter import libCWCBEXEModelAPI
    from .nativeGUI import nativeWinUIAPI
    from .nativeGUI import webviewUIAPI
from . import userModule
