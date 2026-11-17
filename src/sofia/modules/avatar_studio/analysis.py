"""Check proposed layered wardrobe assets without installing/altering avatar art.

Capability performs bounded analysis of supplied, UNVERIFIED projections only.
No real-world effects, authorized execution, persistence or identity assertions.
Existing Sofía V18 owner components retain control of all real operations.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-AVATAR-STUDIO'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'avatar_studio.review_asset_layers.v1'
MANIFEST_CAPABILITY_ID = 'avatar_studio.review_authoring_manifest.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))  # provisional admission request
_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_DIGEST = re.compile(r'^[0-9a-f]{64}$')
_SEMVER = re.compile(r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')
_TRAVERSAL = re.compile(r'(?:^|[:/])\.\.?(?:[:/]|$)')
_PRIVATE_SEGMENTS = frozenset({'home', 'users', 'root', 'private', 'secrets', 'etc', 'tmp', 'var', 'opt', 'srv', 'mnt', 'data'})
_SUPPORTED_MANIFEST_MAJORS = frozenset({'1', '2'})


def _identity(value: object, label: str = 'id') -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError('invalid '+label)
    return value


def _exact(item: object, keys: tuple[str, ...]) -> Mapping[str, object]:
    if not isinstance(item, Mapping) or set(item) != set(keys):
        raise ValueError('unexpected fields in supplied projection')
    return item


def _num(value: object, lo: float, hi: float, name: str = 'number') -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError('invalid '+name)
    return float(value)


def _int(value: object, lo: int, hi: int, name: str = 'integer') -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('invalid '+name)
    return value


def _bool(value: object, name: str = 'flag') -> bool:
    if type(value) is not bool:
        raise ValueError('invalid '+name)
    return value


def _choice(value: object, options: tuple[str, ...], label: str = 'choice') -> str:
    if type(value) is not str or value not in options:
        raise ValueError('invalid '+label)
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError('timestamp required')
    try: date = datetime.fromisoformat(value)
    except ValueError as exc: raise ValueError('invalid timestamp') from exc
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError('timestamp requires timezone')
    return date.astimezone(timezone.utc)


def _base(snapshot: Mapping[str, object], now: datetime, max_age_seconds: int):
    _exact(snapshot, ('source_ref', 'observed_at', 'items'))
    _identity(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    observed = _timestamp(snapshot['observed_at'])
    age = (now.astimezone(timezone.utc)-observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    items = snapshot['items']
    if type(items) is not list or len(items) > 128:
        raise ValueError('items must be a bounded list')
    return items, observed, freshness


def _safe_ref(value: object, label: str = 'id') -> str:
    text = _identity(value, label)
    if '\\' in text or '//' in text or re.match(r'^[A-Za-z]:', text):
        raise ValueError('unsafe '+label)
    if _TRAVERSAL.search(text):
        raise ValueError('unsafe '+label)
    if any(segment.lower() in _PRIVATE_SEGMENTS for segment in text.split('/')):
        raise ValueError('private path in '+label)
    return text


def _digest(value: object, label: str = 'digest') -> str:
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError('invalid '+label)
    return value


def _refs(value: object, label: str = 'reference', maximum: int = 64) -> tuple[str, ...]:
    if type(value) is not list or len(value) > maximum:
        raise ValueError(label+'s must be a bounded list')
    refs = tuple(_safe_ref(item, label) for item in value)
    if len(set(refs)) != len(refs):
        raise ValueError('duplicate '+label)
    return refs


def _envelope(snapshot: Mapping[str, object], key: str, now: datetime, max_age_seconds: int):
    _exact(snapshot, ('source_ref', 'observed_at', key))
    _safe_ref(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    observed = _timestamp(snapshot['observed_at'])
    age = (now.astimezone(timezone.utc)-observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    payload = snapshot[key]
    if not isinstance(payload, Mapping):
        raise ValueError('invalid '+key)
    return payload, observed, freshness


def review_authoring_manifest(snapshot: Mapping[str, object], *, now: datetime,
                              max_age_seconds: int = 3600) -> dict[str, object]:
    manifest, observed, freshness = _envelope(snapshot, 'manifest', now, max_age_seconds)
    _exact(manifest, ('manifest_version', 'scene_id', 'revision', 'audience', 'assets'))
    version = manifest['manifest_version']
    if type(version) is not str or _SEMVER.fullmatch(version) is None:
        raise ValueError('invalid manifest version')
    _safe_ref(manifest['scene_id'], 'scene_id')
    revision = _int(manifest['revision'], 0, 2_000_000_000, 'revision')
    declared_audience = _choice(manifest['audience'], ('public', 'private'), 'manifest audience')
    assets_raw = manifest['assets']
    if type(assets_raw) is not list or len(assets_raw) > 128:
        raise ValueError('assets must be a bounded list')

    assets: list[dict[str, object]] = []
    by_id: dict[str, dict[str, object]] = {}
    for item in assets_raw:
        row = _exact(item, ('id', 'kind', 'digest', 'layer_slot', 'layer_order',
                            'audience', 'depends_on', 'reviewed'))
        key = _safe_ref(row['id'], 'asset id')
        if key in by_id:
            raise ValueError('duplicate asset identity')
        record = {
            'id': key,
            'kind': _choice(row['kind'], ('scene', 'wardrobe', 'rig', 'texture'), 'asset kind'),
            'digest': _digest(row['digest'], 'asset digest'),
            'layer_slot': _choice(row['layer_slot'], ('scene', 'base', 'hair', 'eyes', 'top',
                                                      'bottom', 'shoes', 'accessory', 'tail', 'ears'),
                                  'layer slot'),
            'layer_order': _int(row['layer_order'], 0, 1000, 'layer order'),
            'audience': _choice(row['audience'], ('public', 'private'), 'asset audience'),
            'depends_on': _refs(row['depends_on'], 'asset dependency'),
            'reviewed': _bool(row['reviewed'], 'reviewed flag'),
        }
        by_id[key] = record
        assets.append(record)

    version_major = version.split('.', 1)[0]
    classification = ('private' if declared_audience == 'private'
                      or any(asset['audience'] != 'public' for asset in assets) else 'public')
    hard: set[str] = set()
    if version_major not in _SUPPORTED_MANIFEST_MAJORS:
        hard.add('unsupported_manifest_version')
    if not assets:
        hard.add('empty_manifest')
    if declared_audience == 'public' and any(asset['audience'] != 'public' for asset in assets):
        hard.add('private_asset_in_public_manifest')
    occupied: set[tuple[object, object]] = set()
    for asset in assets:
        slot_layer = (asset['layer_slot'], asset['layer_order'])
        if slot_layer in occupied:
            hard.add('duplicate_slot_layer')
        occupied.add(slot_layer)
    positions = {asset['id']: index for index, asset in enumerate(assets)}
    for index, asset in enumerate(assets):
        for dependency in asset['depends_on']:
            if dependency not in by_id:
                hard.add('missing_asset_dependency')
            elif dependency == asset['id']:
                hard.add('self_dependency')
            elif positions[dependency] >= index:
                hard.add('forward_dependency')
    unreviewed = any(asset['reviewed'] is not True for asset in assets)
    findings = sorted(hard | ({'asset_review_missing'} if unreviewed else set()))

    base = dict(schema='sofia.avatar_studio.authoring_manifest.v1', module_id=MODULE_ID,
                sdk_protocol=str(SDK_PROTOCOL_VERSION), source_ref=snapshot['source_ref'],
                observed_at=observed.isoformat(), freshness=freshness,
                evidence_class='supplied_unverified', effect='none', action_authorized=False,
                data_persisted=False, render_claimed=False, wardrobe_modified=False,
                assets_modified=False)
    if freshness != 'fresh':
        return base | dict(status='unknown', compatible=None, classification=None,
                           review_required=None, findings=['snapshot_timestamp_invalid'],
                           manifest=None, assets=None)
    summary = dict(manifest_version=version, revision=revision,
                   declared_audience=declared_audience, asset_count=len(assets),
                   classification=classification)
    public_assets = None if classification == 'private' else [
        {'id': asset['id'], 'kind': asset['kind'], 'layer_slot': asset['layer_slot'],
         'layer_order': asset['layer_order'], 'audience': asset['audience'],
         'reviewed': asset['reviewed'], 'dependency_count': len(asset['depends_on'])}
        for asset in assets
    ]
    return base | dict(status='reviewed', compatible=not hard,
                       classification=classification,
                       review_required=bool(hard or unreviewed),
                       findings=findings, manifest=summary, assets=public_assets)


def _review(item: Mapping[str, object]) -> dict[str, object]:
    row=_exact(item,('id','slot','layer_order','content_class','reviewed','alpha_present'))
    key=_identity(row['id']); slot=_choice(row['slot'],('base','hair','eyes','top','bottom','shoes','accessory','tail','ears'))
    order=_int(row['layer_order'],0,1000); cls=_choice(row['content_class'],('public','private','adult'))
    reviewed=_bool(row['reviewed']); alpha=_bool(row['alpha_present'])
    reasons=(['private_distribution_review_required'] if cls!='public' else []) + (['asset_review_missing'] if not reviewed else []) + (['alpha_channel_missing'] if not alpha else [])
    return dict(id=key,slot=slot,layer_order=order,finding='public_asset_candidate' if not reasons else 'requires_review',issues=reasons, wardrobe_modified=False)



def review_avatar_studio(snapshot: Mapping[str, object], *, now: datetime,
              max_age_seconds: int = 3600) -> dict[str, object]:
    items, observed, freshness = _base(snapshot, now, max_age_seconds)
    results = [_review(item) for item in items]
    ids = [r['id'] for r in results]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate item identity')
    seen_layers=set()
    for record in results:
        slot_layer=(record['slot'],record['layer_order'])
        if slot_layer in seen_layers:
            record['finding']='duplicate_slot_layer'
        seen_layers.add(slot_layer)
    findings = sorted({r['finding'] for r in results})
    base = dict(schema='sofia.avatar_studio.projection_review.v1', module_id=MODULE_ID, sdk_protocol=str(SDK_PROTOCOL_VERSION),
                source_ref=snapshot['source_ref'], observed_at=observed.isoformat(),
                freshness=freshness, evidence_class='supplied_unverified', effect='none',
                action_authorized=False, data_persisted=False)
    if freshness != 'fresh':
        return base | dict(status='unknown', inspected_count=None, findings=['snapshot_timestamp_invalid'], results=[])
    return base | dict(status='reviewed', inspected_count=len(results), findings=findings, results=results)


def capability_registrations():
    layer_capability = Capability(CAPABILITY_ID, 'Check proposed layered wardrobe assets without installing/altering avatar art.')
    manifest_capability = Capability(
        MANIFEST_CAPABILITY_ID,
        'Review a versioned scene/wardrobe authoring manifest without rendering, installing or mutating assets.',
    )

    def layer_handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != layer_capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid reviewed capability request')
        return review_avatar_studio(request.parameters['snapshot'], now=datetime.now(timezone.utc))

    def manifest_handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != manifest_capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid reviewed capability request')
        return review_authoring_manifest(request.parameters['snapshot'], now=datetime.now(timezone.utc))

    return ((layer_capability, layer_handler), (manifest_capability, manifest_handler))
