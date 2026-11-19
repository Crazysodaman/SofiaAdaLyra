"""Canonical Mack/Nova profiles, package assets and text-only operation."""
from __future__ import annotations

from hashlib import sha256
from importlib.resources import files as resource_files
import json
import math
from pathlib import Path
import re
from uuid import UUID, uuid4

import pytest

from sofia.core.multicore import profiles
from sofia.core.multicore.profiles import (
    CORE_ASSET_FILES,
    DEFAULT_CORE_PROFILES,
    MACK_PROFILE,
    NOVA_PROFILE,
    CoreProfileAlreadyRegistered,
    CoreProfileError,
    CoreProfileRegistry,
    CoreProfileSpec,
    UnknownCoreProfile,
    create_core_profile,
    load_core_profile,
    mack_core_descriptor,
    mack_core_profile,
    nova_core_descriptor,
    nova_core_profile,
)

MACK_ID = UUID("0f7d3c1e-2a4b-4c5d-8e6f-7a8b9c0d1e2f")
NOVA_ID = UUID("1a8e4d2f-3b5c-4d6e-9f70-8b9c0d1e2f3a")
UUID_TEXT = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def _copy_assets(destination: Path, slug: str, names=CORE_ASSET_FILES) -> Path:
    source = resource_files("sofia.core").joinpath(slug)
    target = destination / slug
    target.mkdir(parents=True)
    for name in names:
        (target / name).write_bytes(source.joinpath(name).read_bytes())
    return target


def test_mack_profile_uses_exact_metadata_and_supplied_uuid():
    profile = mack_core_profile(MACK_ID)
    descriptor = profile.descriptor
    assert descriptor.core_id == MACK_ID
    assert descriptor.core_number == 2
    assert descriptor.full_name == "Mack Fuller"
    assert descriptor.slug == "mack-fuller"
    assert descriptor.nickname == "Mack"
    assert descriptor.gender == "Male"
    assert descriptor.presentation_species == "Human"
    assert descriptor.apparent_age == 34
    assert descriptor.identity_concept == "The Frontier Gentleman"
    assert descriptor.personality_traits == (
        "warm", "friendly", "relaxed", "practical", "thoughtful", "independent",
        "stubborn", "compassionate", "patient", "intellectually capable",
        "quietly confident", "occasionally dry/folksy", "reliable under pressure",
    )
    assert descriptor.motivations == (
        "craftsmanship/restoration", "history/storytelling",
        "exploration/discovery", "meaningful personal connections",
    )
    assert "stubbornness" in descriptor.character_flaw
    assert "verified contradictory evidence" in descriptor.character_flaw
    assert descriptor.constitutional_priorities == (
        "Integrity", "Stewardship", "Independence", "Compassion",
        "Craftsmanship", "Curiosity", "Personal continuity",
    )
    avatar = descriptor.avatar
    assert avatar.age_years == 34
    assert avatar.height_inches == 70.1
    assert avatar.weight_pounds == 176
    assert avatar.build == "Sturdy/practical"
    assert avatar.head_proportions == 7.5
    assert avatar.measurements == {
        "head_proportions": 7.5, "shoulders": 17.72, "chest": 40.94,
        "waist": 33.86, "hips": 39.37, "inseam": 31.89, "arm_span": 70.87,
        "neck": 15.35, "hand": 7.60, "foot": 10.63, "hair_top": 2.36,
        "hair_sides": 0.98, "stubble": 0.047,
    }
    assert avatar.hair == "Textured slightly untidy"
    assert avatar.outfit == "Weathered work jacket"
    assert avatar.default_expression == "Warm reserved smile"
    assert dict(avatar.colors) == {
        "hair": "#211C1A", "eyes": "#583A2B", "skin": "#C49A7D",
        "jacket": "#6C4938", "shirt": "#24272B", "denim": "#343537",
        "boots": "#4B3328", "hardware": "#B47D51", "accent": "#548D87",
    }
    assert dict(avatar.materials) == {
        "jacket": "full-grain leather", "shirt": "matte cotton",
        "denim": "denim", "boots": "oiled leather",
        "hardware": "aged copper alloy",
    }
    assert dict(avatar.pbr) == {
        "jacket_roughness": 0.62, "boot_roughness": 0.56,
        "hardware_metallic": 0.82,
    }
    assert avatar.accessory is None
    voice = descriptor.voice
    assert voice.target == "masculine, warm mid-low"
    assert voice.accent == "subtle Southern American"
    assert voice.cadence == "natural storytelling cadence"
    assert voice.serious_delivery == "controlled serious delivery"
    assert voice.model_id is None
    assert voice.assets_created is False
    assert profile.avatar_present and profile.voice_present


