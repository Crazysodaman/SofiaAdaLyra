"""Platform-owned per-Core autostart policy and startup reconciliation."""
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import uuid4

import pytest

from sofia.platform.run.core_autostart import (
    CoreAutostartConflict,
    CoreAutostartOutcome,
    CoreAutostartPolicyStore,
    CoreStartupReconciler,
    CoreStartupState,
    approval_fingerprint,
)
from test.test_platform_service_session import provision

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class OneUseApprovals:
    """Test-only one-use verifier; no secret is ever derived or stored."""

    def __init__(self, allow=True):
        self.allow = allow
        self.used = set()
        self.calls = []

    def __call__(
        self, *, approval_ref, core_id, revision, enabled, fingerprint, now,
    ):
        self.calls.append(
            (approval_ref, core_id, revision, enabled, fingerprint, now)
        )
        if not self.allow or approval_ref in self.used:
            return False
        self.used.add(approval_ref)
        return True


def policy_store(tmp_path, *, allow=True):
    _identity, _current, state = provision(tmp_path)
    approvals = OneUseApprovals(allow=allow)
    store = CoreAutostartPolicyStore(state, verify_approval=approvals)
    return store, approvals, state


def enable(store, core_id, *, enabled=True, revision=1, ref="approval:one",
           now=NOW):
    return store.set_enabled(
        core_id=core_id, enabled=enabled, revision=revision,
        approval_ref=ref, now=now,
    )


