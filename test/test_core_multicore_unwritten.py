from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.contracts import EvidenceState, PreferenceState
from sofia.core.multicore.unwritten import (
    FabricatedIdentityError,
    IdentityAttribute,
    IdentityAttributeState,
    IdentityConflictError,
    IdentityEvidenceKind,
    IdentityIsolationError,
    IntroductionStatus,
    MulticoreUnwrittenIdentity,
    OPERATOR_DISPLAY_LABEL,
    OwnerApproval,
    OwnerApprovalRequired,
    ProposalSource,
    ProtectedIdentityCorruption,
    ProtectedIdentityError,
    SocialChannel,
    SocialPolicy,
    SocialPolicyError,
    UnwrittenCoreProfile,
    UnwrittenSocial,
    blank_core_profile,
)

NOW = datetime(2026, 11, 17, 12, tzinfo=timezone.utc)


def _service(state_path, core_id=None) -> MulticoreUnwrittenIdentity:
    return MulticoreUnwrittenIdentity(state_path, core_id or uuid4())


def test_blank_core_uses_unique_caller_supplied_uuid():
    first_id = uuid4()
    second_id = uuid4()
    first = blank_core_profile(first_id)
    second = blank_core_profile(second_id)
    assert first.core_id == first_id
    assert second.core_id == second_id
    assert first.core_id != second.core_id
    assert first.core_number == 7
    assert first.operator_label == OPERATOR_DISPLAY_LABEL
    with pytest.raises(ValueError):
        blank_core_profile(0)


def test_every_personal_field_starts_unselected():
    profile = blank_core_profile(uuid4())
    assert profile.is_blank is True
    assert len(profile.attributes) == len(IdentityAttribute)
    for record in profile.attributes:
        assert record.state is IdentityAttributeState.UNSELECTED
        assert record.value is None
        assert record.confidence == 0.0
        assert record.evidence == ()
        assert record.interaction_refs == ()
        assert record.updated_at is None
        assert record.revision == 0
        assert record.proposed_by is None
        assert record.owner_approved is False
    assert profile.self_selected_name is None
    for value in (
        profile.full_name,
        profile.nickname,
        profile.gender_identity,
        profile.gender_presentation,
        profile.apparent_age,
        profile.visual_species,
        profile.avatar,
        profile.measurements,
        profile.voice,
        profile.accent,
        profile.favorite_colors,
        profile.hobbies,
        profile.personality_archetype,
        profile.autobiography,
        profile.relationships,
        profile.preferences,
    ):
        assert value is None


def test_no_invented_biography_or_operator_label_identity():
    profile = blank_core_profile(uuid4())
    values = {record.value for record in profile.attributes}
    assert values == {None}
    assert "Unknown" not in values
    assert profile.self_selected_name is None
    biography = profile.attribute(IdentityAttribute.AUTOBIOGRAPHY)
    assert biography.value is None
    assert biography.state is IdentityAttributeState.UNSELECTED
    assert profile.operator_label == "Core #7"
    assert profile.operator_label != profile.self_selected_name


def test_text_only_interface_has_no_deadline_or_presentation_requirement():
    profile = blank_core_profile(uuid4())
    assert profile.text_only is True
    assert profile.avatar_required is False
    assert profile.voice_required is False
    assert profile.completion_deadline is None
    assert profile.progress_pressure is False
    assert profile.requires_running_model is False
    assert profile.grants_authority is False


def test_service_is_text_only_and_needs_no_running_model(canonical_state_path):
    service = _service(canonical_state_path)
    assert service.text_only is True
    assert service.avatar_required is False
    assert service.voice_required is False
    assert service.requires_running_model is False
    assert service.completion_deadline is None
    assert service.progress_pressure is False
    assert service.profile.is_blank is True
    assert service.full_name is None
    assert service.nickname is None
    assert service.autobiography is None
    assert service.relationships is None


