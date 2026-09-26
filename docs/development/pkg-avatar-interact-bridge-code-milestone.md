# PKG-AVATAR ↔ PKG-INTERACT | coded observation bridge milestone

**2026-09-22 | AVATAR draft PR #7 only | candidate code, NOT live integration.** INTERACT draft PR #2 remains untouched. No merge, deployment, production database, identity, Constitution, model, network or physical hardware changes.

## Implemented

`src/sofia/avatar/interact_bridge.py` provides an explicit, side-effect-free bridge from AVATAR's shared wardrobe authority to an actual provider-neutral INTERACT `CognitiveRequest`:

- `HostEnvironmentEvidence.capture()` samples the host clock once per operation, with an offset-aware timestamp, explicit host-selected season and activity. The host must configure its timezone and call capture for each request, never reuse a conversation timestamp or generate time through the LLM.
- Optional `HostWeatherEvidence` carries a typed condition, timezone-aware observed timestamp, source ID, location and optional Celsius temperature. It converts to the existing `WardrobeContext`; only observations aged **0 through 6 hours** appear as current in the cognitive projection. Missing, stale or future weather emits `weather_status=unknown` and `weather=null`, without leaking an old condition into the current-weather context. IDs are labels and **not** cryptographic authentication.
- `InteractionObservation.for_chat()` serializes the acknowledged current outfit revision, actual *metadata* items/slots/layers/coverage, text-fallback versus avatar-primary mode, pending/failed changes separately, and an optional source-reviewed Sparks style context. It does not assert any real garment mesh, physical touch or environmental sensing.
- `assemble_with_avatar_observations()` invokes the existing `CognitiveContextAssembler`, replaces exactly one obsolete canonical-clothing-as-current instruction with separate **canonical design versus acknowledged current wear** guidance, and appends structured observation JSON to the existing leading system message without changing user messages or tool definitions. If INTERACT changes that old rule or the wardrobe revision changes while assembling, it fails closed instead of sending contradictory or stale state.
- Nothing automatically invokes this function from `python -m sofia`. It does not authorize or fetch weather, execute garment changes, authenticate host-supplied facts, or dispatch a cognitive provider request.

## Intended composition-root hookup, AFTER review

The trusted host should hold exactly one `SharedWardrobeState`, constructed from its independently reconciled/persisted wardrobe state. It must not simply assume an old saved outfit or asset is visible. Per cognitive operation:

1. Determine an authenticated user/session, trusted activity and locale/season. Configure the host operating-system timezone. Capture a fresh `HostEnvironmentEvidence`, optionally adding separately authorized, source-validated local weather. Do not infer the user's location.
2. Obtain reviewed style preferences through `project_style_context(..., reviewed_source_ids=...)` **only after the host has independently verified the underlying conversation events**. Sparks' explicit likes for engineer and lounge are not Sofía's likes; the optional graphic tee remains a request.
3. Call `assemble_with_avatar_observations(context, wardrobe=wardrobe, environment=environment, style=style, tools=tools)` *instead of* the plain assembler for the same operation. Do not concatenate another conflicting system prompt. Before dispatch, verify the wardrobe revision has not changed; serialize/lock request construction if concurrent changes are possible.
4. A request to change clothing must first go through `SharedWardrobeState.propose()`, then a trusted visual success receipt **or** a separately established renderer-unavailable fact and `acknowledge_text_fallback()`. The LLM's words are never renderer evidence or wardrobe write authority.
5. Only a verified renderer adapter can resynchronize a returning avatar to the exact current wardrobe revision. Keep unknown or stale avatar state hidden; normal fallback remains clothed by the covered-default metadata gate, with separate actual asset/opacity verification still required.

The bridge is an importable integration seam, **not** a production CLI wiring instruction to be applied without a reviewed integration branch and complete tests.

## Test evidence and limitations

`test/test_avatar_interact_bridge.py` has **24 focused checks** covering current versus canonical clothing, text fallback, pending/failed transitions, avatar resync, fresh/stale/future weather and the six-hour boundary, missing weather, timezone-aware clocks, invalid data, sourced likes, unchanged tool definitions, changed assembler contract, and a concurrent wardrobe update. The 24 tests passed on Linux in an isolated harness using interface doubles for cognition/shared state and the real starter catalog and style-context code from the earlier local bundle. The two GitHub source/test blobs are byte-identical to those locally tested files.

**NOT RUN:** exact current GitHub branch checkout, Windows full suite, real CLI/LLM, weather provider/network/sensor, authenticated source verification, real renderer, persistence/restart, or supervised acceptance. Unit checks of metadata do not prove real clothing coverage. The legacy-sentence replacement is an intentionally temporary, fail-closed compatibility seam; replace it with a typed assembler input when INTERACT is stable and review conflicts explicitly.

## Required future acceptance

- Run the exact AVATAR + stable INTERACT combined checkout, focused tests and full suite on Sparks' Windows environment.
- Connect the bridge through a reviewed composition-root change after the INTERACT decision/expression live-model gate, without editing the in-progress INTERACT branch opportunistically.
- Verify a normal CLI conversation answers **current** engineer/lounging attire from acknowledged state rather than canonical design; pending, renderer failure, restart, and unavailable state do not become fabricated facts.
- Verify real host time on configured local timezone and missing/future/stale weather; separately review/authorize a weather provider and its location/privacy policy before claiming live weather knowledge.
- Require explicit Sparks approval before merging either draft PR or deploying anything.
