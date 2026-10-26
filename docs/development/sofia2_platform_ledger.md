# Sofía 2.0 Platform takeover ledger

This is the recoverable evidence ledger for the reconciled Platform work. It
is not a release certificate or permission to deploy.

## Baseline

- Takeover checkout: `/workspace/SofiaAdaLyra-Takeover`
- Branch: `main`
- Source revision: `f3075b81ad00df878b7dc01f877a5113a8c67d67`
- Date/environment: 2026-10-24 UTC, Linux x86_64
- Historical Platform checkout: preserved dirty at `033a1bb7`, not reset or
  overwritten
- Historical Core checkout: preserved dirty at `af860fd8`, not reset or
  overwritten
- Production state and hosts: not opened, changed, restarted, enrolled, or
  migrated
- First reconciled publication: commit `e8f062ea` was pushed to `origin/main`
  on 2026-10-24 after explicit owner instruction. GitHub Actions status could
  not be queried because the available GitHub API credential returned
  `Forbidden`; no matching-revision CI claim is made.

## Reconciled implementation slices

| Scope | Canonical relocated owner | Implemented in takeover | Local evidence | Remaining acceptance |
| --- | --- | --- | --- | --- |
| PLAT-01 / SF-10 | `sofia.platform.run.components` | Dependency-aware component lifecycle, lease-bound writes, pause/quarantine and startup reconciliation | Included in 84-test Platform suite | Application/OS-host registration, Windows service evidence, fault campaign |
| PLAT-02 | `sofia.platform.state` | Atomic multi-record CAS, hash lineage, reviewed namespace/state facade and inert migration/restore plans | Included in 84-test Platform suite | Authorized restore exercise, distributed fencing, Windows/CI |
| PLAT-03 | `sofia.platform.safe` | SAFE facade and secrets-reference broker; no secret values exposed | Included in 84-test Platform suite | Full current-grant projection into Core, rotation/live authority acceptance |
| PLAT-04 | `sofia.platform.run.effects` | Durable effect envelope, exact idempotency, STOP and attestation recheck, explicit unknown/unverified/verified outcomes | Included in 84-test Platform suite | Production TaskExecutionManager registration and remote outcome acceptance |
| PLAT-05 / SF-08/12/13/16 | `sofia.platform.modules` | Signed non-executing package parser, immutable identity, dependency ranges, profiles, lifecycle, compatibility/readiness and canonical observer | Platform suite plus 61-test Core integration suite | Production lifecycle command facade, actual signed publisher package, sandbox and rollback exercise |
| PLAT-06 | `sofia.platform.cognition_compute` | Measured compute admission/reservation model and truthful route reports | Included in 84-test Platform suite | Real provider load/unload receipts and GPU/VRAM host evidence |
| PLAT-07 / SF-03/05/07/14 | `sofia.platform.ops` | Resource/device arbitration, bounded deterministic forecasting, migration replay refusal and startup recovery | **25 passed** OPS migration suite; resource/forecast tests in Platform suite | Distributed consensus, physical-device safety, real Fleet telemetry |
| PLAT-08 | `sofia.platform.modules.readiness` | Independent readiness projection over package, compatibility, lifecycle and evidence | Included in 84-test Platform suite | Exact-revision CI, independent review, release/rollback campaign |

The focused reconciled Platform command covering module package,
compatibility, lifecycle/readiness, compute, resources/forecast, component
supervision, effect broker, SAFE and atomic state services completed with
**84 passed** during the initial port. After Core integration and migration
repairs, the combined 15-module Platform/observer/OPS suite completed with
**98 passed** in 3.54 seconds. The focused OPS workload-migration
reconciliation command had separately completed with **25 passed**. These are
local test results, not CI or live-host proof.

Cross-layer regression evidence after restructure repairs:
`pytest -q -m 'pkg_core and not integration'` — **4,745 passed, 4 skipped,
2,229 deselected, 8 subtests passed** in 310.47 seconds on local Linux. The
run includes local mobile HTTP, pinned mTLS, and attended WebAuthn flows after
bounded loopback permission was granted. No external service or live host was
used.

Packaging acceptance: a clean local wheel build succeeded, installed into a
disposable target, and exposed all five required Core packaged assets plus
Avatar wardrobe and UI resources. Installed Platform/Application and Avatar
imports succeeded. The installed `python -m sofia` command reached its stable
launcher contract using an invalid-argument no-state check. Desktop, Discord,
Windows service, and real-provider host acceptance remain open.

## Canonical boundaries preserved

- All durable Platform metadata remains in the existing `sofia.db`; no
  secondary authority, identity, job, or module database was introduced.
- `CapabilitySystem`, SAFE/STOP and RUN remain the authorization/execution
  boundaries. A signed manifest, forecast, goal, or Core proposal grants no
  authority.
- Startup does not assume a previously active adapter survived restart.
- Unknown or interrupted external outcomes are not replayed as successful.
- The canonical writer host was not selected or migrated.

## Next eligible work

The application-owned module command boundary constructs the canonical
lifecycle manager during
`SofiaApplication` composition, classifies every lifecycle mutation as a
protected SAFE capability, and consumes an exact FIDO2-bound one-use approval
containing module identity, version, digest, revision, target lifecycle and
profile. Operator STOP blocks authority-increasing transitions; discovery
remains inert. Focused evidence: **25 passed** across lifecycle, command
boundary and application module-awareness tests, plus **64 passed** across
execution fingerprints, STOP revision handling, runtime authorization wiring
and permission-store tests. The broader Platform selection passed **100/100**.
The full non-integration SAFE marker completed with **1,805 passed, 2 skipped,
8 failed** solely because its first sandbox run denied loopback sockets; the
four affected mobile/WebAuthn files then passed **36/36** after bounded network
permission was granted. The slice was published as commit `914ed766` on
`origin/main` after owner instruction; it has no matching-revision CI evidence.

Signed capability projection was published as commit `37730af8`.
The lifecycle manager persists capability IDs and schema references from the
already verified manifest in canonical SQLite, including atomic replacement on
update/rollback. The Core observer reads those declarations as data without
importing package code, derives only whether a capability's Platform policy
requires authority, and never reports a current grant. Focused lifecycle,
observer, Core-awareness and SAFE-policy evidence: **60 passed**. It has no
matching-revision CI evidence.

Durable module transition receipts are now exposed by exact module ID and
revision, with bounded history for diagnostics and future RUN reconciliation.
Receipts preserve the previous/next lifecycle, approval reference, actor,
reason and timestamp; they report only the canonical state transition, not an
unverified external effect. Restart persistence is covered by the focused
module command suite. Component-supervisor integration remains deliberately
blocked on a restart-safe reviewed adapter factory; the Platform will not
blindly resurrect an adapter or claim an effect after restart.

Next, complete remaining component supervision/recovery integration and the
Platform Control Center views. Lifecycle commands still need durable RUN
envelopes before asynchronous/external module operations can be considered
complete. Keep effectful transitions inert until authenticated approval and
the existing execution boundary admit them.

## Durable module RUN checkpoint — 2026-10-24 UTC

Baseline: `e57bbd807fc9d40106055867b2841d5a60f75b20`, local Linux checkout.
This slice reuses the application-owned `DurableWorkStore` and
`TaskExecutionManager`; it does not add a scheduler or another database.

- `ModuleOperationRequest` durably binds the exact module/package, lifecycle
  revision, profile, principal/audience, one-use approval, component/host,
  deadline, correlation, leases, requested effect and cancellation policy.
- `ModuleOperationCoordinator` registers one reviewed
  `platform.module.operation` handler in the existing executor. Idempotency is
  bound to the authenticated principal, audience and exact request digest.
  Changed payloads fail rather than attaching to an earlier job.
- Activation is split into an authority-consuming `ACTIVATING` transition and
  a separately verified `ACTIVE` transition. Capability conflicts and all
  other non-effect validation occur before approval consumption. The durable
  attempt stream distinguishes admission, running, denial, pre-dispatch
  failure, external dispatch, unknown outcome and externally verified result.
- An interrupted/ambiguous dispatch remains a terminal `UNCERTAIN` RUN
  receipt and is never automatically replayed. A later explicit
  `reconcile()` uses only the reviewed factory's inert inspection boundary:
  verified-running state may complete activation; verified-stopped state is
  quarantined; ambiguity remains unknown. The historical RUN uncertainty is
  retained.
- `AdapterFactoryRegistry` accepts only factories registered by trusted
  Platform construction and resolves exact signed-package/component/profile/
  host contracts. It never scans candidate paths or imports untrusted package
  code. Restart package reopening verifies the canonical staged path, exact
  manifest identity, file set and artifact hashes.
- `SofiaApplication` owns the factory registry and coordinator, registered on
  the same executor already driven and drained by the background runtime.
  No factories are automatically registered, so effectful restart stays
  fail-closed until a reviewed adapter exists.

Executed local evidence:

- `pytest -q test/test_platform_module_operations.py
  test/test_module_lifecycle_v1.py test/test_platform_module_command_service.py
  test/test_module_awareness.py` — **33 passed**.
- `pytest -q test/test_application.py test/test_application_acceptance.py
  test/test_autonomous_work.py test/test_run_component_supervisor.py
  test/test_platform_module_observer.py test/test_safe_platform_facade.py
  test/test_module_lifecycle_v1.py test/test_platform_module_command_service.py
  test/test_platform_module_operations.py` — **69 passed**.
