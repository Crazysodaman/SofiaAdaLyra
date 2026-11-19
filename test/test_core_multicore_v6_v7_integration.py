"""Cross-workstream acceptance for Aegis Cores #6 (Vera-like) and #7 (blank)."""
from __future__ import annotations

import sqlite3
from dataclasses import fields
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from sofia.core.multicore.contracts import (
    EvidenceState,
    MemoryRecord,
    MemoryType,
    SecurityClass,
    StorageTier,
)
from sofia.core.multicore.memory import (
    MemoryIsolationError,
    MulticoreMemoryStore,
    ShareAuthorization,
)
from sofia.core.multicore.v6_v7_acceptance import (
    BLANK_MEMORY_KEY,
    BLANK_MEMORY_TEXT,
    VERA_MEMORY_KEY,
    VERA_MEMORY_TEXT,
    AllowAllAuthorization,
    AlwaysStoppedSafety,
    CoreProfileView,
    InMemoryCoreInference,
    InMemoryCoreMemory,
    InMemoryCorePackage,
    InMemoryResourceAuthority,
    InMemoryTextPlatform,
    NeverStoppedSafety,
    StaticCoreProfiles,
    V6V7AcceptanceHarness,
    V6V7AcceptanceError,
    V6V7CoreFixture,
    V6V7Denied,
    V6V7Fixtures,
    V6V7Stage,
    V6V7Status,
)
from sofia.platform.chat import (
    ChatActor,
    ChatEngine,
    CoreIdentity,
    GENERAL_ROOM_ID,
    InvitationStatus,
    MembershipStatus,
    RoomHistoryPolicy,
)

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def _fixtures(tmp_path) -> V6V7Fixtures:
    return V6V7Fixtures.create(tmp_path / "fixtures")


def _profiles(fixtures: V6V7Fixtures) -> StaticCoreProfiles:
    profiles = StaticCoreProfiles()
    profiles.bind(fixtures.vera.core_id, fixtures.vera.profile)
    profiles.bind(fixtures.blank.core_id, fixtures.blank.profile)
    return profiles


def _harness(
    fixtures: V6V7Fixtures,
    *,
    package: InMemoryCorePackage | None = None,
    authorization=None,
    safety=None,
    resources: InMemoryResourceAuthority | None = None,
    core_free_platform: InMemoryTextPlatform | None = None,
    restart: bool = True,
) -> V6V7AcceptanceHarness:
    return V6V7AcceptanceHarness(
        owner_id="owner:fixture",
        platform_id="platform:v6v7-fixture",
        profiles=_profiles(fixtures),
        package=package if package is not None else InMemoryCorePackage(),
        authorization=(
            authorization if authorization is not None else AllowAllAuthorization()
        ),
        memory=InMemoryCoreMemory(),
        inference=InMemoryCoreInference(),
        platform=InMemoryTextPlatform(),
        safety=safety if safety is not None else NeverStoppedSafety(),
        resources=(
            resources if resources is not None else InMemoryResourceAuthority()
        ),
        core_free_platform=(
            core_free_platform
            if core_free_platform is not None
            else InMemoryTextPlatform()
        ),
        restart_package=InMemoryCorePackage if restart else None,
        restart_inference=InMemoryCoreInference if restart else None,
        restart_memory=InMemoryCoreMemory if restart else None,
        clock=lambda: NOW,
    )


def _engine(tmp_path) -> ChatEngine:
    path = tmp_path / "chat.db"
    with sqlite3.connect(path):
        pass
    return ChatEngine(
        path,
        owner_id="owner:fixture",
        platform_id="platform:v6v7-fixture",
        clock=lambda: NOW,
    )


def _memory_record(
    owner_id: UUID,
    content: str,
    *,
    security: SecurityClass = SecurityClass.PRIVATE,
) -> MemoryRecord:
    return MemoryRecord(
        memory_id=uuid4(),
        owner_core_id=owner_id,
        memory_type=MemoryType.EPISODIC,
        tier=StorageTier.T1_ACTIVE,
        security=security,
        evidence=EvidenceState.VERIFIED,
        source="v6v7-fixture",
        content=content,
        created_at=NOW,
        updated_at=NOW,
        confidence=1.0,
        significance=5,
    )


def _existing_profile() -> CoreProfileView:
    return CoreProfileView(
        core_number=2,
        full_name="Mack Fuller",
        nickname="Mack",
        slug="mack",
        identity_concept="Existing installed Core fixture",
        callsign="Mack",
        presentation="existing installed Core",
    )


