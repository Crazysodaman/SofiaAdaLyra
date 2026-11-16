"""Aegis P5 owner-secret non-disclosure regressions.

A disposable sentinel is written into a temporary ``safe_owner_secret`` row.
The exercised management, installer, library and synthetic-Core paths must
never echo it into receipts, JSON, logs, exceptions, subprocess argv or env.
"""
from __future__ import annotations

from datetime import timedelta
import json
import logging
from pathlib import Path
import sqlite3
import subprocess

import pytest

from sofia.platform.ops.platform_installer_cli import main
from sofia.platform.ops.synthetic_core_lifecycle import SyntheticCoreLifecycleStore
from sofia.platform.run.management_mutation import (
    ManagementMutationDispatcher, MutationOperation, MutationRegistry,
)
from sofia.platform.run.management_mutation_store import (
    ManagementMutationReceiptStore,
)
from sofia.platform.safe.execution_approval import ExecutionApprovalVerifier
from sofia.platform.safe.permissions import PermissionStore
from sofia.platform.safe.operator_stop import OperatorStopStore
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.sdk.platform_release import PlatformReleaseTarget
from test.aegis_p5_security_support import (
    NOW, PEER, approve_management, assert_secret_absent, raw_request,
    request_document, status,
)

SENTINEL = "P5-OWNER-SECRET-SENTINEL-9f4c2b7a-do-not-disclose"


@pytest.fixture
def secret_state(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "platform.db")
    # Create the canonical SAFE schema, then store a disposable sentinel.  This
    # is test material, not a production credential or an owner-secret lookup.
    ExecutionApprovalVerifier(state)
    OperatorStopStore(state)
    with sqlite3.connect(state) as db:
        db.execute(
            "INSERT INTO safe_owner_secret("
            "singleton,windows_sid,salt,verifier,version,enrolled_at"
            ") VALUES(1,?,?,?,?,?)",
            (
                "S-1-5-21-p5-disposable", b"p5-salt", SENTINEL.encode("utf-8"),
                1, NOW.isoformat(),
            ),
        )
        db.commit()
    return state


def _management_reply(
    state: Path, *, handler_error: str | None = None, approve: bool = False,
):
    def handler(_invocation) -> None:
        if handler_error is not None:
            raise RuntimeError(handler_error)

    approvals = ExecutionApprovalVerifier(state)
    if approve:
        document = request_document(idempotency_key="idempotency:secret-handler")
        document["approval_id"] = approve_management(approvals, document)
        wire = json.dumps(document, separators=(",", ":")).encode("utf-8")
    else:
        wire = raw_request()

    receipts = ManagementMutationReceiptStore(state)
    dispatcher = ManagementMutationDispatcher(
        current_status=lambda: status(),
        registry=MutationRegistry((
            MutationOperation(
                name="platform.test.mutate", scopes=frozenset({"test"}),
                handler=handler,
            ),
        )),
        approvals=approvals,
        receipts=receipts, clock=lambda: NOW,
    )
    return dispatcher.dispatch(
        wire, authenticated_peer=PEER, now=NOW,
    )


def _installer_denial(tmp_path: Path, capsys) -> tuple[int, str]:
    missing = tmp_path / "absent-release"
    key = tmp_path / "absent-publisher.pem"
    code = main([
        "verify", "--release-root", str(missing),
        "--publisher-key", str(key),
        "--publisher-key-sha256", "a" * 64,
        "--publisher-signer", "p5-disposable-signer",
        "--expected-source-sha", "b" * 40,
        "--target", PlatformReleaseTarget.DEBIAN12_X86_64.value,
        "--minimum-revision", "1", "--json",
    ])
    output = capsys.readouterr().out
    return code, output


def _receipt_and_audit_text(state: Path) -> str:
    with sqlite3.connect(state) as db:
        receipts = db.execute(
            "SELECT * FROM platform_management_mutation_receipt"
        ).fetchall()
        audit = db.execute("SELECT * FROM safe_audit_event").fetchall()
    return json.dumps([receipts, audit], default=str)


def test_owner_secret_is_absent_from_receipts_logs_exceptions_and_cli(
    secret_state, tmp_path, caplog, capsys, monkeypatch,
):
    subprocess_calls: list = []

    def forbidden_subprocess(*args, **kwargs):
        subprocess_calls.append((args, kwargs))
        return None

    for name in ("Popen", "run", "call", "check_call", "check_output"):
        monkeypatch.setattr(subprocess, name, forbidden_subprocess)

    caplog.set_level(logging.DEBUG)
    observations: list[object] = []
    exceptions: list[BaseException] = []

    denied = _management_reply(secret_state)
    observations.append(denied)

    unknown = _management_reply(
        secret_state, handler_error=f"handler observed {SENTINEL}", approve=True,
    )
    observations.append(unknown)
    # The denied request and the handler crash must never expose the sentinel.
    assert denied["outcome"] == "DENIED"
    assert unknown["outcome"] == "OUTCOME_UNKNOWN"

    installer_code, installer_output = _installer_denial(tmp_path, capsys)
    assert installer_code == 3
    observations.append(installer_output)

    store = PermissionStore(secret_state)
    expires = NOW + timedelta(minutes=5)
    try:
        store.grant(
            "storage.write_text", scope={"path": "p5-disposable"},
            grant_id="grant:p5-secret", expires_at=expires, now=NOW,
            approval_id=None,
        )
    except BaseException as exc:  # expected denial; inspect its text
        exceptions.append(exc)
    else:  # pragma: no cover - defensive if the denial contract regresses
        raise AssertionError("library grant without owner approval succeeded")

    synthetic = SyntheticCoreLifecycleStore(tmp_path / "synthetic" / "bindings.sqlite")
    observations.append(str(synthetic.path))
    assert synthetic.path.is_file()

    observations.append(_receipt_and_audit_text(secret_state))
    for observation in observations:
        assert_secret_absent(SENTINEL, observation)
    for exception in exceptions:
        assert_secret_absent(SENTINEL, str(exception), repr(exception))
    assert_secret_absent(SENTINEL, caplog.text)
    assert subprocess_calls == []
