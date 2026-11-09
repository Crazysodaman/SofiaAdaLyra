# Aegis Platform 1.0 acceptance

Platform-only shakedown and full-project shakedown are separate verdicts.
Both are **NO**. G8 (#129) remains deferred. Authority: #120; original
700-task coding register #132 remains unchanged. No production activation.

## Binding owner-only release criterion (2026-11-09)

**Owner decision: Platform 1.0 is an owner-operated private homelab release, not a public SaaS or commercial model marketplace.** The [Platform/Core owner-only acceptance crosswalk](AEGIS_OWNER_ONLY_1_0_GO_LIVE_ACCEPTANCE_2026-11-09.md) is **required for GO** and maps private-by-default offline install, single owner / multiple enrolled nodes, approved personal LAN Hub, no account/billing/cloud prerequisite, precise license handling and unchanged security to existing **38** rows. This adds **no 39th row, no LIB-17 and no PASS**. Personal/noncommercial models are permitted as *candidate data artifacts* if exact legal terms allow the contemplated use; do not demand commercial redistribution rights for local use, and do not bypass origin/trust/transfer verification. Platform still boots with **zero Core/model/Voice**, and protected owner state remains separate. Verify on disposable installed Windows/Debian hosts before releasing.

## Reconciled source inventory

Initial inspected baseline: `81371ac8ca45f00657f3eed02a05d8b11a0be3fb`.
Integrated service checkpoint: `70eb4ffbdde6905a0b76f7d2d82d8d881b9e054b` (PR202).
No open PRs at campaign startup. Existing worktrees were preserved.

| Area | Existing production source | Observed implementation / remaining dependency |
| --- | --- | --- |
| Identity | `platform/state/installation_identity.py`, `sdk/identity.py` | Persistent UUID/key and AEG-P serial; explicit bootstrap, corruption refusal. Reuse PR192. Core-free service binds the existing UUID/fingerprint; reviewed recovery remains. |
| Owner security | `platform/safe/`, `sdk/principals.py` | Existing signed exact approval, STOP, replay/audit contracts; reuse PR193. Service IPC must call these owners. |
| Fleet | `platform/ops/callsigns.py`, `platform/distributed/` | Atomic designated local registry and durable admission/revocation. Remote naming transport is missing; no global offline success. |
| Signed Core boundary | `platform/ops/core_definition.py`, `sdk/core_definition.py` | Existing signed verifier and runtime/asset digests (PR195). Governed durable stage/activate/remove interface remains. |
| Generic workers | `platform/core_worker/`, `platform/cognition_provider.py` | Core-free worker/provider implementations (PR196/197); optional inference is separate from baseline. No real personal writer authority is granted. |
| Rust Core Link | `rust/crates/sofia-core-link/` | Current-selection-fenced status adapter (PR199); lifecycle-changing operations need separate owner authority. |
| Broker | `rust/crates/sofia-ui-broker/` | Durable Windows/Unix journal (PR198), policy foundation. Running authenticated IPC, session/DND observers and native tray remain. |
| Rust service | `rust/crates/sofia-platform-lifecycle/` | Rust process owner, native SCM dispatcher and systemd notify/drain template integrated in PR202. Signed OS installation, boot/reboot, authenticated external management and crash-policy composition remain. |
| Legacy services | `platform/run/runtime_service.py`, `platform/run/release_process.py` | Python runtime service imports personal Core settings and launches legacy runtime. Cannot certify as Core-free Rust service. |
| Modules | `platform/modules/`, `platform/application/module_lifecycle.py` | Existing generic manifests and local-state lifecycle; complete signed isolated installed-host lifecycle still requires verification. |
| Update/recovery | `platform/ops/platform_install.py`, `platform/run/active_release.py`, `platform/state/` | Existing staging/recovery/verified restore components; Platform-only service composition and installed OS upgrade/reinstall acceptance remain. |
| Packaging | `packaging/components.toml`, `platform/verify/component_artifacts.py` | Separate SDK/Platform/Core wheels. Rust binaries and OS service installers are not yet a complete Platform release. |

Paths above are under `src/sofia/` unless prefixed `rust/` or `packaging/`.
A wheel import, unit test, or compiled crate is not installed-host service evidence.

## Platform-only release matrix

States: PASS, FAIL, BLOCKED, NOT TESTED. FAIL denotes a known missing mandatory
production path; NOT TESTED means no complete disposable installed-host acceptance
receipt, even where narrower unit/installed-wheel evidence exists.
Every row needs exact source SHA, test IDs, CI run, artifact digests and actual
Windows/Debian host observations before PASS. The baseline matrix is amended below by exact-SHA service receipts. No row
claims complete signed-release installed-host acceptance.

| ID | Requirement | State | Windows | Debian 12 | Missing release evidence / next dependency |
| --- | --- | --- | --- | --- | --- |
| 01 | Fresh Platform-only install | NOT TESTED | NOT TESTED | NOT TESTED | **GO blocker AG-D011:** signed one-script Windows PowerShell / Debian 12 Bash installer, themed interactive TUI (when terminal supports it), plain ASCII/monochrome fallback, no preinstalled Python/Cargo/Core, real SCM/systemd install and signed installed-host receipts; wheels alone do not count |
| 02 | No Core installed | NOT TESTED | NOT TESTED | NOT TESTED | Minimal installed wheels covered by `test_platform_optional_dependencies`; final OS release receipt pending |
| 03 | No canonical Core DB | NOT TESTED | NOT TESTED | NOT TESTED | Same minimal test; service-wide file access acceptance pending |
| 04 | Permanent UUID | NOT TESTED | NOT TESTED | NOT TESTED | Existing identity tests; reinstall/reboot OS receipt pending |
| 05 | Core-free health/startup | NOT TESTED | NOT TESTED | NOT TESTED | Actual installed-wheel Rust process passes; signed OS release receipt pending |
| 06 | Windows service start/stop | NOT TESTED | NOT TESTED | NOT TESTED | Actual disposable native SCM start/stop/restart passes; final signed installer receipt pending |
| 07 | Debian service start/stop | NOT TESTED | NOT TESTED | NOT TESTED | Actual two-boot disposable Debian12 systemd start/stop passes (PR205/206); final signed OS release receipt pending |
| 08 | Abrupt exit recovery | FAIL | NOT TESTED | NOT TESTED | Disposable Debian12 systemd crash/restart and generations pass (PR205/206); complete signed-release recovery policy remains |
| 09 | No duplicate supervisor | NOT TESTED | NOT TESTED | NOT TESTED | Actual installed process rejects duplicates; final OS release receipt pending |
| 10 | Authenticated CLI/IPC | FAIL | NOT TESTED | NOT TESTED | Canonical SAFE-backed management boundary |
| 11 | SAFE/STOP | NOT TESTED | NOT TESTED | NOT TESTED | Existing SAFE tests; running service integration |
| 12 | Owner revocation | NOT TESTED | NOT TESTED | NOT TESTED | Existing verified grants; service integration |
| 13 | Fleet enrollment | NOT TESTED | NOT TESTED | NOT TESTED | Existing disposable mTLS/admission tests; release host receipts |
| 14 | Fleet revocation | NOT TESTED | NOT TESTED | NOT TESTED | Admission/removal/stale-trust regressions; host receipts |
| 15 | Remote naming authority | FAIL | NOT TESTED | NOT TESTED | Authenticated remote registry adapter |
| 16 | Offline names | NOT TESTED | NOT TESTED | NOT TESTED | Existing cached/unconfirmed client tests; remote reconnect |
| 17 | Generic signed module install | NOT TESTED | NOT TESTED | NOT TESTED | Installed signed artifact lifecycle |
| 18 | Module rollback/lifecycle | NOT TESTED | NOT TESTED | NOT TESTED | Isolation, limits and crash/revocation acceptance |
| 19 | Signed update/recovery | NOT TESTED | NOT TESTED | NOT TESTED | Installer update/repair/rollback with verified signatures, bounded interruption/restart and OS service recovery receipts |
| 20 | Identity through reinstall | NOT TESTED | NOT TESTED | NOT TESTED | Installer uninstall/reinstall OS receipts; preserve protected identity/state by default, no personal Core purge or duplicate service/writer |
| 21 | Invalid Core rejection | NOT TESTED | NOT TESTED | NOT TESTED | Existing signature/path tests; installed package service boundary |
| 22 | Signed synthetic Core install | FAIL | NOT TESTED | NOT TESTED | Governed stage/activation interface |
| 23 | Synthetic start/stop/detach | FAIL | NOT TESTED | NOT TESTED | Governed process lifecycle |
| 24 | Removal leaves Platform healthy | FAIL | NOT TESTED | NOT TESTED | Core-free service runs; governed installed-Core removal still missing |
| 25 | Cross-platform compatibility | NOT TESTED | NOT TESTED | NOT TESTED | Existing contract CI; complete release candidate |
| 26 | Recovery without second writer | NOT TESTED | NOT TESTED | NOT TESTED | Existing writer fencing; new service composition |
| 27 | Native Rust regressions | NOT TESTED | NOT TESTED | NOT TESTED | Native Rust and disposable SCM/systemd regressions pass; final signed-release integration receipt pending |
| 28 | Installed-wheel isolation | NOT TESTED | NOT TESTED | NOT TESTED | Component CI + minimal dependency test; final exact release receipt pending |
| 29 | Exact-SHA release CI | NOT TESTED | NOT TESTED | NOT TESTED | Distinct Platform-only gate plus signed release artifacts |
| 30 | Complete operator runbook | FAIL | NOT TESTED | NOT TESTED | Document AG-D011 one-script setup, themed TUI / ASCII fallback, headless noninteractive invocation, verified service, update/repair/rollback/uninstall and diagnostics |
| 31 | Versioned authenticated management API | NOT TESTED | NOT TESTED | NOT TESTED | B3 CLI/IPC boundary consumed by CLI, TUI and GUI without duplicate stores |
| 32 | Terminal Control Center (Windows) | NOT TESTED | NOT TESTED | NOT TESTED | AG-D022 TUI over the management API with live status, reconnect and stale-state handling |
| 33 | Terminal Control Center (Debian 12) | NOT TESTED | NOT TESTED | NOT TESTED | AG-D022 TUI on headless Debian 12; headless Platform keeps running with no GUI dependency |
| 34 | GUI Control Center shell (Windows) | NOT TESTED | NOT TESTED | NOT TESTED | AG-D007 CC-1 read-only shell with service-owned authorization rechecks |
| 35 | Core Manager surfaces (parity) | NOT TESTED | NOT TESTED | NOT TESTED | AG-D004 via the versioned API on GUI and TUI; no display-name-only authorization |
| 36 | Module Manager surfaces (policy) | NOT TESTED | NOT TESTED | NOT TESTED | AG-D006 live status, uninstall/reinstall policy and Core-originated removal proposals |
| 37 | Security/Approvals, Updates/Recovery and Diagnostics surfaces | NOT TESTED | NOT TESTED | NOT TESTED | Protected operations gated service-side; approval surface may not mint authority |
| 38 | Shared GUI/TUI theme and independent installability | NOT TESTED | NOT TESTED | NOT TESTED | Same approved AEGIS_SHARED_GUI_TUI_THEME tokens in GUI, terminal Control Center and AG-D011 installer TUI; truecolor/limited-color/NO_COLOR plain-ASCII fallback; separately installable GUIs; headless service independent |

## AG-D028 owner-required Artifact Library and selective distribution (2026-11-08)

**Decision:** In addition to the signed Platform-only installer AG-D011, the owner expressly requires the [AG-D028 Artifact Library](../roadmaps/AG_D028_AEGIS_FEDERATED_ARTIFACT_LIBRARY.md) **before Platform 1.0 GO**. The [binding AG-D028 release specification](../roadmaps/AG_D028_PLATFORM_1_0_RELEASE_SPEC.md) defines catalog/store data ownership, SDK/management contracts, current trust/SAFE, owner-hosted LAN Hub, peer transfer, dependency-aware selective installs, large artifact chunking and disk quotas/GC. The [independent LIB-01 through LIB-16 QA runbook](../roadmaps/AG_D028_ARTIFACT_LIBRARY_QA_RUNBOOK.md) specifies exact disposable installed-host setups, negative cases and evidence fields. Engineering tracker: [#250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250). This is a new requirement inside existing 38 rows, **not a 39th row**.

**Owner's primary deployment profile:** [single Hub on Sofía VM, one logical Library, zero replicas initially; future read-only replicas and controlled manual promotion](../roadmaps/AG_D028_SOFIA_VM_PRIMARY_LIBRARY_DEPLOYMENT.md). Hub remains Platform-owned even when Sofía Core shares the VM. Existing LIB-01–16 shall include Core/Hub coexistence, zero-replica operation, separate storage, and disposable replica safety/dual-primary negative tests, with **no new row or scenario number**.

**Release-blocking minimum:** (1) air-gapped signed Core-free OS installation with only Platform+neutral SDK/runtime; (2) separate download/stage/installation of one or multiple selected synthetic Cores and optional modules, previewing dependencies and without auto-activation; (3) an owner-configured signed Hub library that can serve verified bytes over an authenticated LAN without WAN; (4) direct enrolled peer-to-peer transfer with independent recipient signature/hash/license verification and explicit target install authorization; (5) resumable bounded transfers with revoked-peer/STOP/crash/quota/rollback/GC safety and model-size chunked synthetic data handling; (6) truthful GUI/TUI/CLI parity and operator-runbook evidence. No private Core data, memory, owner secret, `sofia.db`, module credentials or public-network listener shared by default.

**Test-to-row mapping:** All scenarios are **PENDING**, with no row states changed by this specification.

| AG-D028 test IDs | Core acceptance classes | Original #201 rows refined |
| --- | --- | --- |
| LIB-01/02 | Offline Windows/Debian signed Platform-only bootstrap and OS-service/absence proof | 01,02,03,05,07,28,30,33,38 |
| LIB-03/07/08 | Authenticated owner Hub, enrolled peer download, revocation, wrong-host/unknown-peer refusal, no Internet | 10–14,17–19,29,31,36,37 |
| LIB-04/05/06 | Selective synthetic Core(s), single/multi optional modules, dependency graph, no auto-install/activation | 02,03,17,18,21–26,28,35,36 |
| LIB-09/10/11/12/13 | Signature/path/license attacks, interruption, resume, large-data bounds, quota/GC, STOP, rollback and protected identity | 08–12,17–21,25,26,28,29,37 |
| LIB-14/15/16 | Windows GUI, Windows+Debian TUI/CLI, offline normal operation, installation/runbook/receipt parity | 01,05,08,16,19,20,29–38 |

**Evidence rule:** Team E must receive separately verifiable exact-HEAD CI, signed artifact and trusted test-signer provenance, release/SDK versions, disposable Windows/Debian 12 installed-host identity, service health, full positive/negative transfer logs, source/sink digest, ownership/STOP denial receipts and no-Core/no-private-state evidence. Each of LIB-01–16 plus every unrelated existing row must pass. Unit tests, a README or mock Hub cannot mark any row PASS. Current Platform-only GO remains **NO**, and this extension does not authorize live downloads/enrollment or personal Core start.

**Owner/implementation coordination:** Team A owns authenticated management and Fleet trust/SAFE; B owns the sole signed installer/cache/acquisition execution; D owns SDK/core/module dependency manifests and adapter lifecycle; C owns management GUI/TUI; E independently tests the full multi-host matrix. Integrate in isolated draft branches with formal versioned contract freeze and reviewed merges; do not overwrite the 38-row source ledger or weaken negative checks.

## AG-D011 interactive installer promoted to Platform 1.0 GO-LIVE blocker (2026-11-08)

**Explicit owner decision:** The cross-platform, one-script installer and its
shared-theme interactive terminal experience are required for the **Platform 1.0
GO** decision. This refines the already-required signed OS installer; it does
not add or renumber acceptance rows. Evaluate against existing rows **01, 19,
20, 30 and 38**, plus **06–08 and 10** for service registration, recovery and
authorized management. Design-only documentation, staged files and wheel tests
cannot satisfy these release gates.

**Minimum ship contract:**

- Reviewed signed release bundle, independently verified root of trust, and
  one auditable launch script per OS: `Install-Aegis.ps1` for supported Windows
  and `install-aegis.sh` for Debian 12. No Git clone, Python, Cargo, GPU,
  Sofía Core or model required to install a **Core-free** Platform.
- Keyboard-only interactive setup/maintenance **TUI** where a usable terminal
  exists, with the **same canonical Aegis palette** as GUI and TUI:
  `#9400D3` purple, `#00C2FF` cyan, `#39FF14` lime, `#000000` background.
  Reuse `contracts/ui/aegis-theme-v1.json`, not an installer-specific palette.
  Provide safe truecolor/256/16-color handling, `NO_COLOR`, narrow/SSH
  **plain ASCII numbered-menu fallback**, and no ANSI in redirected/log/JSON
  output. Color never conveys trust or authorization by itself.
- Same installer backend and security rules for TUI and scripted/headless CLI.
  Preflight, exact signed artifact/OS/architecture validation, install preview,
  approved service changes, status/diagnostics, update, repair, rollback and
  uninstall. A noninteractive mode must require explicit safe inputs and must
  never bypass SAFE/STOP, owner approval, revocation or anti-replay.
- Install a real **Rust-owned native OS service** with verified installed
  runtime/SDK dependencies, durable identity and receipts. Install/reinstall
  must not adopt unrelated services, create a second writer, silently install a
  Core/Fleet peer or purge protected state. Uninstall preserves state by default;
  destructive purge requires separate authorization.
- **GO evidence:** exact-SHA signed Windows and Debian 12 disposable-host
  install/update/repair/uninstall/reinstall and reboot/crash/rollback tests;
  interactive TUI, ASCII/monochrome and headless mode checks; accessibility,
  secret redaction, keyboard cancellation and failure-path receipts. All mapped
  rows remain NOT TESTED/FAIL until their actual signed installed-host evidence
  is accepted.

**Implementation status:** REQUIRED, **NOT YET VERIFIED OR SHIPPED**. AG-D011
is the canonical installer UX design. Do not infer the scripts currently
exist or that the active B1 staging branch already activates the signed Rust
service. No production deployment, real Core activation or G8 authorization.

## UI scope added by owner directive (2026-11-08)

Rows 31-38 extend the shakedown per the explicit owner directive to include
the native GUI, TUI and their essential management functionality. Rows 01-30
keep their historical evidence discipline; no row above was renumbered,
deleted or quietly completed. Rows 31-38 begin in NOT TESTED and require the
same receipt discipline: exact source SHA, test IDs, CI run, artifact digests
and actual Windows/Debian host observations before PASS. Row 31 (the
authenticated management API) is the prerequisite for every UI row, so the
previously documented failure of row 10 stays a blocker until resolved.
Advanced personal SofA-a Workbench, the full Model Manager and autonomous
Core self-management remain outside the minimum Platform-only release
requirements. Batch definitions and exact implementation evidence live in
[AEGIS UI shakedown batches](AEGIS_UI_SHAKEDOWN_BATCHES_2026-11-08.md).

## Audit reconciliation

A: uncaught signed-definition CLI rejection did not reproduce at baseline:
`CoreDefinitionRejected` inherits `PermissionError` / `OSError`, already caught.
Eight denial variants and an actual subprocess now verify structured REJECTED,
exit 2, no traceback and no database creation.

B: reproduced prohibited returned proposals despite disabled worker/request tools.
Reject proposals before releasing the inference response; proposal data is never
execution authorization.

C: signed-definition verifier already checks root/ancestors. A separate installed
worker digest erased ancestor redirects through resolve(); explicit and implicit
roots and nested redirects now have fail-before-read regressions.

D: baseline metadata already omits Ollama and transport imports are lazy. Add an
explicit optional extra and prove a real pip installation using only SDK/Platform
and mandatory dependencies, without preinstalled Ollama or Core.

E: retain Fleet stale trust, verified durable admission and removal/revocation
regressions. No retired credentials are reintroduced.

The five live Ollama failures stay visible in full-project suite evidence.
They are not a Platform-only dependency. Neither verdict is promoted by separating
CI scopes. Next release work: signed Platform-only artifacts, authenticated
management, and installed OS upgrade/recovery acceptance.

## Integrated service receipts (PR202)

Merge source: `70eb4ffbdde6905a0b76f7d2d82d8d881b9e054b`.
Tested head: `86016572c56a2f5af70a834beb2c902253a4f299`; the merge adds
concurrent documentation only. Production paths include
`rust/crates/sofia-platform-lifecycle/src/bin/platform_service.rs`, native
`service_windows.rs`, `platform/run/platform_service.py`, and the systemd
unit template under `packaging/services/`. Post-merge smoke: 21 passed.

- [Native service CI](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42314070122):
  Windows 22 Python passed / 1 Unix-only skip; Linux 22 passed / 1 SCM-only skip.
  `test_rust_platform_scm` registers a disposable real Windows service and verifies
  start, stop, restart and stop. `test_rust_platform_service` installs SDK and
  Platform only, verifies no Core/Ollama, graceful exit, exact PID/identity,
  duplicate denial, abrupt-parent EOF recovery and durable generation advance.
- [Platform-only gate](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42314069993):
  Windows 289 passed / 7 OS-specific skips; Debian12 286 passed / 10 skips.
  Native Rust workspace: 55 Windows / 49 Linux passed; strict fmt/Clippy passed.
  All 12 exact-head PR workflows passed.
- Full unfiltered suite: 8,867 passed, 24 skipped, 23 subtests passed;
  only the five known live Ollama connection failures remain. Nothing disabled.
- `test_core_worker_socket_paths` reproduces and fixes long Unix runtime paths;
  private ephemeral IPC moves while durable lifetime/generation paths stay fixed.
- Separate Debian12 container evidence at `b4b19b26` rebuilt the unchanged Rust
  source on glibc2.36 and exercised the SDK/Platform-only service as UID10001.
  This is native container/process evidence, not booted systemd or signed-installer
  certification. Newer-host GLIBC_2.39 output was reproduced failing on Debian12.

The read-only Platform-only release manifest/verifier is documented in
[Platform release verification](PLATFORM_RELEASE_VERIFICATION.md). It does not
install or activate code or establish a durable downgrade-prevention checkpoint.
Signed OS release production, dependency/runtime construction, external SAFE-backed
management, remote Fleet naming, isolated modules, synthetic Core lifecycle and
recovery acceptance still block Platform-only readiness.

## Reconciled narrow evidence through PR208

Current integrated code: `cc0a1912538c8f21444556d608b9e80927ee4432`.
Subsequent audit/documentation commits through `6285b1672a41b1e0daadf4ac31a68e30a743f04c`
add no production source. No whole release-matrix row is promoted to PASS.

| Batch | Exact tested source / CI | Narrow observed evidence | Remaining release boundary |
| --- | --- | --- | --- |
| PR205/206 | `9c8a31cde185a8a424f19bf41cbf997d515a1534`; [offline VM](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42340702204) | Two actual offline Debian12 kernel/systemd boots, bundled CPython3.12.16, same UUID/key, generations 1–6, four clean stops, two crash recoveries and duplicate denials | Disposable assembly, no production signed OS installer or full Windows reboot/upgrade acceptance |
| PR207 | `d0c1396634f13f1e2ce68a86cadc33e893a68ce9`; [native gate](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42342014180) | Cache corruption/redirection fail closed; Windows359/8, Debian357/10; full8,948/25 with23 subtests and five known Ollama failures | Cache metadata grants no installation authority; unsafe legacy permissions need reviewed transition |
| PR208 | `30cf9e203c04b284995fc75e01df9f592da19ec4`; [native gate](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42343177305) | Signed code/runtime candidate staging; Windows368/9, Debian367/10; full8,958/25 with23 subtests and five known Ollama failures | Non-activating; no service registration, environment installation, owner grant or durable release selection |

The [revision-pinned audit](AEGIS_CODEX_AUDIT_2026-11-07.md) separately records
actual Package Tests and Windows/Debian full-release RC failures at `4d854a1a`.
Those were not among the targeted PR workflows above. Do not describe full
release CI as green from targeted PR gates. The installed-manifest lookup
failure has been reproduced in a fresh SDK/Platform venv; the writer-lock fixture
failure has been reproduced with a controlled delayed genuine RUN receipt.
Fixes and fresh exact-head Package/RC results are pending integration. The
production freshness/permission checks and independent wheel METADATA test are
retained. No test is removed or disabled to resolve either failure.

Signed-staged artifact VM integration is separately in draft PR209; do not
infer its success from PR208's inert byte-staging fixtures or earlier VM jobs.
Authenticated management, final installers and recovery, remote Fleet, isolated
modules, governed synthetic Core lifecycle and operator runbook remain open.
