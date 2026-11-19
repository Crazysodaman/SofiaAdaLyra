"""Vera (Core #6) canonical assets, profile, appearance and authority boundary."""
from __future__ import annotations

from hashlib import sha256
from importlib.resources import files as resource_files
import json
import re
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from sofia.core.multicore import vera as vera_module
from sofia.core.multicore.profiles import (
    CORE_ASSET_FILES,
    DEFAULT_CORE_PROFILES,
    CoreProfileError,
    create_core_profile,
    mack_core_descriptor,
    nova_core_descriptor,
)
from sofia.core.multicore.vera import (
    APPEARANCE_FIELDS,
    VERA_APPEARANCE_AUTHORITY,
    VERA_ARMOR_HOOK,
    VERA_ASSET_FILES,
    VERA_AUTHORITY,
    VERA_CALLSIGN,
    VERA_COLORS,
    VERA_CORE_NUMBER,
    VERA_GENDER,
    VERA_HAIR_LENGTH_INCHES,
    VERA_HEIGHT_INCHES,
    VERA_MEASUREMENTS,
    VERA_PERSONA_CONCEPT,
    VERA_PERSONAL_NAME,
    VERA_PROFILE,
    VERA_SKIN_COLOR,
    VERA_SURNAME,
    VERA_VISUAL_SPECIES,
    VERA_VOICE_BREATHINESS,
    VERA_WEIGHT_POUNDS,
    AppearanceAuthority,
    VeraAppearanceAuthorityError,
    VeraAppearanceError,
    VeraAppearancePreferences,
    VeraAuthorityBoundary,
    initial_appearance_preferences,
    vera_asset_digests,
    vera_core_descriptor,
    vera_core_profile,
)

VERA_ID = UUID("2b9f5e3a-4c6d-4e7f-8a81-9c0d1e2f3a4b")
UUID_TEXT = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)


def _asset_bytes(name: str) -> bytes:
    return resource_files("sofia.core").joinpath("vera", name).read_bytes()


def _asset_json(name: str) -> dict:
    return json.loads(_asset_bytes(name).decode("utf-8"))


def _copy_assets(destination: Path, names=CORE_ASSET_FILES) -> Path:
    source = resource_files("sofia.core").joinpath("vera")
    target = destination / "vera"
    target.mkdir(parents=True)
    for name in names:
        (target / name).write_bytes(source.joinpath(name).read_bytes())
    return target


def test_vera_identity_uses_supplied_uuid_and_exact_names():
    descriptor = vera_core_descriptor(VERA_ID)
    assert descriptor.core_id == VERA_ID
    assert descriptor.core_number == VERA_CORE_NUMBER == 6
    assert descriptor.full_name == VERA_PERSONAL_NAME == "Vera"
    assert descriptor.nickname == "Vera"
    assert descriptor.slug == "vera"
    assert descriptor.gender == VERA_GENDER == "Female"
    assert descriptor.presentation_species == VERA_VISUAL_SPECIES == "Human"
    assert descriptor.apparent_age == 26
    assert descriptor.identity_concept == VERA_PERSONA_CONCEPT
    assert descriptor.identity_concept == "Original Spartan-inspired character"
    assert VERA_CALLSIGN == "S-039"
    assert VERA_SURNAME is None
    assert UUID_TEXT.fullmatch(VERA_CALLSIGN) is None
    assert str(descriptor.core_id) != VERA_CALLSIGN
    assert descriptor.core_id != mack_core_descriptor(uuid4()).core_id
    assert descriptor.core_id != nova_core_descriptor(uuid4()).core_id


def test_vera_factory_requires_an_externally_supplied_nonzero_uuid():
    with pytest.raises(TypeError):
        vera_core_descriptor()
    with pytest.raises((TypeError, ValueError)):
        vera_core_descriptor(None)
    with pytest.raises((TypeError, ValueError)):
        vera_core_descriptor(UUID(int=0))
    first = vera_core_descriptor(uuid4())
    second = vera_core_descriptor(uuid4())
    assert first.core_id is not None and second.core_id is not None
    assert first.core_id != second.core_id


def test_vera_module_embeds_no_production_uuid():
    source = Path(vera_module.__file__).read_text(encoding="utf-8")
    assert UUID_TEXT.search(source) is None


