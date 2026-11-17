"""Bounded, effect-free independent review validator for MOD-MENTOR.

The validator consumes supplied review evidence only. It never accepts
self-certification, grades identity or transfers authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.mentor_review import capability_registrations as module_registrations
from sofia.modules.mentor_review.independent import (
    CAPABILITY_ID,
    capability_registrations,
    validate_review_evidence,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
D1 = 'a' * 64
SECRET = 'raw-private-review-transcript'


def review(**extra):
    return dict(
        review_id='review:1',
        reviewer_ref='reviewer:alice',
        subject_ref='sofia:core',
        criterion='grounding',
        score=4,
        maximum=5,
        evidence_sha256=D1,
        self_certified=False,
    ) | extra


def manifest(**extra):
    return dict(
        source_ref='mentor:review-evidence',
        observed_at=NOW.isoformat(),
        reviews=[review()],
    ) | extra


def test_valid_independent_review_without_identity_grading():
    result = validate_review_evidence(manifest(), now=NOW)
    assert result['status'] == 'validated_review_evidence'
    assert result['findings'] == []
    assert result['inspected_review_count'] == 1
    assert result['reviews'][0]['finding'] == 'eligible_independent_review'
    assert result['reviews'][0]['normalized_score'] == pytest.approx(0.8)
    assert result['effect'] == 'none'
    assert result['action_authorized'] is False
    assert result['data_persisted'] is False
    assert result['identity_graded'] is False
    assert result['self_certification_accepted'] is False
    assert result['review_authenticity_verified'] is False


def test_self_certification_is_rejected_not_accepted():
    result = validate_review_evidence(
        manifest(reviews=[review(self_certified=True)]), now=NOW)
    assert result['status'] == 'validated_with_findings'
    assert result['reviews'][0]['finding'] == 'not_independent'
    assert 'self_certification_rejected' in result['findings']
    assert result['self_certification_accepted'] is False
    assert result['identity_graded'] is False


def test_reviewer_subject_identity_conflict_is_not_independent():
    result = validate_review_evidence(
        manifest(reviews=[review(reviewer_ref='sofia:core')]), now=NOW)
    assert result['reviews'][0]['finding'] == 'not_independent'
    assert 'reviewer_subject_identity_conflict' in result['findings']


@pytest.mark.parametrize('delta', [-7200, 3600])
def test_stale_or_future_snapshot_is_unknown(delta):
    result = validate_review_evidence(
        manifest(observed_at=(NOW + timedelta(seconds=delta)).isoformat()), now=NOW)
    assert result['status'] == 'unknown'
    assert result['inspected_review_count'] is None
    assert result['reviews'] == []
    assert result['findings'] == ['review_evidence_timestamp_invalid']


@pytest.mark.parametrize('review_value', [
    {'review_id': 'bad review'},
    {'reviewer_ref': 'bad reviewer'},
    {'subject_ref': 'bad subject'},
    {'criterion': 'popularity'},
    {'maximum': 0},
    {'maximum': 101},
    {'maximum': True},
    {'score': -1},
    {'score': 6},
    {'score': True},
    {'evidence_sha256': 'xyz'},
    {'evidence_sha256': 'A' * 64},
    {'self_certified': 1},
    {'raw_transcript': SECRET},
])
def test_review_rejects_malformed_or_oversized(review_value):
    with pytest.raises(ValueError):
        validate_review_evidence(manifest(reviews=[review(**review_value)]), now=NOW)


@pytest.mark.parametrize('snapshot_change', [
    {'reviews': []},
    {'reviews': 'bad'},
    {'reviews': [review()] * 129},
    {'reviews': [review(), review()]},
    {'reviews': [review(), review(review_id='review:2')]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'observed_at': 'not-a-date'},
    {'raw_review_transcript': SECRET},
])
def test_manifest_rejects_malformed_or_oversized(snapshot_change):
    with pytest.raises(ValueError):
        validate_review_evidence(manifest(**snapshot_change), now=NOW)


def test_manifest_rejects_extra_snapshot_fields():
    with pytest.raises(ValueError):
        validate_review_evidence(manifest(certify=True), now=NOW)


def test_result_does_not_echo_private_raw_content():
    result = validate_review_evidence(manifest(), now=NOW)
    assert SECRET not in json.dumps(result)
    assert result['reviews'][0]['evidence_sha256'] == D1


def test_review_evidence_registration_is_inert():
    registrations = capability_registrations()
    assert [cap.name for cap, _ in registrations] == [CAPABILITY_ID]
    capability, handler = next(
        item for item in module_registrations() if item[0].name == CAPABILITY_ID)
    assert isinstance(capability, Capability)
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'snapshot': manifest()}, None, 'forged'))
    live = manifest(observed_at=datetime.now(timezone.utc).isoformat())
    outcome = handler(CapabilityRequest(
        capability, {'snapshot': live}, None, 'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            capability, {'snapshot': live, 'certify': True}, None, 'invalid'))
