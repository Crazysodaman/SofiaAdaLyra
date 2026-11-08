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
_STATUS_FIELDS = frozenset({
    "platform_id", "generation", "operator_stop", "core_started",
})


class ManagementReadDenied(PermissionError):
    """No management disclosure or authority is available."""


class ManagementReadDispatcher:
    """A scoped read dispatcher for one trusted PlatformServiceSession.

    current_status must resolve fresh installation identity, lease and STOP.
    authorize must resolve the transport-verified peer against current owner
    enrollment/revocation for this exact operation. Returning None denies.
    read_settings must use the canonical SettingsService with service-chosen
    owner scopes. None of these callbacks may be client-provided.
    """

    def __init__(
        self, *,
        current_status: Callable[[], Mapping[str, object]],
        authorize: Callable[[str, str], frozenset[SettingsOwner] | None],
        read_settings: Callable[[frozenset[SettingsOwner]], Mapping[str, Any]],
        clock: Callable[[], datetime] | None = None,
        enrolled_denial_responses: bool = False,
    ) -> None:
        if type(enrolled_denial_responses) is not bool:
            raise TypeError("explicit enrolled-denial policy must be bool")
        self._status = current_status
        self._authorize = authorize
        self._settings = read_settings
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
                or status["core_started"] is not False):
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
        if request.operation not in {"platform.status", "settings.inspect"}:
            if self._check(request, authenticated_peer) != scopes:
                raise ManagementReadDenied("management scope changed during observation")
            observed = self._clock()
            if observed >= datetime.fromisoformat(request.deadline.replace("Z", "+00:00")):
                raise ManagementReadDenied("request expired during dispatch")
            return make_response(request, observed_at=observed, denial_code="NOT_PERMITTED")
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
        else:
            observation = {
                "platform_id": request.target_platform_id,
                "generation": request.expected_generation,
                "core_started": False,
                "operator_stop": False,
            }
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
