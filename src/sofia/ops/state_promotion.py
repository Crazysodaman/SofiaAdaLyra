"""Offline operator handoff: prepare but NEVER activate a signed state-home pointer.

This module is not an autonomous relocation or writer-lease authority.
Only an independently approved, verified staged restore can be presented
to an externally privileged, single-writer fencing/cutover broker.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import sys
from typing import Callable

from sofia.platform.config.state_home_pointer import (
    _DOMAIN, _SCHEMA, _require_unredirected_path,
)
from sofia.ops.state_relocation import (
    RelocationAuthorization, StagedStateHome, _fsync_linux_entry,
)


class PendingHomePointerUncertain(RuntimeError):
    """Pointer bytes were published, but directory-entry durability is unknown."""


@dataclass(frozen=True, slots=True)
class PendingHomePointer:
    """Signed artifact for an operator, not a live runtime configuration."""

    pending_path: Path
    pointer_sha256: str
    writer_host_id: str
    new_epoch: int
    operator_approval_ref: str
    activated: bool = False


class OperatorHandoffKind(str, Enum):
    """A failover and a failback use the same fenced promotion protocol."""

    FAILOVER = "failover"
    FAILBACK = "failback"


@dataclass(frozen=True, slots=True)
class OperatorHandoffEvidence:
    """Externally witnessed facts required before a privileged cutover.

    These fields are inputs from the owner-controlled broker; constructing
    this value grants no authority.  The local process cannot establish a
    cross-host fence, reserve a global lease, or approve its own recovery.
    """

    kind: OperatorHandoffKind
    staged: StagedStateHome
    pending: PendingHomePointer
    authorization: RelocationAuthorization
    backup_integrity_ref: str
    promoted_writer_lease_ref: str
    old_runtime_fence_ref: str
    device_identity_ref: str
    audience_privacy_audit_ref: str
    uncertain_effects_review_ref: str
    old_writer_fenced: bool
    old_runtime_stopped: bool
    target_writer_lease_reserved: bool
    split_brain_absent: bool
    device_identity_continuity_verified: bool
    audience_privacy_verified: bool
    uncertain_effects_reconciled: bool
    observed_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class OperatorHandoffReview:
    """Read-only precondition result; never a writer-activation receipt."""

    kind: OperatorHandoffKind
    writer_host_id: str
    proposed_epoch: int
    blockers: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    reviewed_at: datetime
    may_activate_writer: bool = False

    @property
    def ready_for_privileged_broker(self) -> bool:
        return not self.blockers


def review_operator_handoff(
    evidence: OperatorHandoffEvidence, *, now: datetime,
    independently_verify_evidence: Callable[[OperatorHandoffEvidence], bool],
) -> OperatorHandoffReview:
    """Fail closed before an external broker considers failover or failback.

    This verifies the local, signed recovery artifacts and requires a fresh
    independent witness for cross-host facts.  It deliberately has no code
    path that edits the active pointer, starts Sofía, stops another runtime,
    mints a lease, or marks uncertain work successful.
    """
    if not isinstance(evidence, OperatorHandoffEvidence):
        raise TypeError("typed operator handoff evidence required")
    if (
        not isinstance(evidence.kind, OperatorHandoffKind)
        or not isinstance(evidence.staged, StagedStateHome)
        or not isinstance(evidence.pending, PendingHomePointer)
        or not isinstance(evidence.authorization, RelocationAuthorization)
    ):
        raise TypeError("handoff requires typed kind, staging, pointer and authorization")
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("review time must be timezone-aware")
    if not callable(independently_verify_evidence):
        raise TypeError("independent handoff evidence verifier required")
    if (
        evidence.observed_at.tzinfo is None
        or evidence.observed_at.utcoffset() is None
        or evidence.expires_at.tzinfo is None
        or evidence.expires_at.utcoffset() is None
        or evidence.expires_at <= evidence.observed_at
    ):
        raise ValueError("handoff evidence requires a bounded aware validity window")

    refs = (
        evidence.authorization.operator_approval_ref,
        evidence.authorization.writer_fence_ref,
        evidence.backup_integrity_ref,
        evidence.promoted_writer_lease_ref,
        evidence.old_runtime_fence_ref,
        evidence.device_identity_ref,
        evidence.audience_privacy_audit_ref,
        evidence.uncertain_effects_review_ref,
    )
    if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
        raise ValueError("complete external handoff evidence references required")

    blockers: list[str] = []
    staged, pending, authorization = (
        evidence.staged, evidence.pending, evidence.authorization,
    )
    if staged.activated or pending.activated:
        blockers.append("candidate_already_claims_activation")
    if not staged.verified_restore:
        blockers.append("backup_restore_not_verified")
    if (
        staged.writer_host_id != authorization.writer_host_id
        or pending.writer_host_id != authorization.writer_host_id
        or staged.proposed_writer_epoch != authorization.next_writer_epoch
        or pending.new_epoch != authorization.next_writer_epoch
        or pending.operator_approval_ref != authorization.operator_approval_ref
        or staged.destination_state_path != authorization.destination_root / "sofia.db"
    ):
        blockers.append("staged_handoff_identity_or_epoch_mismatch")
    if authorization.next_writer_epoch <= authorization.source_writer_epoch:
        blockers.append("writer_epoch_not_monotonic")
    if now < evidence.observed_at or now >= evidence.expires_at:
        blockers.append("handoff_evidence_not_current")
    try:
        _require_unredirected_path(
            pending.pending_path, label="pending handoff pointer",
        )
        _require_unredirected_path(
            staged.destination_state_path, label="staged handoff database",
        )
        _require_unredirected_path(
            staged.destination_state_path.parent / "protected" / "identity.json",
            label="staged handoff identity",
        )
        staged_files_current = (
            staged.destination_state_path.is_file()
            and (
                staged.destination_state_path.parent
                / "protected" / "identity.json"
            ).is_file()
        )
    except (OSError, PermissionError, RuntimeError, ValueError):
        staged_files_current = False
    if not staged_files_current:
        blockers.append("staged_database_or_identity_unavailable")
    if not pending.pending_path.is_file() or pending.pending_path.is_symlink():
        blockers.append("signed_pending_pointer_unavailable")
    else:
        try:
            pointer_digest = sha256(pending.pending_path.read_bytes()).hexdigest()
        except OSError:
            blockers.append("signed_pending_pointer_unreadable")
        else:
            if not hmac.compare_digest(pointer_digest, pending.pointer_sha256):
                blockers.append("signed_pending_pointer_digest_mismatch")
    if not evidence.old_writer_fenced:
        blockers.append("old_writer_not_fenced")
    if not evidence.old_runtime_stopped:
        blockers.append("old_runtime_not_stopped")
    if not evidence.target_writer_lease_reserved:
        blockers.append("new_writer_lease_not_reserved")
    if not evidence.split_brain_absent:
        blockers.append("split_brain_not_excluded")
    if not evidence.device_identity_continuity_verified:
        blockers.append("device_identity_continuity_unverified")
    if not evidence.audience_privacy_verified:
        blockers.append("post_restore_audience_privacy_unverified")
    if not evidence.uncertain_effects_reconciled:
        blockers.append("uncertain_external_effects_unreconciled")
    try:
        independently_verified = independently_verify_evidence(evidence) is True
    except Exception:
        independently_verified = False
    if not independently_verified:
        blockers.append("independent_privileged_witness_denied")

    return OperatorHandoffReview(
        kind=evidence.kind,
        writer_host_id=authorization.writer_host_id,
        proposed_epoch=authorization.next_writer_epoch,
        blockers=tuple(dict.fromkeys(blockers)),
        evidence_refs=refs,
        reviewed_at=now.astimezone(timezone.utc),
        may_activate_writer=False,
    )


def prepare_pending_state_pointer(
    *,
    staged: StagedStateHome,
    authorization: RelocationAuthorization,
    pointer_hmac_key: bytes,
    pending_path: Path,
    minimum_next_epoch: int,
    verify_privileged_handoff: Callable[
        [StagedStateHome, RelocationAuthorization], bool
    ],
) -> PendingHomePointer:
    """Create a new *.pending.json, never overwrite the active pointer.

    The privileged host agent must independently verify live fencing, user
    consent, identity and recovery evidence. This produces a reviewable file,
    not the promotion operation: the host agent separately protects and
    publishes the active pointer after finishing the verified cutover.
    """
    if not isinstance(staged, StagedStateHome):
        raise TypeError("verified StagedStateHome required")
    if not isinstance(authorization, RelocationAuthorization):
        raise TypeError("typed operator authorization required")
    if type(minimum_next_epoch) is not int or minimum_next_epoch < 1:
        raise ValueError("positive independent epoch floor required")
    if (
        type(authorization.source_writer_epoch) is not int
        or authorization.source_writer_epoch < 1
        or type(authorization.next_writer_epoch) is not int
        or authorization.next_writer_epoch <= authorization.source_writer_epoch
    ):
        raise ValueError("pending writer epoch must exceed witnessed old epoch")
    if any(
        not isinstance(value, str) or not value.strip()
        for value in (
            authorization.protected_operation_id,
            authorization.operator_principal_id,
            authorization.source_writer_host_id,
        )
    ):
        raise ValueError("exact operation, principal and original writer required")
    if not isinstance(pointer_hmac_key, bytes) or len(pointer_hmac_key) != 32:
        raise ValueError("32-byte external operator-controlled HMAC key required")
    if not isinstance(pending_path, Path) or not pending_path.is_absolute():
        raise ValueError("absolute pending pointer path required")
    if not pending_path.name.endswith(".pending.json"):
        raise ValueError("only a non-active .pending.json output is allowed")
    if staged.activated or not staged.verified_restore:
        raise ValueError("only nonactivated, verified staged restore may be signed")
    if (
        staged.writer_host_id != authorization.writer_host_id
        or staged.destination_state_path != authorization.destination_root / "sofia.db"
        or staged.proposed_writer_epoch != authorization.next_writer_epoch
        or staged.proposed_writer_epoch < minimum_next_epoch
    ):
        raise PermissionError("mismatched host, destination or writer epoch")
    if not isinstance(staged.backup_id, str) or not staged.backup_id:
        raise ValueError("staged backup evidence missing")
    if any(
        not isinstance(ref, str) or not ref.strip()
        for ref in (
            authorization.operator_approval_ref,
            authorization.writer_fence_ref,
            authorization.writer_host_id,
        )
    ):
        raise ValueError("operator approval and fencing identifiers required")
    if not callable(verify_privileged_handoff) or verify_privileged_handoff(
        staged, authorization
    ) is not True:
        raise PermissionError("external operator/cutover verifier denied handoff")
    # Resolve nothing before checking the original spelling. An HMAC over
    # a pending pointer must never be minted for a redirected candidate home,
    # SQLite database or protected identity (including parent junctions).
    _require_unredirected_path(
        staged.destination_state_path, label="staged canonical database",
    )
    _require_unredirected_path(
        staged.destination_state_path.parent / "protected" / "identity.json",
        label="staged protected identity",
    )
    home = staged.destination_state_path.parent.resolve(strict=True)
    if not staged.destination_state_path.is_file():
        raise FileNotFoundError("restored destination database missing")
    if not (home / "protected" / "identity.json").is_file():
        raise FileNotFoundError("protected identity missing from staged home")
    # A signed pointer does not bless a symlink/junction-controlled output
    # directory. Recheck the original spelling, not only its resolved target.
    _require_unredirected_path(pending_path, label="pending state-home pointer")
    parent = pending_path.parent.resolve(strict=True)
    if parent == home or home in parent.parents:
        raise ValueError("trusted bootstrap pointer must be outside state home")
    if pending_path.exists() or pending_path.is_symlink():
        raise FileExistsError("pending pointer already exists; never overwrite")
    payload = {
        "schema": _SCHEMA,
        "state_root": str(home),
        "writer_host_id": staged.writer_host_id,
        "epoch": staged.proposed_writer_epoch,
        "operator_approval_ref": authorization.operator_approval_ref,
    }
    signed_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    payload["hmac_sha256"] = hmac.new(
        pointer_hmac_key, _DOMAIN + signed_bytes, sha256
    ).hexdigest()
    document = (json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) + "\n").encode("utf-8")
    # A long sequence of file/path validation and HMAC preparation may
    # outlive the original privileged handoff approval. Refuse to publish
    # even a pending artifact once that approval has been withdrawn.
    if verify_privileged_handoff(staged, authorization) is not True:
        raise PermissionError(
            "privileged handoff approval expired before pending pointer creation"
        )
    _require_unredirected_path(pending_path, label="pending state-home pointer")
    _require_unredirected_path(
        staged.destination_state_path, label="staged canonical database",
    )
    _require_unredirected_path(
        staged.destination_state_path.parent / "protected" / "identity.json",
        label="staged protected identity",
    )
    # Atomic exclusive creation. No replace of live files. The operator-owned
    # destination directory and its ACLs must be validated by the broker.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(pending_path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(document)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        pending_path.unlink(missing_ok=True)
        raise
    # fsync(file) is insufficient to guarantee the newly created pathname
    # survives an abrupt Linux crash. Once the bytes are published, a parent
    # sync failure is UNCERTAIN, never permission to retry by overwriting.
    if sys.platform.startswith("linux"):
        try:
            _fsync_linux_entry(pending_path.parent, directory=True)
        except OSError as exc:
            raise PendingHomePointerUncertain(
                "signed pending pointer exists but durable publication is "
                "uncertain; inspect it before preparing another handoff"
            ) from exc
    return PendingHomePointer(
        pending_path, sha256(document).hexdigest(),
        staged.writer_host_id, staged.proposed_writer_epoch,
        authorization.operator_approval_ref,
    )
