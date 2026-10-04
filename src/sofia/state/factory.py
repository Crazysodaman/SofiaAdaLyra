"""Production StatePlane composition, including opt-in fenced replication."""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import socket
import sqlite3

from sofia.state.plane import StatePlane
from sofia.state.replication import ReplicatedStatePlane, SQLiteReplicationWitness
from sofia.state.sqlite_plane import SQLiteStatePlane


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
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return
    with sqlite3.connect(str(source)) as src, sqlite3.connect(str(destination)) as dst:
        src.backup(dst)
        row = dst.execute("PRAGMA integrity_check").fetchone()
        if row is None or row[0] != "ok":
            destination.unlink(missing_ok=True)
            raise RuntimeError("replica seed failed SQLite integrity_check")


def create_state_plane(state_path: Path | str) -> StatePlane:
    """Create local SQLite by default or an explicitly configured mirror.

    Replication remains opt-in so adding HA code cannot silently move production
    authority. The witness path must be distinct from every data-bearing target.
    """
    primary_path = Path(state_path).resolve()
    primary = SQLiteStatePlane(primary_path)
    if not _enabled("SOFIA_STATE_REPLICATION_ENABLED", False):
        return primary

    witness_raw = os.environ.get("SOFIA_STATE_WITNESS_PATH", "").strip()
    replicas_raw = os.environ.get("SOFIA_STATE_REPLICAS", "").strip()
    if not witness_raw or not replicas_raw:
        raise RuntimeError(
            "replication requires SOFIA_STATE_WITNESS_PATH and SOFIA_STATE_REPLICAS"
        )

    witness_path = Path(witness_raw).resolve()
    specs = _replica_specs(replicas_raw)
    if not specs:
        raise RuntimeError("replication requires at least one replica target")
    all_paths = {primary_path, *(path.resolve() for _, path in specs)}
    if len(all_paths) != len(specs) + 1:
        raise ValueError("replication data target paths must be distinct")
    if witness_path in all_paths:
        raise ValueError("replication witness must not share a data target path")

    if _enabled("SOFIA_STATE_REPLICATION_AUTO_SEED", False):
        for _, path in specs:
            _seed_sqlite(primary_path, path.resolve())

    targets: dict[str, StatePlane] = {"primary": primary}
    for target_id, path in specs:
        resolved = path.resolve()
        if not resolved.exists():
            raise FileNotFoundError(
                f"replica target {target_id} does not exist; seed it first or "
                "enable SOFIA_STATE_REPLICATION_AUTO_SEED"
            )
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
        witness=SQLiteReplicationWitness(witness_path),
        writer_id=writer_id,
        primary_target_id=primary_target,
        ttl_seconds=ttl,
    )
