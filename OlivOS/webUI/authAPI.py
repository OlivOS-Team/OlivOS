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

import gc
import getpass
import hashlib
import hmac
import json
import os
import secrets
import stat
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path

PASSWORD_MIN_LENGTH = 8


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


def password_validation_error(password, confirmation):
    """返回新密码输入的校验提示；None 表示可以提交。"""
    if len(password) < PASSWORD_MIN_LENGTH:
        return '密码至少需要 %d 个字符。' % PASSWORD_MIN_LENGTH
    if password != confirmation:
        return '两次输入的密码不一致。'
    return None


def password_record(password, enforce_strength=True):
    if not isinstance(password, str) or not password or len(password.encode('utf-8')) > 1024:
        raise ValueError('密码不能为空，且 UTF-8 长度不能超过 1024 字节')
    if enforce_strength and len(password) < PASSWORD_MIN_LENGTH:
        # 登录限流是每来源每分钟 10 次，过短的密码在这道限流面前等于没有强度。
        raise ValueError('密码至少需要 %d 个字符' % PASSWORD_MIN_LENGTH)
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


def secure_path(path):
    """读取前把认证文件权限收回当前用户；无法收紧时拒绝使用该文件。"""
    if os.name != 'nt':
        if stat.S_IMODE(os.stat(path).st_mode) & 0o077:
            os.chmod(path, 0o600)
            if stat.S_IMODE(os.stat(path).st_mode) & 0o077:
                raise OSError('WebUI 认证文件权限过宽且无法收紧，请从本机重置密码')
        return
    # Windows 上受保护 DACL 是幂等的；继承来的宽松 ACL 会在这一步被覆盖。
    private_path(path)


def read_record(path):
    try:
        secure_path(path)
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


