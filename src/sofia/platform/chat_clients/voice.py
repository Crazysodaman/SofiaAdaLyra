"""Explicit seam for future simultaneous multi-Core voice.

No group voice capability is claimed here. A client may only report group voice
after independent real-audio session evidence exists for every participating
Core; synthetic text simulation is insufficient.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sofia.platform.chat_clients.contracts import normalize_core_id


class AudioEvidenceKind(str, Enum):
    NONE = "none"
    DETERMINISTIC_SIMULATION = "deterministic_simulation"
    REAL_AUDIO_SESSION = "real_audio_session"


@dataclass(frozen=True, slots=True)
class AudioTestEvidence:
    kind: AudioEvidenceKind
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, AudioEvidenceKind):
            raise TypeError("kind must be an AudioEvidenceKind")
        if type(self.evidence_refs) is not tuple or any(
            not isinstance(item, str) or not item.strip()
            for item in self.evidence_refs
        ):
            raise ValueError("evidence_refs must be nonempty strings")
        if (
            self.kind is AudioEvidenceKind.REAL_AUDIO_SESSION
            and not self.evidence_refs
        ):
            raise ValueError("real audio evidence requires independent references")


@dataclass(frozen=True, slots=True)
class VoiceSeamReport:
    participating_core_ids: tuple[str, ...]
    simultaneous_voice_supported: bool
    group_voice_claimed: bool
    evidence_kind: AudioEvidenceKind
    reason: str


class SimultaneousCoreVoiceSeam:
    """Reserves a transport-neutral seam without pretending audio works."""

    def __init__(self) -> None:
        self._evidence: dict[str, AudioTestEvidence] = {}

    def record_evidence(self, core_id: str, evidence: AudioTestEvidence) -> None:
        core = normalize_core_id(core_id).lower()
        if not isinstance(evidence, AudioTestEvidence):
            raise TypeError("evidence must be AudioTestEvidence")
        self._evidence[core] = evidence

    def report(self, core_ids: tuple[str, ...]) -> VoiceSeamReport:
        if type(core_ids) is not tuple or not core_ids:
            raise ValueError("core_ids must be a nonempty tuple")
        normalized = tuple(normalize_core_id(item).lower() for item in core_ids)
        if len(set(normalized)) != len(normalized):
            raise ValueError("core_ids must be distinct")
        rows = tuple(self._evidence.get(core) for core in normalized)
        real = bool(rows) and all(
            row is not None and row.kind is AudioEvidenceKind.REAL_AUDIO_SESSION
            for row in rows
        )
        if not real:
            return VoiceSeamReport(
                participating_core_ids=normalized,
                simultaneous_voice_supported=False,
                group_voice_claimed=False,
                evidence_kind=AudioEvidenceKind.NONE,
                reason=(
                    "no real multi-Core audio session evidence; "
                    "text simulation cannot prove group voice"
                ),
            )
        return VoiceSeamReport(
            participating_core_ids=normalized,
            simultaneous_voice_supported=True,
            group_voice_claimed=True,
            evidence_kind=AudioEvidenceKind.REAL_AUDIO_SESSION,
            reason="independent real audio evidence recorded for every Core",
        )
