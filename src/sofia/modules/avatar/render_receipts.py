"""RM-AVATAR2D: validate bounded supplied render and frame receipts.

A render request is not a painted frame. This reviewer accepts only exact,
opaque receipt records and never launches a renderer, accesses sprites, or
claims that a frame was authenticated by a display driver.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'RM-AVATAR2D'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'avatar2d.review_render_receipts.v1'
PROFILE = 'OBSERVE'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))

_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_SNAPSHOT_FIELDS = frozenset({'source_ref', 'observed_at', 'current_revision', 'receipts'})
_RECEIPT_FIELDS = frozenset({
    'decision_id', 'revision', 'requested_at', 'callback_at',
    'rendered', 'visible', 'frame_count',
})
_OPTIONAL_RECEIPT_FIELDS = frozenset({'note'})
_MAX_RECEIPTS = 64
_MAX_NOTE = 280
_SENSITIVE_SEGMENTS = frozenset({
    'password', 'passwd', 'secret', 'secrets', 'token', 'apikey', 'api_key',
    'credential', 'credentials', 'private_key', 'privkey', 'access_key',
})
_SECRET_ASSIGN = re.compile(
    r'(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key'
    r'|private[_-]?key|credential)s?\s*[:=]\s*[^\s,;]{1,256}'
)
_BEARER = re.compile(r'(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}')
_URL_USERINFO = re.compile(r'(?i)\b([a-z][a-z0-9+.-]*://)[^/\s@]{1,256}@')
_WIN_PATH = re.compile(r'(?i)\b[A-Za-z]:\\(?:[^\s,;\\]+\\){0,12}[^\s,;\\]*')
_UNC_PATH = re.compile(r'\\\\[^\s,;]{1,256}')
_PRIVATE_PATH = re.compile(
    r'(?i)(?<![\w.-])/(?:home|users|root|private|etc|tmp|var|opt|srv|mnt|data)/[^\s,;]{1,256}'
)
_EMAIL = re.compile(r'(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')


def _safe_ref(value: object, label: str) -> str:
    if not isinstance(value, str) or _REF.fullmatch(value) is None:
        raise ValueError('invalid ' + label)
    if '\\' in value or '//' in value or re.match(r'^[A-Za-z]:/', value):
        raise ValueError('unsafe ' + label)
    if re.search(
        r'(?i)(^|[:/])(?:home|users|root|private|etc|tmp|var|opt|srv|mnt|data)(?:/|$)',
        value,
    ):
        raise ValueError('private path in ' + label)
    segments = re.split(r'[:/]', value)
    if any(segment in {'', '.', '..'} for segment in segments):
        raise ValueError('unsafe ' + label)
    if any(segment.lower() in _SENSITIVE_SEGMENTS for segment in segments):
        raise ValueError('sensitive ' + label)
    return value


def _time(value: object, label: str) -> datetime:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError('invalid ' + label)
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid ' + label) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError(label + ' requires timezone')
    return result.astimezone(timezone.utc)


def _integer(value: object, low: int, high: int, label: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid ' + label)
    return value


def _flag(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError('invalid ' + label)
    return value


def _note(value: object) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    if not isinstance(value, str) or len(value) > _MAX_NOTE:
        raise ValueError('invalid receipt note')
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError('control characters in receipt note')
    text = value
    removed = 0
    for pattern in (
        _SECRET_ASSIGN, _BEARER, _URL_USERINFO, _WIN_PATH, _UNC_PATH,
        _PRIVATE_PATH, _EMAIL,
    ):
        text, count = pattern.subn('<redacted>', text)
        removed += count
    return text, removed


def _parse_receipt(item: object) -> dict[str, object]:
    if (
        not isinstance(item, Mapping)
        or not _RECEIPT_FIELDS.issubset(item)
        or not set(item).issubset(_RECEIPT_FIELDS | _OPTIONAL_RECEIPT_FIELDS)
    ):
        raise ValueError('exact avatar render receipt schema required')
    decision_id = _safe_ref(item['decision_id'], 'decision_id')
    revision = _integer(item['revision'], 0, 1_000_000_000, 'revision')
    requested_at = _time(item['requested_at'], 'requested_at')
    callback_at = _time(item['callback_at'], 'callback_at')
    if callback_at < requested_at:
        raise ValueError('render callback precedes request')
    rendered = _flag(item['rendered'], 'rendered')
    visible = _flag(item['visible'], 'visible')
    frame_count = _integer(item['frame_count'], 0, 240, 'frame_count')
    if rendered and not visible:
        raise ValueError('rendered receipt requires a visible frame')
    if rendered and frame_count < 1:
        raise ValueError('rendered receipt requires at least one frame')
    if not rendered and frame_count != 0:
        raise ValueError('frame count without a rendered receipt')
    note, redactions = _note(item.get('note'))
    return {
        'decision_id': decision_id,
        'revision': revision,
        'requested_at': requested_at,
        'callback_at': callback_at,
        'rendered': rendered,
        'visible': visible,
        'frame_count': frame_count,
        'note': note,
        'redactions': redactions,
    }


def review_avatar_render_receipts(
    snapshot: Mapping[str, object], *, now: datetime,
    max_age_seconds: int = 300,
) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _SNAPSHOT_FIELDS:
        raise ValueError('exact avatar render receipt snapshot required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _integer(max_age_seconds, 1, 86400, 'max_age_seconds')
    source = _safe_ref(snapshot['source_ref'], 'source_ref')
    observed = _time(snapshot['observed_at'], 'observed_at')
    current_revision = _integer(
        snapshot['current_revision'], 0, 1_000_000_000, 'current_revision',
    )
    receipts = snapshot['receipts']
    if type(receipts) is not list or not 1 <= len(receipts) <= _MAX_RECEIPTS:
        raise ValueError('receipts must be a bounded nonempty list')

    parsed: list[dict[str, object]] = []
    seen: set[str] = set()
    redactions = 0
    for raw in receipts:
        receipt = _parse_receipt(raw)
        decision_id = receipt['decision_id']
        if decision_id in seen:
            raise ValueError('duplicate render decision identity')
        seen.add(decision_id)
        if receipt['revision'] > current_revision:
            raise ValueError('render receipt revision is ahead of current')
        if (receipt['callback_at'] - observed).total_seconds() > 5:
            raise ValueError('render callback is later than the snapshot')
        redactions += receipt['redactions']
        parsed.append(receipt)

    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {
        'schema': 'sofia.avatar2d.render_receipt_review.v1',
        'module_id': MODULE_ID,
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_ref': source,
        'observed_at': observed.isoformat(),
        'current_revision': current_revision,
        'freshness': freshness,
        'evidence_class': 'supplied_unverified',
        'effect': 'none',
        'renderer_launched': False,
        'sprite_assets_accessed': False,
        'frame_authenticated': False,
    }
    if freshness != 'fresh':
        return base | {
            'status': 'unknown',
            'counts': {},
            'receipts': [],
            'redactions': redactions,
        }

    outcomes: list[dict[str, object]] = []
    counts = {'receipt_validated': 0, 'no_frame': 0, 'stale': 0}
    for receipt in sorted(parsed, key=lambda row: row['decision_id']):
        flags: list[str] = []
        if receipt['revision'] < current_revision:
            flags.append('stale_revision')
            outcome = 'stale'
        elif not receipt['rendered']:
            flags.append('no_frame_receipt')
            if not receipt['visible']:
                flags.append('window_not_visible_reported')
            outcome = 'no_frame'
        else:
            outcome = 'receipt_validated'
        counts[outcome] += 1
        outcomes.append({
            'decision_id': receipt['decision_id'],
            'revision': receipt['revision'],
            'rendered_reported': receipt['rendered'],
            'visible_reported': receipt['visible'],
            'frame_count_reported': receipt['frame_count'],
            'outcome': outcome,
            'flags': sorted(flags),
            'note': receipt['note'],
        })
    return base | {
        'status': 'reviewed',
        'counts': counts,
        'receipts': outcomes,
        'redactions': redactions,
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate bounded supplied 2D render receipts without launching a renderer.',
    )

    def handler(request: CapabilityRequest):
        if (
            not isinstance(request, CapabilityRequest)
            or request.capability != capability
            or set(request.parameters) != {'snapshot'}
        ):
            raise ValueError('invalid avatar render capability request')
        return review_avatar_render_receipts(
            request.parameters['snapshot'], now=datetime.now(timezone.utc),
        )

    return ((capability, handler),)
