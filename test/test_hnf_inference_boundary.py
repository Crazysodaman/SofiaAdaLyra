"""HNF-08 ownership and compatibility regression tests."""

from sofia.core.cognition.providers.ollama_provider import (
    OllamaProvider as CompatibilityOllamaProvider,
)
from sofia.core.cognition.providers.factory import (
    create_llm_provider as compatibility_factory,
)
from sofia.modules.inference.ollama_provider import OllamaProvider
from sofia.platform.cognition_provider import create_llm_provider
from sofia.platform.config.defaults import create_default_configuration


def test_core_ollama_import_is_the_inference_module_class() -> None:
    assert CompatibilityOllamaProvider is OllamaProvider
    assert OllamaProvider.__module__ == "sofia.modules.inference.ollama_provider"


def test_core_factory_import_is_the_platform_factory() -> None:
    assert compatibility_factory is create_llm_provider


def test_platform_factory_constructs_the_single_module_provider_path() -> None:
    configuration = create_default_configuration().provider

    provider = create_llm_provider(configuration)

    assert type(provider) is OllamaProvider
    assert provider.configuration is configuration
