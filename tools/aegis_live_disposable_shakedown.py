#!/usr/bin/env python3
"""Opt-in live Aegis shakedown harness (disposable state only).

This tool is deliberately NOT a pytest module and is never collected by the
default test suite.  It exercises two independent live boundaries:

1. A signed synthetic Core component is built from this checkout, physically
   installed through the existing component installer with ephemeral test
   keys, then supervised as a real OS subprocess by the existing lifecycle
   state machine.  A crash is forced, the process is truthfully reconciled,
   restarted with a generation advance, stopped, detached and physically
   uninstalled.  Platform health must remain true with zero Cores registered.

2. The canonical Ollama provider adapter is called against a local Ollama
   endpoint (default ``http://127.0.0.1:11434``) with a real marker prompt.
   Separately, the canonical Core Link client/server path is exercised over
   real loopback mTLS with a disposable canonical application state.  The
   conversation LLM in that path is the deterministic test engine and is
   labelled as such; it is never reported as real inference.

No installed Windows service/systemd unit is created or claimed.  No real
Sofia personal memory, production credential, Artemis or Venus host is used.
No model is downloaded: the harness refuses to run if the configured model is
not already present on the local Ollama server.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import signal
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

if __package__ in (None, ""):
    _ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_ROOT))
    sys.path.insert(0, str(_ROOT / "src"))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
)

from sofia.core.conversation.lifelong import LifelongThreadStore  # noqa: E402
from sofia.platform.config.model import ProviderConfiguration  # noqa: E402
from sofia.platform.core_link import (  # noqa: E402
    CoreLinkBinding,
    CoreLinkBindingState,
    CoreLinkBindingStore,
    CoreLinkClientAccessStore,
    CoreLinkConversationGateway,
    CoreLinkEndpoint,
    CoreLinkServer,
    CoreLinkServerConfiguration,
    CoreLinkTLSCredentials,
    PinnedCoreLinkClient,
)
from sofia.platform.core_link.transport import CoreLinkTransportError  # noqa: E402
from sofia.platform.core_worker.ollama_transport import (  # noqa: E402
    GenericOllamaProvider,
)
from sofia.platform.core_worker.synthetic_backend import (  # noqa: E402
    SyntheticCoreProcessBackend,
)
from sofia.platform.ops.component_install import (  # noqa: E402
    CORE_DISTRIBUTION,
    CoreComponentArtifact,
    CoreComponentInstaller,
    CoreComponentRegistry,
    Ed25519ComponentSignatureVerifier,
)
from sofia.platform.ops.platform_install import InstallAuthority  # noqa: E402
from sofia.platform.ops.synthetic_core_lifecycle import (  # noqa: E402
    CoreProcessObservation,
    SyntheticCoreLifecycle,
    SyntheticCoreLifecycleConflict,
    SyntheticCoreOutcome,
    SyntheticCoreState,
)
from sofia.platform.safe.operator_stop import OperatorStopStore  # noqa: E402
from sofia.platform.state.canonical_sqlite import (  # noqa: E402
    bootstrap_canonical_sqlite,
)
from sofia.platform.verify.component_artifacts import build_component  # noqa: E402
from sofia.sdk import (  # noqa: E402
    CoreLinkResponseStatus,
    ProtocolVersion,
)
from sofia.sdk.cognition_model import (  # noqa: E402
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)

# Existing contract-test helpers.  The TLS material, access fixtures and
# canonical application configuration are reused rather than re-invented.
from test.owner_auth_fixture import (  # noqa: E402
    resume_with_signed_owner_proof,
)
from test.test_core_link_conversation import (  # noqa: E402
    NOW,
    access,
    authorize,
    configuration,
    request,
    tls_material,
)

SCHEMA = "aegis.live.disposable-shakedown.v1"
ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "test" / "fixtures" / "synthetic_core_entrypoint.py"
SIGNER_KEY_ID = "aegis-live-ephemeral-test-key"
OWNER = "owner:aegis-live-shakedown"
DEFAULT_MODEL = "qwen2.5-coder:14b"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
CONVERSATION_CLOCK = lambda: NOW + timedelta(seconds=10)  # noqa: E731


class ShakedownFailure(AssertionError):
    """A live invariant did not hold."""


def require(condition: object, label: str, detail: object = None) -> None:
    if not condition:
        raise ShakedownFailure(f"{label}: {detail!r}")


def _expect(exc_type, action) -> dict[str, object]:
    try:
        action()
    except exc_type as exc:  # noqa: BLE001 - explicit expected failure
        return {
            "type": type(exc).__name__,
            "message": str(exc)[:500],
            "expected": exc_type.__name__,
        }
    raise ShakedownFailure(f"expected {exc_type.__name__} was not raised")


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _git_sha() -> str:
    import subprocess

    completed = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT}", "rev-parse", "HEAD"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=30,
    )
    value = completed.stdout.strip()
    return value if completed.returncode == 0 else "UNKNOWN"


def _wait_until(predicate, *, timeout: float = 10.0, interval: float = 0.05) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class RecordingAuthorizer:
    def __init__(self) -> None:
        self.allow = True
        self.calls: list[dict[str, object]] = []

    def __call__(self, operation: str, fingerprint: str, generation: int) -> bool:
        self.calls.append({
            "operation": operation,
            "fingerprint": fingerprint,
            "generation": generation,
            "allowed": self.allow,
            "at": _iso(),
        })
        return self.allow


class RecordingBackend(SyntheticCoreProcessBackend):
    """Real supervised backend with operation counters for evidence."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.start_calls = 0
        self.stop_calls = 0
        self.observe_calls = 0

    def start(self, **kwargs):
        self.start_calls += 1
        return super().start(**kwargs)

    def stop(self, **kwargs):
        self.stop_calls += 1
        return super().stop(**kwargs)

    def observe(self, **kwargs):
        self.observe_calls += 1
        return super().observe(**kwargs)


