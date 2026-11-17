from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.contracts import EvidenceState, PreferenceState
from sofia.core.multicore.learning import (
    DORMANCY,
    MulticoreLearningService,
)

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def test_nova_starts_with_no_established_hobbies_and_none_are_forced(canonical_state_path):
    nova = uuid4()
    learner = MulticoreLearningService(canonical_state_path, nova)

    assert learner.interests() == ()
    assert learner.established_interests() == ()
    assert learner.get_preference(nova, "hobby:pottery", domain="interest") is None
    assert learner.preferences() == ()
    assert learner.refresh(now=NOW + timedelta(days=999)) == ()


def test_single_enthusiasm_cannot_establish_a_preference(canonical_state_path):
    nova = uuid4()
    learner = MulticoreLearningService(canonical_state_path, nova)
    statement = "I think I might really love pottery!"
    preference = learner.observe_interest(
        nova,
        "hobby:pottery",
        stance=True,
        evidence=EvidenceState.REPORTED,
        source="conversation:local",
        statement=statement,
        observed_at=NOW,
    )
    assert preference.state is PreferenceState.TENTATIVE
    assert preference.confidence < 0.5
    assert preference.revision == 1
    assert len(preference.evidence) == 1

    repeated = learner.observe_interest(
        nova,
        "hobby:pottery",
        stance=True,
        evidence=EvidenceState.REPORTED,
        source="conversation:local",
        statement=statement,
        observed_at=NOW,
    )
    assert repeated.state is PreferenceState.TENTATIVE
    assert repeated.revision == 1
    assert repeated.evidence == preference.evidence
    assert len(learner.observations(nova, "hobby:pottery", domain="interest")) == 1


def test_verified_evidence_develops_and_establishes_a_preference(canonical_state_path):
    nova = uuid4()
    learner = MulticoreLearningService(canonical_state_path, nova)
    states = []
    for index in range(3):
        preference = learner.observe_interest(
            nova,
            "hobby:pottery",
            stance=True,
            evidence=EvidenceState.VERIFIED,
            source=f"session:{index}",
            statement=f"I completed pottery class {index} and want to continue.",
            observed_at=NOW + timedelta(days=index),
        )
        states.append(preference.state)
    assert states == [
        PreferenceState.TENTATIVE,
        PreferenceState.DEVELOPING,
        PreferenceState.ESTABLISHED,
    ]
    assert preference.confidence == pytest.approx(1.0)
    assert preference.revision == 3
    assert len(preference.evidence) == 3
    assert learner.established_interests() == (preference,)
    assert learner.interests() == (preference,)


def test_mack_can_revise_a_strongly_held_belief_and_keeps_the_correction(
    canonical_state_path,
):
    mack = uuid4()
    learner = MulticoreLearningService(canonical_state_path, mack)
    for index in range(3):
        established = learner.observe_belief(
            mack,
            "belief:strict-typing",
            stance=True,
            evidence=EvidenceState.VERIFIED,
            source=f"evidence:{index}",
            statement=f"Verified result {index} supports strict typing.",
            observed_at=NOW + timedelta(days=index),
        )
    assert established.state is PreferenceState.ESTABLISHED
    assert established.revision == 3

    revised = learner.observe_belief(
        mack,
        "belief:strict-typing",
        stance=False,
        evidence=EvidenceState.VERIFIED,
        source="evidence:corrected",
        statement="A verified production measurement contradicts the earlier result.",
        observed_at=NOW + timedelta(days=5),
    )
    assert revised.state is PreferenceState.REVISED
    assert revised.revision == 4
    assert len(revised.evidence) == 4
    assert len(learner.observations(mack, "belief:strict-typing", domain="belief")) == 4
    corrections = learner.corrections(mack, "belief:strict-typing", domain="belief")
    assert len(corrections) == 1
    assert corrections[0].prior_state is PreferenceState.ESTABLISHED
    assert corrections[0].new_state is PreferenceState.REVISED
    assert corrections[0].prior_stance is True
    assert corrections[0].new_stance is False
    assert corrections[0].revision == 4


