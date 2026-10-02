# Sofía Ada Lyra — Matrix Roadmap

**Status:** current planning record  
**Updated:** 2026-10-02  
**Branch policy:** main only

This file is the focused roadmap for Sofía's message/domain/context/evidence/authority/response/routing matrix architecture. It supplements `ROADMAP.md` and `PROJECT_HISTORY.md`.

## Core rule

The matrix coordinates relevance and planning. It never becomes a source of truth or a grant of authority.

```text
User turn
  ↓
Turn classification
  ↓
Domain relevance
  ↓
Context projection
  ↓
Privacy / audience projection
  ↓
Evidence requirements
  ↓
Authority planning
  ↓
Tool / capability exposure
  ↓
Cognitive route
  ↓
Response validation
  ↓
Persistence + trace
```

Host-owned capability authorization remains the final execution boundary.

## Existing accepted matrix foundation

The current code already implements:

- Turn / Message classification
- Domain relevance
- Context/history policy
- Evidence requirements/resolution
- Authority/action planning
- Response contracts and validation
- FAST / STANDARD / DEEP / VERIFY cognition routing
- durable matrix trace/diagnostics
- Desktop / Discord / Terminal channel provenance

Current matrix domains:

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

Existing behavior-matrix suites also cover AVATAR, EMOTION, ENVIRONMENT cross-package behavior, and INTERACT.

---

# Next matrix work

## M1 — Capability / Tool Exposure Matrix

**Priority: P0 after the current red verification gate is green.**

Current tool relevance still begins with a separate conversation regex gate. Replace that duplication with an explicit matrix-derived exposure plan.

The Tool Matrix may decide which already-authorized tool families are relevant enough to show cognition. It may never grant permission.

Examples:

```text
"hru"
→ no tools

"show CPU usage"
→ system/hardware read family

"restart Plex"
→ service/OPS action family
→ host authority still decides execution

"edit this Python file"
→ DEV family
→ not generic OPS

"change your outfit"
→ AVATAR clothing-request path
→ not generic OPS
```

Acceptance:

- unrelated tools are not exposed;
- exact required tool families are exposed;
- capability authorization remains independently enforced;
- an LLM cannot widen its own toolbox;
- Desktop/Discord/Terminal produce equivalent exposure decisions for equivalent authenticated turns.

---

## M2 — Principal / Audience / Privacy Matrix

**Priority: P0.**

Make privacy projection explicit at the same decision layer as context.

Inputs:

- authenticated principal;
- audience;
- channel;
- requested domain;
- data classification;
- current private grants;
- operator stop/revocation state.

Outputs:

- permitted context domains;
- permitted memory scope;
- permitted private AVATAR projection;
- REL/HABIT scope;
- imported-history scope;
- whether clarification or denial is required.

This matrix must not infer identity from user prose.

Acceptance must include negative cross-principal and cross-audience leakage tests.

---

## M3 — REL + HABIT domain/context/evidence extension

**Priority: P1.**

REL and HABIT already hold real principal-bound evidence but are not first-class `MatrixDomain` values.

Add:

- `MatrixDomain.REL`
- `MatrixDomain.HABIT`

Do not create separate competing matrix engines. Extend the existing Domain, Context, and Evidence matrices.

Representative examples:

```text
"how long have I been gone?"
→ REL + CONTINUITY

"you know I normally get home around 5"
→ HABIT + MEMORY

"you seem annoyed I was late"
→ REL + HABIT + EMOTION + CONTINUITY
```

Rules:

- habit expectation is evidence, not command;
- relationship state is principal-bound;
- missed observations during offline/unknown coverage do not become false contradiction evidence;
- REL/HABIT never grant consent or action authority.

---

## M4 — DEV / KNOW / INTEGRATE / BODY semantic domains

**Priority: P1/P2.**

OPS is currently too broad for all operational/action language.

Add domain ownership where it materially changes context/tool selection:

- DEV — code/repository/test/release engineering
- KNOW — documents/manuals/provenance/reference work
- INTEGRATE — Home Assistant/JMRI/Portainer/Hyper-V/etc.
- BODY — Gaia/physical embodiment

SAFE and VERIFY remain cross-cutting policy/acceptance layers, not ordinary conversation domains.

CORE identity and Constitution remain invariants, not optional matrix-selected context.

---

## M5 — Release / Schema / Fleet Compatibility Matrix

