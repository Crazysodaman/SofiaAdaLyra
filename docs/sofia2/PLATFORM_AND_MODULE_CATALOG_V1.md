# Sofía 2.0 — Platform-first architecture and module catalog (owner design v4)

**Decision record date:** 2026-10-21 (America/Chicago)  
**Repository baseline:** `Crazysodaman/SofiaAdaLyra`, branch `main`, observed `e5e4407e7da725b51b17eee344ac54a12ec59d1b`  
**Status:** Owner-approved catalog **design only**, not a claim of implementation or Gate completion. V4 includes the existing module profiles, Fleet forecasts, interoperability and maintenance contracts, all 41 earlier entries plus 14 additions. §8 platform extensions remain proposed until separately accepted.  
**Repository document:** `docs/sofia2/PLATFORM_AND_MODULE_CATALOG_V1.md` (owner-authorized publication).  
**Development order:** Platform first (PLAT-01–08), then Companion (RM-*), then optional modules. OpenCode is sole writer for its active local Core tree; publishing this document does not authorize deployment, edits to that tree, DB migration, service restarts, or subsequent GitHub changes.

## 0. Non-negotiable invariants

1. Core owns identity, cognition, autobiographical memory, personality, motivations and expression *intent*. Modules implement capabilities, not additional identities.
2. Platform owns authentication, SAFE, RUN/ACT, single-writer state, host trust, resource grants, release and lifecycle. Model-generated text, a manifest, or module discovery grants **zero** authority.
3. Exactly one canonical `sofia.db` writer and lineage at a time. Module schemas pass through canonical owner APIs; large artifacts can use content-addressed external files.
4. A module can be available, installed, healthy, and production-certified but still **not** authorized for a particular request. Separate all four states.
5. Optional module crashes, stale sensors, remote network partition, resource shortage and unsupported OS must never cause fake effects, duplicate external writes, duplicate Core runtimes or a silent substitute model.
6. Approval must be tied to authenticated principal, audience, exact target, capability, effect/parameters, expiration, revocation and, for protected actions, a one-use receipt.
7. Never move the canonical writer under ordinary module relocation. Physical device controllers are pinned to the enrolled device host; relocate compatible *planning/simulation* workers independently.
8. Readiness is a versioned evidence verdict for an exact module+capability+platform profile, never asserted by a module about itself.

## 1. Platform work packages (implement and verify before Companion)

These are logical platform owners, **not** a prescription for eight independent daemons.

| ID | Service | Mandatory V1 interfaces | Key Gate-4 test set |
| --- | --- | --- | --- |
| **PLAT-01** | Runtime Supervisor | `runtime.status`, `runtime.start_component`, `runtime.stop_component`, `runtime.pause`, `runtime.resume`, `runtime.read_health`, `runtime.reconcile_startup` | Optional-module crash, boot with modules disabled, repeated-crash quarantine, restart preserves Core and singleton ownership |
| **PLAT-02** | Canonical State & Recovery | `state.namespace_open`, `state.write_transaction`, `state.migrate_plan`, `state.backup`, `state.verify_backup`, `state.restore_plan`, `state.audit_lineage` | Concurrent writes fenced, migration interruption, backup validation, no sidecar identity DB, DB restore no duplicate writer |
| **PLAT-03** | Security, SAFE & Identity | `auth.principal`, `auth.audience`, `policy.evaluate`, `grant.inspect`, `grant.revoke`, `approval.verify`, `operator_stop.read` | Spoofed principal denied, audience boundary, expired/revoked grants, STOP under load, no token leakage |
| **PLAT-04** | RUN/ACT Job & Effect Broker | `jobs.submit`, `jobs.lease`, `jobs.cancel`, `jobs.inspect`, `jobs.reconcile`, `effect.verify`, `resource.reserve` | Dispatch/crash window, request dedupe, lease expiry, cancelled-but-unknown effect, no unsafe blind retry |
| **PLAT-05** | Module Manager & SDK | `module.discover`, `module.validate`, `module.plan_install`, `module.stage`, `module.activate`, `module.pause`, `module.resume`, `module.disable`, `module.quarantine`, `module.plan_update`, `module.plan_remove`, `module.health`, `module.describe` | Malicious manifest, bad signature, conflicting registration, dependency cycle, partial activation, crash isolation and rollback |
| **PLAT-06** | Model & Compute Orchestrator | `compute.measure`, `compute.plan`, `compute.reserve`, `compute.release`, `model.probe`, `model.load`, `model.unload`, `model.route_report` | GPU contention, game activity, pinned model digest, unsupported destination, interrupted unload, no silent provider swap |
| **PLAT-07** | Fleet, Device & Dynamic Placement | `fleet.enrolled_hosts`, `fleet.observe_capacity`, `placement.plan`, `placement.admit`, `placement.checkpoint`, `placement.drain`, `placement.activate_remote`, `placement.verify`, `device.acquire_lease`, `device.release_lease` | Unknown host denied, host partition, insufficient RAM/VRAM, false capacity, simultaneous worker fences, pinned hardware not moved |
| **PLAT-08** | Observability, Certification & Releases | `diagnostics.trace`, `diagnostics.health`, `readiness.evaluate`, `readiness.evidence`, `release.verify`, `release.stage`, `release.plan_activation`, `release.plan_rollback` | Forged test evidence, SHA mismatch, unsigned artifact denial, interrupted upgrade, exact-revision audit, release fallback |

### 1.1 Shared facilities (all adopted, implemented **inside** the above owners unless evidence warrants a standalone service)

