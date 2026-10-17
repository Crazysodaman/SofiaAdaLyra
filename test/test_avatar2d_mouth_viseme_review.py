"""Regression tests for semantic viseme repair and safe source-only frame swapping."""
from __future__ import annotations

from hashlib import sha256
import json

import pytest

Image = pytest.importorskip("PIL.Image")
from test.test_avatar2d_independent_features import staged as staged_features
from sofia.avatar.vtuber_mouth_viseme_review import (
    verify_review_mouths, compose_review_frame, create_review_frames,
    _EXTRAS, _ART_FILES,
)


@pytest.fixture
def mouth_staging(staged_features):
    features, foundation = staged_features
    # The test-feature fixture normally pins dummy body bytes. Replace only
    # its separate foundation with actual RGBA reference for frame assembly.
    for filename in ("head_base.png", "face_shading.png"):
        Image.new("RGBA", (2048, 2560)).save(foundation / filename)
    # Make blink and wink genuinely different from open-eye art in tests.
    # The shared Batch10/11 fixture normally uses the same 1px pixel for
    # every source pose; overwrite its closed variants with new 1px art.
    for side in ("left", "right"):
        closed = features / f"layers/eyes/eye_{side}/closed.png"
        image = Image.new("RGBA", (2048, 2560))
        x = 970 if side == "left" else 1060
        image.putpixel((x, 225), (255, 165, 180, 255))
        image.save(closed)
    features_manifest = features / "manifest.json"
    fdoc = json.loads(features_manifest.read_text())
    for entry in fdoc["files"]:
        if entry["file"] in {
            "layers/eyes/eye_left/closed.png",
            "layers/eyes/eye_right/closed.png",
        }:
            data = (features / entry["file"]).read_bytes()
            entry["sha256"] = sha256(data).hexdigest()
            entry["bytes"] = len(data)
    for entry in fdoc["sprites"]:
        if entry["file"] in {
            "layers/eyes/eye_left/closed.png",
            "layers/eyes/eye_right/closed.png",
        }:
            x = 970 if "eye_left" in entry["file"] else 1060
            entry["alpha_bbox"] = [x, 225, x+1, 226]
    fdoc["head_base_sha256"] = sha256((foundation / "head_base.png").read_bytes()).hexdigest()
    fdoc["face_shading_sha256"] = sha256((foundation / "face_shading.png").read_bytes()).hexdigest()
    features_manifest.write_text(json.dumps(fdoc))

    root = foundation.parent / "Batch12_13_MouthsVisemes-v1"
    root.mkdir(parents=True)
    for rel in sorted(_ART_FILES):
        file = root / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGBA", (2048, 2560))
        from PIL import ImageDraw
        # Distinct valid mouth positions, never outside the face region.
        if rel.endswith("/O.png"):
            bbox = (995, 296, 1020, 338)
        elif rel.endswith("/M.png"):
            bbox = (976, 312, 1040, 317)
        else:
            bbox = (982, 306, 1036, 327)
        ImageDraw.Draw(image).ellipse(bbox, fill=(173, 75, 111, 255))
        image.save(file)
    for rel in _EXTRAS:
        file = root / rel
        if rel.endswith(".png"):
            Image.new("RGB", (30, 20)).save(file)
        elif rel.endswith(".gif"):
            Image.new("P", (30, 20)).save(file)
        else:
            file.write_text(rel)
    rows = [
        {"file": str(p.relative_to(root)).replace("\\", "/"),
         "bytes": p.stat().st_size, "sha256": sha256(p.read_bytes()).hexdigest()}
        for p in root.rglob("*") if p.is_file()
    ]
    sprites = []
    for rel in sorted(_ART_FILES):
        with Image.open(root / rel) as im:
            bbox = im.getchannel("A").getbbox()
        sprites.append({
            "file": rel, "role": ("mouth" if "/mouths/" in rel else "viseme"),
            "state": (root / rel).stem, "alpha_bbox": list(bbox),
        })
    doc = {
        "schema": "sofia.avatar2d.mouth_viseme_source_review.v1",
        "private_source_only": True, "production_activated": False,
        "review_status": "visual_corrections_await_owner",
        "master_canvas": [2048, 2560], "mouth_anchor": [1008, 317],
        "head_base_sha256": sha256((foundation / "head_base.png").read_bytes()).hexdigest(),
        "face_shading_sha256": sha256((foundation / "face_shading.png").read_bytes()).hexdigest(),
        "features_manifest_sha256": sha256(features_manifest.read_bytes()).hexdigest(),
        "source_flaws": {
            "viseme_A": "original PNG depicts hair",
            "viseme_O": "original PNG depicts hair",
            "viseme_M": "original PNG depicts incorrectly open mouth",
        },
        "files": rows, "sprites": sprites,
    }
    (root / "manifest.json").write_text(json.dumps(doc))
    return root, foundation, features