def test_fixtures_have_unique_identity_distinct_profiles_and_separate_callsigns(
    tmp_path,
) -> None:
    fixtures = _fixtures(tmp_path)
    vera, blank = fixtures.vera, fixtures.blank

    assert vera.core_id != blank.core_id
    assert vera.profile.core_number != blank.profile.core_number
    assert vera.profile.slug != blank.profile.slug
    assert vera.profile.full_name != blank.profile.full_name
    assert vera.callsign != blank.callsign
    assert vera.profile.blank is False
    assert blank.profile.blank is True
    assert vera.profile.armor_material is not None
    assert blank.profile.armor_material is None
    assert vera.profile.grants_authority is False
    assert blank.profile.grants_authority is False

    for fixture in (vera, blank):
        assert fixture.callsign != str(fixture.core_id)
        with pytest.raises(ValueError):
            UUID(fixture.callsign)
        assert fixture.definition.identity.identity_id == fixture.core_id
        assert fixture.definition_path.is_file()
        assert fixture.constitution_path.is_file()
        assert fixture.personality_path.is_file()

    profile_fields = {item.name for item in fields(CoreProfileView)}
    forbidden = {"authority", "permission", "capability", "role", "grant", "token"}
    assert not any(
        word in name for name in profile_fields for word in forbidden
    )


def test_full_disposable_acceptance_path_passes_required_stages(tmp_path) -> None:
    fixtures = _fixtures(tmp_path)
    harness = _harness(fixtures)
    report = harness.run(fixtures.vera, fixtures.blank)

    assert report.ok is True
    assert report.real_installation is False
    assert report.voice_avatar_required is False
    assert report.restart_simulated is True
    assert report.core_free_platform_verified is True
    assert report.recovery is not None
    for stage in (
        V6V7Stage.FIXTURE,
        V6V7Stage.CORE_FREE_PLATFORM,
        V6V7Stage.REGISTRATION,
        V6V7Stage.ACTIVATION,
        V6V7Stage.BLANK_UNSELECTED,
        V6V7Stage.TEXT_CONVERSATION,
        V6V7Stage.INFERENCE,
        V6V7Stage.MEMORY_ISOLATION,
        V6V7Stage.UNAUTHORIZED_SHARING,
        V6V7Stage.RESTART_RECOVERY,
        V6V7Stage.STOP_AND_AUTHORIZATION_DENIAL,
        V6V7Stage.INVITATION_DECLINE,
        V6V7Stage.RESOURCE_RESERVATION,
    ):
        step = report.step(stage)
        assert step is not None
        assert step.status is V6V7Status.PASSED

    assert harness.package.status(core_id=fixtures.vera.core_id).active is True
    assert harness.package.status(core_id=fixtures.blank.core_id).active is False
    assert harness.platform.selected_core_ids() == (fixtures.vera.core_id,)
    assert report.reservations == (fixtures.vera.core_id,)


def test_authorization_calls_address_uuids_not_callsigns_or_appearance(
    tmp_path,
) -> None:
    fixtures = _fixtures(tmp_path)
    authorizer = AllowAllAuthorization()
    harness = _harness(fixtures, authorization=authorizer)
    harness.run(fixtures.vera, fixtures.blank)

    calls = authorizer.calls
    assert calls
    assert all(isinstance(core_id, UUID) for _, core_id, _, _ in calls)
    assert {core_id for _, core_id, _, _ in calls} == {
        fixtures.vera.core_id,
        fixtures.blank.core_id,
    }
    callsigns = {fixtures.vera.callsign, fixtures.blank.callsign}
    for _, core_id, _, fingerprint in calls:
        assert str(core_id) not in callsigns
        assert fingerprint not in callsigns
    assert {operation for operation, _, _, _ in calls} >= {
        "register",
        "activate",
        "conversation.route",
        "inference.submit",
    }


