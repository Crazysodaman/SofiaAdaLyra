"""Fleet protocol compatibility primitives used before remote activation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True, slots=True)
class FleetProtocolVersion:
    major: int
    minor: int = 0

    def __post_init__(self) -> None:
        if type(self.major) is not int or self.major < 0:
            raise ValueError("major protocol version must be >= 0")
        if type(self.minor) is not int or self.minor < 0:
            raise ValueError("minor protocol version must be >= 0")

    @property
    def revision(self) -> int:
        """Stable integer form suitable for release compatibility windows."""
        return self.major * 1_000_000 + self.minor


@dataclass(frozen=True, slots=True)
class FleetProtocolWindow:
    minimum: FleetProtocolVersion
    maximum: FleetProtocolVersion

    def __post_init__(self) -> None:
        if not isinstance(self.minimum, FleetProtocolVersion):
            raise TypeError("minimum must be FleetProtocolVersion")
        if not isinstance(self.maximum, FleetProtocolVersion):
            raise TypeError("maximum must be FleetProtocolVersion")
        if self.maximum < self.minimum:
            raise ValueError("protocol maximum must be >= minimum")

    def accepts(self, version: FleetProtocolVersion) -> bool:
        if not isinstance(version, FleetProtocolVersion):
            raise TypeError("version must be FleetProtocolVersion")
        return self.minimum <= version <= self.maximum
