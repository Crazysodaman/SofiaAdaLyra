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
