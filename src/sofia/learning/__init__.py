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

__all__ = (
    "DataUse",
    "DataUseGrant",
    "LearningService",
    "OutcomeClass",
    "Prediction",
    "PredictionMode",
    "SourceClass",
)
