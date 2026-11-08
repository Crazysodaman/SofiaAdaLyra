# Platform 1.0 | Team E isolated A–D combined-integration verification plan

**Decision:** E-001, 2026-11-08 UTC. **Authority:** [Platform #201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201), [38-row acceptance](PLATFORM_1_0_ACCEPTANCE.md), [Team E receipt ledger](PLATFORM_1_0_TEAM_E_EVIDENCE_2026-11-08.md). **Status:** PLAN ONLY, not an execution/merge/owner-approval grant. **GO = NO; 0/38 formally PASS.**

This plan is a **separate disposable integration exercise**, not a rewrite of `main`. It never activates the personal Core, contacts production Portainer, enrolls live Fleet peers, consumes owner secrets or changes Venus/Artemis. An isolated disposable OS identity is not permission to act on a real host.

## 1. Freeze and attest the source set before composing code

Record the **40-character Git SHA of each PR head at run start**. Never assemble from mutable branch names. The following pin set is the 2026-11-08 sampling point and **must be refreshed** whenever a worker pushes:

| Lane | Candidate PR and inspected head | Dependency / admission |
| --- | --- | --- |
| Main reference | `dd7020ce48c06e82684d3439779266de9ea965b4` | Re-read repository `main` before starting. Tests on a historical baseline do not certify later main. |
| Full-release CI correctness | [#210](https://github.com/Crazysodaman/SofiaAdaLyra/pull/210), `9549268d44e7766b2078d185f21b40ec9b45667c` | 11/11 PR workflows success, including Windows/Debian RC builds; PR keyless signer/provenance jobs skipped. Reconcile independent installed-wheel and RUN source-lock checks first. |
| A: cold-start | [#224](https://github.com/Crazysodaman/SofiaAdaLyra/pull/224), `0057e44214b73db1d94895cbef54694461910d10` | 9/9 PR workflow success, including two-boot Debian12 VM. Reconcile [#233](https://github.com/Crazysodaman/SofiaAdaLyra/pull/233) diagnostic classes; do not stack two conflicting guest classifiers. Preserve 12s cold-start / 5s health / 45s guest bounds. |
| A: authenticated transport / authority | [#235](https://github.com/Crazysodaman/SofiaAdaLyra/pull/235) -> [#241](https://github.com/Crazysodaman/SofiaAdaLyra/pull/241), inspected #241 `d468611426fc54e304ff6bc1380791a3ba702e90` | #241 **stacks on #235**. Reconcile dispatcher #226, reply contract #234, OS-authenticated Linux listener and Windows named pipe into one Platform-owned API; no direct UI permission. Do not test as authorized if peer only identifies a kernel user but lacks current owner enrollment. |
| B: installer | [#244](https://github.com/Crazysodaman/SofiaAdaLyra/pull/244), inspected `16990b36b591ecfeb3b8ece1060b6600df93b615` | Canonical AG-D011 entrypoints; reconcile older #209 (signed disposable VM), #212 (lifecycle) and #229 (plan). Preview-only behavior and safe refusal are not installed service mutation proof. |
| C: GUI / TUI | [#243](https://github.com/Crazysodaman/SofiaAdaLyra/pull/243), inspected `d7f589b6238bda8f48f908d72792348969bffd2d` | Canonical shell must consume A's versioned authenticated API and B's signed artifacts; reconcile #217, #230, #231; do not add a duplicate service or authority source. |
| D: signed reference modules / Fleet | [#240](https://github.com/Crazysodaman/SofiaAdaLyra/pull/240), inspected `4b976040f93020448bd765a5a06d97b1259e5afc`; [#242](https://github.com/Crazysodaman/SofiaAdaLyra/pull/242), inspected `458ed61fe2e965abc0fd370bac3cad90249d7c45` | Signed inert reference module, strict SDK Python/Rust protocol, Fleet local/remote signed naming. Only synthetic Core lifecycle; never a real Core. |
| D: Portainer / consolidation (separate optional wave) | #236 `82c2c5847b254569c7e43ffb2719ed745ea71cdf`, #238 `7bbf7174a60d0a48fa5c2493be77eebc4f6e66b2` -> #239 `72f82740f133b44e46e2df46e2a7666130dcb0ea` | **BLOCKED**: #236 missing ownership for `test_module_catalog_consolidation.py`; #239 missing `test_shared_transfer_evidence.py`, fails VM preflight **before boot**. Both must independently repair, then run exact-head CI. No production Portainer write scope. |
| E: independent verifier | [#245](https://github.com/Crazysodaman/SofiaAdaLyra/pull/245) | Evidence inventory and source-pinned artifact naming; must pass its own **new** exact-head checks after every documentation/test edit. |

A **pinned candidate manifest** for each isolated run must record: `baseline_sha`, `pr_head_sha` per lane, any intentional excluded PR with rationale, resolved conflicts, resulting combined **Git tree hash / disposable CI commit** (if permitted), test workflow references, signer/trust root, target OS, output artifact SHA256 and runner provenance. Reject mutable `latest`, `main` shorthand, empty SHA, contradictory ancestry or unreviewed conflict resolutions.

## 2. Build *only* in a disposable isolated environment

1. Coordinator reviews the pin set, PR ancestry, overlapping files and exact CI for each **current** PR head. If a required PR is red, pending, or based on superseded contracts, mark that wave **BLOCKED**; do not bypass it.
2. Create a fresh disposable CI workspace or isolated local worktree from the pinned main commit. Fetch each PR by its exact SHA into read-only refs. Verify `git rev-parse` equals the manifest before reading bytes. Never checkout, commit, merge or push to `main`.
3. Conduct a **dry-run** diff and conflict check in wave order below. If an integration exercise later requires an ephemeral merge commit, it must be created only in an explicitly disposable test ref, with no remote push and no production deployment; record both parents and tree hash. **This E-001 task does not perform any merges.**
4. Reject hidden conflict resolution, duplicate dispatcher/installer engines, overwritten IPC schemas, skipped failing tests, updated package owners without corresponding tests, changed signer roots or owner permissions. Notify the source owner and resume only after a reviewed PR correction.
5. Build fresh source-based SDK/Platform wheels and native Rust for Windows + **Debian12 ABI**. Verify independent installed wheel METADATA and target runtime ABI. No preinstalled Python, Cargo, Git, model, or Sofía Core on final **installation targets**.
6. Source-produced test release signatures are for **lab checks only**. Trusted production-signing evidence and release attestation must be independently verified against the reviewed root, not inferred from the GitHub artifact ZIP hash or disposable software signer.
7. Preserve full JUnit and failure logs in secured runners; publish only redacted bounded receipts without secret, raw private journal, SSH credential, signer private key, identity private key, or personal Core state.

## 3. Integration test waves and required fail-closed cases

| Wave | Source owner | Executable checks | Negative / denial proof | Rows informed, not accepted |
| --- | --- | --- | --- | --- |
| W0 source & package correctness | E / #210 | Exact installed-wheel SDK/Platform, independent METADATA, full Package Tests, Windows RC, Debian RC, Rust fmt/Clippy, per-SHA source lock regression; prove no mandatory Ollama | Corrupt wheel, missing source manifest, delayed genuine RUN receipt changed under writer lock, missing package owner, wrong ABI | 02, 03, 25, 27–29 |
| W1 Rust-owned Core-free service | A / #224 | Disposable native Windows SCM lifecycle and offline Debian12 two-boot systemd, crash/restart, duplicate rejection, startup-timeout evidence | No ready phase, deadline exceeded (do not extend 45s), partial first boot, identity mismatch, stale generation, second writer, duplicate service | 04–09, 26–27 |
| W2 authenticated management | A / #235/#241/#226/#234 | Actual Unix peer-credential socket and Windows named-pipe peer identity, *current* enrolled owner scope, schema/correlation, service-issued status/receipts and healthy reconnect | Unknown/revoked/stolen peer, missing SAFE approval, STOP mid-request, stale generation, pipelined/oversized request, extra reply fields, lost connection | 10–12, 31, 37 |
| W3 installer and release transitions | B / #244 | **Real signed** PowerShell/Bash reviewed launcher; native OS service install, update, repair, rollback, uninstall/reinstall, target validation, interruption/reboot, identity preservation | Unsigned/wrong-target/tampered bytes, rollback below floor, purge without separate permission, unrelated SCM service adoption, unsafe filesystem, noninteractive default approval, no signing trust | 01, 04–09, 19–20, 25–30, 38 |
| W4 native clients | C / #243 | Actual Windows GUI + Windows/Debian TUI installation, shared theme, API-only management, live Core/module/settings/updates views, reconnect, headless and accessible console | UI forged approval, stale edit, denied/revoked/STOP API, offline unknown, false healthy display, ANSI in redirected logs, no-color/16/256/ASCII failures, fake signer display | 30–38 |
| W5 Fleet/modules/synthetic Core | D / #240/#242 | Signed reference module SDK conformance, independent resource-limited lifecycle, signed Fleet remote name authority and reconnection, owner-gated **inert synthetic** Core stage/start/stop/detach/remove | Forged signer/name, revoked module grant, duplicate module writer, rogue Portainer stack update, stale cached name, worker crash, budget limit, unauthorized Core activation, actual Core package | 13–18, 21–24, 35–36 |
| W6 same-product release certification | E independent | From *one frozen reviewed release*, install on new Windows and Debian12 disposable hosts, two boots, verify release bytes/signer/source/receipts, execute complete rows 01–38, compare independent reviewer observations | Mismatched SHA across hosts, downloaded archive mismatch, missing/skip/FAIL critical JUnit, fake/duplicated boot IDs, untrusted test signer, mutated approval, partial/unverified installer output | All 38 individually |

**Release acceptance is all-or-nothing per row but not all-or-nothing per CI job.** Development work may pass several waves while rows remain FAIL/NOT TESTED. A critical negative fail, missing requirement or a test marked skipped is **BLOCKING**, not a partial PASS. Keep the full personal Core's five known live Ollama failures reported separately; the Platform cannot claim the full-project shakedown.

### Disposable installed-host scenario IDs (proposed; not yet executed)

- `WIN-FRESH-01`: clean supported Windows VM, no Python/Cargo/Git/Core; trusted signed PowerShell installer, SCM, UUID; preflight denial and owner approval.
- `DEB12-FRESH-01`: clean Debian12 PID1 systemd VM, correct glibc ABI, no Core, signed Bash installer, two boots, enabled service and stable key.
- `WIN-LIFE-02`, `DEB12-LIFE-02`: approved install -> update -> stop/crash -> recovery -> rollback -> repair -> uninstall/reinstall; verify no second writer.
- `WIN-SEC-03`, `DEB12-SEC-03`: invalid signer, corrupted/wrong-target bytes, stale owner permission, STOP during mutation, replay and interrupted installation all fail closed.
- `WIN-UI-04`, `DEB12-TUI-04`: native GUI/TUI/installer palette and accessible terminal fallbacks, live API and no separate authority.
- `HOST-DISCONNECT-05`: detached Fleet peer, revoked module/Core, stale status and recovery across two disposable nodes.
- `HOST-EVIDENCE-06`: signer, exact source, release manifest, binary SHA, independent file inventory, JUnit test IDs, two-boot receipt cross-comparison.

Each ID is **a planned identifier only** until an independently inspected signed host receipt exists. Do not backfill a scenario ID from a development QEMU harness; the latter uses a disposable software signer and test assembly.

## 4. Outcome and artifact contract

For each scenario row, E records:

- `row_id` (01–38), canonical requirement, original state `FAIL` or `NOT TESTED`, final verdict `NOT_CLAIMED` until independently approved.
- `source_sha` and complete dependency head tuple, combined ephemeral tree/commit (if created), CI run/job URL and exact JUnit testcase IDs (skips, failures and deselections included).
- `platform` Windows or Debian12, build target ABI, precise installer/release manifest SHA256, verified signer key ID/fingerprint and authorized trust anchor, installed file inventory SHA256.
- Disposable host ID (non-secret), OS version, two distinct boot IDs, stable Platform UUID/public-key fingerprint, service ID/pid/generation, crash/STOP/approval/denial receipts and time.
- Scope: lab vs trusted signed final release, service/user authorization explicitly separated, keyless attestation status, verified downloaded binary bytes vs GitHub ZIP metadata.
- `negative_cases` required/observed, `limitations`, reviewer identity and independent signoff. **Missing fields block PASS.** Error, unknown or unavailable observations never become PASS.

**Acceptance sequence:** (a) source owners pass exact-head tests; (b) E builds isolated same-SHA candidate and collects real installed-host proofs; (c) independent trusted signer & artifact validation; (d) E reconciles one row at a time against canonical #201; (e) coordinator requests explicit owner GO. No automated row promotion, no module/Core activation or live host migration.

## 5. Open blockers and correct dependency order

1. **#210:** reconcile full-release correctness fix and require *main's own exact-source* Package/Windows/Debian RC checks. PR success is only candidate proof.
2. **#224/#233:** reconcile bounded cold-start and guest diagnostic contract with A. #224 9/9 success and actual two-boot VM; #233 still red at its own head. Fix root, preserve 5s steady-state and 45s VM deadline.
3. **#236/#239 Team D:** correct explicit test-package ownership in `test/conftest.py` mappings or equivalent recognized rules; rerun `test_package_grouping.py` and the full exact-head CI. #239 VM failure is pre-boot test ownership, not systemd. Keep stacked #238 ancestry.
4. **Team A authenticated listener:** reconcile #235 -> #241, #226 dispatcher and #234 reply contract; Windows named-pipe equivalent and current SAFE/STOP/enrollment are required before GUI/installer actions.
5. **Team B full signed installer:** #244 launcher and native install/update/repair/rollback/uninstall; reconcile #209/#212/#229 while preserving one service execution model and protected identity.
6. **Team C native clients:** #243 on the canonical A API, B signed package; real native UI/TUI and fallback with host receipts.
7. **Team D signed module, Fleet naming and synthetic Core:** #240/#242 and compatible isolated module lifecycle with no personal Core or Portainer writes.
8. **Team E complete final release QA:** exact-source signed Windows/Debian12 installed-host matrix, valid signer trust, negative security, no skips of mandatory checks, approve each row only through coordinator/owner.

**No-Go until a complete reviewed signed final Platform product exists.** This plan itself creates no signed release, permissions, merger or install authorization.