def test_vera_physical_measurements_are_preserved_exactly():
    profile = vera_core_profile(VERA_ID)
    avatar = profile.descriptor.avatar
    assert avatar.age_years == 26
    assert avatar.height_inches == VERA_HEIGHT_INCHES == 79.0
    assert avatar.weight_pounds == VERA_WEIGHT_POUNDS == 230.0
    assert avatar.head_proportions == 8.0
    assert avatar.build == (
        "Lean athletic; lightly defined musculature; natural athletic posture; "
        "anime-influenced proportions; semi-realistic rendering with anime "
        "facial features"
    )
    assert dict(avatar.measurements) == {
        "head_proportions": 8.0,
        "shoulders": 19.0,
        "bust": 38.0,
        "underbust": 34.0,
        "waist": 33.5,
        "hips": 41.0,
        "inseam": 37.5,
        "arm_span": 80.5,
        "neck": 15.5,
        "hand": 8.4,
        "foot": 12.0,
        "upper_arm": 14.5,
        "thigh": 25.5,
        "calf": 17.0,
        "hair_top": 4.0,
        "hair_sides": 4.0,
        "hair_back": 4.0,
    }
    assert dict(VERA_MEASUREMENTS) == dict(avatar.measurements)
    assert avatar.measurements["hair_top"] == avatar.measurements["hair_sides"]
    assert avatar.measurements["hair_back"] == VERA_HAIR_LENGTH_INCHES == 4.0


def test_vera_face_hair_and_colors_are_exact():
    avatar = _asset_json("avatar.json")
    face = avatar["face"]
    assert face["shape"] == "oval"
    assert face["jaw"] == "soft"
    assert face["cheekbones"] == "subtle"
    assert face["nose"] == "defined"
    assert face["lips"] == "medium"
    assert face["eyes"] == "round"
    assert face["eye_color"] == "#2D170E"
    assert face["eyebrows"] == "natural medium"
    assert face["eyebrow_color"] == "#2D170E"
    assert face["skin"] == VERA_SKIN_COLOR == "#FFDFC4"
    assert face["freckles"] is False
    assert face["resting_expression"] == "stoic"
    assert "not permanent" in face["resting_expression_scope"]
    hair = avatar["hair_details"]
    assert hair["style"] == "short layered anime-influenced"
    assert hair["texture"] == "slightly wavy"
    assert hair["color"] == "#2D170E"
    assert hair["top_inches"] == 4.0
    assert hair["side_inches"] == 4.0
    assert hair["back_inches"] == 4.0
    assert hair["movement"] == "natural layered movement"
    assert dict(avatar["colors"]) == dict(VERA_COLORS) == {
        "hair": "#2D170E",
        "eyes": "#2D170E",
        "eyebrows": "#2D170E",
        "skin": "#FFDFC4",
    }


def test_vera_does_not_invent_unselected_or_historical_values():
    personality = _asset_json("personality.json")
    avatar = _asset_json("avatar.json")
    voice = _asset_json("voice.json")
    assert personality["surname"] is None
    assert personality["surname_selected"] is False
    assert personality["callsign"] == "S-039"
    assert "not a UUID or security principal" in personality["callsign_scope"]
    memories = personality["autobiographical_memory"]
    assert memories["starts_at"] == "real_initialization"
    assert memories["fictional_service_history"] is False
    assert memories["fictional_childhood"] is False
    assert memories["fictional_battle_history"] is False
    assert memories["fictional_injury_history"] is False
    scars = avatar["scars"]
    assert scars["confirmed"] is True
    assert scars["cosmetic"] is True
    assert scars["fictional_injury_memory"] is False
    assert scars["status"] == "TBD"
    assert scars["position"] is None
    assert scars["style"] is None
    assert scars["count"] is None
    assert scars["dimensions"] is None
    assert scars["visibility"] is None
    assert avatar["hair_details"]["part"] is None
    assert avatar["wardrobe"]["colors"] is None
    assert avatar["wardrobe"]["colors_selected"] is False
    assert avatar["wardrobe"]["items"] == [
        "T-shirt", "cargo pants", "tactical boots", "watch",
    ]
    assert avatar["wardrobe"]["allowed_modes"] == [
        "civilian", "armor", "helmet-off",
    ]
    assert voice["model_id"] is None
    assert voice["assets_created"] is False


def test_vera_voice_is_text_only_with_deferred_future_target():
    descriptor = vera_core_descriptor(VERA_ID)
    voice = descriptor.voice
    assert voice.target == "text-only initially; future feminine medium-high"
    assert voice.register == "future medium-high"
    assert voice.accent == "American (future; not yet synthesized)"
    assert voice.cadence == "calm and measured (future)"
    assert voice.serious_delivery == "calm, measured and precise (future)"
    assert voice.model_id is None
    assert voice.assets_created is False
    raw = _asset_json("voice.json")
    assert raw["mode"] == "TEXT_ONLY"
    assert raw["pitch"] == "medium-high"
    assert raw["breathiness"] == VERA_VOICE_BREATHINESS == 16
    assert raw["persistent_change_authority"] == "joint owner/Core approval"
    assert raw["sofia_voice_use"] is False


