"""MOD-CALENDAR: bounded iCalendar parsing into opaque conflict review.

Only caller-supplied bytes/text are read. No provider, network or filesystem
access occurs, and attendee, location, description and raw content values are
never returned.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone
import re
from typing import Mapping

from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

from .analysis import (
    MODULE_ID,
    MODULE_VERSION,
    PROFILE,
    RESOURCES,
    _REF,
    _datetime,
    review_schedule_conflicts,
)

CAPABILITY_ID = 'calendar.review_ics_conflicts.v1'
MAX_ICS_BYTES = 64 * 1024
MAX_ICS_LINES = 4096
MAX_ICS_EVENTS = 128
MAX_ICS_LINE_CHARS = 4096
_FIELDS = frozenset({'source_ref', 'observed_at', 'content'})
_EVENT_FIELDS = frozenset({'UID', 'DTSTART', 'DTEND', 'TRANSP'})
_PROPERTY = re.compile(r'[A-Z0-9-]+')
_DATE = re.compile(r'\d{8}')
_UTC_STAMP = re.compile(r'\d{8}T\d{6}Z')


def _bounded_text(content: object) -> tuple[str, int]:
    if isinstance(content, str):
        try:
            encoded = content.encode('utf-8')
        except UnicodeEncodeError as exc:
            raise ValueError('iCalendar content must be valid UTF-8 text') from exc
        if len(encoded) > MAX_ICS_BYTES:
            raise ValueError('iCalendar content exceeds size limit')
        text = content
    elif isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
        if len(raw) > MAX_ICS_BYTES:
            raise ValueError('iCalendar content exceeds size limit')
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError('iCalendar content must be valid UTF-8 text') from exc
        encoded = raw
    else:
        raise ValueError('iCalendar content must be bytes or text')
    if '\0' in text or any(ord(ch) < 32 and ch not in '\n\r\t' for ch in text):
        raise ValueError('iCalendar content contains unsupported control characters')
    return text, len(encoded)


def _unfold(text: str) -> list[str]:
    raw_lines = text.splitlines()
    if not raw_lines:
        raise ValueError('empty iCalendar content')
    if len(raw_lines) > MAX_ICS_LINES:
        raise ValueError('iCalendar content exceeds line limit')
    lines: list[str] = []
    for raw in raw_lines:
        if len(raw) > MAX_ICS_LINE_CHARS:
            raise ValueError('iCalendar line exceeds length limit')
        if raw[:1] in (' ', '\t'):
            if not lines:
                raise ValueError('invalid iCalendar line folding')
            if len(lines[-1]) + len(raw) - 1 > MAX_ICS_LINE_CHARS:
                raise ValueError('iCalendar line exceeds length limit')
            lines[-1] += raw[1:]
        else:
            if not raw.strip():
                raise ValueError('blank iCalendar line')
            lines.append(raw)
    return lines


def _property(line: str) -> tuple[str, dict[str, str], str]:
    if ':' not in line:
        raise ValueError('invalid iCalendar property line')
    head, value = line.split(':', 1)
    if not head or head != head.strip():
        raise ValueError('invalid iCalendar property head')
    parts = head.split(';')
    name = parts[0].upper()
    if not _PROPERTY.fullmatch(name):
        raise ValueError('invalid iCalendar property name')
    params: dict[str, str] = {}
    for part in parts[1:]:
        if '=' not in part:
            raise ValueError('invalid iCalendar property parameter')
        key, raw = part.split('=', 1)
        key = key.upper()
        if not key or key in params:
            raise ValueError('invalid or duplicate iCalendar parameter')
        params[key] = raw
    return name, params, value


def _utc_datetime(field: str, params: dict[str, str], value: str) -> datetime:
    value = value.strip()
    if not value or value != value.strip():
        raise ValueError('invalid ' + field)
    value_type = params.get('VALUE', '')
    if value_type.upper() == 'DATE' or (not value_type and _DATE.fullmatch(value)):
        if set(params) - {'VALUE'}:
            raise ValueError('unsupported ' + field + ' parameters')
        if not _DATE.fullmatch(value):
            raise ValueError('invalid ' + field)
        try:
            parsed = date.fromisoformat(value[:4] + '-' + value[4:6] + '-' + value[6:])
        except ValueError as exc:
            raise ValueError('invalid ' + field) from exc
        return datetime.combine(parsed, time.min, tzinfo=timezone.utc)
    if set(params) - {'VALUE'}:
        raise ValueError('unsupported ' + field + ' parameters')
    if not _UTC_STAMP.fullmatch(value):
        raise ValueError(field + ' must be an explicit UTC timestamp or date')
    try:
        return datetime.strptime(value, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError('invalid ' + field) from exc


def _event_value(event: Mapping[str, tuple[dict[str, str], str]], name: str) -> tuple[dict[str, str], str]:
    try:
        return event[name]
    except KeyError as exc:
        raise ValueError('missing iCalendar ' + name) from exc


def _finalize_event(event: Mapping[str, tuple[dict[str, str], str]]) -> dict[str, object]:
    params, uid = _event_value(event, 'UID')
    if params or not _REF.fullmatch(uid):
        raise ValueError('invalid opaque iCalendar event id')
    start_params, start = _event_value(event, 'DTSTART')
    end_params, end = _event_value(event, 'DTEND')
    start_at = _utc_datetime('DTSTART', start_params, start)
    end_at = _utc_datetime('DTEND', end_params, end)
    busy = True
    if 'TRANSP' in event:
        transp_params, transp = event['TRANSP']
        if transp_params:
            raise ValueError('unsupported TRANSP parameters')
        status = transp.strip().upper()
        if status == 'OPAQUE':
            busy = True
        elif status == 'TRANSPARENT':
            busy = False
        else:
            raise ValueError('invalid TRANSP value')
    return {
        'event_id': uid,
        'start_at': start_at.isoformat(),
        'end_at': end_at.isoformat(),
        'busy': busy,
    }


def _parse_ics(text: str) -> list[dict[str, object]]:
    lines = _unfold(text)
    in_calendar = False
    calendar_closed = False
    in_event = False
    event: dict[str, tuple[dict[str, str], str]] = {}
    events: list[dict[str, object]] = []
    seen: set[str] = set()
    for line in lines:
        name, params, value = _property(line)
        if name == 'BEGIN':
            token = value.strip().upper()
            if token == 'VCALENDAR':
                if in_calendar or calendar_closed:
                    raise ValueError('invalid VCALENDAR nesting')
                in_calendar = True
            elif token == 'VEVENT':
                if not in_calendar or calendar_closed or in_event:
                    raise ValueError('invalid VEVENT nesting')
                in_event = True
                event = {}
            else:
                raise ValueError('unsupported iCalendar component')
        elif name == 'END':
            token = value.strip().upper()
            if token == 'VEVENT':
                if not in_event:
                    raise ValueError('VEVENT end without begin')
                finalized = _finalize_event(event)
                uid = str(finalized['event_id'])
                if uid in seen:
                    raise ValueError('duplicate iCalendar event id')
                seen.add(uid)
                events.append(finalized)
                if len(events) > MAX_ICS_EVENTS:
                    raise ValueError('iCalendar event limit exceeded')
                in_event = False
                event = {}
            elif token == 'VCALENDAR':
                if not in_calendar or in_event or calendar_closed:
                    raise ValueError('invalid VCALENDAR end')
                in_calendar = False
                calendar_closed = True
            else:
                raise ValueError('unsupported iCalendar component end')
        elif in_event:
            if name in _EVENT_FIELDS:
                if name in event:
                    raise ValueError('duplicate iCalendar event field')
                event[name] = (params, value)
        elif not in_calendar:
            raise ValueError('iCalendar property outside VCALENDAR')
    if in_event or in_calendar or not calendar_closed:
        raise ValueError('incomplete iCalendar document')
    return events


def review_ics_conflicts(snapshot: Mapping[str, object], *, now: datetime,
                         max_age_seconds: int = 900) -> dict[str, object]:
    if not isinstance(snapshot, Mapping) or set(snapshot) != _FIELDS:
        raise ValueError('exact iCalendar snapshot fields required')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 86400:
        raise ValueError('invalid freshness limit')
    source = snapshot['source_ref']
    if not isinstance(source, str) or not _REF.fullmatch(source):
        raise ValueError('invalid source_ref')
    observed = _datetime(snapshot['observed_at'], 'observed_at')
    text, content_bytes = _bounded_text(snapshot['content'])
    events = _parse_ics(text)
    structure = {
        'source_ref': source,
        'observed_at': observed.isoformat(),
        'events': events,
    }
    reviewed = review_schedule_conflicts(
        structure, now=now, max_age_seconds=max_age_seconds
    )
    return reviewed | {
        'schema': 'sofia.calendar.ics_conflict_review.v1',
        'sdk_protocol': str(SDK_PROTOCOL_VERSION),
        'source_format': 'icalendar',
        'content_bytes': content_bytes,
        'private_contents_returned': False,
        'attendees_returned': False,
        'locations_returned': False,
        'descriptions_returned': False,
        'raw_content_returned': False,
    }


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Parse supplied bounded iCalendar text into opaque event-ID conflict review; '
        'no provider calls, invitations, attendee or location output.',
    )

    def handler(request: CapabilityRequest):
        if (
            not isinstance(request, CapabilityRequest)
            or request.capability != capability
            or set(request.parameters) != {'snapshot'}
        ):
            raise ValueError('invalid calendar iCalendar capability request')
        return review_ics_conflicts(
            request.parameters['snapshot'], now=datetime.now(timezone.utc)
        )

    return ((capability, handler),)
