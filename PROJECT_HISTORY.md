# Sofía Ada Lyra — Project History

> **Canonical project-history record**
>
> Updated: **2026-10-02**
>
> Branch policy: **main only**
>
> This document consolidates the substantive history, decisions, architecture, tests, live observations, code audits, TODOs, feature inventory, operating model, and matrix work discussed across the Sofía project chats. It is a project record rather than a verbatim transcript. Secrets, credentials, and private tokens are intentionally excluded.
>
> When this document conflicts with older historical notes, the newest dated entry and current code on `main` take precedence.

---

## 1. Project purpose

Sofía Ada Lyra is intended to be one persistent assistant identity whose identity is independent of:

- the LLM used for cognition;
- model provider;
- host machine;
- operating system;
- process;
- UI;
- Discord;
- voice;
- avatar;
- Gaia or another physical embodiment.

The core rule has remained:

> **The LLM is Sofía's cognitive engine. It is not Sofía herself.**

The architecture therefore separates identity, Constitution, personality, embodiment, memory, authority, capability, cognition, runtime, state, communication channels, and physical/external execution.

Capability never implies authority.

A model response is not proof that a real action occurred. Real completion claims require host-owned execution evidence.

---

# 2. Development history

## September 9, 2026 — Foundation

The project began around a strict Constitution and identity boundary.

Early work established:

- immutable Constitution representation;
- Constitution file loading;
- SHA-256 integrity checking;
- explicit Constitution version `1.0`;
- negative integrity tests;
- Python 3.12 / pytest project structure;
- `src/sofia` packaging.

Early setup exposed Windows/UNC/mapped-drive packaging problems and a BOM in `pyproject.toml`. These were corrected as the repository moved toward a reproducible package layout.

---

## September 13–15 — Runtime, conversation, persistence, cognition

The application/runtime structure was built out around:

```text
Configuration
    ↓
Composition
    ↓
SofiaRuntime
    ↓
CognitiveContext
    ↓
CognitiveSystem
    ↓
LLM provider
```

Conversation persistence became SQLite-backed and restart-aware.

Important decisions included:

- a conversation can persist across application restart;
- a fresh conversation is created when no session is explicitly resumed;
- explicit resume restores an existing session;
- ConversationStore became reopenable;
- conversation history is context, not authoritative identity/state.

Codebase inspection was added as a read-only capability behind explicit authorization.

---

## September 18–19 — Embodiment and external systems

Canonical avatar/embodiment work established:

- representational embodiment;
- canonical measurements;
- canonical clothing;
- persistence;
- cognitive projection;
- separation of representational actions from real physical actions.

The project explicitly rejected forced gesture templates and canned embodiment language.

External-system architecture was introduced:

```text
External System
    ↓
ExternalIntegrationAdapter (historical prototype; retired in Phase 9, see docs/development/external-cleanup-report.md)
    ↓
Structured Observation
```

Observation, evidence, authority, and execution remained separate.

---

## September 23–25 — INTERACT, Discord, DEV/KNOW/INTEGRATE/OPS

INTERACT was expanded heavily with:

- represented action grammar;
- boundaries;
- consent/state controls;
- private/public projections;
- durable interaction ledgers;
- stop/resume behavior;
- cross-package integration.

Discord became the first non-terminal production channel.

The accepted initial Discord scope was deliberately narrow:

- authenticated Sparks-only private DM;
- durable ingress/outbox;
- reconnect/dedupe;
- shared Sofía conversation/runtime;
- fail-closed delivery uncertainty.

DEV, KNOW, INTEGRATE, and OPS then gained increasingly concrete capabilities for:

- code inspection;
- development planning;
- source-linked changes;
- machine/system inspection;
- integration adapters;
- Fleet inventory;
- remote transport.

---

## September 25–27 — ACT, EVOLVE, RUN, ENVIRONMENT, UI, Fleet controls

ACT, EVOLVE, and RUN package foundations were added.

RUN introduced:

- lease/fencing concepts;
- supervisor state;
- restart windows;
- backoff;
- readiness;
- lifecycle records.

ENVIRONMENT became the shared context owner for:

- time;
- timezone;
- daypart;
- season;
- daylight;
- configured USER/SITE/HOST location;
- weather;
- forecast;
- provider freshness/provenance.

NWS support was intentionally narrow and pinned to `api.weather.gov`.

The Windows UI/workbench was rebuilt around one canonical application path, including:

- desktop conversation;
- durable drafts;
- tray;
- settings;
- Quick Tools;
- adaptive theme inputs.

Fleet/tray work added:

- activity awareness;
- Game Mode;
- remote controls;
- pinned mTLS transport;
- Fleet agent concepts.

---

## September 27–29 — Avatar, environment, production startup, dual cognition

The project moved into large behavior audits.

The accepted package-gate order became:

1. AVATAR
2. ENVIRONMENT
3. INTERACT
4. UI
5. RUN
6. VERIFY

