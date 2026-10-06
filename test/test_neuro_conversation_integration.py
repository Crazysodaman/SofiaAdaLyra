from pathlib import Path

import pytest

from sofia.application import SofiaApplication
from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.neuro import NeuralSignal


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
