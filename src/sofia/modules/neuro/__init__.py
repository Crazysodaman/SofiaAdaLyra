"""Lightweight event-driven neural/control layer for Sofía.

NEURO is a prioritization subsystem, not an evidence, authority, memory,
consent, or execution source.
"""
from .homeostasis import HomeostasisController
from .model import (
    HomeostaticState,
    NeuralActivation,
    NeuralSignal,
    NeuroRoutingDecision,
    NeuroStateSnapshot,
    NeuroWakeMode,
)
from .coordinator import NeuroInputCoordinator
from .runtime import NeuroRuntime
from .salience import SalienceNetwork
from .store import NeuroObservabilityStore
from .sensory import BodyReflexObservation, VoiceSensoryObservation

__all__ = [
    "HomeostaticState",
    "BodyReflexObservation",
    "HomeostasisController",
    "NeuralActivation",
    "NeuralSignal",
    "NeuroInputCoordinator",
    "NeuroObservabilityStore",
    "NeuroRoutingDecision",
    "NeuroRuntime",
    "NeuroStateSnapshot",
    "NeuroWakeMode",
    "SalienceNetwork",
    "VoiceSensoryObservation",
]
