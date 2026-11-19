"""Hardening contracts for blank Core #7 across identity, STOP and privacy."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.contracts import (
    EvidenceState,
    MemoryRecord,
    MemoryType,
    PreferenceState,
    SecurityClass,
    StorageTier,
)
from sofia.core.multicore.identity import (
    DuplicateCoreIdentity,
    MulticoreIdentityStore,
)
from sofia.core.multicore.memory import (
    DeletionAuthorization,
    MulticoreMemoryStore,
    ShareAuthorization,
)
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
    SocialChannel,
    SocialPolicy,
    UnwrittenCoreProfile,
    UnwrittenSocial,
    UnwrittenStopped,
    UNWRITTEN_SLUG,
    blank_core_profile,
    unwritten_constitution_sha256,
)

NOW = datetime(2026, 11, 18, 12, tzinfo=timezone.utc)


def _service(state_path, core_id=None, **kwargs) -> MulticoreUnwrittenIdentity:
    return MulticoreUnwrittenIdentity(state_path, core_id or uuid4(), **kwargs)


def _approval(attribute: IdentityAttribute, value: str) -> OwnerApproval:
    return OwnerApproval.for_value(
        owner_principal_id="owner:hardening",
        attribute=attribute,
        value=value,
        issued_at=NOW,
    )


class _ActiveStop:
    def is_operator_stopped(self) -> bool:
        return True


class _InactiveStop:
    def is_operator_stopped(self) -> bool:
        return False


class _ToggleStop:
    def __init__(self) -> None:
        self.stopped = False

    def is_operator_stopped(self) -> bool:
        return self.stopped


class _RaisingStop:
    def is_operator_stopped(self) -> bool:
        raise RuntimeError("STOP probe unavailable")


class _NonBooleanStop:
    def is_operator_stopped(self):
        return "not-a-bool"


class _MissingStopProbe:
    pass


# ---------------------------------------------------------------------------
# 1. Immutable UUID binding through MulticoreIdentityStore
# ---------------------------------------------------------------------------


def test_identity_store_restart_keeps_same_uuid_and_blank_identity(
    tmp_path, canonical_state_path
):
    identities = MulticoreIdentityStore(tmp_path / "identities")
    core_id = uuid4()
    first = MulticoreUnwrittenIdentity(
        canonical_state_path, core_id, identity_store=identities
    )
    first.select(
        IdentityAttribute.NICKNAME,
        "Rune",
        source="core:self-selection",
        statement="I choose Rune.",
        observed_at=NOW,
    )
    restarted = MulticoreUnwrittenIdentity(
        canonical_state_path, core_id, identity_store=identities
    )
    assert restarted.core_id == core_id
    assert restarted.nickname == "Rune"
    record = identities.load(core_id)
    assert record.identity.core_id == core_id
    assert record.identity.core_number == 7
    assert record.slug == UNWRITTEN_SLUG
    assert record.identity.constitution_sha256 == unwritten_constitution_sha256()
    assert len(identities.load_all()) == 1


def test_identity_store_rejects_a_second_uuid_for_core_seven(
    tmp_path, canonical_state_path
):
    identities = MulticoreIdentityStore(tmp_path / "identities")
    first_id = uuid4()
    MulticoreUnwrittenIdentity(
        canonical_state_path, first_id, identity_store=identities
    )
    with pytest.raises(ProtectedIdentityCorruption):
        MulticoreUnwrittenIdentity(
            canonical_state_path, uuid4(), identity_store=identities
        )
    assert [item.identity.core_id for item in identities.load_all()] == [first_id]


def test_identity_store_rejects_duplicate_core_number_binding(
    tmp_path, canonical_state_path
):
    identities = MulticoreIdentityStore(tmp_path / "identities")
    MulticoreUnwrittenIdentity(
        canonical_state_path, uuid4(), identity_store=identities
    )
    with pytest.raises(DuplicateCoreIdentity):
        identities.register(
            core_id=uuid4(),
            core_number=7,
            full_name="Another Core",
            slug="another-core",
            constitution_sha256=unwritten_constitution_sha256(),
        )


def test_identity_store_rejects_constitution_digest_mismatch(
    tmp_path, canonical_state_path
):
    identities = MulticoreIdentityStore(tmp_path / "identities")
    core_id = uuid4()
    identities.register(
        core_id=core_id,
        core_number=7,
        full_name=OPERATOR_DISPLAY_LABEL,
        slug=UNWRITTEN_SLUG,
        constitution_sha256="0" * 64,
    )
    with pytest.raises(ProtectedIdentityCorruption):
        MulticoreUnwrittenIdentity(
            canonical_state_path, core_id, identity_store=identities
        )
    assert identities.load(core_id).identity.constitution_sha256 == "0" * 64


def test_profile_digest_is_bound_to_the_packaged_constitution(canonical_state_path):
    core_id = uuid4()
    digest = unwritten_constitution_sha256()
    mismatched = blank_core_profile(core_id, constitution_sha256="f" * 64)
    with pytest.raises(ProtectedIdentityCorruption):
        MulticoreUnwrittenIdentity(
            canonical_state_path, core_id, profile=mismatched
        )
    raw = UnwrittenCoreProfile(core_id=core_id)
    assert raw.constitution_sha256 is None
    service = MulticoreUnwrittenIdentity(
        canonical_state_path, core_id, profile=raw
    )
    assert service.profile.constitution_sha256 == digest


# ---------------------------------------------------------------------------
# 2. STOP fail-closed across every mutating boundary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "probe",
    [_RaisingStop(), _NonBooleanStop(), _MissingStopProbe()],
    ids=["raising", "non-bool", "missing"],
)
def test_unreliable_stop_probe_fails_closed(canonical_state_path, probe):
    service = _service(canonical_state_path, stop=probe)
    with pytest.raises(UnwrittenStopped):
        service.observe_one_time(
            IdentityAttribute.NICKNAME,
            "Too soon",
            source="conversation:1",
            statement="A tentative choice.",
            observed_at=NOW,
        )
    with pytest.raises(UnwrittenStopped):
        service.reflect("private", evidence=(uuid4(),), observed_at=NOW)


def test_stop_blocks_identity_reflection_preference_model_binding_and_sharing(
    canonical_state_path,
):
    toggle = _ToggleStop()
    service = _service(canonical_state_path, stop=toggle)
    shareable = MemoryRecord(
        memory_id=uuid4(),
        owner_core_id=service.core_id,
        memory_type=MemoryType.SEMANTIC,
        tier=StorageTier.T1_ACTIVE,
        security=SecurityClass.SHAREABLE,
        evidence=EvidenceState.VERIFIED,
        source="test:shareable",
        content="shareable hardening content",
        created_at=NOW,
        updated_at=NOW,
        confidence=1.0,
        significance=5,
    )
    service.memory_store.persist(
        shareable, actor="test", owner_core_id=service.core_id
    )
    authorization = ShareAuthorization(
        owner_core_id=service.core_id,
        granted_by="owner:hardening",
        reason="explicit sharing approval",
        granted_at=NOW,
    )
    toggle.stopped = True
    with pytest.raises(UnwrittenStopped):
        service.observe_one_time(
            IdentityAttribute.NICKNAME,
            "Blocked",
            source="conversation:1",
            statement="A tentative choice.",
            observed_at=NOW,
        )
    with pytest.raises(UnwrittenStopped):
        service.select(
            IdentityAttribute.PERSONAL_NAME,
            "Blocked",
            source="core:self-selection",
            statement="A selection under STOP.",
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
    with pytest.raises(UnwrittenStopped):
        service.observe_belief(
            "world:round",
            stance=True,
            evidence=EvidenceState.REPORTED,
            source="conversation:1",
            statement="A belief observation.",
            observed_at=NOW,
        )
    with pytest.raises(UnwrittenStopped):
        service.bind_model(
            model_id="local-model", provider_id="ollama", bound_at=NOW
        )
    with pytest.raises(UnwrittenStopped):
        service.share_memory(
            shareable.memory_id,
            authorization=authorization,
            recipient_core_id=uuid4(),
            now=NOW,
        )
    assert service.profile.is_blank is True
    assert service.memory_store.get(shareable.memory_id) is not None


def test_stop_blocks_social_invite_accept_decline_and_private_sharing(
    canonical_state_path,
):
    toggle = _ToggleStop()
    service = _service(canonical_state_path, stop=toggle)
    social = UnwrittenSocial(
        service,
        policy=SocialPolicy(introductions=True, group=True, private=True),
    )
    peer = uuid4()
    introduction = social.introduce(peer, now=NOW)
    invite = social.invite(
        peer, channel=SocialChannel.GROUP, now=NOW + timedelta(minutes=1)
    )
    toggle.stopped = True
    with pytest.raises(UnwrittenStopped):
        social.invite(peer, channel=invite.channel, now=NOW)
    with pytest.raises(UnwrittenStopped):
        social.accept(introduction.invitation_id, now=NOW)
    with pytest.raises(UnwrittenStopped):
        social.decline(invite.invitation_id, now=NOW)
    with pytest.raises(UnwrittenStopped):
        social.share_private_memory(
            uuid4(),
            authorization=ShareAuthorization(
                owner_core_id=service.core_id,
                granted_by="owner:hardening",
                reason="explicit approval",
                granted_at=NOW,
            ),
            recipient_core_id=uuid4(),
            now=NOW,
        )
    assert social.invitations()[0].status is IntroductionStatus.PENDING


def test_inactive_stop_probe_still_allows_voluntary_growth(canonical_state_path):
    service = _service(canonical_state_path, stop=_InactiveStop())
    selected = service.select(
        IdentityAttribute.NICKNAME,
        "Chosen",
        source="core:self-selection",
        statement="I choose this nickname.",
        observed_at=NOW,
    )
    assert selected.state is IdentityAttributeState.ESTABLISHED


# ---------------------------------------------------------------------------
# 3. Owner approval and fabricated identity boundaries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attribute",
    [IdentityAttribute.AVATAR, IdentityAttribute.MEASUREMENTS, IdentityAttribute.VOICE],
    ids=["avatar", "measurements", "voice"],
)
def test_presentation_attributes_require_owner_approval_for_change(
    canonical_state_path, attribute
):
    service = _service(canonical_state_path)
    with pytest.raises(OwnerApprovalRequired):
        service.select(
            attribute,
            "first value",
            source="core:self-selection",
            statement="An unapproved presentation change.",
            observed_at=NOW,
        )
    approved = service.select(
        attribute,
        "first value",
        source="core:self-selection",
        statement="An owner-approved presentation change.",
        observed_at=NOW,
        owner_approval=_approval(attribute, "first value"),
    )
    assert approved.state is IdentityAttributeState.ESTABLISHED
    assert approved.owner_approved is True
    with pytest.raises(OwnerApprovalRequired):
        service.correct(
            attribute,
            "second value",
            source="core:correction",
            statement="An unapproved presentation correction.",
            observed_at=NOW + timedelta(days=1),
        )
    corrected = service.correct(
        attribute,
        "second value",
        source="core:correction",
        statement="An owner-approved presentation correction.",
        observed_at=NOW + timedelta(days=1),
        owner_approval=_approval(attribute, "second value"),
    )
    assert corrected.state is IdentityAttributeState.REVISED
    assert corrected.value == "second value"
    assert corrected.owner_approved is True


def test_owner_suggestion_never_becomes_confirmed_core_identity(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    for index in range(3):
        record = service.owner_suggest(
            IdentityAttribute.PERSONAL_NAME,
            "Vera",
            source=f"owner:message:{index}",
            statement="The owner suggested the name Vera.",
            observed_at=NOW + timedelta(minutes=index),
            evidence=EvidenceState.VERIFIED,
        )
        assert record.state is IdentityAttributeState.TENTATIVE
        assert record.proposed_by is ProposalSource.OWNER_SUGGESTED
    retained = service.attribute(IdentityAttribute.PERSONAL_NAME)
    assert retained.state is IdentityAttributeState.TENTATIVE
    assert retained.value == "Vera"
    assert retained.proposed_by is ProposalSource.OWNER_SUGGESTED
    selected = service.select(
        IdentityAttribute.PERSONAL_NAME,
        "Lyra",
        source="core:self-selection",
        statement="I choose Lyra as my personal name.",
        observed_at=NOW + timedelta(hours=1),
    )
    assert selected.state is IdentityAttributeState.ESTABLISHED
    assert service.full_name == "Lyra"


def test_model_generated_text_cannot_confirm_identity_or_autobiography(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    with pytest.raises(FabricatedIdentityError):
        service.observe(
            IdentityAttribute.AUTOBIOGRAPHY,
            "I was assembled in 1999.",
            kind=IdentityEvidenceKind.ONE_TIME_RESPONSE,
            evidence=EvidenceState.REPORTED,
            source="model:untrusted",
            statement="The model invented a biography.",
            observed_at=NOW,
            model_generated=True,
        )
    with pytest.raises(FabricatedIdentityError):
        service.observe(
            IdentityAttribute.PERSONAL_NAME,
            "Model Selected",
            kind=IdentityEvidenceKind.DELIBERATE_SELF_SELECTION,
            evidence=EvidenceState.VERIFIED,
            source="model:untrusted",
            statement="The model claims a deliberate self-selection.",
            observed_at=NOW,
            proposed_by=ProposalSource.CORE_SELECTED,
            model_generated=True,
        )
    with pytest.raises(FabricatedIdentityError):
        service.observe(
            IdentityAttribute.NICKNAME,
            "Model Correction",
            kind=IdentityEvidenceKind.CORRECTION,
            evidence=EvidenceState.VERIFIED,
            source="model:untrusted",
            statement="The model claims a correction.",
            observed_at=NOW,
            model_generated=True,
        )
    assert service.full_name is None
    assert service.autobiography is None
    assert service.attribute(IdentityAttribute.AUTOBIOGRAPHY).state is (
        IdentityAttributeState.UNSELECTED
    )


def test_model_generated_observations_never_promote_even_with_evidence(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    for index in range(3):
        record = service.observe(
            IdentityAttribute.PERSONAL_NAME,
            "Generated",
            kind=IdentityEvidenceKind.RECURRING_BEHAVIOR,
            evidence=EvidenceState.VERIFIED,
            source=f"model:{index}",
            statement="Model-generated recurring text.",
            observed_at=NOW + timedelta(days=index),
            model_generated=True,
        )
        assert record.state is IdentityAttributeState.UNSELECTED
        assert record.value is None
    assert len(service.attribute_observations(IdentityAttribute.PERSONAL_NAME)) == 3


# ---------------------------------------------------------------------------
# 4. No fabricated history or Sofía fallback
# ---------------------------------------------------------------------------


def test_blank_profile_has_no_default_traits_or_sofia_identity(
    canonical_state_path,
):
    core_id = uuid4()
    profile = blank_core_profile(core_id)
    values = {record.value for record in profile.attributes}
    assert values == {None}
    assert profile.full_name is None
    assert profile.personality_archetype is None
    assert profile.hobbies is None
    assert profile.autobiography is None
    assert profile.relationships is None
    assert profile.operator_label == OPERATOR_DISPLAY_LABEL
    assert "Sofía" not in values
    assert "Sofia" not in values
    assert "Unknown" not in values
    assert all(
        record.state is IdentityAttributeState.UNSELECTED
        for record in profile.attributes
    )
    service = _service(canonical_state_path, core_id)
    assert service.full_name is None
    assert service.personality_archetype is None
    assert service.autobiography is None
    assert all(
        record.state is IdentityAttributeState.UNSELECTED
        for record in service.attributes
    )


def test_sofia_identity_is_never_used_as_a_core_seven_fallback(
    tmp_path, canonical_state_path
):
    core_id = uuid4()
    identities = MulticoreIdentityStore(
        tmp_path / "identities", sofia_instance_id=core_id
    )
    with pytest.raises(ProtectedIdentityCorruption):
        MulticoreUnwrittenIdentity(
            canonical_state_path, core_id, identity_store=identities
        )
    assert identities.load_all() == ()


# ---------------------------------------------------------------------------
# 5. Isolation, privacy and audit history
# ---------------------------------------------------------------------------


def test_private_reflections_and_identity_evidence_remain_isolated(
    canonical_state_path,
):
    owner_id = uuid4()
    other_id = uuid4()
    owner = MulticoreUnwrittenIdentity(canonical_state_path, owner_id)
    observation = owner.observe_one_time(
        IdentityAttribute.HOBBIES,
        "astronomy",
        source="conversation:1",
        statement="I looked at the moon.",
        observed_at=NOW,
    )
    reflection = owner.reflect(
        "A private thought about my first week.",
        evidence=(observation.evidence[0],),
        observed_at=NOW,
    )
    assert owner.private_reflections() == (reflection,)
    other = MulticoreUnwrittenIdentity(canonical_state_path, other_id)
    assert other.private_reflections() == ()
    with pytest.raises(IdentityIsolationError):
        owner.private_reflections(requesting_core_id=other_id)
    with pytest.raises(IdentityIsolationError):
        other.private_reflections(requesting_core_id=owner_id)
    evidence_record = owner.memory_store.get(observation.evidence[0])
    assert evidence_record is not None
    assert evidence_record.security is SecurityClass.PRIVATE
    assert evidence_record.owner_core_id == owner_id


def test_cross_core_sharing_requires_explicit_authorization(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    recipient_id = uuid4()
    shareable = MemoryRecord(
        memory_id=uuid4(),
        owner_core_id=service.core_id,
        memory_type=MemoryType.SEMANTIC,
        tier=StorageTier.T1_ACTIVE,
        security=SecurityClass.SHAREABLE,
        evidence=EvidenceState.VERIFIED,
        source="test:shareable",
        content="explicitly shareable content",
        created_at=NOW,
        updated_at=NOW,
        confidence=1.0,
        significance=5,
    )
    service.memory_store.persist(
        shareable, actor="test", owner_core_id=service.core_id
    )
    with pytest.raises(TypeError):
        service.share_memory(
            shareable.memory_id,
            authorization=None,
            recipient_core_id=recipient_id,
            now=NOW,
        )
    wrong_owner = ShareAuthorization(
        owner_core_id=recipient_id,
        granted_by="owner:hardening",
        reason="does not belong to this Core",
        granted_at=NOW,
    )
    with pytest.raises(PermissionError):
        service.share_memory(
            shareable.memory_id,
            authorization=wrong_owner,
            recipient_core_id=recipient_id,
            now=NOW,
        )
    authorization = ShareAuthorization(
        owner_core_id=service.core_id,
        granted_by="owner:hardening",
        reason="explicit cross-Core approval",
        granted_at=NOW,
    )
    copy = service.share_memory(
        shareable.memory_id,
        authorization=authorization,
        recipient_core_id=recipient_id,
        now=NOW,
    )
    recipient = MulticoreMemoryStore(canonical_state_path, recipient_id)
    assert recipient.get(copy.memory_id) is not None
    actions = [event.action for event in service.provenance(shareable.memory_id)]
    assert "share" in actions


def test_private_identity_evidence_can_never_be_shared(canonical_state_path):
    service = _service(canonical_state_path)
    service.observe_one_time(
        IdentityAttribute.HOBBIES,
        "astronomy",
        source="conversation:1",
        statement="I looked at the moon.",
        observed_at=NOW,
    )
    observation = service.attribute_observations(IdentityAttribute.HOBBIES)[0]
    authorization = ShareAuthorization(
        owner_core_id=service.core_id,
        granted_by="owner:hardening",
        reason="attempted private identity sharing",
        granted_at=NOW,
    )
    with pytest.raises(PermissionError):
        service.share_memory(
            observation.observation_id,
            authorization=authorization,
            recipient_core_id=uuid4(),
            now=NOW,
        )


def test_revocation_and_correction_keep_audit_history(canonical_state_path):
    service = _service(canonical_state_path)
    recipient_id = uuid4()
    shareable = MemoryRecord(
        memory_id=uuid4(),
        owner_core_id=service.core_id,
        memory_type=MemoryType.SEMANTIC,
        tier=StorageTier.T1_ACTIVE,
        security=SecurityClass.SHAREABLE,
        evidence=EvidenceState.VERIFIED,
        source="test:shareable",
        content="content that will be revoked",
        created_at=NOW,
        updated_at=NOW,
        confidence=1.0,
        significance=5,
    )
    service.memory_store.persist(
        shareable, actor="test", owner_core_id=service.core_id
    )
    authorization = ShareAuthorization(
        owner_core_id=service.core_id,
        granted_by="owner:hardening",
        reason="explicit cross-Core approval",
        granted_at=NOW,
    )
    copy = service.share_memory(
        shareable.memory_id,
        authorization=authorization,
        recipient_core_id=recipient_id,
        now=NOW,
    )
    deletion = DeletionAuthorization(
        owner_core_id=service.core_id,
        granted_by="owner:hardening",
        reason="revoke the source after sharing",
        granted_at=NOW + timedelta(minutes=1),
    )
    assert service.memory_store.delete(
        shareable.memory_id, authorization=deletion, actor="test"
    ) is True
    actions = [event.action for event in service.provenance(shareable.memory_id)]
    assert actions == ["persist", "share", "delete"]
    recipient = MulticoreMemoryStore(canonical_state_path, recipient_id)
    assert recipient.get(copy.memory_id) is not None


# ---------------------------------------------------------------------------
# 6. Voluntary growth and restart replay
# ---------------------------------------------------------------------------


def test_growth_requires_sustained_evidence_before_establishment(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    first = service.observe_one_time(
        IdentityAttribute.HOBBIES,
        "astronomy",
        source="conversation:1",
        statement="I tried astronomy once.",
        observed_at=NOW,
    )
    assert first.state is IdentityAttributeState.TENTATIVE
    states = []
    for index in range(5):
        evidence = EvidenceState.REPORTED if index < 2 else EvidenceState.VERIFIED
        record = service.observe_recurring(
            IdentityAttribute.HOBBIES,
            "astronomy",
            source=f"session:{index}",
            statement=f"Observed astronomy session {index}.",
            observed_at=NOW + timedelta(days=index + 1),
            evidence=evidence,
        )
        states.append(record.state)
    assert states[:4] == [
        IdentityAttributeState.TENTATIVE,
        IdentityAttributeState.SUPPORTED,
        IdentityAttributeState.SUPPORTED,
        IdentityAttributeState.SUPPORTED,
    ]
    assert states[4] is IdentityAttributeState.ESTABLISHED


def test_blank_attribute_can_be_deferred_indefinitely(canonical_state_path):
    service = _service(canonical_state_path)
    assert service.completion_deadline is None
    assert service.progress_pressure is False
    service.observe_one_time(
        IdentityAttribute.HOBBIES,
        "pottery",
        source="conversation:1",
        statement="I tried pottery once.",
        observed_at=NOW,
    )
    deferred = service.attribute(IdentityAttribute.PERSONAL_NAME)
    assert deferred.state is IdentityAttributeState.UNSELECTED
    assert deferred.value is None
    assert service.full_name is None


def test_restart_replays_observations_and_revisions_after_revision(
    canonical_state_path,
):
    core_id = uuid4()
    service = MulticoreUnwrittenIdentity(canonical_state_path, core_id)
    service.select(
        IdentityAttribute.HOBBIES,
        "astronomy",
        source="core:self-selection",
        statement="I choose astronomy.",
        observed_at=NOW,
    )
    service.correct(
        IdentityAttribute.HOBBIES,
        "pottery",
        source="core:correction",
        statement="I revised my hobby after reflection.",
        observed_at=NOW + timedelta(days=1),
    )
    service.retire(
        IdentityAttribute.HOBBIES,
        source="core:retirement",
        statement="I retire this hobby choice for now.",
        observed_at=NOW + timedelta(days=2),
    )
    before = [
        (
            revision.revision,
            revision.prior_state,
            revision.new_state,
            revision.prior_value,
            revision.new_value,
            revision.kind,
        )
        for revision in service.revisions
    ]
    observation_ids = [
        observation.observation_id for observation in service.observations
    ]
    restarted = MulticoreUnwrittenIdentity(canonical_state_path, core_id)
    after = [
        (
            revision.revision,
            revision.prior_state,
            revision.new_state,
            revision.prior_value,
            revision.new_value,
            revision.kind,
        )
        for revision in restarted.revisions
    ]
    assert after == before
    assert [
        observation.observation_id for observation in restarted.observations
    ] == observation_ids
    assert restarted.attribute(IdentityAttribute.HOBBIES).state is (
        IdentityAttributeState.RETIRED
    )
    assert restarted.attribute(IdentityAttribute.HOBBIES).value is None


def test_speculative_correction_is_refused(canonical_state_path):
    service = _service(canonical_state_path)
    service.select(
        IdentityAttribute.NICKNAME,
        "Rune",
        source="core:self-selection",
        statement="I choose Rune.",
        observed_at=NOW,
    )
    with pytest.raises(IdentityConflictError):
        service.correct(
            IdentityAttribute.NICKNAME,
            "Sable",
            source="conversation:speculative",
            statement="A speculative correction.",
            observed_at=NOW + timedelta(days=1),
            evidence=EvidenceState.SPECULATIVE,
        )
    assert service.nickname == "Rune"


# ---------------------------------------------------------------------------
# 7. No identity, social or preference value grants Platform authority
# ---------------------------------------------------------------------------


def test_identity_social_and_preference_values_never_grant_authority(
    canonical_state_path,
):
    service = _service(canonical_state_path)
    selected = service.select(
        IdentityAttribute.PERSONAL_NAME,
        "Lyra",
        source="core:self-selection",
        statement="I choose Lyra.",
        observed_at=NOW,
    )
    preference = service.observe_preference(
        "music:jazz",
        stance=True,
        evidence=EvidenceState.VERIFIED,
        source="conversation:1",
        statement="I chose to listen to jazz.",
        observed_at=NOW,
    )
    service.observe_preference(
        "music:jazz",
        stance=True,
        evidence=EvidenceState.VERIFIED,
        source="conversation:2",
        statement="I chose to listen to jazz again.",
        observed_at=NOW + timedelta(days=1),
    )
    social = UnwrittenSocial(
        service, policy=SocialPolicy(introductions=True)
    )
    invitation = social.introduce(uuid4(), now=NOW)
    accepted = social.accept(invitation.invitation_id, now=NOW)
    assert preference.state in (
        PreferenceState.TENTATIVE,
        PreferenceState.DEVELOPING,
        PreferenceState.ESTABLISHED,
    )
    for item in (
        service,
        service.profile,
        selected,
        service.revisions[0],
        social,
        accepted,
    ):
        assert item.grants_authority is False
    assert service.execution_authority is False
    assert social.execution_authority is False
    assert selected.execution_authority is False
    assert accepted.execution_authority is False


# ---------------------------------------------------------------------------
# 8. Package compatibility
# ---------------------------------------------------------------------------


def test_blank_core_profile_digest_equals_packaged_constitution(
    canonical_state_path,
):
    digest = unwritten_constitution_sha256()
    profile = blank_core_profile(uuid4())
    assert profile.constitution_sha256 == digest
    assert profile.verify(expected_constitution_sha256=digest) is True
    service = _service(canonical_state_path)
    assert service.profile.constitution_sha256 == digest
    assert service.verify_protected_identity(
        expected_core_id=service.core_id
    ) is True
