# Goals v0.1

**Status:** production-wired closed-loop baseline; live host acceptance pending
**Date:** 2026-10-06

## Purpose

Goals give Sofía durable direction without turning desire, attention, or model
text into authority. The governing chain is:

```text
observed evidence → NEURO attention → candidate generator → deterministic policy
→ durable candidate → explicit activation → ACT proposal → existing capability
authority → RUN/capability execution → verified receipt → goal progress
```

The old `interaction.goal_journal` remains a narrow compatibility store for
conversation-evidence-backed outreach. Canonical general goals live in the State
Plane namespace `goals-v1`; the two stores do not silently reinterpret each
other.

## Invariants

- Attention is not evidence.
- A goal is not permission, consent, execution, or a receipt.
- LLM prose is not canonical goal state.
- Priority is deterministic host state, not a hidden model score.
- Completion requires host-verifiable evidence for completed outcomes.
- USER goals cannot be abandoned, cancelled, paused, rejected, or superseded by
  SELF policy.
- A goal may propose a capability invocation, but only the existing capability
  gateway and permission engine may authorize and execute it.
- A goal cannot propose changing the permission system to satisfy itself.

## Model and lifecycle

Every immutable goal records a stable ID, typed origin, authenticated owner,
principal/audience scope, title/reason, status, bounded priority/confidence,
evidence references, timestamps, typed completion condition, optional deadline,
parent, blocker, supersession, RUN compatibility state, revision, and immutable
lifecycle event history.

Origins are `USER`, `SELF`, `SYSTEM`, and `MAINTENANCE`. Lifecycle states are
`CANDIDATE`, `ACTIVE`, `PAUSED`, `BLOCKED`, `COMPLETED`, `REJECTED`, `CANCELLED`,
`EXPIRED`, and `SUPERSEDED`. Terminal states never transition back to active;
reopening requires a new goal.

Reconstruction validates the complete immutable lifecycle chain, not merely the
latest status: the initial state, every transition, monotonic event time, unique
event IDs, and the final status must all agree. Legacy unscoped SELF records are
quarantined through a valid terminal transition rather than being exposed.

Completion conditions are typed as root-cause identified, evidence becomes
true, operation receipt, no recurrence for an observed duration, all children
complete, or an explicit user-defined condition. `COMPLETED` always carries
verified completion references. Cancellation and expiration remain distinct
historical outcomes.

## User and autonomous goals

Authenticated user creation starts an active audience-scoped USER goal and
requires a durable source reference such as its saved conversation message.
Sofía's candidate API accepts only a typed high-salience activation plus
independently verified host evidence. Low-salience noise returns no candidate.
The activation itself is never evidence.

The application-owned coordinator accepts reviewed OPS/Fleet/RUN/network fault
classes only. It requires independently typed evidence plus NEURO activation,
then records `ACCEPT`, `REJECT`, `DEFER`, `ASK_USER`, or `MERGE`. Accepted
candidates persist as CANDIDATE before becoming ACTIVE; high-risk candidates
remain reviewable and use existing ACT outreach. Deferred candidates have a
bounded reconsideration interval. SELF goals always retain an authenticated
principal/audience scope; host-wide directions use SYSTEM/MAINTENANCE instead.
Conservative limits are 32 active goals, 64 candidates, hierarchy depth 4, and
16 children per parent. Exact normalized-title duplicates merge evidence.

## Priority and NEURO

Effective priority is computed from bounded base priority, authenticated-user
weight, urgency, age, deadline proximity, new evidence, conversational
relevance, resource pressure, lifecycle state, and an optional capped neural
relevance input. Diagnostics retain every contribution.

Only active goals feed NEURO. The adapter caps goal signal value at 0.9. Real
deadline urgency, newly relevant typed evidence, resource pressure,
conversation resource tags, and capped non-goal NEURO relevance contribute to
the diagnostic priority trace. Canonical base priority is unchanged.

```text
canonical active goal → bounded goal signal → NEURO attention
```

Goal activations are explicitly excluded from the neural-relevance input, so
there is no `goal priority → NEURO → priority` amplification loop. NEURO may
trigger a candidate only when separate reviewed host evidence exists.

## Matrix, ACT, and RUN

For the authenticated current audience, Matrix receives at most five ranked
live goals as JSON data under an explicit SYSTEM disclaimer. Titles and reasons
are data rather than instructions or evidence. Other principals and audiences
cannot enumerate the partition. Goal projection failure is non-fatal.

Conversation creation/list/pause/resume/cancel and SELF review resolve before
model invocation through Matrix's deterministic goal intent. The exact saved
authenticated message is typed source evidence; public/unauthenticated callers
cannot create Sparks-owned goals. The LLM never writes canonical goal state.

`GoalActionProposal` wraps the existing `CapabilityProposal`. The production
planner currently uses reviewed deterministic diagnostic mappings, validates
the registered capability and permission class, and invokes the existing
gateway inside a real background RUN claim. Level-1 inspection remains
automatic. A validated Level-3 mutation enters BLOCKED_APPROVAL until an exact
canonical standing grant exists; goals never provide approval IDs or override
authority.

RUN states are operational: pending diagnostics run under the bounded
application scheduler, rechecks use a durable schedule, waiting evidence wakes
only on relevant evidence or bounded polling, and blocked approval does not
retry execution. Successful calls create typed, goal/action-linked receipts;
unknown/failed execution is not completion. Restart expires every indexed
private/global partition, recovers rechecks, and never converts restart into a
success claim.

## Persistence and privacy

State Plane compare-and-swap revisions provide crash-safe updates and reject
concurrent stale writers. The current record embeds immutable lifecycle history;
records are never physically deleted. Restart reconstructs one current goal
with the same history and revision.

Private goals use both authenticated principal ID and audience key. Normal
enumeration can see only that exact partition plus intentionally unscoped
SYSTEM/MAINTENANCE goals. This follows State Plane's fail-closed scoped listing
semantics.

## Diagnostics and current limits

The Goals tray panel reports active/candidate/blocked/paused/waiting/recent
terminal goals, safe owner/scope, priority trace, reason, timestamps,
completion, blocker, RUN state, hierarchy, and evidence count. Authenticated
local Sparks controls USER lifecycle and SELF candidate review through
GoalService rather than direct database mutation.

This baseline deliberately does not implement Gaia motor goals, semantic-only
duplicate/evidence matching, LLM-authored canonical state, arbitrary
cross-principal administration, or permission-management actions. The
connectome package is experimental and non-authoritative. Live initiative
quality, service canaries, resource thresholds, and long-horizon behavior still
require production observation.

## Verification evidence

Verification counts in this document are updated only from the final observed
gate for the revision being shipped; see the release verification evidence and
commit report. Live initiative quality, external services, and production host
overhead remain separate acceptance work.
