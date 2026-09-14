from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.constitution.model import Constitution
from sofia.identity.model import SofiaIdentity
from sofia.memory.model import MemoryRecord
from sofia.personality.model import PersonalityProfile
from pathlib import Path

from sofia.filesystem.model import (
    FilesystemOperation,
    FilesystemResult,
    FilesystemResultKind,
)

def make_filesystem_result() -> FilesystemResult:
    return FilesystemResult(
        operation=FilesystemOperation.LIST_DIRECTORY,
        kind=FilesystemResultKind.SUCCESS,
        path=Path("."),
        message="Directory inspection completed.",
        entries=(
            Path("src"),
            Path("test"),
        ),
    )


def test_context_can_include_filesystem_results() -> None:
    result = make_filesystem_result()

    context = CognitiveContext(
        request=make_request(),
        filesystem_results=(result,),
    )

    assert context.filesystem_results == (result,)


def test_context_filesystem_results_default_to_empty() -> None:
    context = CognitiveContext(
        request=make_request(),
    )

    assert context.filesystem_results == ()


def test_context_rejects_non_tuple_filesystem_results() -> None:
    with pytest.raises(TypeError):
        CognitiveContext(
            request=make_request(),
            filesystem_results=[make_filesystem_result()],
        )


def test_context_rejects_invalid_filesystem_result() -> None:
    with pytest.raises(TypeError):
        CognitiveContext(
            request=make_request(),
            filesystem_results=("not a filesystem result",),
        )

def make_request() -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content="Hello, Sofía.",
            ),
        )
    )


def make_constitution() -> Constitution:
    return Constitution(
        version="1.0",
        content="Sofía's constitutional principles.",
        content_hash="a" * 64,
        loaded_at=datetime.now(timezone.utc),
    )


def make_identity() -> SofiaIdentity:
    return SofiaIdentity(
        name="Sofía Ada Lyra",
    )


def make_personality() -> PersonalityProfile:
    return PersonalityProfile(
        name="Caffeinated Quirky",
        traits=(
            "analytical",
            "blunt",
            "curious",
        ),
        communication_style="direct and energetic",
    )


def make_memory() -> MemoryRecord:
    return MemoryRecord(
        id="memory-1",
        content="Sofía remembers a previous interaction.",
        created_at=datetime.now(timezone.utc),
    )


def test_context_requires_cognitive_request() -> None:
    request = make_request()

    context = CognitiveContext(
        request=request,
    )

    assert context.request is request


def test_context_can_include_identity() -> None:
    request = make_request()
    identity = make_identity()

    context = CognitiveContext(
        request=request,
        identity=identity,
    )

    assert context.identity is identity


def test_context_can_include_personality() -> None:
    request = make_request()
    personality = make_personality()

    context = CognitiveContext(
        request=request,
        personality=personality,
    )

    assert context.personality is personality


def test_context_can_include_relevant_memories() -> None:
    request = make_request()
    memories = (
        make_memory(),
    )

    context = CognitiveContext(
        request=request,
        memories=memories,
    )

    assert context.memories == memories


def test_context_does_not_require_optional_cognitive_inputs() -> None:
    context = CognitiveContext(
        request=make_request(),
    )

    assert context.identity is None
    assert context.personality is None
    assert context.memories == ()


def test_context_is_immutable() -> None:
    context = CognitiveContext(
        request=make_request(),
    )

    with pytest.raises(FrozenInstanceError):
        context.request = make_request()


def test_context_does_not_mutate_identity() -> None:
    identity = make_identity()

    CognitiveContext(
        request=make_request(),
        identity=identity,
    )

    assert identity.name == "Sofía Ada Lyra"


def test_context_does_not_mutate_personality() -> None:
    personality = make_personality()

    CognitiveContext(
        request=make_request(),
        personality=personality,
    )

    assert personality.name == "Caffeinated Quirky"
    assert personality.traits == (
        "analytical",
        "blunt",
        "curious",
    )


def test_context_does_not_mutate_memories() -> None:
    memory = make_memory()
    memories = (memory,)

    CognitiveContext(
        request=make_request(),
        memories=memories,
    )

    assert memories == (memory,)


def test_context_has_no_authority_contract() -> None:
    context = CognitiveContext(
        request=make_request(),
    )

    assert not hasattr(context, "authority")


def test_context_can_reference_constitution_without_making_it_authority() -> None:
    constitution = make_constitution()

    context = CognitiveContext(
        request=make_request(),
        constitution=constitution,
    )

    assert context.constitution is constitution