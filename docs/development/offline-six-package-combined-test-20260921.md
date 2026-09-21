# Six original-package offline preflights: combined focused test evidence

**Date:** 2026-09-21. **Environment:** isolated Linux container, Python 3.13.5, pytest 9.0.2. **Not a full Sofia repository checkout, CI run, Windows acceptance, production test, package integration or release approval.**

## Tested package slices

- CLEAN `feature/pkg-clean-review-preflight`, draft PR #14: read-only inventory, 39 tests.
- ACT `feature/pkg-act-outreach-preflight`, draft PR #15: opt-in proposal eligibility, 46 tests.
- BODY `feature/pkg-body-simulator-preflight`, draft PR #16: synthetic non-hardware servo rig, 36 tests.
- DEV `feature/pkg-dev-change-proposal-preflight`, draft PR #17: source-linked read-only proposal screen, 41 tests.
- SAFE `feature/pkg-safe-disclosure-preflight`, draft PR #18: private reflection and exact grant preflight, 35 tests.
- EVOLVE `feature/pkg-evolve-amendment-preflight`, draft PR #19: immutable protected amendment proposal, 24 tests.

**Combined command** (with the six staged `src` folders on `PYTHONPATH`, all six original focused test files selected): `python -m pytest -q -o cache_dir=/tmp/sofia_offline_package_combined_pytest_cache <six test paths>`. **Observed:** `221 passed in 0.19s`. Tests were run in the same Python process, with distinct `sofia` namespace modules and no production services, database, Ollama, Discord, renderer or robotics. Earlier BODY test fixture had an unused import removed; rerunning its 36 tests yielded a test file hash matching the committed GitHub branch. Git blob SHA matches were also checked for the other six source and test files. This evidence shows only these isolated slices co-exist without failing their selected tests; it does not establish compatibility with the real `main` package installation or existing subsystem APIs.

## Deferred proof

For each PR, check out its exact head commit against the real repository; run focused tests there, Windows tests, cross-package integration and the agreed coordinated full pytest after INTERACT's gate. Confirm host-enforced identity/grants, real channel receipts, actual Windows paths and physical emergency stops where applicable. A successful mocked outcome is not a live capability. PR #4 indexes all original 13 packages and 3 proposed additions; these six do **not** complete the other packages.

**Status:** all PRs draft, unmerged, undeployed. No protected identity/Constitution, production `state/sofia.db`, credentials, general internet search, physical hardware or live Discord was changed by these tests.
