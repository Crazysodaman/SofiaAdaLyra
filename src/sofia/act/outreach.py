"""Source-linked outreach eligibility. No network, scheduler, or sending."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")


class OutreachCategory(str, Enum):
    SOCIAL = "social"
    OPERATIONAL = "operational"


class Importance(str, Enum):
    TRIVIAL = "trivial"
    ROUTINE = "routine"
    IMPORTANT = "important"
    CRITICAL = "critical"


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
    category: OutreachCategory = OutreachCategory.SOCIAL
    importance: Importance = Importance.ROUTINE
    salience: float = 0.5

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
        if not isinstance(self.category, OutreachCategory):
            raise TypeError("category must be OutreachCategory")
        if not isinstance(self.importance, Importance):
            raise TypeError("importance must be Importance")
        if not isinstance(self.salience, (int, float)) or isinstance(
            self.salience,
            bool,
        ):
            raise TypeError("salience must be numeric")
        if not 0.0 <= self.salience <= 1.0:
            raise ValueError("salience must be in [0,1]")


@dataclass(frozen=True)
class Policy:
    recipient_id: str
    enabled: bool = False
    mute: bool = False
    stop: bool = False
    quiet_start_local: int = 22
    quiet_end_local: int = 8
    timezone_name: str = "UTC"
    quiet_start_utc: int | None = None
    quiet_end_utc: int | None = None
    min_interval: timedelta = timedelta(hours=2)
    max_daily: int = 4
    social_min_interval: timedelta = timedelta(hours=6)
    operational_min_interval: timedelta = timedelta(minutes=30)
    social_max_daily: int = 1
    operational_max_daily: int = 8
    allow_critical_operational_during_quiet: bool = True

    def __post_init__(self) -> None:
        _id(self.recipient_id, "recipient_id")
        if self.quiet_start_utc is not None:
            if type(self.quiet_start_utc) is not int or not 0 <= self.quiet_start_utc <= 23:
                raise ValueError("quiet_start_utc must be an integer in 0..23")
            object.__setattr__(self, "quiet_start_local", self.quiet_start_utc)
            object.__setattr__(self, "timezone_name", "UTC")
        if self.quiet_end_utc is not None:
            if type(self.quiet_end_utc) is not int or not 0 <= self.quiet_end_utc <= 23:
                raise ValueError("quiet_end_utc must be an integer in 0..23")
            object.__setattr__(self, "quiet_end_local", self.quiet_end_utc)
            object.__setattr__(self, "timezone_name", "UTC")
        if not all(isinstance(value, bool) for value in (self.enabled, self.mute, self.stop)):
            raise TypeError("enabled/mute/stop must be booleans")
        if any(
            type(value) is not int or not 0 <= value <= 23
            for value in (self.quiet_start_local, self.quiet_end_local)
        ):
            raise ValueError("quiet hour must be an integer in 0..23")
        if not isinstance(self.timezone_name, str) or not self.timezone_name.strip():
            raise ValueError("timezone_name must be nonempty")
        try:
            ZoneInfo(self.timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone_name must identify an installed timezone") from exc
        for name in (
            "min_interval",
            "social_min_interval",
            "operational_min_interval",
        ):
            value = getattr(self, name)
            if not isinstance(value, timedelta) or value < timedelta(0):
                raise ValueError(f"{name} must be nonnegative")
        for name in ("max_daily", "social_max_daily", "operational_max_daily"):
            value = getattr(self, name)
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be positive")
        if type(self.allow_critical_operational_during_quiet) is not bool:
            raise TypeError(
                "allow_critical_operational_during_quiet must be boolean"
            )

    def local_time(self, now: datetime) -> datetime:
        return _utc(now).astimezone(ZoneInfo(self.timezone_name))

    def is_quiet(self, now: datetime) -> bool:
        hour = self.local_time(now).hour
        start = self.quiet_start_local
        end = self.quiet_end_local
        if start == end:
            return True
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end


@dataclass(frozen=True)
class History:
    """Trusted acknowledged deliveries only, never queued or attempted sends."""

    delivered_candidate_ids: frozenset[str] = frozenset()
    last_delivered_at: datetime | None = None
    delivered_today: int = 0
    delivered_day_utc: str | None = None
    social_last_delivered_at: datetime | None = None
    social_delivered_today: int = 0
    operational_last_delivered_at: datetime | None = None
    operational_delivered_today: int = 0

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
        for name in (
            "social_last_delivered_at",
            "operational_last_delivered_at",
        ):
            value = getattr(self, name)
            if value is not None:
                _utc(value)
        for name in (
            "social_delivered_today",
            "operational_delivered_today",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be nonnegative")


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

    critical_operational = (
        candidate.category is OutreachCategory.OPERATIONAL
        and candidate.importance is Importance.CRITICAL
        and policy.allow_critical_operational_during_quiet
    )
    if policy.is_quiet(moment) and not critical_operational:
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

    if candidate.category is OutreachCategory.SOCIAL:
        legacy_social_history = (
            history.social_last_delivered_at is None
            and history.social_delivered_today == 0
        )
        category_last = (
            history.last_delivered_at
            if legacy_social_history
            else history.social_last_delivered_at
        )
        category_count = (
            history.delivered_today
            if legacy_social_history
            else history.social_delivered_today
        )
        category_interval = (
            policy.min_interval
            if legacy_social_history
            else policy.social_min_interval
        )
        category_limit = (
            policy.max_daily
            if legacy_social_history
            else policy.social_max_daily
        )
        if candidate.importance is Importance.TRIVIAL and candidate.salience < 0.55:
            return Decision.TOO_SOON
    else:
        category_last = history.operational_last_delivered_at
        category_count = history.operational_delivered_today
        category_interval = policy.operational_min_interval
        category_limit = policy.operational_max_daily

    if category_last is not None:
        elapsed = moment - _utc(category_last)
        if elapsed < timedelta(0):
            return Decision.CLOCK_UNCERTAIN
        if elapsed < category_interval:
            return Decision.TOO_SOON

    if (
        history.delivered_day_utc == moment.date().isoformat()
        and category_count >= category_limit
    ):
        return Decision.DAILY_LIMIT

    return Decision.ELIGIBLE_FOR_AUTHORIZATION
