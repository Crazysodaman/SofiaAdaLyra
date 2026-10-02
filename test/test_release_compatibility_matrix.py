"""Release/schema/Fleet compatibility matrix acceptance tests."""
from __future__ import annotations

from datetime import datetime, timezone

from sofia.dev.release import ReleaseManifest
from sofia.verify.compatibility_matrix import (
    CompatibilityState,
    ReleaseCompatibilityInputs,
    ReleaseCompatibilityMatrix,
)


NOW = datetime(2026, 10, 2, 22, 0, tzinfo=timezone.utc)
A = "a" * 64
B = "b" * 64
C = "c" * 64
D = "d" * 64
E = "e" * 64
F = "f" * 64
G = "0" * 64
GIT = "1" * 40


def manifest(**overrides) -> ReleaseManifest:
    values = dict(
        release_id="sofia-0.1.0",
        git_revision=GIT,
        application_version="0.1.0",
        python_version="3.12.10",
        dependency_lock_sha256=A,
        sbom_sha256=B,
        provenance_sha256=C,
        state_schema_min=1,
        state_schema_max=2,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        constitution_sha256=D,
        configuration_schema_version=1,
        created_at=NOW,
        artifact_sha256=E,
        model_id="qwen3.5:9b",
        model_sha256=F,
        asset_sha256=(("avatar.glb", A),),
    )
    values.update(overrides)
    return ReleaseManifest(**values)


def observed(**overrides) -> ReleaseCompatibilityInputs:
    values = dict(
        git_revision=GIT,
        application_version="0.1.0",
        python_version="3.12.10",
        dependency_lock_sha256=A,
        sbom_sha256=B,
        provenance_sha256=C,
        state_schema_revision=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        constitution_sha256=D,
        configuration_schema_version=1,
        source_tests_passed=True,
        semantic_integrity_verified=True,
        signature_verified=True,
        lineage_verified=True,
        anti_rollback_verified=True,
        artifact_sha256=E,
        model_id="qwen3.5:9b",
        model_sha256=F,
        asset_sha256=(("avatar.glb", A),),
    )
    values.update(overrides)
    return ReleaseCompatibilityInputs(**values)


def check(result, dimension):
    return next(item for item in result.checks if item.dimension == dimension)


def test_fully_matching_release_is_accepted():
    result = ReleaseCompatibilityMatrix().evaluate(manifest(), observed())
    assert result.accepted
    assert result.failures == ()
    assert check(result, "state_schema").state is CompatibilityState.PASS
    assert check(result, "fleet_protocol").state is CompatibilityState.PASS
    assert check(result, "signature").state is CompatibilityState.PASS


def test_newer_minor_fleet_protocol_is_compatible_with_required_protocol():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(fleet_protocol_version="1.0"),
        observed(fleet_protocol_version="1.3"),
    )
    assert result.accepted
    assert check(result, "fleet_protocol").state is CompatibilityState.PASS


def test_wrong_fleet_major_version_fails_closed():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(fleet_protocol_version="1.0"),
        observed(fleet_protocol_version="2.0"),
    )
    assert not result.accepted
    assert check(result, "fleet_protocol").state is CompatibilityState.FAIL


def test_state_schema_outside_manifest_window_fails_closed():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(state_schema_min=1, state_schema_max=2),
        observed(state_schema_revision=3),
    )
    assert not result.accepted
    assert check(result, "state_schema").state is CompatibilityState.FAIL


def test_wrong_artifact_digest_is_rejected():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(artifact_sha256=E),
        observed(artifact_sha256=G),
    )
    assert not result.accepted
    assert check(result, "artifact").state is CompatibilityState.FAIL


def test_missing_required_model_digest_is_explicit_unknown_and_rejects():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(model_sha256=F),
        observed(model_sha256=None),
    )
    assert not result.accepted
    model = check(result, "model_digest")
    assert model.required is True
    assert model.state is CompatibilityState.UNKNOWN


def test_model_without_manifest_digest_is_warning_not_fake_verification():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(model_sha256=None),
        observed(model_sha256=None),
    )
    assert result.accepted
    model = check(result, "model_digest")
    assert model.required is False
    assert model.state is CompatibilityState.UNKNOWN
    assert model in result.warnings


def test_missing_or_mismatched_manifest_asset_fails_closed():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(asset_sha256=(("avatar.glb", A), ("voice.model", B))),
        observed(asset_sha256=(("avatar.glb", A),)),
    )
    assert not result.accepted
    assert check(result, "assets").state is CompatibilityState.FAIL


def test_trust_evidence_is_consumed_not_recomputed():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(),
        observed(signature_verified=False),
    )
    assert not result.accepted
    assert check(result, "signature").state is CompatibilityState.FAIL


def test_dependency_and_provenance_mismatch_are_independent_failures():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(),
        observed(
            dependency_lock_sha256=G,
            provenance_sha256=G,
        ),
    )
    assert not result.accepted
    assert check(result, "dependency_lock").state is CompatibilityState.FAIL
    assert check(result, "provenance").state is CompatibilityState.FAIL


def test_unpinned_optional_artifact_is_visible_as_warning():
    result = ReleaseCompatibilityMatrix().evaluate(
        manifest(artifact_sha256=None),
        observed(artifact_sha256=None),
    )
    assert result.accepted
    artifact = check(result, "artifact")
    assert artifact.required is False
    assert artifact.state is CompatibilityState.UNKNOWN
