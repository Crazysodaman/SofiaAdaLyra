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
from itertools import islice
import os
import re
import stat

from sofia.core.creative.model import ArtifactRevision, ArtifactKind
from sofia.core.life.model import PersonalJudgment, TechnicalOutcome


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


@dataclass(frozen=True, slots=True)
class StructuredArtifactCritique:
    """Read-only, independently grounded LIFE review before durable settlement.

    A suggestion is not an approval, work order, success receipt or personal
    preference. The content digest and revision are rechecked on commit.
    """

    project_id: str
    artifact_id: str
    artifact_revision: int
    content_sha256: str
    technical_outcome: TechnicalOutcome
    findings: tuple[ObjectiveFinding, ...]
    personal_judgment: PersonalJudgment
    revision_plan: tuple[str, ...]
    structural_coverage: float
    evidence_refs: tuple[str, ...]

    @property
    def confidence(self) -> float:
        """Certainty of independently checked objective disposition, not taste."""
        return self.structural_coverage

    @property
    def objective_results(self) -> dict[str, bool | None]:
        return {
            item.objective: (
                True if item.disposition is ObjectiveDisposition.PASS
                else False if item.disposition is ObjectiveDisposition.FAIL
                else None
            ) for item in self.findings
        }


def structured_critique_from_report(
    *, project_id: str, report: ArtifactObjectiveReport,
    personal_judgment: PersonalJudgment,
    evidence_refs: tuple[str, ...],
) -> StructuredArtifactCritique:
    """Prepare an unprivileged review from verified original bytes only."""
    if not isinstance(personal_judgment, PersonalJudgment):
        raise TypeError("personal critique must be typed and explicit")
    if not isinstance(evidence_refs, tuple) or not evidence_refs or any(
        not isinstance(ref, str) or not ref.strip() for ref in evidence_refs
    ):
        raise ValueError("critique requires original canonical evidence references")
    if report.integrity is not ObjectiveDisposition.PASS or not report.findings:
        raise ValueError("critique needs an intact artifact and original objectives")
    if any(len(item.objective) > 500 for item in report.findings):
        raise ValueError("critique objective exceeds original brief bounds")
    if len(report.findings) > 16 or len(set(
        item.objective for item in report.findings
    )) != len(report.findings):
        raise ValueError("critique original objectives must be distinct and bounded")
    if all(x.disposition is ObjectiveDisposition.PASS for x in report.findings):
        outcome = TechnicalOutcome.VALID
    elif any(x.disposition is ObjectiveDisposition.FAIL for x in report.findings):
        outcome = TechnicalOutcome.INVALID
    else:
        outcome = TechnicalOutcome.INCONCLUSIVE
    # Revisions are suggestions only. Missing or unsupported checks never
    # silently transform themselves into a claim about artistic quality.
    plan = tuple(
        f"Review original objective: {item.objective} ({item.reason})"
        for item in report.findings
        if item.disposition is not ObjectiveDisposition.PASS
    )
    inspected = sum(
        x.disposition is not ObjectiveDisposition.UNKNOWN for x in report.findings
    )
    return StructuredArtifactCritique(
        project_id=project_id, artifact_id=report.artifact_id,
        artifact_revision=report.revision, content_sha256=report.content_sha256,
        technical_outcome=outcome, findings=report.findings,
        personal_judgment=personal_judgment,
        revision_plan=plan, structural_coverage=inspected / len(report.findings),
        evidence_refs=evidence_refs,
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
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 8:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "min_bytes", "invalid integer criterion")
    minimum = int(raw)
    if minimum < 1 or minimum > 64 * 1024 * 1024:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "min_bytes", "out-of-policy byte count")
    passed = len(content) >= minimum
    return ObjectiveFinding(objective, ObjectiveDisposition.PASS if passed else ObjectiveDisposition.FAIL, "min_bytes", "size criterion met" if passed else "too small")


def _min_words(objective: str, *, content: bytes, kind: ArtifactKind) -> ObjectiveFinding:
    """Count real UTF-8 whitespace-separated words, not a generator claim."""
    if kind not in {ArtifactKind.TEXT, ArtifactKind.STORY, ArtifactKind.CODE}:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "min_words", "kind is not UTF-8 text")
    raw = objective.split(":", 1)[1].strip()
    if not raw.isascii() or not raw.isdecimal() or len(raw) > 6:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "min_words", "invalid word criterion")
    minimum = int(raw)
    if minimum < 1 or minimum > 100_000:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "min_words", "out-of-policy word count")
    try:
        visible = content.decode("utf-8", "strict")
    except UnicodeError:
        return ObjectiveFinding(objective, ObjectiveDisposition.FAIL, "min_words", "invalid UTF-8")
    # Iterate Unicode whitespace-delimited words without allocating a list
    # of every word from an artifact that can be as large as 64 MiB.
    # Stop scanning as soon as the independently typed minimum is reached.
    passed = sum(1 for _ in islice(re.finditer(r"\S+", visible), minimum)) >= minimum
    return ObjectiveFinding(objective, ObjectiveDisposition.PASS if passed else ObjectiveDisposition.FAIL,
                            "min_words", "original word count met" if passed else "too few original words")


