# Machine-learning foundation ownership (ML-001–ML-010)

Status: implemented source foundation; local and CI acceptance must be reported
separately. This map describes ownership and does not grant data use, training,
deployment, or execution authority.

## Source-to-consumer map

| Source/decision | Canonical owner / production source | ML use | Production consumer | Decision |
|---|---|---|---|---|
| Conversation and reviewed memories | CONVERSATION/MEM: `conversation/store.py`, `memory/provenance_store.py` | Excluded by default; exact raw conversation is prohibited | `application/conversation_learning.py`, COGNITION v2 | REUSE owner; never ambient-train |
| Habit observations | HABIT: `habits/continuity.py`, `habits/pattern_store.py` | Future source reference only after explicit scoped grant and independent outcome | existing background coordinator | REUSE; do not create ML habits |
| Projects, artifacts, preferences | LIFE/CREATIVE/PERSONALITY stores | Source/outcome references; no invented aesthetic label | `life/coordinator.py` | REUSE LIFE evidence and scheduler |
| Fleet telemetry and host identity | FLEET/OPS registry and `ops_telemetry_history` | Eligible CPU-only point-in-time features when fresh, scoped, retained, and granted | `learning/fleet_pressure.py` shadow pilot; OPS policy remains authoritative | REUSE; no second Fleet model |
| Attention and priority | `neuro/runtime.py`, `neuro/store.py` | Possible bounded feature or consumer; never evidence | `neuro/coordinator.py` | REUSE; no second feedback loop |
| Semantic plans and facts | `cognition/v2/`, typed Evidence Graph | Predictions may advise routing later; cannot establish facts | production turn kernel | REUSE sole semantic owner |
| Training/source review | `evolve/training_sources.py`, `training_policy.py`, `training_lab.py` | Existing public-source/LoRA admission remains authoritative | EVOLVE reviewed lab | EXTEND through exact lineage; do not replace |
| Consent, permission, STOP | `safe/permissions.py`, `safe/operator_stop.py`, INTERACT | Inputs to eligibility only; never prediction targets with authority | capability gateway and interaction policy | REUSE, fail closed |
| Work budgets and execution | `run/work.py`, `capability/gateway.py` | Candidate evaluation may later be scheduled through RUN | RUN receipts/reconciliation | REUSE; learning owns no worker |
| Canonical persistence | `state/canonical_sqlite.py` and `sofia.db` | Grants, lineage, manifests, evaluations, registry metadata, traces | `application/bootstrap.py` | EXTEND tables; no second database |
| Retention | `application/background_runtime.py` | Bounded derivative deletion | existing `ApplicationBackgroundCoordinator` | EXTEND existing scheduler |
| External model bytes | managed learning candidate root | Digest/signature-pinned immutable bytes | EVOLVE/SAFE-authorized deployment | REUSE managed external-asset pattern |

`sofia.learning.LearningService` is application-owned and has no thread,
scheduler, capability dispatcher, receipt creator, or authority method. The
optional signed candidate registry is unavailable unless an explicit trusted
Ed25519 public key and key ID are configured. Missing configuration therefore
fails closed.

The production chain added by this work is:

`SofiaApplication -> LearningService -> CanonicalSQLiteGuard -> sofia.db`

and, for cleanup only:

`ApplicationBackgroundCoordinator -> LearningService.enforce_retention()`.

The ML-008 production shadow chain is:

`ApplicationBackgroundCoordinator -> FleetPressurePilot -> OPS telemetry history`
`-> GoalEvidenceLedger source/outcome references -> LearningService lineage`
`-> ml_fleet_pressure_forecast diagnostics`.

It fits a bounded deterministic CPU trend candidate from at most 64 prior
observations per host, compares it with last-value and EWMA baselines after a
real delayed telemetry observation, and records missing coverage as UNKNOWN.
At most 32 trusted enrolled/healthy hosts are considered per tick. Gaming,
busy, do-not-disturb, STOP, missing grants, stale telemetry and absent CPU data
all suppress work. The pilot never calls placement, capability or RUN
execution APIs.

No prediction consumer is attached to a capability. The current consumer is
the existing owner settings/tray projection (`ui/settings_sections.py`). A
future Fleet pilot must hand a LIMITED recommendation back to existing
OPS/SAFE/RUN policy rather than executing it here.

## Per-data-use permission matrix

Each allowed cell still requires an exact unexpired grant for the authenticated
principal, original audience, named purpose, and operation. A permission for
one column does not imply another.

Creating or revoking that durable grant consumes an exact, one-use protected
SAFE execution approval (`learning.data_use.grant` / `.revoke`) in the same
SQLite transaction. Source and candidate revocation likewise consume protected
SAFE approvals. A submitted actor label or an `owner-ui:`-shaped string alone
is insufficient.