- `python -m compileall -q src/sofia/platform` and `git diff --check` passed.
  Ruff is not installed in this checkout's test environment, so no lint result
  is claimed.

Readiness remains **BETA / local evidence only**. Automatic adapter restart,
live host/process acceptance, Windows evidence, matching-revision CI and
independent review remain open. Per the owner priority change, unrelated
Platform expansion is deferred while Core B07/B08 is completed.

Core-B07 dependency hardening followed this checkpoint: full signed-manifest
policy identity, trusted readiness-producer admission, evaluator-authenticated
compatibility, verified adapter health projection, case-normalized SIMULATE
classification and honest UNKNOWN availability. These are the minimum
Platform corrections required for Core module self-knowledge; they do not
expand Platform authority or enable automatic restart. Evidence is recorded in
the Core ledger's B07 completion checkpoint.

## HNF-08 inference ownership checkpoint — 2026-10-24 UTC

Baseline: owner-approved hardware-neutral contract commit `ec7f3da6` plus the
B08 package-classification checkpoint `e0be7565`, local Linux x86_64.

- Core retains `LLMProvider`, `CognitiveEngine`, cognitive messages, tool-call
  candidates, context and response policy. Tool candidates remain inert data.
- The Ollama request/response translator now has one implementation at
  `sofia.modules.inference.ollama_provider`. Platform owns provider selection
  and construction at `sofia.platform.cognition_provider`; production
  composition imports that owner directly.
- The Fleet worker service and Platform verification probes use the inference
  module directly. Temporary Core import paths are identity-preserving shims:
  they resolve to the exact same class/factory and cannot create a shadow
  provider path.
- Existing pinned-mTLS remote inference, exact configured model selection,
  no-fallback policy, and canonical Core state remain unchanged. No provider,
  model, worker, database writer, host, or credential was changed.

Executed local evidence:

- Pre-refactor provider/composition/Fleet baseline: **189 passed**.
- Post-refactor same suite plus ownership regressions: **192 passed**.
- Platform interaction/probe consumers: **76 passed**.

These are deterministic and stubbed local tests. The repository's real local
and remote Ollama integration paths remain executable but were not run because
this environment has no approved installed model, enrolled worker, or mTLS
credentials. HNF-08 remains **BETA** pending real-model equivalence, Windows,
matching-revision CI, and independent review.

## HNF-01 through HNF-04 resource contract checkpoint — 2026-10-24 UTC

Canonical owners: `sofia.platform.resources`, existing OPS Fleet registry,
existing signed module package/compatibility services, and canonical
`sofia.db`. No second scheduler, trust registry, or state database was added.

- Resource Capability Contract V1 uses typed capability keys, canonical units,
  explicit manufacturer/observed/benchmark provenance, per-resource IDs,
  freshness and UNKNOWN semantics. Deterministic predicates support equality,
  minima/maxima/ranges, versions, sets, alternatives and same-device matching.
  Two GPUs' VRAM is never summed to satisfy one-device demand.
- Canonical inventory revisions preserve display identity separately from
  immutable Fleet identity, parent VM/host relationships, enrollment/trust,
  provenance facts and historical semantic changes. Discovery projects an
  untrusted record; only the existing enrolled Fleet node binding can project
  trusted inventory.
- Live telemetry is bounded and restart durable. The existing OPS service
  normalizes its legacy host metrics into the shared contract while treating
  unsupported values as absent/UNKNOWN and representing legacy GPU telemetry
  as one device only.
- Signed manifest schema v1 remains byte-compatible. Schema v2 can bind typed
  resource requirements to each operation profile; the reviewed compatibility
  evaluator consumes current `ResourceSupply` evidence. Compatibility remains
  advisory and creates no permission or lease.
- Production Fleet discovery now updates the inventory projection after the
  existing enrollment reconciler, without changing enrollment authority.

Executed local Linux evidence:

- HNF contract/inventory/telemetry, signed package/compatibility, OPS resource,
  Fleet/background integration and package ownership: **72 passed**.

Readiness is **BETA**. Complete authenticated per-device agent inventory,
automatic benchmark scheduling/results, typed placement reservations, real
multi-host trials, Windows, CI and independent review remain open.

## HNF-05/HNF-06 automatic benchmark checkpoint — 2026-10-24 UTC

Canonical owners: the existing application `DurableWorkStore` and
`TaskExecutionManager`, `sofia.platform.resources.BenchmarkCoordinator`, the
HNF inventory/telemetry stores, and canonical `sofia.db`. No scheduler,
executor, state authority, host trust, or permission system was added.

- Enrolled and trusted inventory revisions deterministically create deduped
  benchmark plans. Untrusted discovery records cannot queue work. CPU,
  memory, and scratch-storage runners are bounded and versioned; GPU,
  network, LLM, and module-specific runners remain unavailable unless a
  reviewed adapter is registered rather than fabricating unsupported data.
- The production background owner queues eligible plans and the existing RUN
  manager admits them. Exact Git source revision is required; an unverifiable
  installed build or dirty checkout disables automatic benchmarking rather
  than creating falsely attributed evidence.
- Admission is fail-closed across fresh authenticated activity, CPU/GPU load,
  RAM/VRAM, temperature, throttling, power limits, active non-benchmark work,
  resource/device leases, local policy, and operator STOP. Missing telemetry
  is UNKNOWN and cannot count as idle. The execution handler rechecks the
  same boundary immediately before measurement, so foreground/gaming changes
  preempt queued work.
- Results retain host/resource IDs, inventory and suite revisions, source
  revision, duration, units, sample counts, configuration, utilization and
  environmental evidence, freshness, model identity fields where applicable,
  and explicit failure/cancellation reasons. CPU single/multicore, memory
  bandwidth/index latency, and sequential/random scratch-storage metrics are
  separate; no arbitrary combined score is produced.
- Restart reconciliation preserves an interrupted RUN receipt and creates a
  distinct later attempt only for these explicitly resumable scratch/read-only
  stages. It never reuses the uncertain fingerprint. Stale results become
  eligible for a bounded new attempt; attempt limits and cooldowns prevent
  retry loops.

Executed local Linux evidence:

- HNF benchmark and resource tests plus RUN/background/composition regression
  coverage: **55 passed**.

Readiness remains **BETA**. Reviewed GPU/network benchmark adapters and real
exact-model Ollama benchmark acceptance,
measured-result placement ranking, Windows and Debian CI, real enrolled-host
idle/preemption trials, exact installed-release revision injection, and
independent review remain open. No live host, model, driver, endpoint,
canonical writer, or production service was changed.

Follow-up HNF-06 exact-model inference slice:

- The inference module now owns a reviewed streaming Ollama benchmark adapter.
  It inventories an already-installed selected model, binds one exact digest,
  uses a fixed synthetic non-private prompt with tools disabled, records TTFT,
  prompt/generation throughput, load/total duration and only a response hash,
  then verifies the digest again. It never pulls, installs, switches, or
  exposes generated content.
- The application registers this adapter only for an explicitly configured
  `SOFIA_LOCAL_HOST_ID`. The existing benchmark coordinator queues it only
  when the same enrolled/trusted host has fresh verified Ollama-runtime and
  exact model-digest resource evidence. Local/remote host attribution is
  therefore explicit; a runtime cannot benchmark a different Fleet worker
  through its local provider by accident.
- Digest mismatch/change, missing metrics, missing model, cancellation and
  stale/unverified inventory fail closed and produce canonical RUN/benchmark
  failure evidence. Stubbed provider and canonical RUN integration coverage
  joins the broader HNF benchmark suite; no real-model result is claimed.

## HNF-07 hardware-neutral placement checkpoint — 2026-10-24 UTC

Canonical owner: the existing OPS `PlacementEngine` and `OpsToolService`.
The implementation extends that engine and the existing authorized migration
preflight; it does not create a second placer, scheduler, executor, Fleet
registry, or enrollment authority.

- The production OPS surface accepts Resource Capability Contract requirements
  and evaluates each enrolled trusted host's current inventory plus fresh live
  telemetry. Host display names and deployment roles have no effect on typed
  selection. Unknown/missing facts, stale facts, untrusted inventory, and
  foreground activity fail closed with explicit rejection reasons.
- Individual resource and host supplies remain isolated. GPU VRAM, VM/parent
  RAM, and other capacities are never added across devices or machines to
  satisfy one requirement.
- One explicitly requested fresh benchmark metric may order already-eligible
  hosts. It cannot override a hard resource, trust, privacy/allowlist, or
  activity constraint; no combined synthetic hardware score is used.
- Legacy workload callers remain compatible, but now pass an actual placement
  clock so stale Fleet telemetry is rejected. The existing protected migration
  path runs the same deterministic typed preflight before consuming approval
  or dispatching its existing remote effect.

Executed local Linux evidence:

- Typed placement, migration preflight, signed module compatibility,
  resource and benchmark focused set: **73 passed**.
- Complete `pkg_ops and not integration`: **1,387 passed**, with only three
  loopback-socket cases denied by the default sandbox. The affected mTLS file
  was rerun outside that socket restriction: **6 passed**.

