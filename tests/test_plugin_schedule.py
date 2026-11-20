"""插件调度的本地时间、事件定向与生命周期；不访问网络。"""

import json
import sys
from datetime import datetime, timedelta, timezone
from queue import Empty, Queue
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
import pytz
from apscheduler.events import EVENT_JOB_EXECUTED, JobExecutionEvent
from apscheduler.schedulers.background import BackgroundScheduler

import OlivOS
from OlivOS import scheduleAPI
from OlivOS.core.core import pluginSchedule

NOW = datetime(2027, 1, 14, 18, tzinfo=timezone.utc)
STEP = timedelta(seconds=1)


class Clock:
    instant = NOW

    def __call__(self):
        return self.instant


class PausedScheduler(BackgroundScheduler):
    def start(self):
        super().start(paused=True)


def plugin(namespace, event, **fields):
    return dict(namespace=namespace, model=SimpleNamespace(main=SimpleNamespace(Event=event)), **fields)


def interval_plugin(namespace, callback, *, immediate=False):
    class PluginEvent:
        @staticmethod
        @scheduleAPI.interval(id='task', hours=2, run_on_start=immediate)
        def scheduled(proc):
            callback(proc)

    return plugin(namespace, PluginEvent)


def due(runtime, namespace='sample', task_id='task', at=None, **overrides):
    return OlivOS.API.Control.packet('plugin_timer_due', dict({
        'namespace': namespace, 'task_id': task_id, 'scheduled_at': runtime.now() if at is None else at,
        'generation': runtime.generation, 'epoch': runtime.epoch,
    }, **overrides))


def wait_for_pool(runtime):
    for future in runtime._futures:
        future.result(timeout=3)


def job_for(runtime, namespace, task_id):
    return next(job for job in runtime._source.get_jobs() if job.args[:2] == (namespace, task_id))


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(pluginSchedule, 'BackgroundScheduler', PausedScheduler)
    monkeypatch.setattr(scheduleAPI.tzlocal, 'get_localzone_name', lambda: 'Asia/Shanghai')
    monkeypatch.setattr(scheduleAPI.tzlocal, 'reload_localzone', lambda: None)
    initialized = []

    def make(*models, proc=None):
        if proc is None:
            proc = SimpleNamespace(log=Mock())
        scheduler = pluginSchedule.PluginSchedule(proc, 'test-generation', now=Clock(), root=tmp_path)
        initialized.append(scheduler)
        status = scheduler.start(models)
        return scheduler, status

    yield make
    for scheduler in initialized:
        scheduler.close_gate()
        scheduler.shutdown()


def test_settings_revision_and_corruption_are_checked(tmp_path):
    assert {'UTC', 'Asia/Shanghai', 'Europe/Berlin'} <= set(scheduleAPI.timezone_choices())
    assert 'CST' not in scheduleAPI.timezone_choices()
    assert 'system' not in scheduleAPI.timezone_choices()
    missing = scheduleAPI.read_settings(tmp_path)
    assert missing == {'timezone': 'system', 'revision': 'missing', 'error': None}
    saved = scheduleAPI.save_settings(tmp_path, 'Europe/Berlin', missing['revision'])
    assert saved == scheduleAPI.read_settings(tmp_path)
    assert saved['revision'] != missing['revision']
    with pytest.raises(scheduleAPI.ScheduleConflict):
        scheduleAPI.save_settings(tmp_path, 'UTC', missing['revision'])
    with pytest.raises(ValueError, match='IANA'):
        scheduleAPI.save_settings(tmp_path, 'UTC+1', saved['revision'])
    path = tmp_path / 'conf' / 'plugin_schedule.json'
    assert json.loads(path.read_text(encoding='utf-8')) == {'version': 1, 'timezone': 'Europe/Berlin'}
    path.write_bytes(b'invalid file')
    broken = scheduleAPI.read_settings(tmp_path)
    assert broken['error']
    with pytest.raises(ValueError, match='格式'):
        scheduleAPI.save_settings(tmp_path, 'system', broken['revision'])
    assert path.read_bytes() == b'invalid file'


