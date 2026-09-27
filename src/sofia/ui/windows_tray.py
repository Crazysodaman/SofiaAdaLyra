"""Native Windows notification-area renderer for Sofía.

The Win32 API is loaded only when start() is called on Windows, keeping tests
and non-Windows package consumers import-safe. Actions are emitted to a Queue;
the tray thread never mutates Sofía runtime state itself.
"""
from __future__ import annotations

from queue import Queue
import sys
from threading import Event, Thread
from typing import Callable

from .control_center import GameMode, TrayCommand, TrayStatus


class WindowsTrayUnavailable(RuntimeError):
    pass


class WindowsTrayAgent:
    _CALLBACK_MESSAGE = 0x8000 + 41  # WM_APP + private offset

    def __init__(
        self,
        *,
        events: Queue[TrayCommand],
        status_provider: Callable[[], TrayStatus],
    ) -> None:
        if not isinstance(events, Queue):
            raise TypeError("events must be a Queue")
        if not callable(status_provider):
            raise TypeError("status_provider must be callable")
        self._events = events
        self._status_provider = status_provider
        self._thread: Thread | None = None
        self._ready = Event()
        self._stopped = Event()
        self._hwnd = None
        self._startup_error: Exception | None = None
        self._wndproc = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if sys.platform != "win32":
            raise WindowsTrayUnavailable("Windows notification-area UI requires Windows")
        if self._thread is not None:
            raise RuntimeError("tray agent already started")
        self._thread = Thread(target=self._run, name="sofia-windows-tray", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        if self._startup_error is not None:
            raise WindowsTrayUnavailable(str(self._startup_error)) from self._startup_error
        if self._hwnd is None:
            raise WindowsTrayUnavailable("Windows tray window did not initialize")

    def stop(self) -> None:
        if self._thread is None:
            return
        if self._hwnd is not None and sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.PostMessageW(self._hwnd, 0x0010, 0, 0)  # WM_CLOSE
        self._stopped.wait(timeout=5)
        self._thread = None

    def _run(self) -> None:
        try:
            self._run_windows()
        except Exception as exc:
            self._startup_error = exc
            self._ready.set()
        finally:
            self._stopped.set()

    def _run_windows(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        kernel32 = ctypes.windll.kernel32

        WM_CLOSE = 0x0010
        WM_DESTROY = 0x0002
        WM_RBUTTONUP = 0x0205
        WM_LBUTTONDBLCLK = 0x0203
        NIM_ADD = 0x00000000
        NIM_DELETE = 0x00000002
        NIF_MESSAGE = 0x00000001
        NIF_ICON = 0x00000002
        NIF_TIP = 0x00000004
        IDI_APPLICATION = 32512
        MF_STRING = 0x0000
        MF_GRAYED = 0x0001
        MF_CHECKED = 0x0008
        MF_SEPARATOR = 0x0800
        MF_POPUP = 0x0010
        TPM_RIGHTBUTTON = 0x0002
        TPM_RETURNCMD = 0x0100
        TPM_NONOTIFY = 0x0080

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t,
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        )

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        class NOTIFYICONDATAW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT),
                ("uFlags", wintypes.UINT),
                ("uCallbackMessage", wintypes.UINT),
                ("hIcon", wintypes.HICON),
                ("szTip", wintypes.WCHAR * 128),
                ("dwState", wintypes.DWORD),
                ("dwStateMask", wintypes.DWORD),
                ("szInfo", wintypes.WCHAR * 256),
                ("uTimeoutOrVersion", wintypes.UINT),
                ("szInfoTitle", wintypes.WCHAR * 64),
                ("dwInfoFlags", wintypes.DWORD),
                ("guidItem", GUID),
                ("hBalloonIcon", wintypes.HICON),
            ]

        action_ids = {
            1001: TrayCommand.OPEN_CHAT,
            1002: TrayCommand.OPEN_FLEET,
            1010: TrayCommand.GAME_AUTO,
            1011: TrayCommand.GAME_ON,
            1012: TrayCommand.GAME_OFF,
            1020: TrayCommand.LLM_START,
            1021: TrayCommand.LLM_STOP,
            1022: TrayCommand.LLM_RESTART,
            1023: TrayCommand.LLM_UNLOAD_MODEL,
            1030: TrayCommand.RUNTIME_START,
            1031: TrayCommand.RUNTIME_STOP,
            1032: TrayCommand.RUNTIME_RESTART,
            1040: TrayCommand.OPEN_SETTINGS,
            1041: TrayCommand.DIAGNOSTICS,
            1099: TrayCommand.EXIT_UI,
        }

        def append(menu, flags, item_id, label):
            if not user32.AppendMenuW(menu, flags, item_id, label):
                raise ctypes.WinError()

        def show_menu(hwnd):
            status = self._status_provider()
            if not isinstance(status, TrayStatus):
                raise TypeError("status_provider must return TrayStatus")

            root = user32.CreatePopupMenu()
            game = user32.CreatePopupMenu()
            llm = user32.CreatePopupMenu()
            runtime = user32.CreatePopupMenu()
            if not all((root, game, llm, runtime)):
                raise ctypes.WinError()
            try:
                append(root, MF_STRING | MF_GRAYED, 0, f"Sofía: {status.runtime_state}")
                host = status.runtime_host or "unknown"
                append(root, MF_STRING | MF_GRAYED, 0, f"Runtime host: {host}")
                append(root, MF_SEPARATOR, 0, None)
                append(root, MF_STRING, 1001, "Open Sofía")
                append(
                    root,
                    MF_STRING,
                    1002,
                    f"Fleet: {status.fleet_healthy}/{status.fleet_total} healthy",
                )

                for item_id, label, value in (
                    (1010, "Auto", GameMode.AUTO),
                    (1011, "On", GameMode.ON),
                    (1012, "Off", GameMode.OFF),
                ):
                    flags = MF_STRING | (MF_CHECKED if status.game_mode is value else 0)
                    append(game, flags, item_id, label)
                append(root, MF_POPUP, game, "Game Mode")

                llm_label = status.llm_model or "LLM Engine"
                append(llm, MF_STRING, 1020, "Start")
                append(llm, MF_STRING, 1021, "Stop")
                append(llm, MF_STRING, 1022, "Restart")
                append(llm, MF_STRING, 1023, "Unload model")
                append(root, MF_POPUP, llm, f"{llm_label}: {status.llm_state}")

                append(runtime, MF_STRING, 1030, "Start")
                append(runtime, MF_STRING, 1031, "Stop")
                append(runtime, MF_STRING, 1032, "Restart")
                append(root, MF_POPUP, runtime, "Sofía Runtime")

                append(root, MF_SEPARATOR, 0, None)
                append(root, MF_STRING, 1040, "Settings…")
                append(root, MF_STRING, 1041, "Diagnostics")
                append(root, MF_SEPARATOR, 0, None)
                append(root, MF_STRING, 1099, "Exit Tray Agent")

                point = wintypes.POINT()
                user32.GetCursorPos(ctypes.byref(point))
                user32.SetForegroundWindow(hwnd)
                selected = user32.TrackPopupMenu(
                    root,
                    TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                    point.x,
                    point.y,
                    0,
                    hwnd,
                    None,
                )
                command = action_ids.get(int(selected))
                if command is not None:
                    self._events.put(command)
            finally:
                user32.DestroyMenu(root)

        nid = NOTIFYICONDATAW()

        @WNDPROC
        def wndproc(hwnd, message, wparam, lparam):
            if message == self._CALLBACK_MESSAGE:
                mouse_message = int(lparam) & 0xFFFF
                if mouse_message == WM_LBUTTONDBLCLK:
                    self._events.put(TrayCommand.OPEN_CHAT)
                    return 0
                if mouse_message == WM_RBUTTONUP:
                    try:
                        show_menu(hwnd)
                    except Exception:
                        self._events.put(TrayCommand.DIAGNOSTICS)
                    return 0
            if message == WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if message == WM_DESTROY:
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)

        self._wndproc = wndproc
        instance = kernel32.GetModuleHandleW(None)
        class_name = "SofiaAdaLyraTrayAgent"
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = wndproc
        window_class.hInstance = instance
        window_class.lpszClassName = class_name
        atom = user32.RegisterClassW(ctypes.byref(window_class))
        if not atom:
            error = ctypes.GetLastError()
            if error != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                raise ctypes.WinError(error)

        hwnd = user32.CreateWindowExW(
            0, class_name, "Sofía Tray", 0, 0, 0, 0, 0,
            None, None, instance, None,
        )
        if not hwnd:
            raise ctypes.WinError()
        self._hwnd = hwnd

        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = self._CALLBACK_MESSAGE
        nid.hIcon = user32.LoadIconW(None, IDI_APPLICATION)
        nid.szTip = "Sofía Ada Lyra"
        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            user32.DestroyWindow(hwnd)
            raise ctypes.WinError()

        self._ready.set()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        self._hwnd = None