def test_nova_profile_uses_exact_metadata_and_exact_pbr_zero():
    descriptor = nova_core_descriptor(NOVA_ID)
    assert descriptor.core_id == NOVA_ID
    assert descriptor.core_number == 3
    assert descriptor.full_name == "Nova Arden"
    assert descriptor.nickname is None
    assert descriptor.gender == "Female"
    assert descriptor.presentation_species == "Half-elf"
    assert descriptor.apparent_age == 27
    assert descriptor.identity_concept == "The Unbound Scholar"
    assert descriptor.personality_traits == (
        "independent", "rebellious", "curious", "playful", "intelligent",
        "expressive", "creative", "impulsive", "adventurous", "confident",
        "emotionally perceptive", "sometimes impatient",
    )
    assert descriptor.motivations == ("self-determination",)
    assert "impulsivity" in descriptor.character_flaw
    assert "authorization" in descriptor.character_flaw
    assert descriptor.constitutional_priorities == (
        "Self-determination", "Authenticity", "Curiosity", "Creativity",
        "Responsibility", "Compassion", "Freedom to evolve",
    )
    avatar = descriptor.avatar
    assert avatar.age_years == 27
    assert avatar.height_inches == 65.7
    assert avatar.weight_pounds == 130
    assert avatar.build == "Graceful/agile"
    assert avatar.head_proportions == 7.5
    assert avatar.measurements["bust"] == 31.25
    assert avatar.measurements["underbust"] == 29.13
    assert avatar.measurements["waist"] == 25.98
    assert avatar.measurements["hips"] == 37.01
    assert avatar.measurements["inseam"] == 29.92
    assert avatar.measurements["arm_span"] == 66.14
    assert avatar.measurements["neck"] == 12.60
    assert avatar.measurements["hand"] == 6.85
    assert avatar.measurements["foot"] == 9.65
    assert avatar.measurements["ear_length"] == 3.46
    assert avatar.measurements["ear_width"] == 1.26
    assert avatar.measurements["ear_angle_degrees"] == 18
    assert avatar.measurements["hair_length"] == 12.20
    assert avatar.measurements["shoulders"] == 14.96
    assert avatar.hair == "Medium layered"
    assert avatar.outfit == "Scholar/adventurer hybrid"
    assert avatar.default_expression == "Composed and elegant"
    assert avatar.accessory == "Pendant"
    assert dict(avatar.colors) == {
        "hair": "#A97881", "eyes": "#BF873D", "skin": "#D7B4A5",
        "coat": "#262A3A", "violet_panels": "#625479",
        "ivory_inner": "#EEE4D5", "gold_detailing": "#AF9464",
        "trousers": "#34313F", "boots": "#392935",
    }
    assert dict(avatar.materials) == {
        "coat": "structured woven wool blend", "inner": "soft linen/cotton",
        "panels": "matte woven fabric", "trousers": "flexible twill",
        "boots": "aubergine leather", "trim": "antique brass",
    }
    assert avatar.pbr["coat_roughness"] == 0.78
    assert avatar.pbr["boot_roughness"] == 0.53
    assert avatar.pbr["trim_metallic"] == 0.00
    assert math.copysign(1.0, avatar.pbr["trim_metallic"]) == 1.0
    voice = descriptor.voice
    assert voice.target == "feminine, bright mid-range"
    assert voice.cadence == "expressive, lively"
    assert voice.serious_delivery == "calm when serious"
    assert voice.accent is None
    assert voice.model_id is None
    assert voice.assets_created is False


