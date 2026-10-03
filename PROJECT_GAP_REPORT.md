# Sofía Ada Lyra — Project Gap Report

**Audit date:** 2026-10-02  
**Audited branch:** `main`  
**Current repository head during audit:** `05e4b82ba3c6912e00b24ec452cc6dec7ee69b4e`  
**Last code-bearing head before the documentation-only audit commits:** `57b76f41aa2c70da28be4b05368de8606761b3fb`

This report answers one question:

> **What is still missing from Sofía after inspecting the current code, not just the roadmap?**

It distinguishes:

- **implemented** — production code exists;
- **partial** — important contracts/code exist but the end-to-end mechanism is incomplete;
- **documented only** — accepted design exists in Markdown but not runtime code;
- **missing** — no production implementation found;
- **unverified live** — code exists, but repository evidence does not prove the real deployed system currently works.

---

# Executive summary

Sofía has a substantial architecture. The major gaps are no longer “missing packages.” They are concentrated in:

1. **current verification is red;**
2. **CI can hide a failed package;**
3. **main is not branch-protected;**
4. **the matrix system is still partly shadow/safe-rollout rather than fully controlling context/tool exposure;**
5. **the new matrix roadmap is documented but not implemented;**
6. **runtime/Fleet processes lack durable OS-service packaging;**
7. **backup and restore are contracts/evidence only, not a backup system;**
8. **State Plane is local SQLite only;**
9. **failover has guards but no real witness/quorum/replication mechanism;**
10. **general distributed workers and a general workload backend do not exist;**
11. **release verification exists but the reproducible build/lock/SBOM/provenance pipeline does not;**
12. **cross-platform and Python-version CI coverage is incomplete;**
13. **voice and graphical avatar rendering are absent;**
14. **several “autonomy/personality” systems are only partially wired into production choices.**

---

# P0 — current correctness and trust gates

## 1. Full verification is currently failing

The last completed full verification on the last code-bearing head `57b76f4` reported:

```text
15 failed
3304 passed
6 deselected
accepted=False
```

The failures fall into three groups.

### 1A. Provider regression tests incorrectly reach real model lifecycle

Several tests monkeypatch provider response behavior but the composed application still calls model lifecycle readiness and attempts to use the configured Ollama models.

Observed failures include:

```text
CognitiveEngineError:
configured primary model could not be made ready
```

and secondary-model readiness failure.

**Needed:**

- isolate the model-lifecycle boundary in non-integration tests;
- use a deterministic lifecycle/provider double;
- prove the non-integration suite cannot require live Ollama;
- keep separate live canaries for real Ollama.

### 1B. Idle-reflection application test fixtures are stale

The test application builds a minimal configuration with only `state_path`, but startup now expects `configuration.fleet_discovery`.

Observed:

```text
AttributeError:
SimpleNamespace has no attribute fleet_discovery
```

**Needed:**

- update the test fixture to construct the real configuration contract or a complete typed test configuration;
- avoid fragile ad-hoc `SimpleNamespace` configuration doubles for production startup tests.

### 1C. One exact-string network assertion is stale

Production fallback wording changed while the test still expects the old sentence.

**Needed:**

- decide the canonical grounded fallback;
- assert semantic contract instead of brittle prose where appropriate.

---

## 2. Package CI masks failures

`.github/workflows/package-tests.yml` currently contains:

```yaml
continue-on-error: true
```

The latest completed package run for `57b76f4` had:

- `pkg_core` — **failed**
- the other 20 package jobs — passed
- the overall workflow — **success**

That means a green Package Tests badge is not currently trustworthy.

**Needed:**

- remove `continue-on-error: true`, or add a final mandatory aggregator that fails if any package failed;
- make package CI a real merge/release gate.

---

## 3. `main` is currently unprotected

GitHub reports the `main` branch as:

```text
protected: false
```

**Needed:**

At minimum require:

- full verification;
- matrix gate;
- package gate;
- no force push;
- no deletion.

Because the project intentionally works directly on `main`, branch protection matters even more.

---

# CLOSED — matrix architecture findings

