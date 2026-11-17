"""MOD-IT-NETWORK: bounded review of supplied reachability/topology evidence.

No sockets, probes, DNS queries, device access, route changes or discovery
occur. Callers supply already-authorized observations; stale or future items
are downgraded to ``unknown`` instead of being interpreted.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .diagnostics import MODULE_ID

CAPABILITY_ID = 'it.network.review_reachability_topology.v1'
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'probes', 'links'})
_PROBE_FIELDS = frozenset({'probe_ref', 'origin_ref', 'target_ref',
                           'observed_at', 'result', 'latency_ms'})
_LINK_FIELDS = frozenset({'link_ref', 'endpoint_a', 'endpoint_b',
                          'observed_at', 'state'})
_RESULTS = frozenset({'reachable', 'unreachable', 'timeout', 'refused', 'unknown'})
_LINK_STATES = frozenset({'up', 'down', 'unknown'})


def _ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise ValueError(f'invalid {label}')
    if value.startswith('/') or '\\' in value or '..' in value.split('/'):
        raise ValueError(f'unsafe {label}')
    return value


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f'invalid {label}')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'invalid {label}') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f'{label} requires timezone')
    return parsed.astimezone(timezone.utc)


def _freshness(observed: datetime, now: datetime, max_age_seconds: int) -> str:
    age = (now - observed).total_seconds()
    return 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'


def review_topology(snapshot: Mapping[str, object], *, now: datetime,
                    max_age_seconds: int = 300) -> dict[str, object]:
    """Review one bounded supplied topology/readability projection."""
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('topology snapshot requires exact fields')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('now requires timezone')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid max_age_seconds')
    source = _ref(snapshot['source_ref'], 'source_ref')
    observed = _aware(snapshot['observed_at'], 'observed_at')
    now = now.astimezone(timezone.utc)

    raw_probes = snapshot['probes']
    if type(raw_probes) is not list or not 1 <= len(raw_probes) <= 128:
        raise ValueError('probes must contain 1..128 items')
    raw_links = snapshot['links']
    if type(raw_links) is not list or len(raw_links) > 256:
        raise ValueError('links must be a bounded list')

    probes = []
    probe_refs: set[str] = set()
    for item in raw_probes:
        if not isinstance(item, Mapping) or set(item) != _PROBE_FIELDS:
            raise ValueError('invalid probe fields')
        probe_ref = _ref(item['probe_ref'], 'probe_ref')
        if probe_ref in probe_refs:
            raise ValueError('duplicate probe_ref')
        probe_refs.add(probe_ref)
        origin = _ref(item['origin_ref'], 'origin_ref')
        target = _ref(item['target_ref'], 'target_ref')
        if origin == target:
            raise ValueError('probe origin and target must differ')
        at = _aware(item['observed_at'], 'probe observed_at')
        result = item['result']
        if not isinstance(result, str) or result not in _RESULTS:
            raise ValueError('invalid probe result')
        latency = item['latency_ms']
        if latency is not None and (type(latency) is not int or not 0 <= latency <= 600000):
            raise ValueError('invalid probe latency')
        probes.append((probe_ref, origin, target, at, result, latency))

    links = []
    link_refs: set[str] = set()
    link_pairs: set[tuple[str, str]] = set()
    for item in raw_links:
        if not isinstance(item, Mapping) or set(item) != _LINK_FIELDS:
            raise ValueError('invalid link fields')
        link_ref = _ref(item['link_ref'], 'link_ref')
        if link_ref in link_refs:
            raise ValueError('duplicate link_ref')
        link_refs.add(link_ref)
        a = _ref(item['endpoint_a'], 'endpoint_a')
        b = _ref(item['endpoint_b'], 'endpoint_b')
        if a == b:
            raise ValueError('link endpoints must differ')
        pair = (a, b) if a < b else (b, a)
        if pair in link_pairs:
            raise ValueError('duplicate link endpoints')
        link_pairs.add(pair)
        at = _aware(item['observed_at'], 'link observed_at')
        state = item['state']
        if not isinstance(state, str) or state not in _LINK_STATES:
            raise ValueError('invalid link state')
        links.append((link_ref, a, b, at, state))

    base = {
        'schema': 'sofia.it.network.topology_review.v1',
        'module_id': MODULE_ID,
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_ref': source,
        'observed_at': observed.isoformat(),
        'evidence_class': 'supplied_unverified',
        'effect': 'none',
        'probes_performed': False,
        'external_requests_sent': False,
        'reachability_independently_verified': False,
    }
    freshness = _freshness(observed, now, max_age_seconds)
    base |= {'freshness': freshness}
    if freshness != 'fresh':
        return base | {
            'status': 'unknown',
            'probe_count': None,
            'link_count': None,
            'fresh_probe_count': None,
            'fresh_link_count': None,
            'findings': ['snapshot_timestamp_invalid'],
            'probes': [],
            'links': [],
        }

    findings: list[str] = []
    probe_rows = []
    fresh_probes = 0
    for probe_ref, origin, target, at, result, latency in probes:
        item_freshness = _freshness(at, now, max_age_seconds)
        effective = result if item_freshness == 'fresh' else 'unknown'
        if item_freshness == 'fresh':
            fresh_probes += 1
            if result == 'unreachable':
                findings.append('target_unreachable')
            elif result == 'timeout':
                findings.append('target_timeout')
            elif result == 'refused':
                findings.append('target_refused')
        else:
            findings.append('probe_evidence_stale')
        probe_rows.append({
            'probe_ref': probe_ref,
            'origin_ref': origin,
            'target_ref': target,
            'observed_at': at.isoformat(),
            'freshness': item_freshness,
            'result': effective,
            'latency_ms': latency if item_freshness == 'fresh' else None,
        })

    link_rows = []
    fresh_links = 0
    for link_ref, a, b, at, state in links:
        item_freshness = _freshness(at, now, max_age_seconds)
        effective = state if item_freshness == 'fresh' else 'unknown'
        if item_freshness == 'fresh':
            fresh_links += 1
            if state == 'down':
                findings.append('link_down')
        else:
            findings.append('link_evidence_stale')
        link_rows.append({
            'link_ref': link_ref,
            'endpoint_a': a,
            'endpoint_b': b,
            'observed_at': at.isoformat(),
            'freshness': item_freshness,
            'state': effective,
        })

    known = any(row['result'] != 'unknown' for row in probe_rows) or any(
        row['state'] != 'unknown' for row in link_rows)
    if not known:
        findings.append('insufficient_evidence')
    warnings = {'target_unreachable', 'target_timeout', 'target_refused', 'link_down'}
    status = ('unknown' if not known
              else 'reviewed_with_findings' if warnings.intersection(findings)
              else 'reviewed_no_fault_observed')
    return base | {
        'status': status,
        'probe_count': len(probe_rows),
        'link_count': len(link_rows),
        'fresh_probe_count': fresh_probes,
        'fresh_link_count': fresh_links,
        'findings': sorted(set(findings)),
        'probes': sorted(probe_rows, key=lambda row: row['probe_ref']),
        'links': sorted(link_rows, key=lambda row: row['link_ref']),
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Review supplied reachability and topology evidence without probing.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid topology review request')
        return review_topology(request.parameters['snapshot'],
                               now=datetime.now(timezone.utc))

    return ((capability, handler),)
