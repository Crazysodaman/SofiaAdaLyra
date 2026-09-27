from __future__ import annotations

from datetime import datetime, timezone
import re

from sofia.config.authority import ConfigurationPrecedence, ConfigurationValue
from sofia.config.state_store import StatePlaneConfigurationStore
from sofia.state.plane import StatePlane

_CAPABILITY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}$")
_POLICY_KEY = "capabilities.enabled_extra"


def normalize_capabilities(values) -> tuple[str, ...]:
    if not isinstance(values, (tuple, list)):
        raise TypeError("capabilities must be a tuple or list")
    normalized=[]
    for value in values:
        if not isinstance(value, str) or _CAPABILITY.fullmatch(value) is None:
            raise ValueError("capability names must be bounded identifiers")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def protected_capability_extras(
    state_plane: StatePlane,
    *,
    now: datetime | None = None,
) -> tuple[str, ...]:
    if not isinstance(state_plane, StatePlane):
        raise TypeError("state_plane must be a StatePlane")
    moment=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    store=StatePlaneConfigurationStore(state_plane)
    value=store.resolve(_POLICY_KEY,now=moment)
    if value is None:
        return ()
    if value.precedence is not ConfigurationPrecedence.PROTECTED_POLICY:
        raise PermissionError(
            "standing capability policy must come from protected policy authority"
        )
    return normalize_capabilities(value.value)


def set_protected_capability_extras(
    state_plane: StatePlane,
    *,
    capabilities,
    actor_id: str = "operator:sparks",
    now: datetime | None = None,
) -> ConfigurationValue:
    if not isinstance(state_plane, StatePlane):
        raise TypeError("state_plane must be a StatePlane")
    if actor_id != "operator:sparks":
        raise PermissionError("standing capability policy requires Sparks authority")
    moment=(now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    normalized=normalize_capabilities(capabilities)
    store=StatePlaneConfigurationStore(state_plane)
    previous=store.values(_POLICY_KEY)
    revision=max((item.revision for item in previous),default=0)+1
    value=ConfigurationValue(
        key=_POLICY_KEY,
        value=list(normalized),
        precedence=ConfigurationPrecedence.PROTECTED_POLICY,
        revision=revision,
        source="safe:capability-policy",
        actor_id=actor_id,
        observed_at=moment,
    )
    store.put(value)
    return value
