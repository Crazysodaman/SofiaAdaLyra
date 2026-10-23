"""End-to-end tests for canonical autobiography wiring through the turn request.

The full production bootstrap must wire the reviewed personal timeline into
the conversation service, and lifecycle-gated personal history must reach the
model request only when the authoritative v2 turn plan admits the memory
domain.
"""
from pathlib import Path
from datetime import datetime, timezone

import pytest

from sofia.platform.application import SofiaApplication
from sofia.platform.application.memory_significance import MemorySignificanceService
from sofia.core.cognition.model import CognitiveResponse, CognitiveRole
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.life.model import ExperienceRecord
from sofia.life.store import LifeStore
from sofia.core.memory.autobiography import AutobiographyTimeline
from sofia.core.social.principals import local_sparks_principal
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia" / "core" / "constitution"
    / "constitution.md"
)
HASH_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia" / "core" / "constitution"
    / "constitution.sha256"
)
IDENTITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia" / "core" / "identity"
    / "identity.json"
)
AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia" / "core" / "embodiment"
    / "avatar.json"
)


def configuration(tmp_path: Path) -> SofiaConfiguration:
    bootstrap_canonical_sqlite(tmp_path / "sofia.db")
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


def _capture_runtime(monkeypatch: pytest.MonkeyPatch, app: SofiaApplication):
    requests = []

    def respond(request, filesystem_results=(), **kwargs):
        requests.append(request)
        return CognitiveResponse(content="Captured.")

    monkeypatch.setattr(app.runtime, "respond", respond)
    return requests


def _quiet_background(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOFIA_IDLE_REFLECTIONS", "0")
    monkeypatch.setenv("SOFIA_HABIT_LEARNING", "0")


def test_bootstrap_wires_significance_and_autobiography(tmp_path: Path) -> None:
    app = SofiaApplication(configuration(tmp_path))
    try:
        assert isinstance(app.memory_significance, MemorySignificanceService)
        assert isinstance(app.autobiography, AutobiographyTimeline)
        assert app.conversation._autobiography_provider is not None
        app.start()
    finally:
        app.shutdown()


def test_autobiography_context_reaches_the_model_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    try:
        now = datetime.now(timezone.utc)
        store = LifeStore(app.runtime.configuration.state_path)
        store.record_experience(ExperienceRecord(
            "experience:sparks-radio", None, "artifact_evaluated",
            "One workshop evening produced the tuned radio.",
            ("evidence:radio-1",), "local:text", False, now, now, {},
        ))
        app.conversation.respond(
            "Your earlier reflections about the workshop were interesting.",
            principal=local_sparks_principal(),
        )
        assert requests, "a generative turn must reach the model request"
        request = requests[-1]
        timeline = tuple(
            message.content
            for message in request.messages
            if (
                message.role is CognitiveRole.SYSTEM
                and message.content.startswith("CANONICAL PERSONAL TIMELINE")
            )
        )
        assert len(timeline) == 1
        assert "[experience]" in timeline[0]
        assert "One workshop evening produced the tuned radio." in timeline[0]
    finally:
        app.shutdown()
