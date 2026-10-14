# Companion autonomy contracts: P0 architecture, existing canonical owners

> **Source audit / implementation contract, not a passing test.** Updated 2026-10-10.
> Audited `main`: see `p0-architecture-release-audit-2026-10-10.md` and exact current commit.
> This is an extension of existing SAFE, Matrix v2, LIFE, MEM, NEURO and RUN contracts, **not** a replacement ledger or new runtime.

## Invariants

1. **The cognitive provider is replaceable.** Model text cannot amend identity, Constitution, safe policy, scope, evidence, execution results, relationship or memory truth.
2. **The canonical runtime and state plane are unique.** One `SofiaApplication` owns canonical `sofia.db` and the active service authority on the selected primary host. Read-only clients and fenced workers are not competing writers. A database copy is backup until explicitly promoted with independent fencing.
3. **One turn semantic owner.** `ProductionTurnKernel`/Matrix v2 decides turn domains, evidence requirements, routing and context. NEURO is an attention/routing advisor, not a fact validator.
4. **Audience boundaries bind even for one human.** Desktop, Discord, mobile and future Main/project threads may use a shared authenticated principal while presenting a separate audience and output policy. A shared session must not bypass `SocialSessionStore` restrictions.
5. **Recorded modeled emotion is not a physiological fact.** Expression must be verified against renderer/voice/transport receipts before claiming delivery.
6. **Evidence is graded.** `observed`, `verified`, `inferred`, `simulated`, `hypothesized`, `stale`, `unknown`, `revoked` remain distinct. An LLM statement or a simulation cannot silently become verified.
7. **Idempotency and uncertainty.** A crashed remote operation with unknown completion must not be blindly retried; require outcome reconciliation and existing operator authorization.

## Authoritative writer / consumer / failure table

| Canonical concern | Writer / grounded store | Reader / projection | Failure and retention |
| --- | --- | --- | --- |
| Turn plan, privacy, routing and completed trace | Cognition v2 kernel + `MatrixTraceStore` | Conversation, UI, `CompanionDecisionTrace` | Failed turn is not a completed action; keep bounded content-minimal trace |
| User transcript | `ConversationStore` | UI, Discord, MEM source retriever | Persist originals; bounded provider projection; no automatic deletion on model change |
| Authenticated principal/audience | `SocialSessionStore` + channel binding owners | SAFE, REL, MEM, output adapters | Wrong audience fails closed |
| Facts / claim evidence | `CognitiveEvidenceLedger` + evidence graph | Cognition v2, evaluation, diagnostics | Corrections revoke dependent conclusions, don't forge a prior observation |
| Memory candidates and promotion | `MemoryReviewService` + provenance candidate store | MEM retrieval, other reviewed context | Candidate != fact; revoked memories cannot be reintroduced by cached summaries |
| Modeled emotion and relationship | `EmotionalJournal`, `RelationshipStore` | Conversation, avatar/voice projections | Emotional expression cannot override factual evidence or consent |
| Goal intent | `GoalService` + `GoalStore` | LIFE, RUN, optional ACT | Goals require SAFE at execution; noncompletion remains explicit |
| Independent personal activity | `SelfDirectedLifeCoordinator` + `LifeStore` | GOALS, RUN, ACT, UX | One-use artifact grant; evaluation distinct from assertion of success |
| Execution / job outcomes | RUN and capability gateway receipts | LIFE, GOALS, VERIFY, ACT | UNCERTAIN outcome never auto-becomes completed |
| Outreach | ACT presence/service & delivery receipts | Desktop, Discord, Mobile | Transport accepted != user saw/acknowledged |
| NEURO attention | `NeuroRuntime` + its observability | Cognition, background admission | Salience isn't permission, memory or proof |
| Stored assets and world | WORLD and Creative stores | LIFE, avatar/renderer | Persist source links, never claim render from text only |
| Host discovery and Fleet identities | Fleet Ops + authenticated agent stores | Capability gateway, machine inventory | Unknown endpoint/failed mTLS blocks tools; no implicit enrollment |
| Release and backups | RUN release/backup owners | VERIFY, recovery operator | No activation from an unverified build/manifest |

## Source-to-sink diagram 1: a user turn

