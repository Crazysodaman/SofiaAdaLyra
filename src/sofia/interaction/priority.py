"""Stable cross-channel interaction event ordering metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum


class InteractionPriority(IntEnum):
    STOP_OR_SAFETY = 0
    USER_FOREGROUND = 10
    DELIVERY_ACK = 20
    SYSTEM_NOTICE = 30
    BACKGROUND = 40


@dataclass(frozen=True, slots=True)
class InteractionEnvelope:
    event_id: str
    session_id: str
    occurred_at: datetime
    priority: InteractionPriority
    source: str
    principal_id: str | None = None
    causation_id: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("event_id", self.event_id),
            ("session_id", self.session_id),
            ("source", self.source),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} required")
        if (
            not isinstance(self.occurred_at, datetime)
            or self.occurred_at.tzinfo is None
            or self.occurred_at.utcoffset() is None
        ):
            raise ValueError("occurred_at must be timezone-aware")
        if not isinstance(self.priority, InteractionPriority):
            raise TypeError("priority must be InteractionPriority")
        for label, value in (
            ("principal_id", self.principal_id),
            ("causation_id", self.causation_id),
        ):
            if value is not None and (
                not isinstance(value, str) or not value.strip()
            ):
                raise ValueError(f"{label} must be nonempty when set")

    @property
    def ordering_key(self) -> tuple[int, datetime, str]:
        return (
            int(self.priority),
            self.occurred_at.astimezone(timezone.utc),
            self.event_id,
        )
