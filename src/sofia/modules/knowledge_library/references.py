"""MOD-KNOWLEDGE-LIBRARY: validate supplied external reference manifests.

Only revision/digest/freshness metadata is inspected. No document is read,
indexed or promoted to memory, and authenticity is never asserted.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .analysis import MODULE_ID, MODULE_VERSION, PROFILE, RESOURCES

CAPABILITY_ID = 'knowledge_library.validate_reference_manifest.v1'
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'references'})
_REFERENCE_FIELDS = frozenset({'reference_id', 'locator_ref', 'revision_sha256',
                               'content_sha256', 'source_observed_at', 'expires_at',
                               'provenance_class'})
_PROVENANCE = frozenset({'primary', 'secondary', 'unknown'})


def _aware(value: object, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(name + ' must be ISO timestamp')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid ' + name) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(name + ' requires timezone')
    return parsed.astimezone(timezone.utc)


def validate_reference_manifest(snapshot: Mapping[str, object], *, now: datetime,
                                max_age_seconds: int = 86400,
                                max_source_age_days: int = 365) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact reference manifest required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 604800:
        raise ValueError('invalid freshness bound')
    if type(max_source_age_days) is not int or not 1 <= max_source_age_days <= 3650:
        raise ValueError('invalid source age bound')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    now = now.astimezone(timezone.utc)
    observed = _aware(snapshot['observed_at'], 'observed_at')
    records = snapshot['references']
    if type(records) is not list or not 1 <= len(records) <= 128:
        raise ValueError('1..128 external references required')
    seen_ids = set()
    seen_locators = set()
    parsed = []
    for record in records:
        if not isinstance(record, Mapping) or set(record) != _REFERENCE_FIELDS:
            raise ValueError('invalid reference projection')
        reference_id = record['reference_id']
        locator = record['locator_ref']
        if (not isinstance(reference_id, str) or not _REF.fullmatch(reference_id)
                or reference_id in seen_ids):
            raise ValueError('duplicate or invalid reference_id')
        if (not isinstance(locator, str) or not _REF.fullmatch(locator)
                or locator in seen_locators):
            raise ValueError('duplicate or invalid locator_ref')
        seen_ids.add(reference_id)
        seen_locators.add(locator)
        for name in ('revision_sha256', 'content_sha256'):
            value = record[name]
            if not isinstance(value, str) or not _SHA256.fullmatch(value):
                raise ValueError('invalid ' + name)
        provenance = record['provenance_class']
        if not isinstance(provenance, str) or provenance not in _PROVENANCE:
            raise ValueError('invalid provenance_class')
        source_observed = _aware(record['source_observed_at'], 'source_observed_at')
        if source_observed > observed + timedelta(seconds=5):
            raise ValueError('reference observed after manifest observation')
        expires_at = record['expires_at']
        expiry = None if expires_at is None else _aware(expires_at, 'expires_at')
        parsed.append((reference_id, locator, record['revision_sha256'],
                       record['content_sha256'], provenance, source_observed, expiry))
    age = (now - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema': 'sofia.knowledge_library.reference_manifest.v1',
            'sdk_protocol': str(SDK_PROTOCOL_VERSION), 'module_id': MODULE_ID,
            'source_ref': source, 'freshness': freshness,
            'evidence_class': 'supplied_unverified', 'effect': 'none',
            'index_written': False, 'memory_promoted': False,
            'source_authenticity_verified': False}
    if freshness != 'fresh':
        return base | {'status': 'unknown', 'reference_count': None,
                       'fresh_count': None, 'stale_reference_refs': [],
                       'expired_reference_refs': [], 'references': []}
    reviewed = []
    stale_refs = []
    expired_refs = []
    for (reference_id, locator, revision, content, provenance,
         source_observed, expiry) in parsed:
        if expiry is not None and now > expiry:
            state = 'expired'
            expired_refs.append(reference_id)
        elif (now - source_observed).total_seconds() > max_source_age_days * 86400:
            state = 'stale'
            stale_refs.append(reference_id)
        else:
            state = 'fresh'
        reviewed.append({'reference_id': reference_id, 'locator_ref': locator,
                         'revision_sha256': revision, 'content_sha256': content,
                         'provenance_class': provenance, 'provenance_verified': False,
                         'freshness': state, 'reference_authenticity_verified': False})
    fresh_count = sum(item['freshness'] == 'fresh' for item in reviewed)
    return base | {'status': 'validated' if not stale_refs and not expired_refs
                   else 'validated_with_stale_references',
                   'reference_count': len(reviewed), 'fresh_count': fresh_count,
                   'stale_reference_refs': sorted(stale_refs),
                   'expired_reference_refs': sorted(expired_refs),
                   'references': sorted(reviewed, key=lambda item: item['reference_id'])}


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate supplied external reference revisions and freshness without indexing '
        'or memory writes.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid reference manifest capability request')
        return validate_reference_manifest(request.parameters['snapshot'],
                                           now=datetime.now(timezone.utc))

    return ((capability, handler),)
