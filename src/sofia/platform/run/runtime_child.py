"""Headless child process used by the stable Windows runtime service host."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
from pathlib import Path
import sys
import time

from sofia.platform.application.bootstrap import SofiaApplication
from sofia.platform.config import create_production_configuration
from sofia.platform.run.heartbeat import ApplicationHeartbeatStore
from sofia.platform.state.atomic_file import atomic_write_text


def run_child(
    *,
    state_path: Path,
    ready_file: Path,
    stop_file: Path,
    start_token: str,
    expected_generation_epoch: int | None = None,
    poll_seconds: float = 0.5,
) -> None:
    if not state_path.is_file():
        raise FileNotFoundError("canonical state database does not exist")
    if not isinstance(start_token, str) or re.fullmatch(r"[0-9a-f]{32}", start_token) is None:
        raise ValueError("start_token must be an exact launch ID")
    if expected_generation_epoch is not None and (
        type(expected_generation_epoch) is not int or expected_generation_epoch < 1
    ):
        raise ValueError("expected_generation_epoch must be positive or None")
    if poll_seconds <= 0 or poll_seconds > 5:
        raise ValueError("poll_seconds must be in (0, 5]")
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        ready_file.unlink()
    except FileNotFoundError:
        pass

    heartbeat_store = (
        None if expected_generation_epoch is None
        else ApplicationHeartbeatStore(state_path)
    )

    def require_current_generation() -> None:
        if (
            heartbeat_store is not None
            and heartbeat_store.current_generation() != expected_generation_epoch
        ):
            raise PermissionError(
                "runtime generation changed; denying stale worker readiness"
            )

    # Reject a superseded generation before starting canonical application work.
    require_current_generation()
    application = SofiaApplication(
        create_production_configuration(state_path=state_path)
    )
    try:
        application.start()
        # Reject takeover during boot before publishing the ready marker.
        require_current_generation()
        atomic_write_text(
            ready_file,
            json.dumps(
                {
                    "pid": os.getpid(),
                    "ready_at": datetime.now(timezone.utc).isoformat(),
                    "state_path": str(state_path.resolve()),
                    "start_token": start_token,
                    "generation_epoch": expected_generation_epoch,
                },
                sort_keys=True,
            )
            + "\n",
        )
        while not stop_file.exists():
            require_current_generation()
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
        prog="python -m sofia.platform.run.runtime_child"
    )
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--ready-file", required=True)
    parser.add_argument("--stop-file", required=True)
    parser.add_argument("--start-token", required=True)
    parser.add_argument("--expected-generation-epoch", type=int)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    args = parser.parse_args(argv)
    try:
        run_child(
            state_path=Path(args.state_path),
            ready_file=Path(args.ready_file),
            stop_file=Path(args.stop_file),
            start_token=args.start_token,
            expected_generation_epoch=args.expected_generation_epoch,
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
