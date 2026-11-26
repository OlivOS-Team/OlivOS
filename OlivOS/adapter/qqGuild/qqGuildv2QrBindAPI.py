# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/adapter/qqGuild/qqGuildv2QrBindAPI.py
@Author    :   OlivOS-Team
@Contact   :   https://github.com/OlivOS-Team/OlivOS
@License   :   AGPL
@Copyright :   (C) 2026, OlivOS-Team
@Desc      :   QQ 官方机器人扫码绑定；不保存账号，不记录凭据。
'''

import base64
import io
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import IntEnum
from urllib.parse import quote

import requests

from OlivOS.core.info.infoAPI import OlivOS_Header_UA


class QrBindStatus(IntEnum):
    NONE = 0
    PENDING = 1
    COMPLETED = 2
    EXPIRED = 3


_STATUS_TEXT = {
    QrBindStatus.NONE: '尚未绑定', QrBindStatus.PENDING: '请使用手机 QQ 扫码并确认绑定',
    QrBindStatus.COMPLETED: '绑定成功', QrBindStatus.EXPIRED: '扫码会话已过期或已取消',
}
_QQ_API = 'https://q.qq.com/lite/'
_CONNECT_URL = 'https://q.qq.com/qqbot/openclaw/connect.html'


class QrBindError(Exception):
    """只携带可供界面展示的消息，不附加 QQ 原文或请求参数。"""

    def __init__(self, message, http_status=502):
        super().__init__(message)
        self.http_status = http_status


@dataclass(repr=False, eq=False)
class QrBindSession:
    bind_id: str
    aes_key_bytes: bytearray
    created_at: float
    expires_at: float
    task_id: str = ''
    qr_url: str = ''
    consumed: bool = False
    poll_lock: threading.Lock = field(default_factory=threading.Lock)


class _SecretFields(dict):
    def __repr__(self):
        return '<已隐藏凭据>'


def _result(status):
    return {'status': int(status), 'status_text': _STATUS_TEXT[status]}


def _post(endpoint, payload):
    try:
        response = requests.post(
            _QQ_API + endpoint, json=payload, timeout=10,
            headers={'Accept': 'application/json', 'Content-Type': 'application/json', 'User-Agent': OlivOS_Header_UA},
            allow_redirects=False,
        )
        if response.status_code == 200:
            body = response.json()
            if (isinstance(body, dict) and type(body.get('retcode')) is int and body['retcode'] == 0
                    and isinstance(body.get('data'), dict)):
                return body['data']
    except requests.Timeout:
        error = QrBindError('QQ 扫码服务请求超时，请稍后重试', 504)
    except (requests.RequestException, ValueError):
        error = QrBindError('QQ 扫码服务请求失败，请稍后重试')
    else:
        error = QrBindError('QQ 扫码服务返回异常，请刷新二维码')
    raise error


def _decrypt_secret(encrypted, cipher):
    from cryptography.exceptions import InvalidTag

    try:
        raw = base64.b64decode(encrypted, validate=True)
        if len(raw) > 12 + 16:
            return cipher.decrypt(raw[:12], raw[12:], None).decode('utf-8')
    except (ValueError, InvalidTag):
        pass
    raise QrBindError('无法解密 QQ 返回的机器人凭据，请刷新二维码')


def _credentials(data, cipher):
    rows = data.get('credentials', [data])
    if not isinstance(rows, list) or not rows:
        raise QrBindError('QQ 未返回机器人凭据，请刷新二维码')
    credentials = []
    for row in rows:
        if not isinstance(row, dict):
            raise QrBindError('QQ 返回的机器人凭据格式不正确，请刷新二维码')
        app_id = row.get('bot_appid')
        encrypted = row.get('bot_encrypt_secret')
        openid = row.get('user_openid', data.get('user_openid', ''))
        if (type(app_id) not in (str, int) or str(app_id).strip() in ('', '0')
                or not isinstance(encrypted, str) or not isinstance(openid, str)):
            raise QrBindError('QQ 返回的机器人凭据不完整，请刷新二维码')
        credentials.append(_SecretFields(app_id=str(app_id), app_secret=_decrypt_secret(encrypted, cipher),
                                         user_openid=openid))
    return credentials


class QrBindManager:
    def __init__(self, *, ttl=300, max_sessions=16):
        self._ttl = ttl
        self._max_sessions = max_sessions
        self._changed = threading.Condition(threading.Lock())
        self._sessions = {}
        # 即使在途建单已被取消或超时，直到 HTTP 调用结束前仍占用名额。
        self._creating = set()
        self._cleaner = None
        self._closed = False

    def _discard_locked(self, session):
        self._sessions.pop(session.bind_id)
        session.aes_key_bytes[:] = b'\x00' * len(session.aes_key_bytes)
        self._changed.notify_all()

    def _lookup_locked(self, bind_id):
        session = self._sessions.get(bind_id)
        if session is not None and time.monotonic() >= session.expires_at:
            self._discard_locked(session)
            return None
        return session

    def _cleanup(self):
        # 只在有会话时运行；即使两个 UI 都停止轮询，也会在截止时间擦除密钥。
        with self._changed:
            while self._sessions:
                first = min(self._sessions.values(), key=lambda session: session.expires_at)
                remaining = first.expires_at - time.monotonic()
                if remaining > 0:
                    self._changed.wait(remaining)
                else:
                    self._discard_locked(first)
            self._cleaner = None

    def create_session(self, source=''):
        try:
            source_query = '&source=' + quote(source, safe='') if source else ''
        except (TypeError, UnicodeError):
            raise QrBindError('扫码来源标识无效', 400) from None
        with self._changed:
            if self._closed:
                raise QrBindError('扫码绑定服务已关闭', 503)
            for bind_id in tuple(self._sessions):
                self._lookup_locked(bind_id)
            if len(self._sessions.keys() | self._creating) >= self._max_sessions:
                raise QrBindError('当前扫码会话过多，请稍后重试', 429)
            if self._cleaner is None:
                cleaner = threading.Thread(target=self._cleanup, name='qqGuildQrBindCleanup', daemon=True)
                try:
                    cleaner.start()
                except RuntimeError:
                    raise QrBindError('无法启动扫码会话清理服务', 503) from None
                self._cleaner = cleaner
            now = time.monotonic()
            bind_id = secrets.token_urlsafe(24)
            session = QrBindSession(bind_id, bytearray(os.urandom(32)), now, now + self._ttl)
            encoded_key = base64.b64encode(session.aes_key_bytes).decode('ascii')
            self._sessions[bind_id] = session
            self._creating.add(bind_id)
            self._changed.notify_all()
        try:
            data = _post('create_bind_task', {'key': encoded_key})
            task_id = data.get('task_id')
            if not isinstance(task_id, str) or not task_id.strip():
                raise QrBindError('QQ 未返回有效的扫码任务，请重试')
            try:
                qr_url = '%s?task_id=%s&_wv=2%s' % (_CONNECT_URL, quote(task_id, safe=''), source_query)
            except UnicodeError:
                raise QrBindError('QQ 未返回有效的扫码任务，请重试') from None
            with self._changed:
                if self._lookup_locked(bind_id) is not session:
                    raise QrBindError(_STATUS_TEXT[QrBindStatus.EXPIRED], 410)
                session.created_at = time.monotonic()
                session.expires_at = session.created_at + self._ttl
                session.task_id, session.qr_url = task_id, qr_url
                return {'bind_id': bind_id, 'qr_url': qr_url, 'expires_in': self._ttl, 'poll_interval': 2}
        finally:
            with self._changed:
                self._creating.discard(bind_id)
                if not session.task_id and self._sessions.get(bind_id) is session:
                    self._discard_locked(session)

    def poll_session(self, bind_id):
        with self._changed:
            session = self._lookup_locked(bind_id)
            if session is None or not session.task_id:
                return _result(QrBindStatus.EXPIRED)
        # 同一个会话最多有一次在途轮询；取消、到期和其他会话不等它的网络或解密。
        with session.poll_lock:
            with self._changed:
                if self._lookup_locked(bind_id) is not session:
                    return _result(QrBindStatus.EXPIRED)
            status = None
            try:
                data = _post('poll_bind_result', {'task_id': session.task_id})
                if type(data.get('status')) is not int or data['status'] not in _STATUS_TEXT:
                    raise QrBindError('QQ 返回的扫码状态无效，请刷新二维码')
                status = QrBindStatus(data['status'])
                if status == QrBindStatus.COMPLETED:
                    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

                    with self._changed:
                        if self._lookup_locked(bind_id) is not session:
                            return _result(QrBindStatus.EXPIRED)
                        cipher = AESGCM(bytes(session.aes_key_bytes))
                    credentials = _credentials(data, cipher)
            except QrBindError:
                with self._changed:
                    if self._lookup_locked(bind_id) is not session:
                        return _result(QrBindStatus.EXPIRED)
                    if status == QrBindStatus.COMPLETED:
                        self._discard_locked(session)
                raise
            with self._changed:
                if self._lookup_locked(bind_id) is not session:
                    return _result(QrBindStatus.EXPIRED)
                result = _result(status)
                if status == QrBindStatus.COMPLETED:
                    session.consumed = True
                    result['credentials'] = credentials
                if status in (QrBindStatus.COMPLETED, QrBindStatus.EXPIRED):
                    self._discard_locked(session)
                return result

    def get_qr_png(self, bind_id):
        import qrcode
        from qrcode.exceptions import DataOverflowError

        with self._changed:
            session = self._lookup_locked(bind_id)
            if session is None or not session.qr_url:
                raise KeyError(_STATUS_TEXT[QrBindStatus.EXPIRED])
        try:
            with io.BytesIO() as buffer:
                qrcode.make(session.qr_url).save(buffer, format='PNG')
                png = buffer.getvalue()
        except (DataOverflowError, ValueError, OSError):
            raise QrBindError('无法生成扫码图片，请刷新二维码') from None
        with self._changed:
            if self._lookup_locked(bind_id) is not session:
                raise KeyError(_STATUS_TEXT[QrBindStatus.EXPIRED])
        return png

    def cancel_session(self, bind_id):
        with self._changed:
            session = self._sessions.get(bind_id)
            if session is not None:
                self._discard_locked(session)

    def cancel_all(self):
        with self._changed:
            for session in tuple(self._sessions.values()):
                self._discard_locked(session)

    def close(self):
        with self._changed:
            self._closed = True
            self._creating.clear()
            for session in tuple(self._sessions.values()):
                self._discard_locked(session)
            cleaner = self._cleaner
        if cleaner is not None:
            cleaner.join()


def is_qr_bind_supported(sdk_type, platform_type):
    return sdk_type == 'qqGuildv2_link' and platform_type == 'qqGuild'


def build_qqguild_v2_ws_account(app_id, app_secret):
    return {
        'id': app_id, 'enable': True, 'password': '',
        'sdk_type': 'qqGuildv2_link', 'platform_type': 'qqGuild', 'model_type': 'public',
        'server': _SecretFields(auto=True, type='websocket', host='', port=0, access_token=app_secret),
        'extends': {}, 'debug': False,
    }
