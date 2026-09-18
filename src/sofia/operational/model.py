from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class ContinuityEvidenceStatus(str, Enum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


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


@dataclass(frozen=True)
class RuntimeContinuity:
    """
    Immutable evidence describing continuity between the current
    runtime and a previously recorded runtime.

    RuntimeContinuity is operational evidence only. It does not claim
    that a previous process remains alive, nor does it define Sofía's
    persistent identity.
    """

    evidence_status: ContinuityEvidenceStatus
    current_runtime_id: UUID
    current_started_at: datetime
    previous_runtime_id: UUID | None = None
    previous_started_at: datetime | None = None
    previous_stopped_at: datetime | None = None
    previous_lifecycle_state: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.evidence_status,
            ContinuityEvidenceStatus,
        ):
            raise TypeError(
                "RuntimeContinuity evidence_status must be a "
                "ContinuityEvidenceStatus."
            )

        if not isinstance(
            self.current_runtime_id,
            UUID,
        ):
            raise TypeError(
                "RuntimeContinuity current_runtime_id must be a UUID."
            )

        if not isinstance(
            self.current_started_at,
            datetime,
        ):
            raise TypeError(
                "RuntimeContinuity current_started_at must be a datetime."
            )

        if self.current_started_at.tzinfo is None:
            raise ValueError(
                "RuntimeContinuity current_started_at must be "
                "timezone-aware."
            )

        for name, value in (
            ("previous_started_at", self.previous_started_at),
            ("previous_stopped_at", self.previous_stopped_at),
        ):
            if value is not None:
                if not isinstance(value, datetime):
                    raise TypeError(
                        f"RuntimeContinuity {name} must be a datetime "
                        "or None."
                    )

                if value.tzinfo is None:
                    raise ValueError(
                        f"RuntimeContinuity {name} must be "
                        "timezone-aware."
                    )

        if (
            self.previous_runtime_id is not None
            and not isinstance(self.previous_runtime_id, UUID)
        ):
            raise TypeError(
                "RuntimeContinuity previous_runtime_id must be a UUID "
                "or None."
            )

        if (
            self.previous_lifecycle_state is not None
            and not isinstance(self.previous_lifecycle_state, str)
        ):
            raise TypeError(
                "RuntimeContinuity previous_lifecycle_state must be "
                "a str or None."
            )

        if self.evidence_status is ContinuityEvidenceStatus.OBSERVED:
            if self.previous_runtime_id is None:
                raise ValueError(
                    "Observed RuntimeContinuity must contain a "
                    "previous_runtime_id."
                )

            if self.previous_started_at is None:
                raise ValueError(
                    "Observed RuntimeContinuity must contain a "
                    "previous_started_at."
                )

    @property
    def restart_observed(self) -> bool | None:
        """
        Return whether a previous runtime has been observed.

        True means a previous runtime was observed.
        None means there is insufficient evidence.

        False is intentionally never returned because absence of
        evidence is not evidence that no prior runtime existed.
        """

        if self.previous_runtime_id is not None:
            return True

        return None