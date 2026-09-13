from pathlib import Path

import pytest

from sofia.embodiment.model import (
    AvatarEmbodiment,
    ComputerEmbodiment,
    CurrentEmbodiment,
    Embodiment,
    Measurement,
    PhysicalSelf,
    RobotEmbodiment,
)
from sofia.embodiment.store import (
    AvatarStore,
    EmbodimentStoreError,
)


def create_embodiment() -> Embodiment:
    return Embodiment(
        subject="Sofía Ada Lyra",
        physical_self=PhysicalSelf(
            form="human",
            additional_features=(
                "fox ears",
                "fox tail",
            ),
            measurements=(
                (
                    "height",
                    Measurement(
                        value=67,
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
            ),
            appearance=(
                (
                    "hair_color",
                    "deep crimson",
                ),
                (
                    "skin_color",
                    "warm ivory",
                ),
            ),
            anatomy=(
                (
                    "ears",
                    "2 fox ears",
                ),
                (
                    "tail",
                    "1 fox tail",
                ),
            ),
        ),
        computers=(
            ComputerEmbodiment(
                name="Test Computer",
            ),
        ),
        robots=(
            RobotEmbodiment(
                name="Test Robot",
            ),
        ),
        avatars=(
            AvatarEmbodiment(
                name="Test Avatar",
            ),
        ),
        current=CurrentEmbodiment(
            computer="Test Computer",
            robot="Test Robot",
            avatar="Test Avatar",
        ),
    )


def test_measurement_is_immutable():
    measurement = Measurement(
        value=67,
        unit="in",
    )

    with pytest.raises(AttributeError):
        measurement.value = 68


def test_physical_self_stores_measurements():
    physical_self = create_embodiment().physical_self

    assert dict(physical_self.measurements)["height"] == Measurement(
        value=67,
        unit="in",
    )


def test_embodiment_stores_available_forms():
    embodiment = create_embodiment()

    assert embodiment.computers[0].name == "Test Computer"
    assert embodiment.robots[0].name == "Test Robot"
    assert embodiment.avatars[0].name == "Test Avatar"


def test_embodiment_stores_current_forms():
    embodiment = create_embodiment()

    assert embodiment.current.computer == "Test Computer"
    assert embodiment.current.robot == "Test Robot"
    assert embodiment.current.avatar == "Test Avatar"


def test_avatar_store_round_trips_embodiment(tmp_path: Path):
    path = tmp_path / "avatar.json"

    store = AvatarStore(path)
    original = create_embodiment()

    store.save(original)

    loaded = store.load()

    assert loaded == original


def test_avatar_store_creates_parent_directory(tmp_path: Path):
    path = tmp_path / "nested" / "avatar.json"

    store = AvatarStore(path)
    embodiment = create_embodiment()

    store.save(embodiment)

    assert path.exists()


def test_avatar_store_rejects_missing_file(tmp_path: Path):
    store = AvatarStore(
        tmp_path / "missing.json"
    )

    with pytest.raises(
        EmbodimentStoreError,
        match="does not exist",
    ):
        store.load()


def test_avatar_store_rejects_non_object_json(
    tmp_path: Path,
):
    path = tmp_path / "avatar.json"

    path.write_text(
        "[]",
        encoding="utf-8",
    )

    store = AvatarStore(path)

    with pytest.raises(
        EmbodimentStoreError,
        match="JSON object",
    ):
        store.load()