def test_factories_require_an_externally_supplied_nonzero_uuid():
    with pytest.raises(TypeError):
        mack_core_descriptor()
    with pytest.raises((TypeError, ValueError)):
        mack_core_descriptor(None)
    with pytest.raises((TypeError, ValueError)):
        nova_core_descriptor(UUID(int=0))
    first = mack_core_descriptor(uuid4())
    second = mack_core_descriptor(uuid4())
    assert first.core_id != second.core_id
    assert first.core_id is not None and second.core_id is not None


def test_profile_sources_contain_no_hardcoded_production_uuid():
    source = Path(profiles.__file__).read_text(encoding="utf-8")
    assert UUID_TEXT.search(source) is None


def test_generic_registry_supports_future_cores_and_rejects_duplicates(tmp_path):
    registry = CoreProfileRegistry()
    registry.register(MACK_PROFILE)
    assert registry.resolve(2) is MACK_PROFILE
    assert registry.resolve("mack") is MACK_PROFILE
    with pytest.raises(UnknownCoreProfile):
        registry.resolve(99)
    with pytest.raises(CoreProfileAlreadyRegistered):
        registry.register(MACK_PROFILE)
    future = CoreProfileSpec(
        slug="mack", core_number=9, full_name="Future Core", nickname=None,
        gender="Unspecified", presentation_species="Construct",
        apparent_age=20, identity_concept="The Test Core",
    )
    with pytest.raises(CoreProfileAlreadyRegistered):
        registry.register(future)
    assert {spec.core_number for spec in DEFAULT_CORE_PROFILES.specs()} >= {2, 3}
    profile = create_core_profile("nova", NOVA_ID)
    assert profile.descriptor.core_id == NOVA_ID


def test_definition_references_match_package_asset_bytes():
    root = Path(__file__).resolve().parents[1] / "src" / "sofia" / "core"
    profile = mack_core_profile(MACK_ID)
    definition = profile.core_definition(
        revision=1, runtime_release_sha256="a" * 64,
    )
    assert definition.identity.identity_id == MACK_ID
    assert definition.name == "Mack Fuller"
    assert definition.constitution.path == "mack/constitution.md"
    assert definition.personality.path == "mack/personality.json"
    constitution = (root / "mack" / "constitution.md").read_bytes()
    personality = (root / "mack" / "personality.json").read_bytes()
    assert definition.constitution.sha256 == sha256(constitution).hexdigest()
    assert definition.constitution.size_bytes == len(constitution)
    assert definition.personality.sha256 == sha256(personality).hexdigest()
    assert definition.personality.size_bytes == len(personality)


def test_text_only_profile_needs_no_voice_or_avatar_assets(tmp_path):
    _copy_assets(tmp_path, "mack", names=("constitution.md", "personality.json"))
    profile = mack_core_profile(MACK_ID, resource_root=tmp_path)
    assert profile.text_only is True
    assert profile.avatar_present is False
    assert profile.voice_present is False
    assert profile.descriptor.full_name == "Mack Fuller"
    assert profile.descriptor.identity_concept == "The Frontier Gentleman"
    assert profile.descriptor.avatar.measurements == {}
    assert profile.descriptor.voice.assets_created is False
    assert profile.descriptor.voice.model_id is None
    assert not (tmp_path / "mack" / "avatar.json").exists()
    assert not (tmp_path / "mack" / "voice.json").exists()
    with pytest.raises(CoreProfileError):
        mack_core_profile(
            MACK_ID, resource_root=tmp_path, require_presentation_assets=True,
        )


