"""Independent, read-only artifact checks, deliberately distinct from LLM critique.

Only explicitly typed objectives can PASS; arbitrary prose remains UNKNOWN.
A hash-verified artifact isn't evidence that a project goal was accomplished.
This module cannot mutate project/goal/memory/SAFE state.
"""
from __future__ import annotations

from dataclasses import dataclass
import ast
from enum import Enum
from hashlib import sha256
from pathlib import Path
import os
import stat

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
    passed = len(visible.split()) >= minimum
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
        ast.parse(source, filename="<artifact>", mode="exec")
    except UnicodeError:
        return ObjectiveFinding(objective, ObjectiveDisposition.FAIL, "python_syntax", "invalid UTF-8")
    except (SyntaxError, ValueError, RecursionError):
        return ObjectiveFinding(objective, ObjectiveDisposition.FAIL, "python_syntax", "Python syntax invalid")
    return ObjectiveFinding(objective, ObjectiveDisposition.PASS, "python_syntax", "Python parses; behavior not proved")


# A closed, externally reviewed registry. The model does not register validators.
_VALIDATORS = {
    "text_contains": _ObjectiveRule("text_contains", _text_contains),
    "min_bytes": _ObjectiveRule("min_bytes", _min_bytes),
    "min_words": _ObjectiveRule("min_words", _min_words),
    "python_syntax": _ObjectiveRule("python_syntax", _python_syntax),
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