Readiness is **BETA**: real multi-host resource
reservations, forecast-informed advisory ranking, failover policy, network
partition trials, Windows/Debian CI, and enrolled-host acceptance remain open.

## HNF-09 pre-commissioning portability checkpoint — 2026-10-24 UTC

- Split runtime/inference admission now accepts the hardware-neutral
  `fleet_runtime` role with exact enrolled runtime and GPU-worker IDs. The
  historical `artemis_runtime` spelling remains an explicit compatibility
  alias; it no longer defines policy or permits host-name inference.
- All safety diagnostics and production composition describe roles rather
  than Venus/Artemis. Exact pinned-mTLS transport, no local fallback, no model
  auto-provision, one allowed GPU-worker identity, and separation between the
  runtime and worker remain mandatory.
- Focused split topology, Fleet cognitive engine, provider boundary, remote
  inference contract and durable admission tests: **45 passed** locally.

HNF-09 remains **BLOCKED for live acceptance**, not failed or accepted. This
environment has no owner-authorized disposable Linux VM session, enrolled GPU
worker, pinned commissioning credentials, approved installed model/digest, or
Windows/Debian matching-revision CI. No canonical writer migration, Fleet
enrollment, model pull/switch, network call, host restart, service activation,
or production configuration change was performed.

## Reconciled continuation queue — 2026-10-24 UTC

Queue source revision: `7d1223e1a917088287bea500cd8897518505e286` on
`main`, synchronized with `origin/main`, clean working tree. This is the
single carry-forward projection for the new HNF, ISO, FED and generic-Core
acceptance slices. It supplements the existing Core/Platform ledgers and maps
back to the original evidence system; it is not another completion authority.

The authoritative five-stage validator was run against this exact revision:

`python scripts/v18_five_stage_audit.py --repo . --sha 7d1223e1... --verify-head --output /tmp/v18-audit.json --markdown-output /tmp/v18-audit.md`

Result: **652 NOT_WORKED_ON/unverified, 16 CODED_UNFINISHED, 12
PRODUCTION_CODED, 100 TESTED, 0 TESTED_CI; 133/780 targeted evidence records**.
The 652 count means unaudited evidence, not proven absence of code.

| Status | Requirement / mapping | Real owner, caller and state/authority boundary | Evidence at queue revision | Remaining acceptance / dependency | Next executable step |
| --- | --- | --- | --- | --- | --- |
| DONE_WITH_EVIDENCE | active HNF-06 exact-installed-model benchmark slice; PLAT-06/07/08 | `sofia.modules.inference.benchmark`; application bootstrap registers it with `BenchmarkCoordinator`; canonical RUN and `sofia.db`; no model install/switch authority | 68 focused HNF/provider/application tests passed; commit `7d1223e1` | real local/remote approved Ollama, resource measurements, Windows/CI and independent review remain unverified | retain adapter and exercise it only on an approved installed exact model |
| DONE_WITH_EVIDENCE | Core B07 / CORE-35–40 | Core codebase, maintenance, Workshop and module-awareness services; application composition; Platform SAFE/RUN remain effect owners | Core ledger records 114 + 37 focused passes and broad Core gate at the cited revisions | matching-revision CI, Windows, independent review and real signed module/adapter | preserve during SDK/process migration; do not rebuild |
| IN_PROGRESS | Core B08; HNF-08; original Core/channel tasks | `python -m sofia`, desktop/Discord/mobile/application composition, provider-neutral Core with Platform provider factory; canonical state and audience owners unchanged | wheel/entrypoint and local Core/provider suites recorded in Core and Platform ledgers | genuine Ollama, cross-channel installed-package/recovery campaign, Windows/Linux CI and independent review | make the SDK/process seam without changing conversation semantics, then rerun B08 |
| IN_PROGRESS | HNF-01–04 | `sofia.platform.resources`, OPS inventory/telemetry, signed module manifest and compatibility evaluator; Fleet enrollment remains authority | 72 focused tests recorded | complete authenticated per-device inventory, OWNER_REPORTED provenance, part/replacement history and owner-assisted unknown questions | extend canonical inventory schema and agent observation contract after SDK contracts |
| IN_PROGRESS | HNF-05–06 | `BenchmarkCoordinator` over canonical RUN; background runtime owns queue/tick | 55 general benchmark tests plus exact-model focused run | reviewed GPU/network adapters, live safe-idle/preemption evidence, installed-build revision injection | implement inert adapter contracts first; no physical effects or public speed tests |
| IN_PROGRESS | HNF-07 | existing OPS `PlacementEngine` and protected migration preflight | 73 focused tests; 1,387 OPS passes plus 6 elevated-loopback passes | atomic multi-worker reservations, forecast ranking, explicit failover policy and partition trials | add typed reservation admission to the existing engine, not a second placer |
| BLOCKED_ENVIRONMENT | HNF-09 | hardware-neutral split composition, pinned mTLS Fleet inference and disposable state | 45 local portability tests | approved disposable VM, enrolled GPU worker, credentials, exact model, Windows/Debian CI | keep commissioning harness executable; perform no writer migration or host change |
| READY | ISO-01 audit and ISO-02 unified SDK contracts | existing `sofia.platform.run.components`, SAFE/RUN, Core cognition and module contracts; Platform must own generation/authority | current source audit shows no `sofia.sdk` family and Core/modules still load in the Platform interpreter | versioned request/response/event/authority/generation negotiation, state facade and negative authority tests | introduce the minimal shared SDK family and use it in one real Platform boundary before process extraction |
| BLOCKED_DEPENDENCY | ISO-03 independent Core worker | Platform supervisor, canonical writer/state facade and Core application entrypoint | design contract only; current production composition is in-process | ISO-02, active-generation fencing, process IPC, state facade, stop/restart and exactly-one-active-Core tests | migrate one bounded Core request path after SDK/fencing is tested |
| BLOCKED_DEPENDENCY | ISO-04–05 module/provider worker and component update | module RUN coordinator, adapter factory, component supervisor, signed packages | durable module RUN has 33 + 69 focused passes; provider extraction is locally tested | independent OS process, drain/fence/activate/verify/rollback and real effect observations | reuse supervisor/RUN; never use import reload or blind replay |
| BLOCKED_DEPENDENCY | ISO-06–08 SDK devtools, impact planning and acceptance | single SDK family plus existing release/readiness owners | approved requirements only | ISO-02–05, real process tests, Windows/Linux/VM, exact-revision CI and review | complete contracts and conformance fixtures before developer façade or release claim |
| BLOCKED_DEPENDENCY | FED-01–08 | existing distributed mTLS/identity, SAFE/RUN/ACT, Core REL/Emotion/Memory; separate state lineages | design contract only; Fleet inference transport is not federation | Core B08, ISO generation/process boundary and peer-specific consent/storage; approved live mTLS only later | keep in queue; begin FED-01/02 only after ISO boundary is stable |
| BLOCKED_DEPENDENCY | generic `companion_runtime` multi-Core package target | current verified `sofia.core`, `sofia.platform`, `sofia.modules`; Setuptools and `python -m sofia` are compatibility owners | current layered source tree and package tests; no generic package exists | ISO contract boundary and import/package map; identity/state separation for future distinct Cores | perform bounded compatibility migrations after ISO-02, never a blind rename |
| READY | original 780-task reconciliation | original brief table + sparse five-stage evidence + validator | validator passed at queue revision; 133/780 targeted records | individual source/test audit for 647 not targeted; preserve all original clauses | update task records only when a concrete implementation slice supplies task-specific evidence |
| BLOCKED_ENVIRONMENT | GitHub issues/PRs/current-revision Actions, including issue #119 | GitHub is the external evidence owner | `gh` API returned `403 Forbidden` on 2026-10-24; no issue or CI contents inferred | authenticated read access | retry read-only issue/PR/run audit when credentials permit; never claim L5 meanwhile |
| BLOCKED_OWNER | production hosts, enrollment, writer migration, model pulls/switches, releases and physical effects | owner approval plus Platform SAFE/STOP/RUN | none attempted in this checkout | exact owner authorization and host evidence | continue disposable/local implementation work only |

Dependency order is therefore: preserve Core B07 and current HNF code → finish
ISO-02 generation/authority/state-facade contracts → isolate and fence one Core
worker without a second writer → rerun Core B08 → complete remaining HNF
inventory/benchmark/reservation work → component updates → federation → bounded
generic package migration → continue the remaining individually audited 780
tasks. Host- or owner-blocked evidence does not stop independent code work.

### ISO-02 unified SDK contract checkpoint

Status: **IN_PROGRESS / locally tested contract slice**, not independent
process isolation.

- `sofia.sdk` is the single portable contract family. It has no application
  composition, database, scheduler, signing key, authentication service or
  capability gateway of its own.
- Protocol ranges negotiate the highest overlap and fail closed across major
  versions or disjoint ranges. Component endpoints bind exact release digest,
  Platform instance, positive generation and (for Core only) distinct Core
  identity.
- Request envelopes bind source/destination generations, existing authority
  reference, principal/audience, bounded scopes, payload schema/digest,
  idempotency, correlation and a deadline no later than authority expiry.
  Dispatch validation rejects stale generations and expired authority. This is
  a projection of authority, never a way to mint it.
