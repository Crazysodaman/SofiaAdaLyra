"""Offline validation tests for supplied backup/restore plans and evidence.

No backup is created, no restore is performed and no canonical state is read.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sofia.modules.it_backup_dr.recovery_plan import (
    capability_registrations as plan_regs,
    validate_recovery_plan,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def at(seconds: int = 0) -> str:
    return (NOW + timedelta(seconds=seconds)).isoformat()


def target(**extra):
    return {
        'target_ref': 'target:primary',
        'storage_ref': 'storage:primary',
        'encrypted_reported': True,
        'offsite_reported': True,
    } | extra


def evidence(**extra):
    return {
        'last_backup_at': at(-60),
        'backup_state': 'completed',
        'integrity_check': 'passed',
        'restore_drill': 'passed',
        'restore_duration_seconds': 120,
    } | extra


def plan(**extra):
    return {
        'source_ref': 'backup:plan',
        'observed_at': at(),
        'dataset_ref': 'dataset:one',
        'plan_ref': 'plan:one',
        'backup_interval_seconds': 3600,
        'retention_seconds': 86400,
        'rpo_seconds': 7200,
        'rto_seconds': 600,
        'targets': [target(), target(target_ref='target:secondary',
                                     storage_ref='storage:secondary')],
        'evidence': evidence(),
    } | extra


def test_recovery_plan_consistent_is_effect_free():
    result = validate_recovery_plan(plan(), now=NOW)
    assert result['status'] == 'validated_consistent'
    assert result['findings'] == []
    assert result['target_count'] == 2
    assert result['restore_claim'] == 'supplied_pass'
    assert result['backup_created'] is False
    assert result['restore_performed'] is False
    assert result['restore_independently_verified'] is False
    assert result['canonical_state_inspected'] is False
    assert result['effect'] == 'none'
    assert result['evidence_class'] == 'supplied_unverified'


def test_recovery_plan_flags_incoherent_schedule_and_targets():
    result = validate_recovery_plan(
        plan(backup_interval_seconds=7201, retention_seconds=3600,
             targets=[target(encrypted_reported=False, offsite_reported=False)]),
        now=NOW,
    )
    assert result['status'] == 'validated_with_findings'
    assert set(result['findings']) == {
        'retention_shorter_than_backup_interval',
        'backup_interval_exceeds_rpo',
        'single_backup_target_reported',
        'target_encryption_unconfirmed',
        'target_offsite_unconfirmed',
    }


def test_recovery_plan_evidence_failures_remain_supplied_claims():
    result = validate_recovery_plan(
        plan(evidence=evidence(
            last_backup_at=at(-10000), backup_state='failed',
            integrity_check='failed', restore_drill='failed',
            restore_duration_seconds=None)),
        now=NOW,
    )
    assert result['status'] == 'validated_with_findings'
    assert {
        'backup_failure_reported', 'rpo_exceeded',
        'integrity_failure_reported', 'restore_drill_failure_reported',
    }.issubset(result['findings'])
    assert result['restore_claim'] == 'not_verified'
    assert result['restore_performed'] is False


def test_recovery_plan_unverified_drill_is_not_restorable_proof():
    result = validate_recovery_plan(
        plan(evidence=evidence(restore_drill='not_run',
                               restore_duration_seconds=None)),
        now=NOW,
    )
    assert result['restore_claim'] == 'not_verified'
    assert 'restore_not_verified' in result['findings']
    assert 'integrity_not_verified' not in result['findings']


def test_recovery_plan_rto_exceeded_in_drill():
    result = validate_recovery_plan(
        plan(evidence=evidence(restore_duration_seconds=601)),
        now=NOW,
    )
    assert 'rto_exceeded_in_drill' in result['findings']


def test_recovery_plan_stale_snapshot_is_unknown():
    result = validate_recovery_plan(
        plan(observed_at=at(-3600), evidence=evidence(last_backup_at=at(-7200))),
        now=NOW,
    )
    assert result['status'] == 'unknown'
    assert result['target_count'] is None
    assert result['targets'] == []
    assert result['last_backup_age_seconds'] is None
    assert result['restore_claim'] == 'not_verified'
    assert result['findings'] == ['snapshot_timestamp_invalid']


@pytest.mark.parametrize('change', [
    {'targets': []},
    {'targets': [target(target_ref=f'target:{n}') for n in range(33)]},
    {'targets': [target(), target()]},
    {'targets': [target(storage_ref='../secrets')]},
    {'targets': [target(encrypted_reported='yes')]},
    {'targets': [target(offsite_reported=1)]},
    {'backup_interval_seconds': 0},
    {'backup_interval_seconds': True},
    {'retention_seconds': 0},
    {'rpo_seconds': 0},
    {'rto_seconds': 0},
    {'rpo_seconds': 31_536_001},
    {'evidence': evidence(last_backup_at=at(60))},
    {'evidence': evidence(backup_state='running')},
    {'evidence': evidence(integrity_check='okay')},
    {'evidence': evidence(restore_drill='started')},
    {'evidence': evidence(restore_drill='not_run', restore_duration_seconds=30)},
    {'evidence': evidence(restore_drill='passed', restore_duration_seconds=None)},
    {'evidence': evidence(restore_duration_seconds=-1)},
    {'evidence': {k: v for k, v in evidence().items() if k != 'backup_state'}},
    {'evidence': evidence() | {'restore_now': True}},
    {'source_ref': 'backup\nplan'},
    {'dataset_ref': '../dataset'},
    {'plan_ref': 'plan\\secret'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'execute_restore': True},
])
def test_recovery_plan_rejects_malformed_or_oversized(change):
    with pytest.raises(ValueError):
        validate_recovery_plan(plan(**change), now=NOW)


def test_recovery_plan_registration_is_inert_and_identity_checked():
    (capability, handler), = plan_regs()
    assert isinstance(capability, Capability)
    assert capability.name == 'it.backup_dr.validate_recovery_plan.v1'
    live = plan(observed_at=datetime.now(timezone.utc).isoformat(),
                evidence=evidence(
                    last_backup_at=(datetime.now(timezone.utc)
                                    - timedelta(seconds=60)).isoformat()))
    result = handler(CapabilityRequest(capability, {'plan': live},
                                      None, 'offline recovery plan review'))
    assert result['effect'] == 'none'
    assert result['restore_performed'] is False
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'plan': live}, None, 'forged'))
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, {'plan': live, 'restore': True},
                                  None, 'invalid'))
