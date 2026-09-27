from __future__ import annotations

from dataclasses import dataclass
import re

_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


@dataclass(frozen=True, order=True, slots=True)
class FleetProtocolVersion:
    major: int
    minor: int

    def __post_init__(self) -> None:
        if type(self.major) is not int or self.major < 0:
            raise ValueError("major must be a nonnegative integer")
        if type(self.minor) is not int or self.minor < 0:
            raise ValueError("minor must be a nonnegative integer")

    @classmethod
    def parse(cls, value: str) -> "FleetProtocolVersion":
        if not isinstance(value, str):
            raise TypeError("protocol version must be a string")
        match = _VERSION.fullmatch(value.strip())
        if match is None:
            raise ValueError("protocol version must use MAJOR.MINOR")
        return cls(int(match.group(1)), int(match.group(2)))

    def compatible_with(self, required: "FleetProtocolVersion") -> bool:
        if not isinstance(required, FleetProtocolVersion):
            raise TypeError("required must be a FleetProtocolVersion")
        return self.major == required.major and self.minor >= required.minor

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"


CURRENT_FLEET_PROTOCOL_VERSION = FleetProtocolVersion(1, 0)