def test_nova_can_gain_lose_and_regain_an_interest_only_through_evidence(
    canonical_state_path,
):
    nova = uuid4()
    learner = MulticoreLearningService(canonical_state_path, nova)
    last_at = NOW
    for index in range(3):
        last_at = NOW + timedelta(days=index)
        preference = learner.observe_interest(
            nova,
            "hobby:astronomy",
            stance=True,
            evidence=EvidenceState.VERIFIED,
            source=f"session:{index}",
            statement=f"I spent the evening observing stars, session {index}.",
            observed_at=last_at,
        )
    assert preference.state is PreferenceState.ESTABLISHED
    assert len(learner.established_interests()) == 1

    dwell = last_at + DORMANCY + timedelta(days=1)
    changed = learner.refresh(owner_core_id=nova, now=dwell)
    assert len(changed) == 1
    assert changed[0].state is PreferenceState.DORMANT
    assert learner.established_interests() == ()
    dormant_revision = changed[0].revision
    assert learner.refresh(owner_core_id=nova, now=dwell + timedelta(days=30)) == ()
    assert learner.get_preference(nova, "hobby:astronomy", domain="interest").revision == (
        dormant_revision
    )

    regained = learner.observe_interest(
        nova,
        "hobby:astronomy",
        stance=True,
        evidence=EvidenceState.VERIFIED,
        source="session:renewed",
        statement="I returned to the telescope tonight.",
        observed_at=dwell + timedelta(days=1),
    )
    assert regained.state is PreferenceState.ESTABLISHED
    assert len(learner.established_interests()) == 1

    revised = learner.observe_interest(
        nova,
        "hobby:astronomy",
        stance=False,
        evidence=EvidenceState.VERIFIED,
        source="session:changed",
        statement="I verified that the equipment now causes discomfort.",
        observed_at=dwell + timedelta(days=2),
    )
    assert revised.state is PreferenceState.REVISED
    assert len(learner.corrections(nova, "hobby:astronomy", domain="interest")) == 1


def test_preferences_are_owner_isolated(canonical_state_path):
    mack = uuid4()
    nova = uuid4()
    mack_learner = MulticoreLearningService(canonical_state_path, mack)
    nova_learner = MulticoreLearningService(canonical_state_path, nova)
    mack_learner.observe_preference(
        mack,
        "music:jazz",
        stance=True,
        evidence=EvidenceState.VERIFIED,
        source="session:m",
        statement="I keep returning to jazz recordings.",
        observed_at=NOW,
    )
    assert nova_learner.get_preference(nova, "music:jazz") is None
    assert nova_learner.preferences() == ()

    nova_learner.observe_preference(
        nova,
        "music:jazz",
        stance=False,
        evidence=EvidenceState.REPORTED,
        source="session:n",
        statement="A single comment said jazz is not for me.",
        observed_at=NOW,
    )
    assert nova_learner.get_preference(nova, "music:jazz").state is PreferenceState.TENTATIVE
    assert mack_learner.get_preference(mack, "music:jazz").state is PreferenceState.TENTATIVE
    with pytest.raises(PermissionError):
        mack_learner.get_preference(nova, "music:jazz")


def test_preference_and_belief_domains_remain_distinct(canonical_state_path):
    mack = uuid4()
    learner = MulticoreLearningService(canonical_state_path, mack)
    learner.observe_preference(
        mack,
        "topic:remote-work",
        stance=True,
        evidence=EvidenceState.VERIFIED,
        source="session:1",
        statement="I enjoy remote work.",
        observed_at=NOW,
    )
    learner.observe_belief(
        mack,
        "topic:remote-work",
        stance=False,
        evidence=EvidenceState.VERIFIED,
        source="session:2",
        statement="I believe remote work reduces team cohesion.",
        observed_at=NOW,
    )
    assert learner.get_preference(mack, "topic:remote-work", domain="preference").state is (
        PreferenceState.TENTATIVE
    )
    assert learner.get_preference(mack, "topic:remote-work", domain="belief").state is (
        PreferenceState.TENTATIVE
    )
    assert len(learner.preferences(mack)) == 2
    assert len(learner.preferences(mack, domain="preference")) == 1
    assert len(learner.preferences(mack, domain="belief")) == 1


def test_no_preference_state_exists_without_an_observation(canonical_state_path):
    nova = uuid4()
    learner = MulticoreLearningService(canonical_state_path, nova)
    assert learner.preferences() == ()
    assert learner.get_preference(nova, "hobby:unknown", domain="interest") is None
    with pytest.raises(ValueError):
        learner.observe_interest(
            nova,
            "",
            stance=True,
            evidence=EvidenceState.VERIFIED,
            source="session",
            statement="empty subject",
            observed_at=NOW,
        )
    with pytest.raises(TypeError):
        learner.observe_interest(
            nova,
            "hobby:pottery",
            stance="yes",
            evidence=EvidenceState.VERIFIED,
            source="session",
            statement="invalid stance",
            observed_at=NOW,
        )
    assert learner.preferences() == ()
