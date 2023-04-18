# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/hook.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import platform

# pillow
from PIL import Image

# sqlite
import sqlite3

# win
if platform.system() == 'Windows':
    import win32com.client
    import pythoncom
    import webview

# ext pack
# lxml
from lxml import etree

# yaml
import yaml

# openpyxl
import openpyxl

# aiohttp
import aiohttp

# qrcode
import qrcode

# weblib
import certifi
import httpx
import prompt_toolkit
import regex
import rich

import sys

# Are we running in a PyInstaller bundle
# https://pyinstaller.org/en/stable/runtime-information.html#run-time-information
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    class NullOutput(object):
        def write(self, string):
            pass

        def isatty(self):
            return False

    sys.stdout = NullOutput()
    sys.stderr = NullOutput()