```text
Desktop/Discord/mobile authenticated input
  -> canonical session + principal/audience binding
  -> durable user message
  -> one ProductionTurnKernel / Matrix v2 turn plan
  -> bounded NEURO attention and authorized MEM/context projection
  -> approved cognitive route, tools only via capability gateway
  -> response validation and persisted assistant message + Matrix trace
  -> channel-specific delivery / separate actual receipt
```

## Source-to-sink diagram 2: independent LIFE work

```text
interest / authentic observation / reviewed preference
  -> LIFE idea -> deterministic feasibility + resource + SAFE gate
  -> project and GOALS (desire does not grant execution)
  -> bounded RUN job / one-use authorization
  -> artifact/result and immutable capability receipt
  -> independently verified objective + critique
  -> milestone status + optionally reviewed MEMORY candidate
  -> ACT shares only after scoped outbound authorization
```

## Source-to-sink diagram 3: recovery/failover

```text
canonical writer on approved host
  -> consistent SQLite snapshot + protected files + integrity manifest
  -> encrypted independent backup copies and restoration checks
  -> unavailable active writer: no silent dual-writer auto-promotion
  -> external operator/witness confirms fence and recovery epoch
  -> one standby promoted / restored, clients reauthenticated
  -> compare archive pointers, identity and schema, then resume
```

## Typed event and authority semantics

Event IDs are stable and source-owned. Originating producers attach UTC observation time, subject, source, authenticated principal, audience, expiry/freshness, trust/evidence references and optional action/goal/project identifiers. Downstream adapters may add an interpretation but not mutate the originating evidence or expand its audience. Omitted information must remain `unknown`, not silently default to success.

| Requested operation | Read/inspect | Scoped reversible | Protected/high impact | Never self-authorized |
| --- | --- | --- | --- | --- |
| Observe approved machine status | Existing read scope | n/a | n/a | n/a |
| Offer a creative project, choose quiet time | Goal/presence constraints | Optional bounded creation by grant | n/a | n/a |
| Change system services or GUI | Inspect first | Exact/expiring approval where permitted | Explicit operation-specific consent | Permission escalation |
| Provision a guest, release code, move canonical database | Read plan | Not self-admitted | Human-controlled verified execution | Change identity/Constitution/security owner |
| Delete/restore protected history | Read evidence | n/a | Human-specific authorization | Rewrite historical evidence as though it never happened |

## Context projection budget (future calibration, not live numbers)

Priority order: active user intent and protected instructions; fresh authoritative evidence and relevant current topic; action/permission receipts; narrowly retrieved, promoted memory; recent dialog; modeled affect/presentation; optional project hints and debug noise last. Every domain has a configurable bounded token/character quota. Keep raw originals searchable outside the provider window. Suppress stale, low-confidence, wrong-audience and unrelated project material. Benchmark actual CPU/token/latency before setting default quotas.

## Decision tracing: limited, truthful first implementation

`SofiaApplication.latest_companion_decision_trace()` provides a content-minimal read-only projection over existing Matrix, conversation, SOCIAL and authenticated stable-turn settlement records. It can attribute an **in-process NEURO observation** only when the conversation service's current NEURO message ID and Matrix message ID equal the exact user event; the latest global NEURO timestamp alone is not proof. Verified canonical response persistence is distinct from transport delivery, actual action execution and independently validated objective completion. LIFE/GOALS/ACT outcomes remain **unset**, not invented. No new authority or state ledger is created. On restart a missing ephemeral NEURO correlation remains unknown, not retrospectively inferred.

## Failure policy and model outage

Provider timeout, invalid structured output or model outage must be classified and surfaced as error/unknown; do not turn absence into the expected user-facing answer, retry uncertain external actions or block emergency operator-stop controls. Background work may suspend while the foreground chat remains available. Failure injection and live proof are reserved for Phase 01's later acceptance execution.

## Research and acceptance plan (no tests executed this coding pass)

Preregister comparisons for LIFE alone, LIFE+MEM, +NEURO, +reusable skills and isolated workshop, against a simple bounded-rule baseline. Report correct objective outcomes, false claims, CPU/RAM/VRAM, latency, unnecessary waking, p95 under gaming, topic switching, user correction accuracy, and privacy breaches. For LongMemEval/LoCoMo use explicitly adapted subsets with sample sizes and abstention rate. A complex component is admitted only if it earns measurable improvement. Distinguish `coded`, `focused-tested`, `full-gate`, `Windows-live`, `Fleet-live` and `accepted`.

