"""Immutable emotional evidence and derived state values."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sofia.social.model import AudienceKind, ScopeKind, SocialScope


@dataclass(frozen=True)
class EmotionalEvent:
    event_id: str
    occurred_at: datetime
    source: str
    evidence_ref: str
    description: str
    original_emotions: tuple[str, ...]
    current_emotions: tuple[str, ...]
    revision_count: int
    subject: str | None = None
    scope_kind: str = ScopeKind.GLOBAL.value
    principal_id: str | None = None
    audience_id: str | None = None
    audience_kind: str | None = None

    @property
    def scope(self) -> SocialScope:
        kind = ScopeKind(self.scope_kind)
        if kind is ScopeKind.RELATIONSHIP:
            return SocialScope.relationship(self.principal_id)
        if kind is ScopeKind.AUDIENCE:
            return SocialScope(
                ScopeKind.AUDIENCE,
                principal_id=self.principal_id,
                audience_id=self.audience_id,
                audience_kind=AudienceKind(self.audience_kind),
            )
        if kind is ScopeKind.SYSTEM:
            return SocialScope.system_scope()
        return SocialScope.global_scope()

@dataclass(frozen=True)
class ActiveEmotion:
    name: str
    intensity: float
    evidence_refs: tuple[str, ...]
    event_ids: tuple[str, ...]

@dataclass(frozen=True)
class ReturnExpectation:
    subject: str
    source_ref: str
    recorded_at: datetime
    expected_return_at: datetime

@dataclass(frozen=True)
class ReunionAppraisal:
    gap: timedelta
    expected_return_at: datetime | None
    lateness: timedelta | None
    emotions: tuple[str, ...]
    expectation_source_ref: str | None

@dataclass(frozen=True)
class CurrentEmotionalState:
    as_of: datetime
    subject: str | None
    tone: str
    active: tuple[ActiveEmotion, ...]
