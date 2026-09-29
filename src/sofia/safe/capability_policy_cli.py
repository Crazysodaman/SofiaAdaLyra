from __future__ import annotations

import argparse
from pathlib import Path
import sys

from sofia.config import create_production_configuration
from sofia.safe.capability_policy import (
    protected_capability_extras,
    set_protected_capability_extras,
)
from sofia.state.sqlite_plane import SQLiteStatePlane


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(
        prog="python -m sofia.safe.capability_policy_cli"
    )
    sub=parser.add_subparsers(dest="command",required=True)
    sub.add_parser("show")
    set_cmd=sub.add_parser("set")
    set_cmd.add_argument(
        "capabilities",
        nargs="*",
        help="Extra standing capability names. Empty list clears extras.",
    )
    parser.add_argument("--state-path")
    args=parser.parse_args(argv)
    try:
        configuration=create_production_configuration()
        state_path=(
            Path(args.state_path)
            if args.state_path
            else Path(configuration.state_path)
        )
        plane=SQLiteStatePlane(state_path)
        if args.command=="show":
            values=protected_capability_extras(plane)
        else:
            record=set_protected_capability_extras(
                plane,
                capabilities=args.capabilities,
            )
            values=tuple(record.value)
        print("protected_capability_extras=" + ",".join(values))
        return 0
    except (OSError,PermissionError,RuntimeError,TypeError,ValueError) as exc:
        print(
            f"Capability policy refused: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__=="__main__":
    raise SystemExit(main())
