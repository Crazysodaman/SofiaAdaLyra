"""Offline reconciliation-only tests for mobile notification receipts.

No device pairing, credential enrollment, network call or notification send is
performed by the validator under test.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.mobile.receipts import (
    CAPABILITY_ID,
    capability_registrations,
    reconcile_mobile_receipts,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def record(**extra):
    return dict(
        id='receipt-1',
        device_ref='device-secret-1',
        notification_ref='notification-secret-1',
        observed_state='delivered',
        receipt_ref='receipt:secret-1',
        last_seen_at=NOW.isoformat(),
    ) | extra


def snapshot(**extra):
    return dict(
        source_ref='mobile:agent-1',
        observed_at=NOW.isoformat(),
        items=[record()],
    ) | extra


def entry(capability_id):
    return next(item for item in capability_registrations()
                if item[0].name == capability_id)


def test_reconciles_sent_delivered_seen_and_unknown_without_pairing():
    result = reconcile_mobile_receipts(snapshot(items=[
        record(id='receipt-1', observed_state='sent', receipt_ref=None),
        record(id='receipt-2', observed_state='delivered', receipt_ref='receipt:1'),
        record(id='receipt-3', observed_state='seen', receipt_ref='receipt:2'),
        record(id='receipt-4', observed_state='unknown', receipt_ref=None),
        record(id='receipt-5', observed_state='delivered', receipt_ref=None),
        record(id='receipt-6', observed_state='seen', receipt_ref=None),
    ]), now=NOW)
    assert result['status'] == 'reconciled'
    assert result['record_count'] == 6
    assert result['classifications'] == {
        'SENT': 1, 'DELIVERED': 1, 'SEEN': 1, 'UNKNOWN': 3,
    }
    assert [row['classification'] for row in result['records']] == [
        'SENT', 'DELIVERED', 'SEEN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN']
    assert set(result['findings']) == {
        'delivery_receipt_missing', 'seen_receipt_missing', 'state_not_reported'}
    assert result['effect'] == 'none'
    assert result['pairing_attempted'] is False
    assert result['network_contacted'] is False
    assert result['delivery_fabricated'] is False
    assert result['data_persisted'] is False
    assert result['stale_device_count'] == 0


def test_missing_receipts_never_fabricate_delivered_or_seen():
    result = reconcile_mobile_receipts(snapshot(items=[
        record(id='receipt-1', observed_state='delivered', receipt_ref=None),
        record(id='receipt-2', observed_state='seen', receipt_ref=None),
    ]), now=NOW)
    assert [row['classification'] for row in result['records']] == [
        'UNKNOWN', 'UNKNOWN']
    assert [row['reasons'] for row in result['records']] == [
        ['delivery_receipt_missing'], ['seen_receipt_missing']]


def test_stale_device_is_detected_without_rewriting_receipt_evidence():
    stale_at = NOW - timedelta(hours=2)
    result = reconcile_mobile_receipts(snapshot(items=[
        record(observed_state='delivered', last_seen_at=stale_at.isoformat()),
        record(id='receipt-2', observed_state='sent', receipt_ref=None,
               last_seen_at=NOW.isoformat()),
    ]), now=NOW)
    assert result['stale_device_count'] == 1
    assert result['records'][0]['stale'] is True
    assert result['records'][0]['classification'] == 'DELIVERED'
    assert 'stale_device' in result['findings']
    assert result['records'][0]['last_seen_age_seconds'] == pytest.approx(7200)


def test_future_device_clock_is_treated_as_stale_and_unverified():
    future_at = NOW + timedelta(minutes=10)
    result = reconcile_mobile_receipts(snapshot(items=[
        record(last_seen_at=future_at.isoformat())]), now=NOW)
    assert result['records'][0]['stale'] is True
    assert 'device_timestamp_future' in result['findings']
    assert result['stale_device_count'] == 1


def test_stale_or_future_snapshot_masks_supplied_records():
    for stamp in (NOW - timedelta(days=2), NOW + timedelta(minutes=10)):
        result = reconcile_mobile_receipts(
            snapshot(observed_at=stamp.isoformat()), now=NOW)
        assert result['status'] == 'unknown'
        assert result['record_count'] is None
        assert result['stale_device_count'] is None
        assert result['records'] == []
        assert result['findings'] == ['snapshot_timestamp_invalid']


def test_duplicate_receipt_identity_is_rejected():
    with pytest.raises(ValueError):
        reconcile_mobile_receipts(snapshot(items=[record(), record()]), now=NOW)


@pytest.mark.parametrize('change', [
    {'id': 'bad\nid'},
    {'device_ref': 'bad\ndevice'},
    {'notification_ref': 'bad\nnotification'},
    {'observed_state': 'read'},
    {'receipt_ref': 'bad\nreceipt'},
    {'last_seen_at': NOW.replace(tzinfo=None).isoformat()},
    {'extra_field': True},
])
def test_malformed_record_is_rejected(change):
    with pytest.raises(ValueError):
        reconcile_mobile_receipts(snapshot(items=[record(**change)]), now=NOW)


@pytest.mark.parametrize('change', [
    {'items': 'not-a-list'},
    {'items': [record(id=f'receipt-{index}') for index in range(129)]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'extra_execute': True},
])
def test_malformed_or_oversized_snapshot_is_rejected(change):
    with pytest.raises(ValueError):
        reconcile_mobile_receipts(snapshot(**change), now=NOW)


@pytest.mark.parametrize('bad_stale', [0, 604801, True, 1.5])
def test_invalid_stale_window_is_rejected(bad_stale):
    with pytest.raises(ValueError):
        reconcile_mobile_receipts(snapshot(), now=NOW,
                                  max_stale_seconds=bad_stale)


def test_redacts_supplied_device_and_notification_references():
    result = reconcile_mobile_receipts(snapshot(items=[
        record(device_ref='device-secret-1',
               notification_ref='notification-secret-1')]), now=NOW)
    encoded = json.dumps(result)
    for private in ('device-secret-1', 'notification-secret-1',
                    'receipt:secret-1'):
        assert private not in encoded
    row = result['records'][0]
    assert row['device_fingerprint'].startswith('sha256:')
    assert row['notification_fingerprint'].startswith('sha256:')
    assert result['raw_references_included'] is False


def test_registration_is_inert_and_rejects_shadow_or_overbroad_requests():
    capability, handler = entry(CAPABILITY_ID)
    assert isinstance(capability, Capability)
    live_now = datetime.now(timezone.utc)
    parameters = {'snapshot': snapshot(
        observed_at=live_now.isoformat(),
        items=[record(last_seen_at=live_now.isoformat())],
    )}
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, parameters, None, 'forged fixture'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability,
                                  parameters | {'pair_now': True},
                                  None, 'overbroad fixture'))
    outcome = handler(CapabilityRequest(capability, parameters, None,
                                        'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['pairing_attempted'] is False
    assert outcome['network_contacted'] is False
    assert outcome['sdk_protocol'] == '1.0'
