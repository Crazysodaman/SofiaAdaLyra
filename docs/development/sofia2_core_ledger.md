# Sofía 2.0 Core implementation ledger

One unified ledger for the owner-directed Sofía 2.0 Core B00–B08 sequence.
Planning baseline: `docs/sofia2/` (README, ARCHITECTURE, CORE_1_0_PLAN,
NON_CORE_MODULE_PLAN, UNIFIED_780_PLAN, DEVELOPMENT_WORKFLOW), the original
780-task inventory (`docs/Sofia_V18_700_Tasks_Brief_Table.md`), the five-level
evidence standard (`docs/development/V18_TASK_STATUS_STANDARD.md`), the
companion autonomy contract, the Constitution and the actual source on `main`.

These planning documents are requirements, not implementation evidence.
Status claims in this ledger use the L1–L5 definitions of the evidence
standard and are recorded only after the listed command actually ran on the
listed revision/environment. Local runs are never claimed to be CI (L5).

## Environment and session baseline

| Field | Value |
| --- | --- |
| Branch | `main` (local, owner-published remote) |
| Local base SHA | `e5e4407e` ("docs(sofia2): establish Core architecture and expanded non-Core module roadmap") |
| Prior local HEAD | `af860fd8` (fast-forwarded forward to `e5e4407e`, clean tree, no reset/force) |
| OS | Windows (UNC workspace `\\Artemis\Hestia\Users\Crazysodaman\Programing\SofiaAdaLyra`) |
| Python | 3.12.10 (`.venv`) |
| Test collection | 6760 tests collected (`pytest --collect-only -q`) |
| Companion worktree | `...-fleet` holds branch `test/fleet-tray-remote-controls`; out of scope |
| Commit/push authorization | NOT granted. All work stays uncommitted until the owner authorizes a checkpoint. |

Scope guardrails honored this session: no production deployment, no DB
migration, no protected-authority edits, no canonical-writer ownership
change, no service restart, no git commit/push without separate approval.

## Source audit performed for CORE-B00 (evidence: this session)

Findings marked OBSERVED were read directly on this revision; protocol
observations below come from targeted file reads, not from memory:

- **One canonical composition**: `src/sofia/composition/root.py` `compose()`
  (line 120) is the only full-runtime composer; `SofiaApplication`
  (`src/sofia/application/bootstrap.py:191`) re-binds to the reviewed
  configuration after `compose()`; desktop entry
  (`src/sofia/ui/desktop_application.py`) creates exactly one local
  `SofiaApplication`. `TrayAgentApplication` (`src/sofia/ui/tray_agent.py`)
  is a documented supervised partial composer over the same canonical DB and
  explicitly refuses to initialize a second canonical database
  (`tray_agent.py:63-66`).
- **One canonical writer plane**: `src/sofia/state/canonical_sqlite.py`
  (`require_existing_sqlite`, `CanonicalSQLiteGuard`,
  `bootstrap_canonical_sqlite`); `src/sofia/state/sqlite_access.py`
  `shared_sqlite_access` bounds per-database access rows; production
  preflight (`test/test_production_canonical_startup_preflight.py`)
  verifies empty/missing state is refused before composition. Explicit
  secondary databases (lab DB, draft journal, fleet journals, recovery
  snapshots) refuse the canonical name and are documented, not conflicts.
- **Identity/authority boundaries**: `src/sofia/constitution/store.py`
  (immutable constitution + SHA-256 integrity verifier),
  `src/sofia/identity/store.py` (once-only `instance_id`,
  `REQUIRE_EXISTING` fail-closed for rebuilt nodes), SAFE
  (`src/sofia/safe/permission_store.py`, `execution_approval.py`,
  `operator_stop.py`, `dev_approval.py`), capability gateway
  (`src/sofia/capability/gateway.py`) with access limits enforced at
  authorization time.
- **Filesystem ordering**: `RuntimeStorageLayout.provision_from_source`
  (`src/sofia/config/layout.py:153-293`) publishes seeds with fsync +
  atomic `os.link` (never `os.replace`), rejects symlink redirection on
  protected authority paths, and creates nothing in `REQUIRE_EXISTING`
  mode. `compose()` performs the canonical DB preflight before any
  SQLiteStatePlane/permissions/memory store initialization
  (`root.py:124-128`).
- **No duplicate cognitive engine**: engine creation funnels through
  `src/sofia/composition/engines.py`; `ProductionTurnKernel` is the single
  conversation semantic owner (Cognition v2 cutover batch, recorded in
  PROJECT_HISTORY.md).
- **No shadow identity**: identity is loaded by `IdentityStore` with
  once-persisted `instance_id`; no competing identity store exists.

### B00 gap found and addressed

- **Baseline diagnostics gap:** no single non-mutating "doctor"/preflight
  report combines storage layout, canonical state integrity, schema
  registry compatibility, constitution integrity, identity authenticity,
  personality/embodiment loadability, startup heartbeat readiness and
  writer-lock facts. Existing pieces were spread across
  `ui/settings_service.database_diagnostics`, `run/heartbeat.py`
  (mutating store), `state/component_schema.py` (mutating registration),
  `run/host.py` (supervisor path). Implemented as
  `src/sofia/run/doctor.py` (see B00 section below).

