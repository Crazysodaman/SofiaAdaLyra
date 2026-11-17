"""MOD-INTERACTION: validate supplied pointer, hit-region and gesture offers.

Only exact, caller-supplied, unverified records are inspected. This capability
does not capture input, authenticate a painted frame, grant consent, claim that
a gesture occurred, or choose Sofia's reaction. Core remains the
 only owner of
the reaction decision.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Mapping

from sofia.modules.interaction.core import GESTURES
from sofia.platform.capability.model import Capability, CapabilityRequest
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION

MODULE_ID = 'MOD-INTERACTION'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'interaction.review_pointer_gesture_offer.v1'
PROFILE = 'OBSERVE'
RESOURCES = (('cpu_millicores', 40), ('ram_mib', 24), ('gpu_mib', 0))

_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_DIGEST = re.compile(r'^[0-9a-f]{64}$')
_AUDIENCES = ('public', 'private')
_POINTER_PHASES = ('down', 'move', 'up', 'cancel')
_OFFER_PHASES = ('begin', 'update', 'end', 'cancel')
_MAX_REGIONS = 64
_MAX_OFFERS = 32
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
    'current_frame', 'pointer', 'hit_regions', 'gesture_offers',
})
_FRAME_FIELDS = frozenset({'frame_id', 'presentation_revision', 'bundle_digest'})
_POINTER_FIELDS = frozenset({
    'pointer_id', 'frame_id', 'presentation_revision', 'x', 'y', 'phase',
    'occurred_at',
})
_REGION_FIELDS = frozenset({
    'region_id', 'layer_id', 'z_index', 'x', 'y', 'width', 'height',
    'opaque', 'audience', 'region_private',
})
_OFFER_FIELDS = frozenset({
    'offer_id', 'gesture', 'region_id', 'phase', 'expires_at', 'audience',
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


def _number(value: object, low: float, high: float, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('invalid ' + label)
    result = float(value)
    if not low <= result <= high:
        raise ValueError('invalid ' + label)
    return result


def _flag(value: object, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError('invalid ' + label)
    return value


def _choice(value: object, options: tuple[str, ...], label: str) -> str:
    if not isinstance(value, str) or value not in options:
        raise ValueError('invalid ' + label)
    return value


def _note(value: object) -> tuple[str | None, int]:
    if value is None:
        return None, 0
    if not isinstance(value, str) or len(value) > _MAX_NOTE:
        raise ValueError('invalid pointer note')
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError('control characters in pointer note')
    text = value
    removed = 0
    for pattern in (
        _SECRET_ASSIGN, _BEARER, _URL_USERINFO, _WIN_PATH, _UNC_PATH,
        _PRIVATE_PATH, _EMAIL,
    ):
        text, count = pattern.subn('<redacted>', text)
        removed += count
    return text, removed


def _frame(item: object) -> dict[str, object]:
    _exact(item, _FRAME_FIELDS, label='current frame')
    digest = item['bundle_digest']
    if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
        raise ValueError('validated asset bundle digest required')
    return {
        'frame_id': _safe_ref(item['frame_id'], 'frame_id'),
        'presentation_revision': _integer(
            item['presentation_revision'], 0, 1_000_000_000, 'presentation_revision',
        ),
        'bundle_digest': digest,
    }


def _pointer(item: object) -> dict[str, object]:
    _exact(item, _POINTER_FIELDS, {'note'}, 'pointer record')
    x = _number(item['x'], 0.0, 1.0, 'pointer x')
    y = _number(item['y'], 0.0, 1.0, 'pointer y')
    if x >= 1.0 or y >= 1.0:
        raise ValueError('pointer must remain inside the normalized viewport')
    occurred_at = _time(item['occurred_at'], 'pointer occurred_at')
    note, redactions = _note(item.get('note'))
    return {
        'pointer_id': _safe_ref(item['pointer_id'], 'pointer_id'),
        'frame_id': _safe_ref(item['frame_id'], 'pointer frame_id'),
        'presentation_revision': _integer(
            item['presentation_revision'], 0, 1_000_000_000,
            'pointer presentation_revision',
        ),
        'x': x,
        'y': y,
        'phase': _choice(item['phase'], _POINTER_PHASES, 'pointer phase'),
        'occurred_at': occurred_at,
        'note': note,
        'redactions': redactions,
    }


def _region(item: object) -> dict[str, object]:
    _exact(item, _REGION_FIELDS, {'garment_id'}, 'hit region')
    x = _number(item['x'], 0.0, 1.0, 'hit region x')
    y = _number(item['y'], 0.0, 1.0, 'hit region y')
    width = _number(item['width'], 0.0, 1.0, 'hit region width')
    height = _number(item['height'], 0.0, 1.0, 'hit region height')
    if width <= 0.0 or height <= 0.0:
        raise ValueError('hit region extent must be positive')
    if x + width > 1.0 + 1e-9 or y + height > 1.0 + 1e-9:
        raise ValueError('hit region exceeds the normalized viewport')
    garment_id = item.get('garment_id')
    if garment_id is not None:
        garment_id = _safe_ref(garment_id, 'garment_id')
    return {
        'region_id': _safe_ref(item['region_id'], 'region_id'),
        'layer_id': _safe_ref(item['layer_id'], 'layer_id'),
        'z_index': _integer(item['z_index'], -1000, 1000, 'z_index'),
        'x': x,
        'y': y,
        'width': width,
        'height': height,
        'opaque': _flag(item['opaque'], 'opaque'),
        'audience': _choice(item['audience'], _AUDIENCES, 'hit region audience'),
        'region_private': _flag(item['region_private'], 'region_private'),
        'garment_id': garment_id,
    }


def _offer(item: object) -> dict[str, object]:
    _exact(item, _OFFER_FIELDS, {'note'}, 'gesture offer')
    gesture = item['gesture']
    if not isinstance(gesture, str) or gesture not in GESTURES:
        raise ValueError('invalid gesture offer verb')
    note, redactions = _note(item.get('note'))
    return {
        'offer_id': _safe_ref(item['offer_id'], 'offer_id'),
        'gesture': gesture,
        'region_id': _safe_ref(item['region_id'], 'offer region_id'),
        'phase': _choice(item['phase'], _OFFER_PHASES, 'offer phase'),
        'expires_at': _time(item['expires_at'], 'offer expires_at'),
        'audience': _choice(item['audience'], _AUDIENCES, 'offer audience'),
        'note': note,
        'redactions': redactions,
    }


def _contains(region: Mapping[str, object], x: float, y: float) -> bool:
    return (
        float(region['x']) <= x < float(region['x']) + float(region['width'])
        and float(region['y']) <= y < float(region['y']) + float(region['height'])
    )


def review_pointer_gesture_offer(
    snapshot: Mapping[str, object], *, now: datetime,
    max_age_seconds: int = 300, max_pointer_age_seconds: int = 5,
) -> dict[str, object]:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _integer(max_age_seconds, 1, 86400, 'max_age_seconds')
    _integer(max_pointer_age_seconds, 1, 86400, 'max_pointer_age_seconds')
    _exact(snapshot, _SNAPSHOT_FIELDS, label='pointer snapshot')

    source_ref = _safe_ref(snapshot['source_ref'], 'source_ref')
    observed_at = _time(snapshot['observed_at'], 'observed_at')
    audience = _choice(snapshot['audience'], _AUDIENCES, 'snapshot audience')
    private_claimed = _flag(
        snapshot['private_audience_claimed'], 'private_audience_claimed',
    )
    current_frame = _frame(snapshot['current_frame'])
    pointer = _pointer(snapshot['pointer'])

    raw_regions = snapshot['hit_regions']
    if type(raw_regions) is not list or not 1 <= len(raw_regions) <= _MAX_REGIONS:
        raise ValueError('hit_regions must be a bounded nonempty list')
    regions = [_region(item) for item in raw_regions]
    layers: set[str] = set()
    privacy: dict[str, bool] = {}
    for region in regions:
        layer_id = region['layer_id']
        if layer_id in layers:
            raise ValueError('duplicate hit layer identity')
        layers.add(layer_id)
        if audience == 'public' and region['audience'] == 'private':
            raise ValueError('private hit region cannot enter a public pointer snapshot')
        sensitive = region['audience'] == 'private' or region['region_private']
        if region['region_id'] in privacy and privacy[region['region_id']] != sensitive:
            raise ValueError('conflicting hit region privacy classification')
        privacy[region['region_id']] = sensitive

    raw_offers = snapshot['gesture_offers']
    if type(raw_offers) is not list or len(raw_offers) > _MAX_OFFERS:
        raise ValueError('gesture_offers must be a bounded list')
    offers = [_offer(item) for item in raw_offers]
    offer_ids: set[str] = set()
    for offer in offers:
        if offer['offer_id'] in offer_ids:
            raise ValueError('duplicate gesture offer identity')
        offer_ids.add(offer['offer_id'])
        if audience == 'public' and offer['audience'] == 'private':
            raise ValueError('private gesture offer cannot enter a public snapshot')

    if (pointer['occurred_at'] - observed_at).total_seconds() > 5:
        raise ValueError('pointer occurs after the snapshot')

    redactions = pointer['redactions'] + sum(offer['redactions'] for offer in offers)
    age = (now.astimezone(timezone.utc) - observed_at).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {
        'schema': 'sofia.interaction.pointer_gesture_offer_review.v1',
        'module_id': MODULE_ID,
        'module_version': MODULE_VERSION,
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_ref': source_ref,
        'observed_at': observed_at.isoformat(),
        'audience': audience,
        'freshness': freshness,
        'evidence_class': 'supplied_unverified',
        'effect': 'none',
        'input_captured': False,
        'frame_authenticated': False,
        'gesture_claimed': False,
        'gesture_offer_accepted': False,
        'reaction_decided': False,
        'consent_granted': False,
        'core_reaction_required': True,
    }
    if freshness != 'fresh':
        return base | {
            'status': 'unknown', 'pointer': None, 'offers': [],
            'counts': {}, 'redactions': redactions,
        }

    private_authorized_supplied = audience == 'private' and private_claimed
    if (
        pointer['frame_id'] != current_frame['frame_id']
        or pointer['presentation_revision'] != current_frame['presentation_revision']
        or (now.astimezone(timezone.utc) - pointer['occurred_at']).total_seconds()
        > max_pointer_age_seconds
    ):
        return base | {
            'status': 'stale',
            'pointer': {
                'pointer_id': pointer['pointer_id'],
                'phase': pointer['phase'],
                'outcome': 'stale',
                'flags': ['stale_pointer_record'],
            },
            'offers': [],
            'counts': {},
            'redactions': redactions,
        }

    candidates = [
        region for region in regions
        if region['opaque'] and _contains(region, pointer['x'], pointer['y'])
    ]
    top = max(candidates, key=lambda row: (row['z_index'], row['layer_id'])) if candidates else None
    if top is None:
        pointer_outcome = 'miss'
        pointer_row = {
            'pointer_id': pointer['pointer_id'],
            'phase': pointer['phase'],
            'outcome': 'miss',
            'flags': ['no_opaque_hit'],
        }
        pointer_region = None
    elif privacy[top['region_id']] and not private_authorized_supplied:
        pointer_outcome = 'restricted'
        pointer_row = {
            'pointer_id': pointer['pointer_id'],
            'phase': pointer['phase'],
            'outcome': 'restricted',
            'flags': ['private_audience_not_authorized'],
        }
        pointer_region = None
    else:
        pointer_outcome = 'hit'
        pointer_row = {
            'pointer_id': pointer['pointer_id'],
            'phase': pointer['phase'],
            'outcome': 'hit',
            'flags': [],
            'region_id': top['region_id'],
            'layer_id': top['layer_id'],
            'garment_id': top['garment_id'],
        }
        pointer_region = top['region_id']

    offer_rows: list[dict[str, object]] = []
    counts = {
        'pointer_hit': int(pointer_outcome == 'hit'),
        'pointer_miss': int(pointer_outcome == 'miss'),
        'pointer_restricted': int(pointer_outcome == 'restricted'),
        'offers_eligible': 0,
        'offers_rejected': 0,
    }
    current = now.astimezone(timezone.utc)
    for offer in sorted(offers, key=lambda row: row['offer_id']):
        sensitive = offer['audience'] == 'private' or privacy.get(offer['region_id'], False)
        flags: list[str] = []
        if sensitive and not private_authorized_supplied:
            outcome = 'restricted'
            flags.append('private_audience_not_authorized')
        elif offer['expires_at'] < current:
            outcome = 'expired'
            flags.append('offer_expired')
        elif offer['region_id'] not in privacy:
            outcome = 'unknown_region'
            flags.append('unknown_region')
        elif offer['phase'] != 'end':
            outcome = 'incomplete'
            flags.append('offer_not_complete')
        elif pointer_region is None:
            outcome = 'no_pointer_hit'
            flags.append('no_pointer_hit')
        elif offer['region_id'] != pointer_region:
            outcome = 'region_mismatch'
            flags.append('pointer_region_mismatch')
        else:
            outcome = 'eligible_candidate'
        if outcome == 'eligible_candidate':
            counts['offers_eligible'] += 1
        else:
            counts['offers_rejected'] += 1
        row = {
            'offer_id': offer['offer_id'],
            'gesture': offer['gesture'],
            'region_id': None if outcome == 'restricted' else offer['region_id'],
            'phase': offer['phase'],
            'outcome': outcome,
            'flags': sorted(flags),
            'note': None if outcome == 'restricted' else offer['note'],
        }
        offer_rows.append(row)

    status = (
        'restricted' if pointer_outcome == 'restricted'
        else 'reviewed'
    )
    return base | {
        'status': status,
        'pointer': pointer_row,
        'offers': offer_rows,
        'counts': counts,
        'redactions': redactions,
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate supplied pointer, hit-region and gesture-offer records '
        'without capturing input or deciding a reaction.',
    )

    def handler(request: CapabilityRequest):
        if (
            not isinstance(request, CapabilityRequest)
            or request.capability != capability
            or set(request.parameters) != {'snapshot'}
        ):
            raise ValueError('invalid pointer gesture capability request')
        return review_pointer_gesture_offer(
            request.parameters['snapshot'], now=datetime.now(timezone.utc),
        )

    return ((capability, handler),)
