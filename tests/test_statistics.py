# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   tests/test_statistics.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   性能与消息流量统计模块的离线用例。
'''

import json
import queue
from collections import namedtuple
from unittest.mock import Mock

import OlivOS
from OlivOS.core.core import statisticsAPI


def make_recorder(control_queue=None, **kwargs):
    # 每个用例使用独立队列，避免统计增量串到其它测试。
    control_queue = control_queue if control_queue is not None else queue.Queue()
    return statisticsAPI.TrafficRecorder(control_queue=control_queue, **kwargs), control_queue


def test_traffic_recorder_aggregates_counts_into_one_packet():
    # 一次刷新只发送聚合计数，不能携带消息正文或账号标识。
    recorder, control_queue = make_recorder(flush_interval=3600, max_pending=100)
    recorder.record_inbound()
    recorder.record_outbound()
    recorder.record_event()
    recorder.record_failed()
    recorder.flush(force=True)
    packet = control_queue.get_nowait()
    assert packet.action == 'send'
    assert packet.key['target'] == {'type': 'statistics', 'fliter': 'control_only'}
    data = packet.key['data']
    assert data['action'] == 'traffic'
    assert (data['inbound'], data['outbound'], data['events'], data['failed']) == (1, 1, 2, 1)
    assert set(data) == {'action', 'inbound', 'outbound', 'events', 'failed', 'sampled_at'}
    assert json.loads(json.dumps(packet.key, ensure_ascii=False)) == packet.key


def test_traffic_recorder_flushes_at_pending_threshold():
    # 达到阈值应立即上报，不能等空闲循环慢慢刷新。
    recorder, control_queue = make_recorder(flush_interval=3600, max_pending=2)
    recorder.record_event()
    assert control_queue.empty()
    recorder.record_event()
    data = control_queue.get_nowait().key['data']
    assert data['events'] == 2
    assert control_queue.empty()


def test_traffic_recorder_swallows_full_queue_errors():
    # 队列拥塞时统计包必须被丢弃，不能影响业务消息收发。
    control_queue = queue.Queue(maxsize=1)
    control_queue.put('occupied')
    recorder, _ = make_recorder(control_queue=control_queue, flush_interval=3600)
    recorder.record_event()
    recorder.flush(force=True)
    assert control_queue.full()


def test_statistics_helpers_swallow_recorder_failures(monkeypatch):
    # 公共埋点入口自身异常时只能丢失统计，不能向上打断插件调度或消息发送。
    class BrokenRecorder(object):
        def bind(self, control_queue):
            raise RuntimeError('bind failed')

        def record_event_type(self, func_type):
            raise RuntimeError('event failed')

        def record_outbound(self):
            raise RuntimeError('outbound failed')

        def record_failed(self):
            raise RuntimeError('failed failed')

        def flush(self):
            raise RuntimeError('flush failed')

    monkeypatch.setattr(statisticsAPI, 'gTrafficRecorder', BrokenRecorder())
    statisticsAPI.bind_control_queue(queue.Queue())
    statisticsAPI.record_event_type('group_message')
    statisticsAPI.record_outbound()
    statisticsAPI.record_failed()
    statisticsAPI.flush_traffic()


def test_event_type_counts_messages_as_inbound_but_not_sent_echoes():
    # 平台回显的 *_sent 事件计入事件总量，但不能冒充用户入站消息。
    recorder, control_queue = make_recorder(flush_interval=3600)
    recorder.record_event_type('group_message')
    recorder.record_event_type('private_message_sent')
    recorder.record_event_type('heartbeat')
    recorder.flush(force=True)
    data = control_queue.get_nowait().key['data']
    assert data['inbound'] == 1
    assert data['outbound'] == 0
    assert data['events'] == 3


def make_terminal_event():
    # 构造一个不连接真实协议端的最小事件，用于验证 Event 出站计数入口。
    bot = OlivOS.API.bot_info_T(
        id=10001,
        platform_sdk='terminal_link',
        platform_platform='terminal',
        platform_model='default',
    )
    packet = OlivOS.API.Control.packet('send', {
        'data': {
            'data': 'hello',
            'user_conf': {
                'user_id': '42',
                'target_id': '7',
                'user_name': 'tester',
                'flag_group': True,
            },
        },
    })
    return OlivOS.API.Event(OlivOS.virtualTerminalSDK.event(packet, bot))


def test_event_send_records_one_outbound(monkeypatch):
    # 一条逻辑消息只记一次出站，不能因为公共发送路径拆成多个内部步骤而重复计数。
    event = make_terminal_event()
    record = Mock()
    monkeypatch.setattr(OlivOS.virtualTerminalSDK.event_action, 'send_msg', lambda *args, **kwargs: None)
    monkeypatch.setattr(OlivOS.statisticsAPI, 'record_outbound', record)
    event.send('group', '7', 'hello')
    record.assert_called_once_with()


def test_file_segment_send_does_not_double_count_outbound(monkeypatch):
    # 文件分片会递归调用内部发送函数，外层逻辑发送仍只能计一次出站。
    event = make_terminal_event()
    record = Mock()
    monkeypatch.setattr(event, '_Event__support_file_segment_upload', lambda *args: True)
    monkeypatch.setattr(event, '_Event__upload_group_file', lambda *args, **kwargs: None)
    monkeypatch.setattr(OlivOS.virtualTerminalSDK.event_action, 'send_msg', lambda *args, **kwargs: None)
    monkeypatch.setattr(OlivOS.statisticsAPI, 'record_outbound', record)
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('hello'),
        OlivOS.messageAPI.PARA.file('fixture.txt'),
    ])
    event.send('group', '7', message)
    record.assert_called_once_with()


def make_statistics_monitor(**kwargs):
    return statisticsAPI.server(
        Proc_name='test-statistics',
        control_queue=queue.Queue(),
        **kwargs
    )


def test_statistics_snapshot_warms_up_before_first_sample():
    # 首次采样前返回明确原因，WebUI 可显示启动中而不是抛出异常。
    monitor = make_statistics_monitor()
    snapshot = monitor.snapshot()
    assert snapshot['available'] is False
    assert snapshot['reason'] == 'statistics_warming_up'


def test_statistics_snapshot_is_json_serializable_and_history_is_bounded():
    # 快照必须能直接交给 Flask jsonify，且历史长度受配置限制。
    monitor = make_statistics_monitor(
        history_size=2, traffic_bucket_seconds=5.0, traffic_history_size=2)
    for _ in range(3):
        monitor.sample()
    snapshot = monitor.snapshot()
    assert snapshot['available'] is True
    history = snapshot['performance']['history']
    system = snapshot['performance']['system']
    assert set(system) == {
        'os', 'os_release', 'os_version', 'architecture', 'hostname',
        'cpu_model', 'python_version', 'python_implementation', 'working_directory',
    }
    assert all(value is None or isinstance(value, str) for value in system.values())
    assert history['capacity'] == 2
    assert isinstance(history['cpu_percent'], list)
    assert len(history['cpu_percent']) <= 2
    # 性能页依赖各历史数组严格对齐，任意新增序列都不能单独变长或变短。
    series_names = (
        'cpu_percent', 'load_1', 'memory_percent', 'swap_percent', 'swap_in_bps', 'swap_out_bps',
        'disk_percent',
        'disk_read_bps', 'disk_write_bps', 'network_recv_bps', 'network_sent_bps',
        'process_count', 'process_rss', 'process_cpu_percent', 'process_threads',
        'process_handles',
    )
    lengths = {name: len(history[name]) for name in series_names}
    assert set(lengths.values()) == {len(history['timestamps'])}
    assert history['timestamps'] == sorted(history['timestamps'])
    # 流量快照要暴露桶时长和历史容量，便于前端直接展示历史桶计数并换算顶部速率。
    assert snapshot['traffic']['bucket_seconds'] == 5.0
    assert snapshot['traffic']['history_capacity'] == 2
    assert json.loads(json.dumps(snapshot, ensure_ascii=False)) == snapshot


def test_statistics_system_metadata_reports_platform_details(monkeypatch):
    # 概览页展示的静态配置来自进程内缓存的系统信息，Linux 优先读取 CPU 型号。
    monkeypatch.setattr(statisticsAPI.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(statisticsAPI.platform, 'release', lambda: '6.8.0-test')
    monkeypatch.setattr(statisticsAPI.platform, 'version', lambda: '#1 SMP PREEMPT')
    monkeypatch.setattr(statisticsAPI.platform, 'machine', lambda: 'x86_64')
    monkeypatch.setattr(statisticsAPI.platform, 'node', lambda: 'olivos-host')
    monkeypatch.setattr(statisticsAPI.platform, 'processor', lambda: '')
    monkeypatch.setattr(statisticsAPI.platform, 'python_version', lambda: '3.11.9')
    monkeypatch.setattr(statisticsAPI.platform, 'python_implementation', lambda: 'CPython')
    monkeypatch.setattr(statisticsAPI, '_linux_cpu_model', lambda: 'Test CPU 9000')
    monkeypatch.setattr(statisticsAPI.os, 'getcwd', lambda: '/srv/olivos')

    assert statisticsAPI._system_metadata() == {
        'os': 'Linux',
        'os_release': '6.8.0-test',
        'os_version': '#1 SMP PREEMPT',
        'architecture': 'x86_64',
        'hostname': 'olivos-host',
        'cpu_model': 'Test CPU 9000',
        'python_version': '3.11.9',
        'python_implementation': 'CPython',
        'working_directory': '/srv/olivos',
    }


def test_statistics_system_metadata_falls_back_to_architecture(monkeypatch):
    # processor 在部分平台为空，此时应回退到机器架构而不是让概览字段缺失。
    monkeypatch.setattr(statisticsAPI.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(statisticsAPI.platform, 'release', lambda: '11')
    monkeypatch.setattr(statisticsAPI.platform, 'version', lambda: '10.0.22631')
    monkeypatch.setattr(statisticsAPI.platform, 'machine', lambda: 'AMD64')
    monkeypatch.setattr(statisticsAPI.platform, 'node', lambda: 'olivos-host')
    monkeypatch.setattr(statisticsAPI.platform, 'processor', lambda: 'Intel64 Family 6')
    monkeypatch.setattr(statisticsAPI.platform, 'python_version', lambda: '3.11.9')
    monkeypatch.setattr(statisticsAPI.platform, 'python_implementation', lambda: 'CPython')
    monkeypatch.setattr(statisticsAPI.os, 'getcwd', lambda: 'D:/OlivOS')

    assert statisticsAPI._system_metadata()['cpu_model'] == 'Intel64 Family 6'
    assert statisticsAPI._system_metadata()['os'] == 'Windows'
    monkeypatch.setattr(statisticsAPI.platform, 'processor', lambda: '')
    assert statisticsAPI._system_metadata()['cpu_model'] == 'AMD64'


def test_statistics_windows_are_opt_in_and_downsampled(monkeypatch):
    # 性能页的 1/5/15 分钟数据只能按需附加；每个窗口固定 60 点，空桶沿用相邻有效值。
    monitor = make_statistics_monitor(history_size=1200, scan_interval=1.0)
    now = 1000000.0
    monkeypatch.setattr(statisticsAPI.time, 'time', lambda: now)
    monitor._last_sample = {'sampled_at': now}
    monitor._last_sample_at = now
    for index in range(1000):
        record = {
            'ts': now - 999 + index,
            'cpu_percent': float(index % 100),
            'load_1': 1.0,
            'memory_percent': 20.0,
            'swap_percent': 0.0,
            'swap_in_bps': 10.0,
            'swap_out_bps': 20.0,
            'disk_percent': 30.0,
            'disk_read_bps': 100.0,
            'disk_write_bps': 200.0,
            'network_recv_bps': 300.0,
            'network_sent_bps': 400.0,
            'process_count': 2,
            'process_rss': 1024,
            'process_cpu_percent': 5.0,
            'process_threads': 4,
            'process_handles': 6,
        }
        monitor.performance_history.append(record)
        monitor.performance_long_history.append(dict(record))
    for index in range(180):
        monitor.traffic_long_history.append({
            'ts': now - 179 * 5 + index * 5,
            'inbound': 1,
            'outbound': 2,
            'events': 3,
            'failed': 1,
        })

    default = monitor.snapshot()
    windows = monitor.snapshot(include_windows=True)

    assert 'windows' not in default['performance']
    assert 'windows' not in default['traffic']
    for name, expected_interval in [('1m', 1.0), ('5m', 5.0), ('15m', 15.0)]:
        performance = windows['performance']['windows'][name]
        assert performance['capacity'] == 60
        assert performance['interval'] == expected_interval
        assert len(performance['timestamps']) == 60
        assert len(performance['cpu_percent']) == len(performance['timestamps'])
        assert performance['swap_in_bps'][-1] == 10.0
    assert windows['traffic']['windows']['1m']['capacity'] == 12
    assert windows['traffic']['windows']['5m']['capacity'] == 60
    assert windows['traffic']['windows']['15m']['capacity'] == 60
    assert len(windows['traffic']['windows']['1m']['inbound']) == 12
    assert len(windows['traffic']['windows']['5m']['inbound']) == 60
    assert len(windows['traffic']['windows']['15m']['inbound']) == 60
    assert json.loads(json.dumps(windows, ensure_ascii=False)) == windows


def test_statistics_window_backfills_leading_buckets_and_shifts_existing_samples():
    # 固定长度窗口用最早有效值回填空桶，不能把尚未采样的区域压成 0；时间前进后旧采样整体左移。
    monitor = make_statistics_monitor(history_size=1200, scan_interval=1.0)
    now = 1000000.0
    records = [
        {'ts': now - 2, 'cpu_percent': 10.0},
        {'ts': now - 1, 'cpu_percent': 20.0},
    ]
    monitor.performance_long_history.extend(records)

    window = monitor._performance_window('1m', now)
    assert len(window['timestamps']) == window['capacity'] == 60
    assert len(window['cpu_percent']) == 60
    assert window['cpu_percent'][:58] == [10.0] * 58
    assert window['cpu_percent'][-3:] == [10.0, 20.0, 20.0]

    shifted = monitor._performance_window('1m', now + 1)
    assert shifted['cpu_percent'][:56] == [10.0] * 56
    assert shifted['cpu_percent'][-4:] == [10.0, 20.0, 20.0, 20.0]

    monitor.performance_long_history.append({'ts': now + 1, 'cpu_percent': 30.0})
    with_gap = monitor._performance_window('1m', now + 2)
    assert with_gap['cpu_percent'][-5:] == [10.0, 20.0, 20.0, 30.0, 30.0]


def test_statistics_window_keeps_completed_bucket_averages_stable():
    # 新采样只能更新最新桶；窗口推进不足一个桶时，已完成桶的平均值必须保持不变。
    monitor = make_statistics_monitor(history_size=1200, scan_interval=1.0)
    now = 1000000.0
    for offset in range(10):
        monitor.performance_long_history.append({
            'ts': now - 10 + offset,
            'swap_in_bps': 10.0 + offset,
        })
    first = monitor._performance_window('5m', now)
    assert first['swap_in_bps'][-3:] == [12.0, 17.0, 17.0]

    monitor.performance_long_history.append({'ts': now + 1, 'swap_in_bps': 100.0})
    second = monitor._performance_window('5m', now + 1)
    assert second['swap_in_bps'][-3:] == [12.0, 17.0, 100.0]

    at_boundary = monitor._performance_window('5m', now + 5)
    assert at_boundary['swap_in_bps'][-4:] == [12.0, 17.0, 100.0, 100.0]


def test_statistics_minute_rollups_average_performance_and_sum_traffic():
    # 分钟聚合层用平均值压缩性能指标，用求和保留消息流量；跨分钟后只把完整桶写入历史。
    monitor = make_statistics_monitor()
    monitor._update_performance_rollup_locked({'ts': 120, 'cpu_percent': 10.0})
    monitor._update_performance_rollup_locked({'ts': 150, 'cpu_percent': 20.0})
    monitor._update_performance_rollup_locked({'ts': 180, 'cpu_percent': 40.0})
    monitor._update_traffic_rollup_locked({
        'ts': 121, 'inbound': 1, 'outbound': 2, 'events': 3, 'failed': 1,
    })
    monitor._update_traffic_rollup_locked({
        'ts': 150, 'inbound': 2, 'outbound': 3, 'events': 4, 'failed': 2,
    })
    monitor._update_traffic_rollup_locked({
        'ts': 181, 'inbound': 4, 'outbound': 5, 'events': 6, 'failed': 3,
    })

    assert monitor.performance_rollup_history[-1]['cpu_percent'] == 15.0
    assert monitor.traffic_rollup_history[-1] == {
        'ts': 120, 'inbound': 3, 'outbound': 5, 'events': 7, 'failed': 3,
    }
    assert monitor._performance_rollup_current['ts'] == 180
    assert monitor._performance_rollup_current['sums']['cpu_percent'] == 40.0
    assert monitor._traffic_rollup_current == {
        'ts': 180, 'inbound': 4, 'outbound': 5, 'events': 6, 'failed': 3,
    }


def test_statistics_daily_windows_use_minute_rollups(monkeypatch):
    # 日级窗口只扫描约 1440 个分钟桶，不把 24 小时的原始采样塞进长期队列。
    monitor = make_statistics_monitor(scan_interval=1.0)
    now = 1000000.0
    monkeypatch.setattr(statisticsAPI.time, 'time', lambda: now)
    monitor._last_sample = {'sampled_at': now}
    monitor._last_sample_at = now
    base = int(now // 60) * 60 - 1439 * 60
    for index in range(1440):
        timestamp = base + index * 60
        monitor.performance_rollup_history.append({
            'ts': timestamp,
            'cpu_percent': float(index),
        })
        monitor.traffic_rollup_history.append({
            'ts': timestamp,
            'inbound': 1,
            'outbound': 2,
            'events': 3,
            'failed': 0,
        })

    windows = monitor.snapshot(include_windows=True)

    expected = [('1h', 60.0, 60), ('6h', 360.0, 60), ('24h', 600.0, 144)]
    for name, interval, capacity in expected:
        performance = windows['performance']['windows'][name]
        traffic = windows['traffic']['windows'][name]
        assert performance['interval'] == interval
        assert performance['capacity'] == capacity
        assert traffic['interval'] == interval
        assert traffic['capacity'] == capacity
        assert len(performance['timestamps']) == capacity
        assert len(performance['cpu_percent']) == capacity
        assert len(traffic['timestamps']) == capacity
    # 固定桶边界后，24 小时窗口从整 10 分钟刻度开始，首尾桶按实际落入的分钟聚合。
    assert windows['performance']['windows']['24h']['cpu_percent'][0] == 7.5
    assert windows['performance']['windows']['24h']['cpu_percent'][-1] == 1436.0
    assert sum(windows['traffic']['windows']['24h']['inbound']) == 1437
    assert sum(windows['traffic']['windows']['1h']['inbound']) == 60
    assert sum(windows['traffic']['windows']['6h']['inbound']) == 359
    assert monitor.performance_long_history.maxlen == 901
    assert monitor.performance_rollup_history.maxlen == 1441
    assert windows['performance']['sampling']['rollup_interval'] == 60.0
    assert windows['performance']['sampling']['rollup_capacity'] == 1441


def test_statistics_monitor_accepts_traffic_control_packets():
    # 插件进程与控制组件之间只传递批量增量，统计进程负责累计总量。
    monitor = make_statistics_monitor()
    monitor.sample()
    packet = OlivOS.API.Control.packet('send', {
        'target': {'type': 'statistics', 'fliter': 'control_only'},
        'data': {'action': 'traffic', 'inbound': 2, 'outbound': 3, 'events': 4, 'failed': 1},
    })
    monitor.on_control_rx(packet)
    traffic = monitor.snapshot()['traffic']
    assert traffic['inbound_total'] == 2
    assert traffic['outbound_total'] == 3
    assert traffic['event_total'] == 4
    assert traffic['failed_total'] == 1
    assert traffic['failed_per_minute'] >= 1


def test_statistics_disk_usage_aggregates_all_volumes(monkeypatch):
    # 磁盘容量不能只取当前工作目录所在分区，要聚合所有可访问的本地卷。
    from types import SimpleNamespace

    partitions = [
        SimpleNamespace(device='C:', mountpoint='C:\\'),
        SimpleNamespace(device='D:', mountpoint='D:\\'),
        SimpleNamespace(device='D:', mountpoint='D:\\duplicate'),
    ]
    usages = {
        'C:\\': SimpleNamespace(total=1000, used=400, percent=40.0),
        'D:\\': SimpleNamespace(total=3000, used=2400, percent=80.0),
        'D:\\duplicate': SimpleNamespace(total=9999, used=9999, percent=99.9),
    }
    monkeypatch.setattr(statisticsAPI.psutil, 'disk_partitions', lambda all=False: partitions)
    monkeypatch.setattr(statisticsAPI.psutil, 'disk_usage', lambda path: usages[path])
    monitor = make_statistics_monitor()
    disk = monitor._disk_usage_metrics()
    assert disk['volume_count'] == 2
    assert disk['total'] == 4000
    assert disk['used'] == 2800
    assert disk['percent'] == 70.0
    assert [item['mountpoint'] for item in disk['volumes']] == ['C:\\', 'D:\\']


def test_statistics_performance_reports_extended_system_details(monkeypatch):
    # 性能页需要 CPU 物理核心、频率、每核心使用率，以及内存、磁盘、网络细分字段。
    from types import SimpleNamespace

    def cpu_percent(interval=None, percpu=False):
        return [10.0, 20.0, 30.0, 40.0] if percpu else 25.0

    def net_io_counters(pernic=False):
        if pernic:
            return {}
        return SimpleNamespace(
            bytes_sent=100, bytes_recv=200, packets_sent=3, packets_recv=4,
            errin=1, errout=2, dropin=3, dropout=4,
        )

    monkeypatch.setattr(statisticsAPI.psutil, 'cpu_percent', cpu_percent)
    monkeypatch.setattr(
        statisticsAPI.psutil, 'cpu_count',
        lambda logical=True: 4 if logical else 2,
    )
    monkeypatch.setattr(
        statisticsAPI.psutil, 'cpu_freq',
        lambda: SimpleNamespace(current=2400.0),
        raising=False,
    )
    monkeypatch.setattr(statisticsAPI.psutil, 'getloadavg', lambda: (1.25, 1.0, 0.8))
    monkeypatch.setattr(statisticsAPI.psutil, 'virtual_memory', lambda: SimpleNamespace(
        total=1000, used=400, available=600, free=100, percent=40.0,
        cached=200, buffers=50, shared=25,
    ))
    monkeypatch.setattr(statisticsAPI.psutil, 'swap_memory', lambda: SimpleNamespace(
        total=500, used=125, free=375, percent=25.0, sin=0, sout=0,
    ))
    monkeypatch.setattr(statisticsAPI.psutil, 'disk_partitions', lambda all=False: [])
    monkeypatch.setattr(
        statisticsAPI.psutil, 'disk_usage',
        lambda path: SimpleNamespace(total=1000, used=400, percent=40.0),
    )
    monkeypatch.setattr(statisticsAPI.psutil, 'disk_io_counters', lambda: SimpleNamespace(
        read_bytes=0, write_bytes=0, read_count=0, write_count=0,
        read_time=0, write_time=0,
    ))
    monkeypatch.setattr(statisticsAPI.psutil, 'net_io_counters', net_io_counters)
    monkeypatch.setattr(statisticsAPI.psutil, 'net_connections', lambda kind='inet': [
        SimpleNamespace(status='ESTABLISHED'),
        SimpleNamespace(status='ESTABLISHED'),
        SimpleNamespace(status='TIME_WAIT'),
    ])
    monitor = make_statistics_monitor()
    monitor._memory_io.disabled = True

    sample = monitor._sample_performance()

    assert sample['cpu']['physical_count'] == 2
    assert sample['cpu']['frequency_mhz'] == 2400.0
    assert sample['cpu']['per_cpu_percent'] == [10.0, 20.0, 30.0, 40.0]
    assert sample['memory']['free'] == 100
    assert sample['memory']['cached'] == 200
    assert sample['memory']['buffers'] == 50
    assert sample['memory']['shared'] == 25
    assert sample['memory']['swap_total'] == 500
    assert sample['memory']['swap_used'] == 125
    assert sample['memory']['swap_free'] == 375
    assert sample['memory']['page_faults'] is None
    assert sample['disk']['read_iops'] is None
    assert sample['network']['connection_count'] == 3
    assert sample['network']['tcp_states'] == {'ESTABLISHED': 2, 'TIME_WAIT': 1}
    assert sample['network']['interfaces'] == []


def test_statistics_performance_tolerates_missing_cpu_frequency(monkeypatch):
    # macOS ARM 等平台可能不导出 psutil.cpu_freq，采集应降级为未知频率而不是抛错。
    monkeypatch.delattr(statisticsAPI.psutil, 'cpu_freq', raising=False)
    monitor = make_statistics_monitor()

    sample = monitor._sample_performance()

    assert sample['cpu']['frequency_mhz'] is None


def test_statistics_disk_io_reports_iops_and_latency(monkeypatch):
    # 磁盘质量指标使用累计计数差值；计数不增长时延迟必须为 None，不能显示假的 0 ms。
    from types import SimpleNamespace

    readings = [
        SimpleNamespace(
            read_bytes=1000, write_bytes=2000, read_count=10, write_count=20,
            read_time=100, write_time=200,
        ),
        SimpleNamespace(
            read_bytes=3000, write_bytes=4000, read_count=30, write_count=40,
            read_time=160, write_time=240,
        ),
        SimpleNamespace(
            read_bytes=5000, write_bytes=6000, read_count=30, write_count=40,
            read_time=220, write_time=280,
        ),
    ]
    net = SimpleNamespace(
        bytes_sent=0, bytes_recv=0, packets_sent=0, packets_recv=0,
        errin=0, errout=0, dropin=0, dropout=0,
    )
    monkeypatch.setattr(statisticsAPI.psutil, 'disk_io_counters', lambda: readings.pop(0))
    monkeypatch.setattr(statisticsAPI.psutil, 'net_io_counters', lambda pernic=False: {} if pernic else net)
    monkeypatch.setattr(statisticsAPI.psutil, 'net_connections', lambda kind='inet': [])
    monitor = make_statistics_monitor()
    monitor._memory_io.disabled = True

    monitor._sample_io(100.0)
    sample = monitor._sample_io(102.0)
    stalled = monitor._sample_io(104.0)

    assert sample['disk_read_iops'] == 10.0
    assert sample['disk_write_iops'] == 10.0
    assert sample['disk_read_latency_ms'] == 3.0
    assert sample['disk_write_latency_ms'] == 2.0
    assert stalled['disk_read_iops'] == 0.0
    assert stalled['disk_write_iops'] == 0.0
    assert stalled['disk_read_latency_ms'] is None
    assert stalled['disk_write_latency_ms'] is None


def test_statistics_network_reports_packet_quality_and_interfaces(monkeypatch):
    # 网络质量包含聚合错误/丢包、连接状态和按网卡吞吐；网卡按吞吐降序排列。
    from types import SimpleNamespace

    net_readings = [
        SimpleNamespace(
            bytes_sent=100, bytes_recv=200, packets_sent=10, packets_recv=20,
            errin=1, errout=1, dropin=1, dropout=1,
        ),
        SimpleNamespace(
            bytes_sent=1100, bytes_recv=2200, packets_sent=30, packets_recv=40,
            errin=3, errout=2, dropin=4, dropout=5,
        ),
    ]
    pernic_readings = [
        {
            'eth0': SimpleNamespace(
                bytes_sent=100, bytes_recv=200, errin=1, errout=1,
                dropin=1, dropout=1,
            ),
            'wlan0': SimpleNamespace(
                bytes_sent=10, bytes_recv=20, errin=0, errout=0,
                dropin=0, dropout=0,
            ),
        },
        {
            'eth0': SimpleNamespace(
                bytes_sent=1100, bytes_recv=2200, errin=3, errout=2,
                dropin=4, dropout=5,
            ),
            'wlan0': SimpleNamespace(
                bytes_sent=210, bytes_recv=620, errin=0, errout=0,
                dropin=0, dropout=0,
            ),
        },
    ]
    disk = SimpleNamespace(
        read_bytes=0, write_bytes=0, read_count=0, write_count=0,
        read_time=0, write_time=0,
    )
    monkeypatch.setattr(statisticsAPI.psutil, 'disk_io_counters', lambda: disk)
    monkeypatch.setattr(statisticsAPI.psutil, 'net_io_counters', lambda pernic=False: (
        pernic_readings.pop(0) if pernic else net_readings.pop(0)
    ))
    monkeypatch.setattr(statisticsAPI.psutil, 'net_connections', lambda kind='inet': [
        SimpleNamespace(status='ESTABLISHED'),
        SimpleNamespace(status='TIME_WAIT'),
    ])
    monitor = make_statistics_monitor()
    monitor._memory_io.disabled = True

    monitor._sample_io(100.0)
    sample = monitor._sample_io(102.0)

    assert sample['errin_per_second'] == 1.0
    assert sample['errout_per_second'] == 0.5
    assert sample['dropin_per_second'] == 1.5
    assert sample['dropout_per_second'] == 2.0
    assert sample['connection_count'] == 2
    assert sample['tcp_states'] == {'ESTABLISHED': 1, 'TIME_WAIT': 1}
    assert [item['name'] for item in sample['interfaces']] == ['eth0', 'wlan0']
    assert sample['interfaces'][0]['recv_bps'] == 1000.0
    assert sample['interfaces'][0]['sent_bps'] == 500.0
    assert sample['interfaces'][1]['recv_bps'] == 300.0


def test_statistics_network_connection_failure_degrades_to_null(monkeypatch):
    # 连接枚举在权限不足时必须降级为 None，不能拖垮网络带宽其它指标。
    from types import SimpleNamespace

    net = SimpleNamespace(
        bytes_sent=100, bytes_recv=200, packets_sent=3, packets_recv=4,
        errin=0, errout=0, dropin=0, dropout=0,
    )
    disk = SimpleNamespace(
        read_bytes=0, write_bytes=0, read_count=0, write_count=0,
        read_time=0, write_time=0,
    )

    def denied(kind='inet'):
        raise PermissionError('connection table denied')

    monkeypatch.setattr(statisticsAPI.psutil, 'disk_io_counters', lambda: disk)
    monkeypatch.setattr(statisticsAPI.psutil, 'net_io_counters', lambda pernic=False: {} if pernic else net)
    monkeypatch.setattr(statisticsAPI.psutil, 'net_connections', denied)
    monitor = make_statistics_monitor()
    monitor._memory_io.disabled = True

    sample = monitor._sample_io(100.0)

    assert sample['connection_count'] is None
    assert sample['tcp_states'] is None
    assert sample['net_recv_bps'] == 0.0


def test_statistics_swap_io_uses_counter_delta(monkeypatch):
    # 内存 IO 使用交换区累计计数器的差值，计数器回退时按 0 处理。
    from types import SimpleNamespace

    readings = [
        SimpleNamespace(sin=1000, sout=2000, percent=0.0),
        SimpleNamespace(sin=3000, sout=1500, percent=0.0),
    ]
    monkeypatch.setattr(statisticsAPI.psutil, 'swap_memory', lambda: readings.pop(0))
    monitor = make_statistics_monitor()
    monitor._memory_io.disabled = True
    # 固定单调时钟，避免 CI 上两次采样落在同一个低分辨率时间点而跳过速率计算。
    clock = {'now': 100.0}
    monkeypatch.setattr(statisticsAPI.time, 'monotonic', lambda: clock['now'])
    first = monitor._sample_performance()
    clock['now'] = 101.0
    second = monitor._sample_performance()
    assert first['memory']['swap_in_bps'] == 0.0
    assert second['memory']['swap_in_bps'] > 0.0
    assert second['memory']['swap_out_bps'] == 0.0


def test_statistics_sample_degrades_when_psutil_fails(monkeypatch):
    # 系统探针不可用时仍要产出结构完整的快照，仪表盘不能因此报错。
    def fail(*args, **kwargs):
        raise RuntimeError('probe unavailable')

    for name in ('cpu_percent', 'cpu_count', 'virtual_memory', 'swap_memory', 'disk_usage',
                 'disk_io_counters', 'net_io_counters', 'Process'):
        monkeypatch.setattr(statisticsAPI.psutil, name, fail)
    monitor = make_statistics_monitor()
    monitor.sample()
    snapshot = monitor.snapshot()
    assert snapshot['available'] is True
    assert snapshot['performance']['cpu']['percent'] == 0.0
    assert snapshot['performance']['memory']['total'] == 0
    # 平台探针无法提供线程数或句柄数时，历史采样必须保留 None，
    # 不能把它们伪造成真实存在的 0。
    assert snapshot['performance']['process']['threads'] is None
    assert snapshot['performance']['process']['handles'] is None
    assert snapshot['performance']['history']['process_threads'] == [None]
    assert snapshot['performance']['history']['process_handles'] == [None]


def test_statistics_process_cpu_uses_cpu_time_delta(monkeypatch):
    # 进程 CPU 要用两次 CPU 时间差计算，不能因为每次新建 Process 对象而永远显示 0。
    from contextlib import nullcontext

    class FakeCpuTimes(object):
        def __init__(self, user, system, children_user=0.1, children_system=0.05, iowait=0.0):
            self.user = user
            self.system = system
            self.children_user = children_user
            self.children_system = children_system
            self.iowait = iowait

    class FakeProcess(object):
        def __init__(self):
            self.cpu = 5.0

        def oneshot(self):
            return nullcontext()

        def memory_info(self):
            return Mock(rss=1024)

        def cpu_times(self):
            return FakeCpuTimes(self.cpu, 0.0)

        def num_threads(self):
            return 2

        def num_handles(self):
            return 3

        def children(self, recursive=True):
            return []

    proc = FakeProcess()
    monkeypatch.setattr(statisticsAPI.psutil, 'Process', lambda pid: proc)
    monitor = make_statistics_monitor()
    assert monitor._process_tree_metrics(now=10.0)['cpu_percent'] == 0.0
    proc.cpu = 6.5
    assert monitor._process_tree_metrics(now=12.0)['cpu_percent'] == 75.0


def test_statistics_process_tree_exposes_children_threads_and_cpu_delta(monkeypatch):
    # 进程树快照要保留父子关系、每个进程的线程明细，并用两次 CPU 时间差计算进程负载。
    from contextlib import nullcontext
    from types import SimpleNamespace

    class FakeCpuTimes(object):
        def __init__(self, user, system, children_user=0.1, children_system=0.05, iowait=0.0):
            self.user = user
            self.system = system
            self.children_user = children_user
            self.children_system = children_system
            self.iowait = iowait

    class FakeProcess(object):
        def __init__(self, pid, ppid, cpu=1.0, threads=None, children=None):
            self.pid = pid
            self.parent_pid = ppid
            self.cpu = cpu
            self.thread_rows = threads or []
            self.child_items = children or []

        def ppid(self):
            return self.parent_pid

        def name(self):
            return 'python.exe'

        def status(self):
            return 'running'

        def username(self):
            return 'tester'

        def create_time(self):
            return 100.0

        def memory_info(self):
            return SimpleNamespace(rss=1024, vms=2048, peak_wset=1536, private=900, shared=100)

        def oneshot(self):
            return nullcontext()

        def memory_percent(self):
            return 25.0

        def cmdline(self):
            return ['python.exe', 'main.py', '--token', 'secret-value']

        def exe(self):
            return 'C:/OlivOS/python.exe'

        def cpu_times(self):
            return FakeCpuTimes(self.cpu, 0.0)

        def nice(self):
            return 5

        def ionice(self):
            return SimpleNamespace(ioclass=2, value=4)

        def cpu_affinity(self):
            return [0, 1, 2, 3]

        def num_ctx_switches(self):
            return SimpleNamespace(voluntary=10, involuntary=2)

        def io_counters(self):
            return SimpleNamespace(
                read_count=1, write_count=2, read_bytes=1024, write_bytes=2048,
                other_count=3, other_bytes=4096)

        def num_fds(self):
            return 12

        def threads(self):
            return self.thread_rows

        def num_threads(self):
            return len(self.thread_rows)

        def num_handles(self):
            return 7

        def children(self, recursive=True):
            return self.child_items

    child = FakeProcess(
        101, 100,
        threads=[SimpleNamespace(id=1003, user_time=0.2, system_time=0.1)],
    )
    root = FakeProcess(
        100, 1,
        threads=[
            SimpleNamespace(id=1002, user_time=0.4, system_time=0.1),
            SimpleNamespace(id=1001, user_time=0.5, system_time=0.25),
        ],
        children=[child],
    )
    # 线程详情同时保留 Python 线程名；平台分支在单测中隔离。
    monkeypatch.setattr(statisticsAPI, '_python_thread_names', lambda pid: {1001: 'MainThread'})
    monkeypatch.setattr(statisticsAPI.platform, 'system', lambda: 'Test')
    monkeypatch.setattr(statisticsAPI.psutil, 'Process', lambda pid: root)
    monitor = make_statistics_monitor()
    first = monitor.process_tree_snapshot(now=10.0)
    assert first['available'] is True
    assert first['root_pid'] == 100
    assert first['process_count'] == 2
    assert first['thread_count'] == 3
    assert first['roots'][0]['pid'] == 100
    assert first['roots'][0]['children'][0]['pid'] == 101
    assert [item['id'] for item in first['roots'][0]['threads']] == [1001, 1002]
    assert first['roots'][0]['threads'][0]['python_name'] == 'MainThread'
    assert first['roots'][0]['cmdline'] == 'python.exe main.py --token ********'
    assert 'secret-value' not in first['roots'][0]['cmdline']
    assert first['roots'][0]['exe'] == 'C:/OlivOS/python.exe'
    assert first['roots'][0]['memory_percent'] == 25.0
    assert first['roots'][0]['memory_peak'] == 1536
    assert first['roots'][0]['memory_private'] == 900
    assert first['roots'][0]['memory_shared'] == 100
    assert first['roots'][0]['nice'] == 5
    assert first['roots'][0]['io_priority'] == {'class': 2, 'value': 4}
    assert first['roots'][0]['cpu_affinity'] == [0, 1, 2, 3]
    assert first['roots'][0]['ctx_switches'] == {'voluntary': 10, 'involuntary': 2}
    assert first['roots'][0]['io']['read_bytes'] == 1024
    assert first['roots'][0]['io']['write_bytes'] == 2048
    assert first['roots'][0]['num_fds'] == 12
    assert first['roots'][0]['cpu_children_user'] == 0.1
    assert first['roots'][0]['cpu_percent'] == 0.0

    root.cpu = 2.5
    child.cpu = 2.0
    root.thread_rows[0].user_time = 0.9
    root.thread_rows[1].user_time = 1.5
    child.thread_rows[0].user_time = 0.5
    second = monitor.process_tree_snapshot(now=12.0)
    assert second['roots'][0]['cpu_percent'] == 75.0
    assert second['roots'][0]['children'][0]['cpu_percent'] == 50.0
    assert [item['cpu_percent'] for item in second['roots'][0]['threads']] == [50.0, 25.0]
    assert second['roots'][0]['children'][0]['threads'][0]['cpu_percent'] == 15.0
    totals = monitor._process_tree_metrics(now=14.0)
    assert totals['num_fds'] == 24
    assert totals['handles'] is None


def test_statistics_process_tree_marks_file_descriptors_incomplete_on_process_failure(monkeypatch):
    # 进程树中任一进程读取失败时，文件描述符总数只能视为不完整，不能返回部分和冒充全量。
    from contextlib import nullcontext
    from types import SimpleNamespace

    class FakeProcess(object):
        def __init__(self, pid, fail=False):
            self.pid = pid
            self.fail = fail
            self.child_items = []

        def oneshot(self):
            return nullcontext()

        def memory_info(self):
            if self.fail:
                raise RuntimeError('process vanished')
            return SimpleNamespace(rss=1024)

        def cpu_times(self):
            return SimpleNamespace(user=0.1, system=0.1)

        def num_threads(self):
            return 1

        def num_handles(self):
            return 7

        def num_fds(self):
            return 5

        def children(self, recursive=True):
            return self.child_items

    root = FakeProcess(100)
    child = FakeProcess(101, fail=True)
    root.child_items = [child]
    monkeypatch.setattr(statisticsAPI.platform, 'system', lambda: 'Test')
    monkeypatch.setattr(statisticsAPI.psutil, 'Process', lambda pid: root)
    monitor = make_statistics_monitor()

    totals, cpu_seconds = monitor._process_tree_totals()

    assert totals['count'] == 2
    assert totals['threads'] == 1
    assert totals['handles'] is None
    assert totals['num_fds'] is None
    assert cpu_seconds == 0.2


def test_statistics_process_detail_returns_limited_files_connections_and_memory(monkeypatch):
    # 文件、连接、完整内存与内存映射只在按需详情中读取，并限制单次返回条目数。
    from types import SimpleNamespace

    FullMemory = namedtuple('FullMemory', ['rss', 'vms', 'uss', 'pss'])
    MemoryMap = namedtuple('MemoryMap', ['path', 'rss', 'size', 'pss'])

    class FakeProcess(object):
        pid = 100

        def create_time(self):
            return 100.0

        def children(self, recursive=True):
            return []

        def open_files(self):
            return [SimpleNamespace(path='/tmp/file-%d.log' % index, fd=index, mode='r',
                                    position=0) for index in range(101)]

        def net_connections(self, kind='inet'):
            return [SimpleNamespace(
                fd=4, family='AF_INET', type='SOCK_STREAM',
                laddr=('127.0.0.1', 8000), raddr=('127.0.0.1', 9000),
                status='ESTABLISHED')]

        def memory_full_info(self):
            return FullMemory(rss=1024, vms=2048, uss=512, pss=600)

        def memory_maps(self):
            return [MemoryMap(path='/tmp/lib.so', rss=256, size=512, pss=300)]

    root = FakeProcess()
    monkeypatch.setattr(statisticsAPI.psutil, 'Process', lambda pid: root)
    monitor = make_statistics_monitor()
    detail = monitor.process_detail_snapshot(100, create_time=100.0)
    assert detail['available'] is True
    assert detail['open_files']['count'] == 101
    assert len(detail['open_files']['items']) == statisticsAPI.PROCESS_DETAIL_ITEMS_LIMIT
    assert detail['open_files']['truncated'] is True
    assert detail['open_files']['items'][0]['path'] == '/tmp/file-0.log'
    assert detail['connections']['items'][0]['status'] == 'ESTABLISHED'
    assert detail['connections']['items'][0]['laddr'] == {'ip': '127.0.0.1', 'port': 8000}
    assert detail['memory_full'] == {'rss': 1024, 'vms': 2048, 'uss': 512, 'pss': 600}
    assert detail['memory_maps']['items'][0]['path'] == '/tmp/lib.so'
    assert detail['memory_maps']['items'][0]['metrics']['rss'] == 256
    assert detail['errors'] == []

    changed = monitor.process_detail_snapshot(100, create_time=99.0)
    assert changed['available'] is False
    assert changed['reason'] == 'process_changed'
    missing = monitor.process_detail_snapshot(101)
    assert missing['available'] is False
    assert missing['reason'] == 'process_not_found'


def test_linux_thread_stat_parser_extracts_state_priority_and_processor():
    # Linux 线程 stat 的 comm 可以包含空格，解析时必须从最后一个右括号后开始取字段。
    fields = ['0'] * 40
    fields[0] = 'S'
    fields[15] = '20'
    fields[16] = '0'
    fields[19] = '500'
    fields[36] = '3'
    parsed = statisticsAPI._parse_linux_thread_stat(
        '123 (worker name) ' + ' '.join(fields)
    )
    assert parsed == {
        'state': 'S', 'priority': 20, 'nice': 0, 'processor': 3, 'start_time_ticks': 500,
    }


def test_python_thread_names_only_map_current_process(monkeypatch):
    # Python 线程名只在当前进程内可用，不能把其它 PID 的线程误映射过来。
    from types import SimpleNamespace

    monkeypatch.setattr(
        statisticsAPI.threading,
        'enumerate',
        lambda: [
            SimpleNamespace(native_id=321, name='MainThread'),
            SimpleNamespace(native_id=None, name='ignored'),
        ],
    )
    assert statisticsAPI._python_thread_names(statisticsAPI.os.getpid()) == {321: 'MainThread'}
    assert statisticsAPI._python_thread_names(statisticsAPI.os.getpid() + 1) == {}


def test_linux_thread_detail_reads_wait_channel_and_start_time(monkeypatch):
    # Linux 线程详情应补充 comm、等待点、启动时间和上下文切换。
    fields = ['0'] * 40
    fields[0] = 'S'
    fields[15] = '20'
    fields[16] = '0'
    fields[19] = '500'
    fields[36] = '3'
    files = {
        '/proc/100/task/200/comm': 'worker',
        '/proc/100/task/200/stat': '123 (worker name) ' + ' '.join(fields),
        '/proc/100/task/200/wchan': 'futex_wait_queue_me',
        '/proc/100/task/200/status': (
            'voluntary_ctxt_switches: 7\n'
            'nonvoluntary_ctxt_switches: 2\n'
        ),
    }
    monkeypatch.setattr(
        statisticsAPI, '_read_proc_text', lambda path, limit: files.get(path)
    )
    monkeypatch.setattr(statisticsAPI, '_linux_clock_ticks', lambda: 100)
    detail = statisticsAPI.server._linux_thread_detail(100, 200, boot_time=1000.0)
    assert detail['name'] == 'worker'
    assert detail['state'] == 'S'
    assert detail['wchan'] == 'futex_wait_queue_me'
    assert detail['start_time'] == 1005.0
    assert detail['priority'] == 20
    assert detail['processor'] == 3
    assert detail['ctx_switches'] == {'voluntary': 7, 'involuntary': 2}


def test_windows_thread_details_include_description_priority_and_start_module(monkeypatch):
    # Windows 线程详情应补齐线程描述、相对优先级、起始地址和所属模块。
    descriptions = {201: 'worker-thread'}
    priorities = {201: -2, 202: statisticsAPI._WINDOWS_THREAD_PRIORITY_ERROR}
    addresses = {201: 0x2000, 202: 0x3500, 203: 0x1500}
    closed = []

    class FakeKernel32(object):
        def OpenThread(self, access, inherit, tid):
            return 1000 + tid

        def CloseHandle(self, handle):
            closed.append(handle)
            return 1

        def GetThreadDescription(self, handle, output):
            output._obj.value = descriptions.get(handle - 1000, '')
            return 0

        def GetThreadPriority(self, handle):
            return priorities.get(handle - 1000, 0)

        def LocalFree(self, value):
            return None

    class FakeNtdll(object):
        def NtQueryInformationThread(self, handle, info_class, output, size, returned):
            output._obj.value = addresses[handle - 1000]
            return 0

    rows = [
        {'id': 201, 'name': None, 'python_name': 'worker', 'priority': None,
         'start_address': None, 'start_module': None},
        {'id': 202, 'name': None, 'python_name': None, 'priority': None,
         'start_address': None, 'start_module': None},
        {'id': 203, 'name': None, 'python_name': 'fallback-thread', 'priority': None,
         'start_address': None, 'start_module': None},
    ]
    monkeypatch.setattr(
        statisticsAPI,
        '_windows_process_modules',
        lambda pid, kernel32, psapi: [
            (0x1000, 0x3000, 'python311.dll'),
            (0x3000, 0x4000, 'worker.dll'),
        ],
    )
    statisticsAPI._windows_thread_details(
        100, rows, {201: 'worker-python', 203: 'fallback-thread'},
        FakeKernel32(), FakeNtdll(), object()
    )
    assert rows[0]['name'] == 'worker-thread'
    assert rows[0]['priority'] == -2
    assert rows[0]['start_address'] == 0x2000
    assert rows[0]['start_module'] == 'python311.dll+0x1000'
    assert rows[1]['name'] is None
    assert rows[1]['priority'] is None
    assert rows[1]['start_address'] == 0x3500
    assert rows[1]['start_module'] == 'worker.dll+0x500'
    assert rows[2]['name'] == 'fallback-thread'
    assert rows[2]['start_module'] == 'python311.dll+0x500'
    assert closed == [1201, 1202, 1203]
