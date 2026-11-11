from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from test.owner_auth_fixture import record_verified_owner_approval

from sofia.platform.safe.audit import AuditChain
from sofia.platform.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)


pytestmark = pytest.mark.pkg_safe
NOW = datetime(2026, 10, 7, 1, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _explicit_canonical_state(canonical_state_path):
    return canonical_state_path


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

    record_verified_owner_approval(verifier, approval)
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



def test_audit_chain_verifier_streams_long_history_without_fetchall(
        tmp_path, monkeypatch):
    state = tmp_path / "sofia.db"
    audit = AuditChain(state)
    with sqlite3.connect(state) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        for index in range(180):
            audit.append_in_transaction(
                db, actor_id="system:stream-test",
                event_type="audit.stream",
                payload={"sequence": index},
                occurred_at=NOW + timedelta(seconds=index),
                event_id=f"stream-audit-{index:03d}",
            )

    original_connect = audit._connect

    class StreamingConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, *args, **kwargs):
            cursor = self.connection.execute(*args, **kwargs)

            class NoFetchAll:
                def __iter__(self):
                    return iter(cursor)

                def fetchall(self):
                    raise AssertionError("audit integrity must stream historical rows")

            return NoFetchAll()

        def close(self):
            self.connection.close()

    monkeypatch.setattr(
        audit, "_connect", lambda: StreamingConnection(original_connect()),
    )
    assert audit.verify() == (True, None)
    # Streaming cannot trade away hash integrity just to reduce RAM.
    with sqlite3.connect(state) as db:
        db.execute(
            "UPDATE safe_audit_event SET payload_json=? WHERE event_id=?",
            ('{"forged":true}', "stream-audit-091"),
        )
    verified, reason = audit.verify()
    assert verified is False
    assert "stream-audit-091" in reason
