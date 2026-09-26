"""One-user observed-contact continuity; no subjective feelings or outreach."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum


class ReunionKind(str, Enum):
    NO_EVIDENCE = "no_evidence"
    NORMAL = "normal"
    ELAPSED_GAP = "elapsed_gap"
    CLOCK_UNCERTAIN = "clock_uncertain"


@dataclass(frozen=True)
class Contact:
    """Trusted caller-provided observed conversation event (not an LLM guess)."""
    principal_id: str
    message_id: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ValueError("principal_id required")
        if not isinstance(self.message_id, str) or not self.message_id.strip():
            raise ValueError("message_id required")
        _utc(self.observed_at)


@dataclass(frozen=True)
class Reunion:
    kind: ReunionKind
    elapsed: timedelta | None
    last_message_id: str | None


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware")
    return value.astimezone(timezone.utc)


class SingleUserPresence:
    """In-memory contact evidence. Auth and persistence belong to the host/MEM."""

    def __init__(self, principal_id: str) -> None:
        if not isinstance(principal_id, str) or not principal_id.strip():
            raise ValueError("principal_id required")
        self._principal_id = principal_id
        self._contact: Contact | None = None
        self._seen_ids: set[str] = set()

    @property
    def last_contact(self) -> Contact | None:
        return self._contact

    def record(self, contact: Contact) -> bool:
        """Accept only current principal and never rewind last-seen on replay."""
        if not isinstance(contact, Contact):
            raise TypeError("contact must be Contact")
        if contact.principal_id != self._principal_id:
            raise PermissionError("contact principal does not match")
        if contact.message_id in self._seen_ids:
            return False
        self._seen_ids.add(contact.message_id)
        if self._contact is None or _utc(contact.observed_at) > _utc(self._contact.observed_at):
            self._contact = contact
            return True
        return False

    def reunion(self, now: datetime, significant_gap: timedelta) -> Reunion:
        current = _utc(now)
        if not isinstance(significant_gap, timedelta) or significant_gap <= timedelta(0):
            raise ValueError("significant_gap must be a positive timedelta")
        if self._contact is None:
            return Reunion(ReunionKind.NO_EVIDENCE, None, None)
        elapsed = current - _utc(self._contact.observed_at)
        if elapsed < timedelta(0):
            return Reunion(ReunionKind.CLOCK_UNCERTAIN, None, self._contact.message_id)
        if elapsed >= significant_gap:
            return Reunion(ReunionKind.ELAPSED_GAP, elapsed, self._contact.message_id)
        return Reunion(ReunionKind.NORMAL, elapsed, self._contact.message_id)
