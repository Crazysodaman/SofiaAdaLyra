"""Fleet-aware cognitive placement with explicit local fallback policy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from sofia.cognition.engine import CognitiveEngine, CognitiveEngineError
from sofia.cognition.model import CognitiveRequest, CognitiveResponse
from sofia.config.model import ProviderConfiguration
from sofia.ops.capability import OpsToolService
from sofia.ops.model import FleetHost, WorkloadContract


RemoteInfer = Callable[
    [UUID, ProviderConfiguration, CognitiveRequest],
    CognitiveResponse,
]
RemotePrepare = Callable[
    [UUID, ProviderConfiguration, bool],
    None,
]


@dataclass(frozen=True, slots=True)
class FleetCognitionPolicy:
    """Placement requirements for one cognitive engine role."""

    enabled: bool = False
    local_fallback: bool = True
    min_ram_bytes: int = 0
    min_vram_bytes: int = 0
    gpu_required: bool = False
    auto_provision_models: bool = False
    allowed_host_ids: tuple[str, ...] = ()
    denied_host_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be a bool")
        if type(self.local_fallback) is not bool:
            raise TypeError("local_fallback must be a bool")
        if type(self.gpu_required) is not bool:
            raise TypeError("gpu_required must be a bool")
        if type(self.auto_provision_models) is not bool:
            raise TypeError("auto_provision_models must be a bool")
        for name in ("min_ram_bytes", "min_vram_bytes"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a nonnegative int")
        for name in ("allowed_host_ids", "denied_host_ids"):
            values = getattr(self, name)
            if not isinstance(values, tuple):
                raise TypeError(f"{name} must be a tuple")
            if any(
                not isinstance(value, str) or not value.strip()
                for value in values
            ):
                raise ValueError(
                    f"{name} must contain nonempty host IDs"
                )


class FleetPlacedCognitiveEngine(CognitiveEngine):
    """Place inference on an eligible authenticated Fleet worker when possible.

    Identity, memory, authority, capability execution, and tool dispatch remain
    in the authoritative Sofía runtime. A remote engine receives the same
    CognitiveRequest and returns only CognitiveResponse data.
    """

    def __init__(
        self,
        *,
        local: CognitiveEngine,
        provider: ProviderConfiguration,
        ops: OpsToolService,
        local_host_id: str,
        remote_infer: RemoteInfer,
        remote_prepare: RemotePrepare | None = None,
        policy: FleetCognitionPolicy,
        workload_id: str,
    ) -> None:
        if not isinstance(local, CognitiveEngine):
            raise TypeError("local must be a CognitiveEngine")
        if not isinstance(provider, ProviderConfiguration):
            raise TypeError("provider must be ProviderConfiguration")
        if not isinstance(ops, OpsToolService):
            raise TypeError("ops must be OpsToolService")
        if not isinstance(local_host_id, str) or not local_host_id.strip():
            raise ValueError("local_host_id required")
        if not callable(remote_infer):
            raise TypeError("remote_infer must be callable")
        if remote_prepare is not None and not callable(remote_prepare):
            raise TypeError("remote_prepare must be callable or None")
        if not isinstance(policy, FleetCognitionPolicy):
            raise TypeError("policy must be FleetCognitionPolicy")
        if not isinstance(workload_id, str) or not workload_id.strip():
            raise ValueError("workload_id required")
        self.local = local
        self.provider = provider
        self.ops = ops
        self.local_host_id = local_host_id.strip()
        self.remote_infer = remote_infer
        self.remote_prepare = remote_prepare
        self.policy = policy
        self.workload_id = workload_id.strip()
        self.last_host_id: str | None = None
        self.last_remote = False

    def _contract(self) -> WorkloadContract:
        return WorkloadContract(
            workload_id=self.workload_id,
            version="1",
            supported_platforms=(
                "windows",
                "linux",
            ),
            supported_architectures=(
                "x86_64",
                "amd64",
                "arm64",
                "aarch64",
            ),
            min_ram_bytes=self.policy.min_ram_bytes,
            gpu_required=self.policy.gpu_required,
            min_vram_bytes=self.policy.min_vram_bytes,
            allowed_host_ids=self.policy.allowed_host_ids,
            denied_host_ids=self.policy.denied_host_ids,
            allow_interactive_host=False,
        )

    def _eligible_hosts(self) -> tuple[FleetHost, ...]:
        return tuple(
            host
            for host in self.ops.registry.hosts()
            if (
                host.host_id == self.local_host_id
                or host.node_id is not None
            )
        )

    def _local_or_raise(
        self,
        request: CognitiveRequest,
        *,
        cause: BaseException | None = None,
    ) -> CognitiveResponse:
        if not self.policy.local_fallback:
            error = CognitiveEngineError(
                "Fleet cognition has no accepted remote result and local fallback is disabled."
            )
            if cause is None:
                raise error
            raise error from cause
        self.last_host_id = self.local_host_id
        self.last_remote = False
        return self.local.respond(request)

    def respond(
        self,
        request: CognitiveRequest,
    ) -> CognitiveResponse:
        if not isinstance(request, CognitiveRequest):
            raise TypeError("request must be CognitiveRequest")
        if not self.policy.enabled:
            return self._local_or_raise(request)

        hosts = self._eligible_hosts()
        activities = {
            host.host_id: self.ops.activity.state(host.host_id)
            for host in hosts
        }
        decision = self.ops.placement.choose(
            self._contract(),
            hosts,
            activities=activities,
        )
        host_id = decision.host_id
        if host_id is None:
            return self._local_or_raise(request)

        host = self.ops.registry.host(host_id)
        if host is None:
            return self._local_or_raise(request)
        if host.host_id == self.local_host_id:
            return self._local_or_raise(request)
        if host.node_id is None:
            return self._local_or_raise(request)

        try:
            if self.remote_prepare is not None:
                self.remote_prepare(
                    host.node_id,
                    self.provider,
                    self.policy.auto_provision_models,
                )
            response = self.remote_infer(
                host.node_id,
                self.provider,
                request,
            )
        except Exception as exc:
            return self._local_or_raise(
                request,
                cause=exc,
            )
        if not isinstance(response, CognitiveResponse):
            return self._local_or_raise(
                request,
                cause=TypeError(
                    "remote inference must return CognitiveResponse"
                ),
            )
        self.last_host_id = host.host_id
        self.last_remote = True
        return response
