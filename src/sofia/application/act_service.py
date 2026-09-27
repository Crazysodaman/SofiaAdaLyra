from __future__ import annotations

from dataclasses import replace
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
from sofia.act.system_notice import SystemNoticeQueue
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

    @property
    def policy(self) -> Policy | None:
        return self._policy

    def set_local_timezone(self, timezone_name: str) -> None:
        """Update outreach quiet-hour evaluation from trusted ENVIRONMENT."""
        if self._policy is None:
            return
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            raise ValueError("timezone_name must be nonempty")
        self._policy = replace(
            self._policy,
            timezone_name=timezone_name.strip(),
        )

    def queue_system_notice(
        self,
        *,
        notice_id: str,
        recipient_id: str,
        channel: str,
        destination: str,
        evidence_id: str,
        content: str,
        created_at: datetime,
        expires_at: datetime,
    ):
        return SystemNoticeQueue(self.state_path).enqueue(
            notice_id=notice_id,
            recipient_id=recipient_id,
            channel=channel,
            destination=destination,
            evidence_id=evidence_id,
            content=content,
            created_at=created_at,
            expires_at=expires_at,
        )

    def bind_message(
        self,
        *,
        message_id: str,
        recipient_id: str,
        channel: str,
        destination: str,
        expires_at: datetime,
        at: datetime,
    ):
        outbox = ActOutbox(self.state_path)
        return outbox.bind(
            message_id=message_id,
            recipient_id=recipient_id,
            channel=channel,
            destination=destination,
            expires_at=expires_at,
            at=at,
        )

    def deliver_one(
        self,
        *,
        now: datetime,
        busy: bool = False,
    ) -> DeliveryRunResult | SendResult | None:
        if not self.delivery_enabled:
            return None
        notice_result = SystemNoticeQueue(self.state_path).deliver_one(
            sender=self._sender,
            policy=self._policy,
            now=now,
            busy=busy,
        )
        if notice_result is not None:
            return notice_result

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
