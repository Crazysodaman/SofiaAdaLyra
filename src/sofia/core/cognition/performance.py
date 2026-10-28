"""Compatibility exports for platform-owned performance instrumentation.

The content-free efficiency ledger moved to ``sofia.platform.state.performance``
so Platform SQLite access does not import ``sofia.core``.
"""
from sofia.platform.state.performance import (
    EfficiencySnapshot,
    efficiency_snapshot,
    emit_performance,
    model_call_finished,
    model_call_started,
    ollama_metric,
    performance_trace_enabled,
    record_cache,
    record_sqlite,
)

__all__ = [
    "EfficiencySnapshot",
    "efficiency_snapshot",
    "emit_performance",
    "model_call_finished",
    "model_call_started",
    "ollama_metric",
    "performance_trace_enabled",
    "record_cache",
    "record_sqlite",
]
