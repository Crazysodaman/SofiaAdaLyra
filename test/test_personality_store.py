import json

import pytest

from sofia.personality.model import PersonalityProfile
from sofia.personality.store import (
    PersonalityStore,
    PersonalityStoreError,
)


def create_profile() -> PersonalityProfile:
    return PersonalityProfile(
        name="Sofía Ada Lyra",
        traits=(
            "analytical",
            "blunt",
            "curious",
            "playful",
        ),
        communication_style="direct and rigorous",
        embodiment_guidance=(
            "Embodied expression should remain natural and varied."
        ),
    )


def test_personality_store_saves_profile(tmp_path):
    path = tmp_path / "personality.json"
    store = PersonalityStore(path)

    profile = create_profile()

    store.save(profile)

    assert path.exists()

    data = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    assert data == {
        "name": "Sofía Ada Lyra",
        "traits": [
            "analytical",
            "blunt",
            "curious",
            "playful",
        ],
        "communication_style": "direct and rigorous",
        "embodiment_guidance": (
            "Embodied expression should remain natural and varied."
        ),
    }


def test_personality_store_loads_profile(tmp_path):
    path = tmp_path / "personality.json"
    store = PersonalityStore(path)

    profile = create_profile()
    store.save(profile)

    loaded = store.load()

    assert loaded == profile


def test_personality_store_preserves_trait_order(tmp_path):
    path = tmp_path / "personality.json"
    store = PersonalityStore(path)

    profile = PersonalityProfile(
        name="Sofía",
        traits=("third", "first", "second"),
        communication_style="direct",
    )

    store.save(profile)

    loaded = store.load()

    assert loaded.traits == (
        "third",
        "first",
        "second",
    )


def test_personality_store_preserves_embodiment_guidance(tmp_path):
    path = tmp_path / "personality.json"
    store = PersonalityStore(path)

    profile = PersonalityProfile(
        name="Sofía",
        communication_style="direct",
        embodiment_guidance="Natural and varied.",
    )

    store.save(profile)

    loaded = store.load()

    assert (
        loaded.embodiment_guidance
        == "Natural and varied."
    )


def test_personality_store_accepts_legacy_profile_without_embodiment_guidance(
    tmp_path,
):
    path = tmp_path / "personality.json"

    path.write_text(
        json.dumps({
            "name": "Sofía",
            "traits": ["direct"],
            "communication_style": "direct",
        }),
        encoding="utf-8",
    )

    store = PersonalityStore(path)

    loaded = store.load()

    assert loaded.embodiment_guidance == ""


def test_personality_store_rejects_invalid_save_type(tmp_path):
    path = tmp_path / "personality.json"
    store = PersonalityStore(path)

    with pytest.raises(TypeError, match="PersonalityProfile"):
        store.save("not a personality profile")


def test_personality_store_missing_file_raises(tmp_path):
    path = tmp_path / "personality.json"
    store = PersonalityStore(path)

    with pytest.raises(
        PersonalityStoreError,
        match="does not exist",
    ):
        store.load()


def test_personality_store_malformed_json_raises(tmp_path):
    path = tmp_path / "personality.json"
    path.write_text(
        "{not valid json",
        encoding="utf-8",
    )

    store = PersonalityStore(path)

    with pytest.raises(
        PersonalityStoreError,
        match="Failed to load",
    ):
        store.load()


def test_personality_store_rejects_non_object_json(tmp_path):
    path = tmp_path / "personality.json"
    path.write_text(
        '["not", "an", "object"]',
        encoding="utf-8",
    )

    store = PersonalityStore(path)

    with pytest.raises(
        PersonalityStoreError,
        match="JSON object",
    ):
        store.load()


def test_personality_store_rejects_missing_field(tmp_path):
    path = tmp_path / "personality.json"
    path.write_text(
        json.dumps({
            "name": "Sofía",
            "traits": [],
        }),
        encoding="utf-8",
    )

    store = PersonalityStore(path)

    with pytest.raises(
        PersonalityStoreError,
        match="required field",
    ):
        store.load()


def test_personality_store_rejects_invalid_traits(tmp_path):
    path = tmp_path / "personality.json"
    path.write_text(
        json.dumps({
            "name": "Sofía",
            "traits": ["valid", 123],
            "communication_style": "direct",
        }),
        encoding="utf-8",
    )

    store = PersonalityStore(path)

    with pytest.raises(
        PersonalityStoreError,
        match="contain strings",
    ):
        store.load()