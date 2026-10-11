"""Read-only state relocation preflight. No move, cutover or writes."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import sqlite3
from contextlib import closing


@dataclass(frozen=True, slots=True)
class RelocationPreflight:
    source: Path
    destination: Path
    source_database_exists: bool
    source_bytes: int
    destination_free_bytes: int | None
    files_to_preserve: tuple[str, ...]
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def eligible_for_review(self) -> bool:
        return not self.blockers

    @property
    def ready_for_automatic_cutover(self) -> bool:
        return False  # offline fencing and authorization are not yet implemented


def _unsafe_ancestor(path: Path) -> bool:
    return any(item.is_symlink() for item in (path, *path.parents))


def inspect_state_relocation(source_state_path: Path, destination_root: Path) -> RelocationPreflight:
    if not isinstance(source_state_path, Path) or not isinstance(destination_root, Path):
        raise TypeError("source/destination must be paths")
    if not destination_root.is_absolute():
        raise ValueError("destination must be an absolute host-local path")
    source = source_state_path.absolute()
    dest = destination_root.absolute()
    origin = source.parent
    blockers: list[str] = []
    warnings: list[str] = []
    if source.name != "sofia.db":
        blockers.append("unexpected_canonical_db_filename")
    if not source.is_file():
        blockers.append("canonical_state_database_missing")
    if _unsafe_ancestor(source) or _unsafe_ancestor(dest):
        blockers.append("symlinked_state_or_destination_path")
    if dest == origin or origin in dest.parents or dest in origin.parents:
        blockers.append("source_destination_overlap")
    if os.name == "nt" and (str(dest).startswith("\\\\") or not dest.drive):
        blockers.append("network_or_nonlocal_destination_not_supported")
    if str(dest).startswith("//"):
        blockers.append("network_destination_not_supported")
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        blockers.append("destination_must_be_empty_directory")
    manifest = (
        "sofia.db", "protected/", "personality.json", "avatar.json",
        "release-runtime/active-release.json",
    )
    for expected in ("protected/constitution.md", "protected/identity.json", "personality.json", "avatar.json"):
        if not (origin / expected).is_file():
            warnings.append(f"missing_or_external_component:{expected}")
    # A live home contains more than the SQLite file. A preflight must expose
    # unknown top-level state before anybody assumes a backup is a complete
    # relocation manifest. Keep the scan shallow and bounded for UI use.
    if origin.is_dir():
        known = {
            "sofia.db", "sofia.db-wal", "sofia.db-shm",
            "protected", "personality.json", "avatar.json",
            "release-runtime",
        }
        extras = []
        for count, item in enumerate(origin.iterdir()):
            if count >= 256:
                warnings.append("state_root_inventory_truncated")
                break
            if item.name not in known:
                extras.append(item.name)
        if extras:
            warnings.append(
                "unclassified_state_root_items:" +
                ",".join(sorted(extras)[:32])
            )
    warnings += [
        "mapped_drives_and_remote_mounts_need_explicit_operator_verification",
        "external_assets_archive_references_and_secrets_need_independent_review",
        "running_services_and_fleet_writers_must_be_fenced_before_any_move",
        "existing_backup_engine_must_verify_staged_bundle_before_approved_cutover",
        "never_copy_live_sqlite_wal_files_with_plain_file_copy",
    ]
    db_size = source.stat().st_size if source.is_file() else 0
    free: int | None = None
    try:
        available = dest if dest.exists() else next(
            (item for item in dest.parents if item.exists()), dest,
        )
        free = shutil.disk_usage(available).free
        if free < max(2 * db_size, 512 * 1024 * 1024):
            blockers.append("destination_space_below_conservative_minimum")
    except OSError:
        blockers.append("destination_space_unverifiable")
    return RelocationPreflight(
        source, dest, source.is_file(), db_size, free,
        manifest, tuple(dict.fromkeys(blockers)), tuple(warnings),
    )


def relocation_preflight_text(source: Path, destination: Path) -> str:
    p = inspect_state_relocation(source, destination)
    return "\n".join((
        f"Canonical source: {p.source}",
        f"Proposed destination: {p.destination}",
        f"Database size: {p.source_bytes:,} bytes",
        f"Free bytes: {p.destination_free_bytes}",
        f"Review eligible: {p.eligible_for_review}",
        "Automatic relocation: DISABLED (requires fenced offline cutover)",
        "Blockers: " + (", ".join(p.blockers) or "none"),
        "Warnings: " + "; ".join(p.warnings),
    ))


@dataclass(frozen=True, slots=True)
class StateCandidate:
    """Possible old/copied Sofía home; never proof of canonical authority."""
    state_path: Path
    database_size: int
    protected_identity_present: bool
    is_configured_path: bool
    sqlite_header_valid: bool = False
    expected_schema_present: bool = False
    identity_matches_configured_home: bool | None = None


def discover_local_state_candidates(
    *, configured_path: Path, extra_roots: tuple[Path, ...] = (),
    max_roots: int = 12,
) -> tuple[StateCandidate, ...]:
    """Inspect a bounded explicit candidate set, never enumerate entire disks.

    A discovered file is NOT a verified Sofía database, a grant, or a valid
    replacement for the one canonical path currently configured. Real
    verification requires schema, protected identity and operator ownership.
    """
    if not isinstance(configured_path, Path) or not isinstance(extra_roots, tuple):
        raise TypeError("configured path and candidate roots have invalid types")
    if type(max_roots) is not int or not 1 <= max_roots <= 32:
        raise ValueError("max_roots must be bounded")
    from pathlib import Path as _Path
    import os as _os
    guessed_roots: list[Path] = [
        configured_path.parent,
        _Path.home() / "SofiaAdaLyra",
    ]
    if _os.name == "nt":
        guessed_roots.append(_Path(_os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "SofiaAdaLyra")
        appdata = _os.environ.get("LOCALAPPDATA")
        if appdata:
            guessed_roots.append(_Path(appdata) / "SofiaAdaLyra")
    else:
        guessed_roots += [
            _Path("/var/lib/sofia-ada-lyra"),
            _Path.home() / ".local/share/sofia-ada-lyra",
        ]
    if any(not isinstance(root, Path) for root in extra_roots):
        raise TypeError("extra roots must be paths")
    guessed_roots.extend(extra_roots)
    configured_identity = configured_path.absolute().parent / "protected/identity.json"
    canonical_identity_digest: bytes | None = None
    if configured_identity.is_file() and not configured_identity.is_symlink():
        from hashlib import sha256
        # Private identities are compared only, never returned or logged.
        canonical_identity_digest = sha256(configured_identity.read_bytes()).digest()
    seen: set[Path] = set()
    results: list[StateCandidate] = []
    for root in guessed_roots[:max_roots]:
        directory = root.absolute()
        if directory in seen or _unsafe_ancestor(directory):
            continue
        seen.add(directory)
        database = directory / "sofia.db"
        if not database.is_file() or database.is_symlink():
            continue
        with database.open("rb") as handle:
            has_sqlite_header = handle.read(16) == b"SQLite format 3\\x00"
        has_schema = False
        if has_sqlite_header:
            # Query-only URI prevents accidental DB creation or state edits.
            # A matching schema remains merely a candidate, not authority.
            try:
                with closing(sqlite3.connect(
                    database.as_uri() + "?mode=ro", uri=True, timeout=2,
                )) as connection:
                    connection.execute("PRAGMA query_only=ON")
                    tables = {name for (name,) in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table' AND name IN "
                        "('conversation_sessions','conversation_messages',"
                        "'social_session_principal')"
                    ).fetchall()}
                    has_schema = {
                        "conversation_sessions", "conversation_messages",
                        "social_session_principal",
                    }.issubset(tables)
            except (sqlite3.Error, OSError):
                # Corrupt, locked or incompatible copies never become trusted.
                has_schema = False
        identity = directory / "protected/identity.json"
        identity_exists = identity.is_file() and not identity.is_symlink()
        same_identity: bool | None = None
        if identity_exists and canonical_identity_digest is not None:
            from hashlib import sha256
            same_identity = sha256(identity.read_bytes()).digest() == canonical_identity_digest
        results.append(StateCandidate(
            state_path=database,
            database_size=database.stat().st_size,
            protected_identity_present=identity_exists,
            is_configured_path=database == configured_path.absolute(),
            sqlite_header_valid=has_sqlite_header,
            expected_schema_present=has_schema,
            identity_matches_configured_home=same_identity,
        ))
    return tuple(results)


def describe_state_candidates(configured_path: Path) -> str:
    candidates = discover_local_state_candidates(configured_path=configured_path)
    if not candidates:
        return "No Sofía database files were found at configured or known local roots."
    return "\n".join(
        f"{item.state_path} | {item.database_size:,} bytes | "
        f"protected identity: {item.protected_identity_present} | "
        f"SQLite header: {item.sqlite_header_valid} | "
        f"expected schema: {item.expected_schema_present} | "
        f"identity matches current: {item.identity_matches_configured_home} | "
        f"configured: {item.is_configured_path}"
        for item in candidates
    ) + "\nThese are unverified candidates, not alternate canonical databases."
