"""MOD-DOCUMENTS: deterministic markdown rendering from a bounded plain-text model.

Returns bytes as an inert string and SHA-256 receipt. No file writes, HTML,
PDF/Office rendering, hyperlinks or arbitrary markdown passthrough.
"""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-DOCUMENTS'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'documents.render_safe_markdown.v1'
PROFILE = 'SIMULATE'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_ESC = re.compile(r'([\\`*_{}\[\]()#+\-.!|<>])')
_FIELDS = frozenset({'source_ref', 'observed_at', 'title', 'sections'})
_SECTION_FIELDS = frozenset({'heading', 'paragraphs'})


def _text(value: object, label: str, max_chars: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= max_chars:
        raise ValueError('invalid ' + label)
    if value != value.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError('invalid whitespace or control characters in ' + label)
    return value


def render_safe_markdown(snapshot: Mapping[str, object], *, now: datetime,
                         max_age_seconds: int = 86400) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact document model required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 604800:
        raise ValueError('invalid freshness bound')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    try:
        observed = datetime.fromisoformat(snapshot['observed_at'])
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid observed_at') from exc
    if observed.tzinfo is None or observed.utcoffset() is None:
        raise ValueError('timezone required')
    title = _text(snapshot['title'], 'title', 160)
    sections = snapshot['sections']
    if type(sections) is not list or not 1 <= len(sections) <= 32:
        raise ValueError('sections must be bounded nonempty list')
    clean = []
    for section in sections:
        if not isinstance(section, Mapping) or set(section) != _SECTION_FIELDS:
            raise ValueError('invalid section fields')
        heading = _text(section['heading'], 'heading', 160)
        paragraphs = section['paragraphs']
        if type(paragraphs) is not list or not 1 <= len(paragraphs) <= 16:
            raise ValueError('paragraphs must be 1..16 entries')
        clean.append((heading, [_text(p, 'paragraph', 2000) for p in paragraphs]))
    age = (now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema': 'sofia.documents.safe_markdown.v1',
            'sdk_protocol': str(SDK_PROTOCOL_VERSION), 'module_id': MODULE_ID,
            'source_ref': source, 'freshness': freshness,
            'evidence_class': 'supplied_unverified', 'effect': 'none',
            'file_written': False, 'published': False, 'external_links_created': False}
    if freshness != 'fresh':
        return base | {'status': 'unknown', 'markdown': None, 'sha256': None,
                       'section_count': None, 'word_count': None}
    chunks = ['# ' + _ESC.sub(r'\\\1', title), '']
    word_count = len(title.split())
    for heading, paras in clean:
        chunks.extend(['## ' + _ESC.sub(r'\\\1', heading), ''])
        word_count += len(heading.split())
        for p in paras:
            chunks.extend([_ESC.sub(r'\\\1', p), ''])
            word_count += len(p.split())
    markdown = '\n'.join(chunks).rstrip() + '\n'
    raw = markdown.encode('utf-8')
    if len(raw) > 128 * 1024:
        raise ValueError('render exceeds document size bound')
    return base | {'status': 'rendered_in_memory', 'markdown': markdown,
                   'sha256': sha256(raw).hexdigest(),
                   'section_count': len(clean), 'word_count': word_count}


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Render bounded plain-text sections to safe inert Markdown.')
    def handler(request: CapabilityRequest):
        if not isinstance(request, CapabilityRequest) or request.capability != capability or set(request.parameters) != {'snapshot'}:
            raise ValueError('invalid documents capability request')
        return render_safe_markdown(request.parameters['snapshot'], now=datetime.now(timezone.utc))
    return ((capability, handler),)
