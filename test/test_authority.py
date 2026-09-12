from dataclasses import FrozenInstanceError

import pytest

from sofia.authority.model import Authority


def test_authority_defaults_to_response_and_proposal() -> None:
    authority = Authority()

    assert authority.can_respond is True
    assert authority.can_propose_actions is True
    assert authority.can_execute_actions is False


def test_authority_can_allow_execution() -> None:
    authority = Authority(
        can_execute_actions=True,
    )

    assert authority.can_execute_actions is True


def test_authority_can_restrict_response() -> None:
    authority = Authority(
        can_respond=False,
    )

    assert authority.can_respond is False


def test_authority_can_restrict_action_proposals() -> None:
    authority = Authority(
        can_propose_actions=False,
    )

    assert authority.can_propose_actions is False


def test_authority_is_immutable() -> None:
    authority = Authority()

    with pytest.raises(FrozenInstanceError):
        authority.can_execute_actions = True


@pytest.mark.parametrize(
    "field",
    (
        "can_respond",
        "can_propose_actions",
        "can_execute_actions",
    ),
)
def test_authority_requires_boolean_values(field: str) -> None:
    with pytest.raises(TypeError):
        Authority(**{field: "yes"})