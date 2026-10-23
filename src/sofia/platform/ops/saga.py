"""Saga-style operation-effect classification and bounded compensation planning.

V18 CA-3703 asks for a saga-style operation classification of the reversible,
compensable, retryable-idempotent, externally irreversible and unknown kinds,
with concrete examples for Discord, Git, Home Assistant, JMRI and Hephaestus.
V18 CA-3706 asks for bounded compensating actions and escalation when an
operation partially succeeds, without ever claiming that a snapshot or a
compensation reverses a remote message or a live-device change.

This module is a pure, side-effect-free decision contract. It classifies known
operation kinds and, given an observed partial outcome, returns a *bounded*
compensation and escalation plan. It never performs an effect, never opens the
canonical database and never grants authority. An irreversible operation can
never be reported as compensated; an unknown operation fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class EffectClass(str, Enum):
    """How an operation may be recovered after an uncertain or partial outcome."""

    REVERSIBLE = "fully_reversible"
    COMPENSABLE = "compensable"
    RETRYABLE_IDEMPOTENT = "retryable_idempotent"
    IRREVERSIBLE = "externally_irreversible"
    UNKNOWN = "unknown"


class Escalation(str, Enum):
    """Operator involvement required to settle a partial outcome."""

    NONE = "none"
    OPERATOR_REVIEW = "operator_review"
    OPERATOR_ACTION_REQUIRED = "operator_action_required"


class SagaError(ValueError):
    """Raised when a classification or compensation request is not admissible."""


@dataclass(frozen=True, slots=True)
class OperationEffect:
    """The declared effect class of one named production operation."""

    operation_id: str
    effect_class: EffectClass
    requires_idempotency_key: bool = False
    compensation: str | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or _IDENTIFIER.fullmatch(
            self.operation_id
        ) is None:
            raise SagaError("operation_id must be a bounded identifier")
        if not isinstance(self.effect_class, EffectClass):
            raise TypeError("effect_class must be EffectClass")
        if type(self.requires_idempotency_key) is not bool:
            raise TypeError("requires_idempotency_key must be bool")
        if self.compensation is not None and (
            not isinstance(self.compensation, str)
            or not self.compensation.strip()
            or len(self.compensation) > 240
        ):
            raise SagaError("compensation must be None or bounded nonempty text")
        if not isinstance(self.note, str) or len(self.note) > 320:
            raise SagaError("note must be bounded text")
        if (
            self.effect_class is EffectClass.RETRYABLE_IDEMPOTENT
            and not self.requires_idempotency_key
        ):
            raise SagaError("idempotent retries require a stable idempotency key")
        if (
            self.effect_class is EffectClass.COMPENSABLE
            and self.compensation is None
        ):
            raise SagaError("compensable operations must declare a compensation")
        if (
            self.effect_class is EffectClass.IRREVERSIBLE
            and self.compensation is not None
        ):
            raise SagaError(
                "an externally irreversible operation cannot declare a reversal"
            )


# Concrete classification for the operations named in the original CA-3703
# requirement plus the immediately adjacent production integrations. Each is a
# starting point for the owning subsystem, not a claim that the subsystem has
# been re-wired here.
_KNOWN_OPERATIONS: tuple[OperationEffect, ...] = (
    OperationEffect(
        operation_id="discord.message.send",
        effect_class=EffectClass.IRREVERSIBLE,
        note="A delivered Discord message may already have been read; deletion "
             "cannot restore prior state.",
    ),
    OperationEffect(
        operation_id="discord.message.edit",
        effect_class=EffectClass.IRREVERSIBLE,
        note="Edits are visible remotely and cannot restore the pre-edit text "
             "for a recipient who already saw it.",
    ),
    OperationEffect(
        operation_id="git.commit.local",
        effect_class=EffectClass.REVERSIBLE,
        compensation="git reset --soft to the pre-operation revision",
        note="An unpushed local commit is fully reversible.",
    ),
    OperationEffect(
        operation_id="git.push",
        effect_class=EffectClass.IRREVERSIBLE,
        note="Published history is externally visible; only an added revert "
             "commit is possible, never a true reversal.",
    ),
    OperationEffect(
        operation_id="home_assistant.service.call",
        effect_class=EffectClass.UNKNOWN,
        note="Generic service calls can trigger non-idempotent physical effects. "
             "A local key does not establish remote deduplication.",
    ),
    OperationEffect(
        operation_id="home_assistant.state.set",
        effect_class=EffectClass.UNKNOWN,
        note="An apparent state setter may trigger automation or hardware. "
             "Remote retry guarantees are not established.",
    ),
    OperationEffect(
        operation_id="jmri.turnout.set",
        effect_class=EffectClass.UNKNOWN,
        note="Repeated turnout commands can re-energize physical hardware; "
             "a local request key is not receiver-side deduplication.",
    ),
    OperationEffect(
        operation_id="jmri.power.set",
        effect_class=EffectClass.COMPENSABLE,
        compensation="restore the previously observed power state once, when "
                     "the previous state is known",
        note="Layout power can usually be returned to a known prior state.",
    ),
    OperationEffect(
        operation_id="hephaestus.package.stage",
        effect_class=EffectClass.COMPENSABLE,
        compensation="remove only the newly staged package under the original "
                     "authenticated mapping",
        note="A staged artifact that was never activated can be removed.",
    ),
    OperationEffect(
        operation_id="hephaestus.vm.start",
        effect_class=EffectClass.COMPENSABLE,
        compensation="stop the guest only if it is proven still inactive-for-"
                     "work and was started by this operation",
        note="A partially started guest is a bounded, operator-supervised case.",
    ),
    OperationEffect(
        operation_id="memory.write",
        effect_class=EffectClass.REVERSIBLE,
        compensation="contradict the written atom through the canonical "
                     "correction path",
        note="Canonical memory corrections are additive and auditable.",
    ),
    OperationEffect(
        operation_id="filesystem.scratch.write",
        effect_class=EffectClass.REVERSIBLE,
        compensation="delete the scratch file created by this operation",
        note="Bounded scratch writes are reversible.",
    ),
)

OPERATIONS: dict[str, OperationEffect] = {
    effect.operation_id: effect for effect in _KNOWN_OPERATIONS
}


def classify_operation(operation_id: str) -> OperationEffect:
    """Return the declared effect classification for a known operation.

    An unregistered operation is not silently treated as reversible; it is
    classified as ``UNKNOWN`` so callers fail closed.
    """
    if not isinstance(operation_id, str) or _IDENTIFIER.fullmatch(operation_id) is None:
        raise SagaError("operation_id must be a bounded identifier")
    known = OPERATIONS.get(operation_id)
    if known is not None:
        return known
    return OperationEffect(
        operation_id=operation_id,
        effect_class=EffectClass.UNKNOWN,
        note="unregistered operation; recovery is undecidable without review",
    )


@dataclass(frozen=True, slots=True)
class PartialOutcome:
    """An observed partial or uncertain result for one named operation."""

    operation_id: str
    committed_steps: tuple[str, ...] = ()
    uncommitted_steps: tuple[str, ...] = ()
    external_effect_observed: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.operation_id, str) or _IDENTIFIER.fullmatch(
            self.operation_id
        ) is None:
            raise SagaError("operation_id must be a bounded identifier")
        for name, steps in (
            ("committed_steps", self.committed_steps),
            ("uncommitted_steps", self.uncommitted_steps),
        ):
            if not isinstance(steps, tuple) or any(
                not isinstance(step, str) or not step.strip() or len(step) > 160
                for step in steps
            ):
                raise SagaError(f"{name} must be bounded step labels")
        if set(self.committed_steps) & set(self.uncommitted_steps):
            raise SagaError("a step cannot be both committed and uncommitted")
        if type(self.external_effect_observed) is not bool:
            raise TypeError("external_effect_observed must be bool")


@dataclass(frozen=True, slots=True)
class CompensationPlan:
    """A bounded, non-authoritative recovery plan for a partial outcome."""

    operation_id: str
    effect_class: EffectClass
    compensating_actions: tuple[str, ...]
    escalation: Escalation
    may_retry_automatically: bool
    requires_idempotency_key: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.effect_class, EffectClass):
            raise TypeError("effect_class must be EffectClass")
        if not isinstance(self.escalation, Escalation):
            raise TypeError("escalation must be Escalation")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise SagaError("plan requires a reason")
        if self.effect_class is EffectClass.IRREVERSIBLE and self.compensating_actions:
            raise SagaError(
                "an irreversible operation cannot present a compensating reversal"
            )


def plan_compensation(outcome: PartialOutcome) -> CompensationPlan:
    """Return the bounded compensation/escalation plan for a partial outcome.

    The plan never claims that a compensation reverses an externally observable
    effect. Irreversible and unknown operations escalate to the operator.
    """
    effect = classify_operation(outcome.operation_id)
    klass = effect.effect_class
    if klass is EffectClass.REVERSIBLE:
        action = effect.compensation or "return to the last verified local state"
        return CompensationPlan(
            operation_id=effect.operation_id, effect_class=klass,
            compensating_actions=(action,),
            escalation=Escalation.NONE, may_retry_automatically=False,
            requires_idempotency_key=False,
            reason="fully reversible operation is rolled back locally",
        )
    if klass is EffectClass.COMPENSABLE:
        assert effect.compensation is not None
        return CompensationPlan(
            operation_id=effect.operation_id, effect_class=klass,
            compensating_actions=(effect.compensation,),
            escalation=Escalation.OPERATOR_REVIEW,
            may_retry_automatically=False,
            requires_idempotency_key=False,
            reason="bounded compensation must be confirmed before rerunning",
        )
    if klass is EffectClass.RETRYABLE_IDEMPOTENT:
        return CompensationPlan(
            operation_id=effect.operation_id, effect_class=klass,
            compensating_actions=(),
            escalation=Escalation.NONE, may_retry_automatically=True,
            requires_idempotency_key=True,
            reason="retry the same logical request with its stable key",
        )
    if klass is EffectClass.IRREVERSIBLE:
        return CompensationPlan(
            operation_id=effect.operation_id, effect_class=klass,
            compensating_actions=(),
            escalation=(
                Escalation.OPERATOR_ACTION_REQUIRED
                if outcome.external_effect_observed
                else Escalation.OPERATOR_REVIEW
            ),
            may_retry_automatically=False,
            requires_idempotency_key=False,
            reason="externally irreversible effect cannot be undone; operator "
                   "must decide on an explicit forward correction",
        )
    return CompensationPlan(
        operation_id=effect.operation_id, effect_class=EffectClass.UNKNOWN,
        compensating_actions=(), escalation=Escalation.OPERATOR_ACTION_REQUIRED,
        may_retry_automatically=False, requires_idempotency_key=False,
        reason="unclassified operation; fail closed and await review",
    )
