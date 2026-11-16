"""Platform-owned per-Core autostart policy and startup reconciliation."""
from datetime import datetime, timedelta, timezone
import sqlite3
import time
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


def make_reconciler(
    store, start_core, *, installed=(), observe=None,
    is_stopped=lambda: False,
    is_authorized=lambda _policy: True,
    clock=lambda: NOW,
    start_timeout_seconds=10.0,
):
    return CoreStartupReconciler(
        store=store,
        start_core=start_core,
        observe_core=(
            observe if observe is not None
            else lambda _core, _generation: "STOPPED"
        ),
        installed_core_ids=lambda: tuple(installed),
        is_stopped=is_stopped,
        is_authorized=is_authorized,
        start_timeout_seconds=start_timeout_seconds,
        clock=clock,
    )


def mark_started(store, core_id, generation):
    store.record_outcome(
        core_id=core_id, outcome=CoreAutostartOutcome.STARTED,
        now=NOW, started_generation=generation,
    )


def test_zero_installed_cores_is_zero_core_healthy_without_start(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    started = []
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(),
    )
    report = reconciler.reconcile(expected_generation=4)
    assert report.startup_state is CoreStartupState.ZERO_CORE_HEALTHY
    assert report.core_count == 0
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

    reconciler = make_reconciler(
        store, start_core, installed=(core_id,),
    )
    report = reconciler.reconcile(expected_generation=7)
    assert report.startup_state is CoreStartupState.CORES_RUNNING
    assert report.core_count == 1
    assert report.enabled_count == 1
    assert report.active_count == 1
    assert calls == [(core_id, 7, f"core-autostart:{core_id}:1")]
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.STARTED
    assert persisted.last_started_generation == 7
    assert persisted.last_attempt_at == NOW
    assert persisted.last_error_code is None


def test_disabled_installed_policy_is_never_started(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id, enabled=False)
    started = []
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(core_id,),
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.CORES_DISABLED
    assert report.cores_disabled is True
    assert report.core_count == 1
    assert report.enabled_count == 0
    assert report.active_count == 0
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
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(core_id,),
        is_stopped=lambda: True,
    )
    report = reconciler.reconcile(expected_generation=2)
    assert report.startup_state is CoreStartupState.DEGRADED
    assert report.active_count == 0
    assert started == []
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.STOPPED
    assert persisted.last_error_code == "OPERATOR_STOP"


@pytest.mark.parametrize(
    "age", [timedelta(minutes=10), timedelta(days=1)],
)
def test_durable_approved_policy_stays_eligible_across_reboot(tmp_path, age):
    """A minutes- or day-old approved autostart is durable operator intent."""
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id, now=NOW - age)
    calls = []

    def start_core(core, generation, approval_ref):
        calls.append((core, generation, approval_ref))
        return "STARTED"

    reconciler = make_reconciler(
        store, start_core, installed=(core_id,),
    )
    report = reconciler.reconcile(expected_generation=11)
    assert report.startup_state is CoreStartupState.CORES_RUNNING
    assert report.active_count == 1
    assert calls == [(core_id, 11, f"core-autostart:{core_id}:1")]


def test_future_policy_timestamp_is_refused_as_clock_rollback(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id, now=NOW + timedelta(hours=1))
    started = []
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(core_id,),
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.DEGRADED
    assert report.active_count == 0
    assert report.results[0].error_code == "CLOCK_ROLLBACK"
    assert started == []
    assert (
        store.policy(core_id).last_outcome
        is CoreAutostartOutcome.NOT_STARTED
    )


