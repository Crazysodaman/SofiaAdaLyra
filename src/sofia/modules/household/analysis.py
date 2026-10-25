"""MOD-HOUSEHOLD: inert review of supplied stock projections, no shopping or mutation.

Only opaque item IDs are accepted; item names, household accounts and addresses never
need to cross the module boundary. Source authenticity belongs to the Platform.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import math
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-HOUSEHOLD'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'household.review_inventory.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref', 'observed_at', 'items'})
_ITEM_FIELDS = frozenset({'item_id', 'quantity', 'minimum_quantity', 'expires_on'})


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError('observed_at must be ISO timestamp')
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid observed_at') from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('observed_at requires timezone')
    return result.astimezone(timezone.utc)


def _quantity(value: object, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1e6:
        raise ValueError('invalid ' + name)
    return float(value)


def review_inventory(snapshot: Mapping[str, object], *, now: datetime,
                     max_age_seconds: int = 3600) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact inventory projection required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid freshness bound')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed = _timestamp(snapshot['observed_at'])
    raw_items = snapshot['items']
    if type(raw_items) is not list or len(raw_items) > 128:
        raise ValueError('items must be list with <=128 entries')
    reviewed = []
    seen = set()
    for item in raw_items:
        if not isinstance(item, Mapping) or set(item) != _ITEM_FIELDS:
            raise ValueError('invalid inventory item')
        key = item['item_id']
        if not isinstance(key, str) or not _REF.fullmatch(key) or key in seen:
            raise ValueError('duplicate or invalid item_id')
        seen.add(key)
        quantity = _quantity(item['quantity'], 'quantity')
        minimum = _quantity(item['minimum_quantity'], 'minimum_quantity')
        expiry = item['expires_on']
        if expiry is not None:
            if not isinstance(expiry, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', expiry):
                raise ValueError('expires_on must be ISO date')
            try:
                expiry = date.fromisoformat(expiry)
            except ValueError as exc:
                raise ValueError('invalid expires_on') from exc
        reviewed.append((key, quantity, minimum, expiry))
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema': 'sofia.household.inventory_review.v1', 'sdk_protocol': str(SDK_PROTOCOL_VERSION),
            'module_id': MODULE_ID, 'source_ref': source, 'freshness': freshness,
            'evidence_class': 'supplied_unverified', 'effect': 'none',
            'shopping_authorized': False, 'inventory_modified': False}
    if freshness != 'fresh':
        return base | {'status': 'unknown', 'low_stock': [], 'expiring_within_7_days': [],
                       'expired': [], 'observed_item_count': None}
    today = now.astimezone(timezone.utc).date()
    low = sorted(key for key, qty, minimum, _ in reviewed if qty < minimum)
    expired = sorted(key for key, _, _, expiry in reviewed if expiry is not None and expiry < today)
    soon = sorted(key for key, _, _, expiry in reviewed
                  if expiry is not None and today <= expiry <= date.fromordinal(today.toordinal() + 7))
    return base | {'status': 'reviewed', 'low_stock': low, 'expiring_within_7_days': soon,
                   'expired': expired, 'observed_item_count': len(reviewed)}


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Read-only analysis of supplied opaque household inventory.')
    def handler(request: CapabilityRequest):
        if not isinstance(request, CapabilityRequest) or request.capability != capability or set(request.parameters) != {'snapshot'}:
            raise ValueError('invalid household capability request')
        return review_inventory(request.parameters['snapshot'], now=datetime.now(timezone.utc))
    return ((capability, handler),)
