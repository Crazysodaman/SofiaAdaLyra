"""Service-owned, read-only management dispatch behind a fresh peer verifier.

This is an *internal* dispatch boundary, NOT an exposed IPC socket/listener.
The OS peer identifier must be supplied by a trusted transport adapter, not
from the untrusted request. The verifier must recheck current enrollment,
revocation, user session and scoped access on EVERY invocation. Do not wire an
external transport before those checks exist. No settings writes, approvals,
Core activation, or module lifecycle operations live here.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Callable, Mapping

from sofia.sdk.platform_management import UntrustedManagementRead

_RESPONSE_SCHEMA = "aegis.platform.management.read-response.v1"
_MAX_RESPONSE = 64 * 1024
_ALLOWED_PROVIDERS = frozenset({
    "core.list", "module.list", "fleet.list", "settings.inspect",
    "security.status", "updates.status", "diagnostics.summary", "jobs.list",
})


class ManagementReadDenied(PermissionError):
    """Untrusted or stale read request refused without disclosing data."""


@dataclass(frozen=True, slots=True)
class VerifiedReadPeer:
    """Result from the server-installed current peer/permission verifier.

    Construction of this object is NOT authentication. Only the server-owned
    verifier (which checks a real OS transport identity and current revocation)
    may return it to the dispatcher.
    """

    principal_id: str
    platform_id: str
    generation: int
    operations: frozenset[str]
    valid_until: datetime


def _verify_grant(grant: object, request: UntrustedManagementRead,
                  live: Mapping[str, object], now: datetime) -> None:
    if not isinstance(grant, VerifiedReadPeer):
        raise ManagementReadDenied("current verified peer grant required")
    if (not isinstance(grant.principal_id, str)
            or not grant.principal_id.strip()
            or len(grant.principal_id) > 160
            or type(grant.generation) is not int
            or grant.generation != request.expected_generation
            or grant.platform_id != request.target_platform_id
            or grant.platform_id != live["platform_id"]
            or grant.generation != live["generation"]
            or not isinstance(grant.operations, frozenset)
            or request.operation not in grant.operations
            or not all(op in (_ALLOWED_PROVIDERS | {"platform.status"})
                       for op in grant.operations)
            or not isinstance(grant.valid_until, datetime)
            or grant.valid_until.tzinfo is None
            or grant.valid_until.utcoffset() is None
            or grant.valid_until.astimezone(timezone.utc) <= now):
        raise ManagementReadDenied("current peer scope, target or generation refused")


def _verified_live(raw: object, request: UntrustedManagementRead) -> dict[str, object]:
    if not isinstance(raw, Mapping):
        raise ManagementReadDenied("live Platform state unavailable")
    required = {"platform_id", "generation", "core_started", "operator_stop"}
    if (not required.issubset(raw)
            or type(raw["generation"]) is not int
            or type(raw["core_started"]) is not bool
            or type(raw["operator_stop"]) is not bool
            or raw["core_started"] is not False
            or raw["generation"] != request.expected_generation
            or raw["platform_id"] != request.target_platform_id):
        raise ManagementReadDenied("Platform identity or live generation changed")
    # Do not export identity keys, local filesystem paths, private state or
    # original unreviewed fields from the underlying process health object.
    return {
        "platform_id": raw["platform_id"],
        "generation": raw["generation"],
        "core_started": False,
        "operator_stop": raw["operator_stop"],
        "observation": "CURRENT_LOCAL_PROCESS",
    }


class PlatformManagementReadDispatcher:
    """Binds strict request syntax to *fresh* service-side peer checks.

    The transport is responsible for obtaining the OS peer context securely.
    Providers must be reviewed, scoped, read-only callbacks installed by the
    Platform composition root. They must NOT return credential material.
    """

    def __init__(
        self, *,
        current_peer_grant: Callable[[object, UntrustedManagementRead], object],
        live_status: Callable[[], object],
        providers: Mapping[str, Callable[[], object]],
        clock: Callable[[], datetime],
    ):
        if (not callable(current_peer_grant) or not callable(live_status)
                or not isinstance(providers, Mapping)
                or not set(providers).issubset(_ALLOWED_PROVIDERS)
                or any(not callable(provider) for provider in providers.values())
                or not callable(clock)):
            raise TypeError("reviewed live peer verifier and read-only providers required")
        self._peer_grant = current_peer_grant
        self._live_status = live_status
        self._providers = dict(providers)
        self._clock = clock

    def handle(self, raw: bytes, *, transport_peer: object) -> bytes:
        """Return bounded JSON only after before/after revalidation.

        No mutation capability is accepted. A failed request never calls a
        provider. On midflight peer revocation/STOP state loss/generation
        change, the observed payload is discarded before any bytes are sent.
        """
        instant = self._clock()
        if (not isinstance(instant, datetime) or instant.tzinfo is None
                or instant.utcoffset() is None):
            raise ValueError("service clock must be timezone aware")
        moment = instant.astimezone(timezone.utc)
        request = UntrustedManagementRead.parse(raw, now=moment)
        # Recheck current principal enrollment/revocation using OS peer data
        # before observing canonical state or touching any provider.
        grant = self._peer_grant(transport_peer, request)
        if not isinstance(grant, VerifiedReadPeer):
            raise ManagementReadDenied("current verified peer grant required")
        before = _verified_live(self._live_status(), request)
        _verify_grant(grant, request, before, moment)
        if request.operation == "platform.status":
            observed: object = before
        else:
            provider = self._providers.get(request.operation)
            if provider is None:
                raise ManagementReadDenied("reviewed provider not installed")
            observed = provider()
        # A provider can block: never return values under stale authorization.
        next_instant = self._clock()
        if (not isinstance(next_instant, datetime)
                or next_instant.tzinfo is None
                or next_instant.utcoffset() is None):
            raise ManagementReadDenied("current service clock unavailable")
        next_moment = next_instant.astimezone(timezone.utc)
        if next_moment < moment:
            raise ManagementReadDenied("service clock moved backwards")
        # Never release an observation obtained while a request expired.
        UntrustedManagementRead.parse(raw, now=next_moment)
        new_grant = self._peer_grant(transport_peer, request)
        after = _verified_live(self._live_status(), request)
        _verify_grant(new_grant, request, after, next_moment)
        # STOP is observable, never an authorization grant. This read-only
        # handler deliberately exposes no side-effect operation while stopped.
        result = {
            "schema": _RESPONSE_SCHEMA,
            "protocol": "1.0",
            "request_id": request.request_id,
            "platform_id": request.target_platform_id,
            "generation": request.expected_generation,
            "operation": request.operation,
            "status": "OBSERVED",
            "data": observed,
        }
        try:
            output = json.dumps(
                result, sort_keys=True, separators=(",", ":"),
                ensure_ascii=True, allow_nan=False,
            ).encode("ascii")
        except (TypeError, ValueError, OverflowError) as error:
            raise ManagementReadDenied("provider returned invalid read data") from error
        if len(output) > _MAX_RESPONSE:
            raise ManagementReadDenied("provider output exceeded response limit")
        return output