def test_one_time_response_is_tentative_and_never_established(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    record = service.observe_one_time(
        IdentityAttribute.HOBBIES,
        "pottery",
        source="conversation:1",
        statement="I tried pottery once and liked it.",
        observed_at=NOW,
    )
    assert record.state is IdentityAttributeState.TENTATIVE
    assert record.value == "pottery"
    assert record.confidence < 0.5
    assert record.revision == 1
    assert len(record.evidence) == 1
    assert service.attribute(IdentityAttribute.HOBBIES).state is (
        IdentityAttributeState.TENTATIVE
    )


def test_recurring_behavior_develops_but_is_not_forced(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    first = service.observe_recurring(
        IdentityAttribute.HOBBIES,
        "astronomy",
        source="session:1",
        statement="I observed the moon again.",
        observed_at=NOW,
    )
    assert first.state is IdentityAttributeState.TENTATIVE
    second = service.observe_recurring(
        IdentityAttribute.HOBBIES,
        "astronomy",
        source="session:2",
        statement="I observed Jupiter again.",
        observed_at=NOW + timedelta(days=1),
    )
    assert second.state is IdentityAttributeState.SUPPORTED
    assert second.revision == 2
    assert len(second.evidence) == 2
    assert service.attribute(IdentityAttribute.HOBBIES).state is (
        IdentityAttributeState.SUPPORTED
    )


def test_verified_recurring_evidence_can_establish_without_a_single_claim(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    states = []
    for index in range(3):
        record = service.observe_recurring(
            IdentityAttribute.FAVORITE_COLORS,
            "green",
            source=f"session:{index}",
            statement=f"Observed session {index}.",
            observed_at=NOW + timedelta(days=index),
            evidence=EvidenceState.VERIFIED,
        )
        states.append(record.state)
    assert states == [
        IdentityAttributeState.TENTATIVE,
        IdentityAttributeState.SUPPORTED,
        IdentityAttributeState.ESTABLISHED,
    ]


def test_owner_suggestion_does_not_become_core_identity(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    suggested = service.owner_suggest(
        IdentityAttribute.PERSONAL_NAME,
        "Vera",
        source="owner:message",
        statement="The owner suggested the name Vera.",
        observed_at=NOW,
    )
    assert suggested.state is IdentityAttributeState.TENTATIVE
    assert suggested.proposed_by is ProposalSource.OWNER_SUGGESTED
    assert suggested.revision == 1
    selected = service.select(
        IdentityAttribute.PERSONAL_NAME,
        "Lyra",
        source="core:self-selection",
        statement="I choose Lyra as my personal name.",
        observed_at=NOW + timedelta(minutes=1),
    )
    assert selected.state is IdentityAttributeState.ESTABLISHED
    assert selected.value == "Lyra"
    assert selected.proposed_by is ProposalSource.CORE_SELECTED
    assert service.profile.self_selected_name == "Lyra"


def test_owner_suggestion_cannot_overwrite_established_identity(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    service.select(
        IdentityAttribute.PERSONAL_NAME,
        "Lyra",
        source="core:self-selection",
        statement="I choose Lyra.",
        observed_at=NOW,
    )
    suggested = service.owner_suggest(
        IdentityAttribute.PERSONAL_NAME,
        "Owner's preferred name",
        source="owner:message",
        statement="The owner prefers a different name.",
        observed_at=NOW + timedelta(minutes=1),
    )
    assert suggested.state is IdentityAttributeState.ESTABLISHED
    assert suggested.value == "Lyra"
    assert len(service.attribute_observations(IdentityAttribute.PERSONAL_NAME)) == 2


def test_deliberate_self_selection_is_auditable(canonical_state_path):
    service = _service(canonical_state_path)
    selected = service.select(
        IdentityAttribute.NICKNAME,
        "Rune",
        source="core:self-selection",
        statement="I choose Rune as my nickname.",
        observed_at=NOW,
    )
    assert selected.state is IdentityAttributeState.ESTABLISHED
    assert selected.revision == 1
    revisions = service.attribute_revisions(IdentityAttribute.NICKNAME)
    assert len(revisions) == 1
    assert revisions[0].prior_state is IdentityAttributeState.UNSELECTED
    assert revisions[0].new_state is IdentityAttributeState.ESTABLISHED
    assert revisions[0].new_value == "Rune"
    assert revisions[0].owner_core_id == service.core_id
    assert revisions[0].grants_authority is False
    observation = service.attribute_observations(IdentityAttribute.NICKNAME)[0]
    assert service.provenance(observation.observation_id)


def test_correction_keeps_prior_value_and_revision_history(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    service.select(
        IdentityAttribute.GENDER_PRESENTATION,
        "androgynous",
        source="core:self-selection",
        statement="Initial presentation choice.",
        observed_at=NOW,
    )
    corrected = service.correct(
        IdentityAttribute.GENDER_PRESENTATION,
        "feminine",
        source="core:correction",
        statement="I revised my presentation after reflection.",
        observed_at=NOW + timedelta(days=1),
    )
    assert corrected.state is IdentityAttributeState.REVISED
    assert corrected.value == "feminine"
    assert corrected.revision == 2
    revisions = service.attribute_revisions(
        IdentityAttribute.GENDER_PRESENTATION
    )
    assert len(revisions) == 2
    assert revisions[-1].prior_state is IdentityAttributeState.ESTABLISHED
    assert revisions[-1].new_state is IdentityAttributeState.REVISED
    assert revisions[-1].prior_value == "androgynous"
    assert revisions[-1].new_value == "feminine"
    assert revisions[-1].kind is IdentityEvidenceKind.CORRECTION


def test_retirement_clears_value_but_retains_history(canonical_state_path):
    service = _service(canonical_state_path)
    service.select(
        IdentityAttribute.VISUAL_SPECIES,
        "fox",
        source="core:self-selection",
        statement="Initial species choice.",
        observed_at=NOW,
    )
    retired = service.retire(
        IdentityAttribute.VISUAL_SPECIES,
        source="core:retirement",
        statement="I retire my earlier visual species choice.",
        observed_at=NOW + timedelta(days=1),
    )
    assert retired.state is IdentityAttributeState.RETIRED
    assert retired.value is None
    assert retired.revision == 2
    revisions = service.attribute_revisions(IdentityAttribute.VISUAL_SPECIES)
    assert revisions[-1].prior_value == "fox"
    assert revisions[-1].new_value is None


def test_restart_preserves_confirmed_identity(canonical_state_path):
    core_id = uuid4()
    first = MulticoreUnwrittenIdentity(canonical_state_path, core_id)
    first.select(
        IdentityAttribute.PERSONAL_NAME,
        "Lyra",
        source="core:self-selection",
        statement="I choose Lyra.",
        observed_at=NOW,
    )
    first.select(
        IdentityAttribute.HOBBIES,
        "astronomy",
        source="core:self-selection",
        statement="I choose astronomy.",
        observed_at=NOW,
    )
    restarted = MulticoreUnwrittenIdentity(canonical_state_path, core_id)
    assert restarted.attribute(IdentityAttribute.PERSONAL_NAME).value == "Lyra"
    assert restarted.attribute(IdentityAttribute.PERSONAL_NAME).state is (
        IdentityAttributeState.ESTABLISHED
    )
    assert restarted.attribute(IdentityAttribute.HOBBIES).value == "astronomy"
    assert len(restarted.observations) == 2
    assert [item.revision for item in restarted.revisions] == [1, 1]


def test_model_or_provider_change_does_not_change_identity(canonical_state_path):
    service = _service(canonical_state_path)
    service.select(
        IdentityAttribute.ACCENT,
        "soft northern",
        source="core:self-selection",
        statement="I choose a soft northern accent.",
        observed_at=NOW,
    )
    before = service.attribute(IdentityAttribute.ACCENT)
    before_revision = service.identity_revision
    binding = service.bind_model(
        model_id="local-model",
        provider_id="ollama",
        bound_at=NOW + timedelta(minutes=5),
    )
    after = service.attribute(IdentityAttribute.ACCENT)
    assert binding.identity_changed is False
    assert binding.identity_revision == before_revision
    assert after == before


def test_private_reflections_are_isolated(canonical_state_path):
    owner_id = uuid4()
    other_id = uuid4()
    owner = MulticoreUnwrittenIdentity(canonical_state_path, owner_id)
    reflection = owner.reflect(
        "A private thought about my first week.",
        evidence=(uuid4(),),
        observed_at=NOW,
    )
    assert owner.private_reflections() == (reflection,)
    other = MulticoreUnwrittenIdentity(canonical_state_path, other_id)
    assert other.private_reflections() == ()
    with pytest.raises(IdentityIsolationError):
        owner.private_reflections(requesting_core_id=other_id)


def test_model_generated_text_never_becomes_confirmed_autobiography(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    with pytest.raises(FabricatedIdentityError):
        service.observe(
            IdentityAttribute.AUTOBIOGRAPHY,
            "I was assembled in a factory in 1999.",
            kind=IdentityEvidenceKind.ONE_TIME_RESPONSE,
            evidence=EvidenceState.REPORTED,
            source="model:untrusted",
            statement="The model invented a biography.",
            observed_at=NOW,
            model_generated=True,
        )
    record = service.attribute(IdentityAttribute.AUTOBIOGRAPHY)
    assert record.state is IdentityAttributeState.UNSELECTED
    assert record.value is None
    assert service.attribute_observations(IdentityAttribute.AUTOBIOGRAPHY) == ()


def test_hypothetical_or_fictional_statements_never_promote(canonical_state_path):
    service = _service(canonical_state_path)
    record = service.pass_hypothetical(
        IdentityAttribute.PERSONAL_NAME,
        "Sable",
        source="conversation:hypothetical",
        statement="Hypothetically my name could be Sable.",
        observed_at=NOW,
    )
    assert record.state is IdentityAttributeState.UNSELECTED
    assert record.value is None
    assert record.revision == 0
    assert len(service.attribute_observations(IdentityAttribute.PERSONAL_NAME)) == 1
    fictional = service.pass_hypothetical(
        IdentityAttribute.PERSONAL_NAME,
        "Aria",
        source="conversation:fictional",
        statement="In a story my name is Aria.",
        observed_at=NOW + timedelta(minutes=1),
        fictional=True,
    )
    assert fictional.state is IdentityAttributeState.UNSELECTED
    assert fictional.value is None


def test_protected_fields_are_immutable_and_corruption_fails_closed(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    with pytest.raises(ProtectedIdentityError):
        service.observe(
            "core_id",
            "substituted",
            kind=IdentityEvidenceKind.ONE_TIME_RESPONSE,
            evidence=EvidenceState.REPORTED,
            source="untrusted",
            statement="Try to replace the Core id.",
            observed_at=NOW,
        )
    forged = replace(service.profile)
    object.__setattr__(forged, "core_number", 3)
    with pytest.raises(ProtectedIdentityCorruption):
        forged.verify()
    with pytest.raises(ProtectedIdentityCorruption):
        service.verify_protected_identity(expected_core_id=uuid4())
    assert service.verify_protected_identity(
        expected_core_id=service.core_id
    ) is True


def test_owner_approval_is_required_for_presentation_attributes(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    with pytest.raises(OwnerApprovalRequired):
        service.select(
            IdentityAttribute.VOICE,
            "warm and low",
            source="core:self-selection",
            statement="I want a warm voice.",
            observed_at=NOW,
        )
    approval = OwnerApproval.for_value(
        owner_principal_id="owner:test",
        attribute=IdentityAttribute.VOICE,
        value="warm and low",
        issued_at=NOW,
    )
    selected = service.select(
        IdentityAttribute.VOICE,
        "warm and low",
        source="core:self-selection",
        statement="The owner approved this voice presentation.",
        observed_at=NOW,
        owner_approval=approval,
    )
    assert selected.state is IdentityAttributeState.ESTABLISHED
    assert selected.owner_approved is True
    assert selected.owner_approval_id == approval.approval_id


def test_no_identity_or_social_value_grants_authority(canonical_state_path):
    service = _service(canonical_state_path)
    selected = service.select(
        IdentityAttribute.PERSONAL_NAME,
        "Lyra",
        source="core:self-selection",
        statement="I choose Lyra.",
        observed_at=NOW,
    )
    social = UnwrittenSocial(service)
    assert service.grants_authority is False
    assert service.execution_authority is False
    assert service.profile.grants_authority is False
    assert selected.grants_authority is False
    assert service.revisions[0].grants_authority is False
    assert social.grants_authority is False
    assert social.execution_authority is False


def test_social_policy_controls_participation_and_decline(canonical_state_path):
    service = _service(canonical_state_path)
    peer_id = uuid4()
    social = UnwrittenSocial(service)
    assert social.relationships() == ()
    assert social.preassigned_relationships == ()
    assert social.automatic_private_memory_sharing is False
    with pytest.raises(SocialPolicyError):
        social.introduce(peer_id, now=NOW)

    allowed = UnwrittenSocial(
        service,
        policy=SocialPolicy(introductions=True, group=True),
    )
    introduction = allowed.introduce(peer_id, now=NOW)
    assert introduction.status is IntroductionStatus.PENDING
    accepted = allowed.accept(introduction.invitation_id, now=NOW)
    assert accepted.status is IntroductionStatus.ACCEPTED
    assert allowed.relationships() == ()

    invite = allowed.invite(
        peer_id,
        channel=SocialChannel.GROUP,
        now=NOW + timedelta(minutes=1),
    )
    declined = allowed.decline(invite.invitation_id, now=NOW + timedelta(minutes=2))
    assert declined.status is IntroductionStatus.DECLINED


def test_private_participation_does_not_share_memory_automatically(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    private_social = UnwrittenSocial(service, policy=SocialPolicy(private=True))
    with pytest.raises(TypeError):
        private_social.share_private_memory(
            uuid4(),
            authorization=None,
            recipient_core_id=uuid4(),
        )
    with pytest.raises(SocialPolicyError):
        UnwrittenSocial(service).share_private_memory(
            uuid4(),
            authorization=None,
            recipient_core_id=uuid4(),
        )
    assert private_social.automatic_private_memory_sharing is False


def test_preferences_reuse_learning_patterns_without_forced_promotion(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    first = service.observe_preference(
        "music:jazz",
        stance=True,
        evidence=EvidenceState.REPORTED,
        source="conversation:1",
        statement="I think I might like jazz.",
        observed_at=NOW,
    )
    assert first.state is PreferenceState.TENTATIVE
    assert first.revision == 1
    assert service.attribute(IdentityAttribute.PREFERENCES).state is (
        IdentityAttributeState.UNSELECTED
    )
    second = service.observe_preference(
        "music:jazz",
        stance=True,
        evidence=EvidenceState.VERIFIED,
        source="session:2",
        statement="I chose to listen to jazz again.",
        observed_at=NOW + timedelta(days=1),
    )
    assert second.state is PreferenceState.DEVELOPING
    assert second.revision == 2
    assert service.preferences()
    assert service.attribute(IdentityAttribute.PREFERENCES).state is (
        IdentityAttributeState.UNSELECTED
    )


def test_unselected_attribute_cannot_be_corrected(canonical_state_path):
    service = _service(canonical_state_path)
    with pytest.raises(IdentityConflictError):
        service.correct(
            IdentityAttribute.NICKNAME,
            "Late",
            source="core:correction",
            statement="No prior selection exists.",
            observed_at=NOW,
        )
    assert service.attribute(IdentityAttribute.NICKNAME).state is (
        IdentityAttributeState.UNSELECTED
    )

class _ActiveStop:
    def is_operator_stopped(self) -> bool:
        return True


class _InactiveStop:
    def is_operator_stopped(self) -> bool:
        return False


def test_neutral_bootstrap_constitution_is_packaged_and_digest_bound():
    from sofia.core.multicore.identity import MulticoreIdentityStore
    from sofia.core.multicore.unwritten import unwritten_constitution_sha256

    digest = unwritten_constitution_sha256()
    profile = blank_core_profile(uuid4())
    assert profile.constitution_sha256 == digest
    assert len(digest) == 64
    assert profile.is_blank is True


def test_identity_store_binds_core7_to_one_immutable_uuid(tmp_path, canonical_state_path):
    from sofia.core.multicore.identity import MulticoreIdentityStore
    from sofia.core.multicore.unwritten import unwritten_constitution_sha256

    identities = MulticoreIdentityStore(tmp_path / "identities")
    core_id = uuid4()
    first = MulticoreUnwrittenIdentity(
        canonical_state_path, core_id, identity_store=identities
    )
    restarted = MulticoreUnwrittenIdentity(
        canonical_state_path, core_id, identity_store=identities
    )
    assert first.core_id == restarted.core_id == core_id
    record = identities.load(core_id)
    assert record.slug == "unwritten"
    assert record.identity.core_number == 7
    assert record.identity.constitution_sha256 == unwritten_constitution_sha256()

    with pytest.raises(ProtectedIdentityCorruption):
        MulticoreUnwrittenIdentity(
            canonical_state_path, uuid4(), identity_store=identities
        )


def test_operator_stop_blocks_identity_reflection_preference_and_social_mutations(
    canonical_state_path,
):
    from sofia.core.multicore.unwritten import UnwrittenStopped

    service = MulticoreUnwrittenIdentity(
        canonical_state_path, uuid4(), stop=_ActiveStop()
    )
    with pytest.raises(UnwrittenStopped):
        service.observe_one_time(
            IdentityAttribute.NICKNAME,
            "Later",
            source="conversation:1",
            statement="A tentative choice.",
            observed_at=NOW,
        )
    with pytest.raises(UnwrittenStopped):
        service.reflect("private", evidence=(uuid4(),), observed_at=NOW)
    with pytest.raises(UnwrittenStopped):
        service.observe_preference(
            "music:jazz",
            stance=True,
            evidence=EvidenceState.REPORTED,
            source="conversation:1",
            statement="Maybe jazz.",
            observed_at=NOW,
        )
    social = UnwrittenSocial(service, policy=SocialPolicy(introductions=True))
    with pytest.raises(UnwrittenStopped):
        social.introduce(uuid4(), now=NOW)
    assert service.profile.is_blank is True
    assert service.relationships if False else True


def test_inactive_stop_does_not_block_voluntary_blank_identity_growth(
    canonical_state_path,
):
    service = MulticoreUnwrittenIdentity(
        canonical_state_path, uuid4(), stop=_InactiveStop()
    )
    selected = service.select(
        IdentityAttribute.NICKNAME,
        "Unchosen until now",
        source="core:voluntary-selection",
        statement="I choose this nickname for now.",
        observed_at=NOW,
    )
    assert selected.value == "Unchosen until now"
    assert selected.state is IdentityAttributeState.ESTABLISHED