| ID | Facility | Owner |
| --- | --- | --- |
| SF-01 | Typed Event Broker (principal/audience-scoped subscriptions, bounded delivery, replay semantics) | PLAT-04/02 |
| SF-02 | Artifact Registry (content hash, permissions, metadata, revisions, lifecycle) | PLAT-02/08 |
| SF-03 | Resource Arbiter (compute, GPU, CPU/RAM, storage, bandwidth, priorities) | PLAT-04/06 |
| SF-04 | Secrets Broker (vault refs, rotation, selective disclosure and redaction) | PLAT-03 |
| SF-05 | Device Broker (microphones/cameras/USB/serial, leases and hardware identity) | PLAT-07 |
| SF-06 | Contract/Conformance Harness (schemas, compatibility, fakes, fault injection) | PLAT-08 |
| SF-07 | Hardware Resource Broker (host-level arbitration, exclusive devices and GPU capacity) | PLAT-07/06, consolidated with SF-03/05 |
| SF-08 | Module Dependency Graph (installation/activation order, cycles, version constraints) | PLAT-05 |
| SF-09 | Module Health Dashboard (owner-visible status, versions, resource costs, location) | PLAT-08, surfaced by RM-DESKTOP |
| SF-10 | Automatic Recovery Planner (bounded restart, relocate, quarantine or approval) | PLAT-01/07 |
| SF-11 | Module Compatibility Testing (OS/arch/ABI/capability/device/host gates) | PLAT-05/08 |
| SF-12 | Unified Module Store (approved signed packages, version cache, immutable bundles) | PLAT-05/08 |
| **SF-13** | **Module Profiles (owner approved)**: named operational modes, profile-specific schemas, grants, limits and certification | PLAT-05/03/08 |
| **SF-14** | **Fleet Resource Forecasting (owner approved)**: demand/hardware headroom projections and advisory placement plans | PLAT-07/06/04 |
| **SF-15** | **Module Interoperability Testing (owner approved)**: contract pairs, multi-module workflows, failure and upgrade compatibility matrices | PLAT-08/05/04 |
| **SF-16** | **Per-Module Maintenance Profile (owner approved)**: versioned health expectations, recovery playbooks, support/patch windows, diagnostics, relocation compatibility, and escalation | PLAT-05/01/08, drawing on PLAT-07 |

SF-07 intentionally consolidates with SF-03/SF-05 at implementation time: **sixteen product facilities do not require sixteen duplicate schedulers or daemons.** SF-13–16 are explicitly adopted requirements and should extend the existing platform owners.

### 1.2 Shared module SDK envelope contracts

**Manifest V1** fields: `schema_version`, `module_id`, `version`, `kind`, `publisher`, `artifact_digests`, `signature/trust_ref`, `supported_os_arch`, `api_range`, `capability_schemas`, `dependency_constraints`, `isolation_profile`, `resources`, `device_requirements`, `placement_mode`, `state_namespace`, `migration_contract`, `health_contract`, `update_rollback_contract`, `profiles[]`, `interoperability_contracts[]`, `maintenance_profile_ref` (signed or digest-pinned). A manifest is data only, never executable or self-authorizing.

**Authorized request V1** fields: `request_id`, `job_id`, `module_id/version`, `capability/schema`, `active_profile_id/version`, `authenticated_principal`, `audience`, `target_resource`, `params`, `effective_grant_ref`, `approval_ref_if_needed`, `idempotency_key`, `expiry`, `expected_effect`, `correlation_id`. The platform originates identity/authorization fields, never freeform module or LLM input.

**Result V1** fields: `request_id`, `attempt_id`, `module_instance_id`, `active_profile_id`, `status`, `effect_class`, `observed_effect`, `verification_method`, `source_and_receipt_refs`, `artifact_hashes`, `resource_usage`, `error_class`, `retry_safety`, `completed_at`. Status enum: `DENIED`, `UNAVAILABLE`, `FAILED`, `CANCELLED`, `OUTCOME_UNKNOWN`, `SUCCEEDED_REPORTED_UNVERIFIED`, `SUCCEEDED_VERIFIED`. RUN alone settles durable job status.

**Observation/Event V1** fields: `event_id`, `producer_ref`, `subject_ref`, `principal/audience_scope`, `observed_at`, `recorded_at`, `fresh_until`, `classification`, `evidence_state`, `schema`, `payload_ref`, `correlation_id`, `receipt_ref_if_any`. An event does not authorize anything and may not silently become autobiographical memory.

**Health V1** fields: `module_instance_id`, `host_identity`, `version`, `lifecycle`, `health`, `checked_at`, `last_heartbeat_at`, `reason_codes`, `blocked_dependencies`, `capability_availability`, `current_resource_usage`, `readiness_ref`, `maintenance_profile_ref`, `maintenance_overdue`; no invented green status when unreachable.

### 1.3 Module lifecycle

`DISCOVERED → VALIDATED → REVIEW_PENDING → APPROVED → STAGED → INSTALLED_DISABLED → ACTIVATING → ACTIVE`.

Orthogonal health: `HEALTHY`, `DEGRADED`, `UNREACHABLE`, `FAILED`, `UNKNOWN`. Controlled transitions: `ACTIVE → DRAINING → PAUSED / INSTALLED_DISABLED`; a failed security validation or crash-loop enters `QUARANTINED`. `UPDATING` and `ROLLING_BACK` are supervised operations with exact artifact and state receipts. `REMOVED` only after dependency and retention checks.

All changes need an expected registry revision, actor, authorized operation ref, event timestamp and persisted transition receipt. No half-registered capability remains callable after failed activation. Disabled/uninstalled modules retain owner data only per reviewed retention rules.

### 1.4 Distributed placement and migration (mandatory platform feature)

**Placement modes:**

- `PORTABLE_STATELESS`: safely start compatible instances on any approved host; a request still executes once.
- `CHECKPOINT_RESTART`: drain and checkpoint job state, release old worker lease, restart on approved destination, resume from verified state.
- `HOST_PINNED`: hardware controllers, desktop input/audio attached to a live user, and device-locked integrations remain on that host; their *planning* workers can move separately.
- `CANONICAL_PINNED`: Core canonical writer, identity/approval authority and state promotion are outside general placement logic.

**Placement plan fields:** pinned package+model digest, source/destination trusted host IDs, OS/arch/runtime compatibility, current and projected CPU/RAM/GPU/VRAM, device binding, disk/net needs, latency constraints, gaming/busy state, current lease, estimated interruption/copy cost, plan expiry, policy/ref, rollback target.

**Default placement algorithm:**
1. Exclude unenrolled/revoked/incompatible hosts and non-movable workloads.
2. Refuse if freshness, available memory/VRAM, device availability, consent, resource reservation or privacy policy is unknown.
3. Compare suitability using measured headroom, actual workload, network latency and transfer cost. Do not rank solely by current CPU percent.
4. Require sustained pressure and hysteresis, a benefit threshold, minimum host residence and relocation cooldown before suggesting or automatically moving an approved low-risk worker.
5. Checkpoint/drain; fence old instance; stage exact signed artifacts and allowed references; acquire destination lease; start and health-check the new worker; reconcile exact RUN job and receipts.
6. If validation or handoff fails, preserve truthful `PAUSED`/`OUTCOME_UNKNOWN` states and perform a verified safe rollback if possible. Never run two live effectors on the same idempotency lease.

**Never do automatically:** transfer canonical `sofia.db` ownership, enroll new hosts, widen privileges, use a different cognitive model, copy forbidden personal data to another node, provision a VM, migrate live serial/physical actuators, or deploy unsigned code.

