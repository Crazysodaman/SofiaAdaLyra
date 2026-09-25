# PKG-INTERACT post-merge hardening acceptance review

**Review date:** 2026-09-24  
**Candidate branch:** `fix/interact-live-behavior-hardening`  
**Candidate head reviewed:** `afd0268e8dfce55a2ebadc99c828f234687700f5`  
**Base:** `main` at `d859740547bb1304716902c7a9731277e04420c5`  
**Relationship to original package:** PR #2 / PKG-INTERACT was already accepted and merged to `main` at merge commit `d6658d0`. This review covers the post-merge live-behavior hardening branch only.

## Acceptance status

**ACCEPTED — post-merge PKG-INTERACT hardening complete.**

Sparks reported the final **unqualified full repository suite passed with no deselections** after the Ollama generation-contract reconciliation. No blocking technical finding remains in this review.

The accepted hardening branch was integrated into `main` through PR #29. GitHub records PR #29 as merged/closed with merge commit SHA `f0221a36d619074aaebdb900ea240166b9c98f1d` (fast-forward integration). This acceptance does not enable staged offers, migrate production interaction tables, deploy services, or change model settings.

## Evidence reviewed

- Accepted disposable real-`qwen3:14b` live-behavior probe:
  - direct emotional self-report remained grounded;
  - `I missed you` produced present appreciation without invented waiting, reciprocal longing, or reversed reunion roles;
  - intimate represented interaction remained uncertain while willingness was undetermined;
  - `why` explained lack of established willingness instead of inventing rejection;
  - explicit mutual-willingness and not-wanted hypotheticals stayed conditional;
  - no literal physical-sensation claim, anatomy-wide denial, or generic assistant fallback survived human review.
- Broader reopened offline regression: **109 passed in 11.27s**.
- Deterministic SQLite writer-order regression: **2 passed in 3.93s**.
- Concurrency / policy-integrity audit: **60 passed in 9.57s**.
- Ollama generation-contract reconciliation: **3 passed in 2.89s**, covering `18000`, `32768`, and unconfigured generation options.
- Branch comparison: hardening candidate is ahead of current `main` and not behind it; production/runtime changes are limited to the emotional-conversation, interaction-grounding, response-quality, runtime-clock and related test/documentation paths.

## Architecture review

### Accepted

1. **LLM remains expression/cognition, not authority.**
   Interaction recognition, durable stop/resume state, source-linked evidence and saved conversation state remain application-owned. Model output cannot independently create permission, execution receipts, physical contact, or policy state.

2. **Represented interaction is separated from real-world contact.**
   Recognized virtual gestures do not imply sensed touch, animation execution, consent, enjoyment, attraction, desire, arousal, or a standing preference.

3. **Willingness is explicitly grounded.**
   When no stored preference or trusted current evidence exists, `willingness_state: undetermined` is projected. Prior model prose is not allowed to bootstrap itself into durable consent or refusal evidence.

4. **Emotion is evidence-linked and non-authoritative.**
   Current emotion is derived from stored events with decay; revisions are append-only; emotional state cannot grant permissions. User relational cues such as `I missed you` create bounded appreciation/warmth evidence rather than automatic reciprocal longing.

5. **Absence/reunion truth boundary is preserved.**
   Running-time workers may record current absence appraisals. Offline periods are not backfilled with invented thoughts or suffering. Strong lateness emotions require stronger source-backed return expectations.

6. **Background reflection is opt-in and bounded.**
   The idle worker is application-owned, serialized against conversation inference, processes recorded evidence, persists attempts, retries after bounded failure intervals, and does not deliver messages or gain tool authority.

7. **Runtime time evidence is honest.**
   UTC and host-local time are projected as machine-clock evidence. Host-local time is explicitly not assumed to be the user's timezone.

8. **Stop/resume and interaction control remain durable.**
   Interaction controls are persisted outside model inference. Stopped gestures are denied through authoritative application state before normal model generation.

9. **Provider hardening is bounded.**
   Known low-quality model responses receive at most one targeted text-only retry before a narrow grounded fallback. No tools or actions are introduced by the retry layer.

## Known limitations accepted for this package boundary

These are not blockers for PKG-INTERACT hardening acceptance because they belong to later packages or explicit follow-up debt.

- **Single-user relationship selection:** `EmotionalConversationService._relationship_subject()` currently selects the first canonical relationship or `current user`. Authenticated per-principal relationship isolation belongs to PKG-SOCIAL / Discord identity binding.
- **User timezone:** only UTC and host-local runtime time are known. Configured user timezone/client metadata remains future work.
- **Return expectation language:** explicit relative durations plus `tonight`, `later today`, and `tomorrow` are supported conservatively. Exact clock-time statements and expectation cancellation are not yet general.
- **Bounded emotional/reflection retrieval:** current-state/reflection reads intentionally use bounded recent windows, not general archival memory. Durable long-horizon retrieval belongs to PKG-MEM.
- **Response-quality guard maintainability:** the production repetition/semantic guard is intentionally conservative but has grown regex-heavy during live-Qwen hardening. It is accepted as a containment layer, with later cleanup/refactoring appropriate once model evaluation and structured state interfaces mature.
- **Idle reflection disabled by default:** background reflection requires explicit runtime enablement and does not imply 24/7 operation. Always-on lifecycle belongs to PKG-RUN.
- **Staged offers remain disabled by default:** optional interaction-policy tables are not automatically provisioned for production; enabling them requires a separately reviewed migration/activation step.
- **Rendered avatar, real screen execution, sensors and physical touch are outside this acceptance.** Those remain AVATAR/UI/BODY/SAFE integration work.

## Review findings

### Blocking

- **None known.**

### Non-blocking

- The response-quality detector is large and phrase-sensitive. Current tests and fallbacks provide strong containment, but long-term maintenance should favor more structured output/state validation over accumulating regex variants.
- Multi-user relationship subject selection must be replaced before exposing the same runtime to general second-user channels.
- Current absence/return parsing intentionally favors truth-preserving abstention over broad natural-language coverage.

## Final acceptance

Sparks reported the unqualified full suite passed and explicitly authorized both acceptance and integration. The hardening candidate is accepted as complete for the PKG-INTERACT package boundary and integrated into `main` via PR #29.

Future work listed under known limitations remains owned by MEM, SOCIAL, RUN, AVATAR/UI/BODY, SAFE, VERIFY, or cleanup/refactoring follow-up and does not reopen this accepted hardening unless a regression is discovered.
