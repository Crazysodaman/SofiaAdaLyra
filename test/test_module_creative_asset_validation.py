"""Bounded, effect-free asset provenance validator for MOD-CREATIVE.

The validator consumes supplied projections only. It never generates, renders,
downloads or persists creative assets.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.creative_studio import capability_registrations as module_registrations
from sofia.modules.creative_studio.assets import (
    CAPABILITY_ID,
    capability_registrations,
    validate_asset_manifest,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
D1 = 'a' * 64
SECRET = 'raw-private-asset-bytes'


def asset(**extra):
    return dict(
        asset_id='asset:1',
        provenance_class='licensed',
        origin_ref='origin:supplier',
        license_state='verified',
        license_id='license:cc0',
        revision_sha256=D1,
        revision_observed_at=(NOW - timedelta(hours=1)).isoformat(),
    ) | extra


def manifest(**extra):
    return dict(
        source_ref='creative:manifest',
        observed_at=NOW.isoformat(),
        assets=[asset()],
    ) | extra


def test_valid_asset_manifest_without_generation():
    result = validate_asset_manifest(manifest(), now=NOW)
    assert result['status'] == 'validated_asset_manifest'
    assert result['findings'] == []
    assert result['inspected_asset_count'] == 1
    assert result['assets'][0]['finding'] == 'asset_review_eligible'
    assert result['assets'][0]['revision_sha256'] == D1
    assert result['effect'] == 'none'
    assert result['action_authorized'] is False
    assert result['data_persisted'] is False
    assert result['asset_generated'] is False
    assert result['asset_rendered'] is False
    assert result['network_requests_sent'] is False
    assert result['license_authenticity_verified'] is False


@pytest.mark.parametrize('value,finding', [
    ({'provenance_class': 'unknown'}, 'asset_provenance_unknown'),
    ({'license_state': 'pending'}, 'license_review_pending'),
    ({'license_state': 'unlicensed'}, 'license_unverified'),
    ({'license_state': 'not_required'}, 'license_review_required'),
])
def test_unverified_provenance_or_license_is_held(value, finding):
    result = validate_asset_manifest(manifest(assets=[asset(**value)]), now=NOW)
    assert result['status'] == 'validated_with_findings'
    assert finding in result['findings']
    assert result['assets'][0]['finding'] == 'asset_hold'
    assert result['asset_generated'] is False


@pytest.mark.parametrize('value', [
    {'provenance_class': 'public_domain', 'license_state': 'not_required'},
    {'provenance_class': 'generated', 'license_state': 'not_required'},
])
def test_public_or_generated_assets_can_skip_license(value):
    result = validate_asset_manifest(manifest(assets=[asset(**value)]), now=NOW)
    assert result['status'] == 'validated_asset_manifest'
    assert result['assets'][0]['finding'] == 'asset_review_eligible'


@pytest.mark.parametrize('delta', [-7200, 3600])
def test_stale_or_future_snapshot_is_unknown(delta):
    result = validate_asset_manifest(
        manifest(observed_at=(NOW + timedelta(seconds=delta)).isoformat()), now=NOW)
    assert result['status'] == 'unknown'
    assert result['inspected_asset_count'] is None
    assert result['assets'] == []
    assert result['findings'] == ['asset_manifest_timestamp_invalid']


@pytest.mark.parametrize('asset_value', [
    {'asset_id': 'bad asset'},
    {'provenance_class': 'rumored'},
    {'origin_ref': 'bad origin'},
    {'license_state': 'trusted'},
    {'license_id': 'bad license'},
    {'revision_sha256': 'xyz'},
    {'revision_sha256': 'A' * 64},
    {'revision_observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'revision_observed_at': (NOW + timedelta(hours=1)).isoformat()},
    {'raw_asset_bytes': SECRET},
])
def test_asset_rejects_malformed_or_oversized(asset_value):
    with pytest.raises(ValueError):
        validate_asset_manifest(manifest(assets=[asset(**asset_value)]), now=NOW)


@pytest.mark.parametrize('snapshot_change', [
    {'assets': []},
    {'assets': 'bad'},
    {'assets': [asset()] * 129},
    {'assets': [asset(), asset()]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'observed_at': 'not-a-date'},
    {'raw_asset_content': SECRET},
])
def test_manifest_rejects_malformed_or_oversized(snapshot_change):
    with pytest.raises(ValueError):
        validate_asset_manifest(manifest(**snapshot_change), now=NOW)


def test_manifest_rejects_extra_snapshot_fields():
    with pytest.raises(ValueError):
        validate_asset_manifest(manifest(generate=True), now=NOW)


def test_result_does_not_echo_private_raw_content():
    result = validate_asset_manifest(manifest(), now=NOW)
    assert SECRET not in json.dumps(result)
    assert result['assets'][0]['revision_sha256'] == D1


def test_asset_manifest_registration_is_inert():
    registrations = capability_registrations()
    assert [cap.name for cap, _ in registrations] == [CAPABILITY_ID]
    capability, handler = next(
        item for item in module_registrations() if item[0].name == CAPABILITY_ID)
    assert isinstance(capability, Capability)
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'snapshot': manifest()}, None, 'forged'))
    live = manifest(observed_at=datetime.now(timezone.utc).isoformat(),
                    assets=[asset(revision_observed_at=(
                        datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())])
    outcome = handler(CapabilityRequest(
        capability, {'snapshot': live}, None, 'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            capability, {'snapshot': live, 'render': True}, None, 'invalid'))
