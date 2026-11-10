# Project Aegis | D028 B1 streaming release + signed rollback pins
**Date:** 2026-11-10
**Deployment scope:** Personal, single owner; private Windows/Debian hosts and independently enrolled homelab Platforms. Not a commercial publisher, SaaS, marketplace or external distribution service.
**Status:** Source committed on canonical `main`. NEW TESTS NOT RUN. No installed-host acceptance and no final CI claim.

## Completed connected source slice

1. `src/sofia/platform/ops/platform_signed_asset_copy.py` provides one exclusive, bounded 64-KiB streaming copy of an independently publisher-signed Platform asset, checking exact signed SHA-256, size, source inode and timestamps before/after, owner-private destination, durable new file, and post-copy digest. Destination is removed on failure; an existing installed target cannot be silently overwritten.
2. Original `platform_release_staging.py` and `platform_installation.py` now both use that shared writer. No second install engine, no new release manifest, no owner grant or change to the B1 receipt schema, signature verifier, anti-rollback checkpoint, install/activate/rollback controls or STOP boundary.
3. `src/sofia/platform/verify/python_runtime.py`: CPython 3.12 bundle creation now streams non-native member files rather than storing the full prefix in a Python dictionary; only the bounded native executable is buffered for ABI verification. ZIP member verification and extraction use bounded reads plus publisher-referenced SHA and declared uncompressed sizes, full ZIP SHA before/after, strict canonical manifest and private destination. The existing neutral Core-free ZIP layout remains.
4. `src/sofia/platform/ops/library_b1_rollback_pins.py` resolves historical B1 install receipts to independently verified, currently trusted publisher-signed installed assets. It refuses missing historical releases, pending install attempts, changed assets, revoked signer keys, and torn receipt/history reads. Its exact digests feed the already existing `build_library_pin_graph` as `ROLLBACK_RETAINED`.

## Regression coverage committed, not executed

- `test/test_ops_platform_signed_streaming_copy.py`: 2 MiB and 64 MiB bounded-memory copies; wrong SHA, source substitution, redirects, existing target, and cleanup after mismatched destination verification.
- `test/test_python_runtime_artifacts.py`: actual producer -> verifier -> materializer with a 16 MiB standard library file, no eager ZIP or non-native file reads, plus signed-ZIP tampering refusal; preexisting deterministic runtime tests unchanged.
- `test/test_ops_platform_installation.py`: complete disposable Ed25519 signed B1 stage/install with any eager asset reads forbidden; actual signed installation receipt/revision floor; historical signed asset inventory, rollback pin graph, revoked publisher, altered installed bytes and unresolved installation denial.

Recommended focused original-repository commands:

```bash
python -m compileall -q src/sofia/platform/ops/platform_signed_asset_copy.py src/sofia/platform/ops/platform_release_staging.py src/sofia/platform/ops/platform_installation.py src/sofia/platform/ops/library_b1_rollback_pins.py src/sofia/platform/verify/python_runtime.py
python -m pytest -q test/test_ops_platform_signed_streaming_copy.py -m "not slow"
python -m pytest -q test/test_python_runtime_artifacts.py test/test_ops_platform_installation.py -m "not slow"
python -m pytest -q test/test_ops_platform_signed_streaming_copy.py -m slow
```

Run with exact `main` SHA and repo-declared dependencies before independent release signoff. The chat environment cannot clone GitHub due unavailable github.com DNS; none of these tests was run here.

## Remaining hard gates

- Complete installed-service signed B1/Fleet owner trust and enrolled mTLS source/recipient end-to-end on real disposable Debian 12 and Windows hosts. The signed historical pin adapter is **NOT** a synchronized live B1 pin revision lock: current stage, dependency, transfer and owner pins remain mandatory before destructive GC can be enabled.
- Finish native Windows and Linux CLI/TUI/GUI Library control from independently installed Platform trust profiles with authentic current SAFE/STOP/role, not from client flags. Finish same-SHA Rust/Python D028-00 contract/installer acceptance.
- Signed Core/runtime/module package dependency lifecycle, B1 activation/rollback and crash recovery, host installer + supervisor under real installed identity.
- Continue semantic useful-branch reconciliation into `main` without security regressions. Finish focused original-checkout tests, then full final GitHub CI, then owner-authorized live-hardware shakedown.
- Do not improve LIB-01..LIB-16 or #201 Platform 38-row acceptance ledger from presence of source/tests. Last recorded independent counts remain LIB 0/16 PASS, Platform 0/38 PASS pending exact installed-host evidence.

**GO:** NO. No real host state changed and no new production owner approval was issued in this batch.
