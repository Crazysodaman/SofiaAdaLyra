# Cognition v2 architecture specification

Status: Batch 2 Turn Kernel and ConversationFocus are production-active.

Batch 2 composes one application-owned `ProductionTurnKernel` into ordinary
conversation and owner-direct tool turns. It now owns turn sequencing and
durable audience-scoped discourse focus. Existing Matrix v1 and NEURO are
temporary delegates behind that boundary; Matrix replacement begins in Batch
3. The V2 code does not create a second conversation engine or authority path.

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

The scheduler may overlap only tasks without a dependency edge. Primary and
secondary model workers receive immutable inputs. They may return hypotheses,
analysis, or critiques. The Turn Kernel serializes canonical focus, evidence,
and conversation commits after results are validated. Tools are never replayed
merely because another model is available.

## Performance contract

Every stage will expose content-free measurements where available: wall time,
CPU time, prompt/generated tokens, model duration/residency, database reads and
writes, cache hits, and observed resource pressure. Missing sensors stay
unknown. Batch 1's CI-host baseline is in `cognition-v2-baseline.json`; it is a
control-path baseline, not live Ollama evidence.
