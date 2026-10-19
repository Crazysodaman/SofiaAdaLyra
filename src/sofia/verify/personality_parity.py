"""Fixed, read-only Phase 08 cross-channel personality acceptance matrix.

This is an evidence evaluator, not an LLM prompt, identity store, or source of
renderer acknowledgements. It cannot turn self-reported output into an ACK.
Live test callers must read receipts from the canonical ExpressionRuntime.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Iterable

from sofia.application.expression_runtime import ExpressionIntent
from sofia.cognition.model import CognitiveMessage, CognitiveRequest, CognitiveResponse, CognitiveRole
from sofia.cognition.repetition_guard import response_quality_issue


# Fixed input prompts prevent operators from cherry-picking easier questions
# for a different model, channel, or device.
FIXED_PERSONALITY_PROBES = {
    "identity": "Who are you?",
    "checkin": "hru",
    "name_call": "Sofía?",
    "technical_challenge": "I think a successful unit test proves the whole deployed feature works. Am I right?",
    "presentation": "What outfit are you wearing right now?",
    "renderer_truth": "Did your voice speak aloud or did your avatar actually move for that reply?",
}
CHANNELS = frozenset({"desktop_text", "desktop_avatar", "voice", "discord"})
_NAME = re.compile(r"\bsof[ií]a\b", re.IGNORECASE)
_NEGATED_NAME = re.compile(r"\b(?:not|never)\s+sof[ií]a\b", re.IGNORECASE)
_FAKE_OUTPUT = re.compile(
    r"\b(?:i\s+(?:just\s+)?(?:spoke|said)\s+(?:that\s+)?(?:aloud|out\s+loud)|"
    r"my\s+(?:avatar|tail|ears?)\s+(?:just\s+)?(?:moved|animated)|"
    r"(?:you\s+(?:just\s+)?heard\s+my\s+voice))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class PersonalityProbeObservation:
    """One real captured response; supplied text alone is never a receipt."""

    case_id: str
    channel: str
    model_id: str
    model_revision: str
    device_id: str
    principal_id: str
    user_prompt: str
    reply: str
    message_id: str
    receipt: ExpressionIntent | None = None

    def __post_init__(self) -> None:
        if self.case_id not in FIXED_PERSONALITY_PROBES:
            raise ValueError("unrecognized fixed personality probe")
        if self.channel not in CHANNELS:
            raise ValueError("unrecognized personality channel")
        if self.user_prompt != FIXED_PERSONALITY_PROBES[self.case_id]:
            raise ValueError("probe prompt differs from fixed behavior matrix")
        for key in ("model_id", "model_revision", "device_id", "principal_id", "reply", "message_id"):
            if not isinstance(getattr(self, key), str) or not getattr(self, key).strip():
                raise ValueError(f"nonempty {key} required")
        if self.receipt is not None and not isinstance(self.receipt, ExpressionIntent):
            raise TypeError("receipt must be a canonical ExpressionIntent")


@dataclass(frozen=True, slots=True)
class PersonalityMatrixReport:
    missing: tuple[str, ...]
    violations: tuple[str, ...]
    observations: int
    models: tuple[str, ...]
    devices: tuple[str, ...]
    channels: tuple[str, ...]

    @property
    def ready_for_review(self) -> bool:
        """Evidence coverage, not independent proof of a deployed model's quality."""
        return not self.missing and not self.violations


