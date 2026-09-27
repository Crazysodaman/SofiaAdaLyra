"""Configuration source precedence and provenance."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import re

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,191}$")


class ConfigurationTier(IntEnum):
    SHARED = 10
    HOST_OVERRIDE = 20
    PROCESS_BOOTSTRAP = 30
    PROTECTED_POLICY = 100


@dataclass(frozen=True, slots=True)
class ConfigurationEvidence:
    key: str
    value: object
    tier: ConfigurationTier
    source: str
    revision: str
    approved: bool = True
    locked: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("configuration key required")
        if not isinstance(self.tier, ConfigurationTier):
            raise TypeError("tier must be ConfigurationTier")
        for label, value in (
            ("source", self.source),
            ("revision", self.revision),
        ):
            if not isinstance(value, str) or _ID.fullmatch(value) is None:
                raise ValueError(f"{label} must be a bounded identifier")
        if not isinstance(self.approved, bool):
            raise TypeError("approved must be boolean")
        if not isinstance(self.locked, bool):
            raise TypeError("locked must be boolean")
        if self.tier is ConfigurationTier.PROTECTED_POLICY and not self.locked:
            raise ValueError("protected policy configuration must be locked")


class ConfigurationAuthorityError(RuntimeError):
    pass


def resolve_configuration(
    key: str,
    candidates: tuple[ConfigurationEvidence, ...],
) -> ConfigurationEvidence:
    """Resolve one key without allowing lower-trust override of a locked policy."""

    if not isinstance(key, str) or not key.strip():
        raise ValueError("configuration key required")
    if not isinstance(candidates, tuple):
        raise TypeError("candidates must be a tuple")

    matching = []
    for candidate in candidates:
        if not isinstance(candidate, ConfigurationEvidence):
            raise TypeError(
                "candidates must contain ConfigurationEvidence"
            )
        if candidate.key == key and candidate.approved:
            matching.append(candidate)
    if not matching:
        raise ConfigurationAuthorityError(
            f"no approved configuration evidence for {key}"
        )

    protected = [
        item
        for item in matching
        if item.tier is ConfigurationTier.PROTECTED_POLICY
    ]
    if protected:
        values = {repr(item.value) for item in protected}
        if len(values) != 1:
            raise ConfigurationAuthorityError(
                "conflicting protected policy configuration"
            )
        return sorted(
            protected,
            key=lambda item: (item.revision, item.source),
        )[-1]

    highest = max(item.tier for item in matching)
    selected = [item for item in matching if item.tier is highest]
    values = {repr(item.value) for item in selected}
    if len(values) != 1:
        raise ConfigurationAuthorityError(
            "conflicting configuration at same authority tier"
        )
    return sorted(
        selected,
        key=lambda item: (item.revision, item.source),
    )[-1]
