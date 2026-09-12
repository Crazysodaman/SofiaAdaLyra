import pytest
from sofia.authority.model import Authority
from sofia.cognition.context import CognitiveContext
from sofia.cognition.operation import CognitiveOperation
from sofia.cognition.engine import (
    CognitiveEngine,
    CognitiveEngineError,
)
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.provider import (
    LLMProvider,
    LLMProviderError,
)
from sofia.cognition.rules import RuleEngine
from sofia.cognition.system import CognitiveSystem
from sofia.config.model import ProviderConfiguration


class RecordingLLMProvider(LLMProvider):
    """
    Deterministic provider used to verify the provider boundary.
    """

    def __init__(
        self,
        response: CognitiveResponse,
    ):
        self.received_request = None
        self.response = response

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        self.received_request = request
        return self.response


class FailingLLMProvider(LLMProvider):
    """
    Deterministic provider used to verify provider failure handling.
    """

    def __init__(
        self,
        error: LLMProviderError,
    ):
        self.error = error

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        raise self.error


def test_cognitive_system_does_not_use_fallback_when_primary_succeeds():
    class PrimaryEngine(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            return CognitiveResponse(
                content="Primary response.",
            )

    class FallbackEngine(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            raise AssertionError(
                "Fallback engine should not have been called."
            )

    system = CognitiveSystem(
        engine=PrimaryEngine(),
        fallback_engine=FallbackEngine(),
    )

    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(messages=()),
            ),
            authority=Authority(),
        ),
    )

    assert response.content == "Primary response."


def test_cognitive_system_uses_fallback_after_primary_failure():
    primary_error = CognitiveEngineError(
        "Primary engine failed."
    )

    class PrimaryEngine(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            raise primary_error

    class FallbackEngine(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            return CognitiveResponse(
                content="Fallback response.",
            )

    system = CognitiveSystem(
        engine=PrimaryEngine(),
        fallback_engine=FallbackEngine(),
    )

    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(messages=()),
            ),
            authority=Authority(),
        ),
    )

    assert response.content == "Fallback response."


def test_cognitive_system_propagates_primary_failure_without_fallback():
    primary_error = CognitiveEngineError(
        "Primary engine failed."
    )

    class PrimaryEngine(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            raise primary_error

    system = CognitiveSystem(
        engine=PrimaryEngine(),
    )

    with pytest.raises(
        CognitiveEngineError
    ) as exc_info:
        system.respond(
            CognitiveOperation(
                context=CognitiveContext(
                    request=CognitiveRequest(messages=()),
                ),
                authority=Authority(),
            ),
        )

    assert exc_info.value is primary_error


def test_cognitive_system_raises_fallback_failure_with_primary_failure_as_cause():
    primary_error = CognitiveEngineError(
        "Primary engine failed."
    )

    fallback_error = CognitiveEngineError(
        "Fallback engine failed."
    )

    class PrimaryEngine(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            raise primary_error

    class FallbackEngine(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            raise fallback_error

    system = CognitiveSystem(
        engine=PrimaryEngine(),
        fallback_engine=FallbackEngine(),
    )

    with pytest.raises(
        CognitiveEngineError
    ) as exc_info:
        system.respond(
            CognitiveOperation(
                context=CognitiveContext(
                    request=CognitiveRequest(messages=()),
                ),
                authority=Authority(),
            ),
        )

    assert exc_info.value is fallback_error
    assert exc_info.value.__cause__ is primary_error


def test_cognitive_request_accepts_ordered_messages():
    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="You are Sofía.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
        ),
    )

    assert request.messages[0].role is CognitiveRole.SYSTEM
    assert request.messages[0].content == "You are Sofía."
    assert request.messages[1].role is CognitiveRole.USER
    assert request.messages[1].content == "Hello."


def test_cognitive_request_is_immutable():
    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
        ),
    )

    with pytest.raises(AttributeError):
        request.messages = ()


def test_cognitive_message_is_immutable():
    message = CognitiveMessage(
        role=CognitiveRole.USER,
        content="Hello.",
    )

    with pytest.raises(AttributeError):
        message.content = "Changed."


def test_cognitive_request_accepts_empty_messages():
    request = CognitiveRequest(
        messages=(),
    )

    assert request.messages == ()


