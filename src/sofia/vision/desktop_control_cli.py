"""Owner-only interactive Windows/Linux exact screen capture and input CLI.

An existing local authenticated owner must approve each exact action with a
separate physical FIDO2 key. The OS then requires owner selection/confirmation.
Model messages cannot invoke this as a Fleet or autonomous tool.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import sys
import time

from sofia.platform.config import production_state_path
from sofia.vision.desktop_control import DesktopAction, DesktopInputService


def _local_backend():
    if sys.platform == "win32":
        from sofia.vision.desktop_control import WindowsDesktopInput
        return WindowsDesktopInput()
    if sys.platform == "linux":
        from sofia.vision.linux_desktop import LinuxDesktop
        return LinuxDesktop()
    raise PermissionError("Windows or Linux interactive console required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.vision.desktop_control_cli",
        description="Signed owner control and snapshot of a local exact window",
    )
    parser.add_argument("--state-path", type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--inspect", action="store_true")
    group.add_argument("--capture", action="store_true")
    group.add_argument("--operation", choices=("key_press", "type_text", "mouse_click"))
    parser.add_argument("--window-handle", type=lambda v: int(v, 0))
    parser.add_argument("--process-id", type=int)
    parser.add_argument("--key", default="")
    parser.add_argument("--x", type=int, default=-1)
    parser.add_argument("--y", type=int, default=-1)
    parser.add_argument("--credential-id")
    parser.add_argument("--verify-action", action="store_true", help="Require owner FIDO2 screenshot before AND after one exact input")
    parser.add_argument("--describe-model", help="explicit local Ollama image model for approved capture")
    args = parser.parse_args(argv)
    try:
        backend = _local_backend()
        host = socket.gethostname()
        if args.describe_model and not args.capture:
            raise ValueError("image interpretation needs explicit capture selection")
        if args.verify_action and not args.operation:
            raise ValueError("post-action visual verification requires one exact input")
        if args.inspect:
            if (args.window_handle is not None or args.process_id is not None
                or args.credential_id or args.key or args.x != -1 or args.y != -1):
                raise ValueError("inspect is read-only and takes no authority options")
            hwnd, pid = backend.foreground()
            print(json.dumps({"host_id": host, "window_handle": hwnd,
                              "process_id": pid, "os": sys.platform}))
            return 0
        if not args.credential_id or not args.window_handle or not args.process_id:
            raise ValueError("exact inspected HWND, PID and enrolled FIDO2 key required")
        if backend.foreground() != (args.window_handle, args.process_id):
            raise PermissionError("original target is not currently foreground")
        from sofia.safe.owner_browser import authorize_exact_action
        state_path = args.state_path or production_state_path()
        if args.capture:
            if args.key or args.x != -1 or args.y != -1:
                raise ValueError("capture cannot also send input")
            from sofia.vision.capture import local_target_id, ScreenCaptureService
            from sofia.vision.journeys import ScreenJourney, propose_owner_screen_journey
            target = local_target_id(host, args.window_handle, args.process_id)
            request = propose_owner_screen_journey(
                journey=ScreenJourney.LOOK_AT_WINDOW,
                principal_id="person:sparks", audience_id="local:text",
                device_id=host, target_id=target,
                purpose="One owner-selected local window screenshot",
                at=datetime.now(timezone.utc),
            )
            params = {
                "host_id": host, "window_handle": args.window_handle,
                "process_id": args.process_id, "target_id": target,
                "permit_id": request.permit.permit_id,
                "journey": request.journey.value,
                "purpose": request.permit.purpose,
            }
            approval = authorize_exact_action(
                state_path, capability="screen.capture_once",
                parameters=params, credential_id=args.credential_id,
                expires_seconds=30,
            )
            frame = ScreenCaptureService(
                state_path, foreground_backend=backend,
            ).capture_once(request, approval_id=approval.approval_id)
            observation = None
            if args.describe_model:
                from sofia.vision.interpret import describe_frame
                observation = describe_frame(frame, model=args.describe_model)
            print(json.dumps({
                "visual_description_untrusted": (None if observation is None else observation.description),
                "status": "actual_window_pixels_captured_in_memory",
                "frame_sha256": frame.evidence.receipt.digest_sha256,
                "permit_id": frame.evidence.receipt.permit_id,
                "semantic_content_verified": False,
                "authorized_input": False,
                "pixels_persisted": False,
            }, sort_keys=True))
            return 0
        text = ""
        if args.operation == "type_text":
            print("Enter <=40 printable characters (never enter passwords):",
                  file=sys.stderr)
            text = sys.stdin.readline(160).removesuffix("\n")
        action = DesktopAction(
            host_id=host, window_handle=args.window_handle,
            process_id=args.process_id, operation=args.operation,
            key=args.key, text=text, x=args.x, y=args.y,
        )
        if args.verify_action:
            from dataclasses import asdict
            from sofia.vision.action_workflow import ReviewedScreenAction, ScreenActionWorkflow
            from sofia.vision.capture import local_target_id, ScreenCaptureService
            from sofia.vision.journeys import ScreenJourney, propose_owner_screen_journey

            target = local_target_id(host, args.window_handle, args.process_id)
            def owner_snapshot_request():
                return propose_owner_screen_journey(
                    journey=ScreenJourney.LOOK_AT_WINDOW,
                    principal_id="person:sparks", audience_id="local:text",
                    device_id=host, target_id=target,
                    purpose="Review a single input action on the exact selected window",
                    at=datetime.now(timezone.utc),
                )
            reviewed = ReviewedScreenAction(
                action=action, before=owner_snapshot_request(),
                after=owner_snapshot_request(),
            )
            def authorize_snapshot(request):
                params = {
                    "host_id": host,
                    "window_handle": action.window_handle,
                    "process_id": action.process_id,
                    "target_id": target,
                    "permit_id": request.permit.permit_id,
                    "journey": request.journey.value,
                    "purpose": request.permit.purpose,
                }
                return authorize_exact_action(
                    state_path, capability="screen.capture_once",
                    parameters=params, credential_id=args.credential_id,
                    expires_seconds=30,
                ).approval_id
            def authorize_input(requested_action):
                return authorize_exact_action(
                    state_path, capability="screen.act_exact",
                    parameters=requested_action.approval_parameters(),
                    credential_id=args.credential_id, expires_seconds=60,
                ).approval_id
            print("Before-capture FIDO2, exact input FIDO2, and after-capture FIDO2 are separate approvals.")
            result = ScreenActionWorkflow(
                capture_service=ScreenCaptureService(
                    state_path, foreground_backend=backend,
                ),
                input_service=DesktopInputService(
                    state_path, backend=backend,
                ),
            ).perform_staged(
                reviewed, approve_capture=authorize_snapshot,
                approve_input=authorize_input,
            )
            print(json.dumps(asdict(result), sort_keys=True))
            # A visible change alone is never certified application success.
            return 0 if result.status in {
                "submitted_no_visible_change",
                "submitted_visual_change_unattributed",
            } else 3
        approval = authorize_exact_action(
            state_path, capability="screen.act_exact",
            parameters=action.approval_parameters(),
            credential_id=args.credential_id, expires_seconds=60,
        )
        print("FIDO2 approved. Refocus the exact original window within five seconds.")
        time.sleep(5)
        result = DesktopInputService(
            state_path, backend=backend,
        ).execute(action, approval_id=approval.approval_id)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError, TypeError, PermissionError) as exc:
        print(f"Desktop request refused: {type(exc).__name__}: {exc}",
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