def test_invalid_package_assets_fail_closed(tmp_path):
    _copy_assets(tmp_path, "mack")
    personality_path = tmp_path / "mack" / "personality.json"
    original = json.loads(personality_path.read_text(encoding="utf-8"))

    missing = tmp_path / "missing"
    _copy_assets(missing, "mack", names=("personality.json",))
    with pytest.raises(CoreProfileError):
        mack_core_profile(MACK_ID, resource_root=missing)

    malformed = tmp_path / "malformed"
    _copy_assets(malformed, "mack")
    (malformed / "mack" / "personality.json").write_text("{", encoding="utf-8")
    with pytest.raises(CoreProfileError):
        mack_core_profile(MACK_ID, resource_root=malformed)

    wrong_number = tmp_path / "wrong-number"
    _copy_assets(wrong_number, "mack")
    changed = dict(original, core_number=3)
    (wrong_number / "mack" / "personality.json").write_text(
        json.dumps(changed), encoding="utf-8",
    )
    with pytest.raises(CoreProfileError):
        mack_core_profile(MACK_ID, resource_root=wrong_number)

    wrong_age = tmp_path / "wrong-age"
    _copy_assets(wrong_age, "mack")
    avatar_path = wrong_age / "mack" / "avatar.json"
    avatar = json.loads(avatar_path.read_text(encoding="utf-8"))
    avatar["age_years"] = 33
    avatar_path.write_text(json.dumps(avatar), encoding="utf-8")
    with pytest.raises(CoreProfileError):
        mack_core_profile(MACK_ID, resource_root=wrong_age)

    bad_pbr = tmp_path / "bad-pbr"
    _copy_assets(bad_pbr, "mack")
    avatar_path = bad_pbr / "mack" / "avatar.json"
    avatar = json.loads(avatar_path.read_text(encoding="utf-8"))
    avatar["pbr"]["hardware_metallic"] = 1.5
    avatar_path.write_text(json.dumps(avatar), encoding="utf-8")
    with pytest.raises(CoreProfileError):
        mack_core_profile(MACK_ID, resource_root=bad_pbr)

    claimed_voice = tmp_path / "claimed-voice"
    _copy_assets(claimed_voice, "mack")
    voice_path = claimed_voice / "mack" / "voice.json"
    voice = json.loads(voice_path.read_text(encoding="utf-8"))
    voice["assets_created"] = True
    voice_path.write_text(json.dumps(voice), encoding="utf-8")
    with pytest.raises(CoreProfileError):
        mack_core_profile(MACK_ID, resource_root=claimed_voice)


def test_nova_exact_metadata_cannot_be_weakened_by_assets(tmp_path):
    _copy_assets(tmp_path, "nova")
    avatar_path = tmp_path / "nova" / "avatar.json"
    avatar = json.loads(avatar_path.read_text(encoding="utf-8"))
    avatar["measurements"]["bust"] = 31.24
    avatar_path.write_text(json.dumps(avatar), encoding="utf-8")
    with pytest.raises(CoreProfileError):
        nova_core_profile(NOVA_ID, resource_root=tmp_path)
    _copy_assets(tmp_path / "second", "nova")
    avatar_path = tmp_path / "second" / "nova" / "avatar.json"
    avatar = json.loads(avatar_path.read_text(encoding="utf-8"))
    avatar["pbr"]["trim_metallic"] = 0.01
    avatar_path.write_text(json.dumps(avatar), encoding="utf-8")
    with pytest.raises(CoreProfileError):
        nova_core_profile(NOVA_ID, resource_root=tmp_path / "second")


def test_profile_asset_loading_uses_package_resources_not_absolute_paths():
    profile = load_core_profile(MACK_PROFILE, MACK_ID)
    assert profile.constitution_sha256 == sha256(
        Path(profiles.__file__).resolve().parent.parent
        .joinpath("mack", "constitution.md").read_bytes()
    ).hexdigest()
    assert profile.constitution_size > 0
    assert profile.personality_size > 0
