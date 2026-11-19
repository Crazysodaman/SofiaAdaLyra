"""Per-Core private database isolation, restart and non-destructive backup."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
import sqlite3
from uuid import UUID, uuid4

import pytest

from sofia.core.multicore.continuity import ContinuityIntegrityError
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
from sofia.core.multicore.memory import MemoryIsolationError
from sofia.core.multicore.reflection import ReflectionCandidate
from sofia.core.persistence.core_database import (
    APPROVED_CORE_NUMBERS,
    CORE_DATABASE_FILENAME,
    CoreDatabaseBackup,
    CoreDatabaseConflictError,
    CoreDatabaseError,
    CorePrivateDatabase,
    CorePrivateDatabaseCatalog,
    paths_for,
)
from sofia.platform.state.private_file import assert_owner_private_path

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
CONSTITUTION = "a" * 64
ID1 = UUID("11111111-1111-4111-8111-111111111111")
ID2 = UUID("22222222-2222-4222-8222-222222222222")
ID3 = UUID("33333333-3333-4333-8333-333333333333")
ID6 = UUID("66666666-6666-4666-8666-666666666666")
ID7 = UUID("77777777-7777-4777-8777-777777777777")


def descriptor(
    core_id: UUID,
    *,
    core_number: int = 2,
    full_name: str = "Mack Fuller",
) -> CoreDescriptor:
    return CoreDescriptor(
        core_number=core_number,
        full_name=full_name,
        nickname=full_name.split()[0],
        gender="male",
        presentation_species="human",
        apparent_age=29,
        identity_concept="continuous independent Core identity",
        personality_traits=("direct", "steady", "stubborn"),
        motivations=("protect the people he trusts", "understand the work"),
        character_flaw="stubbornness",
        constitutional_priorities=("truth", "consent", "owner authority"),
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
            colors={"hair": "#1A1A1A", "eyes": "#4A6B52"},
            materials={"jacket": "cotton"},
            pbr={"roughness": 0.5},
        ),
        voice=VoiceMetadata(
            target="modeled-voice",
            register="low",
            accent=None,
            cadence="measured",
            serious_delivery="steady and direct",
        ),
        core_id=core_id,
    )


def memory(owner: UUID, content: str, *, moment: datetime = NOW) -> MemoryRecord:
    return MemoryRecord(
        memory_id=uuid4(),
        owner_core_id=owner,
        memory_type=MemoryType.SEMANTIC,
        tier=StorageTier.T1_ACTIVE,
        security=SecurityClass.PRIVATE,
        evidence=EvidenceState.VERIFIED,
        source="session:private",
        content=content,
        created_at=moment,
        updated_at=moment,
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


def schema_names(path: Path) -> tuple[str, ...]:
    with closing(sqlite3.connect(str(path))) as database:
        rows = database.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return tuple(str(row[0]) for row in rows)


def test_creates_only_uuid_keyed_databases_for_approved_core_numbers(tmp_path):
    root = tmp_path / "private-cores"
    database = CorePrivateDatabase.create(root, core_id=ID2, core_number=2)

    assert database.paths.database == root / str(ID2) / CORE_DATABASE_FILENAME
    assert database.paths.database.is_file()
    assert "mack" not in str(database.paths.database).casefold()
    assert database.core_id == ID2
    assert database.core_number == 2
    assert_owner_private_path(root, directory=True)
    assert_owner_private_path(database.paths.directory, directory=True)
    assert_owner_private_path(database.paths.database, directory=False)
    assert database.verify() is True
    database.close()

    for number in sorted(APPROVED_CORE_NUMBERS - {2}):
        other_id = uuid4()
        other = CorePrivateDatabase.create(
            root, core_id=other_id, core_number=number,
        )
        assert other.paths.database == root / str(other_id) / CORE_DATABASE_FILENAME
        assert other.core_number == number
        other.close()

    for number in (4, 5, 0, 8, -1):
        rejected_id = uuid4()
        with pytest.raises(PermissionError):
            CorePrivateDatabase.create(
                root, core_id=rejected_id, core_number=number,
            )
        assert not (root / str(rejected_id)).exists()


def test_binds_existing_services_and_preserves_one_core_across_restart(tmp_path):
    root = tmp_path / "private-cores"
    database = CorePrivateDatabase.create(
        root,
        core_id=ID2,
        core_number=2,
        descriptor=descriptor(ID2),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )

    memory_id = database.memory_store.persist(
        memory(ID2, "private alpha memory")
    )
    database.learning_service.observe_interest(
        ID2,
        "hobby:restoration",
        stance=True,
        evidence=EvidenceState.VERIFIED,
        source="session:private",
        statement="I repaired the old radio myself and want to keep learning.",
        observed_at=NOW + timedelta(minutes=1),
    )
    batch = database.reflection_service.create_batch(
        ID2,
        [candidate(ID2, "reflect on the private radio repair")],
        batch_key="private-restart",
        now=NOW + timedelta(minutes=2),
    )
    assert batch is not None
    continuity = database.continuity_store.load(expected_core_id=ID2)
    updated = continuity.with_personal_state(
        personality_revision=1,
        personality_digest="b" * 64,
        emotion_revision=1,
        relationships_revision=1,
        now=NOW + timedelta(minutes=3),
    )
    database.continuity_store.save(updated)
    database_path = database.paths.database
    database.close()

    reopened = CorePrivateDatabase.open(
        root, core_id=ID2, expected_core_number=2,
    )
    assert reopened.paths.database == database_path
    assert reopened.memory_store.get(memory_id).content == "private alpha memory"
    preference = reopened.learning_service.get_preference(
        ID2, "hobby:restoration", domain="interest",
    )
    assert preference is not None
    assert reopened.reflection_service.get_batch(batch.batch_id) is not None
    loaded = reopened.continuity_store.load(expected_core_id=ID2)
    assert loaded.core_id == ID2
    assert loaded.personality_revision == 1
    assert loaded.emotion_revision == 1
    assert loaded.relationships_revision == 1
    assert reopened.verify(require_continuity=True) is True
    reopened.close()


def test_cross_core_reads_writes_and_reflection_are_denied(tmp_path):
    root = tmp_path / "private-cores"
    mack = CorePrivateDatabase.create(
        root,
        core_id=ID2,
        core_number=2,
        descriptor=descriptor(ID2),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    nova = CorePrivateDatabase.create(
        root,
        core_id=ID3,
        core_number=3,
        descriptor=descriptor(ID3, core_number=3, full_name="Nova Arden"),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )

    assert mack.paths.database != nova.paths.database
    mack_id = mack.memory_store.persist(memory(ID2, "Mack private memory"))
    nova_id = nova.memory_store.persist(memory(ID3, "Nova private memory"))
    assert mack.memory_store.get(nova_id) is None
    assert nova.memory_store.get(mack_id) is None
    assert [item.memory_id for item in mack.memory_store.active_records()] == [mack_id]
    assert [item.memory_id for item in nova.memory_store.active_records()] == [nova_id]

    with pytest.raises(MemoryIsolationError):
        mack.memory_store.persist(memory(ID3, "foreign write"))
    with pytest.raises(PermissionError):
        mack.learning_service.observe_interest(
            ID3,
            "hobby:foreign",
            stance=True,
            evidence=EvidenceState.REPORTED,
            source="session:foreign",
            statement="This observation belongs to another Core.",
            observed_at=NOW,
        )
    with pytest.raises(PermissionError):
        mack.reflection_service.create_batch(
            ID2,
            [candidate(ID3, "foreign reflection candidate")],
            batch_key="foreign",
            now=NOW,
        )
    with pytest.raises(ContinuityIntegrityError):
        mack.continuity_store.load(expected_core_id=ID3)

    assert mack.memory_store.get(mack_id).owner_core_id == ID2
    assert nova.memory_store.get(nova_id).owner_core_id == ID3
    mack.close()
    nova.close()


def test_namespace_isolation_survives_restart_with_identical_memory_ids(tmp_path):
    root = tmp_path / "private-cores"
    shared_memory_id = uuid4()
    mack = CorePrivateDatabase.create(root, core_id=ID2, core_number=2)
    nova = CorePrivateDatabase.create(root, core_id=ID3, core_number=3)
    mack.memory_store.persist(
        MemoryRecord(
            memory_id=shared_memory_id,
            owner_core_id=ID2,
            memory_type=MemoryType.SEMANTIC,
            tier=StorageTier.T1_ACTIVE,
            security=SecurityClass.PRIVATE,
            evidence=EvidenceState.VERIFIED,
            source="session:mack",
            content="Mack namespace content",
            created_at=NOW,
            updated_at=NOW,
            confidence=0.9,
            significance=8,
        )
    )
    nova.memory_store.persist(
        MemoryRecord(
            memory_id=shared_memory_id,
            owner_core_id=ID3,
            memory_type=MemoryType.SEMANTIC,
            tier=StorageTier.T1_ACTIVE,
            security=SecurityClass.PRIVATE,
            evidence=EvidenceState.VERIFIED,
            source="session:nova",
            content="Nova namespace content",
            created_at=NOW,
            updated_at=NOW,
            confidence=0.9,
            significance=8,
        )
    )
    mack.close()
    nova.close()

    reopened_mack = CorePrivateDatabase.open(root, core_id=ID2, expected_core_number=2)
    reopened_nova = CorePrivateDatabase.open(root, core_id=ID3, expected_core_number=3)
    assert reopened_mack.memory_store.get(shared_memory_id).content == "Mack namespace content"
    assert reopened_nova.memory_store.get(shared_memory_id).content == "Nova namespace content"
    assert reopened_mack.memory_store.active_records()[0].owner_core_id == ID2
    assert reopened_nova.memory_store.active_records()[0].owner_core_id == ID3
    reopened_mack.close()
    reopened_nova.close()


def test_rename_never_changes_path_and_reinstall_cannot_adopt_foreign_database(tmp_path):
    root = tmp_path / "private-cores"
    mack = CorePrivateDatabase.create(
        root,
        core_id=ID2,
        core_number=2,
        descriptor=descriptor(ID2, full_name="Mack Fuller"),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    assert mack.paths.database == paths_for(root, ID2).database
    assert str(mack.paths.database).casefold().endswith(
        str(ID2).casefold() + "\\core.db"
    ) or str(mack.paths.database).casefold().endswith(
        str(ID2).casefold() + "/core.db"
    )
    assert "mack-fuller" not in str(mack.paths.database).casefold()

    nova = CorePrivateDatabase.create(
        root,
        core_id=ID3,
        core_number=3,
        descriptor=descriptor(ID3, core_number=3, full_name="Nova Arden"),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    mack.memory_store.persist(memory(ID2, "Mack must remain Mack"))
    nova.memory_store.persist(memory(ID3, "Nova must remain Nova"))
    mack.close()
    nova.close()

    shutil.copyfile(
        root / str(ID2) / CORE_DATABASE_FILENAME,
        root / str(ID3) / CORE_DATABASE_FILENAME,
    )
    with pytest.raises(CoreDatabaseConflictError):
        CorePrivateDatabase.open(root, core_id=ID3, expected_core_number=3)
    with pytest.raises(CoreDatabaseConflictError):
        CorePrivateDatabase.create(root, core_id=ID3, core_number=3)
    with pytest.raises(CoreDatabaseConflictError):
        CorePrivateDatabase.create(root, core_id=ID2, core_number=3)


def test_schema_initialization_and_reinstall_are_deterministic(tmp_path):
    root = tmp_path / "private-cores"
    first = CorePrivateDatabase.create(root, core_id=ID6, core_number=6)
    names_before = schema_names(first.paths.database)
    assert "core_database_metadata" in names_before
    assert "multicore_memory" in names_before
    assert "multicore_preference" in names_before
    assert "multicore_reflection_batch" in names_before
    first.memory_store.persist(memory(ID6, "Vera persists across restart"))
    first.close()

    reopened = CorePrivateDatabase.open(root, core_id=ID6, expected_core_number=6)
    assert schema_names(reopened.paths.database) == names_before
    reopened.close()

    reinstalled = CorePrivateDatabase.create(root, core_id=ID6, core_number=6)
    assert schema_names(reinstalled.paths.database) == names_before
    assert len(reinstalled.memory_store.active_records()) == 1
    with closing(sqlite3.connect(str(reinstalled.paths.database))) as database:
        count = database.execute(
            "SELECT COUNT(*) FROM core_database_metadata"
        ).fetchone()[0]
    assert count == 1
    reinstalled.close()


def test_backup_never_overwrites_and_rollback_is_non_destructive(tmp_path):
    root = tmp_path / "private-cores"
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    rollback_root = tmp_path / "rollback-stage"
    database = CorePrivateDatabase.create(
        root,
        core_id=ID7,
        core_number=7,
        descriptor=descriptor(ID7, core_number=7, full_name="Core Seven"),
        constitution_sha256=CONSTITUTION,
        now=NOW,
    )
    backed_up_id = database.memory_store.persist(memory(ID7, "state at backup time"))
    database.learning_service.observe_interest(
        ID7,
        "hobby:stars",
        stance=True,
        evidence=EvidenceState.VERIFIED,
        source="session:private",
        statement="I keep returning to the telescope records.",
        observed_at=NOW + timedelta(minutes=1),
    )
    destination = backup_root / "core-7"
    plan = database.backup(destination, dry_run=True)
    assert plan.destination_available is True
    assert plan.database_bytes > 0
    assert plan.continuity_present is True
    assert not destination.exists()

    backup = database.backup(destination)
    assert isinstance(backup, CoreDatabaseBackup)
    assert backup.core_id == ID7
    assert backup.core_number == 7
    assert backup.continuity_sha256 is not None
    assert_owner_private_path(destination, directory=True)
    assert_owner_private_path(destination / "core.db", directory=False)
    assert_owner_private_path(destination / "continuity.json", directory=False)
    before = (destination / "core.db").read_bytes()
    with pytest.raises(FileExistsError):
        database.backup(destination)
    assert (destination / "core.db").read_bytes() == before
    blocked = database.backup(destination, dry_run=True)
    assert blocked.destination_available is False
    assert blocked.blocker == "destination already exists"

    after_backup_id = database.memory_store.persist(
        memory(ID7, "created after the backup", moment=NOW + timedelta(minutes=2))
    )
    restored = database.rollback(destination, rollback_root)
    assert restored.core_id == ID7
    assert restored.core_number == 7
    assert restored.memory_store.get(backed_up_id) is not None
    assert restored.memory_store.get(after_backup_id) is None
    assert database.memory_store.get(after_backup_id) is not None
    assert restored.continuity_store.load(expected_core_id=ID7).core_id == ID7
    assert restored.verify(require_continuity=True) is True
    restored.close()
    database.close()


def test_concurrent_cores_do_not_leak_memories(tmp_path):
    root = tmp_path / "private-cores"
    pairs = ((ID1, 1), (ID2, 2), (ID3, 3), (ID6, 6), (ID7, 7))
    for core_id, number in pairs:
        CorePrivateDatabase.create(root, core_id=core_id, core_number=number).close()

    def write(core_id: UUID) -> None:
        database = CorePrivateDatabase.open(root, core_id=core_id)
        try:
            for index in range(20):
                database.memory_store.persist(
                    memory(
                        core_id,
                        f"{core_id}:private:{index}",
                        moment=NOW + timedelta(seconds=index),
                    )
                )
        finally:
            database.close()

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(write, [core_id for core_id, _ in pairs]))

    for core_id, number in pairs:
        database = CorePrivateDatabase.open(
            root, core_id=core_id, expected_core_number=number,
        )
        records = database.memory_store.active_records()
        assert len(records) == 20
        assert {record.owner_core_id for record in records} == {core_id}
        assert all(
            record.content.startswith(f"{core_id}:private:")
            for record in records
        )
        database.close()


def test_close_is_idempotent_and_catalog_closes_every_database(tmp_path):
    root = tmp_path / "private-cores"
    database = CorePrivateDatabase.create(root, core_id=ID2, core_number=2)
    database.close()
    database.close()
    with pytest.raises(CoreDatabaseError):
        database.verify()
    with pytest.raises(CoreDatabaseError):
        _ = database.memory_store

    with CorePrivateDatabaseCatalog(root) as catalog:
        opened = catalog.open(core_id=ID2, expected_core_number=2)
        assert catalog.get(ID2) is opened
        assert opened.verify() is True
    with pytest.raises(CoreDatabaseError):
        catalog.open(core_id=ID2)

    with CorePrivateDatabase.create(
        root, core_id=ID3, core_number=3,
    ) as context_database:
        assert context_database.verify() is True
    with pytest.raises(CoreDatabaseError):
        context_database.verify()
