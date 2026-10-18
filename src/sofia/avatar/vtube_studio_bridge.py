"""Opt-in, localhost-only VTube Studio adapter for Sofía's future Live2D rig.

This is a separate, manually invoked integration. It does NOT replace the
verified public Tk renderer, use raw Private-Source PNGs, change sofia.db,
infer speech, or enable autonomous API requests. VTS displays its own
permission prompt when the OWNER explicitly requests pairing.

API: https://github.com/DenchiSoft/VTubeStudio/blob/master/README.md
"""
from __future__ import annotations

import argparse
import json
import math
import os
import inspect
import socket
import time
from pathlib import Path
import sys
from uuid import uuid4

_PLUGIN_NAME = "Sofia Ada Lyra"
_PLUGIN_DEVELOPER = "SofiaAdaLyra"
_API = "VTubeStudioPublicAPI"
_MAX_MESSAGE = 128_000
_STATUS_TIMEOUT = 10


class VTSBridgeError(RuntimeError):
    """Safe, non-secret API error (never includes tokens or response payloads)."""


def _port(value: int) -> int:
    if type(value) is not int or not 1024 <= value <= 65535:
        raise ValueError("VTube Studio local port must be between 1024 and 65535")
    return value


def _token_path() -> Path:
    if sys.platform != "win32" or not os.environ.get("LOCALAPPDATA"):
        raise VTSBridgeError("DPAPI pairing requires the Windows user profile on Venus")
    return (
        Path(os.environ["LOCALAPPDATA"])
        / "SofiaAdaLyra" / "Avatar2D" / "VTubeStudio" / "vts_token.dpapi"
    )


def save_owner_token(token: str, *, path: Path | None = None) -> Path:
    """Bind the owner-approved VTS token to their current Windows login.

    Never commit, print, or save the clear-text token. Fail instead of
    overwriting another credential. The VTube Studio permission is revocable.
    """
    if sys.platform != "win32":
        raise VTSBridgeError("DPAPI token storage requires Windows")
    if not isinstance(token, str) or not 1 <= len(token) <= 64 or not token.isascii():
        raise ValueError("invalid VTS token")
    try:
        import win32crypt
    except ImportError as exc:
        raise VTSBridgeError("pywin32 is required for Windows DPAPI") from exc
    target = path if path is not None else _token_path()
    if target.is_symlink() or target.exists():
        raise FileExistsError("VTS owner token already staged; refusing overwrite")
    target.parent.mkdir(parents=True, exist_ok=True)
    protected = win32crypt.CryptProtectData(
        token.encode("ascii"), "Sofia VTube Studio plugin", None, None, None, 0
    )
    # The current Windows user's profile ACL and DPAPI both protect this file.
    with target.open("xb") as file:
        file.write(protected)
    return target


def load_owner_token(*, path: Path | None = None) -> str:
    if sys.platform != "win32":
        raise VTSBridgeError("DPAPI token loading requires Windows")
    try:
        import win32crypt
    except ImportError as exc:
        raise VTSBridgeError("pywin32 is required for Windows DPAPI") from exc
    target = path if path is not None else _token_path()
    if target.is_symlink() or not target.is_file() or target.stat().st_size > 4096:
        raise VTSBridgeError("owner-approved VTS token is missing or invalid")
    try:
        token = win32crypt.CryptUnprotectData(target.read_bytes(), None, None, None, 0)[1]
        result = token.decode("ascii")
        if not 1 <= len(result) <= 64:
            raise ValueError("invalid token length")
        return result
    except (UnicodeDecodeError, ValueError, OSError) as exc:
        raise VTSBridgeError("could not decrypt the VTS token for this Windows user") from exc


def request(message_type: str, data: dict | None = None, *, request_id: str | None = None) -> dict:
    """Build a bounded, deterministic API envelope (no untrusted message types)."""
    allowed = {
        "APIStateRequest", "AuthenticationTokenRequest", "AuthenticationRequest",
        "CurrentModelRequest", "InputParameterListRequest",
        "HotkeysInCurrentModelRequest", "HotkeyTriggerRequest",
        "InjectParameterDataRequest",
    }
    if message_type not in allowed:
        raise ValueError("unsupported VTS request type")
    request_id = request_id or uuid4().hex
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 64 or not request_id.isascii():
        raise ValueError("invalid VTS request id")
    if data is not None and not isinstance(data, dict):
        raise TypeError("VTS data must be a mapping")
    payload = {
        "apiName": _API, "apiVersion": "1.0",
        "requestID": request_id, "messageType": message_type,
    }
    if data is not None:
        payload["data"] = data
    return payload


