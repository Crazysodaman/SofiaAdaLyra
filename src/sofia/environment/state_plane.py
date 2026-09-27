"""State Plane serialization for stable ENVIRONMENT configuration.

Current/fresh sensor observations remain freshness-bound provider evidence and
are not promoted into durable configuration by this adapter.
"""

from __future__ import annotations

import json

from sofia.environment.config import ConfiguredLocation
from sofia.environment.model import LocationSubject
from sofia.state_plane.model import (
    StateClass,
    StateKey,
    StateRecord,
    StateScope,
)


def configured_location_record(
    location: ConfiguredLocation,
    *,
    revision: int,
    principal_id: str | None = None,
    host_id: str | None = None,
) -> StateRecord:
    if not isinstance(location, ConfiguredLocation):
        raise TypeError("ConfiguredLocation required")
    payload = json.dumps(
        {
            "label": location.label,
            "timezone": location.timezone,
            "subject": location.subject.value,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "source_id": location.source_id,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    if location.subject is LocationSubject.USER:
        if not principal_id:
            raise ValueError("USER location requires principal_id")
        scope = StateScope.PRINCIPAL
        record_name = principal_id
    elif location.subject is LocationSubject.HOST:
        if not host_id:
            raise ValueError("HOST location requires host_id")
        scope = StateScope.HOST
        record_name = host_id
    else:
        scope = StateScope.GLOBAL
        record_name = "site"

    return StateRecord(
        key=StateKey("environment.configured_location", record_name),
        state_class=StateClass.SHARED_AUTHORITATIVE,
        owner_package="ENVIRONMENT",
        scope=scope,
        revision=revision,
        schema_revision=1,
        payload=payload,
        principal_id=principal_id if scope is StateScope.PRINCIPAL else None,
        host_id=host_id if scope is StateScope.HOST else None,
    )
