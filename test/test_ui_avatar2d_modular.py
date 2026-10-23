"""Verified public modular face, eye, ear and tail PNGs on canonical wardrobe."""
from __future__ import annotations

from base64 import b64decode
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace
import json
import sys
import types

from sofia.modules.avatar.presentation import AudienceScope, AttireMode
from sofia.modules.avatar.vtuber_character_bundle import load_selected_character_sprites
from sofia.modules.avatar.vtuber_character_parts import generate_public_character_parts
from sofia.modules.avatar.vtuber_character_selection import select_character_parts
from sofia.modules.ui.avatar_renderer import AvatarRenderRequest
from sofia.modules.ui.avatar2d_renderer import TkLayered2DRenderer
from test.test_ui_avatar2d_renderer import env, Root, Canvas, Symbolic


class TracedPhotoImage:
    def __init__(self, *, data, format):
        assert format == "png"
        self.digest = sha256(b64decode(data)).hexdigest()

    def subsample(self, x, y):
        assert (x, y) == (2, 2)
        return self


class TracedCanvas(Canvas):
    def __init__(self):
        super().__init__()
        self.frames = []

    def delete(self, tag):
        if tag == "avatar2d" and self.painted:
            self.frames.append(tuple(image.digest for _, _, image in self.painted))
        super().delete(tag)

    def final_frame(self):
        return tuple(image.digest for _, _, image in self.painted)


def configured(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules, "tkinter", types.SimpleNamespace(PhotoImage=TracedPhotoImage),
    )
    public_root, projection, state = env(tmp_path)
    generate_public_character_parts(public_root / "character")
    root, canvas, fallback = Root(), TracedCanvas(), Symbolic()
    renderer = TkLayered2DRenderer(
        root=root, canvas=canvas, public_root=public_root,
        state_path=state, fallback=fallback,
    )
    return renderer, root, canvas, fallback, public_root, projection


def selected_digests(root, projection, *, gesture=None, expression="neutral"):
    selected = select_character_parts(
        projection, gesture=gesture, expression=expression,
    )
    sprites = load_selected_character_sprites(root / "character", selected)
    return {sprite.group: sprite.digest for sprite in sprites}


def decision(projection, gesture=None, *, emotions=()):
    return AvatarRenderRequest(
        SimpleNamespace(
            decision_id="d.modular", gesture=gesture,
            emotion_labels=emotions,
        ),
        projection,
    )


def test_modular_art_does_not_draw_duplicate_baked_in_face_hair_or_tail(
    tmp_path, monkeypatch,
):
    renderer, _, canvas, fallback, public_root, projection = configured(
        tmp_path, monkeypatch,
    )
    renderer.render_idle(projection)
    expected = selected_digests(public_root, projection)
    frame = canvas.final_frame()
    assert all(value in frame for value in expected.values())
    assert len(frame) >= 16
    assert renderer._last_revision == projection.source_revision
    assert fallback.calls == []
    doc = json.loads(
        (public_root / "outfits" / "day.default" / "manifest.json").read_text()
    )
    removed = {row["sha256"] for row in doc["layers"]
               if row["role"] in ("base_back", "base_face", "base_front")}
    assert not removed.intersection(frame)
    assert expected["ear_left"] in frame
    assert expected["ear_right"] in frame
    assert expected["tail"] in frame


def test_tail_flick_renders_three_actual_frames_before_acknowledgement(
    tmp_path, monkeypatch,
):
    renderer, root, canvas, fallback, public_root, projection = configured(
        tmp_path, monkeypatch,
    )
    results = []
    renderer.render(
        decision(projection, "tail-flick"),
        completed=lambda *args: results.append(args),
    )
    idle_tail = selected_digests(public_root, projection)["tail"]
    moving_tail = selected_digests(
        public_root, projection, gesture="tail-flick",
    )["tail"]
    assert idle_tail != moving_tail
    assert idle_tail in canvas.final_frame()
    assert results == []
    root.run()
    assert moving_tail in canvas.final_frame()
    assert results == []
    root.run()
    assert idle_tail in canvas.final_frame()
    assert results == []
    root.run()
    assert len(results) == 1
    assert results[0][0] == "d.modular"
    assert results[0][1] is True
    assert "3 2D frame(s)" in results[0][2]
    assert fallback.calls == []


def test_blink_and_wink_have_independent_eye_sprites(tmp_path, monkeypatch):
    renderer, root, canvas, _, public_root, projection = configured(
        tmp_path, monkeypatch,
    )
    receipts = []
    renderer.render(
        decision(projection, "blink"), completed=lambda *v: receipts.append(v),
    )
    eye_open = selected_digests(public_root, projection)
    eye_closed = selected_digests(public_root, projection, expression="blink")
    assert eye_open["eye_left"] != eye_closed["eye_left"]
    assert eye_open["eye_right"] != eye_closed["eye_right"]
    root.run()
    assert eye_closed["eye_left"] in canvas.final_frame()
    assert eye_closed["eye_right"] in canvas.final_frame()
    root.run()
    root.run()
    assert receipts[0][1] is True
    renderer.render(
        decision(projection, "wink"), completed=lambda *v: receipts.append(v),
    )
    root.run()
    wink = selected_digests(public_root, projection, expression="wink")
    assert wink["eye_left"] == eye_closed["eye_left"]
    assert wink["eye_right"] == eye_open["eye_right"]
    assert wink["eye_left"] in canvas.final_frame()
    assert wink["eye_right"] in canvas.final_frame()


def test_stopping_animation_cancels_inflight_receipt(tmp_path, monkeypatch):
    renderer, root, canvas, _, _, projection = configured(
        tmp_path, monkeypatch,
    )
    results = []
    renderer.render(
        decision(projection, "ear-flick"),
        completed=lambda *v: results.append(v),
    )
    assert renderer.stop() == "d.modular"
    root.run()
    root.run()
    assert results == []


def test_corrupt_modular_png_uses_safe_symbolic_fallback_not_mixed_art(
    tmp_path, monkeypatch,
):
    renderer, root, canvas, fallback, public_root, projection = configured(
        tmp_path, monkeypatch,
    )
    bad = public_root / "character" / "eye_left" / "open.png"
    bad.write_bytes(b"corrupted-image")
    receipts = []
    renderer.render(
        decision(projection), completed=lambda *v: receipts.append(v),
    )
    assert fallback.calls == ["fallback_render"]
    assert receipts and receipts[0][2] == "symbolic Tk frames"
    assert canvas.final_frame() == ()


def test_private_projection_never_enters_public_character_pack(
    tmp_path, monkeypatch,
):
    renderer, _, canvas, fallback, _, projection = configured(
        tmp_path, monkeypatch,
    )
    private = replace(
        projection, audience=AudienceScope.PRIVATE,
        attire=AttireMode.NUDE, private_fallback_used=False,
    )
    receipts = []
    renderer.render(
        decision(private), completed=lambda *v: receipts.append(v),
    )
    assert receipts[0][1] is False
    assert fallback.calls == []
    assert canvas.final_frame() == ()



def test_unavailable_character_recolor_is_not_falsely_reported_as_rendered(
    tmp_path, monkeypatch,
):
    renderer, _, canvas, fallback, _, projection = configured(
        tmp_path, monkeypatch,
    )
    recolored = replace(
        projection, appearance=replace(
            projection.appearance, hair_color="#4169E1",
        ),
    )
    renderer.render_idle(recolored)
    assert fallback.calls == ["fallback_idle"]
    assert canvas.final_frame() == ()