## B00 — Foundation and baseline

Owner requirements (CORE-01/35 substrate, ARCHITECTURE platform rules):
canonical composition, identity/state ownership, context and authority
boundaries, dependency mapping, filesystem ordering, baseline diagnostics,
schema compatibility, source-to-runtime ownership contracts, build and
focused-test infrastructure, no duplicate writers/engines/identities.

Status: **implemented (L3→L4 evidence recorded; L5 pending CI)**.

| Requirement | Status | Evidence |
| --- | --- | --- |
| Source-to-owner audit | DONE (audit above) | direct file reads on `e5e4407e` |
| Baseline diagnostics | DONE | `src/sofia/run/doctor.py` (non-mutating; 10 checks: storage layout, canonical state pinning, SQLite quick_check, schema registry compatibility, constitution integrity, identity authenticity, personality/embodiment loadability, startup heartbeat, writer lock files); CLI `python -m sofia.run.doctor [--state-path] [--json]` with exit codes 0/3/2 |
| Doctor tests | PASSED | `test/test_run_doctor.py` — 9 passed (`pytest test/test_run_doctor.py -q`, Windows venv Python 3.12.10) |
| Focused baseline suite | PASSED | `pytest test/test_composition.py test/test_application.py test/test_runtime.py test/test_canonical_sqlite_protection.py test/test_production_canonical_startup_preflight.py test/test_state_component_schema.py test/test_state_relocation_local_preflight.py test/test_identity.py test/test_constitution*.py test/test_configuration.py -q` — **131 passed, 14 skipped** in 294.81s (skips are host-conditional, e.g. Linux-only runtime paths) |
| Dup-writer/engines/identity verification | verified | audit section above |
| Ruff lint on new files | PASSED | `ruff check src/sofia/run/doctor.py test/test_run_doctor.py` — All checks passed |

Mapped original tasks (audit-only, no completion claims): CA-6804 canonical
SQLite protection (already tested, 6 tests), CA-3005 shutdown drain (3
tests), CA-3103 single-writer (relates), conversation ordering family
CA-4106/4110/5302/5306/5505 (9 tests present). Reconciliation continues;
destination labels follow UNIFIED_780_PLAN (these are PLATFORM/CORE-adjacent
verification anchors), mapped to CORE-35 substrate for doctor.

## B01 — Convictions and independent opinions (CORE-06)

Owner requirements: persistent convictions and opinions, Sofía-vs-owner
belief separation, evidence and counterevidence, confidence and
uncertainty, append-only revision history, compare-and-swap concurrency,
reconsideration and correction, source verification, contextual relevance,
privacy and audience isolation, actual conversation retrieval, restart
continuity, appropriately expressed disagreement.

Status: **pending**.

Source audit conclusion (OBSERVED): no conviction/opinion store exists
anywhere in `src/` (grep: `conviction` 0 production hits). Existing
substrates to reuse, not duplicate:
- `src/sofia/cognition/v2/evidence.py` `CognitiveEvidenceLedger` +
  `EvidenceGraph` (evidence atoms, corrections, truth maintenance);
- revision patterns: `src/sofia/life/store.py` `life_interest_revision`
  append-only revisions + `life_interest_learning` idempotency receipts;
  `src/sofia/personality/preferences.py` `PreferenceRegistry` CAS +
  audience scoping; `src/sofia/emotion/journal.py` `emotional_revisions`;
  `src/sofia/evolve/revision.py` reviewed revisions.
- application wiring points: `src/sofia/application/bootstrap.py` (stores
  and provider setters like `set_habit_continuity`,
  `set_communication_preference_provider`), background scheduler in
  `src/sofia/application/background_runtime.py`.

Planned design (must follow existing authority discipline; will produce a
change plan + tests before/with implementation):
1. `src/sofia/beliefs/` new package: model, store (canonical SQLite tables
   `belief_conviction`, `belief_conviction_revision` append-only),
   evidence links, reconsideration scheduling.
2. Holder separation: `holder ∈ {sofia, owner}` — owner-held positions are
   recorded attributions Sofía does not assert.
3. CAS revision writes; audience visibility (owner-private default).
4. Wire into composition at application layer; conversation-context
   retrieval provider (owner-scoped audience filtering).
5. Tests: store, CAS, privacy/audience, restart continuity, conversation
   wiring, injection refusal (no evidence → no conviction).

## B02 — Identity and personality evolution (CORE-21, CORE-13)

Status: **pending**. Existing: static `PersonalityProfile` JSON
(`src/sofia/personality/`), reflection journal
(`src/sofia/personality/reflection.py`) that records but never mutates
personality, trait-less profile (~57 static trait strings), protected
identity revision path only via `src/sofia/evolve/amendment.py`
(proposal-only, never auto-applied). Plan: trait-level evolution store with
evidence-backed revisions (reuse `PreferenceRegistry` pattern), trait
history/corrections, drift detection, expression integration; constitution
and identity floors unchanged unless separately owner-approved.

