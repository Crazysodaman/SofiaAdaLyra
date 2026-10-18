"""Explicit Windows ComfyUI Desktop launch and safe owner-only close.

ComfyUI Desktop can have multiple process wrappers. If the launched PID exits,
ownership is *not* transferred to another process automatically; close refuses.
"""
from __future__ import annotations
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

class ComfyHostError(RuntimeError):
    pass

def _psutil():
    try:
        import psutil
    except ImportError as exc:
        raise ComfyHostError("psutil required: pip install psutil") from exc
    return psutil

def _record_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise ComfyHostError("LOCALAPPDATA is required")
    return Path(base) / "SofiaAdaLyra" / "Creative" / "comfyui_owned.json"

def _same_process(rec, psutil):
    try:
        proc = psutil.Process(rec["pid"])
        return (proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
                and abs(proc.create_time() - rec["created"]) < 1.0
                and os.path.normcase(os.path.realpath(proc.exe())) == os.path.normcase(rec["exe"])
                and proc.username() == rec["user"])
    except (psutil.Error, OSError, KeyError, TypeError, ValueError):
        return False

def _load_record(path):
    try:
        if path.is_symlink() or path.stat().st_size > 4096:
            return None
        obj = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(obj, dict) and set(obj) == {"pid", "created", "exe", "user"}:
            return obj
    except (OSError, ValueError):
        pass
    return None

def _instances(psutil, exe: Path):
    target = os.path.normcase(str(exe.resolve()))
    found = []
    for p in psutil.process_iter(["pid", "exe"]):
        try:
            if p.info["exe"] and os.path.normcase(os.path.realpath(p.info["exe"])) == target:
                found.append(p.pid)
        except (psutil.Error, OSError):
            continue
    return found

def status(*, exe: Path, record_path: Path | None = None, psutil=None):
    psutil = psutil or _psutil()
    record = _load_record(record_path or _record_path())
    running = _instances(psutil, exe)
    owned = bool(record and _same_process(record, psutil) and record["pid"] in running)
    return {"running": bool(running), "running_instances": len(running),
            "owned_instance_running": owned, "owned_pid": record["pid"] if owned else None,
            "safe_to_close": owned and len(running) == 1}

def launch(*, exe: Path, record_path: Path | None = None, psutil=None, popen=subprocess.Popen):
    if sys.platform != "win32":
        raise ComfyHostError("launch supported only in an interactive Windows session")
    psutil = psutil or _psutil()
    record_path = record_path or _record_path()
    if not exe.is_absolute() or exe.suffix.lower() != ".exe" or not exe.is_file() or exe.is_symlink():
        raise ComfyHostError("provide the installed ComfyUI Desktop .exe path")
    if _instances(psutil, exe):
        return {"result": "already_running_unowned", "started_by_sofia": False, "may_close": False}
    if record_path.exists():
        existing = _load_record(record_path)
        if existing and _same_process(existing, psutil):
            raise ComfyHostError("owned process record exists; inspect status before launching")
        raise ComfyHostError("stale/invalid ownership record; manual review required")
    proc = popen([str(exe)], cwd=str(exe.parent), shell=False, close_fds=True)
    try:
        p = psutil.Process(proc.pid)
        created = p.create_time()
        actual_exe = os.path.normcase(os.path.realpath(p.exe()))
        if actual_exe != os.path.normcase(os.path.realpath(str(exe))):
            raise ComfyHostError("launcher spawned a different executable; not claiming ownership")
        record = {"pid": proc.pid, "created": created, "exe": actual_exe, "user": p.username()}
        record_path.parent.mkdir(parents=True, exist_ok=True)
        with record_path.open("x", encoding="utf-8") as stream:
            json.dump(record, stream)
    except (OSError, ValueError) as exc:
        raise ComfyHostError("could not verify or persist launch ownership") from exc
    return {"result": "launched_owned", "started_by_sofia": True, "may_close": True, "pid": proc.pid}

def _send_close(pid: int) -> int:
    """Post WM_CLOSE to visible windows owned by this PID, never taskkill."""
    user32 = ctypes.windll.user32
    sent = 0
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(hwnd, extra):
        nonlocal sent
        window_pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == pid and user32.IsWindowVisible(hwnd):
            sent += int(bool(user32.PostMessageW(hwnd, 0x0010, 0, 0)))
        return True
    user32.EnumWindows(callback_type(visit), 0)
    return sent

def close(*, exe: Path, record_path: Path | None = None, psutil=None, send_close=_send_close,
          jobs_running: int | None = None):
    if sys.platform != "win32":
        raise ComfyHostError("close supported only on Windows")
    if jobs_running is None or type(jobs_running) is not int or jobs_running != 0:
        raise ComfyHostError("refusing close without verified zero running jobs")
    psutil = psutil or _psutil()
    record_path = record_path or _record_path()
    rec = _load_record(record_path)
    if not rec or not _same_process(rec, psutil):
        return {"result": "not_owned", "close_sent": False}
    if len(_instances(psutil, exe)) != 1:
        raise ComfyHostError("multiple instances; refusing to close")
    if send_close(rec["pid"]) < 1:
        raise ComfyHostError("no owned application window accepted WM_CLOSE")
    return {"result": "graceful_close_requested", "close_sent": True, "pid": rec["pid"]}

def main(argv=None):
    parser = argparse.ArgumentParser(description="ComfyUI Desktop host lifecycle; safe manual actions only")
    parser.add_argument("--exe", type=Path, required=True, help="Installed ComfyUI Desktop exe")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--status", action="store_true")
    actions.add_argument("--launch", action="store_true")
    actions.add_argument("--close", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.status:
            result = status(exe=args.exe)
        elif args.launch:
            result = launch(exe=args.exe)
        else:
            from .comfyui_bridge import ComfyUIBridge
            queue = ComfyUIBridge().queue()
            if queue["running"] or queue["pending"]:
                raise ComfyHostError("ComfyUI queue is not idle; refusing close")
            result = close(exe=args.exe, jobs_running=queue["running"])
        print(json.dumps(result, indent=2))
        return 0
    except ComfyHostError as exc:
        parser.exit(2, f"ComfyUI host: {exc}\n")

if __name__ == "__main__":
    raise SystemExit(main())
