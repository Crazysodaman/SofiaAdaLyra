"""Production StatePlane composition, including opt-in fenced replication."""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import os
import shutil
import socket
import sqlite3
import tempfile

from sofia.state.plane import StatePlane
from sofia.state.replication import ReplicatedStatePlane, SQLiteReplicationWitness
from sofia.state.sqlite_plane import SQLiteStatePlane
from sofia.state.canonical_sqlite import CanonicalSQLiteGuard


def _enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in {"1", "true", "on", "yes"}:
        return True
    if value in {"0", "false", "off", "no"}:
        return False
    raise ValueError(f"{name} must be boolean")


def _replica_specs(raw: str) -> tuple[tuple[str, Path], ...]:
    result: list[tuple[str, Path]] = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" not in item:
            raise ValueError(
                "SOFIA_STATE_REPLICAS entries must be target_id=path"
            )
        target_id, value = item.split("=", 1)
        target_id = target_id.strip()
        path = Path(value.strip())
        if not target_id or not str(path):
            raise ValueError("replica target ID and path are required")
        result.append((target_id, path))
    if len({target_id for target_id, _ in result}) != len(result):
        raise ValueError("replica target IDs must be unique")
    return tuple(result)


def _seed_sqlite(source: Path, destination: Path) -> None:
    """Publish a consistent replica snapshot atomically, without replacing data.

    A staging database is verified and all SQLite handles are closed *before*
    publication. Creating a replica directly at its canonical path would
    expose an incomplete database after a crash and may leave it locked on
    Windows. The final hard link is an atomic create-if-absent operation on
    the same local filesystem; unsupported filesystems fail closed.
    """
    source = Path(source)
    destination = Path(destination)
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError("verified local primary SQLite source required")
    if destination == source or destination.resolve() == source.resolve():
        raise ValueError("replica and primary must be distinct files")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ValueError("symlinked replica destination is not allowed")
    if destination.exists():
        return  # Existing replicas must be validated by SQLiteStatePlane.
    if destination.parent.is_symlink():
        raise ValueError("replica parent must not be a symbolic link")

    with tempfile.NamedTemporaryFile(
        prefix=".sofia-replica-seed-", suffix=".db",
        dir=destination.parent, delete=False,
    ) as handle:
        staged = Path(handle.name)
    try:
        # backup() sees a transactionally consistent source, including WAL.
        # closing(), unlike sqlite3's transaction context, releases Windows
        # file handles even if backup or integrity_check fails.
        with (
            closing(sqlite3.connect(
                source.resolve().as_uri() + "?mode=ro",
                uri=True, timeout=10,
            )) as src,
            closing(sqlite3.connect(str(staged), timeout=10)) as dst,
        ):
            src.backup(dst)
            row = dst.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                raise RuntimeError("replica seed failed SQLite integrity_check")
            dst.commit()
            checkpoint = dst.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint is not None and checkpoint[0] != 0:
                raise RuntimeError("replica seed could not checkpoint SQLite WAL")

        # Only the closed, verified main DB is published. WAL sidecars, if
        # created during snapshotting, must be empty after checkpointing.
        wal = Path(str(staged) + "-wal")
        if wal.exists() and wal.stat().st_size:
            raise RuntimeError("replica seed has uncheckpointed WAL bytes")
        with staged.open("rb") as content:
            os.fsync(content.fileno())
        # os.link fails with FileExistsError on a concurrent published target.
        # os.replace is forbidden here because it would destroy the winner.
        os.link(staged, destination)
    finally:
        staged.unlink(missing_ok=True)
        for suffix in ("-wal", "-shm", "-journal"):
            Path(str(staged) + suffix).unlink(missing_ok=True)


def create_state_plane(state_path: Path | str) -> StatePlane:
    """Create local SQLite by default or an explicitly configured mirror.

    Replication remains opt-in so adding HA code cannot silently move production
    authority. The witness path must be distinct from every data-bearing target.
    """
    # Ordinary single-host installation retains its explicit bootstrap path.
    # Opt-in replication must NEVER create state before its independent writer
    # witness has been validated. That could turn a failed HA startup into
    # an unapproved new authority on another host.
    if not _enabled("SOFIA_STATE_REPLICATION_ENABLED", False):
        return SQLiteStatePlane(Path(state_path).resolve())
    primary_guard = CanonicalSQLiteGuard(Path(state_path).absolute())
    primary_path = primary_guard.canonical_path

    witness_raw = os.environ.get("SOFIA_STATE_WITNESS_PATH", "").strip()
    replicas_raw = os.environ.get("SOFIA_STATE_REPLICAS", "").strip()
    if not witness_raw or not replicas_raw:
        raise RuntimeError(
            "replication requires SOFIA_STATE_WITNESS_PATH and SOFIA_STATE_REPLICAS"
        )

    # Keep the configured path spelling so a symlink/junction cannot be
    # normalized away before the independent witness guard inspects it.
    witness_path = Path(witness_raw).absolute()
    specs = _replica_specs(replicas_raw)
    if not specs:
        raise RuntimeError("replication requires at least one replica target")
    all_paths = {primary_path, *(path.resolve() for _, path in specs)}
    if len(all_paths) != len(specs) + 1:
        raise ValueError("replication data target paths must be distinct")
    if witness_path in all_paths:
        raise ValueError("replication witness must not share a data target path")

    # Witness is independently persisted control-plane evidence. It must
    # survive previous boots and remain on the same original file identity.
    # Its ordinary constructor refuses missing, replaced, or blank files.
    witness = SQLiteReplicationWitness(witness_path)
    if _enabled("SOFIA_STATE_REPLICATION_AUTO_SEED", False):
        for _, path in specs:
            primary_guard.validate()
            _seed_sqlite(primary_path, path.absolute())
            primary_guard.validate()

    targets: dict[str, StatePlane] = {"primary": SQLiteStatePlane(primary_path)}
    for target_id, path in specs:
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(
                f"replica target {target_id} does not exist; seed it first or "
                "enable SOFIA_STATE_REPLICATION_AUTO_SEED"
            )
        CanonicalSQLiteGuard(path.absolute())
        targets[target_id] = SQLiteStatePlane(resolved)

    writer_id = os.environ.get(
        "SOFIA_STATE_WRITER_ID",
        f"sofia:{socket.gethostname()}",
    ).strip()
    primary_target = os.environ.get(
        "SOFIA_STATE_PRIMARY_TARGET",
        "primary",
    ).strip()
    ttl = int(os.environ.get("SOFIA_STATE_WRITER_TTL_SECONDS", "30"))
    return ReplicatedStatePlane(
        targets,
        witness=witness,
        writer_id=writer_id,
        primary_target_id=primary_target,
        ttl_seconds=ttl,
    )
