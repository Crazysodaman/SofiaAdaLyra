"""Service-side read management must never accept a client's own grants."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest

from sofia.platform.config.settings_authority import SettingsOwner
from sofia.platform.run.management_read import (
    ManagementReadDenied, ManagementReadDispatcher,
)

NOW = datetime(2026, 11, 8, 4, tzinfo=timezone.utc)
FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "contracts/platform/management-read-valid-v1.json"
)


def request(operation="platform.status", **changes):
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    raw["operation"] = operation
    raw.update(changes)
    return json.dumps(raw).encode("utf-8")


def service():
    current = {
        "platform_id": "platform:alpha", "generation": 3,
        "operator_stop": False, "core_started": False,
    }
    events = []
    def authorize(peer, operation):
        events.append(("authorize", peer, operation))
        return frozenset({SettingsOwner.HOST}) if peer == "peer:authorized" else None

    def read_settings(scopes):
        events.append(("settings", scopes))
        return {
            "schema_version": 1, "revision": 2, "effective_revision": 1,
            "values": {"fleet_discovery_enabled": True},
            "contracts": {"fleet_discovery_enabled": {
                "owner": "host", "apply_class": "component_restart",
            }},
        }

    dispatcher = ManagementReadDispatcher(
        current_status=lambda: current,
        authorize=authorize,
        read_settings=read_settings,
        clock=lambda: NOW,
    )
    return dispatcher, current, events


def startup_service(**startup_changes):
    current = {
        "platform_id": "platform:alpha", "generation": 3,
        "operator_stop": False, "core_started": False,
    }
    startup = {
        "platform_id": "platform:alpha", "generation": 3,
        "operator_stop": False, "core_started": False,
        "core_count": 0, "active_core_count": 0,
        "startup_state": "ZERO_CORE_HEALTHY",
        "autostart_enabled_count": 0,
        "autostart_reconciled_at": None,
        "management_listening": True,
    }
    startup.update(startup_changes)
    events = []
    def authorize(peer, operation):
        events.append(("authorize", peer, operation))
        return frozenset({SettingsOwner.HOST}) if peer == "peer:authorized" else None

    dispatcher = ManagementReadDispatcher(
        current_status=lambda: current,
        authorize=authorize,
        read_settings=lambda _scopes: {},
        read_startup=lambda: startup,
        clock=lambda: NOW,
    )
    return dispatcher, current, startup, events


def test_platform_status_uses_current_scope_and_generation():
    dispatcher, state, events = service()
    output = dispatcher.dispatch(
        request(), authenticated_peer="peer:authorized", now=NOW
    )
    assert output["data"]["generation"] == state["generation"]
    assert output["data"]["core_started"] is False
    assert output["source"] == "PLATFORM_SESSION"
    assert len(events) == 2  # Admit and revalidate before disclosure.


def test_platform_status_remains_available_while_a_core_is_running():
    dispatcher, state, events = service()
    state["core_started"] = True
    state["active_core_count"] = 2
    output = dispatcher.dispatch(
        request(), authenticated_peer="peer:authorized", now=NOW
    )
    assert output["outcome"] == "OK"
    assert output["data"] == {
        "platform_id": "platform:alpha", "generation": 3,
        "core_started": True, "operator_stop": False,
    }
    assert len(events) == 2


@pytest.mark.parametrize("change,match", [
    ({"operator_stop": True}, "STOP"),
    ({"generation": 4}, "generation"),
])
def test_running_core_does_not_bypass_stop_or_stale_generation(change, match):
    dispatcher, state, events = service()
    state["core_started"] = True
    state["active_core_count"] = 2
    state.update(change)
    with pytest.raises(ManagementReadDenied, match=match):
        dispatcher.dispatch(
            request(), authenticated_peer="peer:authorized", now=NOW
        )
    assert not any(event[0] == "settings" for event in events)


def test_running_core_does_not_bypass_wrong_peer():
    dispatcher, state, events = service()
    state["core_started"] = True
    state["active_core_count"] = 2
    with pytest.raises(ManagementReadDenied):
        dispatcher.dispatch(
            request(), authenticated_peer="peer:unknown", now=NOW
        )
    assert not any(event[0] == "settings" for event in events)


def test_startup_status_zero_core_is_truthful():
    dispatcher, _, _, events = startup_service()
    result = dispatcher.dispatch(
        request("startup.status"), authenticated_peer="peer:authorized", now=NOW
    )
    assert result["outcome"] == "OK"
    assert result["data"] == {
        "platform_id": "platform:alpha", "generation": 3,
        "operator_stop": False, "core_started": False,
        "core_count": 0, "active_core_count": 0,
        "startup_state": "ZERO_CORE_HEALTHY",
        "autostart_enabled_count": 0,
        "autostart_reconciled_at": None,
        "management_listening": True,
    }
    assert len(events) == 2


@pytest.mark.parametrize("state,cores,active", [
    ("CORES_RUNNING", 2, 2),
    ("DEGRADED", 3, 1),
])
def test_startup_status_reports_running_or_degraded_cores(state, cores, active):
    dispatcher, _, _, _ = startup_service(
        core_started=True, core_count=cores, active_core_count=active,
        startup_state=state, autostart_enabled_count=cores,
        autostart_reconciled_at="2026-11-08T03:59:00Z",
    )
    result = dispatcher.dispatch(
        request("startup.status"), authenticated_peer="peer:authorized", now=NOW
    )
    assert result["outcome"] == "OK"
    data = result["data"]
    assert data["core_started"] is True
    assert data["core_count"] == cores
    assert data["active_core_count"] == active
    assert data["startup_state"] == state
    assert data["autostart_reconciled_at"] == "2026-11-08T03:59:00Z"


def test_startup_status_without_service_reader_is_denied():
    dispatcher, _, events = service()
    result = dispatcher.dispatch(
        request("startup.status"), authenticated_peer="peer:authorized", now=NOW
    )
    assert result["outcome"] == "DENIED"
    assert result["denial"] == {"code": "NOT_PERMITTED"}
    assert result["data"] is None
    assert len(events) == 2


def test_startup_status_non_callable_reader_is_refused():
    with pytest.raises(TypeError, match="callable"):
        ManagementReadDispatcher(
            current_status=lambda: {},
            authorize=lambda _peer, _operation: frozenset(),
            read_settings=lambda _scopes: {},
            read_startup=object(),
        )


@pytest.mark.parametrize("change", [
    {"core_count": -1},
    {"core_count": True},
    {"active_core_count": 1},
    {"active_core_count": True},
    {"core_started": "TRUE"},
    {"operator_stop": True},
    {"generation": 4},
    {"platform_id": "platform:wrong"},
    {"startup_state": "HEALTHY"},
    {"startup_state": "CORES_RUNNING"},
    {"autostart_enabled_count": -1},
    {"autostart_enabled_count": 65536},
    {"autostart_reconciled_at": "not-a-date"},
    {"management_listening": 1},
    {"startup_state": "ZERO_CORE_HEALTHY", "core_count": 1},
])
def test_startup_status_invalid_projection_is_denied(change):
    dispatcher, _, startup, events = startup_service()
    startup.update(change)
    with pytest.raises(ManagementReadDenied):
        dispatcher.dispatch(
            request("startup.status"),
            authenticated_peer="peer:authorized", now=NOW,
        )
    assert not any(event[0] == "settings" for event in events)


def test_startup_status_redacts_unknown_service_fields():
    dispatcher, _, startup, _ = startup_service(
        core_started=True, core_count=1, active_core_count=1,
        startup_state="CORES_RUNNING", autostart_enabled_count=1,
    )
    startup["internal_path"] = "/private/owner"
    startup["owner_secret_material"] = "do-not-disclose"
    result = dispatcher.dispatch(
        request("startup.status"), authenticated_peer="peer:authorized", now=NOW
    )
    assert result["outcome"] == "OK"
    assert set(result["data"]) == {
        "platform_id", "generation", "operator_stop", "core_started",
        "core_count", "active_core_count", "startup_state",
        "autostart_enabled_count", "autostart_reconciled_at",
        "management_listening",
    }


def test_settings_use_service_scopes_and_not_client_supplied_field_scopes():
    dispatcher, _, events = service()
    response = dispatcher.dispatch(
        request("settings.inspect"), authenticated_peer="peer:authorized", now=NOW
    )
    assert "fleet_discovery_enabled" in response["data"]["values"]
    assert events[1] == ("settings", frozenset({SettingsOwner.HOST}))
    with pytest.raises(ValueError, match="unreviewed"):
        dispatcher.dispatch(
            request("settings.inspect", scope=["core"]),
            authenticated_peer="peer:authorized", now=NOW
        )


@pytest.mark.parametrize("bad", [
    "not-enrolled", "", "peer:authorized\n", "peer:authorized; grant"
])
def test_missing_unenrolled_and_invalid_os_principal_denied(bad):
    dispatcher, _, events = service()
    with pytest.raises(ManagementReadDenied):
        dispatcher.dispatch(request(), authenticated_peer=bad, now=NOW)
    assert not any(event[0] == "settings" for event in events)


@pytest.mark.parametrize("changes", [
    {"expected_generation": 2},
    {"target_platform_id": "platform:wrong"},
    {"expected_generation": 0},
])
def test_migration_or_stale_generation_denies_before_observation(changes):
    dispatcher, _, events = service()
    with pytest.raises((ManagementReadDenied, ValueError)):
        dispatcher.dispatch(
            request(**changes), authenticated_peer="peer:authorized", now=NOW
        )
    assert not any(event[0] == "settings" for event in events)


def test_stop_denies_even_read_and_does_not_call_settings():
    dispatcher, state, events = service()
    state["operator_stop"] = True
    with pytest.raises(ManagementReadDenied, match="STOP"):
        dispatcher.dispatch(
            request("settings.inspect"), authenticated_peer="peer:authorized", now=NOW
        )
    assert not events


def test_midflight_revocation_suppresses_response():
    current = {
        "platform_id": "platform:alpha", "generation": 3,
        "operator_stop": False, "core_started": False,
    }
    checks = []
    def authorize(_peer, _op):
        checks.append(1)
        return frozenset({SettingsOwner.HOST}) if len(checks) == 1 else None
    dispatcher = ManagementReadDispatcher(
        current_status=lambda: current, authorize=authorize,
        clock=lambda: NOW,
        read_settings=lambda scopes: {
            "schema_version": 1, "revision": 1, "effective_revision": 1,
            "values": {}, "contracts": {},
        },
    )
    with pytest.raises(ManagementReadDenied):
        dispatcher.dispatch(
            request("settings.inspect"), authenticated_peer="peer:authorized", now=NOW
        )
    assert len(checks) == 2


def test_midflight_generation_transition_suppresses_response():
    dispatcher, state, _ = service()
    def read_and_replace(_scope):
        state["generation"] = 4
        return {
            "schema_version": 1, "revision": 0, "effective_revision": 0,
            "values": {}, "contracts": {},
        }
    dispatcher._settings = read_and_replace
    with pytest.raises(ManagementReadDenied, match="generation"):
        dispatcher.dispatch(
            request("settings.inspect"), authenticated_peer="peer:authorized", now=NOW
        )


@pytest.mark.parametrize("operation", [
    "module.remove", "core.start", "settings.write", "platform.install",
    "fleet.list", "module.list",
])
def test_mutations_and_unimplemented_reads_not_dispatched(operation):
    dispatcher, _, _ = service()
    if operation in {"fleet.list", "module.list"}:
        result = dispatcher.dispatch(
            request(operation), authenticated_peer="peer:authorized", now=NOW
        )
        assert result["outcome"] == "DENIED"
        assert result["denial"] == {"code": "NOT_PERMITTED"}
        assert result["data"] is None
    else:
        with pytest.raises((ManagementReadDenied, PermissionError)):
            dispatcher.dispatch(
                request(operation), authenticated_peer="peer:authorized", now=NOW
            )



def test_core_free_platform_session_can_back_authenticated_status(tmp_path):
    """Real RUN lease and persisted identity, but no external peer socket."""
    from sofia.platform.run.platform_service import PlatformServiceSession
    from test.test_platform_service_session import provision

    identity, current, state = provision(tmp_path)
    with PlatformServiceSession(
        identity.home, state,
        current.identity.canonical_uuid, current.public_key_sha256
    ) as session:
        payload = json.loads(request())
        payload["target_platform_id"] = current.identity.canonical_uuid
        payload["expected_generation"] = session.lease.epoch
        dispatch = ManagementReadDispatcher(
            current_status=session.status,
            clock=lambda: NOW,
            authorize=lambda peer, operation: (
                frozenset({SettingsOwner.HOST})
                if peer == "peer:verified" and operation == "platform.status"
                else None
            ),
            read_settings=lambda _: (_ for _ in ()).throw(
                AssertionError("status must not read canonical settings")
            ),
        )
        result = dispatch.dispatch(
            json.dumps(payload).encode("utf-8"),
            authenticated_peer="peer:verified", now=NOW
        )
        assert result["data"]["core_started"] is False
        assert result["data"]["generation"] == session.lease.epoch
        assert result["platform_id"] == current.identity.canonical_uuid
        assert not list(tmp_path.rglob("sofia.db"))



def test_settings_observer_cannot_leak_unapproved_core_field():
    dispatcher, _, _ = service()
    dispatcher._settings = lambda _: {
        "schema_version": 1, "revision": 1, "effective_revision": 1,
        "values": {"cognitive_primary_model": "private"},
        "contracts": {
            "cognitive_primary_model": {
                "owner": "core", "apply_class": "component_restart",
            }
        },
    }
    with pytest.raises(ManagementReadDenied, match="outside approved scope"):
        dispatcher.dispatch(
            request("settings.inspect"),
            authenticated_peer="peer:authorized", now=NOW
        )


def test_management_read_response_size_is_bounded():
    dispatcher, _, _ = service()
    dispatcher._settings = lambda _: {
        "schema_version": 1, "revision": 1, "effective_revision": 1,
        "values": {"ollama_endpoint": "x" * 100000},
        "contracts": {
            "ollama_endpoint": {"owner": "host", "apply_class": "component_restart"}
        },
    }
    with pytest.raises(ManagementReadDenied, match="unsafe management response"):
        dispatcher.dispatch(
            request("settings.inspect"), authenticated_peer="peer:authorized",
            now=NOW
        )


def test_invalid_non_json_settings_observation_is_rejected():
    dispatcher, _, _ = service()
    dispatcher._settings = lambda _: {
        "schema_version": 1, "revision": 1, "effective_revision": 1,
        "values": {"ollama_endpoint": object()},
        "contracts": {
            "ollama_endpoint": {"owner": "host", "apply_class": "component_restart"}
        },
    }
    with pytest.raises(ManagementReadDenied, match="unsafe management response"):
        dispatcher.dispatch(
            request("settings.inspect"), authenticated_peer="peer:authorized",
            now=NOW
        )


def test_enrolled_peer_only_receives_typed_stop_and_stale_denial():
    dispatcher, current, events = service()
    dispatcher._enrolled_denials = True
    current["operator_stop"] = True
    stopped = dispatcher.dispatch(
        request(), authenticated_peer="peer:authorized", now=NOW,
    )
    assert stopped["outcome"] == "DENIED"
    assert stopped["denial"] == {"code": "STOPPED"}
    assert stopped["data"] is None
    assert not any(entry[0] == "settings" for entry in events)

    with pytest.raises(ManagementReadDenied):
        dispatcher.dispatch(
            request(), authenticated_peer="peer:unknown", now=NOW,
        )
    current["operator_stop"] = False
    current["generation"] = 4
    stale = dispatcher.dispatch(
        request(), authenticated_peer="peer:authorized", now=NOW,
    )
    assert stale["outcome"] == "DENIED"
    assert stale["denial"] == {"code": "STALE_GENERATION"}
    assert stale["data"] is None


def test_midflight_revocation_suppresses_typed_stop_denial():
    dispatcher, current, _ = service()
    dispatcher._enrolled_denials = True
    current["operator_stop"] = True
    attempts = []
    def one_use(peer, operation):
        attempts.append(peer)
        return frozenset({SettingsOwner.HOST}) if len(attempts) == 1 else None
    dispatcher._authorize = one_use
    with pytest.raises(ManagementReadDenied):
        dispatcher.dispatch(
            request(), authenticated_peer="peer:authorized", now=NOW,
        )
    assert len(attempts) == 2
