# PKG-CLEAN: read-only inventory preflight and review

**Status:** code and tests on independent draft branch, not merged or deployed. The code inventories only explicitly requested repository-relative regular-file metadata. A `REVIEW` record is a request for investigation, **not evidence a file is dead or permission to delete**. Protected identifiers, Constitution, data, secrets, backup, SQLite and state paths are rejected before inspecting contents; symlinks, unusual paths and missing files are `UNKNOWN`. No write, delete, subprocess, recursion, import traversal or cleanup executor exists.

**Focused test:** `PYTHONPATH=src python -m pytest -q test/test_clean_inventory.py`. Equivalent staged source passed **39 tests on Linux / Python 3.13.5 / pytest 9.0.2** on 2026-09-21. GitHub checkout, Windows and full repository pytest have not run; the code has no live deployment acceptance.

## Review when CLEAN is active

- Pin exact revision, inventory real entry points, dynamic loaders, tests, migrations, optional integrations and current feature branches; a missing file or search hit is not evidence of dead code.
- Independently verify Windows path and reparse-point handling; `lstat`-then-`lstat` is **not a security-grade race-free path operation**. Keep this scanner read-only and do not grant it file-write or removal authority. Audit unusual filesystem mount and hard-link behaviors.
- Define a reviewed cleanup register with file-by-file evidence, owner, behavior-preserving diff, backup/rollback and explicit approval before adding any mutation executor. Protect user's `state/sofia.db`, backups, secrets, identity and Constitution.
- Review baseline failures, run focused and current-head full tests after any later cleanup, and check live Windows application and backup restoration when affected. Do not disable tests or silently change model context to obtain green.

**Priority:** parallel read-only lane, no change to CORE → INTERACT → MEM → Sparks-only Discord → verified RUN → separately approved internet search.
