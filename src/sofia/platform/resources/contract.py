"""HNF Resource Capability Contract V1.

The same typed keys represent observed hardware supply and signed module
demand.  Compatibility remains advisory: it neither enrolls a host nor grants
execution authority, leases, or consent.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import isfinite
import re
from typing import Mapping, TypeAlias


SCHEMA = "sofia.resource-capability.v1"
_KEY = re.compile(
    r"^[a-z][a-z0-9_]*(?:\[[A-Za-z0-9_.:@/-]+\])?"
    r"(?:\.[a-z][a-z0-9_]*(?:\[[A-Za-z0-9_.:@/-]+\])?){1,7}$"
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,255}$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)(?:\.(0|[0-9][0-9]*)){0,3}(?:[-+][A-Za-z0-9.-]+)?$")

Scalar: TypeAlias = str | int | float | bool
CapabilityValue: TypeAlias = Scalar | tuple[str, ...]


class EvidenceClass(str, Enum):
    MANUFACTURER = "manufacturer_stated"
    OBSERVED = "host_observed"
    BENCHMARK = "benchmark_measured"


class PredicateOperator(str, Enum):
    EQUALS = "equals"
    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    RANGE = "range"
    VERSION = "version"
    CONTAINS = "contains"
    IN_SET = "in_set"


class MatchState(str, Enum):
    MATCH = "match"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


def _utc(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise ValueError(f"invalid {label}")
    return value


def _value(value: CapabilityValue) -> CapabilityValue:
    if type(value) is float and not isfinite(value):
        raise ValueError("capability numbers must be finite")
    if type(value) in (str, int, float, bool):
        return value
    if type(value) is tuple and all(isinstance(item, str) and item for item in value):
        if len(set(value)) != len(value):
            raise ValueError("capability set values must be unique")
        return tuple(sorted(value))
    raise TypeError("capability value must be a scalar or tuple of strings")


def _canonical_unit(key: str) -> str | None:
    normalized = re.sub(r"\[[^]]+\]", "", key)
    if normalized.endswith("_bytes"):
        return "bytes"
    if normalized.endswith("_bps") or normalized.endswith("_bytes_per_second"):
        return "bps" if normalized.endswith("_bps") else "bytes_per_second"
    if normalized.endswith("_ms"):
        return "milliseconds"
    if normalized.endswith("_c"):
        return "celsius"
    if normalized.endswith(".percent") or normalized.endswith("_percent"):
        return "percent"
    if normalized.endswith(".cores.allocatable") or normalized.endswith(".count"):
        return "count"
    return None


@dataclass(frozen=True, slots=True)
class CapabilityFact:
    key: str
    value: CapabilityValue
    unit: str | None
    host_id: str
    resource_id: str
    evidence_class: EvidenceClass
    source_ref: str
    observed_at: datetime
    expires_at: datetime | None
    verified: bool

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or _KEY.fullmatch(self.key) is None:
            raise ValueError("invalid capability key")
        object.__setattr__(self, "value", _value(self.value))
        _identifier(self.host_id, "host_id")
        _identifier(self.resource_id, "resource_id")
        _identifier(self.source_ref, "source_ref")
        if not isinstance(self.evidence_class, EvidenceClass):
            raise TypeError("evidence_class must be EvidenceClass")
        observed = _utc(self.observed_at, "observed_at")
        object.__setattr__(self, "observed_at", observed)
        if self.expires_at is not None:
            expiry = _utc(self.expires_at, "expires_at")
            if expiry <= observed:
                raise ValueError("expires_at must follow observed_at")
            object.__setattr__(self, "expires_at", expiry)
        if type(self.verified) is not bool:
            raise TypeError("verified must be bool")
        if (
            self.verified
            and self.evidence_class is EvidenceClass.MANUFACTURER
            and not self.source_ref.startswith("manufacturer:")
        ):
            raise ValueError("verified manufacturer facts need attributable manufacturer source")
        if (
            self.verified
            and self.evidence_class is EvidenceClass.BENCHMARK
            and not self.source_ref.startswith("benchmark:")
        ):
            raise ValueError("verified benchmark facts need benchmark evidence source")
        expected_unit = _canonical_unit(self.key)
        if expected_unit is not None and self.unit != expected_unit:
            raise ValueError(f"{self.key} requires unit {expected_unit}")
        if self.unit is not None and (
            not isinstance(self.unit, str) or not self.unit.strip()
        ):
            raise ValueError("unit must be nonempty or None")

    def fresh(self, now: datetime, maximum_age: timedelta | None = None) -> bool:
        moment = _utc(now, "now")
        if self.observed_at > moment + timedelta(seconds=5):
            return False
        if self.expires_at is not None and self.expires_at <= moment:
            return False
        return maximum_age is None or moment - self.observed_at <= maximum_age


@dataclass(frozen=True, slots=True)
class CapabilityPredicate:
    key: str
    operator: PredicateOperator
    expected: CapabilityValue
    upper: int | float | None = None
    unit: str | None = None
    required_evidence: tuple[EvidenceClass, ...] = (
        EvidenceClass.OBSERVED, EvidenceClass.BENCHMARK,
    )
    maximum_age_seconds: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or _KEY.fullmatch(self.key) is None:
            raise ValueError("invalid requirement key")
        if not isinstance(self.operator, PredicateOperator):
            raise TypeError("operator must be PredicateOperator")
        object.__setattr__(self, "expected", _value(self.expected))
        if type(self.required_evidence) is not tuple or not self.required_evidence or any(
            not isinstance(item, EvidenceClass) for item in self.required_evidence
        ):
            raise ValueError("required_evidence must be nonempty EvidenceClass values")
        if self.maximum_age_seconds is not None and (
            type(self.maximum_age_seconds) is not int
            or not 1 <= self.maximum_age_seconds <= 31_536_000
        ):
            raise ValueError("maximum_age_seconds must be in 1..31536000")
        expected_unit = _canonical_unit(self.key)
        if expected_unit is not None and self.unit != expected_unit:
            raise ValueError(f"{self.key} requires unit {expected_unit}")
        if self.operator is PredicateOperator.RANGE:
            if type(self.expected) not in (int, float) or type(self.upper) not in (int, float):
                raise TypeError("range requires numeric lower and upper bounds")
            if self.expected > self.upper:
                raise ValueError("range lower bound exceeds upper bound")
        elif self.upper is not None:
            raise ValueError("upper is valid only for range")


@dataclass(frozen=True, slots=True)
class RequirementAlternative:
    predicates: tuple[CapabilityPredicate, ...]
    same_resource: bool = True

    def __post_init__(self) -> None:
        if type(self.predicates) is not tuple or not self.predicates or any(
            not isinstance(item, CapabilityPredicate) for item in self.predicates
        ):
            raise ValueError("alternative requires predicates")
        if type(self.same_resource) is not bool:
            raise TypeError("same_resource must be bool")


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    requirement_id: str
    alternatives: tuple[RequirementAlternative, ...]
    preferred: bool = False

    def __post_init__(self) -> None:
        _identifier(self.requirement_id, "requirement_id")
        if type(self.alternatives) is not tuple or not self.alternatives or any(
            not isinstance(item, RequirementAlternative) for item in self.alternatives
        ) or len(self.alternatives) > 16:
            raise ValueError("requirements need 1..16 alternatives")
        if type(self.preferred) is not bool:
            raise TypeError("preferred must be bool")


@dataclass(frozen=True, slots=True)
class ResourceSupply:
    host_id: str
    enrolled: bool
    trusted: bool
    inventory_revision: int
    facts: tuple[CapabilityFact, ...]
    parent_host_id: str | None = None

    def __post_init__(self) -> None:
        _identifier(self.host_id, "host_id")
        if self.parent_host_id is not None:
            _identifier(self.parent_host_id, "parent_host_id")
            if self.parent_host_id == self.host_id:
                raise ValueError("host cannot be its own parent")
        if type(self.enrolled) is not bool or type(self.trusted) is not bool:
            raise TypeError("enrolled/trusted must be bool")
        if type(self.inventory_revision) is not int or self.inventory_revision < 1:
            raise ValueError("inventory_revision must be positive")
        if type(self.facts) is not tuple or any(
            not isinstance(item, CapabilityFact) or item.host_id != self.host_id
            for item in self.facts
        ):
            raise ValueError("facts must belong to the supply host")


@dataclass(frozen=True, slots=True)
class CompatibilityAssessment:
    host_id: str
    compatible: bool
    matched: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    unknown: tuple[tuple[str, str], ...]
    preferred_unmet: tuple[str, ...]
    inventory_revision: int


def _version_parts(value: object) -> tuple[int, ...] | None:
    if not isinstance(value, str) or _VERSION.fullmatch(value) is None:
        return None
    main = re.split(r"[-+]", value, maxsplit=1)[0]
    return tuple(int(part) for part in main.split("."))


def _matches(fact: CapabilityFact, predicate: CapabilityPredicate) -> bool:
    if fact.unit != predicate.unit:
        return False
    actual, expected = fact.value, predicate.expected
    operator = predicate.operator
    if operator is PredicateOperator.EQUALS:
        return actual == expected
    if operator in (PredicateOperator.MINIMUM, PredicateOperator.MAXIMUM):
        if type(actual) not in (int, float) or type(expected) not in (int, float):
            return False
        return actual >= expected if operator is PredicateOperator.MINIMUM else actual <= expected
    if operator is PredicateOperator.RANGE:
        return type(actual) in (int, float) and expected <= actual <= predicate.upper  # type: ignore[operator]
    if operator is PredicateOperator.CONTAINS:
        return isinstance(actual, tuple) and (
            (isinstance(expected, str) and expected in actual)
            or (isinstance(expected, tuple) and set(expected).issubset(actual))
        )
    if operator is PredicateOperator.IN_SET:
        return isinstance(expected, tuple) and actual in expected
    if operator is PredicateOperator.VERSION:
        left, right = _version_parts(actual), _version_parts(expected)
        return left is not None and right is not None and left >= right
    return False


def _alternative_state(
    alternative: RequirementAlternative,
    facts: tuple[CapabilityFact, ...],
    now: datetime,
) -> tuple[MatchState, str]:
    candidates: dict[str, list[CapabilityFact]] = {}
    for fact in facts:
        candidates.setdefault(fact.resource_id, []).append(fact)
    pools = tuple(candidates.values()) if alternative.same_resource else [list(facts)]
    saw_current = False
    for pool in pools:
        all_match = True
        for predicate in alternative.predicates:
            age = None if predicate.maximum_age_seconds is None else timedelta(
                seconds=predicate.maximum_age_seconds
            )
            relevant = tuple(
                fact for fact in pool
                if fact.key == predicate.key
                and fact.verified
                and fact.evidence_class in predicate.required_evidence
                and fact.fresh(now, age)
            )
            if relevant:
                saw_current = True
            if not relevant or not any(_matches(fact, predicate) for fact in relevant):
                all_match = False
                break
        if all_match:
            return MatchState.MATCH, "matched verified capability facts"
    if not saw_current:
        return MatchState.UNKNOWN, "required capability evidence is missing or stale"
    return MatchState.REJECTED, "verified capability facts do not satisfy predicate"


def evaluate_resource_requirements(
    supply: ResourceSupply,
    requirements: tuple[CapabilityRequirement, ...],
    *,
    now: datetime,
) -> CompatibilityAssessment:
    """Deterministically evaluate requirements without granting authority."""
    if not isinstance(supply, ResourceSupply):
        raise TypeError("supply must be ResourceSupply")
    moment = _utc(now, "now")
    if type(requirements) is not tuple or any(
        not isinstance(item, CapabilityRequirement) for item in requirements
    ):
        raise TypeError("requirements must be CapabilityRequirement values")
    rejected: list[tuple[str, str]] = []
    unknown: list[tuple[str, str]] = []
    matched: list[str] = []
    preferred_unmet: list[str] = []
    if not supply.enrolled:
        rejected.append(("host.enrollment", "host is not enrolled"))
    if not supply.trusted:
        rejected.append(("host.trust", "host is not trusted"))
    for requirement in requirements:
        states = tuple(
            _alternative_state(alternative, supply.facts, moment)
            for alternative in requirement.alternatives
        )
        if any(state is MatchState.MATCH for state, _ in states):
            matched.append(requirement.requirement_id)
            continue
        state = (
            MatchState.UNKNOWN
            if all(item is MatchState.UNKNOWN for item, _ in states)
            else MatchState.REJECTED
        )
        reason = "; ".join(dict.fromkeys(reason for _, reason in states))
        if requirement.preferred:
            preferred_unmet.append(requirement.requirement_id)
        elif state is MatchState.UNKNOWN:
            unknown.append((requirement.requirement_id, reason))
        else:
            rejected.append((requirement.requirement_id, reason))
    return CompatibilityAssessment(
        supply.host_id, not rejected and not unknown, tuple(matched),
        tuple(rejected), tuple(unknown), tuple(preferred_unmet),
        supply.inventory_revision,
    )


def requirement_to_document(requirement: CapabilityRequirement) -> dict[str, object]:
    """Return canonical JSON-compatible signed-manifest data."""
    def encoded(value: CapabilityValue) -> object:
        return list(value) if isinstance(value, tuple) else value
    return {
        "alternatives": [{
            "predicates": [{
                "expected": encoded(predicate.expected),
                "expected_is_set": isinstance(predicate.expected, tuple),
                "key": predicate.key,
                "maximum_age_seconds": predicate.maximum_age_seconds,
                "operator": predicate.operator.value,
                "required_evidence": [item.value for item in predicate.required_evidence],
                "unit": predicate.unit,
                "upper": predicate.upper,
            } for predicate in alternative.predicates],
            "same_resource": alternative.same_resource,
        } for alternative in requirement.alternatives],
        "preferred": requirement.preferred,
        "requirement_id": requirement.requirement_id,
    }


def requirement_from_document(document: object) -> CapabilityRequirement:
    """Strictly parse untrusted manifest requirement data."""
    if not isinstance(document, Mapping) or set(document) != {
        "alternatives", "preferred", "requirement_id",
    }:
        raise ValueError("resource requirement has invalid fields")
    raw_alternatives = document["alternatives"]
    if not isinstance(raw_alternatives, list):
        raise ValueError("resource alternatives must be a list")
    alternatives = []
    for raw_alternative in raw_alternatives:
        if not isinstance(raw_alternative, Mapping) or set(raw_alternative) != {
            "predicates", "same_resource",
        } or not isinstance(raw_alternative["predicates"], list):
            raise ValueError("resource alternative has invalid fields")
        if type(raw_alternative["same_resource"]) is not bool:
            raise ValueError("same_resource must be boolean")
        predicates = []
        for raw in raw_alternative["predicates"]:
            if not isinstance(raw, Mapping) or set(raw) != {
                "expected", "expected_is_set", "key", "maximum_age_seconds",
                "operator", "required_evidence", "unit", "upper",
            } or not isinstance(raw["required_evidence"], list):
                raise ValueError("resource predicate has invalid fields")
            if type(raw["expected_is_set"]) is not bool:
                raise ValueError("expected_is_set must be boolean")
            expected = raw["expected"]
            if raw["expected_is_set"]:
                if not isinstance(expected, list):
                    raise ValueError("resource predicate set is invalid")
                expected = tuple(expected)
            predicates.append(CapabilityPredicate(
                key=raw["key"],  # type: ignore[arg-type]
                operator=PredicateOperator(raw["operator"]),
                expected=expected,  # type: ignore[arg-type]
                upper=raw["upper"],  # type: ignore[arg-type]
                unit=raw["unit"],  # type: ignore[arg-type]
                required_evidence=tuple(
                    EvidenceClass(item) for item in raw["required_evidence"]
                ),
                maximum_age_seconds=raw["maximum_age_seconds"],  # type: ignore[arg-type]
            ))
        alternatives.append(RequirementAlternative(
            tuple(predicates), raw_alternative["same_resource"],  # type: ignore[arg-type]
        ))
    if type(document["preferred"]) is not bool:
        raise ValueError("preferred must be boolean")
    return CapabilityRequirement(
        document["requirement_id"], tuple(alternatives), document["preferred"],  # type: ignore[arg-type]
    )