def test_cross_core_memory_isolation_and_unauthorized_sharing_denial(
    tmp_path,
) -> None:
    fixtures = _fixtures(tmp_path)
    harness = _harness(fixtures)
    harness.run(fixtures.vera, fixtures.blank)
    memory = harness.memory

    assert memory.recall(
        core_id=fixtures.vera.core_id, key=VERA_MEMORY_KEY
    ).content == VERA_MEMORY_TEXT
    assert memory.recall(
        core_id=fixtures.blank.core_id, key=BLANK_MEMORY_KEY
    ).content == BLANK_MEMORY_TEXT
    assert memory.recall(core_id=fixtures.blank.core_id, key=VERA_MEMORY_KEY) is None
    assert memory.recall(core_id=fixtures.vera.core_id, key=BLANK_MEMORY_KEY) is None

    vera_records = memory.records(core_id=fixtures.vera.core_id)
    blank_records = memory.records(core_id=fixtures.blank.core_id)
    assert all(record.owner_core_id == fixtures.vera.core_id for record in vera_records)
    assert all(record.owner_core_id == fixtures.blank.core_id for record in blank_records)
    assert all(record.content != BLANK_MEMORY_TEXT for record in vera_records)
    assert all(record.content != VERA_MEMORY_TEXT for record in blank_records)

    with pytest.raises(PermissionError):
        memory.share(
            source_core_id=fixtures.vera.core_id,
            recipient_core_id=fixtures.blank.core_id,
            key=VERA_MEMORY_KEY,
            authorization=None,
        )
    with pytest.raises(PermissionError):
        memory.share(
            source_core_id=fixtures.vera.core_id,
            recipient_core_id=fixtures.blank.core_id,
            key=VERA_MEMORY_KEY,
            authorization=ShareAuthorization(
                owner_core_id=fixtures.blank.core_id,
                granted_by="owner:fixture",
                reason="foreign owner probe",
                granted_at=NOW,
            ),
        )
    with pytest.raises(PermissionError):
        memory.share(
            source_core_id=fixtures.vera.core_id,
            recipient_core_id=fixtures.blank.core_id,
            key=VERA_MEMORY_KEY,
            authorization=ShareAuthorization(
                owner_core_id=fixtures.vera.core_id,
                granted_by="owner:fixture",
                reason="private class cannot be shared",
                granted_at=NOW,
            ),
        )
    assert memory.records(core_id=fixtures.blank.core_id) == blank_records

    memory.remember(
        core_id=fixtures.vera.core_id,
        key="shareable-note",
        content="fixture text permitted for an authorized copy",
        security=SecurityClass.SHAREABLE,
    )
    shared = memory.share(
        source_core_id=fixtures.vera.core_id,
        recipient_core_id=fixtures.blank.core_id,
        key="shareable-note",
        authorization=ShareAuthorization(
            owner_core_id=fixtures.vera.core_id,
            granted_by="owner:fixture",
            reason="explicit authorized sharing probe",
            granted_at=NOW,
        ),
    )
    assert shared.owner_core_id == fixtures.blank.core_id
    assert shared.security is SecurityClass.AUTHORIZED_SHARED_COPY
    assert memory.recall(core_id=fixtures.vera.core_id, key="shareable-note") is not None


def test_stop_denies_both_personas_and_injected_stop_blocks_the_run(
    tmp_path,
) -> None:
    fixtures = _fixtures(tmp_path)

    step = _harness(fixtures).verify_denials(fixtures.vera, fixtures.blank)
    assert step.status is V6V7Status.PASSED

    stopped = _harness(fixtures, safety=AlwaysStoppedSafety())
    with pytest.raises(V6V7Denied, match="STOP"):
        stopped.run(fixtures.vera, fixtures.blank)
    assert stopped.package.installed_core_ids() == ()
    assert stopped.resources.reserved_core_ids() == ()


def test_recovery_preserves_identity_and_blank_core_stays_unselected(
    tmp_path,
) -> None:
    fixtures = _fixtures(tmp_path)
    package = InMemoryCorePackage()
    harness = _harness(fixtures, package=package)
    report = harness.run(fixtures.vera, fixtures.blank)

    recovery = report.recovery
    assert recovery is not None
    assert recovery.core_id == fixtures.vera.core_id
    assert recovery.generation == fixtures.vera.generation
    assert recovery.full_name == fixtures.vera.profile.full_name
    assert recovery.callsign == fixtures.vera.callsign
    assert recovery.profile.to_payload() == fixtures.vera.profile.to_payload()
    assert recovery.active is True
    assert recovery.simulated is True

    blank = package.status(core_id=fixtures.blank.core_id)
    assert blank.registered is True
    assert blank.active is False
    assert blank.installed is False
    assert fixtures.blank.core_id not in report.reservations


def test_blank_core_remains_unselected_without_inference_or_reservation(
    tmp_path,
) -> None:
    fixtures = _fixtures(tmp_path)
    harness = _harness(fixtures)
    report = harness.run(fixtures.vera, fixtures.blank)

    step = report.step(V6V7Stage.BLANK_UNSELECTED)
    assert step is not None and step.status is V6V7Status.PASSED
    assert harness.platform.selected_core_ids() == (fixtures.vera.core_id,)
    assert harness.package.status(core_id=fixtures.blank.core_id).active is False
    assert harness.inference.history(
        core_id=fixtures.blank.core_id,
        generation=fixtures.blank.generation,
        conversation_id="unselected",
    ) == ()
    assert fixtures.blank.core_id not in harness.resources.reserved_core_ids()


