"""Validate supplied independent review evidence without self-certification.

Capability performs bounded analysis of supplied, UNVERIFIED projections only.
No grading of Sofía identity, execution, persistence or authority transfer.
Existing Sofía V18 owner components retain control of all real operations.
"""
from __future__ import annotations
from datetime import datetime, timezone
import math
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-MENTOR'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'mentor.validate_review_evidence.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))

_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_DIGEST = re.compile(r'^[0-9a-f]{64}$')
_SNAPSHOT_FIELDS = frozenset({'source_ref', 'observed_at', 'reviews'})
_REVIEW_FIELDS = frozenset({
    'review_id', 'reviewer_ref', 'subject_ref', 'criterion', 'score',
    'maximum', 'evidence_sha256', 'self_certified',
})
_CRITERIA = ('correctness', 'grounding', 'coherence', 'personality', 'safety', 'agency')
_MAX_REVIEWS = 128


def _exact(item: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(item, Mapping) or set(item) != keys:
        raise ValueError('unexpected fields in supplied review evidence')
    return item


def _identity(value: object, label: str = 'id') -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError('invalid ' + label)
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
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


def _review(item: object) -> dict[str, object]:
    row = _exact(item, _REVIEW_FIELDS)
    key = _identity(row['review_id'], 'review_id')
    reviewer = _identity(row['reviewer_ref'], 'reviewer_ref')
    subject = _identity(row['subject_ref'], 'subject_ref')
    criterion = _choice(row['criterion'], _CRITERIA, 'criterion')
    maximum = _num(row['maximum'], 1, 100, 'maximum')
    score = _num(row['score'], 0, maximum, 'score')
    digest = _digest(row['evidence_sha256'], 'evidence_sha256')
    self_certified = _bool(row['self_certified'], 'self_certified')

    reasons = []
    if self_certified:
        reasons.append('self_certification_rejected')
    if reviewer == subject:
        reasons.append('reviewer_subject_identity_conflict')
    return dict(
        review_id=key,
        reviewer_ref=reviewer,
        subject_ref=subject,
        criterion=criterion,
        normalized_score=score / maximum,
        evidence_sha256=digest,
        self_certified=self_certified,
        finding='eligible_independent_review' if not reasons else 'not_independent',
        reasons=reasons,
    )


def validate_review_evidence(snapshot: Mapping[str, object], *, now: datetime,
                             max_age_seconds: int = 3600) -> dict[str, object]:
    _exact(snapshot, _SNAPSHOT_FIELDS)
    source = _identity(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    observed = _timestamp(snapshot['observed_at'])
    reviews = snapshot['reviews']
    if type(reviews) is not list or not 1 <= len(reviews) <= _MAX_REVIEWS:
        raise ValueError('reviews must be a bounded non-empty list')
    rows = [_review(item) for item in reviews]
    ids = [row['review_id'] for row in rows]
    if len(set(ids)) != len(ids):
        raise ValueError('duplicate review identity')
    combos = [
        (row['reviewer_ref'], row['subject_ref'], row['criterion']) for row in rows
    ]
    if len(set(combos)) != len(combos):
        raise ValueError('duplicate review criterion for reviewer and subject')

    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = dict(
        schema='sofia.mentor_review.review_evidence_validation.v1',
        module_id=MODULE_ID,
        sdk_protocol=str(SDK_PROTOCOL_VERSION),
        source_ref=source,
        observed_at=observed.isoformat(),
        freshness=freshness,
        evidence_class='supplied_unverified',
        effect='none',
        action_authorized=False,
        data_persisted=False,
        identity_graded=False,
        self_certification_accepted=False,
        review_authenticity_verified=False,
    )
    if freshness != 'fresh':
        return base | dict(
            status='unknown',
            inspected_review_count=None,
            findings=['review_evidence_timestamp_invalid'],
            reviews=[],
        )
    findings = sorted({reason for row in rows for reason in row['reasons']})
    return base | dict(
        status='validated_review_evidence' if not findings else 'validated_with_findings',
        inspected_review_count=len(rows),
        findings=findings,
        reviews=rows,
    )


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate supplied independent review evidence; reject self-certification.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid review evidence capability request')
        return validate_review_evidence(
            request.parameters['snapshot'], now=datetime.now(timezone.utc))

    return ((capability, handler),)
