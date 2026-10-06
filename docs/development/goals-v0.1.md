# Goals v0.1

**Status:** repository-tested deterministic baseline; live initiative evaluation pending
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

Candidate creation, deterministic policy admission, durable CANDIDATE
persistence, and ACTIVE transition are separate calls. This prevents NEURO from
directly manufacturing active durable goals. Autonomous goals require an
expiration. Conservative limits are 32 active goals, 64 candidates, hierarchy
depth 4, and 16 children per parent. Exact normalized-title duplicates return
`MERGE` instead of multiplying.

## Priority and NEURO

Effective priority is computed from bounded base priority, authenticated-user
weight, urgency, age, deadline proximity, new evidence, conversational
relevance, resource pressure, lifecycle state, and an optional capped neural
relevance input. Diagnostics retain every contribution.

Only active goals feed NEURO. The adapter caps goal signal value at 0.9 and uses
an effective priority computed with neural relevance set to zero. Consequently:

```text
canonical active goal → bounded goal signal → NEURO attention
```

There is no automatic `NEURO → priority → NEURO` reinforcement loop. NEURO may
trigger a new in-memory candidate only when separate host evidence exists.

## Matrix, ACT, and RUN

For the authenticated current audience, Matrix receives at most five ranked
live goals as JSON data under an explicit SYSTEM disclaimer. Titles and reasons
are data rather than instructions or evidence. Other principals and audiences
cannot enumerate the partition. Goal projection failure is non-fatal.

`GoalActionProposal` wraps the existing `CapabilityProposal`; it does not call
the capability gateway. Read-only inspection therefore retains ordinary Level
1 behavior, while mutations retain their existing standing/exact approval
requirements. There is no goal override.

RUN compatibility states describe pending inspection, scheduled re-check,
waiting for evidence/deadline, or blocked approval. Setting one persists intent
only: it creates no background claim, job, result, or receipt. A real scheduled
deadline-maintenance task expires due unscoped host goals under the existing
background budget.

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

The programmatic diagnostic projection reports active/candidate/blocked/recent
terminal state, origin, reason, effective priority and its contribution trace,
completion condition, blocker, and RUN state. No large goal-management tray page
is added in this slice.

This baseline does not implement Gaia motor goals, semantic duplicate matching,
LLM-authored canonical state, arbitrary cross-principal administration, or an
automatic capability executor. Live autonomous initiative quality and resource
thresholds still require production observation.

## Verification evidence

On 2026-10-06, the goal-domain test file passed **17/17**, the final focused
goal/NEURO/application gate passed **93 passed / 1 skipped**, and the exact final
non-integration repository gate passed **3,720 passed / 5 skipped / 6
deselected**. Live initiative quality, external services, and production host
overhead remain separate acceptance work.
