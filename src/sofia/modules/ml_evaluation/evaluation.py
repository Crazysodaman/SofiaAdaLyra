"""Validate supplied evaluation evidence with split, leakage and baseline checks.

Capability performs bounded analysis of supplied, UNVERIFIED projections only.
No dataset download, training, inference, tuning or release authority.
Existing Sofía V18 owner components retain control of all real operations.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-ML'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'ml.validate_evaluation_evidence.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))

_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_SNAPSHOT_FIELDS = frozenset({'source_ref', 'observed_at', 'evaluations'})
_EVALUATION_FIELDS = frozenset({
    'evaluation_id', 'split_kind', 'tp', 'fp', 'tn', 'fn',
    'leakage_check_passed', 'baseline_ref', 'baseline_f1',
})
_SPLITS = ('train', 'validation', 'holdout')
_MAX_COUNT = 10_000_000
_MAX_EVALUATIONS = 128


def _exact(item: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(item, Mapping) or set(item) != keys:
        raise ValueError('unexpected fields in supplied evaluation evidence')
    return item


def _identity(value: object, label: str = 'id') -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError('invalid ' + label)
    return value


def _num(value: object, lo: float, hi: float, name: str = 'number') -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError('invalid ' + name)
    return float(value)


def _int(value: object, lo: int, hi: int, name: str = 'integer') -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError('invalid ' + name)
    return value


def _bool(value: object, name: str = 'flag') -> bool:
    if type(value) is not bool:
        raise ValueError('invalid ' + name)
    return value


def _choice(value: object, options: tuple[str, ...], label: str = 'choice') -> str:
    if type(value) is not str or value not in options:
        raise ValueError('invalid ' + label)
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


def _evaluation(item: object) -> dict[str, object]:
    row = _exact(item, _EVALUATION_FIELDS)
    key = _identity(row['evaluation_id'], 'evaluation_id')
    split = _choice(row['split_kind'], _SPLITS, 'split_kind')
    tp = _int(row['tp'], 0, _MAX_COUNT, 'tp')
    fp = _int(row['fp'], 0, _MAX_COUNT, 'fp')
    tn = _int(row['tn'], 0, _MAX_COUNT, 'tn')
    fn = _int(row['fn'], 0, _MAX_COUNT, 'fn')
    leakage = _bool(row['leakage_check_passed'], 'leakage_check_passed')
    baseline_ref = _identity(row['baseline_ref'], 'baseline_ref')
    baseline_f1 = _num(row['baseline_f1'], 0, 1, 'baseline_f1')

    total = tp + fp + tn + fn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = None
    if precision is not None and recall is not None and precision + recall:
        f1 = 2 * precision * recall / (precision + recall)

    reasons = []
    if split != 'holdout':
        reasons.append('not_independent_holdout')
    if not leakage:
        reasons.append('leakage_check_failed')
    if total == 0:
        reasons.append('no_evaluation_samples')
    if f1 is None:
        reasons.append('metric_undefined')
    elif f1 <= baseline_f1:
        reasons.append('baseline_not_beaten')
    return dict(
        evaluation_id=key,
        split_kind=split,
        total=total,
        precision=precision,
        recall=recall,
        f1=f1,
        baseline_ref=baseline_ref,
        baseline_f1=baseline_f1,
        leakage_check_passed=leakage,
        finding='reviewable_holdout' if not reasons else 'evaluation_hold',
        reasons=reasons,
        release_verified=False,
    )


def validate_evaluation_evidence(snapshot: Mapping[str, object], *, now: datetime,
                                 max_age_seconds: int = 3600) -> dict[str, object]:
    _exact(snapshot, _SNAPSHOT_FIELDS)
    source = _identity(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    observed = _timestamp(snapshot['observed_at'])
    evaluations = snapshot['evaluations']
    if type(evaluations) is not list or not 1 <= len(evaluations) <= _MAX_EVALUATIONS:
        raise ValueError('evaluations must be a bounded non-empty list')
    rows = [_evaluation(item) for item in evaluations]
    ids = [row['evaluation_id'] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate evaluation identity')

    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = dict(
        schema='sofia.ml_evaluation.evaluation_evidence_validation.v1',
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
        dataset_downloaded=False,
        hyperparameters_tuned=False,
        release_verified=False,
    )
    if freshness != 'fresh':
        return base | dict(
            status='unknown',
            inspected_evaluation_count=None,
            findings=['evaluation_evidence_timestamp_invalid'],
            evaluations=[],
        )
    findings = sorted({reason for row in rows for reason in row['reasons']})
    return base | dict(
        status='validated_evaluation_evidence' if not findings else 'validated_with_findings',
        inspected_evaluation_count=len(rows),
        findings=findings,
        evaluations=rows,
    )


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate supplied evaluation split, leakage and baseline evidence; never train or infer.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid evaluation evidence capability request')
        return validate_evaluation_evidence(
            request.parameters['snapshot'], now=datetime.now(timezone.utc))

    return ((capability, handler),)