**Closed 2026-10-02.** The matrix architecture gaps identified by the original report are implemented on `main`. The dedicated Matrix Tests closure gate passed **405/405** on commit `130aa735`; later commits in this documentation cleanup are descendants of that green code revision.

## 4. M1 Capability / Tool Exposure — closed

The matrix now owns bounded capability/tool-family exposure. Exact tool definitions are still filtered by host authority, and provider/LLM output cannot widen the allowlist. Desktop/Discord/Terminal parity is covered, and bounded provider-context projection preserves `capability_allowlist` and route controls.

## 5. M2 Principal / Audience / Privacy — closed

A first-class privacy projection exists. Authenticated principal/audience state is authoritative over user prose. REL/HABIT/history/private presentation paths remain scoped by their authoritative stores/grants, with negative cross-audience and cross-principal REL leakage coverage.

## 6. M3 Contextual Influence — closed

The shared influence set is implemented as typed signals/surfaces/modes:

```text
emotion
weather
time/daypart
season
```

Active influence requires provenance/freshness/grounding. Context Matrix exclusions prevent later EMOTION/ENVIRONMENT re-injection. Wardrobe autonomy, reflection weather, seasonal theme, HABIT environmental/seasonal correlation, bounded contextual memory reranking, interaction willingness/expression, and Voice prosody foundations use the reviewed surface policy.

Contextual influence remains non-authoritative and returns NONE for SAFE/authority, factual truth, release verification, Fleet authority/fencing, DEV correctness, protected-state approval, and BODY safety.

## 7. M4/M5 semantic domain expansion — closed

`MatrixDomain` includes first-class REL, HABIT, DEV, KNOW, INTEGRATE, BODY, and VOICE ownership where relevant. SAFE and VERIFY remain cross-cutting rather than ordinary conversation domains.

## 8. Context Matrix authority — closed for reviewed paths

Domain projection is authoritative across NONE, LAST_TURN, TOPIC_WINDOW, BOUNDED_RECENT, and RETRIEVE_SPECIFIC policies. LAST_TURN follow-ups inherit only contextual semantic relevance from the immediately preceding turn, not evidence or authority. Negative history-filtering tests prove excluded domains disappear from provider-visible context.

## 9. Continuity influence bypass — closed

`EmotionalConversationService` and `SofiaRuntime` both enforce Context Matrix EMOTION/ENVIRONMENT eligibility. A direct runtime caller cannot bypass exclusions by supplying a full `ContinuityInfluence`.

## 10. M6/M7 release/Fleet matrices — closed

M6 implements release/schema/Fleet compatibility across revision/version/schema/protocol/agent/model/assets/Constitution/signature/lineage/anti-rollback dimensions, including compatible rollback coverage.

M7 implements typed host/workload/failure/disposition recovery rules with exhaustive state-space coverage and fail-closed promotion requirements for state verification, fencing, and witness evidence.

See `MATRIX_ROADMAP.md` and `CONTEXTUAL_INFLUENCE_AUDIT.md` for the maintained implementation contracts.

# P1 — runtime/service reliability

## 11. Main Sofía runtime service installation is missing

Current RUN code has:

- local lease;
- supervisor;
- restart/backoff;
- readiness;
- service start/stop adapter;
- release rollback hook;
- standalone `python -m sofia.run.host`.

But the repository does not contain a current Windows ServiceFramework/service installer for the main Sofía runtime.

`LocalServiceRuntimeBackend` assumes a service named `SofiaAdaLyra` already exists.

**Needed:**

- install/uninstall runtime service;
- configure the exact active-release executable;
- automatic startup;
- service recovery;
- upgrade handling;
- current-service command verification.

---

## 12. RUN watchdog itself is not installed as a durable service

`python -m sofia.run.host` is a foreground watchdog host.

There is no current repo implementation that installs that watchdog as an independent Windows service.

**Needed:**

- durable watchdog host;
- independent startup;
- independent logging;
- recovery if the watchdog itself crashes;
- verification that it does not depend on the process it supervises.

---

## 13. Windows Fleet bootstrap is a verified canary process, not durable service installation

