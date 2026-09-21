"""I8 catalog tests; never use or change the production SQLite database."""
from pathlib import Path

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.core import InteractionEngine
from sofia.interaction.registry import (
    ACTION_DEFINITIONS, CATALOG_VERSION, EMOTION_EXTENSIONS,
    EXPRESSION_DEFINITIONS, GESTURE_DEFINITIONS, InteractionCatalog,
    catalog_for_engine, normalize_alias,
)

AVATAR = Path(__file__).resolve().parents[1] / "src" / "sofia" / "data" / "avatar.json"


@pytest.fixture
def catalog():
    engine = InteractionEngine(AvatarStore(AVATAR).load())
    return catalog_for_engine(engine), engine


def test_every_existing_canonical_region_resolves_without_renaming(catalog):
    names, engine = catalog
    assert names.region_ids == frozenset(engine.regions)
    for region in engine.regions:
        result = names.resolve_region(region)
        assert (result.status, result.canonical_id, result.version) == (
            "resolved", region, CATALOG_VERSION,
        )


@pytest.mark.parametrize("alias,canonical", [
    ("tummy", "abdomen"),
    ("YOUR LEFT HAND", "left-hand"),
    ("Sofía’s right ear tip", "right-ear-tip"),
    ("fox tail", "tail"),
    ("tail root", "tail-base"),
    ("left boob", "left-breast"),
    ("chest", "chest"),
    ("forehead", "forehead"),
])
def test_exact_and_colloquial_names_preserve_scope(catalog, alias, canonical):
    assert catalog[0].resolve_region(alias).canonical_id == canonical


@pytest.mark.parametrize("alias,expected", [
    ("ear", ("left-ear", "right-ear")),
    ("hand", ("left-hand", "right-hand")),
    ("forearm", ("left-forearm", "right-forearm")),
    ("boobs", ("left-breast", "right-breast")),
])
def test_ambiguous_names_are_not_guessed(catalog, alias, expected):
    result = catalog[0].resolve_region(alias)
    assert result.status == "ambiguous" and result.canonical_id is None
    assert result.candidates == expected


def test_unknown_or_optional_anatomy_is_not_invented():
    names = InteractionCatalog(("head", "chest", "left-breast", "right-breast"))
    assert names.resolve_region("fox tail").status == "unknown"
    assert names.resolve_region("side").status == "unknown"
    assert names.resolve_region("chest").canonical_id == "chest"
    assert names.resolve_region("breast").status == "ambiguous"


def test_separate_gestures_actions_expressions_and_no_unknown_fallback(catalog):
    names = catalog[0]
    assert names.resolve_semantic("gesture", "rubbing").canonical_id == "rub"
    assert names.resolve_semantic("gesture", "intimate touch").canonical_id == "intimate-touch"
    assert names.resolve_semantic("action", "embrace").canonical_id == "hug"
    assert names.resolve_semantic("expression", "giggling").canonical_id == "giggle"
    assert names.resolve_semantic("expression", "sobbing").canonical_id == "sob"
    assert names.resolve_semantic("gesture", "hug").status == "unknown"
    assert names.resolve_semantic("gesture", "unknown intimate act").status == "unknown"
    assert len(GESTURE_DEFINITIONS) >= 20
    assert len(ACTION_DEFINITIONS) >= 15
    assert len(EXPRESSION_DEFINITIONS) >= 20
    assert {"embarrassment", "humiliation", "sexual-arousal"} <= EMOTION_EXTENSIONS


def test_registry_is_immutable_and_does_not_change_runtime_engine(catalog):
    names, engine = catalog
    original = frozenset(engine.regions)
    with pytest.raises(TypeError):
        names.anatomy_aliases["head"] = ("tail",)
    with pytest.raises(TypeError):
        names.semantic_aliases["gesture"]["pat"] = "touch"
    assert frozenset(engine.regions) == original
    # v1 does not silently accept catalog-only verbs before parser integration.
    assert "caress" not in engine.GESTURES if hasattr(engine, "GESTURES") else True


def test_alias_normalization_rejects_malformed_input():
    assert normalize_alias("  Left_Ear-Tip ") == "left ear tip"
    with pytest.raises(ValueError):
        normalize_alias("")
    with pytest.raises(ValueError):
        normalize_alias("head; execute something")
    with pytest.raises(ValueError):
        normalize_alias("x" * 121)
