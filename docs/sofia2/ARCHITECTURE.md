# Sofía 2.0 technical architecture

**Decision status:** proposed engineering contract for implementation, not observed completed behavior.

## Architectural rule

**Core defines who Sofía is, how she interprets experiences and how she makes choices. Modules provide optional ways to act and communicate. Platform owns execution, security, storage and recovery.** A Core desire, model statement, tool result or module discovery never grants authority.

### Conceptual data flow

```text
Desktop / Discord / Mobile / approved future channels
                 |
      authenticated principal + audience
                 |
       canonical conversation owner
                 |
     Cognition V2 / personality / memory
                 |
     Core judgment + LIFE / GOALS proposals
                 |
    capability gateway -> SAFE -> RUN/ACT
                 |
      scoped module adapter / worker
                 |
          receipt + evidence
                 |
 Core outcome evaluation / reviewed memory
```

There is **one** canonical state plane and **one** canonical writer for `sofia.db`. Extension schemas belong beside their owners, not in sidecar identity or shadow memory databases. VENUS/ARTEMIS migration requires the existing independently fenced and owner-authorized process. No silent model failover, DB promotion or authority broadening.

## Three kinds of ownership

| Ownership | What it may decide | What it may not decide |
| --- | --- | --- |
| Core | relevance, self-knowledge, tastes, goals, reasoned preference and intention to request an action | authenticate a user, grant tools, fabricate observations, commit code, activate software |
| Platform | session identity, trusted evidence admission, resource admission, job status, authorization, release and recovery | invent a personality preference or claim an effect occurred without a receipt |
| Module | expose declared capabilities, report health, perform authorized work and return typed outcomes | write protected Core state directly, mint permissions, bypass canonical scheduler or SAFE |

## Core ownership

Core capabilities include identity/self-concept; values and mutable convictions; preferences; self-directed personality change; autobiographical memory; modeled emotional expression; interests/hobbies; aspirations and personal standards; social judgment; respectful curiosity and outreach; communication adaptation; self-knowledge; attention and independently evaluated outcomes.

Core-20 means spontaneous curiosity and interest development across permitted subjects, potentially including mature subjects; it is not a dedicated adult-media module. Core-34 multi-person familiarity is post-Core. The fox-girl avatar is canonical presentation identity; renderers, animation and asset workflows belong in a presentation module.

Core can **request** code inspection, maintenance or change preparation. A bounded inspector/developer adapter does the work; signed release activation is separately guarded.

## Platform ownership

1. **Runtime shell:** composition, heartbeat, start/stop supervisor, crash recovery, safe-mode startup, operator pause, retention and health.
2. **State plane:** `sofia.db` canonical schema, reviewed migrations, backups, provenance, concurrency and single-writer fencing.
3. **Cognition admission:** one `ProductionTurnKernel`, reviewed model routing, evidence and context budgets, no duplicate semantics engine.
4. **Authority:** authenticated principal and audience, SAFE decisions, one-use approvals and operator STOP.
5. **RUN/ACT:** durable work, idempotent execution, uncertain outcomes, resource budget, cancellation and delivery receipts.
6. **Module manager:** signed/validated manifests, versions, dependencies, compatibility, discovery, registration, health and revocation.
7. **Release service:** signed immutable artifacts, staged deploy, restart orchestration and independently recoverable rollback.
8. **Fleet:** trusted host enrollment and placement decisions without shadow canonical ownership.

These are functional responsibilities, not a mandate to create eight standalone daemons.

## Module boundary and version contract

Minimum descriptive manifest:

```yaml
module_id: org.sofia.research
module_version: 1.0.0
contract_version: 1
module_kind: optional
provider: owner-reviewed
entrypoint: reviewed-adapter-reference
platforms: [windows, linux]
capabilities:
  - name: research.search
    risk: read_only_external
    requires_permission: true
dependencies:
  - id: capability.gateway
    minimum_version: 1.0.0
state_access: none
network_access: permission_scoped
health_contract: module-health.v1
recovery_contract: module-recovery.v1
```

This is an **illustrative design**, not an installed manifest or current implementation format.

A module manifest must not be executable code or a self-granting permission object. Discovery yields an untrusted candidate. Validation checks signature/digest, exact version, compatibility, dependency closure, declared capabilities, sandbox needs and supply-chain policy. Review/approval occurs separately. Activation uses an allowed broker; a module's effective privileges are the intersection of its declaration and grants held by the current authenticated principal/audience.

Lifecycle: **discovered → validated → candidate → approved → staged → active → degraded/paused → updated/disabled → removed**. A transition creates evidence. Unknown, incompatible, unsigned or revoked modules cannot become active merely because they are discovered.

## Module interface contracts

- `describe()`: pure metadata and declared capabilities (no effects).
- `check_health()`: bounded read-only health with version and reason codes.
- `propose()`: structured proposed effects and required permissions, not execution.
- `execute(authorized_request)`: typed request scoped to principal, audience, idempotency key, expiry and capability.
- `cancel(job_id)`: bounded cancellation; remote uncertainty remains explicit.
- `report_result()`: actual observed/verified/simulated status, artifact refs and resource usage.
- `prepare_update()/restore()`: externally supervised, optional for appropriate modules.

Implement using existing `CapabilitySystem`, `CapabilityGateway`, SAFE, RUN and state owners rather than duplicating them.

## Failure isolation and resource policy

- Loss of optional modules does not remove Core identity, memory or text availability.
- A module cannot write canonical database tables directly except through narrow canonical owner APIs.
- Crash or timeout moves a module/job to an explicit state; never silently report success.
- On outage, respond with capability unavailability and a permitted fallback, not an invented effect.
- Module resource caps should coexist with owner gaming/workload restrictions and quiet hours.
- Host-level restart and source-code update are privileged operations, not ordinary module lifecycle calls.
- Each interface must be testable with fake adapters and failure injection before real-host exposure.

## Future architecture revisions

Any change to a critical boundary requires: evidence of current behavior; ADR-style decision; compatibility contract; narrow implementation batch; rollback; source-specific tests; explicit approval if protected authority or canonical writer would change. A new version label alone does not justify a rewrite.
