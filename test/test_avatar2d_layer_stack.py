"""Waist-up 2D outfit composition reuses the actual canonical slot matrix."""
from dataclasses import replace
from pathlib import Path

import pytest

from sofia.avatar.presentation import AttireMode, AudienceScope
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.avatar.vtuber_asset_bundle import (
    Avatar2DArtSelection, Avatar2DAssetError,
    Avatar2DSprite, Verified2DArtBundle,
)
from sofia.avatar.vtuber_layer_stack import (
    WAIST_UP_SLOTS, assemble_avatar2d_layers,
)
from sofia.core.embodiment.store import EmbodimentStore


ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "src" / "sofia" / "core" / "embodiment" / "avatar.json"


def environment(tmp_path):
    return load_or_bootstrap_presentation(
        embodiment=EmbodimentStore(SEED).load(),
        state_path=tmp_path / "sofia.db",
    )


def public_parts(runtime):
    projection = runtime.authority.projection(AudienceScope.PUBLIC)
    matrix = runtime.matrix_for(projection.item_ids)
    sprites = [
        Avatar2DSprite("tail.base", "base_back", 0),
        Avatar2DSprite("base.body", "base_body", 0),
        Avatar2DSprite("face.base", "base_face", 0),
        Avatar2DSprite("hair.front", "base_front", 0),
    ]
    by_garment = {}
    for cell in matrix.cells:
        if cell.slot not in WAIST_UP_SLOTS:
            continue
        by_garment.setdefault(
            (cell.garment_id, cell.layer), set()
        ).add(cell.slot)
    for index, ((garment_id, layer), slots) in enumerate(
        sorted(by_garment.items(), key=lambda item: (item[0][1], item[0][0]))
    ):
        sprites.append(
            Avatar2DSprite(
                f"garment.{index}", "garment", index,
                garment_id=garment_id,
                slots=tuple(sorted(slots)),
                wardrobe_layer=layer,
            )
        )
    verified = Verified2DArtBundle(
        bundle_id="test.verified",
        audience=AudienceScope.PUBLIC,
        attire=AttireMode.CLOTHED,
        outfit_id=projection.outfit_id,
        digest="a" * 64,
        images={s.sprite_id: bytearray(b"test-only-asset") for s in sprites},
        sprites=tuple(sprites),
    )
    selection = Avatar2DArtSelection(
        "public", projection, verified, "verified public art",
    )
    return selection, matrix


def test_public_base_and_clothing_draw_in_real_slot_layer_order(tmp_path):
    runtime = environment(tmp_path)
    selected, matrix = public_parts(runtime)
    stack = assemble_avatar2d_layers(selected, matrix=matrix)
    sprites = stack.draw_layers
    assert stack.presentation_revision == runtime.authority.current.revision
    assert stack.audience is AudienceScope.PUBLIC
    assert sprites[0].sprite_id == "tail.base"
    assert sprites[1].sprite_id == "base.body"
    garment = [s for s in sprites if s.role == "garment"]
    assert garment
    assert all(s.garment_id in matrix.item_ids for s in garment)
    assert all(s.visible_slots and set(s.visible_slots) <= WAIST_UP_SLOTS
               for s in garment)
    assert max(s.stack_order for s in garment) < next(
        s.stack_order for s in sprites if s.sprite_id == "hair.front"
    )
    assert {s.role for s in sprites} == {
        "base_back", "base_body", "base_face", "base_front", "garment",
    }


def test_missing_actual_garment_sprite_fails_without_pretending_dressed(tmp_path):
    runtime = environment(tmp_path)
    selected, matrix = public_parts(runtime)
    art = selected.bundle
    art.sprites = tuple(
        sprite for sprite in art.sprites
        if sprite.sprite_id != next(s.sprite_id for s in art.sprites if s.role == "garment")
    )
    with pytest.raises(Avatar2DAssetError, match="garment sprite is missing"):
        assemble_avatar2d_layers(selected, matrix=matrix)


