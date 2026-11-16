# Project Aegis | Unified Platform-First Startup and Legacy Launcher Retirement

**Design date:** 2026-11-16  
**Status:** PROPOSED DESIGN / NOT CODED / NOT TESTED / NOT INSTALLED  
**Scope:** One owner-operated Aegis Fleet. Windows and Debian/Linux native Platform, independent Cores, modules, SDK, Core Link, headless/GUI/TUI, offline and multi-host startup.  
**Baseline inspected:** `Crazysodaman/SofiaAdaLyra` GitHub `main`, `b330b079d01639c2f2f49a60202c3a93f1874bac`. The master TODO is a planning aggregator; original security/release acceptance remains authoritative.

## Decision

1. **Aegis Platform is the only system-level startup owner.** The OS starts/monitors the *native Rust Aegis Platform service*. The Platform is healthy without any installed Core. All Cores and modules are separately packaged and managed with explicit per-component authority and independent process supervision.
2. **Retire Sofía-first launches from the supported installed experience.** `python -m sofia`, `companion-runtime desktop` (when it directly creates Sofía), direct `sofia.core.launcher` UI/CLI, and the integrated Sofía runtime service **must not be supported production activation paths**. Migrate any useful UI code to a *Platform Core Link client* and any cognitive code to an independently hosted Core worker. Do **not** delete existing source until the replacement passes equivalence and rollback tests.
3. **One product name and operator command: `aegis`.** The name is a target CLI/desktop interface, not a statement that the binary exists now. The service binary remains `aegis-platform-service`; it is an internal OS/service entry point, not a normal user console command. Client processes must never create an unregistered Core writer or duplicate Platform daemon.
4. **Installed != enabled != approved != active != autostart.** A Core or module is never started merely because a directory/package exists, a network peer is discovered, a name matches, or a user opens a UI. Only a verified installed release, matching SDK/ABI, owner-approved activation, current policy and chosen startup mode allow process start.
5. **One logical control plane, local host authority.** Each Platform holds its own lifecycle/STOP/SAFE, OS process and hardware decisions. Fleet messaging coordinates enrolled Platforms but never bypasses local admission. Remote Cores retain their canonical state/writer authority.
6. **No generic SDK protocol bump just for this launch redesign.** Preserve version 1.0 wire compatibility if feasible. New startup management commands should be reviewed and negotiated; breaking changes use explicit migrations.

## The user experience

### Normal day

- After installation, the Windows Service Control Manager / Linux `systemd` starts the **Aegis Platform** service at boot with a verified installed profile. No user login, desktop, model, or Internet connection is needed.
- On a Core Host, Platform starts only those signed and *previously approved* Core workers with `startup_mode=on_platform_ready`, after reconciling old state and enforcing any current STOP/revocation. A Core's private state is not created by merely starting Platform.
- On a Core Link / Module Host, Platform stays Core-free. It can connect to a selected, **already enrolled and pinned** remote Core; it must never discover and auto-select a Core.
- On Windows user login, the optional **Aegis Control Center** tray/GUI connects to Platform. On headless Linux, the local authorized operator uses `aegis tui` or `aegis status` through Platform IPC. Closing a client never stops Platform or a Core.
- An optional `aegis chat --core <exact-id-or-resolved-alias>` client opens a session through authenticated Core Link/Platform routing. `aegis chat` with no Core selected prompts for selection; never selects by proximity or display name alone.
- If a Core is missing/disabled, Aegis Control Center still opens and shows `No active Cores`. It offers **Install**, **Activate**, **Start** or **Select Remote Core** only as authorized actions, not as automatic side effects.

### Proposed commands (CLI contract, **not yet implemented**)