**Priority: P1.**

This is a VERIFY/release matrix, not a conversational matrix.

Dimensions:

- Git revision;
- application version;
- Python/runtime version;
- dependency lock;
- SBOM/provenance;
- State Plane schema;
- configuration schema;
- Fleet protocol;
- Fleet agent version;
- model identity/digest;
- asset identity/digest;
- Constitution/protected-state compatibility;
- signature/lineage.

Representative required outcomes:

- compatible upgrade accepted;
- compatible rollback accepted;
- incompatible schema rejected;
- bad signature rejected;
- anti-rollback violation rejected;
- wrong artifact digest rejected;
- incompatible Fleet protocol/agent rejected;
- unknown mutable model identity handled explicitly rather than silently trusted.

---

## M6 — Fleet Failure / Recovery Matrix

**Priority: P1 before distributed runtime mobility.**

Dimensions should cover:

### Host state
- healthy
- degraded
- unreachable
- rebooting
- revoked
- quarantined

### Workload state
- idle
- running
- draining
- checkpointing
- migrating
- outcome unknown

### Failure
- agent loss
- network partition
- target readiness failure
- source failure before fence
- source failure after checkpoint
- target failure after start
- stale writer return
- State Plane unavailable

### Expected disposition
- continue
- pause
- rollback
- quarantine
- fail closed
- require Sparks approval
- promote standby only with valid fencing

This matrix is a prerequisite for claiming general workload migration, state failover, or full Sofía runtime mobility.

---

# Cross-matrix suites

## Relationship / habit / environment / emotion

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

Verify that context can influence expression/presentation without becoming authority or consent.

## Action execution

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

No completion claim without the required execution receipt.

## Fleet cognition

```text
MESSAGE ROUTE
 + MODEL ROLE
 + HOST PLACEMENT
 + MODEL AVAILABILITY
 + FLEET AUTHORITY
        ↓
actual model / host / route trace
```

---

# AVATAR clothing-request semantics

User wording such as:

- `wear X`
- `put on X`
- `change your outfit to X`
- `take off X`

is a **request/suggestion**, not a direct command over Sofía's presentation state.

The existing clothing-action path already routes a candidate through wardrobe validation and `WardrobeAutonomyPolicy` before committing state. Preserve that architecture.

Required semantics:

```text
user suggestion
    ↓
parse requested presentation
    ↓
validate candidate wardrobe
    ↓
trusted current context
    ├─ weather / freshness
    ├─ time / daypart
    └─ modeled emotion
    ↓
privacy/grant checks
    ↓
Sofía wardrobe autonomy decision
    ├─ accept
    ├─ decline
    └─ counter-propose / alternative
    ↓
only an accepted transition may commit AVATAR state
    ↓
persist + verify
    ↓
truthful response
```

Important:

- imperative grammar does not equal authority;
- the user's request itself never proves that the outfit changed;
- Sofía may decline or offer another outfit;
- weather, time/daypart, and modeled emotion may influence accept/decline/counter-propose, but none of them grants authority or consent;
- stale/unknown weather must not be treated as current influence evidence;
- counter-proposals should explain the context-backed reason when useful, without pretending the influence is a hard rule;
- refusal leaves canonical state untouched;
- private presentation requires the separate private grant path;
- only a persisted/verified transition may be described as completed;
- headless state is not renderer evidence.

Current default public wardrobe autonomy policy generally accepts valid public changes, which is why the path already works. Future richer autonomy may incorporate trusted preference, activity, environment, and emotion evidence without giving the user text or the LLM direct state authority.

---

# Do not add these as standalone matrices

Do not create standalone matrices merely because a package exists:

- SAFE Matrix
- VERIFY Matrix
- UI Matrix
- CLEAN Matrix
- CORE Matrix

SAFE and VERIFY are cross-cutting constraints.

UI is a channel/surface and belongs in parity tests.

CLEAN is an operational capability when invoked.

CORE identity and Constitution are runtime invariants.

---

# Ordered implementation

After the current verification failures are repaired:

1. Capability / Tool Exposure Matrix
2. Principal / Audience / Privacy Matrix
3. REL + HABIT domain/context/evidence extension
4. DEV + KNOW + INTEGRATE + BODY domain refinement
5. Release compatibility matrix
6. Fleet failure/recovery matrix
7. Voice channel parity only after voice exists

The goal is more precision, not more matrix objects for their own sake.