def test_wrong_garment_id_or_layer_cannot_draw_on_top_of_body(tmp_path):
    runtime = environment(tmp_path)
    selected, matrix = public_parts(runtime)
    art = selected.bundle
    changed = []
    for sprite in art.sprites:
        if sprite.role == "garment":
            changed.append(replace(sprite, garment_id="invented.jacket"))
            break
    changed.extend(s for s in art.sprites if s not in changed and s.role != "garment")
    art.sprites = tuple(changed)
    with pytest.raises(Avatar2DAssetError, match="does not match"):
        assemble_avatar2d_layers(selected, matrix=matrix)


def test_mismatched_canonical_wardrobe_revision_or_items_fail(tmp_path):
    runtime = environment(tmp_path)
    selected, matrix = public_parts(runtime)
    forged = replace(selected, projection=replace(selected.projection, item_ids=()))
    with pytest.raises(Avatar2DAssetError, match="matrix does not match"):
        assemble_avatar2d_layers(forged, matrix=matrix)


def test_private_and_nude_are_never_drawn_as_public(tmp_path):
    runtime = environment(tmp_path)
    selected, matrix = public_parts(runtime)
    disguised = replace(
        selected, projection=replace(selected.projection, attire=AttireMode.NUDE)
    )
    with pytest.raises(Avatar2DAssetError):
        assemble_avatar2d_layers(disguised, matrix=matrix)

    nude_view = replace(
        selected.projection,
        audience=AudienceScope.PRIVATE,
        attire=AttireMode.NUDE,
        outfit_id=None,
        item_ids=(),
        private_fallback_used=False,
    )
    nude_bundle = Verified2DArtBundle(
        bundle_id="test.private.nude", audience=AudienceScope.PRIVATE,
        attire=AttireMode.NUDE, outfit_id=None, digest="f" * 64,
        images={"private.body": bytearray(b"not-rendered-test-art")},
        sprites=(Avatar2DSprite("private.body", "base_body", 0),),
    )
    # The compositor only accepts private selection after trusted gateway.
    selection = Avatar2DArtSelection(
        "private", nude_view, nude_bundle, "trusted-private-test-fixture",
    )
    stack = assemble_avatar2d_layers(selection, matrix=None)
    assert stack.attire is AttireMode.NUDE
    assert len(stack.draw_layers) == 1
    with pytest.raises(Avatar2DAssetError):
        assemble_avatar2d_layers(
            replace(selection, status="public"),
            matrix=None,
        )
    with pytest.raises(Avatar2DAssetError):
        assemble_avatar2d_layers(
            replace(
                selection,
                bundle=replace(nude_bundle, audience=AudienceScope.PUBLIC),
            ),
            matrix=None,
        )


def test_public_view_needs_covered_authoritative_matrix(tmp_path):
    runtime = environment(tmp_path)
    selected, matrix = public_parts(runtime)
    with pytest.raises(Avatar2DAssetError, match="covered safe"):
        assemble_avatar2d_layers(
            selected, matrix=replace(matrix, covered_default=False)
        )
    with pytest.raises(Avatar2DAssetError, match="covered safe"):
        assemble_avatar2d_layers(
            selected, matrix=replace(matrix, private_only=True)
        )


def test_base_sprite_must_exist_and_closed_bytes_cannot_render(tmp_path):
    runtime = environment(tmp_path)
    selected, matrix = public_parts(runtime)
    selected.bundle.sprites = tuple(
        sprite for sprite in selected.bundle.sprites
        if sprite.sprite_id != "base.body"
    )
    with pytest.raises(Avatar2DAssetError, match="canonical base"):
        assemble_avatar2d_layers(selected, matrix=matrix)
    selected.bundle.close()
    with pytest.raises(Avatar2DAssetError, match="unavailable"):
        assemble_avatar2d_layers(selected, matrix=matrix)