class VTubeStudioBridge:
    """Thin VTube Studio plugin client; connection is explicit and localhost-only.

    A fake socket with send/recv/close is accepted for offline tests.
    """
    def __init__(self, socket, *, port: int = 8001):
        _port(port)
        self._socket = socket
        self.port = port
        self._authenticated = False
        self._closed = False

    @classmethod
    def connect_local(cls, *, port: int = 8001):
        _port(port)
        try:
            from websockets.sync.client import connect
        except ImportError as exc:
            raise VTSBridgeError(
                "Install optional VTube Studio support: pip install 'websockets>=14,<17'"
            ) from exc
        options = {
            "open_timeout": 5,
            "close_timeout": 2,
            "max_size": _MAX_MESSAGE,
        }
        # websockets 15+ honors OS proxy variables by default. Even a local
        # connection may be sent through a system proxy if its bypass list is
        # incomplete. Explicitly bypass proxies when the API is 127.0.0.1.
        # websockets 14 has no proxy option and connects directly already.
        if "proxy" in inspect.signature(connect).parameters:
            options["proxy"] = None
        try:
            connection = connect(f"ws://127.0.0.1:{port}", **options)
        except Exception as exc:
            # Never print a potentially sensitive proxy or connection URL.
            raise VTSBridgeError(
                f"WebSocket handshake to 127.0.0.1:{port} failed "
                f"({type(exc).__name__}). Confirm VTS API is running "
                "and the same port is selected."
            ) from exc
        return cls(connection, port=port)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._authenticated = False
            self._socket.close()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _tb):
        self.close()

    def _send(self, message_type: str, data: dict | None = None, *, timeout: int = _STATUS_TIMEOUT) -> dict:
        if self._closed:
            raise VTSBridgeError("VTS connection is closed")
        envelope = request(message_type, data)
        try:
            self._socket.send(json.dumps(envelope, separators=(",", ":")))
        except Exception as exc:
            self._authenticated = False
            raise VTSBridgeError(
                f"VTS WebSocket send failed ({type(exc).__name__}); "
                "check that VTube Studio is still running"
            ) from exc
        try:
            raw = self._socket.recv(timeout=timeout)
        except TimeoutError as exc:
            self._authenticated = False
            raise VTSBridgeError(
                f"VTS did not reply to {message_type} within {timeout}s. "
                "Check VTube Studio's Requests received counter and port."
            ) from exc
        except Exception as exc:
            self._authenticated = False
            raise VTSBridgeError(
                f"VTS WebSocket receive failed ({type(exc).__name__}); "
                "check VTube Studio and the local connection"
            ) from exc
        if not isinstance(raw, str) or len(raw) > _MAX_MESSAGE:
            raise VTSBridgeError("invalid VTS response size or encoding")
        try:
            response = json.loads(raw)
        except ValueError as exc:
            raise VTSBridgeError("VTS returned invalid JSON") from exc
        if not isinstance(response, dict) or (
            response.get("apiName") != _API
            or response.get("requestID") != envelope["requestID"]
        ):
            raise VTSBridgeError("VTS response did not match the request")
        if response.get("messageType") == "APIError":
            error_data = response.get("data", {})
            code = error_data.get("errorID") if isinstance(error_data, dict) else None
            raise VTSBridgeError(f"VTS rejected {message_type} (error ID: {code})")
        expected_type = message_type.removesuffix("Request") + "Response"
        if response.get("messageType") != expected_type or not isinstance(response.get("data"), dict):
            raise VTSBridgeError("unexpected VTS response type")
        return response["data"]

    def api_status(self) -> dict:
        data = self._send("APIStateRequest")
        return {
            "active": data.get("active") is True,
            "version": str(data.get("vTubeStudioVersion", ""))[:32],
            "session_authenticated": data.get("currentSessionAuthenticated") is True,
        }

    def pair_with_owner_popup(self) -> str:
        """Explicit invocation triggers VTS's own owner approval dialog.

        Token is returned ONLY to the in-process caller, never printed.
        Call save_owner_token() only after successful authentication.
        """
        data = self._send("AuthenticationTokenRequest", {
            "pluginName": _PLUGIN_NAME, "pluginDeveloper": _PLUGIN_DEVELOPER,
        }, timeout=90)
        token = data.get("authenticationToken")
        if not isinstance(token, str) or not 1 <= len(token) <= 64 or not token.isascii():
            raise VTSBridgeError("VTS did not return an owner-approved token")
        self.authenticate(token)
        return token

    def authenticate(self, token: str) -> bool:
        if not isinstance(token, str) or not token:
            raise ValueError("nonempty VTS auth token required")
        data = self._send("AuthenticationRequest", {
            "pluginName": _PLUGIN_NAME, "pluginDeveloper": _PLUGIN_DEVELOPER,
            "authenticationToken": token,
        })
        self._authenticated = data.get("authenticated") is True
        if not self._authenticated:
            raise VTSBridgeError("VTS owner authorization failed or was revoked")
        return True

    def _require_authenticated(self) -> None:
        if not self._authenticated or self._closed:
            raise PermissionError("owner-authenticated VTube Studio session required")

    def current_model(self) -> dict:
        self._require_authenticated()
        data = self._send("CurrentModelRequest")
        return {
            "loaded": data.get("modelLoaded") is True,
            "name": str(data.get("modelName", ""))[:128],
            "has_physics": data.get("hasPhysicsFile") is True,
        }

    def parameter_names(self) -> frozenset[str]:
        """Read available tracking INPUT identifiers; don't invent parameters."""
        self._require_authenticated()
        data = self._send("InputParameterListRequest")
        names = set()
        for field in ("defaultParameters", "customParameters"):
            for item in data.get(field, []):
                if isinstance(item, dict) and isinstance(item.get("name"), str):
                    names.add(item["name"])
        return frozenset(names)

    def send_parameter_frame(
        self, values: dict[str, float], *, owner_allowed: frozenset[str],
        available: frozenset[str],
    ) -> None:
        """One animation frame. The scheduler/lip-sync bridge is NOT wired yet.

        No self-starting frame pump. Only caller-authorized and actually
        available tracking inputs can be driven by Sofía.
        """
        self._require_authenticated()
        if not isinstance(values, dict) or not 1 <= len(values) <= 16:
            raise ValueError("expected between 1 and 16 parameter values")
        if not isinstance(owner_allowed, frozenset) or not isinstance(available, frozenset):
            raise TypeError("verified parameter allowlists required")
        checked = []
        for name, value in values.items():
            if not isinstance(name, str) or name not in owner_allowed or name not in available:
                raise PermissionError("parameter not approved and verified in loaded VTS model")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("parameter value must be finite numeric")
            if not -1000000 <= value <= 1000000:
                raise ValueError("VTS parameter outside documented bounds")
            checked.append({"id": name, "value": float(value)})
        self._send("InjectParameterDataRequest", {
            "faceFound": False, "mode": "set", "parameterValues": checked,
        })

    def trigger_approved_hotkey(
        self, hotkey_id: str, *, owner_allowed: frozenset[str],
    ) -> None:
        self._require_authenticated()
        if (
            not isinstance(hotkey_id, str) or not hotkey_id
            or hotkey_id not in owner_allowed
        ):
            raise PermissionError("hotkey not explicitly allowlisted by owner")
        self._send("HotkeyTriggerRequest", {"hotkeyID": hotkey_id})


