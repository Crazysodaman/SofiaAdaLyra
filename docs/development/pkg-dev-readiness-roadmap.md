# PKG-DEV | branch readiness roadmap

**2026-09-21 | draft PR #17 | baseline head `f480f3396c3653a6954b7bb37281b54ab4b064ad`.** Companion: `pkg-dev-change-review.md`, original `ROADMAP.md` DEV section, `opencode.md` contract. No execution is authorized here.

## Prepared / evidence

Read-only proposal checker requires pinned source SHA, source evidence, changed paths, tests and rollback plan. Flags protected/state/credential paths. **41 focused tests passed on equivalent isolated Linux source**. String path screening is not canonical filesystem/symlink security; `requires_review` is not approval. Real OpenCode/Artemis execution, Windows checkout and full tests NOT RUN.

## Work and review gates

1. Inspect/reuse existing `sofia.codebase` analyzer/inspector, file capability gateway, project Git policy and DEV/test runner. Pin repo SHA and enumerate actual project root, protected files, generated assets and host-specific paths.
2. Build an inspect → evidence-linked diagnosis → proposed diff/test/rollback → independently granted bounded execution → exact diff validation → focused/full tests → reviewed commit → separately authorized restart pipeline. Distinguish actions and results, log no secrets; never allow an LLM or OpenCode process to approve its own patch, protected amendment, or release.
3. Execute only inside isolated checkout/worktree with authenticated operator, path canonicalization and symlink/reparse protections at OS boundary, command allowlist, time/CPU/network quota, stop/kill and file-change scope. No ambient unrestricted shell or Git pushes.
4. Reconcile OpenCode CLI availability on **actual execution host** (Venus install does not imply Artemis install); verify supported invocation, output/trust format, permission prompts and failure handling. Deny if missing rather than silently installing a service.
5. Test a reproducible bug: inspect → propose → explicit approval → patch → real tests → independently verify diff; inject failed test, interrupted process and unauthorized file edit and prove safe rollback. Run current Windows and coordinated repo suite on pinned SHA. Protected Constitution/identity changes belong solely to explicit EVOLVE workflow.

## Decisions at DEV gate

Execution host, OpenCode install/adapter version, allowed repositories and commands, reviewer identity, allowed test cost, approvals for commit versus push versus restart, restore strategy and where private source snippets may be sent. Never infer grants from previous ordinary Git commit consent.

**Exit:** proposal contract only; executor/real OpenCode/rollback/Windows/full tests NOT RUN. No file modification, merge, deployment or protected-state change.
