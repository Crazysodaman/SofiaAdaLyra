# PKG-CLEAN | branch readiness roadmap

**2026-09-21 | draft PR #14 | baseline head `1c95e016c523fe61c956d3b3b721d0ef3c4bfccc`.** Companion `pkg-clean-review.md` and `package-clean-interact-lab-contracts.md`; the original CLEAN outcome is behavior-preserving maintenance. No destructive cleanup is approved by this roadmap.

## Existing evidence and limitations

Read-only candidate-file metadata inventory with protected data/identity/Constitution filters, traversal and symlink rejection, no mutation/deletion API. **39 focused tests passed on equivalent staged Linux source.** A candidate tagged REVIEW is not proved unused or deletable; `lstat` path scanning is not race-free OS enforcement, especially on Windows reparse points. Windows branch checkout/current full-suite NOT RUN.

## Implementation, verification and decision gates

1. Pin actual source SHA and inventory imports/dynamic loading, entrypoints, tests, CLI, service and database migrations, generated assets, optional integrations, deployment files and active PR changes. Preserve original user conversations, journals, backup files, Constitution/identity and permissions.
2. Maintain file-by-file cleanup register: real usage evidence, behavior/ABI impact, package owner, risk classification (doc/static, refactor, migration, deletion), smallest diff, rollback, required approval and expected tests. **No search hit is not proof of dead code.** Prefer reversible docs/format changes and fix stale roadmaps without modifying protected material.
3. Check Windows path casing, junction/reparse/symlink traversal and TOCTOU; never treat a string-based or local `lstat` classifier as authority to delete. Cleanup executor, if any, belongs behind independently authorized DEV/SAFE controls with dry-run and verified backup/restore.
4. Run actual branch focused tests and `git diff --check`, existing CLI/conversation/memory/security/restart subset, full pytest on coordinated accepted branch and any changed dependency/packaging tests on real Windows. Compare before/after model latency and grounding on matched prompts for optimization, not an anecdotal speed claim.
5. Test negative cases: dynamically loaded module falsely marked unused, retained SQLite originals accidentally removed, changed schema without migration, bad dependency version, leaked secret, interrupted cleanup and rollback failure. Stop and revert affected change on evidence or behavior regression.

## Open review decisions

Which specific files/technical debt are candidates, accepted baseline failures, dynamic consumers, Windows/deployment topology, backup location, retention/rebuildable cache criteria and whether any deletion is independently authorized. No blanket `git clean` or branch-history rewrite.

**Exit:** read-only inspection slice tested in isolation only; actual repo inventory, Windows/reparse checks, approved cleanup diffs, full regression and recovery NOT RUN. No merge/deploy/delete.
