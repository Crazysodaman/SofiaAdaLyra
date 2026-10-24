"""Replaceable inference-provider adapters.

These adapters translate the provider-neutral Core request/response contract.
They do not authenticate principals, grant capabilities, or execute tool
calls returned by a model.
"""

from .ollama_provider import OllamaProvider
from .benchmark import OllamaBenchmarkAdapter, OllamaBenchmarkObservation

__all__ = [
    "OllamaBenchmarkAdapter", "OllamaBenchmarkObservation", "OllamaProvider",
]
