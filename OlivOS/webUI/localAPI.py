# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/webUI/localAPI.py
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   仅当前系统用户可访问的 WebUI 管理入口
'''

import hashlib
import json
import os
import socket
import stat
import tempfile
import threading
import time
from pathlib import Path

MAX_MESSAGE = 16384


def current_sid():
    import win32api
    import win32con
    import win32security

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        return win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()


def endpoint(root):
    digest = hashlib.sha256(os.path.normcase(str(Path(root).resolve())).encode('utf-8')).hexdigest()[:24]
    if os.name == 'nt':
        import win32security
        user = hashlib.sha256(win32security.ConvertSidToStringSid(current_sid()).encode()).hexdigest()[:16]
        return rf'\\.\pipe\OlivOS-WebUI-{user}-{digest}'
    directory_name = f'olivos-webui-{os.getuid()}-{digest}'
    address = str(Path(tempfile.gettempdir()) / directory_name / 'control.sock')
    # macOS 的用户临时目录可能超过 Unix socket 的路径长度上限。
    return address if len(os.fsencode(address)) < 100 else str(Path('/tmp') / directory_name / 'control.sock')


def unix_directory(address):
    directory = Path(address).parent
    try:
        directory.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise PermissionError('WebUI 本机通信目录的所有者或权限不正确')


def encode(message):
    data = json.dumps(message, ensure_ascii=False).encode('utf-8')
    if len(data) > MAX_MESSAGE:
        raise ValueError('本机管理消息过长')
    return data


def receive_unix(connection):
    chunks = bytearray()
    while len(chunks) <= MAX_MESSAGE:
        part = connection.recv(min(4096, MAX_MESSAGE + 1 - len(chunks)))
        if not part:
            break
        chunks.extend(part)
        if b'\n' in part:
            break
    if len(chunks) > MAX_MESSAGE:
        raise ValueError('本机管理消息过长')
    return json.loads(chunks)


def request(root, message):
    address = endpoint(root)
    if os.name != 'nt':
        if not Path(address).exists():
            raise FileNotFoundError('WebUI 本机管理入口未运行')
        unix_directory(address)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(8)
            try:
                connection.connect(address)
            except ConnectionRefusedError:
                raise FileNotFoundError('WebUI 本机管理入口未运行') from None
            connection.sendall(encode(message) + b'\n')
            result = receive_unix(connection)
    else:
        import pywintypes
        import win32con
        import win32file
        import win32pipe

        try:
            win32pipe.WaitNamedPipe(address, 5000)
            handle = win32file.CreateFile(address, win32con.GENERIC_READ | win32con.GENERIC_WRITE,
                                          0, None, win32con.OPEN_EXISTING, 0, None)
        except pywintypes.error as error:
            if error.winerror == 2:
                raise FileNotFoundError('WebUI 本机管理入口未运行') from None
            raise OSError('无法连接 WebUI 本机管理入口') from None
        try:
            win32pipe.SetNamedPipeHandleState(handle, win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_NOWAIT,
                                              None, None)
            win32file.WriteFile(handle, encode(message))
            result = json.loads(read_pipe(handle, time.monotonic() + 8))
        finally:
            handle.Close()
    if not isinstance(result, dict) or result.get('ok') is not True:
        raise OSError('WebUI 本机管理操作失败，请检查本机日志及认证文件权限')
    return result


def read_pipe(handle, deadline):
    import pywintypes
    import win32file

    while True:
        try:
            code, data = win32file.ReadFile(handle, MAX_MESSAGE)
            if code != 0:
                raise ValueError('本机管理消息过长')
            return data
        except pywintypes.error as error:
            if error.winerror not in (232, 536):
                raise OSError('本机管理连接已断开') from None
            if time.monotonic() >= deadline:
                raise TimeoutError('WebUI 本机管理请求超时') from None
            time.sleep(0.02)


class LocalServer:
    def __init__(self, root, handler):
        self.address = endpoint(root)
        self.handler = handler
        self.stopped = threading.Event()
        self.ready = threading.Event()
        self.error = None
        self.worker = threading.Thread(target=self.run, name='WebUI-local-management', daemon=True)

    def start(self):
        self.worker.start()
        if not self.ready.wait(5) or self.error is not None:
            self.stopped.set()
            raise OSError('WebUI 本机管理入口启动失败，请检查是否已运行相同实例')

    def close(self):
        self.stopped.set()

    def dispatch(self, message):
        try:
            if not isinstance(message, dict):
                raise ValueError
            return dict(self.handler(message), ok=True)
        except (OSError, ValueError, RuntimeError, TimeoutError):
            # 不把异常中的文件内容或管理请求回显到响应/日志。
            return {'ok': False}

    def run(self):
        errors = (OSError, ValueError)
        if os.name == 'nt':
            import pywintypes
            errors += (pywintypes.error,)
        try:
            if os.name == 'nt':
                self.run_windows()
            else:
                self.run_unix()
        except errors:
            self.error = True
        finally:
            self.ready.set()

    def run_unix(self):
        unix_directory(self.address)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            if Path(self.address).exists():
                # 仅回收已确认没有监听者的旧 socket，不碰普通文件/链接。
                if not stat.S_ISSOCK(Path(self.address).lstat().st_mode):
                    raise OSError('本机管理路径已被占用')
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                    probe.settimeout(0.5)
                    try:
                        probe.connect(self.address)
                    except ConnectionRefusedError:
                        Path(self.address).unlink()
                    else:
                        raise OSError('本机管理入口已运行')
            listener.bind(self.address)
            os.chmod(self.address, 0o600)
            listener.listen(4)
            listener.settimeout(0.2)
            self.ready.set()
            try:
                while not self.stopped.is_set():
                    try:
                        connection, _ = listener.accept()
                    except socket.timeout:
                        continue
                    with connection:
                        connection.settimeout(3)
                        try:
                            result = self.dispatch(receive_unix(connection))
                            connection.sendall(encode(result) + b'\n')
                        except (OSError, ValueError):
                            pass
            finally:
                Path(self.address).unlink(missing_ok=True)

    def run_windows(self):
        import pywintypes
        import win32con
        import win32file
        import win32pipe
        import win32security

        security = pywintypes.SECURITY_ATTRIBUTES()
        security.bInheritHandle = False
        acl = win32security.ACL()
        acl.AddAccessAllowedAce(win32security.ACL_REVISION, win32con.GENERIC_ALL, current_sid())
        security.SECURITY_DESCRIPTOR.SetSecurityDescriptorDacl(1, acl, 0)
        # 单一实例 + 拒绝远程客户端；DACL 仅授权当前系统用户。
        handle = win32pipe.CreateNamedPipe(
            self.address, win32pipe.PIPE_ACCESS_DUPLEX | 0x00080000,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_NOWAIT | 0x8,
            1, MAX_MESSAGE, MAX_MESSAGE, 3000, security,
        )
        self.ready.set()
        try:
            while not self.stopped.is_set():
                try:
                    win32pipe.ConnectNamedPipe(handle, None)
                except pywintypes.error as error:
                    if error.winerror == 536:
                        self.stopped.wait(0.02)
                        continue
                    if error.winerror in (109, 232, 233):
                        win32pipe.DisconnectNamedPipe(handle)
                        continue
                    if error.winerror != 535:
                        raise OSError('本机管理管道连接失败') from None
                try:
                    message = json.loads(read_pipe(handle, time.monotonic() + 3))
                    win32file.WriteFile(handle, encode(self.dispatch(message)))
                    # 等待客户端读取响应，但不让本机慢客户端阻塞下一次管理操作。
                    deadline = time.monotonic() + 1
                    while time.monotonic() < deadline and not self.stopped.is_set():
                        try:
                            win32file.ReadFile(handle, 1)
                        except pywintypes.error as error:
                            if error.winerror in (109, 233):
                                break
                        self.stopped.wait(0.01)
                except (OSError, ValueError, pywintypes.error):
                    pass
                finally:
                    try:
                        win32pipe.DisconnectNamedPipe(handle)
                    except pywintypes.error:
                        pass
        finally:
            handle.Close()
