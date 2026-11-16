"""Bound a synchronous Platform-owned provider call without accepting late output.

Timeout stops the Core/IPC request owner, not an already-running native/network
provider call. The latter can finish later but cannot send an IPC response.
Controller must quarantine the generation and revoke its admission authority.
"""
from __future__ import annotations

from math import isfinite
from queue import Empty, Queue
from threading import Thread
import time
from typing import Callable, TypeVar


_T = TypeVar("_T")


def _cancel(cancel: Callable[[], None] | None) -> None:
    if cancel is None:
        return
    try:
        cancel()
    except Exception:
        # Cancellation is best-effort signalling only. The deadline result is
        # already authoritative and must not be replaced by a cancel hook bug.
        pass


def call_with_deadline(
    call: Callable[[], _T],
    *,
    deadline: float,
    cancel: Callable[[], None] | None = None,
) -> _T:
    """Wait until one monotonic deadline; never publish late provider results.

    A daemon provider thread is intentionally not claimed to be forcibly
    killed. ``cancel`` is invoked deterministically on timeout so a provider
    with a cooperative cancellation event can discard any late result. The
    Core/IPC caller still quarantines the generation because a native/network
    call may already have produced external effects.
    """
    if not callable(call):
        raise TypeError("provider call must be callable")
    if cancel is not None and not callable(cancel):
        raise TypeError("cancel must be callable or None")
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)):
        raise TypeError("deadline must be monotonic seconds")
    if not isfinite(deadline):
        raise ValueError("deadline must be finite")
    if deadline <= time.monotonic():
        raise TimeoutError("Core provider response deadline expired")

    results: Queue[tuple[bool, object]] = Queue(maxsize=1)

    def invoke() -> None:
        try:
            outcome = (True, call())
        except Exception as exc:
            outcome = (False, exc)
        results.put_nowait(outcome)

    thread = Thread(target=invoke, name="sofia-bounded-provider", daemon=True)
    thread.start()
    try:
        ok, result = results.get(timeout=max(0.0, deadline - time.monotonic()))
    except Empty as exc:
        _cancel(cancel)
        raise TimeoutError("Core provider response deadline expired") from exc
    if time.monotonic() >= deadline:
        _cancel(cancel)
        raise TimeoutError("Core provider response deadline expired")
    if not ok:
        raise result
    return result
