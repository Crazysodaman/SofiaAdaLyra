# PKG-DEV | Source inspection and authorized engineering

**Branch:** `feature/pkg-dev-foundation` based on `main` SHA `2141879`. **Status:** side-effect-free proposed-change validator only. No code edits, OpenCode command, terminal access, test runner, Git write or automatic restart is enabled.

## Goal and dependencies
Sofía can investigate a reproducible defect, cite source evidence, prepare a minimal change, obtain appropriately scoped authorization, run bounded tools, test the exact result and recover on failure. Reuse the existing codebase inspector, authority gateway, test runner and installed local OpenCode where **independently verified on the executor host**. A CLI present on Venus is not proof that Artemis can run it. CORE supports grounded explanations; SAFE controls authorizations and resource isolation; VERIFY owns independent acceptance.

## Work slices
1. **D0 inspect:** inventory actual source, repository state, applicable tests, existing connectors/CLIs and protected paths. No changes to code or user's dirty tree during inspection; report missing evidence.
2. **D1 deterministic proposals:** produce a source-linked issue, expected before/after, affected files, pinned content hashes, test command and rollback strategy. New `src/sofia/package_foundations/dev.py` rejects absolute/traversal paths and missing content digests; this does not guard symlinks or authorize a write.
3. **D2 isolated executor:** create a sandbox/worktree with explicit allowlisted files and operations, short time/resource quotas, no ambient network/secret access and independent cancellation. Resolve symlinks and repo-root containment at execution time.
4. **D3 OpenCode adapter:** verify exact binary/version on active host, typed requests/results, bounded stdout/stderr, exit/timeout, no tool auto-approval, impersonation or unrestricted command expansion.
5. **D4 test and review:** focused tests first, exact-SHA full tests as appropriate, diff/path/content-hash verification by host, dependency and security review, and user-visible failure evidence. A model-written claim `tests passed` is not test evidence.
6. **D5 commit and recovery:** separate scoped Git approval, signed/auditable provenance when configured, safe rollback on failure, no force-push by default, and explicit restart/deployment permission distinct from commit permission.

## Acceptance
Run `python -m pytest -q -x test/test_pkg_dev_foundation.py` and add execution-time traversal/symlink, malicious instructions in source, dirty-worktree, wrong digest, denied tool, timeout, test-fail, conflicting branch and rollback tests. Then demonstrate reproduce -> proposal -> approval -> isolated edit -> actual tests -> independently verified diff -> deliberate merge, including a forced failure. Preserve protected Constitution and identity, real user state and existing PRs. Full suite/live acceptance not run on this new branch. No background self-modification is authorized merely by writing this roadmap.
