# OpenCode takeover | Aegis Platform 1.0

**Status:** OWNER-REQUESTED HANDOFF PLAN. Not proof that OpenCode has run.  
**Audit snapshot:** 2026-11-07; GitHub `main` `d437624b18dfe45da8f55ae625820b0f10e9e2c2`.  
**Repository:** `Crazysodaman/SofiaAdaLyra`.  
**Authoritative gate:** [Platform-only #201](https://github.com/Crazysodaman/SofiaAdaLyra/issues/201); [30-row acceptance matrix](PLATFORM_1_0_ACCEPTANCE.md); parent [full project #120](https://github.com/Crazysodaman/SofiaAdaLyra/issues/120).  
**Context:** [Codex audit](AEGIS_CODEX_AUDIT_2026-11-07.md), [Design TODO](../roadmaps/AEGIS_DESIGN_TODO.md), [AGENTS.MD](../../AGENTS.MD).

> **Platform-only shakedown READY: NO. Full-project READY: NO.** Work in disposable development state only. No production enrollment, live migration, hidden authorization, Core identity mutation, G8 execution or owner-service cutover is approved.

## 0. Transfer control and avoid double writers

The owner is switching the development executor from Codex Cloud to local OpenCode. **GitHub cannot establish whether Codex's workspace has been stopped.** Before editing a shared branch or PR, obtain confirmation that Codex is paused/stopped; do not assume absence of GitHub activity proves exclusive ownership. Do not use simultaneous agents on the same files/branch.

At the snapshot there were **two OPEN DRAFT Codex PRs**:
- [#210: Fix reproduced installed-wheel and delayed-receipt release CI failures](https://github.com/Crazysodaman/SofiaAdaLyra/pull/210), head `9549268d44e7766b2078d185f21b40ec9b45667c`, all 12 observed exact-head PR workflows passed, including Package Tests and Windows/Debian Release Candidate Build; still not merged.
- [#209: Boot disposable Debian12 VM from signed staged Platform artifacts](https://github.com/Crazysodaman/SofiaAdaLyra/pull/209), head `a8c867d9762e514aa08ab86d833c74d2aebd739b`, signed-staged **actual offline Debian12 two-boot VM** CI passed; final full local validation/reconciliation was reported pending; still not merged.

**First live action:** requery `main`, #209, #210, checks, base/head commits, changed files and outstanding reviewer comments. They may have changed since the snapshot. If the PRs are still open, adopt/review/reconcile **rather than reimplement** them. Prefer separate worktrees and explicit merge coordination. Never force-push an agent-owned branch. Owner approval is required for push, PR merge, service modification or any production action under AGENTS.MD.

## 1. Startup audit (no changes until complete)

1. Read `AGENTS.MD`, `docs/development/PLATFORM_1_0_ACCEPTANCE.md`, issue #201, this handoff and both PRs. Check actual local `git status --porcelain=v1`, branch, HEAD and remote tracking.
2. Preserve ALL existing worktrees, untracked files, local state, private keys and unknown modifications. No `reset --hard`, `clean -fd`, branch deletion, rebase/force-push or destructive cleanup.
3. `git fetch origin --prune` only with normal Git credentials; do not paste tokens/256-bit secret into the prompt, PowerShell history or logs.
4. Confirm evidence at exact SHA. Record what is OBSERVED versus PR description CLAIMED versus UNKNOWN. Review overlapping source/test/workflow files and reconcile concurrent updates before coding.
5. Check whether Codex is still active. If so, do not modify its open PRs/branches or same-files work; report the conflict and preserve its work.

## 2. P0: Finish the two existing Codex PRs, not duplicate them

**PR #210:** The last observed `main` full release failed for two distinct reasons:
- In an installed-wheel Windows/Debian venv, `test_platform_optional_dependencies.py::test_platform_declares_optional_ollama_without_requiring_it` searched for checkout `packaging/components.toml` starting at installed module `__file__`, raising `ComponentArtifactError`.
- Package Tests' `test_life_procedure_catalog.py::test_procedure_promotion_rechecks_original_source_under_writer_lock[downgrade_run]` expected the writer-lock revalidation error but encountered early original-receipt denial. It used a synthetic scheduler baseline with a later authentic RUN receipt.

PR #210 proposes passing an explicit checkout root in the **test** (while preserving separate installed-wheel METADATA validation), using a controlled delayed genuine receipt test that still validates final writer-lock denial, and enabling exact-head PR Package + both RC workflows. Inspect the actual diff; do not relax the fail-closed production checks, do not simply change expected messages, do not modify production LIFE freshness/permission semantics to make a test green. Confirm full PR CI on both OSes, merge/reconcile only after explicit owner approval, then rerun on resulting exact `main` SHA. The five independently tracked live Ollama failures remain visible and must never be silently skipped/renamed.

**PR #209:** Inspects a signed staged *disposable* Debian12 release in two real offline VM boots with real wheels, bundled Python runtime and native service binary. The test signer is memory-only, NOT a production release signer or owner identity. Confirm exact-head VM result, signed bundle and staged-asset receipts, source hash, installed binary and wheel hashes, identity/generation and process lifecycle. Run its pending full tests and reconcile over #210 after the CI fix is integrated. Do not invent production installation, durable anti-rollback or owner approval from test signatures.

**Completion evidence:** concrete merged PRs, source SHAs, successful exact-head and post-merge runs, failure diagnosis, tests not disabled and remaining release limitations. PR green does not override issue #201.

## 3. P1: Continue Codex's Platform 1.0 campaign in small approved batches

Implement the next **existing #201 requirements**, with tests and bounded PRs. Order by dependency, not visual feature preference:

**B1 | Signed, independently installable Platform.** From #203–208 release verification/runtime/cache/staging and #209 VM evidence, implement a governed code-to-install transition: exact owner approval, signer/revision/current predecessor checks, durable anti-rollback, dependency/SBOM and ABI compatibility, service account/ACL ownership, activation and service-health receipt, crash-safe rollback/repair. Keep stage/install/activate as distinct operations; candidate bytes, developer signer and test receipts must never grant owner authority. Do not replace or activate any real host.

**B2 | Windows/Debian service packaging.** Genuine signed OS installer and native service registration/provisioning/stop/restart/recovery paths; native Windows SCM and Debian12 systemd exact-target acceptance with installed release bytes. No dependency on Sofía Core, model provider, GPU or desktop UI. Verify uninstall/reinstall retains Platform identity only as approved, with no second writer or accidental Core deletion.

**B3 | Authenticated local management CLI/IPC.** Single versioned Rust-owned command/control boundary consumed by CLI and future GUI. Current owner enrollment/revocation, exact principal and scoped SAFE approval, STOP, anti-replay, generation and identity checks before dispatch and before returning protected outcomes. Secret authentication must use protected interactive methods, not arguments, logs or Core-generated attestations. A stable API is the prerequisite for AG-D007.

**B4 | Fleet and module acceptance.** Finish remotely authenticated callsign authority with offline/stale and revocation semantics; distinguish discovery from trust. Finish generic signed modules' staged install, scoped activation, process isolation, crash/revocation, update and rollback with installed-host receipts.

**B5 | Synthetic Core lifecycle.** Use only a safe **signed synthetic nonpersonal Core** to demonstrate list/stage/install/activate/status/deactivate/uninstall; distinct binding, generations, no hidden Core launch, no personal Constitution/memory import and no second SQLite writer. Platform stays healthy after Core removal. Actual user-favored `aegis core install .\Sofia.corepkg` examples are interface proposals until independently implemented and verified.

**B6 | Release certification.** Close signed update/recovery, interrupted upgrade/reinstall/backup/rollback, complete operator runbook, exact-SHA CI and independent Windows/Debian disposable installed-host checks. Every one of #201's 30 rows requires its defined complete evidence before PASS. Keep the G8 physical-host tests separately deferred.

**Out of scope until separately approved:** AG-D007 Control Center UI, AG-D012 Fleet Manager GUI, AG-D019 Developer Workshop UI, personal Sofía Core cognition/avatar, real production enrollment, release signing with an unapproved identity, G8 production migration.

## 4. Working rules and acceptance

- Root authority is `AGENTS.MD`; source observations beat old PR summaries. Do not reopen completed #192–208 infrastructure without a confirmed defect.
- Human approval required before consequential pushes/merges and any host/service/state changes. Development may proceed locally on clean, isolated worktrees after the owner stops Codex. Never state a remote push or PR merge was executed unless Git confirms it.
- Separate synthetic Platform data and real personal Sofía state. No host secrets, 256-bit owner secret, signer private keys or personal memory in artifacts, logs, prompts or test fixtures. FIDO2 remains disabled/optional absent a separate owner decision.
- Never disable/relax tests or waive live Ollama integration results. Platform-only tests do not imply full project GO.
- Stage changes in independently reviewable batches, not one giant PR; use target tests, full unfiltered suite, Rust fmt/Clippy and exact-head Windows/Debian CI where appropriate. Record OS-specific skips and reasons.
- If the environment lacks QEMU/SCM/systemd/production signer, report a genuine BLOCKED/NOT TESTED state and rely on GitHub native CI or disposable fixtures as scoped. Do not simulate real results.
- Never directly change canonical writer host, Fleet authority, installed Windows service on Venus, Artemis/VM, network enrollment or protected Core data.
- Preserve and link existing Aegis design TODOs but **do not** quietly add new design features to Platform 1.0 acceptance.

## 5. Required reporting format after each batch

1. **Snapshot:** local branch, `git status`, starting HEAD, ending commit SHA, PR/push/merge status and exact target main.
2. **Implementation:** files changed and source-backed behavior; which #201 rows are narrowed, still FAIL or NOT TESTED.
3. **Verification:** actual commands, tests, pass/fail/skip counts, exact CI URLs/SHAs, OS and installed-vs-container-vs-VM differentiation; last five live Ollama failures separately tracked.
4. **Risks:** unresolved approvals, red jobs, incomplete install/rollback, missing owner credential integration, stale Fleet trust.
5. **Next batch:** exactly what remains, no fake completion percentage or automatic next-host activation.
6. **GO:** Platform-only shakedown NO/YES by the authoritative acceptance matrix, full-project NO/YES separate and G8 deferred.

## 6. First immediate OpenCode task

**Start at P0, not B1.** Read and compare #210 and #209 against current main, verify no active Codex overlap, reproduce any remaining failures, reconcile completed PR work with authorization, then identify the smallest safe B1 install/activation slice. Execute code and tests where authorized; do not stop after writing a plan. Do not merge or push until the owner approves that consequential operation. Summarize status using section 5.
