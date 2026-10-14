"""Revision-bound, content-minimal companion baseline for V18 CA-002/CA-007.

This is an isolated deterministic integration measurement. It is not a live
Ollama, Venus/Artemis, avatar, voice, multi-day, or user-outreach acceptance.
It reuses the existing production-path Cognition v2 baseline rather than
creating a competing cognition stack or canonical state database.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable

from sofia.verify.cognition_v2_baseline import capture_baseline


SCENARIOS = (
    "casual_conversation",
    "technical_question",
    "fleet_status_request",
    "multi_turn_followup",
)
_MEASUREMENTS = ("wall_ms", "process_cpu_ms", "peak_rss_bytes")
_NONLIVE_CAPABILITIES = {
    "memory_temporal_correctness": "requires source-grounded correction/restart benchmark",
    "cross_device_topic_continuity": "requires authenticated multi-client handoff",
    "unsolicited_outreach_quality": "requires consenting audience and durable delivery receipts",
    "avatar_voice_synchronization": "requires observed renderer and speech device",
    "live_model_latency": "requires the enrolled live model provider",
    "gpu_vram_and_power": "requires trusted active-host GPU telemetry",
    "idle_model_wakeups": "requires a sustained idle host observation window",
    "novel_problem_transfer": "requires preregistered holdout problems and objective graders",
    "multi_day_recovery": "requires witnessed restarts and elapsed time",
}
_SHA = re.compile(r"^[0-9a-f]{40}$")


class BaselineIntegrityError(ValueError):
    """The baseline cannot substantiate its claimed source or measurements."""


def _exact_revision(repo: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "--verify", "HEAD"),
        cwd=repo, capture_output=True, text=True, check=True, timeout=10,
    )
    value = result.stdout.strip()
    if not _SHA.fullmatch(value):
        raise BaselineIntegrityError("baseline needs an exact Git commit")
    return value


def _validated_measurement(data: object) -> dict[str, int | float | None]:
    if not isinstance(data, dict):
        raise BaselineIntegrityError("missing measured timing record")
    output = {}
    for key in _MEASUREMENTS:
        value = data.get(key)
        if key == "peak_rss_bytes" and value is None:
            output[key] = None
        elif type(value) not in (int, float) or value < 0 or value != value:
            raise BaselineIntegrityError("invalid or unmeasured " + key)
        elif value == float("inf"):
            raise BaselineIntegrityError("nonfinite " + key)
        else:
            output[key] = value
    return output


def summarize_control_baseline(
    measured: dict[str, object], *, expected_revision: str,
) -> dict[str, object]:
    """Whitelisted metrics only. Never persist transcripts, private evidence or tokens."""
    if not isinstance(measured, dict) or not _SHA.fullmatch(expected_revision):
        raise BaselineIntegrityError("canonical revision and baseline required")
    if (
        measured.get("schema") != "sofia.cognition-v2.baseline-v1"
        or measured.get("revision") != expected_revision
    ):
        raise BaselineIntegrityError("measured baseline was not bound to exact HEAD")
    environment = measured.get("environment")
    counts = measured.get("database")
    efficiency = measured.get("efficiency")
    scenarios = measured.get("scenarios")
    unavailable = measured.get("unavailable")
    if (
        not isinstance(environment, dict)
        or environment.get("provider") != "test"
        or environment.get("model") != "test"
        or not isinstance(counts, dict)
        or counts.get("conversation_messages") != 8
        or counts.get("matrix_traces") != 4
        or not isinstance(efficiency, dict)
        or not isinstance(scenarios, dict)
        or set(scenarios) != set(SCENARIOS)
        or not isinstance(unavailable, dict)
    ):
        raise BaselineIntegrityError("deterministic scenario/count contract changed")
    required_unknown = (
        "primary_model_inference", "secondary_model_inference",
        "vram_bytes", "gpu_load", "model_residency",
    )
    if any(not isinstance(unavailable.get(key), str) or not unavailable[key]
           for key in required_unknown):
        raise BaselineIntegrityError("unmeasured live capability was misrepresented")
    counters = ("sqlite_queries", "sqlite_writes", "cache_hits",
                "cache_misses", "llm_calls")
    values = {}
    for name in counters:
        value = efficiency.get(name)
        if type(value) is not int or value < 0:
            raise BaselineIntegrityError("invalid instrumentation counter " + name)
        values[name] = value
    if values["sqlite_queries"] == 0 or values["sqlite_writes"] == 0:
        raise BaselineIntegrityError("baseline did not exercise durable state")
    if values["llm_calls"] != 0:
        raise BaselineIntegrityError("deterministic baseline invoked an LLM")
    measurements = {name: _validated_measurement(scenarios[name])
                    for name in SCENARIOS}
    startup = _validated_measurement(measured.get("startup"))
    if not isinstance(measured.get("idle_250ms"), dict):
        raise BaselineIntegrityError("no idle observation")
    idle = _validated_measurement(measured["idle_250ms"])
    contract = {
        "schema": "sofia.v18.companion-baseline-v1",
        "provider": "test",
        "scenario_names": SCENARIOS,
        "expected_messages": 8,
        "expected_matrix_traces": 4,
        "unavailable_capability_names": tuple(sorted(_NONLIVE_CAPABILITIES)),
    }
    fingerprint = sha256(
        json.dumps(contract, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "schema": contract["schema"],
        "revision": expected_revision,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "baseline_contract_sha256": fingerprint,
        "kind": "isolated_deterministic_production_control_path",
        "source_schema": measured["schema"],
        "source_engine": "sofia.verify.cognition_v2_baseline.capture_baseline",
        "scenario_timings": measurements,
        "startup_timing": startup,
        "idle_250ms_timing": idle,
        "durable_counts": {
            "conversation_messages": counts["conversation_messages"],
            "matrix_traces": counts["matrix_traces"],
        },
        "instrumentation": values,
        "not_measured": dict(_NONLIVE_CAPABILITIES),
        "acceptance": {
            "baseline_generated": True,
            "unit_tests": "not_attested_by_baseline",
            "full_ci": "not_attested_by_baseline",
            "venus_live": "not_attested_by_baseline",
            "multi_host": "not_attested_by_baseline",
        },
        "interpretation": (
            "Isolated deterministic CI measurements only; timings vary by runner. "
            "This file makes no release, real-world quality, privacy, or live-host claim."
        ),
    }


def capture_v18_baseline(*, repo: Path,
                         expected_revision: str,
                         capture: Callable[[], dict[str, object]] = capture_baseline
                         ) -> dict[str, object]:
    checkout = repo.resolve(strict=True)
    if not (checkout / ".git").exists():
        raise BaselineIntegrityError("exact Git checkout required")
    before = _exact_revision(checkout)
    if expected_revision != before:
        raise BaselineIntegrityError("requested revision differs from checked-out HEAD")
    result = summarize_control_baseline(capture(), expected_revision=before)
    if _exact_revision(checkout) != before:
        raise BaselineIntegrityError("Git HEAD changed during measurement")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m sofia.verify.v18_companion_baseline")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = capture_v18_baseline(
            repo=args.repo, expected_revision=args.expected_revision,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
        print("V18 baseline rejected: " + type(exc).__name__ + ": " + str(exc),
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
