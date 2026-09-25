"""Read-only runtime clock contracts."""
from datetime import datetime, timezone

from sofia.runtime.clock import runtime_clock_prompt, runtime_clock_snapshot


def test_runtime_clock_preserves_same_instant_and_host_local_awareness():
    fixed = datetime(2026, 9, 23, 23, 45, tzinfo=timezone.utc)
    clock = runtime_clock_snapshot(now=fixed)

    assert clock.utc == fixed
    assert clock.host_local.tzinfo is not None
    assert clock.host_local.utcoffset() is not None
    assert clock.host_local.astimezone(timezone.utc) == fixed
    assert clock.host_timezone_label


def test_runtime_clock_prompt_is_explicitly_read_only():
    fixed = datetime(2026, 9, 23, 23, 45, tzinfo=timezone.utc)
    prompt = runtime_clock_prompt(now=fixed)

    assert "TRUSTED RUNTIME CLOCK" in prompt
    assert "Current UTC:" in prompt
    assert "Current host-local time:" in prompt
    assert "read-only evidence" in prompt
