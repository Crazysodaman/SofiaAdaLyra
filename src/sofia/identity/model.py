from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class SofiaIdentity:
    """
    Persistent identity of Sofía.

    The instance_id identifies the logical Sofía instance independently
    of the process, computer, interface, model, or provider currently
    hosting her.
    """

    name: str
    instance_id: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError(
                "SofiaIdentity name must be a string."
            )

        if not self.name.strip():
            raise ValueError(
                "SofiaIdentity name cannot be empty."
            )

        if not isinstance(self.instance_id, UUID):
            raise TypeError(
                "SofiaIdentity instance_id must be a UUID."
            )