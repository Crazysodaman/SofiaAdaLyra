"""Exact-source, short-lived screen observation scope.

A valid token is necessary, never sufficient: the interactive OS screen
picker, secure-desktop rules, SAFE gate and redaction checks still apply.
No background capture or mouse/keyboard execution lives here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class ScreenObservationPermit:
    permit_id: str
    principal_id: str
    audience_id: str
    device_id: str
    target_id: str
    purpose: str
    issued_at: datetime
    expires_at: datetime
    observation_kind: str

    def allows(
        self, *, principal_id: str, audience_id: str,
        device_id: str, target_id: str, at: datetime,
    ) -> bool:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("timezone-aware screen observation required")
        return (
            (principal_id, audience_id, device_id, target_id)
            == (self.principal_id, self.audience_id, self.device_id, self.target_id)
            and self.issued_at <= at <= self.expires_at
        )


def propose_screen_permit(
    *, principal_id: str, audience_id: str, device_id: str,
    target_id: str, purpose: str, kind: str, at: datetime,
    duration_seconds: int = 30,
) -> ScreenObservationPermit:
    """Scope-only proposal; host must verify explicit interactive-user assent."""
    fields = (principal_id, audience_id, device_id, target_id, purpose)
    if any(not isinstance(f, str) or not f.strip() or len(f) > 200 for f in fields):
        raise ValueError("named nonempty scope/purpose required")
    if kind not in {"snapshot", "bounded_follow"}:
        raise ValueError("automatic ambient capture forbidden")
    if type(duration_seconds) is not int or not 1 <= duration_seconds <= 300:
        raise ValueError("watch duration cannot exceed five minutes")
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("timezone-aware permit time required")
    moment = at.astimezone(timezone.utc)
    return ScreenObservationPermit(
        f"screen-permit:{uuid4().hex}", *fields, moment,
        moment + timedelta(seconds=duration_seconds), kind,
    )


@dataclass(frozen=True, slots=True)
class ScreenObservationReceipt:
    permit_id: str
    target_id: str
    captured_at: datetime
    digest_sha256: str
    actual_frame_available: bool


def receipt_from_permitted_bytes(
    permit: ScreenObservationPermit, *, frame: bytes,
    at: datetime, os_picker_consented: bool,
    protected_surface: bool,
) -> ScreenObservationReceipt:
    """Minimal metadata receipt, no pixel persistence or fact fabrication."""
    if not os_picker_consented or protected_surface:
        raise PermissionError("OS consent missing or surface protected")
    if not permit.allows(
        principal_id=permit.principal_id, audience_id=permit.audience_id,
        device_id=permit.device_id, target_id=permit.target_id, at=at,
    ):
        raise PermissionError("screen grant expired")
    if not isinstance(frame, bytes) or not frame or len(frame) > 64 * 1024 * 1024:
        raise ValueError("bounded real capture frame required")
    return ScreenObservationReceipt(
        permit.permit_id, permit.target_id, at,
        sha256(frame).hexdigest(), True,
    )
