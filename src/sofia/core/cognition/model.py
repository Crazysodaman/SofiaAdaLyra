"""Compatibility exports for SDK-owned provider-neutral cognition contracts.

The cognition payload contracts moved to ``sofia.sdk.cognition_model`` so the
SDK and the Platform foundations do not import ``sofia.core``.
"""
from sofia.sdk.cognition_model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveResponse,
    CognitiveRole,
    CognitiveToolCall,
    CognitiveToolDefinition,
)

__all__ = [
    "CognitiveMessage",
    "CognitiveRequest",
    "CognitiveResponse",
    "CognitiveRole",
    "CognitiveToolCall",
    "CognitiveToolDefinition",
]
