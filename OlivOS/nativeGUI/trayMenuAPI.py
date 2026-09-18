# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/nativeGUI/trayMenuAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   Windows 托盘非默认菜单项的粗体绘制
'''

import ctypes
from contextlib import contextmanager
from ctypes import wintypes

import pystray


class BoldMenuItem(pystray.MenuItem):
    """仅改变显示字体，不占用 Windows 菜单唯一的默认动作。"""


class LOGFONT(ctypes.Structure):
    _fields_ = [(name, wintypes.LONG) for name in (
        'height', 'width', 'escapement', 'orientation', 'weight'
    )] + [(name, wintypes.BYTE) for name in (
        'italic', 'underline', 'strikeout', 'charset', 'out_precision',
        'clip_precision', 'quality', 'pitch'
    )] + [('face', wintypes.WCHAR * 32)]


class MEASUREITEM(ctypes.Structure):
    _fields_ = [(name, wintypes.UINT) for name in (
        'control_type', 'control_id', 'item_id', 'width', 'height'
    )] + [('item_data', ctypes.c_size_t)]


class DRAWITEM(ctypes.Structure):
    _fields_ = [(name, wintypes.UINT) for name in (
        'control_type', 'control_id', 'item_id', 'action', 'state'
    )] + [
        ('window', wintypes.HWND), ('dc', wintypes.HDC),
        ('rect', wintypes.RECT), ('item_data', ctypes.c_size_t)
    ]


def _bind(library, name, result, *args):
    function = getattr(library, name)
    function.restype = result
    function.argtypes = args
    return function


class TrayIcon(pystray.Icon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bold_items = {}
        user = ctypes.windll.user32
        gdi = ctypes.windll.gdi32
        self._get_dc = _bind(user, 'GetDC', wintypes.HDC, wintypes.HWND)
        self._release_dc = _bind(user, 'ReleaseDC', ctypes.c_int, wintypes.HWND, wintypes.HDC)
        self._get_menu_font = _bind(
            ctypes.windll.uxtheme, 'GetThemeSysFont', ctypes.c_long,
            wintypes.HANDLE, ctypes.c_int, ctypes.POINTER(LOGFONT)
        )
        self._create_font = _bind(gdi, 'CreateFontIndirectW', wintypes.HANDLE, ctypes.POINTER(LOGFONT))
        self._select = _bind(gdi, 'SelectObject', wintypes.HANDLE, wintypes.HDC, wintypes.HANDLE)
        self._delete = _bind(gdi, 'DeleteObject', wintypes.BOOL, wintypes.HANDLE)
        self._draw_text = _bind(
            user, 'DrawTextW', ctypes.c_int, wintypes.HDC, wintypes.LPCWSTR,
            ctypes.c_int, ctypes.POINTER(wintypes.RECT), wintypes.UINT
        )
        self._color = _bind(user, 'GetSysColor', wintypes.DWORD, ctypes.c_int)
        self._brush = _bind(user, 'GetSysColorBrush', wintypes.HANDLE, ctypes.c_int)
        self._fill = _bind(user, 'FillRect', ctypes.c_int, wintypes.HDC,
                           ctypes.POINTER(wintypes.RECT), wintypes.HANDLE)
        self._text_color = _bind(gdi, 'SetTextColor', wintypes.DWORD, wintypes.HDC, wintypes.DWORD)
        self._bg_mode = _bind(gdi, 'SetBkMode', ctypes.c_int, wintypes.HDC, ctypes.c_int)
        self._metric = _bind(user, 'GetSystemMetrics', ctypes.c_int, ctypes.c_int)
        self._message_handlers.update({0x002C: self._measure_bold, 0x002B: self._draw_bold})

    def _create_window(self, atom):
        window = super()._create_window(atom)
        # pystray 默认只分发托盘窗口消息，自绘菜单还需要菜单宿主窗口的通知。
        self._HWND_TO_ICON[window] = self
        return window

    def _mainloop(self):
        try:
            return super()._mainloop()
        finally:
            self._HWND_TO_ICON.pop(self._menu_hwnd, None)

    def _update_menu(self):
        self._bold_items.clear()
        return super()._update_menu()

    def _create_menu_item(self, descriptor, callbacks):
        item = super()._create_menu_item(descriptor, callbacks)
        if isinstance(descriptor, BoldMenuItem):
            # MFT_OWNERDRAW；default 仍留给“打开终端”，避免多个 MFS_DEFAULT 报错。
            item.fType |= 0x0100
            self._bold_items[item.wID] = descriptor.text
        return item

    @contextmanager
    def _bold_font(self, dc):
        font = LOGFONT()
        # TMT_MENUFONT 使用系统菜单字体，与默认菜单项的字体和字号一致。
        if self._get_menu_font(None, 803, ctypes.byref(font)) < 0:
            raise OSError('Cannot read the Windows menu font')
        font.weight = 700
        handle = self._create_font(ctypes.byref(font))
        if not handle:
            raise ctypes.WinError()
        previous = self._select(dc, handle)
        try:
            yield
        finally:
            self._select(dc, previous)
            self._delete(handle)

    def _measure_bold(self, wparam, lparam):
        item = MEASUREITEM.from_address(lparam)
        if item.control_type != 1 or item.item_id not in self._bold_items:
            return 0
        dc = self._get_dc(None)
        try:
            with self._bold_font(dc):
                rect = wintypes.RECT()
                # DT_CALCRECT | DT_SINGLELINE | DT_NOPREFIX
                self._draw_text(dc, self._bold_items[item.item_id], -1, ctypes.byref(rect), 0x0C20)
                item.width = rect.right + self._metric(71) + 8  # SM_CXMENUCHECK
                item.height = max(rect.bottom + 4, self._metric(15))  # SM_CYMENU
        finally:
            self._release_dc(None, dc)
        return 1

    def _draw_bold(self, wparam, lparam):
        item = DRAWITEM.from_address(lparam)
        if item.control_type != 1 or item.item_id not in self._bold_items:
            return 0
        selected = bool(item.state & 0x0001)  # ODS_SELECTED
        disabled = bool(item.state & 0x0006)  # ODS_GRAYED | ODS_DISABLED
        self._fill(item.dc, ctypes.byref(item.rect), self._brush(13 if selected else 4))
        color = 17 if disabled else (14 if selected else 7)
        old_color = self._text_color(item.dc, self._color(color))
        old_mode = self._bg_mode(item.dc, 1)  # TRANSPARENT
        try:
            with self._bold_font(item.dc):
                rect = wintypes.RECT(item.rect.left + self._metric(71) + 4, item.rect.top,
                                     item.rect.right, item.rect.bottom)
                # DT_SINGLELINE | DT_VCENTER | DT_NOPREFIX
                self._draw_text(item.dc, self._bold_items[item.item_id], -1, ctypes.byref(rect), 0x0824)
        finally:
            self._text_color(item.dc, old_color)
            self._bg_mode(item.dc, old_mode)
        return 1