def test_saved_timezone_applies_only_when_a_new_generation_starts(tmp_path, runtime):
    class PluginEvent:
        @staticmethod
        @scheduleAPI.cron(id='cleanup', hour=4, minute=0)
        def cleanup(Proc):
            pass

    model = plugin('sample', PluginEvent)
    old, status = runtime(model)
    assert status['effective_timezone'] == 'Asia/Shanghai'
    assert job_for(old, 'sample', 'cleanup').next_run_time.astimezone(timezone.utc) == NOW + timedelta(hours=2)
    saved = scheduleAPI.save_settings(tmp_path, 'Europe/Berlin', status['revision'])
    old.close_gate()
    old.recover()
    assert job_for(old, 'sample', 'cleanup').next_run_time.astimezone(timezone.utc) == NOW + timedelta(hours=2)
    new, status = runtime(model)
    assert status['revision'] == saved['revision']
    assert status['effective_timezone'] == 'Europe/Berlin'
    assert job_for(new, 'sample', 'cleanup').next_run_time.astimezone(timezone.utc) == NOW + timedelta(hours=9)
    scheduleAPI.save_settings(tmp_path, 'system', status['revision'])
    assert runtime(model)[1]['effective_timezone'] == 'Asia/Shanghai'


def test_new_generation_refreshes_host_timezone_name_without_falling_back_to_utc(runtime, monkeypatch):
    cached = None
    host_name = 'Asia/Shanghai'

    def reload_zone():
        nonlocal cached
        cached = host_name
        return pytz.UTC  # tzlocal 无法取得名称时，仍可能返回 UTC 对象。

    monkeypatch.setattr(scheduleAPI.tzlocal, 'reload_localzone', reload_zone)
    monkeypatch.setattr(scheduleAPI.tzlocal, 'get_localzone_name', lambda: cached)
    _, before = runtime()
    host_name = 'Europe/Berlin'
    _, after = runtime()
    host_name = None
    _, unknown = runtime()
    assert before['effective_timezone'] == 'Asia/Shanghai'
    assert after['effective_timezone'] == 'Europe/Berlin'
    assert unknown['effective_timezone'] is None and unknown['error']


def test_host_timezone_error_disables_local_triggers_not_intervals(runtime, monkeypatch):
    def unknown_zone():
        raise OSError('not a configured time zone')

    monkeypatch.setattr(scheduleAPI.tzlocal, 'get_localzone_name', unknown_zone)

    class PluginEvent:
        @staticmethod
        @scheduleAPI.cron(id='cron', hour=4)
        @scheduleAPI.date(id='date', run_at=datetime(2028, 1, 1))
        @scheduleAPI.interval(id='interval', seconds=1)
        def callback(Proc):
            pass

    scheduler, status = runtime(plugin('sample', PluginEvent))
    assert status['error'] and status['effective_timezone'] is None
    assert set(scheduler._tasks) == {('sample', 'interval')}


@pytest.mark.parametrize(('run_at', 'error'), [
    (datetime(2027, 3, 28, 2, 30), 'does not exist'),
    (datetime(2027, 10, 31, 2, 30), 'ambiguous'),
    (NOW, 'naive datetime'),
    ('2027-01-15T03:00:00+00:00', 'naive datetime'),
    (datetime(2027, 1, 14), 'missed before activation'),
])
def test_date_rejects_past_ambiguous_nonexistent_or_aware_time(tmp_path, runtime, run_at, error):
    scheduleAPI.save_settings(tmp_path, 'Europe/Berlin', scheduleAPI.read_settings(tmp_path)['revision'])

    class PluginEvent:
        @staticmethod
        @scheduleAPI.date(id='once', run_at=run_at)
        def callback(Proc):
            pass

    scheduler, _ = runtime(plugin('sample', PluginEvent))
    assert scheduler._source is None
    assert any(error in call.args[1] for call in scheduler.proc.log.call_args_list)


def test_date_at_activation_is_due_not_expired(runtime):
    class PluginEvent:
        @staticmethod
        @scheduleAPI.date(id='now', run_at=datetime(2027, 1, 15, 2))
        def callback(Proc):
            pass

    scheduler, _ = runtime(plugin('sample', PluginEvent))
    assert job_for(scheduler, 'sample', 'now').next_run_time == NOW


