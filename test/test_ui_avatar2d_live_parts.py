"""2D GUI-path acceptance without a window server: actual layered PNG frames.

These tests use the real sprite generator, actual RGBA bytes, current outfit
matrix and modular character loader, while replacing only Tk display surfaces.
A passing headless test does not replace a real Venus visual inspection.
"""
from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from types import SimpleNamespace
import sys
import types

import pytest

from sofia.modules.avatar.presentation import AudienceScope
from sofia.modules.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.modules.avatar.vtuber_public_setup import prepare_public_avatar2d
from sofia.core.embodiment.store import EmbodimentStore
from sofia.modules.ui.avatar2d_renderer import TkLayered2DRenderer
from sofia.modules.ui.avatar_renderer import AvatarRenderRequest


SEED = Path(__file__).resolve().parents[1] / "src/sofia/core/embodiment/avatar.json"


class Root:
    def __init__(self):
        self.pending = {}
        self.next = 0

    def after(self, _milliseconds, callback):
        self.next += 1
        self.pending[self.next] = callback
        return self.next

    def after_cancel(self, handle):
        self.pending.pop(handle, None)

    def advance(self):
        for handle, callback in tuple(self.pending.items()):
            self.pending.pop(handle, None)
            callback()


class Image:
    def __init__(self, *, data, format):
        assert format == "png"
        self.png = b64decode(data)
        assert self.png.startswith(b"\x89PNG\r\n\x1a\n")

    def subsample(self, x, y):
        assert (x, y) == (2, 2)
        return self


class Canvas:
    def __init__(self):
        self.current = []
        self.snapshots = []
        self.deleted = []
        self.visible = True

    def winfo_width(self):
        return 320

    def winfo_viewable(self):
        return self.visible

    def update_idletasks(self):
        self.snapshots.append(tuple(self.current))

    def delete(self, tag):
        self.deleted.append(tag)
        self.current.clear()

    def create_image(self, x, y, **kw):
        assert kw["tags"] == "avatar2d"
        self.current.append(kw["image"].png)
        return len(self.current)


class Fallback:
    backend_name = "symbolic-test"

    def __init__(self):
        self.render_calls = 0
        self.idle_calls = 0

    def render(self, request, *, completed):
        self.render_calls += 1
        completed(request.decision.decision_id, True, "symbolic fallback")

    def render_idle(self, projection):
        self.idle_calls += 1

    def stop(self):
        return None


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules, "tkinter", types.SimpleNamespace(PhotoImage=Image),
    )
    art = tmp_path / "public-2d"
    prepare_public_avatar2d(art)
    db = tmp_path / "sofia.db"
    bundle = load_or_bootstrap_presentation(
        embodiment=EmbodimentStore(SEED).load(),
        state_path=db,
    )
    projection = bundle.authority.projection(AudienceScope.PUBLIC)
    return art, db, projection


def test_live_2d_modular_renderer_paints_12_parts_and_actual_clothing(prepared):
    art, db, projection = prepared
    root, canvas, fallback = Root(), Canvas(), Fallback()
    renderer = TkLayered2DRenderer(
        root=root, canvas=canvas, public_root=art,
        state_path=db, fallback=fallback,
    )
    renderer.render_idle(projection)
    # Twelve independently selected face/ear/tail components, plus real
    # base-body sprite and all canonically occupied visible clothing layers.
    assert len(canvas.current) >= 17
    assert fallback.idle_calls == 0
    assert renderer._last_revision == projection.source_revision
    assert renderer._last_digest is not None


def test_blink_visibly_changes_png_frame_and_reports_three_painted_frames(prepared):
    art, db, projection = prepared
    root, canvas, fallback = Root(), Canvas(), Fallback()
    renderer = TkLayered2DRenderer(
        root=root, canvas=canvas, public_root=art,
        state_path=db, fallback=fallback,
    )
    results = []
    renderer.render(
        AvatarRenderRequest(
            SimpleNamespace(
                decision_id="blink.1", emotion_labels=(), gesture="blink",
            ),
            projection,
        ),
        completed=lambda *args: results.append(args),
    )
    assert len(canvas.snapshots) == 1
    assert results == []
    root.advance()
    assert len(canvas.snapshots) == 2
    # The character sprite set differs when both eyes close.
    assert canvas.snapshots[0] != canvas.snapshots[1]
    root.advance()
    assert len(canvas.snapshots) == 3
    assert canvas.snapshots[0] == canvas.snapshots[2]
    # Actual frame rendering is distinct from the deferred display
    # acknowledgement, so a painted frame alone is not a success receipt.
    assert results == []
    root.advance()  # scheduled final visible-frame receipt
    assert len(results) == 1
    assert results[0][0:2] == ("blink.1", True)
    assert "3 2D frame(s)" in results[0][2]
    assert fallback.render_calls == 0


