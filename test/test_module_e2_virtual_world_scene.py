"""MOD-VIRTUAL-WORLD: supplied scene footprints are reviewed without rendering."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.virtual_world.analysis import (
    CAPABILITY_ID,
    PROFILE,
    capability_registrations,
    review_virtual_world,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def item(**extra):
    return dict(id='chair', x=1.0, y=2.0, width=0.8, height=0.5,
                space_id='room:1') | extra


def snapshot(**extra):
    return dict(source_ref='world:scene-1', observed_at=NOW.isoformat(),
                items=[item()]) | extra


def entry():
    return next(row for row in capability_registrations()
                if row[0].name == CAPABILITY_ID)


def test_placement_review_reports_bounds_without_modifying_world():
    result = review_virtual_world(snapshot(), now=NOW)
    assert result['status'] == 'reviewed'
    assert result['freshness'] == 'fresh'
    assert result['inspected_count'] == 1
    assert result['findings'] == ['placement_candidate']
    row = result['results'][0]
    assert row['bounds'] == (1.0, 2.0, 1.8, 2.5)
    assert row['world_state_modified'] is False
    assert result['action_authorized'] is False
    assert result['data_persisted'] is False
    assert result['effect'] == 'none'
    assert result['evidence_class'] == 'supplied_unverified'
    assert PROFILE == 'SIMULATE'


def test_overlap_is_detected_only_within_the_same_owned_space():
    overlapping = review_virtual_world(
        snapshot(items=[item(), item(id='table', x=1.5)]), now=NOW)
    assert overlapping['findings'] == ['footprint_overlap']
    assert all(row['finding'] == 'footprint_overlap'
               for row in overlapping['results'])
    separated = review_virtual_world(
        snapshot(items=[item(), item(id='table', x=1.5,
                                     space_id='room:2')]), now=NOW)
    assert separated['findings'] == ['placement_candidate']


def test_same_identity_cannot_be_owned_by_two_spaces():
    with pytest.raises(ValueError):
        review_virtual_world(
            snapshot(items=[item(), item(space_id='room:2')]), now=NOW)


@pytest.mark.parametrize('change', [
    {'x': 10001},
    {'y': -10001},
    {'width': 0},
    {'height': -1},
    {'width': float('nan')},
    {'space_id': 'bad space'},
    {'id': 'bad id'},
    {'secret_render_target': 'x'},
])
def test_unsafe_or_out_of_range_items_are_rejected(change):
    with pytest.raises(ValueError):
        review_virtual_world(snapshot(items=[item(**change)]), now=NOW)


@pytest.mark.parametrize('change', [
    {'items': 'not-a-list'},
    {'items': [item(id=f'o{n}') for n in range(129)]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'render_now': True},
])
def test_snapshot_bounds_and_schema_are_enforced(change):
    with pytest.raises(ValueError):
        review_virtual_world(snapshot(**change), now=NOW)


@pytest.mark.parametrize('stamp', [NOW - timedelta(hours=2),
                                   NOW + timedelta(minutes=10)])
def test_stale_or_future_scene_masks_results(stamp):
    result = review_virtual_world(snapshot(observed_at=stamp.isoformat()),
                                  now=NOW)
    assert result['status'] == 'unknown'
    assert result['inspected_count'] is None
    assert result['results'] == []
    assert result['findings'] == ['snapshot_timestamp_invalid']
    assert result['action_authorized'] is False
    assert result['effect'] == 'none'


@pytest.mark.parametrize('policy', [{'max_age_seconds': 0},
                                    {'max_age_seconds': 86401},
                                    {'max_age_seconds': True}])
def test_freshness_bounds_are_enforced(policy):
    with pytest.raises(ValueError):
        review_virtual_world(snapshot(), now=NOW, **policy)


def test_duplicate_identities_are_rejected_and_input_is_not_mutated():
    original = snapshot()
    preserved = deepcopy(original)
    review_virtual_world(original, now=NOW)
    assert original == preserved
    with pytest.raises(ValueError):
        review_virtual_world(snapshot(items=[item(), item()]), now=NOW)


def test_registration_is_inert_and_identity_checked():
    capability, handler = entry()
    assert isinstance(capability, Capability)
    assert capability.name == CAPABILITY_ID
    live = snapshot(observed_at=datetime.now(timezone.utc).isoformat())
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'snapshot': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability,
                                  {'snapshot': live, 'render': True},
                                  None, 'scope creep'))
    outcome = handler(CapabilityRequest(capability, {'snapshot': live}, None,
                                        'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
