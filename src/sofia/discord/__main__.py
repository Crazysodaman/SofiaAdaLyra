"""Explicit Discord process and local operator entry point."""

from __future__ import annotations

import sys

from sofia.discord.live import main as live_main
from sofia.discord.operator import main as operator_main


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args == ["run"]:
        return live_main()
    if len(args) == 1 and args[0] in {"status", "pause", "resume", "revoke", "reenroll"}:
        return operator_main(args[0])
    print(
        "Usage: python -m sofia.discord [run|status|pause|resume|revoke|reenroll]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