### Acceptance matrix axes to fill with exact revisions

`model route × channel/source × principal/audience × text/voice/avatar/vision × SAFE level × gaming/busy state × clean/restarted/partitioned state × failure class`. Sampling must include unauthorized cross-channel relays, rejected avatar-only claims, memory correction, invalid model output, false execution receipts, cancelled jobs and duplicate delivery. Tests are written/executed only on explicit user permission.

## 2026-10-11 SAFE / owner authentication source audit (CA-1201, CA-3105)

The preceding contract predated the owner-approved hybrid auth coding. The following mapping is **observed in source but not tested**; it does not replace the original event diagrams.

| Decision | Canonical authority and production route | Admission / failure |
| --- | --- | --- |
| Level 1 read-only | `safe/permissions.py` classification to existing read capability handlers | Existing approved source scope; no implicit ability to publish to another audience |
| Level 2 bounded automatic | Deterministic SAFE admission and guarded RUN/ACT handlers | No new scope or model-text-specified permission |
| Level 3 scoped standing | `PermissionStore.grant/revoke/grants/allows_standing` → real handler | Exact action-bound FIDO2 receipt to create/revoke; historical unsigned grant not effective; revoked signing key disables grant |
| Level 4 protected exact effect | `owner_browser.authorize_exact_action` → `ExecutionApprovalVerifier.record/matches_unconsumed/consume` | Authenticated credential, exact parameters, expiry, one use; actor string alone is denied |
| Level 5 security/private authority | `PermissionStore.set_private_adult_authority`, `private_adult_authority` | Fresh FIDO2; old unsigned adult expansion is fenced; stored restrictive `private_chat=False` remains restrictive |
| Emergency stop | `OperatorStopStore.set` via CLI and Settings | Immediate PAUSE; RESUME requires exact unchanged stop revision and signed FIDO2 approval |
| Local owner principal | Windows token SID pinned by `owner_enroll_browser.py` and checked by UI/Tray | First trusted enrollment requires supervised Windows terminal/Hello; later graphical sessions require pinned SID plus WebAuthn, not a console |
| FIDO2 key lifecycle | `owner_registration.py` + credential/challenge records in canonical SQLite | Additional key signed by existing authenticator; revocation blocks future approvals and associated standing grants |
| Local control surfaces | `ui/settings_window.py`, `ui/tray_agent.py`, `safe/permissions_cli.py` | Signed owner approval for model/Fleet/service/standing/Level-5 changes; UI callbacks defer long WebAuthn prompts to workers |

**Trust caveat:** Registration with WebAuthn `fmt=none` and a client-reported cross-platform attachment does not demonstrate manufacturer attestation or uniquely prove a hardware-backed private key. The physical-key identity policy remains an owner-controlled design limitation until hardware evidence is reviewed.

**Error state and evidence:** Internal SAFE approval consumption establishes authority, not the success of the external side effect. Failed or interrupted operations require their own RUN/ACT receipt; a consumed but unexecuted approval must not be replayed automatically. Producer/audience scopes remain owned by their originating adapters. This review does **not** yet trace all DEV/EVOLVE or remote Artemis/migration effects, nor prove no other caller bypasses SAFE.

**Host state:** Venus is the sole authorized canonical writer; the owner reported Debian installation in progress on the dedicated Artemis `Sofia` VM. No writer cutover, live key enrollment, remote host action, tests, CI or build took place in this audit.

**Acceptance gate remains open:** Review exact-SHA diffs, execute focused SAFE tests, run the full original V18 package test gates, then supervise physical Windows Hello/FIDO2 and multi-host acceptance before reclassifying any status as accepted.


## CA-005: event/evidence envelope source-to-sink ownership map (2026-10-11)

This table maps the *requested envelope semantics* to currently existing typed source owners. **An event envelope is a view, not a new canonical row.** Each adapter is required to project source-owned values and to preserve `unknown` where a source lacks the necessary field.

