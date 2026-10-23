"""Typed learning contracts which deliberately carry no authority."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Mapping

from sofia.core.social.model import PrincipalContext


class DataUse(str, Enum):
    OBSERVATION = "observation"
    STORAGE = "storage"
    FEATURE_EXTRACTION = "feature_extraction"
    STATISTICAL_TRAINING = "statistical_training"
    LLM_WEIGHT_TRAINING = "llm_weight_training"
    DEPLOYMENT = "deployment"


class SourceClass(str, Enum):
    FLEET_TELEMETRY = "fleet_telemetry"
    OPS_OBSERVATION = "ops_observation"
    OPERATION_RECEIPT = "operation_receipt"
    GOAL_EVIDENCE = "goal_evidence"
    ARTIFACT_EVALUATION = "artifact_evaluation"
    PUBLIC_REVIEWED_DATASET = "public_reviewed_dataset"
    RAW_CONVERSATION = "raw_conversation"
    PRIVATE_JOURNAL = "private_journal"
    SCREEN_CAPTURE = "screen_capture"
    AUDIO_CAPTURE = "audio_capture"


PROHIBITED_TRAINING_SOURCES = frozenset({
    SourceClass.RAW_CONVERSATION,
    SourceClass.PRIVATE_JOURNAL,
    SourceClass.SCREEN_CAPTURE,
    SourceClass.AUDIO_CAPTURE,
})


class OutcomeClass(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    UNKNOWN = "unknown"


class PredictionMode(str, Enum):
    OBSERVE = "observe"
    SHADOW = "shadow"
    ADVISORY = "advisory"
    LIMITED = "limited"


class PredictionDisposition(str, Enum):
    SUPPRESSED = "suppressed"
    SHADOW_ONLY = "shadow_only"
    DISPLAY_ADVISORY = "display_advisory"
    FORWARD_TO_EXISTING_POLICY = "forward_to_existing_policy"


def _aware(value: datetime, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _named(value: str, field: str, *, maximum: int = 300) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{field} must be a bounded nonempty string")
    return value


@dataclass(frozen=True, slots=True)
class DataUseGrant:
    """An authenticated boundary's exact data-use decision, not consent inferred by ML."""

    grant_id: str
    principal_id: str
    audience_id: str
    purpose: str
    uses: frozenset[DataUse]
    issued_at: datetime
    expires_at: datetime
    approval_ref: str

    def __post_init__(self) -> None:
        for field in ("grant_id", "principal_id", "audience_id", "purpose", "approval_ref"):
            _named(getattr(self, field), field)
        if not isinstance(self.uses, frozenset) or not self.uses or any(
            not isinstance(value, DataUse) for value in self.uses
        ):
            raise TypeError("uses must be a nonempty frozenset of DataUse")
        issued = _aware(self.issued_at, "issued_at")
        expires = _aware(self.expires_at, "expires_at")
        if expires <= issued:
            raise ValueError("data-use grant must expire after issuance")
        if expires - issued > timedelta(days=365):
            raise ValueError("data-use grant cannot exceed one year")
        if not self.approval_ref.startswith(("owner-ui:", "safe:")):
            raise PermissionError("data-use grant requires authenticated owner/SAFE evidence")

    def permits(self, *required: DataUse, at: datetime) -> bool:
        moment = _aware(at, "at")
        return self.issued_at.astimezone(timezone.utc) <= moment < self.expires_at.astimezone(timezone.utc) and all(
            use in self.uses for use in required
        )


@dataclass(frozen=True, slots=True)
class Prediction:
    """A scoped, expiring estimate. It cannot prove facts or authorize actions."""

    prediction_id: str
    candidate_digest: str
    subject_id: str
    principal_id: str
    audience_id: str
    generated_at: datetime
    expires_at: datetime
    mode: PredictionMode
    value: Mapping[str, float | int | bool | None]
    uncertainty: float
    reason_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        for field in (
            "prediction_id", "candidate_digest", "subject_id",
            "principal_id", "audience_id",
        ):
            _named(getattr(self, field), field)
        if len(self.candidate_digest) != 64 or any(
            character not in "0123456789abcdef" for character in self.candidate_digest
        ):
            raise ValueError("candidate_digest must be lowercase SHA-256")
        if not isinstance(self.mode, PredictionMode):
            raise TypeError("mode must be PredictionMode")
        generated = _aware(self.generated_at, "generated_at")
        expires = _aware(self.expires_at, "expires_at")
        if expires <= generated:
            raise ValueError("prediction must expire after generation")
        if type(self.uncertainty) not in (int, float) or not 0 <= self.uncertainty <= 1:
            raise ValueError("uncertainty must be in [0, 1]")
        if not isinstance(self.value, Mapping) or not self.value or any(
            not isinstance(key, str) or not key.strip()
            or type(item) not in (int, float, bool, type(None))
            or (type(item) is float and not isfinite(item))
            for key, item in self.value.items()
        ):
            raise TypeError("prediction values must be bounded scalar features")
        if not isinstance(self.reason_refs, tuple) or not self.reason_refs or any(
            not isinstance(value, str) or not value.strip() for value in self.reason_refs
        ):
            raise ValueError("prediction requires source reason references")
        object.__setattr__(self, "value", MappingProxyType(dict(self.value)))

    def visible_to(self, principal: PrincipalContext) -> bool:
        if not isinstance(principal, PrincipalContext):
            raise TypeError("authenticated PrincipalContext required")
        return (
            principal.principal_id == self.principal_id
            and principal.audience_id == self.audience_id
        )

    @property
    def grants_authority(self) -> bool:
        return False

    @property
    def is_factual_evidence(self) -> bool:
        return False

    @property
    def grants_consent(self) -> bool:
        return False

    def disposition(
        self, *, principal: PrincipalContext, at: datetime,
        operator_stop: bool, gaming: bool,
    ) -> PredictionDisposition:
        """Decide visibility/forwarding only; never execute or authorize.

        LIMITED means a fresh recommendation may be handed to the existing
        deterministic policy boundary. It still cannot call a capability.
        """
        if type(operator_stop) is not bool or type(gaming) is not bool:
            raise TypeError("operator_stop and gaming must be bool")
        moment = _aware(at, "at")
        if not self.visible_to(principal) or moment >= self.expires_at.astimezone(timezone.utc):
            return PredictionDisposition.SUPPRESSED
        if operator_stop or gaming or self.mode in (PredictionMode.OBSERVE, PredictionMode.SHADOW):
            return PredictionDisposition.SHADOW_ONLY
        if self.mode is PredictionMode.ADVISORY:
            return PredictionDisposition.DISPLAY_ADVISORY
        return PredictionDisposition.FORWARD_TO_EXISTING_POLICY
