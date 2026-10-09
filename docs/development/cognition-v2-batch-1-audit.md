# Cognition v2 Batch 1 audit and migration map

Audit revision: `17511643a981cdbf9d8fcd7e59f4888aaaa39e50`

Branch: `main`

Canonical database: `sofia.db`

## Observed production path

1. Desktop, terminal, and Discord bridges call the application-owned
   conversation service.
2. `ConversationService.respond()` authenticates/binds the principal, persists
   the user message, invokes post-persistence continuity hooks, and calls the
   Matrix mixin.
3. `ConversationMatrixMixin._record_shadow_matrix()` classifies the turn and
   separately plans context, evidence, authority, privacy, tool exposure,
   response contract, and routing.
4. `ConversationService._observe_neuro_turn()` records advisory attention.
5. Several deterministic application handlers may finish a turn before model
   invocation. Otherwise `EmotionalConversationService._build_request()` adds
   grounded emotion/environment/personality projections.
6. `SofiaRuntime.respond()` invokes deterministic runtime resolvers and then
   `CognitiveSystem` for context assembly, tool rounds, and provider execution.
7. `RoutingCognitiveEngine` chooses primary/secondary/VERIFY work. VERIFY is
   sequential primary draft → secondary critique → primary synthesis.
8. Provider, interaction, quality, grounding, and Matrix validators repair or
   reject the draft before the assistant message is persisted.

This is live production reachability, not merely import/test reachability.

## Current component ownership

| Concern | Current production owner | Finding |
|---|---|---|
| Session/channel persistence | `application.conversation_service`, `conversation.store` | Canonical and retained |
| Turn classification | `cognition.matrix.classifier/coordinator` | Regex-heavy and distributed |
| Context selection | Matrix context planner plus conversation/runtime assemblers | Multiple owners |
| Evidence requirements | Matrix evidence planner | Typed but key-based, not subject graph |
| Evidence availability | `runtime.evidence`, tool evidence refs, scoped application stores | Fragmented acquisition/validation |
| Authority/privacy | Matrix projections over SAFE/SOCIAL owners | SAFE/SOCIAL remain authoritative |
| Attention | `neuro.runtime` and adapters | Retained as advisory input |
| Model routing | Matrix routing plan plus `cognition.routing` policy | Duplicate route decision surfaces |
| Tool loop | `cognition.system` plus capability gateway | Host boundary retained |
| Model lifecycle | Runtime lifecycle manager | Retained, expanded in Batch 7 |
| Tray model status | Tray creates another lifecycle manager for observation | Duplicate runtime reconstruction |
| KNOW | Knowledge service/store/retrieval | Retained storage, retrieval replaced in Batch 9 |
| Memory | Memory system and provenance stores | Retained authority/privacy |
| Fleet/Machine | OPS/MACHINE/DISTRIBUTED capabilities | Retained capability ownership |
| Final grounding | provider guards, repetition/quality repair, Matrix validator | Overlapping post-generation checks |
| Personality | personality modulation + emotional conversation projection | Retained, moved after claims in Batch 11 |

## Duplication and obsolete-path candidates

- Matrix route planning and `CognitiveRoutingPolicy` both decide model depth.
- Matrix evidence requirements, runtime evidence projection, tool evidence
  references, and domain-specific validators form disconnected evidence views.
- Provider repetition guards, quality repair, grounding checks, and Matrix
  response validation overlap without one claim plan.
- `ConversationService` owns persistence, topic planning, deterministic command
  dispatch, request assembly, model invocation, validation, and persistence; it
  is not currently a thin boundary.
- One application-wide `_model_lock` serializes foreground and background model
  activity even when cognitive work would be independent.
- The tray reconstructs lifecycle status with a newly created
  `ModelLifecycleManager` rather than reading only the runtime owner.
- SQLite remains one canonical file, but many stores open independent
  connections and expose no shared operation accounting.

These are removal candidates, not immediate deletion authorization. Their
required behavior must first move to the V2 owner named below.

## V1-to-V2 replacement map