**Acceptance:** placement on two fake hosts, Windows/Linux profile denial, busy Venus with no eligible destination (pause), compatible destination (move), disk/VRAM refusal, network partition after dispatch, source resumption with stale lease rejected, no duplicate physical command, and operator STOP mid-relocation. Live cross-host trial requires owner approval.

## 1.5 SF-13: Module Profiles (owner-approved requirement)

**Purpose:** A single installed module may support several **independently certified operation profiles**. A profile is more than a cosmetic UI mode: it narrows the exposed capabilities, effective grants, sandbox, resource budget, allowed hosts, devices, data scope, and recovery policy. Profile selection may never enlarge authority by itself. The effective permission is the intersection of the module manifest, the selected profile, the authenticated caller's scope, the current SAFE decision, and the executor's last-moment checks.

**Standard profile vocabulary** (module may implement a documented subset):

| Profile | Permitted type of work | Examples | Required boundary |
| --- | --- | --- | --- |
| `OBSERVE` | Bounded, approved reads | Fleet telemetry, JMRI roster, sensors | Source identity, timestamps, stale/unknown state, audience filters |
| `SIMULATE` | Synthetic/offline experiments | Gaia gait, virtual turnout planning | Clearly marked simulation; zero physical effects |
| `ADVISORY` | Analysis + action proposals | VM repair plan, load placement, patch review | No mutation; proposals require independent review/authorization |
| `EXECUTE_SCOPED` | Specific preauthorized reversible effects | Approved job in an isolated workspace | Exact grant, target, expiry, STOP, RUN receipt; no privilege expansion |
| `SUPERVISED` | Human-present or otherwise specifically protected action | Gaia motor test, locomotive movement, VM restore | Fresh approval and independently enforced physical/host safety |

**Profile V1 metadata:** `profile_id`, `profile_version`, `module_id/version/digest`, `available_capability_ids`, `permission_ceiling`, `data_classes`, `allowed_principals/audiences`, `resource_envelope`, `allowed_host/device_classes`, `isolation_profile`, `lifecycle_policy`, `required_approval_class`, `verification_profile`, `readiness_ref`.  Profile selection is a validated state transition with revision and receipt. A module cannot add profiles by returning a new string at runtime.

**Interfaces:** `module.profiles.list`, `module.profiles.describe`, `module.profiles.plan_switch`, `module.profiles.request_switch`, `module.profiles.current`, `readiness.evaluate_profile`. Switching to a narrower profile drains and cancels incompatible queued work. Switching to a more privileged profile *never* inherits an earlier read-only grant; the requested effect requires fresh applicable authorization. Disable a profile independently of the module when evidence is revoked. UI displays the active profile, privileges and last certification evidence.

**Gate-4 examples:** `SIMULATE` cannot produce SSC-32 pulses; `OBSERVE` cannot call JMRI `power.set`; a revoked scope fails during in-flight profile switch; jobs from an old profile cannot resume with expanded capabilities; per-profile tests, exact source SHA and target OS/host profiles are pinned. A module can be `PRODUCTION READY` in `OBSERVE` while `SUPERVISED` is still `BETA` or `BLOCKED`.

## 1.6 SF-14: Fleet Resource Forecasting (owner-approved requirement)

**Purpose:** predict near-term workload pressure and compare `stay`, `defer`, `throttle`, and `move` actions before affecting a live host. Forecasts are **advisory** to the deterministic placement policy; a prediction is never permission, an observation, or proof of real capacity.

**Inputs:** measured per-host CPU, RAM, GPU, VRAM, storage IO, temperature if genuinely available, network/latency, workload class, process/device locks, foreground gaming/busy state, timestamps/freshness, and declared hard constraints. Distinguish missing readings from zero load. Only signed/enrolled host sources may inform placement. Trainable predictions must follow ML-008/011–014 and ML-027–029 eligibility, lineage, shadow evaluation and rollback requirements.

**Interfaces:** `fleet.forecast.collect`, `fleet.forecast.explain`, `fleet.forecast.predict(host_id, horizon)`, `fleet.forecast.compare_plan`, `fleet.forecast.report_outcome`, `fleet.forecast.drift_status`. Suggested initial horizons are 5/15/30 minutes, configurable after measurement. Begin with simple last-value/EWMA/threshold baselines; ML models must beat the baseline on held-out chronological outcomes before being promoted even to advisory use.

**Placement rules:** deterministic guardrails always dominate. Require fresh telemetry, hard RAM/VRAM headroom, device availability, verified package/model digest and grants, privacy/data locality, measured destination performance, expected transfer cost, and a minimum benefit margin. Use hysteresis, minimum residence and cooldown to avoid ping-pong. Do not migrate a running canonical writer, owner authentication authority, or attached actuator; do not silently switch to a different model. If confidence or capacity is unknown, keep, pause or reject instead of guessing.

**Forecast record:** `{forecast_id, model_or_baseline_id, version/digest, host_id, issued_at, horizon, input_refs, freshness, predicted_quantities, uncertainty, constraints, suggested_action, planned_cost, admitted_action_ref_or_null, later_observed_outcome_ref_or_null}`. Raw host telemetry retention and training rights follow existing owner policies.

**Gate-4 examples:** burst load, stale telemetry, cold-start unknown host, GPU gaming interference, bad forecasts, time drift, hysteresis/no oscillation, resource quota refusal, destination not enrolled, network partition and mismatched model digest. Benchmark MAE/false positives, actual avoided contention, migration cost, p95 latency and baseline comparison. Live host migration and long-term effectiveness remain distinct from offline Gate 4.

## 1.7 SF-15: Module Interoperability Testing (owner-approved requirement)

**Purpose:** test combinations of independently working modules before certifying a *workflow*. A `PRODUCTION READY` module pair does **not** imply their interaction is certified.

**Contract:** maintain a versioned `compatibility_matrix` keyed by both module IDs, exact versions/digests, profile IDs, interface/ABI schema versions, OS/host combinations, principal/audience scope, resource reservations and tested source revisions. Each workflow has a pinned expectation of source events, authorization, result receipts, ordering, cancellation and degraded recovery. Include at least the following suites:

| Pair/workflow | Critical acceptance |
| --- | --- |
| Voice ↔ Avatar | Actual playback timestamps match lip/gesture animation; mute/interruption stops visuals correctly; renderer outage preserves text |
| Creative ↔ Avatar | Generated assets require verified hashes, layered rig compatibility and display-category approval before activation |
| Sensors ↔ Vision ↔ Homelab | Observation source identity/freshness/consent preserved; no raw imagery secretly enters Core memory |
| Homelab ↔ IT tools | Resource targeting, exact SAFE/RUN grant and operation receipt; missing endpoint remains unknown |
| Gaia ↔ Sensors ↔ Fleet | Simulator and physical control separated; stale feedback and disconnected serial controllers fail safe |
| Trains ↔ JMRI ↔ Sensors | Track state freshness, turnout/occupancy unknown handling and locomotive stop independently enforced |
| Browser ↔ Research ↔ Documents | Untrusted webpage instructions never become system instructions or authority; provenance survives export |
| Desktop ↔ Discord ↔ Mobile | One canonical conversation, safe audience handoff, deduplicated delivery and revocation |

