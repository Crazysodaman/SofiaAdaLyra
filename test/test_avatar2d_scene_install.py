"""ZIP acceptance: complete public Autumn Cyber scene, no partial/private installs."""
from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from PIL import Image

from sofia.modules.avatar.scene_compositor import SceneSettings, load_public_background
from sofia.modules.avatar.scene_install import install_public_scene_pack
from sofia.modules.avatar.vtuber_asset_bundle import Avatar2DAssetError
from sofia.modules.avatar.vtuber_starter_art import _base
from sofia.modules.avatar.wardrobe_catalog import build_starter_wardrobe
from test.test_ui_avatar2d_renderer import env


def archive_bytes(tmp_path, *, corrupt=False, extra=None):
    catalog=build_starter_wardrobe()
    plan=next(p for p in catalog.presets if p.outfit_id=="outfit.autumn_cyber")
    image=_base("face")
    image_out=BytesIO()
    Image.new("RGBA",(64,64),(23,30,58,255)).save(image_out,"PNG")
    bg=image_out.getvalue()
    bg_digest=sha256(bg).hexdigest()
    scene=SceneSettings(
        outfit_id=plan.outfit_id,item_ids=plan.item_ids,
        background_id="autumn_neon",background_sha256=bg_digest,
    )
    portrait={
        "schema":"sofia-public-illustrated-static-v1",
        "outfit_id":scene.outfit_id,"item_ids":list(scene.item_ids),
        "portrait_sha256":sha256(image).hexdigest(),
        "image_size":[320,400], "public_only":True,
        "quality":"unreviewed_illustrated_candidate", "animation":"static",
    }
    if corrupt:
        portrait["portrait_sha256"]="0"*64
    bg_manifest={
        "schema":"sofia.avatar2d.public_background.v1",
        "id":"autumn_neon","sha256":bg_digest,"public_only":True,
    }
    payload={
        "portraits/outfit.autumn_cyber/portrait.png":image,
        "portraits/outfit.autumn_cyber/manifest.json":json.dumps(portrait).encode(),
        "scenes/backgrounds/autumn_neon/background.png":bg,
        "scenes/backgrounds/autumn_neon/manifest.json":json.dumps(bg_manifest).encode(),
        "scenes/presets/outfit.autumn_cyber.json":json.dumps(scene.as_dict()).encode(),
    }
    if extra is not None:
        payload.update(extra)
    path=tmp_path/"art.zip"
    with ZipFile(path, "w") as out:
        for name, data in payload.items():
            out.writestr(name,data)
    return path


def test_scene_install_stages_source_checked_files(tmp_path):
    root, _, _=env(tmp_path)
    (root/"character").mkdir()
    (root/"character"/"manifest.json").write_text("{}")
    zipfile=archive_bytes(tmp_path)
    planned=install_public_scene_pack(zipfile,root,verify_only=True)
    assert planned.outfit_id=="outfit.autumn_cyber"
    assert not (root/"portraits"/planned.outfit_id).exists()
    done=install_public_scene_pack(zipfile,root)
    assert done==planned
    assert (root/"portraits"/planned.outfit_id/"portrait.png").is_file()
    assert load_public_background(root,"autumn_neon",done.background_sha256)
    with pytest.raises(FileExistsError):
        install_public_scene_pack(zipfile,root)


def test_scene_install_rejects_hash_mismatch_without_any_files(tmp_path):
    root,_,_=env(tmp_path)
    (root/"character").mkdir()
    (root/"character"/"manifest.json").write_text("{}")
    zipfile=archive_bytes(tmp_path,corrupt=True)
    with pytest.raises(Avatar2DAssetError):
        install_public_scene_pack(zipfile,root)
    assert not (root/"portraits").exists()


def test_scene_install_rejects_zip_traversal_before_write(tmp_path):
    root,_,_=env(tmp_path)
    (root/"character").mkdir()
    (root/"character"/"manifest.json").write_text("{}")
    zipfile=archive_bytes(tmp_path, extra={"../../outside.txt":b"wrong"})
    with pytest.raises(Avatar2DAssetError):
        install_public_scene_pack(zipfile,root)
    assert not (tmp_path/"outside.txt").exists()


def test_scene_install_rejects_missing_base_public_pack(tmp_path):
    root,_,_=env(tmp_path)
    zipfile=archive_bytes(tmp_path)
    with pytest.raises(Avatar2DAssetError):
        install_public_scene_pack(zipfile,root)
