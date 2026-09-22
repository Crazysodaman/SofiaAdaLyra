# PKG-AVATAR ↔ PKG-INTERACT | time, weather and worn-state integration

**2026-09-22 | AVATAR draft PR #7.** The observation bridge has now been CODED at `src/sofia/avatar/interact_bridge.py`, but is **not connected to the live CLI or a weather provider**. See [coded bridge milestone](pkg-avatar-interact-bridge-code-milestone.md) for exact implementation, focused evidence and remaining gates. INTERACT draft PR #2 remains an independent branch. No merge, deployment or canonical avatar/identity/Constitution change.

## Existing authority boundaries

- `wardrobe_routine.py` accepts host-supplied, timezone-aware `WardrobeContext.now`, host-selected season/activity and optional source-labeled `WeatherObservation`; weather is considered usable only within 0–6 hours, never based on model-inferred time.
- `shared_wardrobe_state.py` owns acknowledged clothing and the revisioned `WardrobeTextProjection`: current is distinct from pending/failed; text fallback and avatar primary share the same clothing truth.
- INTERACT's current `CognitiveContextAssembler` incorrectly uses canonical design clothing for current-wearing questions. The explicit bridge corrects this instruction **only for requests routed through the bridge**. It checks the exact legacy instruction and fails closed if INTERACT changes it, rather than creating two contradictory authorities.
- `interact_bridge.py` samples a host clock, accepts optional externally supplied weather with location/source/time/Celsius, strips stale or future weather from cognitive observations, and emits source-aware current-wear/style JSON in a provider-neutral `CognitiveRequest`. It neither authenticates evidence nor fetches anything.

## Later host integration sequence

1. Trusted host selects locale/season/activity, captures local system time per operation and optionally obtains a separately authorized, independently verified weather observation; missing/stale/future weather remains unknown. Never infer or expose the user's location without authorization.
2. Independently verify Sparks's original preference-source events, then use `project_style_context` with reviewed source IDs. Engineer and lounge are user-liked outfits; optional graphic tee is user-requested, not a blanket favorite. No Sofía taste should be inferred.
3. Initialize/reconcile a single persistent `SharedWardrobeState` from trusted evidence. A blueprint is not an asset, and a remembered outfit is not proof of current worn state.
4. Route the current INTERACT `CognitiveContext` and tools through `assemble_with_avatar_observations()` instead of the plain assembler. Recheck/serialize wardrobe revision immediately before dispatch; a prompt is informational, not an action authorization.
5. Clothing changes go through AVATAR proposal and trusted visual acknowledgement, or explicit trusted text-fallback acknowledgement. Renderer resynchronization must match the exact current revision. Unverified avatar output remains hidden.
6. After INTERACT's ongoing live-model decision/expression acceptance, run a combined exact checkout, Windows focused and full suite, privacy and source checks, and supervised live conversational tests; review the temporary legacy-sentence compatibility seam for replacement with a typed assembler field.

## Implemented focused checks

`test/test_avatar_interact_bridge.py`: **24/24 passed in an isolated Linux harness** with interface stand-ins for cognition/shared state and existing catalog/style code. Tests cover canonical versus current clothing, lounge transition, failed renderer, avatar resync, host timestamp and timezone, current/stale/future/no weather, six-hour boundary, Celsius validation, sourced preference separation, unchanged tools, and fail-closed assembler/revision conflicts. The committed bridge/test source blobs match their locally tested bytes. **Actual GitHub checkout, Windows/full tests, CLI/LLM integration, real weather provider, authenticated receipts, persistence and renderer acceptance have NOT run.**
