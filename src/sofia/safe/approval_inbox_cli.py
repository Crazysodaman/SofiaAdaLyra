"""Local operator interface for pending SAFE FIDO2 approvals.

Only 'approve' opens the owner-presence WebAuthn ceremony. This CLI is NOT a
network API or a model tool, and it never executes a requested host effect.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
import sys

from sofia.platform.config import production_state_path
from sofia.safe.approval_inbox import ApprovalInbox


def _json(item) -> str:
    return json.dumps(item, sort_keys=True, ensure_ascii=False, indent=2,
                      default=lambda value: value.isoformat() if isinstance(value, datetime)
                      else str(value))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.safe.approval_inbox_cli")
    actions = parser.add_subparsers(dest="command", required=True)

    requested = actions.add_parser("request", help="Queue an exact operation; never approve it")
    requested.add_argument("--capability", required=True)
    requested.add_argument("--parameters-json", required=True)

    listed = actions.add_parser("list", help="Display durable requests")
    listed.add_argument("--status", choices=(
        "pending", "reviewing", "approved", "denied", "cancelled", "expired",
    ))
    listed.add_argument("--limit", type=int, default=50)

    approved = actions.add_parser("approve", help="Attended security-key WebAuthn ceremony")
    approved.add_argument("--request-id", required=True)
    approved.add_argument("--credential-id", required=True)

    denied = actions.add_parser("deny", help="Owner rejects an unapproved request")
    denied.add_argument("--request-id", required=True)

    actions.add_parser("recover", help="Reconcile expired/crashed reviews without executing")
    notifications = actions.add_parser("notifications", help="Read unacknowledged outbox events")
    notifications.add_argument("--limit", type=int, default=50)

    args = parser.parse_args(argv)
    try:
        inbox = ApprovalInbox(production_state_path())
        if args.command == "request":
            parameters = json.loads(args.parameters_json)
            result = asdict(inbox.create(args.capability, parameters))
        elif args.command == "list":
            result = [asdict(r) for r in inbox.list_requests(
                status=args.status, limit=args.limit,
            )]
        elif args.command == "approve":
            result = asdict(inbox.approve_attended(
                args.request_id, credential_id=args.credential_id,
            ))
        elif args.command == "deny":
            result = asdict(inbox.deny_attended(args.request_id))
        elif args.command == "recover":
            result = {"reconciled": inbox.recover(), "effects_executed": 0}
        elif args.command == "notifications":
            result = [asdict(n) for n in inbox.notifications(limit=args.limit)]
        else:
            raise RuntimeError("unsupported inbox command")
        print(_json(result))
        return 0
    except (OSError, RuntimeError, PermissionError, ValueError,
            TypeError, KeyError, json.JSONDecodeError) as exc:
        print("Approval inbox refused: " + type(exc).__name__ + ": " + str(exc),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
