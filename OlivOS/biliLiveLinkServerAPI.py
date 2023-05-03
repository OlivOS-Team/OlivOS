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
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import OlivOS

import asyncio
from aiohttp.client import ClientSession
from aiohttp import cookiejar
import qrcode
import time
import os
import traceback


class server(OlivOS.API.Proc_templet):
    def __init__(self, Proc_name, scan_interval=0.001, dead_interval=1, rx_queue=None, tx_queue=None, logger_proc=None,
                 control_queue=None, debug_mode=False, bot_info_dict=None):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='biliLive_link',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=rx_queue,
            tx_queue=tx_queue,
            logger_proc=logger_proc,
            control_queue=control_queue
        )
        self.Proc_config['debug_mode'] = debug_mode
        self.Proc_data['bot_info_dict'] = bot_info_dict
        self.Proc_data['platform_bot_info_dict'] = None

    def run(self):
        self.log(2, 'OlivOS biliLive Link server [' + self.Proc_name + '] is running')
        while True:
            try:
                asyncio.run(start(int(self.Proc_data['bot_info_dict'].post_info.access_token), self))
            except:
                self.log(2, 'OlivOS biliLive Link server [' + self.Proc_name + '] link lost')
            time.sleep(5)


async def start(room: int, Proc: server):
    cookie = cookiejar.CookieJar()
    async with ClientSession(cookie_jar=cookie) as session:
        if Proc.Proc_data['bot_info_dict'].platform['model'] == 'login':
            isLoop = True
            conf_dir_path = './conf/biliLive/' + Proc.Proc_data['bot_info_dict'].hash
            cookie_new = {}
            # cookie_new = OlivOS.biliLiveSDK.load_cookies(conf_dir_path + '/cookies.json')
            while isLoop:
                try:
                    if 'bili_jct' in cookie_new and 'DedeUserID' in cookie_new:
                        session.cookie_jar.update_cookies(cookies=cookie_new)
                        # 此处需要一个判断cookies有效的接口
                        isLoop = False
                    else:
                        res = await OlivOS.biliLiveSDK.aiohttpGet(session, OlivOS.biliLiveSDK.QRCODE_REQUEST_URL)
                        ts = res['ts']
                        outdated = ts + 180 * 1000  # 180 秒後逾時
                        authKey = res['data']['oauthKey']
                        url = res['data']['url']
                        qr = qrcode.QRCode()
                        qr.add_data(url)
                        try:
                            qr.print_ascii(invert=True)
                        except:
                            pass
                        releaseDir('./conf/')
                        releaseDir('./conf/biliLive')
                        releaseDir(conf_dir_path)
                        qr.make_image().save(conf_dir_path + '/qrcode.png')
                        OlivOS.biliLiveSDK.send_QRCode_event(
                            Proc.Proc_data['bot_info_dict'].hash,
                            os.path.abspath(conf_dir_path + '/qrcode.png'),
                            Proc.Proc_info.control_queue
                        )
                        # os.startfile(os.path.abspath('./conf/biliLive/' + Proc.Proc_data['bot_info_dict'].hash + '/qrcode.png')) # Linux方案: subprocess.call(["xdg-open",file_path])
                        while True:
                            await asyncio.sleep(5)
                            if time.time() > outdated:
                                Proc.log(2, 'OlivOS biliLive Link server [' + Proc.Proc_name + '] login out of time')
                                break  # 登入失敗
                            res = await OlivOS.biliLiveSDK.aiohttpPost(
                                session,
                                OlivOS.biliLiveSDK.CHECK_LOGIN_RESULT,
                                oauthKey=authKey
                            )
                            if res['status']:
                                isLoop = False
                                OlivOS.biliLiveSDK.save_cookies(cookie, conf_dir_path + '/cookies.json')
                                break
                            else:
                                code = res['data']
                                if code in [-1, -2]:
                                    Proc.log(2, 'OlivOS biliLive Link server [' + Proc.Proc_name + '] login failed')
                                    break
                except Exception as e:
                    Proc.log(2, 'OlivOS biliLive Link server [' + Proc.Proc_name + '] login error')
                    traceback.print_exc()
            Proc.log(2, 'OlivOS biliLive Link server [' + Proc.Proc_name + '] login succeed')
        bot = OlivOS.biliLiveSDK.BiliLiveBot(
            room_id=room,
            uid=0,
            session=session,
            loop=session._loop,
            Proc=Proc
        )
        await bot.init_room()
        bot.start()
        Proc.log(2, 'OlivOS biliLive Link server [' + Proc.Proc_name + '] link start')
        while True:
            if Proc.Proc_info.rx_queue.empty():
                await asyncio.sleep(0.01)
            else:
                try:
                    rx_packet_data = Proc.Proc_info.rx_queue.get(block=False)
                except:
                    rx_packet_data = None
                if rx_packet_data is not None:
                    if 'data' in rx_packet_data.key and 'action' in rx_packet_data.key['data']:
                        if 'send' == rx_packet_data.key['data']['action']:
                            if 'data' in rx_packet_data.key['data']:
                                # Proc.Proc_data['extend_data']['ws_obj'].send(rx_packet_data.key['data']['data'])
                                if type(rx_packet_data.key['data']['data']) == dict:
                                    tmp_data = rx_packet_data.key['data']['data']
                                    tmp_data['roomid'] = room
                                    token = OlivOS.biliLiveSDK.get_cookies(cookie, 'bili_jct')
                                    if 'msg' in tmp_data:
                                        tmp_msg = tmp_data['msg']
                                        flag_msg_loop = True
                                        flag_continue = False
                                        while flag_msg_loop or not flag_continue:
                                            if not flag_continue:
                                                if len(tmp_msg) > 20:
                                                    flag_msg_loop = True
                                                    tmp_data['msg'] = tmp_msg[:20]
                                                    tmp_msg = tmp_msg[20:]
                                                else:
                                                    flag_msg_loop = False
                                                    tmp_data['msg'] = tmp_msg
                                            flag_continue = False
                                            try:
                                                await OlivOS.biliLiveSDK.aiohttpPost(session,
                                                                                     OlivOS.biliLiveSDK.SEND_URL,
                                                                                     rnd=time.time(),
                                                                                     csrf=token,
                                                                                     csrf_token=token,
                                                                                     **tmp_data
                                                                                     )
                                            except Exception as e:
                                                flag_continue = True
                                            if flag_msg_loop:
                                                await asyncio.sleep(1)
        bot.close()


def releaseDir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
