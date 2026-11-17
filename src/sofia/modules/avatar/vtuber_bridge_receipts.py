"""MOD-VTUBER-BRIDGE: validate supplied renderer adapter capabilities/receipts.

The capability consumes exact, unverified records only. It never opens a live
VTube Studio connection, starts a renderer, injects parameters, authenticates a
frame, or claims that an animation was applied. Existing adapter owners retain
all real execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping

from sofia.platform.capability.model import Capability, CapabilityRequest
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION

MODULE_ID = 'MOD-VTUBER-BRIDGE'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'avatar.vtuber_bridge.review_renderer_receipts.v1'
PROFILE = 'OBSERVE'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))

_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_SEMVER = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
_AUDIENCES = ('public', 'private')
_OPERATIONS = frozenset({
    'api_status', 'current_model', 'input_parameter_list',
    'inject_parameter_data', 'trigger_hotkey',
})
_FRAME_OPERATIONS = frozenset({'inject_parameter_data', 'trigger_hotkey'})
_MAX_CAPABILITIES = 16
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

_SNAPSHOT_FIELDS = frozenset({
    'source_ref', 'observed_at', 'audience', 'private_audience_claimed',
    'adapter', 'receipts',
})
_ADAPTER_FIELDS = frozenset({
    'adapter_id', 'adapter_version', 'protocol', 'transport', 'authenticated',
    'model_loaded', 'capabilities',
})
_RECEIPT_FIELDS = frozenset({
    'receipt_id', 'operation', 'requested_at', 'completed_at', 'accepted',
    'frame_count', 'audience',
})


def _exact(item: object, required, optional=(), label: str = 'record'):
    if not isinstance(item, Mapping):
        raise ValueError('exact ' + label + ' required')
    keys = set(item)
    if not set(required).issubset(keys) or not keys.issubset(set(required) | set(optional)):
        raise ValueError('exact ' + label + ' schema required')
    return item


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


def _choice(value: object, options, label: str) -> str:
    if not isinstance(value, str) or value not in options:
        raise ValueError('invalid ' + label)
    return value


def _note(value: object) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    if not isinstance(value, str) or len(value) > _MAX_NOTE:
        raise ValueError('invalid adapter receipt note')
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError('control characters in adapter receipt note')
    text = value
    removed = 0
    for pattern in (
        _SECRET_ASSIGN, _BEARER, _URL_USERINFO, _WIN_PATH, _UNC_PATH,
        _PRIVATE_PATH, _EMAIL,
    ):
        text, count = pattern.subn('<redacted>', text)
        removed += count
    return text, removed


def _adapter(item: object) -> dict[str, object]:
    _exact(item, _ADAPTER_FIELDS, label='renderer adapter')
    version = item['adapter_version']
    if not isinstance(version, str) or _SEMVER.fullmatch(version) is None:
        raise ValueError('invalid adapter version')
    capabilities = item['capabilities']
    if type(capabilities) is not list or len(capabilities) > _MAX_CAPABILITIES:
        raise ValueError('adapter capabilities must be a bounded list')
    checked: list[str] = []
    for capability in capabilities:
        if not isinstance(capability, str) or capability not in _OPERATIONS:
            raise ValueError('unsupported adapter capability')
        if capability in checked:
            raise ValueError('duplicate adapter capability')
        checked.append(capability)
    return {
        'adapter_id': _safe_ref(item['adapter_id'], 'adapter_id'),
        'adapter_version': version,
        'protocol': _choice(
            item['protocol'], ('VTubeStudioPublicAPI',), 'adapter protocol',
        ),
        'transport': _choice(item['transport'], ('localhost',), 'adapter transport'),
        'authenticated': _flag(item['authenticated'], 'adapter authenticated'),
        'model_loaded': _flag(item['model_loaded'], 'adapter model_loaded'),
        'capabilities': tuple(sorted(checked)),
    }


def _receipt(item: object) -> dict[str, object]:
    _exact(item, _RECEIPT_FIELDS, {'note'}, 'renderer receipt')
    operation = _choice(item['operation'], _OPERATIONS, 'adapter operation')
    requested_at = _time(item['requested_at'], 'receipt requested_at')
    completed_at = _time(item['completed_at'], 'receipt completed_at')
    if completed_at < requested_at:
        raise ValueError('receipt completion precedes the request')
    accepted = _flag(item['accepted'], 'receipt accepted')
    frame_count = _integer(item['frame_count'], 0, 240, 'receipt frame_count')
    if operation not in _FRAME_OPERATIONS and frame_count != 0:
        raise ValueError('non-frame operation cannot report animation frames')
    if not accepted and frame_count != 0:
        raise ValueError('rejected operation cannot report animation frames')
    note, redactions = _note(item.get('note'))
    return {
        'receipt_id': _safe_ref(item['receipt_id'], 'receipt_id'),
        'operation': operation,
        'requested_at': requested_at,
        'completed_at': completed_at,
        'accepted': accepted,
        'frame_count': frame_count,
        'audience': _choice(item['audience'], _AUDIENCES, 'receipt audience'),
        'note': note,
        'redactions': redactions,
    }


def review_vtuber_bridge_receipts(
    snapshot: Mapping[str, object], *, now: datetime,
    max_age_seconds: int = 300,
) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _integer(max_age_seconds, 1, 86400, 'max_age_seconds')
    _exact(snapshot, _SNAPSHOT_FIELDS, label='renderer bridge snapshot')

    source_ref = _safe_ref(snapshot['source_ref'], 'source_ref')
    observed_at = _time(snapshot['observed_at'], 'observed_at')
    audience = _choice(snapshot['audience'], _AUDIENCES, 'snapshot audience')
    private_claimed = _flag(
        snapshot['private_audience_claimed'], 'private_audience_claimed',
    )
    adapter = _adapter(snapshot['adapter'])

    raw_receipts = snapshot['receipts']
    if type(raw_receipts) is not list or not 1 <= len(raw_receipts) <= _MAX_RECEIPTS:
        raise ValueError('receipts must be a bounded nonempty list')
    receipts = [_receipt(item) for item in raw_receipts]
    receipt_ids: set[str] = set()
    for receipt in receipts:
        if receipt['receipt_id'] in receipt_ids:
            raise ValueError('duplicate adapter receipt identity')
        receipt_ids.add(receipt['receipt_id'])
        if audience == 'public' and receipt['audience'] == 'private':
            raise ValueError('private adapter receipt cannot enter a public snapshot')
        if (receipt['completed_at'] - observed_at).total_seconds() > 5:
            raise ValueError('adapter receipt completion is later than the snapshot')

    redactions = sum(receipt['redactions'] for receipt in receipts)
    age = (now.astimezone(timezone.utc) - observed_at).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {
        'schema': 'sofia.avatar.vtuber_bridge.receipt_review.v1',
        'module_id': MODULE_ID,
        'module_version': MODULE_VERSION,
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_ref': source_ref,
        'observed_at': observed_at.isoformat(),
        'audience': audience,
        'freshness': freshness,
        'adapter': {
            'adapter_id': adapter['adapter_id'],
            'adapter_version': adapter['adapter_version'],
            'protocol': adapter['protocol'],
            'transport': adapter['transport'],
            'authenticated_reported': adapter['authenticated'],
            'model_loaded_reported': adapter['model_loaded'],
            'capabilities': list(adapter['capabilities']),
        },
        'evidence_class': 'supplied_unverified',
        'effect': 'none',
        'live_connection_opened': False,
        'renderer_launched': False,
        'frame_authenticated': False,
        'animation_claimed': False,
        'adapter_control_sent': False,
    }
    if freshness != 'fresh':
        return base | {
            'status': 'unknown', 'counts': {}, 'receipts': [],
            'redactions': redactions,
        }

    declared = set(adapter['capabilities'])
    private_authorized_supplied = audience == 'private' and private_claimed
    counts = {
        'receipt_validated': 0,
        'reported_frame_unverified': 0,
        'rejected': 0,
        'restricted': 0,
        'undeclared_capability': 0,
    }
    rows: list[dict[str, object]] = []
    for receipt in sorted(receipts, key=lambda row: row['receipt_id']):
        flags: list[str] = []
        sensitive = receipt['audience'] == 'private'
        if sensitive and not private_authorized_supplied:
            outcome = 'restricted'
            flags.append('private_audience_not_authorized')
        elif receipt['operation'] not in declared:
            outcome = 'undeclared_capability'
            flags.append('adapter_capability_not_declared')
        elif not receipt['accepted']:
            outcome = 'rejected'
            flags.append('operation_rejected')
        elif receipt['frame_count'] > 0:
            outcome = 'reported_frame_unverified'
            flags.append('animation_not_authenticated')
        else:
            outcome = 'receipt_validated'
        counts[outcome] += 1
        rows.append({
            'receipt_id': receipt['receipt_id'],
            'operation': receipt['operation'],
            'accepted_reported': receipt['accepted'],
            'frame_count_reported': receipt['frame_count'],
            'outcome': outcome,
            'flags': sorted(flags),
            'note': None if outcome == 'restricted' else receipt['note'],
        })
    return base | {
        'status': 'reviewed',
        'counts': counts,
        'receipts': rows,
        'redactions': redactions,
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate supplied VTube Studio renderer adapter capabilities and '
        'receipts without opening a live connection.',
    )

    def handler(request: CapabilityRequest):
        if (
            not isinstance(request, CapabilityRequest)
            or request.capability != capability
            or set(request.parameters) != {'snapshot'}
        ):
            raise ValueError('invalid renderer bridge capability request')
        return review_vtuber_bridge_receipts(
            request.parameters['snapshot'], now=datetime.now(timezone.utc),
        )

    return ((capability, handler),)
