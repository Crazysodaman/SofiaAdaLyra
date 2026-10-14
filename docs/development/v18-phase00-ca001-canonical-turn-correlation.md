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

## Regression and acceptance

`test/test_v18_decision_persistence.py` checks same-event positive cases,
missing/wrong source sessions, spoofed principals, forged channel and role,
canonical state loss, cross-turn proof reuse and an actual initialized
SofiaApplication conversation. The targeted Windows/Linux GitHub workflow is
`.github/workflows/v18-decision-persistence.yml`. The existing package and
release suites provide additional integration evidence after they finish.

## Missing CA-001 stages

- Correlate the NEURO attention winner to **that exact turn**, not the latest
  unrelated NEURO snapshot.
- Join actual eligible memory source IDs and corrections without cross-audience
  disclosure.
- Trace objective-linked LIFE/GOALS decisions, rejected alternatives and
  execution/SAFE/RUN effect receipts through verifiable causal IDs.
- Prove response persistence and actual ACT/render/voice delivery, or
  explicitly record no action.
- Pass real production host, authenticated multi-device and restart acceptance.

**Ledger status: partial_wiring.** Neither CI nor this projection is
independent proof that all CA-001 requested systems participated.
