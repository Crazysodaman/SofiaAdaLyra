"""Validate supplied change manifests and test evidence without Git or execution.

Capability performs bounded analysis of supplied, UNVERIFIED projections only.
No repository access, Git invocation, code execution, test execution or
persistence. Existing Sofía V18 owner components retain control of real work.
"""
from __future__ import annotations
from datetime import datetime, timezone
import re
from typing import Mapping
from sofia.sdk.contracts import SDK_PROTOCOL_VERSION
from sofia.platform.capability.model import Capability, CapabilityRequest

MODULE_ID = 'MOD-DEV'
MODULE_VERSION = '0.1.0'
CAPABILITY_ID = 'dev.validate_change_manifest.v1'
PROFILE = 'ADVISORY'
RESOURCES = (('cpu_millicores', 75), ('ram_mib', 48), ('gpu_mib', 0))

_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,119}$')
_DIGEST = re.compile(r'^[0-9a-f]{64}$')
_SNAPSHOT_FIELDS = frozenset({'source_ref', 'observed_at', 'changes', 'test_evidence'})
_CHANGE_FIELDS = frozenset({
    'change_id', 'path', 'operation', 'added_lines', 'removed_lines',
    'diff_sha256', 'protected',
})
_TEST_FIELDS = frozenset({
    'test_id', 'status', 'evidence_sha256', 'covers_change_refs',
})
_MAX_CHANGES = 128
_MAX_TESTS = 128
_MAX_LINES = 1_000_000
_MAX_COVERS = 32


def _exact(item: object, keys: frozenset[str]) -> Mapping[str, object]:
    if not isinstance(item, Mapping) or set(item) != keys:
        raise ValueError('unexpected fields in supplied change manifest')
    return item


def _identity(value: object, label: str = 'id') -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise ValueError('invalid ' + label)
    return value


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _DIGEST.fullmatch(value) is None:
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


def _repository_path(value: object) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 220:
        raise ValueError('invalid repository-relative path')
    if value.startswith('/') or '\\' in value or '\x00' in value:
        raise ValueError('invalid repository-relative path')
    parts = value.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('invalid repository-relative path')
    if ':' in parts[0]:
        raise ValueError('invalid repository-relative path')
    return value


def _change(item: object) -> dict[str, object]:
    row = _exact(item, _CHANGE_FIELDS)
    return dict(
        change_id=_identity(row['change_id'], 'change_id'),
        path=_repository_path(row['path']),
        operation=_choice(row['operation'], ('add', 'modify', 'delete'), 'operation'),
        added_lines=_int(row['added_lines'], 0, _MAX_LINES, 'added_lines'),
        removed_lines=_int(row['removed_lines'], 0, _MAX_LINES, 'removed_lines'),
        diff_sha256=_digest(row['diff_sha256'], 'diff_sha256'),
        protected=_bool(row['protected'], 'protected'),
    )


def _test(item: object, change_ids: set[str]) -> dict[str, object]:
    row = _exact(item, _TEST_FIELDS)
    key = _identity(row['test_id'], 'test_id')
    status = _choice(row['status'], ('pass', 'fail', 'skipped', 'error'), 'test status')
    digest = _digest(row['evidence_sha256'], 'evidence_sha256')
    covers = row['covers_change_refs']
    if type(covers) is not list or len(covers) > _MAX_COVERS:
        raise ValueError('covers_change_refs must be a bounded list')
    refs = [_identity(value, 'covered change ref') for value in covers]
    if len(set(refs)) != len(refs):
        raise ValueError('duplicate covered change ref')
    return dict(
        test_id=key,
        status=status,
        evidence_sha256=digest,
        covers_change_refs=refs,
        unknown_change_refs=sorted(set(refs) - change_ids),
    )


def validate_change_manifest(snapshot: Mapping[str, object], *, now: datetime,
                             max_age_seconds: int = 3600) -> dict[str, object]:
    _exact(snapshot, _SNAPSHOT_FIELDS)
    source = _identity(snapshot['source_ref'], 'source_ref')
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError('timezone-aware now required')
    _int(max_age_seconds, 1, 86400, 'max_age_seconds')
    observed = _timestamp(snapshot['observed_at'])
    changes = snapshot['changes']
    if type(changes) is not list or not 1 <= len(changes) <= _MAX_CHANGES:
        raise ValueError('changes must be a bounded non-empty list')
    change_rows = [_change(item) for item in changes]
    change_ids = [row['change_id'] for row in change_rows]
    if len(set(change_ids)) != len(change_ids):
        raise ValueError('duplicate change identity')
    paths = [row['path'] for row in change_rows]
    if len(set(paths)) != len(paths):
        raise ValueError('duplicate change path')
    tests = snapshot['test_evidence']
    if type(tests) is not list or len(tests) > _MAX_TESTS:
        raise ValueError('test_evidence must be a bounded list')
    test_rows = [_test(item, set(change_ids)) for item in tests]
    test_ids = [row['test_id'] for row in test_rows]
    if len(set(test_ids)) != len(test_ids):
        raise ValueError('duplicate test identity')

    age = (now.astimezone(timezone.utc) - observed).total_seconds()
    freshness = 'future' if age < -5 else 'stale' if age > max_age_seconds else 'fresh'
    base = dict(
        schema='sofia.development.change_manifest_validation.v1',
        module_id=MODULE_ID,
        sdk_protocol=str(SDK_PROTOCOL_VERSION),
        source_ref=source,
        observed_at=observed.isoformat(),
        freshness=freshness,
        evidence_class='supplied_unverified',
        effect='none',
        action_authorized=False,
        data_persisted=False,
        git_executed=False,
        code_executed=False,
        test_runner_invoked=False,
        diff_content_returned=False,
        source_authenticity_verified=False,
    )
    if freshness != 'fresh':
        return base | dict(
            status='unknown',
            inspected_change_count=None,
            inspected_test_count=None,
            findings=['change_manifest_timestamp_invalid'],
            changes=[],
            tests=[],
        )

    passing_covers: set[str] = set()
    for row in test_rows:
        if row['status'] == 'pass':
            passing_covers.update(row['covers_change_refs'])

    results = []
    for row in change_rows:
        reasons = []
        if row['protected']:
            reasons.append('protected_path_requires_separate_approval')
        if row['change_id'] not in passing_covers:
            reasons.append('missing_passing_test_evidence')
        results.append(dict(
            change_id=row['change_id'],
            path=row['path'],
            operation=row['operation'],
            diff_sha256=row['diff_sha256'],
            finding='hold' if reasons else 'review_eligible',
            reasons=reasons,
        ))

    findings = {reason for row in results for reason in row['reasons']}
    if not test_rows:
        findings.add('missing_test_evidence')
    if any(row['unknown_change_refs'] for row in test_rows):
        findings.add('test_evidence_references_unknown_change')
    ordered = sorted(findings)
    return base | dict(
        status='validated_change_manifest' if not ordered else 'validated_with_findings',
        inspected_change_count=len(results),
        inspected_test_count=len(test_rows),
        findings=ordered,
        changes=results,
        tests=test_rows,
    )


def capability_registrations():
    capability = Capability(
        CAPABILITY_ID,
        'Validate supplied change manifest and test evidence; never run Git or code.',
    )

    def handler(request: CapabilityRequest):
        if (not isinstance(request, CapabilityRequest)
                or request.capability != capability
                or set(request.parameters) != {'snapshot'}):
            raise ValueError('invalid change manifest capability request')
        return validate_change_manifest(
            request.parameters['snapshot'], now=datetime.now(timezone.utc))

    return ((capability, handler),)
