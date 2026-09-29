"""Native Windows notification-area renderer for Sofía.

The Win32 API is loaded only when start() is called on Windows, keeping tests
and non-Windows package consumers import-safe. Actions are emitted to a Queue;
the tray thread never mutates Sofía runtime state itself.
"""
from __future__ import annotations

from pathlib import Path
from queue import Queue
import sys
from threading import Event, Thread
from typing import Callable

from .control_center import (
    GameMode,
    TrayCommand,
    TrayStatus,
    tray_command_enabled,
    tray_command_requires_confirmation,
)


class WindowsTrayUnavailable(RuntimeError):
    pass


class WindowsTrayAgent:
    _CALLBACK_MESSAGE = 0x8000 + 41  # WM_APP + private offset

    def __init__(
        self,
        *,
        events: Queue[TrayCommand],
        status_provider: Callable[[], TrayStatus],
        icon_path: str | Path | None = None,
    ) -> None:
        if not isinstance(events, Queue):
            raise TypeError("events must be a Queue")
        if not callable(status_provider):
            raise TypeError("status_provider must be callable")
        self._events = events
        self._status_provider = status_provider
        self._icon_path = (
            Path(icon_path)
            if icon_path is not None
            else Path(__file__).with_name("assets") / "sofia_fox.ico"
        )
        self._thread: Thread | None = None
        self._ready = Event()
        self._stopped = Event()
        self._hwnd = None
        self._startup_error: Exception | None = None
        self._wndproc = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def icon_path(self) -> Path:
        return self._icon_path

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
            from ctypes import wintypes

            post_message = ctypes.windll.user32.PostMessageW
            post_message.argtypes = [
                wintypes.HWND,
                wintypes.UINT,
                wintypes.WPARAM,
                wintypes.LPARAM,
            ]
            post_message.restype = wintypes.BOOL
            post_message(self._hwnd, 0x0010, 0, 0)  # WM_CLOSE
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
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        MF_STRING = 0x0000
        MF_GRAYED = 0x0001
        MF_CHECKED = 0x0008
        MF_SEPARATOR = 0x0800
        MF_POPUP = 0x0010
        MB_OKCANCEL = 0x00000001
        MB_ICONWARNING = 0x00000030
        IDOK = 1
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

        # ctypes defaults function return values to a 32-bit int. Declare every
        # handle-bearing Win32 call we use so x64 HWND/HMENU/HICON values are
        # never truncated.
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        kernel32.GetLastError.argtypes = []
        kernel32.GetLastError.restype = wintypes.DWORD

        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        user32.RegisterClassW.restype = wintypes.WORD
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            ctypes.c_void_p,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.DestroyWindow.restype = wintypes.BOOL
        user32.PostMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.PostMessageW.restype = wintypes.BOOL
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.PostQuitMessage.restype = None

        user32.CreatePopupMenu.argtypes = []
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.AppendMenuW.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            ctypes.c_size_t,
            wintypes.LPCWSTR,
        ]
        user32.AppendMenuW.restype = wintypes.BOOL
        user32.DestroyMenu.argtypes = [wintypes.HMENU]
        user32.DestroyMenu.restype = wintypes.BOOL
        user32.TrackPopupMenu.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            ctypes.c_void_p,
        ]
        user32.TrackPopupMenu.restype = wintypes.UINT
        user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.MessageBoxW.argtypes = [
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.UINT,
        ]
        user32.MessageBoxW.restype = ctypes.c_int
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        user32.LoadIconW.restype = wintypes.HICON
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        user32.DestroyIcon.argtypes = [wintypes.HICON]
        user32.DestroyIcon.restype = wintypes.BOOL
        user32.GetMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG),
            wintypes.HWND,
            wintypes.UINT,
            wintypes.UINT,
        ]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = ctypes.c_ssize_t

        shell32.Shell_NotifyIconW.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(NOTIFYICONDATAW),
        ]
        shell32.Shell_NotifyIconW.restype = wintypes.BOOL

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
            1024: TrayCommand.LLM_LOAD_PRIMARY,
            1025: TrayCommand.LLM_LOAD_SECONDARY,
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

                llm_label = (
                    "Cognition (dual)"
                    if status.cognitive_routing_enabled
                    else "Cognition"
                )
                primary_label = status.llm_model or "not configured"
                primary_state = status.llm_primary_residency or "unknown"
                append(
                    llm,
                    MF_STRING | MF_GRAYED,
                    0,
                    f"Primary: {primary_label} [{primary_state}]",
                )
                if status.cognitive_routing_enabled:
                    secondary_label = (
                        status.llm_secondary_model or "not configured"
                    )
                    secondary_state = (
                        status.llm_secondary_residency or "unknown"
                    )
                    append(
                        llm,
                        MF_STRING | MF_GRAYED,
                        0,
                        f"Secondary: {secondary_label} [{secondary_state}]",
                    )
                residency_label = (
                    f"Auto residency: on, unload after "
                    f"{status.cognitive_idle_unload_seconds}s"
                    if status.cognitive_auto_manage
                    else "Auto residency: off"
                )
                append(
                    llm,
                    MF_STRING | MF_GRAYED,
                    0,
                    residency_label,
                )
                append(llm, MF_SEPARATOR, 0, None)
                for item_id, label, command in (
                    (1020, "Start", TrayCommand.LLM_START),
                    (1021, "Stop", TrayCommand.LLM_STOP),
                    (1022, "Restart", TrayCommand.LLM_RESTART),
                ):
                    flags = (
                        MF_STRING
                        if tray_command_enabled(command, status)
                        else MF_STRING | MF_GRAYED
                    )
                    append(llm, flags, item_id, label)
                load_primary_flags = (
                    MF_STRING
                    if tray_command_enabled(
                        TrayCommand.LLM_LOAD_PRIMARY,
                        status,
                    )
                    else MF_STRING | MF_GRAYED
                )
                append(llm, load_primary_flags, 1024, "Load Primary")
                if status.cognitive_routing_enabled:
                    load_secondary_flags = (
                        MF_STRING
                        if tray_command_enabled(
                            TrayCommand.LLM_LOAD_SECONDARY,
                            status,
                        )
                        else MF_STRING | MF_GRAYED
                    )
                    append(
                        llm,
                        load_secondary_flags,
                        1025,
                        "Load Secondary",
                    )
                unload_label = (
                    "Unload configured model"
                    if len(status.configured_llm_models) <= 1
                    else (
                        f"Unload {len(status.configured_llm_models)} "
                        "configured models"
                    )
                )
                append(llm, MF_STRING, 1023, unload_label)
                append(root, MF_POPUP, llm, f"{llm_label}: {status.llm_state}")

                for item_id, label, command in (
                    (1030, "Start", TrayCommand.RUNTIME_START),
                    (1031, "Stop", TrayCommand.RUNTIME_STOP),
                    (1032, "Restart", TrayCommand.RUNTIME_RESTART),
                ):
                    flags = (
                        MF_STRING
                        if tray_command_enabled(command, status)
                        else MF_STRING | MF_GRAYED
                    )
                    append(runtime, flags, item_id, label)
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
                if (
                    command is not None
                    and tray_command_requires_confirmation(command)
                ):
                    action = (
                        "stop"
                        if command is TrayCommand.RUNTIME_STOP
                        else "restart"
                    )
                    confirmed = user32.MessageBoxW(
                        hwnd,
                        (
                            f"This will {action} the Sofía runtime on "
                            f"{status.runtime_host or 'this host'}.\n\n"
                            "Continue?"
                        ),
                        "Confirm Sofía runtime control",
                        MB_OKCANCEL | MB_ICONWARNING,
                    )
                    if confirmed != IDOK:
                        command = None
                if command is not None:
                    self._events.put(command)
            finally:
                user32.DestroyMenu(root)

        nid = NOTIFYICONDATAW()
        loaded_icon = None

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
                if loaded_icon:
                    user32.DestroyIcon(loaded_icon)
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
            error = kernel32.GetLastError()
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
        loaded_icon = user32.LoadImageW(
            None,
            str(self._icon_path),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
        if loaded_icon:
            nid.hIcon = loaded_icon
        else:
            icon_resource = ctypes.cast(
                ctypes.c_void_p(IDI_APPLICATION),
                wintypes.LPCWSTR,
            )
            nid.hIcon = user32.LoadIconW(None, icon_resource)
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
