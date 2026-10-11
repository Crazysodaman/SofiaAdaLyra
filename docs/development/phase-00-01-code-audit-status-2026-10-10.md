# Phases 00–01: code/audit status and deferred acceptance ledger

**Base:** GitHub `main` at `e85c52f0`. **Current coding checkpoint:** `d7654d78a070332800384150a5a71061644b29f3` (2026-10-10).  
**User constraint:** write code and conduct source audits, but **do not execute tests**. Commit messages use `[skip ci]`.  
**Interpretation:** Code created or edited is NOT CI accepted, not Windows accepted and not end-to-end LIFE accepted.

## Concrete source changes on main

| Source / concern | Exact implementation or audit | Coded | Tested |
| --- | --- | --- | --- |
| Canonical-owner architecture | `docs/development/companion-autonomy-contract.md` and earlier Phase 00 source map; one authoritative owner per concern, three flow diagrams, SAFE/evidence limits | Yes | No |
| Companion decision audit | `src/sofia/application/decision_trace.py` exposed as `SofiaApplication.latest_companion_decision_trace()`. Read-only Matrix projection, explicit noncausal NEURO timestamp and unset unproven fields | Yes | No |
| Static source reuse/removal audit | `src/sofia/verify/architecture_inventory.py` and documentation: parse AST, assert expected owner source paths, report potential duplicated function bodies without deleting anything | Yes | No |
| Release checkout duplication | Clean `git archive` staged outside checkout, not `release-source/test` underneath pytest discovery | Yes | No |
| Release source integrity | `src/sofia/verify/source_provenance.py` compares staged bytes to Git HEAD blobs and checks imported package originates in the isolated release environment | Yes | No |
| Release workflow source/provenance wiring | New source-provenance step, distinct artifact receipt; corrected YAML indentation and uses `RUNNER_TEMP` via step `GITHUB_ENV` | Yes | No |
| Release toolchain | Removed unpinned `pip install --upgrade pip` in isolated release environment; existing locked production/verification dependencies retained | Yes | No |
| BODY package test grouping | `test/conftest.py` now explicitly marks `test_body_*` with `pkg_body`; retains unique existing tests | Yes | No |
| Windows locked `sofia.db` | Close `_database_counts()` SQLite handle explicitly via `contextlib.closing`; normal `SofiaApplication.shutdown()` now closes primary conversation and UI draft stores, reusing failed-start cleanup semantics | Yes | No |
| LIFE result reconciliation | `SelfDirectedLifeCoordinator.pending_work_review()` projects canonical RUN job statuses with explicit missing receipt/uncertainty/review state; `tick` surfaces this evidence without granting new authority | Yes | No |
| LIFE objective inspection | `src/sofia/life/validation.py` verifies exact artifact bytes/hash and explicit `text_contains:`/`min_bytes:` criteria; natural-language objectives remain unknown; read-only coordinator projection cannot auto-complete | Yes | No |
| LIFE critique replay | `evaluate_artifact()` returns prior record on identical repeated review and refuses contradictory same-revision review absent a separate correction process | Yes | No |
| Phase 6 Windows path repair | Existing SHA-derived safe path code in `creative/paths.py` reused, not reimplemented. Canonical IDs remain unchanged | Pre-existing | Historical results only |
| Historical roadmap truth | Reconciled old "uncommitted/not merged" Windows path repair status on root `ROADMAP.md`; new phase notes do not claim tests passed | Yes | n/a |

## Explicitly NOT completed by code alone

1. **Phase 00 live baselines:** p50/p95, GPU/VRAM, voice/avatar actual receipts, real two-model overlap, long-term memory correction, runtime/failover RPO/RTO, Hephaestus network identity decisions must be verified under real hardware constraints.
2. **Phase 00 independent causal trace:** The current decision trace intentionally does not join unrelated LIFE/MEM/ACT/NEURO outcomes by timestamp. A verified shared turn/event ID and authority-respecting joins are still needed before claiming a complete causal autobiography.
3. **Phase 01 previous CI failures:** Historical 20/22 package jobs passed; `pkg_body`, `pkg_verify`, Release Candidate were red, Manual Verification cancelled at audited `e85c52f0`. No new workflow runs were executed to demonstrate repairs.
4. **Phase 01 LIFE complete cycle:** Source can create native artifacts and now expose unreviewed RUN results; a **read-only structural and explicitly typed objective validator registry** now exists, but independent admission of criteria, creative authoring/revision, automated evidence-based critique/completion, and proven future learning are still unfinished. No current completion claims can be inferred from hash checks alone. An executor receipt proves the artifact exists, not that it satisfies the whole creative brief.
5. **Phase 01 Artemis canary hardening:** `Setup-SofiaFleetArtemis.ps1` still has broad LocalSubnet firewall and unpinned dependency install. A staged hardening Git commit was **not accepted on main**, so it must not be represented as implemented. Its human-supervised prepare/install/verify path remains a canary, never permission to create a VM.
6. **Phase 01 package, integration, release, Windows, manual, multi-day and real-hardware gates:** no tests permitted in this pass. This phase's *release acceptance* is therefore **open by definition**.
7. **Removed-code audit:** No production deletion is currently defensible based on search alone. Dynamic Python imports, Windows services, retained migration readers, UI entrypoints and serialized data require tests/receipts before any removal.

## Upcoming gate order when the user separately allows tests

1. Verify exact Git SHA, inspect workflow YAML syntax and Python imports/typing.
2. Run targeted BODY, VERIFY, CORE/LIFE and release provenance checks on Windows.
3. Run all 22 package families, Matrix, Platform and Release Candidate at same SHA; inspect any failures/skips, no green-by-omission.
4. Run real Venus production startup, two models, memory/emotion/activity, Discord/UI channels; repeat after shutdown/restart.
5. Perform pinned-mTLS Artemis canary with human-reviewed firewall/source scope and pinned dependency lock; do not treat synthetic mTLS as guest OS provisioning.
6. Run multi-day LIFE, archive/restore and Fleet recovery drills only with separately authorized safe infrastructure.

**State labels:** `coded / source-audited / tests-deferred / CI-unaccepted / live-unaccepted`. No checkboxes are closed as `production-accepted` merely because the source exists.
