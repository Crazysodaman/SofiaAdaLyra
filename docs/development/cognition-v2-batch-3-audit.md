# Cognition v2 Batch 3 production audit

Branch: `main`

## Production flow

```text
authenticated saved turn
  -> Turn Kernel focus commit
  -> Matrix v2 semantic/concept plan
  -> existing Matrix context/evidence/authority compatibility adapters
  -> NEURO current-turn observation
  -> bounded schedule/budget refinement
  -> authoritative V2 cognitive route
  -> existing provider/capability/permission owners
```

Matrix v2 produces one typed `TurnPlan` containing intent, domains,
subject-scoped evidence needs, response strategy, action requirement, reasoning
requirement, compute/retrieval budget, and a dependency-valid schedule. The
plan is retained on the production conversation service after response
persistence for diagnostics.

## Files

| File | Decision | Production responsibility |
|---|---|---|
| `cognition/v2/contracts.py` | EXPAND | Typed action/reasoning requirements and bounded cognitive budget. |
| `cognition/v2/matrix.py` | ADD | Concept/focus-driven intent, domain, evidence, action, response, and reasoning planning. |
| `cognition/v2/scheduler.py` | ADD | Dependency validation, budgets, optional independent parallel groups, and worker-role preference. |
| `cognition/v2/kernel.py` | EXPAND | Build the plan before delegates and refine scheduling from current NEURO state. |
| `application/conversation_service.py` | MODIFY | Return current NEURO observation to the kernel and retain the authoritative plan. |
| `application/conversation_matrix.py` | MODIFY | Apply V2 reasoning route while preserving exact VERIFY and all existing authority decisions. |
| `test_cognition_v2_matrix_scheduler.py` | ADD | Production, authority, evidence, scheduling, and NEURO regression coverage. |

## Authority and epistemic boundaries

- Mutation language produces `MUTATION` + `VERIFY` and requires existing
  authority evaluation; the plan cannot grant permission.
- Read relevance does not execute a capability.
- Evidence needs are requirements, not acquired facts.
- A schedule is not running work and contains no result or receipt.
- NEURO changes budget advice only. The same turn/focus yields the same
  evidence needs with or without a neural snapshot.
- High load may reduce bounded budgets and optional parallelism, but cannot
  downgrade VERIFY.
- Existing capability gateway, SAFE, ACT, privacy, consent, and execution
  receipt owners are unchanged.

## Transitional boundary

Matrix v1's context, evidence-availability, privacy, tool-exposure, authority,
and response-validation adapters remain active until their typed V2
replacements arrive. They are downstream compatibility owners, not a second
cognitive route: the V2 reasoning requirement now controls model routing, and
an existing exact VERIFY decision can only strengthen that route. Batch 4
replaces the fragmented evidence view with the subject-scoped graph/ledger.

## Observed verification

- V2 contract/Turn Kernel/Matrix/scheduler focused gate: 20 passed.
- V2 plus conversation/Matrix/NEURO regression slice: 223 passed.
- Non-integration CORE package gate: 2,201 passed, 4 skipped, 1,651
  deselected.
- Production application test confirms the retained V2 plan and DEEP route for
  a focused Artemis CPU query.
- Live Ollama execution is not available in this cloud environment and is not
  claimed by this source-level batch.
