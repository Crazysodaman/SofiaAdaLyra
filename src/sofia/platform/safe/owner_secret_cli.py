"""Attended owner-secret lifecycle. Never accepts a secret through argv."""
from __future__ import annotations

import argparse
import getpass
import secrets
import sys

from sofia.platform.config import production_state_path
from sofia.platform.safe.owner_secret import OwnerSecretStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.platform.safe.owner_secret_cli"
    )
    parser.add_argument("command", choices=("status", "init", "rotate"))
    parser.add_argument("--state-path", help="Use only an authorized canonical test state")
    args = parser.parse_args(argv)
    try:
        from pathlib import Path
        path = Path(args.state_path) if args.state_path else production_state_path()
        store = OwnerSecretStore(path)
        if args.command == "status":
            print("owner_secret=" + ("enrolled" if store.enabled() else "not_enrolled"))
            return 0
        if not sys.stdin.isatty():
            raise PermissionError("an interactive owner terminal is required")
        if args.command == "init":
            if store.enabled():
                raise PermissionError("owner secret is already enrolled")
            print("Requires attended signed-in Venus Windows owner.")
            print("This secret will be shown ONCE. Store it offline, not in Git.")
            if input('Type "ENROLL OWNER SECRET" to proceed: ') != "ENROLL OWNER SECRET":
                raise PermissionError("enrollment canceled")
            secret = secrets.token_hex(32)
            store.enroll(secret)
            print("YOUR 256-BIT OWNER SECRET (COPY OFFLINE NOW):")
            print(secret)
            print("It cannot be retrieved from the database.")
        elif args.command == "rotate":
            old = getpass.getpass("Current owner secret (hidden): ")
            if input('Type "ROTATE OWNER SECRET" to proceed: ') != "ROTATE OWNER SECRET":
                raise PermissionError("rotation canceled")
            new = secrets.token_hex(32)
            store.rotate(old, new)
            print("NEW OWNER SECRET (COPY OFFLINE NOW):")
            print(new)
            print("Existing software approvals for the previous key are revoked.")
        return 0
    except (OSError, PermissionError, RuntimeError, ValueError, TypeError) as exc:
        print("Owner-secret operation refused: " + type(exc).__name__,
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