def test_cognitive_role_defines_system_user_and_assistant():
    assert CognitiveRole.SYSTEM.value == "system"
    assert CognitiveRole.USER.value == "user"
    assert CognitiveRole.ASSISTANT.value == "assistant"


def test_cognitive_message_accepts_cognitive_role():
    message = CognitiveMessage(
        role=CognitiveRole.USER,
        content="Hello.",
    )

    assert message.role is CognitiveRole.USER


def test_cognitive_message_rejects_invalid_role():
    with pytest.raises(ValueError):
        CognitiveMessage(
            role="invalid",
            content="Hello.",
        )


def test_cognitive_engine_can_be_implemented_by_an_adapter():
    class TestAdapter(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            return CognitiveResponse(
                content="Adapter response.",
            )

    adapter = TestAdapter()

    response = adapter.respond(
        CognitiveRequest(
            messages=(
                CognitiveMessage(
                    role=CognitiveRole.USER,
                    content="Hello.",
                ),
            ),
        ),
    )

    assert response.content == "Adapter response."


def test_cognitive_engine_adapter_receives_cognitive_request():
    received_requests = []

    class TestAdapter(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            received_requests.append(request)

            return CognitiveResponse(
                content="Received.",
            )

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="You are Sofía.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
        ),
    )

    adapter = TestAdapter()

    adapter.respond(request)

    assert received_requests == [request]


def test_cognitive_engine_adapter_can_translate_request_without_changing_it():
    original_request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="You are Sofía.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello.",
            ),
        ),
    )

    received_request = None

    class TestAdapter(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            nonlocal received_request
            received_request = request

            return CognitiveResponse(
                content="Translated response.",
            )

    adapter = TestAdapter()

    response = adapter.respond(original_request)

    assert received_request is original_request
    assert response.content == "Translated response."


def test_cognitive_engine_adapter_failure_uses_cognitive_engine_error():
    class FailingAdapter(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            raise CognitiveEngineError(
                "Provider operation failed."
            )

    adapter = FailingAdapter()

    with pytest.raises(
        CognitiveEngineError,
        match="Provider operation failed.",
    ):
        adapter.respond(
            CognitiveRequest(
                messages=(),
            ),
        )


def test_cognitive_engine_adapter_can_be_configured_with_provider():
    class TestAdapter(CognitiveEngine):
        def __init__(self, provider: str, model: str):
            self.provider = provider
            self.model = model

        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            return CognitiveResponse(
                content=f"{self.provider}:{self.model}",
            )

    adapter = TestAdapter(
        provider="test",
        model="test-model",
    )

    response = adapter.respond(
        CognitiveRequest(messages=()),
    )

    assert response.content == "test:test-model"


def test_cognitive_engine_adapter_is_provider_neutral():
    class TestAdapter(CognitiveEngine):
        def respond(
            self,
            request: CognitiveRequest,
        ) -> CognitiveResponse:
            return CognitiveResponse(
                content="Provider-neutral response.",
            )

    adapter = TestAdapter()

    assert isinstance(adapter, CognitiveEngine)


def test_test_cognitive_engine_is_a_cognitive_engine():
    from sofia.cognition.test_engine import TestCognitiveEngine

    configuration = ProviderConfiguration(
        provider="test",
        model="test-model",
    )

    engine = TestCognitiveEngine(
        configuration=configuration,
    )

    assert isinstance(engine, CognitiveEngine)


def test_llm_cognitive_engine_is_a_cognitive_engine():
    from sofia.cognition.llm_engine import LLMCognitiveEngine

    configuration = ProviderConfiguration(
        provider="test-llm",
        model="test-model",
    )

    provider = RecordingLLMProvider(
        response=CognitiveResponse(
            content="Test response.",
        )
    )

    engine = LLMCognitiveEngine(
        configuration=configuration,
        provider=provider,
    )

    assert isinstance(engine, CognitiveEngine)


def test_llm_cognitive_engine_preserves_provider_configuration():
    from sofia.cognition.llm_engine import LLMCognitiveEngine

    configuration = ProviderConfiguration(
        provider="test-llm",
        model="test-model",
    )

    provider = RecordingLLMProvider(
        response=CognitiveResponse(
            content="Test response.",
        )
    )

    engine = LLMCognitiveEngine(
        configuration=configuration,
        provider=provider,
    )

    assert engine.configuration is configuration


def test_llm_provider_is_an_abstract_provider():
    with pytest.raises(TypeError):
        LLMProvider()


def test_llm_provider_error_is_an_exception():
    error = LLMProviderError(
        "Provider failed."
    )

    assert isinstance(error, Exception)


def test_llm_cognitive_engine_requires_an_llm_provider():
    from sofia.cognition.llm_engine import LLMCognitiveEngine

    configuration = ProviderConfiguration(
        provider="test-llm",
        model="test-model",
    )

    with pytest.raises(TypeError):
        LLMCognitiveEngine(
            configuration=configuration,
            provider=object(),
        )


def test_llm_cognitive_engine_passes_exact_request_to_provider():
    from sofia.cognition.llm_engine import LLMCognitiveEngine

    configuration = ProviderConfiguration(
        provider="test-llm",
        model="test-model",
    )

    response = CognitiveResponse(
        content="Provider response.",
    )

    provider = RecordingLLMProvider(
        response=response,
    )

    engine = LLMCognitiveEngine(
        configuration=configuration,
        provider=provider,
    )

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.SYSTEM,
                content="System message.",
            ),
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        )
    )

    engine.respond(request)

    assert provider.received_request is request


