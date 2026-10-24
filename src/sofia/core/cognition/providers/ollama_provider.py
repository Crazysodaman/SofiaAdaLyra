"""Compatibility import for the Platform-managed Ollama inference module.

Core no longer owns the provider implementation. Existing integrations may
import this path during the staged migration, but both paths resolve to the
same class and therefore cannot create a second provider execution path.
"""

from sofia.modules.inference.ollama_provider import OllamaProvider

__all__ = ["OllamaProvider"]
