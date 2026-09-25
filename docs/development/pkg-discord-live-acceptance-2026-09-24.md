# PKG-DISCORD v1 live acceptance | 2026-09-24

**Scope:** supervised, Sparks-only private Discord DM transport to the canonical Sofía runtime.

## Accepted evidence

- Exact bot credentials authenticated successfully without storing the token in Git, SQLite, or documentation.
- Discord Gateway connected and the adapter verified the configured bot identity and exact resolved private DM before first durable enrollment.
- An earlier incorrect DM-channel binding was explicitly revoked and remained separate from the corrected channel.
- The live process received an authenticated owner DM, routed it through the shared Sofía application/conversation pipeline, generated one response, staged it durably, and delivered one visible Discord reply.
- The first live message exposed SQLite thread affinity in the shared conversation path. That inbound item was conservatively classified `outcome_unknown` and was not automatically replayed.
- Conversation and persistent-memory stores were hardened for serialized cross-thread use. Focused repair gate: **28 passed**.
- Final Discord-focused gate after the repair: **88 passed, 1670 deselected**.
- A new live DM after the repair completed end to end without the prior SQLite exception.

## Accepted v1 boundaries

The transport authenticates exactly one enrolled owner account and one exact DM destination. It denies guild/group/wrong-user/unverified traffic, uses durable ingress/outbox/delivery evidence, prevents duplicate logical generation, preserves outcome-unknown quarantine, rechecks binding authority before send, and retains host-side pause/resume/revoke/re-enrollment controls.

## Findings moved out of Discord scope

The live channel exposed two existing cross-package gaps:

1. **INTERACT/CORE quality:** ordinary greetings can still fall back to generic assistant phrasing. This is a conversational-quality regression, not a transport failure.
2. **SOCIAL principal projection:** transport authentication proves the sender is the enrolled owner, but that principal is not yet projected into shared cognition as `Sparks`. Identity-aware questions therefore fall back to generic model boilerplate even while Sofía's own canonical embodiment is correctly available.

Those gaps must be repaired in their owning layers. Discord must not hard-code user identity or personality text to conceal them.

## Evidence limitation

A new repository-wide full-suite run after the final SQLite thread-safety repair was not captured as part of this acceptance. The package closure is based on focused regression plus supervised live end-to-end evidence; integrated VERIFY remains responsible for the next whole-repository run.
