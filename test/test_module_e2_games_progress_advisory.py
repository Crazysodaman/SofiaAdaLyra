"""MOD-GAMES: supplied progress evidence is reviewed, never verified state."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.games.analysis import (
    CAPABILITY_ID,
    PROFILE,
    capability_registrations,
    review_games,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def item(**extra):
    return dict(id='objective-1', progress=5, target=10, failed=False,
                evidence_ref='session:capture-1') | extra


def snapshot(**extra):
    return dict(source_ref='game:session-1', observed_at=NOW.isoformat(),
                items=[item()]) | extra


def entry():
    return next(row for row in capability_registrations()
                if row[0].name == CAPABILITY_ID)


def test_progress_is_reported_without_claiming_game_state():
    result = review_games(snapshot(), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['inspected_count'] == 1
    assert result['freshness'] == 'fresh'
    assert result['evidence_class'] == 'supplied_unverified'
    assert result['effect'] == 'none'
    assert result['action_authorized'] is False
    assert result['data_persisted'] is False
    row = result['results'][0]
    assert row['completion'] == pytest.approx(0.5)
    assert row['finding'] == 'reported_in_progress'
    assert row['game_state_verified'] is False
    assert PROFILE == 'ADVISORY'


def test_complete_and_failed_are_reported_only():
    completed = review_games(snapshot(items=[item(progress=11)]), now=NOW)
    assert completed['results'][0]['completion'] == 1.0
    assert completed['results'][0]['finding'] == 'reported_complete'
    assert completed['results'][0]['game_state_verified'] is False
    failed = review_games(snapshot(items=[item(failed=True)]), now=NOW)
    assert failed['results'][0]['finding'] == 'reported_failed'
    assert failed['results'][0]['game_state_verified'] is False
    assert failed['effect'] == 'none'


def test_no_items_is_reviewed_without_verification_claim():
    result = review_games(snapshot(items=[]), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['inspected_count'] == 0
    assert result['results'] == []
    assert result['findings'] == []
    assert result['effect'] == 'none'


@pytest.mark.parametrize('change', [
    {'progress': -1},
    {'progress': 1000001},
    {'progress': True},
    {'target': 0},
    {'target': 1000001},
    {'failed': 0},
    {'evidence_ref': 'bad\nref'},
    {'unknown_field': 'x'},
])
def test_unsafe_or_out_of_range_items_are_rejected(change):
    with pytest.raises(ValueError):
        review_games(snapshot(items=[item(**change)]), now=NOW)


@pytest.mark.parametrize('change', [
    {'items': 'not-a-list'},
    {'items': [item()] * 129},
    {'source_ref': 'bad\nref'},
    {'observed_at': 'naive'},
    {'extra_execute': True},
])
def test_snapshot_bounds_and_schema_are_enforced(change):
    with pytest.raises(ValueError):
        review_games(snapshot(**change), now=NOW)


@pytest.mark.parametrize('stamp', [NOW - timedelta(hours=2),
                                   NOW + timedelta(minutes=10)])
def test_stale_or_future_snapshot_masks_results(stamp):
    result = review_games(snapshot(observed_at=stamp.isoformat()), now=NOW)
    assert result['status'] == 'unknown'
    assert result['inspected_count'] is None
    assert result['results'] == []
    assert result['findings'] == ['snapshot_timestamp_invalid']
    assert result['effect'] == 'none'


@pytest.mark.parametrize('policy', [{'max_age_seconds': 0},
                                    {'max_age_seconds': 86401},
                                    {'max_age_seconds': True}])
def test_freshness_policy_bounds_are_enforced(policy):
    with pytest.raises(ValueError):
        review_games(snapshot(), now=NOW, **policy)


def test_duplicate_identities_are_rejected():
    with pytest.raises(ValueError):
        review_games(snapshot(items=[item(), item()]), now=NOW)


def test_input_is_not_mutated():
    original = snapshot()
    preserved = deepcopy(original)
    review_games(original, now=NOW)
    assert original == preserved


def test_registration_is_inert_and_identity_checked():
    capability, handler = entry()
    assert isinstance(capability, Capability)
    assert capability.name == CAPABILITY_ID
    live = snapshot(observed_at=datetime.now(timezone.utc).isoformat())
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'snapshot': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, {'snapshot': live, 'play': True},
                                  None, 'scope creep'))
    outcome = handler(CapabilityRequest(capability, {'snapshot': live}, None,
                                        'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
