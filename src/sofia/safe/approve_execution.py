from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4

from sofia.config import create_default_configuration
from sofia.safe.execution_approval import (
    ExecutionApproval,
    ExecutionApprovalVerifier,
    execution_fingerprint,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.safe.approve_execution"
    )
    parser.add_argument("--state-path")
    parser.add_argument("--capability", required=True)
    parser.add_argument(
        "--parameters-json",
        required=True,
        help="Exact capability parameter JSON, excluding approval_id.",
    )
    parser.add_argument("--ttl-seconds", type=int, default=900)
    parser.add_argument("--approved-by", default="Sparks")
    args = parser.parse_args(argv)

    try:
        parameters = json.loads(args.parameters_json)
        if not isinstance(parameters, dict):
            raise ValueError("--parameters-json must decode to an object")
        if "approval_id" in parameters:
            raise ValueError(
                "parameters must not contain approval_id; it is generated here"
            )
        if args.ttl_seconds < 30 or args.ttl_seconds > 86400:
            raise ValueError("ttl-seconds must be in 30..86400")
        if args.approved_by != "Sparks":
            raise PermissionError(
                "current operator approval must be explicitly recorded as Sparks"
            )

        now = datetime.now(timezone.utc)
        approval = ExecutionApproval(
            approval_id=str(uuid4()),
            capability=args.capability,
            request_fingerprint=execution_fingerprint(
                args.capability,
                parameters,
            ),
            approved_by=args.approved_by,
            approved_at=now,
            expires_at=now + timedelta(seconds=args.ttl_seconds),
        )
        state_path = (
            Path(args.state_path)
            if args.state_path
            else Path(create_default_configuration().state_path)
        )
        ExecutionApprovalVerifier(state_path).record(approval)
        print(
            json.dumps(
                {
                    "approval_id": approval.approval_id,
                    "capability": approval.capability,
                    "request_fingerprint": approval.request_fingerprint,
                    "approved_by": approval.approved_by,
                    "approved_at": approval.approved_at.isoformat(),
                    "expires_at": approval.expires_at.isoformat(),
                },
                sort_keys=True,
            )
        )
        return 0
    except (
        json.JSONDecodeError,
        OSError,
        PermissionError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        print(
            f"Execution approval refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