| Current file/component | Action | Target owner | Batch | Deletion condition |
|---|---|---|---:|---|
| `application/conversation_service.py` orchestration | SPLIT | Turn Kernel | 2 | Service retains only session/channel/persistence duties |
| Matrix classifier/coordinator | REPLACE | Matrix v2 | 3 | Semantic plan and deterministic safety cases pass |
| Matrix context plan | MERGE | Turn Plan/context budget | 3/10 | Relevant-only assembly is production active |
| Matrix evidence + `runtime/evidence.py` | REPLACE | Evidence Planner/Graph | 4 | All live domains emit subject-scoped evidence |
| Matrix response validator | REPLACE | Claim validation | 5/11 | All claims validate before rendering |
| Matrix authority/privacy planning | MOVE behavior, KEEP authority | SAFE/SOCIAL projections into Turn Plan | 3 | No permission/privacy regression |
| `cognition/routing.py` sequential orchestration | REPLACE | Cognitive Scheduler | 3/6 | Concurrent workers and ordering tests pass |
| `cognition/system.py` orchestration | MERGE | Turn Kernel/scheduler | 5/12 | Tool gateway loop is preserved elsewhere |
| Application `_model_lock` | REPLACE | Per-worker/session commit synchronization | 6 | Overlap and deterministic commit tests pass |
| `model_lifecycle.py` | KEEP/EXPAND | Resource-aware lifecycle | 7 | Runtime owns unified lifecycle state |
| Tray lifecycle reconstruction | DELETE | Runtime status projection | 8 | Tray controls/readbacks use runtime owner |
| KNOW retrieval | REPLACE | Unified hybrid retrieval | 9 | Provenance/stale revision tests pass |
| Context assemblers | MERGE | Turn-plan-driven context builder | 10 | Token/context budget tests pass |
| Independent SQLite connection patterns | MERGE incrementally | Shared SQLite infrastructure | 10 | Ownership and transaction tests pass |
| Provider quality/grounding repair | MERGE then DELETE overlap | Claim validation + renderer | 11/12 | Equivalent negative tests pass |
| Personality modulation | MOVE, KEEP semantics | Personality Renderer | 11 | Validated AnswerPlan is renderer input |
| Remaining V1 modules/imports | DELETE | V2 | 12 | Production import audit is clean |

## Baseline evidence

`docs/development/cognition-v2-baseline.json` was captured using the normal
application composition, Matrix, NEURO, context, persistence, and response
finalization path with the deterministic test engine on this cloud host.

Observed control-path results:

| Scenario | Wall | Process CPU |
|---|---:|---:|
| Startup | 441.129 ms | 440.902 ms |
| Casual conversation | 38.979 ms | 38.983 ms |
| Technical question | 33.768 ms | 33.774 ms |
| Fleet status request | 35.373 ms | 35.367 ms |
| Multi-turn follow-up | 51.016 ms | 51.023 ms |
| Idle observation window | 250.124 ms | 0.070 ms |

Peak process RSS observed was 72,855,552 bytes. The run persisted eight
conversation messages and four Matrix traces; the resulting temporary
`sofia.db` was 1,081,344 bytes.

Unavailable—not zero—on this host/run:

- Live primary and secondary inference latency
- Live VERIFY latency
- Prompt and generated token counts
- SQLite operation count across independently owned connections
- GPU load and VRAM
- Ollama model residency

These require live configured providers and the later shared instrumentation.
No performance improvement claim is made from this baseline.

## Batch 1 regression boundary

The Batch 1 tests validate:

- Principal/audience pairing in turn input
- Scope-preserving conversation focus
- Explicit subject identity on evidence needs and evidence atoms
- Separate epistemic and acquisition states
- Evidence requirement for observed/known claims
- Scheduler dependency and parallel-group validation
- No permission, consent, execution, or mutable-state field in the V2 contracts
- Honest unavailable metrics in the baseline schema

## Batch 2 migration sequence

1. Add durable, audience-scoped ConversationFocus storage in `sofia.db`.
2. Introduce one application-owned Turn Kernel.
3. Route existing Matrix/NEURO planning through the kernel as temporary
   delegates, without creating a fallback coordinator.
4. Move unresolved request, entity/reference, correction, and pending-action
   continuity into structured focus.
5. Thin `ConversationService` only after production and restart tests prove the
   kernel path.