then broader cleanup and production acceptance.

Avatar work expanded into:

- presentation state;
- wardrobe pieces;
- wardrobe catalogs;
- outfit catalogs;
- season/activity/weather influence;
- emotion influence;
- public/private presentation;
- persisted outfit state;
- deterministic self-fact replies;
- clothing actions.

Environment, emotion, interaction, and avatar were explicitly required to influence each other without environment/emotion becoming authority or consent.

Production startup was repaired so `python -m sofia` launches the desktop by default, with `--cli` retaining the terminal client.

Dual cognition was then built around primary/secondary roles.

Accepted routing direction:

- FAST → secondary;
- STANDARD → primary;
- DEEP → primary;
- VERIFY → primary draft → secondary critique → primary synthesis.

Fleet cognition allows cognitive placement to a remote authorized host while keeping canonical conversation/state authority local.

---

## October 4, 2026 — Architecture cleanup, unified permissions, Fleet/read tooling, CI reconciliation

A large current-main cleanup/audit removed unwired prototypes, consolidated ownership boundaries, and then completed the operator permission/exploration chain.

Key results:

- canonical five-level permission policy implemented in `sofia.safe.permissions`;
- durable standing grants and private/adult authority stored in canonical `sofia.db`;
- tray **Settings → Permissions** wired to the same canonical state;
- Level 1 read-only capabilities exposed without repeated approval;
- bounded Level 2 autonomous capabilities exposed without repeated approval;
- Level 3 uses scoped standing/exact grants;
- Level 4 requires exact action/target approval;
- Level 5 authority-changing operations remain never-self-authorized;
- bounded Fleet discovery may create or refresh **untrusted candidates only**;
- Fleet enrollment/add-machine is Level 4 and requires exact one-time Sparks approval bound to candidate/node/key/endpoint evidence;
- Fleet trust conflicts are preflighted before approval consumption;
- remote tools require trusted active OPS Fleet membership, not partial enrollment state;
- local and enrolled-remote hardware inspection are Level 1;
- approved-scope `network.discover` is Level 1, non-persistent, and independent of automatic Fleet candidate discovery;
- Docker/Portainer read-only inspection now covers endpoints, containers, inspect, stats, engine info, health summary, images, volumes, networks, stacks and bounded recent logs locally and on trusted enrolled remote nodes;
- DEV source/status/candidate inspection are Level 1; isolated `dev.build` is Level 2; apply/rollback/commit/push remain Level 4;
- permission-aware matrix authority now preserves exact host grants and truthful execution receipts;
- stale UI/SAFE/DEV/CORE test harnesses were repaired without weakening production permission or AVATAR type boundaries.

CI evidence at audited head `fc533aaf`:

- Platform Compatibility: **green** on Windows/Linux, Python 3.12/3.14;
- Matrix Tests: **green**;
- `pkg_safe`, `pkg_dev`, `pkg_ops`, `pkg_net`, `pkg_integrate`, `pkg_ui`, `pkg_avatar`, and most other package gates: **green**;
- full Manual Verification: **3375 passed, 1 failed, 6 deselected**;
- the single full-suite assertion failure is `test_environment_runtime_projection.py::test_runtime_preserves_partial_deterministic_multi_question_answers`;
- `pkg_core` is red only because that ENVIRONMENT regression is intentionally cross-owned by CORE;
- `pkg_body` is separately red because the current marker selects zero BODY tests and pytest exits nonzero.

This also exposed a documentation bookkeeping error: the repository now has **22 package/test families**, because **VOICE** has its own `pkg_voice` marker and CI gate.

# 3. Matrix architecture

The matrix architecture was added so each user turn can be handled using explicit typed decisions instead of one giant prompt stuffed with everything Sofía knows.

Current matrix stages are effectively:

```text
A. Turn / Message Classification
        ↓
B. Domain Relevance Matrix
        ↓
C. Context Matrix
        ↓
D. Evidence Matrix
        ↓
E. Authority / Action Matrix
        ↓
F. Response Contract + Validation Matrix
        ↓
G. Cognition Routing Matrix
        ↓
H. Trace / Diagnostics
        ↓
I. Channel Parity
```

The matrix layer coordinates relevance. It does not become a new source of truth.

Current `MatrixDomain` values are:

- SOCIAL
- EMOTION
- ENVIRONMENT
- AVATAR
- INTERACTION
- MEMORY
- COGNITION
- MACHINE
- OPS
- AUTHORITY
- CONTINUITY

Package-owned evaluators currently exist for each of those domains.

The Context Matrix controls both domain projection and prompt-visible history. Current history policies include:

- NONE
- LAST_TURN
- TOPIC_WINDOW
- BOUNDED_RECENT
- RETRIEVE_SPECIFIC

The Evidence Matrix currently supports:

- canonical evidence;
- current evidence;
- measured evidence;
- remembered evidence;
- execution receipts.

