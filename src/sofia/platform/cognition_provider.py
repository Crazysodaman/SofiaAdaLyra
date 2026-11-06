"""Platform-owned construction of approved cognitive providers."""

from sofia.sdk.cognition_engine import LLMProvider
from sofia.platform.core_worker.engines import TestLLMProvider
from sofia.platform.config.model import ProviderConfiguration


def create_llm_provider(
    configuration: ProviderConfiguration,
    *,
    keep_alive: str | None = None,
    endpoint: str | None = None,
) -> LLMProvider:
    """
    Construct the configured LLM provider adapter.
    """

    if configuration.provider == "test-llm":
        return TestLLMProvider()

    if configuration.provider == "ollama":
        from sofia.modules.inference.ollama_provider import OllamaProvider

        return OllamaProvider(
            configuration=configuration,
            keep_alive=keep_alive,
            endpoint=endpoint,
        )

    raise ValueError(
        f"Unknown LLM provider: {configuration.provider}"
    )


def create_generic_llm_provider(
    configuration: ProviderConfiguration,
    *,
    keep_alive: str | None = None,
    endpoint: str | None = None,
) -> LLMProvider:
    """Build a neutral adapter without personal policy or state authority."""
    if configuration.provider == "test-llm":
        return TestLLMProvider()
    if configuration.provider == "ollama":
        from sofia.platform.core_worker.ollama_transport import GenericOllamaProvider

        return GenericOllamaProvider(
            configuration=configuration, keep_alive=keep_alive, endpoint=endpoint,
        )
    raise ValueError(f"Unknown LLM provider: {configuration.provider}")