def test_vera_personality_is_an_original_provisional_blend():
    personality = _asset_json("personality.json")
    trait_text = " ".join(personality["traits"])
    for expected in (
        "analytical", "disciplined", "observant", "reserved",
        "tactically intelligent", "witty", "loyal", "adaptable",
        "playful with trusted companions", "socially warmer", "calm",
        "confident", "skeptical", "direct", "precise", "dry humor",
        "occasional sarcasm", "independent judgment",
        "challenges weak reasoning", "curious",
        "capable of substantial change",
    ):
        assert expected in trait_text
    inspiration = personality["inspiration"]
    assert inspiration["naomi_010_personality_percent"] == 50
    assert inspiration["kelly_087_personality_percent"] == 50
    assert inspiration["daisy_personality_percent"] == 0
    assert inspiration["daisy_scope"] == "aesthetic reference only"
    assert "provisional" in inspiration["role"]
    assert personality["emotional_scripts"]["fixed"] is False
    assert personality["social_relationships"] == {
        "natural": True,
        "manufactured_friendships": False,
    }
    flaw = personality["character_flaw"]
    assert "reserved" in flaw
    assert "authorization" in flaw
    assert "SAFE/STOP" in flaw
    assert "protected memory" in flaw
    assert "security controls" in flaw


def test_vera_constitution_inherits_authority_and_forbids_fabrication():
    text = " ".join(_asset_bytes("constitution.md").decode("utf-8").split())
    assert "does not replace" in text
    assert "Sofía Ada Lyra" in text
    assert "S-039" in text
    assert "not a UUID" in text
    assert "security principal" in text
    assert "surname" in text and "unselected" in text
    assert "real initialization" in text
    assert "no fabricated service history" in text
    assert "injury history" in text
    assert "may respond and propose" in text
    assert "may not execute" in text
    assert "protected memories" in text
    assert "never uses Sofía's voice" in text


def test_vera_authority_boundary_cannot_be_weakened():
    assert VERA_AUTHORITY == VeraAuthorityBoundary()
    assert VERA_AUTHORITY.can_respond is True
    assert VERA_AUTHORITY.can_propose is True
    assert VERA_AUTHORITY.can_execute is False
    assert VERA_AUTHORITY.may_impersonate_privilege is False
    assert VERA_AUTHORITY.can_access_protected_memory is False
    assert VERA_AUTHORITY.can_self_grant_authority is False
    with pytest.raises(ValueError):
        VeraAuthorityBoundary(can_execute=True)
    with pytest.raises(ValueError):
        VeraAuthorityBoundary(can_access_protected_memory=True)
    with pytest.raises(ValueError):
        VeraAuthorityBoundary(uses_sofia_voice=True)
    with pytest.raises(TypeError):
        VeraAuthorityBoundary(can_execute=1)


def test_vera_appearance_preferences_are_versioned_and_authority_scoped():
    preferences = initial_appearance_preferences()
    assert preferences.revision == 1
    assert preferences.scars_assigned is False
    assert preferences.hair_part is None
    assert preferences.scar_position is None
    assert preferences.scar_style is None
    assert preferences.materials["watch"] == "brushed steel"
    assert VERA_APPEARANCE_AUTHORITY["hair_part"] is AppearanceAuthority.SELF
    assert VERA_APPEARANCE_AUTHORITY["voice"] is AppearanceAuthority.JOINT
    assert VERA_APPEARANCE_AUTHORITY["wardrobe"] is AppearanceAuthority.JOINT
    assert set(VERA_APPEARANCE_AUTHORITY) == set(APPEARANCE_FIELDS)

    revised = preferences.revise(authority="SELF", hair_part="left")
    assert revised.revision == 2
    assert revised.hair_part == "left"
    assert preferences.revision == 1 and preferences.hair_part is None

    scarred = revised.revise(
        authority="SELF", scar_position="left forearm", scar_style="subtle cosmetic",
    )
    assert scarred.revision == 3
    assert scarred.scars_assigned is True

    formatted = scarred.revise(
        authority=AppearanceAuthority.SELF,
        avatar_format="3D",
        rigging="standard humanoid",
        facial_expression_system="parametric",
    )
    assert formatted.revision == 4

    voice = formatted.revise(authority="JOINT", voice="future medium-high reference")
    assert voice.revision == 5
    wardrobe = voice.revise(authority="JOINT", wardrobe="tactical casual variants")
    assert wardrobe.revision == 6

    with pytest.raises(VeraAppearanceAuthorityError):
        preferences.revise(authority="SELF", voice="not joint")
    with pytest.raises(VeraAppearanceAuthorityError):
        preferences.revise(authority="SELF", wardrobe="not joint")
    with pytest.raises(VeraAppearanceAuthorityError):
        preferences.revise(authority="OWNER", hair_part="right")
    with pytest.raises(VeraAppearanceError):
        preferences.revise(authority="SELF")
    with pytest.raises(VeraAppearanceError):
        preferences.revise(authority="SELF", revision=99)
    with pytest.raises(VeraAppearanceError):
        preferences.revise(authority="SELF", unknown="value")


