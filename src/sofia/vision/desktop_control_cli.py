"""Local interactive owner-only keyboard/mouse control ceremony.

Run on a machine's interactive Windows desktop, NEVER from a service or VM
hypervisor acting on another session. Inspect a target, then pin its HWND/PID.
Each click, key or bounded text entry requires a separate signed owner FIDO2
approval and a 5-second refocus window. No standing grant or model CLI calls.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from sofia.config import production_state_path
from sofia.vision.desktop_control import (
    DesktopAction, DesktopInputService, WindowsDesktopInput,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.vision.desktop_control_cli",
        description="One-use signed owner input for a specific Windows foreground window",
    )
    parser.add_argument("--state-path", type=Path)
    parser.add_argument("--inspect", action="store_true")
    parser.add_argument("--window-handle", type=int)
    parser.add_argument("--process-id", type=int)
    parser.add_argument("--operation", choices=("key_press", "type_text", "mouse_click"))
    parser.add_argument("--key", default="")
    parser.add_argument("--x", type=int, default=-1)
    parser.add_argument("--y", type=int, default=-1)
    parser.add_argument("--credential-id")
    args = parser.parse_args(argv)
    try:
        backend = WindowsDesktopInput()
        if args.inspect:
            if any((args.operation, args.credential_id, args.window_handle,
                    args.process_id)):
                raise ValueError("--inspect cannot mix with an action or approval")
            hwnd, pid = backend.foreground()
            import socket
            print(json.dumps({"host_id": socket.gethostname(),
                              "window_handle": hwnd, "process_id": pid}))
            return 0
        if not args.operation or not args.credential_id:
            raise ValueError("one operation and enrolled owner FIDO2 credential required")
        if args.window_handle is None or args.process_id is None:
            raise ValueError("pin the exact HWND and PID reported by --inspect")
        if args.operation == "type_text":
            # stdin, not CLI argv: avoid exposing text in process command lines
            # or shell history. Printed receipt also contains no text.
            print("Type up to 40 printable characters for the approved target:", file=sys.stderr)
            raw = sys.stdin.readline(160)
            if raw.endswith("\n"):
                raw = raw[:-1]
            text = raw
        else:
            text = ""
        import socket
        action = DesktopAction(
            host_id=socket.gethostname(),
            window_handle=args.window_handle, process_id=args.process_id,
            operation=args.operation, key=args.key,
            text=text, x=args.x, y=args.y,
        )
        state_path = args.state_path or production_state_path()
        from sofia.safe.owner_browser import authorize_exact_action
        # Physically authenticated, one-use receipt bound to the exact
        # host/HWND/PID/action, never generated from model assertions.
        approval = authorize_exact_action(
            state_path, capability="screen.act_exact",
            parameters=action.approval_parameters(),
            credential_id=args.credential_id, expires_seconds=60,
        )
        print("Security key approved. Refocus the EXACT target window within 5 seconds.")
        time.sleep(5)
        result = DesktopInputService(state_path, backend=backend).execute(
            action, approval_id=approval.approval_id,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError, TypeError, PermissionError) as exc:
        print(
            f"Desktop action refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
