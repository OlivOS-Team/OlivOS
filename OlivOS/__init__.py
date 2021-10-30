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

import OlivOS.infoAPI
import OlivOS.data
import OlivOS.contentAPI
import OlivOS.messageAPI
import OlivOS.metadataAPI
import OlivOS.API
import OlivOS.accountAPI
import OlivOS.diagnoseAPI
import OlivOS.flaskServerAPI
import OlivOS.pluginAPI
import OlivOS.onebotSDK
import OlivOS.telegramSDK
import OlivOS.telegramPollServerAPI
import OlivOS.dodobotEAServerAPI
import OlivOS.dodobotEATXAPI
import OlivOS.dodobotEASDK
if(platform.system() == 'Windows'):
    import OlivOS.multiLoginUIAPI
    import OlivOS.libEXEModelAPI
