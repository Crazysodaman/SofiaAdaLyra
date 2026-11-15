"""Canonical versioned MUTATING management API: SAFE, fencing and transport."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
from threading import Event, Thread
from time import sleep
from uuid import uuid4

import pytest

from sofia.platform.run.library_read_dispatch import (
    LibraryReadDispatcher, LocalReadMultiplexer,
)
from sofia.platform.run.management_mutation import (
    MANAGEMENT_MUTATION_CAPABILITY, MutationFailed, MutationInvocation,
    MutationOperation, MutationRegistry, ManagementMutationDispatcher,
    operator_stop_mutation_registry,
)
from sofia.platform.run.management_mutation_store import (
    ManagementMutationReceiptStore,
)
from sofia.platform.run.management_unix_listener import ManagementUnixListener
from sofia.platform.run.management_windows_pipe import ManagementWindowsPipeListener
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.sdk.platform_management_mutation import (
    MANAGEMENT_MUTATION_PROTOCOL, MANAGEMENT_MUTATION_SCHEMA,
    UntrustedManagementMutation, UntrustedManagementMutationResponse,
    mutation_approval_parameters,
)
from test.owner_auth_fixture import record_verified_owner_approval

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
PLATFORM = "platform:alpha"
PEER = "unix:uid:1000:gid:1000"
TEST_OPERATION = "platform.test.mutate"


def state_path(tmp_path: Path) -> Path:
    return bootstrap_canonical_sqlite(tmp_path / "platform.db")


def request_document(**changes):
    document = {
        "schema": MANAGEMENT_MUTATION_SCHEMA,
        "protocol_version": MANAGEMENT_MUTATION_PROTOCOL,
        "request_id": "request:1",
        "correlation_id": "correlation:1",
        "idempotency_key": "idempotency:1",
        "target_platform_id": PLATFORM,
        "operation": TEST_OPERATION,
        "operation_scope": "test",
        "expected_generation": 3,
        "expected_revision": 0,
        "deadline": (NOW + timedelta(seconds=5)).isoformat().replace(
            "+00:00", "Z"
        ),
        "approval_id": "approval:pending",
        "payload": {"value": "exact"},
    }
    document.update(changes)
    return document


def raw_request(**changes) -> bytes:
    return json.dumps(
        request_document(**changes), separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def typed_request(**changes) -> UntrustedManagementMutation:
    return UntrustedManagementMutation.from_payload(
        request_document(**changes), now=NOW,
    )


def status(operator_stop: bool = False, generation: int = 3):
    return {
        "platform_id": PLATFORM, "generation": generation,
        "operator_stop": operator_stop,
    }


def approve(
    approvals: ExecutionApprovalVerifier,
    document: dict,
    peer: str,
    *,
    approved_at: datetime = NOW,
    expires_at: datetime | None = None,
    approval_id: str | None = None,
    now: datetime = NOW,
) -> str:
    typed = UntrustedManagementMutation.from_payload(document, now=now)
    fingerprint = execution_fingerprint(
        MANAGEMENT_MUTATION_CAPABILITY,
        mutation_approval_parameters(typed, peer),
    )
    identifier = approval_id or ("approval:" + uuid4().hex)
    approval = ExecutionApproval(
        approval_id=identifier,
        capability=MANAGEMENT_MUTATION_CAPABILITY,
        request_fingerprint=fingerprint,
        approved_by="Sparks",
        approved_at=approved_at,
        expires_at=expires_at or (approved_at + timedelta(minutes=5)),
    )
    record_verified_owner_approval(approvals, approval)
    return identifier


def recording_registry(calls: list, *, failure: str | None = None) -> MutationRegistry:
    def handler(invocation: MutationInvocation) -> None:
        calls.append(invocation.request.payload)
        if failure == "raise":
            raise RuntimeError("simulated handler crash")
        if failure == "failed":
            raise MutationFailed("simulated pre-effect refusal")

    return MutationRegistry((
        MutationOperation(
            name=TEST_OPERATION,
            scopes=frozenset({"test"}),
            handler=handler,
        ),
    ))


def compose(
    state: Path, registry: MutationRegistry, *, current_status=None,
    authorize_peer=None, clock=None,
) -> tuple[ManagementMutationDispatcher, ExecutionApprovalVerifier,
           ManagementMutationReceiptStore]:
    approvals = ExecutionApprovalVerifier(state)
    receipts = ManagementMutationReceiptStore(state)
    dispatcher = ManagementMutationDispatcher(
        current_status=current_status or (lambda: status()),
        registry=registry,
        approvals=approvals,
        receipts=receipts,
        authorize_peer=authorize_peer,
        clock=clock or (lambda: NOW),
    )
    return dispatcher, approvals, receipts


def approved_request(
    approvals: ExecutionApprovalVerifier,
    *,
    peer: str = PEER,
    now: datetime = NOW,
    **changes,
) -> bytes:
    document = request_document(**changes)
    document["approval_id"] = approve(
        approvals, document, peer, now=now,
        approved_at=now - timedelta(seconds=1),
        expires_at=now + timedelta(minutes=5),
    )
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


def parse_reply(raw: bytes, *, expected: UntrustedManagementMutation) -> UntrustedManagementMutationResponse:
    return UntrustedManagementMutationResponse.parse(
        raw, expected=expected, now=NOW,
    )


def test_authorized_mutation_activates_canonical_operator_stop(tmp_path):
    state = state_path(tmp_path)
    stop = OperatorStopStore(state)
    approvals = ExecutionApprovalVerifier(state)
    receipts = ManagementMutationReceiptStore(state)
    dispatcher = ManagementMutationDispatcher(
        current_status=lambda: status(operator_stop=stop.current().active),
        registry=operator_stop_mutation_registry(stop),
        approvals=approvals,
        receipts=receipts,
        clock=lambda: NOW,
    )
    document = request_document(
        operation="platform.operator.stop.activate",
        operation_scope="operator",
        payload={"reason": "owner requested immediate stop"},
    )
    document["approval_id"] = approve(approvals, document, PEER)
    expected = UntrustedManagementMutation.from_payload(document, now=NOW)
    reply = dispatcher.dispatch(
        json.dumps(document, separators=(",", ":")).encode("utf-8"),
        authenticated_peer=PEER, now=NOW,
    )
    parsed = parse_reply(
        json.dumps(reply, separators=(",", ":")).encode("utf-8"),
        expected=expected,
    )
    assert parsed.outcome == "SUCCEEDED"
    assert parsed.error_code is None
    assert parsed.current_revision == 1
    assert stop.current().active is True
    assert receipts.current_revision() == 1


def test_wrong_peer_cannot_spend_another_peers_approval(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals, peer=PEER)
    reply = dispatcher.dispatch(
        raw, authenticated_peer="unix:uid:2000:gid:2000", now=NOW,
    )
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "APPROVAL_MISMATCH"
    assert calls == []


def test_missing_approval_is_denied_before_handler(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, _, _ = compose(state, recording_registry(calls))
    reply = dispatcher.dispatch(raw_request(), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "APPROVAL_MISSING"
    assert calls == []


def test_expired_approval_is_denied_before_handler(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    document = request_document()
    document["approval_id"] = approve(
        approvals, document, PEER,
        approved_at=NOW - timedelta(minutes=10),
        expires_at=NOW - timedelta(minutes=5),
    )
    reply = dispatcher.dispatch(
        json.dumps(document, separators=(",", ":")).encode("utf-8"),
        authenticated_peer=PEER, now=NOW,
    )
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "APPROVAL_EXPIRED"
    assert calls == []


def test_revoked_owner_credential_denies_approval(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals)
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=?",
            (NOW.isoformat(),),
        )
        db.commit()
    reply = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] in {"APPROVAL_UNVERIFIED", "APPROVAL_REVOKED"}
    assert calls == []


def test_stop_denies_mutation_before_approval_consumption(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(
        state, recording_registry(calls), current_status=lambda: status(True),
    )
    raw = approved_request(approvals)
    request = UntrustedManagementMutation.parse(raw, now=NOW)
    reply = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "STOPPED"
    assert calls == []
    assert approvals.matches_unconsumed(
        approval_id=request.approval_id,
        capability=MANAGEMENT_MUTATION_CAPABILITY,
        parameters=mutation_approval_parameters(request, PEER),
        now=NOW,
    )


@pytest.mark.parametrize("changes,expected", [
    ({"expected_generation": 2}, "STALE_GENERATION"),
    ({"expected_revision": 4}, "STALE_REVISION"),
    ({"target_platform_id": "platform:beta"}, "TARGET_MISMATCH"),
])
def test_stale_identity_generation_and_revision_are_denied(
    tmp_path, changes, expected,
):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals, **changes)
    reply = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == expected
    assert calls == []


def test_unknown_operation_is_denied(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals, operation="platform.do.not.exist")
    reply = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "UNKNOWN_OPERATION"
    assert calls == []


def test_scope_not_permitted_is_denied(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals, operation_scope="other")
    reply = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "SCOPE_NOT_PERMITTED"
    assert calls == []


def test_handler_crash_is_outcome_unknown_and_advances_revision(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, receipts = compose(
        state, recording_registry(calls, failure="raise"),
    )
    raw = approved_request(approvals)
    reply = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "OUTCOME_UNKNOWN"
    assert reply["error_code"] == "HANDLER_FAILED_UNKNOWN"
    assert reply["current_revision"] == 1
    assert receipts.current_revision() == 1
    assert len(calls) == 1
    # The durable unknown receipt is replayed; the handler never runs twice.
    replay = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert replay["outcome"] == "OUTCOME_UNKNOWN"
    assert replay["receipt_id"] == reply["receipt_id"]
    assert len(calls) == 1


def test_pre_effect_handler_failure_is_failed_without_revision_change(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, receipts = compose(
        state, recording_registry(calls, failure="failed"),
    )
    raw = approved_request(approvals)
    reply = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "FAILED"
    assert reply["error_code"] == "HANDLER_FAILED"
    assert receipts.current_revision() == 0


def test_same_idempotency_key_replays_durable_receipt(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals)
    first = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert first["outcome"] == "SUCCEEDED"
    assert first["current_revision"] == 1
    replay = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert replay["outcome"] == "SUCCEEDED"
    assert replay["receipt_id"] == first["receipt_id"]
    assert replay["current_revision"] == 1
    assert len(calls) == 1


def test_receipt_survives_reload_and_is_replayed(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals)
    first = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert first["outcome"] == "SUCCEEDED"

    reloaded, _, receipts = compose(state, recording_registry(calls))
    assert receipts.current_revision() == 1
    replay = reloaded.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert replay["outcome"] == "SUCCEEDED"
    assert replay["receipt_id"] == first["receipt_id"]
    assert len(calls) == 1


def test_reusing_idempotency_key_for_different_request_is_denied(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals)
    first = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert first["outcome"] == "SUCCEEDED"
    different = approved_request(approvals, payload={"value": "different"})
    reply = dispatcher.dispatch(different, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "IDEMPOTENCY_MISMATCH"
    assert len(calls) == 1


def test_revoked_owner_during_handler_is_outcome_unknown(tmp_path):
    state = state_path(tmp_path)
    receipts = ManagementMutationReceiptStore(state)
    approvals = ExecutionApprovalVerifier(state)

    def revoke_then_return(_invocation: MutationInvocation) -> None:
        with sqlite3.connect(state) as db:
            db.execute(
                "UPDATE safe_owner_credential SET revoked_at=?",
                (NOW.isoformat(),),
            )
            db.commit()

    dispatcher = ManagementMutationDispatcher(
        current_status=lambda: status(),
        registry=MutationRegistry((
            MutationOperation(
                name=TEST_OPERATION, scopes=frozenset({"test"}),
                handler=revoke_then_return,
            ),
        )),
        approvals=approvals, receipts=receipts, clock=lambda: NOW,
    )
    raw = approved_request(approvals)
    reply = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "OUTCOME_UNKNOWN"
    assert reply["error_code"] == "AUTHORITY_REVOKED"


def test_strict_response_rejects_tampering_and_uncorrelated_receipt():
    expected = typed_request()
    good = {
        "schema": "aegis.platform.management_mutation-response.v1",
        "protocol_version": MANAGEMENT_MUTATION_PROTOCOL,
        "request_id": expected.request_id,
        "correlation_id": expected.correlation_id,
        "idempotency_key": expected.idempotency_key,
        "platform_id": expected.target_platform_id,
        "operation": expected.operation,
        "outcome": "SUCCEEDED",
        "receipt_id": "mutreceipt:abc",
        "current_generation": 3,
        "current_revision": 1,
        "error_code": None,
        "detail": None,
        "observed_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    parsed = UntrustedManagementMutationResponse.parse(
        json.dumps(good).encode("utf-8"), expected=expected, now=NOW,
    )
    assert parsed.outcome == "SUCCEEDED"
    for field, value in (
        ("outcome", "BOGUS"),
        ("request_id", "request:other"),
        ("current_generation", 0),
        ("error_code", "UNREVIEWED"),
    ):
        tampered = dict(good)
        tampered[field] = value
        with pytest.raises((ValueError, PermissionError)):
            UntrustedManagementMutationResponse.parse(
                json.dumps(tampered).encode("utf-8"),
                expected=expected, now=NOW,
            )
    unknown = dict(good)
    unknown["grant"] = "owner"
    with pytest.raises(ValueError):
        UntrustedManagementMutationResponse.parse(
            json.dumps(unknown).encode("utf-8"), expected=expected, now=NOW,
        )


def test_read_write_multiplexer_routes_mutation_schema_to_dispatcher(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))

    class _Read:
        def __init__(self):
            self.seen = []

        def dispatch(self, raw, *, authenticated_peer, now):
            self.seen.append((raw, authenticated_peer))
            return {"outcome": "OK"}

    library = LibraryReadDispatcher(
        current_status=lambda: status(),
        authorize_os_peer=lambda _peer, _operation: False,
        installed_signed_catalog=lambda: None,
    )
    read = _Read()
    mux = LocalReadMultiplexer(
        management=read, library=library, mutation=dispatcher,
    )
    raw = approved_request(approvals)
    reply = mux.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "SUCCEEDED"
    assert read.seen == []
    read_reply = mux.dispatch(
        b'{"schema":"aegis.platform.management.read.v1"}',
        authenticated_peer=PEER, now=NOW,
    )
    assert read_reply == {"outcome": "OK"}
    with pytest.raises(PermissionError, match="not composed"):
        LocalReadMultiplexer(
            management=read, library=library,
        ).dispatch(raw, authenticated_peer=PEER, now=NOW)


LINUX = sys.platform == "linux" and hasattr(socket, "SO_PEERCRED")


@pytest.mark.skipif(not LINUX, reason="Linux kernel peer listener")
def test_unix_listener_dispatches_authenticated_mutation(tmp_path):
    state = state_path(tmp_path)
    calls: list = []
    moment = datetime.now(timezone.utc)
    dispatcher, approvals, _ = compose(
        state, recording_registry(calls),
        clock=lambda: datetime.now(timezone.utc),
    )
    peer = f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
    raw = approved_request(
        approvals, peer=peer, now=moment,
        idempotency_key="idempotency:unix",
        deadline=(moment + timedelta(seconds=5)).isoformat(),
    )
    expected = UntrustedManagementMutation.from_payload(
        json.loads(raw), now=moment,
    )

    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    private.chmod(0o700)
    with ManagementUnixListener(
        private / "management.sock", dispatch=dispatcher.dispatch,
    ) as listener:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(str(listener.path))
            client.sendall(raw + b"\n")
            reply = client.recv(65537)
    parsed = UntrustedManagementMutationResponse.parse(
        reply[:-1] if reply.endswith(b"\n") else reply,
        expected=expected, now=datetime.now(timezone.utc),
    )
    assert parsed.outcome == "SUCCEEDED"
    assert calls == [{"value": "exact"}]


WINDOWS = os.name == "nt"


@pytest.mark.skipif(not WINDOWS, reason="Win32 named-pipe token API")
def test_windows_pipe_dispatches_authenticated_mutation(tmp_path):
    import ctypes
    import ctypes.wintypes as wt
    from sofia.platform.run.management_windows_pipe import _api, _own_sid

    state = state_path(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(
        state, recording_registry(calls),
        clock=lambda: datetime.now(timezone.utc),
    )
    k, a = _api()
    peer = "windows:sid:" + _own_sid(k, a)
    moment = datetime.now(timezone.utc)
    document = request_document(
        idempotency_key="idempotency:windows",
        deadline=(moment + timedelta(seconds=5)).isoformat(),
        approval_id="approval:pending",
    )
    fingerprint = execution_fingerprint(
        MANAGEMENT_MUTATION_CAPABILITY,
        mutation_approval_parameters(
            UntrustedManagementMutation.from_payload(document, now=moment),
            peer,
        ),
    )
    approval = ExecutionApproval(
        approval_id="approval:" + uuid4().hex,
        capability=MANAGEMENT_MUTATION_CAPABILITY,
        request_fingerprint=fingerprint,
        approved_by="Sparks", approved_at=moment - timedelta(seconds=1),
        expires_at=moment + timedelta(minutes=5),
    )
    record_verified_owner_approval(approvals, approval)
    document["approval_id"] = approval.approval_id
    wire = json.dumps(document, separators=(",", ":")).encode("utf-8") + b"\n"

    stop = Event()
    server = ManagementWindowsPipeListener(
        "AegisMutation-" + uuid4().hex, dispatch=dispatcher.dispatch,
    )
    with server:
        worker = Thread(target=server.serve_until, args=(stop,), daemon=True)
        worker.start()
        k.CreateFileW.argtypes = [
            wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
            wt.DWORD, wt.DWORD, wt.HANDLE,
        ]
        k.CreateFileW.restype = wt.HANDLE
        handle = None
        for _ in range(60):
            value = k.CreateFileW(
                server.name, 0xC0000000, 0, None, 3, 0x120000, None,
            )
            if value not in (None, ctypes.c_void_p(-1).value):
                handle = value
                break
            sleep(0.03)
        assert handle is not None
        try:
            buf = ctypes.create_string_buffer(wire)
            count = wt.DWORD()
            assert k.WriteFile(handle, buf, len(wire), ctypes.byref(count), None)
            reply = ctypes.create_string_buffer(65536)
            got = wt.DWORD()
            for _ in range(100):
                if k.ReadFile(handle, reply, 65536, ctypes.byref(got), None):
                    break
                sleep(0.02)
            assert got.value > 0
        finally:
            k.CloseHandle(handle)
            stop.set()
            worker.join(timeout=4)
        assert not worker.is_alive()

    body = reply.raw[:got.value]
    parsed = UntrustedManagementMutationResponse.parse(
        body[:-1] if body.endswith(b"\n") else body,
        expected=UntrustedManagementMutation.from_payload(
            document, now=moment,
        ),
        now=datetime.now(timezone.utc),
    )
    assert parsed.outcome == "SUCCEEDED"
    assert calls == [{"value": "exact"}]

def test_platform_service_composes_canonical_mutation_path(tmp_path):
    import sqlite3 as _sqlite3
    from sofia.platform.run.platform_service import PlatformServiceSession
    from test.test_platform_service_session import provision

    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256,
    ) as session:
        if os.name == "nt":
            from sofia.platform.run.management_windows_pipe import _api, _own_sid
            k, a = _api()
            peer = "windows:sid:" + _own_sid(k, a)
        else:
            peer = f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
        current_status = session.status()
        moment = datetime.now(timezone.utc)
        document = request_document(
            idempotency_key="idempotency:service-unknown",
            target_platform_id=current_status["platform_id"],
            expected_generation=current_status["generation"],
            expected_revision=0,
            operation="platform.unknown.mutation",
            operation_scope="operator",
            deadline=(moment + timedelta(seconds=5)).isoformat(),
        )
        denied = session._management_mux.dispatch(
            json.dumps(document, separators=(",", ":")).encode("utf-8"),
            authenticated_peer=peer, now=moment,
        )
        assert denied["outcome"] == "DENIED"
        assert denied["error_code"] == "UNKNOWN_OPERATION"

        document = request_document(
            idempotency_key="idempotency:service-stop",
            target_platform_id=current_status["platform_id"],
            expected_generation=current_status["generation"],
            expected_revision=0,
            operation="platform.operator.stop.activate",
            operation_scope="operator",
            payload={"reason": "service composition test"},
            deadline=(moment + timedelta(seconds=5)).isoformat(),
        )
        approvals = ExecutionApprovalVerifier(state)
        document["approval_id"] = approve(
            approvals, document, peer, now=moment,
            approved_at=moment - timedelta(seconds=1),
            expires_at=moment + timedelta(minutes=5),
        )
        reply = session._management_mux.dispatch(
            json.dumps(document, separators=(",", ":")).encode("utf-8"),
            authenticated_peer=peer, now=datetime.now(timezone.utc),
        )
        assert reply["outcome"] == "SUCCEEDED"
        assert session.stop.current().active is True
        with _sqlite3.connect(state) as db:
            assert db.execute(
                "SELECT COUNT(*) FROM platform_management_mutation_receipt"
            ).fetchone()[0] == 2
