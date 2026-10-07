from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from sofia.safe.audit import AuditChain
from sofia.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)


pytestmark = pytest.mark.pkg_safe
NOW = datetime(2026, 10, 7, 1, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "row_factory",
    (None, sqlite3.Row),
    ids=("default-tuple", "sqlite-row"),
)
def test_append_in_transaction_accepts_caller_owned_row_factory(
    tmp_path, row_factory
):
    state = tmp_path / "sofia.db"
    audit = AuditChain(state)
    audit.append(
        actor_id="system:test",
        event_type="test.seed",
        payload={"position": 1},
        occurred_at=NOW,
        event_id="audit-seed",
    )

    with sqlite3.connect(state) as db:
        db.row_factory = row_factory
        db.execute("BEGIN IMMEDIATE")
        audit.append_in_transaction(
            db,
            actor_id="system:test",
            event_type="test.second",
            payload={"position": 2},
            occurred_at=NOW + timedelta(seconds=1),
            event_id=f"audit-second-{row_factory is sqlite3.Row}",
        )

    assert audit.verify() == (True, None)
    with sqlite3.connect(state) as db:
        assert db.execute(
            "SELECT COUNT(*) FROM safe_audit_event"
        ).fetchone()[0] == 2


def test_execution_approval_records_and_consumes_after_existing_audit_event(
    tmp_path,
):
    state = tmp_path / "sofia.db"
    audit = AuditChain(state)
    audit.append(
        actor_id="system:test",
        event_type="test.preexisting",
        payload={"existing": True},
        occurred_at=NOW,
        event_id="preexisting-audit-event",
    )
    parameters = {"service": "SofiaAdaLyra"}
    approval = ExecutionApproval(
        approval_id="service-restart-once",
        capability="local.service.restart",
        request_fingerprint=execution_fingerprint(
            "local.service.restart", parameters
        ),
        approved_by="Sparks",
        approved_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(minutes=15),
    )
    verifier = ExecutionApprovalVerifier(state)

    verifier.record(approval)
    consumed = verifier.consume(
        approval_id=approval.approval_id,
        capability=approval.capability,
        parameters=parameters,
        now=NOW + timedelta(seconds=2),
    )

    assert consumed == approval
    with pytest.raises(PermissionError, match="already consumed"):
        verifier.consume(
            approval_id=approval.approval_id,
            capability=approval.capability,
            parameters=parameters,
            now=NOW + timedelta(seconds=3),
        )
    assert audit.verify() == (True, None)
