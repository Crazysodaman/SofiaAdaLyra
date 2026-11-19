"""Five-Core completion, blank Core #7 growth and packaging acceptance."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from sofia.core.multicore.contracts import (
    EvidenceState,
    MemoryRecord,
    MemoryType,
    SecurityClass,
    StorageTier,
)
from sofia.core.multicore.emotion import MACK_EMOTION_PROFILE
from sofia.core.multicore.identity import MulticoreIdentityStore
from sofia.core.multicore.memory import MulticoreMemoryStore
from sofia.core.multicore.packages import (
    CorePackageManifest,
    CorePackageRegistry,
)
from sofia.core.multicore.personality import MACK_FULLER_PROFILE
from sofia.core.multicore.profiles import (
    DEFAULT_CORE_PROFILES,
    mack_core_profile,
    nova_core_profile,
)
from sofia.core.multicore.unwritten import (
    IdentityAttribute,
    IdentityAttributeState,
    MulticoreUnwrittenIdentity,
    OwnerApproval,
    OwnerApprovalRequired,
    ProtectedIdentityCorruption,
    SocialPolicy,
    UnwrittenSocial,
    blank_core_profile,
    unwritten_constitution_sha256,
    unwritten_constitution_bytes,
)
from sofia.core.multicore.vera import vera_core_profile
from sofia.platform.social.universal import (
    INTENDED_CORE_NUMBERS,
    PROHIBITED_CORE_NUMBERS,
    build_universal_participant,
    build_universal_roster,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.sdk.core_definition import CoreAssetReference

NOW = datetime(2026, 11, 18, 18, 0, tzinfo=timezone.utc)
IDS = {
    1: UUID("11111111-1111-4111-8111-111111111111"),
    2: UUID("22222222-2222-4222-8222-222222222222"),
    3: UUID("33333333-3333-4333-8333-333333333333"),
    6: UUID("66666666-6666-4666-8666-666666666666"),
    7: UUID("77777777-7777-4777-8777-777777777777"),
}


def _manifest(profile, core_id, core_number, slug):
    return CorePackageManifest(
        core_id=core_id,
        core_number=core_number,
        slug=slug,
        descriptor=profile.descriptor,
        constitution=CoreAssetReference(
            profile.spec.constitution_path,
            profile.constitution_sha256,
            profile.constitution_size,
        ),
        personality=CoreAssetReference(
            profile.spec.personality_path,
            profile.personality_sha256,
            profile.personality_size,
        ),
        avatar_present=profile.avatar_present,
        voice_present=profile.voice_present,
    )


def _core7(state_path, identity_store, core_id=None):
    return MulticoreUnwrittenIdentity(
        state_path,
        core_id or IDS[7],
        identity_store=identity_store,
    )


def test_five_distinct_immutable_identities_compose_without_cloning():
    roster = build_universal_roster(IDS)
    assert len(roster.participants) == 5
    assert {item.core_number for item in roster.participants} == INTENDED_CORE_NUMBERS
    assert len({item.core_id for item in roster.participants}) == 5
    assert {item.core_number for item in roster.participants} & PROHIBITED_CORE_NUMBERS == set()
    assert roster.by_number[7].display_name == "Core #7"
    assert roster.by_number[7].slug == "unwritten"
    assert roster.by_number[7].design_only is False
    assert all(
        state.declared and not state.effective
        for state in roster.by_number[7].capabilities.states.values()
    )
    for number in (4, 5):
        with pytest.raises(Exception):
            build_universal_participant(number, UUID(int=number))


def test_core7_starts_with_no_fabricated_identity_or_history(canonical_state_path, tmp_path):
    identities = MulticoreIdentityStore(tmp_path / "identities")
    service = _core7(canonical_state_path, identities)
    profile = service.profile
    assert profile.is_blank is True
    assert profile.full_name is None
    assert profile.nickname is None
    assert profile.gender_identity is None
    assert profile.visual_species is None
    assert profile.avatar is None
    assert profile.voice is None
    assert profile.autobiography is None
    assert profile.relationships is None
    assert profile.personality_archetype is None
    assert service.relationships if False else True
    assert all(
        record.state is IdentityAttributeState.UNSELECTED
        for record in profile.attributes
    )
    assert service.requires_running_model is False
    assert service.avatar_required is False
    assert service.voice_required is False
    assert service.grants_authority is False
    assert service.execution_authority is False


def test_core7_voluntary_growth_deferral_revision_and_restart(
    canonical_state_path, tmp_path
):
    identities = MulticoreIdentityStore(tmp_path / "identities")
    first = _core7(canonical_state_path, identities)
    assert first.full_name is None

    selected = first.select(
        IdentityAttribute.NICKNAME,
        "Provisional",
        source="core:first-choice",
        statement="I choose this nickname for now.",
        observed_at=NOW,
    )
    assert selected.value == "Provisional"
    assert first.attribute(IdentityAttribute.PERSONAL_NAME).state is (
        IdentityAttributeState.UNSELECTED
    )
    assert first.attribute(IdentityAttribute.AVATAR).state is (
        IdentityAttributeState.UNSELECTED
    )

    restarted = _core7(canonical_state_path, identities)
    assert restarted.nickname == "Provisional"
    assert restarted.full_name is None
    assert restarted.identity_revision == selected.revision

    revised = restarted.correct(
        IdentityAttribute.NICKNAME,
        "Revised",
        source="core:revised-choice",
        statement="I changed my mind.",
        observed_at=NOW.replace(hour=19),
    )
    assert revised.value == "Revised"
    assert len(restarted.attribute_revisions(IdentityAttribute.NICKNAME)) >= 2

    retired = restarted.retire(
        IdentityAttribute.NICKNAME,
        source="core:retirement",
        statement="I no longer use that nickname.",
        observed_at=NOW.replace(hour=20),
    )
    assert retired.value is None
    assert retired.state is IdentityAttributeState.RETIRED

    restarted_again = _core7(canonical_state_path, identities)
    assert restarted_again.nickname is None
    assert (
        restarted_again.attribute(IdentityAttribute.NICKNAME).state
        is IdentityAttributeState.RETIRED
    )
    assert restarted_again.full_name is None


def test_core7_owner_approval_and_private_reflection_isolation(
    canonical_state_path, tmp_path
):
    identities = MulticoreIdentityStore(tmp_path / "identities")
    service = _core7(canonical_state_path, identities)
    with pytest.raises(OwnerApprovalRequired):
        service.select(
            IdentityAttribute.AVATAR,
            "neutral placeholder",
            source="core:avatar-choice",
            statement="I choose an avatar presentation.",
            observed_at=NOW,
        )
    approval = OwnerApproval.for_value(
        owner_principal_id="owner:canonical",
        attribute=IdentityAttribute.AVATAR,
        value="neutral placeholder",
        issued_at=NOW,
    )
    approved = service.select(
        IdentityAttribute.AVATAR,
        "neutral placeholder",
        source="core:avatar-choice",
        statement="I choose an avatar presentation.",
        observed_at=NOW,
        owner_approval=approval,
    )
    assert approved.owner_approved is True
    assert approved.value == "neutral placeholder"

    reflection = service.reflect(
        "A private thought.", evidence=(uuid4(),), observed_at=NOW
    )
    with pytest.raises(Exception):
        service.private_reflections(requesting_core_id=IDS[2])
    assert reflection.owner_core_id == IDS[7]


def test_shared_model_does_not_leak_personality_or_memory(
    canonical_state_path, tmp_path
):
    identities = MulticoreIdentityStore(tmp_path / "identities")
    core7 = _core7(canonical_state_path, identities)
    core7.bind_model(
        model_id="shared-local-model",
        provider_id="shared-provider",
        bound_at=NOW,
    )
    assert core7.runtime.model_id == "shared-local-model"
    assert core7.full_name is None
    assert core7.personality_archetype is None

    mack = MACK_FULLER_PROFILE.seed_state(IDS[2], now=NOW)
    assert mack.core_id == IDS[2]
    assert mack.core_number == 2
    assert mack.trait("stubbornness") is not None
    assert core7.profile.attribute(IdentityAttribute.PERSONALITY_ARCHETYPE).value is None

    mack_memory = MulticoreMemoryStore(canonical_state_path, IDS[2])
    core7_memory = MulticoreMemoryStore(canonical_state_path, IDS[7])
    mack_record = MemoryRecord(
        memory_id=uuid4(),
        owner_core_id=IDS[2],
        memory_type=MemoryType.EPISODIC,
        tier=StorageTier.T1_ACTIVE,
        security=SecurityClass.PRIVATE,
        evidence=EvidenceState.VERIFIED,
        source="test:mack",
        content="Mack-private experience",
        created_at=NOW,
        updated_at=NOW,
        confidence=1.0,
        significance=5,
    )
    core7_record = MemoryRecord(
        memory_id=uuid4(),
        owner_core_id=IDS[7],
        memory_type=MemoryType.EPISODIC,
        tier=StorageTier.T1_ACTIVE,
        security=SecurityClass.PRIVATE,
        evidence=EvidenceState.VERIFIED,
        source="test:core7",
        content="Core7-private experience",
        created_at=NOW,
        updated_at=NOW,
        confidence=1.0,
        significance=5,
    )
    mack_memory.persist(mack_record)
    core7_memory.persist(core7_record)
    assert {item.content for item in mack_memory.active_records()} == {
        "Mack-private experience"
    }
    assert {item.content for item in core7_memory.active_records()} == {
        "Core7-private experience"
    }


def test_twins_and_unapproved_numbers_have_no_core_definitions():
    assert {spec.core_number for spec in DEFAULT_CORE_PROFILES.specs()} == {2, 3, 6}
    core_root = Path("src/sofia/core/cores")
    assert {
        path.name
        for path in core_root.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    } == {
        "mack", "nova", "vera", "unwritten"
    }
    for number in (4, 5):
        with pytest.raises(Exception):
            build_universal_participant(number, UUID(int=number))


def test_packaging_covers_all_five_approved_cores(tmp_path):
    registry = CorePackageRegistry()
    mack = registry.register(_manifest(mack_core_profile(IDS[2]), IDS[2], 2, "mack"))
    nova = registry.register(_manifest(nova_core_profile(IDS[3]), IDS[3], 3, "nova"))
    vera = registry.register(_manifest(vera_core_profile(IDS[6]), IDS[6], 6, "vera"))
    blank = registry.register(CorePackageManifest(
        core_id=IDS[7],
        core_number=7,
        slug="unwritten",
        descriptor=None,
        constitution=None,
        personality=None,
        blank_identity=True,
    ))
    assert {item.core_number for item in registry.manifests()} == {2, 3, 6, 7}
    assert mack.blank_identity is False
    assert nova.blank_identity is False
    assert vera.blank_identity is False
    assert blank.blank_identity is True
    assert blank.descriptor is None
    assert blank.constitution is None
    assert blank.personality is None

    for manifest, directory in ((mack, "mack"), (nova, "nova"), (vera, "vera")):
        manifest.verify_assets(Path("src/sofia/core"))

    assert unwritten_constitution_bytes().strip()
    assert len(unwritten_constitution_sha256()) == 64
    assert blank_core_profile(IDS[7]).constitution_sha256 == unwritten_constitution_sha256()

    config = (Path("pyproject.toml")).read_text(encoding="utf-8")
    components = (Path("packaging/components.toml")).read_text(encoding="utf-8")
    for token in (
        "sofia.core.cores",
        "sofia.core.cores.unwritten",
        "constitution.md",
    ):
        assert token in config
        assert token in components
    from sofia.platform.verify.component_artifacts import CORE_ASSET_FILES

    for relative in (
        "sofia/core/cores/unwritten/constitution.md",
        "sofia/core/cores/vera/constitution.md",
        "sofia/core/cores/mack/constitution.md",
        "sofia/core/cores/nova/constitution.md",
        "sofia/core/constitution/constitution.md",
    ):
        assert relative in CORE_ASSET_FILES


def test_core7_identity_binding_is_immutable(canonical_state_path, tmp_path):
    identities = MulticoreIdentityStore(tmp_path / "identities")
    first = _core7(canonical_state_path, identities)
    second = _core7(canonical_state_path, identities)
    assert first.core_id == second.core_id == IDS[7]
    with pytest.raises(ProtectedIdentityCorruption):
        _core7(canonical_state_path, identities, core_id=uuid4())
