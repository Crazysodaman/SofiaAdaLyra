from datetime import datetime, timezone
from threading import Event

from sofia.application.expression_runtime import ExpressionRuntime
from sofia.avatar.presentation import (
    AppearanceState, AttireMode, AudienceScope, PresentationProjection,
)
from sofia.cognition.matrix import EmbodiedExpressionPlan
from sofia.emotion.model import ActiveEmotion, CurrentEmotionalState
from sofia.personality.influence import ContinuityInfluence
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.ui.avatar_renderer import AvatarRenderRequest, TkAvatarRenderer
from sofia.application import SofiaApplication
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from pathlib import Path
import pytest


pytestmark = [
    pytest.mark.pkg_core,
    pytest.mark.pkg_avatar,
    pytest.mark.pkg_voice,
    pytest.mark.pkg_ui,
]


NOW = datetime(2026, 10, 10, 12, tzinfo=timezone.utc)


def influence():
    return ContinuityInfluence(
        daypart="evening", season="autumn", daylight="night",
        weather_condition="rain", temperature_c=12.0,
        weather_freshness="current", location_freshness="current",
        primary_emotion_evidence_refs=("emotion:event-1",),
        emotional_tone="warm", primary_emotion="fondness",
        primary_intensity=.6, active_emotions=("fondness", "curiosity"),
        foreground_emotion_evidence_refs=("emotion:event-2",),
        foreground_emotion="curiosity", foreground_intensity=.5,
        daypart_evidence_refs=("runtime.clock",),
        season_evidence_refs=("runtime.clock",),
        weather_evidence_refs=("environment.weather:test",),
    )


def decision(tmp_path):
    path = tmp_path / "sofia.db"
    path.touch()
    runtime = ExpressionRuntime(path)
    principal = PrincipalContext(
        "sparks", "desktop-owner", AudienceKind.PRIVATE, "Sparks",
    )
    state = CurrentEmotionalState(
        NOW, "sparks", "warm",
        (
            ActiveEmotion("fondness", .6, ("emotion:event-1",), ("event-1",)),
            ActiveEmotion("curiosity", .5, ("emotion:event-2",), ("event-2",)),
        ),
    )
    plan = EmbodiedExpressionPlan(
        "ear-perk", ("smile",), "lean-forward", ("stand-relaxed",),
        (), "moderate", ("emotion", "daypart"), "grounded fixture",
    )
    value = runtime.decide(
        message_id="assistant-1", session_id="session-1", principal=principal,
        intent="conversation", text="I found it.", state=state,
        influence=influence(), plan=plan, presentation_revision=3,
        created_at=NOW,
    )
    return runtime, value, principal


def test_expression_decision_is_scoped_and_outputs_need_independent_ack(tmp_path):
    runtime, value, principal = decision(tmp_path)
    assert runtime.latest(principal) == value
    assert value.gesture == "ear-perk"
    assert value.emotion_evidence_refs == ("emotion:event-1", "emotion:event-2")
    receipts = runtime.receipts(value.decision_id)
    assert [(item.output, item.status, item.acknowledged) for item in receipts] == [
        ("text", "persisted", True)
    ]

    runtime.receipt(
        decision_id=value.decision_id, output="avatar", status="queued",
        acknowledged=False, backend="fixture", detail="scheduled",
        occurred_at=NOW,
    )
    assert next(
        item for item in runtime.receipts(value.decision_id)
        if item.output == "avatar"
    ).acknowledged is False


class FakeRoot:
    def __init__(self):
        self.callbacks = []

    def after(self, _milliseconds, callback):
        self.callbacks.append(callback)
        return len(self.callbacks)

    def after_cancel(self, _handle):
        return None


class FakeCanvas:
    def __init__(self):
        self.frames = 0

    def delete(self, _tag):
        self.frames += 1

    def winfo_width(self):
        return 320

    def winfo_height(self):
        return 230

    def create_line(self, *args, **kwargs):
        return 1

    create_oval = create_line
    create_arc = create_line
    create_polygon = create_line
    create_text = create_line

    def update_idletasks(self):
        return None


def test_renderer_acknowledges_only_after_last_visible_frame(tmp_path):
    _runtime, value, _principal = decision(tmp_path)
    presentation = PresentationProjection(
        AudienceScope.PUBLIC, 3, AttireMode.CLOTHED, "engineer.signature",
        ("top",), AppearanceState("long layered", "deep crimson", "dark violet"),
        False, "fixture", ("Engineer top",),
    )
    root, canvas, completed = FakeRoot(), FakeCanvas(), []
    renderer = TkAvatarRenderer(root=root, canvas=canvas)
    renderer.render(
        AvatarRenderRequest(value, presentation),
        completed=lambda *args: completed.append(args),
    )
    assert completed == []
    while root.callbacks:
        root.callbacks.pop(0)()
    assert completed == [(value.decision_id, True, "rendered 5 visible frame(s): ear-perk")]
    assert canvas.frames == 5


def test_renderer_stop_prevents_completion_acknowledgement(tmp_path):
    _runtime, value, _principal = decision(tmp_path)
    presentation = PresentationProjection(
        AudienceScope.PUBLIC, 3, AttireMode.CLOTHED, "engineer.signature",
        ("top",), AppearanceState("long layered", "deep crimson", "dark violet"),
        False, "fixture", ("Engineer top",),
    )
    root, completed = FakeRoot(), []
    renderer = TkAvatarRenderer(root=root, canvas=FakeCanvas())
    renderer.render(
        AvatarRenderRequest(value, presentation),
        completed=lambda *args: completed.append(args),
    )
    assert renderer.stop() == value.decision_id
    while root.callbacks:
        root.callbacks.pop(0)()
    assert completed == []


def test_production_conversation_records_expression_and_restores_it_after_restart(tmp_path):
    project = Path(__file__).resolve().parents[1]
    personality = tmp_path / "personality.json"
    personality.write_text(
        '{"name":"Sofía","traits":["witty","warm","skeptical"],'
        '"communication_style":"Direct, warm, witty, and evidence-minded."}',
        encoding="utf-8",
    )
    configuration = SofiaConfiguration(
        constitution_path=project / "src/sofia/constitution/constitution.md",
        constitution_hash_path=project / "src/sofia/constitution/constitution.sha256",
        identity_path=project / "src/sofia/identity/identity.json",
        personality_path=personality,
        avatar_path=project / "src/sofia/embodiment/avatar.json",
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=project,
    )
    first = SofiaApplication(configuration)
    first.start()
    try:
        first.text_ui.save_draft("Hello, what are you thinking about?")
        first.text_ui.send()
        assistant = first.text_ui.history()[-1]
        recorded = first.expression_runtime.get_for_message(assistant.message_id)
        assert recorded is not None, first.conversation.last_expression_runtime_error
        assert recorded.principal_id
        assert first.conversation.last_expression_runtime_error is None
        assert first.expression_runtime.receipts(recorded.decision_id)[0].status == "persisted"
    finally:
        first.shutdown()

    second = SofiaApplication(configuration)
    second.start()
    try:
        assert second.expression_runtime.get_for_message(assistant.message_id) == recorded
    finally:
        second.shutdown()
