# V18 continuation audit: exact 700-ID inventory, installed-wheel seeds and protected recovery

**Local date:** 2026-10-11 (America/Chicago); GitHub actions use UTC.
**Audit starting `main`:** `860cc9b6c67229bfa01984a9cf85847bbddf884e`.
**Most recently checked source after coding:** `4c1c335bc721983bb33ff13620ddd331a2ac74c4`.
**Original roadmap:** `docs/roadmaps/Sofia_Companion_Autonomy_Master_Roadmap_V18_Priority_Phases.md`, Git blob `9ea103b551b1e22ce7230202fdcc762eac63f050`.
**Shared evidence:** `docs/development/v18-task-evidence.json`, reviewed SHA `b3461b677fcf8464a100a956f224ea0d6a73bd75`, Git blob `f9160450268e6a4ef2d8699a02ea5e63f62e0324`.

## Inventory reconciliation, not an implementation percentage

All **700** original `CA-` IDs occur exactly once in V18, and the 700 ledger records agree exactly: no missing, foreign or duplicated ID. No CA checklist item was deleted, renamed, renumbered or silently accepted. Ledger status is older than many merged commits and is retained as a **point-in-time source assessment**, not overwritten from a speculative repository-wide percentage.

| Phase | Original | Code-present/unverified | Partially wired | Individually unassessed |
| --- | ---: | ---: | ---: | ---: |
| 00 | 65 | 0 | 23 | 42 |
| 01 | 66 | 4 | 16 | 46 |
| 02 | 30 | 0 | 15 | 15 |
| 03 | 46 | 0 | 25 | 21 |
| 04 | 22 | 0 | 11 | 11 |
| 05 | 41 | 0 | 26 | 15 |
| 06 | 73 | 0 | 27 | 46 |
| 07 | 26 | 0 | 1 | 25 |
| 08 | 56 | 0 | 4 | 52 |
| 09 | 66 | 2 | 9 | 55 |
| 10 | 27 | 0 | 3 | 24 |
| 11 | 49 | 0 | 1 | 48 |
| 12 | 24 | 0 | 13 | 11 |
| 13 | 63 | 0 | 16 | 47 |
| 14 | 12 | 0 | 1 | 11 |
| 15 | 22 | 0 | 1 | 21 |
| 16 | 12 | 0 | 2 | 10 |
| **Total** | **700** | **6** | **194** | **500** |

**Accepted in shared ledger: 0.** Six are source-traced candidates awaiting exact-SHA test and acceptance receipts, not deployed capabilities. 194 partial tasks are *not* production-code-complete. 500 have no sufficiently individual static trace, **not** 500 proven missing features.

Reference ownership: `v18-main-workstream-coordination-2026-10-11.md`. Evidence consulted from `v18-workstream1-status-2026-10-11.md`, `v18-workstream-2-phase03-06-report.md`, `v18-workstream-3-phase07-10-2026-10-11.md`, and `v18-workstream4-status-2026-10-11.md`. Those reports describe many post-ledger source slices. Their authored or reviewed tasks must not be silently promoted to complete or lost during WS1 serialized evidence merges.

## New source commits on main

1. [`ace59ee2db671794ea6cd2a4861502e0b8ce0a01`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/ace59ee2db671794ea6cd2a4861502e0b8ce0a01): repaired real `RuntimeStorageLayout.from_environment` seed routing for installed-wheel layouts without checkout `src/sofia`; declared `personality/personality.json` in package-data; added source-to-wheel seed/fail-closed regressions. **CA-3004 source hardening, still partial/unaccepted** until exact-SHA wheel release and verification proves this runs installed-only.
2. [`4c1c335bc721983bb33ff13620ddd331a2ac74c4`](https://github.com/Crazysodaman/SofiaAdaLyra/commit/4c1c335bc721983bb33ff13620ddd331a2ac74c4): `REQUIRE_EXISTING` provisioning now verifies the original canonical SQLite file and regular nonredirected Constitution/hash/identity paths; no normal-recovery startup reseeds protected or optional state. Explicit `FIRST_BOOTSTRAP` remains distinct. Added missing authority, missing personality and symlink regressions. This supports the CA-6804 recovery requirement and CA-3102 canonical-owner design, **neither CA is fully implemented or accepted**.

Both changes are production-source changes and focused test-source additions. This chat did not run tests locally, install a wheel, change the live state, deploy the VM or authorize migration. The upstream CI triggered by commits is an external signal and still requires exact-revision review.

## CI evidence and active blockers

At source SHA `860cc9b6`, Actions **Matrix Tests** `38191324057` and **Platform Compatibility** `38191324104` finished successfully. **Debian Release Candidate Build** `38191324074` failed at *Run exact revision provenance and verification* after exact-source reproducible wheel build and installation steps passed. The full Linux gate reported **526 failed, 4941 passed, 5 skipped, 6 deselected and 13 errors**. Many failures were `CanonicalStateUnavailable` for test temp files that historical tests still expect constructors to create, plus installed-wheel missing seed paths. This is *not* evidence of 526 separate code defects. The release gate itself remained failed.

On the same SHA, Windows package tests contained widespread `CanonicalStateUnavailable` failures and other independent regressions. The package run was subsequently cancelled; its incomplete aggregate cannot be represented as a finished current result. `pkg_body` and `pkg_clean` job steps finished successfully while other jobs failed or were in progress. Later commits continuously superseded Actions; older cancelled runs are not acceptance.

**Remaining release work:** reconcile tests that rely on implicit database creation with the explicit *authorized first-bootstrap fixture*; never revert the production no-create protection to make CI green. Verify packaged seeds from the installed wheel and exact-source parity; resolve independently observed UI/verification assertions and Windows resource-handle failures. Record final exact-SHA CI/live receipts only on completion.

## Dependency order and unchanged authority boundaries

- WS1 owns architecture, SAFE and CI/release; WS2 owns state/migration and MEM; WS3 owns LIFE/companion/skills; WS4 owns models/vision/Hephaestus/NEURO. This continuation did not overwrite the serialized shared ledger or another workstream's report.
- Venus is the current **only authoritative writer**. The future Debian 13 Sofia VM on Artemis is a *proposed supervised target*, never an automatic failover. Artemis controller and host Hyper-V permissions belong to the dedicated infrastructure chat, which made other `main` commits concurrently.
- No source commit here claims independently verified old-writer fencing, monotonic epoch cutover, live Debian provisioning or Hephaestus isolation tests.
- Gaming input injection into Venus remains forbidden; Linux/Windows vision and input need separate original-CA source proofs. LIFE, memory, model adaptation, NEURO and consciousness tasks remain assessed against their exact original requirements, not a shadow prototype.

## Next review queue

1. **Phase 00/01:** exact installer provenance and authority assets, CI SQLite test-bootstrap migration, exact wheel runtime tests, release signing/acceptance, remaining per-CA audits.
2. **Phase 02/03:** stop/revocation coverage, missing-authority recovery, external fencing and operator-witnessed migration. Infrastructure owner handles real Artemis changes.
3. **Phase 04–06:** mobile offline/restored-identity and canonical conversation/memory correctness with regression contracts.
4. **Phase 07–16:** continue workstream-owned source-to-effect review without upgrading mere module presence to task completion.

**Honesty gate:** The 700-ID inventory is fully reconciled. The complete 700-task *behavioral/source audit is NOT complete*. Exact remaining implementation effort cannot yet be calculated from an old conservative ledger.
