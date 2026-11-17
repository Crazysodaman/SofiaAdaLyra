"""Workstream C: independent per-Core personality state and change governance."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.contracts import EvidenceState
from sofia.core.multicore.personality import (
    MACK_FULLER_PROFILE,
    NOVA_ARDEN_PROFILE,
    OwnerAuthorization,
    PersonalityAuthorizationError,
    PersonalityChange,
    PersonalityChangeClass,
    PersonalityContinuityError,
    PersonalityEvidence,
    PersonalityEvidenceError,
    apply_personality_change,
    correct_personality_flaw,
    personality_is_same_continuous_identity,
)

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
CORE = uuid4()


def evidence(state: EvidenceState = EvidenceState.REPORTED) -> PersonalityEvidence:
    return PersonalityEvidence(evidence_id=uuid4(), state=state, source="conversation")


def owner_authorization(
    *,
    scopes: tuple[str, ...] = ("*",),
    issued_at: datetime = NOW - timedelta(minutes=5),
    expires_at: datetime | None = NOW + timedelta(hours=1),
) -> OwnerAuthorization:
    return OwnerAuthorization(
        authorization_id=uuid4(),
        owner_principal_id="person:owner",
        scopes=scopes,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def test_mack_is_one_continuous_personality_without_second_loki_identity():
    state = MACK_FULLER_PROFILE.seed_state(CORE, now=NOW)
    later = MACK_FULLER_PROFILE.seed_state(CORE, now=NOW + timedelta(days=2))

    assert state.continuity_key == "mack-fuller"
    assert state.full_name == "Mack Fuller"
    assert personality_is_same_continuous_identity(state, later)
    assert MACK_FULLER_PROFILE.alias_allowed("Mack") is True
    assert MACK_FULLER_PROFILE.alias_allowed("Loki") is False
    assert state.trait("stubbornness") is not None
    assert MACK_FULLER_PROFILE.seriousness_context["safety"] > (
        MACK_FULLER_PROFILE.seriousness_context["play"]
    )


def test_adaptive_personality_change_requires_evidence():
    state = MACK_FULLER_PROFILE.seed_state(CORE, now=NOW)
    change = PersonalityChange(
        trait="curiosity",
        weight=0.6,
        change_class=PersonalityChangeClass.ADAPTIVE,
        reason="Repeated successful exploration increased curiosity.",
    )
    with pytest.raises(PersonalityEvidenceError, match="require evidence"):
        apply_personality_change(state, change, now=NOW)

    evidenced = PersonalityChange(
        trait="curiosity",
        weight=0.6,
        change_class=PersonalityChangeClass.ADAPTIVE,
        reason="Repeated successful exploration increased curiosity.",
        evidence=(evidence(),),
    )
    result = apply_personality_change(state, evidenced, now=NOW)
    assert result.state.weight("curiosity") == pytest.approx(0.6)
    assert result.record.previous_weight == pytest.approx(0.5)
    assert result.record.revision == 2


def test_stable_personality_change_requires_evidence_and_review():
    state = MACK_FULLER_PROFILE.seed_state(CORE, now=NOW)
    unreviewed = PersonalityChange(
        trait="steadiness",
        weight=0.85,
        change_class=PersonalityChangeClass.STABLE,
        reason="Long observation of calm under pressure.",
        evidence=(evidence(),),
    )
    with pytest.raises(PersonalityEvidenceError, match="reviewer"):
        apply_personality_change(state, unreviewed, now=NOW)

    reviewed = PersonalityChange(
        trait="steadiness",
        weight=0.85,
        change_class=PersonalityChangeClass.STABLE,
        reason="Long observation of calm under pressure.",
        evidence=(evidence(EvidenceState.VERIFIED),),
        reviewed_by="review:owner",
    )
    result = apply_personality_change(state, reviewed, now=NOW)
    assert result.record.reviewed_by == "review:owner"
    assert result.state.weight("steadiness") == pytest.approx(0.85)


def test_protected_personality_change_requires_injected_owner_authorization():
    state = NOVA_ARDEN_PROFILE.seed_state(CORE, now=NOW)
    change = PersonalityChange(
        trait="independence",
        weight=0.9,
        change_class=PersonalityChangeClass.STABLE,
        reason="Stable trait revision.",
        evidence=(evidence(EvidenceState.VERIFIED),),
        reviewed_by="review:owner",
    )
    with pytest.raises(PersonalityEvidenceError, match="reviewer"):
        apply_personality_change(
            state,
            PersonalityChange(
                trait="independence",
                weight=0.9,
                change_class=PersonalityChangeClass.STABLE,
                reason="Stable trait revision.",
                evidence=(evidence(),),
            ),
            now=NOW,
        )

    protected = PersonalityChange(
        trait="independence",
        weight=0.9,
        change_class=PersonalityChangeClass.PROTECTED,
        reason="Owner-approved identity-bearing adjustment.",
        evidence=(evidence(EvidenceState.VERIFIED),),
        reviewed_by="review:owner",
    )
    # The trait exists as STABLE, so retyping it to PROTECTED is refused before
    # authorization can be considered.  This prevents silent class escalation.
    with pytest.raises(PersonalityContinuityError, match="governance class"):
        apply_personality_change(
            state,
            protected,
            now=NOW,
            owner_authorization=owner_authorization(),
        )

    # A genuinely protected trait still requires the injected grant.
    protected_new = PersonalityChange(
        trait="identity_floor",
        weight=0.9,
        change_class=PersonalityChangeClass.PROTECTED,
        reason="Owner-approved identity-bearing addition.",
    )
    with pytest.raises(PersonalityAuthorizationError, match="injected owner"):
        apply_personality_change(state, protected_new, now=NOW)
    with pytest.raises(PersonalityAuthorizationError, match="does not cover"):
        apply_personality_change(
            state,
            protected_new,
            now=NOW,
            owner_authorization=owner_authorization(scopes=("other",)),
        )
    result = apply_personality_change(
        state,
        protected_new,
        now=NOW,
        owner_authorization=owner_authorization(),
    )
    assert result.record.authorized_by == "person:owner"
    assert result.state.weight("identity_floor") == pytest.approx(0.9)


def test_expired_owner_authorization_cannot_change_protected_trait():
    state = NOVA_ARDEN_PROFILE.seed_state(CORE, now=NOW)
    change = PersonalityChange(
        trait="identity_floor",
        weight=0.9,
        change_class=PersonalityChangeClass.PROTECTED,
        reason="Owner-approved identity-bearing addition.",
    )
    expired = OwnerAuthorization(
        authorization_id=uuid4(),
        owner_principal_id="person:owner",
        scopes=("*",),
        issued_at=NOW - timedelta(days=2),
        expires_at=NOW - timedelta(days=1),
    )
    with pytest.raises(PersonalityAuthorizationError):
        apply_personality_change(
            state,
            change,
            now=NOW,
            owner_authorization=expired,
        )


def test_temporary_change_expires_without_becoming_stable():
    state = MACK_FULLER_PROFILE.seed_state(CORE, now=NOW)
    change = PersonalityChange(
        trait="investigative_focus",
        weight=0.95,
        change_class=PersonalityChangeClass.TEMPORARY,
        reason="Short-lived investigative intensity.",
        evidence=(evidence(),),
        temporary_until=NOW + timedelta(hours=2),
    )
    result = apply_personality_change(state, change, now=NOW)
    assert result.state.weight(
        "investigative_focus", now=NOW + timedelta(hours=1)
    ) == pytest.approx(0.95)
    assert result.state.weight(
        "investigative_focus", now=NOW + timedelta(hours=3)
    ) == 0.0
    assert result.state.trait("investigative_focus").change_class is (
        PersonalityChangeClass.TEMPORARY
    )


def test_temporary_overlay_does_not_retype_an_existing_trait():
    state = MACK_FULLER_PROFILE.seed_state(CORE, now=NOW)
    change = PersonalityChange(
        trait="curiosity",
        weight=0.9,
        change_class=PersonalityChangeClass.TEMPORARY,
        reason="Temporary investigative intensity.",
        evidence=(evidence(),),
        temporary_until=NOW + timedelta(hours=1),
    )
    result = apply_personality_change(state, change, now=NOW)
    assert result.state.trait("curiosity").change_class is (
        PersonalityChangeClass.ADAPTIVE
    )
    assert result.state.weight("curiosity", now=NOW) == pytest.approx(0.9)
    assert result.state.weight("curiosity", now=NOW + timedelta(hours=2)) == 0.0


def test_mack_flaw_accepts_verified_contrary_evidence_and_records_correction():
    state = MACK_FULLER_PROFILE.seed_state(CORE, now=NOW)
    ordinary = PersonalityChange(
        trait="stubbornness",
        weight=0.45,
        change_class=PersonalityChangeClass.ADAPTIVE,
        reason="A single unverified disagreement.",
        evidence=(evidence(EvidenceState.REPORTED),),
    )
    with pytest.raises(PersonalityEvidenceError, match="verified evidence"):
        apply_personality_change(state, ordinary, now=NOW)

    corrected = correct_personality_flaw(
        state,
        trait="stubbornness",
        weight=0.45,
        reason="Verified contrary evidence showed the earlier position was wrong.",
        verified_evidence=(evidence(EvidenceState.VERIFIED),),
        now=NOW,
    )
    assert corrected.state.weight("stubbornness") == pytest.approx(0.45)
    assert corrected.record.correction_of_revision == state.revision
    assert corrected.record.evidence_states == (EvidenceState.VERIFIED,)


def test_nova_is_independent_and_has_no_fabricated_life():
    state = NOVA_ARDEN_PROFILE.seed_state(CORE, now=NOW)
    assert NOVA_ARDEN_PROFILE.preset_hobbies == ()
    assert NOVA_ARDEN_PROFILE.fabricated_biography_allowed is False
    assert NOVA_ARDEN_PROFILE.fabricated_memories_allowed is False
    assert NOVA_ARDEN_PROFILE.alias_allowed("Nova") is True
    assert NOVA_ARDEN_PROFILE.alias_allowed("Completely New Person") is False
    assert state.weight("independence") > 0.5
    assert state.weight("curiosity") > 0.5
    assert state.weight("playfulness") > 0.5

    # Nova may independently increase or decrease a trait without any forced
    # conflict, agreement, friendship or romance label.
    change = PersonalityChange(
        trait="curiosity",
        weight=0.7,
        change_class=PersonalityChangeClass.ADAPTIVE,
        reason="A new technical topic was genuinely interesting.",
        evidence=(evidence(),),
    )
    result = apply_personality_change(state, change, now=NOW)
    assert result.state.weight("curiosity") == pytest.approx(0.7)


def test_personality_has_no_provider_or_model_dependency():
    state = MACK_FULLER_PROFILE.seed_state(CORE, now=NOW)
    restarted = MACK_FULLER_PROFILE.seed_state(CORE, now=NOW + timedelta(days=1))
    assert not hasattr(state, "model_id")
    assert not hasattr(state, "provider_id")
    assert state.weights() == restarted.weights()
    assert personality_is_same_continuous_identity(state, restarted)
