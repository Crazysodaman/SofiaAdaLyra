"""Strict Core autostart mutation client framing and pinned native transport."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
import socket
import sys
from threading import Event, Thread
from uuid import uuid4

import pytest

from sofia.platform.run.core_autostart import (
    CoreAutostartPolicyStore, CoreStartupReconciler,
)
from sofia.platform.run.management_mutation import (
    MANAGEMENT_MUTATION_CAPABILITY, ManagementMutationDispatcher,
    core_autostart_mutation_registry,
)
from sofia.platform.run.management_mutation_store import (
    ManagementMutationReceiptStore,
)
from sofia.platform.run.management_windows_pipe import (
    ManagementWindowsPipeListener,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.sdk.platform_management_mutation import (
    MANAGEMENT_MUTATION_PROTOCOL, MANAGEMENT_MUTATION_SCHEMA,
    UntrustedManagementMutation, make_mutation_response,
    mutation_approval_parameters, mutation_fingerprint,
)
from sofia.sdk.platform_management_mutation_client import (
    CORE_AUTOSTART_DISABLE_OPERATION, CORE_AUTOSTART_ENABLE_OPERATION,
    CORE_AUTOSTART_SCOPE, ManagementMutationAmbiguous,
    build_core_autostart_mutation, mutate_linux_management,
    mutate_windows_management,
)
from sofia.sdk.platform_management_windows_client import (
    windows_management_pipe_name,
)
from test.owner_auth_fixture import record_verified_owner_approval

PLATFORM_ID = str(uuid4())
GENERATION = 3
CORE_ID = str(uuid4())
APPROVAL_ID = "approval:one-use"


def _build(**changes):
    values = {
        "platform_id": PLATFORM_ID,
        "generation": GENERATION,
        "operation": CORE_AUTOSTART_ENABLE_OPERATION,
        "core_id": CORE_ID,
        "expected_policy_revision": 1,
        "enabled": True,
        "approval_id": APPROVAL_ID,
        "expected_mutation_revision": 0,
    }
    values.update(changes)
    return build_core_autostart_mutation(**values)


def _document_and_wire(request):
    return request.request.to_payload(), request.wire


def _dispatch(mode: str, observed: list):
    def dispatch(raw, *, authenticated_peer, now):
        request = UntrustedManagementMutation.parse(raw, now=now)
        observed.append((request, authenticated_peer))
        if mode == "DENIED":
            return make_mutation_response(
                request, outcome="DENIED", receipt_id="mutreceipt:denied",
                current_generation=request.expected_generation,
                current_revision=0, observed_at=now,
                error_code="STOPPED", detail="operator STOP",
            )
        if mode == "FAILED":
            return make_mutation_response(
                request, outcome="FAILED", receipt_id="mutreceipt:failed",
                current_generation=request.expected_generation,
                current_revision=0, observed_at=now,
                error_code="HANDLER_FAILED", detail="pre-effect failure",
            )
        if mode == "UNKNOWN":
            return make_mutation_response(
                request, outcome="OUTCOME_UNKNOWN",
                receipt_id="mutreceipt:unknown",
                current_generation=request.expected_generation,
                current_revision=1, observed_at=now,
                error_code="HANDLER_FAILED_UNKNOWN",
                detail="effect state is unknown",
            )
        if mode == "MALFORMED":
            body = make_mutation_response(
                request, outcome="SUCCEEDED", receipt_id="mutreceipt:test",
                current_generation=request.expected_generation,
                current_revision=1, observed_at=now,
            )
            body["unreviewed"] = True
            return body
        return make_mutation_response(
            request, outcome="SUCCEEDED", receipt_id="mutreceipt:success",
            current_generation=request.expected_generation,
            current_revision=1, observed_at=now,
        )
    return dispatch


def _call_windows(name, **changes):
    values = {
        "pipe_name": name,
        "expected_platform_id": PLATFORM_ID,
        "expected_generation": GENERATION,
        "operation": CORE_AUTOSTART_ENABLE_OPERATION,
        "core_id": CORE_ID,
        "expected_policy_revision": 1,
        "enabled": True,
        "approval_id": APPROVAL_ID,
        "expected_mutation_revision": 0,
        "wait_seconds": 2,
    }
    values.update(changes)
    return mutate_windows_management(**values)


@contextmanager
def _windows_service(mode: str = "OK"):
    observed: list = []
    name = windows_management_pipe_name(
        platform_id=PLATFORM_ID, generation=GENERATION,
    )
    stop = Event()
    with ManagementWindowsPipeListener(
        name, dispatch=_dispatch(mode, observed),
    ) as server:
        worker = Thread(target=server.serve_until, args=(stop,), daemon=True)
        worker.start()
        try:
            yield name, observed
        finally:
            stop.set()
            worker.join(timeout=4)


@pytest.mark.skipif(os.name != "nt", reason="Win32 named-pipe IPC")
def test_request_framing_is_exact_strict_and_correlated():
    with _windows_service() as (name, observed):
        response = _call_windows(name)

    assert response.outcome == "SUCCEEDED"
    assert response.receipt_id == "mutreceipt:success"
    assert response.current_revision == 1
    assert len(observed) == 1
    request, peer = observed[0]
    assert peer.startswith("windows:sid:S-1-5-")
    assert request.schema == MANAGEMENT_MUTATION_SCHEMA
    assert request.protocol_version == MANAGEMENT_MUTATION_PROTOCOL
    assert request.operation == CORE_AUTOSTART_ENABLE_OPERATION
    assert request.operation_scope == CORE_AUTOSTART_SCOPE
    assert request.target_platform_id == PLATFORM_ID
    assert request.expected_generation == GENERATION
    assert request.expected_revision == 0
    assert request.approval_id == APPROVAL_ID
    assert request.payload == {
        "core_id": CORE_ID,
        "expected_revision": 1,
        "enabled": True,
    }
    assert request.idempotency_key.startswith("idempotency:")
    assert request.request_id.startswith("request:")


@pytest.mark.skipif(os.name != "nt", reason="Win32 named-pipe IPC")
@pytest.mark.parametrize(
    ("mode", "outcome", "error_code", "revision"),
    [
        ("DENIED", "DENIED", "STOPPED", 0),
        ("FAILED", "FAILED", "HANDLER_FAILED", 0),
        ("UNKNOWN", "OUTCOME_UNKNOWN", "HANDLER_FAILED_UNKNOWN", 1),
    ],
)
def test_typed_non_success_receipts_are_returned_verbatim(
    mode, outcome, error_code, revision,
):
    with _windows_service(mode) as (name, observed):
        response = _call_windows(name)
    assert response.outcome == outcome
    assert response.error_code == error_code
    assert response.current_revision == revision
    assert len(observed) == 1


@pytest.mark.skipif(os.name != "nt", reason="Win32 named-pipe IPC")
def test_malformed_response_is_ambiguous_and_never_retried():
    with _windows_service("MALFORMED") as (name, observed):
        with pytest.raises(ManagementMutationAmbiguous):
            _call_windows(name)
        assert len(observed) == 1


@pytest.mark.skipif(os.name != "nt", reason="Win32 named-pipe IPC")
def test_wrong_platform_pin_fails_before_connect():
    other = windows_management_pipe_name(
        platform_id=str(uuid4()), generation=GENERATION,
    )
    with pytest.raises(PermissionError, match="pinned"):
        _call_windows(other)


@pytest.mark.skipif(os.name != "nt", reason="Win32 named-pipe IPC")
def test_disable_framing_carries_enabled_false():
    with _windows_service() as (name, observed):
        response = _call_windows(
            name,
            operation=CORE_AUTOSTART_DISABLE_OPERATION,
            expected_policy_revision=2,
            enabled=False,
            expected_mutation_revision=1,
        )
    assert response.outcome == "SUCCEEDED"
    request = observed[0][0]
    assert request.operation == CORE_AUTOSTART_DISABLE_OPERATION
    assert request.expected_revision == 1
    assert request.payload == {
        "core_id": CORE_ID,
        "expected_revision": 2,
        "enabled": False,
    }


def test_build_requires_caller_supplied_approval_and_exact_targets():
    with pytest.raises(TypeError):
        build_core_autostart_mutation(
            platform_id=PLATFORM_ID, generation=GENERATION,
            operation=CORE_AUTOSTART_ENABLE_OPERATION, core_id=CORE_ID,
            expected_policy_revision=1, enabled=True,
            expected_mutation_revision=0,
        )
    for changes in (
        {"approval_id": ""},
        {"approval_id": "OWNER"},
        {"core_id": "not-a-uuid"},
        {"core_id": CORE_ID.upper()},
        {"expected_policy_revision": 0},
        {"expected_mutation_revision": -1},
        {"generation": 0},
        {"operation": "core.autostart.remove"},
        {"enabled": False},
    ):
        with pytest.raises((TypeError, ValueError)):
            _build(**changes)


def test_derived_idempotency_key_is_stable_and_semantic():
    first = _build()
    second = _build()
    assert first.request.idempotency_key == second.request.idempotency_key
    assert first.request.request_id != second.request.request_id
    other = _build(expected_policy_revision=2, expected_mutation_revision=1)
    assert other.request.idempotency_key != first.request.idempotency_key
    payload, wire = _document_and_wire(first)
    assert set(payload) == {
        "schema", "protocol_version", "request_id", "correlation_id",
        "idempotency_key", "target_platform_id", "operation",
        "operation_scope", "expected_generation", "expected_revision",
        "deadline", "approval_id", "payload",
    }
    assert json.loads(wire) == payload
    assert first.request.approval_id == APPROVAL_ID


@pytest.mark.skipif(
    sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"),
    reason="Linux kernel peer listener",
)
def test_linux_request_framing_against_pinned_unix_listener(tmp_path):
    from sofia.platform.run.management_unix_listener import (
        ManagementUnixListener,
    )

    observed: list = []
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    now = datetime.now(timezone.utc)
    with ManagementUnixListener(
        private / "management.sock", dispatch=_dispatch("OK", observed),
    ) as listener:
        response = mutate_linux_management(
            socket_path=listener.path,
            expected_platform_id=PLATFORM_ID,
            expected_generation=GENERATION,
            operation=CORE_AUTOSTART_ENABLE_OPERATION,
            core_id=CORE_ID,
            expected_policy_revision=1,
            enabled=True,
            approval_id=APPROVAL_ID,
            expected_mutation_revision=0,
            installed_service_uid=os.getuid(),
            installed_service_gid=os.getgid(),
            installed_service_pid=os.getpid(),
            now=now,
        )
    assert response.outcome == "SUCCEEDED"
    request = observed[0][0]
    assert request.payload == {
        "core_id": CORE_ID,
        "expected_revision": 1,
        "enabled": True,
    }
    assert request.approval_id == APPROVAL_ID


@pytest.mark.skipif(os.name != "nt", reason="Win32 named-pipe IPC")
def test_approved_real_dispatcher_writes_one_policy_receipt(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "platform.db")
    store = CoreAutostartPolicyStore(
        state, verify_approval=lambda **_kwargs: False,
    )
    reconciler = CoreStartupReconciler(
        store=store,
        start_core=lambda *_args: "STOPPED",
        observe_core=lambda *_args: "STOPPED",
        installed_core_ids=lambda: (CORE_ID,),
        is_stopped=lambda: False,
        is_authorized=lambda _policy: True,
    )
    stop = OperatorStopStore(state)
    dispatcher = ManagementMutationDispatcher(
        current_status=lambda: {
            "platform_id": PLATFORM_ID,
            "generation": GENERATION,
            "operator_stop": stop.current().active,
        },
        registry=core_autostart_mutation_registry(reconciler),
        approvals=ExecutionApprovalVerifier(state),
        receipts=ManagementMutationReceiptStore(state),
        clock=lambda: datetime.now(timezone.utc),
    )
    captured: dict = {}

    def dispatch(raw, *, authenticated_peer, now):
        request = UntrustedManagementMutation.parse(raw, now=now)
        captured["request"] = request
        captured["peer"] = authenticated_peer
        approval = ExecutionApproval(
            approval_id=request.approval_id,
            capability=MANAGEMENT_MUTATION_CAPABILITY,
            request_fingerprint=execution_fingerprint(
                MANAGEMENT_MUTATION_CAPABILITY,
                mutation_approval_parameters(request, authenticated_peer),
            ),
            approved_by="Sparks",
            approved_at=now - timedelta(seconds=1),
            expires_at=now + timedelta(minutes=5),
        )
        record_verified_owner_approval(ExecutionApprovalVerifier(state), approval)
        return dispatcher.dispatch(
            raw, authenticated_peer=authenticated_peer, now=now,
        )

    name = windows_management_pipe_name(
        platform_id=PLATFORM_ID, generation=GENERATION,
    )
    done = Event()
    with ManagementWindowsPipeListener(name, dispatch=dispatch) as server:
        worker = Thread(target=server.serve_until, args=(done,), daemon=True)
        worker.start()
        try:
            response = _call_windows(name)
        finally:
            done.set()
            worker.join(timeout=4)

    assert response.outcome == "SUCCEEDED"
    assert response.error_code is None
    assert response.current_generation == GENERATION
    assert response.current_revision == 1
    policy = store.policy(CORE_ID)
    assert policy is not None
    assert policy.enabled is True
    assert policy.approved_revision == 1
    assert policy.approval_fingerprint == mutation_fingerprint(
        captured["request"], captured["peer"],
    )


@pytest.mark.skipif(
    sys.platform != "linux" or not hasattr(socket, "SO_PEERCRED"),
    reason="Linux kernel peer listener",
)
def test_linux_wrong_service_pid_denied_before_request(tmp_path):
    from sofia.platform.run.management_unix_listener import (
        ManagementUnixListener,
    )

    observed: list = []
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    with ManagementUnixListener(
        private / "management.sock", dispatch=_dispatch("OK", observed),
    ) as listener:
        with pytest.raises(PermissionError, match="OS identity"):
            mutate_linux_management(
                socket_path=listener.path,
                expected_platform_id=PLATFORM_ID,
                expected_generation=GENERATION,
                operation=CORE_AUTOSTART_ENABLE_OPERATION,
                core_id=CORE_ID,
                expected_policy_revision=1,
                enabled=True,
                approval_id=APPROVAL_ID,
                expected_mutation_revision=0,
                installed_service_uid=os.getuid(),
                installed_service_gid=os.getgid(),
                installed_service_pid=os.getpid() + 10000,
            )
    assert observed == []
