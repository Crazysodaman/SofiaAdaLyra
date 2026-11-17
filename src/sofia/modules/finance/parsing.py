"""MOD-FINANCE: bounded CSV transaction analysis from supplied bytes/text.

No account provider, network, transfer, persistence or raw-row output is used.
Account identifiers are validated only so malformed input is rejected; they are
never returned or included in error messages.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timezone
import io
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .analysis import (
    MODULE_ID,
    MODULE_VERSION,
    PROFILE,
    RESOURCES,
    _CATEGORY,
    _REF,
    _cents,
    _timestamp,
)

CAPABILITY_ID = 'finance.analyze_transaction_csv.v1'
MAX_CSV_BYTES = 64 * 1024
MAX_TRANSACTION_ROWS = 1000
MAX_BUDGET_CATEGORIES = 64
_FIELDS = frozenset({'source_ref', 'observed_at', 'currency', 'budgets', 'content'})
_HEADER = ('date', 'account_id', 'category', 'amount_cents')
_DATE = re.compile(r'\d{4}-\d{2}-\d{2}')
_AMOUNT = re.compile(r'-?(?:0|[1-9]\d{0,13})')
_CURRENCY = re.compile(r'[A-Z]{3}')


def _bounded_text(content: object) -> tuple[str, int]:
    if isinstance(content, str):
        try:
            encoded = content.encode('utf-8')
        except UnicodeEncodeError as exc:
            raise ValueError('transaction CSV must be valid UTF-8 text') from exc
        if len(encoded) > MAX_CSV_BYTES:
            raise ValueError('transaction CSV exceeds size limit')
        text = content
    elif isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
        if len(raw) > MAX_CSV_BYTES:
            raise ValueError('transaction CSV exceeds size limit')
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError('transaction CSV must be valid UTF-8 text') from exc
        encoded = raw
    else:
        raise ValueError('transaction CSV must be bytes or text')
    if '\0' in text or any(ord(ch) < 32 and ch not in '\n\r\t' for ch in text):
        raise ValueError('transaction CSV contains unsupported control characters')
    return text, len(encoded)


def _transaction_date(value: str) -> date:
    if not _DATE.fullmatch(value):
        raise ValueError('invalid transaction date')
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid transaction date') from exc


def _transaction_cents(value: str) -> int:
    if not _AMOUNT.fullmatch(value):
        raise ValueError('invalid transaction amount_cents')
    amount = int(value)
    if not -10**13 <= amount <= 10**13:
        raise ValueError('transaction amount_cents out of bounds')
    return amount


def _parse_csv(text: str) -> list[tuple[date, str, int]]:
    try:
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        header = next(reader, None)
        if header is None or tuple(header) != _HEADER:
            raise ValueError('transaction CSV schema mismatch')
        rows: list[tuple[date, str, int]] = []
        seen: set[tuple[str, str, str, int]] = set()
        for raw in reader:
            if len(rows) >= MAX_TRANSACTION_ROWS:
                raise ValueError('transaction row limit exceeded')
            if len(raw) != len(_HEADER):
                raise ValueError('transaction CSV row width mismatch')
            occurred = _transaction_date(raw[0])
            account = raw[1]
            if not _REF.fullmatch(account):
                raise ValueError('invalid opaque account identifier')
            category = raw[2]
            if not _CATEGORY.fullmatch(category):
                raise ValueError('invalid transaction category')
            amount = _transaction_cents(raw[3])
            key = (raw[0], account, category, amount)
            if key in seen:
                raise ValueError('duplicate transaction row')
            seen.add(key)
            rows.append((occurred, category, amount))
        return rows
    except csv.Error as exc:
        raise ValueError('malformed transaction CSV') from exc


def _budgets(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping) or len(value) > MAX_BUDGET_CATEGORIES:
        raise ValueError('budgets must be a bounded mapping')
    reviewed: dict[str, int] = {}
    for category, amount in value.items():
        if not isinstance(category, str) or not _CATEGORY.fullmatch(category):
            raise ValueError('invalid budget category')
        if category in reviewed:
            raise ValueError('duplicate budget category')
        reviewed[category] = _cents(amount, 'budget_cents')
    return reviewed


def analyze_transaction_csv(snapshot: Mapping[str, object], *, now: datetime,
                            max_age_seconds: int = 604800) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact transaction CSV snapshot fields required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 2592000:
        raise ValueError('invalid maximum age')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed = _timestamp(snapshot['observed_at'])
    currency = snapshot['currency']
    if not isinstance(currency, str) or not _CURRENCY.fullmatch(currency):
        raise ValueError('ISO currency code required')
    budgets = _budgets(snapshot['budgets'])
    text, content_bytes = _bounded_text(snapshot['content'])
    rows = _parse_csv(text)
    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = {
        'schema': 'sofia.finance.transaction_csv_review.v1',
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'module_id': MODULE_ID,
        'source_ref': source,
        'source_format': 'csv',
        'currency': currency,
        'freshness': freshness,
        'content_bytes': content_bytes,
        'evidence_class': 'supplied_unverified',
        'effect': 'none',
        'accounts_accessed': False,
        'account_ids_returned': False,
        'account_ids_redacted': True,
        'transactions_executed': False,
        'network_used': False,
        'raw_rows_returned': False,
        'financial_advice': False,
        'stored': False,
    }
    if freshness != 'fresh':
        return base | {
            'status': 'unknown',
            'row_count': None,
            'total_cents': None,
            'totals_by_month': [],
            'totals_by_category': [],
            'budget_variance': [],
        }
    months: dict[str, tuple[int, int]] = {}
    categories: dict[str, tuple[int, int]] = {}
    for occurred, category, amount in rows:
        month = occurred.strftime('%Y-%m')
        month_total, month_count = months.get(month, (0, 0))
        months[month] = (month_total + amount, month_count + 1)
        category_total, category_count = categories.get(category, (0, 0))
        categories[category] = (category_total + amount, category_count + 1)
    variance = []
    for category in sorted(budgets):
        spent = categories.get(category, (0, 0))[0]
        budget = budgets[category]
        variance.append({
            'category_id': category,
            'budget_cents': budget,
            'spent_cents': spent,
            'variance_cents': budget - spent,
            'over_budget': spent > budget,
        })
    return base | {
        'status': 'reviewed',
        'row_count': len(rows),
        'total_cents': sum(amount for _, _, amount in rows),
        'totals_by_month': [
            {
                'month': month,
                'total_cents': months[month][0],
                'transaction_count': months[month][1],
            }
            for month in sorted(months)
        ],
        'totals_by_category': [
            {
                'category_id': category,
                'total_cents': categories[category][0],
                'transaction_count': categories[category][1],
            }
            for category in sorted(categories)
        ],
        'budget_variance': variance,
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Analyze supplied bounded CSV transactions into category/month totals and '
        'budget variance; no account access, transfers or account-ID output.',
    )

    def handler(request: CapabilityRequest):
        if (
            not isinstance(request, CapabilityRequest)
            or request.capability != capability
            or set(request.parameters) != {'snapshot'}
        ):
            raise ValueError('invalid finance CSV capability request')
        return analyze_transaction_csv(
            request.parameters['snapshot'], now=datetime.now(timezone.utc)
        )

    return ((capability, handler),)
