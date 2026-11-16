"""Platform-owned, fail-closed *read-only* management request dispatch.

No transport is opened here. Only an OS-authenticated Platform session may
supply the peer identity and current authority callback. In particular,
untrusted JSON is never an owner grant or settings write permission.

The authority callback is checked both before and after retrieving data,
including the current STOP state and process generation, to fence revocation
and replacement between request admission and response publication.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import json
import re
from typing import Any

from sofia.platform.config.settings_authority import SettingsOwner, runtime_settings_contracts
from sofia.sdk.platform_management import UntrustedManagementRead
from sofia.sdk.platform_management_response import make_response

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,159}$")
_RFC3339 = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_STATUS_FIELDS = frozenset({
    "platform_id", "generation", "operator_stop", "core_started",
})
_STARTUP_FIELDS = frozenset({
    "platform_id", "generation", "operator_stop", "core_started",
    "core_count", "active_core_count", "startup_state",
    "autostart_enabled_count", "autostart_reconciled_at",
    "management_listening",
})
_STARTUP_STATES = frozenset({
    "ZERO_CORE_HEALTHY", "CORES_RUNNING", "DEGRADED", "UNKNOWN",
})
_MAX_COUNT = 65535


class ManagementReadDenied(PermissionError):
    """No management disclosure or authority is available."""


class ManagementReadDispatcher:
    """A scoped read dispatcher for one trusted PlatformServiceSession.

    current_status must resolve fresh installation identity, lease and STOP.
    authorize must resolve the transport-verified peer against current owner
    enrollment/revocation for this exact operation. Returning None denies.
    read_settings must use the canonical SettingsService with service-chosen
    owner scopes. read_startup must be a service-owned bounded projection of
    current startup state; it is never supplied by a client. None of these
    callbacks may be client-provided.
    """

    def __init__(
        self, *,
        current_status: Callable[[], Mapping[str, object]],
        authorize: Callable[[str, str], frozenset[SettingsOwner] | None],
        read_settings: Callable[[frozenset[SettingsOwner]], Mapping[str, Any]],
        read_startup: Callable[[], Mapping[str, Any]] | None = None,
        clock: Callable[[], datetime] | None = None,
        enrolled_denial_responses: bool = False,
    ) -> None:
        if type(enrolled_denial_responses) is not bool:
            raise TypeError("explicit enrolled-denial policy must be bool")
        if read_startup is not None and not callable(read_startup):
            raise TypeError("service-owned startup status reader must be callable")
        self._status = current_status
        self._authorize = authorize
        self._settings = read_settings
        self._startup = read_startup
        self._clock = clock if clock is not None else lambda: datetime.now(timezone.utc)
        self._enrolled_denials = enrolled_denial_responses

    def _check(
        self, request: UntrustedManagementRead, authenticated_peer: str
    ) -> frozenset[SettingsOwner]:
        if (not isinstance(authenticated_peer, str)
                or _ID.fullmatch(authenticated_peer) is None):
            raise ManagementReadDenied("missing authenticated OS peer identity")
        status = self._status()
        if (not isinstance(status, Mapping)
                or not _STATUS_FIELDS.issubset(status)
                or status["platform_id"] != request.target_platform_id
                or type(status["generation"]) is not int
                or status["generation"] != request.expected_generation
                or status["operator_stop"] is not False
                or type(status["core_started"]) is not bool):
            raise ManagementReadDenied("current Platform identity, generation or STOP unavailable")
        scope = self._authorize(authenticated_peer, request.operation)
        if not isinstance(scope, frozenset) or any(
            not isinstance(owner, SettingsOwner) for owner in scope
        ):
            raise ManagementReadDenied("current peer authorization unavailable")
        # Even read-only Platform status is private unless the OS peer and
        # current owner enrollment were explicitly accepted by Platform.
        if request.operation == "settings.inspect" and not scope:
            raise ManagementReadDenied("settings read scope required")
        return scope

    def _startup_projection(
        self, request: UntrustedManagementRead
    ) -> dict[str, object]:
        reader = self._startup
        if reader is None:
            raise ManagementReadDenied("startup status reader unavailable")
        provided = reader()
        if (not isinstance(provided, Mapping)
                or not _STARTUP_FIELDS.issubset(provided)):
            raise ManagementReadDenied("incomplete startup status projection")
        # Project only the reviewed fields. Any additional service data is
        # dropped rather than disclosed.
        data = {name: provided[name] for name in _STARTUP_FIELDS}
        core_count = data["core_count"]
        active = data["active_core_count"]
        autostart = data["autostart_enabled_count"]
        state = data["startup_state"]
        reconciled = data["autostart_reconciled_at"]
        if (data["platform_id"] != request.target_platform_id
                or type(data["generation"]) is not int
                or data["generation"] != request.expected_generation
                or data["operator_stop"] is not False
                or type(data["core_started"]) is not bool
                or type(core_count) is not int
                or not 0 <= core_count <= _MAX_COUNT
                or type(active) is not int
                or not 0 <= active <= core_count
                or type(state) is not str
                or state not in _STARTUP_STATES
                or type(autostart) is not int
                or not 0 <= autostart <= _MAX_COUNT
                or type(data["management_listening"]) is not bool):
            raise ManagementReadDenied("invalid startup status projection")
        if reconciled is not None:
            if (type(reconciled) is not str
                    or _RFC3339.fullmatch(reconciled) is None):
                raise ManagementReadDenied("invalid startup reconciliation time")
            try:
                parsed = datetime.fromisoformat(reconciled.replace("Z", "+00:00"))
            except ValueError as error:
                raise ManagementReadDenied(
                    "invalid startup reconciliation time"
                ) from error
            if parsed.utcoffset() is None:
                raise ManagementReadDenied(
                    "startup reconciliation time lacks timezone"
                )
        if core_count == 0 and (active != 0 or data["core_started"]):
            raise ManagementReadDenied("inconsistent zero-core startup status")
        if state == "ZERO_CORE_HEALTHY" and core_count != 0:
            raise ManagementReadDenied("inconsistent zero-core startup state")
        if state == "CORES_RUNNING" and active == 0:
            raise ManagementReadDenied("inconsistent running-core startup state")
        return data

    def _deny(
        self, request: UntrustedManagementRead, authenticated_peer: str,
        scopes: frozenset[SettingsOwner], code: str,
    ) -> dict[str, object]:
        if self._check(request, authenticated_peer) != scopes:
            raise ManagementReadDenied("management scope changed during observation")
        observed = self._clock()
        if (not isinstance(observed, datetime)
                or observed.utcoffset() is None
                or observed >= datetime.fromisoformat(request.deadline.replace("Z", "+00:00"))):
            raise ManagementReadDenied("management request expired during observation")
        try:
            return make_response(request, observed_at=observed, denial_code=code)
        except (TypeError, ValueError, OverflowError) as error:
            raise ManagementReadDenied("unsafe management response") from error

    def dispatch(
        self, raw: bytes, *, authenticated_peer: str, now: datetime
    ) -> dict[str, object]:
        request = UntrustedManagementRead.parse(raw, now=now)
        if self._enrolled_denials:
            # Typed STOP/STALE is visible ONLY after kernel/pipe peer identity
            # and fresh exact owner enrollment are independently established.
            # A revoked/unknown principal still receives EOF, never a hint.
            if (not isinstance(authenticated_peer, str)
                    or _ID.fullmatch(authenticated_peer) is None):
                raise ManagementReadDenied("invalid authenticated peer")
            enrolled = self._authorize(authenticated_peer, request.operation)
            if not isinstance(enrolled, frozenset):
                raise ManagementReadDenied("no current owner enrollment")
            status = self._status()
            if not isinstance(status, Mapping) or status.get("platform_id") != request.target_platform_id:
                raise ManagementReadDenied("Platform identity unavailable")
            reason = None
            if status.get("operator_stop") is True:
                reason = "STOPPED"
            elif (type(status.get("generation")) is int
                    and status["generation"] != request.expected_generation):
                reason = "STALE_GENERATION"
            if reason is not None:
                if (self._authorize(authenticated_peer, request.operation) != enrolled
                        or self._status() != status):
                    raise ManagementReadDenied("management denial authority changed")
                observed = self._clock()
                if (not isinstance(observed, datetime)
                        or observed.utcoffset() is None
                        or observed >= datetime.fromisoformat(request.deadline.replace("Z", "+00:00"))):
                    raise ManagementReadDenied("management denial expired")
                return make_response(request, observed_at=observed, denial_code=reason)
        scopes = self._check(request, authenticated_peer)
        if request.operation == "settings.inspect":
            observation: dict[str, object] = dict(
                self._settings(scopes)
            )
            if set(observation) != {
                "schema_version", "revision", "effective_revision",
                "values", "contracts",
            }:
                raise ManagementReadDenied("unexpected canonical settings snapshot")
            values = observation["values"]
            contracts = observation["contracts"]
            if (not isinstance(values, Mapping)
                    or not isinstance(contracts, Mapping)
                    or set(values) != set(contracts)
                    or len(values) > 256):
                raise ManagementReadDenied("invalid scoped settings projection")
            authoritative_contracts = runtime_settings_contracts()
            for field, contract in contracts.items():
                if (not isinstance(field, str)
                        or not isinstance(contract, Mapping)
                        or set(contract) != {"owner", "apply_class"}):
                    raise ManagementReadDenied("invalid settings ownership contract")
                actual = authoritative_contracts.get(field)
                if (actual is None
                        or actual.owner is SettingsOwner.CLIENT
                        or actual.owner not in scopes
                        or contract["owner"] != actual.owner.value
                        or contract["apply_class"] != actual.apply_class.value):
                    raise ManagementReadDenied("settings disclosure outside approved scope")
        elif request.operation == "startup.status":
            if self._startup is None:
                return self._deny(
                    request, authenticated_peer, scopes, "NOT_PERMITTED",
                )
            observation = self._startup_projection(request)
        elif request.operation == "platform.status":
            status = self._status()
            if (not isinstance(status, Mapping)
                    or type(status.get("core_started")) is not bool):
                raise ManagementReadDenied("current Platform status unavailable")
            observation = {
                "platform_id": request.target_platform_id,
                "generation": request.expected_generation,
                "core_started": status["core_started"],
                "operator_stop": False,
            }
        else:
            return self._deny(
                request, authenticated_peer, scopes, "NOT_PERMITTED",
            )
        # An OS principal can be revoked or the Platform lease replaced while
        # reading settings. Never disclose a response after such a transition.
        if self._check(request, authenticated_peer) != scopes:
            raise ManagementReadDenied("management scope changed during observation")
        observed = self._clock()
        if (not isinstance(observed, datetime)
                or observed.utcoffset() is None
                or observed >= datetime.fromisoformat(request.deadline.replace("Z", "+00:00"))):
            raise ManagementReadDenied("management request expired during observation")
        try:
            return make_response(request, observed_at=observed, data=observation)
        except (TypeError, ValueError, OverflowError) as error:
            raise ManagementReadDenied("unsafe management response") from error