**Interfaces:** `compat.plan_matrix`, `compat.run_fixture`, `compat.record_run`, `compat.compare_versions`, `compat.report_workflow_readiness`. Conformance tests use fakes and fault injection first, then approved OS/hardware trial tiers. Every test records exact source/package revisions and fixtures, including negative controls for a single failed/slow/compromised module. Cross-module compatibility decisions may block an otherwise healthy update until a safe adapter or rollback exists.

**Gate-4 examples:** mismatched schemas, incompatible profile combinations, duplicated event delivery, one module crashes mid-workflow, resource oversubscription, audience leakage, stale receipts, mixed-version upgrade/rollback and physical action after STOP. Independent review must distinguish fixture-only from real-hardware coverage.

## 1.8 SF-16: Mandatory per-module maintenance profile (owner-approved requirement)

**Design choice:** Do **not** create a second "self-diagnostics AI" or shadow Core. Core may notice issues, reason about possible causes, choose whether to investigate, propose remedies and review verified outcomes. The platform owns health measurement, diagnostics, maintenance policy, authority, action execution and actual effect verification. A module may supply **untrusted status and domain-specific probes**, but never certify its own repairs, suppress errors, grant authority or write Core memory.

**Every independently installed module version MUST ship with an immutable maintenance profile** linked by digest to its package manifest. The module's operator/owner may maintain separately authorized deployment overrides that only *narrow* automatic activity, change schedules within policy or provide target-specific settings; overrides never authorize additional effects or replace signed package identity. Do not confuse this maintenance profile with SF-13 **operation profiles** (`OBSERVE`, `SIMULATE`, etc.): each operation profile inherits the maintenance constraints and may narrow them further.

**Required `sofia.module.maintenance.v1` data:**

| Area | Required data |
| --- | --- |
| Identity and support | `module_id`, `module_version`, `artifact_digest`, `profile_version`, maintainer/source, support lifecycle (`supported`, `deprecated`, `end_of_life`), evidence and documentation refs |
| Dependency maintenance | exact supported platform/API/ABI/dependency ranges, current compatibility-lockfile ref, known blockers and compatible upgrade path |
| Health probes | read-only `probe_id`, timeout, permitted observation scope, probe cadence/freshness, severity mapping and truthful `unknown` behavior |
| Reliability policy | restart budget, exponential backoff/circuit breaker, cooldowns, quarantine thresholds, max recovery time, conditions requiring owner attention |
| Resources and placement | nominal/max RAM, CPU, GPU, VRAM, disk/network; allowed host classes; movable/pinned mode; measured relocation and revalidation requirements |
| Repair runbook | recognized failure classes, diagnostic collection, proposed repairs, explicitly permitted low-risk automatic actions, approval-required actions, verification predicates and rollback |
| State and recovery | namespace owner, backup/restore applicability, migration compatibility, durable job reconciliation, retention, export/deletion and safe disable/removal plan |
| Updates and security | patch-review cadence, signed package/SBOM/vulnerability refs, change window, staged update/canary policy, revocation response, rollback constraints |
| Privacy and logs | classification, retention caps, redaction of credentials/conversation and sensitive device data, audience/principal eligibility of diagnostics |
| Maintenance evidence | last successful checks, failed checks, reason codes, last review timestamp, update/security advisories, reviewer and independent verification refs |

**Typed read-only interfaces:** `module.maintenance.describe`, `module.maintenance.check_due`, `module.maintenance.probe`, `module.maintenance.recommend`, `module.maintenance.history`, `module.maintenance.support_status`. **Effectful operations:** `module.maintenance.plan_repair` returns an inert plan; `module.maintenance.request_repair` submits a request to the *existing* SAFE/RUN owner; `module.maintenance.verify_repair` reads independently observed postconditions. No direct module-to-OS process execution, no new permissions store and no autonomous release activation.

**Default policy:** Observe/probe when already permitted and resource-admitted; recommend on problems; **never** auto-install, auto-update, downgrade, migrate sensitive data, change privileges, repair an unverified physical device or restart a production-critical component without its separate authorization. Only an explicitly preapproved, reversible and bounded operation may be automated. A missing, outdated or invalid maintenance profile blocks **new module activation and Production Ready certification**, while allowing separately reviewed safe disable or recovery actions for an existing installation.

**Example metadata (proposal, not a validated package):**

```yaml
schema: sofia.module.maintenance.v1
module_id: org.sofia.creative
module_version: 1.0.0
profile_version: 1
artifact_digest: <matching-signed-manifest-digest>
support_status: supported
health:
  probes:
    - id: creative.backend.status
      read_only: true
      timeout_seconds: 5
      maximum_age_seconds: 120
recovery:
  retry_limit: 2
  backoff_seconds: [30, 120]
  on_repeated_failure: quarantine
  automatic_actions: []
  protected_actions: [process.restart, module.update]
  verify_effect: backend_health_and_job_receipts
state:
  owner: canonical_platform_state_api
  retention_policy_ref: <reviewed-policy-ref>
updates:
  signatures_required: true
  require_compatibility_tests: true
  require_rollback_plan: true
placement:
  movable_modes: [checkpoint_restart]
  required_revalidation: [artifact_digest, host_compatibility, current_grants]
```

**Health/maintenance status is not product readiness.** A healthy module can be uncertified; a Production Ready package can become degraded, obsolete, quarantined or affected by a newly disclosed vulnerability. Display separate `readiness`, `health`, `support_status`, `last_maintenance_review`, `maintenance_due`, `deployment`, and `allowed_action` fields. Never overwrite original Gate 1–5 evidence due to a routine health event; critical defects can block current release eligibility with their own reason and timestamp.

**Gate-4 tests:** missing/forged/outdated maintenance profile rejected; unknown probe does not count healthy; health probe hangs without blocking Core; threshold crash loop quarantines only that module; rollback preserves module data; malformed repair advice cannot call privileged handlers; STOP/revocation blocks approved maintenance before effect; upgrade changes a dependency and fails compatibility check; stale Fleet data refuses relocation; sensitive logs stay redacted; verification refuses to infer repair success from a restart command alone. Hardware modules additionally test disconnected device and independent physical failsafe, with supervised live trials tracked separately.

