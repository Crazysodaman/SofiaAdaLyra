"""Project host-owned evidence for matrix requests without owning runtime state."""
from __future__ import annotations

from typing import TYPE_CHECKING
from sofia.cognition.matrix import EvidenceRecord, EvidenceState
from sofia.cognition.model import CognitiveResponse
from sofia.environment.model import EnvironmentFreshness

if TYPE_CHECKING:
    from sofia.runtime.runtime import SofiaRuntime


def project_matrix_evidence(
    runtime: SofiaRuntime,
    *,
    required_keys: tuple[str, ...] | None = None,
    response: CognitiveResponse | None = None,
) -> dict[str, EvidenceRecord | EvidenceState]:
    """Project only host-owned evidence requested by the matrix layer."""
    if required_keys is not None:
        if not isinstance(required_keys, tuple):
            raise TypeError("required_keys must be a tuple or None")
        if any(
            not isinstance(key, str) or not key.strip()
            for key in required_keys
        ):
            raise ValueError(
                "required_keys must contain nonempty strings"
            )
        wanted = set(required_keys)
    else:
        wanted = {
            "avatar.canonical",
            "memory.retrieval",
            "cognition.configuration",
            "continuity.current",
            "interaction.interpretation",
            "emotion.current",
            "operational.measurement",
            "action.execution_receipt",
            "environment.current",
            "environment.weather.current",
            "environment.clock.current",
            "environment.location.current",
            "environment.calendar.current",
        }

    all_static: dict[str, EvidenceRecord | EvidenceState] = {
        "avatar.canonical": EvidenceRecord(
            "avatar.canonical",
            (
                EvidenceState.AVAILABLE
                if (
                    runtime._embodiment is not None
                    and runtime._avatar_presentation is not None
                )
                else EvidenceState.MISSING
            ),
            (
                "runtime:avatar-canonical-and-presentation"
                if (
                    runtime._embodiment is not None
                    and runtime._avatar_presentation is not None
                )
                else None
            ),
        ),
        "memory.retrieval": EvidenceState.UNKNOWN,
        "cognition.configuration": EvidenceRecord(
            "cognition.configuration",
            EvidenceState.AVAILABLE,
            "runtime:cognitive-configuration",
        ),
        "continuity.current": EvidenceRecord(
            "continuity.current",
            (
                EvidenceState.AVAILABLE
                if runtime._runtime_continuity is not None
                else EvidenceState.MISSING
            ),
            (
                "runtime:continuity"
                if runtime._runtime_continuity is not None
                else None
            ),
        ),
        "interaction.interpretation": EvidenceState.UNKNOWN,
        "emotion.current": EvidenceState.UNKNOWN,
        "operational.measurement": EvidenceState.MISSING,
        "action.execution_receipt": EvidenceState.MISSING,
    }
    availability = {
        key: value
        for key, value in all_static.items()
        if key in wanted
    }

    environment_keys = {
        "environment.current",
        "environment.weather.current",
        "environment.location.current",
        "environment.calendar.current",
    }
    snapshot = (
        runtime._environment_service.snapshot(refresh_providers=False)
        if wanted & environment_keys
        else None
    )

    if "environment.clock.current" in wanted:
        availability["environment.clock.current"] = EvidenceRecord(
            "environment.clock.current",
            EvidenceState.AVAILABLE,
            "runtime:clock",
        )

    if snapshot is not None:
        if (
            snapshot.weather is not None
            and snapshot.weather_freshness
            is EnvironmentFreshness.CURRENT
        ):
            weather_state: EvidenceRecord | EvidenceState = (
                EvidenceRecord(
                    "environment.weather.current",
                    EvidenceState.AVAILABLE,
                    f"environment:{snapshot.weather.source_id}",
                )
            )
        elif snapshot.weather_freshness is EnvironmentFreshness.STALE:
            weather_state = EvidenceState.STALE
        else:
            weather_state = EvidenceState.MISSING

        if "environment.weather.current" in wanted:
            availability["environment.weather.current"] = weather_state

        if "environment.current" in wanted:
            availability["environment.current"] = (
                EvidenceRecord(
                    "environment.current",
                    EvidenceState.AVAILABLE,
                    "environment:snapshot",
                )
            )

        if "environment.location.current" in wanted:
            if (
                snapshot.current_location is not None
                and snapshot.current_location_freshness
                is EnvironmentFreshness.CURRENT
            ):
                availability["environment.location.current"] = (
                    EvidenceRecord(
                        "environment.location.current",
                        EvidenceState.AVAILABLE,
                        (
                            "environment:"
                            + snapshot.current_location.source_id
                        ),
                    )
                )
            elif (
                snapshot.current_location_freshness
                is EnvironmentFreshness.STALE
            ):
                availability["environment.location.current"] = (
                    EvidenceState.STALE
                )
            else:
                availability["environment.location.current"] = (
                    EvidenceState.MISSING
                )

        if "environment.calendar.current" in wanted:
            availability["environment.calendar.current"] = (
                EvidenceRecord(
                    "environment.calendar.current",
                    EvidenceState.AVAILABLE,
                    "runtime:calendar",
                )
                if (
                    snapshot.season is not None
                    or snapshot.daylight is not None
                )
                else EvidenceState.MISSING
            )

    if response is not None and "operational.measurement" in wanted:
        if not isinstance(response, CognitiveResponse):
            raise TypeError(
                "matrix evidence response must be CognitiveResponse or None"
            )
        operational_refs = tuple(
            ref
            for ref in response.evidence_refs
            if ref.startswith(
                (
                    "capability:system.inspect",
                    "capability:process.inspect",
                    "capability:network.inspect",
                    "capability:hardware.inspect",
                    "capability:service.inspect",
                    "capability:machine.",
                    "capability:ops.",
                    "capability:storage.",
                    "capability:remote.",
                    "capability:telemetry.",
                )
            )
        )
        if operational_refs:
            availability["operational.measurement"] = EvidenceRecord(
                "operational.measurement",
                EvidenceState.AVAILABLE,
                operational_refs[0],
            )

    if response is not None and "action.execution_receipt" in wanted:
        execution_refs = tuple(
            ref
            for ref in response.evidence_refs
            if ref.startswith("execution-receipt:")
        )
        if execution_refs:
            availability["action.execution_receipt"] = EvidenceRecord(
                "action.execution_receipt",
                EvidenceState.AVAILABLE,
                execution_refs[0],
            )

    return availability
