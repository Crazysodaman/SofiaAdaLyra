"""Workstream C: protected per-Core continuity across restart and model switch."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.core.multicore.continuity import (
    CONTINUITY_SCHEMA,
    ContinuityIntegrityError,
    CoreContinuityState,
    CoreContinuityStore,
)
from sofia.core.multicore.contracts import (
    AvatarMetadata,
    CoreDescriptor,
    VoiceMetadata,
)

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=timezone.utc)
CONSTITUTION = "a" * 64


def descriptor(
    *,
    full_name: str = "Mack Fuller",
    core_number: int = 2,
    core_id=None,
) -> CoreDescriptor:
    return CoreDescriptor(
        core_number=core_number,
        full_name=full_name,
        nickname=full_name.split()[0],
        gender="male",
        presentation_species="human",
        apparent_age=29,
        identity_concept="continuous independent Core identity",
        personality_traits=("direct", "steady", "stubborn"),
        motivations=("protect the people he trusts", "understand the work"),
        character_flaw="stubbornness",
        constitutional_priorities=("truth", "consent", "owner authority"),
        avatar=AvatarMetadata(
            age_years=29,
            height_inches=72.0,
            weight_pounds=180.0,
            build="athletic",
            head_proportions=0.13,
            measurements={"shoulder": 18.0},
            hair="dark",
            outfit="jacket",
            default_expression="calm",
            colors={"hair": "#1A1A1A", "eyes": "#4A6B52"},
            materials={"jacket": "cotton"},
            pbr={"roughness": 0.5},
        ),
        voice=VoiceMetadata(
            target="modeled-voice",
            register="low",
            accent=None,
            cadence="measured",
            serious_delivery="steady and direct",
        ),
        core_id=core_id,
    )


def test_continuity_survives_restart_and_model_switch(tmp_path):
    core_id = uuid4()
    path = tmp_path / "core-continuity.json"
    store = CoreContinuityStore(path)
    state = store.initialize(
        descriptor=descriptor(core_id=core_id),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    assert state.core_id == core_id
    assert state.identity.generation == 1
    memory_id = uuid4()
    store.record_memory(memory_id, now=NOW + timedelta(minutes=1))
    switched = store.switch_runtime(
        model_id="model-a",
        provider_id="provider-a",
        process_id="process-1",
        now=NOW + timedelta(minutes=2),
    )
    assert switched.model_id == "model-a"
    assert switched.core_id == core_id
    assert switched.memory_ids == (memory_id,)

    reopened = CoreContinuityStore(path)
    loaded = reopened.load(expected_core_id=core_id, descriptor=descriptor(core_id=core_id))
    assert loaded.core_id == core_id
    assert loaded.identity.created_at == NOW
    assert loaded.identity.constitution_sha256 == CONSTITUTION
    assert loaded.memory_ids == (memory_id,)
    assert loaded.model_id == "model-a"
    assert loaded.provider_id == "provider-a"

    switched_again = reopened.switch_runtime(
        model_id="model-b",
        provider_id="provider-b",
        process_id="process-2",
        now=NOW + timedelta(minutes=3),
    )
    assert switched_again.core_id == core_id
    assert switched_again.identity == loaded.identity
    assert switched_again.memory_ids == (memory_id,)
    assert switched_again.model_id == "model-b"


def test_missing_continuity_fails_closed_without_creating_a_replacement(tmp_path):
    path = tmp_path / "core-continuity.json"
    store = CoreContinuityStore(path)
    with pytest.raises(ContinuityIntegrityError, match="missing"):
        store.load()
    with pytest.raises(ContinuityIntegrityError, match="missing"):
        store.load(expected_core_id=uuid4())
    assert not path.exists()


def test_initialize_refuses_to_replace_existing_identity(tmp_path):
    path = tmp_path / "core-continuity.json"
    store = CoreContinuityStore(path)
    first = store.initialize(
        descriptor=descriptor(core_id=uuid4()),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    with pytest.raises(ContinuityIntegrityError, match="refusing to mint"):
        CoreContinuityStore(path).initialize(
            descriptor=descriptor(core_id=uuid4()),
            constitution_sha256=CONSTITUTION,
            now=NOW + timedelta(minutes=1),
        )
    assert CoreContinuityStore(path).load().identity == first.identity


def test_corrupt_continuity_fails_closed_and_is_not_repaired(tmp_path):
    path = tmp_path / "core-continuity.json"
    store = CoreContinuityStore(path)
    state = store.initialize(
        descriptor=descriptor(),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    original = path.read_text(encoding="utf-8")
    corrupt = original.replace(str(state.core_id), str(uuid4()))
    assert corrupt != original
    path.write_text(corrupt, encoding="utf-8")
    before = path.read_text(encoding="utf-8")
    with pytest.raises(ContinuityIntegrityError):
        store.load()
    assert path.read_text(encoding="utf-8") == before


def test_identity_substitution_is_forbidden_on_save(tmp_path):
    first_path = tmp_path / "first.json"
    second_path = tmp_path / "second.json"
    first = CoreContinuityStore(first_path)
    first_state = first.initialize(
        descriptor=descriptor(core_id=uuid4()),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    second_state = CoreContinuityStore(second_path).initialize(
        descriptor=descriptor(core_id=uuid4()),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    before = first_path.read_text(encoding="utf-8")
    with pytest.raises(ContinuityIntegrityError, match="replacement"):
        first.save(second_state)
    assert first_path.read_text(encoding="utf-8") == before
    assert first.load().identity == first_state.identity


def test_descriptor_mismatch_and_wrong_expected_core_fail_closed(tmp_path):
    path = tmp_path / "core-continuity.json"
    store = CoreContinuityStore(path)
    state = store.initialize(
        descriptor=descriptor(core_id=uuid4()),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    with pytest.raises(ContinuityIntegrityError, match="different Core"):
        store.load(expected_core_id=uuid4())
    with pytest.raises(ContinuityIntegrityError, match="descriptor"):
        store.load(descriptor=descriptor(full_name="Nova Arden", core_number=3))
    assert store.verify(
        expected_core_id=state.core_id,
        descriptor=descriptor(core_id=state.core_id),
    ) is True


def test_memories_cannot_be_removed_or_replaced(tmp_path):
    path = tmp_path / "core-continuity.json"
    store = CoreContinuityStore(path)
    state = store.initialize(
        descriptor=descriptor(),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    memory_id = uuid4()
    state = state.with_memory(memory_id, now=NOW + timedelta(minutes=1))
    store.save(state)
    with pytest.raises(ContinuityIntegrityError, match="cannot be removed"):
        store.save(replace(
            state,
            memory_ids=(),
            revision=state.revision + 1,
            updated_at=NOW + timedelta(minutes=2),
        ))
    assert store.load().memory_ids == (memory_id,)


def test_personal_state_progress_is_monotonic_and_runtime_independent(tmp_path):
    path = tmp_path / "core-continuity.json"
    store = CoreContinuityStore(path)
    state = store.initialize(
        descriptor=descriptor(),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    advanced = state.with_personal_state(
        personality_revision=3,
        personality_digest="b" * 64,
        emotion_revision=4,
        relationships_revision=5,
        now=NOW + timedelta(minutes=1),
    )
    assert advanced.core_id == state.core_id
    assert advanced.personality_revision == 3
    with pytest.raises(ValueError, match="cannot move backward"):
        advanced.with_personal_state(
            personality_revision=2,
            personality_digest="b" * 64,
            emotion_revision=4,
            relationships_revision=5,
            now=NOW + timedelta(minutes=2),
        )
    store.save(advanced)
    loaded = store.load()
    assert isinstance(loaded, CoreContinuityState)
    assert loaded.schema == CONTINUITY_SCHEMA
    assert loaded.personality_digest == "b" * 64
    assert loaded.core_id == state.core_id


def test_record_memory_is_idempotent_and_never_replaces(tmp_path):
    path = tmp_path / "core-continuity.json"
    store = CoreContinuityStore(path)
    store.initialize(
        descriptor=descriptor(),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    memory_id = uuid4()
    first = store.record_memory(memory_id, now=NOW + timedelta(minutes=1))
    second = store.record_memory(memory_id, now=NOW + timedelta(minutes=2))
    assert first.memory_ids == (memory_id,)
    assert second.memory_ids == (memory_id,)
    assert second.revision == first.revision
