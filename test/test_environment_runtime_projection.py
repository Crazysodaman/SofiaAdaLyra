from datetime import timedelta
from pathlib import Path
import re

from sofia.application import SofiaApplication
from sofia.cognition.llm_engine import LLMCognitiveEngine
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.provider import LLMProvider
from sofia.config.model import ProviderConfiguration, SofiaConfiguration
from sofia.environment.config import (
    ConfiguredLocation,
    EnvironmentConfiguration,
)
from sofia.environment.model import WeatherObservation
from sofia.environment.provider import EnvironmentProviderObservation


PROJECT_ROOT = Path(__file__).parent.parent
CONSTITUTION_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.md"
)
HASH_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "constitution" / "constitution.sha256"
)
IDENTITY_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "identity" / "identity.json"
)
AVATAR_PATH = (
    PROJECT_ROOT / "src" / "sofia" / "embodiment" / "avatar.json"
)


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
        provider=ProviderConfiguration(
            provider="test",
            model="test",
        ),
        filesystem_root=PROJECT_ROOT,
        environment=EnvironmentConfiguration(
            location=ConfiguredLocation(
                label="Configured area",
                timezone="America/Chicago",
                latitude=32.5,
                longitude=-97.1,
            )
        ),
    )


def test_runtime_injects_environment_into_same_cognitive_request(tmp_path):
    config = configuration(tmp_path)
    app = SofiaApplication(config)
    app.start()

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
                    content=(
                        "Explain how the current season and daylight relate "
                        "to your configured location."
                    ),
                ),
            ),
        )
    )

    assert len(provider.requests) == 1
    system = provider.requests[0].messages[0].content
    assert "TRUSTED ENVIRONMENT SNAPSHOT" in system
    assert "TRUSTED RUNTIME CLOCK" in system
    assert "Configured user location: Configured area" in system
    assert "Current physical location evidence: unavailable." in system
    assert "Derived season:" in system
    assert re.search(r"(?<![0-9.])32\.5(?![0-9])", system) is None
    assert re.search(r"(?<![0-9.])-97\.1(?![0-9])", system) is None
    app.shutdown()


def test_runtime_answers_environment_context_sources_without_llm(tmp_path):
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
                    content="Explain your current environment context sources.",
                ),
            ),
        )
    )

    assert "Environment context sources:" in response.content
    assert "Configured area" in response.content
    assert "config.environment" in response.content
    assert "Current physical location evidence: unavailable." in response.content
    assert re.search(r"(?<![0-9.])32\.5(?![0-9])", response.content) is None
    assert re.search(r"(?<![0-9.])-97\.1(?![0-9])", response.content) is None
    assert provider.requests == []
    app.shutdown()


def test_runtime_answers_direct_location_without_asking_llm(tmp_path):
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
                    content="Where am I?",
                ),
            ),
        )
    )

    assert "configured location is Configured area" in response.content
    assert "won't claim you're there right now" in response.content
    assert provider.requests == []
    app.shutdown()


def test_runtime_current_weather_keeps_facts_and_adds_sofia_voice(tmp_path):
    config = configuration(tmp_path)
    app = SofiaApplication(config)

    class CurrentWeatherProvider:
        name = "test-weather"

        def observe(self, *, now):
            return EnvironmentProviderObservation(
                weather=WeatherObservation(
                    condition="Clear",
                    observed_at=now - timedelta(minutes=1),
                    expires_at=now + timedelta(minutes=10),
                    source_id="test.weather",
                    location_label="Configured area",
                    temperature_c=28.8888889,
                    feels_like_c=27.7777778,
                    humidity_percent=31.0,
                    wind_kph=12.8748,
                )
            )

    app.runtime.environment_service._providers = (CurrentWeatherProvider(),)
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
                    content="What's the weather?",
                ),
            ),
        )
    )

    assert response.content.startswith(
        "Current weather for Configured area: Clear, 84 °F, "
        "feels like 82 °F, humidity 31%, wind 8 mph."
    )
    assert "Observed at " in response.content
    assert " from test.weather." in response.content
    assert response.content.endswith("Rather cooperative weather, for once.")
    assert provider.requests == []
    app.shutdown()


def test_runtime_answers_direct_weather_unknown_without_inventing_it(tmp_path):
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
                    content="What's the weather?",
                ),
            ),
        )
    )

    assert response.content == (
        "I don't have current weather evidence. "
        "No configured weather provider produced evidence for the effective location."
    )
    assert provider.requests == []
    app.shutdown()


def test_runtime_environment_service_is_shared_and_invalidated_across_lifecycle(
    tmp_path,
):
    app = SofiaApplication(configuration(tmp_path))
    service = app.runtime.environment_service
    app.start()
    assert app.runtime.environment_service is service
    app.shutdown()
    assert app.runtime.environment_service is service

def test_runtime_omits_detailed_environment_from_unrelated_llm_turn(tmp_path):
    config = configuration(tmp_path)
    app = SofiaApplication(config)
    app.start()

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
                    content="Explain a database transaction.",
                ),
            ),
        )
    )

    system = provider.requests[0].messages[0].content
    assert "TRUSTED RUNTIME CLOCK" in system
    assert "Detailed location/weather/indoor environment data is intentionally omitted" in system
    assert "Configured area" not in system
    app.shutdown()

def test_unrelated_runtime_turn_does_not_refresh_environment_provider(tmp_path):
    config = configuration(tmp_path)
    app = SofiaApplication(config)

    class CountingProvider:
        name = "counting"
        def __init__(self):
            self.calls = 0
        def observe(self, *, now):
            from sofia.environment.provider import EnvironmentProviderObservation
            self.calls += 1
            return EnvironmentProviderObservation()

    counting = CountingProvider()
    app.runtime.environment_service._providers = (counting,)
    app.start()
    assert counting.calls == 1

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
                    content="Explain a database transaction.",
                ),
            ),
        )
    )
    assert counting.calls == 1
    app.shutdown()

def test_runtime_answers_outfit_time_and_weather_in_one_turn_without_llm(tmp_path):
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
                    content=(
                        "what are u wearing, what time is it, "
                        "whats the weather?"
                    ),
                ),
            ),
        )
    )

    assert "I'm in my" in response.content
    assert "The pieces are:" in response.content
    assert "current time" in response.content.casefold()
    assert "current weather evidence" in response.content.casefold()
    assert provider.requests == []
    app.shutdown()


def test_runtime_preserves_partial_deterministic_multi_question_answers(tmp_path):
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
                    content=(
                        "what day is it, explain a database transaction?"
                    ),
                ),
            ),
        )
    )

    assert response.content == "Captured."
    assert len(provider.requests) == 1
    system = "\n".join(
        message.content
        for message in provider.requests[0].messages
        if message.role is CognitiveRole.SYSTEM
    )
    assert "TRUSTED DETERMINISTIC SUBQUESTION ANSWERS" in system
    assert "Clause: what day is it" in system
    assert "Authoritative answer:" in system
    assert "current date" in system.casefold()
    app.shutdown()
