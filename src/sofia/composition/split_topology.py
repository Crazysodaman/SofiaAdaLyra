"""Operator-selected split runtime / inference topology admission policy.

Current production remains Venus writer; this does not move or elect state.
An operator may separately configure the future Artemis runtime as remote-only.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping

from sofia.config.model import SofiaConfiguration
from sofia.distributed.inference_client import ConfiguredRemoteInferenceClient


@dataclass(frozen=True, slots=True)
class SplitInferenceDeployment:
    runtime_host_id: str
    gpu_worker_host_id: str

    def __post_init__(self) -> None:
        for name in ("runtime_host_id", "gpu_worker_host_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 160:
                raise ValueError(f"{name} must be an exact bounded Fleet host ID")
        if self.runtime_host_id == self.gpu_worker_host_id:
            raise ValueError("canonical runtime and inference worker must be distinct")


def selected_split_deployment(
    environ: Mapping[str, str] | None = None,
) -> SplitInferenceDeployment | None:
    """Load explicit, privileged host launch config, not model-generated text.

    An absent role retains the existing Venus production behavior.
    An Artemis role without both exact host IDs fails closed.
    """
    env = os.environ if environ is None else environ
    mode = env.get("SOFIA_SPLIT_INFERENCE_ROLE", "").strip()
    if not mode:
        if env.get("SOFIA_SPLIT_RUNTIME_HOST_ID") or env.get("SOFIA_SPLIT_GPU_HOST_ID"):
            raise ValueError("split topology host IDs require explicit role")
        return None
    if mode != "artemis_runtime":
        raise ValueError("unknown explicit split inference runtime role")
    return SplitInferenceDeployment(
        runtime_host_id=env.get("SOFIA_SPLIT_RUNTIME_HOST_ID", ""),
        gpu_worker_host_id=env.get("SOFIA_SPLIT_GPU_HOST_ID", ""),
    )


def validate_split_inference_runtime(
    *,
    configuration: SofiaConfiguration,
    local_host_id: str | None,
    remote_inference_client,
    deployment: SplitInferenceDeployment | None,
    require_transport: bool = True,
) -> None:
    """Reject any future split runtime that could silently fall back locally.

    The Fleet remote inference transport performs mTLS and grants. This only
    checks placement and no-fallback invariants at production composition.
    """
    if deployment is None:
        return
    if local_host_id != deployment.runtime_host_id:
        raise PermissionError("split inference runtime is not the authorized host")
    fleet = configuration.fleet_cognition
    if not fleet.enabled:
        raise ValueError("Artemis split inference requires Fleet cognition")
    if fleet.local_fallback:
        raise PermissionError("Artemis may not fall back to local inference")
    if fleet.auto_provision_models:
        raise PermissionError("Artemis must not install or switch worker models")
    if not fleet.gpu_required:
        raise PermissionError("Venus GPU worker must be required for placement")
    if fleet.allowed_host_ids != (deployment.gpu_worker_host_id,):
        raise PermissionError("Artemis inference must target exactly approved Venus host")
    if deployment.runtime_host_id in fleet.allowed_host_ids:
        raise PermissionError("Artemis cannot select itself for GPU inference")
    if require_transport and not isinstance(
        remote_inference_client, ConfiguredRemoteInferenceClient
    ):
        raise ValueError(
            "production pinned-mTLS remote inference client is required"
        )
    if configuration.routing is not None and configuration.routing.enabled:
        routing = configuration.routing
        if routing.fallback_enabled:
            raise PermissionError("alternate-model failover is disabled on Artemis")
        providers = (routing.primary, routing.secondary)
    else:
        providers = (configuration.provider,)
    if any(provider is None or provider.provider != "ollama" for provider in providers):
        raise PermissionError("Artemis split cognition requires approved Ollama models")
