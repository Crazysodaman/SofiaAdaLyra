"""22E contracts: advertising is not permission or verified remote identity."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.distributed.capabilities import (
    CapabilityInventory, RemoteCapability, inventory_is_current,
)

NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)


def test_inventory_is_immutable_bounded_to_node_and_operation():
    cap = RemoteCapability("hardware.inspect", ("summary", "thermal"))
    report = CapabilityInventory(uuid4(), NOW, (cap,), "remote-report")
    assert report.advertises("hardware.inspect", "thermal")
    assert not report.advertises("hardware.inspect", "shutdown")
    assert not hasattr(report, "authorized")
    assert not hasattr(report, "authenticate")
    with pytest.raises(Exception):
        report.capabilities = ()


def test_current_stale_future_and_boundary():
    report = CapabilityInventory(uuid4(), NOW, (), "channel")
    assert inventory_is_current(report, now=NOW + timedelta(seconds=60),
                                max_age=timedelta(seconds=60))
    assert not inventory_is_current(report, now=NOW + timedelta(seconds=61),
                                    max_age=timedelta(seconds=60))
    assert not inventory_is_current(report, now=NOW - timedelta(seconds=1),
                                    max_age=timedelta(seconds=60))


def test_rejects_duplicate_capabilities_and_operations():
    cap = RemoteCapability("hardware.inspect", ("summary",))
    with pytest.raises(ValueError, match="Duplicate capability"):
        CapabilityInventory(uuid4(), NOW, (cap, cap), "channel")
    with pytest.raises(ValueError, match="Duplicate operations"):
        RemoteCapability("hardware.inspect", ("summary", "summary"))


@pytest.mark.parametrize("invalid", ["", "bad value", "a" * 129])
def test_invalid_capability_identifiers_rejected(invalid):
    with pytest.raises(ValueError):
        RemoteCapability(invalid, ("summary",))


def test_invalid_clock_or_freshness_rejected():
    report = CapabilityInventory(uuid4(), NOW, (), "channel")
    with pytest.raises(ValueError):
        inventory_is_current(report, now=NOW, max_age=timedelta())
    with pytest.raises(ValueError):
        inventory_is_current(report, now=datetime(2026, 9, 20),
                             max_age=timedelta(seconds=30))
