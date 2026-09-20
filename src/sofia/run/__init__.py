"""Opt-in, bounded runtime opportunity primitives; no daemon starts on import."""

from .periodic import (
    OpportunityPolicy,
    OpportunityResult,
    PeriodicThoughtGate,
    PeriodicThoughtRunner,
)

__all__ = (
    "OpportunityPolicy",
    "OpportunityResult",
    "PeriodicThoughtGate",
    "PeriodicThoughtRunner",
)
