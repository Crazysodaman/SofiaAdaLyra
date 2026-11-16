# OpenCode execution order | Aegis Platform-first startup, Phase 2 + parallel backlog

**Date:** 2026-11-16  
**Repository:** `Crazysodaman/SofiaAdaLyra`  
**Verified remote baseline at handoff:** `ac7f178cd8d7e790151e308c192175ac1ecad62e`; recheck HEAD and CI when executing.  
**Scope:** Source development, isolated disposable tests, local integration and evidence; **not** production installation or protected-state migration.

## 0. Missing documents: resolve before task-ID accounting

The last OpenCode batch reported the following files missing at its old baseline. They were generated outside the GitHub repository and are included in the supplied ZIP; **not** being in GitHub does not mean their contents are fictitious:

- `docs/roadmaps/AEGIS_PLATFORM_FIRST_UNIFIED_STARTUP_DESIGN.md`
- `docs/roadmaps/AEGIS_UNIFIED_MASTER_TODO_1_0_2_1_SDK_PROBE_CORE.md`
- `docs/roadmaps/AEGIS_SDK_COMPATIBILITY_UPDATE_SPEC.md`

Also read the included `docs/roadmaps/AEGIS_STARTUP_BATCH1_SOURCE_CHECKPOINT_2026-11-16.md` for this specific integrated source state.

After the owner safely places these documents in the actual checkout, verify exact paths and contents, then reconcile START-01..24, SDKCOMP-01..30, PROBE-01..25 and E21-17 **item by item**, mapping SOURCE_PRESENT, PARTIAL, IMPLEMENTED_UNTESTED, FOCUSED_TESTED, CI_VERIFIED, INSTALLED_VERIFIED, BLOCKED and NOT_STARTED. Preserve the original task text and acceptance. Do not bulk-mark an entire workstream completed. The source at current HEAD prevails over historical baselines or operator prose.

Read `AGENTS.MD`, `docs/development/SOFIA_OPENCODE_EXECUTION_CONTRACT.md`, `docs/sofia2/DEVELOPMENT_WORKFLOW.md`, latest Platform/Core acceptance, current Git status/worktrees, and all uncommitted changes. Existing Git, approval, security and owner policies continue to govern. This is not a command to reset/push/deploy.

## 1. Previous batch: preserve, validate, do not repeat

Owner-supplied report (not independent live-host evidence): three isolated worktrees integrated on local main/pushed `ac7f178c`; focused Platform-first 175 passed/7 skipped, Platform-only 414/15, CLI 31, autostart 42/7. Full unfiltered tests and latest exact-SHA CI were not verified in that report.

Observed in GitHub source at this SHA:

- `src/sofia/platform/cli.py`: `aegis` client surface, but read operations largely consume local durable observations and **mutations refuse**. No supported live authenticated CLI transport yet.
- `src/sofia/platform/run/core_autostart.py`: one-use-approval-fenced desired-state store and injected `CoreStartupReconciler`.
- `src/sofia/platform/run/platform_service.py`: optional reconciler injection and `startup_status`; no production installed real-Core worker adapter wired by default.
- `src/sofia/platform/run/management_read.py`, `src/sofia/sdk/platform_management*.py`: `startup.status` schemas and authorization.
- `src/sofia/sdk/platform_management_client.py`: existing **Linux-only** OS-authenticated `platform.status` read, with signed/installed pin inputs; extend instead of inventing a duplicate transport.
- `src/sofia/platform/run/management_mutation.py`: owner one-use-approved mutation framework currently used for STOP; add specific authorized Core policy operations rather than parallel mutation authority.

Do not remove the legacy launchers or claim real Core autostart works until the full replacement is tested. Do not launch Sofía or touch personal state for development proof.

## 2. Immediate test-first defects to investigate at source HEAD

These are **source-observed failure risks**, not yet CI-reproduced bugs. Reproduce them with focused tests, fix the minimal responsible code, and record verified outcomes:

