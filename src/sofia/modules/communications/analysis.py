"""MOD-COMMUNICATIONS: passive message-delivery receipt reconciliation.

'Queued' or 'sent' never implies delivered, read, or observed by a recipient.
Opaque message IDs only: no message content, provider credentials or addresses.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-COMMUNICATIONS'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'communications.review_delivery_receipts.v1'
PROFILE = 'OBSERVE'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_FIELDS = frozenset({'source_ref','observed_at','messages'})
_MSG_FIELDS = frozenset({'message_id','recipient_ref','status','submitted_at','status_at'})
_STATUS = frozenset({'queued','sent','delivered','failed','bounced','cancelled'})


def _timestamp(value: object, field: str) -> datetime:
    if type(value) is not str:
        raise ValueError('invalid '+field)
    try: t = datetime.fromisoformat(value)
    except ValueError as exc: raise ValueError('invalid '+field) from exc
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError('timezone required for '+field)
    return t.astimezone(timezone.utc)


def review_delivery_receipts(snapshot: Mapping[str, object], *, now: datetime,
                             max_age_seconds: int = 1800) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact receipt snapshot required')
    if not isinstance(now,datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid freshness bound')
    source = snapshot['source_ref']
    if not isinstance(source,str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed = _timestamp(snapshot['observed_at'],'observed_at')
    messages = snapshot['messages']
    if type(messages) is not list or len(messages)>128:
        raise ValueError('messages must be bounded list')
    inspected = []
    seen = set()
    for msg in messages:
        if not isinstance(msg,Mapping) or set(msg)!=_MSG_FIELDS:
            raise ValueError('invalid message receipt')
        mid,rid,status = msg['message_id'],msg['recipient_ref'],msg['status']
        if any(type(x) is not str or not _REF.fullmatch(x) for x in (mid,rid)) or mid in seen:
            raise ValueError('invalid or duplicate opaque reference')
        if type(status) is not str or status not in _STATUS:
            raise ValueError('invalid delivery state')
        seen.add(mid)
        submitted = _timestamp(msg['submitted_at'],'submitted_at')
        updated = _timestamp(msg['status_at'],'status_at')
        if updated < submitted or (updated-observed).total_seconds() > 5:
            raise ValueError('inconsistent receipt timeline')
        inspected.append((mid,status))  # Recipient is never echoed or aggregated.
    age = (now.astimezone(timezone.utc)-observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema':'sofia.communications.delivery_review.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
            'module_id':MODULE_ID,'source_ref':source,'freshness':freshness,
            'evidence_class':'supplied_unverified','effect':'none',
            'messages_sent':False,'recipient_details_returned':False,
            'recipient_read_verified':False,'delivery_authenticated':False}
    if freshness != 'fresh':
        return base | {'status':'unknown','counts':{},'undelivered_message_ids':[],
                       'delivered_message_ids':[]}
    counts = {state:sum(1 for _,status in inspected if status==state) for state in sorted(_STATUS)}
    return base | {'status':'reviewed','counts':counts,
                   'undelivered_message_ids':sorted(mid for mid,status in inspected if status!='delivered'),
                   'delivered_message_ids':sorted(mid for mid,status in inspected if status=='delivered')}


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Review untrusted delivery receipts without sending or reading messages.')
    def handler(request:CapabilityRequest):
        if not isinstance(request,CapabilityRequest) or request.capability != capability or set(request.parameters) != {'snapshot'}:
            raise ValueError('invalid communications capability request')
        return review_delivery_receipts(request.parameters['snapshot'],now=datetime.now(timezone.utc))
    return ((capability,handler),)
