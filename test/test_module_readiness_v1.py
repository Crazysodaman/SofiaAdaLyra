from dataclasses import replace
from datetime import datetime, timezone

import pytest

from sofia.platform.modules import (
    ModuleLifecycle,
    ModuleLifecycleRecord,
    PlatformReadiness,
    ReadinessEvidence,
    ReadinessEvidenceKind,
    ReadinessEvidenceStore,
    evaluate_module_readiness,
)
from test.test_module_package_v1 import manifest


NOW = datetime(2026, 10, 23, 1, tzinfo=timezone.utc)
SOURCE = "a" * 40


def lifecycle(value, *, state=ModuleLifecycle.STAGED):
    return ModuleLifecycleRecord(
        value.module_id, value.version, value.package_identity_digest(), state,
        1, None, "/staged", "verified package staged", NOW,
    )


def evidence(value, kind, *, passed=True, suffix="one"):
    return ReadinessEvidence(
        f"evidence:{kind.value}:{suffix}", value.module_id,
        value.package_identity_digest(), SOURCE, kind, "verifier:owner-ci",
        passed, NOW, f"receipt:{kind.value}:{suffix}",
    )


def test_readiness_requires_exact_revision_and_never_authorizes_activation():
    value = manifest((("module.py", "0" * 64),))
    records = tuple(evidence(value, kind) for kind in ReadinessEvidenceKind)
    report = evaluate_module_readiness(
        value, lifecycle(value), records, source_sha=SOURCE,
    )
    assert report.status is PlatformReadiness.PRODUCTION_READY
    assert report.activation_authorized is False
    stale = evaluate_module_readiness(
        value, lifecycle(value), records, source_sha="b" * 40,
    )
    assert stale.status is PlatformReadiness.BETA
    assert stale.satisfied == ()


def test_health_or_lifecycle_alone_is_not_release_readiness():
    value = manifest((("module.py", "0" * 64),))
    active = lifecycle(value, state=ModuleLifecycle.ACTIVE)
    report = evaluate_module_readiness(value, active, (), source_sha=SOURCE)
    assert report.status is PlatformReadiness.BETA
    assert report.health_is_not_readiness is True


def test_module_cannot_self_certify():
    value = manifest((("module.py", "0" * 64),))
    with pytest.raises(PermissionError, match="cannot certify itself"):
        replace(
            evidence(value, ReadinessEvidenceKind.TEST),
            issuer=f"module:{value.module_id}",
        )


def test_evidence_is_durable_idempotent_and_revocation_blocks_certification(
    canonical_state_path,
):
    value = manifest((("module.py", "0" * 64),))
    store = ReadinessEvidenceStore(
        canonical_state_path, trusted_issuers=frozenset({"verifier:owner-ci"}),
    )
    records = []
    for kind in ReadinessEvidenceKind:
        records.append(store.record(evidence(value, kind)))
    restarted = ReadinessEvidenceStore(
        canonical_state_path, trusted_issuers=frozenset({"verifier:owner-ci"}),
    )
    assert restarted.record(records[0]) == records[0]
    restarted.revoke(
        records[0].evidence_id, issuer=records[0].issuer,
        reason="test environment invalidated", now=NOW,
    )
    report = evaluate_module_readiness(
        value, lifecycle(value), restarted.for_module(value.module_id),
        source_sha=SOURCE,
    )
    assert report.status is PlatformReadiness.BLOCKED
    assert "certification evidence was revoked" in report.reasons


def test_untrusted_issuer_cannot_enter_readiness_store(canonical_state_path):
    value = manifest((("module.py", "0" * 64),))
    store = ReadinessEvidenceStore(
        canonical_state_path, trusted_issuers=frozenset({"verifier:owner-ci"}),
    )
    forged = replace(
        evidence(value, ReadinessEvidenceKind.TEST), issuer="attacker:claimed-ci",
    )
    with pytest.raises(PermissionError, match="not trusted"):
        store.record(forged)


def test_failed_exact_revision_evidence_blocks_readiness():
    value = manifest((("module.py", "0" * 64),))
    report = evaluate_module_readiness(
        value, lifecycle(value),
        (evidence(value, ReadinessEvidenceKind.SECURITY_AUDIT, passed=False),),
        source_sha=SOURCE,
    )
    assert report.status is PlatformReadiness.BLOCKED


def test_readiness_rejects_non_revision_source_identity():
    value = manifest((("module.py", "0" * 64),))
    with pytest.raises(ValueError, match="source_sha"):
        evaluate_module_readiness(value, lifecycle(value), (), source_sha="main")
