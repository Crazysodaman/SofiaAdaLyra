"""Pure in-process interaction lab for synthetic text and resolved pointer fixtures.

This is not a UI client, a trusted observation producer, or an authorization
source. No filesystem, network, journal, model, renderer or device is opened.
Raw fixture text and intimate region names are never included in exported traces.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sofia.interaction.core import GESTURES, InteractionDecision, InteractionEngine

MAX_STEPS = 64


@dataclass(frozen=True)
class LabStep:
    step_id: str
    modality: str  # text, pointer, stop
    occurred_at: datetime
    text: str | None = None
    region_id: str | None = None
    gesture: str | None = None
    phase: str = "end"

    def __post_init__(self) -> None:
        if not isinstance(self.step_id, str) or not 0 < len(self.step_id) <= 60 or not self.step_id.isascii() or not all(
            c.isalnum() or c in "-_" for c in self.step_id
        ):
            raise ValueError("A bounded ASCII step identifier is required.")
        if not isinstance(self.occurred_at, datetime) or self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("Lab timestamps must be timezone-aware.")
        if self.modality == "text":
            if not isinstance(self.text, str) or not 0 < len(self.text) <= 160:
                raise ValueError("A bounded synthetic text input is required.")
            if self.region_id is not None or self.gesture is not None or self.phase != "end":
                raise ValueError("Text fixtures cannot supply pre-resolved gestures.")
        elif self.modality == "pointer":
            if self.text is not None or self.gesture not in GESTURES or self.phase not in ("begin", "update", "end", "cancel"):
                raise ValueError("A pointer fixture needs a valid resolved gesture and phase.")
            if self.region_id is not None and (not isinstance(self.region_id, str) or len(self.region_id) > 80):
                raise ValueError("Invalid synthetic region identifier.")
        elif self.modality == "stop":
            if self.text is not None or self.region_id is not None or self.gesture is not None or self.phase != "end":
                raise ValueError("A stop fixture cannot contain a gesture.")
        else:
            raise ValueError("Unsupported lab modality.")


@dataclass(frozen=True)
class LabScene:
    scene_id: str
    session_id: str
    steps: tuple[LabStep, ...]

    def __post_init__(self) -> None:
        for label, value in (("scene_id", self.scene_id), ("session_id", self.session_id)):
            if not isinstance(value, str) or not 0 < len(value) <= 60 or not value.isascii() or not all(
                c.isalnum() or c in "-_" for c in value
            ):
                raise ValueError(f"{label} must be a bounded ASCII identifier.")
        if not isinstance(self.steps, tuple) or not 1 <= len(self.steps) <= MAX_STEPS:
            raise ValueError("A lab scene requires 1 to 64 steps.")
        if any(not isinstance(step, LabStep) for step in self.steps):
            raise TypeError("Lab scene steps must be LabStep instances.")
        ids = [step.step_id for step in self.steps]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate lab step identifiers are forbidden.")
        if any(later.occurred_at < earlier.occurred_at for earlier, later in zip(self.steps, self.steps[1:])):
            raise ValueError("Lab steps must be in chronological order.")


@dataclass(frozen=True)
class LabRecord:
    step_id: str
    input_modality: str
    status: str
    semantics: tuple[str, str | None, str, str] | None
    reason: str
    emotion_options: tuple[str, ...] = ()
    text_cues: tuple[str, ...] = ()
    private_region: bool = False

    def redacted(self) -> dict[str, object]:
        """Export only bounded decision metadata, never raw text or private anatomy."""
        semantics = self.semantics
        if self.private_region and semantics is not None:
            semantics = (semantics[0], "[restricted]", semantics[2], semantics[3])
        return {
            "step_id": self.step_id,
            "input_modality": self.input_modality,
            "status": self.status,
            "semantics": semantics,
            "reason": "Restricted region." if self.private_region else self.reason,
        }


class InteractionLab:
    """Deterministic stateless scene runner; a new run never inherits stop state."""

    def __init__(self, engine: InteractionEngine) -> None:
        if not isinstance(engine, InteractionEngine):
            raise TypeError("The lab requires the shared InteractionEngine.")
        self._engine = engine

    def run(self, scene: LabScene) -> tuple[LabRecord, ...]:
        if not isinstance(scene, LabScene):
            raise TypeError("A validated LabScene is required.")
        stopped = False
        records: list[LabRecord] = []
        for step in scene.steps:
            if step.modality == "stop":
                stopped = True
                records.append(LabRecord(step.step_id, "stop", "stopped", None,
                                         "All subsequent interactions are stopped."))
                continue
            decision: InteractionDecision | None
            if step.modality == "text":
                # from_text labels the simulated input modality 'user_text'.
                # This fixture is NEVER saved or forwarded as a real user event.
                decision = self._engine.from_text(
                    content=step.text, message_id=f"{scene.scene_id}-{step.step_id}",
                    session_id=scene.session_id, occurred_at=step.occurred_at,
                    stopped=stopped,
                )
            else:
                decision = self._engine.from_lab_pointer(
                    fixture_id=f"{scene.scene_id}-{step.step_id}",
                    session_id=scene.session_id, region_id=step.region_id,
                    gesture=step.gesture, occurred_at=step.occurred_at,
                    phase=step.phase, stopped=stopped,
                )
            if decision is None:
                records.append(LabRecord(step.step_id, step.modality,
                                         "not_interaction", None,
                                         "No explicit interaction was classified."))
                continue
            region = self._engine.regions.get(decision.event.region_id)
            records.append(LabRecord(
                step.step_id, step.modality, decision.status,
                decision.event.semantics, decision.reason,
                decision.emotion_options, decision.text_cues,
                region.private if region is not None else False,
            ))
        return tuple(records)

    def replay(self, scene: LabScene) -> tuple[LabRecord, ...]:
        """Fresh in-memory evaluation; never dispatch a live action or write state."""
        return self.run(scene)

    @staticmethod
    def export_redacted(records: tuple[LabRecord, ...]) -> tuple[dict[str, object], ...]:
        if not isinstance(records, tuple) or any(not isinstance(item, LabRecord) for item in records):
            raise TypeError("A tuple of lab records is required.")
        return tuple(record.redacted() for record in records)
