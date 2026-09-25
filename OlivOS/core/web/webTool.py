# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/webTool.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

import urllib
import platform
if platform.system() == 'Windows':
    import winreg

# 出站 HTTP 请求的默认超时,格式为 (connect, read) 秒。
# requests 的 timeout 默认是 None,即「一直等」:连上之后对端不响应、或响应体
# 传到一半卡住,都会永久阻塞。OlivOS 的 link 进程与 webhook 服务普遍基于 gevent
# 且未 monkey patch,一次挂起会冻结整个进程(webhook 侧还会连带拖过开放平台
# 3 秒 ACK 期限),因此所有出站调用都必须显式带上超时。
OlivOS_http_timeout = (5.0, 20.0)
# 上传/下载等涉及较大响应体的请求,给更宽的读超时
OlivOS_http_timeout_transfer = (5.0, 60.0)


def get_system_proxy():
    res = None
    if False and platform.system() == 'Windows':
        __path = r'Software\Microsoft\Windows\CurrentVersion\Internet Settings'
        __INTERNET_SETTINGS = winreg.OpenKeyEx(
            winreg.HKEY_CURRENT_USER,
            __path,
            0,
            winreg.KEY_ALL_ACCESS
        )
        res_data = winreg.QueryValueEx(__INTERNET_SETTINGS, "ProxyServer")
        if len(res_data) > 0 and res_data[0] != '':
            res = {
                'http': res_data[0],
                'https': res_data[0]
            }
    else:
        res = urllib.request.getproxies()
        for res_this in res:
            res[res_this] = res[res_this].lstrip('%s://' % res_this)
    return res


def get_system_proxy_tuple(proxy_type='http'):
    res = (None, None, None)
    res_data = get_system_proxy()
    if res_data is not None:
        if proxy_type in res_data:
            res_data_1 = res_data[proxy_type].lstrip('%s://' % proxy_type).split(':')
            if len(res_data_1) == 2:
                res = (res_data_1[0], res_data_1[1], proxy_type)
    return res
