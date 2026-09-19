from dataclasses import FrozenInstanceError

import pytest

from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.grounding import (
    CognitiveGroundingContract,
    CognitiveGroundingSource,
    DEFAULT_COGNITIVE_GROUNDING_CONTRACT,
)
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)


def make_request() -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Who are you?",
            ),
        )
    )


def test_default_grounding_contract_is_present_in_context() -> None:
    context = CognitiveContext(
        request=make_request(),
    )

    assert (
        context.grounding
        is DEFAULT_COGNITIVE_GROUNDING_CONTRACT
    )


def test_grounding_contract_is_immutable() -> None:
    contract = CognitiveGroundingContract()

    with pytest.raises(FrozenInstanceError):
        contract.trust_hierarchy = ()


def test_grounding_contract_hierarchy_is_deterministic() -> None:
    contract = CognitiveGroundingContract()

    assert contract.trust_hierarchy == (
        CognitiveGroundingSource.AUTHORITATIVE_IDENTITY_AND_SELF_STATE,
        CognitiveGroundingSource.AUTHORITATIVE_PERSONALITY,
        CognitiveGroundingSource.CONSTITUTION,
        CognitiveGroundingSource.AUTHORITATIVE_EMBODIMENT,
        CognitiveGroundingSource.AUTHORITATIVE_OPERATIONAL_STATE,
        CognitiveGroundingSource.EXPLICIT_DETERMINISTIC_EVIDENCE,
        CognitiveGroundingSource.EXPLICIT_MEMORY,
        CognitiveGroundingSource.CURRENT_USER_REQUEST,
        CognitiveGroundingSource.PRIOR_ASSISTANT_GENERATED_HISTORY,
        CognitiveGroundingSource.MODEL_PRIORS_AND_EXTERNAL_KNOWLEDGE,
    )


def test_grounding_contract_rejects_duplicate_sources() -> None:
    with pytest.raises(ValueError):
        CognitiveGroundingContract(
            trust_hierarchy=(
                CognitiveGroundingSource.AUTHORITATIVE_IDENTITY_AND_SELF_STATE,
                CognitiveGroundingSource.AUTHORITATIVE_IDENTITY_AND_SELF_STATE,
            ),
        )


def test_grounding_contract_serialization_is_deterministic() -> None:
    contract = CognitiveGroundingContract()

    assert contract.serialize() == contract.serialize()


def test_grounding_contract_serializes_trust_hierarchy() -> None:
    serialized = (
        DEFAULT_COGNITIVE_GROUNDING_CONTRACT.serialize()
    )

    assert "COGNITIVE GROUNDING CONTRACT" in serialized
    assert "TRUST HIERARCHY" in serialized
    assert (
        "1. AUTHORITATIVE_IDENTITY_AND_SELF_STATE: "
        "authoritative identity and self-state"
        in serialized
    )
    assert (
        "10. MODEL_PRIORS_AND_EXTERNAL_KNOWLEDGE: "
        "model priors and external knowledge"
        in serialized
    )


def test_grounding_contract_marks_generated_history_non_authoritative() -> None:
    serialized = (
        DEFAULT_COGNITIVE_GROUNDING_CONTRACT.serialize()
    )

    assert (
        "A prior assistant-generated message is generated output, "
        "not authoritative identity evidence."
        in serialized
    )
    assert (
        "A hallucinated claim in prior conversation history does not "
        "become true merely because it appears in history."
        in serialized
    )


def test_grounding_contract_lowers_model_priors_below_authoritative_state() -> None:
    hierarchy = (
        DEFAULT_COGNITIVE_GROUNDING_CONTRACT.trust_hierarchy
    )

    assert (
        hierarchy.index(
            CognitiveGroundingSource.AUTHORITATIVE_IDENTITY_AND_SELF_STATE
        )
        < hierarchy.index(
            CognitiveGroundingSource.MODEL_PRIORS_AND_EXTERNAL_KNOWLEDGE
        )
    )

    assert (
        "Model priors and external knowledge must not override "
        "authoritative supplied state."
        in DEFAULT_COGNITIVE_GROUNDING_CONTRACT.rules
    )


def test_grounding_contract_distinguishes_knowledge_from_authority() -> None:
    serialized = (
        DEFAULT_COGNITIVE_GROUNDING_CONTRACT.serialize()
    )

    assert (
        "It governs knowledge grounding only. It does not grant "
        "authority, expose tools, execute capabilities, or change "
        "runtime permissions."
        in serialized
    )

    assert (
        "Knowledge authority and action authority are separate concerns."
        in serialized
    )


def test_context_rejects_invalid_grounding_contract() -> None:
    with pytest.raises(TypeError):
        CognitiveContext(
            request=make_request(),
            grounding=object(),
        )


def test_context_remains_immutable_with_grounding_contract() -> None:
    context = CognitiveContext(
        request=make_request(),
    )

    with pytest.raises(FrozenInstanceError):
        context.grounding = CognitiveGroundingContract()


def test_assembler_serializes_grounding_contract() -> None:
    context = CognitiveContext(
        request=make_request(),
    )

    assembled = CognitiveContextAssembler().assemble(
        context,
    )

    system_message = assembled.messages[0]

    assert system_message.role is CognitiveRole.SYSTEM
    assert (
        "COGNITIVE GROUNDING CONTRACT"
        in system_message.content
    )
    assert (
        "TRUST HIERARCHY"
        in system_message.content
    )
    assert (
        "PRIOR_ASSISTANT_GENERATED_HISTORY"
        in system_message.content
    )
    assert (
        "MODEL_PRIORS_AND_EXTERNAL_KNOWLEDGE"
        in system_message.content
    )


def test_custom_grounding_contract_is_serialized() -> None:
    contract = CognitiveGroundingContract(
        trust_hierarchy=(
            CognitiveGroundingSource.AUTHORITATIVE_OPERATIONAL_STATE,
            CognitiveGroundingSource.CURRENT_USER_REQUEST,
        ),
        rules=(
            "Use the supplied operational state directly.",
        ),
    )

    context = CognitiveContext(
        request=make_request(),
        grounding=contract,
    )

    assembled = CognitiveContextAssembler().assemble(
        context,
    )

    system_message = assembled.messages[0].content

    assert (
        "1. AUTHORITATIVE_OPERATIONAL_STATE: "
        "authoritative operational state"
        in system_message
    )
    assert (
        "2. CURRENT_USER_REQUEST: current user request"
        in system_message
    )
    assert (
        "1. Use the supplied operational state directly."
        in system_message
    )


def test_grounding_contract_does_not_create_authority() -> None:
    context = CognitiveContext(
        request=make_request(),
    )

    assert not hasattr(context.grounding, "authority")

    assembled = CognitiveContextAssembler().assemble(
        context,
    )

    assert (
        "Operational authority is enforced outside the cognitive engine."
        in assembled.messages[0].content
    )