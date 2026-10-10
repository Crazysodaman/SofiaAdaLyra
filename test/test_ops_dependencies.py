from datetime import datetime, timezone

import pytest

from sofia.ops.dependencies import (
    DependencyEvidenceStore, DependencyHealth, DependencyObservation,
    DependencyTier, default_dependency_registry,
)


NOW = datetime(2026, 10, 10, 8, tzinfo=timezone.utc)
pytestmark = pytest.mark.pkg_ops


def test_registry_resolves_required_and_enabled_platform_features():
    registry = default_dependency_registry()
    linux = registry.resolve(platform="linux", enabled_features={"fleet.agent"})
    identifiers = {item.dependency_id for item in linux}

    assert {"runtime.python", "runtime.sofia", "security.cryptography"} <= identifiers
    assert "fleet.linux-service" in identifiers
    assert "fleet.windows-service" not in identifiers
    assert "creative.blender" not in identifiers


def test_optional_dependencies_are_explicit_not_silently_required():
    registry = default_dependency_registry()
    normal = registry.resolve(platform="windows", enabled_features={"creative.3d"})
    expanded = registry.resolve(
        platform="windows", enabled_features={"creative.3d"},
        include_optional=True,
    )

    assert all(item.tier is not DependencyTier.OPTIONAL for item in normal)
    assert "creative.blender" in {item.dependency_id for item in expanded}


def test_absent_health_evidence_is_unknown_and_observations_survive_restart(tmp_path):
    state = tmp_path / "sofia.db"
    registry = default_dependency_registry()
    store = DependencyEvidenceStore(state)
    projection = {
        item["dependency_id"]: item for item in store.projection("venus", registry)
    }
    assert projection["runtime.python"]["status"] == "unknown"

    observation = DependencyObservation(
        host_id="venus", dependency_id="runtime.python",
        status=DependencyHealth.HEALTHY, observed_version="3.12.12",
        source="fleet-agent:system.inspect", observed_at=NOW,
        artifact_sha256="a" * 64, signature_verified=True,
        detail="verified runtime probe",
    )
    sequence = store.record(observation)

    assert sequence == 1
    assert DependencyEvidenceStore(state).latest("venus", "runtime.python") == observation
    assert DependencyEvidenceStore(state).latest("artemis", "runtime.python") is None


def test_dependency_observation_rejects_naive_time_and_invalid_hash():
    with pytest.raises(ValueError, match="timezone-aware"):
        DependencyObservation(
            "venus", "runtime.python", DependencyHealth.HEALTHY,
            "3.12", "probe", datetime(2026, 10, 10),
        )
    with pytest.raises(ValueError, match="SHA-256"):
        DependencyObservation(
            "venus", "runtime.python", DependencyHealth.HEALTHY,
            "3.12", "probe", NOW, artifact_sha256="not-a-hash",
        )