The Windows Fleet bootstrap is substantial and verifies:

- wheel hash;
- cert/config files;
- Python environment;
- imports;
- agent config;
- listener;
- process identity;
- bootstrap receipt.

However it starts the agent using PowerShell `Start-Process`.

It does not currently install the Fleet agent as:

- a Windows service;
- a scheduled startup task;
- another reboot-persistent service manager unit.

**Needed:**

- durable Fleet-agent service install;
- automatic restart;
- boot persistence;
- service upgrade/rekey support;
- install-state verification.

---

# P1 — backup, restore, replication and failover

## 14. There is no real backup engine

No production backup/restore implementation was found in the repository.

`src/sofia/ops/recovery.py` defines:

- `BackupEvidence`;
- `RestoreVerification`;
- `RecoveryGuard`.

Those are useful contracts, but they do not create a backup or restore one.

**Needed:**

- consistent SQLite snapshot;
- protected-state snapshot;
- release-state snapshot;
- independent failure-domain destination;
- encryption/access policy;
- retention;
- rotation;
- restore command;
- restore rehearsal;
- semantic post-restore verification.

---

## 15. No replicated State Plane

Current authoritative State Plane implementation is:

```text
SQLiteStatePlane
```

No second backend such as replicated PostgreSQL/SQLite consensus/etc. is implemented.

**Needed:**

- independent replica;
- replication protocol;
- freshness/lag evidence;
- writer election/lease;
- cross-host fencing;
- partition behavior;
- stale-primary rejection;
- failover;
- failback;
- measured RPO/RTO.

---

## 16. Failover currently trusts supplied evidence, not an implemented witness system

`PromotionGuard` requires fields such as:

```text
state_verified
source_fenced
witness_quorum
```

but those are values supplied to the guard.

No production witness/quorum service was found that independently proves them.

**Needed:**

- witness service(s);
- signed/attested fencing evidence;
- quorum collection;
- stale writer detection;
- promotion receipt;
- recovery after network partition.

---

## 17. Schema migration has registry/lease contracts but no general migration runner

Current code provides:

- `MigrationStep`;
- `SchemaRegistry`;
- migration lease/fencing;
- component schema registry;
- migration audit rows.

That is a strong foundation.

What is missing is the production executor that:

- plans a registered path;
- acquires migration lease;
- runs each migration;
- validates data;
- advances component/schema metadata;
- performs rollback/recovery when possible;
- emits verification evidence.

---

# P1 — release/build supply chain

## 18. Release trust exists; release construction does not

Release code already models and verifies:

- exact Git revision;
- dependency-lock digest;
- SBOM digest;
- provenance digest;
- schema window;
- Fleet protocol/agent version;
- Constitution hash;
- artifact/model/asset digests;
- Ed25519 signatures;
- lineage;
- anti-rollback.

But the repository contains no:

- dependency lock file;
- generated SBOM;
- generated build provenance artifact.

And `pyproject.toml` leaves most dependencies floating:

```text
ollama
pypdf
cryptography
tzdata
```

Only `discord.py` is exactly pinned.

**Needed:**

- lock dependencies and hashes;
- reproducible wheel/build;
- SBOM generation;
- provenance generation;
- manifest builder;
- signing workflow;
- immutable release packaging;
- release verification command;
- canary deployment;
- staged Fleet rollout;
- convergence proof.

---

# P1 — CI coverage

## 19. CI only tests Windows + Python 3.12

Current workflows use:

```text
runs-on: windows-latest
python-version: 3.12
```

That does not prove compatibility with:

- Linux/Terra-class hosts;
- Debian/Eos-class hosts;
- Raspberry Pi/Linux agents;
- Python 3.14 on Artemis.

**Needed:**

A compatibility CI matrix such as:

```text
Windows  + Python 3.12
Windows  + Python 3.14
Linux    + Python 3.12
Linux    + Python 3.14
```

Platform-specific tests should be marked appropriately rather than skipped accidentally.

---

## 20. GitHub Actions versions are producing Node deprecation warnings

Current runs report Node 20 deprecation warnings for several action versions.

