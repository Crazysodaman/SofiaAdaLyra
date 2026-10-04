from __future__ import annotations

from dataclasses import dataclass

from sofia.state.model import StateClass


@dataclass(frozen=True, slots=True)
class StateNamespaceSpec:
    """Reviewed ownership and persistence contract for one logical namespace."""

    name: str
    owner: str
    state_class: StateClass
    principal_scoped: bool
    audience_scoped: bool
    append_only: bool = False

    def __post_init__(self) -> None:
        for label, value in (("name", self.name), ("owner", self.owner)):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be nonempty")
        if not isinstance(self.state_class, StateClass):
            raise TypeError("state_class must be a StateClass")
        for value in (
            self.principal_scoped,
            self.audience_scoped,
            self.append_only,
        ):
            if type(value) is not bool:
                raise TypeError("namespace flags must be booleans")
        if self.audience_scoped and not self.principal_scoped:
            raise ValueError("audience-scoped state must also be principal-scoped")


REL_CONTACT_OBSERVATION = StateNamespaceSpec(
    "rel.contact.observation",
    "REL",
    StateClass.SHARED_AUTHORITATIVE,
    principal_scoped=True,
    audience_scoped=False,
    append_only=True,
)
HABIT_OBSERVATION = StateNamespaceSpec(
    "habit.observation",
    "HABIT",
    StateClass.SHARED_AUTHORITATIVE,
    principal_scoped=True,
    audience_scoped=True,
    append_only=True,
)
HABIT_COVERAGE = StateNamespaceSpec(
    "habit.coverage",
    "HABIT",
    StateClass.SHARED_AUTHORITATIVE,
    principal_scoped=True,
    audience_scoped=True,
    append_only=True,
)
HABIT_PATTERN = StateNamespaceSpec(
    "habit.pattern",
    "HABIT",
    StateClass.SHARED_AUTHORITATIVE,
    principal_scoped=True,
    audience_scoped=True,
)
HABIT_EXPECTATION = StateNamespaceSpec(
    "habit.expectation",
    "HABIT",
    StateClass.SHARED_AUTHORITATIVE,
    principal_scoped=True,
    audience_scoped=True,
)
HABIT_SUPPRESSION = StateNamespaceSpec(
    "habit.suppression",
    "HABIT",
    StateClass.SHARED_AUTHORITATIVE,
    principal_scoped=True,
    audience_scoped=True,
    append_only=True,
)
HABIT_EVIDENCE_INVALIDATION = StateNamespaceSpec(
    "habit.evidence.invalidation",
    "HABIT",
    StateClass.SHARED_AUTHORITATIVE,
    principal_scoped=True,
    audience_scoped=True,
    append_only=True,
)