def test_revoked_authorization_is_rechecked_before_each_start(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    started = []
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(core_id,),
        is_authorized=lambda _policy: False,
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.DEGRADED
    assert report.results[0].error_code == "REVOKED"
    assert started == []
    assert store.policy(core_id).last_outcome is CoreAutostartOutcome.NOT_STARTED


def test_cached_started_is_active_only_when_freshly_observed_running(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    mark_started(store, core_id, 3)
    started = []
    observed = []

    def observe(core, generation):
        observed.append((core, generation))
        return "RUNNING"

    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(core_id,),
        observe=observe,
    )
    report = reconciler.reconcile(expected_generation=3)
    assert report.startup_state is CoreStartupState.CORES_RUNNING
    assert report.active_count == 1
    assert started == []
    assert observed == [(core_id, 3)]
    assert report.results[0].started is False


def test_crash_with_cached_started_is_truthfully_stopped_not_active(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    mark_started(store, core_id, 3)
    started = []
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(core_id,),
        observe=lambda _core, _generation: "STOPPED",
    )
    report = reconciler.reconcile(expected_generation=3)
    assert report.startup_state is CoreStartupState.DEGRADED
    assert report.active_count == 0
    assert started == []
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.STOPPED
    assert persisted.last_error_code == "NOT_RUNNING"


def test_pid_reuse_or_zombie_unknown_is_not_counted_active(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    mark_started(store, core_id, 3)
    started = []
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(core_id,),
        observe=lambda _core, _generation: "UNKNOWN",
    )
    report = reconciler.reconcile(expected_generation=3)
    assert report.startup_state is CoreStartupState.UNKNOWN
    assert report.active_count == 0
    assert started == []
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.OUTCOME_UNKNOWN
    assert persisted.last_error_code == "OBSERVE_UNKNOWN"


def test_stale_generation_is_not_active_and_is_started_afresh(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    mark_started(store, core_id, 2)
    started = []
    observed = []

    def observe(core, generation):
        observed.append((core, generation))
        return "STOPPED"

    def start_core(core, generation, approval_ref):
        started.append((core, generation, approval_ref))
        return "STARTED"

    reconciler = make_reconciler(
        store, start_core, installed=(core_id,), observe=observe,
    )
    report = reconciler.reconcile(expected_generation=9)
    assert report.startup_state is CoreStartupState.CORES_RUNNING
    assert report.active_count == 1
    assert observed == [(core_id, 9)]
    assert len(started) == 1
    assert store.policy(core_id).last_started_generation == 9


def test_restart_after_observed_crash_starts_once_more(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    mark_started(store, core_id, 3)
    started = []

    def start_core(core, generation, approval_ref):
        started.append((core, generation, approval_ref))
        return "STARTED"

    reconciler = make_reconciler(
        store, start_core, installed=(core_id,),
        observe=lambda _core, _generation: "STOPPED",
    )
    crashed = reconciler.reconcile(expected_generation=3)
    assert crashed.active_count == 0
    assert started == []
    assert store.policy(core_id).last_outcome is CoreAutostartOutcome.STOPPED

    restarted = reconciler.reconcile(expected_generation=3)
    assert restarted.startup_state is CoreStartupState.CORES_RUNNING
    assert restarted.active_count == 1
    assert len(started) == 1


def test_installed_core_without_policy_is_cores_disabled(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    started = []
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(core_id,),
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.CORES_DISABLED
    assert report.core_count == 1
    assert report.enabled_count == 0
    assert report.active_count == 0
    assert started == []


def test_installed_count_is_inventory_not_policy_count(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    enabled_core = str(uuid4())
    disabled_core = str(uuid4())
    enable(store, enabled_core, ref="approval:enabled")
    enable(store, disabled_core, enabled=False, ref="approval:disabled")
    installed = [enabled_core, disabled_core, str(uuid4())]
    reconciler = make_reconciler(
        store, lambda *_args: "STARTED", installed=installed,
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.CORES_RUNNING
    assert report.core_count == 3
    assert report.enabled_count == 1
    assert report.active_count == 1


def test_zero_installed_cores_stays_healthy_even_with_policy_rows(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    started = []
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(),
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.ZERO_CORE_HEALTHY
    assert report.core_count == 0
    assert started == []


def test_start_failure_becomes_failed_and_never_raises(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)

    def start_core(_core, _generation, _ref):
        raise RuntimeError("backend unavailable")

    reconciler = make_reconciler(
        store, start_core, installed=(core_id,),
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.DEGRADED
    assert report.core_count == 1
    assert report.active_count == 0
    assert report.results[0].started is False
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.FAILED
    assert persisted.last_error_code == "EXC_RuntimeError"


def test_unknown_start_outcome_becomes_outcome_unknown(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    reconciler = make_reconciler(
        store, lambda *_args: "OUTCOME_UNKNOWN", installed=(core_id,),
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.UNKNOWN
    assert report.active_count == 0
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.OUTCOME_UNKNOWN
    assert persisted.last_error_code == "OUTCOME_UNKNOWN"


def test_slow_start_is_bounded_and_recorded_unknown(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)

    def start_core(_core, _generation, _ref):
        time.sleep(1.0)
        return "STARTED"

    reconciler = make_reconciler(
        store, start_core, installed=(core_id,),
        start_timeout_seconds=0.05,
    )
    began = time.monotonic()
    report = reconciler.reconcile(expected_generation=1)
    elapsed = time.monotonic() - began
    assert elapsed < 0.5
    assert report.startup_state is CoreStartupState.UNKNOWN
    assert report.active_count == 0
    assert report.results[0].error_code == "START_TIMEOUT"
    persisted = store.policy(core_id)
    assert persisted.last_outcome is CoreAutostartOutcome.OUTCOME_UNKNOWN
    assert persisted.last_error_code == "START_TIMEOUT"


def test_required_service_callbacks_are_mandatory(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    common = dict(
        store=store,
        start_core=lambda *_args: "STARTED",
        observe_core=lambda *_args: "RUNNING",
        installed_core_ids=lambda: (),
        is_stopped=lambda: False,
        is_authorized=lambda _policy: True,
    )
    for missing in (
        "start_core", "observe_core", "installed_core_ids",
        "is_stopped", "is_authorized",
    ):
        broken = dict(common)
        broken[missing] = None
        with pytest.raises(TypeError):
            CoreStartupReconciler(**broken)


def test_enabled_policy_for_uninstalled_core_is_never_started(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    installed_core = str(uuid4())
    forged_core = str(uuid4())
    enable(store, forged_core)
    started = []
    reconciler = make_reconciler(
        store, lambda *args: started.append(args), installed=(installed_core,),
    )
    report = reconciler.reconcile(expected_generation=1)
    assert report.startup_state is CoreStartupState.DEGRADED
    assert report.results[0].error_code == "NOT_INSTALLED"
    assert started == []


def test_restart_reconciliation_is_idempotent_per_generation(tmp_path):
    store, _approvals, _state = policy_store(tmp_path)
    core_id = str(uuid4())
    enable(store, core_id)
    calls = []

    def start_core(core, generation, ref):
        calls.append((core, generation, ref))
        return CoreAutostartOutcome.STARTED

    first = make_reconciler(
        store, start_core, installed=(core_id,),
    )
    assert first.reconcile(expected_generation=9).active_count == 1
    second = make_reconciler(
        store, start_core, installed=(core_id,),
        observe=lambda _core, _generation: "RUNNING",
    )
    restarted = second.reconcile(expected_generation=9)
    assert restarted.startup_state is CoreStartupState.CORES_RUNNING
    assert restarted.active_count == 1
    assert len(calls) == 1
    assert restarted.results[0].started is False
    assert "RUNNING" in restarted.results[0].reason


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
