"""Aegis P5 owner-approval replay, STOP and revocation regressions.

These tests use disposable signed/unsigned fixtures only.  They do not acquire
new authority, read a production owner secret or mutate canonical Core state.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
import json
import sqlite3

import pytest

from sofia.platform.ops.library_chunk_receiver import ChunkTransferRejected
from sofia.platform.ops.platform_installer_cli import execute_command
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.safe.permissions import (
    PermissionStore, standing_grant_parameters,
)
from sofia.platform.run.library_peer_gate import selected_peer_grant_scope
from test.aegis_p5_security_support import (
    NOW, PEER, approved_request, canonical_state, compose,
    recording_registry, request_document, status,
)
from test.owner_auth_fixture import _signed_permission_approval
from test.test_library_service_adapters import (
    NOW as LIB_NOW, SOURCE, SOURCE_GENERATION, _asset, _offer, _primary,
)
from test.test_ops_platform_installer_cli import (
    _fake_backend, _install, debian_host, scope,
)


def test_management_approval_is_consumed_once_across_idempotency_keys(tmp_path):
    state = canonical_state(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(
        state, recording_registry(calls, failure="failed"),
    )
    raw = approved_request(approvals)
    approval_id = json.loads(raw)["approval_id"]

    first = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert first["outcome"] == "FAILED"
    assert first["error_code"] == "HANDLER_FAILED"
    assert len(calls) == 1

    replay_document = request_document(
        idempotency_key="idempotency:replay", approval_id=approval_id,
    )
    replay = dispatcher.dispatch(
        json.dumps(replay_document, separators=(",", ":")).encode("utf-8"),
        authenticated_peer=PEER, now=NOW,
    )
    assert replay["outcome"] == "DENIED"
    assert replay["error_code"] == "APPROVAL_CONSUMED"
    assert len(calls) == 1
    with sqlite3.connect(state) as db:
        consumed = db.execute(
            "SELECT consumed_at FROM safe_execution_approval WHERE approval_id=?",
            (approval_id,),
        ).fetchone()[0]
    assert consumed is not None


def test_management_durable_replay_never_reexecutes_effect(tmp_path):
    state = canonical_state(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals)

    first = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    replay = dispatcher.dispatch(raw, authenticated_peer=PEER, now=NOW)
    assert first["outcome"] == replay["outcome"] == "SUCCEEDED"
    assert replay["receipt_id"] == first["receipt_id"]
    assert len(calls) == 1


def test_stop_between_management_plan_and_effect_is_denied_without_effect(
    tmp_path,
):
    state = canonical_state(tmp_path)
    calls: list = []
    observations = [status(operator_stop=False), status(operator_stop=True)]

    dispatcher, approvals, _ = compose(
        state, recording_registry(calls),
        current_status=lambda: observations.pop(0),
    )
    reply = dispatcher.dispatch(
        approved_request(approvals), authenticated_peer=PEER, now=NOW,
    )
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "STATE_CHANGED"
    assert calls == []


def test_unobservable_management_state_after_approval_fails_closed(tmp_path):
    state = canonical_state(tmp_path)
    calls: list = []
    reads = 0

    def current_status():
        nonlocal reads
        reads += 1
        if reads == 1:
            return status()
        raise RuntimeError("canonical status became unavailable")

    dispatcher, approvals, _ = compose(
        state, recording_registry(calls), current_status=current_status,
    )
    reply = dispatcher.dispatch(
        approved_request(approvals), authenticated_peer=PEER, now=NOW,
    )
    assert reply["outcome"] == "DENIED"
    assert reply["error_code"] == "STATE_CHANGED"
    assert calls == []


def test_owner_revocation_during_management_handler_is_outcome_unknown(tmp_path):
    from sofia.platform.run.management_mutation import (
        ManagementMutationDispatcher, MutationOperation, MutationRegistry,
    )
    from sofia.platform.run.management_mutation_store import (
        ManagementMutationReceiptStore,
    )

    state = canonical_state(tmp_path)
    approvals = ExecutionApprovalVerifier(state)
    receipts = ManagementMutationReceiptStore(state)

    def revoke(_invocation) -> None:
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
                name="platform.test.mutate", scopes=frozenset({"test"}),
                handler=revoke,
            ),
        )),
        approvals=approvals, receipts=receipts, clock=lambda: NOW,
    )
    reply = dispatcher.dispatch(
        approved_request(approvals), authenticated_peer=PEER, now=NOW,
    )
    assert reply["outcome"] == "OUTCOME_UNKNOWN"
    assert reply["error_code"] == "AUTHORITY_REVOKED"


def test_installer_native_approval_cannot_be_replayed(scope):
    effects: list = []
    backend = _fake_backend(effects)
    _installed, code_approval, native_approval = _install(scope, backend)
    assert len(effects) == 1

    replay_native = execute_command(
        "reinstall",
        replace(scope.inputs, approval_id=native_approval),
        backend=backend,
    )
    replay_code = execute_command(
        "install",
        replace(scope.inputs, code_approval_id=code_approval),
        backend=backend,
    )
    assert replay_native["outcome"] == "DENIED"
    assert replay_code["outcome"] == "DENIED"
    assert len(effects) == 1


def test_installer_stop_between_plan_and_effect_never_executes(scope):
    effects: list = []
    stop = OperatorStopStore(scope.safe)
    stop.set(active=True, updated_by="Sparks", reason="p5 regression STOP")
    result = execute_command(
        "install", scope.inputs, backend=_fake_backend(effects),
    )
    assert result["outcome"] == "DENIED"
    assert result["executed"] is False
    assert result["owner_approved"] is False
    assert effects == []
    assert not scope.inputs.destination.exists()


def test_installer_revoked_owner_proof_between_plan_and_effect_is_denied(scope):
    effects: list = []
    first = execute_command(
        "install", scope.inputs, backend=_fake_backend(effects),
    )
    assert first["required_approval"] == "code"
    # Fresh approval recorded, then the owner credential is revoked before the
    # exact code-publication effect can consume it.
    from test.test_ops_platform_installer_cli import _approve, _code_request
    request = _code_request(scope)
    approval = _approve(
        scope, request["capability"], request["fingerprint"],
        "approval:p5-revoked-code",
    )
    with sqlite3.connect(scope.safe) as db:
        db.execute(
            "UPDATE safe_owner_credential SET revoked_at=?",
            (NOW.isoformat(),),
        )
        db.commit()
    second = execute_command(
        "install", replace(scope.inputs, code_approval_id=approval),
        backend=_fake_backend(effects),
    )
    assert second["outcome"] == "DENIED"
    assert effects == []
    assert not scope.inputs.destination.exists()


def test_library_grant_approval_is_one_use(tmp_path):
    state = canonical_state(tmp_path)
    store = PermissionStore(state)
    offer = _offer(b"p5-library-approval" * 100)
    expires = LIB_NOW + timedelta(minutes=5)
    scope_payload = selected_peer_grant_scope(
        transfer=offer.transfer,
        enrolled_peer_certificate_sha256="a" * 64,
        max_chunk_bytes=1024, now=LIB_NOW, expires_at=expires,
    )
    grant_id = "grant:p5-library-once"
    exact = standing_grant_parameters(
        "library.peer.fetch", scope=scope_payload, grant_id=grant_id,
        expires_at=expires,
    )
    approval_id = _signed_permission_approval(
        store, operation="safe.permission.standing.grant",
        exact=exact, now=LIB_NOW,
    )
    granted = store.grant(
        "library.peer.fetch", scope=scope_payload, expires_at=expires,
        grant_id=grant_id, now=LIB_NOW, approval_id=approval_id,
    )
    assert granted.capability == "library.peer.fetch"
    with pytest.raises(PermissionError, match="already consumed"):
        store.grant(
            "library.peer.fetch", scope=scope_payload, expires_at=expires,
            grant_id="grant:p5-library-replay", now=LIB_NOW,
            approval_id=approval_id,
        )


def test_management_approval_cannot_be_reused_by_library_authority(tmp_path):
    state = canonical_state(tmp_path)
    calls: list = []
    dispatcher, approvals, _ = compose(state, recording_registry(calls))
    raw = approved_request(approvals)
    approval_id = json.loads(raw)["approval_id"]
    assert dispatcher.dispatch(
        raw, authenticated_peer=PEER, now=NOW,
    )["outcome"] == "SUCCEEDED"

    offer = _offer(b"p5-cross-path" * 100)
    grant_id = "grant:p5-cross-path"
    expires = LIB_NOW + timedelta(minutes=5)
    library_scope = selected_peer_grant_scope(
        transfer=offer.transfer,
        enrolled_peer_certificate_sha256="b" * 64,
        max_chunk_bytes=1024, now=LIB_NOW, expires_at=expires,
    )
    with pytest.raises(PermissionError, match="already consumed"):
        PermissionStore(state).grant(
            "library.peer.fetch", scope=library_scope, expires_at=expires,
            grant_id=grant_id, now=LIB_NOW, approval_id=approval_id,
        )
    assert len(calls) == 1


def test_library_stop_between_claim_and_catalog_publish_is_denied(tmp_path):
    data = b"p5-library-stop-between-plan-and-effect" * 8
    offer = _offer(data)
    library_status = {
        "platform_id": SOURCE, "generation": SOURCE_GENERATION,
        "operator_stop": False,
    }
    primary = _primary(tmp_path, offer, status=library_status, data=data)
    primary.claim_primary(now=LIB_NOW)
    library_status["operator_stop"] = True
    with pytest.raises(ChunkTransferRejected):
        primary.publish_catalog(
            transfer=offer.transfer, selected_assets=(_asset(offer),),
            expected_artifact_id=offer.item["artifact_id"],
            sign_external=offer.sign_external, now=LIB_NOW,
        )


def test_library_publisher_revocation_between_claim_and_publish_is_denied(tmp_path):
    data = b"p5-library-publisher-revocation" * 8
    offer = _offer(data)
    library_status = {
        "platform_id": SOURCE, "generation": SOURCE_GENERATION,
        "operator_stop": False,
    }
    primary = _primary(tmp_path, offer, status=library_status, data=data)
    primary.claim_primary(now=LIB_NOW)
    primary._publisher_current = lambda _key: False
    with pytest.raises((ChunkTransferRejected, PermissionError)):
        primary.publish_catalog(
            transfer=offer.transfer, selected_assets=(_asset(offer),),
            expected_artifact_id=offer.item["artifact_id"],
            sign_external=offer.sign_external, now=LIB_NOW,
        )