| User intent | Proposed command | Important behavior |
|---|---|---|
| Launch management in a terminal | `aegis` or `aegis tui` | Shows status/menu; no implicit Core activation |
| Open desktop dashboard | `aegis gui` | Connects to existing Platform; GUI is not the daemon |
| Inspect Platform and component health | `aegis status` | Shows service, identity, modules, all installed and active Cores, errors |
| Start the OS Platform service | `aegis service start` | Uses OS service manager and authenticated local authority |
| Gracefully stop the OS Platform service | `aegis service stop` | Drains/fences child work; distinct from emergency STOP |
| Diagnose startup problems | `aegis doctor --startup` | Read-only checks, no automatic repair or privilege escalation |
| Display Core inventory | `aegis core list` | Exact Core IDs, installation, signing, running and startup policies |
| Start/stop a specific approved Core | `aegis core start <id>` / `aegis core stop <id>` | Per-Core generation and current approval checks |
| Configure approved Core boot policy | `aegis core autostart <id> on|off` | Separate reviewed owner authorization |
| Start/stop one installed module | `aegis module start <id>` / `aegis module stop <id>` | Per-module policy, dependencies and resource admission |
| Open Core conversation | `aegis chat --core <id>` | Thin client; never instantiates Sofía locally |
| Enable/clear operator STOP | `aegis operator-stop engage` / `... release` | Existing SAFE/STOP authorization, **not** OS service stop |
| Verify installed release | `aegis release verify` | Exact signatures, digests, provenance and compatibility |

No unreviewed commands are production promises. An initial launcher may provide `aegis` from the installed SDK/Platform package, but the underlying service remains a native installed service. On Windows desktop, the Start Menu shortcut targets `aegis gui`, never `python -m sofia`.

## Reference startup architecture

```text
OS boot / manual service request
    |
    +-- Windows SCM / Linux systemd [only OS service owner]
          |
          v
    aegis-platform-service (Rust; single host supervisor)
          |
          +-- exact installed release/config + platform identity verification
          +-- lock, lease, RUN generation, SAFE/STOP and recovery reconciliation
          +-- core-free Python Platform state/management adapter (existing boundary)
          +-- authenticated local management IPC (one canonical API)
          |
          +-- Platform control READY  <--- Aegis CLI/TUI/GUI/tray clients
          |
          +-- verified per-component registry + desired-state reconciler
                |
                +-- core-free essential components (as applicable)
                +-- approved independent module workers (dependency order)
                +-- approved autostart Core workers, each isolated
                |       +-- Sofía Ada Lyra (own UUID/state/writer)
                |       +-- SDK Validation Core (own UUID/state/writer, optional)
                +-- optional providers/inference modules if approved/admitted
                +-- authenticated Fleet links to separately enrolled Platforms
```

**Core-free requirement:** the Platform *can supervise* real Core worker processes without importing cognitive code into its own process. The Rust worker response currently includes `core_started: false` to protect the core-free adapter; don't reinterpret that as "the host may never supervise another Core". In the proposed design, name the distinction explicitly: `core_loaded_in_platform_process=false` versus separately reported `active_core_workers=N`, with an independently reviewed schema migration when necessary.

## Detailed startup phases and receipts

| Phase | Action and owner | Required observable result | Failure behavior |
|---|---|---|---|
| S0 | SCM/systemd launch the installed Rust service | OS service instance, exact binary/release identity | Refuse changed binary/config; no unsafe fallback |
| S1 | Native Platform validates signed installed profile, identity UUID, existing private state, file ownership | `INSTALLATION_VERIFIED` | Fail closed; safe diagnosis only |
| S2 | Take process singleton, local lease and service generation; inspect durable STOP and interrupted operations | `PLATFORM_FENCED` | No duplicate daemon; uncertain outcomes reconciled, not blindly repeated |
| S3 | Start minimal Core-free Platform adapter, bind authenticated IPC, bootstrap read-only health/diagnostics | `CONTROL_READY` independent of Core count | If management cannot authenticate, no false READY |
| S4 | Reconcile installed registry, active release pins, module/Core desired state and exact ABI/SDK ranges | `REGISTRY_RECONCILED` | Quarantine questionable entries; report blocked, leave Platform usable |
| S5 | Start approved Core-independent local components and module dependencies; admit resource limits | `BASE_SERVICES_READY/DEGRADED` | Nonessential failures isolated, not a daemon crash |
| S6 | Revalidate each Core autostart rule, private state, scope, signer, version and worker generation; start eligible Core processes | Per-Core `RUNNING/READY`, `BLOCKED`, `STOPPED` or `FAILED` with receipt | Never automatically instantiate unapproved Core or second writer |
| S7 | Start dependents requiring a specific active Core, only if approved; reconnect pinned Fleet Core Link | `COMPONENTS_RECONCILED`; per-dependency status | Remote offline is degraded, never secret automatic fallback |
| S8 | Continue health checks, bounded recovery and event-driven state convergence | `OPERATIONAL` or `DEGRADED`, durable events | Bounded backoff, no startup/restart storm |