The Authority Matrix returns:

- NOT_REQUIRED
- ALLOWED
- DENIED
- REQUIRES_APPROVAL
- CLARIFY

The Response Matrix checks drafts before persistence and can reject/retry/fallback when the model claims:

- an execution without authority;
- an execution without a receipt;
- measured network health without measurements;
- current weather without current evidence.

The Routing Matrix selects logical FAST/STANDARD/DEEP/VERIFY routes while the actual cognitive router still owns execution.

The Trace Matrix records the decision path without duplicating message text.

---

## Matrix acceptance milestone

On **2026-10-01**, the D–I matrix slice was accepted with:

- Windows matrix regression: **147/147**;
- live dual-cognition canary accepted;
- FAST observed on the secondary model;
- DEEP observed on the primary model;
- VERIFY observed as primary → secondary → primary;
- actual model/host/route diagnostics recorded;
- Desktop/Discord/Terminal provenance covered.

Voice live-channel parity remains deferred, but VOICE now has a real runtime/capability + prosody matrix foundation and its own `pkg_voice` package gate.

---

# 4. Behavior matrices

Separate behavior-matrix tests exist for:

### AVATAR

Representative combinations include:

- daypart;
- season;
- activity;
- fresh/stale weather;
- emotion influence;
- public/private outfit behavior.

### EMOTION

The emotion matrix covers:

- transient decay;
- persistent relational emotion;
- mixed positive/negative state;
- environmental influence;
- missing environment;
- source-backed reinforcement;
- reappraisal;
- absence/reunion appraisal.

### ENVIRONMENT cross-matrix

Current cross-package environment tests verify:

```text
ENVIRONMENT
    ↓
EMOTION context
    ↓
INTERACT context
    ↓
AVATAR presentation
    ↓
WARDROBE
```

while preserving the rule that environment does not grant authority, consent, or physical execution.

### INTERACT

The interaction matrix covers:

- ordinary gestures;
- fox-anatomy interactions;
- social actions;
- private interactions;
- stop/resume;
- durable replay;
- grant enforcement;
- non-execution language.

---

# 5. Current architecture

Current application flow is approximately:

```text
Desktop / Discord / Terminal
           │
           ▼
   ConversationService
           │
           ├── authenticated principal/audience
           ├── conversation persistence
           ├── memory learning
           ├── relationship observation
           ├── habit observation
           └── turn matrix
                   │
                   ▼
          Context / Evidence
          Authority / Response
          Routing decisions
                   │
                   ▼
              SofiaRuntime
                   │
         ┌─────────┼─────────┐
         │         │         │
      Memory   Environment  Avatar
         │         │         │
         └─────────┼─────────┘
                   ▼
            CognitiveSystem
                   │
           primary / secondary
                   │
             tool gateway
                   │
           host authorization
                   │
             real capability
```

---

# 6. Canonical production state

A major September 30 correction established one authoritative desktop database.

Normal Windows production state now resolves to:

```text
C:\ProgramData\SofiaAdaLyra\sofia.db
```

unless explicitly overridden by the centrally owned storage configuration.

The desktop no longer moves conversation authority to a Fleet node merely because cognition is remote.

Current rule:

> Fleet may move cognitive work. Conversation/state authority remains local until real replicated-state fencing/recovery exists.

Production protected/state files are separated from repository seed files.

Production identity defaults to `REQUIRE_EXISTING`, preventing a normal rebuilt/joining node from silently minting another Sofía identity.

---

# 7. State Plane

The code now contains a real State Plane abstraction:

- `StatePlane`;
- `SQLiteStatePlane`;
- typed state classes/keys/records;
- compare-and-swap revision handling;
- namespace scoping;
- component schema compatibility;
- migration lease infrastructure.

This means older project notes saying “no State Plane” are obsolete.

Current limitation:

> The production State Plane is still a single local SQLite baseline. It is not yet a replicated multi-host authoritative database.

---

# 8. SAFE

Current SAFE code includes:

- unified five-level capability permission policy;
- canonical durable grants/private-adult authority in `sofia.db`;
- permission CLI and tray Permissions UI;
- automatic Level-1 read and explicitly classified Level-2 exposure;
- scoped Level-3 standing grants;
- exact Level-4 approvals;
- Level-5 never-self-authorized authority changes;
- execution approval;
- DEV approval;
- EVOLVE approval;
- operator stop;
- tamper-evident audit infrastructure;
- Windows DPAPI secret storage;
- signed release verification;
- Ed25519 trust;
- anti-rollback/lineage checks.

Production composition now uses `FailClosedActionExecutor`; the older statement that production still uses `TestActionExecutor` is obsolete.

---

# 9. VERIFY

Current VERIFY includes:

- revision-pinned verification gates;
- static compile/dependency checks;
- pytest verification;
- semantic integrity verification;
- release evidence;
- dual-cognition live verification.

GitHub Actions currently has:

