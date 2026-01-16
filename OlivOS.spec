# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

# 判断平台
is_windows = sys.platform.startswith('win')
is_linux = sys.platform.startswith('linux')
is_mac = sys.platform.startswith('darwin')

# 判断是否为调试模式（通过环境变量或文件名判断）
is_debug = os.getenv('PYINSTALLER_DEBUG')

# 基础分析配置
a = Analysis(
    ['main.py'],
    pathex=['./'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'websockets.legacy.auth',
        'websockets.legacy.client',
        'websockets.legacy.server'
    ],
    hookspath=['./hook'],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

# Splash配置
splash = None
if is_windows:
    splash = Splash(
        './resource/intro.jpg',
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        text_size=12,
        minify_script=True,
        always_on_top=True,
    )

# EXE配置
exe_params = {
    'pyz': pyz,
    'a.scripts': a.scripts,
    'a.binaries': a.binaries,
    'a.zipfiles': a.zipfiles,
    'a.datas': a.datas,
    'name': 'OlivOS',
    'debug': False,
    'bootloader_ignore_signals': False,
    'strip': False,
    'upx': True,
    'upx_exclude': [],
    'icon': 'resource/favoricon.ico',
    'onefile': True
}

# 根据平台和调试模式调整参数
if splash:
    exe_params['splash'] = splash
    exe_params['splash.binaries'] = splash.binaries

# 控制台设置
exe_params['console'] = is_debug or not is_windows

# 运行时临时目录设置
if is_windows:
    exe_params['runtime_tmpdir'] = './runtime/'
else:
    exe_params['runtime_tmpdir'] = './'

# 创建EXE
exe = EXE(**exe_params)
