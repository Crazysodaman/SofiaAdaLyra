"""Immutable evidence records for offline, integration and live acceptance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import re

_SHA = re.compile(r"^[0-9a-f]{40}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/+\-]{0,191}$")


def _id(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded identifier")
    return value


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


class EvidenceKind(str, Enum):
    STATIC = "static"
    UNIT = "unit"
    INTEGRATION = "integration"
    LIVE = "live"
    RECOVERY = "recovery"
    SOAK = "soak"
    NEGATIVE = "negative"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    evidence_id: str
    kind: EvidenceKind
    observed_at: datetime
    passed: bool
    command_or_probe: str
    detail: str
    host_id: str | None = None

    def __post_init__(self) -> None:
        _id(self.evidence_id, "evidence_id")
        if not isinstance(self.kind, EvidenceKind):
            raise TypeError("kind must be EvidenceKind")
        _utc(self.observed_at)
        if not isinstance(self.passed, bool):
            raise TypeError("passed must be boolean")
        if not isinstance(self.command_or_probe, str) or not self.command_or_probe.strip():
            raise ValueError("command_or_probe required")
        if not isinstance(self.detail, str):
            raise TypeError("detail must be text")
        if self.host_id is not None:
            _id(self.host_id, "host_id")


@dataclass(frozen=True, slots=True)
class VerificationManifest:
    verification_id: str
    git_revision: str
    package_ids: tuple[str, ...]
    evidence: tuple[EvidenceRecord, ...]

    def __post_init__(self) -> None:
        _id(self.verification_id, "verification_id")
        if not isinstance(self.git_revision, str) or _SHA.fullmatch(
            self.git_revision
        ) is None:
            raise ValueError("git_revision must be full lowercase Git SHA")
        if not isinstance(self.package_ids, tuple) or not self.package_ids:
            raise ValueError("package_ids must be a nonempty tuple")
        for package_id in self.package_ids:
            _id(package_id, "package_id")
        if len(set(self.package_ids)) != len(self.package_ids):
            raise ValueError("package_ids must be unique")
        if not isinstance(self.evidence, tuple):
            raise TypeError("evidence must be a tuple")
        for record in self.evidence:
            if not isinstance(record, EvidenceRecord):
                raise TypeError("evidence must contain EvidenceRecord")
        ids = tuple(record.evidence_id for record in self.evidence)
        if len(set(ids)) != len(ids):
            raise ValueError("evidence IDs must be unique")

    @property
    def passed(self) -> bool:
        return bool(self.evidence) and all(item.passed for item in self.evidence)

    @property
    def digest(self) -> str:
        document = {
            "verification_id": self.verification_id,
            "git_revision": self.git_revision,
            "package_ids": list(self.package_ids),
            "evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "kind": item.kind.value,
                    "observed_at": _utc(item.observed_at).isoformat(),
                    "passed": item.passed,
                    "command_or_probe": item.command_or_probe,
                    "detail": item.detail,
                    "host_id": item.host_id,
                }
                for item in self.evidence
            ],
        }
        return sha256(
            json.dumps(
                document,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