def test_gesture_stop_prevents_late_2d_success_receipt(prepared):
    art, db, projection = prepared
    root, canvas = Root(), Canvas()
    renderer = TkLayered2DRenderer(
        root=root, canvas=canvas, public_root=art,
        state_path=db, fallback=Fallback(),
    )
    receipts = []
    renderer.render(
        AvatarRenderRequest(
            SimpleNamespace(
                decision_id="blink.stop", emotion_labels=(), gesture="blink",
            ), projection,
        ),
        completed=lambda *args: receipts.append(args),
    )
    assert renderer.stop() == "blink.stop"
    root.advance()
    assert receipts == []


def test_invalid_character_pack_is_never_blended_with_real_outfit(prepared):
    art, db, projection = prepared
    # Corrupt the selected public eye art without updating its manifest.
    (art / "character" / "eye_left" / "open.png").write_bytes(b"corrupt")
    fallback = Fallback()
    renderer = TkLayered2DRenderer(
        root=Root(), canvas=Canvas(), public_root=art,
        state_path=db, fallback=fallback,
    )
    receipts = []
    renderer.render(
        AvatarRenderRequest(
            SimpleNamespace(decision_id="corrupt", emotion_labels=(), gesture=None),
            projection,
        ), completed=lambda *args: receipts.append(args),
    )
    assert fallback.render_calls == 1
    assert len(receipts) == 1
    assert "symbolic fallback" in receipts[0][2]



def test_idle_blink_closes_eyes_and_reopens_without_chat_receipt(prepared):
    art, db, projection = prepared
    root, canvas = Root(), Canvas()
    renderer = TkLayered2DRenderer(
        root=root, canvas=canvas, public_root=art,
        state_path=db, fallback=Fallback(), idle_blink_ms=2000,
    )
    renderer.render_idle(projection)
    ordinary = tuple(canvas.current)
    assert ordinary and len(root.pending) == 1
    assert renderer._active_decision is None
    root.advance()  # scheduled real eye-closed PNG frame
    closed = tuple(canvas.current)
    assert closed != ordinary
    root.advance()  # reopen and schedule next natural blink
    assert tuple(canvas.current) == ordinary
    assert len(root.pending) == 1
    assert renderer.stop() is None
    assert root.pending == {}


def test_idle_blink_is_paused_for_hidden_canvas_and_resumes_when_visible(prepared):
    art, db, projection = prepared
    root, canvas = Root(), Canvas()
    renderer = TkLayered2DRenderer(
        root=root, canvas=canvas, public_root=art,
        state_path=db, fallback=Fallback(), idle_blink_ms=2000,
    )
    renderer.render_idle(projection)
    original = tuple(canvas.current)
    canvas.visible = False
    root.advance()
    assert tuple(canvas.current) == original
    assert len(root.pending) == 1
    canvas.visible = True
    root.advance()
    assert tuple(canvas.current) != original
    renderer.stop()
    assert root.pending == {}


def test_idle_blink_can_be_disabled_or_reject_malformed_interval(prepared):
    art, db, projection = prepared
    root = Root()
    renderer = TkLayered2DRenderer(
        root=root, canvas=Canvas(), public_root=art,
        state_path=db, fallback=Fallback(), idle_blink_ms=0,
    )
    renderer.render_idle(projection)
    assert root.pending == {}
    with pytest.raises(ValueError, match="idle blink interval"):
        TkLayered2DRenderer(
            root=root, canvas=Canvas(), public_root=art,
            state_path=db, fallback=Fallback(), idle_blink_ms=-1,
        )
