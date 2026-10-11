"""Explicit local owner credential provisioning on the *current* Venus writer.

No public RPC, model tool, unattended service or network endpoint can invoke
the first-trust workflow. Run while signed into the intended Venus desktop.
"""
from __future__ import annotations

import argparse
import json
import sys

from sofia.config import production_state_path
from sofia.safe.owner_enroll_browser import (
    enroll_attended, require_venus_interactive_windows,
)
from sofia.safe.owner_webauthn import OwnerWebAuthnVerifier


def _confirm(phrase: str) -> None:
    if not sys.stdin.isatty():
        raise PermissionError("interactive owner terminal required")
    print("This will change Sofía's canonical owner authenticator trust.")
    print("Only perform this from your own signed-in Venus desktop session.")
    print("The browser must explicitly prompt for Windows Hello or your FIDO2 key.")
    typed = input(f'Type "{phrase}" to proceed: ')
    if typed != phrase:
        raise PermissionError("operator did not confirm the enrollment")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m sofia.safe.owner_enroll_cli")
    sub = p.add_subparsers(dest="action", required=True)
    sub.add_parser("list", help="Review registered credentials (no host mutations)")
    first = sub.add_parser("first-hello")
    first.add_argument(
        "--acknowledge-sole-writer",
        action="store_true",
        help="Explicitly acknowledge this is the *currently authorized* Venus writer",
    )
    add = sub.add_parser("add-key")
    add.add_argument(
        "--authorized-by",
        required=True,
        help="Credential ID of an existing enrolled owner authenticator",
    )
    add.add_argument(
        "--kind", choices=("security_key", "platform"),
        default="security_key",
    )
    args = p.parse_args(argv)
    try:
        # First trust cannot depend on an arbitrary --state-path, copied DB,
        # environment-specified alternate writer or unattended automation.
        state = production_state_path()
        if args.action == "list":
            from contextlib import closing
            existing = OwnerWebAuthnVerifier(
                state, rp_id="localhost", origin="http://localhost:39872",
            )
            with closing(existing._db()) as db:
                items = db.execute(
                    "SELECT credential_id,credential_kind,enrolled_at,revoked_at "
                    "FROM safe_owner_credential ORDER BY enrolled_at"
                ).fetchall()
            print(json.dumps([dict(row) for row in items], indent=2))
            return 0
        require_venus_interactive_windows()
        if args.action == "first-hello":
            if not args.acknowledge_sole_writer:
                raise PermissionError(
                    "first enrollment requires --acknowledge-sole-writer"
                )
            _confirm("ENROLL SOFIA WINDOWS HELLO")
            cid = enroll_attended(state, kind="platform")
        elif args.action == "add-key":
            _confirm("REGISTER SOFIA OWNER KEY")
            cid = enroll_attended(
                state, kind=args.kind,
                existing_credential_id=args.authorized_by,
            )
        else:
            raise RuntimeError("unhandled owner enrollment operation")
        print(json.dumps({
            "enrollment": "completed",
            "credential_id": cid,
            "kind": "platform" if args.action == "first-hello" else args.kind,
            "authentication": "WebAuthn registration with user verification",
            "hardware_attestation": "unverified: attestation none",
            "writer_migration_performed": False,
        }, sort_keys=True))
        return 0
    except (OSError, RuntimeError, PermissionError, ValueError, TypeError) as exc:
        print(
            f"Owner enrollment refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
