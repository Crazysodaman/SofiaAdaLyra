"""Evidence-backed habit learning for Sofía."""
from .context import habit_context_from_environment
from .detector import HabitPatternDetector
from .expectation import HabitExpectationEngine
from .model import (
    CoverageState,
    ExpectationStatus,
    HabitExpectation,
    HabitObservation,
    HabitPattern,
    HabitStatus,
    ObservationCoverage,
    ObservationSource,
)
from .projection import habit_prompt
from .service import HabitLearningService
from .store import HabitStore

__all__ = [
    "CoverageState",
    "ExpectationStatus",
    "HabitExpectation",
    "HabitLearningService",
    "HabitObservation",
    "HabitPattern",
    "HabitPatternDetector",
    "HabitStatus",
    "HabitStore",
    "HabitExpectationEngine",
    "ObservationCoverage",
    "ObservationSource",
    "habit_context_from_environment",
    "habit_prompt",
]
