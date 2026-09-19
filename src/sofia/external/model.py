from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


class ExternalSystemType(str, Enum):
    API = "api"
    APPLICATION = "application"
    DATABASE = "database"
    DEVICE = "device"
    PLATFORM = "platform"
    SERVICE = "service"
    OTHER = "other"
    UNKNOWN = "unknown"


class ExternalSystemState(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class ExternalObservationState(str, Enum):
    VERIFIED = "verified"
    STALE = "stale"
    UNKNOWN = "unknown"
    CONTRADICTED = "contradicted"


class ExternalSystemResultKind(str, Enum):
    SUCCESS = "success"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


def _validate_non_empty_string(
    value: object,
    field_name: str,
) -> None:
    if not isinstance(value, str):
        raise TypeError(
            f"{field_name} must be a string."
        )

    if not value.strip():
        raise ValueError(
            f"{field_name} must not be empty."
        )


def _freeze_mapping(
    value: Mapping[str, Any],
) -> Mapping[str, Any]:
    frozen: dict[str, Any] = {}

    for key, item in value.items():
        if isinstance(item, Mapping):
            frozen[key] = _freeze_mapping(item)
        elif isinstance(item, list):
            frozen[key] = tuple(
                _freeze_value(element)
                for element in item
            )
        elif isinstance(item, tuple):
            frozen[key] = tuple(
                _freeze_value(element)
                for element in item
            )
        elif isinstance(item, set):
            frozen[key] = frozenset(
                _freeze_value(element)
                for element in item
            )
        else:
            frozen[key] = item

    return MappingProxyType(frozen)


def _freeze_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)

    if isinstance(value, list):
        return tuple(
            _freeze_value(element)
            for element in value
        )

    if isinstance(value, tuple):
        return tuple(
            _freeze_value(element)
            for element in value
        )

    if isinstance(value, set):
        return frozenset(
            _freeze_value(element)
            for element in value
        )

    return value


@dataclass(frozen=True)
class ExternalSystem:
    """
    Stable identity and classification for an external system.

    This model describes what the system is, not what Sofía is
    authorized to do with it.

    Authentication material, credentials, secrets, tokens, and
    authorization decisions deliberately do not belong here.
    """

    system_id: str
    name: str
    system_type: ExternalSystemType
    description: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.system_id,
            "ExternalSystem system_id",
        )

        _validate_non_empty_string(
            self.name,
            "ExternalSystem name",
        )

        if not isinstance(
            self.system_type,
            ExternalSystemType,
        ):
            raise TypeError(
                "ExternalSystem system_type must be "
                "an ExternalSystemType."
            )

        if self.description is not None:
            _validate_non_empty_string(
                self.description,
                "ExternalSystem description",
            )


@dataclass(frozen=True)
class ExternalSystemObservation:
    """
    Immutable evidence about an external system at a point in time.

    The observation is evidence, not authority and not an instruction
    to perform an action.
    """

    system: ExternalSystem
    observed_at: datetime
    state: ExternalObservationState
    evidence: Mapping[str, Any] | None = None
    source_name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(
            self.system,
            ExternalSystem,
        ):
            raise TypeError(
                "ExternalSystemObservation system must be "
                "an ExternalSystem."
            )

        if not isinstance(
            self.observed_at,
            datetime,
        ):
            raise TypeError(
                "ExternalSystemObservation observed_at must "
                "be a datetime."
            )

        if not isinstance(
            self.state,
            ExternalObservationState,
        ):
            raise TypeError(
                "ExternalSystemObservation state must be "
                "an ExternalObservationState."
            )

        if self.evidence is not None:
            if not isinstance(
                self.evidence,
                Mapping,
            ):
                raise TypeError(
                    "ExternalSystemObservation evidence must "
                    "be a mapping or None."
                )

            object.__setattr__(
                self,
                "evidence",
                _freeze_mapping(self.evidence),
            )

        if self.source_name is not None:
            _validate_non_empty_string(
                self.source_name,
                "ExternalSystemObservation source_name",
            )

        if (
            self.state
            is ExternalObservationState.VERIFIED
            and self.evidence is None
        ):
            raise ValueError(
                "Verified external system observations must "
                "contain evidence."
            )

        if (
            self.state
            is not ExternalObservationState.VERIFIED
            and self.evidence is not None
        ):
            raise ValueError(
                "Non-verified external system observations must "
                "not contain evidence."
            )

    @property
    def system_id(self) -> str:
        return self.system.system_id


@dataclass(frozen=True)
class ExternalSystemResult:
    """
    Structured result from an external-system operation boundary.

    This object represents an outcome. It does not execute anything,
    authorize anything, or contain credentials.
    """

    system_id: str
    kind: ExternalSystemResultKind
    evidence: Mapping[str, Any] | None = None
    observed_at: datetime | None = None
    adapter_name: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_string(
            self.system_id,
            "ExternalSystemResult system_id",
        )

        if not isinstance(
            self.kind,
            ExternalSystemResultKind,
        ):
            raise TypeError(
                "ExternalSystemResult kind must be "
                "an ExternalSystemResultKind."
            )

        if self.evidence is not None:
            if not isinstance(
                self.evidence,
                Mapping,
            ):
                raise TypeError(
                    "ExternalSystemResult evidence must "
                    "be a mapping or None."
                )

            object.__setattr__(
                self,
                "evidence",
                _freeze_mapping(self.evidence),
            )

        if self.observed_at is not None:
            if not isinstance(
                self.observed_at,
                datetime,
            ):
                raise TypeError(
                    "ExternalSystemResult observed_at must "
                    "be a datetime or None."
                )

        if self.adapter_name is not None:
            _validate_non_empty_string(
                self.adapter_name,
                "ExternalSystemResult adapter_name",
            )

        if self.error is not None:
            _validate_non_empty_string(
                self.error,
                "ExternalSystemResult error",
            )

        if self.kind is ExternalSystemResultKind.SUCCESS:
            if self.evidence is None:
                raise ValueError(
                    "Successful external system results must "
                    "contain evidence."
                )

            if self.observed_at is None:
                raise ValueError(
                    "Successful external system results must "
                    "contain observation metadata."
                )

            if self.adapter_name is None:
                raise ValueError(
                    "Successful external system results must "
                    "identify the adapter."
                )

        if self.kind is not ExternalSystemResultKind.SUCCESS:
            if self.evidence is not None:
                raise ValueError(
                    "Non-successful external system results must "
                    "not contain evidence."
                )