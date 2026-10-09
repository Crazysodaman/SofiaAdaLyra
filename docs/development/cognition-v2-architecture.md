# Cognition v2 architecture specification

Status: Batches 1–7 are production-composed, including resource-aware dual-model
residency and concurrent role workers.

## Batch 7 model lifecycle

One `ModelLifecycleManager` now owns installation, explicit load/unload,
request activity, idle reclamation, and reconciliation for both configured
roles. The operator can select `on_demand`, `fast_always_resident`,
`dual_resident`, or the default `resource_aware` mode in persistent settings.
Ollama chat and explicit load use the same configured keep-alive.

Resource-aware mode uses only observed host facts. It keeps both roles resident
when installed model byte sizes and available RAM demonstrate capacity. Gaming,
throttling, high CPU pressure, or insufficient RAM keeps the fast role resident
and the primary role on demand. Missing sensors remain explicitly unknown and
produce a conservative decision reason; GPU/VRAM capability is never invented.
Busy-request accounting is authoritative, so reconciliation cannot unload a
model during active inference. Every load and unload is checked against a fresh
Ollama residency inventory before it is reported as successful.

The application composes one `ProductionTurnKernel` for ordinary conversation
and owner-direct tool turns. It owns turn sequencing, durable audience-scoped
discourse focus, and a validated Matrix v2 plan. The cognitive scheduler turns
that plan into dependency-ordered work and bounded budgets. Existing Matrix v1
context/evidence/authority adapters remain temporarily downstream while their
owners migrate in Batches 4–5 and 12; Matrix v2 is authoritative for the
cognitive route. V2 does not create a second conversation engine or authority
path.

## Invariants

- Sofía is one identity. Models are workers, never identities or authorities.
- `sofia.db` remains the canonical database.
- A turn, focus, claim, and evidence item always retain session/audience scope.
- Attention is not evidence. A claim is not evidence. A goal is not permission.
- LLM output cannot establish evidence, authority, consent, execution, or a
  receipt.
- Every operational evidence item has a subject. Evidence about Venus cannot
  satisfy a need whose subject is Artemis.
- Epistemic state (`observed`, `known`, `inferred`, and so on) remains separate
  from acquisition state (`current`, `stale`, `failed`, and so on).
- Same-session state commits are ordered even when independent model work runs
  concurrently.
- Personality renders an already validated answer; it cannot add factual
  claims.

## Target flow and ownership

| Stage | Owner | Input | Output | Forbidden ownership |
|---|---|---|---|---|
| Authentication/channel | SOCIAL/UI/Discord/Voice | Transport event | Principal/audience-bound turn | Cognitive truth or permission |
| Turn Kernel | CORE cognition | `TurnKernelInput` | Authoritative `TurnPlan` | Capability execution |
| ConversationFocus | Turn Kernel persistence | Prior scoped focus + turn | Revised structured focus | Cross-audience references |
| Matrix v2 | Cognition planning | Turn + focus | Domains, intent, evidence/action needs | Evidence fabrication |
| NEURO | NEURO | Trusted signals + plan | Advisory attention/budget | Truth, permission, consent |
| Cognitive scheduler | CORE cognition | Plan + resources | `CognitiveSchedule` | Durable truth mutation |
| Evidence planner | CORE cognition | Subject-scoped needs | Acquisition requests | Permission bypass |
| Evidence acquisition | Existing capability owners | Authorized requests | Provenance-linked evidence | LLM-created receipts |
| Evidence graph/ledger | CORE/state | Evidence atoms | Subject-scoped current graph | Assistant prose as evidence |
| Truth maintenance | CORE/state | Graph + corrections | Current/contradicted/revoked claims | Deleting audit history |
| Claim planner | CORE cognition | Valid evidence + unknowns | `AnswerPlan` | Rendering personality |
| Model workers | Provider/Fleet | Bounded tasks | Suggestions, analysis, critique | Canonical state commits |
| Claim validation | CORE/VERIFY | Answer plan + graph | Accepted/rejected claims | Adding unsupported claims |
| Personality renderer | PERSONALITY | Validated answer + expression context | Natural response | New facts/actions |
| Delivery | UI/Discord/Voice | Settled response | Channel receipt | Reinterpretation of truth |

## Typed hand-offs

The initial contracts are in `src/sofia/cognition/v2/contracts.py`:

- `TurnKernelInput`: authenticated, channel-scoped input.
- `ConversationFocus` and `FocusReference`: structured discourse state; a
  reference is explicitly not existence evidence.
- `FocusTopic`, `UnresolvedRequest`, and `PendingAction`: bounded durable
  discourse continuity. Only typed evidence settles information requests and
  only execution receipts settle pending actions.
- `EvidenceNeed`: subject/predicate/scope/freshness/trust requirement.
- `EvidenceAtom`: subject-scoped value and provenance with separate epistemic
  and acquisition states.
- `CognitiveTask` and `CognitiveSchedule`: dependency-aware work. Parallel
  groups describe independent work only.
- `TurnPlan`: the validated plan shared by Matrix, NEURO, scheduler, and
  evidence planning.
- `ClaimPlan` and `AnswerPlan`: factual content before personality rendering.

These contracts intentionally contain no permission grant, tool result,
execution method, or mutable canonical state.

