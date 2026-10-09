"""Opt-in, content-free performance observations for local diagnosis.

No prompts, model output, file paths, identities or evidence references are
recorded. Missing provider metrics remain unknown rather than invented zeroes.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from threading import Lock
from time import process_time
from typing import Any

try:
    import resource
except ImportError:  # pragma: no cover - Windows
    resource = None


@dataclass(frozen=True)
class EfficiencySnapshot:
    cache_hits: int
    cache_misses: int
    sqlite_queries: int
    sqlite_writes: int
    llm_calls: int
    concurrent_model_calls: int
    peak_concurrent_model_calls: int
    process_cpu_ms: float
    peak_rss_bytes: int | None


class _EfficiencyLedger:
    def __init__(self) -> None:
        self.lock = Lock()
        self.cache_hits = self.cache_misses = 0
        self.sqlite_queries = self.sqlite_writes = 0
        self.llm_calls = self.concurrent_model_calls = 0
        self.peak_concurrent_model_calls = 0

    def snapshot(self) -> EfficiencySnapshot:
        with self.lock:
            usage = (
                None if resource is None
                else resource.getrusage(resource.RUSAGE_SELF)
            )
            rss = None if usage is None else int(usage.ru_maxrss)
            if rss is not None and sys.platform != "darwin":
                rss *= 1024
            return EfficiencySnapshot(
                self.cache_hits, self.cache_misses,
                self.sqlite_queries, self.sqlite_writes,
                self.llm_calls, self.concurrent_model_calls,
                self.peak_concurrent_model_calls,
                process_time() * 1000,
                rss,
            )


_LEDGER = _EfficiencyLedger()


def record_cache(*, hit: bool) -> None:
    with _LEDGER.lock:
        if hit:
            _LEDGER.cache_hits += 1
        else:
            _LEDGER.cache_misses += 1


def record_sqlite(*, write: bool) -> None:
    with _LEDGER.lock:
        _LEDGER.sqlite_queries += 1
        if write:
            _LEDGER.sqlite_writes += 1


def model_call_started() -> None:
    with _LEDGER.lock:
        _LEDGER.llm_calls += 1
        _LEDGER.concurrent_model_calls += 1
        _LEDGER.peak_concurrent_model_calls = max(
            _LEDGER.peak_concurrent_model_calls,
            _LEDGER.concurrent_model_calls,
        )


def model_call_finished() -> None:
    with _LEDGER.lock:
        _LEDGER.concurrent_model_calls = max(
            0, _LEDGER.concurrent_model_calls - 1,
        )


def efficiency_snapshot() -> EfficiencySnapshot:
    return _LEDGER.snapshot()


def performance_trace_enabled() -> bool:
    return os.environ.get("SOFIA_PERF_TRACE", "").strip() == "1"


def emit_performance(stage: str, **values: Any) -> None:
    """Write a concise diagnostic only when explicitly opted in.

    Callers must provide static stage names and numeric/unknown values only.
    The whitelist prevents accidental logging of user/model content.
    """
    if not performance_trace_enabled():
        return
    allowed = {
        "lock_wait_ms", "elapsed_ms", "load_ms", "prompt_eval_ms",
        "generation_ms", "provider_total_ms", "prompt_tokens",
        "generated_tokens", "context_tokens",
        "route_code", "routing_score", "fallback_count",
        "verification_passes",
        "cache_hits", "cache_misses", "sqlite_queries", "sqlite_writes",
        "llm_calls", "concurrent_model_calls", "peak_concurrent_model_calls",
        "process_cpu_ms", "peak_rss_bytes", "context_budget",
        "output_budget",
    }
    if stage not in {"conversation", "idle_reflection", "ollama", "router", "runtime"}:
        raise ValueError("Unsupported performance trace stage.")
    if set(values) - allowed:
        raise ValueError("Unsupported performance trace field.")
    parts = []
    for name, value in values.items():
        if value is None:
            parts.append(f"{name}=unknown")
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError("Performance metrics must be nonnegative numbers or unknown.")
        else:
            parts.append(f"{name}={value:.1f}" if isinstance(value, float) else f"{name}={value}")
    print(f"[sofia-perf] {stage} " + " ".join(parts), file=sys.stderr, flush=True)


def ollama_metric(response: object, field: str, *, duration: bool = False) -> float | int | None:
    """Read Ollama's optional counters; duration fields are nanoseconds."""
    value = getattr(response, field, None)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value / 1_000_000 if duration else value
