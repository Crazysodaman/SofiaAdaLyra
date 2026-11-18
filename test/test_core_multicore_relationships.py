"""Workstream C: asymmetric, evidence-based relationships between Cores."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.contracts import (
    EvidenceState,
    RelationshipDimensions,
    RelationshipRecord,
)
from sofia.core.multicore.relationships import (
    NO_RELATIONSHIP_AUTHORITY,
    RelationshipAuthorityBoundary,
    RelationshipChange,
    RelationshipChangeKind,
    RelationshipError,
    RelationshipEvidenceError,
    RelationshipIsolationError,
    RelationshipLedger,
    RelationshipStatus,
)

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)


def change(
    kind: RelationshipChangeKind,
    *,
    evidence: tuple | None = None,
    evidence_state: EvidenceState = EvidenceState.VERIFIED,
    **kwargs,
) -> RelationshipChange:
    return RelationshipChange(
        kind=kind,
        reason="Recorded peer conduct and verified outcomes.",
        evidence=(uuid4(),) if evidence is None else evidence,
        evidence_state=evidence_state,
        **kwargs,
    )


def test_relationships_are_asymmetric_and_independently_owned():
    mack = uuid4()
    nova = uuid4()
    mack_ledger = RelationshipLedger(mack)
    nova_ledger = RelationshipLedger(nova)

    mack_view = mack_ledger.apply(
        nova,
        change(
            RelationshipChangeKind.DEVELOP,
            familiarity_delta=0.8,
            reliability_delta=0.7,
            shared_experience=True,
        ),
        now=NOW,
    )
    nova_view = nova_ledger.apply(
        mack,
        change(
            RelationshipChangeKind.DEVELOP,
            familiarity_delta=0.2,
            technical_trust_delta=0.1,
            shared_experience=True,
        ),
        now=NOW,
    )

    assert mack_view.owner_core_id == mack
    assert mack_view.peer_id == nova
    assert nova_view.owner_core_id == nova
    assert nova_view.peer_id == mack
    assert mack_view.dimensions.familiarity == pytest.approx(0.8)
    assert nova_view.dimensions.familiarity == pytest.approx(0.2)
    assert mack_view != nova_view


def test_no_preset_friendship_rivalry_romance_or_family_state():
    owner = uuid4()
    peer = uuid4()
    ledger = RelationshipLedger(owner)
    assert ledger.current(peer) is None
    assert ledger.status(peer) is None
    baseline = RelationshipDimensions()
    assert baseline.familiarity == 0.0
    assert baseline.reliability == 0.0
    assert baseline.technical_trust == 0.0
    assert baseline.boundary_respect == 0.0
    assert baseline.conversational_comfort == 0.0
    assert baseline.respect == 0.0
    assert baseline.shared_experiences == 0
    assert baseline.unresolved_disagreements == 0
    assert {kind.value for kind in RelationshipChangeKind} == {
        "develop", "improve", "deteriorate", "pause", "recover",
    }
    for forbidden in ("friendship", "rivalry", "romance", "family"):
        assert not hasattr(RelationshipChangeKind, forbidden.upper())


def test_relationship_changes_require_non_speculative_evidence():
    with pytest.raises(RelationshipEvidenceError, match="require evidence"):
        RelationshipChange(
            kind=RelationshipChangeKind.DEVELOP,
            reason="Unsupported claim.",
            evidence=(),
            familiarity_delta=0.1,
        )
    with pytest.raises(RelationshipEvidenceError, match="speculative"):
        change(
            RelationshipChangeKind.DEVELOP,
            evidence_state=EvidenceState.SPECULATIVE,
            familiarity_delta=0.1,
        )


def test_develop_improve_deteriorate_pause_and_recover():
    owner = uuid4()
    peer = uuid4()
    ledger = RelationshipLedger(owner)

    with pytest.raises(RelationshipError, match="cannot begin paused"):
        ledger.apply(peer, change(RelationshipChangeKind.PAUSE), now=NOW)
    with pytest.raises(RelationshipError, match="cannot begin paused"):
        ledger.apply(peer, change(RelationshipChangeKind.RECOVER), now=NOW)

    developed = ledger.apply(
        peer,
        change(
            RelationshipChangeKind.DEVELOP,
            familiarity_delta=0.3,
            conversational_comfort_delta=0.2,
            shared_experience=True,
        ),
        now=NOW,
    )
    assert isinstance(developed, RelationshipRecord)
    assert developed.revision == 1
    assert developed.dimensions.shared_experiences == 1

    improved = ledger.apply(
        peer,
        change(
            RelationshipChangeKind.IMPROVE,
            reliability_delta=0.4,
            boundary_respect_delta=0.3,
        ),
        now=NOW + timedelta(hours=1),
    )
    assert improved.dimensions.reliability == pytest.approx(0.4)
    assert improved.revision == 2

    deteriorated = ledger.apply(
        peer,
        change(
            RelationshipChangeKind.DETERIORATE,
            technical_trust_delta=-0.3,
            disagreement=True,
        ),
        now=NOW + timedelta(hours=2),
    )
    assert deteriorated.dimensions.unresolved_disagreements == 1
    assert deteriorated.dimensions.technical_trust == 0.0

    paused = ledger.apply(
        peer,
        change(RelationshipChangeKind.PAUSE),
        now=NOW + timedelta(hours=3),
    )
    assert ledger.status(peer) is RelationshipStatus.PAUSED
    with pytest.raises(RelationshipError, match="only an evidence-backed recover"):
        ledger.apply(
            peer,
            change(RelationshipChangeKind.IMPROVE, respect_delta=0.2),
            now=NOW + timedelta(hours=4),
        )

    recovered = ledger.apply(
        peer,
        change(RelationshipChangeKind.RECOVER),
        now=NOW + timedelta(hours=5),
    )
    assert ledger.status(peer) is RelationshipStatus.ACTIVE
    assert recovered.revision == 5

    resolved = ledger.apply(
        peer,
        change(
            RelationshipChangeKind.IMPROVE,
            boundary_respect_delta=0.2,
            disagreement_resolved=True,
        ),
        now=NOW + timedelta(hours=6),
    )
    assert resolved.dimensions.unresolved_disagreements == 0
    assert paused.dimensions == deteriorated.dimensions


def test_private_reflections_are_isolated_to_the_owning_core():
    mack = uuid4()
    nova = uuid4()
    ledger = RelationshipLedger(mack)
    record = ledger.apply(
        nova,
        change(
            RelationshipChangeKind.DEVELOP,
            familiarity_delta=0.4,
            shared_experience=True,
        ),
        now=NOW,
    )
    reflection = ledger.reflect(
        nova,
        content="I am not sure yet whether the candour is reliable or only style.",
        evidence=(uuid4(),),
        now=NOW,
    )
    assert reflection.owner_core_id == mack
    assert reflection.security.value == "private"
    assert ledger.reflections(nova, requesting_core_id=mack) == (reflection,)
    with pytest.raises(RelationshipIsolationError, match="another Core"):
        ledger.reflections(nova, requesting_core_id=nova)
    assert reflection.content not in record.evidence
    assert record.dimensions == RelationshipRecord(
        owner_core_id=mack,
        peer_id=nova,
        dimensions=record.dimensions,
        evidence=record.evidence,
        updated_at=record.updated_at,
        revision=record.revision,
    ).dimensions
    assert not hasattr(record, "reflection")
    assert not hasattr(record, "private_reflection")


def test_relationships_grant_no_authority_memory_fleet_or_execution():
    boundary = NO_RELATIONSHIP_AUTHORITY
    assert isinstance(boundary, RelationshipAuthorityBoundary)
    assert boundary.authority is False
    assert boundary.memory_access is False
    assert boundary.fleet_access is False
    assert boundary.execution_access is False
    assert boundary.protected_state_access is False
    assert boundary.identity_access is False
    with pytest.raises(ValueError, match="cannot grant"):
        RelationshipAuthorityBoundary(memory_access=True)
    ledger = RelationshipLedger(uuid4())
    assert ledger.authority_boundary is NO_RELATIONSHIP_AUTHORITY


def test_nova_may_agree_or_disagree_without_forced_conflict():
    nova = uuid4()
    peer = uuid4()
    ledger = RelationshipLedger(nova)
    ledger.apply(
        peer,
        change(
            RelationshipChangeKind.DEVELOP,
            familiarity_delta=0.2,
            reliability_delta=0.2,
            shared_experience=True,
        ),
        now=NOW,
    )
    agreed = ledger.apply(
        peer,
        change(
            RelationshipChangeKind.IMPROVE,
            respect_delta=0.3,
            conversational_comfort_delta=0.2,
        ),
        now=NOW + timedelta(hours=1),
    )
    assert ledger.status(peer) is RelationshipStatus.ACTIVE
    assert agreed.dimensions.respect == pytest.approx(0.3)

    disagreed = ledger.apply(
        peer,
        change(
            RelationshipChangeKind.DETERIORATE,
            technical_trust_delta=-0.2,
            disagreement=True,
        ),
        now=NOW + timedelta(hours=2),
    )
    assert ledger.status(peer) is RelationshipStatus.ACTIVE
    assert disagreed.dimensions.unresolved_disagreements == 1
    assert not hasattr(disagreed, "friendship")
    assert not hasattr(disagreed, "rivalry")
    assert not hasattr(disagreed, "romance")


def test_development_of_one_core_does_not_rewrite_the_other_core():
    mack = uuid4()
    nova = uuid4()
    mack_ledger = RelationshipLedger(mack)
    nova_ledger = RelationshipLedger(nova)
    mack_ledger.apply(
        nova,
        change(
            RelationshipChangeKind.DEVELOP,
            familiarity_delta=0.5,
            shared_experience=True,
        ),
        now=NOW,
    )
    assert nova_ledger.current(mack) is None
    nova_ledger.apply(
        mack,
        change(
            RelationshipChangeKind.DEVELOP,
            familiarity_delta=0.1,
            shared_experience=True,
        ),
        now=NOW,
    )
    assert mack_ledger.current(nova).dimensions.familiarity == pytest.approx(0.5)
    assert nova_ledger.current(mack).dimensions.familiarity == pytest.approx(0.1)
    assert mack_ledger.history(nova)[0].owner_core_id == mack
    assert nova_ledger.history(mack)[0].owner_core_id == nova
