"""CORE-003 disposable memory writer, audience, legacy and recovery hardening.

Everything here uses tmp_path. No production/protected state, migration,
Ollama, Fleet or module implementation is touched.
"""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from sofia.core.memory.access import (
    LegacyMemoryState,
    MemoryStateCorrupt,
    MemoryStateIncompatible,
    MemoryStateUnavailable,
    MemoryStateUnsafe,
    MemoryWriterConflict,
)
from sofia.core.memory.audience import (
    ActivePrincipalRegistry,
    MemoryAudienceScope,
    PrincipalGrant,
    classify_memory_scope,
)
from sofia.core.memory.legacy import (
    MemoryStateKind,
    inspect_memory_state,
    quarantine_memory_state,
)
from sofia.core.memory.originals import SourceMessage
from sofia.core.memory.provenance import CandidateStatus, MemoryCandidate
from sofia.core.memory.provenance_store import DurableMemoryCandidateStore
from sofia.core.memory.system import MemorySystem
from sofia.core.social.model import AudienceKind, PrincipalContext
from sofia.core.social.principals import SPARKS_PRINCIPAL_ID, local_sparks_principal
from sofia.platform.config.defaults import production_storage_layout
from sofia.platform.ops.backup import BackupCipher, BackupEngine, BackupError
from sofia.platform.state.canonical_sqlite import bootstrap_canonical_sqlite
from test.test_ops_backup_restore import make_erasure_journal, make_state


NOW = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)


def _candidate(
    content: str,
    *,
    created_at: datetime | None = None,
    principal_id: str = SPARKS_PRINCIPAL_ID,
    audience_id: str | None = "local:text",
) -> MemoryCandidate:
    moment = created_at or NOW
    return MemoryCandidate(
        candidate_id=uuid4(),
        content=content,
        sources=(SourceMessage(
            message_id=str(uuid4()), session_id="synthetic-session",
            role="user", content=f"source for {content}",
            created_at=moment, position=0,
        ),),
        created_at=moment,
        principal_id=principal_id,
        audience_id=audience_id,
    )


def _seed_promoted(store: DurableMemoryCandidateStore, *items: MemoryCandidate):
    for item in items:
        store.propose(item)
        store.promote(item.candidate_id)


