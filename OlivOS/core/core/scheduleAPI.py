# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/core/core/scheduleAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   插件定时声明及宿主调度时区配置。
'''

import hashlib
import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from threading import Lock
from typing import NamedTuple

import pytz
import tzlocal

__all__ = ['interval', 'cron', 'date', 'read_settings', 'save_settings', 'timezone_choices', 'ScheduleConflict']

_SETTINGS_PATH = Path('conf/plugin_schedule.json')
_SETTINGS_LOCK = Lock()
_TIMEZONES = tuple(name for name in pytz.all_timezones if name == 'UTC' or '/' in name)
_METADATA = '_olivos_schedule'


class _Declaration(NamedTuple):
    kind: str
    id: object
    values: tuple


def _mark(kind, task_id, *values):
    def decorate(callback):
        declarations = vars(callback).get(_METADATA, ())
        setattr(callback, _METADATA, declarations + (_Declaration(kind, task_id, values),))
        return callback

    return decorate


def interval(id, *, seconds=0, minutes=0, hours=0, run_on_start=False):
    """声明固定间隔的同步任务；可选择让首次触发与本代激活对齐。"""
    return _mark('interval', id, seconds, minutes, hours, run_on_start)


def cron(id, *, hour=None, minute=None, day_of_week=None):
    """按宿主调度时区的墙钟时间触发，秒固定为 0。"""
    return _mark('cron', id, hour, minute, day_of_week)


def date(id, *, run_at):
    """按宿主调度时区的本地 datetime 提供一次触发机会。"""
    return _mark('date', id, run_at)


class ScheduleConflict(ValueError):
    """所编辑的配置已被其他请求修改。"""


def timezone_choices():
    """返回可选 IANA 时区；调用方单独展示 'system'。"""
    return list(_TIMEZONES)


def _valid_timezone(value):
    return isinstance(value, str) and (value == 'system' or value in _TIMEZONES)


def _status(timezone, revision, error=None):
    return {'timezone': timezone, 'revision': revision, 'error': error}


def _read_path(path):
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return _status('system', 'missing')
    except OSError:
        return _status(None, 'unreadable', '无法读取 conf/plugin_schedule.json，请先检查文件权限')
    revision = hashlib.sha256(data).hexdigest()
    try:
        settings = json.loads(data.decode('utf-8'))
    except (UnicodeError, ValueError, RecursionError):
        settings = None
    if not isinstance(settings, dict) or type(settings.get('version')) is not int or settings['version'] != 1:
        return _status(None, revision, 'conf/plugin_schedule.json 格式错误，请先修复文件')
    timezone = settings.get('timezone')
    if not _valid_timezone(timezone):
        return _status(None, revision, 'conf/plugin_schedule.json 时区无效，请选择有效的 IANA 时区并重载插件')
    return _status(timezone, revision)


def read_settings(root):
    """读取已保存的 timezone、revision 和 error；不解析系统时区。"""
    return _read_path(Path(root) / _SETTINGS_PATH)


def save_settings(root, timezone, revision):
    """在同一写锁中校验版本并原子保存；不覆盖损坏的原配置。"""
    path = Path(root) / _SETTINGS_PATH
    with _SETTINGS_LOCK:
        if not _valid_timezone(timezone) or not isinstance(revision, str):
            raise ValueError('请选择系统时区或有效的 IANA 时区，并提交当前版本')
        current = _read_path(path)
        if current['revision'] != revision:
            raise ScheduleConflict('时区设置已更新，请刷新后再保存')
        if current['error']:
            raise ValueError(current['error'])
        if current['timezone'] == timezone:
            return current
        path.parent.mkdir(parents=True, exist_ok=True)
        data = (json.dumps({'version': 1, 'timezone': timezone}, indent=2) + '\n').encode('utf-8')
        fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.plugin_schedule-')
        try:
            with os.fdopen(fd, 'wb') as output:
                output.write(data)
            os.replace(temporary, path)
        finally:
            with suppress(FileNotFoundError):
                os.unlink(temporary)
        return _status(timezone, hashlib.sha256(data).hexdigest())


def _effective_settings(root):
    settings = dict(read_settings(root), effective_timezone=None)
    zone = None
    if not settings['error']:
        try:
            name = settings['timezone']
            if name == 'system':
                # tzlocal 会缓存名称；换代时读取宿主的新配置，但不采用其 UTC 回退。
                tzlocal.reload_localzone()
                name = tzlocal.get_localzone_name()
            zone = pytz.timezone(name)
        except (OSError, ValueError, LookupError, AttributeError):
            settings['error'] = '无法解析宿主调度时区，请选择有效的 IANA 时区并重载插件'
        else:
            settings['effective_timezone'] = zone.zone
    return settings, zone
