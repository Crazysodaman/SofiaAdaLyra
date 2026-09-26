"""Host-invoked RUN scheduling for ACT delivery.

This module discovers only already-queued INTERACT messages and only attempts
messages that ACT has an immutable delivery envelope for. It does not create
goals, bind destinations, invent outreach policy, start a thread, or open a
network connection. The caller must explicitly enable scheduling and inject
both policy and sender boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from sofia.act.delivery import (
    ActDeliveryRunner,
    ActOutbox,
    BoundMessage,
    DeliveryLimits,
    DeliveryPayload,
    DeliveryRunResult,
    SendResult,
)
from sofia.act.outreach import Policy
from sofia.interaction.goal_journal import GoalJournal


@dataclass(frozen=True)
class ActSchedulePolicy:
    enabled: bool = False
    max_messages_per_tick: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be boolean")
        if (
            type(self.max_messages_per_tick) is not int
            or not 1 <= self.max_messages_per_tick <= 10
        ):
            raise ValueError("max_messages_per_tick must be in 1..10")


@dataclass(frozen=True)
class ActScheduleTick:
    status: str
    examined: int = 0
    results: tuple[DeliveryRunResult, ...] = ()


class ScheduledActRunner:
    """One explicit RUN tick over ACT's durable outbox."""

    def __init__(
        self,
        *,
        journal: GoalJournal,
        outbox: ActOutbox,
        sender: Callable[[DeliveryPayload], SendResult],
        policy_for: Callable[[BoundMessage], Policy | None],
        attempt_id_for: Callable[[BoundMessage], str],
        schedule: ActSchedulePolicy = ActSchedulePolicy(),
        limits: DeliveryLimits = DeliveryLimits(),
    ) -> None:
        if not isinstance(journal, GoalJournal):
            raise TypeError("GoalJournal required")
        if not isinstance(outbox, ActOutbox):
            raise TypeError("ActOutbox required")
        if not callable(sender):
            raise TypeError("sender must be callable")
        if not callable(policy_for):
            raise TypeError("policy_for must be callable")
        if not callable(attempt_id_for):
            raise TypeError("attempt_id_for must be callable")
        if not isinstance(schedule, ActSchedulePolicy):
            raise TypeError("ActSchedulePolicy required")
        if not isinstance(limits, DeliveryLimits):
            raise TypeError("DeliveryLimits required")

        self.journal = journal
        self.outbox = outbox
        self.policy_for = policy_for
        self.attempt_id_for = attempt_id_for
        self.schedule = schedule
        self.delivery = ActDeliveryRunner(
            outbox,
            sender,
            limits=limits,
        )

    def tick(
        self,
        *,
        now: datetime,
        busy: bool = False,
    ) -> ActScheduleTick:
        if not isinstance(busy, bool):
            raise TypeError("busy must be boolean")
        if not self.schedule.enabled:
            return ActScheduleTick("disabled")

        pending = self.journal.pending(limit=50)
        examined = 0
        results: list[DeliveryRunResult] = []

        for queued in pending:
            if len(results) >= self.schedule.max_messages_per_tick:
                break

            examined += 1
            bound = self.outbox.bound(queued.id)
            if bound is None:
                continue

            policy = self.policy_for(bound)
            if policy is None:
                continue
            if not isinstance(policy, Policy):
                raise TypeError("policy_for must return Policy or None")

            attempt_id = self.attempt_id_for(bound)
            if not isinstance(attempt_id, str) or not attempt_id.strip():
                raise ValueError("attempt_id_for must return a nonempty identifier")

            results.append(
                self.delivery.deliver(
                    message_id=bound.message_id,
                    attempt_id=attempt_id,
                    policy=policy,
                    now=now,
                    busy=busy,
                )
            )

        return ActScheduleTick(
            "processed" if results else "idle",
            examined=examined,
            results=tuple(results),
        )