def test_exactly_one_canonical_memory_writer_is_allowed(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    first = DurableMemoryCandidateStore.open_canonical(state)
    try:
        with pytest.raises(MemoryWriterConflict):
            DurableMemoryCandidateStore(state)
        with pytest.raises(MemoryWriterConflict):
            DurableMemoryCandidateStore.open_canonical(state)
    finally:
        first.close()

    reopened = DurableMemoryCandidateStore.open_canonical(state)
    reopened.close()


def test_second_process_writer_is_denied(tmp_path):
    import subprocess
    import sys

    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    holder = DurableMemoryCandidateStore.open_canonical(state)
    try:
        source_root = Path(__file__).resolve().parents[1] / "src"
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            filter(None, (str(source_root), environment.get("PYTHONPATH", "")))
        )
        script = (
            "import sys\n"
            "from pathlib import Path\n"
            "from sofia.core.memory.provenance_store import "
            "DurableMemoryCandidateStore\n"
            "try:\n"
            "    DurableMemoryCandidateStore(Path(sys.argv[1]))\n"
            "except Exception as error:\n"
            "    name = type(error).__name__\n"
            "    print(name)\n"
            "    raise SystemExit(0 if name == 'MemoryWriterConflict' else 2)\n"
            "raise SystemExit(3)\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script, str(state)],
            capture_output=True, text=True, env=environment, timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "MemoryWriterConflict" in result.stdout
    finally:
        holder.close()


def test_strict_writer_never_bootstraps_missing_state(tmp_path):
    missing = tmp_path / "missing.db"
    with pytest.raises(MemoryStateUnavailable, match="unavailable"):
        DurableMemoryCandidateStore.open_canonical(missing)
    assert not missing.exists()
    with pytest.raises(MemoryStateUnavailable, match="unavailable"):
        DurableMemoryCandidateStore(missing, require_existing=True)
    assert not missing.exists()


def test_writer_refuses_wrong_exact_path_and_identity_assets(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    other = bootstrap_canonical_sqlite(tmp_path / "other.db")
    identity = tmp_path / "identity.json"
    identity.write_text("{}", encoding="utf-8")

    with pytest.raises(MemoryStateUnsafe, match="configured canonical state"):
        DurableMemoryCandidateStore.open_canonical(
            other, expected_state_path=state,
        )
    with pytest.raises(MemoryStateUnsafe, match="protected identity"):
        DurableMemoryCandidateStore.open_canonical(identity)
    with pytest.raises(MemoryStateUnsafe, match="regular file"):
        DurableMemoryCandidateStore.open_canonical(tmp_path)


def test_redirected_memory_path_is_refused(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    alias = tmp_path / "alias.db"
    try:
        alias.symlink_to(state)
    except (OSError, NotImplementedError):
        pytest.skip("host denies unprivileged symlinks")
    with pytest.raises(MemoryStateUnsafe, match="redirection"):
        DurableMemoryCandidateStore.open_canonical(alias)


@pytest.mark.skipif(os.name != "nt", reason="NTFS junctions are Windows-only")
def test_windows_junction_memory_path_is_refused(tmp_path):
    import subprocess

    real = tmp_path / "real"
    real.mkdir()
    state = bootstrap_canonical_sqlite(real / "sofia.db")
    alias = tmp_path / "alias"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(alias), str(real)],
        check=True, capture_output=True, text=True,
    )
    with pytest.raises(MemoryStateUnsafe, match="redirection"):
        DurableMemoryCandidateStore.open_canonical(alias / "sofia.db")
    assert state.is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows native DACL validation")
def test_windows_broad_dacl_is_refused(tmp_path):
    import win32api
    import win32con
    import win32security

    broad = tmp_path / "broad-acl"
    broad.mkdir()
    state = bootstrap_canonical_sqlite(broad / "sofia.db")
    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(), win32security.TOKEN_QUERY,
    )
    owner_sid, _ = win32security.GetTokenInformation(
        token, win32security.TokenUser,
    )
    acl = win32security.ACL()
    acl.AddAccessAllowedAce(
        win32security.ACL_REVISION, win32con.GENERIC_ALL, owner_sid,
    )
    acl.AddAccessAllowedAce(
        win32security.ACL_REVISION, win32con.GENERIC_READ,
        win32security.ConvertStringSidToSid("S-1-1-0"),
    )
    descriptor = win32security.GetFileSecurity(
        str(broad), win32security.DACL_SECURITY_INFORMATION,
    )
    descriptor.SetSecurityDescriptorDacl(1, acl, 0)
    descriptor.SetSecurityDescriptorControl(
        win32security.SE_DACL_PROTECTED, win32security.SE_DACL_PROTECTED,
    )
    win32security.SetFileSecurity(
        str(broad), win32security.DACL_SECURITY_INFORMATION, descriptor,
    )
    with pytest.raises(MemoryStateUnsafe, match="owner-private"):
        DurableMemoryCandidateStore.open_canonical(state)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits are not Windows ACLs")
def test_owner_private_directory_requirement_is_enforced(tmp_path):
    broad = tmp_path / "broad"
    broad.mkdir(mode=0o755)
    broad.chmod(0o755)
    state = bootstrap_canonical_sqlite(broad / "sofia.db")
    with pytest.raises(MemoryStateUnsafe, match="owner-private"):
        DurableMemoryCandidateStore.open_canonical(state)


