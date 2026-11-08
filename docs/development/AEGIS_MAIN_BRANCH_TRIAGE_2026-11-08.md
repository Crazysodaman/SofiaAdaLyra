# Project Aegis | main-only branch inventory and disposition snapshot

**Date:** 2026-11-08. **Compared against:** `ec1cce6cf059a3d84136eccd0abd731239a84aac`. **Scope:** 141 non-backup, non-main GitHub refs. **Original owner backup:** `backup/main-before-unification-20261108`.

## Audit semantics

- `IN_MAIN_ANCESTOR`: GitHub compare returned ahead_by=0; branch tip is already in main ancestry. Do not replay or re-merge.
- `CANDIDATE_CONFLICT_REVIEW`: divergent branch with plausible unique useful changes, but file-level semantic and safety review is REQUIRED before any selective port.
- `HOLD_FAILURE_OR_STALE_EVIDENCE`: prior recovery failure or stale combined source. Never replay whole tree or promote test results.
- `DIVERGED_REVIEW`: ahead_by>0, **not proof that unique usable work is absent from main**; historical forks can contain old variants already replaced. Audit changed blobs and contracts before any merge.

**Totals from individually executed GitHub compare checks:** 50 `IN_MAIN_ANCESTOR`, 91 diverged and require dispositions; not 91 outstanding required merges. This document is a branch discovery/triage ledger, NOT proof every divergent branch has been semantically reconciled.

## Owner-approved working branch policy

`main` is the ONLY active engineering branch. Retain historical refs/PRs for recovery; never automatically delete/force-push them. Preserve exact file/blob evidence when marking a branch superseded. Respect SAFE/STOP, signing, revocation, identity, one writer and authenticated installed-host checks. No production service activation.

## Artifact Library D028 release gate

D028-00 signed publisher trust and authenticated owner authority: NOT ACCEPTED.
D028-01 offline independent signed installer: INSTALLED-HOST EVIDENCE PENDING.
D028-02 selective packages/catalog: SOURCE FOUND, integrated true catalog/producer/installer E2E pending.
D028-03 authenticated LAN Hub listener and immutable bytes: NOT DEMONSTRATED.
D028-04 enrolled peer transfer over real mTLS: NOT DEMONSTRATED.
D028-05 durable resume/quotas/rollback/GC: INTERNAL RECEIVER COMPONENT ONLY, broader lifecycle pending.
D028-06 GUI/TUI actual same-service workflow: NOT DEMONSTRATED.
D028-07 LIB-01–LIB-16 independent Windows/Debian installed-host verification: 0/16 accepted (latest known source ledger); recheck before changing any PASS state.

**Engineering evidence:** Internal bounded receiver and sender, signed-manifest/catalog/license pins, aggregate quotas and fail-closed revocation gates at `c5dc9982`; 12 focused disposable local tests passed (not original-repository or multi-host acceptance). No network listener, actual publisher authority, installed-host grant, GUI/TUI execution or approved install operation is supplied by these primitives. The canonical publisher trust, host transport and B1 install/rollback remain separate contracts. Do not mistake a test callback for owner SAFE authority.

## Complete remote-ref listing

