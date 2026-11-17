"""Optional deterministic numeric analytics module."""
from .analysis import summarize_numeric, capability_registrations
from .parsing import (
    MAX_CSV_BYTES,
    capability_registrations as parsing_capability_registrations,
    summarize_numeric_csv,
)
__all__ = [
    'MAX_CSV_BYTES',
    'capability_registrations',
    'parsing_capability_registrations',
    'summarize_numeric',
    'summarize_numeric_csv',
]
