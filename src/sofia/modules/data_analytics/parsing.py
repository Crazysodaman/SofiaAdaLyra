"""MOD-DATA-ANALYTICS: bounded CSV numeric statistics from supplied bytes/text.

No filesystem, network, SQL, evaluation, chart rendering or raw-row echo occurs.
Supplied data has unverified provenance and remains subject to Platform admission.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import math
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .analysis import (
    MODULE_ID,
    MODULE_VERSION,
    PROFILE,
    RESOURCES,
    _COLUMN,
    _REF,
    summarize_numeric,
)

CAPABILITY_ID = 'data_analytics.summarize_numeric_csv.v1'
MAX_CSV_BYTES = 64 * 1024
MAX_CSV_ROWS = 512
MAX_CSV_COLUMNS = 8
_FIELDS = frozenset({'source_ref', 'observed_at', 'content'})
_NUMERIC = re.compile(r'-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?')


def _bounded_text(content: object) -> tuple[str, int]:
    if isinstance(content, str):
        try:
            encoded = content.encode('utf-8')
        except UnicodeEncodeError as exc:
            raise ValueError('numeric CSV must be valid UTF-8 text') from exc
        if len(encoded) > MAX_CSV_BYTES:
            raise ValueError('numeric CSV exceeds size limit')
        text = content
    elif isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
        if len(raw) > MAX_CSV_BYTES:
            raise ValueError('numeric CSV exceeds size limit')
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError('numeric CSV must be valid UTF-8 text') from exc
        encoded = raw
    else:
        raise ValueError('numeric CSV must be bytes or text')
    if '\0' in text or any(ord(ch) < 32 and ch not in '\n\r\t' for ch in text):
        raise ValueError('numeric CSV contains unsupported control characters')
    return text, len(encoded)


def _parse_csv(text: str) -> tuple[list[str], list[dict[str, object]]]:
    try:
        reader = csv.reader(io.StringIO(text, newline=''), strict=True)
        header = next(reader, None)
        if header is None or not 1 <= len(header) <= MAX_CSV_COLUMNS:
            raise ValueError('numeric CSV column count invalid')
        if any(
            not isinstance(column, str) or not _COLUMN.fullmatch(column)
            for column in header
        ) or len(set(header)) != len(header):
            raise ValueError('invalid or duplicate numeric CSV column')
        columns = list(header)
        rows: list[dict[str, object]] = []
        for raw in reader:
            if len(rows) >= MAX_CSV_ROWS:
                raise ValueError('numeric CSV row limit exceeded')
            if len(raw) != len(columns):
                raise ValueError('numeric CSV row width mismatch')
            row: dict[str, object] = {}
            for column, value in zip(columns, raw):
                if value == '':
                    row[column] = None
                elif not _NUMERIC.fullmatch(value):
                    raise ValueError('invalid numeric CSV value')
                else:
                    parsed = float(value)
                    if not math.isfinite(parsed) or abs(parsed) > 1e12:
                        raise ValueError('invalid numeric CSV value bounds')
                    row[column] = parsed
            rows.append(row)
        if not rows:
            raise ValueError('numeric CSV must contain at least one row')
        return columns, rows
    except csv.Error as exc:
        raise ValueError('malformed numeric CSV') from exc


def summarize_numeric_csv(snapshot: Mapping[str, object], *, now: datetime,
                          max_age_seconds: int = 86400) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact numeric CSV snapshot fields required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 604800:
        raise ValueError('invalid freshness bound')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed = snapshot['observed_at']
    if not isinstance(observed, str):
        raise ValueError('invalid observed_at')
    text, content_bytes = _bounded_text(snapshot['content'])
    columns, rows = _parse_csv(text)
    reviewed = summarize_numeric(
        {
            'source_ref': source,
            'observed_at': observed,
            'columns': columns,
            'rows': rows,
        },
        now=now,
        max_age_seconds=max_age_seconds,
    )
    return reviewed | {
        'schema': 'sofia.data_analytics.numeric_csv_summary.v1',
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_format': 'csv',
        'content_bytes': content_bytes,
        'raw_rows_returned': False,
        'data_persisted': False,
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Summarize supplied bounded numeric CSV rows without file access, raw-row '
        'echo, persistence or arbitrary evaluation.',
    )

    def handler(request: CapabilityRequest):
        if (
            not isinstance(request, CapabilityRequest)
            or request.capability != capability
            or set(request.parameters) != {'snapshot'}
        ):
            raise ValueError('invalid data analytics CSV capability request')
        return summarize_numeric_csv(
            request.parameters['snapshot'], now=datetime.now(timezone.utc)
        )

    return ((capability, handler),)
