"""RM-VOICE: correlate supplied synthesis and playback receipts.

A queued or completed synthesis receipt is not proof of audible playback. This
reviewer accepts bounded, opaque receipt records and never opens an audio
device, synthesizes speech, or authenticates a playback outcome.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'RM-VOICE'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'voice.review_receipts.v1'
PROFILE = 'OBSERVE'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))

_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_SNAPSHOT_FIELDS = frozenset({'source_ref', 'observed_at', 'receipts'})
_RECEIPT_FIELDS = frozenset({
    'utterance_id', 'correlation_ref', 'stage', 'state', 'sequence', 'recorded_at',
})
_OPTIONAL_RECEIPT_FIELDS = frozenset({'note'})
_SYNTHESIS_STATES = frozenset({
    'queued', 'started', 'completed', 'failed', 'rejected', 'cancelled',
})
_PLAYBACK_STATES = frozenset({
    'queued', 'started', 'completed', 'failed', 'cancelled', 'interrupted',
})
_TRANSITIONS = {
    ('synthesis', 'queued'): frozenset({
        'started', 'completed', 'failed', 'rejected', 'cancelled',
    }),
    ('synthesis', 'started'): frozenset({'completed', 'failed', 'cancelled'}),
    ('playback', 'queued'): frozenset({
        'started', 'completed', 'failed', 'cancelled', 'interrupted',
    }),
    ('playback', 'started'): frozenset({
        'completed', 'failed', 'cancelled', 'interrupted',
    }),
}
_MAX_RECEIPTS = 128
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


def _integer(value: object, low: int, high: int, label: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError('invalid ' + label)
    return value


def _parse_receipt(item: object) -> dict[str, object]:
    if (
        not isinstance(item, Mapping)
        or not _RECEIPT_FIELDS.issubset(item)
        or not set(item).issubset(_RECEIPT_FIELDS | _OPTIONAL_RECEIPT_FIELDS)
    ):
        raise ValueError('exact voice receipt schema required')
    utterance_id = _safe_ref(item['utterance_id'], 'utterance_id')
    correlation_ref = _safe_ref(item['correlation_ref'], 'correlation_ref')
    stage = item['stage']
    if stage not in ('synthesis', 'playback'):
        raise ValueError('invalid receipt stage')
    states = _SYNTHESIS_STATES if stage == 'synthesis' else _PLAYBACK_STATES
    state = item['state']
    if not isinstance(state, str) or state not in states:
        raise ValueError('invalid receipt state for stage')
    sequence = _integer(item['sequence'], 1, 10000, 'sequence')
    recorded_at = _time(item['recorded_at'], 'recorded_at')
    note, redactions = _note(item.get('note'))
    return {
        'utterance_id': utterance_id,
        'correlation_ref': correlation_ref,
        'stage': stage,
        'state': state,
        'sequence': sequence,
        'recorded_at': recorded_at,
        'note': note,
        'redactions': redactions,
    }


def review_voice_receipts(snapshot: Mapping[str, object], *, now: datetime,
                          max_age_seconds: int = 1800) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _SNAPSHOT_FIELDS:
        raise ValueError('exact voice receipt snapshot required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _integer(max_age_seconds, 1, 86400, 'max_age_seconds')
    source = _safe_ref(snapshot['source_ref'], 'source_ref')
    observed = _time(snapshot['observed_at'], 'observed_at')
    receipts = snapshot['receipts']
    if type(receipts) is not list or not 1 <= len(receipts) <= _MAX_RECEIPTS:
        raise ValueError('receipts must be a bounded nonempty list')

    groups: dict[str, dict[str, object]] = {}
    seen_sequences: set[tuple[str, str, int]] = set()
    redactions = 0
    for raw in receipts:
        receipt = _parse_receipt(raw)
        utterance_id = receipt['utterance_id']
        stage = receipt['stage']
        sequence = receipt['sequence']
        recorded_at = receipt['recorded_at']
        if (recorded_at - observed).total_seconds() > 5:
            raise ValueError('receipt is later than the snapshot')
        key = (utterance_id, stage, sequence)
        if key in seen_sequences:
            raise ValueError('duplicate voice receipt sequence')
        seen_sequences.add(key)
        group = groups.setdefault(
            utterance_id,
            {'correlation_ref': receipt['correlation_ref'], 'stages': {}},
        )
        if group['correlation_ref'] != receipt['correlation_ref']:
            raise ValueError('correlation reference changed within utterance')
        stages = group['stages']
        stages.setdefault(stage, []).append(receipt)
        redactions += receipt['redactions']

    for utterance_id in sorted(groups):
        stages = groups[utterance_id]['stages']
        for stage in ('synthesis', 'playback'):
            records = sorted(stages.get(stage, []), key=lambda row: row['sequence'])
            previous = None
            for record in records:
                if previous is not None:
                    if record['recorded_at'] < previous['recorded_at']:
                        raise ValueError('receipt timeline moves backwards')
                    allowed = _TRANSITIONS.get((stage, previous['state']), frozenset())
                    if record['state'] not in allowed:
                        raise ValueError('invalid ' + stage + ' receipt transition')
                previous = record
            if records:
                stages[stage] = records

    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {
        'schema': 'sofia.voice.receipt_review.v1',
        'module_id': MODULE_ID,
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_ref': source,
        'observed_at': observed.isoformat(),
        'freshness': freshness,
        'evidence_class': 'supplied_unverified',
        'effect': 'none',
        'audio_device_accessed': False,
        'synthesis_authenticated': False,
        'playback_authenticated': False,
        'utterance_content_returned': False,
    }
    if freshness != 'fresh':
        return base | {
            'status': 'unknown',
            'counts': {},
            'utterances': [],
            'interruptions': [],
            'redactions': redactions,
        }

    outcomes: list[dict[str, object]] = []
    interruptions: list[str] = []
    counts = {
        'utterances': 0,
        'correlated_complete': 0,
        'interrupted': 0,
        'cancelled': 0,
        'failed': 0,
        'not_played': 0,
        'incomplete': 0,
        'unverified': 0,
    }
    for utterance_id in sorted(groups):
        stages = groups[utterance_id]['stages']
        synthesis = stages.get('synthesis', [])
        playback = stages.get('playback', [])
        synthesis_state = synthesis[-1]['state'] if synthesis else None
        playback_state = playback[-1]['state'] if playback else None
        flags: list[str] = []
        if synthesis_state is None:
            flags.append('synthesis_receipt_missing')
        elif synthesis_state != 'completed':
            flags.append('synthesis_not_completed_reported')
        if playback_state is None:
            flags.append('playback_receipt_missing')
        if playback and synthesis_state != 'completed':
            flags.append('playback_without_synthesis_completion')
            outcome = 'unverified'
        elif playback_state == 'interrupted':
            flags.append('playback_interrupted_reported')
            interruptions.append(utterance_id)
            outcome = 'interrupted'
        elif playback_state == 'cancelled':
            flags.append('playback_cancelled_reported')
            outcome = 'cancelled'
        elif 'failed' in (synthesis_state, playback_state) or synthesis_state == 'rejected':
            flags.append('failure_reported')
            outcome = 'failed'
        elif synthesis_state == 'completed' and playback_state == 'completed':
            outcome = 'correlated_complete'
        elif synthesis_state == 'completed' and playback_state is None:
            outcome = 'not_played'
        elif synthesis_state in ('queued', 'started') and playback_state is None:
            outcome = 'incomplete'
        else:
            outcome = 'incomplete'
        counts['utterances'] += 1
        counts[outcome] += 1
        latest_notes = [
            record['note'] for records in (synthesis, playback)
            for record in records[-1:] if record['note'] is not None
        ]
        outcomes.append({
            'utterance_id': utterance_id,
            'synthesis_state': synthesis_state,
            'playback_state': playback_state,
            'outcome': outcome,
            'flags': sorted(flags),
            'note': latest_notes[-1] if latest_notes else None,
        })
    return base | {
        'status': 'reviewed',
        'counts': counts,
        'utterances': outcomes,
        'interruptions': sorted(interruptions),
        'redactions': redactions,
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Correlate bounded supplied voice receipts without audio device access.',
    )

    def handler(request: CapabilityRequest):
        if (
            not isinstance(request, CapabilityRequest)
            or request.capability != capability
            or set(request.parameters) != {'snapshot'}
        ):
            raise ValueError('invalid voice capability request')
        return review_voice_receipts(
            request.parameters['snapshot'], now=datetime.now(timezone.utc),
        )

    return ((capability, handler),)
