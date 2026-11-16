"""Provider-neutral cognition interfaces; construction grants no authority."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


from sofia.sdk.cognition_model import CognitiveRequest, CognitiveResponse


class ProviderFailureKind(str, Enum):
    """Coarse, non-secret provider failure classification.

    These values are diagnostic categories, not authority to retry or execute
    anything. Only transport/unavailability categories may be used to select
    another already configured provider.
    """

    CONNECT = "connect"
    READ = "read"
    HTTP = "http"
    STREAM = "stream"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INVALID_REQUEST = "invalid_request"
    MALFORMED_RESPONSE = "malformed_response"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


ProviderErrorKind = ProviderFailureKind

_TRANSPORT_FAILURES = frozenset({
    ProviderFailureKind.CONNECT,
    ProviderFailureKind.READ,
    ProviderFailureKind.STREAM,
    ProviderFailureKind.TIMEOUT,
    ProviderFailureKind.UNAVAILABLE,
})
_RETRYABLE_FAILURES = _TRANSPORT_FAILURES


def _normalize_failure(
    category: ProviderFailureKind | str | None,
    *,
    retryable: bool | None,
) -> tuple[ProviderFailureKind, bool]:
    if category is None:
        kind = ProviderFailureKind.UNKNOWN
    elif isinstance(category, ProviderFailureKind):
        kind = category
    else:
        try:
            kind = ProviderFailureKind(category)
        except (TypeError, ValueError) as exc:
            raise ValueError("unknown provider failure category") from exc
    if retryable is None:
        retryable = kind in _RETRYABLE_FAILURES
    return kind, bool(retryable)


class _ProviderFailure(Exception):
    """Shared optional diagnostics without changing the failure message."""

    def __init__(
        self,
        message: object = "",
        *,
        category: ProviderFailureKind | str | None = None,
        provider: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
        elapsed_ms: float | None = None,
        status_code: int | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.category, self.retryable = _normalize_failure(
            category, retryable=retryable,
        )
        self.provider = provider
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.elapsed_ms = elapsed_ms
        self.status_code = status_code

    @property
    def kind(self) -> ProviderFailureKind:
        """Compatibility alias for diagnostics that use ``kind``."""
        return self.category

    @property
    def is_transport_failure(self) -> bool:
        if self.category is ProviderFailureKind.HTTP:
            return self.retryable
        return self.category in _TRANSPORT_FAILURES


class CognitiveEngineError(_ProviderFailure):
    """Raised when a cognitive engine fails."""


class CognitiveEngine(ABC):
    """Portable computation boundary, separate from personal Core identity."""

    @abstractmethod
    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        raise NotImplementedError


class LLMProviderError(_ProviderFailure):
    """Raised when an LLM provider fails."""


class LLMProvider(ABC):
    """External model adapter; no owner, tool or writer authorization."""

    @abstractmethod
    def respond(self, request: CognitiveRequest) -> CognitiveResponse:
        raise NotImplementedError
