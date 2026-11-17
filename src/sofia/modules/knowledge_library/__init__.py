"""Optional external document revision planning module."""
from .analysis import plan_revision_index, capability_registrations
from .references import (
    validate_reference_manifest,
    capability_registrations as reference_capability_registrations,
)
__all__ = [
    'plan_revision_index',
    'capability_registrations',
    'reference_capability_registrations',
    'validate_reference_manifest',
]
