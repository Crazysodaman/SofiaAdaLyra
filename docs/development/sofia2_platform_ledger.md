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
