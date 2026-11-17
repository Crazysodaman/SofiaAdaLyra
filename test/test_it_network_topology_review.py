"""Offline validation tests for supplied network reachability/topology review.

No socket, probe, DNS query, device or route change is performed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.it_network.topology import (
    capability_registrations as network_topology_regs,
    review_topology,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def at(seconds: int = 0) -> str:
    return (NOW + timedelta(seconds=seconds)).isoformat()


def probe(**extra):
    return {
        'probe_ref': 'probe:a',
        'origin_ref': 'host:origin',
        'target_ref': 'host:target',
        'observed_at': at(),
        'result': 'reachable',
        'latency_ms': 5,
    } | extra


def link(**extra):
    return {
        'link_ref': 'link:a',
        'endpoint_a': 'host:origin',
        'endpoint_b': 'host:target',
        'observed_at': at(),
        'state': 'up',
    } | extra


def snapshot(**extra):
    return {
        'source_ref': 'network:snapshot',
        'observed_at': at(),
        'probes': [probe()],
        'links': [link()],
    } | extra


def test_topology_healthy_projection_is_effect_free():
    result = review_topology(snapshot(), now=NOW)
    assert result['status'] == 'reviewed_no_fault_observed'
    assert result['findings'] == []
    assert result['probe_count'] == 1 and result['link_count'] == 1
    assert result['probes_performed'] is False
    assert result['external_requests_sent'] is False
    assert result['reachability_independently_verified'] is False
    assert result['effect'] == 'none'
    assert result['evidence_class'] == 'supplied_unverified'


@pytest.mark.parametrize('result_value,finding', [
    ('unreachable', 'target_unreachable'),
    ('timeout', 'target_timeout'),
    ('refused', 'target_refused'),
])
def test_topology_supplied_faults_are_reported_not_repaired(result_value, finding):
    result = review_topology(snapshot(probes=[probe(result=result_value)]), now=NOW)
    assert result['status'] == 'reviewed_with_findings'
    assert finding in result['findings']
    assert result['probes'][0]['result'] == result_value


def test_topology_link_down_is_reported_without_claiming_repair():
    result = review_topology(snapshot(links=[link(state='down')]), now=NOW)
    assert 'link_down' in result['findings']
    assert result['probes_performed'] is False


def test_topology_stale_snapshot_is_unknown():
    result = review_topology(snapshot(observed_at=at(-3600)), now=NOW)
    assert result['status'] == 'unknown'
    assert result['findings'] == ['snapshot_timestamp_invalid']
    assert result['probe_count'] is None and result['link_count'] is None
    assert result['probes'] == [] and result['links'] == []


def test_topology_stale_items_are_downgraded_to_unknown():
    stale = review_topology(
        snapshot(probes=[probe(observed_at=at(-3600), result='unreachable')]),
        now=NOW,
    )
    assert stale['probes'][0]['result'] == 'unknown'
    assert stale['probes'][0]['latency_ms'] is None
    assert 'probe_evidence_stale' in stale['findings']
    assert 'target_unreachable' not in stale['findings']
    stale_link = review_topology(snapshot(links=[link(observed_at=at(-3600), state='down')]), now=NOW)
    assert stale_link['links'][0]['state'] == 'unknown'
    assert 'link_down' not in stale_link['findings']


def test_topology_all_unknown_is_insufficient_evidence():
    result = review_topology(
        snapshot(probes=[probe(result='unknown', latency_ms=None)],
                 links=[link(state='unknown')]),
        now=NOW,
    )
    assert result['status'] == 'unknown'
    assert 'insufficient_evidence' in result['findings']


@pytest.mark.parametrize('change', [
    {'probes': []},
    {'probes': [probe(probe_ref=f'probe:{n}') for n in range(129)]},
    {'links': [link(link_ref=f'link:{n}', endpoint_a=f'host:{n}',
                    endpoint_b=f'host:{n + 1}') for n in range(257)]},
    {'probes': [probe(result='open')]},
    {'probes': [probe(latency_ms=-1)]},
    {'probes': [probe(latency_ms=600001)]},
    {'probes': [probe(latency_ms=True)]},
    {'probes': [probe(latency_ms='5')]},
    {'links': [link(state='blocked')]},
    {'links': [link(endpoint_a='host:same', endpoint_b='host:same')]},
    {'probes': [probe(origin_ref='host:same', target_ref='host:same')]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'extra_probe': True},
])
def test_topology_rejects_malformed_or_oversized(change):
    with pytest.raises(ValueError):
        review_topology(snapshot(**change), now=NOW)


def test_topology_rejects_duplicate_identities():
    with pytest.raises(ValueError):
        review_topology(snapshot(probes=[probe(), probe()]), now=NOW)
    with pytest.raises(ValueError):
        review_topology(
            snapshot(links=[link(), link(link_ref='link:b')]),
            now=NOW,
        )


@pytest.mark.parametrize('bad_ref', ['../etc/passwd', '/etc/passwd',
                                     'host\\secret', 'host/../target'])
def test_topology_rejects_path_like_references(bad_ref):
    with pytest.raises(ValueError):
        review_topology(snapshot(source_ref=bad_ref), now=NOW)
    with pytest.raises(ValueError):
        review_topology(snapshot(probes=[probe(target_ref=bad_ref)]), now=NOW)


def test_topology_registration_is_inert_and_identity_checked():
    (capability, handler), = network_topology_regs()
    assert isinstance(capability, Capability)
    assert capability.name == 'it.network.review_reachability_topology.v1'
    live = snapshot(observed_at=datetime.now(timezone.utc).isoformat())
    result = handler(CapabilityRequest(capability, {'snapshot': live},
                                      None, 'offline topology review'))
    assert result['effect'] == 'none'
    assert result['probes_performed'] is False
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'snapshot': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, {'snapshot': live, 'probe': True},
                                  None, 'invalid'))
