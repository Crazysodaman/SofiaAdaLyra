"""Platform management dispatcher protects source/state before UI access."""
from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.platform.application.platform_management_read import (
    ManagementReadDenied, PlatformManagementReadDispatcher, VerifiedReadPeer,
)
from sofia.sdk.platform_management import MANAGEMENT_READ_SCHEMA

NOW = datetime(2026, 11, 8, 4, tzinfo=timezone.utc)


def request(operation="platform.status", generation=3):
    return json.dumps({
        "schema": MANAGEMENT_READ_SCHEMA,
        "protocol": "1.0",
        "request_id": "request:123",
        "target_platform_id": "platform:alpha",
        "expected_generation": generation,
        "operation": operation,
        "created_at": "2026-11-08T03:59:59Z",
        "deadline": "2026-11-08T04:00:05Z",
    }).encode("utf-8")


def service(operation="platform.status"):
    state = {"principal": True, "generation": 3, "stop": False,
             "revoked": False, "allow_core": False}
    visited = []

    def verify(peer, incoming):
        visited.append(("verify", peer))
        if state["revoked"] or not state["principal"] or peer != "OS:LOCAL":
            raise ManagementReadDenied("peer revoked")
        return VerifiedReadPeer(
            principal_id="principal:owner", platform_id="platform:alpha",
            generation=state["generation"],
            operations=frozenset({"platform.status", "settings.inspect"} |
                                 ({"core.list"} if state["allow_core"] else set())),
            valid_until=NOW + timedelta(seconds=30),
        )

    def live():
        visited.append(("status", None))
        return {
            "platform_id": "platform:alpha",
            "generation": state["generation"],
            "core_started": False, "operator_stop": state["stop"],
            "public_key_sha256": "must-not-leak",
        }

    def settings():
        visited.append(("settings", None))
        return {"revision": 12, "effective_revision": 11, "scope": "host"}

    return PlatformManagementReadDispatcher(
        current_peer_grant=verify,
        live_status=live,
        providers={"settings.inspect": settings},
    ), state, visited


def test_authorized_read_gets_bounded_service_owned_response_without_key_leak():
    dispatcher, state, visited = service()
    document = json.loads(dispatcher.handle(
        request(), transport_peer="OS:LOCAL", now=NOW,
    ))
    assert document["status"] == "OBSERVED"
    assert document["generation"] == 3
    assert document["data"]["core_started"] is False
    assert document["data"]["operator_stop"] is False
    assert "must-not-leak" not in json.dumps(document)
    assert [name for name, _ in visited] == [
        "verify", "status", "verify", "status",
    ]


def test_stop_state_is_reported_only_to_verified_read_peers():
    dispatcher, state, _ = service()
    state["stop"] = True
    result = json.loads(dispatcher.handle(
        request(), transport_peer="OS:LOCAL", now=NOW,
    ))
    assert result["data"]["operator_stop"] is True


def test_wrong_peer_cannot_observe_platform_or_provider():
    dispatcher, _state, visited = service()
    with pytest.raises(ManagementReadDenied, match="peer revoked"):
        dispatcher.handle(
            request("settings.inspect"), transport_peer="unverified", now=NOW,
        )
    assert visited == [("verify", "unverified")]


def test_request_mutation_cannot_call_provider():
    dispatcher, _state, visited = service()
    with pytest.raises(PermissionError):
        dispatcher.handle(
            request("settings.write"), transport_peer="OS:LOCAL", now=NOW,
        )
    assert visited == []


def test_revocation_midflight_discards_observation():
    dispatcher, state, visited = service()
    def revoke_in_provider():
        visited.append(("settings", None))
        state["revoked"] = True
        return {"secret": "never-returns"}

    dispatcher._providers["settings.inspect"] = revoke_in_provider
    with pytest.raises(ManagementReadDenied, match="peer revoked"):
        dispatcher.handle(
            request("settings.inspect"), transport_peer="OS:LOCAL", now=NOW,
        )
    assert ("settings", None) in visited


def test_generation_change_midflight_discards_observation():
    dispatcher, state, visited = service()
    def restart_in_provider():
        state["generation"] = 4
        return {"old_generation": True}

    dispatcher._providers["settings.inspect"] = restart_in_provider
    with pytest.raises(ManagementReadDenied):
        dispatcher.handle(
            request("settings.inspect"), transport_peer="OS:LOCAL", now=NOW,
        )


def test_old_generation_and_missing_provider_fail_closed():
    dispatcher, _state, visited = service()
    with pytest.raises(ManagementReadDenied, match="generation"):
        dispatcher.handle(
            request(generation=2), transport_peer="OS:LOCAL", now=NOW,
        )
    # Grant this read explicitly so the missing-provider refusal is tested
    # after authorization, not confused with an earlier scope denial.
    _state["allow_core"] = True
    with pytest.raises(ManagementReadDenied, match="provider not installed"):
        dispatcher.handle(
            request("core.list"), transport_peer="OS:LOCAL", now=NOW,
        )
    assert ("settings", None) not in visited


def test_malformed_status_unknown_response_and_large_provider_denied():
    dispatcher, _state, _visited = service()
    dispatcher._providers["settings.inspect"] = lambda: {"blob": "X" * 70000}
    with pytest.raises(ManagementReadDenied, match="response limit"):
        dispatcher.handle(
            request("settings.inspect"), transport_peer="OS:LOCAL", now=NOW,
        )
    dispatcher._providers["settings.inspect"] = lambda: {"not_json": object()}
    with pytest.raises(ManagementReadDenied, match="invalid read data"):
        dispatcher.handle(
            request("settings.inspect"), transport_peer="OS:LOCAL", now=NOW,
        )


def test_clock_and_peer_verifier_are_required():
    with pytest.raises(ValueError, match="service clock"):
        service()[0].handle(
            request(), transport_peer="OS:LOCAL",
            now=NOW.replace(tzinfo=None),
        )
    with pytest.raises(TypeError, match="peer verifier"):
        PlatformManagementReadDispatcher(
            current_peer_grant=None, live_status=lambda: {}, providers={},
        )
