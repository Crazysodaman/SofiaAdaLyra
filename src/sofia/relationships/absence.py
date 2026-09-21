"""Source-backed absence appraisal; never sends messages or claims feelings."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True, slots=True)
class LastContact:
    """Verified caller-supplied observation of one authenticated person."""
    actor_id: str
    observed_at: datetime
    source_event_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.actor_id, str) or not self.actor_id.strip():
            raise ValueError("actor_id required")
        if not isinstance(self.source_event_id, str) or not self.source_event_id.strip():
            raise ValueError("source_event_id required")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AbsenceAppraisal:
    known: bool
    elapsed: timedelta | None
    last_event_id: str | None
    optional_reunion_cue: bool
    outreach_permitted: bool


def appraise_absence(
    *,
    authenticated_actor_id: str,
    now: datetime,
    contact: LastContact | None,
    reunion_after: timedelta = timedelta(days=1),
    outreach_opt_in: bool = False,
    busy_or_quiet: bool = True,
) -> AbsenceAppraisal:
    """Report only a measured gap for the same actor, never infer loneliness.

    A true outreach_permitted is only a *candidate*; ACT/SAFE still require
    a separate approval, frequency cap, delivery authorization and recipient.
    """
    if not isinstance(authenticated_actor_id, str) or not authenticated_actor_id.strip():
        raise ValueError("authenticated_actor_id required")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if not isinstance(reunion_after, timedelta) or reunion_after <= timedelta(0):
        raise ValueError("reunion_after must be positive")
    if type(outreach_opt_in) is not bool or type(busy_or_quiet) is not bool:
        raise TypeError("flags must be booleans")
    if contact is None:
        return AbsenceAppraisal(False, None, None, False, False)
    if not isinstance(contact, LastContact) or contact.actor_id != authenticated_actor_id:
        return AbsenceAppraisal(False, None, None, False, False)
    gap = now.astimezone(timezone.utc) - contact.observed_at.astimezone(timezone.utc)
    if gap < timedelta(0):
        return AbsenceAppraisal(False, None, None, False, False)
    meaningful = gap >= reunion_after
    return AbsenceAppraisal(True, gap, contact.source_event_id, meaningful, meaningful and outreach_opt_in and not busy_or_quiet)