This is not a current correctness failure, but it is maintenance debt.

**Needed:**

- move to action versions that target the supported Node runtime before GitHub removes compatibility.

---

# P1/P2 — Fleet and distributed execution

## 21. Fleet discovery needs real heterogeneous acceptance

The discovery/enrollment/bootstrap code is extensive.

Still unproven from repository evidence:

- Artemis sustained discovery/enrollment;
- Windows reboot persistence;
- Linux install/enrollment;
- Raspberry Pi install/enrollment;
- duplicate identity rejection;
- spoofed endpoint rejection;
- rekey/rotation on real hosts;
- removal/decommission approval path under live conditions.

---

## 22. Fleet monitoring is not yet a complete closed loop

Code exists for:

- telemetry;
- history;
- desired state;
- drift;
- maintenance requests;
- placement;
- recovery/failover contracts.

What is still needed is one production loop that continuously demonstrates:

```text
observe
→ persist
→ compare desired state
→ detect drift/problem
→ choose reviewed repair
→ authorize
→ execute
→ verify
→ receipt
→ notify
```

without broad shell execution.

---

## 23. General distributed workers are missing

The distributed package contains a real remote agent and a remote Ollama inference worker.

That is not yet a general distributed task system.

There is no general production equivalent of:

```text
Task
→ scheduler
→ durable lease
→ eligible worker
→ execution
→ heartbeat
→ result/receipt
→ retry/recovery
```

**Needed:**

- typed work item;
- scheduler;
- worker registration;
- task leases;
- heartbeat;
- cancellation;
- timeout;
- retry;
- durable results;
- idempotency;
- recovery.

---

## 24. Workload migration lacks a real general backend

`MigrationOrchestrator` already owns the correct orchestration sequence.

The actual workload executor remains a `WorkloadBackend` protocol.

**Needed:**

Concrete backends, for example:

- Docker/Portainer workload backend;
- Windows-service backend;
- process backend where appropriate;
- VM backend only where explicitly supported.

Each backend needs:

- drain;
- checkpoint;
- start;
- readiness;
- fence;
- stop;
- receipt verification.

---

## 25. Full runtime mobility remains missing

Sofía cannot yet safely move her authoritative runtime from one machine to another.

That requires the preceding work:

- replicated State Plane;
- authoritative writer fencing;
- backup/recovery;
- service packaging;
- release compatibility;
- Fleet failure matrix;
- channel rerouting.

Only then can a new host prove it is the single current Sofía runtime.

---

# P1/P2 — personality/autonomy integration

## 26. Context-aware wardrobe autonomy — closed

User-requested clothing changes are suggestions, not direct presentation commands. `WardrobeAutonomyPolicy` receives trusted contextual influence and may accept, decline, or counter-propose. Privacy/grant/coverage constraints dominate, and only an accepted persisted transition may be described as completed.

---

## 27. Reflection weather wiring — closed

Reflection receives evidence-backed current weather together with modeled emotion, trusted daypart, season, and daylight. Stale/future weather is rejected as current influence.

---

## 28. Seasonal adaptive theme — closed

`ThemeSignals` includes season as a bounded visual cue. Accessibility/contrast remains dominant over all adaptive styling.

---

## 29. HABIT environmental/seasonal learning — closed

HABIT learning includes seasonal cadence and environment/weather/daylight correlations with stronger evidence and observation-coverage requirements for sparse signals. Sofía's emotion does not become evidence that a user's habit exists.

---

## 30. Bounded contextual memory salience — closed

Reviewed memory retrieval keeps hard eligibility first:

```text
PROMOTED
+ principal/audience allowed
+ explicit query relevant
        ↓
bounded contextual tie-break
        ↓
final projection
```

Emotion/weather/daypart/season may only weakly rerank already-eligible memories when their matrix evidence is valid. Context cannot promote/create/rewrite a memory, expand scope, or make an otherwise irrelevant memory eligible.

---

## 31. Interaction willingness vs expression — closed

Separate typed influence surfaces now enforce:

```text
willingness:
  emotion = bounded
  weather = none
  daypart = none
  season = none

expression:
  emotion = bounded
  weather/daypart/season = expression-only
```

Explicit stop/boundary state remains dominant; ambient context cannot manufacture consent.

# P2 — proactive behavior

## 32. Canonical interaction initiative planner exists but is not production-wired

`CanonicalInitiativePlanner` and `InitiativeSource` exist.

No production application wiring was found that regularly invokes it from:

- emotion;
- reflection;
- relationship;
- HABIT.

**Needed:**

- reviewed proposal generator;
- frequency/cooldown policy;
- privacy/audience checks;
- stop/boundary check;
- no automatic execution;
- optional renderer/text realization only after accepted proposal state.

---

## 33. Goal delivery exists, but production goal creation is incomplete

`GoalJournal` supports:

- creating goals;
- transitions;
- selecting next goal;
- queueing messages.

`SofiaActService` can deliver pending goal messages.

But current application bootstrap visibly wires reflection outreach, not a complete production goal-generation/activation loop.

**Needed:**

- source-backed goal proposal;
- review/activation policy;
- contextual priority;
- bounded generation;
- completion/cancellation handling;
- ACT receipt linkage.

---

# P2 — cross-platform security

## 34. Protected secret store is Windows-only

`ProtectedSecretStore` is explicitly backed by Windows DPAPI.

That is good for Windows.

It does not provide an equivalent production secret backend for Linux.

This matters if the authoritative Sofía runtime or integrations move to Terra/Linux later.

**Needed:**

- Linux secret provider, for example system keyring/libsecret or another reviewed host keystore;
- migration/import path that never exposes plaintext broadly;
- backend-neutral secret-store interface;
- tests proving secret isolation.

---

# P2/P3 — interfaces and embodiment

## 35. Voice is missing

No production implementation was found for:

- microphone input;
- STT;
- TTS;
- VAD;
- interruption/barge-in;
- audio device routing;
- voice channel parity.

---

## 36. Graphical avatar renderer is missing

AVATAR has strong state/wardrobe/appearance logic.

No production renderer was found for:

- 3D model loading;
- VRM/GLTF/FBX;
- skeleton/rig;
- expressions/blendshapes;
- lip sync;
- animations;
- clothing mesh transitions;
- live viewport;
- renderer receipts.

The MPFB/Blender model work belongs here.

---

## 37. Gaia physical embodiment remains a future production system

BODY includes controller/model/safety/SSC-32 foundations.

Still needed:

- final servo inventory;
- calibration;
- IK;
- gait planner;
- balance/body pose;
- sensor feedback;
- motion scheduler;
- hardware e-stop;
- physical authority;
- real execution receipts;
- failure recovery.

---

# P2/P3 — integration/live acceptance

## 38. Code existence is ahead of live integration proof

The repository contains adapters/capabilities for systems including:

- Home Assistant;
- JMRI;
- Portainer;
- Hyper-V;
- GitHub;
- Ollama;
- storage/NAS;
- Discord;
- local system maintenance.

For several of these, unit/integration code exists but repository evidence cannot prove the real configured deployment is currently healthy.

**Needed:**

- named live canaries;
- timestamped evidence;
- permission/authority proof;
- negative tests;
- recovery test.

---

## 39. ChatGPT history import live state is not provable from the repository

Import/migration code exists.

The repository cannot establish whether the complete owner export has been imported into the canonical production DB.

**Needed:**

- production import receipt/status;
- counts and source hashes;
- duplicate/replay proof;
- principal/audience scope verification.

---

# P3 — optional/deferred product surfaces

## 40. General web/search is not implemented in Sofía

ENVIRONMENT has narrow external providers.

There is no general-purpose web/search/browser capability.

This should remain deferred until authority, privacy, reliability, and receipts are stronger.

---

## 41. Mobile/web client is not implemented

Current primary surfaces are:

- Windows desktop;
- tray;
- terminal;
- Discord.

A mobile/web client would be a future surface, not a current blocker.

---

# What is NOT missing anymore

Do not rebuild these from scratch.

## Implemented foundations