def test_bad_trigger_parameters_do_not_abort_other_tasks(runtime):
    class InvalidHour:
        def __str__(self):
            raise RuntimeError('invalid cron parameter')

    class PluginEvent:
        @staticmethod
        @scheduleAPI.cron(id='bad-hour', hour=InvalidHour())
        @scheduleAPI.interval(id='too-long', hours=10**8, run_on_start=True)
        @scheduleAPI.interval(id='valid', seconds=1)
        def callback(Proc):
            pass

    scheduler, _ = runtime(plugin('sample', PluginEvent))
    assert set(scheduler._tasks) == {('sample', 'valid')}


def test_cron_dst_uses_pinned_pytz_standard_offset(tmp_path, runtime):
    scheduleAPI.save_settings(tmp_path, 'Europe/Berlin', scheduleAPI.read_settings(tmp_path)['revision'])

    class PluginEvent:
        @staticmethod
        @scheduleAPI.cron(id='daily', hour=2, minute=30)
        def callback(Proc):
            pass

    scheduler, _ = runtime(plugin('sample', PluginEvent))
    trigger = job_for(scheduler, 'sample', 'daily').trigger
    for day in (datetime(2027, 3, 28, tzinfo=timezone.utc), datetime(2027, 10, 31, tzinfo=timezone.utc)):
        next_at = trigger.get_next_fire_time(None, day)
        assert next_at.astimezone(timezone.utc) == day + timedelta(hours=1, minutes=30)
        assert trigger.get_next_fire_time(next_at, next_at).day != day.day


def test_declarations_do_not_accept_plugin_timezone_or_numeric_weekdays(runtime):
    with pytest.raises(TypeError):
        scheduleAPI.cron(id='foreign', hour=4, timezone='UTC')

    class PluginEvent:
        @staticmethod
        @scheduleAPI.cron(id='number', day_of_week='2')
        @scheduleAPI.cron(id='name', day_of_week='mon-fri')
        @scheduleAPI.cron(id='hour', hour=27)
        @scheduleAPI.interval(id='fast', seconds=0.1)
        def callback(Proc):
            pass

    scheduler, _ = runtime(plugin('sample', PluginEvent))
    assert set(scheduler._tasks) == {('sample', 'name')}


def test_discovery_is_own_static_methods_and_duplicate_ids_do_not_activate(runtime):
    class Inherited:
        @staticmethod
        @scheduleAPI.interval(id='inherited', seconds=1)
        def inherited(Proc):
            pass

    class PluginEvent(Inherited):
        @staticmethod
        @scheduleAPI.interval(id='shared', seconds=1)
        def valid(Proc):
            pass

        @staticmethod
        @scheduleAPI.interval(id='duplicate', seconds=1)
        @scheduleAPI.interval(id='duplicate', seconds=1)
        def duplicate(Proc):
            pass

        @scheduleAPI.interval(id='instance', seconds=1)
        def instance(Proc):
            pass

        @staticmethod
        @scheduleAPI.interval(id='async', seconds=1)
        async def async_callback(Proc):
            pass

        @staticmethod
        @scheduleAPI.interval(id='args', seconds=1)
        def invalid_args(Proc, extraneous):
            pass

    scheduler, _ = runtime(plugin('a', PluginEvent), plugin('failed', PluginEvent, schedule_init_failed=True),
                           plugin('b', PluginEvent))
    assert set(scheduler._tasks) == {('a', 'shared'), ('b', 'shared')}
    assert any('duplicate task ID' in call.args[1] for call in scheduler.proc.log.call_args_list)


def test_event_reports_planned_utc_and_only_invokes_matching_namespace(runtime):
    calls = []

    def first(proc):
        calls.append(('first', proc))

    def second(proc):
        calls.append(('second', proc))

    scheduler, _ = runtime(interval_plugin('first', first), interval_plugin('second', second))
    job = job_for(scheduler, 'second', 'task')
    planned = NOW.astimezone(pytz.timezone('Asia/Shanghai'))
    event = JobExecutionEvent(EVENT_JOB_EXECUTED, job.id, 'default', planned, retval=job.func(*job.args))
    scheduler._report_event(event, {job.id: ('second', 'task')})
    packet = scheduler._pending[('second', 'task')]
    assert packet.key['scheduled_at'] == NOW and packet.key['scheduled_at'].tzinfo is pytz.UTC
    assert scheduler.dispatch()
    wait_for_pool(scheduler)
    assert calls == [('second', scheduler.proc)]