| Envelope field | Typed canonical source or derived adapter | Verified limitation / sink |
| --- | --- | --- |
| `event_id` | `life/model.py:ProjectEvent.event_id`; conversation message ID (`conversation/model.py`); Matrix `TurnEnvelope.message_id`; RUN job/result identifiers; ACT message/delivery IDs | **No single universal event ID yet.** Distinct schemas must preserve original IDs and namespace them without reassigning the source identity |
| `source` | `cognition/matrix/model.py:EvidenceRecord.source_ref`, individual LIFE/RUN/ACT producer/store | Never infer a trusted source from an LLM citation string; `None` remains unknown |
| `subject` | Project `project_id`, goal `goal_id`, conversation `session_id` and measured resource identity from its owning model | Not every producer includes a universal subject ID. Adapter must not substitute the current chat user |
| `principal` | `social/model.py:PrincipalContext.principal_id`; `life/model.py:LifeProject.creator_principal_id/owner_principal_id`; `matrix/model.py:TurnEnvelope.principal_id` | Producer/caller identity must remain separate from tool authority; a natural-language display name is not authentication |
| `audience` | `social/model.py:SocialScope` / `AudienceKind` plus channel delivery and session binding owners | `TurnEnvelope.channel` alone is **not** adequate evidence of permitted cross-channel audience |
| `observed_at` | `TurnEnvelope.created_at`, `life/model.py:MotivationSignal.observed_at`, durable event/receipt timestamps owned by producer | Timestamps are not interchangeable: event occurrence, ingestion and presentation may be different |
| `expiry/freshness` | Existing permission grant expiry, action/ACT delivery expiry and Matrix `EvidenceState.STALE` | Some evidence records have no expiry. Do not project `fresh` based only on existence |
| `confidence` | `cognition/matrix/model.py:TurnMatrix.confidence` and `life/model.py:ProjectIdea.confidence` | Source-specific confidence is **not** universal factual certainty or permission |
| `evidence_refs` | Matrix `EvidenceRecord.source_ref` and provider-specific typed source IDs; `CompanionDecisionTrace.referenced_evidence` is a limited projection | A reference is a pointer requiring access/verification, never by itself proof of truth |
| `action_id` | Existing SAFE `ExecutionApproval.approval_id`, capability/job effect receipt and RUN job reference | Approval ID is **not** an execution-success receipt |
| `goal_id` | `life/model.py:LifeProject.goal_id` and canonical GOALS service/store | Empty means not linked; do not invent a goal from topic similarity |
| `project_id` | `life/model.py:LifeProject.project_id`, `ProjectEvent.project_id`, GOALS and LIFE associations | Project correlation needs a source-owned explicit link, not nearest-time coincidence |
| `consent_class` | `safe/permissions.py:PermissionLevel`/privacy classification plus exact scoped grants and authenticated owner approval | No producer-level consent derived from emotion, desire, historical conversation or automatically generated text |
| `renderer/transport receipt` | ACT actual delivery/queue status (`application/act_service.py`), Desktop/Discord/Mobile adapters; expression renderer/TTS have separate owners | `desktop-queued`, `discord-ack`, `mobile-queued`, `ha-ack` prove only their specific stage, not human observation or physical embodiment |

**Observed independent paths:** `application/bootstrap.py:SofiaApplication` composes canonical cognition/NEURO/MEM/LIFE/GOALS/ACT; `application/background_runtime.py` supplies distinct asynchronous LIFE and backup/ACT workers. `application/decision_trace.py:project_companion_decision` currently surfaces Matrix `message_id`, `session_id`, principal and referenced evidence. Its `neuro_turn_correlated` flag is true only for a supplied, exact current-message NEURO observation; the conversation service rejects stale or mismatched message IDs before that read-only correlation. Missing goal/project/ACT effect receipts and `objective_verified=False` remain **explicit truthfulness boundaries**. A correlated observation does not prove NEURO caused the reply or an external action.

**Outstanding CA-005 work:** one source-verified adapter interface per producer, independent typed evidence/receipt links for MEM/GOALS/LIFE/RUN/ACT across a single turn, audience checks before projection, operational retention/expiry policy, and tests for missing/stale/revoked/contradictory inputs, restart and multi-host cutover. Same-message NEURO correlation now has focused tests; no complete causal chain or downstream effect proof has been validated. **Do not manufacture a universal event ledger or declare CA-005 accepted.**

## CA-001: end-to-end event-trace static audit boundary