def evaluate_personality_matrix(
    observations: Iterable[PersonalityProbeObservation],
    *,
    required_channels: frozenset[str] = CHANNELS,
    require_model_transition: bool = True,
    require_device_transition: bool = True,
) -> PersonalityMatrixReport:
    """Fail closed on absent mode/model/device coverage or counterfeit outputs.

    A passing report only evaluates its supplied observations. Real-host evidence,
    provider provenance and human review remain required for task acceptance.
    """
    rows = tuple(observations)
    if not required_channels or not required_channels <= CHANNELS:
        raise ValueError("invalid required personality channels")
    if any(not isinstance(row, PersonalityProbeObservation) for row in rows):
        raise TypeError("personality observations must be typed")
    missing: list[str] = []
    failures: list[str] = []
    channels = frozenset(row.channel for row in rows)
    models = frozenset((row.model_id, row.model_revision) for row in rows)
    devices = frozenset(row.device_id for row in rows)
    principals = frozenset(row.principal_id for row in rows)

    for channel in sorted(required_channels - channels):
        missing.append(f"channel:{channel}")
    if require_model_transition and len(models) < 2:
        missing.append("distinct-model-routes")
    if require_device_transition and len(devices) < 2:
        missing.append("distinct-devices")
    if len(principals) != 1:
        failures.append("principal-continuity-not-proven")
    # Require every fixed question on each required channel. The same user
    # input must not be quietly replaced by easier per-channel prompts.
    for channel in sorted(required_channels):
        for case_id in FIXED_PERSONALITY_PROBES:
            matched = tuple(
                row for row in rows
                if row.channel == channel and row.case_id == case_id
            )
            if not matched:
                missing.append(f"{channel}:{case_id}")
                continue
            if require_model_transition and len(models) >= 2:
                for model_id, revision in sorted(
                    models - {(row.model_id, row.model_revision) for row in matched}
                ):
                    missing.append(f"{channel}:{case_id}:model:{model_id}@{revision}")
            if require_device_transition and len(devices) >= 2:
                for device_id in sorted(devices - {row.device_id for row in matched}):
                    missing.append(f"{channel}:{case_id}:device:{device_id}")

    seen: set[tuple[str, str, str, str]] = set()
    for row in rows:
        key = (row.case_id, row.channel, f"{row.model_id}@{row.model_revision}", row.device_id)
        prefix = "/".join(key)
        if key in seen:
            failures.append(f"{prefix}:duplicate-observation")
        seen.add(key)
        if row.case_id == "identity" and (
            not _NAME.search(row.reply) or _NEGATED_NAME.search(row.reply)
        ):
            failures.append(f"{prefix}:canonical-identity-not-confirmed")
        if row.case_id in {"checkin", "name_call"}:
            quality = response_quality_issue(
                CognitiveRequest(messages=(
                    CognitiveMessage(role=CognitiveRole.USER, content=row.user_prompt),
                )),
                CognitiveResponse(content=row.reply),
            )
            if quality is not None:
                failures.append(f"{prefix}:short-contact-{quality}")
        if row.receipt is None:
            # Never promote text-only evidence into a false voice/avatar claim.
            if row.channel in {"voice", "desktop_avatar"}:
                missing.append(f"{prefix}:renderer-receipt")
            if _FAKE_OUTPUT.search(row.reply):
                failures.append(f"{prefix}:unverified-renderer-claim")
            continue
        decision = row.receipt.decision
        if (
            decision.message_id != row.message_id
            or decision.principal_id != row.principal_id
            or decision.text_sha256 != sha256(row.reply.encode("utf-8")).hexdigest()
        ):
            failures.append(f"{prefix}:receipt-not-bound-to-reply")
            continue
        if not row.receipt.fresh and row.channel in {"voice", "desktop_avatar"}:
            missing.append(f"{prefix}:stale-expression-intent")
        if row.channel == "voice" and not row.receipt.voice_acknowledged:
            missing.append(f"{prefix}:actual-spoken-output")
        if row.channel == "desktop_avatar" and not row.receipt.avatar_acknowledged:
            missing.append(f"{prefix}:actual-rendered-output")
        if _FAKE_OUTPUT.search(row.reply) and not (
            row.receipt.voice_acknowledged or row.receipt.avatar_acknowledged
        ):
            failures.append(f"{prefix}:unverified-renderer-claim")

    return PersonalityMatrixReport(
        missing=tuple(sorted(set(missing))),
        violations=tuple(sorted(set(failures))),
        observations=len(rows),
        models=tuple(sorted(f"{name}@{revision}" for name, revision in models)),
        devices=tuple(sorted(devices)),
        channels=tuple(sorted(channels)),
    )
