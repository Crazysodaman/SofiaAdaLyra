"""Host-stage receipt admission contracts, deferred until owner test campaign.

No Hyper-V adapter, Fleet transport, VM, NIC or host process is invoked.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from sofia.ops.workshop_network_stage import verified_host_stage_report
from sofia.ops.workshop_network import SWITCH_NAME


NOW = datetime(2026, 10, 11, 18, 0, tzinfo=timezone.utc)
VM = uuid4()


def host_result(**replacements):
    reported = {
        "VmId": str(VM),
        "VmState": "Off",
        "Outcome": "host_internal_link_staged",
        "SwitchName": SWITCH_NAME,
        "SwitchType": "Internal",
        "HostIPv4": "172.30.250.1/30",
        "GuestIPv4": "172.30.250.2/30",
        "GuestConfigured": False,
        "NatEnabled": False,
        "ObservedAtUtc": NOW.isoformat(),
    }
    reported.update(replacements)
    return reported


def test_fresh_exact_host_stage_is_only_a_host_report():
    result = verified_host_stage_report(host_result(), vm=VM, now=NOW)
    assert result is True
    # This decoder gives NO authority to infer Debian, Fleet enrollment,
    # guest firewall acceptance, or actual isolation.


@pytest.mark.parametrize("altered", [
    {"VmId": str(uuid4())},
    {"VmId": "not-a-uuid"},
    {"VmState": "Running"},
    {"Outcome": "installer_boot_started"},
    {"SwitchName": "Default Switch"},
    {"SwitchType": "External"},
    {"HostIPv4": "192.168.1.55/24"},
    {"GuestIPv4": "172.30.250.3/30"},
    {"GuestConfigured": True},
    {"GuestConfigured": None},
    {"NatEnabled": True},
    {"NatEnabled": 0},
    {"ObservedAtUtc": (NOW-timedelta(minutes=4)).isoformat()},
    {"ObservedAtUtc": (NOW+timedelta(seconds=1)).isoformat()},
    {"ObservedAtUtc": NOW.replace(tzinfo=None).isoformat()},
    {"ObservedAtUtc": "unverified"},
    {"ObservedAtUtc": None},
])
def test_unverified_host_response_cannot_be_reported_success(altered):
    assert verified_host_stage_report(host_result(**altered), vm=VM, now=NOW) is False


def test_missing_evidence_does_not_claim_host_stage_success():
    for key in host_result():
        incomplete = host_result()
        del incomplete[key]
        assert verified_host_stage_report(incomplete, vm=VM, now=NOW) is False


def test_host_clock_accepts_only_at_most_three_minutes_of_source_age():
    source = host_result(ObservedAtUtc=(NOW-timedelta(minutes=3)).isoformat())
    assert verified_host_stage_report(source, vm=VM, now=NOW) is True
    assert verified_host_stage_report(
        source, vm=VM, now=NOW+timedelta(microseconds=1),
    ) is False


def test_uncertain_receipt_decoder_requires_trusted_aware_comparison_time():
    with pytest.raises(ValueError):
        verified_host_stage_report(
            host_result(), vm=VM, now=NOW.replace(tzinfo=None),
        )
