"""Typed workload execution backend.

A workload catalog binds known workload/host identities to already-reviewed
agent capabilities. No shell, argv, executable path, password, or secret is
accepted from a migration request.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from sofia.distributed.operations import RemoteOperationUncertain
from sofia.ops.workload import MigrationPlan


Scalar = str | int | float | bool | None


@dataclass(frozen=True, slots=True)
class WorkloadOperationBinding:
    capability: str
    operation: str
    parameters: tuple[tuple[str, Scalar], ...] = ()
    context_parameters: tuple[tuple[str, str], ...] = ()
    expect_path: str | None = None
    expect_equals: Scalar = None
    result_ref_path: str | None = None

    def __post_init__(self) -> None:
        if not self.capability.strip() or not self.operation.strip():
            raise ValueError("capability and operation are required")
        forbidden = {
            "command","commands","cmd","shell","script","executable",
            "argv","arguments","password","token","secret","private_key",
        }
        for key, value in self.parameters:
            if not isinstance(key, str) or not key.strip():
                raise ValueError("parameter keys must be nonempty")
            if key.casefold() in forbidden:
                raise ValueError("arbitrary execution/secret parameters are forbidden")
            if type(value) not in (str, int, float, bool, type(None)):
                raise TypeError("operation parameters must be bounded scalars")
        allowed_context = {
            "migration_id","workload_id","version","lease_epoch",
            "checkpoint_ref","standby",
        }
        for parameter, context_key in self.context_parameters:
            if not parameter.strip() or parameter.casefold() in forbidden:
                raise ValueError("invalid context parameter")
            if context_key not in allowed_context:
                raise ValueError(f"unsupported context field: {context_key}")


@dataclass(frozen=True, slots=True)
class HostWorkloadProfile:
    workload_id: str
    version: str
    host_id: str
    drain: WorkloadOperationBinding
    start: WorkloadOperationBinding
    ready: WorkloadOperationBinding
    fence: WorkloadOperationBinding
    checkpoint: WorkloadOperationBinding | None = None
    activate: WorkloadOperationBinding | None = None
    rollback: WorkloadOperationBinding | None = None

    def __post_init__(self) -> None:
        if not self.workload_id.strip() or not self.version.strip() or not self.host_id.strip():
            raise ValueError("workload/version/host identity required")


class WorkloadExecutionCatalog:
    def __init__(self, profiles: tuple[HostWorkloadProfile, ...]) -> None:
        if not profiles:
            raise ValueError("workload catalog requires profiles")
        keys = [(p.workload_id, p.version, p.host_id) for p in profiles]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate workload host profile")
        self._profiles = {key: profile for key, profile in zip(keys, profiles)}

    def profile(self, workload_id: str, version: str, host_id: str) -> HostWorkloadProfile:
        try:
            return self._profiles[(workload_id, version, host_id)]
        except KeyError as exc:
            raise KeyError(
                f"no workload execution profile for {workload_id}@{version} on {host_id}"
            ) from exc

    @staticmethod
    def _binding(raw: Mapping[str, Any] | None) -> WorkloadOperationBinding | None:
        if raw is None:
            return None
        if not isinstance(raw, Mapping):
            raise TypeError("operation binding must be an object")
        parameters = raw.get("parameters", {})
        context_parameters = raw.get("context_parameters", {})
        if not isinstance(parameters, Mapping) or not isinstance(context_parameters, Mapping):
            raise TypeError("binding parameters must be objects")
        return WorkloadOperationBinding(
            capability=str(raw["capability"]),
            operation=str(raw["operation"]),
            parameters=tuple((str(k), v) for k, v in sorted(parameters.items())),
            context_parameters=tuple(
                (str(k), str(v)) for k, v in sorted(context_parameters.items())
            ),
            expect_path=(
                None if raw.get("expect_path") is None else str(raw["expect_path"])
            ),
            expect_equals=raw.get("expect_equals"),
            result_ref_path=(
                None if raw.get("result_ref_path") is None
                else str(raw["result_ref_path"])
            ),
        )

    @classmethod
    def from_file(cls, path: Path) -> "WorkloadExecutionCatalog":
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = raw.get("profiles") if isinstance(raw, dict) else None
        if not isinstance(rows, list):
            raise ValueError("workload catalog requires profiles array")
        profiles = []
        for row in rows:
            if not isinstance(row, dict):
                raise TypeError("workload profile must be an object")
            profiles.append(
                HostWorkloadProfile(
                    workload_id=str(row["workload_id"]),
                    version=str(row["version"]),
                    host_id=str(row["host_id"]),
                    drain=cls._binding(row.get("drain")),
                    checkpoint=cls._binding(row.get("checkpoint")),
                    start=cls._binding(row.get("start")),
                    ready=cls._binding(row.get("ready")),
                    fence=cls._binding(row.get("fence")),
                    activate=cls._binding(row.get("activate")),
                    rollback=cls._binding(row.get("rollback")),
                )
            )
        return cls(tuple(profiles))


@dataclass(frozen=True, slots=True)
class WorkloadExecutionReceipt:
    step: str
    host_id: str
    capability: str
    operation: str
    reported_success: bool
    message: str
    result: Any = None
    result_ref: str | None = None


class WorkloadOperationInvoker(Protocol):
    def __call__(
        self,
        host_id: str,
        capability: str,
        operation: str,
        parameters: dict[str, Scalar],
    ) -> Mapping[str, Any]:
        ...


class WorkloadBackendError(RuntimeError):
    pass


class WorkloadOutcomeUncertain(WorkloadBackendError):
    pass


def _path(value: Any, dotted: str | None) -> Any:
    if dotted is None:
        return None
    current = value
    for part in dotted.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                raise WorkloadBackendError(f"result path is missing: {dotted}")
            current = current[part]
            continue
        if isinstance(current, (list, tuple)) and part.isdigit():
            index = int(part)
            if index >= len(current):
                raise WorkloadBackendError(f"result path is missing: {dotted}")
            current = current[index]
            continue
        raise WorkloadBackendError(f"result path is missing: {dotted}")
    return current


class TypedWorkloadBackend:
    def __init__(
        self,
        catalog: WorkloadExecutionCatalog,
        invoker: WorkloadOperationInvoker,
    ) -> None:
        if not isinstance(catalog, WorkloadExecutionCatalog):
            raise TypeError("catalog must be WorkloadExecutionCatalog")
        if not callable(invoker):
            raise TypeError("invoker must be callable")
        self.catalog = catalog
        self.invoker = invoker

    @staticmethod
    def _context(
        plan: MigrationPlan,
        *,
        lease_epoch: int,
        checkpoint_ref: str | None,
        standby: bool,
    ) -> dict[str, Scalar]:
        return {
            "migration_id": plan.migration_id,
            "workload_id": plan.workload.contract.workload_id,
            "version": plan.workload.contract.version,
            "lease_epoch": lease_epoch,
            "checkpoint_ref": checkpoint_ref,
            "standby": standby,
        }

    def binding(self, plan: MigrationPlan, host_id: str, step: str):
        profile = self.catalog.profile(
            plan.workload.contract.workload_id,
            plan.workload.contract.version,
            host_id,
        )
        binding = getattr(profile, step)
        if binding is None:
            raise WorkloadBackendError(
                f"{step} operation is not declared for {host_id}"
            )
        return binding

    def execute(
        self,
        plan: MigrationPlan,
        *,
        host_id: str,
        step: str,
        lease_epoch: int,
        checkpoint_ref: str | None = None,
        standby: bool = False,
    ) -> WorkloadExecutionReceipt:
        binding = self.binding(plan, host_id, step)
        context = self._context(
            plan,
            lease_epoch=lease_epoch,
            checkpoint_ref=checkpoint_ref,
            standby=standby,
        )
        parameters = dict(binding.parameters)
        for parameter, context_key in binding.context_parameters:
            parameters[parameter] = context[context_key]
        try:
            raw = self.invoker(
                host_id,
                binding.capability,
                binding.operation,
                parameters,
            )
        except WorkloadOutcomeUncertain:
            raise
        except RemoteOperationUncertain as exc:
            raise WorkloadOutcomeUncertain(
                f"{step} outcome is uncertain on {host_id}; do not retry or rollback"
            ) from exc
        except Exception as exc:
            raise WorkloadBackendError(
                f"{step} failed on {host_id}: {type(exc).__name__}: {exc}"
            ) from exc
        if not isinstance(raw, Mapping):
            raise WorkloadBackendError("workload invoker returned invalid receipt")
        outcome = str(raw.get("outcome", ""))
        success = outcome in {"reported_success", "success", "ok"}
        message = str(raw.get("message", ""))
        result = raw.get("result")
        if result is None and message:
            try:
                result = json.loads(message)
            except (json.JSONDecodeError, TypeError):
                result = None
        if not success:
            raise WorkloadBackendError(
                f"{step} reported failure on {host_id}: {message or outcome}"
            )
        if binding.expect_path is not None:
            observed = _path(result, binding.expect_path)
            if observed != binding.expect_equals:
                raise WorkloadBackendError(
                    f"{step} verification failed on {host_id}: "
                    f"{binding.expect_path}={observed!r}"
                )
        result_ref = None
        if binding.result_ref_path is not None:
            observed = _path(result, binding.result_ref_path)
            if observed is None:
                raise WorkloadBackendError(
                    f"{step} result reference is missing"
                )
            result_ref = str(observed)
        return WorkloadExecutionReceipt(
            step=step,
            host_id=host_id,
            capability=binding.capability,
            operation=binding.operation,
            reported_success=True,
            message=message,
            result=result,
            result_ref=result_ref,
        )
