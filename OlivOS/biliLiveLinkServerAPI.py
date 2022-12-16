# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/biliLiveLinkServerAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import OlivOS

import asyncio
from aiohttp.client import ClientSession
from aiohttp import cookiejar

class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval = 0.001, dead_interval = 1, rx_queue = None, tx_queue = None, logger_proc = None, debug_mode = False, bot_info_dict = None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name = Proc_name,
            Proc_type = 'biliLive_link',
            scan_interval = scan_interval,
            dead_interval = dead_interval,
            rx_queue = rx_queue,
            tx_queue = tx_queue,
            logger_proc = logger_proc
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['platform_bot_info_dict'] = None

    def run(self):
        asyncio.run(start(int(self.Proc_data['bot_info_dict'].post_info.access_token), self))

async def start(room: int, Proc):
    async with ClientSession(cookie_jar = cookiejar.CookieJar()) as session:
        bot = OlivOS.biliLiveSDK.BiliLiveBot(
            room_id = room,
            uid = 0,
            session = session,
            loop = session._loop,
            Proc = Proc
        )
        await bot.init_room()
        bot.start()
        while True:
            await asyncio.sleep(60)
        bot.close()
