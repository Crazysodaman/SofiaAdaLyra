"""Windows native owner-confirmed exact-window capture, without extra packages.

Win32 PrintWindow renders the selected client/window into an in-memory bitmap,
and the standard library encodes PNG without opening files or seeing the whole
desktop. Protected/accelerated/black surfaces cannot be assumed readable.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from io import BytesIO
import struct
import sys
import zlib

_MAX_SIZE = 12_000_000
_MAX_ENCODED = 16 * 1024 * 1024


def _png_from_bgra(bgra: bytes, width: int, height: int) -> bytes:
    if width <= 0 or height <= 0 or width * height > _MAX_SIZE:
        raise ValueError("screenshot geometry exceeds privacy/size bound")
    if len(bgra) != width * height * 4:
        raise ValueError("incomplete screenshot pixel buffer")
    rows = bytearray()
    for pos in range(0, len(bgra), width * 4):
        line = bgra[pos:pos + width * 4]
        rows.append(0)
        for offset in range(0, len(line), 4):
            rows.extend((line[offset + 2], line[offset + 1], line[offset]))
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(
            ">I", zlib.crc32(kind + data) & 0xffffffff,
        )
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) +
           chunk(b"IDAT", zlib.compress(bytes(rows), 6)) +
           chunk(b"IEND", b""))
    if len(png) > _MAX_ENCODED:
        raise PermissionError("captured PNG too large to retain in memory")
    return png


class WindowsWindowCapture:
    """Local owner confirmation and exact HWND PrintWindow only."""
    def __init__(self, *, user32=None, gdi32=None) -> None:
        if sys.platform != "win32":
            raise RuntimeError("native Windows window capture unavailable")
        self.user32 = user32 or ctypes.WinDLL("user32", use_last_error=True)
        self.gdi32 = gdi32 or ctypes.WinDLL("gdi32", use_last_error=True)

    def select_and_capture(self, *, exact_window: int, exact_pid: int, recheck) -> bytes:
        recheck()
        hwnd = wintypes.HWND(exact_window)
        title_buffer = ctypes.create_unicode_buffer(260)
        self.user32.GetWindowTextW(hwnd, title_buffer, 260)
        title = title_buffer.value[:120]
        if not title or not self.user32.IsWindowVisible(hwnd):
            raise PermissionError("window invisible or title unavailable")
        # The OS confirmation dialog makes consent interactive instead of
        # trusting text, LLM output or a subprocess flag.
        question = (
            f"Allow SOFIA to capture ONE PNG image of this exact window?\n\n"
            f"{title}\nPID: {exact_pid}\nHWND: {exact_window}\n\n"
            "Captured pixels are kept in memory only; no hidden background watch."
        )
        answer = self.user32.MessageBoxW(
            None, question, "SOFIA explicit screen capture",
            0x00000004 | 0x00000020 | 0x00040000,  # YESNO | QUESTION | TOPMOST
        )
        if answer != 6:
            raise PermissionError("owner did not confirm Windows screen capture")
        recheck()
        rect = wintypes.RECT()
        if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            raise PermissionError("window geometry unavailable")
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w <= 0 or h <= 0 or w * h > _MAX_SIZE:
            raise PermissionError("invalid or oversized screen target")
        display = self.user32.GetDC(hwnd)
        if not display:
            raise PermissionError("no window device context")
        memory_dc = bitmap = previous = None
        try:
            memory_dc = self.gdi32.CreateCompatibleDC(display)
            bitmap = self.gdi32.CreateCompatibleBitmap(display, w, h)
            if not memory_dc or not bitmap:
                raise PermissionError("unable to allocate exact-window bitmap")
            previous = self.gdi32.SelectObject(memory_dc, bitmap)
            if not previous:
                raise PermissionError("window bitmap selection failed")
            recheck()
            # PrintWindow is per HWND, never a desktop screenshot or sibling
            # window. Rendering failures, including protected media, refuse.
            self.user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
            self.user32.PrintWindow.restype = wintypes.BOOL
            if not self.user32.PrintWindow(hwnd, memory_dc, 2):
                raise PermissionError("selected window refused or cannot render capture")

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [
                    ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                    ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                    ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                    ("biClrImportant", wintypes.DWORD),
                ]
            header = BITMAPINFOHEADER(
                ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0,
                0, 0, 0, 0,
            )
            raw = ctypes.create_string_buffer(w * h * 4)
            self.gdi32.GetDIBits.argtypes = [
                wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                wintypes.LPVOID, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT,
            ]
            self.gdi32.GetDIBits.restype = ctypes.c_int
            # Must deselect before some GDI implementations expose DIB.
            self.gdi32.SelectObject(memory_dc, previous)
            previous = None
            lines = self.gdi32.GetDIBits(memory_dc, bitmap, 0, h,
                                        raw, ctypes.byref(header), 0)
            if lines != h:
                raise PermissionError("selected window did not provide complete pixels")
            recheck()
            return _png_from_bgra(raw.raw, w, h)
        finally:
            if previous and memory_dc:
                self.gdi32.SelectObject(memory_dc, previous)
            if bitmap:
                self.gdi32.DeleteObject(bitmap)
            if memory_dc:
                self.gdi32.DeleteDC(memory_dc)
            self.user32.ReleaseDC(hwnd, display)
