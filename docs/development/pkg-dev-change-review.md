# PKG-DEV: source-linked change proposal preflight

**Status:** independent offline code/tests on a draft package branch, not integrated with OpenCode or a mutating executor. A `requires_review` result is **not approval**. Ordinary package development permission cannot change protected identity, Constitution, production databases, credentials or data.

## Implemented

A typed immutable proposal requires a pinned 40-character source SHA, affected paths, evidence IDs, description, test and rollback plans. Read-only classification flags untrusted paths, protected files and ordinary files requiring independent review. It neither reads file contents nor executes commands, changes Git branches, invokes OpenCode or modifies files. Existing PKG-DEV codebase analysis remains authoritative, not replaced by this proposal screen.

**Focused tests:** `PYTHONPATH=src python -m pytest -q test/test_dev_change_review.py`. Equivalent staged source/test passed **41 focused tests on Linux Python 3.13.5 / pytest 9.0.2** on 2026-09-21. Actual GitHub checkout, Windows, CI, full-suite, OpenCode and Artemis: **not run**.

## Review when integrating

- Pin and verify actual codebase revision and real source/test evidence outside model output, reconcile existing codebase inspector and authority with proposed changes. Determine the actual OpenCode CLI and host installation on Artemis, filesystem roots and least-privilege sandbox; a local Venus command is not proof of server access.
- Use approved, scoped file changes with separate independent diff verifier and rollback, robust path resolution (the string classifier is **not** a symlink or filesystem security boundary), process timeouts, resource ceilings and command allowlists. Never infer authorization from an LLM-generated path or approve one's own patch.
- Test reproduce → propose → review → authorized patch → focused/full tests → forced failure/rollback. Protected amendments go through EVOLVE, never ordinary DEV authority; no silent model swap or source-code self-deployment.

No live executor, secrets, network, production DB, Constitution/identity, merge or deployment was changed. Preserve CORE → INTERACT → MEM → Sparks-only Discord → verified RUN → later authorized search.
