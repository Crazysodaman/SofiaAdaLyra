"""Evidence separation, correction and withdrawal for autonomous social state."""
from datetime import datetime, timezone
from uuid import uuid4

from sofia.platform.social.autonomy.engine import AutonomousSocialEngine
from sofia.platform.social.autonomy.evidence import (
    EvidenceCategory,
    EvidenceStatus,
)
from sofia.platform.social.autonomy.store import SocialAutonomyStore
from test.social_autonomy_support import (
    AllowAuthorization,
    FakeStop,
    MutableClock,
    identity,
    state_path,
)


NOW = datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc)


def _engine(tmp_path):
    store = SocialAutonomyStore(state_path(tmp_path))
    core = identity("Ada")
    engine = AutonomousSocialEngine(
        core,
        store,
        clock=MutableClock(NOW),
        stop=FakeStop(),
        authorization=AllowAuthorization(),
    )
    return store, core, engine


def test_categories_remain_distinct_and_only_verified_outcomes_are_verified(tmp_path):
    store, core, engine = _engine(tmp_path)
    peer = uuid4()
    observed = engine.record_evidence(
        category=EvidenceCategory.OBSERVED,
        claim="I saw the message in the shared room.",
        evidence_ref="interaction-1",
        peer_core_id=peer,
    )
    self_report = engine.record_evidence(
        category=EvidenceCategory.SELF_REPORT,
        claim="The peer says it finished the review.",
        evidence_ref="self-report-1",
        peer_core_id=peer,
    )
    peer_claim = engine.record_evidence(
        category=EvidenceCategory.PEER_CLAIM,
        claim="The peer claims its patch is safe.",
        evidence_ref="peer-claim-1",
        peer_core_id=peer,
    )
    verified = engine.record_evidence(
        category=EvidenceCategory.VERIFIED_OUTCOME,
        claim="Independent test receipt shows the patch passes.",
        evidence_ref="receipt-1",
        peer_core_id=peer,
    )
    interpretation = engine.record_evidence(
        category=EvidenceCategory.INTERPRETATION,
        claim="I think the peer seems rushed.",
        evidence_ref="interpretation-1",
        peer_core_id=peer,
    )
    uncertainty = engine.record_evidence(
        category=EvidenceCategory.UNCERTAINTY,
        claim="I do not know whether the benchmark is representative.",
        evidence_ref="uncertainty-1",
        peer_core_id=peer,
    )

    assert observed.is_firsthand and not observed.is_claim
    assert self_report.is_claim and not self_report.is_verified
    assert peer_claim.is_claim and not peer_claim.is_verified
    assert verified.is_verified
    assert not interpretation.is_verified
    assert not uncertainty.is_verified
    assert {
        item.category
        for item in engine.active_evidence(peer_core_id=peer)
    } == {
        EvidenceCategory.OBSERVED,
        EvidenceCategory.SELF_REPORT,
        EvidenceCategory.PEER_CLAIM,
        EvidenceCategory.VERIFIED_OUTCOME,
        EvidenceCategory.INTERPRETATION,
        EvidenceCategory.UNCERTAINTY,
    }
    assert store.evidence(core.core_id, verified.evidence_id) == verified


def test_correction_supersedes_only_the_local_claim_and_keeps_history(tmp_path):
    store, core, engine = _engine(tmp_path)
    peer = uuid4()
    original = engine.record_evidence(
        category=EvidenceCategory.PEER_CLAIM,
        claim="The peer says the deployment succeeded.",
        evidence_ref="peer-claim-2",
        peer_core_id=peer,
    )
    correction = engine.correct_evidence(
        original.evidence_id,
        claim="The deployment receipt actually shows a rollback.",
        evidence_ref="correction-2",
    )

    assert correction.category is EvidenceCategory.CORRECTION
    assert correction.supersedes == original.evidence_id
    assert correction.status is EvidenceStatus.ACTIVE
    stored = store.evidence(core.core_id, original.evidence_id)
    assert stored.status is EvidenceStatus.CORRECTED
    assert stored.claim == "The peer says the deployment succeeded."
    assert engine.active_evidence(category=EvidenceCategory.PEER_CLAIM) == ()
    assert engine.active_evidence(category=EvidenceCategory.CORRECTION) == (
        correction,
    )


def test_withdrawal_removes_only_the_withdrawn_evidence_category(tmp_path):
    store, core, engine = _engine(tmp_path)
    peer = uuid4()
    verified = engine.record_evidence(
        category=EvidenceCategory.VERIFIED_OUTCOME,
        claim="A receipt confirmed the milestone.",
        evidence_ref="receipt-3",
        peer_core_id=peer,
    )
    other = engine.record_evidence(
        category=EvidenceCategory.OBSERVED,
        claim="The peer was present in the room.",
        evidence_ref="interaction-3",
        peer_core_id=peer,
    )
    withdrawal = engine.withdraw_evidence(
        verified.evidence_id,
        reason="The source receipt was later found to be stale.",
        evidence_ref="withdrawal-3",
    )

    assert withdrawal.category is EvidenceCategory.WITHDRAWAL
    assert withdrawal.supersedes == verified.evidence_id
    stored = store.evidence(core.core_id, verified.evidence_id)
    assert stored.status is EvidenceStatus.WITHDRAWN
    assert not stored.is_verified
    assert engine.active_evidence(category=EvidenceCategory.VERIFIED_OUTCOME) == ()
    assert engine.active_evidence(category=EvidenceCategory.WITHDRAWAL) == (
        withdrawal,
    )
    assert other in engine.active_evidence(peer_core_id=peer)