def diagnose_local(*, port: int = 8001) -> dict:
    """Read-only local TCP/WebSocket/API status diagnostic, no pairing."""
    _port(port)
    result = {
        "target": f"127.0.0.1:{port}",
        "tcp_open": False,
        "websocket_open": False,
        "api_active": False,
    }
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3):
            result["tcp_open"] = True
    except OSError as exc:
        result["error_stage"] = "tcp"
        result["error_class"] = type(exc).__name__
        return result
    try:
        with VTubeStudioBridge.connect_local(port=port) as bridge:
            result["websocket_open"] = True
            status = bridge.api_status()
            result["api_active"] = status["active"]
            result["version"] = status["version"]
    except VTSBridgeError as exc:
        # This diagnostic is safe: errors are internally sanitized and do
        # not contain credentials or the raw WebSocket response.
        result["error_stage"] = "websocket_or_api"
        result["error"] = str(exc)
    return result


def saved_authorization_status() -> dict:
    """Read-only metadata. Never decrypt or expose a plugin token."""
    path = _token_path()
    return {
        "token_saved": path.is_file() and not path.is_symlink(),
        "storage": "Windows DPAPI (current Windows user)",
        "automatic_reauthentication_available": path.is_file() and not path.is_symlink(),
    }


def reconnect_saved_session(*, port: int = 8001) -> dict:
    """One owner-authorized reuse of a saved token, without any popup.

    Does not start VTS, activate a model, inject parameters, or modify
    presentation/wardrobe state. Can run at owner-session startup.
    """
    _port(port)
    token = load_owner_token()
    with VTubeStudioBridge.connect_local(port=port) as bridge:
        bridge.authenticate(token)
        model = bridge.current_model()
        return {
            "connected": True, "reused_saved_authorization": True,
            "model_loaded": model["loaded"],
            "model_name": model["name"],
            "production_activated": False,
        }