def test_truncated_or_corrupt_state_is_never_reinitialized(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "zero.db")
    state.write_bytes(b"")
    with pytest.raises(MemoryStateCorrupt, match="truncated|empty"):
        DurableMemoryCandidateStore.open_canonical(state)
    assert state.read_bytes() == b""

    valid = bootstrap_canonical_sqlite(tmp_path / "garbage.db")
    corrupt = b"TOP-SECRET-PRIVATE-MARKER" + valid.read_bytes()[:32]
    valid.write_bytes(corrupt)
    with pytest.raises(MemoryStateCorrupt) as error:
        DurableMemoryCandidateStore(valid)
    assert "TOP-SECRET" not in str(error.value)
    assert valid.read_bytes() == corrupt


def test_restart_preserves_canonical_ordering_and_provenance(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    earlier = _candidate(
        "shared archive fact early",
        created_at=NOW - timedelta(days=2),
    )
    later = _candidate(
        "shared archive fact late",
        created_at=NOW,
    )
    store = DurableMemoryCandidateStore.open_canonical(state)
    try:
        _seed_promoted(store, later, earlier)
    finally:
        store.close()

    reopened = DurableMemoryCandidateStore.open_canonical(state)
    try:
        assert [
            candidate_id for candidate_id, _ in reopened.iter_promoted_summaries(
                principal_id=SPARKS_PRINCIPAL_ID, audience_id="local:text",
            )
        ] == [earlier.candidate_id, later.candidate_id]
        loaded = reopened.get(later.candidate_id)
        assert loaded is not None and loaded.sources[0].position == 0
        assert reopened.status(later.candidate_id) is CandidateStatus.PROMOTED
    finally:
        reopened.close()


def test_legacy_schema_is_quarantined_without_import_or_mutation(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "legacy.db")
    with sqlite3.connect(state) as db:
        db.execute(
            "CREATE TABLE memory_candidate ("
            "candidate_id TEXT PRIMARY KEY,content TEXT NOT NULL,"
            "created_at TEXT NOT NULL,status TEXT NOT NULL)"
        )
        db.execute(
            "INSERT INTO memory_candidate VALUES(?,?,?,?)",
            (str(uuid4()), "PRIVATE-LEGACY-CONTENT", NOW.isoformat(), "promoted"),
        )
    before = state.read_bytes()

    with pytest.raises(LegacyMemoryState, match="quarantine"):
        DurableMemoryCandidateStore.open_canonical(state)
    assert state.read_bytes() == before
    with sqlite3.connect(state) as db:
        tables = {
            row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert tables == {"memory_candidate"}

    report = inspect_memory_state(state)
    assert report.kind is MemoryStateKind.LEGACY_SCHEMA
    receipt = quarantine_memory_state(state, quarantine_root=tmp_path / "quarantine")
    assert receipt.sha256 == sha256(before).hexdigest()
    assert (receipt.quarantine_path / state.name).read_bytes() == before
    assert "PRIVATE-LEGACY-CONTENT" not in (
        receipt.quarantine_path / "quarantine.json"
    ).read_text(encoding="utf-8")
    assert state.read_bytes() == before


def test_future_memory_schema_is_refused_and_preserved(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    store = DurableMemoryCandidateStore(state)
    store.close()
    with sqlite3.connect(state) as db:
        db.execute(
            "CREATE TABLE core_memory_schema ("
            "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
            "version INTEGER NOT NULL)"
        )
        db.execute("INSERT INTO core_memory_schema VALUES(1, 999)")
    before = state.read_bytes()
    with pytest.raises(MemoryStateIncompatible, match="unsupported"):
        DurableMemoryCandidateStore.open_canonical(state)
    assert state.read_bytes() == before


def test_audience_scope_isolation_and_guest_never_inherits_unscoped_memory(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    owner = local_sparks_principal()
    shared = PrincipalContext(
        SPARKS_PRINCIPAL_ID, "discord:shared", AudienceKind.SHARED,
    )
    guest = PrincipalContext(
        "person:guest", "discord:shared", AudienceKind.SHARED,
    )
    other_private = PrincipalContext(
        SPARKS_PRINCIPAL_ID, "discord:dm:999", AudienceKind.PRIVATE,
    )
    assert classify_memory_scope(owner, owner_principal_id=SPARKS_PRINCIPAL_ID) is MemoryAudienceScope.OWNER
    assert classify_memory_scope(shared, owner_principal_id=SPARKS_PRINCIPAL_ID) is MemoryAudienceScope.GUEST

    scoped = _candidate("scoped private sensor violet")
    unscoped = _candidate("unscoped private sensor violet", audience_id=None)
    store = DurableMemoryCandidateStore.open_canonical(state)
    try:
        _seed_promoted(store, scoped, unscoped)
        system = MemorySystem(store)
        assert {item.id for item in system.recall_relevant("sensor violet", principal=owner)} == {
            str(scoped.candidate_id), str(unscoped.candidate_id),
        }
        assert system.recall_relevant("sensor violet", principal=shared) == ()
        assert system.recall_relevant("sensor violet", principal=guest) == ()
        # An unscoped candidate is principal-wide in private scopes, but a
        # channel-scoped candidate is never projected into another audience.
        assert [item.id for item in system.recall_relevant(
            "sensor violet", principal=other_private,
        )] == [str(unscoped.candidate_id)]
        with pytest.raises(PermissionError, match="system audience"):
            system.recall_relevant(
                "sensor violet",
                principal=PrincipalContext(
                    "system:core", "system:core", AudienceKind.SYSTEM,
                ),
            )
    finally:
        store.close()


def test_expired_candidate_and_unknown_or_expired_principal_are_denied(tmp_path):
    state = bootstrap_canonical_sqlite(tmp_path / "sofia.db")
    owner = local_sparks_principal()
    item = _candidate("owner temporal sensor magenta")
    store = DurableMemoryCandidateStore.open_canonical(state)
    try:
        _seed_promoted(store, item)
        store.set_expiration(
            item.candidate_id,
            expires_at=NOW - timedelta(seconds=1),
            reviewed_by=owner.principal_id,
            reason="synthetic expiration",
        )
        assert MemorySystem(store).recall_relevant(
            "temporal sensor", principal=owner,
        ) == ()

        registry = ActivePrincipalRegistry((
            PrincipalGrant(
                owner.principal_id, owner.audience_id,
                owner.audience_kind, expires_at=NOW - timedelta(seconds=1),
            ),
        ))
        with pytest.raises(PermissionError, match="expired"):
            MemorySystem(store, principal_registry=registry).recall_relevant(
                "temporal sensor", principal=owner,
            )

        unknown = PrincipalContext(
            "person:unknown", "local:text", AudienceKind.PRIVATE,
        )
        with pytest.raises(PermissionError, match="unknown"):
            MemorySystem(store, principal_registry=registry).recall_relevant(
                "temporal sensor", principal=unknown,
            )
    finally:
        store.close()


def _backup(tmp_path, *, generation=3):
    source = tmp_path / "source"
    source.mkdir()
    state = make_state(source)
    identity = production_storage_layout(state_path=state).identity_path
    core_identity_id = __import__("json").loads(
        identity.read_text(encoding="utf-8")
    )["instance_id"]
    engine = BackupEngine(BackupCipher(b"k" * 32))
    bundle, evidence = engine.create(
        state_path=state,
        destination_root=tmp_path / "backups",
        source_host_id="synthetic-host",
        failure_domain="synthetic-domain",
        now=NOW,
        core_identity_id=core_identity_id,
        generation=generation,
    )
    return state, identity, bundle, evidence, engine, core_identity_id


def test_backup_binds_identity_generation_and_restore_succeeds(tmp_path):
    _state, _identity, bundle, evidence, engine, core_identity_id = _backup(tmp_path)
    manifest = engine.verify(bundle)
    assert manifest.core_identity_id == core_identity_id
    assert manifest.generation == 3
    assert any(
        entry.logical_path == "protected/identity.json"
        for entry in manifest.entries
    )

    target = tmp_path / "restored" / "sofia.db"
    result = engine.restore(
        backup_dir=bundle,
        target_state_path=target,
        verifier="disposable-test",
        erasure_journal=make_erasure_journal(tmp_path),
        expected_identity_id=core_identity_id,
        expected_generation=3,
    )
    assert result.succeeded is True
    assert target.is_file()
    assert evidence.content_digest == manifest.digest


def test_restore_refuses_wrong_identity_digest_or_generation(tmp_path):
    _state, _identity, bundle, _evidence, engine, core_identity_id = _backup(tmp_path)
    journal = make_erasure_journal(tmp_path)

    with pytest.raises(BackupError, match="identity"):
        engine.restore(
            backup_dir=bundle,
            target_state_path=tmp_path / "missing-target" / "sofia.db",
            verifier="disposable-test",
            erasure_journal=journal,
            expected_identity_id="different-core-identity",
        )
    with pytest.raises(BackupError, match="generation"):
        engine.restore(
            backup_dir=bundle,
            target_state_path=tmp_path / "missing-target" / "sofia.db",
            verifier="disposable-test",
            erasure_journal=journal,
            expected_generation=999,
        )

    existing = tmp_path / "existing"
    existing.mkdir()
    target = make_state(existing)
    layout = production_storage_layout(state_path=target)
    layout.identity_path.write_text(
        '{"name": "Sofía Ada Lyra", '
        '"instance_id": "22222222-2222-4222-8222-222222222222"}',
        encoding="utf-8",
    )
    with pytest.raises(BackupError, match="different Core identity"):
        engine.restore(
            backup_dir=bundle,
            target_state_path=target,
            verifier="disposable-test",
            erasure_journal=journal,
        )

    generation_root = tmp_path / "existing-generation"
    generation_root.mkdir()
    generation_target = make_state(generation_root)
    with sqlite3.connect(generation_target) as db:
        db.execute(
            "INSERT OR REPLACE INTO state_plane_meta VALUES('generation','9')"
        )
    with pytest.raises(BackupError, match="different state generation"):
        engine.restore(
            backup_dir=bundle,
            target_state_path=generation_target,
            verifier="disposable-test",
            erasure_journal=journal,
        )

    payload = next((bundle / "payload").iterdir())
    data = bytearray(payload.read_bytes())
    data[-1] ^= 0x01
    payload.write_bytes(bytes(data))
    with pytest.raises(Exception) as error:
        engine.verify(bundle)
    assert "TOP-SECRET" not in str(error.value)


def test_authenticated_manifest_with_wrong_digest_is_refused(tmp_path):
    from dataclasses import replace

    _state, _identity, bundle, _evidence, engine, _core_identity_id = _backup(tmp_path)
    manifest = engine.verify(bundle)
    entry = replace(manifest.entries[0], sha256="0" * 64)
    tampered = replace(manifest, entries=(entry, *manifest.entries[1:]))
    manifest_bytes = tampered.canonical_bytes()
    (bundle / "manifest.json").write_bytes(manifest_bytes)
    (bundle / "manifest.hmac").write_text(
        engine.cipher.manifest_mac(manifest_bytes) + "\n", encoding="ascii",
    )
    with pytest.raises(BackupError, match="digest mismatch"):
        engine.verify(bundle)


def test_restore_never_merges_into_a_live_memory_writer(tmp_path):
    _state, _identity, bundle, _evidence, engine, _core_identity_id = _backup(tmp_path)
    target_root = tmp_path / "live-target"
    target_root.mkdir()
    target = make_state(target_root)
    writer = DurableMemoryCandidateStore.open_canonical(target)
    try:
        with pytest.raises(BackupError, match="live canonical writer"):
            engine.restore(
                backup_dir=bundle,
                target_state_path=target,
                verifier="disposable-test",
                erasure_journal=make_erasure_journal(tmp_path),
            )
    finally:
        writer.close()
