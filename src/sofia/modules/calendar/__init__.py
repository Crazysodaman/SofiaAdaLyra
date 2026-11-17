"""Optional read-only calendar advisory."""
from .analysis import review_schedule_conflicts, capability_registrations
from .parsing import (
    MAX_ICS_BYTES,
    capability_registrations as parsing_capability_registrations,
    review_ics_conflicts,
)
__all__ = [
    'MAX_ICS_BYTES',
    'capability_registrations',
    'parsing_capability_registrations',
    'review_ics_conflicts',
    'review_schedule_conflicts',
]
