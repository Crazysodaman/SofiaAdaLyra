"""Module-local test matrix. No external host or network access required."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.it_network import interpret_snapshot
from sofia.modules.it_network.diagnostics import capability_registrations as network_regs
from sofia.modules.it_helpdesk import triage_evidence
from sofia.modules.it_helpdesk.triage import capability_registrations as helpdesk_regs
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def snapshot(**changes):
    data = dict(source_ref="platform:node1", observed_at=NOW.isoformat(), link_state="up",
                address_cidr="192.168.5.20/24", default_gateway="192.168.5.1",
                dns_rcode="NOERROR", tcp_result="success")
    data.update(changes)
    return data


def ticket(**changes):
    data = dict(ticket_ref="ticket:42", observed_at=NOW.isoformat(),
                symptoms=["cannot_connect"], diagnostic_codes=[],
                expected_network_source_ref="platform:node1")
    data.update(changes)
    return data


def test_healthy_network_is_only_no_fault_observed():
    result = interpret_snapshot(snapshot(), now=NOW)
    assert result.assessment == "no_fault_observed"
    assert result.as_dict()["effect"] == "none"
    assert result.as_dict()["evidence_class"] == "supplied_unverified"
    assert result.as_dict()["sdk_protocol"] == "1.0"


def test_link_and_dns_faults_classified_separately():
    codes = {item.code for item in interpret_snapshot(snapshot(link_state="down", dns_rcode="SERVFAIL"), now=NOW).findings}
    assert codes == {"link_down", "dns_servfail"}


def test_nxdomain_is_not_a_dns_outage():
    result = interpret_snapshot(snapshot(dns_rcode="NXDOMAIN"), now=NOW)
    assert result.assessment == "no_fault_observed"
    assert result.findings[0].code == "dns_name_not_found"


def test_gateway_off_subnet_is_advisory_only():
    result = interpret_snapshot(snapshot(default_gateway="10.0.1.1"), now=NOW)
    assert any(item.code == "gateway_outside_subnet" for item in result.findings)


def test_stale_or_future_evidence_cannot_be_interpreted():
    for dt, freshness in ((NOW-timedelta(minutes=6), "stale"), (NOW+timedelta(minutes=1), "future")):
        result = interpret_snapshot(snapshot(observed_at=dt.isoformat(), link_state="down"), now=NOW)
        assert result.assessment == "unknown"
        assert result.freshness == freshness
        assert all(item.code != "link_down" for item in result.findings)


@pytest.mark.parametrize("field,value", [("link_state", "UP"), ("tcp_result", "exec"),
                                          ("dns_rcode", "NOPE"), ("address_cidr", "no-ip"),
                                          ("source_ref", "x\nsecret"), ("observed_at", "yesterday"),
                                          ("default_gateway", "invalid")])
def test_network_rejects_invalid_fields(field, value):
    with pytest.raises(ValueError):
        interpret_snapshot(snapshot(**{field: value}), now=NOW)


def test_network_rejects_extra_fields_and_mismatched_ip_families():
    with pytest.raises(ValueError):
        interpret_snapshot(snapshot(command="restart"), now=NOW)
    with pytest.raises(ValueError):
        interpret_snapshot(snapshot(default_gateway="::1"), now=NOW)


def test_helpdesk_triages_explicit_diagnostic_codes():
    result = triage_evidence(ticket(diagnostic_codes=["auth_denied"], symptoms=["login_rejected"]), now=NOW)
    assert (result.category, result.confidence) == ("identity", "medium")
    assert result.as_dict()["effect"] == "none"


def test_helpdesk_avoids_fabricating_cause_from_symptom():
    result = triage_evidence(ticket(symptoms=["latency_high"]), now=NOW)
    assert (result.category, result.confidence) == ("performance", "low")


def test_helpdesk_refuses_old_incident_evidence():
    result = triage_evidence(ticket(observed_at=(NOW-timedelta(hours=1)).isoformat(), diagnostic_codes=["storage_full"]), now=NOW)
    assert (result.category, result.confidence) == ("unknown", "none")


def test_network_to_helpdesk_pair_is_explicitly_bounded():
    network = interpret_snapshot(snapshot(dns_rcode="SERVFAIL"), now=NOW)
    result = triage_evidence(ticket(symptoms=["cannot_resolve_name"]), network_report=network.as_dict(), now=NOW)
    assert result.category == "name_resolution"
    assert "dns_servfail" in result.evidence_codes


def test_network_cross_module_source_mismatch_rejected():
    network = interpret_snapshot(snapshot(source_ref="platform:different"), now=NOW)
    with pytest.raises(ValueError, match="source"):
        triage_evidence(ticket(), network_report=network.as_dict(), now=NOW)


def test_network_cross_module_stale_report_ignored():
    network = interpret_snapshot(snapshot(observed_at=(NOW-timedelta(minutes=7)).isoformat(), dns_rcode="SERVFAIL"), now=NOW)
    result = triage_evidence(ticket(symptoms=[]), network_report=network.as_dict(), now=NOW)
    assert result.category == "unknown"
    assert "dns_servfail" not in result.evidence_codes


def test_helpdesk_rejects_unknown_diagnostics_and_implied_command():
    for bad in (ticket(diagnostic_codes=["wipe_drive"]), ticket(command="execute")):
        with pytest.raises(ValueError):
            triage_evidence(bad, now=NOW)


def test_handlers_do_not_claim_grants_and_check_identity():
    for registrations in (network_regs(), helpdesk_regs()):
        (capability, handler), = registrations
        assert isinstance(capability, Capability)
        params = {"snapshot": snapshot()} if capability.name.startswith("it.network") else {"ticket": ticket()}
        real = CapabilityRequest(capability, params, None, "Review supplied evidence")
        with pytest.raises(ValueError, match="mismatch"):
            handler(CapabilityRequest(Capability(capability.name, "Forged descriptor"), params, None, "test"))
        # Production gateway applies permission and STOP before these handlers.
        # Here only module handler shape and inert output are exercised.
        assert callable(handler)


def test_handlers_with_current_snapshots():
    live = datetime.now(timezone.utc).isoformat()
    for regs, params in ((network_regs(), {"snapshot": snapshot(observed_at=live)}),
                         (helpdesk_regs(), {"ticket": ticket(observed_at=live)})):
        (capability, handler), = regs
        result = handler(CapabilityRequest(capability, params, None, "Approved snapshot"))
        assert result["effect"] == "none"
        assert result["sdk_protocol"] == "1.0"
