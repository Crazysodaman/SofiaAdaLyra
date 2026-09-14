from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class OperationalState:
    """
    Immutable description of Sofía's current runtime environment.

    OperationalState describes the current runtime instance.
    It is not persistent identity and must not be used as a substitute
    for SofiaIdentity.
    """

    runtime_id: UUID
    started_at: datetime
    lifecycle_state: str
    application_name: str
    application_version: str
    provider: str
    model: str

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_id, UUID):
            raise TypeError(
                "OperationalState runtime_id must be a UUID."
            )

        if not isinstance(self.started_at, datetime):
            raise TypeError(
                "OperationalState started_at must be a datetime."
            )

        if self.started_at.tzinfo is None:
            raise ValueError(
                "OperationalState started_at must be timezone-aware."
            )

        if not isinstance(self.lifecycle_state, str):
            raise TypeError(
                "OperationalState lifecycle_state must be a str."
            )

        if not self.lifecycle_state:
            raise ValueError(
                "OperationalState lifecycle_state must not be empty."
            )

        if not isinstance(self.application_name, str):
            raise TypeError(
                "OperationalState application_name must be a str."
            )

        if not isinstance(self.application_version, str):
            raise TypeError(
                "OperationalState application_version must be a str."
            )

        if not isinstance(self.provider, str):
            raise TypeError(
                "OperationalState provider must be a str."
            )

        if not isinstance(self.model, str):
            raise TypeError(
                "OperationalState model must be a str."
            )