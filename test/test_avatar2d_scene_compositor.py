"""Production public scene tests: static, presets, modular and visual receipts."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
import sys
import types

import pytest
from PIL import Image

from sofia.modules.avatar.presentation import AttireMode, AudienceScope
from sofia.modules.avatar.scene_compositor import (
    SceneSettings, compose_public_scene, compose_modular_public_outfit,
    export_scene_png, import_public_background, load_public_background,
    load_scene_preset, save_scene_preset, scene_png_bytes,
)
from sofia.modules.avatar.vtuber_asset_bundle import Avatar2DAssetError
from sofia.modules.avatar.vtuber_starter_art import _base
from test.test_ui_avatar2d_renderer import env, Root, Canvas, Symbolic
from sofia.modules.ui.avatar2d_renderer import TkLayered2DRenderer


def png_bytes():
    image=Image.new("RGBA", (120, 160), (42, 25, 89, 255))
    image.putpixel((10,10), (250, 19, 180, 255))
    out=BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def setup(tmp_path):
    root, projection, state = env(tmp_path)
    from sofia.modules.avatar.wardrobe_catalog import build_starter_wardrobe
    catalog=build_starter_wardrobe(state_path=state)
    background=png_bytes()
    digest=import_public_background(root, "neon-workshop", background)
    settings=SceneSettings(
        outfit_id=projection.outfit_id, item_ids=projection.item_ids,
        background_id="neon-workshop", background_sha256=digest,
        width=640, height=800,
    )
    return root, projection, catalog, settings


def test_phase_a_uses_verified_public_portrait_over_real_background(tmp_path):
    root, projection, catalog, settings=setup(tmp_path)
    portrait=root/"portraits"/projection.outfit_id
    portrait.mkdir(parents=True)
    p=_base("face")
    (portrait/"portrait.png").write_bytes(p)
    (portrait/"manifest.json").write_text(json.dumps({
        "schema":"sofia-public-illustrated-static-v1",
        "outfit_id":projection.outfit_id, "item_ids":list(projection.item_ids),
        "public_only":True, "quality":"unreviewed_illustrated_candidate",
        "animation":"static", "image_size":[320,400],
        "portrait_sha256":sha256(p).hexdigest(),
    }))
    scene, source=compose_public_scene(root, projection, catalog=catalog, scene=settings)
    assert scene.size == (640,800)
    assert source == "illustrated static portrait"
    assert scene.getpixel((4,4))[3] == 255
    raw, _ = scene_png_bytes(root, projection, catalog=catalog, scene=settings)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n"


def test_phase_b_saves_and_loads_scene_without_rewriting_db(tmp_path):
    root, projection, catalog, settings=setup(tmp_path)
    datafile=tmp_path/"sofia.db"
    before=datafile.read_bytes()
    path=save_scene_preset(root, settings, catalog=catalog)
    assert path.is_file()
    assert load_scene_preset(root, projection, catalog=catalog) == settings
    assert datafile.read_bytes() == before
    with pytest.raises(FileExistsError):
        save_scene_preset(root, settings, catalog=catalog)
    edited=replace(settings, x=.27, dim=.2, blur=5)
    save_scene_preset(root, edited, catalog=catalog, replace_existing=True)
    assert load_scene_preset(root, projection, catalog=catalog) == edited
    assert datafile.read_bytes() == before


def test_phase_c_reuses_verified_actual_wardrobe_sprite_stack(tmp_path):
    root, projection, catalog, settings=setup(tmp_path)
    # No illustrated portrait: real validated public garment sprites still work.
    result=compose_modular_public_outfit(root, projection, catalog=catalog)
    assert result.size == (320,400)
    composite, source=compose_public_scene(
        root, projection, catalog=catalog, scene=settings,
    )
    assert source == "verified modular wardrobe sprites"
    assert composite.size == (640,800)


def test_cannot_composite_private_or_unmatched_outfits(tmp_path):
    root, projection, catalog, settings=setup(tmp_path)
    private=replace(projection, audience=AudienceScope.PRIVATE)
    with pytest.raises(Avatar2DAssetError):
        compose_public_scene(root, private, catalog=catalog, scene=settings)
    with pytest.raises(Avatar2DAssetError):
        compose_public_scene(root, replace(projection, item_ids=projection.item_ids[:-1]),
                             catalog=catalog, scene=settings)


def test_background_hash_tamper_rejected(tmp_path):
    root, projection, catalog, scene=setup(tmp_path)
    image=root/"scenes"/"backgrounds"/"neon-workshop"/"background.png"
    image.write_bytes(b"spoofed-image")
    with pytest.raises(Avatar2DAssetError):
        load_public_background(root,"neon-workshop",scene.background_sha256)
    with pytest.raises(Avatar2DAssetError):
        save_scene_preset(root, scene, catalog=catalog)


def test_preset_outfit_mismatch_not_loaded(tmp_path):
    root, projection, catalog, scene=setup(tmp_path)
    save_scene_preset(root,scene,catalog=catalog)
    manifest=root/"scenes"/"presets"/(projection.outfit_id+".json")
    raw=json.loads(manifest.read_text())
    raw["item_ids"]=raw["item_ids"][1:]
    manifest.write_text(json.dumps(raw))
    with pytest.raises(Avatar2DAssetError):
        load_scene_preset(root,projection,catalog=catalog)


def test_scene_bounds_nan_and_extra_fields_rejected(tmp_path):
    root, projection, catalog, scene=setup(tmp_path)
    for value in (float("nan"),float("inf"),-1.,10.):
        with pytest.raises(Avatar2DAssetError):
            replace(scene, scale=value)
    with pytest.raises(Avatar2DAssetError):
        SceneSettings.from_dict({**scene.as_dict(),"unexpected":"garbage"})


def test_scene_export_requires_explicit_overwrite(tmp_path):
    root, projection, catalog, scene=setup(tmp_path)
    target=tmp_path/"renders"/"public-scene.png"
    export_scene_png(root,projection,catalog=catalog,scene=scene,destination=target)
    before=target.read_bytes()
    with pytest.raises(FileExistsError):
        export_scene_png(root,projection,catalog=catalog,scene=scene,destination=target)
    assert target.read_bytes()==before


class SceneImage:
    def __init__(self, *, data, format):
        self.digest=sha256(__import__("base64").b64decode(data)).hexdigest()
    def subsample(self, x, y):
        assert x==y==4
        return self


class SceneCanvas(Canvas):
    def final_frame(self):
        return tuple(pic.digest for _, _, pic in self.painted)


def test_live_idle_displays_saved_scene_not_old_pixel_sprite(tmp_path,monkeypatch):
    monkeypatch.setitem(sys.modules,"tkinter",types.SimpleNamespace(PhotoImage=SceneImage))
    root, projection, catalog, scene=setup(tmp_path)
    save_scene_preset(root,scene,catalog=catalog)
    window, canvas, symbolic=Root(),SceneCanvas(),Symbolic()
    renderer=TkLayered2DRenderer(
        root=window,canvas=canvas,public_root=root,
        state_path=tmp_path/"sofia.db",fallback=symbolic,
    )
    renderer.render_idle(projection)
    assert renderer._last_art_source.startswith("public static scene")
    assert canvas.final_frame() and len(canvas.final_frame())==1
    assert symbolic.calls == []


def test_editor_imports_independent_background_with_no_db_mutation(tmp_path):
    from sofia.modules.avatar.scene_editor import _import_local_background, _public_projection
    root, projection, catalog, scene = setup(tmp_path)
    before=(tmp_path/"sofia.db").read_bytes()
    file=tmp_path/"custom-backdrop.jpg"
    Image.new("RGB",(128,96),(41,54,67)).save(file,"JPEG")
    ident, digest = _import_local_background(root,file)
    assert ident.startswith("owner-")
    stored = load_public_background(root,ident,digest)
    assert stored.startswith(b"\x89PNG\r\n\x1a\n")
    assert (tmp_path/"sofia.db").read_bytes()==before
    assert _public_projection(catalog,projection.outfit_id).item_ids==projection.item_ids


def test_scene_background_requires_explicit_unique_identifier(tmp_path):
    root, projection, catalog, scene=setup(tmp_path)
    with pytest.raises(FileExistsError):
        import_public_background(root, "neon-workshop", png_bytes())
    with pytest.raises(Avatar2DAssetError):
        import_public_background(root, "../private", png_bytes())
