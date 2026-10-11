"""Local UI helpers for enrolled owner WebAuthn security-key selection.

Credential IDs are public routing identifiers, never passwords or independent
approval. All protected operations still verify one signed action challenge.
"""
from __future__ import annotations

from contextlib import closing
from pathlib import Path

from sofia.safe.owner_enroll_browser import require_owner_windows_account
from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier


def active_owner_credentials(
    state_path: Path | str, *, kind: str = "security_key",
) -> tuple[str, ...]:
    if kind not in ("security_key", "platform"):
        raise ValueError("unknown owner authenticator kind")
    require_owner_windows_account(state_path)
    verifier = OwnerWebAuthnVerifier(
        state_path, rp_id="localhost", origin="http://localhost:39872",
    )
    with closing(verifier._db()) as db:
        rows = db.execute(
            "SELECT credential_id FROM safe_owner_credential "
            "WHERE credential_kind=? AND revoked_at IS NULL "
            "ORDER BY enrolled_at,credential_id",
            (kind,),
        ).fetchall()
    return tuple(str(row["credential_id"]) for row in rows)


def select_owner_credential(
    state_path: Path | str, *, kind: str, parent=None,
) -> str:
    """Choose an enrolled authenticator for the signed owner ceremony."""
    from tkinter import simpledialog

    active = active_owner_credentials(state_path, kind=kind)
    if not active:
        raise PermissionError(
            "no enrolled " + kind + " owner credential; enroll on Venus "
            "from the independently authenticated operator CLI"
        )
    if len(active) == 1:
        return active[0]
    selected = simpledialog.askstring(
        "Choose enrolled Sofía owner authenticator",
        f"Choose an active {kind} credential ID:\n\n" + "\n".join(active),
        parent=parent,
    )
    if selected is None:
        raise PermissionError("operator canceled credential selection")
    if selected not in active:
        raise PermissionError("selected owner credential is not active")
    return selected


def select_security_key_for_settings(state_path: Path | str, *, parent) -> str:
    """Preserve the Settings API for physically supervised FIDO2 actions."""
    return select_owner_credential(state_path, kind="security_key", parent=parent)