The existing production composition includes the COGNITION v2/Matrix turn trace, `application/background_runtime.py` background LIFE/NEURO functions, original conversation store, SAFE permission gate and ACT delivery service. **Static source evidence does not yet establish a single concrete event traversing all of those subsystems.** Particularly the current `CompanionDecisionTrace` deliberately refuses to claim NEURO causation or LIFE/GOALS/ACT settlement without shared source references. Thus the full CA-001 trace remains **partial/unverified**, with a future controlled event fixture needed to prove each actual caller and settled receipt.

## CA-3104 / CA-1202: versioned LIFE+RUN decision state graph

**Architecture decision:** A personal project status is not the RUN job status. Canonical `LifeProject.status` and `WorkJob.status` remain owned by their existing tables and `PROJECT_TRANSITIONS`/`DurableWorkStore.transition`; the user-facing state below is a **read-only projection** produced by `SelfDirectedLifeCoordinator`. Do not introduce a second persistent scheduler or silently equate a delivered artifact with a verified project.

| Source state / predicate | Canonical action | Requested operator-visible next decision | Forbidden shortcut |
| --- | --- | --- | --- |
| No project, voluntary quiet period, or paused project | `LifeStore.quiet_until`, `LifeProject.status` | `rest` or silence until eligibility changes | Invent urgent activity or send unapproved outreach |
| Active project with no RUN job and active GOALS | LIFE/GOALS + resource/SAFE eligibility | `explore` or queue one bounded authorized task | Treat self-chosen interest as permission |
| RUN `QUEUED` or `RUNNING` | `DurableWorkStore` original work status | `wait`; preserve job ID and observed status | Queue duplicate work to make progress look faster |
| RUN `WAITING_APPROVAL` | RUN original permission-blocked state | `ask` for independent owner authorization | Mint permission from operator-name label or LLM narrative |
| RUN `BLOCKED` | RUN original blocked receipt | `ask` / review blocker | Reclassify blocked as completed |
| RUN `FAILED` or `CANCELLED` | RUN failure/cancellation event | `ask` or `review`; gather failure evidence | Automatically erase failure or create retry with old grant |
| RUN `UNCERTAIN` | RUN original uncertain effect | `ask` for reconciliation and read-only observation | **Never automatically retry an effect that might already have happened** |
| RUN `COMPLETED` without linked artifact | RUN completed receipt, no LIFE artifact proof | `verify`: missing or unlinked evidence | Treat a successful executor return as an objective success |
| RUN `COMPLETED` with artifact but no independent evaluation | LIFE artifact index and RUN link | `verify`: independent artifact review | Fabricate completion from draft or template |
| Independent evaluation inconclusive | `ArtifactEvaluation.technical_outcome=INCONCLUSIVE` | `ask` or `review` for more evidence | Claim verified objective |
| Independent evaluation invalid | `TechnicalOutcome.INVALID` | `review` then propose bounded revision/pause | Discard adverse evidence |
| Independent evaluation valid but open milestones | LIFE milestone/status evidence | `verify` and settle milestone with source proof | Mark all original objectives complete from one result |
| Verified project completion | LIFE project+GOALS+original RUN receipt+current source artifact verification | `COMPLETED`; optional consent-bound sharing | Announce milestone/project done without external source verification |
| Abandoned/rejected/archived/superseded | `LifeProject.status` and source event trail | Silence or explicit review/reactivation if authorized | Reactivate via a background prompt |

**Original source hooks:** `life/model.py:PROJECT_TRANSITIONS` enforces legal project-status changes; `life/coordinator.py:pending_work_review` maps RUN `UNCERTAIN` to `uncertain_no_automatic_retry`, `WAITING_APPROVAL` to `awaiting_separate_operator_approval`, and failed/blocked to review; its project diagnostics derives `next_action` from STOP, original goal, budget, run status, artifact evaluation and verified milestones. `run/work.py:WorkStatus` and `DurableWorkStore.transition` remain the RUN authority; `life/store.py` retains original work outcome observations and links instead of overwriting RUN proof.

**Decision transition schema v1 (documentation, NOT new runtime state):**

```text
LifeProject.status + original RUN status + original GoalStatus
  + relevant SAFE/operator-stop + original artifact/evaluation/milestones
   -> read-only LIFE diagnostic {project_id, condition, source,
       source_job_id, last_run_event_id, next_action, next_reason}
   -> only an independently permitted RUN/GOALS/LIFE action may update
       its own canonical store; after restart recompute this view
```

