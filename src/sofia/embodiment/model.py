from dataclasses import dataclass


@dataclass(frozen=True)
class Measurement:
    value: float
    unit: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, (int, float)):
            raise TypeError(
                "Measurement value must be numeric."
            )

        if not self.unit:
            raise ValueError(
                "Measurement unit must not be empty."
            )


@dataclass(frozen=True)
class ClothingItem:
    """
    One canonical clothing specification entry.

    The specification is intentionally preserved as canonical text rather
    than decomposed into inferred implementation fields.
    """

    category: str
    specification: str

    def __post_init__(self) -> None:
        if not self.category:
            raise ValueError(
                "ClothingItem category must not be empty."
            )

        if not self.specification:
            raise ValueError(
                "ClothingItem specification must not be empty."
            )


@dataclass(frozen=True)
class ClothingSpecification:
    """
    Immutable canonical clothing specification for Sofía.

    Entries retain the exact category/specification language supplied by
    the canonical design document.
    """

    items: tuple[ClothingItem, ...] = ()
    canonical_status: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.items, tuple):
            raise TypeError(
                "ClothingSpecification items must be a tuple."
            )

        for item in self.items:
            if not isinstance(item, ClothingItem):
                raise TypeError(
                    "ClothingSpecification items must contain "
                    "ClothingItem instances."
                )

        if not isinstance(self.canonical_status, str):
            raise TypeError(
                "ClothingSpecification canonical_status must be a string."
            )


@dataclass(frozen=True)
class PhysicalSelf:
    form: str
    additional_features: tuple[str, ...] = ()
    measurements: tuple[tuple[str, Measurement], ...] = ()
    appearance: tuple[tuple[str, str], ...] = ()
    anatomy: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.form:
            raise ValueError(
                "PhysicalSelf form must not be empty."
            )

        if not isinstance(self.additional_features, tuple):
            raise TypeError(
                "PhysicalSelf additional_features must be a tuple."
            )

        for feature in self.additional_features:
            if not isinstance(feature, str):
                raise TypeError(
                    "PhysicalSelf additional_features must contain strings."
                )

        if not isinstance(self.measurements, tuple):
            raise TypeError(
                "PhysicalSelf measurements must be a tuple."
            )

        for name, measurement in self.measurements:
            if not isinstance(name, str):
                raise TypeError(
                    "PhysicalSelf measurement names must be strings."
                )

            if not isinstance(measurement, Measurement):
                raise TypeError(
                    "PhysicalSelf measurements must contain Measurement "
                    "instances."
                )

        if not isinstance(self.appearance, tuple):
            raise TypeError(
                "PhysicalSelf appearance must be a tuple."
            )

        for key, value in self.appearance:
            if not isinstance(key, str):
                raise TypeError(
                    "PhysicalSelf appearance keys must be strings."
                )

            if not isinstance(value, str):
                raise TypeError(
                    "PhysicalSelf appearance values must be strings."
                )

        if not isinstance(self.anatomy, tuple):
            raise TypeError(
                "PhysicalSelf anatomy must be a tuple."
            )

        for key, value in self.anatomy:
            if not isinstance(key, str):
                raise TypeError(
                    "PhysicalSelf anatomy keys must be strings."
                )

            if not isinstance(value, str):
                raise TypeError(
                    "PhysicalSelf anatomy values must be strings."
                )


@dataclass(frozen=True)
class ComputerEmbodiment:
    name: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(
                "ComputerEmbodiment name must not be empty."
            )


@dataclass(frozen=True)
class RobotEmbodiment:
    name: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(
                "RobotEmbodiment name must not be empty."
            )


@dataclass(frozen=True)
class AvatarEmbodiment:
    name: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(
                "AvatarEmbodiment name must not be empty."
            )


@dataclass(frozen=True)
class CurrentEmbodiment:
    computer: str | None = None
    robot: str | None = None
    avatar: str | None = None


@dataclass(frozen=True)
class Embodiment:
    """
    Persistent model of the forms through which Sofía may exist,
    operate, or represent herself.

    Embodiment is not identity, personality, or runtime state.
    """

    subject: str
    physical_self: PhysicalSelf
    clothing: ClothingSpecification = ClothingSpecification()
    computers: tuple[ComputerEmbodiment, ...] = ()
    robots: tuple[RobotEmbodiment, ...] = ()
    avatars: tuple[AvatarEmbodiment, ...] = ()
    current: CurrentEmbodiment = CurrentEmbodiment()

    def __post_init__(self) -> None:
        if not self.subject:
            raise ValueError(
                "Embodiment subject must not be empty."
            )

        if not isinstance(self.physical_self, PhysicalSelf):
            raise TypeError(
                "Embodiment physical_self must be a PhysicalSelf."
            )

        if not isinstance(self.clothing, ClothingSpecification):
            raise TypeError(
                "Embodiment clothing must be a ClothingSpecification."
            )

        if not isinstance(self.computers, tuple):
            raise TypeError(
                "Embodiment computers must be a tuple."
            )

        for computer in self.computers:
            if not isinstance(computer, ComputerEmbodiment):
                raise TypeError(
                    "Embodiment computers must contain "
                    "ComputerEmbodiment instances."
                )

        if not isinstance(self.robots, tuple):
            raise TypeError(
                "Embodiment robots must be a tuple."
            )

        for robot in self.robots:
            if not isinstance(robot, RobotEmbodiment):
                raise TypeError(
                    "Embodiment robots must contain "
                    "RobotEmbodiment instances."
                )

        if not isinstance(self.avatars, tuple):
            raise TypeError(
                "Embodiment avatars must be a tuple."
            )

        for avatar in self.avatars:
            if not isinstance(avatar, AvatarEmbodiment):
                raise TypeError(
                    "Embodiment avatars must contain "
                    "AvatarEmbodiment instances."
                )

        if not isinstance(self.current, CurrentEmbodiment):
            raise TypeError(
                "Embodiment current must be a CurrentEmbodiment."
            )