# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/core/core/pluginSchedule.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   加载器内的定时事件源、定向分发和排空。
'''

import inspect
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from queue import Empty, Full, Queue
from threading import Lock
from typing import NamedTuple

import pytz
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_MAX_INSTANCES, EVENT_JOB_MISSED
from apscheduler.executors.pool import ThreadPoolExecutor as ReporterPool
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from OlivOS.core.core import API, scheduleAPI

_TASK_LIMIT = 128
_QUEUE_SIZE = 64
_WORKERS = 4
_LATE_SECONDS = 5
_DUE_ACTION = 'plugin_timer_due'
_TASK_ID = re.compile(r'[a-zA-Z0-9_.-]{1,64}')
_DAY = r'(?:mon|tue|wed|thu|fri|sat|sun)'
_WEEKDAYS = re.compile(rf'{_DAY}(?:-{_DAY})?(?:,{_DAY}(?:-{_DAY})?)*', re.IGNORECASE)
_EPSILON = timedelta(microseconds=1)
_MAX_LATENESS = timedelta(seconds=_LATE_SECONDS)


def _utc_now():
    return datetime.now(pytz.UTC)


class _Task(NamedTuple):
    callback: object
    trigger: object
    start_immediately: bool


class _DeclarationError(ValueError):
    """只有宿主编写的异常正文可以直接写入日志。"""


def _trigger(declaration, zone, activation):
    if declaration.kind == 'interval':
        seconds, minutes, hours, start_immediately = declaration.values
        if any(type(value) not in (int, float) or not value >= 0 for value in (seconds, minutes, hours)):
            raise _DeclarationError('interval requires non-negative numbers')
        if type(start_immediately) is not bool:
            raise _DeclarationError('run_on_start must be a bool')
        period = timedelta(seconds=seconds, minutes=minutes, hours=hours)
        if period < timedelta(seconds=1):
            raise _DeclarationError('interval must be at least one second')
        first_period = activation + period
        anchor = activation if start_immediately else first_period
        return IntervalTrigger(seconds=period.total_seconds(), start_date=anchor, timezone=pytz.UTC), start_immediately
    if declaration.kind == 'cron':
        hour, minute, weekday = declaration.values
        if any(value is not None and type(value) not in (int, str) for value in (hour, minute)):
            raise _DeclarationError('hour and minute require integers or cron field expressions')
        if weekday is not None and (not isinstance(weekday, str) or not _WEEKDAYS.fullmatch(weekday)):
            raise _DeclarationError('day_of_week requires names such as mon or mon-fri')
        if zone is None:
            raise _DeclarationError('cron requires a resolved schedule timezone')
        return CronTrigger(hour=hour, minute=minute, day_of_week=weekday, second=0, timezone=zone), False
    run_at, = declaration.values
    if not isinstance(run_at, datetime) or run_at.tzinfo is not None:
        raise _DeclarationError('date requires a naive datetime')
    if zone is None:
        raise _DeclarationError('date requires a resolved schedule timezone')
    try:
        run_at = zone.localize(run_at, is_dst=None).astimezone(pytz.UTC)
    except pytz.AmbiguousTimeError:
        raise _DeclarationError('date is ambiguous in the schedule timezone') from None
    except pytz.NonExistentTimeError:
        raise _DeclarationError('date does not exist in the schedule timezone') from None
    return DateTrigger(run_date=run_at, timezone=pytz.UTC), False


def _valid_callback(callback):
    if not inspect.isfunction(callback) or (
        inspect.isgeneratorfunction(callback) or inspect.iscoroutinefunction(callback)
        or inspect.isasyncgenfunction(callback)
    ):
        return False
    try:
        parameters = tuple(inspect.signature(callback, follow_wrapped=False).parameters.values())
    except (TypeError, ValueError):
        return False
    return len(parameters) == 1 and parameters[0].kind in (
        inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD,
    )


def _declarations(event):
    if not isinstance(event, type):
        return
    for descriptor in vars(event).values():
        if isinstance(descriptor, (staticmethod, classmethod)):
            for declaration in vars(descriptor).get(scheduleAPI._METADATA, ()):
                yield declaration, None  # 装饰顺序错误：staticmethod 必须在外层。
            callback = descriptor.__func__
        else:
            callback = descriptor
        if inspect.isfunction(callback):
            for declaration in vars(callback).get(scheduleAPI._METADATA, ()):
                yield declaration, callback if isinstance(descriptor, staticmethod) else None


def _report_due(namespace, task_id, generation, epoch):
    # APScheduler 的 Job 不引用加载器或插件回调。
    return {'namespace': namespace, 'task_id': task_id, 'generation': generation, 'epoch': epoch}


class PluginSchedule:
    def __init__(self, proc, generation, *, now=_utc_now, root='.'):
        self.proc = proc
        self.generation = generation
        self.now = now
        self.root = root
        self.epoch = 0
        self._accepting = False
        self._tasks = {}
        self._fired_dates = set()
        self._queue = Queue(_QUEUE_SIZE)
        self._lock = Lock()
        self._latest = {}
        self._pending = {}
        self._running = {}
        self._drained_at = {}
        self._futures = set()
        self._source = None
        self._workers = None

    def _log(self, level, label, task, scheduled_at=None):
        planned = f' scheduled_at={scheduled_at.isoformat()}' if scheduled_at else ''
        self.proc.log(level, f'Plugin schedule {label}: [{task[0]}/{task[1]}]{planned} generation={self.generation}')

    def start(self, models):
        status, zone = scheduleAPI._effective_settings(self.root)
        if status['error']:
            self.proc.log(4, f'Plugin schedule: {status["error"]}')
        activation = self.now()
        for model in models:
            if model.get('schedule_init_failed'):
                continue
            namespace = model['namespace']
            by_id = {}
            for declaration, callback in _declarations(model['model'].main.Event):
                task_id = declaration.id
                if not isinstance(task_id, str) or not _TASK_ID.fullmatch(task_id):
                    self._log(4, 'invalid task ID (expected 1–64 ASCII letters, digits, _, . or -)', (namespace, '?'))
                    continue
                by_id.setdefault(task_id, []).append((declaration, callback))
            for task_id, declarations in by_id.items():
                key = namespace, task_id
                if len(declarations) != 1:
                    self._log(4, 'duplicate task ID', key)
                    continue
                declaration, callback = declarations[0]
                if not _valid_callback(callback):
                    self._log(4, 'expected a synchronous static method accepting one Proc argument', key)
                    continue
                try:
                    trigger, immediate = _trigger(declaration, zone, activation)
                except (TypeError, ValueError, OverflowError) as error:
                    # APScheduler 参数异常可能带原始插件参数，不把它们写入日志。
                    detail = (str(error) if isinstance(error, _DeclarationError)
                              else f'invalid {declaration.kind} trigger')
                    self._log(4, detail, key)
                    continue
                if isinstance(trigger, DateTrigger) and trigger.run_date < activation:
                    self._log(3, 'date missed before activation', key, trigger.run_date)
                    continue
                if len(self._tasks) == _TASK_LIMIT:
                    self._log(4, 'registration limit reached', key)
                    continue
                self._tasks[key] = _Task(callback, trigger, immediate)
        if self._tasks:
            self._workers = ThreadPoolExecutor(max_workers=_WORKERS, thread_name_prefix='plugin-timer')
            self._start_source(activation, recovering=False)
        return status

    def _start_source(self, now, *, recovering):
        source = BackgroundScheduler(timezone=pytz.UTC, executors={'default': ReporterPool(1)})
        epoch = self.epoch
        lookup = {}
        for key, task in self._tasks.items():
            if isinstance(task.trigger, DateTrigger):
                next_at = task.trigger.run_date
                if recovering:
                    if key in self._fired_dates:
                        continue
                    if next_at <= now:
                        self._fired_dates.add(key)
                        self._log(3, 'date missed during drain', key, next_at)
                        continue
            elif not recovering and task.start_immediately:
                next_at = now
            else:
                next_at = task.trigger.get_next_fire_time(None, now + _EPSILON)
            if next_at is None:
                continue
            job_id = str(len(lookup))
            lookup[job_id] = key
            source.add_job(
                _report_due, task.trigger, id=job_id, args=(*key, self.generation, epoch),
                next_run_time=next_at, coalesce=True, misfire_grace_time=_LATE_SECONDS, max_instances=1,
            )
        if not lookup:
            return
        source.add_listener(lambda event: self._report_event(event, lookup),
                            EVENT_JOB_EXECUTED | EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES)
        with self._lock:
            self._accepting = True
        self._source = source
        source.start()

    def _report_event(self, event, lookup):
        key = lookup[event.job_id]
        if event.code == EVENT_JOB_MAX_INSTANCES:
            for scheduled_at in event.scheduled_run_times:
                self._log(3, 'source skipped (reporter busy)', key, scheduled_at.astimezone(pytz.UTC))
            return
        scheduled_at = event.scheduled_run_time.astimezone(pytz.UTC)
        if isinstance(self._tasks[key].trigger, DateTrigger):
            with self._lock:
                self._fired_dates.add(key)
        if event.code == EVENT_JOB_MISSED:
            self._log(3, 'source missed', key, scheduled_at)
            return
        payload = dict(event.retval, scheduled_at=scheduled_at)
        self.enqueue(API.Control.packet(_DUE_ACTION, payload))

    def enqueue(self, packet):
        if not isinstance(packet, API.Control.packet) or packet.action != _DUE_ACTION:
            return False
        data = packet.key
        if not isinstance(data, dict):
            return False
        key = data.get('namespace'), data.get('task_id')
        scheduled_at = data.get('scheduled_at')
        if not all(isinstance(part, str) for part in key) or not isinstance(scheduled_at, datetime):
            return False
        if scheduled_at.tzinfo is not pytz.UTC and scheduled_at.utcoffset() != timedelta(0):
            return False
        reason = None
        with self._lock:
            if (not self._accepting or data.get('generation') != self.generation
                    or data.get('epoch') != self.epoch or key not in self._tasks):
                return False
            last = self._latest.get(key)
            if last is not None and scheduled_at <= last:
                reason = 'duplicate or out of order'
            else:
                self._latest[key] = scheduled_at
                if self.now() - scheduled_at > _MAX_LATENESS:
                    reason = 'late on receipt'
                elif key in self._pending or key in self._running:
                    reason = 'skipped (task already pending or running)'
                else:
                    try:
                        self._queue.put_nowait(packet)
                    except Full:
                        reason = 'event queue full'
                    else:
                        self._pending[key] = packet
                        return True
        self._log(3, reason, key, scheduled_at)
        return False

    def dispatch(self, budget=8):
        if not self._accepting or self._queue.empty():
            return False
        self._futures = {future for future in self._futures if not future.done()}
        worked = False
        for _ in range(budget):
            try:
                packet = self._queue.get_nowait()
            except Empty:
                break
            worked = True
            data = packet.key
            key = data['namespace'], data['task_id']
            try:
                self._futures.add(self._workers.submit(self._execute, key, packet))
            except RuntimeError:
                with self._lock:
                    if self._pending.get(key) is packet:
                        del self._pending[key]
                self._log(4, 'worker submission failed', key, data['scheduled_at'])
        return worked

    def _execute(self, key, packet):
        data = packet.key
        scheduled_at = data['scheduled_at']
        with self._lock:
            if self._pending.get(key) is not packet:
                return
            del self._pending[key]
            if not self._accepting or data['epoch'] != self.epoch:
                return
            late = self.now() - scheduled_at > _MAX_LATENESS
            if not late:
                self._running[key] = packet
        if late:
            self._log(3, 'late before execution', key, scheduled_at)
            return
        began = time.monotonic()
        level, result = 0, 'completed'
        try:
            self._tasks[key].callback(self.proc)
        except BaseException as error:
            # 不输出插件异常正文：远程服务异常可能含账号或凭据。
            level, result = 4, f'callback failed ({type(error).__name__})'
        finally:
            try:
                self._log(level, f'{result} in {time.monotonic() - began:.3f}s', key, scheduled_at)
            finally:
                with self._lock:
                    if self._running.get(key) is packet:
                        if not self._accepting:
                            self._drained_at[key] = time.monotonic()
                        del self._running[key]

    def close_gate(self):
        with self._lock:
            self._accepting = False
            self.epoch += 1
            self._latest.clear()
            self._pending.clear()
            self._drained_at.clear()
        if self._source is not None:
            self._source.pause()
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                break
        for future in self._futures:
            future.cancel()
        self._futures.clear()

    def running_tasks(self):
        with self._lock:
            return list(self._running)

    def drain_state(self, deadline):
        with self._lock:
            return list(self._running), [key for key, finished in self._drained_at.items() if finished > deadline]

    def _close_source(self):
        if self._source is not None:
            self._source.shutdown(wait=True)
            self._source = None

    def recover(self):
        self._close_source()
        if self._tasks:
            self._start_source(self.now(), recovering=True)

    def shutdown(self):
        self._close_source()
        if self._workers is not None:
            self._workers.shutdown(wait=True)
            self._workers = None
