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
from pathlib import Path
import sys
from uuid import uuid4

_PLUGIN_NAME = "Sofia Ada Lyra"
_PLUGIN_DEVELOPER = "SofiaAdaLyra"
_API = "VTubeStudioPublicAPI"
_MAX_MESSAGE = 128_000


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
        try:
            socket = connect(
                f"ws://127.0.0.1:{port}",
                open_timeout=3,
                close_timeout=2,
                max_size=_MAX_MESSAGE,
            )
        except OSError as exc:
            raise VTSBridgeError(
                "VTube Studio local API unavailable; start VTS and enable Plugin API access"
            ) from exc
        return cls(socket, port=port)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._authenticated = False
            self._socket.close()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value, _tb):
        self.close()

    def _send(self, message_type: str, data: dict | None = None, *, timeout: int = 3) -> dict:
        if self._closed:
            raise VTSBridgeError("VTS connection is closed")
        envelope = request(message_type, data)
        try:
            self._socket.send(json.dumps(envelope, separators=(",", ":")))
            raw = self._socket.recv(timeout=timeout)
        except Exception as exc:
            # Optional WebSocket libraries expose their own closed/timeout
            # exception families. Never include raw responses or credentials.
            self._authenticated = False
            raise VTSBridgeError("VTS request failed; connection or timeout") from exc
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Explicit local VTube Studio API status and owner pairing; no avatar activation"
    )
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--status", action="store_true", help="Read unauthenticated API availability")
    modes.add_argument("--pair", action="store_true", help="Ask VTS to show owner permission popup; DPAPI-store token")
    modes.add_argument("--model", action="store_true", help="Read model info using approved saved token")
    parser.add_argument("--port", type=int, default=8001, help="VTube Studio local API port")
    args = parser.parse_args(argv)
    try:
        _port(args.port)
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
