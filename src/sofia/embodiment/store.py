import json
from pathlib import Path

from sofia.embodiment.model import (
    AvatarEmbodiment,
    ComputerEmbodiment,
    CurrentEmbodiment,
    Embodiment,
    Measurement,
    PhysicalSelf,
    RobotEmbodiment,
)


class EmbodimentStoreError(Exception):
    """Raised when embodiment persistence fails."""


class AvatarStore:
    """
    Persists Sofía's embodiment definition.

    The filename may be avatar.json, but the persisted domain object
    is an Embodiment.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def save(self, embodiment: Embodiment) -> None:
        if not isinstance(embodiment, Embodiment):
            raise TypeError(
                "AvatarStore embodiment must be an Embodiment."
            )

        data = {
            "subject": embodiment.subject,
            "physical_self": {
                "form": embodiment.physical_self.form,
                "additional_features": list(
                    embodiment.physical_self.additional_features
                ),
                "measurements": {
                    name: {
                        "value": measurement.value,
                        "unit": measurement.unit,
                    }
                    for name, measurement
                    in embodiment.physical_self.measurements
                },
                "appearance": dict(
                    embodiment.physical_self.appearance
                ),
                "anatomy": dict(
                    embodiment.physical_self.anatomy
                ),
            },
            "available": {
                "computers": [
                    {
                        "name": computer.name,
                        "description": computer.description,
                    }
                    for computer in embodiment.computers
                ],
                "robots": [
                    {
                        "name": robot.name,
                        "description": robot.description,
                    }
                    for robot in embodiment.robots
                ],
                "avatars": [
                    {
                        "name": avatar.name,
                        "description": avatar.description,
                    }
                    for avatar in embodiment.avatars
                ],
            },
            "current": {
                "computer": embodiment.current.computer,
                "robot": embodiment.current.robot,
                "avatar": embodiment.current.avatar,
            },
        }

        try:
            self._path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            self._path.write_text(
                json.dumps(
                    data,
                    indent=2,
                    ensure_ascii=False,
                ) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            raise EmbodimentStoreError(
                "Failed to save embodiment."
            ) from exc

    def load(self) -> Embodiment:
        try:
            data = json.loads(
                self._path.read_text(
                    encoding="utf-8"
                )
            )
        except FileNotFoundError as exc:
            raise EmbodimentStoreError(
                "Embodiment file does not exist."
            ) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise EmbodimentStoreError(
                "Failed to load embodiment."
            ) from exc

        if not isinstance(data, dict):
            raise EmbodimentStoreError(
                "Embodiment data must be a JSON object."
            )

        try:
            subject = data["subject"]
            physical_data = data["physical_self"]
            available = data["available"]
            current_data = data["current"]
        except KeyError as exc:
            raise EmbodimentStoreError(
                "Embodiment is missing a required field."
            ) from exc

        try:
            physical_self = self._load_physical_self(
                physical_data
            )

            computers = tuple(
                ComputerEmbodiment(
                    name=item["name"],
                    description=item.get(
                        "description",
                        "",
                    ),
                )
                for item in available["computers"]
            )

            robots = tuple(
                RobotEmbodiment(
                    name=item["name"],
                    description=item.get(
                        "description",
                        "",
                    ),
                )
                for item in available["robots"]
            )

            avatars = tuple(
                AvatarEmbodiment(
                    name=item["name"],
                    description=item.get(
                        "description",
                        "",
                    ),
                )
                for item in available["avatars"]
            )

            current = CurrentEmbodiment(
                computer=current_data.get("computer"),
                robot=current_data.get("robot"),
                avatar=current_data.get("avatar"),
            )

            return Embodiment(
                subject=subject,
                physical_self=physical_self,
                computers=computers,
                robots=robots,
                avatars=avatars,
                current=current,
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise EmbodimentStoreError(
                "Embodiment contains invalid data."
            ) from exc

    @staticmethod
    def _load_physical_self(
        data: object,
    ) -> PhysicalSelf:
        if not isinstance(data, dict):
            raise TypeError(
                "physical_self must be a JSON object."
            )

        measurements_data = data["measurements"]

        if not isinstance(measurements_data, dict):
            raise TypeError(
                "physical_self measurements must be a JSON object."
            )

        measurements = tuple(
            (
                name,
                Measurement(
                    value=value["value"],
                    unit=value["unit"],
                ),
            )
            for name, value in measurements_data.items()
        )

        appearance = tuple(
            data["appearance"].items()
        )

        anatomy = tuple(
            data["anatomy"].items()
        )

        return PhysicalSelf(
            form=data["form"],
            additional_features=tuple(
                data["additional_features"]
            ),
            measurements=measurements,
            appearance=appearance,
            anatomy=anatomy,
        )