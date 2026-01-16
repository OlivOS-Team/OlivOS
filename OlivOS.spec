# -*- mode: python ; coding: utf-8 -*-

import sys
import argparse

# 解析命令行参数
parser = argparse.ArgumentParser(description='PyInstaller 构建配置')
parser.add_argument('--debug-mode', action='store_true', help='启用调试模式（显示控制台）')
parser.add_argument('--no-splash', action='store_true', help='禁用启动画面')
parser.add_argument('--name', type=str, default='OlivOS', help='输出文件名称')
parser.add_argument('--no-upx', action='store_true', help='禁用UPX压缩')
args, unknown_args = parser.parse_known_args()

# 将未知参数保留给 PyInstaller
sys.argv = [sys.argv[0]] + unknown_args

block_cipher = None

# 判断平台
is_windows = sys.platform.startswith('win')
is_linux = sys.platform.startswith('linux')
is_mac = sys.platform.startswith('darwin')

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
if is_windows and not args.no_splash:
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
    'name': args.name,
    'debug': args.debug_mode,
    'bootloader_ignore_signals': False,
    'strip': False,
    'upx': not args.no_upx,
    'upx_exclude': [],
    'icon': 'resource/favoricon.ico'
}

# 添加Splash相关参数
if splash:
    exe_params['splash'] = splash
    exe_params['splash.binaries'] = splash.binaries

# 控制台设置
exe_params['console'] = args.debug_mode or not is_windows

# 运行时临时目录设置
if is_windows:
    exe_params['runtime_tmpdir'] = './runtime/'
else:
    exe_params['runtime_tmpdir'] = './'

# 创建EXE
exe = EXE(**exe_params)

# 打印构建信息
print("构建配置信息:")
print(f"  平台: {sys.platform}")
print(f"  调试模式: {'是' if args.debug_mode else '否'}")
print(f"  启动画面: {'启用' if splash else '禁用'}")
print(f"  UPX压缩: {'启用' if not args.no_upx else '禁用'}")
print(f"  输出名称: {args.name}")
print(f"  控制台: {'显示' if exe_params['console'] else '隐藏'}")
