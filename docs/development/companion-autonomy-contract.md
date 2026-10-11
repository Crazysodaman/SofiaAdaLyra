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

`SofiaApplication.latest_companion_decision_trace()` provides a content-minimal view over the current session's *existing* Matrix trace and the latest NEURO snapshot. `neuro_turn_correlated` is **false**, because a timestamp from another subsystem does not demonstrate causal participation in this turn. LIFE/GOALS/ACT and final verified outcomes are **unset**, not invented. No writes, permissions or model calls are involved. Future explicit event correlation may enrich this view only after verifying source IDs and audiences.

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
