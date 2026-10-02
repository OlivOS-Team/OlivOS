# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   main.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

# here put the import lib

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path


def report_startup_error():
    # 启动阶段日志组件可能尚未可用，直接保存异常，不依赖消息队列。
    details = traceback.format_exc()
    message = 'OlivOS 启动或运行失败，请查看错误日志。'
    try:
        log_dir = Path('logfile').resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / datetime.now().strftime('startup-error-%Y%m%d-%H%M%S-%f.log')
        log_path.write_text(details, encoding='utf-8')
        message += f'\n\n错误日志：{log_path}'
    except OSError:
        message += '\n\n错误日志保存失败，请检查目录写入权限。'
    error = sys.exc_info()[1]
    message += f'\n\n{type(error).__name__}: {error}'
    if sys.stderr is not None:
        try:
            sys.stderr.write(details)
        except (OSError, ValueError):
            pass
    if sys.platform == 'win32' and getattr(sys, 'frozen', False):
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'OlivOS 启动错误', 0x10)


if __name__ == '__main__':
    try:
        import OlivOS

        if not os.path.exists('./conf'):
            os.makedirs('./conf')
        OlivOS.bootAPI.Entity(
            basic_conf='./conf/basic.json',
            patch_conf='./conf/config.json'
        ).start()
    except SystemExit as error:
        if error.code is not None and error.code != 0:
            report_startup_error()
        raise
    except Exception:
        report_startup_error()
        sys.exit(1)
