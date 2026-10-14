# CA-001 Phase 00 | Canonical conversation source and Matrix decision correlation

**Scope:** one production-wired, non-authoritative subproblem of CA-001.
**Source owner:** existing `conversation_messages`, `cognition_matrix_trace`,
`social_session_principal`. **No new truth table.**

## Production path

`SofiaApplication.latest_companion_decision_trace()` obtains the latest
session-scoped Matrix trace and invokes
`application.decision_persistence.inspect_turn_persistence()` against the
exact canonical `sofia.db`. The inspector creates no state, opens through
`CanonicalSQLiteGuard.connect(read_only=True)`, reads a single SQLite
snapshot, and returns a typed, content-free `CompanionTurnPersistence`.

A fully linked input+decision statement requires:

1. The originating **USER** message ID, session and a well-formed original
   timestamp at or before the durable completed Matrix decision.
2. The same Matrix message ID, session, principal, channel, intent, history
   and strategy in the existing trace row, with `shadow=0`.
3. An independent `social_session_principal` row confirming exactly the
   claimed principal (and audience, if the Matrix privacy plan provides one).

Any missing, replaced, mismatched or incomplete source fails closed. An
anonymous/local turn can be evidenced as persisted, but cannot be called an
authenticated principal/audience-linked turn. Nothing in these rows alone
proves consent, a model's reasoning, historical memory eligibility, action
execution, external delivery or an objective achieved.

## Ephemeral NEURO turn attribution

`ConversationService.neuro_observation_for_turn(message_id=...)` exposes an
already-observed `NeuroStateSnapshot` only when **both** the active NEURO
message key and Matrix message key equal the requested turn. It does not read
the global latest snapshot as a substitute for this proof. The application
projects `neuro_observed_for_turn_at` and sets `neuro_turn_correlated` only
for an exact in-process match. Restart, new message, missing observation or
future-dated mismatches cannot silently inherit the older turn's snapshot.

This confirms turn attribution of an *observation*, not that the model
consumed it, that its chosen focus caused the reply, or that the snapshot
was durably persisted. The NEURO global latest timestamp remains separate.

## Settled assistant reply (authenticated stable events only)

The same read-only SQLite snapshot can additionally inspect the existing
`canonical_conversation_turn` settlement. A reply counts as **persisted** only
when status is `completed`, the original user event ID and separate SOCIAL
principal/audience/channel/session binding match, and the exact assistant
message ID exists with role `assistant` and bytes matching the sealed
`response_json.content`. The response text is compared in memory but never
included in the projection or evidence artifacts.

`CompanionTurnPersistence.canonical_turn_settled` and
`assistant_reply_persisted` are not delivery receipts or tool execution
proof. Local/unpaired turns and older stores without `canonical_conversation_turn`
remain explicitly unverified. No new canonical tables or write paths are added.

## Regression and acceptance

`test/test_v18_decision_persistence.py` checks same-event positive cases,
missing/wrong source sessions, spoofed principals, forged channel and role,
canonical state loss, cross-turn proof reuse and an actual initialized
SofiaApplication conversation. The targeted Windows/Linux GitHub workflow is
`.github/workflows/v18-decision-persistence.yml`. The existing package and
release suites provide additional integration evidence after they finish.

## Missing CA-001 stages

- Independently persist NEURO source/consumer receipts and prove that the
  actual selected focus was consumed for that turn. The in-process association
  is implemented but is not durable causal evidence.
- Join actual eligible memory source IDs and corrections without cross-audience
  disclosure.
- Trace objective-linked LIFE/GOALS decisions, rejected alternatives and
  execution/SAFE/RUN effect receipts through verifiable causal IDs.
- Prove response persistence and actual ACT/render/voice delivery, or
  explicitly record no action.
- Pass real production host, authenticated multi-device and restart acceptance.

**Ledger status: partial_wiring.** Neither CI nor this projection is
independent proof that all CA-001 requested systems participated.