def password_dialog_icon():
    """弹窗图标：优先当前工作目录，其次源码目录下的资源目录。"""
    candidates = [
        os.path.join('.', 'resource', 'tmp_favoricon.ico'),
        str(Path(__file__).resolve().parents[2] / 'resource' / 'tmp_favoricon.ico'),
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def show_password_dialog(password, migrated=False, on_ready=None):
    """本机一次性窗口；密码可选中或点击复制，不经过日志和网页。"""
    import tkinter

    # 与原生终端共用一套色板，避免系统默认灰色控件与主界面割裂。
    palette = {
        'bg': '#00A0EA', 'text': '#FFFFFF', 'hint': '#BBE9FF', 'field': '#FFFFFF', 'ink': '#000000',
        'primary': '#FFFFFF', 'primary_hover': '#BBE9FF',
        'secondary': '#40C3FF', 'secondary_hover': '#80D7FF',
    }
    dialog_width, dialog_height = 480, 258
    window = None
    try:
        window = tkinter.Tk()
        window.title('OlivOS WebUI 密码（仅显示一次）')
        window.resizable(False, False)
        window.configure(bg=palette['bg'])
        window.geometry('%dx%d+%d+%d' % (
            dialog_width, dialog_height,
            max(0, (window.winfo_screenwidth() - dialog_width) // 2),
            max(0, (window.winfo_screenheight() - dialog_height) // 3),
        ))
        icon = password_dialog_icon()
        if icon is not None:
            try:
                window.iconbitmap(icon)
            except tkinter.TclError:
                pass

        def place_label(text, x, y, size=432, height=18, font=('TkDefaultFont 10'), fg=None, variable=None):
            node = tkinter.Label(
                window, text=text, textvariable=variable, bg=palette['bg'],
                fg=fg or palette['text'], anchor='w', justify='left', font=font,
            )
            node.place(x=x, y=y, width=size, height=height)
            return node

        def place_button(text, command, x, y, size, primary):
            base = palette['primary'] if primary else palette['secondary']
            hover = palette['primary_hover'] if primary else palette['secondary_hover']
            node = tkinter.Button(
                window, text=text, command=command, bd=0, relief='flat', cursor='hand2',
                bg=base, fg=palette['bg'] if primary else palette['text'],
                activebackground=hover, activeforeground=palette['ink'],
                font=('TkDefaultFont 10'),
            )
            node.bind('<Enter>', lambda event: node.configure(bg=hover))
            node.bind('<Leave>', lambda event: node.configure(bg=base))
            node.place(x=x, y=y, width=size, height=38)
            return node

        heading = 'WebUI 旧令牌已迁移' if migrated else 'WebUI 初始密码已生成'
        subtitle = ('原令牌仍是登录密码，记录后可删除旧文件。' if migrated
                    else '这是唯一一次显示，关闭后无法再次查看。')
        place_label(heading, 24, 22, height=26, font=('TkDefaultFont 14 bold'))
        place_label(subtitle, 24, 52, fg=palette['hint'])
        place_label('当前 WebUI 密码', 24, 88, fg=palette['hint'])

        value = tkinter.StringVar(window, value=password)
        # 白色底框提供左右留白，输入框本身只读但仍可选中，方便手动复制或核对。
        field = tkinter.Frame(window, bg=palette['field'], bd=0, highlightthickness=0)
        field.place(x=24, y=108, width=432, height=44)
        entry = tkinter.Entry(
            field, textvariable=value, state='readonly', bd=0, highlightthickness=0,
            readonlybackground=palette['field'], fg=palette['ink'], font=('TkFixedFont 12'),
        )
        entry.place(x=12, y=5, width=408, height=34)

        status = tkinter.StringVar(window, value='请妥善保存；关闭后如忘记，可从本机托盘或终端重置。')
        place_label('', 24, 162, variable=status, fg=palette['hint'])

        def copy_password():
            try:
                window.clipboard_clear()
                window.clipboard_append(password)
                window.update_idletasks()
                status.set('密码已复制，请勿粘贴到群聊、日志或其他公开位置。')
            except tkinter.TclError:
                status.set('复制失败，请在上方输入框中选中密码并手动复制。')
            entry.selection_range(0, tkinter.END)
            entry.focus_set()

        place_button('复制密码', copy_password, 24, 194, 132, True)
        place_button('关闭', window.destroy, 346, 194, 110, False)
        window.bind('<Escape>', lambda event: window.destroy())
        window.protocol('WM_DELETE_WINDOW', window.destroy)
        window.update_idletasks()
        if on_ready:
            on_ready()
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


def start_password_dialog(password, migrated=False):
    """窗口在自己的线程创建和关闭；启动流程只等待窗口就绪，不等待用户操作。"""
    ready = threading.Event()
    failed = threading.Event()

    def display():
        try:
            show_password_dialog(password, migrated=migrated, on_ready=ready.set)
        except (OSError, RuntimeError):
            failed.set()
        finally:
            # Tk 控件和回调包含循环引用，必须在创建解释器的线程内完成回收。
            gc.collect()
            ready.set()

    worker = threading.Thread(target=display, name='WebUI-password-display', daemon=True)
    worker.start()
    if not ready.wait(5) or failed.is_set():
        raise OSError('无法显示 WebUI 密码，请从本机重置密码')
    return True


def display_password(password, migrated=False):
    # 只显示在本机交互界面，不进入日志队列、文件或重定向的 stdout。
    message = ('WebUI 旧令牌已迁移。' if migrated else 'WebUI 初始密码已生成。') + '\n当前 WebUI 密码：' + password
    if windows_desktop_available():
        # 源码和编译版均通过本机弹窗展示，托盘终端只显示普通日志。
        return start_password_dialog(password, migrated=migrated)
    if interactive_output():
        print(message, flush=True)
        return True
    return False


def display_once(password, migrated=False):
    """展示失败只返回 False，调用方据此决定旧令牌与本次生成的凭据能否删除。"""
    try:
        return display_password(password, migrated=migrated)
    except OSError:
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
                if verify(password, record) and display_once(password, migrated=True) is not False:
                    legacy.unlink()
            return record
        if legacy.exists():
            password = legacy.read_text(encoding='utf-8').strip()
            # 历史令牌可能很短，迁移必须原样接受，强度只约束新设置的密码。
            record = password_record(password, enforce_strength=False)
            write_record(path, record)
            if not verify(password, read_record(path)):
                raise OSError('WebUI 密码迁移校验失败')
            # 迁移后密码与原令牌一致：展示失败时保留旧令牌，它是该密码唯一可读的副本。
            if display_once(password, migrated=True) is not False:
                legacy.unlink()
            return record
        # 后台实例不能把新生成的密码写进服务日志。
        can_display = windows_desktop_available() or interactive_output()
        if not can_display:
            raise ValueError('尚未设置 WebUI 密码，请在实例目录执行 --reset-webui-password 后再启用 WebUI')
        password = secrets.token_urlsafe(24)
        record = password_record(password)
        write_record(path, record)
        if display_once(password) is False:
            # 没人看到的密码等于不可登录，撤销本次生成，下次启动重新生成。
            path.unlink(missing_ok=True)
            raise OSError('无法显示 WebUI 初始密码，已撤销本次生成的密码，请重启或从本机重置密码')
        return record


def reset_offline(root, config, record):
    path = auth_path(root, config)
    legacy = Path(root) / config.get('token_path', './conf/webui_token.txt')
    if path.resolve() == legacy.resolve():
        raise ValueError('WebUI 新认证文件不能与旧令牌文件使用同一路径')
    with credential_lock(path):
        write_record(path, record)
        if legacy.exists():
            try:
                legacy.unlink()
            except OSError:
                # 旧令牌此时只是残留文件：认证以新文件为准，删除失败不影响本次重置。
                pass


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
