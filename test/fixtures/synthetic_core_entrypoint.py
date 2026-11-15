"""Disposable synthetic Core entrypoint used by backend lifecycle tests.

This script intentionally imports nothing from ``sofia``. It reports readiness
through a backend-supplied control file, loops until a stop file or signal
arrives, and can be told to crash before or after readiness.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import time

READY_FILE_ENV = "SOFIA_SYNTHETIC_CORE_READY_FILE"
STOP_FILE_ENV = "SOFIA_SYNTHETIC_CORE_STOP_FILE"
GENERATION_ENV = "SOFIA_SYNTHETIC_CORE_GENERATION"


def _atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    ready_path = Path(os.environ[READY_FILE_ENV])
    stop_path = Path(os.environ[STOP_FILE_ENV])
    generation = int(os.environ[GENERATION_ENV])
    mode = os.environ.get("SOFIA_SYNTHETIC_CORE_MODE", "ready")
    dump_path = os.environ.get("SOFIA_SYNTHETIC_CORE_ENV_DUMP")

    if dump_path:
        _atomic_write(
            Path(dump_path),
            json.dumps(dict(sorted(os.environ.items())), sort_keys=True),
        )

    if mode == "crash-before-ready":
        return 7

    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    for name in ("SIGTERM", "SIGINT", "SIGBREAK"):
        candidate = getattr(signal, name, None)
        if candidate is None:
            continue
        try:
            signal.signal(candidate, request_stop)
        except (OSError, ValueError):
            pass

    _atomic_write(
        ready_path,
        json.dumps({
            "pid": os.getpid(),
            "generation": generation,
            "state": "ready",
        }),
    )
    ready_at = time.monotonic()
    while not stopping and not stop_path.exists():
        if mode == "crash-after-ready" and time.monotonic() - ready_at > 0.5:
            os._exit(9)
        time.sleep(0.02)

    try:
        ready_path.unlink()
    except FileNotFoundError:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
