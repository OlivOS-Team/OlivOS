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
from urllib.parse import quote, unquote, urlparse, urlunparse
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


def normalize_access_token(token):
    """把账号 TOKEN 收成非空字符串；空值表示未配置鉴权。"""
    if token is None:
        return None
    token = str(token)
    return token if token else None


def access_token_headers(token):
    """OneBot / Milky 的 Authorization: Bearer 头，TOKEN 按原文写入。"""
    token = normalize_access_token(token)
    if not token:
        return {}
    return {'Authorization': 'Bearer %s' % token}


def access_token_from_query(query):
    """从 query 取出 access_token。用 unquote，避免把 TOKEN 里的 + 当成空格。"""
    if not query:
        return None
    for item in query.split('&'):
        if not item or '=' not in item:
            continue
        key, value = item.split('=', 1)
        if unquote(key) == 'access_token':
            token = unquote(value)
            return token if token else None
    return None


def access_token_from_url(url):
    if not url:
        return None
    return access_token_from_query(urlparse(str(url)).query)


def append_access_token_query(url, token):
    """把 TOKEN 以百分号编码写入 access_token 查询参数，已有同名参数则覆盖。"""
    token = normalize_access_token(token)
    if not token or not url:
        return url
    parsed = urlparse(url)
    parts = []
    found = False
    if parsed.query:
        for item in parsed.query.split('&'):
            if not item:
                continue
            key = unquote(item.split('=', 1)[0])
            if key == 'access_token':
                if found:
                    continue
                parts.append('access_token=%s' % quote(token, safe=''))
                found = True
            else:
                parts.append(item)
    if not found:
        parts.append('access_token=%s' % quote(token, safe=''))
    return urlunparse(parsed._replace(query='&'.join(parts)))


def _header_value(headers, name):
    if headers is None:
        return None
    getter = getattr(headers, 'get', None)
    if getter is not None:
        value = getter(name)
        if value:
            return value
        value = getter(name.lower())
        if value:
            return value
    items = getattr(headers, 'items', None)
    if items is None:
        return None
    target = name.lower()
    for key, value in items():
        if str(key).lower() == target:
            return value
    return None


def access_token_matches(expected, headers=None, url=''):
    """校验请求头或 query 中的 TOKEN，兼容 Bearer、原文和百分号编码。"""
    expected = normalize_access_token(expected)
    if not expected:
        return True
    provided = []
    auth = _header_value(headers, 'Authorization')
    if auth:
        auth = str(auth).strip()
        provided.append(auth)
        if auth.lower().startswith('bearer '):
            provided.append(auth[7:].strip())
    from_url = access_token_from_url(url)
    if from_url:
        provided.append(from_url)
    decoded = []
    for item in provided:
        value = unquote(item)
        if value != item:
            decoded.append(value)
    return expected in provided + decoded


def get_system_proxy_tuple(proxy_type='http'):
    res = (None, None, None)
    res_data = get_system_proxy()
    if res_data is not None:
        if proxy_type in res_data:
            res_data_1 = res_data[proxy_type].lstrip('%s://' % proxy_type).split(':')
            if len(res_data_1) == 2:
                res = (res_data_1[0], res_data_1[1], proxy_type)
    return res
