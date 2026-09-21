# PKG-CLEAN | Evidence-backed maintenance and preservation

**Branch:** `feature/pkg-clean-foundation`, independent from `main` SHA `2141879`. **Status:** read-only eligibility prototype plus tests. Nothing is deleted, moved, reformatted in bulk, migrated or reset; the production database and timestamped backup are out of scope.

## Target
Reduce duplicate/dead code, stale docs, excessive prompt assembly and unused assets only when there is evidence they are unused and a tested recovery path. CLEAN is a maintenance lane, not an override of INTERACT → MEM priority, independent branch ownership or user-specific dirty changes. A path that appears redundant may still be loaded dynamically or referenced by a deployment process.

## Slices
1. **L0 inventory:** pin SHA; enumerate code, tests, dependencies, entry points, config, DB schemas, secrets, backups, untracked files, historical contracts and current PR ownership. Search full references and runtime behavior before labeling anything unused.
2. **L1 classify:** separate safe formatting, measured performance, duplicate behavior, unused candidates and protected/runtime state. Source-linked candidate manifest includes owner, why, impact, path, hashes, references and test coverage.
3. **L2 nondestructive plan:** dry-run diff, confirmed verified backup, rollback, dependency scan and owner review. `src/sofia/package_foundations/clean.py` only decides whether a generic manual plan is eligible; it cannot authenticate review, resolve symlinks, prove liveness or authorize deletion.
4. **L3 minimal scoped changes:** one isolated cleanup with behavior-preserving tests, import-order/cross-platform review and migration compatibility. No simultaneous unrelated feature refactoring or silent Constitution/identity rewrite.
5. **L4 measured optimization:** benchmark before/after context size, latency and memory; preserve authoritative fact availability and safety guarantees. Smaller prompts are not automatically more truthful.
6. **L5 recovery:** restore from copy, verify hashes, restart and replay, compare feature tests and inspect unexpected state changes; revert independently when evidence fails.

## Acceptance and boundaries
Run `python -m pytest -q -x test/test_pkg_clean_foundation.py`, then tests for symlink/path escape, missing reference in dynamic loaders, stale owner review, DB schema rollback, removed test evidence and adverse prompt compression. Full-suite plus relevant live tests are required after any change that can affect behavior. Never run `git clean`, reset/stash someone else's edits, erase the backup or rewrite shared history to make the tree look clean. SAFE owns protected paths and retention, VERIFY owns measured comparisons, each package owner approves its boundaries. This branch ships no cleanup executor and has no accepted merge or deployment.
