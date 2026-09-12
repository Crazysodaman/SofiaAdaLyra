import pytest

from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
)
from sofia.cognition.provider import LLMProviderError
from sofia.cognition.providers.test_provider import TestLLMProvider
from sofia.config.model import ProviderConfiguration
from sofia.cognition.providers.factory import create_llm_provider


def test_test_llm_provider_is_configured_with_a_response():
    response = CognitiveResponse(
        content="Test provider response.",
    )

    provider = TestLLMProvider(
        response=response,
    )

    result = provider.respond(
        CognitiveRequest(messages=()),
    )

    assert result is response


def test_test_llm_provider_receives_exact_request():
    response = CognitiveResponse(
        content="Test provider response.",
    )

    provider = TestLLMProvider(
        response=response,
    )

    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        ),
    )

    provider.respond(request)

    assert provider.received_request is request


def test_test_llm_provider_can_raise_configured_error():
    error = LLMProviderError(
        "Configured provider failure.",
    )

    provider = TestLLMProvider(
        error=error,
    )

    with pytest.raises(LLMProviderError) as exc_info:
        provider.respond(
            CognitiveRequest(messages=()),
        )

    assert exc_info.value is error


def test_test_llm_provider_rejects_response_and_error_together():
    response = CognitiveResponse(
        content="Test response.",
    )

    error = LLMProviderError(
        "Test error.",
    )

    with pytest.raises(ValueError):
        TestLLMProvider(
            response=response,
            error=error,
        )


def test_test_llm_provider_requires_a_response_when_no_error_is_configured():
    provider = TestLLMProvider()

    with pytest.raises(
        LLMProviderError,
        match="TestLLMProvider has no configured response.",
    ):
        provider.respond(
            CognitiveRequest(messages=()),
        )


def test_llm_provider_factory_creates_test_provider():
    configuration = ProviderConfiguration(
        provider="test-llm",
        model="test-model",
    )

    provider = create_llm_provider(
        configuration,
    )

    assert isinstance(provider, TestLLMProvider)


def test_llm_provider_factory_rejects_unknown_provider():
    configuration = ProviderConfiguration(
        provider="unknown-llm",
        model="test-model",
    )

    with pytest.raises(
        ValueError,
        match="Unknown LLM provider: unknown-llm",
    ):
        create_llm_provider(configuration)