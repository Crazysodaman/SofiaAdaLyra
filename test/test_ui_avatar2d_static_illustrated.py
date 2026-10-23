"""Static illustrated add-on: actual PNG, exact outfit binding, safe fallback."""
from dataclasses import replace
from hashlib import sha256
import json

import pytest

from sofia.modules.avatar.presentation import AudienceScope, AttireMode
from sofia.modules.avatar.vtuber_asset_bundle import Avatar2DAssetError
from sofia.modules.avatar.vtuber_static_portraits import load_public_static_portrait
from sofia.modules.avatar.vtuber_starter_art import _base
from test.test_ui_avatar2d_modular import configured, decision


def install_sample(root, projection):
    directory = root / "portraits" / projection.outfit_id
    directory.mkdir(parents=True)
    image = _base("face")  # Real, checked RGBA PNG with 320x400 canvas.
    manifest = {
        "schema": "sofia-public-illustrated-static-v1",
        "outfit_id": projection.outfit_id,
        "item_ids": list(projection.item_ids),
        "featured_item_id": "day.engineer_jacket",
        "portrait_sha256": sha256(image).hexdigest(),
        "image_size": [320, 400],
        "public_only": True,
        "quality": "unreviewed_illustrated_candidate",
        "animation": "static",
    }
    (directory / "portrait.png").write_bytes(image)
    (directory / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8",
    )
    return directory, image


def test_illustrated_static_portrait_overrides_procedural_layers(tmp_path, monkeypatch):
    renderer, root, canvas, fallback, public_root, projection = configured(
        tmp_path, monkeypatch,
    )
    _, png = install_sample(public_root, projection)
    renderer.render_idle(projection)
    assert canvas.final_frame() == (sha256(png).hexdigest(),)
    assert renderer._last_art_source == "static illustrated candidate"
    assert fallback.calls == []
    events = []
    renderer.render(
        decision(projection, "tail-flick"),
        completed=lambda *event: events.append(event),
    )
    assert events == []
    root.run()
    assert events and events[0][1] is True
    assert "1 2D frame(s)" in events[0][2]
    assert "static illustrated candidate" in events[0][2]
    assert not root.pending  # No invented blink/fox movement for static art.


def test_corrupt_illustrated_portrait_falls_back_safely(tmp_path, monkeypatch):
    renderer, root, canvas, fallback, public_root, projection = configured(
        tmp_path, monkeypatch,
    )
    directory, _ = install_sample(public_root, projection)
    (directory / "portrait.png").write_bytes(b"forged")
    renderer.render(decision(projection), completed=lambda *_: None)
    assert fallback.calls == ["fallback_render"]
    assert canvas.final_frame() == ()


def test_private_projection_never_loads_public_illustrated_art(tmp_path, monkeypatch):
    renderer, root, canvas, fallback, public_root, projection = configured(
        tmp_path, monkeypatch,
    )
    install_sample(public_root, projection)
    private = replace(
        projection, audience=AudienceScope.PRIVATE, attire=AttireMode.NUDE,
    )
    assert load_public_static_portrait(
        public_root, private, catalog=renderer.catalog,
    ) is None
    events=[]
    renderer.render(decision(private), completed=lambda *v: events.append(v))
    assert events and events[0][1] is False
    assert canvas.final_frame() == ()


def test_mismatched_item_ids_never_claim_illustrated_clothing(tmp_path, monkeypatch):
    renderer, _, _, _, public_root, projection = configured(tmp_path, monkeypatch)
    install_sample(public_root, projection)
    changed = replace(projection, item_ids=projection.item_ids[:-1])
    assert load_public_static_portrait(
        public_root, changed, catalog=renderer.catalog,
    ) is None


def test_manifest_scope_and_digest_are_checked(tmp_path, monkeypatch):
    renderer, _, _, _, public_root, projection = configured(tmp_path, monkeypatch)
    directory, _ = install_sample(public_root, projection)
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["public_only"] = False
    path.write_text(json.dumps(manifest))
    with pytest.raises(Avatar2DAssetError):
        load_public_static_portrait(
            public_root, projection, catalog=renderer.catalog,
        )
