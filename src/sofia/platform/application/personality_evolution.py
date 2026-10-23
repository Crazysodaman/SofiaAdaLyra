"""Owner-gated application boundary for trait-level personality evolution.

Only an authenticated owner principal may record, adjust, correct, or
retire a reviewed trait. Evolved traits are influence-only state: they may
shape expression style, but they never create evidence, facts, emotion
truth, memory truth, or authority. The static seed profile remains the
constitutional baseline; evolution is an additive, auditable layer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from sofia.core.personality.evolution import (
    TraitChangeKind,
    TraitDriftEntry,
    TraitEvolutionRecord,
    TraitEvolutionStore,
)
from sofia.core.social.model import PrincipalContext
from sofia.core.social.principals import SPARKS_PRINCIPAL_ID

EvidenceVerifier = Callable[[str], bool]


def _aware(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or (
        value.utcoffset() is None
    ):
        raise ValueError(f"{label} must be timezone-aware")
    return value


class PersonalityEvolutionService:
    """Application boundary for one canonical `TraitEvolutionStore`."""

    def __init__(
        self,
        store: TraitEvolutionStore,
        *,
        evidence_verifier: EvidenceVerifier | None = None,
    ) -> None:
        if not isinstance(store, TraitEvolutionStore):
            raise TypeError("store must be a TraitEvolutionStore")
        if evidence_verifier is not None and not callable(evidence_verifier):
            raise TypeError("evidence_verifier must be callable or None")
        self._store = store
        self._evidence_verifier = evidence_verifier

    @property
    def store(self) -> TraitEvolutionStore:
        return self._store

    def _require_owner(self, principal: PrincipalContext) -> None:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("an authenticated principal context is required")
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "only the authenticated owner may revise trait evolution"
            )

    def _verify_evidence(self, evidence_refs: tuple[str, ...]) -> None:
        if self._evidence_verifier is None:
            return
        for ref in evidence_refs:
            if not self._evidence_verifier(ref):
                raise ValueError(
                    f"evidence reference {ref!r} could not be verified "
                    "against its canonical source"
                )

    def record_trait(
        self,
        *,
        principal: PrincipalContext,
        trait: str,
        weight: float,
        confidence: float,
        reason: str,
        evidence_refs: tuple[str, ...],
        now: datetime,
    ) -> TraitEvolutionRecord:
        self._require_owner(principal)
        self._verify_evidence(evidence_refs)
        return self._store.hold(
            trait=trait,
            weight=weight,
            confidence=confidence,
            change_kind=TraitChangeKind.ORIGIN,
            reason=reason,
            evidence_refs=evidence_refs,
            expected_revision=None,
            now=_aware(now, "trait timestamp"),
        )

    def adjust_trait(
        self,
        *,
        principal: PrincipalContext,
        trait: str,
        weight: float,
        confidence: float,
        reason: str,
        evidence_refs: tuple[str, ...],
        expected_revision: int,
        now: datetime,
        correct: bool = False,
    ) -> TraitEvolutionRecord:
        self._require_owner(principal)
        self._verify_evidence(evidence_refs)
        change_kind = (
            TraitChangeKind.CORRECT if correct else TraitChangeKind.ADJUST
        )
        return self._store.hold(
            trait=trait,
            weight=weight,
            confidence=confidence,
            change_kind=change_kind,
            reason=reason,
            evidence_refs=evidence_refs,
            expected_revision=expected_revision,
            now=_aware(now, "trait timestamp"),
        )

    def retire_trait(
        self,
        *,
        principal: PrincipalContext,
        trait: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        expected_revision: int,
        now: datetime,
    ) -> TraitEvolutionRecord:
        self._require_owner(principal)
        self._verify_evidence(evidence_refs)
        return self._store.hold(
            trait=trait,
            weight=0.0,
            confidence=1.0,
            change_kind=TraitChangeKind.RETIRE,
            reason=reason,
            evidence_refs=evidence_refs,
            expected_revision=expected_revision,
            now=_aware(now, "retire timestamp"),
        )

    def expression_influences(
        self,
        *,
        minimum_confidence: float = 0.6,
        minimum_weight: float = 0.05,
        limit: int = 8,
    ) -> tuple[TraitEvolutionRecord, ...]:
        """Read-only reviewed influences; no authority is granted."""
        return self._store.active_influences(
            minimum_confidence=minimum_confidence,
            minimum_weight=minimum_weight,
            limit=limit,
        )

    def influence_context(
        self,
        *,
        limit: int = 8,
    ) -> str | None:
        influences = self.expression_influences(limit=limit)
        if not influences:
            return None
        lines = [
            "EVIDENCE-REVIEWED EVOLVED TRAITS (influence only, "
            "non-authoritative)",
            "These trait weights are audited evolution records; they shape "
            "wording and emphasis but never create evidence, emotion "
            "truth, facts, or authority.",
        ]
        for record in influences:
            lines.append(
                f"{record.trait}: weight={record.weight:.2f} "
                f"confidence={record.confidence:.2f} "
                f"(revision {record.revision})"
            )
        return "\n".join(lines)

    def drift_entries(
        self,
        *,
        window_days: int,
        now: datetime,
    ) -> tuple[TraitDriftEntry, ...]:
        return self._store.drift_entries(
            window_days=window_days,
            now=_aware(now, "drift observation timestamp"),
        )

    def history(self, trait: str) -> tuple[TraitEvolutionRecord, ...]:
        return self._store.history(trait)
