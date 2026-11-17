"""Reconcile supplied mobile delivery/notification receipts, offline.

Capability performs bounded analysis of supplied, UNVERIFIED receipt records
only. It never pairs a device, contacts a phone, retries delivery or persists
data. Existing Sofía mobile owners retain control of all live operations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'RM-MOBILE'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'mobile.reconcile_notification_receipts.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))
_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_RECORD_FIELDS = frozenset(
    {'id', 'device_ref', 'notification_ref', 'observed_state', 'receipt_ref',
     'last_seen_at'}
)
_MAX_RECORDS = 128
_CLASSIFICATIONS = ('SENT', 'DELIVERED', 'SEEN', 'UNKNOWN')


def _identity(value: object, label: str = 'id') -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError('invalid ' + label)
    return value


def _exact(item: object, keys: tuple[str, ...] | frozenset[str]) -> Mapping[str, object]:
    if not isinstance(item, Mapping) or set(item) != set(keys):
        raise ValueError('unexpected fields in supplied receipt record')
    return item


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


def _redacted(value: str | None) -> str | None:
    if value is None:
        return None
    return 'sha256:' + sha256(value.encode('utf-8')).hexdigest()[:16]


def _base(snapshot: Mapping[str, object], now: datetime, max_age_seconds: int):
    _exact(snapshot, ('source_ref', 'observed_at', 'items'))
    _identity(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    observed = _timestamp(snapshot['observed_at'])
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    items = snapshot['items']
    if type(items) is not list or len(items) > _MAX_RECORDS:
        raise ValueError('items must be a bounded list')
    return items, observed, freshness


def _record(item: Mapping[str, object], now: datetime,
            max_stale_seconds: int) -> dict[str, object]:
    row = _exact(item, tuple(_RECORD_FIELDS))
    key = _identity(row['id'])
    device_ref = _identity(row['device_ref'], 'device_ref')
    notification_ref = _identity(row['notification_ref'], 'notification_ref')
    state = _choice(row['observed_state'], ('sent', 'delivered', 'seen', 'unknown'),
                    'observed_state')
    receipt_ref = row['receipt_ref']
    if receipt_ref is not None:
        _identity(receipt_ref, 'receipt_ref')
    last_seen = _timestamp(row['last_seen_at'])
    age = (now.astimezone(timezone.utc) - last_seen).total_seconds()
    reasons: list[str] = []
    stale = False
    if age < -5:
        stale = True
        reasons.append('device_timestamp_future')
    elif age > max_stale_seconds:
        stale = True
        reasons.append('stale_device')
    if state == 'seen':
        classification = 'SEEN'
        if receipt_ref is None:
            classification = 'UNKNOWN'
            reasons.append('seen_receipt_missing')
    elif state == 'delivered':
        classification = 'DELIVERED'
        if receipt_ref is None:
            classification = 'UNKNOWN'
            reasons.append('delivery_receipt_missing')
    elif state == 'sent':
        classification = 'SENT'
    else:
        classification = 'UNKNOWN'
        reasons.append('state_not_reported')
    return dict(
        id=key, classification=classification,
        device_fingerprint=_redacted(device_ref),
        notification_fingerprint=_redacted(notification_ref),
        receipt_present=receipt_ref is not None, stale=stale,
        last_seen_age_seconds=age, reasons=sorted(reasons),
    )


def reconcile_mobile_receipts(snapshot: Mapping[str, object], *, now: datetime,
                              max_age_seconds: int = 3600,
                              max_stale_seconds: int = 3600) -> dict[str, object]:
    items, observed, freshness = _base(snapshot, now, max_age_seconds)
    _int(max_stale_seconds, 1, 604800, 'max_stale_seconds')
    records = [_record(item, now, max_stale_seconds) for item in items]
    ids = [record['id'] for record in records]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate receipt identity')
    findings = sorted({reason for record in records for reason in record['reasons']})
    counts = {name: sum(record['classification'] == name for record in records)
              for name in _CLASSIFICATIONS}
    base = dict(
        schema='sofia.mobile.notification_receipt_reconciliation.v1',
        module_id=MODULE_ID, sdk_protocol=str(SDK_PROTOCOL_VERSION),
        source_ref=snapshot['source_ref'], observed_at=observed.isoformat(),
        freshness=freshness, evidence_class='supplied_unverified', effect='none',
        action_authorized=False, data_persisted=False, pairing_attempted=False,
        network_contacted=False, delivery_fabricated=False,
        raw_references_included=False,
    )
    if freshness != 'fresh':
        return base | dict(status='unknown', record_count=None, classifications={},
                           stale_device_count=None,
                           findings=['snapshot_timestamp_invalid'], records=[])
    return base | dict(status='reconciled', record_count=len(records),
                       classifications=counts,
                       stale_device_count=sum(record['stale'] for record in records),
                       findings=findings, records=records)


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Reconcile supplied mobile notification receipts and detect stale '
        'devices without pairing or network access.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid reviewed capability request')
        return reconcile_mobile_receipts(
            request.parameters['snapshot'], now=datetime.now(timezone.utc)
        )

    return ((capability, handler),)
