"""Offline operator handoff: prepare but NEVER activate a signed state-home pointer.

This module is not an autonomous relocation or writer-lease authority.
Only an independently approved, verified staged restore can be presented
to an externally privileged, single-writer fencing/cutover broker.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
from typing import Callable

from sofia.config.state_home_pointer import _DOMAIN, _SCHEMA
from sofia.ops.state_relocation import RelocationAuthorization, StagedStateHome


@dataclass(frozen=True, slots=True)
class PendingHomePointer:
    """Signed artifact for an operator, not a live runtime configuration."""

    pending_path: Path
    pointer_sha256: str
    writer_host_id: str
    new_epoch: int
    operator_approval_ref: str
    activated: bool = False


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
    home = staged.destination_state_path.parent.resolve(strict=True)
    if not staged.destination_state_path.is_file():
        raise FileNotFoundError("restored destination database missing")
    if not (home / "protected" / "identity.json").is_file():
        raise FileNotFoundError("protected identity missing from staged home")
    if pending_path.parent.resolve(strict=True) == home or (
        home in pending_path.parent.resolve(strict=True).parents
    ):
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
    return PendingHomePointer(
        pending_path, sha256(document).hexdigest(),
        staged.writer_host_id, staged.proposed_writer_epoch,
        authorization.operator_approval_ref,
    )
