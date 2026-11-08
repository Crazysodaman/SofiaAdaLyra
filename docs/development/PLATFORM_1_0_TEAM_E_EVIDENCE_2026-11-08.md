# Team E independent release QA, exact evidence and all 38 acceptance rows

**Snapshot:** 2026-11-08 UTC. **Repository:** [Crazysodaman/SofiaAdaLyra](https://github.com/Crazysodaman/SofiaAdaLyra). **Authority:** [issue #201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201) and [canonical matrix](PLATFORM_1_0_ACCEPTANCE.md). **Starting main SHA:** `dd7020ce48c06e82684d3439779266de9ea965b4`.

**Verdict: NO-GO, 0/38 whole rows PASS.** FAIL: 08, 10, 15, 22, 23, 24, 30. Remaining 31: NOT TESTED for complete signed installed-host release. This independent QA snapshot may not be copied forward to later main SHAs without fresh validation. Neither Core activation nor production host migration or G8 is authorized.

## Exact-SHA CI inspection and failure reproduction

| Source | Observed result | Critical limitation |
| --- | --- | --- |
| [PR #210](https://github.com/Crazysodaman/SofiaAdaLyra/pull/210), `9549268d44e7766b2078d185f21b40ec9b45667c` | **11/11 associated workflows success**. [Package Tests 42362591777](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42362591777): 22/22 jobs success. [Windows RC 42362591763](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42362591763) and [Debian RC 42362591755](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42362591755): build jobs success. Windows full RC log: 8,927 passed, 57 skipped, 6 deselected, 23 subtests. Debian: 8,958 passed, 26 skipped, 6 deselected, 23 subtests. | Both *keyless release provenance* jobs were SKIPPED for pull_request. PR fix not yet integrated to main. Not a signed OS installer nor booted installed-host receipt. Five known full-project live Ollama connection failures remain separately visible. |
| [PR #233](https://github.com/Crazysodaman/SofiaAdaLyra/pull/233), `1eb89e118b3f905c796fde3a6c36bdb0a0bf5b6b` | [Debian12 VM run 42480233409](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42480233409) **FAIL on first boot**. Actual job log: three `worker_startup_deadline` class labels, `ExecMainStatus=2`, `NRestarts=2`, `SubState=auto-restart`; no ready phase. Six other associated workflows success. | Failure remains a blocker. Neither 45s guest deadline nor denial checks may be weakened. [PR #224](https://github.com/Crazysodaman/SofiaAdaLyra/pull/224) proposes 12s cold-start handshake versus 5s steady-state, **not yet proven** by this evidence. |
| Main `dd7020ce48c06e82684d3439779266de9ea965b4` | [Platform gate 42480737336](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42480737336) SUCCESS and [Debian RC 42480737306](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42480737306) SUCCESS at sampling. [Windows RC 42480737256](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42480737256) IN PROGRESS and [Package Tests 42480737315](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42480737315) QUEUED. | Main is **not** declared fully green while runs pending. No inferred merge of #210. |

Artifacts below are **GitHub-provided ZIP digests only, not independently downloaded, rehashed or signer-validated release bytes**:

- PR210 Windows integrated RC artifact **13571879159**, `sha256:2ea5294c6afcc833b1d93356e4e4bfffacc7cc4ef52042e20a13aabd59c6e610`.
- PR210 Debian integrated RC artifact **13571146676**, `sha256:4b13b9774f678469a56755afdbe08eacd253915f94fc893c96216aa2e7f9cd00`.
- PR233 failed Debian VM diagnostic artifact **13617647279**, `sha256:038c73c7a787b6a6b1971141d5c8d03232f9d14b9885daa369fd8334ac719b6f`. This is a **failure receipt**, not a PASS.
- No accepted production signing identity, final signed one-script installer, trusted OS release attestation, or complete host-install provenance was observed.

### One independent narrow QA fix

The Debian VM workflow checks out `github.event.pull_request.head.sha || github.sha`, yet previously named its artifact using only `github.sha` (the synthetic pull-request merge SHA). In PR233 the **source tested** is `1eb89e118b3f905c796fde3a6c36bdb0a0bf5b6b`, but the artifact **name** ends with `0aaadf7a8e9d5a4e71c2ecca645370a04704adc7`. Team E's isolated change binds artifact naming to the exact checkout expression and adds a regression assertion. It changes neither guest runtime nor service handshake, security, signing, source content, readiness deadline or evidence verdict.

## Every acceptance row: existing component probe vs. required final release evidence

Current test mapping comes directly from [tools/aegis_platform_row_preflight.py](../../tools/aegis_platform_row_preflight.py): **25** rows have preflight source-test files, **13** have no mapped integration probes. Test entries are *available test files*, not fresh PASS claims. The preflight generator correctly records `acceptance=NOT_CLAIMED` for all rows. Each row must eventually have **exact SHA, test case ID, OS host receipt, CI job, artifact digest and signer provenance**.

| ID | Requirement | Canonical release state | Preflight test file(s), not host evidence | Required final installed-host evidence |
| --- | --- | --- | --- | --- |
| 01 | Fresh Platform-only install | NOT TESTED | `test_ops_platform_install.py`, `test_ops_platform_release_staging.py`, `test_ops_platform_installation.py` | Signed self-contained installer + keyboard/theme/headless, Windows SCM and Debian systemd host receipts; no preinstalled Python/Core. |
| 02 | No Core installed | NOT TESTED | `test_platform_optional_dependencies.py`, `test_platform_import_isolation.py` | Signed installed-host inventory proving absence of Core and Ollama. |
| 03 | No canonical Core DB | NOT TESTED | `test_platform_optional_dependencies.py`, `test_platform_import_isolation.py` | Two-boot file/process observation proving no canonical personal Core DB. |
| 04 | Permanent UUID | NOT TESTED | `test_platform_installation_identity.py` | Same UUID and key fingerprint through signed reinstall/reboot/update. |
| 05 | Core-free health/startup | NOT TESTED | `test_rust_platform_service.py`, `test_platform_service_session.py` | Rust-owned signed installed OS service active, Core-free and healthy. |
| 06 | Windows service start/stop | NOT TESTED | `test_rust_platform_scm.py` | Signed Windows native SCM install/start/stop/restart/reboot/crash. |
| 07 | Debian service start/stop | NOT TESTED | `test_rust_platform_service.py` | Signed Debian12 systemd install/two boots/start/stop with first READY; current PR233 guest fails. |
| 08 | Abrupt exit recovery | FAIL | `test_rust_platform_service.py`, `test_platform_service_lock_security.py` | Crash and bounded restart of installed release, durable generation/identity, fail-closed recovery. |
| 09 | No duplicate supervisor | NOT TESTED | `test_rust_platform_service.py` | Duplicate/foreign supervisor/service ownership denial on installed hosts. |
| 10 | Authenticated CLI/IPC | FAIL | No mapped component probe | Actual OS-authenticated IPC listener, fresh scope/STOP/revocation and bounded request/response negative tests. |
| 11 | SAFE/STOP | NOT TESTED | `test_safe_operator_stop_revision.py`, `test_safe_permission_state_loss.py` | Installed service enforce STOP, lost approval, replay and no UI bypass. |
| 12 | Owner revocation | NOT TESTED | `test_safe_permission_state_loss.py`, `test_core_link_rust_authority.py` | Current owner/peer revocation rechecked during in-flight operations on both hosts. |
| 13 | Fleet enrollment | NOT TESTED | `test_ops_fleet_atomic_enrollment.py` | Installed disposable two-peer mTLS signed enrollment; no real fleet. |
| 14 | Fleet revocation | NOT TESTED | `test_ops_fleet_removal_authority.py` | Stale cert/scope/replay denial after remote removal. |
| 15 | Remote naming authority | FAIL | No mapped component probe | Authenticated remote naming authority, conflicts and permission proof. |
| 16 | Offline names | NOT TESTED | `test_fleet_stale_trust_regression.py` | Offline unconfirmed name cache, conflict resolution after reconnect. |
| 17 | Generic signed module install | NOT TESTED | `test_module_lifecycle_v1.py` | Signed generic reference-module installation and isolation, invalid signer refusal. |
| 18 | Module rollback/lifecycle | NOT TESTED | `test_module_lifecycle_v1.py` | Module restart/update/rollback/uninstall with resource caps, crash, STOP, revocation and hot-swap safety. |
| 19 | Signed update/recovery | NOT TESTED | `test_ops_platform_install.py`, `test_ops_platform_cache_security.py`, `test_ops_platform_installation.py` | Signed AG-D011 update/repair/rollback/anti-rollback with interruption and reboot. |
| 20 | Identity through reinstall | NOT TESTED | `test_platform_installation_identity.py` | Signed uninstall/reinstall retention, safe purge refusal and no second writer. |
| 21 | Invalid Core rejection | NOT TESTED | `test_signed_core_definitions.py`, `test_core_definition_path_security.py` | Malformed, unsigned, wrong target and traversal Core rejection in running installed service. |
| 22 | Signed synthetic Core install | FAIL | No mapped component probe | Governed signed inert synthetic Core installation, no personal Core. |
| 23 | Synthetic start/stop/detach | FAIL | No mapped component probe | Synthetic Core start/stop/detach with lease and approval proofs. |
| 24 | Removal leaves Platform healthy | FAIL | No mapped component probe | Remove synthetic Core and prove Platform remains healthy and sole writer. |
| 25 | Cross-platform compatibility | NOT TESTED | `test_platform_release_contract.py` | Exact OS target/ABI, wire-contract parity for Windows and Debian12. |
| 26 | Recovery without second writer | NOT TESTED | `test_platform_service_lock_security.py` | Reboot/restore/rollback without duplicate writer/stale lease. |
| 27 | Native Rust regressions | NOT TESTED | `test_rust_platform_service.py`, `test_rust_platform_scm.py` | Native Rust fmt/Clippy/tests plus disposable actual SCM/systemd from final signed product. |
| 28 | Installed-wheel isolation | NOT TESTED | `test_platform_optional_dependencies.py`, `test_component_artifact_separation.py` | Installed SDK/Platform wheel file-hash + independent METADATA proof and no Core. |
| 29 | Exact-SHA release CI | NOT TESTED | `test_platform_release_verifier.py`, `test_ops_signed_vm_release.py` | Identical signed release SHA/source/attestation/artifact hashes across both OS host receipts. |
| 30 | Complete operator runbook | FAIL | No mapped component probe | Run verified install/update/repair/uninstall/rollback/troubleshooting, redacted diagnostics and installer fallbacks. |
| 31 | Versioned authenticated management API | NOT TESTED | No mapped component probe | Running live API with OS peer authentication, bounded versioned request/reply and SAFE. |
| 32 | Terminal Control Center Windows | NOT TESTED | No mapped component probe | Installed native Windows TUI connected to authenticated service; offline/reconnect/STOP. |
| 33 | Terminal Control Center Debian12 | NOT TESTED | No mapped component probe | Installed headless Debian12 TUI connected to service; no-color/SSH/fallback. |
| 34 | GUI Control Center Windows | NOT TESTED | No mapped component probe | Signed installed Windows GUI with current API, no second authority/database. |
| 35 | Core Manager parity | NOT TESTED | No mapped component probe | Live GUI/TUI signed Core manager controls with owner-gated actions. |
| 36 | Module Manager policy | NOT TESTED | No mapped component probe | Live module connect/disconnect/uninstall/reinstall, stale drafts, signer identity and policy. |
| 37 | Security, approvals, updates and diagnostics | NOT TESTED | No mapped component probe | Actual protected approval/update/diagnostics API; UI cannot mint authority; redact secrets. |
| 38 | Theme and independent installability | NOT TESTED | `test_ui_aegis_theme_contract.py` | Canonical theme tokens in installer/GUI/TUI, truecolor/limited/NO_COLOR/ASCII, separately installable headless service. |

## Proof bundle required before promoting any row

For each applicable row collect: final immutable source commit; signed release manifest and root-of-trust chain; independently verified SHA256 of delivered bytes (not GitHub's ZIP metadata alone); target OS/architecture/ABI; actual disposable Windows and Debian12 installation by reviewed script with no Python/Cargo/Core preinstalled; host identity UUID/key fingerprint and native service ownership; two-boot and failure/reboot/rollback receipts as applicable; JUnit full case identifiers with no required test suppressed; time, action, principal/approval scope, result and failure-path evidence; separate QA acceptance.

**Negative security checks retained:** forged/mismatched signer, corrupted wheel, redirect/symlink/TOCTOU, stale cache, revoked/stolen peer and stale scopes, STOP, replay/rollback, incorrect service ownership, duplicate writer, unsupported target, stale management generation and response, sensitive data exfiltration, and Core/module/Fleet denial. Preserve `test/test_aegis_debian_vm_runner.py` replay/missing receipt/foreign-container/path/identity tests, `test/test_life_procedure_catalog.py` original RUN writer-lock denial, and installed-wheel independent METADATA tests. No mock, import test, staging receipt, disposable guest-only software signer or component PASS grants owner permission.

## Coordinator blockers and boundaries

- **A (backend):** authenticated Linux/Windows OS IPC, live owner enrollment/STOP/revocation, steady-state vs cold-start service policy; PR224 must pass exact source native Rust and both actual guest boots before the startup symptom is considered fixed.
- **B (installer):** AG-D011 signed Windows/Debian one-script interactive/headless install, service registration, upgrade/repair/rollback/uninstall/reinstall, identity retention, failure and signature receipts.
- **C (UI):** native GUI/TUI with shared canonical palette and real protected management API; offline/reconnect/stale edits, approvals, no direct authority.
- **D (modules):** Fleet remote naming, signed reference module, isolation/rollback/resource enforcement and governed *synthetic only* Core lifecycle.
- **E (QA):** exact-head independent tests, negative cases, final installed-host SHA and signer provenance, every row's independent evidence check. Never approve a partial row.
- **Coordinator:** reconcile overlapping PRs and main results, accept rows individually only after signed installed-host evidence, then ask owner for explicit GO. Do not silently merge or cut over.

**Limitations:** This review independently inspected current GitHub files, PR patches, workflow/job conclusions, failed VM and successful RC job logs, and artifact metadata. No local full repository build, private runner image, downloaded ZIP byte verification, installed production release, Windows/Debian disposable host provisioning by Team E, or owner-secret access was performed. A failure observed in public CI is reproduced by the CI run, not by a newly executed local VM in this review.


## E-001 coordinator checkpoint, 2026-11-08 UTC (no row state change)

**Independent combined-integration plan:** [PLATFORM_1_0_TEAM_E_COMBINED_INTEGRATION_PLAN_2026-11-08.md](PLATFORM_1_0_TEAM_E_COMBINED_INTEGRATION_PLAN_2026-11-08.md). It pins Teams A–D PR dependencies and six waves of tests plus final same-product signed installed-host certification; this is **a plan only**, not a combined run or signed released install. Row state remains **0/38 PASS**.

At the original QA commit `49bbd132a818b4c6f9657a77a422b70339bc3206`, **7/7 exact-head PR workflows succeeded**, including [Debian12 offline VM 42485376777](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42485376777), [Platform-only gate 42485376764](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42485376764), G0-G1, G4, G5, G6 and G7. VM runner logged **32 focused tests passed** and the actual two-boot systemd step succeeded. Public metadata from the test VM ZIP: artifact ID `13619780819`, `sha256:5431b533da786140319402568f2a2c2761f5c2a81d59e3d893060809c3ffa2e0`. Platform gate uploaded `platform-only-Linux` artifact ID `13619382642` digest `sha256:7739a77a256d0049d18c06d3f79e759fe3499bb2a4ba4229f724e138f727c4e4` and `platform-only-Windows` artifact ID `13619217423` digest `sha256:3d63f954cc58962132d7f8558192e1cdfcd78d9968aff1631fc8516f5a8c4664`. These ZIP hashes are GitHub metadata and **not independently verified installed release signatures**. Subsequent updates to this QA PR require fresh **new-head** CI; old green runs do not carry forward.

**A/Service:** [#224](https://github.com/Crazysodaman/SofiaAdaLyra/pull/224) exact head `0057e44214b73db1d94895cbef54694461910d10` had **9/9** associated workflows SUCCESS, including [two-boot Debian12 VM 42478122896](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42478122896); cold-start 12s is narrower than the existing 15s startup bound, while subsequent IPC remains 5s. This is an **unmerged candidate**, not certified as fixing the separately red [#233 VM 42480233409](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42480233409) in the combined current tree. Reconcile with A; do not raise the 45s guest gate.

**D/Test-package ownership:** [#236 Platform-only CI 42482858552](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42482858552) failed both Windows and Debian for missing ownership in `test_module_catalog_consolidation.py`; [#239 Platform-only CI 42482642441](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42482642441) failed both OSes for `test_shared_transfer_evidence.py`. [#239 Debian VM 42482642665](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42482642665) failed during the **31-case pre-boot preflight** (1 failed, 30 passed), from the same ownership issue. No VM start was attempted after that failure; do not characterize this as a separate systemd defect. D owns the precise mapping repairs; E notified both PR threads and will independently verify the new head after their changes. Retain `test_package_grouping.py` invariant.

**Open release proof:** #210 11/11 PR CI candidate, but the main signed OS installer/installed-host provenance is not certified. Required same-release Windows/Debian12 signed install/upgrade/rollback/reinstall, current SAFE/STOP authenticated management, native UI/TUI, Fleet signed remote name, module isolation and governed synthetic Core lifecycle still absent or unproven in the integrated release. No imported PASS rows, no main update, no real Core, no cutover.


## AG-D028 independent Team E acceptance extension (2026-11-08)

The owner now makes the [Artifact Library, selective acquisition, LAN Hub and enrolled peer transfer](https://github.com/Crazysodaman/SofiaAdaLyra/pull/248) mandatory for Platform 1.0 GO: [issue #250](https://github.com/Crazysodaman/SofiaAdaLyra/issues/250). This is **additional release evidence**, **NOT a new 39th #201 row**. The [16-case Team E independent LIB ledger](PLATFORM_1_0_TEAM_E_AG_D028_LIB_LEDGER_2026-11-08.md) maps every `LIB-01` through `LIB-16` to the original row IDs. [Combined integration plan W7](PLATFORM_1_0_TEAM_E_COMBINED_INTEGRATION_PLAN_2026-11-08.md) covers a signed offline Windows+Debian12 four-host topology, authenticated Core-free Hub, selective inert signed Cores/modules, peer chunk transfer, license/STOP/GC/rollback negatives and service-based GUI/TUI/CLI.

**State-preserving checkpoint:** the canonical 38 remain **7 FAIL / 31 NOT TESTED / 0 PASS**; separately **LIB-01..16 are 16 NOT TESTED, zero certified**. PR #248 is **docs-only** and does not establish an artifact server, verifier acceptance, native signed installer or trusted installed-host test. Team E owns **D028-07** and D028-00 security/contract signoff only; Team A supplies current authenticated authority, B the single governed installer and signed package boundary, C shared UI, D SDK/worker; no alternate signer, owner authority, shared DB writer, automatic Core start or production host network exposure. Prior exact SHA evidence remains scoped to its source, including the unaccepted #236 forced-kill recovery and red/queued D drafts. Existing `tools/aegis_platform_row_preflight.py` now has an **opt-in** source-only LIB crosswalk that cannot claim any installed-host PASS; independent signed release bytes, source/recipient receipts and every negative check are required before release review.
