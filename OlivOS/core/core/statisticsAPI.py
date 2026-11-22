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
import os
import platform
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
TRAFFIC_TARGET = {'type': 'statistics', 'fliter': 'control_only'}


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


def _rate(current, previous, elapsed):
    if previous is None or elapsed <= 0:
        return 0.0
    return max(0.0, (current - previous) / elapsed)


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
        self.performance_history = deque(maxlen=self.history_size)
        self.traffic_history = deque(maxlen=self.traffic_history_size)
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
        self._last_swap_io = None
        self._memory_io = _WindowsMemoryIO()
        self._last_process_cpu_at = None
        self._last_process_cpu_total = 0.0

    @staticmethod
    def _safe(func, default=None):
        try:
            return func()
        except Exception:
            return default

    def _process_tree_totals(self):
        result = {'count': 0, 'rss': 0, 'cpu_percent': 0.0, 'threads': None, 'handles': None}
        try:
            root = psutil.Process(os.getpid())
            processes = [root] + root.children(recursive=True)
        except Exception:
            return result, None
        result['count'] = len(processes)
        rss = 0
        cpu_seconds = 0.0
        threads = 0
        handles = 0
        threads_ok = True
        handles_ok = platform.system() == 'Windows'
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
            except Exception:
                continue
        result['rss'] = max(0, int(rss))
        result['threads'] = threads if threads_ok else None
        result['handles'] = handles if handles_ok else None
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

    def _sample_io(self, now, swap=None):
        disk_io = self._safe(psutil.disk_io_counters)
        net_io = self._safe(psutil.net_io_counters)
        swap_io = swap
        result = {
            'disk_read_bps': 0.0,
            'disk_write_bps': 0.0,
            'net_sent_bps': 0.0,
            'net_recv_bps': 0.0,
            'packets_sent_per_second': 0.0,
            'packets_recv_per_second': 0.0,
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
        self._last_io_at = now
        self._last_disk_io = disk_io
        self._last_net_io = net_io
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
        disk_total = disk_usage['total']
        disk_used = disk_usage['used']
        disk_percent = disk_usage['percent']
        return {
            'sampled_at': time.time(),
            'cpu': {
                'percent': _round(cpu_percent),
                'count': max(0, int(cpu_count or 0)),
                'load_1': load_1,
                'load_5': load_5,
                'load_15': load_15,
            },
            'memory': {
                'total': memory_total,
                'used': memory_used,
                'available': memory_available,
                'percent': memory_percent,
                'swap_percent': swap_percent,
                'swap_in_bps': io['swap_in_bps'],
                'swap_out_bps': io['swap_out_bps'],
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
            },
            'network': {
                'sent_bps': io['net_sent_bps'],
                'recv_bps': io['net_recv_bps'],
                'packets_sent_per_second': io['packets_sent_per_second'],
                'packets_recv_per_second': io['packets_recv_per_second'],
            },
            'process': process,
        }

    def sample(self):
        sample = self._sample_performance()
        now = time.monotonic()
        with self.lock:
            self._last_sample = sample
            self._last_sample_at = sample['sampled_at']
            self.performance_history.append({
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
            })
            self._roll_traffic_bucket_locked(now)
        return sample

    def _roll_traffic_bucket_locked(self, now):
        if now - self._traffic_bucket_started_at < self.traffic_bucket_seconds:
            return
        self.traffic_history.append({
            'ts': time.time(),
            'inbound': self._pending_traffic['inbound'],
            'outbound': self._pending_traffic['outbound'],
            'events': self._pending_traffic['events'],
            'failed': self._pending_traffic['failed'],
        })
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

    def _history_series(self, key):
        return [item.get(key) for item in self.performance_history]

    def snapshot(self):
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
                now_wall = time.time()
                history = [dict(item) for item in self.traffic_history]
                pending = dict(self._pending_traffic)
                if any(pending.values()):
                    history.append(dict(pending, ts=now_wall))
                return {
                    'available': True,
                    'sampled_at': self._last_sample_at,
                    'performance': performance,
                    'traffic': {
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
                    },
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
