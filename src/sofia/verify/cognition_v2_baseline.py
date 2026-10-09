"""Capture an honest, reproducible Cognition v1 control-path baseline.

This Batch 1 harness deliberately uses the deterministic test engine so it can
run in CI without claiming live Ollama, GPU, token, or residency measurements.
Unavailable measurements remain explicit nulls with reasons. Live-model
benchmarks are a separate host acceptance step.
"""
from __future__ import annotations

import argparse
from contextlib import suppress
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import tempfile
from time import perf_counter, process_time, sleep
from typing import Callable

from sofia.application import SofiaApplication
from sofia.config.model import ProviderConfiguration, SofiaConfiguration


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _rss_peak_bytes() -> int | None:
    try:
        import resource
    except ImportError:
        return None
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if not isinstance(value, int) or value < 0:
        return None
    # Linux reports KiB; macOS reports bytes.
    return value if platform.system() == "Darwin" else value * 1024


def _revision() -> str | None:
    with suppress(OSError, subprocess.SubprocessError):
        result = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        value = result.stdout.strip()
        return value or None
    return None


def _configuration(root: Path) -> SofiaConfiguration:
    personality = root / "personality.json"
    personality.write_text(
        json.dumps({
            "name": "Sofía",
            "traits": ["rigorous", "curious", "direct"],
            "communication_style": "Clear, direct, and analytical.",
        }),
        encoding="utf-8",
    )
    source = PROJECT_ROOT / "src" / "sofia"
    return SofiaConfiguration(
        constitution_path=str(source / "constitution" / "constitution.md"),
        constitution_hash_path=str(
            source / "constitution" / "constitution.sha256"
        ),
        identity_path=str(source / "identity" / "identity.json"),
        personality_path=str(personality),
        avatar_path=str(source / "embodiment" / "avatar.json"),
        state_path=str(root / "sofia.db"),
        provider=ProviderConfiguration(provider="test", model="test"),
        filesystem_root=PROJECT_ROOT,
    )


def _measure(operation: Callable[[], object]) -> dict[str, float | int | None]:
    wall_started = perf_counter()
    cpu_started = process_time()
    operation()
    return {
        "wall_ms": round((perf_counter() - wall_started) * 1000, 3),
        "process_cpu_ms": round((process_time() - cpu_started) * 1000, 3),
        "peak_rss_bytes": _rss_peak_bytes(),
    }


def _database_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as db:
        tables = {
            row[0]
            for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        return {
            "conversation_messages": (
                db.execute("SELECT COUNT(*) FROM conversation_messages").fetchone()[0]
                if "conversation_messages" in tables else 0
            ),
            "matrix_traces": (
                db.execute("SELECT COUNT(*) FROM cognition_matrix_trace").fetchone()[0]
                if "cognition_matrix_trace" in tables else 0
            ),
            "database_bytes": path.stat().st_size,
        }


def capture_baseline() -> dict[str, object]:
    """Run fixed control-path scenarios and return machine-readable evidence."""
    with tempfile.TemporaryDirectory(prefix="sofia-cognition-v2-baseline-") as raw:
        root = Path(raw)
        configuration = _configuration(root)
        startup_started = perf_counter()
        startup_cpu_started = process_time()
        application = SofiaApplication(configuration)
        application.start()
        startup = {
            "wall_ms": round((perf_counter() - startup_started) * 1000, 3),
            "process_cpu_ms": round(
                (process_time() - startup_cpu_started) * 1000,
                3,
            ),
            "peak_rss_bytes": _rss_peak_bytes(),
        }
        try:
            scenarios = {
                "casual_conversation": _measure(
                    lambda: application.conversation.respond("How are you?")
                ),
                "technical_question": _measure(
                    lambda: application.conversation.respond(
                        "Explain why a SQLite transaction can become locked."
                    )
                ),
                "fleet_status_request": _measure(
                    lambda: application.conversation.respond(
                        "Can you see Artemis?"
                    )
                ),
                "multi_turn_followup": _measure(
                    lambda: application.conversation.respond("What's her CPU?")
                ),
            }
            idle = _measure(lambda: sleep(0.25))
            database = _database_counts(Path(configuration.state_path))
        finally:
            application.shutdown()

    unavailable = {
        "prompt_tokens": "deterministic test engine exposes no tokenizer counts",
        "generation_tokens": "deterministic test engine exposes no tokenizer counts",
        "sqlite_operation_count": (
            "current stores own separate connections and expose no shared counter"
        ),
        "gpu_load": "no portable production GPU observer was active",
        "vram_bytes": "no portable production VRAM observer was active",
        "model_residency": "test engine has no Ollama residency",
        "primary_model_inference": "live primary model was not invoked",
        "secondary_model_inference": "live secondary model was not invoked",
        "verify_inference": "live VERIFY route was not invoked",
    }
    return {
        "schema": "sofia.cognition-v2.baseline-v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "revision": _revision(),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "provider": "test",
            "model": "test",
            "measurement_scope": "existing production control path",
        },
        "startup": startup,
        "scenarios": scenarios,
        "idle_250ms": idle,
        "database": database,
        "unavailable": unavailable,
        "interpretation": (
            "These values baseline application/Matrix/NEURO/context/persistence "
            "overhead in this CI host. They are not live-model latency evidence."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    payload = json.dumps(capture_baseline(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(payload, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