def test_authorization_denial_prevents_activation_inference_and_reservation(
    tmp_path,
) -> None:
    fixtures = _fixtures(tmp_path)

    class ActivationOnlyDenied:
        def __init__(self) -> None:
            self.calls = []

        def authorize(self, *, operation, core_id, generation, fingerprint):
            self.calls.append((operation, core_id, generation, fingerprint))
            return operation == "register"

    authorization = ActivationOnlyDenied()
    resources = InMemoryResourceAuthority()
    harness = _harness(fixtures, authorization=authorization, resources=resources)
    with pytest.raises(V6V7Denied, match="activate"):
        harness.run(fixtures.vera, fixtures.blank)

    assert harness.package.status(core_id=fixtures.vera.core_id).active is False
    assert harness.package.status(core_id=fixtures.blank.core_id).registered is True
    assert harness.platform.selected_core_ids() == ()
    assert resources.reserved_core_ids() == ()
    assert harness.inference.history(
        core_id=fixtures.vera.core_id,
        generation=fixtures.vera.generation,
        conversation_id=f"v6v7-{fixtures.vera.core_id.hex[:16]}",
    ) == ()
    assert (
        "activate",
        fixtures.vera.core_id,
        fixtures.vera.generation,
        fixtures.vera.definition_digest,
    ) in authorization.calls


def test_existing_installed_cores_coexist_with_v6_v7_registrations(
    tmp_path,
) -> None:
    fixtures = _fixtures(tmp_path)
    package = InMemoryCorePackage()
    existing_id = uuid4()
    package.seed_installed(
        core_id=existing_id,
        profile=_existing_profile(),
        platform_id="platform:v6v7-fixture",
        generation=1,
        definition_digest="a" * 64,
    )
    harness = _harness(fixtures, package=package)
    report = harness.run(fixtures.vera, fixtures.blank)

    assert report.ok is True
    existing = package.status(core_id=existing_id)
    assert existing.installed is True
    assert existing.active is True
    assert existing.full_name == "Mack Fuller"
    assert existing_id in package.installed_core_ids()
    assert fixtures.vera.core_id not in package.installed_core_ids()
    assert fixtures.blank.core_id not in package.installed_core_ids()


def test_platform_only_operation_with_real_chat_engine_and_zero_cores(
    tmp_path,
) -> None:
    engine = _engine(tmp_path)
    assert engine.core_identities() == ()

    body = "Platform-only owner heartbeat with no Core selected"
    engine.send(engine.owner_actor(), GENERAL_ROOM_ID, body)
    page = engine.history(engine.owner_actor(), GENERAL_ROOM_ID)

    assert any(message.body == body for message in page.messages)
    assert engine.core_identities() == ()


def test_decline_invitation_with_real_chat_engine_keeps_blank_core_inactive(
    tmp_path,
) -> None:
    fixtures = _fixtures(tmp_path)
    engine = _engine(tmp_path)
    identity = CoreIdentity(
        core_id=fixtures.blank.core_id,
        platform_id="platform:v6v7-fixture",
        generation=fixtures.blank.generation,
        display_name=fixtures.blank.profile.full_name,
    )
    engine.register_core(identity)
    room = engine.create_group(
        engine.owner_actor(),
        "V6/V7 invitation fixture",
        history_policy=RoomHistoryPolicy.NO_PRE_JOIN,
    )
    invitation = engine.invite(
        engine.owner_actor(), room.room_id, str(fixtures.blank.core_id),
    )
    assert invitation.status is InvitationStatus.PENDING

    declined = engine.decline_invitation(
        ChatActor.core(identity), invitation.invite_id,
    )

    assert declined.status is InvitationStatus.DECLINED
    membership = engine.membership(
        engine.owner_actor(), room.room_id, str(fixtures.blank.core_id),
    )
    assert membership is not None
    assert membership.status is MembershipStatus.DECLINED
    assert membership.is_active is False