| Source class | Observe | Store | Extract scalar feature | Statistical train | LLM weight train | Deploy |
|---|---:|---:|---:|---:|---:|---:|
| Fresh Fleet/OPS observation | grant | grant | grant | separate grant | denied by foundation | separate deployment grant |
| Operation receipt / goal evidence | grant | grant | grant | separate grant | denied by foundation | separate deployment grant |
| Grounded artifact evaluation | grant | grant | grant | separate grant | denied by foundation | separate deployment grant |
| Owner-reviewed public JSONL | EVOLVE review | EVOLVE review | separate grant | separate grant | separate EVOLVE lab approval | separate deployment approval |
| Raw conversation or private journal | existing owner only | existing retention only | denied | denied | denied | n/a |
| Screen or audio capture | capture permit only | capture retention only | denied | denied | denied | n/a |

Prediction records contain scoped values, source-reason references,
uncertainty, expiry, and mode. Their contract always reports
`grants_authority = false`, `grants_consent = false`, and
`is_factual_evidence = false`. OBSERVE/SHADOW/ADVISORY/LIMITED change visibility
and comparison behavior only. Even LIMITED cannot call a capability or bypass
SAFE, STOP, gaming policy, RUN budgets, privacy, or consent.

## Retired or rejected paths

- No ML-specific scheduler, action executor, permission engine, evidence graph,
  memory store, or feedback/reward engine.
- No positive label from praise, an LLM self-report, a goal record, or a model's
  own execution claim.
- No cross-principal or cross-audience feature joins.
- No automatic model promotion or live Fleet placement.
- No model bytes in SQLite and no unverified path or unsigned candidate load.

## ML-010 trial boundary

The code now supplies a restart-safe SHADOW measurement path and diagnostics,
but it is **not** evidence that the required two-week Fleet canary ran. Starting
that trial still requires an exact-revision owner-approved data-use window and
real enrolled-host operation. Advancement beyond SHADOW additionally requires
an independently accepted evaluation and one-use SAFE mode approval. Cold and
restarted worker coverage, real latency/capacity measurements, error rates and
rollback must be collected for at least fourteen days before ML-010 can move
beyond `CODED_UNFINISHED`.

## ML-011 through ML-020 production audit

The Fleet shadow owner now records bounded CPU, RAM, GPU and VRAM targets at
5, 15 and 30 minutes. Unknown/untrusted hosts, foreground gaming, missing
metrics, stale gaps and out-of-order ingestion produce explicit diagnostic
events rather than labels. Threshold anomaly candidates and false alarms are
diagnostic only. Placement advice first calls the existing OPS policy with an
enrolled node identity, fresh telemetry and activity state; its cost annotation
cannot enroll a host or move work. Normal authenticated Fleet operations now
append bounded passive round-trip evidence only after the pinned-mTLS gateway
returns an identity-matched result. The advisor requires at least three fresh
samples for that exact host and enrolled node, publishes its recency-weighted
latency estimate beside a last-value baseline and uncertainty, and abstains for
missing, stale, or mismatched evidence. It never sends a probe. The existing read-only
`ops.placement.choose` capability now requests that annotation after OPS makes
its deterministic decision; predictor abstention or failure cannot change or
block the OPS result. A local error-rate circuit breaker disables
only learned advice and leaves deterministic OPS scheduling active. This codes
ML-011 through ML-014; local requirements are tested, while real-host accuracy,
utility, and exact-revision CI remain unverified.

MEM now has one optional explicit-feedback projection. It records the final
eligible retrieval set, accepts authenticated private `relevant`,
`not_relevant`, `correction`, or `unknown` judgments, and retains exact source
IDs. Silence creates no row. The bounded scorer needs at least eight known
labels and three for the query topic; weak, stale, rare-topic, invalid or
unavailable state falls back to deterministic MEM order. Revocation,
correction, and point-of-use source/privacy reconciliation invalidate
influenced models. The scorer receives only MEM's final promoted,
principal/audience-scoped shortlist and cannot retrieve or authorize anything.
This codes the core of ML-015 through ML-018. ML-019 now freezes the original
deterministic order, scorer order, model lineage, exact eligible IDs and typed
owner reviews for timeline, correction and source truth. Its paired evaluator
calculates held-out recall@5, NDCG@5 and known-label accuracies while preserving
unknowns. ML-019 remains incomplete until independent future conversations
actually populate and validate those metrics.

ML-020 has explicit, reversible, restart-durable feedback for genuine LIFE
project invitations and ordinary reflections, conversation follow-ups, goal
updates, and DEV findings. Usefulness and interruptiveness remain separate;
silence and cleared ratings are unknown. Every accepted change retains its
exact original event and audience. A `too_interruptive` preference suppresses
only that ordinary update class. Operational alerts, Fleet anomalies, and
approval requests are deliberately outside this preference surface.

## Remaining external acceptance

The foundation can be verified locally and in pinned-revision CI. A real model
training run, Fleet shadow trial, Venus/Artemis resource measurement, promotion,
and Gate 4 remain separate, explicitly authorized work. This document is not
their evidence.
