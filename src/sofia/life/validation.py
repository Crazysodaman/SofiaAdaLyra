"""Independent, read-only artifact checks, deliberately distinct from LLM critique.

Only explicitly typed objectives can PASS; arbitrary prose remains UNKNOWN.
A hash-verified artifact isn't evidence that a project goal was accomplished.
This module cannot mutate project/goal/memory/SAFE state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path

from sofia.creative.model import ArtifactRevision, ArtifactKind


class ObjectiveDisposition(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ObjectiveFinding:
    objective: str
    disposition: ObjectiveDisposition
    check: str
    reason: str


@dataclass(frozen=True, slots=True)
class ArtifactObjectiveReport:
    artifact_id: str
    revision: int
    content_sha256: str
    integrity: ObjectiveDisposition
    findings: tuple[ObjectiveFinding, ...]
    checker_version: str = "structural-objectives-v1"

    @property
    def eligible_for_independent_completion(self) -> bool:
        return (
            self.integrity is ObjectiveDisposition.PASS
            and bool(self.findings)
            and all(item.disposition is ObjectiveDisposition.PASS for item in self.findings)
        )


class _ObjectiveRule:
    """Single deterministic rule. Unsupported natural-language goals abstain."""

    def __init__(self, name: str, validator):
        self.name, self.validator = name, validator

    def verify(self, criterion: str, *, content: bytes, kind: ArtifactKind) -> ObjectiveFinding:
        return self.validator(criterion, content=content, kind=kind)


def _text_contains(objective: str, *, content: bytes, kind: ArtifactKind) -> ObjectiveFinding:
    if kind not in {ArtifactKind.TEXT, ArtifactKind.STORY, ArtifactKind.CODE}:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "text_contains", "kind not text-checkable")
    term = objective.split(":", 1)[1].strip()
    if not term or len(term) > 300:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "text_contains", "invalid bounded term")
    try:
        visible = content.decode("utf-8", "strict")
    except UnicodeError:
        return ObjectiveFinding(objective, ObjectiveDisposition.FAIL, "text_contains", "invalid UTF-8")
    passed = term.casefold() in visible.casefold()
    return ObjectiveFinding(objective, ObjectiveDisposition.PASS if passed else ObjectiveDisposition.FAIL, "text_contains", "literal phrase found" if passed else "literal phrase missing")


def _min_bytes(objective: str, *, content: bytes, kind: ArtifactKind) -> ObjectiveFinding:
    raw = objective.split(":", 1)[1].strip()
    if not raw.isascii() or not raw.isdecimal():
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "min_bytes", "invalid integer criterion")
    minimum = int(raw)
    if minimum < 1 or minimum > 64 * 1024 * 1024:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "min_bytes", "out-of-policy byte count")
    passed = len(content) >= minimum
    return ObjectiveFinding(objective, ObjectiveDisposition.PASS if passed else ObjectiveDisposition.FAIL, "min_bytes", "size criterion met" if passed else "too small")


# A closed, externally reviewed registry. The model does not register validators.
_VALIDATORS = {
    "text_contains": _ObjectiveRule("text_contains", _text_contains),
    "min_bytes": _ObjectiveRule("min_bytes", _min_bytes),
}


def inspect_objective_artifact(
    *, revision: ArtifactRevision, path: Path, objectives: tuple[str, ...],
    max_inspect_bytes: int = 64 * 1024 * 1024,
) -> ArtifactObjectiveReport:
    if not isinstance(revision, ArtifactRevision):
        raise TypeError("ArtifactRevision required")
    if not isinstance(path, Path):
        raise TypeError("path must be Path")
    if not isinstance(objectives, tuple) or any(not isinstance(x, str) for x in objectives):
        raise TypeError("objectives must be text tuple")
    if type(max_inspect_bytes) is not int or not 1 <= max_inspect_bytes <= 64 * 1024 * 1024:
        raise ValueError("bounded inspection size required")
    if not path.is_file() or path.is_symlink():
        return ArtifactObjectiveReport(revision.artifact_id, revision.revision, revision.content_sha256, ObjectiveDisposition.FAIL, ())
    size = path.stat().st_size
    if size < 1 or size > max_inspect_bytes or size != revision.byte_size:
        return ArtifactObjectiveReport(revision.artifact_id, revision.revision, revision.content_sha256, ObjectiveDisposition.FAIL, ())
    content = path.read_bytes()
    expected = sha256(content).hexdigest()
    if expected != revision.content_sha256:
        return ArtifactObjectiveReport(revision.artifact_id, revision.revision, revision.content_sha256, ObjectiveDisposition.FAIL, ())
    findings: list[ObjectiveFinding] = []
    for objective in objectives:
        name, sep, _ = objective.partition(":")
        validator = _VALIDATORS.get(name.strip().casefold()) if sep else None
        if validator is None:
            findings.append(ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "unsupported", "natural-language objective needs independent evidence or reviewed validator"))
        else:
            findings.append(validator.verify(objective, content=content, kind=revision.kind))
    return ArtifactObjectiveReport(
        revision.artifact_id, revision.revision, revision.content_sha256,
        ObjectiveDisposition.PASS, tuple(findings),
    )
