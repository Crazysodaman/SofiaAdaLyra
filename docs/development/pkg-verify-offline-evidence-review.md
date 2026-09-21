# PKG-VERIFY: evidence-tier preflight and review

**Status:** isolated offline candidate, not integrated, accepted, merged or deployed. Repo base `main`.

## Coded slice

`src/sofia/verification/evidence_gate.py` checks named criteria against observed `offline` / `integration` / `live` tiers, explicit `passed` / `failed` / `not_run` / justified `not_applicable` outcomes and a target revision. A passing offline mock is insufficient for a criterion requiring real live operation; missing or stale evidence blocks. Empty or duplicate sets fail safely. Tests use no network, CI, deployment or production state.

**Focused test:** `PYTHONPATH=src python -m pytest -q test/test_verification_evidence_gate.py`. Equivalent isolated code on Python 3.13.5 / pytest 9.0.2: **20 passed**; together with MEM's 23, 43 passed. GitHub checkout/CI/Windows/full-suite results **not run**. Tests were staged with a local test-only `sofia.conversation.model` fixture for MEM; it is not part of either PR.

## Review at package gate

- This module accepts claimed evidence text and claimed tiers; it **cannot authenticate** external CI logs, Ollama output, renderer receipts, hardware measurements, actor or revision. Bind to trusted runners/verifiers and tamper-evident evidence with actual dates, version and machine.
- Verify real SHA/pinned revision beyond checking string equality; decide which statuses may be `not_applicable` and require independent human review for exceptions. Never let a model self-approve its own results or declare a skipped live check irrelevant.
- Expand to a durable per-package ledger, failure triage, pre/post performance and personality review, Windows/full-suite, Discord DM, GPU, outage/soak and Gaia physical tests as features become available. Record negative tests and rollback.
- Review alongside the existing test harness and any CI workflows to avoid duplicate authorities. No automatic merge, code execution, permissions, protected-state modification or deployment is granted by this gate.
