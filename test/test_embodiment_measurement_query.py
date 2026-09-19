from sofia.embodiment.measurement_query import (
    MeasurementFact,
    MeasurementQueryResolver,
    MeasurementQueryResult,
)
from sofia.embodiment.model import (
    Embodiment,
    Measurement,
    PhysicalSelf,
)


def create_embodiment() -> Embodiment:
    return Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human-form representation",
            measurements=(
                (
                    "height",
                    Measurement(
                        value=67,
                        unit="in",
                    ),
                ),
                (
                    "weight",
                    Measurement(
                        value=135,
                        unit="lb",
                    ),
                ),
                (
                    "bust",
                    Measurement(
                        value=33,
                        unit="in",
                    ),
                ),
                (
                    "underbust",
                    Measurement(
                        value=30,
                        unit="in",
                    ),
                ),
                (
                    "waist",
                    Measurement(
                        value=26,
                        unit="in",
                    ),
                ),
                (
                    "hips",
                    Measurement(
                        value=37,
                        unit="in",
                    ),
                ),
            ),
        ),
    )


def test_measurement_query_is_recognized():
    resolver = MeasurementQueryResolver()

    result = resolver.resolve(
        "What are your measurements?",
        create_embodiment(),
    )

    assert isinstance(result, MeasurementQueryResult)
    assert result.recognized is True


def test_measurement_query_resolves_all_canonical_measurements():
    resolver = MeasurementQueryResolver()

    result = resolver.resolve(
        "What are your measurements?",
        create_embodiment(),
    )

    assert result.facts == (
        MeasurementFact(
            name="height",
            measurement=Measurement(
                value=67,
                unit="in",
            ),
        ),
        MeasurementFact(
            name="weight",
            measurement=Measurement(
                value=135,
                unit="lb",
            ),
        ),
        MeasurementFact(
            name="bust",
            measurement=Measurement(
                value=33,
                unit="in",
            ),
        ),
        MeasurementFact(
            name="underbust",
            measurement=Measurement(
                value=30,
                unit="in",
            ),
        ),
        MeasurementFact(
            name="waist",
            measurement=Measurement(
                value=26,
                unit="in",
            ),
        ),
        MeasurementFact(
            name="hips",
            measurement=Measurement(
                value=37,
                unit="in",
            ),
        ),
    )


def test_measurement_query_retrieval_is_deterministic():
    resolver = MeasurementQueryResolver()
    embodiment = create_embodiment()

    results = tuple(
        resolver.resolve(
            "What are your measurements?",
            embodiment,
        )
        for _ in range(100)
    )

    assert results == (results[0],) * 100


def test_measurement_query_accepts_supported_wording_variants():
    resolver = MeasurementQueryResolver()
    embodiment = create_embodiment()

    queries = (
        "What are your body measurements?",
        "what are your canonical measurements?",
        "Tell me your measurements",
        "give me your body measurements",
        "  WHAT   ARE   YOUR   MEASUREMENTS?  ",
    )

    for query in queries:
        result = resolver.resolve(
            query,
            embodiment,
        )

        assert result.recognized is True
        assert len(result.facts) == 6


def test_unrelated_query_is_not_recognized():
    resolver = MeasurementQueryResolver()

    result = resolver.resolve(
        "What color are your eyes?",
        create_embodiment(),
    )

    assert result == MeasurementQueryResult(
        recognized=False,
    )


def test_unrecognized_query_does_not_produce_facts():
    resolver = MeasurementQueryResolver()

    result = resolver.resolve(
        "How tall are you?",
        create_embodiment(),
    )

    assert result.recognized is False
    assert result.facts == ()


def test_query_resolution_does_not_modify_embodiment():
    resolver = MeasurementQueryResolver()
    embodiment = create_embodiment()
    original_measurements = embodiment.physical_self.measurements

    resolver.resolve(
        "What are your measurements?",
        embodiment,
    )

    assert embodiment.physical_self.measurements == original_measurements


def test_query_resolver_does_not_generate_or_convert_values():
    resolver = MeasurementQueryResolver()

    result = resolver.resolve(
        "What are your measurements?",
        create_embodiment(),
    )

    values = tuple(
        (fact.name, fact.measurement.value, fact.measurement.unit)
        for fact in result.facts
    )

    assert values == (
        ("height", 67, "in"),
        ("weight", 135, "lb"),
        ("bust", 33, "in"),
        ("underbust", 30, "in"),
        ("waist", 26, "in"),
        ("hips", 37, "in"),
    )


def test_non_string_query_is_rejected():
    resolver = MeasurementQueryResolver()

    try:
        resolver.resolve(
            67,
            create_embodiment(),
        )
    except TypeError as exc:
        assert str(exc) == "Measurement query must be a string."
    else:
        raise AssertionError(
            "Expected TypeError for non-string query."
        )


def test_non_embodiment_is_rejected():
    resolver = MeasurementQueryResolver()

    try:
        resolver.resolve(
            "What are your measurements?",
            None,
        )
    except TypeError as exc:
        assert (
            str(exc)
            == (
                "Measurement query resolver embodiment must be "
                "an Embodiment."
            )
        )
    else:
        raise AssertionError(
            "Expected TypeError for non-Embodiment."
        )