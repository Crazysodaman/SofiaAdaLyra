"""Core-free Desktop state and uncertain-turn recovery regression."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sofia.modules.ui.core_link_desktop import (
    CoreLinkDesktopClient,
    CoreLinkDesktopStateStore,
    RemoteTurnUncertain,
)
from sofia.modules.ui.core_link_settings import CoreLinkSettingsClient
from sofia.platform.core_link import CoreLinkBinding, CoreLinkBindingState
from sofia.platform.state.private_file import assert_owner_private_path
from sofia.sdk import CoreLinkResponse, CoreLinkResponseStatus, ProtocolVersion


NOW = datetime(2026, 10, 25, 20, tzinfo=timezone.utc)


def binding() -> CoreLinkBinding:
    return CoreLinkBinding(
        binding_id="binding:sofia", local_platform_id="platform:desktop",
        remote_platform_id="platform:canonical",
        remote_core_identity_id="core:sofia", remote_core_generation=9,
        endpoint_id="endpoint:sofia",
        credential_ref="os-keystore:sofia/core-link",
        trust_anchor_ref="sha256:" + "a" * 64,
        audience_id="audience:owner-private",
        granted_scopes=(
            "core-link.status", "conversation.create", "conversation.select",
            "conversation.send", "conversation.history", "conversation.result",
            "settings.snapshot", "settings.update", "settings.events",
            "settings.read.core", "settings.write.core",
        ),
        protocol_version=ProtocolVersion(1, 0),
        state=CoreLinkBindingState.ACTIVE, revision=3,
        created_at=NOW, updated_at=NOW,
    )


class ScriptedTransport:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    def request(self, request):
        self.requests.append(request)
        operation, status, payload = self.script.pop(0)
        assert request.operation == operation
        return CoreLinkResponse(request.request_id, status, payload, NOW)


def response_script_for_start(*, session_id="session:remote"):
    return [
        ("status", CoreLinkResponseStatus.COMPLETED, {
            "remote_platform_id": "platform:canonical",
            "remote_core_identity_id": "core:sofia",
            "remote_core_generation": 9,
            "protocol": "1.0", "state": "ready",
            "operator_stop_active": False,
        }),
        ("conversation.create", CoreLinkResponseStatus.COMPLETED, {
            "session_id": session_id,
        }),
        ("conversation.history", CoreLinkResponseStatus.COMPLETED, {
            "session_id": session_id, "messages": [], "next_cursor": None,
        }),
    ]


def test_remote_desktop_preserves_uncertain_turn_and_reconciles_after_restart(
    tmp_path: Path,
):
    selected = binding()
    path = (tmp_path / "client-state.json").resolve()
    first_transport = ScriptedTransport(response_script_for_start() + [
        ("conversation.send", CoreLinkResponseStatus.OUTCOME_UNKNOWN, {
            "event_id": "event:uncertain", "state": "processing",
        }),
    ])
    first = CoreLinkDesktopClient(
        first_transport, selected,
        CoreLinkDesktopStateStore(path, selected), clock=lambda: NOW,
    )
    assert first.start() == ()
    with pytest.raises(RemoteTurnUncertain, match="outcome_unknown"):
        first.send("Please remember this exact turn")
    persisted = CoreLinkDesktopStateStore(path, selected).load()
    assert persisted.draft == "Please remember this exact turn"
    assert persisted.pending_idempotency_key is not None

    second_transport = ScriptedTransport([
        ("status", CoreLinkResponseStatus.COMPLETED, {
            "remote_platform_id": "platform:canonical",
            "remote_core_identity_id": "core:sofia",
            "remote_core_generation": 9,
            "protocol": "1.0", "state": "ready",
            "operator_stop_active": False,
        }),
        ("conversation.select", CoreLinkResponseStatus.COMPLETED, {
            "session_id": "session:remote",
        }),
        ("conversation.result", CoreLinkResponseStatus.COMPLETED, {
            "event_id": "event:uncertain", "state": "completed",
            "content": "Settled once", "canonical_sequence": 1,
        }),
        ("conversation.history", CoreLinkResponseStatus.COMPLETED, {
            "session_id": "session:remote",
            "messages": [
                {"message_id": "m1", "role": "user",
                 "content": "Please remember this exact turn",
                 "created_at": NOW.isoformat()},
                {"message_id": "m2", "role": "assistant",
                 "content": "Settled once",
                 "created_at": (NOW + timedelta(seconds=1)).isoformat()},
            ],
            "next_cursor": None,
        }),
    ])
    restarted = CoreLinkDesktopClient(
        second_transport, selected,
        CoreLinkDesktopStateStore(path, selected), clock=lambda: NOW,
    )
    history = restarted.start()
    assert [message.content for message in history] == [
        "Please remember this exact turn", "Settled once",
    ]
    assert "conversation.send" not in {
        request.operation for request in second_transport.requests
    }
    settled = CoreLinkDesktopStateStore(path, selected).load()
    assert settled.pending_idempotency_key is None
    assert settled.draft == ""


def test_client_state_is_profile_bound_private_json_not_canonical_sqlite(tmp_path):
    selected = binding()
    path = (tmp_path / "remote-ui.json").resolve()
    store = CoreLinkDesktopStateStore(path, selected)
    original = store.load()
    store.save(original)
    assert path.read_bytes().startswith(b"{")
    assert_owner_private_path(path, directory=False)
    assert not any(item.suffix == ".db" for item in path.parent.iterdir())
    other = replace(
        selected, binding_id="binding:roland",
        remote_core_identity_id="core:roland",
    )
    with pytest.raises(PermissionError, match="another Core"):
        CoreLinkDesktopStateStore(path, other).load()


def test_client_state_rejects_redirected_parent(tmp_path):
    selected = binding()
    outside = tmp_path / "outside"
    outside.mkdir(mode=0o700)
    redirected = tmp_path / "redirected"
    redirected.symlink_to(outside, target_is_directory=True)
    store = CoreLinkDesktopStateStore(
        (redirected / "remote-ui.json").absolute(), selected,
    )
    with pytest.raises(PermissionError, match="redirection"):
        store.save(store.load())


def test_tray_status_probe_does_not_create_a_conversation(tmp_path):
    selected = binding()
    transport = ScriptedTransport([
        ("status", CoreLinkResponseStatus.COMPLETED, {
            "remote_platform_id": "platform:canonical",
            "remote_core_identity_id": "core:sofia",
            "remote_core_generation": 9,
            "protocol": "1.0", "state": "ready",
            "operator_stop_active": False,
        }),
    ])
    client = CoreLinkDesktopClient(
        transport, selected,
        CoreLinkDesktopStateStore((tmp_path / "tray-state.json").resolve(), selected),
        clock=lambda: NOW,
    )
    assert client.probe_status()["state"] == "ready"
    assert [request.operation for request in transport.requests] == ["status"]


def test_remote_settings_uses_revisioned_api_and_resynchronizes():
    selected = binding()
    initial = {
        "schema_version": 11, "revision": 4, "effective_revision": 4,
        "values": {"location_label": "Home"},
        "contracts": {"location_label": {
            "owner": "core", "apply_class": "live",
        }},
    }
    changed = {
        **initial, "revision": 5, "effective_revision": 5,
        "values": {"location_label": "Workshop"},
    }
    transport = ScriptedTransport([
        ("settings.snapshot", CoreLinkResponseStatus.COMPLETED, initial),
        ("settings.update", CoreLinkResponseStatus.COMPLETED, {
            "revision": 5, "effective_revision": 5, "apply_state": "applied",
            "changed_fields": ["location_label"], "apply_classes": ["live"],
            "error": None,
        }),
        ("settings.snapshot", CoreLinkResponseStatus.COMPLETED, changed),
    ])
    client = CoreLinkSettingsClient(transport, selected, clock=lambda: NOW)

    assert client.refresh()["revision"] == 4
    receipt = client.update(
        "location_label", "Workshop", idempotency_key="settings:stable",
    )

    assert receipt["apply_state"] == "applied"
    assert client.snapshot["values"]["location_label"] == "Workshop"
    update_request = transport.requests[1]
    assert update_request.payload == {
        "expected_revision": 4,
        "changes": {"location_label": "Workshop"},
    }
    assert update_request.idempotency_key == "settings:stable"


def test_remote_settings_refuses_fields_outside_authorized_projection():
    selected = binding()
    snapshot = {
        "schema_version": 11, "revision": 0, "effective_revision": 0,
        "values": {"location_label": "Home"},
        "contracts": {"location_label": {
            "owner": "core", "apply_class": "live",
        }},
    }
    transport = ScriptedTransport([
        ("settings.snapshot", CoreLinkResponseStatus.COMPLETED, snapshot),
    ])
    client = CoreLinkSettingsClient(transport, selected, clock=lambda: NOW)
    client.refresh()

    with pytest.raises(PermissionError, match="authorized projection"):
        client.update("adaptive_theme", False)
    assert [request.operation for request in transport.requests] == [
        "settings.snapshot",
    ]
