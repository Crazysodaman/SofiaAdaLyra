"""Application-owned work ordering and global budget boundary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable


class WorkPriority(IntEnum):
    FOREGROUND = 0
    DELIVERY = 10
    MAINTENANCE = 20
    BACKGROUND = 30


@dataclass(frozen=True, slots=True)
class GlobalRunBudget:
    max_operations_per_cycle: int = 8
    max_background_per_cycle: int = 1

    def __post_init__(self) -> None:
        if (
            type(self.max_operations_per_cycle) is not int
            or self.max_operations_per_cycle < 1
        ):
            raise ValueError("max_operations_per_cycle must be positive")
        if (
            type(self.max_background_per_cycle) is not int
            or not 0
            <= self.max_background_per_cycle
            <= self.max_operations_per_cycle
        ):
            raise ValueError(
                "max_background_per_cycle must fit total cycle budget"
            )


@dataclass(frozen=True, slots=True)
class ScheduledWork:
    work_id: str
    priority: WorkPriority
    execute: Callable[[], object]
    requires_leader: bool = True
    optional_background: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.work_id, str) or not self.work_id.strip():
            raise ValueError("work_id required")
        if not isinstance(self.priority, WorkPriority):
            raise TypeError("priority must be WorkPriority")
        if not callable(self.execute):
            raise TypeError("execute must be callable")
        if not isinstance(self.requires_leader, bool):
            raise TypeError("requires_leader must be boolean")
        if not isinstance(self.optional_background, bool):
            raise TypeError("optional_background must be boolean")


@dataclass(frozen=True, slots=True)
class WorkResult:
    work_id: str
    status: str
    value: object | None = None


class RuntimeOrchestrator:
    """Run one bounded cycle; live foreground work outranks optional background."""

    def __init__(self, budget: GlobalRunBudget | None = None) -> None:
        self.budget = budget or GlobalRunBudget()

    def run_cycle(
        self,
        work: tuple[ScheduledWork, ...],
        *,
        leader_authoritative: bool,
        user_active: bool,
    ) -> tuple[WorkResult, ...]:
        if not isinstance(work, tuple):
            raise TypeError("work must be a tuple")
        if not isinstance(leader_authoritative, bool):
            raise TypeError("leader_authoritative must be boolean")
        if not isinstance(user_active, bool):
            raise TypeError("user_active must be boolean")

        seen: set[str] = set()
        ordered: list[ScheduledWork] = []
        for item in work:
            if not isinstance(item, ScheduledWork):
                raise TypeError("work must contain ScheduledWork")
            if item.work_id in seen:
                raise ValueError("duplicate work_id")
            seen.add(item.work_id)
            ordered.append(item)
        ordered.sort(key=lambda item: (item.priority, item.work_id))

        results: list[WorkResult] = []
        executed = 0
        background = 0
        for item in ordered:
            if executed >= self.budget.max_operations_per_cycle:
                results.append(WorkResult(item.work_id, "budget"))
                continue
            if item.requires_leader and not leader_authoritative:
                results.append(WorkResult(item.work_id, "not_leader"))
                continue
            if item.optional_background:
                if user_active:
                    results.append(WorkResult(item.work_id, "busy"))
                    continue
                if background >= self.budget.max_background_per_cycle:
                    results.append(
                        WorkResult(item.work_id, "background_budget")
                    )
                    continue
            value = item.execute()
            results.append(WorkResult(item.work_id, "executed", value))
            executed += 1
            if item.optional_background:
                background += 1
        return tuple(results)
