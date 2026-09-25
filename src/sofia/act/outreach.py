"""Source-linked outreach eligibility. No network, scheduler, or sending."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import re

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")


class Decision(str, Enum):
    ELIGIBLE_FOR_AUTHORIZATION = "eligible_for_authorization"
    DISABLED = "disabled"
    STOPPED = "stopped"
    MUTED = "muted"
    BUSY = "busy"
    WRONG_RECIPIENT = "wrong_recipient"
    NO_EVIDENCE = "no_evidence"
    STALE = "stale"
    CLOCK_UNCERTAIN = "clock_uncertain"
    QUIET_HOURS = "quiet_hours"
    TOO_SOON = "too_soon"
    DAILY_LIMIT = "daily_limit"
    ALREADY_DELIVERED = "already_delivered"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    recipient_id: str
    evidence_ids: tuple[str, ...]
    created_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _id(self.candidate_id, "candidate_id")
        _id(self.recipient_id, "recipient_id")
        if (
            not isinstance(self.evidence_ids, tuple)
            or not self.evidence_ids
            or len(self.evidence_ids) > 16
        ):
            raise ValueError("nonempty bounded evidence_ids tuple required")
        for item in self.evidence_ids:
            _id(item, "evidence_id")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("duplicate evidence IDs")
        if _utc(self.expires_at) <= _utc(self.created_at):
            raise ValueError("candidate must expire after creation")


@dataclass(frozen=True)
class Policy:
    recipient_id: str
    enabled: bool = False
    mute: bool = False
    stop: bool = False
    quiet_start_utc: int = 22
    quiet_end_utc: int = 8
    min_interval: timedelta = timedelta(hours=6)
    max_daily: int = 1

    def __post_init__(self) -> None:
        _id(self.recipient_id, "recipient_id")
        if not all(isinstance(value, bool) for value in (self.enabled, self.mute, self.stop)):
            raise TypeError("enabled/mute/stop must be booleans")
        if any(
            type(value) is not int or not 0 <= value <= 23
            for value in (self.quiet_start_utc, self.quiet_end_utc)
        ):
            raise ValueError("quiet hour must be an integer in 0..23")
        if not isinstance(self.min_interval, timedelta) or self.min_interval < timedelta(0):
            raise ValueError("min_interval must be nonnegative")
        if type(self.max_daily) is not int or self.max_daily < 1:
            raise ValueError("max_daily must be positive")


@dataclass(frozen=True)
class History:
    """Trusted acknowledged deliveries only, never queued or attempted sends."""

    delivered_candidate_ids: frozenset[str] = frozenset()
    last_delivered_at: datetime | None = None
    delivered_today: int = 0
    delivered_day_utc: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.delivered_candidate_ids, frozenset):
            raise ValueError("delivered_candidate_ids must be a frozenset")
        for item in self.delivered_candidate_ids:
            _id(item, "delivered_candidate_id")
        if self.last_delivered_at is not None:
            _utc(self.last_delivered_at)
        if type(self.delivered_today) is not int or self.delivered_today < 0:
            raise ValueError("delivered_today must be nonnegative")
        if self.delivered_day_utc is not None:
            try:
                day = datetime.strptime(self.delivered_day_utc, "%Y-%m-%d").date()
            except (ValueError, TypeError) as exc:
                raise ValueError("delivered_day_utc must be ISO date") from exc
            if day.isoformat() != self.delivered_day_utc:
                raise ValueError("delivered_day_utc must be canonical ISO date")
        if self.delivered_today and self.delivered_day_utc is None:
            raise ValueError("nonzero daily count requires day")


def evaluate(
    candidate: Candidate,
    policy: Policy,
    history: History,
    now: datetime,
    *,
    busy: bool = False,
) -> Decision:
    """Return proposal eligibility, never execution or delivery permission."""

    if not isinstance(candidate, Candidate) or not isinstance(policy, Policy) or not isinstance(history, History):
        raise TypeError("typed candidate, policy and history are required")
    if not isinstance(busy, bool):
        raise TypeError("busy must be boolean")

    moment = _utc(now)
    if policy.stop:
        return Decision.STOPPED
    if not policy.enabled:
        return Decision.DISABLED
    if policy.mute:
        return Decision.MUTED
    if busy:
        return Decision.BUSY
    if candidate.recipient_id != policy.recipient_id:
        return Decision.WRONG_RECIPIENT
    if not candidate.evidence_ids:
        return Decision.NO_EVIDENCE
    if candidate.candidate_id in history.delivered_candidate_ids:
        return Decision.ALREADY_DELIVERED
    if moment < _utc(candidate.created_at):
        return Decision.CLOCK_UNCERTAIN
    if moment >= _utc(candidate.expires_at):
        return Decision.STALE

    hour = moment.hour
    if policy.quiet_start_utc == policy.quiet_end_utc:
        quiet = True
    elif policy.quiet_start_utc < policy.quiet_end_utc:
        quiet = policy.quiet_start_utc <= hour < policy.quiet_end_utc
    else:
        quiet = hour >= policy.quiet_start_utc or hour < policy.quiet_end_utc
    if quiet:
        return Decision.QUIET_HOURS

    if history.last_delivered_at is not None:
        elapsed = moment - _utc(history.last_delivered_at)
        if elapsed < timedelta(0):
            return Decision.CLOCK_UNCERTAIN
        if elapsed < policy.min_interval:
            return Decision.TOO_SOON

    if (
        history.delivered_day_utc == moment.date().isoformat()
        and history.delivered_today >= policy.max_daily
    ):
        return Decision.DAILY_LIMIT

    return Decision.ELIGIBLE_FOR_AUTHORIZATION
