"""Phase C Core package layout, entrypoints and compatibility boundaries.

These tests inspect source layout and inert imports only.  They do not install,
activate, start or migrate any Core.
"""
from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from sofia.core.mack import MACK_CORE_NUMBER, MACK_PROFILE, mack_core_profile
from sofia.core.nova import NOVA_CORE_NUMBER, NOVA_PROFILE, nova_core_profile
from sofia.core.sofia import (
    SOFIA_CORE_NUMBER,
    SOFIA_IDENTITY,
    SOFIA_PERSONAL_NAME,
    SOFIA_SLUG,
    build_sofia_core_definition,
)
from sofia.core.unwritten import (
    UNWRITTEN_CORE_NUMBER,
    UNWRITTEN_SLUG,
    blank_core_profile,
)
from sofia.core.vera import (
    VERA_CORE_NUMBER,
    VERA_PERSONAL_NAME,
    VERA_PROFILE,
    vera_core_profile,
)

ROOT = Path(__file__).resolve().parents[1]
CORE_ROOT = ROOT / "src" / "sofia" / "core"
FIVE_PACKAGES = ("sofia", "mack", "nova", "vera", "unwritten")
TWIN_NAMES = ("4", "5", "twin-4", "twin-5", "twin-a", "twin-b")
FIXED = {
    "mack": UUID("22222222-2222-4222-8222-222222222222"),
    "nova": UUID("33333333-3333-4333-8333-333333333333"),
    "vera": UUID("66666666-6666-4666-8666-666666666666"),
    "unwritten": UUID("77777777-7777-4777-8777-777777777777"),
    "sofia": UUID("11111111-1111-4111-8111-111111111111"),
}


def test_five_core_packages_exist_and_old_shared_assets_are_gone():
    for name in FIVE_PACKAGES:
        package = CORE_ROOT / name
        assert package.is_dir(), package
        assert (package / "__init__.py").is_file(), package
    assert not (CORE_ROOT / "cores").exists()
    for name in TWIN_NAMES:
        assert not (CORE_ROOT / name).exists(), name


def test_core_entrypoints_load_only_with_supplied_uuids():
    mack = mack_core_profile(FIXED["mack"])
    nova = nova_core_profile(FIXED["nova"])
    vera = vera_core_profile(FIXED["vera"])
    blank = blank_core_profile(FIXED["unwritten"])

    assert (MACK_PROFILE.slug, MACK_CORE_NUMBER) == ("mack", 2)
    assert (NOVA_PROFILE.slug, NOVA_CORE_NUMBER) == ("nova", 3)
    assert (VERA_PROFILE.slug, VERA_CORE_NUMBER) == ("vera", 6)
    assert VERA_PERSONAL_NAME == "Vera"
    assert (UNWRITTEN_SLUG, UNWRITTEN_CORE_NUMBER) == ("unwritten", 7)

    assert mack.descriptor.core_id == FIXED["mack"]
    assert nova.descriptor.core_id == FIXED["nova"]
    assert vera.descriptor.core_id == FIXED["vera"]
    assert blank.core_id == FIXED["unwritten"]

    assert mack.spec.constitution_path == "mack/constitution.md"
    assert nova.spec.personality_path == "nova/personality.json"
    assert vera.spec.constitution_path == "vera/constitution.md"
    for relative in (
        "mack/constitution.md",
        "nova/personality.json",
        "vera/avatar.json",
        "unwritten/constitution.md",
    ):
        assert (CORE_ROOT / relative).is_file(), relative


def test_sofia_package_is_immutable_and_does_not_fabricate_a_uuid():
    assert SOFIA_IDENTITY.core_number == SOFIA_CORE_NUMBER == 1
    assert SOFIA_IDENTITY.slug == SOFIA_SLUG == "sofia"
    assert SOFIA_IDENTITY.personal_name == SOFIA_PERSONAL_NAME
    assert SOFIA_IDENTITY.grants_authority is False
    source = (CORE_ROOT / "sofia" / "identity.py").read_text(encoding="utf-8")
    assert "instance_id" not in source
    assert "uuid4" not in source
    definition = build_sofia_core_definition(
        FIXED["sofia"], revision=1, runtime_release_sha256="a" * 64,
    )
    assert definition.identity.identity_id == FIXED["sofia"]
    assert definition.name == SOFIA_PERSONAL_NAME
    assert definition.constitution.path == "constitution/constitution.md"
    assert definition.personality.path == "personality/personality.json"
    with pytest.raises(ValueError):
        build_sofia_core_definition(
            UUID(int=0), revision=1, runtime_release_sha256="a" * 64,
        )


def test_legacy_multicore_imports_re_export_canonical_objects():
    from sofia.core import mack, nova, vera, unwritten
    from sofia.core.mack import emotion as mack_emotion
    from sofia.core.mack import personality as mack_personality
    from sofia.core.multicore import emotion, personality, profiles
    from sofia.core.multicore import vera as legacy_vera
    from sofia.core.multicore import unwritten as legacy_unwritten
    from sofia.core.nova import emotion as nova_emotion
    from sofia.core.nova import personality as nova_personality

    assert legacy_vera.VERA_PROFILE is vera.VERA_PROFILE
    assert legacy_vera.vera_core_profile is vera.vera_core_profile
    assert legacy_unwritten.UNWRITTEN_CORE_NUMBER == unwritten.UNWRITTEN_CORE_NUMBER
    assert legacy_unwritten.blank_core_profile is unwritten.blank_core_profile

    assert profiles.MACK_PROFILE is mack.MACK_PROFILE
    assert profiles.NOVA_PROFILE is nova.NOVA_PROFILE
    assert profiles.VERA_PROFILE is vera.VERA_PROFILE
    assert personality.MACK_FULLER_PROFILE is mack_personality.MACK_FULLER_PROFILE
    assert personality.NOVA_ARDEN_PROFILE is nova_personality.NOVA_ARDEN_PROFILE
    assert emotion.MACK_EMOTION_PROFILE is mack_emotion.MACK_EMOTION_PROFILE
    assert emotion.NOVA_EMOTION_PROFILE is nova_emotion.NOVA_EMOTION_PROFILE

    from sofia.core import multicore

    assert multicore.MACK_PROFILE is mack.MACK_PROFILE
    assert multicore.MACK_FULLER_PROFILE is mack_personality.MACK_FULLER_PROFILE


def test_no_runtime_database_or_personal_memory_in_source():
    forbidden_suffixes = (".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm")
    forbidden_names = {"sofia.db", "memory.db", "personal_memory"}
    for path in CORE_ROOT.rglob("*"):
        if not path.is_file():
            continue
        assert not path.name.endswith(forbidden_suffixes), path
        assert path.name.casefold() not in forbidden_names, path
        assert "memories" not in {part.casefold() for part in path.parts}, path


def test_no_duplicate_canonical_asset_copies():
    for slug in ("mack", "nova", "vera", "unwritten"):
        assert not (CORE_ROOT / "cores" / slug).exists()
    assets = {
        path.relative_to(CORE_ROOT).as_posix()
        for path in CORE_ROOT.rglob("*")
        if path.is_file() and path.name in {
            "constitution.md", "personality.json", "avatar.json", "voice.json",
        }
    }
    for slug in ("mack", "nova", "vera"):
        for name in ("constitution.md", "personality.json", "avatar.json", "voice.json"):
            assert f"{slug}/{name}" in assets
    assert "unwritten/constitution.md" in assets
    assert not any(path.startswith("cores/") for path in assets)
