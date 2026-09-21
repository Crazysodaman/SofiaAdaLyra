"""Disclosure preflight for source-linked virtual notes and reflections.

This is NOT authentication, a capability grant, encryption, or a publishing API.
The caller must independently verify actor, audience, and grant provenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class Sensitivity(str, Enum):
    PRIVATE_REFLECTION = "private_reflection"
    PERSONAL = "personal"
    SHARED = "shared"


class Disclose(str, Enum):
    DENIED = "denied"
    NEEDS_TRUSTED_GRANT = "needs_trusted_grant"
    ELIGIBLE_FOR_TRUSTED_ENFORCEMENT = "eligible_for_trusted_enforcement"


def _time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class Artifact:
    artifact_id: str
    revision: int
    owner_id: str
    sensitivity: Sensitivity
    source_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if any(not isinstance(v, str) or not v.strip() for v in (self.artifact_id, self.owner_id)):
            raise ValueError("artifact and owner IDs required")
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("positive revision required")
        if not isinstance(self.sensitivity, Sensitivity):
            raise TypeError("Sensitivity enum required")
        if not isinstance(self.source_ids, tuple) or not self.source_ids or any(
            not isinstance(v, str) or not v.strip() for v in self.source_ids
        ):
            raise ValueError("source IDs required")
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("source IDs must be unique")


@dataclass(frozen=True)
class GrantRecord:
    """Externally issued record; presence alone is not trusted authorization."""
    grant_id: str
    artifact_id: str
    artifact_revision: int
    owner_id: str
    recipient_id: str
    issued_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if any(not isinstance(v, str) or not v.strip() for v in
               (self.grant_id, self.artifact_id, self.owner_id, self.recipient_id)):
            raise ValueError("grant identifiers required")
        if type(self.artifact_revision) is not int or self.artifact_revision < 1:
            raise ValueError("positive artifact revision required")
        if _time(self.expires_at) <= _time(self.issued_at):
            raise ValueError("grant expiry must follow issue")


def evaluate(artifact: Artifact, *, viewer_id: str, owner_id: str,
             now: datetime, trusted_actor: bool = False,
             verified_grant: GrantRecord | None = None,
             trusted_grant_origin: bool = False,
             revoked_grant_ids: frozenset[str] = frozenset()) -> Disclose:
    """Preflight only; actual authorization must be enforced by a trusted host.

    Private reflections are never auto-presented, even to their creator.
    Shared/personal material can only become eligible for an exact scoped grant.
    """
    if not isinstance(artifact, Artifact) or not isinstance(viewer_id, str) or not viewer_id.strip():
        raise ValueError("artifact and viewer required")
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise ValueError("configured owner required")
    if not all(isinstance(v, bool) for v in (trusted_actor, trusted_grant_origin)):
        raise TypeError("trust flags must be boolean")
    if not isinstance(revoked_grant_ids, frozenset):
        raise TypeError("revoked_grant_ids must be frozenset")
    moment = _time(now)
    if not trusted_actor or artifact.owner_id != owner_id or viewer_id != owner_id:
        return Disclose.DENIED
    if artifact.sensitivity is Sensitivity.PRIVATE_REFLECTION:
        return Disclose.DENIED
    if verified_grant is None or not trusted_grant_origin:
        return Disclose.NEEDS_TRUSTED_GRANT
    if not isinstance(verified_grant, GrantRecord):
        raise TypeError("GrantRecord required")
    if (verified_grant.grant_id in revoked_grant_ids
            or verified_grant.artifact_id != artifact.artifact_id
            or verified_grant.artifact_revision != artifact.revision
            or verified_grant.owner_id != owner_id
            or verified_grant.recipient_id != viewer_id
            or not _time(verified_grant.issued_at) <= moment < _time(verified_grant.expires_at)):
        return Disclose.DENIED
    return Disclose.ELIGIBLE_FOR_TRUSTED_ENFORCEMENT