- Response envelopes preserve denied/unavailable/failed/cancelled/unknown,
  reported-unverified and verified-success distinctions. Verified success
  requires an evidence reference. Exact-field decoding rejects injected
  fields.
- State façade protocols expose read projections and Platform-owned CAS
  requests; they intentionally expose no raw SQLite connection and cannot
  create a second writer.
- The existing remote inference wire is byte-compatibly pinned to SDK protocol
  `1.0`; the real worker service rejects a divergent SDK contract before it
  calls the provider. This is the first production consumer while the existing
  Fleet wire remains compatible.

Executed locally with the preserved repository test interpreter:

`pytest -q test/test_sdk_component_contracts.py
test/test_distributed_inference.py test/test_distributed_inference_service.py
test/test_distributed_inference_agent.py
test/test_distributed_inference_transport.py
test/test_distributed_inference_control.py test/test_package_grouping.py` —
**36 passed**. `compileall` for the SDK/distributed packages and
`git diff --check` passed.

Remaining ISO-02/03 work: authenticate serialized producer identity at the
transport boundary, implement the Platform state-facade owner, add process
backpressure/cancellation/events, and move one bounded Core worker into a real
independent OS process with durable exactly-one-generation fencing. The
current in-process application remains the working compatibility path and no
zero-downtime or independent-restart claim is made.

State-facade follow-up:

- `PlatformSDKStateFacade` now adapts the existing `StatePlatformService` and
  State Plane instead of creating storage. Trusted Platform construction must
  supply both the active-generation validator and the effective-authority
  validator; scope strings in a serialized projection are insufficient by
  themselves.
- Reads and CAS writes retain the namespace's reviewed principal/audience and
  state-class policy. Stale generations, expired authority, missing exact
  namespace scope, authority denial, invalid JSON, oversized values and stale
  revisions fail closed. The returned object contains JSON plus revision and
  digest, never a state path, SQLite connection or backend object.
- Restart reconstruction was exercised by creating a second facade over the
  same disposable canonical state and continuing exact CAS revisions.

Focused command covering the new facade, existing Platform state service, SDK
contracts and remote inference integration: **27 passed**. A first attempted
command named a nonexistent historical `test_state_plane.py` and therefore
collected no tests; it is not counted. The corrected command used only present
test modules and passed.

The next blocker is the durable active-component generation owner. Until that
owner is connected to a real independently hosted Core process, the facade is
a tested Platform adapter and not evidence that Core is process-isolated.

### ISO-03 generation-fence prerequisite checkpoint

`ComponentGenerationStore` now persists staged, active, draining, retired and
quarantined component generations in canonical `sofia.db`, subordinate to the
existing exact `LocalRunLeaseStore` epoch. A partial unique index enforces one
ACTIVE generation per component. Activation refuses a second active
generation; replacement requires explicit active→draining→retired/quarantined
fencing before the staged generation can activate. Exact component kind,
release digest, Platform instance and Core identity are matched on every
transition.

The store controls only SDK/state/IPC eligibility. It neither starts nor stops
an OS process and therefore cannot turn a database transition into a process
success claim. Restart reconstruction preserves the active/fenced state;
expired RUN leases cannot mutate it. The SDK state-facade integration test now
uses this durable owner and proves that beginning drain immediately revokes an
old Core generation's state access.

Focused generation, component supervisor, SDK/state, module RUN and inference
regression command: **42 passed**. `compileall` and `git diff --check` passed.
ISO-03 remains **IN_PROGRESS**: a real worker transport/process must present
this endpoint identity, Platform must authenticate it, and drain must verify
process termination before a replacement is called healthy. No independent
Core restart or zero-downtime claim is made from the fencing store alone.

## ISO-03 independently hosted Core worker — 2026-10-24 UTC

Status: **production-coded and locally tested on Linux / BETA**. This closes
the prior local implementation gap; Windows, genuine Ollama, matching-revision
CI, independent review and live service commissioning remain separate release
acceptance.

Production owners and paths:

- `sofia.sdk.cognition` provides bounded, exact-schema provider-neutral
  `CognitiveRequest` / `CognitiveResponse` encoding. It preserves system and
  user context, tool proposals, capability allowlists, route hints and evidence
  references; it contains no callable or permission.
- `sofia.platform.core_worker.process` hosts cognition in a spawned OS process.
  Local IPC uses HMAC-authenticated `multiprocessing.connection` transport,
  Unix-domain sockets on POSIX and named pipes on Windows. All application
  payloads are bounded canonical JSON sent with `send_bytes`, not untrusted
  pickle objects.
- Readiness binds exact SDK protocol, Core identity, Platform instance,
  component generation, release digest and child PID. Platform activates the
  durable generation only after this authenticated readiness succeeds.
- `CoreWorkerRuntimeBackend` connects the worker to the existing
  `ComponentRuntimeSupervisor`; it requires the exact canonical RUN lease
  epoch. `CoreWorkerCognitiveEngine` connects the worker to the existing
  provider-neutral `CognitiveEngine` contract. `create_cognitive_engine()` and
  the production composition root accept an explicitly prepared controller;
  default single-process composition is unchanged.
- Each request is bound to the current canonical RUN owner/epoch, an expiring
  system-only `cognition.respond` projection, exact destination generation,
  schema and payload digest. The worker has no canonical state path, SQLite
  handle, CapabilitySystem, ActionSystem, signing key or owner credential.
- Replacement starts and authenticates the candidate as STAGED, fences the old
  generation before new admissions, drains it, verifies its PID exited, then
  retires/quarantines it before activating the candidate. Platform PID and
  unrelated component ownership do not change. Interrupted drain quarantines
  the old generation instead of claiming a clean stop.
- Deadline failure, explicit cancellation, health failure, protocol mismatch
  and process crash terminate/fence the worker and preserve an uncertain/fault
  boundary; requests are never automatically replayed. A renewed RUN lease is
  read from the canonical lease store before each dispatch, avoiding stale
  in-memory expiry.
- Startup recovery never reconnects or restarts blindly. UNKNOWN or verified-
  running prior state blocks replacement. Only an authoritative external probe
  reporting STOPPED permits the old active generation to be quarantined; a
  fresh generation may then be staged.
- A partial unique SQLite index enforces one active generation for the same
  canonical Core identity even when component IDs differ. Generation events
  remain append-only canonical evidence. SDK state access is revoked as soon
  as a generation enters DRAINING.

Local real-process evidence:

- Initial sandbox run: **3 failures / 13 passes**, all three process cases
  stopped at sandbox-denied socket creation (`PermissionError`); no product
  assertion ran in those failures.
- After bounded socket permission, the first run exposed and repaired an eager
  `platform.state` export cycle. The façade remains at its explicit module
  path, matching the earlier architecture repair.
- Expanded ISO-03 process/fencing/SDK/state/composition suite: **50 passed**.
- Existing supervisor integration subset: **20 passed**.
- Existing local/stub Ollama and pinned remote-inference compatibility suite:
  **56 passed**. These are not real-model calls.
- Final broader affected RUN/application/composition/SDK/state/inference
  command after supervisor integration and packaging classification:
  **123 passed** in 28.69 seconds.
- `compileall` across SDK/Core-worker/RUN/composition and `git diff --check`
  passed immediately after that exact test run.

Local tests prove real child PIDs, unchanged Platform PID, old PID exit,
authenticated readiness, Core identity collision denial, context codec
continuity, replacement continuity, stale state denial, crash/cancel fencing,
deadline and bad-protocol failure, interrupted-drain quarantine, and restart
reconciliation. The current environment has not run a genuine local/remote
Ollama model, Windows named-pipe worker, deployed service update, or current-
revision CI; none is claimed. Core B08 and ISO-04–08 remain next in dependency
order.

## ISO-03 application-owned worker completion — 2026-10-24

Source implementation commit: `5e38baff` (based on and preserving the
concurrent `b5e7b0d0` mentor outbox update). Status: **BETA**, locally tested;
not RELEASE CANDIDATE because Windows named-pipe, genuine Ollama,
matching-revision CI and independent review remain unverified.

- Normal `compose()` can now explicitly own the isolated Core worker through
  `CoreWorkerConfiguration`. Enabling it requires an exact SHA-256 release
  identity. Unsupported providers, dual-model routing and Fleet routing fail
  closed; there is no silent in-process fallback.
- `CoreWorkerProcessOwner` acquires and renews the fixed `component-core`
  scope in the existing canonical RUN lease table, registers the worker with
  `ComponentRuntimeSupervisor`, verifies authenticated readiness and owns
  shutdown. The watchdog's `runtime` lease remains separate and cannot be
  cross-used.
- The child holds a cross-platform lifetime file lock. After a Platform crash,
  a new owner may fence a prior generation only when that lock proves the old
  process stopped. Missing evidence or a still-held lock blocks automatic
  restart. PID reuse is not trusted.
- Lease-renewal loss terminates the child and stops new admissions without
  falsely rewriting canonical generation state under expired authority. A new
  owner must reconcile the stopped process before replacement.
- Runtime teardown stops the process, verifies termination through the
  existing supervisor/backend, retires its generation and releases the scoped
  lease. Core still receives no raw SQLite handle, capability gateway,
  signing key or owner credential.
