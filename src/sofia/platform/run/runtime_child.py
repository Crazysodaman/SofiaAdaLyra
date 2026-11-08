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
from sofia.platform.run.runtime_authority import require_local_runtime_authority
from sofia.platform.run.process_lock import StateProcessLock
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
    if type(expected_generation_epoch) is not int or expected_generation_epoch < 1:
        raise PermissionError("Core runtime child requires a positive generation")
    if poll_seconds <= 0 or poll_seconds > 5:
        raise ValueError("poll_seconds must be in (0, 5]")
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    stop_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        ready_file.unlink()
    except FileNotFoundError:
        pass

    def require_current_authority() -> None:
        require_local_runtime_authority(
            state_path, expected_epoch=expected_generation_epoch,
        )

    # An OS process lock prevents overlapping service-hosted Core children.
    # The canonical cross-host writer and signed Platform admission are
    # distinct authority boundaries and remain independently required.
    with StateProcessLock(
        state_path, resource="core-runtime", owner_label="Core runtime child",
    ):
        require_current_authority()
        application = SofiaApplication(
            create_production_configuration(state_path=state_path)
        )
        try:
            application.start()
            # Reject takeover during boot before publishing the ready marker.
            require_current_authority()
            atomic_write_text(
                ready_file,
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "ready_at": datetime.now(timezone.utc).isoformat(),
                        "state_path": str(state_path.resolve()),
                        "start_token": start_token,
                        "phase": "PROCESS_READY",
                        "generation_epoch": expected_generation_epoch,
                    },
                    sort_keys=True,
                )
                + "\n",
            )
            while not stop_file.exists():
                require_current_authority()
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
