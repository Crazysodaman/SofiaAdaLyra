"""End-to-end tests for canonical conviction wiring through the turn request.

The full production bootstrap must wire the owner-gated BeliefsService into
the conversation service, and held positions must reach the model request
only when the authoritative v2 turn plan admits the values domain.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pytest

from sofia.platform.application import SofiaApplication
from sofia.platform.application.beliefs import BeliefsService
from sofia.cognition.model import CognitiveResponse, CognitiveRole
from sofia.platform.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.beliefs.model import BeliefHolder, BeliefStance
from sofia.social.principals import local_sparks_principal
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite

PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.md"
)
HASH_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "constitution"
    / "constitution.sha256"
)
IDENTITY_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "identity"
    / "identity.json"
)
AVATAR_PATH = (
    PROJECT_ROOT
    / "src"
    / "sofia"
    / "embodiment"
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


def test_bootstrap_wires_the_beliefs_service(tmp_path: Path) -> None:
    app = SofiaApplication(configuration(tmp_path))
    try:
        assert isinstance(app.beliefs, BeliefsService)
        assert app.conversation._conviction_provider is not None
        app.start()
        prune_position = app.beliefs.record_owner_position(
            principal=local_sparks_principal(),
            statement="Prefer Rust for new systems work.",
            topic="rust over python",
            stance=BeliefStance.SUPPORT,
            confidence=0.8,
            reason="Documented migration outcomes.",
            evidence_refs=("memory:session-2026-01-02",),
            expected_revision=None,
            now=datetime.now(timezone.utc),
        )
        current = app.beliefs.store.current(
            holder=BeliefHolder.OWNER,
            topic="rust over python",
            audience_id=local_sparks_principal().audience_id,
        )
        assert current == prune_position
        assert current.revision == 1
    finally:
        app.shutdown()


def test_beliefs_service_is_owner_gated(tmp_path: Path) -> None:
    app = SofiaApplication(configuration(tmp_path))
    app.start()
    try:

        class NotAPrincipal:
            principal_id = "person:sparks"
            audience_id = "local:text"

        with pytest.raises(TypeError):
            app.beliefs.record_owner_position(
                principal=NotAPrincipal(),  # type: ignore[arg-type]
                statement="Prefer Rust for new systems work.",
                topic="rust over python",
                stance=BeliefStance.SUPPORT,
                confidence=0.5,
                reason="Documented migration outcomes.",
                evidence_refs=("memory:session-2026-01-02",),
                expected_revision=None,
                now=datetime.now(timezone.utc),
            )
    finally:
        app.shutdown()


def test_conviction_context_reaches_the_model_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    try:
        app.beliefs.record_owner_position(
            principal=local_sparks_principal(),
            statement="Prefer Rust for new systems work.",
            topic="rust over python",
            stance=BeliefStance.SUPPORT,
            confidence=0.8,
            reason="Documented migration outcomes.",
            evidence_refs=("memory:session-2026-01-02",),
            expected_revision=None,
            now=datetime.now(timezone.utc),
        )
        app.conversation.respond(
            "What do you believe about picking rust for systems work?",
            principal=local_sparks_principal(),
        )
        assert requests, "a generative turn must reach the model request"
        request = requests[-1]
        conviction = tuple(
            message.content
            for message in request.messages
            if (
                message.role is CognitiveRole.SYSTEM
                and message.content.startswith("CANONICAL HELD POSITIONS")
            )
        )
        assert len(conviction) == 1
        assert "[OWNER] rust over python" in conviction[0]
        assert "Prefer Rust for new systems work." in conviction[0]
        assert "attributed to the owner" in conviction[0]
        assert conviction[0].splitlines()[0] == (
            "CANONICAL HELD POSITIONS (authored records only)"
        )
    finally:
        app.shutdown()


def test_withdrawn_positions_do_not_reach_the_model_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_background(monkeypatch)
    app = SofiaApplication(configuration(tmp_path))
    requests = _capture_runtime(monkeypatch, app)
    app.start()
    try:
        origin = app.beliefs.record_owner_position(
            principal=local_sparks_principal(),
            statement="Prefer Rust for new systems work.",
            topic="rust over python",
            stance=BeliefStance.SUPPORT,
            confidence=0.8,
            reason="Documented migration outcomes.",
            evidence_refs=("memory:session-2026-01-02",),
            expected_revision=None,
            now=datetime.now(timezone.utc),
        )
        app.beliefs.withdraw(
            principal=local_sparks_principal(),
            topic=origin.topic,
            reason="The owner asked to drop the claim.",
            evidence_refs=("conversation:turn-99",),
            expected_revision=origin.revision,
            now=datetime.now(timezone.utc) + timedelta(days=1),
        )
        app.conversation.respond(
            "What do you believe about picking rust for systems work?",
            principal=local_sparks_principal(),
        )
        assert requests, "the turn itself must still reach the model request"
        request = requests[-1]
        assert not any(
            message.role is CognitiveRole.SYSTEM
            and message.content.startswith("CANONICAL HELD POSITIONS")
            for message in request.messages
        )
    finally:
        app.shutdown()