- The AF_UNIX path is a short digest (Linux commonly limits paths to 108
  bytes); durable lifetime evidence retains the full endpoint digest. The
  real-process regression initially reproduced this path-length failure and
  the corrected suite passed.

Executed evidence:

- Consolidated ISO-03/SDK/state/configuration/composition/runtime/supervisor
  suite: **145 passed**.
- Final focused process/configuration/lease suite: **64 passed**.
- `pkg_run and not integration`: **622 passed**, 6,439 deselected.
- `pkg_safe and not integration`: initial sandbox run **1,848 passed, 2
  skipped, 9 failed** only because loopback sockets were denied and a spawned
  interpreter lacked this checkout on `PYTHONPATH`; the exact nine failed
  cases passed after authorized loopback execution with `PYTHONPATH=src`.
- `pkg_core and not integration` was interrupted after one observed failure;
  that failure was the same spawned-interpreter source-path mismatch and its
  exact case passed with `PYTHONPATH=src`. The incomplete broad run is not
  claimed green.
- `compileall` and `git diff --check` passed.

No production service, canonical writer, Fleet host, model or credential was
changed. Next eligible work is the Core B08/PLAT-01–08 requirement audit and
focused closure; ISO-04+, federation and generic restructuring remain deferred.

### ISO-03 release-byte attestation follow-up

Commit `a41d5900` closes a trust gap found during the Core/Platform audit. The
release digest in the endpoint is no longer a parent-supplied label that the
child merely echoes. Platform deterministically hashes the actual installed
`sofia` package (excluding bytecode caches and rejecting symlinks), requires
the configured digest to match before acquiring RUN authority, and places the
same expectation in the process specification. The spawned child recomputes
the digest from its own imported package before constructing an engine or
reporting readiness. A forged parent claim therefore times out and the staged
generation is quarantined; it never becomes ACTIVE.

Focused Linux evidence: **13 passed** for the first attestation suite, then
**77 passed** for Core worker, SDK contract, composition and configuration
regressions including parent-side mismatch, child-side mismatch and symlink
denial. A local wheel was built successfully at commit `6e638dd9`, installed
into a disposable target and imported with the reviewed dependency
environment; `python -m sofia --invalid` reached the installed launcher usage
boundary. The first no-dependency import correctly failed because `ollama`
was absent from that interpreter and is not counted as installed-runtime
success. Exact-revision CI remains unavailable (`gh run list` returned HTTP
403), and Windows/real-model acceptance remains open.

### Core/Platform broad regression completion — 2026-10-25 UTC

Commit `5d934a8c` fixes only the HNF benchmark test clock: short-lived hardware
telemetry is now timestamped when the test executes rather than when pytest
collects the module. Production continues to reject stale or missing resource
observations. Focused HNF benchmark coverage passed **11 tests**. The complete
local non-integration Core marker then passed **4,779 tests**, with **4
skipped**, **2,281 deselected**, and **8 subtests passed** in 353.43 seconds.

The Platform remains **BETA**. This local Linux result is not matching-revision
CI, Windows acceptance, genuine model/Fleet commissioning, independent review,
or permission to deploy.

### Exact-commit Platform and release-verification campaign — 2026-10-25 UTC

Exact tested source revision: `92b7c9b380256c4c1d34a13c07a0a3b03e4cd3b1`.

- `pkg_ops and not integration`: **1,400 passed**, 5,664 deselected.
- `pkg_safe and not integration`: **1,857 passed, 2 skipped**, 5,205
  deselected, 23 subtests passed.
- After repairing relocated evidence pointers while retaining byte-exact
  original requirements, `pkg_verify and not integration`: **838 passed**,
  6,226 deselected, 23 subtests passed.
- The final exact-commit all-package non-integration run: **7,052 passed, 6
  skipped, 6 deselected, 23 subtests passed** in 555.77 seconds.
- The five-stage validator passed at the exact revision: 652 NOT_WORKED_ON,
  16 CODED_UNFINISHED, 12 PRODUCTION_CODED, 100 TESTED, 0 TESTED_CI, and
  133/780 targeted evidence records. These counts were not promoted by this
  campaign.
- Disposable wheel build/install passed. Wheel size: 15,076,025 bytes;
  SHA-256 `5d487324d71b64f3fe4f059ced51702852b99af56547fba019b08738b19c15f6`.
  The installed Windows-startup helper resolves the import parent containing
  `sofia`, and the installed launcher reached its usage contract.

The first full run was not green (**7,042 passed, 6 skipped, 10 failed**). It
correctly exposed nine import-time freshness fixture defects and one actual
Windows package-root regression; commit `92b7c9b3` fixes those shared causes.
No production freshness, authorization, STOP or execution boundary was
weakened.

Platform remains **BETA**. Matching-revision GitHub CI is unavailable to this
environment, Windows and real Fleet/model commissioning were not performed,
and independent review remains open; no RELEASE CANDIDATE claim is made.

At exact documentation/evidence revision
`fe2cf85508186b13bd1077e5c6e2dcf46599d2ed`, the official
`sofia.platform.verify.gate --phase full` command completed all six required
steps and reported `accepted=True`. Its test step passed **7,052 tests**, with
**6 skipped**, **6 deselected**, and **23 subtests passed** in 517.55 seconds;
the isolated semantic step reported zero findings and demonstrated
reject-and-recover. Compilation, immutable V18 traceability, package-selection
nonemptiness and `pip check` also returned zero. The receipt is local and does
not substitute for unavailable GitHub CI, Windows/real-host commissioning or
independent review, so Platform remains **BETA**.

### Read-only Platform Control Center projection — 2026-10-25 UTC

Production source commit `6c05a61a` adds a bounded operator projection over
the existing canonical module observer and RUN/module-operation journals. It
is wired into the existing desktop Settings Fleet panel; it neither persists
state nor exposes an action API. Lifecycle, authenticated live health, RUN
status, recorded external-effect evidence and reviewed adapter-factory
availability remain distinct. A Settings process without the live application
factory registry reports that fact as `UNKNOWN` rather than reconstructing or
inventing factories. Job payloads, results, effect text, principals, approval
references and evidence contents are deliberately excluded.

Focused module observer/RUN/control-center evidence: **14 passed**. The
affected desktop Settings/UI batch passed **32 tests with 1 skipped** after
setting `PYTHONPATH=src` for this checkout. Its first run was **31 passed, 1
skipped, 1 failed** because a spawned interpreter resolved another checkout
and could not import `sofia.platform`; no production assertion failed. The
projection's negative test also verifies that a read against absent RUN and
module-operation tables does not create them. `compileall` and
`git diff --check` passed.

This closes the locally implementable read-only SF-09 view, not the entire
effectful operator HMI. Authenticated control actions, live in-process factory
display, Windows host acceptance, exact-revision CI and independent review
remain open. Platform remains **BETA**.

### Canonical module outcome projection — 2026-10-25 UTC

Production source commit `2326df17` connects settled durable module-operation
attempts to the existing typed `PlatformModuleObserver.outcomes()` boundary.
Only the latest terminal journal event for each request is projected, with a
hard 200-row bound. Admission, queueing, running and external-effect-attempted
events are not outcomes. Verified success/failure retains the authenticated
adapter-probe classification; ambiguous dispatch stays `OUTCOME_UNKNOWN` and
is never converted to success. The projection remains historical operational
evidence and never provides a current grant.

The production Core capability self-model now receives these real canonical
outcomes through its existing observer seam. Regression coverage proves a
queued request produces no outcome, verified completion increments only the
verified-outcome projection, uncertain dispatch remains unverified, and every
capability grant remains `UNKNOWN`. The module observer/RUN/Core-awareness and
B07 maintenance batch passed **28 tests** in 5.48 seconds; `compileall` and
`git diff --check` passed. CI, Windows, genuine adapter-host commissioning and
independent review remain open, so Platform and Core remain **BETA**.

Restart-path follow-up commit `9af69751` exercises this production projection
through full application shutdown and recomposition: the canonical verified
result is learned once and the restart observes zero duplicate lessons. The
maintenance/RUN/awareness batch passed **24 tests** in 6.76 seconds. An
exact-revision GitHub Actions query again returned HTTP `403 Forbidden`, so no
CI promotion is claimed.

### Verified module placement projection — 2026-10-25 UTC

Production commit `e72cec4c` persists the signed package placement mode and
isolation policy under the existing module lifecycle owner. Exact verified
package rediscovery safely backfills the additive policy row for older state;
a conflicting row fails closed instead of being overwritten. Update and
rollback atomically move the policy digest with the inactive staged package.

The canonical observer now reports a component placement only when the
matching package lifecycle is `ACTIVE` and a matching activation/resume has a
fresh externally verified adapter observation. A historical success remains
an outcome but stops being current placement/health after freshness expires.
Eligible-host and device-affinity fields remain empty/unknown when canonical
evidence does not establish them. The lifecycle/RUN/observer/Core-awareness
batch passed **39 tests** in 3.29 seconds; `compileall` and `git diff --check`
passed. Real multi-host commissioning, Windows, CI and independent review are
still open; Platform remains **BETA**.

