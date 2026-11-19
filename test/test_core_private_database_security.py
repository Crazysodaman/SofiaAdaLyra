"""Security boundaries for per-Core private database installation and backup."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from uuid import UUID, uuid4

import pytest

from sofia.core.multicore.contracts import (
    AvatarMetadata,
    CoreDescriptor,
    EvidenceState,
    MemoryRecord,
    MemoryType,
    SecurityClass,
    StorageTier,
    VoiceMetadata,
)
from sofia.core.multicore.reflection import ReflectionCandidate
from sofia.core.persistence import core_database
from sofia.core.persistence.core_database import (
    CoreDatabaseBackupError,
    CoreDatabaseConflictError,
    CorePrivateDatabase,
    paths_for,
    verify_backup,
)
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from sofia.platform.state.private_file import ensure_owner_private_directory

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
CONSTITUTION = "a" * 64
ID2 = UUID("22222222-2222-4222-8222-222222222222")
ID3 = UUID("33333333-3333-4333-8333-333333333333")


def descriptor(core_id: UUID, *, core_number: int = 2, full_name: str = "Mack") -> CoreDescriptor:
    return CoreDescriptor(
        core_number=core_number,
        full_name=full_name,
        nickname=full_name,
        gender="male",
        presentation_species="human",
        apparent_age=29,
        identity_concept="continuous independent Core identity",
        personality_traits=("direct",),
        motivations=("protect trusted people",),
        character_flaw="stubbornness",
        constitutional_priorities=("truth", "consent"),
        avatar=AvatarMetadata(
            age_years=29,
            height_inches=72.0,
            weight_pounds=180.0,
            build="athletic",
            head_proportions=0.13,
            measurements={"shoulder": 18.0},
            hair="dark",
            outfit="jacket",
            default_expression="calm",
            colors={"hair": "#1A1A1A"},
            materials={"jacket": "cotton"},
            pbr={"roughness": 0.5},
        ),
        voice=VoiceMetadata(
            target="modeled-voice",
            register="low",
            accent=None,
            cadence="measured",
            serious_delivery="steady",
        ),
        core_id=core_id,
    )


def memory(owner: UUID, content: str) -> MemoryRecord:
    return MemoryRecord(
        memory_id=uuid4(),
        owner_core_id=owner,
        memory_type=MemoryType.SEMANTIC,
        tier=StorageTier.T1_ACTIVE,
        security=SecurityClass.PRIVATE,
        evidence=EvidenceState.VERIFIED,
        source="session:private",
        content=content,
        created_at=NOW,
        updated_at=NOW,
        confidence=0.9,
        significance=8,
    )


def candidate(owner: UUID, content: str) -> ReflectionCandidate:
    return ReflectionCandidate(
        candidate_id=uuid4(),
        owner_core_id=owner,
        content=content,
        evidence=(uuid4(),),
        significance=5,
    )


def fake_git_worktree(root: Path) -> Path:
    metadata = root / ".git"
    (metadata / "objects").mkdir(parents=True)
    (metadata / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    return root


def test_import_does_not_create_files_and_paths_are_pure(tmp_path):
    project = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(project / "src")
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sofia.core.persistence.core_database as module; "
            "assert module.APPROVED_CORE_NUMBERS == frozenset({1, 2, 3, 6, 7})",
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert list(tmp_path.iterdir()) == []

    root = tmp_path / "not-created"
    resolved = paths_for(root, ID2)
    assert resolved.database == root / str(ID2) / "core.db"
    assert not root.exists()


def test_create_fails_closed_on_unsafe_roots_and_permission_denial(tmp_path, monkeypatch):
    with pytest.raises(ValueError):
        CorePrivateDatabase.create("relative-root", core_id=ID2, core_number=2)

    protected = tmp_path / "sofia.db"
    with pytest.raises(PermissionError):
        CorePrivateDatabase.create(protected, core_id=ID2, core_number=2)
    assert not protected.exists()

    git_root = fake_git_worktree(tmp_path / "repo")
    with pytest.raises(PermissionError):
        CorePrivateDatabase.create(
            git_root / "private-cores", core_id=ID2, core_number=2,
        )
    assert not (git_root / "private-cores" / str(ID2)).exists()

    file_root = tmp_path / "not-a-directory"
    file_root.write_text("file", encoding="utf-8")
    with pytest.raises(PermissionError):
        CorePrivateDatabase.create(file_root, core_id=ID2, core_number=2)

    def deny(_path: Path) -> None:
        raise PermissionError("owner-private directory cannot be secured")

    monkeypatch.setattr(core_database, "ensure_owner_private_directory", deny)
    denied_root = tmp_path / "denied-cores"
    with pytest.raises(PermissionError):
        CorePrivateDatabase.create(denied_root, core_id=ID2, core_number=2)
    assert not (denied_root / str(ID2) / "core.db").exists()


def test_redirected_root_fails_closed(tmp_path):
    real = tmp_path / "real-root"
    real.mkdir()
    link = tmp_path / "linked-root"
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this host cannot create a directory symlink for the test")
    with pytest.raises(PermissionError):
        CorePrivateDatabase.create(link, core_id=ID2, core_number=2)
    assert not (real / str(ID2)).exists()


def test_junction_root_fails_closed(tmp_path):
    if os.name != "nt":
        pytest.skip("NTFS directory junctions are Windows-specific")
    real = tmp_path / "real-root"
    real.mkdir()
    link = tmp_path / "junction-root"
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(real)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        pytest.skip("this host cannot create an NTFS directory junction")
    try:
        with pytest.raises(PermissionError):
            CorePrivateDatabase.create(link, core_id=ID2, core_number=2)
        assert not (real / str(ID2)).exists()
    finally:
        subprocess.run(
            ["cmd", "/c", "rmdir", str(link)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )


def test_open_rejects_unbound_sqlite_and_foreign_ownership(tmp_path):
    unbound_root = tmp_path / "unbound-cores"
    ensure_owner_private_directory(unbound_root)
    unbound_id = uuid4()
    ensure_owner_private_directory(unbound_root / str(unbound_id))
    bootstrap_canonical_sqlite(unbound_root / str(unbound_id) / "core.db")
    with pytest.raises(CoreDatabaseConflictError):
        CorePrivateDatabase.open(unbound_root, core_id=unbound_id)

    root = tmp_path / "private-cores"
    mack = CorePrivateDatabase.create(root, core_id=ID2, core_number=2)
    nova = CorePrivateDatabase.create(root, core_id=ID3, core_number=3)
    mack.close()
    nova.close()

    source = root / str(ID2) / "core.db"
    target = root / str(ID3) / "core.db"
    target.unlink()
    source.replace(target)
    with pytest.raises(CoreDatabaseConflictError):
        CorePrivateDatabase.open(root, core_id=ID3, expected_core_number=3)
    with pytest.raises(CoreDatabaseConflictError):
        CorePrivateDatabase.create(root, core_id=ID3, core_number=3)


def test_backup_rejects_overwrite_tampering_and_git_destinations(tmp_path):
    root = tmp_path / "private-cores"
    backup_parent = tmp_path / "backups"
    backup_parent.mkdir()
    database = CorePrivateDatabase.create(
        root,
        core_id=ID2,
        core_number=2,
        descriptor=descriptor(ID2),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    database.memory_store.persist(memory(ID2, "backup secret"))

    destination = backup_parent / "core-2"
    verify_backup(database.backup(destination).destination)
    with pytest.raises(FileExistsError):
        database.backup(destination)
    plan = database.backup(destination, dry_run=True)
    assert plan.destination_available is False
    assert plan.blocker == "destination already exists"

    git_root = fake_git_worktree(tmp_path / "repo")
    with pytest.raises(PermissionError):
        database.backup(git_root / "backup")
    assert not (git_root / "backup").exists()

    tampered = backup_parent / "tampered"
    database.backup(tampered)
    with (tampered / "core.db").open("ab") as handle:
        handle.write(b"tamper")
    with pytest.raises(CoreDatabaseBackupError):
        verify_backup(tampered)
    database.close()


def test_rollback_cannot_adopt_another_cores_backup_or_overwrite_live_state(tmp_path):
    root = tmp_path / "private-cores"
    backup_parent = tmp_path / "backups"
    backup_parent.mkdir()
    mack = CorePrivateDatabase.create(root, core_id=ID2, core_number=2)
    nova = CorePrivateDatabase.create(root, core_id=ID3, core_number=3)
    mack.memory_store.persist(memory(ID2, "Mack backup payload"))
    backup = mack.backup(backup_parent / "mack")

    with pytest.raises(PermissionError):
        nova.rollback(backup.destination, tmp_path / "foreign-rollback")
    assert not (tmp_path / "foreign-rollback" / str(ID3) / "core.db").exists()

    stage = tmp_path / "existing-stage"
    stage.mkdir()
    ensure_owner_private_directory(stage)
    existing = CorePrivateDatabase.create(stage, core_id=ID2, core_number=2)
    existing.close()
    with pytest.raises(FileExistsError):
        mack.rollback(backup.destination, stage)
    mack.close()
    nova.close()


def test_error_strings_and_repr_do_not_leak_private_content(tmp_path, caplog):
    root = tmp_path / "private-cores"
    secret = "TOP-SECRET-PRIVATE-CONTENT-9f41"
    database = CorePrivateDatabase.create(
        root,
        core_id=ID2,
        core_number=2,
        descriptor=descriptor(ID2),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    database.memory_store.persist(memory(ID2, secret))

    errors: list[BaseException] = []
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(Exception) as memory_error:
            database.memory_store.persist(memory(ID3, secret))
        errors.append(memory_error.value)
        with pytest.raises(Exception) as learning_error:
            database.learning_service.observe_interest(
                ID3,
                "hobby:foreign",
                stance=True,
                evidence=EvidenceState.REPORTED,
                source="session:foreign",
                statement=secret,
                observed_at=NOW,
            )
        errors.append(learning_error.value)
        with pytest.raises(Exception) as reflection_error:
            database.reflection_service.create_batch(
                ID2,
                [candidate(ID3, secret)],
                batch_key="foreign-secret",
                now=NOW,
            )
        errors.append(reflection_error.value)
        with pytest.raises(Exception) as continuity_error:
            database.continuity_store.load(expected_core_id=ID3)
        errors.append(continuity_error.value)

    for error in errors:
        assert secret not in str(error)
        assert secret not in repr(error)
    assert secret not in repr(database)
    assert secret not in repr(database.paths)
    assert secret not in caplog.text
    database.close()


def test_metadata_is_single_bound_and_uses_canonical_application_id(tmp_path):
    root = tmp_path / "private-cores"
    database = CorePrivateDatabase.create(
        root,
        core_id=ID2,
        core_number=2,
        descriptor=descriptor(ID2),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    with closing(sqlite3.connect(str(database.paths.database))) as connection:
        application_id = connection.execute("PRAGMA application_id").fetchone()[0]
        rows = connection.execute(
            "SELECT singleton,schema,core_id,core_number "
            "FROM core_database_metadata"
        ).fetchall()
    assert int(application_id) == core_database.CANONICAL_APPLICATION_ID
    assert rows == [
        (1, core_database.CORE_DATABASE_SCHEMA, str(ID2), 2),
    ]
    database.close()
