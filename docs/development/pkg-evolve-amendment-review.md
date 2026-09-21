# PKG-EVOLVE: protected-amendment proposal preflight

**Status:** isolated proposal code/tests on draft package branch, not merged, integrated, enabled, applied or a Constitution amendment. This code **cannot approve or edit** identity/Constitution. It performs no independent signature verification, authorization, file read or write.

## Implemented

Immutable `AmendmentProposal` requires target (`identity` or `constitution`), original and proposed SHA-256 digests, evidence IDs, reason, rollback plan, creation and expiry. `inspect` compares trusted caller-supplied observed digest with expected original and distinguishes source mismatch, expired, uncertain clock, unchanged and explicit-review-required cases. The `requires_explicit_review` result is **not approval**; no `approve` or `apply` API exists. Source and proposal contents are not trusted merely because their SHA-256 strings are well formed.

**Focused tests:** `PYTHONPATH=src python -m pytest -q test/test_evolve_amendment.py`. Equivalent staged source/tests passed **24 focused tests on Linux Python 3.13.5 / pytest 9.0.2**. GitHub checkout, Windows/CI, full repo and live protected-amendment exercise: **not run**.

## Review when EVOLVE is active

- Inspect current identity and Constitution integrity code and canonical approval procedures; do not create a competing protected-state authority. Independently read and hash the actual pinned files, verify authentic proposal issuer and authorized human review; a model-generated `evidence_ids` tuple is not proof of consent.
- Define multi-step authenticated explicit amendment approval, separately reviewed diff and rollback, immutable audit, protected backups, tamper recovery and restart verification. Preserve identity continuity and forbid implicit amendment from a preference, conversation text or Git merge.
- Test source mismatch and forced failed amendment using safe copied fixtures and pinned Windows/full-suite verification, then separately record human-approved protected change if ever requested. No protected state is changed in this branch.

Release order remains CORE → INTERACT → MEM → Sparks-only Discord → verified RUN → separately authorized internet search. No network, production database, autonomous self-redefinition, merge or deployment in this slice.