**Control plane readiness is not conversation readiness.** The Platform can be `OPERATIONAL` with zero Cores. The UI must show that distinction instead of claiming Sofía is alive merely because the service answered.

### Start intent schema (design; no authority originates from this data)

```yaml
platform:
  os_service_boot: automatic          # owner-selected during verified installer setup
  recovery_policy: bounded
  ui_autostart_at_user_login: false    # separate from OS service
cores:
  <core-uuid>:
    installation: verified
    enabled: true
    startup_mode: on_platform_ready    # or manual / on_demand (later, explicit)
    last_approved_release_digest: <sha256>
    state_lineage_id: <lineage-id>
    requires_authorized_revalidation: true
    resource_profile: interactive
modules:
  <module-id>:
    startup_mode: on_platform_ready    # or manual
    dependency_core_id: null
    resource_profile: background
```

This is a requirements sketch, **not** a drop-in configuration format. Production data lives in the existing durable Platform registry, not in a separate YAML authority file. Persist desired state and observed state separately. Never include an owner secret in this data.

## Multi-Core rules

- One Core identity UUID and protected state lineage per Core, with only one active canonical writer for that lineage. Sofía and the SDK Validation Core **must not share** `sofia.db`, private identity, Constitution, personality, grant or memory.
- The common Platform service manages either Core through the *same SDK worker contract*, not `if name == "Sofía"` branches. A generic Core worker/definition has an independent signed digest, state root, generation, SDK compatibility range and health report.
- Separate per-Core `installed`, `enabled`, `startup_mode`, `desired_run_state`, `observed_process_state`, `health`, `generation`, `last_error`, `last_approved_digest`. Names/callsigns are non-authoritative display labels. Deletion/restoration preserve distinct owner-private state.
- No auto-install from SDK discovery. A signed package doesn't mean owner consent. Co-hosting different Cores on one Platform remains **blocked until tested** for identity/state/writer isolation; use two disposable Platform instances first if necessary.
- Core crash: Platform reconciles actual process identity and current generation, releases only verified stopped worker resources, applies restart budget, and records why a worker is blocked. Do not revive a revoked or operator-stopped Core.
- Core update: drain one Core's requests and effects, fence generation, verify new bytes/SDK, restart *that Core*, recover conversation state, and preserve Platform and other Core uptime. A Platform ABI upgrade or state-schema change can still require a reviewed wider maintenance window.

## Module and resource startup policy

- Separate **mandatory** Core-free control components from **optional** capability modules, then topologically order dependency-aware starts. Detect cycles and missing dependencies and block only affected modules.
- Start *only* approved installed modules; signed Package/Module SDK compatibility, current grants, external device permissions and Fleet enrollment are checked at activation and consequential calls.
- Do not eagerly start optional heavy models, GPU workers, avatar renderers or voice generators simply because a Core started. Load on eligible demand/explicit autostart policy, budget host resources, and yield to gaming activity on Venus. Platform control readiness must not depend on Ollama availability.
- On Artemis: a Core-host VM can run Aegis headlessly. On Venus: Windows Platform can be Core Link + module/inference host without loading Sofía Core. Third hosts can run Platform with zero Core. No unstated software role changes on any physical machine.
- Multiple signed modules may use one approved resource/telemetry owner rather than duplicate pollers; no additional mandatory daemons introduced for startup.
- If a pinned remote host is down, report `REMOTE_UNAVAILABLE`; don't silently execute on a different computer or download a cloud model.

