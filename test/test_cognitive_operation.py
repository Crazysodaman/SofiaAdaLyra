from dataclasses import FrozenInstanceError

import pytest

from sofia.authority.model import Authority
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.cognition.operation import CognitiveOperation


def make_context() -> CognitiveContext:
    request = CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        )
    )

    return CognitiveContext(
        request=request,
    )


def test_operation_requires_context() -> None:
    context = make_context()
    authority = Authority()

    operation = CognitiveOperation(
        context=context,
        authority=authority,
    )

    assert operation.context is context


def test_operation_requires_authority() -> None:
    context = make_context()
    authority = Authority()

    operation = CognitiveOperation(
        context=context,
        authority=authority,
    )

    assert operation.authority is authority


def test_operation_keeps_authority_out_of_context() -> None:
    operation = CognitiveOperation(
        context=make_context(),
        authority=Authority(),
    )

    assert not hasattr(operation.context, "authority")


def test_operation_is_immutable() -> None:
    operation = CognitiveOperation(
        context=make_context(),
        authority=Authority(),
    )

    with pytest.raises(FrozenInstanceError):
        operation.authority = Authority()


def test_operation_rejects_invalid_context() -> None:
    with pytest.raises(TypeError):
        CognitiveOperation(
            context="not a context",
            authority=Authority(),
        )


def test_operation_rejects_invalid_authority() -> None:
    with pytest.raises(TypeError):
        CognitiveOperation(
            context=make_context(),
            authority="not authority",
        )