def _python_syntax(objective: str, *, content: bytes, kind: ArtifactKind) -> ObjectiveFinding:
    """Syntax-only CODE check; no eval, import, exec or quality self-score."""
    if kind is not ArtifactKind.CODE:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "python_syntax", "only CODE artifacts supported")
    if objective.split(":", 1)[1].strip().casefold() != "python":
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "python_syntax", "unsupported language")
    if len(content) > 256_000:
        return ObjectiveFinding(objective, ObjectiveDisposition.UNKNOWN, "python_syntax", "code exceeds parser budget")
    try:
        source = content.decode("utf-8", "strict")
        # ast.parse() accepts constructs such as a module-level `return` or
        # `break` that Python rejects. Compile to a code object without
        # executing it so PASS reflects an actually compilable module.
        compile(source, filename="<artifact>", mode="exec", dont_inherit=True)
    except UnicodeError:
        return ObjectiveFinding(objective, ObjectiveDisposition.FAIL, "python_syntax", "invalid UTF-8")
    except (SyntaxError, ValueError, TypeError, RecursionError, OverflowError):
        return ObjectiveFinding(objective, ObjectiveDisposition.FAIL, "python_syntax", "Python syntax invalid")
    return ObjectiveFinding(objective, ObjectiveDisposition.PASS, "python_syntax", "Python compiles; execution and behavior not proved")


# Closed, host-owned registries.  Objective names alone are deliberately not
# enough to select a validator: the immutable creative revision's ArtifactKind
# also has to admit that check.  This keeps, for example, a model from attaching
# ``text_contains`` to an image or ``python_syntax`` to a story and receiving a
# misleading technical verdict.  ``min_bytes`` is the only representation-level
# check shared by every currently supported artifact kind.
_MIN_BYTES = _ObjectiveRule("min_bytes", _min_bytes)
_TEXT_CONTAINS = _ObjectiveRule("text_contains", _text_contains)
_MIN_WORDS = _ObjectiveRule("min_words", _min_words)
_PYTHON_SYNTAX = _ObjectiveRule("python_syntax", _python_syntax)

_ARTIFACT_KIND_VALIDATORS: dict[ArtifactKind, dict[str, _ObjectiveRule]] = {
    kind: {"min_bytes": _MIN_BYTES} for kind in ArtifactKind
}
for _text_kind in (ArtifactKind.TEXT, ArtifactKind.STORY, ArtifactKind.CODE):
    _ARTIFACT_KIND_VALIDATORS[_text_kind] = {
        **_ARTIFACT_KIND_VALIDATORS[_text_kind],
        "text_contains": _TEXT_CONTAINS,
        "min_words": _MIN_WORDS,
    }
_ARTIFACT_KIND_VALIDATORS[ArtifactKind.CODE] = {
    **_ARTIFACT_KIND_VALIDATORS[ArtifactKind.CODE],
    "python_syntax": _PYTHON_SYNTAX,
}


def inspect_objective_artifact(
    *, revision: ArtifactRevision, path: Path, objectives: tuple[str, ...],
    max_inspect_bytes: int = 64 * 1024 * 1024,
) -> ArtifactObjectiveReport:
    if not isinstance(revision, ArtifactRevision):
        raise TypeError("ArtifactRevision required")
    if not isinstance(path, Path):
        raise TypeError("path must be Path")
    # A caller must inspect the exact path recorded for this immutable
    # creative revision. Matching bytes copied to a different file do not
    # establish provenance for the original artifact or its RUN receipt.
    if path != Path(revision.content_path):
        return ArtifactObjectiveReport(
            revision.artifact_id, revision.revision,
            revision.content_sha256, ObjectiveDisposition.FAIL, (),
        )
    if not isinstance(objectives, tuple) or any(not isinstance(x, str) for x in objectives):
        raise TypeError("objectives must be text tuple")
    if type(max_inspect_bytes) is not int or not 1 <= max_inspect_bytes <= 64 * 1024 * 1024:
        raise ValueError("bounded inspection size required")
    # The source path is untrusted until its *opened descriptor* has been
    # independently identified. A pre-check followed by path.read_bytes()
    # could otherwise race a replacement, symlink swap or oversized write.
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode):
            raise OSError("source is not an ordinary file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            opened = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
                or opened.st_size < 1
                or opened.st_size > max_inspect_bytes
                or opened.st_size != revision.byte_size
            ):
                raise OSError("artifact descriptor or length changed")
            # Bound actual bytes even if another writer grows the file.
            content = stream.read(max_inspect_bytes + 1)
            after_open = os.fstat(stream.fileno())
        after_path = path.lstat()
        if (
            len(content) != revision.byte_size
            or after_open.st_size != opened.st_size
            or after_open.st_mtime_ns != opened.st_mtime_ns
            or (after_path.st_dev, after_path.st_ino) != (opened.st_dev, opened.st_ino)
            or not stat.S_ISREG(after_path.st_mode)
        ):
            raise OSError("artifact changed during independent inspection")
    except OSError:
        return ArtifactObjectiveReport(revision.artifact_id, revision.revision, revision.content_sha256, ObjectiveDisposition.FAIL, ())
    if sha256(content).hexdigest() != revision.content_sha256:
        return ArtifactObjectiveReport(revision.artifact_id, revision.revision, revision.content_sha256, ObjectiveDisposition.FAIL, ())
    findings: list[ObjectiveFinding] = []
    kind_validators = _ARTIFACT_KIND_VALIDATORS.get(revision.kind, {})
    for objective in objectives:
        name, sep, _ = objective.partition(":")
        validator = kind_validators.get(name.strip().casefold()) if sep else None
        if validator is None:
            findings.append(ObjectiveFinding(
                objective, ObjectiveDisposition.UNKNOWN, "unsupported",
                "objective has no reviewed validator for this artifact kind",
            ))
        else:
            findings.append(validator.verify(objective, content=content, kind=revision.kind))
    return ArtifactObjectiveReport(
        revision.artifact_id, revision.revision, revision.content_sha256,
        ObjectiveDisposition.PASS, tuple(findings),
    )
