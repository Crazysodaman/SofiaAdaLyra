"""Operator-gated, non-promoting staged relocation of one canonical state home.

Reuses BackupEngine's consistent SQLite snapshot, encrypted state bundle,
manifest MAC, full restore verification and protected-identity checks.
Never rewrites a bootstrap pointer, switches active writers or starts Sofia.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
from typing import Callable

from sofia.ops.backup import BackupEngine, BackupError
from sofia.ops.state_mobility import inspect_state_relocation


@dataclass(frozen=True, slots=True)
class RelocationAuthorization:
    """Evidence carried from an independently privileged control plane."""

    source_state_path: Path
    destination_root: Path
    writer_host_id: str
    source_writer_host_id: str
    next_writer_epoch: int
    operator_approval_ref: str
    writer_fence_ref: str


@dataclass(frozen=True, slots=True)
class StagedStateHome:
    backup_dir: Path
    destination_state_path: Path
    backup_id: str
    writer_host_id: str
    proposed_writer_epoch: int
    verified_restore: bool
    activated: bool = False


def stage_verified_state_home(
    *, proof: RelocationAuthorization,
    independently_verify_authorization: Callable[[RelocationAuthorization], bool],
    backup_engine: BackupEngine,
    encrypted_backup_root: Path,
    failure_domain: str,
    erasure_journal_path: Path,
) -> StagedStateHome:
    """Copy/verify state after independently proven exclusive-writer fencing.

    This operation deliberately stops before any host activation or pointer
    promotion. Authenticated human approval and writer fencing must be
    established OUTSIDE the model and supplied via a trusted controller.
    """
    if not isinstance(proof, RelocationAuthorization):
        raise TypeError("typed relocation authorization required")
    if not callable(independently_verify_authorization):
        raise TypeError("independent control-plane approval verifier required")
    if not isinstance(backup_engine, BackupEngine):
        raise TypeError("existing encrypted BackupEngine required")
    if (
        not isinstance(erasure_journal_path, Path)
        or not erasure_journal_path.is_absolute()
    ):
        raise ValueError(
            "current external memory deletion journal required for relocated state"
        )
    if not isinstance(encrypted_backup_root, Path) or not encrypted_backup_root.is_absolute():
        raise ValueError("absolute operator-approved encrypted backup root required")
    if any(not isinstance(v, str) or not v.strip() for v in (
        proof.writer_host_id, proof.source_writer_host_id,
        proof.operator_approval_ref, proof.writer_fence_ref, failure_domain,
    )):
        raise ValueError("complete privileged approval and fencing provenance required")
    if type(proof.next_writer_epoch) is not int or proof.next_writer_epoch < 1:
        raise ValueError("positive next writer epoch required")
    if independently_verify_authorization(proof) is not True:
        raise PermissionError("writer fencing / owner approval was not verified")
    preflight = inspect_state_relocation(
        proof.source_state_path, proof.destination_root,
    )
    if not preflight.eligible_for_review:
        raise ValueError("relocation preflight rejected: " + ", ".join(preflight.blockers))
    unsafe = tuple(w for w in preflight.warnings if w.startswith((
        "unclassified_state_root_items:",
        "state_root_inventory_truncated",
        "missing_or_external_component:",
    )))
    if unsafe:
        raise ValueError("incomplete protected state manifest: " + "; ".join(unsafe))
    backup_root = encrypted_backup_root.absolute()
    origin = proof.source_state_path.absolute().parent
    destination = proof.destination_root.absolute()
    if (
        backup_root == origin or origin in backup_root.parents
        or backup_root == destination or destination in backup_root.parents
        or backup_root in origin.parents or backup_root in destination.parents
        or backup_root.is_symlink()
    ):
        raise ValueError("backup destination must be a separate approved location")
    bundle, _evidence = backup_engine.create(
        state_path=proof.source_state_path,
        destination_root=backup_root,
        source_host_id=proof.source_writer_host_id,
        failure_domain=failure_domain,
    )
    manifest = backup_engine.verify(bundle)
    if manifest.source_host_id != proof.source_writer_host_id:
        raise BackupError(
            "authenticated source host does not match fenced original writer"
        )
    # A backup can verify perfectly while omitting files it never collected.
    # Confirm that every persistent file in this operator-fenced home has an
    # entry in the authenticated encrypted manifest. Missing external assets
    # must be explicitly classified before another cutover attempt.
    archived = {entry.logical_path for entry in manifest.entries}
    transient_sqlite = {"sofia.db-wal", "sofia.db-shm", "sofia.db-journal"}
    persistent: set[str] = set()
    root = origin
    for item in root.rglob("*"):
        if item.is_symlink():
            raise BackupError("state relocation refuses symbolic-link entries")
        if not item.is_file():
            continue
        relative = item.relative_to(root).as_posix()
        if relative in transient_sqlite:
            continue
        persistent.add(relative)
    missing = sorted(persistent - archived)
    if missing:
        raise BackupError(
            "encrypted backup omits persistent state files: "
            + ", ".join(missing[:16])
        )
    if "sofia.db" not in archived:
        raise BackupError("authenticated backup manifest lacks canonical database")
    # Do NOT restore into the destination file-by-file. On interruption
    # that would strand a plausible but incomplete "Sofia" state home.
    # Restore into a fresh sibling on the SAME approved local filesystem,
    # and only publish a verified whole directory as a non-active candidate.
    # An existing destination, even an empty one, is not owned by staging.
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(
            "verified stage requires a fresh absent destination home"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(
            "verified stage destination appeared after preflight"
        )
    staging = Path(tempfile.mkdtemp(
        prefix=f".{destination.name}.restore-", dir=destination.parent,
    ))
    published = False
    try:
        restored = backup_engine.restore(
            backup_dir=bundle,
            target_state_path=staging / "sofia.db",
            verifier=f"approved-relocation:{proof.operator_approval_ref}",
            replace_existing=False,
            erasure_journal=erasure_journal_path,
        )
        if not restored.succeeded or restored.backup_id != manifest.backup_id:
            raise BackupError("staged restore did not match its verified manifest")
        if not (staging / "sofia.db").is_file():
            raise BackupError("verified staging claim has no canonical database")
        if not (staging / "protected" / "identity.json").is_file():
            raise BackupError("verified staging claim has no protected identity")
        # Recheck all destination ancestry before publication, never
        # silently replace a previously existing home. A host-privileged
        # cutover/fencing broker is still necessary for adversarial races.
        from sofia.ops.state_mobility import _unsafe_ancestor, _filesystem_kind
        if (
            destination.exists() or destination.is_symlink()
            or _unsafe_ancestor(destination)
            or _filesystem_kind(destination) != "local"
        ):
            raise BackupError(
                "destination was replaced, redirected or left local storage"
            )
        os.rename(staging, destination)
        published = True
    finally:
        if not published:
            # Deleting only our randomly created workdir never overwrites
            # the owner-selected destination or modifies the old writer.
            shutil.rmtree(staging)
    # Neither the bootstrap state pointer nor the active writer is touched.
    # A reviewed host-privileged cutover is independently required.
    return StagedStateHome(
        backup_dir=bundle,
        destination_state_path=destination / "sofia.db",
        backup_id=manifest.backup_id,
        writer_host_id=proof.writer_host_id,
        proposed_writer_epoch=proof.next_writer_epoch,
        verified_restore=True,
        activated=False,
    )
