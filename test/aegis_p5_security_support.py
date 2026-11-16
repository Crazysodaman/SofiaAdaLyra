"""Shared, non-production fixtures for the Aegis P5 security regression suite.

Every key, approval, database and process backend here is disposable test
material.  Nothing in this module reads a production owner secret, credential
or protected canonical state.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import pytest

from sofia.platform.run.management_mutation import (
    MANAGEMENT_MUTATION_CAPABILITY, ManagementMutationDispatcher,
    MutationOperation, MutationRegistry,
)
from sofia.platform.run.management_mutation_store import (
    ManagementMutationReceiptStore,
)
from sofia.platform.safe.execution_approval import (
    ExecutionApproval, ExecutionApprovalVerifier, execution_fingerprint,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.sdk.platform_management_mutation import (
    MANAGEMENT_MUTATION_PROTOCOL, MANAGEMENT_MUTATION_SCHEMA,
    UntrustedManagementMutation, mutation_approval_parameters,
)
from test.owner_auth_fixture import record_verified_owner_approval

NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
PLATFORM = "platform:alpha"
PEER = "unix:uid:1000:gid:1000"
TEST_OPERATION = "platform.test.mutate"


def canonical_state(tmp_path: Path) -> Path:
    return bootstrap_canonical_sqlite(tmp_path / "platform.db")


def request_document(**changes) -> dict[str, object]:
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
        request_document(**changes), separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def status(*, operator_stop: bool = False, generation: int = 3):
    return {
        "platform_id": PLATFORM, "generation": generation,
        "operator_stop": operator_stop,
    }


def approve_management(
    approvals: ExecutionApprovalVerifier,
    document: dict[str, object],
    peer: str = PEER,
    *,
    now: datetime = NOW,
    approval_id: str | None = None,
    approved_at: datetime | None = None,
    expires_at: datetime | None = None,
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
        approved_at=approved_at or (now - timedelta(seconds=1)),
        expires_at=expires_at or (now + timedelta(minutes=5)),
    )
    record_verified_owner_approval(approvals, approval)
    return identifier


def approved_request(
    approvals: ExecutionApprovalVerifier,
    *,
    peer: str = PEER,
    now: datetime = NOW,
    **changes,
) -> bytes:
    document = request_document(**changes)
    document["approval_id"] = approve_management(
        approvals, document, peer, now=now,
    )
    return json.dumps(document, separators=(",", ":")).encode("utf-8")


def recording_registry(calls: list, *, failure: str | None = None) -> MutationRegistry:
    def handler(invocation) -> None:
        calls.append(invocation.request.payload)
        if failure == "raise":
            raise RuntimeError("simulated handler crash")
        if failure == "failed":
            from sofia.platform.run.management_mutation import MutationFailed
            raise MutationFailed("simulated pre-effect refusal")

    return MutationRegistry((
        MutationOperation(
            name=TEST_OPERATION,
            scopes=frozenset({"test"}),
            handler=handler,
        ),
    ))


def compose(
    state: Path,
    registry: MutationRegistry,
    *,
    current_status=None,
    clock=None,
):
    approvals = ExecutionApprovalVerifier(state)
    receipts = ManagementMutationReceiptStore(state)
    dispatcher = ManagementMutationDispatcher(
        current_status=current_status or (lambda: status()),
        registry=registry,
        approvals=approvals,
        receipts=receipts,
        clock=clock or (lambda: NOW),
    )
    return dispatcher, approvals, receipts


def make_directory_redirect(link: Path, target: Path) -> str:
    """Create a symlink where allowed, otherwise an NTFS junction on Windows."""
    try:
        link.symlink_to(target, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=False, capture_output=True, text=True,
        )
        if completed.returncode == 0 and link.is_junction():
            return "junction"
    pytest.skip("host denies unprivileged directory redirection")


def assert_secret_absent(secret: str, *observations: object) -> None:
    for observation in observations:
        text = observation if isinstance(observation, str) else json.dumps(
            observation, sort_keys=True, default=str,
        )
        assert secret not in text
