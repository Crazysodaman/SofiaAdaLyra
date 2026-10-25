"""Advisory module behavior: no real host effects, no Core or remote services."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.it_devops.analysis import assess_pipeline, capability_registrations as devops_caps
from sofia.modules.homelab.analysis import assess_services, capability_registrations as homelab_caps
from sofia.modules.remote_access.analysis import assess_session, capability_registrations as remote_caps
from sofia.modules.energy.analysis import assess_ups, capability_registrations as energy_caps
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 10, 25, 17, tzinfo=timezone.utc)


def pipe(**change):
    data = {"source_ref": "ci:runner1", "pipeline_ref": "build:1", "observed_at": NOW.isoformat(),
            "commit_sha": "a" * 40, "branch": "main", "build": "passed", "tests": "passed",
            "security_scan": "passed", "artifact_digest": "b" * 64, "deploy_state": "not_requested"}
    data.update(change)
    return data


def service(name="api", **change):
    data = {"source_ref": "platform:site1", "service_ref": name, "host_ref": "node:01",
            "observed_at": NOW.isoformat(), "state": "healthy", "depends_on": []}
    data.update(change)
    return data


def session(**change):
    data = {"source_ref": "platform:remote", "session_ref": "session:1", "observed_at": NOW.isoformat(),
            "transport": "ssh", "status": "active", "mfa_reported": True,
            "device_enrolled_reported": True, "channel_encrypted_reported": True, "idle_seconds": 2,
            "revoke_reported": False}
    data.update(change)
    return data


def ups(**change):
    data = {"source_ref": "ups:device1", "ups_ref": "ups:1", "observed_at": NOW.isoformat(),
            "mains_present": True, "battery_percent": 99.0, "load_percent": 21.0,
            "runtime_seconds": 2400, "self_test_state": "passed"}
    data.update(change)
    return data


def test_devops_eligible_is_review_only():
    result = assess_pipeline(pipe(), now=NOW)
    assert result["eligible_for_human_review"] is True
    assert result["effect"] == "none"
    assert result["evidence_class"] == "supplied_unverified"


@pytest.mark.parametrize("field,value,code", [
    ("build", "failed", "build_failed_reported"),
    ("tests", "failed", "tests_failed_reported"),
    ("security_scan", "failed", "security_scan_failed_reported"),
    ("security_scan", "pending", "security_scan_not_complete"),
    ("deploy_state", "failed_reported", "deployment_failure_reported"),
    ("artifact_digest", None, "artifact_digest_missing"),
    ("deploy_state", "deployed_reported", "deployment_outcome_unverified"),
])
def test_devops_findings(field, value, code):
    report = assess_pipeline(pipe(**{field: value}), now=NOW)
    assert code in report["findings"]
    assert report["eligible_for_human_review"] is False


@pytest.mark.parametrize("field,value", [
    ("commit_sha", "a" * 30), ("branch", "../../main"), ("security_scan", "executed"),
    ("artifact_digest", "signed"), ("build", True), ("deploy_state", "auto_deploy"),
    ("observed_at", "not-date"), ("source_ref", "secret\nline"),
])
def test_devops_bad_inputs(field, value):
    with pytest.raises(ValueError):
        assess_pipeline(pipe(**{field: value}), now=NOW)


def test_devops_future_or_stale_is_unknown():
    for observed, reason in [(NOW + timedelta(minutes=1), "future"), (NOW - timedelta(minutes=6), "stale")]:
        report = assess_pipeline(pipe(observed_at=observed.isoformat()), now=NOW)
        assert (report["freshness"], report["classification"]) == (reason, "unknown")
        assert report["eligible_for_human_review"] is False


def test_homelab_impact_is_hypothetical_only():
    observations = [service("db", state="unavailable"), service("api", depends_on=["db"])]
    report = assess_services(observations, now=NOW)
    api = next(x for x in report["services"] if x["service_ref"] == "api")
    assert api["unavailable_upstreams"] == ["db"]
    assert api["reported_state"] == "healthy"
    assert api["classification"] == "attention"
    assert report["effect"] == "none"


def test_homelab_no_fault():
    report = assess_services([service("db"), service("api", depends_on=["db"])], now=NOW)
    assert all(x["classification"] == "no_issue_observed" for x in report["services"])


@pytest.mark.parametrize("observations", [
    [service("api", depends_on=["missing"])],
    [service("api", depends_on=["api"])],
    [service("api", depends_on=["db"]), service("db", depends_on=["api"])],
    [service("api"), service("api")],
    [service("db", source_ref="site:a"), service("api", depends_on=["db"])],
    [service("api", depends_on=["db", "db"]), service("db")],
    [service("api", state="broken")],
    [service("api", host_ref="node\nvalue")],
])
def test_homelab_rejects_ambiguous_topology(observations):
    with pytest.raises(ValueError):
        assess_services(observations, now=NOW)


def test_homelab_stale_dependency_not_treated_as_down():
    obs = [service("db", observed_at=(NOW-timedelta(minutes=8)).isoformat(), state="unavailable"),
           service("api", depends_on=["db"])]
    api = next(x for x in assess_services(obs, now=NOW)["services"] if x["service_ref"] == "api")
    assert api["unknown_upstreams"] == ["db"]
    assert api["unavailable_upstreams"] == []


def test_remote_session_never_mints_authorization():
    report = assess_session(session(), now=NOW)
    assert report["classification"] == "no_issue_observed"
    assert report["authorization_conclusion"] == "not_evaluated"
    assert report["evidence_class"] == "supplied_unverified"


@pytest.mark.parametrize("values,flag", [
    ({"mfa_reported": False}, "mfa_unconfirmed"),
    ({"device_enrolled_reported": False}, "device_enrollment_unconfirmed"),
    ({"channel_encrypted_reported": False}, "encryption_unconfirmed"),
    ({"idle_seconds": 901}, "idle_timeout_exceeded"),
    ({"revoke_reported": True}, "active_after_revocation_reported"),
    ({"status": "failed"}, "access_failure_reported"),
])
def test_remote_access_reports_flags(values, flag):
    assert flag in assess_session(session(**values), now=NOW)["findings"]


@pytest.mark.parametrize("bad", [
    {"transport": "telnet"}, {"mfa_reported": "true"}, {"idle_seconds": -3},
    {"status": "active", "idle_seconds": None}, {"session_ref": "../../token"},
    {"observed_at": "2026-10-25T17:00:00"}, {"status": "escalate"},
    {"revoke_reported": 0},
])
def test_remote_access_rejects_invalid_evidence(bad):
    with pytest.raises(ValueError):
        assess_session(session(**bad), now=NOW)


def test_remote_access_disallows_secret_in_schema():
    with pytest.raises(ValueError):
        assess_session(session(token="hidden"), now=NOW)


def test_remote_stale_unknown():
    report = assess_session(session(observed_at=(NOW-timedelta(hours=1)).isoformat(), revoke_reported=True), now=NOW)
    assert report["classification"] == "unknown"
    assert "active_after_revocation_reported" not in report["findings"]


def test_ups_normal():
    report = assess_ups(ups(), now=NOW)
    assert report["classification"] == "no_issue_observed"
    assert report["effect"] == "none"
    assert report["estimate_is_not_a_shutdown_permission"] is True


@pytest.mark.parametrize("values,flag", [
    ({"mains_present": False}, "utility_power_absent_reported"),
    ({"mains_present": None}, "utility_state_unknown"),
    ({"battery_percent": 12}, "battery_low_reported"),
    ({"load_percent": 99.0}, "load_high_reported"),
    ({"load_percent": 100.0}, "load_at_or_over_limit_reported"),
    ({"runtime_seconds": 500}, "estimated_runtime_below_reserve"),
    ({"self_test_state": "failed"}, "self_test_failure_reported"),
    ({"self_test_state": "not_run"}, "self_test_unverified"),
])
def test_ups_findings(values, flag):
    assert flag in assess_ups(ups(**values), now=NOW)["findings"]


@pytest.mark.parametrize("changes", [
    {"battery_percent": True}, {"battery_percent": -1}, {"battery_percent": float("nan")},
    {"load_percent": 101}, {"runtime_seconds": -5}, {"runtime_seconds": False},
    {"self_test_state": "reboot"}, {"mains_present": "yes"},
    {"observed_at": "bad"}, {"ups_ref": "secret\nfield"},
])
def test_ups_rejects_bad_readings(changes):
    with pytest.raises(ValueError):
        assess_ups(ups(**changes), now=NOW)


def test_ups_stale_never_uses_old_estimate():
    report = assess_ups(ups(observed_at=(NOW-timedelta(minutes=3)).isoformat(), runtime_seconds=1), now=NOW)
    assert report["freshness"] == "stale"
    assert report["runtime_estimate_seconds"] is None
    assert "estimated_runtime_below_reserve" not in report["findings"]


@pytest.mark.parametrize("factory,param", [
    (devops_caps, {"observation": pipe(observed_at=datetime.now(timezone.utc).isoformat())}),
    (homelab_caps, {"observations": [service(observed_at=datetime.now(timezone.utc).isoformat())]}),
    (remote_caps, {"observation": session(observed_at=datetime.now(timezone.utc).isoformat())}),
    (energy_caps, {"observation": ups(observed_at=datetime.now(timezone.utc).isoformat())}),
])
def test_capability_handlers_are_inert_and_validate_identity(factory, param):
    ((cap, handler),) = factory()
    assert isinstance(cap, Capability)
    assert handler(CapabilityRequest(cap, param, None, "review data"))["effect"] == "none"
    fake = Capability(cap.name, "Unapproved shadow descriptor")
    with pytest.raises(ValueError):
        handler(CapabilityRequest(fake, param, None, "review data"))


def test_invalid_policy_never_broadens_freshness():
    with pytest.raises(ValueError):
        assess_pipeline(pipe(), now=NOW, max_age_seconds=True)
    with pytest.raises(ValueError):
        assess_services([service()], now=NOW, max_age_seconds=0)
    with pytest.raises(ValueError):
        assess_session(session(), now=NOW, max_idle_seconds=86401)
    with pytest.raises(ValueError):
        assess_ups(ups(), now=NOW, reserve_seconds=0)
