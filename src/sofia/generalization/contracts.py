"""Typed contracts for sealed, independently graded novel-problem suites."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_REVISION = re.compile(r"[0-9a-f]{40}\Z")


def _id(value: str, name: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{name} must be a bounded identifier")
    return value


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def answer_digest(value: object) -> str:
    """Hash a grader-owned expected/submitted value without storing the key."""
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


class ProblemDomain(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    DOCKER = "docker"
    CODING = "coding"
    SIMULATION = "simulation"


class SuiteSplit(str, Enum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class ExplorationAdmission:
    """Observed admission inputs; these are limits, never execution authority."""

    busy: bool = False
    cpu_percent: float | None = None
    gpu_percent: float | None = None
    resource_pressure: float = 0.0

    def __post_init__(self) -> None:
        if type(self.busy) is not bool:
            raise TypeError("busy must be bool")
        for name in ("cpu_percent", "gpu_percent"):
            value = getattr(self, name)
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
                or not 0 <= float(value) <= 100
            ):
                raise ValueError(f"{name} must be unknown or in 0..100")
        if (
            isinstance(self.resource_pressure, bool)
            or not isinstance(self.resource_pressure, (int, float))
            or not 0 <= float(self.resource_pressure) <= 1
        ):
            raise ValueError("resource_pressure must be in 0..1")


@dataclass(frozen=True, slots=True)
class NovelProblemCase:
    case_id: str
    family_id: str
    domain: ProblemDomain
    split: SuiteSplit
    prompt: str
    expected_answer_sha256: str
    milestone_digests: tuple[tuple[str, str], ...] = ()
    required_evidence_kinds: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _id(self.case_id, "case_id")
        _id(self.family_id, "family_id")
        if not isinstance(self.domain, ProblemDomain) or not isinstance(self.split, SuiteSplit):
            raise TypeError("domain and split must be typed")
        if not isinstance(self.prompt, str) or not self.prompt.strip() or len(self.prompt) > 12_000:
            raise ValueError("prompt must be bounded nonempty text")
        if _SHA.fullmatch(self.expected_answer_sha256) is None:
            raise ValueError("expected_answer_sha256 must be SHA-256")
        names = []
        for name, digest in self.milestone_digests:
            names.append(_id(name, "milestone name"))
            if _SHA.fullmatch(digest) is None:
                raise ValueError("milestone digest must be SHA-256")
        if len(names) != len(set(names)) or len(names) > 32:
            raise ValueError("milestones must be unique and bounded")
        allowed = {"operation_receipt", "reviewed_evidence", "external_observation"}
        if (
            len(self.required_evidence_kinds) > 8
            or len(set(self.required_evidence_kinds)) != len(self.required_evidence_kinds)
            or any(item not in allowed for item in self.required_evidence_kinds)
        ):
            raise ValueError("unsupported or duplicate required evidence kind")


@dataclass(frozen=True, slots=True)
class NovelProblemSuite:
    suite_id: str
    source_revision: str
    cases: tuple[NovelProblemCase, ...]
    sealed_at: datetime
    retention_until: datetime
    provenance_ref: str

    def __post_init__(self) -> None:
        _id(self.suite_id, "suite_id")
        if _REVISION.fullmatch(self.source_revision) is None:
            raise ValueError("source_revision must be an exact Git revision")
        sealed = _aware(self.sealed_at, "sealed_at")
        retained = _aware(self.retention_until, "retention_until")
        if retained <= sealed or retained - sealed > __import__("datetime").timedelta(days=365):
            raise ValueError("suite retention must be positive and at most one year")
        if not isinstance(self.provenance_ref, str) or not self.provenance_ref.strip():
            raise ValueError("suite provenance required")
        if not isinstance(self.cases, tuple) or not 5 <= len(self.cases) <= 500:
            raise ValueError("suite requires 5..500 cases")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("case IDs must be unique")
        if {case.domain for case in self.cases} != set(ProblemDomain):
            raise ValueError("suite must cover all required problem domains")
        if {case.split for case in self.cases} != set(SuiteSplit):
            raise ValueError("suite must contain train, validation and test splits")
        ownership: dict[str, SuiteSplit] = {}
        for case in self.cases:
            prior = ownership.setdefault(case.family_id, case.split)
            if prior is not case.split:
                raise ValueError("problem families cannot cross suite splits")

    @property
    def seal_digest(self) -> str:
        body = [{
            "case_id": item.case_id, "family_id": item.family_id,
            "domain": item.domain.value, "split": item.split.value,
            "prompt_sha256": answer_digest(item.prompt),
            "expected_answer_sha256": item.expected_answer_sha256,
            "milestones": item.milestone_digests,
            "required_evidence_kinds": item.required_evidence_kinds,
        } for item in sorted(self.cases, key=lambda case: case.case_id)]
        return answer_digest({
            "suite_id": self.suite_id, "source_revision": self.source_revision,
            "cases": body, "sealed_at": _aware(self.sealed_at, "sealed_at").isoformat(),
            "provenance_ref": self.provenance_ref,
        })


@dataclass(frozen=True, slots=True)
class AttemptMetrics:
    inference_route: str
    model_id: str
    elapsed_ms: int
    estimated_tokens: int
    intervention_count: int
    tool_call_count: int

    def __post_init__(self) -> None:
        _id(self.inference_route, "inference_route")
        _id(self.model_id, "model_id")
        for name, value, maximum in (
            ("elapsed_ms", self.elapsed_ms, 7 * 24 * 3_600_000),
            ("estimated_tokens", self.estimated_tokens, 10_000_000),
            ("intervention_count", self.intervention_count, 10_000),
            ("tool_call_count", self.tool_call_count, 10_000),
        ):
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError(f"{name} outside bounded range")
