from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class ConfigurationPrecedence(IntEnum):
    SHARED = 10
    HOST_OVERRIDE = 20
    PROCESS_OVERRIDE = 30
    PROTECTED_POLICY = 100


@dataclass(frozen=True, slots=True)
class ConfigurationValue:
    """One configuration fact with explicit source and authority metadata."""

    key: str
    value: object
    precedence: ConfigurationPrecedence
    revision: int
    source: str
    actor_id: str
    observed_at: datetime
    host_id: str | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("key", "source", "actor_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if not isinstance(self.precedence, ConfigurationPrecedence):
            raise TypeError("precedence must be ConfigurationPrecedence")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("revision must be a positive integer")
        if not isinstance(self.observed_at, datetime):
            raise TypeError("observed_at must be a datetime")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.host_id is not None and (
            not isinstance(self.host_id, str) or not self.host_id.strip()
        ):
            raise ValueError("host_id must be None or nonempty")
        if self.expires_at is not None:
            if not isinstance(self.expires_at, datetime):
                raise TypeError("expires_at must be a datetime or None")
            if self.expires_at.tzinfo is None or self.expires_at.utcoffset() is None:
                raise ValueError("expires_at must be timezone-aware")

    def active_at(self, now: datetime) -> bool:
        if not isinstance(now, datetime):
            raise TypeError("now must be a datetime")
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        return self.expires_at is None or now < self.expires_at


class ConfigurationResolver:
    """
    Resolve one key without silently blending conflicting authorities.

    Protected policy has the highest precedence and cannot be displaced by
    shared, host, or process-local values.
    """

    @staticmethod
    def resolve(
        values: tuple[ConfigurationValue, ...],
        *,
        now: datetime,
        host_id: str | None = None,
    ) -> ConfigurationValue | None:
        if not isinstance(values, tuple):
            raise TypeError("values must be a tuple")
        eligible: list[ConfigurationValue] = []
        for value in values:
            if not isinstance(value, ConfigurationValue):
                raise TypeError("values must contain ConfigurationValue values")
            if not value.active_at(now):
                continue
            if value.precedence is ConfigurationPrecedence.HOST_OVERRIDE:
                if host_id is None or value.host_id != host_id:
                    continue
            eligible.append(value)

        if not eligible:
            return None

        top = max(value.precedence for value in eligible)
        contenders = [value for value in eligible if value.precedence == top]
        highest_revision = max(value.revision for value in contenders)
        finalists = [
            value for value in contenders if value.revision == highest_revision
        ]
        if len(finalists) != 1:
            first = finalists[0]
            if any(item.value != first.value for item in finalists[1:]):
                raise RuntimeError(
                    "conflicting configuration values at equal authority/revision"
                )
            return first
        return finalists[0]
