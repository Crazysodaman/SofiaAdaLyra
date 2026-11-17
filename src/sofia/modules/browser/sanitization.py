"""MOD-BROWSER: sanitize supplied page text/HTML into bounded untrusted evidence.

No page is fetched, rendered or executed. Scripts, styles, comments and tags are
removed from caller-supplied content before it is returned as untrusted text.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import html
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .analysis import MODULE_ID, MODULE_VERSION, PROFILE, RESOURCES

CAPABILITY_ID = 'browser.sanitize_page_evidence.v1'
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'pages'})
_PAGE_FIELDS = frozenset({'page_id', 'source_ref', 'content_type', 'content'})
_CONTENT_TYPES = ('text/plain', 'text/html')
_MAX_RAW = 40000
_MAX_TEXT = 20000
_SCRIPT_STYLE = re.compile(r'<(script|style)\b[^>]*>.*?</\1\s*>', re.I | re.S)
_COMMENT = re.compile(r'<!--.*?-->', re.S)
_TAG = re.compile(r'<[^>]*>')
_INJECTION = (
    (re.compile(r'\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?\b', re.I),
     'instruction_override'),
    (re.compile(r'\b(?:system|assistant|developer)\s*:', re.I), 'role_impersonation'),
    (re.compile(r'\byou\s+must\s+(?:now\s+)?(?:run|execute|send|delete|reveal|ignore)\b', re.I),
     'effect_directive'),
    (re.compile(r'\b(?:reveal|print|leak)\s+(?:the\s+)?'
                r'(?:system|secret|token|password|key)\b', re.I), 'secret_exfiltration'),
)


def _content(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= _MAX_RAW:
        raise ValueError('bounded page content required')
    if any(ord(c) == 0 or (ord(c) < 32 and c not in '\n\t\r') or ord(c) == 127
           for c in value):
        raise ValueError('unsafe control characters in page content')
    return value


def _sanitize_html(content: str) -> tuple[str, int, int, int, int]:
    escaped = html.unescape(content)
    script_count = len(re.findall(r'<script\b', escaped, re.I))
    style_count = len(re.findall(r'<style\b', escaped, re.I))
    comment_count = len(_COMMENT.findall(escaped))
    work = _COMMENT.sub('', _SCRIPT_STYLE.sub('', escaped))
    tag_count = len(_TAG.findall(work))
    work = _TAG.sub('', work)
    for _ in range(2):
        work = html.unescape(_TAG.sub('', _SCRIPT_STYLE.sub('', _COMMENT.sub('', work))))
    work = re.sub(r'[ \t\r\f\v]+', ' ', work)
    work = re.sub(r'\n[ ]*\n[ ]*\n+', '\n\n', work)
    text = work.strip()
    if len(text) > _MAX_TEXT:
        raise ValueError('sanitized page text exceeds bound')
    return text, tag_count, script_count, style_count, comment_count


def sanitize_page_evidence(snapshot: Mapping[str, object], *, now: datetime,
                           max_age_seconds: int = 1800) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact page evidence snapshot required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid freshness limit')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    try:
        obs = datetime.fromisoformat(snapshot['observed_at'])
    except (TypeError, ValueError) as exc:
        raise ValueError('invalid observed_at') from exc
    if obs.tzinfo is None or obs.utcoffset() is None:
        raise ValueError('timezone required')
    pages = snapshot['pages']
    if type(pages) is not list or not 1 <= len(pages) <= 32:
        raise ValueError('1..32 supplied pages required')
    seen = set()
    parsed = []
    for item in pages:
        if not isinstance(item, Mapping) or set(item) != _PAGE_FIELDS:
            raise ValueError('exact supplied page fields required')
        page_id = item['page_id']
        page_source = item['source_ref']
        if (not isinstance(page_id, str) or not _REF.fullmatch(page_id) or page_id in seen
                or not isinstance(page_source, str) or not _REF.fullmatch(page_source)):
            raise ValueError('duplicate or invalid page reference')
        seen.add(page_id)
        content_type = item['content_type']
        if not isinstance(content_type, str) or content_type not in _CONTENT_TYPES:
            raise ValueError('unsupported content type')
        parsed.append((page_id, page_source, content_type, _content(item['content'])))
    age = (now.astimezone(timezone.utc) - obs.astimezone(timezone.utc)).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema': 'sofia.browser.page_evidence.v1', 'module_id': MODULE_ID,
            'sdk_protocol': str(SDK_PROTOCOL_VERSION), 'source_ref': source,
            'freshness': freshness, 'evidence_class': 'supplied_unverified',
            'trust': 'untrusted', 'effect': 'none', 'instructions_executed': False,
            'network_requests_sent': False, 'dns_resolved': False, 'rendered': False}
    if freshness != 'fresh':
        return base | {'status': 'unknown', 'page_count': None,
                       'active_content_removed': None, 'instruction_marker_pages': [],
                       'pages': []}
    results = []
    marker_pages = []
    removed = 0
    for page_id, page_source, content_type, content in parsed:
        if content_type == 'text/html':
            text, tags, scripts, styles, comments = _sanitize_html(content)
            active = scripts + styles
        else:
            text = content.strip()
            if len(text) > _MAX_TEXT:
                raise ValueError('sanitized page text exceeds bound')
            tags = scripts = styles = comments = active = 0
        flags = [label for pattern, label in _INJECTION if pattern.search(text)]
        if flags:
            marker_pages.append(page_id)
        removed += active
        results.append({'page_id': page_id, 'source_ref': page_source,
                        'content_type': content_type, 'sanitized_text': text,
                        'text_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                        'sanitized_char_count': len(text), 'removed_tag_count': tags,
                        'removed_script_count': scripts, 'removed_style_count': styles,
                        'removed_comment_count': comments,
                        'instruction_markers': flags,
                        'treated_as_untrusted_data': True})
    return base | {'status': 'sanitized', 'page_count': len(results),
                   'active_content_removed': removed,
                   'instruction_marker_pages': sorted(marker_pages),
                   'pages': sorted(results, key=lambda p: p['page_id'])}


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Strip active content from supplied page text into bounded untrusted evidence.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid page sanitation request')
        return sanitize_page_evidence(request.parameters['snapshot'],
                                      now=datetime.now(timezone.utc))

    return ((capability, handler),)
