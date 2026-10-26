"""Reviewed isolated process adapter for the bounded Research module.

This is intentionally not a generic Python/plugin executor.  The child entry
point and capability are fixed in reviewed Platform source.  Platform retains
authorization and capability registration; the child receives only bounded
JSON input and has no canonical-state handle.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json
import multiprocessing
from multiprocessing.connection import Connection
from pathlib import Path
import secrets
from threading import RLock
from typing import Mapping

from sofia.platform.capability.model import Capability, CapabilityRequest
from sofia.platform.run.supervisor import ProcessState, RuntimeObservation

from .adapters import (
    AdapterFactoryContract,
    AdapterInspection,
    ReviewedAdapterFactory,
    ReviewedModuleAdapter,
)
from .compatibility import ModulePlatformTarget
from .package import OperationProfileKind, VerifiedModulePackage


MAX_MESSAGE_BYTES = 262_144
RESEARCH_MODULE_ID = "org.sofia.research"
RESEARCH_COMPONENT_ID = "research.worker"
RESEARCH_CAPABILITY_ID = "research.compare_claim_sources.v1"


class ModuleProcessError(RuntimeError):
    pass


def _canonical(value: Mapping[str, object]) -> bytes:
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("module IPC payload must be canonical JSON") from exc
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise ValueError("module IPC payload exceeds size limit")
    return encoded


def _send(connection: Connection, secret: bytes, body: Mapping[str, object]) -> None:
    encoded = _canonical(body)
    connection.send_bytes(
        _canonical({
            "body": body,
            "mac": hmac.new(secret, encoded, "sha256").hexdigest(),
        })
    )


def _receive(connection: Connection, secret: bytes) -> dict[str, object]:
    raw = connection.recv_bytes(MAX_MESSAGE_BYTES)
    try:
        message = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ModuleProcessError("invalid module IPC message") from exc
    if not isinstance(message, dict) or set(message) != {"body", "mac"}:
        raise ModuleProcessError("invalid module IPC envelope")
    body, mac = message["body"], message["mac"]
    if not isinstance(body, dict) or not isinstance(mac, str) or not hmac.compare_digest(
        mac, hmac.new(secret, _canonical(body), "sha256").hexdigest(),
    ):
        raise ModuleProcessError("module IPC authentication failed")
    return body


def _research_worker_main(
    connection: Connection, secret: bytes, identity: Mapping[str, object],
) -> None:
    try:
        expected = {
            "module_id", "package_digest", "component_id", "host_identity", "epoch",
        }
        if set(identity) != expected:
            return
        _send(connection, secret, {
            "kind": "ready", **identity,
            "protocol": "sofia.module.worker.v1",
            "pid": multiprocessing.current_process().pid or 0,
        })
        accepting = True
        while True:
            message = _receive(connection, secret)
            kind = message.get("kind")
            if kind == "health" and set(message) == {"kind"}:
                _send(connection, secret, {
                    "kind": "health", "ready": True, "accepting": accepting,
                    "pid": multiprocessing.current_process().pid or 0,
                })
                continue
            if kind == "drain" and set(message) == {"kind"}:
                accepting = False
                _send(connection, secret, {"kind": "drained"})
                continue
            if kind == "shutdown" and set(message) == {"kind"}:
                _send(connection, secret, {"kind": "stopped"})
                return
            if kind != "execute" or set(message) != {
                "kind", "request_id", "capability", "parameters",
            } or not accepting:
                raise ModuleProcessError("unsupported or drained module request")
            if message["capability"] != RESEARCH_CAPABILITY_ID:
                raise PermissionError("capability identity mismatch")
            parameters = message["parameters"]
            if not isinstance(parameters, dict) or set(parameters) != {"snapshot"}:
                raise ValueError("exact research parameters required")
            from sofia.modules.research.analysis import compare_claim_sources
            result = compare_claim_sources(
                parameters["snapshot"], now=datetime.now(timezone.utc),
            )
            _send(connection, secret, {
                "kind": "result", "request_id": message["request_id"],
                "result": result,
            })
    except BaseException as exc:
        try:
            _send(connection, secret, {
                "kind": "error", "error": type(exc).__name__,
            })
        except BaseException:
            pass
    finally:
        connection.close()


class ResearchModuleProcessAdapter(ReviewedModuleAdapter):
    """One exact signed package generation in a separate OS process."""

    def __init__(
        self, *, package_digest: str, host_identity: str, runtime_dir: Path,
        response_timeout_seconds: float = 10.0,
    ) -> None:
        if (
            not isinstance(package_digest, str)
            or len(package_digest) != 64
            or any(character not in "0123456789abcdef" for character in package_digest)
        ):
            raise ValueError("package_digest must be SHA-256")
        if not isinstance(host_identity, str) or not host_identity.strip():
            raise ValueError("host_identity required")
        if not isinstance(runtime_dir, Path):
            raise TypeError("runtime_dir must be Path")
        if type(response_timeout_seconds) not in {int, float} or not (
            0.1 <= response_timeout_seconds <= 120.0
        ):
            raise ValueError("response timeout must be in 0.1..120 seconds")
        self.package_digest = package_digest
        self.host_identity = host_identity
        self.runtime_dir = runtime_dir
        self.response_timeout_seconds = response_timeout_seconds
        self._process: multiprocessing.Process | None = None
        self._connection: Connection | None = None
        self._secret: bytes | None = None
        self._epoch: int | None = None
        self._lock = RLock()
        self._capability = Capability(
            RESEARCH_CAPABILITY_ID,
            "Compare supplied source stances without browsing or truth claims.",
        )

    def _rpc(self, body: Mapping[str, object]) -> dict[str, object]:
        with self._lock:
            if self._connection is None or self._secret is None or (
                self._process is None or not self._process.is_alive()
            ):
                raise ModuleProcessError("research module process is unavailable")
            _send(self._connection, self._secret, body)
            if not self._connection.poll(self.response_timeout_seconds):
                self._force_terminate_locked()
                raise TimeoutError("research module response deadline expired")
            response = _receive(self._connection, self._secret)
        if response.get("kind") == "error":
            raise ModuleProcessError(
                f"research module failed: {response.get('error', 'unknown')}"
            )
        return response

    def _force_terminate_locked(self) -> None:
        process = self._process
        if process is not None and process.is_alive():
            process.terminate()
            process.join(2.0)
        if process is not None and process.is_alive():
            process.kill()
            process.join(2.0)
        if self._connection is not None:
            self._connection.close()
        self._process = None
        self._connection = None
        self._secret = None
        self._epoch = None

    def start(self, *, epoch: int) -> None:
        if type(epoch) is not int or epoch < 1:
            raise ValueError("positive RUN epoch required")
        if self._process is not None:
            raise RuntimeError("research module process already started")
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        parent, child = multiprocessing.get_context("spawn").Pipe(duplex=True)
        secret = secrets.token_bytes(32)
        identity = {
            "module_id": RESEARCH_MODULE_ID,
            "package_digest": self.package_digest,
            "component_id": RESEARCH_COMPONENT_ID,
            "host_identity": self.host_identity,
            "epoch": epoch,
        }
        process = multiprocessing.get_context("spawn").Process(
            target=_research_worker_main,
            args=(child, secret, identity),
            name=f"sofia-research-{epoch}", daemon=False,
        )
        process.start()
        child.close()
        self._process, self._connection, self._secret, self._epoch = (
            process, parent, secret, epoch,
        )
        if not parent.poll(self.response_timeout_seconds):
            self.stop()
            raise ModuleProcessError("research module did not become ready")
        ready = _receive(parent, secret)
        if ready != {
            "kind": "ready", **identity,
            "protocol": "sofia.module.worker.v1", "pid": process.pid,
        }:
            self.stop()
            raise ModuleProcessError("research module readiness identity mismatch")

    def inspect(self) -> AdapterInspection:
        state = ProcessState.STOPPED
        ready = False
        evidence = "probe:research-worker:stopped"
        process = self._process
        if process is not None and process.is_alive():
            try:
                response = self._rpc({"kind": "health"})
                if response.get("kind") != "health" or response.get("pid") != process.pid:
                    raise ModuleProcessError("research module health identity mismatch")
                state = ProcessState.RUNNING
                ready = response.get("ready") is True and response.get("accepting") is True
                evidence = f"probe:research-worker:{process.pid}:{self._epoch}"
            except Exception:
                state = ProcessState.FAILED
                evidence = "probe:research-worker:failed"
        return AdapterInspection(
            RESEARCH_MODULE_ID, self.package_digest, RESEARCH_COMPONENT_ID,
            self.host_identity, state, ready, evidence,
            datetime.now(timezone.utc),
        )

    def observe(self) -> RuntimeObservation:
        inspection = self.inspect()
        return RuntimeObservation(inspection.state, ready=inspection.ready)

    def stop(self) -> None:
        process = self._process
        if process is None:
            return
        try:
            if process.is_alive() and self._connection is not None:
                response = self._rpc({"kind": "drain"})
                if response != {"kind": "drained"}:
                    raise ModuleProcessError("research module drain failed")
                response = self._rpc({"kind": "shutdown"})
                if response != {"kind": "stopped"}:
                    raise ModuleProcessError("research module shutdown failed")
        finally:
            process.join(2.0)
            if process.is_alive():
                process.terminate()
                process.join(2.0)
            if process.is_alive():
                process.kill()
                process.join(2.0)
            if self._connection is not None:
                self._connection.close()
            self._process = None
            self._connection = None
            self._secret = None
            self._epoch = None

    def _handle(self, request: CapabilityRequest):
        if not isinstance(request, CapabilityRequest) or request.capability != self._capability:
            raise ValueError("canonical research capability request required")
        request_id = "module-request:" + secrets.token_hex(16)
        response = self._rpc({
            "kind": "execute", "request_id": request_id,
            "capability": RESEARCH_CAPABILITY_ID,
            "parameters": request.parameters,
        })
        if set(response) != {"kind", "request_id", "result"} or (
            response["kind"] != "result" or response["request_id"] != request_id
        ):
            raise ModuleProcessError("research module response identity mismatch")
        return response["result"]

    def capability_registrations(self):
        return ((self._capability, self._handle),)


class ReviewedResearchProcessFactory(ReviewedAdapterFactory):
    """Trusted construction bound to one verified package and local host."""

    def __init__(
        self, *, package_digest: str, host_identity: str, runtime_dir: Path,
        platform_target: ModulePlatformTarget,
    ) -> None:
        if not isinstance(runtime_dir, Path):
            raise TypeError("runtime_dir must be Path")
        if not isinstance(platform_target, ModulePlatformTarget):
            raise TypeError("platform_target must be ModulePlatformTarget")
        self.runtime_dir = runtime_dir
        self._platform_target = platform_target
        self._contract = AdapterFactoryContract(
            "factory:research-process:v1", RESEARCH_MODULE_ID,
            frozenset({package_digest}), frozenset({RESEARCH_COMPONENT_ID}),
            ("sofia.module.worker.v1",),
            frozenset({
                OperationProfileKind.OBSERVE, OperationProfileKind.ADVISORY,
            }),
            frozenset({"module.activate"}), "subprocess-restricted",
            (("cpu_millis", 75), ("ram_mib", 48)),
            frozenset({host_identity}), frozenset(), True, True, False,
        )

    @property
    def contract(self) -> AdapterFactoryContract:
        return self._contract

    @property
    def platform_target(self) -> ModulePlatformTarget:
        return self._platform_target

    def reconstruct_for_inspection(
        self, *, package: VerifiedModulePackage,
        profile: OperationProfileKind, component_id: str, host_identity: str,
    ) -> ReviewedModuleAdapter:
        if package.package_digest not in self.contract.package_digests:
            raise PermissionError("research package identity mismatch")
        if profile not in self.contract.profiles:
            raise PermissionError("research operation profile is not reviewed")
        if component_id not in self.contract.component_ids or (
            host_identity not in self.contract.host_bindings
        ):
            raise PermissionError("research component or host identity mismatch")
        return ResearchModuleProcessAdapter(
            package_digest=package.package_digest,
            host_identity=host_identity,
            runtime_dir=self.runtime_dir,
        )
