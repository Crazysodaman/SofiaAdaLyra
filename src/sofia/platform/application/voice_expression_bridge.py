"""Platform-governed adapter from a Core's voice cue to a voice module.

The Core submits non-authoritative expressive metadata. The Platform
independently verifies current component bindings, SAFE permission, audience,
mute/STOP/output policy, original settled speech text and a one-use claim.
Only then may an installed audio adapter submit work. No direct Core-to-device
authority is created by this helper.
"""
from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Callable, Protocol

from sofia.sdk.contracts import ComponentEndpoint, ComponentKind, ComponentRequestEnvelope
from sofia.sdk.contract_wire import canonical_sha256
from sofia.sdk.voice_expression import (
    VOICE_EXPRESSION_SCHEMA, VOICE_SYNTHESIZE_SCOPE, VoiceExpressionCue,
)
from sofia.modules.voice.prosody_matrix import VoiceProsodyProfile


class VoiceOutputSink(Protocol):
    def submit(
        self, text: str, *, profile: VoiceProsodyProfile,
        correlation_id: str | None = None,
    ) -> object: ...


class PlatformVoiceExpressionBroker:
    """Require trusted Platform callbacks for every effectful handoff.

    The resolvers MUST consult current Platform binding/generation/SAFE records,
    not caller-provided identity strings or Core-controlled metadata. This is
    an internal broker building block, not an authenticated network listener.
    """

    def __init__(
        self, *,
        current_core: Callable[[str], ComponentEndpoint | None],
        current_module: Callable[[str], ComponentEndpoint | None],
        authorize: Callable[[ComponentRequestEnvelope, VoiceExpressionCue], bool],
        output_allowed: Callable[[str, str], bool],
        profile_allowed: Callable[[str, str, int], bool],
        settled_text: Callable[[str, str], str | None],
        claim_once: Callable[[str], bool],
        sink: VoiceOutputSink,
    ) -> None:
        callbacks = (current_core, current_module, authorize, output_allowed,
                     profile_allowed, settled_text, claim_once)
        if any(not callable(item) for item in callbacks):
            raise TypeError("all Platform voice authority callbacks are required")
        if not callable(getattr(sink, "submit", None)):
            raise TypeError("voice output sink must have submit()")
        self._current_core = current_core
        self._current_module = current_module
        self._authorize = authorize
        self._output_allowed = output_allowed
        self._profile_allowed = profile_allowed
        self._settled_text = settled_text
        self._claim_once = claim_once
        self._sink = sink

    @staticmethod
    def _profile(cue: VoiceExpressionCue) -> VoiceProsodyProfile:
        return VoiceProsodyProfile(
            rate_scale=cue.rate_units / 10_000,
            pitch_semitones=cue.pitch_units / 10_000,
            energy_scale=cue.energy_units / 10_000,
            volume_scale=cue.volume_units / 10_000,
            pause_scale=cue.pause_units / 10_000,
            tone_tags=cue.tone_tags,
            ambient_context=cue.ambient_context,
        )

    def submit(
        self, request: ComponentRequestEnvelope, payload: object,
        *, now: datetime,
    ) -> object:
        """Submit at most once after all independent gates pass.

        claim_once must atomically reject replayed request IDs against a
        persistent Platform-owned store. A failed/uncertain submission must
        not be blindly replayed by inventing a fresh request ID.
        """
        if not isinstance(request, ComponentRequestEnvelope):
            raise TypeError("SDK ComponentRequestEnvelope required")
        cue = VoiceExpressionCue.from_payload(payload)
        if request.payload_type != VOICE_EXPRESSION_SCHEMA:
            raise PermissionError("wrong voice-expression payload type")
        if request.source.kind is not ComponentKind.CORE:
            raise PermissionError("only a bound Core may submit voice expression")
        if request.destination.kind is not ComponentKind.MODULE:
            raise PermissionError("voice destination must be a bound module")
        if request.source.core_identity_id != cue.core_identity_id:
            raise PermissionError("Core identity does not match voice cue")
        if request.authority.audience_id != cue.audience_id:
            raise PermissionError("audience does not match voice cue")
        if request.correlation_id != cue.decision_id:
            raise PermissionError("decision correlation mismatch")
        if VOICE_SYNTHESIZE_SCOPE not in request.authority.scopes:
            raise PermissionError("voice synthesis scope is missing")
        if request.payload_digest != canonical_sha256(cue.to_payload()):
            raise PermissionError("voice expression payload digest mismatch")

        actual_core = self._current_core(cue.core_identity_id)
        actual_module = self._current_module(request.destination.component_id)
        if actual_core is None or actual_core != request.source:
            raise PermissionError("Core is not the currently bound generation")
        if actual_module is None or actual_module != request.destination:
            raise PermissionError("voice module is not the currently bound generation")
        request.require_dispatchable(
            now=now,
            expected_destination_generation=actual_module.generation,
        )
        cue.require_fresh(now)
        if not self._authorize(request, cue):
            raise PermissionError("Platform SAFE rejected voice handoff")
        if not self._output_allowed(cue.core_identity_id, cue.audience_id):
            raise PermissionError("voice output disabled, stopped, muted or disallowed")
        if not self._profile_allowed(cue.core_identity_id, cue.voice_profile_id,
                                     cue.voice_profile_revision):
            raise PermissionError("voice profile/revision not approved for this Core")

        # Fetch from authoritative conversation storage, not Core-submitted text.
        text = self._settled_text(cue.message_id, cue.audience_id)
        if not isinstance(text, str) or not text.strip():
            raise PermissionError("settled speech text is unavailable")
        if sha256(text.encode("utf-8")).hexdigest() != cue.text_sha256:
            raise PermissionError("settled speech text digest mismatch")
        if not self._claim_once(request.request_id):
            raise PermissionError("voice request replay rejected")
        # TTS queue results (including rejected/unavailable) remain truthful.
        return self._sink.submit(
            text, profile=self._profile(cue), correlation_id=cue.decision_id,
        )