## Shutdown, operator STOP and recovery

1. **OS service stop:** mark `DRAINING`, reject new work, notify clients, cancel/complete bounded operations, stop dependent modules then Core workers under generation checks, release local leases when independently verified, commit receipts and stop adapter then native service. On timeout persist `UNCERTAIN`, preserve fencing; don't claim clean shutdown.
2. **Core stop:** affects exactly the selected Core and its dependent capabilities. Other Cores, unrelated modules and Platform stay running.
3. **GUI/terminal close:** disconnects *only that client*. Does not stop Platform or active Cores.
4. **Operator STOP:** security/effect-admission boundary, independent of service stop. Exact safety-critical control remains available even when automatic Core starts are suppressed. No background Core may clear STOP.
5. **Power failure:** next OS start reads persisted intent and observed state, independently checks real process identity and writer leases, reconciles pending operations before any restart, and refuses stale/replayed generations.
6. **Bad upgrade:** use trusted signed rollback and preserve state/identity; no fallback to the Sofía-first legacy launcher. A rollback must be separately approved where policy requires.

## Startup error UX and observability

Display *service*, *Core*, *module*, *Fleet* and *model* readiness separately. Example:

```text
AEGIS PLATFORM      READY      Venus / Core Link + Module Host
OS SERVICE          RUNNING    Signed release verified
LOCAL CORES         0         Expected on this host
SELECTED CORE LINK  OFFLINE    Sofía / Artemis (pinned, enrolled)
MODULES             2 READY   1 DEFERRED (GPU gaming protection)
INFERENCE           IDLE      No model loaded by default
OPERATOR STOP       INACTIVE
NEXT ACTION         Check Artemis Platform connection
```

The proposed status is **illustrative only**, not an observation from the user's machines. Always include exact authoritative Core ID and Platform ID in detail screens, a timestamp and freshness, source/provenance of the observation, owner-actionable error and last attempted recovery. Color alone never carries status. No sensitive state, model prompt or secret in logs.

## Legacy startup removal plan

**Target outcome: no two public launch owners.** The following paths are reviewed/retired without immediately deleting useful internal code:

| Current source | Today | Required target |
|---|---|---|
| `src/sofia/__main__.py` | `python -m sofia` launches integrated Core client | Remove installed startup entry point; during transition return explicit `Use aegis ...` error/help, never spawn Core |
| `src/sofia/core/launcher.py` | Direct integrated Core desktop/terminal startup | Replace production use with generic isolated SDK Core worker entry; migrate chat UI to thin Platform client |
| `src/sofia/platform/launcher.py` | `companion-runtime` can jump to Core launcher when CORE_HOST | New `aegis` CLI/TUI/GUI client only; never construct `SofiaApplication` as startup shortcut |
| `src/sofia/platform/run/runtime_service.py` | Legacy Windows Sofía runtime service that imports Core code | Retire installed registration after verified upgrade; preserve or migrate data and eliminate duplicate service ownership |
| `rust/crates/sofia-platform-lifecycle/src/bin/platform_service.rs` | Existing Core-free Platform process owner | **Keep** as system-level owner; add verified independent component reconciliation/supervision, no in-process cognition |
| `src/sofia/platform/run/platform_service.py` | Core-free Platform adapter with management IPC; does not start Cores | **Keep** Core-free; extend narrowly via owned management/reconciliation APIs; no alternate state authority |
| `src/sofia/platform/ops/synthetic_core_lifecycle.py` | Governed synthetic/disposable Core lifecycle | Reuse proven contracts, develop production Core manager and real-host tests without treating synthetic proof as release proof |
| `packaging/installers/*` and `packaging/services/aegis-platform.service` | Signed installer and Debian service foundations; not fully installed-host certified | Install one native Platform service, `aegis` CLI, optional GUI/TUI; migrate old service carefully, no second writer |

