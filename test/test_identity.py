from pathlib import Path
from uuid import UUID

import pytest

from sofia.identity.model import SofiaIdentity
from sofia.identity.store import IdentityStore, IdentityStoreError


def create_identity(
    name: str = "Sofía Ada Lyra",
) -> SofiaIdentity:
    return SofiaIdentity(
        name=name,
        instance_id=UUID(
            "12345678-1234-5678-1234-567812345678"
        ),
    )


def test_identity_stores_name():
    identity = create_identity()

    assert identity.name == "Sofía Ada Lyra"


def test_identity_stores_instance_id():
    identity = create_identity()

    assert identity.instance_id == UUID(
        "12345678-1234-5678-1234-567812345678"
    )


def test_identity_instance_id_is_uuid():
    identity = create_identity()

    assert isinstance(identity.instance_id, UUID)


def test_identity_name_is_string():
    identity = create_identity()

    assert isinstance(identity.name, str)


def test_identity_is_immutable():
    identity = create_identity()

    with pytest.raises(AttributeError):
        identity.name = "Something Else"


def test_identity_store_saves_identity(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    store = IdentityStore(identity_path)

    identity = create_identity()

    store.save(identity)

    assert identity_path.exists()


def test_identity_store_loads_saved_identity(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    store = IdentityStore(identity_path)

    original = create_identity(
        name="Nyx",
    )

    store.save(original)

    loaded = store.load()

    assert loaded == original


def test_identity_store_creates_canonical_identity_when_missing(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"
    store = IdentityStore(identity_path)

    identity = store.load()

    assert identity.name == "Sofía Ada Lyra"
    assert isinstance(identity.instance_id, UUID)


def test_identity_store_persists_generated_identity_when_missing(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"
    store = IdentityStore(identity_path)

    first = store.load()
    second = store.load()

    assert first == second
    assert identity_path.exists()


def test_identity_store_preserves_changed_name(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"
    store = IdentityStore(identity_path)

    identity = create_identity(
        name="Nyx",
    )

    store.save(identity)

    loaded = store.load()

    assert loaded.name == "Nyx"
    assert loaded.instance_id == identity.instance_id


def test_identity_store_creates_parent_directory(
    tmp_path: Path,
):
    identity_path = tmp_path / "nested" / "identity.json"
    store = IdentityStore(identity_path)

    store.save(create_identity())

    assert identity_path.exists()


def test_identity_store_rejects_malformed_json(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        "{not valid json",
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_rejects_missing_name(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        "{}",
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_rejects_non_string_name(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        '{"name": 123}',
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_rejects_empty_name(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        '{"name": ""}',
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_rejects_whitespace_name(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        '{"name": "   "}',
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_upgrades_legacy_identity(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        '{"name": "Sofía Ada Lyra"}',
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    identity = store.load()

    assert identity.name == "Sofía Ada Lyra"
    assert isinstance(identity.instance_id, UUID)

    reloaded = store.load()

    assert reloaded == identity


def test_identity_store_rejects_non_string_instance_id(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        '{"name": "Sofía Ada Lyra", "instance_id": 123}',
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_rejects_invalid_instance_id(
    tmp_path: Path,
):
    identity_path = tmp_path / "identity.json"

    identity_path.write_text(
        '{"name": "Sofía Ada Lyra", "instance_id": "not-a-uuid"}',
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()