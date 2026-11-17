"""Bounded iCalendar parsing tests. No provider, network or filesystem access."""
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.calendar.parsing import (
    CAPABILITY_ID,
    MAX_ICS_BYTES,
    capability_registrations,
    review_ics_conflicts,
)
from sofia.platform.capability.model import CapabilityRequest

NOW = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)


def vevent(uid, start, end, busy=None, extra=()):
    lines = ['BEGIN:VEVENT', f'UID:{uid}', f'DTSTART:{start}', f'DTEND:{end}']
    if busy is not None:
        lines.append('TRANSP:' + ('OPAQUE' if busy else 'TRANSPARENT'))
    lines.extend(extra)
    lines.append('END:VEVENT')
    return lines


def ics(*events):
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//test//EN']
    for event in events:
        lines.extend(event)
    lines.append('END:VCALENDAR')
    return '\r\n'.join(lines) + '\r\n'


def snapshot(content, **changes):
    return {
        'source_ref': 'calendar:supplied',
        'observed_at': NOW.isoformat(),
        'content': content,
    } | changes


def exact_size_ics(size):
    head = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//test//EN']
    body = vevent('event-a', '20261025T100000Z', '20261025T110000Z')
    tail = ['END:VCALENDAR']
    base_size = sum(len(part) + 2 for part in head + body + tail)
    remaining = size - base_size
    if remaining < 0:
        raise AssertionError('requested iCalendar size is too small')
    pads = []
    while remaining > 4002:
        pads.append('X-PAD:' + 'a' * 3994)
        remaining -= 4002
    if remaining:
        if remaining >= 8:
            length = remaining - 2
            pads.append('X-PAD:' + 'a' * (length - 6))
        else:
            borrow = 8 - remaining
            previous = pads[-1]
            reduced = len(previous) - borrow
            if reduced < 6:
                raise AssertionError('cannot pad iCalendar exactly')
            pads[-1] = previous[:reduced]
            pads.append('X-PAD:')
    content = '\r\n'.join(head + pads + body + tail) + '\r\n'
    assert len(content.encode('utf-8')) == size
    return content