## 1.9 Hardware-neutral Fleet, one-to-one resource contract and idle benchmarks (owner-approved 2026-10-24)

**Authoritative supplemental decision:** [Hardware-neutral Fleet, resource compatibility, idle benchmarking and inference boundary V1](HARDWARE_NEUTRAL_FLEET_AND_INFERENCE_CONTRACT_V1.md). This is approved **design**, not implementation or test evidence.

- **Hardware is interchangeable:** physical hosts, VMs, GPUs and peripherals use enrolled immutable IDs, capability/resource observations and current host roles; "Venus" and "Artemis" are examples, never placement constants. Runtime/canonical-writer authority is separately fenced; intended VM/host is a deployment choice.
- **Near-1:1 schema:** host supply and signed per-profile module demand share typed keys, predicates, units, source identity, TTL and explicit UNKNOWN. Cover identity/trust, OS/ABI, CPU, RAM, individual GPUs/VRAM/backends, storage, network, physical devices, service/model versions, virtualization/parent relationships, health/availability, thermal/activity, recovery and placement affinity.
- **Three evidence classes:** persist attributable manufacturer-stated specifications, authenticated machine-observed inventory/live telemetry, and exact-workload measured benchmarks separately. Do not promote a self-report or stale value to a verified manufacturer fact or assume aggregate VRAM is usable by one GPU.
- **Automatic earliest-safe benchmarking:** on first enrollment, hardware/driver/runtime/model changes or expired performance evidence, enqueue durable staged CPU, RAM, GPU, storage, network and exact-model inference benchmarks; run at the first **verified idle** and sufficiently safe, resource-reservable interval. Pause/preempt for user input, gaming, model inference, overheating, STOP, reservations and stale activity observations. No destructive tests, model downloads, physical effects, network saturation or production-state writes without independent approval.
- **Measured matching:** deterministic compatibility and SAFE/resource admission always precede benchmark-based placement ranking; forecasts and benchmark results are advisory. Every decision records exact resource IDs, observations, model/package digests, reservations and refusals.
- **Test-preserving LLM boundary:** keep provider-neutral cognitive contracts in Core, move Ollama/provider details behind a Platform-managed inference module, retain fake/stub and *real Ollama* test paths throughout staged migration, and verify remote pinned-mTLS worker inference on a disposable-state VM before dropping legacy imports. This refactor does not by itself certify Core or Platform.
- **Implementation:** HNF-01–09 acceptance slices in the linked document extend PLAT-05/06/07/08 and SF-03/05/07/11/13/14/16; they do not introduce nine new daemons or change the 780-task inventory. Primary near-term coding sequence remains Core B08 and its blocking Platform dependencies, followed by broader Platform production readiness. Owner-authorized state migration is separate.

## 1.10 Component-isolated updates and unified SDK (owner-approved 2026-10-24)

**Authoritative supplemental decision:** [Component-isolated updates and unified SDK V1](COMPONENT_UPDATES_AND_UNIFIED_SDK_V1.md). This is an approved **target architecture**, not evidence the current in-process application can hot-swap its Core.

