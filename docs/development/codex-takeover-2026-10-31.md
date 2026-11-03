# Codex takeover evidence — 2026-10-31

Target: SHAKEDOWN READY only. G8 remains DEFERRED in #129.

## Observed source baseline

- Initial checkout: clean `work`, `ee8aa13169bbfbdc73d583826028740f499ee317`, one worktree. No staged or uncommitted changes. No prior work removed.
- Remote main: `ee8aa13169bbfbdc73d583826028740f499ee317` (independently read with `git ls-remote`). Local `main`/`origin/main` were stale at `b1008488`; do not use those stale refs as remote evidence.
- PR #121: draft, approved development branch `chatgpt/go-live-release-env-version`, head `370a935a09d859b844bc795ef1a676e2cd5414ae`, base main above. Comparison: 135 ahead / 1 behind. No main merge/rebase performed.
- Fetched remote development ref and created a local branch at that exact head. Original `work` branch retained.
- Read root `AGENTS.MD`; no nested AGENTS files discovered. User takeover instructions explicitly authorize development commits, pushes and updates to #120/#121.
- Retrieved current #120, #129 and PR #121 and #120 discussion. Historical audit claims in their bodies are not acceptance of current code.

## Exact baseline CI, independently retrieved

All runs below bind to `370a935a09d859b844bc795ef1a676e2cd5414ae`.

| Evidence | Run | Observed result |
|---|---|---|
| Windows installed-wheel RC | [41207426099](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/41207426099) | SUCCESS; log: 8,047 passed / 41 skipped / 6 deselected / 23 subtests; full verification accepted=True |
| Debian installed-wheel RC | [41207426087](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/41207426087) | SUCCESS; log: 8,067 passed / 21 skipped / 6 deselected / 23 subtests; full verification accepted=True |
| Windows package matrix | [41207425956](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/41207425956) | All 22 jobs SUCCESS; nonempty selection checks succeeded |
| PR targeted workflows | 41207429708, 41207429695, 41207429694, 41207429716, 41207429692, 41207429696, 41207429775, 41207429691, 41207429745 | All nine SUCCESS |

RC source provenance, twice-built wheel reproducibility, separated component construction and release evidence steps succeeded. Upload steps explicitly describe unsigned evidence. No approved signing identity or signing secret is configured in the attached runtime. Signed release acceptance and independent security review remain unproven. Skip/deselection suitability still requires review. These old results never certify subsequent changes.

## Diagnosed production defect and bounded repair

`SofiaApplication` composes `HostEffectAttestationLedger.verify_dispatch_outcome` into `GoalProductionCoordinator` as its independent outcome verifier. Static caller search finds no production caller of `attest_effect`; a full authenticated host observer-to-ledger integration remains unproven. Do not count the callback or ledger alone as a complete G7-A acceptance trace.

The ledger accepted redirected key/journal/tip reads, broad existing files and umask-dependent new journal permissions. It also accepted missing journal history despite an existing sealed tip. New negative tests reproduced eight failures before the patch (25 passing). The repair validates private files and redirection, publishes journals through the shared private atomic writer, rejects missing anchored history, and serializes publication/verification with the existing cross-platform process lock. Interrupted journal-to-tip publication remains denied after restart; no unsafe automatic repair or replay is introduced.

The cross-gate Windows/Ubuntu workflow now includes host-ledger and production GOALS reconciliation tests, which were absent from its test selection.

## Executed local verification and integration repair

- Before the ledger repair: new negative cases reproduced **8 failures / 25 passes**.
- Focused final ledger, GOALS production wiring, Discord process-lock and UI process-lock suites: **86 passed** (`python -m pytest -q test/test_host_effect_attestation.py test/test_goal_production_wiring.py test/test_discord_process_lock.py test/test_ui_process_lock.py`).
- Initial raw full-suite attempt: interrupted after **1,725 passed / 2 skipped / 8 component-build setup errors**. The sandbox denied pip's proxy connection; no passing full-suite claim was made.
- Network-enabled raw full suite (`python -m pytest -q -o faulthandler_timeout=60`): **8,081 passed / 21 skipped / 5 failed / 23 subtests**, 700.75 seconds. All five failures were in the two existing integration-marked Ollama/embodiment modules, **before provider invocation**, because their disposable canonical databases had not been bootstrapped. This was a real fixture defect, not evidence of provider availability.
- Repaired those two test modules to request the existing `canonical_state_path` disposable-state fixture. No production guard, assertion or marker changed. Retesting both complete affected modules executes all five cases; each now reaches its actual provider call and fails with **ConnectionError: Failed to connect to Ollama** (5 failed, 2.08 seconds). The integration suite remains BLOCKED, not passed or silently skipped. The raw full-suite counts above precede this fixture-only correction; no later full-suite pass is claimed.
- `pip check`: no broken requirements. Changed ledger/test syntax compilation and `git diff --check`: pass.

