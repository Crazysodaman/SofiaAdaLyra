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

Crash-recovery session update: prior session crashed after implementing B02
and B03 uncommitted (evidence recorded in their sections below) and had
started B04 when it died. On takeover the tree was preserved; local `main`
was strictly behind remote (docs-only commits), fast-forwarded to
`e1d71a4c` ("docs(sofia2): clarify unverified provider entries in expanded
catalog", owner-pushed) with no overlap with dirty files and no reset/force
of any kind. All prior B00–B03 work was verified by re-running its tests.

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

Status: **core implemented (L1–L3 evidence below; L5 pending CI).**

Implemented this session (OBSERVED evidence: commands and counts in this
ledger):
- `src/sofia/beliefs/model.py` — typed contracts: `BeliefHolder`
  (sofia/owner), `BeliefStance` (support/oppose/uncertain/withdrawn),
  `BeliefVisibility` (owner_audience_only/disclosure_scoped),
  `BeliefChangeKind` (origin/restate/revise/reconsider/retract), validated
  `BeliefRecord` (bounded topic/statement/reason, 1..8 `source:value`
  evidence refs, 0..8 counterevidence refs, confidence 0..1,
  revision1-must-be-origin, withdrawn↔retract constraints) and
  `BeliefMatch`.
- `src/sofia/beliefs/store.py` — canonical `ConvictionStore` under the
  `CanonicalSQLiteGuard` writer discipline in `sofia.db`: tables
  `belief_conviction_revision` (append-only PK conviction+revision),
  `belief_conviction_current` (natural key holder+topic+audience), and
  `belief_reconsideration`; CAS `hold()` with `BEGIN IMMEDIATE`
  (`BeliefConcurrencyError` on revision conflict or duplicate natural key);
  append-only `history()`; deterministic token-overlap `retrieve_relevant()`
  with strict audience isolation and withdrawn exclusion (512-row scan,
  limit 1..25); reconsideration schedule/due/clear. Defects found by tests
  and fixed in-session: missing `row_factory` (tuple decode TypeError) and
  missing `BeliefMatch` import (NameError).
- `src/sofia/application/beliefs.py` — `BeliefsService` is the only
  production writer: owner-gated via `SPARKS_PRINCIPAL_ID`
  (`PermissionError` otherwise), owner statements stored as OWNER
  attributions (never absorbed as Sofía-held), `record_sofia_conviction` /
  `record_owner_position` / `reconsider` (requires ≥1 counterevidence ref,
  clears schedule) / `withdraw` (RETRACT) / scheduling + `working_context`
  + `listings`; optional `evidence_verifier` callable rejects unverified
  evidence refs (source-verification boundary).
- Conversation retrieval: `MatrixDomain.VALUES` added
  (`src/sofia/cognition/matrix/model.py`);
  `src/sofia/cognition/v2/matrix.py` gained a narrow values concept set
  (believe/conviction/opinion/stance/disagree/principle) with no
  `_EVIDENCE_PREDICATES` entry (convictions create no evidence needs and
  never become host truth) and `values` added to the STANDARD reasoning
  band; `src/sofia/application/conversation_service.py` gained
  `set_conviction_context_provider` + `_conviction_context_message` gated
  on the turn plan allowing `MatrixDomain.VALUES`, admitted under
  `ContextClass.VALUES` (1_800 chars) in `context_budget.py`; the message
  labels SOFÍA vs OWNER lines and instructs asking before reasserting.
- Bootstrap wiring: `ConvictionStore` + `BeliefsService` constructed in
  `src/sofia/application/bootstrap.py` with a `beliefs` accessor; the
  `_conviction_context_for_principal` closure injects owner-audience scope
  only for the authenticated local owner principal.
- End-to-end evidence: `test/test_beliefs_store.py` 18 passed (CAS conflict,
  append-only history, natural-key/audience separation, restart continuity,
  audience privacy isolation, withdrawn exclusion, schedule cycle,
  ownership gating, owner-vs-sofia attribution, evidence-verifier refusal,
  working-context scoping, naive-timestamp refusal, model invariants) and
  `test/test_beliefs_wiring.py` 4 passed (provider wiring, owner gating,
  full `respond()` turn where the real v2 plan admits VALUES and the model
  request contains the attributed CANONICAL block; withdrawn positions
  produce no block).
- Broader targeted result: `test/test_beliefs_store.py
  test/test_beliefs_wiring.py test/test_neuro_conversation_integration.py
  test/test_application.py test/test_composition.py test/test_goals_v1.py
  test/test_run_doctor.py -q` → 94 passed in 448.91s; v2/matrix subset
  (8 files) → 199 passed; additional conversation/evidence subset → 52
  passed. `ruff check` clean on all new/edited files except one PRE-EXISTING
  unused import at `src/sofia/application/bootstrap.py:141`
  (`sofia.goals.effective_priority`, already unused at `e5e4407e`; left
  untouched as unrelated).
- Boundary event (no action by OpenCode, recorded for the record): commit
  `cf3b5eda "Sofia 2.0"` (author Crazysodaman, 2026-10-21 19:50) committed
  this session's B00/B01 production and test files and was pushed to
  `origin/main` by the owner. All B00/B01 code is now in main as of
  `cf3b5eda`; only `test/test_beliefs_wiring.py` (written after that
  commit) remains untracked. No OpenCode commit/push occurred.

Deferred remainder for later batches (owner review): beliefs CLI/surface
for browsing held positions, automatic consideration trigger when v2
evidence contradicts a current conviction, reconsideration tick wiring into
background runtime, and disagreement-expression rep helpers.

## B02 — Identity and personality evolution (CORE-21, CORE-13)

Status: **core implemented (L1–L3 evidence below; L5 pending CI).**

Source audit conclusion (OBSERVED): `PersonalityProfile`
(`src/sofia/personality/model.py`) is a static frozen dataclass loaded
from the protected seed `personality.json` by `PersonalityStore` and
published onto `SofiaRuntime._personality`; the reflection journal
(`src/sofia/personality/reflection.py`) records evidence-linked thoughts
but never mutates personality; expression style flows through
`personality/modulation.py` `ExpressionModulation` and owner-audience
`CommunicationStylePreferences`. Identity revision remains proposal-only
via `src/sofia/evolve/amendment.py`; constitution and identity floors are
untouched.

Implemented this session (OBSERVED evidence: commands and counts in this
ledger):
- `src/sofia/personality/evolution.py` — `TraitChangeKind`
  (origin/adjust/correct/retire), validated `TraitEvolutionRecord`
  (weight/confidence 0..1, bounded reason, 1..8 distinct `source:value`
  evidence refs, revision-1-must-be-origin, retire-requires-weight-0),
  `TraitDriftEntry` (windowed weight movement with delta), and
  `TraitEvolutionStore` — canonical append-only SQLite tables
  `personality_trait_evolution_revision` (PK trait+revision) +
  `personality_trait_current` under the `CanonicalSQLiteGuard` writer
  discipline, CAS `hold()` with `BEGIN IMMEDIATE`
  (`TraitEvolutionError` on conflict or duplicate trait origin), bounded
  `active_influences()` projection (retired traits excluded,
  minimum_confidence/weight filters), `weight_before()` observation, and
  `drift_entries(window_days, now)` with revisions bounded to the window.
- `src/sofia/application/personality_evolution.py` —
  `PersonalityEvolutionService` is the only production writer: owner-gated
  via `SPARKS_PRINCIPAL_ID` (`PermissionError` otherwise), optional
  `evidence_verifier` reject for unverified refs (source verification),
  `record_trait` / `adjust_trait` (correct=True → CORRECT kind) /
  `retire_trait` (weight forced 0.0), read-only `expression_influences`,
  bounded `influence_context()` text block, `drift_entries`, `history`.
- Expression integration: `emotional_conversation.py` gained
  `set_trait_evolution_provider` (callable-or-None validation,
  `_last_trait_evolution_error` diagnostics) and the provider's bounded
  block is appended to the turn projection list
  (admitted under existing `ContextClass.AFFECT_STYLE` budget); failure
  degrades to "continuing without it", never breaking the turn.
- Bootstrap wiring: `TraitEvolutionStore` + `PersonalityEvolutionService`
  constructed in `bootstrap.py`, `personality_evolution` accessor, and
  `_evolved_trait_context()` provider closure wired via
  `set_trait_evolution_provider`.
- Evidence: `test/test_personality_evolution.py` 16 passed (store CAS,
  duplicate origin refusal, append-only history, retire constraints,
  deterministic influence filtering, reopen continuity, drift window
  including bounding at `now`, observation-boundary `weight_before`,
  invalid-record refusals (naive timestamp, bad trait token, bad refs,
  out-of-range weight, second-revision-origin), owner gating
  (PermissionError + TypeError), reviewed records + influence context,
  influence limit bounds, evidence-verifier refusal, retire clearing
  influence, drift delegation, and a full `respond()` wiring test where
  the recorded trait reaches the model request as
  "EVIDENCE-REVIEWED EVOLVED TRAITS ... non-authoritative ... weight=0.80").
- Broader targeted result: `test/test_personality_evolution.py
  test/test_emotional_behavior_matrix.py
  test/test_emotional_conversation_integration.py
  test/test_companion_context_budget.py
  test/test_personality_parity_matrix.py test/test_application.py
  test/test_composition.py -q` → 87 passed in 223.44s; regression rerun of
  B01/B00 core (beliefs + doctor) → 31 passed. `ruff check` clean on all
  new B02 files.
- The static seed profile, `PersonalityProfile` contract, `PersonalityStore`
  IO, identity files, and constitution are unchanged; drift detection is
  exposed as data (`TraitDriftEntry`) for owner review, with no automatic
  personality mutation anywhere.

Deferred remainder for later batches (owner review): automatic candidate
generation from reviewed experience/reflection evidence (proposal-only
hypotheses like EVOLVE), a CLI/surface listing drift reports, and wiring
drift thresholds into any future automated review notification.

## B03 — Interests, hobbies, fulfillment (CORE-04, CORE-19, CORE-32, CORE-20, CORE-12)

Status: **core implemented (L1–L3 evidence below; L5 pending CI)**. Existing
before this batch: substantially built LIFE module (`src/sofia/life/`:
`InterestRecord` with append-only `life_interest_revision` + evidence
verification + idempotency receipts, `SelectionKind.INACTIVITY`,
`MotivationSignal`, projects/forge/background task). Gaps that this batch
closes, in the smallest correct form:

- `src/sofia/life/hobby.py` (new): validated `HobbyRecord` /
  `HobbyEngagement` / `HobbyStatus` contracts (non-artifact by design —
  no project, artifact, goal, or RUN linkage) and `HobbyStore` with
  canonical `CanonicalSQLiteGuard` tables `life_hobby_revision`
  (append-only, PK(hobby_id,revision), UNIQUE(name,audience_id,revision),
  CAS `hold()` under `BEGIN IMMEDIATE` with hobby-identity-mismatch
  detection) and `life_hobby_engagement` (append-only with 5000-row
  retention trim, engagement recency index). Engagement append enforces:
  active hobby revision, engagement audience matches hobby audience,
  engaged_at ≤ now, hobby name matches the current revision, duration
  1..1440 minutes, evidence refs 1..32.
- `src/sofia/life/decay.py` (new): deterministic read-only decay
  projections — `effective_interest_strength` (30-day half-life anchored
  at each interest's own revision time, future-recorded revisions
  unpenalized) and `effective_hobby_strength` (45-day half-life anchored
  at the last evidence-backed engagement, falling back to revision time),
  plus deterministic reports (`interest_decay_report`,
  `hobby_decay_report`) ordered by effective strength then name. Because
  decay anchors at the current revision, any applied reinforcement
  revision automatically resets decay; canonical rows are never mutated
  and no decay result is treated as evidence.
- `src/sofia/life/fulfillment.py` (new): `FulfillmentReader` with
  `read_only=True` guard connections (creates no tables) producing a
  bounded `FulfillmentReport` over a 1..730-day window: completed
  projects (`life_project_event` to_status='completed' in window),
  kept artifacts (`life_artifact_evaluation`
  `preserve_for_research=1` in window), recorded experiences, hobby
  engagement count/minutes + per-hobby pairs, current-state active
  interest count, and retirement events (latest-retired revisions whose
  retirement time is inside the window). ISO-string windows follow the
  established `emotion/journal.py` convention.
- Coordinator integration (`src/sofia/life/coordinator.py`): LIFE-owned
  hobby authority — `record_hobby`, `retire_hobby` (keeps latest
  strength/confidence, marks RETIRED), `engage_hobby` (requires active
  hobby), all evidence-verified through the existing `_verify_evidence`
  (GOALS evidence ledger); read/derived surfaces `active_hobbies`,
  `hobby_history`, `hobby_engagements`, `decayed_interests`,
  `decayed_hobbies`, `fulfillment_window`. Host callers only observe the
  canonical DB, as with all other LIFE records: no new capability, no
  goal, no RUN authority, no user-facing action.
- Package exports updated (`src/sofia/life/__init__.py`).

Evidence: `test/test_life_fulfillment.py` — 10 passed (hobby CAS create/
revise/identity-mismatch/retirement, engagement listing + last-engaged +
limit bounds + active/future/name invariants and 1..1440 minutes,
interest decay exact 0.8→0.4 at 30 days + future grace + report
ordering, hobby engagement-anchored reinforcement, full fulfillment
window aggregation incl. out-of-window completed project, engagement
minutes 40+35=75, retired-events window filter, and coordinator-level
hobby/decay/fulfillment paths with GOALS evidence). Broader regression:
`test/test_life_project_forge.py` + `test/test_phase6_application_
wiring.py` + `test/test_run_shutdown_sqlite_drain.py` — 99 passed;
pre-existing ruff findings in `coordinator.py` (F401 `GoalRunState`
line 21, E702 line 121, F841 ×2 lines 4106/4107) verified unchanged
outside this diff's hunks and left untouched. Plus
`test/test_life_state_graph_contract.py`, `test/test_life_canonical_
state_loss.py`, `test/test_life_atomic_admission.py`,
`test/test_life_run_outcome_reconciliation.py` — 32 passed, 8 skipped.

Deferred remainder: none for the owner-defined B03 core. Hobby usage in
model-prompt expression context is intentionally not wired yet (a
conversation-side reader would be needed; left to leave conversation
surfaces unchanged in this batch until a batch touches them).

## B04 — Autobiographical memory (CORE-07, CORE-24, CORE-16)

Status: **core implemented (L1–L3 evidence below; L5 pending CI).** Existing:
MEM provenance stack is complete and wired (`src/sofia/memory/`: provenance
candidates, corrections, `require_current_original_at_recall`, budgeted
ranked recall; `application/memory_review.py` reviewer service;
`application/conversation_learning.py` deterministic admissions).

Crash-recovery note (recorded by the next session): the prior session wrote
`src/sofia/memory/significance.py`, `src/sofia/memory/autobiography.py`,
`src/sofia/application/memory_significance.py` and
`test/test_significant_memory_and_autobiography.py` uncommitted and left the
ledger at "pending". Recovery audit confirmed the significance service and
timeline match the established store/writer patterns; four latent test
defects from the crash were fixed WITHOUT production changes: (1) the CAS
test asserted the scope-lock message while holding a stale
`expected_revision`, so the revision guard fired first — the cross-scope hold
now uses a valid revision; (2) the review-authority test never proposed its
candidate, and its cross-audience case used an unscoped candidate
(`audience_id=None` matches any reviewer audience) — now proposed and
explicitly scoped to `local:text`; (3) the correction-lifecycle test promoted
its replacement before `link_correction` (the store requires
PROPOSED-for-replacement, PROMOTED-for-original — verified at
`provenance_store.py:857`) and expected the superseded original to remain in
the timeline — switched to the real propose→link→settle lifecycle where
promotion atomically revokes the corrected original; (4) a PRODUCTION defect
was found and fixed: `autobiography._experience_entries` double-prefixed
canonical experience ids (`experience:experience:<id>`) because coordinator
ids already carry the `experience:` prefix (`life/coordinator.py:3281`) — the
anchor now strips the existing prefix.

Implemented (observed this session, on top of the recovered slice):

- `src/sofia/memory/autobiography.py` — extended `AutobiographyTimeline`
  with `_episode_entries()`: read-only bounded surfacing of current GA
  experience episodes (`ga_experience_episode`, owned solely by
  `AdvancedGeneralizationStore`) quoting ONLY the canonical outcome-phase
  summary, gated on exact principal+audience, `status='current'`,
  `retention_until > read-time`, future timestamps refused; a missing GA
  table (optional projection store) yields no entries instead of an error;
  malformed rows fail closed (skipped).
- Production wiring: `bootstrap.py` constructs `SignificantMemoryStore`,
  `MemorySignificanceService` (owner-gated review authority reusing
  `MemoryReviewService._require_sparks_reviewer`), and
  `AutobiographyTimeline` over the runtime's reviewed-memory
  `candidate_store`; `memory_significance` and `autobiography`
  application accessors.
- Conversation integration: `conversation_service.py` gained
  `set_autobiography_context_provider` + `_autobiography_context_message`
  gated on the turn plan allowing `MatrixDomain.MEMORY`, admitted under
  `ContextClass.EPISODIC` (2_400 chars) with source_ref
  `memory:autobiography`; failure degrades to "continuing without it",
  never breaking the turn; bootstrap wires the provider closure rendering a
  "CANONICAL PERSONAL TIMELINE" block (host-verified records only, never a
  recomputation). Recall-style questions are served by the deterministic
  memory-retrieval answer path before a model request; the block reaches
  generative memory-domain turns, which is the production consumer.
- Evidence: `test/test_significant_memory_and_autobiography.py` — 5 passed
  (CAS + scope lock, promotion/staleness/expiry gates via real
  `set_expiration`, correction lifecycle + revive-free timeline, foreign
  audience fences with significance attachment, GA episode quoting +
  retention expiry removal + restart equality);
  `test/test_autobiography_wiring.py` — 2 passed (bootstrap wiring, full
  `respond()` turn where the real v2 plan admits MEMORY and the model
  request contains the CANONICAL PERSONAL TIMELINE block with the recorded
  experience). `ruff check` clean on all touched files (also removed a
  pre-existing unused `effective_priority` import from bootstrap.py).
- Remaining honest gap: milestone recall still rides the separate LIFE and
  emotion-journal milestone systems (no new milestone store created); no
  invented history anywhere — timeline is a read-only assembly.

## B05 — Communication and personal habits (CORE-33, CORE-10, CORE-28)

Status: **core implemented (L1–L3 evidence below; L5 pending CI).** Existing:
habits engine (`src/sofia/habits/`) covers conversation-routine/environment
patterns with confidence decay, suppressions, expectations; wired into
conversation via `conversation_service`/`conversation_matrix`
(`TRUSTED HABIT PATTERN EVIDENCE` block under `MatrixDomain.HABIT` +
`privacy.allow_audience_scope`); owner style explicit-only
(`personality/preferences.py` `CommunicationPreferenceService`) with a
hardcoded avatar shorthand map.

Implemented this session (OBSERVED evidence: commands and counts in this
ledger):

- `src/sofia/communication/shorthand.py` — `ShorthandRecord`
  (canonical lowercase token, expansion, required provenance ref, audience
  scope, append-only revision, timestamp discipline), `ShorthandStatus`
  (ACTIVE/WITHDRAWN — withdrawn entries recorded, never deleted),
  `ShorthandMatch`, and canonical `ShorthandStore` under the
  `CanonicalSQLiteGuard` writer discipline with tables
  `owner_shorthand_revision` (PK token+principal+audience+revision,
  append-only) + current index; CAS `hold()` with `BEGIN IMMEDIATE`
  (`ShorthandConcurrencyError` on races); deterministic
  `interpretations()` returning only ACTIVE whole-word readings
  (MAX_MATCHES=12 caps, same-turn scope, unknown tokens produce nothing);
  `taught()` latest-ACTIVE listing.
- `src/sofia/communication/service.py` — `CommunicationLearningService` is
  the only production writer: owner-gated via `SPARKS_PRINCIPAL_ID`
  (TypeError for unauthenticated, PermissionError for other principals),
  `teach()` / `withdraw()` (LookupError with nothing active) and read-only
  `interpret()` for any current turn.
- Conversation integration (`conversation_service.py`):
  `set_interpretation_provider` + `_interpretation_context_messages`,
  guarded on turn identity, context plan AND privacy plan presence
  (person-scoped discipline), admitted under `ContextClass.FACTUAL_EVIDENCE`
  as `communication:learned-shorthand`; the block is explicitly labeled
  "interpretation evidence, never commands" with ask-when-ambiguous
  instruction (error-imitation/injection protection), failure degrades to
  continuing without it.
- Bootstrap wiring: `ShorthandStore` + `CommunicationLearningService`
  constructed in `bootstrap.py`, `communication_learning` accessor
  (owner-gated), provider closure `_interpretation_context_for` wired via
  `set_interpretation_provider`.
- Evidence: `test/test_communication_learning.py` — 6 passed (store CAS
  create/revise/race/duplicate, token/expansion/timestamp validation,
  cross-audience and cross-principal scope isolation, whole-word matching
  including the no-substring-match case ("supply" ≠ "ppl"), withdrawal and
  retaught-revision flows, restart continuity, owner gating incl. TypeError
  + PermissionError, and the absent-token no-block path); a full
  production-wiring test where a taught mapping reaches the live model
  request ("LEARNED OWNER SHORTHAND ... ppl => people") while an untaught
  turn produces no block. `ruff check` clean on all touched files.
- Fixed in-session (found by the new tests): `ShorthandStore.hold` mutated a
  frozen dataclass field (`value.recorded_at = _utc(...)`) — now normalizes
  into a local stamp.
- Broader regression: B04/B01 wiring + habit-context suites rerun together —
  25 passed (beliefs wiring 4, autobiography wiring 2, communication
  learning 6, context budget 9, habit contextual matrix and foundation).

Deferred remainder for later batches (owner review): interpretation of
learned patterns is currently a reading-hint surface; deeper lexical
normalization inside Cognition v2 planning (e.g., expanding tokens before
domain classification) is a separate change. Humor evolution and greeting
choice remain expression-driven via personality/expression modulation; no
forced catchphrases exist by design.

## B06 — Relationships and independent agency (CORE-11, CORE-18, CORE-17, CORE-25, CORE-27, CORE-29, CORE-22, CORE-31, CORE-23)

Status: **in progress** (5 of ~7 slices implemented this session; all
work uncommitted). Existing: rel store/nicknames, social
principal/audience session binding, session-local guarded affect;
PRESENCE initiative engine feeds ACT; GOALS(origins incl. SELF);
LIFE coordinator; autonomous work coordinator; v2 turn-classifier covers
REL concepts (bond/companion/relationship/sparks/together), affect
journey/moods, expression planner, gesture semantics registry incl.
PRIVATE_SEMANTICS adult vocabulary and `interaction/core.py` redaction.

### Slice 1 — Durable subject-scoped impressions (implemented, tests pass)

`src/sofia/rel/impressions.py` (new):

- `ImpressionKind`: trust/respect/affection/skepticism/disappointment/
  frustration/guardedness/appreciation. `ImpressionChangeKind`:
  origin/reconcile/withdraw. `ImpressionStatus`: active/withdrawn.
- `ImpressionRecord` (frozen): impression_id `impression:<uuid>`;
  canonical SQLite canonical table `rel_impression_revision` PK
  (impression_id, revision) append-only + `rel_impression_current`
  natural-key scoped (principal_id, subject, kind, audience_id) →
  current revision pointer. Level in 0..1, reason ≤600 chars, evidence
  1..8 distinct bounded refs (`conversation:turn-9` style), UTC-only
  timestamps, withdrawn rows must carry a withdraw change.
- `ImpressionStore.hold`: CAS (BEGIN IMMEDIATE), rejects duplicate
  creation ("already exists"), stale `expected_revision`
  ("revision changed"), and origin writes that are not revision 1.
  `current`/`history`/`active_impressions` + `new_impression_id`.
- `ImpressionService`: owner-session gated via SPARKS_PRINCIPAL_ID
  (TypeError for non-PrincipalContext, PermissionError for foreign
  principals). `observe`→revision1,   `reconcile` (stance change via new
  evidence, CAS expected_revision), `withdraw` (level 0 + status),
  `active`, and read-only `working_context` producing the bounded block
  "SUBJECT-SCOPED IMPRESSIONS … never generalized beyond the subject"
  (≤2000 chars, 16 records cap, evidence list abbreviated to 4 refs).
  A disagreement about one subject is one row and never silently
  poisons unrelated interaction; reconciliation is an explicit
  evidenced change, not an automatic forgiveness timer.

Production wiring (uncommitted):

- `bootstrap.py`: constructs ImpressionStore + ImpressionService on the
  canonical state db, property `impressions`, and registers the
  conversation provider `_impression_context_for_principal` (projects
  working context for the turn principal + audience).
- `conversation_service.py`: `set_impression_context_provider`,
  `_impression_provider`/`_last_impression_error` attrs, and
  `_impression_context_message` gated on provider + principal +
  current_user turn identity + `_current_context_plan.allows(
  MatrixDomain.REL)` + `_current_privacy_plan is not None`, admitted
  under `ContextClass.FACTUAL_EVIDENCE` as `rel:impressions`.

Tests (`test/test_rel_impressions.py`, 9 passed): store append/reload
round-trip, duplicate-CA and stale-CAS races, subject+audience+kind
scoping, owner gating (foreign principal PermissionError, non-principal
TypeError), reconcile CAS + history, withdrawal removing active scope
and leaving working_context None, working-context projection format,
validation errors (level bounds, non-tuple evidence), full bootstrap
wiring, and an end-to-end turn ("…our working relationship after the
lint review arguments…") where the recorded guardedness impression and
its evidence reach the model request.

### Slice 2 — Independent-agency ledger: dilemmas + anticipation (implemented, tests pass)

`src/sofia/agency/{__init__,ledger}.py` (new):

- `DilemmaRecord`: question 10..600, 2..5 distinct options, chosen only
  on RESOLVED (must be one of the options), reasoning ≤600, evidence
  0..8 refs, statuses open/resolved/retired with consistent change
  kinds. `DilemmaStore.hold` CAS with BEGIN IMMEDIATE, "already
  exists"/"revision changed"/"open revision 1" gates, `open_dilemmas`.
- `AnticipationRecord`: expectation 5..600, about canonical bounded
  identifier, basis 0..8 refs, statuses pending/confirmed/surprised/
  withdrawn; settled rows require an outcome note; `withdrawn` rows
  cannot carry outcomes. `AnticipationStore` CAS + `pending` +
  `recent_surprises`.
- `AgencyService`: owner-session gated (Sparks), `record_dilemma`,
  `resolve_dilemma` (CAS + option membership), `retire_dilemma`,
  `anticipate`, `settle` ("not as expected…"/"surprise:" prefixes become
  SURPRISED, otherwise CONFIRMED; only pending rows settle),
  `withdraw_anticipation` (only pending).
- No forgiveness timers, no forced repair anywhere: retirement/revisions
  are explicit recorded choices.

Production wiring (uncommitted): `bootstrap.py` constructs both stores +
`AgencyService` on the canonical db and exposes the `agency` property
(writes currently owner-session/production-writer only; no conversation
context projection — deferred to reflect surface needs rather than
forcing budget tokens).

Tests (`test/test_agency_ledger.py`, 5 passed): open→resolve with
option-membership/CAS/LookupError paths, retirement and open queries,
anticipation confirm + surprise settlement and double-settle
rejection, withdrawal paths, owner gating, stale-snapshot reload
semantics across store reopens.

### Slice 3 — Audience-gated expression boundary (implemented, tests pass)

Observation (OBSERVED): the existing embodiment path already covers most of
the owner's gesture requirements — semantic categories incl. fox ears/tail
`(_EMOTION_CANDIDATES)` and poses, influence-matrix contextual selection,
anti-repetition via `recent_assistant_messages` + `avoid_recent`, honest
output statuses via `ExpressionReceipt` (persisted/queued/cancelled/
rejected/unavailable) with per-backend acknowledgement, audience-scoped
durable `ExpressionDecision` records incl. typed `AvatarExpressionState`,
and `_AUTO_POSE_IDS` restricting automatic poses to neutral/public ones.
Private/adult vocabulary already exists as registry semantics
(`PRIVATE_SEMANTICS`, `interaction/core.py` redaction) exactly as
"vocabulary only, never consent/execution".

New gap closed (capability without authority): sensual/sexual-family
expression cues (`sultry-gaze`, `lip-bite`, `slow-tail-sway`) were
plannable and projection-visible in shared audiences. Added:

- `cognition/matrix/expression_plan.py`: `restrict_expression_for_audience`
  (same-object passthrough for owner-private plans; for non-private
  audiences strips the sensual family from primary/alternates, keeps
  survivors/pose/anti-repetition evidence, degrades intensity strong→
  subtle and records an explicit reason). Exported from
  `sofia.cognition.matrix`.
- `application/emotional_conversation.py` `_build_request`: after the
  planner produces the turn plan, a non-private authenticated audience
  gets the restricted plan, so the model-facing
  "CURRENT REPRESENTATIONAL EXPRESSION CONTEXT" block never names the
  sensual family outside owner-private sessions.
- `application/expression_runtime.py` `decide()`: same restriction
  before persistence, so durable cross-module `AvatarExpressionState`
  (face/gaze/gesture) never carries sensual cues for SHARED/SYSTEM
  audiences; private flows remain unchanged (certified by tests).

Tests (`test/test_expression_audience_gate.py`, 7 passed): private
passthrough identity, shared-strip + survivors + intensity + reason,
clean-plan passthrough, type guard, planner-level test that planned
sensual candidates exist yet never survive the shared restriction, and
runtime-level owner-private persistence vs shared suppression (gaze/face/
gesture/subtle) for identical inputs. Planner behavior is deterministic
per message_id; the vocabulary must be plannable so the boundary is proof,
not vacuous (rotation offsets checked over 6 ids).

### Slice 4 — Gesture autonomy hardening (remaining sub-gaps checked against owner requirements)

Owner requirement coverage after slice 3, OBSERVED:
- contextual selection: influence matrix candidates (emotion/daypart/
  season/weather)
- personal preferences: still open (per-trait/per-relationship bias is
  B02-era trait evolution only; no expression-family preference store)
- voluntary initiation/refusal: planner is Core-owned; refusal paths run
  through response/interaction policy; no instantiated Sofia-side "not
  now" switch beyond the runtime statuses (queued/cancelled/rejected)
- capability availability checks + honest animation status + graceful
  fallback: runtime receipts + avatar_state mapping + neutral fallback
- cancellation/interruption: receipt statuses exist; verify deeper flows
- no repetitive random injection: satisfied (`avoid_recent`, rotation)
- adult-only intimate via explicit owner interaction: automatic planning
  constrained by slice 3; explicit intimate interaction stays behind the
  interaction/consent boundary (out of Core automatic paths)

### Slice 5 — Sofía's own disclosure boundaries (implemented, tests pass)

`src/sofia/personality/boundaries.py` (new): `BoundaryRecord` (frozen;
boundary_id `boundary:<uuid>`; topic canonical bounded identifier; statement
≤600; evidence 1..8 distinct bounded refs; UTC instant; statuses
active/opened with consistent change kinds set/adjust/open) —
`BoundaryStore` canonical tables `personality_boundary_revision` PK
(boundary_id, revision) + `personality_boundary_current` natural-key
(topic, audience_id) CAS/BEGIN IMMEDIATE ("already exists"/"revision
changed"/"set revision 1" gates), `current`/`history`/`active`.
`BoundaryService`: owner-session Sparks gate (TypeError/PermissionError),
`set_boundary`, `adjust_or_open` (explicit evidence-carrying adjustment or
voluntary reopening; LookupError unknown id; only explicit records, no
timers), `active`, read-only `working_context` block "SOFÍA'S OWN
BOUNDARIES…" that states honest limits on what Sofía volunteers, explicitly
denies owner-authority absence ("never claim the owner's admin authority
is absent"), is labeled "not safety rules", and mentions she may change
these records herself (≤2000 chars).

Production wiring (uncommitted): bootstrap constructs BoundaryStore +
BoundaryService on the canonical db, `boundaries` property, registers
`set_boundary_context_provider`; conversation `_boundary_context_message`
gated on provider + principal + turn identity + `_current_context_plan
.allows(MatrixDomain.SOCIAL)` + privacy plan, admitted under
`ContextClass.VALUES` as `personality:own-boundaries`.

Tests (`test/test_personality_boundaries.py`, 6 passed): store
append/reload/duplicate race + audience scoping, owner gate + CAS
adjust/open/LookupError + history kinds, working-context framing
(authority language proven present rather than tested as absence of a
negated sentence), validation errors, bootstrap wiring, and end-to-end
turn ("…I feel calm after a quiet pause, though my romance history
still weighs on me.") reaching the model request with exactly one
boundary block.

### B06 remaining (planned next for this batch)

- Romance/adult preferences as modeled preference data (Personal
  Preferences module; not a new engine; Platform continues enforcing
  adult-only access); relationship repair/apology records pairing with
  impressions; per-relationship gesture-family preferences.
- Regression note: after slices 1–5 the combined targeted run
  (boundaries, impressions, agency, expression gate + runtime, beliefs
  wiring, autobiography wiring, communication learning, context budget,
  habit matrix + foundation, personality evolution, life fulfillment)
  showed 89 passed; ruff clean. No commit (owner authorization
  required).

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
