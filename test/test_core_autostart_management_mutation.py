"""Owner-approved Core autostart mutation through the canonical dispatcher."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import inspect
import json
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from sofia.platform.run.core_autostart import (
    CoreAutostartPolicyStore, CoreStartupReconciler,
    management_autostart_writer,
)
from sofia.platform.run.management_mutation import (
    CORE_AUTOSTART_DISABLE_OPERATION, CORE_AUTOSTART_ENABLE_OPERATION,
    CORE_AUTOSTART_SCOPE, MANAGEMENT_MUTATION_CAPABILITY,
    ManagementMutationDispatcher, core_autostart_mutation_registry,
)
from sofia.platform.run.management_mutation_store import (
    ManagementMutationReceiptStore,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.sdk.platform_management_mutation import (
    MANAGEMENT_MUTATION_PROTOCOL, MANAGEMENT_MUTATION_SCHEMA,
    UntrustedManagementMutation, mutation_approval_parameters,
    mutation_fingerprint,
)
from test.owner_auth_fixture import record_verified_owner_approval
from test.test_platform_service_session import provision

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
PLATFORM = "platform:alpha"
PEER = "unix:uid:1000:gid:1000"
GENERATION = 3


def state_path(tmp_path: Path) -> Path:
    return bootstrap_canonical_sqlite(tmp_path / "platform.db")


def policy_store(state: Path, *, verify=None) -> CoreAutostartPolicyStore:
    return CoreAutostartPolicyStore(
        state, verify_approval=verify or (lambda **_kwargs: False),
    )


def make_reconciler(store, installed=()):
    return CoreStartupReconciler(
        store=store,
        start_core=lambda *_args: "FAILED",
        observe_core=lambda *_args: "STOPPED",
        installed_core_ids=lambda: tuple(installed),
        is_stopped=lambda: False,
        is_authorized=lambda _policy: True,
        clock=lambda: NOW,
    )


def request_document(
    operation: str,
    payload: dict,
    *,
    idempotency_key: str,
    expected_revision: int = 0,
    expected_generation: int = GENERATION,
) -> dict:
    return {
        "schema": MANAGEMENT_MUTATION_SCHEMA,
        "protocol_version": MANAGEMENT_MUTATION_PROTOCOL,
        "request_id": "request:" + uuid4().hex,
        "correlation_id": "correlation:" + uuid4().hex,
        "idempotency_key": idempotency_key,
        "target_platform_id": PLATFORM,
        "operation": operation,
        "operation_scope": CORE_AUTOSTART_SCOPE,
        "expected_generation": expected_generation,
        "expected_revision": expected_revision,
        "deadline": (NOW + timedelta(seconds=5)).isoformat().replace(
            "+00:00", "Z"
        ),
        "approval_id": "approval:pending",
        "payload": payload,
    }


def wire(document: dict) -> bytes:
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


def approve(
    state: Path,
    document: dict,
    *,
    peer: str = PEER,
    now: datetime = NOW,
    approved_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> str:
    typed = UntrustedManagementMutation.from_payload(document, now=now)
    approved = approved_at or now
    approval = ExecutionApproval(
        approval_id="approval:" + uuid4().hex,
        capability=MANAGEMENT_MUTATION_CAPABILITY,
        request_fingerprint=execution_fingerprint(
            MANAGEMENT_MUTATION_CAPABILITY,
            mutation_approval_parameters(typed, peer),
        ),
        approved_by="Sparks",
        approved_at=approved,
        expires_at=expires_at or (approved + timedelta(minutes=5)),
    )
    record_verified_owner_approval(ExecutionApprovalVerifier(state), approval)
    return approval.approval_id


def dispatcher(state: Path, registry, stop: OperatorStopStore):
    return ManagementMutationDispatcher(
        current_status=lambda: {
            "platform_id": PLATFORM,
            "generation": GENERATION,
            "operator_stop": stop.current().active,
        },
        registry=registry,
        approvals=ExecutionApprovalVerifier(state),
        receipts=ManagementMutationReceiptStore(state),
        clock=lambda: NOW,
    )


def core_payload(core_id: str, revision: int, enabled: bool) -> dict:
    return {
        "core_id": core_id,
        "expected_revision": revision,
        "enabled": enabled,
    }


def authorized_document(
    state: Path, operation: str, payload: dict, *, idempotency_key: str,
    expected_revision: int = 0, **approval_options,
) -> dict:
    document = request_document(
        operation, payload, idempotency_key=idempotency_key,
        expected_revision=expected_revision,
    )
    document["approval_id"] = approve(state, document, **approval_options)
    return document


def receipt_count(state: Path) -> int:
    with sqlite3.connect(state) as db:
        return db.execute(
            "SELECT COUNT(*) FROM platform_management_mutation_receipt"
        ).fetchone()[0]


def test_approved_enable_and_disable_change_durable_policy_once(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    registry = core_autostart_mutation_registry(
        make_reconciler(store, (core_id,))
    )
    dispatch = dispatcher(state, registry, stop)

    enable = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(core_id, 1, True),
        idempotency_key="idempotency:autostart-enable",
    )
    typed_enable = UntrustedManagementMutation.from_payload(enable, now=NOW)
    reply = dispatch.dispatch(wire(enable), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "SUCCEEDED"
    assert reply["error_code"] is None
    assert reply["current_revision"] == 1
    enabled = store.policy(core_id)
    assert enabled is not None
    assert enabled.enabled is True
    assert enabled.approved_revision == 1
    assert enabled.approval_fingerprint == mutation_fingerprint(
        typed_enable, PEER
    )
    assert receipt_count(state) == 1

    disable = authorized_document(
        state, CORE_AUTOSTART_DISABLE_OPERATION,
        core_payload(core_id, 2, False),
        idempotency_key="idempotency:autostart-disable",
        expected_revision=1,
    )
    reply = dispatch.dispatch(wire(disable), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "SUCCEEDED"
    assert reply["current_revision"] == 2
    disabled = store.policy(core_id)
    assert disabled.enabled is False
    assert disabled.approved_revision == 2
    assert receipt_count(state) == 2


def test_missing_approval_is_denied_without_policy_or_receipt_effect(
    tmp_path,
):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (core_id,))
        ),
        stop,
    )
    document = request_document(
        CORE_AUTOSTART_ENABLE_OPERATION, core_payload(core_id, 1, True),
        idempotency_key="idempotency:autostart-missing",
    )
    reply = dispatch.dispatch(wire(document), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "APPROVAL_MISSING"
    assert store.policy(core_id) is None


def test_expired_approval_is_denied(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (core_id,))
        ),
        stop,
    )
    document = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(core_id, 1, True),
        idempotency_key="idempotency:autostart-expired",
        approved_at=NOW - timedelta(minutes=10),
        expires_at=NOW - timedelta(minutes=5),
    )
    reply = dispatch.dispatch(wire(document), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "APPROVAL_EXPIRED"
    assert store.policy(core_id) is None


def test_revoked_owner_credential_denies_autostart_mutation(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (core_id,))
        ),
        stop,
    )
    document = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(core_id, 1, True),
        idempotency_key="idempotency:autostart-revoked",
    )
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=?",
            (NOW.isoformat(),),
        )
        db.commit()
    reply = dispatch.dispatch(wire(document), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] in {"APPROVAL_UNVERIFIED", "APPROVAL_REVOKED"}
    assert store.policy(core_id) is None


def test_consumed_approval_cannot_be_reused_for_another_request(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (core_id,))
        ),
        stop,
    )
    first = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(core_id, 1, True),
        idempotency_key="idempotency:autostart-consumed-first",
    )
    assert dispatch.dispatch(
        wire(first), authenticated_peer=PEER, now=NOW,
    )["outcome"] == "SUCCEEDED"
    assert store.policy(core_id).approved_revision == 1

    second = request_document(
        CORE_AUTOSTART_DISABLE_OPERATION, core_payload(core_id, 2, False),
        idempotency_key="idempotency:autostart-consumed-second",
        expected_revision=1,
    )
    second["approval_id"] = first["approval_id"]
    reply = dispatch.dispatch(wire(second), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "APPROVAL_CONSUMED"
    persisted = store.policy(core_id)
    assert persisted.enabled is True
    assert persisted.approved_revision == 1


def test_operator_stop_denies_before_approval_consumption(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (core_id,))
        ),
        stop,
    )
    document = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(core_id, 1, True),
        idempotency_key="idempotency:autostart-stop",
    )
    stop.set(
        active=True, updated_by="Sparks", reason="pause autostart changes",
        at=NOW,
    )
    typed = UntrustedManagementMutation.from_payload(document, now=NOW)
    reply = dispatch.dispatch(wire(document), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "STOPPED"
    assert store.policy(core_id) is None
    assert ExecutionApprovalVerifier(state).matches_unconsumed(
        approval_id=document["approval_id"],
        capability=MANAGEMENT_MUTATION_CAPABILITY,
        parameters=mutation_approval_parameters(typed, PEER),
        now=NOW,
    )


def test_stale_policy_revision_is_denied_without_effect(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (core_id,))
        ),
        stop,
    )
    first = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(core_id, 1, True),
        idempotency_key="idempotency:autostart-stale-first",
    )
    assert dispatch.dispatch(
        wire(first), authenticated_peer=PEER, now=NOW,
    )["outcome"] == "SUCCEEDED"

    stale = authorized_document(
        state, CORE_AUTOSTART_DISABLE_OPERATION,
        core_payload(core_id, 1, False),
        idempotency_key="idempotency:autostart-stale-second",
        expected_revision=1,
    )
    reply = dispatch.dispatch(wire(stale), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "STALE_REVISION"
    persisted = store.policy(core_id)
    assert persisted.enabled is True
    assert persisted.approved_revision == 1


def test_unknown_or_uninstalled_core_is_denied(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    installed = str(uuid4())
    unknown = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (installed,))
        ),
        stop,
    )
    document = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(unknown, 1, True),
        idempotency_key="idempotency:autostart-uninstalled",
    )
    reply = dispatch.dispatch(wire(document), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "TARGET_MISMATCH"
    assert store.policy(unknown) is None


def test_target_and_enabled_must_agree(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (core_id,))
        ),
        stop,
    )
    document = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(core_id, 1, False),
        idempotency_key="idempotency:autostart-inconsistent",
    )
    reply = dispatch.dispatch(wire(document), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "INVALID_PAYLOAD"
    assert store.policy(core_id) is None


def test_idempotent_repeat_returns_prior_receipt_and_writes_once(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (core_id,))
        ),
        stop,
    )
    document = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(core_id, 1, True),
        idempotency_key="idempotency:autostart-replay",
    )
    first = dispatch.dispatch(wire(document), authenticated_peer=PEER, now=NOW)
    assert first["outcome"] == "SUCCEEDED"
    first_policy = store.policy(core_id)
    replay = dispatch.dispatch(wire(document), authenticated_peer=PEER, now=NOW)
    assert replay["outcome"] == "SUCCEEDED"
    assert replay["receipt_id"] == first["receipt_id"]
    assert replay["current_revision"] == first["current_revision"]
    assert store.policy(core_id) == first_policy
    assert receipt_count(state) == 1


def test_management_write_does_not_use_a_second_approval_store(tmp_path):
    state = state_path(tmp_path)
    calls: list = []

    def verify(**kwargs):
        calls.append(kwargs)
        return False

    store = policy_store(state, verify=verify)
    core_id = str(uuid4())
    stop = OperatorStopStore(state)
    dispatch = dispatcher(
        state,
        core_autostart_mutation_registry(
            make_reconciler(store, (core_id,))
        ),
        stop,
    )
    document = authorized_document(
        state, CORE_AUTOSTART_ENABLE_OPERATION,
        core_payload(core_id, 1, True),
        idempotency_key="idempotency:autostart-no-second-store",
    )
    reply = dispatch.dispatch(wire(document), authenticated_peer=PEER, now=NOW)
    assert reply["outcome"] == "SUCCEEDED"
    assert calls == []
    assert store.policy(core_id).approved_revision == 1
    with sqlite3.connect(state) as db:
        columns = {
            row[1] for row in db.execute(
                "PRAGMA table_info(platform_core_autostart_policy)"
            )
        }
    assert "approval_ref" not in columns
    assert not any("secret" in column for column in columns)


def test_internal_management_write_requires_service_capability(tmp_path):
    state = state_path(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    signature = inspect.signature(
        CoreAutostartPolicyStore.set_enabled_from_management
    )
    assert "_authority" in signature.parameters
    with pytest.raises(PermissionError):
        store.set_enabled_from_management(
            core_id=core_id,
            enabled=True,
            expected_revision=1,
            authorization_fingerprint="0" * 64,
            now=NOW,
        )
    assert store.policy(core_id) is None
    writer = management_autostart_writer(store)
    assert callable(writer)


def test_sdk_surface_cannot_reach_internal_management_writer():
    root = Path(__file__).resolve().parents[1] / "src" / "sofia" / "sdk"
    forbidden = (
        "set_enabled_from_management",
        "management_autostart_writer",
        "_MANAGEMENT_WRITE_AUTHORITY",
    )
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{path} exposes {token}"


def test_service_wires_autostart_mutation_when_reconciler_present(tmp_path):
    from sofia.platform.run.platform_service import PlatformServiceSession

    identity, current, state = provision(tmp_path)
    store = policy_store(state)
    core_id = str(uuid4())
    reconciler = make_reconciler(store, (core_id,))
    with PlatformServiceSession(
        identity.home, state, current.identity.canonical_uuid,
        current.public_key_sha256, core_autostart=reconciler,
    ) as session:
        if os.name == "nt":
            from sofia.platform.run.management_windows_pipe import (
                _api, _own_sid,
            )
            k, a = _api()
            peer = "windows:sid:" + _own_sid(k, a)
        else:
            peer = f"unix:uid:{os.getuid()}:gid:{os.getgid()}"
        status = session.status()
        moment = datetime.now(timezone.utc)
        document = request_document(
            CORE_AUTOSTART_ENABLE_OPERATION, core_payload(core_id, 1, True),
            idempotency_key="idempotency:autostart-service",
            expected_generation=status["generation"],
        )
        document["target_platform_id"] = status["platform_id"]
        document["deadline"] = (
            moment + timedelta(seconds=5)
        ).isoformat().replace("+00:00", "Z")
        document["approval_id"] = approve(
            state, document, peer=peer, now=moment,
        )
        reply = session._management_mux.dispatch(
            wire(document), authenticated_peer=peer,
            now=datetime.now(timezone.utc),
        )
        assert reply["outcome"] == "SUCCEEDED"
        persisted = store.policy(core_id)
        assert persisted.enabled is True
        assert persisted.approved_revision == 1
        assert receipt_count(state) == 1
