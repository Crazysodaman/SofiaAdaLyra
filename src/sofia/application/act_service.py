from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from sofia.act.delivery import (
    ActDeliveryRunner,
    ActOutbox,
    DeliveryPayload,
    DeliveryRunResult,
    SendResult,
)
from sofia.act.outreach import Policy
from sofia.interaction.goal_journal import GoalJournal


class SofiaActService:
    """Application-owned ACT delivery facade over durable INTERACT queue state."""

    def __init__(self, state_path: Path) -> None:
        if not isinstance(state_path, Path):
            raise TypeError("state_path must be a Path")
        self.state_path = state_path
        self._sender: Callable[[DeliveryPayload], SendResult] | None = None
        self._policy: Policy | None = None

    def configure_delivery(
        self,
        *,
        sender: Callable[[DeliveryPayload], SendResult],
        policy: Policy,
    ) -> None:
        if not callable(sender):
            raise TypeError("sender must be callable")
        if not isinstance(policy, Policy):
            raise TypeError("policy must be a Policy")
        self._sender = sender
        self._policy = policy

    def disable_delivery(self) -> None:
        self._sender = None
        self._policy = None

    @property
    def delivery_enabled(self) -> bool:
        return self._sender is not None and self._policy is not None

    def deliver_one(
        self,
        *,
        now: datetime,
        busy: bool = False,
    ) -> DeliveryRunResult | None:
        if not self.delivery_enabled:
            return None
        journal = GoalJournal(self.state_path)
        outbox = ActOutbox(self.state_path)
        runner = ActDeliveryRunner(
            outbox,
            self._sender,
        )
        for message in journal.pending(limit=10):
            if outbox.bound(message.id) is None:
                continue
            result = runner.deliver(
                message_id=message.id,
                attempt_id=str(uuid4()),
                policy=self._policy,
                now=now,
                busy=busy,
            )
            if result.claim_result.status not in (
                "not_queued",
                "not_bound",
                "retry_wait",
                "attempt_limit",
                "outcome_unknown",
            ):
                return result
        return None
