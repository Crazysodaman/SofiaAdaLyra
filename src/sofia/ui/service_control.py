"""Typed service/model controls used by the tray client."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from sofia.integrations.local_maintenance import LocalMaintenanceAdapter
from sofia.integrations.ollama import OllamaAdapter
from sofia.safe.execution_approval import ExecutionApprovalVerifier

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
        approval_verifier: ExecutionApprovalVerifier | None = None,
    ) -> None:
        if not isinstance(local_host_id, str) or not local_host_id.strip():
            raise ValueError("local_host_id required")
        self.local_host_id = local_host_id
        self.local = local_maintenance or LocalMaintenanceAdapter()
        self.remote = remote
        self.ollama = ollama or OllamaAdapter()
        self.approval_verifier = approval_verifier

    @staticmethod
    def approval_spec(
        target: ServiceTarget,
        action: ServiceAction,
        *,
        llm_model: str | None = None,
        llm_keep_alive: str | None = None,
    ) -> tuple[str, dict]:
        if action is ServiceAction.INSTALL_MODEL:
            if target.kind is not ServiceKind.LLM_ENGINE:
                raise ValueError("only an LLM target can install a model")
            if not llm_model:
                raise ValueError("LLM model identity required for install")
            return "ollama.model.pull", {"model": llm_model}
        if action is ServiceAction.LOAD_MODEL:
            if target.kind is not ServiceKind.LLM_ENGINE:
                raise ValueError("only an LLM target can load a model")
            if not llm_model:
                raise ValueError("LLM model identity required for load")
            keep_alive = (llm_keep_alive or "10m").strip()
            if not keep_alive:
                raise ValueError("LLM keep_alive required for load")
            return "ollama.model.load", {
                "model": llm_model,
                "keep_alive": keep_alive,
            }
        if action is ServiceAction.UNLOAD_MODEL:
            if target.kind is not ServiceKind.LLM_ENGINE:
                raise ValueError("only an LLM target can unload a model")
            if not llm_model:
                raise ValueError("LLM model identity required for unload")
            return "ollama.model.unload", {"model": llm_model}
        command = {
            ServiceAction.START: "start",
            ServiceAction.STOP: "stop",
            ServiceAction.RESTART: "restart",
        }.get(action)
        if command is None:
            raise ValueError(f"unsupported service action: {action.value}")
        return f"local.service.{command}", {"name": target.service_name}

    def execute(
        self,
        target: ServiceTarget,
        action: ServiceAction,
        *,
        approval_id: str | None = None,
        llm_model: str | None = None,
        llm_keep_alive: str | None = None,
    ) -> ServiceControlResult:
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

        if self.approval_verifier is None:
            raise PermissionError(
                "local service control requires an execution approval verifier"
            )
        capability, parameters = self.approval_spec(
            target,
            action,
            llm_model=llm_model,
            llm_keep_alive=llm_keep_alive,
        )
        self.approval_verifier.consume(
            approval_id=approval_id or "",
            capability=capability,
            parameters=parameters,
            now=datetime.now(timezone.utc),
        )

        if action is ServiceAction.INSTALL_MODEL:
            if target.kind is not ServiceKind.LLM_ENGINE:
                raise ValueError("only an LLM target can install a model")
            if not llm_model:
                raise ValueError("LLM model identity required for install")
            self.ollama.pull(llm_model)
            if llm_model not in self._model_names(self.ollama.models()):
                raise RuntimeError("Ollama did not confirm the installed model")
            return ServiceControlResult(
                target.host_id,
                target.service_name,
                action,
                f"install confirmed for {llm_model}",
            )

        if action is ServiceAction.LOAD_MODEL:
            if target.kind is not ServiceKind.LLM_ENGINE:
                raise ValueError("only an LLM target can load a model")
            if not llm_model:
                raise ValueError("LLM model identity required for load")
            keep_alive = (llm_keep_alive or "10m").strip()
            if not keep_alive:
                raise ValueError("LLM keep_alive required for load")
            self.ollama.load(llm_model, keep_alive=keep_alive)
            if llm_model not in self._model_names(self.ollama.running()):
                raise RuntimeError("Ollama did not confirm the loaded model")
            return ServiceControlResult(
                target.host_id,
                target.service_name,
                action,
                f"load confirmed for {llm_model}",
            )

        if action is ServiceAction.UNLOAD_MODEL:
            if target.kind is not ServiceKind.LLM_ENGINE:
                raise ValueError("only an LLM target can unload a model")
            if not llm_model:
                raise ValueError("LLM model identity required for unload")
            self.ollama.unload(llm_model)
            if llm_model in self._model_names(self.ollama.running()):
                raise RuntimeError("Ollama did not confirm the unloaded model")
            return ServiceControlResult(
                target.host_id,
                target.service_name,
                action,
                f"unload confirmed for {llm_model}",
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

    @staticmethod
    def _model_names(payload) -> frozenset[str]:
        items = payload.get("models", ()) if isinstance(payload, dict) else ()
        return frozenset(
            str(item.get("name") or item.get("model")).strip()
            for item in items
            if isinstance(item, dict) and (item.get("name") or item.get("model"))
        )
