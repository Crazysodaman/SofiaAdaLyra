from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class SofiaIdentity:
    """
    Persistent identity of Sofía.

    The instance_id identifies the logical Sofía instance independently
    of the process, computer, interface, model, or provider currently
    hosting her.

    When instance_id is omitted, a new UUID is generated. IdentityStore
    persists that generated value so subsequent loads retain the same
    logical identity.
    """

    name: str
    instance_id: UUID = field(default_factory=uuid4)

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