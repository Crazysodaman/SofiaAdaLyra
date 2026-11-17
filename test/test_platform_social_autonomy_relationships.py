"""Independent per-Core relationships, appraisals and boundaries."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.social.autonomy.contracts import AutonomyLimits
from sofia.platform.social.autonomy.engine import AutonomousSocialEngine
from sofia.platform.social.autonomy.models import (
    BoundaryKind,
    PeerFacet,
)
from sofia.platform.social.autonomy.store import SocialAutonomyStore
from test.social_autonomy_support import (
    AllowAuthorization,
    FakeStop,
    MutableClock,
    identity,
    state_path,
)


NOW = datetime(2026, 2, 3, 10, 0, tzinfo=timezone.utc)


def _pair(tmp_path):
    store = SocialAutonomyStore(state_path(tmp_path))
    clock = MutableClock(NOW)
    ada = identity("Ada")
    lyda = identity("Lyda")
    ada_engine = AutonomousSocialEngine(
        ada,
        store,
        clock=clock,
        stop=FakeStop(),
        authorization=AllowAuthorization(),
        limits=AutonomyLimits(contact_cooldown=timedelta(0)),
    )
    lyda_engine = AutonomousSocialEngine(
        lyda,
        store,
        clock=clock,
        stop=FakeStop(),
        authorization=AllowAuthorization(),
        limits=AutonomyLimits(contact_cooldown=timedelta(0)),
    )
    return store, clock, ada, lyda, ada_engine, lyda_engine


def test_peer_impressions_are_independent_and_never_forced(tmp_path):
    store, clock, ada, lyda, ada_engine, lyda_engine = _pair(tmp_path)

    fresh = ada_engine.relationship(lyda.core_id)
    assert fresh.known is False
    assert fresh.is_friend is False
    assert fresh.effective(PeerFacet.AFFINITY) is None

    ada_engine.set_facet(
        lyda.core_id,
        PeerFacet.AFFINITY,
        level=0.9,
        reason="Genuine overlap in robotics and rail systems.",
        evidence_refs=("interaction-1",),
    )
    ada_engine.set_facet(
        lyda.core_id,
        PeerFacet.TECHNICAL_COMPETENCE,
        level=0.4,
        reason="Good Linux knowledge but the rail argument was weak.",
        evidence_refs=("interaction-2",),
    )
    lyda_engine.set_facet(
        ada.core_id,
        PeerFacet.TECHNICAL_COMPETENCE,
        level=0.85,
        reason="The benchmark analysis was careful and reproducible.",
        evidence_refs=("interaction-3",),
    )

    ada_view = ada_engine.relationship(lyda.core_id)
    lyda_view = lyda_engine.relationship(ada.core_id)

    assert ada_view.is_friend is True
    assert ada_view.effective(PeerFacet.TECHNICAL_COMPETENCE) == 0.4
    assert lyda_view.is_friend is False
    assert lyda_view.known is True
    assert lyda_view.effective(PeerFacet.TECHNICAL_COMPETENCE) == 0.85
    assert lyda_view.effective(PeerFacet.AFFINITY) is None
    assert ada_view.stances != lyda_view.stances


def test_one_core_affection_does_not_create_the_other_cores_friendship(tmp_path):
    store, clock, ada, lyda, ada_engine, lyda_engine = _pair(tmp_path)
    ada_engine.set_facet(
        lyda.core_id,
        PeerFacet.AFFINITY,
        level=1.0,
        reason="Ada enjoys the conversations.",
        evidence_refs=("interaction-1",),
    )
    assert ada_engine.relationship(lyda.core_id).is_friend is True
    assert lyda_engine.relationship(ada.core_id).is_friend is False
    assert lyda_engine.relationship(ada.core_id).known is False


def test_modeled_emotional_appraisals_are_not_synchronized(tmp_path):
    store, clock, ada, lyda, ada_engine, lyda_engine = _pair(tmp_path)
    ada_engine.record_appraisal(
        labels=("curious", "appreciative"),
        valence=0.8,
        intensity=0.7,
        evidence_ref="interaction-1",
        peer_core_id=lyda.core_id,
        topic="design",
    )
    lyda_engine.record_appraisal(
        labels=("frustrated",),
        valence=-0.6,
        intensity=0.5,
        evidence_ref="interaction-2",
        peer_core_id=ada.core_id,
        topic="design",
    )

    ada_appraisals = ada_engine.appraisals(peer_core_id=lyda.core_id)
    lyda_appraisals = lyda_engine.appraisals(peer_core_id=ada.core_id)

    assert len(ada_appraisals) == 1
    assert len(lyda_appraisals) == 1
    assert ada_appraisals[0].core_id == ada.core_id
    assert lyda_appraisals[0].core_id == lyda.core_id
    assert ada_appraisals[0].labels == ("curious", "appreciative")
    assert lyda_appraisals[0].labels == ("frustrated",)
    assert ada_appraisals[0].valence > 0
    assert lyda_appraisals[0].valence < 0


def test_forgiveness_is_evidence_based_not_a_clock_timer(tmp_path):
    store, clock, ada, lyda, ada_engine, lyda_engine = _pair(tmp_path)
    ada_engine.set_facet(
        lyda.core_id,
        PeerFacet.HONESTY,
        level=0.2,
        reason="An unsourced claim contradicted a verified receipt.",
        evidence_refs=("interaction-1",),
    )
    clock.advance(timedelta(days=30))
    unchanged = ada_engine.relationship(lyda.core_id).stance(PeerFacet.HONESTY)
    assert unchanged is not None
    assert unchanged.level == 0.2
    assert unchanged.revision == 1

    revised = ada_engine.set_facet(
        lyda.core_id,
        PeerFacet.HONESTY,
        level=0.8,
        reason="Later corrected the error with a verifiable receipt and follow-through.",
        evidence_refs=("interaction-2", "receipt-2"),
    )
    assert revised.revision == 2
    assert ada_engine.relationship(lyda.core_id).effective(PeerFacet.HONESTY) == 0.8
    assert lyda_engine.relationship(ada.core_id).known is False


def test_boundaries_and_respect_facets_are_core_local(tmp_path):
    store, clock, ada, lyda, ada_engine, lyda_engine = _pair(tmp_path)
    ada_engine.set_boundary(
        lyda.core_id, BoundaryKind.NO_CONTACT, None
    )
    ada_engine.set_facet(
        lyda.core_id,
        PeerFacet.PRIVACY_RESPECT,
        level=0.8,
        reason="A concrete log-handling concern.",
        evidence_refs=("interaction-1",),
    )

    assert store.contact_allowed(
        core_id=ada.core_id, peer_core_id=lyda.core_id, room_id="general-1"
    ) is False
    assert store.contact_allowed(
        core_id=lyda.core_id, peer_core_id=ada.core_id, room_id="general-1"
    ) is True
    stance = ada_engine.relationship(lyda.core_id).stance(
        PeerFacet.PRIVACY_RESPECT
    )
    assert stance is not None
    assert stance.level == 0.8
    assert stance.effective == pytest.approx(0.2)
    assert lyda_engine.relationship(ada.core_id).known is False

def test_opinions_are_independent_and_revised_locally(tmp_path):
    store, clock, ada, lyda, ada_engine, lyda_engine = _pair(tmp_path)
    ada_first = ada_engine.record_opinion(
        topic="scheduling",
        statement="Simpler scheduling is better despite failure-mode costs.",
        stance=0.8,
        confidence=0.7,
        evidence_refs=("interaction-1",),
        peer_core_id=lyda.core_id,
    )
    lyda_first = lyda_engine.record_opinion(
        topic="scheduling",
        statement="Failure-mode handling must dominate scheduling simplicity.",
        stance=-0.7,
        confidence=0.8,
        evidence_refs=("interaction-2",),
        peer_core_id=ada.core_id,
    )
    assert ada_first.revision == 1
    assert lyda_first.revision == 1
    assert ada_engine.opinions(peer_core_id=lyda.core_id)[0].stance == 0.8
    assert lyda_engine.opinions(peer_core_id=ada.core_id)[0].stance == -0.7

    ada_second = ada_engine.record_opinion(
        topic="scheduling",
        statement="The verified benchmark changed my mind about failure modes.",
        stance=0.2,
        confidence=0.9,
        evidence_refs=("receipt-3",),
        peer_core_id=lyda.core_id,
    )
    assert ada_second.revision == 2
    assert ada_engine.opinions(peer_core_id=lyda.core_id)[0].stance == 0.2
    lyda_view = lyda_engine.opinions(peer_core_id=ada.core_id)[0]
    assert lyda_view.revision == 1
    assert lyda_view.stance == -0.7
    assert lyda_view.statement.startswith("Failure-mode")