Broad exact-revision regression at `e4e77f27052e47117bfe679965472c44193a70e2`:
`pkg_run and not integration` passed **631 tests** with 6,439 deselected in
70.96 seconds. `pkg_core and not integration` passed **4,782 tests**, with 4
skipped, 2,284 deselected and 8 subtests passed in 335.15 seconds. These are
local Linux results, not matching-revision CI or live-host acceptance.

### Durable module-outcome backlog progress — 2026-10-25 UTC

Production commit `2f3ed65e` (rebased without source changes from the tested
`df69a7b3` checkpoint) repairs audit finding A. The canonical module
observer now exposes a bounded monotonic journal page contract, and Core
maintenance persists its source cursor in canonical state. Verified lessons
and cursor advancement commit in one transaction. Restart resumes after the
last processed terminal event; concurrent/replayed pages remain idempotent.
Denied, cancelled, failed and uncertain outcomes advance progress but never
become lessons or authority. Observers without a durable cursor fail rather
than silently truncating a larger backlog.

Focused lifecycle/observer/RUN/maintenance coverage passed **46 tests**,
including 76 verified outcomes drained across eight ten-record pages and zero
duplicate learning after application restart. Exact-code broad gates at
`df69a7b3`: `pkg_run and not integration` passed **633 tests** with 6,439
deselected in 76.19 seconds; `pkg_core and not integration` passed **4,784
tests**, with 4 skipped, 2,284 deselected and 8 subtests passed in 397.98
seconds. `compileall` and `git diff --check` passed. CI/Windows/live-host review
remain open; Platform remains **BETA**.

After rebasing onto the six concurrent optional-module commits at
`cd896d87`, the focused maintenance/observer/awareness suite passed **27
tests** at `2f3ed65e`. The broader counts above remain evidence for the
identical source diff before that rebase, not exact-revision CI evidence.

### Universal Platform roles and protected Core Link bindings — 2026-10-25 UTC

Production commits `44f27ecc` and `2029241b` begin LINK-01/LINK-02 without
claiming their remaining transport or package-separation acceptance. A strict
mode-neutral role contract now declares composable `CORE_HOST`, `CORE_LINK`,
`MODULE_HOST`, and `STANDBY` responsibilities. The Debian systemd unit declares
its Core-host role, headless startup refuses a Core-free role before state
access, direct `SofiaApplication` construction has the same guard, and the
legacy `python -m sofia` import is lazy. The installed `companion-runtime`
entrypoint can report Core-free Platform status without importing Core or
opening `sofia.db`; desktop/tray/settings remain deliberately refused in
Core-Link mode until an authenticated remote client exists.

The new Platform-owned Core Link registry is a protected atomic JSON file,
not canonical Core state or a second SQLite writer. It stores only typed
destination identity, endpoint, secret-store reference, trust fingerprint,
audience/scopes, SDK version and lifecycle evidence. Whole-store and
per-binding CAS, an OS process lock, strict schema decoding, explicit
selection, restart persistence and immutable target identity prevent silent
switching. Endpoint, key, Core ID, Platform ID or generation drift quarantines
and deselects the binding; revoked bindings cannot be revived by contact.
Launcher status exposes only a redacted selected-binding projection.

Exact-source local Linux regression at `2029241b` passed **160 tests** across
Core Link, Platform roles, headless runtime/mobile hosting, legacy CLI,
composition/application, SDK, atomic-file and process-lock suites in 32.93
seconds. An installed wheel was built successfully with the approved locked
setuptools backend and contains the `companion-runtime` console entrypoint.
Inspection also confirms that the current unified wheel still contains Core
code and Sofía assets, so physical Core-free packaging, authenticated IPC,
pairing, remote Desktop/Tray and settings synchronization remain open. This
slice is **BETA**, not Release Candidate; CI, Windows, systemd commissioning
and independent review were not performed.

### Profile-scoped desktop launch/reopen — 2026-10-25 UTC

Production commit `4fc9e497` adds a desktop singleton beside the existing tray
singleton while keeping their lifetimes independent. A repeated desktop launch
does not construct a second window or application runtime: it writes a bounded,
same-user attention request and the existing workbench restores, raises and
focuses its window where the GUI permits, with a bell fallback. The attention
mailbox is atomic, mode-restricted, schema-checked, single-use and freshness
bounded. OS-backed locks recover automatically after process exit.

Lock identity is now a generic client-profile anchor rather than a required
canonical database path. A Core Link binding-store path plus exact binding ID
can derive independent desktop/tray locks without creating or opening
`sofia.db`; different Core profiles cannot collide by display name. This does
not make the current local-state tray a remote client and does not change its
shutdown semantics. The focused UI/process-lock/Core-Link/launcher regression
passed **52 tests** in 2.45 seconds on local Linux. Real Windows foreground
behavior, XDG launchers, remote transport, tray attention and crash/visual
acceptance remain open; the launcher/UI work remains **BETA**.

The complete non-integration `pkg_ui` gate at published revision `2a6c3419`
passed **587 tests**, with **1 skipped** and 6,812 deselected, in 60.46 seconds
on local Linux when localhost socket access was enabled. The first sandboxed
attempt produced 13 `PermissionError: Operation not permitted` failures, all at
ephemeral mobile HTTP server socket creation; rerunning the identical command
with network permission executed those cases successfully. This is local test
evidence, not Windows GUI, CI, real remote Core Link or host commissioning.

### Platform-routed isolated cognition — 2026-10-25 UTC

Production commit `c5c2f357` completes the previously blocked local production
path for dual-model and Fleet inference with the independent Core worker. The
worker process hosts exact primary/secondary provider identities, while
Platform remains the sole owner of route selection, model lifecycle, Fleet
placement, resource admission, pinned remote transport, activity evidence and
canonical state. A remote placement invokes the existing authenticated Fleet
client; a local placement invokes the matching role in the fenced child. The
configured no-local-fallback policy is preserved, and neither remote failure
nor a mismatched worker specification selects a substitute model.

The process protocol now includes a bounded model role and serializes complete
request/health exchanges over its single authenticated channel. This prevents
parallel route decisions or supervisor probes from cross-consuming replies.
Existing timeout, crash, lease-loss and generation-quarantine behavior remains
fail closed and does not replay uncertain model requests or external effects.

Local Linux evidence: **91 passed** in the focused process/routing/Fleet/split
topology batch, **19 passed** in the final real-process file, and **207 passed**
in the broader composition/lifecycle/conversation/provider regression. The
initial sandbox baseline's ten failures were exclusively denied local socket
creation; the same suite passed with bounded socket permission. Genuine local
or remote Ollama, Windows named pipes, current-revision CI, live Fleet host
commissioning and independent review remain open. Platform stays **BETA**.

### Authenticated Core Link conversation host — 2026-10-25 UTC

This Core Link batch adds the host-side canonical access projection,
authority-free SDK request/response contract, conversation gateway and pinned
mutual-TLS transport. Client certificates are enrolled or revoked only by an
exact one-use SAFE approval; every request rechecks expiry, scope, destination
Platform, Core identity, active isolated-Core generation and operator STOP.
Principal and audience come from canonical enrollment, never request JSON.
The Core-free client resolves certificates through a protected credential
reference and pins the exact server public key from the explicitly selected
Core binding.

Conversation creation/selection, bounded keyset history, sending, result
reconciliation and cancellation status use the existing canonical application
and lifelong turn store. Stable client idempotency keys become canonical event
IDs, so reconnect/replay returns the stored response rather than invoking the
model twice. A processing turn is reported as `OUTCOME_UNKNOWN`; the current
provider boundary cannot truthfully abort a call already in flight. Source
device and client-time metadata now propagate through every production
interaction-service override instead of being dropped by specialized routes.

Production startup exposes the mTLS listener only through explicit host
configuration and only while a healthy, generation-fenced independent Core
worker exists. Compatibility-mode Core cannot accidentally be advertised
remotely. Local Core Link state remains a protected JSON binding registry and
never opens or creates a client-side `sofia.db`.

Local Linux evidence after integration: a real loopback TLS conversation
passed with generated CA/server/client certificates and rejected a mismatched
server pin. The focused Core Link, binding, conversation, Core-worker and
configuration batch passed **120 tests** in 65.39 seconds. `py_compile` and
`git diff --check` passed. Remote Desktop/Tray adoption, durable streaming, a
cancellable active provider request, Windows acceptance, installed Core-free
packaging, CI and independent review remain open; LINK/Core B08 stay **BETA**.

### Core-free Desktop and Tray conversation clients — 2026-10-25 UTC

The generic launcher now routes `desktop` and `tray` to Core Link clients when
the local Platform has `CORE_LINK` without `CORE_HOST`. This route never
constructs `SofiaApplication`, opens canonical SQLite or imports any
`sofia.core.*` module. Package export initializers for Platform configuration,
state, RUN, SDK, UI and Core Link were made lazy to enforce that physical
boundary while preserving their public imports for compatibility-mode hosts.

The remote Desktop uses the exact explicitly selected binding, protected
credential reference, endpoint identity, Core identity/generation and pinned
mTLS transport. It provides authenticated status, conversation selection,
bounded history and sends. Client-owned session selection, draft text and a
pending idempotency key live in mode-restricted atomic JSON scoped to the exact
binding/Core—not `sofia.db`. A connection loss or `OUTCOME_UNKNOWN` preserves
the draft and request identity; restart queries `conversation.result` and
never blindly resubmits the turn. The host now durably claims conversation
creation idempotency in canonical state, so a lost creation response cannot
silently create another session on retry.

