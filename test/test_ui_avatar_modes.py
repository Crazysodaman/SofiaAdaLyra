"""Exclusive 2D/3D mode selection, late receipts and durable UI preference."""
from types import SimpleNamespace

import pytest

from sofia.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.ui.avatar_mode import (
    AvatarVisualMode, AvatarModeUnavailable, ExclusiveAvatarRenderer,
)
from sofia.ui.avatar_mode_store import AvatarModePreferenceStore
from sofia.ui.avatar_renderer import AvatarRenderRequest


class FakeRenderer:
    def __init__(self, name):
        self.backend_name = name
        self.pending = None
        self.active = None
        self.history = []
        self.idle_count = 0

    def stop(self):
        self.history.append("stop")
        old = self.active
        self.active = None
        return old

    def render(self, request, *, completed):
        self.history.append("render")
        self.active = request.decision.decision_id
        self.pending = completed

    def render_idle(self, projection):
        self.history.append("idle")
        self.idle_count += 1


def request():
    return AvatarRenderRequest(
        SimpleNamespace(decision_id="d.1"),
        SimpleNamespace(source_revision=1),
    )


def test_unavailable_3d_does_not_switch_or_cancel_real_2d_animation():
    flat = FakeRenderer("real-2d")
    manager = ExclusiveAvatarRenderer(two_d=flat)
    results = []
    manager.render(request(), completed=lambda *receipt: results.append(receipt))
    with pytest.raises(AvatarModeUnavailable, match="not installed"):
        manager.select(AvatarVisualMode.THREE_D)
    assert manager.active_mode is AvatarVisualMode.TWO_D
    assert flat.active == "d.1"
    assert flat.history == ["render"]
    flat.pending("d.1", True, "2D painted")
    assert results == [("d.1", True, "2D painted")]


def test_switch_cancels_old_2d_and_blocks_late_acknowledgement():
    a = FakeRenderer("real-2d")
    b = FakeRenderer("real-3d")
    clears = []
    manager = ExclusiveAvatarRenderer(
        two_d=a, three_d=b, clear_visual=lambda: clears.append("cleared")
    )
    events = []
    manager.render(request(), completed=lambda *v: events.append(v))
    old_callback = a.pending
    switch = manager.select(AvatarVisualMode.THREE_D)
    assert switch.changed
    assert switch.cancelled_decision_id == "d.1"
    assert switch.cancelled_backend == "real-2d"
    assert clears == ["cleared"]
    assert manager.backend_name == "real-3d"
    assert manager.active_mode is AvatarVisualMode.THREE_D
    old_callback("d.1", True, "late 2D frame")
    assert events == []
    manager.render(request(), completed=lambda *v: events.append(v))
    b.pending("d.1", True, "3D host painted")
    assert events == [("d.1", True, "3D host painted")]
    back = manager.select(AvatarVisualMode.TWO_D)
    assert back.changed
    assert manager.active_mode is AvatarVisualMode.TWO_D
    assert clears == ["cleared", "cleared"]
    assert manager.available_modes == (
        AvatarVisualMode.TWO_D, AvatarVisualMode.THREE_D
    )


def test_unchanged_mode_does_not_stop_or_reinitialize():
    a = FakeRenderer("2d")
    manager = ExclusiveAvatarRenderer(two_d=a)
    result = manager.select(AvatarVisualMode.TWO_D)
    assert not result.changed
    assert result.cancelled_decision_id is None
    assert a.history == []


def test_idle_only_paints_into_one_selected_backend():
    a = FakeRenderer("2d")
    b = FakeRenderer("3d")
    m = ExclusiveAvatarRenderer(two_d=a, three_d=b)
    projection = SimpleNamespace()
    m.render_idle(projection)
    assert a.idle_count == 1 and b.idle_count == 0
    m.select(AvatarVisualMode.THREE_D)
    m.render_idle(projection)
    assert a.idle_count == 1 and b.idle_count == 1


def test_mode_store_only_writes_canonical_db_and_survives_restart(tmp_path):
    db = tmp_path / "sofia.db"
    bootstrap_canonical_sqlite(db)
    store = AvatarModePreferenceStore(db)
    assert store.load() is AvatarVisualMode.TWO_D
    store.save(AvatarVisualMode.THREE_D)
    assert AvatarModePreferenceStore(db).load() is AvatarVisualMode.THREE_D
    store.save(AvatarVisualMode.TWO_D)
    assert AvatarModePreferenceStore(db).load() is AvatarVisualMode.TWO_D
    with pytest.raises(ValueError):
        store.save("3d")
    assert not (tmp_path / "avatar-mode.json").exists()


def test_same_object_cannot_be_both_2d_and_3d():
    backend = FakeRenderer("only-one")
    with pytest.raises(ValueError, match="different renderer"):
        ExclusiveAvatarRenderer(two_d=backend, three_d=backend)