def test_malformed_stale_duplicate_and_late_events_are_not_executed(runtime):
    count = []

    def callback(proc):
        count.append(proc)

    scheduler, _ = runtime(interval_plugin('sample', callback))
    assert not scheduler.enqueue(due(scheduler, generation='other'))
    assert not scheduler.enqueue(due(scheduler, epoch=-1))
    assert not scheduler.enqueue(due(scheduler, namespace='other'))
    assert not scheduler.enqueue(due(scheduler, at=NOW.replace(tzinfo=None)))
    assert not scheduler.enqueue(due(scheduler, at=NOW - timedelta(seconds=6)))
    assert scheduler.enqueue(due(scheduler))
    assert not scheduler.enqueue(due(scheduler))
    assert not scheduler.enqueue(due(scheduler, at=NOW - STEP))
    scheduler.dispatch()
    wait_for_pool(scheduler)
    assert count == [scheduler.proc]


def test_queue_full_releases_slot_but_marks_event_seen(runtime, monkeypatch):
    monkeypatch.setattr(pluginSchedule, '_QUEUE_SIZE', 1)

    def callback(proc):
        pass

    scheduler, _ = runtime(interval_plugin('sample', callback), interval_plugin('next', callback))
    assert scheduler.enqueue(due(scheduler))
    rejected = due(scheduler, namespace='next')
    assert not scheduler.enqueue(rejected)
    scheduler.dispatch()
    wait_for_pool(scheduler)
    assert not scheduler.enqueue(rejected)
    assert scheduler.enqueue(due(scheduler, namespace='next', at=NOW + STEP))


def test_four_workers_pending_reservations_and_pre_execute_lateness(runtime):
    release = Event()
    started = [Event() for _ in range(4)]
    waiting_called = Event()

    def declare(index):
        def blocked(proc):
            started[index].set()
            assert release.wait(timeout=3)

        return interval_plugin(str(index), blocked)

    def waiting(proc):
        waiting_called.set()

    scheduler, _ = runtime(*(declare(i) for i in range(4)), interval_plugin('waiting', waiting))
    try:
        for namespace in ['0', '1', '2', '3', 'waiting']:
            assert scheduler.enqueue(due(scheduler, namespace=namespace))
        assert scheduler.dispatch()
        assert all(event.wait(timeout=3) for event in started)
        assert set(scheduler.running_tasks()) == {(str(i), 'task') for i in range(4)}
        assert not scheduler.enqueue(due(scheduler, namespace='waiting', at=NOW + STEP))
        assert not scheduler.enqueue(due(scheduler, namespace='0', at=NOW + STEP))
        scheduler.now.instant = NOW + 6 * STEP
    finally:
        release.set()
    wait_for_pool(scheduler)
    assert not waiting_called.is_set()
    assert scheduler.enqueue(due(scheduler, namespace='waiting'))
    scheduler.dispatch()
    wait_for_pool(scheduler)
    assert waiting_called.is_set()


def test_gate_revokes_queued_and_dispatched_work(runtime):
    release = Event()
    entered = [Event() for _ in range(4)]
    calls = []

    def worker(index):
        def blocked(proc):
            entered[index].set()
            assert release.wait(timeout=3)

        return blocked

    def must_not_run(proc):
        calls.append(proc)

    models = [interval_plugin(str(index), worker(index)) for index in range(4)]
    models.extend(interval_plugin(namespace, must_not_run) for namespace in ('in-pool', 'in-queue'))
    scheduler, _ = runtime(*models)
    try:
        for namespace in ('0', '1', '2', '3', 'in-pool', 'in-queue'):
            assert scheduler.enqueue(due(scheduler, namespace=namespace))
        assert scheduler.dispatch(budget=5)
        assert all(event.wait(timeout=3) for event in entered)
        futures = list(scheduler._futures)
        scheduler.close_gate()
        assert sum(future.cancelled() for future in futures) == 1
        assert scheduler._queue.empty()
    finally:
        release.set()
    for future in futures:
        if not future.cancelled():
            future.result(timeout=3)
    assert not calls


