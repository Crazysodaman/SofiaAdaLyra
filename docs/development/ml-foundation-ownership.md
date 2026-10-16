# Machine-learning foundation ownership (ML-001–ML-007)

Status: implemented source foundation; local and CI acceptance must be reported
separately. This map describes ownership and does not grant data use, training,
deployment, or execution authority.

## Source-to-consumer map

| Source/decision | Canonical owner / production source | ML use | Production consumer | Decision |
|---|---|---|---|---|
| Conversation and reviewed memories | CONVERSATION/MEM: `conversation/store.py`, `memory/provenance_store.py` | Excluded by default; exact raw conversation is prohibited | `application/conversation_learning.py`, COGNITION v2 | REUSE owner; never ambient-train |
| Habit observations | HABIT: `habits/continuity.py`, `habits/pattern_store.py` | Future source reference only after explicit scoped grant and independent outcome | existing background coordinator | REUSE; do not create ML habits |
| Projects, artifacts, preferences | LIFE/CREATIVE/PERSONALITY stores | Source/outcome references; no invented aesthetic label | `life/coordinator.py` | REUSE LIFE evidence and scheduler |
| Fleet telemetry and host identity | FLEET/OPS registry and telemetry adapters | Eligible scalar features when fresh, scoped, retained, and granted | OPS/FLEET policy (future ML-008 pilot) | REUSE; no second Fleet model |
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

## Remaining external acceptance

The foundation can be verified locally and in pinned-revision CI. A real model
training run, Fleet shadow trial, Venus/Artemis resource measurement, promotion,
and Gate 4 remain separate, explicitly authorized work. This document is not
their evidence.
