"""Independent it_security optional Sofía 2.0 capability."""
from .analysis import triage_findings, capability_registrations
from .exposure import (
    capability_registrations as exposure_capability_registrations,
    review_credential_exposure,
)

__all__ = [
    "triage_findings",
    "capability_registrations",
    "review_credential_exposure",
    "exposure_capability_registrations",
]
