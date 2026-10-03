"""Typed Windows service identities for PKG-RUN.

This module is platform-neutral so CI can validate service wiring without
requiring pywin32 or a live Service Control Manager.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WindowsServiceSpec:
    name: str
    display_name: str
    description: str
    class_string: str
    delayed_auto_start: bool = True

    def __post_init__(self) -> None:
        for field_name in ("name", "display_name", "description", "class_string"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be nonempty")
        if type(self.delayed_auto_start) is not bool:
            raise TypeError("delayed_auto_start must be bool")


RUNTIME_SERVICE = WindowsServiceSpec(
    name="SofiaAdaLyra",
    display_name="Sofía Ada Lyra Runtime",
    description=(
        "Canonical headless Sofía Ada Lyra application runtime. "
        "Owns the local application lifecycle but does not grant distributed "
        "leadership or cross-host authority."
    ),
    class_string="sofia.run.runtime_service.SofiaRuntimeWindowsService",
)

WATCHDOG_SERVICE = WindowsServiceSpec(
    name="SofiaAdaLyraWatchdog",
    display_name="Sofía Ada Lyra Watchdog",
    description=(
        "Independent local RUN watchdog for the Sofía Ada Lyra runtime service. "
        "Uses the local lease/fencing and bounded restart policy."
    ),
    class_string="sofia.run.watchdog_service.SofiaWatchdogWindowsService",
)


def service_specs() -> tuple[WindowsServiceSpec, ...]:
    return (RUNTIME_SERVICE, WATCHDOG_SERVICE)