The independent Core Link tray/status fallback performs authenticated status
only, does not create a conversation, can launch the Desktop, and has its own
profile-scoped singleton lock. Closing either local UI never invokes a remote
Core/Platform stop. The full existing local Desktop/Tray implementation and
legacy Core-host launcher remain available.

Local Linux evidence: **38 passed** in the Core Link/Desktop/Tray batch,
including real mutual-TLS remote Desktop conversation and restart
reconciliation; the complete non-integration UI gate passed **590 tests with
1 skipped** in 59.73 seconds; and the complete non-integration RUN gate passed
**655 tests** in 81.40 seconds. The focused configuration/state/SDK gate passed
**87 tests**. Windows GUI foreground behavior, native tray protocols, visual
acceptance, remote Settings, installed split-wheel inspection, CI and
independent review remain open. The client migration remains **BETA**.

### Canonical Settings authority and Core Link Settings client — 2026-10-26 UTC

This batch extends the existing `RuntimeUserSettingsStore` rather than adding
a configuration database. `CanonicalSettingsService` supplies typed field
ownership, explicit LIVE/NEXT_OPERATION/COMPONENT_RESTART/PLATFORM_RESTART
classification, canonical compare-and-swap revisions, durable per-client
idempotency, append-only change events, and separate saved/effective apply
receipts. Client-owned UI fields are excluded from the Core-host projection;
Core and host writes require independent authenticated field scopes. A value
saved in SQLite is never by itself reported as applied.

The application registers a reviewed LIVE apply callback for environment,
NEURO, and avatar-routine settings. Provider/model, Fleet-discovery,
background-worker, and integration changes retain their truthful pending
restart or next-operation state. Apply exceptions retain the saved revision,
old effective revision, error class, and auditable event. Existing trusted
local settings callers remain compatible: an out-of-band change to the legacy
canonical row is imported into the revision journal as UNKNOWN, invalidating
stale remote CAS tokens instead of being silently overwritten.

Core Link adds authenticated settings snapshot, update, and bounded event-page
operations. The remote Settings client uses the selected identity/generation,
pinned mutual TLS, protected credential reference, and authorized projection;
it opens no local canonical database and imports no Core package. It provides
JSON-typed field editing, authoritative resynchronization after every save,
periodic revision notification polling, saved/effective diagnostics, and an
independent profile-scoped singleton. The generic launcher routes `settings`
to this client in Core-Link-only mode while preserving the local Core-host
Settings window.

Local Linux evidence: focused settings/Core-Link/configuration/launcher tests
passed **48 tests**; the combined settings, Core Link, environment reload and
runtime settings batch passed **35 tests** with the one loopback case selected
separately; that real mutual-TLS case passed **1 test**. The complete
non-integration `pkg_ui` gate passed **598 tests with 1 skipped** in 75.89
seconds when disposable localhost sockets were permitted. The identical
sandboxed run's 14 failures were all socket-creation denials and not code
assertion failures. Windows GUI acceptance, native notification delivery,
component-restart execution for pending settings, CI, host commissioning and
independent review remain open. Settings/Core Link remain **BETA**.

### Per-user UI launchers and read-only remote Control Center — 2026-10-26 UTC

The installed `companion-runtime` facade now includes `desktop`, `tray`,
`settings`, `control-center`, `status`, and an explicit `install-ui` operator
command. The installer creates four current-user Windows Start Menu shell
links through the standard WScript shell-link API and, when requested, the
same current-user Desktop links. Tray and Desktop login startup are separate
HKCU choices; disabling either removes its value without uninstalling the
client. No machine-wide service, scheduled task, elevation, Core process,
state path, binding secret, or credential is embedded in a shortcut. Taskbar
pinning remains the normal user-controlled Windows action.

Linux installation writes four per-user XDG application entries and optional
Desktop/Tray XDG autostart entries. It uses Desktop Entry argument escaping,
atomic writes, rejects target symlinks, needs no root/system service, and
removes disabled autostart entries. The existing Core Link tray is also the
documented small status-window fallback on sessions without a compatible
notification-area protocol.

The distinct Core Link Control Center is a profile-scoped singleton that reads
authenticated Core identity/generation, Platform runtime/STOP state, and
canonical settings saved/effective revisions. It does not display static demo
health, instantiate Core, open client SQLite, or gain effectful authority.
Local compatibility mode continues to open the established full settings and
control surface.

Local Linux evidence: launcher, role, process-lock, Windows registration and
XDG regression passed **35 tests**; the complete non-integration `pkg_ui` gate
passed **598 tests with 1 skipped** and 7,205 deselected in 73.36 seconds with
disposable localhost access. A no-isolation wheel build succeeded, and wheel
inspection found the new launcher/Control Center modules plus the installed
`companion-runtime` console entrypoint. Actual Windows Start Menu/foreground
visual acceptance, Wayland compositor acceptance, signed installer creation,
CI and independent review remain open. The launcher slice remains **BETA**.

### Module-health identity and benchmark-host attribution hardening — 2026-10-26 UTC

The current-health audit reproduced a trust-boundary defect in
`CanonicalPlatformModuleObserver`: a recent externally verified attempt was
selected by module ID alone. A newly active package could therefore inherit a
fresh success observation from an older signed package. Runtime health now
requires the exact active lifecycle package digest, activation profile,
completed lifecycle revision and activation/resume request before it can be
projected as HEALTHY. Historical outcomes remain auditable but cannot become
current health. A changed-package regression proves the old receipt yields
UNKNOWN_STATE.

The benchmark audit also confirmed that built-in CPU/RAM/storage runners are
local process functions while plans were generated for every trusted inventory
record. `BenchmarkCoordinator` now requires a verified local machine identity,
queues built-in work only for that identity, rechecks the host at the RUN
handler boundary, and persists `execution_host_id` on both success and failure.
Fresh benchmark scores exclude missing or mismatched execution-host evidence,
so historical unbound measurements cannot affect placement. Production
composition derives this identity from local machine discovery rather than a
renameable host environment value. Remote inventory remains eligible for
placement observation but not local measurement; authenticated remote agent
benchmark dispatch remains an explicit open feature.

The safe-idle audit found the current telemetry admission already fails closed
for missing, stale or unsafe temperature, throttling and power-limit evidence;
no synthetic healthy telemetry or code relaxation was added. Focused module
operation/observer/HNF tests passed **27 tests**. The complete non-integration
`pkg_ops` gate passed **1,427 tests** with 6,381 deselected in 63.67 seconds,
and `pkg_run` passed **661 tests** with 7,147 deselected in 88.62 seconds, using
the permitted disposable IPC/localhost boundary. Linux tests do not replace
Windows, real Fleet-agent, CI, or independent-review evidence. Platform
readiness remains **BETA**.

### Exact component update-impact planning — 2026-10-26 UTC

ISO-07 now has a production-owned, effect-free planning boundary on the
existing `ComponentRuntimeSupervisor`. `ComponentUpdateCandidate` binds exact
source and target SHA-256 identities, the declared change class, explicit
compatibility evidence, and exact shared-ABI consumers. The supervisor derives
the plan from its durable registered component/dependency graph rather than a
caller-supplied topology. Core-only, optional-module-only and inference-only
changes drain only the selected component and pause its transitive dependents;
unrelated components are explicitly retained. Platform and canonical-state
schema changes broaden to a Platform restart. A shared ABI broadens to its
declared consumers and their dependents, and an ABI consumer containing the
Platform requires a Platform restart.

UNKNOWN or failed compatibility, wrong component kind, unknown targets or ABI
consumers, and data-only changes without a reviewed atomic reload contract all
fail closed. The result reports only whether impact is resolved; it carries no
SAFE/RUN authority and cannot stage, approve, drain, restart, or activate a
component. This closes the ISO-07 planning primitive, not ISO-05 activation or
ISO-08 live acceptance.

Local Linux evidence: the focused impact/supervisor/generation gate passed
**22 tests**; the extended gate including real independently hosted Core
process replacement passed **41 tests** with permitted disposable local IPC.
The affected non-integration `pkg_run` selection also exited successfully.
No Windows, real module/provider update, CI, live-host, or independent-review
evidence is claimed. ISO-07 is **BETA**; ISO-04, ISO-05 and ISO-08 remain open.

### Representative isolated Research module process — 2026-10-26 UTC

ISO-04 now has one real optional-module process slice rather than only the
previous in-memory adapter test. `ResearchModuleProcessAdapter` hosts the
reviewed `research.compare_claim_sources.v1` implementation in a distinct OS
process over bounded, versioned, HMAC-authenticated IPC. The entrypoint and
capability are fixed in reviewed Platform source: it is not a generic command
runner and never imports candidate package code. The worker receives no
canonical SQLite path or handle, cannot authorize itself, performs no browsing
or external effect, and Platform's existing `CapabilitySystem` still evaluates
authorization before the proxy handler may dispatch.

`ReviewedResearchProcessFactory` binds an exact signed-package digest,
component ID, local host identity, reviewed OBSERVE/ADVISORY profiles and
resource/isolation contract. Production construction exposes an explicit
registration hook; discovery never registers it and registration itself grants
no lifecycle authority. Activation still uses the existing signed lifecycle,
one-use owner approval and durable `ModuleOperationCoordinator` RUN handler.