The approved release verifier's existing full phase uses `-m 'not integration'`; this patch does not change its exclusions. New exact-commit Windows/Debian RC and package results are required after publication. Raw local full-suite results do not establish installed-wheel provenance, signing or G8 acceptance.

Prepared `docs/development/g8-shakedown-runbook-draft.md` with authority prerequisites, disposable installation/enrollment, restore verification, independent fencing, conversation/provider/module checks, negative/recovery matrix, cognitive trace and evidence template. It is an unapproved preparation draft, not executed G8 work or a closed G7 checklist entry.

## Acceptance baseline by gate

Counts preserve the authoritative PR #121 grouping, including G1-A diagnostics counted in G0. No item is closed merely by this inventory or by a unit-test repair.

| Gate | Open before | Closed with evidence | Open after | Blockers |
|---|---:|---:|---:|---|
| G0 | 11 | 0 | 11 | Per-requirement authority, artifact and source review incomplete |
| G1 | 16 | 0 | 16 | New exact-SHA RC, skip review, signed evidence and independent review |
| G2 | 15 | 0 | 15 | Installation/lifecycle acceptance and authority composition review |
| G3 | 9 | 0 | 9 | Complete isolated migration/fencing/recovery acceptance |
| G4 | 5 | 0 | 5 | Automated complete conversation/provider continuity evidence |
| G5 | 5 | 0 | 5 | Recovery, OS lifecycle, trust/STOP acceptance |
| G6 | 4 | 0 | 4 | Signed module settings/lifecycle acceptance |
| G7 | 5 | 0 | 5 | Reviewed signed release, runbook and decision |
| G7-A | 19 | 0 | 19 | Authenticated observer composition, closed-loop installed-artifact trace; six research items nonblocking |
| TOTAL | 89 | 0 | 89 | Development BLOCKED; SHAKEDOWN READY not established |

G8: 16 DEFERRED. No production host access, enrollment, key change, canonical writer transition or protected-state migration was performed.

## Candidate source/test owners for continued requirement review

These paths locate implementation and verification candidates. They do not claim every requirement is wired, tested or accepted.

### G0

Source: `src/sofia/platform/verify/stage_release_source.py`, `src/sofia/platform/state/private_file.py`.

Tests: `test/test_verify_release_stage_git_tree.py`, `test/test_core_link_binding.py`.

### G1

Source: `src/sofia/platform/state/private_file.py`, `src/sofia/platform/ui_launchers.py`, `.github/workflows/release-candidate.yml`, `.github/workflows/debian-release-candidate.yml`.

Tests: `test/test_core_link_binding.py`, `test/test_core_link_conversation.py`, `test/test_platform_ui_launchers.py`.

### G2

Source: `src/sofia/platform/verify/component_artifacts.py`, `src/sofia/platform/ops/component_install.py`, `src/sofia/platform/core_worker/process.py`, `src/sofia/platform/modules/lifecycle.py`.

Tests: `test/test_component_install_production.py`, `test/test_core_component_install.py`, `test/test_core_worker_process.py`, `test/test_platform_module_settings.py`.

### G3

Source: `src/sofia/platform/state/replication.py`, `src/sofia/platform/ops/state_promotion.py`.

Tests: `test/test_state_replication.py`, `test/test_state_operator_handoff_review.py`, `test/test_state_relocation_atomic_publish.py`.

### G4

Source: `src/sofia/modules/ui/core_link_desktop.py`, `src/sofia/platform/core_link/transport.py`.

Tests: `test/test_core_link_desktop.py`, `test/test_core_link_conversation.py`.

### G5

Source: `src/sofia/platform/ops/recovery.py`, `src/sofia/platform/state/canonical_sqlite.py`.

Tests: `test/test_g5_recovery_evidence.py`, `test/test_backup_canonical_identity_fencing.py`, `test/test_canonical_sqlite_protection.py`.

### G6

Source: `src/sofia/platform/modules/lifecycle.py`.

