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
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

# here put the import lib

import platform

from . import infoAPI
from . import bootAPI
from . import bootDataAPI
from . import data
from . import hook
from . import contentAPI
from . import messageAPI
from . import metadataAPI
from . import API
from . import accountAPI
from . import diagnoseAPI
from . import flaskServerAPI
from . import pluginAPI
from . import onebotSDK
from . import qqGuildSDK
from . import qqGuildLinkServerAPI
from . import telegramSDK
from . import telegramPollServerAPI
from . import dodobotEAServerAPI
from . import dodobotEATXAPI
from . import dodobotEASDK
from . import dodoSDK
from . import dodoPollServerAPI
from . import dodoLinkSDK
from . import dodoLinkServerAPI
from . import fanbookSDK
from . import fanbookPollServerAPI
from . import kaiheilaSDK
from . import kaiheilaLinkServerAPI
if(platform.system() == 'Windows'):
    from . import multiLoginUIAPI
    from . import libEXEModelAPI
    from . import nativeWinUIAPI
