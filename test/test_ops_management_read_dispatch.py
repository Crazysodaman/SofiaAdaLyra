"""Management dispatch is authorized by the host, never by request syntax."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from sofia.platform.application.management_read_service import (
    ManagementReadDenied, PlatformManagementReadDispatcher,
)

pytestmark = pytest.mark.pkg_ops
NOW = datetime(2026, 11, 8, 4, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts/platform/management-read-valid-v1.json"


def configured(provider=None):
    state = {
        "active": True,
        "stop": False,
        "platform_id": "platform:alpha",
        "generation": 3,
        "reads": 0,
        "checks": 0,
        "time": NOW,
    }
    def authorize(peer, operation):
        state["checks"] += 1
        return (state["active"] and peer is state and operation == "platform.status")
    def read():
        state["reads"] += 1
        return {"health": "unknown", "source": "Platform"}
    manager = PlatformManagementReadDispatcher(
        authorize_peer=authorize,
        current_identity=lambda: (state["platform_id"], state["generation"]),
        operator_stop_active=lambda: state["stop"],
        providers={"platform.status": provider or read},
        clock=lambda: state["time"],
    )
    return state, manager


def request(**values):
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    doc.update(values)
    return json.dumps(doc).encode("utf-8")


def test_reviewed_read_requires_live_transport_auth_on_both_sides():
    state, manager = configured()
    result = manager.read(request(), peer=state)
    assert result.platform_id == "platform:alpha"
    assert result.generation == 3
    assert state["reads"] == 1 and state["checks"] == 2
    output = json.loads(result.to_json())
    assert output["payload"]["health"] == "unknown"
    assert output["schema"] == "aegis.platform.management.response.v1"
    assert "authenticated" not in output


def test_missing_and_forged_peer_never_call_provider():
    state, manager = configured()
    for peer in (None, object(), {"active": True}):
        with pytest.raises(ManagementReadDenied, match="authorization"):
            manager.read(request(), peer=peer)
    assert state["reads"] == 0


def test_revocation_midflight_drops_result():
    state = {}
    def revoke():
        state["active"] = False
        return {"modules": []}
    state, manager = configured(revoke)
    with pytest.raises(ManagementReadDenied, match="authorization"):
        manager.read(request(), peer=state)
    assert state["checks"] == 2


def test_identity_generation_or_stop_changes_midflight_fail_closed():
    for action in ("generation", "platform_id", "stop"):
        state = {}
        def alter():
            state[action] = (
                4 if action == "generation" else "platform:other"
                if action == "platform_id" else True
            )
            return {"state": "unknown"}
        state, manager = configured(alter)
        with pytest.raises(ManagementReadDenied, match="generation, identity or STOP"):
            manager.read(request(), peer=state)


def test_initial_stop_and_stale_request_never_read():
    state, manager = configured()
    state["stop"] = True
    with pytest.raises(ManagementReadDenied, match="STOP"):
        manager.read(request(), peer=state)
    assert state["reads"] == 0
    state["stop"] = False
    state["time"] += timedelta(minutes=3)
    with pytest.raises(PermissionError):
        manager.read(request(), peer=state)
    assert state["reads"] == 0


def test_requested_unknown_read_provider_denied_before_auth():
    state, manager = configured()
    with pytest.raises(ManagementReadDenied, match="unavailable"):
        manager.read(request(operation="module.list"), peer=state)
    assert state["reads"] == 0


def test_suspicious_secret_fields_are_never_serialized():
    state, manager = configured(lambda: {
        "status": "unknown", "owner_secret": "64hex-private-credential",
    })
    with pytest.raises(ManagementReadDenied, match="sensitive"):
        manager.read(request(), peer=state)


def test_oversized_or_invalid_provider_payload_fails_closed():
    state, manager = configured(lambda: {"data": "x" * 35000})
    with pytest.raises(ManagementReadDenied, match="exceeds limit"):
        manager.read(request(), peer=state)
    state, manager = configured(lambda: {"data": object()})
    with pytest.raises(ManagementReadDenied, match="unsupported"):
        manager.read(request(), peer=state)


def test_authentication_is_not_supplied_by_request_fields():
    state, manager = configured()
    with pytest.raises(ValueError, match="unreviewed"):
        manager.read(request(owner_approved=True), peer=state)


def test_midflight_clock_expiry_refuses_delivery():
    state = {}
    def slow():
        state["time"] = NOW + timedelta(seconds=6)
        return {"state": "unknown"}
    state, manager = configured(slow)
    with pytest.raises(ManagementReadDenied, match="exceeded request deadline"):
        manager.read(request(), peer=state)