- Constitution integrity
- identity persistence
- personality
- conversation persistence
- reviewed memory/provenance
- ChatGPT export/import code
- emotional journal/reunion appraisal
- environment/time/season/weather
- AVATAR body/wardrobe/presentation state
- interaction ledger/boundaries
- ACT delivery/outreach foundation
- EVOLVE governed revisions
- SAFE capability/approval/operator-stop foundation
- VERIFY revision gates
- local SQLite State Plane
- component schema registry
- release manifest/signature/lineage/anti-rollback contracts
- RUN supervisor logic
- Fleet registry/discovery/enrollment/bootstrap foundations
- remote mTLS agent
- remote Ollama inference
- workload migration state machine/orchestrator
- failover guard contracts
- dual cognition
- Windows desktop/tray
- Discord transport

The work now is to convert these foundations into a **fully proven production system**.

---

# Recommended execution order

## Phase A — make the current revision trustworthy

1. Fix the 15 verification failures.
2. Remove Package Tests failure masking.
3. Protect `main`.
4. Add Linux + Python 3.14 CI.
5. Make Context Matrix projection authoritative.

## Phase B — matrix/autonomy layer ✅ closed

6. ✅ M1 Tool Exposure.
7. ✅ M2 Privacy/Audience.
8. ✅ M3 Contextual Influence.
9. ✅ M4 REL/HABIT.
10. ✅ M5 DEV/KNOW/INTEGRATE/BODY.
11. ✅ M6 Release compatibility.
12. ✅ M7 Fleet failure/recovery.

M8 Voice runtime/prosody matrix foundation is also implemented; actual live STT/TTS adapters and Desktop/Discord voice-channel parity remain interface work.

## Phase C — make Sofía survive machines/reboots

13. Main runtime Windows service.
14. Watchdog service.
15. Fleet agent durable service.
16. Real backup/restore.
17. Schema migration runner.
18. Reproducible signed release pipeline.

## Phase D — finish Fleet and distributed execution

19. Real heterogeneous Fleet acceptance.
20. Continuous monitoring/maintenance loop.
21. General worker scheduler.
22. Concrete workload backends.
23. Replicated State Plane.
24. Witness/quorum + fencing.
25. Failover/failback.
26. Full runtime mobility.

## Phase E — finish behavioral autonomy

27. ✅ Context-aware wardrobe request autonomy.
28. ✅ Reflection weather wiring.
29. ✅ Seasonal UI theme.
30. ✅ Seasonal/environment HABIT learning.
31. ✅ Contextual memory rerank.
32. ✅ Interaction willingness/expression split.
33. Production initiative/goal generation.

## Phase F — embodiment/interfaces

34. Voice.
35. Avatar renderer.
36. Gaia physical loop.
37. Additional live integration canaries.
38. General web/mobile later.

## Live behavior defects

39. 🟡 **Authoritative grounding regression in direct/follow-up conversation.**
    Direct factual questions and short follow-ups can still bypass deterministic
    state lanes and reach the LLM, allowing invented or contradictory claims.
    The observed live cases include bare `Weather`, bare `Time`,
    Fahrenheit/Celsius follow-ups becoming a fake conversational mode,
    hardware/benchmark claims without measurement evidence, outfit follow-ups
    contradicting persisted AVATAR presentation state, and "what's on your
    mind?" inventing unrecorded thoughts instead of using the Reflection
    Journal. Fix requires deterministic routing plus response validation and
    regression coverage across Desktop/Discord/Terminal. Current repairs are
    in progress on `main`; do not mark closed until the focused and full gates
    pass.

---

# Bottom line

The project is not missing a new giant architecture.

It is missing the **last-mile mechanisms and proofs** that turn many already-good contracts into a reliable distributed production system.

The highest-value work remains:

```text
green verification
→ trustworthy CI
→ authoritative matrices
→ durable services
→ backup/restore
→ release supply chain
→ distributed workers
→ replicated state + fencing
→ failover/runtime mobility
→ renderer/voice/Gaia
```

That order keeps Sofía from gaining more surface area faster than her reliability foundation can support it.
