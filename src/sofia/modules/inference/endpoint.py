"""Compatibility exports for the Platform-owned endpoint contract."""
from sofia.platform.config.inference_endpoint import (
    DEFAULT_OLLAMA_ENDPOINT,
    OLLAMA_ENDPOINT_ENVIRONMENT_KEY,
    configured_ollama_endpoint,
    validate_ollama_endpoint,
)

__all__ = [
    "DEFAULT_OLLAMA_ENDPOINT", "OLLAMA_ENDPOINT_ENVIRONMENT_KEY",
    "configured_ollama_endpoint", "validate_ollama_endpoint",
]
