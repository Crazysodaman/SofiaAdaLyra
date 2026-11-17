"""Bounded, effect-free change-manifest validator for MOD-DEV.

The validator consumes supplied projections only. It never reads a repository,
invokes Git, executes code or runs tests.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.development import capability_registrations as module_registrations
from sofia.modules.development.changes import (
    CAPABILITY_ID,
    capability_registrations,
    validate_change_manifest,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
D1 = 'a' * 64
D2 = 'b' * 64
SECRET = 'raw-diff-secret-value'


def change(**extra):
    return dict(
        change_id='change:1',
        path='src/sofia/modules/development/analysis.py',
        operation='modify',
        added_lines=3,
        removed_lines=1,
        diff_sha256=D1,
        protected=False,
    ) | extra


def evidence(**extra):
    return dict(
        test_id='test:1',
        status='pass',
        evidence_sha256=D2,
        covers_change_refs=['change:1'],
    ) | extra


def manifest(**extra):
    return dict(
        source_ref='dev:manifest',
        observed_at=NOW.isoformat(),
        changes=[change()],
        test_evidence=[evidence()],
    ) | extra


def test_valid_manifest_without_git_or_execution():
    result = validate_change_manifest(manifest(), now=NOW)
    assert result['status'] == 'validated_change_manifest'
    assert result['findings'] == []
    assert result['inspected_change_count'] == 1
    assert result['inspected_test_count'] == 1
    assert result['changes'][0]['finding'] == 'review_eligible'
    assert result['effect'] == 'none'
    assert result['action_authorized'] is False
    assert result['data_persisted'] is False
    assert result['git_executed'] is False
    assert result['code_executed'] is False
    assert result['test_runner_invoked'] is False
    assert result['diff_content_returned'] is False
    assert result['source_authenticity_verified'] is False


def test_protected_change_and_failing_evidence_are_held():
    result = validate_change_manifest(
        manifest(
            changes=[change(protected=True)],
            test_evidence=[evidence(status='fail')],
        ),
        now=NOW,
    )
    assert result['status'] == 'validated_with_findings'
    assert result['changes'][0]['finding'] == 'hold'
    assert set(result['changes'][0]['reasons']) == {
        'protected_path_requires_separate_approval',
        'missing_passing_test_evidence',
    }
    assert result['findings'] == sorted(result['changes'][0]['reasons'])
    assert result['git_executed'] is False


def test_missing_or_unknown_test_evidence_is_truthful():
    missing = validate_change_manifest(manifest(test_evidence=[]), now=NOW)
    assert missing['status'] == 'validated_with_findings'
    assert 'missing_test_evidence' in missing['findings']
    assert missing['changes'][0]['finding'] == 'hold'
    unknown = validate_change_manifest(
        manifest(test_evidence=[evidence(covers_change_refs=['change:other'])]),
        now=NOW,
    )
    assert 'test_evidence_references_unknown_change' in unknown['findings']
    assert unknown['tests'][0]['unknown_change_refs'] == ['change:other']


@pytest.mark.parametrize('delta', [-7200, 3600])
def test_stale_or_future_snapshot_is_unknown(delta):
    result = validate_change_manifest(
        manifest(observed_at=(NOW + timedelta(seconds=delta)).isoformat()), now=NOW)
    assert result['status'] == 'unknown'
    assert result['inspected_change_count'] is None
    assert result['inspected_test_count'] is None
    assert result['changes'] == []
    assert result['tests'] == []
    assert result['findings'] == ['change_manifest_timestamp_invalid']


@pytest.mark.parametrize('change_value', [
    {'change_id': 'bad change'},
    {'path': '../secrets'},
    {'path': '/etc/passwd'},
    {'path': 'src\\windows\\path.py'},
    {'path': 'src//double.py'},
    {'path': 'C:/secret.py'},
    {'operation': 'rewrite'},
    {'added_lines': -1},
    {'added_lines': True},
    {'added_lines': 1_000_001},
    {'removed_lines': 1_000_001},
    {'diff_sha256': 'xyz'},
    {'diff_sha256': 'A' * 64},
    {'protected': 1},
    {'raw_diff': SECRET},
])
def test_change_rejects_malformed_or_oversized(change_value):
    with pytest.raises(ValueError):
        validate_change_manifest(manifest(changes=[change(**change_value)]), now=NOW)


@pytest.mark.parametrize('test_value', [
    {'test_id': 'bad test'},
    {'status': 'maybe'},
    {'evidence_sha256': 'xyz'},
    {'covers_change_refs': 'change:1'},
    {'covers_change_refs': ['change:1', 'change:1']},
    {'covers_change_refs': ['bad ref']},
    {'covers_change_refs': [f'change:{n}' for n in range(33)]},
    {'raw_output': SECRET},
])
def test_test_evidence_rejects_malformed_or_oversized(test_value):
    with pytest.raises(ValueError):
        validate_change_manifest(
            manifest(test_evidence=[evidence(**test_value)]), now=NOW)


@pytest.mark.parametrize('snapshot_change', [
    {'changes': []},
    {'changes': 'bad'},
    {'changes': [change()] * 129},
    {'changes': [change(), change()]},
    {'changes': [change(), change(change_id='change:2')]},
    {'test_evidence': 'bad'},
    {'test_evidence': [evidence()] * 129},
    {'test_evidence': [evidence(), evidence()]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'observed_at': 'not-a-date'},
    {'raw_repository_state': SECRET},
])
def test_manifest_rejects_malformed_or_oversized(snapshot_change):
    with pytest.raises(ValueError):
        validate_change_manifest(manifest(**snapshot_change), now=NOW)


def test_manifest_rejects_extra_snapshot_fields():
    with pytest.raises(ValueError):
        validate_change_manifest(manifest(execute=True), now=NOW)


def test_result_does_not_echo_private_raw_content():
    result = validate_change_manifest(manifest(), now=NOW)
    assert SECRET not in json.dumps(result)
    assert result['changes'][0]['diff_sha256'] == D1
    assert result['tests'][0]['evidence_sha256'] == D2


def test_change_manifest_registration_is_inert():
    registrations = capability_registrations()
    assert [cap.name for cap, _ in registrations] == [CAPABILITY_ID]
    capability, handler = next(
        item for item in module_registrations() if item[0].name == CAPABILITY_ID)
    assert isinstance(capability, Capability)
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'snapshot': manifest()}, None, 'forged'))
    live_observed = datetime.now(timezone.utc)
    live = manifest(
        observed_at=live_observed.isoformat(),
        test_evidence=[evidence()],
    )
    outcome = handler(CapabilityRequest(
        capability, {'snapshot': live}, None, 'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
    with pytest.raises(ValueError):
        handler(CapabilityRequest(
            capability, {'snapshot': live, 'run_git': True}, None, 'invalid'))
