"""Permission-scoped statistical learning foundations.

The learning service owns lineage, immutable feature/evaluation manifests and
candidate diagnostics.  It owns no scheduler, factual evidence, capability,
permission, consent, or execution authority.
"""

from .contracts import (
    DataUse,
    DataUseGrant,
    OutcomeClass,
    Prediction,
    PredictionMode,
    SourceClass,
)
from .service import LearningService
from .fleet_pressure import FleetPressurePilot

__all__ = (
    "DataUse",
    "DataUseGrant",
    "LearningService",
    "FleetPressurePilot",
    "OutcomeClass",
    "Prediction",
    "PredictionMode",
    "SourceClass",
)
