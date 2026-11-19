"""Source-level integration for the five approved Aegis Core runtime owners."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from importlib.resources import files as resource_files
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from sofia.core.identity.model import SofiaIdentity
from sofia.core.multicore import emotion as emotion_module
from sofia.core.multicore import personality as personality_module
from sofia.core.multicore.contracts import (
    EvidenceState,
    MemoryRecord,
    MemoryType,
    SecurityClass,
    StorageTier,
)
from sofia.core.multicore.emotion import (
    MACK_EMOTION_PROFILE,
    NOVA_EMOTION_PROFILE,
)
from sofia.core.multicore.identity import (
    MulticoreIdentityStore,
    SofiaIdentitySubstitution,
)
from sofia.core.multicore.memory import (
    MemoryIsolationError,
    MulticoreMemoryStore,
)
from sofia.core.multicore.packages import CorePackageRegistry
from sofia.core.multicore.personality import (
    MACK_FULLER_PROFILE,
    NOVA_ARDEN_PROFILE,
    personality_is_same_continuous_identity,
)
from sofia.core.multicore.profiles import (
    DEFAULT_CORE_PROFILES,
    UnknownCoreProfile,
    mack_core_profile,
    nova_core_profile,
)
from sofia.core.multicore.unwritten import (
    IdentityAttributeState,
    MulticoreUnwrittenIdentity,
    blank_core_profile,
    unwritten_constitution_sha256,
)
from sofia.core.multicore.vera import vera_core_profile
from sofia.platform.social.universal import (
    UniversalFacadeError,
    build_universal_participant,
    build_universal_roster,
)

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
IDS = {
    1: UUID("11111111-1111-4111-8111-111111111111"),
    2: UUID("22222222-2222-4222-8222-222222222222"),
    3: UUID("33333333-3333-4333-8333-333333333333"),
    6: UUID("66666666-6666-4666-8666-666666666666"),
    7: UUID("77777777-7777-4777-8777-777777777777"),
}
CORE_ROOT = Path(__file__).resolve().parents[1] / "src" / "sofia" / "core"


def _register(store: MulticoreIdentityStore, profile):
    return store.register_descriptor(
        profile.descriptor,
        constitution_sha256=profile.constitution_sha256,
        created_at=NOW - timedelta(hours=1),
    )


def _register_blank(store: MulticoreIdentityStore):
    return store.register(
        core_id=IDS[7],
        core_number=7,
        full_name="Core #7",
        slug="unwritten",
        constitution_sha256=unwritten_constitution_sha256(),
        created_at=NOW - timedelta(hours=1),
    )


def _memory_record(owner_core_id: UUID, content: str) -> MemoryRecord:
    return MemoryRecord(
        memory_id=uuid4(),
        owner_core_id=owner_core_id,
        memory_type=MemoryType.EPISODIC,
        tier=StorageTier.T1_ACTIVE,
        security=SecurityClass.PRIVATE,
        evidence=EvidenceState.VERIFIED,
        source="test:five-core-runtime",
        content=content,
        created_at=NOW,
        updated_at=NOW,
        confidence=1.0,
        significance=5,
    )


def _copy_core_assets(destination: Path, slug: str, names: tuple[str, ...]) -> Path:
    source = resource_files("sofia.core").joinpath(slug)
    target = destination / slug
    target.mkdir(parents=True)
    for name in names:
        (target / name).write_bytes(source.joinpath(name).read_bytes())
    return target


def test_five_cores_have_distinct_external_uuids_numbers_and_slugs(tmp_path):
    sofia = SofiaIdentity(name="Sofía Ada Lyra", instance_id=IDS[1])
    roster = build_universal_roster(IDS)
    participants = roster.by_number

    assert set(participants) == {1, 2, 3, 6, 7}
    assert len({item.core_id for item in participants.values()}) == 5
    assert len({item.slug for item in participants.values()}) == 5
    assert {item.slug for item in participants.values()} == {
        "sofia", "mack", "nova", "vera", "unwritten",
    }
    assert participants[1].core_id == sofia.instance_id == IDS[1]
    assert participants[1].display_name == "Sofía Ada Lyra"

    mack = mack_core_profile(IDS[2])
    nova = nova_core_profile(IDS[3])
    vera = vera_core_profile(IDS[6])
    blank = blank_core_profile(IDS[7])
    for number, profile in ((2, mack), (3, nova), (6, vera)):
        assert profile.descriptor.core_id == participants[number].core_id
        assert profile.descriptor.core_number == participants[number].core_number
        assert profile.descriptor.core_id == IDS[number]
    assert blank.core_id == participants[7].core_id == IDS[7]
    assert blank.core_number == 7
    assert blank.operator_label == participants[7].display_name == "Core #7"
    assert blank.is_blank is True
    assert blank.self_selected_name is None
    assert blank.constitution_sha256 == unwritten_constitution_sha256()

    store = MulticoreIdentityStore(
        tmp_path / "identities", sofia_instance_id=IDS[1],
    )
    _register(store, mack)
    _register(store, nova)
    _register(store, vera)
    _register_blank(store)
    records = store.load_all()
    assert {record.identity.core_id for record in records} == {
        IDS[2], IDS[3], IDS[6], IDS[7],
    }
    assert {record.identity.core_number for record in records} == {2, 3, 6, 7}
    assert len({record.slug for record in records}) == 4
    assert all(record.identity.core_id != IDS[1] for record in records)
    with pytest.raises(SofiaIdentitySubstitution):
        store.register(
            core_id=IDS[1],
            core_number=1,
            full_name="Sofía Ada Lyra",
            slug="sofia",
            constitution_sha256="a" * 64,
        )


def test_shared_model_binding_does_not_leak_personality_or_memory(
    canonical_state_path, tmp_path
):
    store = MulticoreIdentityStore(tmp_path / "identities")
    mack = mack_core_profile(IDS[2])
    nova = nova_core_profile(IDS[3])
    for profile in (mack, nova):
        _register(store, profile)
    for core_id in (IDS[2], IDS[3]):
        store.bind_model(
            core_id,
            model_id="shared-local-model",
            provider_id="shared-provider",
            bound_at=NOW,
        )

    mack_record = store.load(IDS[2])
    nova_record = store.load(IDS[3])
    assert mack_record.model_id == nova_record.model_id == "shared-local-model"
    assert mack_record.provider_id == nova_record.provider_id == "shared-provider"
    assert mack_record.identity.core_id == IDS[2]
    assert nova_record.identity.core_id == IDS[3]
    assert mack_record.identity.core_id != nova_record.identity.core_id

    mack_state = MACK_FULLER_PROFILE.seed_state(IDS[2], now=NOW)
    nova_state = NOVA_ARDEN_PROFILE.seed_state(IDS[3], now=NOW)
    assert mack_state.core_id == IDS[2]
    assert nova_state.core_id == IDS[3]
    assert mack_state.continuity_key != nova_state.continuity_key
    assert "stubbornness" in mack_state.weights()
    assert "stubbornness" not in nova_state.weights()
    assert "independence" in nova_state.weights()
    assert "independence" not in mack_state.weights()
    assert personality_is_same_continuous_identity(mack_state, nova_state) is False

    mack_memory = MulticoreMemoryStore(canonical_state_path, IDS[2])
    nova_memory = MulticoreMemoryStore(canonical_state_path, IDS[3])
    mack_memory.persist(
        _memory_record(IDS[2], "Mack-only memory about the shared model")
    )
    nova_memory.persist(
        _memory_record(IDS[3], "Nova-only memory about the shared model")
    )

    mack_result = mack_memory.retrieve("shared model memory")
    nova_result = nova_memory.retrieve("shared model memory")
    assert {record.owner_core_id for record in mack_result.records} == {IDS[2]}
    assert {record.owner_core_id for record in nova_result.records} == {IDS[3]}
    assert {record.content for record in mack_result.records} == {
        "Mack-only memory about the shared model"
    }
    assert {record.content for record in nova_result.records} == {
        "Nova-only memory about the shared model"
    }
    with pytest.raises(MemoryIsolationError):
        mack_memory.retrieve("shared model memory", owner_core_id=IDS[3])


def test_core_personality_emotion_and_vera_prose_metadata_stay_separate():
    mack = mack_core_profile(IDS[2])
    nova = nova_core_profile(IDS[3])
    vera = vera_core_profile(IDS[6])
    mack_seed_names = {
        seed.name for seed in MACK_FULLER_PROFILE.baseline_traits
    }
    nova_seed_names = {
        seed.name for seed in NOVA_ARDEN_PROFILE.baseline_traits
    }

    assert MACK_FULLER_PROFILE.continuity_key == "mack-fuller"
    assert NOVA_ARDEN_PROFILE.continuity_key == "nova-arden"
    assert MACK_FULLER_PROFILE.continuity_key != NOVA_ARDEN_PROFILE.continuity_key
    assert MACK_EMOTION_PROFILE.continuity_key == MACK_FULLER_PROFILE.continuity_key
    assert NOVA_EMOTION_PROFILE.continuity_key == NOVA_ARDEN_PROFILE.continuity_key
    assert MACK_EMOTION_PROFILE.continuity_key != NOVA_EMOTION_PROFILE.continuity_key
    assert dict(MACK_EMOTION_PROFILE.temperament) != dict(
        NOVA_EMOTION_PROFILE.temperament
    )
    assert "steadiness" in MACK_EMOTION_PROFILE.temperament
    assert "independence" in NOVA_EMOTION_PROFILE.temperament
    assert "stubborn" in mack.descriptor.personality_traits
    assert "rebellious" in nova.descriptor.personality_traits
    assert mack.descriptor.personality_traits != nova.descriptor.personality_traits
    assert "stubbornness" in mack.descriptor.character_flaw
    assert "impulsivity" in nova.descriptor.character_flaw

    vera_asset = json.loads(
        resource_files("sofia.core")
        .joinpath("vera", "personality.json")
        .read_text(encoding="utf-8")
    )
    assert vera.descriptor.personality_traits == tuple(vera_asset["traits"])
    assert vera.descriptor.motivations == tuple(vera_asset["motivations"])
    assert vera.descriptor.character_flaw == vera_asset["character_flaw"]
    assert vera.descriptor.constitutional_priorities == tuple(
        vera_asset["constitutional_priorities"]
    )
    assert set(vera.descriptor.personality_traits).isdisjoint(
        mack_seed_names | nova_seed_names
    )
    assert not hasattr(emotion_module, "VERA_EMOTION_PROFILE")
    assert not hasattr(personality_module, "VERA_PERSONALITY_PROFILE")
    assert not any(
        "VERA" in name and "PROFILE" in name
        for name in dir(emotion_module) + dir(personality_module)
    )

    blank = blank_core_profile(IDS[7])
    assert blank.personality_archetype is None
    assert blank.autobiography is None
    assert blank.relationships is None
    assert all(
        record.state is IdentityAttributeState.UNSELECTED
        for record in blank.attributes
    )
    assert not (
        resource_files("sofia.core")
        .joinpath("unwritten", "personality.json")
        .is_file()
    )


def test_voice_and_avatar_assets_are_deferred_and_text_needs_neither(
    canonical_state_path, tmp_path
):
    profiles = (
        (2, mack_core_profile(IDS[2]), mack_core_profile),
        (3, nova_core_profile(IDS[3]), nova_core_profile),
        (6, vera_core_profile(IDS[6]), vera_core_profile),
    )
    for _, profile, _ in profiles:
        assert profile.text_only is True
        assert profile.descriptor.voice.assets_created is False
        assert profile.descriptor.voice.model_id is None

    text_only_root = tmp_path / "text-only-assets"
    _copy_core_assets(
        text_only_root, "mack", ("constitution.md", "personality.json")
    )
    _copy_core_assets(
        text_only_root, "nova", ("constitution.md", "personality.json")
    )
    _copy_core_assets(
        text_only_root, "vera", ("constitution.md", "personality.json")
    )
    for number, original, builder in profiles:
        reduced = builder(IDS[number], resource_root=text_only_root)
        assert reduced.text_only is True
        assert reduced.avatar_present is False
        assert reduced.voice_present is False
        assert reduced.descriptor.full_name == original.descriptor.full_name
        assert reduced.descriptor.voice.assets_created is False
        assert reduced.descriptor.voice.model_id is None

    identities = MulticoreIdentityStore(tmp_path / "identities")
    service = MulticoreUnwrittenIdentity(
        canonical_state_path, IDS[7], identity_store=identities,
    )
    assert service.text_only is True
    assert service.avatar_required is False
    assert service.voice_required is False
    assert service.requires_running_model is False
    assert service.profile.avatar is None
    assert service.profile.voice is None


def test_twins_have_no_profiles_assets_packages_and_cannot_compose(tmp_path):
    assert {spec.core_number for spec in DEFAULT_CORE_PROFILES.specs()} == {2, 3, 6}
    for number in (4, 5):
        with pytest.raises(UnknownCoreProfile):
            DEFAULT_CORE_PROFILES.resolve(number)
        with pytest.raises(UniversalFacadeError):
            build_universal_participant(number, uuid4())

    packages = CorePackageRegistry()
    assert packages.manifests() == ()
    for selector in (4, 5, "twin-a", "twin-b"):
        with pytest.raises(KeyError):
            packages.resolve(selector)

    asset_directories = {
        path.name
        for path in CORE_ROOT.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert {"mack", "nova", "vera", "unwritten", "sofia"} <= asset_directories
    assert not (CORE_ROOT / "cores").exists()
    assert not any(
        name in asset_directories for name in ("4", "5", "twin-a", "twin-b")
    )
    with pytest.raises(UniversalFacadeError):
        build_universal_roster({**IDS, 4: uuid4()})


def test_restart_preserves_core_identity_model_binding_and_personality(
    canonical_state_path, tmp_path
):
    directory = tmp_path / "identities"
    store = MulticoreIdentityStore(directory, sofia_instance_id=IDS[1])
    mack = mack_core_profile(IDS[2])
    nova = nova_core_profile(IDS[3])
    vera = vera_core_profile(IDS[6])
    for profile in (mack, nova, vera):
        _register(store, profile)
    _register_blank(store)

    bindings = {
        2: ("model:alpha", "provider:one"),
        3: ("model:beta", "provider:two"),
        6: ("model:alpha", "provider:two"),
        7: ("model:gamma", "provider:three"),
    }
    for number, (model_id, provider_id) in bindings.items():
        store.bind_model(
            IDS[number],
            model_id=model_id,
            provider_id=provider_id,
            bound_at=NOW,
        )
    before = {record.identity.core_number: record for record in store.load_all()}
    assert set(before) == {2, 3, 6, 7}
    assert all(
        record.identity.core_id != IDS[1] for record in before.values()
    )

    before_personality = {
        2: MACK_FULLER_PROFILE.seed_state(IDS[2], now=NOW),
        3: NOVA_ARDEN_PROFILE.seed_state(IDS[3], now=NOW),
    }
    memory = {
        number: MulticoreMemoryStore(canonical_state_path, IDS[number])
        for number in bindings
    }
    for number, memory_store in memory.items():
        memory_store.persist(
            _memory_record(IDS[number], f"Core #{number} restart memory")
        )

    restarted = MulticoreIdentityStore(directory, sofia_instance_id=IDS[1])
    after = {
        record.identity.core_number: record for record in restarted.load_all()
    }
    assert set(after) == set(before)
    for number, previous in before.items():
        current = after[number]
        assert current.identity == previous.identity
        assert current.slug == previous.slug
        assert current.model_id == bindings[number][0]
        assert current.provider_id == bindings[number][1]

    for number, previous_state in before_personality.items():
        profile = MACK_FULLER_PROFILE if number == 2 else NOVA_ARDEN_PROFILE
        current_state = profile.seed_state(IDS[number], now=NOW)
        assert personality_is_same_continuous_identity(
            previous_state, current_state
        )
        assert previous_state.weights() == current_state.weights()

    for number in bindings:
        restarted_memory = MulticoreMemoryStore(
            canonical_state_path, IDS[number]
        )
        assert {
            record.content for record in restarted_memory.active_records()
        } == {f"Core #{number} restart memory"}

    assert SofiaIdentity(
        name="Sofía Ada Lyra", instance_id=IDS[1]
    ).instance_id == IDS[1]
    with pytest.raises(SofiaIdentitySubstitution):
        restarted.load(IDS[1])
