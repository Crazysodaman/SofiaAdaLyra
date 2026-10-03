from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import zipfile

import pytest

from sofia.dev.release import ReleaseManifest
from sofia.dev.release_store import ReleaseStateStore
from sofia.run.active_release import (
    ActiveReleaseError,
    ActiveReleaseResolver,
    ReleaseEnvironmentManager,
)
from sofia.run.release import directory_sha256
from sofia.safe.release import ReleaseActivationEvidence
from sofia.state.sqlite_plane import SQLiteStatePlane


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
    state = tmp_path / "sofia.db"
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
        "sofia.run.active_release.venv.EnvBuilder",
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
