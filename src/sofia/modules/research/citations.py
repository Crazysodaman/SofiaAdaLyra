"""MOD-RESEARCH: bounded citation/provenance validation of supplied documents.

Only caller-supplied text and metadata are inspected. No browsing, retrieval or
authenticity verification occurs; document bodies are never returned.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import hashlib
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .analysis import MODULE_ID, MODULE_VERSION, PROFILE, RESOURCES

CAPABILITY_ID = 'research.validate_source_citations.v1'
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'documents'})
_DOCUMENT_FIELDS = frozenset({'document_id', 'origin_ref', 'published_at',
                              'provenance_class', 'content', 'citations'})
_PROVENANCE = frozenset({'primary', 'secondary', 'unknown'})
_MAX_CONTENT = 20000
_INJECTION = (
    (re.compile(r'\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?\b', re.I),
     'instruction_override'),
    (re.compile(r'\b(?:system|assistant|developer)\s*:', re.I), 'role_impersonation'),
    (re.compile(r'\byou\s+must\s+(?:now\s+)?(?:run|execute|send|delete|reveal|ignore)\b', re.I),
     'effect_directive'),
    (re.compile(r'\b(?:reveal|print|leak)\s+(?:the\s+)?'
                r'(?:system|secret|token|password|key)\b', re.I), 'secret_exfiltration'),
)


def _aware(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError('invalid ' + label)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid ' + label) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(label + ' requires timezone')
    return parsed.astimezone(timezone.utc)


def _content(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= _MAX_CONTENT:
        raise ValueError('bounded document content required')
    if any(ord(c) == 0 or (ord(c) < 32 and c not in '\n\t\r') or ord(c) == 127
           for c in value):
        raise ValueError('unsafe control characters in document content')
    return value


def _injection_flags(content: str) -> list[str]:
    return [label for pattern, label in _INJECTION if pattern.search(content)]


def validate_source_citations(snapshot: Mapping[str, object], *, now: datetime,
                              max_age_seconds: int = 86400,
                              max_source_age_days: int = 365) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact citation snapshot required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 604800:
        raise ValueError('invalid snapshot age limit')
    if type(max_source_age_days) is not int or not 1 <= max_source_age_days <= 3650:
        raise ValueError('invalid source age limit')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    now = now.astimezone(timezone.utc)
    observed = _aware(snapshot['observed_at'], 'observed_at')
    raw = snapshot['documents']
    if type(raw) is not list or not 1 <= len(raw) <= 32:
        raise ValueError('1..32 supplied documents required')
    seen = set()
    parsed = []
    for item in raw:
        if not isinstance(item, Mapping) or set(item) != _DOCUMENT_FIELDS:
            raise ValueError('exact supplied document fields required')
        doc_id = item['document_id']
        origin = item['origin_ref']
        if (any(not isinstance(v, str) or not _REF.fullmatch(v) for v in (doc_id, origin))
                or doc_id in seen):
            raise ValueError('duplicate or invalid document reference')
        seen.add(doc_id)
        provenance = item['provenance_class']
        if not isinstance(provenance, str) or provenance not in _PROVENANCE:
            raise ValueError('invalid provenance class')
        published = _aware(item['published_at'], 'published_at')
        if published > observed + timedelta(seconds=5):
            raise ValueError('source publication after snapshot')
        content = _content(item['content'])
        citations = item['citations']
        if type(citations) is not list or len(citations) > 64:
            raise ValueError('bounded citation list required')
        if any(not isinstance(c, str) or not _REF.fullmatch(c) for c in citations):
            raise ValueError('invalid citation reference')
        if len(set(citations)) != len(citations):
            raise ValueError('duplicate citation reference')
        parsed.append((doc_id, origin, provenance, published, content, citations))
    doc_ids = {row[0] for row in parsed}
    age = (now - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema': 'sofia.research.citation_validation.v1', 'module_id': MODULE_ID,
            'sdk_protocol': str(SDK_PROTOCOL_VERSION), 'source_ref': source,
            'freshness': freshness, 'effect': 'none',
            'evidence_class': 'supplied_unverified', 'external_requests_sent': False,
            'source_authenticity_verified': False,
            'citations_resolved_against_supplied_documents_only': True}
    if freshness != 'fresh':
        return base | {'status': 'unknown', 'document_count': None,
                       'resolved_citation_count': None, 'unresolved_citation_refs': [],
                       'stale_document_refs': [], 'instruction_marker_documents': [],
                       'documents': []}
    unresolved = set()
    stale_docs = []
    injected = []
    documents = []
    for doc_id, origin, provenance, published, content, citations in parsed:
        resolved = [c for c in citations if c in doc_ids]
        missing = [c for c in citations if c not in doc_ids]
        unresolved.update(missing)
        if (now - published).total_seconds() > max_source_age_days * 86400:
            stale_docs.append(doc_id)
        flags = _injection_flags(content)
        if flags:
            injected.append(doc_id)
        documents.append({'document_id': doc_id, 'origin_ref': origin,
                          'provenance_class': provenance, 'provenance_verified': False,
                          'content_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
                          'content_returned': False,
                          'source_age_days': max(0, int((now - published).total_seconds() // 86400)),
                          'citation_count': len(citations),
                          'resolved_citation_count': len(resolved),
                          'unresolved_citation_refs': sorted(missing),
                          'instruction_markers': flags,
                          'treated_as_untrusted_data': True})
    return base | {'status': 'validated', 'document_count': len(documents),
                   'resolved_citation_count': sum(d['resolved_citation_count']
                                                  for d in documents),
                   'unresolved_citation_refs': sorted(unresolved),
                   'stale_document_refs': sorted(stale_docs),
                   'instruction_marker_documents': sorted(injected),
                   'documents': sorted(documents, key=lambda d: d['document_id'])}


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate supplied citation provenance and freshness without browsing or fetching.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid citation validation request')
        return validate_source_citations(request.parameters['snapshot'],
                                         now=datetime.now(timezone.utc))

    return ((capability, handler),)
