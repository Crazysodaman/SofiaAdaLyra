from sofia.cognition.provider import LLMProvider
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.cognition.providers.test_provider import TestLLMProvider
from sofia.config.model import ProviderConfiguration


def create_llm_provider(
    configuration: ProviderConfiguration,
) -> LLMProvider:
    """
    Construct the configured LLM provider adapter.
    """

    if configuration.provider == "test-llm":
        return TestLLMProvider()

    if configuration.provider == "ollama":
        return OllamaProvider(
            configuration=configuration,
        )

    raise ValueError(
        f"Unknown LLM provider: {configuration.provider}"
    )