## Active Batch 2 ownership

`ProductionTurnKernel.coordinate()` commits focus before invoking planning and
attention delegates, always in that order. `SQLiteConversationFocusStore`
persists the structured focus in canonical `sofia.db` under a session/audience
partition and uses compare-and-swap revisions. Fleet inventory contributes
identity candidates only; those candidates are not reachability or state
evidence. The provider receives a bounded focus projection that explicitly
states the same limitation.

The reference resolver uses structured aliases, bounded fuzzy matching,
pronoun/ellipsis continuity, explicit local-host deixis, and correction
handling. It retains multiple topic records while changing one primary focus.
It does not grow a phrase-specific routing table. ConversationService remains
the session/channel/persistence boundary, though further thinning depends on
the Matrix v2 and evidence-graph migrations.

## Active Batch 3 planning

`MatrixV2Planner` maps normalized concepts plus structured conversation focus
into intent, relevant domains, subject-scoped evidence needs, action class,
response strategy, and reasoning requirement. It uses exact deterministic
checks for mutation and verification boundaries, but does not extend the old
phrase-shaped regular-expression classifier. A focused Fleet subject carries
through elliptical operational turns even when the new message has no host
name.

`ValidatedCognitiveScheduler` emits an acyclic `CognitiveSchedule`. Independent
evidence-acquisition tasks may be marked parallel; reasoning depends on their
completion, claim validation depends on reasoning, and rendering depends on
validation. This is a work description only: it does not execute a capability,
write canonical evidence, or grant authority.

NEURO may promote bounded reasoning depth, reduce budgets under observed load,
control optional parallelism, and contribute retrieval/background priority.
It cannot add an evidence need, remove VERIFY, create truth, or change an
action's authority requirement. Existing exact VERIFY routing is retained if a
compatibility safety planner requests it.

## Active Batch 4 evidence ownership

`CognitiveEvidenceLedger` is the append-only canonical record for typed V2
evidence in `sofia.db`. Every atom carries an exact subject, predicate, JSON
value, reviewed source, observation/expiry time, scope, trust, epistemic state,
acquisition state, and evidence ID. Dependency edges are scope-checked and
acyclic by construction because only already-recorded evidence can be a
dependency.

`EvidenceGraph` resolves an `EvidenceNeed` by exact subject/predicate/scope. It
applies maximum age, explicit expiry, trust, future-timestamp, contradiction,
revocation, failure, and unavailable-state rules. Evidence about Venus is
therefore invisible to an Artemis need even when its predicate is identical.
Hypotheses and unknowns do not satisfy operational fact needs.

Corrections are durable transactions. The directly corrected evidence becomes
`CONTRADICTED`; every dependent inference/hypothesis becomes `REVOKED`; history
is preserved. `EvidenceAcquisitionCoordinator` accepts only a host-normalized
payload paired with an existing `CapabilityResult`, verifies the exact
subject/predicate/scope and capability source, and records success, failure, or
unavailability without treating authority denial as a fact.

Observed/known evidence cannot cite conversation/assistant prose as its source,
and `execution.*` predicates require an `execution-receipt:*` source. Batch 5
connects Fleet/Machine capability results and the claim/answer pipeline to this
ledger; legacy string-prefix evidence remains a compatibility input until that
domain migration is complete.

## Dependency direction

```text
channels
  -> application/session boundary
    -> Turn Kernel
      -> focus + Matrix v2 + NEURO advice
        -> scheduler
          -> evidence planner
            -> existing capability/authority owners
          -> model workers
        -> evidence graph/truth maintenance
          -> claim planner/validator
            -> personality renderer
              -> channel delivery
```

Capability, SAFE, ACT, INTERACT consent, memory privacy, and Fleet trust remain
outside the cognitive worker layer. V2 consumes their decisions and evidence;
it does not absorb their authority.

## Concurrency contract

DEEP and VERIFY turns with no exposed tools run independent Primary and
Secondary inference intervals concurrently. Primary receives the canonical
request; Secondary receives only the latest user task plus at most three
bounded host-owned `TRUSTED`/`CURRENT` context projections, with no tools or
capability allowlist. Their immutable results are joined in stable role order
and Primary performs the final synthesis. Secondary output remains review
material, never evidence, authority, a receipt, or a state mutation.
The validated V2 budget can still disable worker overlap under observed
resource pressure without downgrading the requested reasoning depth.

Tool-bearing turns remain single-worker so model concurrency cannot duplicate a
capability request. Role-local locks prevent two turns from racing the same
configured worker while still permitting Primary and Secondary to overlap.
Conversation surfaces use separate turn locks, so one Discord session does not
globally serialize an unrelated Desktop session. A shared activity drain gate
rejects new work during shutdown and waits for already-started turns to commit.
Fallback between configured roles is off by default and requires the separate
`SOFIA_COGNITION_FALLBACK_ENABLED` operator policy.

## Performance contract

Every stage will expose content-free measurements where available: wall time,
CPU time, prompt/generated tokens, model duration/residency, database reads and
writes, cache hits, and observed resource pressure. Missing sensors stay
unknown. Batch 1's CI-host baseline is in `cognition-v2-baseline.json`; it is a
control-path baseline, not live Ollama evidence.