1. **Autostart persistence across next-day reboot:** `core_autostart.py` presently defaults to `DEFAULT_POLICY_FRESHNESS_SECONDS = 900`, and `_is_fresh()` compares current wall-clock time with `policy.updated_at`. An otherwise-approved durable autostart configured a day earlier may be refused as `STALE_POLICY`. Separate durable operator intent from short-lived authentication proofs; re-check *current* owner authorization/revocation at each start without reusing a consumed one-use grant. Test minutes, days, clock rollback, revoked permission and expired explicit grant.
2. **Cached STARTED may not mean process is alive:** `CoreStartupReconciler.reconcile()` treats matching `last_started_generation` and STARTED outcome as `active += 1` without re-observing the worker. Require fresh OS process PID/generation/installed-artifact observation and explicit uncertain-outcome handling before counting it active. Test crash, PID reuse, zombie, stale lease, platform restart, concurrent manager and restart loop budget.
3. **Disabled Core reported as ZERO_CORE_HEALTHY:** Reconciler returns `ZERO_CORE_HEALTHY` when *no enabled policies* even if disabled policy rows exist; `PlatformServiceSession.startup_status()` counts all policy rows as `core_count`, while both `management_read.py` and `platform_management_response.py` reject `ZERO_CORE_HEALTHY` with nonzero `core_count`. Distinguish zero installed Cores from installed-but-disabled; derive Core count from signed installed registry, not solely policy count, and add schema-compatible status states if needed. Test zero, one disabled, one installed no policy, one enabled and failures.
4. **Autostart trust boundary:** The reconciler's `is_authorized` default allows True; a generated `approval_ref` string is not a signed grant. Production must provide verified, service-owned signed package, installed identity, current SAFE/STOP and generation checks; impossible states deny. Test forged Core records, unapproved activation, expired owner grants, operator STOP and no automatic owner-secret access.
5. **Run-stopping latency and shared lock:** Inspect whether synchronous startup under the Platform session constructor can exceed native OS READY deadline, delay service health, block management reads, or hold leases; convert only to a reviewed, bounded, cancellable reconciliation after CONTROL_READY, with independent health reporting. Do not loosen release timeouts merely to hide a hang.

## 3. Parallel execution topology (one integration owner, nonoverlapping worktrees)

Start these workers concurrently **only** when distinct working directories and concrete nonoverlapping file ownership are available. Otherwise run coherent batches sequentially. The integration owner alone reconciles shared files, source drift and HEAD. Record each worker's base SHA, branch/worktree path, exact changed paths and focused test command.

### P0-A: Native Platform + real supervised Core autostart

Own `src/sofia/platform/run/core_autostart.py`, a reviewed **new** native-service Core process adapter, and Core lifecycle integration tests. Coordinate edits to `src/sofia/platform/run/platform_service.py` and Rust `platform_service.rs` through the integration owner. Implement **START-03/04/05/06/10/18/22**: service recovers desired state; uses *verified installed* signed Core runtime manifest, exact Core UUID and lineage; explicit approved autostart; observes PID/generation and health; starts/stops only that Core, never Platform; remains healthy with none; safe STOP/revocation, bounded backoff and uncertainty. First use disposable synthetic signed Core real subprocess; then a separately packaged SDK Validation Core, **not** synthetic = real. Distinguish tested process from installed OS service evidence.

### P0-B: SDK protocol and consumer impact owner

Own `src/sofia/sdk/**`, `rust/crates/sofia-contracts/**`, SDK golden/parity tests. Implement **SDKCOMP-01..06, 07..14, 20..22, 29** where ready. Start with API/consumer inventory and contract freeze, then additive portable Core/Module SDK, truthful outcome taxonomy, supported protocol negotiation and negative tests. Maintain existing Python/Rust wire protocol 1.0 unless an actual breaking change warrants reviewed bump. No private Platform imports allowed in SDK-only probe Core. **Send frozen API contract to workers before they integrate.** No blind search/replace across 55 module identities.

### P0-C: Authenticated Platform management operation + cross-OS transport

Own `src/sofia/platform/run/management_*.py`, native management listener tests, new reviewed **mutation** adapters. Work with SDK owner to update request/response schemas. Implement **START-07**, and necessary parts of **SDKCOMP-12/17**. Add read operations for current installed Core inventory/startup and exact one-use-approved `core.autostart.enable/disable` mutation via the existing service-owned dispatcher/SAFE/STOP, not a new permission database. Extend existing Linux `platform_management_client.py` after SDK owner review; provide Windows named pipe equivalent with authenticated current OS peer SID and pinned installed service identity/generation. Do **not** claim that an arbitrary env path or JSON role is proof of enrollment. Verify denial, replay, revocation, signed generation change, permission matching, no effects on failure.

### P1-D: CLI, TUI, GUI client integration

Own `src/sofia/platform/cli.py`, UI client adapters and focused tests. Implement **START-01/07/08/20** as dependencies mature. Replace direct raw SQLite status inference with live authenticated Platform observations; fail closed when absent, distinguishing `NOT_OBSERVED`, denied, no installed Core, disabled, stopped, starting, running and failed. Support `aegis doctor --startup` and CLI help/JSON/exits. `aegis core autostart <id> on|off` must use owner-approved management mutation, not raw table update. `aegis chat --core <id>` requires selected authenticated Core Link, and must never spawn `sofia.core.launcher`. Ensure GUI/TUI connect to the same service; no new fake health or management daemon.

### P1-E: Independently built second Core via SDK

