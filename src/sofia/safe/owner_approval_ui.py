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


def select_security_key_for_settings(state_path: Path | str, *, parent) -> str:
    """Use one reviewed key, or ask the operator to identify which of many."""
    from tkinter import simpledialog

    active = active_owner_credentials(state_path, kind="security_key")
    if not active:
        raise PermissionError(
            "no supervised FIDO2 security key enrolled; use owner_enroll_cli "
            "from the signed-in Venus desktop before protected approvals"
        )
    if len(active) == 1:
        return active[0]
    selected = simpledialog.askstring(
        "Choose enrolled Sofía FIDO2 key",
        "Multiple security keys are registered. Enter the exact credential ID "
        "of the key you intend to use:\n\n" + "\n".join(active),
        parent=parent,
    )
    if selected is None:
        raise PermissionError("operator canceled credential selection")
    if selected not in active:
        raise PermissionError("selected FIDO2 credential is not active")
    return selected
