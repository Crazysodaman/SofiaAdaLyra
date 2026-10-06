"""Lightweight event-driven neural/control layer for Sofía.

NEURO is a prioritization subsystem, not an evidence, authority, memory,
consent, or execution source.
"""
from .homeostasis import HomeostasisController
from .model import (
    HomeostaticState,
    NeuralActivation,
    NeuralSignal,
    NeuroStateSnapshot,
)
from .runtime import NeuroRuntime
from .salience import SalienceNetwork

__all__ = [
    "HomeostaticState",
    "HomeostasisController",
    "NeuralActivation",
    "NeuralSignal",
    "NeuroRuntime",
    "NeuroStateSnapshot",
    "SalienceNetwork",
]
