# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/webUI/authAPI.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   WebUI 本机密码存储与迁移
'''

import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path


def private_path(path):
    """POSIX 文件权限；Windows 使用仅当前用户可访问的受保护 DACL。"""
    if os.name != 'nt':
        os.chmod(path, 0o600)
        return
    import win32api
    import win32con
    import win32security
    import pywintypes

    try:
        token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
        try:
            sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
        finally:
            token.Close()
        acl = win32security.ACL()
        acl.AddAccessAllowedAce(win32security.ACL_REVISION, win32con.GENERIC_ALL, sid)
        win32security.SetNamedSecurityInfo(
            str(path), win32security.SE_FILE_OBJECT,
            win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
            None, None, acl, None,
        )
    except pywintypes.error:
        raise OSError('无法为 WebUI 认证文件设置当前用户专用权限') from None


@contextmanager
def credential_lock(path):
    """串行化启动迁移和离线重置，锁文件不保存凭据。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path) + '.lock', os.O_RDWR | os.O_CREAT, 0o600)
    locked = False
    try:
        private_path(str(path) + '.lock')
        if os.fstat(descriptor).st_size == 0:
            os.write(descriptor, b'\0')
        deadline = time.monotonic() + 5
        while not locked:
            try:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except OSError:
                if time.monotonic() >= deadline:
                    raise OSError('WebUI 正在进行其他本机操作或实例仍在运行，请稍后重试') from None
                time.sleep(0.05)
        yield
    finally:
        if locked:
            if os.name == 'nt':
                import msvcrt
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def password_record(password):
    if not isinstance(password, str) or not password or len(password.encode('utf-8')) > 1024:
        raise ValueError('密码不能为空，且 UTF-8 长度不能超过 1024 字节')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1, dklen=32)
    return {'version': 1, 'algorithm': 'scrypt', 'n': 16384, 'r': 8, 'p': 1,
            'salt': salt.hex(), 'hash': digest.hex(), 'revision': secrets.token_hex(16)}


def validate_record(record):
    try:
        if (not isinstance(record, dict) or record.get('version') != 1 or record.get('algorithm') != 'scrypt'
                or any(type(record.get(key)) is not int or record[key] != value
                       for key, value in (('n', 16384), ('r', 8), ('p', 1)))
                or any(not isinstance(record.get(key), str) or len(bytes.fromhex(record[key])) != length
                       for key, length in (('salt', 16), ('hash', 32), ('revision', 16)))):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError('WebUI 认证文件格式无效，请从本机重置密码') from None
    return record


def verify(password, record):
    validate_record(record)
    if not isinstance(password, str) or not password or len(password.encode('utf-8')) > 1024:
        return False
    digest = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(record['salt']),
                            n=record['n'], r=record['r'], p=record['p'], dklen=32)
    return hmac.compare_digest(digest, bytes.fromhex(record['hash']))


def auth_path(root, config):
    return Path(root) / config.get('auth_path', './conf/webui_auth.json')


def read_record(path):
    try:
        with Path(path).open('r', encoding='utf-8') as source:
            return validate_record(json.loads(source.read(8193)))
    except (ValueError, UnicodeError):
        raise ValueError('WebUI 认证文件损坏，请从本机重置密码') from None


def write_record(path, record):
    validate_record(record)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.webui-auth-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            private_path(temporary)
            json.dump(record, output, ensure_ascii=False, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        if read_record(temporary) != record:
            raise OSError('WebUI 认证文件写入校验失败')
        os.replace(temporary, path)
        if os.name != 'nt':
            directory = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def interactive_output():
    return bool(sys.stdin and sys.stdout and sys.stdin.isatty() and sys.stdout.isatty())


def windows_desktop_available():
    """只在可见的 Windows 窗口站显示本机密码，不向后台服务弹窗。"""
    if os.name != 'nt':
        return False
    import ctypes
    from ctypes import wintypes

    class UserObjectFlags(ctypes.Structure):
        _fields_ = [('inherit', wintypes.BOOL), ('reserved', wintypes.BOOL), ('flags', wintypes.DWORD)]

    user32 = ctypes.windll.user32
    user32.GetProcessWindowStation.restype = wintypes.HANDLE
    user32.GetUserObjectInformationW.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
    ]
    flags = UserObjectFlags()
    required = wintypes.DWORD()
    station = user32.GetProcessWindowStation()
    return bool(station and user32.GetUserObjectInformationW(
        station, 1, ctypes.byref(flags), ctypes.sizeof(flags), ctypes.byref(required),
    ) and flags.flags & 1)


def show_password_dialog(password, migrated=False):
    """本机一次性窗口；密码可选中或点击复制，不经过日志和网页。"""
    import tkinter
    from tkinter import ttk

    window = None
    try:
        window = tkinter.Tk()
        window.title('OlivOS WebUI 密码（仅显示一次）')
        window.resizable(False, False)
        panel = ttk.Frame(window, padding=20)
        panel.grid(sticky='nsew')
        heading = 'WebUI 旧令牌已迁移，原令牌仍是登录密码。' if migrated else 'WebUI 初始密码已生成。'
        ttk.Label(panel, text=heading).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 12))
        ttk.Label(panel, text='当前 WebUI 密码：').grid(row=1, column=0, columnspan=2, sticky='w')
        value = tkinter.StringVar(window, value=password)
        entry = ttk.Entry(panel, textvariable=value, state='readonly', width=52)
        entry.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(4, 12))
        status = tkinter.StringVar(window, value='请妥善保存；关闭后如忘记，可从本机托盘或终端重置。')
        ttk.Label(panel, textvariable=status, wraplength=440).grid(
            row=3, column=0, columnspan=2, sticky='w', pady=(0, 12),
        )

        def copy_password():
            try:
                window.clipboard_clear()
                window.clipboard_append(password)
                window.update_idletasks()
                status.set('密码已复制，请勿粘贴到群聊、日志或其他公开位置。')
            except tkinter.TclError:
                status.set('复制失败，请在上方输入框中选中密码并手动复制。')

        ttk.Button(panel, text='复制密码', command=copy_password).grid(row=4, column=0, sticky='w')
        ttk.Button(panel, text='关闭', command=window.destroy).grid(row=4, column=1, sticky='e')
        window.protocol('WM_DELETE_WINDOW', window.destroy)
        window.mainloop()
        return True
    except tkinter.TclError:
        raise OSError('无法显示 WebUI 密码，请从本机重置密码') from None
    finally:
        if window is not None:
            try:
                window.destroy()
            except tkinter.TclError:
                pass


def display_password(password, migrated=False):
    # 只显示在本机交互界面，不进入日志队列、文件或重定向的 stdout。
    message = ('WebUI 旧令牌已迁移。' if migrated else 'WebUI 初始密码已生成。') + '\n当前 WebUI 密码：' + password
    if windows_desktop_available():
        # 源码和编译版均通过本机弹窗展示，托盘终端只显示普通日志。
        return show_password_dialog(password, migrated=migrated)
    if interactive_output():
        print(message, flush=True)
        return True
    return False


def initialize(root, config):
    path = auth_path(root, config)
    legacy = Path(root) / config.get('token_path', './conf/webui_token.txt')
    if path.resolve() == legacy.resolve():
        raise ValueError('WebUI 新认证文件不能与旧令牌文件使用同一路径')
    with credential_lock(path):
        if path.exists():
            record = read_record(path)
            # 恢复「新文件已落盘、旧文件尚未删除」之间被中断的迁移；新文件始终是认证真源。
            if legacy.exists():
                password = legacy.read_text(encoding='utf-8').strip()
                if verify(password, record):
                    display_password(password, migrated=True)
                    legacy.unlink()
            return record
        if legacy.exists():
            password = legacy.read_text(encoding='utf-8').strip()
            record = password_record(password)
            write_record(path, record)
            if not verify(password, read_record(path)):
                raise OSError('WebUI 密码迁移校验失败')
            display_password(password, migrated=True)
            legacy.unlink()
            return record
        # 后台实例不能把新生成的密码写进服务日志。
        can_display = windows_desktop_available() or interactive_output()
        if not can_display:
            raise ValueError('尚未设置 WebUI 密码，请在实例目录执行 --reset-webui-password 后再启用 WebUI')
        password = secrets.token_urlsafe(24)
        record = password_record(password)
        write_record(path, record)
        display_password(password)
        return record


def reset_offline(root, config, record):
    path = auth_path(root, config)
    legacy = Path(root) / config.get('token_path', './conf/webui_token.txt')
    if path.resolve() == legacy.resolve():
        raise ValueError('WebUI 新认证文件不能与旧令牌文件使用同一路径')
    with credential_lock(path):
        write_record(path, record)
        if legacy.exists():
            legacy.unlink()


def set_local_password(root, record):
    from . import localAPI, serverAPI

    root = Path(root).resolve()
    config, _ = serverAPI.load_local_config(root, strict=True)
    try:
        localAPI.request(root, {'action': 'reset', 'record': record})
    except FileNotFoundError:
        # 运行期锁覆盖整个服务生命周期，不能因管理入口/监听元数据缺失而误判为离线。
        with credential_lock(root / 'data/webui/manager'):
            if serverAPI.active_listener(root) is not None:
                raise OSError('WebUI 正在运行但无法连接本机管理入口，未修改密码') from None
            reset_offline(root, config, record)
        return False
    return True


def reset_command(root=None):
    """本机交互命令；在线走权限受限的 IPC，离线仅更新当前实例文件。"""
    root = Path(root or os.getcwd()).resolve()
    if not sys.stdin or not sys.stdin.isatty():
        raise ValueError('请在本机交互式终端运行密码重置命令')
    password = getpass.getpass('请输入新 WebUI 密码：')
    if password != getpass.getpass('请再次输入：'):
        raise ValueError('两次输入的密码不一致，未修改密码')
    record = password_record(password)
    del password
    online = set_local_password(root, record)
    print('WebUI 密码已更新，原有登录已失效，无需重启 OlivOS。' if online else 'WebUI 密码已更新，下次启动生效。')
