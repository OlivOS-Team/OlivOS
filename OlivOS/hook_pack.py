r"""
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/hook.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
"""

import platform

# sqlite
import sqlite3

# pillow
from PIL import Image

# win
if platform.system() == 'Windows':
    import winsound

    import pythoncom
    import webview
    import win32com.client

# ext pack
# lxml
import email
import smtplib
import sys

# aiohttp
import aiohttp

# weblib
import certifi
import httpx

# openpyxl
import openpyxl
import prompt_toolkit

# pyjson5
import pyjson5

# qrcode
import qrcode
import regex
import rich

# yaml
import yaml
from lxml import etree

# Are we running in a PyInstaller bundle
# https://pyinstaller.org/en/stable/runtime-information.html#run-time-information
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):

    class NullOutput:
        def write(self, string):
            pass

        def isatty(self):
            return False

    sys.stdout = NullOutput()
    sys.stderr = NullOutput()
