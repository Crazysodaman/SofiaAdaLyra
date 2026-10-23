"""Canonical EVOLVE proposal for an isolated, governed DEV candidate."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re


_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


def _bounded_text(value: str, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{label} must be bounded nonempty text")
    return value.strip()


def _relative_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 300:
        raise ValueError("allowed paths must be bounded relative paths")
    path = PurePosixPath(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("allowed paths must remain inside the repository")
    return path.as_posix()


@dataclass(frozen=True, slots=True)
class CodeEvolutionProposal:
    """Evidence-backed request to build, but not install, a code candidate."""

    proposal_id: str
    base_sha: str
    prompt: str
    allowed_paths: tuple[str, ...]
    tests: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    reason: str
    rollback_plan: str
    created_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.proposal_id, str) or _ID.fullmatch(self.proposal_id) is None:
            raise ValueError("proposal_id must be a bounded identifier")
        if not isinstance(self.base_sha, str) or _SHA.fullmatch(self.base_sha) is None:
            raise ValueError("base_sha must be a lowercase Git SHA")
        _bounded_text(self.prompt, "prompt", 12000)
        if not isinstance(self.allowed_paths, tuple) or not self.allowed_paths or len(self.allowed_paths) > 64:
            raise ValueError("bounded allowed_paths required")
        normalized = tuple(_relative_path(item) for item in self.allowed_paths)
        if normalized != self.allowed_paths or len(set(normalized)) != len(normalized):
            raise ValueError("allowed_paths must be normalized and distinct")
        if not isinstance(self.tests, tuple) or len(self.tests) > 32:
            raise ValueError("tests must be a bounded tuple")
        for test in self.tests:
            _bounded_text(test, "test command", 500)
        if not isinstance(self.evidence_ids, tuple) or not self.evidence_ids or len(self.evidence_ids) > 32:
            raise ValueError("bounded evidence IDs required")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence IDs must be distinct")
        for evidence_id in self.evidence_ids:
            if not isinstance(evidence_id, str) or _ID.fullmatch(evidence_id) is None:
                raise ValueError("evidence_id must be a bounded identifier")
        _bounded_text(self.reason, "reason", 1000)
        _bounded_text(self.rollback_plan, "rollback_plan", 1000)
        if _utc(self.expires_at) <= _utc(self.created_at):
            raise ValueError("expiry must follow creation")

    @property
    def target(self) -> str:
        scope = json.dumps(self.allowed_paths, separators=(",", ":"))
        return f"code:{sha256(scope.encode('utf-8')).hexdigest()}"

    @property
    def fingerprint(self) -> str:
        document = {
            "proposal_id": self.proposal_id,
            "base_sha": self.base_sha,
            "prompt": self.prompt,
            "allowed_paths": list(self.allowed_paths),
            "tests": list(self.tests),
            "evidence_ids": list(self.evidence_ids),
            "reason": self.reason,
            "rollback_plan": self.rollback_plan,
            "created_at": _utc(self.created_at).isoformat(),
            "expires_at": _utc(self.expires_at).isoformat(),
        }
        return sha256(
            json.dumps(
                document,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()
