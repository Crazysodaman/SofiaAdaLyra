"""Read-only state relocation preflight. No move, cutover or writes."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import os
import shutil


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
