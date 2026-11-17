"""Per-Core and per-conversation sliding-window inference budgets."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import math
from threading import RLock
from typing import Deque

from .contract import BudgetExceeded
from .identity import CoreIdentity


@dataclass(frozen=True, slots=True)
class BudgetWindow:
    max_requests: int
    max_output_tokens: int
    window_seconds: float

    def __post_init__(self) -> None:
        if type(self.max_requests) is not int or self.max_requests < 1:
            raise ValueError("max_requests must be a positive integer")
        if type(self.max_output_tokens) is not int or self.max_output_tokens < 1:
            raise ValueError("max_output_tokens must be a positive integer")
        if type(self.window_seconds) not in (int, float) or not (
            1.0 <= float(self.window_seconds) <= 86_400.0
        ):
            raise ValueError("window_seconds must be in 1..86400")
        object.__setattr__(self, "window_seconds", float(self.window_seconds))


@dataclass(frozen=True, slots=True)
class InferenceBudgetPolicy:
    core: BudgetWindow
    conversation: BudgetWindow

    def __post_init__(self) -> None:
        if not isinstance(self.core, BudgetWindow):
            raise TypeError("core budget must be BudgetWindow")
        if not isinstance(self.conversation, BudgetWindow):
            raise TypeError("conversation budget must be BudgetWindow")


@dataclass(frozen=True, slots=True)
class BudgetDecision:
    allowed: bool
    reason: str | None
    remaining_requests: int
    remaining_output_tokens: int


@dataclass(slots=True)
class _Event:
    at: float
    output_tokens: int


@dataclass(slots=True)
class _Window:
    budget: BudgetWindow
    events: Deque[_Event] = field(default_factory=deque)

    def prune(self, now: float) -> None:
        cutoff = now - self.budget.window_seconds
        while self.events and self.events[0].at <= cutoff:
            self.events.popleft()

    def evaluate(self, now: float, output_tokens: int) -> BudgetDecision:
        self.prune(now)
        used_tokens = sum(item.output_tokens for item in self.events)
        remaining_requests = max(0, self.budget.max_requests - len(self.events))
        remaining_tokens = max(0, self.budget.max_output_tokens - used_tokens)
        if remaining_requests < 1:
            return BudgetDecision(False, "request budget exhausted", 0, remaining_tokens)
        if output_tokens > remaining_tokens:
            return BudgetDecision(
                False, "output token budget exhausted", remaining_requests, remaining_tokens,
            )
        return BudgetDecision(True, None, remaining_requests, remaining_tokens)


def _core_key(core: CoreIdentity) -> tuple[str, str]:
    return ("core", f"{core.platform_id}:{core.core_id}")


def _conversation_key(core: CoreIdentity, conversation_id: str) -> tuple[str, str]:
    return (
        "conversation",
        f"{core.platform_id}:{core.core_id}:{core.generation}:{conversation_id}",
    )


class BudgetLedger:
    """Conservative accounting: accepted work consumes request and token budget."""

    def __init__(self, policy: InferenceBudgetPolicy) -> None:
        if not isinstance(policy, InferenceBudgetPolicy):
            raise TypeError("policy must be InferenceBudgetPolicy")
        self.policy = policy
        self._lock = RLock()
        self._windows: dict[tuple[str, str], _Window] = {}

    def _window(self, key: tuple[str, str], budget: BudgetWindow) -> _Window:
        window = self._windows.get(key)
        if window is None:
            window = _Window(budget)
            self._windows[key] = window
        return window

    @staticmethod
    def _check_now(now: float) -> float:
        if type(now) not in (int, float) or not math.isfinite(float(now)):
            raise ValueError("now must be a finite number")
        return float(now)

    def check(
        self, core: CoreIdentity, conversation_id: str,
        output_tokens: int, now: float,
    ) -> BudgetDecision:
        if not isinstance(core, CoreIdentity):
            raise TypeError("core must be CoreIdentity")
        if type(output_tokens) is not int or output_tokens < 1:
            raise ValueError("output_tokens must be a positive integer")
        moment = self._check_now(now)
        with self._lock:
            core_decision = self._window(
                _core_key(core), self.policy.core
            ).evaluate(moment, output_tokens)
            if not core_decision.allowed:
                return core_decision
            return self._window(
                _conversation_key(core, conversation_id), self.policy.conversation
            ).evaluate(moment, output_tokens)

    def consume(
        self, core: CoreIdentity, conversation_id: str,
        output_tokens: int, now: float,
    ) -> BudgetDecision:
        if not isinstance(core, CoreIdentity):
            raise TypeError("core must be CoreIdentity")
        if type(output_tokens) is not int or output_tokens < 1:
            raise ValueError("output_tokens must be a positive integer")
        moment = self._check_now(now)
        with self._lock:
            core_window = self._window(_core_key(core), self.policy.core)
            core_decision = core_window.evaluate(moment, output_tokens)
            if not core_decision.allowed:
                return core_decision
            conversation_window = self._window(
                _conversation_key(core, conversation_id), self.policy.conversation
            )
            conversation_decision = conversation_window.evaluate(moment, output_tokens)
            if not conversation_decision.allowed:
                return conversation_decision
            event = _Event(moment, output_tokens)
            core_window.events.append(event)
            conversation_window.events.append(_Event(moment, output_tokens))
            return BudgetDecision(
                True, None,
                max(0, core_decision.remaining_requests - 1),
                max(0, core_decision.remaining_output_tokens - output_tokens),
            )

    def require(
        self, core: CoreIdentity, conversation_id: str,
        output_tokens: int, now: float,
    ) -> BudgetDecision:
        decision = self.consume(core, conversation_id, output_tokens, now)
        if not decision.allowed:
            raise BudgetExceeded(decision.reason or "inference budget exhausted")
        return decision
