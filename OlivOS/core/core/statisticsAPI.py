# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/core/core/statisticsAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   性能与消息流量统计。
'''

import copy
import ctypes
import math
import os
import platform
import re
import threading
import time
import traceback
from collections import deque

import psutil

from OlivOS.core.core import API

modelName = 'statisticsAPI'
MESSAGE_EVENT_TYPES = ('private_message', 'group_message')
DEFAULT_HISTORY_SIZE = 120
DEFAULT_TRAFFIC_BUCKET_SECONDS = 5.0
DEFAULT_TRAFFIC_HISTORY_SIZE = 60
WINDOW_CONFIG = {
    '1m': {'seconds': 60.0, 'points': 60, 'rollup': False},
    '5m': {'seconds': 300.0, 'points': 60, 'rollup': False},
    '15m': {'seconds': 900.0, 'points': 60, 'rollup': False},
    '1h': {'seconds': 3600.0, 'points': 60, 'rollup': True},
    '6h': {'seconds': 21600.0, 'points': 60, 'rollup': True},
    '24h': {'seconds': 86400.0, 'points': 144, 'rollup': True},
}
WINDOW_SECONDS = {name: config['seconds'] for name, config in WINDOW_CONFIG.items()}
WINDOW_POINTS = 60
RAW_WINDOW_SECONDS = max(
    config['seconds'] for config in WINDOW_CONFIG.values() if not config['rollup']
)
ROLLUP_WINDOW_SECONDS = max(
    config['seconds'] for config in WINDOW_CONFIG.values() if config['rollup']
)
ROLLUP_INTERVAL_SECONDS = 60.0
ROLLUP_CAPACITY = int(math.ceil(ROLLUP_WINDOW_SECONDS / ROLLUP_INTERVAL_SECONDS)) + 1
NETWORK_CONNECTION_REFRESH_SECONDS = 5.0
NETWORK_INTERFACE_LIMIT = 16
PERFORMANCE_HISTORY_KEYS = (
    'cpu_percent', 'load_1', 'memory_percent', 'swap_percent', 'swap_in_bps',
    'swap_out_bps', 'disk_percent', 'disk_read_bps', 'disk_write_bps',
    'network_recv_bps', 'network_sent_bps', 'process_count', 'process_rss',
    'process_cpu_percent', 'process_threads', 'process_handles',
)
PERFORMANCE_GAUGE_KEYS = frozenset((
    'cpu_percent', 'load_1', 'memory_percent', 'swap_percent', 'disk_percent',
    'process_count', 'process_rss', 'process_cpu_percent', 'process_threads',
    'process_handles',
))
PERFORMANCE_RATE_KEYS = frozenset((
    'swap_in_bps', 'swap_out_bps', 'disk_read_bps', 'disk_write_bps',
    'network_recv_bps', 'network_sent_bps',
))
TRAFFIC_TARGET = {'type': 'statistics', 'fliter': 'control_only'}
PROCESS_CMDLINE_LIMIT = 1200
PROCESS_PATH_LIMIT = 1024
SYSTEM_TEXT_LIMIT = 240
SYSTEM_PATH_LIMIT = 1024
PROCESS_DETAIL_ITEMS_LIMIT = 100
PROCESS_THREAD_DETAIL_LIMIT = 256
_WINDOWS_THREAD_QUERY_INFORMATION = 0x0040
_WINDOWS_THREAD_QUERY_LIMITED_INFORMATION = 0x0800
_WINDOWS_PROCESS_QUERY_INFORMATION = 0x0400
_WINDOWS_PROCESS_VM_READ = 0x0010
_WINDOWS_THREAD_START_ADDRESS = 9
_WINDOWS_THREAD_PRIORITY_ERROR = 0x7FFFFFFF
_WINDOWS_PROCESS_MODULE_LIMIT = 1024
SECRET_ARGUMENT = re.compile(
    r'password|passwd|token|secret|cookie|authorization|'
    r'access[_-]?key|api[_-]?key|(?:^|[_-])key$', re.I
)


def _non_negative_int(value, default=0):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, value)


def _non_negative_float(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if value != value or value in (float('inf'), float('-inf')):
        return default
    return max(0.0, value)


def _round(value, digits=2):
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return 0.0


def _optional_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result or result in (float('inf'), float('-inf')):
        return None
    return result


def _text(value, limit):
    if value is None:
        return None
    try:
        text = str(value).strip()
    except Exception:
        return None
    if len(text) > limit:
        return text[:max(0, limit - 1)] + '…'
    return text


def _safe_text(func, limit):
    try:
        return _text(func(), limit)
    except Exception:
        return None


def _linux_cpu_model():
    try:
        with open('/proc/cpuinfo', 'r', encoding='utf-8', errors='replace') as handle:
            for line in handle:
                if line.lower().startswith('model name'):
                    _, _, value = line.partition(':')
                    return _text(value, SYSTEM_TEXT_LIMIT)
    except Exception:
        pass
    return None


def _system_metadata():
    # 概览页只展示不随采样变化的系统信息，因此进程内采集一次即可。
    system_name = _safe_text(platform.system, SYSTEM_TEXT_LIMIT)
    display_name = {'Darwin': 'macOS'}.get(system_name, system_name)
    cpu_model = _linux_cpu_model() if system_name == 'Linux' else None
    if not cpu_model:
        cpu_model = _safe_text(platform.processor, SYSTEM_TEXT_LIMIT)
    if not cpu_model:
        cpu_model = _safe_text(platform.machine, SYSTEM_TEXT_LIMIT)
    working_directory = None
    try:
        working_directory = os.getcwd()
    except Exception:
        pass
    return {
        'os': _text(display_name, SYSTEM_TEXT_LIMIT),
        'os_release': _safe_text(platform.release, SYSTEM_TEXT_LIMIT),
        'os_version': _safe_text(platform.version, SYSTEM_TEXT_LIMIT),
        'architecture': _safe_text(platform.machine, SYSTEM_TEXT_LIMIT),
        'hostname': _safe_text(platform.node, SYSTEM_TEXT_LIMIT),
        'cpu_model': cpu_model,
        'python_version': _safe_text(platform.python_version, SYSTEM_TEXT_LIMIT),
        'python_implementation': _safe_text(platform.python_implementation, SYSTEM_TEXT_LIMIT),
        'working_directory': _text(working_directory, SYSTEM_PATH_LIMIT),
    }


def _masked_cmdline(parts, limit=PROCESS_CMDLINE_LIMIT):
    # 命令行可能带令牌或密码，展示前屏蔽疑似敏感参数及其后一项。
    if isinstance(parts, str):
        parts = [parts]
    masked = []
    mask_next = False
    for part in parts:
        text = str(part)
        if mask_next:
            masked.append('********')
            mask_next = False
            continue
        if SECRET_ARGUMENT.search(text):
            key, separator, _ = text.partition('=')
            if separator:
                masked.append(key + '=********')
            else:
                masked.append(text)
                mask_next = True
            continue
        masked.append(text)
    return _text(' '.join(masked), limit)


def _io_priority(value):
    if value is None:
        return None
    if hasattr(value, 'ioclass'):
        return {'class': _optional_int(value.ioclass), 'value': _optional_int(value.value)}
    return {'class': _optional_int(value), 'value': None}


def _parse_linux_thread_stat(content):
    # /proc/<pid>/task/<tid>/stat 的 comm 可包含空格，先按最后一个右括号切分。
    try:
        fields = content.rsplit(')', 1)[1].split()
    except IndexError:
        return {}
    result = {}
    if fields:
        result['state'] = fields[0][:8]
    if len(fields) >= 17:
        result['priority'] = _optional_int(fields[15])
        result['nice'] = _optional_int(fields[16])
    if len(fields) >= 37:
        result['processor'] = _optional_int(fields[36])
    if len(fields) >= 20:
        result['start_time_ticks'] = _optional_int(fields[19])
    return result


# 读取 /proc 文本时统一处理编码错误和长度上限。
def _read_proc_text(path, limit):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as source:
            return _text(source.read(), limit)
    except Exception:
        return None


# Python 线程名只在当前进程内可映射到 native_id。
def _python_thread_names(pid):
    try:
        if int(pid) != os.getpid():
            return {}
    except (TypeError, ValueError):
        return {}
    result = {}
    try:
        threads = threading.enumerate()
    except Exception:
        return result
    for thread in threads:
        native_id = getattr(thread, 'native_id', None)
        try:
            native_id = int(native_id)
        except (TypeError, ValueError):
            continue
        name = _text(getattr(thread, 'name', None), 128)
        if name:
            result[native_id] = name
    return result


def _linux_clock_ticks():
    try:
        return int(os.sysconf('SC_CLK_TCK'))
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _linux_boot_time():
    try:
        return float(psutil.boot_time())
    except Exception:
        return None


_WINDOWS_LIBRARIES = {}
_WINDOWS_LIBRARY_LOCK = threading.Lock()


class _WindowsModuleInfo(ctypes.Structure):
    _fields_ = [
        ('lpBaseOfDll', ctypes.c_void_p),
        ('SizeOfImage', ctypes.c_ulong),
        ('EntryPoint', ctypes.c_void_p),
    ]


def _windows_library(name):
    if platform.system() != 'Windows':
        return None
    with _WINDOWS_LIBRARY_LOCK:
        library = _WINDOWS_LIBRARIES.get(name)
        if library is not None:
            return library
        try:
            library = ctypes.WinDLL(name, use_last_error=True)
        except Exception:
            return None
        _WINDOWS_LIBRARIES[name] = library
        return library


def _windows_kernel32():
    library = _windows_library('kernel32')
    if library is None:
        return None
    try:
        library.OpenThread.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        library.OpenThread.restype = ctypes.c_void_p
        library.CloseHandle.argtypes = [ctypes.c_void_p]
        library.CloseHandle.restype = ctypes.c_int
        library.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        library.OpenProcess.restype = ctypes.c_void_p
        library.GetThreadPriority.argtypes = [ctypes.c_void_p]
        library.GetThreadPriority.restype = ctypes.c_int
        library.LocalFree.argtypes = [ctypes.c_void_p]
        library.LocalFree.restype = ctypes.c_void_p
        description = getattr(library, 'GetThreadDescription', None)
        if description is not None:
            description.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
            description.restype = ctypes.c_long
    except Exception:
        return None
    return library


def _windows_ntdll():
    library = _windows_library('ntdll')
    if library is None:
        return None
    try:
        query = getattr(library, 'NtQueryInformationThread', None)
        if query is not None:
            query.argtypes = [
                ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
                ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
            ]
            query.restype = ctypes.c_long
    except Exception:
        return None
    return library


def _windows_psapi():
    library = _windows_library('psapi')
    if library is None:
        return None
    try:
        enum_ex = getattr(library, 'EnumProcessModulesEx', None)
        if enum_ex is not None:
            enum_ex.argtypes = [
                ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong,
                ctypes.POINTER(ctypes.c_ulong), ctypes.c_ulong,
            ]
            enum_ex.restype = ctypes.c_int
        library.EnumProcessModules.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
        ]
        library.EnumProcessModules.restype = ctypes.c_int
        library.GetModuleFileNameExW.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_ulong,
        ]
        library.GetModuleFileNameExW.restype = ctypes.c_ulong
        library.GetModuleInformation.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(_WindowsModuleInfo), ctypes.c_ulong,
        ]
        library.GetModuleInformation.restype = ctypes.c_int
    except Exception:
        return None
    return library


# 一次枚举进程模块，供该进程下的所有线程起始地址复用。
def _windows_process_modules(pid, kernel32, psapi):
    if kernel32 is None or psapi is None:
        return []
    process = None
    try:
        process = kernel32.OpenProcess(
            _WINDOWS_PROCESS_QUERY_INFORMATION | _WINDOWS_PROCESS_VM_READ, 0, int(pid)
        )
        if not process:
            return []
        modules = (ctypes.c_void_p * _WINDOWS_PROCESS_MODULE_LIMIT)()
        needed = ctypes.c_ulong()
        enum_ex = getattr(psapi, 'EnumProcessModulesEx', None)
        if enum_ex is not None:
            ok = enum_ex(process, modules, ctypes.sizeof(modules), ctypes.byref(needed), 0x03)
            if not ok:
                ok = psapi.EnumProcessModules(
                    process, modules, ctypes.sizeof(modules), ctypes.byref(needed)
                )
        else:
            ok = psapi.EnumProcessModules(process, modules, ctypes.sizeof(modules), ctypes.byref(needed))
        if not ok:
            return []
        count = min(
            needed.value // ctypes.sizeof(ctypes.c_void_p), _WINDOWS_PROCESS_MODULE_LIMIT
        )
        result = []
        path_buffer = ctypes.create_unicode_buffer(PROCESS_PATH_LIMIT)
        for index in range(count):
            handle = modules[index]
            info = _WindowsModuleInfo()
            if not psapi.GetModuleInformation(
                process, handle, ctypes.byref(info), ctypes.sizeof(info)
            ):
                continue
            base = int(info.lpBaseOfDll or 0)
            size = int(info.SizeOfImage or 0)
            path_buffer.value = ''
            if not psapi.GetModuleFileNameExW(
                process, handle, path_buffer, len(path_buffer)
            ):
                continue
            path = _text(path_buffer.value, PROCESS_PATH_LIMIT)
            if path:
                result.append((base, base + size, os.path.basename(path)))
        return result
    except Exception:
        return []
    finally:
        if process:
            try:
                kernel32.CloseHandle(process)
            except Exception:
                pass


def _windows_thread_start_module(address, modules):
    if not address:
        return None
    for base, end, name in modules or ():
        if base <= address < end:
            offset = address - base
            return _text('%s+0x%X' % (name, offset) if offset else name, 256)
    return _text('0x%X' % address, 256)


# Windows 线程没有独立命令行，补充描述、优先级和起始模块。
def _windows_thread_detail(tid, kernel32, ntdll, modules):
    result = {'name': None, 'priority': None, 'start_address': None, 'start_module': None}
    if kernel32 is None:
        return result
    handle = None
    for access in (
        _WINDOWS_THREAD_QUERY_INFORMATION | _WINDOWS_THREAD_QUERY_LIMITED_INFORMATION,
        _WINDOWS_THREAD_QUERY_INFORMATION,
        _WINDOWS_THREAD_QUERY_LIMITED_INFORMATION,
    ):
        try:
            handle = kernel32.OpenThread(access, 0, int(tid))
        except Exception:
            handle = None
        if handle:
            break
    if not handle:
        return result
    try:
        description = getattr(kernel32, 'GetThreadDescription', None)
        if description is not None:
            text = ctypes.c_wchar_p()
            try:
                if description(handle, ctypes.byref(text)) >= 0:
                    result['name'] = _text(text.value, 256)
            except Exception:
                pass
            finally:
                try:
                    kernel32.LocalFree(text)
                except Exception:
                    pass
        priority = getattr(kernel32, 'GetThreadPriority', None)
        if priority is not None:
            value = priority(handle)
            if value != _WINDOWS_THREAD_PRIORITY_ERROR:
                result['priority'] = int(value)
        query = getattr(ntdll, 'NtQueryInformationThread', None) if ntdll is not None else None
        if query is not None:
            address = ctypes.c_void_p()
            status = query(
                handle, _WINDOWS_THREAD_START_ADDRESS, ctypes.byref(address),
                ctypes.sizeof(address), None,
            )
            if status == 0 and address.value:
                result['start_address'] = int(address.value)
                result['start_module'] = _windows_thread_start_module(address.value, modules)
    except Exception:
        pass
    finally:
        try:
            kernel32.CloseHandle(handle)
        except Exception:
            pass
    return result


# 批量查询 Windows 线程，失败时保留基础采样字段。
def _windows_thread_details(pid, rows, python_names=None, kernel32=None, ntdll=None, psapi=None):
    if kernel32 is None:
        kernel32 = _windows_kernel32()
    if ntdll is None:
        ntdll = _windows_ntdll()
    if psapi is None:
        psapi = _windows_psapi()
    if kernel32 is None:
        return
    names = python_names or {}
    modules = _windows_process_modules(pid, kernel32, psapi)
    for row in rows or ():
        detail = _windows_thread_detail(row.get('id'), kernel32, ntdll, modules)
        if detail['name']:
            row['name'] = detail['name']
        elif not row.get('name'):
            row['name'] = names.get(row.get('id'))
        if detail['priority'] is not None:
            row['priority'] = detail['priority']
        if detail['start_address'] is not None:
            row['start_address'] = detail['start_address']
        if detail['start_module']:
            row['start_module'] = detail['start_module']


def _named_numbers(value):
    if value is None:
        return None
    result = {}
    for name in getattr(value, '_fields', ()) or ():
        item = getattr(value, name, None)
        if item is None or isinstance(item, bool):
            continue
        if isinstance(item, int):
            result[name] = item
        elif isinstance(item, float):
            result[name] = _round(item, 3)
    return result or None


def _address_row(value):
    if value is None:
        return None
    if hasattr(value, 'ip'):
        return {
            'ip': _text(getattr(value, 'ip', ''), 128),
            'port': _optional_int(getattr(value, 'port', None)),
        }
    try:
        if isinstance(value, (tuple, list)) and len(value) >= 2:
            return {'ip': _text(value[0], 128), 'port': _optional_int(value[1])}
    except Exception:
        pass
    return {'ip': _text(value, 128), 'port': None}


def _open_file_row(item):
    return {
        'path': _text(getattr(item, 'path', ''), PROCESS_PATH_LIMIT),
        'fd': _optional_int(getattr(item, 'fd', None)),
        'mode': _text(getattr(item, 'mode', ''), 32),
        'position': _optional_int(getattr(item, 'position', None)),
    }


def _connection_row(item):
    return {
        'fd': _optional_int(getattr(item, 'fd', None)),
        'family': _text(getattr(item, 'family', ''), 32),
        'type': _text(getattr(item, 'type', ''), 32),
        'laddr': _address_row(getattr(item, 'laddr', None)),
        'raddr': _address_row(getattr(item, 'raddr', None)),
        'status': _text(getattr(item, 'status', ''), 32),
    }


def _memory_map_row(item):
    return {
        'path': _text(getattr(item, 'path', ''), PROCESS_PATH_LIMIT),
        'metrics': _named_numbers(item),
    }


def _rate(current, previous, elapsed):
    if previous is None or elapsed <= 0:
        return 0.0
    return max(0.0, (current - previous) / elapsed)


def _counter_delta(current, previous, name):
    if current is None or previous is None:
        return None
    try:
        return max(0, int(getattr(current, name)) - int(getattr(previous, name)))
    except (AttributeError, TypeError, ValueError):
        return None


def _optional_non_negative_float(value):
    number = _optional_float(value)
    return None if number is None else max(0.0, number)


class _WindowsMemoryIO(object):
    # Windows 的 psutil 交换区计数器恒为 0，改用 PDH 的硬缺页读写速率。
    PDH_FMT_DOUBLE = 0x00000200
    PAGE_SIZE = 4096
    COUNTERS = (r'\Memory\Pages Input/sec', r'\Memory\Pages Output/sec')

    class _CounterValue(ctypes.Structure):
        _fields_ = [('status', ctypes.c_ulong), ('value', ctypes.c_double)]

    def __init__(self):
        self.pdh = None
        self.query = None
        self.counters = []
        self.disabled = platform.system() != 'Windows'
        if self.disabled:
            return
        try:
            pdh = ctypes.WinDLL('pdh')
            pdh.PdhOpenQueryW.argtypes = [
                ctypes.c_wchar_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
            pdh.PdhOpenQueryW.restype = ctypes.c_ulong
            add_func = getattr(pdh, 'PdhAddEnglishCounterW', None)
            if add_func is None:
                add_func = pdh.PdhAddCounterW
            add_func.argtypes = [
                ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_size_t,
                ctypes.POINTER(ctypes.c_void_p)]
            add_func.restype = ctypes.c_ulong
            pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
            pdh.PdhCollectQueryData.restype = ctypes.c_ulong
            pdh.PdhGetFormattedCounterValue.argtypes = [
                ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                ctypes.POINTER(self._CounterValue)]
            pdh.PdhGetFormattedCounterValue.restype = ctypes.c_ulong
            pdh.PdhCloseQuery.argtypes = [ctypes.c_void_p]
            pdh.PdhCloseQuery.restype = ctypes.c_ulong
            self.pdh = pdh
            self._add_func = add_func
        except Exception:
            self.disabled = True

    def _open(self):
        query = ctypes.c_void_p()
        if self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(query)) != 0:
            return False
        counters = []
        for path in self.COUNTERS:
            counter = ctypes.c_void_p()
            if self._add_func(query, path, 0, ctypes.byref(counter)) != 0:
                self.pdh.PdhCloseQuery(query)
                return False
            counters.append(counter)
        if self.pdh.PdhCollectQueryData(query) != 0:
            self.pdh.PdhCloseQuery(query)
            return False
        self.query = query
        self.counters = counters
        return True

    def sample(self):
        if self.disabled:
            return None
        if self.query is None:
            if not self._open():
                self.disabled = True
            return None
        try:
            if self.pdh.PdhCollectQueryData(self.query) != 0:
                return None
            values = []
            for counter in self.counters:
                value = self._CounterValue()
                status = self.pdh.PdhGetFormattedCounterValue(
                    counter, self.PDH_FMT_DOUBLE, None, ctypes.byref(value)
                )
                if status != 0:
                    return None
                values.append(max(0.0, float(value.value)) * self.PAGE_SIZE)
            return values
        except Exception:
            return None

    def close(self):
        if self.query is not None and self.pdh is not None:
            try:
                self.pdh.PdhCloseQuery(self.query)
            except Exception:
                pass
        self.query = None
        self.counters = []


def unavailable_snapshot(reason='statistics_unavailable'):
    return {
        'available': False,
        'reason': reason,
        'sampled_at': 0,
        'performance': None,
        'traffic': None,
    }


class TrafficRecorder(object):
    def __init__(self, control_queue=None, flush_interval=1.0, max_pending=200):
        self.control_queue = control_queue
        self.flush_interval = _non_negative_float(flush_interval, 1.0)
        self.max_pending = max(1, _non_negative_int(max_pending, 200))
        self.lock = threading.Lock()
        self.pending = {'inbound': 0, 'outbound': 0, 'events': 0, 'failed': 0}
        self.last_flush = time.monotonic()

    def bind(self, control_queue):
        with self.lock:
            self.control_queue = control_queue

    def record_inbound(self):
        self._record(inbound=1, events=1)

    def record_event(self):
        self._record(events=1)

    def record_outbound(self):
        self._record(outbound=1)

    def record_failed(self):
        self._record(failed=1)

    def record_event_type(self, func_type):
        if func_type in MESSAGE_EVENT_TYPES:
            self.record_inbound()
        else:
            self.record_event()

    def _record(self, inbound=0, outbound=0, events=0, failed=0):
        packet = None
        control_queue = None
        with self.lock:
            self.pending['inbound'] += inbound
            self.pending['outbound'] += outbound
            self.pending['events'] += events
            self.pending['failed'] += failed
            total = sum(self.pending.values())
            elapsed = time.monotonic() - self.last_flush
            if total >= self.max_pending or self.flush_interval <= 0 or elapsed >= self.flush_interval:
                packet = self._take_packet_locked()
                control_queue = self.control_queue
        if packet is not None:
            self._put(packet, control_queue)

    def flush(self, force=False):
        packet = None
        control_queue = None
        with self.lock:
            # 空闲循环会频繁调用 flush；非强制刷新只在到达上报周期时发送，
            # 避免把每条事件都拆成单独的控制包。
            if force or (
                any(self.pending.values())
                and time.monotonic() - self.last_flush >= self.flush_interval
            ):
                packet = self._take_packet_locked()
                control_queue = self.control_queue
        if packet is not None:
            self._put(packet, control_queue)

    def _take_packet_locked(self):
        if not any(self.pending.values()):
            return None
        data = dict(self.pending)
        for key in self.pending:
            self.pending[key] = 0
        self.last_flush = time.monotonic()
        return API.Control.packet('send', {
            'target': dict(TRAFFIC_TARGET),
            'data': {
                'action': 'traffic',
                'inbound': data['inbound'],
                'outbound': data['outbound'],
                'events': data['events'],
                'failed': data['failed'],
                'sampled_at': time.time(),
            },
        })

    @staticmethod
    def _put(packet, control_queue):
        if control_queue is None:
            return
        try:
            control_queue.put(packet, block=False)
        except Exception:
            # 统计队列拥塞时只丢弃统计增量，不能影响消息收发。
            pass


gTrafficRecorder = TrafficRecorder()


def bind_control_queue(control_queue):
    try:
        gTrafficRecorder.bind(control_queue)
    except Exception:
        # 统计是旁路能力，初始化失败不能影响插件进程启动。
        pass


def record_event_type(func_type):
    try:
        gTrafficRecorder.record_event_type(func_type)
    except Exception:
        pass


def record_outbound():
    try:
        gTrafficRecorder.record_outbound()
    except Exception:
        pass


def record_failed():
    try:
        gTrafficRecorder.record_failed()
    except Exception:
        pass


def flush_traffic():
    try:
        gTrafficRecorder.flush()
    except Exception:
        pass


class server(API.Proc_templet):
    def __init__(self, Proc_name='OlivOS_statistics', scan_interval=1.0, dead_interval=1,
                 rx_queue=None, tx_queue=None, control_queue=None, logger_proc=None,
                 history_size=DEFAULT_HISTORY_SIZE,
                 traffic_bucket_seconds=DEFAULT_TRAFFIC_BUCKET_SECONDS,
                 traffic_history_size=DEFAULT_TRAFFIC_HISTORY_SIZE):
        super().__init__(Proc_name, 'statistics', scan_interval, dead_interval, rx_queue, tx_queue,
                         control_queue, logger_proc)
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.history_size = max(2, _non_negative_int(history_size, DEFAULT_HISTORY_SIZE))
        self.traffic_bucket_seconds = max(0.1, _non_negative_float(
            traffic_bucket_seconds, DEFAULT_TRAFFIC_BUCKET_SECONDS
        ))
        self.traffic_history_size = max(2, _non_negative_int(
            traffic_history_size, DEFAULT_TRAFFIC_HISTORY_SIZE
        ))
        self.scan_interval = max(0.1, _non_negative_float(
            scan_interval, 1.0
        ))
        self.performance_history = deque(maxlen=self.history_size)
        self.traffic_history = deque(maxlen=self.traffic_history_size)
        self.performance_long_history = deque(maxlen=max(
            self.history_size,
            int(math.ceil(RAW_WINDOW_SECONDS / self.scan_interval)) + 1,
        ))
        self.traffic_long_history = deque(maxlen=max(
            self.traffic_history_size,
            int(math.ceil(RAW_WINDOW_SECONDS / self.traffic_bucket_seconds)) + 1,
        ))
        self.performance_rollup_history = deque(maxlen=ROLLUP_CAPACITY)
        self.traffic_rollup_history = deque(maxlen=ROLLUP_CAPACITY)
        self._performance_rollup_current = None
        self._traffic_rollup_current = None
        self.inbound_total = 0
        self.outbound_total = 0
        self.event_total = 0
        self.failed_total = 0
        self._pending_traffic = {'inbound': 0, 'outbound': 0, 'events': 0, 'failed': 0}
        self._traffic_bucket_started_at = time.monotonic()
        self._traffic_window_started_at = time.time()
        self._last_sample = None
        self._last_sample_at = 0
        self._last_io_at = None
        self._last_disk_io = None
        self._last_net_io = None
        self._last_net_pernic_io = None
        self._last_swap_io = None
        self._last_network_connections_at = None
        self._network_connection_count = None
        self._network_tcp_states = None
        self._memory_io = _WindowsMemoryIO()
        self.system_info = _system_metadata()
        self._last_process_cpu_at = None
        self._last_process_cpu_total = 0.0
        self._process_detail_lock = threading.Lock()
        self._process_detail_cpu = {}
        self._thread_detail_cpu = {}

    @staticmethod
    def _safe(func, default=None):
        try:
            return func()
        except Exception:
            return default

    def _process_tree(self):
        try:
            root = psutil.Process(os.getpid())
            return root, [root] + root.children(recursive=True)
        except Exception:
            return None, []

    def _process_tree_totals(self):
        result = {
            'count': 0, 'rss': 0, 'cpu_percent': 0.0,
            'threads': None, 'handles': None, 'num_fds': None,
        }
        root, processes = self._process_tree()
        if root is None:
            return result, None
        result['count'] = len(processes)
        rss = 0
        cpu_seconds = 0.0
        threads = 0
        handles = 0
        num_fds = 0
        threads_ok = True
        handles_ok = platform.system() == 'Windows'
        num_fds_ok = True
        for proc in processes:
            try:
                with proc.oneshot():
                    rss += proc.memory_info().rss
                    cpu_times = proc.cpu_times()
                    cpu_seconds += max(0.0, float(cpu_times.user) + float(cpu_times.system))
                    if threads_ok:
                        try:
                            threads += proc.num_threads()
                        except Exception:
                            threads_ok = False
                    if handles_ok:
                        try:
                            handles += proc.num_handles()
                        except Exception:
                            handles_ok = False
                    if num_fds_ok:
                        num_fds_func = getattr(proc, 'num_fds', None)
                        if not callable(num_fds_func):
                            num_fds_ok = False
                        else:
                            try:
                                num_fds += num_fds_func()
                            except Exception:
                                num_fds_ok = False
            except Exception:
                # 任一进程读取失败时，文件描述符总数不再完整，避免把部分值当成全量返回。
                num_fds_ok = False
                continue
        result['rss'] = max(0, int(rss))
        result['threads'] = threads if threads_ok else None
        result['handles'] = handles if handles_ok else None
        result['num_fds'] = num_fds if num_fds_ok else None
        return result, cpu_seconds

    def _process_tree_metrics(self, now=None):
        result, cpu_seconds = self._process_tree_totals()
        if cpu_seconds is None:
            return result
        now = time.monotonic() if now is None else now
        if self._last_process_cpu_at is not None:
            elapsed = max(0.0, now - self._last_process_cpu_at)
            result['cpu_percent'] = _round(
                _rate(cpu_seconds, self._last_process_cpu_total, elapsed) * 100.0
            )
        self._last_process_cpu_at = now
        self._last_process_cpu_total = cpu_seconds
        return result

    # 线程共享进程命令行；Linux 额外提供等待点和启动时间。
    @staticmethod
    def _linux_thread_detail(pid, tid, boot_time=None):
        base = '/proc/{0}/task/{1}'.format(pid, tid)
        result = {
            'name': None,
            'state': None,
            'priority': None,
            'nice': None,
            'processor': None,
            'ctx_switches': None,
            'wchan': None,
            'start_time': None,
        }
        name = _read_proc_text(base + '/comm', 64)
        if name:
            result['name'] = name
        stat = _read_proc_text(base + '/stat', 4096)
        if stat:
            parsed = _parse_linux_thread_stat(stat)
            start_ticks = parsed.pop('start_time_ticks', None)
            result.update(parsed)
            if start_ticks is not None:
                clock_ticks = _linux_clock_ticks()
                boot = boot_time if boot_time is not None else _linux_boot_time()
                if clock_ticks and boot is not None:
                    result['start_time'] = _round(boot + float(start_ticks) / clock_ticks, 3)
        wchan = _read_proc_text(base + '/wchan', 128)
        if wchan and wchan != '0':
            result['wchan'] = wchan
        status_text = _read_proc_text(base + '/status', 16384)
        if status_text:
            counters = {}
            for line in status_text.splitlines():
                key, separator, value = line.partition(':')
                if separator and key in ('voluntary_ctxt_switches', 'nonvoluntary_ctxt_switches'):
                    counters[key] = _non_negative_int(value.strip())
            if counters:
                result['ctx_switches'] = {
                    'voluntary': counters.get('voluntary_ctxt_switches', 0),
                    'involuntary': counters.get('nonvoluntary_ctxt_switches', 0),
                }
        return result

    def _process_detail(self, proc, now, cache_updates, previous_threads, thread_cache_updates):
        # 进程与线程的 CPU 百分比都用同一 pid + create_time 的两次 CPU 时间差计算。
        try:
            pid = int(proc.pid)
        except Exception:
            return None
        detail = {
            'pid': pid,
            'ppid': 0,
            'name': '',
            'status': '',
            'username': '',
            'create_time': 0.0,
            'cmdline': None,
            'exe': None,
            'memory_rss': 0,
            'memory_vms': 0,
            'memory_percent': None,
            'memory_peak': None,
            'memory_private': None,
            'memory_shared': None,
            'cpu_percent': 0.0,
            'cpu_user': 0.0,
            'cpu_system': 0.0,
            'cpu_children_user': None,
            'cpu_children_system': None,
            'cpu_iowait': None,
            'nice': None,
            'io_priority': None,
            'cpu_affinity': None,
            'ctx_switches': None,
            'io': None,
            'thread_count': None,
            'handles': None,
            'num_fds': None,
            'threads': None,
            'threads_truncated': False,
            'children': [],
        }
        detail['ppid'] = _non_negative_int(self._safe(proc.ppid, 0))
        detail['name'] = self._safe(proc.name, '') or ''
        detail['status'] = self._safe(proc.status, '') or ''
        detail['username'] = self._safe(proc.username, '') or ''
        detail['create_time'] = _round(self._safe(proc.create_time, 0.0), 3)
        cmdline = self._safe(proc.cmdline)
        if cmdline:
            detail['cmdline'] = _masked_cmdline(cmdline)
        detail['exe'] = _text(self._safe(proc.exe), PROCESS_PATH_LIMIT)
        memory = self._safe(proc.memory_info)
        detail['memory_rss'] = max(0, int(getattr(memory, 'rss', 0) or 0))
        detail['memory_vms'] = max(0, int(getattr(memory, 'vms', 0) or 0))
        memory_percent = self._safe(proc.memory_percent)
        if memory_percent is not None:
            detail['memory_percent'] = _round(memory_percent, 2)
        peak = getattr(memory, 'peak_wset', None)
        if peak is None:
            peak = getattr(memory, 'peak', None)
        detail['memory_peak'] = _optional_int(peak)
        detail['memory_private'] = _optional_int(getattr(memory, 'private', None))
        detail['memory_shared'] = _optional_int(getattr(memory, 'shared', None))
        cpu_times = self._safe(proc.cpu_times)
        user = _non_negative_float(getattr(cpu_times, 'user', 0.0))
        system = _non_negative_float(getattr(cpu_times, 'system', 0.0))
        detail['cpu_user'] = _round(user, 3)
        detail['cpu_system'] = _round(system, 3)
        detail['cpu_children_user'] = _optional_float(getattr(cpu_times, 'children_user', None))
        detail['cpu_children_system'] = _optional_float(getattr(cpu_times, 'children_system', None))
        detail['cpu_iowait'] = _optional_float(getattr(cpu_times, 'iowait', None))
        detail['nice'] = _optional_int(self._safe(proc.nice))
        detail['io_priority'] = _io_priority(self._safe(proc.ionice))
        affinity = self._safe(proc.cpu_affinity)
        if isinstance(affinity, (list, tuple)):
            values = []
            for item in affinity:
                value = _optional_int(item)
                if value is not None:
                    values.append(value)
            detail['cpu_affinity'] = values
        ctx_switches = self._safe(proc.num_ctx_switches)
        if ctx_switches is not None:
            detail['ctx_switches'] = {
                'voluntary': _non_negative_int(getattr(ctx_switches, 'voluntary', 0)),
                'involuntary': _non_negative_int(getattr(ctx_switches, 'involuntary', 0)),
            }
        io_counters = self._safe(proc.io_counters)
        if io_counters is not None:
            detail['io'] = {
                name: _non_negative_int(getattr(io_counters, name, 0))
                for name in ('read_count', 'write_count', 'read_bytes', 'write_bytes',
                             'other_count', 'other_bytes')
                if hasattr(io_counters, name)
            }
        threads = self._safe(proc.threads)
        if threads is not None:
            thread_rows = []
            python_names = _python_thread_names(pid)
            for thread in threads:
                tid = _non_negative_int(getattr(thread, 'id', 0))
                thread_user = _non_negative_float(getattr(thread, 'user_time', 0.0))
                thread_system = _non_negative_float(getattr(thread, 'system_time', 0.0))
                thread_total = thread_user + thread_system
                thread_key = (pid, detail['create_time'], tid)
                previous = previous_threads.get(thread_key)
                thread_cpu_percent = 0.0
                if previous is not None:
                    elapsed = max(0.0, now - previous[0])
                    thread_cpu_percent = _round(_rate(thread_total, previous[1], elapsed) * 100.0, 2)
                thread_cache_updates[thread_key] = (now, thread_total)
                thread_rows.append({
                    'id': tid,
                    'user': _round(thread_user, 3),
                    'system': _round(thread_system, 3),
                    'cpu_percent': thread_cpu_percent,
                    'name': None,
                    'python_name': python_names.get(tid),
                    'state': None,
                    'priority': None,
                    'nice': None,
                    'processor': None,
                    'ctx_switches': None,
                    'wchan': None,
                    'start_time': None,
                    'start_address': None,
                    'start_module': None,
                })
            detail['threads'] = sorted(thread_rows, key=lambda item: item['id'])
            detail['thread_count'] = len(detail['threads'])
            if platform.system() == 'Linux':
                boot_time = self._safe(psutil.boot_time)
                for row in detail['threads'][:PROCESS_THREAD_DETAIL_LIMIT]:
                    row.update(self._linux_thread_detail(pid, row['id'], boot_time))
                detail['threads_truncated'] = len(detail['threads']) > PROCESS_THREAD_DETAIL_LIMIT
            elif platform.system() == 'Windows':
                _windows_thread_details(pid, detail['threads'], python_names)
        else:
            num_threads = getattr(proc, 'num_threads', None)
            if callable(num_threads):
                value = self._safe(num_threads)
                if value is not None:
                    detail['thread_count'] = _non_negative_int(value)
        num_fds = getattr(proc, 'num_fds', None)
        if callable(num_fds):
            value = self._safe(num_fds)
            if value is not None:
                detail['num_fds'] = _non_negative_int(value)
        num_handles = getattr(proc, 'num_handles', None)
        if callable(num_handles):
            value = self._safe(num_handles)
            if value is not None:
                detail['handles'] = _non_negative_int(value)
        total_cpu = user + system
        key = (pid, detail['create_time'])
        with self._process_detail_lock:
            previous = self._process_detail_cpu.get(key)
        if previous is not None:
            elapsed = max(0.0, now - previous[0])
            detail['cpu_percent'] = _round(_rate(total_cpu, previous[1], elapsed) * 100.0)
        cache_updates[key] = (now, total_cpu)
        return detail

    def process_tree_snapshot(self, now=None):
        # 进程树只在 WebUI 打开“进程”标签时按需读取，避免每秒深挖线程明细。
        root, processes = self._process_tree()
        if root is None or not processes:
            return {
                'available': False,
                'reason': 'process_tree_unavailable',
                'sampled_at': time.time(),
                'root_pid': None,
                'process_count': 0,
                'thread_count': 0,
                'roots': [],
            }
        now = time.monotonic() if now is None else now
        details = {}
        cache_updates = {}
        thread_cache_updates = {}
        with self._process_detail_lock:
            previous_threads = dict(self._thread_detail_cpu)
        for proc in processes:
            detail = self._process_detail(
                proc, now, cache_updates, previous_threads, thread_cache_updates
            )
            if detail is not None:
                details[detail['pid']] = detail
        if not details:
            return {
                'available': False,
                'reason': 'process_tree_unavailable',
                'sampled_at': time.time(),
                'root_pid': None,
                'process_count': 0,
                'thread_count': 0,
                'roots': [],
            }
        with self._process_detail_lock:
            current_keys = set((detail['pid'], detail['create_time']) for detail in details.values())
            for key in list(self._process_detail_cpu):
                if key not in current_keys:
                    del self._process_detail_cpu[key]
            self._process_detail_cpu.update(cache_updates)
            current_thread_keys = set()
            for detail in details.values():
                for thread in detail['threads'] or []:
                    current_thread_keys.add((detail['pid'], detail['create_time'], thread['id']))
            for key in list(self._thread_detail_cpu):
                if key not in current_thread_keys:
                    del self._thread_detail_cpu[key]
            self._thread_detail_cpu.update(thread_cache_updates)
        children_by_parent = {}
        for detail in details.values():
            children_by_parent.setdefault(detail['ppid'], []).append(detail)
        for children in children_by_parent.values():
            children.sort(key=lambda item: item['pid'])
        seen = set()

        def attach(detail):
            if detail['pid'] in seen:
                return
            seen.add(detail['pid'])
            for child in children_by_parent.get(detail['pid'], []):
                if child['pid'] in seen:
                    continue
                detail['children'].append(child)
                attach(child)

        root_pid = _non_negative_int(getattr(root, 'pid', 0))
        root_detail = details.get(root_pid) if root_pid else None
        if root_detail is None:
            root_detail = details[sorted(details)[0]]
        roots = [root_detail]
        attach(root_detail)
        for detail in sorted(details.values(), key=lambda item: item['pid']):
            if detail['pid'] not in seen:
                attach(detail)
                roots.append(detail)
        thread_count = sum((detail['thread_count'] or 0) for detail in details.values())
        return {
            'available': True,
            'sampled_at': time.time(),
            'root_pid': root_pid or None,
            'process_count': len(details),
            'thread_count': thread_count,
            'roots': roots,
        }

    @staticmethod
    def _detail_unavailable(pid, reason):
        return {
            'available': False,
            'reason': reason,
            'pid': pid,
            'sampled_at': time.time(),
            'open_files': None,
            'connections': None,
            'memory_full': None,
            'memory_maps': None,
            'errors': [],
        }

    @staticmethod
    def _detail_value(label, func, errors):
        if func is None:
            errors.append(label)
            return None
        try:
            return func()
        except Exception:
            errors.append(label)
            return None

    @staticmethod
    def _limited_detail(items, mapper):
        if items is None:
            return None
        values = list(items)
        return {
            'count': len(values),
            'items': [mapper(item) for item in values[:PROCESS_DETAIL_ITEMS_LIMIT]],
            'truncated': len(values) > PROCESS_DETAIL_ITEMS_LIMIT,
        }

    @staticmethod
    def _process_connections(proc):
        method = getattr(proc, 'net_connections', None)
        if callable(method):
            return method(kind='inet')
        method = getattr(proc, 'connections', None)
        if callable(method):
            return method(kind='inet')
        raise AttributeError('connections unavailable')

    def process_detail_snapshot(self, pid, create_time=None):
        # 文件、连接、完整内存与映射只在用户主动展开时读取，并限制返回条目数。
        pid = _non_negative_int(pid, -1)
        root, processes = self._process_tree()
        if root is None:
            return self._detail_unavailable(pid, 'process_tree_unavailable')
        match = None
        for proc in processes:
            if _non_negative_int(getattr(proc, 'pid', -1), -1) == pid:
                match = proc
                break
        if match is None:
            return self._detail_unavailable(pid, 'process_not_found')
        actual_create_time = _round(self._safe(match.create_time, 0.0), 3)
        expected_create_time = _optional_float(create_time)
        if expected_create_time is not None and abs(actual_create_time - expected_create_time) > 0.001:
            return self._detail_unavailable(pid, 'process_changed')
        errors = []
        open_files = self._detail_value('open_files', getattr(match, 'open_files', None), errors)
        connections = self._detail_value(
            'connections', lambda: self._process_connections(match), errors
        )
        memory_full = self._detail_value(
            'memory_full', getattr(match, 'memory_full_info', None), errors
        )
        memory_maps = self._detail_value('memory_maps', getattr(match, 'memory_maps', None), errors)
        return {
            'available': True,
            'pid': pid,
            'create_time': actual_create_time,
            'sampled_at': time.time(),
            'open_files': self._limited_detail(open_files, _open_file_row),
            'connections': self._limited_detail(connections, _connection_row),
            'memory_full': _named_numbers(memory_full),
            'memory_maps': self._limited_detail(memory_maps, _memory_map_row),
            'errors': errors,
        }

    def _sample_io(self, now, swap=None):
        disk_io = self._safe(psutil.disk_io_counters)
        net_io = self._safe(psutil.net_io_counters)
        net_pernic_io = self._safe(lambda: psutil.net_io_counters(pernic=True))
        swap_io = swap
        result = {
            'disk_read_bps': 0.0,
            'disk_write_bps': 0.0,
            'disk_read_iops': None,
            'disk_write_iops': None,
            'disk_read_latency_ms': None,
            'disk_write_latency_ms': None,
            'net_sent_bps': 0.0,
            'net_recv_bps': 0.0,
            'packets_sent_per_second': 0.0,
            'packets_recv_per_second': 0.0,
            'errin_per_second': None,
            'errout_per_second': None,
            'dropin_per_second': None,
            'dropout_per_second': None,
            'connection_count': None,
            'tcp_states': None,
            'interfaces': [],
            'swap_in_bps': 0.0,
            'swap_out_bps': 0.0,
        }
        elapsed = 0.0 if self._last_io_at is None else max(0.0, now - self._last_io_at)
        memory_io = self._memory_io.sample()
        if elapsed > 0:
            if disk_io is not None and self._last_disk_io is not None:
                result['disk_read_bps'] = _round(_rate(
                    disk_io.read_bytes, self._last_disk_io.read_bytes, elapsed
                ))
                result['disk_write_bps'] = _round(_rate(
                    disk_io.write_bytes, self._last_disk_io.write_bytes, elapsed
                ))
                read_count_delta = _counter_delta(
                    disk_io, self._last_disk_io, 'read_count'
                )
                write_count_delta = _counter_delta(
                    disk_io, self._last_disk_io, 'write_count'
                )
                read_time_delta = _counter_delta(
                    disk_io, self._last_disk_io, 'read_time'
                )
                write_time_delta = _counter_delta(
                    disk_io, self._last_disk_io, 'write_time'
                )
                if read_count_delta is not None:
                    result['disk_read_iops'] = _round(read_count_delta / elapsed)
                    if read_count_delta > 0 and read_time_delta is not None:
                        result['disk_read_latency_ms'] = _round(
                            read_time_delta / read_count_delta
                        )
                if write_count_delta is not None:
                    result['disk_write_iops'] = _round(write_count_delta / elapsed)
                    if write_count_delta > 0 and write_time_delta is not None:
                        result['disk_write_latency_ms'] = _round(
                            write_time_delta / write_count_delta
                        )
            if net_io is not None and self._last_net_io is not None:
                result['net_sent_bps'] = _round(_rate(
                    net_io.bytes_sent, self._last_net_io.bytes_sent, elapsed
                ))
                result['net_recv_bps'] = _round(_rate(
                    net_io.bytes_recv, self._last_net_io.bytes_recv, elapsed
                ))
                result['packets_sent_per_second'] = _round(_rate(
                    net_io.packets_sent, self._last_net_io.packets_sent, elapsed
                ))
                result['packets_recv_per_second'] = _round(_rate(
                    net_io.packets_recv, self._last_net_io.packets_recv, elapsed
                ))
                for key in ('errin', 'errout', 'dropin', 'dropout'):
                    delta = _counter_delta(net_io, self._last_net_io, key)
                    if delta is not None:
                        result['%s_per_second' % key] = _round(delta / elapsed)
            interfaces = []
            if net_pernic_io is not None and self._last_net_pernic_io is not None:
                for name, current in net_pernic_io.items():
                    previous = self._last_net_pernic_io.get(name)
                    if previous is None:
                        continue
                    item = {
                        'name': _text(name, 128),
                        'sent_bps': _round(_rate(
                            current.bytes_sent, previous.bytes_sent, elapsed
                        )),
                        'recv_bps': _round(_rate(
                            current.bytes_recv, previous.bytes_recv, elapsed
                        )),
                    }
                    for key in ('errin', 'errout', 'dropin', 'dropout'):
                        delta = _counter_delta(current, previous, key)
                        item['%s_per_second' % key] = (
                            None if delta is None else _round(delta / elapsed)
                        )
                    interfaces.append(item)
            interfaces.sort(key=lambda item: item['recv_bps'] + item['sent_bps'], reverse=True)
            result['interfaces'] = interfaces[:NETWORK_INTERFACE_LIMIT]
            if memory_io is not None:
                result['swap_in_bps'] = _round(memory_io[0])
                result['swap_out_bps'] = _round(memory_io[1])
            elif swap_io is not None and self._last_swap_io is not None:
                result['swap_in_bps'] = _round(_rate(
                    getattr(swap_io, 'sin', 0), getattr(self._last_swap_io, 'sin', 0), elapsed
                ))
                result['swap_out_bps'] = _round(_rate(
                    getattr(swap_io, 'sout', 0), getattr(self._last_swap_io, 'sout', 0), elapsed
                ))
        if (
            self._last_network_connections_at is None
            or now - self._last_network_connections_at >= NETWORK_CONNECTION_REFRESH_SECONDS
        ):
            self._last_network_connections_at = now
            connections = self._safe(lambda: psutil.net_connections(kind='inet'))
            if connections is None:
                self._network_connection_count = None
                self._network_tcp_states = None
            else:
                states = {}
                for connection in connections:
                    status = _text(getattr(connection, 'status', None) or 'NONE', 32)
                    if status:
                        states[status] = states.get(status, 0) + 1
                self._network_connection_count = len(connections)
                self._network_tcp_states = states
        result['connection_count'] = self._network_connection_count
        result['tcp_states'] = copy.deepcopy(self._network_tcp_states)
        self._last_io_at = now
        self._last_disk_io = disk_io
        self._last_net_io = net_io
        self._last_net_pernic_io = net_pernic_io
        self._last_swap_io = swap_io
        return result

    def _disk_usage_metrics(self):
        volumes = []
        seen = set()
        try:
            partitions = psutil.disk_partitions(all=False)
        except Exception:
            partitions = []
        for part in partitions or []:
            mountpoint = str(getattr(part, 'mountpoint', '') or '')
            if not mountpoint:
                continue
            device = str(getattr(part, 'device', '') or '')
            key = os.path.normcase(device or mountpoint)
            if key in seen:
                continue
            seen.add(key)
            usage = self._safe(lambda path=mountpoint: psutil.disk_usage(path))
            if usage is None:
                continue
            total = max(0, int(getattr(usage, 'total', 0) or 0))
            if total <= 0:
                continue
            used = max(0, int(getattr(usage, 'used', 0) or 0))
            volumes.append({
                'device': device,
                'mountpoint': mountpoint,
                'total': total,
                'used': used,
                'percent': _round(getattr(usage, 'percent', 0.0)),
            })
        if not volumes:
            path = os.getcwd()
            usage = self._safe(lambda: psutil.disk_usage(path))
            if usage is not None:
                total = max(0, int(getattr(usage, 'total', 0) or 0))
                used = max(0, int(getattr(usage, 'used', 0) or 0))
                if total > 0:
                    volumes.append({
                        'device': '',
                        'mountpoint': path,
                        'total': total,
                        'used': used,
                        'percent': _round(getattr(usage, 'percent', 0.0)),
                    })
        volumes.sort(key=lambda item: item['mountpoint'].lower())
        total = sum(item['total'] for item in volumes)
        used = sum(item['used'] for item in volumes)
        return {
            'total': total,
            'used': used,
            'percent': _round(used * 100.0 / total) if total > 0 else 0.0,
            'volume_count': len(volumes),
            'volumes': volumes,
        }

    def _sample_performance(self):
        now = time.monotonic()
        cpu_percent = self._safe(lambda: psutil.cpu_percent(interval=None), 0.0)
        cpu_count = self._safe(lambda: psutil.cpu_count(logical=True), None)
        cpu_physical_count = self._safe(lambda: psutil.cpu_count(logical=False), None)
        cpu_frequency = self._safe(psutil.cpu_freq, None)
        per_cpu_percent = self._safe(
            lambda: psutil.cpu_percent(interval=None, percpu=True), []
        )
        if not isinstance(per_cpu_percent, (list, tuple)):
            per_cpu_percent = []
        load_func = getattr(psutil, 'getloadavg', None)
        load = self._safe(load_func, None) if callable(load_func) else None
        memory = self._safe(psutil.virtual_memory)
        swap = self._safe(psutil.swap_memory)
        disk_usage = self._disk_usage_metrics()
        io = self._sample_io(now, swap)
        process = self._process_tree_metrics()
        load_1 = load_5 = load_15 = None
        if load is not None and len(load) >= 3:
            load_1, load_5, load_15 = (_round(load[0]), _round(load[1]), _round(load[2]))
        memory_total = max(0, int(getattr(memory, 'total', 0) or 0))
        memory_used = max(0, int(getattr(memory, 'used', 0) or 0))
        memory_available = max(0, int(getattr(memory, 'available', 0) or 0))
        memory_percent = _round(getattr(memory, 'percent', 0.0) if memory is not None else 0.0)
        swap_percent = _round(getattr(swap, 'percent', 0.0)) if swap is not None else None
        frequency_mhz = (
            _optional_non_negative_float(getattr(cpu_frequency, 'current', None))
            if cpu_frequency is not None else None
        )
        disk_total = disk_usage['total']
        disk_used = disk_usage['used']
        disk_percent = disk_usage['percent']
        return {
            'sampled_at': time.time(),
            'system': dict(self.system_info),
            'cpu': {
                'percent': _round(cpu_percent),
                'count': max(0, int(cpu_count or 0)),
                'load_1': load_1,
                'load_5': load_5,
                'load_15': load_15,
                'physical_count': _optional_int(cpu_physical_count),
                'frequency_mhz': None if frequency_mhz is None else _round(frequency_mhz),
                'per_cpu_percent': [_round(item) for item in per_cpu_percent],
            },
            'memory': {
                'total': memory_total,
                'used': memory_used,
                'available': memory_available,
                'free': _optional_int(getattr(memory, 'free', None)),
                'percent': memory_percent,
                'cached': _optional_int(getattr(memory, 'cached', None)),
                'buffers': _optional_int(getattr(memory, 'buffers', None)),
                'shared': _optional_int(getattr(memory, 'shared', None)),
                'swap_total': _optional_int(getattr(swap, 'total', None)),
                'swap_used': _optional_int(getattr(swap, 'used', None)),
                'swap_free': _optional_int(getattr(swap, 'free', None)),
                'swap_percent': swap_percent,
                'swap_in_bps': io['swap_in_bps'],
                'swap_out_bps': io['swap_out_bps'],
                'page_faults': None,
            },
            'disk': {
                'path': os.getcwd(),
                'total': disk_total,
                'used': disk_used,
                'percent': disk_percent,
                'volume_count': disk_usage['volume_count'],
                'volumes': disk_usage['volumes'],
                'read_bps': io['disk_read_bps'],
                'write_bps': io['disk_write_bps'],
                'read_iops': io['disk_read_iops'],
                'write_iops': io['disk_write_iops'],
                'read_latency_ms': io['disk_read_latency_ms'],
                'write_latency_ms': io['disk_write_latency_ms'],
            },
            'network': {
                'sent_bps': io['net_sent_bps'],
                'recv_bps': io['net_recv_bps'],
                'packets_sent_per_second': io['packets_sent_per_second'],
                'packets_recv_per_second': io['packets_recv_per_second'],
                'errin_per_second': io['errin_per_second'],
                'errout_per_second': io['errout_per_second'],
                'dropin_per_second': io['dropin_per_second'],
                'dropout_per_second': io['dropout_per_second'],
                'connection_count': io['connection_count'],
                'tcp_states': io['tcp_states'],
                'interfaces': io['interfaces'],
            },
            'process': process,
        }

    def sample(self):
        sample = self._sample_performance()
        now = time.monotonic()
        with self.lock:
            self._last_sample = sample
            self._last_sample_at = sample['sampled_at']
            record = {
                'ts': sample['sampled_at'],
                'cpu_percent': sample['cpu']['percent'],
                'load_1': sample['cpu']['load_1'],
                'memory_percent': sample['memory']['percent'],
                'swap_percent': _non_negative_float(sample['memory'].get('swap_percent'), 0.0),
                'swap_in_bps': sample['memory']['swap_in_bps'],
                'swap_out_bps': sample['memory']['swap_out_bps'],
                'disk_percent': sample['disk']['percent'],
                'disk_read_bps': sample['disk']['read_bps'],
                'disk_write_bps': sample['disk']['write_bps'],
                'network_recv_bps': sample['network']['recv_bps'],
                'network_sent_bps': sample['network']['sent_bps'],
                'process_count': sample['process']['count'],
                'process_rss': sample['process']['rss'],
                'process_cpu_percent': sample['process']['cpu_percent'],
                'process_threads': sample['process']['threads'],
                'process_handles': sample['process']['handles'],
            }
            self.performance_history.append(record)
            self.performance_long_history.append(dict(record))
            self._update_performance_rollup_locked(record)
            self._roll_traffic_bucket_locked(now)
        return sample

    def _roll_traffic_bucket_locked(self, now):
        if now - self._traffic_bucket_started_at < self.traffic_bucket_seconds:
            return
        bucket = {
            'ts': time.time(),
            'inbound': self._pending_traffic['inbound'],
            'outbound': self._pending_traffic['outbound'],
            'events': self._pending_traffic['events'],
            'failed': self._pending_traffic['failed'],
        }
        self.traffic_history.append(bucket)
        self.traffic_long_history.append(dict(bucket))
        self._update_traffic_rollup_locked(bucket)
        self._pending_traffic = {'inbound': 0, 'outbound': 0, 'events': 0, 'failed': 0}
        self._traffic_bucket_started_at = now

    def on_control_rx(self, packet):
        if getattr(packet, 'action', None) != 'send':
            return
        key = getattr(packet, 'key', None)
        if not isinstance(key, dict):
            return
        data = key.get('data')
        if not isinstance(data, dict) or data.get('action') != 'traffic':
            return
        inbound = _non_negative_int(data.get('inbound'))
        outbound = _non_negative_int(data.get('outbound'))
        events = _non_negative_int(data.get('events'))
        failed = _non_negative_int(data.get('failed'))
        if not (inbound or outbound or events or failed):
            return
        with self.lock:
            self.inbound_total += inbound
            self.outbound_total += outbound
            self.event_total += events
            self.failed_total += failed
            self._pending_traffic['inbound'] += inbound
            self._pending_traffic['outbound'] += outbound
            self._pending_traffic['events'] += events
            self._pending_traffic['failed'] += failed
            self._roll_traffic_bucket_locked(time.monotonic())

    def _traffic_rate(self, history, key, now_wall):
        start = max(self._traffic_window_started_at, now_wall - 60.0)
        elapsed = max(1.0, now_wall - start)
        total = sum(
            _non_negative_int(item.get(key))
            for item in history
            if _non_negative_float(item.get('ts')) >= start
        )
        return _round(total * 60.0 / elapsed)

    def _history_series(self, key, history=None):
        source = self.performance_history if history is None else history
        return [item.get(key) for item in source]

    @staticmethod
    def _rollup_start(timestamp, interval):
        timestamp = _optional_float(timestamp)
        if timestamp is None:
            return None
        return int(timestamp // interval) * interval

    @staticmethod
    def _new_performance_rollup(start):
        return {
            'ts': start,
            'sums': {key: 0.0 for key in PERFORMANCE_HISTORY_KEYS},
            'counts': {key: 0 for key in PERFORMANCE_HISTORY_KEYS},
        }

    @staticmethod
    def _performance_rollup_record(current):
        record = {'ts': current['ts']}
        for key in PERFORMANCE_HISTORY_KEYS:
            count = current['counts'][key]
            record[key] = (
                _round(current['sums'][key] / count) if count else None
            )
        return record

    def _update_performance_rollup_locked(self, record):
        start = self._rollup_start(record.get('ts'), ROLLUP_INTERVAL_SECONDS)
        if start is None:
            return
        current = self._performance_rollup_current
        if current is None:
            current = self._new_performance_rollup(start)
            self._performance_rollup_current = current
        elif start > current['ts']:
            self.performance_rollup_history.append(
                self._performance_rollup_record(current)
            )
            current = self._new_performance_rollup(start)
            self._performance_rollup_current = current
        for key in PERFORMANCE_HISTORY_KEYS:
            value = _optional_float(record.get(key))
            if value is None:
                continue
            current['sums'][key] += value
            current['counts'][key] += 1

    def _performance_rollup_source_locked(self):
        source = list(self.performance_rollup_history)
        if self._performance_rollup_current is not None:
            source.append(self._performance_rollup_record(
                self._performance_rollup_current
            ))
        return source

    @staticmethod
    def _new_traffic_rollup(start):
        return {
            'ts': start,
            'inbound': 0,
            'outbound': 0,
            'events': 0,
            'failed': 0,
        }

    def _update_traffic_rollup_locked(self, bucket):
        start = self._rollup_start(bucket.get('ts'), ROLLUP_INTERVAL_SECONDS)
        if start is None:
            return
        current = self._traffic_rollup_current
        if current is None:
            current = self._new_traffic_rollup(start)
            self._traffic_rollup_current = current
        elif start > current['ts']:
            self.traffic_rollup_history.append(dict(current))
            current = self._new_traffic_rollup(start)
            self._traffic_rollup_current = current
        for key in ('inbound', 'outbound', 'events', 'failed'):
            current[key] += _non_negative_int(bucket.get(key))

    def _traffic_rollup_source_locked(self):
        source = list(self.traffic_rollup_history)
        if self._traffic_rollup_current is not None:
            source.append(dict(self._traffic_rollup_current))
        return source

    @staticmethod
    def _window_groups(items, start, width, capacity):
        groups = {}
        if width <= 0 or capacity <= 0:
            return groups
        for item in items:
            timestamp = _optional_float(item.get('ts'))
            if timestamp is None or timestamp < start:
                continue
            index = int((timestamp - start) / width)
            index = max(0, min(capacity - 1, index))
            groups.setdefault(index, []).append(item)
        return groups

    def _performance_window(self, name, now_wall, rollup_source=None):
        config = WINDOW_CONFIG[name]
        seconds = config['seconds']
        capacity = config['points']
        width = seconds / float(capacity)
        start = now_wall - seconds
        source = rollup_source if config['rollup'] else self.performance_long_history
        groups = self._window_groups(
            source, start, width, capacity
        )
        result = {
            'interval': _round(width, 3),
            'capacity': capacity,
            'timestamps': [],
        }
        for key in PERFORMANCE_HISTORY_KEYS:
            result[key] = []
        last_values = {key: 0 for key in PERFORMANCE_HISTORY_KEYS}
        for index in range(capacity):
            group = groups.get(index)
            if group:
                result['timestamps'].append(group[-1].get('ts'))
            else:
                result['timestamps'].append(min(now_wall, start + (index + 1) * width))
            for key in PERFORMANCE_HISTORY_KEYS:
                if not group:
                    result[key].append(last_values[key])
                    continue
                if config['rollup'] or key in PERFORMANCE_RATE_KEYS:
                    values = [
                        _optional_float(item.get(key)) for item in group
                    ]
                    values = [value for value in values if value is not None]
                    value = _round(sum(values) / len(values)) if values else None
                else:
                    value = group[-1].get(key)
                if value is None:
                    value = last_values[key]
                last_values[key] = value
                result[key].append(value)
        return result

    def _traffic_window(self, name, now_wall, raw_source, rollup_source):
        config = WINDOW_CONFIG[name]
        seconds = config['seconds']
        if config['rollup']:
            source = rollup_source
            capacity = config['points']
        else:
            source = raw_source
            capacity = min(
                WINDOW_POINTS,
                max(2, int(math.ceil(seconds / self.traffic_bucket_seconds))),
            )
        width = seconds / float(capacity)
        start = now_wall - seconds
        groups = self._window_groups(source, start, width, capacity)
        result = {
            'interval': _round(width, 3),
            'capacity': capacity,
            'timestamps': [],
            'inbound': [],
            'outbound': [],
            'events': [],
            'failed': [],
        }
        for index in range(capacity):
            group = groups.get(index)
            if group:
                result['timestamps'].append(group[-1].get('ts'))
            else:
                result['timestamps'].append(min(now_wall, start + (index + 1) * width))
            for key in ('inbound', 'outbound', 'events', 'failed'):
                result[key].append(
                    sum(_non_negative_int(item.get(key)) for item in group)
                    if group else 0
                )
        return result

    def snapshot(self, include_windows=False):
        try:
            with self.lock:
                if self._last_sample is None:
                    return unavailable_snapshot('statistics_warming_up')
                performance = copy.deepcopy(self._last_sample)
                performance['history'] = {
                    'interval': _non_negative_float(self.Proc_info.scan_interval, 1.0),
                    'capacity': self.history_size,
                    'timestamps': self._history_series('ts'),
                    'cpu_percent': self._history_series('cpu_percent'),
                    'load_1': self._history_series('load_1'),
                    'memory_percent': self._history_series('memory_percent'),
                    'swap_percent': self._history_series('swap_percent'),
                    'swap_in_bps': self._history_series('swap_in_bps'),
                    'swap_out_bps': self._history_series('swap_out_bps'),
                    'disk_percent': self._history_series('disk_percent'),
                    'disk_read_bps': self._history_series('disk_read_bps'),
                    'disk_write_bps': self._history_series('disk_write_bps'),
                    'network_recv_bps': self._history_series('network_recv_bps'),
                    'network_sent_bps': self._history_series('network_sent_bps'),
                    'process_count': self._history_series('process_count'),
                    'process_rss': self._history_series('process_rss'),
                    'process_cpu_percent': self._history_series('process_cpu_percent'),
                    'process_threads': self._history_series('process_threads'),
                    'process_handles': self._history_series('process_handles'),
                }
                performance['sampling'] = {
                    'interval': _non_negative_float(self.Proc_info.scan_interval, 1.0),
                    'history_capacity': self.history_size,
                    'long_history_capacity': self.performance_long_history.maxlen,
                    'rollup_interval': ROLLUP_INTERVAL_SECONDS,
                    'rollup_capacity': self.performance_rollup_history.maxlen,
                    'last_sampled_at': self._last_sample_at,
                }
                now_wall = time.time()
                history = [dict(item) for item in self.traffic_history]
                pending = dict(self._pending_traffic)
                if any(pending.values()):
                    history.append(dict(pending, ts=now_wall))
                long_history = [dict(item) for item in self.traffic_long_history]
                if any(pending.values()):
                    long_history.append(dict(pending, ts=now_wall))
                traffic = {
                    'inbound_total': self.inbound_total,
                    'outbound_total': self.outbound_total,
                    'event_total': self.event_total,
                    'failed_total': self.failed_total,
                    'inbound_per_minute': self._traffic_rate(history, 'inbound', now_wall),
                    'outbound_per_minute': self._traffic_rate(history, 'outbound', now_wall),
                    'event_per_minute': self._traffic_rate(history, 'events', now_wall),
                    'failed_per_minute': self._traffic_rate(history, 'failed', now_wall),
                    'bucket_seconds': self.traffic_bucket_seconds,
                    'history_capacity': self.traffic_history_size,
                    'history': history,
                }
                if include_windows:
                    performance_rollup_source = self._performance_rollup_source_locked()
                    traffic_rollup_source = self._traffic_rollup_source_locked()
                    performance['windows'] = {
                        name: self._performance_window(
                            name, now_wall, performance_rollup_source
                        )
                        for name in WINDOW_CONFIG
                    }
                    traffic['windows'] = {
                        name: self._traffic_window(
                            name, now_wall, long_history, traffic_rollup_source
                        )
                        for name in WINDOW_CONFIG
                    }
                return {
                    'available': True,
                    'sampled_at': self._last_sample_at,
                    'performance': performance,
                    'traffic': traffic,
                }
        except Exception:
            return unavailable_snapshot()

    def run(self):
        self.log(2, 'OlivOS statistics monitor is running')
        while not self.stop_event.is_set():
            try:
                self.sample()
            except Exception:
                self.log(4, 'statistics sample failed: %s' % traceback.format_exc())
            self.stop_event.wait(self.Proc_info.scan_interval)
        self._memory_io.close()

    def on_terminate(self):
        self.stop_event.set()