def test_llm_cognitive_engine_returns_provider_response():
    from sofia.cognition.llm_engine import LLMCognitiveEngine

    configuration = ProviderConfiguration(
        provider="test-llm",
        model="test-model",
    )

    response = CognitiveResponse(
        content="Provider response.",
    )

    provider = RecordingLLMProvider(
        response=response,
    )

    engine = LLMCognitiveEngine(
        configuration=configuration,
        provider=provider,
    )

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        )
    )

    result = engine.respond(request)

    assert result is response


def test_llm_cognitive_engine_translates_provider_failure():
    from sofia.cognition.llm_engine import LLMCognitiveEngine

    configuration = ProviderConfiguration(
        provider="test-llm",
        model="test-model",
    )

    provider_error = LLMProviderError(
        "Provider is unavailable."
    )

    provider = FailingLLMProvider(
        error=provider_error,
    )

    engine = LLMCognitiveEngine(
        configuration=configuration,
        provider=provider,
    )

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        )
    )

    with pytest.raises(
        CognitiveEngineError,
        match="LLM provider failed to process the cognitive request.",
    ) as exc_info:
        engine.respond(request)

    assert exc_info.value.__cause__ is provider_error


def test_llm_cognitive_engine_does_not_swallow_provider_failure():
    from sofia.cognition.llm_engine import LLMCognitiveEngine

    configuration = ProviderConfiguration(
        provider="test-llm",
        model="test-model",
    )

    provider_error = LLMProviderError(
        "Provider is unavailable."
    )

    provider = FailingLLMProvider(
        error=provider_error,
    )

    engine = LLMCognitiveEngine(
        configuration=configuration,
        provider=provider,
    )

    with pytest.raises(CognitiveEngineError):
        engine.respond(
            CognitiveRequest(messages=()),
        )


def test_cognitive_system_uses_fallback_after_llm_provider_failure():
    from sofia.cognition.llm_engine import LLMCognitiveEngine

    configuration = ProviderConfiguration(
        provider="test-llm",
        model="test-model",
    )

    provider = FailingLLMProvider(
        error=LLMProviderError(
            "Provider is unavailable."
        ),
    )

    primary_engine = LLMCognitiveEngine(
        configuration=configuration,
        provider=provider,
    )

    fallback_engine = RuleEngine()

    system = CognitiveSystem(
        engine=primary_engine,
        fallback_engine=fallback_engine,
    )

    response = system.respond(
        CognitiveOperation(
            context=CognitiveContext(
                request=CognitiveRequest(
                    messages=(
                        CognitiveMessage(
                            role=CognitiveRole.USER,
                            content="Hello, Sofía.",
                        ),
                    ),
                ),
            ),
            authority=Authority(),
        ),
    )

    assert response.content == "Hello, Sparks."