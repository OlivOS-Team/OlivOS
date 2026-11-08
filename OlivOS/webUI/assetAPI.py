# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/webUI/assetAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

# WebUI 宿主的静态资源清单；路由、打包内嵌与测试共用同一份数据。

import json
from pathlib import Path

MANIFEST_NAME = 'static-files.json'


def _filename(value):
    return (isinstance(value, str) and value not in ('', '.', '..') and
            Path(value).name == value and '/' not in value and '\\' not in value)


def missing(directory, assets):
    root = Path(directory)
    return tuple(name for name in assets['files'] if not (root / name).is_file())


def load(directory):
    path = Path(directory) / MANIFEST_NAME
    try:
        document = json.loads(path.read_text(encoding='utf-8'))
        entry = document['entry']
        root = document['root']
        static = document['static']
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError('WebUI 静态资源清单损坏：' + MANIFEST_NAME) from exc
    if not _filename(entry) or not isinstance(root, dict) or not isinstance(static, list):
        raise ValueError('WebUI 静态资源清单格式不正确：' + MANIFEST_NAME)

    root_files = {}
    for name, config in root.items():
        if not _filename(name) or not isinstance(config, dict):
            raise ValueError('WebUI 静态资源清单格式不正确：' + MANIFEST_NAME)
        mimetype = config.get('mimetype')
        headers = config.get('headers', {})
        if (not isinstance(mimetype, str) or not mimetype or not isinstance(headers, dict) or
                not all(isinstance(key, str) and isinstance(value, str) for key, value in headers.items())):
            raise ValueError('WebUI 静态资源清单格式不正确：' + MANIFEST_NAME)
        root_files[name] = {'mimetype': mimetype, 'headers': dict(headers)}

    static_files = tuple(static)
    if not all(_filename(name) for name in static_files):
        raise ValueError('WebUI 静态资源清单格式不正确：' + MANIFEST_NAME)
    files = (entry, *root_files, *static_files)
    if len(files) != len(set(files)):
        raise ValueError('WebUI 静态资源清单存在重复文件：' + MANIFEST_NAME)
    return {
        'entry': entry,
        'root': root_files,
        'static': static_files,
        'files': files,
    }