| Ref | HEAD | Disposition |
|---|---|---|
| `chatgpt/ag-d026-module-rationalization-20261108` | `33f7ba020cdd` | CANDIDATE_CONFLICT_REVIEW |
| `chatgpt/ag-d027-module-batch02-20261108` | `3f3e4ab06d2e` | CANDIDATE_CONFLICT_REVIEW |
| `chatgpt/ag-d028-artifact-hub-distribution-20261108` | `8d5c7ae58fde` | IN_MAIN_ANCESTOR |
| `chatgpt/b1-install-forward-port-20261108` | `7b4a5e763735` | DIVERGED_REVIEW |
| `chatgpt/ca700-phase-review-rollup-20261105` | `20397a8f7372` | DIVERGED_REVIEW |
| `chatgpt/core-002-ollama-failclosed-20261108` | `15efd8337f60` | DIVERGED_REVIEW |
| `chatgpt/core-team1-lifecycle-c001-20261108` | `20bf12a3613f` | DIVERGED_REVIEW |
| `chatgpt/core-team3-continuity-20261108` | `4b2766e5e1fa` | IN_MAIN_ANCESTOR |
| `chatgpt/core-team4-corelink-20261108` | `36c96442097a` | IN_MAIN_ANCESTOR |
| `chatgpt/core-team5-ig001-integration-20261108` | `ce6fa8c405b2` | IN_MAIN_ANCESTOR |
| `chatgpt/debian-vm-readiness-evidence-20261108` | `9262a97ecf0c` | DIVERGED_REVIEW |
| `chatgpt/debian-vm-startup-failure-classification-20261108` | `1eb89e118b3f` | DIVERGED_REVIEW |
| `chatgpt/full-ci-rust-and-life-hotfix-20261105` | `b832f83e53ad` | DIVERGED_REVIEW |
| `chatgpt/g0-g1-release-integrity` | `9fc88ab96a26` | DIVERGED_REVIEW |
| `chatgpt/g0-g7a-package-ownership-bridge` | `bf61c4c308e4` | DIVERGED_REVIEW |
| `chatgpt/g2-current-corelink-store-selection` | `e38b0e94d2d1` | DIVERGED_REVIEW |
| `chatgpt/g2-worker-installed-root-link-fence-20261105` | `86d237807789` | DIVERGED_REVIEW |
| `chatgpt/g3-replication-read-fencing` | `2c2901a023e2` | DIVERGED_REVIEW |
| `chatgpt/g4-core-link-transport` | `7a0e4ee1d244` | DIVERGED_REVIEW |
| `chatgpt/g5-recovery-evidence` | `2530ec58c829` | DIVERGED_REVIEW |
| `chatgpt/g6-module-lifecycle` | `817a631c0fe3` | DIVERGED_REVIEW |
| `chatgpt/g7-commissioning-preflight` | `4e7aced78ac3` | DIVERGED_REVIEW |
| `chatgpt/g7a-evidence-truth` | `92b1d686f56e` | DIVERGED_REVIEW |
| `chatgpt/go-live-release-env-version` | `904bef4275e3` | IN_MAIN_ANCESTOR |
| `chatgpt/hybrid-700-evidence-register` | `c2f17de19018` | DIVERGED_REVIEW |
| `chatgpt/hybrid-700-task-evidence-register` | `c0b66a994b02` | DIVERGED_REVIEW |
| `chatgpt/hybrid-ci-owner-proof-regression` | `f480a82bbccc` | DIVERGED_REVIEW |
| `chatgpt/life-outreach-receipt-clock-20261105` | `85b3b324a420` | DIVERGED_REVIEW |
| `chatgpt/life-postrun-receipt-clock-20261105` | `6bbfbc48c945` | DIVERGED_REVIEW |
| `chatgpt/module-rationalization-batch1-20261108` | `3b584a62dbd0` | CANDIDATE_CONFLICT_REVIEW |
| `chatgpt/module-rationalization-batch01` | `7bbf7174a60d` | CANDIDATE_CONFLICT_REVIEW |
| `chatgpt/owner-256-bit-secret-approval` | `7ee8cc0e0812` | DIVERGED_REVIEW |
| `chatgpt/p1-contract-verify-dependencies` | `182671028678` | DIVERGED_REVIEW |
| `chatgpt/p2-rust-dependency-remediation` | `f496444a4194` | DIVERGED_REVIEW |
| `chatgpt/p3-g7a-reconcile-evidence-regressions` | `11105f92458c` | DIVERGED_REVIEW |
| `chatgpt/pkg-interact-receipt-clock-20261105` | `0f5e55cd016a` | DIVERGED_REVIEW |
| `chatgpt/pkg-safe-mtls-ci-clock-20261105` | `936ee8de0e08` | DIVERGED_REVIEW |
| `chatgpt/platform-1-acceptance-preflight-20261108` | `4a4e2dcca7e3` | DIVERGED_REVIEW |
| `chatgpt/platform-1-management-readonly-20261108` | `4c4156cbe1b2` | DIVERGED_REVIEW |
| `chatgpt/platform-1-ui-live-observation-20261108` | `6b3fc4e9b8c0` | DIVERGED_REVIEW |
| `chatgpt/platform-gui-shell-20261108` | `2e796cb77d7c` | DIVERGED_REVIEW |
| `chatgpt/platform-installer-shell-20261108` | `dc5a118b8c03` | DIVERGED_REVIEW |
| `chatgpt/platform-management-dispatch-20261108` | `345db70f2eb2` | DIVERGED_REVIEW |
| `chatgpt/platform-management-reply-contract-20261108` | `e6cdaa63beec` | DIVERGED_REVIEW |
| `chatgpt/platform-read-dispatch-20261108` | `a706224f063c` | DIVERGED_REVIEW |
| `chatgpt/platform-read-management-dispatch-20261108` | `99f20270fe8c` | DIVERGED_REVIEW |
| `chatgpt/platform-settings-view-20261108` | `019bdfa85fd3` | DIVERGED_REVIEW |
| `chatgpt/platform-signed-installer-preview-20261108` | `fe39c686602f` | DIVERGED_REVIEW |
| `chatgpt/platform-status-response-v1-20261108` | `8fa289b8821f` | DIVERGED_REVIEW |
| `chatgpt/platform-tui-binary-smoke-20261108` | `39ec7046d499` | DIVERGED_REVIEW |
| `chatgpt/platform-tui-shell-20261108` | `87b8d1c68296` | DIVERGED_REVIEW |
| `chatgpt/platform-unix-os-peer-20261108` | `fddc4ae78c61` | IN_MAIN_ANCESTOR |
| `chatgpt/platform-vm-startup-readiness-20261108` | `0057e44214b7` | DIVERGED_REVIEW |
| `chatgpt/platform-win-gui-shell-20261108` | `7fa6fd940cca` | DIVERGED_REVIEW |
| `chatgpt/platform-windows-control-center-shell-20261108` | `c439b4ef9293` | DIVERGED_REVIEW |
| `chatgpt/r1-windows-cargo-bootstrap-20261105` | `1ab73bee619a` | DIVERGED_REVIEW |
| `chatgpt/r2-current-enrollment-boundary` | `90471534ec8e` | DIVERGED_REVIEW |
| `chatgpt/r2-debug-redaction-20261108` | `0796efc43879` | DIVERGED_REVIEW |
| `chatgpt/r2-diagnostic-only-raw-transport-20261105` | `0473e6767cc9` | DIVERGED_REVIEW |
| `chatgpt/r2-enrollment-not-before-20261105` | `27b7bf8560fe` | DIVERGED_REVIEW |
| `chatgpt/r2-history-cursor-secret-redaction` | `7b488dd61899` | DIVERGED_REVIEW |
| `chatgpt/r2-main-consolidated` | `1bd5024a665d` | DIVERGED_REVIEW |
| `chatgpt/r2-pinned-tls-before-http` | `8946c5db855a` | DIVERGED_REVIEW |
| `chatgpt/r2-pre-dispatch-binding-recheck-20261105` | `e24834d9d5d3` | DIVERGED_REVIEW |
| `chatgpt/r2-probe-privacy-boundaries` | `56fde6425ab2` | DIVERGED_REVIEW |
| `chatgpt/r2-response-revocation-fence-20261105` | `715bf92d803a` | DIVERGED_REVIEW |
| `chatgpt/r2-rust-response-acceptance-20261105` | `717f90046628` | DIVERGED_REVIEW |
| `chatgpt/r2-server-send-recheck-20261105` | `442e66dd3db3` | DIVERGED_REVIEW |
| `chatgpt/r3-appearance-identity-validation-20261105` | `e7172240b368` | DIVERGED_REVIEW |
| `chatgpt/r3-calendar-validation-20261105` | `d30b2cbbc5b2` | DIVERGED_REVIEW |
| `chatgpt/r3-durable-appearance-restore-contract-20261105` | `0a9c79fe8938` | DIVERGED_REVIEW |
| `chatgpt/r3-r5-desktop-policy-foundation` | `fa4d00088a80` | DIVERGED_REVIEW |
| `chatgpt/r3-restore-reconciled-main-20261105` | `53574e7ba50a` | DIVERGED_REVIEW |
| `chatgpt/r3-tray-shutdown-lifecycle-20261105` | `ffe0a510bc2f` | DIVERGED_REVIEW |
| `chatgpt/r6-host-observer-identity-20261105` | `4cab34dadee7` | DIVERGED_REVIEW |
| `chatgpt/r6-r7-host-safety-contracts` | `af5c55bbe38e` | DIVERGED_REVIEW |
| `chatgpt/r6-r7-reconciled-main` | `977173ca8998` | DIVERGED_REVIEW |
| `chatgpt/r6-restart-generation-fence-20261105` | `87fbb290b91b` | DIVERGED_REVIEW |
| `chatgpt/release-regressions-20261105` | `0ed89c2a94e2` | DIVERGED_REVIEW |
| `chatgpt/sdk-reference-module-20261108` | `8f0a9f9a72bc` | IN_MAIN_ANCESTOR |
| `chatgpt/team-a-linux-management-listener-20261108` | `9a830ab26aed` | IN_MAIN_ANCESTOR |
| `chatgpt/team-c-platform-ui-consolidation-20261108` | `d12c9c53c705` | IN_MAIN_ANCESTOR |
| `chatgpt/team-d-236-224-forcedkill-recovery-probe-20261108` | `1ee89b8cf4fd` | HOLD_FAILURE_OR_STALE_EVIDENCE |
| `chatgpt/team-d-242-bounded-first-ready-proof-20261108` | `145aa726caf4` | HOLD_FAILURE_OR_STALE_EVIDENCE |
| `chatgpt/team-d-ag-d028-module-closure-20261108` | `aea6cdff2162` | IN_MAIN_ANCESTOR |
| `chatgpt/team-d-d007-a-native-guest-ipc-evidence-20261108` | `03de6f080578` | IN_MAIN_ANCESTOR |
| `chatgpt/team-d-module-worker-negative-20261108` | `c5c9178ac3e2` | IN_MAIN_ANCESTOR |
| `chatgpt/team-d-portainer-reconcile-20261108` | `9184ab8078bb` | CANDIDATE_CONFLICT_REVIEW |
| `chatgpt/team-d-remote-fleet-boundary-20261108` | `43404546d6c8` | IN_MAIN_ANCESTOR |
| `chatgpt/team-e-release-qa-20261108` | `1cf8ad046be3` | IN_MAIN_ANCESTOR |
| `chatgpt/v18-700-owner-crosswalk-20261102` | `fe9d3efa5024` | DIVERGED_REVIEW |
| `chatgpt/verify-preserve-started-main-runs-20261105` | `3bc66c65db56` | DIVERGED_REVIEW |
| `codex/aegis-broker-verified` | `dbea1da9b95b` | IN_MAIN_ANCESTOR |
| `codex/aegis-core-definitions` | `97a57d261a99` | IN_MAIN_ANCESTOR |
| `codex/aegis-core-link-authority` | `47c7c18c08a3` | IN_MAIN_ANCESTOR |
| `codex/aegis-corefree-verified` | `7a0274e18ce0` | IN_MAIN_ANCESTOR |
| `codex/aegis-debian-vm-acceptance` | `73bad4b960d8` | IN_MAIN_ANCESTOR |
| `codex/aegis-fleet-atomic` | `6e68cae5c381` | IN_MAIN_ANCESTOR |
| `codex/aegis-fleet-callsigns` | `ff5d33247a9e` | IN_MAIN_ANCESTOR |
| `codex/aegis-fleet-removal` | `c13ce6a30fbc` | IN_MAIN_ANCESTOR |
| `codex/aegis-generic-core-runtime` | `f9b64bb39864` | IN_MAIN_ANCESTOR |
| `codex/aegis-identity-contract` | `626db04f1592` | IN_MAIN_ANCESTOR |
| `codex/aegis-installation-bootstrap` | `4c08a85f210c` | IN_MAIN_ANCESTOR |
| `codex/aegis-installed-cli-fixture` | `0894520f9a27` | IN_MAIN_ANCESTOR |
| `codex/aegis-local-state-redirect` | `dbf8e03d89a6` | IN_MAIN_ANCESTOR |
| `codex/aegis-module-owner-principal` | `d7c972faa7da` | IN_MAIN_ANCESTOR |
| `codex/aegis-net-revocation` | `a4d63109d438` | IN_MAIN_ANCESTOR |
| `codex/aegis-neutral-providers` | `6b844110eb5b` | IN_MAIN_ANCESTOR |
| `codex/aegis-ops-owner-principal` | `2e8ac4d2e735` | IN_MAIN_ANCESTOR |
| `codex/aegis-platform-cache-security` | `d0c1396634f1` | IN_MAIN_ANCESTOR |
| `codex/aegis-platform-one` | `cc8178e5df14` | IN_MAIN_ANCESTOR |
| `codex/aegis-platform-release-contract` | `275d8bfc2a4c` | IN_MAIN_ANCESTOR |
| `codex/aegis-python-runtime` | `9c8a31cde185` | IN_MAIN_ANCESTOR |
| `codex/aegis-recovery-verified` | `5b6ecfd14cfc` | IN_MAIN_ANCESTOR |
| `codex/aegis-release-ci-correctness` | `9549268d44e7` | DIVERGED_REVIEW |
| `codex/aegis-release-staging` | `30cf9e203c04` | IN_MAIN_ANCESTOR |
| `codex/aegis-restore-owner-proof` | `77a8270a04f6` | IN_MAIN_ANCESTOR |
| `codex/aegis-runtime-followups` | `38f24c733c34` | IN_MAIN_ANCESTOR |
| `codex/aegis-rust-service` | `86016572c56a` | IN_MAIN_ANCESTOR |
| `codex/aegis-security-verified` | `7c3d081d2f08` | IN_MAIN_ANCESTOR |
| `codex/aegis-shakedown` | `cf315ce27c57` | HOLD_FAILURE_OR_STALE_EVIDENCE |
| `codex/aegis-signed-owner-principals` | `951b71ab9e32` | IN_MAIN_ANCESTOR |
| `codex/aegis-signed-vm-install` | `a8c867d9762e` | DIVERGED_REVIEW |
| `codex/aegis-systemd-acceptance` | `e07ba2e3f174` | IN_MAIN_ANCESTOR |
| `codex/aegis-tool-binding-isolation` | `dca0ab5a5bd3` | IN_MAIN_ANCESTOR |
| `codex/aegis-windows-journal` | `d233643fbd0d` | IN_MAIN_ANCESTOR |
| `codex/constitution-v2-proposal` | `91b6a11ae69c` | DIVERGED_REVIEW |
| `codex/module-documents` | `84c3997319b0` | DIVERGED_REVIEW |
| `codex/r1-rust-sdk-contracts` | `b065b58c6014` | DIVERGED_REVIEW |
| `codex/r2-readonly-core-link` | `b08b137aa5cd` | DIVERGED_REVIEW |
| `codex/rust-modernization-plan` | `409ceddf0fa8` | DIVERGED_REVIEW |
| `opencode/b1-install-lifecycle` | `7e11c5b77121` | CANDIDATE_CONFLICT_REVIEW |
| `opencode/p0-release-ci-correctness` | `22bf91fb9571` | IN_MAIN_ANCESTOR |
| `opencode/p0-signed-vm-release` | `2a9dc0b85f8b` | IN_MAIN_ANCESTOR |
| `opencode/p0-v18-gate4-timing` | `368764bc2b47` | DIVERGED_REVIEW |
| `opencode/r2-readonly-core-link-hardening` | `2ebc34e07751` | DIVERGED_REVIEW |
| `opencode/ui-shakedown-reconcile` | `e0f1b079f67b` | CANDIDATE_CONFLICT_REVIEW |
| `team-b/ag-d011-installer-preview-20261108` | `e40700717f39` | IN_MAIN_ANCESTOR |
| `team-e/ig001-disposable-platform-e008-20261108` | `31566e303a99` | HOLD_FAILURE_OR_STALE_EVIDENCE |
| `team-e/ig001-disposable-platform-e009-20261108` | `1ad9681c311c` | IN_MAIN_ANCESTOR |
| `work` | `05a58db559c0` | IN_MAIN_ANCESTOR |