def test_ics_reviews_only_opaque_event_ids_and_ignores_free_time():
    content = ics(
        vevent(
            'event-a',
            '20261025T100000Z',
            '20261025T110000Z',
            extra=[
                'ATTENDEE;CN=Private Person:mailto:secret@example.com',
                'LOCATION:Private Office',
                'DESCRIPTION:Secret plan',
            ],
        ),
        vevent('event-b', '20261025T103000Z', '20261025T113000Z'),
        vevent('event-free', '20261025T100000Z', '20261025T120000Z', busy=False),
    )
    result = review_ics_conflicts(snapshot(content), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['event_count'] == 3
    assert result['busy_event_count'] == 2
    assert result['conflicts'] == [{'event_ids': ['event-a', 'event-b'],
                                    'overlap_seconds': 1800}]
    assert result['effect'] == 'none'
    assert result['events_modified'] is False
    assert result['invitations_sent'] is False
    assert result['private_contents_returned'] is False
    assert result['attendees_returned'] is False
    assert result['locations_returned'] is False
    assert result['descriptions_returned'] is False
    assert result['raw_content_returned'] is False
    text = str(result)
    assert 'secret@example.com' not in text
    assert 'Private Office' not in text
    assert 'Secret plan' not in text


def test_ics_accepts_bytes_and_all_day_utc_dates():
    content = (
        'BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:event-day\r\n'
        'DTSTART;VALUE=DATE:20261025\r\nDTEND;VALUE=DATE:20261026\r\n'
        'END:VEVENT\r\nEND:VCALENDAR\r\n'
    ).encode('utf-8')
    result = review_ics_conflicts(snapshot(content), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['event_count'] == 1
    assert result['content_bytes'] == len(content)


def test_ics_exact_size_limit_is_accepted():
    content = exact_size_ics(MAX_ICS_BYTES)
    result = review_ics_conflicts(snapshot(content), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['content_bytes'] == MAX_ICS_BYTES


def test_ics_oversized_content_is_rejected():
    with pytest.raises(ValueError, match='size'):
        review_ics_conflicts(snapshot(exact_size_ics(MAX_ICS_BYTES) + 'a'), now=NOW)
    with pytest.raises(ValueError, match='size'):
        review_ics_conflicts(snapshot(b'x' * (MAX_ICS_BYTES + 1)), now=NOW)


@pytest.mark.parametrize('content', [
    b'\xff',
    'not a calendar',
    ics(vevent('dup', '20261025T100000Z', '20261025T110000Z'),
        vevent('dup', '20261025T120000Z', '20261025T130000Z')),
    ics(['BEGIN:VEVENT', 'DTSTART:20261025T100000Z',
         'DTEND:20261025T110000Z', 'END:VEVENT']),
    ics(vevent('bad id', '20261025T100000Z', '20261025T110000Z')),
    ics(vevent('bad-float', '20261025T100000', '20261025T110000Z')),
    ics(vevent('bad-zone', 'TZID=Europe/Paris:20261025T100000Z',
               '20261025T110000Z')),
    ics(vevent('bad-range', '20261025T110000Z', '20261025T100000Z')),
    ics(['BEGIN:VEVENT', 'UID:unclosed', 'DTSTART:20261025T100000Z']),
    ics(vevent('nul', '20261025T100000Z', '20261025T110000Z')) + '\x00',
    ics(['BEGIN:VEVENT', 'UID:bad-repeat', 'DTSTART:20261025T100000Z',
         'DTSTART:20261025T103000Z', 'DTEND:20261025T110000Z', 'END:VEVENT']),
])
def test_ics_rejects_malformed_or_duplicate_content(content):
    with pytest.raises(ValueError):
        review_ics_conflicts(snapshot(content), now=NOW)


def test_ics_rejects_too_many_events():
    events = [vevent(f'event-{index}', '20261025T100000Z',
                     '20261025T110000Z') for index in range(129)]
    with pytest.raises(ValueError, match='limit'):
        review_ics_conflicts(snapshot(ics(*events)), now=NOW)


def test_ics_rejects_wrong_content_type_and_extra_fields():
    with pytest.raises(ValueError):
        review_ics_conflicts(snapshot(123), now=NOW)
    with pytest.raises(ValueError):
        review_ics_conflicts(
            snapshot(ics()) | {'command': 'delete'}, now=NOW
        )


def test_ics_stale_or_future_observation_is_unknown():
    content = ics(vevent('event-a', '20261025T100000Z', '20261025T110000Z'))
    for observed in (NOW - timedelta(hours=1), NOW + timedelta(minutes=1)):
        result = review_ics_conflicts(
            snapshot(content, observed_at=observed.isoformat()),
            now=NOW,
            max_age_seconds=900,
        )
        assert result['status'] == 'unknown'
        assert result['event_count'] is None
        assert result['busy_event_count'] is None
        assert result['conflicts'] == []


def test_ics_capability_registration_shape_and_handler():
    entries = capability_registrations()
    assert len(entries) == 1
    capability, handler = entries[0]
    assert capability.name == CAPABILITY_ID
    assert capability.name.endswith('.v1')
    now = datetime.now(timezone.utc)
    live = {
        'source_ref': 'calendar:supplied',
        'observed_at': now.isoformat(),
        'content': ics(vevent('event-live', '20261025T100000Z',
                              '20261025T110000Z')),
    }
    result = handler(CapabilityRequest(
        capability, {'snapshot': live}, requested_scope=None, rationale='test'
    ))
    assert result['status'] == 'reviewed' and result['effect'] == 'none'
    assert result['sdk_protocol'] == '1.0'
    for parameters in ({}, {'snapshot': live, 'unsafe': True}):
        with pytest.raises(ValueError):
            handler(CapabilityRequest(
                capability, parameters, requested_scope=None, rationale='test'
            ))
