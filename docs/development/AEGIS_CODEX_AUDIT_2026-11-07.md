# Aegis | Codex Platform 1.0 status and evidence audit

**Observed:** 2026-11-07 (UTC, GitHub API snapshot).  
**Source:** Crazysodaman/SofiaAdaLyra, main at \`4d854a1a88516ab0b2eb49a848c8e42ed1aff493\` (merge #207).  
**Scope:** Status/evidence audit only, not a line-by-line security audit or installed-host test by this reviewer. PR descriptions, source inspection, CI job summaries and actual failed CI logs were reviewed.  
**Gate owners:** [#201 Platform-only](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201), [#120 full project](https://github.com/Crazysodaman/SofiaAdaLyra/issues/120), deferred [G8 #129](https://github.com/Crazysodaman/SofiaAdaLyra/issues/129).

**Verdicts: Platform-only shakedown NOT READY; full-project shakedown NOT READY; production GO not granted.** No production changes are authorized by this audit.

## 1. Codex implementation status

| PR | Subject | Observed |
| --- | --- | --- |
| [#202](https://github.com/Crazysodaman/SofiaAdaLyra/pull/202) | Rust Core-free OS service with native Windows SCM and Unix notify/drain | MERGED; CI reports actual native SCM/service tests |
| [#203](https://github.com/Crazysodaman/SofiaAdaLyra/pull/203) | Signed, inert Core-free Platform release manifest/verifier | MERGED; does not install/activate |
| [#204](https://github.com/Crazysodaman/SofiaAdaLyra/pull/204) | Disposable systemd lifecycle acceptance | MERGED; native Ubuntu CI real systemd test passed; not Debian production |
| [#205](https://github.com/Crazysodaman/SofiaAdaLyra/pull/205) | Exact-source two-boot offline Debian12 VM acceptance | MERGED; actual QEMU/VM CI passed with no Core/Ollama; not final signed installed OS release |
| [#206](https://github.com/Crazysodaman/SofiaAdaLyra/pull/206) | Neutral CPython runtime artifacts, Windows/Debian relocation | MERGED; actual relocation probes and Debian12 VM ran |
| [#207](https://github.com/Crazysodaman/SofiaAdaLyra/pull/207) | Redirected/corrupt artifact cache refusal | MERGED; three baseline defects reproduced, regressions fixed |
| [#208](https://github.com/Crazysodaman/SofiaAdaLyra/pull/208) | Signed Platform candidate code/runtime staging | OPEN; staging without service registration, activation or ownership grant |

At sampled PR #208 head \`30cf9e203c04b284995fc75e01df9f592da19ec4\`, targeted Platform-only, offline VM, G0-G1, G4, G5, G6 and component/cross-gate PR workflows were green. Do not infer full release or final candidate readiness from these targeted jobs. The code-stage receipt explicitly says activated=false, os_service_registered=false, service_health_verified=false.

PR #205 test evidence reports two independent VM boots, four clean stops, two crash recoveries, two duplicate instance denials, same installation UUID/key and generation advancement 1–6. PR #206 verifies actual bundled Python runtime relocation. These are materially stronger than import/unit-only smoke tests, but are still disposable test acceptance, not Venus/Artemis production commissioning.

## 2. Confirmed failing workflows on main 4d854a1

**Source: actual GitHub Actions job logs**, not inferred from workflow labels.

1. **[Package Tests run 42342975243](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42342975243)**: pkg_run fails one test: \`test_life_procedure_catalog.py::test_procedure_promotion_rechecks_original_source_under_writer_lock[downgrade_run]\`. Expected ValueError regex \`original LIFE/RUN/evaluation proof changed\`; observed \`procedure requires the real original scoped RUN receipt\`. Log summary: **1 failed, 1013 passed, 12 skipped, 7952 deselected**. Diagnosis unproven: check validation ordering, monkeypatched writer-lock race fixture and fail-closed effects before changing test assertion or production contract.
2. **[Windows RC run 42342975230](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42342975230)**: \`test_platform_optional_dependencies.py::test_platform_declares_optional_ollama_without_requiring_it\` fails with \`ComponentArtifactError: repository root with component manifest not found\`. Full gate: **1 failed, 8915 passed, 56 skipped, 6 deselected, 23 subtests passed**. The test calls \`load_component_manifest()\` without an explicit checkout path; \`repository_root()\` starts at installed module \`__file__\`, which cannot assume a source checkout. Determine whether test should explicitly inspect staged source manifest and independently verify wheel METADATA.
3. **[Debian RC run 42342975080](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42342975080)**: same manifest-discovery failure; full gate **1 failed, 8945 passed, 26 skipped, 6 deselected, 23 subtests passed**.
4. Both failed RCs then reported missing component upload artifacts, secondary consequences of skipped artifact construction after verification aborted. Do not count upload errors as independent root causes.
5. These three red workflows are separate from the **five known local live-Ollama failures** reported by Codex on earlier unfiltered local tests. No test, package or mandatory CI gate should be disabled/waived to obtain green.

**Blocking policy:** Full release may not claim CI GREEN or production readiness while above exact-head workflows fail. Fix narrowly, reproduce on both installed OS runner environments and rerun the full relevant gates.

## 3. Acceptance ledger drift

The checked authoritative [30-row Platform 1.0 matrix](PLATFORM_1_0_ACCEPTANCE.md) currently contains **0 PASS, 7 FAIL, 23 NOT TESTED** (full signed-release acceptance). FAIL IDs: **08** abrupt recovery policy, **10** authenticated CLI/IPC, **15** remote naming, **22** signed synthetic Core install, **23** synthetic lifecycle, **24** Core removal leaves Platform healthy, **30** operator runbook.

The matrix has genuine newer narrower service evidence appended for #202 but its table still lists Debian12 booted systemd evidence as pending, despite PR #205 reporting a successful disposable two-boot VM campaign. Issue #201's description is also lagging, still naming the Rust native service as the main next implementation priority. **Reconcile with exact source/CI/installed-artifact provenance**, not by promoting any whole rows to PASS automatically. Signed final release installer and comprehensive Windows/Debian installed-host receipts remain missing.

## 4. Remaining architecture gaps from inspected code and approved matrix

- **Installation and recovery:** #208 stages verified code but no signed OS installation/activation, real service registration, secure approval, durable anti-rollback selection, activation health check, rollback on interrupted upgrade or reinstall recovery.
- **Governed local controls:** Authenticated external CLI/IPC is FAIL #10; existing Rust broker journals and service ownership do not equal protected management interface.
- **Fleet:** Atomic admission/revocation and designated local callsign authority exist; verified remote naming and full live two-host authenticated management remain missing (#15).
- **Modules:** Signed generic module install/process isolation, rollback, stale grant denial and release-host verification remain incomplete.
- **Synthetic Core:** Signed stage/install, separate approval/activation, start/stop/detach and remove-with-Platform-health remains missing (#22–24).
- **Release integrity:** End-to-end signed release artifacts and installers, update/rollback anti-rollback, SCM/systemd release provisioning, operator runbook and signed host evidence remain open.
- **Core-free UI:** The AG-D007 detailed Control Center UI is **DESIGN DOCUMENTED, NOT IMPLEMENTED**. Do not add UI work to #201 without explicit owner scheduling.
- **Sofía cognition:** Full Core, Ollama-live and G7-A/full-project acceptance must remain separate. Platform-only CI cannot certify Sofía herself.

## 5. Recommended order for Codex (not a new authorized scope)

1. **P0 current CI correctness:** reproduce Windows/Linux manifest-root failure and pkg_run writer-lock test; preserve independent installed-wheel verification; fix cause without weakening assertions, then rerun Package Tests, both RCs and full exact-SHA checks.
2. **P0 status truth:** reconcile #201 and matrix with #202–207 evidence, label what is disposable test-only vs final installed release; keep 30 acceptance rows conservatively NOT TESTED/FAIL until complete.
3. **P1 complete #208:** verify signed staging, mutation/race tests, source revision and recheck copy. Ensure the receipt remains unambiguously NON-ACTIVATED and no owner grant is inferred.
4. **P1 establish governed installer + approval + service activation:** prepare signed Platform install/reinstall/update/rollback, durable anti-rollback floor, service-side SAFE/STOP, exact host/version identity and interrupted-operation reconciliation.
5. **P1 platform management:** build authenticated, revocation-fenced CLI/IPC before management GUIs, then remote Fleet naming and signed generic module lifecycle.
6. **P1 synthetic Core shakedown:** use signed inert/synthetic Core without Sofía state; install, activate, stop, detach, remove and prove Platform continuity.
7. **P2 final release acceptance:** complete Windows/Debian exact source/SHA installed-host receipts and signed artifact evidence; update operator runbook, independently review before status promotion.
8. **Release fence:** no automatic production deployments, migration, Fleet enrollment or G8 activity; do not interrupt Codex for AG-D007/Fleet Manager UI design implementation unless explicitly reprioritized.

## 6. Aegis AG-D status

| Design ID | Snapshot |
| --- | --- |
| AG-D001 | IN PROGRESS, release acceptance still NOT READY |
| AG-D002 | PARTIAL SIGNATURE/CORE BOUNDARY; synthetic lifecycle NOT ACCEPTED |
| AG-D003–AG-D006 | Captured/owner-desired designs; native manager production commands not accepted |
| AG-D007 | Detailed Control Center layout/paths specification exists; implementation NOT SCHEDULED |
| AG-D012 | Fleet foundations implemented; native Fleet Manager and remote naming unaccepted |
| AG-D019–AG-D021 | Captured proposals only; not an implicit Codex work assignment |

**Audit limit:** This review checked current GitHub PR metadata, source fragments, acceptance matrix, exact-head workflow/job results and full failed job logs. It did not execute tests locally, inspect private runner images or access production host services. PR descriptions are author claims cross-checked where accessible with public CI, not independently re-run production acceptance. All verified facts apply only to the specified snapshot; subsequent Codex commits may change these results.
