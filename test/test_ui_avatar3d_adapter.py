"""3D can only acknowledge installed real driver frames; no fictional rig."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from sofia.avatar.presentation import AttireMode, AudienceScope
from sofia.avatar.presentation_runtime import load_or_bootstrap_presentation
from sofia.embodiment.store import EmbodimentStore
from sofia.ui.avatar3d_renderer import Avatar3DRenderer, Avatar3DRig
from sofia.ui.avatar_renderer import AvatarRenderRequest


SEED = Path(__file__).resolve().parents[1] / "src/sofia/embodiment/avatar.json"


def projection(tmp_path):
    runtime = load_or_bootstrap_presentation(
        embodiment=EmbodimentStore(SEED).load(),
        state_path=tmp_path / "sofia.db",
    )
    return runtime.authority.projection(AudienceScope.PUBLIC)


def rig():
    return Avatar3DRig(
        model_id="sofia.model.3d",
        model_sha256="a" * 64,
        rig_id="fox.rig.1",
        supported_gestures=frozenset(("ear-perk", "tail-flick")),
        supported_poses=frozenset(("stand-relaxed",)),
    )


class RealDriverFixture:
    def __init__(self, ready=True):
        self.installed = ready
        self.stop_calls = 0
        self.cues = []
        self.callback = None
        self.idle_count = 0

    def ready(self, required):
        return self.installed and required.model_sha256 == "a"*64

    def stop(self):
        self.stop_calls += 1
        return None

    def render(self, cue, *, completed):
        self.cues.append(cue)
        self.callback = completed

    def render_idle(self, projection):
        self.idle_count += 1


def request(tmp_path, *, gesture="ear-perk"):
    p = projection(tmp_path)
    d = SimpleNamespace(
        decision_id="d3.1",
        presentation_revision=p.source_revision,
        gesture=gesture,
        pose="stand-relaxed",
        intensity="subtle",
        emotion_labels=("focused",),
    )
    return AvatarRenderRequest(d, p)


def test_no_uninstalled_3d_driver_is_considered_available():
    with pytest.raises(RuntimeError, match="unavailable"):
        Avatar3DRenderer(rig=rig(), driver=RealDriverFixture(ready=False))
    with pytest.raises(TypeError, match="rig"):
        Avatar3DRenderer(rig=None, driver=RealDriverFixture())


def test_real_driver_receipt_is_required_before_any_3d_render_success(tmp_path):
    driver = RealDriverFixture()
    engine = Avatar3DRenderer(rig=rig(), driver=driver)
    result = []
    engine.render(request(tmp_path), completed=lambda *args: result.append(args))
    assert len(driver.cues) == 1
    cue = driver.cues[0]
    assert cue.model_sha256 == "a"*64
    assert cue.gesture == "ear-perk"
    assert cue.outfit_id == "day.default"
    assert cue.garment_ids
    assert result == []  # merely requesting a render is NOT a frame receipt
    driver.callback("d3.1", True, "GPU presented verified frame")
    assert result == [("d3.1", True, "GPU presented verified frame")]


def test_3d_bone_mapping_and_mode_stop_are_independent_of_2d(tmp_path):
    driver = RealDriverFixture()
    renderer = Avatar3DRenderer(rig=rig(), driver=driver)
    outcomes = []
    renderer.render(
        request(tmp_path, gesture="nonexistent-bone"),
        completed=lambda *args: outcomes.append(args),
    )
    assert driver.cues[-1].gesture is None
    callback = driver.callback
    assert renderer.stop() == "d3.1"
    callback("d3.1", True, "stale frame")
    assert outcomes == []
    assert driver.stop_calls >= 2


def test_3d_public_host_does_not_decode_or_display_private_nude(tmp_path):
    driver = RealDriverFixture()
    renderer = Avatar3DRenderer(rig=rig(), driver=driver)
    original = request(tmp_path)
    private = replace(
        original.presentation, audience=AudienceScope.PRIVATE,
        attire=AttireMode.NUDE, private_fallback_used=False,
    )
    outcomes = []
    renderer.render(
        AvatarRenderRequest(original.decision, private),
        completed=lambda *args: outcomes.append(args),
    )
    assert outcomes and outcomes[0][1] is False
    assert driver.cues == []
    renderer.render_idle(private)
    assert driver.idle_count == 0


def test_3d_stale_wardrobe_revision_fails_before_gpu_driver(tmp_path):
    driver = RealDriverFixture()
    renderer = Avatar3DRenderer(rig=rig(), driver=driver)
    original = request(tmp_path)
    stale = replace(original.presentation, source_revision=22)
    events = []
    renderer.render(
        AvatarRenderRequest(original.decision, stale),
        completed=lambda *args: events.append(args),
    )
    assert events[0][1] is False
    assert driver.cues == []