def test_complete_repaired_pack_reports_no_live_activation(mouth_staging):
    mouth, foundation, features = mouth_staging
    report = verify_review_mouths(
        mouth, foundation_root=foundation, features_root=features
    )
    assert report["mouth_states"] == report["viseme_states"] == 6
    assert report["verified_files"] == len(_EXTRAS) + 12
    assert report["voice_lip_sync_implemented"] is False
    assert report["production_activated"] is False


def test_tampered_viseme_rejected(mouth_staging):
    mouth, foundation, features = mouth_staging
    (mouth / "layers" / "visemes" / "A.png").write_bytes(b"hair")
    with pytest.raises(ValueError, match="mismatch"):
        verify_review_mouths(
            mouth, foundation_root=foundation, features_root=features
        )


def test_semantically_wrong_hair_outside_mouth_slot_is_rejected(mouth_staging):
    mouth, foundation, features = mouth_staging
    file = mouth / "layers" / "visemes" / "O.png"
    hair = Image.new("RGBA", (2048, 2560))
    hair.putpixel((900, 80), (170, 12, 40, 255))
    hair.save(file)
    manifest_path = mouth / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["files"]:
        if entry["file"] == "layers/visemes/O.png":
            entry["sha256"] = sha256(file.read_bytes()).hexdigest()
            entry["bytes"] = file.stat().st_size
    for entry in manifest["sprites"]:
        if entry["file"] == "layers/visemes/O.png":
            entry["alpha_bbox"] = [900, 80, 901, 81]
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="outside face slot"):
        verify_review_mouths(
            mouth, foundation_root=foundation, features_root=features
        )


def test_independent_blink_wink_and_mouth_frame_pixels(mouth_staging):
    mouth, foundation, features = mouth_staging
    kwargs = dict(foundation_root=foundation, features_root=features, mouths_root=mouth)
    neutral = compose_review_frame(expression="neutral", **kwargs)
    blink = compose_review_frame(expression="blink", **kwargs)
    left = compose_review_frame(expression="left_wink", **kwargs)
    right = compose_review_frame(expression="right_wink", **kwargs)
    open_mouth = compose_review_frame(expression="O", **kwargs)
    assert neutral.tobytes() != blink.tobytes()
    assert left.tobytes() != right.tobytes()
    assert neutral.tobytes() != open_mouth.tobytes()


def test_review_frames_are_never_published_or_overwritten(mouth_staging, tmp_path):
    mouth, foundation, features = mouth_staging
    args = dict(mouths_root=mouth, foundation_root=foundation, features_root=features)
    with pytest.raises(ValueError, match="public folders"):
        create_review_frames(output=tmp_path / "Public-V2" / "output", **args)
    folder = mouth.parent / "Reviewed-Frames"
    files = create_review_frames(output=folder, **args)
    assert len(files) == 12
    assert (folder / "00_neutral.png").is_file()
    with pytest.raises(ValueError, match="new absolute"):
        create_review_frames(output=folder, **args)


def test_manifest_cannot_self_activate(mouth_staging):
    mouth, foundation, features = mouth_staging
    path = mouth / "manifest.json"
    doc = json.loads(path.read_text())
    doc["production_activated"] = True
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="unsafe mouth"):
        verify_review_mouths(mouth, foundation_root=foundation, features_root=features)
