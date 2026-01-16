# -*- mode: python ; coding: utf-8 -*-

import sys
import os

block_cipher = None

is_windows = sys.platform.startswith('win')
is_linux = sys.platform.startswith('linux')
is_mac = sys.platform.startswith('darwin')
is_debug = os.getenv('PYINSTALLER_DEBUG') == 1

print(
    f"is_windows: {is_windows}\n"
    f"is_linux: {is_linux}\n"
    f"is_mac: {is_mac}\n"
    f"is_debug: {is_debug}\n"
)

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
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        splash,
        splash.binaries,
        [],
        name='OlivOS',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir='./runtime/',
        console=is_debug,
        icon='resource/favoricon.ico'
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='OlivOS',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir='./',
        console=True,
        icon='resource/favoricon.ico'
    )
