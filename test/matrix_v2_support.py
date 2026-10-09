"""Small test adapter for assertions migrating from retired Matrix v1."""
from sofia.application.conversation_matrix import (
    _v2_evidence_matrix,
    _v2_safeguard_turn,
)
from sofia.cognition.matrix import MatrixRoute, RoutingPlan, TurnEnvelope
from sofia.cognition.v2 import (
    ConversationFocus,
    FocusReference,
    MatrixV2Planner,
    ReasoningRequirement,
    TurnKernelInput,
)


def _plan(envelope: TurnEnvelope):
    named = next(
        (
            name for name in ("Artemis", "Venus", "Eos", "Nyx", "Dionysus")
            if name.casefold() in envelope.content.casefold()
        ),
        None,
    )
    reference = (
        None
        if named is None
        else FocusReference(
            f"reference:{named.casefold()}",
            f"fleet-node:{named.casefold()}",
            "fleet-node",
            envelope.message_id,
            1.0,
            aliases=(named,),
        )
    )
    focus = ConversationFocus(
        session_id=envelope.session_id,
        audience_id=(
            None
            if envelope.principal_id is None
            else f"principal:{envelope.principal_id}"
        ),
        revision=0,
        primary_reference=reference,
        references=(() if reference is None else (reference,)),
    )
    turn = TurnKernelInput(
        turn_id=envelope.message_id,
        session_id=envelope.session_id,
        content=envelope.content,
        created_at=envelope.created_at,
        channel=envelope.channel,
        principal_id=envelope.principal_id,
        audience_id=focus.audience_id,
    )
    return MatrixV2Planner().plan(turn, focus)


class V2MatrixCoordinator:
    def __init__(self, *args, **kwargs):
        _ = args, kwargs

    def evaluate(self, envelope: TurnEnvelope):
        return _v2_safeguard_turn(_plan(envelope), envelope.content)


class V2TurnClassifier:
    def classify(self, envelope: TurnEnvelope):
        return V2MatrixCoordinator().evaluate(envelope)


class V2RoutingPlanner:
    def plan(self, envelope: TurnEnvelope, turn):
        _ = turn
        requirement = _plan(envelope).reasoning_requirement
        routes = {
            ReasoningRequirement.DETERMINISTIC: MatrixRoute.FAST,
            ReasoningRequirement.FAST: MatrixRoute.FAST,
            ReasoningRequirement.STANDARD: MatrixRoute.STANDARD,
            ReasoningRequirement.DEEP: MatrixRoute.DEEP,
            ReasoningRequirement.VERIFY: MatrixRoute.VERIFY,
        }
        return RoutingPlan(routes[requirement], "Cognition v2 test projection")


def v2_registry():
    """No registry exists in v2; retained call sites may pass this sentinel."""
    return None


def v2_evidence(envelope: TurnEnvelope):
    """Return the authoritative v2 evidence contract for a test envelope."""
    return _v2_evidence_matrix(_plan(envelope))
