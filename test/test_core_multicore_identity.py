"""Persistent independent Core identity records and writer-generation fencing."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from sofia.core.multicore.identity import (
    CoreIdentityNotFound,
    DuplicateActiveWriterGeneration,
    DuplicateCoreIdentity,
    MulticoreIdentityError,
    MulticoreIdentityStore,
    SofiaIdentitySubstitution,
    StaleWriterGeneration,
    WriterFenceMismatch,
)
from sofia.core.multicore.profiles import mack_core_profile, nova_core_profile

MACK_ID = UUID("2b9f5e3a-4c6d-4e7f-8a91-9c0d1e2f3a4b")
NOVA_ID = UUID("3c0a6f4b-5d7e-4f80-9ba2-ad1e2f3a4b5c")
SOFIA_ID = UUID("4d1b7a5c-6e8f-4081-acb3-be2f3a4b5c6d")


def _register_mack(store: MulticoreIdentityStore, core_id: UUID = MACK_ID):
    profile = mack_core_profile(core_id)
    return store.register_descriptor(
        profile.descriptor,
        constitution_sha256=profile.constitution_sha256,
    )


def test_supplied_uuid_persists_across_restart(tmp_path):
    store = MulticoreIdentityStore(tmp_path / "cores")
    record = _register_mack(store)
    assert record.identity.core_id == MACK_ID
    assert record.identity.core_number == 2
    assert record.identity.full_name == "Mack Fuller"
    assert record.identity.generation == 1
    assert record.identity.slug == "mack-fuller"

    restarted = MulticoreIdentityStore(tmp_path / "cores")
    loaded = restarted.load(MACK_ID)
    assert loaded == record
    assert restarted.load_all() == (record,)


def test_missing_record_is_never_replaced_by_sofia_or_a_new_identity(tmp_path):
    store = MulticoreIdentityStore(tmp_path / "cores", sofia_instance_id=SOFIA_ID)
    with pytest.raises(CoreIdentityNotFound):
        store.load(MACK_ID)
    assert list((tmp_path / "cores").glob("*.json")) == []


def test_duplicate_uuid_number_and_slug_are_rejected(tmp_path):
    store = MulticoreIdentityStore(tmp_path / "cores")
    _register_mack(store)
    with pytest.raises(DuplicateCoreIdentity):
        _register_mack(store, MACK_ID)
    with pytest.raises(DuplicateCoreIdentity):
        store.register(
            core_id=uuid4(), core_number=2, full_name="Another Two",
            slug="another-two", constitution_sha256="b" * 64,
        )
    with pytest.raises(DuplicateCoreIdentity):
        store.register(
            core_id=uuid4(), core_number=7, full_name="Another Mack",
            slug="mack-fuller", constitution_sha256="c" * 64,
        )
    assert len(store.load_all()) == 1


def test_sofia_identity_cannot_be_substituted(tmp_path):
    store = MulticoreIdentityStore(
        tmp_path / "cores", sofia_instance_id=SOFIA_ID,
        protected_identity_ids=(NOVA_ID,),
    )
    with pytest.raises(SofiaIdentitySubstitution):
        store.register(
            core_id=SOFIA_ID, core_number=1, full_name="Sofia Ada Lyra",
            slug="sofia", constitution_sha256="a" * 64,
        )
    with pytest.raises(SofiaIdentitySubstitution):
        store.register(
            core_id=NOVA_ID, core_number=3, full_name="Nova Arden",
            slug="nova", constitution_sha256="a" * 64,
        )
    with pytest.raises(SofiaIdentitySubstitution):
        store.load(SOFIA_ID)
    assert store.load_all() == ()
    assert not any(path.name == "identity.json" for path in tmp_path.rglob("*"))


def test_protected_canonical_state_paths_are_refused(tmp_path):
    with pytest.raises(PermissionError):
        MulticoreIdentityStore(tmp_path / "state" / "sofia.db")
    with pytest.raises(PermissionError):
        MulticoreIdentityStore(tmp_path / "sofia.db" / "cores")
    with pytest.raises(ValueError):
        MulticoreIdentityStore(Path("relative") / "cores")


def test_duplicate_active_writer_generation_is_fenced(tmp_path):
    store = MulticoreIdentityStore(tmp_path / "cores")
    _register_mack(store)
    first = store.claim_writer(
        MACK_ID, writer_id="writer:alpha", expected_generation=1,
    )
    assert first.identity.generation == 2
    assert first.writer_fence is not None
    assert first.writer_fence.generation == 2
    with pytest.raises(DuplicateActiveWriterGeneration):
        store.claim_writer(
            MACK_ID, writer_id="writer:beta", expected_generation=2,
        )
    with pytest.raises(DuplicateActiveWriterGeneration):
        store.claim_writer(
            MACK_ID, writer_id="writer:alpha", expected_generation=2,
        )
    with pytest.raises(WriterFenceMismatch):
        store.release_writer(
            MACK_ID, writer_id="writer:beta", generation=2,
        )
    released = store.release_writer(
        MACK_ID, writer_id="writer:alpha", generation=2,
    )
    assert released.writer_fence is None
    assert released.identity.generation == 2
    with pytest.raises(StaleWriterGeneration):
        store.claim_writer(
            MACK_ID, writer_id="writer:beta", expected_generation=1,
        )
    second = store.claim_writer(
        MACK_ID, writer_id="writer:beta", expected_generation=2,
    )
    assert second.identity.generation == 3
    assert second.writer_fence is not None
    assert second.writer_fence.writer_id == "writer:beta"
    restarted = MulticoreIdentityStore(tmp_path / "cores")
    assert restarted.load(MACK_ID).writer_fence == second.writer_fence


def test_writer_fence_survives_restart_and_cannot_be_duplicated(tmp_path):
    store = MulticoreIdentityStore(tmp_path / "cores")
    _register_mack(store)
    store.claim_writer(MACK_ID, writer_id="writer:alpha", expected_generation=1)
    restarted = MulticoreIdentityStore(tmp_path / "cores")
    with pytest.raises(DuplicateActiveWriterGeneration):
        restarted.claim_writer(
            MACK_ID, writer_id="writer:beta", expected_generation=2,
        )


def test_model_and_provider_switch_preserves_identity_continuity(tmp_path):
    store = MulticoreIdentityStore(tmp_path / "cores")
    registered = _register_mack(store)
    store.claim_writer(MACK_ID, writer_id="writer:alpha", expected_generation=1)
    before = store.load(MACK_ID)
    switched = store.bind_model(
        MACK_ID, model_id="model:first", provider_id="provider:alpha",
    )
    assert switched.identity.core_id == registered.identity.core_id
    assert switched.identity.core_number == registered.identity.core_number
    assert switched.identity.full_name == registered.identity.full_name
    assert switched.identity.slug == registered.identity.slug
    assert switched.identity.generation == before.identity.generation == 2
    assert switched.writer_fence == before.writer_fence
    assert switched.model_id == "model:first"
    assert switched.provider_id == "provider:alpha"

    restarted = MulticoreIdentityStore(tmp_path / "cores")
    assert restarted.load(MACK_ID).model_id == "model:first"
    second = restarted.bind_model(
        MACK_ID, model_id="model:second", provider_id="provider:beta",
    )
    assert second.identity.core_id == registered.identity.core_id
    assert second.identity.generation == 2
    assert second.model_id == "model:second"
    assert second.provider_id == "provider:beta"


def test_nova_identity_is_independent_of_mack_and_sofia(tmp_path):
    store = MulticoreIdentityStore(tmp_path / "cores", sofia_instance_id=SOFIA_ID)
    mack = _register_mack(store)
    profile = nova_core_profile(NOVA_ID)
    nova = store.register_descriptor(
        profile.descriptor,
        constitution_sha256=profile.constitution_sha256,
    )
    assert nova.identity.core_id == NOVA_ID
    assert nova.identity.core_id != mack.identity.core_id
    assert nova.identity.core_id != SOFIA_ID
    assert nova.identity.constitution_sha256 != mack.identity.constitution_sha256
    assert {record.identity.core_number for record in store.load_all()} == {2, 3}


def test_identity_record_files_are_owner_private_and_strict(tmp_path):
    store = MulticoreIdentityStore(tmp_path / "cores")
    _register_mack(store)
    paths = list((tmp_path / "cores").glob("*.json"))
    assert [path.name for path in paths] == [f"{MACK_ID}.json"]
    payload = json.loads(paths[0].read_text(encoding="utf-8"))
    payload["owner_authenticated"] = True
    paths[0].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MulticoreIdentityError):
        store.load(MACK_ID)


def test_sofia_identity_constitution_and_protected_assets_are_unchanged(tmp_path):
    core_root = Path(__file__).resolve().parents[1] / "src" / "sofia" / "core"
    protected = (
        core_root / "identity" / "identity.json",
        core_root / "constitution" / "constitution.md",
        core_root / "constitution" / "constitution.sha256",
        core_root / "personality" / "personality.json",
        core_root / "embodiment" / "avatar.json",
    )
    before = {path: path.read_bytes() for path in protected}
    store = MulticoreIdentityStore(tmp_path / "cores", sofia_instance_id=SOFIA_ID)
    _register_mack(store)
    profile = nova_core_profile(NOVA_ID)
    store.register_descriptor(
        profile.descriptor, constitution_sha256=profile.constitution_sha256,
    )
    store.claim_writer(MACK_ID, writer_id="writer:alpha", expected_generation=1)
    store.bind_model(MACK_ID, model_id="model:test", provider_id="provider:test")
    after = {path: path.read_bytes() for path in protected}
    assert after == before


def test_created_at_must_be_timezone_aware(tmp_path):
    store = MulticoreIdentityStore(tmp_path / "cores")
    with pytest.raises(MulticoreIdentityError):
        store.register(
            core_id=MACK_ID, core_number=2, full_name="Mack Fuller",
            slug="mack-fuller", constitution_sha256="a" * 64,
            created_at=datetime(2026, 1, 1),
        )
    assert not (tmp_path / "cores" / f"{MACK_ID}.json").exists()
