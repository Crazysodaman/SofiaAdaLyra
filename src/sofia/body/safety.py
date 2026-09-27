"""Simulation-first, fail-closed physical motion authorization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class EmergencyStopState:
    engaged: bool
    observed_at: datetime
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.engaged, bool):
            raise TypeError("engaged must be boolean")
        _utc(self.observed_at)
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("E-stop source required")


@dataclass(frozen=True, slots=True)
class MotionAuthority:
    grant_id: str
    expires_at: datetime
    allowed_joint_ids: tuple[str, ...]
    maximum_duration_ms: int

    def __post_init__(self) -> None:
        if not isinstance(self.grant_id, str) or not self.grant_id.strip():
            raise ValueError("grant_id required")
        _utc(self.expires_at)
        if not isinstance(self.allowed_joint_ids, tuple) or not self.allowed_joint_ids:
            raise ValueError("allowed_joint_ids required")
        if any(not isinstance(item, str) or not item.strip() for item in self.allowed_joint_ids):
            raise ValueError("joint IDs must be nonempty")
        if type(self.maximum_duration_ms) is not int or not 1 <= self.maximum_duration_ms <= 60_000:
            raise ValueError("maximum_duration_ms must be in 1..60000")


@dataclass(frozen=True, slots=True)
class MotionCommand:
    command_id: str
    joint_id: str
    target: float
    duration_ms: int

    def __post_init__(self) -> None:
        if not self.command_id.strip() or not self.joint_id.strip():
            raise ValueError("command_id and joint_id required")
        if isinstance(self.target, bool) or not isinstance(self.target, (int, float)):
            raise TypeError("target must be numeric")
        if type(self.duration_ms) is not int or self.duration_ms < 1:
            raise ValueError("duration_ms must be positive")


class PhysicalMotionGate:
    """Authorize a command; this class does not talk to servos."""

    def require(
        self,
        command: MotionCommand,
        *,
        authority: MotionAuthority,
        emergency_stop: EmergencyStopState,
        now: datetime,
    ) -> None:
        if not isinstance(command, MotionCommand):
            raise TypeError("MotionCommand required")
        if not isinstance(authority, MotionAuthority):
            raise TypeError("MotionAuthority required")
        if not isinstance(emergency_stop, EmergencyStopState):
            raise TypeError("EmergencyStopState required")
        moment = _utc(now)
        if emergency_stop.engaged:
            raise PermissionError("physical emergency stop is engaged")
        if moment >= _utc(authority.expires_at):
            raise PermissionError("motion authority expired")
        if command.joint_id not in authority.allowed_joint_ids:
            raise PermissionError("joint is outside authorized motion scope")
        if command.duration_ms > authority.maximum_duration_ms:
            raise PermissionError("motion duration exceeds authorized bound")
