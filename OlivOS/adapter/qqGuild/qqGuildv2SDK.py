# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqGuildv2SDK.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   qqGuildv2 对外入口，保持原有 OlivOS.qqGuildv2SDK.* 调用兼容
'''

from .qqGuildv2SDKCommon import *  # noqa: F401,F403
from .qqGuildv2SDKCommon import API_common
from .qqGuildv2SDKCommon import event_action_common
from .qqGuildv2SDKGroup import API_group
from .qqGuildv2SDKGroup import event_action_group
from .qqGuildv2SDKGuild import API_guild
from .qqGuildv2SDKGuild import event_action_guild
from .qqGuildv2SDKGuildPrivate import API_guild_private
from .qqGuildv2SDKGuildPrivate import event_action_guild_private
from .qqGuildv2SDKPrivate import API_private
from .qqGuildv2SDKPrivate import event_action_private
from . import qqGuildv2SDKCommon
from . import qqGuildv2SDKGroup
from . import qqGuildv2SDKGuild
from . import qqGuildv2SDKGuildPrivate
from . import qqGuildv2SDKPrivate


class event_action(
    event_action_common,
    event_action_guild,
    event_action_guild_private,
    event_action_group,
    event_action_private
):
    pass


class API(
    API_common,
    API_guild,
    API_guild_private,
    API_group,
    API_private
):
    pass


def _bind_runtime_symbols():
    for module in [
        qqGuildv2SDKCommon,
        qqGuildv2SDKGuild,
        qqGuildv2SDKGuildPrivate,
        qqGuildv2SDKGroup,
        qqGuildv2SDKPrivate
    ]:
        module.event_action = event_action
        module.API = API


_bind_runtime_symbols()
