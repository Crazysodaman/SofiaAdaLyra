"""Bounded, effect-free ML and generalization evidence validators.

Both validators consume supplied projections only. They never train, infer,
download data, modify models or verify release/AGI claims.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from sofia.modules.generalization import (
    capability_registrations as generalization_module_registrations,
)
from sofia.modules.generalization.transfer import (
    CAPABILITY_ID as TRANSFER_CAPABILITY_ID,
    capability_registrations as transfer_registrations,
    validate_transfer_evidence,
)
from sofia.modules.ml_evaluation import (
    capability_registrations as ml_module_registrations,
)
from sofia.modules.ml_evaluation.evaluation import (
    CAPABILITY_ID as EVALUATION_CAPABILITY_ID,
    capability_registrations as evaluation_registrations,
    validate_evaluation_evidence,
)
from sofia.platform.capability.model import Capability, CapabilityRequest

NOW = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
SECRET = 'raw-private-dataset-row'


def evaluation(**extra):
    return dict(
        evaluation_id='eval:1',
        split_kind='holdout',
        tp=8,
        fp=2,
        tn=8,
        fn=2,
        leakage_check_passed=True,
        baseline_ref='baseline:majority',
        baseline_f1=0.5,
    ) | extra


def evaluation_manifest(**extra):
    return dict(
        source_ref='ml:evaluation-evidence',
        observed_at=NOW.isoformat(),
        evaluations=[evaluation()],
    ) | extra


def trial(**extra):
    return dict(
        trial_id='trial:1',
        task_ref='task:new',
        baseline_successes=4,
        candidate_successes=8,
        trial_count=10,
        novel_task=True,
        independent_holdout=True,
        leakage_check_passed=True,
    ) | extra


def transfer_manifest(**extra):
    return dict(
        source_ref='generalization:transfer-evidence',
        observed_at=NOW.isoformat(),
        trials=[trial()],
    ) | extra


# MOD-ML -----------------------------------------------------------------------

def test_valid_holdout_evaluation_without_training_or_inference():
    result = validate_evaluation_evidence(evaluation_manifest(), now=NOW)
    assert result['status'] == 'validated_evaluation_evidence'
    assert result['findings'] == []
    assert result['inspected_evaluation_count'] == 1
    row = result['evaluations'][0]
    assert row['split_kind'] == 'holdout'
    assert row['total'] == 20
    assert row['precision'] == pytest.approx(0.8)
    assert row['recall'] == pytest.approx(0.8)
    assert row['f1'] == pytest.approx(0.8)
    assert row['finding'] == 'reviewable_holdout'
    assert row['release_verified'] is False
    assert result['effect'] == 'none'
    assert result['action_authorized'] is False
    assert result['data_persisted'] is False
    assert result['training_executed'] is False
    assert result['inference_executed'] is False
    assert result['dataset_downloaded'] is False
    assert result['hyperparameters_tuned'] is False
    assert result['release_verified'] is False


@pytest.mark.parametrize('value,finding', [
    ({'split_kind': 'train'}, 'not_independent_holdout'),
    ({'split_kind': 'validation'}, 'not_independent_holdout'),
    ({'leakage_check_passed': False}, 'leakage_check_failed'),
    ({'baseline_f1': 0.9}, 'baseline_not_beaten'),
])
def test_evaluation_split_leakage_and_baseline_findings(value, finding):
    result = validate_evaluation_evidence(
        evaluation_manifest(evaluations=[evaluation(**value)]), now=NOW)
    assert result['status'] == 'validated_with_findings'
    assert finding in result['findings']
    assert result['evaluations'][0]['finding'] == 'evaluation_hold'
    assert result['training_executed'] is False
    assert result['inference_executed'] is False


def test_empty_confusion_matrix_is_not_evaluation_evidence():
    result = validate_evaluation_evidence(
        evaluation_manifest(evaluations=[
            evaluation(tp=0, fp=0, tn=0, fn=0)]), now=NOW)
    assert result['evaluations'][0]['finding'] == 'evaluation_hold'
    assert 'no_evaluation_samples' in result['findings']
    assert 'metric_undefined' in result['findings']
    assert result['release_verified'] is False


@pytest.mark.parametrize('delta', [-7200, 3600])
def test_evaluation_stale_or_future_snapshot_is_unknown(delta):
    result = validate_evaluation_evidence(
        evaluation_manifest(observed_at=(NOW + timedelta(seconds=delta)).isoformat()),
        now=NOW,
    )
    assert result['status'] == 'unknown'
    assert result['inspected_evaluation_count'] is None
    assert result['evaluations'] == []
    assert result['findings'] == ['evaluation_evidence_timestamp_invalid']


@pytest.mark.parametrize('evaluation_value', [
    {'evaluation_id': 'bad evaluation'},
    {'split_kind': 'test'},
    {'tp': -1},
    {'tp': True},
    {'tp': 10_000_001},
    {'fp': 10_000_001},
    {'tn': 10_000_001},
    {'fn': 10_000_001},
    {'leakage_check_passed': 1},
    {'baseline_ref': 'bad baseline'},
    {'baseline_f1': -0.1},
    {'baseline_f1': 1.1},
    {'baseline_f1': float('nan')},
    {'baseline_f1': float('inf')},
    {'baseline_f1': True},
    {'raw_predictions': SECRET},
])
def test_evaluation_rejects_malformed_or_oversized(evaluation_value):
    with pytest.raises(ValueError):
        validate_evaluation_evidence(
            evaluation_manifest(evaluations=[evaluation(**evaluation_value)]),
            now=NOW,
        )


@pytest.mark.parametrize('snapshot_change', [
    {'evaluations': []},
    {'evaluations': 'bad'},
    {'evaluations': [evaluation()] * 129},
    {'evaluations': [evaluation(), evaluation()]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'observed_at': 'not-a-date'},
    {'raw_dataset': SECRET},
])
def test_evaluation_manifest_rejects_malformed_or_oversized(snapshot_change):
    with pytest.raises(ValueError):
        validate_evaluation_evidence(evaluation_manifest(**snapshot_change), now=NOW)


def test_evaluation_manifest_rejects_extra_snapshot_fields():
    with pytest.raises(ValueError):
        validate_evaluation_evidence(evaluation_manifest(train=True), now=NOW)


def test_evaluation_result_does_not_echo_private_raw_content():
    result = validate_evaluation_evidence(evaluation_manifest(), now=NOW)
    assert SECRET not in json.dumps(result)


# MOD-GENERALIZATION -----------------------------------------------------------

def test_valid_transfer_evidence_without_model_change():
    result = validate_transfer_evidence(transfer_manifest(), now=NOW)
    assert result['status'] == 'validated_transfer_evidence'
    assert result['findings'] == []
    assert result['inspected_trial_count'] == 1
    row = result['trials'][0]
    assert row['delta_success_rate'] == pytest.approx(0.4)
    assert row['finding'] == 'candidate_transfer_evidence'
    assert row['generalized_intelligence_verified'] is False
    assert result['effect'] == 'none'
    assert result['action_authorized'] is False
    assert result['data_persisted'] is False
    assert result['training_executed'] is False
    assert result['inference_executed'] is False
    assert result['model_modified'] is False
    assert result['generalized_intelligence_verified'] is False


@pytest.mark.parametrize('value,finding', [
    ({'novel_task': False}, 'not_novel_task'),
    ({'independent_holdout': False}, 'not_independent_transfer'),
    ({'leakage_check_passed': False}, 'leakage_check_failed'),
    ({'candidate_successes': 4}, 'baseline_not_beaten'),
])
def test_transfer_novelty_independence_leakage_and_baseline(value, finding):
    result = validate_transfer_evidence(
        transfer_manifest(trials=[trial(**value)]), now=NOW)
    assert result['status'] == 'validated_with_findings'
    assert finding in result['findings']
    assert result['trials'][0]['finding'] == 'transfer_hold'
    assert result['generalized_intelligence_verified'] is False


@pytest.mark.parametrize('delta', [-7200, 3600])
def test_transfer_stale_or_future_snapshot_is_unknown(delta):
    result = validate_transfer_evidence(
        transfer_manifest(observed_at=(NOW + timedelta(seconds=delta)).isoformat()),
        now=NOW,
    )
    assert result['status'] == 'unknown'
    assert result['inspected_trial_count'] is None
    assert result['trials'] == []
    assert result['findings'] == ['transfer_evidence_timestamp_invalid']


@pytest.mark.parametrize('trial_value', [
    {'trial_id': 'bad trial'},
    {'task_ref': 'bad task'},
    {'trial_count': 0},
    {'trial_count': 100_001},
    {'trial_count': True},
    {'baseline_successes': -1},
    {'baseline_successes': 11},
    {'baseline_successes': True},
    {'candidate_successes': -1},
    {'candidate_successes': 11},
    {'novel_task': 1},
    {'independent_holdout': 1},
    {'leakage_check_passed': 1},
    {'raw_transfer_transcript': SECRET},
])
def test_transfer_rejects_malformed_or_oversized(trial_value):
    with pytest.raises(ValueError):
        validate_transfer_evidence(
            transfer_manifest(trials=[trial(**trial_value)]), now=NOW)


@pytest.mark.parametrize('snapshot_change', [
    {'trials': []},
    {'trials': 'bad'},
    {'trials': [trial()] * 129},
    {'trials': [trial(), trial()]},
    {'source_ref': 'bad\nref'},
    {'observed_at': NOW.replace(tzinfo=None).isoformat()},
    {'observed_at': 'not-a-date'},
    {'raw_transfer_dataset': SECRET},
])
def test_transfer_manifest_rejects_malformed_or_oversized(snapshot_change):
    with pytest.raises(ValueError):
        validate_transfer_evidence(transfer_manifest(**snapshot_change), now=NOW)


def test_transfer_manifest_rejects_extra_snapshot_fields():
    with pytest.raises(ValueError):
        validate_transfer_evidence(transfer_manifest(finetune=True), now=NOW)


def test_transfer_result_does_not_echo_private_raw_content():
    result = validate_transfer_evidence(transfer_manifest(), now=NOW)
    assert SECRET not in json.dumps(result)


# Registration ----------------------------------------------------------------

@pytest.mark.parametrize('registrations,module_registrations,capability_id', [
    (evaluation_registrations, ml_module_registrations, EVALUATION_CAPABILITY_ID),
    (transfer_registrations, generalization_module_registrations, TRANSFER_CAPABILITY_ID),
])
def test_evidence_validator_registration_is_inert(
        registrations, module_registrations, capability_id):
    assert [cap.name for cap, _ in registrations()] == [capability_id]
    capability, handler = next(
        item for item in module_registrations() if item[0].name == capability_id)
    assert isinstance(capability, Capability)
    forged = Capability(capability.name, 'Unapproved shadow descriptor')
    with pytest.raises(ValueError):
        handler(CapabilityRequest(forged, {'snapshot': {}}, None, 'forged'))
    if capability_id == EVALUATION_CAPABILITY_ID:
        live = evaluation_manifest(observed_at=datetime.now(timezone.utc).isoformat())
        invalid = {'snapshot': live, 'train': True}
    else:
        live = transfer_manifest(observed_at=datetime.now(timezone.utc).isoformat())
        invalid = {'snapshot': live, 'finetune': True}
    outcome = handler(CapabilityRequest(
        capability, {'snapshot': live}, None, 'authorized offline fixture'))
    assert outcome['effect'] == 'none'
    assert outcome['sdk_protocol'] == '1.0'
    with pytest.raises(ValueError):
        handler(CapabilityRequest(capability, invalid, None, 'invalid'))