- Package Tests;
- Matrix Tests;
- Manual Verification.

---

# 10. Release / Integrity Plane

The current release architecture contains:

- immutable `ReleaseManifest`;
- exact Git revision;
- application/Python version;
- dependency lock digest field;
- SBOM digest field;
- provenance digest;
- schema compatibility;
- Fleet protocol/agent compatibility;
- Constitution digest;
- optional artifact/model/asset digests;
- Ed25519 verification;
- lineage verification;
- anti-rollback;
- immutable staged release directories;
- active-release State Plane records;
- rollback to a previously accepted release;
- crash-loop recovery hook.

Still missing from the real build pipeline:

- generated dependency lock artifact;
- repository SBOM artifact;
- complete provenance generation;
- reproducible release build;
- signed release builder;
- staged Fleet canary/wave rollout;
- convergence proof.

---

# 11. Fleet

Current Fleet/remote code is substantially beyond the earlier “75%” estimate.

The repository contains:

- Fleet inventory;
- telemetry;
- activity awareness;
- placement;
- drift;
- durable leases;
- candidate discovery;
- enrollment;
- bootstrap;
- Windows bootstrap/rekey;
- mTLS remote control;
- remote inspection;
- remote inference;
- Ollama inspection/lifecycle;
- workload contracts;
- migration planning;
- migration orchestration.

Automatic discovery is now wired into the application background coordinator when configured.

Current-main Fleet discovery now automatically creates/refreshes untrusted candidates only; exact enrollment/add-machine is Level 4 and requires Sparks approval. Approved-scope read-only network discovery remains independent from candidate persistence, and enrolled remote inspection requires trusted active OPS membership.

Current missing Fleet work is mainly real deployment/acceptance and later-state architecture:

- heterogeneous Windows/Linux/Pi live acceptance;
- continuous maintenance and key rotation/revocation drills;
- distributed worker runtime;
- concrete general workload backend;
- replicated state;
- cross-host writer fencing;
- failover;
- full runtime mobility.

---

# 12. Workload migration

Workload migration has a real typed state machine:

```text
PLANNED
 ↓
DRAINED
 ↓
CHECKPOINTED (when required)
 ↓
TARGET_STARTED
 ↓
READY
 ↓
SOURCE_FENCED
 ↓
COMPLETED
```

Rollback and outcome-uncertain states are explicitly handled.

However the general executor remains a `WorkloadBackend` protocol.

Therefore:

> Migration orchestration exists; a production backend capable of actually draining/checkpointing/starting/fencing arbitrary workloads is still required.

---

# 13. RUN and service supervision

Current RUN source includes:

- local runtime lease;
- fencing epoch;
- readiness deadline;
- restart backoff;
- restart-window limits;
- supervisor event log;
- release rollback hook;
- standalone `python -m sofia.run.host` watchdog host;
- service-status/start/stop adapter.

Important current limitation:

> The repository no longer contains the earlier dedicated Windows ServiceFramework installer/wrapper files for the Sofía runtime and watchdog.

The new supervisor can control a Windows service, but current source does not fully provision/install that service boundary.

Required work includes:

- install runtime service;
- uninstall;
- configure executable/release pointer;
- automatic startup;
- service recovery;
- watchdog installation;
- upgrade;
- verification of installed command/path.

---

# 14. Avatar

Current AVATAR is no longer just a body JSON file.

It includes:

- embodiment contract;
- authoritative body measurements;
- presentation state;
- wardrobe;
- clothing catalogs;
- outfit catalogs;
- public/private projections;
- private presentation grants;
- environment/emotion influences;
- persisted presentation;
- clothing action handling;
- deterministic self-fact responses;
- matrix integration.

Current major missing piece:

> There is still no real graphical avatar renderer.

Missing renderer-level work includes:

- 3D model load;
- rig;
- animation controller;
- expression/blendshape driver;
- lip sync;
- clothing mesh/state binding;
- live viewport;
- animation receipts.

MPFB/Blender model work belongs to this phase.

---

# 15. Voice

VOICE is now a first-class package/test family rather than an entirely absent workstream.

Current source includes:

- voice runtime/capability modeling;
- TTS plumbing on Windows;
- evidence-linked prosody controls;
- VOICE cognition/matrix ownership;
- explicit enable/disable and fallback semantics;
- package-level regression coverage.

Still incomplete or awaiting supervised live acceptance:

- microphone/STT pipeline;
- robust input-device handling and VAD;
- interruption/barge-in;
- natural voice-quality tuning;
- Desktop/Discord live voice-channel parity;
- end-to-end evidence that spoken output/listening status matches real devices and engines.

---

# 16. Gaia / BODY

BODY remains the long-term physical embodiment boundary.

Future complete path:

```text
cognitive intention
      ↓
BODY plan
      ↓
physical authority
      ↓
motion safety
      ↓
SSC-32 / servos
      ↓
sensor feedback
      ↓
verified physical state
```