def test_callback_failure_releases_slot_and_preserves_next_execution(runtime):
    called = []

    def callback(proc):
        called.append(proc)
        if len(called) == 1:
            raise ValueError('credentials should not leak')

    scheduler, _ = runtime(interval_plugin('sample', callback))
    for at in (NOW, NOW + STEP):
        assert scheduler.enqueue(due(scheduler, at=at))
        scheduler.dispatch()
        wait_for_pool(scheduler)
    assert called == [scheduler.proc, scheduler.proc]
    messages = [call.args[1] for call in scheduler.proc.log.call_args_list]
    assert any('callback failed (ValueError)' in message for message in messages)
    assert all('credentials' not in message for message in messages)


def test_recovery_keeps_interval_anchor_and_only_future_unfired_dates(runtime):
    def callback(proc):
        pass

    class Dated:
        @staticmethod
        @scheduleAPI.date(id='future', run_at=datetime(2027, 1, 16, 4))
        @scheduleAPI.date(id='overdue', run_at=datetime(2027, 1, 15, 3))
        @scheduleAPI.date(id='already', run_at=datetime(2027, 1, 15, 2, 15))
        def callback(Proc):
            pass

    scheduler, _ = runtime(interval_plugin('sample', callback, immediate=True), plugin('date', Dated))
    assert job_for(scheduler, 'sample', 'task').next_run_time == NOW
    obsolete = due(scheduler)
    saved_job = job_for(scheduler, 'date', 'future')
    expected = datetime(2027, 1, 15, 20, tzinfo=timezone.utc)
    assert saved_job.next_run_time == expected
    already = job_for(scheduler, 'date', 'already')
    scheduler.now.instant = NOW + timedelta(minutes=15)
    event = JobExecutionEvent(EVENT_JOB_EXECUTED, already.id, 'default', already.next_run_time,
                              retval=already.func(*already.args))
    scheduler._report_event(event, {already.id: ('date', 'already')})
    scheduler.close_gate()
    scheduler.now.instant = NOW + timedelta(hours=1, minutes=30)
    scheduler.recover()
    assert not scheduler.enqueue(obsolete)
    assert job_for(scheduler, 'sample', 'task').next_run_time == NOW + timedelta(hours=2)
    assert job_for(scheduler, 'date', 'future').next_run_time == expected
    assert {job.args[1] for job in scheduler._source.get_jobs()} == {'task', 'future'}
    assert any('date missed during drain: [date/overdue]' in call.args[1] for call in scheduler.proc.log.call_args_list)
    scheduler.close_gate()
    scheduler.now.instant = NOW
    scheduler.recover()
    assert {job.args[1] for job in scheduler._source.get_jobs()} == {'task', 'future'}


def test_real_apscheduler_reports_start_immediately_without_running_plugin(tmp_path):
    reported = Event()
    called = Event()

    def callback(proc):
        called.set()

    scheduler = pluginSchedule.PluginSchedule(SimpleNamespace(log=Mock()), 'real', root=tmp_path)
    enqueue = scheduler.enqueue

    def notify(packet):
        result = enqueue(packet)
        reported.set()
        return result

    scheduler.enqueue = notify
    try:
        scheduler.start([interval_plugin('sample', callback, immediate=True)])
        assert reported.wait(timeout=3)
        assert not called.is_set()
        assert scheduler.dispatch()
        assert called.wait(timeout=3)
    finally:
        scheduler.close_gate()
        scheduler.shutdown()


@pytest.mark.parametrize(('operation', 'action'), [
    ('restart', 'restart_do'), ('update', 'plugin_lifecycle_complete'), ('stop', 'plugin_lifecycle_complete'),
])
def test_loader_acknowledges_only_after_running_callbacks_save_and_database_stop(runtime, operation, action):
    entered, release = Event(), Event()
    order = []
    loader = OlivOS.pluginAPI.shallow(enable_gui=False, rx_queue=Queue(), control_queue=Queue())
    loader.log = Mock()
    loader.run_plugin_func = lambda event, name: order.append(name)
    loader.database = SimpleNamespace(stop=lambda: order.append('database stopped'))

    def callback(proc):
        entered.set()
        assert release.wait(timeout=3)
        order.append('callback finished')

    scheduler, _ = runtime(interval_plugin('sample', callback), proc=loader)
    loader._schedule = scheduler
    try:
        assert scheduler.enqueue(due(scheduler))
        scheduler.dispatch()
        future, = scheduler._futures
        assert entered.wait(timeout=3)
        loader._request_schedule_lifecycle(operation, None)
        assert loader._advance_schedule_lifecycle() is None
        assert order == []
        with pytest.raises(Empty):
            loader.Proc_info.control_queue.get_nowait()
    finally:
        release.set()
    future.result(timeout=3)
    loader._advance_schedule_lifecycle()
    assert order == ['callback finished', 'save', 'database stopped']
    complete = loader.Proc_info.control_queue.get_nowait()
    assert complete.action == action and complete.key['operation'] == operation
    assert complete.key['generation'] == loader.schedule_generation


