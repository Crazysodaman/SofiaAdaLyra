"""Offline engineering proposal screening; NEVER edits files or grants execution."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

_SHA = re.compile(r"[0-9a-f]{40}\Z")


class ReviewState(str, Enum):
    BLOCKED_PROTECTED = "blocked_protected"
    INVALID_PATH = "invalid_path"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True)
class ChangeProposal:
    proposal_id: str
    base_sha: str
    affected_paths: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    description: str
    test_plan: str
    rollback_plan: str

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or not self.proposal_id.strip():
            raise ValueError("proposal_id required")
        if not isinstance(self.base_sha, str) or _SHA.fullmatch(self.base_sha) is None:
            raise ValueError("base_sha must be a pinned lowercase 40-character SHA")
        if not isinstance(self.affected_paths, tuple) or not self.affected_paths or any(
            not isinstance(item, str) or not item for item in self.affected_paths
        ):
            raise ValueError("affected_paths must be nonempty tuple")
        if len(set(self.affected_paths)) != len(self.affected_paths):
            raise ValueError("duplicate paths")
        if not isinstance(self.source_evidence_ids, tuple) or not self.source_evidence_ids or any(
            not isinstance(item, str) or not item.strip() for item in self.source_evidence_ids
        ):
            raise ValueError("source evidence references required")
        for field in ("description", "test_plan", "rollback_plan"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} required")


@dataclass(frozen=True)
class ReviewFinding:
    state: ReviewState
    affected_path: str
    reason: str


_PROTECTED_COMPONENTS = frozenset({".git", ".env", "state", "secret", "secrets", "credentials", "backups", "backup"})
_PROTECTED_ROOTS = (("src", "sofia", "constitution"), ("src", "sofia", "identity"), ("src", "sofia", "data"))
_PROTECTED_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".pem", ".key")


def inspect(proposal: ChangeProposal) -> tuple[ReviewFinding, ...]:
    """Preflight classification, not a grant, patch, approval or security sandbox."""
    if not isinstance(proposal, ChangeProposal):
        raise TypeError("ChangeProposal required")
    result: list[ReviewFinding] = []
    for path in proposal.affected_paths:
        if (path.startswith("/") or "\\" in path or ":" in path or "\x00" in path
                or "//" in path or path.endswith("/") or any(x in ("", ".", "..") for x in path.split("/"))):
            result.append(ReviewFinding(ReviewState.INVALID_PATH, path, "untrusted relative path"))
            continue
        parts = tuple(item.casefold() for item in path.split("/"))
        if (any(part in _PROTECTED_COMPONENTS or part.startswith(".env.") for part in parts)
                or any(parts[:len(root)] == root for root in _PROTECTED_ROOTS)
                or parts[-1].endswith(_PROTECTED_SUFFIXES)):
            result.append(ReviewFinding(ReviewState.BLOCKED_PROTECTED, path, "protected state, identity, data or credentials"))
            continue
        result.append(ReviewFinding(ReviewState.REQUIRES_REVIEW, path, "human diff, tests and rollback still required"))
    return tuple(result)