**Idempotency/replay and correction requirement:** Reusing a previously consumed SAFE approval, executing the same external mutation after `UNCERTAIN`, or remapping stale material host observations to a new plan is forbidden. Explicit `ProjectEvent` evidence refs, RUN job IDs and event IDs must be preserved for reconciliation; corrections update the owning source/review record, not the prior event's claimed success.

**Partial source audit status:** This source review confirms multiple existing decision branches and a versioned *design contract*, not all required restart/dedupe/correction/failure-injection tests or every external effect predicate. CA-3104 and CA-1202 remain **partial** until source-by-source acceptance proves all branches. The technical outcome `VALID` is not proof that the *original personal objective* was fulfilled without independent evidence.


## CA-3101: ownership/consumer/error-state audit, 2026-10-11

The project already has a **static, non-executing ownership inventory** in `src/sofia/verify/architecture_inventory.py:OWNERS`. Its listed owners include application, turn kernel, conversation, social, memory review, emotion, relationship, GOALS, LIFE, RUN, SAFE, ACT, NEURO, WORLD, Fleet, state, backup, release and VERIFY. The authoritative writer/consumer/failure table near the beginning of this document maps the same concern families to their storage and readers; its three source-to-sink paths show the user turn, independent LIFE work and fenced recovery.

**Missing proof:** the AST inventory is a *source-existence tool*, not evidence that actual `SofiaApplication` production bootstrap reaches every component, all relevant data writers use one canonical `sofia.db`, failed/superseded snapshots are retained correctly or every Fleet effect enforces permission. Source-only findings cannot be promoted to a complete caller-by-caller ABI audit. The design requirement for component ownership is **partially source-wired**, pending review of actual inventory output, error-state traces, retention policy and tests.

## CA-1203: existing context-window controls and unimplemented budgets

A real prompt-context budget spans different owners; no one component has authority to truncate canonical originals.

| Existing control | Production owner | Observed behavior | Remaining gap |
| --- | --- | --- | --- |
| Provider route budget | `src/sofia/cognition/budgets.py:model_token_budget` | Validated route hints target 2,048 fast, 4,096 standard, 8,192 deep/open or 16,384 verify context tokens; configured limits clamp allocations; output tokens also bounded | Actual provider token accounting and cross-model budget acceptance not measured in this work |
| History message count | `src/sofia/cognition/matrix/context_plan.py:MatrixContextPlanner` | History limit for NONE/LAST_TURN/TOPIC_WINDOW/BOUNDED_RECENT/RETRIEVE_SPECIFIC = 1/3/8/12/1 | Counts are not token or character limits; long single source message can still dominate |
| Per-turn domain eligibility | `TurnMatrix.domains` / `ContextPlan.included_domains` via `conversation_matrix.py` | Domains excluded at `MatrixRelevance.NONE`; user turn retained; history filtered to current policy | Provenance/freshness for every optional payload, audience transfer and cumulative size not yet individually proved |
| Independent optional work | `application/optional_budget.py:OptionalAutonomyBudget` | Canonical daily quota reservations protect background work; separate from interactive prompt window | Reservations are conservative estimates, **not actual CPU/GPU/tokens measurements** |
| Memory/evidence | Matrix `EvidenceRecord.source_ref`, MEMORY candidate/retrieval stores | Source-ref provenance can be exposed without importing all raw text into one prompt | Dedicated per-class caps for episodic retrieval, broadcasts, affect/style, current project and factual evidence still require code and tests |

**Non-negotiable selection order:** active user intent, identity and protected policy, relevant current source/evidence and permission receipts first; bounded relevant dialogue and independently promoted memory second; optional LIFE/project/affect/wardrobe and other presentation/context last. Low-confidence, stale, unrelated or wrong-audience materials must be rejected at their source/admission boundary rather than silently truncated into apparently true statements. Retrieved references do **not** authorize tools.

**Source acceptance:** existing controls support a **partial** context window solution, not the requested complete explicit per-class measured prompt budget. Any new source-specific budget must preserve canonical transcripts outside the window and report what was excluded for size, relevance, freshness or audience. Focused and full acceptance remain unrun.
