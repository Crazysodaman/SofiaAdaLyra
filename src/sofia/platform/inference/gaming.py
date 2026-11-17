"""Gaming-aware admission policy for shared inference.

This policy expresses neutral platform rules, not any Core's personality.  It
defers autonomous work under foreground pressure and never authorizes a CPU or
cloud fallback on its own.
"""
from __future__ import annotations

from dataclasses import dataclass

from sofia.platform.ops.activity import ActivityMode

from .contract import WorkloadClass

_FOREGROUND_ACTIVITY = frozenset({
    ActivityMode.NORMAL, ActivityMode.IDLE, ActivityMode.BUSY,
    ActivityMode.DO_NOT_DISTURB, ActivityMode.GAMING,
})


@dataclass(frozen=True, slots=True)
class GamingDecision:
    allowed: bool
    deferred: bool
    reason: str | None


@dataclass(frozen=True, slots=True)
class GamingPolicy:
    core_to_core_yields: bool = True
    allow_background_preload: bool = False
    allow_cpu_fallback: bool = False
    allow_cloud_fallback: bool = False

    def __post_init__(self) -> None:
        for label in (
            "core_to_core_yields", "allow_background_preload",
            "allow_cpu_fallback", "allow_cloud_fallback",
        ):
            if type(getattr(self, label)) is not bool:
                raise TypeError(f"{label} must be bool")

    def decision(
        self, workload: WorkloadClass, activity: ActivityMode,
    ) -> GamingDecision:
        if not isinstance(workload, WorkloadClass):
            raise TypeError("workload must be WorkloadClass")
        if not isinstance(activity, ActivityMode):
            raise TypeError("activity must be ActivityMode")
        if activity is ActivityMode.GAMING:
            if workload is WorkloadClass.FOREGROUND_OWNER:
                return GamingDecision(True, False, None)
            if self.core_to_core_yields:
                return GamingDecision(
                    False, True, "autonomous inference yields to gaming",
                )
            return GamingDecision(
                False, True, "background inference is not permitted during gaming",
            )
        if activity is ActivityMode.UNKNOWN or activity is ActivityMode.AUTO:
            if workload is WorkloadClass.FOREGROUND_OWNER:
                return GamingDecision(True, False, None)
            return GamingDecision(
                False, True, "background activity evidence is unknown",
            )
        if activity in {ActivityMode.BUSY, ActivityMode.DO_NOT_DISTURB}:
            if workload is WorkloadClass.FOREGROUND_OWNER:
                return GamingDecision(True, False, None)
            return GamingDecision(
                False, True, "autonomous inference yields to foreground activity",
            )
        if workload is WorkloadClass.BENCHMARK and activity is not ActivityMode.IDLE:
            return GamingDecision(
                False, True, "benchmark requires verified idle activity",
            )
        return GamingDecision(True, False, None)

    def preload_allowed(
        self, activity: ActivityMode, *, verified_idle: bool,
    ) -> bool:
        if not isinstance(activity, ActivityMode):
            raise TypeError("activity must be ActivityMode")
        if type(verified_idle) is not bool:
            raise TypeError("verified_idle must be bool")
        return (
            self.allow_background_preload
            and verified_idle
            and activity is ActivityMode.IDLE
        )

    def cpu_fallback_allowed(self, activity: ActivityMode) -> bool:
        if not isinstance(activity, ActivityMode):
            raise TypeError("activity must be ActivityMode")
        return self.allow_cpu_fallback and activity is not ActivityMode.GAMING

    def cloud_fallback_allowed(self) -> bool:
        return self.allow_cloud_fallback

    def core_to_core_yields_to(self, activity: ActivityMode) -> bool:
        if not isinstance(activity, ActivityMode):
            raise TypeError("activity must be ActivityMode")
        return self.core_to_core_yields and activity in {
            ActivityMode.GAMING, ActivityMode.BUSY,
            ActivityMode.DO_NOT_DISTURB, ActivityMode.UNKNOWN,
        }

    def model_load_allowed(
        self, workload: WorkloadClass, activity: ActivityMode, *,
        verified_idle: bool,
    ) -> bool:
        """Cold model loads are activity-gated separate from queue admission."""
        if not isinstance(workload, WorkloadClass):
            raise TypeError("workload must be WorkloadClass")
        if not isinstance(activity, ActivityMode):
            raise TypeError("activity must be ActivityMode")
        if activity not in _FOREGROUND_ACTIVITY:
            return False
        if activity is ActivityMode.GAMING:
            return False
        if workload is WorkloadClass.FOREGROUND_OWNER:
            return activity in {
                ActivityMode.NORMAL, ActivityMode.BUSY, ActivityMode.IDLE,
            }
        if workload is WorkloadClass.BENCHMARK:
            return verified_idle and activity is ActivityMode.IDLE
        return (
            self.allow_background_preload
            and verified_idle
            and activity is ActivityMode.IDLE
        )
