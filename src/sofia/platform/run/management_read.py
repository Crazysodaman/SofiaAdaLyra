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
from datetime import datetime
import re
from typing import Any

from sofia.platform.config.settings_authority import SettingsOwner
from sofia.sdk.platform_management import UntrustedManagementRead

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
    ) -> None:
        self._status = current_status
        self._authorize = authorize
        self._settings = read_settings

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
        if request.operation not in {"platform.status", "settings.inspect"}:
            raise ManagementReadDenied("management operation not implemented")
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
        return {
            "schema": "aegis.platform.management.read-response.v1",
            "protocol": "1.0",
            "request_id": request.request_id,
            "platform_id": request.target_platform_id,
            "platform_generation": request.expected_generation,
            "operation": request.operation,
            "source": "PLATFORM_SESSION",
            "data": observation,
        }
