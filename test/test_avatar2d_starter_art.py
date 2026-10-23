"""Public procedural art is actual aligned PNG data for existing wardrobe IDs.

The generator is deliberately offline/read-only with respect to canonical
sofia.db. It cannot generate protected private/nude artwork.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sofia.avatar.private_grant import PrivatePresentationGrantResolver
from sofia.avatar.presentation import AudienceScope
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.avatar.vtuber_asset_bundle import Avatar2DAssetGateway
from sofia.avatar.vtuber_layer_stack import assemble_avatar2d_layers
from sofia.avatar.vtuber_starter_art import (
    WIDTH, HEIGHT, PNG_HEADER, generate_public_outfit_art,
    generate_public_wardrobe_library, main,
)
from sofia.avatar.wardrobe_catalog import build_starter_wardrobe
from sofia.core.embodiment.store import EmbodimentStore


SEED = Path(__file__).resolve().parents[1] / "src/sofia/core.embodiment/avatar.json"


@pytest.mark.parametrize("outfit_id", [
    "day.default",
    "night.lounge",
    "outfit.light_lab_tech",
    "outfit.cozy_evening",
])
def test_real_public_wardrobe_sprite_assets_roundtrip(tmp_path, outfit_id):
    catalog = build_starter_wardrobe()
    out = tmp_path / "art" / "outfits" / outfit_id
    receipt = generate_public_outfit_art(
        catalog, outfit_id=outfit_id, destination=out,
    )
    assert receipt.asset_count >= 5
    assert receipt.bytes_written > 0
    files = tuple(out.rglob("*.png"))
    assert len(files) == receipt.asset_count
    assert all(file.read_bytes().startswith(PNG_HEADER) for file in files)
    assert all(
        int.from_bytes(file.read_bytes()[16:20], "big") == WIDTH
        and int.from_bytes(file.read_bytes()[20:24], "big") == HEIGHT
        for file in files
    )

    runtime = load_or_bootstrap_presentation(
        embodiment=EmbodimentStore(SEED).load(),
        state_path=tmp_path / "sofia.db",
    )
    loader = Avatar2DAssetGateway(
        authority=runtime.authority,
        grant_resolver=PrivatePresentationGrantResolver(
            state_path=tmp_path / "sofia.db",
        ),
        public_root=tmp_path / "art",
        private_root=tmp_path / "private-art",
    )
    # The loader checks the *currently selected* outfit. For alternate
    # outfits, test the real checked manifest reader without mutating
    # production state.
    from sofia.avatar.vtuber_asset_bundle import _read_bundle
    from sofia.avatar.presentation import AttireMode
    checked = _read_bundle(
        out, audience=AudienceScope.PUBLIC,
        attire=AttireMode.CLOTHED, outfit_id=outfit_id,
    )
    assert len(checked.images) == receipt.asset_count
    assert all(checked.images.values())
    if outfit_id == "day.default":
        selection = loader.public()
        assert selection.status == "public"
        assert selection.bundle is not None
        plan = assemble_avatar2d_layers(
            selection,
            matrix=runtime.matrix_for(selection.projection.item_ids),
        )
        assert plan.draw_layers
        assert all(x.garment_id is None or x.garment_id
                   in selection.projection.item_ids for x in plan.draw_layers)
        selection.bundle.close()
    checked.close()


def test_builds_canonical_daytime_coat_and_top_sprites_by_existing_ids(tmp_path):
    catalog = build_starter_wardrobe()
    out = tmp_path / "outfit"
    generate_public_outfit_art(catalog, outfit_id="day.default", destination=out)
    assert (out / "garments" / "day.technical_top.png").is_file()
    assert (out / "garments" / "day.engineer_jacket.png").is_file()
    assert (out / "garments" / "base.bralette.png").is_file()
    assert (out / "base" / "face.png").is_file()
    assert (out / "base" / "front.png").is_file()


def test_private_outfits_denied_without_creating_art_or_working_around_permission(tmp_path):
    catalog = build_starter_wardrobe()
    out = tmp_path / "should_not_write"
    with pytest.raises(PermissionError, match="protected"):
        generate_public_outfit_art(
            catalog, outfit_id="private.violet_tease", destination=out,
        )
    assert not out.exists()


def test_existing_art_not_overwritten_and_image_quality_explicit(tmp_path):
    import json

    catalog = build_starter_wardrobe()
    out = tmp_path / "outfit"
    generate_public_outfit_art(catalog, outfit_id="day.default", destination=out)
    manifest = json.loads((out / "manifest.json").read_text("utf-8"))
    assert manifest["art_quality"] == "procedural_starter"
    assert manifest["outfit_id"] == "day.default"
    assert manifest["audience"] == "public"
    assert manifest["fidelity_status"] == "unreviewed_not_exact"
    garment_layers = [layer for layer in manifest["layers"]
                      if layer.get("role") == "garment"]
    assert garment_layers
    assert all(layer["visual_review_status"] ==
               "unreviewed_procedural_starter" for layer in garment_layers)
    assert all(len(layer["source_sha256"]) == 64 for layer in garment_layers)
    assert not any(item.get("audience") == "private" for item in manifest["layers"])
    before = (out / "base" / "body.png").read_bytes()
    with pytest.raises(FileExistsError):
        generate_public_outfit_art(catalog, outfit_id="day.default", destination=out)
    assert (out / "base" / "body.png").read_bytes() == before


def test_cli_never_creates_or_writes_canonical_state(tmp_path):
    state = tmp_path / "sofia.db"
    assert not state.exists()
    code = main([
        "--output", str(tmp_path / "art"),
        "--outfit", "night.lounge",
    ])
    assert code == 0
    assert not state.exists()
    assert (tmp_path / "art" / "outfits" / "night.lounge"
            / "manifest.json").is_file()



def test_full_visible_public_wardrobe_library_is_reusable_and_excludes_private(tmp_path):
    import json

    catalog = build_starter_wardrobe()
    report = generate_public_wardrobe_library(
        catalog, destination=tmp_path / "art",
    )
    manifest_file = tmp_path / "art" / "library" / "items.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["schema"] == "sofia.avatar2d.public_sprite_library.v1"
    assert report.asset_count == len(manifest["assets"])
    assert report.asset_count >= 40
    assert manifest["fidelity_status"] == "unreviewed_not_exact"
    assert all(len(i["source_sha256"]) == 64 for i in manifest["assets"])
    assert all(i["visual_review_status"] == "unreviewed_procedural_starter"
               for i in manifest["assets"])
    reviewed_public = {
        bp.garment.item_id for bp in catalog.blueprints
        if not bp.private_only and not bp.garment.private_only
    }
    for row in manifest["assets"]:
        assert row["garment_id"] in reviewed_public
        assert row["private_only"] is False
        png = tmp_path / "art" / "library" / row["asset"]
        assert png.read_bytes().startswith(PNG_HEADER)
        assert __import__("hashlib").sha256(png.read_bytes()).hexdigest() == row["sha256"]
        assert row["slots"]
    assert (tmp_path / "art" / "library" / "day.engineer_jacket.png").is_file()
    assert (tmp_path / "art" / "library" / "night.lounge_tee.png").is_file()
    assert not (tmp_path / "art" / "library"
                / "under.private.rope_full_harness.png").exists()
    with pytest.raises(FileExistsError):
        generate_public_wardrobe_library(
            catalog, destination=tmp_path / "art",
        )
