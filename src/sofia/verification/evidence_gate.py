"""Evidence-tier release gate for PKG-VERIFY; never executes a test or deploys."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum


class Tier(str, Enum):
    OFFLINE = "offline"
    INTEGRATION = "integration"
    LIVE = "live"


class Outcome(str, Enum):
    PASS = "passed"
    FAIL = "failed"
    NOT_RUN = "not_run"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    required_tier: Tier
    outcome: Outcome
    observed_tier: Tier | None = None
    revision: str | None = None
    evidence: str | None = None
    justification: str | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("check name required")
        if not isinstance(self.required_tier, Tier) or not isinstance(self.outcome, Outcome):
            raise TypeError("invalid tier or outcome")
        if self.observed_tier is not None and not isinstance(self.observed_tier, Tier):
            raise TypeError("invalid observed tier")


@dataclass(frozen=True, slots=True)
class GateReport:
    ready: bool
    blocking: tuple[str, ...]
    failed: tuple[str, ...]
    incomplete: tuple[str, ...]


_ORDER = {Tier.OFFLINE: 0, Tier.INTEGRATION: 1, Tier.LIVE: 2}


def evaluate_gate(checks: tuple[Check, ...], *, target_revision: str) -> GateReport:
    """An offline fixture can never satisfy a live gate or an unpinned SHA.

    A caller supplies evidence strings; this checker cannot authenticate CI,
    platform logs or user reports. Independent evidence verification is needed.
    """
    if not isinstance(target_revision, str) or not target_revision.strip():
        raise ValueError("target_revision must be provided")
    if not checks:
        return GateReport(False, ("no_checks",), (), ("no_checks",))
    seen: set[str] = set()
    blocking: list[str] = []
    failed: list[str] = []
    incomplete: list[str] = []
    for check in checks:
        if not isinstance(check, Check):
            raise TypeError("checks must be Check instances")
        if check.name in seen:
            raise ValueError("duplicate check name")
        seen.add(check.name)
        if check.outcome is Outcome.FAIL:
            failed.append(check.name)
            blocking.append(check.name)
        elif check.outcome is Outcome.NOT_APPLICABLE:
            if not check.justification or not check.justification.strip():
                incomplete.append(check.name)
                blocking.append(check.name)
        elif (
            check.outcome is not Outcome.PASS
            or check.observed_tier is None
            or _ORDER[check.observed_tier] < _ORDER[check.required_tier]
            or check.revision != target_revision
            or not check.evidence or not check.evidence.strip()
        ):
            incomplete.append(check.name)
            blocking.append(check.name)
    return GateReport(not blocking, tuple(blocking), tuple(failed), tuple(incomplete))