Important future requirements:

- final servo calibration;
- kinematics/gaits;
- sensors;
- physical e-stop;
- failure recovery;
- execution receipts.

---

# 17. Current capabilities

Sofía currently has code foundations for the following capability families.

## Conversation

- terminal;
- Windows desktop;
- Discord DM;
- durable conversation sessions;
- bounded provider-visible history;
- principal/audience binding.

## Cognition

- Ollama;
- primary/secondary routing;
- FAST/STANDARD/DEEP/VERIFY;
- model lifecycle;
- Fleet-placed inference;
- response-quality retry;
- matrix tracing.

## Memory

- conversation originals;
- reviewed/promoted memory;
- provenance;
- source invalidation;
- bounded historical ChatGPT import evidence;
- automatic proposal of reviewable memory candidates.

## Self / continuity

- identity;
- Constitution;
- personality;
- runtime state;
- restart continuity;
- workspace change awareness;
- operational self-model.

## Environment

- current clock;
- timezone;
- daypart;
- season/daylight;
- configured location;
- weather/forecast;
- NWS;
- Home Assistant observation path.

## Avatar

- body;
- measurements;
- wardrobe;
- outfits;
- presentation;
- emotion/environment influence;
- private/public state;
- clothing requests.

## Machine / Fleet

- machine discovery and inventory;
- system/process/network/service/hardware inspection;
- Level-1 approved-scope network discovery that does not persist Fleet membership;
- Level-2 bounded Fleet candidate discovery that persists only untrusted candidates;
- exact Level-4 Sparks approval for Fleet enrollment/add-machine;
- trusted-membership requirement for remote tools;
- local and enrolled-remote hardware inspection;
- Fleet telemetry, placement and migration planning;
- remote Docker/Portainer read-only inspection;
- remote Ollama/model lifecycle.

## Development

- Level-1 codebase/status/candidate inspection;
- filesystem observation;
- durable self-improvement candidate history;
- isolated Level-2 `dev.build`;
- protected Level-4 apply/rollback/commit/push;
- Git/GitHub-oriented development surfaces;
- release architecture.

---

# 18. Tool/command surfaces

Representative commands/surfaces currently include:

### Start Sofía

```powershell
python -m sofia
```

Starts the normal desktop workbench.

### Terminal mode

```powershell
python -m sofia --cli
```

Starts the terminal conversation client.

### RUN supervisor host

```powershell
python -m sofia.run.host
```

Runs the host-neutral watchdog/supervisor loop against the configured local Sofía service.

### Revision verification

```powershell
python -m sofia.verify.gate --phase full --evidence-path verify-evidence.json
```

Runs static checks plus the non-integration pytest gate and records revision-pinned evidence.

### Dual cognition live verification

```powershell
python -m sofia.verify.dual_cognition --evidence-path dual-cognition-evidence.json
```

Tests configured FAST/DEEP/VERIFY routes against the real configured cognitive engines.

### Package gates

```powershell
pytest -q -m "pkg_avatar and not integration"
pytest -q -m "pkg_environment and not integration"
pytest -q -m "pkg_interact and not integration"
```

Package markers currently exist for **22 package families**.

---

# 19. Current package roster

The repository now defines **22 package markers**, confirmed by `pyproject.toml`, `test/conftest.py`, and the Package Tests workflow:

1. CORE
2. INTERACT
3. MEM
4. SOCIAL
5. NET
6. UI
7. VOICE
8. RUN
9. OPS
10. ACT
11. REL
12. AVATAR
13. DEV
14. BODY
15. EVOLVE
16. CLEAN
17. KNOW
18. INTEGRATE
19. ENVIRONMENT
20. HABIT
21. SAFE
22. VERIFY

Older ROADMAP/PROJECT_HISTORY text that says 19, 20, or 21 packages is historical and superseded for current planning.

---

# 20. Current CI status at the time of this history update

Audited current `main` head:

```text
fc533aafab25bffc6248406484d4b672a6e7e41f
```

Current workflows:

- Platform Compatibility: **success** across Windows/Linux, Python 3.12/3.14;
- Matrix Tests: **success**;
- Package Tests: **failure**, with failures isolated to BODY/ENVIRONMENT plus CORE's intentional cross-ownership of the same ENVIRONMENT assertion;
- Manual Verification: **failure** with **3375 passed, 1 failed, 6 deselected**.

The single full-verification assertion failure is:

```text
test/test_environment_runtime_projection.py::
test_runtime_preserves_partial_deterministic_multi_question_answers
```

The expected trusted deterministic subquestion material is missing from the provider-visible system context for the mixed turn:

```text
what day is it, explain a database transaction?
```

Package details relevant to the October 4 permission/Fleet work:

- `pkg_safe`: **success**;
- `pkg_dev`: **success**;
- `pkg_ops`: **success**;
- `pkg_net`: **success**;
- `pkg_integrate`: **success**;
- `pkg_core`: **failure only because the ENVIRONMENT test is also CORE-marked**;
- `pkg_body`: **failure because zero BODY tests are currently selected**.

