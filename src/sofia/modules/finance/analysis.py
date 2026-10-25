"""MOD-FINANCE: bounded private budget review. No account access or transactions.

Inputs are caller-supplied monthly aggregate *integer cents*. External source trust,
permission, retention and finance privacy admission are Platform responsibilities.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-FINANCE'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'finance.review_budget_aggregates.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 50), ('ram_mib', 32), ('gpu_mib', 0))
_REF = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_CATEGORY = re.compile(r'^[a-z][a-z0-9_]{0,39}$')
_FIELDS = frozenset({'source_ref','observed_at','currency','period','income_cents','categories'})
_CAT_FIELDS = frozenset({'category_id','spent_cents','budget_cents'})


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError('observed_at must be text')
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid observed_at') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('observed_at requires timezone')
    return parsed.astimezone(timezone.utc)


def _cents(value: object, field: str) -> int:
    if type(value) is not int or not 0 <= value <= 10**13:
        raise ValueError('invalid ' + field)
    return value


def review_budget_aggregates(snapshot: Mapping[str, object], *, now: datetime,
                             max_age_seconds: int = 604800) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact budget aggregate schema required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 2592000:
        raise ValueError('invalid maximum age')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed = _timestamp(snapshot['observed_at'])
    currency = snapshot['currency']
    if type(currency) is not str or not re.fullmatch(r'[A-Z]{3}', currency):
        raise ValueError('ISO currency code required')
    period = snapshot['period']
    if type(period) is not str or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', period):
        raise ValueError('period must be YYYY-MM')
    income = _cents(snapshot['income_cents'], 'income_cents')
    cats = snapshot['categories']
    if type(cats) is not list or len(cats) > 64:
        raise ValueError('categories must be bounded list')
    reviewed = []
    seen = set()
    for item in cats:
        if not isinstance(item, Mapping) or set(item) != _CAT_FIELDS:
            raise ValueError('invalid category entry')
        cat = item['category_id']
        if type(cat) is not str or not _CATEGORY.fullmatch(cat) or cat in seen:
            raise ValueError('invalid or duplicate category_id')
        seen.add(cat)
        reviewed.append((cat, _cents(item['spent_cents'], 'spent_cents'),
                         _cents(item['budget_cents'], 'budget_cents')))
    age = (now.astimezone(timezone.utc)-observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {'schema':'sofia.finance.budget_review.v1','sdk_protocol':str(SDK_PROTOCOL_VERSION),
            'module_id':MODULE_ID,'source_ref':source,'period':period,'currency':currency,
            'freshness':freshness,'evidence_class':'supplied_unverified','effect':'none',
            'accounts_accessed':False,'transactions_executed':False,'financial_advice':False,
            'stored':False}
    if freshness != 'fresh':
        return base | {'status':'unknown','total_spent_cents':None,
                       'net_cashflow_cents':None,'categories_over_budget':[],
                       'total_budget_cents':None,'categories_assessed':None}
    spent = sum(x[1] for x in reviewed)
    return base | {'status':'reviewed', 'income_cents':income,
                   'total_spent_cents':spent, 'net_cashflow_cents':income-spent,
                   'total_budget_cents':sum(x[2] for x in reviewed),
                   'categories_over_budget':[
                       {'category_id':cat,'over_by_cents':s-b}
                       for cat,s,b in sorted(reviewed) if s>b],
                   'categories_assessed':len(reviewed)}


def capability_registrations():
    capability = Capability(CAPABILITY_ID, 'Review approved monthly category totals without reading accounts or making payments.')
    def handler(request: CapabilityRequest):
        if not isinstance(request, CapabilityRequest) or request.capability != capability or set(request.parameters) != {'snapshot'}:
            raise ValueError('invalid finance capability request')
        return review_budget_aggregates(request.parameters['snapshot'], now=datetime.now(timezone.utc))
    return ((capability, handler),)
