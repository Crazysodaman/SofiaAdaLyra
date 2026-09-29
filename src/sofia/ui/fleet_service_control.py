from __future__ import annotations

from sofia.distributed.capability import RemoteFleetToolService
from sofia.ui.control_center import ServiceAction, ServiceKind, ServiceTarget
from sofia.ui.service_control import ServiceControlResult


class FleetRemoteServiceController:
    """Tray service controller over the production exact-grant Fleet path."""

    def __init__(self, service: RemoteFleetToolService) -> None:
        if not isinstance(service, RemoteFleetToolService):
            raise TypeError("service must be a RemoteFleetToolService")
        self.service = service

    def execute(
        self,
        target: ServiceTarget,
        action: ServiceAction,
    ) -> ServiceControlResult:
        if not isinstance(target, ServiceTarget):
            raise TypeError("ServiceTarget required")
        if not isinstance(action, ServiceAction):
            raise TypeError("ServiceAction required")
        if action in {
            ServiceAction.INSTALL_MODEL,
            ServiceAction.LOAD_MODEL,
            ServiceAction.UNLOAD_MODEL,
        }:
            raise ValueError(
                "remote model lifecycle is not an enrolled Fleet capability"
            )
        if target.kind not in (
            ServiceKind.SOFIA_RUNTIME,
            ServiceKind.LLM_ENGINE,
        ):
            raise ValueError("unsupported remote service kind")

        operation = {
            ServiceAction.START: "start",
            ServiceAction.STOP: "stop",
            ServiceAction.RESTART: "restart",
        }.get(action)
        if operation is None:
            raise ValueError(f"unsupported remote action: {action.value}")

        result = self.service.invoke(
            target.host_id,
            "service.manage",
            operation,
            {"service": target.service_name},
        )
        outcome = result.get("outcome")
        message = str(result.get("message") or outcome or "unknown")
        if outcome != "reported_success":
            raise RuntimeError(
                "remote Fleet service operation did not report success: "
                f"{message}"
            )
        return ServiceControlResult(
            host_id=target.host_id,
            service_name=target.service_name,
            action=action,
            detail=message,
        )

    def close(self) -> None:
        self.service.close()
