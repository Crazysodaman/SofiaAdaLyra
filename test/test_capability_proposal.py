import pytest

from sofia.capability.proposal import CapabilityProposal


def test_capability_proposal_contains_structured_invocation():
    proposal = CapabilityProposal(
        capability_name="codebase.inspect",
        parameters={},
        rationale="Inspect the authorized codebase.",
        requested_scope=None,
    )

    assert proposal.capability_name == "codebase.inspect"
    assert proposal.parameters == {}
    assert proposal.rationale == "Inspect the authorized codebase."
    assert proposal.requested_scope is None


def test_capability_proposal_is_immutable():
    proposal = CapabilityProposal(
        capability_name="codebase.inspect",
        parameters={},
        rationale="Inspect the codebase.",
    )

    with pytest.raises(AttributeError):
        proposal.capability_name = "other.capability"


def test_capability_proposal_rejects_empty_capability_name():
    with pytest.raises(ValueError):
        CapabilityProposal(
            capability_name="",
            parameters={},
            rationale="Inspect the codebase.",
        )


def test_capability_proposal_rejects_non_string_capability_name():
    with pytest.raises(TypeError):
        CapabilityProposal(
            capability_name=123,
            parameters={},
            rationale="Inspect the codebase.",
        )


def test_capability_proposal_rejects_non_dict_parameters():
    with pytest.raises(TypeError):
        CapabilityProposal(
            capability_name="codebase.inspect",
            parameters=[],
            rationale="Inspect the codebase.",
        )


def test_capability_proposal_rejects_empty_rationale():
    with pytest.raises(ValueError):
        CapabilityProposal(
            capability_name="codebase.inspect",
            parameters={},
            rationale="",
        )


def test_capability_proposal_contains_no_authorization_contract():
    proposal = CapabilityProposal(
        capability_name="codebase.inspect",
        parameters={},
        rationale="Inspect the codebase.",
    )

    assert not hasattr(proposal, "authority")
    assert not hasattr(proposal, "authorization")
    assert not hasattr(proposal, "authorized")
    assert not hasattr(proposal, "execute")