## Required next reconciliation

1. Verify overlapping module D026/D027/Portainer and OpenCode B1/UI candidates file-by-file; prefer current canonical implementations, import independently useful tests only when compatible.
2. Older R2/R3/CI forks remain historical and require semantic comparison before applying old snapshots.
3. Deliver canonical authenticated publisher-index and owner enrollment contract, then Hub/peer service integration and actual end-to-end signed package transfer.
4. Run exact-main Rust/Python CI, disposable Windows and Debian 12 service tests, plus independent LIB-01–LIB-16 acceptance. No synthetic PASS.


## Exact blob audit after main consolidation (2026-11-08)

**Verified workflow:** [read-only main-only branch blob triage](https://github.com/Crazysodaman/SofiaAdaLyra/actions/runs/42530305184) at `37534701542835a6cd37159237efdc44ff795c25`. The machine-readable 141-ref result is stored as the workflow artifact `aegis-main-only-branch-triage` (no branches deleted, force-pushed or merged by the workflow). The audit compares changed-file **blob hashes** against current main, not merely branch age or commit counts.

| Class | Count | Current decision |
|---|---:|---|
| IN_MAIN_ANCESTOR | 50 | Usable work is already historically incorporated; do not merge again |
| IN_MAIN_BY_BLOB_CONTENT | 12 | Identical changed-file bytes already in main; keep historical refs, do not replay |
| REVIEW_ADDITIVE | 3 | Actual new files exist; evaluate security/overlap before selective import |
| REVIEW_TEST_OR_DOCS | 1 | Constitution v2 proposal is documentation only; not approved as release behavior |
| REVIEW_COLLISION | 75 | Existing main files differ; HOLD whole-branch merges pending semantic/security tests |

**Adjudicated additive candidates (explicit byte/path review):**

1. `chatgpt/module-rationalization-batch01`: distinct `src/sofia/modules/integrations/portainer_projection.py`, matching read-only test and AG-D027 roadmap document. **PRESERVE / OPTIONAL SELECTIVE PORT** after module ownership review. Not required to operate D028; do not enable Portainer or copy protected host data.
2. `chatgpt/platform-read-management-dispatch-20261108`: distinct historical `src/sofia/platform/application/management_read_service.py` plus its tests/workflow, but main already owns a different canonical `src/sofia/platform/run/management_read.py`. **HOLD AS SUPERSEDED API ALTERNATIVE**, no second management authority; evaluate individual tests only.
3. `chatgpt/platform-win-gui-shell-20261108`: distinct older `packaging/ui/Start-AegisControlCenter.ps1` shell while main already has `packaging/gui/Start-AegisControlCenter.ps1`. **HOLD AS SUPERSEDED UI ENTRYPOINT**, no duplicate launcher; evaluate isolated tests if current coverage lacks them.
4. `codex/constitution-v2-proposal`: docs-only, **OWNER DECISION PENDING**, not a Core personality migration permission.

**Known collision priorities:** AG-D026 and AG-D027 module branches modify existing Portainer, cognition and SAFE code; `opencode/b1-install-lifecycle` contains an older installer/permission variant. **DO NOT WHOLE-MERGE** those forks over the signed B1, STOP/SAFE or current Platform baseline. Extract only independently testable non-duplicate fixes, or preserve as historical evidence after source review.

**Use this interpretation:** IN_MAIN_BY_BLOB_CONTENT is a verified file-level result, not necessarily full ancestry. REVIEW_COLLISION is a review queue, NOT proof that a branch is bad or that all its unique ideas are integrated. Archive the source history, do not discard it. The latest D028 Hub/mTLS code is additive, requires canonical installed owner enrollment/publisher verification, and does not grant installed-host acceptance.
