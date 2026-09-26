from __future__ import annotations

from pathlib import Path

from sofia.application import SofiaApplication
from sofia.avatar.presentation import (
    AppearanceState,
    AudienceScope,
    PresentationAuthority,
    PrivatePresentationGrant,
)
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.provider import LLMProvider
from sofia.config.model import ProviderConfiguration, SofiaConfiguration


PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_PATH = PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.md"
HASH_PATH = PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.sha256"
IDENTITY_PATH = PROJECT_ROOT / "src" / "sofia" / "identity" / "identity.json"
AVATAR_PATH = PROJECT_ROOT / "src" / "sofia" / "data" / "avatar.json"


class CapturingProvider(LLMProvider):
    def __init__(self) -> None:
        self.requests: list[CognitiveRequest] = []

    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        self.requests.append(request)
        return CognitiveResponse(content="Captured.")


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


def private_grant() -> PrivatePresentationGrant:
    return PrivatePresentationGrant(True, True, True, True, False)


def test_application_bootstraps_headless_avatar_and_persists_it(tmp_path):
    config = configuration(tmp_path)
    app = SofiaApplication(config)
    app.start()

    authority = app.runtime.avatar_presentation
    assert isinstance(authority, PresentationAuthority)
    assert authority.current.outfit_id == "engineer.signature"
    assert (tmp_path / "avatar-presentation.json").is_file()

    authority.propose_outfit(
        operation_id="op.lounge",
        expected_revision=authority.current.revision,
        outfit_id="lounge.relaxed",
        reason="late-night daily choice",
        daily=True,
    )
    authority.commit_text(operation_id="op.lounge", renderer_unavailable=True)
    app.shutdown()

    resumed = SofiaApplication(config)
    resumed.start()
    assert resumed.runtime.avatar_presentation is not None
    assert resumed.runtime.avatar_presentation.last_daily.outfit_id == "lounge.relaxed"
    resumed.shutdown()


def test_private_nude_state_restores_but_public_cognition_gets_daily_fallback(tmp_path):
    config = configuration(tmp_path)
    app = SofiaApplication(config)
    app.start()
    authority = app.runtime.avatar_presentation
    assert authority is not None

    authority.propose_outfit(
        operation_id="op.lounge",
        expected_revision=authority.current.revision,
        outfit_id="lounge.relaxed",
        reason="daily lounge state",
        daily=True,
    )
    authority.commit_text(operation_id="op.lounge", renderer_unavailable=True)

    grant = private_grant()
    authority.propose_nude(
        operation_id="op.nude",
        expected_revision=authority.current.revision,
        reason="private presentation",
        grant=grant,
    )
    authority.commit_text(
        operation_id="op.nude",
        renderer_unavailable=True,
        grant=grant,
    )
    assert authority.projection(AudienceScope.PRIVATE, grant=grant).attire.value == "nude"
    assert app.runtime.avatar_presentation_projection.outfit_id == "lounge.relaxed"

    provider = CapturingProvider()
    app.runtime.cognitive_system.engine = LLMCognitiveEngine(
        configuration=config.provider,
        provider=provider,
    )
    app.runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Explain how your presentation state reaches cognition.",
                ),
            ),
        )
    )
    system = provider.requests[-1].messages[0].content
    assert "CURRENT AVATAR PRESENTATION" in system
    assert '"outfit_id": "lounge.relaxed"' in system
    assert '"attire": "clothed"' in system
    assert '"attire": "nude"' not in system
    app.shutdown()


def test_current_presentation_overrides_static_clothing_as_current_wear(tmp_path):
    config = configuration(tmp_path)
    app = SofiaApplication(config)
    app.start()
    authority = app.runtime.avatar_presentation
    assert authority is not None
    authority.propose_outfit(
        operation_id="op.lounge",
        expected_revision=authority.current.revision,
        outfit_id="lounge.relaxed",
        reason="late-night conversation",
        daily=True,
    )
    authority.commit_text(operation_id="op.lounge", renderer_unavailable=True)

    provider = CapturingProvider()
    app.runtime.cognitive_system.engine = LLMCognitiveEngine(
        configuration=config.provider,
        provider=provider,
    )
    app.runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Discuss your current presentation grounding.",
                ),
            ),
        )
    )
    system = provider.requests[-1].messages[0].content
    assert "CANONICAL CLOTHING" in system
    assert "CURRENT AVATAR PRESENTATION" in system
    assert "overrides static canonical clothing design as a CURRENT-WEAR fact" in system
    assert '"outfit_id": "lounge.relaxed"' in system
    app.shutdown()


def test_direct_current_self_fact_bypasses_provider_and_uses_typed_state(tmp_path):
    config = configuration(tmp_path)
    app = SofiaApplication(config)
    app.start()
    provider = CapturingProvider()
    app.runtime.cognitive_system.engine = LLMCognitiveEngine(
        configuration=config.provider,
        provider=provider,
    )

    response = app.runtime.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="What color is your hair?",
                ),
            ),
        )
    )

    assert response.content == "My hair is deep crimson, worn long layered."
    assert provider.requests == []
    app.shutdown()
