"""Owner-gated production surface for beliefs and convictions.

The application service is the only production writer for canonical
beliefs. It enforces:

- only an authenticated owner principal may record, revise, reconsider,
  schedule, or withdraw any position;
- owner statements are stored as owner attributions, never absorbed as
  Sofía-held convictions;
- evidence references must verify through the configured evidence source
  when one is wired (source verification);
- audience visibility is recorded exactly as decided.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from sofia.core.beliefs.model import (
    BeliefChangeKind,
    BeliefHolder,
    BeliefMatch,
    BeliefRecord,
    BeliefStance,
    BeliefVisibility,
)
from sofia.core.beliefs.store import BeliefReconsideration, ConvictionStore
from sofia.core.social.model import PrincipalContext
from sofia.core.social.principals import SPARKS_PRINCIPAL_ID

EvidenceVerifier = Callable[[str], bool]


def _aware(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


class BeliefsService:
    """Application boundary for one canonical `ConvictionStore`."""

    def __init__(
        self,
        store: ConvictionStore,
        *,
        evidence_verifier: EvidenceVerifier | None = None,
    ) -> None:
        if not isinstance(store, ConvictionStore):
            raise TypeError("store must be a ConvictionStore")
        if evidence_verifier is not None and not callable(evidence_verifier):
            raise TypeError("evidence_verifier must be callable or None")
        self._store = store
        self._evidence_verifier = evidence_verifier

    @property
    def store(self) -> ConvictionStore:
        return self._store

    def _require_owner(self, principal: PrincipalContext) -> str:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("an authenticated principal context is required")
        if principal.principal_id != SPARKS_PRINCIPAL_ID:
            raise PermissionError(
                "only the authenticated owner may modify held positions"
            )
        return principal.audience_id

    def _verify_evidence(
        self,
        evidence_refs: tuple[str, ...],
    ) -> None:
        if self._evidence_verifier is None:
            return
        for ref in evidence_refs:
            if not self._evidence_verifier(ref):
                raise ValueError(
                    f"evidence reference {ref!r} could not be verified "
                    "against its canonical source"
                )

    def _apply(
        self,
        *,
        holder: BeliefHolder,
        audience_id: str,
        topic: str,
        statement: str,
        stance: BeliefStance,
        confidence: float,
        reason: str,
        evidence_refs: tuple[str, ...],
        counterevidence_refs: tuple[str, ...],
        visibility: BeliefVisibility,
        expected_revision: int | None,
        change_kind: BeliefChangeKind,
        now: datetime,
    ) -> BeliefRecord:
        now = _aware(now, "belief timestamp")
        if stance is BeliefStance.WITHDRAWN:
            raise ValueError(
                "withdrawn convictions come only from the explicit "
                "withdraw entry point"
            )
        if change_kind is BeliefChangeKind.RETRACT:
            raise ValueError(
                "retraction comes only from the explicit withdraw entry point"
            )
        if change_kind is BeliefChangeKind.RECONSIDER:
            if len(counterevidence_refs) < 1:
                raise ValueError(
                    "a reconsidered result must record at least one "
                    "piece of counterevidence that prompted the review"
                )
        self._verify_evidence(evidence_refs)
        self._verify_evidence(counterevidence_refs)
        return self._store.hold(
            holder=holder,
            topic=topic,
            statement=statement,
            stance=stance,
            confidence=confidence,
            reason=reason,
            evidence_refs=evidence_refs,
            counterevidence_refs=counterevidence_refs,
            audience_id=audience_id,
            visibility=visibility,
            expected_revision=expected_revision,
            change_kind=change_kind,
            now=now,
        )

    def record_sofia_conviction(
        self,
        *,
        principal: PrincipalContext,
        topic: str,
        statement: str,
        stance: BeliefStance,
        confidence: float,
        reason: str,
        evidence_refs: tuple[str, ...],
        counterevidence_refs: tuple[str, ...] = (),
        visibility: BeliefVisibility = BeliefVisibility.OWNER_AUDIENCE_ONLY,
        expected_revision: int | None = None,
        now: datetime,
    ) -> BeliefRecord:
        if expected_revision is None:
            change_kind = BeliefChangeKind.ORIGIN
        else:
            change_kind = BeliefChangeKind.REVISE
        return self._apply(
            holder=BeliefHolder.SOFIA,
            audience_id=self._require_owner(principal),
            topic=topic,
            statement=statement,
            stance=stance,
            confidence=confidence,
            reason=reason,
            evidence_refs=evidence_refs,
            counterevidence_refs=counterevidence_refs,
            visibility=visibility,
            expected_revision=expected_revision,
            change_kind=change_kind,
            now=now,
        )

    def record_owner_position(
        self,
        *,
        principal: PrincipalContext,
        topic: str,
        statement: str,
        stance: BeliefStance,
        confidence: float,
        reason: str,
        evidence_refs: tuple[str, ...],
        counterevidence_refs: tuple[str, ...] = (),
        expected_revision: int | None = None,
        now: datetime,
    ) -> BeliefRecord:
        if expected_revision is None:
            change_kind = BeliefChangeKind.ORIGIN
        else:
            change_kind = BeliefChangeKind.REVISE
        return self._apply(
            holder=BeliefHolder.OWNER,
            audience_id=self._require_owner(principal),
            topic=topic,
            statement=statement,
            stance=stance,
            confidence=confidence,
            reason=reason,
            evidence_refs=evidence_refs,
            counterevidence_refs=counterevidence_refs,
            visibility=BeliefVisibility.OWNER_AUDIENCE_ONLY,
            expected_revision=expected_revision,
            change_kind=change_kind,
            now=now,
        )

    def reconsider(
        self,
        *,
        principal: PrincipalContext,
        topic: str,
        statement: str,
        stance: BeliefStance,
        confidence: float,
        reason: str,
        evidence_refs: tuple[str, ...],
        counterevidence_refs: tuple[str, ...],
        expected_revision: int,
        now: datetime,
    ) -> BeliefRecord:
        audience_id = self._require_owner(principal)
        current = self._require_current(topic, audience_id)
        record = self._apply(
            holder=current.holder,
            audience_id=audience_id,
            topic=topic,
            statement=statement,
            stance=stance,
            confidence=confidence,
            reason=reason,
            evidence_refs=evidence_refs,
            counterevidence_refs=counterevidence_refs,
            visibility=current.visibility,
            expected_revision=expected_revision,
            change_kind=BeliefChangeKind.RECONSIDER,
            now=now,
        )
        self._store.clear_reconsideration(record.conviction_id)
        return record

    def withdraw(
        self,
        *,
        principal: PrincipalContext,
        topic: str,
        reason: str,
        evidence_refs: tuple[str, ...],
        expected_revision: int,
        now: datetime,
    ) -> BeliefRecord:
        audience_id = self._require_owner(principal)
        current = self._require_current(topic, audience_id)
        now = _aware(now, "withdraw timestamp")
        self._verify_evidence(evidence_refs)
        return self._store.hold(
            holder=current.holder,
            topic=current.topic,
            statement=current.statement,
            stance=BeliefStance.WITHDRAWN,
            confidence=current.confidence,
            reason=reason,
            evidence_refs=current.evidence_refs,
            counterevidence_refs=(
                current.counterevidence_refs
                if len(evidence_refs) == 0
                else evidence_refs
            ),
            audience_id=audience_id,
            visibility=current.visibility,
            expected_revision=expected_revision,
            change_kind=BeliefChangeKind.RETRACT,
            now=now,
        )

    def _require_current(
        self,
        topic: str,
        audience_id: str,
    ) -> BeliefRecord:
        for holder in (BeliefHolder.SOFIA, BeliefHolder.OWNER):
            current = self._store.current(
                holder=holder,
                topic=topic,
                audience_id=audience_id,
            )
            if current is not None:
                return current
        raise ValueError(
            "no current conviction for this topic and audience"
        )

    def schedule_reconsideration(
        self,
        *,
        principal: PrincipalContext,
        topic: str,
        due_at: datetime,
        note: str,
    ) -> BeliefRecord:
        audience_id = self._require_owner(principal)
        current = self._require_current(topic, audience_id)
        due_at = _aware(due_at, "reconsideration due time")
        return self._store.schedule_reconsideration(
            current.conviction_id,
            due_at=due_at,
            note=note,
            expected_revision=current.revision,
        )

    def due_reconsiderations(
        self,
        *,
        now: datetime,
    ) -> tuple[BeliefReconsideration, ...]:
        return self._store.due_reconsiderations(now=_aware(now, "now"))

    def working_context(
        self,
        *,
        query_text: str,
        audience_id: str,
        owner_audience_id: str | None,
        limit: int = 5,
    ) -> tuple[BeliefMatch, ...]:
        return self._store.retrieve_relevant(
            query_text=query_text,
            audience_id=audience_id,
            owner_audience_id=owner_audience_id,
            limit=limit,
        )

    def listings(
        self,
        *,
        holder: BeliefHolder,
        audience_id: str,
    ) -> tuple[BeliefRecord, ...]:
        return self._store.current_for_holder(
            holder=holder,
            audience_id=audience_id,
        )
