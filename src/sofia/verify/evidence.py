"""Explicit, fail-closed release evidence, without pretending fixtures are live tests.

This is a pure data contract. Callers must independently verify test output,
source revision, machine identity and the origin of any claimed live evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re

_SHA = re.compile(r"[0-9a-f]{40}\Z")


class Result(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"
    NOT_APPLICABLE = "not_applicable"


class Tier(str, Enum):
    OFFLINE = "offline"
    INTEGRATION = "integration"
    LIVE = "live"


@dataclass(frozen=True)
class Evidence:
    """One claimed check, explicitly scoped to a package and exact commit."""

    evidence_id: str
    package: str
    check: str
    source_sha: str
    tier: Tier
    result: Result
    observed_at: datetime
    environment: str
    actual_system: bool = False
    source_reference: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        for field in ("evidence_id", "package", "check", "environment"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be nonempty")
        if not isinstance(self.source_sha, str) or _SHA.fullmatch(self.source_sha) is None:
            raise ValueError("source_sha must be a 40-character lowercase commit SHA")
        if not isinstance(self.tier, Tier) or not isinstance(self.result, Result):
            raise TypeError("tier and result must use their declared enum types")
        if not isinstance(self.observed_at, datetime) or self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if not isinstance(self.actual_system, bool):
            raise TypeError("actual_system must be a boolean")
        if self.actual_system and self.tier is not Tier.LIVE:
            raise ValueError("actual_system may only be claimed for live checks")
        if self.result is Result.PASSED and not self.source_reference.strip():
            raise ValueError("a claimed pass needs an independently reviewable source reference")
        if self.result in (Result.NOT_RUN, Result.NOT_APPLICABLE) and self.actual_system:
            raise ValueError("unperformed checks cannot claim an actual system")


@dataclass(frozen=True)
class Requirement:
    check: str
    minimum_tier: Tier
    actual_system: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.check, str) or not self.check.strip():
            raise ValueError("requirement check must be nonempty")
        if not isinstance(self.minimum_tier, Tier):
            raise TypeError("minimum_tier must be a Tier")
        if self.actual_system and self.minimum_tier is not Tier.LIVE:
            raise ValueError("actual-system requirements must be live")


@dataclass(frozen=True)
class GateReport:
    ready: bool
    missing: tuple[str, ...]
    blocked: tuple[str, ...]


_RANK = {Tier.OFFLINE: 0, Tier.INTEGRATION: 1, Tier.LIVE: 2}


def assess_gate(package: str, source_sha: str, requirements: tuple[Requirement, ...],
                evidence: tuple[Evidence, ...]) -> GateReport:
    """Fail closed: only same-package/same-revision passing checks count.

    A newer failure for a check blocks release until a later passing check
    of the required tier. Records are ordered by their supplied timestamps;
    ties are treated as blocked when any failure is present.
    """
    if not package.strip() or _SHA.fullmatch(source_sha) is None:
        raise ValueError("package and exact source_sha are required")
    if not requirements:
        return GateReport(False, ("acceptance requirements not defined",), ())
    missing: list[str] = []
    blocked: list[str] = []
    applicable = tuple(record for record in evidence if record.package == package and record.source_sha == source_sha)
    for requirement in requirements:
        candidates = tuple(record for record in applicable if record.check == requirement.check
                           and _RANK[record.tier] >= _RANK[requirement.minimum_tier]
                           and (not requirement.actual_system or record.actual_system))
        if not candidates:
            missing.append(requirement.check)
            continue
        newest = max(record.observed_at.astimezone(timezone.utc) for record in candidates)
        latest = tuple(record for record in candidates if record.observed_at.astimezone(timezone.utc) == newest)
        if any(record.result is Result.FAILED for record in latest) or not any(record.result is Result.PASSED for record in latest):
            blocked.append(requirement.check)
    return GateReport(not missing and not blocked, tuple(missing), tuple(blocked))
