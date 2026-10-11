"""Read-only, authenticated location of the canonical production state home.

Bootstrap trust lives OUTSIDE sofia.db, so relocation can be discovered after
restart. This does not fence writers or authorize a move; it only verifies a
previously operator-approved, host-bound location record. No file is written.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path


_SCHEMA = "sofia.state-home-pointer.v1"
_DOMAIN = b"sofia-state-home-pointer-v1\0"


@dataclass(frozen=True, slots=True)
class VerifiedStateHome:
    root: Path
    writer_host_id: str
    epoch: int
    operator_approval_ref: str


def read_verified_state_home(
    *, pointer_path: Path, key_path: Path, expected_writer_host_id: str,
    minimum_writer_epoch: int = 1,
) -> VerifiedStateHome:
    """Require exact HMAC, writer host and canonical protected-state presence.

    Authenticated bootstrap is necessary but does not guarantee a prior
    machine is fenced. Operational cutover MUST be separately approved and
    proven by a privileged broker with an exclusive writer lease/epoch.
    """
    if not isinstance(pointer_path, Path) or not isinstance(key_path, Path):
        raise TypeError("trusted pointer and key must be Paths")
    if (
        not isinstance(expected_writer_host_id, str)
        or not expected_writer_host_id.strip()
        or len(expected_writer_host_id) > 160
    ):
        raise ValueError("exact host identity required")
    if type(minimum_writer_epoch) is not int or minimum_writer_epoch < 1:
        raise ValueError("positive external writer epoch floor required")
    if pointer_path.is_symlink() or key_path.is_symlink():
        raise PermissionError("state-home trust files must not be symlinks")
    raw_key = key_path.read_bytes()
    if len(raw_key) != 32:
        raise ValueError("external state-home pointer HMAC key must be 32 bytes")
    if pointer_path.stat().st_size > 16_384:
        raise ValueError("state-home bootstrap pointer exceeds size policy")
    document = json.loads(pointer_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {
        "schema", "state_root", "writer_host_id",
        "epoch", "operator_approval_ref", "hmac_sha256",
    }:
        raise ValueError("unknown or incomplete state-home pointer schema")
    signature = document.pop("hmac_sha256")
    if not isinstance(signature, str) or len(signature) != 64:
        raise ValueError("invalid state-home signature")
    canonical = json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    calculated = hmac.new(raw_key, _DOMAIN + canonical, sha256).hexdigest()
    if not hmac.compare_digest(signature, calculated):
        raise PermissionError("state-home location record failed authentication")
    if document["schema"] != _SCHEMA:
        raise ValueError("unsupported state-home pointer version")
    host = document["writer_host_id"]
    if host != expected_writer_host_id:
        raise PermissionError("state home was authorized for a different host")
    epoch = document["epoch"]
    if type(epoch) is not int or epoch < minimum_writer_epoch:
        raise ValueError("state-home writer epoch is invalid or too old")
    receipt = document["operator_approval_ref"]
    if not isinstance(receipt, str) or not receipt.strip() or len(receipt) > 300:
        raise ValueError("operator-approved cutover reference required")
    root_value = document["state_root"]
    if not isinstance(root_value, str) or not root_value.strip():
        raise ValueError("state root missing")
    root = Path(root_value)
    if not root.is_absolute() or os.fspath(root).startswith(("\\\\", "//")):
        raise ValueError("canonical state root must be an absolute host-local path")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("state home must exist as a real directory")
    resolved_root = root.resolve(strict=True)
    if (
        resolved_root == key_path.resolve(strict=True)
        or resolved_root in key_path.resolve(strict=True).parents
        or resolved_root == pointer_path.resolve(strict=True)
        or resolved_root in pointer_path.resolve(strict=True).parents
    ):
        raise ValueError("trust key and location pointer must live outside the state home")
    if not (root / "sofia.db").is_file():
        raise FileNotFoundError("verified state home lacks sofia.db")
    if not (root / "protected" / "identity.json").is_file():
        raise FileNotFoundError("verified state home lacks protected identity")
    return VerifiedStateHome(root, host, epoch, receipt)
