"""Platform-owned, fail-closed read dispatch for the versioned management API.

This is service-side dispatch, NOT an IPC listener, credential verifier or
authentication provider. Only an authenticated transport can supply the
opaque peer handle; it is revalidated before AND after every provider call.
Owner approval/write operations, remote Fleet access and real Core startup
do not exist in this module. Providers must return authorized scoped views.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Callable, Mapping

from sofia.sdk.platform_management import UntrustedManagementRead

MAX_RESULT_BYTES = 32 * 1024
ALLOWED_OPERATIONS = frozenset({
    "platform.status", "core.list", "module.list", "fleet.list",
    "settings.inspect", "security.status", "updates.status",
    "diagnostics.summary", "jobs.list",
})

ReadProvider = Callable[[], Mapping[str, object]]
PeerAuthorizer = Callable[[object, str], bool]
CurrentIdentity = Callable[[], tuple[str, int]]
StopObserver = Callable[[], bool]
Clock = Callable[[], datetime]


class ManagementReadDenied(PermissionError):
    """A missing, revoked or inconsistent authority/projection."""


@dataclass(frozen=True, slots=True)
class ManagementReadResult:
    request_id: str
    platform_id: str
    generation: int
    observed_at: str
    operation: str
    payload: Mapping[str, object]

    def to_json(self) -> bytes:
        return json.dumps({
            "schema": "aegis.platform.management.response.v1",
            "request_id": self.request_id,
            "platform_id": self.platform_id,
            "generation": self.generation,
            "observed_at": self.observed_at,
            "operation": self.operation,
            "payload": self.payload,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            allow_nan=False).encode("utf-8")


def _no_secret_keys(value: object, depth: int = 0) -> None:
    """Refuse accidental unscoped sensitive fields from a provider."""
    if depth > 8:
        raise ManagementReadDenied("projection nesting is unbounded")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ManagementReadDenied("non-text projection key")
            normalized = key.lower()
            if (normalized in {"__proto__", "constructor", "prototype"}
                    or any(part in normalized for part in (
                        "secret", "password", "access_token", "private_key",
                        "credential", "refresh_token", "api_key",
                    ))):
                raise ManagementReadDenied("sensitive field in read projection")
            _no_secret_keys(item, depth + 1)
    elif isinstance(value, (list, tuple)):
        if len(value) > 1024:
            raise ManagementReadDenied("too many projection items")
        for item in value:
            _no_secret_keys(item, depth + 1)
    elif value is None or type(value) in (str, int, float, bool):
        return
    else:
        raise ManagementReadDenied("unsupported projection value")


class PlatformManagementReadDispatcher:
    """No network binding and no canonical DB writer of its own.

    The transport supplies only its opaque OS-authenticated peer handle.
    Both the current-authorization callback and state-generation check must
    resolve against live Platform-owned sources, not cached UI state.
    """

    def __init__(
        self, *,
        authorize_peer: PeerAuthorizer,
        current_identity: CurrentIdentity,
        operator_stop_active: StopObserver,
        providers: Mapping[str, ReadProvider],
        clock: Clock,
    ) -> None:
        if not all(callable(fn) for fn in (
            authorize_peer, current_identity, operator_stop_active, clock,
        )):
            raise TypeError("live Platform authority callbacks required")
        if not isinstance(providers, Mapping) or not providers:
            raise TypeError("reviewed read providers required")
        if not set(providers) <= ALLOWED_OPERATIONS or any(
            not callable(provider) for provider in providers.values()
        ):
            raise ValueError("only reviewed read providers may be registered")
        self._authorize_peer = authorize_peer
        self._current_identity = current_identity
        self._operator_stop_active = operator_stop_active
        self._providers = dict(providers)
        self._clock = clock

    def _authorize(self, peer: object, request: UntrustedManagementRead) -> None:
        if peer is None or self._authorize_peer(peer, request.operation) is not True:
            raise ManagementReadDenied("current peer authorization denied")
        platform_id, generation = self._current_identity()
        if (platform_id != request.target_platform_id
                or type(generation) is not int
                or generation != request.expected_generation
                or self._operator_stop_active() is not False):
            raise ManagementReadDenied("Platform generation, identity or STOP mismatch")

    def read(self, raw: bytes, *, peer: object) -> ManagementReadResult:
        timestamp = self._clock()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ManagementReadDenied("authoritative wall clock unavailable")
        request = UntrustedManagementRead.parse(raw, now=timestamp)
        provider = self._providers.get(request.operation)
        if provider is None:
            raise ManagementReadDenied("requested read provider unavailable")

        self._authorize(peer, request)
        projected = provider()
        if not isinstance(projected, dict):
            raise ManagementReadDenied("provider returned unscoped projection")
        # Clone exactly once. A provider may own a mutable dict and change it
        # after return; never authorize one object and later serialize another.
        try:
            serialized = json.dumps(
                projected, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
            if len(serialized) > MAX_RESULT_BYTES:
                raise ManagementReadDenied("management read result exceeds limit")
            bounded_snapshot = json.loads(serialized)
        except (ValueError, TypeError, OverflowError, RecursionError) as error:
            raise ManagementReadDenied("unserializable read projection") from error
        _no_secret_keys(bounded_snapshot)
        observed_at = self._clock()
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ManagementReadDenied("authoritative wall clock unavailable")
        # Re-evaluate active principal/revocation/STOP/generation after the
        # potentially slow provider. Never deliver data that outlived authority.
        self._authorize(peer, request)
        if (observed_at < timestamp or observed_at >= datetime.fromisoformat(
                request.deadline.replace("Z", "+00:00"))):
            raise ManagementReadDenied("provider result exceeded request deadline")
        result = ManagementReadResult(
            request_id=request.request_id,
            platform_id=request.target_platform_id,
            generation=request.expected_generation,
            observed_at=observed_at.astimezone(timezone.utc).isoformat(),
            operation=request.operation,
            payload=bounded_snapshot,
        )
        try:
            encoded = result.to_json()
        except (ValueError, TypeError, OverflowError) as error:
            raise ManagementReadDenied("unserializable read projection") from error
        if len(encoded) > MAX_RESULT_BYTES:
            raise ManagementReadDenied("management read result exceeds limit")
        return result
