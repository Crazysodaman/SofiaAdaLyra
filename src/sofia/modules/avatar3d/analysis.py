"""Review virtual avatar rig constraints; 2D renderer and identity unaffected.

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

MODULE_ID = 'MOD-AVATAR3D'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'avatar3d.review_joint_pose.v1'
RIG_COMPATIBILITY_CAPABILITY_ID = 'avatar3d.review_rig_scene_compatibility.v1'
PROFILE = 'SIMULATE'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))  # provisional admission request
_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_DIGEST = re.compile(r'^[0-9a-f]{64}$')
_TRAVERSAL = re.compile(r'(?:^|[:/])\.\.?(?:[:/]|$)')
_PRIVATE_SEGMENTS = frozenset({'home', 'users', 'root', 'private', 'secrets', 'etc', 'tmp', 'var', 'opt', 'srv', 'mnt', 'data'})


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


def review_rig_scene_compatibility(snapshot: Mapping[str, object], *, now: datetime,
                                   max_age_seconds: int = 3600) -> dict[str, object]:
    rig, observed, freshness = _envelope(snapshot, 'rig', now, max_age_seconds)
    _exact(rig, ('model_id', 'rig_id', 'model_sha256', 'bones', 'morphs', 'wardrobes'))
    model_id = _safe_ref(rig['model_id'], 'model_id')
    rig_id = _safe_ref(rig['rig_id'], 'rig_id')
    model_sha256 = _digest(rig['model_sha256'], 'model digest')
    bones_raw, morphs_raw, wardrobes_raw = rig['bones'], rig['morphs'], rig['wardrobes']
    if type(bones_raw) is not list or len(bones_raw) > 128:
        raise ValueError('bones must be a bounded list')
    if type(morphs_raw) is not list or len(morphs_raw) > 256:
        raise ValueError('morphs must be a bounded list')
    if type(wardrobes_raw) is not list or len(wardrobes_raw) > 128:
        raise ValueError('wardrobes must be a bounded list')

    bones: dict[str, dict[str, object]] = {}
    for item in bones_raw:
        row = _exact(item, ('id', 'parent_id', 'wardrobe_refs'))
        key = _safe_ref(row['id'], 'bone id')
        if key in bones:
            raise ValueError('duplicate bone identity')
        parent = row['parent_id']
        if parent is not None:
            parent = _safe_ref(parent, 'parent bone reference')
        bones[key] = {'parent': parent, 'wardrobe_refs': _refs(row['wardrobe_refs'], 'wardrobe reference')}

    morphs: dict[str, str] = {}
    for item in morphs_raw:
        row = _exact(item, ('id', 'bone_id'))
        key = _safe_ref(row['id'], 'morph id')
        if key in morphs:
            raise ValueError('duplicate morph identity')
        morphs[key] = _safe_ref(row['bone_id'], 'morph bone reference')

    wardrobes: dict[str, dict[str, tuple[str, ...]]] = {}
    for item in wardrobes_raw:
        row = _exact(item, ('id', 'required_bone_ids', 'required_morph_ids'))
        key = _safe_ref(row['id'], 'wardrobe id')
        if key in wardrobes:
            raise ValueError('duplicate wardrobe identity')
        wardrobes[key] = {
            'bones': _refs(row['required_bone_ids'], 'required bone reference'),
            'morphs': _refs(row['required_morph_ids'], 'required morph reference'),
        }

    findings: set[str] = set()
    if not bones:
        findings.add('empty_rig')
    for key, bone in bones.items():
        parent = bone['parent']
        if parent is not None and parent not in bones:
            findings.add('missing_parent_bone')
        seen: set[str] = set()
        current: object = key
        while isinstance(current, str) and current in bones:
            if current in seen:
                findings.add('bone_cycle')
                break
            seen.add(current)
            current = bones[current]['parent']
        for wardrobe_ref in bone['wardrobe_refs']:
            if wardrobe_ref not in wardrobes:
                findings.add('missing_wardrobe_reference')
    for bone_ref in morphs.values():
        if bone_ref not in bones:
            findings.add('missing_morph_bone')
    for wardrobe in wardrobes.values():
        for bone_ref in wardrobe['bones']:
            if bone_ref not in bones:
                findings.add('missing_wardrobe_bone')
        for morph_ref in wardrobe['morphs']:
            if morph_ref not in morphs:
                findings.add('missing_wardrobe_morph')

    ordered = sorted(findings)
    base = dict(schema='sofia.avatar3d.rig_scene_compatibility.v1', module_id=MODULE_ID,
                sdk_protocol=str(SDK_PROTOCOL_VERSION), source_ref=snapshot['source_ref'],
                observed_at=observed.isoformat(), freshness=freshness,
                evidence_class='supplied_unverified', effect='none', action_authorized=False,
                data_persisted=False, render_claimed=False, rig_modified=False)
    if freshness != 'fresh':
        return base | dict(status='unknown', compatible=None, inspected_count=None,
                           findings=['snapshot_timestamp_invalid'], rig=None)
    summary = dict(model_id=model_id, rig_id=rig_id, model_sha256=model_sha256,
                   bone_count=len(bones), morph_count=len(morphs), wardrobe_count=len(wardrobes))
    return base | dict(status='compatible' if not ordered else 'incompatible',
                       compatible=not ordered, inspected_count=len(bones)+len(morphs)+len(wardrobes),
                       findings=ordered, rig=summary)


def _review(item: Mapping[str, object]) -> dict[str, object]:
    row=_exact(item,('id','joint','angle_deg','minimum_deg','maximum_deg','rig_digest'))
    key=_identity(row['id']); joint=_choice(row['joint'],('head','neck','spine','shoulder_l','shoulder_r','elbow_l','elbow_r','hip_l','hip_r','knee_l','knee_r','tail_root'))
    angle=_num(row['angle_deg'],-360,360); low=_num(row['minimum_deg'],-360,360); high=_num(row['maximum_deg'],-360,360)
    if low>=high: raise ValueError('invalid joint limits')
    digest=row['rig_digest']
    if type(digest) is not str or re.fullmatch(r'[0-9a-f]{64}',digest) is None: raise ValueError('invalid rig digest')
    return dict(id=key,joint=joint,finding='in_limit' if low<=angle<=high else 'limit_exceeded', pose_rendered=False)



def review_avatar3d(snapshot: Mapping[str, object], *, now: datetime,
              max_age_seconds: int = 3600) -> dict[str, object]:
    items, observed, freshness = _base(snapshot, now, max_age_seconds)
    results = [_review(item) for item in items]
    ids = [r['id'] for r in results]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate item identity')
    used=set()
    for record in results:
        if record['joint'] in used:
            record['finding']='duplicate_joint_pose'
        used.add(record['joint'])
    findings = sorted({r['finding'] for r in results})
    base = dict(schema='sofia.avatar3d.projection_review.v1', module_id=MODULE_ID, sdk_protocol=str(SDK_PROTOCOL_VERSION),
                source_ref=snapshot['source_ref'], observed_at=observed.isoformat(),
                freshness=freshness, evidence_class='supplied_unverified', effect='none',
                action_authorized=False, data_persisted=False)
    if freshness != 'fresh':
        return base | dict(status='unknown', inspected_count=None, findings=['snapshot_timestamp_invalid'], results=[])
    return base | dict(status='reviewed', inspected_count=len(results), findings=findings, results=results)


def capability_registrations():
    pose_capability = Capability(CAPABILITY_ID, 'Review virtual avatar rig constraints; 2D renderer and identity unaffected.')
    rig_capability = Capability(
        RIG_COMPATIBILITY_CAPABILITY_ID,
        'Check supplied 3D rig, bone, morph and wardrobe references without rendering or modifying assets.',
    )

    def pose_handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != pose_capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid reviewed capability request')
        return review_avatar3d(request.parameters['snapshot'], now=datetime.now(timezone.utc))

    def rig_handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest) or request.capability != rig_capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid reviewed capability request')
        return review_rig_scene_compatibility(request.parameters['snapshot'], now=datetime.now(timezone.utc))

    return ((pose_capability, pose_handler), (rig_capability, rig_handler))
