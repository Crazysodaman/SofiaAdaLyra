"""Exact, owner-authorized Windows desktop input, never ambient model control.

This is an OS executor for a single local, interactive session. It cannot be
used as a Fleet agent handler, elevate to another desktop, or drive a Hyper-V
guest from the host. Model output cannot manufacture the required FIDO2-bound
SAFE approval. The owner chooses an exact foreground window and operation.

Venus (gaming workstation) requires fresh, independent *live* game-process
inspection and a fresh, non-overridden NORMAL tray observation. UNKNOWN or
unreadable process/activity evidence denies input. Other hosts still need
one-use approval, an interactive session, STOP clear and exact foreground HWND.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
import ctypes
from ctypes import wintypes
import os
import platform
import re
import socket
import sys


_MAX_TEXT = 40
_ALLOWED_KEYS = frozenset({"tab", "enter", "escape", "left", "right", "up", "down", "backspace"})
_KEY_CODES = {"tab": 0x09, "enter": 0x0D, "escape": 0x1B, "left": 0x25, "up": 0x26,
              "right": 0x27, "down": 0x28, "backspace": 0x08}
# Non-Steam and launch-store games cannot all be detected by filename. An
# operator-curated deny set can only expand this list, never remove defaults.
_GAME_NAMES = frozenset({
    "factorio.exe", "doom.exe", "doomx64.exe", "doom eternal.exe",
    "haloinfinite.exe", "halo.exe", "mcc-win64-shipping.exe",
    "borderlands4.exe", "borderlands3.exe", "spaceengineers.exe",
    "cnc3game.dat", "starfield.exe", "eldenring.exe",
})
_NON_GAME_STEAM = frozenset({
    "steam.exe", "steamservice.exe", "steamwebhelper.exe",
    "gameoverlayui.exe", "wallpaper32.exe", "wallpaper64.exe",
    "vrserver.exe", "vrmonitor.exe", "vrcompositor.exe",
})
_SHA = re.compile(r"^[a-zA-Z0-9_.-]{1,120}$")


@dataclass(frozen=True, slots=True)
class DesktopAction:
    """Single deterministic input action with exact selected OS target."""
    host_id: str
    window_handle: int
    process_id: int
    operation: str
    key: str = ""
    text: str = ""
    x: int = -1
    y: int = -1

    def __post_init__(self) -> None:
        if not isinstance(self.host_id, str) or _SHA.fullmatch(self.host_id) is None:
            raise ValueError("exact bounded local host identity required")
        if type(self.window_handle) is not int or self.window_handle <= 0:
            raise ValueError("existing window handle required")
        if type(self.process_id) is not int or self.process_id <= 0:
            raise ValueError("exact foreground process ID required")
        if self.operation not in {"key_press", "type_text", "mouse_click"}:
            raise ValueError("only bounded keyboard or left click operations allowed")
        if self.operation == "key_press":
            if self.key not in _ALLOWED_KEYS or self.text or (self.x, self.y) != (-1, -1):
                raise ValueError("unsupported or mixed key request")
        elif self.operation == "type_text":
            if (not isinstance(self.text, str) or not self.text or
                len(self.text) > _MAX_TEXT or
                any(ord(c) < 32 or ord(c) == 127 for c in self.text) or
                self.key or (self.x, self.y) != (-1, -1)):
                raise ValueError("bounded printable Unicode text required")
        elif (self.key or self.text or type(self.x) is not int or
              type(self.y) is not int or not 0 <= self.x <= 32767 or
              not 0 <= self.y <= 32767):
            raise ValueError("exact screen coordinates required")

    def approval_parameters(self) -> dict:
        return {"host_id": self.host_id, "window_handle": self.window_handle,
                "process_id": self.process_id, "operation": self.operation,
                "key": self.key, "text": self.text, "x": self.x, "y": self.y}


def game_process_clear() -> bool:
    """Scan ALL observed local processes using the already-installed SYSTEM API.

    Failure, limit saturation or incomplete names/executable evidence means
    gaming cannot be ruled out. No optional psutil dependency or process
    injection is needed. Tray observations do NOT replace this fresh scan.
    """
    if sys.platform != "win32":
        raise PermissionError("Windows-only live game inspection")
    from sofia.system.capability import create_local_system_backend
    from sofia.system.model import (
        SystemCapabilityName, SystemCapabilityRequest,
        SystemCapabilityResultKind,
    )
    backend = create_local_system_backend()
    capability = next(
        (item for item in backend.supported_capabilities
         if item.name is SystemCapabilityName.PROCESS_INSPECT),
        None,
    )
    if capability is None:
        raise PermissionError("local process inspection unavailable")
    result = backend.execute(
        SystemCapabilityRequest(capability, {"limit": 2048})
    )
    if result.kind is not SystemCapabilityResultKind.SUCCESS:
        raise PermissionError("gaming status not fully observable")
    processes = tuple(result.evidence.get("processes", ()))
    if not processes or len(processes) >= 2048:
        raise PermissionError("process observation missing or truncated")
    extra = os.environ.get("SOFIA_GUI_EXTRA_GAME_EXECUTABLES", "")
    known = _GAME_NAMES | frozenset(
        p.strip().casefold() for p in extra.split(",") if p.strip()
    )
    from sofia.ops.activity import detect_windows_game
    for item in processes:
        if not getattr(item, "name", None):
            raise PermissionError("unknown running process identity")
    gaming, _ = detect_windows_game(
        processes, known_game_executables=known,
    )
    return not gaming

def require_workstation_clear(state_path: Path | str, host_id: str, at: datetime) -> None:
    """A manual NORMAL override never bypasses game protection on Venus."""
    if host_id.casefold() != "venus":
        return
    from sofia.ops.activity import ActivityMode, HostActivityStore
    state = HostActivityStore(state_path).state(host_id)
    if (state.override is not ActivityMode.AUTO or
        state.effective is not ActivityMode.NORMAL or
        state.source != "windows-process-inspection" or
        state.observed_at is None or
        at - state.observed_at < timedelta(0) or
        at - state.observed_at > timedelta(seconds=35)):
        raise PermissionError("Venus gaming safety requires fresh unoverridden NORMAL tray evidence")
    if not game_process_clear():
        raise PermissionError("a running game prohibits Venus desktop automation")


class WindowsDesktopInput:
    """Actual Win32 SendInput transport, restricted to the foreground session."""
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("interactive Win32 backend unavailable")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    def foreground(self) -> tuple[int, int]:
        active_console_session = int(self.kernel32.WTSGetActiveConsoleSessionId())
        if active_console_session == 0xFFFFFFFF:
            raise PermissionError("no active interactive Windows console")
        pid = wintypes.DWORD()
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        hwnd = int(self.user32.GetForegroundWindow() or 0)
        if hwnd <= 0 or not self.user32.GetWindowThreadProcessId(
            wintypes.HWND(hwnd), ctypes.byref(pid)
        ):
            raise PermissionError("no verifiable foreground window")
        current_pid = int(self.kernel32.GetCurrentProcessId())
        session = wintypes.DWORD()
        if not self.kernel32.ProcessIdToSessionId(current_pid, ctypes.byref(session)):
            raise PermissionError("cannot verify current user session")
        if session.value == 0 or session.value != active_console_session:
            raise PermissionError("desktop input requires the active local console, never a service or different session")
        return hwnd, int(pid.value)

    def _ensure_click_hits_approved_window(self, action: DesktopAction) -> None:
        """Refuse coordinates outside the exact selected foreground HWND.

        Foreground alone does not prove a click will land on that window:
        another application/overlay can cover a point. Win32's hit-test and
        root-window identity are independently checked before moving cursor.
        """
        rect = wintypes.RECT()
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
        if not self.user32.GetWindowRect(
            wintypes.HWND(action.window_handle), ctypes.byref(rect)
        ):
            raise PermissionError("approved window geometry cannot be verified")
        if not (rect.left <= action.x < rect.right and
                rect.top <= action.y < rect.bottom):
            raise PermissionError("click lies outside approved window")
        self.user32.WindowFromPoint.argtypes = [wintypes.POINT]
        self.user32.WindowFromPoint.restype = wintypes.HWND
        hit = int(self.user32.WindowFromPoint(
            wintypes.POINT(action.x, action.y)
        ) or 0)
        if hit == 0:
            raise PermissionError("click hit-test unavailable")
        self.user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user32.GetAncestor.restype = wintypes.HWND
        root = int(self.user32.GetAncestor(wintypes.HWND(hit), 2) or 0)
        if root != action.window_handle:
            raise PermissionError("another window or overlay covers approved click point")

    @staticmethod
    def _structures():
        ptr = ctypes.c_size_t
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ptr)]
        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ptr)]
        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                        ("wParamH", wintypes.WORD)]
        class DATA(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT),
                        ("hi", HARDWAREINPUT)]
        class INPUT(ctypes.Structure):
            _fields_ = [("type", wintypes.DWORD), ("data", DATA)]
        return MOUSEINPUT, KEYBDINPUT, INPUT

    def _send(self, events: list[tuple[str, int, int]]) -> None:
        M, K, I = self._structures()
        inputs = []
        for kind, value, flags in events:
            if kind == "key":
                inputs.append(I(1, I._fields_[1][1](ki=K(value, 0, flags, 0, 0))))
            elif kind == "unicode":
                inputs.append(I(1, I._fields_[1][1](ki=K(0, value, flags, 0, 0))))
            else:
                inputs.append(I(0, I._fields_[1][1](mi=M(0, 0, 0, flags, 0, 0))))
        array = (I * len(inputs))(*inputs)
        self.user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(I), ctypes.c_int]
        self.user32.SendInput.restype = wintypes.UINT
        if self.user32.SendInput(len(inputs), array, ctypes.sizeof(I)) != len(inputs):
            raise OSError(ctypes.get_last_error(), "Win32 SendInput rejected")

    def execute(self, action: DesktopAction, recheck) -> None:
        if action.operation == "mouse_click":
            recheck()
            self._ensure_click_hits_approved_window(action)
            # SetCursorPos avoids virtual-desktop coordinate normalization.
            if not self.user32.SetCursorPos(action.x, action.y):
                raise OSError(ctypes.get_last_error(), "SetCursorPos rejected")
            recheck()
            self._send([("mouse", 0, 0x0002), ("mouse", 0, 0x0004)])
        elif action.operation == "key_press":
            recheck()
            self._send([("key", _KEY_CODES[action.key], 0),
                        ("key", _KEY_CODES[action.key], 0x0002)])
        else:
            # A printable codepoint can be more than one UTF-16 unit. Deliver
            # each Unicode unit pair after a new host/activity/STOP check.
            raw = action.text.encode("utf-16-le")
            for offset in range(0, len(raw), 2):
                recheck()
                char = int.from_bytes(raw[offset:offset+2], "little")
                self._send([("unicode", char, 0x0004),
                            ("unicode", char, 0x0006)])


class DesktopInputService:
    """Production SAFE-approval gate before any single OS input operation."""
    def __init__(self, state_path: Path | str, *, backend=None) -> None:
        self.state_path = Path(state_path)
        self.backend = backend if backend is not None else WindowsDesktopInput()

    def execute(self, action: DesktopAction, *, approval_id: str) -> dict:
        if not isinstance(action, DesktopAction):
            raise TypeError("typed DesktopAction required")
        if not isinstance(approval_id, str) or not approval_id.strip():
            raise PermissionError("one-use owner approval required")
        real_host = socket.gethostname()
        if action.host_id.casefold() != real_host.casefold():
            raise PermissionError("requested host does not match executing OS")
        if sys.platform != "win32":
            raise PermissionError("only real Windows interactive sessions supported")
        from sofia.safe.execution_approval import ExecutionApprovalVerifier
        from sofia.safe.operator_stop import OperatorStopStore

        stop = OperatorStopStore(self.state_path)
        def recheck() -> None:
            now = datetime.now(timezone.utc)
            if stop.current().active:
                raise PermissionError("independent operator STOP active")
            require_workstation_clear(self.state_path, action.host_id, now)
            if self.backend.foreground() != (action.window_handle, action.process_id):
                raise PermissionError("original approved foreground window changed")
        # The approval is consumed immediately before the effect, never before
        # initial environmental checks; failed/partial injection is not replayed.
        recheck()
        ExecutionApprovalVerifier(self.state_path).consume(
            approval_id=approval_id, capability="screen.act_exact",
            parameters=action.approval_parameters(), now=datetime.now(timezone.utc),
        )
        recheck()
        self.backend.execute(action, recheck)
        # A successful result means the Win32 API accepted input, not that
        # another app processed it or that a game anti-cheat approves it.
        return {"status": "os_input_submitted", "host_id": real_host,
                "window_handle": action.window_handle,
                "process_id": action.process_id, "operation": action.operation,
                "effect_verified": False}