**Sequence:** (1) new Platform-first CLI and reconciler; (2) signed standalone Core package/worker and real lifecycle; (3) installer migration and old-service detection with explicit consent; (4) run side-by-side disposable tests with only *one* active state writer; (5) move all released shortcuts/docs/tests to `aegis`; (6) remove compatibility entrypoint and old service code/metadata only when no protected-state migration is bypassed and rollback path is independently validated. The old service must never auto-start simultaneously with the new Platform service.

## Implementation TODOs (new `START-*` IDs, not duplicate 1.0 acceptance rows)

### P0: finish now as part of 1.0 shakedown path

- [ ] **START-01** Freeze `aegis` user entrypoint, native service naming, command/exit-code/status schema, privilege boundary and operator STOP distinction.
- [ ] **START-02** Inventory/remove all production calls from `python -m sofia`, `companion-runtime desktop`, `sofia.core.launcher` and legacy runtime service to direct Core instantiation; retain safe migration pathway.
- [ ] **START-03** Add generic Platform service desired-state reconciliation using the existing canonical registry, identity and SAFE/STOP, no second DB or authority.
- [ ] **START-04** Define and persist per-Core installed/verified/enabled/approved/autostart/desired/observed/generation states; reject ambiguity and exact-identity mismatch.
- [ ] **START-05** Implement real independent Core worker supervision using SDK-only, separately signed Core packages; Platform adapter remains Core-free.
- [ ] **START-06** Wire approved Core autostart to Platform CONTROL_READY; default disabled until owner opts in; don't let absent Cores block Platform.
- [ ] **START-07** Implement authenticated CLI management for service/Core/module/startup status and startup policy; `aegis` CLI never creates local Core writer.
- [ ] **START-08** Move GUI/TUI/tray to Core-free Platform management and selected Core Link; no direct Sofía launch fallback or GUI-dependent service.
- [ ] **START-09** Bind installer/SCM/systemd to the one native Platform service, uninstall/disable old service on approved upgrade without state deletion or duplicate writers.
- [ ] **START-10** Complete safe service shutdown, recovery, process/generation fencing and STOP/revocation during startup; no blind retry of uncertain operation.
- [ ] **START-11** Add exact-SHA Windows/Debian installed-host single-service, no-Core/one-Core and module-disconnected smoke receipts without personal state.
- [ ] **START-12** Fix current CI blockers before claiming the new launch path shakedown-ready. Preserve 1.0 acceptance rows and G8 status.

### P1: complete after baseline is stable, parallel where isolated

- [ ] **START-13** Support multiple distinct installed Core inventories and per-Core autostart with isolation; defer same-host multi-Core GO until proven.
- [ ] **START-14** Use the SDK Validation Core to prove independent bootstrap, process, module access and version negotiation with no private imports.
- [ ] **START-15** Implement dependency-aware module startup ordering/cycle refusal, independent module restart and no-Core operation.
- [ ] **START-16** Implement authenticated Core Link selection and reconnect across owner-enrolled hosts; no discovery-based auto-binding.
- [ ] **START-17** Add resource-aware optional provider, GPU and inference startup; prevent model load during gaming unless allowed by host policy.
- [ ] **START-18** Add per-component bounded restart budgets, health telemetry, event records and startup impact measurements.
- [ ] **START-19** Implement safe old-runtime installer migration, versioned state compatibility, rollback and non-adoption of unrelated OS services.
- [ ] **START-20** Add end-to-end `aegis doctor --startup`, precise GUI/TUI error/status parity, headless service observability and startup docs.
- [ ] **START-21** Review and remove no-longer-needed old launcher/service registration/entrypoint code only once real Core startup and rollback are accepted.
- [ ] **START-22** Add cross-platform developer harness to exercise the complete startup/recovery/shutdown process without real owner state.

### P2: optimize after data, not by assumption

