"""Headless child process used by the stable Windows runtime service host."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time

from sofia.application.bootstrap import SofiaApplication
from sofia.config import create_production_configuration
from sofia.state.atomic_file import atomic_write_text


def run_child(
    *,
    state_path: Path,
    ready_file: Path,
    stop_file: Path,
    poll_seconds: float = 0.5,
) -> None:
    if not state_path.is_file():
        raise FileNotFoundError("canonical state database does not exist")
    if poll_seconds <= 0 or poll_seconds > 5:
        raise ValueError("poll_seconds must be in (0, 5]")
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        ready_file.unlink()
    except FileNotFoundError:
        pass

    application = SofiaApplication(
        create_production_configuration(state_path=state_path)
    )
    try:
        application.start()
        atomic_write_text(
            ready_file,
            json.dumps(
                {
                    "pid": os.getpid(),
                    "ready_at": datetime.now(timezone.utc).isoformat(),
                    "state_path": str(state_path.resolve()),
                },
                sort_keys=True,
            )
            + "\n",
        )
        while not stop_file.exists():
            time.sleep(poll_seconds)
    finally:
        try:
            application.shutdown()
        finally:
            try:
                ready_file.unlink()
            except FileNotFoundError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sofia.run.runtime_child"
    )
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--stop-file", required=True)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    args = parser.parse_args(argv)
    try:
        run_child(
            state_path=Path(args.state_path),
            ready_file=Path(args.ready_file),
            stop_file=Path(args.stop_file),
            poll_seconds=args.poll_seconds,
        )
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(
            f"release runtime child failed: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
