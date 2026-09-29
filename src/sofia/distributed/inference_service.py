"""Agent-side cognitive worker for explicitly allowed local Ollama models.

This service performs inference only. Tool calls are returned to the caller as
data; there is intentionally no CapabilityGateway, ActionSystem, shell, or tool
dispatcher on this boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from sofia.cognition.provider import LLMProvider
from sofia.cognition.providers.ollama_provider import OllamaProvider
from sofia.config.model import ProviderConfiguration
from sofia.distributed.inference import (
    RemoteInferenceRequest,
    RemoteInferenceResponse,
)


class RemoteInferenceDenied(PermissionError):
    """The requested inference is outside the worker's configured policy."""


@dataclass(frozen=True, slots=True)
class RemoteInferencePolicy:
    allowed_models: tuple[str, ...]
    max_context_size: int = 65_536
    allow_tools: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.allowed_models, tuple) or not self.allowed_models:
            raise ValueError("allowed_models must be a nonempty tuple")
        normalized: list[str] = []
        for model in self.allowed_models:
            if (
                not isinstance(model, str)
                or not model.strip()
                or len(model.encode("utf-8")) > 512
                or "\x00" in model
            ):
                raise ValueError("allowed_models contains an invalid model name")
            normalized.append(model.strip())
        if len(set(normalized)) != len(normalized):
            raise ValueError("allowed_models must not contain duplicates")
        if type(self.max_context_size) is not int or not (
            512 <= self.max_context_size <= 1_048_576
        ):
            raise ValueError("max_context_size must be in 512..1048576")
        if type(self.allow_tools) is not bool:
            raise TypeError("allow_tools must be a bool")
        object.__setattr__(self, "allowed_models", tuple(normalized))


ProviderFactory = Callable[[ProviderConfiguration], LLMProvider]


class LocalOllamaInferenceService:
    """Run one bounded cognitive request on an explicitly allowed local model."""

    def __init__(
        self,
        *,
        node_id: UUID,
        policy: RemoteInferencePolicy,
        provider_factory: ProviderFactory | None = None,
    ) -> None:
        if not isinstance(node_id, UUID):
            raise TypeError("node_id must be a UUID")
        if not isinstance(policy, RemoteInferencePolicy):
            raise TypeError("policy must be RemoteInferencePolicy")
        if provider_factory is not None and not callable(provider_factory):
            raise TypeError("provider_factory must be callable or None")
        self.node_id = node_id
        self.policy = policy
        self._provider_factory = provider_factory or (
            lambda configuration: OllamaProvider(configuration)
        )

    def infer(
        self,
        request: RemoteInferenceRequest,
    ) -> RemoteInferenceResponse:
        if not isinstance(request, RemoteInferenceRequest):
            raise TypeError("request must be RemoteInferenceRequest")
        if request.node_id != self.node_id:
            raise RemoteInferenceDenied(
                "inference request is addressed to a different node"
            )
        configuration = request.provider
        if configuration.provider != "ollama":
            raise RemoteInferenceDenied(
                "this worker only exposes its configured Ollama backend"
            )
        if configuration.model not in self.policy.allowed_models:
            raise RemoteInferenceDenied(
                "requested model is not in this worker's allowlist"
            )
        if (
            configuration.context_size is not None
            and configuration.context_size > self.policy.max_context_size
        ):
            raise RemoteInferenceDenied(
                "requested context size exceeds worker policy"
            )
        if request.request.tools and not self.policy.allow_tools:
            raise RemoteInferenceDenied(
                "tool schemas are disabled for this inference worker"
            )

        provider = self._provider_factory(configuration)
        if not isinstance(provider, LLMProvider):
            raise TypeError(
                "provider_factory must return an LLMProvider"
            )
        response = provider.respond(request.request)
        return RemoteInferenceResponse(
            request_id=request.request_id,
            node_id=request.node_id,
            response=response,
        )
