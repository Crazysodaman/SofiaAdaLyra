from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from uuid import uuid4

from sofia.config import create_production_configuration
from sofia.evolve.amendment import ProtectedTarget
from sofia.evolve.approval import AmendmentApproval, ApprovalAction
from sofia.evolve.revision import RevisionApproval
from sofia.safe.evolve_approval import DurableEvolutionApprovalVerifier


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.safe.evolve_approve"
    )
    parser.add_argument("--state-path")
    parser.add_argument(
        "--kind",
        required=True,
        choices=("protected", "revision"),
    )
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--proposal-fingerprint", required=True)
    parser.add_argument(
        "--target",
        choices=[item.value for item in ProtectedTarget],
        help="Required for protected identity/Constitution approvals.",
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=[item.value for item in ApprovalAction],
    )
    parser.add_argument("--ttl-seconds", type=int, default=900)
    parser.add_argument("--approved-by", default="Sparks")
    parser.add_argument(
        "--authority-reference",
        required=True,
        help="Operator-visible review/change reference.",
    )
    args = parser.parse_args(argv)

    try:
        if args.ttl_seconds < 30 or args.ttl_seconds > 86400:
            raise ValueError("ttl-seconds must be in 30..86400")
        if args.approved_by != "Sparks":
            raise PermissionError(
                "current EVOLVE approval authority is explicitly Sparks"
            )
        if args.kind == "protected" and args.target is None:
            raise ValueError("--target is required for protected approval")
        if args.kind == "revision" and args.target is not None:
            raise ValueError("--target is not used for revision approval")

        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=args.ttl_seconds)
        approval_id = str(uuid4())
        action = ApprovalAction(args.action)
        state_path = (
            Path(args.state_path)
            if args.state_path
            else Path(create_production_configuration().state_path)
        )
        verifier = DurableEvolutionApprovalVerifier(state_path)

        if args.kind == "protected":
            approval = AmendmentApproval(
                approval_id=approval_id,
                proposal_id=args.proposal_id,
                proposal_fingerprint=args.proposal_fingerprint,
                target=ProtectedTarget(args.target),
                action=action,
                approved_by=args.approved_by,
                approved_at=now,
                expires_at=expires,
                authority_reference=args.authority_reference,
            )
            verifier.record_amendment(approval)
        else:
            approval = RevisionApproval(
                approval_id=approval_id,
                proposal_id=args.proposal_id,
                proposal_fingerprint=args.proposal_fingerprint,
                action=action,
                approved_by=args.approved_by,
                approved_at=now,
                expires_at=expires,
                authority_reference=args.authority_reference,
            )
            verifier.record_revision(approval)

        print(
            "EVOLVE approval recorded "
            f"approval_id={approval_id} "
            f"proposal_id={args.proposal_id} "
            f"action={args.action} "
            f"expires_at={expires.isoformat()}"
        )
        return 0
    except (OSError, PermissionError, RuntimeError, TypeError, ValueError) as exc:
        print(
            f"EVOLVE approval refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
