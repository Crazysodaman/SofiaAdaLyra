"""Validate supplied transfer trial evidence without training or inference.

Capability performs bounded analysis of supplied, UNVERIFIED projections only.
No model modification, training, inference, dataset access or AGI claim.
Existing Sofía V18 owner components retain control of all real operations.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-GENERALIZATION'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'generalization.validate_transfer_evidence.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))

_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_SNAPSHOT_FIELDS = frozenset({'source_ref', 'observed_at', 'trials'})
_TRIAL_FIELDS = frozenset({
    'trial_id', 'task_ref', 'baseline_successes', 'candidate_successes',
    'trial_count', 'novel_task', 'independent_holdout', 'leakage_check_passed',
})
_MAX_TRIALS = 128
_MAX_TRIAL_COUNT = 100_000


def _exact(item: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(item, Mapping) or set(item) != keys:
        raise ValueError('unexpected fields in supplied transfer evidence')
    return item


def _identity(value: object, label: str = 'id') -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError('invalid ' + label)
    return value


def _int(value: object, lo: int, hi: int, name: str = 'integer') -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('invalid ' + name)
    return value


def _bool(value: object, name: str = 'flag') -> bool:
    if type(value) is not bool:
        raise ValueError('invalid ' + name)
    return value


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError('timestamp required')
    try:
        date = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError('invalid timestamp') from exc
    if date.tzinfo is None or date.utcoffset() is None:
        raise ValueError('timestamp requires timezone')
    return date.astimezone(timezone.utc)


def _trial(item: object) -> dict[str, object]:
    row = _exact(item, _TRIAL_FIELDS)
    key = _identity(row['trial_id'], 'trial_id')
    task = _identity(row['task_ref'], 'task_ref')
    n = _int(row['trial_count'], 1, _MAX_TRIAL_COUNT, 'trial_count')
    baseline = _int(row['baseline_successes'], 0, n, 'baseline_successes')
    candidate = _int(row['candidate_successes'], 0, n, 'candidate_successes')
    novel = _bool(row['novel_task'], 'novel_task')
    independent = _bool(row['independent_holdout'], 'independent_holdout')
    leakage = _bool(row['leakage_check_passed'], 'leakage_check_passed')

    reasons = []
    if not novel:
        reasons.append('not_novel_task')
    if not independent:
        reasons.append('not_independent_transfer')
    if not leakage:
        reasons.append('leakage_check_failed')
    if candidate <= baseline:
        reasons.append('baseline_not_beaten')
    return dict(
        trial_id=key,
        task_ref=task,
        trial_count=n,
        baseline_successes=baseline,
        candidate_successes=candidate,
        delta_success_rate=(candidate - baseline) / n,
        novel_task=novel,
        independent_holdout=independent,
        leakage_check_passed=leakage,
        finding='candidate_transfer_evidence' if not reasons else 'transfer_hold',
        reasons=reasons,
        generalized_intelligence_verified=False,
    )


def validate_transfer_evidence(snapshot: Mapping[str, object], *, now: datetime,
                               max_age_seconds: int = 3600) -> dict[str, object]:
    _exact(snapshot, _SNAPSHOT_FIELDS)
    source = _identity(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    observed = _timestamp(snapshot['observed_at'])
    trials = snapshot['trials']
    if type(trials) is not list or not 1 <= len(trials) <= _MAX_TRIALS:
        raise ValueError('trials must be a bounded non-empty list')
    rows = [_trial(item) for item in trials]
    ids = [row['trial_id'] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate trial identity')

    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = dict(
        schema='sofia.generalization.transfer_evidence_validation.v1',
        module_id=MODULE_ID,
        sdk_protocol=str(SDK_PROTOCOL_VERSION),
        source_ref=source,
        observed_at=observed.isoformat(),
        freshness=freshness,
        evidence_class='supplied_unverified',
        effect='none',
        action_authorized=False,
        data_persisted=False,
        training_executed=False,
        inference_executed=False,
        model_modified=False,
        generalized_intelligence_verified=False,
    )
    if freshness != 'fresh':
        return base | dict(
            status='unknown',
            inspected_trial_count=None,
            findings=['transfer_evidence_timestamp_invalid'],
            trials=[],
        )
    findings = sorted({reason for row in rows for reason in row['reasons']})
    return base | dict(
        status='validated_transfer_evidence' if not findings else 'validated_with_findings',
        inspected_trial_count=len(rows),
        findings=findings,
        trials=rows,
    )


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate supplied transfer trial evidence; never train, infer or claim AGI.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid transfer evidence capability request')
        return validate_transfer_evidence(
            request.parameters['snapshot'], now=datetime.now(timezone.utc))

    return ((capability, handler),)
