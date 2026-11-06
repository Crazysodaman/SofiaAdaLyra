"""Replaceable inference adapters, loaded only when explicitly requested."""
from importlib import import_module

_EXPORTS = {
    "OllamaBenchmarkAdapter": "benchmark",
    "OllamaBenchmarkObservation": "benchmark",
    "OllamaProvider": "ollama_provider",
}
__all__ = list(_EXPORTS)


def __getattr__(name):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value
