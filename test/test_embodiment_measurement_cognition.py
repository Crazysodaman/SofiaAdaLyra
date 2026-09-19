from sofia.cognition.assembler import CognitiveContextAssembler
from sofia.cognition.context import CognitiveContext
from sofia.cognition.model import (
    CognitiveMessage,
    CognitiveRequest,
    CognitiveRole,
)
from sofia.embodiment.measurement_query import MeasurementQueryResolver
from sofia.embodiment.model import (
    Embodiment,
    Measurement,
    PhysicalSelf,
)


def make_embodiment() -> Embodiment:
    return Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human",
            measurements=(
                ("height", Measurement(value=67, unit="in")),
                ("weight", Measurement(value=135, unit="lb")),
                ("bust", Measurement(value=33, unit="in")),
                ("underbust", Measurement(value=30, unit="in")),
                ("waist", Measurement(value=26, unit="in")),
                ("hips", Measurement(value=37, unit="in")),
            ),
        ),
    )


def make_request(content: str) -> CognitiveRequest:
    return CognitiveRequest(
        messages=(
            CognitiveMessage(
                role=CognitiveRole.USER,
                content=content,
            ),
        ),
    )


def test_measurement_query_result_projects_into_cognitive_context() -> None:
    embodiment = make_embodiment()

    result = MeasurementQueryResolver().resolve(
        "What are your measurements?",
        embodiment,
    )

    context = CognitiveContext(
        request=make_request("What are your measurements?"),
        embodiment=embodiment,
        measurement_query=result,
    )

    assert context.measurement_query is result
    assert context.measurement_query.recognized is True
    assert [
        fact.name
        for fact in context.measurement_query.facts
    ] == [
        "height",
        "weight",
        "bust",
        "underbust",
        "waist",
        "hips",
    ]


def test_assembler_projects_authoritative_measurement_facts() -> None:
    embodiment = make_embodiment()

    result = MeasurementQueryResolver().resolve(
        "What are your measurements?",
        embodiment,
    )

    context = CognitiveContext(
        request=make_request("What are your measurements?"),
        embodiment=embodiment,
        measurement_query=result,
    )

    content = (
        CognitiveContextAssembler()
        .assemble(context)
        .messages[0]
        .content
    )

    assert (
        "AUTHORITATIVE EMBODIMENT MEASUREMENT QUERY RESULT"
        in content
    )
    assert "- height: 67 in" in content
    assert "- weight: 135 lb" in content
    assert "- bust: 33 in" in content
    assert "- underbust: 30 in" in content
    assert "- waist: 26 in" in content
    assert "- hips: 37 in" in content


def test_unrecognized_measurement_query_does_not_project_facts() -> None:
    embodiment = make_embodiment()

    result = MeasurementQueryResolver().resolve(
        "What is your favorite color?",
        embodiment,
    )

    context = CognitiveContext(
        request=make_request("What is your favorite color?"),
        embodiment=embodiment,
        measurement_query=result,
    )

    content = (
        CognitiveContextAssembler()
        .assemble(context)
        .messages[0]
        .content
    )

    assert context.measurement_query.recognized is False
    assert (
        "AUTHORITATIVE EMBODIMENT MEASUREMENT QUERY RESULT"
        not in content
    )


def test_measurement_query_result_is_immutable_structured_state() -> None:
    embodiment = make_embodiment()

    result = MeasurementQueryResolver().resolve(
        "Tell me your body measurements?",
        embodiment,
    )

    assert result.recognized is True
    assert all(
        isinstance(fact.measurement, Measurement)
        for fact in result.facts
    )