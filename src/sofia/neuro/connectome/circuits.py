"""Provenance-linked selected Drosophila circuit motifs.

These specifications are research hypotheses, not a whole-brain simulation and
not biological ground truth. Prototype weights are normalized engineering
parameters; they are not claimed synapse counts.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CircuitEdge:
    source_group: str
    target_group: str
    sign_assumption: str
    weight: float
    weight_derivation: str


@dataclass(frozen=True, slots=True)
class CircuitSpec:
    circuit_id: str
    purpose: str
    biological_source: str
    source_url: str
    cell_groups: tuple[str, ...]
    edges: tuple[CircuitEdge, ...]
    simplifications: tuple[str, ...]
    sofia_mapping: str


def _edge(source, target, sign, weight):
    return CircuitEdge(
        source, target, sign, weight,
        "Normalized prototype parameter selected for bounded comparison; "
        "not a reproduced synapse count.",
    )


def selected_circuits() -> tuple[CircuitSpec, ...]:
    """Return inspectable motifs without installing them into NEURO v0.1."""
    central_complex = (
        "Hulse et al., A connectome of the Drosophila central complex reveals "
        "network motifs suitable for flexible navigation and context-dependent "
        "action selection, eLife (2021)."
    )
    return (
        CircuitSpec(
            "central-complex-action-selection",
            "Competing action channels with recurrent support and lateral inhibition.",
            central_complex, "https://doi.org/10.7554/eLife.66039",
            ("compass-like heading units", "fan-shaped-body integrators", "descending action channels"),
            (
                _edge("fan-shaped-body integrators", "descending action channels", "excitatory engineering assumption", 0.55),
                _edge("descending action channels", "descending action channels", "recurrent excitation prototype", 0.18),
                _edge("descending action channels", "competing action channels", "mutual inhibition prototype", -0.22),
            ),
            (
                "Cell types are grouped rather than represented neuron-by-neuron.",
                "Transmitters and signs remain explicit assumptions where not imported.",
                "No motor command or permission is produced.",
            ),
            "Optional comparison model for ACT/RUN next-task competition.",
        ),
        CircuitSpec(
            "salience-competition",
            "Winner-take-all attention over bounded signal channels.",
            "Dorkenwald et al., Neuronal wiring diagram of an adult brain, Nature (2024).",
            "https://doi.org/10.1038/s41586-024-07558-y",
            ("sensory projection groups", "integrator groups", "descending output groups"),
            (
                _edge("sensory projection groups", "integrator groups", "excitatory prototype", 0.62),
                _edge("integrator groups", "competing integrator groups", "lateral inhibition prototype", -0.28),
            ),
            (
                "Uses selected motifs only; no FlyWire graph is bundled or reproduced.",
                "Source provenance informs architecture, not factual runtime evidence.",
            ),
            "Experimental alternative to deterministic NEURO salience ranking.",
        ),
        CircuitSpec(
            "mushroom-body-association",
            "Sparse feature expansion and bounded reinforcement of associations.",
            "Li et al., The connectome of the adult Drosophila mushroom body provides insights into function, eLife (2020).",
            "https://doi.org/10.7554/eLife.62576",
            ("projection-neuron features", "Kenyon-cell-like sparse units", "output channels", "dopaminergic reinforcement channel"),
            (
                _edge("projection-neuron features", "Kenyon-cell-like sparse units", "sparse excitatory prototype", 0.45),
                _edge("Kenyon-cell-like sparse units", "output channels", "bounded learned association", 0.35),
                _edge("dopaminergic reinforcement channel", "bounded learned association", "modulatory update only", 0.08),
            ),
            (
                "Hash-based sparse expansion replaces biological connectivity.",
                "MEM eligibility, privacy, provenance, and retrieval remain authoritative.",
            ),
            "Candidate activation before, never instead of, MEM eligibility checks.",
        ),
        CircuitSpec(
            "central-complex-orientation",
            "Orientation persistence and competing navigation headings.",
            central_complex, "https://doi.org/10.7554/eLife.66039",
            ("compass-like heading units", "travel-direction integrators", "steering output channels"),
            (
                _edge("compass-like heading units", "travel-direction integrators", "excitatory prototype", 0.58),
                _edge("travel-direction integrators", "steering output channels", "signed steering prototype", 0.42),
            ),
            (
                "Abstract channels do not model geometry, gait, or servo timing.",
                "BODY safety/reflex handling always precedes this slow layer.",
            ),
            "Future Gaia orientation attention, never immediate hardware control.",
        ),
    )
