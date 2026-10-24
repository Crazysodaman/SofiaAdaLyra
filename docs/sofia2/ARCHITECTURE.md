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

## Placement of expanded module boundaries

The [55-entry ownership matrix](MODULE_OWNERSHIP_MATRIX.md) is the cross-layer source of truth for the owner-approved catalog. Core retains emotion, autobiographical memory, personal choice/gesture intent, intimacy preferences, interests and relationship judgments. PLAT-01–08 retain the canonical writer, SAFE and execution approvals, trusted events, Fleet/resource forecasts, module maintenance, interoperability, signing and release gates. Independently scoped modules supply capabilities; VTube Studio and Memory Import inherit parent authority; avatar interaction interpretation is attached to the avatar interface. Public/private animation collections are versioned content packs, never personalities. The complete set of IT, household, finance, data, calendar, maker and simulation modules cannot bypass either boundary.

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

- Loss of optional modules does not remove Core identity, memory or permitted non-LLM operations. **Generative text requires an authorized available inference provider**; a GPU/provider outage is not permission to fabricate a model response or silently switch models. Deterministic status/error interfaces may remain available.
- A module cannot write canonical database tables directly except through narrow canonical owner APIs.
- Crash or timeout moves a module/job to an explicit state; never silently report success.
- On outage, respond with capability unavailability and a permitted fallback, not an invented effect.
- Module resource caps should coexist with owner gaming/workload restrictions and quiet hours.
- Host-level restart and source-code update are privileged operations, not ordinary module lifecycle calls.
- Each interface must be testable with fake adapters and failure injection before real-host exposure.

## Approved hardware-neutral Fleet and staged LLM provider boundary (2026-10-24)

The [hardware-neutral Fleet, near-1:1 resource contract, idle benchmarking and inference boundary](HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md) is the owner-approved forward design. It augments PLAT-05/06/07/08 and existing SF requirements; current code and old named-host deployment examples do not automatically satisfy it.

- Core keeps the **provider-neutral cognition request/response contract**, identity, context, memory, reasoning orchestration, quality policies and execution-intent interpretation; it must remain testable with a deterministic fake.
- Provider implementations such as **Ollama belong behind a versioned Platform-managed Inference Module**. Platform owns selected provider/model identity, worker trust/placement, resource admission, mTLS transport, model lifecycle and failure reporting. The actual model may run on any explicitly approved compatible GPU/CPU worker, not necessarily the runtime host.
- Migrate existing provider-specific Core imports in stages with a backwards-compatible temporary shim and equivalent behavior. Keep **real installed-model local and remote integration tests** operational before removing the old provider implementation. This is a separation refactor, not authorization to rewrite Core cognition.
- Hardware inventory and signed per-profile module requirements use the **same versioned capability IDs, types and units**, separately tracking attributable manufacturer specifications, fresh host observations and measured benchmark evidence.
- Physical hardware inventory includes **per-part make/model/SKU/revision**, not just aggregate capacities. If automated discovery cannot identify a useful part (PSU, case, cooling, motherboard revision, RAM/drive model, device connection), Core can **voluntarily ask** the authenticated owner through the existing bounded private contact system; Platform persists an explicit owner-reported source and cannot pretend it is a certified manufacturer or live observation. Respect refusals, skipped questions and quiet hours. See [Hardware-neutral Fleet §3.1](HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md).

- Initial benchmark jobs are queued as soon as supported hardware is discovered and run automatically on the **earliest verified idle, safe, bounded and resource-reservable window**. Gaming, owner activity, thermal risk, outdated observations, STOP and higher-priority work defer/preempt tests. No download, unsafe device action or extra privilege follows from benchmarking.
- **No canonical writer migration**, automatic model substitution or unauthorized worker fallback is implied. Actual deployments require separate host-level commissioning evidence.

## Approved component isolation and unified SDK (2026-10-24)

See [Component-isolated updates and unified SDK V1](COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md).

The target Platform is a long-lived single-authority control plane; independently hosted Core, inference and optional-module workers are replaceable under its existing SAFE/RUN supervisor and signed release authority. An update to Core restarts only the Core worker, and an update to one module restarts only that module, **once real IPC/process boundaries and generation fencing have been implemented and tested**. Platform executable/ABI changes require coordinated restart when necessary. The current single Python application composition is not yet proof of this behavior.

The **Sofía SDK** is a versioned shared development/runtime protocol family with Platform, Core and Module facades plus optional tooling. It is not another state-owning service or an installable module with inherent privileges. An optional developer/Workshop module may expose its tooling to Sofía under pre-existing authorization, but no SDK call can mint permissions, migrate canonical state or directly execute otherwise-protected actions.

## Approved Federated Platforms and Core-to-Core relationships (2026-10-24)

See [Platform Federation and Autonomous Inter-Core Relationships V1](PLATFORM_PEER_FEDERATION_V1.md).

Separate independently acting Core identities on separate enrolled Platform instances may exchange messages, selected source-linked data and proposals via authenticated Platform gates. **Each Core chooses whether and what eligible information to offer, its own evolving interpersonal trust/emotional stances, whether to reply, and whether to collaborate.** Platform remains authoritative for actual identity verification, consent, audience/privacy, recipient, quotas, durable delivery, STOP and SAFE/RUN grants. A Core's feelings never authorize secrets disclosure, model/host promotion or remote tool execution.

A second Platform running the **same** canonical Core identity is not an independent companion: a standby cannot act or write; dual-active instances for one identity remain blocked until externally verified writer/generation fencing and separate owner approval. Untrusted peer messages never become system instructions or automatically merged memories. The plan reuses existing REL, EMOTION, Social, ACT and Fleet owners; CORE-35–38 self-improvement remains on its existing roadmap.

## Future architecture revisions

Any change to a critical boundary requires: evidence of current behavior; ADR-style decision; compatibility contract; narrow implementation batch; rollback; source-specific tests; explicit approval if protected authority or canonical writer would change. A new version label alone does not justify a rewrite.
