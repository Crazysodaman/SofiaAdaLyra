"""Evidence-only relationship context, without fabricated internal states."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True, slots=True)
class RelationshipContext:
    principal_id: str
    first_contact_at: datetime
    last_contact_at: datetime
    contact_count: int
    observed_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.principal_id, str) or not self.principal_id.strip():
            raise ValueError("principal_id required")
        for value in (
            self.first_contact_at,
            self.last_contact_at,
            self.observed_at,
        ):
            if (
                not isinstance(value, datetime)
                or value.tzinfo is None
                or value.utcoffset() is None
            ):
                raise ValueError("relationship timestamps must be aware")
        if type(self.contact_count) is not int or self.contact_count < 1:
            raise ValueError("contact_count must be positive")
        if self.last_contact_at < self.first_contact_at:
            raise ValueError("last contact cannot precede first contact")
        if self.observed_at < self.last_contact_at:
            raise ValueError("observation cannot precede last contact")

    @property
    def absence(self) -> timedelta:
        return self.observed_at.astimezone(timezone.utc) - self.last_contact_at.astimezone(timezone.utc)
