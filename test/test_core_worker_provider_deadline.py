"""CORE-001: hard wall-clock deadline for synchronous Platform providers."""
from threading import Event
import time

import pytest

from sofia.platform.core_worker.provider_deadline import call_with_deadline


def test_provider_completes_before_deadline():
    assert call_with_deadline(
        lambda: "generated-response", deadline=time.monotonic() + 2.0,
    ) == "generated-response"


def test_provider_timeout_does_not_wait_for_uncooperative_call():
    started, release, finished = Event(), Event(), Event()

    def blocked():
        started.set()
        try:
            release.wait(timeout=3)
            return "too-late-model-result"
        finally:
            finished.set()

    before = time.monotonic()
    try:
        with pytest.raises(TimeoutError, match="deadline expired"):
            call_with_deadline(
                blocked, deadline=time.monotonic() + 0.15,
            )
        assert started.is_set()
        assert time.monotonic() - before < 1.0
    finally:
        release.set()
    assert finished.wait(timeout=2)


def test_provider_result_received_after_deadline_is_rejected():
    def slow():
        time.sleep(0.06)
        return "late-result"

    with pytest.raises(TimeoutError, match="deadline expired"):
        call_with_deadline(slow, deadline=time.monotonic() + 0.02)


def test_provider_exception_preserved_before_deadline():
    def failed():
        raise ValueError("synthetic provider failed")
    with pytest.raises(ValueError, match="synthetic provider failed"):
        call_with_deadline(failed, deadline=time.monotonic() + 2)


def test_provider_expired_admission_never_starts_call():
    called = Event()

    def forbidden():
        called.set()
        return "never"

    with pytest.raises(TimeoutError, match="deadline expired"):
        call_with_deadline(forbidden, deadline=time.monotonic() - 1)
    assert not called.is_set()


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_provider_bad_deadline_fails_closed(bad):
    with pytest.raises((TypeError, TimeoutError, ValueError)):
        call_with_deadline(lambda: "nope", deadline=bad)