## B03 — Interests, hobbies, fulfillment (CORE-04, CORE-19, CORE-32, CORE-20, CORE-12)

Status: **pending**. Existing: substantially built LIFE module
(`src/sofia/life/`: `InterestRecord` with append-only
`life_interest_revision` + evidence verification + idempotency receipts,
`SelectionKind.INACTIVITY`, `MotivationSignal`, projects/forge/background
task). Gaps observed: no non-artifact hobby/leisure representation beyond
inactivity selections, no personal-fulfillment aggregate, no
interest decay/reinforcement over time, interest discovery only via
experience mining plus hardcoded keyword domains in
`background_runtime.py:133-141`. Plan: audit against owner batch text,
fill gaps with smallest correct changes, tests.

## B04 — Autobiographical memory (CORE-07, CORE-24, CORE-16)

Status: **pending**. Existing: MEM provenance stack is complete and
wired (`src/sofia/memory/`: provenance candidates, corrections,
`require_current_original_at_recall`, budgeted ranked recall;
`application/memory_review.py` reviewer service;
`application/conversation_learning.py` deterministic admissions).
Gaps observed: no episode narrative/consolidation, no first-class
autobiographical timeline/milestone recall beyond LIFE milestones and
emotion-journal milestones, no episode-to-memory consolidation path
(`generalization/advanced.py` episodes disconnected from MEM). Plan:
significant-experience selection and timeline recall over promoted
memory + life experiences, with provenance protections; no invented
history (fail closed).

## B05 — Communication and personal habits (CORE-33, CORE-10, CORE-28)

Status: **pending**. Existing: habits engine
(`src/sofia/habits/`) covers conversation-routine/environment patterns
with confidence decay, suppressions, expectations; wired into
conversation via `conversation_service`/`conversation_matrix`;
owner style currently explicit-only (`personality/preferences.py`
`CommunicationPreferenceService`) plus hardcoded avatar shorthand map.
Gaps observed: no learned owner shorthand/typo/lexical pattern store, no
habit->language adaptation, PREFERENCE_PATTERN/RELATIONSHIP_ROUTINE
categories declared but unused. Plan: owner communication-pattern store
(confidence-scoped, evidence-limited), learned-expansion interpretation
in conversation, error-imitation protection, evolving humor hooks
without forced catchphrases.

## B06 — Relationships and independent agency (CORE-11, CORE-18, CORE-17, CORE-25, CORE-27, CORE-29, CORE-22, CORE-31, CORE-23)

Status: **pending**. Existing: rel store/nicknames, social
principal/audience session binding, session-local guarded affect;
PRESENCE initiative engine feeds ACT; GOALS(origins incl. SELF);
LIFE coordinator; autonomous work coordinator. Gaps observed: no durable
per-principal impression model (trust/respect/skepticism/dislike with
evidence), no relationship repair/apology record, no internal dilemma
resolution representation, no anticipation/surprise ledger distinct from
ACT categories, affect-to-durable promotion deliberately gated and written
nowhere. Deferred per owner: household multi-person recognition (CORE-34)
— post-Core only. Plan: impression store with evidence and privacy,
boundaries/refusal representation, repair/apology flow, anticipation Hooks
into PRESENCE/ACT policy.

## B07 — Modules and self-maintenance (CORE-35, CORE-36, CORE-37, CORE-38, CORE-39, CORE-40)

Status: **pending**. Existing: codebase inspector/analyzer (read-only,
one-shot), filesystem change observation capability, DEV/EVOLVE governed
candidate pipeline (detached worktree, verified gates, no self-approval),
OPS drift/repair/maintenance, run supervision and systemd unit,
`verify/` release gate, mentor system-parts inventory.
Gaps observed: no module manifest/registry (grep: none), no persistent
codebase inspection cache or source-change-driven re-analysis correlation,
no typed module health/lifecycle states, no in-process subsystem restart
supervision. Plan: `src/sofia/modules/` manifest validation + registry +
compatibility + health projection reusing CapabilitySystem/Gateway/SAFE;
discovery yields untrusted candidates only.

## B08 — Full system integration and acceptance

Status: **pending**. Will include Core-to-Desktop/Discord/2D-avatar
integration evidence, cross-channel privacy tests, Core-without-optional-
module tests, restart continuity, backup/restore, security review,
source-to-runtime verification, release-readiness assessment. Host
acceptance/deployment/CI remain owner-authorized steps; no claims without
execution.

## Blocking facts and decisions for the owner

- None currently blocking B00/B01 implementation; all owner-level host
  actions remain unauthorized and are tracked, not attempted.
- CI (L5) evidence awaits owner-authorized push of a checkpoint.

## Session continuation instructions

1. Work tree must be quiescent before any fetch: no active writes.
2. Read this ledger and `docs/sofia2/` plans; then audit the latest
   `git log origin/main` diff since last recorded SHA.
3. Resume at the first batch marked `in progress`/`pending` in the batch
   sections above, in B00→B08 order; audit any newer upstream code first.
4. Update this ledger after every implemented slice with real test
   commands and counts (never from memory).