- [ ] **START-23** Measure cold boot, ready-to-control, ready-to-chat, resource footprint, crash recovery, model warm start and game impact on approved hardware.
- [ ] **START-24** Profile and consider selective Rust migration for orchestration/telemetry if it materially reduces overhead without duplicating Platform authority.

## Acceptance checks (new `START-A*` cases)

| ID | Pass condition |
|---|---|
| START-A01 | Signed installed Windows service starts Platform on OS boot with no user login, no Core, model or GUI. |
| START-A02 | Signed installed Debian 12 systemd service starts Core-free headless Platform; cannot import cognition. |
| START-A03 | `aegis` UI/CLI connects to one authoritative running service and cannot spawn a second Platform. |
| START-A04 | With no Core installed, Platform reports READY, zero Cores and accurate module/Fleet status. |
| START-A05 | Merely installing a Core does not activate or autostart it; owner-approved autostart does. |
| START-A06 | Core launched only by Platform under pinned signature, version, UUID, grant, STOP and writer generation. |
| START-A07 | Core startup is a separate OS process and does not import Core into Platform process. |
| START-A08 | Crash/timeout/worker kill reconciles and uses bounded restart; no duplicate writer or stale child adoption. |
| START-A09 | Stopping/restarting/uninstalling one Core leaves Platform, unrelated modules and other eligible Cores running. |
| START-A10 | GUI/TUI/CLI/OS service present the same status and authorized lifecycle decisions; GUI close is not shutdown. |
| START-A11 | Core-free module and Fleet operation survive absent, failed or updating Core. |
| START-A12 | Dependency cycle/missing module blocks dependent component only, never silently enables it. |
| START-A13 | Operator STOP/revocation during startup refuses effects and prevents unauthorized worker activation. |
| START-A14 | Service stop/boot recovery never executes an uncertain operation blindly; exact generation/lease reconciliation. |
| START-A15 | Native service shutdown drains children; reports UNKNOWN/UNCERTAIN when not verified. |
| START-A16 | Pinned remote Core Link reconnects or reports offline, never auto-binds to new host/Core. |
| START-A17 | Artemis (Core Host) and Venus (Core Link/module host) trial works with real approved inference and no protected-state migration. |
| START-A18 | Two distinct test Cores demonstrate independent identity, state, grants and restart (or same-host item stays explicitly blocked). |
| START-A19 | Existing Sofía-first installed startup paths cannot create a production Core or duplicate OS service. |
| START-A20 | Signed installer migration and rollback preserve protected state and never run two competing old/new services. |
| START-A21 | Startup requires neither WAN/cloud login nor auto-download of any model; headless and no-color operation succeed. |
| START-A22 | Exact-SHA Windows/Debian tests, signed installed-host receipts and all unchanged 1.0 release gates prove GO; no self-certified PASS. |

## Release mapping and status

- **1.0 acceptance:** START-01 through START-12 and START-A01–A15/A19–A22 are functional traceability over **existing** Platform 01–38, CORE and LIB acceptance, **not new rows**. Do not retroactively change release acceptance states. Actual source fixes and verified host receipts decide whether launch is accepted.
- **2.1 + SDK Validation Core:** START-13–24 and related multi-Core/profiling enhancements connect to SDKCOMP, PROBE, E21, ISO and LINK families. If a requirement is essential for owner-selected production Core installation, pull only its narrow dependency into the 1.0 shakedown.
- **Not done yet:** This document specifies the target. It does not remove Python entrypoints, create the `aegis` command, update services or install a Core. No source/host tests were executed here.

## OpenCode engineering constraints

Read this design and the current master TODO before editing. Begin with a line-by-line caller map for the four Sofía-first launch paths and native service; keep one integration owner for shared SDK and lifecycle surfaces. Implement in small evidence-backed batches with full relevant tests. Review unchanged security boundaries: exact signer/digest, owner intent, protected paths, STOP, lease/generation, rollback, Core-free boot, no unexpected downloads or public services. Preserve previous releases for audited migration, but never ship the legacy startup path as a second active production service. Compare every acceptance result to the exact tested SHA and record any environmental blocker truthfully.
