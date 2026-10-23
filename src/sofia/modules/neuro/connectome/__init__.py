"""Experimental connectome-inspired research; never production authority."""

from .circuits import CircuitEdge, CircuitSpec, selected_circuits
from .competition import CircuitCompetition, CompetitionResult
from .associative import AssociationCandidate, SparseAssociativeMemory

__all__ = [
    "AssociationCandidate", "CircuitCompetition", "CircuitEdge", "CircuitSpec",
    "CompetitionResult", "SparseAssociativeMemory", "selected_circuits",
]