- Updating the **isolated Core process** should restart/replace only Core; Platform and unrelated modules remain available. Updating an independently hosted module should restart only that module. An LLM provider update should not restart Core or change its authorized model. A Platform executable or incompatible host ABI update may require a supervised Platform restart, with explicit exceptions for supported atomic data/config reloads.
- This requires **real process/IPC separation** with generation fencing, authenticated versioned APIs, drain, signed immutable staging, external readiness checks, timeout, rollback and restart recovery. \`ComponentRuntimeSupervisor\` supplies groundwork but the present \`SofiaApplication\` imports Core and modules in-process; calling that "hot-update ready" would be false.
- Provide **one shared SDK family** for Platform, Core and modules: neutral typed contracts/protocols, audience-safe facades, signed module/resource schemas, testing fixtures, CLI/devtools and version negotiation. The SDK is **not** a privileged mandatory runtime module. Sofía may use optional DEV/EVOLVE/Workshop-backed SDK tools to inspect, propose, build and test candidates without signing or deployment authority.
- A Core/module-only update cannot replace an incompatible Platform-owned state schema, shared in-process library or security contract without a reviewed broader maintenance scope. Never spawn two active Core generations or allow a stale worker to retain writable canonical-state or effect authority.
- The linked document's ISO-01–08 acceptance slices extend existing PLAT-01–05/08, Core B08 and existing DEV/EVOLVE controls. Test real independent OS processes, correct unchanged Platform PID on Core/module upgrade, absence of duplicated effects, end-to-end cognition and transparent partial unavailability.

## 2. Companion modules (implement **after** platform contracts and Gate-4 focused suites)

| Module | Core capabilities | Mandatory interfaces | Gate-4 test minimum |
| --- | --- | --- | --- |
| **RM-DESKTOP** | Canonical chat/tray/settings, approvals inbox, module health/readiness UI, module controls | `chat.send`, `chat.display`, `ui.clear_transcript_view`, `settings.get/request_change`, `approvals.review`, `modules.display` | UI crash independent of Core; clear screen without forgetting; exact authenticated owner permission; stale status honest |
| **RM-DISCORD** | DM conversation and optional outreach; transport receipts | `discord.bind_principal`, `discord.receive`, `discord.deliver`, `discord.delivery_status`, `discord.revoke_binding` | Revoked/forged sender, wrong audience, duplicate message, sent-vs-seen truthfulness, outage does not block desktop |
| **RM-AVATAR2D** | Face/ears/tail/eyes/pose/wardrobe/click regions, truthful frame receipts | `avatar.load_rig`, `avatar.set_expression`, `avatar.set_outfit`, `avatar.animate`, `avatar.frame_receipt`, `avatar.hit_test` | Renderer crash, missing asset, rapid revision conflict, public/private asset boundaries, actual visible revision proof |
| **RM-VOICE** | TTS/STT, audio engine/device, interruptions, avatar lip sync, consent | `voice.probe`, `voice.synthesize`, `voice.play`, `voice.interrupt`, `voice.capture_with_consent`, `voice.transcribe`, `voice.playback_receipt` | Mic disabled by default, interruption, device disconnect, revoked capture, receipt stages, text fallback, timing correlation |
| **RM-MOBILE** | Device pairing, scoped chat, health, notifications, optional sensors | `mobile.pair`, `mobile.revoke`, `mobile.chat`, `mobile.notify`, `mobile.reconcile_delivery`, `mobile.capture_with_consent` | Revocation, offline and duplicate delivery, cross-device session isolation, credential loss and re-pair |

RM-VOICE is a release candidate until measured voice quality and scope evidence justify bundling. RM-MOBILE remains a deferred release candidate unless accepted. Avatar presentation is a Core identity *projection*, not a second personality/state owner.

## 3. Complete optional module catalog

### 3.1 Original optional modules (14, retained)

| ID | Name | Purpose |
| --- | --- | --- |
| MOD-DEV | Development | Source inspection, patch/test proposals and approved execution |
| MOD-RESEARCH | Research | Web/document evidence and source analysis |
| MOD-CREATIVE | Creative | Images, audio, writing, animation, media workflow/artifacts |
| MOD-VISION | Vision | Screen/window observation under explicit scope |
| MOD-DESKTOP-ACT | Desktop action | Approved local mouse/keyboard/app automation |
| MOD-HOMELAB | Homelab | Site-specific trusted host, service and VM integration |
| MOD-ROBOTICS-GAIA | Gaia robotics | Simulator, kinematics, calibrated supervised actuator adapter |
| MOD-TRAINS | Model trains | JMRI roster/sensor observation, later guarded physical dispatch |
| MOD-GAMES | Gaming | Game assistance, approved APIs, GPU/gaming awareness |
| MOD-PRODUCTIVITY | Productivity | Tasks, inventory, calendar, scheduling and documents integration |
| MOD-ML | Machine learning | Governed dataset, experiment, benchmark and model candidates |
| MOD-GENERALIZATION | Reusable skills | Transferable procedures with independent evaluation |
| MOD-VWORLD | Virtual world | Reproducible scenes, simulation and virtual interactions |
| MOD-MENTOR | Mentor | Independent rubrics, challenges, reviews, regression evidence |

### 3.2 Previously proposed modules — **all eight now accepted into catalog**

| ID | Name | Capability and boundary |
| --- | --- | --- |
| MOD-BROWSER | Browser automation | Approved website access and browser workflows; untrusted page instructions are data |
| MOD-MEDIA | Media | Audio/video libraries and playback; outbound sharing is separate |
| MOD-DOCUMENTS | Documents | PDF/Office generation, parsing, document revisions and exports |
| MOD-COMMUNICATIONS | Communications | Email, messages, future platforms, delivery receipts and distinct recipient grants |
| MOD-SMART-HOME | Smart home | Appliances, lights, approved automations; locks/security high authority |
| MOD-CAD | CAD | Parametric designs, engineering drawings, models and validation |
| MOD-SENSORS | Sensors | Local weather, environmental instruments, cameras and approved IoT observations |
| MOD-REMOTE-ACCESS | Remote access | Approved remote terminal/desktop sessions, consented target and traceable commands |

**MOD-SENSORS clarification:** Sofía may already receive weather from ENVIRONMENT/NWS and some values from Home Assistant. Keep using those producers. MOD-SENSORS adds a pluggable *physical acquisition adapter* with sensor identity, calibration, freshness, privacy, device access, units, uncertainty and failure reporting; it is not a second weather intelligence or memory module. Cameras also require separate consent and MOD-VISION to interpret approved imagery. Internet weather remains a provider adapter; local weather stations become optional hardware adapters.

### 3.3 IT modules (10 owner-accepted design entries)

| ID | Name | Capability; default authority |
| --- | --- | --- |
| MOD-IT-HELPDESK | Troubleshooting assistant | Diagnose, ticket/runbook preparation; non-destructive by default |
| MOD-IT-NETWORK | Network diagnostics | DNS/DHCP/latency/routes/VLAN/Wi-Fi; discovery scans explicitly scoped |
| MOD-IT-SYSTEMS | OS administration | Windows/Linux services, users, packages, logs; changes separately granted |
| MOD-IT-CONTAINERS | Containers | Docker/Compose/Portainer inventory, logs, deployments with explicit grants |
| MOD-IT-STORAGE | Storage | SMART, capacity, mounts, NAS; disk repartition/erase protected |
| MOD-IT-DATABASE | Databases | Read-only queries, schemas, integrity; no direct canonical DB admin bypass |
| MOD-IT-BACKUP-DR | Backup/DR | Backup status, verify restores in sandbox, protected live restore plans |
| MOD-IT-SECURITY | Defensive security | Patching/vulnerability/ACL/cert/PKI audits; no implicit key changes |
| MOD-IT-OBSERVABILITY | Monitoring/SRE | Metrics, logs, alerts, incidents, service objective reports |
| MOD-IT-DEVOPS | CI/CD & infrastructure | Pipelines, IaC review, test artifacts; protected publish/apply |

**Separation:** MOD-HOMELAB owns the *specific topology and trusted resource graph* of the owner's lab. MOD-IT-* provide reusable diagnostic/execution adapters. They may call each other only through registered, authorized capabilities. Do not duplicate Fleet host trust, STOP, secrets, RUN, or backups of canonical Core state.

### 3.4 Maker/engineering modules (4 owner-accepted design entries)

| ID | Name | Purpose |
| --- | --- | --- |
| MOD-ENGINEERING | Engineering and electrical | Calculations, diagrams, standards-aware references, grounded safety checks |
| MOD-ELECTRONICS | Embedded and IoT development | Arduino/ESPHome/microcontrollers, firmware artifacts and test rigs |
| MOD-3D-PRINT | 3D printing | Slicing, printer telemetry, approved print submission, job monitoring |
| MOD-ENERGY | Energy and UPS | Power consumption, battery/UPS status, runtime advice, controlled load shedding |

These four are **accepted design entries**, not approved installations or completed features. Likewise, the ten IT entries are accepted for the catalog only. Keep integrations independent and protect physical actions.

### 3.5 Owner-approved expansion: 14 additional catalog entries

The owner has accepted **all 41 existing entries plus all 14 below** for design inclusion, not for implementation claims, installed status, or authority to execute. The **55 entries** consist of **5 companion release modules, 47 optional module designs, 1 attached submodule and 2 adapters**. Three attached entries are not standalone services. See the [complete ownership matrix](MODULE_OWNERSHIP_MATRIX.md).

| ID | Name | Packaging | Correct parent or domain | Scope and boundary | V18 source pointer / verification |
| --- | --- | --- | --- | --- | --- |
| `MOD-AVATAR3D` | 3D Avatar | OPTIONAL | Companion/Avatar | 3D rig, full-body animation, physics and actual frame receipts | `src/sofia/modules/ui/avatar3d_renderer.py` |
| `MOD-AVATAR-STUDIO` | Avatar Studio | OPTIONAL | Creative/Avatar | Wardrobe and scene authoring, layered rig compatibility, review of public/private assets | `src/sofia/modules/avatar/authoring.py; avatar/scene_editor.py` |
| `MOD-INTERACTION` | Avatar Interaction | SUBMODULE | RM-AVATAR2D + MOD-AVATAR3D (also Virtual World) | Pointer hit tests, user-offered virtual interactions and gesture event parsing; Core chooses its own response | `src/sofia/modules/interaction/; avatar/vtuber_hit_test.py` |
| `MOD-VTUBER-BRIDGE` | VTube Studio Bridge | ADAPTER | RM-AVATAR2D | Owner-paired external 2D renderer adapter; no independent personality or render claims | `src/sofia/modules/avatar/vtube_studio_bridge.py` |
| `MOD-WORKSHOP` | Hephaestus Workshop | OPTIONAL | Homelab/Science | Isolated VM experiments, guest preparation and signed lab artifacts | `src/sofia/platform/ops/workshop_provision.py; ops/workshop_policy.py` |
| `MOD-DIGITAL-TWIN` | Digital Twin | OPTIONAL | Homelab/Simulation | Hypothetical infrastructure dependency and failure scenarios, not live effects | `src/sofia/platform/ops/digital_twin.py` |
| `MOD-KNOWLEDGE-LIBRARY` | Knowledge Library | OPTIONAL | Research/Documents | External indexed references, bounded retrieval and source revisions, not autobiographical memory | `src/sofia/core/knowledge/service.py` |
| `MOD-MEMORY-IMPORT` | Memory Import | ADAPTER | PLAT-02 + Core MEM admission | Reviewed foreign memory/conversation imports; candidate promotion stays with canonical memory owner | `src/sofia/core/memory/chatgpt_import.py; memory/chatgpt_migration.py` |
| `MOD-PROJECT-FORGE` | Project Forge | OPTIONAL | Creative/Productivity | Artifact generation, run management, evaluation and delivery; Core owns personal goals | `src/sofia/core/life/draft_agent.py; creative/service.py` |
| `MOD-FILE-WATCH` | File Watch | OPTIONAL | IT/Observation | Approved directory-change observation and permitted workflow triggers | `src/sofia/platform/filesystem/changes.py; filesystem/orchestrator.py` |
| `MOD-HOUSEHOLD` | Household | OPTIONAL | Home/Productivity | Grocy, Mealie, Homebox and consented inventory/meal workflows | Specific domain provider unverified; generic integration framework exists |
| `MOD-FINANCE` | Personal Finance | OPTIONAL | Private productivity | Firefly III and budget analysis with distinct sensitive-data grants; no unapproved transfers | Dedicated finance provider not yet verified |
| `MOD-DATA-ANALYTICS` | Data Analytics | OPTIONAL | Research/Productivity | CSV/structured data, statistics, reports and charts | Dedicated analytics provider not yet verified |
| `MOD-CALENDAR` | Calendar | OPTIONAL | Productivity/Communications | Provider event sync, conflict checks, meeting preparation and action receipts | Dedicated calendar provider not yet verified |

**Explicit Core / Platform split:** Core owns modeled emotions, private thoughts, sexuality/romantic and other preferences, social impressions, gesture selection and refusal, creativity/curiosity, and autobiography. Platform owns SAFE consent/adult gates, canonical state, RUN/ACT, trusted evidence, Fleet forecasts, health/maintenance, module profiles, compatibility and updates. Avatar modules own actual animations, public and privately gated gesture **content packs**, rigging, click hit tests and verified rendering. No second emotional system, permission issuer, memory authority or cognitive runtime is added.

**Attached entries:** `MOD-INTERACTION` is a shared **Avatar submodule** for user input and interaction events; `MOD-VTUBER-BRIDGE` is an **RM-AVATAR2D renderer provider**; `MOD-MEMORY-IMPORT` is an **owner-reviewed state/memory import adapter**. They inherit parents' activation, authorization and maintenance profiles. The other 11 new entries are separately scoped optional capabilities.

**Provider separation:** Smart Home operates connected appliances, Sensors observes physical hardware, and the existing ENVIRONMENT service merges time/weather/environment evidence. Homelab binds approved site-specific nodes; IT modules offer reusable diagnostics. Core interests/goals are never copied into Project Forge or a hobby module. Finance, Household and Calendar retain separate sensitive-data grants. Memory Import proposes reviewed candidates rather than directly editing autobiography.

## 4. Universal Production Readiness (owner's revised labels)

| Readiness | Binding definition |
| --- | --- |
| **DESIGN** | Requirements defined. No implied implementation. |
| **ALPHA** | Implementation incomplete or unverified. |
| **BETA** | Production-wired, testing incomplete. |
| **RELEASE CANDIDATE** | **Tested, Audited, and Reviewed** (the required stage). Applicable focused and integration tests actually passed at a pinned revision, task-specific audit exists, and independent review accepted the release candidate. Not the same as deployed. |
| **PRODUCTION READY** | Full applicable release criteria verified for the precise module version, capability scope, OS/architecture/host profile: RC requirements + matching-revision applicable CI, signed immutable package, installation/update/recovery/rollback proof, performance/security/privacy/resource checks, and any required approved real-host/hardware trial. |
| **BLOCKED** | Critical defect, security failure or revoked certification. Supersedes otherwise positive stage until re-evaluated. |

**Default verdict: `ALPHA` if code exists but isn't verified, otherwise `DESIGN`; default production-ready flag: `false`.** Unknown historical code must be described as **unverified** until audited. Modules cannot certify their own readiness. A module may be RC while not enabled or not installed. Readiness never grants permissions.

**Certification unit:** `(module_id, module_version, artifact_digest, capability_set, active_profile_id/version, target_os_arch, required_device_and_host_class)`. Individual workflows also have separate interoperability readiness; a healthy module is not automatically certified with another module.

**Independent readiness dimensions:** `development_gate` (original L1–L5), `readiness` (the above), `live_acceptance` (`not_applicable/pending/passed/failed`), `security` (`not_reviewed/passed/failed`), `deployment` (`not_installed/staged/active/degraded/paused`), `target_profile`, `artifact_digest`, `source_sha`, `evidence_refs`. Do not infer L5 from RC, or RC from an individual passing test.

**Example metadata, not actual evaluation:**

```yaml
module_id: org.sofia.voice
version: 1.0.0
source_sha: <exact-git-sha>
artifact_digest: <verified-sha256>
profile: windows-x86_64/approved-audio-device
readiness: RELEASE_CANDIDATE
development_gate: 4
production_ready: false
live_acceptance: pending
security: passed
deployment: not_installed
review_ref: <independent-review-evidence>
test_refs: [<exact-revision-focused-tests>]
ci_refs: []
```

## 5. Workload and safety defaults

- **No resource interference:** foreground text/UI/approved active controls outrank background creative/ML/DEV jobs. During gaming, heavy GPU workers pause or relocate only when destination, grant, exact model/artifacts and privacy match.
- **No hidden installs:** Discovery ≠ signature trust ≠ install permission ≠ execution authority.
- **No physical auto-move:** Gaia, JMRI physical commands, power/relay/device controllers require pinned endpoints and independently enforced safety.
- **No stale success:** `queued`, `dispatched`, `device_ack`, `verified_effect` and `human_observed` are different facts.
- **No shadow identity:** remote hosts run scoped workers only, not a separate Core, shadow memory or owner authority.
- **No irreversible background update:** filesystem/VM/PKI/security changes and production release activation require the appropriate owner-protected grant.
- **No unsafe failover:** if no eligible approved host exists, mark the job `PAUSED` or `UNAVAILABLE`; never move to an incompatible or untrusted host.

## 6. Implementation order and concrete batch exits

| Order | Batch | Deliverable | Exit evidence |
| --- | --- | --- | --- |
| 1 | PF-00 | Read-only audit of existing V18 SAFE/RUN/OPS/Capability/System state and Core B00 seams | Exact-sha reuse map and conflict list |
| 2 | PF-01 | PLAT-01 and PLAT-02 recovery/fencing interfaces | Simulated crash/restart/writer integrity focused + integration tests |
| 3 | PF-02 | PLAT-03 and PLAT-04 authority/job receipts | Denial, STOP, idempotency, unknown effects tests |
| 4 | PF-03 | PLAT-05 SDK, manifest, lifecycle, trust and 16 shared facilities contracts | Unsigned/malicious packages, dependency, sandbox, activation tests |
| 5 | PF-04 | PLAT-06 and PLAT-07 fleet capacity forecasts, placement, devices, compute admission | Multihost simulation and gaming-aware placement with pinned controls |
| 6 | PF-05 | PLAT-08 release readiness evaluator, evidence and package signing plans | RC/production-ready negative controls; per-profile, maintenance-profile and interoperability evidence; rollback and exact SHA tests |
| 7 | CM-01 | RM-DESKTOP and RM-DISCORD | Authenticated single canonical conversation, cross-audience privacy, delivery proofs |
| 8 | CM-02 | RM-AVATAR2D and RM-VOICE | Renderer/playback real receipts, sync, failure isolation, consent |
| 9 | CM-03 | RM-MOBILE if ready | Device pairing/revocation and offline reconciliation |
| 10 | OPT-* | Independent optional modules after common contract | Module-specific Gate-4 tests; supervised physical trials separate |

Each batch maps relevant original CA/ML/GA IDs individually, preserves their wording and evidence, and counts levels only with actual recorded source/test/audit evidence. Requirements-only documents do not become Gate 3 or 4.

## 7. OpenCode integration boundaries

This is an **architecture specification draft**. It must not be used to overwrite active Core B00–B08 files or install modules on Venus/Artemis. When owner authorizes a new work batch, OpenCode must inventory current source and dirty tree, pin exact commit, safely reconcile this document, implement one owned platform slice with tests, produce an auditable diff and seek separate approval for commits, pushes, releases and host actions.

**Owner-approved maintenance addition:** PLAT-05 registers and validates signed maintenance profiles; PLAT-01 uses recovery limits; PLAT-08 checks evidence and exposes maintenance status; PLAT-07 provides destination/device facts. Core can propose and evaluate, never sidestep SAFE/RUN.

**First implementation seam:** PLAT-05 manifest/SDK uses existing `src/sofia/platform/capability/{system,gateway,model}.py` and SAFE/RUN canonical owners, not a parallel permission or execution engine. Ensure PLAT-01/02/03/04 interfaces are contractually stable before feature-module registration can perform effects.

## 8. Additional platform extensions to consider (recommendations, **not yet owner-approved**)

These primarily extend PLAT-01–08; avoid a new daemon/module unless there is an independently deployable permission, lifecycle or resource boundary.

| Priority | Proposed extension | Existing owner | Why it matters / acceptance target |
| --- | --- | --- | --- |
| **P0** | **Data-locality & privacy-aware placement** | PLAT-03/07 | A movable worker may not copy local-only/private artifacts to an otherwise fast but unauthorized host; prove denial and secure cleanup of transfer staging |
| **P0** | **Update compatibility lockfile and version constraints** | PLAT-05/08 | Pin dependency graph, exact API/ABI/schema versions and package digests; fail closed on incompatible upgrades, support safe rollback |
| **P0** | **Resource and workload reservations with preemption policy** | PLAT-04/06/07 | Guarantee foreground priority without killing uncertain effects; only checkpoint-safe jobs may be preempted |
| **P0** | **Failure-domain-aware placement and no-split-brain fencing** | PLAT-01/02/07 | Avoid placing supposedly redundant workers on one failure domain; lease/epoch prevents duplicate effectful instances during partitions |
| **P1** | **Shadow/canary deployments and feature flags** | PLAT-05/08 | Exercise a new module revision in read-only/shadow or limited-scoped canary before rollout; never shadow-execute physical effects |
| **P1** | **Configuration drift detection** | PLAT-05/07/08 | Compare approved configuration with observed host/runtime settings; report difference, propose repair, do not silently rewrite |
| **P1** | **Resilience objectives and chaos testing** | PLAT-01/04/08 | Measure recovery time, lost-job rate, uncertain-effect rate, and failures under process death/disk-full/network partition |
| **P1** | **Module bill of materials and vulnerability response** | PLAT-05/08 | Track SBOM, license, dependencies, OS/runtime support and vulnerability exposure; suspend unsafe revisions without replacing source by guess |
| **P1** | **Traceable end-to-end provenance** | PLAT-02/04/08 | Relate module versions, events, SAFE decisions, actual effects and artifacts via immutable references without duplicating Core memory |
| **P2** | **Fleet cost/energy and thermal budgeting** | PLAT-06/07 | Choose an eligible host using actual power/noise/thermal/transfer impact, not CPU% alone; measurements must precede optimization |
| **P2** | **Offline-first and reconnect policy** | PLAT-01/04/07 | Define what local read-only work is possible during Fleet separation and precisely how jobs reconcile on reconnect |
| **P2** | **Capability discovery UX and permission explainer** | PLAT-03/05/08 + RM-DESKTOP | Show what a module can currently do, *why* an action is denied, required device, proposed resource use and owner decision required |

**Recommended next decisions:** explicitly adopt the four P0 extensions because they prevent architectural mistakes before the first remote module moves; keep the rest as staged proposals until there is a tested use case. Production readiness and deployment permissions remain separate.