Own `examples/sdk_validation_core/**`, disposable Core package/test harness, test assets and tests. Implement **PROBE-01..12/18..21**, **START-14**, after P0-B SDK seam is frozen. New UUID and benign identity/definition; no Sofía private assets or imports, independent state; deterministic conversation then optional real local inference only when separately authorized. Prove verified signed test install, process start/restart/crash, durable separate history, Core Link, reference module grant/revoke, no Platform source forks. Log *every private API needed* as an SDK gap and hand it to SDK owner; do not bypass. Two distinct Cores should first be tested with separate disposable Platforms if same-host multi-Core separation is not yet accepted.

### P1-F: Installer, native launch and legacy retirement preparation

Own `packaging/installers/**`, `packaging/services/**`, packaging/installer-specific tests; coordinate shared `pyproject.toml`, `packaging/components.toml` and service Rust file with integration owner. Implement **START-02/09/11/19/21/22** incrementally. Produce exact signed disposable Windows/Debian release and install/restart/uninstall/rollback test harness (not real owner host). Make `aegis` entrypoint canonical. Detect old Sofía service/shortcut and provide **reviewable** migration with backup and rollback; *do not remove legacy runtime until replacement parity is proven*. Verify no parallel writer or service adoption. Windows SCM or systemd effectful installs require separately approved disposable hosts; blocked host tests remain blocked.

### P0-G: CI regression repair and shakedown evidence

Own currently failing test/fixture groups and only isolated production code paths, with shared edits coordinated. Implement **START-12**, existing Platform 01..38, Core, LIB, SDK acceptance as evidence allows. Fetch exact SHA GitHub CI and reproduce fresh failures; previous SHA had Library peer-grant tests, UI bootstrap, Debian ACL/component lifecycle/Unix management timeout and Rust Clippy. Treat those as investigation hints only until reproduced on current main. Fix tests/fixtures or code without disabling assertions, lowering SAFE, changing grants or manufacturing acceptance receipts. Run focused, cross-domain, Rust fmt/strict Clippy and package checks; defer expensive full CI to a coherent merged checkpoint, never bypass actual required final gates.

### P2-H: Source audit and independent 2.1 optimizations

Own `E21-17` source audit ledger and distinct low-risk tests/implementation files. Enumerate all tracked source files with line coverage, source-call boundaries and source SHA. Reconcile original TODOs. While other workers code, implement source-safe `E21-00/01/12/13/15/16/18` slices, then benchmark-supported Rust or module improvements **E21-14** without creating second process/state authority. Gaming-first policy on Venus and Core-free Platform remain mandatory. Label real-hardware measurements `BLOCKED_HOST` until authorized.

## 4. Integration waves and acceptance

- **Wave 0:** Stage the missing docs, inspect/record exact HEAD and worktree status, validate owner report vs source, reproduce the five risks above, establish source ownership map. Start code fixes; no audit-only finish.
- **Wave 1:** One Platform-only process (no Core) healthy, one *disposable* signed synthetic Core actually supervised through the canonical service path, current authenticated CLI startup read. Confirm legacy launcher isn't invoked. Integration owner merges; exact PATHS/SHAs/tests recorded.
- **Wave 2:** Approved autostart enable/disable over authenticated OS socket/pipe; persistent desired state survives overnight; stale/revoked proofs deny; Core crash/restart reconciles truthfully; SDK public facade and independent test Core can run by real OS worker with separate state. Confirm zero/disabled/one/many projection semantics.
- **Wave 3:** GUI/TUI parity, signed installer rollback/legacy coexistence safety, module dependency admission, Fleet/2.1 low-risk improvements. Cross-platform disposable tests before any real installation.
- **Wave 4:** Full merged exact-SHA CI and package/RC testing, verify no suppressed test failures, preserve existing 1.0 GO and G8 UNACCEPTED states without installed proof. Cleanly stage proposed legacy retirement only after equivalence/rollback proof.

**Do not stop after Wave 0 or one patch if additional authorized executable work remains.** Continue through available nonconflicting workstreams; if one is blocked, advance another. However do not claim all 239 planned improvements are safely parallelizable; dependency/ownership boundaries override velocity.

## 5. Reporting and publication

For every significant batch publish: current HEAD and worktree state; task IDs; verified files/code/test evidence; exact local/CI pass/fail/skip counts; installed-host/unverified boundary; integration SHA(s); open production gaps and pending approvals; next executable batch. Maintain a central task ledger (planned vs coded vs tested vs CI vs signed installed vs live verified) and a source-audit coverage manifest. No invented success or background execution. Keep GitHub `main` the agreed integration target, use owner-approved commits/pushes without force, and avoid overlapping writes. If a push races an external update, stop and reconcile; never discard owner changes.

**Start now with P0-A/C on the actual native Core startup path while P0-B freezes SDK contracts and P0-G fixes current CI.**
