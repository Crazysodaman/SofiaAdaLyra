# PKG-AVATAR ↔ PKG-INTERACT | time, weather and worn-state integration

**2026-09-22 | AVATAR PR #7 integration handoff only.** INTERACT PR #2 is an independent draft. This document does not authorize merging either branch, editing production data, deploying a weather service or changing the canonical avatar configuration.

## Current verified boundaries

- `src/sofia/avatar/wardrobe_routine.py` accepts a trusted, timezone-aware `WardrobeContext.now`, a host-selected `Season`, an `Activity` and optional `WeatherObservation` with condition, observed-at time and source ID. Weather is effective only if its UTC-normalized age is between zero and six hours. There is no weather fetch or automatic host-clock injection in that module. No weather observation means `effective_weather is None`; stale or future-dated observations also become unknown for outfit selection.
- The planner only proposes an outfit. It does not establish what Sofía is currently wearing, generate clothes, perform a renderer action, fetch local weather, or prove time/environment sensing.
- `src/sofia/avatar/shared_wardrobe_state.py` owns the acknowledged current outfit and revision. Its `WardrobeTextProjection` separates current items from pending or failed items and signals whether the avatar is synced/visible. It supports explicit text fallback without a second wardrobe.
- `src/sofia/cognition/assembler.py` on INTERACT PR #2 currently directs questions about what Sofía is wearing to CANONICAL CLOTHING from `AuthoritativeSelfState`, which is sourced from `Embodiment.clothing.items`. That canonical design description is not the live worn-state authority. Avoid injecting conflicting instructions claiming both are the only current wardrobe truth.
- No verified live INTERACT wardrobe adapter, authenticated renderer receipts, full GitHub checkout tests, supervised integration or weather provider exists in this AVATAR PR.

## Minimal integration handoff for INTERACT

1. **Trusted clock:** a runtime host supplies an offset-aware current timestamp and selected local timezone/locale as observations at each operation. Do not use raw LLM output or a past conversation timestamp as the clock. Display and scheduling logic should account for restart, clock jumps and missing timezone.
2. **Weather only when independently available:** a separately authorized provider or verified local weather sensor supplies an explicit location or station, observation timestamp, units, source and freshness. No general web/search capability is implied. If unavailable/stale, Sofía must say she does not have current weather and the planner must use its weather-unknown path. Never invent conditions or quietly reuse stale readings.
3. **Canonical versus current:** canonical clothing specifies the approved character design/available wardrobe. For `what are you wearing now?`, `I put on a graphic tee`, or other current-state requests, use AVATAR's acknowledged `WardrobeTextProjection` as authoritative. Canonical designs alone do not imply an item is worn; when current state is not available, answer that it is unknown. Treat pending and failed outfits as attempted changes, not present clothes.
4. **Operation sequence:** the conversational layer proposes a specific preset/item selection with expected wardrobe revision; AVATAR validates its slots/layers/coverage; trusted renderer receipt acknowledges the visual result, or a trusted unavailable-renderer fact explicitly commits the same state in text fallback. Only then can chat narrate the new outfit as current.
5. **Safe startup:** begin with the covered preset in text fallback only when a trusted initialization path has actually selected that state. Never claim an unverified mesh is visible. Reconcile persistent revision and source before announcing a restored outfit; unknown state stays unknown.
6. **Taste context:** source-verified Sparks likes for `engineer.signature` and `lounge.relaxed` remain his preferences, not Sofía's. Graphic tee is an optional requested variation, not a blanket favorite. Do not infer color/item likes from outfit-level likes.
7. **Release isolation:** add only a small reviewed adapter after INTERACT's current live-model decision/expression probe and focused Windows tests. Keep PR #2 and PR #7 separate until exact-source integration tests, current full suite, privacy/SAFE review and Sparks's explicit merge/deployment approval.

## Acceptance tests before integration is called live

- A known host time and season reach the planner without a guessed time; time-zone changes and restarts do not silently reuse stale clock evidence.
- Fresh sourced weather can affect a proposed outfit; absent, future and older-than-six-hours weather do not become a current-condition claim.
- Canonical engineer clothing stays a design reference even when acknowledged current clothing is lounge/graphic tee.
- Pending or failed wardrobe transition does not change a current-wearing answer.
- Text fallback keeps one acknowledged outfit; a returning avatar cannot show until the exact current revision is verified.
- Sparks's sourced outfit-level likes are distinguishable from Sofía's own preferences and from requests.
- No model-generated text is accepted as an authenticated clock, weather observation, owner identity or renderer receipt.

**Status:** integration design only; not implemented on INTERACT, not executed against a live clock/weather feed or renderer.