from pathlib import Path
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from sofia.application import SofiaApplication
from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.interaction.ledger import InteractionLedger
from sofia.interaction.registry import InteractionCatalog
from sofia.interaction.reviewed_hug_question import CLARIFICATION
from sofia.interaction.source_link import VerifiedInteractionState
from sofia.neuro import NeuralSignal
from sofia.emotion.model import CurrentEmotionalState
from sofia.social.model import AudienceKind, PrincipalContext
from sofia.social.principals import local_sparks_principal
from sofia.goals import CompletionKind, GoalCompletionCondition


pytestmark = pytest.mark.pkg_core
PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_PATH = PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.md"
HASH_PATH = PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.sha256"
IDENTITY_PATH = PROJECT_ROOT / "src" / "sofia" / "identity" / "identity.json"
AVATAR_PATH = PROJECT_ROOT / "src" / "sofia" / "embodiment" / "avatar.json"


def configuration(tmp_path: Path) -> SofiaConfiguration:
    personality = tmp_path / "personality.json"
    personality.write_text(
        """{
  "name": "Sofía Ada Lyra",
  "traits": ["rigorous", "curious", "direct"],
  "communication_style": "Clear, direct, warm and natural."
}""",
        encoding="utf-8",
    )
    return SofiaConfiguration(
        constitution_path=CONSTITUTION_PATH,
        constitution_hash_path=HASH_PATH,
        identity_path=IDENTITY_PATH,
        personality_path=personality,
        avatar_path=AVATAR_PATH,
        state_path=tmp_path / "sofia.db",
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=PROJECT_ROOT,
    )


def _capture_runtime(monkeypatch, app):
    requests = []

    def respond(request, filesystem_results=(), **kwargs):
        requests.append(request)
        return CognitiveResponse(content="Captured.")

    monkeypatch.setattr(app.runtime, "respond", respond)
    return requests


def _quiet_background(monkeypatch):
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
    monkeypatch.setenv("SOFIA_HABIT_LEARNING", "0")


def test_live_conversation_projects_neuro_snapshot_into_matrix_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    requests.clear()
    try:
        app.conversation.respond("How are you?")

        assert requests
        request = requests[-1]
        neuro = tuple(
            message
            for message in request.messages
            if (
                message.role is CognitiveRole.SYSTEM
                and message.content.startswith("NEURAL ATTENTION CONTEXT")
            )
        )
        assert len(neuro) == 1
        assert "domain:social" in neuro[0].content
        assert "NOT evidence" in neuro[0].content
        assert app.conversation.neuro_snapshot is app.neuro.last_snapshot
    finally:
        app.shutdown()


def test_channel_conversations_share_application_neuro_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from datetime import datetime, timezone

    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    channel = app.open_channel_conversation()
    requests.clear()
    try:
        app.neuro.observe_signal(
            NeuralSignal(
                source="ops:shared-canary",
                kind="fault",
                value=1.0,
                confidence=1.0,
                novelty=1.0,
                urgency=1.0,
                observed_at=datetime.now(timezone.utc),
                ttl_seconds=120.0,
            )
        )

        channel.respond("hello", channel="discord")

        request = requests[-1]
        neuro_text = "\n".join(
            message.content
            for message in request.messages
            if message.role is CognitiveRole.SYSTEM
            and message.content.startswith("NEURAL ATTENTION CONTEXT")
        )
        assert "fault:ops:shared-canary" in neuro_text
        assert "tool authority" in neuro_text
    finally:
        app.shutdown()


def test_neuro_emotion_refresh_uses_active_principal_relationship_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    principal = PrincipalContext(
        principal_id="person:discord:other",
        audience_id="dm:other",
        audience_kind=AudienceKind.PRIVATE,
        display_name="Other",
    )
    captured = {}

    def current_state(*, now, subject, scope):
        captured.update(now=now, subject=subject, scope=scope)
        return CurrentEmotionalState(
            as_of=now,
            subject=subject,
            tone="steady",
            active=(),
        )

    monkeypatch.setattr(
        app.conversation,
        "_emotional_journal",
        SimpleNamespace(current_state=current_state),
    )
    now = datetime.now(timezone.utc)

    snapshot = app._refresh_neuro_inputs(now=now, principal=principal)

    assert snapshot is not None
    assert captured == {
        "now": now,
        "subject": principal.principal_id,
        "scope": principal.relationship_scope,
    }


