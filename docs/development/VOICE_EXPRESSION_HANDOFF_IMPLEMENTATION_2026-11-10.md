# Aegis Core voice-expression handoff | implementation checkpoint (2026-11-10)

**Scope:** A Core-owned voice expression cue can be projected from a settled expression decision, validated by a Platform broker, and dispatched to a replaceable Voice sink. This is a functional SDK/broker implementation slice, not yet a live isolated Core-to-module transport or a deployed GPU voice service.

## Implemented on main

- src/sofia/sdk/voice_expression.py: VoiceExpressionCue, schema aegis.voice.expression.v1. Canonical integer-only controls, bounded tags, Core identity, voice-profile identity/revision, message digest, audience, and expiry. No raw speech text, biometric data or audio bytes in the metadata.
- src/sofia/platform/application/expression_runtime.py: voice_handoff_for_message() exports the already-settled, scoped, fresh expression decision without recomputing it or creating audio.
- src/sofia/platform/application/voice_expression_bridge.py: PlatformVoiceExpressionBroker verifies current trusted Core/module bindings, generations, request/digest, scope/audience/correlation, current SAFE decision and mute/STOP/output callback, settled text hash and durable one-use claim BEFORE invoking a voice sink.
- src/sofia/sdk/__init__.py: lazy exports for versioned cue/schema/scope.
- test/test_voice_expression_handoff.py and test/test_companion_expression_runtime.py: positive handoff and explicit denial cases (auth, mute, wrong Core/module, audience, text, generation, timestamps, payload, duplicate playback).

## Required runtime integration and boundaries

1. Only the Platform constructs trusted binding, authorization and output-policy callbacks. It must consult actual SAFE state, not echo a Core-provided grant field.
2. The authorization callback must check current grant/revocation, profile-asset permissions, audience/channel, host/generation and STOP. Caller-provided metadata is never authentication.
3. Output policy must enforce owner mute, text-only Core preference, no device, disabled TTS, and channel restrictions; no microphone is opened by this slice.
4. Text lookup must retrieve the real settled assistant message from canonical conversation state, scope it to the verified audience, and compare SHA256 with the cue.
5. Replay claim must be persistent, transactional and one-use, bound to authenticated Core/generation/request, with uncertain outcomes kept uncertain on crash. Current test stub is only in-memory; never treat it as a production claim store.
6. Actual Voice module maps supported controls only, protects each Core voice profile and supplies true synthesis/playback receipts. A queued or generated waveform is not a confirmed audible playback.
7. For remote clients, waveform bytes may use separately authorized direct transport, but metadata/permissions and receipts stay Platform-governed. No direct Core-to-module privilege.
8. Wire authenticated Core worker IPC to this SDK cue and connect installed Voice module transport, durable claim/state owners and real TTS sinks. Test on authorized Windows/Linux/Fleet hosts before release claims.

## Status

Source and test cases committed to main, **not executed here**. No live production state, microphone, voice model, owner GPU, Fleet grant or audio device was changed. The legacy local SofiaApplication.speak() path remains unchanged and still recomputes its own profile; consolidating this with the persisted expression decision is still an integration task. This checkpoint is NOT full voice-module completion or live shakedown evidence.
