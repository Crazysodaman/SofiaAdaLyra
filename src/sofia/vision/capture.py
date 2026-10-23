"""One owner-approved real screen frame, scoped to the exact local OS target.

The frame exists in memory for its consuming caller, never in SQLite, file
storage or audit text. Signed execution approval does not substitute for the
separate OS/user interactive target-selection ceremony.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import socket
import sys

from sofia.vision.consent import ScreenObservationPermit
from sofia.vision.journeys import (
    ScreenJourneyRequest, ScreenFrameEvidence,
    ScreenJourneyReceiptStore, accept_actual_picked_frame,
)

_MAX_PNG_BYTES = 16 * 1024 * 1024


def local_target_id(host: str, hwnd: int, pid: int) -> str:
    if (not isinstance(host, str) or not host or len(host) > 120
            or type(hwnd) is not int or hwnd <= 0
            or type(pid) is not int or pid <= 0):
        raise ValueError("exact local host/HWND/PID required")
    return f"desktop:{host.casefold()}:{hwnd}:{pid}"


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    """Keep untrusted pixels in memory only; no semantic or action claim."""
    pixels_png: bytes
    evidence: ScreenFrameEvidence

    def __post_init__(self) -> None:
        if (not isinstance(self.pixels_png, bytes)
            or len(self.pixels_png) > _MAX_PNG_BYTES
            or not self.pixels_png.startswith(b"\x89PNG\r\n\x1a\n")
            or sha256(self.pixels_png).hexdigest()
               != self.evidence.receipt.digest_sha256):
            raise ValueError("real exact frame integrity required")


def default_capture_backend():
    if sys.platform == "win32":
        from sofia.vision.windows_capture import WindowsWindowCapture
        return WindowsWindowCapture()
    if sys.platform == "linux":
        from sofia.vision.linux_desktop import LinuxDesktop
        return LinuxDesktop()
    raise RuntimeError("unsupported desktop capture platform")


class ScreenCaptureService:
    def __init__(self, state_path: Path | str, *, capture_backend=None,
                 foreground_backend=None) -> None:
        self.state_path = Path(state_path)
        self.capture_backend = (
            capture_backend if capture_backend is not None
            else default_capture_backend()
        )
        if foreground_backend is not None:
            self.foreground_backend = foreground_backend
        elif sys.platform == "win32":
            from sofia.vision.desktop_control import WindowsDesktopInput
            self.foreground_backend = WindowsDesktopInput()
        else:
            self.foreground_backend = self.capture_backend

    def capture_once(self, request: ScreenJourneyRequest, *,
                     approval_id: str) -> CapturedFrame:
        if not isinstance(request, ScreenJourneyRequest):
            raise TypeError("original owner screen request required")
        if not approval_id or not isinstance(approval_id, str):
            raise PermissionError("single use physical-owner approval required")
        permit: ScreenObservationPermit = request.permit
        from sofia.vision.journeys import ScreenJourney
        if request.journey not in (
            ScreenJourney.LOOK_AT_WINDOW, ScreenJourney.SHOW_CHANGES,
            ScreenJourney.NAVIGATE_GUIDANCE,
        ) or permit.observation_kind != "snapshot":
            raise PermissionError("this executor supports a single bounded snapshot only")
        host = socket.gethostname()
        actual_hwnd, actual_pid = self.foreground_backend.foreground()
        selected = local_target_id(host, actual_hwnd, actual_pid)
        if permit.device_id.casefold() != host.casefold() or permit.target_id != selected:
            raise PermissionError("capture permit not bound to current OS host and target")
        if permit.principal_id != "person:sparks" or permit.audience_id != "local:text":
            raise PermissionError("capture can be released only to original local owner")
        from sofia.platform.safe.operator_stop import OperatorStopStore
        from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
        from sofia.vision.desktop_control import require_workstation_clear
        stop = OperatorStopStore(self.state_path)

        def recheck():
            now = datetime.now(timezone.utc)
            if stop.current().active:
                raise PermissionError("owner operator STOP active")
            if not permit.allows(
                principal_id=permit.principal_id, audience_id=permit.audience_id,
                device_id=permit.device_id, target_id=permit.target_id, at=now,
            ):
                raise PermissionError("screen observation permit expired")
            if sys.platform == "win32":
                require_workstation_clear(self.state_path, host, now)
            elif sys.platform == "linux":
                from sofia.vision.linux_desktop import require_linux_game_clear
                require_linux_game_clear()
            else:
                raise PermissionError("unavailable OS capture")
            if self.foreground_backend.foreground() != (actual_hwnd, actual_pid):
                raise PermissionError("approved foreground capture target changed")

        # Auth is exact and one-use. No model can submit an arbitrary window.
        recheck()
        ExecutionApprovalVerifier(self.state_path).consume(
            approval_id=approval_id, capability="screen.capture_once",
            parameters={
                "host_id": host, "window_handle": actual_hwnd,
                "process_id": actual_pid, "target_id": selected,
                "permit_id": permit.permit_id, "journey": request.journey.value,
                "purpose": permit.purpose,
            },
            now=datetime.now(timezone.utc),
        )
        recheck()
        pixels = self.capture_backend.select_and_capture(
            exact_window=actual_hwnd, exact_pid=actual_pid, recheck=recheck,
        )
        now = datetime.now(timezone.utc)
        recheck()
        # OS picker fact is supplied only by this trusted backend, never by
        # user/LLM call arguments or a prior metadata-only receipt.
        evidence = accept_actual_picked_frame(
            request, pixel_bytes=pixels, at=now,
            actual_os_picker_selected_target_id=selected,
            confirmed_interactive_os_picker=True, protected_surface=False,
        )
        frame = CapturedFrame(pixels, evidence)
        ScreenJourneyReceiptStore(self.state_path).record(frame.evidence)
        return frame
