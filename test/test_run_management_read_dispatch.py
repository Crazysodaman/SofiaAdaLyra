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
    )
    return dispatcher, current, events


def test_platform_status_uses_current_scope_and_generation():
    dispatcher, state, events = service()
    output = dispatcher.dispatch(
        request(), authenticated_peer="peer:authorized", now=NOW
    )
    assert output["data"]["generation"] == state["generation"]
    assert output["data"]["core_started"] is False
    assert output["source"] == "PLATFORM_SESSION"
    assert len(events) == 2  # Admit and revalidate before disclosure.


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
    with pytest.raises(ManagementReadDenied, match="exceeds limit"):
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
    with pytest.raises(ManagementReadDenied, match="invalid management response"):
        dispatcher.dispatch(
            request("settings.inspect"), authenticated_peer="peer:authorized",
            now=NOW
        )
