"""MOD-KNOWLEDGE-LIBRARY: validate external document revision candidates.

Only proposes an index delta from supplied, untrusted manifests. It does not
read documents, search files, create an index, or write to autobiographical memory.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-KNOWLEDGE-LIBRARY'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'knowledge_library.plan_revision_index.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_SHA256 = re.compile(r'^[0-9a-f]{64}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'documents'})
_DOC_FIELDS = frozenset({'document_id', 'source_ref', 'revision_sha256',
                        'indexed_sha256', 'modified_at', 'deleted'})


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


def plan_revision_index(snapshot: Mapping[str, object], *, now: datetime,
                        max_age_seconds: int = 86400) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact document manifest required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 604800:
        raise ValueError('invalid freshness bound')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed = _aware(snapshot['observed_at'], 'observed_at')
    records = snapshot['documents']
    if type(records) is not list or len(records) > 128:
        raise ValueError('documents must be bounded list')
    seen = set()
    pending = []
    unchanged = 0
    noop_deleted = 0
    for record in records:
        if not isinstance(record, Mapping) or set(record) != _DOC_FIELDS:
            raise ValueError('invalid document projection')
        doc_id = record['document_id']
        remote = record['source_ref']
        if (not isinstance(doc_id, str) or not _REF.fullmatch(doc_id) or doc_id in seen
                or not isinstance(remote, str) or not _REF.fullmatch(remote)):
            raise ValueError('invalid or duplicate document reference')
        seen.add(doc_id)
        revision = record['revision_sha256']
        indexed = record['indexed_sha256']
        deleted = record['deleted']
        if type(deleted) is not bool:
            raise ValueError('invalid deleted flag')
        if indexed is not None and (not isinstance(indexed, str) or not _SHA256.fullmatch(indexed)):
            raise ValueError('invalid indexed digest')
        if revision is not None and (not isinstance(revision, str) or not _SHA256.fullmatch(revision)):
            raise ValueError('invalid revision digest')
        if not deleted and revision is None:
            raise ValueError('live document requires revision digest')
        if deleted and revision is not None:
            raise ValueError('deleted document must not claim a live revision')
        modified = _aware(record['modified_at'], 'modified_at')
        if modified > observed + timedelta(seconds=5):
            raise ValueError('document modified after manifest observation')
        if deleted:
            if indexed is not None:
                pending.append({'document_id': doc_id, 'operation': 'tombstone', 'revision_sha256': None})
            else:
                noop_deleted += 1
        elif revision == indexed:
            unchanged += 1
        else:
            pending.append({'document_id': doc_id, 'operation': 'candidate_update',
                            'revision_sha256': revision})
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema': 'sofia.knowledge_library.revision_plan.v1',
            'sdk_protocol': str(SDK_PROTOCOL_VERSION), 'module_id': MODULE_ID,
            'source_ref': source, 'freshness': freshness,
            'evidence_class': 'supplied_unverified', 'effect': 'none',
            'index_written': False, 'memory_promoted': False,
            'source_authenticity_verified': False}
    if freshness != 'fresh':
        return base | {'status': 'unknown', 'candidate_operations': [],
                       'unchanged_count': None, 'unindexed_deleted_count': None}
    return base | {'status': 'proposed_only',
                   'candidate_operations': sorted(pending, key=lambda x: x['document_id']),
                   'unchanged_count': unchanged, 'unindexed_deleted_count': noop_deleted}


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Propose changes to an external source index; never index or write memory.')
    def handler(request: CapabilityRequest):
        if not isinstance(request, CapabilityRequest) or request.capability != capability or set(request.parameters) != {'snapshot'}:
            raise ValueError('invalid knowledge library capability request')
        return plan_revision_index(request.parameters['snapshot'], now=datetime.now(timezone.utc))
    return ((capability, handler),)