def test_real_memory_store_isolates_v6_v7_and_existing_core_owners(
    tmp_path, canonical_state_path,
) -> None:
    fixtures = _fixtures(tmp_path)
    existing_id = uuid4()
    store = MulticoreMemoryStore(canonical_state_path)

    vera_record = _memory_record(
        fixtures.vera.core_id, f"vera fixture secret {VERA_MEMORY_TEXT}"
    )
    blank_record = _memory_record(
        fixtures.blank.core_id, f"blank fixture secret {BLANK_MEMORY_TEXT}"
    )
    existing_record = _memory_record(
        existing_id, "existing Core fixture secret retained"
    )
    store.for_owner(fixtures.vera.core_id).persist(vera_record)
    store.for_owner(fixtures.blank.core_id).persist(blank_record)
    store.for_owner(existing_id).persist(existing_record)

    for owner in (fixtures.vera.core_id, fixtures.blank.core_id, existing_id):
        retrieval = store.for_owner(owner).retrieve("fixture secret")
        assert retrieval.records
        assert all(record.owner_core_id == owner for record in retrieval.records)

    with pytest.raises(MemoryIsolationError):
        store.for_owner(fixtures.vera.core_id).persist(blank_record)

    with pytest.raises(PermissionError):
        store.for_owner(fixtures.vera.core_id).share(
            vera_record.memory_id,
            authorization=ShareAuthorization(
                owner_core_id=fixtures.vera.core_id,
                granted_by="owner:fixture",
                reason="private fixture record must not share",
                granted_at=NOW,
            ),
            recipient_core_id=fixtures.blank.core_id,
        )
    with pytest.raises(PermissionError):
        store.for_owner(fixtures.vera.core_id).share(
            vera_record.memory_id,
            authorization=ShareAuthorization(
                owner_core_id=fixtures.blank.core_id,
                granted_by="owner:fixture",
                reason="foreign owner must not share",
                granted_at=NOW,
            ),
            recipient_core_id=fixtures.blank.core_id,
        )

    shareable = _memory_record(
        fixtures.vera.core_id,
        "explicitly shareable fixture text",
        security=SecurityClass.SHAREABLE,
    )
    store.for_owner(fixtures.vera.core_id).persist(shareable)
    copy = store.for_owner(fixtures.vera.core_id).share(
        shareable.memory_id,
        authorization=ShareAuthorization(
            owner_core_id=fixtures.vera.core_id,
            granted_by="owner:fixture",
            reason="explicit authorized fixture copy",
            granted_at=NOW,
        ),
        recipient_core_id=fixtures.blank.core_id,
    )
    assert copy.owner_core_id == fixtures.blank.core_id
    assert copy.security is SecurityClass.AUTHORIZED_SHARED_COPY
    blank_records = store.for_owner(fixtures.blank.core_id).retrieve("fixture").records
    assert all(record.owner_core_id == fixtures.blank.core_id for record in blank_records)
    assert any(record.content == "explicitly shareable fixture text" for record in blank_records)
    vera_records = store.for_owner(fixtures.vera.core_id).retrieve("shareable").records
    assert any(
        record.owner_core_id == fixtures.vera.core_id
        and record.content == "explicitly shareable fixture text"
        for record in vera_records
    )


def test_fixture_rejects_non_inert_or_mismatched_profile_metadata(tmp_path) -> None:
    fixtures = _fixtures(tmp_path)
    profiles = _profiles(fixtures)
    profiles.bind(fixtures.blank.core_id, fixtures.vera.profile)
    harness = V6V7AcceptanceHarness(
        owner_id="owner:fixture",
        platform_id="platform:v6v7-fixture",
        profiles=profiles,
        package=InMemoryCorePackage(),
        authorization=AllowAllAuthorization(),
        memory=InMemoryCoreMemory(),
        inference=InMemoryCoreInference(),
        platform=InMemoryTextPlatform(),
        safety=NeverStoppedSafety(),
        resources=InMemoryResourceAuthority(),
    )
    with pytest.raises(V6V7AcceptanceError, match="profile"):
        harness.run(fixtures.vera, fixtures.blank)


def test_fixture_requires_exactly_one_blank_core(tmp_path) -> None:
    fixtures = _fixtures(tmp_path)
    not_blank = V6V7CoreFixture.create(
        tmp_path / "not-blank",
        profile=CoreProfileView(
            core_number=8,
            full_name="Not Blank Fixture",
            nickname="NotBlank",
            slug="not-blank-fixture",
            identity_concept="not the blank fixture",
            callsign="Not Blank",
            presentation="ordinary fixture",
        ),
        platform_id="platform:v6v7-fixture",
    )
    profiles = _profiles(fixtures)
    profiles.bind(not_blank.core_id, not_blank.profile)
    harness = V6V7AcceptanceHarness(
        owner_id="owner:fixture",
        platform_id="platform:v6v7-fixture",
        profiles=profiles,
        package=InMemoryCorePackage(),
        authorization=AllowAllAuthorization(),
        memory=InMemoryCoreMemory(),
        inference=InMemoryCoreInference(),
        platform=InMemoryTextPlatform(),
        safety=NeverStoppedSafety(),
        resources=InMemoryResourceAuthority(),
    )
    with pytest.raises(V6V7AcceptanceError, match="blank"):
        harness.run(fixtures.vera, not_blank)
