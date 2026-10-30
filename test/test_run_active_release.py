from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import zipfile

import pytest

from sofia.platform.dev.release import ReleaseManifest
from sofia.platform.dev.release_store import ReleaseStateStore
from sofia.platform.run.active_release import (
    ActiveReleaseError,
    ActiveReleaseResolver,
    ReleaseEnvironmentManager,
)
from sofia.platform.run.release import directory_sha256
from sofia.platform.safe.release import ReleaseActivationEvidence
from sofia.platform.state.sqlite_plane import SQLiteStatePlane
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite


NOW = datetime(2026, 10, 3, 4, 0, tzinfo=timezone.utc)


def make_wheel(root: Path) -> Path:
    wheel = root / "sofia_ada_lyra-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("sofia/__init__.py", "")
        archive.writestr(
            "sofia_ada_lyra-0.1.0.dist-info/METADATA",
            "Name: sofia-ada-lyra\nVersion: 0.1.0\n",
        )
        archive.writestr(
            "sofia_ada_lyra-0.1.0.dist-info/RECORD",
            "",
        )
    return wheel


def active_release_fixture(tmp_path: Path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    plane = SQLiteStatePlane(state)
    store = ReleaseStateStore(plane)

    release_root = tmp_path / "release-runtime"
    artifact = release_root / "releases" / "release-1"
    artifact.mkdir(parents=True)
    make_wheel(artifact)
    lock = b"cryptography==50.0.2 --hash=sha256:" + (b"a" * 64) + b"\n"
    (artifact / "requirements.lock").write_bytes(lock)
    artifact_digest = directory_sha256(artifact)

    manifest = ReleaseManifest(
        release_id="release-1",
        git_revision="1" * 40,
        application_version="0.1.0",
        python_version="3.12.10",
        dependency_lock_sha256=sha256(lock).hexdigest(),
        sbom_sha256="2" * 64,
        provenance_sha256="3" * 64,
        verification_evidence_sha256="5" * 64,
        verification_phase="full",
        state_schema_min=1,
        state_schema_max=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        constitution_sha256="4" * 64,
        configuration_schema_version=1,
        created_at=NOW,
        artifact_sha256=artifact_digest,
    )
    evidence = ReleaseActivationEvidence(
        release_id=manifest.release_id,
        manifest_sha256=manifest.manifest_sha256,
        signer_key_id="test",
        signature_verified=True,
        lineage_verified=True,
        anti_rollback_verified=True,
        verified_at=NOW,
    )
    store.activate(manifest, evidence)
    pointer = {
        "release_id": manifest.release_id,
        "manifest_sha256": manifest.manifest_sha256,
        "path": str(artifact.resolve()),
        "previous_release_id": None,
        "verified_at": NOW.isoformat(),
    }
    (release_root / "active-release.json").write_text(
        json.dumps(pointer),
        encoding="utf-8",
    )
    return state, release_root, artifact, manifest


def test_resolver_binds_authoritative_state_pointer_and_artifact(tmp_path):
    state, release_root, artifact, manifest = active_release_fixture(tmp_path)

    resolved = ActiveReleaseResolver(
        state_path=state,
        release_root=release_root,
    ).resolve()

    assert resolved is not None
    assert resolved.release_id == manifest.release_id
    assert resolved.manifest_sha256 == manifest.manifest_sha256
    assert resolved.artifact_sha256 == manifest.artifact_sha256
    assert resolved.artifact_path == artifact.resolve()
    assert resolved.wheel_path.name.endswith(".whl")
    assert resolved.dependency_lock_path.name == "requirements.lock"


def test_resolver_rejects_tampered_active_artifact(tmp_path):
    state, release_root, artifact, _ = active_release_fixture(tmp_path)
    (artifact / "requirements.lock").write_text(
        "tampered",
        encoding="utf-8",
    )

    with pytest.raises(ActiveReleaseError, match="artifact digest"):
        ActiveReleaseResolver(
            state_path=state,
            release_root=release_root,
        ).resolve()


def test_resolver_rejects_pointer_to_another_path(tmp_path):
    state, release_root, _, _ = active_release_fixture(tmp_path)
    pointer_path = release_root / "active-release.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["path"] = str(tmp_path / "elsewhere")
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(ActiveReleaseError, match="pointer path mismatch"):
        ActiveReleaseResolver(
            state_path=state,
            release_root=release_root,
        ).resolve()


def test_environment_manager_reuses_only_matching_stamped_environment(
    tmp_path,
    monkeypatch,
):
    state, release_root, _, _ = active_release_fixture(tmp_path)
    release = ActiveReleaseResolver(
        state_path=state,
        release_root=release_root,
    ).resolve()
    assert release is not None

    class FakeBuilder:
        def __init__(self, **kwargs):
            pass

        def create(self, root):
            python = ReleaseEnvironmentManager._python(Path(root))
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_bytes(b"python")

    monkeypatch.setattr(
        "sofia.platform.run.active_release.venv.EnvBuilder",
        FakeBuilder,
    )
    manager = ReleaseEnvironmentManager(
        release_root=release_root,
    )

    calls = []

    def fake_run(argv, *, timeout=600):
        calls.append(tuple(argv))
        if "-c" in argv:
            return release.application_version
        return ""

    monkeypatch.setattr(manager, "_run", fake_run)

    first = manager.ensure(release)
    count_after_first = len(calls)
    second = manager.ensure(release)

    assert first.root == second.root
    assert first.python_path.is_file()
    assert len(calls) == count_after_first


def component_release_fixture(
    tmp_path: Path,
    wheels: dict[str, Path],
    *,
    mutate=None,
):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    plane = SQLiteStatePlane(state)
    store = ReleaseStateStore(plane)

    release_root = tmp_path / "release-runtime"
    artifact = release_root / "releases" / "release-c"
    artifact.mkdir(parents=True)
    for component in ("sdk", "platform", "core"):
        (artifact / wheels[component].name).write_bytes(
            wheels[component].read_bytes()
        )
    if mutate is not None:
        mutate(artifact)
    lock = b"cryptography==50.0.2 --hash=sha256:" + (b"b" * 64) + b"\n"
    (artifact / "requirements.lock").write_bytes(lock)
    artifact_digest = directory_sha256(artifact)

    components = []
    from sofia.platform.verify.component_artifacts import inspect_wheel

    for component, wheel in sorted(wheels.items()):
        report = inspect_wheel(wheel, f"sofia-{component}")
        from sofia.platform.dev.release import ComponentArtifactIdentity

        components.append(
            ComponentArtifactIdentity(
                component=component,
                distribution=f"sofia-{component}",
                version=report.version,
                sha256=report.sha256,
            )
        )
    from sofia.platform.dev.release import ComponentArtifactIdentity as _Identity

    manifest = ReleaseManifest(
        release_id="release-c",
        git_revision="1" * 40,
        application_version="0.1.0",
        python_version="3.12.10",
        dependency_lock_sha256=sha256(lock).hexdigest(),
        sbom_sha256="2" * 64,
        provenance_sha256="3" * 64,
        verification_evidence_sha256="5" * 64,
        verification_phase="full",
        state_schema_min=1,
        state_schema_max=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        constitution_sha256="4" * 64,
        configuration_schema_version=1,
        created_at=NOW,
        artifact_sha256=artifact_digest,
        components=tuple(sorted(components, key=lambda identity: identity.component)),
    )
    evidence = ReleaseActivationEvidence(
        release_id=manifest.release_id,
        manifest_sha256=manifest.manifest_sha256,
        signer_key_id="test",
        signature_verified=True,
        lineage_verified=True,
        anti_rollback_verified=True,
        verified_at=NOW,
    )
    store.activate(manifest, evidence)
    pointer = {
        "release_id": manifest.release_id,
        "manifest_sha256": manifest.manifest_sha256,
        "path": str(artifact.resolve()),
        "previous_release_id": None,
        "verified_at": NOW.isoformat(),
    }
    (release_root / "active-release.json").write_text(
        json.dumps(pointer),
        encoding="utf-8",
    )
    return state, release_root, artifact, manifest


@pytest.fixture(scope="module")
def built_component_wheels(tmp_path_factory) -> dict[str, Path]:
    from sofia.platform.verify.component_artifacts import build_all_components

    return build_all_components(tmp_path_factory.mktemp("resolver-wheels"), repo=ROOT)


ROOT = Path(__file__).resolve().parents[1]


def test_resolver_binds_component_release_wheels(
    tmp_path, built_component_wheels
):
    state, release_root, artifact, manifest = component_release_fixture(
        tmp_path, built_component_wheels
    )
    resolved = ActiveReleaseResolver(
        state_path=state,
        release_root=release_root,
    ).resolve()
    assert resolved is not None
    assert resolved.wheel_path is None
    assert [wheel.name for wheel in resolved.component_wheels] == sorted(
        built_component_wheels[component].name
        for component in ("sdk", "platform", "core")
    )
    assert resolved.artifact_sha256 == manifest.artifact_sha256


def test_resolver_rejects_component_release_with_extra_wheel(
    tmp_path, built_component_wheels
):
    def add_extra(artifact: Path) -> None:
        (artifact / "extra-1.0-py3-none-any.whl").write_bytes(b"not a wheel")

    state, release_root, artifact, _ = component_release_fixture(
        tmp_path,
        built_component_wheels,
        mutate=add_extra,
    )

    with pytest.raises(ActiveReleaseError, match="wheel count mismatch"):
        ActiveReleaseResolver(
            state_path=state,
            release_root=release_root,
        ).resolve()


def test_resolver_rejects_tampered_component_wheel(
    tmp_path, built_component_wheels
):
    core_name = built_component_wheels["core"].name

    def tamper(artifact: Path) -> None:
        core_wheel = artifact / core_name
        core_wheel.write_bytes(core_wheel.read_bytes() + b"\x00tamper")

    state, release_root, artifact, _ = component_release_fixture(
        tmp_path,
        built_component_wheels,
        mutate=tamper,
    )

    with pytest.raises(ActiveReleaseError, match="absent, duplicated or tampered"):
        ActiveReleaseResolver(
            state_path=state,
            release_root=release_root,
        ).resolve()


def test_legacy_then_component_migration_preserves_release_history(
    tmp_path, built_component_wheels
):
    from sofia.platform.dev.release import ComponentArtifactIdentity
    from sofia.platform.verify.component_artifacts import inspect_wheel

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    plane = SQLiteStatePlane(state)
    store = ReleaseStateStore(plane)
    release_root = tmp_path / "release-runtime"
    releases = release_root / "releases"

    legacy = releases / "release-legacy"
    legacy.mkdir(parents=True)
    legacy_lock_bytes = b"cryptography==50.0.2 --hash=sha256:" + (b"a" * 64) + b"\n"
    (legacy / "requirements.lock").write_bytes(legacy_lock_bytes)
    (legacy / "README").write_bytes(b"legacy release tree")
    assert directory_sha256(legacy).isalnum()
    legacy_lock = (legacy / "requirements.lock").read_bytes()
    legacy_manifest = ReleaseManifest(
        release_id="release-legacy",
        git_revision="1" * 40,
        application_version="0.0.9",
        python_version="3.12.10",
        dependency_lock_sha256=sha256(legacy_lock).hexdigest(),
        sbom_sha256="2" * 64,
        provenance_sha256="3" * 64,
        verification_evidence_sha256="5" * 64,
        verification_phase="full",
        state_schema_min=1,
        state_schema_max=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.0.9",
        constitution_sha256="4" * 64,
        configuration_schema_version=1,
        created_at=NOW,
        artifact_sha256="6" * 64,
    )
    evidence = ReleaseActivationEvidence(
        release_id=legacy_manifest.release_id,
        manifest_sha256=legacy_manifest.manifest_sha256,
        signer_key_id="test",
        signature_verified=True,
        lineage_verified=True,
        anti_rollback_verified=True,
        verified_at=NOW,
    )
    store.activate(legacy_manifest, evidence)
    assert store.accepted("release-legacy")

    separated = releases / "release-next"
    separated.mkdir(parents=True)
    for component in ("sdk", "platform", "core"):
        (separated / built_component_wheels[component].name).write_bytes(
            built_component_wheels[component].read_bytes()
        )
    next_lock = b"cryptography==50.0.2 --hash=sha256:" + (b"b" * 64) + b"\n"
    (separated / "requirements.lock").write_bytes(next_lock)
    identities = []
    for component in ("sdk", "platform", "core"):
        report = inspect_wheel(
            built_component_wheels[component], f"sofia-{component}"
        )
        identities.append(
            ComponentArtifactIdentity(
                component=component,
                distribution=f"sofia-{component}",
                version=report.version,
                sha256=report.sha256,
            )
        )
    separated_manifest = ReleaseManifest(
        release_id="release-next",
        git_revision="2" * 40,
        application_version="0.1.0",
        python_version="3.12.10",
        dependency_lock_sha256=sha256(next_lock).hexdigest(),
        sbom_sha256="2" * 64,
        provenance_sha256="3" * 64,
        verification_evidence_sha256="5" * 64,
        verification_phase="full",
        state_schema_min=1,
        state_schema_max=1,
        fleet_protocol_version="1.0",
        fleet_agent_version="0.1.0",
        constitution_sha256="4" * 64,
        configuration_schema_version=1,
        created_at=NOW,
        artifact_sha256=directory_sha256(separated),
        components=tuple(sorted(identities, key=lambda identity: identity.component)),
    )
    next_evidence = ReleaseActivationEvidence(
        release_id=separated_manifest.release_id,
        manifest_sha256=separated_manifest.manifest_sha256,
        signer_key_id="test",
        signature_verified=True,
        lineage_verified=True,
        anti_rollback_verified=True,
        verified_at=NOW,
    )
    store.activate(separated_manifest, next_evidence)

    active = store.active()
    assert active["release_id"] == "release-next"
    assert active["previous_release_id"] == "release-legacy"
    assert store.accepted("release-legacy")
    resolved = ActiveReleaseResolver(
        state_path=state,
        release_root=release_root,
    ).resolve()
    assert resolved is not None
    assert resolved.release_id == "release-next"
    assert resolved.component_wheels
    assert resolved.wheel_path is None


def test_environment_manager_atomicity_rejects_partial_targets(
    tmp_path, monkeypatch, built_component_wheels
):
    state, release_root, _, _ = component_release_fixture(
        tmp_path, built_component_wheels
    )
    release = ActiveReleaseResolver(
        state_path=state,
        release_root=release_root,
    ).resolve()
    assert release is not None

    attempts = []

    class ExplodingEnvBuilder:
        def __init__(self, **kwargs):
            pass

        def create(self, root):
            attempts.append(Path(root))
            raise RuntimeError("venv creation interrupted mid-migration")

    monkeypatch.setattr(
        "sofia.platform.run.active_release.venv.EnvBuilder",
        ExplodingEnvBuilder,
    )
    manager = ReleaseEnvironmentManager(release_root=release_root)
    with pytest.raises(RuntimeError, match="interrupted"):
        manager.ensure(release)
    environments_root = release_root / "environments"
    leftovers = [
        path
        for path in environments_root.iterdir()
        if path.name != release.release_id
        and not path.name.startswith(".")
    ]
    assert attempts and not any(path.exists() for path in attempts)
    assert leftovers == []


def test_environment_manager_installs_component_wheels(
    tmp_path,
    monkeypatch,
    built_component_wheels,
):
    state, release_root, _, _ = component_release_fixture(
        tmp_path, built_component_wheels
    )
    release = ActiveReleaseResolver(
        state_path=state,
        release_root=release_root,
    ).resolve()
    assert release is not None

    class FakeBuilder:
        def __init__(self, **kwargs):
            pass

        def create(self, root):
            python = ReleaseEnvironmentManager._python(Path(root))
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_bytes(b"python")

    monkeypatch.setattr(
        "sofia.platform.run.active_release.venv.EnvBuilder",
        FakeBuilder,
    )
    manager = ReleaseEnvironmentManager(release_root=release_root)
    calls = []

    def fake_run(argv, *, timeout=600):
        calls.append(tuple(argv))
        if "-c" in argv:
            return release.application_version
        return ""

    monkeypatch.setattr(manager, "_run", fake_run)
    prepared = manager.ensure(release)
    install_calls = [
        call for call in calls if "--no-deps" in call
    ]
    assert len(install_calls) == 3
    assert [
        Path(call[-1]).name for call in install_calls
    ] == [
        wheel.name for wheel in release.component_wheels
    ]
    assert any(call[-1] == "check" for call in calls)
    version_calls = [call for call in calls if "-c" in call]
    assert len(version_calls) == 1
    assert "version('sofia-platform')" in version_calls[0][-1]
    assert "sofia-ada-lyra" not in version_calls[0][-1]
    assert prepared.python_path.is_file()