def test_zero_policies_is_zero_core_healthy_without_start_callback(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    started = []
    reconciler = CoreStartupReconciler(
        store=store,
        start_core=lambda *args: started.append(args),
        is_stopped=lambda: False,
        clock=lambda: NOW,
    )
    report = reconciler.reconcile(expected_generation=4)
    assert report.startup_state is CoreStartupState.ZERO_CORE_HEALTHY
    assert report.enabled_count == 0
    assert report.active_count == 0
    assert report.zero_core_healthy is True
    assert report.results == ()
    assert started == []


def test_approved_enabled_core_starts_once_and_records_started(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    policy = enable(store, core_id)
    assert policy.enabled is True
    assert policy.approved_revision == 1
    assert policy.last_outcome is CoreAutostartOutcome.NOT_STARTED
    calls = []

    def start_core(core, generation, approval_ref):
        calls.append((core, generation, approval_ref))
        return "STARTED"

    reconciler = CoreStartupReconciler(
        store=store, start_core=start_core, is_stopped=lambda: False,
        clock=lambda: NOW,
    )
    report = reconciler.reconcile(expected_generation=7)
    assert report.startup_state is CoreStartupState.HEALTHY
    assert report.enabled_count == 1
    assert report.active_count == 1
    assert calls == [(core_id, 7, f"core-autostart:{core_id}:1")]
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.STARTED
    assert persisted.last_started_generation == 7
    assert persisted.last_attempt_at == NOW
    assert persisted.last_error_code is None


def test_disabled_policy_is_never_started(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id, enabled=False)
    started = []
    reconciler = CoreStartupReconciler(
        store=store,
        start_core=lambda *args: started.append(args),
        is_stopped=lambda: False,
        clock=lambda: NOW,
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.ZERO_CORE_HEALTHY
    assert started == []
    persisted = store.policy(core_id)
    assert persisted.enabled is False
    assert persisted.last_outcome is CoreAutostartOutcome.NOT_STARTED


def test_missing_or_denied_approval_is_refused_without_policy_row(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    with pytest.raises(PermissionError):
        store.set_enabled(
            core_id=core_id, enabled=True, revision=1,
            approval_ref="", now=NOW,
        )
    denied, _denied_approvals, _ = policy_store(
        tmp_path / "denied", allow=False,
    )
    with pytest.raises(PermissionError):
        denied.set_enabled(
            core_id=core_id, enabled=True, revision=1,
            approval_ref="approval:denied", now=NOW,
        )
    assert store.policy(core_id) is None
    assert denied.policy(core_id) is None


def test_operator_stop_marks_stopped_and_starts_nothing(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    started = []
    reconciler = CoreStartupReconciler(
        store=store,
        start_core=lambda *args: started.append(args),
        is_stopped=lambda: True,
        clock=lambda: NOW,
    )
    report = reconciler.reconcile(expected_generation=2)
    assert report.startup_state is CoreStartupState.DEGRADED
    assert report.active_count == 0
    assert started == []
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.STOPPED
    assert persisted.last_error_code == "OPERATOR_STOP"


def test_revoked_and_stale_policies_are_not_started(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    started = []
    revoked = CoreStartupReconciler(
        store=store,
        start_core=lambda *args: started.append(args),
        is_stopped=lambda: False,
        is_authorized=lambda _policy: False,
        clock=lambda: NOW,
    )
    report = revoked.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.DEGRADED
    assert started == []
    assert store.policy(core_id).last_outcome is CoreAutostartOutcome.NOT_STARTED

    stale_store, _stale_approvals, _state = policy_store(tmp_path / "stale")
    stale_core = str(uuid4())
    enable(
        stale_store, stale_core,
        now=NOW - timedelta(seconds=901),
    )
    stale = CoreStartupReconciler(
        store=stale_store,
        start_core=lambda *args: started.append(args),
        is_stopped=lambda: False,
        freshness_seconds=900,
        clock=lambda: NOW,
    )
    stale_report = stale.reconcile(expected_generation=1)
    assert stale_report.startup_state is CoreStartupState.DEGRADED
    assert started == []
    assert (
        stale_store.policy(stale_core).last_outcome
        is CoreAutostartOutcome.NOT_STARTED
    )


def test_start_failure_becomes_failed_and_never_raises(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)

    def start_core(_core, _generation, _ref):
        raise RuntimeError("backend unavailable")

    reconciler = CoreStartupReconciler(
        store=store, start_core=start_core, is_stopped=lambda: False,
        clock=lambda: NOW,
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.DEGRADED
    assert report.results[0].started is False
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.FAILED
    assert persisted.last_error_code == "EXC_RuntimeError"


def test_unknown_start_outcome_becomes_outcome_unknown(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    reconciler = CoreStartupReconciler(
        store=store,
        start_core=lambda *_args: "OUTCOME_UNKNOWN",
        is_stopped=lambda: False,
        clock=lambda: NOW,
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.UNKNOWN
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.OUTCOME_UNKNOWN
    assert persisted.last_error_code == "OUTCOME_UNKNOWN"


def test_restart_reconciliation_is_idempotent_per_generation(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    calls = []

    def start_core(core, generation, ref):
        calls.append((core, generation, ref))
        return CoreAutostartOutcome.STARTED

    first = CoreStartupReconciler(
        store=store, start_core=start_core, is_stopped=lambda: False,
        clock=lambda: NOW,
    )
    assert first.reconcile(expected_generation=9).active_count == 1
    second = CoreStartupReconciler(
        store=store, start_core=start_core, is_stopped=lambda: False,
        clock=lambda: NOW,
    )
    restarted = second.reconcile(expected_generation=9)
    assert restarted.startup_state is CoreStartupState.HEALTHY
    assert restarted.active_count == 1
    assert len(calls) == 1
    assert restarted.results[0].started is False
    assert "already started" in restarted.results[0].reason


def test_duplicate_and_stale_writers_are_denied(tmp_path):
    store, approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id, ref="approval:first")
    with pytest.raises(CoreAutostartConflict):
        enable(store, core_id, ref="approval:duplicate")
    with pytest.raises(CoreAutostartConflict):
        enable(store, core_id, revision=3, ref="approval:fresh")
    with pytest.raises(CoreAutostartConflict):
        store.set_enabled(
            core_id=str(uuid4()), enabled=True, revision=2,
            approval_ref="approval:new-core", now=NOW,
        )
    # Each distinct approval reference is eligible exactly once.
    reused = approvals.calls[0][0]
    with pytest.raises(PermissionError):
        enable(
            store, str(uuid4()), revision=1, ref=reused,
        )


def test_policy_persists_without_reference_or_secret_material(tmp_path):
    store, _approvals, state = policy_store(tmp_path)
    core_id = str(uuid4())
    reference = "approval:owner-one-use-9f3a"
    enable(store, core_id, ref=reference)
    reopened = CoreAutostartPolicyStore(
        state, verify_approval=OneUseApprovals(),
    )
    persisted = reopened.policy(core_id)
    assert persisted is not None
    assert persisted.enabled is True
    assert persisted.approved_revision == 1
    assert persisted.approval_fingerprint == approval_fingerprint(
        core_id, 1, True
    )
    assert persisted.updated_at == NOW
    raw = state.read_bytes()
    assert reference.encode("utf-8") not in raw
    with sqlite3.connect(state) as db:
        columns = {
            row[1] for row in db.execute(
                "PRAGMA table_info(platform_core_autostart_policy)"
            )
        }
    assert "approval_ref" not in columns
    assert not any("secret" in column for column in columns)
    assert {
        "core_id", "enabled", "approved_revision", "approval_fingerprint",
        "updated_at", "last_outcome", "last_attempt_at", "last_error_code",
    }.issubset(columns)
