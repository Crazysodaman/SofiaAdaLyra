from datetime import datetime, timezone
from hashlib import sha256

import pytest

from sofia.ops import (
    InstallAuthority, InstallOperation, InstallOutcome, OfflineArtifactCache,
    PlatformArtifact, PlatformInstallCoordinator, PlatformInstallPlan,
    PlatformInstallReceipt, PlatformInstallStore, PlatformKind, RecoveryBundle,
)


NOW = datetime(2026, 10, 10, 9, tzinfo=timezone.utc)
pytestmark = pytest.mark.pkg_ops


def artifact(tmp_path, *, platform=PlatformKind.LINUX):
    source = tmp_path / "sofia.whl"
    source.write_bytes(b"signed-sofia-wheel")
    digest = sha256(source.read_bytes()).hexdigest()
    value = PlatformArtifact(
        "sofia", "1.2.3", platform, "x86_64", digest,
        "release-key-1", True, "signed-release",
    )
    return value, source


def plan(value, **overrides):
    fields = dict(
        plan_id="install-1", host_id="artemis", artifact=value,
        operation=InstallOperation.INSTALL,
        authority=InstallAuthority.OPERATOR_APPROVED,
        approval_id="approval-1", previous_version=None, requested_at=NOW,
    )
    fields.update(overrides)
    return PlatformInstallPlan(**fields)


def test_offline_cache_rejects_corruption_and_enforces_budget(tmp_path):
    value, source = artifact(tmp_path)
    cache = OfflineArtifactCache(tmp_path / "cache", max_bytes=100)
    cached = cache.import_artifact(value, source)
    assert cached.name == value.sha256
    assert cache.resolve(value) == cached

    source.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="approved SHA-256"):
        cache.import_artifact(value, source)

    other = tmp_path / "other.whl"
    other.write_bytes(b"x" * 200)
    other_artifact = PlatformArtifact(
        "other", "1", PlatformKind.LINUX, "x86_64",
        sha256(other.read_bytes()).hexdigest(), "release-key-1", True, "release",
    )
    with pytest.raises(RuntimeError, match="resource limit"):
        cache.import_artifact(other_artifact, other)


def test_install_requires_authority_and_operator_approval_id(tmp_path):
    value, _source = artifact(tmp_path)
    with pytest.raises(PermissionError, match="explicit authority"):
        plan(value, authority=InstallAuthority.NONE)
    with pytest.raises(PermissionError, match="approval_id"):
        plan(value, approval_id=None)


def test_coordinator_requires_matching_verified_receipt_and_is_idempotent(tmp_path):
    value, source = artifact(tmp_path)
    cache = OfflineArtifactCache(tmp_path / "cache")
    cache.import_artifact(value, source)
    store = PlatformInstallStore(tmp_path / "sofia.db")
    coordinator = PlatformInstallCoordinator(cache, store)
    calls = []

    class Installer:
        def execute(self, requested, artifact_path):
            calls.append((requested, artifact_path))
            return PlatformInstallReceipt(
                "receipt-1", requested.plan_id, requested.host_id,
                requested.artifact.artifact_id, requested.artifact.version,
                requested.operation, InstallOutcome.SUCCEEDED,
                requested.artifact.sha256, True, True, None, NOW, NOW,
                "service and capability health checks passed",
            )

    requested = plan(value)
    first = coordinator.execute(requested, Installer())
    second = PlatformInstallCoordinator(cache, PlatformInstallStore(store.path)).execute(
        requested, Installer(),
    )
    assert first == second
    assert len(calls) == 1


def test_success_cannot_be_claimed_without_health_and_signature_verification(tmp_path):
    value, _source = artifact(tmp_path)
    with pytest.raises(ValueError, match="signature and health"):
        PlatformInstallReceipt(
            "receipt-1", "install-1", "artemis", "sofia", "1.2.3",
            InstallOperation.INSTALL, InstallOutcome.SUCCEEDED, value.sha256,
            True, False, None, NOW, NOW,
        )


@pytest.mark.parametrize("platform", [PlatformKind.WINDOWS, PlatformKind.LINUX])
def test_recovery_bundle_is_offline_hash_pinned(platform):
    script = RecoveryBundle(
        platform, "python.pkg", "a" * 64, "sofia.whl", "b" * 64,
    ).render()
    assert "https://" not in script and "http://" not in script
    assert "a" * 64 in script and "b" * 64 in script
    assert "hash mismatch" in script.casefold() or "sha256sum -c" in script