The older CI masking bug is closed. Package jobs no longer use `continue-on-error: true`; package failures now fail the workflow.

---

# 21. Current TODO

## P0 — correctness / verification

- fix the ENVIRONMENT mixed-question deterministic-subanswer regression;
- restore at least one meaningful BODY-owned package test (or deliberately redefine BODY package ownership) so `pkg_body` does not fail from zero selected tests;
- rerun exact-head Package Tests and Manual Verification;
- run live Venus/Artemis canaries for the completed Permissions → Fleet → Hardware → Network → Docker → DEV chain.

## P1 — RUN/service reliability

- verify the installed Windows runtime service command/path against current accepted source;
- verify/install the watchdog host from current source rather than historical service wrappers;
- exercise crash/restart/backoff and active-release startup;
- add automatic bad-release rollback/controlled forward-fix evidence.

## P1 — backup/recovery

- independent canonical-state backup;
- protected-state/trust-root backup;
- restore into a clean environment;
- semantic integrity validation after restore;
- define and measure RPO/RTO;
- bare-metal recovery rehearsal.

## P1 — Fleet live acceptance

- supervised Artemis candidate discovery and exact enrollment approval;
- Linux host acceptance;
- Raspberry Pi-class acceptance;
- key rotation/rekey/revocation;
- quarantine/duplicate/spoof rejection;
- continuous monitoring/maintenance;
- useful one-time ACT enrollment/change notifications.

## P2 — distributed execution

- concrete general workload backend;
- durable task scheduling/leases;
- worker heartbeat/readiness;
- result/receipt handling;
- real drain/checkpoint/start/fence migration canary;
- cross-host singleton fencing.

## P2 — replicated authoritative state

- second independent data-bearing location;
- one-writer contract;
- witness/equivalent fencing authority;
- replica health/freshness;
- partition behavior;
- failover and stale-writer rejection;
- independent versioned backup and recovery tests.

## P2 — release supply chain

- generated dependency lock;
- repository SBOM;
- build provenance;
- reproducible immutable artifact;
- signer workflow and trust-root custody;
- canary/update rings;
- staged Fleet rollout;
- convergence proof;
- automatic rollback/forward-fix.

## P3 — interface/embodiment

- graphical avatar renderer and animation receipts;
- live voice/STT/device/channel acceptance and natural-quality tuning;
- mobile/web only if still desired;
- Gaia physical integration with hardware E-stop.

## Later — general web/search

- keep general browsing/search separately authorized and last;
- NWS remains a narrow approved ENVIRONMENT exception, not a general web grant.

---

# 22. Matrix audit — 2026-10-02

The current matrix architecture is strong and should **not** be expanded by creating one matrix for every package.

That would turn the architecture into spreadsheet hydra.

However additional matrix coverage is warranted in a few specific places.

## Recommended new matrix 1 — Capability / Tool Exposure Matrix

**Priority: P0**

Current tool exposure still begins with a separate regex function:

```python
_conversation_tools_relevant(...)
```

The matrix controls:

- domain;
- context;
- evidence;
- authority;
- response validation;
- LLM route;

but it does **not** yet own exact tool exposure.

Recommended contract:

```text
Turn Matrix
 + Domain Matrix
 + Authority Matrix
 + Principal/Audience
        ↓
Capability/Tool Matrix
        ↓
exact permitted tool families
        ↓
CapabilityGateway still performs final authorization
```

This matrix must never grant authority. It only decides which already-authorized tools are relevant enough to expose to cognition.

Example:

```text
"hru"
→ no tools

"show CPU usage"
→ system/hardware read tools

"restart Plex"
→ service/OPS action family
→ authority decision still independent

"change your outfit"
→ AVATAR state-action path only
→ no generic OPS toolbox
```

This removes duplicated regex routing and is the clearest missing piece in the existing A–I turn pipeline.

---

## Recommended new matrix 2 — Principal / Audience / Privacy Matrix

**Priority: P0**

Principal/audience is already enforced by several stores, but it is not a first-class matrix decision.

Add explicit turn-level privacy projection:

```text
principal
audience
channel
requested domain
data classification
private grants
        ↓
Privacy Projection
        ↓
what may enter context
what may be retrieved
what may be displayed
```

This is especially important for:

- Discord;
- future multi-user channels;
- private avatar state;
- relationship state;
- memory;
- HABIT;
- imported historical chats;
- future voice.

This should probably be an extension adjacent to the Context Matrix rather than an independent policy engine.

---

## Recommended matrix extension 3 — REL + HABIT domain projections

**Priority: P1**

REL and HABIT now collect real principal-bound state, but neither is a `MatrixDomain`.

Do **not** build new standalone matrix engines.

Instead extend the existing Domain + Context + Evidence matrices with:

```text
REL
HABIT
```

Examples:

```text
"how long have I been gone?"
→ REL / continuity evidence

"you know I normally get home around 5"
→ HABIT + MEMORY

"you seem annoyed I was late"
→ REL + HABIT + EMOTION + CONTINUITY
```

This lets those states influence conversation only when relevant instead of becoming permanent prompt baggage.

---

## Recommended matrix extension 4 — DEV / KNOW / INTEGRATE / BODY semantic domains

**Priority: P1/P2**

Today many action terms collapse into `OPS`.

That is adequate for early rollout, but increasingly coarse.

Add domain ownership only where it changes context/tool selection:

- DEV — source/code/test/release work;
- KNOW — document/reference/provenance questions;
- INTEGRATE — Home Assistant/JMRI/Portainer/application adapters;
- BODY — Gaia/robot physical control.

This prevents:

```text
"edit this Python file"
```

from being treated like:

```text
"restart a Windows service"
```

just because both are state-changing actions.

SAFE and VERIFY should remain cross-cutting policies rather than ordinary conversational domains.

---

## Recommended new matrix 5 — Release / Schema / Fleet Compatibility Matrix

**Priority: P1**

This is **not** a conversation matrix.

It should be a VERIFY/release acceptance matrix across:

- release revision;
- State Plane schema revision;
- configuration schema;
- Fleet protocol;
- Fleet agent version;
- Python/runtime version;
- dependency lock;
- model identity;
- asset identity.

Representative rows should prove:

- upgrade accepted;
- rollback accepted within compatibility window;
- newer incompatible schema rejected;
- bad signature rejected;
- wrong agent protocol rejected;
- wrong artifact digest rejected;
- mutable/unknown model identity handled honestly.

The release code already has the contracts. The systematic compatibility matrix is the missing proof layer.

---

## Recommended new matrix 6 — Fleet Failure / Recovery Matrix

**Priority: P1 before runtime mobility**

Also not a conversation matrix.

Dimensions should include:

### Host state

- healthy;
- degraded;
- unreachable;
- rebooting;
- revoked;
- quarantined.

### Workload state

- idle;
- running;
- draining;
- checkpointing;
- migrating;
- outcome unknown.

### Failure

- agent loss;
- network partition;
- target fails readiness;
- source dies before fence;
- source dies after checkpoint;
- target dies after start;
- stale writer returns;
- database unavailable.

### Expected result

- continue;
- pause;
- rollback;
- quarantine;
- fail closed;
- require operator approval;
- promote standby only with valid fencing.

This matrix is essential before claiming workload migration, failover, or full runtime mobility.

---

## Recommended cross-matrix suites

Add representative end-to-end combinations rather than full Cartesian explosions.

### Relationship / habit / emotion

```text
REL
 + HABIT
 + ENVIRONMENT
 + CONTINUITY
        ↓
EMOTION
        ↓
INTERACT
        ↓
AVATAR
```

### Action execution

```text
DOMAIN
 + PRIVACY
 + TOOL EXPOSURE
 + AUTHORITY
 + EVIDENCE
        ↓
EXECUTION
        ↓
RECEIPT
        ↓
RESPONSE VALIDATION
```

### Fleet cognition

```text
MESSAGE ROUTE
 + MODEL ROLE
 + HOST PLACEMENT
 + MODEL AVAILABILITY
 + FLEET AUTHORITY
        ↓
actual model/host execution trace
```

---

## Matrices that should NOT be added

Do not create separate matrices merely because a package exists.

Specifically, avoid standalone:

- SAFE Matrix;
- VERIFY Matrix;
- UI Matrix;
- CLEAN Matrix;
- CORE Matrix.

SAFE and VERIFY are cross-cutting constraints around every matrix.

UI is a channel/surface and belongs in parity tests.

CLEAN is an operational capability/domain when invoked, not a perpetual cognition context.

CORE identity/Constitution remain invariants and should not become optional matrix-selected truth.

---

# 23. Recommended matrix order

After the current regression gate is green:

1. **Tool/Capability Exposure Matrix**
2. **Principal/Audience/Privacy projection**
3. **REL + HABIT domain/context/evidence extension**
4. **DEV + KNOW + INTEGRATE + BODY domain refinement**
5. **Release compatibility matrix**
6. **Fleet failure/recovery matrix**
7. Extend live voice channel parity after STT/TTS/device acceptance is proven

This gives the matrix architecture more precision without turning it into another giant monolith.

---

# 24. Current conclusion

Sofía has crossed the line from “assistant prototype” into a fairly serious distributed assistant architecture.

The major remaining problems are no longer missing folders.

They are now:

- trustworthy verification;
- OS service deployment;
- backup/restore;
- real heterogeneous Fleet acceptance;
- distributed work;
- replicated authoritative state;
- failure recovery;
- immutable release supply chain;
- renderer/voice/physical embodiment.

