import pytest

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


def test_embodiment_retrieves_authoritative_measurement():
    embodiment = create_embodiment()

    assert embodiment.get_measurement("height") == Measurement(
        value=67,
        unit="in",
    )


def test_physical_self_retrieves_authoritative_measurement():
    embodiment = create_embodiment()

    assert embodiment.physical_self.get_measurement(
        "waist"
    ) == Measurement(
        value=26,
        unit="in",
    )


def test_measurement_retrieval_is_deterministic():
    embodiment = create_embodiment()

    results = tuple(
        embodiment.get_measurement("hips")
        for _ in range(100)
    )

    assert results == (
        Measurement(
            value=37,
            unit="in",
        ),
    ) * 100


def test_measurement_retrieval_returns_stored_value_without_conversion():
    embodiment = create_embodiment()

    measurement = embodiment.get_measurement(
        "weight"
    )

    assert measurement.value == 135
    assert measurement.unit == "lb"


def test_measurement_retrieval_does_not_modify_embodiment():
    embodiment = create_embodiment()
    original = embodiment.physical_self.measurements

    embodiment.get_measurement("height")

    assert embodiment.physical_self.measurements == original


def test_unknown_measurement_is_explicit():
    embodiment = create_embodiment()

    with pytest.raises(
        KeyError,
        match="Unknown canonical measurement",
    ):
        embodiment.get_measurement("inseam")


def test_empty_measurement_name_is_rejected():
    embodiment = create_embodiment()

    with pytest.raises(
        ValueError,
        match="Measurement name must not be empty",
    ):
        embodiment.get_measurement("")


def test_non_string_measurement_name_is_rejected():
    embodiment = create_embodiment()

    with pytest.raises(
        TypeError,
        match="Measurement name must be a string",
    ):
        embodiment.get_measurement(67)