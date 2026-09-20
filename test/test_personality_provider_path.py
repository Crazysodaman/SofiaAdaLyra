"""G3: deterministic assembler-to-LLM-provider evidence, NOT LLM fidelity."""
from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.cognition.provider import LLMProvider
from sofia.config.model import ProviderConfiguration
from sofia.personality.model import PersonalityProfile


class RecordingProvider(LLMProvider):
    def __init__(self, content="Provider says hello."):
        self.requests = []
        self.content = content

    def respond(self, request):
        self.requests.append(request)
        return CognitiveResponse(content=self.content)


def test_saved_personality_crosses_engine_to_provider_unchanged():
    profile = PersonalityProfile(
        name="Sofía", traits=("curious", "precise"),
        communication_style="Answer concisely.",
        embodiment_guidance="Optional representational fox expression.",
    )
    user = CognitiveMessage(role=CognitiveRole.USER, content="Who are you?")
    source = CognitiveRequest(messages=(user,))
    assembled = CognitiveContextAssembler().assemble(
        CognitiveContext(request=source, personality=profile)
    )
    provider = RecordingProvider()
    engine = LLMCognitiveEngine(
        ProviderConfiguration(provider="test-llm", model="recording"), provider
    )
    result = engine.respond(assembled)
    assert len(provider.requests) == 1
    assert provider.requests[0] is assembled
    assert provider.requests[0].messages[-1] is user
    system = provider.requests[0].messages[0].content
    assert system.count("PERSONALITY EXPRESSION BOUNDARY") == 1
    assert "Traits: curious, precise" in system
    assert "Communication style: Answer concisely." in system
    assert "Embodiment guidance: Optional representational fox expression." in system
    assert result.content == "Provider says hello."


def test_provider_response_is_observed_not_falsely_certified_as_personality():
    profile = PersonalityProfile(name="Sofía", traits=("playful",))
    assembled = CognitiveContextAssembler().assemble(CognitiveContext(
        request=CognitiveRequest(messages=(CognitiveMessage(
            role=CognitiveRole.USER, content="Who are you?"),)),
        personality=profile,
    ))
    provider = RecordingProvider("I am a generic AI assistant.")
    engine = LLMCognitiveEngine(
        ProviderConfiguration(provider="test-llm", model="recording"), provider
    )
    assert engine.respond(assembled).content == "I am a generic AI assistant."
    # This confirms prompt delivery only; model personality fidelity is unverified.
