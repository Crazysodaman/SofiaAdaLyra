import pytest

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
from sofia.cognition.rules import RuleEngine
from sofia.cognition.system import CognitiveSystem


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
        CognitiveRequest(messages=()),
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
        CognitiveRequest(messages=()),
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
            CognitiveRequest(messages=()),
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
            CognitiveRequest(messages=()),
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

    engine = TestCognitiveEngine()

    assert isinstance(engine, CognitiveEngine)

def test_test_cognitive_engine_is_a_cognitive_engine():
    from sofia.cognition.test_engine import TestCognitiveEngine
    from sofia.config.model import ProviderConfiguration

    provider = ProviderConfiguration(
        provider="test",
        model="test-model",
    )

    engine = TestCognitiveEngine(
        configuration=provider,
    )

    assert isinstance(engine, CognitiveEngine)