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
    monitor = make_statistics_monitor(history_size=2, traffic_history_size=2)
    for _ in range(3):
        monitor.sample()
    snapshot = monitor.snapshot()
    assert snapshot['available'] is True
    assert isinstance(snapshot['performance']['history']['cpu_percent'], list)
    assert len(snapshot['performance']['history']['cpu_percent']) <= 2
    assert json.loads(json.dumps(snapshot, ensure_ascii=False)) == snapshot


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


def test_statistics_process_cpu_uses_cpu_time_delta(monkeypatch):
    # 进程 CPU 要用两次 CPU 时间差计算，不能因为每次新建 Process 对象而永远显示 0。
    from contextlib import nullcontext

    class FakeCpuTimes(object):
        def __init__(self, user, system):
            self.user = user
            self.system = system

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
