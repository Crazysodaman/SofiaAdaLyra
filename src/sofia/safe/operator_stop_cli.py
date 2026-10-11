from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sofia.config import production_state_path
from sofia.safe.operator_stop import OperatorStopStore


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(
        prog="python -m sofia.safe.operator_stop_cli"
    )
    parser.add_argument("state",choices=("on","off","status"))
    parser.add_argument("--state-path")
    parser.add_argument("--reason",default="operator request")
    parser.add_argument(
        "--credential-id",
        help="Enrolled FIDO2 security key required only for clearing a stop",
    )
    args=parser.parse_args(argv)
    try:
        path=(
            Path(args.state_path)
            if args.state_path
            else production_state_path()
        )
        store=OperatorStopStore(path)
        if args.state=="status":
            state=store.current()
        else:
            approval_id = None
            if args.state == "off":
                if not args.credential_id:
                    raise PermissionError("operator resume requires --credential-id")
                from sofia.safe.owner_browser import authorize_exact_action
                approval = authorize_exact_action(
                    path, capability="operator.stop.resume",
                    parameters={"active": False, "reason": args.reason.strip()},
                    credential_id=args.credential_id,
                    expires_seconds=90,
                )
                approval_id = approval.approval_id
            state=store.set(
                active=args.state=="on",
                updated_by="Sparks",
                reason=args.reason,
                approval_id=approval_id,
            )
        print(
            f"operator_stop={'on' if state.active else 'off'} "
            f"updated_by={state.updated_by} "
            f"updated_at={state.updated_at.isoformat()} "
            f"reason={state.reason}"
        )
        return 0
    except (OSError,PermissionError,RuntimeError,TypeError,ValueError) as exc:
        print(
            f"Operator stop refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__=="__main__":
    raise SystemExit(main())