class HealthProbe:
    """Disposable Platform-health marker, independent of Core presence."""

    def __init__(self, marker: Path) -> None:
        self.marker = marker
        self.calls = 0

    def __call__(self) -> bool:
        self.calls += 1
        try:
            return self.marker.is_file()
        except OSError:
            return False


def _artifact(wheel: Path, signer: Ed25519PrivateKey) -> CoreComponentArtifact:
    digest = _sha256_file(wheel)
    return CoreComponentArtifact(
        artifact_id=CORE_DISTRIBUTION,
        version="0.1.0",
        sha256=digest,
        signature_b64=base64.b64encode(
            signer.sign(digest.encode("ascii"))
        ).decode(),
        signer_key_id=SIGNER_KEY_ID,
        source="aegis-live-ephemeral",
    )


def _binding_summary(binding) -> dict[str, object] | None:
    if binding is None:
        return None
    return {
        "core_id": binding.core_id,
        "lineage_id": binding.lineage_id,
        "generation": binding.generation,
        "state": binding.state.value,
        "artifact_sha256": binding.artifact_sha256,
        "version": binding.version,
        "last_operation": (
            None if binding.last_operation is None else binding.last_operation.value
        ),
        "last_outcome": (
            None if binding.last_outcome is None else binding.last_outcome.value
        ),
    }


def _receipt_summary(receipt) -> dict[str, object]:
    return {
        "operation": receipt.operation.value,
        "outcome": receipt.outcome.value,
        "generation": receipt.generation,
        "state": receipt.state.value,
        "artifact_sha256": receipt.artifact_sha256,
        "happened_at": receipt.happened_at.isoformat(),
        "platform_healthy": receipt.platform_healthy,
        "detail": receipt.detail,
        "install_receipt_id": (
            None if receipt.install_receipt is None
            else receipt.install_receipt.receipt_id
        ),
        "removal_receipt_id": (
            None if receipt.removal_receipt is None
            else receipt.removal_receipt.removal_id
        ),
        "removal_before_digest": (
            None if receipt.removal_receipt is None
            else receipt.removal_receipt.before_digest
        ),
        "removal_after_digest": (
            None if receipt.removal_receipt is None
            else receipt.removal_receipt.after_digest
        ),
    }