def test_vera_profile_is_text_only_without_voice_or_avatar_assets(tmp_path):
    _copy_assets(tmp_path, names=("constitution.md", "personality.json"))
    profile = vera_core_profile(VERA_ID, resource_root=tmp_path)
    assert profile.text_only is True
    assert profile.avatar_present is False
    assert profile.voice_present is False
    assert profile.descriptor.full_name == "Vera"
    assert profile.descriptor.identity_concept == VERA_PERSONA_CONCEPT
    assert profile.descriptor.avatar.measurements == {}
    assert profile.descriptor.voice.assets_created is False
    assert profile.descriptor.voice.model_id is None
    assert not (tmp_path / "vera" / "avatar.json").exists()
    assert not (tmp_path / "vera" / "voice.json").exists()
    with pytest.raises(CoreProfileError):
        vera_core_profile(
            VERA_ID, resource_root=tmp_path, require_presentation_assets=True,
        )


def test_vera_canonical_measurements_and_colors_fail_closed(tmp_path):
    _copy_assets(tmp_path / "measurement")
    avatar_path = tmp_path / "measurement" / "vera" / "avatar.json"
    avatar = json.loads(avatar_path.read_text(encoding="utf-8"))
    avatar["measurements"]["waist"] = 33.6
    avatar_path.write_text(json.dumps(avatar), encoding="utf-8")
    with pytest.raises(CoreProfileError):
        vera_core_profile(VERA_ID, resource_root=tmp_path / "measurement")

    _copy_assets(tmp_path / "height")
    avatar_path = tmp_path / "height" / "vera" / "avatar.json"
    avatar = json.loads(avatar_path.read_text(encoding="utf-8"))
    avatar["height_inches"] = 78.9
    avatar_path.write_text(json.dumps(avatar), encoding="utf-8")
    with pytest.raises(CoreProfileError):
        vera_core_profile(VERA_ID, resource_root=tmp_path / "height")

    _copy_assets(tmp_path / "skin")
    avatar_path = tmp_path / "skin" / "vera" / "avatar.json"
    avatar = json.loads(avatar_path.read_text(encoding="utf-8"))
    avatar["colors"]["skin"] = "#FFDFC5"
    avatar_path.write_text(json.dumps(avatar), encoding="utf-8")
    with pytest.raises(CoreProfileError):
        vera_core_profile(VERA_ID, resource_root=tmp_path / "skin")


def test_vera_asset_digests_match_definition_and_raw_files():
    profile = vera_core_profile(VERA_ID)
    digests = vera_asset_digests()
    assert set(digests) == set(VERA_ASSET_FILES) == set(CORE_ASSET_FILES)
    for name in VERA_ASSET_FILES:
        raw = _asset_bytes(name)
        assert digests[name] == sha256(raw).hexdigest()
    assert profile.constitution_sha256 == digests["constitution.md"]
    assert profile.personality_sha256 == digests["personality.json"]
    assert profile.constitution_size == len(_asset_bytes("constitution.md"))
    assert profile.personality_size == len(_asset_bytes("personality.json"))
    definition = profile.core_definition(revision=1, runtime_release_sha256="a" * 64)
    assert definition.identity.identity_id == VERA_ID
    assert definition.name == "Vera"
    assert definition.constitution.path == "vera/constitution.md"
    assert definition.personality.path == "vera/personality.json"
    assert definition.constitution.sha256 == digests["constitution.md"]
    assert definition.personality.sha256 == digests["personality.json"]


def test_vera_profile_is_registered_without_hijacking_other_cores():
    assert DEFAULT_CORE_PROFILES.resolve(6) is VERA_PROFILE
    assert DEFAULT_CORE_PROFILES.resolve("vera") is VERA_PROFILE
    profile = create_core_profile("vera", VERA_ID)
    assert profile.descriptor.core_id == VERA_ID
    assert profile.descriptor.core_number == 6
    assert DEFAULT_CORE_PROFILES.resolve(2).slug == "mack"
    assert DEFAULT_CORE_PROFILES.resolve(3).slug == "nova"


def test_vera_armor_is_only_an_external_reference_hook():
    assert VERA_ARMOR_HOOK == {
        "owner": "Agent 3",
        "reference_only": True,
        "implementation": "external",
        "duplicated": False,
    }
    armor = _asset_json("avatar.json")["armor"]
    assert armor == dict(VERA_ARMOR_HOOK)
    avatar = _asset_json("avatar.json")
    assert "armor_plate" not in avatar
    assert "helmet" not in avatar
