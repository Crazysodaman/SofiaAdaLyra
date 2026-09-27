"""Read-only UI projection for Fleet/release state."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FleetReleaseState(str, Enum):
    CURRENT = "current"
    OUTDATED = "outdated"
    CORRUPT = "corrupt"
    INCOMPATIBLE = "incompatible"
    QUARANTINED = "quarantined"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class FleetNodeView:
    host_id: str
    lifecycle: str
    release_state: FleetReleaseState
    release_id: str | None = None
    runtime_endpoint: str | None = None
    attention_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.host_id, str) or not self.host_id.strip():
            raise ValueError("host_id required")
        if not isinstance(self.lifecycle, str) or not self.lifecycle.strip():
            raise ValueError("lifecycle required")
        if not isinstance(self.release_state, FleetReleaseState):
            raise TypeError("release_state must be FleetReleaseState")
        if self.release_id is not None and not self.release_id.strip():
            raise ValueError("release_id must be nonempty when set")
        if self.runtime_endpoint is not None and not self.runtime_endpoint.strip():
            raise ValueError("runtime_endpoint must be nonempty when set")