def test_loader_timeout_rejects_then_recovers_without_reload_or_database_stop(runtime, monkeypatch):
    entered, release = Event(), Event()
    mono = Mock(return_value=100)
    monkeypatch.setattr(OlivOS.pluginAPI, 'time', SimpleNamespace(monotonic=mono))
    loader = OlivOS.pluginAPI.shallow(enable_gui=False, rx_queue=Queue(), control_queue=Queue(), dead_interval=1)
    loader.log = Mock()
    loader.run_plugin_func = Mock()
    loader.database = SimpleNamespace(stop=Mock())

    def callback(proc):
        entered.set()
        assert release.wait(timeout=3)

    scheduler, _ = runtime(interval_plugin('sample', callback, immediate=True), proc=loader)
    loader._schedule = scheduler
    obsolete = due(scheduler)
    try:
        assert scheduler.enqueue(obsolete)
        scheduler.dispatch()
        future, = scheduler._futures
        assert entered.wait(timeout=3)
        loader._request_schedule_lifecycle('restart', {'started_at': 123})
        mono.return_value = 102
        assert loader._advance_schedule_lifecycle() == 'timeout'
        assert not loader.Proc_config['ready_for_restart']
        assert not scheduler.enqueue(obsolete)
        rejected = loader.Proc_info.control_queue.get_nowait()
        assert rejected.action == 'plugin_lifecycle_rejected' and rejected.key['reason'] == 'timeout'
        web = loader.Proc_info.control_queue.get_nowait()
        assert web.key['data']['action'] == 'plugin_schedule_lifecycle_rejected'
        assert web.key['data']['data'] == {
            'operation': 'restart', 'reason': 'timeout', 'started_at': 123,
            'tasks': [{'namespace': 'sample', 'task_id': 'task'}],
        }
    finally:
        release.set()
    future.result(timeout=3)
    loader._advance_schedule_lifecycle()
    assert loader._schedule_lifecycle is None
    assert job_for(scheduler, 'sample', 'task').next_run_time == NOW + timedelta(hours=2)
    assert not scheduler.enqueue(obsolete)
    assert scheduler.enqueue(due(scheduler))
    assert scheduler.dispatch()
    wait_for_pool(scheduler)
    assert loader.Proc_info.control_queue.empty()
    loader.run_plugin_func.assert_not_called()
    loader.database.stop.assert_not_called()


def test_loader_cancels_if_last_callback_finished_after_deadline_between_polls(runtime, monkeypatch):
    entered, release = Event(), Event()
    mono = Mock(return_value=100)
    clock = SimpleNamespace(monotonic=mono)
    monkeypatch.setattr(OlivOS.pluginAPI, 'time', clock)
    monkeypatch.setattr(pluginSchedule, 'time', clock)
    loader = OlivOS.pluginAPI.shallow(enable_gui=False, rx_queue=Queue(), control_queue=Queue(), dead_interval=1)
    loader.log = Mock()
    loader.run_plugin_func = Mock()
    loader.database = SimpleNamespace(stop=Mock())

    def callback(proc):
        entered.set()
        assert release.wait(timeout=3)

    scheduler, _ = runtime(interval_plugin('sample', callback), proc=loader)
    loader._schedule = scheduler
    try:
        assert scheduler.enqueue(due(scheduler))
        scheduler.dispatch()
        future, = scheduler._futures
        assert entered.wait(timeout=3)
        loader._request_schedule_lifecycle('update', None)
        mono.return_value = 102
    finally:
        release.set()
    future.result(timeout=3)
    assert not scheduler.running_tasks()
    assert loader._advance_schedule_lifecycle() == 'timeout'
    rejected = loader.Proc_info.control_queue.get_nowait()
    assert rejected.action == 'plugin_lifecycle_rejected' and rejected.key['reason'] == 'timeout'
    loader.run_plugin_func.assert_not_called()
    loader.database.stop.assert_not_called()


