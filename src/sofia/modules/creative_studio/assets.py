"""Validate supplied asset provenance, license and revision evidence only.

Capability performs bounded analysis of supplied, UNVERIFIED projections only.
No asset generation, rendering, download, persistence or identity assertions.
Existing Sofía V18 owner components retain control of all real operations.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-CREATIVE'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'creative.validate_asset_manifest.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))

_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_DIGEST = re.compile(r'^[0-9a-f]{64}$')
_SNAPSHOT_FIELDS = frozenset({'source_ref', 'observed_at', 'assets'})
_ASSET_FIELDS = frozenset({
    'asset_id', 'provenance_class', 'origin_ref', 'license_state', 'license_id',
    'revision_sha256', 'revision_observed_at',
})
_PROVENANCE = ('original', 'licensed', 'public_domain', 'generated', 'unknown')
_LICENSE_STATES = ('verified', 'pending', 'unlicensed', 'not_required')
_MAX_ASSETS = 128


def _exact(item: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(item, Mapping) or set(item) != keys:
        raise ValueError('unexpected fields in supplied asset manifest')
    return item


def _identity(value: object, label: str = 'id') -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError('invalid ' + label)
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
        raise ValueError('invalid ' + label)
    return value


def _int(value: object, lo: int, hi: int, name: str = 'integer') -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('invalid ' + name)
    return value


def _choice(value: object, options: tuple[str, ...], label: str = 'choice') -> str:
    if type(value) is not str or value not in options:
        raise ValueError('invalid ' + label)
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError('timestamp required')
    try:
        date = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid timestamp') from exc
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError('timestamp requires timezone')
    return date.astimezone(timezone.utc)


def _asset(item: object, *, now: datetime) -> dict[str, object]:
    row = _exact(item, _ASSET_FIELDS)
    key = _identity(row['asset_id'], 'asset_id')
    provenance = _choice(row['provenance_class'], _PROVENANCE, 'provenance_class')
    origin = _identity(row['origin_ref'], 'origin_ref')
    license_state = _choice(row['license_state'], _LICENSE_STATES, 'license_state')
    license_id = _identity(row['license_id'], 'license_id')
    revision = _digest(row['revision_sha256'], 'revision_sha256')
    revision_at = _timestamp(row['revision_observed_at'])
    if revision_at > now.astimezone(timezone.utc):
        raise ValueError('asset revision timestamp is in the future')

    reasons = []
    if provenance == 'unknown':
        reasons.append('asset_provenance_unknown')
    if license_state == 'pending':
        reasons.append('license_review_pending')
    elif license_state == 'unlicensed':
        reasons.append('license_unverified')
    elif license_state == 'not_required' and provenance not in ('public_domain', 'generated'):
        reasons.append('license_review_required')
    if reasons:
        return dict(
            asset_id=key,
            provenance_class=provenance,
            origin_ref=origin,
            license_state=license_state,
            license_id=license_id,
            revision_sha256=revision,
            revision_observed_at=revision_at.isoformat(),
            finding='asset_hold',
            reasons=reasons,
        )
    return dict(
        asset_id=key,
        provenance_class=provenance,
        origin_ref=origin,
        license_state=license_state,
        license_id=license_id,
        revision_sha256=revision,
        revision_observed_at=revision_at.isoformat(),
        finding='asset_review_eligible',
        reasons=[],
    )


def validate_asset_manifest(snapshot: Mapping[str, object], *, now: datetime,
                            max_age_seconds: int = 3600) -> dict[str, object]:
    _exact(snapshot, _SNAPSHOT_FIELDS)
    source = _identity(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    observed = _timestamp(snapshot['observed_at'])
    assets = snapshot['assets']
    if type(assets) is not list or not 1 <= len(assets) <= _MAX_ASSETS:
        raise ValueError('assets must be a bounded non-empty list')
    rows = [_asset(item, now=now) for item in assets]
    ids = [row['asset_id'] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate asset identity')

    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = dict(
        schema='sofia.creative_studio.asset_manifest_validation.v1',
        module_id=MODULE_ID,
        sdk_protocol=str(SDK_PROTOCOL_VERSION),
        source_ref=source,
        observed_at=observed.isoformat(),
        freshness=freshness,
        evidence_class='supplied_unverified',
        effect='none',
        action_authorized=False,
        data_persisted=False,
        asset_generated=False,
        asset_rendered=False,
        network_requests_sent=False,
        license_authenticity_verified=False,
    )
    if freshness != 'fresh':
        return base | dict(
            status='unknown',
            inspected_asset_count=None,
            findings=['asset_manifest_timestamp_invalid'],
            assets=[],
        )
    findings = sorted({reason for row in rows for reason in row['reasons']})
    return base | dict(
        status='validated_asset_manifest' if not findings else 'validated_with_findings',
        inspected_asset_count=len(rows),
        findings=findings,
        assets=rows,
    )


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate supplied asset provenance, license and revision evidence; never generate assets.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid asset manifest capability request')
        return validate_asset_manifest(
            request.parameters['snapshot'], now=datetime.now(timezone.utc))

    return ((capability, handler),)
