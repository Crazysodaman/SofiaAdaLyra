"""Actual local Linux desktop inspection, scoped capture and input.

Hyprland Wayland: Hyprland's own IPC identifies the active client, slurp -r
requires a human to choose exactly that client's rectangle, grim captures only
that rectangle, and an already installed ydotool/ydotoold performs exact
one-shot input. X11: xdotool selects/identifies an X window; ImageMagick's
import reads that exact window; xdotool XTEST sends one bounded input action.

Nothing runs as root, launches a daemon, accesses a remote compositor, creates
a virtual device, or grants a model authorization. Missing tools, sessions,
identity, lock status or changed geometry are explicit refusals.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

_LINUX_KEYS = {
    "tab": 15, "enter": 28, "escape": 1, "left": 105,
    "right": 106, "up": 103, "down": 108, "backspace": 14,
}
_X11_KEYS = frozenset(_LINUX_KEYS)
_GEOMETRY = re.compile(r"^-?\d+,-?\d+ [1-9]\d{0,4}x[1-9]\d{0,4}$")
_PNG = b"\x89PNG\r\n\x1a\n"
_MAX_CAPTURE_BYTES = 16 * 1024 * 1024


def _run(argv: tuple[str, ...], *, data: bytes | None = None,
         timeout: int = 8, maximum: int = 262144) -> bytes:
    """No shell and no ambient environment mutations; bound OS output."""
    if not argv or any(not isinstance(a, str) for a in argv):
        raise ValueError("fixed argv required")
    try:
        p = subprocess.run(argv, input=data, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout,
                           check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PermissionError("Linux desktop provider unavailable or timed out") from exc
    if p.returncode != 0 or len(p.stdout) > maximum or len(p.stderr) > 4096:
        raise PermissionError("Linux desktop provider rejected command or output bound")
    return p.stdout


def require_linux_session() -> str:
    if sys.platform != "linux" or os.geteuid() == 0:
        raise PermissionError("Linux desktop requires an unprivileged local user")
    kind = os.environ.get("XDG_SESSION_TYPE", "")
    if kind not in {"wayland", "x11"}:
        raise PermissionError("no supported Linux graphical session")
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        raise PermissionError("remote SSH cannot impersonate the local screen owner")
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        raise PermissionError("interactive user runtime directory required")
    p = Path(runtime)
    if p.is_symlink() or not p.is_dir() or p.stat().st_uid != os.getuid():
        raise PermissionError("desktop user runtime directory not trustworthy")
    if kind == "wayland" and (not os.environ.get("WAYLAND_DISPLAY")
                               or not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")):
        raise PermissionError("only a local Hyprland Wayland session is supported")
    if kind == "x11" and not os.environ.get("DISPLAY"):
        raise PermissionError("X11 display unavailable")
    return kind


def _json(argv: tuple[str, ...]) -> dict:
    raw = _run(argv)
    try:
        parsed = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise PermissionError("compositor returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise PermissionError("compositor returned unexpected state")
    return parsed


def _hypr_locked() -> None:
    raw = _run(("hyprctl", "-j", "locked")).strip().lower()
    # A missing/unknown lock report must NOT be interpreted as unlocked.
    if raw not in (b"false", b"0", b'{"locked":false}', b'{"locked": false}'):
        raise PermissionError("Hyprland lock state is active or unknown")


class LinuxDesktop:
    """One precise local desktop, selectable by the OWNER, not by model text."""
    def __init__(self, *, runner=_run, session=require_linux_session) -> None:
        self.runner = runner
        self.kind = session()

    def _hypr_window(self) -> dict:
        _hypr_locked()
        value = _json(("hyprctl", "-j", "activewindow"))
        try:
            address = int(value["address"], 16)
            pid = int(value["pid"])
            xy, size = value["at"], value["size"]
            x, y, w, h = int(xy[0]), int(xy[1]), int(size[0]), int(size[1])
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise PermissionError("Hyprland active target identity missing") from exc
        if address <= 0 or pid <= 0 or w <= 0 or h <= 0 or w * h > 12_000_000:
            raise PermissionError("invalid active window geometry or identity")
        if value.get("mapped") is False or value.get("hidden") is True:
            raise PermissionError("window is hidden or not mapped")
        return {"handle": address, "pid": pid, "geometry": (x, y, w, h)}

    def foreground(self) -> tuple[int, int]:
        if self.kind == "wayland":
            window = self._hypr_window()
            return window["handle"], window["pid"]
        # xdotool getactivewindow is an X11 client identity, not a Wayland
        # XWayland proxy. Separate PID lookup is checked at every recheck.
        hwnd = int(self.runner(("xdotool", "getactivewindow")).strip())
        pid = int(self.runner(("xdotool", "getwindowpid", str(hwnd))).strip())
        if hwnd <= 0 or pid <= 0:
            raise PermissionError("X11 active window identity unavailable")
        return hwnd, pid

    def select_and_capture(self, *, exact_window: int, exact_pid: int,
                           recheck) -> bytes:
        """Human-pick the exact pre-approved target then capture real PNG."""
        recheck()
        if self.kind == "wayland":
            window = self._hypr_window()
            if (window["handle"], window["pid"]) != (exact_window, exact_pid):
                raise PermissionError("Wayland window changed before owner selection")
            x, y, w, h = window["geometry"]
            chosen = f"{x},{y} {w}x{h}"
            if not _GEOMETRY.fullmatch(chosen):
                raise PermissionError("invalid selected Wayland rectangle")
            # slurp -r requires a physical click on the single named region.
            # It cannot select an arbitrary monitor, private app or overlay.
            selected = self.runner(("slurp", "-r"), data=(chosen + "\n").encode(),
                                   timeout=35).decode("ascii", "strict").strip()
            if selected != chosen:
                raise PermissionError("owner cancelled or chose different target")
            recheck()
            if self._hypr_window()["geometry"] != (x, y, w, h):
                raise PermissionError("window geometry changed after OS selection")
            frame = self.runner(("grim", "-g", chosen, "-"),
                                timeout=15, maximum=_MAX_CAPTURE_BYTES)
        else:
            # xdotool selectwindow physically changes cursor, waits for click.
            selected = int(self.runner(("xdotool", "selectwindow"), timeout=35).strip())
            if selected != exact_window:
                raise PermissionError("X11 owner selected a different window")
            recheck()
            frame = self.runner(("import", "-window", str(exact_window), "png:-"),
                                timeout=15, maximum=_MAX_CAPTURE_BYTES)
        if not frame.startswith(_PNG) or len(frame) > _MAX_CAPTURE_BYTES:
            raise PermissionError("OS did not return a bounded PNG capture")
        return frame

    def execute(self, action, recheck) -> None:
        """At most one approved operation, with fresh focus and STOP checks."""
        recheck()
        if self.kind == "wayland":
            if action.operation == "key_press":
                code = _LINUX_KEYS[action.key]
                self.runner(("ydotool", "key", f"{code}:1", f"{code}:0"))
            elif action.operation == "type_text":
                for char in action.text:
                    recheck()
                    self.runner(("ydotool", "type", "-f", "-"),
                                data=char.encode("utf-8"))
            else:
                x, y, w, h = self._hypr_window()["geometry"]
                if not (x <= action.x < x + w and y <= action.y < y + h):
                    raise PermissionError("click outside the active Hyprland window")
                self.runner(("ydotool", "mousemove", "--absolute",
                             "-x", str(action.x), "-y", str(action.y)))
                recheck()
                self.runner(("ydotool", "click", "0xC0"))
        else:
            if action.operation == "key_press":
                self.runner(("xdotool", "key", "--clearmodifiers", action.key))
            elif action.operation == "type_text":
                for char in action.text:
                    recheck()
                    self.runner(("xdotool", "type", "--clearmodifiers", "--file", "-"),
                                data=char.encode("utf-8"))
            else:
                # X11 XTEST affects the active pointer/desktop; check focus
                # before moving, and independently again before click.
                self.runner(("xdotool", "mousemove", "--sync", str(action.x),
                             str(action.y)))
                recheck()
                self.runner(("xdotool", "click", "1"))


def require_linux_game_clear() -> None:
    """Refuse user-desktop input if game detection is uncertain or positive.

    This is a conservative machine-level process scan in addition to STOP and
    foreground identity; a paused/running game is still a game.
    """
    from sofia.system.capability import create_local_system_backend
    from sofia.system.model import (
        SystemCapabilityName, SystemCapabilityRequest, SystemCapabilityResultKind,
    )
    from sofia.ops.activity import detect_windows_game
    backend = create_local_system_backend()
    cap = next((item for item in backend.supported_capabilities
                if item.name is SystemCapabilityName.PROCESS_INSPECT), None)
    if cap is None:
        raise PermissionError("Linux running-game inspection unavailable")
    result = backend.execute(SystemCapabilityRequest(cap, {"limit": 2048}))
    if result.kind is not SystemCapabilityResultKind.SUCCESS:
        raise PermissionError("Linux game inspection inconclusive")
    processes = tuple(result.evidence.get("processes", ()))
    if not processes or len(processes) >= 2048:
        raise PermissionError("Linux game-process inspection truncated")
    names = {"factorio", "doom", "halo", "borderlands4", "spaceengineers",
             "steam_app", "wine64-preloader"}
    names |= {n.strip().casefold() for n in
              os.environ.get("SOFIA_GUI_EXTRA_GAME_EXECUTABLES", "").split(",")
              if n.strip()}
    if any(not getattr(p, "name", "") for p in processes):
        raise PermissionError("some Linux processes lack game classification")
    found, _ = detect_windows_game(
        processes, known_game_executables=frozenset(names),
    )
    if found:
        raise PermissionError("game is running: desktop automation denied")
