# PKG-VERIFY: offline evidence gate and review ledger

**Status:** draft code preflight on a package branch, not merged, integrated, deployed or a verified release. Base: `main` at branch creation, 2026-09-21.

## Implemented slice

`sofia.verify` provides an immutable typed check record, status (`passed`, `failed`, `not_run`, `not_applicable`), execution tier (`offline`, `integration`, `live`), exact 40-character commit SHA, environment, time and source reference. `assess_gate` only accepts matching package/revision evidence meeting the required tier, blocks newer or simultaneous failures, requires actual-system evidence when specified and refuses zero acceptance requirements. This is *not* a test runner, proof of identity or authenticated attestation. The `actual_system` field is a claim made by the caller; the human/release system must independently verify its origin.

**Offline command:** `python -m pytest -q test/test_verify_evidence_gate.py` with editable package installation or `PYTHONPATH=src`. Equivalent staged source/test passed **27 tests on a Linux container with Python 3.13 / pytest** on 2026-09-21; verify GitHub branch checkout independently before merging. Actual Windows, full repo pytest, CI and real service/live model tests: **not run**.

## Review at package gate

1. Bind a real command or runner to externally captured, immutable and authenticated test evidence. Validate runner identity, actual machine, exit status, test count, logs and source SHA outside model-generated text. Separate simulated receipts from real renderer, Discord, Artemis or Gaia acknowledgments.
2. Prevent evidence-ID collisions, malformed versions, duplicate requirement names, forged future timestamps, tampering and replacing earlier failures in durable storage. Define authorized corrections and deletion/retention, privacy-safe log references and recovery after reboot.
3. Define the actual package-specific acceptance requirements in protected/reviewed release configuration; generic caller-supplied requirements alone do not authorize a release. Require human sign-off and CI/host proof at the selected gates.
4. Test Windows, pinned source revision and the coordinated full suite, and verify independent real live evidence. A green offline fixture is never proof of 24/7 operation, personality quality, UI animation or physical stop.

**Scope:** no CI modifications, no production database, no network/search grant, no automated merging or deployment, and no identity/Constitution modifications. Keep CORE → INTERACT → MEM, then Sparks-only Discord → verified RUN → separately authorized internet search.