Tests: `test/test_module_lifecycle_v1.py`, `test/test_platform_module_settings.py`.

### G7

Source: `.github/workflows/release-candidate.yml`, `.github/workflows/debian-release-candidate.yml`.

Tests: `test/test_state_operator_handoff_review.py`, `test/test_verify_installed_wheel_release.py`.

### G7-A

Source: `src/sofia/platform/application/bootstrap.py`, `src/sofia/core/goals/coordinator.py`, `src/sofia/platform/run/host_effect_attestation.py`, `src/sofia/core/cognition/v2/evidence.py`.

Tests: `test/test_host_effect_attestation.py`, `test/test_goal_production_wiring.py`, `test/test_cognition_v2_evidence.py`, `test/test_learning_foundation.py`.

## All unchecked tracker entries at takeover

Verbatim requirement inventory, with no implied closure. Individual caller/artifact/authority review is still required; section labels and live terminology are subject to the explicit development/G8 scope split at the top of #120.

| Entry | Gate | Acceptance | Requirement |
|---|---|---|---|
| 1 | G0 | OPEN / acceptance not established | Inventory exact `main` SHA, local working-tree changes, current Core/Platform package contents, Windows services, VM prerequisites, and canonical state owner; identify any incomplete Codex/OpenCode work. |
| 2 | G0 | OPEN / acceptance not established | Reconcile each GO requirement with *actual production call site*, tests, installed-wheel behavior, authorizer/state owner, and immutable evidence, not just design docs or mocked adapters. |
| 3 | G0 | OPEN / acceptance not established | Mark current states DESIGN / ALPHA / BETA / RELEASE CANDIDATE / PRODUCTION READY / BLOCKED with supporting evidence. Do not auto-promote from file presence or audit workflow success. |
| 4 | G0 | OPEN / acceptance not established | Keep one authoritative GO issue, use existing `ROADMAP.md` for any cross-link, and reference #119 rather than duplicating its 700-task acceptance ledger. |
| 5 | G0 | OPEN / acceptance not established | Define explicit rollback boundary and protected backups before any production cutover. |
| 6 | G0 | OPEN / acceptance not established | Capture sanitized **native Windows CI** token user SID, token default owner SID, file owner SID, DACL ACE SID/type/mask for a disposable failing `tmp_path` directory; do not log sensitive tokens, paths or contents. Show failing-before proof and reproduce both gates. |
| 7 | G0 | OPEN / acceptance not established | Implement the **smallest secure** production/fixture correction, after evaluating both (a) canonical private directory provisioning and (b) an identity-aware validator. Accept an Administrators owner only if current token context and actual effective access match the declared trusted-admin boundary; do **not** globally turn all Administrators-owned foreign directories into owner-private state by assumption. Properly interpret `OWNER RIGHTS` only when exact descriptor owner and applicable ACE grant meet the private-state policy. Do not blindly treat any owner-backed ACE as proof of current-user read/write access. |
| 8 | G0 | OPEN / acceptance not established | Preserve unauthorized `Everyone/Users` ACE rejection, foreign owner rejection, NULL-DACL denial, redirected parent/junction/symlink denial, wrong identity, symlink race behavior, no automatic re-ACL of arbitrary pre-existing production directories, and no security bypass under CI. |
| 9 | G0 | OPEN / acceptance not established | Add Windows-native and deterministic tests for regular user, elevated/admin default owner, OWNER RIGHTS, foreign owner, owner without effective access, extra broad ACE, inherited ACEs, junctions, persistent JSON file, and revoked/wrong-host Core Link binding. Privilege-dependent tests must report a justified inability rather than claim coverage. |
| 10 | G0 | OPEN / acceptance not established | Run focused `test/test_core_link_binding.py` and `test/test_core_link_desktop.py` and shared-usage affected suites; verify Windows package matrix / RC on the **same SHA**, with exact pass counts. Do not certify until passing. |
| 11 | G0 | OPEN / acceptance not established | Record exact code diff, tests/evidence, reviewer decision, commit SHA, and G1-A DONE status before addressing the Debian TLS / launcher release blockers. |
| 12 | G1 | OPEN / acceptance not established | Fix Windows Core Link private-state SID/ACL failures in `src/sofia/platform/state/private_file.py` / related tests. Retain owner-only confidentiality, reject unsafe ACEs/junctions and unauthorized readers; separate security behavior from Windows test-fixture assumptions. |
| 13 | G1 | OPEN / acceptance not established | Fix Debian Core Link mutual-TLS fixture chain (`Missing Authority Key Identifier`) and exercise real pinned mTLS, without disabling verification or modifying production trust policy. |
| 14 | G1 | OPEN / acceptance not established | Fix Windows current-user launcher path/shortcut regression. |
| 15 | G1 | OPEN / acceptance not established | Verify both remote conversation and protected Core Link binding tests, with negative cases for wrong host/identity/revocation, disconnected client, and stale generation. |
| 16 | G1 | OPEN / acceptance not established | All **22 package suites** pass on the exact commit; full **Windows** and **Debian** Release Candidate installed-wheel/provenance/reproducibility gates pass on that same SHA; no required tests skipped or evidence waived. |
| 17 | G1 | OPEN / acceptance not established | Independent security/recovery review and signed release evidence, not merely CI-green claims. |
| 18 | G1 | OPEN / acceptance not established | Correct the **disposable test CA/leaf fixtures** using proper Subject Key Identifier / Authority Key Identifier as required by the target OpenSSL verifier; validate CA-to-leaf issuer identity and client/server EKU/SAN, not merely the presence of one extension. |
| 19 | G1 | OPEN / acceptance not established | Preserve actual mutual TLS, hostname validation, pinning, wrong-CA/wrong-identity rejection, expired/revoked enrollment and negative tests. Do not switch verification off, use `CERT_NONE`, or relax production TLS policies. |
| 20 | G1 | OPEN / acceptance not established | Run `test/test_core_link_conversation.py` with localhost sockets plus the full Debian RC installed-wheel gate on the **same exact SHA** and capture signed evidence. |
| 21 | G1 | OPEN / acceptance not established | Replace fragile literal separator assertions with **path-component/semantic assertions** that independently verify shortcuts only land under the approved current user's Start Menu / Desktop, without accepting traversal/redirected paths or unrelated user/system startup locations. |
| 22 | G1 | OPEN / acceptance not established | Keep existing Unicode-safe encoded PowerShell, restricted current-user autostart, receipt validation and safe shortcut creation tests. |
| 23 | G1 | OPEN / acceptance not established | Verify exact Windows test case and broader UI package + installed-wheel Windows RC. |
| 24 | G1 | OPEN / acceptance not established | **Windows Release Candidate**, [run 40597782000](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/40597782000), cancelled after its configured **60-minute job limit** while installed-wheel verification showed ~90% complete, with no indicated test failure in the progress tail. Its artifact is only partial diagnostics and **not** a release certificate. |
| 25 | G1 | OPEN / acceptance not established | **Manual Verification**, [run 40597781926](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/40597781926), cancelled at the configured **20-minute limit**, after 1,850 tests executed, with no final verification-evidence file. Must not count as acceptance. |
| 26 | G1 | OPEN / acceptance not established | Fix the *verification budget or test sharding*, not test gates: `.github/workflows/release-candidate.yml` has `timeout-minutes: 60` and `.github/workflows/manual-verify.yml` has `timeout-minutes: 20`. Increase bounds conservatively or split the full suite with merged exact-SHA receipts; preserve installed-wheel provenance, signed artifacts, full required test coverage and no skipped checks. Record a new exact SHA; it needs its own full acceptance. |
| 27 | G1 | OPEN / acceptance not established | Independently validate security-sensitive ACL/junction/owner tests ran (rather than being skipped), review signed RC evidence, then close G1. |
| 28 | G2 | OPEN / acceptance not established | Generic Platform/SDK installation on a clean headless Debian VM works **without preinstalling Sofía Core**, her Constitution, or private state. Verify actual artifact/import/dependency contents, not just a role flag. |
| 29 | G2 | OPEN / acceptance not established | Install the reviewed, identity-bound Sofía Core package as an authorized component on that Platform, using approved exact digests and compatibility negotiation. Reject unsigned/wrong-version/wrong-identity packages. |
| 30 | G2 | OPEN / acceptance not established | Core runs as an independently supervised process with authenticated, versioned Platform IPC; Core has no unrestricted canonical SQLite writer. Validate generation fencing, drain, restart, health and release attestation. |
| 31 | G2 | OPEN / acceptance not established | Independent module/provider lifecycle: install/stage/start/stop/update/rollback and maintain module settings via the canonical Platform authority. Platform/other modules stay running for module-only updates. |
| 32 | G2 | OPEN / acceptance not established | Supported `LIVE` and `NEXT_OPERATION` config updates apply without restarting services; a `COMPONENT_RESTART` drains/replaces **only** affected worker; a genuine `PLATFORM_RESTART` explicitly reports downtime. Do **not** promise zero interruption for Core replacement/host cutover. |
| 33 | G2 | OPEN / acceptance not established | Receive an unpushed patch/diff bundle for `8ca07dfd` or publish only after explicit reviewed merge strategy, then inspect all 21 files and code movement for semantic identity, cycles and import-side effects. |
| 34 | G2 | OPEN / acceptance not established | Validate baseline failure equivalence with exact test IDs and commands, prevent canary path contamination in Windows subprocesses, and document privilege skips rather than treating them as passing. |
| 35 | G2 | OPEN / acceptance not established | Re-run installed-wheel import isolation in fresh environments, ideally on Windows and Debian, not just `PYTHONPATH=src`. Ensure legacy integrated Core still operates. |
| 36 | G2 | OPEN / acceptance not established | After acceptance, commit/push via approved Git workflow, trigger new same-SHA CI; then mark **G2-A DONE**. Never claim complete G2 until physical package separation G2-B is proven. |
| 37 | G2 | OPEN / acceptance not established | **G2-A / dependency isolation:** Build Core-free import dependency audit and installed wheel/RECORD validator; relocate shared value types and instrumentation (e.g. `IdentityBootstrapMode`, `EnvironmentConfiguration`, `LocationSubject`, `PrincipalContext`/`AudienceKind`, cognition request types, `record_sqlite`) into SDK or Platform-owned leaf contracts with backwards-compatible Core reexports. Eliminate all Core imports in the *Platform-only* import graph, not just the 6 obvious imports. Preserve existing integrated-mode behavior and tests. |
| 38 | G2 | OPEN / acceptance not established | **G2-B / physical packages:** Produce separately installed, versioned, provenance-bound, reproducible and signed `platform-runtime`, `sdk-contracts` (or reviewed coherent contract distribution), `core-runtime` + `core-sofia` artifacts. Verify no real Core, Constitution, memory, persona, Core-only dependencies or Core runtime assets ship to a `CORE_LINK/MODULE_HOST` installation; preserve installed-wheel compatibility and a tested upgrade/migration path from the original unified wheel. |
| 39 | G2 | OPEN / acceptance not established | **G2-C / Core lifecycle and authority:** Bind approved Core artifact identity/digest, SDK/ABI/schema compatibility and exact one-use SAFE/owner approval to an actual production coordinator that stages, handshakes, drains, fences and activates via `CoreWorkerController.replace()` without restarting Platform. Verify package bytes before and inside spawned worker; enforce one active Core generation and fail closed on uncertainty. |
| 40 | G2 | OPEN / acceptance not established | **G2-D / crash/upgrade reconciliation:** Implement bounded, durable component-generation reconciliation/health/restart-policy handling after worker death, interruption and release failure. No automatic resurrection of a fenced writer or arbitrary replay of uncertain actions. Exercise OS watchdog, restart, rollback and leased-generation failures. |
| 41 | G2 | OPEN / acceptance not established | **G2-E / local module-host state:** Refactor the module lifecycle manager from `CanonicalSQLiteGuard(sofia.db)` assumptions to reviewed Platform-local operational storage on `MODULE_HOST`. Enforce `MODULE_HOST` authorization and its immutable package/receipt/settings scope, with remote global authority still at Core Host. Test offline/online, revoked grants, stale revisions, different machines and migration of *existing* module records only when separately reviewed. |
| 42 | G2 | OPEN / acceptance not established | **G2-F / actual host commissioning prep:** Audit `Setup-SofiaFleetArtemis.ps1` obsolete `sofia.distributed` entry points; implement safe path fixes if reproducible. Verify generic headless Platform install, a separately installed approved Core, Venus thin-client/Fleet GPU worker, pinned model, signed runtime state pointer, systemd/Windows service behavior. Keep no-effect rehearsal separated from authorized live migration. |
| 43 | G3 | OPEN / acceptance not established | Sofía can create an explainable, self-initiated *migration proposal* using current authenticated Fleet resources, policy, compatibility, and an accurate risk/availability assessment. No self-issued execution authority. |
| 44 | G3 | OPEN / acceptance not established | New VM Platform discovery, verification, trusted enrollment, user approval/standing grant and host/role eligibility work end to end. First pairing/enrollment requires the contract's explicit approval. |
| 45 | G3 | OPEN / acceptance not established | Stage the exact signed Core artifact and ensure target Platform, SDK, dependencies, state schema, assets, memory and runtime capabilities are compatible; estimate storage/bandwidth/compute and required interruption. |
| 46 | G3 | OPEN / acceptance not established | Produce a consistent protected backup/snapshot of all **canonical identity, memory, conversation, personality, emotional, configuration, audit, and state-plane assets**, plus required external references; integrity hashes and restore rehearsal are mandatory. |
| 47 | G3 | OPEN / acceptance not established | Transfer state through authenticated, confidential transport and verify completeness, provenance, and byte/hash integrity. The target must not expose/private-serve or mutate canonical state before legal activation. |
| 48 | G3 | OPEN / acceptance not established | Drain in-flight conversations/actions, persist idempotency and uncertain-effect receipts, fence source Core and source canonical writer, verify **one active writer**, start/attest target Core and commit host generation atomically as far as protocol permits. |
| 49 | G3 | OPEN / acceptance not established | Preserve identity, memories, current persona/presentation choices, conversation IDs, authorized modules and owner permissions; migration must never create another Sofía or silently reset state. |
| 50 | G3 | OPEN / acceptance not established | Venus Core Link safely follows the **authorized exact-identity relocation** (pre-enrolled handoff certificate/endpoint/generation, or explicit reapproval), with no silently trusting a discovered same-name host. Restore desktop chat and remote settings. No platform-wide restart on Venus. |
| 51 | G3 | OPEN / acceptance not established | Evidence-backed success and rollback/recovery: injected partition/crash pre-/mid-/post-fence, corrupt/incomplete copy, unavailable target, stale lease, duplicate writer, schema incompatibility, lost approval, and replay of uncertain actions all fail safely. Once the source is fenced, it cannot blindly resurrect. |
| 52 | G4 | OPEN / acceptance not established | Use the Core Link desktop/tray as a genuine Core-free client, bound to the authoritative VM Core, without local `SofiaApplication` or second canonical database; prove installation and real Windows GUI behavior. |
| 53 | G4 | OPEN / acceptance not established | Discord routing remains single-bot/single-authority and safely reconnects to the new canonical Core without duplicated sessions/outbound messages. |
| 54 | G4 | OPEN / acceptance not established | Preserve Avatar 2D and voice functionality on Venus; at minimum accurately report any unsupported remote voice/animation workflow, and do not count a hypothetical presentation as a completed action. |
| 55 | G4 | OPEN / acceptance not established | Venus-based Ollama inference stays explicitly model/digest-pinned and securely mediated (authenticated worker/gateway, no exposed unauthenticated API); Core on VM uses approved Fleet provider routing with startup/reconnection/outage receipts. |
| 56 | G4 | OPEN / acceptance not established | Test Venus offline/PC asleep, Ollama down, network partition, stale telemetry, game-mode GPU contention, and return-to-service. No unauthorized model/host switch and no invented model response. |
| 57 | G5 | OPEN / acceptance not established | Canonical single-writer state and protected state-plane asset ownership survive service crash, host reboot, network partition and recovery without duplicates. |
| 58 | G5 | OPEN / acceptance not established | Verified consistent backup **and restore** of actual canonical SQLite and relevant state assets. RPO/RTO targets must be agreed and measured; optional redundancy/read-only replicas cannot become a second acting Core. |
| 59 | G5 | OPEN / acceptance not established | Approved migration authorization, SAFE/FIDO step-up, STOP propagation, secrets/credentials isolation, audience/privacy scope, trust revocation, mTLS rotation and append-only audit traces work in production-shaped tests. |
| 60 | G5 | OPEN / acceptance not established | Independent OS watchdog and clean Windows/systemd service lifecycle; no boot-loop, hidden restart, silent loss of in-flight work or failed rollback represented as success. |
| 61 | G5 | OPEN / acceptance not established | Distinguish operation completion, persisted receipt, delivered event, actual external effect and unknown outcome. |
| 62 | G6 | OPEN / acceptance not established | Core and Platform start and remain healthy with all optional modules absent. |
| 63 | G6 | OPEN / acceptance not established | Module Manager can accurately list verified packages, install/stage/activate/pause/disable/update/rollback/remove with governed approval, dependency/resource constraints, and real health/maintenance/readiness receipts. |
| 64 | G6 | OPEN / acceptance not established | At least one **real signed, reviewed** module demonstrates module-owned settings contract + protected update + registered apply handler + verified effective revision, including restart/cancel paths. |
| 65 | G6 | OPEN / acceptance not established | Each of the **47 optional modules** keeps its own independent sign/review/installation/readiness gate; no blanket BETA/Production Ready claim. Optional modules never block GO unless specifically required by the critical user conversation path. |
| 66 | G7 | OPEN / acceptance not established | Freeze and document the exact reviewed source commit, independently installed signed artifacts, dependency locks, supported hosts, ABI/schema compatibility, deployment roles and immutable provenance. |
| 67 | G7 | OPEN / acceptance not established | Pass all applicable exact-SHA Windows/Debian package families, installed-wheel RC, reproducibility, security and negative tests; resolve or explicitly block failures without waiving requirements. |
| 68 | G7 | OPEN / acceptance not established | Prepare a reviewed G8 shakedown runbook with safe disposable-state installation, pairing, Core activation, Venus conversation, inference, module tests, failure injection and rollback steps. |
| 69 | G7 | OPEN / acceptance not established | Prepare owner approval boundaries, state/secret inventory, protected backup and restore procedures, source-writer fencing/STOP checks, stop conditions and evidence templates without touching protected production state. |
| 70 | G7 | OPEN / acceptance not established | Independently review G0–G6 and mandatory minimum G7-A development evidence; declare SHAKEDOWN READY or BLOCKED. This is **not** production GO and does not authorize G8 execution. |
| 71 | G7-A | OPEN / acceptance not established | Reconcile E01–E22 against latest exact-SHA source, configuration, installed Core artifact, production callers, tests, known exceptions and runtime registration. Record PRESENT / COMPOSED / WIRED / TESTED / MATCHING-CI / LIVE-ACCEPTED separately; **file existence is not acceptance**. |
| 72 | G7-A | OPEN / acceptance not established | Keep one persistent Sofía identity, one canonical writer, one V2 semantic \`ProductionTurnKernel\`, one governed scheduler and existing model/provider boundary. No Core identity/state duplication into Modules or Platform. |
| 73 | G7-A | OPEN / acceptance not established | Preserve already-verified links: conversation→V2 focus/answer; approved source→reviewed memory; NEURO→advisory priority; GOALS→SAFE/RUN/receipt; LIFE verified artifact→interest update; Generalization outcome→GOALS bounded planning advice; model selection→provider/Fleet routing. |
| 74 | G7-A | OPEN / acceptance not established | **Symbolic/evidence truth:** Determine the intended production role of the V2 \`EvidenceGraph\` created in \`platform/application/bootstrap.py\`; find/establish an actual justified consumer or explicitly document inspection-only ownership. Test conflicting, stale, corrected and revoked atoms against factual answers and goals. Require traceable derivations; never equate document hyperlink graphs with causal proof. |
| 75 | G7-A | OPEN / acceptance not established | **Perception→Core trusted bridge:** Exercise at least one **real supported, consented** observation path (e.g., authorized Fleet/host sensor evidence) through source identity, time, expiry, scope, Presence receipt/conflict handling, V2 evidence, answer/focus and relevant goal planning. Show failures for forged, stale, cross-audience, revoked or missing-source observations. Visual/audio capture is not automatically authorized. |
| 76 | G7-A | OPEN / acceptance not established | **Learning→future decision:** Prove independently verified outcomes can change a later eligible plan or preference via existing Learning/Generalization/LIFE owners; show a deterministic **without-learning** baseline/ablation, reason trace, bounded influence and revocation. A model's own praise or unverified prose cannot be training evidence. |
| 77 | G7-A | OPEN / acceptance not established | **Planning→authorized action→outcome:** Demonstrate a typed multi-step goal with dependencies, blocked/approval branch, bounded retry or evidence-triggered replan, independently enforced SAFE/STOP, a real scoped read-only capability result/receipt, and correct FAILED/UNKNOWN handling. A plan never grants permission. |
| 78 | G7-A | OPEN / acceptance not established | **Memory, goals and identity continuity:** Restart the canonical Core and verify source provenance, corrected memories, lessons, current goal/plan state, behavioral preferences, conversation continuity, and exactly-once or safely reconciled work. No private cross-audience leakage or duplicate effects. |
| 79 | G7-A | OPEN / acceptance not established | **Provider/module failure isolation:** Verify Core without optional modules, provider/GPU outage, cancelled or unavailable observation, host/network partition, resource pressure and recovery. Non-LLM functions must not invent answers; unresolved effects remain UNKNOWN. |
| 80 | G7-A | OPEN / acceptance not established | **One end-to-end acceptance trace:** On the actual release artifact, show **authenticated observation → Presence/V2 evidence → explainable inference → GOALS plan → SAFE/RUN/module result → verified outcome → eligible learning → changed later decision**. Include provenance/identity/audience/expiry IDs and test revocation, restart and baseline comparison. This is **required for GO**, not something demonstrated merely by individual unit tests. |
| 81 | G7-A | NONBLOCKING RESEARCH | Expand **symbolic reasoning** through provenance-aware bounded rules, derivation chains, contradictions, unknowns and explicit uncertainty, using V2/KNOW and GOALS ownership. |
| 82 | G7-A | NONBLOCKING RESEARCH | Extend **hierarchical planning/replanning** with versioned dependency graphs, recovery plans, cancellation and uncertainty-aware branches; never invent a second RUN or ACT scheduler. |
| 83 | G7-A | NONBLOCKING RESEARCH | Pilot a **causal world model** using a small verifiable domain (e.g., homelab service dependency/impact): source-linked hypotheses, counterfactual comparisons, confounders, calibration and held-out outcomes. Never promote hypothesis to observation automatically. |
| 84 | G7-A | NONBLOCKING RESEARCH | Improve **lifelong learning and skill transfer**, model/skill-candidate approval, prediction error/calibration, adaptive decision influence and metacognitive abstention; use existing Learning/Generalization/EVOLVE review and shadow baselines. |
| 85 | G7-A | NONBLOCKING RESEARCH | Connect additional **perception modalities** only after independently verified device/capture consent, data privacy, source freshness, prompt-injection isolation, and measured real-host benefit. |
| 86 | G7-A | NONBLOCKING RESEARCH | Develop **feedback control** only inside specialized bounded modules (Gaia simulations first), retaining Platform safety and a separately reviewed physical-actuator gate. Physical robot/servo control and all optional modules are **not GO LIVE dependencies** unless separately elevated to the critical deployment path. |
| 87 | G7-A | OPEN / acceptance not established | For each mandatory edge, record source path, exact SHA, production call site, configuration, expected outcome, negative case, deterministic baseline, tests and real runtime/host evidence. Existing candidate test inventory includes \`test/test_cognition_v2_turn_kernel.py\`, \`test/test_cognition_v2_evidence.py\`, \`test/test_generalization_advanced.py\`, \`test/test_learning_foundation.py\`, \`test/test_life_project_forge.py\`, \`test/test_presence_cross_modal_provenance.py\` and \`test/test_v18_presence_conflicts.py\`. **Test files were inspected, not run in the audit.** |
| 88 | G7-A | OPEN / acceptance not established | Obtain matching-SHA Windows/Debian installed-artifact CI and independently reviewed live Venus ↔ Sofía VM acceptance when applicable. Respect G1–G7 prerequisites and the protected state-cutover approval boundary. |
| 89 | G7-A | OPEN / acceptance not established | Mark **G7-A NO-GO** until the minimum cross-subsystem trace and negative/restart tests are demonstrated. Preserve explicit uncertainty and avoid blanket “hybrid AI production ready” claims. |

## Addendum 2026-11-02 (correction, facts only)

The production diagnosis above was true for this document's baseline and is
**not** the current state. Later main commits changed these findings:

- Commit `4b704b61` (feat(g7a): verify outcomes through pinned Fleet host) and
  predecessor work added production call sites for `attest_effect` and the
  observation ledger (`platform/distributed/agent.py`, `platform/distributed/capability.py`,
  `platform/application/bootstrap.py`). The "no production caller of
  `attest_effect`" defect is repaired in source; acceptance still requires
  matching-SHA CI and live-verifiable evidence per G7-A #87–#89.
- Commits `1d23040b`, `34e23f5e`, `c6961900`, `a7a697d1` established the V2
  `EvidenceGraph` truth-gate consumer for Fleet hardware answers (item 74),
  including premise expiry/revocation invalidation, stale derived-premise
  propagation with source trust, and Fleet evidence revocation on node
  retirement.
- This addendum records only these source facts; it does not close any
  acceptance item. Per-item status remains governed by #120/#133 evidence
  rules and the exact-SHA CI gates.
