"""Typed service/model controls used by the tray client."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sofia.integrations.local_maintenance import LocalMaintenanceAdapter
from sofia.integrations.ollama import OllamaAdapter

from .control_center import ServiceAction, ServiceKind, ServiceTarget


class RemoteControlUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ServiceControlResult:
    host_id: str
    service_name: str
    action: ServiceAction
    detail: str


class RemoteServiceController(Protocol):
    def execute(self, target: ServiceTarget, action: ServiceAction) -> ServiceControlResult: ...


class DesktopServiceController:
    """Route local service controls locally and remote controls through Fleet."""

    def __init__(
        self,
        *,
        local_host_id: str,
        local_maintenance: LocalMaintenanceAdapter | None = None,
        remote: RemoteServiceController | None = None,
        ollama: OllamaAdapter | None = None,
        llm_model: str | None = None,
    ) -> None:
        if not isinstance(local_host_id, str) or not local_host_id.strip():
            raise ValueError("local_host_id required")
        self.local_host_id = local_host_id
        self.local = local_maintenance or LocalMaintenanceAdapter()
        self.remote = remote
        self.ollama = ollama or OllamaAdapter()
        self.llm_model = llm_model

    def execute(self, target: ServiceTarget, action: ServiceAction) -> ServiceControlResult:
        if not isinstance(target, ServiceTarget):
            raise TypeError("ServiceTarget required")
        if not isinstance(action, ServiceAction):
            raise TypeError("ServiceAction required")

        if target.host_id != self.local_host_id:
            if self.remote is None:
                raise RemoteControlUnavailable(
                    "remote service control requires an authenticated Fleet controller"
                )
            return self.remote.execute(target, action)

        if action is ServiceAction.UNLOAD_MODEL:
            if target.kind is not ServiceKind.LLM_ENGINE:
                raise ValueError("only an LLM target can unload a model")
            if not self.llm_model:
                raise ValueError("LLM model identity required for unload")
            self.ollama.unload(self.llm_model)
            return ServiceControlResult(
                target.host_id,
                target.service_name,
                action,
                f"unload requested for {self.llm_model}",
            )

        command = {
            ServiceAction.START: "start",
            ServiceAction.STOP: "stop",
            ServiceAction.RESTART: "restart",
        }.get(action)
        if command is None:
            raise ValueError(f"unsupported service action: {action.value}")
        result = self.local.service(target.service_name, command)
        detail = result.stdout.strip() or result.stderr.strip() or "ok"
        return ServiceControlResult(
            target.host_id,
            target.service_name,
            action,
            detail,
        )