def test_boot_ignores_acknowledgement_from_other_generation():
    loader = OlivOS.pluginAPI.shallow(enable_gui=False, rx_queue=Queue(), control_queue=Queue())
    process = Mock()
    components, processes = {loader.Proc_name: loader}, {loader.Proc_name: process}
    result = dict(name=loader.Proc_name, operation='stop', generation='other')
    packet = OlivOS.API.Control.packet('plugin_lifecycle_complete', result)
    assert OlivOS.bootAPI.complete_plugin_lifecycle(packet, components, processes) is None
    process.terminate.assert_not_called()
    result['generation'] = loader.schedule_generation
    assert OlivOS.bootAPI.complete_plugin_lifecycle(packet, components, processes) == 'stop'
    process.terminate.assert_called_once_with()
    process.join.assert_called_once_with()
    assert not components and not processes


def test_boot_drops_obsolete_status_and_clears_in_delivery_order():
    loader = OlivOS.pluginAPI.shallow(enable_gui=False, rx_queue=Queue(), control_queue=Queue())
    web = SimpleNamespace(Proc_type='webUI', Proc_info=SimpleNamespace(rx_queue=Queue()))
    components = {loader.Proc_name: loader, 'web': web}
    loader._send_schedule_event('plugin_schedule_status', {'effective_timezone': 'UTC'})
    packet = loader.Proc_info.control_queue.get_nowait()
    assert OlivOS.bootAPI._current_schedule_source(packet, components)
    OlivOS.bootAPI._send_schedule_status(components, packet)
    components.pop(loader.Proc_name)
    OlivOS.bootAPI._send_schedule_status(components)
    assert not OlivOS.bootAPI._current_schedule_source(packet, components)
    components[loader.Proc_name] = OlivOS.pluginAPI.shallow(Proc_name=loader.Proc_name, enable_gui=False)
    assert not OlivOS.bootAPI._current_schedule_source(packet, components)
    assert web.Proc_info.rx_queue.get_nowait() is packet
    assert web.Proc_info.rx_queue.get_nowait().key['data']['data'] is None


def test_successful_update_download_enters_boot_even_without_plugin_loader(monkeypatch):
    logger = object()
    control_queue = Queue()
    update = Mock(return_value=True)
    monkeypatch.setattr(OlivOS.updateAPI, 'OlivOSUpdateGet', update)
    OlivOS.bootAPI.update_get_func({'logger': logger}, {'logger_proc': 'logger'}, control_queue)
    update.assert_called_once_with(logger_proc=logger)
    queued = control_queue.get_nowait()
    assert (queued.action, queued.key) == ('init_type', 'update_replace')


def test_nuitka_bundles_dynamic_timezone_packages_and_propagates_failure(monkeypatch):
    from script import nuitka_build

    monkeypatch.setattr(nuitka_build, 'get_all_site_packages', lambda: [])
    run = Mock(side_effect=nuitka_build.subprocess.CalledProcessError(1, ['nuitka']))
    monkeypatch.setattr(nuitka_build.subprocess, 'run', run)
    with pytest.raises(nuitka_build.subprocess.CalledProcessError):
        nuitka_build.build_with_site_packages()
    options, = run.call_args.args
    assert {'--include-package=tzdata', '--include-package-data=tzdata', '--include-package-data=pytz',
            '--include-distribution-metadata=APScheduler'} <= set(options)
    assert run.call_args.kwargs == {'check': True}