The audit also repaired a real ownership defect: the coordinator previously
dropped its adapter reference after activation. That could orphan a real child
and made reconciliation rebuild a different inert adapter. It now retains the
exact dispatched adapter, uses it for reconciliation, withdraws its exact
capability handler on shutdown, and then verifies safe stop. Application
shutdown closes RUN workers before this module teardown. Bounded IPC timeout
force-terminates the worker so a late response cannot be mistaken for a later
request. Process-backed pause is now two-phase: the exact one-use approval
withdraws capabilities and commits DRAINING before stop dispatch; only an
identity-bound STOPPED observation commits PAUSED. A lost stop receipt remains
DRAINING/UNCERTAIN, and an idempotent retry resolves to the same RUN job rather
than replaying the external stop.

Local Linux evidence: **16 tests** passed for real process startup, signed
package + one-use approval + durable RUN activation, authenticated health,
actual capability execution, authorization denial, oversized input, timeout,
post-dispatch lifecycle-commit uncertainty, verified two-phase pause,
ambiguous-stop no-replay, capability withdrawal and shutdown. The combined
module lifecycle/package/compatibility/process/command gate passed **47 tests**,
and application shutdown/
acceptance regressions passed **20 tests**. The complete affected
non-integration `pkg_run` gate passed **678 tests** with 7,147 deselected.
ISO-04 remains **ALPHA** overall:
inference-provider hot replacement/rollback, authenticated remote placement,
restart reconstruction of a pre-existing external worker, Windows process
acceptance, CI and independent review remain open. No automatic module install
or production activation was performed.

### Platform-owned provider boundary for isolated Core — 2026-10-26 UTC

The remaining Core/provider ownership defect in the isolated cognition path is
closed in production composition. `CoreEngineProcessSpec` still pins the exact
primary/secondary provider, model and generation parameters, but the Core child
no longer constructs Ollama or test-LLM adapters. `PlatformProviderBinding`
routes each role to a distinct Platform-owned inference process. The
authenticated Core IPC channel carries one bounded provider-neutral request;
the second HMAC-authenticated provider channel checks exact configuration,
release, role, RUN epoch and payload/response digests. Tool calls remain
proposal data and neither child receives canonical SQLite, SAFE grants or an
execution handle.

Missing roles, changed configuration, extra roles and runtime provider failure
fail closed. Each provider independently attests the installed release bytes
before readiness. A provider failure makes the Core request outcome uncertain,
quarantines that Core generation and is not retried. The existing outer Fleet
placement boundary remains authoritative: remote placement bypasses the local
adapter through the pinned transport, while an admitted local call uses the
Platform-owned binding. Model lifecycle/resource policy also remains in the
Platform wrappers. Compatibility mode continues to use the same provider
factory directly until isolated operation completes broader acceptance.

Each provider role now also owns a scoped lease in the canonical RUN lease
table and an exact `ComponentGenerationStore` INFERENCE row. Readiness activates
that row only after the child proves component ID, generation, package release,
configuration and lease epoch. Every inference call rechecks the live lease and
exact active generation. Normal verified shutdown retires the generation;
externally drained or uncertain shutdown quarantines it. A prior ACTIVE row is
never silently reconnected or replayed after restart: startup blocks pending an
explicit reconciliation policy.

Local Linux evidence: the real-process file passed **26 tests**, including
distinct Platform/Core/provider PID assertions, exact-binding denial,
provider-failure quarantine, independent release-byte rejection, authenticated
provider health, durable restart fencing, stale-generation dispatch denial and
verified ordered shutdown. The affected
Core/cognition/configuration/HNF/provider/split-topology
suite plus generation-store regressions passed **137 tests**. Restricted execution initially denied AF_UNIX socket creation; the
identical suite passed with the permitted disposable local IPC boundary. No
genuine Ollama request, Windows named-pipe test, CI, live Fleet host or
independent review is claimed. Isolated provider ownership is **BETA**;
independent replacement/rollback (ISO-04/05), safe-probe restart
reconciliation and host acceptance remain open.

The complete affected non-integration `pkg_run` gate passed **685 tests** with
7,147 deselected in 154.11 seconds on local Linux. This is local regression
evidence, not matching-revision CI or independent review.

### Bounded Core-worker startup attestation — 2026-10-26 UTC

The audited hard-coded 10-second startup deadline is replaced by the typed
`CoreWorkerConfiguration.startup_timeout_seconds` setting (60 seconds by
default, bounded to 5–300 seconds and required to fit inside the canonical RUN
lease TTL). `SOFIA_CORE_WORKER_STARTUP_TIMEOUT_SECONDS` exposes the reviewed
deployment override. Production composition passes the value to the process
owner; no digest or identity check is disabled.

The child now establishes authenticated local IPC and reports an exact
protocol/endpoint/PID `starting` record before potentially slow release-byte
hashing. It becomes ready only after the child independently hashes the
installed package and verifies the configured SHA-256 release. The parent uses
one total monotonic deadline across connection, startup status, attestation and
readiness. Sanitized errors distinguish pre-IPC child exit, authenticated IPC
timeout, startup identity mismatch, attestation/identity rejection, invalid
startup contract and generic child startup failure without exposing paths or
private exception text.

Local Linux evidence: Core process/configuration regressions passed **60
tests**. A deterministic delayed-attestation process test proves deadline
cleanup terminates the child, quarantines (rather than activates) the staged
generation and leaves no active Core identity. Existing replacement, health,
cognition and shutdown tests remain green. Actual Windows spawn/named-pipe and
18–19 second package-hash timing, installed-wheel startup, CI and independent
review remain required; this repair is **BETA**, not RELEASE CANDIDATE.

The complete non-integration `pkg_run` gate passed **686 tests** with 7,148
deselected in 111.71 seconds on the same local Linux source.

### Windows shortcut quoting and cross-platform launcher selection — 2026-10-26 UTC

Windows `.lnk` creation no longer appends user-controlled paths/arguments after
PowerShell `-Command` and relies on ambiguous `$args` parsing. Platform invokes
a fixed UTF-16LE `-EncodedCommand`; shortcut path, target, Windows-quoted
arguments, description and working directory travel as separate environment
fields. This preserves Unicode Sofía names and paths containing spaces, quotes
or shell metacharacters without evaluating them as PowerShell. Every expected
shortcut must exist as a regular non-symlink file before the installer returns
a receipt. Start Menu, optional Desktop and HKCU startup behavior remain
per-user and require no elevation.

The XDG CLI regression now explicitly selects Linux semantics; it no longer
expects a Linux receipt merely because that test happens to execute in a
Windows job. Production platform selection is unchanged. Launcher payloads
still invoke only `sofia.platform.launcher`, carry no database/credential path,
and Core-Link role tests prove installation does not import or start Core.

Local Linux evidence: focused launcher/role coverage passed **25 tests**. The
complete non-integration `pkg_ui` gate passed **599 tests with 1 skipped** and
7,239 deselected in 100.07 seconds. Real Windows COM shortcut creation, Start
Menu visual launch, HKCU registry inspection, installed-wheel execution, CI and
independent review remain open; the launcher remains **BETA**.

### Optional-release, package ownership and expiring-fixture remediation — 2026-10-26 UTC

Implementation commit `c5c9249f` preserves the approved 47-module catalog and
its fail-closed release policy. The previously failing incomplete-review test
had become a false negative after all 47 source candidates arrived: its helper
silently constructed a complete policy. It now deliberately omits one reviewed
package identity. Separate negatives prove missing per-module data
classification and missing capability schema are rejected. Production batch
cardinality and receipts derive from the canonical catalog set, preventing a
future catalog edit from leaving stale magic counts in enforcement code.

The five audit-listed test files now have explicit cross-package ownership:
Core Link (`pkg_ui`, `pkg_net`, `pkg_safe`), optional-module lifecycle/release
(`pkg_run`, `pkg_safe`, `pkg_verify` as applicable), and UI launcher security
(`pkg_ui`, `pkg_safe`). The all-package collection proof found **7,836 unique
non-integration tests** and nonempty selections for all 22 configured package
markers; this collection did not execute those tests.

Imported module-operation fixtures no longer bind approval deadlines or
authenticated adapter observations to module-import time. Each invocation
creates one consistent bounded operation clock, while an explicit negative
still proves expired requests are rejected. LIFE's historical-receipt test now
orders its synthetic evaluation after the real asynchronous RUN receipt rather
than predating genuine evidence on a loaded host. Production expiration,
freshness, receipt and authorization checks were not relaxed.

Local Linux evidence on the implementation tree: optional release/grouping
coverage **70 passed**; named expiry/restart/backlog/Control Center/LIFE
regressions **5 passed**; `pkg_run` **752 passed**; `pkg_safe` **2,570 passed,
2 skipped, 23 subtests passed**; `pkg_verify` **878 passed, 23 subtests passed**.
Restricted execution initially denied AF_UNIX worker sockets; complete RUN and
SAFE results were obtained with the approved disposable local IPC boundary.
No signed owner release, module installation, Windows execution, matching-SHA
CI or independent review is claimed. Platform remains **BETA**.
