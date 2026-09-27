from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ReleaseEvidence:
    """Revision-pinned verification facts for one candidate release."""

    release_id: str
    git_revision: str
    manifest_sha256: str
    verified_at: datetime
    source_tests_passed: bool
    state_schema_compatible: bool
    fleet_protocol_compatible: bool
    dependencies_verified: bool
    artifacts_verified: bool
    signature_verified: bool
    semantic_integrity_verified: bool

    def __post_init__(self) -> None:
        for name in ("release_id", "git_revision", "manifest_sha256"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be nonempty")
        if not isinstance(self.verified_at, datetime):
            raise TypeError("verified_at must be a datetime")
        if self.verified_at.tzinfo is None or self.verified_at.utcoffset() is None:
            raise ValueError("verified_at must be timezone-aware")

    @property
    def accepted(self) -> bool:
        return all(
            (
                self.source_tests_passed,
                self.state_schema_compatible,
                self.fleet_protocol_compatible,
                self.dependencies_verified,
                self.artifacts_verified,
                self.signature_verified,
                self.semantic_integrity_verified,
            )
        )
