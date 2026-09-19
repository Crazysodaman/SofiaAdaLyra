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
        "can_inspect_filesystem",
    ),
)
def test_authority_requires_boolean_values(field: str) -> None:
    with pytest.raises(TypeError):
        Authority(**{field: "yes"})


def test_filesystem_inspection_is_disabled_by_default() -> None:
    authority = Authority()

    assert authority.can_inspect_filesystem is False


def test_filesystem_inspection_authority_can_be_enabled() -> None:
    authority = Authority(
        can_inspect_filesystem=True,
    )

    assert authority.can_inspect_filesystem is True


def test_filesystem_inspection_capability_requires_authority() -> None:
    authority = Authority()

    assert authority.can_use_capability(
        "filesystem.inspect"
    ) is False


def test_filesystem_inspection_capability_is_authorized_when_enabled() -> None:
    authority = Authority(
        can_inspect_filesystem=True,
    )

    assert authority.can_use_capability(
        "filesystem.inspect"
    ) is True


def test_explicit_capability_can_be_authorized() -> None:
    authority = Authority(
        allowed_capabilities=("codebase.inspect",),
    )

    assert authority.can_use_capability(
        "codebase.inspect"
    ) is True


def test_unknown_capability_is_denied_by_default() -> None:
    authority = Authority()

    assert authority.can_use_capability(
        "unknown.capability"
    ) is False


def test_allowed_capabilities_must_be_tuple() -> None:
    with pytest.raises(TypeError):
        Authority(
            allowed_capabilities=["codebase.inspect"],
        )


def test_allowed_capabilities_must_not_contain_empty_names() -> None:
    with pytest.raises(ValueError):
        Authority(
            allowed_capabilities=("codebase.inspect", ""),
        )


def test_allowed_capabilities_must_not_contain_duplicates() -> None:
    with pytest.raises(ValueError):
        Authority(
            allowed_capabilities=(
                "codebase.inspect",
                "codebase.inspect",
            ),
        )


def test_capability_name_must_be_non_empty() -> None:
    authority = Authority()

    with pytest.raises(ValueError):
        authority.can_use_capability("")


def test_capability_name_must_be_string() -> None:
    authority = Authority()

    with pytest.raises(TypeError):
        authority.can_use_capability(None)