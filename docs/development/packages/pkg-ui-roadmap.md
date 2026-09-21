# PKG-UI | Voice, avatar, authenticated clients and Discord adapter

**Branch:** `feature/pkg-ui-foundation`, forked from `main` SHA `2141879`. **Status:** pure expression-channel receipt model, not a renderer, speech engine or bot. No microphone, camera, avatar, Discord credential, client or service has been enabled.

## Outcome and package boundaries
Provide optional CLI, desktop, web/mobile and private Discord DM interfaces to **one shared Sofía runtime**. Text interaction must work without an avatar; a generated stage direction is not a played animation. INTERACT owns represented gesture semantics and Discord social contracts; ACT owns opt-in outbound policy; SAFE owns authenticated clients, global stop and revocation; NET owns remote transport if applicable.

## Delivery slices
1. **U0 audit:** inventory existing CLI, canonical avatar records, expression catalog, authentication and OS capabilities. Document what has actually rendered or played versus merely specified.
2. **U1 client/session API:** authenticated caller and stable source-message ID, per-channel authorization, ordering/replay checks, cancellation, rate and payload limits. A Discord ID is not trusted without enrollment proof. No duplicate Sofía personality instance.
3. **U2 text/desktop:** plain dialogue without a renderer; optional avatar overlay with click-through prevention, focus and coordinate calibration. A pointer hit must be mapped by a verified region map, not assumed to be a pat.
4. **U3 voice:** explicit mic/speaker opt-in, visible recording state, ASR source confidence, TTS/audio completion receipts, cancellation and device-unavailable fallback. No passive microphone or invented speech.
5. **U4 avatar:** canonical fox/human geometry, mapped ears/tail/regions, animation command IDs and actual renderer acknowledgments. `src/sofia/package_foundations/ui.py` only reports planned versus caller-reported acknowledgments; without authenticated receipts it proves no playback.
6. **U5 Discord:** implement INTERACT D0–D4 with enrolled private DMs, inbound routing to shared sessions and sender identity; no server-wide content monitoring or unsolicited sends. Actual outbound needs separate ACT authorization and receipts.
7. **U6 recovery:** reconnect, duplicate event, missed audio, hidden window, stale overlay, token rotation, stop across clients and privacy deletion.

## Acceptance and protections
Run `python -m pytest -q -x test/test_pkg_ui_foundation.py`, then headless/text, forged-event, focus/click-through, renderer acknowledgement, offline/reconnect, mic permission and DM opt-in tests. Real on-screen animation, audio playback and Discord DM must be **separately observed**; fake transport is insufficient. Preserve redacted logs, credential secrecy and user-controlled recording. No interface, notification or background worker is deployed by this branch. Exact-SHA full tests, privacy/security review and separate deployment/merge approval remain pending.
