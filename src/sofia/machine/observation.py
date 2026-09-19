from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from sofia.machine.model import MachineProfile


class ObservationState(str, Enum):
    VERIFIED = "verified"
    STALE = "stale"
    UNKNOWN = "unknown"
    CONTRADICTED = "contradicted"


class ObservationSource(str, Enum):
    MACHINE_DISCOVERY = "machine_discovery"
    RUNTIME = "runtime"
    EXTERNAL = "external"
    MANUAL = "manual"


@dataclass(frozen=True)
class ObservationProvenance:
    source_type: ObservationSource
    source_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_type, ObservationSource):
            raise TypeError(
                "ObservationProvenance source_type must be "
                "an ObservationSource."
            )

        if not isinstance(self.source_name, str):
            raise TypeError(
                "ObservationProvenance source_name must be a string."
            )

        if not self.source_name.strip():
            raise ValueError(
                "ObservationProvenance source_name must not be empty."
            )


@dataclass(frozen=True)
class MachineObservation:
    profile: MachineProfile
    observed_at: datetime
    verified_at: datetime
    provenance: ObservationProvenance
    state: ObservationState = ObservationState.VERIFIED

    def __post_init__(self) -> None:
        if not isinstance(self.profile, MachineProfile):
            raise TypeError(
                "MachineObservation profile must be a MachineProfile."
            )

        if not isinstance(self.observed_at, datetime):
            raise TypeError(
                "MachineObservation observed_at must be a datetime."
            )

        if not isinstance(self.verified_at, datetime):
            raise TypeError(
                "MachineObservation verified_at must be a datetime."
            )

        if self.verified_at < self.observed_at:
            raise ValueError(
                "MachineObservation verified_at must not be earlier "
                "than observed_at."
            )

        if not isinstance(
            self.provenance,
            ObservationProvenance,
        ):
            raise TypeError(
                "MachineObservation provenance must be an "
                "ObservationProvenance."
            )

        if not isinstance(self.state, ObservationState):
            raise TypeError(
                "MachineObservation state must be an ObservationState."
            )

    @property
    def machine_id(self) -> str:
        return self.profile.identity.machine_id

    @property
    def hostname(self) -> str:
        return self.profile.identity.hostname

    def with_state(
        self,
        state: ObservationState,
    ) -> "MachineObservation":
        if not isinstance(state, ObservationState):
            raise TypeError(
                "MachineObservation state must be an ObservationState."
            )

        return MachineObservation(
            profile=self.profile,
            observed_at=self.observed_at,
            verified_at=self.verified_at,
            provenance=self.provenance,
            state=state,
        )

    def reverified(
        self,
        verified_at: datetime,
    ) -> "MachineObservation":
        if not isinstance(verified_at, datetime):
            raise TypeError(
                "MachineObservation verified_at must be a datetime."
            )

        if verified_at < self.observed_at:
            raise ValueError(
                "MachineObservation verified_at must not be earlier "
                "than observed_at."
            )

        return MachineObservation(
            profile=self.profile,
            observed_at=self.observed_at,
            verified_at=verified_at,
            provenance=self.provenance,
            state=ObservationState.VERIFIED,
        )