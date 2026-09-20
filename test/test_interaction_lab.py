"""The lab has no renderer, model, live UI, journal or external side effects."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sofia.embodiment.store import AvatarStore
from sofia.interaction.core import InteractionEngine
from sofia.interaction.lab import InteractionLab, LabScene, LabStep, MAX_STEPS

AVATAR = Path(__file__).resolve().parents[1] / "src" / "sofia" / "data" / "avatar.json"
NOW = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)


@pytest.fixture
def lab():
    return InteractionLab(InteractionEngine(AvatarStore(AVATAR).load()))


def step(name, mode, **kwargs):
    return LabStep(step_id=name, modality=mode, occurred_at=NOW, **kwargs)


def scene(*steps):
    return LabScene(scene_id="test-scene", session_id="test-session", steps=steps)


@pytest.mark.parametrize("text,region,gesture", [
    ("*pats your head*", "head", "pat"),
    ("*taps your left ear*", "left-ear", "tap"),
    ("*strokes your tail tip*", "tail-tip", "stroke"),
    ("*holds your right hand*", "right-hand", "hold"),
    ("*touches your groin*", "groin", "touch"),
])
def test_text_and_pointer_fixture_share_meaning_policy_and_reaction_options(lab, text, region, gesture):
    trace = lab.run(scene(
        step("written", "text", text=text),
        step("pointer", "pointer", region_id=region, gesture=gesture),
    ))
    assert trace[0].semantics == trace[1].semantics
    assert trace[0].status == trace[1].status
    assert trace[0].emotion_options == trace[1].emotion_options
    assert trace[0].text_cues == trace[1].text_cues
    assert lab.replay(scene(
        step("written", "text", text=text),
        step("pointer", "pointer", region_id=region, gesture=gesture),
    )) == trace


def test_lab_keeps_discussion_distinct_from_completed_touch(lab):
    trace = lab.run(scene(
        step("talk", "text", text="How do I pat your head?"),
        step("action", "text", text="*pats your head*"),
    ))
    assert trace[0].status == "not_interaction"
    assert trace[0].semantics is None
    assert trace[1].status == "accepted"


def test_stop_is_effective_for_subsequent_text_and_pointer_and_resets_on_replay(lab):
    case = scene(
        step("before", "text", text="*pats your head*"),
        step("stop", "stop"),
        step("after-text", "text", text="*pats your head*"),
        step("after-pointer", "pointer", region_id="head", gesture="pat"),
    )
    trace = lab.run(case)
    assert tuple(item.status for item in trace) == ("accepted", "stopped", "denied", "denied")
    assert not trace[2].emotion_options and not trace[3].text_cues
    assert lab.replay(case) == trace
    assert lab.run(scene(step("new", "text", text="*pats your head*")))[0].status == "accepted"


def test_unfinished_or_cancelled_pointer_never_becomes_completed_touch(lab):
    trace = lab.run(scene(
        step("begin", "pointer", region_id="tail", gesture="stroke", phase="begin"),
        step("cancel", "pointer", region_id="tail", gesture="stroke", phase="cancel"),
    ))
    assert tuple(item.status for item in trace) == ("acknowledged", "denied")
    assert all(not item.emotion_options for item in trace)


def test_private_regions_are_redacted_in_export_without_erasing_internal_policy(lab):
    trace = lab.run(scene(
        step("private", "text", text="*touches your groin*"),
        step("ordinary", "text", text="*taps your left ear*"),
    ))
    assert trace[0].semantics[1] == "groin"
    assert trace[0].status == "denied"
    exported = lab.export_redacted(trace)
    assert exported[0]["semantics"][1] == "[restricted]"
    assert exported[0]["reason"] == "Restricted region."
    assert "groin" not in repr(exported)
    assert "touches your" not in repr(exported)
    assert exported[1]["semantics"][1] == "left-ear"
    assert lab.export_redacted(trace) == exported


def test_scene_rejects_duplicates_invalid_modes_time_order_and_unbounded_budget():
    with pytest.raises(ValueError, match="Duplicate"):
        scene(step("same", "text", text="*pats your head*"),
              step("same", "pointer", region_id="head", gesture="pat"))
    with pytest.raises(ValueError, match="chronological"):
        scene(LabStep("later", "stop", NOW + timedelta(seconds=1)), step("earlier", "stop"))
    with pytest.raises(ValueError, match="1 to 64"):
        scene(*(step(f"step-{n}", "stop") for n in range(MAX_STEPS + 1)))
    with pytest.raises(ValueError, match="Unsupported lab modality"):
        step("invalid", "real_click")
    with pytest.raises(ValueError, match="pre-resolved"):
        step("forged", "text", text="*pats your head*", region_id="head")
    with pytest.raises(ValueError, match="timezone-aware"):
        LabStep("bad-time", "stop", datetime(2026, 9, 20))


def test_a_lab_scene_cannot_open_an_unauthorized_region(lab):
    trace = lab.run(scene(step("attempt", "pointer", region_id="genitals", gesture="touch")))
    assert trace[0].status == "denied"
    assert trace[0].emotion_options == ()
    assert lab.export_redacted(trace)[0]["semantics"][1] == "[restricted]"