def test_neuro_failure_is_nonfatal_and_not_projected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    requests.clear()

    def fail_turn(**kwargs):
        raise RuntimeError("synthetic neuro failure")

    monkeypatch.setattr(app.neuro, "observe_turn", fail_turn)
    try:
        response = app.conversation.respond("How are you?")

        assert response.content == "Captured."
        assert app.conversation.last_neuro_error == "RuntimeError"
        request = requests[-1]
        assert not any(
            message.role is CognitiveRole.SYSTEM
            and message.content.startswith("NEURAL ATTENTION CONTEXT")
            for message in request.messages
        )
    finally:
        app.shutdown()


def test_persistent_goal_is_scoped_into_matrix_and_neuro_without_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    try:
        app.conversation.respond(
            "Track the Docker instability for me.",
            principal=local_sparks_principal(),
        )
        source = next(
            message for message in reversed(app.conversation.messages())
            if message.role.value == "user"
        )
        app.goals.create_user_goal(
            principal=local_sparks_principal(),
            title="Investigate Docker instability",
            reason="Sparks explicitly requested continued investigation.",
            base_priority=0.8,
            confidence=1.0,
            completion=GoalCompletionCondition(
                CompletionKind.EVIDENCE_TRUE,
                "Root cause and stable resolution are evidenced.",
            ),
            evidence_refs=(source.id,),
            now=datetime.now(timezone.utc),
        )
        requests.clear()
        # Exercise the generative goal-context projection itself; ordinary
        # exact goal commands are answered earlier by the deterministic host
        # resolver and correctly never need an LLM request.
        app.conversation.set_goal_command_handler(None)

        app.conversation.respond(
            "Tell me about goal Investigate Docker instability status.",
            principal=local_sparks_principal(),
        )

        system = tuple(
            message.content for message in requests[-1].messages
            if message.role is CognitiveRole.SYSTEM
        )
        goal_context = next(
            item for item in system if item.startswith("TRUSTED GOAL CONTEXT")
        )
        assert "Investigate Docker instability" in goal_context
        assert "grants no permission" in goal_context
        assert any(item.kind == "goal" for item in app.neuro.recent_signals)
    finally:
        app.shutdown()


def test_goal_projection_failure_does_not_break_conversation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    _capture_runtime(monkeypatch, app)
    app.start()
    app.conversation.set_goal_command_handler(None)
    app.conversation.set_goal_context_provider(
        lambda principal, now: (_ for _ in ()).throw(RuntimeError("synthetic"))
    )
    try:
        response = app.conversation.respond(
            "Hello", principal=local_sparks_principal(),
        )
        assert response.content == "Captured."
        assert app.conversation.last_goal_context_error is None

        response = app.conversation.respond(
            "Tell me about goal synthetic status.",
            principal=local_sparks_principal(),
        )
        assert response.content == "Captured."
        assert app.conversation.last_goal_context_error == "RuntimeError"
    finally:
        app.shutdown()


def test_deterministic_compound_interaction_still_updates_neuro(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    app.start()
    try:
        response = app.conversation.respond(
            "I hug you and kiss your cheek",
            channel="desktop",
        )

        assert "not treated any as completed" in response.content
        snapshot = app.conversation.neuro_snapshot
        assert snapshot is not None
        assert snapshot.focus is not None
        assert any(
            item.kind == "foreground"
            and item.source == "conversation:desktop"
            for item in (snapshot.focus, *snapshot.secondary)
        )
        assert app.conversation.last_neuro_error is None
    finally:
        app.shutdown()


def test_reviewed_deterministic_clarification_updates_neuro(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    _quiet_background(monkeypatch)
    monkeypatch.setenv("SOFIA_INTERACT_STAGED_OFFERS", "1")
    app = SofiaApplication(configuration(tmp_path))
    app.start()
    try:
        state_path = tmp_path / "sofia.db"
        InteractionLedger(state_path)
        VerifiedInteractionState(
            state_path,
            InteractionCatalog(("head", "left-hand")),
        )
        response = app.conversation.respond(
            "Can I hug you?",
            channel="desktop",
        )

        assert response.content == CLARIFICATION
        snapshot = app.conversation.neuro_snapshot
        assert snapshot is not None
        assert any(
            item.kind == "foreground"
            and item.source == "conversation:desktop"
            for item in (snapshot.focus, *snapshot.secondary)
        )
        assert app.conversation.last_neuro_error is None
    finally:
        app.shutdown()
