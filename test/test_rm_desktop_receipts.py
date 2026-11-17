"""Offline reconciliation-only tests for desktop presentation receipts.

No screen capture, window inspection, notification send or process access is
performed by the validator under test.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.desktop_automation.receipts import (
    CAPABILITY_ID,
    capability_registrations,
    reconcile_desktop_receipts,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def record(**extra):
    return dict(
        id='receipt-1',
        kind='notification',
        observed_state='delivered',
        receipt_ref='receipt:secret-1',
        subject_ref='person:alice-secret',
    ) | extra


def snapshot(**extra):
    return dict(
        source_ref='desktop:agent-1',
        observed_at=NOW.isoformat(),
        items=[record()],
    ) | extra


def entry(capability_id):
    return next(item for item in capability_registrations()
                if item[0].name == capability_id)


def test_reconciles_sent_delivered_and_unknown_without_effects():
    result = reconcile_desktop_receipts(snapshot(items=[
        record(id='receipt-1', observed_state='delivered', receipt_ref='receipt:1'),
        record(id='receipt-2', observed_state='sent', receipt_ref=None),
        record(id='receipt-3', observed_state='unknown', receipt_ref=None),
        record(id='receipt-4', observed_state='delivered', receipt_ref=None),
    ]), now=NOW)
    assert result['status'] == 'reconciled'
    assert result['record_count'] == 4
    assert result['classifications'] == {
        'SENT': 1, 'DELIVERED': 1, 'UNKNOWN': 2,
    }
    assert [row['classification'] for row in result['records']] == [
        'DELIVERED', 'SENT', 'UNKNOWN', 'UNKNOWN']
    assert 'delivery_receipt_missing' in result['findings']
    assert result['effect'] == 'none'
    assert result['screen_accessed'] is False
    assert result['process_inspected'] is False
    assert result['delivery_fabricated'] is False
    assert result['data_persisted'] is False


def test_missing_delivery_receipt_is_never_promoted_to_delivered():
    result = reconcile_desktop_receipts(snapshot(items=[
        record(observed_state='delivered', receipt_ref=None)]), now=NOW)
    assert result['records'][0]['classification'] == 'UNKNOWN'
    assert result['records'][0]['receipt_present'] is False
    assert result['records'][0]['reasons'] == ['delivery_receipt_missing']


def test_stale_or_future_snapshot_masks_supplied_records():
    for stamp in (NOW - timedelta(days=2), NOW + timedelta(minutes=10)):
        result = reconcile_desktop_receipts(
            snapshot(observed_at=stamp.isoformat()), now=NOW)
        assert result['status'] == 'unknown'
        assert result['record_count'] is None
        assert result['records'] == []
        assert result['findings'] == ['snapshot_timestamp_invalid']


def test_duplicate_receipt_identity_is_rejected():
    with pytest.raises(ValueError):
        reconcile_desktop_receipts(snapshot(items=[record(), record()]), now=NOW)


@pytest.mark.parametrize('change', [
    {'id': 'bad\nid'},
    {'kind': 'window'},
    {'observed_state': 'displayed'},
    {'receipt_ref': 'bad\nref'},
    {'subject_ref': 'bad\nsubject'},
    {'extra_field': True},
])
def test_malformed_record_is_rejected(change):
    with pytest.raises(ValueError):
        reconcile_desktop_receipts(snapshot(items=[record(**change)]), now=NOW)


@pytest.mark.parametrize('change', [
    {'items': 'not-a-list'},
    {'items': [record(id=f'receipt-{index}') for index in range(129)]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'extra_execute': True},
])
def test_malformed_or_oversized_snapshot_is_rejected(change):
    with pytest.raises(ValueError):
        reconcile_desktop_receipts(snapshot(**change), now=NOW)


def test_redacts_supplied_private_references():
    result = reconcile_desktop_receipts(snapshot(items=[
        record(subject_ref='person:alice-secret',
               receipt_ref='receipt:secret-1')]), now=NOW)
    encoded = json.dumps(result)
    assert 'alice-secret' not in encoded
    assert 'receipt:secret-1' not in encoded
    assert result['records'][0]['subject_redacted'].startswith('sha256:')
    assert result['raw_references_included'] is False


def test_registration_is_inert_and_rejects_shadow_or_overbroad_requests():
    capability, handler = entry(CAPABILITY_ID)
    assert isinstance(capability, Capability)
    live_now = datetime.now(timezone.utc)
    parameters = {'snapshot': snapshot(observed_at=live_now.isoformat())}
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, parameters, None, 'forged fixture'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability,
                                  parameters | {'execute': True},
                                  None, 'overbroad fixture'))
    outcome = handler(CapabilityRequest(capability, parameters, None,
                                        'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['delivery_fabricated'] is False
    assert outcome['sdk_protocol'] == '1.0'