The matrix system should be expanded selectively around **tool exposure, privacy, REL/HABIT context, release compatibility, and Fleet failure behavior**, not multiplied indiscriminately.



# 25. Roadmap synchronization — 2026-10-02

The focused matrix plan is now maintained in [`MATRIX_ROADMAP.md`](MATRIX_ROADMAP.md) and summarized in [`ROADMAP.md`](ROADMAP.md).

The matrix expansion was subsequently completed on `main` in this order:

1. ✅ M1 Capability / Tool Exposure Matrix
2. ✅ M2 Principal / Audience / Privacy Matrix
3. ✅ M3 Contextual Influence Matrix
4. ✅ M4 REL + HABIT domain/context/evidence extension
5. ✅ M5 DEV + KNOW + INTEGRATE + BODY semantic domain refinement
6. ✅ M6 Release / Schema / Fleet Compatibility Matrix
7. ✅ M7 Fleet Failure / Recovery Matrix
8. ✅ M8 Voice runtime/prosody matrix foundation

The dedicated Matrix Tests closure gate passed **405/405** on commit `130aa735`. Actual live STT/TTS adapters and Desktop/Discord voice-channel parity remain later interface work, not missing matrix foundations.

At that checkpoint the package/test roster was treated as 21 families. **Current main has 22**, because VOICE now has its own `pkg_voice` marker and CI gate. The current roster is documented in section 19 above; older 20/21-family references are historical.

## AVATAR clothing-request autonomy clarification

Natural-language clothing forms such as:

- `wear X`
- `put on X`
- `change your outfit to X`
- `take off X`

are treated semantically as **requests/suggestions**, not direct commands over Sofía's canonical AVATAR state.

The current implementation already preserves the critical authority separation through `ClothingActionService` and `WardrobeAutonomyPolicy`:

```text
user request/suggestion
    ↓
parse candidate change
    ↓
wardrobe validation
    ↓
privacy/grant checks
    ↓
wardrobe autonomy decision
    ├─ accept
    └─ decline
    ↓
accepted transition only
    ↓
commit
    ↓
persist
    ↓
verify
    ↓
truthful completion response
```

Future richer autonomy may also support a counter-proposal/alternative outfit.

The intended autonomy decision is context-aware. Trusted current **weather**, **time/daypart**, and **modeled emotion** should influence whether Sofía accepts the requested outfit, declines it, or counter-proposes another option. Those inputs are influences only: they do not become authority, consent, or private-presentation grants. Stale or unknown weather must not be treated as current evidence.

That earlier gap is now closed: current wardrobe autonomy receives trusted contextual influence through the shared contextual-influence contract. Weather/time/daypart/season/emotion remain bounded influences only and never become authority, consent, or private-presentation grants.

The default public wardrobe policy currently accepts valid public requests, which is why the existing feature already behaves successfully in normal cases. That default acceptance must never be interpreted as the user having direct state authority.

Imperative grammar is not authority.

A user request or LLM statement is not proof that a wardrobe change occurred. Only the committed and verified AVATAR presentation transition may be described as completed.

Private presentation remains separately grant-gated, and refusal leaves canonical wardrobe state unchanged.


# 26. Contextual influence audit — 2026-10-02

A whole-code-path audit was performed for the influence set:

```text
modeled emotion
current weather
trusted time/daypart
grounded season
```

The result is recorded in [`CONTEXTUAL_INFLUENCE_AUDIT.md`](CONTEXTUAL_INFLUENCE_AUDIT.md).

The project now treats these four signals as one **Contextual Influence Matrix** rather than four independent policy systems.

The matrix is a whitelist per decision surface. It decides whether each signal may affect:

- the decision itself;
- expression only;
- bounded salience;
- a strong preference;
- hard compatibility;
- or nothing.

Implementation outcome:

- automatic outfit selection and user-requested wardrobe autonomy use the shared influence contract with different reviewed strengths;
- Context Matrix exclusions prevent later EMOTION/ENVIRONMENT re-injection;
- reflection receives evidence-backed current weather together with trusted emotion/daypart/season context;
- outreach salience uses bounded context while ACT independently enforces quiet hours/limits;
- desktop adaptive theme includes season as a bounded visual cue;
- HABIT learning supports seasonal/environment correlations with evidence/coverage requirements;
- reviewed memory retrieval performs only bounded contextual tie-breaking after PROMOTED + principal/audience + explicit query relevance eligibility;
- interaction willingness and expression use separate typed surfaces, so weather/daypart/season cannot directly decide willingness or consent;
- Voice prosody reuses the same provenance-gated influence contract without letting weather/season directly alter numeric prosody.

The non-negotiable invariant is:

> Context may shape personality and preference. It may not shape truth or authority.

Therefore emotion/weather/time/season must never independently change SAFE policy, action authorization, private grants, execution receipts, release verification, Fleet trust/fencing, DEV correctness, EVOLVE approval, or BODY safety.
