"""Canonical Fleet state-path policy and legacy sidecar migration.

Production host-side Fleet control state belongs in Sofía's configured canonical
state database. Older releases stored Fleet identity, endpoint, grant, request,
and inference records in separate SQLite sidecars. This module migrates those
tables into the canonical database before current production code opens them.

Remote Fleet *agents* still own their own host-local persistence. This module
only consolidates the control-plane databases beside the authoritative runtime.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from sofia.distributed.durable import (
    DurableRemoteAuthorization,
    DurableRemoteLedger,
)
from sofia.distributed.endpoint_policy_durable import DurableEndpointPolicy
from sofia.distributed.identity_durable import DurableNodeIdentityRegistry
from sofia.distributed.inference_control import DurableInferenceLedger


_LEGACY_TABLES = (
    ("remote-identities.db", "distributed_node_identity"),
    ("remote-endpoints.db", "approved_remote_endpoint"),
    ("remote-grants.db", "remote_standing_grant"),
    ("remote-ledger.db", "remote_request_ledger"),
    ("remote-request-ledger.db", "remote_request_ledger"),
    ("remote-inference-ledger.db", "remote_inference_ledger"),
)


def canonical_fleet_state_paths(
    state_path: Path | str,
) -> dict[str, Path]:
    """Return canonical control-plane paths, all backed by one SQLite file."""
    canonical = Path(state_path)
    if str(state_path) == ":memory:":
        raise ValueError("canonical Fleet state must be on disk")
    return {
        "identity": canonical,
        "endpoint": canonical,
        "grant": canonical,
        "ledger": canonical,
        "inference_ledger": canonical,
    }


def _initialize_canonical_tables(state_path: Path) -> None:
    stores = (
        DurableNodeIdentityRegistry(state_path),
        DurableEndpointPolicy(state_path),
        DurableRemoteAuthorization(state_path),
        DurableRemoteLedger(state_path),
        DurableInferenceLedger(state_path),
    )
    for store in stores:
        close = getattr(store, "close", None)
        if callable(close):
            close()


def _retired_path(path: Path) -> Path:
    candidate = path.with_name(path.name + ".migrated")
    index = 1
    while candidate.exists():
        candidate = path.with_name(path.name + f".migrated.{index}")
        index += 1
    return candidate


def migrate_legacy_fleet_sidecars(
    state_path: Path | str,
) -> tuple[Path, ...]:
    """Move legacy host-side Fleet tables into the canonical Sofía database.

    The copy is idempotent and fail-closed. Existing canonical rows win only
    when they are byte-for-byte equivalent to legacy rows; conflicting legacy
    records abort migration. Legacy files are renamed only after every source
    row has been verified in the canonical database.
    """
    canonical = Path(state_path)
    if str(state_path) == ":memory:":
        raise ValueError("canonical Fleet state must be on disk")
    canonical.parent.mkdir(parents=True, exist_ok=True)
    _initialize_canonical_tables(canonical)

    legacy = tuple(
        (canonical.parent / filename, table)
        for filename, table in _LEGACY_TABLES
        if (canonical.parent / filename).is_file()
        and (canonical.parent / filename).resolve() != canonical.resolve()
    )
    if not legacy:
        return ()

    aliases: list[tuple[str, Path, str]] = []
    with closing(sqlite3.connect(canonical, timeout=10.0)) as db:
        db.execute("PRAGMA busy_timeout = 10000")
        try:
            for index, (source, table) in enumerate(legacy):
                alias = f"legacy_{index}"
                db.execute(
                    f"ATTACH DATABASE ? AS {alias}",
                    (str(source),),
                )
                aliases.append((alias, source, table))

            db.execute("BEGIN IMMEDIATE")
            for alias, source, table in aliases:
                exists = db.execute(
                    f"SELECT 1 FROM {alias}.sqlite_master "
                    "WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                if exists is None:
                    continue
                db.execute(
                    f'INSERT OR IGNORE INTO main."{table}" '
                    f'SELECT * FROM {alias}."{table}"'
                )
                unmatched = db.execute(
                    "SELECT COUNT(*) FROM ("
                    f'SELECT * FROM {alias}."{table}" '
                    "EXCEPT "
                    f'SELECT * FROM main."{table}"'
                    ")"
                ).fetchone()[0]
                if unmatched:
                    raise RuntimeError(
                        "legacy Fleet state conflicts with canonical "
                        f"sofia.db: {source.name}:{table}"
                    )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            for alias, _source, _table in reversed(aliases):
                try:
                    db.execute(f"DETACH DATABASE {alias}")
                except sqlite3.Error:
                    pass

    retired: list[Path] = []
    for source, _table in legacy:
        destination = _retired_path(source)
        try:
            source.replace(destination)
        except OSError as exc:
            raise RuntimeError(
                "legacy Fleet SQLite sidecar was copied into canonical "
                f"sofia.db but could not be retired: {source}. Stop older "
                "Sofía/tray processes and retry before continuing."
            ) from exc
        retired.append(destination)
    return tuple(retired)
