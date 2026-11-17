"""Optional standalone browser capability."""
from .analysis import review_navigation_candidates, capability_registrations
from .sanitization import (
    sanitize_page_evidence,
    capability_registrations as sanitization_capability_registrations,
)
__all__ = [
    "review_navigation_candidates",
    "capability_registrations",
    "sanitize_page_evidence",
    "sanitization_capability_registrations",
]