def run_process_stage(work: Path) -> dict[str, object]:
    state = work / "state"
    state.mkdir(parents=True, exist_ok=True)

    wheel = build_component("core", work / "wheels", repo=ROOT)
    signer = Ed25519PrivateKey.generate()
    artifact = _artifact(wheel, signer)
    public_pem = signer.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    verifier = Ed25519ComponentSignatureVerifier({SIGNER_KEY_ID: public_pem})

    marker = state / "platform-health.json"
    marker.write_text(
        json.dumps({"platform": "healthy", "cores_required": 0}),
        encoding="utf-8",
    )
    marker_digest = _sha256_file(marker)
    health = HealthProbe(marker)

    registry = CoreComponentRegistry(state / "core-components.sqlite")
    installer = CoreComponentInstaller(
        registry,
        verifier,
        installation_root=state / "installed-components",
        authorization_check=lambda authority, approval_id, artifact, operation: True,
    )
    backend = RecordingBackend(
        argv=[sys.executable, str(ENTRYPOINT)],
        entrypoint_path=ENTRYPOINT,
        entrypoint_sha256=_sha256_file(ENTRYPOINT),
        working_root=state / "core-work",
        working_directory=state / "core-work" / "runtime",
        environment={"SOFIA_SYNTHETIC_CORE_MODE": "ready"},
        readiness_timeout=15.0,
        stop_timeout=5.0,
    )
    authorizer = RecordingAuthorizer()
    freshness = [True]
    platform_id = str(uuid4())
    core_id = str(uuid4())
    lineage_id = str(uuid4())

    def new_lifecycle() -> SyntheticCoreLifecycle:
        return SyntheticCoreLifecycle(
            store_path=state / "synthetic-core-lifecycle.sqlite",
            platform_id=platform_id,
            installer=installer,
            backend=backend,
            authorization=authorizer,
            freshness=lambda: freshness[0],
            platform_health_check=health,
        )

    lifecycle = new_lifecycle()
    component_root = installer.installation_root / (
        f"core-{artifact.version}-{artifact.sha256}"
    )
    evidence: dict[str, object] = {
        "wheel": str(wheel),
        "wheel_sha256": artifact.sha256,
        "artifact_version": artifact.version,
        "signer_key_id": SIGNER_KEY_ID,
        "signer_keys_ephemeral": True,
        "platform_id": platform_id,
        "core_id": core_id,
        "lineage_id": lineage_id,
        "component_root": str(component_root),
        "platform_marker_sha256": marker_digest,
        "steps": [],
    }

    def step(name: str, **values) -> None:
        evidence["steps"].append({"step": name, "at": _iso(), **values})

    try:
        # Installation through the existing signed component installer.
        installed = lifecycle.install(
            owner_id=OWNER,
            core_id=core_id,
            lineage_id=lineage_id,
            artifact=artifact,
            wheel_path=wheel,
            authority=InstallAuthority.STANDING_POLICY,
        )
        require(component_root.is_dir(), "installed component root exists")
        step(
            "install",
            receipt=_receipt_summary(installed),
            registry_installed=registry.installed(CORE_DISTRIBUTION) is not None,
        )

        # Authorization denial before execution.
        authorizer.allow = False
        denied_start = _expect(
            PermissionError,
            lambda: lifecycle.start(
                owner_id=OWNER, core_id=core_id, expected_generation=0
            ),
        )
        require(backend.start_calls == 0, "denied start invoked no process")
        step("start_denied_before_execution", denial=denied_start,
             backend_start_calls=backend.start_calls)

        # Stale freshness denial before execution.
        authorizer.allow = True
        freshness[0] = False
        stale_start = _expect(
            PermissionError,
            lambda: lifecycle.start(
                owner_id=OWNER, core_id=core_id, expected_generation=0
            ),
        )
        require(backend.start_calls == 0, "stale start invoked no process")
        freshness[0] = True
        step("start_denied_stale_freshness", denial=stale_start,
             backend_start_calls=backend.start_calls)

        # Real supervised subprocess start.
        started = lifecycle.start(
            owner_id=OWNER, core_id=core_id, expected_generation=0
        )
        pid1 = backend.pid_for(core_id)
        generation1 = backend.generation_for(core_id)
        active = lifecycle.store.active_lineage(lineage_id)
        require(started.state is SyntheticCoreState.ACTIVE, "first start active")
        require(started.generation == 1, "first start generation one")
        require(pid1 is not None and pid1 != os.getpid(), "real child PID observed")
        require(generation1 == 1, "backend tracks generation one")
        require(backend.running_pids() == (pid1,), "exactly one running child")
        require(active is not None and active.core_id == core_id,
                "exactly one active lineage writer")
        step(
            "start",
            receipt=_receipt_summary(started),
            pid=pid1,
            generation=generation1,
            running_pids=list(backend.running_pids()),
            active_binding=_binding_summary(active),
            backend_start_calls=backend.start_calls,
        )

        # Duplicate/stale start must not create a second writer.
        duplicate = _expect(
            SyntheticCoreLifecycleConflict,
            lambda: lifecycle.start(
                owner_id=OWNER, core_id=core_id, expected_generation=1
            ),
        )
        require(backend.start_calls == 1, "duplicate start invoked no process")
        require(backend.pid_for(core_id) == pid1, "duplicate start kept one PID")
        step("duplicate_start_denied", denial=duplicate,
             backend_start_calls=backend.start_calls, pid=pid1)

        # STOP authorization flip during execution denies effects.
        authorizer.allow = False
        denied_stop = _expect(
            PermissionError,
            lambda: lifecycle.stop(
                owner_id=OWNER, core_id=core_id, expected_generation=1
            ),
        )
        observed_after_denied_stop = backend.observe(
            core_id=core_id, lineage_id=lineage_id, generation=1
        )
        require(backend.stop_calls == 0, "denied stop invoked no stop")
        require(observed_after_denied_stop is CoreProcessObservation.RUNNING,
                "denied stop left process running")
        step(
            "stop_denied_during_execution",
            denial=denied_stop,
            backend_stop_calls=backend.stop_calls,
            observed=observed_after_denied_stop.value,
            pid=pid1,
        )

        # Force a genuine crash outside the lifecycle state machine.
        os.kill(pid1, signal.SIGTERM)
        require(
            _wait_until(
                lambda: backend.observe(
                    core_id=core_id, lineage_id=lineage_id, generation=1
                ) is CoreProcessObservation.STOPPED,
                timeout=10.0,
            ),
            "crashed child observed stopped",
        )
        crashed_binding = lifecycle.store.binding(OWNER, core_id)
        require(crashed_binding is not None, "crashed binding persists")
        require(crashed_binding.state is SyntheticCoreState.ACTIVE,
                "lifecycle still records the pre-crash ACTIVE state")
        step(
            "forced_crash",
            pid=pid1,
            observed="stopped",
            binding_before_reconcile=_binding_summary(crashed_binding),
        )

        # Truthful reconciliation: stop observes STOPPED and records it.
        authorizer.allow = True
        reconciled_stop = lifecycle.stop(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        require(reconciled_stop.outcome is SyntheticCoreOutcome.SUCCEEDED,
                "reconciled stop succeeded")
        require(reconciled_stop.state is SyntheticCoreState.STOPPED,
                "reconciled stop state")
        require(
            lifecycle.store.binding(OWNER, core_id).state is SyntheticCoreState.STOPPED,
            "binding reconciled to stopped",
        )
        step(
            "reconcile_after_crash",
            receipt=_receipt_summary(reconciled_stop),
            binding=_binding_summary(lifecycle.store.binding(OWNER, core_id)),
            backend_stop_calls=backend.stop_calls,
        )

        # Simulate a Platform restart and advance the generation.
        restarted = new_lifecycle()
        require(restarted.store.binding(OWNER, core_id) is not None,
                "restart reopens durable binding")
        restarted_receipt = restarted.start(
            owner_id=OWNER, core_id=core_id, expected_generation=1
        )
        pid2 = backend.pid_for(core_id)
        generation2 = backend.generation_for(core_id)
        require(restarted_receipt.generation == 2, "restart advanced generation")
        require(pid2 is not None and pid2 != pid1, "restart produced a new PID")
        require(generation2 == 2, "backend tracks generation two")
        require(backend.running_pids() == (pid2,), "one running child after restart")
        require(pid1 != pid2 and pid1 not in backend.running_pids(),
                "crashed PID is not a writer")
        step(
            "restart_generation_advance",
            receipt=_receipt_summary(restarted_receipt),
            previous_pid=pid1,
            pid=pid2,
            generation=generation2,
            running_pids=list(backend.running_pids()),
            active_binding=_binding_summary(
                restarted.store.active_lineage(lineage_id)
            ),
        )

        stopped = restarted.stop(
            owner_id=OWNER, core_id=core_id, expected_generation=2
        )
        require(stopped.state is SyntheticCoreState.STOPPED, "authorized stop state")
        require(restarted_receipt.generation == 2, "stop used generation two")
        require(backend.pid_for(core_id) is None, "stop cleared child PID")
        step("stop", receipt=_receipt_summary(stopped),
             running_pids=list(backend.running_pids()))

        detached = restarted.detach(
            owner_id=OWNER, core_id=core_id, expected_generation=2
        )
        require(detached.state is SyntheticCoreState.DETACHED, "detach state")
        require(component_root.is_dir(), "detach leaves component physically installed")
        require(registry.installed(CORE_DISTRIBUTION) is not None,
                "detach leaves registry receipt")
        step("detach", receipt=_receipt_summary(detached),
             component_root_exists=component_root.is_dir())

        removed = restarted.remove(
            owner_id=OWNER, core_id=core_id, expected_generation=2
        )
        require(removed.outcome is SyntheticCoreOutcome.SUCCEEDED, "remove succeeded")
        require(removed.state is SyntheticCoreState.REMOVED, "remove state")
        require(removed.platform_healthy is True, "remove reports Platform healthy")
        require(not component_root.exists(), "component root physically removed")
        require(registry.installed(CORE_DISTRIBUTION) is None,
                "registry has zero installed Cores")
        require(
            installer.installed_component_root(artifact.version, artifact.sha256)
            is None,
            "component root verification reports absence",
        )
        require(restarted.store.active_lineage(lineage_id) is None,
                "no active lineage after removal")
        require(backend.running_pids() == (), "zero supervised processes")
        require(backend.pid_for(core_id) is None, "no PID after removal")
        require(health() is True, "Platform health callback remains true")
        require(_sha256_file(marker) == marker_digest,
                "Platform health evidence unchanged")
        step(
            "remove_and_zero_cores",
            receipt=_receipt_summary(removed),
            registry_installed=None,
            component_root_exists=component_root.exists(),
            running_pids=list(backend.running_pids()),
            active_lineage=None,
            platform_healthy_after=health(),
            platform_marker_sha256_after=_sha256_file(marker),
            health_calls=health.calls,
        )

        evidence["zero_cores"] = {
            "registry_installed": registry.installed(CORE_DISTRIBUTION),
            "component_root_exists": component_root.exists(),
            "running_pids": list(backend.running_pids()),
            "active_lineage": _binding_summary(
                restarted.store.active_lineage(lineage_id)
            ),
            "binding": _binding_summary(restarted.store.binding(OWNER, core_id)),
            "platform_healthy": health(),
            "platform_marker_sha256": _sha256_file(marker),
        }
        evidence["authorization_calls"] = authorizer.calls
        evidence["backend_counters"] = {
            "start_calls": backend.start_calls,
            "stop_calls": backend.stop_calls,
            "observe_calls": backend.observe_calls,
        }
    finally:
        backend.close()
    return evidence


class RecordingChatClient:
    """Real Ollama client wrapper that records the raw provider response."""

    def __init__(self, client) -> None:
        self._client = client
        self.calls: list[dict[str, object]] = []
        self.raw_response = None

    def chat(self, **kwargs):
        self.calls.append({
            "model": kwargs.get("model"),
            "message_count": len(kwargs.get("messages") or ()),
            "options": kwargs.get("options"),
            "tools_advertised": bool(kwargs.get("tools")),
        })
        response = self._client.chat(**kwargs)
        self.raw_response = response
        return response


def _ollama_model_present(endpoint: str, model: str) -> tuple[bool, list[str]]:
    from ollama import Client

    try:
        tags = Client(host=endpoint, timeout=10).list()
    except Exception as exc:  # noqa: BLE001 - availability evidence
        return False, [f"list_failed:{type(exc).__name__}:{exc}"]
    names = []
    if hasattr(tags, "models"):
        names = [getattr(item, "model", getattr(item, "name", "")) for item in tags.models]
    elif isinstance(tags, dict):
        names = [item.get("model", item.get("name", "")) for item in tags.get("models", [])]
    return model in names, names


def run_inference_stage(
    *, endpoint: str, model: str, output_dir: Path
) -> dict[str, object]:
    from ollama import Client

    present, models = _ollama_model_present(endpoint, model)
    evidence: dict[str, object] = {
        "endpoint": endpoint,
        "requested_model": model,
        "model_already_present": present,
        "observed_models": models,
        "model_downloaded": False,
    }
    if not present:
        evidence["status"] = "BLOCKED_MODEL_ABSENT"
        evidence["blocked_reason"] = (
            "configured model is not already present; the harness never downloads"
        )
        return evidence

    marker = f"AEGIS-LIVE-D4-{uuid4().hex[:12].upper()}"
    prompt = (
        "Output exactly the following token on a single line and nothing "
        f"else. Do not add punctuation or explanation: {marker}"
    )
    configuration_value = ProviderConfiguration(
        provider="ollama", model=model, temperature=0.0, seed=424242,
        context_size=2048, max_output_tokens=48,
    )
    recording = RecordingChatClient(
        Client(host=endpoint, timeout=45.0)
    )
    provider = GenericOllamaProvider(configuration_value, client=recording)
    cognitive_request = CognitiveRequest(
        messages=(CognitiveMessage(role=CognitiveRole.USER, content=prompt),),
        allow_tools=False,
    )
    started = time.perf_counter()
    response = provider.respond(cognitive_request)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    raw = recording.raw_response

    def raw_value(name: str):
        return getattr(raw, name, None) if raw is not None else None

    content = response.content
    evidence.update({
        "status": "OBSERVED",
        "marker_prompt": prompt,
        "marker_expected": marker,
        "provider": "ollama",
        "provider_class": type(provider).__name__,
        "provider_endpoint": endpoint,
        "transport_calls": recording.calls,
        "response_content": content,
        "response_non_empty": bool(content.strip()),
        "marker_present": marker in content,
        "wall_ms": round(elapsed_ms, 3),
        "raw_response": {
            "model": raw_value("model"),
            "done": raw_value("done"),
            "done_reason": raw_value("done_reason"),
            "eval_count": raw_value("eval_count"),
            "prompt_eval_count": raw_value("prompt_eval_count"),
            "total_duration_ns": raw_value("total_duration"),
            "load_duration_ns": raw_value("load_duration"),
            "prompt_eval_duration_ns": raw_value("prompt_eval_duration"),
            "eval_duration_ns": raw_value("eval_duration"),
        },
        "uses_simulated_text": False,
    })
    require(content.strip(), "real model produced non-empty completion")
    require(marker in content, "real model completion contains exact marker",
            {"content": content[:500]})
    require(
        (raw_value("eval_count") or 0) > 0,
        "real model reports generated tokens",
        {"eval_count": raw_value("eval_count")},
    )
    (output_dir / "ollama-live-response.json").write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return evidence


def _scoped_request(value, operation: str, payload: dict, **kwargs):
    base = request(operation, payload, **kwargs)
    return base


def _dispatch(gateway, value, operation: str, payload: dict, fingerprint: str, **kwargs):
    return gateway.dispatch(
        certificate_public_key_sha256=fingerprint,
        request=_scoped_request(value, operation, payload, **kwargs),
    )


def _drain_history(gateway, value, session_id: str) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    cursor = None
    for _page in range(16):
        response = _dispatch(
            gateway, value, "conversation.history",
            {"session_id": session_id, "after": cursor, "limit": 1},
            value.certificate_public_key_sha256,
        )
        require(
            response.status is CoreLinkResponseStatus.COMPLETED,
            "history page completed",
            {"status": response.status.value, "payload": response.payload},
        )
        messages.extend(response.payload["messages"])
        cursor = response.payload.get("next_cursor")
        if cursor is None:
            return messages
    raise ShakedownFailure("history traversal did not terminate")


def _activate_binding(tmp_path: Path, value, *, fingerprint: str):
    binding_root = tmp_path / "client-private"
    binding_root.mkdir(mode=0o700, exist_ok=True)
    binding_store = CoreLinkBindingStore(
        (binding_root / "bindings.json").resolve()
    )
    binding = CoreLinkBinding(
        binding_id="binding:live-shakedown",
        local_platform_id=value.local_platform_id,
        remote_platform_id=value.remote_platform_id,
        remote_core_identity_id=value.remote_core_identity_id,
        remote_core_generation=value.remote_core_generation,
        endpoint_id="endpoint:live-core-link",
        credential_ref="os-keystore:live/core-link",
        trust_anchor_ref=f"sha256:{fingerprint}",
        audience_id=value.principal.audience_id,
        granted_scopes=(
            "core-link.status", "conversation.create", "conversation.select",
            "conversation.send", "conversation.history",
            "conversation.result", "conversation.cancel",
        ),
        protocol_version=ProtocolVersion(1, 0),
        state=CoreLinkBindingState.PENDING_APPROVAL,
        revision=1,
        created_at=NOW,
        updated_at=NOW,
    )
    pending = binding_store.add_pending(binding, expected_store_revision=0)
    verifying = binding_store.transition(
        binding.binding_id, expected_binding_revision=1,
        expected_store_revision=pending.revision,
        state=CoreLinkBindingState.VERIFYING,
        at=NOW + timedelta(milliseconds=1),
    )
    active = binding_store.reconcile_contact(
        binding.binding_id, expected_binding_revision=2,
        expected_store_revision=verifying.revision,
        remote_platform_id=binding.remote_platform_id,
        remote_core_identity_id=binding.remote_core_identity_id,
        remote_core_generation=binding.remote_core_generation,
        endpoint_id=binding.endpoint_id,
        trust_anchor_ref=binding.trust_anchor_ref,
        at=NOW + timedelta(milliseconds=2),
    )
    binding_store.select(
        binding.binding_id, expected_store_revision=active.revision,
    )
    return binding_store, binding


def run_conversation_stage(work: Path) -> dict[str, object]:
    from dataclasses import replace

    from sofia.platform.application import SofiaApplication
    from sofia.platform.distributed.tls import (
        public_key_fingerprint_from_pem_certificate,
    )

    conversation_root = work / "conversation"
    app_root = conversation_root / "app"
    app_root.mkdir(parents=True, exist_ok=True)
    tls_root = conversation_root / "tls"
    tls_root.mkdir(parents=True, exist_ok=True)
    state = app_root / "sofia.db"
    bootstrap_canonical_sqlite(state)

    ca_path, (server_cert, server_key), (client_cert, client_key) = tls_material(
        tls_root
    )
    client_fingerprint = public_key_fingerprint_from_pem_certificate(client_cert)
    server_fingerprint = public_key_fingerprint_from_pem_certificate(server_cert)

    application = SofiaApplication(configuration(app_root))
    application.start()
    server = None
    thread = None
    gateway = None
    extra_gateways: list[object] = []
    evidence: dict[str, object] = {
        "transport": (
            "real loopback mTLS: canonical PinnedCoreLinkClient -> "
            "CoreLinkServer -> CoreLinkConversationGateway"
        ),
        "conversation_llm": (
            "deterministic TestCognitiveEngine (ProviderConfiguration "
            "provider='test'); NOT real model inference"
        ),
        "real_inference_evidence": "separate stage in this same run",
        "durable_state": "disposable canonical SQLite under the temp app root",
        "steps": [],
        "client_fingerprint": client_fingerprint,
        "server_fingerprint": server_fingerprint,
    }

    def step(name: str, **values) -> None:
        evidence["steps"].append({"step": name, "at": _iso(), **values})

    try:
        host_access = replace(
            access(), certificate_public_key_sha256=client_fingerprint,
        )
        access_store = CoreLinkClientAccessStore(state)
        approval = authorize(
            state, capability="core-link.enroll",
            parameters=host_access.parameters(),
        )
        access_store.enroll(host_access, approval_id=approval, now=NOW)
        step("enroll", client_id=host_access.client_id,
             approval_id=approval, fingerprint=client_fingerprint)

        def new_gateway():
            return CoreLinkConversationGateway(
                application, access_store=access_store,
                remote_platform_id="platform:canonical",
                remote_core_identity_id="core:sofia",
                generation_provider=lambda: 7,
                clock=CONVERSATION_CLOCK,
            )

        def start_server(gateway_value):
            server_value = CoreLinkServer(
                CoreLinkServerConfiguration(
                    listen_host="127.0.0.1", listen_port=0,
                    server_certificate=server_cert,
                    server_private_key=server_key,
                    client_ca_file=ca_path,
                    socket_timeout_seconds=20,
                ),
                gateway_value,
            )
            thread_value = threading.Thread(
                target=server_value.serve_forever, daemon=True,
            )
            thread_value.start()
            return server_value, thread_value

        gateway = new_gateway()
        server, thread = start_server(gateway)
        binding_store, binding = _activate_binding(
            conversation_root, host_access, fingerprint=server_fingerprint,
        )
        endpoint = CoreLinkEndpoint(
            binding.endpoint_id, "localhost", server.address[1],
        )
        client = PinnedCoreLinkClient(
            binding_store,
            endpoint_resolver=lambda endpoint_id: (
                endpoint if endpoint_id == endpoint.endpoint_id else None
            ),
            credential_resolver=lambda credential_ref: CoreLinkTLSCredentials(
                ca_path, client_cert, client_key,
            ),
            timeout_seconds=20,
        )
        step("server_start", address=list(server.address),
             binding_id=binding.binding_id,
             trust_anchor_ref=binding.trust_anchor_ref)

        create_request = request(
            "conversation.create", {}, idempotency_key="session:live-shakedown",
        )
        created = client.request(create_request)
        require(created.status is CoreLinkResponseStatus.COMPLETED,
                "create completed", created.payload)
        session_id = created.payload["session_id"]
        step("create_session", session_id=session_id,
             status=created.status.value)

        first_request = request(
            "conversation.send",
            {"session_id": session_id, "content": "Live harness turn one",
             "client_created_at": NOW.isoformat()},
            idempotency_key="turn:live:1",
        )
        first = client.request(first_request)
        require(first.status is CoreLinkResponseStatus.COMPLETED,
                "first turn completed", first.payload)
        step("turn_1", content=first.payload["content"],
             receipt=first.payload.get("receipt"),
             status=first.status.value)

        second = client.request(request(
            "conversation.send",
            {"session_id": session_id, "content": "Live harness turn two",
             "client_created_at": NOW.isoformat()},
            idempotency_key="turn:live:2",
        ))
        require(second.status is CoreLinkResponseStatus.COMPLETED,
                "second turn completed", second.payload)
        step("turn_2", content=second.payload["content"],
             status=second.status.value)

        duplicate = client.request(first_request)
        require(duplicate.status is CoreLinkResponseStatus.COMPLETED,
                "duplicate request completed", duplicate.payload)
        require(duplicate.payload["content"] == first.payload["content"],
                "duplicate request returned identical content")
        require(
            duplicate.payload.get("receipt", {}).get("replayed") is True,
            "duplicate request is marked replayed",
            duplicate.payload.get("receipt"),
        )
        step("duplicate_request_id", content=duplicate.payload["content"],
             receipt=duplicate.payload.get("receipt"))

        history_before = _drain_history(gateway, host_access, session_id)
        require(
            [item["role"] for item in history_before]
            == ["user", "assistant", "user", "assistant"],
            "durable history has two complete turns",
            history_before,
        )
        step("history_before_restart", messages=history_before)

        # Restart the host gateway and server, then reconnect the canonical
        # client.  History and the create idempotency decision are durable.
        server.close()
        thread.join(timeout=5)
        gateway = new_gateway()
        server, thread = start_server(gateway)
        endpoint = CoreLinkEndpoint(
            binding.endpoint_id, "localhost", server.address[1],
        )
        client = PinnedCoreLinkClient(
            binding_store,
            endpoint_resolver=lambda endpoint_id: (
                endpoint if endpoint_id == endpoint.endpoint_id else None
            ),
            credential_resolver=lambda credential_ref: CoreLinkTLSCredentials(
                ca_path, client_cert, client_key,
            ),
            timeout_seconds=20,
        )
        replay_create = client.request(create_request)
        require(replay_create.status is CoreLinkResponseStatus.COMPLETED,
                "create replay after restart completed", replay_create.payload)
        require(replay_create.payload["session_id"] == session_id,
                "create replay after restart returned same session")
        history_after = _drain_history(gateway, host_access, session_id)
        require(history_after == history_before,
                "durable history survives host restart", history_after)
        step(
            "restart_reconnect",
            address=list(server.address),
            session_id=session_id,
            history_after=history_after,
            create_replay_session=replay_create.payload["session_id"],
        )

        # Client-side bounded timeout against the live server.
        timeout_client = PinnedCoreLinkClient(
            binding_store,
            endpoint_resolver=lambda endpoint_id: (
                endpoint if endpoint_id == endpoint.endpoint_id else None
            ),
            credential_resolver=lambda credential_ref: CoreLinkTLSCredentials(
                ca_path, client_cert, client_key,
            ),
            timeout_seconds=0.001,
        )
        started = time.perf_counter()
        timeout_error = _expect(
            CoreLinkTransportError,
            lambda: timeout_client.request(request("status", {})),
        )
        timeout_ms = (time.perf_counter() - started) * 1000.0
        step("client_timeout", error=timeout_error, elapsed_ms=round(timeout_ms, 3))

        # Cancellation of an already-admitted processing turn is truthful:
        # it reports OUTCOME_UNKNOWN and never claims cancellation.
        processing_key = "turn:live:processing"
        processing_event = gateway._event_id(host_access, processing_key)
        LifelongThreadStore(state).admit_turn(
            event_id=processing_event,
            principal=host_access.principal,
            session_id=session_id,
            channel="core-link",
            content="Admitted but still processing",
            runtime_id="conversation-runtime:live-harness",
            now=NOW + timedelta(milliseconds=500),
            source_device_id=host_access.client_id,
            client_created_at=NOW,
        )
        cancelled = client.request(request(
            "conversation.cancel", {"idempotency_key": processing_key},
        ))
        require(cancelled.status is CoreLinkResponseStatus.OUTCOME_UNKNOWN,
                "processing cancellation stays truthful",
                {"status": cancelled.status.value, "payload": cancelled.payload})
        step("cancellation_processing", status=cancelled.status.value,
             payload=cancelled.payload)

        # Provider/service unavailability must be reported, never invented.
        class UnavailableApplication:
            def open_channel_conversation(self, *, session_id=None):
                raise RuntimeError("disposable conversation service is offline")

        unavailable_gateway = CoreLinkConversationGateway(
            UnavailableApplication(), access_store=access_store,
            remote_platform_id="platform:canonical",
            remote_core_identity_id="core:sofia",
            generation_provider=lambda: 7,
            clock=CONVERSATION_CLOCK,
        )
        extra_gateways.append(unavailable_gateway)
        unavailable = _dispatch(
            unavailable_gateway, host_access, "conversation.create", {},
            client_fingerprint, idempotency_key="session:unavailable",
        )
        require(unavailable.status is CoreLinkResponseStatus.UNAVAILABLE,
                "unavailable service reported truthfully",
                {"status": unavailable.status.value, "payload": unavailable.payload})
        step("provider_unavailable", status=unavailable.status.value,
             payload=unavailable.payload)

        # Operator STOP: diagnostic status remains available, effects denied.
        stop_store = OperatorStopStore(state)
        stop_store.set(
            active=True, updated_by="Sparks",
            reason="live shakedown operator stop",
            at=NOW + timedelta(seconds=5),
        )
        stopped_status = client.request(request("status", {}))
        require(stopped_status.status is CoreLinkResponseStatus.COMPLETED,
                "diagnostic status survives STOP", stopped_status.payload)
        require(stopped_status.payload.get("operator_stop_active") is True,
                "status reports STOP active", stopped_status.payload)
        stop_denied = client.request(request(
            "conversation.send",
            {"session_id": session_id, "content": "Must not be delivered",
             "client_created_at": NOW.isoformat()},
            idempotency_key="turn:live:stopped",
        ))
        require(stop_denied.status is CoreLinkResponseStatus.DENIED,
                "STOP denies conversation effects",
                {"status": stop_denied.status.value, "payload": stop_denied.payload})
        step("operator_stop", status=stopped_status.payload,
             denied_status=stop_denied.status.value,
             denied_payload=stop_denied.payload)

        # Lift STOP through the canonical signed owner resume path.
        resume_with_signed_owner_proof(
            stop_store, reason="live shakedown resume",
            now=NOW + timedelta(seconds=6),
        )
        resumed = client.request(request(
            "conversation.send",
            {"session_id": session_id, "content": "Delivered after signed resume",
             "client_created_at": NOW.isoformat()},
            idempotency_key="turn:live:resumed",
        ))
        require(resumed.status is CoreLinkResponseStatus.COMPLETED,
                "signed resume restores authorized effects",
                {"status": resumed.status.value, "payload": resumed.payload})
        step("signed_resume", status=resumed.status.value,
             content=resumed.payload.get("content"))

        # Revocation flips access off immediately; client gets DENIED.
        revoke_approval = authorize(
            state, capability="core-link.revoke",
            parameters={
                "client_id": host_access.client_id, "expected_revision": 1,
            },
            now=NOW + timedelta(seconds=2),
        )
        revoked = access_store.revoke(
            host_access.client_id, expected_revision=1,
            approval_id=revoke_approval, now=NOW + timedelta(seconds=2),
        )
        revoke_denied = client.request(request(
            "conversation.send",
            {"session_id": session_id, "content": "Must not be delivered after revoke",
             "client_created_at": NOW.isoformat()},
            idempotency_key="turn:live:revoked",
        ))
        require(revoke_denied.status is CoreLinkResponseStatus.DENIED,
                "revocation denies conversation effects",
                {"status": revoke_denied.status.value,
                 "payload": revoke_denied.payload})
        step("revocation", revoked_at=revoked.revoked_at.isoformat(),
             denied_status=revoke_denied.status.value,
             denied_payload=revoke_denied.payload)

        evidence["session_id"] = session_id
        evidence["history_final"] = history_after
        evidence["durable_turns"] = len(history_after)
    finally:
        if server is not None:
            server.close()
        if thread is not None:
            thread.join(timeout=5)
        for extra in extra_gateways:
            try:
                extra.close()
            except Exception:
                pass
        if gateway is not None and server is None:
            gateway.close()
        application.shutdown()
    return evidence


def build_evidence(args) -> dict[str, object]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work = Path(tempfile.mkdtemp(prefix="aegis-live-shakedown-"))
    output_dir = Path(args.output_dir) if args.output_dir else work / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, object] = {
        "schema": SCHEMA,
        "generated_at": _iso(),
        "source_sha": _git_sha(),
        "python": sys.version,
        "platform": sys.platform,
        "work_root": str(work),
        "output_dir": str(output_dir),
        "claims": {
            "installed_service_claimed": False,
            "real_sofia_identity_or_memory_used": False,
            "real_artemis_or_venus_used": False,
            "model_downloaded": False,
            "synthetic_core_process": (
                "real OS subprocess launched from the disposable entrypoint "
                "fixture by SyntheticCoreProcessBackend"
            ),
            "installed_component": (
                "signed Core wheel built from this checkout, physically "
                "installed into a temp venv and physically removed"
            ),
            "real_inference": (
                "canonical GenericOllamaProvider against local loopback Ollama"
            ),
            "core_link_transport": (
                "real loopback mTLS: PinnedCoreLinkClient -> CoreLinkServer"
            ),
            "conversation_llm": (
                "deterministic TestCognitiveEngine (provider='test'); NOT real "
                "inference"
            ),
        },
        "blocked": [
            "No installed Windows service/systemd unit was created or claimed.",
            "No real Artemis or Venus host was contacted; loopback only.",
            "No production Sofia personal identity or memory store was used; "
            "disposable temp SQLite and read-only canonical repo assets only.",
            "The supervised subprocess is the disposable synthetic entrypoint, "
            "not the installed Core wheel's production runtime.",
            "Core Link conversation used a deterministic test LLM, not real "
            "model inference; real inference was evidenced separately.",
            "No model download was attempted; the configured model had to "
            "already exist on the local Ollama server.",
        ],
        "stages": {},
    }
    try:
        evidence["stages"]["synthetic_core_process"] = run_process_stage(work)
        evidence["stages"]["real_inference"] = run_inference_stage(
            endpoint=args.endpoint, model=args.model, output_dir=output_dir,
        )
        evidence["stages"]["core_link_conversation"] = run_conversation_stage(
            work
        )
        evidence["status"] = "PASSED"
    except BaseException as exc:  # noqa: BLE001 - evidence must survive
        evidence["status"] = "FAILED"
        evidence["error"] = {
            "type": type(exc).__name__,
            "message": str(exc)[:2000],
            "traceback": traceback.format_exc()[-8000:],
        }
    finally:
        if not args.keep_work:
            shutil.rmtree(work, ignore_errors=True)
    evidence["output_json"] = str(output_dir / "evidence.json")
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument(
        "--output-dir", default=None,
        help="Evidence directory (default: temp work dir, automatically kept).",
    )
    parser.add_argument(
        "--keep-work", action="store_true",
        help="Keep the disposable temp work root for inspection.",
    )
    args = parser.parse_args(argv)
    evidence = build_evidence(args)
    if args.output_dir:
        output = Path(args.output_dir) / "evidence.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        evidence["output_json"] = str(output)
    else:
        # The work dir was removed; persist to a stable temp path instead.
        output = Path(tempfile.gettempdir()) / (
            "aegis-live-shakedown-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + ".json"
        )
        evidence["output_json"] = str(output)
        output.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({
        "status": evidence.get("status"),
        "output_json": evidence.get("output_json"),
        "source_sha": evidence.get("source_sha"),
        "error": evidence.get("error"),
    }, indent=2, sort_keys=True))
    return 0 if evidence.get("status") == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
