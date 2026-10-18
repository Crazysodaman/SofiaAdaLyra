"""Contract tests for the explicit, local-only Sofía VTube Studio API adapter.

All WebSocket traffic is simulated; no VTS app, camera, profile, or token
is accessed in tests.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from sofia.avatar.vtube_studio_bridge import (
    VTubeStudioBridge, VTSBridgeError, request, _port,
)


class FakeSocket:
    def __init__(self, replies):
        self.replies = list(replies)
        self.sent: list[dict] = []
        self.closed = False

    def send(self, raw: str):
        self.sent.append(json.loads(raw))

    def recv(self, timeout=3):
        assert timeout in (3, 10, 90)
        if not self.replies:
            raise AssertionError("unexpected socket read")
        reply = self.replies.pop(0)
        result = reply(self.sent[-1]) if callable(reply) else dict(reply)
        result.setdefault("apiName", "VTubeStudioPublicAPI")
        result.setdefault("requestID", self.sent[-1]["requestID"])
        return json.dumps(result)

    def close(self):
        self.closed = True


def response(kind, data):
    return {"messageType": kind, "data": data}


def test_envelopes_reject_unknown_api_messages_and_ports():
    envelope = request("APIStateRequest", request_id="exact")
    assert envelope == {
        "apiName": "VTubeStudioPublicAPI", "apiVersion": "1.0",
        "requestID": "exact", "messageType": "APIStateRequest",
    }
    with pytest.raises(ValueError, match="unsupported"):
        request("LoadModelRequest", {})
    with pytest.raises(ValueError):
        request("APIStateRequest", request_id="a" * 65)
    for invalid in (0, 800, 65536, True, "8001"):
        with pytest.raises(ValueError):
            _port(invalid)


def test_status_is_unauthenticated_and_no_vts_process_is_started():
    socket = FakeSocket([response("APIStateResponse", {
        "active": True, "vTubeStudioVersion": "1.0",
        "currentSessionAuthenticated": False,
    })])
    with VTubeStudioBridge(socket) as bridge:
        assert bridge.api_status() == {
            "active": True, "version": "1.0", "session_authenticated": False,
        }
    assert socket.closed
    assert socket.sent[0]["messageType"] == "APIStateRequest"
    assert "data" not in socket.sent[0]


def test_owner_popup_and_authenticated_session_do_not_log_token():
    secret = "owner-consented-test-token"
    socket = FakeSocket([
        response("AuthenticationTokenResponse", {"authenticationToken": secret}),
        response("AuthenticationResponse", {"authenticated": True}),
        response("CurrentModelResponse", {
            "modelLoaded": True, "modelName": "Sofia",
            "hasPhysicsFile": True,
            "modelID": "not_printed",
        }),
    ])
    with VTubeStudioBridge(socket) as bridge:
        assert bridge.pair_with_owner_popup() == secret
        assert bridge.current_model() == {
            "loaded": True, "name": "Sofia", "has_physics": True,
        }
    assert socket.sent[0]["messageType"] == "AuthenticationTokenRequest"
    assert socket.sent[0]["data"]["pluginName"] == "Sofia Ada Lyra"
    assert socket.sent[1]["data"]["authenticationToken"] == secret


def test_model_hotkey_and_parameter_control_require_authenticated_owner():
    bridge = VTubeStudioBridge(FakeSocket([]))
    with pytest.raises(PermissionError, match="owner-authenticated"):
        bridge.current_model()
    with pytest.raises(PermissionError):
        bridge.send_parameter_frame(
            {"FaceAngleX": 1.0},
            owner_allowed=frozenset({"FaceAngleX"}),
            available=frozenset({"FaceAngleX"}),
        )
    with pytest.raises(PermissionError):
        bridge.trigger_approved_hotkey(
            "toggle-approved-coat", owner_allowed=frozenset({"toggle-approved-coat"}),
        )


def test_parameter_injection_requires_two_allowlists_and_finite_numbers():
    socket = FakeSocket([
        response("AuthenticationResponse", {"authenticated": True}),
        response("InputParameterListResponse", {
            "modelLoaded": True, "defaultParameters": [{"name": "FaceAngleX"}],
            "customParameters": [{"name": "SofiaEarLeft"}],
        }),
        response("InjectParameterDataResponse", {}),
    ])
    bridge = VTubeStudioBridge(socket)
    bridge.authenticate("temporary-test-token")
    available = bridge.parameter_names()
    assert available == frozenset({"FaceAngleX", "SofiaEarLeft"})
    with pytest.raises(PermissionError):
        bridge.send_parameter_frame(
            {"SofiaEarLeft": 0.5},
            owner_allowed=frozenset({"FaceAngleX"}), available=available,
        )
    for bad in (float("nan"), float("inf"), True, 1e99):
        with pytest.raises(ValueError):
            bridge.send_parameter_frame(
                {"FaceAngleX": bad},
                owner_allowed=frozenset({"FaceAngleX"}), available=available,
            )
    bridge.send_parameter_frame(
        {"FaceAngleX": 12.0},
        owner_allowed=frozenset({"FaceAngleX"}), available=available,
    )
    payload = socket.sent[-1]
    assert payload["messageType"] == "InjectParameterDataRequest"
    assert payload["data"] == {
        "faceFound": False, "mode": "set",
        "parameterValues": [{"id": "FaceAngleX", "value": 12.0}],
    }


def test_hotkey_uses_only_owner_allowlisted_identifier():
    socket = FakeSocket([
        response("AuthenticationResponse", {"authenticated": True}),
        response("HotkeyTriggerResponse", {"hotkeyID": "approved-hotkey"}),
    ])
    bridge = VTubeStudioBridge(socket)
    bridge.authenticate("temporary-test-token")
    with pytest.raises(PermissionError):
        bridge.trigger_approved_hotkey(
            "not-allowed", owner_allowed=frozenset({"approved-hotkey"}),
        )
    bridge.trigger_approved_hotkey(
        "approved-hotkey", owner_allowed=frozenset({"approved-hotkey"}),
    )
    assert socket.sent[-1]["data"]["hotkeyID"] == "approved-hotkey"


def test_api_error_not_exposed_and_bad_request_id_fails():
    socket = FakeSocket([
        response("APIError", {"errorID": 50, "message": "SECRET remote detail"}),
        {"messageType": "APIStateResponse", "requestID": "stale", "data": {}},
    ])
    bridge = VTubeStudioBridge(socket)
    with pytest.raises(VTSBridgeError, match="error ID: 50") as captured:
        bridge.api_status()
    assert "SECRET" not in str(captured.value)
    with pytest.raises(VTSBridgeError, match="did not match"):
        bridge.api_status()


def test_auth_rejection_is_not_silent():
    socket = FakeSocket([
        response("AuthenticationResponse", {"authenticated": False}),
    ])
    bridge = VTubeStudioBridge(socket)
    with pytest.raises(VTSBridgeError, match="revoked"):
        bridge.authenticate("rejected")
    with pytest.raises(PermissionError):
        bridge.current_model()


def test_help_has_no_socket_or_dpapi_side_effect(capsys):
    from sofia.avatar.vtube_studio_bridge import main
    with pytest.raises(SystemExit) as done:
        main(["--help"])
    assert done.value.code == 0
    assert "--pair" in capsys.readouterr().out


def test_owner_pairing_allows_time_for_vts_permission_popup():
    socket = FakeSocket([
        response("AuthenticationTokenResponse", {
            "authenticationToken": "owner-approved",
        }),
        response("AuthenticationResponse", {"authenticated": True}),
    ])
    with VTubeStudioBridge(socket) as bridge:
        assert bridge.pair_with_owner_popup() == "owner-approved"


def test_reconnect_reuses_saved_owner_approval_without_token_popup(monkeypatch):
    from sofia.avatar import vtube_studio_bridge as api
    socket = FakeSocket([
        response("AuthenticationResponse", {"authenticated": True}),
        response("CurrentModelResponse", {
            "modelLoaded": False, "modelName": "", "hasPhysicsFile": False,
        }),
    ])
    monkeypatch.setattr(api, "load_owner_token", lambda: "stored-token")
    monkeypatch.setattr(
        api.VTubeStudioBridge, "connect_local",
        classmethod(lambda cls, *, port=8001: cls(socket, port=port)),
    )
    result = api.reconnect_saved_session(port=9996)
    assert result == {
        "connected": True, "reused_saved_authorization": True,
        "model_loaded": False, "model_name": "",
        "production_activated": False,
    }
    assert socket.closed
    assert [sent["messageType"] for sent in socket.sent] == [
        "AuthenticationRequest", "CurrentModelRequest",
    ]
    assert socket.sent[0]["data"]["authenticationToken"] == "stored-token"


def test_saved_authorization_metadata_never_decrypts_or_discloses_token(
    monkeypatch, tmp_path,
):
    from sofia.avatar import vtube_studio_bridge as api
    target = tmp_path / "vts_token.dpapi"
    monkeypatch.setattr(api, "_token_path", lambda: target)
    assert api.saved_authorization_status()["token_saved"] is False
    target.write_bytes(b"opaque DPAPI bytes (not real token)")
    report = api.saved_authorization_status()
    assert report["token_saved"] is True
    assert "token" not in json.dumps(report).lower().replace("token_saved", "")


def test_watch_reconnects_after_transient_local_failure_without_new_pair(
    monkeypatch,
):
    from sofia.avatar import vtube_studio_bridge as api
    monkeypatch.setattr(api, "load_owner_token", lambda: "previous-owner-consent")
    statuses = []
    attempts = []
    pauses = [0]
    final_socket = FakeSocket([
        response("AuthenticationResponse", {"authenticated": True}),
        response("APIStateResponse", {"active": True}),
    ])

    def connect(*, port):
        attempts.append(port)
        if len(attempts) == 1:
            raise api.VTSBridgeError("VTS not open yet")
        return api.VTubeStudioBridge(final_socket, port=port)

    def pause(_seconds):
        pauses[0] += 1

    api.watch_saved_connection(
        port=9996, interval_seconds=2, connect=connect, sleep=pause,
        should_stop=lambda: pauses[0] >= 2, on_status=statuses.append,
    )
    assert attempts == [9996, 9996]
    assert statuses == ["waiting_for_vtube_studio", "connected"]
    assert final_socket.closed
    assert [sent["messageType"] for sent in final_socket.sent] == [
        "AuthenticationRequest", "APIStateRequest",
    ]


def test_auto_reconnect_stops_if_plugin_permission_revoked(monkeypatch):
    from sofia.avatar import vtube_studio_bridge as api
    monkeypatch.setattr(api, "load_owner_token", lambda: "revoked-owner-token")
    socket = FakeSocket([
        response("AuthenticationResponse", {"authenticated": False}),
    ])
    with pytest.raises(PermissionError, match="re-enrollment"):
        api.watch_saved_connection(
            port=9996, interval_seconds=2,
            connect=lambda *, port: api.VTubeStudioBridge(socket, port=port),
            sleep=lambda _: pytest.fail("must not retry revoked credential"),
            should_stop=lambda: False,
        )
    assert socket.closed
    assert [item["messageType"] for item in socket.sent] == [
        "AuthenticationRequest",
    ]


def test_watch_requires_existing_owner_token_and_bounded_interval(monkeypatch):
    from sofia.avatar import vtube_studio_bridge as api
    monkeypatch.setattr(api, "load_owner_token", lambda: "test-token")
    for seconds in (-1, 1, 121, float("nan"), float("inf"), True):
        with pytest.raises(ValueError, match="interval"):
            api.watch_saved_connection(interval_seconds=seconds)
    monkeypatch.setattr(
        api, "load_owner_token",
        lambda: (_ for _ in ()).throw(api.VTSBridgeError("missing DPAPI token")),
    )
    with pytest.raises(api.VTSBridgeError, match="missing DPAPI"):
        api.reconnect_saved_session(port=9996)