def test_loader_finishes_init_after_before_activating_only_successful_plugins(tmp_path, monkeypatch):
    order = []

    class First:
        @staticmethod
        @scheduleAPI.interval(id='start', hours=2, run_on_start=True)
        def start(proc):
            order.append('scheduled')

    class Second:
        @staticmethod
        def init_after(plugin_event, Proc):
            assert Proc._schedule is None
            order.append('second init_after')
            raise RuntimeError('test init_after failure')

        @staticmethod
        @scheduleAPI.interval(id='never', hours=2, run_on_start=True)
        def start(proc):
            order.append('failed plugin scheduled')

    class LeaveLoop(Exception):
        pass

    monkeypatch.chdir(tmp_path)
    sleep = Mock(side_effect=[None, LeaveLoop()])
    clock = SimpleNamespace(**{name: getattr(OlivOS.pluginAPI.time, name)
                               for name in ('time', 'strftime', 'monotonic')}, sleep=sleep)
    monkeypatch.setattr(OlivOS.pluginAPI, 'time', clock)
    monkeypatch.setattr(OlivOS.pluginAPI, 'gProc', None)
    monkeypatch.setattr(pluginSchedule, 'BackgroundScheduler', PausedScheduler)
    monkeypatch.setattr(scheduleAPI.tzlocal, 'reload_localzone', lambda: None)
    monkeypatch.setattr(scheduleAPI.tzlocal, 'get_localzone_name', lambda: 'UTC')
    monkeypatch.setattr(OlivOS.userModule.UserConfDB, 'DataBaseAPI', Mock())
    loader = OlivOS.pluginAPI.shallow(enable_gui=False, rx_queue=Queue(), control_queue=Queue())
    loader.log = Mock()
    loader.sendPluginList = Mock()
    loader.load_plugin_list = Mock()
    loader.plugin_models_dict = {name: plugin(name, event, name=name)
                                 for name, event in [('first', First), ('second', Second)]}
    loader.plugin_models_call_list = ['first', 'second']
    try:
        with pytest.raises(LeaveLoop):
            loader.run()
        loader.sendPluginList.assert_called_with(ready=True)
        assert order == ['second init_after']
        scheduler = loader._schedule
        assert set(scheduler._tasks) == {('first', 'start')}
        assert scheduler.enqueue(due(scheduler, namespace='first', task_id='start'))
        scheduler.dispatch()
        wait_for_pool(scheduler)
        assert order == ['second init_after', 'scheduled']
    finally:
        if loader._schedule is not None:
            loader._schedule.close_gate()
            loader._schedule.shutdown()


@pytest.mark.parametrize('packed', [False, True])
@pytest.mark.parametrize('init_fails', [False, True])
def test_installed_source_and_opk_schedule_only_after_successful_init(
        tmp_path, monkeypatch, runtime, packed, init_fails):
    monkeypatch.chdir(tmp_path)
    source, cache = tmp_path / 'plugin/app', tmp_path / 'plugin/tmp'
    source.mkdir(parents=True)
    cache.mkdir(parents=True)
    monkeypatch.setattr(OlivOS.pluginAPI, 'plugin_path', str(source) + '/')
    monkeypatch.setattr(OlivOS.pluginAPI, 'plugin_path_tmp', str(cache) + '/')
    monkeypatch.syspath_prepend(str(source))
    monkeypatch.syspath_prepend(str(cache))
    namespace = 'ScheduleSourceFixture'
    loader = OlivOS.pluginAPI.shallow(enable_gui=False, rx_queue=Queue(), control_queue=Queue())
    loader.log = Mock()
    loader.database = SimpleNamespace(_init_namespace=Mock())
    manifest = {'name': namespace, 'namespace': namespace, 'priority': 12000, 'compatible_svn': 190, 'support': []}
    init_body = "raise RuntimeError('test failed init')" if init_fails else 'pass'
    files = {
        'app.json': json.dumps(manifest),
        '__init__.py': 'from . import main\n',
        'main.py': f'''
from OlivOS import scheduleAPI

class Event:
    def init(plugin_event, Proc):
        {init_body}

    @staticmethod
    @scheduleAPI.interval(id='probe', hours=2)
    def probe(Proc):
        pass
''',
    }
    if packed:
        with ZipFile(source / f'{namespace}.opk', 'w') as archive:
            for name, value in files.items():
                archive.writestr(name, value)
    else:
        destination = source / namespace
        destination.mkdir()
        for name, value in files.items():
            (destination / name).write_text(value, encoding='utf-8')
    try:
        loader.load_plugin_list()
        loader.run_plugin_func(None, 'init_after')
        assert namespace in loader.plugin_models_dict
        assert not (cache / namespace).exists()
        scheduler, _ = runtime(*loader.plugin_models_dict.values())
        assert set(scheduler._tasks) == (set() if init_fails else {(namespace, 'probe')})
    finally:
        sys.modules.pop(f'{namespace}.main', None)
        sys.modules.pop(namespace, None)
