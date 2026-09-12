from pathlib import Path

import pytest

from sofia.identity.model import SofiaIdentity
from sofia.identity.store import IdentityStore, IdentityStoreError


def test_identity_stores_name():
    identity = SofiaIdentity(
        name="Sofía Ada Lyra",
    )

    assert identity.name == "Sofía Ada Lyra"


def test_identity_name_is_string():
    identity = SofiaIdentity(
        name="Sofía Ada Lyra",
    )

    assert isinstance(identity.name, str)


def test_identity_is_immutable():
    identity = SofiaIdentity(
        name="Sofía Ada Lyra",
    )

    with pytest.raises(AttributeError):
        identity.name = "Something Else"


def test_identity_store_saves_identity(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    store = IdentityStore(identity_path)

    identity = SofiaIdentity(
        name="Sofía Ada Lyra",
    )

    store.save(identity)

    assert identity_path.exists()


def test_identity_store_loads_saved_identity(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    store = IdentityStore(identity_path)

    original = SofiaIdentity(
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


def test_identity_store_preserves_changed_name(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    store = IdentityStore(identity_path)

    store.save(
        SofiaIdentity(
            name="Nyx",
        )
    )

    loaded = store.load()

    assert loaded.name == "Nyx"

def test_identity_store_creates_parent_directory(tmp_path: Path):
    identity_path = tmp_path / "nested" / "identity.json"
    store = IdentityStore(identity_path)

    store.save(
        SofiaIdentity(
            name="Nyx",
        )
    )

    assert identity_path.exists()


def test_identity_store_rejects_malformed_json(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(
        "{not valid json",
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_rejects_missing_name(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(
        "{}",
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_rejects_non_string_name(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(
        '{"name": 123}',
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_rejects_empty_name(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(
        '{"name": ""}',
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()


def test_identity_store_rejects_whitespace_name(tmp_path: Path):
    identity_path = tmp_path / "identity.json"
    identity_path.write_text(
        '{"name": "   "}',
        encoding="utf-8",
    )

    store = IdentityStore(identity_path)

    with pytest.raises(IdentityStoreError):
        store.load()