def watch_saved_connection(
    *, port: int = 8001, interval_seconds: float = 10,
    should_stop=None, sleep=None, connect=None, on_status=None,
) -> None:
    """Opt-in owner-session reconnection loop, without permission popups.

    This is transport keepalive only. No model loading, camera access, speech
    events, private art, game activity, or parameters are requested. A future
    user-session controller may call this while Sofía is running; a Windows
    service in a different DPAPI identity cannot access this user's token.
    """
    _port(port)
    if (
        isinstance(interval_seconds, bool)
        or not isinstance(interval_seconds, (int, float))
        or not math.isfinite(interval_seconds)
        or not 2 <= interval_seconds <= 120
    ):
        raise ValueError("reconnection interval must be 2 to 120 seconds")
    token = load_owner_token()  # fail closed if approval was never stored
    stop = should_stop if should_stop is not None else (lambda: False)
    pause = sleep if sleep is not None else time.sleep
    connector = connect if connect is not None else VTubeStudioBridge.connect_local
    emit = on_status if on_status is not None else (lambda _status: None)
    previous = None

    def transition(status: str) -> None:
        nonlocal previous
        if status != previous:
            previous = status
            emit(status)

    while not stop():
        try:
            with connector(port=port) as bridge:
                # Distinguish a revoked token from a transient socket failure.
                # Never ask VTS for another token automatically.
                try:
                    bridge.authenticate(token)
                except VTSBridgeError as exc:
                    raise PermissionError(
                        "VTube Studio refused saved owner authorization; "
                        "explicit re-enrollment is required"
                    ) from exc
                transition("connected")
                while not stop():
                    status = bridge.api_status()
                    if not status["active"]:
                        raise VTSBridgeError("VTube Studio API is no longer active")
                    if not stop():
                        pause(interval_seconds)
        except VTSBridgeError:
            if stop():
                break
            transition("waiting_for_vtube_studio")
            pause(interval_seconds)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicit local VTube Studio API status and owner pairing; no avatar activation"
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--status", action="store_true", help="Read unauthenticated API availability")
    modes.add_argument("--diagnose", action="store_true", help="Read-only TCP/WebSocket/API diagnostic without pairing")
    modes.add_argument("--pair", action="store_true", help="Ask VTS to show owner permission popup; DPAPI-store token")
    modes.add_argument("--model", action="store_true", help="Read model info using approved saved token")
    modes.add_argument("--credential-status", action="store_true", help="Check for the saved DPAPI token without opening VTS")
    modes.add_argument("--reconnect", action="store_true", help="Reuse saved permission for one local connection, without a popup")
    modes.add_argument("--watch", action="store_true", help="Keep reconnecting with saved permission until Ctrl+C; no avatar control")
    parser.add_argument("--interval", type=float, default=10, help="Seconds between --watch checks (2 to 120)")
    parser.add_argument("--port", type=int, default=8001, help="VTube Studio local API port")
    args = parser.parse_args(argv)
    try:
        _port(args.port)
        if args.diagnose:
            report = diagnose_local(port=args.port)
            print(json.dumps(report, indent=2))
            return 0 if report["api_active"] else 2
        if args.credential_status:
            report = saved_authorization_status()
            print(json.dumps(report, indent=2))
            return 0 if report["token_saved"] else 2
        if args.reconnect:
            print(json.dumps(reconnect_saved_session(port=args.port), indent=2))
            return 0
        if args.watch:
            def report_status(value):
                print(json.dumps({"vtube_studio": value, "port": args.port}), flush=True)
            try:
                watch_saved_connection(
                    port=args.port, interval_seconds=args.interval,
                    on_status=report_status,
                )
            except KeyboardInterrupt:
                print(json.dumps({"vtube_studio": "stopped_by_owner"}))
            return 0
        if args.pair and _token_path().exists():
            raise VTSBridgeError("VTS token already saved: refuse silent credential replacement")
        with VTubeStudioBridge.connect_local(port=args.port) as bridge:
            if args.status:
                result = bridge.api_status()
            elif args.pair:
                token = bridge.pair_with_owner_popup()
                save_owner_token(token)
                result = {"paired": True, "stored_using": "Windows DPAPI", "production_activated": False}
            else:
                bridge.authenticate(load_owner_token())
                result = bridge.current_model()
        print(json.dumps(result, indent=2))
        return 0
    except (VTSBridgeError, ValueError, PermissionError, FileExistsError) as exc:
        parser.exit(2, f"VTube Studio: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
